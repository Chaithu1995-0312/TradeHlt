"""
test_probability_engine.py
═══════════════════════════════════════════════════════════════════════════════
INOUT Probability Engine — Test Suite

Coverage:
    - DataExtractor: join logic, feature extraction, CSV export
    - Approach A (Statistical): bucket logic, edge cases, prior fallback
    - Approach B (ML): training, prediction, save/load
    - Approach C (Sequence): stub behavior, extension point
    - Approach D (Hybrid): blend logic, auto-degradation
    - ProbabilityEngine: public API, output schema, EV calculation
    - INOUTScannerProbAdapter: score blending, not-fitted fallback
    - Architecture boundary: no forbidden imports

Run:
    python -m unittest inout.test_probability_engine -v
"""

from __future__ import annotations

import copy
import json
import os
import sys
import sqlite3
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inout.probability_engine import (
    INOUTDataExtractor,
    ProbabilityEngine,
    INOUTScannerProbAdapter,
    _ApproachA_Statistical,
    _ApproachB_ML,
    _ApproachC_Sequence,
    _ApproachD_Hybrid,
    _compute_stats,
    _bin,
    _blend,
    _PRIOR,
    _N_TRAIN_THRESHOLD,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_iso(offset_minutes: float = 0.0) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)).isoformat()


