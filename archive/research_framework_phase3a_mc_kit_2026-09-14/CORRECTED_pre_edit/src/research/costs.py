"""costs.py — conservative flat cost model for the falsification phase (M1–M6).

The purpose of M1–M6 is *falsification, not execution realism*. A simple model that
slightly OVER-penalizes is strictly preferable to a sophisticated one that under-
estimates and manufactures false edges. We therefore apply a flat round-trip haircut:

    round_trip = entry (0.05%) + exit (0.05%) + slippage_reserve (0.02%) = 0.12% = 12 bps

applied symmetrically to every trade. `forward_walk` stays pure GROSS geometry; the cost
is converted to R units and subtracted by `EdgeAggregator` so every gate qualifies on
NET RR. Cost-model evolution (see plan): M1–M6 flat → M7 observed → M8 per-symbol.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ROUND_TRIP_BPS = 12.0   # 0.12%


@dataclass(frozen=True)
class CostModel:
    """Flat round-trip cost expressed in basis points of entry price."""

    round_trip_bps: float = DEFAULT_ROUND_TRIP_BPS

    def cost_r(self, entry: float, risk_distance: float) -> float:
        """Round-trip cost expressed in R units (= cost_price / risk_distance).

        risk_distance is the 1R price distance (sl_atr_mult * atr). A trade risking a
        small distance relative to price pays proportionally more cost in R terms —
        which correctly penalizes tight-stop / high-churn hypotheses.
        """
        if risk_distance <= 0:
            raise ValueError(f"CostModel.cost_r: non-positive risk_distance ({risk_distance})")
        cost_price = (self.round_trip_bps / 10_000.0) * entry
        return cost_price / risk_distance

    def net_rr(self, gross_rr: float, entry: float, risk_distance: float) -> float:
        """Net an outcome's gross R by the round-trip cost."""
        return gross_rr - self.cost_r(entry, risk_distance)


# Canonical instances.
DEFAULT_COST_MODEL = CostModel()                  # 12 bps — used everywhere by default
ZERO_COST = CostModel(round_trip_bps=0.0)          # for pure-geometry math tests only


# ══════════════════════════════════════════════════════════════════════════════
# Component cost model — SEM-015 BROKER_EXECUTION_COST_DECOMPOSITION
# ──────────────────────────────────────────────────────────────────────────────
# ADDITIVE. Everything above this line is untouched: `CostModel` /
# `DEFAULT_COST_MODEL` remain the default everywhere, so every existing result
# stays byte-identical until a config explicitly opts in (`costs.cost_model`).
#
# Why this exists: the flat `round_trip_bps` above is one number applied to every
# instrument. Real trading cost is a property of the BROKER and the ORDER TYPE,
# not of price level or volatility. It decomposes into:
#
#   half_spread  the bid/ask gap you cross on entry and again on exit
#   commission   the broker's per-side fee
#   slippage     drift between the price you asked for and the price you got,
#                which differs by ORDER TYPE (a stop slips more than a limit)
#   swap         overnight financing, charged per night held
#
# LEG ASYMMETRY (the reason this is not just `2 * c_per_side`): in this
# architecture a trade ENTERS on a market order at the signal bar's close and
# EXITS either on a stop (SL) or a limit (TP). Only the stop leg pays stop
# slippage, and a resting limit order never fills better than its level. The
# source calibration's `c_per_side` bundles stop slippage into a single per-side
# figure because ZONE-X, which commissioned it, places stops on BOTH legs — a
# correct convention there, and the wrong one here. This model applies each
# component to the legs that actually incur it.
#
# See the SEM-015 ontology node and results/research/xauusd_mt5_cost_calibration/.
# ══════════════════════════════════════════════════════════════════════════════

MEASURED = "MEASURED"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
UNKNOWN = "UNKNOWN"

_USABLE_STATUS = (MEASURED,)

#: How `entry_slippage` was obtained. Never silently zero — see `from_manifest`.
ENTRY_SLIP_MEASURED = "MEASURED"
ENTRY_SLIP_PROXY_FROM_STOP = "PROXY_FROM_STOP"

#: Exit kinds closed by a STOP order, and therefore paying stop slippage.
#: `forward_walk` emits these verbatim (see research.contracts.Outcome).
_STOP_EXITS = frozenset({"SL_HIT"})


class UnmeasuredCostError(ValueError):
    """Raised when a cost component is used without a defensible measured basis.

    Deliberately loud. The failure mode this guards against is an unmeasured
    component silently becoming 0.0, which understates cost and manufactures
    apparent edge — the same discipline `mt5_cost_calibration.py` enforces on the
    measurement side ("write UNKNOWN, never invent").
    """


