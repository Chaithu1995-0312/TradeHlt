"""Comparators: what the engine did on each bar vs what the v2 concept contracts say.

Verdicts (closed):
  AGREE                 engine and contract say the same thing
  EXPECTED_DIVERGENCE   they differ, and the difference is a divergence already RECORDED on the
                        concept (named by an explicit (concept_id, surface) attribution that must
                        exist in concept_contracts.yaml, or attribution raises)
  UNEXPLAINED           they differ and no recorded divergence explains it: a candidate semantic
                        defect, in the engine OR in the contract OR in the semantics implementation
  NOT_CHECKABLE         no comparator can decide (missing input, no implementation)

Every comparator reads engine facts recorded by observe.py and computes the contract side with the
src/semantics implementations; nothing here re-implements engine logic. Not a performance run:
no row aggregates P&L.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Optional

from semantics import geometry as gp
from semantics.market.events import sweep
from semantics.market.levels import range_levels
from semantics.registry import (
    UnmatchedTerminalReason, active_config_value, load_concept_contracts, match_terminal,
)
from semantics.types import Bias, LevelStatus, OhlcBar, Side

AGREE = "AGREE"
EXPECTED_DIVERGENCE = "EXPECTED_DIVERGENCE"
UNEXPLAINED = "UNEXPLAINED"
NOT_CHECKABLE = "NOT_CHECKABLE"
VERDICTS = (AGREE, EXPECTED_DIVERGENCE, UNEXPLAINED, NOT_CHECKABLE)

FOUNDING = "m15_structural_range"
CLOCK = "htf_period"
_RETRACE_RE = re.compile(r"^\d+% retrace hit")
_EXTENSION_PREFIX = "1.618 extension hit"


@dataclass
class Row:
    check: str
    concept_id: str
    bar: Optional[int]
    verdict: str
    engine: Any = None
    contract: Any = None
    note: str = ""
    divergence_ref: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CheckContext:
    """Observed bars (observe.Observation.bars) plus the run's own events.jsonl rows."""

    bars: list
    events: list
    concepts: dict = field(default_factory=lambda: load_concept_contracts()["concepts"])
    features: Optional[dict] = None   # ts -> {slot: value}, the run's own feature frame (C7)
    history: Optional[dict] = None    # full-corpus OHLC + ts keys the frame was built from (C7)

    def __post_init__(self) -> None:
        self.by_index = {b["bar"]: b for b in self.bars}

    def ohlc(self, index: Optional[int]) -> Optional[OhlcBar]:
        rec = self.by_index.get(index) if index is not None else None
        return to_bar(rec["candle"], index) if rec else None


def to_bar(candle: Optional[dict], index: Optional[int] = None) -> Optional[OhlcBar]:
    if not candle:
        return None
    return OhlcBar(candle["open"], candle["high"], candle["low"], candle["close"],
                   candle["index"] if index is None else index, candle.get("timestamp"))


def attribute(concepts: dict, concept_id: str, surface_prefix: str) -> str:
    """The recorded divergence a disagreement is attributed to. Raises if it is not recorded."""
    for item in (concepts.get(concept_id) or {}).get("divergences") or []:
        if isinstance(item, dict) and str(item.get("surface", "")).startswith(surface_prefix):
            return f"{concept_id} {item['surface']}"
    raise KeyError(f"no recorded divergence on {concept_id} starting with {surface_prefix!r}")


def _cfg(ref: str) -> Any:
    value = active_config_value(ref)
    if not isinstance(value, (int, float, str)):
        raise KeyError(f"active config has no value for {ref}")
    return value


def _bias(direction: Optional[str]) -> Optional[Bias]:
    return {"LONG": Bias.LONG, "SHORT": Bias.SHORT}.get(str(direction or "").upper())


def _range_edges(active_range: Optional[dict], available_at: int):
    if not active_range or active_range.get("h_ref") is None or active_range.get("l_ref") is None:
        return None
    return range_levels(active_range["h_ref"], active_range["l_ref"], founding=FOUNDING,
                        formed_at=available_at, available_at=available_at, timeframe="M15", clock=CLOCK)


# ── C1  MKT-P01 + terminal map (D4 for V-12) ─────────────────────────────────────────────
def check_terminations(ctx: CheckContext) -> list[Row]:
    rows = []
    for ev in ctx.events:
        if ev.get("event") != "RESET":
            continue
        reason = str(ev.get("reason") or "")
        try:
            entry = match_terminal(reason)
        except UnmatchedTerminalReason:
            rows.append(Row("C1", "MKT-P01", ev.get("candle_index"), UNEXPLAINED, reason, None,
                            "RESET reason matches no terminal_reason_map entry (I-3)"))
            continue
        rows.append(Row("C1", "MKT-P01", ev.get("candle_index"), AGREE, reason,
                        f"{entry.get('authority')}/{entry.get('class')}/{entry.get('code')}"))
    return rows


