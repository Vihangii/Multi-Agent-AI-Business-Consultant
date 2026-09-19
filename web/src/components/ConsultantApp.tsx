"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, analyzeFile, getHealth, inspectFile } from "@/lib/api";
import type { AnalyzeResult, HealthResult } from "@/lib/types";
import { Results } from "./Results";
import { AUTO, HORIZON_BOUNDS, Sidebar, type SidebarState } from "./Sidebar";
import { Card, Notice } from "./ui";

const initialState: SidebarState = {
  file: null,
  fileError: null,
  inspecting: false,
  inspect: null,
  inspectError: null,
  dateColumn: AUTO,
  revenueColumn: AUTO,
  frequency: "",
  periods: HORIZON_BOUNDS.D[2],
  skipRecommendations: false,
  apiKey: "",
};

export function ConsultantApp() {
  const [state, setState] = useState<SidebarState>(initialState);
  const [health, setHealth] = useState<HealthResult | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [resultSkipped, setResultSkipped] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const inspectSeq = useRef(0);

  const patch = useCallback((p: Partial<SidebarState>) => {
    setState((s) => ({ ...s, ...p }));
  }, []);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch((e: unknown) => setHealthError(e instanceof Error ? e.message : String(e)));
  }, []);

  // On upload: validate locally, then ask the API which columns it would pick
  const handleFile = useCallback(
    async (file: File | null) => {
      const seq = ++inspectSeq.current;
      if (!file) {
        patch({ file: null, fileError: null, inspect: null, inspectError: null });
        return;
      }
      patch({
        file,
        fileError: null,
        inspecting: true,
        inspect: null,
        inspectError: null,
        dateColumn: AUTO,
        revenueColumn: AUTO,
      });
      try {
        const info = await inspectFile(file, state.apiKey || undefined);
        if (seq !== inspectSeq.current) return; // a newer upload superseded this one
        patch({
          inspecting: false,
          inspect: info,
          dateColumn: info.detected_date_column ?? AUTO,
          revenueColumn: info.detected_revenue_column ?? AUTO,
        });
      } catch (e: unknown) {
        if (seq !== inspectSeq.current) return;
        patch({
          inspecting: false,
          inspect: null,
          inspectError: e instanceof Error ? e.message : String(e),
        });
      }
    },
    [patch, state.apiKey],
  );

  async function run() {
    if (!state.file) return;
    setRunning(true);
    setRunError(null);
    try {
      const res = await analyzeFile(
        state.file,
        {
          periods: state.frequency ? state.periods : null,
          frequency: state.frequency || null,
          skipRecommendations: state.skipRecommendations,
          dateColumn: state.dateColumn === AUTO ? null : state.dateColumn,
          revenueColumn: state.revenueColumn === AUTO ? null : state.revenueColumn,
        },
        state.apiKey || undefined,
      );
      setResult(res);
      setResultSkipped(state.skipRecommendations);
      if (window.innerWidth < 1024) setSidebarOpen(false);
    } catch (e: unknown) {
      if (e instanceof ApiError) {
        setRunError(`Backend error (${e.status}): ${e.message}`);
      } else if (e instanceof TypeError) {
        setRunError(
          "Could not reach the API. Check that the backend is running and NEXT_PUBLIC_API_URL points to it.",
        );
      } else {
        setRunError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center gap-3 border-b border-border bg-surface px-4 py-3">
        <button
          type="button"
          onClick={() => setSidebarOpen((o) => !o)}
          className="rounded-lg border border-border px-2 py-1 text-sm hover:bg-surface-2"
          aria-label="Toggle sidebar"
        >
          ☰
        </button>
        <div>
          <h1 className="bg-gradient-to-r from-[#1e3a8a] via-[#3b82f6] to-[#60a5fa] bg-clip-text text-xl font-extrabold tracking-tight text-transparent sm:text-2xl">
            Multi-Agent AI Business Consultant
          </h1>
          <p className="text-xs text-text-2 sm:text-sm">
            Data-driven automated business analysis, forecasting, and strategic consulting
          </p>
        </div>
      </header>

      <div className="flex flex-1">
        {sidebarOpen && (
          <div className="w-full shrink-0 lg:sticky lg:top-0 lg:h-screen lg:w-[340px]">
            <Sidebar
              state={state}
              health={health}
              healthError={healthError}
              running={running}
              onFile={handleFile}
              onChange={patch}
              onRun={run}
            />
          </div>
        )}

        <main className={`min-w-0 flex-1 p-4 sm:p-6 ${sidebarOpen ? "hidden lg:block" : ""}`}>
          {runError && (
            <Notice tone="bad" className="mb-4">
              {runError}
            </Notice>
          )}

          {result ? (
            <Results result={result} skipRecommendations={resultSkipped} />
          ) : (
            <Welcome running={running} />
          )}
        </main>
      </div>
    </div>
  );
}

function Welcome({ running }: { running: boolean }) {
  return (
    <div className="space-y-4">
      <Notice tone="info">
        {running
          ? "⚡ Running the multi-agent consulting pipeline… this takes a few seconds (longer with AI recommendations)."
          : "👈 Upload your business transaction data in the sidebar (or download the sample CSV) and click Run Consultant Pipeline to begin."}
      </Notice>
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <h3 className="mb-2 font-semibold">🔍 1. Data Agent</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm text-text-2">
            <li>Detects date and revenue columns automatically.</li>
            <li>Parses currency strings, aggregates duplicate dates.</li>
            <li>Computes growth, monthly and volatility statistics.</li>
          </ul>
        </Card>
        <Card>
          <h3 className="mb-2 font-semibold">📈 2. Forecast Agent</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm text-text-2">
            <li>Fits a Facebook Prophet time-series model.</li>
            <li>Projects future revenue with 95% confidence intervals.</li>
            <li>Backtests itself and reports MAPE, MAE and coverage.</li>
          </ul>
        </Card>
        <Card>
          <h3 className="mb-2 font-semibold">🚀 3. Recommendation Agent</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm text-text-2">
            <li>Sends the analysis to an OpenAI GPT model.</li>
            <li>Returns prioritised, data-backed strategies.</li>
            <li>Includes a 90-day action plan.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
