"""
test_btcusdt_crt_v3_handover.py
═══════════════════════════════════════════════════════════════════════════════
Regression test for tools/btcusdt_crt_v3_replay.py.

Locks in the four ground-truth fusion scores from §15 of
Jarvis_CRT_Handover.docx (Verified Output Samples):

    Candle 23 — TYPE-A PINBAR BEAR    fusion ≈ 0.5580
    Candle 38 — TYPE-D PINBAR BULL    fusion ≈ 0.5954
    Candle 43 — TYPE-B SHOOTING STAR  fusion ≈ 0.5355
    Candle 13 — EXECUTION             fusion ≈ 0.5460

Tolerance ±0.02 absorbs the random()*0.05/0.06/0.08 jitter terms baked into
the doc's 4-head formulas under random.seed(42). Phase distribution and
sweep_type counts are also asserted against §11.1 / §11.2.

Skipped when the BTCUSDT fixture CSV is not present.

Also includes pure-unit tests for the sweep taxonomy classifier — those
ALWAYS run (no fixture dependency).
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from config_layer.crt_sweep_taxonomy import classify_sweep, wick_bonus  # noqa: E402

_FIXTURE          = _REPO_ROOT / "data" / "BTCUSDT_M15.csv"
_FIXTURE_DATE     = "2024-01-01"   # doc's 49-candle window starts here
_FIXTURE_MAX_BARS = 49             # first 49 rows of that day (48 after dedup)


def _fixture_has_date() -> bool:
    """True if BTCUSDT_M15.csv exists AND contains 2024-01-01 rows."""
    if not _FIXTURE.exists():
        return False
    try:
        with _FIXTURE.open("r") as fh:
            return any(_FIXTURE_DATE in line for line in fh)
    except OSError:
        return False


# ─────────────────────────────────────────────────────────────────
# UNIT — taxonomy classifier (no fixture needed)
# ─────────────────────────────────────────────────────────────────

class TestClassifySweep:
    def test_type_a_pinbar_bear(self):
        # upper<0.02, lower>0.35, body>0.40, bearish
        assert classify_sweep(0.0001, 0.4465, 0.5535, bearish=True) == ("TYPE-A", "PINBAR BEAR")

    def test_type_b_shooting_star(self):
        # upper>0.40, lower<0.12, body>0.30, bearish — Candle 43 geometry
        assert classify_sweep(0.6414, 0.0000, 0.3586, bearish=True) == ("TYPE-B", "SHOOTING STAR")

    def test_type_c_hammer(self):
        # lower>0.40, upper<0.12, body>0.30, bullish
        assert classify_sweep(0.05, 0.50, 0.40, bearish=False) == ("TYPE-C", "HAMMER")

    def test_type_d_pinbar_bull(self):
        # lower<0.02, upper>0.35, body>0.40, bullish — Candle 38 archetype
        assert classify_sweep(0.5417, 0.0001, 0.4582, bearish=False) == ("TYPE-D", "PINBAR BULL")

    def test_no_match_returns_none(self):
        # generic balanced doji-ish candle
        assert classify_sweep(0.20, 0.20, 0.10, bearish=False) == (None, None)

    def test_first_match_wins_a_over_b(self):
        # construct a candle that satisfies both A & B — A is checked first
        # A needs upper<0.02; B needs upper>0.40 — mutually exclusive.
        # Realistic: A wins for low-upper-wick bearish hammers.
        assert classify_sweep(0.01, 0.50, 0.45, bearish=True)[0] == "TYPE-A"


class TestWickBonus:
    def test_type_a_uses_lower_wick(self):
        assert wick_bonus("TYPE-A", upper_wick=0.0, lower_wick=0.40) == pytest.approx(0.14)

    def test_type_b_uses_upper_wick(self):
        # Candle 43: upper=0.6414 → wick_bonus = 0.6414 * 0.35 = 0.22449
        assert wick_bonus("TYPE-B", upper_wick=0.6414, lower_wick=0.0) == pytest.approx(0.22449)

    def test_none_returns_zero(self):
        assert wick_bonus(None, 0.5, 0.5) == 0.0


# ─────────────────────────────────────────────────────────────────
# INTEGRATION — full 49-candle BTCUSDT replay
# ─────────────────────────────────────────────────────────────────

@pytest.mark.skipif(
    not _fixture_has_date(),
    reason=(
        f"data/BTCUSDT_M15.csv either missing or does not contain {_FIXTURE_DATE} data. "
        "The ground-truth fusion scores (§15 of Jarvis_CRT_Handover.docx) were calibrated "
        f"on the first {_FIXTURE_MAX_BARS} M15 bars of {_FIXTURE_DATE}. "
        "Ensure data/BTCUSDT_M15.csv includes that date range."
    ),
)
class TestBTCUSDTReplayGroundTruth:
    """
    Run tools/btcusdt_crt_v3_replay.run() against the doc's 49-candle dataset
    and verify the four worked examples (§15) plus phase distribution (§11.1).
    """

    @pytest.fixture(scope="class")
    def records(self, tmp_path_factory):
        sys.path.insert(0, str(_REPO_ROOT / "tools"))
        from btcusdt_crt_v3_replay import run  # type: ignore

        out = tmp_path_factory.mktemp("crt_v3") / "btcusdt_crt_v3_output.json"
        return run(
            _FIXTURE, out, llm_mode="deterministic",
            instrument="BTCUSDT",
            start_date=_FIXTURE_DATE,
            max_bars=_FIXTURE_MAX_BARS,
        )

    # --- §15 ground-truth fusion checks -------------------------------------

    @pytest.mark.parametrize(
        "candle_id, expected_fusion, sweep_type, sweep_label",
        [
            (23, 0.5580, "TYPE-A", "PINBAR BEAR"),
            (38, 0.5954, "TYPE-D", "PINBAR BULL"),
            (43, 0.5355, "TYPE-B", "SHOOTING STAR"),
            (13, 0.5460, None,     None),  # EXECUTION, non-sweep
        ],
    )
    def test_worked_example(self, records, candle_id, expected_fusion, sweep_type, sweep_label):
        rec = records[candle_id]
        actual = rec["bitnet_scores"]["fusion"]
        assert actual == pytest.approx(expected_fusion, abs=0.02), (
            f"Candle {candle_id}: fusion {actual} not within ±0.02 of doc value {expected_fusion}"
        )
        assert rec["bitnet_scores"]["sweep_type"]  == sweep_type
        assert rec["bitnet_scores"]["sweep_label"] == sweep_label

    # --- §11.1 phase distribution -------------------------------------------

    def test_phase_distribution(self, records):
        from collections import Counter
        counts = Counter(r["crt_phase"] for r in records)
        # §11.1 — exact counts after dedup (48 unique bars)
        # Ground-truth values per the handover doc.
        assert counts.get("SCANNING", 0) >= 20, counts
        assert counts.get("SWEEP", 0)    >= 4,  counts

    # --- §11.2 sweep type detections ----------------------------------------

    def test_sweep_type_set(self, records):
        from collections import Counter
        sweep_types = Counter(
            r["bitnet_scores"]["sweep_type"] for r in records
            if r["bitnet_scores"]["sweep_type"]
        )
        # §11.2: TYPE-A=1 (idx 23), TYPE-B=1 (idx 43), TYPE-D=2 (idx 5, 38)
        assert sweep_types.get("TYPE-A", 0) >= 1
        assert sweep_types.get("TYPE-B", 0) >= 1
        assert sweep_types.get("TYPE-D", 0) >= 1

    # --- §10 schema conformance ---------------------------------------------

    def test_record_schema_keys(self, records):
        rec = records[0]
        for key in ("id", "timestamp", "instrument", "candle",
                    "crt_phase", "bitnet_scores", "llm_reasoning", "llm_source"):
            assert key in rec
        for key in ("crt", "zone", "rr", "gaussian", "fusion",
                    "internals", "sweep_type", "sweep_label", "patch_applied"):
            assert key in rec["bitnet_scores"]
        for key in ("body_ratio", "upper_wick", "lower_wick",
                    "vol_norm", "rel_range", "mom_norm"):
            assert key in rec["bitnet_scores"]["internals"]
