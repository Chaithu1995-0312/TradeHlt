"""
CRT State Resolver — Bar-aligned Confusion Matrix
=================================================
Transition-parity instrument (research only, no production authority).

Compares the config-driven CRTStateResolver against a reconstructed engine
state timeline derived from a CRT backtest events.jsonl.

WHY THIS EXISTS
---------------
Aggregate dwell counts hide *where* the resolver first diverges from the
engine. This script produces:

  1. Per-bar engine timeline (from STATE_TRANSITION + RESET events)
  2. Per-bar resolver timeline (FeaturePipeline → CRTStateResolver)
  3. Confusion matrix (engine_state × resolver_state)
  4. First-divergence catalog (engine entered X while resolver stayed Y)
  5. Transition-level agreement (engine edges vs resolver edges)

USAGE
-----
    python scripts/research/crt_state_confusion_matrix.py \\
        --ohlcv data/mt5/XAUUSD_M15.csv \\
        --events results/run_20260724_104845_XAUUSD/XAUUSD_events.jsonl \\
        --reference-summary results/run_20260724_104845_XAUUSD/XAUUSD_summary.json \\
        --output reports/crt_state_confusion_matrix.md

AUTHORITY
---------
Research / documentation only. Does not enable market_reality crt_state.
Does not modify production config or CRT engine behaviour.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

logger = logging.getLogger("CRT_CONFUSION")

ALL_STATES = [
    "RANGE",
    "SWEEP",
    "DISPLACEMENT",
    "EXPANSION",
    "RETEST",
    "EXECUTION",
    "RESOLUTION",
    "SHADOW_PENDING",
    "EXPIRED",
]


# ── Engine timeline reconstruction ────────────────────────────────

@dataclass
class EngineTimeline:
    """Bar-aligned engine states reconstructed from events.jsonl."""

    enter_states: list[str]          # state at bar open (prev_state; what state_counts uses)
    exit_states: list[str]           # state after process_candle
    n_bars: int
    n_transitions: int
    n_resets: int
    htf_resets: int
    gap_resets: int
    other_resets: int
    transition_pairs: Counter = field(default_factory=Counter)
    reset_from_counts: Counter = field(default_factory=Counter)
    reconstruction_notes: list[str] = field(default_factory=list)


def load_events(events_path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with events_path.open("r", encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rec["_ord"] = i
            events.append(rec)
    return events


def remap_event_indices_to_ohlcv(
    events: list[dict[str, Any]],
    ohlcv_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Map engine ``candle_index`` → raw OHLCV row via timestamp join.

    Backtest events stamp ``candle_index`` from ``process_candle``'s internal
    counter, which is **not** the raw CSV row (XAUUSD M15 MT5 run measures a
    constant +74 offset). Resolver FeaturePipeline paths use raw rows via
    ``_src_idx``. Without this remap, confusion matrices compare misaligned bars.
    """
    import pandas as pd

    df = pd.read_csv(ohlcv_path)
    df.columns = [c.lower() for c in df.columns]
    ts_col = "timestamp" if "timestamp" in df.columns else "time"
    df[ts_col] = pd.to_datetime(df[ts_col])
    ts_to_raw = {pd.Timestamp(t): i for i, t in enumerate(df[ts_col])}

    remapped: list[dict[str, Any]] = []
    deltas: Counter = Counter()
    miss = 0
    for e in events:
        e2 = dict(e)
        ts = e.get("timestamp")
        eng_i = e.get("candle_index")
        if ts is not None and eng_i is not None:
            raw = ts_to_raw.get(pd.Timestamp(ts))
            if raw is not None:
                deltas[int(raw) - int(eng_i)] += 1
                e2["candle_index"] = int(raw)
                e2["_engine_candle_index"] = int(eng_i)
            else:
                miss += 1
        remapped.append(e2)

    meta = {
        "n_events": len(events),
        "n_miss_timestamp": miss,
        "delta_mode": deltas.most_common(1)[0] if deltas else None,
        "delta_histogram_top": deltas.most_common(5),
    }
    return remapped, meta


def reconstruct_engine_timeline(
    events: list[dict[str, Any]],
    n_bars: int,
) -> EngineTimeline:
    """Replay STATE_TRANSITION + RESET into enter/exit state arrays.

    Alignment with backtest_v2.py:1916-2109:
      prev_state = engine.state.current_state  # enter
      process_candle(...)
      curr_state = engine.state.current_state  # exit
      state_counts[prev_state] += 1

    So ``enter_states`` is what the engine summary's state_distribution counts.
    """
    state_events = [
        e for e in events
        if e.get("event") in ("STATE_TRANSITION", "RESET") and e.get("state_to")
    ]
    # Sort by candle_index, stable on file order for same-index multi-events
    state_events.sort(key=lambda e: (int(e["candle_index"]), e["_ord"]))

    by_idx: dict[int, list[dict]] = defaultdict(list)
    for e in state_events:
        by_idx[int(e["candle_index"])].append(e)

    n_transitions = sum(1 for e in state_events if e["event"] == "STATE_TRANSITION")
    n_resets = sum(1 for e in state_events if e["event"] == "RESET")
    htf = gap = other = 0
    reset_from: Counter = Counter()
    pairs: Counter = Counter()

    for e in state_events:
        if e["event"] == "STATE_TRANSITION":
            pairs[(e.get("state_from"), e.get("state_to"))] += 1
        elif e["event"] == "RESET":
            reset_from[e.get("state_from") or "?"] += 1
            reason = str(e.get("reason") or "")
            if "HTF changed" in reason:
                htf += 1
            elif "gap" in reason.lower() or "Session gap" in reason:
                gap += 1
            else:
                other += 1

    cur = "RANGE"
    enter: list[str] = []
    exit_: list[str] = []
    notes: list[str] = []

    max_event_idx = max(by_idx.keys()) if by_idx else -1
    if max_event_idx >= n_bars:
        notes.append(
            f"WARNING: event candle_index max={max_event_idx} >= n_bars={n_bars}; "
            "extra events ignored for bars beyond OHLCV length."
        )

    skipped_stale_resets = 0
    for i in range(n_bars):
        enter.append(cur)
        if i in by_idx:
            for e in by_idx[i]:
                new_state = e["state_to"]
                # Honor the engine's AUTHORITATIVE state_from. reset_to_range emits
                # state_from = current_state.name (crt_engine_v2.py:1712), so a RESET whose
                # state_from disagrees with our running state is a reset the engine issued from a
                # DIFFERENT state than the one we are tracking — applying it would truncate a
                # still-active state. This is the EXPANSION drift root cause: an unguarded replay
                # lets a reset issued from RANGE/SWEEP cut a live EXPANSION, giving 3,060 vs the
                # authoritative state_distribution's 4,605. Guarding on state_from reproduces the
                # summary (EXPANSION 4,604). STATE_TRANSITION events are always applied (their
                # state_from is the pre-transition state by construction).
                if (
                    e.get("event") == "RESET"
                    and e.get("state_from") is not None
                    and e.get("state_from") != cur
                ):
                    skipped_stale_resets += 1
                    continue
                # Defensive: only accept known state names
                if new_state not in ALL_STATES and new_state != "RANGE":
                    notes.append(
                        f"Unknown state_to={new_state!r} at candle_index={i}; applying anyway."
                    )
                cur = str(new_state)
        exit_.append(cur)

    if skipped_stale_resets:
        notes.append(
            f"Skipped {skipped_stale_resets} RESET event(s) whose state_from disagreed with the "
            "reconstructed state (engine state_from is authoritative; these resets applied to a "
            "state the engine was not in at that bar). This is what reconciles reconstructed "
            "EXPANSION dwell with state_distribution."
        )

    # If we never saw RESOLUTION in events as exit, note it
    if "RESOLUTION" not in Counter(exit_) and any(
        e.get("state_to") == "RESOLUTION" for e in state_events
    ):
        notes.append("RESOLUTION appeared in events but not in exit timeline (check ordering).")

    return EngineTimeline(
        enter_states=enter,
        exit_states=exit_,
        n_bars=n_bars,
        n_transitions=n_transitions,
        n_resets=n_resets,
        htf_resets=htf,
        gap_resets=gap,
        other_resets=other,
        transition_pairs=pairs,
        reset_from_counts=reset_from,
        reconstruction_notes=notes,
    )


