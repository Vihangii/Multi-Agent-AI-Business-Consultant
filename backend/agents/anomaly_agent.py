"""
Anomaly Agent
Flags days/weeks/months where revenue departed sharply from what the fitted
model expected, so the strategist can ask "explain or exclude?" instead of
silently averaging shocks into its advice.

Two detectors:
  1. Point anomalies — robust z-score of Prophet's in-sample residual
     (actual − predicted) using the median and MAD, so a handful of extreme
     days can't inflate the scale and hide themselves.
  2. Period shocks — month-over-month totals that drop or spike far beyond
     the dataset's typical monthly change.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# |robust z| at or above this is an anomaly (3.5 is the conventional MAD threshold)
Z_THRESHOLD = 3.5
Z_HIGH = 5.0
# Month-over-month change flagged when it exceeds this many robust SDs of the
# usual monthly change, and is at least this big in absolute % terms
MONTHLY_Z_THRESHOLD = 2.5
MONTHLY_MIN_ABS_PCT = 25.0
MAX_POINTS = 20


def _robust_z(values: np.ndarray) -> np.ndarray:
    med = np.median(values)
    mad = np.median(np.abs(values - med))
    if mad == 0:
        # Fall back to std when the middle of the distribution is flat
        sd = values.std()
        return np.zeros_like(values) if sd == 0 else (values - med) / sd
    return 0.6745 * (values - med) / mad


def detect_anomalies(cleaned_df: pd.DataFrame, forecast_df: pd.DataFrame) -> dict:
    """
    Args:
        cleaned_df: ['ds', 'y'] history from the Data Agent.
        forecast_df: ['ds', 'predicted', 'lower_bound', 'upper_bound'] from the
            Forecast Agent (history + future). Only the historical rows are used.

    Returns:
        {
          "points": [ {date, actual, expected, deviation, deviation_percent,
                       z_score, direction, severity, outside_interval}, ... ],
          "periods": [ {period, revenue, previous_revenue, change_percent,
                        direction, severity}, ... ],
          "summary": {point_count, spike_count, drop_count, largest_drop, largest_spike,
                      period_count, anomalous_share_percent}
        }
    """
    hist = cleaned_df[["ds", "y"]].copy()
    hist["ds"] = pd.to_datetime(hist["ds"])
    fc = forecast_df[["ds", "predicted", "lower_bound", "upper_bound"]].copy()
    fc["ds"] = pd.to_datetime(fc["ds"])
    merged = hist.merge(fc, on="ds", how="inner").dropna(subset=["y", "predicted"])

    points: list[dict] = []
    if len(merged) >= 10:
        resid = (merged["y"] - merged["predicted"]).to_numpy(dtype=float)
        z = _robust_z(resid)
        merged = merged.assign(z=z)
        flagged = merged[np.abs(merged["z"]) >= Z_THRESHOLD].copy()
        flagged["absz"] = flagged["z"].abs()
        flagged = flagged.sort_values("absz", ascending=False).head(MAX_POINTS)
        for _, r in flagged.sort_values("ds").iterrows():
            expected = float(r["predicted"])
            actual = float(r["y"])
            dev = actual - expected
            points.append({
                "date": str(r["ds"].date()),
                "actual": round(actual, 2),
                "expected": round(expected, 2),
                "deviation": round(dev, 2),
                "deviation_percent": round(dev / expected * 100, 2) if expected else None,
                "z_score": round(float(r["z"]), 2),
                "direction": "spike" if dev > 0 else "drop",
                "severity": "high" if abs(r["z"]) >= Z_HIGH else "medium",
                "outside_interval": bool(actual < r["lower_bound"] or actual > r["upper_bound"]),
            })

    # Period-level shocks (monthly)
    periods: list[dict] = []
    monthly = hist.set_index("ds")["y"].resample("MS").sum()
    if len(monthly) >= 4:
        change = monthly.pct_change().dropna() * 100
        change = change.replace([np.inf, -np.inf], np.nan).dropna()
        if len(change) >= 3:
            zc = _robust_z(change.to_numpy(dtype=float))
            for (period, pct), zval in zip(change.items(), zc):
                if abs(zval) >= MONTHLY_Z_THRESHOLD and abs(pct) >= MONTHLY_MIN_ABS_PCT:
                    prev = monthly.shift(1)[period]
                    periods.append({
                        "period": period.strftime("%Y-%m"),
                        "revenue": round(float(monthly[period]), 2),
                        "previous_revenue": round(float(prev), 2),
                        "change_percent": round(float(pct), 2),
                        "direction": "spike" if pct > 0 else "drop",
                        "severity": "high" if abs(zval) >= Z_HIGH else "medium",
                    })

    spikes = [p for p in points if p["direction"] == "spike"]
    drops = [p for p in points if p["direction"] == "drop"]
    summary = {
        "point_count": len(points),
        "spike_count": len(spikes),
        "drop_count": len(drops),
        "largest_drop": min(drops, key=lambda p: p["deviation"]) if drops else None,
        "largest_spike": max(spikes, key=lambda p: p["deviation"]) if spikes else None,
        "period_count": len(periods),
        "anomalous_share_percent": round(len(points) / len(merged) * 100, 2) if len(merged) else 0.0,
    }
    return {"points": points, "periods": periods, "summary": summary}


def anomalies_for_prompt(anomalies: dict | None, limit: int = 6) -> str:
    """Compact text block for the strategist's context."""
    if not anomalies or (not anomalies["points"] and not anomalies["periods"]):
        return "No significant anomalies were detected."
    lines = []
    pts = sorted(anomalies["points"], key=lambda p: abs(p["z_score"]), reverse=True)[:limit]
    for p in pts:
        lines.append(
            f"  - {p['date']}: {p['direction']} — actual {p['actual']:,.2f} vs expected {p['expected']:,.2f} "
            f"({p['deviation_percent']:+.1f}%, z={p['z_score']}, {p['severity']})"
        )
    for q in anomalies["periods"][:limit]:
        lines.append(
            f"  - Month {q['period']}: {q['direction']} of {q['change_percent']:+.1f}% vs previous month "
            f"({q['revenue']:,.2f} vs {q['previous_revenue']:,.2f})"
        )
    s = anomalies["summary"]
    head = (
        f"{s['point_count']} anomalous data points ({s['spike_count']} spikes, {s['drop_count']} drops; "
        f"{s['anomalous_share_percent']}% of history) and {s['period_count']} monthly shocks. "
        "For each, decide whether it is a one-off to exclude from planning or a signal to act on."
    )
    return head + "\n" + "\n".join(lines)
