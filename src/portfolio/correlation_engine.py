# correlation_engine.py — rolling Pearson with static heuristic fallback.
#
# Primary path: 20-day Pearson on daily closes (cached, TTL-bounded).
# Fallback:     existing group-based heuristic (preserved verbatim).

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np

from src.utils.integrity_events import emit_integrity_event

log = logging.getLogger(__name__)

# ── Static fallback table — PRESERVED VERBATIM ────────────────────────────────
_CRYPTO_SYMBOLS = {"BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT"}
_FX_MAJORS      = {"EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"}
_USD_SHORTS     = {"USDJPY", "USDCHF", "USDCAD"}
_HIGH_CORR = 0.8
_MED_CORR  = 0.4
_LOW_CORR  = 0.2

# ── Defaults (override via portfolio.correlation in prod config) ──────────────
_DEFAULT_LOOKBACK_DAYS    = 20
_DEFAULT_CACHE_TTL_SECS   = 3600
_DEFAULT_MIN_OBSERVATIONS = 10
_DEFAULT_MAX_STALENESS    = 3
_FETCH_BUFFER_DAYS        = 10        # weekends/holidays buffer

_SOURCE = "correlation_engine"


@dataclass
class _CorrMatrix:
    matrix:      dict           # {(inst_a, inst_b): float} — keys are sorted tuples
    computed_at: float
    n_days:      int
    sources:     dict = field(default_factory=dict)   # instrument → n_observations


