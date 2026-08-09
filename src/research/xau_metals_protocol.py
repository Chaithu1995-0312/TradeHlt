"""
xau_metals_protocol.py
======================
Loader + pure helpers for **xau_metals_protocol_v1** (pre-registered).

Frozen BEFORE re-measurement. Changing economics requires a new protocol_id
and a new JSON file — do not mutate v1 constants in place after OOS is seen.

Authority: research-only. Does not wire live spine.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROTOCOL_PATH = (
    ROOT / "configs" / "research" / "xau_metals_protocol_v1.json"
)
PROTOCOL_ID = "xau_metals_protocol_v1"


class ProtocolError(ValueError):
    """Protocol frozen-contract violation."""


@lru_cache(maxsize=4)
def load_protocol(path: str | None = None) -> dict[str, Any]:
    p = Path(path) if path else DEFAULT_PROTOCOL_PATH
    if not p.exists():
        raise FileNotFoundError(p)
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("protocol_id") != PROTOCOL_ID and path is None:
        raise ProtocolError(
            f"default protocol_id mismatch: {data.get('protocol_id')!r}"
        )
    return data


def protocol_sha256(path: str | None = None) -> str:
    p = Path(path) if path else DEFAULT_PROTOCOL_PATH
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def seed_u32(*parts: str) -> int:
    material = "|".join(parts)
    return int(hashlib.sha256(material.encode("utf-8")).hexdigest()[:8], 16)


def cost_r_fixed_usd(
    entry: float,
    atr_abs: float,
    *,
    sl_atr_mult: float,
    usd_round_trip: float,
) -> float:
    """Primary XAU_COST_V1: cost_R = usd_rt / risk_distance."""
    risk = sl_atr_mult * atr_abs
    if risk <= 0:
        raise ProtocolError(f"non-positive risk_distance={risk}")
    if usd_round_trip < 0:
        raise ProtocolError("usd_round_trip must be >= 0")
    return float(usd_round_trip) / float(risk)


def cost_r_flat_bps(
    entry: float,
    atr_abs: float,
    *,
    sl_atr_mult: float,
    round_trip_bps: float,
) -> float:
    """Legacy diagnostic only under v1."""
    risk = sl_atr_mult * atr_abs
    if risk <= 0:
        raise ProtocolError(f"non-positive risk_distance={risk}")
    return (float(round_trip_bps) / 10_000.0) * float(entry) / float(risk)


def net_rr(
    gross_rr: float,
    entry: float,
    atr_abs: float,
    *,
    sl_atr_mult: float,
    protocol: Optional[dict] = None,
    cost_mode: str = "primary",
    usd_round_trip: Optional[float] = None,
) -> float:
    """Net gross R under protocol cost (primary or explicit usd override)."""
    proto = protocol or load_protocol()
    exit_g = proto["exit_geometry"]
    sl = float(exit_g.get("sl_atr_mult", sl_atr_mult))
    cm = proto["cost_model"]
    if cost_mode == "primary" or usd_round_trip is not None:
        usd = (
            float(usd_round_trip)
            if usd_round_trip is not None
            else float(cm["primary"]["usd_round_trip"])
        )
        c = cost_r_fixed_usd(entry, atr_abs, sl_atr_mult=sl, usd_round_trip=usd)
    elif cost_mode == "legacy_bps":
        bps = float(cm["legacy_diagnostic"]["round_trip_bps"])
        c = cost_r_flat_bps(entry, atr_abs, sl_atr_mult=sl, round_trip_bps=bps)
    else:
        raise ProtocolError(f"unknown cost_mode={cost_mode!r}")
    return float(gross_rr) - c


def train_quantiles(
    scores: Sequence[float], low_pct: float = 10.0, high_pct: float = 90.0
) -> dict[str, float]:
    import numpy as np

    a = np.asarray(list(scores), dtype=float)
    if a.size < 10:
        raise ProtocolError(f"need >=10 train scores, got {a.size}")
    return {
        "n": int(a.size),
        "p_low": float(np.percentile(a, low_pct)),
        "p_high": float(np.percentile(a, high_pct)),
        "low_pct": float(low_pct),
        "high_pct": float(high_pct),
    }


def assign_random_match_control(
    *,
    n_units: int,
    splits: Sequence[str],
    in_top: Sequence[bool],
    protocol: Optional[dict] = None,
) -> list[bool]:
    """XAU_CTRL_V1: per-split size-match to top decile; single membership vector.

    Returns list[bool] membership in random_match_n (length n_units).
    Acceptance: count(random)==count(top) and per-split equality.
    """
    import random

    proto = protocol or load_protocol()
    ctrl = proto["control_arm"]
    if ctrl.get("id") != "XAU_CTRL_V1_RANDOM_MATCH":
        raise ProtocolError("control_arm id mismatch")

    material = ctrl["seeds"]["material"]
    s_train = seed_u32(material, "train")
    s_oos = seed_u32(material, "oos")

    train_idx = [i for i in range(n_units) if splits[i] == "train"]
    oos_idx = [i for i in range(n_units) if splits[i] == "oos"]
    top_train = [i for i in train_idx if in_top[i]]
    top_oos = [i for i in oos_idx if in_top[i]]

    def _draw(pool: list[int], k: int, seed: int) -> list[int]:
        if k == 0:
            return []
        if k > len(pool):
            raise ProtocolError(
                f"cannot size-match k={k} from pool={len(pool)}"
            )
        rng = random.Random(seed)
        return sorted(rng.sample(pool, k))

    rand_train = _draw(train_idx, len(top_train), s_train)
    rand_oos = _draw(oos_idx, len(top_oos), s_oos)
    member = [False] * n_units
    for i in rand_train + rand_oos:
        member[i] = True

    # acceptance_test
    n_top = sum(1 for x in in_top if x)
    n_rand = sum(1 for x in member if x)
    if n_rand != n_top:
        raise ProtocolError(
            f"control acceptance failed: len(random)={n_rand} != len(top)={n_top}"
        )
    if sum(member[i] for i in train_idx) != len(top_train):
        raise ProtocolError("control train size-match failed")
    if sum(member[i] for i in oos_idx) != len(top_oos):
        raise ProtocolError("control oos size-match failed")
    return member


def assert_control_acceptance(
    *,
    in_top: Sequence[bool],
    in_random: Sequence[bool],
    splits: Sequence[str],
) -> None:
    """Pure acceptance check used by tests and runners."""
    if len(in_top) != len(in_random) or len(in_top) != len(splits):
        raise ProtocolError("length mismatch")
    if sum(in_random) != sum(in_top):
        raise ProtocolError("total size-match failed")
    for split in ("train", "oos"):
        t = sum(1 for i, s in enumerate(splits) if s == split and in_top[i])
        r = sum(1 for i, s in enumerate(splits) if s == split and in_random[i])
        if t != r:
            raise ProtocolError(f"split {split} size-match failed t={t} r={r}")


def primary_usd(protocol: Optional[dict] = None) -> float:
    proto = protocol or load_protocol()
    return float(proto["cost_model"]["primary"]["usd_round_trip"])


def sensitivity_usd_grid(protocol: Optional[dict] = None) -> list[float]:
    proto = protocol or load_protocol()
    return [
        float(x)
        for x in proto["cost_model"]["sensitivity_pre_registered"][
            "usd_round_trip_grid"
        ]
    ]
