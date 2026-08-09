"""Full CRTEngine state machine on sequential candles (not fusion crt_score)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from config_layer.config_builder import ConfigBuilder
from config_layer.crt_engine_v2 import CRTEngine, Candle
from research.model_runners.contracts import ModelContract
from research.model_runners.require_config import require_key, require_section
from research.model_runners.substrate import BarContext


class CrtStateMachineAdapter:
    """Stateful adapter: must score bars in chronological order only."""

    def __init__(
        self,
        *,
        contract: ModelContract,
        prod_config: dict[str, Any],
        instrument: str,
        ohlcv_csv: Path,
        emit: str,
    ):
        self.contract = contract
        if emit not in ("events", "all"):
            raise ValueError("--emit must be 'events' or 'all' for crt_state_machine")
        self._emit = emit

        # Load CRTConfig from production overrides (avoid bare ConfigBuilder.build()).
        require_section(prod_config, "crt_engine")
        require_section(prod_config, "params")
        # ConfigBuilder.from_existing or build with instrument + prod overrides.
        # Use get_prod_config path via production_config if available.
        from config_layer.production_config import load_prod_config_from_registry
        from config_layer.production_config import get_active_version

        version = get_active_version()
        # Prefer explicit version matching loaded JSON if stamped.
        if "version" in prod_config:
            version = str(prod_config["version"])
        crt_cfg = load_prod_config_from_registry(version, instrument)
        self._engine = CRTEngine(crt_cfg)

        # Seed range from first N candles of the CSV (engine requires initialise_range).
        df = pd.read_csv(ohlcv_csv)
        cols = {c.lower(): c for c in df.columns}
        # minimal normalize
        rename = {}
        for want in ("timestamp", "open", "high", "low", "close", "volume"):
            if want in cols:
                rename[cols[want]] = want
        df = df.rename(columns=rename)
        if "timestamp" not in df.columns:
            raise ValueError("crt_state_machine seed CSV missing timestamp")
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # R3: seed width is config-driven, not a magic number (§6.5 — behavioural
        # constants live in config). Strict read; no default.
        mr = require_section(prod_config, "model_runners")
        csm = require_key(mr, "crt_state_machine", path="model_runners")
        if not isinstance(csm, dict):
            raise KeyError(
                "model_runners.crt_state_machine must be a mapping, "
                f"got {type(csm).__name__}"
            )
        seed_n = int(require_key(csm, "seed_bars", path="model_runners.crt_state_machine"))
        if seed_n < 1:
            raise ValueError(
                f"model_runners.crt_state_machine.seed_bars must be >= 1, got {seed_n}"
            )
        if len(df) < seed_n + 10:
            raise RuntimeError(
                f"crt_state_machine needs >= {seed_n + 10} candles, have {len(df)}"
            )
        candles: list[Candle] = []
        for i, row in df.iloc[:seed_n].iterrows():
            candles.append(
                Candle(
                    timestamp=pd.Timestamp(row["timestamp"]).to_pydatetime(),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                    index=int(i),
                )
            )
        self._engine.initialise_range(candles, htf_candle_id="offline", session="LONDON")
        self._bar_i = seed_n
        self._seed_n = seed_n

        self.config_sections_read = ["crt_engine", "params", "model_runners"]
        self.config_keys_read = [
            "crt_engine.* via load_prod_config_from_registry",
            "model_runners.crt_state_machine.seed_bars",
        ]
        self.artifact_info = {
            "path": None,
            "seed_bars": seed_n,
            "emit": emit,
            "instrument": instrument,
            "config_version": version,
        }
        # R4: the former timestamp->row index (a SECOND full parse of the same CSV
        # the runner's substrate already loaded) is removed. Ingestion order is the
        # adapter's own contract (chronological, enforced below), so the engine's
        # own monotonic counter is the single index authority — matching
        # process_candle()'s "[PATCH 4] Auto-assign candle index" behaviour.
        self._last_ts: str | None = None

    def score_bar(self, bar: BarContext) -> dict[str, Any]:
        o = bar.ohlcv
        ts = bar.timestamp
        # Chronological order is a hard precondition: process_candle() mutates
        # persistent engine state, so an out-of-order bar silently corrupts the
        # FSM trajectory. Fail loudly instead.
        if self._last_ts is not None and ts < self._last_ts:
            raise RuntimeError(
                f"crt_state_machine requires chronological bars: {ts} < {self._last_ts}"
            )
        self._last_ts = ts
        # process_candle() re-stamps index from its own monotonic counter, so the
        # value passed here is positional only.
        idx = bar.bar_index + self._seed_n
        candle = Candle(
            timestamp=pd.Timestamp(ts).to_pydatetime(),
            open=float(o["open"]),
            high=float(o["high"]),
            low=float(o["low"]),
            close=float(o["close"]),
            volume=float(o["volume"]),
            index=idx,
        )
        result = self._engine.process_candle(candle, htf_candle_id="offline")
        if not isinstance(result, dict):
            raise TypeError(f"process_candle must return dict, got {type(result)}")
        if "action" not in result:
            raise KeyError("CRTEngine.process_candle result missing 'action'")
        action = str(result["action"])
        state_val = result["state"] if "state" in result else None
        if self._emit == "events" and action in ("NONE", "", "none"):
            return {
                "score": 0.0,
                "action": action,
                "state": state_val,
                "emitted": False,
                "native_keys": list(result.keys()),
            }
        out = dict(result)
        out["emitted"] = True
        for k, v in list(out.items()):
            if hasattr(v, "value") and not isinstance(v, (str, int, float, bool)):
                out[k] = str(v.value)
            elif not isinstance(v, (str, int, float, bool, list, dict, type(None))):
                out[k] = str(v)
        if "score" not in out:
            out["score"] = 1.0 if action not in ("NONE", "", "none") else 0.0
        return out
