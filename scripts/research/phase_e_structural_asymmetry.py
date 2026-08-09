# -*- coding: utf-8 -*-
"""
phase_e_structural_asymmetry.py — Program 2 / Phase E1 (thin CLI driver).

Does the COMPLETED sweep→displacement→retest structure possess forward asymmetry beyond sweep alone?
PURE measurement — multi-horizon MFE/MAE + symmetric first-hit, no SL/TP/RR/expectancy. Pipeline:
  E1.0 funnel + transition probabilities + power  →  E1.1 MFE/MAE  →  E1.2 barrier races  →
  E1.3 four controls (A random / B session / C vol / D sweep-only)  →  E1.4 permutation  →
  E1.5 planted-asymmetry calibration (in-pipeline)  →  E1.6 OOS + conjunctive four-way verdict + POWER.

FROZEN: no conditioning (regime/HTF/session is E2), no threshold search, no profitability. The four-way
verdict (ASYMMETRY_SURVIVES / LOSES_TO_SWEEP_ONLY / NULL_ADEQUATE_POWER / INSUFFICIENT_POWER) + an
orthogonal POWER flag ensure insufficient N is never reported as "no asymmetry."

Deterministic JSON body (no wall-clock); manifest separate. Usage:
    python scripts/research/phase_e_structural_asymmetry.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
for _p in (str(_ROOT), str(_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                                                       # noqa: E402

from research.adapters.structural_event_source import harvest, StructuralEvent  # noqa: E402
from research.conditional_entropy_grid import hour_of, hour_to_session, vol_terciles, vol_label  # noqa: E402
from research.structural_asymmetry import (                              # noqa: E402
    aggregate, measure_path, permutation_vs_control, seed_for, PathMeasure,
)
from utils.console_safe import safe_print                              # noqa: E402

DEFAULT_CONFIG = "configs/research/research_config_phase_e.json"
_SESSION_WINDOWS = {"ASIA": [0, 7], "LONDON": [7, 13], "NEWYORK": [13, 21], "OFF": [21, 24]}


def _measure_events(events, candles, horizons, levels, hmax) -> list[PathMeasure]:
    out = []
    n = len(candles)
    for e in events:
        i = e.entry_index
        if e.atr <= 0 or i + 1 >= n:
            continue
        fut = candles[i + 1:i + 1 + hmax]
        if not fut:
            continue
        out.append(measure_path(e.entry, e.direction, e.atr, fut, horizons=horizons, levels=levels))
    return out


def _measure_idx_dir(pairs, candles, horizons, levels, hmax, atr_of) -> list[PathMeasure]:
    out = []
    n = len(candles)
    for i, direction in pairs:
        a = atr_of(i)
        if a <= 0 or i + 1 >= n:
            continue
        fut = candles[i + 1:i + 1 + hmax]
        if not fut:
            continue
        out.append(measure_path(float(candles[i].close), direction, a, fut, horizons=horizons, levels=levels))
    return out


def _calibration(planted_p_plus, n, horizons, levels) -> dict:
    """E1.5 — inject a synthetic population with known first-hit drift; verify the pipeline recovers it."""
    n_plus = int(round(planted_p_plus * n))
    pop = []
    for k in range(n):
        sign = +1 if k < n_plus else -1
        pop.append(PathMeasure(mfe_r={h: (1.0 if sign > 0 else 0.0) for h in horizons},
                               mae_r={h: (0.0 if sign > 0 else -1.0) for h in horizons},
                               first_hit={L: sign for L in levels}))
    agg = aggregate(pop, horizons=horizons, levels=levels)
    recovered = agg["first_hit"][str(levels[len(levels) // 2])]["p_plus"]
    return {"planted_p_plus": planted_p_plus, "recovered_p_plus": recovered}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phase_e_structural_asymmetry")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--out", default="results/research/phase_e")
    args = parser.parse_args(argv)

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    inst = cfg["instrument"]
    csv = str(Path(cfg["data_dir"]) / f"{inst}_M15.csv")
    m = cfg["measure"]
    horizons = list(m["horizons"]); levels = list(m["levels"])
    H = int(m["primary_horizon"]); L = float(m["primary_level"]); hmax = max(horizons)
    alpha = float(cfg["significance"]["alpha"]); nperm = int(cfg["significance"]["n_permutations"])
    oos_split = float(cfg["oos"]["split"]); power_ci_max = float(cfg["power"]["ci_max"])
    atr_period = int(cfg["atr_period"])

    out_root = Path(args.out)
    events, funnel, candles = harvest(inst, csv, out_root, atr_period=atr_period)
    n = len(candles)

    def atr_of(i):
        from research.indicators import atr as _a
        return _a(candles[max(0, i - atr_period):i + 1], atr_period)

    # ── populations ──
    test = [e for e in events if e.stage == "RETEST"]
    sweep_only = [e for e in events if e.stage == "SWEEP" and not e.completed]
    safe_print(f"  {inst}: retests(completed)={len(test)} sweep_only={len(sweep_only)} "
               f"funnel={funnel}")

    # per-bar features for matched controls
    valid = list(range(atr_period + 1, n - hmax - 1))
    atrs = np.array([atr_of(i) for i in valid], dtype=float)
    lo, hi = vol_terciles(atrs)
    sess = {i: hour_to_session(hour_of(candles[i].timestamp), _SESSION_WINDOWS) for i in valid}
    vol = {i: vol_label(atr_of(i), lo, hi) for i in valid}
    rng = np.random.default_rng(int(cfg["controls"]["seed"]))

    def _rand_in(pool):
        return int(pool[rng.integers(0, len(pool))]) if pool else None

    by_sess = {}
    by_vol = {}
    for i in valid:
        by_sess.setdefault(sess[i], []).append(i)
        by_vol.setdefault(vol[i], []).append(i)

    test_idx_dir = [(e.entry_index, e.direction) for e in test
                    if e.atr > 0 and e.entry_index in set(valid)]
    # Control A: random bar, same direction (paired). B: same session. C: same vol-tercile.
    ctrl_A, ctrl_B, ctrl_C = [], [], []
    for i, d in test_idx_dir:
        ctrl_A.append((_rand_in(valid), d))
        ctrl_B.append((_rand_in(by_sess.get(sess.get(i, "OFF"), valid)), d))
        ctrl_C.append((_rand_in(by_vol.get(vol.get(i, "N"), valid)), d))
    ctrl_A = [(i, d) for i, d in ctrl_A if i is not None]
    ctrl_B = [(i, d) for i, d in ctrl_B if i is not None]
    ctrl_C = [(i, d) for i, d in ctrl_C if i is not None]

    # ── measure ──
    M_test = _measure_events(test, candles, horizons, levels, hmax)
    M_D = _measure_events(sweep_only, candles, horizons, levels, hmax)
    M_A = _measure_idx_dir(ctrl_A, candles, horizons, levels, hmax, atr_of)
    M_B = _measure_idx_dir(ctrl_B, candles, horizons, levels, hmax, atr_of)
    M_C = _measure_idx_dir(ctrl_C, candles, horizons, levels, hmax, atr_of)
    controls = {"random_A": M_A, "session_B": M_B, "vol_C": M_C, "sweep_only_D": M_D}

    agg_test = aggregate(M_test, horizons=horizons, levels=levels)
    agg_ctrl = {k: aggregate(v, horizons=horizons, levels=levels) for k, v in controls.items()}

    # ── E1.4 permutation: test vs each control (primary H + L) ──
    tvc = {}
    for k, mc in controls.items():
        ex_obs, ex_p = permutation_vs_control(M_test, mc, stat="excursion", key=H,
                                              n_permutations=nperm, seed=seed_for("exc", k))
        fh_obs, fh_p = permutation_vs_control(M_test, mc, stat="first_hit", key=L,
                                              n_permutations=nperm, seed=seed_for("fh", k))
        tvc[k] = {"excursion": [ex_obs, round(ex_p, 6)], "first_hit": [fh_obs, round(fh_p, 6)]}

    # ── E1.5 calibration ──
    cal = _calibration(float(cfg["calibration"]["planted_p_plus"]), int(cfg["calibration"]["n"]),
                       horizons, levels)
    cal_ok = abs(cal["recovered_p_plus"] - cal["planted_p_plus"]) <= float(cfg["calibration"]["tolerance"])
    cal["passed"] = cal_ok

    # ── E1.6 OOS (chronological split of the test population, by event order) ──
    ev_sorted = sorted(test, key=lambda e: e.entry_index)
    cut = int(round(len(ev_sorted) * (1.0 - oos_split)))
    M_oos = _measure_events(ev_sorted[cut:], candles, horizons, levels, hmax)
    agg_oos = aggregate(M_oos, horizons=horizons, levels=levels)
    oos_exc = agg_oos["excursion"][str(H)]["asymmetry"]
    oos_fh = agg_oos["first_hit"][str(L)]["delta"]
    oos_ci = agg_oos["first_hit"][str(L)]["ci_halfwidth"]
    power = "ADEQUATE" if (oos_ci is not None and oos_ci <= power_ci_max) else "INADEQUATE"

    # ── verdict (conjunctive, four-way) ──
    exc_full = agg_test["excursion"][str(H)]["asymmetry"]
    fh_full = agg_test["first_hit"][str(L)]["delta"]
    exc_pos = exc_full > 0
    fh_pos = fh_full > 0

    def _beats(k):
        ex = tvc[k]["excursion"]; fh = tvc[k]["first_hit"]
        return ex[0] > 0 and ex[1] <= alpha and fh[0] > 0 and fh[1] <= alpha
    beats_D = _beats("sweep_only_D")
    beats_all = all(_beats(k) for k in controls)
    oos_stable = (oos_exc > 0 and oos_fh > 0)

    if exc_pos and fh_pos and beats_all and oos_stable and power == "ADEQUATE" and cal_ok:
        verdict = "ASYMMETRY_SURVIVES"
    elif (exc_pos or fh_pos) and not beats_D:
        verdict = "LOSES_TO_SWEEP_ONLY"
    elif power == "INADEQUATE":
        verdict = "INSUFFICIENT_POWER"
    else:
        verdict = "NULL_ADEQUATE_POWER"

    # ── funnel transition probabilities + power ──
    f = funnel
    def _p(a, b):
        return round(f.get(a, 0) / f.get(b), 6) if f.get(b) else None
    funnel_block = {
        "counts": f,
        "P_disp_given_sweep": _p("displacement", "sweep"),
        "P_retest_given_disp": _p("retest", "displacement"),
        "P_exec_given_retest": _p("execution", "retest"),
        "n_test_retests": len(M_test), "n_sweep_only": len(M_D),
        "primary_first_hit_ci_halfwidth_full":
            agg_test["first_hit"][str(L)]["ci_halfwidth"],
    }

    report = {
        "phase": "E1", "instrument": inst,
        "frozen": {"horizons": horizons, "levels": levels, "primary_horizon": H, "primary_level": L,
                   "n_permutations": nperm, "alpha": alpha, "oos_split": oos_split,
                   "power_ci_max": power_ci_max, "truth": "exit-agnostic MFE/MAE + first-hit; NO profitability"},
        "funnel": funnel_block,
        "test_retest": agg_test,
        "controls": agg_ctrl,
        "permutation_test_vs_control": tvc,
        "calibration": cal,
        "oos": {"excursion_asym": oos_exc, "first_hit_delta": oos_fh, "ci_halfwidth": oos_ci,
                "n": agg_oos["n"]},
        "verdict": verdict, "power": power,
        "summary": {"verdict": verdict, "power": power,
                    "excursion_asym_full": exc_full, "first_hit_delta_full": fh_full,
                    "beats_sweep_only_D": beats_D, "beats_all_controls": beats_all,
                    "oos_sign_stable": oos_stable, "calibration_passed": cal_ok},
    }
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "phase_e_structural_asymmetry.json").write_text(
        json.dumps(report, sort_keys=True, indent=2), encoding="utf-8")
    (out_root / "phase_e_manifest.json").write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                    "git_commit": _git_commit(), "config": args.config}, sort_keys=True, indent=2),
        encoding="utf-8")
    _print(report)
    safe_print(f"\n-> {out_root / 'phase_e_structural_asymmetry.json'}")
    return 0


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def _print(r: dict) -> None:
    fb = r["funnel"]; H = r["frozen"]["primary_horizon"]; L = r["frozen"]["primary_level"]
    safe_print("\nPHASE E1 — structural continuation asymmetry (PURE; no profitability)\n")
    safe_print(f"  FUNNEL {fb['counts']}  P(disp|sweep)={fb['P_disp_given_sweep']} "
               f"P(retest|disp)={fb['P_retest_given_disp']} P(exec|retest)={fb['P_exec_given_retest']}")
    safe_print(f"  N test_retests={fb['n_test_retests']}  sweep_only={fb['n_sweep_only']}")
    t = r["test_retest"]
    safe_print(f"  TEST  excursion_asym(h={H})={t['excursion'][str(H)]['asymmetry']:+.4f}  "
               f"first_hit_delta(L={L})={t['first_hit'][str(L)]['delta']:+.4f} "
               f"(p+={t['first_hit'][str(L)]['p_plus']:.3f} p-={t['first_hit'][str(L)]['p_minus']:.3f} "
               f"CI±{t['first_hit'][str(L)]['ci_halfwidth']})")
    for k, tvc in r["permutation_test_vs_control"].items():
        safe_print(f"    vs {k:14s}: exc Δ={tvc['excursion'][0]:+.4f} p={tvc['excursion'][1]:.4f} | "
                   f"firsthit Δ={tvc['first_hit'][0]:+.4f} p={tvc['first_hit'][1]:.4f}")
    o = r["oos"]
    safe_print(f"  OOS   excursion_asym={o['excursion_asym']:+.4f} first_hit_delta={o['first_hit_delta']:+.4f} "
               f"CI±{o['ci_halfwidth']} (n={o['n']})")
    c = r["calibration"]
    safe_print(f"  CALIBRATION planted={c['planted_p_plus']} recovered={c['recovered_p_plus']} "
               f"passed={c['passed']}")
    safe_print(f"\n  VERDICT: {r['verdict']} · POWER: {r['power']}")


if __name__ == "__main__":
    raise SystemExit(main())
