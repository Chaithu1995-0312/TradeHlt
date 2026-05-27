"""
╔══════════════════════════════════════════════════════════════════════╗
║  CRT ENGINE -- PHASE-5: GAUSSIAN RECALIBRATION  (v5 -- unified)     ║
║                                                                      ║
║  SINGLE TRAINING VALIDATION SCRIPT for both Gaussian and TradeNet   ║
║                                                                      ║
║  Supports:                                                           ║
║    - Real CSV data from backtest results                             ║
║    - Synthetic data mode (--synthetic) for CI/smoke tests            ║
║    - 32-dim canonical features (GAUSSIAN_SCHEMA.n_features)          ║
║    - GaussianNBModel training and validation                         ║
║    - TradeNet training and validation (--tradenet)                   ║
║    - Save/load/inference verification for both models                ║
║                                                                      ║
║  DATA SOURCE                                                         ║
║    BacktestRunner → *_trades.csv → TradeRecord fields               ║
║    dataset_builder.build_gaussian_dataset() builds the full         ║
║    GAUSSIAN_SCHEMA.n_features-dimensional feature vector.           ║
║    Phase5 is an EVALUATOR, not a dataset builder.                   ║
║                                                                      ║
║  Usage:                                                              ║
║    python phase5_calibration.py --synthetic --train                 ║
║    python phase5_calibration.py --synthetic --train --tradenet      ║
║    python phase5_calibration.py --csv data/ --audit-only            ║
║    python phase5_calibration.py --csv data/ --train                 ║
║    python phase5_calibration.py --csv data/ --train --integrate     ║
║    python phase5_calibration.py --csv data/ --train --promote       ║
║    python phase5_calibration.py --cached models/phase5_dataset.json ║
╚══════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import os
import random
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from features.feature_schema import (
    GAUSSIAN_SCHEMA, TRADENET_SCHEMA, SCHEMA_VERSION,
    validate_vector,
)

from features.dataset_builder import (
    extract_feature_vector, build_dataset,
)

# ── Compatibility shims for functions that may not exist in dataset_builder ──
MIN_GAUSSIAN_SAMPLES  = 20
LAMBDA_DECAY_DEFAULT  = 0.0


def rr_to_class(rr: float) -> int:
    """Map pnl_rr_net float to 4-class label used by GaussianNBModel."""
    if rr < 0:
        return 0   # loss
    elif rr < 1.0:
        return 1   # small win
    elif rr < 2.0:
        return 2   # mid win
    else:
        return 3   # big win


def build_gaussian_dataset(
    trade_dicts: list[dict],
    lambda_decay: float = LAMBDA_DECAY_DEFAULT,
) -> tuple[list[list[float]], list[float]]:
    """
    Build (X, y_rr) from a list of trade dicts.
    Delegates feature extraction to dataset_builder.extract_feature_vector.
    """
    X: list[list[float]] = []
    y_rr: list[float]    = []
    skipped = 0
    for t in trade_dicts:
        try:
            rr = float(t.get("pnl_rr_net", t.get("rr", "")))
        except (TypeError, ValueError):
            skipped += 1
            continue
        try:
            vec = extract_feature_vector(t)
        except Exception:
            skipped += 1
            continue
        X.append(vec)
        y_rr.append(rr)

    if len(X) < MIN_GAUSSIAN_SAMPLES:
        raise ValueError(
            f"build_gaussian_dataset: only {len(X)} valid trades "
            f"(need >= {MIN_GAUSSIAN_SAMPLES}), skipped={skipped}"
        )
    return X, y_rr
from training.trainer import (
    GaussianNBModel, StandardScaler, train_gaussian,
    save_gaussian_model, load_gaussian_model, cross_val_gaussian,
    train as train_tradenet, save_model as save_tradenet_model,
    load_model as load_tradenet_model,
)
from training.evaluator import evaluate_gaussian, GaussianEvalResult, evaluate as evaluate_tradenet
from core.model_registry import (
    register_gaussian, promote_gaussian, get_active_gaussian,
)

log = logging.getLogger("Phase5")
logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S", level=logging.INFO,
)

from config_layer.production_config import PROD_VERSION as _P5_PROD_VERSION
log.info("Production config version: %s", _P5_PROD_VERSION)

MIN_LOO_CORR_FOR_INTEGRATION = 0.10
MIN_LOO_CORR_TO_SAVE         = 0.05
RR_BUCKET_MIDPOINTS          = [-0.5, 0.5, 1.5, 3.0]
RR_BUCKET_DEFAULTS           = [0.0, 1.0, 2.0]   # loss/small/mid/big edges


def _parse_float_csv(raw: str) -> list[float]:
    return [float(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_str_csv(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def _make_rr_to_class(buckets: list[float]):
    """Build an rr→class mapper from an ordered list of upper-bound thresholds.

    With buckets=[0.0, 1.0, 2.0] (default) yields 4 classes matching rr_to_class().
    """
    edges = sorted(buckets)

    def _classify(rr: float) -> int:
        for i, edge in enumerate(edges):
            if rr < edge:
                return i
        return len(edges)
    return _classify


def _apply_feature_mask(X: list[list[float]], keep_idx: list[int]) -> list[list[float]]:
    """Zero out features not in keep_idx. Preserves vector width so the trained
    model stays drop-in compatible with the existing 35-dim runtime."""
    keep = set(keep_idx)
    return [[v if i in keep else 0.0 for i, v in enumerate(row)] for row in X]


def _resolve_subset_indices(subset_names: list[str]) -> list[int]:
    from features.feature_schema import CANONICAL_FEATURE_ORDER
    idx_map = {name: i for i, name in enumerate(CANONICAL_FEATURE_ORDER)}
    bad = [n for n in subset_names if n not in idx_map]
    if bad:
        raise ValueError(
            f"--feature-subset references unknown feature(s): {bad}. "
            f"Valid: {CANONICAL_FEATURE_ORDER}"
        )
    return [idx_map[n] for n in subset_names]


# Direction-mirroring: normalize short records to "long perspective" so one model
# can serve both directions. Features that encode bullish/bearish bias are negated;
# paired binary features (higher_high↔lower_low) are swapped.
_MIRROR_NEGATE_FEATURES = frozenset({
    "ema_spread", "trend_bias", "trend_strength", "momentum_score",
    "rsi_14", "macd_line", "macd_signal", "macd_hist",
    "break_of_structure", "liquidity_sweep",
})
_MIRROR_SWAP_PAIRS = [
    ("higher_high", "lower_low"),
    ("swing_high",  "swing_low"),
]


def _mirror_short_vec(vec: list[float], feature_order) -> list[float]:
    """Return a mirrored copy of vec for a short record (long-perspective normalization)."""
    idx_map = {name: i for i, name in enumerate(feature_order)}
    result = list(vec)
    for fname in _MIRROR_NEGATE_FEATURES:
        idx = idx_map.get(fname)
        if idx is not None:
            result[idx] = -result[idx]
    for fa, fb in _MIRROR_SWAP_PAIRS:
        ia, ib = idx_map.get(fa), idx_map.get(fb)
        if ia is not None and ib is not None:
            result[ia], result[ib] = result[ib], result[ia]
    return result

DEFAULT_RESULTS_DIRS = [
    "results/tuner/runs_oos",   # auto_tuner_multi OOS runs (rglob finds run_*/INSTR_trades.csv)
    "results/tuner/runs",       # auto_tuner single-instrument runs
    # legacy portfolio dirs kept for backward compatibility
    "results/portfolio_p2", "results/portfolio_p4",
    "results/portfolio_p3_on", "results/portfolio_p32",
    "results/portfolio_p1",   "results/portfolio_phase1",
]

SCORER_CLASS_NAME    = "CRTCalibratedScorer"
SCORER_INSERT_MARKER = "class CRTGaussianScorer:"
SCORER_BLOCK_MARKER  = "# [Phase-5] CALIBRATED GAUSSIAN SCORER"


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def checksum_vector(x: list[float]) -> str:
    """Simple checksum of a feature vector for lineage tracking."""
    import hashlib
    return hashlib.md5(str([round(v, 6) for v in x]).encode()).hexdigest()[:12]


def _pass_fail(label: str, passed: bool, detail: str = "") -> None:
    """Print a PASS/FAIL line with optional detail."""
    status = "PASS OK" if passed else "FAIL !!"
    suffix = f"  ({detail})" if detail else ""
    print(f"  [{status}]  {label}{suffix}")


# ─────────────────────────────────────────────────────────────────────────────
# SYNTHETIC DATA GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def generate_synthetic_dataset(
    n_samples:  int   = 500,
    seed:       int   = 42,
    noise:      float = 0.3,
) -> "TradeDataset":
    """
    Generate synthetic trade dataset for CI/smoke tests.

    Creates GAUSSIAN_SCHEMA.n_features-dimensional feature vectors with a
    weak linear signal embedded so Gaussian correlation is positive.

    No real CSV files needed — allows full pipeline validation without data.

    Parameters
    ----------
    n_samples  : number of synthetic trades to generate
    seed       : random seed for reproducibility
    noise      : noise amplitude (0.0 = perfect signal, 1.0 = pure noise)

    Returns
    -------
    TradeDataset instance (source="synthetic")
    """
    n_features = GAUSSIAN_SCHEMA.n_features
    rng = random.Random(seed)

    X:    list[list[float]] = []
    y_rr: list[float]       = []

    # Embed a weak linear signal: feature 0 predicts outcome
    for i in range(n_samples):
        # Base features: standard-normal-ish via sum of uniforms (CLT)
        feats = [sum(rng.uniform(-1, 1) for _ in range(6)) / 3.0
                 for _ in range(n_features)]

        # Signal: feature 0 drives RR via a noisy linear relationship
        signal = feats[0]
        rr = 0.5 + 1.5 * signal + noise * (rng.random() - 0.5) * 4
        rr = max(-3.0, min(5.0, rr))  # clamp to realistic range

        X.append(feats)
        y_rr.append(round(rr, 4))

    log.info(
        f"generate_synthetic_dataset: {n_samples} samples x {n_features} features "
        f"(schema={GAUSSIAN_SCHEMA.name} v{SCHEMA_VERSION} seed={seed})"
    )

    return TradeDataset(
        trades=[],
        X=X,
        y_rr=y_rr,
        source="synthetic",
        n_instruments=1,
        instruments=["SYNTHETIC"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# TRADE DATASET
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TradeDataset:
    """
    Feature matrix + labels built from backtest TradeRecord data.
    All feature construction delegates to dataset_builder -- single path.
    """
    trades:        list[dict]
    X:             list[list[float]]
    y_rr:          list[float]
    source:        str = "unknown"
    n_instruments: int = 0
    instruments:   list[str] = field(default_factory=list)

    @classmethod
    def from_backtest_results(
        cls,
        results_dirs: list[str],
        base: str = ".",
        lambda_decay: float = LAMBDA_DECAY_DEFAULT,
    ) -> "TradeDataset":
        """
        Load from *_trades.csv files written by BacktestRunner/ReportWriter.
        These CSVs contain ALL TradeRecord fields -- the full
        GAUSSIAN_SCHEMA.n_features-dimensional feature schema is available
        with no zero-filling required.
        """
        base_path = Path(base)
        trade_dicts: list[dict] = []
        # Dedup key = (csv_path, trade_id) so the same trade_id from different
        # parameter-sweep runs on the same instrument is kept once per source file.
        # Using bare trade_id would discard real-feature runs whose IDs overlap
        # with earlier zero-feature tuner runs (CRT-0001, CRT-0002 … are reused
        # across every sweep run of the same dataset).
        seen_keys:   set[str]   = set()
        zero_feat_skipped: int  = 0
        instruments: set[str]   = set()

        for result_dir in results_dirs:
            for csv_path in (base_path / result_dir).rglob("*_trades.csv"):
                instr = csv_path.parent.name
                instruments.add(instr)
                with open(csv_path, newline="", encoding="utf-8-sig") as f:
                    for row in csv.DictReader(f):
                        tid = row.get("trade_id", "")
                        # compound key: source file + trade_id
                        dedup_key = f"{csv_path}|{tid}"
                        if dedup_key in seen_keys:
                            continue
                        seen_keys.add(dedup_key)
                        # Skip rows where ALL canonical features are zero —
                        # these come from skip_features=True tuner runs and
                        # carry no signal for GaussianNB training.
                        try:
                            _open = float(row.get("open") or 0)
                            _atr  = float(row.get("atr")  or 0)
                        except (ValueError, TypeError):
                            _open, _atr = 0.0, 0.0
                        if _open == 0.0 and _atr == 0.0:
                            zero_feat_skipped += 1
                            continue
                        row["instrument"] = row.get("instrument", instr)
                        trade_dicts.append(row)

        if zero_feat_skipped:
            log.info(
                "from_backtest_results: skipped %d zero-feature rows "
                "(from skip_features=True tuner runs — use backtest_v2.py "
                "directly for training data).",
                zero_feat_skipped,
            )

        if not trade_dicts:
            raise ValueError(
                f"No trades found in {results_dirs} under base='{base}'. "
                "Run backtest_v2.py first to generate *_trades.csv files."
            )

        log.info(
            f"from_backtest_results: {len(trade_dicts)} trades, "
            f"instruments: {sorted(instruments)}"
        )
        return cls._build(trade_dicts, "csv_results", sorted(instruments), lambda_decay)

    @classmethod
    def from_opportunities(
        cls,
        path: str | Path,
        mirror_short: bool = True,
    ) -> "TradeDataset":
        """Load Pipeline-B opportunity logs (unbiased ground-truth labels).

        Reads JSONL records produced by scripts/research/opportunity_scanner.py.
        Each record contributes one training sample with the achieved RR as the
        target. CRT is NOT consulted — this is the unbiased training path.

        mirror_short: when True (default), short records have directional features
        negated/swapped so all training samples are in "long perspective". This
        allows one model to serve both directions. The runtime must apply the same
        mirroring when calling compute() for short trades.
        """
        from features.feature_pipeline import build_feature_vector
        from features.feature_schema import CANONICAL_FEATURES, CANONICAL_FEATURE_ORDER

        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"opportunities log not found: {p}")

        X: list[list[float]] = []
        y_rr: list[float] = []
        instruments: set[str] = set()
        skipped = 0
        skip_reasons: dict[str, int] = defaultdict(int)
        n_mirrored = 0
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    skipped += 1
                    skip_reasons["bad_json"] += 1
                    continue
                feats = rec.get("features")
                if not isinstance(feats, dict):
                    skipped += 1
                    skip_reasons["no_features"] += 1
                    continue
                missing = [k for k in CANONICAL_FEATURES if k not in feats]
                if missing:
                    skipped += 1
                    skip_reasons["missing_keys"] += 1
                    continue
                try:
                    vec = build_feature_vector(feats)
                    rr  = float(rec.get("rr_achieved", 0.0))
                except (TypeError, ValueError):
                    skipped += 1
                    skip_reasons["bad_vector"] += 1
                    continue
                if mirror_short and rec.get("direction") == "short":
                    vec = _mirror_short_vec(vec, CANONICAL_FEATURE_ORDER)
                    n_mirrored += 1
                X.append(vec)
                y_rr.append(rr)
                if rec.get("instrument"):
                    instruments.add(str(rec["instrument"]))

        if len(X) < MIN_GAUSSIAN_SAMPLES:
            raise ValueError(
                f"from_opportunities: only {len(X)} usable samples in {p} "
                f"(need >= {MIN_GAUSSIAN_SAMPLES}). Skipped={skipped} ({dict(skip_reasons)})"
            )

        log.info(
            "from_opportunities: %d samples from %s (skipped=%d, mirrored=%d, instruments=%s)",
            len(X), p, skipped, n_mirrored, sorted(instruments),
        )
        return cls(
            trades=[], X=X, y_rr=y_rr, source=f"opportunities:{p.name}",
            n_instruments=len(instruments), instruments=sorted(instruments),
        )

    @classmethod
    def from_live_alerts(
        cls,
        path: "str | Path",
        mirror_short: bool = True,
    ) -> "TradeDataset":
        """Load JSONL produced by scripts/research/ingest_live_outcomes.py.

        The ingest script's output schema is identical to opportunities.jsonl
        (features dict + rr_achieved + direction + instrument), so this wrapper
        delegates to ``from_opportunities`` and only retags the source for
        downstream provenance tracking. Closes the feedback loop on live-
        executed trades whose outcomes have been paired with their originating
        alerts.
        """
        ds = cls.from_opportunities(path, mirror_short=mirror_short)
        p = Path(path)
        return cls(
            trades=ds.trades, X=ds.X, y_rr=ds.y_rr,
            source=f"live_alerts:{p.name}",
            n_instruments=ds.n_instruments, instruments=ds.instruments,
        )

    @classmethod
    def from_trade_records(
        cls,
        trade_records: list,
        lambda_decay: float = LAMBDA_DECAY_DEFAULT,
    ) -> "TradeDataset":
        """
        Build directly from in-memory TradeRecord dataclass objects.
        Use when you have backtest results without the CSV round-trip.
        """
        if not trade_records:
            raise ValueError("trade_records is empty")
        dicts: list[dict] = []
        instruments: set[str] = set()
        for t in trade_records:
            d = t.__dict__.copy() if hasattr(t, "__dict__") else dict(t)
            instruments.add(str(d.get("instrument", "UNKNOWN")))
            dicts.append(d)
        log.info(f"from_trade_records: {len(dicts)} trades, instruments: {sorted(instruments)}")
        return cls._build(dicts, "trade_records", sorted(instruments), lambda_decay)

    @classmethod
    def _build(
        cls,
        trade_dicts: list[dict],
        source: str,
        instruments: list[str],
        lambda_decay: float,
    ) -> "TradeDataset":
        try:
            X, y_rr = build_gaussian_dataset(trade_dicts, lambda_decay=lambda_decay)
        except ValueError as e:
            raise ValueError(
                f"Phase5 dataset build failed [{source}]: {e}\n"
                f"{len(trade_dicts)} raw trades loaded, "
                f"minimum required: {MIN_GAUSSIAN_SAMPLES}."
            ) from e

        # Spot-check schema compliance
        for i, x in enumerate(X[:5]):
            validate_vector(x, GAUSSIAN_SCHEMA, f"phase5.TradeDataset._build[{i}]")

        log.info(
            f"TradeDataset: {len(X)} samples x {GAUSSIAN_SCHEMA.n_features} features "
            f"(schema={GAUSSIAN_SCHEMA.name} v{SCHEMA_VERSION})"
        )
        return cls(
            trades=trade_dicts, X=X, y_rr=y_rr, source=source,
            n_instruments=len(instruments), instruments=instruments,
        )

    def export(self, path: str = "models/phase5_dataset.json") -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "schema_name":    GAUSSIAN_SCHEMA.name,
            "schema_version": SCHEMA_VERSION,
            "schema_checksum": GAUSSIAN_SCHEMA.checksum,
            "feature_names":  list(GAUSSIAN_SCHEMA.feature_names),
            "n_samples":      len(self.X),
            "n_instruments":  self.n_instruments,
            "instruments":    self.instruments,
            "source":         self.source,
            "exported_at":    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "X":              self.X,
            "y_rr":           self.y_rr,
        }, indent=2))
        log.info(f"Dataset exported -> {out}")
        return out

    @classmethod
    def load_cached(cls, path: str) -> "TradeDataset":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Cached dataset not found: {p}")
        payload = json.loads(p.read_text())
        saved_v = payload.get("schema_version")
        if saved_v != SCHEMA_VERSION:
            raise ValueError(
                f"Cached dataset schema_version='{saved_v}' != current '{SCHEMA_VERSION}'. "
                "Re-run backtest to rebuild."
            )
        log.info(f"Loaded cached dataset: {len(payload['X'])} samples from {p}")
        return cls(
            trades=[], X=payload["X"], y_rr=payload["y_rr"], source="cached",
            n_instruments=payload.get("n_instruments", 0),
            instruments=payload.get("instruments", []),
        )


# ─────────────────────────────────────────────────────────────────────────────
# CALIBRATION RESULT
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CalibrationResult:
    n_samples:            int
    n_instruments:        int
    instruments:          list[str]
    schema_version:       str
    model:                GaussianNBModel
    scaler:               StandardScaler
    train_metrics:        dict
    cv_metrics:           dict
    eval_result:          GaussianEvalResult
    loo_metrics:          Optional[dict] = None
    integration_approved: bool = False
    verdict:              str  = ""
    model_path:           Optional[Path] = None

    def print_summary(self) -> None:
        W = 66
        print(f"\n{'=' * W}")
        print(f"  PHASE-5 CALIBRATION RESULT  (schema: {self.schema_version})")
        print(f"{'=' * W}")
        print(f"  Dataset        : {self.n_samples} samples  |  {', '.join(self.instruments)}")
        print(f"  train corr     : {self.train_metrics.get('corr_expected_rr', 0):+.4f}")
        print(f"  train cal_err  : {self.train_metrics.get('calibration_error', 0):+.4f}")
        print(f"  CV corr mean   : {self.cv_metrics.get('corr_mean', 0):+.4f}  "
              f"std={self.cv_metrics.get('corr_std', 0):.4f}  "
              f"stable={self.cv_metrics.get('stable', False)}")
        if self.loo_metrics:
            print(f"  LOO corr       : {self.loo_metrics.get('loo_corr', 0):+.4f}  "
                  f"n={self.loo_metrics['n_loo']}")
        print(f"  eval corr      : {self.eval_result.corr_expected_rr:+.4f}")
        print(f"  eval cal_err   : {self.eval_result.calibration_error:+.4f}")
        print(f"  mean pred/act  : {self.eval_result.mean_expected_rr:.4f} / {self.eval_result.mean_actual_rr:.4f}")
        print(f"  class dist     : {self.eval_result.class_distribution}")
        print(f"  Verdict        : {self.verdict}")
        if self.model_path:
            print(f"  Saved          : {self.model_path}")
        print(f"{'=' * W}\n")


# ─────────────────────────────────────────────────────────────────────────────
# CALIBRATION PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def run_calibration(
    dataset:     TradeDataset,
    train_ratio: float = 0.70,
    run_loo:     bool  = False,
    version:     str   = "",
) -> CalibrationResult:
    """
    Full calibration pipeline.
    1. train_gaussian()        → GaussianNBModel + scaler + train_metrics
    2. cross_val_gaussian()    → stability metrics
    3. evaluate_gaussian()     → GaussianEvalResult on full dataset
    4. LOO-CV                  → if run_loo or n < 500
    5. Verdict                 → integration_approved decision
    """
    X, y_rr = dataset.X, dataset.y_rr
    n = len(X)
    log.info(f"run_calibration: n={n} instruments={dataset.instruments}")

    # 1. Train
    model, scaler, train_metrics = train_gaussian(X, y_rr, train_ratio=train_ratio)
    log.info(f"train_gaussian: corr={train_metrics['corr_expected_rr']:+.4f} "
             f"cal_err={train_metrics['calibration_error']:.4f}")

    # 2. Cross-validation
    try:
        cv_metrics = cross_val_gaussian(X, y_rr, n_folds=3)
        log.info(f"cross_val: mean={cv_metrics['corr_mean']:+.4f} "
                 f"std={cv_metrics['corr_std']:.4f} stable={cv_metrics['stable']}")
    except ValueError as e:
        log.warning(f"cross_val_gaussian skipped: {e}")
        cv_metrics = {"corr_mean": 0.0, "corr_std": 0.0, "stable": False, "n_folds": 0}

    # 3. Full-dataset evaluation
    eval_result = evaluate_gaussian(model, scaler, X, y_rr)
    log.info(f"evaluate_gaussian: corr={eval_result.corr_expected_rr:+.4f}")

    # 4. LOO-CV
    loo_metrics = None
    if run_loo or n < 500:
        log.info(f"Running LOO-CV ({n} folds)...")
        y_cls    = [rr_to_class(r) for r in y_rr]
        X_scaled = scaler.transform(X)
        loo_metrics = _leave_one_out_cv(model, X_scaled, y_cls, y_rr)
        log.info(f"LOO: corr={loo_metrics.get('loo_corr', 0):+.4f} n={loo_metrics['n_loo']}")

    # 5. Verdict
    corr     = eval_result.corr_expected_rr
    stable   = cv_metrics.get("stable", False)
    cv_mean  = cv_metrics.get("corr_mean", 0.0)

    if corr >= MIN_LOO_CORR_FOR_INTEGRATION and stable:
        approved = True
        verdict  = (f"APPROVED -- corr={corr:+.4f} >= {MIN_LOO_CORR_FOR_INTEGRATION} "
                    f"and CV stable (std={cv_metrics.get('corr_std', 0):.4f})")
    elif corr >= MIN_LOO_CORR_FOR_INTEGRATION and not stable:
        approved = False
        verdict  = (f"UNSTABLE -- corr={corr:+.4f} passes threshold but "
                    f"CV std={cv_metrics.get('corr_std', 0):.4f} >= 0.05. Collect more data.")
    elif corr > 0:
        approved = False
        verdict  = (f"MARGINAL -- corr={corr:+.4f} positive but below "
                    f"integration threshold {MIN_LOO_CORR_FOR_INTEGRATION}.")
    else:
        approved = False
        verdict  = (f"REJECTED -- corr={corr:+.4f} <= 0. "
                    f"GaussianNB adds no signal. Accumulate more diverse trade history.")

    if loo_metrics and loo_metrics.get("loo_corr", 0) < 0 and approved:
        approved = False
        verdict += (f" [OVERRIDE: LOO corr={loo_metrics['loo_corr']:+.4f} < 0 "
                    f"-- signal does not generalise out-of-sample]")

    return CalibrationResult(
        n_samples=n, n_instruments=dataset.n_instruments,
        instruments=dataset.instruments, schema_version=SCHEMA_VERSION,
        model=model, scaler=scaler,
        train_metrics=train_metrics, cv_metrics=cv_metrics,
        eval_result=eval_result, loo_metrics=loo_metrics,
        integration_approved=approved, verdict=verdict,
    )


def _leave_one_out_cv(
    model:    GaussianNBModel,
    X_scaled: list[list[float]],
    y_cls:    list[int],
    y_rr:     list[float],
) -> dict:
    """LOO-CV: re-trains fresh model for each held-out sample."""
    n = len(X_scaled)
    predicted: list[float] = []
    actual:    list[float] = []
    for i in range(n):
        X_tr = [X_scaled[j] for j in range(n) if j != i]
        y_tr = [y_cls[j]    for j in range(n) if j != i]
        if len(set(y_tr)) < 2:
            continue
        fold_model = GaussianNBModel()
        fold_model.fit(X_tr, y_tr)
        exp_rr, _, _ = fold_model.predict_expected_rr(X_scaled[i])
        predicted.append(exp_rr)
        actual.append(y_rr[i])

    n2 = len(predicted)
    if n2 < 5:
        return {"loo_corr": float("nan"), "n_loo": n2}

    mp  = sum(predicted) / n2
    ma  = sum(actual)    / n2
    cov = sum((p - mp) * (a - ma) for p, a in zip(predicted, actual)) / n2
    sp  = (sum((p - mp) ** 2 for p in predicted) / n2) ** 0.5
    sa  = (sum((a - ma) ** 2 for a in actual)    / n2) ** 0.5
    corr = cov / (sp * sa) if sp > 0 and sa > 0 else 0.0
    return {
        "loo_corr":          round(corr, 4),
        "n_loo":             n2,
        "mean_predicted_rr": round(sum(predicted) / n2, 4),
        "mean_actual_rr":    round(sum(actual)    / n2, 4),
    }


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT REPORT
# ─────────────────────────────────────────────────────────────────────────────

def audit_report(dataset: TradeDataset) -> None:
    X, y_rr, n = dataset.X, dataset.y_rr, len(dataset.X)
    W = 66
    print(f"\n{'=' * W}")
    print(f"  PHASE-5 DATA AUDIT  (schema v{SCHEMA_VERSION})")
    print(f"{'=' * W}")
    print(f"  Source      : {dataset.source}")
    print(f"  Samples     : {n}")
    print(f"  Features    : {GAUSSIAN_SCHEMA.n_features} (GAUSSIAN_SCHEMA -- no zero-fill)")
    print(f"  Instruments : {', '.join(dataset.instruments)}")

    if n < MIN_GAUSSIAN_SAMPLES:
        print(f"\n  WARNING: {n} samples < minimum {MIN_GAUSSIAN_SAMPLES}. "
              "High variance expected.")

    # RR distribution
    y_cls   = [rr_to_class(r) for r in y_rr]
    labels  = ["<0 (loss)", "0-1R (small)", "1-2R (mid)", ">2R (strong)"]
    counts  = [y_cls.count(c) for c in range(4)]
    print(f"\n-- RR DISTRIBUTION {'-' * 45}")
    for lbl, cnt in zip(labels, counts):
        pct = cnt / n if n else 0
        print(f"  {lbl:<14}  {cnt:>4}  {pct:>5.1%}  {'#' * int(pct * 32)}")
    if counts[0] / n > 0.55:
        print(f"\n  WARNING: {counts[0]/n:.0%} losses. Use CV corr, not accuracy.")

    # Feature stats
    print(f"\n-- FEATURE STATISTICS {'-' * 42}")
    print(f"  {'Feature':<22}  {'Mean':>8}  {'Std':>8}  {'Min':>8}  {'Max':>8}")
    for fi, fname in enumerate(GAUSSIAN_SCHEMA.feature_names):
        vals = [x[fi] for x in X]
        mean = sum(vals) / n
        std  = (sum((v - mean) ** 2 for v in vals) / n) ** 0.5
        flag = "  ZERO-VARIANCE WARNING" if std < 1e-6 else ""
        print(f"  {fname:<22}  {mean:>8.4f}  {std:>8.4f}  {min(vals):>8.4f}  {max(vals):>8.4f}{flag}")

    # Per-instrument
    if dataset.trades:
        by_instr: dict[str, list[float]] = defaultdict(list)
        for t in dataset.trades:
            try:
                rr = float(t.get("pnl_rr_net", ""))
                by_instr[str(t.get("instrument", "?"))].append(rr)
            except (TypeError, ValueError):
                pass
        if by_instr:
            print(f"\n-- PER-INSTRUMENT {'-' * 47}")
            for instr, rrs in sorted(by_instr.items()):
                wr  = sum(1 for r in rrs if r > 0) / len(rrs)
                avg = sum(rrs) / len(rrs)
                print(f"  {instr:<12}  n={len(rrs):>4}  WR={wr:.0%}  AvgRR={avg:+.3f}R")

    # Data lineage
    if X:
        print(f"\n-- DATA LINEAGE {'-' * 49}")
        print(f"  schema_checksum : {GAUSSIAN_SCHEMA.checksum}")
        print(f"  X[0] checksum   : {checksum_vector(X[0])}")
        print(f"  schema_version  : {SCHEMA_VERSION}")
    print(f"{'=' * W}\n")


# ─────────────────────────────────────────────────────────────────────────────
# POST-TRAINING VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def verify_gaussian_model(
    model_path: Path,
    test_X:     list[list[float]],
    test_y_rr:  list[float],
) -> bool:
    """
    Load saved Gaussian model from disk and run inference on test set.

    Asserts:
    - Model loads without error
    - Predictions have correct shape (n_test,)
    - All predicted RR values are finite
    - Correlation with actual RR is computable

    Returns True if all checks pass.
    """
    W = 66
    print(f"\n{'-' * W}")
    print(f"  GAUSSIAN POST-TRAINING VERIFICATION")
    print(f"{'-' * W}")

    passed_all = True

    # 1. Load model
    try:
        loaded_model, loaded_scaler, _ = load_gaussian_model(
            str(model_path.relative_to(Path("models")))
        )
        _pass_fail("Load saved model", True, f"{model_path}")
    except Exception as e:
        _pass_fail("Load saved model", False, str(e))
        return False

    # 2. Shape check
    try:
        n_test = len(test_X)
        X_scaled = loaded_scaler.transform(test_X)
        pred_rr = [loaded_model.predict_expected_rr(x)[0] for x in X_scaled]
        shape_ok = len(pred_rr) == n_test
        _pass_fail("Inference output shape", shape_ok,
                   f"expected {n_test}, got {len(pred_rr)}")
        if not shape_ok:
            passed_all = False
    except Exception as e:
        _pass_fail("Inference output shape", False, str(e))
        return False

    # 3. Value range check
    all_finite = all(math.isfinite(v) for v in pred_rr)
    _pass_fail("All predictions finite", all_finite,
               f"n_predictions={len(pred_rr)}")
    if not all_finite:
        passed_all = False

    # 4. Correlation check
    try:
        n = len(pred_rr)
        mp = sum(pred_rr) / n
        ma = sum(test_y_rr) / n
        cov = sum((p - mp) * (a - ma) for p, a in zip(pred_rr, test_y_rr)) / n
        sp = (sum((p - mp) ** 2 for p in pred_rr) / n) ** 0.5
        sa = (sum((a - ma) ** 2 for a in test_y_rr) / n) ** 0.5
        corr = cov / (sp * sa) if sp > 0 and sa > 0 else 0.0
        corr_ok = math.isfinite(corr)
        _pass_fail("Correlation computable", corr_ok,
                   f"corr={corr:+.4f} on {n} test samples")
        if not corr_ok:
            passed_all = False
    except Exception as e:
        _pass_fail("Correlation computable", False, str(e))
        passed_all = False

    # 5. Feature dim check
    dim_ok = loaded_model.n_features == GAUSSIAN_SCHEMA.n_features
    _pass_fail(
        "Feature dimensions match schema",
        dim_ok,
        f"model={loaded_model.n_features}, schema={GAUSSIAN_SCHEMA.n_features}",
    )
    if not dim_ok:
        passed_all = False

    print(f"{'-' * W}")
    print(f"  Gaussian verification: {'ALL PASSED' if passed_all else 'SOME FAILED'}")
    print(f"{'-' * W}\n")
    return passed_all


def verify_tradenet_model(
    model_path: Path,
    test_X:     list[list[float]],
    test_y_bin: list[int],
) -> bool:
    """
    Load saved TradeNet model from disk and run inference on test set.

    Asserts:
    - Model loads without error
    - Predictions have correct shape (n_test,)
    - All predicted probabilities are in [0, 1]
    - Accuracy is computable

    Returns True if all checks pass.
    """
    W = 66
    print(f"\n{'-' * W}")
    print(f"  TRADENET POST-TRAINING VERIFICATION")
    print(f"{'-' * W}")

    passed_all = True

    # 1. Try to load model
    try:
        import torch
        loaded_model = load_tradenet_model(
            str(model_path.relative_to(Path("models")))
        )
        _pass_fail("Load saved TradeNet model", True, f"{model_path}")
    except ImportError:
        _pass_fail("Load saved TradeNet model", False,
                   "torch not installed — TradeNet verification skipped")
        return True  # Not a failure if torch is absent
    except Exception as e:
        _pass_fail("Load saved TradeNet model", False, str(e))
        return False

    # 2. Inference shape
    try:
        import torch
        n_test = len(test_X)
        X_t    = torch.tensor(test_X, dtype=torch.float32)
        with torch.no_grad():
            preds_raw = loaded_model(X_t).numpy().flatten().tolist()
        shape_ok = len(preds_raw) == n_test
        _pass_fail("Inference output shape", shape_ok,
                   f"expected {n_test}, got {len(preds_raw)}")
        if not shape_ok:
            passed_all = False
    except Exception as e:
        _pass_fail("Inference output shape", False, str(e))
        return False

    # 3. Value range [0, 1]
    range_ok = all(0.0 <= p <= 1.0 for p in preds_raw)
    _pass_fail("Predictions in [0, 1]", range_ok,
               f"min={min(preds_raw):.4f} max={max(preds_raw):.4f}")
    if not range_ok:
        passed_all = False

    # 4. Accuracy check
    try:
        threshold   = 0.5
        pred_labels = [1 if p >= threshold else 0 for p in preds_raw]
        n           = len(pred_labels)
        correct     = sum(pl == yl for pl, yl in zip(pred_labels, test_y_bin))
        accuracy    = correct / n if n > 0 else 0.0
        acc_ok      = math.isfinite(accuracy)
        _pass_fail("Accuracy computable", acc_ok,
                   f"accuracy={accuracy:.4f} on {n} test samples")
        if not acc_ok:
            passed_all = False
    except Exception as e:
        _pass_fail("Accuracy computable", False, str(e))
        passed_all = False

    # 5. Feature dim check
    try:
        import torch
        first_layer_in = list(loaded_model.parameters())[0].shape[1]
        dim_ok = first_layer_in == TRADENET_SCHEMA.n_features
        _pass_fail(
            "Feature dimensions match schema",
            dim_ok,
            f"model={first_layer_in}, schema={TRADENET_SCHEMA.n_features}",
        )
        if not dim_ok:
            passed_all = False
    except Exception as e:
        _pass_fail("Feature dimensions check", False, str(e))
        passed_all = False

    print(f"{'-' * W}")
    print(f"  TradeNet verification: {'ALL PASSED' if passed_all else 'SOME FAILED'}")
    print(f"{'-' * W}\n")
    return passed_all


# ─────────────────────────────────────────────────────────────────────────────
# TRADENET TRAINING PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def run_tradenet_training(
    dataset:     TradeDataset,
    version:     str,
    train_ratio: float = 0.70,
    epochs:      int   = 100,
    lr:          float = 0.001,
    instrument:  str   = "",
    run_id:      str   = "",
) -> Optional[Path]:
    """
    Train TradeNet binary classifier on the same feature vectors as Gaussian.

    Binary labels: 1 = trade is a win (RR >= 1.0), 0 = loss.

    Steps:
    1. Split dataset (time-ordered, no shuffle)
    2. Train TradeNet via trainer.train()
    3. Evaluate on held-out test set
    4. Save model
    5. Verify save/load/inference round-trip

    Returns path to saved model, or None if training failed.
    """
    W = 66
    print(f"\n{'=' * W}")
    print(f"  TRADENET TRAINING  (schema: {SCHEMA_VERSION})")
    print(f"{'=' * W}")

    # Gap-6 fix: hard crash instead of silent skip — torch is mandatory for TradeNet.
    # torch 2.2.2+cpu is installed for Python 3.12 only.  If you see this error,
    # re-run the entire command with  py -3.12  instead of  python.
    try:
        import torch
    except ImportError:
        import sys as _sys
        _sys.stderr.write(
            "\n"
            "====================================================================\n"
            "  FATAL: torch not found in this Python environment\n"
            "\n"
            "  TradeNet training requires PyTorch (torch 2.2.2+cpu).\n"
            "  torch is installed for Python 3.12, NOT the current Python.\n"
            "\n"
            "  Fix -- re-run with py -3.12:\n"
            "    py -3.12 scripts/training/phase5_calibration.py \\\n"
            "        --opportunities <file> --version <ver> --train --tradenet\n"
            "\n"
            "  Verify torch: py -3.12 -c \"import torch; print(torch.__version__)\"\n"
            "====================================================================\n"
            "\n"
        )
        _sys.exit(1)

    X, y_rr = dataset.X, dataset.y_rr
    n       = len(X)

    # Binary labels: win = RR >= 1.0
    y_bin = [1 if r >= 1.0 else 0 for r in y_rr]

    # Time-ordered split
    n_train = int(n * train_ratio)
    n_test  = n - n_train

    if n_train < 50:
        print(f"  [SKIP] TradeNet: insufficient training samples ({n_train} < 50).")
        return None, {}

    X_train, y_train = X[:n_train], y_bin[:n_train]
    X_test,  y_test  = X[n_train:], y_bin[n_train:]

    print(f"  Samples: {n} total  |  {n_train} train  |  {n_test} test")
    print(f"  Win rate (train): {sum(y_train)/len(y_train):.2%}")

    # ── Normalise features (mirrors the Gaussian pipeline) ────────────────────
    # Raw features span vastly different scales:
    #   open/close/ema_*  ≈ 60000  vs  trend_bias/body_ratio  ≈ 1.0
    # Without scaling, large-magnitude gradients dominate and suppress indicator
    # signals, causing the model to collapse to the majority class (loss).
    from training.trainer import StandardScaler as TnScaler
    tn_scaler = TnScaler()
    tn_scaler.fit(X_train)                                  # fit on train only (no leakage)
    X_train_sc = tn_scaler.transform(X_train)
    X_test_sc  = tn_scaler.transform(X_test) if X_test else []
    print(f"  StandardScaler fit: {TRADENET_SCHEMA.n_features} features "
          f"(n_train={n_train})")

    # Train on SCALED data.
    # class_weight_auto=True (default) applies pos_weight = n_neg/n_pos per batch
    # to prevent majority-class (loss) collapse.
    try:
        print(f"  Training TradeNet for {epochs} epochs...")
        tn_model = train_tradenet(
            X_train_sc, y_train,
            epochs=epochs, lr=lr, batch_size=64, verbose=True,
        )
    except Exception as e:
        print(f"  [ERROR] TradeNet training failed: {e}")
        import traceback; traceback.print_exc()
        return None, {}

    # Evaluate on SCALED test set — Gap-2 fix: capture metrics dict for registry
    tn_metrics: dict = {}
    if n_test > 0:
        try:
            tn_eval = evaluate_tradenet(tn_model, X_test_sc, y_test)
            tn_eval.print(label="TradeNet test")
            print(f"  accuracy={tn_eval.accuracy:.4f}  composite={tn_eval.composite_score:.4f}")
            tn_metrics = {
                "accuracy":        round(float(tn_eval.accuracy),        4),
                "composite_score": round(float(tn_eval.composite_score), 4),
                "n_train":         n_train,
                "n_test":          n_test,
            }
        except Exception as e:
            print(f"  [WARN] TradeNet evaluation failed: {e}")

    # Save — Gap-1 fix: pass version= explicitly so registry key matches version string.
    # Also pass scaler= so make_neural_fn() can apply the same normalisation at
    # inference time (saves alongside .pth as tradenet_{version}_scaler.json).
    if instrument:
        model_filename = f"{instrument}/{run_id}/tradenet_{version}.pth"
    else:
        model_filename = f"tradenet_{version}.pth"
    try:
        model_path = save_tradenet_model(tn_model, model_filename,
                                         metrics=tn_metrics, version=version,
                                         scaler=tn_scaler,
                                         instrument=instrument or None,
                                         run_id=run_id or None)
        print(f"  TradeNet saved -> {model_path}")
    except Exception as e:
        print(f"  [ERROR] TradeNet save failed: {e}")
        return None, {}

    # Post-training verification (use scaled data for consistency)
    if n_test > 0:
        verify_tradenet_model(model_path, X_test_sc, y_test)
    else:
        verify_tradenet_model(model_path, X_train_sc[:20], y_train[:20])

    # Gap-3 fix: return (path, metrics) so caller can patch p5 report
    return model_path, tn_metrics


# ─────────────────────────────────────────────────────────────────────────────
# SCORER INTEGRATION
# ─────────────────────────────────────────────────────────────────────────────


def integrate_scorer(result: CalibrationResult, base: str = ".", force: bool = False) -> bool:
    """Inject CRTCalibratedScorer into backtest_v2.py.
    Drop-in replacement for CRTGaussianScorer using full GAUSSIAN_SCHEMA.n_features-feature schema.
    Only runs if result.integration_approved or force=True.
    """
    if not result.integration_approved and not force:
        log.warning("integrate_scorer: blocked (integration_approved=False). Use --force.")
        return False

    model_d  = result.model.to_dict()
    scaler_d = result.scaler.to_dict()
    params   = {
        "schema_version":  SCHEMA_VERSION,
        "schema_checksum": GAUSSIAN_SCHEMA.checksum,
        "feature_names":   list(GAUSSIAN_SCHEMA.feature_names),
        "n_features":      GAUSSIAN_SCHEMA.n_features,
        "n_classes":       model_d["n_classes"],
        "class_priors":    model_d["class_priors"],
        "means":           model_d["means"],
        "vars":            model_d["vars"],
        "rr_weights":      [0.0, 0.5, 1.5, 2.5],
        "scaler_mean":     scaler_d["mean"],
        "scaler_std":      scaler_d["std"],
    }
    params_json = json.dumps(params, separators=(",", ":"))

    n_loo    = result.loo_metrics["n_loo"]    if result.loo_metrics else "n/a"
    loo_corr = result.loo_metrics["loo_corr"] if result.loo_metrics else "n/a"
    corr_str = f"{result.eval_result.corr_expected_rr:+.4f}"
    cv_mean  = f"{result.cv_metrics.get('corr_mean', 0):+.4f}"
    cv_std   = f"{result.cv_metrics.get('corr_std',  0):.4f}"
    cv_stab  = str(result.cv_metrics.get('stable', False))
    instrs   = ", ".join(result.instruments)

    # Build scorer block header and class body without nested triple-quotes
    hdr  = "\n\n"
    hdr += "# " + "-" * 65 + "\n"
    hdr += "# " + SCORER_BLOCK_MARKER + "\n"
    hdr += "# Schema  : " + SCHEMA_VERSION + " (checksum: " + GAUSSIAN_SCHEMA.checksum + ")\n"
    hdr += "# Samples : " + str(result.n_samples) + " (" + ", ".join(result.instruments) + ")\n"
    hdr += "# Corr    : " + corr_str + "\n"
    hdr += "# CV      : mean=" + cv_mean + " std=" + cv_std + " stable=" + cv_stab + "\n"
    hdr += "# LOO     : corr=" + str(loo_corr) + " n=" + str(n_loo) + "\n"
    hdr += "# Verdict : " + result.verdict + "\n"
    hdr += "# Generated by phase5_calibration.py v5 -- do not edit manually.\n"
    hdr += "# " + "-" * 65 + "\n"
    hdr += "\n_P5_PARAMS = " + params_json + "\n\n"

    cls  = "class " + SCORER_CLASS_NAME + ":\n"
    cls += "    # Phase-5 GaussianNB scorer (v5) -- drop-in for CRTGaussianScorer.\n"
    cls += f"    # Full {GAUSSIAN_SCHEMA.n_features}-feature GAUSSIAN_SCHEMA. No zero-filled features.\n"
    cls += "    # compute() accepts cached_features dict from CRTEngine.\n"
    cls += "\n"
    cls += "    def __init__(self):\n"
    cls += "        p = _P5_PARAMS\n"
    cls += "        self._n_features  = p['n_features']\n"
    cls += "        self._n_classes   = p['n_classes']\n"
    cls += "        self._priors      = p['class_priors']\n"
    cls += "        self._means       = p['means']\n"
    cls += "        self._vars        = p['vars']\n"
    cls += "        self._rr_weights  = p['rr_weights']\n"
    cls += "        self._scaler_mean = p['scaler_mean']\n"
    cls += "        self._scaler_std  = p['scaler_std']\n"
    cls += "\n"
    cls += "    def _scale(self, x):\n"
    cls += "        return [(x[i] - self._scaler_mean[i]) / self._scaler_std[i]\n"
    cls += "                for i in range(self._n_features)]\n"
    cls += "\n"
    cls += "    def _predict_proba(self, xs):\n"
    cls += "        import math as _m\n"
    cls += "        lp = []\n"
    cls += "        for c in range(self._n_classes):\n"
    cls += "            v = _m.log(self._priors[c] + 1e-300)\n"
    cls += "            for f in range(self._n_features):\n"
    cls += "                mu, va = self._means[c][f], self._vars[c][f]\n"
    cls += "                v -= 0.5 * _m.log(2 * _m.pi * va) + (xs[f] - mu) ** 2 / (2 * va)\n"
    cls += "            lp.append(v)\n"
    cls += "        mx = max(lp)\n"
    cls += "        ex = [_m.exp(v - mx) for v in lp]\n"
    cls += "        t  = sum(ex)\n"
    cls += "        return [e / t for e in ex]\n"
    cls += "\n"
    cls += "    def compute(self, features, candle_idx):\n"
    cls += "        if not features:\n"
    cls += "            return None\n"
    cls += "        try:\n"
    cls += "            from features.dataset_builder import build_feature_vector as _b\n"
    cls += "            x  = _b(features)\n"
    cls += "            p  = self._predict_proba(self._scale(x))\n"
    cls += "            er = sum(w * q for w, q in zip(self._rr_weights, p))\n"
    cls += "            sc = min(1.0, max(0.0, er / (max(self._rr_weights) or 1.0)))\n"
    cls += "            return {\n"
    cls += "                'score':       round(sc, 4),\n"
    cls += "                'p_win':       round(p[2] + p[3], 4),\n"
    cls += "                'p_loss':      round(p[0], 4),\n"
    cls += "                'p_weak':      round(p[1], 4),\n"
    cls += "                'p_mid':       round(p[2], 4),\n"
    cls += "                'p_strong':    round(p[3], 4),\n"
    cls += "                'expected_rr': round(er, 4),\n"
    cls += "            }\n"
    cls += "        except Exception:\n"
    cls += "            return None\n"
    cls += "\n"

    scorer_block = hdr + cls

    bt_path = Path(base) / "backtest_v2.py"
    if not bt_path.exists():
        log.error(f"backtest_v2.py not found at {bt_path}")
        return False

    src = bt_path.read_text(encoding="utf-8")

    if SCORER_BLOCK_MARKER in src:
        blk_start = src.rfind("\n\n# ---", 0, src.index(SCORER_BLOCK_MARKER))
        if blk_start == -1:
            blk_start = src.index(SCORER_BLOCK_MARKER) - 4
        cls_start = src.find(f"\nclass {SCORER_CLASS_NAME}", blk_start)
        cls_end   = src.find("\n\nclass ", cls_start + 1)
        if cls_end == -1:
            cls_end = len(src)
        src = src[:blk_start] + src[cls_end:]
        log.info("Removed previous CRTCalibratedScorer block")

    insert_at = src.find(f"\n{SCORER_INSERT_MARKER}")
    if insert_at == -1:
        log.error(f"'{{SCORER_INSERT_MARKER}}' not found in backtest_v2.py")
        return False

    bt_path.write_text(src[:insert_at] + scorer_block + src[insert_at:], encoding="utf-8")
    log.info(f"CRTCalibratedScorer injected (schema={SCHEMA_VERSION} corr={corr_str})")
    print(f"\n  CRTCalibratedScorer injected into backtest_v2.py")
    print(f"  Activate: replace CRTGaussianScorer() with CRTCalibratedScorer()")
    print(f"  in BacktestRunner.__init__")
    return True


def main() -> None:
    ap = argparse.ArgumentParser(
        description="CRT Phase-5 Recalibration v5 -- unified Gaussian + TradeNet validator"
    )
    src = ap.add_mutually_exclusive_group(required=False)
    src.add_argument("--csv",       metavar="DIR",  nargs="?", const=".",
                     help="Base dir with results subdirs (default mode; value unused — "
                          "use --results-dirs to control which dirs are scanned)")
    src.add_argument("--cached",    metavar="JSON", help="Cached phase5_dataset.json path")
    src.add_argument("--synthetic", action="store_true",
                     help="Generate synthetic data for CI/smoke tests (no real data needed)")
    src.add_argument("--opportunities", metavar="JSONL",
                     help="Pipeline-B unbiased opportunity log produced by "
                          "scripts/research/opportunity_scanner.py")

    ap.add_argument("--n-synthetic",   type=int,   default=500,
                    help="Number of synthetic samples to generate (default: 500)")
    ap.add_argument("--synthetic-seed", type=int,  default=42,
                    help="Random seed for synthetic data (default: 42)")
    ap.add_argument("--audit-only",    action="store_true")
    ap.add_argument("--train",         action="store_true")
    ap.add_argument("--gaussian",      action="store_true",
                    help="Train Gaussian NB model (use with --train; "
                         "mutually exclusive with --tradenet).")
    ap.add_argument("--tradenet",      action="store_true",
                    help="Train TradeNet binary classifier (use with --train; "
                         "mutually exclusive with --gaussian). "
                         "Runs standalone — does not require a prior --gaussian run "
                         "in the same session.")
    ap.add_argument("--integrate",     action="store_true",
                    help="DEPRECATED — models now load dynamically via "
                         "core.model_registry. Flag is accepted for backwards "
                         "compatibility but emits a warning and does nothing.")
    ap.add_argument("--promote",       action="store_true")
    ap.add_argument("--export",        action="store_true")
    ap.add_argument("--loo",           action="store_true")
    ap.add_argument("--force",         action="store_true")
    ap.add_argument("--base",          default=".")
    ap.add_argument("--train-ratio",   type=float, default=0.70)
    ap.add_argument("--version",       default="")
    ap.add_argument("--results-dirs",  nargs="+", default=DEFAULT_RESULTS_DIRS)
    ap.add_argument("--feature-subset", default="",
                    help="Comma-separated CANONICAL_FEATURE names to keep "
                         "(others zeroed). Used by LLM hypertuning loop.")
    ap.add_argument("--class-weights", default="",
                    help="Comma-separated priors override (length must match "
                         "n_classes). Used by LLM hypertuning loop.")
    ap.add_argument("--rr-buckets", default="",
                    help="Comma-separated rr upper-bound edges defining outcome "
                         "classes (default: 0.0,1.0,2.0). Used by LLM hypertuning loop.")
    ap.add_argument("--mirror-short-features", action="store_true", default=True,
                    help="When loading --opportunities, negate/swap directional features "
                         "on short records so all samples are in long perspective. "
                         "Prevents signal cancellation when both long+short are present.")
    ap.add_argument("--no-mirror-short-features", dest="mirror_short_features",
                    action="store_false",
                    help="Disable short-feature mirroring (use for direction-filtered logs).")
    ap.add_argument("--instrument", default="",
                    help="Instrument label (e.g. EURUSD, BTCUSDT). When provided, "
                         "the calibration report is written to "
                         "results/{instrument}/{run_id}/p5_calibration_{version}.json "
                         "and the gaussian registry entry gains 'instrument' and 'run_id' fields.")
    ap.add_argument("--run-id", "--run", dest="run_id", default=None,
                    help="Run ID for path scoping (e.g. 20260519_113806). "
                         "When given with --instrument and no --opportunities, "
                         "auto-resolves logs/{instrument}/{run_id}/opportunities.jsonl. "
                         "Default: read from JSONL run_header; auto-generate YYYYMMDD_HHMMSS if absent.")
    args = ap.parse_args()

    # ── Auto-resolve --opportunities from --instrument + --run-id ────────────
    if not args.opportunities and not args.synthetic and not args.cached and args.csv is None:
        if args.instrument and args.run_id:
            auto_path = Path("logs") / args.instrument / args.run_id / "opportunities.jsonl"
            if not auto_path.exists():
                print(f"ERROR: auto-resolved opportunities not found: {auto_path}",
                      file=sys.stderr)
                sys.exit(1)
            args.opportunities = str(auto_path)
            print(f"Auto-resolved opportunities: {auto_path}")

    # Default to csv mode when no source flag is given (--results-dirs already set)
    if not args.synthetic and not args.cached and not args.opportunities and args.csv is None:
        args.csv = "."   # value unused; triggers csv loading branch

    # --synthetic / --opportunities imply --train by default
    _train_explicit = args.train   # True when user passed --train explicitly
    if (args.synthetic or args.opportunities) and not args.audit_only:
        args.train = True
        # Auto-select Gaussian ONLY when --train was not explicit (implied mode).
        # When --train is explicit the user MUST specify --gaussian or --tradenet.
        if not _train_explicit and not args.gaussian and not args.tradenet:
            args.gaussian = True

    # ── Enforce --train requires exactly one of --gaussian / --tradenet ──────
    if args.train:
        if args.gaussian and args.tradenet:
            print(
                "ERROR: --gaussian and --tradenet are mutually exclusive.\n"
                "  Train Gaussian only:  ... --train --gaussian\n"
                "  Train TradeNet only:  ... --train --tradenet",
                file=sys.stderr,
            )
            sys.exit(1)
        if not args.gaussian and not args.tradenet:
            print(
                "ERROR: --train requires exactly one model flag.\n"
                "  Train Gaussian only:  ... --train --gaussian\n"
                "  Train TradeNet only:  ... --train --tradenet",
                file=sys.stderr,
            )
            sys.exit(1)

    if not (args.audit_only or args.train):
        args.audit_only = True

    # ── Resolve LLM-tunable hyperparameters ───────────────────────────────────
    feature_keep_idx: list[int] = []
    if args.feature_subset:
        try:
            feature_keep_idx = _resolve_subset_indices(_parse_str_csv(args.feature_subset))
            log.info("Feature subset active: %d/%d features kept",
                     len(feature_keep_idx), GAUSSIAN_SCHEMA.n_features)
        except ValueError as e:
            print(f"\n{e}")
            sys.exit(1)

    class_weights: list[float] = []
    if args.class_weights:
        class_weights = _parse_float_csv(args.class_weights)

    rr_buckets: list[float] = list(RR_BUCKET_DEFAULTS)
    if args.rr_buckets:
        rr_buckets = sorted(_parse_float_csv(args.rr_buckets))
        log.info("Custom rr buckets: %s", rr_buckets)
        # Override module-level rr_to_class so run_calibration's LOO-CV
        # class assignment honours the LLM-supplied buckets.
        globals()["rr_to_class"] = _make_rr_to_class(rr_buckets)

    # ── Upfront input validation ─────────────────────────────────────────────
    if args.opportunities:
        opp_path = Path(args.opportunities)
        if not opp_path.exists():
            print(f"\nERROR: --opportunities file not found: {opp_path}", file=sys.stderr)
            sys.exit(1)
        if opp_path.stat().st_size == 0:
            print(f"\nERROR: --opportunities file is empty: {opp_path}", file=sys.stderr)
            sys.exit(1)
    if args.cached:
        cached_path = Path(args.cached)
        if not cached_path.exists():
            print(f"\nERROR: --cached file not found: {cached_path}", file=sys.stderr)
            sys.exit(1)

    # ── Resolve run_id (inherited from JSONL run_header, or auto-generated) ───
    _run_id: str = args.run_id or ""
    if not _run_id and args.opportunities:
        try:
            with Path(args.opportunities).open("r", encoding="utf-8") as _fh:
                _hdr = json.loads(_fh.readline().strip())
            if _hdr.get("type") == "run_header":
                _run_id = _hdr.get("run_id", "")
        except Exception:
            pass
    if not _run_id:
        _run_id = time.strftime("%Y%m%d_%H%M%S")
    log.info("run_id: %s", _run_id)

    # ── Load / generate dataset ───────────────────────────────────────────────
    print("\nLoading phase5 dataset...")
    try:
        if args.synthetic:
            print(f"  [SYNTHETIC MODE] Generating {args.n_synthetic} synthetic samples "
                  f"(seed={args.synthetic_seed})")
            dataset = generate_synthetic_dataset(
                n_samples=args.n_synthetic,
                seed=args.synthetic_seed,
            )
        elif args.opportunities:
            dataset = TradeDataset.from_opportunities(
                args.opportunities,
                mirror_short=args.mirror_short_features,
            )
        elif args.cached:
            dataset = TradeDataset.load_cached(args.cached)
        else:
            dataset = TradeDataset.from_backtest_results(
                args.results_dirs, base=args.base
            )
    except (FileNotFoundError, ValueError) as e:
        print(f"\n{e}")
        sys.exit(1)

    # Apply LLM-suggested feature subset mask (zero unselected dims)
    if feature_keep_idx:
        dataset.X = _apply_feature_mask(dataset.X, feature_keep_idx)

    print(f"  {len(dataset.X)} samples from {dataset.n_instruments} instruments "
          f"(source={dataset.source})\n")

    if args.export and not args.synthetic:
        dataset.export(Path(args.base) / "models" / "phase5_dataset.json")

    audit_report(dataset)

    if args.audit_only:
        return

    # ── Gaussian training ─────────────────────────────────────────────────────
    if args.train and args.gaussian:
        version = args.version or f"p5_{time.strftime('%Y%m%dT%H%M%S')}"
        try:
            result = run_calibration(
                dataset, train_ratio=args.train_ratio,
                run_loo=args.loo, version=version,
            )
        except Exception as e:
            print(f"\nCalibration failed: {e}")
            import traceback; traceback.print_exc()
            sys.exit(1)

        # Apply LLM-suggested class priors override (post-training, pre-save)
        if class_weights:
            try:
                total = sum(class_weights)
                if total <= 0:
                    raise ValueError("class_weights must sum to >0")
                normalised = [w / total for w in class_weights]
                if hasattr(result.model, "class_priors") and \
                        len(normalised) == len(result.model.class_priors):
                    log.info(
                        "Overriding class priors %s -> %s",
                        result.model.class_priors, normalised,
                    )
                    result.model.class_priors = normalised
                else:
                    log.warning(
                        "class-weights length %d does not match model "
                        "(class_priors=%s); ignoring.",
                        len(normalised),
                        getattr(result.model, "class_priors", "n/a"),
                    )
            except Exception as exc:
                log.warning("class-weights override failed: %s", exc)

        result.print_summary()

        # Save model
        model_path: Optional[Path] = None
        if result.eval_result.corr_expected_rr >= MIN_LOO_CORR_TO_SAVE or args.force:
            if args.instrument:
                model_file = f"{args.instrument}/{_run_id}/gaussian_{version}.json"
            else:
                model_file = f"gaussian_{version}.json"
            model_path = save_gaussian_model(
                result.model, result.scaler,
                metrics=result.train_metrics,
                name=model_file,
                feature_schema=list(GAUSSIAN_SCHEMA.feature_names),
            )
            result.model_path = model_path
            print(f"  Model saved -> {model_path}")
            print(f"OUTPUT:gaussian:{Path(model_path).resolve()}")

            # ── Post-training Gaussian verification ────────────────────────────
            n_total  = len(dataset.X)
            n_train  = int(n_total * args.train_ratio)
            test_X   = dataset.X[n_train:]   if n_train < n_total else dataset.X[:20]
            test_rr  = dataset.y_rr[n_train:] if n_train < n_total else dataset.y_rr[:20]

            gaussian_ok = verify_gaussian_model(model_path, test_X, test_rr)
            _pass_fail("Gaussian end-to-end pipeline", gaussian_ok)
        else:
            print(f"  Model NOT saved (corr={result.eval_result.corr_expected_rr:+.4f} "
                  f"< threshold {MIN_LOO_CORR_TO_SAVE}). Use --force to override.")

        # Save calibration report — run-scoped when --instrument is provided
        if args.instrument:
            report_path = (Path(args.base) / "results"
                           / args.instrument / _run_id / f"p5_calibration_{version}.json")
        else:
            report_path = Path(args.base) / "results" / f"p5_calibration_{version}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps({
            "version": version, "schema_version": SCHEMA_VERSION,
            "n_features": GAUSSIAN_SCHEMA.n_features,
            "n_samples": result.n_samples, "instruments": result.instruments,
            "train_metrics": result.train_metrics, "cv_metrics": result.cv_metrics,
            "eval": {
                "corr_expected_rr":   result.eval_result.corr_expected_rr,
                "calibration_error":  result.eval_result.calibration_error,
                "mean_expected_rr":   result.eval_result.mean_expected_rr,
                "mean_actual_rr":     result.eval_result.mean_actual_rr,
                "class_distribution": result.eval_result.class_distribution,
            },
            "loo_metrics": result.loo_metrics,
            "integration_approved": result.integration_approved,
            "verdict": result.verdict,
            "source": dataset.source,
        }, indent=2))
        print(f"  Report saved -> {report_path}")
        print(f"OUTPUT:report:{report_path.resolve()}")

        # ── GAP-1: Auto-register in gaussian_registry.json ──────────────────
        # register_gaussian() is idempotent when version already exists.
        # Fail-open: a registration error must never block --promote.
        if model_path is not None:
            try:
                _reg_metrics = {
                    "corr_expected_rr":  result.eval_result.corr_expected_rr,
                    "calibration_error": result.eval_result.calibration_error,
                    "mean_expected_rr":  result.eval_result.mean_expected_rr,
                    "mean_actual_rr":    result.eval_result.mean_actual_rr,
                    "n_train":           result.n_samples,
                }
                register_gaussian(
                    version,
                    str(model_path),
                    list(GAUSSIAN_SCHEMA.feature_names),
                    _reg_metrics,
                    instrument=args.instrument or None,
                    run_id=_run_id or None,
                )
                log.info("GAP-1: Model auto-registered in gaussian_registry: %s", version)
                print(f"  Model registered  -> gaussian_registry.json [{version}]")

                # Gap-4 fix: auto-promote when no active Gaussian exists
                # (mirrors the TradeNet auto-promote pattern in trainer.save_model)
                try:
                    _promo_instrument = (args.instrument or "EURUSD")
                    if get_active_gaussian() is None:
                        promoted, reason = promote_gaussian(
                            version, instrument=_promo_instrument
                        )
                        log.info("Gaussian auto-promoted (no prior active version): %s", reason)
                        print(f"  Auto-promoted     -> {reason}")
                except Exception as _auto_err:
                    log.warning("Gaussian auto-promotion check failed (non-fatal): %s", _auto_err)

            except Exception as _reg_err:
                log.warning(
                    "GAP-1: register_gaussian() failed (non-fatal, promote separately): %s",
                    _reg_err,
                )

        if args.integrate:
            log.warning(
                "--integrate is DEPRECATED. Models load dynamically via "
                "core.model_registry.load_active_gaussian_scorer(). "
                "Use --promote to set the active version, or call "
                "promote_gaussian() manually. Skipping source-file injection."
            )

        if args.promote and result.model_path:
            if result.integration_approved or args.force:
                promoted, reason = promote_gaussian(version)
                status = "promoted" if promoted else "blocked"
                print(f"\n  Promotion {status}: {reason}")
            else:
                print("\n  Promotion skipped (integration_approved=False). Use --force.")

    # ── TradeNet training ─────────────────────────────────────────────────────
    if args.train and args.tradenet:
        version = args.version or f"p5_{time.strftime('%Y%m%dT%H%M%S')}"
        # Gap-3 fix: unpack (path, metrics) tuple returned by run_tradenet_training
        tn_path, tn_metrics = run_tradenet_training(
            dataset,
            version=version,
            train_ratio=args.train_ratio,
            instrument=args.instrument or "",
            run_id=_run_id,
        )
        if tn_path:
            _pass_fail("TradeNet end-to-end pipeline", True, str(tn_path))
            # Resolve report_path for standalone TradeNet run.
            # When Gaussian was trained in a prior command the report already exists;
            # when it wasn't, patching is skipped gracefully (fail-open).
            if args.instrument:
                _tn_report = (Path(args.base) / "results"
                              / args.instrument / _run_id / f"p5_calibration_{version}.json")
            else:
                _tn_report = (Path(args.base) / "results"
                              / f"p5_calibration_{version}.json")
            try:
                rdata = json.loads(_tn_report.read_text())
                rdata["tradenet"] = {
                    "model_path": str(tn_path),
                    "version":    version,
                    "status":     "trained",
                    "metrics":    tn_metrics,
                }
                _tn_report.write_text(json.dumps(rdata, indent=2))
                print(f"  Report updated with TradeNet section -> {_tn_report}")
            except Exception as _patch_err:
                log.warning("Could not patch report with TradeNet section: %s", _patch_err)
        else:
            _pass_fail("TradeNet end-to-end pipeline", False,
                       "training failed or torch not available")

    # ── Final summary ─────────────────────────────────────────────────────────
    W = 66
    print(f"\n{'=' * W}")
    print(f"  PHASE-5 VALIDATION COMPLETE")
    print(f"  schema={SCHEMA_VERSION}  n_features={GAUSSIAN_SCHEMA.n_features}  "
          f"source={dataset.source}")
    print(f"{'=' * W}\n")


if __name__ == "__main__":
    main()