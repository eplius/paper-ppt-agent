import { useEffect, useMemo, useState } from "react";
import { Layout } from "../components/layout/Layout";
import { useLocale } from "../i18n";
import { fetchUsageSnapshot } from "../lib/api";
import { openUsageSocket } from "../lib/ws";

interface DailyRow {
  day: string;
  calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

interface ModelRow {
  model: string;
  calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

interface StageRow {
  stage: string;
  calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

interface UsageRecord {
  ts: string;
  day: string;
  provider: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  job_id: string | null;
  stage: string | null;
  page: number | null;
  attempt: number;
  duration_ms: number;
}

interface Summary {
  total_calls: number;
  total_prompt: number;
  total_completion: number;
  total_tokens: number;
}

const EMPTY_SUMMARY: Summary = {
  total_calls: 0,
  total_prompt: 0,
  total_completion: 0,
  total_tokens: 0,
};

function formatNumber(n: number): string {
  return new Intl.NumberFormat().format(n);
}

function BarChart({ rows, keyField, valueField, max }: {
  rows: Array<Record<string, unknown>>;
  keyField: string;
  valueField: string;
  max: number;
}) {
  if (rows.length === 0) {
    return <p className="muted-copy">No data yet.</p>;
  }
  return (
    <div className="logs-bars">
      {rows.map((row, idx) => {
        const value = Number(row[valueField] ?? 0);
        const pct = max > 0 ? (value / max) * 100 : 0;
        return (
          <div key={idx} className="logs-bar-row">
            <span className="logs-bar-label" title={String(row[keyField])}>
              {String(row[keyField])}
            </span>
            <div className="logs-bar-track">
              <div className="logs-bar-fill" style={{ width: `${pct}%` }} />
            </div>
            <span className="logs-bar-value">{formatNumber(value)}</span>
          </div>
        );
      })}
    </div>
  );
}

export function LogsPage() {
  const { t, locale } = useLocale();
  const [summary, setSummary] = useState<Summary>(EMPTY_SUMMARY);
  const [daily, setDaily] = useState<DailyRow[]>([]);
  const [byModel, setByModel] = useState<ModelRow[]>([]);
  const [byStage, setByStage] = useState<StageRow[]>([]);
  const [records, setRecords] = useState<UsageRecord[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let disposed = false;
    let hydratedFromSocket = false;

    fetchUsageSnapshot()
      .then((snapshot) => {
        if (disposed || hydratedFromSocket) {
          return;
        }
        setSummary(snapshot.summary ?? EMPTY_SUMMARY);
        setDaily(snapshot.daily ?? []);
        setByModel(snapshot.by_model ?? []);
        setByStage(snapshot.by_stage ?? []);
        setRecords(snapshot.recent ?? []);
      })
      .catch(() => {
        // Keep the page usable even if the realtime socket is unavailable.
      });

    const socket = openUsageSocket(
      (event) => {
        if (event.type === "snapshot") {
          hydratedFromSocket = true;
          setSummary((event.summary as Summary) ?? EMPTY_SUMMARY);
          setDaily((event.daily as DailyRow[]) ?? []);
          setByModel((event.by_model as ModelRow[]) ?? []);
          setByStage((event.by_stage as StageRow[]) ?? []);
          setRecords((event.recent as UsageRecord[]) ?? []);
          return;
        }
        if (event.type === "usage") {
          const rec = event.record as UsageRecord;
          setRecords((prev) => [rec, ...prev].slice(0, 200));
          setSummary((prev) => ({
            total_calls: prev.total_calls + 1,
            total_prompt: prev.total_prompt + rec.prompt_tokens,
            total_completion: prev.total_completion + rec.completion_tokens,
            total_tokens: prev.total_tokens + rec.total_tokens,
          }));
          setByModel((prev) => mergeRow(prev, "model", rec.model, rec));
          setByStage((prev) =>
            mergeRow(prev, "stage", rec.stage ?? "(unknown)", rec),
          );
          setDaily((prev) => mergeRow(prev, "day", rec.day, rec));
        }
      },
      () => setConnected(true),
      () => setConnected(false),
    );

    return () => {
      disposed = true;
      socket.close();
    };
  }, []);

  const maxDaily = useMemo(
    () => Math.max(1, ...daily.map((d) => d.total_tokens)),
    [daily],
  );
  const maxModel = useMemo(
    () => Math.max(1, ...byModel.map((d) => d.total_tokens)),
    [byModel],
  );
  const maxStage = useMemo(
    () => Math.max(1, ...byStage.map((d) => d.total_tokens)),
    [byStage],
  );

