"""
measurement_basis.py — the declared measurement-basis vocabulary + comparator
(CH-measurement-basis-declaration, Phase 3 of the identity-chain program).

WHY THIS EXISTS
---------------
The join spine (``identity_spine.py`` / invariant I8) made a spine bar and an oracle
label JOINABLE: both carry ``lt_id``/``trace_id``/``bar_open_ts``. Joinable is not
comparable. Two rows can name the exact same bar and still be two different
measurements, because the number on each was produced under a different ruler:

    axis              spine (trades.csv)        labeler (labels.csv)
    cost_model_id     stamped (CH-cost-model-    absent (id lives only in a
                      identity-stamp)            sidecar manifest.json)
    tie_break         absent                     stamped (labeler.py)
    reference_level   absent                     partial (sl_geom column)
    walk_kernel       implicit (backtest_ledger)  implicit (multi_tp_walk)
    fill_model_id     implicit (engine_intrabar)  stamped (adverse-fill flag)

The repo already has a basis triple — ``identity.tokens.L5_BASIS = ("walk_kernel",
"cost_model_id", "fill_model_id")`` — enforced against closed vocabularies. Its defect
is that two of those three axes are COARSER than the quantities that actually move the
number: ``walk_kernel`` does not distinguish ``tie_break`` (measured +0.0866R on 6.81%
of units, SEM-017), and no axis distinguishes ``reference_level`` (moves
``risk_distance``, hence every R, SEM-017). So two L5 records can carry an IDENTICAL
declared basis and still be non-comparable. That is this module's failure class: not
"skipped != absent" (F-056/079/083/085), but **declared-equal != actually-equal**.

This module does not unify the rulers (that is deliberately deferred — see the plan's
follow-up backlog item 1). It only names them precisely enough that two rows can be
mechanically compared, and refuses comparison — rather than silently returning a number
— whenever they are not the same ruler.

AUTHORITY
---------
Per CLAUDE.md 6.5 Authority Ladder: this module grants information, never economic
value, never production authority. Pure functions + constants; no I/O on import; no
trading decision, PnL, cost arithmetic, or label value is computed or altered here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from identity.tokens import COST_MODEL_IDS, FILL_MODEL_IDS, WALK_KERNELS

# --------------------------------------------------------------------------- #
# The two new axes. walk_kernel / cost_model_id / fill_model_id are NOT
# re-declared here — they are re-exported from identity.tokens, the existing
# authority, so this module never becomes a second, drifting copy of them.
# --------------------------------------------------------------------------- #
TIE_BREAK_PRODUCTION = "production"
TIE_BREAK_OPTIMISTIC = "optimistic"
TIE_BREAK_CLOSE_ONLY = "close_only_no_tiebreak"
TIE_BREAK_OBSERVABLE = "observable_only"   # no intrabar order inferred; branches reported
TIE_BREAKS = frozenset({TIE_BREAK_PRODUCTION, TIE_BREAK_OPTIMISTIC, TIE_BREAK_CLOSE_ONLY,
                        TIE_BREAK_OBSERVABLE})

REF_LEVEL_DISPLACEMENT_EXTREME = "displacement_extreme"   # engine: state.displacement_candle
REF_LEVEL_SIGNAL_BAR_EXTREME = "signal_bar_extreme"       # live/adapter/labeler disp_bar arm
REF_LEVEL_ENTRY_CLOSE_ATR = "entry_close_atr"             # research fixed_atr / forward_walk
REF_LEVEL_SWEEP_EXTREME = "sweep_extreme"                 # K23 F3: engine sl_anchor=sweep_extreme / labeler trailing-N-bar proxy
REFERENCE_LEVELS = frozenset({
    REF_LEVEL_DISPLACEMENT_EXTREME, REF_LEVEL_SIGNAL_BAR_EXTREME, REF_LEVEL_ENTRY_CLOSE_ATR,
    REF_LEVEL_SWEEP_EXTREME,
})

#: First-class sentinel — never a blank, never inferred. Mirrors NOT_REACHED /
#: NOT_JOINED elsewhere in the identity chain (layer_trace.py, build_bar_matrix.py).
UNSTAMPED = "UNSTAMPED"

#: The five axes a basis is declared over, in join-priority order (see
#: ``COMPARE_TABLE`` for why walk_kernel is checked first).
BASIS_AXES = ("walk_kernel", "reference_level", "fill_model_id", "cost_model_id", "tie_break")

#: axis -> its closed vocabulary (frozenset of canonical member strings).
AXIS_VOCAB = {
    "walk_kernel": WALK_KERNELS,
    "cost_model_id": COST_MODEL_IDS,
    "fill_model_id": FILL_MODEL_IDS,
    "tie_break": TIE_BREAKS,
    "reference_level": REFERENCE_LEVELS,
}

# --------------------------------------------------------------------------- #
# Alias tables — the direct analogue of identity_spine.INDEX_ALIASES /
# BAR_TS_ALIASES. Every known spelling of the SAME model maps onto the ONE
# canonical member. canonicalise() never guesses: an unlisted spelling
# returns None, not a best-effort match.
# --------------------------------------------------------------------------- #
#: Five unreconciled spellings of the component cost model found at source
#: 2026-09-23 (costs.py:330, labeler manifest, visual_crt contract prefix,
#: research/config.py:64), all collapsing onto tokens.COST_MODEL_IDS's member.
COST_MODEL_ALIASES = {
    "CM-XAUUSD-COMPONENT-MEASURED-V1": "sem015_component_xauusd",
    "CM-XAUUSD-COMPONENT-MEASURED": "sem015_component_xauusd",
    "component_measured.v1": "sem015_component_xauusd",
    "component_measured": "sem015_component_xauusd",
    "CM-XAUUSD-LEGACY-12BPS": "flat_12bps",
    "CM-XAUUSD-LEGACY-12BPS-V1": "flat_12bps",
    "CM-PROTOCOL-12BPS-BAKED": "flat_12bps",
    "CM-INFO-STAGE-NONE": "none_gross",
    "flat_bps": "flat_12bps",
}

#: provenance.py:70's hardcoded literal -> the kernel's own constant name.
TIE_BREAK_ALIASES = {
    "SL_before_TP": TIE_BREAK_PRODUCTION,
}

#: axis -> its alias table (empty dict where no alias is known yet).
AXIS_ALIASES = {
    "cost_model_id": COST_MODEL_ALIASES,
    "tie_break": TIE_BREAK_ALIASES,
    "walk_kernel": {},
    "fill_model_id": {},
    "reference_level": {},
}


def canonicalise(axis: str, value) -> Optional[str]:
    """Resolve any known spelling of ``value`` on ``axis`` to its ONE canonical member.

    Returns ``None`` — never a guess — when ``value`` is blank/absent or is not a
    recognised spelling (canonical or aliased) on this axis. ``UNSTAMPED`` passed in
    canonicalises to itself: it is a first-class declared value, not an unknown one.
    """
    if axis not in AXIS_VOCAB:
        raise ValueError(f"canonicalise: unknown axis {axis!r} (expected one of {BASIS_AXES})")
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s == UNSTAMPED:
        return UNSTAMPED
    if s in AXIS_VOCAB[axis]:
        return s
    return AXIS_ALIASES[axis].get(s)


@dataclass(frozen=True)
class Basis:
    """The declared measurement basis of one outcome-bearing row.

    ``sl_refloored`` is a row-level DISCLOSURE, not part of the compare key: whether
    ``backtest_v2.py``'s ``[FIX-SL]`` floor fired on this specific row. It varies
    within one run's population, so per-row denial on it would be incoherent — it is
    reported as a population fraction, never silently pooled into the basis itself.
    """
    walk_kernel: str
    cost_model_id: str
    fill_model_id: str
    tie_break: str
    reference_level: str
    sl_refloored: Optional[bool] = None

    def as_dict(self) -> dict:
        return {
            "walk_kernel": self.walk_kernel,
            "cost_model_id": self.cost_model_id,
            "fill_model_id": self.fill_model_id,
            "tie_break": self.tie_break,
            "reference_level": self.reference_level,
            "sl_refloored": self.sl_refloored,
        }


def basis_from_row(row: dict) -> Basis:
    """Build a ``Basis`` from a CSV/dict row, canonicalising every axis.

    A blank, absent, or unrecognised value on any axis becomes ``UNSTAMPED`` — never
    inferred, never defaulted to a plausible-looking guess. This is the single
    fail-closed gate every producer (labeler, backtest) and every reader (``can_compare``,
    invariant I9) shares, so "the value wasn't declared" and "the value doesn't parse"
    are indistinguishable outcomes by design: both mean the row cannot be trusted.
    """
    values = {}
    for axis in BASIS_AXES:
        canon = canonicalise(axis, row.get(axis))
        values[axis] = canon if canon is not None else UNSTAMPED
    raw_floor = row.get("sl_refloored")
    if raw_floor is None or str(raw_floor).strip() == "":
        sl_refloored = None
    else:
        s = str(raw_floor).strip().lower()
        sl_refloored = s in ("true", "1", "yes")
    return Basis(sl_refloored=sl_refloored, **values)


# --------------------------------------------------------------------------- #
# Comparator verdicts — mirrors identity_spine.JOIN_TABLE's shape (a verdict
# constant + a rationale citing the SEM/F id that measured the gap).
# --------------------------------------------------------------------------- #
ALLOW_SAME_BASIS = "ALLOW_SAME_BASIS"
DENY_UNSTAMPED_OPERAND = "DENY_UNSTAMPED_OPERAND"
DENY_WALK_KERNEL_MISMATCH = "DENY_WALK_KERNEL_MISMATCH"
DENY_REFERENCE_LEVEL_MISMATCH = "DENY_REFERENCE_LEVEL_MISMATCH"
DENY_FILL_MODEL_MISMATCH = "DENY_FILL_MODEL_MISMATCH"
DENY_COST_MODEL_MISMATCH = "DENY_COST_MODEL_MISMATCH"
DENY_TIE_BREAK_MISMATCH = "DENY_TIE_BREAK_MISMATCH"

#: (axis, verdict, rationale) — checked in this ORDER, which is load-bearing: a
#: comparison between a spine row (walk_kernel=backtest_ledger) and a labeler row
#: (walk_kernel=multi_tp_walk) differs on walk_kernel AND cost_model_id AND
#: reference_level simultaneously, and walk_kernel must win — a different trade
#: OBJECT (F-088: single-target vs. dual-target-plus-trail) makes every finer-grained
#: axis moot, so naming the root disagreement first is the honest answer, not
#: whichever axis happens to be checked first by accident.
COMPARE_TABLE = (
    ("walk_kernel", DENY_WALK_KERNEL_MISMATCH,
     "F-088: forward_walk/backtest_ledger/multi_tp_walk model different trade objects"),
    ("reference_level", DENY_REFERENCE_LEVEL_MISMATCH,
     "SEM-017: reference level moves risk_distance, hence every R on the row"),
    ("fill_model_id", DENY_FILL_MODEL_MISMATCH,
     "SEM-016: adverse-fill vs perfect-fill changes realised stop exits"),
    ("cost_model_id", DENY_COST_MODEL_MISMATCH,
     "SEM-015: measured ~11x cost gap between the flat and component models on XAUUSD"),
    ("tie_break", DENY_TIE_BREAK_MISMATCH,
     "SEM-017: measured +0.0866R on 6.81% of units between production and optimistic"),
)


def can_compare(a: Basis, b: Basis) -> tuple[str, str]:
    """Whether two rows' declared bases permit a numeric comparison between them.

    Never raises — this is a read-side analytic and a caller reading many rows must
    not have one bad operand abort the whole pass. Returns ``(verdict, rationale)``;
    ``ALLOW_SAME_BASIS`` is the only verdict under which comparing the two rows'
    outcome numbers is licensed. Every other verdict names, by axis, why not.
    """
    for axis in BASIS_AXES:
        av, bv = getattr(a, axis), getattr(b, axis)
        if av == UNSTAMPED or bv == UNSTAMPED:
            bad = "a" if av == UNSTAMPED else "b"
            return DENY_UNSTAMPED_OPERAND, (
                f"{axis} is UNSTAMPED on operand {bad} — a basis is never inferred "
                "from a row that did not record it"
            )
    for axis, verdict, rationale in COMPARE_TABLE:
        av, bv = getattr(a, axis), getattr(b, axis)
        if av != bv:
            return verdict, f"{axis} differs: {av!r} vs {bv!r} ({rationale})"
    return ALLOW_SAME_BASIS, "all five axes agree"


def require_comparable(a: Basis, b: Basis) -> None:
    """Raise unless ``can_compare`` returns ``ALLOW_SAME_BASIS``.

    The gated counterpart to ``can_compare`` — for a caller that wants a numeric
    comparison to be a hard error on mismatch rather than a verdict it must check
    itself. Mirrors the ``check_run(require_all=...)`` / ``can_compare`` two-surface
    pattern already used for the identity-chain invariants.
    """
    verdict, rationale = can_compare(a, b)
    if verdict != ALLOW_SAME_BASIS:
        raise RuntimeError(f"require_comparable: {verdict} — {rationale}")
