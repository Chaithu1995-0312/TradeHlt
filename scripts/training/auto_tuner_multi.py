"""
auto_tuner_multi.py
═══════════════════════════════════════════════════════════════════════════════
CRT Engine — Multi-Instrument Deterministic Optimizer  (Ultron Phase-7)

ARCHITECTURE UPGRADE (v3):
  - True multi-instrument optimization: every param set scored across ALL
    instruments simultaneously (not primary + post-hoc validation).
  - ConfigBuilder.build() enforced — zero direct CRTConfig/get_crt_config usage.
  - Consistency penalty: configs that only work on one market are penalised.
  - Replay-safe: every result carries a full config_snapshot per instrument.
  - Deterministic: fixed seeds, no global mutable state, same input → same output.
  - Parallel: ProcessPoolExecutor — one worker per param set, all instruments
    evaluated inside the worker.

USAGE:
  # Tune across all instruments found in data/
  python auto_tuner_multi.py --data-dir data/ --instruments EURUSD GBPUSD BTCUSDT XAUUSD

  # With OOS hold-out (80/20 split)
  python auto_tuner_multi.py --data-dir data/ --instruments EURUSD GBPUSD --train-split 0.8

  # Single instrument (backward-compatible)
  python auto_tuner_multi.py --csv data/GBPUSD_M15.csv --instrument GBPUSD
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import argparse

import concurrent.futures
import dataclasses
import datetime as _dt
import json
import logging
import math
import os
import random
import sys
import time
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

# ── Path setup ───────────────────────────────────────────────────────────────
_SRC = Path(__file__).resolve().parent.parent.parent / "src"
for _p in (_SRC, _SRC / "runtime"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from utils.console_safe import safe_print

# ── Import project modules ──────────────────────────────────────────────────
try:
    from backtest_v2 import BacktestConfig, BacktestRunner, CandleLoader
    from config_layer.crt_engine_v2 import CRTConfig          # kept only for type hints
    from config_layer.config_builder import ConfigBuilder      # REQUIRED — replaces get_crt_config
    from config_layer.llama_gate import llm_score
except ImportError as e:
    safe_print(f"\n  IMPORT ERROR: {e}\n"
          "  Ensure backtest_v2.py, crt_engine_v2.py, config_builder.py "
          "and llama_gate.py are in the same directory.\n")
    sys.exit(1)

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    level=logging.WARNING,
)
tuner_log = logging.getLogger("AutoTuner")
tuner_log.setLevel(logging.INFO)
LOG_FILE = "results/tuner/live_log_multi.jsonl"

# ── Load tuner section from production config; fall back to coded defaults ────
try:
    from config_layer.production_config import get_prod_section as _get_section
    _TUNER_CFG = _get_section("tuner")
except Exception:
    _TUNER_CFG = {}

_FW          = _TUNER_CFG.get("fitness_weights", {})
_LLM_GATE    = _TUNER_CFG.get("llm_gate", {})


def log_event(data: dict) -> None:
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
for _v in PARAM_SPACE.values():
    SPACE_SIZE *= len(_v)


def sample_random(rng: random.Random) -> dict:
    """Uniform random sample from PARAM_SPACE — deterministic given rng state."""
    return {k: rng.choice(v) for k, v in PARAM_SPACE.items()}


def sample_neighbourhood(base: dict, rng: random.Random, perturbation: float = 0.3) -> dict:
    """
    Focused exploitation: start from a known-good config, perturb each param
    with probability = perturbation.
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
# 2. INSTRUMENT METADATA
# ═══════════════════════════════════════════════════════════════════════════

INSTRUMENT_PIP: dict[str, float] = {
    "EURCAD": 0.0001, "EURUSD": 0.0001, "GBPUSD": 0.0001,
    "USDJPY": 0.01,   "AUDUSD": 0.0001, "NZDUSD": 0.0001,
    "USDCHF": 0.0001, "BTCUSDT": 1.0,   "ETHUSDT": 0.01,
    "XAUUSD": 0.01,   "US30": 1.0,      "NAS100": 0.25,
    "SP500":  0.25,
}

# Per-instrument weighting in the combined score (must sum to 1.0 for a given set)
INSTRUMENT_WEIGHT_DEFAULT: float = 1.0   # equal weight; normalised at runtime


