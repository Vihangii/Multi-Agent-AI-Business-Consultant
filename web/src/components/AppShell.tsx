"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import type { HealthResult } from "@/lib/types";
import { Preloader } from "./Preloader";
import { Badge, Icon } from "./ui";

export function Logo({ size = 28 }: { size?: number }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <svg viewBox="0 0 64 64" width={size} height={size} aria-hidden>
        <defs>
          <linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#2a78d6" />
            <stop offset="1" stopColor="#1baf7a" />
          </linearGradient>
        </defs>
        <rect x="4" y="4" width="56" height="56" rx="14" fill="url(#lg)" />
        <path d="M16 42 L26 30 L34 36 L48 20" fill="none" stroke="#fff" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="48" cy="20" r="4.5" fill="#fff" />
      </svg>
      <span className="text-[15px] font-semibold tracking-tight">
        AI Business <span className="text-text-2">Consultant</span>
      </span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Theme toggle: system → light → dark
// ---------------------------------------------------------------------------

type Theme = "system" | "light" | "dark";

function readStoredTheme(): Theme {
  if (typeof window === "undefined") return "system";
  try {
    const t = localStorage.getItem("theme");
    return t === "light" || t === "dark" ? t : "system";
  } catch {
    return "system";
  }
}

function useTheme(): [Theme, (t: Theme) => void] {
  // Server renders "system"; the client re-reads storage after hydration so
  // the icon matches what the pre-paint script in layout.tsx applied.
  const [theme, setTheme] = useState<Theme>("system");
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => {
      setTheme(readStoredTheme());
      setHydrated(true);
    });
    return () => cancelAnimationFrame(id);
  }, []);
  void hydrated;
  const apply = (t: Theme) => {
    setTheme(t);
    try {
      if (t === "system") {
        localStorage.removeItem("theme");
        document.documentElement.removeAttribute("data-theme");
      } else {
        localStorage.setItem("theme", t);
        document.documentElement.setAttribute("data-theme", t);
      }
    } catch {
      /* ignore */
    }
  };
  return [theme, apply];
}

export function ThemeToggle() {
  const [theme, setTheme] = useTheme();
  const next: Record<Theme, Theme> = { system: "light", light: "dark", dark: "system" };
  const icon = theme === "light" ? "sun" : theme === "dark" ? "moon" : "monitor";
  return (
    <button
      type="button"
      onClick={() => setTheme(next[theme])}
      title={`Theme: ${theme} (click to change)`}
      aria-label={`Theme: ${theme}`}
      className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface text-text-2 transition hover:border-border-strong hover:text-text"
    >
      <Icon name={icon} size={17} />
    </button>
  );
}

// ---------------------------------------------------------------------------
// Status pill
// ---------------------------------------------------------------------------

export function ApiStatus({ health, error }: { health: HealthResult | null; error: string | null }) {
  if (error) {
    return (
      <Badge tone="bad">
        <span className="h-1.5 w-1.5 rounded-full bg-current" /> API offline
      </Badge>
    );
  }
  if (!health) {
    return (
      <Badge tone="neutral">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" /> Connecting…
      </Badge>
    );
  }
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <Badge tone="good">
        <span className="h-1.5 w-1.5 rounded-full bg-current" /> API online
      </Badge>
      {health.llm_configured ? (
        <Badge tone="accent" className="hidden sm:inline-flex">
          <Icon name="sparkle" size={11} /> {health.llm_provider} · {health.llm_model}
        </Badge>
      ) : (
        <Badge tone="warn" className="hidden sm:inline-flex">no LLM key</Badge>
      )}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Shell
// ---------------------------------------------------------------------------

export function AppShell({
  children,
  health,
  healthError,
  onToggleSidebar,
  fullBleed = false,
  dark = false,
}: {
  children: ReactNode;
  health?: HealthResult | null;
  healthError?: string | null;
  onToggleSidebar?: () => void;
  fullBleed?: boolean;
  /** Force the dark palette for this page (e.g. the cinematic landing page). */
  dark?: boolean;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-page text-text" data-theme={dark ? "dark" : undefined}>
      <Preloader />
      <header className="sticky top-0 z-30 border-b border-border bg-surface/85 backdrop-blur supports-[backdrop-filter]:bg-surface/70">
        <div className={`flex h-14 items-center gap-3 px-4 ${fullBleed ? "" : "mx-auto max-w-7xl"}`}>
          {onToggleSidebar && (
            <button
              type="button"
              onClick={onToggleSidebar}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface text-text-2 hover:text-text lg:hidden"
              aria-label="Toggle configuration panel"
            >
              <Icon name="menu" size={18} />
            </button>
          )}
          <Link href="/" className="shrink-0">
            <Logo />
          </Link>
          <nav className="ml-4 hidden items-center gap-1 text-sm md:flex">
            <Link href="/app" className="rounded-md px-2.5 py-1.5 text-text-2 hover:bg-surface-2 hover:text-text">
              Workspace
            </Link>
            <Link href="/#how-it-works" className="rounded-md px-2.5 py-1.5 text-text-2 hover:bg-surface-2 hover:text-text">
              How it works
            </Link>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {health !== undefined && <ApiStatus health={health ?? null} error={healthError ?? null} />}
            {!dark && <ThemeToggle />}
          </div>
        </div>
      </header>

      <div className="flex flex-1 flex-col">{children}</div>

      <footer className="border-t border-border bg-surface">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-2 px-4 py-5 text-xs text-muted sm:flex-row">
          <span>© {new Date().getFullYear()} Multi-Agent AI Business Consultant</span>
          <span>FastAPI · Prophet · Next.js</span>
        </div>
      </footer>
    </div>
  );
}
