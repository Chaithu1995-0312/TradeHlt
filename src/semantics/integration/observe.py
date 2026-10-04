"""Observe the REAL backtest on a corpus, bar by bar, without editing the engine.

`runtime.backtest_v2.main` is run exactly as the CLI runs it. The only intervention is that the
engine it constructs gets an instance-level wrapper around `process_candle` which calls the real
method and then copies read-only facts out of `engine.state`; and `BacktestRunner.__init__` is
wrapped only to remember the runner, whose own feature frame is read afterwards
(`export_features`). Nothing is written back.

Faithfulness is not assumed: `replay_gate` compares the observed run's event stream with a plain,
unwrapped run of the same command. Any difference is REPLAY_NOT_FAITHFUL and no verdict may be drawn.
The gate is a run-identity check, not a meaning oracle (decision O-1).
"""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
MONTH_SLICE = ROOT / "data" / "mt5" / "XAUUSD_W2026-07-06-to-2026-08-07.csv"
_GATE_FIELDS = ("candle_index", "event", "state_to", "reason")


def _num(value: Any) -> Any:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else value


def _candle(c: Any) -> Optional[dict]:
    if c is None:
        return None
    return {"index": int(getattr(c, "index", 0)), "timestamp": str(getattr(c, "timestamp", "")),
            "open": float(c.open), "high": float(c.high), "low": float(c.low), "close": float(c.close)}


def _trade(t: Any) -> Optional[dict]:
    if t is None:
        return None
    names = ("id", "entry_price", "sl_price", "tp1_price", "tp2_price", "status", "pnl", "partial_pnl",
             "open_candle_index", "displacement_origin", "risk_pct")
    out = {n: _num(getattr(t, n, None)) for n in names}
    out["direction"] = getattr(getattr(t, "direction", None), "value", None)
    out["opened_at"] = str(getattr(t, "opened_at", None))
    out["closed_at"] = str(getattr(t, "closed_at", None))
    return out


def state_facts(state: Any) -> dict:
    """Read-only copy of the engine facts the comparators need (reuses snapshot_engine_state)."""
    from runtime.crt_baseline_trace import snapshot_engine_state

    facts = snapshot_engine_state(state)
    se = getattr(state, "sweep_event", None)
    facts["sweep_candle"] = _candle(getattr(se, "candle", None)) if se is not None else None
    facts["displacement_candle"] = _candle(getattr(state, "displacement_candle", None))
    facts["trade"] = _trade(getattr(state, "active_trade", None))
    ar = getattr(state, "active_range", None)
    facts["range_clock_id"] = getattr(ar, "clock_id", None) if ar is not None else None
    return facts


TS_FORMAT = "%Y-%m-%d %H:%M:%S"   # the key format of BacktestRunner.feature_ts_to_idx


def ts_key(value: Any) -> str:
    import pandas as pd

    return pd.to_datetime(str(value)).strftime(TS_FORMAT)


@dataclass
class Observation:
    run_dir: Path
    bars: list = field(default_factory=list)       # one dict per process_candle call
    events: list = field(default_factory=list)     # the run's own events.jsonl rows
    features: Optional[dict] = None                # ts -> {slot name: value}, the run's own frame
    history: Optional[dict] = None                 # full-corpus float64 OHLC + ts keys (C7)

    @property
    def events_path(self) -> Path:
        return next(self.run_dir.glob("*_events.jsonl"))


def read_history(csv: Path, instrument: str) -> dict:
    """Full-corpus OHLC as float64, admitted and read the way BacktestRunner does
    (backtest_v2.py:2623, :2671-2681), so causal swings see the same pre-warmup history the
    feature pipeline saw."""
    import pandas as pd

    from data_ingestion.dataset_registry import admit_csv_path

    path = admit_csv_path(str(csv), instrument).filepath
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    if "timestamp" not in df.columns:
        df["timestamp"] = (df["date"].astype(str) + " " + df["time"].astype(str)
                           if "time" in df.columns else df["date"])
    out = {"timestamp": list(pd.to_datetime(df["timestamp"]).dt.strftime(TS_FORMAT))}
    for col in ("open", "high", "low", "close"):
        out[col] = df[col].to_numpy(dtype=float)
    return out


def runner_features(runner: Any, wanted: set) -> dict:
    """The run's own canonical vectors (read-only), keyed by timestamp, for the wanted timestamps."""
    from features.feature_schema import CANONICAL_FEATURES

    vectors, ts_to_idx = runner.export_features()[:2]
    return {ts: dict(zip(CANONICAL_FEATURES, (float(v) for v in vectors[i])))
            for ts, i in ts_to_idx.items() if ts in wanted}