# ═══════════════════════════════════════════════════════════════════════════
# 3. FITNESS FUNCTION
# ═══════════════════════════════════════════════════════════════════════════

TRADE_COUNT_FLOOR:  int   = _TUNER_CFG.get("trade_count_floor",  3)
TRADE_COUNT_TARGET: int   = _TUNER_CFG.get("trade_count_target", 50)
CONSISTENCY_ALPHA:  float = _TUNER_CFG.get("consistency_alpha",  0.1)


def _compute_base_score(metrics: dict) -> float:
    """Quantitative fitness for a single instrument run."""
    n   = metrics.get("approved_trades", 0)
    exp = metrics.get("expansions", 0)
    ret = metrics.get("retests", 0)

    _exp_floor = _TUNER_CFG.get("expansion_quality_min_count", 20)
    _ret_ratio = _TUNER_CFG.get("expansion_quality_min_ratio", 0.05)
    if exp > _exp_floor and ret > 0 and (ret / exp) < _ret_ratio:
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


def fitness_single(metrics: dict, use_llm: bool = True) -> float:
    """Composite score for one instrument (base + optional LLM gate)."""
    base_score = _compute_base_score(metrics)

    _llm_trigger = _LLM_GATE.get("base_score_trigger",     0.1)
    _llm_reject  = _LLM_GATE.get("hard_reject_threshold",  0.2)
    _llm_blend   = _LLM_GATE.get("blend_weights",          [0.7, 0.3])

    if base_score <= _llm_trigger or not use_llm:
        reason = "use_llm=False" if not use_llm else f"base_score={base_score:.4f} ≤ trigger={_llm_trigger}"
        tuner_log.debug("LLM skipped — %s", reason)
        return round(base_score, 6) if base_score != -999.0 else -999.0

    tuner_log.info(
        "LLM triggered — base_score=%.4f  metrics: trades=%s wr=%.0f%% exp_rr=%.3fR dd=%.1f%%",
        base_score,
        metrics.get("approved_trades", "?"),
        metrics.get("win_rate", 0) * 100,
        metrics.get("expectancy_rr", 0),
        metrics.get("max_drawdown_pct", 0) * 100,
    )

    try:
        llm_weight = llm_score(metrics)
    except Exception:
        llm_weight = 1.0   # fail-open: don't discard a good config on LLM error

    if llm_weight < _llm_reject:
        tuner_log.info(f"LLM hard-rejected config (base={base_score:.3f}, llm_weight={llm_weight:.4f}).")
        return -999.0

    blended = round(base_score * (_llm_blend[0] + _llm_blend[1] * llm_weight), 6)
    tuner_log.info(
        "LLM accepted — weight=%.4f  base=%.4f → blended=%.4f",
        llm_weight, base_score, blended,
    )
    return blended


def fitness_multi(
    per_instrument_scores: dict[str, float],
    weights: Optional[dict[str, float]] = None,
) -> tuple[float, float]:
    """
    Combine per-instrument scores into one final score with consistency penalty.

    Returns
    -------
    (final_score, consistency_penalty)
        final_score = weighted_mean - alpha * std_dev
    """
    valid = {k: v for k, v in per_instrument_scores.items() if v > -999.0}

    if not valid:
        return -999.0, 0.0

    instruments = list(valid.keys())
    scores      = list(valid.values())

    if weights:
        w = [weights.get(inst, INSTRUMENT_WEIGHT_DEFAULT) for inst in instruments]
        total_w = sum(w)
        w = [wi / total_w for wi in w]
    else:
        w = [1.0 / len(scores)] * len(scores)

    mean_score = sum(s * wi for s, wi in zip(scores, w))

    # Consistency penalty: penalise high variance across markets
    if len(scores) > 1:
        variance   = sum(wi * (s - mean_score) ** 2 for s, wi in zip(scores, w))
        std_dev    = math.sqrt(variance)
    else:
        std_dev = 0.0

    consistency_penalty = std_dev
    final_score = mean_score - CONSISTENCY_ALPHA * consistency_penalty

    return round(final_score, 6), round(consistency_penalty, 6)


# ═══════════════════════════════════════════════════════════════════════════
# 4. SINGLE-INSTRUMENT BACKTEST WORKER (process-safe)
# ═══════════════════════════════════════════════════════════════════════════

