import { CheckCircle2, Circle, Loader2, FileSearch, Search, Target, Wand2, Settings, Download } from "lucide-react";
import type { ComponentType } from "react";
import type { JobStatus } from "../../lib/types";
import { useLocale } from "../../i18n";

const STAGES: Array<{ id: string; icon: ComponentType<{ size?: number; color?: string }> }> = [
  { id: "parsing", icon: FileSearch },
  { id: "research", icon: Search },
  { id: "strategy", icon: Target },
  { id: "generation", icon: Wand2 },
  { id: "postprocess", icon: Settings },
  { id: "export", icon: Download },
];

const STAGE_LABELS: Record<string, { zh: string; en: string }> = {
  parsing: { zh: "解析论文", en: "Parsing" },
  research: { zh: "研究分析", en: "Research" },
  strategy: { zh: "策略规划", en: "Strategy" },
  generation: { zh: "生成页面", en: "Generation" },
  postprocess: { zh: "后处理", en: "Post-process" },
  export: { zh: "导出文件", en: "Export" },
};

interface ProgressPanelProps {
  job?: JobStatus;
  connectionStatus: string;
}

const STAGE_INDEX = new Map(STAGES.map((stage, index) => [stage.id, index]));

export function ProgressPanel({ job, connectionStatus }: ProgressPanelProps) {
  const { t, locale } = useLocale();
  const isConnected = connectionStatus === "connected";
  const isConnecting = connectionStatus === "connecting";
  const activeStageIndex =
    job?.status && STAGE_INDEX.has(job.status) ? STAGE_INDEX.get(job.status)! : -1;
  const allComplete = job?.status === "complete";
  const statusLabel = (() => {
    const status = job?.status ?? "idle";
    if (status in STAGE_LABELS) {
      return locale === "zh" ? STAGE_LABELS[status].zh : STAGE_LABELS[status].en;
    }
    if (status === "complete") {
      return locale === "zh" ? "已完成" : "Complete";
    }
    if (status === "error") {
      return locale === "zh" ? "失败" : "Error";
    }
    if (status === "cancelled") {
      return locale === "zh" ? "已取消" : "Cancelled";
    }
    if (status === "pending") {
      return locale === "zh" ? "等待中" : "Pending";
    }
    if (status === "idle") {
      return locale === "zh" ? "空闲" : "Idle";
    }
    return status;
  })();
  const activeMessage = translateJobMessage(job?.message, locale);

  return (
    <section className="panel monitor-panel">
      <div className="panel-header-row" style={{ justifyContent: "space-between" }}>
        <div>
          <p className="panel-title">{t("progress.title")}</p>
          <p className="muted-copy" style={{ marginTop: "0.25rem" }}>{t("progress.body")}</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.82rem", color: "var(--muted)" }}>
          <span
            className={`status-dot ${
              isConnected
                ? "status-dot-connected"
                : isConnecting
                ? "status-dot-connecting"
                : "status-dot-disconnected"
            }`}
          />
          {isConnected
            ? locale === "zh" ? "已连接" : "Connected"
            : isConnecting
            ? locale === "zh" ? "连接中" : "Connecting"
            : locale === "zh" ? "未连接" : "Offline"}
        </div>
      </div>

      <div className="monitor-metrics">
        <div>
          <span>{t("progress.metricProgress")}</span>
          <strong>{Math.round((job?.progress ?? 0) * 100)}%</strong>
        </div>
        <div>
          <span>{t("progress.metricSlides")}</span>
          <strong>{job?.slides_completed ?? 0}</strong>
        </div>
        <div>
          <span>{t("progress.metricStatus")}</span>
          <strong>{statusLabel}</strong>
        </div>
      </div>

      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${(job?.progress ?? 0) * 100}%` }} />
      </div>

      <ul className="stage-list">
        {STAGES.map((stage, index) => {
          const isComplete =
            allComplete ||
            (activeStageIndex >= 0 && index < activeStageIndex);
          const isActive = job?.status === stage.id;
          const Icon = stage.icon;
          const label = locale === "zh" ? STAGE_LABELS[stage.id].zh : STAGE_LABELS[stage.id].en;
          return (
            <li
              key={stage.id}
              className={`stage-item ${isActive ? "stage-active" : ""} ${isComplete ? "stage-complete" : ""}`}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                <span
                  className="stage-icon"
                  style={{ color: isComplete ? "var(--success)" : isActive ? "var(--accent)" : "var(--muted)" }}
                >
                  <Icon size={15} />
                </span>
                <strong>{label}</strong>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                {isActive && <Loader2 size={14} className="spin" color="var(--accent)" />}
                {isComplete && !isActive && <CheckCircle2 size={14} color="var(--success)" />}
                {!isComplete && !isActive && <Circle size={14} color="var(--muted)" />}
                <span style={{ fontSize: "0.8rem", color: isComplete ? "var(--success)" : "var(--muted)" }}>
                  {isActive
                    ? (activeMessage ?? (locale === "zh" ? "处理中..." : "Processing..."))
                    : isComplete
                    ? t("progress.ready")
                    : t("progress.pending")}
                </span>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function translateJobMessage(message: string | undefined, locale: "en" | "zh") {
  if (!message || locale !== "zh") {
    return message;
  }

  const exact: Record<string, string> = {
    "Generation started": "任务已开始",
    "Refinement started": "优化任务已开始",
    "Queued for generation": "已加入生成队列",
    "Queued for refinement": "已加入优化队列",
    "Parsing paper...": "正在解析论文...",
    "Analyzing paper content...": "正在分析论文内容...",
    "Manuscript generated": "讲稿已生成",
    "Creating design specification...": "正在生成设计规范...",
    "Design spec created": "设计规范已生成",
    "Generating slide SVGs...": "正在生成幻灯片 SVG...",
    "Finalizing SVGs...": "正在整理 SVG...",
    "Exporting to PowerPoint...": "正在导出 PowerPoint...",
    "PowerPoint generated!": "PowerPoint 已生成",
    "Re-generating slides with feedback...": "正在根据反馈重新生成幻灯片...",
    "Re-generating selected slides with feedback...": "正在根据反馈重新生成选定页面...",
    "Refined PowerPoint generated!": "优化后的 PowerPoint 已生成",
    "Job cancelled": "任务已取消",
    "Refine job cancelled": "优化任务已取消",
    "Revising manuscript structure from feedback...": "正在根据反馈重写讲稿结构...",
    "Manuscript revised": "讲稿已更新",
    "Rebuilding design specification...": "正在重建设计规范...",
    "Design spec rebuilt": "设计规范已重建",
  };
  if (exact[message]) {
    return exact[message];
  }

  const parsedMatch = message.match(/^Parsed:\s*(.+)$/);
  if (parsedMatch) {
    return `已解析：${parsedMatch[1]}`;
  }

  const generatedSlideMatch = message.match(/^Generated slide (\d+)\/(\d+)$/);
  if (generatedSlideMatch) {
    return `已生成第 ${generatedSlideMatch[1]}/${generatedSlideMatch[2]} 页`;
  }

  const generatedSlidesMatch = message.match(/^(\d+) slides generated$/);
  if (generatedSlidesMatch) {
    return `已生成 ${generatedSlidesMatch[1]} 页`;
  }

  const regeneratedSlidesMatch = message.match(/^(\d+) slides regenerated$/);
  if (regeneratedSlidesMatch) {
    return `已重新生成 ${regeneratedSlidesMatch[1]} 页`;
  }

  const processedFilesMatch = message.match(/^Processed (\d+) files$/);
  if (processedFilesMatch) {
    return `已处理 ${processedFilesMatch[1]} 个文件`;
  }

  return message;
}