# ── C2  MKT-E01 sweep ─────────────────────────────────────────────────────────────────────
def check_sweeps(ctx: CheckContext) -> list[Row]:
    rows = []
    for rec in ctx.bars:
        before, after = rec["before"], rec["after"]
        if before.get("current_state") != "RANGE":
            continue
        idx = rec["bar"]
        se = after.get("sweep_event")
        engine_swept = (se is not None and se.get("candle_index") == idx
                        and after.get("current_state") in ("SWEEP", "SHADOW_PENDING"))
        rng = after.get("active_range") if engine_swept else before.get("active_range")
        if (not engine_swept and before.get("range_clock_id") != after.get("range_clock_id")):
            if _range_edges(before.get("active_range"), idx - 1) is not None:
                rows.append(Row("C2", "MKT-E01", idx, NOT_CHECKABLE, None, None,
                                "the range was re-founded on this bar"))
            continue
        edges = _range_edges(rng, idx - 1)
        if edges is None:
            continue
        bar = to_bar(rec["candle"], idx)
        contract = {lvl.side.value: sweep(bar, lvl) for lvl in edges}
        hits = sorted(side for side, ev in contract.items() if ev is not None)
        engine_side = None
        if engine_swept:
            engine_side = "UPPER" if str(se.get("direction")).upper() == "SHORT" else "LOWER"
        if engine_side is None and not hits:
            continue
        if engine_side is not None:
            verdict = AGREE if engine_side in hits else UNEXPLAINED
            note = "" if verdict == AGREE else "engine SWEEP is not GP-04 on the range edge"
            rows.append(Row("C2", "MKT-E01", idx, verdict, engine_side, hits, note))
            for side in hits:
                if side != engine_side:
                    rows.append(Row("C2", "MKT-E01", idx, UNEXPLAINED, engine_side, side,
                                    "two-sided bar: both edges are GP-04 sweeps; the engine records one side"))
        else:
            rows.append(Row("C2", "MKT-E01", idx, UNEXPLAINED, None, hits,
                            "GP-04 sweep of an ACTIVE range edge while the engine stayed in RANGE"))
    return rows


# ── C3  MKT-E04 displacement + TRS-01 thesis ─────────────────────────────────────────────
@dataclass
class Setup:
    """One displaced engine setup, with the contract thesis built for it (None if not buildable)."""

    disp_bar: int
    sweep_bar: Optional[int]
    direction: Optional[str]
    thesis: Any
    note: str = ""


def _contract_thesis(ctx: CheckContext, rec: dict):
    from semantics.trading.thesis import form_thesis

    before = rec["before"]
    se = before.get("sweep_event") or {}
    sweep_idx = se.get("candle_index")
    sweep_bar = to_bar(before.get("sweep_candle"), sweep_idx) or ctx.ohlc(sweep_idx)
    sweep_rec = ctx.by_index.get(sweep_idx)
    rng = (sweep_rec or {}).get("after", {}).get("active_range") or before.get("active_range")
    edges = _range_edges(rng, (sweep_idx or 0) - 1)
    if sweep_bar is None or edges is None:
        return None, "sweep bar or its range not observed"
    side = "UPPER" if str(se.get("direction")).upper() == "SHORT" else "LOWER"
    level = next(lvl for lvl in edges if lvl.side.value == side)
    thesis = form_thesis(sweep_bar, level, to_bar(rec["candle"], rec["bar"]),
                         retrace_fraction=float(_cfg("crt_engine.retrace_reset_pct")),
                         extension_fib=float(_cfg("crt_engine.extension_reset_fib")), clock=CLOCK)
    return thesis, ""


def check_displacements(ctx: CheckContext) -> tuple[list[Row], list[Setup]]:
    rows, setups = [], []
    for rec in ctx.bars:
        before, after = rec["before"], rec["after"]
        if before.get("current_state") != "SWEEP" or after.get("current_state") != "DISPLACEMENT":
            continue
        idx = rec["bar"]
        se = before.get("sweep_event") or {}
        bias = _bias(se.get("direction"))
        bar = to_bar(rec["candle"], idx)
        if bias is None or se.get("price") is None:
            rows.append(Row("C3", "MKT-E04", idx, NOT_CHECKABLE, None, None, "no sweep direction/price"))
            continue
        wick = float(se["price"])
        ok = gp.directional_impulse(bar, wick, bias)
        rows.append(Row("C3", "MKT-E04", idx, AGREE if ok else UNEXPLAINED, "DISPLACEMENT", ok,
                        "" if ok else "engine DISPLACEMENT fails GP-06 against the sweep extreme"))
        thesis, why = _contract_thesis(ctx, rec)
        if why:
            rows.append(Row("C3", "TRS-01", idx, NOT_CHECKABLE, "DISPLACEMENT", None, why))
        elif thesis is None:
            rows.append(Row("C3", "TRS-01", idx, UNEXPLAINED, "DISPLACEMENT", None,
                            "form_thesis returns no thesis: it tests GP-06 against the swept LEVEL price, "
                            "MKT-E04 says the sweep EXTREME (wick)"))
        else:
            same = thesis.direction is bias
            rows.append(Row("C3", "TRS-01", idx, AGREE if same else UNEXPLAINED, se.get("direction"),
                            thesis.direction.value, "" if same else "thesis direction differs"))
        setups.append(Setup(idx, se.get("candle_index"), se.get("direction"), thesis, why))
    return rows, setups


