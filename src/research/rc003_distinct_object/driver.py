"""RC-003 driver — executes the frozen pre-registration, nothing more.

Every population rule, test, referent, alpha, and stop condition below is fixed by
``docs/research/preregistration-rc003-distinct-object.md``. Nothing here may be tuned
after a result is seen; a null is registered, not re-cut.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from config_layer.production_config import (
    get_active_version,
    get_prod_section,
    load_prod_config_from_registry,
)
from features.crt_state_resolver import CRTStateResolver, build_htf_id_timeline
from features.feature_pipeline import FeaturePipeline
from features.feature_schema import CANONICAL_FEATURES
from research.measurement.bootstrap import seed_from_key

PREREG_PATH = "docs/research/preregistration-rc003-distinct-object.md"
# Whole-file sha at freeze time, 2026-09-04, recorded BEFORE this package existed. Kept as
# provenance: it is what "frozen" meant when the driver did not yet exist.
PREREG_FREEZE_SHA256 = "0102f9dc66bbcf08181aef9712c7cf0048a3fe58607de7325796c54a8c8e0f57"
# What is actually verified at run time. Section 12 is append-only, so the whole-file hash
# necessarily changes once a result is written; the FROZEN PREFIX (everything up to and
# including the section-12 append-only marker) must not. Equal to PREREG_FREEZE_SHA256 minus
# the file's single trailing newline.
PREREG_FROZEN_MARKER = "*(append-only; nothing above this line is edited after a result is seen)*"
PREREG_SHA256 = "731ccbcfadcc43310db0a1a588f9b997692187d87f809278cee30d226a1ddc4c"

# §5 — fixed by the pre-registration.
ALPHA_PRIMARY = 0.05
ALPHA_SECONDARY = 0.0167  # Bonferroni over the three declared secondaries
N_MIN_PER_GROUP = 150  # §8 stop condition
N_BOOT = 2000
BLOCK_BARS = 96  # one trading day of M15 — the block unit for §6


# ── population construction (§3) ────────────────────────────────────────────


@dataclass
class Bar:
    idx: int
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    state: Optional[str]
    sweep_sig: Optional[int]
    range_h_ref: float
    range_l_ref: float
    feature_states: dict = field(default_factory=dict)


@dataclass
class Populations:
    bars: list[Bar]
    violating: list[int]
    continuation: list[int]
    founding: dict[int, int]  # violating idx -> founding SWEEP bar idx
    corpus_path: str
    corpus_sha256: str
    n_raw: int
    n_enriched: int


def frozen_prefix_sha256(path: str | Path = PREREG_PATH) -> str:
    """sha256 of the immutable part of the pre-registration: everything up to and including
    the section-12 append-only marker. Appending a result must not change this."""
    text = Path(path).read_text(encoding="utf-8")
    i = text.index(PREREG_FROZEN_MARKER) + len(PREREG_FROZEN_MARKER)
    return hashlib.sha256(text[:i].encode("utf-8")).hexdigest()


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_populations(corpus: str | Path, instrument: str = "XAUUSD") -> Populations:
    """Rebuild VIOLATING and CONTINUATION exactly as §3 declares."""
    corpus = Path(corpus)
    corpus_sha = _sha256_file(corpus)

    df = pd.read_csv(corpus)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    n_raw = len(df)

    enriched, _ = FeaturePipeline(df).run()
    n = len(enriched)
    dropped = n_raw - n

    cph = int(get_prod_section("backtest")["htf_candles_per_range"])
    htf_ids = build_htf_id_timeline(n_raw, candles_per_htf=cph, instrument=instrument)[dropped:]

    cfg = load_prod_config_from_registry(get_active_version(), instrument)
    atr_abs = enriched["atr"].to_numpy(float) * enriched["close"].to_numpy(float)
    rng = enriched["high"].to_numpy(float) - enriched["low"].to_numpy(float)
    body = np.abs(enriched["close"].to_numpy(float) - enriched["open"].to_numpy(float))
    with np.errstate(divide="ignore", invalid="ignore"):
        body_ratio = np.where(rng > 0, body / rng, 0.0)
    qualifies = (
        (rng >= cfg.atr_multiplier_min * atr_abs)
        & (body >= cfg.atr_min_displacement * atr_abs)
        & (body_ratio >= cfg.body_ratio_min)
    )

    avail = [c for c in CANONICAL_FEATURES if c in enriched.columns]
    for col in ("retest_flag", "displacement_flag", "rsi_state"):
        if col not in enriched.columns:
            enriched[col] = 0

    resolver = CRTStateResolver()
    resolver.reset_counts()
    resolver.reset_memory()
    resolver.record_resolver_evidence = True  # RC-003 capture — read-only, decision-neutral

    o = enriched["open"].to_numpy(float)
    h = enriched["high"].to_numpy(float)
    lo = enriched["low"].to_numpy(float)
    c = enriched["close"].to_numpy(float)
    ts = enriched["timestamp"].astype(str).to_numpy()

    bars: list[Bar] = []
    for i in range(n):
        row = enriched.iloc[i]
        fd = {k: row[k] for k in avail if k in row.index}
        for col in ("retest_flag", "displacement_flag", "rsi_state"):
            fd[col] = row[col]
        resolver.last_resolver_evidence = None
        try:
            st = resolver.resolve(fd, timestamp=row["timestamp"], htf_id=htf_ids[i])
        except Exception:
            st = None
        ev = resolver.last_resolver_evidence or {}
        bars.append(
            Bar(
                idx=i,
                timestamp=str(ts[i]),
                open=float(o[i]),
                high=float(h[i]),
                low=float(lo[i]),
                close=float(c[i]),
                state=st,
                sweep_sig=ev.get("sweep_sig"),
                range_h_ref=float(ev.get("range_h_ref", 0.0) or 0.0),
                range_l_ref=float(ev.get("range_l_ref", 0.0) or 0.0),
                feature_states=ev.get("feature_states", {}),
            )
        )

    # founding SWEEP bar = first bar of the contiguous SWEEP streak containing i
    def founding_of(i: int) -> Optional[int]:
        if bars[i].state != "SWEEP":
            return None
        j = i
        while j > 0 and bars[j - 1].state == "SWEEP":
            j -= 1
        return j

    violating: list[int] = []
    founding: dict[int, int] = {}
    continuation: list[int] = []
    for i in range(n):
        if not bool(qualifies[i]):
            continue
        b = bars[i]
        if b.state in ("DISPLACEMENT", "EXPANSION") and str(
            b.feature_states.get("displacement_flag", "")
        ) == "Displacement":
            continuation.append(i)
            continue
        if b.state != "SWEEP":
            continue
        j = founding_of(i)
        if j is None:
            continue
        sig = bars[j].sweep_sig
        if not sig:
            continue
        implied = -1 if sig > 0 else 1  # +1 sell-side -> SHORT; -1 buy-side -> LONG
        cdir = 1 if b.close > b.open else (-1 if b.close < b.open else 0)
        if cdir == 0 or cdir == implied:
            continue
        violating.append(i)
        founding[i] = j

    return Populations(
        bars=bars,
        violating=violating,
        continuation=continuation,
        founding=founding,
        corpus_path=corpus.as_posix(),
        corpus_sha256=corpus_sha,
        n_raw=n_raw,
        n_enriched=n,
    )


# ── §6 block bootstrap / effective n ────────────────────────────────────────


def block_bootstrap_prop_diff(
    a_flags: list[tuple[int, int]],
    b_flags: list[tuple[int, int]],
    *,
    key: str,
    n_boot: int = N_BOOT,
    alpha: float = ALPHA_PRIMARY,
    block: int = BLOCK_BARS,
) -> dict[str, Any]:
    """Block bootstrap on (bar_index, 0/1) pairs. Resamples whole blocks, not bars,
    so clustered events do not inflate confidence. Returns the proportion difference
    (a - b) with its CI, plus the measured effective n for each group."""
    rng = np.random.default_rng(seed_from_key(key))

    def blocks(flags):
        d: dict[int, list[int]] = {}
        for idx, v in flags:
            d.setdefault(idx // block, []).append(v)
        return list(d.values())

    ba, bb = blocks(a_flags), blocks(b_flags)
    if not ba or not bb:
        raise ValueError("block_bootstrap_prop_diff: empty group")

    def resample(bl):
        pick = rng.integers(0, len(bl), len(bl))
        vals = [v for k in pick for v in bl[k]]
        return float(np.mean(vals)) if vals else float("nan")

    diffs = np.array([resample(ba) - resample(bb) for _ in range(n_boot)])
    diffs = diffs[~np.isnan(diffs)]
    lo, hi = np.percentile(diffs, [100 * alpha / 2, 100 * (1 - alpha / 2)])

    pa = float(np.mean([v for _, v in a_flags]))
    pb = float(np.mean([v for _, v in b_flags]))
    return {
        "p_a": pa,
        "p_b": pb,
        "diff": pa - pb,
        "ci_lo": float(lo),
        "ci_hi": float(hi),
        "crosses_zero": bool(lo <= 0.0 <= hi),
        "n_a_raw": len(a_flags),
        "n_b_raw": len(b_flags),
        "n_a_eff_blocks": len(ba),
        "n_b_eff_blocks": len(bb),
        "block_bars": block,
        "alpha": alpha,
    }


# ── §5 tests ────────────────────────────────────────────────────────────────


def _swept_side(pop: Populations, i: int) -> Optional[int]:
    """+1 = high side swept, -1 = low side swept, from the founding bar's sweep_sig."""
    j = pop.founding.get(i)
    if j is None:
        return None
    sig = pop.bars[j].sweep_sig
    if not sig:
        return None
    return 1 if sig > 0 else -1  # +1 sell-side == HIGH swept


