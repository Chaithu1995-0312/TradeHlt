"""
soft_conf_ema_double_update_probe.py
=====================================
MEASURE-ONLY probe (READ-ONLY w.r.t. src/): does the CRT soft-confirmation window's
double EMA update per candle move the S-score vector, and in which direction?

Defect under measurement (see plan file
`pure-conversation-when-you-curried-ocean.md`): `EngineState.update_emas` fires TWICE on
the same candle close during the RETEST/soft-confirmation window —
  crt_engine_v2.py:2617  (unconditional, pre-chain, every candle)
  crt_engine_v2.py:2976  (inside `elif self.state.evaluating_soft_conf:`, every candle of
                          the confirmation window, run AFTER the 2617 update)
Re-applying the same EMA update gives an effective alpha of 2*a - a**2, which COMPRESSES
the fast/slow spread in a trend (predicted ratio ~0.46x for ema_fast=2/ema_slow=5) and
inflates it in chop (~1.34x) — see PREDICTION below. `f_mom` reads the SPREAD, so this is
the opposite of "overly sensitive momentum" — it systematically UNDER-states directional
momentum in trends, making approval HARDER, not easier.

This script does not edit src/config_layer/crt_engine_v2.py. It monkeypatches
EngineState.update_emas (in this process only) to carry a parallel single-update EMA
trajectory alongside the live double-update one, and recomputes the confirmation score C
and fusion score S for both arms at every compute_soft_confirmation() call using a pure
reimplementation of the SAME arithmetic (crt_engine_v2.py:1900-1939), cross-checked at
runtime against the real function's output for the double-update arm (self-consistency —
see tests/test_soft_conf_ema_probe.py for the enforced floor).

EXACTNESS BOUNDARY: the counterfactual single-update trajectory is exact only while both
arms share the same underlying engine STATE trajectory (the live engine only ever runs the
real double-update path — G, active_range, displacement_candle etc. all come from the real
run). The first candle where the S-vs-tier decision bucket would flip under single-update
EMAs is recorded as `first_divergence_idx`; every evaluation after that point is a REAL
computation on a state trajectory a genuine single-update engine might not have reached the
same way, and is labeled POST_DIVERGENCE — indicative only, not a measurement.

Per the standing instruction, this probe runs on XAUUSD only (data/mt5/XAUUSD_M15.csv).
Do NOT substitute a crypto major to manufacture more soft-conf evaluations — a thin result
on XAUUSD is the honest result, and the throughput ceiling (1 setup / 47,275 bars) is
itself part of what's being reported.

Usage:
  python scripts/analysis/soft_conf_ema_double_update_probe.py
  python scripts/analysis/soft_conf_ema_double_update_probe.py --csv <path> --instrument XAUUSD
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import (  # noqa: E402
    Direction, EngineState, UltronRiskEngine,
)
from config_layer.production_config import (  # noqa: E402
    PROD_VERSION, load_prod_config_from_registry,
)
from runtime.backtest_v2 import (  # noqa: E402
    BacktestConfig, BacktestRunner, CandleLoader, MultiInstrumentRunner,
)
from utils.console_safe import safe_print  # noqa: E402

_DEFAULT_CSV = str(_ROOT / "data" / "mt5" / "XAUUSD_M15.csv")
_DEFAULT_INSTRUMENT = "XAUUSD"
_OUT_DIR = _ROOT / "results" / "analysis"
_ARTIFACT_JSON = _OUT_DIR / "soft_conf_ema_double_update.LATEST.json"
_ARTIFACT_MD = _OUT_DIR / "soft_conf_ema_double_update.LATEST.md"

_REGIME_WINDOW = 5  # candles of sign-persistence checked for trend vs chop tagging


# ─────────────────────────────────────────────────────────────────────────────
# Pure reimplementation of compute_soft_confirmation's arithmetic
# (mirrors crt_engine_v2.py:1900-1939 verbatim; cross-checked at runtime — see
# `_check_self_consistency` below and tests/test_soft_conf_ema_probe.py).
# ─────────────────────────────────────────────────────────────────────────────

def _recompute_C(risk_engine: UltronRiskEngine, candle, state: EngineState,
                  ema_fast: float, ema_slow: float) -> dict:
    cfg = risk_engine.config
    w_body, w_mom, w_dist, w_disp = cfg.conf_weights

    # 1. Body ratio
    f_body = min(1.0, candle.body_ratio / cfg.confirmation_body_min)

    # 2. Smoothed momentum — EMA fast/slow spread normalised by ATR
    dir_mult = 1.0 if state.direction == Direction.LONG else -1.0
    mom_delta = (ema_fast - ema_slow) * dir_mult
    f_mom = max(0.0, min(1.0, mom_delta / state.atr_abs)) if state.atr_abs > 0 else 0.0

    # 3. Non-linear distance decay
    rng = state.active_range
    static_ceiling = cfg.retest_depth_max * rng.size
    atr_ceiling = cfg.retest_atr_depth_fraction * state.atr_abs if state.atr_abs > 0 else static_ceiling
    adaptive_ceiling = max(static_ceiling, atr_ceiling)
    if state.direction == Direction.LONG:
        depth = abs(candle.close - rng.l_ref)
    else:
        depth = abs(rng.h_ref - candle.close)
    f_dist = math.exp(-((depth / adaptive_ceiling) ** 2)) if adaptive_ceiling > 0 else 0.0

    # 4. Displacement strength
    disp = state.displacement_candle
    disp_move = abs(disp.close - disp.open) if disp else 0.0
    f_disp = min(1.0, disp_move / (1.5 * state.atr_abs)) if state.atr_abs > 0 else 0.0

    C_linear = (w_body * f_body) + (w_mom * f_mom) + (w_dist * f_dist) + (w_disp * f_disp)
    weak_link = min(f_body, f_mom)
    C = (1.0 - cfg.weak_link_weight) * C_linear + cfg.weak_link_weight * weak_link
    C = max(cfg.conf_floor, C)

    return {
        "f_body": f_body, "f_mom": f_mom, "f_dist": f_dist, "f_disp": f_disp,
        "ema_fast": ema_fast, "ema_slow": ema_slow, "spread": ema_fast - ema_slow,
        "C_linear": C_linear, "weak_link": weak_link, "C": C,
    }


def _tier_bucket(S: float, tier_1: float, tier_2: float) -> str:
    if S >= tier_1:
        return "TIER1"
    if S >= tier_2:
        return "TIER2"
    return "REJECT"


# ─────────────────────────────────────────────────────────────────────────────
# Monkeypatches (process-local only — no edit to src/ on disk)
# ─────────────────────────────────────────────────────────────────────────────

class _ProbeState:
    records: list = []
    first_divergence_idx: int | None = None
    max_c_self_consistency_err: float = 0.0
    n_calls: int = 0


def _install_patches() -> tuple:
    """Returns (restore_fn,). Patches EngineState.update_emas and
    UltronRiskEngine.compute_soft_confirmation on the class objects."""
    orig_update_emas = EngineState.update_emas
    orig_compute_soft_confirmation = UltronRiskEngine.compute_soft_confirmation

    def patched_update_emas(self: EngineState, close: float, fast: int = 2, slow: int = 5) -> None:
        idx = self.current_candle_index
        if not hasattr(self, "_probe_single_last_idx"):
            self._probe_ema_fast_single = 0.0
            self._probe_ema_slow_single = 0.0
            self._probe_single_last_idx = -1
            self._probe_spread_sign_hist: list = []
        if self._probe_single_last_idx != idx:
            if self._probe_single_last_idx == -1:
                # Seed identically to the real EMA's own seeding rule (crt_engine_v2.py:288-290).
                self._probe_ema_fast_single = close
                self._probe_ema_slow_single = close
            else:
                a_f = 2.0 / (fast + 1)
                a_s = 2.0 / (slow + 1)
                self._probe_ema_fast_single = close * a_f + self._probe_ema_fast_single * (1.0 - a_f)
                self._probe_ema_slow_single = close * a_s + self._probe_ema_slow_single * (1.0 - a_s)
            self._probe_single_last_idx = idx

        # Call the REAL update first so we can read its (possibly double-applied) result,
        # then track the double-update spread sign for regime tagging.
        orig_update_emas(self, close, fast=fast, slow=slow)
        spread = self.ema_fast_val - self.ema_slow_val
        sign = 0 if spread == 0 else (1 if spread > 0 else -1)
        hist = self._probe_spread_sign_hist
        if not hist or hist[-1][0] != idx:
            hist.append((idx, sign))
            if len(hist) > _REGIME_WINDOW:
                del hist[0]

    def patched_compute_soft_confirmation(self: UltronRiskEngine, candle, state: EngineState) -> float:
        _ProbeState.n_calls += 1
        C_double_real = orig_compute_soft_confirmation(self, candle, state)

        # Self-consistency check: our pure reimplementation, fed the REAL (double-update)
        # EMA values, must reproduce the real function's output exactly.
        check = _recompute_C(self, candle, state, state.ema_fast_val, state.ema_slow_val)
        err = abs(check["C"] - C_double_real)
        if err > _ProbeState.max_c_self_consistency_err:
            _ProbeState.max_c_self_consistency_err = err

        single_fast = getattr(state, "_probe_ema_fast_single", state.ema_fast_val)
        single_slow = getattr(state, "_probe_ema_slow_single", state.ema_slow_val)
        single = _recompute_C(self, candle, state, single_fast, single_slow)

        G = state.risk_score.final if state.risk_score else 0.0
        cfg = self.config
        S_double = (G ** cfg.conf_alpha) * (C_double_real ** cfg.conf_beta)
        S_single = (G ** cfg.conf_alpha) * (single["C"] ** cfg.conf_beta)

        bucket_double = _tier_bucket(S_double, cfg.tier_1_threshold, cfg.tier_2_threshold)
        bucket_single = _tier_bucket(S_single, cfg.tier_1_threshold, cfg.tier_2_threshold)
        flipped = bucket_double != bucket_single

        idx = state.current_candle_index
        if flipped and _ProbeState.first_divergence_idx is None:
            _ProbeState.first_divergence_idx = idx
        post_divergence = (
            _ProbeState.first_divergence_idx is not None and idx > _ProbeState.first_divergence_idx
        )

        hist = getattr(state, "_probe_spread_sign_hist", [])
        signs = [s for _, s in hist]
        if len(signs) >= 2 and all(s == signs[0] and s != 0 for s in signs):
            regime = "trend"
        else:
            regime = "chop"

        _ProbeState.records.append({
            "candle_index": idx,
            "timestamp": str(getattr(candle, "timestamp", "")),
            "soft_conf_candle_num": state.soft_conf_candles,
            "direction": state.direction.name if hasattr(state.direction, "name") else str(state.direction),
            "atr_abs": state.atr_abs,
            "regime": regime,
            "double": {
                "ema_fast": check["ema_fast"], "ema_slow": check["ema_slow"],
                "f_mom": check["f_mom"], "C": C_double_real, "S": S_double, "tier": bucket_double,
            },
            "single": {
                "ema_fast": single["ema_fast"], "ema_slow": single["ema_slow"],
                "f_mom": single["f_mom"], "C": single["C"], "S": S_single, "tier": bucket_single,
            },
            "shared": {
                "G": G, "f_body": check["f_body"], "f_dist": check["f_dist"], "f_disp": check["f_disp"],
            },
            "flipped": flipped,
            "post_divergence": post_divergence,
            "self_consistency_err": err,
        })
        return C_double_real  # unchanged — live behavior is not altered

    EngineState.update_emas = patched_update_emas
    UltronRiskEngine.compute_soft_confirmation = patched_compute_soft_confirmation

    def _restore():
        EngineState.update_emas = orig_update_emas
        UltronRiskEngine.compute_soft_confirmation = orig_compute_soft_confirmation

    return (_restore,)


# ─────────────────────────────────────────────────────────────────────────────
# Provenance
# ─────────────────────────────────────────────────────────────────────────────

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_provenance() -> dict:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(_ROOT), text=True
        ).strip()
    except Exception:
        sha = None
    try:
        dirty = bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=str(_ROOT), text=True
        ).strip())
    except Exception:
        dirty = None
    return {
        "git_sha": sha,
        "tree_dirty": dirty,
        "note": (
            "tree_dirty=true means untracked/uncommitted files exist alongside git_sha "
            "(see project_untracked_tree_divergence memory) — git_sha does not fully "
            "characterise what ran; treat as best-effort provenance, not a clean pin."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def _summarize(records: list) -> dict:
    trend = [r for r in records if r["regime"] == "trend" and not r["post_divergence"]]
    chop = [r for r in records if r["regime"] == "chop" and not r["post_divergence"]]

    def _mean_ratio(rows):
        ratios = []
        for r in rows:
            s_single = r["single"]["ema_fast"] - r["single"]["ema_slow"]
            s_double = r["double"]["ema_fast"] - r["double"]["ema_slow"]
            if s_single != 0:
                ratios.append(s_double / s_single)
        return round(sum(ratios) / len(ratios), 4) if ratios else None

    return {
        "n_evaluations": len(records),
        "n_trend": len(trend),
        "n_chop": len(chop),
        "n_flipped": sum(1 for r in records if r["flipped"]),
        "n_post_divergence": sum(1 for r in records if r["post_divergence"]),
        "first_divergence_idx": _ProbeState.first_divergence_idx,
        "mean_spread_ratio_double_over_single_trend": _mean_ratio(trend),
        "mean_spread_ratio_double_over_single_chop": _mean_ratio(chop),
        "prediction": {
            "claim": "trend spread compresses under double-update (~0.46x for ema_fast=2/ema_slow=5); "
                     "chop spread inflates (~1.34x)",
            "closed_form_alpha_eff_fast": round(2 * (2.0 / 3) - (2.0 / 3) ** 2, 6),
            "closed_form_alpha_eff_slow": round(2 * (1.0 / 3) - (1.0 / 3) ** 2, 6),
        },
        "max_c_self_consistency_err": _ProbeState.max_c_self_consistency_err,
        "n_compute_soft_confirmation_calls": _ProbeState.n_calls,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv", default=_DEFAULT_CSV)
    p.add_argument("--instrument", default=_DEFAULT_INSTRUMENT)
    p.add_argument("--output", default=str(_ROOT / "results" / "analysis" / "soft_conf_ema_probe_run"))
    args = p.parse_args()

    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    (restore,) = _install_patches()
    try:
        crt_cfg = load_prod_config_from_registry(PROD_VERSION, args.instrument)
        cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
        cfg.instrument = args.instrument
        cfg.pip_size = MultiInstrumentRunner.INSTRUMENT_PIP.get(args.instrument, 0.0001)
        loader = CandleLoader(args.csv, args.instrument)
        runner = BacktestRunner(
            cfg, csv_path=args.csv,
            overrides={"diagnostic": "soft_conf_ema_double_update_probe"},
        )
        runner.run(loader.stream(), loader.count(), args.output)
    finally:
        restore()

    records = _ProbeState.records
    summary = _summarize(records)

    artifact = {
        "artifact": "soft_conf_ema_double_update_probe",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "instrument": args.instrument,
        "csv_path": args.csv,
        "csv_sha256": _sha256_file(Path(args.csv)),
        "config_version": PROD_VERSION,
        "config_ema_fast": crt_cfg.ema_fast,
        "config_ema_slow": crt_cfg.ema_slow,
        "config_conf_weights": list(crt_cfg.conf_weights),
        "config_weak_link_weight": crt_cfg.weak_link_weight,
        "provenance": _git_provenance(),
        "summary": summary,
        "records": records,
        "exactness_boundary": (
            "Records with post_divergence=true are computed from a state trajectory the real "
            "(double-update) engine produced, NOT from a genuine single-update rerun — indicative "
            "only, not a measurement. See first_divergence_idx in summary."
        ),
    }

    with open(_ARTIFACT_JSON, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, default=str)

    md = _render_md(artifact)
    with open(_ARTIFACT_MD, "w", encoding="utf-8") as f:
        f.write(md)

    safe_print(md)
    safe_print(f"\nArtifact: {_ARTIFACT_JSON.relative_to(_ROOT)}")
    return 0


def _render_md(a: dict) -> str:
    s = a["summary"]
    lines = [
        "# Soft-Confirmation Double EMA Update Probe",
        "",
        f"**Instrument:** {a['instrument']}  **Config:** {a['config_version']}  "
        f"**CSV SHA256:** {a['csv_sha256'][:16]}...",
        f"**git_sha:** {a['provenance']['git_sha']}  **tree_dirty:** {a['provenance']['tree_dirty']}",
        "",
        "## Result",
        f"- compute_soft_confirmation() calls: {s['n_compute_soft_confirmation_calls']}",
        f"- Evaluations recorded: {s['n_evaluations']} (trend={s['n_trend']}, chop={s['n_chop']})",
        f"- Tier-bucket flips (double vs single): {s['n_flipped']}",
        f"- first_divergence_idx: {s['first_divergence_idx']}",
        f"- post_divergence evaluations (indicative only): {s['n_post_divergence']}",
        "",
        "## Prediction check",
        f"- claim: {s['prediction']['claim']}",
        f"- mean spread ratio (double/single), trend-only, pre-divergence: "
        f"{s['mean_spread_ratio_double_over_single_trend']}",
        f"- mean spread ratio (double/single), chop-only, pre-divergence: "
        f"{s['mean_spread_ratio_double_over_single_chop']}",
        f"- closed-form alpha_eff (fast/slow): "
        f"{s['prediction']['closed_form_alpha_eff_fast']} / {s['prediction']['closed_form_alpha_eff_slow']}",
        "",
        "## Self-consistency (probe reimplementation vs real compute_soft_confirmation)",
        f"- max |C_reimplemented - C_real| over all calls: {s['max_c_self_consistency_err']:.2e}",
        "",
        "## Exactness boundary",
        a["exactness_boundary"],
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
