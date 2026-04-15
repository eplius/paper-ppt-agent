import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { fetchJobStatus, fetchPreview, fetchProjectPreview, fetchProviders, generatePresentation, refinePresentation, uploadPaper } from "../lib/api";
import type {
  GenerateRequestPayload,
  GenerationOptions,
  GenerationHistoryItem,
  JobEvent,
  JobStatus,
  PreviewResponse,
  PreviewSlide,
  ProviderListItem,
  RefineRequestPayload,
  UploadResponse,
} from "../lib/types";
import { openJobSocket } from "../lib/ws";

type ConnectionStatus = "disconnected" | "connecting" | "connected";
const FINAL_JOB_STATUSES = new Set(["complete", "error"]);
const HISTORY_LIMIT = 8;

interface RunConfigSnapshot {
  provider: string;
  model: string;
  baseUrl?: string;
  options: GenerationOptions;
  parentJobId?: string | null;
}

interface GenerationState {
  uploadSession?: UploadResponse;
  providers: ProviderListItem[];
  jobId?: string;
  job?: JobStatus;
  slides: PreviewSlide[];
  logs: string[];
  selectedSlide?: PreviewSlide;
  connectionStatus: ConnectionStatus;
  error?: string;
  result?: PreviewResponse;
  history: GenerationHistoryItem[];
  activeJobId?: string;
  currentRunConfig?: RunConfigSnapshot;
  socket?: WebSocket;
  loadProviders: () => Promise<void>;
  uploadFile: (file: File) => Promise<void>;
  startGeneration: (payload: GenerateRequestPayload) => Promise<string>;
  startRefine: (payload: RefineRequestPayload) => Promise<string>;
  connect: (jobId: string) => void;
  hydrateResult: (jobId: string) => Promise<void>;
  resumeCurrentRun: () => Promise<boolean>;
  selectSlide: (slide?: PreviewSlide) => void;
  syncHistory: () => void;
  removeHistory: (jobId: string) => void;
  reset: () => void;
}

function appendSlide(slides: PreviewSlide[], slide: PreviewSlide): PreviewSlide[] {
  const remaining = slides.filter((item) => item.index !== slide.index);
  return [...remaining, slide].sort((left, right) => left.index - right.index);
}

function formatLog(event: JobEvent): string {
  return `[${event.stage}] ${event.message}`;
}

function shouldReplaceSlides(current: PreviewSlide[], incoming: PreviewSlide[]): boolean {
  if (incoming.length > current.length) {
    return true;
  }
  if (incoming.length === 0 || current.length === 0) {
    return incoming.length > 0;
  }
  return incoming.some((slide, index) => current[index]?.content !== slide.content);
}

function upsertHistoryItem(history: GenerationHistoryItem[], item: GenerationHistoryItem): GenerationHistoryItem[] {
  return [item, ...history.filter((entry) => entry.jobId !== item.jobId)]
    .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt))
    .slice(0, HISTORY_LIMIT);
}

function buildHistoryItem(state: Pick<GenerationState, "history" | "jobId" | "uploadSession" | "job" | "slides" | "result" | "currentRunConfig">) {
  if (!state.jobId) {
    return undefined;
  }

  const existing = state.history.find((entry) => entry.jobId === state.jobId);
  const slideCount = Math.max(
    state.slides.length,
    state.result?.slides.length ?? 0,
    state.job?.slides_completed ?? 0,
    existing?.slideCount ?? 0,
  );

  return {
    jobId: state.jobId,
    fileName: state.uploadSession?.file_info.name ?? existing?.fileName ?? state.jobId,
    sourceType: state.uploadSession?.file_info.source_type ?? existing?.sourceType,
    status: state.result?.status ?? state.job?.status ?? existing?.status ?? "pending",
    slideCount,
    updatedAt: new Date().toISOString(),
    projectDir:
      state.result?.project_dir ??
      existing?.projectDir ??
      deriveProjectDirFromOutputPath(state.job?.output_path ?? state.result?.output_path ?? existing?.outputPath),
    outputPath: state.job?.output_path ?? state.result?.output_path ?? existing?.outputPath ?? null,
    provider: state.currentRunConfig?.provider ?? existing?.provider,
    model: state.currentRunConfig?.model ?? existing?.model,
    baseUrl: state.currentRunConfig?.baseUrl ?? existing?.baseUrl,
    options: state.currentRunConfig?.options ?? existing?.options,
    parentJobId: state.currentRunConfig?.parentJobId ?? existing?.parentJobId ?? null,
  } satisfies GenerationHistoryItem;
}

