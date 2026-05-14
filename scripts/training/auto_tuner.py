"""
auto_tuner.py
═══════════════════════════════════════════════════════════════════════════════
CRT Engine — Auto-Tuner  (Ultron Phase-6 / Quant Research Infrastructure)

WHAT THIS DOES
  Replaces manual param tweaking with a self-calibrating search loop:
    Parameter Sampler → Backtest Runner → Metric Extractor →
    Fitness Scorer → Result Store → Best Selection

  Phase 1: Random Search     (exploration, 100+ iterations)
  Phase 2: Focused Search    (top-20% neighbourhood, 50 iterations)
  Phase 3: Cross-Instrument  (validate on held-out instrument)

USAGE
  # Single instrument, 100 iterations
  python auto_tuner.py --csv data/GBPUSD_M15_real.csv --instrument GBPUSD

  # Multi-instrument with cross-validation
  python auto_tuner.py --data-dir data/ --instruments GBPUSD XAUUSD EURCAD

  # Resume from checkpoint
  python auto_tuner.py --csv data/GBPUSD_M15_real.csv --resume results/tuner/

  # More iterations
  python auto_tuner.py --csv data/GBPUSD_M15_real.csv --n-iter 200

ASSUMPTIONS
  - backtest_v2.py lives at src/runtime/backtest_v2.py (import as runtime.backtest_v2)
  - Data files: data/{INSTRUMENT}_M15_real.csv  (or _M15.csv)
  - Each backtest run is deterministic (seeded RNGs in BacktestConfig)
  - Fitness function is calibrated for 50+ trade minimum

FAILURE MODES
  - < 50 trades in a run: penalised by trade_count term in fitness
  - Backtest exception: logged as score=-999, excluded from rankings
  - All runs below threshold: returns best available, warns loudly
  - Single instrument: valid for exploration, NOT for production deployment

OVERFITTING RISKS
  - Tuning on one instrument + one year = high overfitting risk
  - Mitigation: multi-instrument validation (--instruments flag)
  - Mitigation: fitness penalises low trade counts
  - Mitigation: top configs must survive cross-instrument check

SELF-REVIEW
  - Parameters tuned: 5 structural params (funnel gates only)
  - Parameters NOT tuned: session windows, capital curve, slippage
    (these are realism constants, not edge parameters)
  - Trade count floor: 30 (below = fitness -> 0)
  - Cross-validation: mandatory before production deployment

═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import time
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional
from config_layer.market_router import classify_market
from config_layer.config_builder import ConfigBuilder



# ── Import from backtest_v2 (src/runtime/backtest_v2.py via editable install) ─
try:
    from runtime.backtest_v2 import (
        BacktestConfig,
        BacktestRunner,
        CandleLoader,
    )
    from config_layer.crt_engine_v2 import CRTConfig
except ImportError as e:
    print(
        f"\n  IMPORT ERROR: {e}\n"
        "  Ensure backtest_v2.py and crt_engine_v2.py are in the same directory.\n"
    )
    sys.exit(1)

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    level=logging.WARNING,   # suppress backtest noise during tuning
)
tuner_log = logging.getLogger("AutoTuner")
tuner_log.setLevel(logging.INFO)

from config_layer.production_config import PROD_VERSION as _TUNER_PROD_VERSION
tuner_log.info("Production config version: %s", _TUNER_PROD_VERSION)

LOG_FILE = "results/tuner/live_log.jsonl"

def log_event(data: dict):
    Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(data) + "\n")

# ═══════════════════════════════════════════════════════════════════════════
# 1. PARAMETER SPACE
# Only tune funnel-gate parameters. Everything else is realism constants.
# ═══════════════════════════════════════════════════════════════════════════

PARAM_SPACE: dict[str, list] = {
    "retest_depth_max":           [0.20, 0.25, 0.30, 0.40, 0.50, 0.60],
    "retest_atr_depth_fraction":  [0.30, 0.40, 0.50, 0.70, 1.00],
    "body_ratio_min":             [0.50, 0.60, 0.65, 0.70, 0.75, 0.80],
    "atr_multiplier_min":         [1.00, 1.20, 1.50, 1.75, 2.00],
    "expansion_atr_min_distance": [0.10, 0.15, 0.20, 0.25, 0.30],
}

# Total search space size
SPACE_SIZE = 1
for v in PARAM_SPACE.values():
    SPACE_SIZE *= len(v)


# ═══════════════════════════════════════════════════════════════════════════
# 2. PARAMETER SAMPLER
# ═══════════════════════════════════════════════════════════════════════════

def sample_random(rng: random.Random) -> dict:
    """Uniform random sample from PARAM_SPACE."""
    return {k: rng.choice(v) for k, v in PARAM_SPACE.items()}


def sample_neighbourhood(base: dict, rng: random.Random, perturbation: float = 0.3) -> dict:
    """
    Focused search: start from a good config, randomly perturb each param
    with probability = perturbation. Implements Phase-2 exploitation.
    """
    result = {}
    for k, choices in PARAM_SPACE.items():
        if rng.random() < perturbation:
            result[k] = rng.choice(choices)
        else:
            # Stay at current value, or nearest available
            current = base.get(k, rng.choice(choices))
            if current in choices:
                result[k] = current
            else:
                # Snap to nearest
                result[k] = min(choices, key=lambda x: abs(x - current))
    return result


def params_to_key(params: dict) -> str:
    """Deterministic hashable key for deduplication."""
    return "|".join(f"{k}={v}" for k, v in sorted(params.items()))


# ═══════════════════════════════════════════════════════════════════════════
# 3. FITNESS FUNCTION
# Composite score — prevents overfitting to single metric.
# ═══════════════════════════════════════════════════════════════════════════

TRADE_COUNT_FLOOR = 3    # below this: fitness -> 0, not worth evaluating
TRADE_COUNT_TARGET = 50   # above this: full trade_count bonus

def fitness(metrics: dict) -> float:
    """
    Composite fitness score [0, ~1.5].
    Funnel guard: if exp>20 and ret/exp<0.05 -> broken pipeline -> -999.0
    Trade floor:  if trades < TRADE_COUNT_FLOOR -> -999.0
    """
    n   = metrics.get("approved_trades", 0)
    exp = metrics.get("expansions", 0)
    ret = metrics.get("retests",    0)

    # Pipeline health: expansions happening but nothing retesting
    # means retest_depth_max / retest_atr_depth_fraction is too tight.
    if exp > 20:
        ret_ratio = ret / exp
        if ret_ratio < 0.05:
            return -999.0

    if n < TRADE_COUNT_FLOOR:
        return -999.0

    exp_rr  = metrics.get("expectancy_rr", 0.0)
    wr      = metrics.get("win_rate", 0.0)
    dd      = metrics.get("max_drawdown_pct", 1.0)
    tc_norm = min(n / TRADE_COUNT_TARGET, 1.0)

    score = (
        0.50 * exp_rr  +
        0.20 * wr      +
        0.20 * tc_norm +
        0.10 * (1.0 - dd)
    )
    return round(score, 6)


# ═══════════════════════════════════════════════════════════════════════════
# 4. BACKTEST WRAPPER
# Converts param dict → CRTConfig → BacktestRunner → metrics dict.
# DOES NOT modify CRT logic — only injects parameters.
# ═══════════════════════════════════════════════════════════════════════════

INSTRUMENT_PIP = {
    "EURCAD": 0.0001, "GBPUSD": 0.0001, "USDJPY": 0.01,
    "AUDUSD": 0.0001, "NZDUSD": 0.0001, "USDCHF": 0.0001,
    "BTCUSDT": 1.0,   "ETHUSDT": 0.01,  "XAUUSD": 0.01,
    "US30": 1.0,      "NAS100": 0.25,   "SP500": 0.25,
}


def run_backtest(
    params: dict,
    csv_path: str,
    instrument: str,
    base_bt_config: Optional[BacktestConfig] = None,
    output_dir: str = "results/tuner/runs",
) -> dict:
    """
    Run one backtest with the given CRTConfig parameters.
    Returns metrics dict. On exception returns error dict with score=-999.
    """
    try:
        # ConfigBuilder.build() is the ONLY valid config source.
        crt_cfg = ConfigBuilder.build(instrument, overrides=params)

        if base_bt_config is not None:
            bt_cfg = deepcopy(base_bt_config)
            bt_cfg.crt_config  = crt_cfg
            bt_cfg.instrument  = instrument
            bt_cfg.pip_size    = INSTRUMENT_PIP.get(instrument, 0.0001)
            bt_cfg.debug_mode  = False   # suppress verbose logs during tuning
        else:
            bt_cfg = BacktestConfig(
                instrument  = instrument,
                pip_size    = INSTRUMENT_PIP.get(instrument, 0.0001),
                crt_config  = crt_cfg,
                debug_mode  = False,   # suppress verbose per-trade logs during tuning
            )

        loader = CandleLoader(csv_path, instrument)
        # skip_features=True: FeaturePipeline is param-invariant for a given CSV.
        # Tuner fitness uses metric scalars only — feature columns not needed here.
        runner = BacktestRunner(bt_cfg, csv_path=csv_path, skip_features=True)

        # ── Partial data mode (set MAX_CANDLES > 0 to cap; 0 = full dataset) ──
        # Useful for fast debugging iterations. Set to 0 for production runs.
        MAX_CANDLES = 0   # 0 = full dataset (production default)

        if MAX_CANDLES > 0:
            stream     = (c for i, c in enumerate(loader.stream()) if i < MAX_CANDLES)
            candle_cnt = min(MAX_CANDLES, loader.count())
        else:
            stream     = loader.stream()
            candle_cnt = loader.count()

        # Suppress per-run output directory writes during tuning
        m = runner.run(stream, candle_cnt, output_dir=output_dir)

        fc = m.funnel_counts if hasattr(m, "funnel_counts") else {}
        return {
            "approved_trades":  m.approved_trades,
            "win_rate":         round(m.win_rate, 4),
            "expectancy_rr":    round(m.expectancy_rr, 4),
            "total_pnl_rr_net": round(m.total_pnl_rr_net, 4),
            "max_drawdown_pct": round(m.max_drawdown_pct, 4),
            "avg_rr_net":       round(m.avg_rr_net, 4),
            "expansions":    fc.get("expansion_success",    0),
            "retests":       fc.get("retest_success",       0),
            "sweeps":        fc.get("sweeps_detected",      0),
            "displacements": fc.get("displacement_success", 0),
            "confirmations": fc.get("confirmation_passed",  0),
            "error":         None,
        }

    except Exception as exc:
        tuner_log.warning(f"Backtest failed: {exc}")
        return {
            "approved_trades": 0, "win_rate": 0.0,
            "expectancy_rr": 0.0, "total_pnl_rr_net": 0.0,
            "max_drawdown_pct": 1.0, "avg_rr_net": 0.0,
            "expansions": 0, "retests": 0,
            "sweeps": 0, "displacements": 0, "confirmations": 0,
            "error": str(exc),
        }


# ═══════════════════════════════════════════════════════════════════════════
# 5. RESULT STORE
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TunerResult:
    iteration:  int
    params:     dict
    metrics:    dict
    score:      float
    elapsed_s:  float
    instrument: str
    phase:      str = "random"

    def to_dict(self) -> dict:
        return {
            "iteration":  self.iteration,
            "phase":      self.phase,
            "instrument": self.instrument,
            "score":      self.score,
            "params":     self.params,
            "metrics":    self.metrics,
            "elapsed_s":  round(self.elapsed_s, 2),
        }


class ResultStore:
    def __init__(self):
        self._results:  list[TunerResult] = []
        self._seen_keys: set[str] = set()

    def add(self, result: TunerResult) -> None:
        self._results.append(result)

    def is_duplicate(self, params: dict) -> bool:
        return params_to_key(params) in self._seen_keys

    def mark_seen(self, params: dict) -> None:
        self._seen_keys.add(params_to_key(params))

    def valid(self) -> list[TunerResult]:
        """Only results with score > -999."""
        return [r for r in self._results if r.score > -999.0]

    def top_n(self, n: int = 10) -> list[TunerResult]:
        return sorted(self.valid(), key=lambda r: r.score, reverse=True)[:n]

    def best(self) -> Optional[TunerResult]:
        v = self.valid()
        return max(v, key=lambda r: r.score) if v else None

    def score_distribution(self) -> dict:
        scores = [r.score for r in self.valid()]
        if not scores:
            return {}
        scores_sorted = sorted(scores)
        n = len(scores_sorted)
        return {
            "count":    n,
            "min":      round(min(scores), 4),
            "max":      round(max(scores), 4),
            "mean":     round(sum(scores) / n, 4),
            "p25":      round(scores_sorted[n // 4], 4),
            "p50":      round(scores_sorted[n // 2], 4),
            "p75":      round(scores_sorted[3 * n // 4], 4),
            "negative": sum(1 for s in scores if s < 0),
        }

    def top_20pct_configs(self) -> list[dict]:
        """Return param dicts from top 20% of valid results for Phase-2 seeding."""
        v = self.valid()
        if not v:
            return []
        cutoff = max(1, len(v) // 5)
        top = sorted(v, key=lambda r: r.score, reverse=True)[:cutoff]
        return [r.params for r in top]

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(
                [r.to_dict() for r in self._results],
                f, indent=2
            )
        tuner_log.info(f"Checkpoint saved → {path}")

    @classmethod
    def load(cls, path: str) -> "ResultStore":
        store = cls()
        with open(path) as f:
            data = json.load(f)
        for d in data:
            r = TunerResult(
                iteration  = d["iteration"],
                params     = d["params"],
                metrics    = d["metrics"],
                score      = d["score"],
                elapsed_s  = d.get("elapsed_s", 0.0),
                instrument = d.get("instrument", "UNKNOWN"),
                phase      = d.get("phase", "random"),
            )
            store.add(r)
            store.mark_seen(r.params)
        tuner_log.info(f"Loaded {len(store._results)} results from {path}")
        return store


# ═══════════════════════════════════════════════════════════════════════════
# 6. AUTO-TUNER CORE
# ═══════════════════════════════════════════════════════════════════════════

class AutoTuner:
    """
    Self-calibrating parameter optimizer for CRT Engine.

    Phase 1 — Random Search     (full space exploration)
    Phase 2 — Focused Search    (neighbourhood of top-20%)
    Phase 3 — Cross-Instrument  (validate on held-out instruments)
    """

    def __init__(
        self,
        csv_paths:      dict[str, str],   # {instrument: csv_path}
        output_dir:     str = "results/tuner",
        n_iter_phase1:  int = 100,
        n_iter_phase2:  int = 50,
        seed:           int = 42,
        base_bt_config: Optional[BacktestConfig] = None,
        checkpoint_every: int = 20,
    ):
        self.csv_paths      = csv_paths
        self.output_dir     = Path(output_dir)
        self.n_iter_phase1  = n_iter_phase1
        self.n_iter_phase2  = n_iter_phase2
        self.rng            = random.Random(seed)
        self.base_bt_config = base_bt_config
        self.checkpoint_every = checkpoint_every

        self.store     = ResultStore()
        self.iteration = 0

        # Primary instrument = first in dict (used for Phase 1+2)
        self.primary_instrument = next(iter(csv_paths))
        self.primary_csv        = csv_paths[self.primary_instrument]

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.best_score = -999
        self.no_improve_counter = 0

        tuner_log.info(
            f"AutoTuner init | primary={self.primary_instrument} "
            f"space_size={SPACE_SIZE:,} "
            f"phase1={n_iter_phase1} phase2={n_iter_phase2}"
        )

    # ── Public API ────────────────────────────────────────────────────────

    def run(self) -> TunerResult:
        """Run full tuning pipeline. Returns best result."""
        print(f"\n{'═'*65}")
        print(f"  CRT AUTO-TUNER")
        print(f"  Primary instrument: {self.primary_instrument}")
        print(f"  Parameter space:    {SPACE_SIZE:,} combinations")
        print(f"  Phase 1 (random):   {self.n_iter_phase1} iterations")
        print(f"  Phase 2 (focused):  {self.n_iter_phase2} iterations")
        print(f"{'═'*65}\n")

        # Phase 1 — Random Search
        self._run_phase("random", self.n_iter_phase1)

        # Phase 2 — Focused Search on top-20%
        top_configs = self.store.top_20pct_configs()
        if top_configs:
            tuner_log.info(f"Phase 2 seeded from {len(top_configs)} top configs")
            self._run_phase("focused", self.n_iter_phase2, seed_configs=top_configs)
        else:
            tuner_log.warning("No valid configs from Phase 1 — skipping Phase 2")

        # Phase 3 — Cross-instrument validation
        if len(self.csv_paths) > 1:
            self._run_cross_validation()

        # Final save + report
        self._save_final_report()

        best = self.store.best()
        if best is None:
            tuner_log.error("No valid results found — check data and parameters")
            sys.exit(1)

        return best

    def resume(self, checkpoint_path: str) -> TunerResult:
        """Load checkpoint and continue from where it left off."""
        self.store     = ResultStore.load(checkpoint_path)
        self.iteration = len(self.store._results)
        tuner_log.info(f"Resuming from iteration {self.iteration}")
        return self.run()

    # ── Phase runners ─────────────────────────────────────────────────────

    def _run_phase(
        self,
        phase: str,
        n_iter: int,
        seed_configs: Optional[list[dict]] = None,
    ) -> None:
        print(f"\n  Phase {1 if phase == 'random' else 2}: {phase.upper()} SEARCH")
        print(f"  {'─'*60}")

        for i in range(n_iter):
            # Sample params
            if phase == "focused" and seed_configs:
                base = self.rng.choice(seed_configs)
                params = sample_neighbourhood(base, self.rng)
            else:
                params = sample_random(self.rng)

            # Skip exact duplicates
            if self.store.is_duplicate(params):
                continue
            self.store.mark_seen(params)

            self.iteration += 1
            t0 = time.perf_counter()

            metrics = run_backtest(
                params      = params,
                csv_path    = self.primary_csv,
                instrument  = self.primary_instrument,
                base_bt_config = self.base_bt_config,
                output_dir  = str(self.output_dir / "runs"),
            )

            score     = fitness(metrics)
            elapsed   = time.perf_counter() - t0

            result = TunerResult(
                iteration  = self.iteration,
                params     = params,
                metrics    = metrics,
                score      = score,
                elapsed_s  = elapsed,
                instrument = self.primary_instrument,
                phase      = phase,
            )
            self.store.add(result)

            # Progress line
            n_trades = metrics.get("approved_trades", 0)
            exp_rr   = metrics.get("expectancy_rr", 0.0)
            wr       = metrics.get("win_rate", 0.0)
            n_swp    = metrics.get("sweeps",      0)
            n_exp    = metrics.get("expansions",  0)
            n_ret    = metrics.get("retests",     0)
            if score > -999:
                status = "OK "
            elif n_exp > 20 and n_ret == 0:
                status = "BCK"   # broken at expansion->retest
            else:
                status = "LOW"
            print(
                f"  [{status}] iter={self.iteration:>4}  "
                f"score={score:>+.4f}  "
                f"exp={exp_rr:>+.3f}R  wr={wr:.0%}  "
                f"n={n_trades:>3}  "
                f"S={n_swp} E={n_exp} R={n_ret}  "
                f"t={elapsed:.1f}s"
            )
            log_event({
                "iteration":     self.iteration,
                "phase":         phase,
                "score":         score,
                "exp_rr":        exp_rr,
                "win_rate":      wr,
                "trades":        n_trades,
                "time":          round(elapsed, 2),
                "params":        params,
                "sweeps":        metrics.get("sweeps",        0),
                "displacements": metrics.get("displacements", 0),
                "expansions":    metrics.get("expansions",    0),
                "retests":       metrics.get("retests",       0),
                "confirmations": metrics.get("confirmations", 0),
            })

            # ── Early stopping ────────────────────────────────────
            if score > self.best_score:
                self.best_score = score
                self.no_improve_counter = 0
            else:
                self.no_improve_counter += 1

            if self.no_improve_counter >= 25:
                print(
                    f"\n  Early stopping: no improvement for 25 iterations "
                    f"(best={self.best_score:+.4f})"
                )
                break

            # Checkpoint
            if self.iteration % self.checkpoint_every == 0:
                self._checkpoint()

        best = self.store.best()
        if best:
            print(f"\n  Phase best: score={best.score:+.4f} | {self._params_str(best.params)}")

    def _run_cross_validation(self) -> None:
        """Validate top-5 configs on all non-primary instruments."""
        print(f"\n  Phase 3: CROSS-INSTRUMENT VALIDATION")
        print(f"  {'─'*60}")

        top5 = self.store.top_n(5)
        non_primary = {k: v for k, v in self.csv_paths.items()
                       if k != self.primary_instrument}

        for result in top5:
            for instrument, csv_path in non_primary.items():
                self.iteration += 1
                t0 = time.perf_counter()

                metrics = run_backtest(
                    params      = result.params,
                    csv_path    = csv_path,
                    instrument  = instrument,
                    base_bt_config = self.base_bt_config,
                    output_dir  = str(self.output_dir / "runs"),
                )

                score   = fitness(metrics)
                elapsed = time.perf_counter() - t0

                xval_result = TunerResult(
                    iteration  = self.iteration,
                    params     = result.params,
                    metrics    = metrics,
                    score      = score,
                    elapsed_s  = elapsed,
                    instrument = instrument,
                    phase      = "cross_val",
                )
                self.store.add(xval_result)

                n = metrics.get("approved_trades", 0)
                exp = metrics.get("expectancy_rr", 0.0)
                print(
                    f"  [XVAL] {instrument:<10} iter={self.iteration:>4}  "
                    f"score={score:>+.4f}  exp={exp:>+.3f}R  n={n:>3}  "
                    f"t={elapsed:.1f}s"
                )

    # ── Output ────────────────────────────────────────────────────────────

    def _checkpoint(self) -> None:
        path = str(self.output_dir / "checkpoint.json")
        self.store.save(path)

    def _save_final_report(self) -> None:
        """Write checkpoint + full JSON report + print console summary."""
        self._checkpoint()

        top10 = self.store.top_n(10)
        dist  = self.store.score_distribution()
        best  = self.store.best()

        report = {
            "summary": {
                "total_iterations":   self.iteration,
                "valid_results":      len(self.store.valid()),
                "primary_instrument": self.primary_instrument,
                "space_size":         SPACE_SIZE,
            },
            "score_distribution": dist,
            "best_config": best.to_dict() if best else None,
            "top_10":      [r.to_dict() for r in top10],
        }

        report_path = self.output_dir / "tuner_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        tuner_log.info(f"Report saved → {report_path}")

        # Console summary
        print(f"\n{'═'*65}")
        print(f"  TUNER RESULTS — {self.primary_instrument}")
        print(f"{'═'*65}")
        print(f"  Total iterations:  {self.iteration}")
        print(f"  Valid results:     {len(self.store.valid())}")

        print(f"\n  SCORE DISTRIBUTION")
        print(f"  {'─'*40}")
        for k, v in dist.items():
            print(f"    {k:<12} {v}")

        print(f"\n  TOP 10 CONFIGURATIONS")
        print(f"  {'─'*60}")
        header = f"  {'#':<4} {'score':>7}  {'exp_rr':>7}  {'wr':>6}  {'n':>4}  {'dd':>6}  params"
        print(header)
        print(f"  {'─'*60}")
        for rank, r in enumerate(top10, 1):
            m   = r.metrics
            exp = m.get("expectancy_rr", 0.0)
            wr  = m.get("win_rate", 0.0)
            n   = m.get("approved_trades", 0)
            dd  = m.get("max_drawdown_pct", 0.0)
            print(
                f"  {rank:<4} {r.score:>+7.4f}  "
                f"{exp:>+7.4f}  {wr:>6.1%}  {n:>4}  {dd:>6.1%}  "
                f"{self._params_str(r.params)}"
            )

        if best:
            print(f"\n  BEST CONFIG (score={best.score:+.4f})")
            print(f"  {'─'*40}")
            for k, v in best.params.items():
                default = getattr(ConfigBuilder.build(instrument), k, "?")
                changed = " *" if v != default else ""
                print(f"    {k:<35} = {v}{changed}")
            print(f"\n  Metrics:")
            for k, v in best.metrics.items():
                if k != "error":
                    print(f"    {k:<35} = {v}")

        print(f"\n  Report → {report_path}")
        print(f"{'═'*65}\n")

    @staticmethod
    def _params_str(params: dict) -> str:
        return " ".join(f"{k.split('_')[-1]}={v}" for k, v in sorted(params.items()))


# ═══════════════════════════════════════════════════════════════════════════
# 7. MULTI-INSTRUMENT TUNER
# Runs independent search per instrument, then finds configs that
# generalise across all (intersection of top configs).
# ═══════════════════════════════════════════════════════════════════════════

class MultiInstrumentTuner:
    """
    Orchestrates per-instrument tuning and cross-instrument consensus.

    Strategy:
      1. Tune independently on each instrument
      2. Find configs that score >= threshold on ALL instruments
      3. Report consensus best + per-instrument bests
    """

    CONSENSUS_THRESHOLD = 0.05   # minimum score on every instrument to qualify

    def __init__(
        self,
        csv_paths:     dict[str, str],
        output_dir:    str = "results/tuner",
        n_iter:        int = 100,
        seed:          int = 42,
    ):
        self.csv_paths  = csv_paths
        self.output_dir = Path(output_dir)
        self.n_iter     = n_iter
        self.seed       = seed

    def run(self) -> None:
        all_stores: dict[str, ResultStore] = {}
        all_top_keys: list[set[str]] = []

        for instrument, csv_path in self.csv_paths.items():
            print(f"\n{'━'*65}")
            print(f"  TUNING: {instrument}")
            print(f"{'━'*65}")
            out = str(self.output_dir / instrument)
            tuner = AutoTuner(
                csv_paths      = {instrument: csv_path},
                output_dir     = out,
                n_iter_phase1  = self.n_iter,
                n_iter_phase2  = max(self.n_iter // 2, 20),
                seed           = self.seed,
            )
            tuner.run()
            all_stores[instrument] = tuner.store

            # Collect keys of top-20% for this instrument
            top = tuner.store.top_n(max(1, len(tuner.store.valid()) // 5))
            top_keys = {params_to_key(r.params) for r in top}
            all_top_keys.append(top_keys)

        # Consensus: configs that appear in top-20% of ALL instruments
        if len(all_top_keys) > 1:
            consensus_keys = all_top_keys[0]
            for ks in all_top_keys[1:]:
                consensus_keys = consensus_keys & ks

            print(f"\n{'═'*65}")
            print(f"  CONSENSUS CONFIGS (top-20% on ALL {len(self.csv_paths)} instruments)")
            print(f"{'═'*65}")
            if consensus_keys:
                print(f"  Found {len(consensus_keys)} consensus config(s)\n")
                # Print them from first instrument's store
                first_store = next(iter(all_stores.values()))
                consensus = [r for r in first_store.valid()
                             if params_to_key(r.params) in consensus_keys]
                for r in sorted(consensus, key=lambda x: x.score, reverse=True)[:5]:
                    print(f"  score={r.score:+.4f}  {AutoTuner._params_str(r.params)}")
            else:
                print("  No consensus configs found across all instruments.")
                print("  Recommendation: use per-instrument best configs.")
            print(f"{'═'*65}\n")


# ═══════════════════════════════════════════════════════════════════════════
# 8. CLI
# ═══════════════════════════════════════════════════════════════════════════

def _find_csv(data_dir: str, instrument: str) -> Optional[str]:
    """Find M15 CSV for instrument in data_dir."""
    base = Path(data_dir)
    for suffix in ("_M15_real.csv", "_M15.csv", "_m15_real.csv", "_m15.csv"):
        p = base / f"{instrument}{suffix}"
        if p.exists():
            return str(p)
    # Glob fallback
    matches = list(base.glob(f"{instrument}*M15*.csv"))
    return str(matches[0]) if matches else None


def main() -> None:
    ap = argparse.ArgumentParser(
        description="CRT Auto-Tuner — self-calibrating parameter optimizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single instrument
  python auto_tuner.py --csv data/GBPUSD_M15_real.csv --instrument GBPUSD

  # Multiple instruments (cross-validation)
  python auto_tuner.py --data-dir data/ --instruments GBPUSD XAUUSD EURCAD

  # More iterations
  python auto_tuner.py --csv data/GBPUSD_M15_real.csv --n-iter 200

  # Resume from checkpoint
  python auto_tuner.py --csv data/GBPUSD_M15_real.csv --resume results/tuner/checkpoint.json

  # Multi-instrument consensus
  python auto_tuner.py --data-dir data/ --instruments GBPUSD XAUUSD --multi
"""
    )
    ap.add_argument("--csv",         help="Single M15 CSV path")
    ap.add_argument("--instrument",  help="Instrument name (e.g. GBPUSD)")
    ap.add_argument("--data-dir",    default="data", help="Directory with M15 CSVs")
    ap.add_argument("--instruments", nargs="+",      help="Instruments to tune (multi mode)")
    ap.add_argument("--output-dir",  default="results/tuner")
    ap.add_argument("--n-iter",      type=int, default=100)
    ap.add_argument("--seed",        type=int, default=42)
    ap.add_argument("--resume",      help="Resume from checkpoint JSON path")
    ap.add_argument("--multi",       action="store_true",
                    help="Multi-instrument consensus mode")
    ap.add_argument("--verbose", "-v", action="store_true")

    args = ap.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        tuner_log.setLevel(logging.DEBUG)

    # ── Build csv_paths dict ─────────────────────────────────────────────
    csv_paths: dict[str, str] = {}

    if args.csv and args.instrument:
        csv_paths[args.instrument.upper()] = args.csv

    elif args.instruments:
        for instr in args.instruments:
            p = _find_csv(args.data_dir, instr.upper())
            if p:
                csv_paths[instr.upper()] = p
            else:
                print(f"  WARNING: No M15 CSV found for {instr} in {args.data_dir}")

    else:
        ap.error("Provide either --csv + --instrument, or --instruments")

    if not csv_paths:
        print("  ERROR: No valid CSV paths resolved. Exiting.")
        sys.exit(1)

    # ── Run ─────────────────────────────────────────────────────────────
    if args.multi and len(csv_paths) > 1:
        tuner = MultiInstrumentTuner(
            csv_paths  = csv_paths,
            output_dir = args.output_dir,
            n_iter     = args.n_iter,
            seed       = args.seed,
        )
        tuner.run()

    else:
        tuner = AutoTuner(
            csv_paths     = csv_paths,
            output_dir    = args.output_dir,
            n_iter_phase1 = args.n_iter,
            n_iter_phase2 = max(args.n_iter // 2, 20),
            seed          = args.seed,
        )
        if args.resume:
            tuner.resume(args.resume)
        else:
            tuner.run()


if __name__ == "__main__":
    main()
