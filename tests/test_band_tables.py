"""Tests for configs/research/band_tables.json and src/research/band_tables.py.

The JSON file is DATA, not ontology (CLAUDE.md 6.6 — a band partition of a stored
float is not a market concept). It exists so a value's band membership is a
recomputable arithmetic fact instead of a hand-maintained label, per step 3 of
the layered-outcome-ontology plan (docs/implementation_plan/i-have-everything-
i-crispy-dawn.md). Three things this floor must prove, not merely assert:

  1. BT-RR-ECON-V1 is actually exhaustive and mutually exclusive — the user's
     original 4-band draft was neither, and only an arithmetic scan catches
     that class of defect (a doc claiming "exhaustive" is not evidence of it).
  2. BT-RR-STAGE1-V1 is a byte-faithful DESCRIPTION of the incumbent
     src/training/stage1_dataset_builder.RR_BUCKETS, so the two can never
     silently diverge without this floor turning red.
  3. BT-CAPTURE-V1's guard priority (UNDEFINED > UNSTABLE > NEGATIVE > VIOLATION,
     an ambiguity the plan left open and this registration resolved with
     evidence) is exactly what src/research/band_tables.classify_capture()
     implements — not merely documented in a note.

Per E-001 ("a test that cannot fail is not enforcement"), every exhaustiveness/
exclusivity/vocabulary claim below is proven non-vacuous with a planted defect.
This file uses `research.band_tables` (the shared, tested loader) rather than a
second, locally-reimplemented classifier — duplicating that logic here would be
exactly the "second kernel" class of drift risk this whole plan exists to close.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.band_tables import BandTableError, classify, classify_capture, load_band_table

BAND_TABLES_PATH = Path("configs/research/band_tables.json")
_REFERENCE_RUN = Path("logs/XAUUSD/20260913_130531/opportunities.jsonl")
skip_no_reference_run = pytest.mark.skipif(
    not _REFERENCE_RUN.exists(),
    reason="reference dry-scan run not present (logs/** is gitignored; not on every clone)",
)

# The one architectural rule (plan section "The one architectural rule"): number-words
# on anything scanner-derived, world-words only where a cost basis exists. Every table
# in this registry has cost_basis NONE, so none of these may appear in a band name/note.
_WORLD_WORDS = ("WIN", "PROFIT", "TARGET", "BREAKEVEN", "ECON_")
# "LOSS" is excluded from the blanket list because BT-RR-STAGE1-V1 legitimately
# describes the incumbent's pre-existing "LOSS" label as-is (see its own test below);
# it is checked separately, scoped to BT-RR-ECON-V1 / BT-CAPTURE-V1 only.


@pytest.fixture(scope="module")
def registry() -> dict:
    assert BAND_TABLES_PATH.exists(), f"{BAND_TABLES_PATH} must exist"
    with open(BAND_TABLES_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def econ_table() -> dict:
    return load_band_table("BT-RR-ECON-V1")


@pytest.fixture(scope="module")
def stage1_table() -> dict:
    return load_band_table("BT-RR-STAGE1-V1")


@pytest.fixture(scope="module")
def capture_table() -> dict:
    return load_band_table("BT-CAPTURE-V1")


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------

_SINGLE_AXIS_TABLES = ("BT-RR-STAGE1-V1", "BT-RR-ECON-V1")


def test_registry_shape(registry):
    assert registry["schema_version"] == "1.0.0"
    assert set(registry["tables"]) == {"BT-RR-STAGE1-V1", "BT-RR-ECON-V1", "BT-CAPTURE-V1"}
    for table_id, table in registry["tables"].items():
        assert table["unit"]
        assert table["first_match_wins"] is True
        assert table["exhaustive"] is True
        assert table["mutually_exclusive"] is True
        assert table["cost_basis"] == "NONE", (
            f"{table_id}: a band table with a cost model is a different, unregistered claim")
        bands = table["bands"]
        assert bands, f"{table_id}: bands must be non-empty"
        ids = [b["band_id"] for b in bands]
        assert ids == sorted(ids), f"{table_id}: band_id must be ascending"
        assert len(set(ids)) == len(ids), f"{table_id}: duplicate band_id"
    for table_id in _SINGLE_AXIS_TABLES:
        assert registry["tables"][table_id]["axis"] == "rr_achieved"
        assert registry["tables"][table_id]["table_kind"] == "single_axis_interval"
    cap = registry["tables"]["BT-CAPTURE-V1"]
    assert cap["axis"] == "exit_bounded_capture"
    assert cap["table_kind"] == "guarded_two_stage"
    assert cap["inputs"] == ["mfe_r", "rr_achieved"]


def test_load_band_table_rejects_unknown_id():
    with pytest.raises(BandTableError, match="unknown band table"):
        load_band_table("BT-DOES-NOT-EXIST")


def test_classify_rejects_wrong_table_kind(capture_table, econ_table):
    with pytest.raises(BandTableError, match="single_axis_interval"):
        classify(0.5, capture_table)
    with pytest.raises(BandTableError, match="guarded_two_stage"):
        classify_capture(0.5, 0.5, econ_table)


# ---------------------------------------------------------------------------
# BT-RR-ECON-V1 — arithmetic exhaustiveness / exclusivity, not a doc claim
# ---------------------------------------------------------------------------


def test_econ_table_is_exhaustive_and_mutually_exclusive(econ_table):
    """Every probed value gets exactly one band; nothing is unclassified.

    Covers: the atoms exactly, the measured boundary (0.499923/0.500000 from the
    SEM-037 arming-identity verification), the declared-unreachable intervals,
    and a dense scan so no gap or overlap hides between grid points.
    """
    probes = [
        -1e9, -3.0, -1.0000001, -1.0, -0.9999999, -0.5, -1e-9, 0.0, 1e-9,
        0.499923, 0.5, 0.5543, 0.9999999, 1.0, 1.0000001, 1.9988, 1.9999999,
        2.0, 2.0000001, 2.5, 1e9,
    ]
    probes += [-5.0 + i * 0.001 for i in range(10000)]  # dense scan, -5.0..5.0
    for v in probes:
        name = classify(v, econ_table)  # raises if no band matches (not exhaustive)
        assert name is not None


def test_econ_table_nonvacuous_gap_detection(econ_table):
    """E-001 non-vacuity: prove the exhaustiveness check can actually fail."""
    import copy

    widened = copy.deepcopy(econ_table)
    for b in widened["bands"]:
        if b["name"] == "RR_NEG1_TO_0":
            b["lo"] = -0.9  # opens a real gap at -0.95
    with pytest.raises(BandTableError, match="matched no band"):
        classify(-0.95, widened)


def test_econ_table_nonvacuous_overlap_detection(econ_table):
    """First-match-wins hides an overlap rather than raising, so detect it by
    checking every band independently instead of relying on classify()'s
    early return."""
    import copy

    widened = copy.deepcopy(econ_table)
    for b in widened["bands"]:
        if b["name"] == "RR_0_TO_1":
            b["hi"] = 1.5  # now overlaps RR_1_TO_2 on [1.0, 1.5)

    def _matches(bands, value):
        out = []
        for band in bands:
            lo, hi = band["lo"], band["hi"]
            lo_ok = True if lo is None else (value >= lo if band["lo_inclusive"] else value > lo)
            hi_ok = True if hi is None else (value <= hi if band["hi_inclusive"] else value < hi)
            if lo_ok and hi_ok:
                out.append(band["name"])
        return out

    matches = _matches(widened["bands"], 1.2)
    assert len(matches) == 2, "planted overlap was not detected — test is vacuous"


def test_econ_table_atoms_match_sem037_measurement(econ_table):
    """The atom bands' notes must cite the exact counts SEM-037 records.

    Pinned so the two artifacts (this table and the ontology node) cannot
    silently diverge if either is edited independently.
    """
    by_name = {b["name"]: b for b in econ_table["bands"]}
    assert by_name["RR_EQ_NEG1"]["kind"] == "atom"
    assert "30,797" in by_name["RR_EQ_NEG1"]["note"]
    assert by_name["RR_GE_2"]["kind"] == "atom"
    assert "1,344" in by_name["RR_GE_2"]["note"]
    # Structurally-unreachable bands must be present, not omitted (SEM-037's own rule).
    assert "RR_BELOW_NEG1" in by_name
    assert "RR_NEG1_TO_0" in by_name
    assert "STRUCTURALLY_UNREACHABLE" in by_name["RR_BELOW_NEG1"]["note"]
    # RR_NEG1_TO_0 is reachable via TIMEOUT (the 2026-09-14 self-caught correction) —
    # its note must say so, NOT claim structural unreachability for the whole band.
    # The note LEGITIMATELY quotes the earlier WRONG claim verbatim as its own audit
    # trail (append-discipline, CLAUDE.md 6.2 rule 4 — preserve history, never
    # delete truth), so a blanket "must not contain" check is the wrong instrument
    # here; assert the note's actual CONCLUSION instead.
    neg1_to_0_note = by_name["RR_NEG1_TO_0"]["note"]
    assert "Reachable via TIMEOUT" in neg1_to_0_note
    assert "UNREACHABLE FOR SL_HIT" in neg1_to_0_note


def test_no_world_words_in_econ_table(econ_table):
    """Mechanical guard on the plan's one architectural rule."""
    blob = json.dumps(econ_table)
    for word in _WORLD_WORDS:
        assert word not in blob, f"world-word {word!r} leaked into a cost_basis:NONE table"


