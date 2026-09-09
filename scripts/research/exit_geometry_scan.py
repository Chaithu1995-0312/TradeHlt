"""exit_geometry_scan.py — exit-geometry & dynamic-stop decomposition (SEM-019 / SEM-020).

Answers the question the profitable-entry oracle program left open: the declared vocabulary
carries relative information (conjunctions beat base at a 6-8x excess over a measured
permutation null) that never crosses zero. Is that bounded by the EXIT, by COST, or by the
size of the information itself?

STAGES
------
  ceilings     What could ANY exit achieve? Computes the SEM-020 decomposition on the real
               two-target object under measured broker cost. This is a GATE: if no cell's
               perfect-foresight ceiling clears zero, no exit policy can help and the axis
               closes without searching it.
  sweep        Geometry x dynamic-stop-policy grid (SEM-019), every bar, both directions.
  interaction  Does exit geometry interact with the oracle's informative state cells, or
               merely shift their level? This is the payoff.

Research/diagnostic only: `economic_claims_allowed: false`, no promotion, no fusion weight,
no G001, no ACTIVE_VERSION change. The holdout partition is never read by any stage here.

Usage:
    python scripts/research/exit_geometry_scan.py --stage ceilings --instrument XAUUSD
"""

from __future__ import annotations

import argparse
import dataclasses
import glob
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.production_config import get_prod_section  # noqa: E402
from research.costs import ComponentCostModel  # noqa: E402
from research.measurement.forward_walk import AdverseFill  # noqa: E402
from research.oracle.exit_analysis import (  # noqa: E402
    ceiling_block,
    gate_verdict,
    horizon_excursions,
    min_achievable_cost,
    passive_exposure_r,
)
from research.oracle.labeler import (  # noqa: E402
    SL_GEOMETRIES,
    label_corpus,
)
from research.oracle.multi_tp_walk import TIE_BREAK_PRODUCTION  # noqa: E402
from research.oracle.exit_sweep import (  # noqa: E402
    build_bars,
    policy_for,
    sl_variants,
    sweep_cell,
)
from research.oracle.labeler import _nights_held, _tp1_multiplier  # noqa: E402
from research.oracle.scan import (  # noqa: E402
    block_bootstrap_mean_ci,
    l2_state_cells,
    partition,
    state_columns,
)
from research.oracle.stop_policy import (  # noqa: E402
    POLICY_PRODUCTION,
    NoModification,
    default_policy_grid,
)

#: Horizons in M15 bars. 40 is the oracle program's horizon (kept so the incumbent is
#: directly comparable); 20 and 96 bracket it at 5h and 24h. 40 runs FIRST in the sweep so
#: the primary result is on disk before the expensive 96-bar arm starts -- a long run that
#: is interrupted should lose robustness arms, never the headline.
HORIZONS = (20, 40, 96)
SWEEP_HORIZON_ORDER = (40, 20, 96)

#: The widest stop in the declared sweep grid. `min_achievable_cost` is the cost floor at
#: this width — declared up front so the ceiling cannot be quietly improved later by
#: widening the grid after seeing the result.
WIDEST_SL_ATR_MULT = 3.0


def _load_inputs(instrument: str, timeframe: str):
    tag = f"{instrument}_{timeframe}"
    matrix_dir = _ROOT / "results" / "research" / "bar_matrix" / tag
    matrix_csv = matrix_dir / "bar_matrix.csv"
    if not matrix_csv.exists():
        raise SystemExit(f"[FATAL] bar matrix not found: {matrix_csv}\n"
                         f"        run scripts/research/build_bar_matrix.py first")
    bm_manifest = json.loads((matrix_dir / "manifest.json").read_text(encoding="utf-8"))
    matrix = pd.read_csv(matrix_csv, parse_dates=["timestamp"])
    raw = pd.read_csv(Path(bm_manifest["corpus_path"]), parse_dates=["timestamp"])
    raw["_pos"] = range(len(raw))

    manifests = sorted(glob.glob(str(
        _ROOT / "results" / "research" / "xauusd_mt5_cost_calibration"
        / "*manifest_LATEST.json")))
    if not manifests:
        raise SystemExit("[FATAL] no SEM-015 cost manifest found")
    cost_path = manifests[-1]
    cost_model = ComponentCostModel.from_manifest(
        json.loads(Path(cost_path).read_text(encoding="utf-8")),
        instrument=instrument, source=cost_path,
    )
    return matrix, raw, bm_manifest, cost_model, cost_path


