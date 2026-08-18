import { useEffect, useMemo, useState } from "react";
import { matchPath, useLocation, useNavigate } from "react-router-dom";
import { Child, Med, Prescription, prescriptionsApi } from "../api";
import Logo from "../components/Logo";
import PrescriptionForm, { validatePrescription } from "../components/PrescriptionForm";
import Select from "../components/Select";
import {
  MED_COLOR_HEX,
  colorKeyForRecord,
  pluralize,
  recordFactChips,
  recordMeta,
  recordStatus,
  recordTitle,
} from "../lib/format";

type Filter = "all" | "prescriptions" | "notes" | "ending_soon";
type Sort = "newest" | "oldest";

const SORT_KEY = "pp:records-sort";

function isEndingSoon(p: Prescription): boolean {
  return recordStatus(p).label.startsWith("Ends");
}

function TileGlyph({ p, meds }: { p: Prescription; meds: Med[] }) {
  const colorKey = colorKeyForRecord(p, meds);
  const bg = `${MED_COLOR_HEX[colorKey]}22`;
  return (
    <div className="record-thumb" style={{ background: bg }}>
      <span style={{ color: MED_COLOR_HEX[colorKey] }}>Rx</span>
    </div>
  );
}

interface RecordCardProps {
  p: Prescription;
  meds: Med[];
  onDelete: (id: string) => void;
  highlighted?: boolean;
}

function RecordCard({ p, meds, onDelete, highlighted }: RecordCardProps) {
  const navigate = useNavigate();
  const status = recordStatus(p);
  const chips = recordFactChips(p);
  const colorKey = colorKeyForRecord(p, meds);

  return (
    <article
      className={`record-card ${highlighted ? "highlighted" : ""}`}
      role="link"
      tabIndex={0}
      onClick={() => navigate(`/records/${p.id}`)}
      onKeyDown={(e) => {
        if (e.key === "Enter") navigate(`/records/${p.id}`);
      }}
    >
      <div className="record-card-top">
        <TileGlyph p={p} meds={meds} />
        <div className="record-card-title-block">
          <div className="record-card-title-row">
            <span
              className="med-chip"
              style={{ background: MED_COLOR_HEX[colorKey] }}
            />
            <span className="record-card-title">{recordTitle(p)}</span>
          </div>
          {recordMeta(p) && <div className="record-card-meta">{recordMeta(p)}</div>}
          {chips.length > 0 && (
            <div className="record-fact-chips">
              {chips.map((c, i) => (
                <span key={i} className="record-fact-chip">
                  {c}
                </span>
              ))}
            </div>
          )}
        </div>
        <span
          className="record-status-badge"
          style={{ background: status.bg, color: status.fg }}
        >
          {status.label}
        </span>
      </div>
      <div className="record-card-footer">
        <span className="record-card-filename">
          {p.doctor_name || "Manually entered"}
        </span>
        <button
          type="button"
          className="record-ask-link"
          onClick={(e) => {
            e.stopPropagation();
            navigate("/ask", { state: { seedQuestion: `Tell me about ${recordTitle(p)}` } });
          }}
        >
          Ask about this →
        </button>
      </div>
      <button
        type="button"
        className="record-card-delete"
        aria-label="Delete record"
        onClick={(e) => {
          e.stopPropagation();
          onDelete(p.id!);
        }}
      >
        Delete
      </button>
    </article>
  );
}

