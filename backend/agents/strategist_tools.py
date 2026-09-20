"""
Tools the strategist agent can call to query the analysed data.

Each tool is a plain function over a `DataContext`; `TOOL_SPECS` describes
them to the model in provider-neutral JSON schema. Results are returned as
JSON strings so any provider can carry them back as tool results.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd

from backend.llm import ToolSpec


@dataclass
class DataContext:
    cleaned_df: pd.DataFrame  # ['ds', 'y', ...]
    analysis: dict
    forecast_summary: dict
    whatif: dict | None = None
    anomalies: dict | None = None
    granularity: str = "daily"
    extra: dict = field(default_factory=dict)


def _js(obj: Any) -> str:
    return json.dumps(obj, default=str)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def get_monthly_breakdown(ctx: DataContext, last_n: int = 24) -> str:
    """Revenue per calendar month with month-over-month change."""
    df = ctx.cleaned_df.copy()
    df["ds"] = pd.to_datetime(df["ds"])
    m = df.set_index("ds")["y"].resample("MS").sum()
    pct = m.pct_change() * 100
    rows = [
        {
            "month": d.strftime("%Y-%m"),
            "revenue": round(float(v), 2),
            "change_percent": None if pd.isna(pct[d]) else round(float(pct[d]), 2),
            "days_with_data": int(df[(df["ds"] >= d) & (df["ds"] < d + pd.offsets.MonthBegin(1))].shape[0]),
        }
        for d, v in m.items()
    ]
    return _js({"months": rows[-max(1, int(last_n)):], "total_months": len(rows)})


def get_top_periods(ctx: DataContext, kind: str = "best", n: int = 5, granularity: str = "month") -> str:
    """Best or worst N months (or single days/weeks) by revenue."""
    df = ctx.cleaned_df.copy()
    df["ds"] = pd.to_datetime(df["ds"])
    if granularity == "day":
        s = df.set_index("ds")["y"]
        fmt = "%Y-%m-%d"
    elif granularity == "week":
        s = df.set_index("ds")["y"].resample("W").sum()
        fmt = "week of %Y-%m-%d"
    else:
        s = df.set_index("ds")["y"].resample("MS").sum()
        fmt = "%Y-%m"
    s = s.sort_values(ascending=(kind == "worst")).head(max(1, min(int(n), 20)))
    return _js({"kind": kind, "granularity": granularity, "periods": [
        {"period": d.strftime(fmt), "revenue": round(float(v), 2)} for d, v in s.items()
    ]})


def compare_periods(ctx: DataContext, start_a: str, end_a: str, start_b: str, end_b: str) -> str:
    """Total revenue in two date ranges and the difference between them."""
    df = ctx.cleaned_df.copy()
    df["ds"] = pd.to_datetime(df["ds"])

    def total(s: str, e: str) -> tuple[float, int]:
        sel = df[(df["ds"] >= pd.Timestamp(s)) & (df["ds"] <= pd.Timestamp(e))]
        return float(sel["y"].sum()), int(len(sel))

    try:
        a, na = total(start_a, end_a)
        b, nb = total(start_b, end_b)
    except (ValueError, TypeError) as e:
        return _js({"error": f"Could not parse dates: {e}"})
    diff = b - a
    return _js({
        "period_a": {"start": start_a, "end": end_a, "revenue": round(a, 2), "records": na},
        "period_b": {"start": start_b, "end": end_b, "revenue": round(b, 2), "records": nb},
        "difference": round(diff, 2),
        "difference_percent": round(diff / a * 100, 2) if a else None,
    })


def get_weekday_profile(ctx: DataContext) -> str:
    """Average revenue by day of week (daily data only)."""
    if ctx.granularity != "daily":
        return _js({"error": "Weekday profile needs daily data; this dataset is " + ctx.granularity})
    df = ctx.cleaned_df.copy()
    df["ds"] = pd.to_datetime(df["ds"])
    prof = df.groupby(df["ds"].dt.day_name())["y"].mean()
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    rows = [{"weekday": d, "avg_revenue": round(float(prof[d]), 2)} for d in order if d in prof]
    overall = float(df["y"].mean())
    for r in rows:
        r["vs_average_percent"] = round((r["avg_revenue"] - overall) / overall * 100, 2) if overall else None
    return _js({"weekdays": rows, "overall_avg": round(overall, 2)})


def get_forecast_summary(ctx: DataContext) -> str:
    """The forecast horizon, trend, end value, confidence interval and backtest accuracy."""
    return _js(ctx.forecast_summary)


def get_anomalies(ctx: DataContext, limit: int = 10) -> str:
    """Days and months where revenue departed sharply from the model's expectation."""
    a = ctx.anomalies or {"points": [], "periods": [], "summary": {}}
    pts = sorted(a["points"], key=lambda p: abs(p["z_score"]), reverse=True)[: max(1, int(limit))]
    return _js({"points": pts, "periods": a["periods"][: max(1, int(limit))], "summary": a["summary"]})