# ── C4  TRS-03 / MKT-E10 invalidation, MKT-E11 spent, MKT-E12 expiry ─────────────────────
_LIVE = ("DISPLACEMENT", "EXPANSION", "RETEST")


def _resets_on(rec: dict) -> list[str]:
    return [str(e.get("reason") or "") for e in rec.get("events") or [] if e.get("event") == "RESET"]


def _clock_ids(ctx: CheckContext, upto: int) -> list:
    """Clock id per bar index 0..upto (carried forward over unobserved indices), so a position in
    the list IS the engine bar index that mark_expired / clock_rollovers report."""
    ids, last = [], None
    for i in range(upto + 1):
        rec = ctx.by_index.get(i)
        if rec is not None:
            last = rec["htf_candle_id"]
        ids.append(last)
    first = next((x for x in ids if x is not None), None)
    return [first if x is None else x for x in ids]


def check_thesis_lifecycle(ctx: CheckContext, setups: Iterable[Setup]) -> list[Row]:
    """Per setup, walk the bars after the displacement until the engine or the contract ends it.

    Contract side: mark_failed / mark_spent per bar, mark_expired with the stage rule (R1-B: a
    rollover expires the thesis only before the episode reaches MKT-P01.EXTENDED). The stage is the
    MKT-P01 projection of the engine state (MKT-P01 rule), so extended_at = first EXPANSION bar.
    """
    from semantics.trading.thesis import ACTIVE, EXPIRED, FAILED, SPENT, mark_expired, mark_failed, mark_spent

    retrace_div = attribute(ctx.concepts, "TRS-03", "ResetLogic.should_reset retrace")
    trade_div = attribute(ctx.concepts, "TRS-03", "ResetLogic.should_reset (crt_engine_v2.py:2876)")
    flip_div = {FAILED: attribute(ctx.concepts, "TRS-03", "ResetLogic.should_reset HTF protection"),
                SPENT: attribute(ctx.concepts, "MKT-E11", "ResetLogic.should_reset HTF protection")}
    rows = []
    last_bar = max(ctx.by_index) if ctx.by_index else 0
    clock_ids = _clock_ids(ctx, last_bar)
    for setup in setups:
        thesis = setup.thesis
        if thesis is None:
            continue
        extended_at = next((r["bar"] for r in ctx.bars
                            if r["bar"] > setup.disp_bar and r["after"].get("current_state") == "EXPANSION"), None)
        expiry = mark_expired(thesis, clock_ids, extended_at=extended_at)
        expired_at = expiry.terminal_at if expiry.status == EXPIRED else None
        survived_flip = False
        prev_clock = clock_ids[setup.disp_bar] if setup.disp_bar < len(clock_ids) else None
        for rec in ctx.bars:
            idx = rec["bar"]
            if idx <= setup.disp_bar:
                continue
            resets = _resets_on(rec)
            engine_retrace = any(_RETRACE_RE.match(r) for r in resets)
            engine_ext = any(r.startswith(_EXTENSION_PREFIX) for r in resets)
            engine_clock = any(r.startswith("HTF changed:") for r in resets)
            trade_open = ((rec["before"].get("trade") or {}).get("status") in ("OPEN", "TP1"))
            bar = to_bar(rec["candle"], idx)
            if rec["htf_candle_id"] != prev_clock and idx != expired_at:
                survived_flip = True        # a rollover the thesis outlives (R1-B)
            prev_clock = rec["htf_candle_id"]
            if idx == expired_at:
                contract = EXPIRED
            else:
                contract = mark_failed(thesis, bar).status
                if contract == ACTIVE:
                    contract = mark_spent(thesis, bar).status
            engine = ("FAILED" if engine_retrace else "SPENT" if engine_ext
                      else "EXPIRED" if engine_clock else ("ACTIVE" if rec["after"].get("current_state") in _LIVE
                                                           or trade_open else "ENDED"))
            if contract == ACTIVE and engine in ("ACTIVE", "ENDED"):
                if engine == "ENDED":
                    break
                continue
            if contract == engine:
                rows.append(Row("C4", _concept_for(contract), idx, AGREE, engine, contract))
            elif trade_open:
                rows.append(Row("C4", _concept_for(contract), idx, EXPECTED_DIVERGENCE, engine, contract,
                                "resets are suppressed while a trade is open", trade_div))
            elif survived_flip and contract in (FAILED, SPENT) and engine == "ACTIVE":
                rows.append(Row("C4", _concept_for(contract), idx, EXPECTED_DIVERGENCE, engine, contract,
                                "after a survived rollover the engine no longer evaluates retrace/extension",
                                flip_div[contract]))
            elif FAILED in (contract, engine) and SPENT not in (contract, engine) and EXPIRED not in (contract, engine):
                rows.append(Row("C4", "TRS-03", idx, EXPECTED_DIVERGENCE, engine, contract,
                                "engine retrace uses the displacement body and >=; contract the sweep->close "
                                "move and strict GP-02", retrace_div))
            else:
                rows.append(Row("C4", _concept_for(contract if contract != ACTIVE else engine), idx,
                                UNEXPLAINED, engine, contract, "thesis lifecycle disagrees"))
            break
    return rows


