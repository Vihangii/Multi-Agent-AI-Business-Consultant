"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { MAX_UPLOAD_MB, validateFile } from "@/lib/api";
import { generateSampleCsv } from "@/lib/sample";
import type { Frequency, HealthResult, InspectResult } from "@/lib/types";
import { Button, Icon, Label, Notice, Select, Spinner } from "./ui";

export const AUTO = "__auto__";

// Slider bounds per frequency: [min, max, default, step]
export const HORIZON_BOUNDS: Record<Frequency, [number, number, number, number]> = {
  D: [7, 365, 180, 7],
  W: [4, 104, 26, 1],
  MS: [1, 24, 6, 1],
};

export interface SidebarState {
  file: File | null;
  fileError: string | null;
  inspecting: boolean;
  inspect: InspectResult | null;
  inspectError: string | null;
  dateColumn: string; // AUTO or column name
  revenueColumn: string;
  regressorColumn: string; // "" = none
  language: string;
  frequency: Frequency | "";
  periods: number;
  skipRecommendations: boolean;
  apiKey: string;
}

interface Props {
  state: SidebarState;
  health: HealthResult | null;
  healthError: string | null;
  running: boolean;
  onFile: (file: File | null) => void;
  onChange: (patch: Partial<SidebarState>) => void;
  onRun: () => void;
}

