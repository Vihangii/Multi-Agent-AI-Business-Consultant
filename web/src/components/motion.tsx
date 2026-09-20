"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/** Fades/slides children in when they scroll into view (once). */
export function Reveal({
  children,
  className = "",
  delay = 0,
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  as?: "div" | "section" | "li" | "ol" | "ul";
}) {
  const ref = useRef<HTMLElement | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      // Old browsers / crawlers: show immediately (deferred a frame to avoid a sync setState)
      const id = requestAnimationFrame(() => setInView(true));
      return () => cancelAnimationFrame(id);
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            setInView(true);
            io.disconnect();
          }
        }
      },
      { rootMargin: "0px 0px -10% 0px", threshold: 0.1 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const Comp = Tag as unknown as "div";
  return (
    <Comp
      ref={ref as React.RefObject<HTMLDivElement>}
      className={`reveal ${inView ? "in" : ""} ${className}`}
      style={delay ? { transitionDelay: `${delay}ms` } : undefined}
    >
      {children}
    </Comp>
  );
}

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

/**
 * Animates the first number inside a formatted string from 0 to its value,
 * preserving prefix/suffix, thousands separators and decimals — so
 * "$1,234.56" counts up as "$0.00" → "$1,234.56" and "+12.3%" as "+0.0%" → "+12.3%".
 */
export function CountUp({ value, duration = 900, className = "" }: { value: string; duration?: number; className?: string }) {
  const [display, setDisplay] = useState(value);

  useEffect(() => {
    const m = /-?\d[\d,]*(?:\.\d+)?/.exec(value);
    if (!m || prefersReducedMotion()) {
      const id = requestAnimationFrame(() => setDisplay(value));
      return () => cancelAnimationFrame(id);
    }
    const numStr = m[0];
    const target = parseFloat(numStr.replace(/,/g, ""));
    const decimals = (numStr.split(".")[1] ?? "").length;
    const grouped = numStr.includes(",");
    const prefix = value.slice(0, m.index);
    const suffix = value.slice(m.index + numStr.length);
    const fmt = (n: number) =>
      prefix +
      (grouped ? n.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) : n.toFixed(decimals)) +
      suffix;

    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      setDisplay(fmt(target * easeOut(t)));
      if (t < 1) raf = requestAnimationFrame(tick);
      else setDisplay(value);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);

  return <span className={className}>{display}</span>;
}
