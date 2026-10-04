"""process_diagnostics.py — significance tests over the Phase-1 process fingerprint.

MEASURE-ONLY, BNBUSDT-scoped research (decoupled from the live spine: no config, no
governance, no decision path). Phase 1 (`process_characterization.py`) described the
series; this module turns each "it looks like X" into a statistic with a verdict, and
answers the real open question: *after volatility state is known, is there any (even
nonlinear) information left in direction?* ACF/Hurst catch only linear structure — mutual
information + conditional entropy catch what they miss.

Four diagnostics:
  1. Ljung-Box Q       — is the linear autocorrelation jointly zero? (returns / e^2 / ATR)
  2. ARCH-LM           — is there volatility clustering? (LM = T*R^2 on lagged e^2)
  3. Mutual information — nonlinear dependence ACF cannot see (3 pairs, vs shuffled surrogate)
  4. Direction entropy — H(sign r_{t+1} | sign r_t) within the same vol band (coin-flip test)

Pure & deterministic: numpy + stdlib only (no scipy — chi^2 verdicts use a hardcoded
critical-value table; OLS via numpy.linalg.lstsq; MI via contingency counts). Composes the
Phase-1 series builders rather than recomputing them. The thin CLI
(`scripts/analysis/process_diagnostics.py`) owns all I/O.
"""

from __future__ import annotations

import dataclasses
import hashlib
import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from research.process_characterization import (
    STATE_LABELS,
    _round,
    atr_series,
    autocorrelation,
    digitize_states,
    log_returns,
)

# Upper-tail chi^2 critical values, df 1..40 -> (alpha=0.05, alpha=0.01). Covers every
# Ljung-Box lag and ARCH-LM q used here; avoids a scipy dependency.
_CHI2_CRIT: dict[int, tuple[float, float]] = {
    1: (3.841, 6.635), 2: (5.991, 9.210), 3: (7.815, 11.345), 4: (9.488, 13.277),
    5: (11.070, 15.086), 6: (12.592, 16.812), 7: (14.067, 18.475), 8: (15.507, 20.090),
    9: (16.919, 21.666), 10: (18.307, 23.209), 11: (19.675, 24.725), 12: (21.026, 26.217),
    13: (22.362, 27.688), 14: (23.685, 29.141), 15: (24.996, 30.578), 16: (26.296, 32.000),
    17: (27.587, 33.409), 18: (28.869, 34.805), 19: (30.144, 36.191), 20: (31.410, 37.566),
    21: (32.671, 38.932), 22: (33.924, 40.289), 23: (35.172, 41.638), 24: (36.415, 42.980),
    25: (37.652, 44.314), 26: (38.885, 45.642), 27: (40.113, 46.963), 28: (41.337, 48.278),
    29: (42.557, 49.588), 30: (43.773, 50.892), 31: (44.985, 52.191), 32: (46.194, 53.486),
    33: (47.400, 54.776), 34: (48.602, 56.061), 35: (49.802, 57.342), 36: (50.998, 58.619),
    37: (52.192, 59.893), 38: (53.384, 61.162), 39: (54.572, 62.428), 40: (55.758, 63.691),
}


def _make_seed(name: str) -> int:
    """Deterministic stdlib seed derivation (sha256 -> int). Byte-identical across runs.
    No reusable `_seed_for` exists in the codebase, so this is inlined here."""
    return int(hashlib.sha256(name.encode()).hexdigest(), 16) % (2 ** 31)


# ─────────────────────────────────────────────────────────────────
# 1. LJUNG-BOX Q
# ─────────────────────────────────────────────────────────────────

def ljung_box(series: Sequence[float], lags: Sequence[int]) -> dict[str, dict]:
    """Ljung-Box Q = n(n+2)·Σ_{k=1..h} ρ_k²/(n−k) at each h in `lags`. df = h; verdict via
    the hardcoded chi^2 table. Returns {str(h): {Q, df, reject_at_5pct, reject_at_1pct}}."""
    x = np.asarray(series, dtype=float)
    n = x.size
    out: dict[str, dict] = {}
    max_h = max(lags) if lags else 0
    acf = autocorrelation(x, max_h)  # ρ_1..ρ_{max_h}
    for h in lags:
        if h < 1 or h > len(acf) or h not in _CHI2_CRIT or n <= h:
            out[str(h)] = {"Q": float("nan"), "df": h,
                           "reject_at_5pct": False, "reject_at_1pct": False}
            continue
        q = n * (n + 2) * sum((acf[k - 1] ** 2) / (n - k) for k in range(1, h + 1))
        c05, c01 = _CHI2_CRIT[h]
        out[str(h)] = {
            "Q": q, "df": h,
            "reject_at_5pct": bool(q > c05),
            "reject_at_1pct": bool(q > c01),
        }
    return out


# ─────────────────────────────────────────────────────────────────
# 2. ARCH-LM
# ─────────────────────────────────────────────────────────────────

