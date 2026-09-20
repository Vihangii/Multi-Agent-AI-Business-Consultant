const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});

const moneyCompact = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});

export function fmtMoney(v: number | null | undefined): string {
  return typeof v === "number" && Number.isFinite(v) ? money.format(v) : "n/a";
}

export function fmtMoneyCompact(v: number): string {
  return moneyCompact.format(v);
}

export function fmtPct(
  v: number | null | undefined,
  opts: { sign?: boolean; digits?: number } = {},
): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return "n/a";
  const digits = opts.digits ?? 2;
  const s = v.toFixed(digits);
  return (opts.sign && v > 0 ? "+" : "") + s + "%";
}

export function fmtInt(v: number | null | undefined): string {
  return typeof v === "number" ? v.toLocaleString("en-US") : "n/a";
}

export function fmtDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function fmtDateShort(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
}
