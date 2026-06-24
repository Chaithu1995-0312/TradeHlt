> Created: 2026-05-21 · Updated: 2026-05-21 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Correlation Engine v2 — Rolling Pearson with TTL Cache & Static Fallback

## Context

`CorrelationEngine` ([`src/portfolio/correlation_engine.py`](src/portfolio/correlation_engine.py)) currently estimates instrument correlation via a deterministic group-membership heuristic (same 3-letter prefix → 0.8, same asset-class set → 0.8, FX↔USD shorts → 0.4, else → 0.2). It never updates when actual co-movement diverges from those groupings — so when EURUSD/GBPUSD decorrelate during a macro event, the engine keeps treating them as highly correlated and the portfolio over-allocates risk. This patch replaces the heuristic *as the primary path* with a rolling 20-day Pearson correlation computed from real daily OHLCV, keeps the existing heuristic as a visible fallback for missing/stale data, and adds a TTL cache so we don't recompute on every candle. Public interfaces stay identical; downstream consumers in [`allocator.py:82`](src/portfolio/allocator.py:82) and [`signal_pool.py:74`](src/scanner/signal_pool.py:74) need no changes.

**Reality vs original prompt** — the prompt assumed `get_correlation()`, a `{"EURUSD_GBPUSD": 0.85}` dict, a `candle_store.py`, a `ConfigBuilder.build_portfolio_config()`, and a `config["instruments"]` key. None of those exist in this repo. Plan aligns to the codebase as-is.

---

## Critical files

| File | Role |
| --- | --- |
| [`src/portfolio/correlation_engine.py`](src/portfolio/correlation_engine.py) | Primary edit — rewrite internals, preserve public surface |
| [`src/data_ingestion/historical_fetcher.py`](src/data_ingestion/historical_fetcher.py) | Read-only — `HistoricalFetcher.load(pair, "D1", start, end) → List[OHLCVRow]` is the data source |
| [`src/config_layer/production_config.py`](src/config_layer/production_config.py) | Read-only — use `get_prod_section("portfolio")` to load the correlation block |
| [`src/utils/integrity_events.py`](src/utils/integrity_events.py) | Read-only — `emit_integrity_event(event_type, severity, source, payload)` |
| [`configs/production/v2_multi_2026_04 - deepdeektry.json`](configs/production/v2_multi_2026_04%20-%20deepdeektry.json) | Add `portfolio.correlation` block |
| [`configs/production/v1_multi_2026_03.json`](configs/production/v1_multi_2026_03.json) | Add `portfolio.correlation` block (parity) |
| [`scripts/update_config_hash.py`](scripts/update_config_hash.py) | Re-hash both configs after edit |

**Untouched:** [`allocator.py`](src/portfolio/allocator.py), [`signal_pool.py`](src/scanner/signal_pool.py), [`capital_policy.py`](src/portfolio/capital_policy.py) — zero downstream changes.

---

## Design decisions (confirmed)

1. **Magnitude semantics** — `correlation()` returns `abs(pearson)` in `[0, 1]`, preserving the existing contract used by `signal_pool.corr_threshold > 0.7` and `capital_policy.compute_risk(..., max_correlation=...)`. Anti-correlated pairs co-move under shocks and must dedup the same as positively correlated pairs.
2. **Instrument source = union** of `data_ingestion.pairs` ∪ `inout.scanner.allowed_symbols`. No new instrument registry — the matrix automatically tracks whatever the system trades.
3. **Construction = optional injection with lazy defaults** — `CorrelationEngine()` still works (allocator/signal_pool unchanged); tests can inject `config=`/`fetcher=`.
4. **Method name stays `correlation()`** (prompt's `get_correlation` doesn't exist; renaming would break two consumers for no gain).
5. **Static fallback = existing group heuristic**, not a pair dict. The `_heuristic_correlation()` private method stays exactly as-is and becomes the safety net.

---

## Edit 1 — `src/portfolio/correlation_engine.py`

Rewrite the module with this structure. Module-level group sets (`_CRYPTO_SYMBOLS`, `_FX_MAJORS`, `_USD_SHORTS`) and the `_HIGH_CORR`/`_MED_CORR`/`_LOW_CORR` constants stay verbatim. `_heuristic_correlation()` stays verbatim. The public methods `correlation()` and `max_correlation_with_existing()` keep their signatures.

