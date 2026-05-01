import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Layout } from "../components/layout/Layout";
import { SlidePreview } from "../components/preview/SlidePreview";
import { SlideViewer } from "../components/preview/SlideViewer";
import { AgentLog } from "../components/progress/AgentLog";
import { ProgressPanel } from "../components/progress/ProgressPanel";
import { VersionHistory } from "../components/result/VersionHistory";
import { useGeneration } from "../hooks/useGeneration";
import { useLocale } from "../i18n";
import { fetchJobStatus, fetchPreview, fetchProjectPreview, getDownloadUrl, getDownloadUrlForOutput, isNotFoundError, reexportPresentation } from "../lib/api";
import { translateStageStatus } from "../lib/i18nStatus";
import type { DeepSeekSettings, GenerateRequestPayload, GenerationHistoryItem, JobStatus, OpenAISettings, PreviewResponse, PreviewSlide } from "../lib/types";

// Routing profile stored by GeneratePage so we can re-use model config here.
const ROUTING_PROFILE_STORAGE_KEY = "paper-ppt-agent-routing-profiles-v1";

interface RoutingProfile {
  model: string;
  baseUrl: string;
  apiKey: string;
  deepseekSettings?: DeepSeekSettings;
  openaiSettings?: OpenAISettings;
}
type RoutingProfileMap = Record<string, RoutingProfile>;

function readProviderProfile(
  provider: string,
  defaults?: { model?: string; baseUrl?: string },
): { provider: string; model: string; apiKey: string; baseUrl: string; deepseekSettings?: DeepSeekSettings; openaiSettings?: OpenAISettings } | null {
  try {
    const raw = window.localStorage.getItem(ROUTING_PROFILE_STORAGE_KEY);
    if (!raw) return null;
    const profiles = JSON.parse(raw) as RoutingProfileMap;
    const profile = profiles[provider];
    if (!profile?.apiKey) {
      return null;
    }
    return {
      provider,
      model: defaults?.model || profile.model,
      apiKey: profile.apiKey,
      baseUrl: defaults?.baseUrl || profile.baseUrl,
      deepseekSettings: profile.deepseekSettings,
      openaiSettings: profile.openaiSettings,
    };
  } catch {
    return null;
  }
}

