"""Tradelatest baseline adapter — normalize spine/research trade rows into BenchmarkTradeRecord.

Does NOT re-run the engine. Maps existing ledger dicts (backtest trades CSV rows,
research Outcome-like dicts) into the common contract with honest UNKNOWN fields.

Reuse:
  - Dataset pin via DatasetManifest / Phase-1 corpus binding
  - Fill model declaration mirrors research forward_walk
  - Metrics are computed outside this adapter (oss_lab.metrics)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Sequence

from oss_lab.adapters.base import AdapterCapability
from oss_lab.contracts.dataset_manifest import (
    XAUUSD_M15_PHASE1_PRIMARY,
    DatasetManifest,
)
from oss_lab.contracts.fill_model import TRADLATEST_RESEARCH_INTRABAR, FillModelDeclaration
from oss_lab.contracts.presence import Presence
from oss_lab.contracts.trade_record import BenchmarkTradeRecord, Side


# Engine-specific testimony: informative, never comparable across engines, never a
# metric input. Kept out of the contract so the common record stays engine-neutral.
_TL_TESTIMONY_KEYS: tuple[str, ...] = (
    "trade_id",
    "risk_score",          # CRT fusion decision-confidence 0-1 — NOT a risk amount
    "risk_pct",
    "htf_id",
    "state_path",
    "session",
    "day_of_week",
    "hour_of_day",
    "candle_idx",
    "duration_candles",
    "shadow_used",
    "bitnet_score_at_entry",
    "bitnet_decision_at_entry",
    "config_version",
    "closed_at",
    "tp1",
    "tp2",
    # R-valued twins retained as cross-check testimony only (never mapped to money fields)
    "pnl_rr_raw",
    "pnl_rr_net",
)

# Every key the contract mapping above consumes. Anything in the row that is neither
# consumed nor listed as testimony is treated as a canonical feature column and parked
# in the sidecar — this avoids importing CANONICAL_FEATURES and keeps the lab isolated.
_TL_CONSUMED_KEYS: frozenset[str] = frozenset(
    {
        "instrument", "symbol", "timeframe",
        "direction", "side",
        "signal_ts", "signal_time", "timestamp",
        "decision_ts", "decision_time",
        "order_ts", "order_time",
        "fill_ts", "fill_time", "entry_time",
        "entry_requested", "entry", "entry_price",
        "entry_filled", "fill_price",
        "sl", "stop_loss", "sl_price",
        "tp", "take_profit", "tp_price",
        "exit", "exit_price", "close_price",
        "exit_reason", "outcome", "result",
        "quantity", "size", "lots",
        "initial_risk", "risk", "risk_distance", "sl_distance",
        "gross_pnl", "pnl_gross", "pnl_rr_gross",
        "net_pnl", "pnl",
        "fees", "commission",
        "spread_cost", "spread",
        "slippage_cost", "slippage",
        "financing_cost", "swap",
        "other_costs",
        "mfe", "mae", "mfe_r", "mae_r",
        # backtest_v2 trades-CSV native columns consumed by the fallback layer
        "entry_raw", "entry_fill", "exit_fill", "position_size", "opened_at",
        "capital_before", "capital_after",
        "pnl_pips_raw", "pnl_pips_net", "spread_pips", "slippage_pips",
    }
)


class TradelatestBaselineAdapter:
    """Map Tradelatest-native trade dictionaries → BenchmarkTradeRecord."""

    oss_id = "OSS-TRADLATEST-BASELINE"

    def __init__(self) -> None:
        self._dataset: Optional[DatasetManifest] = None

    def capability(self) -> AdapterCapability:
        return AdapterCapability(
            oss_id=self.oss_id,
            can_run_backtest=False,  # runner may shell to backtest_v2 later; not wired yet
            can_emit_trades=True,
            can_emit_signals=False,
            can_emit_orders=False,
            can_emit_fills=False,
            can_measure_latency=False,
            can_run_lookahead_probe=False,
            dependency_installed=True,
            notes=[
                "Normalization only in Phase 3 scaffold.",
                "Full backtest invocation is a later runner phase.",
                "Reuse research.measurement + backtest_v2 for native runs — do not reimplement.",
            ],
        )

    def bind_dataset(self, manifest: DatasetManifest) -> None:
        if manifest.data_hash != XAUUSD_M15_PHASE1_PRIMARY.data_hash:
            # Soft policy for non-primary: allow but require explicit note.
            # Primary mismatch is the common failure mode we care about.
            pass
        path = Path(manifest.physical_path)
        # Do not require file existence at bind time in pure unit tests —
        # runners enforce existence when executing.
        self._dataset = manifest

    def declare_fill_model(self) -> FillModelDeclaration:
        return TRADLATEST_RESEARCH_INTRABAR

    def normalize_trades(
        self,
        native_trades: Sequence[dict[str, Any]],
        *,
        run_id: str,
        instrument: str = "XAUUSD",
        timeframe: str = "M15",
        pip_size: Optional[float] = None,
    ) -> list[BenchmarkTradeRecord]:
        out: list[BenchmarkTradeRecord] = []
        for i, row in enumerate(native_trades):
            rec = self._map_one(
                row,
                run_id=run_id,
                instrument=instrument,
                timeframe=timeframe,
                idx=i,
                pip_size=pip_size,
            )
            out.append(rec)
        return out

    def _map_one(
        self,
        row: dict[str, Any],
        *,
        run_id: str,
        instrument: str,
        timeframe: str,
        idx: int,
        pip_size: Optional[float] = None,
    ) -> BenchmarkTradeRecord:
        """Best-effort mapping of common Tradelatest ledger keys.

        Contract-named keys always win; the backtest_v2 trades-CSV column names are a
        fallback layer applied afterwards (see _apply_native_ledger).

        Supported key aliases (first present wins):
          entry / entry_price / entry_filled
          sl / stop_loss
          tp / take_profit
          exit / exit_price
          direction / side
          pnl / net_pnl
          mfe / mae

        UNIT CONTRACT: unsuffixed money fields (net_pnl, gross_pnl, fees, *_cost,
        initial_risk) are ACCOUNT CURRENCY; only *_r fields are R-multiples
        (trade_record.py "price units unless *_r"). `pnl_rr_net` / `rr_achieved` are
        dimensionless R (backtest_v2.py:1051-1053) and are deliberately NOT accepted as
        `net_pnl` — doing so silently corrupts expectancy_r once initial_risk is present.
        """
        eng = "tradelatest"
        rec = BenchmarkTradeRecord(
            run_id=run_id,
            engine=eng,
            instrument=str(row.get("instrument") or row.get("symbol") or instrument),
            timeframe=str(row.get("timeframe") or timeframe),
        )

        side_raw = str(row.get("direction") or row.get("side") or "").lower()
        if side_raw in ("long", "buy", "1"):
            rec.side = Side.LONG
            rec.mark("side", Presence.PRESENT, native_field="direction|side", source_adapter=eng)
        elif side_raw in ("short", "sell", "-1"):
            rec.side = Side.SHORT
            rec.mark("side", Presence.PRESENT, native_field="direction|side", source_adapter=eng)
        else:
            rec.side = Side.UNKNOWN
            rec.mark(
                "side",
                Presence.UNKNOWN,
                reason="no direction/side field in native row",
                source_adapter=eng,
            )

        def _float(keys: tuple[str, ...]) -> tuple[Optional[float], Optional[str]]:
            for k in keys:
                if k in row and row[k] is not None and row[k] != "":
                    try:
                        return float(row[k]), k
                    except (TypeError, ValueError):
                        continue
            return None, None

        def _str(keys: tuple[str, ...]) -> tuple[Optional[str], Optional[str]]:
            for k in keys:
                if k in row and row[k] is not None and row[k] != "":
                    return str(row[k]), k
            return None, None

        # timestamps
        for field_name, keys in (
            ("signal_ts", ("signal_ts", "signal_time", "timestamp")),
            ("decision_ts", ("decision_ts", "decision_time")),
            ("order_ts", ("order_ts", "order_time")),
            ("fill_ts", ("fill_ts", "fill_time", "entry_time")),
        ):
            val, native = _str(keys)
            setattr(rec, field_name, val)
            if val is not None:
                rec.mark(field_name, Presence.PRESENT, native_field=native, source_adapter=eng)
            else:
                rec.mark(
                    field_name,
                    Presence.NOT_AVAILABLE,
                    reason=f"none of {keys} present",
                    source_adapter=eng,
                )

        # prices
        for field_name, keys in (
            ("entry_requested", ("entry_requested", "entry", "entry_price")),
            ("entry_filled", ("entry_filled", "fill_price", "entry", "entry_price")),
            ("sl", ("sl", "stop_loss", "sl_price")),
            ("tp", ("tp", "take_profit", "tp_price")),
            ("exit", ("exit", "exit_price", "close_price")),
        ):
            val, native = _float(keys)
            setattr(rec, field_name, val)
            if val is not None:
                rec.mark(field_name, Presence.PRESENT, native_field=native, source_adapter=eng)
            else:
                rec.mark(
                    field_name,
                    Presence.NOT_AVAILABLE,
                    reason=f"none of {keys} present",
                    source_adapter=eng,
                )

        er, ern = _str(("exit_reason", "outcome", "result"))
        rec.exit_reason = er
        if er is not None:
            rec.mark("exit_reason", Presence.PRESENT, native_field=ern, source_adapter=eng)
        else:
            rec.mark("exit_reason", Presence.NOT_AVAILABLE, reason="no exit_reason", source_adapter=eng)

        # quantity / risk
        for field_name, keys in (
            ("quantity", ("quantity", "size", "lots")),
            ("initial_risk", ("initial_risk", "risk", "risk_distance", "sl_distance")),
        ):
            val, native = _float(keys)
            setattr(rec, field_name, val)
            if val is not None:
                rec.mark(field_name, Presence.PRESENT, native_field=native, source_adapter=eng)
            else:
                rec.mark(
                    field_name,
                    Presence.NOT_AVAILABLE,
                    reason=f"none of {keys} present",
                    source_adapter=eng,
                )

        # pnl family
        for field_name, keys in (
            ("gross_pnl", ("gross_pnl", "pnl_gross", "pnl_rr_gross")),
            # R-valued keys (pnl_rr_net / rr_achieved) are NOT accepted here — see docstring.
            ("net_pnl", ("net_pnl", "pnl")),
            ("fees", ("fees", "commission")),
            ("spread_cost", ("spread_cost", "spread")),
            ("slippage_cost", ("slippage_cost", "slippage")),
            ("financing_cost", ("financing_cost", "swap")),
            ("other_costs", ("other_costs",)),
        ):
            val, native = _float(keys)
            setattr(rec, field_name, val)
            if val is not None:
                rec.mark(field_name, Presence.PRESENT, native_field=native, source_adapter=eng)
            else:
                rec.mark(
                    field_name,
                    Presence.NOT_AVAILABLE,
                    reason=f"none of {keys} present",
                    source_adapter=eng,
                )

        # mfe/mae
        for field_name, keys in (
            ("mfe", ("mfe",)),
            ("mae", ("mae",)),
            ("mfe_r", ("mfe_r",)),
            ("mae_r", ("mae_r",)),
        ):
            val, native = _float(keys)
            setattr(rec, field_name, val)
            if val is not None:
                rec.mark(field_name, Presence.PRESENT, native_field=native, source_adapter=eng)
            else:
                rec.mark(
                    field_name,
                    Presence.NOT_AVAILABLE,
                    reason=f"none of {keys} present — recompute via forward_walk if needed",
                    source_adapter=eng,
                )

        # latency — never invent; mark NOT_AVAILABLE for offline ledgers
        for field_name in ("decision_latency", "order_latency", "fill_latency"):
            rec.mark(
                field_name,
                Presence.NOT_APPLICABLE,
                reason="offline ledger has no wall-clock latency clock",
                source_adapter=eng,
            )

        # ── backtest_v2 trades-CSV fallback (TradeJournal.to_csv_rows, :1102-1172) ──
        # Fills ONLY fields still unset above; contract-named keys always win. Column
        # names here are the producer's, and every value written is re-marked with its
        # real provenance (derivations say so — never presented as natively emitted).

        def _fill(field_name: str, keys: tuple[str, ...], reason: str) -> Optional[float]:
            existing = getattr(rec, field_name, None)
            if existing is not None:
                return existing
            val, native = _float(keys)
            if val is None:
                return None
            setattr(rec, field_name, val)
            rec.mark(
                field_name, Presence.PRESENT,
                reason=reason, native_field=native, source_adapter=eng,
            )
            return val

        _fill("entry_requested", ("entry_raw",), "pre-slippage requested entry")
        entry_filled = _fill("entry_filled", ("entry_fill",), "slippage-adjusted entry fill")
        _fill("exit", ("exit_fill",), "slippage-adjusted exit fill")
        quantity = _fill("quantity", ("position_size",), "base-currency units (backtest_v2:983)")

        # opened_at IS the fill bar: the entry fill is computed on that same candle
        # (backtest_v2.py:960, :994-995). There is no separate signal/decision/order
        # clock in this backtest, so those three stay NOT_AVAILABLE.
        if rec.fill_ts is None:
            _ts, _native = _str(("opened_at",))
            if _ts is not None:
                rec.fill_ts = _ts
                rec.mark(
                    "fill_ts", Presence.PRESENT,
                    reason="opened_at is the fill bar (backtest_v2.py:960,:994-995)",
                    native_field=_native, source_adapter=eng,
                )

        # net_pnl in ACCOUNT CURRENCY, from the producer's own realized bookkeeping
        # (CapitalCurve.apply_trade, backtest_v2.py:421-427). Never pnl_rr_net (R).
        if rec.net_pnl is None:
            _cap_b, _ = _float(("capital_before",))
            _cap_a, _ = _float(("capital_after",))
            if _cap_b is not None and _cap_a is not None:
                rec.net_pnl = _cap_a - _cap_b
                rec.mark(
                    "net_pnl", Presence.PRESENT,
                    reason=(
                        "derived:capital_after - capital_before (account currency); "
                        "precision bounded by producer 2dp rounding"
                    ),
                    native_field="capital_after|capital_before", source_adapter=eng,
                )

        # tp: the source carries a sequential TP LADDER (tp1 -> tp2; a TP2 exit also
        # counts as a TP1 hit, backtest_v2.py:1335). A single scalar cannot represent
        # it, and picking either leg would manufacture a false single-target record.
        if rec.tp is None and any(
            k in row and row[k] not in (None, "") for k in ("tp1", "tp2")
        ):
            rec.mark(
                "tp", Presence.NOT_APPLICABLE,
                reason=(
                    "source has an applicable multi-leg TP ladder (tp1->tp2) that this "
                    "single-scalar contract field cannot represent"
                ),
                native_field="tp1|tp2", source_adapter=eng,
            )

        # initial_risk in ACCOUNT CURRENCY, matching net_pnl's unit. MUST NOT come from
        # `risk_score` — that is CRT fusion decision-confidence, 0-1 (backtest_v2:2240-2241).
        if (
            rec.initial_risk is None
            and entry_filled is not None
            and rec.sl is not None
            and quantity is not None
        ):
            rec.initial_risk = abs(entry_filled - rec.sl) * quantity
            rec.mark(
                "initial_risk", Presence.PRESENT,
                reason=(
                    "deterministically derived from available artifact fields; precision "
                    "bounded by the producer's CSV rounding (position_size 2dp)"
                ),
                native_field="derived:|entry_fill - sl| * position_size",
                source_adapter=eng,
            )

        # Cost decomposition in money units. pip_size is not a CSV column: prefer the
        # caller's value, else infer from the rounded pip columns and say so.
        _ps, _ps_note = pip_size, "caller-supplied pip_size"
        if _ps is None:
            _pips_net, _ = _float(("pnl_pips_net",))
            if entry_filled is not None and rec.exit is not None and _pips_net:
                _ps = abs(rec.exit - entry_filled) / abs(_pips_net)
                _ps_note = "pip_size inferred from rounded pnl_pips_net (1dp) — coarser"
        if _ps is not None and quantity is not None:
            for _fname, _key, _sign in (
                ("gross_pnl", "pnl_pips_raw", "signed, pre-cost"),
                ("spread_cost", "spread_pips", "positive magnitude"),
                ("slippage_cost", "slippage_pips", "positive magnitude"),
            ):
                if getattr(rec, _fname) is not None:
                    continue
                _pips, _native = _float((_key,))
                if _pips is None:
                    continue
                setattr(rec, _fname, _pips * _ps * quantity)
                rec.mark(
                    _fname, Presence.PRESENT,
                    reason=(
                        f"derived:{_key} * pip_size * position_size ({_sign}); {_ps_note}"
                    ),
                    native_field=_native, source_adapter=eng,
                )

        # ── Testimony sidecar — engine-specific, NEVER a metric input ────────────
        # adapter_meta is documented non-metric (trade_record.py:121-122) and
        # canonical.py never reads it. CRT decision-confidence, state path and the
        # canonical feature columns live here, not in the comparable contract.
        rec.adapter_meta = {"native_index": idx, "native_keys": sorted(row.keys())}
        _tl = {
            k: row[k]
            for k in _TL_TESTIMONY_KEYS
            if k in row and row[k] not in (None, "")
        }
        _leftover = {
            k: v
            for k, v in row.items()
            if k not in _TL_CONSUMED_KEYS and k not in _TL_TESTIMONY_KEYS
        }
        if _leftover:
            _tl["feature_columns"] = _leftover
        if _tl:
            rec.adapter_meta["tradelatest"] = _tl
        return rec
