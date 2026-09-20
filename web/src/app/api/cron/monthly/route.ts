// Vercel Cron target (see web/vercel.json): re-run every schedule and email the result.
//
// Vercel calls this with `Authorization: Bearer $CRON_SECRET`. Run it by hand:
//   curl -H "Authorization: Bearer $CRON_SECRET" https://<app>/api/cron/monthly

import { NextResponse } from "next/server";
import { analyzeParams } from "@/lib/api";
import { buildEmail, sendEmail } from "@/lib/email";
import { emailConfigured, listSchedules, saveSchedule, schedulesConfigured, unsubscribeToken } from "@/lib/schedules";
import type { AnalyzeResult } from "@/lib/types";

export const runtime = "nodejs";
export const maxDuration = 300;

function apiUrl(): string {
  return (process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");
}

function appUrl(request: Request): string {
  return process.env.APP_URL ?? new URL(request.url).origin;
}

export async function GET(request: Request) {
  const secret = process.env.CRON_SECRET;
  if (!secret || request.headers.get("authorization") !== `Bearer ${secret}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  if (!schedulesConfigured() || !emailConfigured()) {
    return NextResponse.json({ error: "Scheduling not configured" }, { status: 501 });
  }

  const schedules = await listSchedules();
  const results: { id: string; email: string; status: string; error?: string }[] = [];

  for (const s of schedules) {
    try {
      const form = new FormData();
      form.append("file_url", s.fileUrl);
      const params = new URLSearchParams(analyzeParams(s.options));
      const headers: Record<string, string> = {};
      if (process.env.API_KEY) headers["X-API-Key"] = process.env.API_KEY;

      const res = await fetch(`${apiUrl()}/analyze?${params}`, { method: "POST", body: form, headers });
      if (!res.ok) {
        let detail = res.statusText;
        try {
          detail = (await res.json()).detail ?? detail;
        } catch {
          /* keep statusText */
        }
        throw new Error(`API ${res.status}: ${detail}`);
      }
      const result = (await res.json()) as AnalyzeResult;

      const unsubscribeUrl = `${appUrl(request)}/api/schedules?id=${s.id}&token=${unsubscribeToken(s.id)}`;
      const { subject, html } = buildEmail(result, { fileName: s.fileName, appUrl: appUrl(request), unsubscribeUrl });
      await sendEmail(s.email, subject, html);

      await saveSchedule({ ...s, lastRunAt: new Date().toISOString(), lastStatus: "ok", lastError: undefined });
      results.push({ id: s.id, email: s.email, status: "sent" });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      await saveSchedule({ ...s, lastRunAt: new Date().toISOString(), lastStatus: "error", lastError: msg }).catch(() => {});
      results.push({ id: s.id, email: s.email, status: "error", error: msg });
    }
  }

  return NextResponse.json({ ran: results.length, results });
}
