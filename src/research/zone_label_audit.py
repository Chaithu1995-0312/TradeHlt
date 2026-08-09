"""zone_label_audit.py — F-041B Phase-5 ZoneGate label-provenance audit (MEASURE-ONLY).

Answers the deferred F-041 Go/No-Go: are the stored `models/zone_registry.json` zone labels
(~98% SL-hit / 6-of-8 negative mean_rr) HONEST intrabar_fixed outcomes, or an artifact inherited
from `opportunities.jsonl` (the stream F-022 found only 36.8% self-consistent)? And, on honestly
re-derived outcomes, does any zone's geometry separate positive expectancy at all?

DISCIPLINE (the #1 methodological risk — isolate contamination from re-partition drift):
  * Stored labels were computed under the ORIGINAL seeded KMeans membership (discover_zones.py).
    The honest relabel therefore runs over the SAME reconstructed membership — a delta then means
    label contamination, never re-clustering.
  * Membership identity is PROVEN, not assumed, by a tiered gate (`verify_membership`): reproducing
    the stored per-zone (mean_rr, sl_hit_rate) from the reconstructed members using the ORIGINAL
    labels rules out a permuted partition without needing a historical member-hash.
  * Runtime 38-dim Gaussian assignment is reported SEPARATELY as an assignment-parity metric.

Authority: research/docs + governance-hygiene only (§6.5). The live gate is purely geometric and
never reads these labels (F-036 NON_PIVOTAL); this audit grants ZoneGate no production authority.

Pure logic module — all file I/O lives in the thin driver `scripts/research/zone_label_audit.py`.
Exit truth is the UNCHANGED `research.measurement.forward_walk(exit_model="intrabar_fixed")`.
"""
from __future__ import annotations

import random
import statistics as _stats
from dataclasses import dataclass, asdict

from bitnet.zone_cosine_searcher import compute_gaussian_score
from research.contracts import Signal
from research.measurement.forward_walk import forward_walk

# ── constants (pre-registered; frozen before running — E-001) ────────────────────
MIN_N: int = 30                # sufficiency floor; below this NO expectancy claim is made
COST_RT: float = 0.0012        # 12 bps round-trip, fraction of notional (matches the M4 gate)
MAX_FORWARD: int = 40          # governing realized-exit horizon (matches trade-anatomy)
CONTAM_SL_DELTA: float = 0.10  # |stored_sl - honest_sl| > this (any zone) ⇒ CONTAMINATED
BOOT_SEED: int = 1337
BOOT_ITERS: int = 2000


# ── value objects ────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ZoneAudit:
    zone_id: str
    n: int
    stored_sl_rate: float | None
    honest_sl_rate: float
    sl_delta: float | None            # honest - stored (None if stored missing)
    stored_mean_rr: float | None
    honest_expectancy: float | None   # net-of-cost mean R; None if n < MIN_N
    ci_low: float | None
    ci_high: float | None
    sufficiency: str                  # SUFFICIENT | INSUFFICIENT


# ── outcome / expectancy primitives ──────────────────────────────────────────────
def net_r(outcome) -> float:
    """Net-of-cost realized R for one honest Outcome (12 bps expressed in R via entry/risk)."""
    sig = outcome.signal
    risk = sig.sl_atr_mult * sig.atr
    cost_r = COST_RT * sig.entry / risk if risk > 0 else 0.0
    return outcome.rr_achieved - cost_r


def honest_outcome(opp: dict, candles, ts_to_idx) -> object | None:
    """Re-derive one opportunity's HONEST outcome via forward_walk(intrabar_fixed).

    Mirrors the proven extraction in scripts/analysis/bnbusdt_trade_anatomy.py:derive_row —
    Signal(sl_atr_mult=1.0, tp_atr_mult=|tp-entry|/risk, atr=risk). Returns None when the
    opportunity has no matching candle or no forward bars (caller counts the skip).
    """
    ts = str(opp["timestamp"]).replace("T", " ").strip()
    idx = ts_to_idx.get(ts)
    if idx is None:
        return None
    direction = str(opp["direction"]).lower()
    if direction not in ("long", "short"):
        return None
    entry = float(opp["entry"])
    sl = float(opp["sl"])
    tp = float(opp.get("tp", entry))
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    future = candles[idx + 1: idx + 1 + MAX_FORWARD]
    if not future:
        return None
    sig = Signal(
        instrument=str(opp.get("instrument", "")), timestamp=candles[idx].timestamp,
        entry_index=idx, direction=direction, entry=entry,
        sl_atr_mult=1.0, tp_atr_mult=abs(tp - entry) / risk, atr=risk,
    )
    return forward_walk(sig, future, max_forward=MAX_FORWARD, exit_model="intrabar_fixed")