```python
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
        # Lazy default: pull the portfolio section from prod config
        if config is None:
            try:
                from src.config_layer.production_config import get_prod_section
                config = get_prod_section("portfolio") or {}
            except Exception as exc:
                log.warning("CorrelationEngine: prod config unavailable (%s) — using defaults", exc)
                config = {}
        self._config = config

        # Lazy default: instantiate HistoricalFetcher unless dependencies missing
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
        self._default_correlation = 0.0   # unknown pair, no data → assume uncorrelated

    # ── Public API ────────────────────────────────────────────────────────────

    def correlation(self, sym1: str, sym2: str) -> float:
        """Return estimated correlation in [0, 1]. Magnitude only."""
        if not sym1 or not sym2:
            return 0.0
        if sym1 == sym2:
            return 1.0

        s1, s2 = sym1.upper(), sym2.upper()
        key    = tuple(sorted([s1, s2]))

        # Cache hit
        now = time.time()
        if self._cache is not None and (now - self._cache.computed_at) < self._cache_ttl:
            val = self._cache.matrix.get(key)
            if val is not None:
                return val
            # Cache valid but pair absent → fall through to fallback

        # Recompute matrix if cache cold/expired
        if self._cache is None or (now - self._cache.computed_at) >= self._cache_ttl:
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

        # Fallback to group heuristic
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
        # Engine receives the portfolio section; for instruments we need the
        # full prod config. Re-fetch via get_prod_section on demand.
        try:
            from src.config_layer.production_config import get_prod_section
            di       = get_prod_section("data_ingestion") or {}
            inout    = get_prod_section("inout") or {}
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
                {"instrument": instrument, "rows_loaded": len(rows) if rows else 0,
                 "min_required": self._min_obs},
            )
            return None

        newest_ts = rows[-1].ts
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

        matrix: dict = {}
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
```

**Integrity event catalogue** (all `WARNING` severity, source `correlation_engine`):

| Event | When |
| --- | --- |
| `CORRELATION_FETCHER_UNAVAILABLE` | `HistoricalFetcher` import failed at init |
| `CORRELATION_CONFIG_UNAVAILABLE` | `get_prod_section` failed when listing instruments |
| `CORRELATION_NO_INSTRUMENTS` | Union of pairs + allowed_symbols is empty |
| `CORRELATION_DATA_INSUFFICIENT` | Per-instrument: `<min_observations` rows, or load raised |
| `CORRELATION_STALE_DATA` | Per-instrument: newest candle older than `max_staleness_days` |
| `CORRELATION_COMPUTE_FAILED` | Matrix computation raised |
| `CORRELATION_STATIC_FALLBACK` | A `correlation()` call hit the group heuristic |

---

## Edit 2 — Both production configs

Add to **both** `configs/production/v2_multi_2026_04 - deepdeektry.json` and `configs/production/v1_multi_2026_03.json` under the existing top-level `portfolio` key (sibling of `initial_capital`, `risk_pct`, …):

```json
"portfolio": {
    "initial_capital": 100000.0,
    "risk_pct": 0.01,
    "slippage_atr_fraction": 0.08,
    "warmup_candles": 100,
    "output_dir": "results/portfolio",
    "correlation": {
        "lookback_days":        20,
        "cache_ttl_secs":       3600,
        "min_observations":     10,
        "max_staleness_days":   3
    }
}
```

Then re-hash:

```powershell
python scripts/update_config_hash.py "configs/production/v2_multi_2026_04 - deepdeektry.json"
python scripts/update_config_hash.py "configs/production/v1_multi_2026_03.json"
```

(Note: the hash is computed over `params` only; the `portfolio` block is a sibling, so the hash will remain unchanged. Run the script anyway to confirm — and to keep the convention.)

---

## Verification (adapted to actual codebase APIs)

The original prompt's verification used `ConfigBuilder.build_portfolio_config()`, which does not exist. Use the actual API:

