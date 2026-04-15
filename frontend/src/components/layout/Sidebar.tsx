import { Link, useLocation } from "react-router-dom";
import { useGeneration } from "../../hooks/useGeneration";
import { useLocale } from "../../i18n";

export function Sidebar() {
  const { t, locale } = useLocale();
  const location = useLocation();
  const { history, activeJobId, removeHistory } = useGeneration();
  const searchParams = new URLSearchParams(location.search);
  const links = [
    { to: "/", label: t("sidebar.overview") },
    { to: "/generate", label: t("sidebar.generationStudio") },
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
          >
            <strong className="history-create-name">{t("result.newRun")}</strong>
          </Link>
          {recentHistory.length > 0 ? (
            recentHistory.map((entry) => {
              const target = entry.jobId === activeJobId ? "/generate" : `/result?job=${entry.jobId}`;
              const isActive =
                (target === "/generate" && location.pathname === "/generate") ||
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
                    onClick={() => removeHistory(entry.jobId)}
                  >
                    ×
                  </button>
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
  };

  const normalized = status.toLowerCase();
  const matched = translations[normalized];
  if (matched) {
    return locale === "zh" ? matched.zh : matched.en;
  }
  return status;
}
