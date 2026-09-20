"use client";

import { useMemo, useState } from "react";
import {
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fmtDate, fmtMoney, fmtMoneyCompact, fmtPct } from "@/lib/format";
import type { AnalyzeResult, WhatIfScenario } from "@/lib/types";
import { Card, Metric, Notice, SectionTitle } from "./ui";

export function WhatIfTab({ result }: { result: AnalyzeResult }) {
  const w = result.whatif;
  const steps = w?.steps ?? [];
  const [idx, setIdx] = useState(() => Math.max(0, steps.indexOf(0)));

  const scenarios = useMemo(() => {
    const m = new Map<number, WhatIfScenario>();
    w?.scenarios.forEach((s) => m.set(s.change_percent, s));
    return m;
  }, [w]);

  if (!w || steps.length === 0) {
    return (
      <Card>
        <Notice tone="info">No what-if scenarios were returned for this run.</Notice>
      </Card>
    );
  }

  const pct = steps[idx] ?? 0;
  const base = scenarios.get(0)!;
  const sc = scenarios.get(pct) ?? base;
  const driverLabel = w.driver ?? "revenue uplift";

  const rows = base.series.map((p, i) => ({
    t: new Date(p.ds).getTime(),
    baseline: p.predicted,
    scenario: sc.series[i]?.predicted ?? p.predicted,
  }));

  return (
    <div className="space-y-4">
      <Card>
        <SectionTitle>What-if: change {driverLabel} by…</SectionTitle>
        {w.method === "regressor" ? (
          <p className="mb-3 text-sm text-text-2">
            The model was fit with <code>{w.driver}</code> as a Prophet regressor, so these
            scenarios reflect the relationship it learned from your data (current level ≈{" "}
            {w.baseline_driver_value?.toLocaleString()} per period). Each step re-predicts the
            forecast with the future driver scaled by the chosen percentage.
          </p>
        ) : (
          <Notice tone="info" className="mb-3">
            No driver column was selected, so this is a <b>simple uplift</b> applied to the forecast —
            useful as a target, not a prediction. Pick a numeric column such as marketing spend in
            the sidebar (“What-if driver”) and re-run to get scenarios learned from your data.
          </Notice>
        )}

        <div className="flex items-center gap-4">
          <span className="w-14 text-right text-sm tabular text-text-2">{steps[0]}%</span>
          <input
            type="range"
            min={0}
            max={steps.length - 1}
            step={1}
            value={idx}
            onChange={(e) => setIdx(Number(e.target.value))}
            className="flex-1 accent-accent"
            aria-label="Scenario percentage"
          />
          <span className="w-14 text-sm tabular text-text-2">+{steps[steps.length - 1]}%</span>
        </div>
        <div className="mt-2 flex flex-wrap gap-1">
          {steps.map((s, i) => (
            <button
              key={s}
              type="button"
              onClick={() => setIdx(i)}
              className={`rounded-md border px-2 py-0.5 text-xs tabular ${
                i === idx ? "border-accent bg-accent-soft font-semibold" : "border-border text-text-2 hover:bg-surface-2"
              }`}
            >
              {s > 0 ? `+${s}` : s}%
            </button>
          ))}
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Metric
            label={`Scenario (${pct > 0 ? "+" : ""}${pct}%)`}
            value={fmtMoney(sc.total_forecasted)}
            hint="Total forecasted revenue over the horizon"
          />
          <Metric label="Baseline" value={fmtMoney(base.total_forecasted)} hint="Total at current level" />
          <Metric
            label="Difference"
            value={`${sc.delta_vs_baseline >= 0 ? "+" : ""}${fmtMoney(sc.delta_vs_baseline)}`}
            hint={fmtPct(sc.delta_vs_baseline_percent, { sign: true })}
            tone={sc.delta_vs_baseline > 0 ? "good" : sc.delta_vs_baseline < 0 ? "bad" : "muted"}
          />
          <Metric
            label="Horizon end value"
            value={fmtMoney(sc.forecast_end_value)}
            hint={w.driver && sc.driver_value != null ? `${w.driver} ≈ ${sc.driver_value.toLocaleString()}` : "per period"}
          />
        </div>
      </Card>

      <Card>
        <SectionTitle>Baseline vs scenario</SectionTitle>
        <div className="h-[340px] w-full">
          <ResponsiveContainer>
            <LineChart data={rows} margin={{ top: 12, right: 16, bottom: 4, left: 8 }}>
              <XAxis
                dataKey="t"
                type="number"
                domain={["dataMin", "dataMax"]}
                scale="time"
                tickFormatter={(v) =>
                  new Date(v).toLocaleDateString("en-US", { month: "short", day: "numeric" })
                }
                tick={{ fill: "var(--muted)", fontSize: 11 }}
                axisLine={{ stroke: "var(--axis)" }}
                tickLine={false}
                minTickGap={56}
              />
              <YAxis
                tickFormatter={(v) => fmtMoneyCompact(v)}
                tick={{ fill: "var(--muted)", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                width={64}
              />
              <Tooltip
                cursor={{ stroke: "var(--axis)", strokeDasharray: "3 3" }}
                contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
                labelFormatter={(v) => fmtDate(new Date(Number(v)).toISOString())}
                formatter={(v) => fmtMoney(Number(v))}
              />
              <Legend verticalAlign="top" align="right" iconType="plainline" wrapperStyle={{ fontSize: 12, paddingBottom: 8 }} />
              <Line name="Baseline" dataKey="baseline" stroke="var(--series-forecast)" strokeWidth={2} dot={false} isAnimationActive animationDuration={700} />
              <Line
                name={`Scenario ${pct > 0 ? "+" : ""}${pct}%`}
                dataKey="scenario"
                stroke="var(--series-actual)"
                strokeWidth={2}
                strokeDasharray={pct === 0 ? "2 4" : undefined}
                dot={false}
                isAnimationActive
                animationDuration={500}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card>
        <SectionTitle>All scenarios</SectionTitle>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-surface-2 text-left">
              <tr>
                <th className="px-3 py-2">Change</th>
                {w.driver && <th className="px-3 py-2 text-right">{w.driver}</th>}
                <th className="px-3 py-2 text-right">Total forecast</th>
                <th className="px-3 py-2 text-right">vs baseline</th>
                <th className="px-3 py-2 text-right">Horizon end</th>
              </tr>
            </thead>
            <tbody>
              {w.scenarios.map((s) => (
                <tr
                  key={s.change_percent}
                  className={`border-t border-border ${s.change_percent === pct ? "bg-accent-soft/40" : ""}`}
                >
                  <td className="px-3 py-1.5 tabular">{s.change_percent > 0 ? "+" : ""}{s.change_percent}%</td>
                  {w.driver && <td className="px-3 py-1.5 tabular text-right">{s.driver_value?.toLocaleString()}</td>}
                  <td className="px-3 py-1.5 tabular text-right">{fmtMoney(s.total_forecasted)}</td>
                  <td className="px-3 py-1.5 tabular text-right">{fmtPct(s.delta_vs_baseline_percent, { sign: true })}</td>
                  <td className="px-3 py-1.5 tabular text-right">{fmtMoney(s.forecast_end_value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
