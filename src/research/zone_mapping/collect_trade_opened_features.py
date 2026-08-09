"""
Collect TRADE_OPENED-shaped feature dicts from a real XAUUSD CRT path.

Research-only helper for P1a.5 corpus parity. Does not run EngineRunner.
Builds the same feature map shape BacktestRunner builds at TRADE_OPENED
(CANONICAL_FEATURES + OHLCV setdefault + direction).
"""
from __future__ import annotations

from dataclasses import dataclass, fields, replace
from datetime import datetime, time as dt_time
from typing import Any, Optional

import pandas as pd

from config_layer.config_builder import ConfigBuilder
from config_layer.crt_engine_v2 import CRTEngine, Candle
from features.feature_pipeline import FeaturePipeline
from features.feature_schema import CANONICAL_FEATURES
from runtime.backtest_v2 import HTFBuilder


@dataclass(frozen=True)
class TradeOpenedFeatureSample:
    timestamp: str
    candle_index: int
    features: dict[str, Any]
    direction: Optional[int]


def _parse_hhmm(value: Any) -> dt_time:
    """Coerce 'HH:MM' / 'HH:MM:SS' / datetime.time → datetime.time."""
    if isinstance(value, dt_time):
        return value
    if isinstance(value, str):
        parts = value.strip().split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        s = int(parts[2]) if len(parts) > 2 else 0
        return dt_time(h, m, s)
    raise TypeError(f"session bound must be str or datetime.time, got {type(value)!r}")


def _normalize_session_windows(windows: dict) -> dict:
    """
    Ensure session_windows values are (datetime.time, datetime.time).

    Prevents CRT score_time / off_session filter crash:
      TypeError: '<=' not supported between instances of 'str' and 'datetime.time'
    when JSON-shaped string bounds leak into CRTConfig.
    """
    out: dict = {}
    for name, bounds in (windows or {}).items():
        if isinstance(bounds, (list, tuple)) and len(bounds) >= 2:
            out[str(name)] = (_parse_hhmm(bounds[0]), _parse_hhmm(bounds[1]))
        else:
            raise ValueError(f"session_windows[{name!r}] must be a (start, end) pair, got {bounds!r}")
    return out


def _harden_crt_config(cfg):
    """Return CRTConfig with normalized session_windows (and uppercase allowed_sessions)."""
    sw = _normalize_session_windows(dict(cfg.session_windows))
    allowed = tuple(str(s).upper() for s in (cfg.allowed_sessions or ()))
    return replace(cfg, session_windows=sw, allowed_sessions=allowed)


def _crt_config_from_prod(instrument: str = "XAUUSD"):
    """Build CRTConfig with production scalar detection knobs from ``params`` only.

    Does NOT bulk-apply ``crt_engine`` JSON — session_windows / weight tuples from raw
    JSON can leave string times and break ``start <= t <= end`` comparisons.
    """
    from config_layer.crt_engine_v2 import CRTConfig
    from config_layer.production_config import get_prod_section

    crt_field_names = {f.name for f in fields(CRTConfig)}
    overrides: dict[str, Any] = {}
    try:
        params = get_prod_section("params")
    except Exception:
        params = {}
    if isinstance(params, dict):
        for k, v in params.items():
            if k in crt_field_names and isinstance(v, (int, float)) and not isinstance(v, bool):
                overrides[k] = v
    base = ConfigBuilder.build(instrument, overrides=overrides or None)
    return _harden_crt_config(base)