def _bootstrap_ci(values: list[float], *, iters: int = BOOT_ITERS,
                  seed: int = BOOT_SEED, alpha: float = 0.05) -> tuple[float, float]:
    """Percentile bootstrap CI for the MEAN of `values` (heavy-tailed R → no normal approx)."""
    n = len(values)
    if n == 0:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    means = []
    for _ in range(iters):
        s = 0.0
        for _ in range(n):
            s += values[rng.randrange(n)]
        means.append(s / n)
    means.sort()
    lo = means[int((alpha / 2) * iters)]
    hi = means[min(iters - 1, int((1 - alpha / 2) * iters))]
    return (round(lo, 6), round(hi, 6))


# ── membership verification (tiered; runs FIRST) ─────────────────────────────────
def _label_stats(indices: list[int], outcomes: list[str], rrs: list[float]) -> tuple[int, float, float]:
    """(n, mean_rr, sl_hit_rate) computed from the ORIGINAL opportunity labels."""
    n = len(indices)
    if n == 0:
        return (0, 0.0, 0.0)
    mean_rr = sum(rrs[i] for i in indices) / n
    sl = sum(1 for i in indices if outcomes[i] == "SL_HIT") / n
    return (n, round(mean_rr, 4), round(sl, 4))


def verify_membership(stored_zones: list[dict],
                      reconstructed: list[list[int]],
                      outcomes: list[str], rrs: list[float]) -> dict:
    """Tiered proof that the reconstructed KMeans partition IS the one that made the stored labels.

    reconstructed[c] = list of record-indices in reconstructed cluster c.
    Returns {counts_match, stats_reproduced, hash_available, hash_match, status,
             mapping:{reconstructed_cluster -> stored_zone_index}, detail:[...]}.

    status: VERIFIED (counts match AND stored (mean_rr, sl_hit_rate) reproduce from the ORIGINAL
    labels on the reconstructed members) · PARTIALLY_VERIFIED (counts only) · FAILED (count multiset
    mismatch → caller halts, no verdict). Distinct stored sizes give a clean sorted-n bijection; a
    permuted partition reproduces counts but NOT the per-zone stats ⇒ cannot reach VERIFIED.
    """
    stored = [{"zone_id": z.get("id", f"zone_{k}"),
               "n": int(z.get("meta", {}).get("n_samples", 0)),
               "mean_rr": z.get("meta", {}).get("mean_rr"),
               "sl": z.get("meta", {}).get("sl_hit_rate"),
               "idx": k} for k, z in enumerate(stored_zones)]
    recon = [{"members": m, "n": len(m)} for m in reconstructed]
    for r in recon:
        r["n_rr_sl"] = _label_stats(r["members"], outcomes, rrs)

    counts_match = sorted(s["n"] for s in stored) == sorted(r["n"] for r in recon)
    # Bijection by sorted-n (stored sizes are distinct); greedy nearest if counts diverge.
    mapping: dict[int, int] = {}
    detail = []
    stats_reproduced = counts_match and len(stored) == len(recon)
    stored_by_n = sorted(stored, key=lambda s: s["n"])
    recon_by_n = sorted(range(len(recon)), key=lambda c: recon[c]["n"])
    for s, c in zip(stored_by_n, recon_by_n):
        mapping[c] = s["idx"]
        rn, rmean, rsl = recon[c]["n_rr_sl"]
        n_ok = (rn == s["n"])
        mean_ok = (s["mean_rr"] is not None and abs(rmean - float(s["mean_rr"])) <= 5e-4)
        sl_ok = (s["sl"] is not None and abs(rsl - float(s["sl"])) <= 5e-4)
        if not (n_ok and mean_ok and sl_ok):
            stats_reproduced = False
        detail.append({"stored_zone": s["zone_id"], "stored_n": s["n"], "recon_n": rn,
                       "stored_mean_rr": s["mean_rr"], "recon_mean_rr": rmean,
                       "stored_sl": s["sl"], "recon_sl": rsl,
                       "n_ok": n_ok, "mean_ok": mean_ok, "sl_ok": sl_ok})

    if not counts_match:
        status = "FAILED"
    elif stats_reproduced:
        status = "VERIFIED"
    else:
        status = "PARTIALLY_VERIFIED"
    return {"counts_match": counts_match, "stats_reproduced": stats_reproduced,
            "hash_available": False, "hash_match": None, "status": status,
            "mapping": mapping, "detail": detail}


