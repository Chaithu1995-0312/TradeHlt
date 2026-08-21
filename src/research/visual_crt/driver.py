"""driver.py — Visual CRT ledger driver. Default bindings = MC-VCRT-XAUUSD-M15-V1.

Walks a corpus bar-by-bar, emits SEM-012 v2 entries for BOTH pre-registered arms, and
resolves each through ``forward_walk(exit_model="intrabar_fixed")``.

CONTRACT BINDINGS. The frozen GEOMETRY below is never changed here — change the contract, with
a new MC id. The COST and EXIT models are injected per run (``cost_model`` / ``adverse_fill``)
precisely so a new contract can rebind them without editing this module; both default to V1's
bindings, so calling ``run_arm`` without them reproduces V1 byte-for-byte (verified against the
committed V1 ledgers before MC-VCRT-XAUUSD-M15-V2 was built).
  * corpus         : measurement population only; the visual-audit corpus is a separate run
  * L3 pre-flight  : ``dataset_integrity.validate_dataset`` is BINDING, not the F-039 default
  * duplicate rule : one shot per (pool, direction) until a newer closed parent replaces the
                     pool, AND at most one open trade at a time (contract-owned)
  * arms           : A = displacement-bar close, B = retest-bar close. Pre-registered together.
                     Reporting one arm without the other, or picking one after seeing
                     outcomes, is FC-METRIC-VARIANT-SELECTION.
  * horizon        : 40 bars. Also bounds Arm B's retest search — the contract froze the
                     retest predicate but no separate retest age, so the declared horizon is
                     reused rather than a new parameter invented.

ISOLATION: no runtime import of the live spine from this package (AST-enforced). Note the one
measured transitive touch: ``features.parent_candle._aggregate`` lazily imports
``crt_engine_v2.Candle`` when a parent period closes, so the spine's *Candle dataclass* is
loaded as an OHLC container. No spine geometry, state machine, config, or decision is
imported or called. ``runtime.backtest_v2.CandleLoader`` is deliberately NOT used — it lives
behind a forbidden module — so this driver parses the CSV itself.

Outputs go only under ``results/visual_crt/``.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Iterator, Sequence

from features.parent_candle import ParentCandleBuilder
from research.contracts import Signal
from research.indicators import atr as research_atr
from research.measurement.forward_walk import AdverseFill, forward_walk
from research.visual_crt.geometry import detect_directional_displacement, detect_pool_sweep
from research.visual_crt.pools import visible_pools
from research.visual_crt.retest import detect_pool_retest

CONTRACT_ID = "MC-VCRT-XAUUSD-M15-V1"
SEM_VERSION = 2

# ── frozen parameters (mirror the sealed contract; never tuned here) ────────
BODY_RATIO_MIN = 0.65
ATR_MULTIPLIER_MIN = 1.0
ATR_MIN_DISPLACEMENT = 1.2
MAX_SWEEP_AGE_CANDLES = 20
ATR_PERIOD = 14
N_PRIOR_H4 = 1
RETEST_DEPTH_MAX = 0.15
RETEST_ATR_DEPTH_FRACTION = 0.3
RETEST_MIN_DEPTH_ATR_FRACTION = 0.1
SL_ATR_BUFFER = 0.2
TP_ATR_MULT = 2.0
HORIZON_BARS = 40
ROUND_TRIP_BPS = 12.0

ARMS = ("A", "B")


@dataclass(frozen=True)
class Bar:
    """Local OHLC container. Deliberately not the spine's Candle."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    index: int


@dataclass(frozen=True)
class LedgerRow:
    arm: str
    instrument: str
    entry_ts: str
    entry_index: int
    direction: str
    entry: float
    sl_atr_mult: float
    tp_atr_mult: float
    atr_abs: float
    pool_kind: str
    pool_price: float
    sweep_bar_index: int
    sweep_price: float
    displacement_bar_index: int
    outcome: str
    rr_gross: float
    rr_net: float
    mfe: float
    mae: float
    duration_candles: int
    corpus_path: str
    corpus_sha256: str
    contract_id: str
    sem_012_version: int
    status: str = "CURRENT"


def load_bars(path: str | Path) -> list[Bar]:
    """Parse an OHLCV CSV into local Bars. Chronological order is asserted, not assumed."""
    rows: list[Bar] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for i, rec in enumerate(csv.DictReader(fh)):
            ts_raw = rec.get("timestamp") or rec.get("time") or rec.get("date")
            rows.append(
                Bar(
                    timestamp=datetime.fromisoformat(str(ts_raw).strip()),
                    open=float(rec["open"]),
                    high=float(rec["high"]),
                    low=float(rec["low"]),
                    close=float(rec["close"]),
                    volume=float(rec.get("volume") or 0.0),
                    index=i,
                )
            )
    for prev, cur in zip(rows[:-1], rows[1:]):
        if cur.timestamp < prev.timestamp:
            raise ValueError(f"load_bars: non-chronological at index {cur.index}")
    return rows