def _crt_cfgs():
    crt = get_prod_section("crt_engine")
    ep = get_prod_section("execution_planner")
    slt = get_prod_section("sl_tp_comparison")
    return crt, ep, slt


def stage_ceilings(args) -> int:
    """SEM-020: what could any exit achieve, on the real object, under measured cost."""
    t0 = time.time()
    matrix, raw, bm_manifest, cost_model, cost_path = _load_inputs(
        args.instrument, args.timeframe)
    crt_cfg, ep_cfg, slt_cfg = _crt_cfgs()
    if args.limit_bars:
        matrix = matrix.head(args.limit_bars)

    high = raw["high"].to_numpy(float)
    low = raw["low"].to_numpy(float)
    close_raw = raw["close"].to_numpy(float)
    n_raw = high.size

    pos = matrix["_pos"].to_numpy(int)
    entry_all = np.full(n_raw, np.nan)
    entry_all[pos] = matrix["close"].to_numpy(float)
    atr_all = np.full(n_raw, np.nan)
    atr_all[pos] = matrix["atr_abs"].to_numpy(float)

    adverse = AdverseFill(stop_slippage=cost_model.stop_slippage, model_gaps=True)

    blocks: dict = {}
    arm_rows = []
    for horizon in HORIZONS:
        # Exit-agnostic excursions: what the path OFFERED, independent of any exit rule.
        exc = horizon_excursions(high, low, np.nan_to_num(entry_all, nan=0.0),
                                 horizon=horizon)
        # Passive same-direction exposure over the same window, in PRICE units. Divided by
        # each arm's own risk distance below so it lands in that arm's R units.
        passive_price = {
            d: passive_exposure_r(close_raw, close_raw, np.ones(n_raw),
                                  horizon=horizon, direction=d)
            for d in ("long", "short")
        }

        # Realised gross under the incumbent two-target object at THIS horizon. Re-walked
        # rather than reused, because the on-disk labels exist only at horizon 40 and a
        # ceiling must be compared against the same horizon it was computed for.
        labels, _stats = label_corpus(
            matrix, raw, cost_model=cost_model, adverse_fill=adverse,
            max_forward=horizon,
            sl_atr_buffer=float(crt_cfg["sl_atr_buffer"]),
            tp2_mult=float(crt_cfg["tp2_atr_multiplier"]),
            fixed_sl_atr_mult=float(slt_cfg["legacy_sl_atr_mult"]),
            partial_fraction=float(ep_cfg["partial_tp_fraction"]),
            trail_fraction=0.5, crt_cfg=crt_cfg,
        )
        inc = labels[labels["tie_break"] == TIE_BREAK_PRODUCTION]

        for geom in SL_GEOMETRIES:
            for direction in ("long", "short"):
                sub = inc[(inc["sl_geom"] == geom) & (inc["direction"] == direction)]
                if sub.empty:
                    continue
                p = sub["_pos"].to_numpy(int)
                risk = sub["risk_distance"].to_numpy(float)
                gross = sub["y_R_gross"].to_numpy(float)

                mfe_r = exc[direction]["mfe"][p] / risk
                passive = passive_price[direction][p] / risk

                min_cost = min_achievable_cost(
                    cost_model, entry=sub["entry"].to_numpy(float),
                    atr_abs=atr_all[p], widest_sl_atr_mult=WIDEST_SL_ATR_MULT,
                    direction=direction)

                key = f"{geom}|{direction}|h{horizon}"
                blocks[key] = ceiling_block(
                    mfe_r=mfe_r, realised_gross_r=gross, min_cost=min_cost,
                    passive_r=passive,
                    exit_object="SEM-017 two-target partial exit",
                    cost_basis=f"SEM-015 component measured ({cost_model.instrument})",
                    tie_break=TIE_BREAK_PRODUCTION,
                )
                blocks[key]["horizon"] = horizon
                blocks[key]["sl_geom"] = geom
                blocks[key]["direction"] = direction
                blocks[key]["mean_cost_r_incumbent"] = round(
                    float(sub["cost_r"].mean()), 6)
                blocks[key]["expectancy_net_incumbent"] = round(
                    float(sub["y_R_net"].mean()), 6)
                arm_rows.append({"cell": key, **{
                    k: blocks[key][k] for k in (
                        "n", "mfe_capture", "expectancy_gross", "expectancy_net_incumbent",
                        "min_achievable_cost", "perfect_information_upper_bound",
                        "structural_upper_bound", "reality_gap", "ceiling_utilization",
                        "capture_ratio_p50", "passive_exposure_r", "regime",
                        "exit_axis_open")}})

    verdict = gate_verdict(blocks)
    out_dir = _ROOT / "results" / "research" / "exit_geometry" / f"{args.instrument}_{args.timeframe}"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "ceilings",
        "instrument": args.instrument,
        "timeframe": args.timeframe,
        "declares": ["SEM-019 dynamic stop policy", "SEM-020 exit capture decomposition"],
        "authority": "research_diagnostic_only",
        "economic_claims_allowed": False,
        "horizons": list(HORIZONS),
        "widest_sl_atr_mult": WIDEST_SL_ATR_MULT,
        "cost_manifest": cost_path.replace("\\", "/"),
        "bar_matrix_manifest": bm_manifest,
        "gate": verdict,
        "cells": blocks,
        "caveats": [
            "The perfect-foresight ceiling is NOT headroom. It requires knowing the path in "
            "advance; no causal rule reaches it. The attainable bound is the causal ceiling, "
            "measured in the sweep stage.",
            "reality_gap == mfe_capture - expectancy_gross exactly (the cost term cancels), so "
            "any pessimism in the same-bar tie-break inflates it one-for-one. The tie-break is "
            "recorded on every cell for that reason.",
            "This instrument rose across the corpus. passive_exposure_r is carried on every cell "
            "because a cell must beat passive same-direction exposure, not merely zero.",
            "Ceilings here are computed on the SEM-017 two-target object under SEM-015 measured "
            "cost. They are NOT commensurable with the F-025 lineage, which used a single-TP "
            "object under flat 12bps on different instruments.",
        ],
        "elapsed_seconds": round(time.time() - t0, 1),
    }
    (out_dir / "ceilings_report.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")
    pd.DataFrame(arm_rows).to_csv(out_dir / "ceilings_cells.csv", index=False)

    print(f"\n  ceilings -> {out_dir / 'ceilings_report.json'}  ({report['elapsed_seconds']}s)")
    print(f"\n  {'cell':28s} {'MFE_r':>8s} {'E_gross':>9s} {'E_net':>8s} "
          f"{'minCost':>8s} {'perfect':>8s} {'struct':>8s} {'gap':>8s} {'cap50':>7s} {'passive':>8s}")
    for k in sorted(blocks, key=lambda k: (blocks[k]["horizon"], blocks[k]["sl_geom"],
                                           blocks[k]["direction"])):
        b = blocks[k]
        def f(x, w=8, p=4):
            return f"{x:>{w}.{p}f}" if isinstance(x, (int, float)) else f"{'--':>{w}s}"
        print(f"  {k:28s} {f(b['mfe_capture'])} {f(b['expectancy_gross'],9)} "
              f"{f(b['expectancy_net_incumbent'])} {f(b['min_achievable_cost'])} "
              f"{f(b['perfect_information_upper_bound'])} {f(b['structural_upper_bound'])} "
              f"{f(b['reality_gap'])} {f(b['capture_ratio_p50'],7,3)} {f(b['passive_exposure_r'])}")
    print(f"\n  GATE: {verdict['verdict']}  "
          f"({verdict['cells_with_room']}/{verdict['cells']} cells with room; "
          f"perfect ceiling range {verdict['perfect_ceiling_min']} .. "
          f"{verdict['perfect_ceiling_max']})")
    print(f"  capture-ratio violations: {verdict['capture_ratio_violations']} "
          f"({'OK' if verdict['capture_ratio_ok'] else 'DEFECT — investigate before reporting'})")
    if verdict["verdict"] == "EXIT_AXIS_CLOSED":
        print("\n  No exit rule of any kind can profit on this population. "
              "Stages B-D are not run.")
    return 0