def _concept_for(status: str) -> str:
    return {"FAILED": "TRS-03", "SPENT": "MKT-E11", "EXPIRED": "MKT-E12"}.get(status, "TRS-01")


# ── C5  TRS-04 / TRS-05 / TRS-06 the engine's trade plan ─────────────────────────────────
def engine_trades(ctx: CheckContext) -> dict:
    """trade id -> {open: first record with it, last: last record with it, close: record where it ended}."""
    trades: dict = {}
    for rec in ctx.bars:
        t = rec["after"].get("trade")
        if t and t.get("id"):
            slot = trades.setdefault(t["id"], {"open": rec, "last": rec, "close": None})
            slot["last"] = rec
            if t.get("status") not in ("PENDING", "OPEN", "TP1") and slot["close"] is None:
                slot["close"] = rec
    return trades


def check_trade_plans(ctx: CheckContext) -> list[Row]:
    rows = []
    entry_div = attribute(ctx.concepts, "TRS-04", "setup.entry_semantics")
    tp1_multiples = sorted({float(_cfg(f"crt_engine.tp1_atr_multiplier_{k}"))
                            for k in ("liq_sweep", "pullback", "breakout", "reversal")})
    tp2_multiple = float(_cfg("crt_engine.tp2_atr_multiplier"))
    buffer_atr = float(_cfg("crt_engine.sl_atr_buffer"))
    trades = engine_trades(ctx)
    if not trades:
        return [Row("C5", cid, None, NOT_CHECKABLE, None, None, "the engine opened no trade on this corpus")
                for cid in ("TRS-04", "TRS-05", "TRS-06")]
    for tid, slot in trades.items():
        rec = slot["open"]
        t, facts = rec["after"]["trade"], rec["after"]
        idx = rec["bar"]
        entry, sl = t["entry_price"], t["sl_price"]
        risk = abs(entry - sl)
        retest = ctx.ohlc(facts.get("retest_candle_index"))
        if retest is None:
            rows.append(Row("C5", "TRS-04", idx, NOT_CHECKABLE, entry, None, f"{tid}: retest bar not observed"))
        else:
            rows.append(Row("C5", "TRS-04", idx, AGREE if entry == retest.close else UNEXPLAINED, entry,
                            retest.close, f"{tid}: entry price = retest close"))
            if t.get("open_candle_index") != retest.index:
                rows.append(Row("C5", "TRS-04", idx, EXPECTED_DIVERGENCE, t.get("open_candle_index"),
                                retest.index, f"{tid}: booked on a later bar than the retest", entry_div))
        disp = facts.get("displacement_candle") or rec["before"].get("displacement_candle")
        atr = facts.get("atr")
        if disp is None or atr is None:
            rows.append(Row("C5", "TRS-05", idx, NOT_CHECKABLE, sl, None, f"{tid}: displacement candle not observed"))
        else:
            want = (disp["low"] - buffer_atr * atr) if t["direction"] == "LONG" else (disp["high"] + buffer_atr * atr)
            same = abs(want - sl) <= 1e-9 * max(1.0, abs(sl))
            rows.append(Row("C5", "TRS-05", idx, AGREE if same else UNEXPLAINED, sl, want,
                            f"{tid}: displacement extreme -/+ {buffer_atr} x ATR (ATR at the open bar)"))
        if risk <= 0:
            rows.append(Row("C5", "TRS-06", idx, UNEXPLAINED, risk, None, f"{tid}: zero risk distance"))
            continue
        r1 = abs(t["tp1_price"] - entry) / risk
        r2 = abs(t["tp2_price"] - entry) / risk
        ok1 = any(abs(r1 - m) <= 1e-9 for m in tp1_multiples)
        rows.append(Row("C5", "TRS-06", idx, AGREE if ok1 else UNEXPLAINED, round(r1, 9), tp1_multiples,
                        f"{tid}: target 1 multiple of R"))
        rows.append(Row("C5", "TRS-06", idx, AGREE if abs(r2 - tp2_multiple) <= 1e-9 else UNEXPLAINED,
                        round(r2, 9), tp2_multiple, f"{tid}: target 2 multiple of R (fixed_r)"))
    return rows


# ── C6  DEX-05/06/07 the position walked under the engine's own settings ─────────────────
_ENGINE_EXIT = {"TP2": "TARGET_FINAL", "STOPPED_STRUCTURAL": "ORIGIN", "TIMEOUT": "TIMEOUT",
                "UNCONFIRMED": "UNCONFIRMED"}