function RecordDetail({
  record,
  childList,
  onDelete,
  onUpdated,
  onManageChildren,
}: {
  record: Prescription;
  childList: Child[];
  onDelete: (id: string) => void;
  onUpdated: () => void;
  onManageChildren: () => void;
}) {
  const navigate = useNavigate();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Prescription>(record);
  const [errors, setErrors] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [photos, setPhotos] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    setPhotos([]);
    if (record.id) {
      prescriptionsApi
        .photos(record.id)
        .then((urls) => {
          if (!cancelled) setPhotos(urls);
        })
        .catch(() => {
          // no original photo(s) for this record (manually typed, or
          // uploaded before this feature existed) - just show nothing
        });
    }
    return () => {
      cancelled = true;
    };
  }, [record.id]);

  const startEdit = () => {
    setDraft(record);
    setErrors([]);
    setSaveError("");
    setEditing(true);
  };

  const save = async () => {
    const validationErrors = validatePrescription(draft);
    setErrors(validationErrors);
    if (validationErrors.length > 0) return;
    setBusy(true);
    setSaveError("");
    try {
      await prescriptionsApi.update(record.id!, draft);
      onUpdated();
      setEditing(false);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Failed to save changes");
    } finally {
      setBusy(false);
    }
  };

  const childName = childList.find((c) => c.id === record.child_id)?.name;

  return (
    <div className="content--page">
      <div className="page">
        <button
          className="ghost-btn"
          onClick={() => (editing ? setEditing(false) : navigate("/records"))}
        >
          ← {editing ? "Cancel edit" : "Back to records"}
        </button>
        <div className="record-detail-card">
          {editing ? (
            <>
              <h2>Edit record</h2>
              <PrescriptionForm
                value={draft}
                onChange={setDraft}
                lowConfidence={[]}
                childList={childList}
                onManageChildren={onManageChildren}
              />
              {errors.length > 0 && (
                <div className="review-errors">
                  {errors.map((e, i) => (
                    <p key={i}>{e}</p>
                  ))}
                </div>
              )}
              {saveError && <p className="field-hint error-text">{saveError}</p>}
              <div className="actions form-actions">
                <button onClick={save} disabled={busy}>
                  Save changes
                </button>
                <button className="ghost" onClick={() => setEditing(false)} disabled={busy}>
                  Cancel
                </button>
              </div>
            </>
          ) : (
            <>
              <h2>{record.doctor_name || "Prescription"}</h2>
              {photos.length > 0 && (
                <div className="record-photo-strip">
                  {photos.map((url, i) => (
                    <a
                      key={i}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      title={photos.length > 1 ? `Page ${i + 1} - open full size` : "Open full size"}
                    >
                      <img src={url} alt={`Prescription page ${i + 1}`} />
                    </a>
                  ))}
                </div>
              )}
              {record.date_of_visit && (
                <p>
                  <strong>Date:</strong> {record.date_of_visit}
                </p>
              )}
              {childName && (
                <p>
                  <strong>Child:</strong> {childName}
                </p>
              )}
              {record.complaint && (
                <p>
                  <strong>Complaint:</strong> {record.complaint}
                </p>
              )}
              {record.diagnosis && (
                <p>
                  <strong>Diagnosis:</strong> {record.diagnosis}
                </p>
              )}
              {record.medications.length > 0 && (
                <ul className="med-list">
                  {record.medications.map((m, i) => (
                    <li key={i}>
                      <strong>{m.name}</strong>
                      {[m.form, m.dosage, m.frequency, m.duration]
                        .filter(Boolean)
                        .join(" · ")}
                    </li>
                  ))}
                </ul>
              )}
              {(record.child_age || record.child_weight) && (
                <div className="card-meta">
                  {record.child_age && <span>Age: {record.child_age}</span>}
                  {record.child_weight && <span>Weight: {record.child_weight}</span>}
                </div>
              )}
              {record.additional_notes && <p className="notes">{record.additional_notes}</p>}
              <div className="actions form-actions">
                <button
                  onClick={() =>
                    navigate("/ask", {
                      state: { seedQuestion: `Tell me about ${recordTitle(record)}` },
                    })
                  }
                >
                  Ask about this
                </button>
                <button className="ghost" onClick={startEdit}>
                  Edit
                </button>
                <button className="ghost danger" onClick={() => onDelete(record.id!)}>
                  Delete
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

interface RecordsViewProps {
  visible: boolean;
  prescriptions: Prescription[];
  meds: Med[];
  childList: Child[];
  loading: boolean;
  error: string;
  onDelete: (id: string) => void;
  onUpdated: () => void;
  onManageChildren: () => void;
}

export default function RecordsView({
  visible,
  prescriptions,
  meds,
  childList,
  loading,
  error,
  onDelete,
  onUpdated,
  onManageChildren,
}: RecordsViewProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [childFilter, setChildFilter] = useState<string>("all");
  const [sort, setSort] = useState<Sort>(
    () => (localStorage.getItem(SORT_KEY) as Sort) || "newest"
  );

  useEffect(() => {
    localStorage.setItem(SORT_KEY, sort);
  }, [sort]);

  const [highlightId, setHighlightId] = useState<string | null>(null);
  useEffect(() => {
    const id = (location.state as { highlightId?: string } | null)?.highlightId;
    if (id) {
      setHighlightId(id);
      navigate(location.pathname, { replace: true, state: null });
      const t = setTimeout(() => setHighlightId(null), 1200);
      return () => clearTimeout(t);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state]);

  const detailMatch = matchPath("/records/:id", location.pathname);
  const detailRecord = detailMatch
    ? prescriptions.find((p) => p.id === detailMatch.params.id)
    : null;

  const counts = useMemo(
    () => ({
      all: prescriptions.length,
      prescriptions: prescriptions.length,
      notes: 0, // this app never produces visit-note records - always 0
      ending_soon: prescriptions.filter(isEndingSoon).length,
    }),
    [prescriptions]
  );

  const filtered = useMemo(() => {
    let list = prescriptions;
    if (filter === "ending_soon") list = list.filter(isEndingSoon);
    // "prescriptions" filter is a no-op today (every record is a
    // prescription; "notes" always has 0 and is hidden) but kept so the
    // pill row matches the design once note-type records exist.
    if (childFilter !== "all") {
      list = list.filter((p) => (p.child_id ?? "") === childFilter);
    }

    const q = search.trim().toLowerCase();
    if (q) {
      list = list.filter((p) => {
        const medNames = p.medications.map((m) => m.name.toLowerCase()).join(" ");
        return (
          medNames.includes(q) ||
          p.doctor_name.toLowerCase().includes(q) ||
          recordTitle(p).toLowerCase().includes(q)
        );
      });
    }

    return [...list].sort((a, b) => {
      const da = a.date_of_visit || "";
      const db = b.date_of_visit || "";
      return sort === "newest" ? db.localeCompare(da) : da.localeCompare(db);
    });
  }, [prescriptions, filter, childFilter, search, sort]);

  const medCount = meds.length;

  const pills: { key: Filter; label: string; count: number }[] = [
    { key: "all", label: "All", count: counts.all },
    { key: "prescriptions", label: "Prescriptions", count: counts.prescriptions },
    { key: "notes", label: "Visit notes", count: counts.notes },
    { key: "ending_soon", label: "Ending soon", count: counts.ending_soon },
  ];

  return (
    <div className="panel" style={{ display: visible ? undefined : "none" }}>
      {detailRecord ? (
        <>
          <div className="panel-head">
            <h2>Records</h2>
          </div>
          <RecordDetail
            record={detailRecord}
            childList={childList}
            onDelete={onDelete}
            onUpdated={onUpdated}
            onManageChildren={onManageChildren}
          />
        </>
      ) : (
        <>
          <div className="panel-head">
            <h1>Records</h1>
            <span className="records-summary">
              {pluralize(prescriptions.length, "stored")}
              {medCount > 0 ? ` · ${pluralize(medCount, "medication")}` : ""}
            </span>
            <div className="panel-head-spacer" />
            <div className="records-search">
              <svg width="14" height="14" viewBox="0 0 20 20" fill="none" stroke="#6B6989" strokeWidth="1.8">
                <circle cx="9" cy="9" r="6" />
                <path d="M17 17l-4-4" strokeLinecap="round" />
              </svg>
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search"
                aria-label="Search records"
              />
            </div>
            <button className="ghost-btn newchat" onClick={() => navigate("/upload")}>
              + Add record
            </button>
          </div>

          <div className="filter-row">
            {pills
              .filter((p) => p.key === "all" || p.count > 0)
              .map((p) => (
                <button
                  key={p.key}
                  type="button"
                  className={`filter-pill ${filter === p.key ? "active" : ""}`}
                  onClick={() => setFilter(p.key)}
                >
                  {p.label} {p.count}
                </button>
              ))}
            <div className="panel-head-spacer" />
            {childList.length > 0 && (
              <Select
                className="sort-btn"
                value={childFilter}
                onChange={setChildFilter}
                options={[
                  { value: "all", label: "All children" },
                  ...childList.map((c) => ({ value: c.id, label: c.name })),
                ]}
                ariaLabel="Filter by child"
              />
            )}
            <button
              type="button"
              className="sort-btn"
              onClick={() => setSort((s) => (s === "newest" ? "oldest" : "newest"))}
            >
              {sort === "newest" ? "Newest first ↓" : "Oldest first ↑"}
            </button>
          </div>

          <div className="content--page">
            <div className="page records-page">
              {error && <div className="error">{error}</div>}

              {loading ? (
                <div className="cards-grid">
                  {[0, 1, 2, 3].map((i) => (
                    <div key={i} className="record-card-skeleton">
                      <div className="skeleton-bar" style={{ width: "60%" }} />
                      <div className="skeleton-bar short" />
                    </div>
                  ))}
                </div>
              ) : prescriptions.length === 0 ? (
                <div className="empty">
                  <Logo size={48} className="empty-mark" />
                  <h3>No records yet</h3>
                  <p>Add a prescription photo and I can answer questions about it.</p>
                  <button className="no-records-cta" onClick={() => navigate("/upload")}>
                    Upload a prescription
                  </button>
                </div>
              ) : filtered.length === 0 ? (
                <div className="empty">
                  <h3>Nothing matches &quot;{search}&quot;</h3>
                  <button
                    className="ghost-btn newchat"
                    onClick={() => {
                      setSearch("");
                      setFilter("all");
                    }}
                  >
                    Clear filters
                  </button>
                </div>
              ) : (
                <div className="cards-grid">
                  {filtered.map((p) => (
                    <RecordCard
                      key={p.id}
                      p={p}
                      meds={meds}
                      onDelete={onDelete}
                      highlighted={p.id === highlightId}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
