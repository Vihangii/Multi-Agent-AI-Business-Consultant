"use client";

import { useEffect, useRef } from "react";
import { MAX_UPLOAD_MB, validateFile } from "@/lib/api";
import { generateSampleCsv } from "@/lib/sample";
import type { Frequency, HealthResult, InspectResult } from "@/lib/types";
import { Label, Notice, Select, Spinner } from "./ui";

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

export function Sidebar({
  state,
  health,
  healthError,
  running,
  onFile,
  onChange,
  onRun,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  // Reset the horizon to the frequency's default when the frequency changes
  useEffect(() => {
    if (state.frequency) {
      onChange({ periods: HORIZON_BOUNDS[state.frequency][2] });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.frequency]);

  function handleFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    if (!f) return onFile(null);
    const err = validateFile(f);
    if (err) {
      onChange({ file: null, fileError: err, inspect: null });
      e.target.value = "";
      return;
    }
    onFile(f);
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
  const colOptions = [{ value: AUTO, label: "Auto-detect" }].concat(
    cols.map((c) => ({ value: c, label: c })),
  );
  const bounds = state.frequency ? HORIZON_BOUNDS[state.frequency] : null;
  const canRun = !!state.file && !running && !state.inspecting;

  return (
    <aside className="flex h-full flex-col gap-5 overflow-y-auto border-r border-border bg-surface p-4">
      <div>
        <div className="text-lg font-bold tracking-tight">🛠 Configuration</div>
        <div className="mt-1 text-xs text-muted">
          {health ? (
            <>
              API online · {health.openai_configured ? "AI enabled" : "no OpenAI key"}
              {health.auth_required && " · key required"}
            </>
          ) : healthError ? (
            <span className="text-bad">API unreachable — {healthError}</span>
          ) : (
            "Checking API…"
          )}
        </div>
      </div>

      {health?.auth_required && (
        <div>
          <Label htmlFor="apikey">API key</Label>
          <input
            id="apikey"
            type="password"
            value={state.apiKey}
            onChange={(e) => onChange({ apiKey: e.target.value })}
            placeholder="X-API-Key"
            className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-accent"
          />
        </div>
      )}

      {/* Upload */}
      <section>
        <div className="mb-2 text-sm font-semibold">📂 Upload Dataset</div>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          onChange={handleFileInput}
          className="block w-full text-sm text-text-2 file:mr-3 file:rounded-lg file:border file:border-border file:bg-surface-2 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-text hover:file:bg-accent-soft"
        />
        <div className="mt-1 text-xs text-muted">
          CSV, XLSX or XLS · max {MAX_UPLOAD_MB} MB · needs a date column and a revenue column
        </div>
        {state.fileError && (
          <Notice tone="bad" className="mt-2">
            {state.fileError}
          </Notice>
        )}
        {state.file && (
          <div className="mt-2 truncate text-xs text-text-2">
            📄 {state.file.name} · {(state.file.size / 1024).toFixed(1)} KB
          </div>
        )}
        <button
          type="button"
          onClick={downloadSample}
          className="mt-3 w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm font-medium hover:bg-accent-soft"
        >
          📥 Download Sample CSV
        </button>
      </section>

      {/* Columns */}
      {state.file && (
        <section>
          <div className="mb-2 text-sm font-semibold">🧭 Columns</div>
          {state.inspecting ? (
            <div className="flex items-center gap-2 text-sm text-text-2">
              <Spinner /> Inspecting file…
            </div>
          ) : state.inspect ? (
            <div className="space-y-3">
              <div>
                <Label htmlFor="datecol" hint="Auto-detected value is preselected; change it if it's wrong.">
                  Date column
                </Label>
                <Select
                  id="datecol"
                  value={state.dateColumn}
                  onChange={(v) => onChange({ dateColumn: v })}
                  options={colOptions}
                />
              </div>
              <div>
                <Label htmlFor="revcol">Revenue column</Label>
                <Select
                  id="revcol"
                  value={state.revenueColumn}
                  onChange={(v) => onChange({ revenueColumn: v })}
                  options={colOptions}
                />
              </div>
              {(state.inspect.detected_date_column === null ||
                state.inspect.detected_revenue_column === null) && (
                <Notice tone="warn">
                  Could not auto-detect both columns — please pick them above.
                </Notice>
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
                          <th key={c} className="whitespace-nowrap px-2 py-1 font-semibold">
                            {c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {state.inspect.preview.map((row, i) => (
                        <tr key={i} className="border-t border-border">
                          {cols.map((c) => (
                            <td key={c} className="whitespace-nowrap px-2 py-1 tabular">
                              {row[c]}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </div>
          ) : (
            <Notice tone="warn">
              {state.inspectError
                ? `Could not inspect the file: ${state.inspectError}`
                : "Columns will be auto-detected when the pipeline runs."}
            </Notice>
          )}
        </section>
      )}

      {/* Forecasting options */}
      <section>
        <div className="mb-2 text-sm font-semibold">🔮 Forecasting Options</div>
        <Label htmlFor="freq" hint="Enforce forecasting at a particular time granularity.">
          Frequency override
        </Label>
        <Select
          id="freq"
          value={state.frequency}
          onChange={(v) => onChange({ frequency: v as Frequency | "" })}
          options={[
            { value: "", label: "Auto-detect" },
            { value: "D", label: "Daily ('D')" },
            { value: "W", label: "Weekly ('W')" },
            { value: "MS", label: "Monthly ('MS')" },
          ]}
        />
        {bounds ? (
          <div className="mt-3">
            <Label htmlFor="periods">
              Forecast horizon · {state.periods}{" "}
              {state.frequency === "D" ? "days" : state.frequency === "W" ? "weeks" : "months"}
            </Label>
            <input
              id="periods"
              type="range"
              min={bounds[0]}
              max={bounds[1]}
              step={bounds[3]}
              value={state.periods}
              onChange={(e) => onChange({ periods: Number(e.target.value) })}
              className="w-full accent-accent"
            />
            <div className="flex justify-between text-[11px] text-muted">
              <span>{bounds[0]}</span>
              <span>{bounds[1]}</span>
            </div>
          </div>
        ) : (
          <div className="mt-2 text-xs text-muted">
            Horizon: ~6 months, based on detected data granularity.
          </div>
        )}
      </section>

      {/* AI */}
      <section>
        <div className="mb-2 text-sm font-semibold">🤖 AI Consult Strategy</div>
        <label className="flex cursor-pointer items-start gap-2 text-sm">
          <input
            type="checkbox"
            checked={state.skipRecommendations}
            onChange={(e) => onChange({ skipRecommendations: e.target.checked })}
            className="mt-0.5 accent-accent"
          />
          <span>
            Skip AI Recommendations
            <span className="block text-xs text-muted">
              Bypass Stage 3 (OpenAI) for offline testing or to save tokens.
            </span>
          </span>
        </label>
        {health && !health.openai_configured && !state.skipRecommendations && (
          <Notice tone="info" className="mt-2">
            The API has no OpenAI key — the report stage will be reported as unavailable.
          </Notice>
        )}
      </section>

      <button
        type="button"
        onClick={onRun}
        disabled={!canRun}
        className="mt-auto flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white shadow hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {running ? (
          <>
            <Spinner /> Running pipeline…
          </>
        ) : (
          "🚀 Run Consultant Pipeline"
        )}
      </button>
    </aside>
  );
}
