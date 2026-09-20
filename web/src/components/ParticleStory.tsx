"use client";

// Scroll-driven particle "brain" hero, inspired by cinematic dark landing
// pages: a cloud of coloured triangles morphs brain → scattered field →
// sphere as the user scrolls through a tall story section, while the copy
// switches sides. Pure canvas 2D with a hand-rolled perspective projection —
// no 3D library, ~1,500 particles, pauses off-screen, static under
// prefers-reduced-motion.

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Button, Icon } from "./ui";

const N = 2600;
const PALETTE = ["#f2c94c", "#f2c94c", "#9b7bff", "#7c5cff", "#3ee0c8", "#ffffff", "#ffffff", "#ffd27a", "#ff7ab6"];

type Vec = [number, number, number];

// ---------------------------------------------------------------------------
// Shapes
// ---------------------------------------------------------------------------

function seeded(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function spherePoint(rand: () => number): Vec {
  const u = rand() * 2 - 1;
  const t = rand() * Math.PI * 2;
  const r = Math.sqrt(1 - u * u);
  return [r * Math.cos(t), u, r * Math.sin(t)];
}

/** Bumpy ellipsoid with a central fissure — reads as a brain at a glance. */
function brainShape(rand: () => number): Vec[] {
  const out: Vec[] = [];
  while (out.length < N) {
    const [x, y, z] = spherePoint(rand);
    // gyri: radial bumps from a few sine waves
    const bump = 1 + 0.07 * Math.sin(7 * Math.atan2(z, x)) * Math.cos(5 * Math.asin(y)) + 0.05 * Math.sin(11 * y + 3 * x);
    let px = x * 1.15 * bump;
    const py = y * 0.95 * bump - 0.05;
    const pz = z * 1.35 * bump;
    // longitudinal fissure between hemispheres
    if (Math.abs(px) < 0.06 && py > -0.4) continue;
    px += Math.sign(px) * 0.03;
    // flatten the underside a little (brain stem side)
    if (py < -0.55 && rand() < 0.6) continue;
    // a small portion of particles sit inside as a dense white core
    const inner = rand() < 0.12 ? 0.55 + rand() * 0.35 : 1;
    out.push([px * inner, py * inner, pz * inner]);
  }
  return out;
}

function scatterShape(rand: () => number): Vec[] {
  return Array.from({ length: N }, () => [(rand() * 2 - 1) * 2.6, (rand() * 2 - 1) * 1.7, (rand() * 2 - 1) * 2.2] as Vec);
}

function globeShape(rand: () => number): Vec[] {
  return Array.from({ length: N }, () => {
    const p = spherePoint(rand);
    const r = rand() < 0.08 ? 0.6 + rand() * 0.3 : 1.05;
    return [p[0] * r, p[1] * r, p[2] * r] as Vec;
  });
}

const smooth = (t: number) => t * t * (3 - 2 * t);
const clamp01 = (t: number) => Math.min(1, Math.max(0, t));

// ---------------------------------------------------------------------------
// Canvas
// ---------------------------------------------------------------------------

function ParticleCanvas({ progressRef }: { progressRef: React.MutableRefObject<number> }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    const rand = seeded(7);
    const shapes = [brainShape(rand), scatterShape(rand), globeShape(rand)];
    const colors = Array.from({ length: N }, () => PALETTE[Math.floor(rand() * PALETTE.length)]);
    // Mostly tiny triangles with a few large ones, like a particle render
    const sizes = Array.from({ length: N }, () => (rand() < 0.86 ? 1 + rand() * 1.6 : 3 + rand() * 4));
    const spins = Array.from({ length: N }, () => rand() * Math.PI * 2);
    const spinRates = Array.from({ length: N }, () => (rand() - 0.5) * 1.2);
    const jitter = Array.from({ length: N }, () => rand() * Math.PI * 2);

    let w = 0, h = 0, dpr = 1;
    const resize = () => {
      dpr = Math.min(2, window.devicePixelRatio || 1);
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    let mouseX = 0, mouseY = 0, targetMX = 0, targetMY = 0;
    const onMove = (e: MouseEvent) => {
      targetMX = (e.clientX / window.innerWidth - 0.5) * 2;
      targetMY = (e.clientY / window.innerHeight - 0.5) * 2;
    };
    window.addEventListener("mousemove", onMove, { passive: true });

    let visible = true;
    const io = new IntersectionObserver((es) => { visible = es[0]?.isIntersecting ?? true; }, { threshold: 0 });
    io.observe(canvas);

    const pos: Vec[] = shapes[0].map((p) => [...p] as Vec);
    const depthOrder = Array.from({ length: N }, (_, i) => i);
    let raf = 0;
    let last = performance.now();
    let angle = 0;

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      if (!visible) return;
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const time = now / 1000;

      // Scroll progress → which shapes to blend and where the cloud sits
      const p = clamp01(progressRef.current);
      const seg = p < 0.5 ? 0 : 1; // 0: brain→scatter, 1: scatter→globe
      const t = smooth(clamp01(seg === 0 ? p / 0.5 : (p - 0.5) / 0.5));
      const a = shapes[seg];
      const b = shapes[seg + 1];
      // horizontal position: right (hero) → centre (scatter) → left (globe)
      // On narrow screens the copy stacks over the canvas: keep the cloud
      // small, in the upper third, and dimmer so text stays legible.
      const narrow = w < 1024;
      const offsetX = narrow ? 0 : p < 0.5 ? (1 - t) * 0.22 : -t * 0.22;
      const scale = (narrow ? 0.62 : 1) * (p < 0.5 ? 1 - t * 0.15 : 0.85 + t * 0.2);
      const globalDim = narrow ? 0.55 : 1;

      if (!reduced) {
        angle += dt * 0.18;
        mouseX += (targetMX - mouseX) * 0.04;
        mouseY += (targetMY - mouseY) * 0.04;
      }

      const cosA = Math.cos(angle + mouseX * 0.35);
      const sinA = Math.sin(angle + mouseX * 0.35);
      const tilt = 0.25 + mouseY * 0.2;
      const cosT = Math.cos(tilt);
      const sinT = Math.sin(tilt);
      const R = Math.min(w * 0.42, h * 0.36) * scale;
      const cx = w * (0.5 + offsetX);
      const cy = narrow ? h * 0.3 : h * 0.5;
      const fov = 2.6;

      const projected: { x: number; y: number; s: number; d: number }[] = new Array(N);
      for (let i = 0; i < N; i++) {
        const pa = a[i], pb = b[i];
        // ease-morph toward the blended target with a gentle per-particle drift
        const drift = reduced ? 0 : Math.sin(time * 0.8 + jitter[i]) * 0.02;
        const tx = pa[0] + (pb[0] - pa[0]) * t + drift;
        const ty = pa[1] + (pb[1] - pa[1]) * t + Math.cos(time * 0.7 + jitter[i]) * 0.02 * (reduced ? 0 : 1);
        const tz = pa[2] + (pb[2] - pa[2]) * t;
        const q = pos[i];
        q[0] += (tx - q[0]) * 0.08;
        q[1] += (ty - q[1]) * 0.08;
        q[2] += (tz - q[2]) * 0.08;

        // rotate around Y then tilt around X
        const x1 = q[0] * cosA - q[2] * sinA;
        const z1 = q[0] * sinA + q[2] * cosA;
        const y2 = q[1] * cosT - z1 * sinT;
        const z2 = q[1] * sinT + z1 * cosT;
        const persp = fov / (fov + z2);
        projected[i] = { x: cx + x1 * R * persp, y: cy + y2 * R * persp, s: sizes[i] * persp, d: z2 };
      }

      depthOrder.sort((i, j) => projected[j].d - projected[i].d); // back to front

      ctx.clearRect(0, 0, w, h);
      for (let k = 0; k < N; k++) {
        const i = depthOrder[k];
        const pr = projected[i];
        const depthAlpha = 0.35 + 0.65 * clamp01((1.2 - pr.d) / 2.4);
        ctx.globalAlpha = depthAlpha * globalDim;
        ctx.strokeStyle = colors[i];
        ctx.lineWidth = pr.s > 3 ? 1.2 : 0.8;
        const rot = spins[i] + (reduced ? 0 : time * spinRates[i]);
        const s = pr.s * 1.4;
        ctx.beginPath();
        for (let v = 0; v < 3; v++) {
          const ang = rot + (v * 2 * Math.PI) / 3;
          const vx = pr.x + Math.cos(ang) * s;
          const vy = pr.y + Math.sin(ang) * s;
          if (v === 0) ctx.moveTo(vx, vy);
          else ctx.lineTo(vx, vy);
        }
        ctx.closePath();
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    };

    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      window.removeEventListener("mousemove", onMove);
    };
  }, [progressRef]);

  return <canvas ref={ref} className="h-full w-full" aria-hidden />;
}

