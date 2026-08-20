import { useEffect, useRef, useState } from "react";
import { todayIso } from "../lib/format";

export interface DatePickerProps {
  value: string; // ISO yyyy-mm-dd, or "" for unset
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  ariaLabel?: string;
  max?: string; // ISO yyyy-mm-dd
  min?: string; // ISO yyyy-mm-dd
  disabled?: boolean;
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function toIso(y: number, m: number, d: number): string {
  return `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

function parseIso(iso: string): Date | null {
  if (!iso) return null;
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? null : d;
}

function formatDisplay(iso: string): string {
  const d = parseIso(iso);
  if (!d) return "";
  return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}/${d.getFullYear()}`;
}

// Reduces "02a/5x9-2023" to "02/05/2023" as the user types - strip
// non-digits, cap at 8 digits (ddmmyyyy), re-insert the slashes. Rebuilding
// from scratch on every keystroke (rather than patching) means backspace
// across a slash just works, with no separate delete-key handling needed.
function maskDateText(raw: string): string {
  const digits = raw.replace(/\D/g, "").slice(0, 8);
  let out = digits.slice(0, 2);
  if (digits.length > 2) out += "/" + digits.slice(2, 4);
  if (digits.length > 4) out += "/" + digits.slice(4, 8);
  return out;
}

// Returns the ISO date if `text` is a complete, real calendar date
// (rejects e.g. 31/02/2023), else null.
function parseTypedDate(text: string): string | null {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(text);
  if (!m) return null;
  const day = Number(m[1]);
  const month = Number(m[2]);
  const year = Number(m[3]);
  const d = new Date(year, month - 1, day);
  if (d.getFullYear() !== year || d.getMonth() !== month - 1 || d.getDate() !== day) return null;
  return toIso(year, month - 1, day);
}

// The native <input type="date">'s calendar popup can't be styled at all
// (worse than <select>, which at least honors background-color/color on
// <option> - this ignores CSS entirely) and, on this app's mobile viewport,
// wasn't opening on tap at all. This is a full replacement: a real text
// input (typing a dd/mm/yyyy date commits it directly, same as the native
// field always allowed) plus a separate calendar-icon button that opens a
// custom popup - clicking the text area only ever types, clicking the icon
// only ever opens the picker, matching how a native date input's text
// segments vs. its picker-indicator behave.
export default function DatePicker({
  value,
  onChange,
  placeholder = "dd/mm/yyyy",
  className,
  ariaLabel,
  max,
  min,
  disabled,
}: DatePickerProps) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(() => formatDisplay(value));
  const selected = parseIso(value);
  const [viewYear, setViewYear] = useState(() => (selected ?? new Date()).getFullYear());
  const [viewMonth, setViewMonth] = useState(() => (selected ?? new Date()).getMonth());
  const rootRef = useRef<HTMLDivElement>(null);

  // Only re-syncs from the committed value, so a partially-typed ("02/0")
  // in-progress date is never clobbered mid-keystroke - onChange only ever
  // fires once typing resolves to a complete, valid date anyway.
  useEffect(() => {
    setText(formatDisplay(value));
  }, [value]);

