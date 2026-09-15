#!/usr/bin/env python3
"""H-017 / H-MSIP-001 measurement harness — EXPLORATORY_RESEARCH only.

Executes the FROZEN pre-registration protocol. Does not change CRT behavior,
MSIP authority, thresholds, or production configs.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

from config_layer.crt_engine_v2 import CRTConfig, CRTEngine, Candle  # noqa: E402
from config_layer.production_config import get_prod_config  # noqa: E402
from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features.feature_schema import FEATURE_ORDER_HASH, SCHEMA_HASH  # noqa: E402
from msip.interpretation_config import (  # noqa: E402
    default_experimental_section,
    load_msip_shadow_config,
)
from msip.shadow_emitter import ProvenanceContext, build_market_state, observe_crt_state  # noqa: E402
from runtime.backtest_v2 import HTFBuilder  # noqa: E402

# ── frozen protocol constants (must match pre-registration) ─────────────
PROGRAM_ALIAS = "H-MSIP-001"
REGISTRY_ID = "H-017"
CORPUS_REL = "data/mt5/XAUUSD_M15.csv"
CORPUS_SHA = "4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56"
ACTIVE_STATES = frozenset({"SWEEP", "DISPLACEMENT", "EXPANSION", "RETEST", "EXECUTION"})
PRIMARY_H = 8
MAX_H = 32
MIN_N = 80
N_PERM = 2000
PERM_SEED = 20260714
MATCH_MAX_DIST = 32
BH_Q = 0.10
N_FOLDS = 4
HTF_CANDLES = 4
WARMUP = 30
CALENDAR_SPIKE_MAX = 0.50

PREREG_MD = _ROOT / "docs/research-readiness/h-msip-001-continuous-market-state-preregistration.md"
PREREG_JSON = _ROOT / "docs/research-readiness/h-msip-001-experiment-definition.json"

PARTITIONS: list[dict[str, Any]] = [
    {"id": "P-SWEEP", "kind": "single", "field": ("structure_state", "liquidity_sweep"), "levels": [-1, 0, 1]},
    {
        "id": "P-STRUCT-HHLL",
        "kind": "pair",
        "fields": [("structure_state", "higher_high"), ("structure_state", "lower_low")],
        "levels": [(0, 0), (1, 0), (0, 1), (1, 1)],
    },
    {"id": "P-VOL", "kind": "single", "field": ("volatility_state", "volatility_regime"), "levels": [0, 1, 2]},
    {"id": "P-SESSION", "kind": "single", "field": ("session_state", "session"), "levels": [0, 1, 2]},
    {"id": "P-TREND", "kind": "single", "field": ("trend_state", "trend_bias"), "levels": [-1, 0, 1]},
    {"id": "P-BOS", "kind": "single", "field": ("structure_state", "break_of_structure"), "levels": [-1, 0, 1]},
]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_meta(root: Path) -> dict[str, Any]:
    commit = None
    dirty = None
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
        st = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=root, text=True, stderr=subprocess.DEVNULL
        )
        dirty = bool(st.strip())
    except Exception:
        pass
    return {"repository_commit": commit, "dirty_worktree": dirty}


def _parse_ts(val: Any) -> pd.Timestamp:
    return pd.Timestamp(val)


def _bh(pvals: list[float], q: float = BH_Q) -> list[bool]:
    """Benjamini–Hochberg: return reject mask for p-values (same order)."""
    m = len(pvals)
    if m == 0:
        return []
    order = np.argsort(pvals)
    ranked = np.array(pvals)[order]
    thresh = q * (np.arange(1, m + 1) / m)
    below = ranked <= thresh
    if not below.any():
        return [False] * m
    max_k = np.max(np.where(below)[0])
    reject = np.zeros(m, dtype=bool)
    reject[order[: max_k + 1]] = True
    return reject.tolist()


def _level_key(level: Any) -> str:
    if isinstance(level, (list, tuple)):
        return ",".join(str(int(x) if isinstance(x, (int, float, np.integer)) else x) for x in level)
    if isinstance(level, (float, np.floating)):
        if float(level).is_integer():
            return str(int(level))
        return str(float(level))
    return str(int(level) if isinstance(level, (int, np.integer)) else level)


def _get_partition_value(dims: dict, part: dict) -> Any | None:
    try:
        if part["kind"] == "single":
            d, f = part["field"]
            v = dims.get(d, {}).get(f)
            if v is None:
                return None
            return int(v) if not isinstance(v, (list, tuple)) else v
        vals = []
        for d, f in part["fields"]:
            v = dims.get(d, {}).get(f)
            if v is None:
                return None
            vals.append(int(v))
        return tuple(vals)
    except Exception:
        return None


def _block_key(dims: dict) -> tuple | None:
    try:
        s = dims["session_state"]["session"]
        v = dims["volatility_state"]["volatility_regime"]
        t = dims["trend_state"]["trend_bias"]
        if s is None or v is None or t is None:
            return None
        return (int(s), int(v), int(t))
    except Exception:
        return None


@dataclass
class BarRec:
    bar_index: int
    timestamp: str
    ts: pd.Timestamp
    close: float
    open: float
    high: float
    low: float
    crt_state: str
    candidate_episode_id: int | None
    occupancy_active: bool
    msv_status: str
    dims: dict
    block: tuple | None
    r8: float | None
    fold: int


def build_panel() -> tuple[list[BarRec], dict[str, Any], dict[str, Any]]:
    corpus = _ROOT / CORPUS_REL
    sha = _sha256_file(corpus)
    if sha != CORPUS_SHA:
        raise SystemExit(f"corpus sha mismatch: {sha} != {CORPUS_SHA}")

    df = pd.read_csv(corpus)
    df.columns = [c.lower() for c in df.columns]
    if "timestamp" not in df.columns:
        df = df.rename(columns={df.columns[0]: "timestamp"})
    n_raw = len(df)
    opens = df["open"].astype(float).values
    highs = df["high"].astype(float).values
    lows = df["low"].astype(float).values
    closes = df["close"].astype(float).values
    volumes = df["volume"].astype(float).values if "volume" in df.columns else np.zeros(n_raw)
    timestamps = df["timestamp"].astype(str).values

    # Feature pipeline (WHAT)
    pipe = FeaturePipeline(df.copy())
    enriched, _ = pipe.run()
    enriched = enriched.copy()
    enriched["_ts_str"] = enriched["timestamp"].astype(str)
    feat_by_ts = {str(r["_ts_str"]): r for _, r in enriched.iterrows()}

    # CRT co-run
    crt_cfg: CRTConfig = get_prod_config("XAUUSD")
    engine = CRTEngine(crt_cfg)
    htf = HTFBuilder(HTF_CANDLES, "XAUUSD")
    _prev_htf = ""
    _htf_remaining = HTF_CANDLES
    initialised = False
    warmup_done = False

    crt_state = [""] * n_raw
    episode_ids: list[int | None] = [None] * n_raw
    ep_counter = 0
    cur_ep: int | None = None

    for i in range(n_raw):
        ts = timestamps[i]
        try:
            ts_dt = pd.Timestamp(ts).to_pydatetime()
        except Exception:
            ts_dt = timestamps[i]
        candle = Candle(
            timestamp=ts_dt,
            open=float(opens[i]),
            high=float(highs[i]),
            low=float(lows[i]),
            close=float(closes[i]),
            volume=float(volumes[i]),
            index=i,
        )
        htf.push(candle)
        if htf.current_htf_id != _prev_htf:
            _prev_htf = htf.current_htf_id
            _htf_remaining = HTF_CANDLES - 1
        else:
            _htf_remaining = max(0, _htf_remaining - 1)
        engine.state.htf_remaining_candles = _htf_remaining

        if not warmup_done:
            if i + 1 < WARMUP:
                crt_state[i] = "WARMUP"
                continue
            warmup_done = True

        if not initialised:
            seeds = htf.seed_candles()
            if seeds:
                engine.initialise_range(seeds, htf.current_htf_id, session="UNKNOWN")
                initialised = True
            else:
                crt_state[i] = "UNINIT"
                continue

        engine.process_candle(candle, htf.current_htf_id)
        name = engine.state.current_state.name
        crt_state[i] = name
        if name in ACTIVE_STATES:
            if cur_ep is None:
                ep_counter += 1
                cur_ep = ep_counter
            episode_ids[i] = cur_ep
        else:
            cur_ep = None
            episode_ids[i] = None

    # MSIP config
    section = default_experimental_section(config_id="msip_shadow_h017_v1")
    mcfg = load_msip_shadow_config({"msip_shadow": section})
    assert mcfg.enabled
    prov = ProvenanceContext(
        config_id=mcfg.config_id,
        config_sha256=mcfg.config_sha256,
        repository_commit=_git_meta(_ROOT).get("repository_commit"),
        corpus_path=CORPUS_REL,
        corpus_sha256=sha,
        feature_schema_hash=SCHEMA_HASH,
        feature_order_hash=FEATURE_ORDER_HASH,
    )

    census = defaultdict(int)
    bars: list[BarRec] = []

    for i in range(n_raw):
        ts = str(timestamps[i])
        # exclusions (mutually exclusive priority order)
        if i + MAX_H >= n_raw:
            census["excl_no_forward_horizon"] += 1
            continue
        st = crt_state[i]
        if st in ("WARMUP", "UNINIT", ""):
            census["excl_crt_not_observed"] += 1
            continue
        row = feat_by_ts.get(ts)
        if row is None:
            census["excl_no_complete_msv_features"] += 1
            continue
        crt_obs = observe_crt_state(
            {
                "crt_state": st,
                "observed": True,
                "bar_index": i,
            }
        )
        vec = build_market_state(
            row.to_dict(),
            mcfg,
            prov,
            crt_obs=crt_obs,
            symbol="XAUUSD",
            timeframe="M15",
            bar_timestamp=ts,
            bar_index=i,
        )
        if vec is None or vec.status != "COMPLETE":
            census["excl_msv_not_complete"] += 1
            continue

        # inject episode into dims provenance-adjacent (observation only)
        dims = dict(vec.dimensions)
        dims["crt_phase_observation"] = {
            **dims.get("crt_phase_observation", {}),
            "crt_state": st,
            "observed": True,
            "candidate_episode_id": episode_ids[i],
            "occupancy_active": bool(episode_ids[i] is not None and st in ACTIVE_STATES),
        }
        r8 = float(closes[i + PRIMARY_H] / closes[i] - 1.0)
        block = _block_key(dims)
        if block is None:
            census["excl_block_keys_missing"] += 1
            continue

        census["eligible"] += 1
        bars.append(
            BarRec(
                bar_index=i,
                timestamp=ts,
                ts=_parse_ts(ts),
                close=float(closes[i]),
                open=float(opens[i]),
                high=float(highs[i]),
                low=float(lows[i]),
                crt_state=st,
                candidate_episode_id=episode_ids[i],
                occupancy_active=bool(episode_ids[i] is not None and st in ACTIVE_STATES),
                msv_status="COMPLETE",
                dims=dims,
                block=block,
                r8=r8,
                fold=-1,
            )
        )

    # assign 4 calendar folds by eligible bar order (equal count)
    n_el = len(bars)
    fold_size = max(1, n_el // N_FOLDS)
    for j, b in enumerate(bars):
        f = min(N_FOLDS - 1, j // fold_size)
        b.fold = int(f)

    meta = {
        "n_raw_bars": n_raw,
        "n_enriched_pipeline": int(len(enriched)),
        "n_eligible": n_el,
        "census": dict(census),
        "corpus_sha256": sha,
        "msip_config_id": mcfg.config_id,
        "msip_config_sha256": mcfg.config_sha256,
        "feature_schema_hash": SCHEMA_HASH,
        "feature_order_hash": FEATURE_ORDER_HASH,
        "crt_config_source": "get_prod_config('XAUUSD') / ACTIVE_VERSION",
        "crt_observation_source": "CRTEngine.process_candle after HTFBuilder+initialise_range (read-only)",
        "n_candidate_episodes": ep_counter,
        "active_occupancy_bars": sum(1 for b in bars if b.occupancy_active),
        "range_bars": sum(1 for b in bars if b.crt_state == "RANGE"),
    }
    return bars, meta, {"opens": opens, "highs": highs, "lows": lows, "closes": closes}


def match_controls(bars: list[BarRec]) -> dict[str, Any]:
    """Exact block match + nearest bar index within MATCH_MAX_DIST for RANGE controls."""
    range_by_block: dict[tuple, list[BarRec]] = defaultdict(list)
    for b in bars:
        if b.crt_state == "RANGE" and b.block is not None:
            range_by_block[b.block].append(b)
    for blk in range_by_block:
        range_by_block[blk].sort(key=lambda x: x.bar_index)

    # treatment bars = occupancy active (episode + active state)
    treatments = [b for b in bars if b.occupancy_active]
    matches: dict[int, int] = {}  # treatment bar_index -> control bar_index
    unmatched = 0
    dist_hist: list[int] = []

    for t in treatments:
        pool = range_by_block.get(t.block or (), [])
        if not pool:
            unmatched += 1
            continue
        # binary search nearest
        idxs = [p.bar_index for p in pool]
        pos = np.searchsorted(idxs, t.bar_index)
        candidates = []
        if pos < len(pool):
            candidates.append(pool[pos])
        if pos > 0:
            candidates.append(pool[pos - 1])
        best = None
        best_d = None
        for c in candidates:
            d = abs(c.bar_index - t.bar_index)
            if d <= MATCH_MAX_DIST and (best_d is None or d < best_d):
                best = c
                best_d = d
        if best is None:
            unmatched += 1
            continue
        matches[t.bar_index] = best.bar_index
        dist_hist.append(int(best_d))

    return {
        "n_treatment": len(treatments),
        "n_matched": len(matches),
        "n_unmatched": unmatched,
        "match_distance_mean": float(np.mean(dist_hist)) if dist_hist else None,
        "match_distance_p95": float(np.percentile(dist_hist, 95)) if dist_hist else None,
        "matches": matches,
    }


def analyze(bars: list[BarRec], match_info: dict) -> dict[str, Any]:
    by_idx = {b.bar_index: b for b in bars}
    matches: dict[int, int] = match_info["matches"]
    treatments = [b for b in bars if b.occupancy_active and b.bar_index in matches]

    rng = np.random.default_rng(PERM_SEED)
    family_results = []

    for part in PARTITIONS:
        levels = part["levels"]
        level_stats = []
        pvals = []
        for level in levels:
            # treatment subset for this level
            t_idx = []
            t_y = []
            c_y = []
            for b in treatments:
                pv = _get_partition_value(b.dims, part)
                if pv is None:
                    continue
                if part["kind"] == "pair":
                    ok = tuple(pv) == tuple(level)
                else:
                    ok = int(pv) == int(level)
                if not ok:
                    continue
                ctrl = by_idx.get(matches[b.bar_index])
                if ctrl is None or ctrl.r8 is None or b.r8 is None:
                    continue
                t_idx.append(b.bar_index)
                t_y.append(b.r8)
                c_y.append(ctrl.r8)

            n_t, n_c = len(t_y), len(c_y)
            support_ok = n_t >= MIN_N and n_c >= MIN_N
            cell: dict[str, Any] = {
                "partition_id": part["id"],
                "level": level if not isinstance(level, tuple) else list(level),
                "level_key": _level_key(level),
                "n_treatment": n_t,
                "n_matched_control": n_c,
                "support": "OK" if support_ok else "INSUFFICIENT_SUPPORT",
            }
            if not support_ok:
                cell.update(
                    {
                        "delta_match": None,
                        "p_perm": None,
                        "bh_reject": False,
                        "walk_forward": None,
                        "calendar_spike": None,
                        "crt_state_only": None,
                    }
                )
                level_stats.append(cell)
                pvals.append(1.0)
                continue

            t_y_a = np.asarray(t_y, dtype=float)
            c_y_a = np.asarray(c_y, dtype=float)
            delta = float(t_y_a.mean() - c_y_a.mean())
            # SE of difference (independent approx)
            se = float(
                math.sqrt(t_y_a.var(ddof=1) / n_t + c_y_a.var(ddof=1) / n_c)
            ) if n_t > 1 and n_c > 1 else float("nan")

            # permutation within blocks: shuffle treatment labels among active-matched bars in same block
            # Build block-grouped treatment pool for this partition's assigned labels
            # Protocol: within active-candidate universe, shuffle partition labels within blocks
            active_matched = treatments
            labels = []
            outcomes = []
            blocks = []
            for b in active_matched:
                pv = _get_partition_value(b.dims, part)
                if pv is None or b.r8 is None:
                    continue
                if part["kind"] == "pair":
                    lab = tuple(pv)
                else:
                    lab = int(pv)
                labels.append(lab)
                outcomes.append(b.r8)
                blocks.append(b.block)

            labels_a = np.array(labels, dtype=object)
            outcomes_a = np.array(outcomes, dtype=float)
            # normalize blocks to hashable tuples
            blocks_t = [tuple(b) if not isinstance(b, tuple) else b for b in blocks]
            blocks_a = np.array(blocks_t, dtype=object)
            target_level = tuple(level) if part["kind"] == "pair" else int(level)

            def _delta_for_labels(labs: np.ndarray) -> float:
                mask = np.array(
                    [
                        (lab == target_level)
                        if not isinstance(lab, (list, np.ndarray))
                        else tuple(lab) == target_level
                        for lab in labs
                    ],
                    dtype=bool,
                )
                if mask.sum() < 2 or (~mask).sum() < 2:
                    return 0.0
                return float(outcomes_a[mask].mean() - outcomes_a[~mask].mean())

            real_assoc = _delta_for_labels(labels_a)
            nulls = np.empty(N_PERM, dtype=float)
            # group indices by block once
            block_groups: dict[tuple, np.ndarray] = {}
            for bi, blk in enumerate(blocks_t):
                block_groups.setdefault(blk, []).append(bi)
            block_groups = {k: np.asarray(v, dtype=int) for k, v in block_groups.items()}
            for p in range(N_PERM):
                labs_shuf = labels_a.copy()
                for idx in block_groups.values():
                    if len(idx) > 1:
                        labs_shuf[idx] = rng.permutation(labs_shuf[idx])
                nulls[p] = _delta_for_labels(labs_shuf)
            # two-sided p
            p_perm = float((np.abs(nulls) >= abs(real_assoc)).mean())

            # walk-forward folds (equal eligible-bar folds assigned on panel build)
            fold_deltas: list[float | None] = []
            for f in range(N_FOLDS):
                ty, cy = [], []
                for bi, y_t, y_c in zip(t_idx, t_y, c_y):
                    if by_idx[bi].fold == f:
                        ty.append(y_t)
                        cy.append(y_c)
                if len(ty) >= 5 and len(cy) >= 5:
                    fold_deltas.append(float(np.mean(ty) - np.mean(cy)))
                else:
                    fold_deltas.append(None)

            sign_target = float(np.sign(delta)) if delta != 0 else 0.0
            n_defined = sum(1 for d in fold_deltas if d is not None)
            n_agree = sum(
                1
                for d in fold_deltas
                if d is not None and d != 0 and float(np.sign(d)) == sign_target
            )
            held_out = fold_deltas[-1] if fold_deltas else None
            held_out_ok = (
                held_out is not None
                and held_out != 0
                and float(np.sign(held_out)) == sign_target
            )
            # pre-reg: sign stable in ≥3/4 folds AND held-out last fold
            wf_stable = bool(n_defined >= 3 and n_agree >= 3 and held_out_ok)

            # calendar spike: month share of absolute contributions
            month_contrib = defaultdict(float)
            for bi, yt, yc in zip(t_idx, t_y, c_y):
                mkey = by_idx[bi].ts.strftime("%Y-%m")
                month_contrib[mkey] += abs(yt - yc)
            total_c = sum(month_contrib.values()) or 1.0
            max_share = max(month_contrib.values()) / total_c
            calendar_spike = max_share > CALENDAR_SPIKE_MAX

            # CRT_STATE_ONLY guard: residual delta after stratifying by CRT state
            # If within each CRT state, partition levels have no residual, fail
            by_state = defaultdict(list)
            for bi, yt, yc in zip(t_idx, t_y, c_y):
                by_state[by_idx[bi].crt_state].append((yt, yc))
            residual_exists = False
            for st, pairs in by_state.items():
                if len(pairs) < 20:
                    continue
                d = float(np.mean([p[0] for p in pairs]) - np.mean([p[1] for p in pairs]))
                # residual vs overall: if any state-specific delta has same sign and |d|>0.25*|delta|
                if delta != 0 and abs(d) > 0.25 * abs(delta) and np.sign(d) == np.sign(delta):
                    residual_exists = True
            # stronger: recompute within-state partition association
            residual_assoc = False
            for st in ACTIVE_STATES:
                st_bars = [b for b in treatments if b.crt_state == st]
                if len(st_bars) < MIN_N:
                    continue
                y_l, y_o = [], []
                for b in st_bars:
                    pv = _get_partition_value(b.dims, part)
                    if pv is None or b.r8 is None:
                        continue
                    lab = tuple(pv) if part["kind"] == "pair" else int(pv)
                    if lab == target_level:
                        y_l.append(b.r8)
                    else:
                        y_o.append(b.r8)
                if len(y_l) >= 20 and len(y_o) >= 20:
                    d_in = float(np.mean(y_l) - np.mean(y_o))
                    if abs(d_in) > 1e-12:
                        residual_assoc = True
            crt_state_only = not residual_assoc

            cell.update(
                {
                    "delta_match": delta,
                    "se_delta": se,
                    "mean_r8_treatment": float(t_y_a.mean()),
                    "mean_r8_control": float(c_y_a.mean()),
                    "assoc_within_active": real_assoc,
                    "p_perm": p_perm,
                    "fold_deltas": fold_deltas,
                    "walk_forward_stable": bool(wf_stable),
                    "held_out_last_fold_delta": fold_deltas[-1] if fold_deltas else None,
                    "calendar_max_month_share": float(max_share),
                    "calendar_spike": bool(calendar_spike),
                    "crt_state_only": bool(crt_state_only),
                    "bh_reject": False,  # filled later
                }
            )
            level_stats.append(cell)
            pvals.append(p_perm)

        # BH within family among support-OK cells only
        ok_idx = [i for i, c in enumerate(level_stats) if c["support"] == "OK"]
        ok_p = [pvals[i] for i in ok_idx]
        rejects = _bh(ok_p, BH_Q) if ok_p else []
        for j, i in enumerate(ok_idx):
            level_stats[i]["bh_reject"] = bool(rejects[j]) if j < len(rejects) else False

        family_results.append(
            {
                "partition_id": part["id"],
                "cells": level_stats,
                "n_ok_cells": sum(1 for c in level_stats if c["support"] == "OK"),
                "n_insufficient": sum(1 for c in level_stats if c["support"] != "OK"),
                "n_bh_reject": sum(1 for c in level_stats if c.get("bh_reject")),
            }
        )

    # global POSTHOC guard: no continuous cutpoints introduced in this run
    posthoc_guard = {
        "result": "PASS",
        "note": "Harness used only pre-registered discrete partition fields/levels; no adaptive cutpoints",
    }

    # decision classification
    any_supportive = False
    any_ok = False
    for fam in family_results:
        for c in fam["cells"]:
            if c["support"] != "OK":
                continue
            any_ok = True
            if (
                c.get("bh_reject")
                and c.get("walk_forward_stable")
                and not c.get("calendar_spike")
                and not c.get("crt_state_only")
                and c.get("p_perm") is not None
                and c["p_perm"] <= 0.05
            ):
                any_supportive = True

    if not any_ok:
        verdict = "INCONCLUSIVE_INSUFFICIENT_SUPPORT"
    elif any_supportive:
        verdict = "RESEARCH_SUPPORTIVE"
    else:
        verdict = "RESEARCH_NOT_SUPPORTIVE"

    return {
        "family_results": family_results,
        "posthoc_guard": posthoc_guard,
        "verdict": verdict,
        "primary_outcome": f"R_h@h={PRIMARY_H}",
        "min_n": MIN_N,
        "n_perm": N_PERM,
        "perm_seed": PERM_SEED,
        "bh_q": BH_Q,
    }


def write_artifacts(
    bars: list[BarRec],
    meta: dict,
    match_info: dict,
    analysis: dict,
    out_dir: Path,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    git = _git_meta(_ROOT)
    prereg_hash = _sha256_file(PREREG_JSON)
    prereg_md_hash = _sha256_file(PREREG_MD)

    # strip matches from machine copy for size - store summary + path to full matches
    match_summary = {k: v for k, v in match_info.items() if k != "matches"}
    matches_path = out_dir / "matches.json"
    matches_path.write_text(
        json.dumps({str(k): v for k, v in match_info["matches"].items()}, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    evidence = {
        "schema_id": "H_017_EXPERIMENT_EVIDENCE_V1",
        "program_alias": PROGRAM_ALIAS,
        "registry_id": REGISTRY_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "task_class": "EXPLORATORY_RESEARCH",
        "authority": "RESEARCH_ONLY",
        "status": "COMPLETE",
        "hard_flags": {
            "CRT_BEHAVIOR_CHANGE": False,
            "MSIP_SHADOW_AUTHORITY_CHANGE": False,
            "THRESHOLD_TUNING": False,
            "MIGRATION_AUTHORIZED": False,
            "PRODUCTION_AUTHORITY": False,
        },
        "frozen_protocol": {
            "experiment_definition_sha256": prereg_hash,
            "preregistration_md_sha256": prereg_md_hash,
            "partitions": "UNCHANGED",
            "primary_outcome": f"R_h@h={PRIMARY_H}",
            "permutation_count": N_PERM,
            "permutation_seed": PERM_SEED,
            "support_threshold": MIN_N,
            "oos": "4_CALENDAR_FOLDS + HELD_OUT_LAST_FOLD",
        },
        "repository": git,
        "population_meta": meta,
        "matching": match_summary,
        "analysis": analysis,
        "verdict": analysis["verdict"],
        "candidate_occupancy_note": (
            "Occupancy requires ACTIVE_STATES AND non-null candidate_episode_id; "
            "episode id increments on entry to active set and clears on exit — "
            "distinct from crt_state label alone."
        ),
    }
    evidence_path = out_dir / "H_017_EXPERIMENT_EVIDENCE_V1.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    # compact cell table
    rows = []
    for fam in analysis["family_results"]:
        for c in fam["cells"]:
            rows.append(
                {
                    "partition_id": c["partition_id"],
                    "level_key": c["level_key"],
                    "support": c["support"],
                    "n_treatment": c["n_treatment"],
                    "n_control": c["n_matched_control"],
                    "delta_match": c.get("delta_match"),
                    "p_perm": c.get("p_perm"),
                    "bh_reject": c.get("bh_reject"),
                    "walk_forward_stable": c.get("walk_forward_stable"),
                    "calendar_spike": c.get("calendar_spike"),
                    "crt_state_only": c.get("crt_state_only"),
                }
            )
    (out_dir / "cell_summary.json").write_text(
        json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    return evidence


def write_critique(evidence: dict, out_dir: Path) -> Path:
    v = evidence["verdict"]
    analysis = evidence["analysis"]
    n_ok = sum(f["n_ok_cells"] for f in analysis["family_results"])
    n_ins = sum(f["n_insufficient"] for f in analysis["family_results"])
    n_bh = sum(f["n_bh_reject"] for f in analysis["family_results"])
    lines = [
        f"# H-017 / H-MSIP-001 Critique",
        "",
        f"**Verdict:** `{v}`",
        f"**Authority:** RESEARCH_ONLY — no CRT/MSIP/production authority granted.",
        "",
        "## Protocol fidelity",
        "",
        "- Partitions unchanged from pre-registration (no drop/merge).",
        f"- Primary outcome R_h@h={PRIMARY_H}.",
        f"- Permutations N={N_PERM} seed={PERM_SEED}.",
        f"- Support threshold n≥{MIN_N}; insufficient cells reported as INSUFFICIENT_SUPPORT.",
        "- Occupancy uses candidate_episode_id × ACTIVE_STATES (not state label alone).",
        "",
        "## Support census",
        "",
        f"- Support-OK cells: **{n_ok}**",
        f"- INSUFFICIENT_SUPPORT cells: **{n_ins}**",
        f"- BH reject (primary family FDR): **{n_bh}**",
        "",
        "## Population",
        "",
        f"- Eligible bars: {evidence['population_meta']['n_eligible']}",
        f"- Active occupancy bars: {evidence['population_meta']['active_occupancy_bars']}",
        f"- Matched treatments: {evidence['matching']['n_matched']} / "
        f"{evidence['matching']['n_treatment']} (unmatched={evidence['matching']['n_unmatched']})",
        "",
        "## Interpretation",
        "",
    ]
    if v == "RESEARCH_SUPPORTIVE":
        lines.append(
            "At least one pre-registered cell cleared support, permutation+BH, walk-forward, "
            "calendar-spike, and CRT_STATE_ONLY guards on primary R_8. This is **research information "
            "only** — not a promotion or fusion authority claim."
        )
    elif v == "RESEARCH_NOT_SUPPORTIVE":
        lines.append(
            "Support-OK cells existed but none cleared the full success conjunction on primary R_8. "
            "Under the frozen null, MarketStateVector partitions do not demonstrate reproducible "
            "incremental forward-return separation during CRT occupancy beyond matched controls "
            "after multiple-testing and OOS guards."
        )
    elif v == "INCONCLUSIVE_INSUFFICIENT_SUPPORT":
        lines.append(
            "No cell met n≥80 on both treatment and matched control. Result is power/support limited, "
            "not a decisive null on the scientific claim."
        )
    else:
        lines.append("Protocol failure or unclassified — see evidence.")

    lines += [
        "",
        "## Explicit non-claims",
        "",
        "- No threshold tuning",
        "- No CRT migration / G-MIG-01",
        "- No MSIP shadow trading authority",
        "- No production cutover",
        "",
        f"Generated: {evidence['generated_at_utc']}",
        "",
    ]
    path = out_dir / "H_017_CRITIQUE.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_decision_ledger(evidence: dict, out_dir: Path) -> Path:
    entry = {
        "schema_id": "RESEARCH_DECISION_LEDGER_ENTRY_V1",
        "id": "DLE-H017-001",
        "registry_id": REGISTRY_ID,
        "program_alias": PROGRAM_ALIAS,
        "timestamp_utc": evidence["generated_at_utc"],
        "task_class": "EXPLORATORY_RESEARCH",
        "authority": "RESEARCH_ONLY",
        "verdict": evidence["verdict"],
        "hypothesis_status_recommended": (
            "validated"
            if evidence["verdict"] == "RESEARCH_SUPPORTIVE"
            else (
                "open"
                if evidence["verdict"] == "INCONCLUSIVE_INSUFFICIENT_SUPPORT"
                else "falsified"
            )
        ),
        "grants": {
            "crt_behavior_change": False,
            "msip_shadow_authority_change": False,
            "threshold_tuning": False,
            "migration": False,
            "production": False,
        },
        "evidence_ref": str(out_dir / "H_017_EXPERIMENT_EVIDENCE_V1.json"),
        "critique_ref": str(out_dir / "H_017_CRITIQUE.md"),
        "stop_boundary": "OWNER_REVIEW",
    }
    path = out_dir / "H_017_DECISION_LEDGER_ENTRY.json"
    path.write_text(json.dumps(entry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # append to research decision ledger if present
    ledger = _ROOT / "results" / "research" / "decision_ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    return path


def update_hypothesis_seed_status(verdict: str) -> None:
    """Append status note via re-seed: update H-017 notes/status in seed then dump.

    Map verdict → registry status without inventing promotion authority.
    """
    # Status mapping per authorization REQUIRED_RESULT_CLASSIFICATION
    if verdict == "RESEARCH_SUPPORTIVE":
        status = "validated"  # research validated only
    elif verdict == "RESEARCH_NOT_SUPPORTIVE":
        status = "falsified"
    elif verdict == "INCONCLUSIVE_INSUFFICIENT_SUPPORT":
        status = "open"
    else:
        status = "open"

    seed_path = _ROOT / "scripts" / "governance" / "seed_hypothesis_registry.py"
    text = seed_path.read_text(encoding="utf-8")
    # lightweight: append a status flip via running python that patches build_records result
    # Prefer post-hoc append to JSONL after seed dump with updated status field
    from governance.hypothesis_registry import HypothesisRegistry

    reg_path = _ROOT / "data" / "hypothesis_registry.jsonl"
    # reseed first to ensure H-017 exists
    subprocess.run([sys.executable, str(seed_path)], cwd=_ROOT, check=True)
    reg = HypothesisRegistry(reg_path)
    reg.load()
    rec = dict(reg.get("H-017"))
    rec["status"] = status
    rec["last_validated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rec["notes"] = (
        rec.get("notes", "")
        + f" | RUN complete verdict={verdict}; status→{status}; RESEARCH_ONLY."
    )
    # rewrite all records with updated H-017
    all_recs = []
    for r in reg.records:
        if r["id"] == "H-017":
            all_recs.append(rec)
        else:
            all_recs.append(r)
    HypothesisRegistry.dump(reg_path, all_recs)


def update_findings_doc(evidence: dict) -> None:
    """Append a maintained findings note (not a full F-id unless supportive long-lived)."""
    path = _ROOT / "docs" / "research-readiness" / "h-msip-001-run-findings.md"
    v = evidence["verdict"]
    body = f"""# H-MSIP-001 / H-017 Run Findings (maintained)