export function ResultPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const jobId = params.get("job");
  const { t, locale } = useLocale();
  const {
    reset,
    history,
    startRefine,
    connect,
    activeJobId,
    job: liveJob,
    slides: liveSlides,
    result: liveResult,
    logs,
    connectionStatus,
  } = useGeneration();
  // Direct-bind the global error-store setters so we can mirror local
  // page errors (load / refine / reexport / failed-job) into the global
  // error slot — that's what drives the floating ErrorBanner.
  const setGlobalError = (msg: string | undefined) =>
    useGeneration.setState({ error: msg });

  const historyEntry = history.find((entry) => entry.jobId === jobId);
  const [result, setResult] = useState<PreviewResponse | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [slides, setSlides] = useState<PreviewSlide[]>([]);
  const [selectedSlide, setSelectedSlide] = useState<PreviewSlide | undefined>(undefined);
  const [loadError, setLoadError] = useState<string | null>(null);

  const outputPath = job?.output_path ?? result?.output_path ?? historyEntry?.outputPath;
  const downloadHref = outputPath
    ? getDownloadUrlForOutput(outputPath)
    : jobId
      ? getDownloadUrl(jobId)
      : undefined;

  // ── refine state ───────────────────────────────────────────────────────────
  const [feedback, setFeedback] = useState("");
  const [refineLoading, setRefineLoading] = useState(false);
  const [refineError, setRefineError] = useState<string | null>(null);
  const [targetPagesSet, setTargetPagesSet] = useState<Set<number>>(new Set());
  const [allowStructureChanges, setAllowStructureChanges] = useState(false);
  const [reexportLoading, setReexportLoading] = useState(false);
  const [reexportError, setReexportError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId || jobId !== activeJobId) {
      return;
    }

    if (liveResult) {
      setResult(liveResult);
      setSlides(liveResult.slides);
      setSelectedSlide((current) => pickSelectedSlide(liveResult.slides, current));
    }
    if (liveJob) {
      setJob(liveJob);
    }
  }, [activeJobId, jobId, liveJob, liveResult]);

  useEffect(() => {
    let cancelled = false;

    async function loadResult(currentJobId: string, entry?: GenerationHistoryItem) {
      const projectDir = entry?.projectDir ?? deriveProjectDirFromOutputPath(entry?.outputPath);
      const canLoadFromProject = Boolean(projectDir) && currentJobId !== activeJobId;

      try {
        const [nextResult, nextJob] = canLoadFromProject
          ? await Promise.all([
              fetchProjectPreview(projectDir!),
              fetchJobStatus(currentJobId).catch(() => {
                if (!entry) {
                  throw new Error("Job not found.");
                }
                return buildStoredJob(entry);
              }),
            ])
          : await Promise.all([
              fetchPreview(currentJobId).catch(async () => {
                if (!projectDir) {
                  throw new Error("Result not found.");
                }
                return fetchProjectPreview(projectDir);
              }),
              fetchJobStatus(currentJobId).catch(() => {
                if (!entry) {
                  throw new Error("Job not found.");
                }
                return buildStoredJob(entry);
              }),
            ]);

        if (cancelled) {
          return;
        }

        setResult(nextResult);
        setJob(nextJob ?? (entry ? buildStoredJob(entry) : null));
        setSlides(nextResult.slides);
        setSelectedSlide((current) => pickSelectedSlide(nextResult.slides, current));
        setLoadError(null);
      } catch (error) {
        if (cancelled) {
          return;
        }
        setResult(null);
        setJob(entry ? buildStoredJob(entry) : null);
        setSlides([]);
        setSelectedSlide(undefined);
        // A 404 from the backend means the job is gone (server restart,
        // session GC, or someone shared a stale URL). Use a friendlier
        // message that points the user to the next step instead of
        // dumping the raw error string.
        if (isNotFoundError(error)) {
          setLoadError(
            entry
              ? "This run is no longer available on the server, but its history record was kept. Start a new run to regenerate."
              : "This job was not found. It may have been removed or never existed on this server.",
          );
        } else {
          setLoadError(error instanceof Error ? error.message : "Failed to load result.");
        }
      }
    }

    if (!jobId) {
      setResult(null);
      setJob(null);
      setSlides([]);
      setSelectedSlide(undefined);
      setLoadError("Missing job id.");
      return () => {
        cancelled = true;
      };
    }

    if (jobId === activeJobId && liveJob) {
      setJob(liveJob);
      setResult(liveResult ?? null);
      setSlides(liveResult?.slides ?? liveSlides);
      setSelectedSlide((current) => pickSelectedSlide(liveResult?.slides ?? liveSlides, current));
      setLoadError(null);
      return () => {
        cancelled = true;
      };
    }

    void loadResult(jobId, historyEntry);
    return () => {
      cancelled = true;
    };
  }, [activeJobId, historyEntry, jobId, liveJob, liveResult, liveSlides]);

  useEffect(() => {
    setSelectedSlide((current) => pickSelectedSlide(slides, current));
  }, [slides]);

  // Mirror any active page-level error into the global ``error`` store so
  // the floating ErrorBanner becomes visible. Priority order:
  //   1. ``loadError``     — the result preview / job lookup failed.
  //   2. ``reexportError`` — a re-export attempt failed.
  //   3. ``refineError``   — a refine submission failed.
  //   4. ``job.error``     — the failed run itself carries an error.
  // Cleared on unmount so navigating away from the page doesn't leave a
  // stale banner behind.
  useEffect(() => {
    const failedJobError =
      job?.status === "error" ? job.error ?? historyEntry?.error ?? null : null;
    const message = loadError || reexportError || refineError || failedJobError || null;
    if (message) {
      setGlobalError(message);
    } else {
      setGlobalError(undefined);
    }
    return () => {
      // Only clear if we were the ones who set it — comparing the current
      // store value to the message we set keeps unrelated errors (e.g.
      // raised by another page that just navigated in) intact.
      const current = useGeneration.getState().error;
      if (current && current === message) {
        setGlobalError(undefined);
      }
    };
  }, [loadError, reexportError, refineError, job?.status, job?.error, historyEntry?.error]);

  // Auto-sync multi-select when slide count changes (keeps valid pages only)
  useEffect(() => {
    const max = slides.length;
    setTargetPagesSet((prev) => {
      const next = new Set<number>();
      prev.forEach((page) => {
        if (page >= 1 && page <= max) next.add(page);
      });
      if (next.size === prev.size) return prev;
      return next;
    });
  }, [slides.length]);

  // Navigate to generation page to watch refine progress
  const handleRefine = async () => {
    if (!feedback.trim() || !jobId) return;

    const targetPages: number[] = Array.from(targetPagesSet).sort((a, b) => a - b);

    const profile = readProviderProfile(historyEntry?.provider ?? "openai", {
      model: historyEntry?.model,
      baseUrl: historyEntry?.baseUrl ?? undefined,
    });
    if (!profile || !profile.apiKey) {
      setRefineError("No model configuration found. Please return to the generate page and configure a model first.");
      return;
    }

    const fallbackOptions: GenerateRequestPayload["options"] = historyEntry?.options ?? {
      canvas_format: "ppt169",
      style: "academic",
      language: "zh",
      detail_level: "normal",
    };

    setRefineLoading(true);
    setRefineError(null);
    try {
      const newJobId = await startRefine({
        job_id: jobId,
        feedback: feedback.trim(),
        model_config: {
          provider: profile.provider,
          model: profile.model,
          api_key: profile.apiKey,
          base_url: profile.baseUrl || undefined,
          deepseek_settings:
            profile.provider === "deepseek" ? profile.deepseekSettings : undefined,
          openai_settings:
            profile.provider === "openai" ? profile.openaiSettings : undefined,
        },
        options: fallbackOptions,
        target_pages: targetPages,
        allow_structure_changes: allowStructureChanges,
      });
      setFeedback("");
      setTargetPagesSet(new Set());
      connect(newJobId);
      navigate(`/result?job=${newJobId}`);
    } catch (err) {
      setRefineError(err instanceof Error ? err.message : "Refinement failed.");
    } finally {
      setRefineLoading(false);
    }
  };

  const handleReexport = async () => {
    if (!jobId) return;
    setReexportLoading(true);
    setReexportError(null);
    try {
      const response = await reexportPresentation(jobId);
      setJob((current) =>
        current
          ? {
              ...current,
              status: response.status,
              output_path: response.output_path,
              error: null,
            }
          : {
              status: response.status,
              progress: 1,
              message: "",
              slides_completed: slides.length,
              total_slides: slides.length,
              output_path: response.output_path,
              error: null,
            },
      );
      setResult((current) =>
        current
          ? {
              ...current,
              output_path: response.output_path,
              status: response.status,
            }
          : current,
      );
    } catch (err) {
      setReexportError(err instanceof Error ? err.message : "Re-export failed.");
    } finally {
      setReexportLoading(false);
    }
  };

  return (
    <Layout contentClassName="result-page">
      <section className="result-hero">
        <div className="result-copy">
          <p className="eyebrow">{t("result.eyebrow")}</p>
          <h1>{t("result.title")}</h1>
          <p className="muted-copy">{t("result.body")}</p>
        </div>
        <div className="result-actions">
          <button
            type="button"
            className="secondary-button"
            onClick={() => {
              reset();
              navigate("/generate?fresh=1");
            }}
          >
            {t("result.newRun")}
          </button>
          {downloadHref ? (
            <a href={downloadHref} className="primary-button">
              {t("result.download")}
            </a>
          ) : null}
          <button
            type="button"
            className="secondary-button"
            onClick={() => void handleReexport()}
            disabled={!jobId || reexportLoading}
          >
            {reexportLoading ? t("result.reexportLoading") : t("result.reexport")}
          </button>
        </div>
      </section>

      <section className="result-summary">
        <div className="metric-stripe">
          <span>{t("result.status")}</span>
          <strong>{formatStatusLabel(result?.status ?? job?.status ?? historyEntry?.status, locale, t("common.unknown"))}</strong>
        </div>
        <div className="metric-stripe">
          <span>{t("result.slides")}</span>
          <strong>{slides.length}</strong>
        </div>
        <div className="metric-stripe" style={{ minWidth: 0 }}>
          <span>{t("result.output")}</span>
          <strong style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "block", maxWidth: "100%" }} title={outputPath ?? ""}>
            {(() => {
              const p = outputPath;
              if (!p) return t("common.pending");
              const parts = p.replace(/\\/g, "/").split("/");
              return parts[parts.length - 1];
            })()}
          </strong>
        </div>
      </section>

      <section className="result-grid">
        <div className="column-stack">
          <SlidePreview slides={slides} selectedSlide={selectedSlide} onSelect={setSelectedSlide} />
        </div>
        <SlideViewer slide={selectedSlide} />
      </section>

      {loadError ? <p className="error-text">{loadError}</p> : null}
      {reexportError ? <p className="error-text">{reexportError}</p> : null}

      {/* ── Feedback / Refine section ── */}
      <section className="result-refine">
        <div className="refine-header">
          <h2>{t("result.refineTitle")}</h2>
          <p className="muted-copy">{t("result.refineBody")}</p>
        </div>

        <div className="refine-form">
          <div className="refine-form-row">
            <div className="field-label" style={{ flex: 1 }}>
              <div className="selectPages-toolbar">
                <strong>{t("result.selectPages")}</strong>
                <button
                  type="button"
                  onClick={() =>
                    setTargetPagesSet(
                      targetPagesSet.size === slides.length
                        ? new Set()
                        : new Set(slides.map((_, i) => i + 1)),
                    )
                  }
                  disabled={refineLoading || slides.length === 0}
                  className="ghost-button"
                >
                  {t("result.selectAll")} ({targetPagesSet.size}/{slides.length})
                </button>
              </div>
              <div className="slide-thumb-multiselect" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(110px, 1fr))", gap: 8 }}>
                {slides.map((slide, idx) => {
                  const page = idx + 1;
                  const selected = targetPagesSet.has(page);
                  return (
                    <div
                      key={slide.name ?? idx}
                      className={`slide-thumb-selectable ${selected ? "slide-thumb-selected" : ""}`}
                      onClick={() => {
                        if (refineLoading) return;
                        setTargetPagesSet((prev) => {
                          const next = new Set(prev);
                          if (next.has(page)) next.delete(page);
                          else next.add(page);
                          return next;
                        });
                      }}
                      title={`Page ${page}`}
                    >
                      <div className="slide-thumb-checkbox">{selected ? "✓" : ""}</div>
                      <div
                        style={{
                          background: "#fff",
                          borderRadius: 6,
                          overflow: "hidden",
                          aspectRatio: "16/9",
                        }}
                        dangerouslySetInnerHTML={{ __html: slide.content ?? "" }}
                      />
                      <div style={{ textAlign: "center", fontSize: 11, marginTop: 4, color: "#9ba0a6" }}>
                        {page}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={allowStructureChanges}
                onChange={(e) => setAllowStructureChanges(e.target.checked)}
                disabled={refineLoading}
              />
              <span>{t("result.allowStructure")}</span>
            </label>
          </div>
          <textarea
            className="refine-textarea"
            rows={4}
            placeholder={t("result.refinePlaceholder")}
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            disabled={refineLoading}
          />
          {refineError ? <p className="error-text">{refineError}</p> : null}
          <button
            type="button"
            className="primary-button"
            disabled={!feedback.trim() || refineLoading || !jobId}
            onClick={() => void handleRefine()}
          >
            {refineLoading ? t("result.refineLoading") : t("result.refineSubmit")}
          </button>
        </div>
      </section>

      <VersionHistory jobId={jobId} />

      {jobId === activeJobId ? (
        <section className="result-refine-monitor">
          <div className="column-stack">
            <ProgressPanel job={liveJob} connectionStatus={connectionStatus} />
            <AgentLog logs={logs} />
          </div>
        </section>
      ) : null}
    </Layout>
  );
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

function buildStoredJob(historyItem: GenerationHistoryItem): JobStatus {
  return {
    status: historyItem.status,
    progress: historyItem.status === "complete" ? 1 : 0,
    message: "",
    slides_completed: historyItem.slideCount,
    total_slides: historyItem.slideCount,
    output_path: historyItem.outputPath ?? null,
    error: historyItem.status === "error" ? "Job not found." : null,
  };
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

function formatStatusLabel(
  status: string | null | undefined,
  locale: "en" | "zh",
  unknownLabel: string,
) {
  return status ? translateStageStatus(status, locale, "history") : unknownLabel;
}
