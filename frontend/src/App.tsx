import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  ChatMessage,
  Medication,
  Prescription,
  emptyMedication,
  emptyPrescription,
  prescriptionsApi,
} from "./api";
import { useAuth } from "./auth/AuthContext";

type Tab = "ask" | "records" | "upload";

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
          <button type="button" className="ghost" onClick={addMed}>
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
              className="ghost danger"
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
  const { user, logout } = useAuth();
  const [tab, setTab] = useState<Tab>("ask");

  // chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
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
  const [ocrStatus, setOcrStatus] = useState("");
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

  const askQuestion = async () => {
    const q = question.trim();
    if (!q || chatLoading) return;
    setMessages((m) => [...m, { role: "user", content: q }]);
    setQuestion("");
    setChatLoading(true);
    try {
      const res = await prescriptionsApi.chat(q);
      setMessages((m) => [
        ...m,
        { role: "assistant", content: res.answer, sources: res.sources },
      ]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content:
            e instanceof Error ? `Error: ${e.message}` : "Something went wrong.",
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
    setOcrStatus("queued");
    try {
      const job = await prescriptionsApi.ocrAndWait(uploadFile, setOcrStatus);
      setOcrText(job.raw_text);
      const extracted = (job.extracted ?? emptyPrescription()) as Prescription;
      if (!extracted.medications || extracted.medications.length === 0) {
        extracted.medications = [emptyMedication()];
      }
      setDraft(extracted);
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "OCR failed");
    } finally {
      setUploadBusy(false);
      setOcrStatus("");
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
      <aside className="sidebar">
        <div className="brand">
          <div className="logo">Rx</div>
          <div>
            <h1>Prescription Assistant</h1>
            <p>Your knowledge base</p>
          </div>
        </div>

        <div>
          <div className="section-label">Sections</div>
          <div className="nav">
            <button
              className={`nav-card ${tab === "ask" ? "active" : ""}`}
              onClick={() => setTab("ask")}
            >
              <div className="name">
                <span className="nav-dot" />
                Ask
              </div>
              <div className="desc">Chat with your saved prescriptions</div>
            </button>
            <button
              className={`nav-card ${tab === "records" ? "active" : ""}`}
              onClick={() => setTab("records")}
            >
              <div className="name">
                <span className="nav-dot" />
                Records
              </div>
              <div className="desc">Browse and manage saved records</div>
            </button>
            <button
              className={`nav-card ${tab === "upload" ? "active" : ""}`}
              onClick={() => setTab("upload")}
            >
              <div className="name">
                <span className="nav-dot" />
                Upload
              </div>
              <div className="desc">Add a prescription by photo or form</div>
            </button>
          </div>
        </div>

        <div className="account">
          <Link to="/profile" className="account-info" title="View profile">
            <span className="account-avatar">
              {(user?.display_name || user?.email || "?")
                .charAt(0)
                .toUpperCase()}
            </span>
            <span className="account-name">
              {user?.display_name || user?.email}
            </span>
          </Link>
          <button className="ghost" onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>

      <main className="main">
        <header className="main-header">
          <h2>
            {tab === "ask" ? "Ask" : tab === "records" ? "Records" : "Upload"}
          </h2>
          {tab === "records" ? (
            <span className="badge">{prescriptions.length} saved</span>
          ) : (
            <span className="badge">Private to your account</span>
          )}
        </header>

        {saveMessage && <div className="toast">{saveMessage}</div>}

        {tab === "ask" ? (
          <section className="chat">
            <div className="messages">
              <div className="thread">
                {messages.length === 0 && (
                  <div className="empty">
                    <h3>How can I help?</h3>
                    <p>
                      Ask about your child&apos;s saved prescriptions &mdash;
                      diagnoses, medications, or past visits.
                    </p>
                    <div className="suggestions">
                      {suggestions.map((s, i) => (
                        <button
                          type="button"
                          key={i}
                          className="suggestion"
                          onClick={() => setQuestion(s)}
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {messages.map((m, i) => (
                  <div key={i} className={`msg ${m.role}`}>
                    <div className={`avatar ${m.role}`}>
                      {m.role === "user" ? "You" : "Rx"}
                    </div>
                    <div className="bubble">
                      {m.content}
                      {m.sources && m.sources.length > 0 && (
                        <div className="sources">
                          {m.sources.map((s, j) => (
                            <span key={j} className="chip">
                              {s}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {chatLoading && (
                  <div className="msg assistant">
                    <div className="avatar assistant">Rx</div>
                    <div className="bubble typing">Thinking…</div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>
            </div>
            <div className="composer-wrap">
              <div className="composer">
                <input
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && askQuestion()}
                  placeholder="Ask about a prescription…"
                />
                <button
                  className="send-btn"
                  onClick={askQuestion}
                  disabled={chatLoading}
                  title="Send"
                  aria-label="Send"
                >
                  <svg
                    width="18"
                    height="18"
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
            </div>
          </section>
        ) : (
          <div className="content--page">
            <div className="page">
            {tab === "records" && (
              <section className="panel">
            <div className="panel-head">
              <h2>Saved Prescriptions</h2>
              <button className="ghost" onClick={loadPrescriptions}>
                Refresh
              </button>
            </div>
            {recordsError && <div className="error">{recordsError}</div>}
            {prescriptions.length === 0 ? (
              <div className="empty">
                <p>No records yet. Use the Upload tab to add one.</p>
              </div>
            ) : (
              <div className="cards">
                {prescriptions.map((p) => (
                  <article className="card" key={p.id}>
                    <div className="card-head">
                      <div>
                        <h3>{p.doctor_name || "Unknown doctor"}</h3>
                        <span className="date">
                          {p.date_of_visit || "No date"}
                        </span>
                      </div>
                      <button
                        className="ghost danger"
                        onClick={() => deletePrescription(p.id)}
                      >
                        Delete
                      </button>
                    </div>
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
                      <ul className="med-list">
                        {p.medications.map((m, i) => (
                          <li key={i}>
                            <strong>{m.name}</strong>
                            {[m.dosage, m.frequency, m.duration]
                              .filter(Boolean)
                              .join(" · ")}
                          </li>
                        ))}
                      </ul>
                    )}
                    <div className="card-meta">
                      {p.child_age && <span>Age: {p.child_age}</span>}
                      {p.child_weight && <span>Weight: {p.child_weight}</span>}
                    </div>
                    {p.additional_notes && (
                      <p className="notes">{p.additional_notes}</p>
                    )}
                  </article>
                ))}
              </div>
            )}
          </section>
        )}

        {tab === "upload" && (
          <section className="panel">
            <div className="panel-head">
              <h2>Add a Prescription</h2>
              {!manualDraft && !draft && (
                <button
                  className="ghost"
                  onClick={() => setManualDraft(emptyPrescription())}
                >
                  Enter manually
                </button>
              )}
            </div>

            {uploadError && <div className="error">{uploadError}</div>}

            {manualDraft ? (
              <>
                <PrescriptionForm value={manualDraft} onChange={setManualDraft} />
                <div className="actions">
                  <button
                    onClick={() => saveDraft(manualDraft, () => setManualDraft(null))}
                    disabled={uploadBusy}
                  >
                    Save to knowledge base
                  </button>
                  <button className="ghost" onClick={() => setManualDraft(null)}>
                    Cancel
                  </button>
                </div>
              </>
            ) : (
              <>
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
                    <button onClick={runOcr} disabled={uploadBusy}>
                      {uploadBusy
                        ? ocrStatus === "processing"
                          ? "Processing…"
                          : ocrStatus === "queued"
                          ? "Queued…"
                          : "Extracting…"
                        : "Extract with OCR"}
                    </button>
                  )}
                </div>

                {ocrText && (
                  <details className="raw">
                    <summary>Raw OCR text</summary>
                    <pre>{ocrText}</pre>
                  </details>
                )}

                {draft && (
                  <>
                    <p className="hint">Review and correct before saving:</p>
                    <PrescriptionForm value={draft} onChange={setDraft} />
                    <div className="actions">
                      <button
                        onClick={() => saveDraft(draft, clearUpload)}
                        disabled={uploadBusy}
                      >
                        Save to knowledge base
                      </button>
                      <button className="ghost" onClick={clearUpload}>
                        Discard
                      </button>
                    </div>
                  </>
                )}
              </>
            )}
          </section>
            )}

            </div>
          </div>
        )}
      </main>
    </div>
  );
}