class _Recorder:
    def __init__(self) -> None:
        self.bars: list = []
        self.engines: list = []
        self.runners: list = []

    def wrap(self, engine: Any) -> Any:
        real = engine.process_candle
        recorder = self

        def observed(candle, htf_candle_id, *args, **kwargs):
            before = state_facts(engine.state)
            events_before = len(engine.state.event_log)
            result = real(candle, htf_candle_id, *args, **kwargs)
            recorder.bars.append({
                "bar": int(engine.state.current_candle_index),
                "candle": _candle(candle),
                "htf_candle_id": str(htf_candle_id),
                "before": before,
                "after": state_facts(engine.state),
                "action": {k: _num(v) for k, v in (result or {}).items() if isinstance(v, (str, int, float, bool, type(None)))},
                "events": [e.to_dict() if hasattr(e, "to_dict") else e
                           for e in engine.state.event_log[events_before:]],
            })
            return result

        engine.process_candle = observed   # instance attribute; the class is untouched
        self.engines.append(engine)
        return engine


@contextmanager
def prod_version(version: Optional[str]):
    """Run under a non-active config version (e.g. a shadow), the way crt_overlay /
    crt_occupancy_lib do: patch the module-global PROD_VERSION in BOTH modules that read it,
    restore in `finally`. `None` = the ACTIVE_VERSION, unchanged."""
    if version is None:
        yield
        return
    import config_layer.production_config as _pc
    from runtime import backtest_v2 as _bt

    _pc.get_full_config_dict(version)          # fail fast if the version file does not exist
    prev = (_pc.PROD_VERSION, _bt.PROD_VERSION)
    _pc.PROD_VERSION = _bt.PROD_VERSION = version
    try:
        yield
    finally:
        _pc.PROD_VERSION, _bt.PROD_VERSION = prev


def _newest_run_dir(output: Path) -> Path:
    runs = sorted((p for p in output.iterdir() if p.is_dir() and p.name.startswith("run_")),
                  key=lambda p: p.stat().st_mtime)
    if not runs:
        raise FileNotFoundError(f"no run_* directory written under {output}")
    return runs[-1]


def _run_backtest(csv: Path, output: Path, instrument: str, recorder: Optional[_Recorder]) -> Path:
    from runtime import backtest_v2

    output.mkdir(parents=True, exist_ok=True)
    argv = ["backtest_v2", "--csv", str(csv), "--instrument", instrument, "--output", str(output)]
    with mock.patch.object(sys, "argv", argv):
        if recorder is None:
            backtest_v2.main()
        else:
            real_cls = backtest_v2.CRTEngine
            real_init = backtest_v2.BacktestRunner.__init__

            def factory(*a, **kw):
                return recorder.wrap(real_cls(*a, **kw))

            def runner_init(self, *a, **kw):   # the real __init__, then remember the instance
                real_init(self, *a, **kw)
                recorder.runners.append(self)

            with mock.patch.object(backtest_v2, "CRTEngine", factory), \
                    mock.patch.object(backtest_v2.BacktestRunner, "__init__", runner_init):
                backtest_v2.main()
    return _newest_run_dir(output)


def read_events(run_dir: Path) -> list:
    path = next(run_dir.glob("*_events.jsonl"))
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def observe_backtest(csv: Path, output: Path, *, instrument: str = "XAUUSD") -> Observation:
    recorder = _Recorder()
    run_dir = _run_backtest(Path(csv), Path(output) / "observed", instrument, recorder)
    if len(recorder.engines) != 1:
        raise RuntimeError(f"expected one engine, the backtest built {len(recorder.engines)}")
    if len(recorder.runners) != 1:
        raise RuntimeError(f"expected one BacktestRunner, the backtest built {len(recorder.runners)}")
    runner = recorder.runners[0]
    wanted = {ts_key(b["candle"]["timestamp"]) for b in recorder.bars if b.get("candle")}
    return Observation(run_dir, recorder.bars, read_events(run_dir),
                       features=runner_features(runner, wanted),
                       history=read_history(Path(runner.csv_path), instrument))


def plain_backtest(csv: Path, output: Path, *, instrument: str = "XAUUSD") -> Path:
    return _run_backtest(Path(csv), Path(output) / "plain", instrument, None)


def gate_key(row: dict) -> tuple:
    return tuple(row.get(f) for f in _GATE_FIELDS)


def replay_gate(observed_events: list, plain_events: list) -> dict:
    """PASS iff the observed run emitted exactly the plain run's event stream (on _GATE_FIELDS)."""
    a = [gate_key(r) for r in observed_events]
    b = [gate_key(r) for r in plain_events]
    if a == b:
        return {"status": "PASS", "events": len(a)}
    first = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    return {"status": "REPLAY_NOT_FAITHFUL", "observed": len(a), "plain": len(b), "first_difference": first,
            "observed_row": a[first] if first < len(a) else None, "plain_row": b[first] if first < len(b) else None}