# ── Resolver timeline ─────────────────────────────────────────────

def compute_enriched_frame(
    ohlcv_path: Path,
    *,
    fp_cfg: Optional[dict] = None,
    _df: Optional[Any] = None,
) -> Any:
    """Run FeaturePipeline once; return the enriched frame (with ``_src_idx``).

    PARITY SWEEP PERFORMANCE SEAM (F-069 program): FeaturePipeline output is
    invariant across CRTStateResolver-config candidates in a Stage-A sweep —
    only ``config_path`` (market_crt_states.yaml) varies, never the feature
    vector. Call this once per sweep and pass the result to every
    ``build_resolver_timeline(..., enriched=...)`` call.

    ``_df`` is an internal reuse seam for callers (``build_resolver_timeline``)
    that already loaded+renamed the raw OHLCV — not part of the public
    contract.
    """
    import numpy as np
    import pandas as pd
    from features.feature_pipeline import FeaturePipeline

    if _df is None:
        df = pd.read_csv(ohlcv_path)
        rename = {c: c.lower() for c in df.columns if c.lower() in
                  {"open", "high", "low", "close", "volume", "timestamp", "time"}}
        df = df.rename(columns=rename)
    else:
        df = _df

    n_raw = len(df)
    # Preserve raw OHLCV positions through FeaturePipeline.finalize(), which
    # dropna()+reset_index(drop=True) and would otherwise re-zero the index —
    # breaking engine HTF phase-lock (warmup drop ≈78 bars → full HTF phase slip).
    df_fp = df.copy()
    df_fp["_src_idx"] = np.arange(n_raw, dtype=np.int64)

    pipe = FeaturePipeline(df_fp, cfg=fp_cfg)
    enriched, _ = pipe.run()
    if "_src_idx" not in enriched.columns:
        raise RuntimeError(
            "FeaturePipeline dropped _src_idx; cannot phase-lock HTF to engine. "
            "Expected finalize() to retain non-canonical columns."
        )
    return enriched