def test_no_world_words_nonvacuous():
    assert "WIN" in "ECON_MAJOR_WIN", "sanity: the substring check itself must be able to fire"


# ---------------------------------------------------------------------------
# BT-RR-STAGE1-V1 — must stay a faithful description of the incumbent code
# ---------------------------------------------------------------------------


def test_stage1_table_matches_incumbent_rr_buckets_exactly(stage1_table):
    """BT-RR-STAGE1-V1 must reproduce training.stage1_dataset_builder.RR_BUCKETS
    boundary-for-boundary. This table DESCRIBES that constant; it does not
    replace or reconcile it (declared collision, plan section 'Layer 2')."""
    from training.stage1_dataset_builder import RR_BUCKETS

    assert len(stage1_table["bands"]) == len(RR_BUCKETS)
    for band, (low, high, bid, label) in zip(stage1_table["bands"], RR_BUCKETS):
        assert band["band_id"] == bid
        assert band["name"] == label
        want_lo = None if low == float("-inf") else low
        want_hi = None if high == float("inf") else high
        assert band["lo"] == want_lo, f"{label}: lo mismatch"
        assert band["hi"] == want_hi, f"{label}: hi mismatch"
        assert band["hi_inclusive"] is False, f"{label}: RR_BUCKETS is half-open [lo,hi)"


