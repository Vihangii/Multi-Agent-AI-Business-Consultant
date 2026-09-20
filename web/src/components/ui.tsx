"use client";

import type { ReactNode } from "react";
import { CountUp } from "./motion";

// ---------------------------------------------------------------------------
// Layout primitives
// ---------------------------------------------------------------------------

export function Card({
  children,
  className = "",
  padded = true,
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <section
      className={`rounded-[var(--radius-card)] border border-border bg-surface shadow-card ${padded ? "p-5" : ""} ${className}`}
    >
      {children}
    </section>
  );
}

export function SectionTitle({
  children,
  action,
  hint,
}: {
  children: ReactNode;
  action?: ReactNode;
  hint?: string;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
      <div>
        <h2 className="text-[15px] font-semibold tracking-tight text-text">{children}</h2>
        {hint && <p className="mt-0.5 text-xs text-muted">{hint}</p>}
      </div>
      {action}
    </div>
  );
}

export function Label({
  children,
  htmlFor,
  hint,
}: {
  children: ReactNode;
  htmlFor?: string;
  hint?: string;
}) {
  return (
    <label
      htmlFor={htmlFor}
      className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.08em] text-muted"
      title={hint}
    >
      {children}
    </label>
  );
}

// ---------------------------------------------------------------------------
// Controls
// ---------------------------------------------------------------------------