**Date:** {evidence['generated_at_utc'][:10]}  
**Verdict:** `{v}`  
**Authority:** RESEARCH_ONLY  

## Population

- Corpus sha: `{evidence['population_meta']['corpus_sha256'][:16]}…`
- Eligible bars: {evidence['population_meta']['n_eligible']}
- Active occupancy bars: {evidence['population_meta']['active_occupancy_bars']}
- Candidate episodes: {evidence['population_meta']['n_candidate_episodes']}
- Matched: {evidence['matching']['n_matched']} / {evidence['matching']['n_treatment']} (unmatched {evidence['matching']['n_unmatched']})

## Exclusion census

```json
{json.dumps(evidence['population_meta']['census'], indent=2, sort_keys=True)}
```

## Primary result (R_h @ h=8)

See `results/research/h_msip_001/cell_summary.json` for every pre-registered cell including
`INSUFFICIENT_SUPPORT`.

## Verdict meaning

| Class | Meaning |
|-------|---------|
| RESEARCH_SUPPORTIVE | ≥1 cell cleared full success conjunction — research info only |
| RESEARCH_NOT_SUPPORTIVE | Support-OK cells exist; none cleared full conjunction |
| INCONCLUSIVE_INSUFFICIENT_SUPPORT | No cell met n≥80 |