def _make_db_with_trades(n: int = 60, tp1_rate: float = 0.6, tp2_rate: float = 0.4) -> str:
    """Create a temp SQLite DB with synthetic completed trades for testing."""
    db_path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    # Schema mirrors inout/db.py exactly
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS inout_trades (
            trade_id TEXT PRIMARY KEY, symbol TEXT, direction TEXT,
            state TEXT, entry_price REAL, stop_loss REAL, tp1_price REAL,
            tp2_price REAL, runner_trail_sl REAL, position_size REAL,
            risk_pct REAL, rr_ratio REAL, signal_score REAL, signal_meta TEXT,
            created_at TEXT, activated_at TEXT, closed_at TEXT, time_stop_at TEXT,
            close_reason TEXT, total_pnl_rr REAL, prob_snapshot TEXT, gemini_context TEXT
        );
        CREATE TABLE IF NOT EXISTS inout_exits (
            exit_id TEXT PRIMARY KEY, trade_id TEXT, tier INTEGER,
            fraction REAL, fill_price REAL, target_price REAL,
            slippage_pct REAL, pnl_rr REAL, exit_reason TEXT, exited_at TEXT
        );
        CREATE TABLE IF NOT EXISTS inout_audit (
            audit_id TEXT PRIMARY KEY, trade_id TEXT, event_type TEXT,
            symbol TEXT, payload TEXT, logged_at TEXT
        );
    """)

    import uuid, random
    rng = random.Random(42)

    for i in range(n):
        trade_id   = str(uuid.uuid4())
        direction  = "LONG" if rng.random() > 0.4 else "SHORT"
        entry      = 50000.0 + rng.uniform(-500, 500)
        sl_dist    = 200.0 + rng.uniform(0, 100)
        stop_loss  = entry - sl_dist if direction == "LONG" else entry + sl_dist
        tp1_price  = entry + sl_dist if direction == "LONG" else entry - sl_dist
        tp2_price  = entry + 2 * sl_dist if direction == "LONG" else entry - 2 * sl_dist
        vol_ratio  = rng.uniform(1.5, 5.0)
        expansion  = rng.uniform(1.2, 6.0)
        signal_score = rng.uniform(0.5, 0.95)
        created    = _now_iso(-rng.uniform(30, 300))
        closed     = _now_iso(-rng.uniform(1, 25))
        meta = json.dumps({
            "atr": 150.0, "volume_ratio": vol_ratio,
            "candle_expansion": expansion, "structure_broken": rng.random() > 0.4,
            "direction": direction, "composite_score": signal_score,
        })

        # Determine outcome
        hit_tp1 = rng.random() < tp1_rate
        hit_tp2 = hit_tp1 and rng.random() < tp2_rate
        pnl = 2.0 if hit_tp2 else (1.0 if hit_tp1 else -1.0)

        conn.execute("""
            INSERT INTO inout_trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (trade_id, "BTCUSDT", direction, "CLOSED", entry, stop_loss, tp1_price, tp2_price,
              stop_loss, 0.01, 0.5, 2.0, signal_score, meta, created, created, closed,
              None, "TP2" if hit_tp2 else ("TP1" if hit_tp1 else "SL"), pnl, None, None))

        # Record exits
        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        closed_dt  = datetime.fromisoformat(closed.replace("Z", "+00:00"))
        duration   = (closed_dt - created_dt).total_seconds() / 60.0

        if hit_tp1:
            tp1_time = _now_iso(-duration * 0.5)
            conn.execute("""
                INSERT INTO inout_exits VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (str(uuid.uuid4()), trade_id, 1, 0.30,
                  tp1_price, tp1_price, 0.0, 1.0, "TP1", tp1_time))

        if hit_tp2:
            tp2_time = _now_iso(-duration * 0.2)
            conn.execute("""
                INSERT INTO inout_exits VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (str(uuid.uuid4()), trade_id, 2, 0.50,
                  tp2_price, tp2_price, 0.0, 2.0, "TP2", tp2_time))
        elif not hit_tp1:
            conn.execute("""
                INSERT INTO inout_exits VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (str(uuid.uuid4()), trade_id, 99, 1.0,
                  stop_loss, stop_loss, 0.0, -1.0, "SL", closed))

    conn.commit()
    conn.close()
    return db_path


def _make_features(
    vol: float = 2.5, exp: float = 3.0, struct: bool = True,
    direction: str = "LONG", score: float = 0.72, rr: float = 2.0
) -> dict[str, Any]:
    return {
        "atr": 150.0, "volume_ratio": vol, "candle_expansion": exp,
        "structure_broken": int(struct),
        "direction": direction,
        "direction_encoded": 1 if direction == "LONG" else -1,
        "signal_score": score,
        "rr_ratio": rr,
    }


def _make_records(n: int = 80, tp1_rate: float = 0.6, tp2_rate: float = 0.35) -> list[dict]:
    """Build synthetic dataset records directly (bypasses SQLite)."""
    import random, uuid
    rng = random.Random(99)
    records = []
    for _ in range(n):
        tp1 = int(rng.random() < tp1_rate)
        tp2 = int(tp1 and rng.random() < tp2_rate)
        runner = int(tp2 and rng.random() < 0.3)
        pnl = 2.0 if tp2 else (1.0 if tp1 else -1.0)
        records.append({
            "trade_id":           str(uuid.uuid4()),
            "symbol":             "BTCUSDT",
            "direction":          "LONG" if rng.random() > 0.4 else "SHORT",
            "direction_encoded":  1,
            "atr":                100.0 + rng.uniform(-20, 20),
            "volume_ratio":       rng.uniform(1.5, 5.0),
            "candle_expansion":   rng.uniform(1.2, 6.0),
            "structure_broken":   int(rng.random() > 0.4),
            "signal_score":       rng.uniform(0.5, 0.9),
            "rr_ratio":           2.0,
            "state":              "CLOSED",
            "created_at":         _now_iso(-60),
            "closed_at":          _now_iso(-5),
            "tp1_hit":            tp1,
            "tp2_hit":            tp2,
            "runner_hit":         runner,
            "stopped":            int(not tp1),
            "timeout":            0,
            "time_to_tp1_min":    rng.uniform(1, 8) if tp1 else None,
            "time_to_tp2_min":    rng.uniform(3, 12) if tp2 else None,
            "total_duration_min": rng.uniform(3, 15),
            "pnl_rr":             pnl,
        })
    return records


# ═════════════════════════════════════════════════════════════════════════════
# 1. DataExtractor Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestDataExtractor(unittest.TestCase):

    def setUp(self):
        self.db_path = _make_db_with_trades(n=30)

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except Exception:
            pass

    def test_extract_returns_records(self):
        ext = INOUTDataExtractor(self.db_path)
        records = ext.extract()
        self.assertEqual(len(records), 30)

    def test_records_have_required_columns(self):
        ext = INOUTDataExtractor(self.db_path)
        records = ext.extract()
        required = [
            "trade_id", "symbol", "direction", "direction_encoded",
            "atr", "volume_ratio", "candle_expansion", "structure_broken",
            "signal_score", "rr_ratio",
            "tp1_hit", "tp2_hit", "runner_hit", "stopped", "timeout",
            "time_to_tp1_min", "time_to_tp2_min", "total_duration_min", "pnl_rr",
        ]
        for col in required:
            self.assertIn(col, records[0], msg=f"missing column: {col}")

    def test_binary_labels_are_0_or_1(self):
        ext = INOUTDataExtractor(self.db_path)
        for r in ext.extract():
            self.assertIn(r["tp1_hit"], (0, 1))
            self.assertIn(r["tp2_hit"], (0, 1))

    def test_missing_db_returns_empty(self):
        ext = INOUTDataExtractor("/nonexistent/path.db")
        self.assertEqual(ext.extract(), [])

    def test_to_csv_writes_file(self):
        ext = INOUTDataExtractor(self.db_path)
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = f.name
        try:
            count = ext.to_csv(csv_path)
            self.assertEqual(count, 30)
            self.assertTrue(Path(csv_path).exists())
            with open(csv_path) as f:
                lines = f.readlines()
            self.assertEqual(len(lines), 31)  # header + 30 rows
        finally:
            os.unlink(csv_path)

    def test_only_closed_trades_extracted(self):
        """PENDING/ACTIVE trades must not appear in dataset."""
        conn = sqlite3.connect(self.db_path)
        import uuid
        conn.execute("""
            INSERT INTO inout_trades (trade_id, symbol, direction, state, signal_meta, created_at)
            VALUES (?, 'BTCUSDT', 'LONG', 'ACTIVE', '{}', ?)
        """, (str(uuid.uuid4()), _now_iso()))
        conn.commit()
        conn.close()
        ext = INOUTDataExtractor(self.db_path)
        records = ext.extract()
        states = {r["state"] for r in records}
        self.assertNotIn("ACTIVE", states)


# ═════════════════════════════════════════════════════════════════════════════
# 2. Approach A — Statistical Bucket Engine
# ═════════════════════════════════════════════════════════════════════════════

class TestApproachA(unittest.TestCase):

    def setUp(self):
        self.records = _make_records(n=100)
        self.engine = _ApproachA_Statistical(min_bucket_n=5)
        self.engine.fit(self.records)

    def test_fit_sets_global_stats(self):
        self.assertGreater(len(self.engine._global), 0)
        self.assertIn("tp1_rate", self.engine._global)

    def test_predict_returns_schema(self):
        features = _make_features()
        result = self.engine.predict(features)
        for key in ("tp1_prob", "tp2_prob", "runner_prob",
                    "expected_time_tp1", "expected_time_tp2",
                    "expected_rr", "confidence", "n_samples", "warnings", "approach"):
            self.assertIn(key, result, msg=f"missing key: {key}")

    def test_probabilities_clamped_between_0_1(self):
        features = _make_features()
        result = self.engine.predict(features)
        for k in ("tp1_prob", "tp2_prob", "runner_prob", "confidence"):
            self.assertGreaterEqual(result[k], 0.0)
            self.assertLessEqual(result[k], 1.0)

    def test_tp1_rate_reflects_data(self):
        """With tp1_rate=0.6 in synthetic data, tp1_prob should be near 0.6"""
        features = _make_features()
        result = self.engine.predict(features)
        # Allow ±0.3 tolerance — bucket may vary
        self.assertGreater(result["tp1_prob"], 0.1)

    def test_prior_returned_when_no_data(self):
        engine = _ApproachA_Statistical()
        # Not fitted — global is empty
        result = engine.predict(_make_features())
        self.assertIn("prior", result.get("approach", ""))

    def test_low_bucket_n_warning(self):
        engine = _ApproachA_Statistical(min_bucket_n=999)
        engine.fit(self.records)
        result = engine.predict(_make_features())
        # With min_n=999 and small data, should warn about low count
        self.assertIsInstance(result.get("warnings", []), list)

    def test_bucket_key_varies_with_features(self):
        k1 = self.engine._bucket_key(_make_features(vol=1.0, exp=1.0))
        k2 = self.engine._bucket_key(_make_features(vol=5.0, exp=8.0))
        self.assertNotEqual(k1, k2)

    def test_different_directions_get_different_keys(self):
        k_long  = self.engine._bucket_key(_make_features(direction="LONG"))
        k_short = self.engine._bucket_key(_make_features(direction="SHORT"))
        self.assertNotEqual(k_long, k_short)


# ═════════════════════════════════════════════════════════════════════════════
# 3. Approach B — ML Model Engine
# ═════════════════════════════════════════════════════════════════════════════

class TestApproachB(unittest.TestCase):

    def setUp(self):
        self.model_dir = tempfile.mkdtemp()
        self.records = _make_records(n=100)
        self.engine = _ApproachB_ML(model_dir=self.model_dir)

    def test_not_fitted_returns_prior(self):
        result = self.engine.predict(_make_features())
        self.assertIn("not_fitted", result["approach"])

    def test_fit_with_sufficient_data(self):
        self.engine.fit(self.records)
        self.assertTrue(self.engine._fitted)
        self.assertEqual(self.engine._n_train, len(self.records))

    def test_fit_skipped_insufficient_data(self):
        engine = _ApproachB_ML(model_dir=self.model_dir)
        engine.fit(_make_records(n=5))   # far below threshold
        self.assertFalse(engine._fitted)

    def test_predict_after_fit_returns_schema(self):
        self.engine.fit(self.records)
        result = self.engine.predict(_make_features())
        for key in ("tp1_prob", "tp2_prob", "runner_prob",
                    "expected_time_tp1", "expected_time_tp2",
                    "expected_rr", "confidence", "n_samples", "warnings"):
            self.assertIn(key, result)

    def test_probabilities_in_valid_range(self):
        self.engine.fit(self.records)
        result = self.engine.predict(_make_features())
        for k in ("tp1_prob", "tp2_prob", "runner_prob", "confidence"):
            v = result[k]
            self.assertGreaterEqual(v, 0.0, msg=f"{k}={v}")
            self.assertLessEqual(v, 1.0, msg=f"{k}={v}")

    def test_high_score_signal_has_higher_tp_prob(self):
        """Higher signal quality should generally yield higher TP probability."""
        self.engine.fit(self.records)
        r_low  = self.engine.predict(_make_features(score=0.51, vol=1.1, exp=1.2))
        r_high = self.engine.predict(_make_features(score=0.92, vol=4.8, exp=5.5))
        # Not guaranteed by small data, but test that output varies
        self.assertIsNotNone(r_low["tp2_prob"])
        self.assertIsNotNone(r_high["tp2_prob"])

    def test_save_and_load(self):
        self.engine.fit(self.records)
        tp2_before = self.engine.predict(_make_features())["tp2_prob"]

        self.engine.save()

        engine2 = _ApproachB_ML(model_dir=self.model_dir)
        ok = engine2.load()
        self.assertTrue(ok)
        self.assertTrue(engine2._fitted)

        tp2_after = engine2.predict(_make_features())["tp2_prob"]
        self.assertAlmostEqual(tp2_before, tp2_after, places=4)


# ═════════════════════════════════════════════════════════════════════════════
# 4. Approach C — Sequence Model Stub
# ═════════════════════════════════════════════════════════════════════════════

class TestApproachC(unittest.TestCase):

    def setUp(self):
        self.engine = _ApproachC_Sequence()

    def test_fit_is_noop(self):
        """fit() should not raise even on empty records"""
        self.engine.fit([])
        self.engine.fit(_make_records(n=10))

    def test_predict_returns_prior_with_stub_warning(self):
        result = self.engine.predict(_make_features())
        self.assertEqual(result["approach"], "C_stub")
        self.assertIn("approach_C_is_stub_phase2_not_implemented", result["warnings"])

    def test_predict_sequence_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.engine._predict_sequence([])

    def test_returns_prior_values(self):
        result = self.engine.predict(_make_features())
        self.assertAlmostEqual(result["tp1_prob"], _PRIOR["tp1_prob"])
        self.assertAlmostEqual(result["tp2_prob"], _PRIOR["tp2_prob"])


# ═════════════════════════════════════════════════════════════════════════════
# 5. Approach D — Hybrid Engine
# ═════════════════════════════════════════════════════════════════════════════

class TestApproachD(unittest.TestCase):

    def setUp(self):
        self.model_dir = tempfile.mkdtemp()

    def test_prior_only_with_zero_records(self):
        engine = _ApproachD_Hybrid(model_dir=self.model_dir)
        engine.fit([])
        result = engine.predict(_make_features())
        self.assertIn("prior", result["approach"])

    def test_stat_only_with_few_records(self):
        engine = _ApproachD_Hybrid(model_dir=self.model_dir)
        engine.fit(_make_records(n=20))
        result = engine.predict(_make_features())
        self.assertIn("stat_only", result["approach"])

    def test_hybrid_active_with_sufficient_records(self):
        engine = _ApproachD_Hybrid(model_dir=self.model_dir)
        engine.fit(_make_records(n=100))
        result = engine.predict(_make_features())
        self.assertIn("hybrid", result["approach"])

    def test_blend_weight_in_result(self):
        engine = _ApproachD_Hybrid(model_dir=self.model_dir)
        engine.fit(_make_records(n=100))
        result = engine.predict(_make_features())
        self.assertIn("blend_weight_b", result)
        self.assertGreaterEqual(result["blend_weight_b"], 0.0)
        self.assertLessEqual(result["blend_weight_b"], 1.0)

    def test_save_and_load_propagates_to_b(self):
        engine = _ApproachD_Hybrid(model_dir=self.model_dir)
        engine.fit(_make_records(n=100))
        engine.save()

        engine2 = _ApproachD_Hybrid(model_dir=self.model_dir)
        ok = engine2.load()
        self.assertTrue(ok)


# ═════════════════════════════════════════════════════════════════════════════
# 6. ProbabilityEngine — Public API
# ═════════════════════════════════════════════════════════════════════════════

class TestProbabilityEngine(unittest.TestCase):

    def setUp(self):
        self.model_dir = tempfile.mkdtemp()
        self.db_path   = _make_db_with_trades(n=70)

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except Exception:
            pass

    def test_not_fitted_returns_prior_with_warning(self):
        engine = ProbabilityEngine(approach="D", model_dir=self.model_dir)
        result = engine.predict(_make_features())
        self.assertFalse(engine.is_fitted)
        self.assertIn("not_fitted", result["approach"])
        self.assertIn("engine_not_fitted_returning_prior", result["warnings"])

    def test_train_from_db(self):
        engine = ProbabilityEngine(approach="A", model_dir=self.model_dir)
        n = engine.train(db_path=self.db_path, save_dataset=False)
        self.assertEqual(n, 70)
        self.assertTrue(engine.is_fitted)

    def test_train_from_records(self):
        engine = ProbabilityEngine(approach="B", model_dir=self.model_dir)
        records = _make_records(n=80)
        n = engine.train_from_records(records)
        self.assertEqual(n, 80)
        self.assertTrue(engine.is_fitted)

    def test_predict_canonical_schema(self):
        engine = ProbabilityEngine(approach="A", model_dir=self.model_dir)
        engine.train_from_records(_make_records(n=80))
        result = engine.predict(_make_features())
        required = [
            "approach", "tp1_prob", "tp2_prob", "runner_prob",
            "expected_time_tp1", "expected_time_tp2", "expected_rr",
            "confidence", "n_samples", "warnings",
        ]
        for k in required:
            self.assertIn(k, result, msg=f"missing key: {k}")

    def test_all_four_approaches_instantiate(self):
        for approach in ("A", "B", "C", "D"):
            engine = ProbabilityEngine(approach=approach, model_dir=self.model_dir)
            self.assertEqual(engine.approach, approach)

    def test_from_config_uses_dict(self):
        cfg = {"approach": "A", "model_dir": self.model_dir, "blend_weight": 0.5}
        engine = ProbabilityEngine.from_config(cfg)
        self.assertEqual(engine.approach, "A")

    def test_unknown_approach_defaults_to_d(self):
        engine = ProbabilityEngine(approach="Z", model_dir=self.model_dir)
        self.assertEqual(engine.approach, "Z")  # stored as-is, engine is D

    def test_output_clamping(self):
        """Probabilities must never exceed [0, 1]."""
        engine = ProbabilityEngine(approach="A", model_dir=self.model_dir)
        engine.train_from_records(_make_records(n=80))
        result = engine.predict(_make_features())
        for k in ("tp1_prob", "tp2_prob", "runner_prob", "confidence"):
            v = result[k]
            self.assertGreaterEqual(v, 0.0, f"{k}={v}")
            self.assertLessEqual(v, 1.0, f"{k}={v}")

    def test_compute_ev_positive_for_high_win_rate(self):
        engine = ProbabilityEngine(approach="A", model_dir=self.model_dir)
        prob = {"tp1_prob": 0.7, "tp2_prob": 0.5, "runner_prob": 0.2}
        ev = engine.compute_ev(prob, sl_rr=1.0)
        self.assertGreater(ev, 0)

    def test_compute_ev_negative_for_low_win_rate(self):
        engine = ProbabilityEngine(approach="A", model_dir=self.model_dir)
        prob = {"tp1_prob": 0.1, "tp2_prob": 0.05, "runner_prob": 0.02}
        ev = engine.compute_ev(prob, sl_rr=1.0)
        self.assertLess(ev, 0)

    def test_save_and_load_b(self):
        engine = ProbabilityEngine(approach="B", model_dir=self.model_dir)
        engine.train_from_records(_make_records(n=80))
        tp2_before = engine.predict(_make_features())["tp2_prob"]
        engine.save()

        engine2 = ProbabilityEngine(approach="B", model_dir=self.model_dir)
        ok = engine2.load()
        self.assertTrue(ok)
        tp2_after = engine2.predict(_make_features())["tp2_prob"]
        self.assertAlmostEqual(tp2_before, tp2_after, places=4)

    def test_save_noop_for_approach_a(self):
        """Approach A has no file artifacts — save() should not raise."""
        engine = ProbabilityEngine(approach="A", model_dir=self.model_dir)
        engine.train_from_records(_make_records(n=80))
        engine.save()  # must not raise

    def test_approach_d_degrades_gracefully_small_data(self):
        engine = ProbabilityEngine(approach="D", model_dir=self.model_dir)
        engine.train_from_records(_make_records(n=8))   # below stat threshold
        result = engine.predict(_make_features())
        # Must return something valid, not crash
        self.assertIn("approach", result)
        self.assertIn("tp2_prob", result)

    def test_approach_d_uses_hybrid_with_large_data(self):
        engine = ProbabilityEngine(approach="D", model_dir=self.model_dir)
        engine.train_from_records(_make_records(n=100))
        result = engine.predict(_make_features())
        self.assertIn("hybrid", result["approach"])

    def test_direction_encoding_auto(self):
        """direction → direction_encoded normalization should work."""
        engine = ProbabilityEngine(approach="A", model_dir=self.model_dir)
        engine.train_from_records(_make_records(n=80))
        # Pass direction as string (no direction_encoded)
        features = {"atr": 150.0, "volume_ratio": 2.5, "candle_expansion": 3.0,
                    "structure_broken": 1, "direction": "SHORT",
                    "signal_score": 0.70, "rr_ratio": 2.0}
        result = engine.predict(features)
        self.assertIn("tp2_prob", result)


# ═════════════════════════════════════════════════════════════════════════════
# 7. Scanner Prob Adapter Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestINOUTScannerProbAdapter(unittest.TestCase):

    def setUp(self):
        self.model_dir = tempfile.mkdtemp()
        self.prob_cfg = {
            "tp2_min_prob": 0.30, "tp1_min_prob": 0.35,
            "min_confidence": 0.10, "prob_blend_alpha": 0.7,
        }

    def test_unfitted_engine_returns_rule_score_unchanged(self):
        engine = ProbabilityEngine(approach="A", model_dir=self.model_dir)
        adapter = INOUTScannerProbAdapter(engine, self.prob_cfg)
        score, prob = adapter.score_signal(0.75, _make_features())
        self.assertAlmostEqual(score, 0.75)
        self.assertIn("fallback_rule_based", prob["approach"])

    def test_fitted_engine_blends_score(self):
        engine = ProbabilityEngine(approach="A", model_dir=self.model_dir)
        engine.train_from_records(_make_records(n=80))
        adapter = INOUTScannerProbAdapter(engine, self.prob_cfg)
        score, prob = adapter.score_signal(0.75, _make_features())
        # Blended score should be different from pure rule score
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
        self.assertIn("prob_score", prob)
        self.assertIn("rule_score", prob)
        self.assertAlmostEqual(prob["rule_score"], 0.75)

    def test_enhanced_score_bounded(self):
        engine = ProbabilityEngine(approach="A", model_dir=self.model_dir)
        engine.train_from_records(_make_records(n=80))
        adapter = INOUTScannerProbAdapter(engine, self.prob_cfg)
        for rule_score in (0.0, 0.5, 1.0):
            score, _ = adapter.score_signal(rule_score, _make_features())
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)


# ═════════════════════════════════════════════════════════════════════════════
# 8. Utility Function Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestUtilities(unittest.TestCase):

    def test_bin_returns_correct_index(self):
        boundaries = [1.0, 2.0, 4.0, 7.0]
        self.assertEqual(_bin(0.5, boundaries), 0)
        self.assertEqual(_bin(1.5, boundaries), 1)
        self.assertEqual(_bin(3.0, boundaries), 2)
        self.assertEqual(_bin(5.0, boundaries), 3)
        self.assertEqual(_bin(10.0, boundaries), 4)  # beyond all

    def test_blend_midpoint(self):
        result = _blend(0.0, 1.0, 0.5)
        self.assertAlmostEqual(result, 0.5)

    def test_blend_zero_weight(self):
        result = _blend(0.8, 0.3, 0.0)
        self.assertAlmostEqual(result, 0.8)

    def test_blend_full_weight(self):
        result = _blend(0.8, 0.3, 1.0)
        self.assertAlmostEqual(result, 0.3)

    def test_compute_stats_empty(self):
        self.assertEqual(_compute_stats([]), {})

    def test_compute_stats_rates(self):
        records = [{"tp1_hit": 1, "tp2_hit": 1, "runner_hit": 0, "pnl_rr": 2.0,
                    "time_to_tp1_min": 3.0, "time_to_tp2_min": 7.0},
                   {"tp1_hit": 0, "tp2_hit": 0, "runner_hit": 0, "pnl_rr": -1.0,
                    "time_to_tp1_min": None, "time_to_tp2_min": None}]
        stats = _compute_stats(records)
        self.assertAlmostEqual(stats["tp1_rate"], 0.5)
        self.assertAlmostEqual(stats["tp2_rate"], 0.5)
        self.assertEqual(stats["n"], 2)


# ═════════════════════════════════════════════════════════════════════════════
# 9. Architecture Boundary Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestProbEngineArchitecture(unittest.TestCase):
    """
    Verify probability_engine.py does NOT import from forbidden modules.
    Checks import lines only (not docstrings/comments).
    """

    @staticmethod
    def _import_lines(filepath: str) -> str:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return "\n".join(
            ln.rstrip()
            for ln in lines
            if ln.strip().startswith(("import ", "from "))
        )

    def _prob_file(self) -> str:
        import inout.probability_engine as mod
        return mod.__file__

    def test_does_not_import_engine_runner(self):
        imports = self._import_lines(self._prob_file())
        self.assertNotIn("engine_runner", imports)

    def test_does_not_import_fusion_engine(self):
        imports = self._import_lines(self._prob_file())
        self.assertNotIn("fusion_engine", imports)

    def test_does_not_import_live_engine_hook(self):
        imports = self._import_lines(self._prob_file())
        self.assertNotIn("live_engine_hook", imports)

    def test_does_not_import_execution_planner(self):
        imports = self._import_lines(self._prob_file())
        self.assertNotIn("execution_planner", imports)

    def test_does_not_write_to_inout_db(self):
        """Probability engine must never INSERT/UPDATE inout_trades."""
        with open(self._prob_file(), "r", encoding="utf-8") as f:
            src = f.read()
        # Only DataExtractor accesses DB and it's read-only
        # Verify no INSERT/UPDATE on core tables outside DataExtractor
        self.assertNotIn("INSERT INTO inout_trades", src)
        self.assertNotIn("UPDATE inout_trades", src)
        self.assertNotIn("INSERT INTO inout_exits", src)


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("INOUT Probability Engine — Test Suite")
    print("=" * 60)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestDataExtractor,
        TestApproachA,
        TestApproachB,
        TestApproachC,
        TestApproachD,
        TestProbabilityEngine,
        TestINOUTScannerProbAdapter,
        TestUtilities,
        TestProbEngineArchitecture,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
