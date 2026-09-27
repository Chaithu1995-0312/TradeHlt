"""Unit tests for the measurement-basis declaration vocabulary + comparator
(CH-measurement-basis-declaration, Phase 3 of the identity-chain program).

Pins: the closed vocabularies (new + re-exported), the alias tables that
reconcile every known spelling of the same cost model / tie-break onto one
canonical member, ``canonicalise``'s never-guess contract, ``basis_from_row``'s
fail-closed UNSTAMPED default, and every verdict ``can_compare`` can return.
"""
from __future__ import annotations

import pytest

from governance.measurement_basis import (
    ALLOW_SAME_BASIS,
    AXIS_VOCAB,
    BASIS_AXES,
    COMPARE_TABLE,
    COST_MODEL_ALIASES,
    DENY_COST_MODEL_MISMATCH,
    DENY_FILL_MODEL_MISMATCH,
    DENY_REFERENCE_LEVEL_MISMATCH,
    DENY_TIE_BREAK_MISMATCH,
    DENY_UNSTAMPED_OPERAND,
    DENY_WALK_KERNEL_MISMATCH,
    REF_LEVEL_DISPLACEMENT_EXTREME,
    REF_LEVEL_ENTRY_CLOSE_ATR,
    REF_LEVEL_SIGNAL_BAR_EXTREME,
    REF_LEVEL_SWEEP_EXTREME,
    REFERENCE_LEVELS,
    TIE_BREAK_ALIASES,
    TIE_BREAK_CLOSE_ONLY,
    TIE_BREAK_OPTIMISTIC,
    TIE_BREAK_PRODUCTION,
    TIE_BREAKS,
    UNSTAMPED,
    Basis,
    basis_from_row,
    can_compare,
    canonicalise,
    require_comparable,
)
from identity.tokens import COST_MODEL_IDS, FILL_MODEL_IDS, WALK_KERNELS


def _row(**overrides) -> dict:
    """A fully-stamped labeler-shaped row, PRIMARY arm, overridable per test."""
    base = dict(
        walk_kernel="multi_tp_walk",
        cost_model_id="sem015_component_xauusd",
        fill_model_id="sem016_adverse",
        tie_break=TIE_BREAK_PRODUCTION,
        reference_level=REF_LEVEL_SIGNAL_BAR_EXTREME,
    )
    base.update(overrides)
    return base


def _trades_row(**overrides) -> dict:
    """A fully-stamped trades.csv-shaped row."""
    base = dict(
        walk_kernel="backtest_ledger",
        cost_model_id="backtest_g1g2_v2",
        fill_model_id="engine_intrabar",
        tie_break=TIE_BREAK_PRODUCTION,
        reference_level=REF_LEVEL_DISPLACEMENT_EXTREME,
        sl_refloored="false",
    )
    base.update(overrides)
    return base


class TestAxisVocabularies:
    def test_basis_axes_are_exactly_five(self):
        assert set(BASIS_AXES) == {
            "walk_kernel", "cost_model_id", "fill_model_id", "tie_break", "reference_level",
        }

    def test_three_axes_are_re_exported_not_redeclared(self):
        # Identity: the SAME frozenset objects as identity.tokens, never a copy.
        assert AXIS_VOCAB["walk_kernel"] is WALK_KERNELS
        assert AXIS_VOCAB["cost_model_id"] is COST_MODEL_IDS
        assert AXIS_VOCAB["fill_model_id"] is FILL_MODEL_IDS

    def test_tie_break_has_three_members(self):
        assert TIE_BREAKS == {TIE_BREAK_PRODUCTION, TIE_BREAK_OPTIMISTIC, TIE_BREAK_CLOSE_ONLY}

    def test_reference_level_has_four_members(self):
        assert REFERENCE_LEVELS == {
            REF_LEVEL_DISPLACEMENT_EXTREME, REF_LEVEL_SIGNAL_BAR_EXTREME, REF_LEVEL_ENTRY_CLOSE_ATR,
            REF_LEVEL_SWEEP_EXTREME,
        }

    def test_every_axis_has_a_vocab_entry(self):
        for axis in BASIS_AXES:
            assert axis in AXIS_VOCAB


