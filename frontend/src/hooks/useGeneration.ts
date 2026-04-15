import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { cancelJob, fetchJobStatus, fetchPreview, fetchProjectPreview, fetchProviders, generatePresentation, refinePresentation, uploadPaper } from "../lib/api";
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
const FINAL_JOB_STATUSES = new Set(["complete", "error", "cancelled"]);
const HISTORY_LIMIT = 8;
const LEGACY_GENERATION_STORAGE_KEY = "paper-ppt-agent-generation-v1";
const GENERATION_STORAGE_KEY = "paper-ppt-agent-generation-v2";

interface RunConfigSnapshot {
  provider: string;
  model: string;
  baseUrl?: string;
  options: GenerationOptions;
  parentJobId?: string | null;
}

interface RunSnapshot {
  jobId: string;
  uploadSession?: UploadResponse;
  job?: JobStatus;
  slides: PreviewSlide[];
  logs: string[];
  selectedSlide?: PreviewSlide;
  error?: string;
  result?: PreviewResponse;
  currentRunConfig?: RunConfigSnapshot;
  connectionStatus: ConnectionStatus;
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
  runs: Record<string, RunSnapshot>;
  activeJobId?: string;
  currentRunConfig?: RunConfigSnapshot;
  socketsByJob: Record<string, WebSocket>;
  loadProviders: () => Promise<void>;
  uploadFile: (file: File) => Promise<void>;
  startGeneration: (payload: GenerateRequestPayload) => Promise<string>;
  startRefine: (payload: RefineRequestPayload) => Promise<string>;
  connect: (jobId: string) => void;
  hydrateResult: (jobId: string) => Promise<void>;
  resumeCurrentRun: (targetJobId?: string) => Promise<boolean>;
  selectSlide: (slide?: PreviewSlide) => void;
  syncHistory: (jobId?: string) => void;
  removeHistory: (jobId: string) => Promise<void>;
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

function buildHistoryItemFromRun(history: GenerationHistoryItem[], run?: RunSnapshot) {
  if (!run) {
    return undefined;
  }

  const existing = history.find((entry) => entry.jobId === run.jobId);
  const slideCount = Math.max(
    run.slides.length,
    run.result?.slides.length ?? 0,
    run.job?.slides_completed ?? 0,
    existing?.slideCount ?? 0,
  );

  return {
    jobId: run.jobId,
    fileName: run.uploadSession?.file_info.name ?? existing?.fileName ?? run.jobId,
    sourceType: run.uploadSession?.file_info.source_type ?? existing?.sourceType,
    status: run.result?.status ?? run.job?.status ?? existing?.status ?? "pending",
    slideCount,
    updatedAt: new Date().toISOString(),
    projectDir:
      run.result?.project_dir ??
      existing?.projectDir ??
      deriveProjectDirFromOutputPath(run.job?.output_path ?? run.result?.output_path ?? existing?.outputPath),
    outputPath: run.job?.output_path ?? run.result?.output_path ?? existing?.outputPath ?? null,
    provider: run.currentRunConfig?.provider ?? existing?.provider,
    model: run.currentRunConfig?.model ?? existing?.model,
    baseUrl: run.currentRunConfig?.baseUrl ?? existing?.baseUrl,
    options: run.currentRunConfig?.options ?? existing?.options,
    parentJobId: run.currentRunConfig?.parentJobId ?? existing?.parentJobId ?? null,
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

function createRunSnapshot(
  jobId: string,
  params?: Partial<Omit<RunSnapshot, "jobId" | "slides" | "logs" | "connectionStatus">> & {
    slides?: PreviewSlide[];
    logs?: string[];
    connectionStatus?: ConnectionStatus;
  },
): RunSnapshot {
  return {
    jobId,
    uploadSession: params?.uploadSession,
    job: params?.job,
    slides: params?.slides ?? [],
    logs: params?.logs ?? [],
    selectedSlide: params?.selectedSlide,
    error: params?.error,
    result: params?.result,
    currentRunConfig: params?.currentRunConfig,
    connectionStatus: params?.connectionStatus ?? "disconnected",
  };
}

function applyRunToCurrent(run?: RunSnapshot) {
  if (!run) {
    return {};
  }
  return {
    uploadSession: run.uploadSession,
    jobId: run.jobId,
    job: run.job,
    slides: run.slides,
    logs: run.logs,
    selectedSlide: run.selectedSlide,
    connectionStatus: run.connectionStatus,
    error: run.error,
    result: run.result,
    activeJobId: run.job && FINAL_JOB_STATUSES.has(run.job.status) ? undefined : run.jobId,
    currentRunConfig: run.currentRunConfig,
  };
}

function clearLegacyGenerationStorage() {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.removeItem(LEGACY_GENERATION_STORAGE_KEY);
  } catch {
    // ignore storage cleanup failures
  }
}

function serializeRunsForStorage(runs: Record<string, RunSnapshot>) {
  return Object.fromEntries(
    Object.entries(runs).map(([jobId, run]) => [
      jobId,
      {
        jobId,
        uploadSession: run.uploadSession,
        job: run.job,
        error: run.error,
        currentRunConfig: run.currentRunConfig,
        connectionStatus: "disconnected" as const,
      } satisfies Partial<RunSnapshot> & { jobId: string; connectionStatus: ConnectionStatus },
    ]),
  );
}

export const useGeneration = create<GenerationState>()(
  persist(
    (set, get) => ({
      providers: [],
      slides: [],
      logs: [],
      connectionStatus: "disconnected",
      history: [],
      runs: {},
      socketsByJob: {},
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
        const run = createRunSnapshot(response.job_id, {
          uploadSession: get().uploadSession,
          job: {
            status: response.status,
            progress: 0,
            message: "Generation started",
            slides_completed: 0,
            total_slides: 0,
          },
          logs: ["[generate] Generation started"],
          currentRunConfig: {
            provider: payload.model_config.provider,
            model: payload.model_config.model,
            baseUrl: payload.model_config.base_url,
            options: payload.options,
            parentJobId: null,
          },
          error: undefined,
          result: undefined,
          selectedSlide: undefined,
        });
        set((state) => ({
          ...applyRunToCurrent(run),
          runs: {
            ...state.runs,
            [response.job_id]: run,
          },
        }));
        sessionStorage.setItem(`paper-ppt-live-job:${response.job_id}`, "1");
        get().syncHistory(response.job_id);
        return response.job_id;
      },
      async startRefine(payload) {
        const response = await refinePresentation(payload);
        const existingParent = get().history.find((entry) => entry.jobId === payload.job_id);
        const run = createRunSnapshot(response.job_id, {
          uploadSession: existingParent?.sourceType
            ? {
                session_id: payload.job_id,
                file_info: {
                  name: existingParent.fileName,
                  size: 0,
                  source_type: existingParent.sourceType,
                },
              }
            : undefined,
          job: {
            status: response.status,
            progress: 0,
            message: "Refinement started",
            slides_completed: 0,
            total_slides: 0,
          },
          logs: ["[refine] Refinement started"],
          currentRunConfig: {
            provider: payload.model_config.provider,
            model: payload.model_config.model,
            baseUrl: payload.model_config.base_url,
            options: payload.options,
            parentJobId: payload.job_id,
          },
          error: undefined,
          result: undefined,
          selectedSlide: undefined,
        });
        set((state) => ({
          ...applyRunToCurrent(run),
          runs: {
            ...state.runs,
            [response.job_id]: run,
          },
        }));
        sessionStorage.setItem(`paper-ppt-live-job:${response.job_id}`, "1");
        get().syncHistory(response.job_id);
        return response.job_id;
      },
      connect(jobId) {
        const existingSocket = get().socketsByJob[jobId];
        const existingRun = get().runs[jobId];

        if (existingSocket && (existingSocket.readyState === WebSocket.OPEN || existingSocket.readyState === WebSocket.CONNECTING)) {
          set((state) => ({
            ...applyRunToCurrent({
              ...(existingRun ?? createRunSnapshot(jobId)),
              connectionStatus: existingSocket.readyState === WebSocket.OPEN ? "connected" : "connecting",
            }),
            runs: existingRun
              ? {
                  ...state.runs,
                  [jobId]: {
                    ...existingRun,
                    connectionStatus: existingSocket.readyState === WebSocket.OPEN ? "connected" : "connecting",
                  },
                }
              : state.runs,
          }));
          return;
        }

        set((state) => ({
          ...applyRunToCurrent(existingRun ?? createRunSnapshot(jobId, { connectionStatus: "connecting" })),
          runs: {
            ...state.runs,
            [jobId]: {
              ...(existingRun ?? createRunSnapshot(jobId)),
              connectionStatus: "connecting",
            },
          },
        }));

        const socket = openJobSocket(
          jobId,
          (event) => {
            set((state) => {
              const currentRun = state.runs[jobId] ?? createRunSnapshot(jobId);
              const logLine = formatLog(event);
              const logs =
                event.message && currentRun.logs[currentRun.logs.length - 1] !== logLine
                  ? [...currentRun.logs, logLine]
                  : currentRun.logs;

              const nextJob: JobStatus = {
                status: event.type === "complete" ? "complete" : event.type === "error" ? "error" : event.stage,
                progress: event.progress,
                message: event.message,
                slides_completed: event.slides_completed,
                total_slides: event.total_slides,
                output_path:
                  typeof event.data.output_path === "string" ? event.data.output_path : currentRun.job?.output_path,
                error: event.type === "error" ? event.message : undefined,
              };

              let slides = currentRun.slides;
              if (event.type === "slide_ready" && typeof event.data.svg === "string") {
                slides = appendSlide(currentRun.slides, {
                  index: Number(event.data.page ?? currentRun.slides.length + 1),
                  name: `slide_${event.data.page ?? currentRun.slides.length + 1}`,
                  source: "output",
                  content: String(event.data.svg),
                });
              }

              const updatedRun: RunSnapshot = {
                ...currentRun,
                job: nextJob,
                slides,
                selectedSlide: pickSelectedSlide(slides, currentRun.selectedSlide),
                logs,
                error: event.type === "error" ? event.message : undefined,
                connectionStatus: FINAL_JOB_STATUSES.has(nextJob.status) ? "disconnected" : currentRun.connectionStatus,
              };

              return {
                ...(state.jobId === jobId ? applyRunToCurrent(updatedRun) : {}),
                runs: {
                  ...state.runs,
                  [jobId]: updatedRun,
                },
              };
            });
            get().syncHistory(jobId);

            if (event.stage === "generation") {
              void fetchPreview(jobId)
                .then((preview) => {
                  set((state) => {
                    const currentRun = state.runs[jobId] ?? createRunSnapshot(jobId);
                    if (!shouldReplaceSlides(currentRun.slides, preview.slides)) {
                      return state.jobId === jobId
                        ? {
                            ...(state.jobId === jobId ? applyRunToCurrent(currentRun) : {}),
                          }
                        : {};
                    }
                    const updatedRun: RunSnapshot = {
                      ...currentRun,
                      result: preview,
                      slides: preview.slides,
                      selectedSlide: pickSelectedSlide(preview.slides, currentRun.selectedSlide),
                    };
                    return {
                      ...(state.jobId === jobId ? applyRunToCurrent(updatedRun) : {}),
                      runs: {
                        ...state.runs,
                        [jobId]: updatedRun,
                      },
                    };
                  });
                  get().syncHistory(jobId);
                })
                .catch(() => undefined);
            }

            if (event.type === "complete") {
              void get().hydrateResult(jobId);
            }
          },
          () =>
            set((state) => {
              const run = state.runs[jobId] ?? createRunSnapshot(jobId);
              const updatedRun = { ...run, connectionStatus: "connected" as const };
              return {
                ...(state.jobId === jobId ? applyRunToCurrent(updatedRun) : {}),
                runs: {
                  ...state.runs,
                  [jobId]: updatedRun,
                },
              };
            }),
          () =>
            set((state) => {
              const run = state.runs[jobId] ?? createRunSnapshot(jobId);
              const updatedRun = { ...run, connectionStatus: "disconnected" as const };
              const nextSockets = { ...state.socketsByJob };
              delete nextSockets[jobId];
              return {
                ...(state.jobId === jobId ? applyRunToCurrent(updatedRun) : {}),
                runs: {
                  ...state.runs,
                  [jobId]: updatedRun,
                },
                socketsByJob: nextSockets,
              };
            }),
        );

        set((state) => ({
          socketsByJob: {
            ...state.socketsByJob,
            [jobId]: socket,
          },
        }));
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
        set((state) => {
          const currentRun = state.runs[jobId] ?? createRunSnapshot(jobId);
          const updatedRun: RunSnapshot = {
            ...currentRun,
            result,
            job,
            slides: result.slides,
            selectedSlide: pickSelectedSlide(result.slides, currentRun.selectedSlide),
            error: job.error ?? undefined,
            connectionStatus: FINAL_JOB_STATUSES.has(job.status) ? "disconnected" : currentRun.connectionStatus,
          };
          return {
            ...(state.jobId === jobId ? applyRunToCurrent(updatedRun) : {}),
            runs: {
              ...state.runs,
              [jobId]: updatedRun,
            },
          };
        });
        get().syncHistory(jobId);
      },
      async resumeCurrentRun(targetJobId) {
        const currentJobId = targetJobId ?? get().activeJobId ?? get().jobId;
        if (!currentJobId) {
          return false;
        }

        const currentRun = get().runs[currentJobId];
        const currentJob = currentRun?.job ?? get().job;
        if (
          !targetJobId &&
          ((get().socketsByJob[currentJobId] && currentRun?.connectionStatus !== "disconnected") ||
            (currentJob && FINAL_JOB_STATUSES.has(currentJob.status)))
        ) {
          if (currentRun) {
            set(() => ({
              ...applyRunToCurrent(currentRun),
            }));
          }
          return true;
        }

        try {
          const [job, preview] = await Promise.all([fetchJobStatus(currentJobId), fetchPreview(currentJobId).catch(() => undefined)]);

          set((state) => {
            const run = state.runs[currentJobId] ?? createRunSnapshot(currentJobId);
            const nextSlides = preview?.slides ?? run.slides;
            const updatedRun: RunSnapshot = {
              ...run,
              job,
              result: preview ?? run.result,
              slides: nextSlides,
              selectedSlide: pickSelectedSlide(nextSlides, run.selectedSlide),
              error: job.error ?? undefined,
              connectionStatus: FINAL_JOB_STATUSES.has(job.status) ? "disconnected" : run.connectionStatus,
            };
            return {
              ...applyRunToCurrent(updatedRun),
              runs: {
                ...state.runs,
                [currentJobId]: updatedRun,
              },
            };
          });
          get().syncHistory(currentJobId);

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
        set((state) => {
          if (!state.jobId) {
            return { selectedSlide: slide };
          }
          const currentRun = state.runs[state.jobId];
          if (!currentRun) {
            return { selectedSlide: slide };
          }
          return {
            selectedSlide: slide,
            runs: {
              ...state.runs,
              [state.jobId]: {
                ...currentRun,
                selectedSlide: slide,
              },
            },
          };
        });
      },
      syncHistory(targetJobId) {
        const jobId = targetJobId ?? get().jobId;
        const nextItem = buildHistoryItemFromRun(get().history, jobId ? get().runs[jobId] : undefined);
        if (!nextItem) {
          return;
        }
        set((state) => ({
          history: upsertHistoryItem(state.history, nextItem),
          activeJobId:
            state.jobId === nextItem.jobId && FINAL_JOB_STATUSES.has(nextItem.status) ? undefined : state.activeJobId,
        }));
      },
      async removeHistory(jobId) {
        const run = get().runs[jobId];
        const status = run?.job?.status ?? get().history.find((entry) => entry.jobId === jobId)?.status;
        if (status && !FINAL_JOB_STATUSES.has(status)) {
          await cancelJob(jobId).catch(() => undefined);
        }
        const socket = get().socketsByJob[jobId];
        socket?.close();
        set((state) => {
          const nextRuns = { ...state.runs };
          delete nextRuns[jobId];
          const nextSockets = { ...state.socketsByJob };
          delete nextSockets[jobId];
          const isCurrent = state.jobId === jobId;
          return {
            history: state.history.filter((entry) => entry.jobId !== jobId),
            runs: nextRuns,
            socketsByJob: nextSockets,
            ...(isCurrent
              ? {
                  uploadSession: undefined,
                  jobId: undefined,
                  job: undefined,
                  slides: [],
                  logs: [],
                  selectedSlide: undefined,
                  connectionStatus: "disconnected" as const,
                  error: undefined,
                  result: undefined,
                  activeJobId: undefined,
                  currentRunConfig: undefined,
                }
              : {}),
          };
        });
        sessionStorage.removeItem(`paper-ppt-live-job:${jobId}`);
      },
      reset() {
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
        });
      },
    }),
    {
      name: GENERATION_STORAGE_KEY,
      storage: createJSONStorage(() => {
        clearLegacyGenerationStorage();
        return window.localStorage;
      }),
      partialize: (state) => ({
        uploadSession: state.uploadSession,
        jobId: state.jobId,
        job: state.job,
        connectionStatus: "disconnected",
        error: state.error,
        history: state.history,
        runs: serializeRunsForStorage(state.runs),
        activeJobId: state.activeJobId,
        currentRunConfig: state.currentRunConfig,
      }),
    },
  ),
);
