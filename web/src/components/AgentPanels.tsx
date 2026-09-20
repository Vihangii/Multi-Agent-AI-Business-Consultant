"use client";

import { useState } from "react";
import { fmtDate, fmtMoney, fmtPct } from "@/lib/format";
import type { AgentInfo, Anomalies } from "@/lib/types";
import { Card, Icon, Notice, SectionTitle } from "./ui";

// ---------------------------------------------------------------------------
// Anomalies (dashboard)
// ---------------------------------------------------------------------------

export function AnomaliesCard({ anomalies }: { anomalies: Anomalies | undefined }) {
  if (!anomalies) return null;
  const s = anomalies.summary;
  const none = anomalies.points.length === 0 && anomalies.periods.length === 0;

  return (
    <Card>
      <SectionTitle hint="Periods that departed sharply from the model's expectation">Anomaly agent</SectionTitle>
      {s.error ? (
        <Notice tone="warn">Anomaly detection failed: {s.error}</Notice>
      ) : none ? (
        <Notice tone="good">No significant anomalies — every period stayed within what the model expected.</Notice>
      ) : (
        <>
          <p className="mb-3 text-sm text-text-2">
            {s.point_count} anomalous data point{s.point_count === 1 ? "" : "s"} ({s.spike_count} spike
            {s.spike_count === 1 ? "" : "s"}, {s.drop_count} drop{s.drop_count === 1 ? "" : "s"};{" "}
            {s.anomalous_share_percent}% of history) and {s.period_count} monthly shock
            {s.period_count === 1 ? "" : "s"}. Detected from Prophet residuals with a robust z-score
            (|z| ≥ 3.5). The strategist decides for each whether it is a one-off to exclude or a signal to act on.
          </p>
          {anomalies.points.length > 0 && (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-surface-2 text-left">
                  <tr>
                    <th className="px-3 py-2">Date</th>
                    <th className="px-3 py-2">Type</th>
                    <th className="px-3 py-2 text-right">Actual</th>
                    <th className="px-3 py-2 text-right">Expected</th>
                    <th className="px-3 py-2 text-right">Deviation</th>
                    <th className="px-3 py-2 text-right">z</th>
                  </tr>
                </thead>
                <tbody>
                  {anomalies.points.map((p) => (
                    <tr key={p.date} className="border-t border-border">
                      <td className="px-3 py-1.5 tabular">{fmtDate(p.date)}</td>
                      <td className="px-3 py-1.5">
                        <span className={`rounded-md px-1.5 py-0.5 text-xs font-semibold ${p.severity === "high" ? "bg-bad-bg text-bad" : "bg-warn-bg text-warn"}`}>
                          {p.direction === "drop" ? "▼ drop" : "▲ spike"} · {p.severity}
                        </span>
                      </td>
                      <td className="px-3 py-1.5 tabular text-right">{fmtMoney(p.actual)}</td>
                      <td className="px-3 py-1.5 tabular text-right">{fmtMoney(p.expected)}</td>
                      <td className="px-3 py-1.5 tabular text-right">{fmtPct(p.deviation_percent, { sign: true, digits: 1 })}</td>
                      <td className="px-3 py-1.5 tabular text-right">{p.z_score}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {anomalies.periods.length > 0 && (
            <div className="mt-3 space-y-1">
              {anomalies.periods.map((q) => (
                <Notice key={q.period} tone={q.direction === "drop" ? "bad" : "warn"}>
                  <b>{q.period}</b>: {q.direction} of {fmtPct(q.change_percent, { sign: true, digits: 1 })} vs the previous month (
                  {fmtMoney(q.revenue)} vs {fmtMoney(q.previous_revenue)})
                </Notice>
              ))}
            </div>
          )}
        </>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Agent activity + QA (report tab)
// ---------------------------------------------------------------------------

function fmtArgs(args: Record<string, unknown>): string {
  const entries = Object.entries(args);
  if (entries.length === 0) return "()";
  return "(" + entries.map(([k, v]) => `${k}=${typeof v === "string" ? `"${v}"` : String(v)}`).join(", ") + ")";
}

export function AgentActivity({ agent }: { agent: AgentInfo | undefined }) {
  const [open, setOpen] = useState(false);
  if (!agent) return null;
  const qa = agent.qa;
  const qaTone = qa.status === "passed" ? "good" : qa.status === "corrected" ? "warn" : "info";
  const qaLabel =
    qa.status === "passed"
      ? "Critic verified every figure — no corrections needed."
      : qa.status === "corrected"
        ? `Critic corrected ${qa.corrections} claim${qa.corrections === 1 ? "" : "s"}.`
        : qa.status === "unverified"
          ? `Critic could not verify the report${qa.note ? ` (${qa.note})` : ""}.`
          : "Critic pass was skipped.";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded-md border border-border bg-surface-2 px-2 py-1">
          <Icon name="sparkle" size={12} /> {agent.provider} · <span className="font-mono">{agent.model}</span>
        </span>
        <span className="rounded-md border border-border bg-surface-2 px-2 py-1">
          {agent.mode === "tools"
            ? `${agent.tool_calls.length} tool call${agent.tool_calls.length === 1 ? "" : "s"} in ${agent.rounds} round${agent.rounds === 1 ? "" : "s"}`
            : "static prompt (no tools)"}
        </span>
        {agent.usage?.input_tokens != null && (
          <span className="rounded-md border border-border bg-surface-2 px-2 py-1 tabular">
            {agent.usage.input_tokens?.toLocaleString()} in / {agent.usage.output_tokens?.toLocaleString()} out tokens
          </span>
        )}
        {agent.tool_calls.length > 0 && (
          <button type="button" onClick={() => setOpen((o) => !o)} className="rounded-md border border-border px-2 py-1 hover:bg-surface-2">
            {open ? "Hide" : "Show"} agent activity
          </button>
        )}
      </div>

      {open && (
        <ol className="space-y-1 rounded-lg border border-border bg-surface-2/50 p-3 text-xs">
          {agent.tool_calls.map((t, i) => (
            <li key={i} className="grid grid-cols-[1.5rem_1fr] gap-1">
              <span className="text-muted tabular">{i + 1}.</span>
              <div className="min-w-0">
                <code className="font-semibold">{t.tool}</code>
                <span className="text-text-2">{fmtArgs(t.arguments)}</span>
                <span className="ml-2 text-muted">{t.ms} ms</span>
                <div className="truncate font-mono text-[11px] text-muted" title={t.result_preview}>
                  → {t.result_preview}
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}

      <Notice tone={qaTone}>
        <div className="font-medium">Critic QA · {qaLabel}</div>
        {qa.issues.length > 0 && (
          <ul className="mt-1 list-disc space-y-1 pl-5 text-xs">
            {qa.issues.map((i, k) => (
              <li key={k}>
                <span className="line-through opacity-70">{i.claim}</span> → <b>{i.correct_value}</b>
                {i.section && <span className="text-muted"> ({i.section})</span>}
              </li>
            ))}
          </ul>
        )}
      </Notice>
    </div>
  );
}