def build_resolver_timeline(
    ohlcv_path: Path,
    config_path: Optional[Path] = None,
    *,
    htf_mode: str = "engine",
    instrument: str = "XAUUSD",
    candles_per_htf: Optional[int] = None,
    engine_reset_by_idx: Optional[dict[int, str]] = None,
    engine_state_to_by_idx: Optional[dict[int, str]] = None,
    enriched: Optional[Any] = None,
    fp_cfg: Optional[dict] = None,
) -> tuple[list[str], list[int], dict[str, Any]]:
    """Run FeaturePipeline + CRTStateResolver; return (states, source_indices, meta).

    FeaturePipeline.finalize() drops warmup rows, so returned states are shorter
    than raw OHLCV. ``source_indices`` maps each resolver bar → original candle index.

    htf_mode:
      * ``engine`` (default) — phase-lock HTF ids to engine HTFBuilder timeline
        built over the full raw OHLCV length (fixes warmup-drop phase drift).
      * ``internal`` — resolver's own bar counter from the enriched slice only.

    engine_reset_by_idx:
      Optional map raw candle_index → RESET reason from a CRT engine
      events.jsonl. When provided, bars that the engine reset are passed as
      ``engine_reset=True`` so active_range rebuilds on the same freeze bars
      (B1b range-rebuild edge parity). Research shadow only.

    engine_state_to_by_idx:
      Optional map raw candle_index → STATE_TRANSITION state_to (B1e EXP
      entry/exit inject for residual DISP→EXP + FP over-hold).

    enriched:
      Optional pre-computed FeaturePipeline output (must retain ``_src_idx``).
      PARITY SWEEP PERFORMANCE SEAM (F-069 program): the enriched frame is
      invariant across CRTStateResolver-config candidates — only ``config_path``
      changes between sweep iterations, never the feature vector. Passing a
      cached frame skips the FeaturePipeline re-run (~half the per-candidate
      cost). Caller is responsible for invalidating the cache if ``fp_cfg``
      changes (this function does not fingerprint it).

    fp_cfg:
      Optional FeaturePipeline config-section overlay (full section copy with
      a delta applied — ``FeaturePipeline._require_fp_cfg`` is strict on all
      37 ``_FP_CFG_KEYS``; a partial dict raises). Ignored when ``enriched``
      is supplied. ``None`` loads the active production section (unchanged
      default behaviour).
    """
    import pandas as pd
    from features.feature_pipeline import FeaturePipeline
    from features.crt_state_resolver import CRTStateResolver, build_htf_id_timeline
    from features.feature_schema import CANONICAL_FEATURES

    import numpy as np

    # Raw OHLC is always loaded (cheap: a CSV read, not the FeaturePipeline
    # compute). Needed for the warmup-range HTF seed step below regardless of
    # whether `enriched` is cached, because seeding replays raw bars that
    # FeaturePipeline.finalize() drops (they never appear in `enriched`).
    df = pd.read_csv(ohlcv_path)
    rename = {c: c.lower() for c in df.columns if c.lower() in
              {"open", "high", "low", "close", "volume", "timestamp", "time"}}
    df = df.rename(columns=rename)

    n_raw = len(df)
    if enriched is not None:
        if "_src_idx" not in enriched.columns:
            raise RuntimeError(
                "Cached `enriched` frame is missing `_src_idx`; cannot phase-lock "
                "HTF to engine. Pass the frame returned by an earlier "
                "compute_enriched_frame() call, not a raw FeaturePipeline().run()."
            )
    else:
        enriched = compute_enriched_frame(ohlcv_path, fp_cfg=fp_cfg, _df=df)
    source_indices = [int(v) for v in enriched["_src_idx"].tolist()]

    thr_defaults = {"rsi_overbought": 70.0, "rsi_oversold": 30.0}
    resolver = CRTStateResolver(config_path=config_path)
    # CH-resolution-site: turn the (default-OFF, decision-neutral) RC-003 capture on
    # so every bar carries WHICH branch produced its state. F-069 classified the
    # residual by mismatch CELL only, which cannot separate a TTL expiry from a
    # dwell hold from predicate exhaustion. Observation only — the recorder does not
    # influence control flow, and the injection=none parity number must reproduce
    # 88.1560% exactly with it on.
    resolver.record_resolver_evidence = True
    resolver.last_resolver_evidence = {}
    thr = resolver._config.get("thresholds", {})
    rsi_ob = float(thr.get("rsi_overbought", thr_defaults["rsi_overbought"]))
    rsi_os = float(thr.get("rsi_oversold", thr_defaults["rsi_oversold"]))

    life = thr.get("lifecycle") or {}
    cph = int(
        candles_per_htf
        if candles_per_htf is not None
        else life.get("htf_candles_per_range", 4)
    )

    # Engine-aligned HTF ids over the FULL raw stream (pre-warmup-drop)
    engine_htf_ids: list[str] | None = None
    if htf_mode == "engine":
        engine_htf_ids = build_htf_id_timeline(
            n_raw, candles_per_htf=cph, instrument=instrument
        )

    # B1: seed HTF-range memory with raw bars dropped by FeaturePipeline warmup
    # so active_range matches engine initialise_range after BacktestRunner warmup.
    first_src = int(source_indices[0]) if source_indices else 0
    if (
        getattr(resolver, "_sweep_geometry", "pipeline_swing") == "htf_range"
        and first_src > 0
    ):
        raw_o = df["open"].astype(float).tolist()
        raw_h = df["high"].astype(float).tolist()
        raw_l = df["low"].astype(float).tolist()
        raw_c = df["close"].astype(float).tolist()
        for i in range(first_src):
            hid = engine_htf_ids[i] if engine_htf_ids is not None else None
            resolver.seed_ohlc(raw_o[i], raw_h[i], raw_l[i], raw_c[i], htf_id=hid)
        resolver.finalize_seed_range()

    # Prefer timestamp column for gap detection; fall back to index-only HTF
    ts_col = None
    for cand in ("timestamp", "time", "datetime"):
        if cand in enriched.columns:
            ts_col = cand
            break
    if ts_col is not None:
        enriched = enriched.copy()
        enriched[ts_col] = pd.to_datetime(enriched[ts_col])

    states: list[str] = []
    resolution_sites: list[Optional[str]] = []
    htf_ids_used: list[str] = []
    for row_i, (_, row) in enumerate(enriched.iterrows()):
        fv: dict[str, float] = {}
        for name in CANONICAL_FEATURES:
            if name in enriched.columns:
                val = row[name]
                if pd.isna(val):
                    val = 0.0
                fv[name] = float(val)
        for name in ("retest_flag", "displacement_flag"):
            if name in enriched.columns:
                val = row[name]
                fv[name] = 0.0 if pd.isna(val) else float(val)
            else:
                fv[name] = 0.0
        # rsi_state from rsi_14
        rsi = fv.get("rsi_14", 50.0)
        if rsi > rsi_ob:
            fv["rsi_state"] = 1.0
        elif rsi < rsi_os:
            fv["rsi_state"] = -1.0
        else:
            fv["rsi_state"] = 0.0
        ts = row[ts_col] if ts_col is not None else None
        if ts is not None and pd.isna(ts):
            ts = None

        src = source_indices[row_i]
        htf_id = None
        if engine_htf_ids is not None and 0 <= src < len(engine_htf_ids):
            htf_id = engine_htf_ids[src]
            htf_ids_used.append(htf_id)

        eng_rsn = None
        eng_rst = False
        if engine_reset_by_idx is not None and src in engine_reset_by_idx:
            eng_rst = True
            eng_rsn = engine_reset_by_idx[src]
        eng_to = None
        if engine_state_to_by_idx is not None:
            eng_to = engine_state_to_by_idx.get(src)

        states.append(
            resolver.resolve(
                fv,
                timestamp=ts,
                htf_id=htf_id,
                engine_reset=eng_rst,
                reset_reason=eng_rsn,
                engine_state_to=eng_to,
            )
        )
        # CH-resolution-site: WHICH branch produced that state. Parallel to
        # `states` by construction (appended in the same iteration), so the
        # analysis side never has to re-align them.
        ev = resolver.last_resolver_evidence or {}
        resolution_sites.append(ev.get("resolution_site"))

    # Phase-lock diagnostics
    n_htf_changes = 0
    if htf_ids_used:
        prev = htf_ids_used[0]
        for hid in htf_ids_used[1:]:
            if hid != prev:
                n_htf_changes += 1
                prev = hid

    meta = {
        "n_raw": n_raw,
        "n_resolved": len(states),
        "n_dropped_warmup": n_raw - len(states),
        "resolver_counts": dict(Counter(states)),
        "config": str(resolver._config_path),
        "lifecycle_stats": resolver.lifecycle_stats,
        "lifecycle_cfg": {
            k: (sorted(v) if isinstance(v, set) else v)
            for k, v in resolver._lifecycle.items()
        },
        "htf_mode": htf_mode,
        "htf_instrument": instrument,
        "htf_candles_per_range": cph,
        "htf_unique_ids": len(set(htf_ids_used)) if htf_ids_used else 0,
        "htf_changes_on_resolved_slice": n_htf_changes,
        "htf_first_id": htf_ids_used[0] if htf_ids_used else None,
        "htf_last_id": htf_ids_used[-1] if htf_ids_used else None,
        "engine_reset_injection": (
            len(engine_reset_by_idx) if engine_reset_by_idx is not None else 0
        ),
        "engine_state_to_injection": (
            len(engine_state_to_by_idx) if engine_state_to_by_idx is not None else 0
        ),
        # CH-resolution-site. Carried in meta rather than widening the return tuple,
        # so crt_parity_sweep.py and run_once() keep their existing unpacking.
        "resolution_sites": resolution_sites,
        "site_counts": dict(Counter(s for s in resolution_sites if s is not None)),
        "n_site_unattributed": sum(1 for s in resolution_sites if s is None),
    }
    return states, source_indices, meta


