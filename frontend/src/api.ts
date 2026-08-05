export interface Medication {
  name: string;
  form: string;
  dosage: string;
  frequency: string;
  duration: string;
}

export interface Prescription {
  id?: string;
  doctor_name: string;
  date_of_visit: string | null;
  complaint: string;
  diagnosis: string;
  medications: Medication[];
  child_age: string;
  child_weight: string;
  additional_notes: string;
  source_text?: string;
}

export type ColorKey = "violet" | "mint" | "amber" | "sky";

export interface Fact {
  label: string;
  value: string;
  emphasis: boolean;
}

export interface MedTag {
  name: string;
  color_key: ColorKey;
}

export interface Source {
  id: string;
  kind: "prescription" | "note";
  title: string;
  prescriber: string | null;
  date: string | null;
  page: number | null;
  thumbnail_url: string | null;
}

export interface FollowUp {
  label: string;
  question: string;
}

export interface AnswerPayload {
  text: string;
  med: MedTag | null;
  facts: Fact[] | null;
  safety_note: string | null;
  sources: Source[];
  follow_ups: FollowUp[];
  grounded: boolean;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string; // user question text; unused for assistant messages
  payload?: AnswerPayload; // assistant answer - backend always returns one,
  // even when it's degrading gracefully (no records, LLM unavailable, ...)
  status?: "error"; // set only when the request itself failed (network/5xx) -
  // distinct from a low, degraded AnswerPayload the backend did return
}

export interface Med {
  id: string;
  name: string;
  form: string;
  cadence: string;
  color_key: ColorKey;
  last_seen_at: string;
  active: boolean;
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  created_at: string | null;
  password_changed_at: string | null;
}

export interface JobCreated {
  job_id: string;
  status: string;
}

export type ExtractedDraft = Prescription & { low_confidence?: string[] };

export interface JobOut {
  id: string;
  status: "queued" | "processing" | "done" | "error";
  raw_text: string;
  extracted: ExtractedDraft | null;
  error: string;
}

export const emptyMedication = (): Medication => ({
  name: "",
  form: "",
  dosage: "",
  frequency: "",
  duration: "",
});

export const emptyPrescription = (): Prescription => ({
  doctor_name: "",
  date_of_visit: null,
  complaint: "",
  diagnosis: "",
  medications: [emptyMedication()],
  child_age: "",
  child_weight: "",
  additional_notes: "",
});

const API_BASE = import.meta.env.VITE_API_URL || "";

// Auth uses HttpOnly cookies set by the server, so the browser attaches them
// automatically. Every request must send credentials.
function errorMessage(payload: unknown, fallback: string): string {
  const detail = (payload as { detail?: unknown })?.detail;
  if (Array.isArray(detail)) {
    return detail.map((d: { msg?: string }) => d.msg).join(", ");
  }
  return (detail as string) || fallback;
}

async function tryRefresh(): Promise<boolean> {
  const res = await fetch(`${API_BASE}/api/auth/refresh`, {
    method: "POST",
    credentials: "include",
  });
  return res.ok;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  retry = true
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include",
  });

  if (res.status === 401 && retry && (await tryRefresh())) {
    return request<T>(path, options, false);
  }
  if (res.status === 401) {
    window.dispatchEvent(new Event("auth:logout"));
  }
  if (!res.ok) {
    const payload = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorMessage(payload, "Request failed"));
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// --------------------------- auth ---------------------------
async function publicPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorMessage(payload, "Request failed"));
  }
  return res.json();
}

export const authApi = {
  login: async (email: string, password: string) => {
    await publicPost("/api/auth/login", { email, password });
  },
  register: async (
    email: string,
    password: string,
    display_name: string,
    consent: boolean
  ) => {
    await publicPost("/api/auth/register", {
      email,
      password,
      display_name,
      consent,
    });
  },
  me: () => request<User>("/api/auth/me"),
  logout: async () => {
    await fetch(`${API_BASE}/api/auth/logout`, {
      method: "POST",
      credentials: "include",
    }).catch(() => {});
  },
};

// --------------------------- account ---------------------------
export const accountApi = {
  updateProfile: (display_name: string) =>
    request<User>("/api/account/profile", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name }),
    }),
  changePassword: (current_password: string, new_password: string) =>
    request<{ ok: boolean }>("/api/account/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password, new_password }),
    }),
  // Triggers a real file download rather than returning JSON to the caller -
  // the export is meant to leave the app as a file, not be held in memory.
  exportData: async () => {
    const res = await fetch(`${API_BASE}/api/account/export`, {
      credentials: "include",
    });
    if (!res.ok) throw new Error("Export failed");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "prescription-pal-export.json";
    a.click();
    URL.revokeObjectURL(url);
  },
  deleteAccount: (confirm: string) =>
    request<{ ok: boolean }>("/api/account", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm }),
    }),
};

// --------------------------- prescriptions / chat / ocr ---------------------------
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// fetch() has no upload-progress event, so the initial multipart POST uses
// XHR instead - the polling loop that follows stays on the plain request()
// helper, since progress only matters for the byte-upload phase.
function uploadFileWithProgress(
  file: File,
  onProgress: (pct: number) => void,
  signal?: AbortSignal
): Promise<JobCreated> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/ocr`);
    xhr.withCredentials = true;
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject(new Error("Invalid response from server"));
        }
      } else {
        let message = "Upload failed";
        try {
          message = errorMessage(JSON.parse(xhr.responseText), message);
        } catch {
          // non-JSON error body - keep the generic message
        }
        reject(new Error(message));
      }
    };
    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.onabort = () => reject(new DOMException("Upload cancelled", "AbortError"));
    signal?.addEventListener("abort", () => xhr.abort());
    xhr.send(form);
  });
}

export const prescriptionsApi = {
  list: () => request<Prescription[]>("/api/prescriptions"),
  get: (id: string) => request<Prescription>(`/api/prescriptions/${id}`),
  create: (p: Prescription) =>
    request<Prescription>("/api/prescriptions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(p),
    }),
  update: (id: string, p: Prescription) =>
    request<Prescription>(`/api/prescriptions/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(p),
    }),
  delete: (id: string) =>
    request<{ deleted: boolean }>(`/api/prescriptions/${id}`, {
      method: "DELETE",
    }),
  chat: (question: string) =>
    request<AnswerPayload>("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }),

  // Async OCR: submit the image (with real upload progress), then poll the
  // job until it finishes. onProgress/signal are optional so existing
  // callers that don't need them are unaffected.
  ocrAndWait: async (
    file: File,
    onStatus?: (status: string) => void,
    onProgress?: (pct: number) => void,
    signal?: AbortSignal
  ): Promise<JobOut> => {
    const { job_id } = await uploadFileWithProgress(
      file,
      onProgress ?? (() => {}),
      signal
    );

    for (let i = 0; i < 80; i++) {
      if (signal?.aborted) throw new DOMException("Cancelled", "AbortError");
      await sleep(1500);
      const job = await request<JobOut>(`/api/jobs/${job_id}`, { signal });
      onStatus?.(job.status);
      if (job.status === "done") return job;
      if (job.status === "error") {
        throw new Error(job.error || "Processing failed");
      }
    }
    throw new Error("Timed out waiting for OCR to finish");
  },
};

// --------------------------- medications (derived) ---------------------------
export const medicationsApi = {
  list: () => request<Med[]>("/api/medications"),
};
