import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Medication,
  Prescription,
  emptyMedication,
  emptyPrescription,
  prescriptionsApi,
} from "../api";

interface FormProps {
  value: Prescription;
  onChange: (p: Prescription) => void;
  lowConfidence: string[];
}

function fieldFlag(lowConfidence: string[], path: string): boolean {
  return lowConfidence.includes(path);
}

function ReviewForm({ value, onChange, lowConfidence }: FormProps) {
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

  const flagged = (field: string) => (fieldFlag(lowConfidence, field) ? "flagged" : "");

  return (
    <div className="review-fields">
      {value.medications.map((m, i) => (
        <div className="review-med-block" key={i}>
          {value.medications.length > 1 && (
            <div className="review-med-block-head">
              <span>Medication {i + 1}</span>
              <button
                type="button"
                className="ghost danger"
                onClick={() => removeMed(i)}
                aria-label="Remove medication"
              >
                ×
              </button>
            </div>
          )}
          <div className="review-grid">
            <label className={flagged(`medications.${i}.name`)}>
              MEDICATION
              <input
                value={m.name}
                onChange={(e) => setMed(i, "name", e.target.value)}
                placeholder="e.g. Amoxicillin"
              />
              {fieldFlag(lowConfidence, `medications.${i}.name`) && (
                <span className="field-hint">Please check</span>
              )}
            </label>
            <label className={flagged(`medications.${i}.dosage`)}>
              STRENGTH / DOSE
              <input
                value={m.dosage}
                onChange={(e) => setMed(i, "dosage", e.target.value)}
                placeholder="e.g. 250mg"
              />
              {fieldFlag(lowConfidence, `medications.${i}.dosage`) && (
                <span className="field-hint">Please check</span>
              )}
            </label>
            <label className={flagged(`medications.${i}.frequency`)}>
              HOW OFTEN
              <input
                value={m.frequency}
                onChange={(e) => setMed(i, "frequency", e.target.value)}
                placeholder="e.g. 3 times a day"
              />
              {fieldFlag(lowConfidence, `medications.${i}.frequency`) && (
                <span className="field-hint">Please check</span>
              )}
            </label>
            <label className={flagged(`medications.${i}.duration`)}>
              COURSE
              <input
                value={m.duration}
                onChange={(e) => setMed(i, "duration", e.target.value)}
                placeholder="e.g. 7 days"
              />
              {fieldFlag(lowConfidence, `medications.${i}.duration`) && (
                <span className="field-hint">Please check</span>
              )}
            </label>
          </div>
        </div>
      ))}
      <button type="button" className="ghost" onClick={addMed}>
        + Add another medication
      </button>

      <div className="review-grid">
        <label className={flagged("doctor_name")}>
          PRESCRIBER
          <input
            value={value.doctor_name}
            onChange={(e) => set("doctor_name", e.target.value)}
            placeholder="Dr. ..."
          />
          {fieldFlag(lowConfidence, "doctor_name") && (
            <span className="field-hint">Please check</span>
          )}
        </label>
        <label className={flagged("date_of_visit")}>
          DATE ON PRESCRIPTION
          <input
            type="date"
            value={value.date_of_visit ?? ""}
            onChange={(e) => set("date_of_visit", e.target.value || null)}
          />
          {fieldFlag(lowConfidence, "date_of_visit") && (
            <span className="field-hint">Please check</span>
          )}
        </label>
      </div>

      <div className="review-grid">
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

function validate(p: Prescription): string[] {
  const errors: string[] = [];
  if (!p.medications.some((m) => m.name.trim())) {
    errors.push("At least one medication name is required.");
  }
  if (p.date_of_visit) {
    const d = new Date(`${p.date_of_visit}T00:00:00`);
    if (Number.isNaN(d.getTime())) {
      errors.push("Date on prescription isn't a valid date.");
    } else if (d.getTime() > Date.now()) {
      errors.push("Date on prescription can't be in the future.");
    }
  }
  return errors;
}

interface UploadViewProps {
  visible: boolean;
  hasRecords: boolean;
  onSaved: () => void;
}

type Stage = "idle" | "uploading" | "review";

export default function UploadView({ visible, hasRecords, onSaved }: UploadViewProps) {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [dragOver, setDragOver] = useState(false);
  const [stage, setStage] = useState<Stage>("idle");
  const [progress, setProgress] = useState(0);
  const [ocrStatus, setOcrStatus] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [ocrText, setOcrText] = useState("");
  const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraError, setCameraError] = useState("");

  const [draft, setDraft] = useState<Prescription | null>(null);
  const [lowConfidence, setLowConfidence] = useState<string[]>([]);
  const [source, setSource] = useState<"photo" | "typed">("photo");
  const [busy, setBusy] = useState(false);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  const reset = () => {
    setStage("idle");
    setProgress(0);
    setOcrStatus("");
    setUploadError("");
    setOcrText("");
    setDraft(null);
    setLowConfidence([]);
    setValidationErrors([]);
  };

  const startUpload = async (file: File) => {
    const rejectReason =
      !file.type.startsWith("image/")
        ? "That file type isn't supported - use a JPG or PNG photo."
        : file.size > 20 * 1024 * 1024
        ? "That file is over the 20 MB limit."
        : "";
    if (rejectReason) {
      setUploadError(rejectReason);
      return;
    }

    setUploadError("");
    setStage("uploading");
    setProgress(0);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const job = await prescriptionsApi.ocrAndWait(
        file,
        setOcrStatus,
        setProgress,
        controller.signal
      );
      setOcrText(job.raw_text);
      const extracted = job.extracted ?? { ...emptyPrescription(), low_confidence: [] };
      const { low_confidence, ...rest } = extracted;
      const p = rest as Prescription;
      if (!p.medications || p.medications.length === 0) {
        p.medications = [emptyMedication()];
      }
      setDraft(p);
      setLowConfidence(low_confidence ?? []);
      setSource("photo");
      setStage("review");
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") {
        reset();
        return;
      }
      setUploadError(e instanceof Error ? e.message : "OCR failed");
      setStage("idle");
    }
  };

  const cancelUpload = () => {
    abortRef.current?.abort();
  };

  const onFilePicked = (file: File | null) => {
    if (!file) return;
    startUpload(file);
  };

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setCameraOpen(false);
  };

  useEffect(() => () => stopCamera(), []);

  useEffect(() => {
    if (!visible) stopCamera();
  }, [visible]);

  useEffect(() => {
    if (cameraOpen && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
      videoRef.current.play().catch(() => {});
    }
  }, [cameraOpen]);

  const openCamera = async () => {
    setCameraError("");
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError("This browser doesn't support camera capture.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false,
      });
      streamRef.current = stream;
      setCameraOpen(true);
    } catch (e) {
      const name = e instanceof DOMException ? e.name : "";
      setCameraError(
        name === "NotAllowedError"
          ? "Camera permission was denied. Allow camera access in your browser settings to take a photo."
          : name === "NotFoundError"
          ? "No camera was found on this device."
          : "Couldn't access the camera."
      );
    }
  };

  const capturePhoto = () => {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const file = new File([blob], `prescription-${Date.now()}.jpg`, {
          type: "image/jpeg",
        });
        stopCamera();
        startUpload(file);
      },
      "image/jpeg",
      0.92
    );
  };

  const isMobileDevice =
    typeof navigator !== "undefined" && /Android|iPhone|iPad|iPod|Mobi/i.test(navigator.userAgent);

  const startManual = () => {
    setDraft(emptyPrescription());
    setLowConfidence([]);
    setSource("typed");
    setStage("review");
  };

  const discard = () => {
    if (ocrText || source === "typed") {
      if (!confirm("Discard this record?")) return;
    }
    reset();
  };

  const save = async (addAnother: boolean) => {
    if (!draft) return;
    const errors = validate(draft);
    setValidationErrors(errors);
    if (errors.length > 0) return;

    setBusy(true);
    try {
      const wasFirstRecord = !hasRecords;
      const saved = await prescriptionsApi.create(draft);
      onSaved();
      if (addAnother) {
        reset();
        return;
      }
      if (wasFirstRecord) {
        navigate("/ask");
      } else {
        navigate("/records", { state: { highlightId: saved.id } });
      }
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel" style={{ display: visible ? undefined : "none" }}>
      <div className="panel-head">
        <h1>Add a prescription</h1>
        <span className="privacy-pill">
          <span className="dot" />
          Stays on your account
        </span>
      </div>

      <div className="content--page">
        <div className="page upload-page">
          {stage !== "review" && (
            <div
              className={`dropzone ${dragOver ? "drag-over" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                onFilePicked(e.dataTransfer.files?.[0] ?? null);
              }}
            >
              {!cameraOpen && (
                <>
                  <div className="dropzone-tile">
                    <svg width="24" height="24" viewBox="0 0 20 20" fill="none" stroke="#5B4BE6" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M10 13.5V4M6.5 7.5 10 4l3.5 3.5" />
                      <path d="M4 13v2a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-2" />
                    </svg>
                  </div>
                  <div className="dropzone-title">Drop a photo here</div>
                  <div className="dropzone-sub">JPG or PNG · up to 20 MB</div>
                </>
              )}

              {cameraOpen ? (
                <div className="camera-panel">
                  <video ref={videoRef} className="camera-video" playsInline muted autoPlay />
                  <div className="camera-actions">
                    <button onClick={capturePhoto}>Capture</button>
                    <button className="ghost" onClick={stopCamera}>
                      Cancel
                    </button>
                  </div>
                </div>
              ) : stage === "uploading" ? (
                <div className="upload-progress">
                  <div className="progress-track">
                    <div className="progress-fill" style={{ width: `${progress}%` }} />
                  </div>
                  <div className="progress-label">
                    {ocrStatus === "processing"
                      ? "Reading your prescription…"
                      : ocrStatus === "queued"
                      ? "Queued…"
                      : progress < 100
                      ? `Uploading… ${progress}%`
                      : "Reading your prescription…"}
                  </div>
                  <button className="ghost" onClick={cancelUpload}>
                    Cancel
                  </button>
                </div>
              ) : (
                <div className="dropzone-actions">
                  <button onClick={() => fileInputRef.current?.click()}>Choose file</button>
                  <button
                    className="secondary-white"
                    onClick={openCamera}
                    disabled={!isMobileDevice}
                    title={
                      isMobileDevice
                        ? undefined
                        : "Camera capture is only available on mobile devices."
                    }
                  >
                    Take a photo
                  </button>
                </div>
              )}

              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                style={{ display: "none" }}
                onChange={(e) => onFilePicked(e.target.files?.[0] ?? null)}
              />

              {(uploadError || cameraError) && (
                <p className="dropzone-error">{uploadError || cameraError}</p>
              )}
            </div>
          )}

          {stage !== "review" && (
            <div className="or-divider">
              <span>OR TYPE IT IN</span>
            </div>
          )}

          {stage !== "review" && (
            <button className="ghost" onClick={startManual}>
              Enter manually
            </button>
          )}

          {stage === "review" && draft && (
            <>
              <div className="review-card">
                <div className="review-card-head">
                  {source === "photo" ? (
                    <span className="med-tag">
                      <span className="med-tag-square" style={{ background: "#FFB43F" }} />
                      Read from your photo
                    </span>
                  ) : (
                    <span className="med-tag typed">Typed by you</span>
                  )}
                  <span className="review-card-hint">Check each field before saving</span>
                </div>

                <ReviewForm
                  value={draft}
                  onChange={setDraft}
                  lowConfidence={lowConfidence}
                />

                <div className="safety-note">
                  <span className="safety-icon">!</span>
                  <p>
                    We read these fields automatically, so mistakes happen. Anything you
                    correct here is what future answers will use.
                  </p>
                </div>

                {validationErrors.length > 0 && (
                  <div className="review-errors">
                    {validationErrors.map((e, i) => (
                      <p key={i}>{e}</p>
                    ))}
                  </div>
                )}
              </div>

              {ocrText && (
                <details className="raw">
                  <summary>Raw OCR text</summary>
                  <pre>{ocrText}</pre>
                </details>
              )}

              <div className="review-actions">
                <button onClick={() => save(false)} disabled={busy}>
                  Save record
                </button>
                <button className="ghost" onClick={() => save(true)} disabled={busy}>
                  Save &amp; add another
                </button>
                <div className="panel-head-spacer" />
                <button className="text-ghost" onClick={discard}>
                  Discard
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