def _run_single_instrument(
    params:        dict,
    csv_path:      str,
    instrument:    str,
    base_bt_config: Optional[BacktestConfig],
    output_dir:    str,
    start_idx:     int = 0,
    end_idx:       int = 0,
) -> tuple[dict, dict]:
    """
    Run backtest for ONE instrument with params applied via ConfigBuilder.

    Returns
    -------
    (metrics_dict, config_snapshot_dict)
        config_snapshot is a serialisable dict of the CRTConfig used.
    """
    try:
        # Build base config to get valid keys
        base_cfg = ConfigBuilder.build(instrument)

        # Filter only valid override keys
        valid_params = {
            k: v for k, v in params.items()
            if hasattr(base_cfg, k)
        }

        # Optional: warn if anything was dropped
        if len(valid_params) != len(params):
            invalid = set(params) - set(valid_params)
            tuner_log.warning(f"[{instrument}] Invalid params filtered: {invalid}")
        # ── Config via ConfigBuilder ONLY — no CRTConfig(), no get_crt_config() ──
        cfg: CRTConfig = ConfigBuilder.build(instrument, overrides=valid_params)
        config_snapshot: dict = dataclasses.asdict(cfg)

        pip_size = INSTRUMENT_PIP.get(instrument, 0.0001)

        if base_bt_config is not None:
            bt_cfg = deepcopy(base_bt_config)
            bt_cfg.crt_config = cfg
            bt_cfg.instrument = instrument
            bt_cfg.pip_size   = pip_size
            if hasattr(bt_cfg, "debug_mode"):
                bt_cfg.debug_mode = False
        else:
            bt_cfg = BacktestConfig(
                # Required parameters
                htf_candles_per_range = 16,
                slippage_enabled = True,
                slippage_atr_fraction = 0.08,
                slippage_seed = 0,
                simulated_spread_pct = 0.0002,
                initial_capital = 100000.0,
                risk_pct_per_trade = 0.01,
                use_compounding = True,
                gap_reset_enabled = True,
                gap_reset_minutes = 120,
                event_flush_every = 1000,
                warmup_candles = 100,
                # Instance parameters
                instrument = instrument,
                pip_size = pip_size,
                crt_config = cfg,
            )
            if "debug_mode" in getattr(BacktestConfig, "__annotations__", {}):
                bt_cfg.debug_mode = False

        loader = CandleLoader(csv_path, instrument)
        # skip_features=True: FeaturePipeline is param-invariant for a given CSV
        # (OHLCV → indicators has no dependency on CRT params).  The tuner fitness
        # function only reads metric scalars so feature columns in _trades.csv are
        # not required here.  Full-feature runs use the default BacktestRunner path.
        runner = BacktestRunner(bt_cfg, csv_path=csv_path, skip_features=True)
        stream = loader.stream()
        total_candles = loader.count()

        if start_idx > 0 or end_idx > 0:
            def _slice(stream_in):
                for i, c in enumerate(stream_in):
                    if i < start_idx:
                        continue
                    if end_idx > 0 and i >= end_idx:
                        break
                    yield c
            stream      = _slice(stream)
            candle_cnt  = (end_idx if end_idx > 0 else total_candles) - start_idx
        else:
            candle_cnt = total_candles

        m  = runner.run(stream, candle_cnt, output_dir=output_dir)
        fc = m.funnel_counts if hasattr(m, "funnel_counts") else {}

        expectancy_rr = getattr(m, "expectancy_rr", getattr(m, "avg_rr_net", 0.0))
        total_pnl_rr_net = getattr(m, "total_pnl_rr_net", getattr(m, "total_pnl_rr", 0.0))
        max_drawdown_pct = getattr(m, "max_drawdown_pct", getattr(m, "max_drawdown", 0.0))
        avg_rr_net = getattr(m, "avg_rr_net", expectancy_rr)

        metrics = {
            "approved_trades":  getattr(m, "approved_trades", 0),
            "win_rate":         round(getattr(m, "win_rate", 0.0), 4),
            "expectancy_rr":    round(expectancy_rr, 4),
            "total_pnl_rr_net": round(total_pnl_rr_net, 4),
            "max_drawdown_pct": round(max_drawdown_pct, 4),
            "avg_rr_net":       round(avg_rr_net, 4),
            "expansions":       fc.get("expansion_success", 0),
            "retests":          fc.get("retest_success", 0),
            "sweeps":           fc.get("sweeps_detected", 0),
            "error":            None,
        }
        return metrics, config_snapshot

    except Exception as exc:
        tuner_log.warning(f"[{instrument}] backtest failed: {exc}")
        empty_metrics = {
            "approved_trades": 0, "win_rate": 0.0,
            "expectancy_rr": 0.0, "total_pnl_rr_net": 0.0,
            "max_drawdown_pct": 1.0, "avg_rr_net": 0.0,
            "expansions": 0, "retests": 0, "sweeps": 0,
            "error": str(exc),
        }
        return empty_metrics, {}


