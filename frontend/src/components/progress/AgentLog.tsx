import { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronRight, Eye, Terminal } from "lucide-react";
import { useLocale } from "../../i18n";
import { translateLogLine } from "../../lib/i18nStatus";
import type { CriticEvent } from "../../lib/types";

function buildArchiveUrl(archivePath: string, jobId?: string): string | null {
  if (!jobId || !archivePath) return null;
  const filename = archivePath.split("/").pop();
  if (!filename) return null;
  return `/api/critic-archive/${jobId}/${filename}`;
}

interface AgentLogProps {
  logs?: string[];
  criticEvents?: CriticEvent[];
  jobId?: string;
}

export function AgentLog({ logs, criticEvents, jobId }: AgentLogProps) {
  const { t, locale } = useLocale();
  const safeLogs = Array.isArray(logs) ? logs : [];
  const safeCritic = Array.isArray(criticEvents) ? criticEvents : [];
  const summary = safeLogs.length === 0 ? t("log.summaryEmpty") : `${safeLogs.length} ${t("log.summaryCount")}`;

  const [criticOpen, setCriticOpen] = useState(false);
  const [expandedPages, setExpandedPages] = useState<Set<number>>(new Set());
  const [expandedPrompts, setExpandedPrompts] = useState<Set<string>>(new Set());

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

  const togglePrompt = (key: string) => {
    setExpandedPrompts((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
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
                            {ev.repair_prompt ? (
                              <div className="critic-repair">
                                <button
                                  type="button"
                                  className="critic-repair-toggle"
                                  onClick={() => togglePrompt(`${ev.page}-${ev.attempt}`)}
                                >
                                  {expandedPrompts.has(`${ev.page}-${ev.attempt}`) ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                                  Repair Prompt
                                </button>
                                {expandedPrompts.has(`${ev.page}-${ev.attempt}`) ? (
                                  <pre className="critic-repair-text">{ev.repair_prompt}</pre>
                                ) : null}
                              </div>
                            ) : null}
                            {ev.archive_path && jobId ? (
                              <a
                                className="critic-archive-link"
                                href={buildArchiveUrl(ev.archive_path, jobId) ?? "#"}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                <Eye size={11} />
                                View pre-repair SVG
                              </a>
                            ) : null}
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
