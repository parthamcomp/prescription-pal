import { useEffect, useMemo, useRef, useState } from "react";
import { matchPath, useLocation, useNavigate } from "react-router-dom";
import {
  Child,
  Measurement,
  MilestoneStatus,
  PercentileCurvePoint,
  PercentileCurves,
  ScheduleStatus,
  measurementsApi,
  vaccinationsApi,
} from "../api";
import { childAvatarColor, formatChildAgeShort, formatSourceDate, todayIso } from "../lib/format";

const LAST_CHILD_KEY = "pp:last-child-id";

type ProfileTab = "percentiles" | "vaccination";

function childInitial(name: string): string {
  return (name.trim().charAt(0) || "?").toUpperCase();
}

function sexLabel(sex: Child["sex"]): string | null {
  if (sex === "male") return "Boy";
  if (sex === "female") return "Girl";
  return null;
}

// -------------------------------------------------------------------------
// Child selector (avatar + name + age pill, opens a dropdown) - Select.tsx
// is text-only, so this is a small bespoke sibling using the same
// open/close/click-outside/keyboard shape.
// -------------------------------------------------------------------------
function ChildPicker({
  childList,
  selectedId,
  onSelect,
  onManageChildren,
}: {
  childList: Child[];
  selectedId: string;
  onSelect: (id: string) => void;
  onManageChildren: () => void;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const selectedIndex = childList.findIndex((c) => c.id === selectedId);
  const selected = childList[selectedIndex];

  useEffect(() => {
    if (!open) return;
    const onClickOutside = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  if (!selected) return null;
  const age = selected.date_of_birth ? formatChildAgeShort(selected.date_of_birth) : null;
  const sex = sexLabel(selected.sex);

  return (
    <div className="child-picker" ref={rootRef}>
      <button
        type="button"
        className="child-picker-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="child-avatar" style={{ background: childAvatarColor(selectedIndex) }}>
          {childInitial(selected.name)}
        </span>
        <span className="child-picker-text">
          <span className="child-picker-name">{selected.name}</span>
          <span className="child-picker-meta">
            {[age, sex].filter(Boolean).join(" · ") || "Age not set"}
          </span>
        </span>
        <svg
          width="13"
          height="13"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="child-picker-chevron"
        >
          <path d="M4 6l4 4 4-4" />
        </svg>
      </button>
      {open && (
        <ul className="child-picker-list" role="listbox">
          {childList.map((c, i) => {
            const rowAge = c.date_of_birth ? formatChildAgeShort(c.date_of_birth) : null;
            return (
              <li
                key={c.id}
                role="option"
                aria-selected={c.id === selectedId}
                className={`child-picker-option ${c.id === selectedId ? "selected" : ""}`}
                onClick={() => {
                  onSelect(c.id);
                  setOpen(false);
                }}
              >
                <span className="child-avatar small" style={{ background: childAvatarColor(i) }}>
                  {childInitial(c.name)}
                </span>
                <span className="child-picker-option-name">{c.name}</span>
                {rowAge && <span className="child-picker-option-age">{rowAge}</span>}
              </li>
            );
          })}
          <li
            className="child-picker-option add"
            onClick={() => {
              setOpen(false);
              onManageChildren();
            }}
          >
            <span className="child-avatar small dashed">+</span>
            <span className="child-picker-option-name">Add child</span>
          </li>
        </ul>
      )}
    </div>
  );
}

// -------------------------------------------------------------------------
// Percentiles tab
// -------------------------------------------------------------------------
const CHART_COLORS = {
  height: { line: "#5B4BE6", band3: "rgba(91,75,230,0.09)", band15: "rgba(91,75,230,0.15)", median: "#C9C3F7", pillBg: "var(--violet-tint)", pillFg: "#4536C9" },
  weight: { line: "#17C39A", band3: "rgba(23,195,154,0.09)", band15: "rgba(23,195,154,0.15)", median: "#9FE2CC", pillBg: "var(--mint-tint)", pillFg: "var(--mint-text)" },
};

function GrowthChart({
  measure,
  curve,
  points,
}: {
  measure: "height" | "weight";
  curve: PercentileCurvePoint[] | null;
  points: { ageMonths: number; value: number }[];
}) {
  const colors = CHART_COLORS[measure];
  const W = 380;
  const H = 200;
  const left = 20;
  const right = 360;
  const top = 18;
  const bottom = 175;

  if (!curve || curve.length === 0) {
    return (
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="170" className="growth-chart">
        <line x1={left} y1={bottom} x2={right} y2={bottom} stroke="var(--hairline)" strokeWidth="1.5" />
        <text x={left} y={196} fontSize="9.5" fontWeight="700" fill="#9A98B5">Birth</text>
        <text x={right - 12} y={196} fontSize="9.5" fontWeight="700" fill="#9A98B5">5y</text>
      </svg>
    );
  }

  const x = (month: number) => left + (month / 60) * (right - left);

  const allYValues = [
    ...curve.map((c) => c.p3),
    ...curve.map((c) => c.p97),
    ...points.map((p) => p.value),
  ];
  const yMin = Math.min(...allYValues) * 0.96;
  const yMax = Math.max(...allYValues) * 1.04;
  const y = (v: number) => bottom - ((v - yMin) / (yMax - yMin)) * (bottom - top);

  const areaPath = (lo: keyof PercentileCurvePoint, hi: keyof PercentileCurvePoint) => {
    const top_ = curve.map((c) => `${x(c.month)},${y(c[hi] as number)}`).join(" L");
    const bottom_ = [...curve]
      .reverse()
      .map((c) => `${x(c.month)},${y(c[lo] as number)}`)
      .join(" L");
    return `M${top_} L${bottom_} Z`;
  };
  const linePath = (key: keyof PercentileCurvePoint) =>
    "M" + curve.map((c) => `${x(c.month)},${y(c[key] as number)}`).join(" L");

  const sortedPoints = [...points].sort((a, b) => a.ageMonths - b.ageMonths);
  const childLine =
    sortedPoints.length >= 2
      ? "M" + sortedPoints.map((p) => `${x(p.ageMonths)},${y(p.value)}`).join(" L")
      : null;
  const lastPoint = sortedPoints[sortedPoints.length - 1];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="170" className="growth-chart">
      <path d={areaPath("p3", "p97")} fill={colors.band3} />
      <path d={areaPath("p15", "p85")} fill={colors.band15} />
      <path d={linePath("p50")} fill="none" stroke={colors.median} strokeWidth="1.5" strokeDasharray="3 4" />
      {childLine && (
        <path d={childLine} fill="none" stroke={colors.line} strokeWidth="2.75" strokeLinecap="round" strokeLinejoin="round" />
      )}
      {sortedPoints.slice(0, -1).map((p, i) => (
        <circle key={i} cx={x(p.ageMonths)} cy={y(p.value)} r="3.5" fill="#FFFFFF" stroke={colors.line} strokeWidth="2" />
      ))}
      {lastPoint && (
        <circle cx={x(lastPoint.ageMonths)} cy={y(lastPoint.value)} r="6" fill={colors.line} stroke="#FFFFFF" strokeWidth="2.5" />
      )}
      <text x={left} y={196} fontSize="9.5" fontWeight="700" fill="#9A98B5">Birth</text>
      <text x={right - 12} y={196} fontSize="9.5" fontWeight="700" fill="#9A98B5">5y</text>
    </svg>
  );
}

function GrowthCard({
  title,
  measure,
  unit,
  child,
  curve,
  measurements,
  onManageChildren,
}: {
  title: string;
  measure: "height" | "weight";
  unit: string;
  child: Child;
  curve: PercentileCurvePoint[] | null;
  measurements: Measurement[];
  onManageChildren: () => void;
}) {
  const colors = CHART_COLORS[measure];
  const valueKey = measure === "height" ? "height_cm" : "weight_kg";
  const pctKey = measure === "height" ? "height_percentile" : "weight_percentile";
  const withValue = measurements.filter((m) => m[valueKey] != null);
  const points = withValue
    .filter((m) => m.age_months != null)
    .map((m) => ({ ageMonths: m.age_months as number, value: m[valueKey] as number }));
  const latest = withValue[0]; // measurements are sorted newest-first
  const previous = withValue[1];

  const outOfRange =
    latest?.age_months != null && (latest.age_months < 0 || latest.age_months > 60);

  return (
    <div className="growth-card">
      <div className="growth-card-head">
        <span className="growth-card-dot" style={{ background: colors.line }} />
        <span className="growth-card-title">{title}</span>
        <span className="growth-card-sub">
          WHO standards{child.sex ? ` · ${child.sex === "male" ? "boys" : "girls"}` : ""}
        </span>
      </div>

      <GrowthChart measure={measure} curve={curve} points={points} />

      <div className="growth-legend">
        <span className="growth-legend-item">
          <span className="growth-legend-swatch" style={{ background: colors.line, opacity: 0.2 }} />
          3rd&ndash;97th
        </span>
        <span className="growth-legend-item">
          <span className="growth-legend-swatch" style={{ background: colors.line, opacity: 0.35 }} />
          15th&ndash;85th
        </span>
        <span className="growth-legend-item">
          <span className="growth-legend-swatch" style={{ background: colors.median }} />
          median
        </span>
      </div>

      {latest ? (
        <>
          <div className="growth-value-row">
            <span className="growth-value">
              {latest[valueKey]} {unit}
            </span>
            {latest[pctKey] != null ? (
              <span
                className="growth-percentile-pill"
                style={{ background: colors.pillBg, color: colors.pillFg }}
              >
                {Math.round(latest[pctKey] as number)}th percentile
              </span>
            ) : !child.sex ? (
              <span className="growth-percentile-pill muted">Set sex to see percentile</span>
            ) : outOfRange ? (
              <span className="growth-percentile-pill muted">Outside 0&ndash;5y range</span>
            ) : null}
          </div>
          <div className="growth-meta">
            {latest.age_months != null && `Age ${formatChildAgeShort(child.date_of_birth!, latest.measured_on)} · `}
            measured {formatSourceDate(latest.measured_on)}
          </div>
          {previous && previous[valueKey] != null && (
            <div
              className={`growth-delta ${
                (latest[valueKey] as number) - (previous[valueKey] as number) >= 0 ? "up" : "down"
              }`}
            >
              {(latest[valueKey] as number) - (previous[valueKey] as number) >= 0 ? "▲" : "▼"}{" "}
              {Math.abs((latest[valueKey] as number) - (previous[valueKey] as number)).toFixed(1)} {unit} since{" "}
              {formatSourceDate(previous.measured_on)}
            </div>
          )}
          {latest[pctKey] != null && ((latest[pctKey] as number) < 3 || (latest[pctKey] as number) > 97) && (
            <div className="growth-caution">
              Outside the typical range &mdash; worth mentioning at the next visit.
            </div>
          )}
        </>
      ) : !child.sex ? (
        <div className="growth-empty">
          Set {child.name}&apos;s sex to see WHO percentile bands here.{" "}
          <button type="button" className="growth-empty-link" onClick={onManageChildren}>
            Set now
          </button>
        </div>
      ) : (
        <div className="growth-empty">No measurements yet</div>
      )}
    </div>
  );
}

function AddMeasurementModal({
  childId,
  onClose,
  onSaved,
}: {
  childId: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [measuredOn, setMeasuredOn] = useState(todayIso());
  const [heightValue, setHeightValue] = useState("");
  const [weightValue, setWeightValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const save = async () => {
    if (!heightValue && !weightValue) {
      setError("Enter a height or a weight");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await measurementsApi.create({
        child_id: childId,
        measured_on: measuredOn,
        height_value: heightValue ? Number(heightValue) : null,
        height_unit: "cm",
        weight_value: weightValue ? Number(weightValue) : null,
        weight_unit: "kg",
      });
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save measurement");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>Add measurement</h3>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        <div className="modal-body">
          <div className="form" style={{ gap: 14 }}>
            <label>
              Date
              <input type="date" value={measuredOn} onChange={(e) => setMeasuredOn(e.target.value)} />
            </label>
            <div className="grid2">
              <label>
                Height (cm)
                <input
                  type="number"
                  value={heightValue}
                  onChange={(e) => setHeightValue(e.target.value)}
                  placeholder="e.g. 104.2"
                />
              </label>
              <label>
                Weight (kg)
                <input
                  type="number"
                  value={weightValue}
                  onChange={(e) => setWeightValue(e.target.value)}
                  placeholder="e.g. 16.8"
                />
              </label>
            </div>
            {error && <p className="field-hint error-text">{error}</p>}
            <div className="actions form-actions">
              <button onClick={save} disabled={busy}>
                Save measurement
              </button>
              <button className="ghost" onClick={onClose} disabled={busy}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function PercentilesTab({
  child,
  onManageChildren,
}: {
  child: Child;
  onManageChildren: () => void;
}) {
  const [measurements, setMeasurements] = useState<Measurement[]>([]);
  const [curves, setCurves] = useState<PercentileCurves | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [addOpen, setAddOpen] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [m, c] = await Promise.all([
        measurementsApi.list(child.id),
        child.sex ? measurementsApi.percentileCurves(child.sex) : Promise.resolve(null),
      ]);
      setMeasurements(m);
      setCurves(c);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load growth data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [child.id, child.sex]);

  return (
    <>
      <div className="filter-row">
        <div className="panel-head-spacer" />
        <button className="add-measurement-btn" onClick={() => setAddOpen(true)}>
          + Add measurement
        </button>
      </div>

      <div className="content--page">
        <div className="page child-profile-page">
          {error && <div className="error">{error}</div>}
          {!loading && (
            <div className="growth-cards-grid">
              <GrowthCard
                title="Height-for-age"
                measure="height"
                unit="cm"
                child={child}
                curve={curves?.height_for_age ?? null}
                measurements={measurements}
                onManageChildren={onManageChildren}
              />
              <GrowthCard
                title="Weight-for-age"
                measure="weight"
                unit="kg"
                child={child}
                curve={curves?.weight_for_age ?? null}
                measurements={measurements}
                onManageChildren={onManageChildren}
              />
            </div>
          )}

          <div className="growth-table-card">
            <div className="growth-table-title">Recent measurements</div>
            {measurements.length === 0 ? (
              <div className="growth-empty centered">
                No measurements yet &mdash; add the first one above.
              </div>
            ) : (
              <>
                <div className="growth-table-row growth-table-head">
                  <span>DATE</span>
                  <span>AGE</span>
                  <span>HEIGHT</span>
                  <span>HT %ILE</span>
                  <span>WEIGHT</span>
                  <span>WT %ILE</span>
                </div>
                {measurements.map((m, i) => (
                  <div
                    key={m.id}
                    className={`growth-table-row ${i === 0 ? "latest" : ""}`}
                  >
                    <span>{formatSourceDate(m.measured_on)}</span>
                    <span className="muted">
                      {child.date_of_birth ? formatChildAgeShort(child.date_of_birth, m.measured_on) : "—"}
                    </span>
                    <span>{m.height_cm != null ? `${m.height_cm} cm` : "—"}</span>
                    <span className="violet">{m.height_percentile != null ? `${Math.round(m.height_percentile)}th` : "—"}</span>
                    <span>{m.weight_kg != null ? `${m.weight_kg} kg` : "—"}</span>
                    <span className="mint">{m.weight_percentile != null ? `${Math.round(m.weight_percentile)}th` : "—"}</span>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      </div>

      {addOpen && (
        <AddMeasurementModal childId={child.id} onClose={() => setAddOpen(false)} onSaved={load} />
      )}
    </>
  );
}

// -------------------------------------------------------------------------
// Vaccination tab
// -------------------------------------------------------------------------
function isValidDoseDate(value: string, dob: string | null): boolean {
  if (!value) return false;
  const d = new Date(`${value}T00:00:00`);
  if (Number.isNaN(d.getTime())) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  if (d > today) return false;
  if (dob) {
    const dobDate = new Date(`${dob}T00:00:00`);
    if (d < dobDate) return false;
  }
  return true;
}

function computeDefaultExpanded(milestones: MilestoneStatus[]): Set<string> {
  const expanded = new Set<string>();
  const firstNotGiven = milestones.findIndex((m) => m.status !== "given");
  if (firstNotGiven === -1) {
    if (milestones.length > 0) expanded.add(milestones[milestones.length - 1].key);
    return expanded;
  }
  milestones.forEach((m, i) => {
    if (m.status === "due") expanded.add(m.key);
    if (i === firstNotGiven) expanded.add(m.key);
  });
  if (firstNotGiven > 0 && milestones[firstNotGiven - 1].status === "given") {
    expanded.add(milestones[firstNotGiven - 1].key);
  }
  return expanded;
}

function VaccineRow({
  vaccine,
  dob,
  dateDraft,
  onDraftChange,
  onCheck,
  onUncheck,
}: {
  vaccine: { slug: string; name: string; subtitle: string; given: boolean; date_administered: string | null };
  dob: string | null;
  dateDraft: string;
  onDraftChange: (v: string) => void;
  onCheck: () => void;
  onUncheck: () => void;
}) {
  const value = vaccine.given ? vaccine.date_administered ?? "" : dateDraft;
  const valid = isValidDoseDate(value, dob);
  const state = vaccine.given ? "given" : valid ? "ready" : "pending";

  return (
    <div className={`vaccine-row ${state}`}>
      <div className="vaccine-row-main">
        <button
          type="button"
          className="vaccine-checkbox"
          role="checkbox"
          aria-checked={vaccine.given}
          aria-label={`Mark ${vaccine.name} as given`}
          disabled={!valid && !vaccine.given}
          onClick={() => (vaccine.given ? onUncheck() : onCheck())}
        >
          {vaccine.given && (
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 8.5l3 3 7-7" />
            </svg>
          )}
        </button>
        <div className="vaccine-row-text">
          <div className="vaccine-row-name">{vaccine.name}</div>
          <div className="vaccine-row-subtitle">{vaccine.subtitle}</div>
        </div>
      </div>
      <input
        type="date"
        className="vaccine-date-input"
        value={value}
        max={todayIso()}
        onChange={(e) => onDraftChange(e.target.value)}
        disabled={vaccine.given}
      />
    </div>
  );
}

function VaccinationTab({ child }: { child: Child }) {
  const [status, setStatus] = useState<ScheduleStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const initializedExpand = useRef(false);

  // `silent` skips the loading-gate toggle - used when refetching after a
  // check/uncheck, where `status` is already populated and re-hiding the
  // whole list behind the loading gate just to redraw it a moment later
  // produced a visible flash. Only the very first load (or a hard error
  // recovery) should show that gate.
  const load = async (silent = false) => {
    if (!silent) setLoading(true);
    setError("");
    try {
      const s = await vaccinationsApi.scheduleStatus(child.id);
      setStatus(s);
      if (!initializedExpand.current) {
        setExpanded(computeDefaultExpanded(s.milestones));
        initializedExpand.current = true;
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load vaccination schedule");
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    initializedExpand.current = false;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [child.id]);

  const toggleExpand = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const check = async (slug: string) => {
    const dateValue = drafts[slug];
    if (!isValidDoseDate(dateValue, child.date_of_birth)) return;
    try {
      await vaccinationsApi.upsertDose(child.id, slug, dateValue);
      await load(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save dose");
    }
  };

  const uncheck = async (slug: string, keepDate: string | null) => {
    try {
      await vaccinationsApi.deleteDose(child.id, slug);
      if (keepDate) setDrafts((d) => ({ ...d, [slug]: keepDate }));
      await load(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update dose");
    }
  };

  return (
    <>
      <div className="filter-row">
        {status && (
          <div className="vaccine-progress-pill">
            <span className="vaccine-progress-track">
              <span
                className="vaccine-progress-fill"
                style={{
                  width: `${status.total_count > 0 ? (status.given_count / status.total_count) * 100 : 0}%`,
                }}
              />
            </span>
            <span>
              {status.given_count} of {status.total_count} given
            </span>
          </div>
        )}
        <div className="panel-head-spacer" />
      </div>

      <div className="content--page">
        <div className="page child-profile-page">
          {error && <div className="error">{error}</div>}

          <div className="vaccine-info-banner">
            <span className="vaccine-info-icon">i</span>
            <p>A checkbox unlocks once you enter the date that dose was actually given.</p>
          </div>

          {!loading &&
            status?.milestones.map((m) => (
              <div key={m.key} className="vaccine-milestone">
                <button
                  type="button"
                  className={`vaccine-group-head ${m.status}`}
                  onClick={() => toggleExpand(m.key)}
                >
                  <span className="vaccine-milestone-pill">{m.label}</span>
                  <span className="vaccine-milestone-summary">{m.summary}</span>
                  {m.overdue && <span className="vaccine-overdue-tag">Overdue</span>}
                  <span className={`vaccine-count-pill ${m.status}`}>
                    {m.given_count}/{m.total_count} given
                  </span>
                  <svg
                    width="13"
                    height="13"
                    viewBox="0 0 16 16"
                    fill="none"
                    stroke="#6B6989"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    style={{ transform: expanded.has(m.key) ? "rotate(180deg)" : undefined }}
                  >
                    <path d="M4 6l4 4 4-4" />
                  </svg>
                </button>
                {expanded.has(m.key) &&
                  m.vaccines.map((v) => (
                    <VaccineRow
                      key={v.slug}
                      vaccine={v}
                      dob={child.date_of_birth}
                      dateDraft={drafts[v.slug] ?? ""}
                      onDraftChange={(val) => setDrafts((d) => ({ ...d, [v.slug]: val }))}
                      onCheck={() => check(v.slug)}
                      onUncheck={() => uncheck(v.slug, v.date_administered)}
                    />
                  ))}
              </div>
            ))}
        </div>
      </div>
    </>
  );
}

// -------------------------------------------------------------------------
// Main view
// -------------------------------------------------------------------------
interface ChildProfileViewProps {
  visible: boolean;
  childList: Child[];
  onManageChildren: () => void;
}

export default function ChildProfileView({
  visible,
  childList,
  onManageChildren,
}: ChildProfileViewProps) {
  const location = useLocation();
  const navigate = useNavigate();

  const percM = matchPath("/child/:childId/percentiles", location.pathname);
  const vaccM = matchPath("/child/:childId/vaccination", location.pathname);
  const childId = percM?.params.childId ?? vaccM?.params.childId ?? null;
  const tab: ProfileTab = vaccM ? "vaccination" : "percentiles";

  useEffect(() => {
    if (!visible || childList.length === 0) return;
    const validId = childId && childList.some((c) => c.id === childId);
    if (validId) {
      localStorage.setItem(LAST_CHILD_KEY, childId as string);
      return;
    }
    const last = localStorage.getItem(LAST_CHILD_KEY);
    const target = childList.find((c) => c.id === last)?.id ?? childList[0].id;
    navigate(`/child/${target}/percentiles`, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, childId, childList]);

  const child = useMemo(() => childList.find((c) => c.id === childId) ?? null, [childList, childId]);

  return (
    <div className="panel" style={{ display: visible ? undefined : "none" }}>
      {childList.length === 0 ? (
        <>
          <div className="panel-head">
            <h1>Child</h1>
          </div>
          <div className="content--page">
            <div className="page">
              <div className="empty">
                <h3>No children yet</h3>
                <p>Add a child to track growth percentiles and vaccinations.</p>
                <button className="no-records-cta" onClick={onManageChildren}>
                  Add a child
                </button>
              </div>
            </div>
          </div>
        </>
      ) : !child ? null : (
        <>
          <div className="panel-head">
            <ChildPicker
              childList={childList}
              selectedId={child.id}
              onSelect={(id) => navigate(`/child/${id}/${tab}`)}
              onManageChildren={onManageChildren}
            />
            <div className="panel-head-spacer" />
            <div className="tab-capsule">
              <button
                type="button"
                className={`tab-capsule-btn ${tab === "percentiles" ? "active" : ""}`}
                onClick={() => navigate(`/child/${child.id}/percentiles`)}
              >
                Percentiles
              </button>
              <button
                type="button"
                className={`tab-capsule-btn ${tab === "vaccination" ? "active" : ""}`}
                onClick={() => navigate(`/child/${child.id}/vaccination`)}
              >
                Vaccination
              </button>
            </div>
          </div>

          {tab === "percentiles" ? (
            <PercentilesTab key={child.id} child={child} onManageChildren={onManageChildren} />
          ) : (
            <VaccinationTab key={child.id} child={child} />
          )}
        </>
      )}
    </div>
  );
}