def collect_xauusd_trade_opened_features(
    *,
    csv_path: str = "data/mt5/XAUUSD_M15.csv",
    tail_rows: int = 0,
    max_samples: int = 25,
    warmup_candles: int = 50,
    htf_candles_per_range: int = 96,
    use_prod_crt_config: bool = False,
) -> list[TradeOpenedFeatureSample]:
    """
    Stream the Phase-1 XAUUSD corpus through FeaturePipeline + CRTEngine.

    Parameters
    ----------
    tail_rows
        If > 0, only the last N CSV rows are used. 0 = full Phase-1 file.
    use_prod_crt_config
        When True, overlay production ``params`` scalars (stricter gates; often
        fewer TRADE_OPENED). Default False = market-router CRTConfig (enough
        opens on Phase-1 for parity sampling). Session windows always hardened.

    Returns up to ``max_samples`` TRADE_OPENED feature snapshots (ts-aligned).
    """
    from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path

    guarded = str(guard_xauusd_csv_path(csv_path, "XAUUSD"))
    raw = pd.read_csv(guarded)
    raw.columns = [c.strip().lower() for c in raw.columns]
    if "timestamp" not in raw.columns:
        if "date" in raw.columns and "time" in raw.columns:
            raw["timestamp"] = raw["date"].astype(str) + " " + raw["time"].astype(str)
        elif "date" in raw.columns:
            raw["timestamp"] = raw["date"]
        else:
            raise ValueError(f"No timestamp/date columns in {guarded}")

    if tail_rows > 0 and len(raw) > tail_rows:
        raw = raw.tail(int(tail_rows)).reset_index(drop=True)
    else:
        raw = raw.reset_index(drop=True)

    pipeline = FeaturePipeline(raw)
    enriched, feature_vectors = pipeline.run()
    ts_series = pd.to_datetime(enriched["timestamp"])
    ts_to_idx = {
        ts_series.iloc[i].strftime("%Y-%m-%d %H:%M:%S"): i
        for i in range(len(ts_series))
    }

    candles: list[Candle] = []
    for _, row in raw.iterrows():
        ts = pd.to_datetime(row["timestamp"]).to_pydatetime()
        if getattr(ts, "tzinfo", None) is not None:
            ts = ts.replace(tzinfo=None)
        if not isinstance(ts, datetime):
            ts = datetime.fromisoformat(str(ts))
        candles.append(
            Candle(
                timestamp=ts,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]) if "volume" in row and pd.notna(row["volume"]) else 0.0,
            )
        )

    if use_prod_crt_config:
        crt_cfg = _crt_config_from_prod("XAUUSD")
    else:
        crt_cfg = _harden_crt_config(ConfigBuilder.build("XAUUSD"))

    engine = CRTEngine(crt_cfg)
    htf = HTFBuilder(htf_candles_per_range, "XAUUSD")

    samples: list[TradeOpenedFeatureSample] = []
    initialised = False
    candle_idx = 0
    prev_htf_id = ""
    htf_remaining = htf_candles_per_range

    for candle in candles:
        candle_idx += 1
        htf.push(candle)
        if htf.current_htf_id != prev_htf_id:
            prev_htf_id = htf.current_htf_id
            htf_remaining = htf_candles_per_range - 1
        else:
            htf_remaining = max(0, htf_remaining - 1)
        engine.state.htf_remaining_candles = htf_remaining

        if candle_idx < warmup_candles:
            continue

        if not initialised:
            seed = htf.seed_candles()
            if seed:
                engine.initialise_range(seed, htf.current_htf_id, "OFF_SESSION")
                initialised = True
            continue

        result = engine.process_candle(candle, htf.current_htf_id)
        action = str(result.get("action", "NONE"))
        if "TRADE_OPENED" not in action or engine.state.active_trade is None:
            continue

        ts_key = candle.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        fv_idx = ts_to_idx.get(ts_key, -1)
        if fv_idx < 0:
            continue

        vec = feature_vectors[fv_idx]
        if hasattr(vec, "tolist"):
            vec = vec.tolist()
        feat_map = {name: float(vec[i]) for i, name in enumerate(CANONICAL_FEATURES)}
        feat_map.setdefault("close", candle.close)
        feat_map.setdefault("high", candle.high)
        feat_map.setdefault("low", candle.low)
        feat_map.setdefault("open", candle.open)
        feat_map.setdefault("volume", candle.volume)
        feat_map.setdefault("timestamp", ts_key)
        feat_map["_data_integrity"] = "real"

        direction = None
        crt_dir = engine.state.direction
        if crt_dir is not None:
            try:
                direction = int(getattr(crt_dir, "value", crt_dir))
                feat_map["direction"] = direction
                feat_map["signal_dir"] = direction
                feat_map["trade_direction"] = direction
            except Exception:
                direction = None

        samples.append(
            TradeOpenedFeatureSample(
                timestamp=ts_key,
                candle_index=candle_idx,
                features=feat_map,
                direction=direction,
            )
        )
        if len(samples) >= max_samples:
            break

    return samples