class TestCanonicalise:
    @pytest.mark.parametrize("spelling", sorted(COST_MODEL_ALIASES))
    def test_every_known_cost_model_spelling_canonicalises(self, spelling):
        canon = canonicalise("cost_model_id", spelling)
        assert canon == COST_MODEL_ALIASES[spelling]
        assert canon in COST_MODEL_IDS

    def test_canonical_member_passed_through_unchanged(self):
        assert canonicalise("cost_model_id", "sem015_component_xauusd") == "sem015_component_xauusd"

    def test_unrecognised_spelling_returns_none_never_a_guess(self):
        assert canonicalise("cost_model_id", "some_made_up_model_id") is None

    def test_blank_and_none_return_none(self):
        assert canonicalise("cost_model_id", "") is None
        assert canonicalise("cost_model_id", None) is None
        assert canonicalise("cost_model_id", "   ") is None

    def test_unstamped_passes_through_as_itself(self):
        assert canonicalise("cost_model_id", UNSTAMPED) == UNSTAMPED
        assert canonicalise("tie_break", UNSTAMPED) == UNSTAMPED

    def test_provenance_hardcoded_literal_canonicalises_to_production(self):
        assert canonicalise("tie_break", "SL_before_TP") == TIE_BREAK_PRODUCTION
        assert TIE_BREAK_ALIASES["SL_before_TP"] == TIE_BREAK_PRODUCTION

    def test_unknown_axis_raises(self):
        with pytest.raises(ValueError):
            canonicalise("not_a_real_axis", "x")


class TestBasisFromRow:
    def test_fully_stamped_row_round_trips(self):
        b = basis_from_row(_row())
        assert b.walk_kernel == "multi_tp_walk"
        assert b.cost_model_id == "sem015_component_xauusd"
        assert b.tie_break == TIE_BREAK_PRODUCTION
        assert b.reference_level == REF_LEVEL_SIGNAL_BAR_EXTREME

    def test_missing_axis_becomes_unstamped_not_blank(self):
        row = _row()
        del row["cost_model_id"]
        b = basis_from_row(row)
        assert b.cost_model_id == UNSTAMPED

    def test_unrecognised_value_becomes_unstamped_not_guessed(self):
        b = basis_from_row(_row(cost_model_id="totally_unknown_spelling"))
        assert b.cost_model_id == UNSTAMPED

    def test_fifth_cost_model_spelling_from_labeler_manifest_canonicalises(self):
        b = basis_from_row(_row(cost_model_id="CM-XAUUSD-COMPONENT-MEASURED-V1"))
        assert b.cost_model_id == "sem015_component_xauusd"

    def test_sl_refloored_absent_is_none(self):
        assert basis_from_row(_row()).sl_refloored is None

    def test_sl_refloored_parses_true_false(self):
        assert basis_from_row(_row(sl_refloored="true")).sl_refloored is True
        assert basis_from_row(_row(sl_refloored="False")).sl_refloored is False

    def test_sl_refloored_is_not_part_of_compare_key(self):
        a = basis_from_row(_trades_row(sl_refloored="true"))
        b = basis_from_row(_trades_row(sl_refloored="false"))
        verdict, _ = can_compare(a, b)
        assert verdict == ALLOW_SAME_BASIS


