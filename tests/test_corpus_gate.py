"""Floors for `data_ingestion.corpus_gate` -- the corpus admission seam.

Covers the contract the module exists to hold:
  * IDENTITY is fail-closed and independent of `enforce`
  * the canonical XAUUSD corpus admits WITHOUT a path rewrite (so wiring the
    gate into a research caller cannot silently change which bytes are read)
  * a declared-forensic path is rejected before any candle is parsed
  * D-1 (lattice) is HARD; D-2/D-3/D-4 are observations that stay silent
    unless a `plausibility` config block arms them
  * `enforce=False` returns a REJECT instead of raising (the batch semantics
    `backtest_v2._preflight_dataset` depends on)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from data_ingestion.corpus_gate import (  # noqa: E402
    CorpusAdmission,
    _median_true_range,
    _plausibility,
    admit_corpus,
)
from data_ingestion.dataset_registry import DatasetAdmissionError  # noqa: E402

_REPO = Path(__file__).resolve().parents[1]
_CANONICAL = _REPO / "data" / "mt5" / "XAUUSD_M15.csv"
_FORENSIC = _REPO / "data" / "mt5" / "XAUUSD_H4.csv"

_HEADER = "timestamp,open,high,low,close,volume\n"


def _write_csv(path: Path, rows: list[tuple[str, float, float, float, float, float]]) -> None:
    path.write_text(
        _HEADER + "".join(f"{t},{o},{h},{l},{c},{v}\n" for t, o, h, l, c, v in rows),
        encoding="utf-8",
    )


# ---------------------------------------------------------------- identity ---

@pytest.mark.skipif(not _CANONICAL.is_file(), reason="canonical corpus not present")
def test_canonical_corpus_admits_without_rewrite():
    """The gate must not move the corpus. If `rewritten` were ever True, wiring
    it into a research caller would silently change which bytes are read."""
    adm = admit_corpus(str(_CANONICAL), "XAUUSD", write_report=False)
    assert adm.bound is True
    assert adm.rewritten is False
    assert adm.dataset_id == "XAUUSD_MT5_PHASE1_20260521"
    assert Path(adm.filepath).resolve() == _CANONICAL.resolve()
    assert adm.file_hash and "4d73f5cebe33ec91" in adm.file_hash


@pytest.mark.skipif(not _FORENSIC.is_file(), reason="forensic H4 not present")
def test_forensic_path_is_rejected_regardless_of_enforce():
    """Identity is not a threshold question -- `enforce=False` must NOT soften it."""
    for enforce in (True, False):
        with pytest.raises(DatasetAdmissionError):
            admit_corpus(str(_FORENSIC), "XAUUSD", enforce=enforce, write_report=False)


# ----------------------------------------------------------- plausibility ---

def _cfg_no_thresholds() -> dict:
    return {"default_bar_minutes": 15}


def test_d1_lattice_constant_phase_passes(tmp_path):
    """A non-zero but CONSTANT phase is legal -- a broker day may open at 01:00."""
    p = tmp_path / "TEST_M15.csv"
    _write_csv(p, [
        ("2026-01-05 01:07:00", 1.0, 2.0, 0.5, 1.5, 10),
        ("2026-01-05 01:22:00", 1.5, 2.5, 1.0, 2.0, 10),
        ("2026-01-05 01:37:00", 2.0, 3.0, 1.5, 2.5, 10),
    ])
    metrics, hard, warns = _plausibility(p, 15, _cfg_no_thresholds())
    assert metrics["lattice_phase_constant"] is True
    assert hard == []


def test_d1_mixed_phase_is_hard(tmp_path):
    """Deltas are all 15 min, so modal-delta passes -- only D-1 catches this."""
    p = tmp_path / "TEST_M15.csv"
    _write_csv(p, [
        ("2026-01-05 01:00:00", 1.0, 2.0, 0.5, 1.5, 10),
        ("2026-01-05 01:15:00", 1.5, 2.5, 1.0, 2.0, 10),
        ("2026-01-05 01:37:00", 2.0, 3.0, 1.5, 2.5, 10),
    ])
    metrics, hard, _ = _plausibility(p, 15, _cfg_no_thresholds())
    assert metrics["lattice_phase_constant"] is False
    assert len(hard) == 1 and hard[0].startswith("D-1 lattice")


def test_d2_frozen_and_d3_zero_volume_are_counted_but_silent(tmp_path):
    """Observations earn no authority (CLAUDE.md 6.5): absent a `plausibility`
    block they are reported and emit NOTHING."""
    p = tmp_path / "TEST_M15.csv"
    _write_csv(p, [
        ("2026-01-05 01:00:00", 1.0, 1.0, 1.0, 1.0, 0),     # frozen AND zero-volume
        ("2026-01-05 01:15:00", 1.5, 2.5, 1.0, 2.0, 10),
    ])
    metrics, hard, warns = _plausibility(p, 15, _cfg_no_thresholds())
    assert metrics["frozen_bars"] == 1 and metrics["zero_volume_bars"] == 1
    assert hard == [] and warns == []


def test_plausibility_thresholds_are_opt_in(tmp_path):
    """Arming a threshold turns the same observation into a WARN -- and only then."""
    p = tmp_path / "TEST_M15.csv"
    _write_csv(p, [
        ("2026-01-05 01:00:00", 1.0, 1.0, 1.0, 1.0, 0),
        ("2026-01-05 01:15:00", 1.5, 2.5, 1.0, 2.0, 10),
    ])
    armed = {**_cfg_no_thresholds(),
             "plausibility": {"max_frozen_pct": 0.1, "max_zero_volume_pct": 0.1}}
    _metrics, hard, warns = _plausibility(p, 15, armed)
    assert hard == []
    assert any(w.startswith("D-2") for w in warns)
    assert any(w.startswith("D-3") for w in warns)


def test_d4_gap_is_measured_against_median_true_range(tmp_path):
    """The sequence gate counts missing BARS; only D-4 sees price DISCONTINUITY."""
    rows = [(f"2026-01-05 {1 + i // 4:02d}:{(i % 4) * 15:02d}:00",
             100.0, 101.0, 99.0, 100.0, 10) for i in range(8)]
    # bar 8 opens 50 points above the previous close -- no bar is missing.
    rows.append(("2026-01-05 03:00:00", 150.0, 151.0, 149.0, 150.0, 10))
    p = tmp_path / "TEST_M15.csv"
    _write_csv(p, rows)
    metrics, hard, _ = _plausibility(p, 15, _cfg_no_thresholds())
    assert hard == []                       # never hard
    assert metrics["gap_over_3tr"] == 1
    assert metrics["gap_max_tr"] > 3.0


def test_median_true_range_is_robust_to_a_single_gap():
    """Median, not mean, so a gap bar cannot inflate its own yardstick."""
    highs = [101.0] * 20 + [900.0]
    lows = [99.0] * 20 + [100.0]
    closes = [100.0] * 20 + [800.0]
    assert _median_true_range(highs, lows, closes) == pytest.approx(2.0)


# --------------------------------------------------------------- contract ---

def test_admission_exposes_the_provenance_pair():
    """`dataset_id` + `file_hash` are why this type exists -- they are what a run
    manifest records so a later reader can tell if two runs read the same bytes."""
    fields = CorpusAdmission.__dataclass_fields__
    for name in ("dataset_id", "file_hash", "decision", "plausibility", "report"):
        assert name in fields