```powershell
# 1 — engine constructs without error and returns a value in [0, 1]
python -c "from src.portfolio.correlation_engine import CorrelationEngine; ce = CorrelationEngine(); r = ce.correlation('EURUSD', 'GBPUSD'); print(f'EURUSD/GBPUSD: {r:.4f}'); assert 0.0 <= r <= 1.0; print('PASS')"

# 2 — symmetry
python -c "from src.portfolio.correlation_engine import CorrelationEngine; ce = CorrelationEngine(); ab = ce.correlation('EURUSD','GBPUSD'); ba = ce.correlation('GBPUSD','EURUSD'); assert abs(ab-ba) < 1e-9, f'asymmetry: {ab} vs {ba}'; print('PASS — symmetric:', ab)"

# 3 — cache TTL: second call ≥10× faster than the first
python -c "import time; from src.portfolio.correlation_engine import CorrelationEngine; ce = CorrelationEngine(); t0=time.time(); ce.correlation('EURUSD','GBPUSD'); t1=time.time(); ce.correlation('EURUSD','GBPUSD'); t2=time.time(); assert (t2-t1) < (t1-t0)*0.1, 'cache not working'; print(f'PASS — first {t1-t0:.3f}s, cached {t2-t1:.5f}s')"

# 4 — fallback fires visibly for an unknown pair
python -c "import json, pathlib; from src.portfolio.correlation_engine import CorrelationEngine; ce = CorrelationEngine(); ce.correlation('FAKE1','FAKE2'); events=[json.loads(l) for l in pathlib.Path('logs/integrity_events.jsonl').read_text(encoding='utf-8').splitlines()[-30:]]; kinds=[e.get('event') for e in events]; assert 'CORRELATION_STATIC_FALLBACK' in kinds, kinds; print('PASS — fallback event fired')"

# 5 — downstream untouched: allocator + signal_pool still construct and behave
python -c "from src.portfolio.allocator import PortfolioAllocator; a = PortfolioAllocator(); r = a.allocate({'symbol':'EURUSD','confidence':0.7}); print('allocator:', r['action']); assert r['action'] in ('ALLOCATE','REJECT'); print('PASS')"

# 6 — short backtest shows no regression
python scripts/backtest/run_backtest.py --instrument ETHUSDT --bars 500
```

Tests to add under `tests/portfolio/test_correlation_engine.py`:

- Symmetry — `correlation(A,B) == correlation(B,A)`.
- Same-symbol → 1.0; empty → 0.0.
- Pearson degenerate (constant series) → falls back to heuristic.
- Anti-correlated synthetic series (r ≈ -1) → returns ≈ 1.0 (magnitude semantics).
- Cache hit within TTL window does not call `HistoricalFetcher.load` (use a `MagicMock` fetcher and assert `call_count`).
- Stale-data path: feed `OHLCVRow` with `ts` 10 days old → emits `CORRELATION_STALE_DATA` and falls back.
- `max_correlation_with_existing` with empty list → 0.0.
- `_get_tracked_instruments` reads union from both config keys.

---

## Success criteria

- `correlation()` returns rolling magnitude for any pair where both instruments have ≥10 fresh daily closes.
- Symmetric across argument order.
- Cache TTL prevents recomputation within `cache_ttl_secs` (default 3600s).
- Static heuristic fires visibly via `CORRELATION_STATIC_FALLBACK` whenever the rolling path can't answer.
- Zero changes in [`allocator.py`](src/portfolio/allocator.py), [`signal_pool.py`](src/scanner/signal_pool.py), [`capital_policy.py`](src/portfolio/capital_policy.py).
- Both prod configs re-hashed (no-op expected; convention).
- 500-bar backtest on ETHUSDT clean.

## What does NOT change

- `correlation(sym1, sym2) → float` and `max_correlation_with_existing(symbol, list)` signatures.
- Return range `[0, 1]`.
- Static group heuristic (`_FX_MAJORS`, `_CRYPTO_SYMBOLS`, `_USD_SHORTS`, `_heuristic_correlation`) — preserved verbatim as fallback.
- `CorrelationEngine()` zero-arg construction — still works for `allocator.py:44` and `signal_pool.py`.
- Class name and import path.

## What NOT to do

- Do not rename `correlation()` to `get_correlation()`.
- Do not return signed Pearson — always `abs()`.
- Do not import `scipy` — numpy only.
- Do not recompute the matrix on every call — TTL cache is mandatory.
- Do not delete `_heuristic_correlation()`, the group sets, or the `_HIGH/MED/LOW_CORR` constants.
- Do not hardcode the instrument list — read from `data_ingestion.pairs` ∪ `inout.scanner.allowed_symbols`.
- Do not stuff config under `params` — keep `correlation` under top-level `portfolio` so the existing `params`-only hash stays stable.