class TestCanCompare:
    def test_identical_basis_allows(self):
        a = basis_from_row(_row())
        b = basis_from_row(_row())
        verdict, rationale = can_compare(a, b)
        assert verdict == ALLOW_SAME_BASIS
        assert rationale

    def test_never_raises_on_mismatched_operands(self):
        a = basis_from_row(_row())
        b = basis_from_row(_row(cost_model_id="unknown"))
        # must not raise
        can_compare(a, b)

    def test_unstamped_operand_denies_before_any_mismatch_check(self):
        a = basis_from_row(_row())
        b = basis_from_row(_row(cost_model_id=""))
        verdict, rationale = can_compare(a, b)
        assert verdict == DENY_UNSTAMPED_OPERAND
        assert "cost_model_id" in rationale

    def test_pre_change_unstamped_artifact_never_silently_equal(self):
        stamped = basis_from_row(_row())
        unstamped = Basis(
            walk_kernel=UNSTAMPED, cost_model_id=UNSTAMPED, fill_model_id=UNSTAMPED,
            tie_break=UNSTAMPED, reference_level=UNSTAMPED,
        )
        verdict, _ = can_compare(stamped, unstamped)
        assert verdict == DENY_UNSTAMPED_OPERAND

    def test_tie_break_mismatch_named_when_only_axis_that_differs(self):
        a = basis_from_row(_row(tie_break=TIE_BREAK_PRODUCTION))
        b = basis_from_row(_row(tie_break=TIE_BREAK_OPTIMISTIC))
        verdict, rationale = can_compare(a, b)
        assert verdict == DENY_TIE_BREAK_MISMATCH
        assert "SEM-017" in rationale

    def test_reference_level_mismatch_named_when_only_axis_that_differs(self):
        a = basis_from_row(_row(reference_level=REF_LEVEL_SIGNAL_BAR_EXTREME))
        b = basis_from_row(_row(reference_level=REF_LEVEL_ENTRY_CLOSE_ATR))
        verdict, rationale = can_compare(a, b)
        assert verdict == DENY_REFERENCE_LEVEL_MISMATCH
        assert "SEM-017" in rationale

    def test_cost_model_mismatch_named_when_only_axis_that_differs(self):
        a = basis_from_row(_row(cost_model_id="sem015_component_xauusd"))
        b = basis_from_row(_row(cost_model_id="flat_12bps"))
        verdict, rationale = can_compare(a, b)
        assert verdict == DENY_COST_MODEL_MISMATCH
        assert "SEM-015" in rationale

    def test_fill_model_mismatch_named_when_only_axis_that_differs(self):
        a = basis_from_row(_row(fill_model_id="sem016_adverse"))
        b = basis_from_row(_row(fill_model_id="touch_exact"))
        verdict, rationale = can_compare(a, b)
        assert verdict == DENY_FILL_MODEL_MISMATCH
        assert "SEM-016" in rationale

    def test_walk_kernel_mismatch_named_when_only_axis_that_differs(self):
        a = basis_from_row(_row(walk_kernel="multi_tp_walk"))
        b = basis_from_row(_row(walk_kernel="forward_walk_intrabar_fixed"))
        verdict, rationale = can_compare(a, b)
        assert verdict == DENY_WALK_KERNEL_MISMATCH
        assert "F-088" in rationale

    def test_spine_vs_labeler_row_denies_on_walk_kernel_first(self):
        """The comparison the repo most wants to make informally, refused honestly.

        A trades.csv row and a labels.csv row differ on walk_kernel AND
        reference_level AND cost_model_id simultaneously. walk_kernel must win:
        a different trade OBJECT (F-088) makes every finer-grained axis moot.
        """
        spine = basis_from_row(_trades_row())
        labeler = basis_from_row(_row())
        verdict, rationale = can_compare(spine, labeler)
        assert verdict == DENY_WALK_KERNEL_MISMATCH
        assert "backtest_ledger" in rationale
        assert "multi_tp_walk" in rationale

    def test_compare_table_order_matches_walk_kernel_first(self):
        assert COMPARE_TABLE[0][0] == "walk_kernel"

    def test_every_deny_verdict_is_reachable_via_compare_table(self):
        verdicts = {v for _, v, _ in COMPARE_TABLE}
        assert verdicts == {
            DENY_WALK_KERNEL_MISMATCH, DENY_REFERENCE_LEVEL_MISMATCH,
            DENY_FILL_MODEL_MISMATCH, DENY_COST_MODEL_MISMATCH, DENY_TIE_BREAK_MISMATCH,
        }


class TestRequireComparable:
    def test_allows_silently(self):
        a = basis_from_row(_row())
        b = basis_from_row(_row())
        require_comparable(a, b)  # must not raise

    def test_raises_on_any_deny_verdict(self):
        a = basis_from_row(_row(tie_break=TIE_BREAK_PRODUCTION))
        b = basis_from_row(_row(tie_break=TIE_BREAK_OPTIMISTIC))
        with pytest.raises(RuntimeError, match="DENY_TIE_BREAK_MISMATCH"):
            require_comparable(a, b)

    def test_raises_on_unstamped_operand(self):
        a = basis_from_row(_row())
        b = basis_from_row(_row(walk_kernel=""))
        with pytest.raises(RuntimeError, match="DENY_UNSTAMPED_OPERAND"):
            require_comparable(a, b)
