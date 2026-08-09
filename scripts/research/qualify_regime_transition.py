# -*- coding: utf-8 -*-
"""qualify_regime_transition.py — Program 4b driver (thin CLI).

Measures whether a forward Markov P^H regime-TRANSITION forecast — "what regime is coming",
not "what regime is now" (Program 4, KILLED, F-030) — is economically consumable by a
DIRECTIONAL consumer. Reuses `research.regime_conditioning.evaluate_scope` VERBATIM (same
M4 gate, same cross-matrix, same verdict vocabulary) but conditions consumers on the
PREDICTED label series (`interpreters.regime_observer.MarkovRegimeForecaster.forecast_series`)
instead of the contemporaneous one, and additionally supplies the CURRENT-level series so the
5th control (within-tercile shuffle) can run — isolating whether an apparent transition edge
is really just the already-falsified LEVEL signal reappearing.

Two families (mirrors qualify_regime_conditioning.py exactly):
  * toy   — configs/research/research_config_regime_transition.json   consumers: expansion_breakout, mean_reversion
  * spine — configs/research/research_config_spine_majors.json (UNCHANGED, Program 4's own file)   consumer: spine

The calibration gate is HARD here (raises), not advisory — per the pre-registration: "the CLI
raises... no economic claim runs on an instrument whose vol-memory prior isn't reproduced."

Deterministic body (no wall-clock); the run manifest (timestamp/git) is written separately.

Usage:
    python scripts/research/qualify_regime_transition.py
    python scripts/research/qualify_regime_transition.py --out results/research/regime_transition
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import research.controls    # noqa: F401,E402  (register controls)
import research.hypotheses  # noqa: F401,E402  (register hypotheses, incl. spine)
from interpreters.regime_observer import MarkovRegimeForecaster, RegimeLabeler  # noqa: E402
from research.config import ResearchConfig                        # noqa: E402
from research.costs import CostModel                              # noqa: E402
from research.process_characterization import characterize        # noqa: E402
from research.provenance import provenance_block                  # noqa: E402
from research.qualification import (                              # noqa: E402
    BH_METHOD_VERSION, PERMUTATION_METHOD_VERSION, QUALIFICATION_VERSION, QualConfig,
)
from research.regime_conditioning import RegimeConfig, evaluate_scope  # noqa: E402
from research.registry import HYPOTHESIS_REGISTRY                 # noqa: E402
from research.runner import HypothesisRunner                      # noqa: E402
from utils.console_safe import safe_print                         # noqa: E402

MAJORS = ["BNBUSDT", "ETHUSDT", "BTCUSDT", "SOLUSDT"]
SCOPES = MAJORS + ["POOLED"]

TOY_CONFIG = "configs/research/research_config_regime_transition.json"
SPINE_CONFIG = "configs/research/research_config_spine_majors.json"   # Program 4's own file, unchanged
FAMILIES = [
    ("toy", TOY_CONFIG, ["expansion_breakout", "mean_reversion"]),
    ("spine", SPINE_CONFIG, ["spine"]),
]


class CalibrationError(RuntimeError):
    """Raised when the hard calibration gate fails — no economic claim may run."""


def _csv_map(cfg: ResearchConfig, instruments: list[str]) -> dict[str, str]:
    keep = set(instruments)
    out: dict[str, str] = {}
    for p in sorted(Path(cfg.data_dir).glob(cfg.pattern)):
        inst = p.stem.split("_")[0]
        if inst in keep:
            out[inst] = str(p)
    return out


def _load_candles(csv_path: str, instrument: str) -> list:
    """Same deterministic loader the runner uses, so candle indices align 1:1 with
    `signal.entry_index` produced during runner.collect()."""
    from runtime.backtest_v2 import CandleLoader
    candles = list(CandleLoader(csv_path, instrument).stream())
    for i, c in enumerate(candles):
        c.index = i
    return candles


def _current_level_series(csv_map: dict[str, str], rcfg: RegimeConfig) -> dict[str, list]:
    labeler = RegimeLabeler(atr_period=rcfg.atr_period, tercile_window=rcfg.tercile_window)
    return {inst: labeler.label_series(_load_candles(path, inst))
            for inst, path in sorted(csv_map.items())}


def _predicted_series(csv_map: dict[str, str], rcfg: RegimeConfig, mcfg: dict) -> dict[str, list]:
    forecaster = MarkovRegimeForecaster(
        atr_period=rcfg.atr_period, tercile_window=rcfg.tercile_window,
        w_markov=mcfg["w_markov"], h=mcfg["h"],
    )
    return {inst: forecaster.forecast_series(_load_candles(path, inst))
            for inst, path in sorted(csv_map.items())}


def _calibration(csv_map: dict[str, str], mcfg: dict) -> dict:
    """HARD gate (raises CalibrationError on failure) — per the pre-registration, no economic
    claim runs on an instrument whose volatility-memory prior isn't reproduced."""
    inst = "BNBUSDT" if "BNBUSDT" in csv_map else sorted(csv_map)[0]
    pm = characterize(_load_candles(csv_map[inst], inst), instrument=inst)
    lo = mcfg["hurst_atr_center"] - mcfg["hurst_atr_tolerance"]
    hi = mcfg["hurst_atr_center"] + mcfg["hurst_atr_tolerance"]
    persistent = bool(pm.thesis_flags.get("volatility_persistent"))
    in_band = lo <= pm.hurst_atr <= hi
    result = {
        "instrument": inst,
        "hurst_atr": pm.hurst_atr,
        "hurst_returns": pm.hurst_returns,
        "volatility_persistent": persistent,
        "hurst_atr_band": [round(lo, 6), round(hi, 6)],
        "valid": bool(persistent and in_band),
    }
    if not result["valid"]:
        raise CalibrationError(
            f"Program 4b hard calibration gate FAILED for {inst}: "
            f"hurst_atr={pm.hurst_atr} not in [{lo},{hi}] or volatility_persistent={persistent}. "
            "No economic claim may run — the labeler's substrate does not reproduce the "
            "pre-registered volatility-memory prior."
        )
    return result


