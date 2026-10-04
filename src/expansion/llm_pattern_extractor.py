# llm_pattern_extractor.py — offline LLM analysis of past trades → expansion directions
# LLM is used ONCE, offline. Output is frozen before ExpansionEngine runs.
# Falls back to rule-based plan if LLM unavailable.
#
import json
import logging
from pathlib import Path
from src.expansion.policy_schema import ExpansionCandidate, ExpansionPlan, PARAM_BOUNDS

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a trading system analyst. Analyze the provided trade metrics and config to identify
SAFE parameter relaxations that could increase trade count without collapsing profitability.

OUTPUT JSON only:
{
  "expansion_candidates": [
    {
      "param": "<param_name>",
      "direction": "increase|decrease",
      "step": <float>,
      "priority": <int 1-5>
    }
  ]
}

RULES:
- Suggest at most 3 parameters
- Prefer smallest step sizes (0.03–0.05)
- Do NOT suggest rr_min reduction as first priority
- Parameters allowed: fusion_min_score, zone_gate_threshold, body_ratio_min, min_rr_ratio
- direction is always "decrease" for threshold params (to allow more trades)
- Prioritize fusion_min_score first, zone_gate_threshold second
"""


def extract_expansion_plan(
    base_config: dict,
    baseline_metrics: dict,
    trade_log_sample: list = None,
    target_multiplier: float = 2.0,
) -> ExpansionPlan:
    """
    Call LLM with current config + metrics to get expansion directions.
    Falls back to a deterministic conservative plan if LLM fails.

    Args:
        base_config: current production config dict
        baseline_metrics: BacktestMetrics dict from baseline run
        trade_log_sample: optional list of recent trade dicts for context
        target_multiplier: desired trade count multiplier (for context)
    Returns:
        ExpansionPlan with ordered candidates
    """
    try:
        from src.config_layer.llm_inference_client import llm_chat
        candidates = _llm_extract(base_config, baseline_metrics, trade_log_sample, target_multiplier, llm_chat)
    except Exception as exc:
        log.warning("LLM pattern extraction failed: %s — using fallback plan", exc)
        candidates = _fallback_plan(base_config)

    return ExpansionPlan(
        base_metrics=baseline_metrics,
        candidates=candidates,
        target_multiplier=target_multiplier,
    )


def _llm_extract(base_config, baseline_metrics, trade_log_sample, target_multiplier, llm_chat) -> list[ExpansionCandidate]:
    """Call LLM and parse expansion candidates."""
    context = {
        "current_config": {k: v for k, v in base_config.items() if isinstance(v, (int, float, str))},
        "baseline_metrics": baseline_metrics,
        "target_multiplier": target_multiplier,
        "trade_sample_count": len(trade_log_sample) if trade_log_sample else 0,
    }
    if trade_log_sample:
        context["trade_sample"] = trade_log_sample[:20]  # cap context size

    user_msg = f"Config and metrics:\n{json.dumps(context, indent=2)}\n\nSuggest expansion directions."

    resp = llm_chat(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=512,
        temperature=0.1,  # low temp for deterministic output
    )

    if not resp:
        raise RuntimeError("Empty LLM response")

    return _parse_candidates(resp, base_config)


def _parse_candidates(resp: str, base_config: dict) -> list[ExpansionCandidate]:
    """Extract and validate candidates from LLM JSON response."""
    import re
    m = re.search(r'\{.*\}', resp, re.DOTALL)
    if not m:
        raise ValueError("No JSON in LLM response")

    data = json.loads(m.group())
    raw_candidates = data.get("expansion_candidates", [])

    candidates = []
    for rc in raw_candidates[:3]:  # max 3
        param = rc.get("param", "")
        if param not in PARAM_BOUNDS:
            log.warning("LLM suggested unknown param %r — skipping", param)
            continue
        if param not in base_config:
            log.warning("Param %r not in base_config — skipping", param)
            continue

        direction = rc.get("direction", "decrease")
        step = float(rc.get("step", 0.05))
        step = max(0.01, min(0.10, step))  # clip step to safe range
        priority = int(rc.get("priority", len(candidates) + 1))

        lo, hi = PARAM_BOUNDS[param]
        candidates.append(ExpansionCandidate(
            param=param,
            direction=direction,
            step=step,
            priority=priority,
            floor=lo,
            ceiling=hi,
        ))
        log.info("LLM expansion candidate: %s %s by %.3f (priority=%d)", direction, param, step, priority)

    return candidates


def _fallback_plan(base_config: dict) -> list[ExpansionCandidate]:
    """
    Conservative rule-based fallback when LLM is unavailable.
    Always valid — uses minimum step sizes.
    """
    log.info("Using fallback expansion plan (LLM unavailable)")
    candidates = []
    priority = 1

    for param, step in [
        ("fusion_min_score", 0.05),
        ("zone_gate_threshold", 0.05),
        ("body_ratio_min", 0.05),
    ]:
        if param in base_config and param in PARAM_BOUNDS:
            lo, hi = PARAM_BOUNDS[param]
            candidates.append(ExpansionCandidate(
                param=param,
                direction="decrease",
                step=step,
                priority=priority,
                floor=lo,
                ceiling=hi,
            ))
            priority += 1

    return candidates


def save_expansion_plan(plan: ExpansionPlan, path: str = "results/expansion/expansion_plan.json"):
    """Persist the expansion plan for audit + reproducibility."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    data = {
        "base_metrics": plan.base_metrics,
        "target_multiplier": plan.target_multiplier,
        "candidates": [c.__dict__ for c in plan.candidates],
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    log.info("Expansion plan saved: %s", path)