# ═══════════════════════════════════════════════════════════════════════════
# 5. MULTI-INSTRUMENT WORKER  (entry point for ProcessPoolExecutor)
# ═══════════════════════════════════════════════════════════════════════════

def evaluate_params_multi(
    params:        dict,
    csv_paths:     dict[str, str],          # {instrument: csv_path}
    base_bt_config: Optional[BacktestConfig],
    output_dir:    str,
    start_indices: dict[str, int],          # per-instrument train start idx
    end_indices:   dict[str, int],          # per-instrument train end idx
    weights:       Optional[dict[str, float]] = None,
    use_llm:       bool = True,
) -> dict:
    """
    Top-level worker executed in a child process.

    Evaluates params across ALL instruments, then combines scores.

    Returns a replay-safe result dict.
    """
    instrument_metrics:   dict[str, dict]  = {}
    instrument_scores:    dict[str, float] = {}
    config_snapshots:     dict[str, dict]  = {}

    for instrument, csv_path in csv_paths.items():
        if not csv_path or not Path(csv_path).exists():
            tuner_log.warning(f"[{instrument}] CSV not found: {csv_path} — skipping.")
            instrument_scores[instrument]   = -999.0
            instrument_metrics[instrument]  = {"error": "csv_not_found"}
            config_snapshots[instrument]    = {}
            continue

        metrics, snapshot = _run_single_instrument(
            params, csv_path, instrument, base_bt_config, output_dir,
            start_indices.get(instrument, 0),
            end_indices.get(instrument, 0),
        )
        score = fitness_single(metrics, use_llm=use_llm)

        instrument_metrics[instrument]  = metrics
        instrument_scores[instrument]   = score
        config_snapshots[instrument]    = snapshot

    final_score, consistency = fitness_multi(instrument_scores, weights=weights)

    return {
        "params":              params,
        "instrument_results":  {
            inst: {
                "score":   instrument_scores.get(inst, -999.0),
                "metrics": instrument_metrics.get(inst, {}),
            }
            for inst in csv_paths
        },
        "final_score":         final_score,
        "consistency_penalty": consistency,
        "config_snapshot":     config_snapshots,   # per-instrument CRTConfig snapshot
    }


# ═══════════════════════════════════════════════════════════════════════════
# 6. RESULT STORE
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TunerResult:
    iteration:           int
    params:              dict
    metrics:             dict                    # aggregated / primary metrics kept for display
    score:               float
    elapsed_s:           float
    instrument:          str                     # "MULTI" or single name
    phase:               str = "random"
    instrument_results:  dict = field(default_factory=dict)
    consistency_penalty: float = 0.0
    config_snapshot:     dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "iteration":           self.iteration,
            "phase":               self.phase,
            "instrument":          self.instrument,
            "score":               self.score,
            "consistency_penalty": self.consistency_penalty,
            "params":              self.params,
            "metrics":             self.metrics,
            "instrument_results":  self.instrument_results,
            "config_snapshot":     self.config_snapshot,
            "elapsed_s":           round(self.elapsed_s, 2),
        }


class _TunerJSONEncoder(json.JSONEncoder):
    """Handles datetime.time / datetime.datetime objects in config_snapshot."""
    def default(self, o):
        if isinstance(o, _dt.time):
            return o.strftime("%H:%M:%S")
        if isinstance(o, _dt.datetime):
            return o.isoformat()
        if isinstance(o, _dt.date):
            return o.isoformat()
        return super().default(o)


