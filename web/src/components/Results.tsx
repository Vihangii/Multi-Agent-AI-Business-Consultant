"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { fmtDate, fmtInt, fmtMoney, fmtPct } from "@/lib/format";
import type { AnalyzeResult } from "@/lib/types";
import { AgentActivity, AnomaliesCard } from "./AgentPanels";
import type { LastRun } from "./ConsultantApp";
import { ExportBar } from "./ExportAndSchedule";
import { ForecastChart } from "./ForecastChart";
import { Card, Metric, Notice, SectionTitle } from "./ui";
import { WhatIfTab } from "./WhatIfTab";

const TABS = [
  { id: "dashboard", label: "📊 Executive Dashboard" },
  { id: "forecast", label: "📈 Revenue Forecast" },
  { id: "whatif", label: "🎛️ What-if" },
  { id: "report", label: "🚀 Strategic AI Report" },
  { id: "data", label: "📋 Cleaned Data" },
] as const;
type TabId = (typeof TABS)[number]["id"];

export function Results({
  result,
  skipRecommendations,
  lastRun,
  file,
}: {
  result: AnalyzeResult;
  skipRecommendations: boolean;
  lastRun: LastRun | null;
  file: File | null;
  apiKey?: string;
}) {
  const [tab, setTab] = useState<TabId>("dashboard");

  return (
    <div className="space-y-4">
      <ExportBar result={result} lastRun={lastRun} file={file} />
      <div role="tablist" className="flex flex-wrap gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
              tab === t.id
                ? "border-accent text-text"
                : "border-transparent text-text-2 hover:text-text"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "dashboard" && <DashboardTab result={result} />}
      {tab === "forecast" && <ForecastTab result={result} />}
      {tab === "whatif" && <WhatIfTab result={result} />}
      {tab === "report" && (
        <ReportTab result={result} skipRecommendations={skipRecommendations} />
      )}
      {tab === "data" && <DataTab result={result} />}
    </div>
  );
}

// ---------------------------------------------------------------------------