# ── Injection map builders (extracted from main() for sweep reuse) ─

def build_engine_reset_map(events: list[dict[str, Any]], n_bars: int) -> dict[int, str]:
    """Raw candle_index → RESET reason, honoring the state_from guard.

    A RESET whose ``state_from`` disagrees with the running reconstructed
    state is skipped (mirrors ``reconstruct_engine_timeline``'s guard) so the
    injection map cannot desync from the engine timeline it's paired with.
    """
    engine_reset_by_idx: dict[int, str] = {}
    cur = "RANGE"
    by_idx: dict[int, list] = defaultdict(list)
    for e in events:
        if e.get("event") in ("STATE_TRANSITION", "RESET") and e.get("state_to"):
            by_idx[int(e["candle_index"])].append(e)
    for i in range(n_bars):
        for e in by_idx.get(i, []):
            if (
                e.get("event") == "RESET"
                and e.get("state_from") is not None
                and e.get("state_from") != cur
            ):
                continue
            if e.get("event") == "RESET":
                engine_reset_by_idx[i] = str(e.get("reason") or "engine_reset")
            cur = str(e["state_to"])
    return engine_reset_by_idx


def build_engine_state_to_map(events: list[dict[str, Any]]) -> dict[int, str]:
    """Raw candle_index → STATE_TRANSITION "FROM>TO" (last transition on bar wins).

    FROM is required so SWEEP→EXP inject cannot fire on a bare TO=EXPANSION.
    """
    engine_state_to_by_idx: dict[int, str] = {}
    for e in events:
        if e.get("event") != "STATE_TRANSITION" or not e.get("state_to"):
            continue
        ci = int(e["candle_index"])
        fr = str(e.get("state_from") or "")
        to = str(e["state_to"])
        engine_state_to_by_idx[ci] = f"{fr}>{to}" if fr else to
    return engine_state_to_by_idx


# Injection modes, ordered weakest→strongest oracle assistance. "none" is the
# ONLY mode that answers "can the resolver reproduce the engine from
# configuration alone" — the others are diagnostics (F-069 program).
INJECTION_MODES = ("none", "reset", "state_to", "full")


def _injection_maps_for_mode(
    mode: str,
    engine_reset_by_idx: dict[int, str],
    engine_state_to_by_idx: dict[int, str],
) -> tuple[Optional[dict[int, str]], Optional[dict[int, str]]]:
    if mode not in INJECTION_MODES:
        raise ValueError(f"Unknown injection mode {mode!r}; expected one of {INJECTION_MODES}")
    reset_map = engine_reset_by_idx if mode in ("reset", "full") else None
    state_to_map = engine_state_to_by_idx if mode in ("state_to", "full") else None
    return reset_map, state_to_map


# ── Confusion matrix + divergence analysis ────────────────────────

@dataclass
class ConfusionReport:
    engine_mode: str                     # "enter" | "exit"
    engine_counts: Counter
    resolver_counts: Counter
    reference_counts: dict[str, int]
    matrix: dict[tuple[str, str], int]   # (engine, resolver) → count
    agreement: int
    total: int
    # First-divergence: engine transition edges where resolver disagreed
    edge_mismatches: list[dict[str, Any]]
    # Where engine is X and resolver is Y (top off-diagonal cells)
    top_confusions: list[tuple[str, str, int]]
    # Consecutive runs where states differ
    divergence_episodes: list[dict[str, Any]]
    n_aligned_bars: int
    # CH-resolution-site (additive, empty when sites were not supplied):
    # (engine, resolver, resolution_site) → count over MISMATCHED bars only, plus
    # the pre-predicate / predicate-derived split of the residual. This is the
    # dimension F-069 never had — it classified by cell, never by code path.
    site_matrix: dict[tuple[str, str, str], int] = field(default_factory=dict)
    residual_site_counts: dict[str, int] = field(default_factory=dict)
    residual_pre_predicate: int = 0
    residual_predicate_derived: int = 0
    residual_site_unattributed: int = 0