def _preflight(path: str | Path) -> dict:
    """L3 dataset-integrity gate. BINDING per the sealed contract."""
    from data_ingestion.dataset_integrity import validate_dataset

    return validate_dataset(
        str(path), bar_minutes=15, write_report=False, raise_on_fail=True
    )


def _net_r(
    rr_gross: float,
    entry: float,
    risk_distance: float,
    *,
    exit_kind: str = "SL_HIT",
    direction: str = "long",
    cost_model=None,
) -> float:
    """Net an outcome's gross R by the bound cost model.

    ``cost_model=None`` is the V1 binding: the declared 12bps round-trip constant. Cost is a
    fraction of notional and R is priced in `risk_distance`, so the cost in R is
    (bps/10000 * entry) / risk_distance. 12bps is the LEGACY UNCALIBRATED constant — every net
    figure it produces is DIAGNOSTIC (FC-COST-MODEL-SUBSTITUTION), and F-082 measured it
    over-charging XAUUSD by ~11x.

    Any other value must expose `cost_r(entry, risk_distance, exit_kind=..., direction=...)` —
    i.e. `research.costs.ComponentCostModel` (SEM-015), which is exit-aware: stop slippage is
    charged on a stop exit and never on a take-profit.
    """
    if risk_distance <= 0:
        return rr_gross
    if cost_model is None:
        cost_price = (ROUND_TRIP_BPS / 10_000.0) * entry
        return rr_gross - (cost_price / risk_distance)
    return rr_gross - cost_model.cost_r(
        entry, risk_distance, exit_kind=exit_kind, direction=direction
    )


def _pool_key(pool) -> tuple:
    """Identity of a pool for the one-shot rule. A newer closed parent produces a new
    formed_at_index and therefore a new key, which re-arms that level."""
    return (pool.kind, round(pool.price, 6), pool.formed_at_index)


