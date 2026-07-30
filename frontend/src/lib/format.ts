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

// Max 3 chips, dose -> frequency -> course, from the same fields the Ask
// fact strip uses - never re-parsed from prose.
export function recordFactChips(p: Prescription): string[] {
  const med = primaryMedication(p);
  if (!med) return [];
  return [med.dosage, med.frequency, med.duration && shortenDuration(med.duration)]
    .filter((v): v is string => Boolean(v && v.trim()))
    .slice(0, 3);
}

export function recordTitle(p: Prescription): string {
  const med = primaryMedication(p);
  if (med) return `${med.name} ${med.dosage}`.trim();
  if (p.date_of_visit) return `Prescription · ${formatSourceDate(p.date_of_visit)}`;
  return "Prescription";
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
