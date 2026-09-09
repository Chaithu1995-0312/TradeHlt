"""MC-CTXATTR-XAUUSD-M15-V1 / SEM-036 — contract shape and pre-registration integrity.

CH-v3-unified-market-structure-v1.

F-083's lesson was that a sealed contract can declare a measurement the run never executes, and
nothing notices: `MC-VCRT-XAUUSD-M15-V1` declared an OOS split, an embargo, a purge and control
comparisons while `driver.py` contained zero occurrences of any of them. Shape validation
passed the whole time.

So these tests bind the CONTRACT to the CODE, not just to the schema:
  - the declared multiplicity, split and gate constants exist as module constants in the driver
    (a sweep therefore requires a visible code edit, not a parameter);
  - all 22 declared tests are actually enumerable;
  - the primary metric is orthogonal to the stratum BY CONSTRUCTION, verified numerically on a
    planted case rather than asserted in prose;
  - nothing in the contract or the driver can claim economics while mt00 is UNRUN.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.evidence import context_attribution as ca  # noqa: E402

CONTRACT_PATH = (
    _ROOT / "configs" / "research" / "measurement_contracts" / "instances"
    / "MC-CTXATTR-XAUUSD-M15-V1.json"
)


@pytest.fixture(scope="module")
def contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


# ---- the contract exists and cannot overclaim -------------------------------------------

def test_contract_is_sealed_and_claims_no_economics(contract):
    """The DURABLE invariant, not a snapshot of pre-run state.

    `mt00` legitimately advances UNRUN -> PARTIAL/PASS/FAIL when the run executes, so pinning a
    single value here would just have to be edited after every run — a test that is edited to
    match reality is not a floor. What must never change is the E4 seal: while `mt01_matrix_
    coverage` is UNRUN, `economic_claims_allowed` cannot become true no matter what `mt00` says.
    """
    assert contract["contract_id"] == "MC-CTXATTR-XAUUSD-M15-V1"
    assert contract["schema_version"] == "1.0.0"
    ts = contract["trust_status"]
    assert ts["mt00"] in {"UNRUN", "PASS", "FAIL", "PARTIAL"}
    assert ts["mt01_matrix_coverage"] in {"UNRUN", "COMPLETE", "INCOMPLETE"}
    assert contract["authority"]["economic_admissible"] is False
    if ts["mt01_matrix_coverage"] != "COMPLETE" or ts["mt00"] != "PASS":
        assert ts["economic_claims_allowed"] is False, (
            "economic_claims_allowed cannot be true unless BOTH mt00 PASSES and mt01 coverage "
            "is COMPLETE (MEASUREMENT_CONTRACT.md E4)"
        )


def test_driver_declares_research_authority_only():
    """A driver that could emit an economic verdict would make the contract's declaration
    cosmetic. The flag is a literal in `measure`, not a parameter."""
    rep_keys = ca.measure.__doc__ or ""
    src = (_SRC / "research" / "evidence" / "context_attribution.py").read_text(encoding="utf-8")
    assert '"economic_claims_allowed": False' in src
    assert '"authority": "RESEARCH_ONLY"' in src
    assert "G001" in rep_keys or "G001" in src


# ---- contract <-> code binding (the F-083 floor) ------------------------------------------

def test_declared_multiplicity_matches_the_enumerable_tests(contract):
    declared = contract["metrics"]["multiplicity"]["n_variants_preregistered"]
    actual = len(ca.FAMILIES) * len(ca.DIRECTIONS)
    assert declared == actual == 22, f"contract says {declared}, driver enumerates {actual}"


def test_declared_gate_constants_exist_in_the_driver(contract):
    """Every number the success gate names must be a module constant, so changing it is a
    visible code edit rather than a silent keyword argument at a call site."""
    gate = contract["metrics"]["success_gate"]
    kill = contract["metrics"]["kill_criteria"]
    assert ca.MIN_CELL_N == 30 and "n >= 30" in gate
    assert ca.BH_Q == 0.10 and "q=0.10" in gate
    assert ca.PERM_BLOCK_BARS == 40 and "block=40" in gate
    assert ca.PERM_N == 199 and "n_perm=199" in gate
    assert ca.PASS_CEILING == 6 and "6 of 22" in gate
    assert ca.K == 0.5 and "k=0.5 frozen" in gate
    assert "NEW MC-* id" in kill


def test_split_constants_come_from_the_frozen_shared_calendar(contract):
    """Imported from `asymmetry_contract`, not redeclared — a local copy could drift and
    silently spend a different holdout."""
    assert ca.EMBARGO_BARS == 96
    assert ca.HORIZON_BARS == 40
    assert str(ca.HOLDOUT_START) == "2025-12-24 19:15:00"
    assert "2025-12-24 19:15:00" in contract["splits"]["oos_fraction_or_dates"]
    assert contract["splits"]["embargo"].startswith("96 ")


def test_the_run_writes_the_split_it_used(contract):
    """The direct F-083 remediation: the split manifest is produced BY the run, and names the
    resolved boundary index, not just the declared date."""
    assert "WRITES the resolved boundary" in contract["splits"]["oos_fraction_or_dates"]
    src = (_SRC / "research" / "evidence" / "context_attribution.py").read_text(encoding="utf-8")
    assert "first_holdout_bar_index" in src
    assert "split_manifest.json" in src


def test_every_declared_family_has_a_predicate(contract):
    """A family named in `features.name_binding` but absent from `FAMILIES` would be declared
    and never measured."""
    declared = {
        k[len("agree_"):] for k in contract["features"]["name_binding"]
        if k.startswith("agree_") and k != "agree_composite"
    }
    assert declared == set(ca.SINGLE_FAMILIES), (
        f"contract declares {sorted(declared)}, driver implements "
        f"{sorted(ca.SINGLE_FAMILIES)}"
    )
    assert "composite" in ca.FAMILIES


def test_controls_named_in_the_gate_are_implemented(contract):
    gate = contract["metrics"]["success_gate"]
    assert "long_only" in gate and "shuffled-context" in gate
    assert callable(ca.long_only_control)
    assert callable(ca.shuffled_context_control)
    assert callable(ca.block_permutation_p)


# ---- the primary metric behaves as the contract claims -------------------------------------

def _row(bar, side, stratum, y, agree):
    return {"bar_index": bar, "decision_ts": f"2025-01-01 00:{bar % 60:02d}:00",
            "ts": None, "side": side, "stratum": stratum,
            "y_R_net": y, "y_R_gross": y,
            "snap": {"parent_bias": ("LONG" if agree else "SHORT")}}


def test_delta_within_stratum_is_zero_when_context_is_pure_crt_proxy():
    """THE load-bearing property, verified numerically rather than argued.

    Planted confound: within each stratum the context has NO effect (agree and disagree rows
    have identical outcomes), but agreement is concentrated in the high-mean stratum and
    disagreement in the low-mean one, and the cells are deliberately lopsided (180/20). A
    marginal overlay reads that as a large effect. The within-stratum overlay must read
    exactly 0 — which is what "beyond CRT alone" has to mean.

    The lopsided split is the point: it is what exposed the two defects this metric was fixed
    for (uncentered y leaves a `k * stratum_mean * (n_a - n_d) / n` term, and a single-cell
    stratum is a rescale rather than a contrast).
    """
    rows = []
    i = 0
    for _ in range(180):
        rows.append(_row(i, "long", "RANGE", 1.0, agree=True)); i += 1
    for _ in range(20):
        rows.append(_row(i, "long", "RANGE", 1.0, agree=False)); i += 1
    for _ in range(20):
        rows.append(_row(i, "long", "SWEEP", -1.0, agree=True)); i += 1
    for _ in range(180):
        rows.append(_row(i, "long", "SWEEP", -1.0, agree=False)); i += 1

    pred = ca.SINGLE_FAMILIES["parent_crt"]
    within = ca.delta_within_stratum(rows, pred, "long", "y_R_net")["delta"]
    marginal = ca.delta_marginal(rows, pred, "long", "y_R_net")["delta"]

    assert within == pytest.approx(0.0, abs=1e-12), (
        f"within-stratum delta {within} is non-zero on a pure CRT proxy -- the primary metric "
        "is not orthogonal to the stratum"
    )
    assert abs(marginal) > 0.3, (
        f"marginal delta {marginal} should be large here; if it is not, the fixture no longer "
        "demonstrates the confound the metric exists to remove"
    )


def test_single_cell_strata_contribute_nothing():
    """A stratum where every row agrees is a uniform rescale by (1+k), not a contrast. Folding
    it in would report `k` as an effect for a context that never varied."""
    rows = [_row(i, "long", "RANGE", 1.0, agree=True) for i in range(200)]
    out = ca.delta_within_stratum(rows, ca.SINGLE_FAMILIES["parent_crt"], "long", "y_R_net")
    assert out["delta"] is None
    assert out["n_strata"] == 0
    assert out["stratum_occupancy"]["RANGE"]["informative"] is False


def test_unbalanced_cells_alone_do_not_manufacture_an_effect():
    """The centering correction, isolated.

    One stratum, non-zero mean, wildly unbalanced cells, and no real effect. Uncentered this
    would report `k * m * (n_a - n_d) / n` = 0.5 * -0.29 * (190-10)/200, a spurious signal of
    roughly the size the program is looking for.
    """
    rows = [_row(i, "long", "RANGE", -0.29, agree=True) for i in range(190)]
    rows += [_row(i, "long", "RANGE", -0.29, agree=False) for i in range(190, 200)]
    out = ca.delta_within_stratum(rows, ca.SINGLE_FAMILIES["parent_crt"], "long", "y_R_net")
    assert out["delta"] == pytest.approx(0.0, abs=1e-12)
    assert out["n_agree"] == 190 and out["n_disagree"] == 10


def test_delta_within_stratum_detects_a_real_within_stratum_effect():
    """The mirror of the test above: the metric must not be trivially zero.

    Same single stratum, context genuinely predictive. A metric that returned 0 everywhere
    would pass the orthogonality test for the wrong reason.
    """
    rows = [_row(i, "long", "RANGE", 1.0, agree=True) for i in range(200)]
    rows += [_row(i, "long", "RANGE", -1.0, agree=False) for i in range(200, 400)]
    within = ca.delta_within_stratum(rows, ca.SINGLE_FAMILIES["parent_crt"],
                                    "long", "y_R_net")["delta"]
    assert within == pytest.approx(ca.K, abs=1e-9), (
        f"expected delta == k ({ca.K}) for a perfectly predictive context, got {within}"
    )


def test_abstaining_families_are_excluded_from_both_cells():
    """`None` means NO READING, not disagreement.

    Counting an absent zone as a disagree would silently convert "we could not look" into
    evidence against the family — the single easiest way to manufacture a result here, since
    most SMC zones are absent on most bars.
    """
    rows = [_row(i, "long", "RANGE", 1.0, agree=True) for i in range(40)]
    rows += [_row(i, "long", "RANGE", -1.0, agree=False) for i in range(40, 70)]
    abstain = [_row(i, "long", "RANGE", 5.0, agree=True) for i in range(70, 100)]
    for r in abstain:
        r["snap"] = {"parent_bias": "NONE"}
    rows += abstain

    out = ca.delta_within_stratum(rows, ca.SINGLE_FAMILIES["parent_crt"], "long", "y_R_net")
    assert out["n_agree"] == 40
    assert out["n_disagree"] == 30
    assert out["n_scored"] == 70, "abstaining rows leaked into a cell"

    # The abstainers carry an extreme outcome (+5.0). If they were being folded in anywhere,
    # the delta would move; it must not.
    without = [r for r in rows if r["snap"].get("parent_bias") != "NONE"]
    assert out["delta"] == pytest.approx(
        ca.delta_within_stratum(without, ca.SINGLE_FAMILIES["parent_crt"],
                                "long", "y_R_net")["delta"]
    )


def test_benjamini_hochberg_is_monotone_and_rejects_a_pure_null():
    """22 uniform p-values must yield zero survivors at q=0.10."""
    pvals = {f"t{i}": (i + 1) / 23.0 for i in range(22)}
    assert not any(ca.benjamini_hochberg(pvals, q=0.10).values())

    strong = dict(pvals)
    strong["t0"] = 0.0001
    assert ca.benjamini_hochberg(strong, q=0.10)["t0"] is True


def test_permutation_p_has_a_floor_and_never_reports_zero():
    """With 199 permutations the attainable floor is 0.005. Reporting 0.0 would claim more
    resolution than the design has."""
    src = (_SRC / "research" / "evidence" / "context_attribution.py").read_text(encoding="utf-8")
    assert "(hits + 1) / (PERM_N + 1)" in src


# ---- the honest-limits declarations -------------------------------------------------------

def test_contract_records_the_every_bar_population_limitation(contract):
    """The single most important caveat: this is not production's executed trades."""
    note = contract["authority"]["note"]
    assert "EVERY-BAR" in note
    assert "NOT on production's executed trades" in note
    assert "3 trades" in note


def test_contract_forbids_the_known_substitution_traps(contract):
    forbidden = " ".join(contract["metrics"]["forbidden_metric_substitutions"])
    assert "delta_marginal presented as the PRIMARY" in forbidden
    assert "E>0" in forbidden
    assert "long_only omitted" in forbidden
    assert "window_truncated" in forbidden
    aliases = " ".join(contract["features"]["forbidden_aliases"])
    assert "crt_state_resolved" in aliases
    assert "session" in aliases