function Step({
  n,
  title,
  done,
  children,
}: {
  n: number;
  title: string;
  done?: boolean;
  children: ReactNode;
}) {
  return (
    <section className="relative pl-9">
      <span
        className={`absolute left-0 top-0 flex h-6 w-6 items-center justify-center rounded-full border text-[11px] font-semibold ${
          done ? "border-good/30 bg-good-bg text-good" : "border-border bg-surface-2 text-text-2"
        }`}
        aria-hidden
      >
        {done ? <span className="animate-pop inline-flex"><Icon name="check" size={12} /></span> : n}
      </span>
      <h3 className="mb-3 text-sm font-semibold leading-6">{title}</h3>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

export function Sidebar({ state, health, healthError, running, onFile, onChange, onRun }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  // Reset the horizon to the frequency's default when the frequency changes
  useEffect(() => {
    if (state.frequency) {
      onChange({ periods: HORIZON_BOUNDS[state.frequency][2] });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.frequency]);

  function acceptFile(f: File | null) {
    if (!f) return onFile(null);
    const err = validateFile(f);
    if (err) {
      onChange({ file: null, fileError: err, inspect: null });
      if (inputRef.current) inputRef.current.value = "";
      return;
    }
    onFile(f);
  }

  function handleFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    acceptFile(e.target.files?.[0] ?? null);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    acceptFile(e.dataTransfer.files?.[0] ?? null);
  }

  function downloadSample() {
    const blob = new Blob([generateSampleCsv()], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "sample_daily_sales.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  const cols = state.inspect?.columns ?? [];
  const colOptions = [{ value: AUTO, label: "Auto-detect" }].concat(cols.map((c) => ({ value: c, label: c })));
  const bounds = state.frequency ? HORIZON_BOUNDS[state.frequency] : null;
  const canRun = !!state.file && !running && !state.inspecting;
  const columnsReady = !!state.inspect;

  return (
    <aside className="flex h-full flex-col gap-7 overflow-y-auto border-r border-border bg-surface px-5 py-6">
      {/* Step 1 — data */}
      <Step n={1} title="Upload your data" done={!!state.file}>
        <input
          ref={inputRef}
          id="file-input"
          type="file"
          accept=".csv,.xlsx,.xls"
          onChange={handleFileInput}
          className="sr-only"
        />
        <label
          htmlFor="file-input"
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-6 text-center transition ${
            dragging
              ? "border-accent bg-accent-soft"
              : state.file
                ? "border-good/40 bg-good-bg/40"
                : "border-border-strong bg-surface-2/60 hover:border-accent hover:bg-accent-soft/40"
          }`}
        >
          {state.file ? (
            <>
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-good-bg text-good">
                <Icon name="file" size={18} />
              </span>
              <span className="max-w-full truncate text-sm font-medium">{state.file.name}</span>
              <span className="text-xs text-muted">
                {(state.file.size / 1024).toFixed(1)} KB · click or drop to replace
              </span>
            </>
          ) : (
            <>
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-soft text-accent">
                <Icon name="upload" size={18} />
              </span>
              <span className="text-sm font-medium">Drop a file or click to browse</span>
              <span className="text-xs text-muted">CSV, XLSX or XLS · up to {MAX_UPLOAD_MB} MB</span>
            </>
          )}
        </label>
        {state.fileError && <Notice tone="bad">{state.fileError}</Notice>}
        <Button variant="ghost" size="sm" onClick={downloadSample} className="-ml-1">
          <Icon name="download" size={14} /> Download sample CSV
        </Button>
      </Step>

      {/* Step 2 — columns */}
      <Step n={2} title="Confirm columns" done={columnsReady}>
        {!state.file ? (
          <p className="text-sm text-muted">Upload a file to detect its date and revenue columns.</p>
        ) : state.inspecting ? (
          <div className="flex items-center gap-2 text-sm text-text-2">
            <Spinner /> Inspecting file…
          </div>
        ) : state.inspect ? (
          <>
            <div>
              <Label htmlFor="datecol" hint="Auto-detected value is preselected; change it if it's wrong.">
                Date column
              </Label>
              <Select id="datecol" value={state.dateColumn} onChange={(v) => onChange({ dateColumn: v })} options={colOptions} />
            </div>
            <div>
              <Label htmlFor="revcol">Revenue column</Label>
              <Select id="revcol" value={state.revenueColumn} onChange={(v) => onChange({ revenueColumn: v })} options={colOptions} />
            </div>
            <div>
              <Label
                htmlFor="drivercol"
                hint="A numeric column that drives revenue (e.g. marketing spend). Enables what-if scenarios learned from your data."
              >
                What-if driver <span className="normal-case tracking-normal text-muted">(optional)</span>
              </Label>
              <Select
                id="drivercol"
                value={state.regressorColumn}
                onChange={(v) => onChange({ regressorColumn: v })}
                options={[{ value: "", label: "None — simple % uplift" }].concat(
                  (state.inspect.numeric_columns ?? [])
                    .filter((c) => c !== state.dateColumn && c !== state.revenueColumn)
                    .map((c) => ({ value: c, label: c })),
                )}
              />
            </div>
            {(state.inspect.detected_date_column === null || state.inspect.detected_revenue_column === null) && (
              <Notice tone="warn">Could not auto-detect both columns — please pick them above.</Notice>
            )}
            <details className="rounded-lg border border-border">
              <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-text-2">
                Preview (first 5 of {state.inspect.row_count.toLocaleString()} rows)
              </summary>
              <div className="overflow-x-auto">
                <table className="min-w-full text-xs">
                  <thead className="bg-surface-2 text-left">
                    <tr>
                      {cols.map((c) => (
                        <th key={c} className="whitespace-nowrap px-2 py-1 font-semibold">{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {state.inspect.preview.map((row, i) => (
                      <tr key={i} className="border-t border-border">
                        {cols.map((c) => (
                          <td key={c} className="whitespace-nowrap px-2 py-1 tabular">{row[c]}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          </>
        ) : (
          <Notice tone="warn">
            {state.inspectError ? `Could not inspect the file: ${state.inspectError}` : "Columns will be auto-detected when the pipeline runs."}
          </Notice>
        )}
      </Step>

      {/* Step 3 — options */}
      <Step n={3} title="Forecast & report options">
        <div>
          <Label htmlFor="freq" hint="Enforce forecasting at a particular time granularity.">Frequency</Label>
          <Select
            id="freq"
            value={state.frequency}
            onChange={(v) => onChange({ frequency: v as Frequency | "" })}
            options={[
              { value: "", label: "Auto-detect" },
              { value: "D", label: "Daily" },
              { value: "W", label: "Weekly" },
              { value: "MS", label: "Monthly" },
            ]}
          />
        </div>
        {bounds ? (
          <div>
            <Label htmlFor="periods">
              Horizon ·{" "}
              <span className="normal-case tracking-normal text-text">
                {state.periods} {state.frequency === "D" ? "days" : state.frequency === "W" ? "weeks" : "months"}
              </span>
            </Label>
            <input
              id="periods"
              type="range"
              min={bounds[0]}
              max={bounds[1]}
              step={bounds[3]}
              value={state.periods}
              onChange={(e) => onChange({ periods: Number(e.target.value) })}
              className="w-full"
            />
            <div className="flex justify-between text-[11px] text-muted">
              <span>{bounds[0]}</span>
              <span>{bounds[1]}</span>
            </div>
          </div>
        ) : (
          <p className="text-xs text-muted">Horizon: ~6 months, based on the detected granularity.</p>
        )}

        <div>
          <Label htmlFor="lang">Report language</Label>
          <Select
            id="lang"
            value={state.language}
            disabled={state.skipRecommendations}
            onChange={(v) => onChange({ language: v })}
            options={(health?.languages ?? ["English"]).map((l) => ({ value: l, label: l }))}
          />
        </div>

        <label className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-border bg-surface-2/50 px-3 py-2.5 text-sm">
          <input
            type="checkbox"
            checked={state.skipRecommendations}
            onChange={(e) => onChange({ skipRecommendations: e.target.checked })}
            className="mt-0.5"
          />
          <span>
            Skip AI recommendations
            <span className="block text-xs text-muted">Run only the data, forecast and anomaly agents.</span>
          </span>
        </label>
        {health && !health.llm_configured && !state.skipRecommendations && (
          <Notice tone="info">
            The API has no LLM provider configured — the report stage will be reported as unavailable.
          </Notice>
        )}
        {health?.auth_required && (
          <div>
            <Label htmlFor="apikey">API key</Label>
            <input
              id="apikey"
              type="password"
              value={state.apiKey}
              onChange={(e) => onChange({ apiKey: e.target.value })}
              placeholder="X-API-Key"
              className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm shadow-card"
            />
          </div>
        )}
        {healthError && <Notice tone="bad">API unreachable — {healthError}</Notice>}
      </Step>

      <div className="mt-auto pt-2">
        <Button variant="primary" size="lg" onClick={onRun} disabled={!canRun} className="w-full">
          {running ? (
            <>
              <Spinner /> Running pipeline…
            </>
          ) : (
            <>
              <Icon name="play" size={16} /> Run Consultant Pipeline
            </>
          )}
        </Button>
        {!state.file && <p className="mt-2 text-center text-xs text-muted">Upload a file to enable</p>}
      </div>
    </aside>
  );
}
