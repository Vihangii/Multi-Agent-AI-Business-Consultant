import { upload } from "@vercel/blob/client";

/**
 * Upload a file straight from the browser to Vercel Blob and return its URL.
 * Used for files too large to POST to a Vercel function (> 4.5 MB).
 * Throws if the app has no Blob store configured.
 */
export async function uploadToBlob(file: File): Promise<string> {
  const blob = await upload(file.name, file, {
    access: "public",
    handleUploadUrl: "/api/upload",
    contentType: file.type || "application/octet-stream",
  });
  return blob.url;
}

/** Delete a blob once the analysis is done. Failures are ignored. */
export async function deleteBlob(url: string): Promise<void> {
  try {
    await fetch(`/api/upload?url=${encodeURIComponent(url)}`, { method: "DELETE" });
  } catch {
    /* best effort */
  }
}
