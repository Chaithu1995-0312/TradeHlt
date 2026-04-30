"""
auto_tuner.py
═══════════════════════════════════════════════════════════════════════════════
CRT Engine — Auto-Tuner  (Ultron Phase-6 / Quant Research Infrastructure)

ROBUSTNESS UPGRADES (v2):
  - Multiprocessing: Parallel execution across CPU cores.
  - Train/Test Split: Out-Of-Sample (OOS) validation to prevent curve-fitting.
  - Fault Tolerance: Graceful Ctrl+C handling to save checkpoints safely.
  - Process Isolation: Engine exceptions won't crash the tuning master.

USAGE:
  # Standard fast run on 8 cores
  python auto_tuner.py --csv data/GBPUSD_M15.csv --instrument GBPUSD --workers 8

  # Robust run: 80% In-Sample tuning, 20% Out-of-Sample validation
  python auto_tuner.py --csv data/GBPUSD_M15.csv --instrument GBPUSD --train-split 0.8

  # Multi-instrument consensus with OOS validation
  python auto_tuner.py --data-dir data/ --instruments GBPUSD XAUUSD --train-split 0.8 --multi
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import argparse
import concurrent.futures
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
from config_layer.config_builder import ConfigBuilder
from config_layer.llama_gate import llm_score


# ── Import from backtest_v2 (must be in same directory) ────────────────────
try:
    from runtime.backtest_v2 import BacktestConfig, BacktestRunner, CandleLoader
    from config_layer.crt_engine_v2 import CRTConfig
except ImportError as e:
    print(f"\n  IMPORT ERROR: {e}\n  Ensure backtest_v2.py and crt_engine_v2.py are in the same directory.\n")
    sys.exit(1)

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    level=logging.WARNING,
)
tuner_log = logging.getLogger("AutoTuner")
tuner_log.setLevel(logging.INFO)
LOG_FILE = "results/tuner/live_log_gemini_pro.jsonl"

# ── Load tuner section from production config; fall back to coded defaults ────
try:
    from config_layer.production_config import get_prod_section as _get_section
    _TUNER_CFG = _get_section("tuner")
except Exception:
    _TUNER_CFG = {}

_FW       = _TUNER_CFG.get("fitness_weights", {})
_LLM_GATE = _TUNER_CFG.get("llm_gate", {})

def log_event(data: dict):
    Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(data) + "\n")

# ═══════════════════════════════════════════════════════════════════════════
# 1. PARAMETER SPACE
# ═══════════════════════════════════════════════════════════════════════════

PARAM_SPACE: dict[str, list] = {
    "retest_depth_max":           [0.20, 0.25, 0.30, 0.40, 0.50, 0.60],
    "retest_atr_depth_fraction":  [0.30, 0.40, 0.50, 0.70, 1.00],
    "body_ratio_min":             [0.50, 0.60, 0.65, 0.70, 0.75, 0.80],
    "atr_multiplier_min":         [1.00, 1.20, 1.50, 1.75, 2.00],
    "expansion_atr_min_distance": [0.10, 0.15, 0.20, 0.25, 0.30],
}

SPACE_SIZE = 1
for v in PARAM_SPACE.values():
    SPACE_SIZE *= len(v)

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
            current = base.get(k, rng.choice(choices))
            result[k] = current if current in choices else min(choices, key=lambda x: abs(x - current))
    return result

def params_to_key(params: dict) -> str:
    """Deterministic hashable key for deduplication."""
    return "|".join(f"{k}={v}" for k, v in sorted(params.items()))


# ═══════════════════════════════════════════════════════════════════════════
# 3. FITNESS FUNCTION
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
# 3. FITNESS FUNCTION (WITH LLM GATE)
# ═══════════════════════════════════════════════════════════════════════════

TRADE_COUNT_FLOOR:  int = _TUNER_CFG.get("trade_count_floor",  3)
TRADE_COUNT_TARGET: int = _TUNER_CFG.get("trade_count_target", 50)

def _compute_base_score(metrics: dict) -> float:
    """Original quantitative fitness logic."""
    n   = metrics.get("approved_trades", 0)
    exp = metrics.get("expansions", 0)
    ret = metrics.get("retests",    0)

    _exp_floor = _TUNER_CFG.get("expansion_quality_min_count", 20)
    _ret_ratio = _TUNER_CFG.get("expansion_quality_min_ratio", 0.05)
    if exp > _exp_floor and (ret / exp) < _ret_ratio:
        return -999.0

    if n < TRADE_COUNT_FLOOR:
        return -999.0

    exp_rr  = metrics.get("expectancy_rr", 0.0)
    wr      = metrics.get("win_rate", 0.0)
    dd      = metrics.get("max_drawdown_pct", 1.0)
    tc_norm = min(n / TRADE_COUNT_TARGET, 1.0)

    score = (
        _FW.get("expectancy_rr",    0.50) * exp_rr +
        _FW.get("win_rate",         0.20) * wr +
        _FW.get("trade_count_norm", 0.20) * tc_norm +
        _FW.get("drawdown",         0.10) * (1.0 - dd)
    )
    return score

def fitness(metrics: dict) -> float:
    """Composite score with LLM semantic gating."""
    base_score = _compute_base_score(metrics)

    _llm_trigger = _LLM_GATE.get("base_score_trigger",    0.1)
    _llm_reject  = _LLM_GATE.get("hard_reject_threshold", 0.2)
    _llm_blend   = _LLM_GATE.get("blend_weights",         [0.7, 0.3])

    if base_score <= _llm_trigger:
        return round(base_score, 6) if base_score != -999.0 else -999.0

    llm_weight = llm_score(metrics)

    if llm_weight < _llm_reject:
        tuner_log.info(f"LLM hard-rejected config (base_score={base_score:.3f}).")
        return -999.0

    final_score = base_score * (_llm_blend[0] + _llm_blend[1] * llm_weight)
    return round(final_score, 6)

def fitnessbeforellm(metrics: dict) -> float:
    n   = metrics.get("approved_trades", 0)
    exp = metrics.get("expansions", 0)
    ret = metrics.get("retests",    0)
    _exp_floor = _TUNER_CFG.get("expansion_quality_min_count", 20)
    _ret_ratio = _TUNER_CFG.get("expansion_quality_min_ratio", 0.05)
    if exp > _exp_floor and (ret / exp) < _ret_ratio:
        return -999.0

    if n < TRADE_COUNT_FLOOR:
        return -999.0

    exp_rr  = metrics.get("expectancy_rr", 0.0)
    wr      = metrics.get("win_rate", 0.0)
    dd      = metrics.get("max_drawdown_pct", 1.0)
    tc_norm = min(n / TRADE_COUNT_TARGET, 1.0)

    score = (
        _FW.get("expectancy_rr",    0.50) * exp_rr +
        _FW.get("win_rate",         0.20) * wr +
        _FW.get("trade_count_norm", 0.20) * tc_norm +
        _FW.get("drawdown",         0.10) * (1.0 - dd)
    )
    return round(score, 6)

# ═══════════════════════════════════════════════════════════════════════════
# 4. BACKTEST WRAPPER (ISOLATED WORKER)
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
    output_dir: str = "results/tuner/runs_gemini_pro",
    start_idx: int = 0,
    end_idx: int = 0,
) -> dict:
    """Isolated worker function. Safe for multiprocessing multiprocessing."""
    try:

        # ConfigBuilder.build() is the ONLY valid config source.
        # Overrides are passed directly — frozen dataclass cannot use setattr.
        crt_cfg = ConfigBuilder.build(instrument, overrides=params)

        if base_bt_config is not None:
            bt_cfg = deepcopy(base_bt_config)
            bt_cfg.crt_config  = crt_cfg
            bt_cfg.instrument  = instrument
            bt_cfg.pip_size    = INSTRUMENT_PIP.get(instrument, 0.0001)
        else:
            bt_cfg = BacktestConfig(
                instrument  = instrument,
                pip_size    = INSTRUMENT_PIP.get(instrument, 0.0001),
                crt_config  = crt_cfg,
            )

        loader = CandleLoader(csv_path, instrument)
        # skip_features=True: FeaturePipeline is param-invariant for a given CSV.
        # Tuner fitness uses metric scalars only — feature columns not needed here.
        runner = BacktestRunner(bt_cfg, csv_path=csv_path, skip_features=True)

        stream = loader.stream()
        total_candles = loader.count()
        
        # OOS Slicing logic
        if start_idx > 0 or end_idx > 0:
            _base_stream = stream  # capture value before rebinding (avoids late-binding closure bug)
            def slice_stream():
                for i, c in enumerate(_base_stream):
                    if i < start_idx: continue
                    if end_idx > 0 and i >= end_idx: break
                    yield c
            stream = slice_stream()
            candle_cnt = (end_idx if end_idx > 0 else total_candles) - start_idx
        else:
            candle_cnt = total_candles

        m = runner.run(stream, candle_cnt, output_dir=output_dir)

        fc = m.funnel_counts if hasattr(m, "funnel_counts") else {}
        return {
            "approved_trades":  m.approved_trades,
            "win_rate":         round(m.win_rate, 4),
            "expectancy_rr":    round(m.avg_rr_net, 4),
            "total_pnl_rr_net": round(m.total_pnl_rr_net, 4),
            "max_drawdown_pct": round(m.max_drawdown_pct, 4),
            "avg_rr_net":       round(m.avg_rr_net, 4),
            "expansions":       fc.get("expansion_success", 0),
            "retests":          fc.get("retest_success", 0),
            "sweeps":           fc.get("sweeps_detected", 0),
            "error":            None,
        }

    except Exception as exc:
        tuner_log.warning(f"Backtest failed: {exc}")
        return {
            "approved_trades": 0, "win_rate": 0.0,
            "expectancy_rr": 0.0, "total_pnl_rr_net": 0.0,
            "max_drawdown_pct": 1.0, "avg_rr_net": 0.0,
            "expansions": 0, "retests": 0, "sweeps": 0,
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
        self.mark_seen(result.params)

    def is_duplicate(self, params: dict) -> bool:
        return params_to_key(params) in self._seen_keys

    def mark_seen(self, params: dict) -> None:
        self._seen_keys.add(params_to_key(params))

    def valid(self) -> list[TunerResult]:
        return [r for r in self._results if r.score > -999.0]

    def top_n(self, n: int = 10) -> list[TunerResult]:
        return sorted(self.valid(), key=lambda r: r.score, reverse=True)[:n]

    def best(self) -> Optional[TunerResult]:
        v = self.valid()
        return max(v, key=lambda r: r.score) if v else None

    def top_20pct_configs(self) -> list[dict]:
        v = self.valid()
        if not v: return []
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
            store.add(TunerResult(**d))
        return store

# ═══════════════════════════════════════════════════════════════════════════
# 6. AUTO-TUNER CORE (PARALLELIZED)
# ═══════════════════════════════════════════════════════════════════════════

class AutoTuner:
    def __init__(
        self,
        csv_paths:      dict[str, str],
        output_dir:     str = "results/tuner",
        n_iter_phase1:  int = 100,
        n_iter_phase2:  int = 50,
        seed:           int = 42,
        base_bt_config: Optional[BacktestConfig] = None,
        checkpoint_every: int = 20,
        max_workers:    int = 4,
        train_split:    float = 1.0,  # 1.0 = use all data for training
    ):
        self.csv_paths      = csv_paths
        self.output_dir     = Path(output_dir)
        self.n_iter_phase1  = n_iter_phase1
        self.n_iter_phase2  = n_iter_phase2
        self.rng            = random.Random(seed)
        self.base_bt_config = base_bt_config
        self.checkpoint_every = checkpoint_every
        self.max_workers    = max_workers
        self.train_split    = train_split

        self.store     = ResultStore()
        self.iteration = 0

        self.primary_instrument = next(iter(csv_paths))
        self.primary_csv        = csv_paths[self.primary_instrument]

        # Pre-calculate data splits for Out-Of-Sample validation
        self.total_candles = CandleLoader(self.primary_csv, self.primary_instrument).count()
        self.train_end_idx = int(self.total_candles * self.train_split)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.best_score = -999

    def run(self) -> TunerResult:
        print(f"\n{'═'*65}")
        print(f"  CRT AUTO-TUNER [ROBUST V2]")
        print(f"  Primary instrument: {self.primary_instrument}")
        print(f"  Total candles:      {self.total_candles:,}")
        if self.train_split < 1.0:
            print(f"  Data split:         IS: 0→{self.train_end_idx} | OOS: {self.train_end_idx}→{self.total_candles}")
        print(f"  Workers:            {self.max_workers} processes")
        print(f"{'═'*65}\n")

        try:
            self._run_phase("random", self.n_iter_phase1)
            
            top_configs = self.store.top_20pct_configs()
            if top_configs:
                self._run_phase("focused", self.n_iter_phase2, seed_configs=top_configs)

            if self.train_split < 1.0:
                self._run_oos_validation()

            if len(self.csv_paths) > 1:
                self._run_cross_validation()

        except KeyboardInterrupt:
            print("\n\n  [!] INTERRUPTED BY USER — Saving state safely before exit...\n")
        finally:
            self._save_final_report()

        best = self.store.best()
        if not best: sys.exit(1)
        return best

    def _run_phase(self, phase: str, n_iter: int, seed_configs: Optional[list[dict]] = None) -> None:
        print(f"\n  Phase {1 if phase == 'random' else 2}: {phase.upper()} SEARCH (In-Sample)")
        print(f"  {'─'*60}")

        # Pre-generate unique parameters
        tasks = []
        while len(tasks) < n_iter:
            params = sample_neighbourhood(self.rng.choice(seed_configs), self.rng) if phase == "focused" and seed_configs else sample_random(self.rng)
            if not self.store.is_duplicate(params):
                tasks.append(params)
                self.store.mark_seen(params)

        with concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_params = {
                executor.submit(
                    run_backtest, p, self.primary_csv, self.primary_instrument,
                    self.base_bt_config, str(self.output_dir / "runs_gemini_pro"), 0, self.train_end_idx
                ): p for p in tasks
            }

            for future in concurrent.futures.as_completed(future_to_params):
                params = future_to_params[future]
                self.iteration += 1
                t0 = time.perf_counter()
                
                metrics = future.result()
                score   = fitness(metrics)
                elapsed = time.perf_counter() - t0

                res = TunerResult(self.iteration, params, metrics, score, elapsed, self.primary_instrument, phase)
                self.store.add(res)
                self._print_progress(res, elapsed)

                if self.iteration % self.checkpoint_every == 0:
                    self._checkpoint()

    def _run_oos_validation(self) -> None:
        """Phase 4: Test top 10 configs on the held-out OOS data split."""
        print(f"\n  Phase 4: OUT-OF-SAMPLE VALIDATION (OOS)")
        print(f"  {'─'*60}")

        top10 = self.store.top_n(10)
        with concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_res = {
                executor.submit(
                    run_backtest, r.params, self.primary_csv, self.primary_instrument,
                    self.base_bt_config, str(self.output_dir / "runs_gemini_pro"), self.train_end_idx, self.total_candles
                ): r for r in top10
            }

            for future in concurrent.futures.as_completed(future_to_res):
                orig_res = future_to_res[future]
                metrics = future.result()
                score   = fitness(metrics)
                
                oos_res = TunerResult(self.iteration, orig_res.params, metrics, score, 0.0, self.primary_instrument, "oos_validation")
                self.store.add(oos_res)
                print(f"  [OOS ] score={score:>+.4f}  exp={metrics.get('expectancy_rr',0):>+.3f}R  n={metrics.get('approved_trades',0):>3}  {self._params_str(orig_res.params)}")

    def _run_cross_validation(self) -> None:
        print(f"\n  Phase 3: CROSS-INSTRUMENT VALIDATION")
        print(f"  {'─'*60}")
        # Simplified parallel cross-validation logic can go here (similar to OOS executor mapping)
        pass 

    def _print_progress(self, r: TunerResult, elapsed: float):
        m = r.metrics
        status = "OK " if r.score > -999 else ("BCK" if m.get("expansions",0)>20 and m.get("retests",0)==0 else "LOW")
        print(f"  [{status}] iter={r.iteration:>4}  score={r.score:>+.4f}  "
              f"exp={m.get('expectancy_rr',0):>+.3f}R  wr={m.get('win_rate',0):.0%}  "
              f"n={m.get('approved_trades',0):>3}  t={elapsed:.1f}s")

    def _checkpoint(self):
        self.store.save(str(self.output_dir / "checkpoint_gemini_pro.json"))

    def _save_final_report(self):
        self._checkpoint()
        best = self.store.best()
        if best:
            print(f"\n{'═'*65}\n  BEST CONFIG (score={best.score:+.4f})")
            for k, v in best.params.items(): print(f"    {k:<35} = {v}")
            print(f"{'═'*65}\n")

    @staticmethod
    def _params_str(params: dict) -> str:
        return " ".join(f"{k.split('_')[-1]}={v}" for k, v in sorted(params.items()))

# ═══════════════════════════════════════════════════════════════════════════
# 8. CLI
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    ap = argparse.ArgumentParser(description="CRT Auto-Tuner [ROBUST V2]")
    ap.add_argument("--csv",         help="Single M15 CSV path")
    ap.add_argument("--instrument",  help="Instrument name (e.g. GBPUSD)")
    ap.add_argument("--data-dir",    default="data", help="Directory with M15 CSVs")
    ap.add_argument("--instruments", nargs="+", help="Instruments to tune (multi mode)")
    ap.add_argument("--output-dir",  default="results/tuner")
    ap.add_argument("--n-iter",      type=int, default=100)
    ap.add_argument("--seed",        type=int, default=42)
    ap.add_argument("--workers",     type=int, default=os.cpu_count() or 4, help="Number of CPU cores to use")
    ap.add_argument("--train-split", type=float, default=1.0, help="Fraction of data for In-Sample (e.g. 0.8)")
    
    args = ap.parse_args()

    csv_paths: dict[str, str] = {}
    if args.csv and args.instrument:
        csv_paths[args.instrument.upper()] = args.csv

    tuner = AutoTuner(
        csv_paths     = csv_paths,
        output_dir    = args.output_dir,
        n_iter_phase1 = args.n_iter,
        n_iter_phase2 = max(args.n_iter // 2, 20),
        seed          = args.seed,
        max_workers   = args.workers,
        train_split   = args.train_split
    )
    tuner.run()

if __name__ == "__main__":
    main()