def _run_family(cfg_path: str, consumer_names: list[str], csv_map_majors,
                predicted_series, current_level_series, rcfg: RegimeConfig
                ) -> tuple[ResearchConfig, dict]:
    os.environ["RESEARCH_SPINE_CONFIG"] = cfg_path     # no-op for toy family
    cfg = ResearchConfig.from_file(cfg_path)
    runner = HypothesisRunner(cfg)
    cost = CostModel(cfg.round_trip_bps)
    qcfg = QualConfig.from_research_config(cfg)
    csv_map = _csv_map(cfg, MAJORS)
    if not csv_map:
        raise SystemExit(f"No CSVs matched {cfg.pattern} in {cfg.data_dir} for {MAJORS}")
    control_names = sorted(n for n, h in HYPOTHESIS_REGISTRY.items() if h.family == "control")

    per_by_hyp: dict[str, dict] = {}
    for name in list(consumer_names) + control_names:
        per_by_hyp[name] = runner.collect(name, csv_map)
    consumers = {n: per_by_hyp[n] for n in consumer_names}
    controls = {n: per_by_hyp[n] for n in control_names}

    family: dict[str, dict] = {}
    for scope in SCOPES:
        wanted = MAJORS if scope == "POOLED" else [scope]
        scope_instruments = [i for i in wanted if i in csv_map]
        family[scope] = evaluate_scope(
            consumers, controls, predicted_series, qcfg, cost, rcfg, scope_instruments,
            current_level_series=current_level_series)
    return cfg, family


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def _print_table(doc: dict) -> None:
    safe_print("\nQUALIFY-REGIME-TRANSITION — Program 4b (intrabar_fixed, 12bps; alpha=0.05)")
    cal = doc["calibration"]
    safe_print(f"calibration[{cal['instrument']}]: H_atr={cal['hurst_atr']} "
               f"band={cal['hurst_atr_band']} valid={cal['valid']}\n")
    header = (f"| {'Family':6s} | {'Consumer':18s} | {'Scope':10s} | {'Verdict':22s} |")
    safe_print(header)
    safe_print("|" + "-" * 8 + "|" + "-" * 20 + "|" + "-" * 12 + "|" + "-" * 24 + "|")
    for fam_key, _cfg, consumers in FAMILIES:
        for consumer in consumers:
            for scope in SCOPES:
                cons = doc["families"][fam_key][scope]["consumers"].get(consumer)
                if cons is None:
                    continue
                safe_print(f"| {fam_key:6s} | {consumer:18s} | {scope:10s} | {cons['verdict']:22s} |")
    exploitable = [
        f"{fam}:{c}@{sc}"
        for fam, _cfg, cons in FAMILIES
        for sc in SCOPES
        for c, r in doc["families"][fam][sc]["consumers"].items()
        if r["verdict"] == "REGIME_EXPLOITABLE"
    ]
    safe_print(f"\nREGIME_EXPLOITABLE: {exploitable or 'none'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="qualify_regime_transition",
        description="Program 4b — forward Markov regime-transition forecast across crypto majors")
    parser.add_argument("--out", default="results/research/regime_transition")
    parser.add_argument("--regime-config", default=TOY_CONFIG,
                        help="source of the 'regime'/'markov' blocks (labeler + forecast + control params)")
    args = parser.parse_args(argv)

    rcfg = RegimeConfig.from_file(args.regime_config)
    mcfg = json.loads(Path(args.regime_config).read_text(encoding="utf-8"))["markov"]
    base_cfg = ResearchConfig.from_file(TOY_CONFIG)
    csv_map_majors = _csv_map(base_cfg, MAJORS)
    if not csv_map_majors:
        raise SystemExit(f"No CSVs matched {base_cfg.pattern} in {base_cfg.data_dir}")

    calibration = _calibration(csv_map_majors, mcfg)   # raises on failure -- runs FIRST
    current_level_series = _current_level_series(csv_map_majors, rcfg)
    predicted_series = _predicted_series(csv_map_majors, rcfg, mcfg)

    families_out: dict[str, dict] = {}
    cfgs: dict[str, ResearchConfig] = {}
    for fam_key, cfg_path, consumers in FAMILIES:
        cfg, fam = _run_family(cfg_path, consumers, csv_map_majors,
                               predicted_series, current_level_series, rcfg)
        families_out[fam_key] = fam
        cfgs[fam_key] = cfg

    doc = {
        "qualification_version": QUALIFICATION_VERSION,
        "permutation_method_version": PERMUTATION_METHOD_VERSION,
        "bh_method_version": BH_METHOD_VERSION,
        "alpha": cfgs["toy"].q_significance_alpha,
        "scope_order": SCOPES,
        "majors": MAJORS,
        "regime_params": {
            "atr_period": rcfg.atr_period, "tercile_window": rcfg.tercile_window,
            "lag_k": rcfg.lag_k, "harmful_margin": rcfg.harmful_margin,
            "redundant_tol": rcfg.redundant_tol,
        },
        "markov_params": mcfg,
        **provenance_block(cfgs["toy"].exit_model, cfgs["toy"].round_trip_bps),
        "calibration": calibration,
        "families": {
            "toy": {"config_path": TOY_CONFIG, "config_sha256": cfgs["toy"].sha256(),
                    **families_out["toy"]},
            "spine": {"config_path": SPINE_CONFIG, "config_sha256": cfgs["spine"].sha256(),
                      "prod_version": "v2_multi_2026_04", **families_out["spine"]},
        },
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "regime_transition.json").write_text(
        json.dumps(doc, sort_keys=True, indent=2), encoding="utf-8")
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "toy_config_sha256": cfgs["toy"].sha256(),
        "spine_config_sha256": cfgs["spine"].sha256(),
    }
    (out_dir / "regime_transition_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")

    _print_table(doc)
    safe_print(f"\n-> {out_dir / 'regime_transition.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