def check_positions(ctx: CheckContext, setups: Iterable[Setup]) -> list[Row]:
    from semantics.execution.fill import fill
    from semantics.execution.portfolio import admit
    from semantics.execution.position import exit_rule, exit_schedule, replay_position
    from semantics.execution.size import position_size
    from semantics.trading.entry import legacy_entry, resting_entry
    from semantics.trading.plan import trade_plan
    from semantics.trading.stop import Stop
    from semantics.trading.target import Target

    by_disp = {s.disp_bar: s for s in setups}
    rows = []
    trades = engine_trades(ctx)
    if not trades:
        return [Row("C6", cid, None, NOT_CHECKABLE, None, None, "the engine opened no trade on this corpus")
                for cid in ("DEX-05", "DEX-06", "DEX-07")]
    for tid, slot in trades.items():
        rec, t = slot["open"], slot["open"]["after"]["trade"]
        facts = rec["after"]
        open_idx = t.get("open_candle_index") or rec["bar"]
        setup = by_disp.get(facts.get("displacement_candle_index"))
        retest = ctx.ohlc(facts.get("retest_candle_index"))
        if setup is None or setup.thesis is None or retest is None:
            rows.append(Row("C6", "DEX-05", open_idx, NOT_CHECKABLE, tid, None, "no contract thesis or retest bar"))
            continue
        semantics_ = str(_cfg("setup.entry_semantics"))
        entry = (legacy_entry(retest, approval_bar=open_idx) if semantics_ == "approval_bar_legacy"
                 else resting_entry(retest))
        stop = Stop("TRS-05", "engine", entry.available_at, float(t["sl_price"]), "engine", 0.0)
        targets = [Target("TRS-06", "engine", entry.available_at, float(t["tp1_price"]), 1, 0.0),
                   Target("TRS-06", "engine", entry.available_at, float(t["tp2_price"]), 2, 0.0)]
        plan = trade_plan(setup.thesis, entry, stop, targets)
        if plan is None:
            rows.append(Row("C6", "DEX-05", open_idx, UNEXPLAINED, tid, None, "contract refuses the engine plan"))
            continue
        size = position_size(plan, risk_fraction=0.01, equity=1.0, equity_basis="initial_capital")
        done = fill(plan.entry, admit(size, [], max_concurrent_positions=1, max_open_risk=1.0, bar=plan.available_at))
        rule = exit_rule("close_on_origin" if active_config_value("crt_engine.displacement_origin_kill_enabled") is True
                         else "hold", plan_bar=plan.available_at,
                         precedence=str(_cfg("crt_engine.displacement_origin_kill_precedence")))
        future = [to_bar(r["candle"], r["bar"]) for r in ctx.bars if r["bar"] > done.bar]
        position = replay_position(plan, done, exit_schedule(0.5, 0.5, plan_bar=plan.available_at), rule,
                                   future, origin_price=t.get("displacement_origin"))
        close = slot["close"]
        if close is None:
            engine_exit, engine_bar = None, None
        else:
            status = close["after"]["trade"]["status"]
            engine_exit = _ENGINE_EXIT.get(status)
            if status == "STOPPED":
                engine_exit = "TRAIL_STOP" if (close["after"]["trade"].get("partial_pnl") or 0) != 0 else "STOP"
            engine_bar = close["bar"]
        contract_exit = position.exit_reason.value if position.exit_reason else None
        same = (engine_exit, engine_bar) == (contract_exit, position.exit_bar)
        rows.append(Row("C6", "DEX-05", open_idx, AGREE if same else UNEXPLAINED,
                        {"exit": engine_exit, "bar": engine_bar},
                        {"exit": contract_exit, "bar": position.exit_bar},
                        f"{tid}: exit reason and bar under the engine's own settings"))
    return rows


# ── C7  mapped feature slots ──────────────────────────────────────────────────────────────
# The batch FeaturePipeline computes its slots in its own code (feature_pipeline.py). The contract
# side here is built from the concept contracts through src/semantics: MKT-E01 from the MKT-L01
# lifecycle walk (any ACTIVE level, consumed once swept or broken), MKT-C04 from its v2 rule
# (`conditions.two_sided_sweep`: MKT-E01 events of both sides within W), MKT-C07 from MKT-C01 +
# MKT-C03, MKT-C03 / MKT-C06 from
# their registered rules. Every disagreement carries a mechanism note (the inventory key).
# Rows: per bar where either side is non-neutral or they differ; MKT-C03 / MKT-C06 (defined on
# every bar) get one summary AGREE row plus a row per disagreeing bar.
UPPER, LOWER = Side.UPPER.value, Side.LOWER.value
E01_TWO_SIDED = "feature_pipeline.liquidity_sweep two-sided bar"
NOTE_TIE = "inclusive tie: close equals the latest swing level"
NOTE_SWEPT = "slot re-fires on the latest swing level, already SWEPT (contract consumes a level once swept)"
NOTE_BROKEN = "slot fires on the latest swing level, already BROKEN by a close beyond it"
NOTE_OLDER = "an older still-ACTIVE swing level was swept (the slot checks only the latest level)"
NOTE_TWO_SIDED = "two-sided bar: the slot encodes one side"
NOTE_PRECEDENCE = ("slot rule fired on both latest levels; UPPER-first precedence encoded a side that is "
                   "not a MKT-E01 event (its level was already consumed), losing this side")
NOTE_OTHER = "unclassified"


