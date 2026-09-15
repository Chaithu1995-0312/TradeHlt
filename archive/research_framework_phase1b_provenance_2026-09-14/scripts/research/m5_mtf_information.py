# -*- coding: utf-8 -*-
"""m5_mtf_information.py — Stage-1 information gate for Program 9 (thin CLI).

Non-directional: does the M5-BASE conjunction (M5 state + last-closed M15/H1/H4 states)
carry information about a forward event (9a vol expansion · 9b range expansion · 9c
compression→expansion transition) — and, critically, INCREMENTAL information beyond the
M15-base conjunction causally available at the same M5 instant (Gate B, the F-043
within-coarse-cell permutation)? Frozen thresholds + verdict vocabulary (PASS /
M15_REDUNDANT / FAIL): docs/research/preregistration-program-9.md (pre-registered BEFORE
this driver ran; changing any threshold requires a NEW pre-registration).

Mirrors scripts/research/transition_information.py (the frozen Program-4 instrument,
untouched) with the Program-9 deltas: M5 base + ("M15","H1","H4") rules · wall-clock
horizon rescale {3,6,12,24}/k=12/half-life>=12 · chronological 50/50 stability split
(D5 — the calendar 2024/2025 split is impossible for the ~270d FX M5 retention) ·
Gate B incremental null · 6+6 universe (data/binance + data/mt5).

AUTHORITY: research/docs only (§6.5). Stage-1 PASS earns the Stage-2 economic test
(qualify_m5_straddle.py, sole consumer per D7) — never sizing/fusion. MEASURE-ONLY.
Deterministic body (no wall-clock); the run manifest (timestamp/git) is separate.

Usage:
    python scripts/research/m5_mtf_information.py
    python scripts/research/m5_mtf_information.py --permutations 2000 --out results/research/m5_mtf
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.candle_state.encoder import CandleStateEncoder           # noqa: E402
from research.candle_state.info_robustness import (                    # noqa: E402
    cross_market, info_half_life, information_gain, mi_stability, permutation_p,
)
from research.candle_state.m5_incremental import (                     # noqa: E402
    M5_BASE_LABEL, M5_HALF_LIFE_MIN_BARS, M5_HORIZONS, M5_K_DECISION, M5_RULES,
    VERDICT_PASS, coarse_key, stage1_verdict, within_coarse_permutation_p,
)
from research.candle_state.mtf_conjunction import MultiTFConjunctionBuilder  # noqa: E402
from research.candle_state.transition_target import (                  # noqa: E402
    atr_per_bar, range_expansion_target, regime_transition_target, vol_expansion_target,
)
from utils.console_safe import safe_print                              # noqa: E402

CRYPTO = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT"]
FX = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "EURCAD", "XAUUSD"]
GROUP_DIR = {**{s: "binance" for s in CRYPTO}, **{s: "mt5" for s in FX}}
THETA = 1.5
ATR_PERIOD = 14
PROGRAMS = ("9a_vol_expansion", "9b_range_expansion", "9c_regime_transition")


def _load(symbol: str) -> list:
    from runtime.backtest_v2 import CandleLoader
    path = _ROOT / "data" / GROUP_DIR[symbol] / f"{symbol}_M5.csv"
    candles = list(CandleLoader(str(path), symbol).stream())
    for i, c in enumerate(candles):
        c.index = i
    return candles


def _targets(candles, atrs, base_vol, k):
    """{program: (target, valid)} at horizon k. Targets = the unchanged Program-4 kernels."""
    return {
        "9a_vol_expansion": vol_expansion_target(atrs, k=k, theta=THETA),
        "9b_range_expansion": range_expansion_target(candles, k=k, theta=THETA),
        "9c_regime_transition": regime_transition_target(base_vol, k=k),
    }


def _chrono_split(valid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """D5: per-instrument chronological 50/50 split of the VALID decision bars."""
    idx = np.flatnonzero(valid)
    half = idx.size // 2
    train = np.zeros(valid.size, dtype=bool)
    test = np.zeros(valid.size, dtype=bool)
    train[idx[:half]] = True
    test[idx[half:]] = True
    return train, test


def _program_block(keys, coarse, candles, atrs, base_vol, prog, n_perm, name) -> dict:
    """Per-scope Stage-1 evaluation for one program (shared by per-instrument + pooled)."""
    ig_curve: dict[int, float] = {}
    for k in M5_HORIZONS:
        tgt, val = _targets(candles, atrs, base_vol, k)[prog]
        ig_curve[k] = information_gain(keys, tgt, val)

    tdec, vdec = _targets(candles, atrs, base_vol, M5_K_DECISION)[prog]
    p_raw = permutation_p(keys, tdec, vdec, n_permutations=n_perm, name=f"{name}:raw")
    p_inc = within_coarse_permutation_p(keys, coarse, tdec, vdec,
                                        n_permutations=n_perm, name=f"{name}:inc")
    train_valid, test_valid = _chrono_split(vdec)          # D5 chronological 50/50
    stab = mi_stability(keys, tdec, train_valid, keys, tdec, test_valid)
    half = info_half_life(ig_curve, min_bars=M5_HALF_LIFE_MIN_BARS)
    n_dec = int(vdec.sum())
    gate_a = bool(p_raw <= 0.05 and half["passed"] and stab["passed"] and n_dec >= 30)
    verdict = stage1_verdict(gate_a, p_inc)
    return {
        "n_decision": n_dec,
        "ig_curve": {str(k): round(v, 6) for k, v in ig_curve.items()},
        "decision_p_value": round(p_raw, 6),
        "decision_significant": bool(p_raw <= 0.05),
        "incremental_p_value": round(p_inc, 6),
        "incremental_significant": bool(p_inc <= 0.05),
        "half_life": half,
        "stability": stab,
        "gate_a_pass": gate_a,
        # Stage-1 verdict per pre-reg D6: PASS / M15_REDUNDANT / FAIL.
        "verdict": verdict,
        "stage1_pass": bool(verdict == VERDICT_PASS),
    }


def _analyze(symbol: str, candles, builder, n_perm: int) -> dict:
    keys = builder.key_series(candles)
    coarse = [coarse_key(k) for k in keys]
    atrs = atr_per_bar(candles, ATR_PERIOD)
    # M5 vol axis parsed from the conjunction key ("M5=DIR/VOL|...").
    base_vol = [k.split("|")[0].split("=")[1].split("/")[1] for k in keys]

    per_program: dict[str, dict] = {}
    for prog in PROGRAMS:
        per_program[prog] = _program_block(
            keys, coarse, candles, atrs, base_vol, prog, n_perm,
            name=f"m5mtf:{prog}:{symbol}:k{M5_K_DECISION}")
    return {"n_bars": len(candles), "programs": per_program}


def _pooled(symbols: list[str], loaded: dict, builder, n_perm: int, label: str) -> dict:
    """Pool conjunction cells + targets across a group. The D5 stability split stays
    PER-INSTRUMENT chronological (each instrument contributes its own halves)."""
    all_keys: list[str] = []
    all_coarse: list[str] = []
    dec: dict[str, list] = {p: [] for p in PROGRAMS}
    dec_valid: dict[str, list] = {p: [] for p in PROGRAMS}
    train_m: dict[str, list] = {p: [] for p in PROGRAMS}
    test_m: dict[str, list] = {p: [] for p in PROGRAMS}
    curve_acc: dict[str, dict[int, list]] = {p: {k: [] for k in M5_HORIZONS} for p in PROGRAMS}
    curve_val: dict[str, dict[int, list]] = {p: {k: [] for k in M5_HORIZONS} for p in PROGRAMS}

    for sym in symbols:
        candles = loaded[sym]
        keys = builder.key_series(candles)
        coarse = [coarse_key(k) for k in keys]
        atrs = atr_per_bar(candles, ATR_PERIOD)
        base_vol = [k.split("|")[0].split("=")[1].split("/")[1] for k in keys]
        all_keys.extend(keys)
        all_coarse.extend(coarse)
        for prog in PROGRAMS:
            td, vd = _targets(candles, atrs, base_vol, M5_K_DECISION)[prog]
            tr, te = _chrono_split(vd)
            dec[prog].extend(td.tolist())
            dec_valid[prog].extend(vd.tolist())
            train_m[prog].extend(tr.tolist())
            test_m[prog].extend(te.tolist())
            for k in M5_HORIZONS:
                tk, vk = _targets(candles, atrs, base_vol, k)[prog]
                curve_acc[prog][k].extend(tk.tolist())
                curve_val[prog][k].extend(vk.tolist())

    out: dict[str, dict] = {}
    for prog in PROGRAMS:
        td = np.asarray(dec[prog], dtype=np.int64)
        vd = np.asarray(dec_valid[prog], dtype=bool)
        ig_curve = {k: information_gain(all_keys, np.asarray(curve_acc[prog][k], dtype=np.int64),
                                        np.asarray(curve_val[prog][k], dtype=bool))
                    for k in M5_HORIZONS}
        p_raw = permutation_p(all_keys, td, vd, n_permutations=n_perm,
                              name=f"m5mtf:pooled:{label}:{prog}:raw")
        p_inc = within_coarse_permutation_p(all_keys, all_coarse, td, vd,
                                            n_permutations=n_perm,
                                            name=f"m5mtf:pooled:{label}:{prog}:inc")
        stab = mi_stability(all_keys, td, np.asarray(train_m[prog], dtype=bool),
                            all_keys, td, np.asarray(test_m[prog], dtype=bool))
        half = info_half_life(ig_curve, min_bars=M5_HALF_LIFE_MIN_BARS)
        n_dec = int(vd.sum())
        gate_a = bool(p_raw <= 0.05 and half["passed"] and stab["passed"] and n_dec >= 30)
        verdict = stage1_verdict(gate_a, p_inc)
        out[prog] = {
            "n_decision": n_dec,
            "ig_curve": {str(k): round(v, 6) for k, v in ig_curve.items()},
            "decision_p_value": round(p_raw, 6),
            "decision_significant": bool(p_raw <= 0.05),
            "incremental_p_value": round(p_inc, 6),
            "incremental_significant": bool(p_inc <= 0.05),
            "half_life": half,
            "stability": stab,
            "gate_a_pass": gate_a,
            "verdict": verdict,
            "stage1_pass": bool(verdict == VERDICT_PASS),
        }
    return out


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="m5_mtf_information",
                                 description="Stage-1 information gate (Program 9)")
    ap.add_argument("--permutations", type=int, default=2000)
    ap.add_argument("--out", default="results/research/m5_mtf")
    args = ap.parse_args(argv)

    builder = MultiTFConjunctionBuilder(
        CandleStateEncoder(atr_period=ATR_PERIOD),
        rules=M5_RULES, base_label=M5_BASE_LABEL)

    loaded = {sym: _load(sym) for sym in CRYPTO + FX}
    per_instrument: dict[str, dict] = {}
    for sym in CRYPTO + FX:
        safe_print(f"  analyzing {sym} ...")
        per_instrument[sym] = _analyze(sym, loaded[sym], builder, args.permutations)

    safe_print("  pooling crypto ...")
    crypto_pool = _pooled(CRYPTO, loaded, builder, args.permutations, "crypto")
    safe_print("  pooling fx ...")
    fx_pool = _pooled(FX, loaded, builder, args.permutations, "fx")

    # Cross-market verdict per program (pooled-group Stage-1 A-AND-B pass).
    cross: dict[str, str] = {}
    for prog in PROGRAMS:
        cross[prog] = cross_market(crypto_pool[prog]["stage1_pass"], fx_pool[prog]["stage1_pass"])

    body = {
        "preregistration": "docs/research/preregistration-program-9.md",
        "frozen_thresholds": {
            "permutation_alpha": 0.05, "mi_retention_min": 0.5,
            "half_life_min_bars": M5_HALF_LIFE_MIN_BARS, "theta": THETA,
            "k_decision": M5_K_DECISION,
            "incremental_gate": "within-K15-cell permutation p <= 0.05 (Gate B, D6)",
            "stability_split": "per-instrument chronological 50/50 of valid decision bars (D5)",
        },
        "permutations": args.permutations,
        "horizons": M5_HORIZONS,
        "base_label": M5_BASE_LABEL,
        "rules": list(M5_RULES),
        "crypto_symbols": CRYPTO,
        "fx_symbols": FX,
        "per_instrument": per_instrument,
        "pooled": {"crypto": crypto_pool, "fx": fx_pool},
        "cross_market": cross,
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "m5_mtf_information.json").write_text(
        json.dumps(body, sort_keys=True, indent=2), encoding="utf-8")
    (out_dir / "m5_mtf_information_manifest.json").write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                    "git_commit": _git_commit()}, sort_keys=True, indent=2), encoding="utf-8")

    # Console summary.
    safe_print("\nSTAGE-1 (Program 9) — pooled cross-market verdicts (frozen thresholds)\n")
    safe_print(f"| {'Program':22s} | {'crypto p':>9s} | {'crypto inc-p':>12s} | {'crypto verdict':>14s} | "
               f"{'fx p':>8s} | {'fx inc-p':>9s} | {'fx verdict':>14s} | {'cross':14s} |")
    for prog in PROGRAMS:
        c, f = crypto_pool[prog], fx_pool[prog]
        safe_print(f"| {prog:22s} | {c['decision_p_value']:9.4f} | {c['incremental_p_value']:12.4f} | "
                   f"{c['verdict']:>14s} | {f['decision_p_value']:8.4f} | "
                   f"{f['incremental_p_value']:9.4f} | {f['verdict']:>14s} | {cross[prog]:14s} |")
    safe_print(f"\nStage-1 survivors (-> Stage 2 per D7): "
               f"{[p for p in PROGRAMS if cross[p] != 'REJECTED'] or 'none'}")
    safe_print(f"-> {out_dir / 'm5_mtf_information.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
