import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useGeneration } from "../../hooks/useGeneration";
import { useLocale } from "../../i18n";

export function Sidebar() {
  const { t, locale } = useLocale();
  const location = useLocation();
  const { history, activeJobId, removeHistory, reset } = useGeneration();
  const [confirmState, setConfirmState] = useState<{
    jobId: string;
    top: number;
    left: number;
  } | null>(null);
  const confirmRef = useRef<HTMLDivElement | null>(null);
  const searchParams = new URLSearchParams(location.search);
  const links = [
    { to: "/", label: t("sidebar.overview") },
    { to: "/generate", label: t("sidebar.generationStudio") },
    { to: "/logs", label: t("sidebar.logs") },
  ];
  const recentHistory = history.slice(0, 5);
  const currentResultJobId = searchParams.get("job");
  const isFreshEntryActive = location.pathname === "/generate" && searchParams.get("fresh") === "1";
  const formatter = new Intl.DateTimeFormat(locale === "zh" ? "zh-CN" : "en-US", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  useEffect(() => {
    if (!confirmState) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (confirmRef.current && !confirmRef.current.contains(event.target as Node)) {
        setConfirmState(null);
      }
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setConfirmState(null);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [confirmState]);

  return (
    <aside className="sidebar">
      <div className="sidebar-section">
        <p className="sidebar-label">{t("sidebar.navigation")}</p>
        {links.map((link) => (
          <Link
            key={link.to}
            to={link.to}
            className={`sidebar-link ${location.pathname === link.to ? "sidebar-link-active" : ""}`}
          >
            {link.label}
          </Link>
        ))}
      </div>

      <div className="sidebar-section">
        <p className="sidebar-label">{t("sidebar.history")}</p>
        <div className="history-list">
          <Link
            to="/generate?fresh=1"
            className={`history-create-card ${isFreshEntryActive ? "history-create-card-active" : ""}`}
            onClick={() => reset()}
          >
            <strong className="history-create-name">{t("result.newRun")}</strong>
          </Link>
          {recentHistory.length > 0 ? (
            recentHistory.map((entry) => {
              const target = getHistoryTarget(entry, activeJobId);
              const isConfirmOpen = confirmState?.jobId === entry.jobId;
              const isActive =
                (target.startsWith("/generate") && location.pathname === "/generate" && searchParams.get("job") === entry.jobId) ||
                (target === "/generate" && location.pathname === "/generate" && !searchParams.get("job")) ||
                (location.pathname === "/result" && currentResultJobId === entry.jobId);

              return (
                <div key={entry.jobId} className="history-record">
                  <Link to={target} className={`history-card ${isActive ? "history-card-active" : ""}`}>
                    <div className="history-card-header">
                      <strong className="history-name" title={entry.fileName}>
                        {entry.fileName}
                      </strong>
                      <span className="history-status">{translateHistoryStatus(entry.status, locale)}</span>
                    </div>
                    <div className="history-card-meta">
                      <span>{entry.slideCount > 0 ? `${entry.slideCount} ${t("preview.slides")}` : t("common.pending")}</span>
                      <span>{formatter.format(new Date(entry.updatedAt))}</span>
                    </div>
                  </Link>
                  <button
                    type="button"
                    className="history-delete"
                    aria-label={locale === "zh" ? "删除记录" : "Delete history item"}
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      setConfirmState((current) => {
                        if (current?.jobId === entry.jobId) {
                          return null;
                        }
                        return {
                          jobId: entry.jobId,
                          ...getDeleteConfirmPosition(event.clientX, event.clientY),
                        };
                      });
                    }}
                  >
                    ×
                  </button>
                  {isConfirmOpen ? (
                    <div
                      ref={confirmRef}
                      className="history-delete-confirm"
                      style={{
                        top: `${confirmState.top}px`,
                        left: `${confirmState.left}px`,
                      }}
                      role="dialog"
                      aria-modal="false"
                    >
                      <p>{t("sidebar.confirmDelete")}</p>
                      <div className="history-delete-confirm-actions">
                        <button
                          type="button"
                          className="history-delete-confirm-btn"
                          onClick={() => setConfirmState(null)}
                        >
                          {t("versions.close")}
                        </button>
                        <button
                          type="button"
                          className="history-delete-confirm-btn history-delete-confirm-btn-danger"
                          onClick={() => {
                            setConfirmState(null);
                            void removeHistory(entry.jobId);
                          }}
                        >
                          {t("versions.delete")}
                        </button>
                      </div>
                    </div>
                  ) : null}
                </div>
              );
            })
          ) : (
            <p className="muted-copy">{t("sidebar.historyEmpty")}</p>
          )}
        </div>
      </div>
    </aside>
  );
}

function getDeleteConfirmPosition(clientX: number, clientY: number) {
  const width = 188;
  const height = 96;
  return {
    left: Math.min(window.innerWidth - width - 12, Math.max(12, clientX - width + 20)),
    top: Math.min(window.innerHeight - height - 12, Math.max(12, clientY - height - 10)),
  };
}

function getHistoryTarget(
  entry: { jobId: string; status: string; parentJobId?: string | null },
  activeJobId?: string,
) {
  if (entry.parentJobId || isHistoryResultStatus(entry.status)) {
    return `/result?job=${entry.jobId}`;
  }
  if (entry.jobId === activeJobId) {
    return `/generate?job=${entry.jobId}`;
  }
  return `/generate?job=${entry.jobId}`;
}

function isHistoryResultStatus(status: string) {
  const normalized = status.toLowerCase();
  return normalized === "complete" || normalized === "error" || normalized === "cancelled";
}

function translateHistoryStatus(status: string, locale: "en" | "zh") {
  const translations: Record<string, { zh: string; en: string }> = {
    pending: { zh: "处理中", en: "Pending" },
    parsing: { zh: "解析中", en: "Parsing" },
    research: { zh: "研究中", en: "Research" },
    strategy: { zh: "规划中", en: "Strategy" },
    generation: { zh: "生成中", en: "Generation" },
    postprocess: { zh: "后处理中", en: "Post-process" },
    export: { zh: "导出中", en: "Export" },
    complete: { zh: "已完成", en: "Complete" },
    error: { zh: "失败", en: "Error" },
    cancelled: { zh: "已取消", en: "Cancelled" },
  };

  const normalized = status.toLowerCase();
  const matched = translations[normalized];
  if (matched) {
    return locale === "zh" ? matched.zh : matched.en;
  }
  return status;
}
