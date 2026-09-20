"use client";

import Link from "next/link";
import { AppShell } from "./AppShell";
import { Badge, Button, Icon } from "./ui";

const STEPS = [
  {
    n: "01",
    title: "Data Agent",
    text: "Finds your date and revenue columns, cleans currency strings and duplicates, and computes growth, monthly and volatility statistics.",
    icon: "file",
  },
  {
    n: "02",
    title: "Forecast Agent",
    text: "Fits a Prophet model (optionally with a driver like marketing spend), backtests it, and precomputes what-if scenarios.",
    icon: "chart",
  },
  {
    n: "03",
    title: "Anomaly Agent",
    text: "Scores every period against the model's expectation and flags collapses and spikes for the strategist to explain or exclude.",
    icon: "alert",
  },
  {
    n: "04",
    title: "Strategist Agent",
    text: "A tool-using LLM queries the data — months, comparisons, weekday profile, scenarios — before writing a prioritised plan.",
    icon: "sparkle",
  },
  {
    n: "05",
    title: "Critic Agent",
    text: "A second model fact-checks every figure against the numbers, rewrites wrong claims and lists what it corrected.",
    icon: "shield",
  },
];

const FEATURES = [
  { icon: "chart", title: "Honest forecasting", text: "Every forecast ships with its own backtest: MAPE, MAE and interval coverage on held-out history." },
  { icon: "bolt", title: "What-if scenarios", text: "Pick a driver column and the model learns its effect — slide −30…+50% and see revenue respond." },
  { icon: "sparkle", title: "Agents that check their work", text: "The strategist queries your data with tools; the critic audits the report before you see it." },
  { icon: "download", title: "Boardroom-ready exports", text: "One click to PDF or PowerPoint with a native editable chart, KPIs, scenarios and the full report." },
  { icon: "mail", title: "Monthly re-runs by email", text: "Schedule it once and get a fresh forecast and recommendations on the 1st of every month." },
  { icon: "shield", title: "Your model, your choice", text: "Runs on OpenAI, Anthropic Claude, or a fully local Ollama model — swap with one setting." },
];

