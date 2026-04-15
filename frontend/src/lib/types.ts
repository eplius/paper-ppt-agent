export type SourceType = "pdf" | "latex";

export interface FileInfo {
  name: string;
  size: number;
  source_type: SourceType;
}

export interface UploadResponse {
  session_id: string;
  file_info: FileInfo;
}

export interface ProviderModel {
  id: string;
  display_name: string;
  supports_vision: boolean;
}

export interface ProviderListItem {
  name: string;
  display_name: string;
  models: ProviderModel[];
}

export interface ProvidersResponse {
  providers: ProviderListItem[];
}

export interface GenerationOptions {
  canvas_format: string;
  style: string;
  num_pages?: number;
  language: string;
  detail_level: string;
}

export interface GenerateRequestPayload {
  session_id: string;
  instruction: string;
  model_config: {
    provider: string;
    model: string;
    api_key: string;
    base_url?: string;
  };
  options: GenerationOptions;
}

export interface GenerateResponse {
  job_id: string;
  status: string;
}

export interface JobStatus {
  status: string;
  progress: number;
  message: string;
  slides_completed: number;
  total_slides: number;
  output_path?: string | null;
  error?: string | null;
}

export interface PreviewSlide {
  index: number;
  name: string;
  source: string;
  content: string;
}

export interface PreviewResponse {
  job_id: string;
  project_dir?: string | null;
  slides: PreviewSlide[];
  output_path?: string | null;
  status: string;
}

export interface GenerationHistoryItem {
  jobId: string;
  fileName: string;
  sourceType?: SourceType;
  status: string;
  slideCount: number;
  updatedAt: string;
  projectDir?: string | null;
  outputPath?: string | null;
  provider?: string;
  model?: string;
  baseUrl?: string;
  options?: GenerationOptions;
  parentJobId?: string | null;
}

export interface JobEvent {
  type: "progress" | "slide_ready" | "complete" | "error";
  job_id: string;
  stage: string;
  status: string;
  message: string;
  progress: number;
  slides_completed: number;
  total_slides: number;
  data: Record<string, unknown>;
}

export interface RefineRequestPayload {
  job_id: string;
  feedback: string;
  model_config: {
    provider: string;
    model: string;
    api_key: string;
    base_url?: string;
  };
  options: GenerationOptions;
  target_pages?: number[];
  allow_structure_changes?: boolean;
}

export interface RefineResponse {
  job_id: string;
  status: string;
}
