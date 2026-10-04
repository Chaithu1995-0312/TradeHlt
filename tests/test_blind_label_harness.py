"""
Blind-labeling descriptive-fidelity test — mechanical integrity floor.

Why this file exists: the whole point of the blind-label program (see
docs/research/preregistration-blind-label-descriptive-fidelity.md) is that the labeler never
sees the feature values being scored against. "The HTML doesn't show the answers" is a claim
about generated output, not a property that holds just because the generator script intends
it to — so it gets a test that can fail, not a docstring promise (CLAUDE.md E-001: a test that
can't fail isn't enforcement).

Covers:
  1. The generated HTML leaks no answer token, no scored-feature value, no timestamp.
  2. The manifest (the answer key) is never referenced by the HTML by path or content.
  3. Sampling is deterministic under a fixed seed (same seed -> byte-identical manifest,
     modulo the generated_at-style fields this generator doesn't even emit).
  4. The scorer distinguishes a perfect labeler from a random one on synthetic data — if it
     can't, it isn't measuring anything (same E-001 principle applied to the scorer).
  5. Context windows never reach past the target bar (no lookahead shown to the labeler).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SRC = ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

SAMPLER = ROOT / "scripts" / "analysis" / "blind_label_sample.py"
SCORER_MODULE = "scripts.analysis.blind_label_score"


def _run_sampler(tmp_path: Path, seed: int) -> Path:
    out_dir = tmp_path / f"seed_{seed}"
    result = subprocess.run(
        [sys.executable, str(SAMPLER), "--seed", str(seed), "--output-dir", str(out_dir)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, f"sampler failed:\nSTDOUT:{result.stdout}\nSTDERR:{result.stderr}"
    return out_dir


@pytest.fixture(scope="module")
def sample_dir(tmp_path_factory) -> Path:
    tmp_path = tmp_path_factory.mktemp("blind_label")
    return _run_sampler(tmp_path, seed=20260801)


# ── 1 & 2: blinding ──────────────────────────────────────────────────────────────────────────

def test_html_leaks_no_answer_value(sample_dir):
    manifest = json.loads((sample_dir / "sample_manifest.json").read_text(encoding="utf-8"))
    html_text = (sample_dir / "session_01.html").read_text(encoding="utf-8")

    for item in manifest["items"]:
        for feature, value in item["answers"].items():
            # The four raw codes (-1, 0, 1, 2, 1.0, -1.0, 0.0) are too common in generic
            # markup/CSS/JS to grep for directly (e.g. "1" appears in <h3>Chart 1 of ...).
            # Instead assert the FEATURE NAMES themselves never appear -- if the answer
            # columns aren't named anywhere in the page, their values can't be labeled as
            # answers even where a bare digit coincides.
            assert feature not in html_text, (
                f"HTML references scored feature name '{feature}' — answer key exposure risk"
            )
        # Timestamps must not appear (they'd let a labeler correlate against known-price charts).
        assert item["target_timestamp"] not in html_text
        assert item["item_id"] in html_text, "item_id must be present (needed for CSV export)"


def test_html_never_references_manifest(sample_dir):
    html_text = (sample_dir / "session_01.html").read_text(encoding="utf-8")
    assert "sample_manifest" not in html_text
    assert "manifest" not in html_text.lower()


def test_html_has_no_feature_column_names(sample_dir):
    html_text = (sample_dir / "session_01.html").read_text(encoding="utf-8")
    for banned in ("trend_bias", "volatility_regime", "liquidity_sweep",
                   "break_of_structure", "session", "hour_of_day", "disp_strength"):
        assert banned not in html_text


def test_context_window_never_reaches_past_target(sample_dir):
    """No lookahead shown: the target bar must be the LAST bar in every OHLCV window."""
    manifest = json.loads((sample_dir / "sample_manifest.json").read_text(encoding="utf-8"))
    for item in manifest["items"]:
        assert item["context_end_index"] == item["target_row_index"]
        assert item["context_start_index"] == (
            item["target_row_index"] - manifest["context_bars"] + 1
        )


# ── 3: determinism ──────────────────────────────────────────────────────────────────────────

def test_same_seed_is_deterministic(tmp_path):
    d1 = _run_sampler(tmp_path, seed=999)
    d2 = _run_sampler(tmp_path, seed=999)
    m1 = json.loads((d1 / "sample_manifest.json").read_text(encoding="utf-8"))
    m2 = json.loads((d2 / "sample_manifest.json").read_text(encoding="utf-8"))
    ids1 = [it["item_id"] for it in m1["items"]]
    ids2 = [it["item_id"] for it in m2["items"]]
    assert ids1 == ids2, "same seed must produce the same items in the same display order"
    rows1 = [it["target_row_index"] for it in m1["items"]]
    rows2 = [it["target_row_index"] for it in m2["items"]]
    assert rows1 == rows2


def test_sample_composition_matches_prereg(sample_dir):
    manifest = json.loads((sample_dir / "sample_manifest.json").read_text(encoding="utf-8"))
    assert manifest["arm_counts"]["A"] == 60
    assert manifest["arm_counts"]["C"] == 10
    # Arm B target is 30 (10/stratum); tolerate under-fill only if a stratum pool ran dry
    # (E-001: report insufficiency, don't force a fake count) -- but it must not silently
    # exceed 30, and it must not be zero (that would mean the stratified logic is dead).
    assert 0 < manifest["arm_counts"]["B"] <= 30


def test_items_respect_minimum_spacing(sample_dir):
    manifest = json.loads((sample_dir / "sample_manifest.json").read_text(encoding="utf-8"))
    by_bar = sorted({it["target_row_index"] for it in manifest["items"]
                     if it["arm"] != "C"})
    for a, b in zip(by_bar, by_bar[1:]):
        assert b - a >= manifest["min_spacing_bars"]


# ── 4: scorer sanity (E-001 — a scorer that can't distinguish signal from noise is not
#      enforcement) ────────────────────────────────────────────────────────────────────────

def test_scorer_perfect_labels_give_high_kappa():
    from scripts.analysis.blind_label_score import _kappa

    # 15 of each class -- clears both the total-n floor AND the minority-class floor
    # (MIN_CELL_N=15 applies to each, per the registered rule; see
    # test_scorer_reports_insufficient_minority_below_registered_floor below).
    y_true = [1.0, -1.0, 0.0] * 15
    result = _kappa(y_true, y_true, "nominal")
    assert result["status"] == "SCORED"
    assert result["kappa"] == pytest.approx(1.0)


def test_scorer_random_labels_give_low_kappa():
    from scripts.analysis.blind_label_score import _kappa
    import random

    rng = random.Random(42)
    y_true = [rng.choice([1.0, -1.0, 0.0]) for _ in range(200)]
    y_pred = [rng.choice([1.0, -1.0, 0.0]) for _ in range(200)]
    result = _kappa(y_true, y_pred, "nominal")
    assert result["status"] == "SCORED"
    assert abs(result["kappa"]) < 0.15, (
        "scorer must not report substantial agreement on independently-random labels"
    )


def test_scorer_reports_insufficient_below_min_n():
    from scripts.analysis.blind_label_score import _kappa

    result = _kappa([1.0, -1.0], [1.0, -1.0], "nominal")
    assert result["status"] == "INSUFFICIENT"
    assert result["kappa"] is None


def test_scorer_reports_insufficient_minority_below_registered_floor():
    """docs/research/registration-blind-label-scorer-min-n-correction.md (D2): the
    pre-registration gates on RAREST-class instance count (>= MIN_CELL_N), not total n. A cell
    can clear the total-n floor while one class has almost no support. These six cases reproduce
    the 6 measured cells the unfixed scorer wrongly reported SCORED (Arm A q3_sweep/q4_bos;
    Arm B q1_trend/q2_vol/q3_sweep/q4_bos) as synthetic class-count fixtures -- pred is a copy of
    true (the best possible case), so even a perfect labeler must not be reported SCORED on an
    underpowered minority class."""
    from scripts.analysis.blind_label_score import _kappa

    cases = [
        ("nominal", {0: 50, 1: 6, -1: 4}),   # Arm A q3_sweep
        ("nominal", {0: 42, 1: 13, -1: 5}),  # Arm A q4_bos
        ("nominal", {1: 17, -1: 13}),        # Arm B q1_trend
        ("linear", {2: 14, 1: 10, 0: 6}),    # Arm B q2_vol
        ("nominal", {0: 13, -1: 9, 1: 8}),   # Arm B q3_sweep
        ("nominal", {0: 15, 1: 9, -1: 6}),   # Arm B q4_bos
    ]
    for weight_mode, counts in cases:
        y_true = [v for v, c in counts.items() for _ in range(c)]
        result = _kappa(y_true, y_true, weight_mode)
        assert result["status"] == "INSUFFICIENT_MINORITY", (counts, result)
        assert result["kappa"] is None
        assert result["minority_class_n"] == min(counts.values())


def test_scorer_still_scores_well_powered_cells_after_minority_fix():
    """Same registration, verification #2: the fix must not make everything insufficient --
    Arm A q1_trend/q2_vol (n=60, every class >= 15) must remain SCORED."""
    from scripts.analysis.blind_label_score import _kappa

    q1_true = [1.0] * 27 + [-1.0] * 33  # Arm A q1_trend measured composition (rarest=27)
    result = _kappa(q1_true, q1_true, "nominal")
    assert result["status"] == "SCORED"
    assert result["kappa"] == pytest.approx(1.0)

    q2_true = [2] * 16 + [1] * 22 + [0] * 22  # Arm A q2_vol measured composition (rarest=16)
    result = _kappa(q2_true, q2_true, "linear")
    assert result["status"] == "SCORED"
    assert result["kappa"] == pytest.approx(1.0)


def test_linear_weighted_kappa_penalizes_distance():
    """volatility_regime is ordinal (Low<Normal<High) -- a Low/High confusion should score
    worse than a Low/Normal confusion under linear weighting, which is why Q2 uses it."""
    from scripts.analysis.blind_label_score import _kappa

    n = 45  # 15 per class -- clears the minority-class floor too (was n=20 / 6-7 per class)
    y_true = [0, 1, 2] * (n // 3) + [0] * (n % 3)
    y_adjacent_errors = [min(v + 1, 2) if v < 2 else v for v in y_true]  # off-by-one only
    y_extreme_errors = [2 - v for v in y_true]  # Low<->High flips

    k_adjacent = _kappa(y_true, y_adjacent_errors, "linear")["kappa"]
    k_extreme = _kappa(y_true, y_extreme_errors, "linear")["kappa"]
    assert k_adjacent > k_extreme, (
        "linear-weighted kappa must penalize Low<->High confusions more than Low<->Normal"
    )
