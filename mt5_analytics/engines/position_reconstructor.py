"""
position_reconstructor — deals → PositionEpisode (THE KERNEL).

*Position reconstruction is sacred; everything else is disposable.* Every higher layer
(features → reports → clusters → conclusions) inherits truth from here, so this module
is small, explicit, and exhaustively torture-tested (Phase 2a) before anything is built
on top of it.

What it handles (broker-tolerant):
  • partial scale-outs   — IN, OUT, OUT, OUT finalize only on volume balance
  • pyramiding           — VWAP entry/exit, never first-deal price
  • multiple tickets / one position_id
  • commission / swap as SEPARATE (zero-volume) deal records, incl. post-close swap
  • INOUT reversals      — close-old + open-new in one deal (BUY 1 / SELL 2 → close 1 + open 1)
  • reopen-after-close   — same position_id, two distinct episodes
  • completion guard     — an unbalanced (still-open) leg is NOT emitted

Input: a list of MT5 deal dicts (from `mt5_adapter.history_deals_get`, or synthetic
fixtures). Required keys per deal: position_id, ticket, symbol, type, entry, volume,
price, profit, swap, commission, time. Output: a list of frozen `PositionEpisode`s
(one per fully-closed lifetime), deterministic given the same deals.

Note (K-3): an INOUT (reversal) deal both closes one episode and opens the next, so its
ticket appears in BOTH adjacent episodes' `deal_tickets`. `deal_tickets` is therefore NOT
a partition of deals across episodes — do not assume ticket→episode is 1:1.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from ..schemas.position_episode_v1_0 import (
    LONG,
    SHORT,
    PositionEpisode,
    make_episode_id,
    to_iso_utc,
)

# MT5 deal type constants (mt5.DEAL_TYPE_*).
DEAL_TYPE_BUY = 0
DEAL_TYPE_SELL = 1

# MT5 deal entry constants (mt5.DEAL_ENTRY_*).
DEAL_ENTRY_IN = 0
DEAL_ENTRY_OUT = 1
DEAL_ENTRY_INOUT = 2
DEAL_ENTRY_OUT_BY = 3

_VOL_EPS = 1e-9

logger = logging.getLogger("mt5_analytics.position_reconstructor")


def is_position_deal(deal) -> bool:
    """True for deals that belong to a real trading position.

    Account operations — deposits / credits / bonuses / charges (MT5 `DEAL_TYPE_BALANCE`
    et al.) — carry `position_id == 0` and must NOT enter reconstruction or P/L
    reconciliation (a demo deposit's `profit` is the account balance, not a trade result).
    Per-position commission / swap deals DO reference their `position_id`, so this keeps
    them. Grounded in a live demo run: the lone deal was `position_id=0, type=2,
    profit=100000` — the deposit.
    """
    return int(deal.get("position_id", 0)) != 0


def _direction_of(deal_type: int) -> str:
    return LONG if int(deal_type) == DEAL_TYPE_BUY else SHORT


@dataclass
class _Leg:
    """Mutable accumulator for one open→closed lifetime; frozen into a PositionEpisode."""

    position_id: int
    symbol: str
    direction: str
    in_px_vol: list[tuple[float, float]] = field(default_factory=list)   # (price, vol)
    out_px_vol: list[tuple[float, float]] = field(default_factory=list)
    gross_profit: float = 0.0
    commission: float = 0.0
    swap: float = 0.0
    tickets: list[int] = field(default_factory=list)
    entry_time_raw: object = None
    exit_time_raw: object = None

    @property
    def open_volume(self) -> float:
        return sum(v for _, v in self.in_px_vol) - sum(v for _, v in self.out_px_vol)

    def add_cashflow(self, deal: dict) -> None:
        self.gross_profit += float(deal.get("profit", 0.0) or 0.0)
        self.commission += float(deal.get("commission", 0.0) or 0.0)
        self.swap += float(deal.get("swap", 0.0) or 0.0)
        t = deal.get("ticket")
        if t is not None and int(t) not in self.tickets:
            self.tickets.append(int(t))

    def to_episode(self) -> PositionEpisode:
        in_vol = sum(v for _, v in self.in_px_vol)
        out_vol = sum(v for _, v in self.out_px_vol)
        entry_vwap = (
            sum(p * v for p, v in self.in_px_vol) / in_vol if in_vol > _VOL_EPS else 0.0
        )
        exit_vwap = (
            sum(p * v for p, v in self.out_px_vol) / out_vol if out_vol > _VOL_EPS else 0.0
        )
        entry_iso = to_iso_utc(self.entry_time_raw)
        exit_iso = to_iso_utc(self.exit_time_raw)
        # duration from the raw (epoch) stamps when available, else from ISO parsing.
        try:
            dur = float(int(self.exit_time_raw) - int(self.entry_time_raw))
        except (TypeError, ValueError):
            from datetime import datetime

            dur = (
                datetime.fromisoformat(exit_iso.replace("Z", "+00:00"))
                - datetime.fromisoformat(entry_iso.replace("Z", "+00:00"))
            ).total_seconds()
        net = self.gross_profit + self.commission + self.swap
        return PositionEpisode(
            position_id=self.position_id,
            episode_id=make_episode_id(self.position_id, entry_iso, self.tickets),
            symbol=self.symbol,
            direction=self.direction,
            entry_time=entry_iso,
            exit_time=exit_iso,
            entry_vwap=round(entry_vwap, 10),
            exit_vwap=round(exit_vwap, 10),
            volume=round(in_vol, 10),
            net_pnl=round(net, 10),
            gross_profit=round(self.gross_profit, 10),
            commission=round(self.commission, 10),
            swap=round(self.swap, 10),
            duration_seconds=dur,
            deal_tickets=tuple(self.tickets),
        )


def _segment_position(
    position_id: int, deals: Sequence[dict], open_position_ids: frozenset[int]
) -> list[PositionEpisode]:
    """Walk one position_id's time-ordered deals into balanced episodes."""
    finalized: list[_Leg] = []
    current: _Leg | None = None

    for deal in deals:
        vol = float(deal.get("volume", 0.0) or 0.0)
        entry = int(deal.get("entry", DEAL_ENTRY_IN))
        price = float(deal.get("price", 0.0) or 0.0)
        symbol = str(deal.get("symbol", ""))
        t = deal.get("time")

        # Zero-volume cashflow-only record (separate commission/swap deal, incl. post-close).
        if vol <= _VOL_EPS:
            target = current if current is not None else (finalized[-1] if finalized else None)
            if target is not None:
                target.add_cashflow(deal)
            else:
                # Cashflow with no leg yet — open a placeholder so it is never dropped.
                current = _Leg(position_id, symbol, _direction_of(deal.get("type", 0)))
                current.entry_time_raw = current.exit_time_raw = t
                current.add_cashflow(deal)
            continue

        if entry == DEAL_ENTRY_IN:
            if current is None:
                current = _Leg(position_id, symbol, _direction_of(deal.get("type", 0)))
                current.entry_time_raw = t
            elif not current.in_px_vol:
                # K-2: a placeholder seeded by a pre-entry cashflow record (commission/
                # swap before the first IN) — adopt THIS deal's entry identity, not the
                # cashflow record's time/direction.
                current.entry_time_raw = t
                current.direction = _direction_of(deal.get("type", 0))
            current.in_px_vol.append((price, vol))
            current.exit_time_raw = t
            current.add_cashflow(deal)

        elif entry in (DEAL_ENTRY_OUT, DEAL_ENTRY_OUT_BY):
            if current is None:
                # Orphan OUT (shouldn't happen on clean data) — attach cashflow only.
                if finalized:
                    finalized[-1].add_cashflow(deal)
                continue
            current.out_px_vol.append((price, vol))
            current.exit_time_raw = t
            current.add_cashflow(deal)
            if abs(current.open_volume) <= _VOL_EPS:
                if position_id in open_position_ids:
                    logger.debug(
                        "reconstructor anomaly: balanced (closed) leg for position_id "
                        "%s but it is reported OPEN by positions_get", position_id,
                    )
                finalized.append(current)
                current = None

        elif entry == DEAL_ENTRY_INOUT:
            # Reversal: close the whole current leg, open a new opposite leg with the
            # remainder. The deal's `type` is the NEW direction (SELL closes a long).
            close_vol = abs(current.open_volume) if current is not None else 0.0
            open_vol = vol - close_vol
            if current is not None and close_vol > _VOL_EPS:
                current.out_px_vol.append((price, close_vol))
                current.exit_time_raw = t
                current.add_cashflow(deal)
                finalized.append(current)
                current = None
            if open_vol > _VOL_EPS:
                current = _Leg(position_id, symbol, _direction_of(deal.get("type", 0)))
                current.entry_time_raw = t
                current.exit_time_raw = t
                current.in_px_vol.append((price, open_vol))
                # cashflow already consumed by the closing portion above (avoid double count)
                tk = deal.get("ticket")
                if tk is not None and int(tk) not in current.tickets:
                    current.tickets.append(int(tk))

    # Completion guard: emit only fully-balanced legs. A residual open `current` leg is
    # pending (not yet closed) and is intentionally NOT emitted — corroborated by the
    # position_id still appearing in `open_position_ids` when supplied.
    return [leg.to_episode() for leg in finalized]


def reconstruct_position_episodes(
    deals: Iterable[dict],
    *,
    open_position_ids: frozenset[int] = frozenset(),
) -> list[PositionEpisode]:
    """Reconstruct all fully-closed PositionEpisodes from a flat list of MT5 deals.

    The completion guard is **volume balance** (`Σin == Σout`), which is equivalent to
    "closed" since an open MT5 position always has non-zero net volume; a residual open
    leg is simply not emitted. `open_position_ids` (from `positions_get`) is therefore an
    advisory **cross-check** only — when a *balanced* leg's position_id is also reported
    open, a DEBUG anomaly is logged (K-1) — it never changes which episodes are emitted.

    Deterministic: episodes are returned sorted by (entry_time, position_id, episode_id).
    """
    by_pos: dict[int, list[dict]] = defaultdict(list)
    for d in deals:
        if not is_position_deal(d):
            continue   # skip account ops (deposits/credits/bonuses) — not trades
        by_pos[int(d["position_id"])].append(d)

    episodes: list[PositionEpisode] = []
    for pos_id, dlist in by_pos.items():
        ordered = sorted(dlist, key=lambda d: (d.get("time", 0), d.get("ticket", 0)))
        episodes.extend(_segment_position(pos_id, ordered, open_position_ids))

    episodes.sort(key=lambda e: (e.entry_time, e.position_id, e.episode_id))
    return episodes
