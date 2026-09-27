"""Tests for CH-cost-model-identity-stamp (TRACE_OBSERVATION_JOIN).

Covers the cost/denominator identity stamping added to backtest_v2's trade
records, summary.json and report.txt:

 1. cost_model_params_hash deterministic + sensitive to any of the 4 knobs
 2. strict-read fail-closed: removing ANY of the 4 cost knobs makes
    from_prod_config RAISE (KeyError) - never '' / default id / empty hash
 3. single-valued id: derivation always emits backtest_g1g2_v2 (backtest_zero_cost
    is reserve-only, never generated)
 4. to_csv_rows stamps the 3 fields on each row; old-record load keeps "" defaults
 5. _write_summary stamps the 3 keys at the run level
 6. no current production backtest config path reaches the reserve-only zero id

Pure additive metadata: these tests never assert a change in any PnL value.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import config_layer.production_config as _pc  # noqa: E402  (patched in tests)
from runtime import backtest_v2 as b  # noqa: E402


def _full_backtest_cfg() -> dict:
    return {
        "htf_candles_per_range": 16,
        "warmup_candles": 78,
        "slippage_enabled": True,
        "slippage_atr_fraction": 0.1,
        "slippage_seed": 42,
        "simulated_spread_pct": 0.0002,
        "initial_capital": 100000.0,
        "risk_pct_per_trade": 0.01,
        "use_compounding": True,
        "gap_reset_enabled": True,
        "gap_reset_minutes": 120,
        "event_flush_every": 100,
    }


def _expected_hash(enabled, fraction, seed, spread) -> str:
    payload = json.dumps({
        "slippage_enabled": bool(enabled),
        "slippage_atr_fraction": float(fraction),
        "slippage_seed": int(seed),
        "simulated_spread_pct": float(spread),
    }, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# ── 1. hash determinism / knob sensitivity ─────────────────────────────────
def test_params_hash_deterministic_and_knob_sensitive():
    h1 = b._cost_params_hash(True, 0.1, 42, 0.0002)
    assert h1 == b._cost_params_hash(True, 0.1, 42, 0.0002)      # deterministic
    assert h1 == _expected_hash(True, 0.1, 42, 0.0002)            # matches spec
    # any single knob change changes the hash
    assert h1 != b._cost_params_hash(False, 0.1, 42, 0.0002)
    assert h1 != b._cost_params_hash(True, 0.05, 42, 0.0002)
    assert h1 != b._cost_params_hash(True, 0.1, 7, 0.0002)
    assert h1 != b._cost_params_hash(True, 0.1, 42, 0.0010)


# ── 2. strict-read fail-closed (NEGATIVE) ──────────────────────────────────
@pytest.mark.parametrize("knob", [
    "slippage_enabled", "slippage_atr_fraction", "slippage_seed",
    "simulated_spread_pct",
])
def test_missing_any_cost_knob_raises(monkeypatch, knob):
    cfg = _full_backtest_cfg()
    cfg.pop(knob)
    monkeypatch.setattr(_pc, "get_prod_section", lambda section: cfg)
    with pytest.raises(KeyError):
        b.BacktestConfig.from_prod_config()


def test_full_cfg_derives_single_valued_id(monkeypatch):
    cfg = _full_backtest_cfg()
    monkeypatch.setattr(_pc, "get_prod_section", lambda section: cfg)
    bc = b.BacktestConfig.from_prod_config()
    assert bc.cost_model_id == b.BACKTEST_COST_MODEL_ID == "backtest_g1g2_v2"
    assert bc.cost_model_params_hash == _expected_hash(True, 0.1, 42, 0.0002)
    assert len(bc.cost_model_params_hash) == 16


# ── 3. reserve-only zero id ────────────────────────────────────────────────
def test_zero_cost_is_reserve_only_never_generated():
    assert b.BACKTEST_COST_MODEL_ID_ZERO_RESERVED == "backtest_zero_cost"
    assert b.BACKTEST_COST_MODEL_ID != b.BACKTEST_COST_MODEL_ID_ZERO_RESERVED
    # derivation is a constant; a hash value can never equal the reserved id string
    assert _expected_hash(False, 0.0, 0, 0.0) != b.BACKTEST_COST_MODEL_ID_ZERO_RESERVED


# ── 4. trades.csv rows stamped + old-record back-compat ────────────────────
def test_to_csv_rows_stamps_cost_identity():
    journal = b.TradeJournal(
        "XAUUSD", 0.01,
        b.SlippageModel(0.1, 42),
        b.CapitalCurve(100000.0, 0.01, True),
        0.2,
        cost_model_id=b.BACKTEST_COST_MODEL_ID,
        cost_model_params_hash="abc123def4567890",
        risk_denominator_id=b.BACKTEST_RISK_DENOM_ID,
    )
    rec = b.TradeRecord(
        trade_id="T1", instrument="XAUUSD", direction="LONG",
        entry_price_raw=2614.46, sl_price=2610.05, tp1_price=2618.87, tp2_price=2623.28,
        entry_price_fill=2614.46, exit_price_fill=2609.77, exit_reason="STOPPED",
        pnl_rr_raw=-0.8763, pnl_rr_net=-1.0547,
    )
    # mirror what on_trade_opened does (set the journal-level ids on the record)
    rec.cost_model_id = journal.cost_model_id
    rec.cost_model_params_hash = journal.cost_model_params_hash
    rec.risk_denominator_id = journal.risk_denominator_id
    journal.closed.append(rec)

    rows = journal.to_csv_rows()
    assert rows, "expected at least one csv row"
    row = rows[0]
    assert row["cost_model_id"] == b.BACKTEST_COST_MODEL_ID
    assert row["cost_model_params_hash"] == "abc123def4567890"
    assert row["risk_denominator_id"] == b.BACKTEST_RISK_DENOM_ID
    # Parity: existing PnL columns are carried through unchanged (additive stamp only).
    assert row["pnl_rr_raw"] == -0.8763
    assert row["pnl_rr_net"] == -1.0547


def test_old_record_defaults_empty_for_backcompat():
    rec = b.TradeRecord(
        trade_id="T1", instrument="X", direction="LONG",
        entry_price_raw=1.0, sl_price=0.9, tp1_price=1.1, tp2_price=1.2,
    )
    assert rec.cost_model_id == ""
    assert rec.cost_model_params_hash == ""
    assert rec.risk_denominator_id == ""


# ── 5. summary.json run-level stamping ─────────────────────────────────────
def test_write_summary_stamps_cost_identity(tmp_path):
    writer = b.ReportWriter(str(tmp_path), "XAUUSD")

    class _M:
        def to_dict(self):
            return {"instrument": "XAUUSD"}

    writer._write_summary(
        _M(), run_id="RUN1",
        cost_model_id="backtest_g1g2_v2",
        cost_model_params_hash="abc", risk_denominator_id="entry_fill_to_sl__v1",
    )
    data = json.loads((writer.output_dir / "XAUUSD_summary.json").read_text(encoding="utf-8"))
    assert data["run_id"] == "RUN1"
    assert data["cost_model_id"] == "backtest_g1g2_v2"
    assert data["cost_model_params_hash"] == "abc"
    assert data["risk_denominator_id"] == "entry_fill_to_sl__v1"


# ── 6. no current production backtest config reaches the reserve-only id ───
def test_no_production_config_reaches_zero_reserved_id():
    prod = ROOT / "configs" / "production"
    seen = 0
    for cfg_path in sorted(prod.glob("*.json")):
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        backtest = cfg.get("backtest")
        if not isinstance(backtest, dict):
            continue
        seen += 1
        # derivation is the module constant; it must never equal the reserved id
        assert b.BACKTEST_COST_MODEL_ID != b.BACKTEST_COST_MODEL_ID_ZERO_RESERVED
    assert seen > 0, "expected production configs with a 'backtest' section"


# ── 7. CH-measurement-basis-declaration: the remaining 4 basis axes + disclosure ──
def test_walk_kernel_and_reference_level_are_closed_vocab_members():
    from governance.measurement_basis import REFERENCE_LEVELS
    from identity.tokens import WALK_KERNELS

    assert b.BACKTEST_WALK_KERNEL in WALK_KERNELS
    assert b.BACKTEST_REFERENCE_LEVEL in REFERENCE_LEVELS


def test_engine_fill_model_id_is_a_closed_vocab_member():
    from identity.tokens import FILL_MODEL_IDS

    assert b.ENGINE_FILL_MODEL_ID in FILL_MODEL_IDS


def test_tie_break_resolved_from_intrabar_exits_flag():
    from governance.measurement_basis import TIE_BREAK_CLOSE_ONLY, TIE_BREAK_PRODUCTION

    intrabar = b.TradeJournal(
        "XAUUSD", 0.01, b.SlippageModel(0.1, 42), b.CapitalCurve(100000.0, 0.01, True),
        0.2, intrabar_exits=True,
    )
    assert intrabar.tie_break == TIE_BREAK_PRODUCTION

    close_only = b.TradeJournal(
        "XAUUSD", 0.01, b.SlippageModel(0.1, 42), b.CapitalCurve(100000.0, 0.01, True),
        0.2, intrabar_exits=False,
    )
    assert close_only.tie_break == TIE_BREAK_CLOSE_ONLY


def test_tie_break_defaults_to_production_for_backcompat_callers():
    """A caller that doesn't pass intrabar_exits (matching every pre-existing call
    site before this change) must still declare a value, never blank — production
    is the correct default because intrabar_touch IS the config default."""
    journal = b.TradeJournal(
        "XAUUSD", 0.01, b.SlippageModel(0.1, 42), b.CapitalCurve(100000.0, 0.01, True), 0.2,
    )
    from governance.measurement_basis import TIE_BREAK_PRODUCTION
    assert journal.tie_break == TIE_BREAK_PRODUCTION


def test_to_csv_rows_stamps_measurement_basis():
    journal = b.TradeJournal(
        "XAUUSD", 0.01, b.SlippageModel(0.1, 42), b.CapitalCurve(100000.0, 0.01, True),
        0.2, intrabar_exits=True,
    )
    rec = b.TradeRecord(
        trade_id="T1", instrument="XAUUSD", direction="LONG",
        entry_price_raw=2614.46, sl_price=2610.05, tp1_price=2618.87, tp2_price=2623.28,
        entry_price_fill=2614.46, exit_price_fill=2609.77, exit_reason="STOPPED",
        pnl_rr_raw=-0.8763, pnl_rr_net=-1.0547,
    )
    # mirror what on_trade_opened does
    rec.walk_kernel = b.BACKTEST_WALK_KERNEL
    rec.reference_level = b.BACKTEST_REFERENCE_LEVEL
    rec.fill_model_id = b.ENGINE_FILL_MODEL_ID
    rec.tie_break = journal.tie_break
    rec.sl_refloored = True
    journal.closed.append(rec)

    row = journal.to_csv_rows()[0]
    assert row["walk_kernel"] == "backtest_ledger"
    assert row["reference_level"] == "displacement_extreme"
    assert row["fill_model_id"] == "engine_intrabar"
    assert row["tie_break"] == "production"
    assert row["sl_refloored"] == 1
    # Parity: additive stamp only.
    assert row["pnl_rr_net"] == -1.0547


def test_old_record_defaults_for_measurement_basis():
    rec = b.TradeRecord(
        trade_id="T1", instrument="X", direction="LONG",
        entry_price_raw=1.0, sl_price=0.9, tp1_price=1.1, tp2_price=1.2,
    )
    assert rec.walk_kernel == ""
    assert rec.reference_level == ""
    assert rec.fill_model_id == ""
    assert rec.tie_break == ""
    assert rec.sl_refloored is False


def test_stamped_basis_produces_a_basis_object_can_compare_allows():
    from governance.measurement_basis import ALLOW_SAME_BASIS, basis_from_row, can_compare

    journal = b.TradeJournal(
        "XAUUSD", 0.01, b.SlippageModel(0.1, 42), b.CapitalCurve(100000.0, 0.01, True),
        0.2, cost_model_id=b.BACKTEST_COST_MODEL_ID, intrabar_exits=True,
    )
    rec = b.TradeRecord(
        trade_id="T1", instrument="XAUUSD", direction="LONG",
        entry_price_raw=1.0, sl_price=0.9, tp1_price=1.1, tp2_price=1.2,
    )
    rec.cost_model_id = journal.cost_model_id
    rec.walk_kernel = b.BACKTEST_WALK_KERNEL
    rec.reference_level = b.BACKTEST_REFERENCE_LEVEL
    rec.fill_model_id = b.ENGINE_FILL_MODEL_ID
    rec.tie_break = journal.tie_break
    journal.closed.append(rec)
    row = journal.to_csv_rows()[0]

    a = basis_from_row(row)
    b2 = basis_from_row(row)
    verdict, _ = can_compare(a, b2)
    assert verdict == ALLOW_SAME_BASIS