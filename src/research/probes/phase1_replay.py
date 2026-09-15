"""Phase-1 resolver replay helpers shared by evidence + sample_acquisition CLIs."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from config_layer.crt_engine_v2 import StateMachine
from config_layer.production_config import PROD_VERSION, load_prod_config_from_registry
from research.costs import ComponentCostModel
from research.probes.costs_path import net_r as net_r_timeout
from research.probes.scoreboard import profit_factor, scoreboard_row
from runtime.backtest_v2 import BacktestConfig, BacktestRunner, CandleLoader, MultiInstrumentRunner

HORIZON = 20


STRIDE = 20


PF_CAP = 9999.0


MIN_N_LABEL = 30


CASES_RUBRIC = {
    "A": (
        "Memory expectancy > Always-Long AND TrendBias expectancy <= Always-Long "
        "→ pending_displacement_dir carries directional information beyond drift on this object; "
        "trend_bias does not."
    ),
    "B": (
        "TrendBias expectancy > Always-Long AND Memory expectancy <= Always-Long "
        "→ trend_bias carries the signal on this object; memory direction is not load-bearing."
    ),
    "C": (
        "Both Memory and TrendBias expectancy > Always-Long "
        "→ both arms informative vs drift on this object (agreement is diagnostic only, not an objective)."
    ),
    "D": (
        "Neither Memory nor TrendBias expectancy > Always-Long "
        "→ null on this ENTRY/H20/SEM-015 TIMEOUT object; no Case promotes."
    ),
}


class _Capture:
    collapses: list = []
    replayed_states: list = []
    creates: list = []
    open_create: dict | None = None
    shadow_entries_without_open_create: int = 0


def _dir_to_long_short(d: Any) -> Optional[str]:
    if d is None:
        return None
    name = d.name if hasattr(d, "name") else str(d)
    name = name.upper()
    if name in ("LONG", "1", "+1"):
        return "LONG"
    if name in ("SHORT", "-1"):
        return "SHORT"
    return None


def _tb_to_long_short(tb: Any) -> Optional[str]:
    try:
        v = float(tb)
    except (TypeError, ValueError):
        return None
    if math.isnan(v):
        return None
    if v > 0:
        return "LONG"
    if v < 0:
        return "SHORT"
    return None


def _install_collapse_capture():
    """Capture pending_displacement_dir at ENGINE SHADOW→EXP collapse.

    Kept for sample_acquisition.py. This is NOT the frozen four-arm resolver object.
    """
    orig = StateMachine.try_shadow_pending_to_expansion

    def patched(self, state, candle, ev_logger=None):
        pending_dir = state.pending_displacement_dir
        pending_formed = state.pending_displacement_formed_idx
        pending_src = state.pending_displacement_source_htf
        atr_abs = getattr(state, "atr_abs", None)
        ok = orig(self, state, candle, ev_logger)
        if ok:
            _Capture.collapses.append(
                {
                    "candle_index": int(candle.index),
                    "timestamp": str(getattr(candle, "timestamp", "")),
                    "pending_displacement_dir": (
                        pending_dir.name if pending_dir is not None else "NONE"
                    ),
                    "pending_displacement_formed_idx": pending_formed,
                    "pending_displacement_source_htf": pending_src or None,
                    "atr_abs": float(atr_abs) if atr_abs else None,
                    "action": "SHADOW_EXPANSION_CONFIRMED",
                }
            )
        return ok

    StateMachine.try_shadow_pending_to_expansion = patched

    def restore():
        StateMachine.try_shadow_pending_to_expansion = orig

    return restore


def _load_trend_bias_by_ts(bar_matrix_path: Path):
    import pyarrow.parquet as pq

    if not bar_matrix_path.is_file():
        raise FileNotFoundError(
            f"Phase-1 trend_bias source missing: {bar_matrix_path} "
            "(required for Resolver-TrendBias; do not invent substitutes)"
        )
    table = pq.read_table(bar_matrix_path, columns=["timestamp", "trend_bias", "atr_abs"])
    out: dict[str, float] = {}
    atr_by_ts: dict[str, float] = {}
    for row in table.to_pylist():
        ts = row["timestamp"]
        if hasattr(ts, "strftime"):
            key = ts.strftime("%Y-%m-%d %H:%M:%S")
        else:
            key = str(ts).replace("T", " ").split(".")[0]
        out[key] = float(row["trend_bias"]) if row["trend_bias"] is not None else 0.0
        if row.get("atr_abs"):
            atr_by_ts[key] = float(row["atr_abs"])
    return out, atr_by_ts


def _normalize_ts(ts: str) -> str:
    s = str(ts).replace("T", " ").strip()
    if "." in s:
        s = s.split(".")[0]
    if "+" in s:
        s = s.split("+")[0].strip()
    if s.endswith("Z"):
        s = s[:-1].strip()
    return s


def _call_case(mem: dict, tb: dict, al: dict) -> dict:
    """Cases A–D on expectancy only (standing contract). None expectancy → treat as not > control."""
    e_m = mem.get("expectancy")
    e_t = tb.get("expectancy")
    e_c = al.get("expectancy")
    if e_c is None:
        return {
            "case": "D",
            "reason": "Always-Long expectancy unavailable; cannot adjudicate A–C → Case D by null-control rule.",
            "rubric": CASES_RUBRIC["D"],
        }
    mem_beats = e_m is not None and e_m > e_c
    tb_beats = e_t is not None and e_t > e_c
    if mem_beats and not tb_beats:
        case = "A"
    elif tb_beats and not mem_beats:
        case = "B"
    elif mem_beats and tb_beats:
        case = "C"
    else:
        case = "D"
    return {
        "case": case,
        "memory_expectancy": e_m,
        "trendbias_expectancy": e_t,
        "always_long_expectancy": e_c,
        "memory_beats_control": mem_beats,
        "trendbias_beats_control": tb_beats,
        "rubric": CASES_RUBRIC[case],
        "note": (
            "Case call is interpretive only on this frozen object. "
            "economic_claims_allowed=false. No promotion. "
            "Engine-Atlas is a fourth directional source on the scoreboard, not a Case letter."
        ),
    }


def run_shadow_collapse_replay(csv_path: Path, instrument: str, output_dir: Path) -> list[dict]:
    """ENGINE StateMachine SHADOW→EXP capture. Different object from resolver SHADOW→EXP."""
    _Capture.collapses = []
    restore = _install_collapse_capture()
    try:
        crt_cfg = load_prod_config_from_registry(PROD_VERSION, instrument)
        cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
        cfg.instrument = instrument
        cfg.pip_size = MultiInstrumentRunner.INSTRUMENT_PIP.get(instrument, 0.0001)
        loader = CandleLoader(str(csv_path), instrument)
        runner = BacktestRunner(
            cfg,
            csv_path=str(csv_path),
            overrides={"diagnostic": "phase1_resolver_replay_evidence"},
        )
        runner.run(loader.stream(), loader.count(), str(output_dir / "bt_run"))
    finally:
        restore()
    return list(_Capture.collapses)


def net_r(corpus, bar_index, direction, atr, cost_model, horizon: int = HORIZON):
    return net_r_timeout(corpus, bar_index, direction, atr, cost_model, horizon)

def make_scoreboard_row(name, net_rs, *, n_universe, n_eligible):
    return scoreboard_row(name, net_rs, n_universe=n_universe, n_eligible=n_eligible, min_n_label=MIN_N_LABEL, pf_cap=PF_CAP)

dir_to_long_short = _dir_to_long_short
tb_to_long_short = _tb_to_long_short
install_collapse_capture = _install_collapse_capture
load_trend_bias_by_ts = _load_trend_bias_by_ts
normalize_ts = _normalize_ts
call_case = _call_case
_net_r = net_r
_scoreboard_row = make_scoreboard_row
_profit_factor = profit_factor