def _ref_value(pop: Populations, i: int, referent: str) -> Optional[float]:
    j = pop.founding.get(i)
    side = _swept_side(pop, i)
    if j is None or side is None:
        return None
    if referent == "A":
        v = pop.bars[j].range_h_ref if side > 0 else pop.bars[j].range_l_ref
        return float(v) if v else None
    return float(pop.bars[j].high if side > 0 else pop.bars[j].low)


def _beyond(pop: Populations, i: int, referent: str, mode: str) -> Optional[int]:
    ref = _ref_value(pop, i, referent)
    side = _swept_side(pop, i)
    if ref is None or side is None:
        return None
    b = pop.bars[i]
    px = b.close if mode == "close" else (b.high if side > 0 else b.low)
    return int(px > ref) if side > 0 else int(px < ref)


def _control_beyond(pop: Populations, i: int, referent: str, mode: str) -> Optional[int]:
    """CONTINUATION bars have no founding streak of their own by construction; the control
    asks the mirror question — did the bar leave the OTHER side of the same reference?
    Reference is taken from the bar's own frozen range bounds (referent A) or its own
    extremes (referent B), with side = the candle's own direction."""
    b = pop.bars[i]
    side = 1 if b.close > b.open else -1
    if referent == "A":
        v = b.range_h_ref if side > 0 else b.range_l_ref
        ref = float(v) if v else None
    else:
        ref = float(b.high if side > 0 else b.low)
    if ref is None:
        return None
    px = b.close if mode == "close" else (b.high if side > 0 else b.low)
    return int(px > ref) if side > 0 else int(px < ref)


