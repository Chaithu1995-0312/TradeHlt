"""
inout/probability_engine.py
═══════════════════════════════════════════════════════════════════════════════
INOUT Strategy — Probability Engine

Converts trade log data (SQLite) into runtime probability predictions.

Four approaches — all implemented, config-driven selection:
═══════════════════════════════════════════════════════════════════════════════

APPROACH A — Statistical Bucket Engine
    Buckets past trades by feature profile → computes empirical distributions.
    Fast. Deterministic. Zero ML overhead.
    Best for: early stage (<500 trades), full explainability required.

APPROACH B — Feature + ML Model Engine  (Balanced — DEFAULT)
    GradientBoosting classifier (TP1/TP2 probability) +
    GradientBoosting regressor (time to TP1/TP2).
    Good performance at 200+ trades. Interpretable feature importance.
    Best for: production use, moderate data volume.

APPROACH C — Sequence Model Engine  (Advanced — Extension Point)
    Reads candle sequences from signal_meta. Stub for Phase 2+.
    Extension point: replace _predict_sequence() with LSTM / Transformer / BitNet.
    Best for: 2000+ trades, full candle history stored.

APPROACH D — Hybrid Engine  (BEST — default above threshold)
    Statistical base (Approach A) + ML correction (Approach B).
    Falls back to A if too few trades for B.
    Adaptive: auto-promotes to D once N_TRAIN_THRESHOLD is met.

═══════════════════════════════════════════════════════════════════════════════

Runtime output (all approaches return same schema):
    {
        "approach":           str,         # which engine produced this
        "tp1_prob":           float,       # P(TP1 hit) in [0,1]
        "tp2_prob":           float,       # P(TP2 hit) in [0,1]
        "runner_prob":        float,       # P(runner trail hit) in [0,1]
        "expected_time_tp1":  float,       # E[minutes to TP1]
        "expected_time_tp2":  float,       # E[minutes to TP2]
        "expected_rr":        float,       # E[RR across all outcomes]
        "confidence":         float,       # model confidence in [0,1]
        "n_samples":          int,         # training/bucket sample count
        "warnings":           list[str],   # e.g. ["low_sample_count"]
    }

Integration with scanner:
    prob = engine.predict(signal_features)
    if prob["tp2_prob"] >= cfg.prob("tp2_min_prob", 0.45):
        signal is accepted

Architecture boundaries:
    - Does NOT import EngineRunner, FusionEngine, or any core/ module
    - Does NOT modify inout_trades or inout_exits tables (read-only)
    - All model artifacts saved to data/inout_prob_models/
    - Config section: "inout.probability" in production config

Extension points:
    Phase 2 — Approach C: replace _predict_sequence() with real sequence model
    Phase 3 — inject Gemini context into Approach D hybrid scorer
    Phase 3 — replace _bucket_key() with learned embeddings from BitNet
"""

from __future__ import annotations

import csv
import json
import logging
import math
import os
import pickle
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

import numpy as np

logger = logging.getLogger("INOUT.PROB_ENGINE")

# ── Constants ─────────────────────────────────────────────────────────────────

# Minimum trades needed before activating ML models
_N_TRAIN_THRESHOLD = 50    # minimum for Approach B
_N_STAT_THRESHOLD  = 10    # minimum for Approach A buckets (falls back to prior)

# Feature names used for ML (must match DataExtractor output)
_FEATURE_COLS = [
    "atr", "volume_ratio", "candle_expansion",
    "structure_broken", "direction_encoded",
    "signal_score", "rr_ratio",
]

# Targets
_CLASS_TARGETS = ["tp1_hit", "tp2_hit", "runner_hit"]
_REGR_TARGETS  = ["time_to_tp1_min", "time_to_tp2_min", "total_duration_min"]

# Prior (used when data is insufficient)
_PRIOR = {
    "tp1_prob": 0.45,
    "tp2_prob": 0.30,
    "runner_prob": 0.15,
    "expected_time_tp1": 5.0,
    "expected_time_tp2": 9.0,
    "expected_rr": 0.5,
    "confidence": 0.1,
}


# ═════════════════════════════════════════════════════════════════════════════
# DATA EXTRACTOR
# ═════════════════════════════════════════════════════════════════════════════

