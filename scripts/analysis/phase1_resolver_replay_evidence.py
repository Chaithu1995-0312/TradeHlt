#!/usr/bin/env python
"""phase1_resolver_replay_evidence.py — frozen Phase-1 four-arm replay.

STANDING CONTRACT (do not deviate)
----------------------------------
Unit=ENTRY · Corpus=Phase-1 · Horizon=H20 · Cost=SEM-015 TIMEOUT
Control=Always-Long (stride H20)

Four directional sources (separate event generators, not parent/child):
  1. Engine-Atlas       = EXP entry + atlas direction
                            (mostly DISP→EXP; 6 SHADOW_EXPANSION_CONFIRMED)
  2. Resolver-Memory    = SHADOW→EXP + pending_displacement_dir
                            (strict_memory; skip trend_bias-filled dir)
  3. Resolver-TrendBias = SHADOW→EXP + trend_bias sign
  4. Always-Long        = stride H20 on the same close_at_horizon / SEM-015 path

coverage = n_entries / eligible corpus
  NEVER Resolver-n / Engine-n  (Resolver EXP ⊄ Engine EXP)

Every arm prints: n | coverage | expectancy | PF | win rate
No PF without n. Interpret with Cases A–D only (Memory/TrendBias vs Always-Long).
Engine is a fourth directional source on the scoreboard, not a Case letter.
No economic promotion.

METHOD
------
Resolver arms replay CRTStateResolver.resolve() over the dual-construction
LIVE feature vectors (injection=none), snapshotting pending_displacement_dir
at SHADOW→EXP BEFORE _update_memory clears it. Engine arm reads the decision
atlas EXP entries. Always-Long strides the same CSV.

The prior engine-StateMachine SHADOW_EXPANSION_CONFIRMED capture (n=6) is a
DIFFERENT object; kept behind --legacy-engine-shadow-bt for sample_acquisition.

FORBIDDEN (this script does none of these)
------------------------------------------
Flip continuous_disp_to_expansion · wire CHoCH · reopen occupancy · optimize parity ·
reclassify April off-session rejects · TV forensic as occupancy adjudicator ·
promote economic findings · UI / L-003 ontology reopen.

USAGE
-----
  $env:PYTHONPATH='D:\\Tradelatest'
  .\\venv\\Scripts\\python.exe scripts\\analysis\\phase1_resolver_replay_evidence.py

Artifacts
---------
  results/analysis/phase1_resolver_replay/<run_id>/
  results/analysis/phase1_resolver_replay/scoreboard.LATEST.json
  docs/research/phase1_resolver_replay_evidence_note.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics as st
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
for _p in (str(_ROOT), str(_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config_layer.crt_engine_v2 import Direction, StateMachine  # noqa: E402
from config_layer.production_config import (  # noqa: E402
    PROD_VERSION,
    load_prod_config_from_registry,
)
from features.crt_state_resolver import CRTStateResolver  # noqa: E402
from research.costs import ComponentCostModel, UnmeasuredCostError  # noqa: E402
from runtime.backtest_v2 import (  # noqa: E402
    BacktestConfig,
    BacktestRunner,
    CandleLoader,
    MultiInstrumentRunner,
)

# Shared probe helpers (extracted; pre-edit copy in archive/probes_extraction_phase1_2026-09-14/)
from research.probes.corpus import load_corpus  # noqa: E402
from research.probes.costs_path import net_r as _net_r_shared  # noqa: E402
from research.probes.governance import assert_no_claim_keys  # noqa: E402
from research.probes.horizon import close_at_horizon  # noqa: E402
from research.probes.scoreboard import profit_factor as _profit_factor_shared  # noqa: E402
from research.probes.scoreboard import scoreboard_row as _scoreboard_row_shared  # noqa: E402

HORIZON = 20
STRIDE = 20
PF_CAP = 9999.0
MIN_N_LABEL = 30

_DEFAULT_CSV = _ROOT / "data" / "mt5" / "XAUUSD_M15.csv"
_DEFAULT_BAR_MATRIX = _ROOT / "results" / "research" / "bar_matrix" / "XAUUSD_M15" / "bar_matrix.parquet"
_DEFAULT_RUN_DIR = _ROOT / "logs" / "dual_construction_full_gapfix"
_DEFAULT_ATLAS = _ROOT / "results" / "decision_atlas_full"
_MANIFEST = (
    _ROOT / "results" / "research" / "xauusd_mt5_cost_calibration"
    / "xauusd_mt5_cost_calibration_manifest_LATEST.json"
)
_OUT_DIR = _ROOT / "results" / "analysis" / "phase1_resolver_replay"
_NOTE_PATH = _ROOT / "docs" / "research" / "phase1_resolver_replay_evidence_note.md"

_FEAT_PREFIX = "resolver.feature_vector."
_FEAT_SKIP = frozenset({"__null__"})

# Frozen Cases A–D rubric (interpretive only; not a promotion gate).
CASES_RUBRIC = {
    "A": (
        "Memory expectancy > Always-Long AND TrendBias expectancy <= Always-Long "
        "→ pending_displacement_dir carries directional information beyond drift on this object; "
        "trend_bias does not."
    ),
    "B": (
        "TrendBias expectancy > Always-Long AND Memory expectancy <= Always-Long "
        "→ trend_bias carries the signal on this object; memory direction is not load-bearing."
    ),
    "C": (
        "Both Memory and TrendBias expectancy > Always-Long "
        "→ both arms informative vs drift on this object (agreement is diagnostic only, not an objective)."
    ),
    "D": (
        "Neither Memory nor TrendBias expectancy > Always-Long "
        "→ null on this ENTRY/H20/SEM-015 TIMEOUT object; no Case promotes."
    ),
}


class _Capture:
    collapses: list = []
    replayed_states: list = []
    creates: list = []
    open_create: dict | None = None
    shadow_entries_without_open_create: int = 0


def _close_open_create(outcome: str, *, extra: dict | None = None) -> None:
    rec = _Capture.open_create
    if rec is None:
        return
    rec["outcome"] = outcome
    if extra:
        rec.update(extra)
    _Capture.creates.append(rec)
    _Capture.open_create = None


from research.provenance import sha256_file as _sha256_file  # noqa: E402 — research-framework Phase 1 dedup


def _git_provenance() -> dict:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(_ROOT), text=True
        ).strip()
    except Exception:
        sha = None
    try:
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=str(_ROOT), text=True
            ).strip()
        )
    except Exception:
        dirty = None
    return {"git_sha": sha, "tree_dirty": dirty}


def _dir_to_long_short(d: Any) -> Optional[str]:
    if d is None:
        return None
    name = d.name if hasattr(d, "name") else str(d)
    name = name.upper()
    if name in ("LONG", "1", "+1"):
        return "LONG"
    if name in ("SHORT", "-1"):
        return "SHORT"
    return None


def _tb_to_long_short(tb: Any) -> Optional[str]:
    try:
        v = float(tb)
    except (TypeError, ValueError):
        return None
    if math.isnan(v):
        return None
    if v > 0:
        return "LONG"
    if v < 0:
        return "SHORT"
    return None


def _install_collapse_capture():
    """Capture pending_displacement_dir at ENGINE SHADOW→EXP collapse.

    Kept for sample_acquisition.py. This is NOT the frozen four-arm resolver object.
    """
    orig = StateMachine.try_shadow_pending_to_expansion

    def patched(self, state, candle, ev_logger=None):
        pending_dir = state.pending_displacement_dir
        pending_formed = state.pending_displacement_formed_idx
        pending_src = state.pending_displacement_source_htf
        atr_abs = getattr(state, "atr_abs", None)
        ok = orig(self, state, candle, ev_logger)
        if ok:
            _Capture.collapses.append(
                {
                    "candle_index": int(candle.index),
                    "timestamp": str(getattr(candle, "timestamp", "")),
                    "pending_displacement_dir": (
                        pending_dir.name if pending_dir is not None else "NONE"
                    ),
                    "pending_displacement_formed_idx": pending_formed,
                    "pending_displacement_source_htf": pending_src or None,
                    "atr_abs": float(atr_abs) if atr_abs else None,
                    "action": "SHADOW_EXPANSION_CONFIRMED",
                }
            )
        return ok

    StateMachine.try_shadow_pending_to_expansion = patched

    def restore():
        StateMachine.try_shadow_pending_to_expansion = orig

    return restore


def _install_resolver_memory_capture():
    """Snapshot pending_displacement_dir at resolver SHADOW→EXP, before memory clear.

    Also records resolver CREATE (HTF reset while DISPLACEMENT) and its
    occupancy outcomes. Additive; four-arm H20 does not consume creates.
    """
    orig_update = CRTStateResolver._update_memory
    orig_force = CRTStateResolver._force_range_reset
    orig_tick = CRTStateResolver._tick_shadow_ttl

    def patched_force(self, reason, *, kind):
        prev = self._memory.current_state
        pending_was = bool(self._memory.pending_displacement_active)
        is_create = (
            kind == "htf"
            and prev == "DISPLACEMENT"
            and bool(self._lifecycle.get("shadow_on_htf_displacement_reset"))
        )
        if is_create:
            self._pending_dir_source = getattr(self, "_disp_dir_source", None)
            if _Capture.open_create is not None:
                _close_open_create("OVERWRITTEN_BY_NEW_MEMORY")
        elif kind in ("gap", "forced") and pending_was:
            _close_open_create("CLEARED_NON_HTF_RESET", extra={"clear_kind": kind})
        result = orig_force(self, reason, kind=kind)
        if is_create:
            bar = getattr(self, "_current_bar", {}) or {}
            d = self._memory.pending_displacement_dir
            _Capture.open_create = {
                "memory_id": len(_Capture.creates) + 1,
                "bar_index": bar.get("bar_index"),
                "candle_index": int(self._memory.candle_index),
                "timestamp": str(bar.get("timestamp") or ""),
                "reason": str(reason or ""),
                "kind": kind,
                "prev_state": prev,
                "formed_idx": int(self._memory.pending_displacement_formed_idx),
                "created_idx": int(self._memory.pending_displacement_created_idx),
                "pending_dir": d,
                "ttl_initial": int(self._memory.pending_displacement_ttl),
                "reached_shadow_pending": False,
                "outcome": "OPEN",
            }
        return result

    def patched_tick(self):
        was = bool(self._memory.pending_displacement_active)
        orig_tick(self)
        if was and not self._memory.pending_displacement_active:
            bar = getattr(self, "_current_bar", {}) or {}
            _close_open_create(
                "EXPIRED_TTL",
                extra={
                    "closed_bar_index": bar.get("bar_index"),
                    "closed_candle_index": int(self._memory.candle_index),
                },
            )

    def patched_update(self, resolved, features, timestamp=None):
        prev = self._memory.current_state
        entered = prev != resolved
        if resolved == "SHADOW_PENDING" and entered:
            if _Capture.open_create is None:
                _Capture.shadow_entries_without_open_create += 1
            else:
                _Capture.open_create["reached_shadow_pending"] = True
        if resolved == "EXPANSION" and entered and prev == "SHADOW_PENDING":
            bar = getattr(self, "_current_bar", {}) or {}
            _Capture.collapses.append(
                {
                    "bar_index": bar.get("bar_index"),
                    "candle_index": int(self._memory.candle_index),
                    "timestamp": str(bar.get("timestamp") or timestamp or ""),
                    "pending_displacement_dir": self._memory.pending_displacement_dir,
                    "pending_dir_source": getattr(self, "_pending_dir_source", None),
                    "pending_displacement_formed_idx": (
                        self._memory.pending_displacement_formed_idx
                    ),
                    "pending_displacement_active": bool(
                        self._memory.pending_displacement_active
                    ),
                    "live_atr": bar.get("live_atr"),
                    "trend_bias": bar.get("trend_bias"),
                    "htf_id": bar.get("htf_id"),
                    "action": "RESOLVER_SHADOW_EXP",
                }
            )
            _close_open_create(
                "SHADOW_PENDING_TO_EXPANSION",
                extra={
                    "closed_bar_index": bar.get("bar_index"),
                    "closed_candle_index": int(self._memory.candle_index),
                },
            )
        if resolved == "RANGE" and entered and prev == "SHADOW_PENDING":
            bar = getattr(self, "_current_bar", {}) or {}
            _close_open_create(
                "SHADOW_PENDING_TO_RANGE",
                extra={
                    "closed_bar_index": bar.get("bar_index"),
                    "closed_candle_index": int(self._memory.candle_index),
                },
            )
        result = orig_update(self, resolved, features, timestamp)
        if resolved == "SWEEP" and entered:
            if self._memory.displacement_direction != 0:
                self._disp_dir_source = "sweep_geometry"
        if resolved == "DISPLACEMENT" and entered:
            o = features.get("open")
            c = features.get("close")
            try:
                of = float(o) if o is not None else None
                cf = float(c) if c is not None else None
            except (TypeError, ValueError):
                of = cf = None
            if of is not None and cf is not None and cf != of:
                self._disp_dir_source = "body"
            elif of is not None and cf is not None and cf == of:
                if getattr(self, "_disp_dir_source", None) != "sweep_geometry":
                    tb = features.get("trend_bias", 0.0) or 0.0
                    try:
                        tbv = float(tb)
                    except (TypeError, ValueError):
                        tbv = 0.0
                    if tbv != 0.0 and self._memory.displacement_direction != 0:
                        self._disp_dir_source = "trend_bias_fill"
        return result

    CRTStateResolver._update_memory = patched_update
    CRTStateResolver._force_range_reset = patched_force
    CRTStateResolver._tick_shadow_ttl = patched_tick

    def restore():
        CRTStateResolver._update_memory = orig_update
        CRTStateResolver._force_range_reset = orig_force
        CRTStateResolver._tick_shadow_ttl = orig_tick

    return restore


def _load_trend_bias_by_ts(bar_matrix_path: Path):
    import pyarrow.parquet as pq

    if not bar_matrix_path.is_file():
        raise FileNotFoundError(
            f"Phase-1 trend_bias source missing: {bar_matrix_path} "
            "(required for Resolver-TrendBias; do not invent substitutes)"
        )
    table = pq.read_table(bar_matrix_path, columns=["timestamp", "trend_bias", "atr_abs"])
    out: dict[str, float] = {}
    atr_by_ts: dict[str, float] = {}
    for row in table.to_pylist():
        ts = row["timestamp"]
        if hasattr(ts, "strftime"):
            key = ts.strftime("%Y-%m-%d %H:%M:%S")
        else:
            key = str(ts).replace("T", " ").split(".")[0]
        out[key] = float(row["trend_bias"]) if row["trend_bias"] is not None else 0.0
        if row.get("atr_abs"):
            atr_by_ts[key] = float(row["atr_abs"])
    return out, atr_by_ts


def _normalize_ts(ts: str) -> str:
    s = str(ts).replace("T", " ").strip()
    if "." in s:
        s = s.split(".")[0]
    if "+" in s:
        s = s.split("+")[0].strip()
    if s.endswith("Z"):
        s = s[:-1].strip()
    return s


def _parse_ts(ts: Any):
    if ts is None:
        return None
    if hasattr(ts, "to_pydatetime"):
        try:
            return ts.to_pydatetime()
        except Exception:
            pass
    if isinstance(ts, datetime):
        return ts
    s = _normalize_ts(ts)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return ts


def _is_missing(v: Any) -> bool:
    if v is None:
        return True
    try:
        if isinstance(v, float) and math.isnan(v):
            return True
    except (TypeError, ValueError):
        pass
    try:
        import pandas as pd

        if pd.isna(v):
            return True
    except Exception:
        pass
    return False


def _profit_factor(xs: list[float]) -> float:
    return _profit_factor_shared(xs, pf_cap=PF_CAP)




def _scoreboard_row(
    name: str,
    net_rs: list[float],
    *,
    n_universe: int,
    n_eligible: int,
) -> dict:
    return _scoreboard_row_shared(
        name,
        net_rs,
        n_universe=n_universe,
        n_eligible=n_eligible,
        min_n_label=MIN_N_LABEL,
        pf_cap=PF_CAP,
    )




def _net_r(
    corpus: list[dict],
    bar_index: int,
    direction: str,
    atr: float,
    cost_model: ComponentCostModel,
) -> Optional[float]:
    return _net_r_shared(corpus, bar_index, direction, atr, cost_model, HORIZON)




def _call_case(mem: dict, tb: dict, al: dict) -> dict:
    """Cases A–D on expectancy only (standing contract). None expectancy → treat as not > control."""
    e_m = mem.get("expectancy")
    e_t = tb.get("expectancy")
    e_c = al.get("expectancy")
    if e_c is None:
        return {
            "case": "D",
            "reason": "Always-Long expectancy unavailable; cannot adjudicate A–C → Case D by null-control rule.",
            "rubric": CASES_RUBRIC["D"],
        }
    mem_beats = e_m is not None and e_m > e_c
    tb_beats = e_t is not None and e_t > e_c
    if mem_beats and not tb_beats:
        case = "A"
    elif tb_beats and not mem_beats:
        case = "B"
    elif mem_beats and tb_beats:
        case = "C"
    else:
        case = "D"
    return {
        "case": case,
        "memory_expectancy": e_m,
        "trendbias_expectancy": e_t,
        "always_long_expectancy": e_c,
        "memory_beats_control": mem_beats,
        "trendbias_beats_control": tb_beats,
        "rubric": CASES_RUBRIC[case],
        "note": (
            "Case call is interpretive only on this frozen object. "
            "economic_claims_allowed=false. No promotion. "
            "Engine-Atlas is a fourth directional source on the scoreboard, not a Case letter."
        ),
    }


def run_shadow_collapse_replay(csv_path: Path, instrument: str, output_dir: Path) -> list[dict]:
    """ENGINE StateMachine SHADOW→EXP capture. Different object from resolver SHADOW→EXP."""
    _Capture.collapses = []
    restore = _install_collapse_capture()
    try:
        crt_cfg = load_prod_config_from_registry(PROD_VERSION, instrument)
        cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
        cfg.instrument = instrument
        cfg.pip_size = MultiInstrumentRunner.INSTRUMENT_PIP.get(instrument, 0.0001)
        loader = CandleLoader(str(csv_path), instrument)
        runner = BacktestRunner(
            cfg,
            csv_path=str(csv_path),
            overrides={"diagnostic": "phase1_resolver_replay_evidence"},
        )
        runner.run(loader.stream(), loader.count(), str(output_dir / "bt_run"))
    finally:
        restore()
    return list(_Capture.collapses)


def _feat_dict_from_row(row: dict) -> Optional[dict]:
    feat: dict[str, Any] = {}
    n_present = 0
    for k, v in row.items():
        if not k.startswith(_FEAT_PREFIX):
            continue
        name = k[len(_FEAT_PREFIX):]
        if name in _FEAT_SKIP:
            continue
        if _is_missing(v):
            continue
        try:
            feat[name] = float(v)
        except (TypeError, ValueError):
            feat[name] = v
        n_present += 1
    if n_present == 0 or "open" not in feat:
        return None
    return feat


def _load_live_rows(run_dir: Path) -> tuple[list[dict], dict]:
    from utils.duckdb_query import open_views

    cglob = str((run_dir / "XAUUSD_crt_construction.parquet").resolve()).replace("\\", "/")
    bglob = str((run_dir / "XAUUSD_bar_structure.parquet").resolve()).replace("\\", "/")
    cglob = cglob.rstrip("/") + "/**/*.parquet"
    bglob = bglob.rstrip("/") + "/**/*.parquet"
    con = open_views({"crt": cglob, "bar": bglob})
    identity = con.execute(
        "select run_id, config_version, config_hash, ontology_source, corpus_sha256, "
        "count(*) n, count(*) filter (phase = 'LIVE') live "
        "from crt group by 1,2,3,4,5"
    ).fetchdf()
    if identity.empty:
        raise RuntimeError(f"no construction rows in {run_dir}")
    ident = identity.iloc[0].to_dict()
    expected = con.execute(
        """
        with s as (
          select bar_index, ontology_state,
                 lag(ontology_state) over (order by bar_index) as prev
          from crt where phase = 'LIVE'
        )
        select prev, count(*) n
        from s
        where ontology_state = 'EXPANSION' and prev is distinct from ontology_state
        group by 1
        """
    ).fetchdf()
    expected_n = int(expected["n"].sum()) if not expected.empty else 0
    expected_from_shadow = 0
    for rec in expected.to_dict("records"):
        if rec["prev"] == "SHADOW_PENDING":
            expected_from_shadow = int(rec["n"])
    ident["expected_resolver_exp_entries"] = expected_n
    ident["expected_resolver_shadow_exp"] = expected_from_shadow
    df = con.execute(
        """
        SELECT c.*, b.htf_candle_id
        FROM crt c
        LEFT JOIN bar b ON c.bar_index = b.bar_index
        WHERE c.phase = 'LIVE'
        ORDER BY c.bar_index
        """
    ).fetchdf()
    rows = df.to_dict("records")
    con.close()
    return rows, ident


def run_resolver_memory_replay(run_dir: Path) -> tuple[list[dict], dict]:
    """Replay CRTStateResolver over dual-construction LIVE vectors (injection=none)."""
    rows, ident = _load_live_rows(run_dir)
    ontology_source = ident.get("ontology_source") or "configs/formulas/market_crt_states.yaml"
    cfg_path = Path(str(ontology_source))
    if not cfg_path.is_absolute():
        cfg_path = _ROOT / cfg_path

    _Capture.collapses = []
    _Capture.replayed_states = []
    _Capture.creates = []
    _Capture.open_create = None
    _Capture.shadow_entries_without_open_create = 0
    restore = _install_resolver_memory_capture()
    n_mismatch = 0
    n_no_feat = 0
    n_err = 0
    first_mismatch = None
    try:
        resolver = CRTStateResolver(config_path=cfg_path)
        resolver.reset_memory()
        resolver.reset_counts()
        for row in rows:
            feat = _feat_dict_from_row(row)
            parquet_state = row.get("ontology_state")
            if feat is None:
                n_no_feat += 1
                _Capture.replayed_states.append(None)
                if parquet_state not in (None,):
                    n_mismatch += 1
                    if first_mismatch is None:
                        first_mismatch = {
                            "bar_index": int(row["bar_index"]),
                            "parquet": parquet_state,
                            "replayed": None,
                            "reason": "NO_FEATURES",
                        }
                continue
            resolver._current_bar = {
                "bar_index": int(row["bar_index"]),
                "timestamp": row.get("timestamp"),
                "live_atr": row.get("engine.live_context.live_atr"),
                "trend_bias": feat.get("trend_bias"),
                "htf_id": row.get("htf_candle_id"),
            }
            ts = _parse_ts(row.get("timestamp"))
            htf_id = row.get("htf_candle_id")
            if _is_missing(htf_id):
                htf_id = None
            else:
                htf_id = str(htf_id)
            try:
                state = resolver.resolve(feat, timestamp=ts, htf_id=htf_id)
            except Exception as exc:  # noqa: BLE001 — observation replay; record, do not invent
                n_err += 1
                state = None
                if first_mismatch is None:
                    first_mismatch = {
                        "bar_index": int(row["bar_index"]),
                        "parquet": parquet_state,
                        "replayed": None,
                        "reason": f"RESOLVER_ERROR:{type(exc).__name__}: {exc}",
                    }
            _Capture.replayed_states.append(state)
            if state != parquet_state:
                n_mismatch += 1
                if first_mismatch is None:
                    first_mismatch = {
                        "bar_index": int(row["bar_index"]),
                        "parquet": parquet_state,
                        "replayed": state,
                    }
    finally:
        restore()

    collapses = list(_Capture.collapses)
    ident["n_live_rows"] = len(rows)
    ident["n_no_features"] = n_no_feat
    ident["n_resolver_errors"] = n_err
    ident["n_state_mismatch"] = n_mismatch
    ident["first_mismatch"] = first_mismatch
    ident["n_captured_shadow_exp"] = len(collapses)
    ident["ontology_source_resolved"] = str(cfg_path)
    if _Capture.open_create is not None:
        _close_open_create("UNRESOLVED_AT_EOF")
    ident["n_resolver_create"] = len(_Capture.creates)
    ident["n_shadow_entries_without_open_create"] = int(
        _Capture.shadow_entries_without_open_create
    )
    return collapses, ident


def _engine_atlas_entries(atlas_dir: Path) -> list[dict]:
    import pyarrow.parquet as pq

    dec_path = atlas_dir / "transition_decision.parquet"
    env_path = atlas_dir / "envelope_bar.parquet"
    if not dec_path.is_file():
        raise FileNotFoundError(f"atlas missing {dec_path}")
    dec = pq.read_table(dec_path).to_pylist()
    atr_by_bar = {}
    if env_path.is_file():
        atr_by_bar = {
            b["bar_index"]: b["live_atr"]
            for b in pq.read_table(env_path).to_pylist()
            if b.get("live_atr")
        }
    out = []
    for d in dec:
        if d.get("to_state") != "EXPANSION":
            continue
        if d.get("is_self_transition"):
            continue
        direction = d.get("direction")
        if direction not in ("LONG", "SHORT"):
            continue
        out.append(
            {
                "bar_index": int(d["bar_index"]),
                "direction": direction,
                "from_state": d.get("from_state"),
                "live_atr": atr_by_bar.get(d["bar_index"]),
                "episode_id": d.get("episode_id"),
            }
        )
    return out


def _score_entries(
    entries: list[dict],
    *,
    direction_key: str,
    atr_key: str,
    corpus: list[dict],
    cost_model: ComponentCostModel,
    skip_key: str,
) -> tuple[list[float], int]:
    nets: list[float] = []
    n_eligible = 0
    for ep in entries:
        d = ep.get(direction_key)
        if d not in ("LONG", "SHORT"):
            ep[skip_key] = "no_direction"
            continue
        n_eligible += 1
        atr = ep.get(atr_key)
        if not atr or float(atr) <= 0:
            ep[skip_key] = "no_atr"
            continue
        net = _net_r(corpus, int(ep["bar_index"]), d, float(atr), cost_model)
        if net is None:
            ep[skip_key] = "horizon_truncated"
            continue
        ep[skip_key] = None
        ep["net_R"] = net
        nets.append(net)
    return nets, n_eligible


def _render_md(artifact: dict) -> str:
    sb = artifact["scoreboard"]
    cc = artifact["case_call"]
    arm_order = (
        "Engine-Atlas",
        "Resolver-Memory",
        "Resolver-TrendBias",
        "Always-Long",
    )
    lines = [
        "# Phase-1 four-arm resolver replay evidence note",
        "",
        f"**run_id:** `{artifact['run_id']}`",
        "",
        "**Claim class:** DESCRIPTIVE_ONLY · `economic_claims_allowed: false` · authority: none",
        "",
        "Frozen standing contract: Unit=ENTRY · Corpus=Phase-1 · Horizon=H20 · Cost=SEM-015 TIMEOUT · "
        "Control=Always-Long (stride H20).",
        "",
        "Arms (separate event generators; Resolver EXP ⊄ Engine EXP):",
        "- **Engine-Atlas** — EXP entry + atlas direction (mostly DISP→EXP)",
        "- **Resolver-Memory** — SHADOW→EXP + `pending_displacement_dir` (strict_memory; skip trend_bias fill)",
        "- **Resolver-TrendBias** — SHADOW→EXP + `trend_bias` sign",
        "- **Always-Long** — stride H20 on the same `close_at_horizon` / SEM-015 TIMEOUT path",
        "",
        "coverage = n_entries / eligible corpus. Never Resolver-n / Engine-n.",
        "Every arm prints n | coverage | expectancy | PF | win rate, including ugly / n<30 cells.",
        "",
        f"**source_run_id (dual-construction parquet):** `{artifact['provenance'].get('source_run_id')}`",
        "",
        "## Scoreboard",
        "",
        "| Arm | n | coverage % | expectancy | PF | win rate | power |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for key in arm_order:
        r = sb[key]
        e = f"{r['expectancy']:+.6f}" if r["expectancy"] is not None else "n/a"
        pf = f"{r['PF']:.4f}" if r["PF"] is not None else "n/a"
        wr = f"{r['win_rate']:.4f}" if r["win_rate"] is not None else "n/a"
        lines.append(
            f"| {key} | {r['n']} | {r['coverage_pct']:.4f} | {e} | {pf} | {wr} | {r['power']} |"
        )
    lines += [
        "",
        f"**n_eligible_corpus (H20-walkable bars):** {artifact['n_eligible_corpus']}",
        f"**n_resolver_shadow_exp (universe for Memory/TrendBias before strict_memory):** "
        f"{artifact['n_resolver_shadow_exp']}",
        f"**n_engine_atlas_exp:** {artifact['n_engine_atlas_exp']}",
        "",
        "## Object attribution (frozen)",
        "",
        "- Engine EXP = mostly DISP→EXP (plus a small SHADOW_EXPANSION_CONFIRMED remainder).",
        "- Resolver EXP = SHADOW→EXP. 0 DISP→EXP on this resolver object.",
        "- A result on one arm is not a result about the other construction's EXPANSION label.",
        "",
        "## Direction attribution (this run)",
        "",
        f"- Engine atlas `from_state`: `{artifact.get('engine_from_state_counts')}` "
        "(the 6 shadow-resume collapses are labeled SWEEP→EXP in the atlas, not SHADOW_PENDING).",
        f"- strict_memory skips: `{artifact.get('strict_memory_skip_counts')}`",
        f"- Memory vs TrendBias direction agree: "
        f"`{artifact.get('memory_trendbias_dir_agree')}` / `{artifact.get('n_resolver_shadow_exp')}`",
        "",
        "## Cases A–D (interpretive only; Memory / TrendBias vs Always-Long)",
        "",
    ]
    for k, v in artifact["cases_rubric"].items():
        mark = " **← CALL**" if k == cc["case"] else ""
        lines.append(f"- **Case {k}:** {v}{mark}")
    lines += [
        "",
        f"**Case call: {cc['case']}**",
        "",
        f"- Memory expectancy: `{cc.get('memory_expectancy')}`",
        f"- TrendBias expectancy: `{cc.get('trendbias_expectancy')}`",
        f"- Always-Long expectancy: `{cc.get('always_long_expectancy')}`",
        f"- Memory beats control: `{cc.get('memory_beats_control')}`",
        f"- TrendBias beats control: `{cc.get('trendbias_beats_control')}`",
        "",
        cc.get("note", ""),
        "",
        "## SUPERSEDED object (do not reuse as this scoreboard)",
        "",
        "The 2026-09-09 n=6 scoreboard captured **engine** `SHADOW_EXPANSION_CONFIRMED` "
        "via `StateMachine.try_shadow_pending_to_expansion`. That is not Resolver EXP. "
        "See `docs/research/phase1_resolver_replay_n6_funnel_diagnostic.md`. Kept, not deleted.",
        "",
        "## How to run",
        "",
        "```powershell",
        "cd D:\\Tradelatest",
        "$env:PYTHONPATH='D:\\Tradelatest'",
        ".\\venv\\Scripts\\python.exe scripts\\analysis\\phase1_resolver_replay_evidence.py",
        "```",
        "",
        "## Provenance",
        "",
        f"- run_id: `{artifact['run_id']}`",
        f"- source_run_id: `{artifact['provenance'].get('source_run_id')}`",
        f"- csv_sha256: `{artifact['provenance']['csv_sha256']}`",
        f"- cost: `{artifact['provenance']['cost_model_provenance'].get('ontology_id')}` "
        f"({artifact['provenance']['cost_model_provenance'].get('status')})",
        f"- config_version: `{artifact['provenance']['config_version']}`",
        f"- git_sha: `{artifact['provenance'].get('git_sha')}` tree_dirty=`{artifact['provenance'].get('tree_dirty')}`",
        f"- generated_at (UTC): `{artifact['generated_at']}`",
        f"- resolver replay mismatches: `{artifact['provenance'].get('n_state_mismatch')}`",
        "",
        "## Forbidden-work confirmation",
        "",
        "All forbidden flags in the JSON artifact are `false` "
        "(no continuous_disp flip, no CHoCH, no occupancy reopen, no parity optimize, "
        "no April reclassify, no TV forensic adjudicator, no economic promotion, no UI/L-003).",
        "",
        "---",
        "No economic promotion language. Measure-before-promote. Cases A–D only.",
        "",
    ]
    return "\n".join(lines)


def _print_scoreboard(rows: list[dict], run_id: str, case_call: dict) -> None:
    print(f"\nrun_id: {run_id}")
    print("=== SCOREBOARD (Phase-1 · ENTRY · H20 · SEM-015 TIMEOUT) ===")
    print(f"{'arm':22s} {'n':>5s} {'cov%':>10s} {'E':>10s} {'PF':>8s} {'WR':>8s} {'power':>12s}")
    for row in rows:
        e = f"{row['expectancy']:+.4f}" if row["expectancy"] is not None else "   n/a"
        pf = f"{row['PF']:.3f}" if row["PF"] is not None else "  n/a"
        wr = f"{100 * row['win_rate']:.1f}%" if row["win_rate"] is not None else "  n/a"
        print(
            f"{row['arm']:22s} {row['n']:5d} {row['coverage_pct']:9.4f}% "
            f"{e:>10s} {pf:>8s} {wr:>8s} {row['power']:>12s}"
        )
    print(f"\nCase call (Memory/TrendBias vs Always-Long): {case_call['case']} — {case_call['rubric']}")
    print("DESCRIPTIVE ONLY — economic_claims_allowed=false — no promotion.")


def _resolver_create_funnel(creates: list[dict]) -> dict:
    counts = Counter(c.get("outcome") for c in creates)
    n = len(creates)
    n_shadow = sum(1 for c in creates if c.get("reached_shadow_pending"))
    n_exp = int(counts.get("SHADOW_PENDING_TO_EXPANSION") or 0)
    n_sh_range = int(counts.get("SHADOW_PENDING_TO_RANGE") or 0)
    return {
        "CREATE": n,
        "EXPIRED_TTL": int(counts.get("EXPIRED_TTL") or 0),
        "CLEARED_NON_HTF_RESET": int(counts.get("CLEARED_NON_HTF_RESET") or 0),
        "OVERWRITTEN_BY_NEW_MEMORY": int(counts.get("OVERWRITTEN_BY_NEW_MEMORY") or 0),
        "SHADOW_PENDING": n_shadow,
        "SHADOW_PENDING_TO_EXPANSION": n_exp,
        "SHADOW_PENDING_TO_RANGE": n_sh_range,
        "UNRESOLVED_AT_EOF": int(counts.get("UNRESOLVED_AT_EOF") or 0),
        "outcome_counts": dict(counts),
        "P_SHADOW_PENDING_given_CREATE": (n_shadow / n) if n else None,
        "P_EXPANSION_given_SHADOW_PENDING": (n_exp / n_shadow) if n_shadow else None,
        "P_EXPANSION_given_CREATE": (n_exp / n) if n else None,
        "P_RANGE_given_SHADOW_PENDING": (n_sh_range / n_shadow) if n_shadow else None,
    }


def _resolver_create_census_main(args: argparse.Namespace) -> int:
    """Frozen-grain resolver CREATE count. No four-arm H20. No engine-69 join."""
    run_dir = Path(args.run_dir)
    envelope = _OUT_DIR / "run_20260909_202201"
    envelope.mkdir(parents=True, exist_ok=True)
    print("resolver CREATE census")
    print("source_run_id: run_20260906_013609")
    print("injection: none")
    print("predicate: _force_range_reset kind==htf AND prev==DISPLACEMENT AND shadow_on_htf_displacement_reset")
    print("do_not_join: engine CREATE 69")
    collapses, ident = run_resolver_memory_replay(run_dir)
    if ident.get("n_state_mismatch", 0) != 0:
        print("BLOCKER: resolver replay did not reproduce parquet ontology_state.")
        print(f"  mismatches={ident['n_state_mismatch']} first={ident.get('first_mismatch')}")
        return 2
    expected_shadow_exp = int(ident.get("expected_resolver_shadow_exp") or 0)
    if len(collapses) != expected_shadow_exp:
        print("BLOCKER: captured SHADOW→EXP count != parquet SHADOW→EXP entries.")
        print(f"  captured={len(collapses)} parquet={expected_shadow_exp}")
        return 2
    creates = list(_Capture.creates)
    funnel = _resolver_create_funnel(creates)
    payload = {
        "artifact": "phase1_resolver_create_census",
        "source_run_id": "run_20260906_013609",
        "session_run_id": "run_20260909_202201",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "claim_class": "DESCRIPTIVE_ONLY",
        "economic_claims_allowed": False,
        "authority": "none",
        "producer": "resolver",
        "predicate": {
            "site": "CRTStateResolver._force_range_reset",
            "kind": "htf",
            "prev": "DISPLACEMENT",
            "shadow_on_htf_displacement_reset": True,
        },
        "injection": "none",
        "do_not_join": ["engine_CREATE_69"],
        "replay_identity": ident,
        "funnel": funnel,
        "n_shadow_exp_collapses": len(collapses),
        "n_shadow_entries_without_open_create": int(
            ident.get("n_shadow_entries_without_open_create") or 0
        ),
        "parquet_resolver_shadow_pending_entries": 47,
        "parquet_resolver_shadow_to_exp": 31,
        "parquet_resolver_shadow_to_range": 16,
        "creates": creates,
    }
    out_path = envelope / "resolver_create_census.json"
    out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"CREATE n={funnel['CREATE']}")
    print(f"funnel={ {k: funnel[k] for k in ('CREATE','EXPIRED_TTL','CLEARED_NON_HTF_RESET','OVERWRITTEN_BY_NEW_MEMORY','SHADOW_PENDING','SHADOW_PENDING_TO_EXPANSION','SHADOW_PENDING_TO_RANGE','UNRESOLVED_AT_EOF')} }")
    print(
        "P(SHADOW|CREATE)=",
        funnel["P_SHADOW_PENDING_given_CREATE"],
        "P(EXP|SHADOW)=",
        funnel["P_EXPANSION_given_SHADOW_PENDING"],
        "P(EXP|CREATE)=",
        funnel["P_EXPANSION_given_CREATE"],
    )
    print(f"SHADOW entries without open CREATE: {payload['n_shadow_entries_without_open_create']}")
    print(f"SHADOW→EXP collapses: {len(collapses)} (parquet {expected_shadow_exp})")
    print(f"wrote {out_path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--csv", default=str(_DEFAULT_CSV))
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--bar-matrix", default=str(_DEFAULT_BAR_MATRIX))
    ap.add_argument("--run-dir", default=str(_DEFAULT_RUN_DIR))
    ap.add_argument("--atlas", default=str(_DEFAULT_ATLAS))
    ap.add_argument("--out-dir", default=str(_OUT_DIR))
    ap.add_argument(
        "--legacy-engine-shadow-bt",
        action="store_true",
        help="Run the old engine StateMachine SHADOW capture (n=6 object). Not the four-arm.",
    )
    ap.add_argument(
        "--skip-replay",
        action="store_true",
        help="Reuse collapses.json if present (legacy engine-shadow debug only).",
    )
    ap.add_argument(
        "--resolver-create-census",
        action="store_true",
        help="Count resolver HTF-DISP CREATE on the frozen grain only. No four-arm H20.",
    )
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.resolver_create_census:
        return _resolver_create_census_main(args)
    csv_path = Path(args.csv)
    if not csv_path.is_file():
        print(f"BLOCKER: Phase-1 corpus missing at {csv_path}")
        return 2
    if not _MANIFEST.is_file():
        print(f"BLOCKER: SEM-015 cost manifest missing at {_MANIFEST}")
        return 2

    try:
        cost_model = ComponentCostModel.from_manifest(
            json.loads(_MANIFEST.read_text(encoding="utf-8")),
            instrument="XAUUSD",
            source=_MANIFEST.name,
        )
    except UnmeasuredCostError as exc:
        print(f"BLOCKER: SEM-015 cost model unusable — {exc}")
        return 2

    if args.legacy_engine_shadow_bt:
        return _legacy_engine_shadow_main(args, out_dir, csv_path, cost_model)

    run_id = datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")
    run_out = out_dir / run_id
    run_out.mkdir(parents=True, exist_ok=True)
    print(f"run_id: {run_id}")
    print("replaying CRTStateResolver over dual-construction LIVE vectors (injection=none)...")

    collapses, ident = run_resolver_memory_replay(Path(args.run_dir))
    if ident.get("n_state_mismatch", 0) != 0:
        print("BLOCKER: resolver replay did not reproduce parquet ontology_state.")
        print(f"  mismatches={ident['n_state_mismatch']} first={ident.get('first_mismatch')}")
        (run_out / "replay_identity.json").write_text(
            json.dumps(ident, indent=2, default=str), encoding="utf-8"
        )
        return 2
    expected_shadow = int(ident.get("expected_resolver_shadow_exp") or 0)
    if len(collapses) != expected_shadow:
        print("BLOCKER: captured SHADOW→EXP count != parquet SHADOW→EXP entries.")
        print(f"  captured={len(collapses)} parquet={expected_shadow}")
        (run_out / "replay_identity.json").write_text(
            json.dumps(ident, indent=2, default=str), encoding="utf-8"
        )
        return 2
    print(f"captured resolver SHADOW→EXP: {len(collapses)} (matches parquet)")

    corpus = load_corpus(csv_path)
    n_eligible_corpus = max(0, len(corpus) - HORIZON)

    for ep in collapses:
        ep["memory_direction_raw"] = _dir_to_long_short(ep.get("pending_displacement_dir"))
        src = ep.get("pending_dir_source")
        if ep["memory_direction_raw"] is None:
            ep["memory_direction"] = None
            ep["strict_memory_skip"] = "no_pending_displacement_dir"
        elif src == "trend_bias_fill":
            ep["memory_direction"] = None
            ep["strict_memory_skip"] = "trend_bias_fill"
        else:
            ep["memory_direction"] = ep["memory_direction_raw"]
            ep["strict_memory_skip"] = None
        ep["trendbias_direction"] = _tb_to_long_short(ep.get("trend_bias"))
        if ep.get("live_atr") is None or (isinstance(ep.get("live_atr"), float) and math.isnan(ep["live_atr"])):
            ep["live_atr"] = None

    mem_entries = []
    for ep in collapses:
        mem_entries.append(
            {
                "bar_index": ep["bar_index"],
                "direction": ep.get("memory_direction"),
                "live_atr": ep.get("live_atr"),
                "strict_memory_skip": ep.get("strict_memory_skip"),
            }
        )
    # strict_memory already nulled direction; _score_entries will skip no_direction
    mem_nets, mem_eligible = _score_entries(
        mem_entries, direction_key="direction", atr_key="live_atr",
        corpus=corpus, cost_model=cost_model, skip_key="memory_skip",
    )
    for src, dst in zip(collapses, mem_entries):
        src["memory_skip"] = dst.get("memory_skip")
        src["memory_net_R"] = dst.get("net_R")

    tb_entries = [
        {
            "bar_index": ep["bar_index"],
            "direction": ep.get("trendbias_direction"),
            "live_atr": ep.get("live_atr"),
        }
        for ep in collapses
    ]
    tb_nets, tb_eligible = _score_entries(
        tb_entries, direction_key="direction", atr_key="live_atr",
        corpus=corpus, cost_model=cost_model, skip_key="trendbias_skip",
    )
    for src, dst in zip(collapses, tb_entries):
        src["trendbias_skip"] = dst.get("trendbias_skip")
        src["trendbias_net_R"] = dst.get("net_R")

    print("scoring Engine-Atlas EXP entries...")
    engine_entries = _engine_atlas_entries(Path(args.atlas))
    from_counts: dict[str, int] = {}
    for e in engine_entries:
        k = str(e.get("from_state") or "UNKNOWN")
        from_counts[k] = from_counts.get(k, 0) + 1
    eng_nets, eng_eligible = _score_entries(
        engine_entries, direction_key="direction", atr_key="live_atr",
        corpus=corpus, cost_model=cost_model, skip_key="engine_skip",
    )

    atr_by_index: dict[int, float] = {}
    # Prefer construction live_atr via collapses' sibling: load from engine entries + collapses
    for e in engine_entries:
        if e.get("live_atr"):
            atr_by_index[int(e["bar_index"])] = float(e["live_atr"])
    for ep in collapses:
        if ep.get("live_atr"):
            atr_by_index[int(ep["bar_index"])] = float(ep["live_atr"])
    # Fill remaining from bar_matrix atr_abs (Always-Long needs every stride bar)
    try:
        _trend_by_ts, atr_by_ts = _load_trend_bias_by_ts(Path(args.bar_matrix))
    except FileNotFoundError as exc:
        print(f"BLOCKER: {exc}")
        return 2
    for i, row in enumerate(corpus):
        if i in atr_by_index:
            continue
        key = row["ts"].strftime("%Y-%m-%d %H:%M:%S")
        if key in atr_by_ts:
            atr_by_index[i] = atr_by_ts[key]

    al_nets: list[float] = []
    al_universe = 0
    for i in range(len(corpus)):
        if (i % STRIDE) != 0:
            continue
        al_universe += 1
        atr = atr_by_index.get(i)
        if not atr or atr <= 0:
            continue
        net = _net_r(corpus, i, "LONG", float(atr), cost_model)
        if net is None:
            continue
        al_nets.append(net)

    eng_row = _scoreboard_row(
        "Engine-Atlas", eng_nets, n_universe=n_eligible_corpus, n_eligible=eng_eligible
    )
    mem_row = _scoreboard_row(
        "Resolver-Memory", mem_nets, n_universe=n_eligible_corpus, n_eligible=mem_eligible
    )
    tb_row = _scoreboard_row(
        "Resolver-TrendBias", tb_nets, n_universe=n_eligible_corpus, n_eligible=tb_eligible
    )
    al_row = _scoreboard_row(
        "Always-Long", al_nets, n_universe=n_eligible_corpus, n_eligible=al_universe
    )
    al_row["n_stride_universe"] = al_universe
    case_call = _call_case(mem_row, tb_row, al_row)
    mem_tb_agree = sum(
        1
        for ep in collapses
        if ep.get("memory_direction")
        and ep.get("memory_direction") == ep.get("trendbias_direction")
    )

    artifact = {
        "artifact": "phase1_fourarm_replay",
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "claim_class": "DESCRIPTIVE_ONLY",
        "economic_claims_allowed": False,
        "authority": "none",
        "standing_contract": {
            "unit": "ENTRY",
            "corpus": "Phase-1",
            "horizon": "H20",
            "cost": "SEM-015 TIMEOUT",
            "control": "Always-Long stride H20",
            "engine_atlas": "EXP entry + atlas direction (mostly DISP→EXP)",
            "resolver_memory": "SHADOW→EXP + pending_displacement_dir (strict_memory)",
            "resolver_trendbias": "SHADOW→EXP + trend_bias sign",
            "coverage": "n_entries / eligible_corpus (never resolver_n / engine_n)",
            "outputs": ["n", "coverage_pct", "expectancy", "PF", "win_rate"],
        },
        "forbidden_work_confirmation": {
            "continuous_disp_to_expansion_flipped": False,
            "choch_wired": False,
            "occupancy_reopened": False,
            "parity_optimized": False,
            "april_offsession_reclassified": False,
            "tv_forensic_as_occupancy_adjudicator": False,
            "economic_promotion": False,
            "ui_or_l003_reopen": False,
        },
        "provenance": {
            **_git_provenance(),
            "csv_path": str(csv_path),
            "csv_sha256": _sha256_file(csv_path),
            "bar_matrix": str(args.bar_matrix),
            "run_dir": str(args.run_dir),
            "atlas": str(args.atlas),
            "source_run_id": ident.get("run_id"),
            "source_config_version": ident.get("config_version"),
            "source_config_hash": ident.get("config_hash"),
            "ontology_source": ident.get("ontology_source"),
            "n_state_mismatch": ident.get("n_state_mismatch"),
            "n_resolver_errors": ident.get("n_resolver_errors"),
            "cost_model_provenance": cost_model.provenance(),
            "config_version": PROD_VERSION,
            "horizon": HORIZON,
            "always_long_stride": STRIDE,
        },
        "n_eligible_corpus": n_eligible_corpus,
        "n_resolver_shadow_exp": len(collapses),
        "n_engine_atlas_exp": len(engine_entries),
        "engine_from_state_counts": from_counts,
        "strict_memory_skip_counts": _count_key(collapses, "strict_memory_skip"),
        "memory_trendbias_dir_agree": mem_tb_agree,
        "replay_identity": {k: ident[k] for k in ident if k != "expected_resolver_exp_entries" or True},
        "collapses": collapses,
        "engine_entries": engine_entries,
        "scoreboard": {
            "Engine-Atlas": eng_row,
            "Resolver-Memory": mem_row,
            "Resolver-TrendBias": tb_row,
            "Always-Long": al_row,
        },
        "cases_rubric": CASES_RUBRIC,
        "case_call": case_call,
    }
    assert_no_claim_keys(artifact)

    json_path = run_out / "scoreboard.json"
    json_path.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")
    latest_json = out_dir / "scoreboard.LATEST.json"
    latest_json.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")
    (run_out / "run_manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "artifact": "phase1_fourarm_replay",
                "source_run_id": ident.get("run_id"),
                "generated_at": artifact["generated_at"],
                "economic_claims_allowed": False,
                "n_eligible_corpus": n_eligible_corpus,
                "scoreboard": artifact["scoreboard"],
                "case_call": {"case": case_call["case"]},
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    md = _render_md(artifact)
    (run_out / "scoreboard.md").write_text(md, encoding="utf-8")
    (out_dir / "scoreboard.LATEST.md").write_text(md, encoding="utf-8")
    _NOTE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _NOTE_PATH.write_text(md, encoding="utf-8")

    _print_scoreboard([eng_row, mem_row, tb_row, al_row], run_id, case_call)
    print(f"JSON: {json_path}")
    print(f"LATEST: {latest_json}")
    print(f"NOTE: {_NOTE_PATH}")
    return 0


def _count_key(rows: list[dict], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        k = r.get(key)
        name = "none" if k is None else str(k)
        out[name] = out.get(name, 0) + 1
    return out


def _legacy_engine_shadow_main(args, out_dir: Path, csv_path: Path, cost_model) -> int:
    """Historical n=6 engine-shadow object. Not the authorized four-arm."""
    collapses_path = out_dir / "collapses.json"
    if args.skip_replay and collapses_path.is_file():
        collapses = json.loads(collapses_path.read_text(encoding="utf-8"))
        print(f"reused collapses: {len(collapses)} from {collapses_path}")
    else:
        print("running ENGINE SHADOW→EXP collapse replay (legacy object)...")
        collapses = run_shadow_collapse_replay(csv_path, args.instrument, out_dir)
        collapses_path.write_text(json.dumps(collapses, indent=2), encoding="utf-8")
        print(f"captured collapses: {len(collapses)} → {collapses_path}")

    trend_by_ts, atr_by_ts = _load_trend_bias_by_ts(Path(args.bar_matrix))
    corpus = load_corpus(csv_path)

    for ep in collapses:
        key = _normalize_ts(ep["timestamp"])
        ep["trend_bias"] = trend_by_ts.get(key)
        ep["trend_bias_ts_key"] = key
        if ep.get("atr_abs") is None:
            ep["atr_abs"] = atr_by_ts.get(key)
        ep["memory_direction"] = _dir_to_long_short(ep.get("pending_displacement_dir"))
        ep["trendbias_direction"] = _tb_to_long_short(ep.get("trend_bias"))

    n_universe = len(collapses)
    mem_nets, mem_eligible = [], 0
    for ep in collapses:
        d = ep["memory_direction"]
        if d is None:
            ep["memory_skip"] = "no_pending_displacement_dir"
            continue
        mem_eligible += 1
        atr = ep.get("atr_abs")
        if not atr or atr <= 0:
            ep["memory_skip"] = "no_atr"
            continue
        net = _net_r(corpus, ep["candle_index"], d, float(atr), cost_model)
        if net is None:
            ep["memory_skip"] = "horizon_truncated"
            continue
        ep["memory_net_R"] = net
        ep["memory_skip"] = None
        mem_nets.append(net)

    tb_nets, tb_eligible = [], 0
    for ep in collapses:
        d = ep["trendbias_direction"]
        if d is None:
            ep["trendbias_skip"] = "trend_bias_zero_or_missing"
            continue
        tb_eligible += 1
        atr = ep.get("atr_abs")
        if not atr or atr <= 0:
            ep["trendbias_skip"] = "no_atr"
            continue
        net = _net_r(corpus, ep["candle_index"], d, float(atr), cost_model)
        if net is None:
            ep["trendbias_skip"] = "horizon_truncated"
            continue
        ep["trendbias_net_R"] = net
        ep["trendbias_skip"] = None
        tb_nets.append(net)

    atr_by_index: dict[int, float] = {}
    for i, row in enumerate(corpus):
        key = row["ts"].strftime("%Y-%m-%d %H:%M:%S")
        if key in atr_by_ts:
            atr_by_index[i] = atr_by_ts[key]
    al_nets, al_universe = [], 0
    for i in range(len(corpus)):
        if (i % STRIDE) != 0:
            continue
        al_universe += 1
        atr = atr_by_index.get(i)
        if not atr or atr <= 0:
            continue
        net = _net_r(corpus, i, "LONG", float(atr), cost_model)
        if net is None:
            continue
        al_nets.append(net)

    mem_row = _scoreboard_row("Resolver-Memory", mem_nets, n_universe=n_universe, n_eligible=mem_eligible)
    tb_row = _scoreboard_row("Resolver-TrendBias", tb_nets, n_universe=n_universe, n_eligible=tb_eligible)
    al_row = _scoreboard_row("Always-Long", al_nets, n_universe=al_universe, n_eligible=al_universe)
    case_call = _call_case(mem_row, tb_row, al_row)
    print("LEGACY engine-shadow object — not the authorized four-arm.")
    _print_scoreboard([mem_row, tb_row, al_row], "legacy-engine-shadow", case_call)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