  useEffect(() => {
    if (!open) return;
    const d = selected ?? new Date();
    setViewYear(d.getFullYear());
    setViewMonth(d.getMonth());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onClickOutside = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClickOutside);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const maxDate = max ? parseIso(max) : null;
  const minDate = min ? parseIso(min) : null;

  const isDisabled = (iso: string) => {
    if (maxDate && iso > toIso(maxDate.getFullYear(), maxDate.getMonth(), maxDate.getDate())) return true;
    if (minDate && iso < toIso(minDate.getFullYear(), minDate.getMonth(), minDate.getDate())) return true;
    return false;
  };

  const handleTextChange = (raw: string) => {
    const masked = maskDateText(raw);
    setText(masked);
    const iso = parseTypedDate(masked);
    if (iso && !isDisabled(iso)) {
      onChange(iso);
    }
  };

  const prevMonth = () => {
    if (viewMonth === 0) {
      setViewMonth(11);
      setViewYear((y) => y - 1);
    } else {
      setViewMonth((m) => m - 1);
    }
  };
  const nextMonth = () => {
    if (viewMonth === 11) {
      setViewMonth(0);
      setViewYear((y) => y + 1);
    } else {
      setViewMonth((m) => m + 1);
    }
  };

  // A fixed 6x7 grid, filled with the trailing days of the previous month
  // and leading days of the next, so the layout never reflows month to
  // month.
  const firstOfMonth = new Date(viewYear, viewMonth, 1);
  const startOffset = firstOfMonth.getDay();
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const daysInPrevMonth = new Date(viewYear, viewMonth, 0).getDate();

  const cells: { day: number; y: number; m: number; outside: boolean }[] = [];
  for (let i = 0; i < startOffset; i++) {
    cells.push({
      day: daysInPrevMonth - startOffset + 1 + i,
      y: viewMonth === 0 ? viewYear - 1 : viewYear,
      m: viewMonth === 0 ? 11 : viewMonth - 1,
      outside: true,
    });
  }
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({ day: d, y: viewYear, m: viewMonth, outside: false });
  }
  for (let nextMonthDay = 1; cells.length < 42; nextMonthDay++) {
    cells.push({
      day: nextMonthDay,
      y: viewMonth === 11 ? viewYear + 1 : viewYear,
      m: viewMonth === 11 ? 0 : viewMonth + 1,
      outside: true,
    });
  }

  const currentDayIso = todayIso();

  return (
    <div className={`date-picker ${open ? "open" : ""} ${disabled ? "disabled" : ""}`} ref={rootRef}>
      <div className={`date-picker-trigger ${className ?? ""}`}>
        <input
          type="text"
          inputMode="numeric"
          autoComplete="off"
          className={text ? "date-picker-text-input" : "date-picker-text-input placeholder"}
          value={text}
          onChange={(e) => handleTextChange(e.target.value)}
          placeholder={placeholder}
          aria-label={ariaLabel}
          disabled={disabled}
        />
        <button
          type="button"
          className="date-picker-icon-btn"
          aria-haspopup="dialog"
          aria-expanded={open}
          aria-label="Open calendar"
          disabled={disabled}
          onClick={() => setOpen((o) => !o)}
        >
          <svg
            width="15"
            height="15"
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <rect x="3" y="4" width="14" height="13" rx="2.5" />
            <path d="M3 8h14M7 2.5v3M13 2.5v3" />
          </svg>
        </button>
      </div>

      {open && (
        <div className="date-picker-popup" role="dialog" aria-label="Choose a date">
          <div className="date-picker-header">
            <button type="button" className="date-picker-nav" onClick={prevMonth} aria-label="Previous month">
              ‹
            </button>
            <span className="date-picker-month-label">
              {MONTH_NAMES[viewMonth]} {viewYear}
            </span>
            <button type="button" className="date-picker-nav" onClick={nextMonth} aria-label="Next month">
              ›
            </button>
          </div>
          <div className="date-picker-weekdays">
            {WEEKDAYS.map((w) => (
              <span key={w}>{w}</span>
            ))}
          </div>
          <div className="date-picker-grid">
            {cells.map((c, i) => {
              const iso = toIso(c.y, c.m, c.day);
              const disabled = isDisabled(iso);
              const isSelected = value === iso;
              const isToday = iso === currentDayIso;
              return (
                <button
                  key={i}
                  type="button"
                  className={`date-picker-cell ${c.outside ? "outside" : ""} ${
                    isSelected ? "selected" : ""
                  } ${isToday ? "today" : ""}`}
                  disabled={disabled}
                  onClick={() => {
                    onChange(iso);
                    setOpen(false);
                  }}
                >
                  {c.day}
                </button>
              );
            })}
          </div>
          {value && (
            <button
              type="button"
              className="date-picker-clear"
              onClick={() => {
                onChange("");
                setOpen(false);
              }}
            >
              Clear
            </button>
          )}
        </div>
      )}
    </div>
  );
}
