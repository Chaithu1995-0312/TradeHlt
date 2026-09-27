"""
execution_planner_replay.py — split the RETEST->EXECUTION edge into Selection vs SL/TP (measure-only).

The gate-contribution study showed the entire +0.584R edge appears at the RETEST->EXECUTION gate, but
that jump conflates two things: (a) *which* retest candles are selected (session/zone/shadow + score),
and (b) the CRT engine's structure-based SL/TP vs a vanilla fixed SL/TP. This script separates them
with a 2x2 counterfactual, all four cells forward-simulated identically (only the varied dimension moves):

                       | vanilla SL/TP (1*ATR / 2*ATR) | CRT structure SL/TP (displacement-anchored)
    Selected (accepted)|              A                |   B   (anchor: ~ real executed +0.545R)
    Rejected (filtered)|              C                |   D   (the missing measurement)

  SL/TP-structure effect = mean(B-A) on selected AND mean(D-C) on rejected
  Selection effect       = mean(A-C) on vanilla   AND mean(B-D) on structure
  Observed C->B jump decomposes into the two effects + an interaction term.

Faithful to production:
  - RETEST candidates (selected + rejected) come from the additive RETEST_REPLAY telemetry the CRT
    engine emits (schemas.md 9.4) — the only source that carries trade DIRECTION + structure inputs.
  - Structure SL/TP is reconstructed with the exact build_trade formula (sl = displacement_candle
    {low|high} -/+ sl_atr_buffer*atr); verified to reproduce the engine's real sl/tp1 bit-for-bit.
  - Forward exits use analytics.sl_tp_comparator.simulate_exit (TP2>SL>TP1, matches BacktestRunner).

TWO EXIT ARMS (added in STORY-83.8 — the old arm is UNCHANGED and still written to the same
replay_bnbusdt.json payload, byte-for-byte comparable with the adba177 script's output):

  ARM 1 (default / unchanged)  analytics.sl_tp_comparator.simulate_exit — closes the WHOLE
      position at the first of TP2 > SL > TP1 over raw high/low (sl_tp_comparator.py:149-205).
  ARM 2 (new)                  research.oracle.multi_tp_walk — the SEM-017 two-target object
      production actually trades: partial_fraction realised at TP1, the runner trailed to
      entry + trail_fraction*(tp1-entry), remainder to TP2 (crt_engine_v2.py:2596-2603).
      tie_break="optimistic" reproduces simulate_exit's TP2 > SL > TP1 precedence over raw
      high/low (multi_tp_walk.py:324-346), so the ONLY difference left between the arms is the
      partial + trail object itself. Both arms walk the SAME records, SAME forward slice and
      SAME levels; the walk arm is aggregated through the SAME _aggregate_variant_results with
      a declared reason map (see _WALK_REASON_MAP).

The replay's candle load is now admitted BEFORE any content is read (corpus_gate.admit_corpus,
the build_bar_matrix.py:375-383 pattern). Previously it was a bare
SLTPComparator.load_candles_from_csv, i.e. the script's only ungated corpus read.

Measure-only: writes ONLY under results/execution_planner_replay/. No config edit, no promotion.
Trust gate (hard): cell B (structure on selected) must reproduce the real executed expectancy or the
harness is untrusted. Reported under BOTH walks.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, "src")

from analytics.sl_tp_comparator import (                       # noqa: E402
    _aggregate_variant_results,
    simulate_exit,
    SLTPComparator,
)
from data_ingestion.corpus_gate import admit_corpus               # noqa: E402
from data_ingestion.dataset_registry import DatasetAdmissionError  # noqa: E402
from data_ingestion.dataset_integrity import DatasetIntegrityError  # noqa: E402
from research.oracle.multi_tp_walk import (                     # noqa: E402
    OUT_STOPPED,
    OUT_TIMEOUT,
    OUT_TP1_BE_STOP,
    OUT_TP1_TP2,
    RUNNER_LEDGER_BLEND,
    TIE_BREAK_OPTIMISTIC,
    TIMEOUT_MARK_TO_CLOSE,
    multi_tp_walk,
)
from config_layer.production_config import (                   # noqa: E402
    PROD_VERSION,
    get_prod_section,
    load_prod_config_from_registry,
)
from config_layer.config_builder import ConfigBuilder          # noqa: E402
from runtime.backtest_v2 import (                              # noqa: E402
    BacktestConfig,
    BacktestRunner,
    CandleLoader,
)

SEED = 1337  # convention; the replay + backtest are deterministic
# Vanilla counterfactual = the opportunity_scanner definition (sl=1*ATR, tp=2*ATR fixed 2R).
VANILLA_SL_ATR = 1.0
VANILLA_TP_ATR = 2.0


def _norm_ts(s: str) -> str:
    return str(s).replace("T", " ").split("+")[0].split("Z")[0].strip()[:19]


def _run_backtest(
    instrument: str, csv: str, out_dir: Path, htf_clock_basis: str | None = None,
) -> tuple[Path, Path, object]:
    """Run one deterministic backtest on the ACTIVE prod config; return (telemetry, trades_csv, metrics).

    Faithful construction (mirrors phase6e_shadow_ab): load the registry crt_engine values + apply the
    market router via ConfigBuilder.from_existing. BacktestConfig.from_prod_config(instrument) ALONE
    rebuilds a CRTConfig from flat params/defaults (the session-sweep.md construction caveat) and would
    silently drop the v4 all-sessions override.

    `htf_clock_basis`: optional research-only override of BacktestConfig.htf_clock_basis
    ("count" | "calendar", backtest_v2.py:207/246). None (default) leaves the field exactly as
    from_prod_config() read it from the active config's `backtest` section — byte-identical to
    every other caller of this function. BacktestConfig is a plain (non-frozen) @dataclass, so
    this is a post-construction field override here in the research script, not a config-file
    or engine change — parent_crt.enabled=true on v2_htfcrt_2026_08 means ParentCRTFeed is
    already constructed unconditionally inside BacktestRunner.run() (backtest_v2.py:2334), so
    the calendar arm's own requirement (parent_feed is not None) is already satisfied.
    """
    base = load_prod_config_from_registry(PROD_VERSION, instrument)
    crt = ConfigBuilder.from_existing(instrument, base)
    cfg = BacktestConfig.from_prod_config(instrument=instrument, crt_config=crt)
    if htf_clock_basis is not None:
        if htf_clock_basis not in ("count", "calendar"):
            raise ValueError(f"htf_clock_basis override must be 'count' or 'calendar', got {htf_clock_basis!r}")
        cfg.htf_clock_basis = htf_clock_basis
    loader = CandleLoader(csv, instrument)
    runner = BacktestRunner(cfg, csv_path=csv)
    m = runner.run(loader.stream(), loader.count(), str(out_dir))
    tel = sorted(glob.glob(str(out_dir / "**" / f"*{instrument}*crt_telemetry*.jsonl"), recursive=True),
                 key=os.path.getmtime, reverse=True)
    trd = sorted(glob.glob(str(out_dir / "**" / f"{instrument}*trades.csv"), recursive=True),
                 key=os.path.getmtime, reverse=True)
    if not tel:
        raise SystemExit(f"no crt_telemetry.jsonl produced under {out_dir}")
    return Path(tel[0]), (Path(trd[0]) if trd else None), m


def _load_replay(telemetry_path: Path) -> list[dict]:
    out = []
    for line in open(telemetry_path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("kind") == "RETEST_REPLAY":
            out.append(d)
    return out


def _structure_levels(r: dict) -> tuple[float, float, float]:
    """Faithful build_trade SL/TP: SL anchored to displacement-candle extreme."""
    d = r["direction"]
    sl = r["disp_low"] - r["sl_atr_buffer"] * r["atr"] if d == 1 \
        else r["disp_high"] + r["sl_atr_buffer"] * r["atr"]
    risk = abs(r["entry"] - sl)
    tp1 = r["entry"] + d * r["tp1_mult"] * risk
    tp2 = r["entry"] + d * r["tp2_mult"] * risk
    return sl, tp1, tp2


def _vanilla_levels(r: dict) -> tuple[float, float, float]:
    """Vanilla fixed SL/TP: sl = 1*ATR, tp = 2*ATR (opportunity_scanner definition)."""
    d = r["direction"]
    risk = VANILLA_SL_ATR * r["atr"]
    sl = r["entry"] - d * risk
    tp = r["entry"] + d * VANILLA_TP_ATR * r["atr"]
    return sl, tp, tp  # single TP -> tp1 == tp2


def _simulate_cell(records: list[dict], levels_fn, candle_idx: dict, candles: list[dict],
                   max_candles: int) -> list[dict]:
    """Forward-simulate one population under one SL/TP method; return per-record result dicts."""
    results = []
    for r in records:
        i = candle_idx.get(_norm_ts(r["timestamp"]))
        if i is None:
            continue
        forward = candles[i + 1 : i + 1 + max_candles]
        if not forward:
            continue
        sl, tp1, tp2 = levels_fn(r)
        ex = simulate_exit(r["entry"], r["direction"], sl, tp1, tp2, forward, max_candles)
        ex["sl_dist_atr"] = round(abs(r["entry"] - sl) / r["atr"], 4) if r["atr"] > 0 else 0.0
        ex["entry"] = r["entry"]
        results.append(ex)
    return results


def compute_attribution(exp: dict) -> dict:
    """Pure 2x2 decomposition from the four cell expectancies (keys A_/B_/C_/D_*).

    Identity (both paths reconstruct the observed C->B jump):
        B - C == selection_effect_vanilla   + sltp_effect_on_selected
        B - C == selection_effect_structure + sltp_effect_on_rejected
    """
    a, b = exp["A_selected_vanilla"], exp["B_selected_structure"]
    c, d = exp["C_rejected_vanilla"], exp["D_rejected_structure"]
    return {
        "observed_C_to_B":            round(b - c, 4),
        "sltp_effect_on_selected":    round(b - a, 4),
        "sltp_effect_on_rejected":    round(d - c, 4),
        "selection_effect_vanilla":   round(a - c, 4),
        "selection_effect_structure": round(b - d, 4),
        "interaction":                round((b - a) - (d - c), 4),
    }


# -----------------------------------------------------------------------------
# SECOND EXIT ARM — the production object (SEM-017 two-target partial + trail)
# -----------------------------------------------------------------------------
WALK_TIE_BREAK = TIE_BREAK_OPTIMISTIC           # TP2 > SL > TP1 over raw high/low
WALK_PARTIAL_FRACTION = 0.5                     # execution_planner.partial_tp_fraction
WALK_TRAIL_FRACTION = 0.5                       # crt_engine_v2.py:2602 half-way trail
WALK_RUNNER_STOP_PRICING = RUNNER_LEDGER_BLEND   # every recorded backtest R came from the ledger blend
WALK_TIMEOUT_PRICING = TIMEOUT_MARK_TO_CLOSE     # finite-horizon policy: position-weighted mark

# OracleOutcome.outcome -> the exit_reason vocabulary _aggregate_variant_results counts.
# MAPPING NOTE (declared, not silent): the two-target object has NO "TP1-only" terminal state —
# a position that touches TP1 always leaves via TP2, the trail stop, or the horizon — so
# tp1_rate is structurally 0.0 on this arm, and sl_rate folds OUT_TP1_BE_STOP (a profitable
# trail stop) in with OUT_STOPPED. `walk_outcome_hist` below keeps the un-collapsed counts so
# the collapse is visible rather than assumed.
_WALK_REASON_MAP = {
    OUT_TP1_TP2:   "TP2",
    OUT_TP1_BE_STOP: "SL",
    OUT_STOPPED:   "SL",
    OUT_TIMEOUT:   "TIMEOUT",
}


@dataclass(frozen=True)
class _WalkBar:
    """Minimal bar for multi_tp_walk (attribute access; the loaded candles are dicts).

    Mirrors tests/research/test_multi_tp_walk_parity.py:44-52. `index` is the ABSOLUTE candle
    index so the kernel's own no-lookahead guard (multi_tp_walk.py:266-272) fires if a forward
    slice ever contains the entry bar.
    """

    high: float
    low: float
    close: float
    open: float = 0.0
    index: int = 0


def _sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _candles_fingerprint(candles: list[dict]) -> dict:
    """Count, endpoints and a sha of the OHLCV lines — the candle-list equality proof."""
    h = hashlib.sha256()
    for c in candles:
        h.update(f"{c['open']},{c['high']},{c['low']},{c['close']}\n".encode("utf-8"))
    return {
        "count": len(candles),
        "first_ts": candles[0]["timestamp"] if candles else None,
        "last_ts": candles[-1]["timestamp"] if candles else None,
        "ohlcv_sha256": h.hexdigest(),
    }


def _walk_future(forward: list[dict], entry_i: int) -> list[_WalkBar]:
    return [
        _WalkBar(
            high=float(c["high"]),
            low=float(c["low"]),
            close=float(c["close"]),
            open=float(c.get("open", c["close"])),
            index=entry_i + 1 + k,
        )
        for k, c in enumerate(forward)
    ]


def _walk_row(outcome, entry: float, sl: float, atr: float, key: str) -> dict:
    """Reshape one OracleOutcome into the dict shape _aggregate_variant_results consumes."""
    return {
        "realized_rr": outcome.rr_gross,
        "candles_held": outcome.duration_candles,
        "exit_reason": _WALK_REASON_MAP[outcome.outcome],
        "sl_dist_atr": round(abs(entry - sl) / atr, 4) if atr > 0 else 0.0,
        "entry": entry,
        # un-collapsed diagnostics; ignored by the aggregator, kept for the mapping audit
        "walk_outcome": outcome.outcome,
        "reached_tp1": outcome.reached_tp1,
        "bars_to_tp1": outcome.bars_to_tp1,
        "gapped_stop": outcome.gapped_stop,
        "_key": key,
    }


def _simulate_cell_pair(records: list[dict], levels_fn, candle_idx: dict,
                        candles: list[dict], max_candles: int,
                        ) -> tuple[list[dict], list[dict], list[str], list[str], list[dict]]:
    """One population, one forward slice, BOTH arms; aligned by record key.

    Arm 1 is inlined verbatim from _simulate_cell so the pairing cannot drift; caller asserts
    the two produce identical aggregates. Returns (old, walk, keys_old, keys_walk, skipped).
    """
    old: list[dict] = []
    walk: list[dict] = []
    keys_old: list[str] = []
    keys_walk: list[str] = []
    skipped: list[dict] = []
    for r in records:
        key = _norm_ts(r["timestamp"])
        i = candle_idx.get(key)
        if i is None:
            continue
        forward = candles[i + 1: i + 1 + max_candles]
        if not forward:
            continue
        sl, tp1, tp2 = levels_fn(r)

        # ---- ARM 1 — identical to _simulate_cell -------------------------------------
        ex = simulate_exit(r["entry"], r["direction"], sl, tp1, tp2, forward, max_candles)
        ex["sl_dist_atr"] = round(abs(r["entry"] - sl) / r["atr"], 4) if r["atr"] > 0 else 0.0
        ex["entry"] = r["entry"]
        old.append(ex)
        keys_old.append(key)

        # ---- ARM 2 — SEM-017 two-target partial + trail ------------------------------
        try:
            outcome = multi_tp_walk(
                r["entry"],
                "long" if r["direction"] == 1 else "short",
                sl, tp1, tp2,
                _walk_future(forward, i),
                tie_break=WALK_TIE_BREAK,
                partial_fraction=WALK_PARTIAL_FRACTION,
                trail_fraction=WALK_TRAIL_FRACTION,
                runner_stop_pricing=WALK_RUNNER_STOP_PRICING,
                timeout_pricing=WALK_TIMEOUT_PRICING,
                max_forward=max_candles,
            )
        except ValueError as exc:
            skipped.append({"key": key, "reason": str(exc)})
            continue
        walk.append(_walk_row(outcome, r["entry"], sl, r["atr"], key))
        keys_walk.append(key)
    return old, walk, keys_old, keys_walk, skipped


def _mean_rr(rows: list[dict]) -> float | None:
    return round(sum(r["realized_rr"] for r in rows) / len(rows), 4) if rows else None


def _reason_hist(rows: list[dict], field: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        k = r[field]
        out[k] = out.get(k, 0) + 1
    return out


def _walk_cell_block(records: list[dict], levels_fn, candle_idx: dict, candles: list[dict],
                     max_candles: int) -> tuple[dict, dict]:
    """Both arms over one cell -> (report block, walk exp-dict entry).

    agg_walk uses the walk arm's full walked set so compute_attribution sees an
    apples-to-apples 2x2. Paired subset means are reported alongside for audit.
    """
    old_rows = _simulate_cell(records, levels_fn, candle_idx, candles, max_candles)
    pair_old, walk_rows, keys_old, keys_walk, skipped = _simulate_cell_pair(
        records, levels_fn, candle_idx, candles, max_candles)

    agg_old = _aggregate_variant_results(old_rows)
    agg_pair_old = _aggregate_variant_results(pair_old)
    if agg_old != agg_pair_old:
        raise SystemExit(
            "HARNESS: the paired old arm diverged from _simulate_cell — the walk arm's "
            "alignment is unproven, refusing to report a difference table"
        )

    agg_walk = _aggregate_variant_results(walk_rows)
    walk_keys = set(keys_walk)
    paired = [k for k in keys_old if k in walk_keys]
    old_by_key = {k: r for k, r in zip(keys_old, pair_old)}
    walk_by_key = {k: r for k, r in zip(keys_walk, walk_rows)}
    mean_old_paired = _mean_rr([old_by_key[k] for k in paired])
    mean_walk_paired = _mean_rr([walk_by_key[k] for k in paired])

    block = {
        "n_simulate_exit": len(old_rows),
        "mean_rr_simulate_exit": _mean_rr(old_rows),
        "agg_simulate_exit": agg_old,
        "n_multi_tp_walk": len(walk_rows),
        "mean_rr_multi_tp_walk": _mean_rr(walk_rows),
        "agg_multi_tp_walk": agg_walk,
        "n_paired": len(paired),
        "mean_rr_simulate_exit_paired": mean_old_paired,
        "mean_rr_multi_tp_walk_paired": mean_walk_paired,
        "delta_paired": (round(mean_walk_paired - mean_old_paired, 4)
                         if (mean_old_paired is not None and mean_walk_paired is not None) else None),
        "n_walk_skipped": len(skipped),
        "walk_skipped": skipped[:20],
        "walk_outcome_hist": _reason_hist(walk_rows, "walk_outcome"),
        "walk_exit_reason_hist": _reason_hist(walk_rows, "exit_reason"),
    }
    return block, {"agg": agg_walk, "walk_by_key": walk_by_key}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instrument", default="BNBUSDT")
    ap.add_argument("--csv", default=None, help="default data/<INSTR>_M15.csv")
    ap.add_argument("--output-dir", default="results/execution_planner_replay")
    ap.add_argument("--htf-clock-basis", default=None, choices=["count", "calendar"],
                     help="Research-only override of BacktestConfig.htf_clock_basis "
                          "(backtest_v2.py:207). Default: leave as read from the active config.")
    args = ap.parse_args(argv)

    instrument = args.instrument
    csv = args.csv or f"data/{instrument}_M15.csv"
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # ── Gate corpus admission before any content is read ─────────────────────
    # Precedent: scripts/research/build_bar_matrix.py:375-396.
    # write_report=False is mandatory: concurrent or read-only runs must not collide on the
    # report file slot (corpus_gate.py:259-266).
    try:
        admission = admit_corpus(csv, instrument, write_report=False)
    except (DatasetAdmissionError, DatasetIntegrityError, FileNotFoundError) as exc:
        print(f"CORPUS ADMISSION REFUSED ({csv}, {instrument}): {exc}", file=sys.stderr)
        return 3

    if not admission.approved:
        print(
            f"CORPUS ADMISSION REFUSED ({csv}, {instrument}): decision={admission.decision} "
            f"reason={admission.reason}",
            file=sys.stderr,
        )
        return 3

    csv_admitted = admission.filepath
    declared_hash = (admission.file_hash or "").split(":")[-1]
    recomputed_hash = _sha256_file(csv_admitted)
    if declared_hash and declared_hash.lower() != recomputed_hash.lower():
        raise SystemExit(
            f"CORPUS INTEGRITY FAILURE: admitted file sha256 mismatch "
            f"(declared={declared_hash}, recomputed={recomputed_hash})"
        )

    # Candle-parity proof: fingerprint of requested-path load vs admitted-path load.
    # On an in-place admission (rewritten=False) both point to the same file; the fingerprint
    # proves the data the replay walks is bit-for-bit what the gate approved.
    candles = SLTPComparator.load_candles_from_csv(csv_admitted)
    candle_idx = {_norm_ts(c["timestamp"]): i for i, c in enumerate(candles)}
    admitted_fingerprint = _candles_fingerprint(candles)
    requested_fingerprint = _candles_fingerprint(SLTPComparator.load_candles_from_csv(csv))

    try:
        max_candles = int(get_prod_section("sl_tp_comparison").get("max_candles_per_trade", 100))
    except (RuntimeError, KeyError):
        max_candles = 100

    # 1) one deterministic backtest -> RETEST_REPLAY telemetry + real trades
    tel_path, trd_path, metrics = _run_backtest(instrument, csv_admitted, out / "_run", args.htf_clock_basis)
    replay = _load_replay(tel_path)
    if not replay:
        raise SystemExit("no RETEST_REPLAY records found — is the additive telemetry wired?")

    selected = [r for r in replay if r["accepted"]]
    rejected = [r for r in replay if not r["accepted"]]

    cells = {
        "A_selected_vanilla":   _aggregate_variant_results(_simulate_cell(selected, _vanilla_levels,   candle_idx, candles, max_candles)),
        "B_selected_structure": _aggregate_variant_results(_simulate_cell(selected, _structure_levels, candle_idx, candles, max_candles)),
        "C_rejected_vanilla":   _aggregate_variant_results(_simulate_cell(rejected, _vanilla_levels,   candle_idx, candles, max_candles)),
        "D_rejected_structure": _aggregate_variant_results(_simulate_cell(rejected, _structure_levels, candle_idx, candles, max_candles)),
    }
    exp = {k: v["expectancy_rr"] for k, v in cells.items()}
    attribution = compute_attribution(exp)
    by_reject_reason = compute_by_reject_reason(replay, candle_idx, candles, max_candles)

    # ── Trust gate = STRUCTURAL fidelity (not net-number match) ──────────────
    # All four cells share the simplified simulate_exit model (TP2>SL>TP1, no 0.5R trail,
    # no partial-TP, no costs), so the attribution deltas are apples-to-apples. The real
    # net +0.545R is a SEPARATE figure: it differs from cell B only by the trail/partial/cost
    # exit model, which is identical across cells and therefore cancels in every delta.
    # The harness is trustworthy iff (a) the selected set == the real executed trades, and
    # (b) the offline structure SL reconstruction reproduces the engine's recorded SL.
    real_rr = None
    sl_fidelity_mismatch = None
    if trd_path is not None:
        import csv as _csv
        rows = list(_csv.DictReader(open(trd_path, encoding="utf-8")))
        vals = []
        for row in rows:
            try:
                vals.append(float(row.get("pnl_rr_net")))
            except (TypeError, ValueError):
                pass
        real_rr = round(sum(vals) / len(vals), 4) if vals else None
        by_ts = {_norm_ts(t.get("opened_at", "")): t for t in rows}
        sl_fidelity_mismatch = 0
        for r in selected:
            t = by_ts.get(_norm_ts(r["timestamp"]))
            if not t:
                continue
            sl, _, _ = _structure_levels(r)
            try:
                if abs(sl - float(t["sl"])) > 1e-4:
                    sl_fidelity_mismatch += 1
            except (TypeError, ValueError, KeyError):
                pass

    cell_b = exp["B_selected_structure"]
    counts_ok = len(selected) == metrics.approved_trades and len(rejected) > 0
    fidelity_ok = (sl_fidelity_mismatch == 0)
    anchor_ok = counts_ok and fidelity_ok

    # dominant effect verdict
    sltp = (attribution["sltp_effect_on_selected"] + attribution["sltp_effect_on_rejected"]) / 2.0
    sel = (attribution["selection_effect_vanilla"] + attribution["selection_effect_structure"]) / 2.0
    dominant = "selection" if abs(sel) > abs(sltp) else "sl_tp_structure"

    payload = {
        "prod_version": PROD_VERSION,
        "instrument": instrument,
        "htf_clock_basis_override": args.htf_clock_basis,
        "seed": SEED,
        "max_candles": max_candles,
        "vanilla_def": {"sl_atr": VANILLA_SL_ATR, "tp_atr": VANILLA_TP_ATR},
        "counts": {
            "retest_total": len(replay),
            "selected": len(selected),
            "rejected": len(rejected),
            "reject_reasons": _reason_counts(rejected),
            "backtest_trades": metrics.approved_trades,
        },
        "cells": cells,
        "expectancy": {k: round(v, 4) for k, v in exp.items()},
        "attribution": attribution,
        "by_reject_reason": by_reject_reason,
        "anchors": {
            "cell_B_structure_selected_gross": cell_b,
            "real_executed_mean_rr_net": real_rr,
            "gross_vs_net_gap": (round(real_rr - cell_b, 4) if real_rr is not None else None),
            "_note": "cells are gross/simplified-exit (no trail/partial/cost); the gross-vs-net gap "
                     "is the trail+partial-TP+cost contribution, constant across cells.",
            "selected_eq_backtest_trades": counts_ok,
            "structure_sl_fidelity_mismatch": sl_fidelity_mismatch,
            "harness_trustworthy": anchor_ok,
        },
        "verdict": {
            "dominant_effect": dominant,
            "avg_sltp_effect": round(sltp, 4),
            "avg_selection_effect": round(sel, 4),
        },
    }
    (out / "replay_bnbusdt.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # ── Arm 2 (multi_tp_walk) companion run ──────────────────────────────────
    # Aggregates both arms side-by-side using the same records, slices and levels.
    w_block_A, w_meta_A = _walk_cell_block(selected, _vanilla_levels,   candle_idx, candles, max_candles)
    w_block_B, w_meta_B = _walk_cell_block(selected, _structure_levels, candle_idx, candles, max_candles)
    w_block_C, w_meta_C = _walk_cell_block(rejected, _vanilla_levels,   candle_idx, candles, max_candles)
    w_block_D, w_meta_D = _walk_cell_block(rejected, _structure_levels, candle_idx, candles, max_candles)
    walk_cells = {
        "A_selected_vanilla":   w_block_A,
        "B_selected_structure": w_block_B,
        "C_rejected_vanilla":   w_block_C,
        "D_rejected_structure": w_block_D,
    }
    exp_walk = {k: v["agg_multi_tp_walk"]["expectancy_rr"] for k, v in walk_cells.items()}
    walk_attribution = compute_attribution(exp_walk)
    walk_cell_b = exp_walk["B_selected_structure"]
    walk_sltp = (walk_attribution["sltp_effect_on_selected"] + walk_attribution["sltp_effect_on_rejected"]) / 2.0
    walk_sel = (walk_attribution["selection_effect_vanilla"] + walk_attribution["selection_effect_structure"]) / 2.0
    walk_dominant = "selection" if abs(walk_sel) > abs(walk_sltp) else "sl_tp_structure"
    by_reject_reason_walk = compute_by_reject_reason_walk(replay, candle_idx, candles, max_candles)

    compare_payload = {
        "prod_version": PROD_VERSION,
        "instrument": instrument,
        "htf_clock_basis_override": args.htf_clock_basis,
        "seed": SEED,
        "max_candles": max_candles,
        "corpus_admission": {
            "requested_csv": csv,
            "admitted_csv": csv_admitted,
            "dataset_id": admission.dataset_id,
            "decision": admission.decision,
            "bound": admission.bound,
            "rewritten": admission.rewritten,
            "declared_file_hash": admission.file_hash,
            "recomputed_file_hash": f"sha256:{recomputed_hash}",
            "fingerprint_requested_path": requested_fingerprint,
            "fingerprint_admitted_path": admitted_fingerprint,
            "fingerprints_identical": (requested_fingerprint == admitted_fingerprint),
        },
        "walk_arm_spec": {
            "kernel": "research.oracle.multi_tp_walk",
            "tie_break": WALK_TIE_BREAK,
            "partial_fraction": WALK_PARTIAL_FRACTION,
            "trail_fraction": WALK_TRAIL_FRACTION,
            "runner_stop_pricing": WALK_RUNNER_STOP_PRICING,
            "timeout_pricing": WALK_TIMEOUT_PRICING,
            "exit_reason_map": _WALK_REASON_MAP,
            "_mapping_note": "two-target object has no TP1-only terminal state; tp1_rate is structurally "
                             "0.0, and OUT_TP1_BE_STOP is counted under SL in the standard aggregate. "
                             "See walk_outcome_hist for un-collapsed counts.",
        },
        "counts": payload["counts"],
        "cells": walk_cells,
        "expectancy_simulate_exit": payload["expectancy"],
        "expectancy_multi_tp_walk": {k: round(v, 4) for k, v in exp_walk.items()},
        "attribution_simulate_exit": attribution,
        "attribution_multi_tp_walk": walk_attribution,
        "verdict_simulate_exit": payload["verdict"],
        "verdict_multi_tp_walk": {
            "dominant_effect": walk_dominant,
            "avg_sltp_effect": round(walk_sltp, 4),
            "avg_selection_effect": round(walk_sel, 4),
        },
        "trust_gate": {
            "real_executed_mean_rr_net": real_rr,
            "cell_B_simulate_exit": cell_b,
            "gap_simulate_exit": (round(real_rr - cell_b, 4) if real_rr is not None else None),
            "cell_B_multi_tp_walk": walk_cell_b,
            "gap_multi_tp_walk": (round(real_rr - walk_cell_b, 4) if real_rr is not None else None),
            "selected_eq_backtest_trades": counts_ok,
            "structure_sl_fidelity_mismatch": sl_fidelity_mismatch,
            "harness_trustworthy": anchor_ok,
        },
        "by_reject_reason_simulate_exit": by_reject_reason,
        "by_reject_reason_multi_tp_walk": by_reject_reason_walk,
    }
    compare_path = out / f"replay_walk_compare_{instrument}.json"
    compare_path.write_text(json.dumps(compare_payload, indent=2), encoding="utf-8")

    # human-readable summary
    print(f"=== Execution-Planner Replay — {instrument} ({PROD_VERSION}) ===")
    print(f"  corpus admission: {admission.dataset_id} decision={admission.decision} "
          f"rewritten={admission.rewritten} bound={admission.bound}")
    print(f"  fingerprints match: {requested_fingerprint == admitted_fingerprint} "
          f"({admitted_fingerprint['count']} candles, sha={admitted_fingerprint['ohlcv_sha256'][:16]}...)")
    print(f"  RETEST {len(replay)} = selected {len(selected)} + rejected {len(rejected)}  "
          f"(backtest trades={metrics.approved_trades})")
    print(f"  reject reasons: {payload['counts']['reject_reasons']}")
    print()
    print("  === ARM 1: simulate_exit (simplified: TP2>SL>TP1, no trail, no partial) ===")
    print("  2x2 expectancy (R):")
    print(f"                       vanilla      structure")
    print(f"    Selected      A {exp['A_selected_vanilla']:+.3f}   B {exp['B_selected_structure']:+.3f}")
    print(f"    Rejected      C {exp['C_rejected_vanilla']:+.3f}   D {exp['D_rejected_structure']:+.3f}")
    print(f"  attribution: {attribution}")
    print(f"  VERDICT: dominant effect = {dominant.upper()}  (selection {sel:+.3f} vs SL/TP {sltp:+.3f})")
    print()
    print("  === ARM 2: multi_tp_walk (SEM-017: 0.5 at TP1, 0.5 trail to half-way) ===")
    print("  2x2 expectancy (R):")
    print(f"                       vanilla      structure")
    print(f"    Selected      A {exp_walk['A_selected_vanilla']:+.3f}   B {exp_walk['B_selected_structure']:+.3f}")
    print(f"    Rejected      C {exp_walk['C_rejected_vanilla']:+.3f}   D {exp_walk['D_rejected_structure']:+.3f}")
    print(f"  attribution: {walk_attribution}")
    print(f"  VERDICT: dominant effect = {walk_dominant.upper()}  "
          f"(selection {walk_sel:+.3f} vs SL/TP {walk_sltp:+.3f})")
    print()
    print("  === SIDE-BY-SIDE EXIT COMPARISON ===")
    print(f"    {'cell':<24}{'n_old':>6}{'mean_old':>10}{'n_walk':>8}{'mean_walk':>11}"
          f"{'n_pair':>8}{'paired_delta':>14}")
    for k in ["A_selected_vanilla", "B_selected_structure", "C_rejected_vanilla", "D_rejected_structure"]:
        b = walk_cells[k]
        d_str = f"{b['delta_paired']:+.4f}" if b["delta_paired"] is not None else "n/a"
        print(f"    {k:<24}{b['n_simulate_exit']:>6}{b['mean_rr_simulate_exit']:>10.4f}"
              f"{b['n_multi_tp_walk']:>8}{b['mean_rr_multi_tp_walk']:>11.4f}"
              f"{b['n_paired']:>8}{d_str:>14}")
    print()
    print("  === TRUST GATES & CONTEXT ===")
    print(f"  selected==backtest_trades ({metrics.approved_trades})? {counts_ok}  "
          f"structure-SL fidelity mismatches={sl_fidelity_mismatch} -> {'OK' if anchor_ok else 'FAIL'}")
    print(f"  real executed mean net R: {real_rr}")
    print(f"  cell B simulate_exit gross: {cell_b:+.4f}  |  gap (net - gross) = "
          f"{(round(real_rr - cell_b, 4) if real_rr is not None else 'n/a')}")
    print(f"  cell B multi_tp_walk gross: {walk_cell_b:+.4f}  |  gap (net - gross) = "
          f"{(round(real_rr - walk_cell_b, 4) if real_rr is not None else 'n/a')}")
    print()
    print("  by_reject_reason (ARM 1 simulate_exit):")
    print(f"    {'reason':<18}{'n':>5}{'win_rate':>10}{'expectancy_rr':>16}{'avg_realized_rr':>18}")
    for reason, agg in sorted(by_reject_reason.items(), key=lambda kv: -kv[1]["total_trades"]):
        print(f"    {reason:<18}{agg['total_trades']:>5}{agg['win_rate']:>10.3f}"
              f"{agg['expectancy_rr']:>16.4f}{agg['avg_realized_rr']:>18.4f}")
    print()
    print("  by_reject_reason (ARM 2 multi_tp_walk):")
    print(f"    {'reason':<18}{'n':>5}{'win_rate':>10}{'expectancy_rr':>16}{'avg_realized_rr':>18}")
    for reason, agg in sorted(by_reject_reason_walk.items(), key=lambda kv: -kv[1]["total_trades"]):
        print(f"    {reason:<18}{agg['total_trades']:>5}{agg['win_rate']:>10.3f}"
              f"{agg['expectancy_rr']:>16.4f}{agg['avg_realized_rr']:>18.4f}")
    print(f"  wrote {out / 'replay_bnbusdt.json'}")
    print(f"  wrote {compare_path}")
    return 0 if anchor_ok else 2


def _reason_counts(records: list[dict]) -> dict:
    out: dict[str, int] = {}
    for r in records:
        k = r.get("reject_reason") or "none"
        out[k] = out.get(k, 0) + 1
    return out


def compute_by_reject_reason(
    replay: list[dict], candle_idx: dict, candles: list[dict], max_candles: int,
) -> dict:
    """Additive breakdown: forward-simulate EVERY RETEST candidate — accepted AND every
    rejected reason — under the SAME structure SL/TP (_structure_levels, the real build_trade
    formula). This is "force-approve every candidate" for the rejected buckets: each one is
    walked forward exactly as if it had opened a real trade. Buckets are apples-to-apples with
    each other and with the real executed trades (ACCEPTED bucket == cell B).

    Does not touch the existing A/B/C/D cells — those still lump all rejected candidates
    together for the 2x2 attribution. This is a separate, finer-grained view."""
    buckets: dict[str, list[dict]] = {}
    for r in replay:
        key = "ACCEPTED" if r["accepted"] else (r.get("reject_reason") or "UNKNOWN")
        buckets.setdefault(key, []).append(r)

    out: dict[str, dict] = {}
    for reason, records in buckets.items():
        sim = _simulate_cell(records, _structure_levels, candle_idx, candles, max_candles)
        agg = _aggregate_variant_results(sim)
        out[reason] = {
            "total_trades":   agg["total_trades"],
            "win_rate":       agg["win_rate"],
            "expectancy_rr":  agg["expectancy_rr"],
            "avg_realized_rr": agg["avg_realized_rr"],
            "tp1_rate":       agg["tp1_rate"],
            "tp2_rate":       agg["tp2_rate"],
            "sl_rate":        agg["sl_rate"],
            "timeout_rate":   agg["timeout_rate"],
        }
    return out


def compute_by_reject_reason_walk(
    replay: list[dict], candle_idx: dict, candles: list[dict], max_candles: int,
) -> dict:
    """Same buckets as compute_by_reject_reason, but simulated under SEM-017 multi_tp_walk."""
    buckets: dict[str, list[dict]] = {}
    for r in replay:
        key = "ACCEPTED" if r["accepted"] else (r.get("reject_reason") or "UNKNOWN")
        buckets.setdefault(key, []).append(r)

    out: dict[str, dict] = {}
    for reason, records in buckets.items():
        _, walk_rows, _, _, skipped = _simulate_cell_pair(
            records, _structure_levels, candle_idx, candles, max_candles)
        agg = _aggregate_variant_results(walk_rows)
        out[reason] = {
            "total_trades":   agg["total_trades"],
            "win_rate":       agg["win_rate"],
            "expectancy_rr":  agg["expectancy_rr"],
            "avg_realized_rr": agg["avg_realized_rr"],
            "tp1_rate":       agg["tp1_rate"],
            "tp2_rate":       agg["tp2_rate"],
            "sl_rate":        agg["sl_rate"],
            "timeout_rate":   agg["timeout_rate"],
            "n_walk_skipped": len(skipped),
            "walk_outcome_hist": _reason_hist(walk_rows, "walk_outcome"),
        }
    return out


if __name__ == "__main__":
    sys.exit(main())
