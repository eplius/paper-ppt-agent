import type {
  CancelJobResponse,
  GenerateRequestPayload,
  GenerateResponse,
  JobStatus,
  PreviewResponse,
  ProvidersResponse,
  RefineRequestPayload,
  RefineResponse,
  UploadResponse,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function uploadPaper(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return request<UploadResponse>("/api/upload", {
    method: "POST",
    body: formData,
  });
}

export async function fetchProviders(): Promise<ProvidersResponse> {
  return request<ProvidersResponse>("/api/providers");
}

export async function generatePresentation(
  payload: GenerateRequestPayload,
): Promise<GenerateResponse> {
  return request<GenerateResponse>("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchJobStatus(jobId: string): Promise<JobStatus> {
  return request<JobStatus>(`/api/status/${jobId}`);
}

export async function cancelJob(jobId: string): Promise<CancelJobResponse> {
  return request<CancelJobResponse>(`/api/status/${jobId}/cancel`, {
    method: "POST",
  });
}

export async function fetchPreview(jobId: string): Promise<PreviewResponse> {
  return request<PreviewResponse>(`/api/preview/${jobId}`);
}

export async function fetchProjectPreview(projectDir: string): Promise<PreviewResponse> {
  const params = new URLSearchParams({ project_dir: projectDir });
  return request<PreviewResponse>(`/api/preview-project?${params.toString()}`);
}

export async function refinePresentation(
  payload: RefineRequestPayload,
): Promise<RefineResponse> {
  return request<RefineResponse>("/api/refine", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteSession(sessionId: string): Promise<void> {
  await request<void>(`/api/session/${sessionId}`, { method: "DELETE" });
}

export function getDownloadUrl(jobId: string): string {
  return `${API_BASE}/api/download/${jobId}`;
}

export function getDownloadUrlForOutput(outputPath: string): string {
  const params = new URLSearchParams({ output_path: outputPath });
  return `${API_BASE}/api/download-file?${params.toString()}`;
}
