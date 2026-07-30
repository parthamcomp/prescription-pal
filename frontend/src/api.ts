export interface Medication {
  name: string;
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

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
}

export interface User {
  id: string;
  email: string;
  display_name: string;
}

export interface JobCreated {
  job_id: string;
  status: string;
}

export interface JobOut {
  id: string;
  status: "queued" | "processing" | "done" | "error";
  raw_text: string;
  extracted: Prescription | null;
  error: string;
}

export const emptyMedication = (): Medication => ({
  name: "",
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
  register: async (email: string, password: string, display_name: string) => {
    await publicPost("/api/auth/register", { email, password, display_name });
  },
  me: () => request<User>("/api/auth/me"),
  logout: async () => {
    await fetch(`${API_BASE}/api/auth/logout`, {
      method: "POST",
      credentials: "include",
    }).catch(() => {});
  },
};

// --------------------------- prescriptions / chat / ocr ---------------------------
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export const prescriptionsApi = {
  list: () => request<Prescription[]>("/api/prescriptions"),
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
    request<{ answer: string; sources: string[] }>("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }),

  // Async OCR: submit the image, then poll the job until it finishes.
  ocrAndWait: async (
    file: File,
    onStatus?: (status: string) => void
  ): Promise<JobOut> => {
    const form = new FormData();
    form.append("file", file);
    const { job_id } = await request<JobCreated>("/api/ocr", {
      method: "POST",
      body: form,
    });

    for (let i = 0; i < 80; i++) {
      await sleep(1500);
      const job = await request<JobOut>(`/api/jobs/${job_id}`);
      onStatus?.(job.status);
      if (job.status === "done") return job;
      if (job.status === "error") {
        throw new Error(job.error || "Processing failed");
      }
    }
    throw new Error("Timed out waiting for OCR to finish");
  },
};
