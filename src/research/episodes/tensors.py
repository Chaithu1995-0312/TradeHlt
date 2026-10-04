"""Tier-3 tensor materializer — [N, T, D] views for sequence models.

Generalizes the IC-002 precedent (`ic002_entry_evolution/`, 15 features × N bars as
npz) from one frozen feature list to a declared channel spec over the episode path.
Tensors are **never canonical** (substrate §13): they are a regenerable cache, so a
tensor view is deleted and rebuilt rather than migrated.

Channels are R-NORMALIZED by default. A raw price channel makes BNBUSDT (~600) and
EURUSD (~1.1) incomparable in the same batch and lets the model learn the instrument
instead of the path; dividing by `risk_distance` makes every channel a multiple of the
position's own risk. Price channels are also direction-signed, so a long and a short
with identical geometry produce identical rows.

Variable-length episodes are padded to T with an explicit mask — `mask[n, t] == 1`
marks a real observation. Never train on padded steps without applying it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

from research.episodes.schema import (
    Derived,
    EntrySnapshot,
    Observation,
    OpportunityEpisode,
    resolved_derived,
)

# A channel: (entry, obs, derived) -> float. `derived` is never None here — the
# builder skips t=0, which is the only step without a derived layer.
Channel = Callable[[EntrySnapshot, Observation, Derived], float]


def _sign(entry: EntrySnapshot) -> float:
    return 1.0 if entry.direction == "long" else -1.0


def _price_r(attr: str) -> Channel:
    """(price - entry) / risk, signed so long and short are comparable."""
    def _c(entry, obs, d):
        return _sign(entry) * (getattr(obs, attr) - entry.entry_price) / entry.risk_distance
    return _c


CHANNELS: dict[str, Channel] = {
    # path state (already direction-aware and R-normalized in Derived)
    "unrealized_pnl_r":     lambda e, o, d: d.unrealized_pnl_r,
    "mfe_r":                lambda e, o, d: d.mfe_r,
    "mae_r":                lambda e, o, d: d.mae_r,
    "drawdown_from_peak_r": lambda e, o, d: d.drawdown_from_peak_r,
    "distance_to_sl_r":     lambda e, o, d: d.distance_to_sl_raw / e.risk_distance,
    "distance_to_tp_r":     lambda e, o, d: d.distance_to_tp_raw / e.risk_distance,
    # bar geometry, entry-relative and direction-signed
    "open_r":  _price_r("open"),
    "high_r":  _price_r("high"),
    "low_r":   _price_r("low"),
    "close_r": _price_r("close"),
    "range_r": lambda e, o, d: (o.high - o.low) / e.risk_distance,
    # raw
    "volume":     lambda e, o, d: o.volume,
    "bars_held":  lambda e, o, d: float(d.bars_held),
}

DEFAULT_CHANNELS: tuple[str, ...] = (
    "unrealized_pnl_r", "mfe_r", "mae_r", "drawdown_from_peak_r",
    "close_r", "range_r",
)


@dataclass(frozen=True)
class TensorSpec:
    """A declared, hashable tensor view."""

    channels: tuple[str, ...] = DEFAULT_CHANNELS
    max_steps: int = 40
    pad_value: float = 0.0
    dtype: str = "float64"

    def __post_init__(self) -> None:
        unknown = [c for c in self.channels if c not in CHANNELS]
        if unknown:
            raise ValueError(f"TensorSpec: unknown channels {unknown} "
                             f"(available: {sorted(CHANNELS)})")
        if not self.channels:
            raise ValueError("TensorSpec: at least one channel is required")
        if self.max_steps < 1:
            raise ValueError(f"TensorSpec: max_steps must be >= 1 (got {self.max_steps})")

    @property
    def D(self) -> int:
        return len(self.channels)

    def spec_hash(self) -> str:
        import hashlib

        blob = json.dumps({"channels": list(self.channels), "max_steps": self.max_steps,
                           "pad_value": self.pad_value, "dtype": self.dtype},
                          sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


@dataclass
class TensorBatch:
    """[N, T, D] + mask + row identity. A regenerable view, never truth."""

    X: np.ndarray                       # (N, T, D)
    mask: np.ndarray                    # (N, T) uint8 — 1 = real observation
    episode_ids: list[str] = field(default_factory=list)
    instruments: list[str] = field(default_factory=list)
    spec: TensorSpec = field(default_factory=TensorSpec)
    lengths: list[int] = field(default_factory=list)

    @property
    def shape(self) -> tuple[int, int, int]:
        return tuple(self.X.shape)  # type: ignore[return-value]

    def channel(self, name: str) -> np.ndarray:
        """The (N, T) slice for one channel."""
        return self.X[:, :, self.spec.channels.index(name)]

    def summary(self) -> dict[str, Any]:
        return {
            "n_episodes": int(self.X.shape[0]),
            "max_steps": int(self.X.shape[1]),
            "n_channels": int(self.X.shape[2]),
            "channels": list(self.spec.channels),
            "spec_hash": self.spec.spec_hash(),
            "real_steps": int(self.mask.sum()),
            "pad_fraction": round(1.0 - float(self.mask.mean()), 6) if self.mask.size else 0.0,
            "mean_length": round(float(np.mean(self.lengths)), 3) if self.lengths else 0.0,
        }


def build_tensor(episodes: Sequence[OpportunityEpisode],
                 spec: TensorSpec | None = None) -> TensorBatch:
    """Materialize [N, T, D] from episodes. Deterministic and order-preserving.

    Only forward steps (t >= 1) are emitted: t=0 is the entry bar, which carries no
    path state and which no policy may act on.
    """
    spec = spec or TensorSpec()
    n, T, D = len(episodes), spec.max_steps, spec.D

    X = np.full((n, T, D), spec.pad_value, dtype=spec.dtype)
    mask = np.zeros((n, T), dtype=np.uint8)
    ids, instruments, lengths = [], [], []
    fns = [CHANNELS[c] for c in spec.channels]

    for i, ep in enumerate(episodes):
        derived = resolved_derived(ep)
        entry = ep.entry
        k = 0
        for step, d in zip(ep.steps, derived):
            if step.obs.t < 1 or d is None:
                continue
            if k >= T:
                break
            X[i, k, :] = [fn(entry, step.obs, d) for fn in fns]
            mask[i, k] = 1
            k += 1
        ids.append(ep.episode_id)
        instruments.append(ep.instrument)
        lengths.append(k)

    return TensorBatch(X=X, mask=mask, episode_ids=ids, instruments=instruments,
                       spec=spec, lengths=lengths)


def path_relative(batch: TensorBatch, eps: float = 1e-9) -> np.ndarray:
    """IC-002's path-relative transform: z_t = (x_t - x_0) / max(|x_0|, eps).

    Same identity as `ic002_entry_evolution.schema.path_relative_row`, vectorized over
    the batch. Padded steps stay at 0 so the mask still selects real observations.
    """
    x0 = batch.X[:, :1, :]
    scale = np.maximum(np.abs(x0), eps)
    z = (batch.X - x0) / scale
    return z * batch.mask[:, :, None]


# ─────────────────────────────────────────────────────────────────
# I/O — npz, matching the IC-002 precedent
# ─────────────────────────────────────────────────────────────────
def save_tensor(batch: TensorBatch, out_dir: Path | str,
                *, name: str = "episode_tensor") -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    npz_path = out_dir / f"{name}.npz"
    meta_path = out_dir / f"{name}_meta.json"

    np.savez_compressed(
        npz_path,
        X=batch.X,
        mask=batch.mask,
        lengths=np.asarray(batch.lengths, dtype=np.int64),
        channels=np.array(list(batch.spec.channels)),
        episode_ids=np.array(batch.episode_ids),
        instruments=np.array(batch.instruments),
    )
    meta = {
        **batch.summary(),
        "spec": {"channels": list(batch.spec.channels), "max_steps": batch.spec.max_steps,
                 "pad_value": batch.spec.pad_value, "dtype": batch.spec.dtype},
        "tier": 3,
        "derived_from": "tier1_episodes",
        "authority": "none — regenerable training view",
        "bytes_on_disk": npz_path.stat().st_size,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {"npz": str(npz_path), "meta": str(meta_path), **meta}


def load_tensor(out_dir: Path | str, *, name: str = "episode_tensor") -> TensorBatch:
    out_dir = Path(out_dir)
    data = np.load(out_dir / f"{name}.npz", allow_pickle=False)
    meta = json.loads((out_dir / f"{name}_meta.json").read_text(encoding="utf-8"))
    s = meta["spec"]
    spec = TensorSpec(channels=tuple(s["channels"]), max_steps=int(s["max_steps"]),
                      pad_value=float(s["pad_value"]), dtype=str(s["dtype"]))
    return TensorBatch(
        X=data["X"], mask=data["mask"],
        episode_ids=[str(x) for x in data["episode_ids"].tolist()],
        instruments=[str(x) for x in data["instruments"].tolist()],
        spec=spec, lengths=[int(x) for x in data["lengths"].tolist()],
    )