export function Select({
  id,
  value,
  onChange,
  options,
  disabled,
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  disabled?: boolean;
}) {
  return (
    <div className="relative">
      <select
        id={id}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="w-full appearance-none rounded-lg border border-border bg-surface py-2 pl-3 pr-9 text-sm text-text shadow-card transition hover:border-border-strong disabled:cursor-not-allowed disabled:opacity-50"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <svg
        aria-hidden
        viewBox="0 0 20 20"
        className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
        fill="currentColor"
      >
        <path d="M5.5 7.5 10 12l4.5-4.5" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "light";
const variantClass: Record<ButtonVariant, string> = {
  primary:
    "bg-accent text-accent-ink shadow-card hover:bg-accent-hover disabled:hover:bg-accent",
  secondary:
    "border border-border bg-surface text-text shadow-card hover:border-border-strong hover:bg-surface-2",
  ghost: "text-text-2 hover:bg-surface-2 hover:text-text",
  danger: "bg-bad text-white hover:opacity-90",
  // For use on colored/gradient backgrounds: fixed colors regardless of theme
  light: "bg-white text-[#1e3a8a] shadow-card hover:bg-white/90",
};

export function Button({
  children,
  variant = "secondary",
  size = "md",
  className = "",
  type = "button",
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "sm" | "md" | "lg";
}) {
  const sizeClass = size === "sm" ? "px-2.5 py-1.5 text-xs" : size === "lg" ? "px-5 py-3 text-[15px]" : "px-3.5 py-2 text-sm";
  return (
    <button
      type={type}
      className={`press inline-flex items-center justify-center gap-2 rounded-lg font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${variantClass[variant]} ${sizeClass} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Feedback
// ---------------------------------------------------------------------------

type Tone = "info" | "good" | "warn" | "bad";
const toneClass: Record<Tone, string> = {
  info: "bg-info-bg text-text border-accent/25",
  good: "bg-good-bg text-good border-good/25",
  warn: "bg-warn-bg text-warn border-warn/25",
  bad: "bg-bad-bg text-bad border-bad/25",
};
const toneIcon: Record<Tone, ReactNode> = {
  info: <Icon name="info" />,
  good: <Icon name="check" />,
  warn: <Icon name="alert" />,
  bad: <Icon name="x" />,
};

export function Notice({
  tone,
  children,
  className = "",
}: {
  tone: Tone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      role={tone === "bad" ? "alert" : "status"}
      className={`flex items-start gap-2.5 rounded-lg border px-3 py-2.5 text-sm ${toneClass[tone]} ${className}`}
    >
      <span aria-hidden className="mt-0.5 shrink-0">
        {toneIcon[tone]}
      </span>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

export function Metric({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "good" | "bad" | "muted";
}) {
  const color =
    tone === "good" ? "text-good" : tone === "bad" ? "text-bad" : tone === "muted" ? "text-muted" : "text-text";
  return (
    <div className="rounded-xl border border-border bg-surface-2/60 px-4 py-3.5">
      <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">{label}</div>
      <div className={`mt-1.5 text-[26px] font-semibold leading-none tracking-tight tabular ${color}`}>
        <CountUp value={value} />
      </div>
      {hint && <div className="mt-2 text-xs text-muted">{hint}</div>}
    </div>
  );
}

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent ${className}`}
      aria-hidden
    />
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden />;
}

export function Badge({
  children,
  tone = "neutral",
  className = "",
}: {
  children: ReactNode;
  tone?: "neutral" | "accent" | "good" | "warn" | "bad";
  className?: string;
}) {
  const cls = {
    neutral: "border-border bg-surface-2 text-text-2",
    accent: "border-accent/30 bg-accent-soft text-accent",
    good: "border-good/30 bg-good-bg text-good",
    warn: "border-warn/30 bg-warn-bg text-warn",
    bad: "border-bad/30 bg-bad-bg text-bad",
  }[tone];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${cls} ${className}`}>
      {children}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Stepper (pipeline stages)
// ---------------------------------------------------------------------------

export function Stepper({
  steps,
  active,
  doneThrough,
}: {
  steps: { label: string; icon?: ReactNode }[];
  active: number; // index of the step in progress (-1 for none)
  doneThrough: number; // last completed index
}) {
  return (
    <ol className="flex flex-wrap items-center gap-2">
      {steps.map((s, i) => {
        const done = i <= doneThrough;
        const isActive = i === active;
        return (
          <li key={s.label} className="flex items-center gap-2">
            <span
              className={`flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-xs font-medium transition ${
                done
                  ? "border-good/30 bg-good-bg text-good"
                  : isActive
                    ? "border-accent/40 bg-accent-soft text-accent"
                    : "border-border bg-surface-2 text-muted"
              }`}
            >
              {done ? <span className="animate-pop inline-flex"><Icon name="check" size={12} /></span> : isActive ? <Spinner className="h-3 w-3" /> : <span className="tabular">{i + 1}</span>}
              {s.label}
            </span>
            {i < steps.length - 1 && <span className="h-px w-3 bg-border" aria-hidden />}
          </li>
        );
      })}
    </ol>
  );
}

// ---------------------------------------------------------------------------
// Icons (inline, no dependency)
// ---------------------------------------------------------------------------

const paths: Record<string, ReactNode> = {
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 8h.01" />
    </>
  ),
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  alert: (
    <>
      <path d="M12 4 2.5 20h19L12 4z" />
      <path d="M12 10v4M12 17h.01" />
    </>
  ),
  x: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m9 9 6 6M15 9l-6 6" />
    </>
  ),
  upload: (
    <>
      <path d="M12 16V4M6 10l6-6 6 6" />
      <path d="M4 20h16" />
    </>
  ),
  download: (
    <>
      <path d="M12 4v12M6 10l6 6 6-6" />
      <path d="M4 20h16" />
    </>
  ),
  play: <path d="M7 4.5v15l12-7.5-12-7.5z" />,
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </>
  ),
  moon: <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z" />,
  monitor: (
    <>
      <rect x="3" y="4" width="18" height="12" rx="2" />
      <path d="M8 20h8M12 16v4" />
    </>
  ),
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  file: (
    <>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5z" />
      <path d="M14 3v5h5M9 13h6M9 17h6" />
    </>
  ),
  sparkle: <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3zM5 18l.7 1.8L7.5 20.5l-1.8.7L5 23l-.7-1.8-1.8-.7 1.8-.7L5 18z" />,
  chart: (
    <>
      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
    </>
  ),
  shield: <path d="M12 3 4 6v6c0 5 3.5 8.5 8 9 4.5-.5 8-4 8-9V6l-8-3zM9 12l2 2 4-4" />,
  bolt: <path d="M13 2 4 14h6l-1 8 9-12h-6l1-8z" />,
  mail: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3 7 9 6 9-6" />
    </>
  ),
  github: (
    <path d="M12 2a10 10 0 0 0-3.2 19.5c.5.1.7-.2.7-.5v-1.8c-2.8.6-3.4-1.2-3.4-1.2-.4-1.1-1.1-1.4-1.1-1.4-.9-.6.1-.6.1-.6 1 .1 1.5 1 1.5 1 .9 1.6 2.4 1.1 3 .9.1-.7.4-1.1.6-1.4-2.2-.2-4.6-1.1-4.6-5a3.9 3.9 0 0 1 1-2.7c-.1-.3-.5-1.3.1-2.7 0 0 .9-.3 2.8 1a9.6 9.6 0 0 1 5 0c1.9-1.3 2.8-1 2.8-1 .6 1.4.2 2.4.1 2.7a3.9 3.9 0 0 1 1 2.7c0 3.9-2.4 4.8-4.6 5 .4.3.7.9.7 1.9v2.8c0 .3.2.6.7.5A10 10 0 0 0 12 2z" />
  ),
};

export function Icon({ name, size = 16, className = "" }: { name: keyof typeof paths | string; size?: number; className?: string }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`shrink-0 ${className}`}
    >
      {paths[name] ?? null}
    </svg>
  );
}
