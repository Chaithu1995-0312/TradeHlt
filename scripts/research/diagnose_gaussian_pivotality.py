# -*- coding: utf-8 -*-
"""diagnose_gaussian_pivotality.py — does the Gaussian channel change ANY trade? (F-060 Part B)

CONTEXT. The live Gaussian channel is an UNPARAMETERIZED kernel: `exp(-x^2/2)` over 3 of 38
features, with mu=0/sigma=1 forced because no `models/gaussian_registry.json` entry carries those
keys (F-060; floor `tests/test_gaussian_live_parameterization.py`). With mu=0 the score peaks when
the market is FLAT and decays symmetrically for moves in either direction — yet it enters fusion at
`weight_gaussian: 0.2` alongside directional channels. This script asks the only question that can
be answered decisively: does that channel move the entry set at all?

METHOD (F-036, reused verbatim). Pin the channel and compare the trade-ledger sha256 against the
unpinned baseline. A byte-identical ledger proves NON-PIVOTAL — no statistics needed, because you
cannot bootstrap a difference that is exactly zero.

WHY THE SEAM IS `HeuristicGaussianEngine.compute` AND NOT THE WEIGHT OR THE ADAPTER:
  * `weight_gaussian = 0` is REMOVAL WITH RENORMALIZATION over the remaining three channels
    (fusion_engine.py:487) — a different intervention than a constant-0.5 vote, since it silently
    re-weights CRT/zone/rr too.
  * Patching `GaussianAdapter.score` (fusion_engine.py:231) covers fusion but MISSES
    `engine_results["gaussian"]`, a separate call at engine_runner.py:698 that feeds the
    completeness gate and the Phase-5 path at :730-741.
  * Both seams funnel through the same object (`GaussianAdapter(self.gaussian)`,
    engine_runner.py:382, is the same instance called at :698). Pinning `compute` therefore covers
    fusion AND engine_results AND the ConvergenceController stability term — the weak third channel
    the zone sweep explicitly deferred (diagnose_zone_inertness.py:20-23).

GATE HYGIENE (decisive — do not remove). Gaussian only reaches a decision when the 4-engine fusion
gate runs. `backtest_v2.py:1899` reads `os.getenv("BACKTEST_ENGINE_GATE", "1")`; the code default is
ON (F-058) but F-037 and `active_models.yaml` document OFF, and the value has historically come from
an untracked `.env`. A gate-OFF run would exercise the CRT state machine only and report
"non-pivotal" while measuring nothing. So this driver SETS the var explicitly and records the
effective value in its manifest.

TWO CELLS, BECAUSE "PIN TO 0.5" ANSWERS THE WRONG QUESTION (revised 2026-07-22, mid-experiment).
A pre-run measurement of the channel over the full corpus (280,008 bars, 4 majors) found it is
effectively CONSTANT:

    instrument   mean      std       min       max      tanh(momentum) saturated
    BNBUSDT      0.883795  1.24e-02  0.873710  1.000000  98.12%
    ETHUSDT      0.882561  3.37e-03  0.870426  1.000000  99.64%
    BTCUSDT      0.882543  2.91e-03  0.876969  1.000000  99.90%
    SOLUSDT      0.883815  1.19e-02  0.869977  1.000000  93.42%

Mechanism: `momentum_score = close.diff() / atr` (feature_pipeline.py:765) divides an ABSOLUTE price
change by a RELATIVE atr (ATR(14)/close), so it ranges ±4600 (FeatureHealth: min=-4622, max=+5766)
and `tanh` saturates to exactly ±1 on 93-99.9% of bars. With `ema_diff` of order 1e-3, x is pinned
at ±0.5 and — because mu=0 makes the kernel SYMMETRIC, so the sign is discarded — the score is
exp(-0.125) = 0.8824969 almost always.

So pinning to 0.5 would change the channel's LEVEL (0.883 -> 0.5, i.e. 0.077 off the fused score at
weight 0.2) and would tell us nothing about whether its VARIATION carries information. The two
questions must be separated:

    pinned_at_saturation (0.8824969)  -> INFORMATION test: does the channel's variation matter?
    pinned_0p5                        -> LEVEL test: does its constant offset matter?

PRE-REGISTERED INTERPRETATION (fixed before these cells ran — E-001 discipline):

    pinned_at_saturation byte-identical -> GAUSSIAN_INFORMATION_INERT
        The channel contributes no information; it is a constant offset wearing a model's name.
        A proof, not an estimate. Research/docs authority only.
    pinned_at_saturation differs        -> GAUSSIAN_INFORMATION_PIVOTAL_UNDERPOWERED
        Its variation moves trades, but see the power ceiling below. NO authority.
    pinned_0p5 differs while pinned_at_saturation is identical
        -> the channel acts purely as a LEVEL/bias term on the fusion threshold. This is a
        calibration fact about `weight_gaussian` + `tier_*`, NOT evidence the Gaussian model works.

The power ceiling is known IN ADVANCE and must not be laundered after the fact. Gate-ON trade counts
(F-037) are BNB 11 / ETH 4 / BTC 5 / SOL 6 -> pooled n≈26, below the `min_samples: 30` floor. If the
ledgers differ, the honest statement is "the channel moves trades; its economic sign is
INSUFFICIENT" — no expectancy claim, no re-weight, no removal, no promote (§6.5 Authority Ladder:
information != value != authority).

MEASURE-ONLY. No config is edited, no hash changes, nothing is promoted.
PRODUCTION_BEHAVIOR_CHANGED = NO.

Usage:
    python scripts/research/diagnose_gaussian_pivotality.py                      # 4 majors
    python scripts/research/diagnose_gaussian_pivotality.py --instruments BNBUSDT
    python scripts/research/diagnose_gaussian_pivotality.py --selfcheck-only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
_RESEARCH = _ROOT / "scripts" / "research"
for _p in (str(_SRC), str(_RESEARCH)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.chdir(_ROOT)

# The fusion gate must be ON for this experiment to measure anything. Set before importing the
# backtest module so no import-time capture can read a stale value.
os.environ["BACKTEST_ENGINE_GATE"] = "1"

# Reuse the F-036 harness verbatim (keeps spine-run semantics byte-identical to qualify_zone_topk).
import qualify_zone_topk as qz                                        # noqa: E402
from engines.heuristic_gaussian_engine import HeuristicGaussianEngine  # noqa: E402
from research.provenance import provenance_block                     # noqa: E402
from research.config import ResearchConfig                           # noqa: E402
from research.qualification import QUALIFICATION_VERSION             # noqa: E402
from utils.console_safe import safe_print                            # noqa: E402

SPINE_CONFIG = qz.SPINE_CONFIG
MAJORS = qz.MAJORS

# exp(-0.125): the value the kernel takes whenever tanh(momentum) saturates, i.e. on 93-99.9% of
# bars. Pinning HERE removes the channel's variation while preserving its level — the information
# test. Analytic (not a per-instrument empirical mean), so it is instrument-independent and exact.
SATURATION_SCORE = round(math.exp(-0.125), 7)   # 0.8824969
PINNED_SCORE = 0.5   # the neutral vote GaussianAdapter itself falls back to (fusion_engine.py:235)

# Measured pre-run over the full corpus; recorded in the artifact as the motivation for the
# saturation cell. See scripts note in the module docstring.
CHANNEL_DISTRIBUTION = {
    "BNBUSDT": {"mean": 0.883795, "std": 1.24e-02, "min": 0.873710, "tanh_saturated_pct": 98.12},
    "ETHUSDT": {"mean": 0.882561, "std": 3.37e-03, "min": 0.870426, "tanh_saturated_pct": 99.64},
    "BTCUSDT": {"mean": 0.882543, "std": 2.91e-03, "min": 0.876969, "tanh_saturated_pct": 99.90},
    "SOLUSDT": {"mean": 0.883815, "std": 1.19e-02, "min": 0.869977, "tanh_saturated_pct": 93.42},
}


# ─────────────────────────────────────────────────────────────────────────────
# Injection — wrap HeuristicGaussianEngine.compute. `value=None` is a pure passthrough, which is
# what the self-check exercises: it proves the WRAPPING MECHANISM is neutral, so any ledger delta
# in the real cell is attributable to the pinned value alone (single-variable isolation).
# ─────────────────────────────────────────────────────────────────────────────
class _PinGaussian:
    def __init__(self, value: float | None):
        self.value = value
        self._orig = None

    def __enter__(self):
        orig = HeuristicGaussianEngine.compute
        val = self.value

        def patched(self_engine, input_data, candle_idx=0, direction="long"):
            if val is None:
                return orig(self_engine, input_data, candle_idx=candle_idx, direction=direction)
            return {"score": val, "reason": "ablation_pinned",
                    "meta": {"mu": None, "sigma": None, "x": None}}

        self._orig = orig
        HeuristicGaussianEngine.compute = patched
        return self

    def __exit__(self, *exc):
        HeuristicGaussianEngine.compute = self._orig
        return False


# ─────────────────────────────────────────────────────────────────────────────
def _selfcheck(version: str, root: Path, instrument: str) -> dict:
    """Unpatched vs patched-passthrough must be byte-identical, else the hook is not neutral."""
    _, _, sha_un = qz._run_spine_once(instrument, version, root / "_selfcheck_unpatched")
    with _PinGaussian(None):
        _, _, sha_pa = qz._run_spine_once(instrument, version, root / "_selfcheck_patched")
    return {"instrument": instrument, "unpatched_sha": sha_un, "patched_passthrough_sha": sha_pa,
            "byte_identical": bool(sha_un) and sha_un == sha_pa}


def _run_cell(value: float | None, version: str, root: Path, instruments: list[str],
              tag: str) -> dict:
    out: dict[str, dict] = {}
    ctx = _PinGaussian(value) if value is not None else _PinGaussian(None)
    with ctx:
        for inst in instruments:
            l1, _entries, sha = qz._run_spine_once(inst, version, root / tag / inst)
            out[inst] = {"trades_sha256": sha, **l1}
            safe_print(f"    {inst}: trades={l1['approved_trades']} "
                       f"E={l1['expectancy_r']} sha={sha[:12]}")
    return out


# ─────────────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="diagnose_gaussian_pivotality",
        description="Does the (unparameterized) Gaussian channel change any trade? [F-060]")
    p.add_argument("--instruments", nargs="*", default=MAJORS)
    p.add_argument("--out", default="results/research/gaussian_pivotality")
    p.add_argument("--selfcheck-only", action="store_true")
    p.add_argument("--no-selfcheck", action="store_true")
    args = p.parse_args(argv)

    os.environ["RESEARCH_SPINE_CONFIG"] = SPINE_CONFIG
    for name in ("CRT", "ENGINE_RUNNER", "ZONE_GATE", "HEURISTIC_GAUSSIAN"):
        logging.getLogger(name).setLevel(logging.ERROR)

    spine_block = json.loads(Path(SPINE_CONFIG).read_text(encoding="utf-8")).get("spine", {})
    version = spine_block.get("prod_version") or qz._bt.PROD_VERSION
    instruments = [i for i in args.instruments if (Path("data") / f"{i}_M15.csv").exists()]
    if not instruments:
        raise SystemExit(f"no data CSVs for {args.instruments}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    spine_root = out_dir / "_spine"

    gate = os.environ["BACKTEST_ENGINE_GATE"]
    safe_print(f"BACKTEST_ENGINE_GATE={gate} (must be 1, else this measures nothing)")
    safe_print(f"prod_version={version}  instruments={instruments}\n")

    # ── self-check ────────────────────────────────────────────────────────────
    selfcheck = None
    if not args.no_selfcheck:
        safe_print("self-check (compute-wrap neutral as passthrough)…")
        selfcheck = _selfcheck(version, spine_root, instruments[0])
        safe_print(f"  {selfcheck['instrument']}: byte_identical={selfcheck['byte_identical']}")
        if not selfcheck["byte_identical"]:
            raise SystemExit("self-check FAILED — compute wrap not neutral as passthrough. STOP.")
    if args.selfcheck_only:
        safe_print("\nself-check only — exiting before the ablation cells.")
        return 0

    # ── cells ─────────────────────────────────────────────────────────────────
    safe_print("\n[cell baseline] gaussian live (exp(-x^2/2))")
    baseline = _run_cell(None, version, spine_root, instruments, "baseline")

    safe_print(f"\n[cell pinned_at_saturation] variation removed, level kept ({SATURATION_SCORE})")
    saturated = _run_cell(SATURATION_SCORE, version, spine_root, instruments, "saturation")

    safe_print(f"\n[cell pinned_0p5] level shifted to the neutral vote ({PINNED_SCORE})")
    pinned = _run_cell(PINNED_SCORE, version, spine_root, instruments, "pinned")

    # ── verdict (pre-registered; see module docstring) ────────────────────────
    per_inst = {}
    info_change = False   # baseline vs saturation — does the channel's VARIATION matter?
    level_change = False  # baseline vs 0.5        — does its LEVEL matter?
    for inst in instruments:
        b, s, q = baseline[inst], saturated[inst], pinned[inst]
        info_identical = bool(b["trades_sha256"]) and b["trades_sha256"] == s["trades_sha256"]
        level_identical = bool(b["trades_sha256"]) and b["trades_sha256"] == q["trades_sha256"]
        info_change = info_change or not info_identical
        level_change = level_change or not level_identical
        per_inst[inst] = {
            "information_byte_identical": info_identical,
            "level_byte_identical": level_identical,
            "baseline_sha256": b["trades_sha256"],
            "saturation_sha256": s["trades_sha256"],
            "pinned_0p5_sha256": q["trades_sha256"],
            "baseline_trades": b["approved_trades"],
            "saturation_trades": s["approved_trades"],
            "pinned_0p5_trades": q["approved_trades"],
            "baseline_expectancy_r": b["expectancy_r"],
            "saturation_expectancy_r": s["expectancy_r"],
            "pinned_0p5_expectancy_r": q["expectancy_r"],
            "delta_trades_level": q["approved_trades"] - b["approved_trades"],
        }

    pooled_n = sum(v["baseline_trades"] for v in per_inst.values())
    if not info_change:
        verdict = "GAUSSIAN_INFORMATION_INERT"
        authority = ("research/docs only — a byte-identical ledger under variation-removal is a "
                     "proof, not an estimate: the channel is a constant offset, not a model")
    else:
        verdict = "GAUSSIAN_INFORMATION_PIVOTAL_UNDERPOWERED"
        authority = ("NONE — the channel's variation moves the entry set, but pooled n is below "
                     "the min_samples=30 floor; no expectancy claim, no re-weight, no removal (§6.5)")

    rc = ResearchConfig.from_file(SPINE_CONFIG)
    body = {
        "experiment": "gaussian_channel_pivotality",
        "registers_finding": "F-060",
        "method": "F-036 ledger-sha ablation; seam = HeuristicGaussianEngine.compute",
        "cells": {"baseline": "live kernel",
                  "pinned_at_saturation": SATURATION_SCORE,
                  "pinned_0p5": PINNED_SCORE},
        "channel_distribution_prerun": CHANNEL_DISTRIBUTION,
        "backtest_engine_gate": gate,
        "instruments": instruments,
        "prod_version": version,
        "qualification_version": QUALIFICATION_VERSION,
        "spine_config_sha256": rc.sha256(),
        **provenance_block(rc.exit_model, rc.round_trip_bps),
        "selfcheck": selfcheck,
        "per_instrument": per_inst,
        "pooled_baseline_trades": pooled_n,
        "power_floor_min_samples": 30,
        "underpowered": pooled_n < 30,
        "information_entry_change": info_change,
        "level_entry_change": level_change,
        "verdict": verdict,
        "authority_granted": authority,
        "production_behavior_changed": "NO",
    }
    body_json = json.dumps(body, sort_keys=True, indent=2)
    body_sha = hashlib.sha256(body_json.encode("utf-8")).hexdigest()
    (out_dir / "gaussian_pivotality.json").write_text(body_json, encoding="utf-8")
    (out_dir / "gaussian_pivotality_manifest.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": qz._git_commit(),
        "body_sha256": body_sha,
        "spine_config_sha256": rc.sha256(),
        "backtest_engine_gate": gate,
    }, sort_keys=True, indent=2), encoding="utf-8")

    safe_print(f"\nVERDICT: {verdict}")
    safe_print(f"information channel changed entries: {info_change}")
    safe_print(f"level channel changed entries:       {level_change}")
    safe_print(f"pooled baseline trades={pooled_n} (floor 30) underpowered={pooled_n < 30}")
    safe_print(f"authority: {authority}")
    safe_print(f"body_sha256={body_sha}")
    safe_print(f"-> {out_dir / 'gaussian_pivotality.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