def build_confusion(
    engine_states: list[str],
    resolver_states: list[str],
    source_indices: list[int],
    *,
    engine_mode: str,
    reference: dict[str, int],
    engine_events: list[dict[str, Any]],
    max_edge_samples: int = 40,
    max_episodes: int = 30,
    resolution_sites: Optional[list[Optional[str]]] = None,
) -> ConfusionReport:
    """Align resolver bars to engine via source_indices; build matrix.

    ``resolution_sites`` (optional, parallel to ``resolver_states``) adds the
    CH-resolution-site cross-tab. Omitted → the report's site fields stay empty
    and every pre-existing field is unchanged, so old callers are unaffected.
    """
    # Map: only bars that exist in both
    eng_aligned: list[str] = []
    res_aligned: list[str] = []
    idx_aligned: list[int] = []
    site_aligned: list[Optional[str]] = []
    for res_i, src_i in enumerate(source_indices):
        if 0 <= src_i < len(engine_states):
            eng_aligned.append(engine_states[src_i])
            res_aligned.append(resolver_states[res_i])
            idx_aligned.append(src_i)
            if resolution_sites is not None and res_i < len(resolution_sites):
                site_aligned.append(resolution_sites[res_i])
            else:
                site_aligned.append(None)

    matrix: Counter = Counter()
    for e, r in zip(eng_aligned, res_aligned):
        matrix[(e, r)] += 1

    # ── CH-resolution-site: cross-tab over MISMATCHED bars only ──────────────
    # The question is "which branch produced the residual", so agreeing bars are
    # deliberately excluded — including them would let the ~88% agreement swamp
    # the 11.84% the measurement is about.
    site_matrix: Counter = Counter()
    residual_site_counts: Counter = Counter()
    residual_pre = residual_post = residual_unattributed = 0
    if resolution_sites is not None:
        from features.crt_state_resolver import _PRE_PREDICATE_SITES  # noqa: PLC0415

        for e, r, s in zip(eng_aligned, res_aligned, site_aligned):
            if e == r:
                continue
            if s is None:
                residual_unattributed += 1
                continue
            site_matrix[(e, r, s)] += 1
            residual_site_counts[s] += 1
            if s in _PRE_PREDICATE_SITES:
                residual_pre += 1
            else:
                residual_post += 1

    agreement = sum(1 for e, r in zip(eng_aligned, res_aligned) if e == r)
    total = len(eng_aligned)

    # Off-diagonal ranked
    off = [(a, b, c) for (a, b), c in matrix.items() if a != b]
    off.sort(key=lambda t: -t[2])

    # Divergence episodes (contiguous runs of mismatch)
    episodes: list[dict[str, Any]] = []
    i = 0
    while i < total and len(episodes) < max_episodes:
        if eng_aligned[i] != res_aligned[i]:
            j = i
            pair_counts: Counter = Counter()
            while j < total and eng_aligned[j] != res_aligned[j]:
                pair_counts[(eng_aligned[j], res_aligned[j])] += 1
                j += 1
            top_pair = pair_counts.most_common(1)[0]
            episodes.append({
                "start_idx": idx_aligned[i],
                "end_idx": idx_aligned[j - 1],
                "length": j - i,
                "dominant_engine": top_pair[0][0],
                "dominant_resolver": top_pair[0][1],
                "dominant_n": top_pair[1],
            })
            i = j
        else:
            i += 1

    # Engine transition edges: at STATE_TRANSITION candle, did resolver match state_to?
    edge_mismatches: list[dict[str, Any]] = []
    res_by_src = {src: res_aligned[k] for k, src in enumerate(idx_aligned)}
    for e in engine_events:
        if e.get("event") != "STATE_TRANSITION":
            continue
        ci = int(e["candle_index"])
        if ci not in res_by_src:
            continue
        eng_to = e.get("state_to")
        res = res_by_src[ci]
        if eng_to != res:
            edge_mismatches.append({
                "candle_index": ci,
                "timestamp": e.get("timestamp"),
                "engine_from": e.get("state_from"),
                "engine_to": eng_to,
                "resolver": res,
                "reason": (e.get("reason") or "")[:120],
            })
            if len(edge_mismatches) >= max_edge_samples * 20:
                # collect more for stats, truncate display later
                pass

    return ConfusionReport(
        engine_mode=engine_mode,
        engine_counts=Counter(eng_aligned),
        resolver_counts=Counter(res_aligned),
        reference_counts=reference,
        matrix=dict(matrix),
        agreement=agreement,
        total=total,
        edge_mismatches=edge_mismatches,
        top_confusions=off[:25],
        divergence_episodes=episodes,
        n_aligned_bars=total,
        site_matrix=dict(site_matrix),
        residual_site_counts=dict(residual_site_counts),
        residual_pre_predicate=residual_pre,
        residual_predicate_derived=residual_post,
        residual_site_unattributed=residual_unattributed,
    )


# ── Reporting ─────────────────────────────────────────────────────

def _pct(n: int, d: int) -> str:
    return f"{100.0 * n / d:.2f}%" if d else "n/a"