function pickSelectedSlide(slides: PreviewSlide[], selectedSlide?: PreviewSlide) {
  if (!slides.length) {
    return undefined;
  }
  if (!selectedSlide) {
    return slides[0];
  }
  return slides.find((slide) => slide.index === selectedSlide.index) ?? slides[0];
}

function deriveProjectDirFromOutputPath(outputPath?: string | null): string | null {
  if (!outputPath) {
    return null;
  }
  const normalized = outputPath.replace(/\\/g, "/");
  const exportsMarker = "/exports/";
  const idx = normalized.lastIndexOf(exportsMarker);
  if (idx === -1) {
    return null;
  }
  return outputPath.slice(0, idx);
}

function buildStoredJob(historyItem: GenerationHistoryItem, result?: PreviewResponse): JobStatus {
  const slideCount = result?.slides.length ?? historyItem.slideCount;
  return {
    status: historyItem.status,
    progress: historyItem.status === "complete" ? 1 : 0,
    message: "",
    slides_completed: slideCount,
    total_slides: slideCount,
    output_path: historyItem.outputPath ?? result?.output_path ?? null,
    error: historyItem.status === "error" ? "Job not found." : null,
  };
}

export const useGeneration = create<GenerationState>()(
  persist(
    (set, get) => ({
      providers: [],
      slides: [],
      logs: [],
      connectionStatus: "disconnected",
      history: [],
      async loadProviders() {
        const response = await fetchProviders();
        set({ providers: response.providers });
      },
      async uploadFile(file) {
        const uploadSession = await uploadPaper(file);
        set({ uploadSession, error: undefined });
      },
      async startGeneration(payload) {
        const response = await generatePresentation(payload);
        set({
          jobId: response.job_id,
          activeJobId: response.job_id,
          job: {
            status: response.status,
            progress: 0,
            message: "Generation started",
            slides_completed: 0,
            total_slides: 0,
          },
          slides: [],
          logs: ["[generate] Generation started"],
          error: undefined,
          result: undefined,
          selectedSlide: undefined,
          currentRunConfig: {
            provider: payload.model_config.provider,
            model: payload.model_config.model,
            baseUrl: payload.model_config.base_url,
            options: payload.options,
            parentJobId: null,
          },
        });
        sessionStorage.setItem(`paper-ppt-live-job:${response.job_id}`, "1");
        get().syncHistory();
        return response.job_id;
      },
      async startRefine(payload) {
        const response = await refinePresentation(payload);
        set({
          jobId: response.job_id,
          activeJobId: response.job_id,
          job: {
            status: response.status,
            progress: 0,
            message: "Refinement started",
            slides_completed: 0,
            total_slides: 0,
          },
          slides: [],
          logs: ["[refine] Refinement started"],
          error: undefined,
          result: undefined,
          selectedSlide: undefined,
          currentRunConfig: {
            provider: payload.model_config.provider,
            model: payload.model_config.model,
            baseUrl: payload.model_config.base_url,
            options: payload.options,
            parentJobId: payload.job_id,
          },
        });
        sessionStorage.setItem(`paper-ppt-live-job:${response.job_id}`, "1");
        get().syncHistory();
        return response.job_id;
      },
      connect(jobId) {
        get().socket?.close();
        set({ connectionStatus: "connecting", jobId, activeJobId: jobId });

        const socket = openJobSocket(
          jobId,
          (event) => {
            set((state) => {
              const logLine = formatLog(event);
              const logs =
                event.message && state.logs[state.logs.length - 1] !== logLine
                  ? [...state.logs, logLine]
                  : state.logs;

              const nextJob: JobStatus = {
                status: event.type === "complete" ? "complete" : event.type === "error" ? "error" : event.stage,
                progress: event.progress,
                message: event.message,
                slides_completed: event.slides_completed,
                total_slides: event.total_slides,
                output_path:
                  typeof event.data.output_path === "string" ? event.data.output_path : state.job?.output_path,
                error: event.type === "error" ? event.message : undefined,
              };

              let slides = state.slides;
              if (event.type === "slide_ready" && typeof event.data.svg === "string") {
                slides = appendSlide(state.slides, {
                  index: Number(event.data.page ?? state.slides.length + 1),
                  name: `slide_${event.data.page ?? state.slides.length + 1}`,
                  source: "output",
                  content: String(event.data.svg),
                });
              }

              return {
                jobId,
                activeJobId: FINAL_JOB_STATUSES.has(nextJob.status) ? undefined : jobId,
                job: nextJob,
                slides,
                selectedSlide: pickSelectedSlide(slides, state.selectedSlide),
                logs,
                error: event.type === "error" ? event.message : undefined,
              };
            });
            get().syncHistory();

            if (event.stage === "generation") {
              void fetchPreview(jobId)
                .then((preview) => {
                  set((state) => {
                    if (!shouldReplaceSlides(state.slides, preview.slides)) {
                      return {};
                    }
                    return {
                      result: preview,
                      slides: preview.slides,
                      selectedSlide: pickSelectedSlide(preview.slides, state.selectedSlide),
                    };
                  });
                  get().syncHistory();
                })
                .catch(() => undefined);
            }

            if (event.type === "complete") {
              void get().hydrateResult(jobId);
            }
          },
          () => set({ connectionStatus: "connected" }),
          () => set({ connectionStatus: "disconnected", socket: undefined }),
        );

        set({ socket });
      },
      async hydrateResult(jobId) {
        const historyEntry = get().history.find((entry) => entry.jobId === jobId);
        const projectDir =
          historyEntry?.projectDir ?? deriveProjectDirFromOutputPath(historyEntry?.outputPath);

        const [result, job] = await Promise.all([
          fetchPreview(jobId).catch(async () => {
            if (!projectDir) {
              throw new Error("Result not found.");
            }
            return fetchProjectPreview(projectDir);
          }),
          fetchJobStatus(jobId).catch(() => {
            if (!historyEntry) {
              throw new Error("Job not found.");
            }
            return buildStoredJob(historyEntry);
          }),
        ]);
        set((state) => ({
          jobId,
          activeJobId: FINAL_JOB_STATUSES.has(job.status) ? undefined : jobId,
          result,
          job,
          slides: result.slides,
          selectedSlide: pickSelectedSlide(result.slides, state.selectedSlide),
          error: job.error ?? undefined,
        }));
        get().syncHistory();
      },
      async resumeCurrentRun() {
        const currentJobId = get().activeJobId ?? get().jobId;
        if (!currentJobId) {
          return false;
        }

        const currentJob = get().job;
        if (get().socket || (currentJob && FINAL_JOB_STATUSES.has(currentJob.status))) {
          return true;
        }

        try {
          const [job, preview] = await Promise.all([fetchJobStatus(currentJobId), fetchPreview(currentJobId).catch(() => undefined)]);

          set((state) => ({
            jobId: currentJobId,
            activeJobId: FINAL_JOB_STATUSES.has(job.status) ? undefined : currentJobId,
            job,
            result: preview ?? state.result,
            slides: preview?.slides ?? state.slides,
            selectedSlide: pickSelectedSlide(preview?.slides ?? state.slides, state.selectedSlide),
          error: job.error ?? undefined,
        }));
          get().syncHistory();

          if (job.status === "complete") {
            await get().hydrateResult(currentJobId);
            return true;
          }

          if (job.status === "error") {
            return true;
          }

          get().connect(currentJobId);
          return true;
        } catch (error) {
          set({
            connectionStatus: "disconnected",
            error: error instanceof Error ? error.message : "Failed to resume generation",
          });
          return false;
        }
      },
      selectSlide(slide) {
        set({ selectedSlide: slide });
      },
      syncHistory() {
        const nextItem = buildHistoryItem(get());
        if (!nextItem) {
          return;
        }
        set((state) => ({
          history: upsertHistoryItem(state.history, nextItem),
          activeJobId: FINAL_JOB_STATUSES.has(nextItem.status) ? undefined : nextItem.jobId,
        }));
      },
      removeHistory(jobId) {
        set((state) => ({
          history: state.history.filter((entry) => entry.jobId !== jobId),
        }));
        sessionStorage.removeItem(`paper-ppt-live-job:${jobId}`);
      },
      reset() {
        get().socket?.close();
        set({
          uploadSession: undefined,
          jobId: undefined,
          job: undefined,
          slides: [],
          logs: [],
          selectedSlide: undefined,
          connectionStatus: "disconnected",
          error: undefined,
          result: undefined,
          activeJobId: undefined,
          currentRunConfig: undefined,
          socket: undefined,
        });
      },
    }),
    {
      name: "paper-ppt-agent-generation-v1",
      storage: createJSONStorage(() => window.localStorage),
      partialize: (state) => ({
        uploadSession: state.uploadSession,
        jobId: state.jobId,
        job: state.job,
        slides: state.slides,
        logs: state.logs,
        selectedSlide: state.selectedSlide,
        connectionStatus: "disconnected",
        error: state.error,
        result: state.result,
        history: state.history,
        activeJobId: state.activeJobId,
        currentRunConfig: state.currentRunConfig,
      }),
    },
  ),
);
