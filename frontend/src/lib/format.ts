import { ColorKey, Med, Prescription, Source } from "../api";

export const MED_COLOR_HEX: Record<ColorKey, string> = {
  violet: "#5B4BE6",
  mint: "#17C39A",
  amber: "#FFB43F",
  sky: "#3FA9F5",
};

// A violet square on a violet pill would be invisible - swap in amber there.
export function medTagSquareColor(colorKey: ColorKey): string {
  return colorKey === "violet" ? MED_COLOR_HEX.amber : MED_COLOR_HEX[colorKey];
}

export function formatSourceDate(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return null;
  const opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short" };
  if (d.getFullYear() !== new Date().getFullYear()) opts.year = "numeric";
  return d.toLocaleDateString("en-GB", opts);
}

// "xx year(s) yy month(s)" as of referenceDate (the prescription's visit
// date, not today) - a record documents how old the child was at the visit,
// not how old they are now.
export function formatChildAge(dateOfBirth: string, referenceDate: string): string | null {
  const dob = new Date(`${dateOfBirth}T00:00:00`);
  const ref = new Date(`${referenceDate}T00:00:00`);
  if (Number.isNaN(dob.getTime()) || Number.isNaN(ref.getTime())) return null;
  if (ref < dob) return null;

  let years = ref.getFullYear() - dob.getFullYear();
  let months = ref.getMonth() - dob.getMonth();
  if (ref.getDate() < dob.getDate()) months -= 1;
  if (months < 0) {
    years -= 1;
    months += 12;
  }

  const parts: string[] = [];
  if (years > 0) parts.push(`${years} ${years === 1 ? "year" : "years"}`);
  if (months > 0) parts.push(`${months} ${months === 1 ? "month" : "months"}`);
  return parts.length > 0 ? parts.join(" ") : "0 months";
}

export function sourceMeta(s: Source): string {
  const parts = [s.prescriber, formatSourceDate(s.date)].filter(Boolean) as string[];
  let meta = parts.join(" · ");
  if (s.page) meta += (meta ? " · " : "") + `page ${s.page}`;
  return meta;
}

// Mirrors backend/app/services/meds.py's duration parsing so Records can
// compute the same "ends in N days" / "finished" status client-side without
// a round trip. Keep these two in sync if the duration vocabulary changes.
const DURATION_RE = /(\d+)\s*(days|day|d\b|weeks|week|wk|months|month|mo\b)/i;
const DURATION_UNIT_DAYS: Record<string, number> = {
  day: 1,
  days: 1,
  d: 1,
  week: 7,
  weeks: 7,
  wk: 7,
  month: 30,
  months: 30,
  mo: 30,
};

export function parseDurationDays(duration: string): number | null {
  if (!duration) return null;
  const m = DURATION_RE.exec(duration);
  if (!m) return null;
  const count = parseInt(m[1], 10);
  const unit = m[2].toLowerCase().replace(/\.$/, "");
  const days = DURATION_UNIT_DAYS[unit];
  return days ? count * days : null;
}

export function shortenDuration(duration: string): string {
  if (!duration) return duration;
  const m = DURATION_RE.exec(duration);
  return m ? m[0].trim() : duration;
}

export interface RecordStatus {
  label: string;
  bg: string;
  fg: string;
}

// The record's "primary" medication - the same one build_document/_build_source
// treat as representative (the first one entered).
export function primaryMedication(p: Prescription) {
  return p.medications.find((m) => m.name.trim()) ?? null;
}

export function recordStatus(p: Prescription): RecordStatus {
  const med = primaryMedication(p);
  const days = med ? parseDurationDays(med.duration) : null;
  if (p.date_of_visit && days !== null) {
    const visit = new Date(`${p.date_of_visit}T00:00:00`);
    const ends = new Date(visit);
    ends.setDate(ends.getDate() + days);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const msPerDay = 86400000;
    const daysLeft = Math.round((ends.getTime() - today.getTime()) / msPerDay);
    if (daysLeft < 0) {
      return { label: "Finished", bg: "var(--surface-alt)", fg: "var(--ink-2)" };
    }
    if (daysLeft <= 7) {
      return {
        label: `Ends ${formatSourceDate(ends.toISOString().slice(0, 10))}`,
        bg: "var(--amber-tint)",
        fg: "var(--amber-text)",
      };
    }
  }
  return { label: "Active", bg: "var(--mint-tint)", fg: "var(--mint-text)" };
}

// A single medication gets its full dose/frequency/course (max 3 chips, the
// same fields the Ask fact strip uses, never re-parsed from prose). Once a
// record has more than one, that level of detail per med won't fit a card -
// one chip per medication (name + shortened course) instead, so a multi-med
// record's card actually reflects everything it contains rather than just
// whichever medication happened to be entered first.
const MAX_MULTI_MED_CHIPS = 4;

export function recordFactChips(p: Prescription): string[] {
  const meds = p.medications.filter((m) => m.name.trim());
  if (meds.length === 0) return [];
  if (meds.length === 1) {
    const med = meds[0];
    return [med.dosage, med.frequency, med.duration && shortenDuration(med.duration)]
      .filter((v): v is string => Boolean(v && v.trim()))
      .slice(0, 3);
  }
  const shown = meds.slice(0, MAX_MULTI_MED_CHIPS).map((m) => {
    const duration = m.duration && shortenDuration(m.duration);
    return duration ? `${m.name.trim()} · ${duration}` : m.name.trim();
  });
  const hidden = meds.length - MAX_MULTI_MED_CHIPS;
  if (hidden > 0) shown.push(`+${hidden} more`);
  return shown;
}

export function recordTitle(p: Prescription): string {
  const meds = p.medications.filter((m) => m.name.trim());
  if (meds.length === 1) return `${meds[0].name} ${meds[0].dosage}`.trim();
  if (meds.length > 1) return meds.map((m) => m.name.trim()).join(", ");
  if (p.date_of_visit) return `Prescription · ${formatSourceDate(p.date_of_visit)}`;
  return "Prescription";
}

export interface RecordCardTitle {
  text: string;
  moreCount: number;
}

// The card's title row, unlike recordTitle() (used for search matching and
// the "Ask about this" seed question, where every medication name should
// still count), is space-constrained - listing every medication name for a
// 7-med record stretched the card and forced a horizontal scrollbar. Cap
// what's shown to 2 names and surface the rest as a "+N more" badge instead.
const MAX_CARD_TITLE_MEDS = 2;

export function recordCardTitle(p: Prescription): RecordCardTitle {
  const meds = p.medications.filter((m) => m.name.trim());
  if (meds.length > 1) {
    const shown = meds.slice(0, MAX_CARD_TITLE_MEDS).map((m) => m.name.trim());
    return { text: shown.join(", "), moreCount: Math.max(0, meds.length - MAX_CARD_TITLE_MEDS) };
  }
  return { text: recordTitle(p), moreCount: 0 };
}

export function recordMeta(p: Prescription): string {
  return [p.doctor_name, formatSourceDate(p.date_of_visit)].filter(Boolean).join(" · ");
}

export function colorKeyForRecord(p: Prescription, meds: Med[]): ColorKey {
  const med = primaryMedication(p);
  if (!med) return "violet";
  const found = meds.find((m) => m.name.toLowerCase() === med.name.toLowerCase());
  return found?.color_key ?? "violet";
}

export function pluralize(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}