def stage_sweep(args) -> int:
    """SEM-019: does ANY causal stop policy, at any geometry, move the needle?"""
    t0 = time.time()
    matrix, raw, bm_manifest, cost_model, cost_path = _load_inputs(
        args.instrument, args.timeframe)
    crt_cfg, ep_cfg, slt_cfg = _crt_cfgs()
    if args.limit_bars:
        matrix = matrix.head(args.limit_bars)

    bars = build_bars(raw)
    ts_by_pos = list(raw["timestamp"])
    close_raw = raw["close"].to_numpy(float)
    n_raw = len(bars)

    pos_list = matrix["_pos"].astype(int).tolist()
    close_list = matrix["close"].astype(float).tolist()
    atr_list = matrix["atr_abs"].astype(float).tolist()
    intent_list = matrix["trade_intent"].tolist()
    tp1_cache = {i: _tp1_multiplier(crt_cfg, i) for i in set(intent_list)}
    tp1_mult_list = [tp1_cache[i] for i in intent_list]

    adverse = AdverseFill(stop_slippage=cost_model.stop_slippage, model_gaps=True)
    grid = {p.name: p for p in default_policy_grid()}
    arms = [POLICY_PRODUCTION, NoModification.name] + [
        n for n in grid if n != NoModification.name]

    sl_atr_buffer = float(crt_cfg["sl_atr_buffer"])
    tp2_mult = float(crt_cfg["tp2_atr_multiplier"])
    partial = float(ep_cfg["partial_tp_fraction"])

    rows = []
    out_dir = (_ROOT / "results" / "research" / "exit_geometry"
               / f"{args.instrument}_{args.timeframe}")
    out_dir.mkdir(parents=True, exist_ok=True)
    for horizon in SWEEP_HORIZON_ORDER:
        passive_price = {
            d: passive_exposure_r(close_raw, close_raw, np.ones(n_raw),
                                  horizon=horizon, direction=d)
            for d in ("long", "short")
        }
        for variant in sl_variants():
            for direction in ("long", "short"):
                common = dict(
                    bars=bars, pos_list=pos_list, close_list=close_list,
                    atr_list=atr_list, tp1_mult_list=tp1_mult_list,
                    ts_by_pos=ts_by_pos, direction=direction, sl_variant=variant,
                    horizon=horizon, tp2_mult=tp2_mult, partial_fraction=partial,
                    sl_atr_buffer=sl_atr_buffer, cost_model=cost_model,
                    adverse_fill=adverse, nights_fn=_nights_held,
                )
                base_res, base_net, base_pos, base_out = sweep_cell(
                    policy=NoModification(), trail_fraction=None, **common)
                print(f"      h{horizon} {variant}/{direction} baseline n={base_res.n} "
                      f"({round(time.time()-t0,1)}s)", flush=True)

                for arm in arms:
                    policy, trail = policy_for(arm, grid)
                    if arm == NoModification.name:
                        res, y_net, keep = base_res, base_net, base_pos
                        res = dataclasses.replace(res, changed_vs_fixed=0,
                                                  status="BASELINE")
                    else:
                        res, y_net, keep, _ = sweep_cell(
                            policy=policy, trail_fraction=trail,
                            baseline_outcomes=base_out, **common)
                    if y_net.size == 0:
                        continue
                    blocks = keep // horizon
                    mean, lo, hi = block_bootstrap_mean_ci(
                        y_net, blocks, n_boot=args.n_boot, seed=20260821)
                    pv = float(np.nanmean(passive_price[direction][keep]))
                    rows.append({
                        "horizon": horizon, "sl_variant": variant,
                        "direction": direction, "arm": arm, "status": res.status,
                        "n": res.n, "changed_vs_fixed": res.changed_vs_fixed,
                        "mean_net": round(res.mean_net, 6),
                        "ci_lo": round(lo, 6), "ci_hi": round(hi, 6),
                        "mean_gross": round(res.mean_gross, 6),
                        "mean_cost": round(res.mean_cost, 6),
                        "win_rate": round(res.win_rate, 4),
                        "stop_exit_rate": round(res.stop_exit_rate, 4),
                        "mean_duration": round(res.mean_duration, 2),
                        "passive_price_mean": round(pv, 6),
                        "beats_zero": bool(lo > 0),
                        "outcome_mix": json.dumps(res.outcome_mix, sort_keys=True),
                    })
        # Written after EVERY horizon, not once at the end: a multi-hour sweep that is
        # interrupted should leave usable evidence rather than nothing.
        pd.DataFrame(rows).to_csv(out_dir / "sweep_cells.csv", index=False)
        print(f"  ...horizon {horizon} done ({round(time.time()-t0,1)}s, "
              f"{len(rows)} cells written)", flush=True)

    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "sweep_cells.csv", index=False)

    inert = df[df["status"] == "STRUCTURALLY_INERT"]
    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "sweep",
        "instrument": args.instrument,
        "declares": ["SEM-019 dynamic stop policy"],
        "authority": "research_diagnostic_only",
        "economic_claims_allowed": False,
        "cells": int(len(df)),
        "arms": arms,
        "sl_variants": list(sl_variants()),
        "horizons": list(HORIZONS),
        "n_boot": args.n_boot,
        "cells_beating_zero": int(df["beats_zero"].sum()),
        "structurally_inert_cells": int(len(inert)),
        "structurally_inert_examples": inert[
            ["horizon", "sl_variant", "direction", "arm"]].head(20).to_dict("records"),
        "cost_manifest": cost_path.replace(chr(92), "/"),
        "elapsed_seconds": round(time.time() - t0, 1),
        "caveats": [
            "Entries are identical in every cell, so a difference is attributable to the "
            "exit alone. That is also why NO cell here is an edge: the entry population "
            "is every bar, so an unconditionally positive cell is a defect signal.",
            "STRUCTURALLY_INERT cells could never have fired (the trail is wider than the "
            "distance to the target). They are not evidence that stop policies do not help.",
            "Intervals are block bootstraps sized to the horizon; adjacent labels overlap.",
        ],
    }
    (out_dir / "sweep_report.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")

    print(f"\n  sweep -> {out_dir / 'sweep_cells.csv'}  ({summary['elapsed_seconds']}s)")
    print(f"  {summary['cells']} cells | beating zero: "
          f"{summary['cells_beating_zero']} | structurally inert: "
          f"{summary['structurally_inert_cells']}")
    ref = df[(df["horizon"] == 40) & (df["sl_variant"].isin(("disp_bar", "fixed_1")))]
    print("\n  ARM COMPARISON (h40, net R, block-bootstrap 95% CI)")
    for (v, d), g in ref.groupby(["sl_variant", "direction"]):
        print(f"   {v}/{d}:")
        for _, r in g.sort_values("mean_net", ascending=False).iterrows():
            flag = "  INERT" if r["status"] == "STRUCTURALLY_INERT" else ""
            print(f"      {r['arm']:20s} {r['mean_net']:+.4f}R "
                  f"[{r['ci_lo']:+.4f},{r['ci_hi']:+.4f}] "
                  f"chg={r['changed_vs_fixed']:6d} "
                  f"stop%={r['stop_exit_rate']:.3f}{flag}")
    return 0