@dataclass
class _Contract:
    """Contract-side series over the full corpus, one entry per history row."""

    bars: list
    position: tuple            # MKT-C01, None = no reference (absence)
    momentum: tuple            # MKT-C03
    two_sided: tuple           # MKT-C04 v2, None = no reference
    session: tuple             # MKT-C06
    formed: dict               # side -> set of rows where a MKT-L01 level becomes available
    life: Any                  # events.LevelLifecycle
    latest: dict               # side -> list[index into life.levels | None], latest level available <= i-1
    window: int
    swept_on: dict = field(default_factory=dict)   # bar -> side -> [level index] (the MKT-E01 events)

    def __post_init__(self) -> None:
        for j, end in enumerate(self.life.ended):
            if end is not None and end[0] is LevelStatus.SWEPT:
                self.swept_on.setdefault(end[1], {}).setdefault(self.life.levels[j].side.value, []).append(j)
        for i, evs in enumerate(self.life.events):
            if len(evs) != sum(len(v) for v in self.swept_on.get(i, {}).values()):
                raise AssertionError(f"lifecycle events and SWEPT levels disagree on bar {i}")


def _param(shard: dict, name: str) -> Any:
    """One identity-bearing parameter, resolved from every representation that declares it."""
    refs = {rep["parameterization"][name] for rep in (shard.get("representations") or {}).values()
            if isinstance((rep or {}).get("parameterization"), dict) and name in rep["parameterization"]}
    values = {_cfg(ref) for ref in refs}
    if len(values) != 1:
        raise KeyError(f"{shard.get('producer_id')}: parameter {name!r} resolves to {sorted(map(str, values))}")
    return values.pop()


def _contract_series(history: dict, shard: dict) -> _Contract:
    from semantics.market.conditions import momentum_bias, session, structural_position, two_sided_sweep
    from semantics.market.events import level_lifecycle
    from semantics.market.levels import swing_levels

    k, window = int(_param(shard, "k")), int(_param(shard, "window"))
    o, h, l, c = (history[x] for x in ("open", "high", "low", "close"))
    n = len(c)
    bars = [OhlcBar(o[i], h[i], l[i], c[i], i) for i in range(n)]
    levels = swing_levels(h, l, k=k)
    life = level_lifecycle(levels, bars)
    formed = {UPPER: set(), LOWER: set()}
    by_avail: dict = {}
    for j, lvl in enumerate(levels):
        formed[lvl.side.value].add(lvl.available_at)
        by_avail[(lvl.side.value, lvl.available_at)] = j
    latest = {UPPER: [None] * n, LOWER: [None] * n}
    for side in latest:
        cur = None
        for i in range(n):
            latest[side][i] = cur                  # as of i-1
            cur = by_avail.get((side, i), cur)
    windows = active_config_value("feature_pipeline.session_windows_utc")
    if not isinstance(windows, dict):
        raise KeyError("active config has no feature_pipeline.session_windows_utc")
    return _Contract(
        bars=bars,
        position=structural_position(h, l, c, k=k).values,
        momentum=momentum_bias(c, fast=int(_param(shard, "ema_fast_span")),
                               slow=int(_param(shard, "ema_slow_span"))).values,
        two_sided=two_sided_sweep(h, l, c, k=k, window=window).values,
        session=session(history["timestamp"], basis=str(_param(shard, "session_timestamp_basis")),
                        windows=windows).values,
        formed=formed, life=life, latest=latest, window=window)


def _row(cid: str, bar, verdict: str, key: str, value, contract, note: str = "", ref=None) -> Row:
    return Row("C7", cid, bar, verdict, {"slot": key, "value": value}, contract, note, ref)


def _e01_sides(cs: _Contract, i: int) -> dict:
    """Contract MKT-E01 events on bar i, by side: side -> indices of the levels swept."""
    return cs.swept_on.get(i, {})


def _why_slot_fired(cs: _Contract, i: int, side: str) -> tuple[str, Optional[str]]:
    """Mechanism when the slot fires on `side` and the contract has no MKT-E01 there.
    Returns (note, recorded-divergence prefix or None)."""
    j = cs.latest[side][i]
    if j is None:
        return NOTE_OTHER, None
    status = cs.life.status_before(j, i)
    if status is LevelStatus.SWEPT:
        return NOTE_SWEPT, None
    if status is LevelStatus.BROKEN:
        return NOTE_BROKEN, None
    if cs.bars[i].close == cs.life.levels[j].price:
        return NOTE_TIE, "FM-058 tie"
    return NOTE_OTHER, None


def _slot_rule(cs: _Contract, i: int, side: str) -> bool:
    """Whether the slot's own rule (pierce, close not beyond, latest level) holds on `side` — used
    only to name a mechanism, never as the contract side."""
    j = cs.latest[side][i]
    if j is None:
        return False
    lvl, bar = cs.life.levels[j], cs.bars[i]
    return gp.pierce(bar, lvl.price, lvl.side) and not gp.beyond(bar, lvl.price, lvl.side)


