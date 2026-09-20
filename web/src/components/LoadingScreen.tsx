"use client";

import { useEffect, useState, type ReactNode } from "react";
import { Logo } from "./AppShell";
import { Icon, Stepper } from "./ui";

const TIPS = [
  "The Data Agent recognises currency strings like “$1,200.50” and duplicate dates.",
  "Prophet is backtested on the last 20% of your history so you can see its real accuracy.",
  "Pick a driver column (e.g. marketing spend) to get what-if scenarios learned from your data.",
  "The Strategist Agent queries your data with tools before writing a single sentence.",
  "The Critic Agent checks every number in the report and corrects what's wrong.",
  "Export the whole analysis to PDF or PowerPoint with one click.",
];

/** Branded full-screen loader used for route transitions and the initial API connect. */
export function LoadingScreen({
  title = "Loading…",
  subtitle,
  children,
}: {
  title?: string;
  subtitle?: string;
  children?: ReactNode;
}) {
  return (
    <div className="bg-dots flex min-h-[70vh] flex-1 flex-col items-center justify-center px-6 py-16 text-center">
      <div className="animate-fade-up flex flex-col items-center">
        <div className="relative mb-6 animate-float">
          <span className="absolute inset-0 -m-3 animate-ping rounded-2xl bg-accent/15" aria-hidden />
          <Logo size={44} />
        </div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-2 max-w-md text-sm text-text-2">{subtitle}</p>}
        <div className="mt-6 h-1 w-48 overflow-hidden rounded-full bg-surface-3">
          <div className="h-full w-1/2 animate-[shimmer_1.4s_infinite_linear] rounded-full bg-accent" style={{ backgroundSize: "800px 100%" }} />
        </div>
        {children}
      </div>
    </div>
  );
}

const STAGES = [
  { label: "Data" },
  { label: "Forecast" },
  { label: "Anomalies" },
  { label: "Strategist" },
  { label: "Critic" },
];

/** Full-screen overlay shown while the pipeline runs. */
export function PipelineOverlay({
  stage,
  skipAi,
  fileName,
}: {
  stage: number;
  skipAi: boolean;
  fileName?: string;
}) {
  const [tip, setTip] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTip((i) => (i + 1) % TIPS.length), 4500);
    const e = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => {
      clearInterval(t);
      clearInterval(e);
    };
  }, []);

  const steps = skipAi ? STAGES.slice(0, 3) : STAGES;
  const labels = ["Cleaning and analysing your data", "Fitting the forecast model and backtesting", "Scanning for anomalies", "Strategist is querying the data and writing the report", "Critic is fact-checking the report"];

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed inset-0 z-40 flex items-center justify-center bg-page/80 p-4 backdrop-blur-sm"
    >
      <div className="animate-fade-up w-full max-w-lg rounded-2xl border border-border bg-surface p-6 shadow-hero sm:p-8">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-soft text-accent">
            <Icon name="sparkle" size={20} />
          </span>
          <div className="min-w-0">
            <div className="font-semibold">Running the agent pipeline</div>
            <div className="truncate text-xs text-muted">
              {fileName ?? "your dataset"} · {elapsed}s · {skipAi ? "about 5 seconds" : "usually 10–40 seconds with AI agents"}
            </div>
          </div>
        </div>

        <div className="mt-5">
          <Stepper steps={steps} active={stage} doneThrough={stage - 1} />
        </div>
        <p className="mt-3 text-sm text-text-2">{labels[Math.max(0, Math.min(stage, labels.length - 1))]}…</p>

        <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-surface-3">
          <div
            className="h-full rounded-full bg-accent transition-all duration-700"
            style={{ width: `${Math.min(95, ((stage + 0.5) / steps.length) * 100)}%` }}
          />
        </div>

        <div className="mt-5 rounded-lg border border-border bg-surface-2/60 px-3 py-2.5 text-xs text-text-2">
          <span className="font-semibold text-text">Did you know?</span> {TIPS[tip]}
        </div>
      </div>
    </div>
  );
}