#: Exit configurations carried into the interaction test. Deliberately small and declared
#: up front: this stage asks whether the exit INTERACTS with the entry information, which
#: is a question about a handful of representative exits, not another grid to mine.
INTERACTION_ARMS = ("production", "ratchet_1r", "breakeven_at_1r", "time_decay_6_12")
INTERACTION_HORIZON = 40          # the oracle program's horizon, so cells are comparable
INTERACTION_GEOMS = ("disp_bar", "fixed_1")


def _net_by_pos(common, arm, grid):
    policy, trail = policy_for(arm, grid)
    res, y_net, keep, _ = sweep_cell(policy=policy, trail_fraction=trail, **common)
    return pd.Series(y_net, index=keep)


def stage_interaction(args) -> int:
    """Does exit geometry INTERACT with the entry information, or just shift its level?

    The test is paired, which matters: every exit config is measured on the SAME bars, so
    the sampling noise is shared and an unpaired comparison would be badly mis-specified.
    Pairing collapses the question to something simple and already-tested -- for two exits
    A and B, define d = y_A - y_B per bar and ask whether d is PREDICTABLE FROM THE STATE.

        d predictable from state  =>  the state says which exit wins  =>  INTERACTION
        d unpredictable           =>  the exit is a level shift       =>  LEVEL

    That is exactly the question `l2_state_cells` already answers, so it is reused verbatim
    on the difference series rather than reimplemented.
    """
    t0 = time.time()
    matrix, raw, bm_manifest, cost_model, cost_path = _load_inputs(
        args.instrument, args.timeframe)
    crt_cfg, ep_cfg, slt_cfg = _crt_cfgs()
    if args.limit_bars:
        matrix = matrix.head(args.limit_bars)

    bars = build_bars(raw)
    ts_by_pos = list(raw["timestamp"])
    pos_list = matrix["_pos"].astype(int).tolist()
    close_list = matrix["close"].astype(float).tolist()
    atr_list = matrix["atr_abs"].astype(float).tolist()
    intent_list = matrix["trade_intent"].tolist()
    tp1_cache = {i: _tp1_multiplier(crt_cfg, i) for i in set(intent_list)}
    tp1_mult_list = [tp1_cache[i] for i in intent_list]

    adverse = AdverseFill(stop_slippage=cost_model.stop_slippage, model_gaps=True)
    grid = {p.name: p for p in default_policy_grid()}
    h = INTERACTION_HORIZON

    state_df = matrix.set_index("_pos")
    scols = [c for c in state_columns(matrix) if c in state_df.columns]

    results = []
    perm_summary = []
    for geom in INTERACTION_GEOMS:
        for direction in ("long", "short"):
            common = dict(
                bars=bars, pos_list=pos_list, close_list=close_list,
                atr_list=atr_list, tp1_mult_list=tp1_mult_list, ts_by_pos=ts_by_pos,
                direction=direction, sl_variant=geom, horizon=h,
                tp2_mult=float(crt_cfg["tp2_atr_multiplier"]),
                partial_fraction=float(ep_cfg["partial_tp_fraction"]),
                sl_atr_buffer=float(crt_cfg["sl_atr_buffer"]),
                cost_model=cost_model, adverse_fill=adverse, nights_fn=_nights_held,
            )
            base = _net_by_pos(common, NoModification.name, grid)

            for arm in INTERACTION_ARMS:
                arm_net = _net_by_pos(common, arm, grid)
                common_idx = base.index.intersection(arm_net.index)
                d = (arm_net.loc[common_idx] - base.loc[common_idx])

                frame = pd.DataFrame({"_pos": common_idx, "d": d.to_numpy()})
                for c in scols:
                    frame[c] = state_df.loc[common_idx, c].to_numpy()
                # TRAIN only. The holdout is not read by this stage.
                frame["y_win"] = (frame["d"] > 0).astype(int)
                part = partition(frame, oos_fraction=0.2, embargo_bars=96, horizon=h)
                tr = part.train.reset_index(drop=True)

                cells = l2_state_cells(tr, scols, y_value="d", horizon=h,
                                       min_eff_n=30, n_boot=args.n_boot)
                ok = cells[cells["status"] == "OK"]
                real_hits = int(ok["beats_base"].sum())

                # Block-permutation null: shuffle WHOLE blocks of the difference series so
                # any state-conditional signal is destroyed while the overlap structure is
                # preserved. A naive row shuffle would understate the null badly.
                rng = np.random.default_rng(20260821)
                perm_hits = []
                for _ in range(args.n_perm):
                    blk = (tr["_pos"].to_numpy() // h)
                    uniq = np.unique(blk)
                    mapping = dict(zip(uniq, rng.permutation(uniq)))
                    order = np.argsort([mapping[b] for b in blk], kind="stable")
                    shuffled = tr.copy()
                    shuffled["d"] = tr["d"].to_numpy()[order]
                    pc = l2_state_cells(shuffled, scols, y_value="d", horizon=h,
                                        min_eff_n=30, n_boot=max(100, args.n_boot // 4))
                    pok = pc[pc["status"] == "OK"]
                    perm_hits.append(int(pok["beats_base"].sum()))

                # Empirical p-value, not a max() comparison. With k permutations the
                # smallest attainable p is 1/(k+1), so a verdict of INTERACTION is only
                # reachable when enough permutations were actually run -- which is the
                # honest way to say that a small permutation budget cannot license a
                # positive. `real_hits > max(perm)` on 2 draws is close to a coin flip.
                ge = sum(1 for x in perm_hits if x >= real_hits)
                pval = (1.0 + ge) / (1.0 + len(perm_hits)) if perm_hits else None
                if real_hits == 0 or pval is None or pval > 0.05:
                    verdict = "LEVEL" if (pval is None or pval > 0.20) else "INDETERMINATE"
                else:
                    verdict = "INTERACTION"
                row = {
                    "geom": geom, "direction": direction, "arm": arm,
                    "n": int(len(tr)), "cells_scored": int(len(ok)),
                    "mean_d": round(float(tr["d"].mean()), 6),
                    "cells_state_predicts_d": real_hits,
                    "permuted": perm_hits,
                    "permuted_mean": round(float(np.mean(perm_hits)), 2) if perm_hits else None,
                    "p_value": None if pval is None else round(pval, 4),
                    "min_attainable_p": round(1.0 / (1.0 + len(perm_hits)), 4) if perm_hits else None,
                    "verdict": verdict,
                }
                results.append(row)
                perm_summary.append(row)
                print(f"   {geom:10s} {direction:5s} {arm:18s} "
                      f"meanD={row['mean_d']:+.5f} cells={real_hits:3d} "
                      f"permMean={row['permuted_mean']} "
                      f"p={row['p_value']} -> {verdict}")

    df = pd.DataFrame(results)
    out_dir = (_ROOT / "results" / "research" / "exit_geometry"
               / f"{args.instrument}_{args.timeframe}")
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "interaction_cells.csv", index=False)

    n_inter = int((df["verdict"] == "INTERACTION").sum())
    n_indet = int((df["verdict"] == "INDETERMINATE").sum())
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "interaction",
        "instrument": args.instrument,
        "declares": ["SEM-019 dynamic stop policy", "SEM-020 exit capture decomposition"],
        "authority": "research_diagnostic_only",
        "economic_claims_allowed": False,
        "horizon": h,
        "arms": list(INTERACTION_ARMS),
        "geoms": list(INTERACTION_GEOMS),
        "n_perm": args.n_perm,
        "comparisons": int(len(df)),
        "interaction_verdicts": n_inter,
        "indeterminate_verdicts": n_indet,
        "level_verdicts": int(len(df) - n_inter - n_indet),
        "min_attainable_p": round(1.0 / (1.0 + args.n_perm), 4),
        "overall": "INTERACTION" if n_inter > len(df) / 2 else "LEVEL",
        "rows": results,
        "caveats": [
            "The test is PAIRED: every exit is measured on the same bars, so the noise is "
            "shared. An unpaired comparison of two exits' cell expectancies would be "
            "mis-specified and would find differences that are pure common noise.",
            "A LEVEL verdict means the exit does not unlock the entry information: it "
            "shifts every cell together. That is a real answer, not a failed search.",
            "TRAIN partition only. The stride holdout is not read by this stage.",
            "Verdicts use an empirical p-value over block permutations, so the smallest "
            "attainable p is 1/(n_perm+1). A permutation budget too small to reach 0.05 "
            "cannot license an INTERACTION verdict, and that limit is reported rather than "
            "worked around with a max() comparison.",
        ],
        "elapsed_seconds": round(time.time() - t0, 1),
    }
    (out_dir / "interaction_report.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\n  interaction -> {out_dir / 'interaction_report.json'} "
          f"({report['elapsed_seconds']}s)")
    print(f"  {n_inter}/{len(df)} comparisons show INTERACTION -> overall "
          f"{report['overall']}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stage", required=True, choices=("ceilings", "sweep", "interaction"))
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--timeframe", default="M15")
    ap.add_argument("--limit-bars", type=int, default=None, help="first N matrix rows (smoke)")
    ap.add_argument("--n-boot", type=int, default=500, help="block-bootstrap resamples per cell")
    ap.add_argument("--n-perm", type=int, default=3, help="block permutations for the interaction null")
    args = ap.parse_args(argv)

    if args.stage == "ceilings":
        return stage_ceilings(args)
    if args.stage == "sweep":
        return stage_sweep(args)
    if args.stage == "interaction":
        return stage_interaction(args)
    print(f"[stage {args.stage}] not yet implemented")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