def _why_contract_fired(cs: _Contract, i: int, side: str, swept: list, encoded: Optional[str],
                        hits: dict) -> tuple[str, Optional[str]]:
    """Mechanism when the contract has a MKT-E01 event on `side` and the slot does not encode it.
    Two-sided ONLY when the contract itself has events on both sides; the slot's own rule firing
    on the other side is not enough (that was the 2026-10-03 mislabel, corrected)."""
    if encoded is not None and encoded != side and encoded in hits:
        return NOTE_TWO_SIDED, E01_TWO_SIDED
    if encoded is not None and encoded != side and _slot_rule(cs, i, side):
        return NOTE_PRECEDENCE, None
    if all(j != cs.latest[side][i] for j in swept):
        return NOTE_OLDER, None
    return NOTE_OTHER, None


def _verdict(ctx, cid: str, ref: Optional[str]):
    return (EXPECTED_DIVERGENCE, attribute(ctx.concepts, cid, ref)) if ref else (UNEXPLAINED, None)


def _cmp_liquidity_sweep(ctx, cs, i, bar, key, cid, slot):
    v = int(slot[key])
    encoded = {1: UPPER, -1: LOWER}.get(v)
    hits = _e01_sides(cs, i)
    if encoded is None and not hits:
        return []
    rows = []
    if encoded is not None:
        if encoded in hits:
            rows.append(_row(cid, bar, AGREE, key, v, sorted(hits)))
        else:
            note, ref = _why_slot_fired(cs, i, encoded)
            verdict, dref = _verdict(ctx, cid, ref)
            rows.append(_row(cid, bar, verdict, key, v, sorted(hits), note, dref))
    for side, swept in hits.items():
        if side != encoded:
            note, ref = _why_contract_fired(cs, i, side, swept, encoded, hits)
            verdict, dref = _verdict(ctx, cid, ref)
            rows.append(_row(cid, bar, verdict, key, v, side, note, dref))
    return rows


def _cmp_sweep_detected(ctx, cs, i, bar, key, cid, slot):
    v = bool(slot[key])
    hits = _e01_sides(cs, i)
    if v and hits:
        return [_row(cid, bar, AGREE, key, 1, sorted(hits))]
    if not v and not hits:
        return []
    if v:
        fired = [s for s in (UPPER, LOWER) if _slot_rule(cs, i, s)]
        note, ref = _why_slot_fired(cs, i, fired[0]) if fired else (NOTE_OTHER, None)
    else:
        side, swept = next(iter(hits.items()))
        note, ref = _why_contract_fired(cs, i, side, swept, None, hits)
    verdict, dref = _verdict(ctx, cid, ref)
    return [_row(cid, bar, verdict, key, int(v), sorted(hits), note, dref)]


def _fm060_on_slot(ctx, i: int, window: int) -> Optional[bool]:
    """The superseded v1 rule FM-060, evaluated on the run's own liquidity_sweep slot over W bars.
    Used only to attribute a disagreement, never as the contract side. None if a row is missing."""
    seen = set()
    for t in range(max(0, i - window + 1), i + 1):
        row = ctx.features.get(ctx.history["timestamp"][t])
        if row is None:
            return None
        seen.add(int(row["liquidity_sweep"]))
    return 1 in seen and -1 in seen


def _cmp_two_sided(ctx, cs, i, bar, key, cid, slot):
    """MKT-C04 contract v2 (`conditions.two_sided_sweep`: MKT-E01 events of both sides within W).
    A disagreement is attributed to the recorded FM-060 divergence only when FM-060 on the slot's
    own liquidity_sweep history reproduces the slot value; anything else stays UNEXPLAINED."""
    v, want = bool(slot[key]), cs.two_sided[i]
    if want is None:
        return [] if not v else [_row(cid, bar, UNEXPLAINED, key, 1, None, "slot is 1 with no swing reference")]
    if v == want:
        return [_row(cid, bar, AGREE, key, int(v), want)] if v else []
    if _fm060_on_slot(ctx, i, cs.window) == v:
        return [_row(cid, bar, EXPECTED_DIVERGENCE, key, int(v), want,
                     "slot follows FM-060 on its own liquidity_sweep history",
                     attribute(ctx.concepts, cid, "FM-060 rule on the liquidity_sweep slot"))]
    return [_row(cid, bar, UNEXPLAINED, key, int(v), want, "slot is not FM-060 of its own liquidity_sweep history")]


def _cmp_position(ctx, cs, i, bar, key, cid, slot):
    v, want = int(slot[key]), cs.position[i]
    if want is None:
        if v == 0:
            return [_row(cid, bar, EXPECTED_DIVERGENCE, key, v, None, "no swing reference yet; the slot writes 0",
                         attribute(ctx.concepts, cid, "FM-057"))]
        return [_row(cid, bar, UNEXPLAINED, key, v, None, "slot is non-zero with no swing reference")]
    if v == int(want):
        return [] if want == 0 else [_row(cid, bar, AGREE, key, v, want.name)]
    return [_row(cid, bar, UNEXPLAINED, key, v, want.name, "structural position differs")]