# ── assignment parity (runtime 38-dim Gaussian vs reconstructed KMeans) ───────────
def runtime_assignment(vec38: list[float], zones: list[dict]) -> int:
    """Argmax weighted-Gaussian zone index (`compute_gaussian_score`).

    CORRECTED 2026-07-22 — previously documented as "exactly how the live gate
    partitions". It is not: the live spine consumes only `top_scores` and **never assigns
    a zone at all** (see the note in `engines.live_engine.BitNetZoneGate.check`; the real
    decision is `compute_weighted_cluster_score(top_scores) >= zone_cluster_threshold` in
    `engines.zone_cluster_score`). `best_zone_id` is telemetry. This argmax is therefore a
    *hypothetical* partition used for the parity diagnostic below — no decision path acts
    on it, which is why low parity is a governance observation and not a runtime risk.

    Note also "38-dim" in the section header is loose: the vector is 38-slot but only ~25
    dims are active (13 carry zero weight in the registry).
    """
    best_i, best_s = -1, -1.0
    for i, z in enumerate(zones):
        s = compute_gaussian_score(vec38, z)
        if s > best_s:
            best_s, best_i = s, i
    return best_i


def assignment_parity(vectors: list[list[float]], recon_assign: list[int],
                      zones: list[dict], mapping: dict[int, int]) -> dict:
    """Fraction of members whose reconstructed-KMeans zone == runtime-Gaussian zone.

    `mapping` translates a reconstructed cluster index → stored-zone index so the two partitions
    are compared in the same label space.

    EXPECTED TO BE LOW — explained 2026-07-22, do not read a low value as a defect. The two
    sides are built on near-disjoint information: KMeans is squared-Euclidean over all 38 RAW
    unnormalised dims, while the Gaussian divides by a global sigma and zero-weights 13 dims.
    Those 13 zeroed dims carry **99.9983%** of the variance driving the KMeans objective
    (`volume` alone 97.58%), so KMeans effectively partitions by volume/price level while the
    runtime scores candle shape. Judge any value against the majority-class baseline (0.3264
    on BNBUSDT), not 1/k. Measured decomposition:
    `docs/analysis/zone-assignment-parity.LATEST.json`.
    """
    n = len(vectors)
    agree = 0
    per_zone_total: dict[int, int] = {}
    per_zone_agree: dict[int, int] = {}
    for k in range(n):
        stored_zone = mapping.get(recon_assign[k], -1)
        rt = runtime_assignment(vectors[k], zones)
        per_zone_total[stored_zone] = per_zone_total.get(stored_zone, 0) + 1
        if rt == stored_zone:
            agree += 1
            per_zone_agree[stored_zone] = per_zone_agree.get(stored_zone, 0) + 1
    overall = agree / n if n else 0.0
    per_zone = {str(z): round(per_zone_agree.get(z, 0) / per_zone_total[z], 4)
                for z in sorted(per_zone_total)}
    return {"overall": round(overall, 4), "per_zone": per_zone, "n": n}


