"""
rr_dataset_builder.py
=====================
Extracts 11-feature vectors from TradeRecord objects for RR Pattern Miner training.

Feature Schema v2 (FIXED — 11 features, NO Gaussian leakage):
  0: depth          — retest_depth
  1: body           — body_ratio
  2: disp           — disp_strength
  3: is_asia        — one-hot: 1.0 if ASIA session, else 0.0
  4: is_london      — one-hot: 1.0 if LONDON session, else 0.0
  5: is_newyork     — one-hot: 1.0 if NEWYORK session, else 0.0
  6: sin_hour       — sin(2π * hour / 24)  [O(1) lookup]
  7: cos_hour       — cos(2π * hour / 24)  [O(1) lookup]
  8: depth_body     — depth × body
  9: depth_disp     — depth × disp
 10: body_disp      — body × disp

Note: gaussian_score and gaussian_p_win are EXCLUDED from the feature vector
to prevent circular dependency in the fusion formula.
They are used in rr_fusion.py only as the Gaussian baseline, not as ML inputs.

Targets:
  y_rr:  float — actual RR achieved (regression)
  y_win: int   — 1 if win, 0 otherwise (classification)

INVARIANTS:
  - Feature vector is always length 11
  - Trades with gaussian_score == 0.0 are filtered (unscored by CRT)
  - Minimum 20 samples required before training
  - std == 0.0 columns get replaced with 1.0 during normalization (in trainer)

CHANGES FROM v1:
  - Session encoding changed from ordinal (0/1/2) to one-hot (3 binary features)
    Reason: ordinal implied NEWYORK > LONDON > ASIA — a fake numerical relationship
  - Removed gaussian_score, gaussian_p_win from feature vector
    Reason: they appear in the fusion formula → including them as ML inputs
            creates a circular dependency and guarantees overfitting
"""

import json
import math
import os
from typing import List, Tuple, Any, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
N_FEATURES = 11
MIN_SAMPLES = 20

FEATURE_NAMES = [
    "depth",
    "body",
    "disp",
    "is_asia",
    "is_london",
    "is_newyork",
    "sin_hour",
    "cos_hour",
    "depth_body",
    "depth_disp",
    "body_disp",
]

# Precomputed O(1) trig lookup for hours 0-23
_SIN_HOUR: Tuple[float, ...] = tuple(
    math.sin(2.0 * math.pi * h / 24.0) for h in range(24)
)
_COS_HOUR: Tuple[float, ...] = tuple(
    math.cos(2.0 * math.pi * h / 24.0) for h in range(24)
)


# ---------------------------------------------------------------------------
# Session one-hot encoding
# ---------------------------------------------------------------------------

def _encode_session_onehot(session: Any) -> Tuple[float, float, float]:
    """
    Return (is_asia, is_london, is_newyork) one-hot encoding.

    One-hot avoids the ordinal encoding trap (NEWYORK > LONDON > ASIA is not
    a meaningful ordering for the model to learn).

    Unknown sessions return (0, 0, 0) — treated as "no session signal".
    """
    if session is None:
        return 0.0, 0.0, 0.0
    s = str(session).upper().strip()
    if s in ("ASIA", "ASIAN"):
        return 1.0, 0.0, 0.0
    if s in ("LONDON", "LONDON_OPEN"):
        return 0.0, 1.0, 0.0
    if s in ("NEWYORK", "NEW_YORK", "NY"):
        return 0.0, 0.0, 1.0
    return 0.0, 0.0, 0.0


# ---------------------------------------------------------------------------
# Hour extraction
# ---------------------------------------------------------------------------

def _extract_hour(entry_time: Any) -> int:
    """
    Extract integer hour (0-23) from entry_time.
    Accepts datetime objects or ISO strings.
    Falls back to 0 on parse failure.
    """
    if entry_time is None:
        return 0
    if hasattr(entry_time, "hour"):
        return int(entry_time.hour) % 24
    try:
        s = str(entry_time).replace("T", " ").split(" ")
        if len(s) >= 2:
            return int(s[1].split(":")[0]) % 24
    except Exception:
        pass
    return 0


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def extract_features(trade: Any) -> Optional[List[float]]:
    """
    Extract 11-feature vector from a TradeRecord (or dict-like) object.

    Returns None if the trade should be filtered:
      - gaussian_score == 0.0 → trade was not scored by CRT Gaussian engine

    Args:
        trade: TradeRecord dataclass or dict with required fields.

    Returns:
        List[float] of length 11, or None.
    """
    def _get(obj, attr, default=0.0):
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    # Filter unscored trades — must have been through the CRT Gaussian engine
    gaussian_score = float(_get(trade, "gaussian_score", 0.0))
    if gaussian_score == 0.0:
        return None

    depth = float(_get(trade, "retest_depth", 0.0))
    body  = float(_get(trade, "body_ratio", _get(trade, "body_ratio_feat", 0.0)))
    disp  = float(_get(trade, "disp_strength", _get(trade, "disp_str_feat", 0.0)))

    session = _get(trade, "session", None)
    is_asia, is_london, is_newyork = _encode_session_onehot(session)

    entry_time = _get(trade, "entry_time", None)
    hour = _extract_hour(entry_time)
    sin_h = _SIN_HOUR[hour]
    cos_h = _COS_HOUR[hour]

    return [
        depth,
        body,
        disp,
        is_asia,
        is_london,
        is_newyork,
        sin_h,
        cos_h,
        depth * body,   # depth_body
        depth * disp,   # depth_disp
        body  * disp,   # body_disp
    ]


