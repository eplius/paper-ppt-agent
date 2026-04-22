import { Terminal } from "lucide-react";
import { useLocale } from "../../i18n";

interface AgentLogProps {
  logs?: string[];
}

export function AgentLog({ logs }: AgentLogProps) {
  const { t } = useLocale();
  const safeLogs = Array.isArray(logs) ? logs : [];
  const summary = safeLogs.length === 0 ? t("log.summaryEmpty") : `${safeLogs.length} ${t("log.summaryCount")}`;
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
          <p key={`${log}-${index}`} className="log-line">{log}</p>
        ))}
      </div>
    </section>
  );
}