# ── per-zone audit + verdict ──────────────────────────────────────────────────────
def audit_zones(reconstructed: list[list[int]], mapping: dict[int, int],
                stored_zones: list[dict], honest: list[object | None]) -> list[ZoneAudit]:
    """Per stored-zone: stored vs HONEST sl_hit_rate + net-of-cost expectancy (bootstrap CI)."""
    audits: list[ZoneAudit] = []
    for c, members in enumerate(reconstructed):
        stored_idx = mapping.get(c)
        if stored_idx is None:
            continue
        z = stored_zones[stored_idx]
        meta = z.get("meta", {})
        outs = [honest[i] for i in members if honest[i] is not None]
        n = len(outs)
        honest_sl = sum(1 for o in outs if o.outcome == "SL_HIT") / n if n else 0.0
        stored_sl = meta.get("sl_hit_rate")
        if n >= MIN_N:
            nets = [net_r(o) for o in outs]
            exp = round(_stats.fmean(nets), 6)
            lo, hi = _bootstrap_ci(nets)
            suff = "SUFFICIENT"
        else:
            exp, lo, hi, suff = None, None, None, "INSUFFICIENT"
        audits.append(ZoneAudit(
            zone_id=z.get("id", f"zone_{stored_idx}"), n=n,
            stored_sl_rate=stored_sl, honest_sl_rate=round(honest_sl, 4),
            sl_delta=(round(honest_sl - float(stored_sl), 4) if stored_sl is not None else None),
            stored_mean_rr=meta.get("mean_rr"), honest_expectancy=exp,
            ci_low=lo, ci_high=hi, sufficiency=suff,
        ))
    return audits


def classify_verdict(audits: list[ZoneAudit], membership_status: str) -> dict:
    """Pre-registered verdict from the per-zone audits (E-001; thresholds frozen above).

    CONTAMINATED     — any zone |sl_delta| > 0.10  OR  honest expectancy sign flips vs stored mean_rr
    HONEST_NO_EDGE   — labels survive AND no well-powered zone clears net E>0
    HONEST_EDGE      — a well-powered zone clears net E>0 (→ route to M4, do NOT promote here)
    HONEST_INSUFFICIENT reported per-zone (n<MIN_N) — excluded from the NO_EDGE/EDGE decision.
    """
    powered = [a for a in audits if a.sufficiency == "SUFFICIENT"]
    contaminated = any(a.sl_delta is not None and abs(a.sl_delta) > CONTAM_SL_DELTA for a in powered)
    sign_flip = any(
        a.honest_expectancy is not None and a.stored_mean_rr is not None
        and (a.honest_expectancy > 0) != (float(a.stored_mean_rr) > 0)
        and abs(a.honest_expectancy) > 1e-6 and abs(float(a.stored_mean_rr)) > 1e-6
        for a in powered
    )
    edge_zones = [a.zone_id for a in powered
                  if a.honest_expectancy is not None and a.ci_low is not None and a.ci_low > 0]
    if contaminated or sign_flip:
        verdict = "CONTAMINATED"
    elif edge_zones:
        verdict = "HONEST_EDGE"
    else:
        verdict = "HONEST_NO_EDGE"
    return {
        "verdict": verdict,
        "membership_status": membership_status,
        "contaminated_by_sl_delta": contaminated,
        "contaminated_by_sign_flip": sign_flip,
        "edge_zones": edge_zones,
        "n_powered_zones": len(powered),
        "n_insufficient_zones": len(audits) - len(powered),
    }


def build_report(*, instrument: str, source_opportunities: str, registry_path: str,
                 membership: dict, parity: dict, audits: list[ZoneAudit],
                 verdict: dict, skips: dict, n_records: int) -> dict:
    """Assemble the deterministic report dict written by the driver."""
    return {
        "audit": "F-041B ZoneGate label-provenance (Phase-5)",
        "authority": "research/docs + governance-hygiene only (CLAUDE.md §6.5); grants no G001 authority",
        "instrument": instrument,
        "source_opportunities": source_opportunities,
        "registry_path": registry_path,
        "n_records": n_records,
        "skips": skips,
        "exit_model": "intrabar_fixed",
        "cost_round_trip": COST_RT,
        "min_n": MIN_N,
        "membership_verification": membership,
        "assignment_parity": parity,
        "zones": [asdict(a) for a in audits],
        "verdict": verdict,
    }
