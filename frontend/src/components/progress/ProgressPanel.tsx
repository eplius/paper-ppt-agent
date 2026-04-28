import { CheckCircle2, Circle, Loader2, FileSearch, Search, Target, Wand2, Settings, Download } from "lucide-react";
import type { ComponentType } from "react";
import type { JobStatus } from "../../lib/types";
import { useLocale } from "../../i18n";
import { normalizeProgressStage, translateJobMessage, translateStageStatus } from "../../lib/i18nStatus";

const STAGES: Array<{ id: string; icon: ComponentType<{ size?: number; color?: string }> }> = [
  { id: "parsing", icon: FileSearch },
  { id: "research", icon: Search },
  { id: "strategy", icon: Target },
  { id: "generation", icon: Wand2 },
  { id: "postprocess", icon: Settings },
  { id: "export", icon: Download },
];

interface ProgressPanelProps {
  job?: JobStatus;
  connectionStatus: string;
}

const STAGE_INDEX = new Map(STAGES.map((stage, index) => [stage.id, index]));

export function ProgressPanel({ job, connectionStatus }: ProgressPanelProps) {
  const { t, locale } = useLocale();
  const isConnected = connectionStatus === "connected";
  const isConnecting = connectionStatus === "connecting";
  const activeStatus = normalizeProgressStage(job?.status);
  const activeStageIndex =
    activeStatus && STAGE_INDEX.has(activeStatus) ? STAGE_INDEX.get(activeStatus)! : -1;
  const allComplete = job?.status === "complete";
  const statusLabel = translateStageStatus(job?.status ?? "idle", locale, "progress");
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
          <strong className="monitor-status-value">{statusLabel}</strong>
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
          const isActive = activeStatus === stage.id;
          const Icon = stage.icon;
          const label = translateStageStatus(stage.id, locale, "progress");
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
