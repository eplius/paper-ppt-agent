import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Layout } from "../components/layout/Layout";
import { SlidePreview } from "../components/preview/SlidePreview";
import { SlideViewer } from "../components/preview/SlideViewer";
import { AgentLog } from "../components/progress/AgentLog";
import { ProgressPanel } from "../components/progress/ProgressPanel";
import { useGeneration } from "../hooks/useGeneration";
import { useLocale } from "../i18n";
import { fetchJobStatus, fetchPreview, fetchProjectPreview, getDownloadUrl, getDownloadUrlForOutput } from "../lib/api";
import type { GenerateRequestPayload, GenerationHistoryItem, JobStatus, PreviewResponse, PreviewSlide } from "../lib/types";

// Routing profile stored by GeneratePage so we can re-use model config here.
const ROUTING_PROFILE_STORAGE_KEY = "paper-ppt-agent-routing-profiles-v1";

interface RoutingProfile {
  model: string;
  baseUrl: string;
  apiKey: string;
}
type RoutingProfileMap = Record<string, RoutingProfile>;

function readProviderProfile(
  provider: string,
  defaults?: { model?: string; baseUrl?: string },
): { provider: string; model: string; apiKey: string; baseUrl: string } | null {
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
    };
  } catch {
    return null;
  }
}

export function ResultPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const jobId = params.get("job");
  const { t } = useLocale();
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
  const [targetPagesText, setTargetPagesText] = useState("");
  const [allowStructureChanges, setAllowStructureChanges] = useState(false);

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
              Promise.resolve(entry ? buildStoredJob(entry) : null),
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
        setLoadError(error instanceof Error ? error.message : "Failed to load result.");
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

  // Navigate to generation page to watch refine progress
  const handleRefine = async () => {
    if (!feedback.trim() || !jobId) return;

    const targetPages = parsePageSelection(targetPagesText);
    if (targetPagesText.trim() && targetPages.length === 0) {
      setRefineError("页码范围格式不正确，例如 3 或 2,4-6。");
      return;
    }

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
        },
        options: fallbackOptions,
        target_pages: targetPages,
        allow_structure_changes: allowStructureChanges,
      });
      setFeedback("");
      setTargetPagesText("");
      connect(newJobId);
      navigate(`/result?job=${newJobId}`);
    } catch (err) {
      setRefineError(err instanceof Error ? err.message : "Refinement failed.");
    } finally {
      setRefineLoading(false);
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
        </div>
      </section>

      <section className="result-summary">
        <div className="metric-stripe">
          <span>{t("result.status")}</span>
          <strong>{formatStatusLabel(result?.status ?? job?.status ?? historyEntry?.status, t("common.unknown"), t)}</strong>
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

      {/* ── Feedback / Refine section ── */}
      <section className="result-refine">
        <div className="refine-header">
          <h2>{t("result.refineTitle")}</h2>
          <p className="muted-copy">{t("result.refineBody")}</p>
        </div>

        <div className="refine-form">
          <div className="refine-form-row">
            <label className="field-label">
              仅修改页码
              <input
                className="input-field"
                placeholder="例如：3 或 2,4-6；留空表示全部页面"
                value={targetPagesText}
                onChange={(e) => setTargetPagesText(e.target.value)}
                disabled={refineLoading}
              />
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={allowStructureChanges}
                onChange={(e) => setAllowStructureChanges(e.target.checked)}
                disabled={refineLoading}
              />
              <span>允许结构调整（增删页、插页、重排）</span>
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

function parsePageSelection(value: string): number[] {
  const result = new Set<number>();
  for (const rawPart of value.split(",")) {
    const part = rawPart.trim();
    if (!part) {
      continue;
    }
    const rangeMatch = part.match(/^(\d+)\s*-\s*(\d+)$/);
    if (rangeMatch) {
      const start = Number(rangeMatch[1]);
      const end = Number(rangeMatch[2]);
      if (!Number.isFinite(start) || !Number.isFinite(end) || start <= 0 || end < start) {
        return [];
      }
      for (let page = start; page <= end; page += 1) {
        result.add(page);
      }
      continue;
    }
    const page = Number(part);
    if (!Number.isFinite(page) || page <= 0) {
      return [];
    }
    result.add(page);
  }
  return [...result].sort((left, right) => left - right);
}

function formatStatusLabel(
  status: string | null | undefined,
  unknownLabel: string,
  t: (key: string) => string,
) {
  const normalized = status ?? "";
  if (normalized === "complete") return t("progress.ready");
  if (normalized === "error") return "失败";
  if (normalized === "cancelled") return "已取消";
  if (normalized === "pending") return t("common.pending");
  if (normalized === "generation") return "生成中";
  if (normalized === "research") return "分析中";
  if (normalized === "strategy") return "规划中";
  if (normalized === "postprocess") return "后处理中";
  if (normalized === "export") return "导出中";
  if (normalized === "parsing") return "解析中";
  return normalized || unknownLabel;
}
