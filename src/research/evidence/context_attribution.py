"""MC-CTXATTR-XAUUSD-M15-V1 — does any context family add value beyond CRT state alone?

CH-v3-unified-market-structure-v1. SEM-036. Object frozen in
`docs/research/context_attribution_object.md`. Contract sealed and floor-green BEFORE this
module existed (the F-083 lesson).

THE QUESTION, AND WHY IT IS ASKED THIS WAY
------------------------------------------
"Which context features improve expectancy beyond CRT alone?" cannot be asked of CRT's own
trade ledger: that ledger holds **3 trades** across 47,275 XAUUSD M15 bars. Eleven families
against n=3 is not an underpowered study, it is not a study.

So the population is inverted, exactly as F-086 did: every bar, both directions, labelled at
source by `multi_tp_walk` under the production two-target geometry (SEM-017) — 94,314 units on
the PRIMARY arm. The CRT state is not discarded, it becomes the STRATUM.

"BEYOND CRT ALONE" IS A CONSTRUCTION, NOT A CAVEAT
--------------------------------------------------
The primary metric is `delta_within_stratum`: the mean-preserving size overlay
(`rnet_overlay.overlay`'s formula, k=0.5 frozen) computed INSIDE each `crt_state_after`
stratum, then aggregated stratum-size-weighted. Because the weights average to 1 within every
stratum, a family cannot score by proxying for CRT state — the CRT contribution is differenced
out by construction rather than argued away in prose.

`delta_marginal` (the same overlay ignoring strata) is computed too, and
`crt_proxy_component = delta_marginal - delta_within_stratum` is reported. That difference IS
the part of a naive result that was really just CRT state wearing a context family's name.
Making it visible is half the point of the program.

WHAT A PASS WOULD AND WOULD NOT MEAN
------------------------------------
Would: this family carries information orthogonal to CRT state, on a population production does
not trade, at Authority-Ladder rung 1.

Would NOT: a G001 improvement, permission to size, or permission to enter
`context_attribution.promoted_families` — which stays empty. The base rate here is about
-0.29R (F-086), so a positive delta can mean losing less rather than earning, and `E>0` is
deliberately not a gate clause.

POWER IS THIN AND THAT IS PRE-REGISTERED
-----------------------------------------
F-086 MEASURED the label autocorrelation (+0.292 at lag 1, +0.003 by lag 20), giving an
effective independent sample near 941 per direction rather than 47,157. Against 22 tests that
is not much. `INSUFFICIENT` is a registrable outcome, not a failure to be re-cut — and the
contract's `kill_criteria` says so before any number was seen.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable, Optional

from data_ingestion.dataset_integrity import validate_dataset
from research.evidence.asymmetry_contract import (
    CORPUS,
    CORPUS_SHA,
    EMBARGO_BARS,
    HOLDOUT_START,
    HORIZON_BARS,
    _parse_ts,
)
from research.evidence.magnitude_prior import OVERLAY_K, _sign
from research.evidence.run_close_out import finalize_run

CONTRACT_ID = "MC-CTXATTR-XAUUSD-M15-V1"
SEM_ID = "SEM-036"
K = OVERLAY_K  # 0.5, frozen; imported rather than redeclared so it cannot drift

OUT_DEFAULT = Path("docs/research-readiness/context_attribution/mc_ctxattr_xauusd_m15_v1")
LABELS_DEFAULT = Path("results/research/oracle_labels/XAUUSD_M15/labels.csv")
SNAPSHOT_DEFAULT = Path("logs/bar_structure/XAUUSD_bar_structure.jsonl")

#: The PRIMARY arm declared at `labeler.py:76-79`. The other three label arms are robustness,
#: not three extra shots at significance, and are never gated.
PRIMARY_SL_GEOM = "disp_bar"
PRIMARY_TIE_BREAK = "production"

#: Pre-registered gate constants. Changing any of these after seeing holdout y requires a NEW
#: MC-* id — they are module constants, not parameters, so a sweep is a visible code edit.
MIN_CELL_N = 30
BH_Q = 0.10
PERM_BLOCK_BARS = 40
PERM_N = 199
PASS_CEILING = 6
_BAR_MINUTES = 15


# ---------------------------------------------------------------------------------------
# Family predicates — declared in the contract's `features.name_binding` BEFORE any y was seen
# ---------------------------------------------------------------------------------------

def _match(direction_name: Optional[str], side: str) -> bool:
    """A snapshot direction field (LONG/SHORT/NONE) agreeing with a label side (long/short)."""
    if not direction_name:
        return False
    return direction_name.upper() == side.upper()


def _agree_parent_crt(s: dict, side: str) -> Optional[bool]:
    bias = s.get("parent_bias")
    if not bias or bias == "NONE":
        return None  # no bias expressed: excluded from BOTH cells, never counted as disagree
    return _match(bias, side)


def _agree_htf(s: dict, side: str) -> Optional[bool]:
    st = s.get("htf_state")
    if not st or st == "UNKNOWN":
        return None
    bias = s.get("parent_bias")
    if not bias or bias == "NONE":
        return None
    return st == "EXPANSION" and _match(bias, side)


def _agree_objective(s: dict, side: str) -> Optional[bool]:
    st = s.get("objective_status")
    if not st or st == "NONE":
        return None
    return st == "EXISTS" and _match(s.get("objective_direction"), side)


def _zone_agree(family: str) -> Callable[[dict, str], Optional[bool]]:
    def f(s: dict, side: str) -> Optional[bool]:
        if not s.get(f"{family}_present"):
            return None  # absence is not disagreement — it is no reading
        return bool(s.get(f"{family}_bullish")) == (side == "long")
    return f


def _agree_choch(s: dict, side: str) -> Optional[bool]:
    if s.get("choch_basis") != "PIPELINE_FM057_FM054":
        return None
    v = s.get("choch_value")
    if v is None or v == 0:
        return None
    return (v > 0) == (side == "long")


def _agree_eqh_eql(s: dict, side: str) -> Optional[bool]:
    """Resting liquidity on the far side of the trade: a long wants equal-lows below (a pool to
    push off), a short wants equal-highs above."""
    hi, lo = bool(s.get("eqh_present")), bool(s.get("eql_present"))
    if hi == lo:
        return None  # both or neither: no asymmetric reading
    return lo if side == "long" else hi


def _agree_pdh_pdl(s: dict, side: str) -> Optional[bool]:
    if not (s.get("pdh_present") and s.get("pdl_present")):
        return None
    dh, dl = s.get("pdh_distance"), s.get("pdl_distance")
    if dh is None or dl is None:
        return None
    nearer_low = abs(dl) < abs(dh)
    return nearer_low if side == "long" else (not nearer_low)


SINGLE_FAMILIES: "dict[str, Callable[[dict, str], Optional[bool]]]" = {
    "parent_crt": _agree_parent_crt,
    "htf": _agree_htf,
    "objective": _agree_objective,
    "fvg": _zone_agree("fvg"),
    "order_block": _zone_agree("order_block"),
    "breaker": _zone_agree("breaker"),
    "mitigation": _zone_agree("mitigation"),
    "choch": _agree_choch,
    "eqh_eql": _agree_eqh_eql,
    "pdh_pdl": _agree_pdh_pdl,
}


def _agree_composite(s: dict, side: str) -> Optional[bool]:
    """Majority of the ten single-family readings. Ties and all-abstain are excluded.

    NOT independent of its parts — it is a function of them. It is counted inside the 22
    pre-registered tests and inside the pass-count ceiling rather than presented as separate
    evidence, which is what the contract's `open_risks_non_blocking` records.
    """
    votes = [f(s, side) for f in SINGLE_FAMILIES.values()]
    seen = [v for v in votes if v is not None]
    if not seen:
        return None
    agree = sum(1 for v in seen if v)
    if agree * 2 == len(seen):
        return None
    return agree * 2 > len(seen)


FAMILIES = dict(SINGLE_FAMILIES)
FAMILIES["composite"] = _agree_composite
DIRECTIONS = ("long", "short")


# ---------------------------------------------------------------------------------------
# Loading and joining
# ---------------------------------------------------------------------------------------

def load_snapshot(path: Path) -> dict:
    """`bar_index -> snapshot record`, LIVE rows only.

    WARMUP rows carry no engine state and are excluded here rather than filtered downstream, so
    no arm can accidentally treat a null CRT state as a stratum.
    """
    by_bar: dict = {}
    corpus_shas: set = set()
    run_ids: set = set()
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            corpus_shas.add(rec.get("corpus_sha256"))
            run_ids.add(rec.get("run_id"))
            if rec.get("phase") != "LIVE":
                continue
            if not rec.get("crt_state_after"):
                continue
            by_bar[int(rec["bar_index"])] = rec
    if len(corpus_shas) != 1:
        raise ValueError(f"snapshot mixes {len(corpus_shas)} corpora: {sorted(corpus_shas)}")
    if len(run_ids) != 1:
        raise ValueError(f"snapshot mixes {len(run_ids)} runs: {sorted(run_ids)}")
    sha = corpus_shas.pop()
    if sha != CORPUS_SHA:
        raise ValueError(
            f"snapshot corpus_sha256 {sha} != contract corpus {CORPUS_SHA}. The join is legal "
            "only within one corpus; refusing rather than silently attributing."
        )
    return by_bar


def unit_rows(labels_csv: Path, snapshot: dict) -> list:
    """One record per (bar, direction) on the PRIMARY label arm, joined to its snapshot.

    Join key is `labels._pos == snapshot.bar_index`. Both are 0-based positions into the same
    corpus file, which is why the corpus sha is checked before any row is emitted.
    """
    import csv as _csv

    rows: list = []
    with labels_csv.open(encoding="utf-8", newline="") as fh:
        for rec in _csv.DictReader(fh):
            if rec["sl_geom"] != PRIMARY_SL_GEOM or rec["tie_break"] != PRIMARY_TIE_BREAK:
                continue
            pos = int(rec["_pos"])
            snap = snapshot.get(pos)
            if snap is None:
                continue
            try:
                y_net = float(rec["y_R_net"])
                y_gross = float(rec["y_R_gross"])
            except (TypeError, ValueError):
                continue
            if not (math.isfinite(y_net) and math.isfinite(y_gross)):
                continue
            side = str(rec["direction"]).lower()
            if side not in DIRECTIONS:
                continue
            rows.append({
                "bar_index": pos,
                "decision_ts": rec["timestamp"],
                "ts": _parse_ts(rec["timestamp"]),
                "side": side,
                "stratum": snap["crt_state_after"],
                "y_R_net": y_net,
                "y_R_gross": y_gross,
                "snap": snap,
            })
    rows.sort(key=lambda r: (r["ts"], r["side"]))
    return rows


def split_rows(rows: list) -> tuple:
    """Chronological holdout with embargo and purge, on the FROZEN MC-ASYM calendar.

    The boundary is WRITTEN to the manifest, not merely declared — F-083 found a contract that
    declared a split its run never executed, and the fix is that the run emits what it used.
    """
    embargo = timedelta(minutes=_BAR_MINUTES * EMBARGO_BARS)
    purge = timedelta(minutes=_BAR_MINUTES * HORIZON_BARS)
    train_last = HOLDOUT_START - max(embargo, purge)
    train = [r for r in rows if r["ts"] <= train_last]
    hold = [r for r in rows if r["ts"] >= HOLDOUT_START]
    dropped = [r for r in rows if train_last < r["ts"] < HOLDOUT_START]
    manifest = {
        "contract_id": CONTRACT_ID,
        "scheme": "single_holdout_chronologic",
        "holdout_start": HOLDOUT_START.isoformat(sep=" "),
        "train_last_allowed": train_last.isoformat(sep=" "),
        "embargo_bars": EMBARGO_BARS,
        "purge_horizon_bars": HORIZON_BARS,
        "n_train": len(train),
        "n_holdout": len(hold),
        "n_embargo_dropped": len(dropped),
        "first_holdout_bar_index": min((r["bar_index"] for r in hold), default=None),
        "last_train_bar_index": max((r["bar_index"] for r in train), default=None),
        "calendar_source": "research.evidence.asymmetry_contract (frozen, shared with MC-ASYM/MAGPRIOR/MRPRIOR/VCRTPRIOR)",
        "f086_stride_spent": False,
    }
    return train, hold, manifest


# ---------------------------------------------------------------------------------------
# The metric
# ---------------------------------------------------------------------------------------

def _mean(xs: list) -> Optional[float]:
    return (sum(xs) / len(xs)) if xs else None


def _overlay_cells(rows: list, predicate, side: str, y_key: str) -> tuple:
    """(agree_ys, disagree_ys) for one family x direction."""
    agree_ys: list = []
    dis_ys: list = []
    for r in rows:
        if r["side"] != side:
            continue
        verdict = predicate(r["snap"], side)
        if verdict is None:
            continue
        (agree_ys if verdict else dis_ys).append(r[y_key])
    return agree_ys, dis_ys


def _delta(agree_ys: list, dis_ys: list, k: float = K) -> Optional[float]:
    """Mean-preserving overlay delta: E[w*y] - E[y], w = 1+k on agree, 1-k on disagree.

    Identical formula to `rnet_overlay.overlay` — reused rather than reinvented so the two
    programs' numbers mean the same thing.
    """
    ys = agree_ys + dis_ys
    if not ys:
        return None
    e_y = sum(ys) / len(ys)
    e_wy = (sum((1.0 + k) * x for x in agree_ys) + sum((1.0 - k) * x for x in dis_ys)) / len(ys)
    return e_wy - e_y


def delta_within_stratum(rows: list, predicate, side: str, y_key: str) -> dict:
    """PRIMARY. Overlay computed inside each CRT stratum on STRATUM-CENTERED y, then
    aggregated stratum-size-weighted.

    TWO corrections are needed for this to actually mean "beyond CRT alone", and both were
    found by `test_delta_within_stratum_is_zero_when_context_is_pure_crt_proxy` BEFORE any
    outcome was computed:

    1. **Centering.** The raw overlay delta is `k * (n_a*mean_a - n_d*mean_d) / n`. If the
       context carries NO information (`mean_a == mean_d == m`) that reduces to
       `k * m * (n_a - n_d) / n` — non-zero whenever the cells are unbalanced and the stratum
       mean is non-zero. On this population the base rate is about -0.29R, so an
       information-free context with a lopsided agree/disagree split would score a spurious
       effect. Centering y on its own stratum mean first removes exactly that term: the
       centered cells satisfy `n_a*mean_a + n_d*mean_d == 0`, so the delta is zero iff the
       agree cell mean equals the stratum mean, which is the definition of "no within-stratum
       information".

    2. **Single-cell strata contribute nothing.** If every row in a stratum agrees (or every
       row disagrees) the overlay is not a contrast at all, it is a uniform rescale by `1+k`.
       Such a stratum carries no within-stratum evidence and is skipped rather than folded in
       as a large apparent effect.

    With both, a family cannot score by proxying for the stratum variable — verified
    numerically on a planted confound, not asserted in prose.
    """
    by_stratum: dict = defaultdict(list)
    for r in rows:
        if r["side"] == side:
            by_stratum[r["stratum"]].append(r)

    total_n = 0
    weighted = 0.0
    n_agree = n_dis = 0
    occupancy: dict = {}
    for stratum, srows in by_stratum.items():
        a, d = _overlay_cells(srows, predicate, side, y_key)
        n = len(a) + len(d)
        informative = bool(a) and bool(d)
        occupancy[stratum] = {
            "n_units": len(srows), "n_scored": n,
            "n_agree": len(a), "n_disagree": len(d),
            "informative": informative,
        }
        if not informative:
            continue
        m = (sum(a) + sum(d)) / n
        dl = _delta([x - m for x in a], [x - m for x in d])
        if dl is None:
            continue
        weighted += dl * n
        total_n += n
        n_agree += len(a)
        n_dis += len(d)
    return {
        "delta": (weighted / total_n) if total_n else None,
        "n_scored": total_n,
        "n_agree": n_agree,
        "n_disagree": n_dis,
        "n_strata": len([s for s, o in occupancy.items() if o["informative"]]),
        "stratum_occupancy": occupancy,
    }


def delta_marginal(rows: list, predicate, side: str, y_key: str) -> dict:
    """DIAGNOSTIC. The same overlay ignoring strata.

    `delta_marginal - delta_within_stratum` is the CRT-proxy component: the part of a naive
    result that was really the CRT state wearing this family's name.
    """
    a, d = _overlay_cells(rows, predicate, side, y_key)
    return {"delta": _delta(a, d), "n_agree": len(a), "n_disagree": len(d)}


# ---------------------------------------------------------------------------------------
# Nulls, controls, multiplicity
# ---------------------------------------------------------------------------------------

def block_permutation_p(rows: list, predicate, side: str, y_key: str,
                        observed: Optional[float], *, seed: int) -> Optional[float]:
    """Two-sided p from a BLOCK permutation null (block = 40 bars, 199 permutations).

    Block, not iid: F-086 MEASURED the label autocorrelation (+0.292 at lag 1, +0.003 by lag
    20), so an iid shuffle would understate the null's spread and manufacture significance.
    Blocks of `y` are rotated against the (unchanged) context, which destroys the
    context->outcome association while preserving both marginals and the autocorrelation.
    """
    if observed is None:
        return None
    side_rows = [r for r in rows if r["side"] == side]
    if len(side_rows) < PERM_BLOCK_BARS * 2:
        return None
    ys = [r[y_key] for r in side_rows]
    n = len(ys)
    n_blocks = max(1, n // PERM_BLOCK_BARS)
    rng = random.Random(seed)

    hits = 0
    for _ in range(PERM_N):
        blocks = [ys[i * PERM_BLOCK_BARS:(i + 1) * PERM_BLOCK_BARS] for i in range(n_blocks)]
        tail = ys[n_blocks * PERM_BLOCK_BARS:]
        rng.shuffle(blocks)
        shuffled = [y for b in blocks for y in b] + tail
        permuted = [dict(r, **{y_key: shuffled[i]}) for i, r in enumerate(side_rows)]
        d = delta_within_stratum(permuted, predicate, side, y_key)["delta"]
        if d is not None and abs(d) >= abs(observed):
            hits += 1
    # +1 / +1 so p is never exactly 0: with 199 permutations the attainable floor is 0.005, and
    # reporting 0.0 would claim more resolution than the design has.
    return (hits + 1) / (PERM_N + 1)


def shuffled_context_control(rows: list, predicate, side: str, y_key: str, *, seed: int) -> Optional[float]:
    """Permute the context WITHIN each stratum. The exact null for `delta_within_stratum`:
    it destroys the context->outcome link while preserving CRT state and both marginals."""
    by_stratum: dict = defaultdict(list)
    for r in rows:
        if r["side"] == side:
            by_stratum[r["stratum"]].append(r)
    rng = random.Random(seed)
    rebuilt: list = []
    for srows in by_stratum.values():
        snaps = [r["snap"] for r in srows]
        rng.shuffle(snaps)
        rebuilt.extend(dict(r, snap=snaps[i]) for i, r in enumerate(srows))
    return delta_within_stratum(rebuilt, predicate, side, y_key)["delta"]


def long_only_control(rows: list, y_key: str) -> dict:
    """Passive same-direction exposure. THE binding control, not zero.

    XAUUSD rose across this corpus. F-086 measured positive cell counts collapsing 65->8,
    56->1 and 2->0 once controlled against passive long exposure, which is why a delta must
    beat this rather than beat zero.
    """
    ys = [r[y_key] for r in rows if r["side"] == "long"]
    return {"n": len(ys), "mean": _mean(ys)}


def benjamini_hochberg(pvals: dict, q: float = BH_Q) -> dict:
    """BH-FDR survival flags over the pre-registered family of tests.

    BH rather than Bonferroni: at an effective independent n near 941 per direction, Bonferroni
    over 22 has essentially no power and would guarantee a vacuous null whatever is there.
    """
    items = sorted(((k, p) for k, p in pvals.items() if p is not None), key=lambda kv: kv[1])
    m = len(items)
    survive = {k: False for k in pvals}
    largest = -1
    for i, (_, p) in enumerate(items, start=1):
        if p <= (i / m) * q:
            largest = i
    for i, (k, _) in enumerate(items, start=1):
        survive[k] = i <= largest
    return survive


# ---------------------------------------------------------------------------------------
# Measure
# ---------------------------------------------------------------------------------------

def measure(rows: list, *, y_key: str = "y_R_net", seed: int = 20260829) -> dict:
    train, hold, split = split_rows(rows)
    cells: dict = {}
    pvals: dict = {}

    lo_train = long_only_control(train, y_key)
    lo_hold = long_only_control(hold, y_key)

    for fam, pred in FAMILIES.items():
        for side in DIRECTIONS:
            key = f"{fam}|{side}"
            tr = delta_within_stratum(train, pred, side, y_key)
            ho = delta_within_stratum(hold, pred, side, y_key)
            ho_marg = delta_marginal(hold, pred, side, y_key)
            cell_seed = int(hashlib.sha256(f"{seed}|{key}".encode()).hexdigest()[:8], 16)
            p = block_permutation_p(hold, pred, side, y_key, ho["delta"], seed=cell_seed)
            shuf = shuffled_context_control(hold, pred, side, y_key, seed=cell_seed)
            pvals[key] = p
            cells[key] = {
                "family": fam,
                "direction": side,
                "train": {k: v for k, v in tr.items() if k != "stratum_occupancy"},
                "holdout": {k: v for k, v in ho.items() if k != "stratum_occupancy"},
                "holdout_stratum_occupancy": ho["stratum_occupancy"],
                "delta_marginal_holdout": ho_marg["delta"],
                "crt_proxy_component": (
                    None if ho_marg["delta"] is None or ho["delta"] is None
                    else ho_marg["delta"] - ho["delta"]
                ),
                "sign_match": (
                    _sign(tr["delta"]) is not None
                    and _sign(tr["delta"]) == _sign(ho["delta"])
                ),
                "p_block_permutation": p,
                "control_shuffled_context": shuf,
                "control_long_only_holdout": lo_hold["mean"],
            }

    survive = benjamini_hochberg(pvals)
    n_pass = 0
    for key, c in cells.items():
        c["bh_fdr_survives"] = survive.get(key, False)
        ho = c["holdout"]
        d = ho["delta"]
        beats_controls = (
            d is not None
            and c["control_shuffled_context"] is not None
            and abs(d) > abs(c["control_shuffled_context"])
            and lo_hold["mean"] is not None
            and abs(d) > abs(lo_hold["mean"])
        )
        powered = ho["n_agree"] >= MIN_CELL_N and ho["n_disagree"] >= MIN_CELL_N
        if not powered:
            c["verdict"] = "INSUFFICIENT"
        elif c["sign_match"] and c["bh_fdr_survives"] and beats_controls:
            c["verdict"] = "DIAGNOSTIC_PASS"
            n_pass += 1
        else:
            c["verdict"] = "DIAGNOSTIC_FAIL"
        c["beats_controls"] = beats_controls
        c["powered"] = powered

    multiplicity_artifact = n_pass > PASS_CEILING
    return {
        "contract_id": CONTRACT_ID,
        "sem_id": SEM_ID,
        "authority": "RESEARCH_ONLY",
        "economic_claims_allowed": False,
        "y_key": y_key,
        "k_frozen": K,
        "n_units": len(rows),
        "n_tests_preregistered": len(FAMILIES) * len(DIRECTIONS),
        "n_pass": n_pass,
        "pass_ceiling": PASS_CEILING,
        "multiplicity_artifact_suspected": multiplicity_artifact,
        "verdict": (
            "MULTIPLICITY_ARTIFACT_SUSPECTED" if multiplicity_artifact
            else ("DIAGNOSTIC_PASS" if n_pass else "NO_FAMILY_CLEARS")
        ),
        "controls": {"long_only_train": lo_train, "long_only_holdout": lo_hold},
        "split": split,
        "cells": cells,
        "not": [
            "G001",
            "an economic claim",
            "authority to size",
            "authority to enter context_attribution.promoted_families",
            "a statement about production's executed trades",
            "E>0",
            "F-086 stride holdout",
            "a k sweep",
        ],
    }


def fingerprint(rows: list) -> dict:
    h = hashlib.sha256()
    for r in rows:
        h.update(f"{r['bar_index']}|{r['decision_ts']}|{r['side']}|{r['stratum']}|"
                 f"{r['y_R_net']:.10f}".encode())
    return {
        "contract_id": CONTRACT_ID,
        "n": len(rows),
        "sha256": h.hexdigest(),
        "corpus_path": str(CORPUS),
        "corpus_sha256": CORPUS_SHA,
        "primary_arm": {"sl_geom": PRIMARY_SL_GEOM, "tie_break": PRIMARY_TIE_BREAK},
        "population_hash_inputs": [
            "instrument", "timestamp", "direction", "bar_index", "crt_state_after",
            "sl_geom", "tie_break", "corpus_path", "corpus_sha256",
            "snapshot_schema_version", "contract_id",
        ],
    }


def run(out_dir: Optional[Path] = None, *, labels: Optional[Path] = None,
        snapshot: Optional[Path] = None, y_key: str = "y_R_net") -> dict:
    out_dir = out_dir or OUT_DEFAULT
    labels = labels or LABELS_DEFAULT
    snapshot = snapshot or SNAPSHOT_DEFAULT
    validate_dataset(str(CORPUS))

    snap = load_snapshot(snapshot)
    rows = unit_rows(labels, snap)
    if not rows:
        raise SystemExit("join produced 0 rows -- labels and snapshot do not share bar indices")

    report = measure(rows, y_key=y_key)
    out_dir.mkdir(parents=True, exist_ok=True)
    fp = fingerprint(rows)
    (out_dir / "population_fingerprint.json").write_text(
        json.dumps(fp, indent=2), encoding="utf-8")
    (out_dir / "split_manifest.json").write_text(
        json.dumps(report["split"], indent=2), encoding="utf-8")
    (out_dir / "metrics.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")
    with (out_dir / "ledger.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for key, c in report["cells"].items():
            fh.write(json.dumps({"cell": key, **{k: v for k, v in c.items()
                                                 if k != "holdout_stratum_occupancy"}},
                                default=str) + "\n")
    report["provenance"] = finalize_run(CONTRACT_ID, out_dir)
    report["fingerprint_sha256"] = fp["sha256"]
    return report


def main(argv=None) -> int:
    import argparse

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=str(OUT_DEFAULT))
    p.add_argument("--labels", default=str(LABELS_DEFAULT))
    p.add_argument("--snapshot", default=str(SNAPSHOT_DEFAULT))
    p.add_argument("--y", default="y_R_net", choices=["y_R_net", "y_R_gross"])
    args = p.parse_args(argv)
    rep = run(Path(args.out), labels=Path(args.labels),
              snapshot=Path(args.snapshot), y_key=args.y)
    print(f"verdict={rep['verdict']}  n_units={rep['n_units']:,}  "
          f"pass={rep['n_pass']}/{rep['n_tests_preregistered']}")
    for key, c in sorted(rep["cells"].items()):
        print(f"  {key:<24} {c['verdict']:<16} "
              f"delta_ho={c['holdout']['delta']}  p={c['p_block_permutation']}  "
              f"n_a={c['holdout']['n_agree']} n_d={c['holdout']['n_disagree']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
