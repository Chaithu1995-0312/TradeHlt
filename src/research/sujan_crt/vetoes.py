"""SEM-031 nested veto chain. Conjunction is admission. SEM-023 never gates."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from config_layer.htf_state import HTFState, HTFStateThresholds, classify_htf_state

from research.sujan_crt.geometry import (
    MEASURABLE_PARENTS,
    Bar,
    DisplacementEvent,
    SweepEvent,
    VetoParams,
    body_bias,
    closed_parents,
    daily_target,
    detect_displacement,
    detect_parent_sweep,
    detect_return,
    location_admitted,
    parent_levels,
    reward_to_risk,
    structural_stop,
)
from research.sujan_crt.score import alignment_score


@dataclass(frozen=True)
class SujanCandidate:
    entry_index: int
    timestamp: object
    direction: str
    entry: float
    stop: float
    target: float
    rr: float
    location_kind: str
    size_hint: str
    romeo_clock: str
    alignment_score: int | None
    weekly_state: str
    daily_state: str
    h4_state: str
    sweep: SweepEvent
    displacement: DisplacementEvent
    rungs: tuple[str, ...]
    max_rung: str


def _thresholds(params: VetoParams) -> HTFStateThresholds:
    return HTFStateThresholds(
        expansion_min_range_ratio=params.expansion_min_range_ratio,
        accumulation_max_range_ratio=params.accumulation_max_range_ratio,
        distribution_min_range_ratio=params.distribution_min_range_ratio,
    )


def _state(parents: Sequence[Bar], params: VetoParams) -> HTFState | None:
    if len(parents) < 2:
        return None
    return classify_htf_state(parents[-2], parents[-1], _thresholds(params))


def _all_levels(by_rule: dict[str, list[Bar]]) -> list[tuple[str, float, int]]:
    out: list[tuple[str, float, int]] = []
    for rule in MEASURABLE_PARENTS:
        out.extend(parent_levels(by_rule.get(rule, []), rule))
    return out


def _sweep_levels(levels: Sequence[tuple[str, float, int]]) -> list[tuple[str, float, int]]:
    return [lv for lv in levels if lv[0].endswith("_high") or lv[0].endswith("_low")]


def detect_funnel_entries(
    bars: Sequence[Bar],
    params: VetoParams,
    atr: Sequence[float],
) -> list[SujanCandidate]:
    """Nested rungs R0..R4. SEM-023 score is diagnostic and never a rung."""
    if len(atr) != len(bars):
        raise ValueError("atr must be aligned 1:1 with bars")
    if not bars:
        return []

    by_rule = {rule: closed_parents(bars, rule) for rule in MEASURABLE_PARENTS}
    candidates: list[SujanCandidate] = []
    seen_entries: set[int] = set()

    for bar in bars:
        visible = {
            rule: [p for p in parents if p.index < bar.index]
            for rule, parents in by_rule.items()
        }
        levels = _all_levels(visible)
        sweep = detect_parent_sweep(bar, _sweep_levels(levels))
        if sweep is None:
            continue
        disp = detect_displacement(bars, sweep, params.max_sweep_age_bars)
        if disp is None:
            continue
        ret = detect_return(bars, disp, params.max_return_age_bars)
        if ret is None or ret.index in seen_entries:
            continue

        visible_e = {
            rule: [p for p in parents if p.index < ret.index]
            for rule, parents in by_rule.items()
        }
        d_e = visible_e["D1"]
        if not d_e:
            continue
        entry = ret.close
        stop = structural_stop(disp)
        target = daily_target(d_e[-1], sweep.direction)
        rr = reward_to_risk(entry, stop, target)
        if rr is None:
            continue
        atr_i = float(atr[ret.index])
        if atr_i <= 0:
            continue

        loc_ok, loc_kind = location_admitted(
            entry,
            _all_levels(visible_e),
            entry_index=ret.index,
            atr=atr_i,
            tolerance_atr=params.location_tolerance_atr,
        )
        d_bias = body_bias(d_e[-1])
        daily_ok = d_bias == sweep.direction
        w_e = visible_e["W1"]
        mn_e = visible_e["MN1"]
        h4_e = visible_e["H4"]
        w_state_e = _state(w_e, params)
        d_state_e = _state(d_e, params)
        not_chase = not (
            w_state_e is HTFState.EXPANSION and d_state_e is HTFState.EXPANSION
        )
        mn_ok = bool(
            mn_e
            and w_e
            and body_bias(mn_e[-1]) == sweep.direction
            and body_bias(w_e[-1]) == sweep.direction
        )
        rr_ok = rr >= params.rr_floor

        rungs = ["R0"]
        if loc_ok:
            rungs.append("R1")
        if loc_ok and daily_ok and not_chase:
            rungs.append("R2")
        if loc_ok and daily_ok and not_chase and mn_ok:
            rungs.append("R3")
        if loc_ok and daily_ok and not_chase and mn_ok and rr_ok:
            rungs.append("R4")

        h4_state = _state(h4_e, params)
        size_hint = "full" if h4_state is HTFState.ACCUMULATION else "half"
        score = alignment_score(
            monthly_aligned=mn_ok,
            weekly_aligned=bool(w_e) and body_bias(w_e[-1]) == sweep.direction,
            daily_objective_clear=daily_ok,
            htf_location=bool(loc_ok),
            liquidity_sweep=True,
            rejection_block=False,
            displacement=True,
            bos_choch=False,
        )
        candidates.append(
            SujanCandidate(
                entry_index=ret.index,
                timestamp=ret.timestamp,
                direction=sweep.direction,
                entry=entry,
                stop=stop,
                target=target,
                rr=rr,
                location_kind=loc_kind or "",
                size_hint=size_hint,
                romeo_clock="UNUSED",
                alignment_score=score,
                weekly_state=w_state_e.value if w_state_e is not None else "UNKNOWN",
                daily_state=d_state_e.value if d_state_e is not None else "UNKNOWN",
                h4_state=h4_state.value if h4_state is not None else "UNKNOWN",
                sweep=sweep,
                displacement=disp,
                rungs=tuple(rungs),
                max_rung=rungs[-1],
            )
        )
        seen_entries.add(ret.index)
    return candidates


def detect_veto_chain_entries(
    bars: Sequence[Bar],
    params: VetoParams,
    atr: Sequence[float],
) -> list[SujanCandidate]:
    """SEM-031 method = R4 only (full nested conjunction)."""
    return [c for c in detect_funnel_entries(bars, params, atr) if c.max_rung == "R4"]
