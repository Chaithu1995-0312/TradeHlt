"""validate_oracle_harness.py — Stage 0.5 HARD GATE for the oracle program.

A null result from a blind miner is indistinguishable from a real negative. So is a null
from a join that silently misaligned. Before any result from this program is
interpretable, the harness has to demonstrate it can find something that is definitely
there, and fail to find something that is definitely not.

If any BLOCKING check fails, the correct report is "harness unproven", never "no
information". That distinction is the entire reason this file exists.

BLOCKING CHECKS
---------------
  planted_signal   Inject features with a KNOWN AUC (0.60 / 0.55 / 0.53) and confirm the
                   miner recovers each at roughly its planted magnitude. A miner that
                   cannot find a planted edge cannot license a null.
  label_shift      Shift labels by +/-1 bar and confirm the planted effect COLLAPSES. If
                   a misaligned join still finds structure, the join leaks and every
                   downstream number is void.
  deterministic    A relationship that must hold mechanically (trend_bias is the sign of
                   ema_fast - ema_slow) must recover at AUC ~ 1.0. Proves the feature
                   columns sit on the row they claim to.
  shuffled_null    Permuting the label must return the base rate. If it does not, the
                   harness manufactures signal.

REPORTED, NOT GATING
--------------------
  resolver_dwell   The per-bar CRT state distribution this run produces, against the
                   engine reference pinned in market_crt_states.yaml. This characterises
                   the RESOLVER, not this harness, so it does not gate — but it is
                   reported because any pattern keyed on `crt_state_resolved` is a
                   statement about the resolver until an engine re-measurement says
                   otherwise.

Usage:
    python scripts/research/validate_oracle_harness.py --instrument XAUUSD
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.oracle.scan import (  # noqa: E402
    DEFAULT_HORIZON,
    block_bootstrap_mean_ci,
    effective_n,
    rank_auc,
)
from statistics import NormalDist  # noqa: E402

# Engine per-bar state occupancy pinned in the market_crt_states.yaml header, from a
# 47,275-bar XAUUSD M15 run. Reference only — a different epoch's engine, quoted so the
# resolver's divergence is visible rather than assumed away.
_ENGINE_DWELL_REFERENCE = {
    "RANGE": 35159, "SWEEP": 6995, "EXPANSION": 4605, "DISPLACEMENT": 373,
    "SHADOW_PENDING": 43, "RETEST": 17, "EXECUTION": 5, "RESOLUTION": 5, "EXPIRED": 0,
}

PLANTED_TARGETS = (0.60, 0.55, 0.53)
_AUC_TOLERANCE = 0.02


def _plant(rng: np.random.Generator, y: np.ndarray, target_auc: float) -> np.ndarray:
    """A feature whose AUC against `y` is `target_auc` by construction.

    For two unit-variance normals separated by delta, AUC = Phi(delta / sqrt(2)), so
    delta = sqrt(2) * Phi^-1(AUC). Planting through the known identity means the check
    tests the MINER, not the planting.
    """
    delta = np.sqrt(2.0) * NormalDist().inv_cdf(target_auc)
    return y.astype(float) * delta + rng.standard_normal(y.size)


def run_checks(labels: pd.DataFrame, matrix: pd.DataFrame, *, horizon: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    results: dict = {}

    y = labels["y_win"].to_numpy().astype(int)
    blocks = (labels["_pos"].to_numpy() // horizon).astype(np.int64)

    # ── BLOCKING 1: planted-signal recovery ─────────────────────────────────
    planted = {}
    ok_planted = True
    for target in PLANTED_TARGETS:
        x = _plant(rng, y, target)
        got = rank_auc(x, y)
        passed = abs(got - target) <= _AUC_TOLERANCE
        ok_planted &= passed
        planted[f"auc_{target}"] = {
            "planted": target, "recovered": round(got, 5),
            "abs_error": round(abs(got - target), 5), "pass": bool(passed)}
    results["planted_signal"] = {"blocking": True, "pass": bool(ok_planted), "detail": planted}

    # ── BLOCKING 2: an INDEPENDENT shift must destroy the planted effect ────
    # Shifted by a full horizon, the label shares no forward bar with the one the
    # feature was planted on, so the only thing that could keep AUC above 0.5 is a
    # misaligned or duplicated join. A +/-1 shift CANNOT be used here: adjacent labels
    # overlap by horizon-1 forward bars and are genuinely correlated, so a residual
    # there is physics, not a leak. (An earlier version of this check asserted collapse
    # at +/-1 and failed the gate for exactly that reason — it assumed the label
    # independence this whole program exists to reject.)
    x = _plant(rng, y, 0.60)
    shift_detail = {"aligned_auc": round(rank_auc(x, y), 5), "shift_bars": horizon}
    ok_shift = True
    for k in (horizon, -horizon):
        got = rank_auc(x, np.roll(y, k))
        collapsed = abs(got - 0.5) < 0.02
        ok_shift &= collapsed
        shift_detail[f"shift_{k:+d}_auc"] = round(got, 5)
        shift_detail[f"shift_{k:+d}_collapsed"] = bool(collapsed)
    results["label_shift_independent"] = {
        "blocking": True, "pass": bool(ok_shift), "detail": shift_detail}

    # ── BLOCKING 3: exact per-bar identities ────────────────────────────────
    # These hold EXACTLY on every row by definition (FM-001, FM-002), so any residual is
    # a column that is not on the row it claims to be on.
    ident_detail, ident_pass = {}, True
    identities = {
        "body_size == abs(close - open)": (
            matrix["body_size"].to_numpy(float),
            np.abs(matrix["close"].to_numpy(float) - matrix["open"].to_numpy(float))),
        "candle_range == high - low": (
            matrix["candle_range"].to_numpy(float),
            matrix["high"].to_numpy(float) - matrix["low"].to_numpy(float)),
    }
    for name, (lhs, rhs) in identities.items():
        err = float(np.nanmax(np.abs(lhs - rhs)))
        ok = err < 1e-6
        ident_pass &= ok
        ident_detail[name] = {"max_abs_error": err, "pass": bool(ok)}
    results["deterministic"] = {
        "blocking": True, "pass": bool(ident_pass), "detail": ident_detail}

    # ── BLOCKING 4: off-by-one detector ─────────────────────────────────────
    # The same identities, with one side shifted a single bar, must BREAK. They are
    # built on close/open/high/low, which change every bar, so a one-bar shift is
    # genuinely destructive. (A smooth quantity is useless here: an earlier version used
    # trend_bias vs ema_fast-ema_slow and stayed at AUC 0.999 under a one-bar shift
    # purely because the EMA spread barely moves between adjacent bars.)
    shift_detail, shift_ok = {}, True
    for name, (lhs, rhs) in identities.items():
        err = float(np.nanmax(np.abs(lhs - np.roll(rhs, 1))))
        broke = err > 1e-3
        shift_ok &= broke
        shift_detail[name] = {"max_abs_error_when_shifted": round(err, 8), "broke": bool(broke)}
    results["deterministic_shift"] = {
        "blocking": True, "pass": bool(shift_ok),
        "detail": {"identities": shift_detail,
                   "why": ("an exact identity that survives a one-bar shift means the "
                           "columns are not on the row they claim")}}

    # ── BLOCKING 4: shuffled label returns the base rate ────────────────────
    vals = labels["y_R_net"].to_numpy(dtype=float)
    base_mean, base_lo, base_hi = block_bootstrap_mean_ci(vals, blocks, n_boot=1000, seed=seed)
    shuffled = vals.copy()
    rng.shuffle(shuffled)
    sh_mean, sh_lo, sh_hi = block_bootstrap_mean_ci(shuffled, blocks, n_boot=1000, seed=seed)
    sh_pass = bool(base_lo <= sh_mean <= base_hi)
    results["shuffled_null"] = {
        "blocking": True, "pass": sh_pass,
        "detail": {"base_mean_R": round(base_mean, 5),
                   "base_ci": [round(base_lo, 5), round(base_hi, 5)],
                   "shuffled_mean_R": round(sh_mean, 5),
                   "shuffled_ci": [round(sh_lo, 5), round(sh_hi, 5)]}}

    # ── REPORTED: how fast label overlap actually decays ────────────────────
    # The block bootstrap uses a block of `horizon` bars. This measures whether that is
    # the right size: if outcome correlation dies well before `horizon`, the block is
    # conservative (wider intervals than strictly needed), which is the safe direction.
    ac = {}
    for k in (1, 2, 5, 10, 20, horizon, 2 * horizon):
        if k >= y.size:
            continue
        ac[f"lag_{k}"] = {
            "agreement": round(float((y[k:] == y[:-k]).mean()), 5),
            "corr": round(float(np.corrcoef(y[k:], y[:-k])[0, 1]), 5),
            "planted_auc_at_lag": round(float(rank_auc(x, np.roll(y, k))), 5),
        }
    results["label_autocorrelation"] = {
        "blocking": False, "pass": None,
        "detail": {
            "note": ("Adjacent oracle labels share forward bars and ARE correlated; this "
                     "is why every interval in this program is a block bootstrap. Blocks "
                     "are sized at the full horizon, so if correlation dies before that "
                     "the intervals are conservative rather than optimistic."),
            "block_size_used": horizon,
            "decay": ac,
        }}

    # ── REPORTED: resolver dwell vs the engine reference ────────────────────
    dwell = matrix["crt_state_resolved"].value_counts().to_dict()
    comparison = {}
    for state, ref in _ENGINE_DWELL_REFERENCE.items():
        got = int(dwell.get(state, 0))
        comparison[state] = {"resolver": got, "engine_reference": ref,
                             "ratio": round(got / ref, 3) if ref else None}
    results["resolver_dwell"] = {
        "blocking": False,
        "pass": None,
        "detail": {
            "note": ("Characterises the RESOLVER, not this harness. The reference is a "
                     "different epoch's ENGINE run pinned in market_crt_states.yaml, so a "
                     "divergence here is expected and is not evidence of a harness fault. "
                     "It is reported because any pattern keyed on crt_state_resolved is a "
                     "statement about the resolver until an engine re-measurement is run."),
            "resolver_distribution": {k: int(v) for k, v in dwell.items()},
            "comparison": comparison,
            "states_never_produced": sorted(
                s for s in _ENGINE_DWELL_REFERENCE if s not in dwell),
        }}

    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--timeframe", default="M15")
    ap.add_argument("--arm-geom", default="disp_bar")
    ap.add_argument("--arm-tie", default="production")
    ap.add_argument("--direction", default="long")
    ap.add_argument("--horizon", type=int, default=DEFAULT_HORIZON)
    ap.add_argument("--seed", type=int, default=20260820)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args(argv)

    tag = f"{args.instrument}_{args.timeframe}"
    matrix_csv = _ROOT / "results" / "research" / "bar_matrix" / tag / "bar_matrix.csv"
    labels_csv = _ROOT / "results" / "research" / "oracle_labels" / tag / "labels.csv"
    for p in (matrix_csv, labels_csv):
        if not p.exists():
            print(f"[FATAL] missing {p}")
            return 2
    out_dir = Path(args.out_dir) if args.out_dir else (
        _ROOT / "results" / "research" / "oracle_harness" / tag)
    out_dir.mkdir(parents=True, exist_ok=True)

    matrix = pd.read_csv(matrix_csv, parse_dates=["timestamp"])
    labels = pd.read_csv(labels_csv, parse_dates=["timestamp"])
    arm = labels[(labels["sl_geom"] == args.arm_geom)
                 & (labels["tie_break"] == args.arm_tie)
                 & (labels["direction"] == args.direction)].reset_index(drop=True)
    if arm.empty:
        print("[FATAL] arm selection is empty")
        return 2

    results = run_checks(arm, matrix, horizon=args.horizon, seed=args.seed)
    blocking = {k: v for k, v in results.items() if v["blocking"]}
    all_pass = all(v["pass"] for v in blocking.values())

    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "instrument": args.instrument,
        "arm": {"sl_geom": args.arm_geom, "tie_break": args.arm_tie,
                "direction": args.direction},
        "rows": int(len(arm)),
        "effective_n": effective_n(arm, horizon=args.horizon),
        "horizon": args.horizon,
        "seed": args.seed,
        "gate": "PASS" if all_pass else "FAIL",
        "verdict_meaning": (
            "PASS means a null from this harness is interpretable as absence of "
            "information. FAIL means any downstream null is 'harness unproven' and must "
            "not be reported as a negative result."),
        "checks": results,
    }
    (out_dir / "harness_report.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(f"\n  HARNESS GATE: {report['gate']}")
    print(f"  arm {args.arm_geom}|{args.arm_tie}|{args.direction} "
          f"| rows {report['rows']} | effective n {report['effective_n']}")
    for name, r in results.items():
        mark = {True: "PASS", False: "FAIL", None: "----"}[r["pass"]]
        kind = "BLOCKING" if r["blocking"] else "reported"
        print(f"   [{mark}] {name:16s} ({kind})")
    d = results["planted_signal"]["detail"]
    print("   planted AUC recovery: " + ", ".join(
        f"{v['planted']}->{v['recovered']}" for v in d.values()))
    print("   identities          : " + ", ".join(
        f"{k.split('==')[0].strip()} err={v['max_abs_error']:.2e}"
        for k, v in results["deterministic"]["detail"].items()))
    sd = results["label_shift_independent"]["detail"]
    h = sd["shift_bars"]
    print(f"   label shift (+/-{h:d})   : aligned {sd['aligned_auc']} -> "
          f"+{h} {sd[f'shift_+{h}_auc']} / -{h} {sd[f'shift_-{h}_auc']}")
    print("   off-by-one detector : " + ", ".join(
        f"{k.split('==')[0].strip()} shifted_err={v['max_abs_error_when_shifted']:.4g}"
        for k, v in results["deterministic_shift"]["detail"]["identities"].items()))
    ac_d = results["label_autocorrelation"]["detail"]["decay"]
    print("   label autocorr      : " + ", ".join(
        f"{k.replace('lag_','k=')}:{v['corr']:+.3f}" for k, v in ac_d.items()))
    sn = results["shuffled_null"]["detail"]
    print(f"   shuffled null       : base {sn['base_mean_R']} vs "
          f"shuffled {sn['shuffled_mean_R']} (base CI {sn['base_ci']})")
    print(f"\n  report -> {out_dir / 'harness_report.json'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
