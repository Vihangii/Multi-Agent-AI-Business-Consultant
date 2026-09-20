// Create a monthly re-run schedule (POST) or delete one via unsubscribe link (DELETE/GET).

import { NextResponse } from "next/server";
import {
  createSchedule,
  deleteSchedule,
  emailConfigured,
  schedulesConfigured,
  unsubscribeToken,
  verifyUnsubscribeToken,
} from "@/lib/schedules";
import type { AnalyzeOptions } from "@/lib/types";

export const runtime = "nodejs";

const ALLOWED_HOST_SUFFIX = ".public.blob.vercel-storage.com";

export async function POST(request: Request) {
  if (!schedulesConfigured() || !emailConfigured()) {
    return NextResponse.json(
      { error: "Scheduling is not configured on this deployment (needs a Vercel Blob store and RESEND_API_KEY)." },
      { status: 501 },
    );
  }
  let body: { email?: string; fileUrl?: string; fileName?: string; options?: AnalyzeOptions };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const email = (body.email ?? "").trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return NextResponse.json({ error: "A valid email address is required." }, { status: 400 });
  }
  let host = "";
  try {
    host = new URL(body.fileUrl ?? "").hostname;
  } catch {
    /* handled below */
  }
  if (!host.endsWith(ALLOWED_HOST_SUFFIX)) {
    return NextResponse.json({ error: "fileUrl must point at this app's Blob store." }, { status: 400 });
  }
  const s = await createSchedule({
    email,
    fileUrl: body.fileUrl!,
    fileName: body.fileName ?? "dataset",
    options: body.options ?? { skipRecommendations: false },
  });
  return NextResponse.json({ id: s.id, unsubscribeToken: unsubscribeToken(s.id) });
}

async function remove(request: Request) {
  const url = new URL(request.url);
  const id = url.searchParams.get("id") ?? "";
  const token = url.searchParams.get("token") ?? "";
  if (!id || !token || !verifyUnsubscribeToken(id, token)) {
    return NextResponse.json({ error: "Invalid unsubscribe link." }, { status: 400 });
  }
  if (!schedulesConfigured()) return NextResponse.json({ error: "Not configured" }, { status: 501 });
  const ok = await deleteSchedule(id);
  return ok
    ? new NextResponse("<p style='font-family:system-ui'>You have been unsubscribed. No more monthly forecasts will be sent for this dataset.</p>", {
        headers: { "content-type": "text/html" },
      })
    : NextResponse.json({ error: "Schedule not found (already removed?)." }, { status: 404 });
}

export const DELETE = remove;
export const GET = remove; // so the unsubscribe link works from an email client
