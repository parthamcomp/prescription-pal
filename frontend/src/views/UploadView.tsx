import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Child,
  Prescription,
  emptyMedication,
  emptyPrescription,
  prescriptionsApi,
} from "../api";
import { useConfirm } from "../components/ConfirmDialog";
import PrescriptionForm, { validatePrescription } from "../components/PrescriptionForm";

interface UploadViewProps {
  visible: boolean;
  hasRecords: boolean;
  childList: Child[];
  onManageChildren: () => void;
  onSaved: () => void;
}

type Stage = "idle" | "uploading" | "review";

export default function UploadView({
  visible,
  hasRecords,
  childList,
  onManageChildren,
  onSaved,
}: UploadViewProps) {
  const navigate = useNavigate();
  const confirm = useConfirm();
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
  const [sourceJobId, setSourceJobId] = useState<string | null>(null);

  const reset = () => {
    setStage("idle");
    setProgress(0);
    setOcrStatus("");
    setUploadError("");
    setOcrText("");
    setDraft(null);
    setLowConfidence([]);
    setValidationErrors([]);
    setSourceJobId(null);
  };

  const MAX_PAGES = 6;

  const startUpload = async (files: File[]) => {
    const rejectReason = files.some((f) => !f.type.startsWith("image/"))
      ? "That file type isn't supported - use JPG or PNG photos."
      : files.some((f) => f.size > 20 * 1024 * 1024)
      ? "Each file must be under the 20 MB limit."
      : files.length > MAX_PAGES
      ? `Upload at most ${MAX_PAGES} pages at a time.`
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
        files,
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
      if (!p.child_id && childList.length === 1) {
        p.child_id = childList[0].id;
      }
      setDraft(p);
      setLowConfidence(low_confidence ?? []);
      setSource("photo");
      setSourceJobId(job.id);
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

  const onFilesPicked = (files: FileList | File[] | null) => {
    if (!files || files.length === 0) return;
    startUpload(Array.from(files));
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
        startUpload([file]);
      },
      "image/jpeg",
      0.92
    );
  };

  const isMobileDevice =
    typeof navigator !== "undefined" && /Android|iPhone|iPad|iPod|Mobi/i.test(navigator.userAgent);

  const startManual = () => {
    setDraft({
      ...emptyPrescription(),
      child_id: childList.length === 1 ? childList[0].id : null,
    });
    setLowConfidence([]);
    setSource("typed");
    setStage("review");
  };

  const discard = async () => {
    if (ocrText || source === "typed") {
      if (!(await confirm({ message: "Discard this record?", confirmLabel: "Discard", danger: true }))) return;
    }
    reset();
  };

  const save = async (addAnother: boolean) => {
    if (!draft) return;
    const errors = validatePrescription(draft);
    setValidationErrors(errors);
    if (errors.length > 0) return;

    setBusy(true);
    try {
      const wasFirstRecord = !hasRecords;
      const saved = await prescriptionsApi.create({
        ...draft,
        source_job_id: sourceJobId,
      });
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
                onFilesPicked(e.dataTransfer.files);
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
                  <div className="dropzone-title">Drop photo(s) here</div>
                  <div className="dropzone-sub">
                    JPG or PNG · up to 20 MB each · multiple pages of one visit? select them
                    all at once
                  </div>
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
                multiple
                style={{ display: "none" }}
                onChange={(e) => onFilesPicked(e.target.files)}
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

                <PrescriptionForm
                  value={draft}
                  onChange={setDraft}
                  lowConfidence={lowConfidence}
                  childList={childList}
                  onManageChildren={onManageChildren}
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
                <button className="danger-btn" onClick={discard}>
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