class INOUTDataExtractor:
    """
    Reads inout_trades + inout_exits from SQLite and produces
    a flat per-trade dataset ready for training or analysis.

    Never writes to the DB. Read-only access.

    Dataset columns:
        trade_id, symbol, direction, direction_encoded,
        atr, volume_ratio, candle_expansion, structure_broken, signal_score,
        rr_ratio, created_at, closed_at,
        tp1_hit, tp2_hit, runner_hit, stopped, timeout,
        time_to_tp1_min, time_to_tp2_min, total_duration_min,
        pnl_rr
    """

    def __init__(self, db_path: str) -> None:
        self._path = Path(db_path)

    def extract(self) -> list[dict[str, Any]]:
        """
        Extract and join all closed trades into flat dataset.
        Returns list of dicts — one per closed trade.

        Only includes trades in terminal states:
        CLOSED | TIMEOUT | FAILED (PENDING/ACTIVE excluded — incomplete)
        """
        if not self._path.exists():
            logger.warning("INOUT.EXTRACTOR: DB not found at %s — returning empty", self._path)
            return []

        with self._conn() as conn:
            trades = conn.execute("""
                SELECT * FROM inout_trades
                WHERE state IN ('CLOSED','TIMEOUT','FAILED')
                ORDER BY created_at
            """).fetchall()

            exits = conn.execute("""
                SELECT * FROM inout_exits ORDER BY exited_at
            """).fetchall()

        if not trades:
            logger.info("INOUT.EXTRACTOR: no completed trades found")
            return []

        # Build exit index: trade_id → list of exits
        exit_index: dict[str, list[dict]] = {}
        for ex in exits:
            row = dict(ex)
            tid = row["trade_id"]
            exit_index.setdefault(tid, []).append(row)

        records = []
        for trade in trades:
            trade_dict = dict(trade)
            trade_exits = exit_index.get(trade_dict["trade_id"], [])
            record = self._build_record(trade_dict, trade_exits)
            if record:
                records.append(record)

        logger.info("INOUT.EXTRACTOR: extracted %d records from %d trades", len(records), len(trades))
        return records

    def to_csv(self, output_path: str) -> int:
        """Extract and save to CSV. Returns row count."""
        records = self.extract()
        if not records:
            return 0
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
            writer.writeheader()
            writer.writerows(records)
        logger.info("INOUT.EXTRACTOR: saved %d rows to %s", len(records), output_path)
        return len(records)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _build_record(
        self,
        trade: dict[str, Any],
        exits: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Build a flat feature+label record from one trade + its exits."""
        try:
            # ── Entry features from signal_meta ───────────────────────────────
            meta = json.loads(trade.get("signal_meta") or "{}")
            atr            = float(meta.get("atr", trade.get("stop_loss", 0) or 0))
            volume_ratio   = float(meta.get("volume_ratio", 1.0))
            candle_exp     = float(meta.get("candle_expansion", 0.0))
            struct_broken  = int(bool(meta.get("structure_broken", False)))
            direction      = str(trade.get("direction", "LONG"))
            dir_encoded    = 1 if direction == "LONG" else -1
            signal_score   = float(trade.get("signal_score") or meta.get("composite_score", 0.5))
            rr_ratio       = float(trade.get("rr_ratio") or 2.0)

            # ── Outcome labels from exits ──────────────────────────────────────
            exit_reasons = {ex["exit_reason"]: ex for ex in exits}
            tp1_hit    = int("TP1" in exit_reasons)
            tp2_hit    = int("TP2" in exit_reasons)
            runner_hit = int("RUNNER_TRAIL" in exit_reasons)
            stopped    = int("SL" in exit_reasons or "BE_SL" in exit_reasons)
            timed_out  = int("SOFT_TIME_STOP" in exit_reasons or "MAX_TIME_STOP" in exit_reasons)

            # ── Time features ─────────────────────────────────────────────────
            created_at = _parse_iso(trade.get("created_at"))
            closed_at  = _parse_iso(trade.get("closed_at"))
            total_min  = _elapsed_minutes(created_at, closed_at) if created_at and closed_at else None

            def _time_to_tier(reason: str) -> float | None:
                if reason not in exit_reasons:
                    return None
                exit_at = _parse_iso(exit_reasons[reason]["exited_at"])
                if created_at and exit_at:
                    return _elapsed_minutes(created_at, exit_at)
                return None

            t_tp1    = _time_to_tier("TP1")
            t_tp2    = _time_to_tier("TP2")

            # ── P&L ───────────────────────────────────────────────────────────
            pnl_rr = float(trade.get("total_pnl_rr") or 0.0)
            if pnl_rr == 0.0 and exits:
                # Sum partial pnl_rr weighted by fraction
                pnl_rr = sum(
                    float(ex.get("pnl_rr") or 0) * float(ex.get("fraction") or 0)
                    for ex in exits
                )

            return {
                "trade_id":           trade["trade_id"],
                "symbol":             trade.get("symbol", "UNKNOWN"),
                "direction":          direction,
                "direction_encoded":  dir_encoded,
                "atr":                atr,
                "volume_ratio":       volume_ratio,
                "candle_expansion":   candle_exp,
                "structure_broken":   struct_broken,
                "signal_score":       signal_score,
                "rr_ratio":           rr_ratio,
                "state":              trade.get("state", "UNKNOWN"),
                "created_at":         trade.get("created_at"),
                "closed_at":          trade.get("closed_at"),
                # Labels
                "tp1_hit":            tp1_hit,
                "tp2_hit":            tp2_hit,
                "runner_hit":         runner_hit,
                "stopped":            stopped,
                "timeout":            timed_out,
                # Timings (None if not reached)
                "time_to_tp1_min":    t_tp1,
                "time_to_tp2_min":    t_tp2,
                "total_duration_min": total_min,
                "pnl_rr":             round(pnl_rr, 4),
            }
        except Exception as exc:
            logger.warning(
                "INOUT.EXTRACTOR: failed to build record for trade %s: %s",
                trade.get("trade_id"), exc,
            )
            return None

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self._path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


# ═════════════════════════════════════════════════════════════════════════════
# APPROACH A — STATISTICAL BUCKET ENGINE
# ═════════════════════════════════════════════════════════════════════════════

class _ApproachA_Statistical:
    """
    Approach A — Statistical Bucket Engine

    Groups past trades by a composite bucket key (discrete bins of
    volume_ratio, candle_expansion, and direction) then computes
    empirical success rates and time distributions within each bucket.

    No ML. Fully deterministic and explainable.
    Falls back to global prior when bucket has < min_bucket_n samples.
    """

    def __init__(self, min_bucket_n: int = 5) -> None:
        self._min_n = min_bucket_n
        self._global: dict[str, Any] = {}     # global stats across all trades
        self._buckets: dict[str, dict] = {}   # bucket_key → stats
        self._n_total = 0

    def fit(self, records: list[dict[str, Any]]) -> None:
        """Compute bucket statistics from extracted records."""
        if not records:
            return

        self._n_total = len(records)

        # ── Global stats ──────────────────────────────────────────────────────
        self._global = _compute_stats(records)

        # ── Per-bucket stats ──────────────────────────────────────────────────
        buckets: dict[str, list] = {}
        for r in records:
            key = self._bucket_key(r)
            buckets.setdefault(key, []).append(r)

        self._buckets = {
            key: _compute_stats(recs)
            for key, recs in buckets.items()
            if len(recs) >= self._min_n
        }
        logger.info(
            "INOUT.PROB_A: fitted %d total trades, %d buckets",
            self._n_total, len(self._buckets),
        )

    def predict(self, features: dict[str, Any]) -> dict[str, Any]:
        """Return probability dict for given features."""
        key = self._bucket_key(features)
        stats = self._buckets.get(key, self._global)

        if not stats:
            return {**_PRIOR, "approach": "A_prior", "n_samples": 0,
                    "warnings": ["no_data_fallback_to_prior"]}

        warnings = []
        n = stats.get("n", 0)
        if n < self._min_n:
            warnings.append(f"low_bucket_n:{n}")

        return {
            "approach":           "A_statistical",
            "tp1_prob":           float(stats.get("tp1_rate", _PRIOR["tp1_prob"])),
            "tp2_prob":           float(stats.get("tp2_rate", _PRIOR["tp2_prob"])),
            "runner_prob":        float(stats.get("runner_rate", _PRIOR["runner_prob"])),
            "expected_time_tp1":  float(stats.get("mean_time_tp1", _PRIOR["expected_time_tp1"])),
            "expected_time_tp2":  float(stats.get("mean_time_tp2", _PRIOR["expected_time_tp2"])),
            "expected_rr":        float(stats.get("mean_rr", _PRIOR["expected_rr"])),
            "confidence":         min(1.0, n / 100.0),
            "n_samples":          n,
            "warnings":           warnings,
        }

    def _bucket_key(self, r: dict[str, Any]) -> str:
        """
        Discretize continuous features into bucket bins.

        Extension point: Phase 3 — replace bins with learned embeddings from BitNet
        """
        vol  = _bin(float(r.get("volume_ratio", 1.0)),  [1.0, 2.0, 3.5, 6.0])
        exp  = _bin(float(r.get("candle_expansion", 0)), [1.5, 2.5, 4.0, 7.0])
        sc   = _bin(float(r.get("signal_score", 0.5)),   [0.5, 0.6, 0.75, 0.9])
        d    = "L" if int(r.get("direction_encoded", 1)) > 0 else "S"
        return f"{d}|v{vol}|e{exp}|s{sc}"


# ═════════════════════════════════════════════════════════════════════════════
# APPROACH B — ML MODEL ENGINE
# ═════════════════════════════════════════════════════════════════════════════

class _ApproachB_ML:
    """
    Approach B — Feature + ML Model Engine

    Trains scikit-learn GradientBoosting models:
        - 3 classifiers: P(tp1_hit), P(tp2_hit), P(runner_hit)
        - 3 regressors:  E[time_to_tp1], E[time_to_tp2], E[total_duration]

    Calibrated with Platt scaling for reliable probability outputs.
    Feature importance available for interpretability.
    """

    def __init__(self, model_dir: str = "data/inout_prob_models") -> None:
        self._model_dir = Path(model_dir)
        self._classifiers: dict[str, Any] = {}
        self._regressors: dict[str, Any] = {}
        self._n_train = 0
        self._feature_importance: dict[str, list] = {}
        self._fitted = False

    def fit(self, records: list[dict[str, Any]]) -> None:
        if len(records) < _N_TRAIN_THRESHOLD:
            logger.warning(
                "INOUT.PROB_B: only %d records — need %d for ML training. Skipped.",
                len(records), _N_TRAIN_THRESHOLD,
            )
            return

        from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
        from sklearn.calibration import CalibratedClassifierCV

        X, y_class, y_regr = _build_matrices(records)
        self._n_train = len(X)

        # ── Classification models (TP1, TP2, runner) ──────────────────────────
        for target in _CLASS_TARGETS:
            y = y_class[target]
            if y.sum() < 5 or (len(y) - y.sum()) < 5:
                logger.warning("INOUT.PROB_B: skipping %s — too few positive/negative examples", target)
                continue
            base = GradientBoostingClassifier(
                n_estimators=100, max_depth=3, learning_rate=0.05,
                subsample=0.8, random_state=42,
            )
            # Calibrated for reliable probabilities
            clf = CalibratedClassifierCV(base, cv=min(5, max(2, len(X)//20)), method="sigmoid")
            clf.fit(X, y)
            self._classifiers[target] = clf
            logger.info("INOUT.PROB_B: trained classifier for %s n=%d", target, self._n_train)

        # ── Regression models — use per-target aligned X subset ───────────────
        # y_regr values are (row_index, value) pairs; X must be subset-aligned
        for target, pairs in y_regr.items():
            if len(pairs) < _N_TRAIN_THRESHOLD // 2:
                continue
            idxs = np.array([p[0] for p in pairs], dtype=np.int32)
            vals = np.array([p[1] for p in pairs], dtype=np.float32)
            X_sub = X[idxs]
            reg = GradientBoostingRegressor(
                n_estimators=100, max_depth=3, learning_rate=0.05,
                subsample=0.8, random_state=42,
            )
            reg.fit(X_sub, vals)
            self._regressors[target] = reg
            logger.info("INOUT.PROB_B: trained regressor for %s n=%d", target, len(vals))

        self._fitted = True

    def predict(self, features: dict[str, Any]) -> dict[str, Any]:
        if not self._fitted:
            return {**_PRIOR, "approach": "B_not_fitted", "n_samples": 0,
                    "warnings": ["model_not_fitted_fallback_to_prior"]}

        x = _features_to_array(features)
        result: dict[str, Any] = {"approach": "B_ml", "n_samples": self._n_train, "warnings": []}

        # Classification probabilities
        for target, clf in self._classifiers.items():
            try:
                prob = float(clf.predict_proba(x)[0][1])
            except Exception:
                prob = _PRIOR.get(target.replace("_hit", "_prob"), 0.3)
                result["warnings"].append(f"clf_error:{target}")
            result[target.replace("_hit", "_prob")] = prob

        # Fill missing probs with prior
        for k, v in [("tp1_prob", _PRIOR["tp1_prob"]),
                     ("tp2_prob", _PRIOR["tp2_prob"]),
                     ("runner_prob", _PRIOR["runner_prob"])]:
            result.setdefault(k, v)

        # Regression predictions
        def _regr(target: str, prior: float) -> float:
            reg = self._regressors.get(target)
            if reg is None:
                return prior
            try:
                val = float(reg.predict(x)[0])
                return max(0.0, val)
            except Exception:
                result["warnings"].append(f"reg_error:{target}")
                return prior

        result["expected_time_tp1"] = _regr("time_to_tp1_min", _PRIOR["expected_time_tp1"])
        result["expected_time_tp2"] = _regr("time_to_tp2_min", _PRIOR["expected_time_tp2"])

        # Expected RR
        tp1_p = result["tp1_prob"]
        tp2_p = result["tp2_prob"]
        run_p = result["runner_prob"]
        tp1_rr = 1.0
        tp2_rr = 2.0
        run_rr = 2.5
        sl_loss = -1.0
        win_p = max(tp1_p, tp2_p)
        result["expected_rr"] = round(
            tp2_p * tp2_rr + run_p * run_rr + (1 - win_p) * sl_loss, 4
        )

        result["confidence"] = min(1.0, self._n_train / 500.0)
        return result

    def save(self) -> None:
        """Serialize models to disk."""
        self._model_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "classifiers": self._classifiers,
            "regressors": self._regressors,
            "n_train": self._n_train,
        }
        path = self._model_dir / "approach_b.pkl"
        with open(path, "wb") as f:
            pickle.dump(payload, f)
        logger.info("INOUT.PROB_B: models saved to %s", path)

    def load(self) -> bool:
        """Deserialize from disk. Returns True if successful."""
        path = self._model_dir / "approach_b.pkl"
        if not path.exists():
            return False
        try:
            with open(path, "rb") as f:
                payload = pickle.load(f)
            self._classifiers = payload.get("classifiers", {})
            self._regressors  = payload.get("regressors", {})
            self._n_train     = payload.get("n_train", 0)
            self._fitted = bool(self._classifiers)
            logger.info("INOUT.PROB_B: loaded models from %s (n_train=%d)", path, self._n_train)
            return self._fitted
        except Exception as exc:
            logger.warning("INOUT.PROB_B: failed to load models: %s", exc)
            return False


# ═════════════════════════════════════════════════════════════════════════════
# APPROACH C — SEQUENCE MODEL ENGINE  (STUB — EXTENSION POINT)
# ═════════════════════════════════════════════════════════════════════════════

class _ApproachC_Sequence:
    """
    Approach C — Sequence Model Engine  (Phase 2+ Extension Point)

    In Phase 1: stub that returns prior + warning.

    Phase 2 implementation plan:
        1. Store candle sequences in signal_meta (extend INOUTScanner.to_dict())
        2. Build padded sequence tensors from raw_candle history
        3. Train LSTM / Transformer on (sequence → outcome)
        4. Replace _predict_sequence() with torch.inference_mode() call

    Alternatively: feed to local BitNet / Ollama for pattern context.
    """

    def __init__(self) -> None:
        self._fitted = False

    def fit(self, records: list[dict[str, Any]]) -> None:
        """
        Phase 2: train sequence model on candle history from signal_meta.
        Currently a no-op — logs intent.
        """
        sequences_available = sum(
            1 for r in records
            if json.loads(r.get("signal_meta") or "{}").get("raw_candle")
        )
        logger.info(
            "INOUT.PROB_C: STUB — %d/%d records have raw_candle data. "
            "Phase 2: implement LSTM/Transformer here.",
            sequences_available, len(records),
        )
        # Phase 2 implementation:
        # seqs = [self._extract_sequence(r) for r in records if has_seq(r)]
        # model = LSTMClassifier(input_dim=5, hidden_dim=64, output_dim=3)
        # model.fit(seqs, labels)
        # self._model = model
        # self._fitted = True

    def predict(self, features: dict[str, Any]) -> dict[str, Any]:
        """
        Phase 2: run sequence inference.
        Phase 1: returns prior with clear stub warning.

        Extension point: Phase 2 — replace body with:
            sequence = features.get("candle_sequence", [])
            return self._predict_sequence(sequence)
        """
        return {
            **_PRIOR,
            "approach":   "C_stub",
            "n_samples":  0,
            "warnings":   ["approach_C_is_stub_phase2_not_implemented"],
        }

    def _predict_sequence(self, sequence: list[dict]) -> dict[str, Any]:
        """
        Phase 2: real sequence inference.
        Placeholder — raises NotImplementedError until implemented.
        """
        raise NotImplementedError(
            "Phase 2: implement LSTM/Transformer/BitNet sequence inference here"
        )


# ═════════════════════════════════════════════════════════════════════════════
# APPROACH D — HYBRID ENGINE  (DEFAULT)
# ═════════════════════════════════════════════════════════════════════════════

class _ApproachD_Hybrid:
    """
    Approach D — Hybrid Engine (BEST — default above N_TRAIN_THRESHOLD)

    Combines Approach A (statistical base) with Approach B (ML correction).

    Blend logic:
        if n_trades < N_STAT_THRESHOLD:   → prior only
        if n_trades < N_TRAIN_THRESHOLD:  → Approach A only
        else:                             → A × (1 - blend_weight) + B × blend_weight
            where blend_weight grows from 0.0 → 1.0 as n_trades grows

    Approach C can be injected as a third signal when sequence data is available.

    Extension point:
        Phase 3: inject Gemini regime context as a fourth signal:
            gemini_signal = self._gemini_context(features, regime)
            result = _blend(a_result, b_result, gemini_signal)
    """

    def __init__(
        self,
        model_dir: str = "data/inout_prob_models",
        blend_weight: float = 0.6,
    ) -> None:
        self._a = _ApproachA_Statistical()
        self._b = _ApproachB_ML(model_dir=model_dir)
        self._c = _ApproachC_Sequence()
        self._blend_weight = blend_weight   # weight of B in final blend
        self._n_total = 0

    def fit(self, records: list[dict[str, Any]]) -> None:
        self._n_total = len(records)
        self._a.fit(records)
        if self._n_total >= _N_TRAIN_THRESHOLD:
            self._b.fit(records)
        self._c.fit(records)
        logger.info(
            "INOUT.PROB_D: hybrid fitted — n=%d A+B=%s",
            self._n_total,
            "active" if self._n_total >= _N_TRAIN_THRESHOLD else "A_only",
        )

    def predict(self, features: dict[str, Any]) -> dict[str, Any]:
        a_result = self._a.predict(features)

        if self._n_total < _N_STAT_THRESHOLD:
            return {**a_result, "approach": "D_prior_only"}

        if self._n_total < _N_TRAIN_THRESHOLD:
            return {**a_result, "approach": "D_stat_only"}

        b_result = self._b.predict(features)

        # Adaptive blend weight: increases as training set grows
        adaptive_w = min(
            self._blend_weight,
            (self._n_total - _N_TRAIN_THRESHOLD) / 500.0 * self._blend_weight,
        )
        a_w = 1.0 - adaptive_w

        blended = {
            "approach":           "D_hybrid",
            "n_samples":          self._n_total,
            "warnings":           a_result.get("warnings", []) + b_result.get("warnings", []),
            "tp1_prob":           _blend(a_result["tp1_prob"],           b_result["tp1_prob"],           adaptive_w),
            "tp2_prob":           _blend(a_result["tp2_prob"],           b_result["tp2_prob"],           adaptive_w),
            "runner_prob":        _blend(a_result["runner_prob"],        b_result["runner_prob"],        adaptive_w),
            "expected_time_tp1":  _blend(a_result["expected_time_tp1"],  b_result["expected_time_tp1"],  adaptive_w),
            "expected_time_tp2":  _blend(a_result["expected_time_tp2"],  b_result["expected_time_tp2"],  adaptive_w),
            "expected_rr":        _blend(a_result["expected_rr"],        b_result["expected_rr"],        adaptive_w),
            "confidence":         _blend(a_result["confidence"],         b_result["confidence"],         adaptive_w),
            "blend_weight_b":     round(adaptive_w, 4),
        }

        # Phase 3 extension point:
        # if gemini_context_available:
        #     g_result = self._call_gemini(features)
        #     blended = _blend_three(blended, g_result, gemini_weight=0.15)

        return blended

    def save(self) -> None:
        self._b.save()

    def load(self) -> bool:
        return self._b.load()


# ═════════════════════════════════════════════════════════════════════════════
# MAIN PROBABILITY ENGINE (PUBLIC API)
# ═════════════════════════════════════════════════════════════════════════════

class ProbabilityEngine:
    """
    Public interface for the INOUT Probability Engine.

    Selects and manages the appropriate approach based on config and data volume.

    Usage
    -----
        # Training (offline, run after accumulating trades):
        engine = ProbabilityEngine.from_config(cfg)
        n = engine.train(db_path="logs/inout_trades.db")

        # Runtime (called from INOUTScanner.scan()):
        prob = engine.predict(signal.to_dict())
        if prob["tp2_prob"] >= threshold:
            # accept signal

        # Save/load for persistence:
        engine.save()
        engine.load()

    Config section (in production_configs under "inout.probability"):
        approach:          "A" | "B" | "C" | "D"  (default "D")
        min_train_records: int                       (default 50)
        model_dir:         str                       (default "data/inout_prob_models")
        blend_weight:      float                     (default 0.6)
        tp1_min_prob:      float                     (default 0.35)
        tp2_min_prob:      float                     (default 0.30)
        auto_retrain_n:    int                       (retrain every N new trades, default 100)
    """

    def __init__(
        self,
        approach: str = "D",
        model_dir: str = "data/inout_prob_models",
        blend_weight: float = 0.6,
    ) -> None:
        self._approach_name = approach.upper()
        self._engine: Any = self._build_engine(approach, model_dir, blend_weight)
        self._fitted = False
        self._n_trained = 0
        self._dataset_path: str | None = None

    @classmethod
    def from_config(cls, cfg_raw: dict[str, Any]) -> "ProbabilityEngine":
        """
        Instantiate from raw config dict.

        cfg_raw should be the "inout.probability" section:
            {
                "approach": "D",
                "model_dir": "data/inout_prob_models",
                "blend_weight": 0.6
            }
        """
        return cls(
            approach=cfg_raw.get("approach", "D"),
            model_dir=cfg_raw.get("model_dir", "data/inout_prob_models"),
            blend_weight=float(cfg_raw.get("blend_weight", 0.6)),
        )

    # ── Training ──────────────────────────────────────────────────────────────

    def train(
        self,
        db_path: str = "logs/inout_trades.db",
        save_dataset: bool = True,
        dataset_path: str = "data/inout_dataset.csv",
    ) -> int:
        """
        Full training pipeline:
            1. Extract data from SQLite
            2. Save dataset CSV (optional)
            3. Fit the selected approach engine
            4. Mark as fitted

        Returns number of training records used.
        """
        extractor = INOUTDataExtractor(db_path)
        records = extractor.extract()

        if save_dataset and records:
            extractor.to_csv(dataset_path)
            self._dataset_path = dataset_path

        if not records:
            logger.warning("INOUT.PROB: no records to train on")
            return 0

        self._engine.fit(records)
        self._fitted = True
        self._n_trained = len(records)

        logger.info(
            "INOUT.PROB: trained approach=%s on %d records",
            self._approach_name, self._n_trained,
        )
        return self._n_trained

    def train_from_records(self, records: list[dict[str, Any]]) -> int:
        """Train directly from pre-extracted records (for testing)."""
        if not records:
            return 0
        self._engine.fit(records)
        self._fitted = True
        self._n_trained = len(records)
        return self._n_trained

    # ── Prediction ────────────────────────────────────────────────────────────

    def predict(self, features: dict[str, Any]) -> dict[str, Any]:
        """
        Return probability predictions for a signal's features.

        If not yet fitted, returns prior with warning.
        Always returns the canonical output schema.

        Parameters
        ----------
        features : dict — typically INOUTSignal.to_dict() or a subset:
            Required: atr, volume_ratio, candle_expansion, structure_broken,
                      direction_encoded (or direction), signal_score, rr_ratio
        """
        if not self._fitted:
            return {
                **_PRIOR,
                "approach": f"{self._approach_name}_not_fitted",
                "n_samples": 0,
                "warnings": ["engine_not_fitted_returning_prior"],
            }

        # Normalise direction
        feat = dict(features)
        if "direction_encoded" not in feat:
            feat["direction_encoded"] = 1 if feat.get("direction", "LONG") == "LONG" else -1

        result = self._engine.predict(feat)
        return self._clamp_output(result)

    # ── EV helper ─────────────────────────────────────────────────────────────

    def compute_ev(self, prob: dict[str, Any], sl_rr: float = 1.0) -> float:
        """
        Compute Expected Value in RR units.

        EV = P(tp2) × tp2_rr + P(runner) × runner_rr + P(loss) × (-sl_rr)

        Extension point: Phase 2 — use probability engine time distributions
        to weight RR by time-decay probability.
        """
        tp2_p = float(prob.get("tp2_prob", 0))
        run_p = float(prob.get("runner_prob", 0))
        tp1_p = float(prob.get("tp1_prob", 0))
        loss_p = max(0.0, 1.0 - tp1_p)
        ev = tp2_p * 2.0 + run_p * 2.5 + loss_p * (-sl_rr)
        return round(ev, 4)

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self) -> None:
        """Persist model artifacts to disk."""
        if hasattr(self._engine, "save"):
            self._engine.save()
        else:
            logger.info("INOUT.PROB: approach %s has no save() — in-memory only", self._approach_name)

    def load(self) -> bool:
        """Load model artifacts from disk. Returns True if successful."""
        if hasattr(self._engine, "load"):
            ok = self._engine.load()
            if ok:
                self._fitted = True
            return ok
        return False

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    @property
    def n_trained(self) -> int:
        return self._n_trained

    @property
    def approach(self) -> str:
        return self._approach_name

    # ── Internal ──────────────────────────────────────────────────────────────

    def _build_engine(self, approach: str, model_dir: str, blend_weight: float) -> Any:
        approach = approach.upper()
        if approach == "A":
            return _ApproachA_Statistical()
        if approach == "B":
            return _ApproachB_ML(model_dir=model_dir)
        if approach == "C":
            return _ApproachC_Sequence()
        if approach == "D":
            return _ApproachD_Hybrid(model_dir=model_dir, blend_weight=blend_weight)
        logger.warning("INOUT.PROB: unknown approach '%s' — defaulting to D", approach)
        return _ApproachD_Hybrid(model_dir=model_dir, blend_weight=blend_weight)

    @staticmethod
    def _clamp_output(result: dict[str, Any]) -> dict[str, Any]:
        """Clamp all probability values to [0, 1] and times to [0, 60]."""
        for k in ("tp1_prob", "tp2_prob", "runner_prob", "confidence"):
            if k in result:
                result[k] = round(max(0.0, min(1.0, float(result[k]))), 6)
        for k in ("expected_time_tp1", "expected_time_tp2"):
            if k in result:
                result[k] = round(max(0.0, min(60.0, float(result[k]))), 4)
        if "expected_rr" in result:
            result["expected_rr"] = round(float(result["expected_rr"]), 4)
        return result


# ═════════════════════════════════════════════════════════════════════════════
# SCANNER INTEGRATION ADAPTER
# ═════════════════════════════════════════════════════════════════════════════

class INOUTScannerProbAdapter:
    """
    Thin adapter that replaces _compute_composite_score() in INOUTScanner
    with ProbabilityEngine output — WITHOUT modifying scanner.py.

    Usage (in INOUTScanner or runner):
        adapter = INOUTScannerProbAdapter(engine, cfg)

        # Instead of scanner._compute_composite_score():
        score, accepted = adapter.score_signal(signal_features)

    How it works:
        - Calls engine.predict(features)
        - Returns (composite_score, accept_bool)
        - composite_score is now P(tp2) weighted by confidence
        - Falls back to rule-based score if engine not fitted
    """

    def __init__(self, engine: ProbabilityEngine, prob_cfg: dict[str, Any]) -> None:
        self._engine = engine
        self._cfg = prob_cfg

    def score_signal(
        self,
        rule_based_score: float,
        signal_features: dict[str, Any],
    ) -> tuple[float, dict[str, Any]]:
        """
        Compute probability-enhanced score for a signal.

        Parameters
        ----------
        rule_based_score  : float — original composite score from INOUTScanner
        signal_features   : dict — INOUTSignal.to_dict() or equivalent

        Returns
        -------
        (enhanced_score, prob_result)
            enhanced_score: float [0, 1] — probability-weighted signal strength
            prob_result: full probability dict for logging / decision making
        """
        if not self._engine.is_fitted:
            # Engine not ready → use rule-based score unchanged
            return rule_based_score, {**_PRIOR, "approach": "fallback_rule_based"}

        prob = self._engine.predict(signal_features)

        tp2_min  = float(self._cfg.get("tp2_min_prob", 0.30))
        tp1_min  = float(self._cfg.get("tp1_min_prob", 0.35))
        conf_min = float(self._cfg.get("min_confidence", 0.1))

        # Blend rule-based score with probability-based score
        # Weight of probability grows with confidence
        blend_alpha = float(self._cfg.get("prob_blend_alpha", 0.7))
        conf = float(prob.get("confidence", 0.0))
        actual_alpha = min(blend_alpha, conf)

        # Probability-based score: weighted by TP2 and TP1 probability
        prob_score = 0.6 * float(prob["tp2_prob"]) + 0.4 * float(prob["tp1_prob"])

        enhanced_score = (1 - actual_alpha) * rule_based_score + actual_alpha * prob_score
        enhanced_score = round(max(0.0, min(1.0, enhanced_score)), 6)

        # Add probability snapshot to result for storage in prob_snapshot column
        prob["prob_score"] = prob_score
        prob["enhanced_score"] = enhanced_score
        prob["rule_score"] = rule_based_score

        return enhanced_score, prob


# ═════════════════════════════════════════════════════════════════════════════
# SHARED UTILITIES
# ═════════════════════════════════════════════════════════════════════════════

def _compute_stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate statistics for a group of trade records."""
    n = len(records)
    if n == 0:
        return {}

    tp1_hits   = [r["tp1_hit"] for r in records]
    tp2_hits   = [r["tp2_hit"] for r in records]
    runner_hits= [r.get("runner_hit", 0) for r in records]
    rrs        = [float(r.get("pnl_rr") or 0) for r in records]

    t_tp1  = [r["time_to_tp1_min"] for r in records if r.get("time_to_tp1_min") is not None]
    t_tp2  = [r["time_to_tp2_min"] for r in records if r.get("time_to_tp2_min") is not None]

    return {
        "n":             n,
        "tp1_rate":      sum(tp1_hits) / n,
        "tp2_rate":      sum(tp2_hits) / n,
        "runner_rate":   sum(runner_hits) / n,
        "mean_rr":       sum(rrs) / n if rrs else 0.0,
        "mean_time_tp1": sum(t_tp1) / len(t_tp1) if t_tp1 else _PRIOR["expected_time_tp1"],
        "mean_time_tp2": sum(t_tp2) / len(t_tp2) if t_tp2 else _PRIOR["expected_time_tp2"],
        "p25_time_tp1":  sorted(t_tp1)[len(t_tp1)//4]  if t_tp1 else _PRIOR["expected_time_tp1"],
        "p50_time_tp1":  sorted(t_tp1)[len(t_tp1)//2]  if t_tp1 else _PRIOR["expected_time_tp1"],
        "p75_time_tp1":  sorted(t_tp1)[3*len(t_tp1)//4] if t_tp1 else _PRIOR["expected_time_tp1"],
        "p50_time_tp2":  sorted(t_tp2)[len(t_tp2)//2]  if t_tp2 else _PRIOR["expected_time_tp2"],
        "p75_time_tp2":  sorted(t_tp2)[3*len(t_tp2)//4] if t_tp2 else _PRIOR["expected_time_tp2"],
    }


def _build_matrices(records: list[dict]) -> tuple:
    """
    Build numpy feature matrix X and label arrays for training.

    Classification: X (n×7) aligned with y_class (n,) per target
    Regression: y_regr[target] = list of (row_idx, value) pairs
                Caller must subset X[idxs] before fitting regressors.
    """
    X_all, y_class_all = [], {t: [] for t in _CLASS_TARGETS}
    y_regr_pairs: dict[str, list[tuple[int, float]]] = {t: [] for t in _REGR_TARGETS}

    for i, r in enumerate(records):
        try:
            row = [
                float(r.get("atr", 0)),
                float(r.get("volume_ratio", 1)),
                float(r.get("candle_expansion", 0)),
                float(r.get("structure_broken", 0)),
                float(r.get("direction_encoded", 1)),
                float(r.get("signal_score", 0.5)),
                float(r.get("rr_ratio", 2.0)),
            ]
            X_all.append(row)
            for t in _CLASS_TARGETS:
                y_class_all[t].append(int(r.get(t, 0)))
            # Regression: only record if value is non-None
            for t in _REGR_TARGETS:
                val = r.get(t)
                if val is not None:
                    y_regr_pairs[t].append((i, float(val)))
        except (TypeError, ValueError):
            continue

    X = np.array(X_all, dtype=np.float32)
    y_class = {t: np.array(v, dtype=np.int32) for t, v in y_class_all.items()}

    return X, y_class, y_regr_pairs


def _features_to_array(features: dict[str, Any]) -> "np.ndarray":
    """Convert feature dict to 2D numpy array (1 × n_features) for inference."""
    row = [
        float(features.get("atr", 0)),
        float(features.get("volume_ratio", 1)),
        float(features.get("candle_expansion", 0)),
        float(features.get("structure_broken", 0)),
        float(features.get("direction_encoded", 1)),
        float(features.get("signal_score", 0.5)),
        float(features.get("rr_ratio", 2.0)),
    ]
    return np.array([row], dtype=np.float32)


def _bin(value: float, boundaries: list[float]) -> int:
    """Discretize a float into a bin index based on boundaries."""
    for i, b in enumerate(boundaries):
        if value < b:
            return i
    return len(boundaries)


def _blend(a: float, b: float, w_b: float) -> float:
    """Weighted blend: (1 - w_b) * a + w_b * b"""
    return round((1 - w_b) * a + w_b * b, 6)


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _elapsed_minutes(start: datetime, end: datetime) -> float:
    return max(0.0, (end - start).total_seconds() / 60.0)
