"""P2 BLOCKING FLOOR (real corpus) — substrate labels == incumbent labels at scale.

The synthetic floor in `test_policy_parity.py` proves the kernel wrapping is correct.
This one proves it on the actual BNBUSDT detection corpus, through the real
projector and the real `clean_labels` builder, which is the migration precondition
for P7.

Measured 2026-07-23: n=100,000 units compared, 100.0000% field-identical.

Skips (rather than fails) when the corpus is absent, so the suite stays green in a
checkout without `logs/` — the corpus lives outside version control.

KNOWN PRECISION NOTE: `clean_labels` rounds `y_R_net` to 6 dp; `LabelSet.rr_net`
keeps 8. That is a representational difference in a cost-adjusted derivation, not a
walk difference — every field the KERNEL produces matches exactly. The tolerance
below is the incumbent's own rounding granularity.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.clean_labels.builder import BuildConfig, label_one_unit
from research.clean_labels.protocol import EXIT_MODEL, MAX_FORWARD
from research.episodes.policy import PolicyEvaluator
from research.episodes.projectors.detection import project_record

ROOT = Path(__file__).resolve().parents[3]
CANDLES = ROOT / "data" / "BNBUSDT_M15.csv"
# The 39-dim (CANONICAL_FEATURE_DIM) corpus. Older 38-dim runs are no longer
# labelable by clean_labels at all — its _feature_vector requires the current dim.
OPPS = ROOT / "logs" / "BNBUSDT" / "bnbusdt_causal_39dim_20260722" / "opportunities.jsonl"

N_UNITS = 2000          # keep the committed floor fast; the full 100k run is manual
INCUMBENT_ROUNDING = 1e-6


pytestmark = pytest.mark.skipif(
    not (CANDLES.is_file() and OPPS.is_file()),
    reason="BNBUSDT detection corpus not present (logs/ and data/ are untracked)",
)


@pytest.fixture(scope="module")
def loaded():
    import sys

    sys.path.insert(0, str(ROOT / "scripts" / "analysis"))
    from bnbusdt_trade_anatomy import load_candles

    candles, ts_to_idx, _ = load_candles(CANDLES)
    return candles, ts_to_idx


def _units(limit: int):
    with OPPS.open(encoding="utf-8") as fh:
        n = 0
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "entry" not in rec or "timestamp" not in rec:
                continue
            yield rec
            n += 1
            if n >= limit:
                return


def test_labelsets_match_clean_labels_on_the_real_corpus(loaded):
    candles, ts_to_idx = loaded
    cfg = BuildConfig(instrument="BNBUSDT", max_forward=MAX_FORWARD)
    ev = PolicyEvaluator(max_forward=MAX_FORWARD)

    n = 0
    mismatches: list[tuple] = []
    for rec in _units(N_UNITS):
        row, _ = label_one_unit(rec, candles, ts_to_idx, cfg)
        if row is None:
            continue
        ep, reason = project_record(rec, candles, ts_to_idx,
                                    instrument="BNBUSDT", max_forward=MAX_FORWARD)
        assert reason is None, f"projector skipped a unit clean_labels accepted: {reason}"
        ls = ev.evaluate(ep, EXIT_MODEL)
        n += 1

        failed = {
            k for k, ok in {
                "outcome": row["path_outcome"] == ls.outcome,
                "duration": row["y_holding_bars"] == ls.duration_candles,
                "time_to_tp": row["path_time_to_tp"] == ls.time_to_tp,
                "time_to_failure": row["path_time_to_failure"] == ls.time_to_failure,
                "reached_1r": bool(row["y_survives_be"]) == ls.reached_1r,
                "path_mfe_r": abs(row["path_mfe_r"] - ls.mfe_r) < 1e-6,
                "path_mae_r": abs(row["path_mae_r_heat"] - abs(ls.mae_r)) < 1e-6,
                "horizon_mfe_r": abs(row["y_mfe_r"] - ls.horizon["mfe_r"]) < 1e-9,
                "horizon_time_to_1r": row["y_time_to_1r"] == ls.horizon["bars_to_first_1r"],
                "rr_net": abs(row["y_R_net"] - ls.rr_net) < INCUMBENT_ROUNDING,
            }.items() if not ok
        }
        if failed and len(mismatches) < 5:
            mismatches.append((row["unit_id"], sorted(failed)))

    assert n > 0, "no comparable units — corpus present but produced zero clean rows"
    assert not mismatches, (
        f"PARITY BROKEN on {len(mismatches)} of {n} units — a second exit kernel may "
        f"have been introduced: {mismatches}"
    )


def test_events_agree_with_the_kernel_on_the_real_corpus(loaded):
    """REACHED_R@1R must equal horizon_excursion's bars_to_first_1r, unit for unit.

    Measured 2026-07-23: 2999/2999 (100.0000%). This caught a real float-boundary
    disagreement (2/2999) when the detector compared a rounded R ratio instead of the
    kernel's raw-price predicate — see test_event_engine's boundary regression.
    """
    from research.episodes.events import EventEngine

    candles, ts_to_idx = loaded
    engine, ev = EventEngine(), PolicyEvaluator(max_forward=MAX_FORWARD)

    n, disagreements = 0, []
    for rec in _units(N_UNITS):
        ep, reason = project_record(rec, candles, ts_to_idx,
                                    instrument="BNBUSDT", max_forward=MAX_FORWARD)
        if reason is not None:
            continue
        got = engine.detect(ep).first("REACHED_R", r=1.0)
        expected = ev.evaluate(ep, EXIT_MODEL).horizon["bars_to_first_1r"]
        n += 1
        if (got.t if got else None) != expected:
            if len(disagreements) < 5:
                disagreements.append((ep.episode_id, got.t if got else None, expected))

    assert n > 0
    assert not disagreements, (
        f"REACHED_R@1R disagrees with the governing kernel on {len(disagreements)} of "
        f"{n} episodes — two definitions of 'reached 1R' have drifted: {disagreements}"
    )


def test_projector_and_clean_labels_select_the_same_population(loaded):
    """Both funnels must accept the same units, or the parity test compares samples."""
    candles, ts_to_idx = loaded
    cfg = BuildConfig(instrument="BNBUSDT", max_forward=MAX_FORWARD)

    only_incumbent, only_substrate = 0, 0
    for rec in _units(N_UNITS):
        row, _ = label_one_unit(rec, candles, ts_to_idx, cfg)
        ep, reason = project_record(rec, candles, ts_to_idx,
                                    instrument="BNBUSDT", max_forward=MAX_FORWARD)
        if row is not None and reason is not None:
            only_incumbent += 1
        # The substrate accepts units clean_labels rejects for FEATURE reasons only —
        # episodes deliberately do not require a feature vector (features are joined
        # by bar index on demand), so that direction is expected and not an error.
        elif row is None and reason is None:
            only_substrate += 1

    assert only_incumbent == 0, (
        f"{only_incumbent} units labelled by clean_labels but skipped by the projector — "
        "the substrate must never lose a unit the incumbent could label"
    )
