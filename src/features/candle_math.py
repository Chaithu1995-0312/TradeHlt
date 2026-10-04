"""
Candle geometry primitives — the single, immutable source of truth for candle math.

MECHANISM, NOT POLICY. These are mathematical identities over OHLC (like `area = pi*r*r`),
NOT trading interpretations. They live in code, are never configurable, and are never
`eval`'d. Feature *compositions* that are debatable (e.g. which denominator `body_ratio`
uses) are policy and belong in config (see configs/formulas/); the primitives below are not.

WHY THIS MODULE EXISTS
----------------------
`wick_size`/`body_ratio` were computed in three places that must agree:
  - CRT engine `Candle` property        (src/config_layer/crt_engine_v2.py)
  - batch feature pipeline (vectorized)  (src/features/feature_pipeline.py)
  - single-row builder                   (src/features/crt_feature_builder.py, dead)
The canonical definition is `body_ratio = body_size / candle_range` — bounded [0, 1], which
is the only metric the CRT displacement gate `body_ratio < 0.70` is coherent against. Routing
the scalar callers through this module makes divergence structurally impossible; the vectorized
pipeline is bound to these identities by tests/test_candle_math.py (parity battery).

All functions are scalar (float -> float). The vectorized pipeline mirrors these identities
in numpy for performance and is verified equal by the parity test.
"""


def body_size(open_: float, close: float) -> float:
    """Absolute candle body: |close - open|."""
    return abs(close - open_)


def candle_range(high: float, low: float) -> float:
    """Full candle range: high - low. (Historically mislabelled `wick_size`.)"""
    return high - low


def upper_wick(open_: float, high: float, close: float) -> float:
    """Upper rejection wick: high - max(open, close)."""
    return high - max(open_, close)


def lower_wick(open_: float, low: float, close: float) -> float:
    """Lower rejection wick: min(open, close) - low."""
    return min(open_, close) - low


def total_wick(open_: float, high: float, low: float, close: float) -> float:
    """Combined wick length: upper_wick + lower_wick == candle_range - body_size."""
    return upper_wick(open_, high, close) + lower_wick(open_, low, close)


def body_ratio(open_: float, high: float, low: float, close: float) -> float:
    """
    Canonical body ratio: body_size / candle_range, bounded [0, 1].

    Returns 0.0 when the candle range is non-positive (degenerate flat bar), matching the
    legacy guard in both the CRT `Candle` property and the batch pipeline.

    Identity: FEAT-BODY_TO_RANGE_RATIO / FORMULA-BODY-TO-RANGE (FM-010).
    Distinct from body_to_total_wick_ratio (FEAT-BODY_TO_TOTAL_WICK_RATIO).
    """
    rng = candle_range(high, low)
    return body_size(open_, close) / rng if rng > 0 else 0.0


def body_to_total_wick_ratio(open_: float, high: float, low: float, close: float) -> float:
    """
    Distinct semantic: body_size / total_wick (unbounded above 1 when body > wicks).

    Identity: FEAT-BODY_TO_TOTAL_WICK_RATIO / FORMULA-BODY-TO-TOTAL-WICK.
    Historically emitted under the bare name ``body_ratio`` by live_engine_hook
    (GD-001 / Q-BODY-RATIO-NONCANON-LIVE). Not interchangeable with body_ratio.
    Returns 0.0 when total_wick is non-positive.
    """
    tw = total_wick(open_, high, low, close)
    return body_size(open_, close) / tw if tw > 1e-8 else 0.0