def write_markdown(
    path: Path,
    timeline: EngineTimeline,
    res_meta: dict[str, Any],
    report: ConfusionReport,
    reference: dict[str, int],
    *,
    ohlcv_path: str,
    events_path: str,
) -> None:
    lines: list[str] = []
    a = lines.append

    a("# CRT State Resolver — Bar-Aligned Confusion Matrix")
    a("")
    a(f"> Generated: {__import__('datetime').datetime.now().isoformat()}")
    a(">")
    a("> **Authority:** research / documentation only. `crt_state.enabled` stays false.")
    a("> Milestone: **transition parity** (not dwell tuning).")
    a("")
    a("## Purpose")
    a("")
    a("Feature completeness is closed. Remaining divergence is **lifecycle** and")
    a("**detector semantics**. This report localizes *where* the resolver first")
    a("disagrees with the engine on a per-bar basis, so HTF-reset and detector")
    a("work can target concrete mismatch cells instead of aggregate dwell totals.")
    a("")
    a("## Inputs")
    a("")
    a(f"| Input | Path |")
    a(f"|-------|------|")
    a(f"| OHLCV | `{ohlcv_path}` |")
    a(f"| Engine events | `{events_path}` |")
    a(f"| Resolver config | `{res_meta.get('config')}` |")
    a(f"| Engine mode | `{report.engine_mode}` (enter = prev_state / state_distribution basis) |")
    a("")
    a("## Engine timeline reconstruction")
    a("")
    a(f"- Bars: **{timeline.n_bars:,}**")
    a(f"- STATE_TRANSITION events: **{timeline.n_transitions:,}**")
    a(f"- RESET events: **{timeline.n_resets:,}** "
      f"(HTF={timeline.htf_resets:,}, gap={timeline.gap_resets:,}, other={timeline.other_resets:,})")
    a(f"- Reset-from histogram: `{dict(timeline.reset_from_counts)}`")
    a("")
    a("### Engine transition pairs (top)")
    a("")
    a("| From | To | N |")
    a("|------|----|---|")
    for (frm, to), n in timeline.transition_pairs.most_common(20):
        a(f"| {frm} | {to} | {n:,} |")
    a("")
    if timeline.reconstruction_notes:
        a("### Reconstruction notes")
        a("")
        for note in timeline.reconstruction_notes:
            a(f"- {note}")
        a("")

    a("### Dwell: reconstructed enter-state vs summary reference")
    a("")
    a("| State | Reconstructed (enter) | Summary reference | Δ |")
    a("|-------|----------------------|-------------------|---|")
    enter_c = Counter(timeline.enter_states)
    for s in ALL_STATES:
        e = enter_c.get(s, 0)
        r = reference.get(s, 0)
        if e == 0 and r == 0:
            continue
        a(f"| {s} | {e:,} | {r:,} | {e - r:+,} |")
    a("")
    a("> **Note (root-caused 2026-07-25):** the events stream is COMPLETE and consistent")
    a("> (STATE_TRANSITION count == sum of non-RANGE entry counts; RESET count == RANGE entries).")
    a("> The earlier EXPANSION under-count (reconstructed 3,060 vs `state_distribution` 4,605) was")
    a("> a RECONSTRUCTION bug, not lossy telemetry: the replay applied RESET events without honoring")
    a("> the engine's authoritative `state_from` (reset_to_range emits state_from=current_state,")
    a("> crt_engine_v2.py:1712). A reset issued from RANGE/SWEEP was truncating a still-active")
    a("> reconstructed EXPANSION. The state_from guard above reconciles the timeline with")
    a("> `state_distribution` (EXPANSION 4,604 ≈ 4,605). `expansion_dwell_stats` (≈6,105) is a")
    a("> separate metric — the candidate-lifetime INDEX SPAN, not continuous per-bar occupancy.")
    a("")

    a("## Resolver run")
    a("")
    a(f"- Raw OHLCV bars: **{res_meta['n_raw']:,}**")
    a(f"- Resolved bars (post-warmup): **{res_meta['n_resolved']:,}** "
      f"(dropped {res_meta['n_dropped_warmup']})")
    a(f"- Aligned bars (resolver ∩ engine): **{report.n_aligned_bars:,}**")
    life = res_meta.get("lifecycle_stats") or {}
    if life:
        a(f"- Resolver lifecycle resets: HTF=**{life.get('htf_reset_count', 0):,}** "
          f"gap=**{life.get('gap_reset_count', 0):,}** "
          f"forced=**{life.get('forced_reset_count', 0):,}**")
    a(f"- **HTF mode:** `{res_meta.get('htf_mode', 'n/a')}` "
      f"(instrument=`{res_meta.get('htf_instrument')}`, "
      f"window={res_meta.get('htf_candles_per_range')})")
    if res_meta.get("htf_mode") == "engine":
        a(f"- HTF phase-lock: unique ids=**{res_meta.get('htf_unique_ids', 0):,}**, "
          f"changes on resolved slice=**{res_meta.get('htf_changes_on_resolved_slice', 0):,}**, "
          f"range `{res_meta.get('htf_first_id')}` → `{res_meta.get('htf_last_id')}`")
    a("")
    a("| State | Resolver | Engine (aligned) | Reference |")
    a("|-------|----------|------------------|-----------|")
    for s in ALL_STATES:
        rc = report.resolver_counts.get(s, 0)
        ec = report.engine_counts.get(s, 0)
        ref = reference.get(s, 0)
        if rc == 0 and ec == 0 and ref == 0:
            continue
        a(f"| {s} | {rc:,} | {ec:,} | {ref:,} |")
    a("")

    a("## Agreement")
    a("")
    a(f"- **Exact bar match:** {report.agreement:,} / {report.total:,} "
      f"(**{_pct(report.agreement, report.total)}**)")
    a(f"- **Mismatch bars:** {report.total - report.agreement:,} "
      f"({_pct(report.total - report.agreement, report.total)})")
    a("")

    a("## Confusion matrix")
    a("")
    a("Rows = **engine** state; columns = **resolver** state.")
    a("")
    # Column header: only states that appear
    used = sorted(
        {s for (e, r) in report.matrix for s in (e, r)},
        key=lambda s: ALL_STATES.index(s) if s in ALL_STATES else 99,
    )
    a("| eng\\res | " + " | ".join(used) + " | row sum |")
    a("|---------|" + "|".join(["------"] * len(used)) + "|---------|")
    for eng in used:
        row = [report.matrix.get((eng, res), 0) for res in used]
        cells = " | ".join(f"**{v}**" if used[i] == eng else f"{v}" for i, v in enumerate(row))
        a(f"| **{eng}** | {cells} | {sum(row):,} |")
    a("")

    a("### Top off-diagonal confusions (engine → resolver mislabel)")
    a("")
    a("| Engine | Resolver | N | % of mismatches |")
    a("|--------|----------|---|-----------------|")
    n_mis = report.total - report.agreement
    for eng, res, n in report.top_confusions:
        a(f"| {eng} | {res} | {n:,} | {_pct(n, n_mis)} |")
    a("")

    a("## Divergence episodes (contiguous mismatch runs)")
    a("")
    a("First episodes by timeline order (capped).")
    a("")
    a("| Start idx | End idx | Len | Dominant engine | Dominant resolver | Dom N |")
    a("|-----------|---------|-----|-----------------|-------------------|-------|")
    for ep in report.divergence_episodes:
        a(
            f"| {ep['start_idx']} | {ep['end_idx']} | {ep['length']} | "
            f"{ep['dominant_engine']} | {ep['dominant_resolver']} | {ep['dominant_n']} |"
        )
    a("")

    a("## Engine transition edges where resolver disagreed")
    a("")
    a("At each `STATE_TRANSITION` candle_index, compare engine `state_to` vs resolver state.")
    a("")
    # Summarize edge mismatch types
    edge_types = Counter(
        (m["engine_from"], m["engine_to"], m["resolver"])
        for m in report.edge_mismatches
    )
    a(f"- Total disagreeing transition edges: **{len(report.edge_mismatches):,}**")
    a("")
    a("| Engine from | Engine to | Resolver at bar | N |")
    a("|-------------|-----------|-----------------|---|")
    for (frm, to, res), n in edge_types.most_common(25):
        a(f"| {frm} | {to} | {res} | {n:,} |")
    a("")
    a("### Sample mismatches (first 40)")
    a("")
    a("| Idx | Time | Engine | Resolver | Reason |")
    a("|-----|------|--------|----------|--------|")
    for m in report.edge_mismatches[:40]:
        eng = f"{m['engine_from']}→{m['engine_to']}"
        a(
            f"| {m['candle_index']} | {m['timestamp']} | {eng} | "
            f"{m['resolver']} | {m['reason']} |"
        )
    a("")

    a("## Interpretation guide (for next milestones)")
    a("")
    a("| Pattern | Likely cause | Next lever |")
    a("|---------|--------------|------------|")
    a("| Engine RANGE, resolver SWEEP/EXPANSION | Sticky lifecycle / no HTF terminate | HTF reset memory |")
    a("| Engine SWEEP, resolver RANGE | Missed sweep detection or funnel order | Sweep detector / funnel |")
    a("| Engine DISPLACEMENT, resolver SWEEP/RANGE | Detector threshold / body gate | Engine-grade displacement |")
    a("| Engine EXPANSION, resolver RETEST | Permissive retest_flag | Engine-grade retest |")
    a("| Engine RETEST, resolver EXPANSION | Retest under-fire | Retest detector |")
    a("| Engine RESET edges invisible to resolver | HTF/gap lifecycle | Wire RESET→RANGE in resolver |")
    a("")
    a("## Production stance")
    a("")
    a("- `market_reality.crt_state.enabled = false` — **unchanged**")
    a("- CRT engine remains execution authority")
    a("- This matrix is the gate for HTF-reset and detector PRs: each change should")
    a("  **shrink a named off-diagonal cell** without collapsing SWEEP agreement")
    a("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Report written to {path}")


