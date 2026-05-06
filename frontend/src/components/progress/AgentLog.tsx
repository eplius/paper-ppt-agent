import { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronRight, Terminal } from "lucide-react";
import { useLocale } from "../../i18n";
import { translateLogLine } from "../../lib/i18nStatus";
import type { CriticEvent } from "../../lib/types";

interface AgentLogProps {
  logs?: string[];
  criticEvents?: CriticEvent[];
}

export function AgentLog({ logs, criticEvents }: AgentLogProps) {
  const { t, locale } = useLocale();
  const safeLogs = Array.isArray(logs) ? logs : [];
  const safeCritic = Array.isArray(criticEvents) ? criticEvents : [];
  const summary = safeLogs.length === 0 ? t("log.summaryEmpty") : `${safeLogs.length} ${t("log.summaryCount")}`;

  const [criticOpen, setCriticOpen] = useState(false);
  const [expandedPages, setExpandedPages] = useState<Set<number>>(new Set());

  const togglePage = (page: number) => {
    setExpandedPages((prev) => {
      const next = new Set(prev);
      if (next.has(page)) {
        next.delete(page);
      } else {
        next.add(page);
      }
      return next;
    });
  };

  // Group critic events by page
  const criticByPage = new Map<number, CriticEvent[]>();
  for (const ev of safeCritic) {
    const existing = criticByPage.get(ev.page) ?? [];
    existing.push(ev);
    criticByPage.set(ev.page, existing);
  }
  const sortedPages = Array.from(criticByPage.keys()).sort((a, b) => a - b);

  const totalErrors = safeCritic.reduce((sum, ev) => sum + ev.report.error_count, 0);
  const totalWarnings = safeCritic.reduce((sum, ev) => sum + ev.report.warning_count, 0);

  return (
    <section className="panel">
      <div className="panel-header-row">
        <div>
          <div className="panel-title-row">
            <Terminal size={15} className="panel-title-icon" />
            <p className="panel-title">{t("log.title")}</p>
          </div>
          <p className="panel-support-text">{summary}</p>
        </div>
      </div>
      <div className="log-console">
        {safeLogs.length === 0 ? <p className="muted-copy">{t("log.empty")}</p> : null}
        {safeLogs.map((log, index) => (
          <p key={`${log}-${index}`} className="log-line">{translateLogLine(log, locale)}</p>
        ))}
      </div>
      {safeCritic.length > 0 ? (
        <div className="critic-section">
          <button
            type="button"
            className="critic-toggle"
            onClick={() => setCriticOpen((v) => !v)}
          >
            {criticOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            <AlertTriangle size={14} />
            <span>Critic 检查记录</span>
            <span className="critic-badge critic-badge-error">{totalErrors}</span>
            <span className="critic-badge critic-badge-warn">{totalWarnings}</span>
          </button>
          {criticOpen ? (
            <div className="critic-list">
              {sortedPages.map((page) => {
                const events = criticByPage.get(page) ?? [];
                const lastEvent = events[events.length - 1];
                const passed = lastEvent?.report.passed ?? true;
                const pageErrors = events.reduce((s, e) => s + e.report.error_count, 0);
                const pageWarnings = events.reduce((s, e) => s + e.report.warning_count, 0);
                const isExpanded = expandedPages.has(page);

                return (
                  <div key={page} className="critic-page">
                    <button
                      type="button"
                      className="critic-page-header"
                      onClick={() => togglePage(page)}
                    >
                      {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                      <span className="critic-page-label">Page {page}</span>
                      <span className={`critic-status ${passed ? "critic-status-pass" : "critic-status-fail"}`}>
                        {passed ? "PASS" : "FAIL"}
                      </span>
                      <span className="critic-attempts">{events.length} attempt{events.length > 1 ? "s" : ""}</span>
                      {pageErrors > 0 ? <span className="critic-badge critic-badge-error">{pageErrors} err</span> : null}
                      {pageWarnings > 0 ? <span className="critic-badge critic-badge-warn">{pageWarnings} warn</span> : null}
                    </button>
                    {isExpanded ? (
                      <div className="critic-attempts-list">
                        {events.map((ev, idx) => (
                          <div key={`${ev.page}-${ev.attempt}-${idx}`} className="critic-attempt">
                            <p className="critic-attempt-label">Attempt {ev.attempt}</p>
                            {ev.report.violations.length === 0 ? (
                              <p className="critic-no-violations">No violations</p>
                            ) : (
                              ev.report.violations.map((v, vi) => (
                                <div key={vi} className={`critic-violation critic-violation-${v.severity}`}>
                                  <span className="critic-violation-severity">{v.severity}</span>
                                  <span className="critic-violation-rule">{v.rule}</span>
                                  {v.element ? <span className="critic-violation-element">{v.element}</span> : null}
                                  <p className="critic-violation-detail">{v.detail}</p>
                                </div>
                              ))
                            )}
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