def run_arm(
    bars: Sequence[Bar],
    arm: str,
    *,
    instrument: str,
    corpus_path: str,
    corpus_sha256: str,
    cost_model=None,
    adverse_fill: "AdverseFill | None" = None,
    contract_id: str = CONTRACT_ID,
) -> list[LedgerRow]:
    """Walk the corpus once for one arm. Pure w.r.t. the filesystem.

    `cost_model` / `adverse_fill` / `contract_id` are the per-contract bindings. Their defaults
    are MC-VCRT-XAUUSD-M15-V1's, so an unparameterised call reproduces V1 byte-for-byte. The
    frozen geometry (pool vocabulary, sweep/displacement/retest predicates, thresholds, horizon,
    duplicate rule) is NOT injectable — changing it requires a new contract AND new code.
    """
    if arm not in ARMS:
        raise ValueError(f"run_arm: unknown arm {arm!r} (expected one of {ARMS})")

    h4 = ParentCandleBuilder(rule="H4", keep=max(2, N_PRIOR_H4 + 1))
    d1 = ParentCandleBuilder(rule="D1", keep=2)

    rows: list[LedgerRow] = []
    fired: set[tuple] = set()          # one-shot per (pool identity, direction)
    open_until_index = -1              # one open trade at a time
    pending_sweeps: list = []          # sweeps awaiting a displacement
    pending_displacements: list = []   # arm B only: displacements awaiting a retest

    for i, bar in enumerate(bars):
        h4.push(bar)
        d1.push(bar)

        window = bars[max(0, i - (ATR_PERIOD + 1)): i + 1]
        atr_abs = research_atr(window, ATR_PERIOD)
        if atr_abs <= 0:
            continue

        pools = visible_pools(h4.parent_history, d1.parent_history, n_prior_h4=N_PRIOR_H4)

        # ── expire stale candidates ────────────────────────────────────────
        pending_sweeps = [
            s for s in pending_sweeps if i - s.bar_index <= MAX_SWEEP_AGE_CANDLES
        ]
        pending_displacements = [
            d for d in pending_displacements if i - d.bar_index <= HORIZON_BARS
        ]

        entry_event = None
        entry_disp = None

        # ── arm B: a pending displacement may retest on this bar ───────────
        if arm == "B":
            for disp in list(pending_displacements):
                ev = detect_pool_retest(
                    bar, disp, atr_abs,
                    retest_depth_max=RETEST_DEPTH_MAX,
                    retest_atr_depth_fraction=RETEST_ATR_DEPTH_FRACTION,
                    retest_min_depth_atr_fraction=RETEST_MIN_DEPTH_ATR_FRACTION,
                )
                if ev is not None:
                    entry_event, entry_disp = ev, disp
                    pending_displacements.remove(disp)
                    break

        # ── displacement on this bar, for any live sweep ───────────────────
        if entry_event is None:
            for sweep in list(pending_sweeps):
                disp = detect_directional_displacement(
                    bar, sweep, atr_abs,
                    body_ratio_min=BODY_RATIO_MIN,
                    atr_min_displacement=ATR_MIN_DISPLACEMENT,
                    atr_multiplier_min=ATR_MULTIPLIER_MIN,
                    max_sweep_age_candles=MAX_SWEEP_AGE_CANDLES,
                )
                if disp is None:
                    continue
                pending_sweeps.remove(sweep)
                if arm == "A":
                    entry_event, entry_disp = disp, disp
                else:
                    pending_displacements.append(disp)
                break

        # ── a new sweep may also start on this bar ─────────────────────────
        sweep_now = detect_pool_sweep(bar, pools)
        if sweep_now is not None:
            key = (_pool_key(sweep_now.pool), sweep_now.direction)
            if key not in fired:
                pending_sweeps.append(sweep_now)

        if entry_event is None or entry_disp is None:
            continue

        # ── duplicate rule ─────────────────────────────────────────────────
        sweep = entry_disp.sweep
        key = (_pool_key(sweep.pool), sweep.direction)
        if key in fired:
            continue
        if i <= open_until_index:
            continue  # a trade is already open — drop, never queue

        # ── build the signal ───────────────────────────────────────────────
        entry_px = float(bar.close)
        direction = entry_disp.direction
        if direction == "long":
            stop = sweep.sweep_price - SL_ATR_BUFFER * atr_abs
            risk_distance = entry_px - stop
        else:
            stop = sweep.sweep_price + SL_ATR_BUFFER * atr_abs
            risk_distance = stop - entry_px
        if risk_distance <= 0:
            continue  # degenerate geometry (entry already beyond the stop)

        sig = Signal(
            instrument=instrument,
            timestamp=bar.timestamp,
            entry_index=i,
            direction=direction,
            entry=entry_px,
            sl_atr_mult=risk_distance / atr_abs,
            tp_atr_mult=TP_ATR_MULT,
            atr=atr_abs,
            meta={"arm": arm, "pool_kind": sweep.pool.kind},
        )
        future = bars[i + 1: i + 1 + HORIZON_BARS]
        if not future:
            continue
        out = forward_walk(
            sig, future, max_forward=HORIZON_BARS, exit_model="intrabar_fixed",
            adverse_fill=adverse_fill,
        )

        fired.add(key)
        open_until_index = i + out.duration_candles

        rows.append(
            LedgerRow(
                arm=arm,
                instrument=instrument,
                entry_ts=bar.timestamp.isoformat(),
                entry_index=i,
                direction=direction,
                entry=entry_px,
                sl_atr_mult=sig.sl_atr_mult,
                tp_atr_mult=TP_ATR_MULT,
                atr_abs=atr_abs,
                pool_kind=sweep.pool.kind,
                pool_price=sweep.pool.price,
                sweep_bar_index=sweep.bar_index,
                sweep_price=sweep.sweep_price,
                displacement_bar_index=entry_disp.bar_index,
                outcome=out.outcome,
                rr_gross=out.rr_achieved,
                rr_net=_net_r(
                    out.rr_achieved, entry_px, risk_distance,
                    exit_kind=out.outcome, direction=direction, cost_model=cost_model,
                ),
                mfe=out.mfe,
                mae=out.mae,
                duration_candles=out.duration_candles,
                corpus_path=corpus_path,
                corpus_sha256=corpus_sha256,
                contract_id=contract_id,
                sem_012_version=SEM_VERSION,
            )
        )

    return rows


def summarize(rows: Sequence[LedgerRow], *, contract_id: str = CONTRACT_ID) -> dict:
    """Diagnostic summary. NOT an economic verdict — economic_claims_allowed is false."""
    n = len(rows)
    if n == 0:
        return {"n": 0, "verdict": "INSUFFICIENT", "note": "no entries produced"}
    wins_net = [r for r in rows if r.rr_net > 0]
    exp_net = sum(r.rr_net for r in rows) / n
    exp_gross = sum(r.rr_gross for r in rows) / n
    gains = sum(r.rr_net for r in wins_net)
    losses = -sum(r.rr_net for r in rows if r.rr_net <= 0)
    return {
        "n": n,
        "wins_net": len(wins_net),
        "win_rate_net": len(wins_net) / n,
        "expectancy_R_gross": exp_gross,
        "expectancy_R_net": exp_net,
        "profit_factor_net": (gains / losses) if losses > 0 else None,
        "outcomes": {o: sum(1 for r in rows if r.outcome == o) for o in
                     sorted({r.outcome for r in rows})},
        "power": "SUFFICIENTLY_POPULATED" if n >= 30 else "INSUFFICIENT",
        "authority": "DIAGNOSTIC_ONLY — economic_claims_allowed=false on " + contract_id,
    }


def write_ledger(out_dir: Path, arm: str, rows: Sequence[LedgerRow]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"ledger_arm_{arm}.jsonl"
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(asdict(r), sort_keys=True) + "\n")
    return path