def write_json_artifact(
    path: Path,
    report: ConfusionReport,
    timeline: EngineTimeline,
    res_meta: dict[str, Any],
) -> None:
    """Machine-readable companion for later regression pins."""
    payload = {
        "authority": "research_only",
        "engine_mode": report.engine_mode,
        "agreement": report.agreement,
        "total": report.total,
        "agreement_rate": report.agreement / report.total if report.total else 0.0,
        "engine_counts": dict(report.engine_counts),
        "resolver_counts": dict(report.resolver_counts),
        "reference_counts": report.reference_counts,
        "matrix": {f"{e}|{r}": n for (e, r), n in report.matrix.items()},
        "top_confusions": [
            {"engine": a, "resolver": b, "n": n} for a, b, n in report.top_confusions
        ],
        "edge_mismatch_n": len(report.edge_mismatches),
        "timeline": {
            "n_bars": timeline.n_bars,
            "n_transitions": timeline.n_transitions,
            "n_resets": timeline.n_resets,
            "htf_resets": timeline.htf_resets,
            "gap_resets": timeline.gap_resets,
            "reset_from_counts": dict(timeline.reset_from_counts),
        },
        "resolver_meta": res_meta,
        # CH-resolution-site: decision provenance over the residual.
        "resolution_site": {
            "site_matrix": {
                f"{e}|{r}|{s}": n for (e, r, s), n in report.site_matrix.items()
            },
            "residual_site_counts": report.residual_site_counts,
            "residual_pre_predicate": report.residual_pre_predicate,
            "residual_predicate_derived": report.residual_predicate_derived,
            "residual_site_unattributed": report.residual_site_unattributed,
        },
    }
    # The per-bar site list is large and already summarised above; keep it out of
    # the artifact so the JSON stays diffable.
    if isinstance(payload.get("resolver_meta"), dict):
        payload["resolver_meta"] = {
            k: v for k, v in payload["resolver_meta"].items() if k != "resolution_sites"
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"JSON artifact written to {path}")


# ── Reusable core (sweep-driver entry point, F-069 program) ────────

@dataclass
class PreparedEngineContext:
    """Engine-side inputs, computed once and reused across many resolver-config
    candidates in a Stage-A sweep (the engine backtest itself does not change
    between candidates — only ``config_path``/``fp_cfg`` do).
    """

    ohlcv_path: Path
    events_path: Path
    n_bars: int
    events: list[dict[str, Any]]
    timeline: EngineTimeline
    reference: dict[str, int]
    engine_reset_by_idx: dict[int, str]
    engine_state_to_by_idx: dict[int, str]


def prepare_engine_context(
    ohlcv_path: Path,
    events_path: Path,
    *,
    reference_summary_path: Optional[Path] = None,
) -> PreparedEngineContext:
    """Load events + reconstruct the engine timeline ONCE. Reuse the returned
    context across every Stage-A candidate via ``run_once(engine_ctx=...)``.
    """
    import pandas as pd

    reference: dict[str, int] = {s: 0 for s in ALL_STATES}
    if reference_summary_path and reference_summary_path.exists():
        summary = json.loads(reference_summary_path.read_text(encoding="utf-8"))
        for k, v in (summary.get("state_distribution") or {}).items():
            reference[k] = int(v)

    events = load_events(events_path)
    n_bars = len(pd.read_csv(ohlcv_path))
    events, _remap_meta = remap_event_indices_to_ohlcv(events, ohlcv_path)
    timeline = reconstruct_engine_timeline(events, n_bars)
    engine_reset_by_idx = build_engine_reset_map(events, n_bars)
    engine_state_to_by_idx = build_engine_state_to_map(events)

    return PreparedEngineContext(
        ohlcv_path=ohlcv_path,
        events_path=events_path,
        n_bars=n_bars,
        events=events,
        timeline=timeline,
        reference=reference,
        engine_reset_by_idx=engine_reset_by_idx,
        engine_state_to_by_idx=engine_state_to_by_idx,
    )


def run_once(
    engine_ctx: PreparedEngineContext,
    *,
    config_path: Optional[Path] = None,
    engine_mode: str = "exit",
    injection: str = "none",
    htf_mode: str = "engine",
    instrument: str = "XAUUSD",
    candles_per_htf: Optional[int] = None,
    enriched: Optional[Any] = None,
    fp_cfg: Optional[dict] = None,
    max_episodes: int = 30,
) -> tuple[ConfusionReport, dict[str, Any]]:
    """One resolver-config candidate against a fixed, pre-computed engine
    timeline. The reusable core behind both the CLI and the sweep driver.

    injection: one of INJECTION_MODES. ``"none"`` is config-only (the F-069
    program's primary metric); ``"full"`` matches the CLI's historical
    unconditional-injection default and is a diagnostic upper bound only.

    max_episodes: forwarded to ``build_confusion``. The CLI's historical
    default (30) is preserved unless the caller raises it — the sweep driver
    passes a high value so ``len(divergence_episodes)`` is a TRUE total, not
    a value silently capped by this default.
    """
    reset_map, state_to_map = _injection_maps_for_mode(
        injection, engine_ctx.engine_reset_by_idx, engine_ctx.engine_state_to_by_idx
    )
    res_states, source_indices, res_meta = build_resolver_timeline(
        engine_ctx.ohlcv_path,
        config_path,
        htf_mode=htf_mode,
        instrument=instrument,
        candles_per_htf=candles_per_htf,
        engine_reset_by_idx=reset_map,
        engine_state_to_by_idx=state_to_map,
        enriched=enriched,
        fp_cfg=fp_cfg,
    )
    res_meta["injection"] = injection

    engine_states = (
        engine_ctx.timeline.enter_states if engine_mode == "enter"
        else engine_ctx.timeline.exit_states
    )
    report = build_confusion(
        engine_states,
        res_states,
        source_indices,
        engine_mode=engine_mode,
        reference=engine_ctx.reference,
        engine_events=engine_ctx.events,
        max_episodes=max_episodes,
        resolution_sites=res_meta.get("resolution_sites"),
    )
    return report, res_meta


