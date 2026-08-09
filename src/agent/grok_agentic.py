"""
grok_agentic.py — GrokAgenticAI multi-agent registry
─────────────────────────────────────────────────────────────────────────────
Product name: **GrokAgenticAI**

Operators address the system as "Ask GrokAgenticAI …". Under that brand,
multiple *specialist* agents differentiate by goal and tool allowlist:

  · OpsDoctor        — read-only incident / funnel / throughput diagnosis
  · CampaignRunner   — tune → validate → (confirm) promote → backtest loop
  · TruthJanitor     — construction / lint / census / citations hygiene pack
  · (reserved) ResearchRunner, TrainingRefresh, MultiLLMBridge

Planning stays bounded: seed recipes + optional branch tables. Free LLM tool
choice over the full REGISTRY is forbidden (design Mode D).
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .goal import AgentGoal, Autonomy, GoalKind, SuccessCriterion


PRODUCT_NAME = "GrokAgenticAI"
PRODUCT_ALIASES = (
    "grokagenticai",
    "grok agentic ai",
    "grok agentic",
    "ask grokagenticai",
    "ask grok agentic",
)


@dataclass(frozen=True)
class SpecialistSpec:
    """One differentiated agent under the GrokAgenticAI brand."""

    key: str                    # ops_doctor | campaign_runner | truth_janitor
    display_name: str           # OpsDoctor
    goal_kind: GoalKind
    mode: str                   # ops | pipeline | truth | …
    seed_intent: str            # PLAN_REGISTRY / recipe key
    autonomy: Autonomy
    description: str
    tool_allowlist: Sequence[str] = field(default_factory=tuple)
    # When True, only tools in tool_allowlist may run for this specialist
    enforce_allowlist: bool = True
    max_steps: int = 12
    default_success: tuple = ()
    default_fail_fast: tuple = ()


# ── Registry (extend here when adding specialists) ───────────────────────────

SPECIALISTS: Dict[str, SpecialistSpec] = {
    "ops_doctor": SpecialistSpec(
        key="ops_doctor",
        display_name="OpsDoctor",
        goal_kind="ops_diagnose",
        mode="ops",
        seed_intent="ops_diagnose",
        autonomy="read_only",
        description=(
            "Diagnose throughput drops, funnel failures, and reject reasons. "
            "Read-only tools + optional incident pack under results/incidents/."
        ),
        tool_allowlist=(
            "ops.throughput_snapshot",
            "ops.funnel_diagnose",
            "ops.fail_reasons",
            "ops.incident_pack",
            "collector.tail",
            "log.query",
            "log.get_run",
            "audit.tail",
            "findings.list_recent",
        ),
        enforce_allowlist=True,
        max_steps=8,
        default_success=(
            SuccessCriterion("incident_pack", "eq", True),
            SuccessCriterion("ops.complete", "eq", True),
        ),
        default_fail_fast=(
            SuccessCriterion("status", "eq", "fatal"),
        ),
    ),
    "campaign_runner": SpecialistSpec(
        key="campaign_runner",
        display_name="CampaignRunner",
        goal_kind="campaign_pipeline",
        mode="pipeline",
        seed_intent="campaign_run",
        autonomy="confirm_writes",
        description=(
            "Goal-oriented pipeline: tune → validate → optional promote → backtest. "
            "Write tools stay confirm-gated; promotion still requires APPROVE."
        ),
        tool_allowlist=(
            "tuner.run_multi",
            "validator.validate",
            "promotion.promote_from_checkpoint",
            "backtest.run_v2",
            "live_hook.dry_run",
        ),
        enforce_allowlist=True,
        max_steps=12,
        default_success=(
            SuccessCriterion("validation.decision", "eq", "APPROVE"),
            SuccessCriterion("campaign.complete", "eq", True),
        ),
        default_fail_fast=(
            SuccessCriterion("status", "eq", "error"),
        ),
    ),
    "truth_janitor": SpecialistSpec(
        key="truth_janitor",
        display_name="TruthJanitor",
        goal_kind="truth_janitor",
        mode="truth",
        seed_intent="truth_janitor",
        autonomy="confirm_writes",  # hygiene_pack is write; checks are read-only
        description=(
            "Repo hygiene: construction protocol check, feature-math lint, script census, "
            "citation floor → results/hygiene/ pack. No production/doc auto-edit."
        ),
        tool_allowlist=(
            "truth.construction_check",
            "truth.feature_math_lint",
            "truth.script_census",
            "truth.citation_floor",
            "truth.hygiene_pack",
        ),
        enforce_allowlist=True,
        max_steps=8,
        default_success=(
            SuccessCriterion("hygiene_pack", "eq", True),
            SuccessCriterion("truth.complete", "eq", True),
        ),
        default_fail_fast=(
            SuccessCriterion("status", "eq", "fatal"),
        ),
    ),
}

# intent_key → specialist key
INTENT_TO_SPECIALIST: Dict[str, str] = {
    "ops_diagnose": "ops_doctor",
    "campaign_run": "campaign_runner",
    "campaign_tune_validate": "campaign_runner",
    "truth_janitor": "truth_janitor",
}

# NL aliases → specialist key (checked after product prefix strip)
_SPECIALIST_ALIASES: List[tuple[str, str]] = [
    (r"\bops[_\s-]?doctor\b", "ops_doctor"),
    (r"\bdiagnose\b", "ops_doctor"),
    (r"\bincident\b", "ops_doctor"),
    (r"\bfunnel\b", "ops_doctor"),
    (r"\bthroughput\b", "ops_doctor"),
    (r"\bcampaign[_\s-]?runner\b", "campaign_runner"),
    (r"\bcampaign\b", "campaign_runner"),
    (r"\btune.*until\b", "campaign_runner"),
    (r"\brun\s+until\b", "campaign_runner"),
    (r"\btruth[_\s-]?janitor\b", "truth_janitor"),
    (r"\bhygiene\b", "truth_janitor"),
    (r"\bconstruction\s+protocol\b", "truth_janitor"),
    (r"\bdoc\s*drift\b", "truth_janitor"),
    (r"\bcitation\s+sync\b", "truth_janitor"),
    (r"\bscript\s+census\b", "truth_janitor"),
    (r"\bfeature[_\s-]?math\s+lint\b", "truth_janitor"),
]


def list_specialists() -> List[SpecialistSpec]:
    return list(SPECIALISTS.values())


def get_specialist(key: str) -> Optional[SpecialistSpec]:
    return SPECIALISTS.get(key)


def strip_product_prefix(text: str) -> str:
    """Remove 'Ask GrokAgenticAI' / brand prefixes so routing sees the goal text."""
    t = text.strip()
    lower = t.lower()
    for alias in sorted(PRODUCT_ALIASES, key=len, reverse=True):
        if lower.startswith(alias):
            rest = t[len(alias):].lstrip(" \t:,-")
            return rest if rest else t
    # Mid-string "ask GrokAgenticAI to …"
    m = re.search(
        r"(?i)\bask\s+grok\s*agentic\s*ai\s+(?:to\s+)?",
        t,
    )
    if m:
        return t[m.end():].strip() or t
    m2 = re.search(r"(?i)\bgrokagenticai\s*[:\-]?\s*", t)
    if m2 and m2.start() == 0:
        return t[m2.end():].strip() or t
    return t


def detect_specialist(text: str) -> Optional[str]:
    """Return specialist key from NL, or None."""
    body = strip_product_prefix(text)
    lower = body.lower()
    for pattern, key in _SPECIALIST_ALIASES:
        if re.search(pattern, lower):
            return key
    return None


def extract_instruments(text: str) -> List[str]:
    """Best-effort instrument tokens (A-Z + optional USDT/USD suffix)."""
    found = re.findall(
        r"\b([A-Z]{2,10}(?:USDT|USD|EUR|GBP|JPY)?)\b",
        text.upper(),
    )
    # Drop common English false positives
    stop = {"ASK", "RUN", "THE", "FOR", "AND", "UNTIL", "WITH", "FROM", "JSON", "CSV", "API"}
    out = []
    for tok in found:
        if tok in stop:
            continue
        if tok not in out:
            out.append(tok)
    return out


def build_goal(
    specialist_key: str,
    objective: str,
    *,
    instruments: Optional[List[str]] = None,
    context: Optional[dict] = None,
) -> AgentGoal:
    spec = SPECIALISTS[specialist_key]
    goal_id = f"ga_{spec.key}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    return AgentGoal(
        goal_id=goal_id,
        kind=spec.goal_kind,
        objective=objective,
        agent_name=PRODUCT_NAME,
        specialist=spec.display_name,
        instruments=list(instruments or []),
        success=list(spec.default_success),
        fail_fast=list(spec.default_fail_fast),
        autonomy=spec.autonomy,
        max_steps=spec.max_steps,
        seed_intent=spec.seed_intent,
        context=dict(context or {}),
    )


def help_banner() -> str:
    lines = [
        f"{PRODUCT_NAME} — multi-agent kitchen (async; not the candle spine)",
        "Say:  Ask GrokAgenticAI <goal>",
        "Specialists:",
    ]
    for s in SPECIALISTS.values():
        lines.append(f"  · {s.display_name:16} ({s.key}) — {s.description}")
    lines.append("Legacy pipeline/copilot/governance intents still work without a specialist.")
    lines.append("Writes: confirm-gated. Promotion: ValidationReport APPROVE only. No live orders from OpsDoctor.")
    return "\n".join(lines)