export function Landing() {
  return (
    <AppShell>
      {/* Hero */}
      <section className="bg-dots border-b border-border">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:py-24">
          <div className="max-w-3xl animate-fade-up">
            <Badge tone="accent" className="mb-5">
              <Icon name="sparkle" size={11} /> Five agents · one upload
            </Badge>
            <h1 className="text-4xl font-semibold leading-[1.1] tracking-tight sm:text-6xl">
              Turn a sales spreadsheet into a{" "}
              <span className="bg-gradient-to-r from-[#2a78d6] to-[#1baf7a] bg-clip-text text-transparent">
                fact-checked strategy
              </span>
              .
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-relaxed text-text-2">
              Upload a CSV or Excel file. Get a cleaned dataset, a Prophet revenue forecast with accuracy scores and
              what-if scenarios, and a strategy report written by an AI agent that queries your data and is audited by
              a second one — exportable to PDF or PowerPoint.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link href="/app">
                <Button variant="primary" size="lg">
                  Open the workspace <Icon name="arrow" size={16} />
                </Button>
              </Link>
              <a href="#how-it-works">
                <Button variant="secondary" size="lg">
                  See how it works
                </Button>
              </a>
              <span className="text-sm text-muted">No account needed · works without an API key</span>
            </div>
          </div>

          {/* Faux product frame */}
          <div className="mt-14 animate-fade-up rounded-2xl border border-border bg-surface p-2 shadow-hero">
            <div className="rounded-xl border border-border bg-surface-2 p-4 sm:p-6">
              <div className="grid gap-3 sm:grid-cols-4">
                {[
                  ["Total revenue", "$777,075", "912 records"],
                  ["Historical growth", "+134.1%", "increasing"],
                  ["Forecast outlook", "+8.7%", "upward · 180 × D"],
                  ["Backtest MAPE", "5.1%", "rated excellent"],
                ].map(([l, v, h]) => (
                  <div key={l} className="rounded-lg border border-border bg-surface px-4 py-3">
                    <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted">{l}</div>
                    <div className="mt-1 text-2xl font-semibold tracking-tight tabular">{v}</div>
                    <div className="mt-1 text-xs text-muted">{h}</div>
                  </div>
                ))}
              </div>
              <div className="mt-3 grid gap-3 lg:grid-cols-[2fr_1fr]">
                <div className="rounded-lg border border-border bg-surface p-4">
                  <div className="mb-2 text-xs font-medium text-text-2">Revenue forecast</div>
                  <MiniChart />
                </div>
                <div className="rounded-lg border border-border bg-surface p-4 text-xs">
                  <div className="mb-2 font-medium text-text-2">Agent activity</div>
                  <ol className="space-y-1.5 font-mono text-[11px] text-muted">
                    <li><span className="text-text">get_monthly_breakdown</span>(last_n=12)</li>
                    <li><span className="text-text">get_anomalies</span>()</li>
                    <li><span className="text-text">what_if</span>(change_percent=15)</li>
                    <li><span className="text-text">get_weekday_profile</span>()</li>
                  </ol>
                  <div className="mt-3 rounded-md border border-warn/30 bg-warn-bg px-2.5 py-2 text-warn">
                    <b>QA</b> · Critic corrected 1 claim: <s>12% growth</s> → 8.7%
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="mx-auto max-w-7xl px-4 py-16 sm:py-20">
        <div className="max-w-2xl">
          <h2 className="text-3xl font-semibold tracking-tight">How it works</h2>
          <p className="mt-3 text-text-2">
            Five specialised agents run in sequence. Each has one job and a clear contract, so a failure in the AI
            stage never takes the analysis down with it.
          </p>
        </div>
        <ol className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {STEPS.map((s) => (
            <li key={s.n} className="rounded-2xl border border-border bg-surface p-5 shadow-card">
              <div className="flex items-center justify-between">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-soft text-accent">
                  <Icon name={s.icon} size={18} />
                </span>
                <span className="text-xs font-semibold tabular text-muted">{s.n}</span>
              </div>
              <h3 className="mt-4 font-semibold">{s.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-text-2">{s.text}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Features */}
      <section className="border-t border-border bg-surface">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:py-20">
          <div className="max-w-2xl">
            <h2 className="text-3xl font-semibold tracking-tight">Built for decisions, not demos</h2>
            <p className="mt-3 text-text-2">Everything a business owner needs to trust a number and act on it.</p>
          </div>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title} className="flex gap-4 rounded-2xl border border-border bg-page p-5">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent">
                  <Icon name={f.icon} size={18} />
                </span>
                <div>
                  <h3 className="font-semibold">{f.title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-text-2">{f.text}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-7xl px-4 py-16 sm:py-20">
        <div className="rounded-2xl bg-gradient-to-br from-[#1e3a8a] via-[#2a78d6] to-[#1baf7a] p-8 text-white shadow-hero sm:p-12">
          <h2 className="text-3xl font-semibold tracking-tight">Try it with the sample dataset</h2>
          <p className="mt-2 max-w-xl text-white/85">
            The workspace ships with a synthetic 30-month sales file. Upload it, run the pipeline, and export the
            report — about a minute end to end.
          </p>
          <Link href="/app" className="mt-6 inline-block">
            <Button size="lg" className="bg-white text-[#1e3a8a] hover:bg-white/90">
              Open the workspace <Icon name="arrow" size={16} />
            </Button>
          </Link>
        </div>
      </section>
    </AppShell>
  );
}

/** Static decorative chart for the hero frame. */
function MiniChart() {
  const w = 600;
  const h = 150;
  const n = 60;
  const pts = Array.from({ length: n }, (_, i) => {
    const x = (i / (n - 1)) * w;
    const base = 70 - i * 0.55 + Math.sin(i / 3.2) * 9;
    return [x, base];
  });
  const split = Math.round(n * 0.72);
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const band = pts
    .slice(split)
    .map(([x, y], i) => `${x.toFixed(1)},${(y - 6 - i * 0.5).toFixed(1)}`)
    .concat(
      pts
        .slice(split)
        .reverse()
        .map(([x, y], i) => `${x.toFixed(1)},${(y + 6 + (n - split - i) * 0.5).toFixed(1)}`),
    )
    .join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-36 w-full" aria-hidden>
      {[30, 60, 90, 120].map((y) => (
        <line key={y} x1="0" x2={w} y1={y} y2={y} stroke="var(--grid)" strokeWidth="1" />
      ))}
      <polygon points={band} fill="var(--series-forecast)" fillOpacity="0.15" />
      <path d={line} fill="none" stroke="var(--series-forecast)" strokeWidth="2.5" />
      {pts.slice(0, split).filter((_, i) => i % 2 === 0).map(([x, y], i) => (
        <circle key={i} cx={x} cy={y + (i % 3 - 1) * 4} r="2.4" fill="var(--series-actual)" fillOpacity="0.85" />
      ))}
      <line x1={pts[split][0]} x2={pts[split][0]} y1="10" y2={h - 10} stroke="var(--muted)" strokeDasharray="4 4" />
      <circle cx={pts[18][0]} cy={pts[18][1] + 34} r="6" fill="none" stroke="var(--bad)" strokeWidth="2" />
      <circle cx={pts[18][0]} cy={pts[18][1] + 34} r="2.5" fill="var(--bad)" />
    </svg>
  );
}