def test_stage1_table_nonvacuous_drift_detection():
    """E-001 non-vacuity: prove the parity check can detect real drift."""
    fake_buckets = (
        (float("-inf"), 0.0, 0, "LOSS"),
        (0.0, 1.5, 1, "SCRATCH"),  # drifted edge: 1.0 -> 1.5
        (1.5, 2.0, 2, "BASE"),
        (2.0, 3.0, 3, "STRONG"),
        (3.0, float("inf"), 4, "OUTLIER"),
    )
    table = load_band_table("BT-RR-STAGE1-V1")
    mismatches = [
        band["name"] for band, (low, high, bid, label) in zip(table["bands"], fake_buckets)
        if band["hi"] != (None if high == float("inf") else high)
    ]
    assert mismatches, "planted drift (1.0 -> 1.5) was not detected — test is vacuous"


def test_stage1_table_status_is_incumbent_described_not_active(stage1_table):
    """Distinguishes 'we described the old thing' from 'we own the old thing'."""
    assert stage1_table["status"] == "INCUMBENT_DESCRIBED"
    assert stage1_table["source"]["module"] == "src/training/stage1_dataset_builder.py"
    assert stage1_table["source"]["constant"] == "RR_BUCKETS"


# ---------------------------------------------------------------------------
# BT-CAPTURE-V1 — the guarded two-stage classifier, and its priority decision
# ---------------------------------------------------------------------------