@dataclass(frozen=True)
class ComponentCostModel:
    """Broker-truth trading cost, decomposed. SEM-015.

    All price-unit fields are **per unit traded, per leg**, in the instrument's own
    price units (USD/oz for XAUUSD). They are NOT basis points.

    Unlike `CostModel`, this model is *exit-aware*: `stop_slippage` is charged only
    when the position is closed by a stop order. Modelling a take-profit as if it
    slipped in the holder's favour would be exactly the optimism this class exists
    to remove.
    """

    half_spread: float           # half the bid/ask gap — crossed on entry AND exit
    commission: float            # broker fee per leg (sign-insensitive; abs() applied)
    entry_slippage: float        # market-order fill drift on entry
    stop_slippage: float         # STOP-order fill drift — charged on stop exits only
    swap_long_per_night: "float | None"   # signed: negative = you pay. None = UNMEASURED
    swap_short_per_night: "float | None"
    instrument: str
    source: str                  # provenance: manifest path + sha256, or "SYNTHETIC"
    status: str                  # MEASURED | INSUFFICIENT_DATA | UNKNOWN
    entry_slippage_basis: str = ENTRY_SLIP_MEASURED

    def __post_init__(self) -> None:
        if self.status not in (MEASURED, INSUFFICIENT_DATA, UNKNOWN):
            raise ValueError(
                f"ComponentCostModel.status must be one of "
                f"{(MEASURED, INSUFFICIENT_DATA, UNKNOWN)}, got {self.status!r}"
            )
        if self.entry_slippage_basis not in (ENTRY_SLIP_MEASURED, ENTRY_SLIP_PROXY_FROM_STOP):
            raise ValueError(
                f"ComponentCostModel.entry_slippage_basis must be one of "
                f"{(ENTRY_SLIP_MEASURED, ENTRY_SLIP_PROXY_FROM_STOP)}, "
                f"got {self.entry_slippage_basis!r}"
            )
        if not self.source:
            raise ValueError("ComponentCostModel.source is required (provenance is not optional)")
        for name in ("half_spread", "commission", "entry_slippage", "stop_slippage"):
            if float(getattr(self, name)) < 0.0:
                raise ValueError(
                    f"ComponentCostModel.{name} must be >= 0 (got {getattr(self, name)}); "
                    "costs are magnitudes, the caller applies direction"
                )

    # ── construction ─────────────────────────────────────────────────────────
    @classmethod
    def from_manifest(cls, manifest: dict, *, instrument: str, source: str) -> "ComponentCostModel":
        """Build from an `mt5_cost_calibration` manifest dict.

        FAIL-CLOSED on the components this model charges. Spread, commission and
        STOP slippage must each carry status MEASURED; a partial manifest raises
        rather than letting a component become a silent 0.0.

        ENTRY slippage is handled explicitly rather than defaulted. Market-order
        slippage is frequently absent from a calibration (the reference XAUUSD run
        has n=0 MARKET fills, status INSUFFICIENT_DATA). When it is missing this
        falls back to the measured STOP slippage as a declared **conservative
        proxy** — conservative because a stop triggers into momentum and so
        typically slips at least as much as a market order — and records
        `entry_slippage_basis=PROXY_FROM_STOP` so the assumption travels with the
        number into every report. It never falls back to zero.
        """
        statuses = manifest.get("statuses") or {}
        required = ("spread", "commission", "slippage_stop")
        missing = [k for k in required if statuses.get(k) not in _USABLE_STATUS]
        if missing:
            raise UnmeasuredCostError(
                f"ComponentCostModel.from_manifest({instrument}): components {missing} are not "
                f"{MEASURED} (got {[statuses.get(k) for k in missing]}). Refusing to default them "
                "to 0.0 — measure them, or keep the instrument on the flat-bps model."
            )
        block = manifest.get("c_per_side") or {}
        if block.get("status") not in _USABLE_STATUS:
            raise UnmeasuredCostError(
                f"ComponentCostModel.from_manifest({instrument}): c_per_side.status="
                f"{block.get('status')!r}, expected {MEASURED}"
            )
        comp = block.get("components") or {}
        stop_slip = float(comp["stop_slippage_usd"])

        entry_slip_raw = comp.get("entry_slippage_usd")
        if entry_slip_raw is not None and statuses.get("slippage_market") in _USABLE_STATUS:
            entry_slip, basis = float(entry_slip_raw), ENTRY_SLIP_MEASURED
        else:
            entry_slip, basis = stop_slip, ENTRY_SLIP_PROXY_FROM_STOP

        # Swap lives in a sidecar file, not inline in the manifest. Read it when the
        # manifest points at one; otherwise leave it None (= UNMEASURED). It is NOT
        # defaulted to 0.0 — a silent zero here would make overnight carry free.
        swap: dict = manifest.get("swap") or {}
        if not swap:
            swap_path = (manifest.get("outputs") or {}).get("swap_json")
            if swap_path and Path(swap_path).is_file():
                loaded = json.loads(Path(swap_path).read_text(encoding="utf-8"))
                if loaded.get("status") in _USABLE_STATUS:
                    swap = loaded
        return cls(
            half_spread=float(comp["half_spread_usd"]),
            commission=abs(float(comp["commission_per_oz_usd"])),
            entry_slippage=entry_slip,
            stop_slippage=stop_slip,
            swap_long_per_night=(
                float(swap["swap_long_usd_per_oz"]) if "swap_long_usd_per_oz" in swap else None
            ),
            swap_short_per_night=(
                float(swap["swap_short_usd_per_oz"]) if "swap_short_usd_per_oz" in swap else None
            ),
            instrument=instrument,
            source=source,
            status=MEASURED,
            entry_slippage_basis=basis,
        )

    # ── cost surface ─────────────────────────────────────────────────────────
    def _require_usable(self) -> None:
        if self.status not in _USABLE_STATUS:
            raise UnmeasuredCostError(
                f"ComponentCostModel({self.instrument}) has status={self.status!r}; "
                f"only {MEASURED} may be used to charge cost. Source: {self.source}"
            )

    def cost_price(
        self,
        *,
        exit_kind: str = "SL_HIT",
        direction: str = "long",
        nights_held: int = 0,
    ) -> float:
        """Round-trip cost in PRICE units per unit traded.

        entry leg : half_spread + commission + entry_slippage   (market order)
        exit leg  : half_spread + commission + stop_slippage if a stop exit,
                    else half_spread + commission               (limit order)
        carry     : |swap| * nights_held, charged only when swap is a debit
        """
        self._require_usable()
        entry_leg = self.half_spread + self.commission + self.entry_slippage
        exit_leg = self.half_spread + self.commission
        if exit_kind in _STOP_EXITS:
            exit_leg += self.stop_slippage
        total = entry_leg + exit_leg
        if nights_held > 0:
            swap = self.swap_long_per_night if direction == "long" else self.swap_short_per_night
            if swap is None:
                raise UnmeasuredCostError(
                    f"ComponentCostModel({self.instrument}): nights_held={nights_held} but the "
                    f"{direction} overnight swap is UNMEASURED. Refusing to treat carry as free. "
                    f"Source: {self.source}"
                )
            # A positive swap is a CREDIT. Only a debit adds to cost; a credit is
            # deliberately NOT netted off here. Letting overnight financing subsidise
            # a losing entry conflates two different payoffs — the carry-HARVEST
            # payoff was falsified separately as F-034 and must not leak in as a
            # discount on a directional trade's cost.
            if swap < 0:
                total += abs(swap) * nights_held
        return total

    def cost_r(
        self,
        entry: float,
        risk_distance: float,
        *,
        exit_kind: str = "SL_HIT",
        direction: str = "long",
        nights_held: int = 0,
    ) -> float:
        """Round-trip cost in R units (= cost_price / risk_distance).

        Mirrors `CostModel.cost_r`'s ratio semantics, so a tight-stop / high-churn
        hypothesis is still penalised proportionally. `entry` is accepted for
        signature symmetry with `CostModel.cost_r` and is unused: component costs
        are absolute price units and do not need the price level to scale.
        """
        if risk_distance <= 0:
            raise ValueError(
                f"ComponentCostModel.cost_r: non-positive risk_distance ({risk_distance})"
            )
        return self.cost_price(
            exit_kind=exit_kind, direction=direction, nights_held=nights_held
        ) / risk_distance

    def net_rr(
        self,
        gross_rr: float,
        entry: float,
        risk_distance: float,
        *,
        exit_kind: str = "SL_HIT",
        direction: str = "long",
        nights_held: int = 0,
    ) -> float:
        """Net an outcome's gross R by the round-trip cost."""
        return gross_rr - self.cost_r(
            entry, risk_distance,
            exit_kind=exit_kind, direction=direction, nights_held=nights_held,
        )

    def effective_bps(
        self,
        entry: float,
        *,
        exit_kind: str = "SL_HIT",
        direction: str = "long",
        nights_held: int = 0,
    ) -> float:
        """Round-trip cost of ONE trade expressed in basis points of its entry price.

        Only for reporting alongside the flat model — a component cost has no single
        bps value, because it is absolute price units and the bps equivalent moves with
        the price level. Never use this to charge cost; use `cost_r`.
        """
        if entry <= 0:
            raise ValueError(f"ComponentCostModel.effective_bps: non-positive entry ({entry})")
        return (
            self.cost_price(exit_kind=exit_kind, direction=direction, nights_held=nights_held)
            / entry
        ) * 10_000.0

    # ── provenance ───────────────────────────────────────────────────────────
    def provenance(self) -> dict:
        """Self-describing block for `research.provenance.truth_standard_block`."""
        return {
            "cost_model_id": "component_measured.v1",
            "ontology_id": "SEM-015",
            "instrument": self.instrument,
            "status": self.status,
            "source": self.source,
            "entry_slippage_basis": self.entry_slippage_basis,
            "components": {
                "half_spread": self.half_spread,
                "commission": self.commission,
                "entry_slippage": self.entry_slippage,
                "stop_slippage": self.stop_slippage,
                "swap_long_per_night": self.swap_long_per_night,
                "swap_short_per_night": self.swap_short_per_night,
            },
        }