def _duration_to_next_event(pop: Populations, i: int, horizon: int = 500) -> Optional[int]:
    """S3 — bars until the next liquidity_sweep or break_of_structure."""
    for k in range(i + 1, min(i + horizon + 1, len(pop.bars))):
        fs = pop.bars[k].feature_states
        if str(fs.get("liquidity_sweep", "NoSweep")) != "NoSweep":
            return k - i
        if str(fs.get("break_of_structure", "NoBreak")) != "NoBreak":
            return k - i
    return None


def run_rc003(corpus: str | Path, out_dir: str | Path, instrument: str = "XAUUSD") -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    actual = frozen_prefix_sha256()
    if actual != PREREG_SHA256:
        raise RuntimeError(
            f"pre-registration's FROZEN PREFIX changed since freeze: {actual} != {PREREG_SHA256}. "
            "Everything above the section-12 marker is immutable; only section 12 may be appended."
        )

    pop = build_populations(corpus, instrument=instrument)
    n_v, n_c = len(pop.violating), len(pop.continuation)

    fingerprint = {
        "corpus_path": pop.corpus_path,
        "corpus_sha256": pop.corpus_sha256,
        "n_raw_bars": pop.n_raw,
        "n_enriched_bars": pop.n_enriched,
        "n_violating": n_v,
        "n_continuation": n_c,
        "violating_timestamps": [pop.bars[i].timestamp for i in pop.violating],
        "n_min_per_group_declared": N_MIN_PER_GROUP,
        "insufficient": bool(n_v < N_MIN_PER_GROUP or n_c < N_MIN_PER_GROUP),
    }
    (out / "population_fingerprint.json").write_text(
        json.dumps(fingerprint, indent=2), encoding="utf-8"
    )

    results: dict[str, Any] = {
        "prereg_frozen_prefix_sha256": PREREG_SHA256,
        "prereg_freeze_whole_file_sha256": PREREG_FREEZE_SHA256,
        "insufficient": fingerprint["insufficient"],
        "n_violating": n_v,
        "n_continuation": n_c,
        "tests": {},
    }

    def prop_test(name, referent, mode, alpha):
        a = [(i, v) for i in pop.violating
             if (v := _beyond(pop, i, referent, mode)) is not None]
        b = [(i, v) for i in pop.continuation
             if (v := _control_beyond(pop, i, referent, mode)) is not None]
        if not a or not b:
            return {"status": "NO_DATA", "n_a": len(a), "n_b": len(b)}
        r = block_bootstrap_prop_diff(a, b, key=f"rc003|{name}", alpha=alpha)
        r["status"] = "OK"
        r["referent"] = referent
        r["mode"] = mode
        return r

    results["tests"]["PRIMARY_close_refA"] = prop_test(
        "PRIMARY_close_refA", "A", "close", ALPHA_PRIMARY
    )
    results["tests"]["S1_close_refB"] = prop_test("S1_close_refB", "B", "close", ALPHA_SECONDARY)
    results["tests"]["S2_extend_refA"] = prop_test("S2_extend_refA", "A", "extend", ALPHA_SECONDARY)

    # S3 — duration
    dv = [(i, d) for i in pop.violating if (d := _duration_to_next_event(pop, i)) is not None]
    dc = [(i, d) for i in pop.continuation if (d := _duration_to_next_event(pop, i)) is not None]
    if dv and dc:
        s3 = block_bootstrap_prop_diff(dv, dc, key="rc003|S3_duration", alpha=ALPHA_SECONDARY)
        s3["status"] = "OK"
        s3["note"] = "mean bars-to-next-structural-event; diff = violating - continuation"
        results["tests"]["S3_duration"] = s3
    else:
        results["tests"]["S3_duration"] = {"status": "NO_DATA", "n_a": len(dv), "n_b": len(dc)}

    # §4 — referent disagreement is a declared output
    dis = 0
    both = 0
    for i in pop.violating:
        a = _beyond(pop, i, "A", "close")
        b = _beyond(pop, i, "B", "close")
        if a is None or b is None:
            continue
        both += 1
        dis += int(a != b)
    disagreement = {
        "n_compared": both,
        "n_disagree": dis,
        "rate": (dis / both) if both else None,
        "primary_verdict_flips": None,
    }
    pa = results["tests"]["PRIMARY_close_refA"]
    s1 = results["tests"]["S1_close_refB"]
    if pa.get("status") == "OK" and s1.get("status") == "OK":
        disagreement["primary_verdict_flips"] = bool(
            pa["crosses_zero"] != s1["crosses_zero"]
        )
    (out / "referent_disagreement.json").write_text(
        json.dumps(disagreement, indent=2), encoding="utf-8"
    )
    results["referent_disagreement"] = disagreement

    (out / "metrics.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    with (out / "ledger.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for i in pop.violating:
            f.write(json.dumps({
                "group": "VIOLATING",
                "timestamp": pop.bars[i].timestamp,
                "founding_ts": pop.bars[pop.founding[i]].timestamp,
                "swept_side": _swept_side(pop, i),
                "close_beyond_refA": _beyond(pop, i, "A", "close"),
                "close_beyond_refB": _beyond(pop, i, "B", "close"),
                "extend_beyond_refA": _beyond(pop, i, "A", "extend"),
                "bars_to_next_event": _duration_to_next_event(pop, i),
            }, ensure_ascii=False) + "\n")

    (out / "run_manifest.json").write_text(json.dumps({
        "prereg_path": PREREG_PATH,
        "prereg_frozen_prefix_sha256": PREREG_SHA256,
        "prereg_freeze_whole_file_sha256": PREREG_FREEZE_SHA256,
        "corpus_path": pop.corpus_path,
        "corpus_sha256": pop.corpus_sha256,
        "active_version": get_active_version(),
        # Provenance for the F-071 class: the committed repo is not always the running
        # system. Pin the resolver source this run actually executed against.
        "resolver_source_sha256": _sha256_file(
            Path(__file__).resolve().parents[2] / "features" / "crt_state_resolver.py"
        ),
        "instrument": instrument,
        "alpha_primary": ALPHA_PRIMARY,
        "alpha_secondary_bonferroni": ALPHA_SECONDARY,
        "n_min_per_group": N_MIN_PER_GROUP,
        "block_bars": BLOCK_BARS,
        "n_boot": N_BOOT,
        "economic_claims_allowed": False,
        "promise_rung_max_claim": "PL-0",
    }, indent=2), encoding="utf-8")

    return results