def test_capture_table_guard_priority_is_declared_and_unique(capture_table):
    priorities = [g["priority"] for g in capture_table["guards"]]
    assert priorities == sorted(priorities)
    assert len(set(priorities)) == len(priorities)
    names_in_order = [g["name"] for g in
                       sorted(capture_table["guards"], key=lambda g: g["priority"])]
    assert names_in_order == [
        "CAPTURE_UNDEFINED", "CAPTURE_UNSTABLE", "CAPTURE_NEGATIVE", "CAPTURE_VIOLATION",
    ]


def test_capture_table_no_magic_numbers(capture_table):
    """Every threshold a guard reads must live in that guard's own params (Config-First
    Doctrine, CLAUDE.md 6.5) — not be re-derivable only from the note text."""
    by_name = {g["name"]: g for g in capture_table["guards"]}
    assert by_name["CAPTURE_UNDEFINED"]["params"]["epsilon"] == pytest.approx(1e-9)
    assert by_name["CAPTURE_UNSTABLE"]["params"]["unstable_threshold"] == pytest.approx(0.05)
    assert by_name["CAPTURE_VIOLATION"]["params"]["violation_threshold"] == pytest.approx(1.0)


def test_classify_capture_matches_each_guard_directly(capture_table):
    """Exercises classify_capture() itself (not a reimplementation) against one
    hand-picked example per guard, plus one real band."""
    # CAPTURE_UNDEFINED: mfe_r effectively zero.
    assert classify_capture(0.0, -1.0, capture_table) == ("CAPTURE_UNDEFINED", None)
    # CAPTURE_UNSTABLE: small positive mfe_r, below the 0.05 threshold.
    assert classify_capture(0.02, -1.0, capture_table) == ("CAPTURE_UNSTABLE", None)
    # CAPTURE_NEGATIVE: mfe_r past the instability threshold, rr negative.
    assert classify_capture(0.3, -0.1, capture_table) == ("CAPTURE_NEGATIVE", None)
    # CAPTURE_VIOLATION: capture > 1 (defect case — arithmetically impossible on real data).
    name, val = classify_capture(0.5, 0.9, capture_table)
    assert name == "CAPTURE_VIOLATION"
    assert val == pytest.approx(1.8)
    # A genuine band once every guard has passed: capture = 0.6/1.0 = 0.6 -> CAPTURE_GOOD.
    name, val = classify_capture(1.0, 0.6, capture_table)
    assert name == "CAPTURE_GOOD"
    assert val == pytest.approx(0.6)


def test_classify_capture_priority_resolves_the_unstable_negative_overlap(capture_table):
    """The plan's four capture states were not declared mutually exclusive; this
    registration's own evidence (2026-09-14 note) found CAPTURE_UNSTABLE is a
    STRICT SUBSET of CAPTURE_NEGATIVE on the reference run (100% overlap, 4,007
    of 4,007) and resolved the ambiguity by priority. This pins that resolution
    directly against the function, not only against the note's prose."""
    # mfe_r=0.02 (< 0.05 threshold) with rr=-1.0: satisfies BOTH raw conditions
    # (0<mfe_r<0.05, and mfe_r>0 with rr<0) — UNSTABLE must win by priority.
    name, _ = classify_capture(0.02, -1.0, capture_table)
    assert name == "CAPTURE_UNSTABLE"


def test_no_world_words_in_capture_table(capture_table):
    blob = json.dumps(capture_table)
    for word in _WORLD_WORDS:
        assert word not in blob, f"world-word {word!r} leaked into a cost_basis:NONE table"


# ---------------------------------------------------------------------------
# Reference-run regression: the true band/capture populations, reproduced from
# the artifact directly, so the corrected counts in this file's notes cannot go
# stale again the way the first draft's counts did (E-001 self-catch,
# 2026-09-14 — see the RR_NEG1_TO_0 / RR_0_TO_1 / RR_1_TO_2 notes), and so the
# BT-CAPTURE-V1 guard-priority resolution is proven against the real corpus,
# not just the four hand-picked examples above.
# ---------------------------------------------------------------------------