# ---------------------------------------------------------------------------
# Target extraction
# ---------------------------------------------------------------------------

def extract_target(trade: Any) -> Tuple[float, int]:
    """
    Extract regression and classification targets.

    Returns:
        (y_rr, y_win) — actual RR achieved and win label (1/0).
    """
    def _get(obj, attr, default=0.0):
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    rr = float(_get(trade, "rr_achieved", 0.0))
    outcome = _get(trade, "outcome", "loss")
    if isinstance(outcome, str):
        win = 1 if outcome.upper() in ("WIN", "W", "TP", "1") else 0
    else:
        win = 1 if int(outcome) == 1 else 0
    return rr, win


# ---------------------------------------------------------------------------
# Dataset builder
# ---------------------------------------------------------------------------

def build_dataset(
    trades: List[Any],
) -> Tuple[List[List[float]], List[float], List[int]]:
    """
    Build (X, y_rr, y_win) from a list of TradeRecord objects.

    Args:
        trades: List of TradeRecord or dict objects.

    Returns:
        X      — List of 11-feature vectors
        y_rr   — List of float RR targets
        y_win  — List of int win labels (0/1)

    Raises:
        ValueError: if fewer than MIN_SAMPLES valid trades found.
    """
    X: List[List[float]] = []
    y_rr: List[float] = []
    y_win: List[int] = []

    for trade in trades:
        feats = extract_features(trade)
        if feats is None:
            continue
        rr, win = extract_target(trade)
        X.append(feats)
        y_rr.append(rr)
        y_win.append(win)

    if len(X) < MIN_SAMPLES:
        raise ValueError(
            f"Insufficient training data: {len(X)} valid trades found, "
            f"minimum required is {MIN_SAMPLES}."
        )

    return X, y_rr, y_win


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_dataset(
    X: List[List[float]],
    y_rr: List[float],
    y_win: List[int],
    path: str = "models/rr_dataset.json",
) -> None:
    """Persist dataset to JSON for reproducibility."""
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    payload = {
        "n_samples":     len(X),
        "n_features":    N_FEATURES,
        "feature_names": FEATURE_NAMES,
        "X":             X,
        "y_rr":          y_rr,
        "y_win":         y_win,
    }
    with open(path, "w") as f:
        json.dump(payload, f, separators=(",", ":"))


def load_dataset(
    path: str = "models/rr_dataset.json",
) -> Tuple[List[List[float]], List[float], List[int]]:
    """
    Reload dataset from JSON.

    Raises:
        FileNotFoundError: if path does not exist.
        ValueError: if loaded dataset is smaller than MIN_SAMPLES.
    """
    with open(path, "r") as f:
        payload = json.load(f)

    X    = payload["X"]
    y_rr = payload["y_rr"]
    y_win = payload["y_win"]

    if len(X) < MIN_SAMPLES:
        raise ValueError(
            f"Loaded dataset has only {len(X)} samples; minimum is {MIN_SAMPLES}."
        )

    return X, y_rr, y_win


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import datetime

    class _MockTrade:
        def __init__(self, i):
            self.retest_depth  = 0.3 + i * 0.01
            self.body_ratio    = 0.5 + i * 0.005
            self.disp_strength = 0.2 + i * 0.002
            self.gaussian_score = 0.6 + (i % 5) * 0.04  # non-zero → passes filter
            self.gaussian_p_win = 0.55 + (i % 3) * 0.05
            self.session       = ["ASIA", "LONDON", "NEWYORK"][i % 3]
            self.entry_time    = datetime.datetime(2024, 1, 1, i % 24, 0, 0)
            self.rr_achieved   = 1.5 + (i % 4) * 0.5 if i % 2 == 0 else -1.0
            self.outcome       = "win" if i % 2 == 0 else "loss"

    trades = [_MockTrade(i) for i in range(30)]
    X, y_rr, y_win = build_dataset(trades)
    print(f"Built dataset: {len(X)} samples x {len(X[0])} features")
    print(f"Feature names: {FEATURE_NAMES}")
    print(f"Sample X[0]: {X[0]}")
    assert len(X[0]) == N_FEATURES, f"Expected {N_FEATURES} features, got {len(X[0])}"

    # Verify one-hot session encoding
    asia_sample = [t for t in trades if t.session == "ASIA"][0]
    feats = extract_features(asia_sample)
    assert feats[3] == 1.0 and feats[4] == 0.0 and feats[5] == 0.0, "ASIA one-hot wrong"

    london_sample = [t for t in trades if t.session == "LONDON"][0]
    feats = extract_features(london_sample)
    assert feats[3] == 0.0 and feats[4] == 1.0 and feats[5] == 0.0, "LONDON one-hot wrong"

    ny_sample = [t for t in trades if t.session == "NEWYORK"][0]
    feats = extract_features(ny_sample)
    assert feats[3] == 0.0 and feats[4] == 0.0 and feats[5] == 1.0, "NEWYORK one-hot wrong"

    save_dataset(X, y_rr, y_win, "models/rr_dataset_test.json")
    X2, yr2, yw2 = load_dataset("models/rr_dataset_test.json")
    assert len(X2) == len(X), "Round-trip failed"
    print("Dataset builder v2 self-test PASSED.")