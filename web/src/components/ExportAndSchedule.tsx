"use client";

import { useState } from "react";
import { uploadToBlob } from "@/lib/blob";
import { buildReportData, exportPdf, exportPptx } from "@/lib/export";
import type { AnalyzeResult } from "@/lib/types";
import type { LastRun } from "./ConsultantApp";
import { Button, Icon, Notice, Spinner } from "./ui";

interface Props {
  result: AnalyzeResult;
  lastRun: LastRun | null;
  file: File | null;
}

/** Export buttons (PDF / PowerPoint / Markdown) plus the monthly-email scheduler. */
export function ExportBar({ result, lastRun, file }: Props) {
  const [busy, setBusy] = useState<"pdf" | "pptx" | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const base = (lastRun?.fileName ?? "analysis").replace(/\.[^.]+$/, "");

  async function run(kind: "pdf" | "pptx") {
    setBusy(kind);
    setErr(null);
    try {
      const data = buildReportData(result, lastRun?.fileName ?? "dataset");
      if (kind === "pdf") await exportPdf(data, base);
      else await exportPptx(data, base);
    } catch (e) {
      setErr(`Export failed: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(null);
    }
  }

  function downloadMd() {
    if (!result.recommendations) return;
    const blob = new Blob([result.recommendations], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${base}-recommendations.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button size="sm" disabled={busy !== null} onClick={() => run("pdf")}>
        {busy === "pdf" ? <Spinner /> : <Icon name="download" size={14} />} PDF
      </Button>
      <Button size="sm" disabled={busy !== null} onClick={() => run("pptx")}>
        {busy === "pptx" ? <Spinner /> : <Icon name="download" size={14} />} PowerPoint
      </Button>
      {result.recommendations && (
        <Button size="sm" onClick={downloadMd}>
          <Icon name="file" size={14} /> Markdown
        </Button>
      )}
      <ScheduleButton result={result} lastRun={lastRun} file={file} />
      {err && <Notice tone="bad" className="basis-full">{err}</Notice>}
    </div>
  );
}

function ScheduleButton({ lastRun, file }: Props) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "saving" | "done" | "error">("idle");
  const [msg, setMsg] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!lastRun) return;
    setState("saving");
    setMsg("");
    try {
      // The cron job needs the file by URL; upload it to Blob if it isn't there yet.
      let fileUrl = lastRun.fileUrl;
      if (!fileUrl) {
        if (!file) throw new Error("The original file is no longer available; re-run the analysis first.");
        try {
          fileUrl = await uploadToBlob(file);
        } catch (e) {
          throw new Error(
            "Scheduling needs file storage (a Vercel Blob store) and email (Resend) configured on this deployment. " +
              `Storage error: ${e instanceof Error ? e.message : String(e)}`,
          );
        }
      }
      const res = await fetch("/api/schedules", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, fileUrl, fileName: lastRun.fileName, options: lastRun.options }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`);
      setState("done");
      setMsg(`Scheduled. You'll get a fresh forecast for “${lastRun.fileName}” at ${email} on the 1st of every month.`);
    } catch (err) {
      setState("error");
      setMsg(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <>
      <Button size="sm" onClick={() => setOpen((o) => !o)}>
        <Icon name="mail" size={14} /> Email me monthly
      </Button>
      {open && (
        <form onSubmit={submit} className="basis-full rounded-lg border border-border bg-surface-2/60 p-3">
          <div className="mb-2 text-sm font-semibold">Monthly re-run</div>
          <p className="mb-2 text-xs text-text-2">
            On the 1st of each month the pipeline re-runs on this dataset with the same options and emails you the
            updated forecast and recommendations. Every email has an unsubscribe link.
          </p>
          <div className="flex flex-wrap gap-2">
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              className="min-w-[220px] flex-1 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-accent"
            />
            <Button type="submit" variant="primary" disabled={state === "saving" || state === "done"}>
              {state === "saving" ? <Spinner /> : null} Schedule
            </Button>
          </div>
          {state === "done" && <Notice tone="good" className="mt-2">{msg}</Notice>}
          {state === "error" && <Notice tone="bad" className="mt-2">{msg}</Notice>}
        </form>
      )}
    </>
  );
}
