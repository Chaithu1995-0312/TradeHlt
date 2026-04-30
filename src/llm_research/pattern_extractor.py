# pattern_extractor.py — LLM-based pattern extraction from historical trade data
# Used OFFLINE only. Output (policy.json) is frozen before any forward test.
# LLM extracts rules + weights from past trades; does NOT predict future trades.
#
import csv
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a quantitative trading analyst. Analyze the provided historical trade data and
extract pattern rules that explain wins vs losses. 

OUTPUT JSON only:
{
  "rules": [
    "<condition that correlates with losses — avoid>",
    "<condition that correlates with wins — prefer>"
  ],
  "filters": [
    {"condition": "<feature_expr>", "action": "BLOCK", "reason": "<why>"}
  ],
  "boosters": [
    {"condition": "<feature_expr>", "action": "INCREASE_SIZE", "factor": <float>, "reason": "<why>"}
  ],
  "weights": {
    "<feature_name>": <0.0–1.0 importance weight>
  },
  "confidence_formula": "<e.g.: 0.4 * fusion_score + 0.3 * zone_gate + 0.3 * rr>",
  "tier_rules": {
    "TIER_1": "<condition for high-confidence trades>",
    "TIER_2": "<condition for medium-confidence trades>",
    "TIER_3": "everything else — skip"
  }
}

RULES:
- Base rules on feature correlations you observe in the data
- Filters must reference actual feature names from the data
- Weights must sum to approximately 1.0
- Do not overfit — prefer general patterns over specific values
- Maximum 5 filters, 3 boosters
"""


@dataclass
class ExtractedPolicy:
    """Policy extracted from historical trade data by LLM."""
    rules: list[str] = field(default_factory=list)
    filters: list[dict] = field(default_factory=list)
    boosters: list[dict] = field(default_factory=list)
    weights: dict = field(default_factory=dict)
    confidence_formula: str = ""
    tier_rules: dict = field(default_factory=dict)
    source: str = "llm"     # "llm" | "fallback"
    trade_count_analyzed: int = 0


def extract_patterns(
    trades_csv: str,
    config: dict = None,
    max_trades: int = 500,
) -> ExtractedPolicy:
    """
    Load historical trades, call LLM to extract patterns, return policy.

    Args:
        trades_csv: path to CSV with historical trades + outcomes
        config: optional config dict (unused but available for context)
        max_trades: max rows to send to LLM (cost/token control)
    Returns:
        ExtractedPolicy
    """
    trades = _load_trades(trades_csv, max_rows=max_trades)
    log.info("PatternExtractor: loaded %d trades from %s", len(trades), trades_csv)

    try:
        from src.config_layer.llama_gate import llm_chat
        policy = _llm_extract(trades, llm_chat)
        policy.trade_count_analyzed = len(trades)
        return policy
    except Exception as exc:
        log.warning("LLM pattern extraction failed: %s — using fallback policy", exc)
        return _fallback_policy(trades)


def _load_trades(csv_path: str, max_rows: int = 500) -> list[dict]:
    """Load trade CSV; return list of row dicts (capped at max_rows)."""
    trades = []
    try:
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                trades.append(dict(row))
                if len(trades) >= max_rows:
                    break
    except FileNotFoundError:
        log.error("Trades CSV not found: %s", csv_path)
    return trades


def _llm_extract(trades: list[dict], llm_chat) -> ExtractedPolicy:
    """Send trades to LLM, parse response into ExtractedPolicy."""
    # Summarize trades for LLM (avoid sending raw CSV rows — too noisy)
    summary = _summarize_trades(trades)
    user_msg = f"Historical trade data summary:\n{json.dumps(summary, indent=2)}\n\nExtract pattern rules."

    resp = llm_chat(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=1024,
        temperature=0.1,
    )

    if not resp:
        raise RuntimeError("Empty LLM response")

    return _parse_policy(resp)


def _summarize_trades(trades: list[dict]) -> dict:
    """Compute aggregate stats for LLM context (not raw rows)."""
    wins = [t for t in trades if float(t.get("pnl_rr_net", t.get("pnl", 0))) > 0]
    losses = [t for t in trades if float(t.get("pnl_rr_net", t.get("pnl", 0))) <= 0]

    def avg(rows, key):
        vals = [float(r.get(key, 0)) for r in rows if r.get(key) not in (None, "")]
        return sum(vals) / len(vals) if vals else 0.0

    numeric_keys = ["fusion_score", "zone_gate", "rr", "body_ratio", "retest_depth",
                    "disp_strength", "pnl_rr_net"]

    summary = {
        "total_trades": len(trades),
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": len(wins) / len(trades) if trades else 0.0,
        "win_averages": {k: avg(wins, k) for k in numeric_keys},
        "loss_averages": {k: avg(losses, k) for k in numeric_keys},
        "feature_columns": list(trades[0].keys()) if trades else [],
    }
    return summary


def _parse_policy(resp: str) -> ExtractedPolicy:
    """Extract JSON from LLM response and build ExtractedPolicy."""
    import re
    m = re.search(r'\{.*\}', resp, re.DOTALL)
    if not m:
        raise ValueError("No JSON block in LLM response")

    data = json.loads(m.group())
    return ExtractedPolicy(
        rules=data.get("rules", []),
        filters=data.get("filters", [])[:5],
        boosters=data.get("boosters", [])[:3],
        weights=data.get("weights", {}),
        confidence_formula=data.get("confidence_formula", ""),
        tier_rules=data.get("tier_rules", {}),
        source="llm",
    )


def _fallback_policy(trades: list[dict]) -> ExtractedPolicy:
    """
    Minimal deterministic fallback policy when LLM is unavailable.
    Uses simple threshold rules observed in data.
    """
    log.info("Using fallback policy (LLM unavailable)")
    return ExtractedPolicy(
        rules=[
            "avoid trades when zone_gate < 0.6",
            "prefer trades when fusion_score > 0.7",
        ],
        filters=[
            {"condition": "zone_gate < 0.5", "action": "BLOCK", "reason": "weak zone"},
        ],
        boosters=[
            {"condition": "fusion_score > 0.75 AND rr > 2.5", "action": "INCREASE_SIZE",
             "factor": 1.2, "reason": "high confidence setup"},
        ],
        weights={"fusion_score": 0.4, "zone_gate": 0.35, "rr": 0.25},
        confidence_formula="0.4 * fusion_score + 0.35 * zone_gate + 0.25 * rr",
        tier_rules={
            "TIER_1": "fusion_score > 0.70 AND zone_gate > 0.65",
            "TIER_2": "fusion_score > 0.55 AND zone_gate > 0.50",
            "TIER_3": "everything else",
        },
        source="fallback",
        trade_count_analyzed=len(trades),
    )


def save_policy(policy: ExtractedPolicy, path: str = "results/llm_research/policy.json"):
    """Persist policy to disk (FREEZE before forward test)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(policy.__dict__, f, indent=2)
    log.info("Policy saved (frozen): %s (source=%s)", path, policy.source)


def load_policy(path: str = "results/llm_research/policy.json") -> ExtractedPolicy:
    """Load a previously frozen policy."""
    with open(path) as f:
        data = json.load(f)
    return ExtractedPolicy(**data)