class CorrelationEngine:
    """
    Estimates correlation between two symbols, in [0, 1].

    Primary path: rolling Pearson on the last `lookback_days` daily closes,
    cached with TTL. Returns abs(r) — direction is irrelevant for co-movement
    risk; anti-correlated pairs still co-move under shocks.

    Fallback path: original group-based heuristic (same 3-letter prefix, same
    asset class, FX↔USD shorts). Used when data is missing, stale, or compute
    fails. All fallbacks emit an integrity event so the divergence is visible.

    Public surface unchanged from Phase 1:
        - correlation(sym1, sym2) -> float in [0, 1]
        - max_correlation_with_existing(symbol, existing_symbols) -> float
    """

    def __init__(
        self,
        config: Optional[dict] = None,
        fetcher=None,
    ):
        if config is None:
            try:
                from src.config_layer.production_config import get_prod_section
                config = get_prod_section("portfolio") or {}
            except Exception as exc:
                log.warning("CorrelationEngine: prod config unavailable (%s) — using defaults", exc)
                config = {}
        self._config = config

        if fetcher is None:
            try:
                from src.data_ingestion.historical_fetcher import HistoricalFetcher
                fetcher = HistoricalFetcher()
            except Exception as exc:
                emit_integrity_event(
                    "CORRELATION_FETCHER_UNAVAILABLE", "WARNING", _SOURCE,
                    {"error": str(exc)},
                )
                fetcher = None
        self._fetcher = fetcher

        corr_cfg = (config or {}).get("correlation", {})
        self._lookback_days  = int(corr_cfg.get("lookback_days",     _DEFAULT_LOOKBACK_DAYS))
        self._cache_ttl      = float(corr_cfg.get("cache_ttl_secs", _DEFAULT_CACHE_TTL_SECS))
        self._min_obs        = int(corr_cfg.get("min_observations", _DEFAULT_MIN_OBSERVATIONS))
        self._max_stale_days = int(corr_cfg.get("max_staleness_days", _DEFAULT_MAX_STALENESS))

        self._cache: Optional[_CorrMatrix] = None
        self._default_correlation = 0.0

    # ── Public API ────────────────────────────────────────────────────────────

    def correlation(self, sym1: str, sym2: str) -> float:
        """Return estimated correlation in [0, 1]. Magnitude only."""
        if not sym1 or not sym2:
            return 0.0
        if sym1 == sym2:
            return 1.0

        s1, s2 = sym1.upper(), sym2.upper()
        key    = tuple(sorted([s1, s2]))

        now = time.time()
        if self._cache is not None and (now - self._cache.computed_at) < self._cache_ttl:
            val = self._cache.matrix.get(key)
            if val is not None:
                return val
        else:
            try:
                self._cache = self._compute_matrix()
                val = self._cache.matrix.get(key)
                if val is not None:
                    return val
            except Exception as exc:
                emit_integrity_event(
                    "CORRELATION_COMPUTE_FAILED", "WARNING", _SOURCE,
                    {"inst_a": s1, "inst_b": s2, "error": str(exc)},
                )

        static_val = self._heuristic_correlation(s1, s2)
        emit_integrity_event(
            "CORRELATION_STATIC_FALLBACK", "WARNING", _SOURCE,
            {"inst_a": s1, "inst_b": s2, "static_value": static_val,
             "reason": "pair missing from rolling matrix"},
        )
        return static_val

    def max_correlation_with_existing(self, symbol: str, existing_symbols: list) -> float:
        """Return max correlation between `symbol` and any existing position."""
        if not existing_symbols:
            return 0.0
        return max(self.correlation(symbol, s) for s in existing_symbols)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _get_tracked_instruments(self) -> list:
        """Union of data_ingestion.pairs ∪ inout.scanner.allowed_symbols.
        No hardcoded list — automatic coverage of whatever the system trades."""
        try:
            from src.config_layer.production_config import get_prod_section
            di    = get_prod_section("data_ingestion") or {}
            inout = get_prod_section("inout") or {}
        except Exception as exc:
            emit_integrity_event(
                "CORRELATION_CONFIG_UNAVAILABLE", "WARNING", _SOURCE,
                {"error": str(exc)},
            )
            return []

        instruments = set()
        for pair in di.get("pairs", []):
            instruments.add(str(pair).upper())
        for sym in inout.get("scanner", {}).get("allowed_symbols", []):
            instruments.add(str(sym).upper())

        if not instruments:
            emit_integrity_event(
                "CORRELATION_NO_INSTRUMENTS", "WARNING", _SOURCE,
                {"config_keys_checked": ["data_ingestion.pairs",
                                         "inout.scanner.allowed_symbols"]},
            )
        return sorted(instruments)

    def _load_closes(self, instrument: str) -> Optional[np.ndarray]:
        """Load up to `lookback_days + buffer` daily closes. Returns None if
        unavailable, insufficient, or stale."""
        if self._fetcher is None:
            return None

        end_dt   = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=self._lookback_days + _FETCH_BUFFER_DAYS)
        try:
            rows = self._fetcher.load(
                pair=instrument,
                timeframe="D1",
                start=start_dt.strftime("%Y-%m-%d"),
                end=end_dt.strftime("%Y-%m-%d"),
            )
        except Exception as exc:
            emit_integrity_event(
                "CORRELATION_DATA_INSUFFICIENT", "WARNING", _SOURCE,
                {"instrument": instrument, "error": str(exc)},
            )
            return None

        if not rows or len(rows) < self._min_obs:
            emit_integrity_event(
                "CORRELATION_DATA_INSUFFICIENT", "WARNING", _SOURCE,
                {"instrument": instrument,
                 "rows_loaded": len(rows) if rows else 0,
                 "min_required": self._min_obs},
            )
            return None

        newest_ts = rows[-1].ts
        if newest_ts.tzinfo is None:
            newest_ts = newest_ts.replace(tzinfo=timezone.utc)
        if (end_dt - newest_ts) > timedelta(days=self._max_stale_days):
            emit_integrity_event(
                "CORRELATION_STALE_DATA", "WARNING", _SOURCE,
                {"instrument": instrument,
                 "newest_ts": newest_ts.isoformat(),
                 "max_staleness_days": self._max_stale_days},
            )
            return None

        return np.array([r.close for r in rows[-self._lookback_days:]], dtype=np.float64)

    def _pearson(self, a: np.ndarray, b: np.ndarray) -> Optional[float]:
        """Return abs(Pearson r) in [0, 1].

        Magnitude only — direction is irrelevant for co-movement risk.
        Highly anti-correlated pairs (r ≈ -1) co-move under shocks and must be
        treated as correlated for dedup / risk-concentration purposes."""
        if len(a) < self._min_obs or len(b) < self._min_obs:
            return None
        a = a - a.mean()
        b = b - b.mean()
        denom = float(np.std(a) * np.std(b))
        if denom < 1e-10:
            return None
        r = float(np.dot(a, b) / (len(a) * denom))
        return float(np.clip(abs(r), 0.0, 1.0))

    def _compute_matrix(self) -> _CorrMatrix:
        instruments = self._get_tracked_instruments()
        closes: dict = {}
        for inst in instruments:
            arr = self._load_closes(inst)
            if arr is not None:
                closes[inst] = arr

        matrix:  dict = {}
        sources: dict = {k: len(v) for k, v in closes.items()}
        insts = sorted(closes.keys())
        for i, a in enumerate(insts):
            for b in insts[i + 1:]:
                arr_a, arr_b = closes[a], closes[b]
                n = min(len(arr_a), len(arr_b))
                r = self._pearson(arr_a[-n:], arr_b[-n:])
                if r is not None:
                    matrix[tuple(sorted([a, b]))] = r

        return _CorrMatrix(
            matrix=matrix,
            computed_at=time.time(),
            n_days=self._lookback_days,
            sources=sources,
        )

    # ── Static fallback (PRESERVED verbatim from Phase 1) ─────────────────────

    def _heuristic_correlation(self, s1: str, s2: str) -> float:
        """Group-based heuristic correlation. Used as fallback when rolling
        data is missing, stale, or compute fails. DO NOT REMOVE."""
        if len(s1) >= 3 and len(s2) >= 3 and s1[:3] == s2[:3]:
            return _HIGH_CORR
        if s1 in _CRYPTO_SYMBOLS and s2 in _CRYPTO_SYMBOLS:
            return _HIGH_CORR
        if s1 in _FX_MAJORS and s2 in _FX_MAJORS:
            return _HIGH_CORR
        if s1 in _USD_SHORTS and s2 in _USD_SHORTS:
            return _HIGH_CORR
        if (s1 in _FX_MAJORS and s2 in _USD_SHORTS) or \
           (s1 in _USD_SHORTS and s2 in _FX_MAJORS):
            return _MED_CORR
        return _LOW_CORR