def what_if(ctx: DataContext, change_percent: float) -> str:
    """Forecast totals if the driver (or revenue) changes by change_percent; interpolates between precomputed scenarios."""
    w = ctx.whatif
    if not w or not w.get("scenarios"):
        return _js({"error": "No what-if scenarios are available for this run."})
    scen = sorted(w["scenarios"], key=lambda s: s["change_percent"])
    steps = [s["change_percent"] for s in scen]
    x = float(change_percent)
    if x <= steps[0] or x >= steps[-1]:
        s = scen[0] if x <= steps[0] else scen[-1]
        note = f"clamped to the nearest precomputed scenario ({s['change_percent']:+d}%)"
        chosen = {k: v for k, v in s.items() if k != "series"}
    else:
        lo = max((s for s in scen if s["change_percent"] <= x), key=lambda s: s["change_percent"])
        hi = min((s for s in scen if s["change_percent"] >= x), key=lambda s: s["change_percent"])
        if lo is hi:
            chosen, note = {k: v for k, v in lo.items() if k != "series"}, "exact precomputed scenario"
        else:
            t = (x - lo["change_percent"]) / (hi["change_percent"] - lo["change_percent"])
            chosen = {"change_percent": x}
            for k in ("driver_value", "forecast_end_value", "avg_forecasted_value", "total_forecasted", "delta_vs_baseline", "delta_vs_baseline_percent"):
                a, b = lo.get(k), hi.get(k)
                chosen[k] = round(a + (b - a) * t, 2) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None
            note = f"linear interpolation between {lo['change_percent']:+d}% and {hi['change_percent']:+d}%"
    return _js({"driver": w.get("driver"), "method": w.get("method"), "baseline_driver_value": w.get("baseline_driver_value"), "scenario": chosen, "note": note})


TOOLS: dict[str, Callable[..., str]] = {
    "get_monthly_breakdown": get_monthly_breakdown,
    "get_top_periods": get_top_periods,
    "compare_periods": compare_periods,
    "get_weekday_profile": get_weekday_profile,
    "get_forecast_summary": get_forecast_summary,
    "get_anomalies": get_anomalies,
    "what_if": what_if,
}

TOOL_SPECS: list[ToolSpec] = [
    ToolSpec("get_monthly_breakdown", "Revenue per calendar month with month-over-month % change. Use to ground any claim about trends, seasonality or specific months.",
             {"type": "object", "properties": {"last_n": {"type": "integer", "description": "How many most-recent months to return (default 24)"}}, "required": []}),
    ToolSpec("get_top_periods", "The best or worst N periods by revenue.",
             {"type": "object", "properties": {
                 "kind": {"type": "string", "enum": ["best", "worst"]},
                 "n": {"type": "integer", "description": "1-20, default 5"},
                 "granularity": {"type": "string", "enum": ["month", "week", "day"], "description": "default month"},
             }, "required": ["kind"]}),
    ToolSpec("compare_periods", "Total revenue in two date ranges (YYYY-MM-DD) and the difference. Use for year-over-year or before/after comparisons.",
             {"type": "object", "properties": {
                 "start_a": {"type": "string"}, "end_a": {"type": "string"},
                 "start_b": {"type": "string"}, "end_b": {"type": "string"},
             }, "required": ["start_a", "end_a", "start_b", "end_b"]}),
    ToolSpec("get_weekday_profile", "Average revenue by day of week (daily data only). Use to recommend staffing, promotions or ad scheduling.",
             {"type": "object", "properties": {}, "required": []}),
    ToolSpec("get_forecast_summary", "The forecast horizon, trend, end value, confidence interval and backtest accuracy (MAPE, coverage, rating).",
             {"type": "object", "properties": {}, "required": []}),
    ToolSpec("get_anomalies", "Days and months where revenue departed sharply from the model's expectation, with z-scores. Decide whether each is a one-off or a signal.",
             {"type": "object", "properties": {"limit": {"type": "integer", "description": "default 10"}}, "required": []}),
    ToolSpec("what_if", "Forecast totals if the driver (e.g. marketing spend) changes by a percentage, learned from the data. Works for any value between -30 and +50.",
             {"type": "object", "properties": {"change_percent": {"type": "number", "description": "e.g. 15 for +15%, -10 for -10%"}}, "required": ["change_percent"]}),
]


def execute_tool(ctx: DataContext, name: str, arguments: dict) -> str:
    fn = TOOLS.get(name)
    if fn is None:
        return _js({"error": f"Unknown tool '{name}'"})
    try:
        return fn(ctx, **arguments)
    except TypeError as e:
        return _js({"error": f"Bad arguments for {name}: {e}"})
    except Exception as e:  # never let a tool crash the agent loop
        return _js({"error": f"{type(e).__name__}: {e}"})