def _iter_reference_rows():
    with open(_REFERENCE_RUN, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row.get("type") == "run_header":
                continue
            yield row


@skip_no_reference_run
def test_econ_table_reference_run_band_populations(econ_table):
    counts: dict[str, int] = {}
    n = 0
    for row in _iter_reference_rows():
        n += 1
        counts[classify(row["rr_achieved"], econ_table)] = counts.get(
            classify(row["rr_achieved"], econ_table), 0) + 1

    assert n == 94_332, "reference run row count changed -- re-derive every count in this file"
    assert sum(counts.values()) == n, "band partition is not exhaustive on the real artifact"
    assert counts == {
        "RR_EQ_NEG1": 30_797,
        "RR_NEG1_TO_0": 33,
        "RR_0_TO_1": 56_869,
        "RR_1_TO_2": 5_289,
        "RR_GE_2": 1_344,
    }


@skip_no_reference_run
def test_econ_table_reference_run_outcome_composition(econ_table):
    """Pins WHICH outcome populates each band, not just how many rows.

    This is what the corrected notes claim (e.g. RR_NEG1_TO_0 is TIMEOUT-only,
    RR_1_TO_2 is SL_HIT-only) — a count match alone would not catch a future
    artifact where the composition shifted but the totals happened to agree.
    """
    by_band: dict[str, dict[str, int]] = {}
    for row in _iter_reference_rows():
        band = classify(row["rr_achieved"], econ_table)
        by_band.setdefault(band, {}).setdefault(row["outcome"], 0)
        by_band[band][row["outcome"]] += 1

    assert by_band["RR_EQ_NEG1"] == {"SL_HIT": 30_797}
    assert by_band["RR_NEG1_TO_0"] == {"TIMEOUT": 33}
    assert by_band["RR_0_TO_1"] == {"SL_HIT": 56_851, "TIMEOUT": 18}
    assert by_band["RR_1_TO_2"] == {"SL_HIT": 5_289}
    assert by_band["RR_GE_2"] == {"TP_HIT": 1_344}


@skip_no_reference_run
def test_econ_table_reference_run_tie_break_defect_subset(econ_table):
    """The 1,366-row stop-first-tie-break defect subset (SEM-037) lands
    entirely inside RR_1_TO_2, and nowhere else — the fact the corrected
    RR_1_TO_2 note now asserts explicitly rather than by inheritance."""
    band_of_defect_rows: dict[str, int] = {}
    n_defect = 0
    for row in _iter_reference_rows():
        if row["outcome"] != "SL_HIT":
            continue
        risk = abs(row["entry"] - row["sl"])
        mfe_r = (row["mfe"] / risk) if risk > 0 else 0.0
        if mfe_r >= 2.0:
            n_defect += 1
            band = classify(row["rr_achieved"], econ_table)
            band_of_defect_rows[band] = band_of_defect_rows.get(band, 0) + 1

    assert n_defect == 1_366
    assert band_of_defect_rows == {"RR_1_TO_2": 1_366}


@skip_no_reference_run
def test_capture_table_reference_run_populations(capture_table):
    """Reproduces the exact classify_capture() counts this registration's own
    BT-CAPTURE-V1 notes cite — including the 25,332 CAPTURE_NEGATIVE figure
    that is only correct AFTER the priority-order resolution removes the
    4,007-row CAPTURE_UNSTABLE overlap."""
    counts: dict[str, int] = {}
    n = 0
    for row in _iter_reference_rows():
        n += 1
        risk = abs(row["entry"] - row["sl"])
        mfe_r = (row["mfe"] / risk) if risk > 0 else 0.0
        state, _ = classify_capture(mfe_r, row["rr_achieved"], capture_table)
        counts[state] = counts.get(state, 0) + 1

    assert n == 94_332
    assert sum(counts.values()) == n, "capture classification is not exhaustive on the real artifact"
    assert counts == {
        "CAPTURE_UNDEFINED": 1_491,
        "CAPTURE_UNSTABLE": 4_007,
        "CAPTURE_NEGATIVE": 25_332,
        "CAPTURE_GIVEBACK": 15_648,
        "CAPTURE_MODERATE": 28_515,
        "CAPTURE_GOOD": 19_335,
        "CAPTURE_EFFICIENT": 4,
    }
    assert "CAPTURE_VIOLATION" not in counts, (
        "0 violations measured on the reference run — a violation appearing means a "
        "join/alignment defect, not a finding (SEM-020 known_invariants)")