def _cmp_against_momentum(ctx, cs, i, bar, key, cid, slot):
    from semantics.market.conditions import break_against_momentum

    v = int(slot[key])
    want = break_against_momentum(cs.position[i], cs.momentum[i])
    if want is None:
        return [] if v == 0 else [_row(cid, bar, UNEXPLAINED, key, v, None, "slot is non-zero with an undefined input")]
    if v == want:
        return [_row(cid, bar, AGREE, key, v, want)] if v else []
    return [_row(cid, bar, UNEXPLAINED, key, v, want, "break against momentum differs")]


def _cmp_formation(side: str):
    def cmp(ctx, cs, i, bar, key, cid, slot):
        v, want = bool(slot[key]), i in cs.formed[side]
        if v == want:
            return [_row(cid, bar, AGREE, key, int(v), True, f"{side} swing level becomes available")] if v else []
        return [_row(cid, bar, UNEXPLAINED, key, int(v), want, f"{side} swing level formation differs")]
    return cmp


def _cmp_pierce(side: str):
    from semantics.market.events import level_pierce

    def cmp(ctx, cs, i, bar, key, cid, slot):
        v = bool(slot[key])
        j = cs.latest[side][i]
        want = j is not None and level_pierce(cs.bars[i], cs.life.levels[j]) is not None
        if v == want:
            return [_row(cid, bar, AGREE, key, int(v), True, f"pierce of the last {side} swing level")] if v else []
        return [_row(cid, bar, UNEXPLAINED, key, int(v), want, f"pierce of the last {side} swing level differs")]
    return cmp


def _cmp_every_bar(series: str, what: str):
    """For conditions defined on every bar: disagreements per bar, agreement counted (see C7 header)."""
    def cmp(ctx, cs, i, bar, key, cid, slot):
        v, want = int(slot[key]), getattr(cs, series)[i]
        if want is not None and v == int(want):
            return [("agree", cid, key)]
        return [_row(cid, bar, UNEXPLAINED, key, v, want, f"{what} differs")]
    return cmp


# representation key -> (concept the comparator is written for, comparator)
_SLOT_COMPARATORS = {
    "break_of_structure": ("MKT-C01", _cmp_position),
    "trend_bias": ("MKT-C03", _cmp_every_bar("momentum", "momentum bias")),
    "double_sweep": ("MKT-C04", _cmp_two_sided),
    "session": ("MKT-C06", _cmp_every_bar("session", "session ordinal")),
    "change_of_character": ("MKT-C07", _cmp_against_momentum),
    "swing_high": ("MKT-L01", _cmp_formation(UPPER)),
    "swing_low": ("MKT-L01", _cmp_formation(LOWER)),
    "liquidity_sweep": ("MKT-E01", _cmp_liquidity_sweep),
    "sweep_detected": ("MKT-E01", _cmp_sweep_detected),
    "higher_high": ("MKT-E08", _cmp_pierce(UPPER)),
    "lower_low": ("MKT-E08", _cmp_pierce(LOWER)),
}


def check_feature_slots(ctx: CheckContext, shards: dict) -> list[Row]:
    from collections import Counter

    from semantics.integration.observe import ts_key

    rows = []
    for shard in shards.values():
        if shard.get("producer_id") != "feature_pipeline":
            continue
        reps = shard.get("representations") or {}
        if ctx.features is None or ctx.history is None:
            return rows + [Row("C7", rep.get("concept_id"), None, NOT_CHECKABLE, key, None,
                               "the run's feature frame was not observed") for key, rep in reps.items()]
        active = {}
        for key, rep in reps.items():
            spec = _SLOT_COMPARATORS.get(key)
            if spec is None:
                rows.append(Row("C7", rep.get("concept_id"), None, NOT_CHECKABLE, key, None,
                                "no src/semantics implementation to compare this slot with"))
            elif spec[0] != rep.get("concept_id"):
                raise KeyError(f"C7 comparator for {key} is written for {spec[0]}, the shard maps {rep.get('concept_id')}")
            else:
                active[key] = spec
        cs = _contract_series(ctx.history, shard)
        engine_bar = {ts_key(b["candle"]["timestamp"]): b["bar"] for b in ctx.bars if b.get("candle")}
        agreed: Counter = Counter()
        for i, ts in enumerate(ctx.history["timestamp"]):
            slot = ctx.features.get(ts)
            if slot is None or ts not in engine_bar:
                continue
            for key, (cid, cmp) in active.items():
                for out in cmp(ctx, cs, i, engine_bar[ts], key, cid, slot):
                    if isinstance(out, tuple):
                        agreed[out[1:]] += 1
                    else:
                        rows.append(out)
        for (cid, key), n in sorted(agreed.items()):
            rows.append(Row("C7", cid, None, AGREE, {"slot": key, "bars": n}, None,
                            f"{n} bars agree (summary row; disagreeing bars are rows of their own)"))
    return rows


def run_checks(ctx: CheckContext, shards: dict) -> list[Row]:
    rows = check_terminations(ctx)
    rows += check_sweeps(ctx)
    disp_rows, setups = check_displacements(ctx)
    rows += disp_rows
    rows += check_thesis_lifecycle(ctx, setups)
    rows += check_trade_plans(ctx)
    rows += check_positions(ctx, setups)
    rows += check_feature_slots(ctx, shards)
    return rows
