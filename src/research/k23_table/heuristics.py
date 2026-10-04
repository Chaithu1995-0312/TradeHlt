"""The 18 tested K23 block heuristics (pre-registration v1, section 3).

Pure functions of a bar-matrix frame. No training, no labels, no outcome. #15 is excluded
by the pre-registration (look-ahead by design). Constants come from the shadow config where a
key exists (strict lookup, KeyError on a missing key); the rest are DECLARED_CONVENTIONS below.
"""
from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd

# Pre-registration section 3, DECLARED_CONVENTIONS. Not tunable after the freeze.
CONV = {
    "h2_slope": 2.0,
    "h2_spike_weight": 0.2,
    "h3_divisor": 2.0,
    "h3_disagree_factor": 0.5,
    "h4_divisor": 2.0,
    "h5_center": 1.0,
    "h5_width": 0.5,
    "h8_width": 1.0,
    "h10_tokyo_only": 0.5,
    "h12_divisor": 2.0,
    "h12_factor": 0.25,
    "h13_width": 1.5,
    "h16_slope": 2.0,
    "h17_alpha": 1.0,
    "h18_no_ttl_score": 0.5,
    "eps": 1e-9,
}

HEURISTIC_IDS = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19)
DISCRETE_IDS = (6, 14, 19)
SMC_DISTANCE_COLS = (
    "order_block_distance", "fvg_distance", "breaker_distance", "mitigation_block_distance",
    "pdh_distance", "pdl_distance", "eqh_distance", "eql_distance",
)


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -500.0, 500.0)))


def _clamp(x, lo=0.0, hi=1.0):
    return np.clip(x, lo, hi)


def _bell(x, c, w):
    return np.exp(-((x - c) ** 2) / (2.0 * w * w))


def _sign(x):
    return np.sign(x)


def bars_in_state(state: np.ndarray) -> np.ndarray:
    """1-based position inside the maximal contiguous run of one state (K29 derivation)."""
    n = len(state)
    out = np.ones(n, dtype=np.int64)
    for i in range(1, n):
        out[i] = out[i - 1] + 1 if state[i] == state[i - 1] else 1
    return out


def episode_ids(state: np.ndarray) -> np.ndarray:
    """Maximal contiguous run of engine_state_after = one episode (block scheme A)."""
    change = np.r_[False, state[1:] != state[:-1]]
    return np.cumsum(change)


def fit_transition_kernel(state: np.ndarray, fit_idx: np.ndarray, valid: Mapping) -> dict:
    """Discovery-only empirical P(curr|prev), Laplace alpha over {legal exits} U {self-loop}."""
    alpha = CONV["h17_alpha"]
    names = {getattr(k, "name", str(k)): {getattr(x, "name", str(x)) for x in v}
             for k, v in valid.items()}
    counts: dict = {}
    outside: dict = {}
    for i in fit_idx:
        if i == 0:
            continue
        prev, cur = state[i - 1], state[i]
        support = names.get(prev, set()) | {prev}
        if cur in support:
            counts[(prev, cur)] = counts.get((prev, cur), 0) + 1
        else:
            outside[(prev, cur)] = outside.get((prev, cur), 0) + 1
    prob = {}
    for prev in {p for p, _ in counts} | set(names):
        support = sorted(names.get(prev, set()) | {prev})
        tot = sum(counts.get((prev, c), 0) for c in support) + alpha * len(support)
        for c in support:
            prob[(prev, c)] = (counts.get((prev, c), 0) + alpha) / tot
    return {"prob": prob, "outside_support_edges": outside}