# ── CLI ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bar-aligned CRT resolver vs engine confusion matrix"
    )
    parser.add_argument(
        "--ohlcv",
        default="data/mt5/XAUUSD_M15.csv",
        help="OHLCV CSV used for FeaturePipeline + resolver",
    )
    parser.add_argument(
        "--events",
        default="results/run_20260724_104845_XAUUSD/XAUUSD_events.jsonl",
        help="CRT engine events.jsonl from a matching backtest run",
    )
    parser.add_argument(
        "--reference-summary",
        default="results/run_20260724_104845_XAUUSD/XAUUSD_summary.json",
        help="Engine summary.json for state_distribution reference",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Optional market_crt_states.yaml override",
    )
    parser.add_argument(
        "--engine-mode",
        choices=("enter", "exit"),
        default="exit",
        help="Compare against engine enter-state (prev) or exit-state (curr). "
             "Default EXIT matches resolver post-process semantics (B1c sticky). "
             "Use enter only for state_distribution occupancy comparison.",
    )
    parser.add_argument(
        "--htf-mode",
        choices=("engine", "internal"),
        default="engine",
        help="HTF phase source: 'engine' phase-locks to HTFBuilder timeline over "
             "full OHLCV (default); 'internal' uses resolver bar counter only.",
    )
    parser.add_argument(
        "--instrument",
        default="XAUUSD",
        help="Instrument prefix for engine HTF ids (default XAUUSD)",
    )
    parser.add_argument(
        "--htf-candles-per-range",
        type=int,
        default=None,
        help="Override HTF window size (default: config lifecycle / 4)",
    )
    parser.add_argument(
        "--output",
        default="reports/crt_state_confusion_matrix.md",
        help="Markdown report path",
    )
    parser.add_argument(
        "--json-out",
        default="reports/crt_state_confusion_matrix.json",
        help="Machine-readable artifact path",
    )
    parser.add_argument(
        "--injection",
        choices=INJECTION_MODES,
        default="full",
        help="Engine-oracle assistance fed into the resolver via resolve()'s "
             "engine_reset/engine_state_to params (F-069 program). 'full' "
             "(default) preserves this script's historical unconditional-"
             "injection behaviour byte-for-byte. 'none' is config-only — the "
             "only mode that measures 'can the resolver reproduce the engine "
             "from configuration alone' (CRT Semantic Parity primary metric). "
             "'reset'/'state_to' isolate each oracle channel individually.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    )

    ohlcv_path = Path(args.ohlcv)
    events_path = Path(args.events)
    if not ohlcv_path.exists():
        print(f"ERROR: OHLCV not found: {ohlcv_path}")
        sys.exit(1)
    if not events_path.exists():
        print(f"ERROR: events not found: {events_path}")
        sys.exit(1)

    reference_summary_path = Path(args.reference_summary) if args.reference_summary else None
    if reference_summary_path and reference_summary_path.exists():
        summary = json.loads(reference_summary_path.read_text(encoding="utf-8"))
        ref_preview = {k: v for k, v in (summary.get("state_distribution") or {}).items() if v}
        print(f"Reference state_distribution: {ref_preview}")

    print(f"Loading events from {events_path}...")
    print(f"Reconstructing engine timeline + injection maps (injection={args.injection})...")
    engine_ctx = prepare_engine_context(
        ohlcv_path, events_path, reference_summary_path=reference_summary_path,
    )
    timeline = engine_ctx.timeline
    print(
        f"  transitions={timeline.n_transitions} resets={timeline.n_resets} "
        f"(HTF={timeline.htf_resets} gap={timeline.gap_resets} other={timeline.other_resets})"
    )
    print(f"  enter dwell: {dict(Counter(timeline.enter_states))}")
    print(
        f"  engine RESET injection map: {len(engine_ctx.engine_reset_by_idx):,} raw bars "
        f"(after timestamp remap + state_from guard)"
    )
    print(
        f"  engine STATE_TRANSITION inject map: "
        f"{len(engine_ctx.engine_state_to_by_idx):,} raw bars"
    )

    print(f"Running resolver on {ohlcv_path} (htf_mode={args.htf_mode})...")
    cfg = Path(args.config) if args.config else None
    report, res_meta = run_once(
        engine_ctx,
        config_path=cfg,
        engine_mode=args.engine_mode,
        injection=args.injection,
        htf_mode=args.htf_mode,
        instrument=args.instrument,
        candles_per_htf=args.htf_candles_per_range,
    )
    print(f"  resolved={res_meta['n_resolved']} warmup_drop={res_meta['n_dropped_warmup']}")
    print(f"  resolver counts: {res_meta['resolver_counts']}")
    print(
        f"  HTF mode={res_meta.get('htf_mode')} "
        f"unique_ids={res_meta.get('htf_unique_ids')} "
        f"changes={res_meta.get('htf_changes_on_resolved_slice')} "
        f"first={res_meta.get('htf_first_id')} last={res_meta.get('htf_last_id')}"
    )
    life = res_meta.get("lifecycle_stats") or {}
    print(
        f"  lifecycle resets: HTF={life.get('htf_reset_count', 0)} "
        f"gap={life.get('gap_reset_count', 0)}"
    )
    print(
        f"  agreement={report.agreement}/{report.total} "
        f"({_pct(report.agreement, report.total)})"
    )
    print("  top confusions:")
    for eng, res, n in report.top_confusions[:8]:
        print(f"    engine={eng:<16} resolver={res:<16} n={n}")

    write_markdown(
        Path(args.output),
        timeline,
        res_meta,
        report,
        engine_ctx.reference,
        ohlcv_path=str(ohlcv_path),
        events_path=str(events_path),
    )
    write_json_artifact(Path(args.json_out), report, timeline, res_meta)


if __name__ == "__main__":
    main()
