"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, analyzeFile, getHealth, inspectFile, type FileSource } from "@/lib/api";
import { deleteBlob, uploadToBlob } from "@/lib/blob";
import type { AnalyzeOptions, AnalyzeResult, HealthResult } from "@/lib/types";

/** What the last successful run used — needed to schedule a monthly re-run. */
export interface LastRun {
  fileUrl: string | null;
  fileName: string;
  options: AnalyzeOptions;
}
import { AppShell } from "./AppShell";
import { LoadingScreen, PipelineOverlay } from "./LoadingScreen";
import { Results } from "./Results";
import { AUTO, HORIZON_BOUNDS, Sidebar, type SidebarState } from "./Sidebar";
import { Button, Card, Icon, Notice, Skeleton } from "./ui";


const initialState: SidebarState = {
  file: null,
  fileError: null,
  inspecting: false,
  inspect: null,
  inspectError: null,
  dateColumn: AUTO,
  revenueColumn: AUTO,
  regressorColumn: "",
  language: "English",
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
  const [lastRun, setLastRun] = useState<LastRun | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const inspectSeq = useRef(0);
  const [stage, setStage] = useState(-1);
  const stageTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // The API doesn't stream progress, so estimate stage timing while a run is in flight
  const startStageTicker = useCallback((skipAi: boolean) => {
    const last = skipAi ? 2 : 4;
    const timings = [600, 1800, 800, 9000, 8000];
    let i = 0;
    setStage(0);
    const tick = () => {
      i = Math.min(i + 1, last);
      setStage(i);
      if (i < last) stageTimer.current = setTimeout(tick, timings[i]);
    };
    stageTimer.current = setTimeout(tick, timings[0]);
  }, []);
  const stopStageTicker = useCallback(() => {
    if (stageTimer.current) clearTimeout(stageTimer.current);
    stageTimer.current = null;
    setStage(-1);
  }, []);
  // Blob URL for the current file when it was too large to POST directly
  const blobUrl = useRef<string | null>(null);

  /**
   * Decide how to hand the file to the API. On Vercel the API can't receive
   * multipart bodies over 4.5 MB, so bigger files are uploaded to Vercel Blob
   * first and passed by URL.
   */
  const resolveSource = useCallback(
    async (file: File): Promise<FileSource> => {
      const capMb = health?.max_multipart_mb ?? Infinity;
      if (file.size <= capMb * 1024 * 1024) return { file };
      if (blobUrl.current) return { fileUrl: blobUrl.current };
      try {
        const url = await uploadToBlob(file);
        blobUrl.current = url;
        return { fileUrl: url };
      } catch (e) {
        throw new Error(
          `This file is ${(file.size / 1024 / 1024).toFixed(1)} MB, over the ${capMb} MB direct-upload limit of the API host, ` +
            `and large-file uploads are not available (${e instanceof Error ? e.message : String(e)}).`,
        );
      }
    },
    [health],
  );

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
      if (blobUrl.current) {
        void deleteBlob(blobUrl.current);
        blobUrl.current = null;
      }
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
        regressorColumn: "",
      });
      try {
        const info = await inspectFile(await resolveSource(file), state.apiKey || undefined);
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
    [patch, state.apiKey, resolveSource],
  );

  async function run() {
    if (!state.file) return;
    setRunning(true);
    setRunError(null);
    startStageTicker(state.skipRecommendations);
    try {
      const res = await analyzeFile(
        await resolveSource(state.file),
        {
          periods: state.frequency ? state.periods : null,
          frequency: state.frequency || null,
          skipRecommendations: state.skipRecommendations,
          dateColumn: state.dateColumn === AUTO ? null : state.dateColumn,
          revenueColumn: state.revenueColumn === AUTO ? null : state.revenueColumn,
          regressorColumn: state.regressorColumn || null,
          language: state.language,
        },
        state.apiKey || undefined,
      );
      setResult(res);
      setResultSkipped(state.skipRecommendations);
      setLastRun({
        fileUrl: blobUrl.current,
        fileName: state.file.name,
        options: {
          periods: state.frequency ? state.periods : null,
          frequency: state.frequency || null,
          skipRecommendations: state.skipRecommendations,
          dateColumn: state.dateColumn === AUTO ? null : state.dateColumn,
          revenueColumn: state.revenueColumn === AUTO ? null : state.revenueColumn,
          regressorColumn: state.regressorColumn || null,
          language: state.language,
        },
      });
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
      stopStageTicker();
      setRunning(false);
    }
  }

  return (
    <AppShell health={health} healthError={healthError} onToggleSidebar={() => setSidebarOpen((o) => !o)} fullBleed>
      <div className="flex flex-1">
        {sidebarOpen && (
          <div className="w-full shrink-0 lg:sticky lg:top-14 lg:h-[calc(100vh-3.5rem)] lg:w-[360px]">
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

        <main className={`min-w-0 flex-1 bg-page ${sidebarOpen ? "hidden lg:block" : ""}`}>
          {!health && !healthError && !result ? (
            <LoadingScreen title="Connecting to the API" subtitle="Checking the backend and which AI provider is available…" />
          ) : (
          <div className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8">
            {running && (
              <PipelineOverlay stage={stage} skipAi={state.skipRecommendations} fileName={state.file?.name} />
            )}

            {runError && (
              <Notice tone="bad" className="mb-5">
                {runError}
              </Notice>
            )}

            {result ? (
              <div className="animate-fade-up">
                <Results result={result} skipRecommendations={resultSkipped} lastRun={lastRun} file={state.file} apiKey={state.apiKey} />
              </div>
            ) : running ? (
              <RunningSkeleton />
            ) : (
              <Welcome onStart={() => setSidebarOpen(true)} hasFile={!!state.file} />
            )}
          </div>
          )}
        </main>
      </div>
    </AppShell>
  );
}

function RunningSkeleton() {
  return (
    <div className="space-y-4" aria-hidden>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <Skeleton className="h-72" />
      <div className="grid gap-4 md:grid-cols-2">
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
      </div>
    </div>
  );
}

function Welcome({ onStart, hasFile }: { onStart: () => void; hasFile: boolean }) {
  const agents = [
    { icon: "file", title: "Data Agent", text: "Detects columns, parses currency strings, aggregates duplicates, computes growth and volatility." },
    { icon: "chart", title: "Forecast Agent", text: "Prophet forecast with 95% intervals, a backtest (MAPE, MAE, coverage) and what-if scenarios." },
    { icon: "alert", title: "Anomaly Agent", text: "Robust z-scores on model residuals flag collapses and spikes for the strategist." },
    { icon: "sparkle", title: "Strategist Agent", text: "Queries the data with tools before writing prioritised, data-backed recommendations." },
    { icon: "shield", title: "Critic Agent", text: "Fact-checks every figure in the report against the data and corrects what's wrong." },
  ];
  return (
    <div className="animate-fade-up space-y-6">
      <Card className="bg-dots">
        <div className="max-w-2xl">
          <h1 className="text-2xl font-semibold tracking-tight">Workspace</h1>
          <p className="mt-2 text-text-2">
            {hasFile
              ? "Your file is ready. Confirm the columns, choose your options, and run the pipeline."
              : "Upload a sales or revenue spreadsheet in the panel to begin — or grab the sample CSV to see everything in under a minute."}
          </p>
          <div className="mt-4 flex flex-wrap gap-2 lg:hidden">
            <Button variant="primary" onClick={onStart}>
              <Icon name="upload" size={15} /> Open the configuration panel
            </Button>
          </div>
        </div>
      </Card>

      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-[0.08em] text-muted">What runs when you click Run</h2>
        <ol className="stagger grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          {agents.map((a, i) => (
            <li key={a.title} className="hover-lift rounded-xl border border-border bg-surface p-4 shadow-card">
              <div className="flex items-center justify-between">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-soft text-accent">
                  <Icon name={a.icon} size={16} />
                </span>
                <span className="text-xs font-semibold tabular text-muted">0{i + 1}</span>
              </div>
              <h3 className="mt-3 text-sm font-semibold">{a.title}</h3>
              <p className="mt-1 text-xs leading-relaxed text-text-2">{a.text}</p>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