def arch_lm(returns: Sequence[float], q: int = 12) -> dict:
    """Engle ARCH-LM test: OLS e_t² on its own q lags, LM = T·R² ~ χ²(q). e = demeaned
    returns. Returns {LM, df, r2, reject_at_5pct, reject_at_1pct}."""
    r = np.asarray(returns, dtype=float)
    n = r.size
    nan = {"LM": float("nan"), "df": q, "r2": float("nan"),
           "reject_at_5pct": False, "reject_at_1pct": False}
    if q < 1 or q not in _CHI2_CRIT or n <= q + 1:
        return nan
    e2 = (r - r.mean()) ** 2
    T = n - q
    Y = e2[q:]
    cols = [np.ones(T)] + [e2[q - i: n - i] for i in range(1, q + 1)]
    X = np.column_stack(cols)
    beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
    resid = Y - X @ beta
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((Y - Y.mean()) ** 2))
    if ss_tot == 0.0:
        return nan
    r2 = 1.0 - ss_res / ss_tot
    lm = T * r2
    c05, c01 = _CHI2_CRIT[q]
    return {"LM": lm, "df": q, "r2": r2,
            "reject_at_5pct": bool(lm > c05), "reject_at_1pct": bool(lm > c01)}


# ─────────────────────────────────────────────────────────────────
# 3. MUTUAL INFORMATION
# ─────────────────────────────────────────────────────────────────

def _contingency(xc: np.ndarray, yc: np.ndarray, nx: int, ny: int) -> np.ndarray:
    m = np.zeros((nx, ny), dtype=float)
    np.add.at(m, (xc, yc), 1.0)
    return m


def _mi_nats(m: np.ndarray) -> float:
    """Mutual information (nats) from a contingency count matrix."""
    total = m.sum()
    if total <= 0:
        return 0.0
    pxy = m / total
    px = pxy.sum(axis=1, keepdims=True)
    py = pxy.sum(axis=0, keepdims=True)
    outer = px * py  # (nx,ny) via broadcasting
    nz = pxy > 0
    return float(np.sum(pxy[nz] * np.log(pxy[nz] / outer[nz])))


def _equal_freq_codes(values: np.ndarray, bins: int) -> np.ndarray:
    """Map a continuous series to equal-frequency bin codes [0, bins)."""
    edges = np.quantile(values, np.linspace(0.0, 1.0, bins + 1))
    inner = edges[1:-1]
    return np.clip(np.digitize(values, inner), 0, bins - 1).astype(int)


def mutual_information(
    xc: np.ndarray, yc: np.ndarray, nx: int, ny: int,
    *, name: str, n_surrogates: int = 200,
) -> dict:
    """Observed MI (nats) + shuffled-surrogate baseline. Surrogate RNG seeded
    deterministically from `name`. p = permutation tail (fraction of surrogates ≥ obs)."""
    obs = _mi_nats(_contingency(xc, yc, nx, ny))
    rng = np.random.default_rng(_make_seed(name))
    surr = np.empty(n_surrogates, dtype=float)
    for i in range(n_surrogates):
        surr[i] = _mi_nats(_contingency(xc, rng.permutation(yc), nx, ny))
    p = (float(np.sum(surr >= obs)) + 1.0) / (n_surrogates + 1.0)
    return {
        "mi_nats": obs,
        "surrogate_mean": float(surr.mean()),
        "surrogate_std": float(surr.std()),
        "p_value": p,
        "significant": bool(p < 0.05),
    }


# ─────────────────────────────────────────────────────────────────
# 4. DIRECTION-ONLY CONDITIONAL ENTROPY (within vol band)
# ─────────────────────────────────────────────────────────────────

def _conditional_entropy_bits(contingency: np.ndarray) -> float:
    """H(Y|X) over a 2x2 (dir_t, dir_{t+1}) count matrix, normalized by log(2) -> [0,1].
    1.0 == Y independent & uniform given X (coin-flip). NaN if empty."""
    total = contingency.sum()
    if total <= 0:
        return float("nan")
    h = 0.0
    for row in contingency:
        rt = row.sum()
        if rt <= 0:
            continue
        for c in row:
            if c > 0:
                p = c / rt
                h += (rt / total) * (-p * math.log(p))
    return h / math.log(2)


def direction_conditional_entropy(
    states: Sequence[str],
) -> tuple[dict[str, float], float, dict[str, int]]:
    """H(sign r_{t+1} | sign r_t) restricted to consecutive pairs that stay in the same
    vol band. Returns (per_band_entropy, global_entropy, per_band_counts)."""
    bands = ["C", "N", "E"]
    dir_idx = {"U": 0, "D": 1}
    tables = {b: np.zeros((2, 2), dtype=float) for b in bands}
    for a, b in zip(states[:-1], states[1:]):
        if a[0] == b[0] and a[0] in tables:  # stay-within-band
            tables[a[0]][dir_idx[a[1]], dir_idx[b[1]]] += 1.0
    per_band = {b: _conditional_entropy_bits(tables[b]) for b in bands}
    counts = {b: int(tables[b].sum()) for b in bands}
    total = sum(counts.values())
    if total > 0:
        glob = sum(per_band[b] * counts[b] for b in bands
                   if not math.isnan(per_band[b])) / total
    else:
        glob = float("nan")
    return per_band, glob, counts