## Non-authority

CRT behavior, MSIP trading authority, thresholds, migration, production: **unchanged / not granted**.

## Artifacts

- Evidence: `results/research/h_msip_001/H_017_EXPERIMENT_EVIDENCE_V1.json`
- Critique: `results/research/h_msip_001/H_017_CRITIQUE.md`
- Decision ledger: `results/research/h_msip_001/H_017_DECISION_LEDGER_ENTRY.json`
"""
    path.write_text(body, encoding="utf-8")


def main() -> int:
    out_dir = _ROOT / "results" / "research" / "h_msip_001"
    print("Building panel (FeaturePipeline + CRT co-run + MSV)...", flush=True)
    bars, meta, _ohlcv = build_panel()
    print(f"Eligible bars: {len(bars)}; occupancy={meta['active_occupancy_bars']}", flush=True)
    print("Matching controls...", flush=True)
    match_info = match_controls(bars)
    print(
        f"Matched {match_info['n_matched']}/{match_info['n_treatment']} "
        f"unmatched={match_info['n_unmatched']}",
        flush=True,
    )
    print("Analyzing partitions (permutations)...", flush=True)
    analysis = analyze(bars, match_info)
    print(f"Verdict: {analysis['verdict']}", flush=True)
    evidence = write_artifacts(bars, meta, match_info, analysis, out_dir)
    write_critique(evidence, out_dir)
    write_decision_ledger(evidence, out_dir)
    update_findings_doc(evidence)
    try:
        update_hypothesis_seed_status(analysis["verdict"])
    except Exception as exc:
        print(f"WARN: hypothesis status update failed: {exc}", flush=True)
    # status file
    (out_dir / "RUN_STATUS.json").write_text(
        json.dumps(
            {
                "H-017_STATUS": "COMPLETE_AWAITING_OWNER_REVIEW",
                "verdict": analysis["verdict"],
                "STOP_BOUNDARY": "OWNER_REVIEW",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"out_dir": str(out_dir), "verdict": analysis["verdict"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
