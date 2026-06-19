"""
deal_characterizer — pure, read-only analysis of which broker patterns a deal stream
actually contains (Phase 5.6B). NO execution.

Fixtures are *assumptions*; broker history is *evidence*. This turns a raw deal stream into
a coverage report — which of the hard reconstruction patterns (partial close, pyramid,
INOUT reversal, reopen, separate-commission, post-close swap) reality has truly exercised —
plus a maturity score. Reuses the kernel (`reconstruct_position_episodes`, `is_position_deal`)
so the characterization agrees with how the pipeline actually reconstructs.
"""
from __future__ import annotations

from collections import defaultdict

from .position_reconstructor import (
    DEAL_ENTRY_IN,
    DEAL_ENTRY_INOUT,
    DEAL_ENTRY_OUT,
    DEAL_ENTRY_OUT_BY,
    is_position_deal,
    reconstruct_position_episodes,
)

_VOL_EPS = 1e-9

# The reconstruction-critical broker behaviors we want reality to confirm.
EXPECTED_PATTERNS = (
    "partial_closes",
    "pyramids",
    "inout_reversals",
    "reopens",
    "separate_commission_deals",
    "post_close_swaps",
)


def _vol(d) -> float:
    return float(d.get("volume", 0.0) or 0.0)


def _has_post_close_swap(dlist) -> bool:
    """A zero-volume swap record arriving while the position is already flat (post-close)."""
    open_vol = 0.0
    closed_once = False
    for d in dlist:
        v = _vol(d)
        if v <= _VOL_EPS:
            if abs(float(d.get("swap", 0.0) or 0.0)) > 0 and closed_once and abs(open_vol) <= _VOL_EPS:
                return True
            continue
        entry = int(d.get("entry", DEAL_ENTRY_IN))
        if entry == DEAL_ENTRY_IN:
            open_vol += v
        elif entry in (DEAL_ENTRY_OUT, DEAL_ENTRY_OUT_BY):
            open_vol -= v
        elif entry == DEAL_ENTRY_INOUT:
            open_vol = v - abs(open_vol)
        if abs(open_vol) <= _VOL_EPS:
            closed_once = True
    return False


def characterize_deal_stream(deals) -> dict:
    """Count which reconstruction patterns appear in `deals` (pure, deterministic)."""
    counts = {p: 0 for p in EXPECTED_PATTERNS}
    counts["trade_positions"] = 0
    counts["account_ops_skipped"] = 0

    by_pos: dict[int, list[dict]] = defaultdict(list)
    for d in deals:
        if not is_position_deal(d):
            counts["account_ops_skipped"] += 1   # deposits/credits/bonuses (pid 0)
            continue
        by_pos[int(d["position_id"])].append(d)

    for _pid, dlist in by_pos.items():
        dlist = sorted(dlist, key=lambda d: (d.get("time", 0), d.get("ticket", 0)))
        counts["trade_positions"] += 1
        episodes = reconstruct_position_episodes(dlist)
        ticket_to_deal = {int(d["ticket"]): d for d in dlist if "ticket" in d}
        has_inout = any(int(d.get("entry", 0)) == DEAL_ENTRY_INOUT for d in dlist)

        # partial close / pyramid are per-episode (reopen has 1 IN+1 OUT per episode,
        # so it must NOT be miscounted as a partial close).
        for ep in episodes:
            ed = [ticket_to_deal[t] for t in ep.deal_tickets if t in ticket_to_deal]
            n_in = sum(1 for d in ed
                       if int(d.get("entry", 0)) == DEAL_ENTRY_IN and _vol(d) > _VOL_EPS)
            n_out = sum(1 for d in ed
                        if int(d.get("entry", 0)) in (DEAL_ENTRY_OUT, DEAL_ENTRY_OUT_BY)
                        and _vol(d) > _VOL_EPS)
            if n_out >= 2:
                counts["partial_closes"] += 1
            if n_in >= 2:
                counts["pyramids"] += 1

        if has_inout:
            counts["inout_reversals"] += 1
        elif len(episodes) >= 2:
            counts["reopens"] += 1   # closed then re-opened (NOT a reversal)

        if any(_vol(d) <= _VOL_EPS and abs(float(d.get("commission", 0.0) or 0.0)) > 0
               for d in dlist):
            counts["separate_commission_deals"] += 1
        if _has_post_close_swap(dlist):
            counts["post_close_swaps"] += 1

    return counts


def coverage_gaps(counts: dict) -> dict:
    """Split EXPECTED_PATTERNS into validated (count > 0) vs missing (count == 0)."""
    validated = [p for p in EXPECTED_PATTERNS if counts.get(p, 0) > 0]
    missing = [p for p in EXPECTED_PATTERNS if counts.get(p, 0) == 0]
    return {"validated": validated, "missing": missing}


def coverage_score(counts: dict) -> dict:
    """0–100 maturity score + tier (Bronze/Silver/Gold/Platinum)."""
    gaps = coverage_gaps(counts)
    n_val = len(gaps["validated"])
    total = len(EXPECTED_PATTERNS)
    score = round(100.0 * n_val / total) if total else 0
    tier = ("Platinum" if score == 100 else "Gold" if score >= 75
            else "Silver" if score >= 50 else "Bronze")
    return {"coverage_score": score, "validated_patterns": n_val,
            "missing_patterns": total - n_val, "tier": tier}


def broker_capabilities(counts: dict) -> dict:
    """Boolean capability map for the monotonic broker registry (5.6G)."""
    return {p: counts.get(p, 0) > 0 for p in EXPECTED_PATTERNS}


def to_markdown(counts: dict) -> str:
    gaps = coverage_gaps(counts)
    score = coverage_score(counts)
    lines = [
        "# Broker Semantics Coverage",
        "",
        f"**Maturity:** {score['coverage_score']}/100 ({score['tier']}) — "
        f"{score['validated_patterns']}/{len(EXPECTED_PATTERNS)} patterns validated",
        "",
        "| Pattern | Count |",
        "| --- | --- |",
    ]
    lines += [f"| {p} | {counts.get(p, 0)} |" for p in EXPECTED_PATTERNS]
    lines += [
        f"| trade_positions | {counts.get('trade_positions', 0)} |",
        f"| account_ops_skipped | {counts.get('account_ops_skipped', 0)} |",
        "",
        f"**Validated:** {', '.join(gaps['validated']) or '(none yet)'}",
        "",
        f"**Missing (unseen by reality):** {', '.join(gaps['missing']) or '(none)'}",
    ]
    return "\n".join(lines) + "\n"