# ─────────────────────────────────────────────────────────────────
# MANIFEST + ORCHESTRATION
# ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProcessDiagnostics:
    """Deterministic diagnostics manifest (no wall-clock; that lives in the CLI's
    separate run-manifest)."""
    instrument: str
    n_candles: int
    n_returns: int
    rounding: int
    # 1. ljung-box
    ljung_box_lags: list[int]
    ljung_box: dict[str, dict]
    # 2. arch-lm
    arch_lm_q: int
    arch_lm: dict
    # 3. mutual information
    mi_bins: int
    mi_n_surrogates: int
    mutual_information: dict[str, dict]
    # 4. direction conditional entropy
    direction_entropy_per_band: dict[str, float]
    direction_entropy_global: float
    direction_entropy_counts: dict[str, int]
    # derived advisory summary (raw stats above remain authoritative)
    thesis_flags: dict[str, bool]

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def _round_lb(lb: dict[str, dict], nd: int) -> dict[str, dict]:
    return {h: {k: (_round(v, nd) if isinstance(v, float) else v)
                for k, v in row.items()} for h, row in lb.items()}


def run_diagnostics(
    candles: Sequence,
    *,
    instrument: str = "UNKNOWN",
    atr_period: int = 14,
    ljung_box_lags: Sequence[int] = (10, 20),
    arch_q: int = 12,
    mi_bins: int = 20,
    mi_surrogates: int = 200,
    round_to: int = 6,
) -> ProcessDiagnostics:
    """Run the four diagnostics over an ordered candle sequence."""
    bars = list(candles)
    n = len(bars)
    closes = [b.close for b in bars]
    rets = log_returns(closes)
    e = rets - rets.mean() if rets.size else rets
    sq = e ** 2
    atrs = atr_series(bars, atr_period)
    states, _lo, _hi = digitize_states(rets, atrs)

    lags = list(ljung_box_lags)
    lb = {
        "returns": ljung_box(rets, lags),
        "squared_returns": ljung_box(sq, lags),
        "atr": ljung_box(atrs, lags),
    }
    al = arch_lm(rets, arch_q)

    # MI pairs. Codes: sign 1->U(0)/0->D... use 1 for r>=0 to match digitize ('U').
    sign = (rets >= 0.0).astype(int)  # 1 = up, 0 = down
    band_code = np.array([{"C": 0, "N": 1, "E": 2}[s[0]] for s in states], dtype=int) \
        if states else np.empty(0, dtype=int)
    atr_code = _equal_freq_codes(atrs, mi_bins) if atrs.size else np.empty(0, dtype=int)

    mi: dict[str, dict] = {}
    if sign.size > 2:
        mi["sign_t__sign_next"] = mutual_information(
            sign[:-1], sign[1:], 2, 2,
            name=f"process_diagnostics:mi:sign_t__sign_next:{instrument}",
            n_surrogates=mi_surrogates)
        mi["atr_t__sign_next"] = mutual_information(
            atr_code[:-1], sign[1:], mi_bins, 2,
            name=f"process_diagnostics:mi:atr_t__sign_next:{instrument}",
            n_surrogates=mi_surrogates)
        mi["vol_state_t__sign_next"] = mutual_information(
            band_code[:-1], sign[1:], 3, 2,
            name=f"process_diagnostics:mi:vol_state_t__sign_next:{instrument}",
            n_surrogates=mi_surrogates)

    per_band, glob, counts = direction_conditional_entropy(states)

    # Advisory thesis flags.
    lb_ret_20 = lb["returns"].get("20", {})
    flags = {
        "returns_linearly_uncorrelated": bool(not lb_ret_20.get("reject_at_5pct", True)),
        "arch_effects_present": bool(al.get("reject_at_1pct", False)),
        "direction_coinflip_given_vol": bool(
            not math.isnan(glob) and glob > 0.98),
        "nonlinear_direction_info": bool(
            mi.get("sign_t__sign_next", {}).get("significant", False)
            or mi.get("vol_state_t__sign_next", {}).get("significant", False)),
    }

    def _rmi(d: dict) -> dict:
        return {k: {kk: (_round(vv, round_to) if isinstance(vv, float) else vv)
                    for kk, vv in v.items()} for k, v in d.items()}

    return ProcessDiagnostics(
        instrument=instrument,
        n_candles=n,
        n_returns=int(rets.size),
        rounding=round_to,
        ljung_box_lags=lags,
        ljung_box={s: _round_lb(v, round_to) for s, v in lb.items()},
        arch_lm_q=arch_q,
        arch_lm={k: (_round(v, round_to) if isinstance(v, float) else v)
                 for k, v in al.items()},
        mi_bins=mi_bins,
        mi_n_surrogates=mi_surrogates,
        mutual_information=_rmi(mi),
        direction_entropy_per_band={b: _round(per_band[b], round_to) for b in per_band},
        direction_entropy_global=_round(glob, round_to),
        direction_entropy_counts=counts,
        thesis_flags=flags,
    )
