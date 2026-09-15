# -*- coding: utf-8 -*-
"""transition_information.py — Stage-1 information gate for Program 4b/4c/4d (thin CLI).

Non-directional: does the M15∧H1∧H4 candle-state CONJUNCTION carry information about a forward
event (vol/range expansion · state persistence · compression→expansion transition)? Measured with
the audited information-gain primitive + label-permutation test, then put through the three FROZEN
robustness gates (stability 2024→2025 · half-life · cross-market). See
docs/research/preregistration-program-4bcd.md.

AUTHORITY: research/docs only (§6.5). Stage 1 PASS earns a Stage-2 economic test
(qualify_transitions.py) — never sizing/fusion. MEASURE-ONLY: no spine/config edits, no promotion.
Deterministic body (no wall-clock); the run manifest (timestamp/git) is written separately.

Usage:
    python scripts/research/transition_information.py
    python scripts/research/transition_information.py --permutations 2000 --out results/research/candle_state
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
from research.candle_state.mtf_conjunction import MultiTFConjunctionBuilder  # noqa: E402
from research.candle_state.transition_target import (                  # noqa: E402
    atr_per_bar, persistence_target, regime_transition_target,
    range_expansion_target, vol_expansion_target,
)
from utils.console_safe import safe_print                              # noqa: E402

CRYPTO = ["BNBUSDT", "ETHUSDT", "BTCUSDT", "SOLUSDT"]
FX = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "EURCAD"]   # XAUUSD excluded (F-035 holiday gap)
HORIZONS = [1, 2, 4, 8]
K_DECISION = 4
THETA = 1.5
ATR_PERIOD = 14
PROGRAMS = ("4b_vol_expansion", "4b_range_expansion", "4c_persistence", "4d_regime_transition")


def _load(symbol: str) -> list:
    from runtime.backtest_v2 import CandleLoader
    path = _ROOT / "data" / f"{symbol}_M15.csv"
    candles = list(CandleLoader(str(path), symbol).stream())
    for i, c in enumerate(candles):
        c.index = i
    return candles


def _targets(candles, atrs, keys, m15_vol, k):
    """Return {program: (target, valid)} at horizon k."""
    return {
        "4b_vol_expansion": vol_expansion_target(atrs, k=k, theta=THETA),
        "4b_range_expansion": range_expansion_target(candles, k=k, theta=THETA),
        "4c_persistence": persistence_target(keys, k=k),
        "4d_regime_transition": regime_transition_target(m15_vol, k=k),
    }


def _analyze(symbol: str, candles, builder, n_perm: int) -> dict:
    keys = builder.key_series(candles)
    atrs = atr_per_bar(candles, ATR_PERIOD)
    # M15 vol axis parsed from the conjunction key ("M15=DIR/VOL|...").
    m15_vol = [k.split("|")[0].split("=")[1].split("/")[1] for k in keys]
    years = np.asarray([c.timestamp.year for c in candles], dtype=int)

    per_program: dict[str, dict] = {}
    for prog in PROGRAMS:
        ig_curve: dict[int, float] = {}
        for k in HORIZONS:
            tgt, val = _targets(candles, atrs, keys, m15_vol, k)[prog]
            ig_curve[k] = information_gain(keys, tgt, val)

        # decision horizon: permutation significance + stability (2024 train -> 2025 test)
        tdec, vdec = _targets(candles, atrs, keys, m15_vol, K_DECISION)[prog]
        p = permutation_p(keys, tdec, vdec, n_permutations=n_perm,
                          name=f"transition:{prog}:{symbol}:k{K_DECISION}")
        train_valid = vdec & (years == 2024)
        test_valid = vdec & (years == 2025)
        stab = mi_stability(keys, tdec, train_valid, keys, tdec, test_valid)
        half = info_half_life(ig_curve)
        n_dec = int(vdec.sum())
        per_program[prog] = {
            "n_decision": n_dec,
            "ig_curve": {str(k): round(v, 6) for k, v in ig_curve.items()},
            "decision_p_value": round(p, 6),
            "decision_significant": bool(p <= 0.05),
            "half_life": half,
            "stability": stab,
            # Stage-1 PASS requires ALL frozen gates (see pre-registration).
            "stage1_pass": bool(p <= 0.05 and half["passed"] and stab["passed"] and n_dec >= 30),
        }
    return {"n_bars": len(candles), "programs": per_program}


def _pooled(symbols: list[str], loaded: dict, builder, n_perm: int, label: str) -> dict:
    """Pool conjunction cells + targets across a group (cells are instrument-agnostic tokens)."""
    all_keys: list[str] = []
    dec: dict[str, list] = {p: [] for p in PROGRAMS}
    dec_valid: dict[str, list] = {p: [] for p in PROGRAMS}
    years_all: list[int] = []
    curve_acc: dict[str, dict[int, list]] = {p: {k: [] for k in HORIZONS} for p in PROGRAMS}
    curve_val: dict[str, dict[int, list]] = {p: {k: [] for k in HORIZONS} for p in PROGRAMS}

    for sym in symbols:
        candles = loaded[sym]
        keys = builder.key_series(candles)
        atrs = atr_per_bar(candles, ATR_PERIOD)
        m15_vol = [k.split("|")[0].split("=")[1].split("/")[1] for k in keys]
        all_keys.extend(keys)
        years_all.extend(c.timestamp.year for c in candles)
        for prog in PROGRAMS:
            td, vd = _targets(candles, atrs, keys, m15_vol, K_DECISION)[prog]
            dec[prog].extend(td.tolist())
            dec_valid[prog].extend(vd.tolist())
            for k in HORIZONS:
                tk, vk = _targets(candles, atrs, keys, m15_vol, k)[prog]
                curve_acc[prog][k].extend(tk.tolist())
                curve_val[prog][k].extend(vk.tolist())

    years_arr = np.asarray(years_all, dtype=int)
    out: dict[str, dict] = {}
    for prog in PROGRAMS:
        td = np.asarray(dec[prog], dtype=np.int64)
        vd = np.asarray(dec_valid[prog], dtype=bool)
        ig_curve = {k: information_gain(all_keys, np.asarray(curve_acc[prog][k], dtype=np.int64),
                                        np.asarray(curve_val[prog][k], dtype=bool)) for k in HORIZONS}
        p = permutation_p(all_keys, td, vd, n_permutations=n_perm,
                          name=f"transition:pooled:{label}:{prog}")
        stab = mi_stability(all_keys, td, vd & (years_arr == 2024),
                            all_keys, td, vd & (years_arr == 2025))
        half = info_half_life(ig_curve)
        n_dec = int(vd.sum())
        out[prog] = {
            "n_decision": n_dec,
            "ig_curve": {str(k): round(v, 6) for k, v in ig_curve.items()},
            "decision_p_value": round(p, 6),
            "decision_significant": bool(p <= 0.05),
            "half_life": half,
            "stability": stab,
            "stage1_pass": bool(p <= 0.05 and half["passed"] and stab["passed"] and n_dec >= 30),
        }
    return out


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="transition_information",
                                 description="Stage-1 information gate (Program 4b/4c/4d)")
    ap.add_argument("--permutations", type=int, default=2000)
    ap.add_argument("--out", default="results/research/candle_state")
    args = ap.parse_args(argv)

    builder = MultiTFConjunctionBuilder(CandleStateEncoder(atr_period=ATR_PERIOD))

    loaded = {sym: _load(sym) for sym in CRYPTO + FX}
    per_instrument: dict[str, dict] = {}
    for sym in CRYPTO + FX:
        safe_print(f"  analyzing {sym} ...")
        per_instrument[sym] = _analyze(sym, loaded[sym], builder, args.permutations)

    crypto_pool = _pooled(CRYPTO, loaded, builder, args.permutations, "crypto")
    fx_pool = _pooled(FX, loaded, builder, args.permutations, "fx")

    # Cross-market verdict per program (pooled-group Stage-1 pass).
    cross: dict[str, str] = {}
    for prog in PROGRAMS:
        cross[prog] = cross_market(crypto_pool[prog]["stage1_pass"], fx_pool[prog]["stage1_pass"])

    body = {
        "frozen_thresholds": {"permutation_alpha": 0.05, "mi_retention_min": 0.5,
                              "half_life_min_bars": 4, "theta": THETA, "k_decision": K_DECISION},
        "permutations": args.permutations,
        "horizons": HORIZONS,
        "crypto_symbols": CRYPTO,
        "fx_symbols": FX,
        "per_instrument": per_instrument,
        "pooled": {"crypto": crypto_pool, "fx": fx_pool},
        "cross_market": cross,
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "transition_information.json").write_text(
        json.dumps(body, sort_keys=True, indent=2), encoding="utf-8")
    (out_dir / "transition_information_manifest.json").write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                    "git_commit": _git_commit()}, sort_keys=True, indent=2), encoding="utf-8")

    # Console summary.
    safe_print("\nSTAGE-1 INFORMATION GATE — pooled cross-market verdict (frozen thresholds)\n")
    safe_print(f"| {'Program':22s} | {'crypto p':>9s} | {'crypto HL':>9s} | {'crypto ret':>10s} | "
               f"{'fx p':>8s} | {'verdict':14s} |")
    for prog in PROGRAMS:
        c, f = crypto_pool[prog], fx_pool[prog]
        safe_print(f"| {prog:22s} | {c['decision_p_value']:9.4f} | "
                   f"{c['half_life']['half_life_bars']:9d} | {c['stability']['retention']:10.3f} | "
                   f"{f['decision_p_value']:8.4f} | {cross[prog]:14s} |")
    any_pass = any(v != "REJECTED" for v in cross.values())
    safe_print(f"\nStage-1 survivors (-> Stage 2): "
               f"{[p for p in PROGRAMS if cross[p] != 'REJECTED'] or 'none'}")
    safe_print(f"-> {out_dir / 'transition_information.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
