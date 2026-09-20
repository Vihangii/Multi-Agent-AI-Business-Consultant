// Server-side schedule store for monthly re-runs.
//
// Schedules are small JSON documents kept in Vercel Blob under `schedules/`,
// one file per schedule — no database to provision, and the Blob store is
// already required for large uploads. `list()` in the cron job enumerates them.

import { del, list, put } from "@vercel/blob";
import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";
import type { AnalyzeOptions } from "./types";

export interface Schedule {
  id: string;
  email: string;
  fileUrl: string; // the dataset, already in Blob
  fileName: string;
  options: AnalyzeOptions;
  createdAt: string;
  lastRunAt?: string;
  lastStatus?: "ok" | "error";
  lastError?: string;
}

const PREFIX = "schedules/";

export function schedulesConfigured(): boolean {
  return Boolean(process.env.BLOB_READ_WRITE_TOKEN);
}

export function emailConfigured(): boolean {
  return Boolean(process.env.RESEND_API_KEY);
}

/** HMAC of the id — put in unsubscribe links so only the recipient can delete. */
export function unsubscribeToken(id: string): string {
  const secret = process.env.CRON_SECRET ?? process.env.BLOB_READ_WRITE_TOKEN ?? "dev";
  return createHmac("sha256", secret).update(id).digest("hex").slice(0, 32);
}

export function verifyUnsubscribeToken(id: string, token: string): boolean {
  const expected = unsubscribeToken(id);
  return token.length === expected.length && timingSafeEqual(Buffer.from(token), Buffer.from(expected));
}

function pathFor(id: string) {
  return `${PREFIX}${id}.json`;
}

export async function saveSchedule(s: Schedule): Promise<void> {
  await put(pathFor(s.id), JSON.stringify(s), {
    access: "public", // Vercel Blob has no private mode; ids are unguessable (128-bit)
    addRandomSuffix: false,
    allowOverwrite: true,
    contentType: "application/json",
  });
}

export async function createSchedule(input: Omit<Schedule, "id" | "createdAt">): Promise<Schedule> {
  const s: Schedule = { ...input, id: randomBytes(16).toString("hex"), createdAt: new Date().toISOString() };
  await saveSchedule(s);
  return s;
}

export async function listSchedules(): Promise<Schedule[]> {
  const out: Schedule[] = [];
  let cursor: string | undefined;
  do {
    const page = await list({ prefix: PREFIX, cursor, limit: 100 });
    for (const b of page.blobs) {
      try {
        const res = await fetch(b.url, { cache: "no-store" });
        if (res.ok) out.push((await res.json()) as Schedule);
      } catch {
        /* skip unreadable */
      }
    }
    cursor = page.hasMore ? page.cursor : undefined;
  } while (cursor);
  return out;
}

export async function findSchedule(id: string): Promise<{ schedule: Schedule; url: string } | null> {
  const page = await list({ prefix: pathFor(id), limit: 1 });
  const b = page.blobs[0];
  if (!b) return null;
  const res = await fetch(b.url, { cache: "no-store" });
  if (!res.ok) return null;
  return { schedule: (await res.json()) as Schedule, url: b.url };
}

export async function deleteSchedule(id: string): Promise<boolean> {
  const found = await findSchedule(id);
  if (!found) return false;
  await del(found.url);
  return true;
}