// ---------------------------------------------------------------------------
// Story
// ---------------------------------------------------------------------------

const SLIDES = [
  {
    eyebrow: "Five agents · one upload",
    title: ["Turn a sales spreadsheet", "into a fact-checked strategy."],
    text: "Upload a CSV or Excel file. Get a cleaned dataset, a Prophet forecast with real accuracy scores, what-if scenarios, and a strategy report written by an AI agent that queries your data — and is audited by a second one.",
    side: "left" as const,
    cta: true,
  },
  {
    eyebrow: "The problem",
    title: ["Spreadsheets hold the answers.", "Nobody has time to find them."],
    text: "Trends hide in monthly totals, one bad week distorts the average, and forecasts get presented as facts. Decisions end up made on gut feel.",
    side: "center" as const,
    cta: false,
  },
  {
    eyebrow: "The approach",
    title: ["Agents that query,", "check, and correct."],
    text: "A strategist agent pulls the numbers it needs with tools. A critic agent audits every figure it wrote. You get the plan — and the proof.",
    side: "right" as const,
    cta: true,
  },
];

export function ParticleStory() {
  const containerRef = useRef<HTMLDivElement>(null);
  const progressRef = useRef(0);
  const [slide, setSlide] = useState(0);
  const [local, setLocal] = useState(0); // 0..1 within the current slide, for fades

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let raf = 0;
    const update = () => {
      raf = 0;
      const rect = el.getBoundingClientRect();
      const total = rect.height - window.innerHeight;
      const p = total > 0 ? clamp01(-rect.top / total) : 0;
      progressRef.current = p;
      const idx = Math.min(SLIDES.length - 1, Math.floor(p * SLIDES.length));
      setSlide(idx);
      setLocal(p * SLIDES.length - idx);
    };
    const onScroll = () => { if (!raf) raf = requestAnimationFrame(update); };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  // fade text in over the first 20% of each slide and out over the last 15%
  const fadeIn = slide === 0 ? 1 : clamp01(local / 0.2);
  const fadeOut = slide === SLIDES.length - 1 ? 1 : clamp01((1 - local) / 0.15);
  const fade = Math.min(fadeIn, fadeOut);
  const s = SLIDES[slide];
  const align =
    s.side === "left" ? "items-start text-left lg:max-w-[48%]" : s.side === "right" ? "items-end text-right lg:ml-auto lg:max-w-[48%]" : "items-center text-center";

  return (
    <div ref={containerRef} className="relative" style={{ height: `${SLIDES.length * 100}vh` }} data-theme="dark">
      <div className="sticky top-0 h-screen overflow-hidden bg-[#06070a] text-white">
        {/* vignette + subtle grid */}
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(124,92,255,0.14),transparent_60%)]" />
        <div className="pointer-events-none absolute inset-0 opacity-[0.35] [background-image:radial-gradient(rgba(255,255,255,0.12)_1px,transparent_1px)] [background-size:26px_26px]" />

        <div className="absolute inset-0">
          <ParticleCanvas progressRef={progressRef} />
        </div>

        <div className="pointer-events-none relative mx-auto flex h-full max-w-7xl flex-col justify-end px-6 pb-24 lg:justify-center lg:pb-0">
          <div className={`flex flex-col ${align}`} style={{ opacity: fade, transform: `translateY(${(1 - fade) * 14}px)`, transition: "opacity 0.15s linear" }}>
            <span className="mb-4 inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#f2c94c]">
              <Icon name="sparkle" size={11} /> {s.eyebrow}
            </span>
            <h1 className="text-4xl font-semibold leading-[1.05] tracking-tight sm:text-6xl lg:text-7xl">
              {s.title.map((line, i) => (
                <span key={i} className="block">
                  {line}
                </span>
              ))}
            </h1>
            <p className={`mt-6 max-w-xl text-base leading-relaxed text-white/70 sm:text-lg ${s.side === "center" ? "mx-auto" : ""}`}>{s.text}</p>
            {s.cta && (
              <div className={`pointer-events-auto mt-8 flex flex-wrap gap-3 ${s.side === "right" ? "justify-end" : ""}`}>
                <Link href="/app">
                  <Button size="lg" className="bg-[#7c5cff] text-white shadow-[0_0_40px_rgba(124,92,255,0.45)] hover:bg-[#8b6dff]">
                    Open the workspace <Icon name="arrow" size={16} />
                  </Button>
                </Link>
                <a href="#how-it-works">
                  <Button size="lg" className="border border-white/15 bg-white/5 text-white hover:bg-white/10">
                    See how it works
                  </Button>
                </a>
              </div>
            )}
          </div>
        </div>

        {/* progress + scroll hint */}
        <div className="pointer-events-none absolute bottom-6 left-1/2 flex -translate-x-1/2 items-center gap-2">
          {SLIDES.map((_, i) => (
            <span key={i} className={`h-1.5 rounded-full transition-all duration-300 ${i === slide ? "w-8 bg-white" : "w-1.5 bg-white/30"}`} />
          ))}
        </div>
        {slide === 0 && (
          <div className="pointer-events-none absolute bottom-14 left-1/2 -translate-x-1/2 animate-float text-[11px] uppercase tracking-[0.2em] text-white/40">
            Scroll
          </div>
        )}
      </div>
    </div>
  );
}