  const formatter = new Intl.DateTimeFormat(locale === "zh" ? "zh-CN" : "en-US", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  return (
    <Layout>
      <section className="logs-page">
        <header className="logs-header">
          <h1>{t("logs.title")}</h1>
          <p className="muted-copy">
            {t("logs.subtitle")}
            <span
              className={`logs-status ${connected ? "logs-status-on" : "logs-status-off"}`}
            >
              {connected ? t("logs.live") : t("logs.offline")}
            </span>
          </p>
        </header>

        <section className="logs-summary">
          <SummaryCard label={t("logs.calls")} value={summary.total_calls} />
          <SummaryCard label={t("logs.promptTokens")} value={summary.total_prompt} />
          <SummaryCard label={t("logs.completionTokens")} value={summary.total_completion} />
          <SummaryCard label={t("logs.totalTokens")} value={summary.total_tokens} />
        </section>

        <section className="logs-grid">
          <article className="logs-card">
            <h2>{t("logs.dailyTitle")}</h2>
            <BarChart
              rows={daily as unknown as Array<Record<string, unknown>>}
              keyField="day"
              valueField="total_tokens"
              max={maxDaily}
            />
          </article>
          <article className="logs-card">
            <h2>{t("logs.byModel")}</h2>
            <BarChart
              rows={byModel as unknown as Array<Record<string, unknown>>}
              keyField="model"
              valueField="total_tokens"
              max={maxModel}
            />
          </article>
          <article className="logs-card">
            <h2>{t("logs.byStage")}</h2>
            <BarChart
              rows={byStage as unknown as Array<Record<string, unknown>>}
              keyField="stage"
              valueField="total_tokens"
              max={maxStage}
            />
          </article>
        </section>

        <section className="logs-card">
          <h2>{t("logs.recent")}</h2>
          <div className="logs-table-wrap">
            <table className="logs-table">
              <thead>
                <tr>
                  <th>{t("logs.time")}</th>
                  <th>{t("logs.provider")}</th>
                  <th>{t("logs.model")}</th>
                  <th>{t("logs.stage")}</th>
                  <th>{t("logs.job")}</th>
                  <th>{t("logs.page")}</th>
                  <th>{t("logs.attempt")}</th>
                  <th>{t("logs.promptTokens")}</th>
                  <th>{t("logs.completionTokens")}</th>
                  <th>{t("logs.totalTokens")}</th>
                  <th>ms</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r, idx) => (
                  <tr key={`${r.ts}-${idx}`}>
                    <td>{formatter.format(new Date(r.ts))}</td>
                    <td>{r.provider}</td>
                    <td>{r.model}</td>
                    <td>{r.stage ?? "-"}</td>
                    <td title={r.job_id ?? ""}>
                      {r.job_id ? r.job_id.slice(0, 8) : "-"}
                    </td>
                    <td>{r.page ?? "-"}</td>
                    <td>{r.attempt}</td>
                    <td>{formatNumber(r.prompt_tokens)}</td>
                    <td>{formatNumber(r.completion_tokens)}</td>
                    <td>{formatNumber(r.total_tokens)}</td>
                    <td>{r.duration_ms}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </section>
    </Layout>
  );
}

function SummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="logs-summary-card">
      <span className="logs-summary-label">{label}</span>
      <span className="logs-summary-value">{formatNumber(value)}</span>
    </div>
  );
}

function mergeRow<T>(
  prev: T[],
  keyField: string,
  keyValue: string,
  rec: UsageRecord,
): T[] {
  const idx = prev.findIndex((r) => (r as Record<string, unknown>)[keyField] === keyValue);
  if (idx === -1) {
    return [
      {
        [keyField]: keyValue,
        calls: 1,
        prompt_tokens: rec.prompt_tokens,
        completion_tokens: rec.completion_tokens,
        total_tokens: rec.total_tokens,
      } as unknown as T,
      ...prev,
    ];
  }
  const row = prev[idx] as unknown as {
    calls: number;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  const next = [...prev];
  next[idx] = {
    ...prev[idx],
    calls: row.calls + 1,
    prompt_tokens: row.prompt_tokens + rec.prompt_tokens,
    completion_tokens: row.completion_tokens + rec.completion_tokens,
    total_tokens: row.total_tokens + rec.total_tokens,
  } as unknown as T;
  return next;
}