function DashboardTab({ result }: { result: AnalyzeResult }) {
  const a = result.analysis;
  const fs = result.forecast_summary;

  const avgMonthly = a.monthly?.avg_monthly_revenue;
  const growth = a.growth?.overall_percent;
  const dir = a.growth?.direction ?? "n/a";
  const fGrowth = fs.predicted_growth_percent;

  return (
    <div className="space-y-4">
      <Card>
        <SectionTitle>📌 Key Performance Indicators</SectionTitle>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Metric label="Total Revenue" value={fmtMoney(a.revenue.total)} hint="Dataset cumulative revenue" />
          <Metric
            label={avgMonthly ? "Avg Monthly" : "Avg Per Record"}
            value={fmtMoney(avgMonthly ?? a.revenue.mean)}
            hint="Mean performance level"
          />
          <Metric
            label="Historical Growth"
            value={fmtPct(growth, { sign: true })}
            hint={`Overall trend: ${dir.toUpperCase()}`}
            tone={dir === "increasing" ? "good" : dir === "decreasing" ? "bad" : "muted"}
          />
          <Metric
            label="Forecast Outlook"
            value={fmtPct(fGrowth, { sign: true })}
            hint={`Trend: ${fs.forecast_trend.toUpperCase()} (${fs.forecast_periods} × '${fs.forecast_frequency}')`}
            tone={
              fs.forecast_trend === "upward"
                ? "good"
                : fs.forecast_trend === "downward"
                  ? "bad"
                  : "muted"
            }
          />
        </div>
      </Card>

      <Card>
        <SectionTitle>🔍 Data Processing & Detection Details</SectionTitle>
        <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
          <Row k="Detected date column" v={<code>{result.date_column}</code>} />
          <Row
            k="Date range"
            v={`${fmtDate(a.date_range.start)} → ${fmtDate(a.date_range.end)} (${fmtInt(a.date_range.span_days)} days)`}
          />
          <Row k="Detected revenue column" v={<code>{result.revenue_column}</code>} />
          <Row k="What-if driver" v={result.regressor_column ? <code>{result.regressor_column}</code> : "none"} />
          <Row k="Records (raw → cleaned)" v={`${fmtInt(result.raw_row_count)} → ${fmtInt(result.cleaned_row_count)}`} />
          <Row k="Granularity" v={fs.data_granularity} />
          <Row k="Pipeline time" v={`${result.elapsed_seconds.toFixed(1)} s`} />
        </dl>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <SectionTitle>💰 Revenue Statistics</SectionTitle>
          <dl className="grid grid-cols-2 gap-y-1.5 text-sm">
            <Row k="Mean" v={fmtMoney(a.revenue.mean)} />
            <Row k="Median" v={fmtMoney(a.revenue.median)} />
            <Row k="Std deviation" v={fmtMoney(a.revenue.std_dev)} />
            <Row k="Min" v={fmtMoney(a.revenue.min)} />
            <Row k="Max" v={fmtMoney(a.revenue.max)} />
            <Row k="Records" v={fmtInt(a.total_records)} />
          </dl>
        </Card>
        <Card>
          <SectionTitle>📆 Monthly Breakdown</SectionTitle>
          {a.monthly ? (
            <div className="space-y-2">
              <Notice tone="good">
                <b>Best month:</b> {a.monthly.best_month} ({fmtMoney(a.monthly.best_month_revenue)})
              </Notice>
              <Notice tone="warn">
                <b>Worst month:</b> {a.monthly.worst_month} ({fmtMoney(a.monthly.worst_month_revenue)})
              </Notice>
              {a.volatility && (
                <dl className="grid grid-cols-2 gap-y-1.5 pt-1 text-sm">
                  <Row k="Avg monthly change" v={fmtPct(a.volatility.avg_monthly_change_percent, { sign: true })} />
                  <Row k="Max monthly drop" v={fmtPct(a.volatility.max_monthly_drop_percent)} />
                  <Row k="Max monthly spike" v={fmtPct(a.volatility.max_monthly_spike_percent, { sign: true })} />
                </dl>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted">No monthly breakdown available.</p>
          )}
        </Card>
      </div>

      <AnomaliesCard anomalies={result.anomalies} />
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <>
      <dt className="text-text-2">{k}</dt>
      <dd className="tabular font-medium">{v}</dd>
    </>
  );
}

// ---------------------------------------------------------------------------

function ForecastTab({ result }: { result: AnalyzeResult }) {
  const fs = result.forecast_summary;
  const acc = fs.accuracy;

  return (
    <div className="space-y-4">
      <Card>
        <SectionTitle>📈 Revenue Projections (Prophet Forecasting)</SectionTitle>
        <ForecastChart
          forecast={result.forecast}
          actuals={result.cleaned_data}
          lastActualDate={fs.last_actual_date}
          anomalies={result.anomalies?.points}
        />
      </Card>

      <Card>
        <SectionTitle>🔮 Forecast Metrics & Peak Values</SectionTitle>
        <div className="grid gap-3 sm:grid-cols-3">
          <Metric label="Peak Forecasted Value" value={fmtMoney(fs.peak_forecasted_value)} hint={fmtDate(fs.peak_forecasted_date)} />
          <Metric label="Avg Forecasted Value" value={fmtMoney(fs.avg_forecasted_value)} hint={`over ${fs.forecast_periods} periods`} />
          <Metric
            label="Horizon End Value"
            value={fmtMoney(fs.forecast_end_value)}
            hint={`${fmtDate(fs.forecast_end_date)} · 95% CI ${fmtMoney(fs.confidence_interval.lower)} – ${fmtMoney(fs.confidence_interval.upper)}`}
          />
        </div>
      </Card>

      <Card>
        <SectionTitle>🎯 Model Accuracy (backtest)</SectionTitle>
        {acc ? (
          <>
            <p className="mb-3 text-sm text-text-2">
              The model was re-fit on the history before {fmtDate(acc.holdout_start)} and scored against
              the {fmtInt(acc.holdout_points)} actual points from {fmtDate(acc.holdout_start)} to{" "}
              {fmtDate(acc.holdout_end)}.
            </p>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <Metric label="MAPE" value={fmtPct(acc.mape_percent, { digits: 1 })} hint="Mean absolute % error — lower is better" />
              <Metric label="MAE" value={fmtMoney(acc.mae)} hint="Mean absolute error in revenue units" />
              <Metric
                label="95% Interval Coverage"
                value={fmtPct(acc.interval_coverage_percent, { digits: 0 })}
                hint="Held-out actuals inside the predicted band · ideal ≈ 95%"
              />
              <Metric
                label="Rating"
                value={acc.rating.charAt(0).toUpperCase() + acc.rating.slice(1)}
                hint={ratingHint(acc.rating)}
                tone={acc.rating === "excellent" || acc.rating === "good" ? "good" : acc.rating === "poor" ? "bad" : undefined}
              />
            </div>
          </>
        ) : (
          <p className="text-sm text-muted">
            Not enough history to run a backtest; accuracy metrics unavailable.
          </p>
        )}
      </Card>
    </div>
  );
}

function ratingHint(r: string): string {
  switch (r) {
    case "excellent":
      return "MAPE under 10%";
    case "good":
      return "MAPE 10–20%";
    case "fair":
      return "MAPE 20–50%";
    case "poor":
      return "MAPE over 50%";
    default:
      return "";
  }
}

// ---------------------------------------------------------------------------

function ReportTab({
  result,
  skipRecommendations,
}: {
  result: AnalyzeResult;
  skipRecommendations: boolean;
}) {
  const md = result.recommendations;

  return (
    <Card>
      <SectionTitle>🚀 Strategic Consultation Recommendations</SectionTitle>
      {md ? (
        <div className="space-y-4">
          <AgentActivity agent={result.agent} />
          <div className="prose-report text-sm">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{md}</ReactMarkdown>
          </div>
        </div>
      ) : result.recommendations_error ? (
        <Notice tone="bad">
          <div>The Strategist Agent could not generate a report: {result.recommendations_error}</div>
          <div className="mt-1 text-xs opacity-80">
            Configure a provider on the API server (OPENAI_API_KEY, ANTHROPIC_API_KEY, or OLLAMA_MODEL for a
            local model), then re-run the pipeline.
          </div>
        </Notice>
      ) : skipRecommendations ? (
        <Notice tone="warn">
          AI recommendations were skipped. Untick “Skip AI Recommendations” in the sidebar and re-run to generate them.
        </Notice>
      ) : (
        <Notice tone="bad">No consultation report was returned from the Recommendation Agent.</Notice>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------

function DataTab({ result }: { result: AnalyzeResult }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <SectionTitle>📋 Cleaned Data ({fmtInt(result.cleaned_data.length)} rows)</SectionTitle>
        <ScrollTable
          head={["Date", "Revenue"]}
          rows={result.cleaned_data.map((r) => [fmtDate(r.ds), fmtMoney(r.y)])}
        />
      </Card>
      <Card>
        <SectionTitle>🔮 Forecast Table ({fmtInt(result.forecast.length)} rows)</SectionTitle>
        <ScrollTable
          head={["Date", "Predicted", "Lower", "Upper"]}
          rows={result.forecast.map((r) => [
            fmtDate(r.ds),
            fmtMoney(r.predicted),
            fmtMoney(r.lower_bound),
            fmtMoney(r.upper_bound),
          ])}
        />
      </Card>
    </div>
  );
}

function ScrollTable({ head, rows }: { head: string[]; rows: string[][] }) {
  return (
    <div className="max-h-[520px] overflow-auto rounded-lg border border-border">
      <table className="min-w-full text-sm">
        <thead className="sticky top-0 bg-surface-2 text-left">
          <tr>
            {head.map((h) => (
              <th key={h} className="px-3 py-2 font-semibold">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-border">
              {r.map((c, j) => (
                <td key={j} className={`px-3 py-1.5 ${j > 0 ? "tabular text-right" : ""}`}>
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
