"""
Critic / QA Agent
A second model pass that audits the strategist's report against the actual
numbers and returns a corrected version.

Input: the report plus a "facts sheet" (every figure the pipeline computed).
Output: a list of discrepancies ("claimed 12% growth; data says 8.7%") and a
revised report with those claims fixed. If nothing is wrong the original
report is kept untouched.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from backend.llm import LLMClient, LLMNotConfigured, get_llm

logger = logging.getLogger(__name__)

CRITIC_SYSTEM = """You are a meticulous financial fact-checker reviewing a strategy report written by a colleague.

You will receive:
1. FACTS — the authoritative numbers computed from the data (totals, growth, months, forecast, accuracy, scenarios, anomalies).
2. REPORT — the colleague's markdown report.

Your job:
- Find every numeric or factual claim in the REPORT that contradicts the FACTS: wrong percentages, wrong totals, wrong months, a "best month" that isn't, a forecast direction that doesn't match, a scenario figure that differs from the table, an anomaly date that doesn't exist, etc.
- Treat reasonable rounding (e.g. 8.67% written as "about 9%" or "8.7%") as CORRECT. Only flag real contradictions or figures that do not appear in the FACTS at all.
- Ignore stylistic issues and opinions; only check facts.
- Produce a corrected report that keeps the original structure, tone, language and formatting, changing ONLY the incorrect claims (and the sentences that depend on them).

Respond with ONE JSON object and nothing else:
{
  "issues": [
    {"claim": "<quoted text from the report>", "correct_value": "<what the FACTS say>", "section": "<section heading>"}
  ],
  "revised_report": "<the full corrected markdown report; identical to the original if issues is empty>"
}"""


@dataclass
class CriticResult:
    status: str  # "passed" | "corrected" | "unverified" | "skipped"
    issues: list[dict] = field(default_factory=list)
    revised_report: str | None = None
    provider: str | None = None
    model: str | None = None
    note: str | None = None
    usage: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "issues": self.issues,
            "corrections": len(self.issues),
            "provider": self.provider,
            "model": self.model,
            "note": self.note,
        }


def build_facts_sheet(
    analysis: dict,
    forecast_summary: dict,
    whatif: dict | None,
    anomalies: dict | None,
    monthly: list[dict] | None = None,
) -> dict:
    """Everything the strategist could legitimately have cited, in one compact dict."""
    facts: dict = {
        "analysis": analysis,
        "forecast_summary": forecast_summary,
    }
    if whatif and whatif.get("scenarios"):
        facts["whatif"] = {
            "driver": whatif.get("driver"),
            "method": whatif.get("method"),
            "baseline_driver_value": whatif.get("baseline_driver_value"),
            "scenarios": [{k: v for k, v in s.items() if k != "series"} for s in whatif["scenarios"]],
        }
    if anomalies:
        facts["anomalies"] = {
            "summary": anomalies.get("summary", {}),
            "points": anomalies.get("points", [])[:20],
            "periods": anomalies.get("periods", []),
        }
    if monthly:
        facts["monthly_revenue"] = monthly
    return facts


_JSON_RE = re.compile(r"\{.*\}", re.S)


def _parse_json(text: str) -> dict | None:
    text = text.strip()
    # Strip a ```json fence if the model added one
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S).strip()
    try:
        return json.loads(text)
    except ValueError:
        m = _JSON_RE.search(text)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except ValueError:
            return None


def review_report(report: str, facts: dict, llm: LLMClient | None = None) -> CriticResult:
    """
    Audit `report` against `facts`. Never raises: any failure yields
    status "unverified" so the original report is still delivered.
    """
    try:
        llm = llm or get_llm()
    except LLMNotConfigured as e:
        return CriticResult(status="skipped", note=str(e))

    user = (
        "FACTS (authoritative):\n" + json.dumps(facts, default=str, indent=1)
        + "\n\nREPORT:\n" + report
        + "\n\nAudit the REPORT against the FACTS and respond with the JSON object."
    )
    try:
        resp = llm.chat(
            [{"role": "system", "content": CRITIC_SYSTEM}, {"role": "user", "content": user}],
            max_tokens=6000,
            temperature=0.0,
            json_mode=True,
        )
    except Exception as e:
        logger.warning("Critic request failed: %s", e)
        return CriticResult(status="unverified", provider=llm.provider, model=llm.model, note=f"request failed: {e}")

    data = _parse_json(resp.text)
    if not data or not isinstance(data.get("issues"), list):
        return CriticResult(status="unverified", provider=llm.provider, model=llm.model, note="could not parse critic output", usage=resp.usage)

    issues = [
        {"claim": str(i.get("claim", ""))[:300], "correct_value": str(i.get("correct_value", ""))[:300], "section": str(i.get("section", ""))[:120]}
        for i in data["issues"]
        if isinstance(i, dict)
    ]
    revised = data.get("revised_report")
    if issues and isinstance(revised, str) and revised.strip() and len(revised) > 0.5 * len(report):
        return CriticResult(status="corrected", issues=issues, revised_report=revised, provider=llm.provider, model=llm.model, usage=resp.usage)
    if issues:
        # Found problems but the rewrite looks truncated/unsafe — keep the original, report the issues
        return CriticResult(status="corrected", issues=issues, revised_report=None, provider=llm.provider, model=llm.model,
                            note="issues found; original report kept because the rewrite was incomplete", usage=resp.usage)
    return CriticResult(status="passed", provider=llm.provider, model=llm.model, usage=resp.usage)
