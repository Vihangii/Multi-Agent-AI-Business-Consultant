"use client";

import { useMemo } from "react";
import {
  Area,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fmtDate, fmtDateShort, fmtMoney, fmtMoneyCompact } from "@/lib/format";
import type { AnomalyPoint, CleanedPoint, ForecastPoint } from "@/lib/types";

interface Row {
  t: number; // epoch ms
  predicted: number;
  lower: number;
  upper: number;
  band: [number, number];
  actual?: number;
  anomaly?: number; // actual value, only on anomalous days
  anomalyInfo?: AnomalyPoint;
}

interface Props {
  forecast: ForecastPoint[];
  actuals: CleanedPoint[];
  lastActualDate: string;
  anomalies?: AnomalyPoint[];
}

const SERIES = {
  forecast: "var(--series-forecast)",
  actual: "var(--series-actual)",
  anomaly: "var(--bad)",
};

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: Row }[];
}) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2 text-xs shadow-lg">
      <div className="mb-1 font-semibold">{fmtDate(new Date(r.t).toISOString())}</div>
      {r.actual !== undefined && (
        <div className="flex items-center gap-2">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: SERIES.actual }} />
          <span className="text-text-2">Actual</span>
          <span className="ml-auto tabular font-medium">{fmtMoney(r.actual)}</span>
        </div>
      )}
      <div className="flex items-center gap-2">
        <span className="inline-block h-2 w-2 rounded-full" style={{ background: SERIES.forecast }} />
        <span className="text-text-2">Forecast</span>
        <span className="ml-auto tabular font-medium">{fmtMoney(r.predicted)}</span>
      </div>
      <div className="mt-1 text-muted">
        95% interval {fmtMoney(r.lower)} – {fmtMoney(r.upper)}
      </div>
      {r.anomalyInfo && (
        <div className="mt-1 font-medium text-bad">
          ⚠ Anomaly: {r.anomalyInfo.direction} of {r.anomalyInfo.deviation_percent?.toFixed(1)}% (z = {r.anomalyInfo.z_score})
        </div>
      )}
    </div>
  );
}

export function ForecastChart({ forecast, actuals, lastActualDate, anomalies }: Props) {
  const rows = useMemo<Row[]>(() => {
    // Key by calendar date (YYYY-MM-DD), not epoch ms: the API sends actuals as
    // "2024-09-07T00:00:00" (parsed as local time) and anomaly dates as
    // "2024-09-07" (parsed as UTC), which differ by the timezone offset.
    const day = (iso: string) => iso.slice(0, 10);
    const actualByDay = new Map<string, number>();
    for (const a of actuals) {
      actualByDay.set(day(a.ds), a.y);
    }
    const anomalyByDay = new Map<string, AnomalyPoint>();
    for (const a of anomalies ?? []) {
      anomalyByDay.set(day(a.date), a);
    }
    return forecast.map((f) => {
      const t = new Date(f.ds).getTime();
      const key = day(f.ds);
      const lower = Math.max(0, f.lower_bound);
      const info = anomalyByDay.get(key);
      return {
        t,
        predicted: f.predicted,
        lower,
        upper: f.upper_bound,
        band: [lower, f.upper_bound],
        actual: actualByDay.get(key),
        anomaly: info ? actualByDay.get(key) : undefined,
        anomalyInfo: info,
      };
    });
  }, [forecast, actuals, anomalies]);

  const splitT = new Date(lastActualDate).getTime();

  return (
    <div className="h-[420px] w-full">
      <ResponsiveContainer>
        <ComposedChart data={rows} margin={{ top: 12, right: 16, bottom: 4, left: 8 }}>
          <XAxis
            dataKey="t"
            type="number"
            domain={["dataMin", "dataMax"]}
            scale="time"
            tickFormatter={(v) => fmtDateShort(new Date(v).toISOString())}
            tick={{ fill: "var(--muted)", fontSize: 11 }}
            axisLine={{ stroke: "var(--axis)" }}
            tickLine={false}
            minTickGap={40}
          />
          <YAxis
            tickFormatter={(v) => fmtMoneyCompact(v)}
            tick={{ fill: "var(--muted)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={64}
          />
          <Tooltip
            content={<CustomTooltip />}
            cursor={{ stroke: "var(--axis)", strokeDasharray: "3 3" }}
          />
          <Legend
            verticalAlign="top"
            align="right"
            iconType="plainline"
            wrapperStyle={{ fontSize: 12, color: "var(--text-2)", paddingBottom: 8 }}
          />
          <Area
            name="95% confidence interval"
            dataKey="band"
            type="monotone"
            stroke="none"
            fill={SERIES.forecast}
            fillOpacity={0.14}
            isAnimationActive
            animationDuration={900}
            animationEasing="ease-out"
            legendType="rect"
          />
          <Line
            name="Forecast"
            dataKey="predicted"
            type="monotone"
            stroke={SERIES.forecast}
            strokeWidth={2}
            dot={false}
            isAnimationActive
            animationDuration={1100}
            animationEasing="ease-out"
          />
          <Scatter
            name="Actual"
            dataKey="actual"
            fill={SERIES.actual}
            shape={(p: { cx?: number; cy?: number }) =>
              p.cx != null && p.cy != null ? (
                <circle cx={p.cx} cy={p.cy} r={3} fill={SERIES.actual} fillOpacity={0.8} />
              ) : (
                <g />
              )
            }
            isAnimationActive={false}
            legendType="circle"
          />
          {anomalies && anomalies.length > 0 && (
            <Scatter
              name="Anomaly"
              dataKey="anomaly"
              shape={(p: { cx?: number; cy?: number }) =>
                p.cx != null && p.cy != null ? (
                  <g>
                    <circle cx={p.cx} cy={p.cy} r={7} fill="none" stroke={SERIES.anomaly} strokeWidth={2} />
                    <circle cx={p.cx} cy={p.cy} r={3} fill={SERIES.anomaly} />
                  </g>
                ) : (
                  <g />
                )
              }
              isAnimationActive={false}
              legendType="circle"
            />
          )}
          <ReferenceLine
            x={splitT}
            stroke="var(--muted)"
            strokeDasharray="4 4"
            label={{
              value: "forecast →",
              position: "insideTopRight",
              fill: "var(--muted)",
              fontSize: 11,
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