class ResultStore:
    def __init__(self):
        self._results:   list[TunerResult] = []
        self._seen_keys: set[str]          = set()

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
        if not v:
            return []
        cutoff = max(1, len(v) // 5)
        return [r.params for r in sorted(v, key=lambda r: r.score, reverse=True)[:cutoff]]

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump([r.to_dict() for r in self._results], f, indent=2, cls=_TunerJSONEncoder)
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
# 7. AUTO-TUNER CORE
# ═══════════════════════════════════════════════════════════════════════════

class AutoTuner:
    def __init__(
        self,
        csv_paths:        dict[str, str],
        output_dir:       str  = "results/tuner",
        n_iter_phase1:    int  = 100,
        n_iter_phase2:    int  = 50,
        seed:             int  = 42,
        base_bt_config:   Optional[BacktestConfig] = None,
        checkpoint_every: int  = 20,
        max_workers:      int  = 4,
        train_split:      float = 1.0,
        weights:          Optional[dict[str, float]] = None,
        use_llm:          bool = True,
    ):
        if not csv_paths:
            raise ValueError("csv_paths must contain at least one instrument.")

        self.csv_paths        = csv_paths
        self.output_dir       = Path(output_dir)
        self.n_iter_phase1    = n_iter_phase1
        self.n_iter_phase2    = n_iter_phase2
        # Deterministic RNG — immutable seed, no global mutation
        self.rng              = random.Random(seed)
        self.base_bt_config   = base_bt_config
        self.checkpoint_every = checkpoint_every
        self.max_workers      = max_workers
        self.train_split      = train_split
        self.weights          = weights
        self.use_llm          = use_llm

        self.store     = ResultStore()
        self.iteration = 0

        # Per-instrument data-split indices (train / OOS)
        self.train_end_indices: dict[str, int] = {}
        self.total_candles_map: dict[str, int] = {}
        for instrument, csv_path in csv_paths.items():
            if Path(csv_path).exists():
                total = CandleLoader(csv_path, instrument).count()
                self.total_candles_map[instrument]  = total
                self.train_end_indices[instrument]  = int(total * train_split)
            else:
                tuner_log.warning(f"CSV not found at init: {csv_path}")
                self.total_candles_map[instrument]  = 0
                self.train_end_indices[instrument]  = 0

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.best_score = -999.0

    # ── Public entry ────────────────────────────────────────────────────────

    def run(self) -> TunerResult:
        mode_label = "MULTI-INSTRUMENT" if len(self.csv_paths) > 1 else "SINGLE-INSTRUMENT"
        safe_print(f"\n{'═'*65}")
        safe_print(f"  CRT AUTO-TUNER [v3 — {mode_label}]")
        safe_print(f"  Instruments:  {', '.join(self.csv_paths)}")
        for inst, total in self.total_candles_map.items():
            end = self.train_end_indices[inst]
            if self.train_split < 1.0:
                safe_print(f"  {inst:<12} candles={total:,}  IS=0→{end}  OOS={end}→{total}")
            else:
                safe_print(f"  {inst:<12} candles={total:,}")
        safe_print(f"  Workers:      {self.max_workers} processes")
        safe_print(f"{'═'*65}\n")

        try:
            self._run_phase("random", self.n_iter_phase1)

            top_configs = self.store.top_20pct_configs()
            if top_configs:
                self._run_phase("focused", self.n_iter_phase2, seed_configs=top_configs)

            if self.train_split < 1.0:
                self._run_oos_validation()

        except KeyboardInterrupt:
            safe_print("\n\n  [!] INTERRUPTED — saving checkpoint safely...\n")
        finally:
            self._save_final_report()

        best = self.store.best()
        if not best:
            sys.exit(1)
        return best

    # ── Phases ──────────────────────────────────────────────────────────────

    def _run_phase(
        self,
        phase:        str,
        n_iter:       int,
        seed_configs: Optional[list[dict]] = None,
    ) -> None:
        label = "RANDOM SEARCH" if phase == "random" else "FOCUSED SEARCH"
        safe_print(f"\n  Phase {1 if phase == 'random' else 2}: {label} (In-Sample, all instruments)")
        safe_print(f"  {'─'*60}")

        # Build unique param tasks deterministically
        tasks: list[dict] = []
        while len(tasks) < n_iter:
            if phase == "focused" and seed_configs:
                base = self.rng.choice(seed_configs)
                params = sample_neighbourhood(base, self.rng)
            else:
                params = sample_random(self.rng)
            if not self.store.is_duplicate(params):
                tasks.append(params)
                self.store.mark_seen(params)

        # Build per-instrument train-only index windows
        start_indices = {inst: 0 for inst in self.csv_paths}
        end_indices   = {inst: self.train_end_indices[inst] for inst in self.csv_paths}

        with concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {
                executor.submit(
                    evaluate_params_multi,
                    p,
                    self.csv_paths,
                    self.base_bt_config,
                    str(self.output_dir / "runs"),
                    start_indices,
                    end_indices,
                    self.weights,
                    self.use_llm,
                ): p for p in tasks
            }

            for future in concurrent.futures.as_completed(future_map):
                self.iteration += 1
                t0 = time.perf_counter()

                try:
                    result = future.result()
                except Exception as exc:
                    tuner_log.warning(f"Worker raised: {exc}")
                    continue

                elapsed = time.perf_counter() - t0
                score   = result["final_score"]
                params  = result["params"]

                # Flatten per-instrument metrics for display (first valid instrument)
                display_metrics = self._extract_display_metrics(result)

                tr = TunerResult(
                    iteration           = self.iteration,
                    params              = params,
                    metrics             = display_metrics,
                    score               = score,
                    elapsed_s           = elapsed,
                    instrument          = "MULTI" if len(self.csv_paths) > 1 else next(iter(self.csv_paths)),
                    phase               = phase,
                    instrument_results  = result["instrument_results"],
                    consistency_penalty = result["consistency_penalty"],
                    config_snapshot     = result["config_snapshot"],
                )
                self.store.add(tr)
                self._print_progress(tr, elapsed)

                if self.iteration % self.checkpoint_every == 0:
                    self._checkpoint()

    def _run_oos_validation(self) -> None:
        safe_print(f"\n  Phase 3: OUT-OF-SAMPLE VALIDATION (all instruments)")
        safe_print(f"  {'─'*60}")

        top10 = self.store.top_n(10)
        start_indices = {inst: self.train_end_indices[inst] for inst in self.csv_paths}
        end_indices   = {inst: self.total_candles_map[inst]  for inst in self.csv_paths}

        with concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {
                executor.submit(
                    evaluate_params_multi,
                    r.params,
                    self.csv_paths,
                    self.base_bt_config,
                    str(self.output_dir / "runs_oos"),
                    start_indices,
                    end_indices,
                    self.weights,
                    self.use_llm,
                ): r for r in top10
            }

            for future in concurrent.futures.as_completed(future_map):
                orig_res = future_map[future]
                try:
                    result = future.result()
                except Exception as exc:
                    tuner_log.warning(f"OOS worker raised: {exc}")
                    continue

                score = result["final_score"]
                safe_print(
                    f"  [OOS ] score={score:>+.4f}  "
                    f"consist_pen={result['consistency_penalty']:>.4f}  "
                    f"{self._params_str(orig_res.params)}"
                )

                oos_tr = TunerResult(
                    iteration           = self.iteration,
                    params              = orig_res.params,
                    metrics             = self._extract_display_metrics(result),
                    score               = score,
                    elapsed_s           = 0.0,
                    instrument          = "MULTI_OOS",
                    phase               = "oos_validation",
                    instrument_results  = result["instrument_results"],
                    consistency_penalty = result["consistency_penalty"],
                    config_snapshot     = result["config_snapshot"],
                )
                self.store.add(oos_tr)

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_display_metrics(result: dict) -> dict:
        """Pull the first valid instrument's metrics for progress display."""
        for inst_data in result.get("instrument_results", {}).values():
            m = inst_data.get("metrics", {})
            if m.get("error") is None:
                return m
        return {}

    def _print_progress(self, r: TunerResult, elapsed: float) -> None:
        m = r.metrics
        if r.score > -999:
            status = "OK "
        elif m.get("expansions", 0) > 20 and m.get("retests", 0) == 0:
            status = "BCK"
        else:
            status = "LOW"

        inst_scores = " | ".join(
            f"{inst}={data.get('score', -999):+.3f}"
            for inst, data in r.instrument_results.items()
        ) if r.instrument_results else ""

        safe_print(
            f"  [{status}] iter={r.iteration:>4}  score={r.score:>+.4f}  "
            f"pen={r.consistency_penalty:.4f}  "
            f"exp={m.get('expectancy_rr', 0):>+.3f}R  wr={m.get('win_rate', 0):.0%}  "
            f"n={m.get('approved_trades', 0):>3}  [{inst_scores}]  t={elapsed:.1f}s"
        )

    def _checkpoint(self) -> None:
        self.store.save(str(self.output_dir / "checkpoint_multi.json"))

    def _save_final_report(self) -> None:
        self._checkpoint()
        best = self.store.best()
        if best:
            safe_print(f"\n{'='*65}\n  BEST CONFIG (score={best.score:+.4f}  consistency_penalty={best.consistency_penalty:.4f})")
            for k, v in best.params.items():
                safe_print(f"    {k:<35} = {v}")
            safe_print(f"\n  Per-instrument breakdown:")
            for inst, data in best.instrument_results.items():
                safe_print(f"    {inst:<12} score={data.get('score', -999):>+.4f}")
            safe_print(f"{'='*65}\n")

    @staticmethod
    def _params_str(params: dict) -> str:
        return " ".join(f"{k.split('_')[-1]}={v}" for k, v in sorted(params.items()))


# ═══════════════════════════════════════════════════════════════════════════
# 8. CLI
# ═══════════════════════════════════════════════════════════════════════════

def _build_csv_paths(args: argparse.Namespace) -> dict[str, str]:
    """Resolve instrument→CSV mapping from CLI args."""
    csv_paths: dict[str, str] = {}

    if args.csv and args.instrument:
        csv_paths[args.instrument.upper()] = args.csv
        return csv_paths

    data_dir = Path(args.data_dir)
    instruments = [i.upper() for i in (args.instruments or [])]

    if instruments:
        for inst in instruments:
            # Try common filename patterns
            candidates = [
                data_dir / f"{inst}_M15.csv",
                data_dir / f"{inst}.csv",
                data_dir / f"{inst.lower()}_m15.csv",
            ]
            for c in candidates:
                if c.exists():
                    csv_paths[inst] = str(c)
                    break
            else:
                tuner_log.warning(f"No CSV found for {inst} in {data_dir} — skipping.")
    else:
        # Auto-discover all CSVs in data_dir
        for csv_file in sorted(data_dir.glob("*.csv")):
            inst = csv_file.stem.upper().replace("_M15", "").replace("_M1", "")
            csv_paths[inst] = str(csv_file)

    if not csv_paths:
        print(f"\n  ERROR: No CSV files resolved. Check --data-dir or --csv / --instrument.\n")
        sys.exit(1)

    return csv_paths


def main() -> None:
    ap = argparse.ArgumentParser(description="CRT Multi-Instrument Auto-Tuner [v3]")
    ap.add_argument("--csv",         help="Single M15 CSV path (use with --instrument)")
    ap.add_argument("--instrument",  help="Instrument name (e.g. GBPUSD)")
    ap.add_argument("--data-dir",    default="data", help="Directory with M15 CSVs")
    ap.add_argument("--instruments", nargs="+",       help="Instruments to tune (multi mode)")
    ap.add_argument("--output-dir",  default="results/tuner")
    ap.add_argument("--n-iter",      type=int,   default=100)
    ap.add_argument("--seed",        type=int,   default=42)
    ap.add_argument("--workers",     type=int,   default=os.cpu_count() or 4)
    ap.add_argument("--train-split", type=float, default=1.0,
                    help="Fraction of data for In-Sample training (e.g. 0.8)")
    ap.add_argument("--no-llm",      action="store_true",
                    help="Disable LLM gate (faster, fully deterministic)")

    args = ap.parse_args()
    csv_paths = _build_csv_paths(args)

    tuner = AutoTuner(
        csv_paths       = csv_paths,
        output_dir      = args.output_dir,
        n_iter_phase1   = args.n_iter,
        n_iter_phase2   = max(args.n_iter // 2, 20),
        seed            = args.seed,
        max_workers     = args.workers,
        train_split     = args.train_split,
        use_llm         = not args.no_llm,
    )
    tuner.run()


if __name__ == "__main__":
    main()