def compute_heuristics(
    m: pd.DataFrame,
    *,
    cfg: Mapping,
    fit_idx: np.ndarray,
    valid_transitions: Mapping,
) -> tuple[pd.DataFrame, dict]:
    """Return (frame with h1..h19 per bar, diagnostics). h19 is emitted per direction
    as h19_long / h19_short. `fit_idx` = row positions of the discovery partition (#17)."""
    from features.broker_clock import exchange_sessions_at, parse_exchange_session_windows

    ce = cfg["crt_engine"]
    bt = cfg["backtest"]
    diag: dict = {}
    h = pd.DataFrame(index=m.index)

    h["h1"] = m["body_ratio"]
    h["h2"] = _clamp(_sigmoid(CONV["h2_slope"] * (m["volume_ratio"] - 1.0))
                     + CONV["h2_spike_weight"] * m["volume_spike"])
    agree = np.where(_sign(m["ema_spread"]) == _sign(m["momentum_score"]), 1.0,
                     CONV["h3_disagree_factor"])
    h["h3"] = _sigmoid(m["trend_strength_z"] / CONV["h3_divisor"]) * agree
    h["h4"] = (_sigmoid(m["macd_hist_z"] / CONV["h4_divisor"])
               * (0.5 + 0.5 * _sign(m["macd_hist_raw"]) * _sign(m["rsi_14"] - 50.0)))
    h["h5"] = _bell(m["volatility_ratio"], CONV["h5_center"], CONV["h5_width"])
    h["h6"] = (1.0 + (2 * m["higher_high"] - 1 + 2 * m["lower_low"] - 1
                      + 2 * m["break_of_structure"] - 1 + 2 * m["change_of_character"] - 1) / 4.0) / 2.0
    h["h7"] = _clamp(m["liquidity_pressure_score"]
                     * (1.0 + m["sweep_detected"] + 0.5 * m["double_sweep"]) / 1.5)

    absd = m[list(SMC_DISTANCE_COLS)].abs()
    med = absd.median()  # all emitted bars, no outcome (pre-registration section 3, #8)
    if (med <= 0).any():
        raise ValueError(f"#8 median-normaliser is non-positive for {list(med[med <= 0].index)}")
    diag["h8_medians"] = {k: float(v) for k, v in med.items()}
    h["h8"] = _bell((absd / med).min(axis=1, skipna=True), 0.0, CONV["h8_width"])

    decay_window = int(bt["htf_candles_per_range"])
    h["h9"] = _sigmoid(m["disp_strength"] - 1.0) * np.exp(-m["candles_since_sweep"] / decay_window)

    windows = parse_exchange_session_windows(bt["exchange_session_windows"])
    ts = pd.to_datetime(m["timestamp"]).to_numpy()
    sess = np.empty(len(m))
    for i, t in enumerate(pd.DatetimeIndex(ts).to_pydatetime()):
        act = set(exchange_sessions_at(t, windows))
        sess[i] = 1.0 if ({"LONDON", "NEWYORK"} & act) else (
            CONV["h10_tokyo_only"] if "TOKYO" in act else 0.0)
    h["h10"] = sess

    dc = m["delta_close"].abs()
    h["h11"] = dc / (dc + m["upper_wick"] + m["lower_wick"] + CONV["eps"])
    h["h12"] = _clamp(0.5 + CONV["h12_factor"] * (
        np.tanh(m["price_vs_ma20_z"] / CONV["h12_divisor"])
        + np.tanh(m["price_vs_ma50_z"] / CONV["h12_divisor"])))
    h["h13"] = (1.0 - 2.0 * (m["bb_position"] - 0.5).abs()) * _bell(m["bb_width_z"], 0.0, CONV["h13_width"])
    reg = m[["volatility_regime_global_batch", "volatility_regime_expanding_causal",
             "volatility_regime_rolling_causal"]]
    h["h14"] = 1.0 - (reg.max(axis=1) - reg.min(axis=1)) / 2.0
    h["h16"] = _sigmoid(CONV["h16_slope"] * (m["volume_range_proxy_ratio"] - 1.0))

    state = m["engine_state_after"].astype(str).to_numpy()
    kern = fit_transition_kernel(state, np.asarray(fit_idx), valid_transitions)
    diag["h17_outside_support_edges_discovery"] = {f"{a}->{b}": n for (a, b), n in kern["outside_support_edges"].items()}
    h17 = np.full(len(m), np.nan)
    for i in range(1, len(m)):
        h17[i] = kern["prob"].get((state[i - 1], state[i]), 0.0)
    h["h17"] = h17

    ttl = {
        "SWEEP": float(ce["max_sweep_age_candles"]),
        "EXPANSION": float(ce["max_expansion_age_candles"]),
        "RETEST": float(ce["soft_conf_max_candles"]),
        "SHADOW_PENDING": float(ce["pending_displacement_ttl_candles"]),
    }
    diag["h18_ttl_table"] = ttl
    b = bars_in_state(state)
    t_arr = np.array([ttl.get(s, np.nan) for s in state])
    h["h18"] = np.where(np.isnan(t_arr), CONV["h18_no_ttl_score"], 1.0 - _clamp(b / t_arr))

    bias = m["parent_bias"].astype(str).to_numpy()
    for d, tag in (("LONG", "long"), ("SHORT", "short")):
        h[f"h19_{tag}"] = np.where(bias == "NONE", 0.5, np.where(bias == d, 1.0, 0.0))
    return h, diag
