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

# Reality Classification (Phase 9): a pattern is one of three DISTINCT states — never a bool.
# Conflating "impossible on this broker" with "not yet seen" is the metric lying.
OBSERVED = "OBSERVED"                  # count > 0
REACHABLE_UNSEEN = "REACHABLE_UNSEEN"  # the broker CAN emit it; we just haven't yet
N_A = "N_A"                            # structurally impossible on this account/fee model

ACCOUNT_MARGIN_MODE_RETAIL_NETTING = 0  # mt5.ACCOUNT_MARGIN_MODE_RETAIL_NETTING


def reachable_patterns(margin_mode, commission_charged: bool) -> set:
    """Which EXPECTED_PATTERNS this account can STRUCTURALLY emit.

    partial_close / post_close_swap: any account. pyramid / INOUT / reopen: netting only
    (on hedging each order is a separate position — no scale-in, no reversal, no id reuse).
    separate_commission: only a commission-charging (non-spread-only) broker.
    """
    reachable = {"partial_closes", "post_close_swaps"}
    if int(margin_mode) == ACCOUNT_MARGIN_MODE_RETAIL_NETTING:
        reachable |= {"pyramids", "inout_reversals", "reopens"}
    if commission_charged:
        reachable |= {"separate_commission_deals"}
    return reachable


def classify(counts: dict, reachable: set) -> dict:
    """Per-pattern PatternStatus given observed counts + the reachable set."""
    out = {}
    for p in EXPECTED_PATTERNS:
        if counts.get(p, 0) > 0:
            out[p] = OBSERVED          # observed ⇒ reachable by definition
        elif p in reachable:
            out[p] = REACHABLE_UNSEEN
        else:
            out[p] = N_A
    return out


def _vol(d) -> float:
    return float(d.get("volume", 0.0) or 0.0)


def _incurred_swap(dlist) -> bool:
    """True if the position was charged swap, in EITHER broker representation:
      • folded into a trade deal (volume>0 with swap!=0) — MetaQuotes-Demo's form,
        observed 2026-06-24: the close OUT deal carried swap=-0.02; OR
      • a separate zero-volume swap record (the synthetic-fixture form).
    Reconstruction sums swap regardless of representation (net_pnl is correct either way);
    this is purely the coverage signal that the broker's overnight-swap path was exercised."""
    return any(abs(float(d.get("swap", 0.0) or 0.0)) > 1e-9 for d in dlist)


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
        if _incurred_swap(dlist):
            counts["post_close_swaps"] += 1

    return counts


def coverage_gaps(counts: dict, reachable: "set | None" = None) -> dict:
    """Account-agnostic (reachable=None) → {validated, missing}.
    Account-aware → {validated, reachable_unseen, n_a} (impossible ≠ not-yet-seen)."""
    if reachable is None:
        return {
            "validated": [p for p in EXPECTED_PATTERNS if counts.get(p, 0) > 0],
            "missing": [p for p in EXPECTED_PATTERNS if counts.get(p, 0) == 0],
        }
    return {
        "validated": [p for p in EXPECTED_PATTERNS if p in reachable and counts.get(p, 0) > 0],
        "reachable_unseen": [p for p in EXPECTED_PATTERNS
                             if p in reachable and counts.get(p, 0) == 0],
        "n_a": [p for p in EXPECTED_PATTERNS if p not in reachable],
    }


def coverage_score(counts: dict, reachable: "set | None" = None) -> dict:
    """Maturity score + tier. Denominator = reachable patterns when supplied
    (observed / (observed + reachable_unseen)), else all EXPECTED_PATTERNS."""
    universe = list(reachable) if reachable is not None else list(EXPECTED_PATTERNS)
    total = len(universe)
    n_val = len([p for p in universe if counts.get(p, 0) > 0])
    score = round(100.0 * n_val / total) if total else 100
    tier = ("Platinum" if score == 100 else "Gold" if score >= 75
            else "Silver" if score >= 50 else "Bronze")
    return {"coverage_score": score, "validated_patterns": n_val,
            "missing_patterns": total - n_val, "tier": tier}


def broker_capabilities(counts: dict) -> dict:
    """Boolean capability map for the monotonic broker registry (5.6G)."""
    return {p: counts.get(p, 0) > 0 for p in EXPECTED_PATTERNS}


def to_markdown(counts: dict, reachable: "set | None" = None) -> str:
    gaps = coverage_gaps(counts, reachable)
    score = coverage_score(counts, reachable)
    denom = len(reachable) if reachable is not None else len(EXPECTED_PATTERNS)
    status = classify(counts, reachable) if reachable is not None else None
    lines = [
        "# Broker Semantics Coverage",
        "",
        f"**Maturity:** {score['coverage_score']}/100 ({score['tier']}) — "
        f"{score['validated_patterns']}/{denom} reachable patterns validated",
        "",
        "| Pattern | Count | Status |",
        "| --- | --- | --- |",
    ]
    lines += [f"| {p} | {counts.get(p, 0)} | {status[p] if status else ''} |"
              for p in EXPECTED_PATTERNS]
    lines += [
        f"| trade_positions | {counts.get('trade_positions', 0)} | |",
        f"| account_ops_skipped | {counts.get('account_ops_skipped', 0)} | |",
        "",
        f"**Validated:** {', '.join(gaps['validated']) or '(none yet)'}",
    ]
    if reachable is not None:
        lines += [
            "",
            f"**Reachable but unseen:** {', '.join(gaps['reachable_unseen']) or '(none)'}",
            "",
            f"**N/A for this broker:** {', '.join(gaps['n_a']) or '(none)'}",
        ]
    else:
        lines += ["", f"**Missing (unseen by reality):** {', '.join(gaps['missing']) or '(none)'}"]
    return "\n".join(lines) + "\n"
