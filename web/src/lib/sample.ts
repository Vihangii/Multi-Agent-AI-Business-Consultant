// Synthetic daily revenue CSV: trend + weekly + yearly seasonality + noise.
// Same construction as the Streamlit sample generator, with a seeded PRNG so
// the download is reproducible.

function mulberry32(seed: number) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Box–Muller normal sample
function normal(rand: () => number, mean: number, std: number): number {
  const u = 1 - rand();
  const v = rand();
  return mean + std * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function dayOfYear(d: Date): number {
  const start = Date.UTC(d.getUTCFullYear(), 0, 0);
  return Math.floor((d.getTime() - start) / 86_400_000);
}

export function generateSampleCsv(): string {
  const rand = mulberry32(42);
  const start = Date.UTC(2024, 0, 1);
  const end = Date.UTC(2026, 5, 30);
  const n = Math.floor((end - start) / 86_400_000) + 1;

  const rows: string[] = ["TransactionDate,GrossRevenue"];
  for (let i = 0; i < n; i++) {
    const d = new Date(start + i * 86_400_000);
    const trend = 500 + (700 * i) / (n - 1);
    const weekly = 150 * Math.sin((2 * Math.PI * d.getUTCDay()) / 7);
    const yearly = 300 * Math.sin((2 * Math.PI * dayOfYear(d)) / 365.25);
    const noise = normal(rand, 0, 100);
    const revenue = Math.max(100, trend + weekly + yearly + noise);
    rows.push(`${d.toISOString().slice(0, 10)},${revenue.toFixed(2)}`);
  }
  return rows.join("\n") + "\n";
}

export function sampleCsvFile(): File {
  return new File([generateSampleCsv()], "sample_daily_sales.csv", {
    type: "text/csv",
  });
}
