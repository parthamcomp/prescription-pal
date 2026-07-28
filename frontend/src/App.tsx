import { useEffect, useRef, useState } from "react";
import {
  ChatMessage,
  Medication,
  OCRResult,
  Prescription,
  emptyMedication,
  emptyPrescription,
  prescriptionsApi,
} from "./api";

type Tab = "ask" | "records" | "upload";

type DisplayMessage = ChatMessage & { time: string };

function now() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function initials(name: string) {
  const parts = name.replace(/^Dr\.?\s*/i, "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "??";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

interface FormProps {
  value: Prescription;
  onChange: (p: Prescription) => void;
}

function PrescriptionForm({ value, onChange }: FormProps) {
  const set = <K extends keyof Prescription>(key: K, v: Prescription[K]) =>
    onChange({ ...value, [key]: v });

  const setMed = (i: number, key: keyof Medication, v: string) => {
    const medications = value.medications.map((m, idx) =>
      idx === i ? { ...m, [key]: v } : m
    );
    onChange({ ...value, medications });
  };

  const addMed = () =>
    onChange({ ...value, medications: [...value.medications, emptyMedication()] });

  const removeMed = (i: number) =>
    onChange({
      ...value,
      medications: value.medications.filter((_, idx) => idx !== i),
    });

  return (
    <div className="form">
      <div className="grid2">
        <label>
          Doctor name
          <input
            value={value.doctor_name}
            onChange={(e) => set("doctor_name", e.target.value)}
            placeholder="Dr. ..."
          />
        </label>
        <label>
          Date of visit
          <input
            type="date"
            value={value.date_of_visit ?? ""}
            onChange={(e) => set("date_of_visit", e.target.value || null)}
          />
        </label>
      </div>

      <div className="grid2">
        <label>
          Child age
          <input
            value={value.child_age}
            onChange={(e) => set("child_age", e.target.value)}
            placeholder="e.g. 3 years"
          />
        </label>
        <label>
          Child weight
          <input
            value={value.child_weight}
            onChange={(e) => set("child_weight", e.target.value)}
            placeholder="e.g. 14 kg"
          />
        </label>
      </div>

      <label>
        Complaint
        <textarea
          value={value.complaint}
          onChange={(e) => set("complaint", e.target.value)}
          rows={2}
        />
      </label>

      <label>
        Diagnosis
        <textarea
          value={value.diagnosis}
          onChange={(e) => set("diagnosis", e.target.value)}
          rows={2}
        />
      </label>

      <div className="meds">
        <div className="meds-head">
          <span>Medications</span>
          <button type="button" className="btn ghost" onClick={addMed}>
            + Add medication
          </button>
        </div>
        {value.medications.map((m, i) => (
          <div className="med-row" key={i}>
            <input
              value={m.name}
              onChange={(e) => setMed(i, "name", e.target.value)}
              placeholder="Name"
            />
            <input
              value={m.dosage}
              onChange={(e) => setMed(i, "dosage", e.target.value)}
              placeholder="Dosage"
            />
            <input
              value={m.frequency}
              onChange={(e) => setMed(i, "frequency", e.target.value)}
              placeholder="Frequency"
            />
            <input
              value={m.duration}
              onChange={(e) => setMed(i, "duration", e.target.value)}
              placeholder="Duration"
            />
            <button
              type="button"
              className="icon-btn"
              onClick={() => removeMed(i)}
              aria-label="Remove medication"
            >
              ×
            </button>
          </div>
        ))}
      </div>

      <label>
        Additional notes
        <textarea
          value={value.additional_notes}
          onChange={(e) => set("additional_notes", e.target.value)}
          rows={3}
        />
      </label>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState<Tab>("ask");

  // chat state
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // records state
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([]);
  const [recordsError, setRecordsError] = useState("");

  // upload state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [ocrText, setOcrText] = useState("");
  const [draft, setDraft] = useState<Prescription | null>(null);
  const [manualDraft, setManualDraft] = useState<Prescription | null>(null);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [saveMessage, setSaveMessage] = useState("");

  const loadPrescriptions = async () => {
    try {
      setRecordsError("");
      setPrescriptions(await prescriptionsApi.list());
    } catch (e) {
      setRecordsError(e instanceof Error ? e.message : "Failed to load records");
    }
  };

  useEffect(() => {
    loadPrescriptions();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, chatLoading]);

  const askQuestion = async (text?: string) => {
    const q = (text ?? question).trim();
    if (!q || chatLoading) return;
    setMessages((m) => [...m, { role: "user", content: q, time: now() }]);
    setQuestion("");
    setChatLoading(true);
    try {
      const res = await prescriptionsApi.chat(q);
      setMessages((m) => [
        ...m,
        { role: "assistant", content: res.answer, sources: res.sources, time: now() },
      ]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content:
            e instanceof Error ? `Error: ${e.message}` : "Something went wrong.",
          time: now(),
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleFileSelect = (file: File | null) => {
    setUploadError("");
    setDraft(null);
    setOcrText("");
    setUploadFile(file);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(file ? URL.createObjectURL(file) : "");
  };

  const runOcr = async () => {
    if (!uploadFile) return;
    setUploadBusy(true);
    setUploadError("");
    try {
      const result: OCRResult = await prescriptionsApi.ocr(uploadFile);
      setOcrText(result.raw_text);
      const extracted = result.extracted;
      if (!extracted.medications || extracted.medications.length === 0) {
        extracted.medications = [emptyMedication()];
      }
      setDraft(extracted);
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "OCR failed");
    } finally {
      setUploadBusy(false);
    }
  };

  const saveDraft = async (p: Prescription, clear: () => void) => {
    setUploadBusy(true);
    setUploadError("");
    try {
      await prescriptionsApi.create(p);
      setSaveMessage("Saved to knowledge base.");
      clear();
      await loadPrescriptions();
      setTab("records");
      setTimeout(() => setSaveMessage(""), 4000);
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setUploadBusy(false);
    }
  };

  const deletePrescription = async (id?: string) => {
    if (!id) return;
    if (!confirm("Delete this record?")) return;
    try {
      await prescriptionsApi.delete(id);
      await loadPrescriptions();
    } catch (e) {
      setRecordsError(e instanceof Error ? e.message : "Failed to delete");
    }
  };

  const clearUpload = () => {
    handleFileSelect(null);
    setDraft(null);
    setOcrText("");
  };

  const suggestions = [
    "What antibiotics has my child taken?",
    "Summarise the last visit's diagnosis",
    "Which medicines were given for fever?",
    "Who was the doctor for the last visit?",
  ];

  return (
    <div className="app">
      <aside className="rail">
        <div className="brand">
          <span className="mark">Rx</span>
          <div className="brand-text">
            <h1>Prescription Assistant</h1>
            <p>local &amp; private</p>
          </div>
        </div>
        <nav className="nav">
          <button
            className={`nav-tab ${tab === "ask" ? "active" : ""}`}
            data-tab="ask"
            onClick={() => setTab("ask")}
          >
            <span className="nav-dot" />
            Ask
          </button>
          <button
            className={`nav-tab ${tab === "records" ? "active" : ""}`}
            data-tab="records"
            onClick={() => setTab("records")}
          >
            <span className="nav-dot" />
            Records
          </button>
          <button
            className={`nav-tab ${tab === "upload" ? "active" : ""}`}
            data-tab="upload"
            onClick={() => setTab("upload")}
          >
            <span className="nav-dot" />
            Upload
          </button>
        </nav>
        <div className="rail-footer">Runs locally · v1.0</div>
      </aside>

      <main className="main">
        <div className="topline">
          <h2>{tab === "ask" ? "Ask" : tab === "records" ? "Records" : "Upload"}</h2>
          {tab === "records" ? (
            <span className="stamp">{prescriptions.length} saved</span>
          ) : (
            <span className="stamp">local &amp; private</span>
          )}
        </div>

        {saveMessage && <div className="toast">{saveMessage}</div>}

        {tab === "ask" ? (
          <section className="chat">
            <div className="thread-wrap">
              <div className="thread">
                {messages.length === 0 && (
                  <div className="empty-chart">
                    <div className="empty-icon">✦</div>
                    <h3>Nothing charted yet</h3>
                    <p>
                      Ask about your child&apos;s saved prescriptions &mdash;
                      diagnoses, medications, or past visits.
                    </p>
                    <div className="quick-stamps">
                      {suggestions.map((s, i) => (
                        <button
                          type="button"
                          key={i}
                          className="quick-stamp"
                          onClick={() => askQuestion(s)}
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {messages.map((m, i) => (
                  <div key={i} className={`entry ${m.role}`}>
                    <div className="entry-head">
                      <span>{m.role === "user" ? "You" : "Chart entry"}</span>
                      <span>{m.time}</span>
                    </div>
                    <div className="entry-body">
                      {m.content}
                    </div>
                    {m.sources && m.sources.length > 0 && (
                      <div className="entry-sources">
                        {m.sources.map((s, j) => (
                          <span key={j} className="source-tag">
                            {s}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                {chatLoading && (
                  <div className="entry assistant">
                    <div className="entry-head">
                      <span>Chart entry</span>
                      <span>{now()}</span>
                    </div>
                    <div className="entry-body typing">Thinking…</div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>
            </div>
            <div className="composer-bar">
              <div className="composer-row">
                <input
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && askQuestion()}
                  placeholder="Ask about a prescription…"
                />
                <button
                  className="send-btn"
                  onClick={() => askQuestion()}
                  disabled={chatLoading}
                  title="Send"
                  aria-label="Send"
                >
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z" />
                  </svg>
                </button>
              </div>
              <p className="composer-note">
                Runs locally · Not medical advice · Consult a healthcare
                professional
              </p>
            </div>
          </section>
        ) : (
          <div className="page-scroll">
            <div className="page-inner">
              {tab === "records" && (
                <section>
                  <div className="toolbar">
                    <h3>{prescriptions.length} saved entries</h3>
                    <button className="btn ghost" onClick={loadPrescriptions}>
                      Refresh
                    </button>
                  </div>
                  {recordsError && <div className="error">{recordsError}</div>}
                  {prescriptions.length === 0 ? (
                    <div className="empty-chart">
                      <p>No records yet. Use the Upload tab to add one.</p>
                    </div>
                  ) : (
                    <div className="cards">
                      {prescriptions.map((p) => (
                        <article className="chart-card" key={p.id}>
                          <div className="chart-card-head">
                            <div className="who">
                              <div className="who-badge">
                                {initials(p.doctor_name || "Unknown")}
                              </div>
                              <div>
                                <h3>{p.doctor_name || "Unknown doctor"}</h3>
                                <span className="tag-date">
                                  {p.date_of_visit || "No date"}
                                </span>
                              </div>
                            </div>
                            <button
                              className="btn ghost danger"
                              onClick={() => deletePrescription(p.id)}
                            >
                              Delete
                            </button>
                          </div>
                          <div className="chart-card-body">
                            {p.complaint && (
                              <p>
                                <strong>Complaint:</strong> {p.complaint}
                              </p>
                            )}
                            {p.diagnosis && (
                              <p>
                                <strong>Diagnosis:</strong> {p.diagnosis}
                              </p>
                            )}
                            {p.medications.length > 0 && (
                              <table className="mar-table">
                                <thead>
                                  <tr>
                                    <th>Medication</th>
                                    <th>Dose</th>
                                    <th>Frequency</th>
                                    <th>Duration</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {p.medications.map((m, i) => (
                                    <tr key={i}>
                                      <td>{m.name}</td>
                                      <td>{m.dosage}</td>
                                      <td>{m.frequency}</td>
                                      <td>{m.duration}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
                            {(p.child_age || p.child_weight) && (
                              <div className="card-meta">
                                {p.child_age && <span>Age: {p.child_age}</span>}
                                {p.child_weight && <span>Weight: {p.child_weight}</span>}
                              </div>
                            )}
                            {p.additional_notes && (
                              <p className="notes">{p.additional_notes}</p>
                            )}
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </section>
              )}

              {tab === "upload" && (
                <section>
                  <div className="toolbar">
                    <h3>Add a prescription</h3>
                    {!manualDraft && !draft && (
                      <button
                        className="btn ghost"
                        onClick={() => setManualDraft(emptyPrescription())}
                      >
                        Enter manually
                      </button>
                    )}
                  </div>

                  {uploadError && <div className="error">{uploadError}</div>}

                  {manualDraft ? (
                    <div className="form-card">
                      <PrescriptionForm value={manualDraft} onChange={setManualDraft} />
                      <div className="actions">
                        <button
                          className="btn"
                          onClick={() => saveDraft(manualDraft, () => setManualDraft(null))}
                          disabled={uploadBusy}
                        >
                          Save to knowledge base
                        </button>
                        <button className="btn ghost" onClick={() => setManualDraft(null)}>
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="form-card">
                        <div className="uploader">
                          <input
                            type="file"
                            accept="image/*"
                            onChange={(e) =>
                              handleFileSelect(e.target.files?.[0] ?? null)
                            }
                          />
                          {previewUrl && (
                            <img className="preview" src={previewUrl} alt="preview" />
                          )}
                          {uploadFile && !draft && (
                            <button className="btn" onClick={runOcr} disabled={uploadBusy}>
                              {uploadBusy ? "Extracting…" : "Extract with OCR"}
                            </button>
                          )}
                        </div>

                        {ocrText && (
                          <details className="raw">
                            <summary>Raw OCR text</summary>
                            <pre>{ocrText}</pre>
                          </details>
                        )}
                      </div>

                      {draft && (
                        <div className="form-card" style={{ marginTop: 14 }}>
                          <p className="hint">Review and correct before saving:</p>
                          <PrescriptionForm value={draft} onChange={setDraft} />
                          <div className="actions">
                            <button
                              className="btn"
                              onClick={() => saveDraft(draft, clearUpload)}
                              disabled={uploadBusy}
                            >
                              Save to knowledge base
                            </button>
                            <button className="btn ghost" onClick={clearUpload}>
                              Discard
                            </button>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </section>
              )}

              <footer className="footer">
                Runs locally · Not medical advice · Consult a healthcare
                professional
              </footer>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
