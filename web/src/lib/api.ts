import type {
  AnalyzeOptions,
  AnalyzeResult,
  HealthResult,
  InspectResult,
} from "./types";

// The browser calls the FastAPI backend directly. Proxying through a Vercel
// serverless function would cap uploads at 4.5 MB, well under the 25 MB limit.
export const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

export const MAX_UPLOAD_MB = Number(process.env.NEXT_PUBLIC_MAX_UPLOAD_MB ?? 25);
export const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;
export const ALLOWED_EXTENSIONS = [".csv", ".xlsx", ".xls"] as const;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function headers(apiKey?: string): HeadersInit {
  return apiKey ? { "X-API-Key": apiKey } : {};
}

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
    return JSON.stringify(body);
  } catch {
    return res.statusText || `HTTP ${res.status}`;
  }
}

/** Client-side validation mirroring backend/io_utils.parse_upload. */
export function validateFile(file: File): string | null {
  const lower = file.name.toLowerCase();
  if (!ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext))) {
    return "Unsupported file format. Please upload a .csv, .xlsx, or .xls file.";
  }
  if (file.size === 0) return "The selected file is empty.";
  if (file.size > MAX_UPLOAD_BYTES) {
    return `File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Maximum upload size is ${MAX_UPLOAD_MB} MB.`;
  }
  return null;
}

export async function getHealth(): Promise<HealthResult> {
  const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return res.json();
}

/**
 * The file is sent either as a multipart body or, when it has already been
 * uploaded to Vercel Blob, as a `file_url` form field the API downloads itself.
 */
export type FileSource = { file: File } | { fileUrl: string };

function sourceForm(src: FileSource): FormData {
  const form = new FormData();
  if ("file" in src) form.append("file", src.file, src.file.name);
  else form.append("file_url", src.fileUrl);
  return form;
}

export async function inspectFile(
  src: FileSource,
  apiKey?: string,
): Promise<InspectResult> {
  const res = await fetch(`${API_URL}/inspect`, {
    method: "POST",
    body: sourceForm(src),
    headers: headers(apiKey),
  });
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return res.json();
}

export async function analyzeFile(
  src: FileSource,
  opts: AnalyzeOptions,
  apiKey?: string,
): Promise<AnalyzeResult> {
  const params = new URLSearchParams();
  params.set("skip_recommendations", String(opts.skipRecommendations));
  if (opts.periods != null) params.set("periods", String(opts.periods));
  if (opts.frequency) params.set("frequency", opts.frequency);
  if (opts.dateColumn) params.set("date_column", opts.dateColumn);
  if (opts.revenueColumn) params.set("revenue_column", opts.revenueColumn);

  const res = await fetch(`${API_URL}/analyze?${params.toString()}`, {
    method: "POST",
    body: sourceForm(src),
    headers: headers(apiKey),
  });
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return res.json();
}
