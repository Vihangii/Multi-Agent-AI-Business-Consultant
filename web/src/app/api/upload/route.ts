// Token exchange for Vercel Blob *client* uploads, plus cleanup.
//
// Vercel serverless functions reject request bodies over 4.5 MB, so files
// bigger than that never pass through this app or the Python API. Instead the
// browser uploads straight to Vercel Blob (this route only mints a scoped
// token), then sends the resulting URL to the API as `file_url`.
//
// Requires BLOB_READ_WRITE_TOKEN (added automatically when a Blob store is
// connected to the Vercel project). Without it the route returns 501 and the
// client falls back to multipart uploads only.

import { del } from "@vercel/blob";
import { handleUpload, type HandleUploadBody } from "@vercel/blob/client";
import { NextResponse } from "next/server";

const MAX_MB = Number(process.env.NEXT_PUBLIC_MAX_UPLOAD_MB ?? 25);
const ALLOWED = ["text/csv", "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/octet-stream"];

function configured(): boolean {
  return Boolean(process.env.BLOB_READ_WRITE_TOKEN);
}

export async function POST(request: Request) {
  if (!configured()) {
    return NextResponse.json(
      { error: "Blob uploads are not configured (BLOB_READ_WRITE_TOKEN missing)." },
      { status: 501 },
    );
  }
  const body = (await request.json()) as HandleUploadBody;
  try {
    const json = await handleUpload({
      body,
      request,
      onBeforeGenerateToken: async (pathname) => {
        const lower = pathname.toLowerCase();
        if (!/\.(csv|xlsx|xls)$/.test(lower)) {
          throw new Error("Only .csv, .xlsx and .xls files can be uploaded.");
        }
        return {
          allowedContentTypes: ALLOWED,
          maximumSizeInBytes: MAX_MB * 1024 * 1024,
          addRandomSuffix: true,
        };
      },
      onUploadCompleted: async () => {
        // Nothing to do: the browser passes the blob URL to the API itself.
      },
    });
    return NextResponse.json(json);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e) },
      { status: 400 },
    );
  }
}

// Best-effort cleanup once the analysis has finished.
export async function DELETE(request: Request) {
  if (!configured()) return NextResponse.json({ ok: false }, { status: 501 });
  const url = new URL(request.url).searchParams.get("url");
  if (!url) return NextResponse.json({ error: "url required" }, { status: 400 });
  try {
    await del(url);
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e) },
      { status: 400 },
    );
  }
}
