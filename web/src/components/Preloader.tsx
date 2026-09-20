"use client";

// Branded preloader shown on every full page load / refresh.
//
// It is rendered in the initial (server) HTML so it is visible from the very
// first paint — the CSS animations run before React hydrates. Once the page
// is interactive and fonts are ready (and a short minimum time has passed so
// the animation reads as intentional) it fades out and unmounts.

import { useEffect, useState } from "react";

const MIN_MS = 1100; // minimum time on screen
const EXIT_MS = 550; // fade-out duration (matches CSS)

export function Preloader() {
  const [phase, setPhase] = useState<"in" | "out" | "gone">("in");

  useEffect(() => {
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    const started = performance.now();
    let cancelled = false;
    let exitTimer: ReturnType<typeof setTimeout> | undefined;

    const finish = () => {
      if (cancelled) return;
      const wait = reduced ? 0 : Math.max(0, MIN_MS - (performance.now() - started));
      exitTimer = setTimeout(() => {
        setPhase("out");
        exitTimer = setTimeout(() => setPhase("gone"), reduced ? 0 : EXIT_MS);
      }, wait);
    };

    const fonts = (document as Document & { fonts?: FontFaceSet }).fonts;
    if (fonts?.ready) fonts.ready.then(finish, finish);
    else finish();

    return () => {
      cancelled = true;
      if (exitTimer) clearTimeout(exitTimer);
    };
  }, []);

  if (phase === "gone") return null;

  return (
    <div
      aria-hidden
      className={`preloader fixed inset-0 z-[100] flex flex-col items-center justify-center bg-page text-text ${phase === "out" ? "preloader-out" : ""}`}
    >
      <div className="relative">
        <svg viewBox="0 0 64 64" width="72" height="72" className="preloader-logo">
          <defs>
            <linearGradient id="plg" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#2a78d6" />
              <stop offset="1" stopColor="#1baf7a" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="56" height="56" rx="14" fill="url(#plg)" className="preloader-tile" />
          <path
            d="M16 42 L26 30 L34 36 L48 20"
            fill="none"
            stroke="#fff"
            strokeWidth="5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="preloader-line"
          />
          <circle cx="48" cy="20" r="4.5" fill="#fff" className="preloader-dot" />
        </svg>
        <span className="preloader-ring absolute inset-0 -m-3 rounded-[22px] border border-accent/40" />
      </div>
      <div className="preloader-text mt-6 text-[15px] font-semibold tracking-tight">
        AI Business <span className="text-text-2">Consultant</span>
      </div>
      <div className="mt-5 h-0.5 w-40 overflow-hidden rounded-full bg-surface-3">
        <div className="preloader-bar h-full rounded-full bg-accent" />
      </div>
    </div>
  );
}
