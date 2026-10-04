"""Program 4 — regime conditioning harness tests.

Properties: determinism (byte-identical report), it calls the REAL M4 gate (not a fork),
the label-permutation controls work in BOTH directions (a planted regime edge is detected;
no-edge and noise cannot manufacture a REGIME_EXPLOITABLE verdict), and the verdict
vocabulary is the pre-registered set.
"""
import json
import random
from datetime import datetime

from research.contracts import Outcome, Signal
from research.costs import ZERO_COST
from research.measurement.metrics import EdgeAggregator
from research.qualification import QualConfig
from research.regime_conditioning import RegimeConfig, evaluate_scope

_QCFG = QualConfig(min_samples=10, expectancy_min=0.0, pf_min=1.0, oos_split=0.3,
                   oos_retention_min=0.5, n_permutations=200, significance_alpha=0.05)
_RCFG = RegimeConfig(atr_period=14, tercile_window=480, lag_k=5, min_cell_samples=10,
                     harmful_margin=0.05, redundant_tol=0.05, null_relabelings=40)
_CONSUMER_VERDICTS = {"REGIME_EXPLOITABLE", "REGIME_INFORMATIONAL", "REGIME_HARMFUL",
                      "REGIME_REDUNDANT", "REGIME_INSUFFICIENT"}
_CELL_VERDICTS = {"REGIME_EXPLOITABLE", "REGIME_INFORMATIONAL", "REGIME_HARMFUL",
                  "REGIME_INSUFFICIENT"}


def _o(rr: float, idx: int, inst: str = "I") -> Outcome:
    sig = Signal(instrument=inst, timestamp=datetime(2026, 1, 1), entry_index=idx,
                 direction="long", entry=100.0, sl_atr_mult=1.0, tp_atr_mult=2.0, atr=1.0)
    return Outcome(signal=sig, outcome="TP_HIT" if rr > 0 else "SL_HIT", rr_achieved=rr,
                   mfe=0.0, mae=0.0, duration_candles=1, time_to_tp=1 if rr > 0 else None,
                   time_to_failure=None if rr > 0 else 1, reached_1r=rr > 0)


def _ctrl(n: int):
    return {"ctrl": {"I": [_o(0.0, i) for i in range(n)]}}


def _noise_scenario(n: int = 120, seed: int = 1):
    """rr INDEPENDENT of the regime label (pure noise) + random labels."""
    rng = random.Random(seed)
    outs = [_o(rng.choice([2.0, 2.0, -1.0]), i) for i in range(n)]
    labels = [rng.choice(["C", "N", "E"]) for _ in range(n)]
    return {"toy": {"I": outs}}, _ctrl(n), {"I": labels}


def _edge_scenario(n: int = 150, seed: int = 123):
    """A PLANTED, non-periodic regime edge: rr is +2 exactly when the (random) label is 'E',
    −1 otherwise. A correct harness must flag this REGIME_EXPLOITABLE in regime 'E' — and the
    lagged control must NOT (the labels are random, so a shift destroys the alignment)."""
    rng = random.Random(seed)
    labels = [rng.choice(["C", "N", "E"]) for _ in range(n)]
    outs = [_o(2.0 if labels[i] == "E" else -1.0, i) for i in range(n)]
    return {"toy": {"I": outs}}, _ctrl(n), {"I": labels}


def test_evaluate_scope_deterministic():
    consumers, controls, labels = _noise_scenario()
    a = evaluate_scope(consumers, controls, labels, _QCFG, ZERO_COST, _RCFG, ["I"])
    b = evaluate_scope(consumers, controls, labels, _QCFG, ZERO_COST, _RCFG, ["I"])
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_verdict_vocabulary_and_structure():
    consumers, controls, labels = _noise_scenario()
    r = evaluate_scope(consumers, controls, labels, _QCFG, ZERO_COST, _RCFG, ["I"])
    assert r["scope_verdict"] in _CONSUMER_VERDICTS
    cons = r["consumers"]["toy"]
    assert cons["verdict"] in _CONSUMER_VERDICTS
    cells = cons["cells"]
    assert set(cells) == {"C", "N", "E"}
    for g in ("C", "N", "E"):
        assert cells[g]["gate_verdict"] in {"PROMOTE", "REJECT", "INSUFFICIENT"}
        assert cells[g]["cell_verdict"] in _CELL_VERDICTS


def test_planted_regime_edge_is_exploitable():
    """The harness CAN detect a genuine, non-periodic regime edge (avoids false negatives)."""
    consumers, controls, labels = _edge_scenario()
    r = evaluate_scope(consumers, controls, labels, _QCFG, ZERO_COST, _RCFG, ["I"])
    cons = r["consumers"]["toy"]
    assert r["scope_verdict"] == "REGIME_EXPLOITABLE"
    assert cons["verdict"] == "REGIME_EXPLOITABLE"
    assert cons["best_regime"] == "E"
    assert cons["beats_nulls"] is True
    assert cons["redundant"] is False
    assert cons["cells"]["E"]["cell_verdict"] == "REGIME_EXPLOITABLE"
    assert cons["cells"]["E"]["gate_verdict"] == "PROMOTE"


def test_no_edge_cannot_be_exploitable():
    """A consumer with no edge anywhere (constant loss) can never PROMOTE a cell, so the scope
    cannot be exploitable — the gate-first guard."""
    n = 120
    consumers = {"toy": {"I": [_o(-1.0, i) for i in range(n)]}}
    r = evaluate_scope(consumers, _ctrl(n), {"I": ["C", "N", "E"] * (n // 3)},
                       _QCFG, ZERO_COST, _RCFG, ["I"])
    assert r["scope_verdict"] != "REGIME_EXPLOITABLE"


def test_exploitable_implies_controls_passed():
    """Internal-consistency invariant (holds in EVERY scenario): an EXPLOITABLE consumer must
    have beaten the null distribution, not be redundant, and its best cell must have PROMOTEd."""
    for scen in (_noise_scenario(seed=7), _edge_scenario(), _noise_scenario(seed=3)):
        consumers, controls, labels = scen
        r = evaluate_scope(consumers, controls, labels, _QCFG, ZERO_COST, _RCFG, ["I"])
        for cons in r["consumers"].values():
            if cons["verdict"] == "REGIME_EXPLOITABLE":
                assert cons["beats_nulls"] is True
                assert cons["redundant"] is False
                best = cons["best_regime"]
                assert cons["cells"][best]["gate_verdict"] == "PROMOTE"


def test_underpowered_consumer_is_insufficient():
    """A consumer whose every regime cell fails the sample gate (the spine-throughput case,
    F-019/F-022) must report REGIME_INSUFFICIENT, not HARMFUL/INFORMATIONAL — sign-counts on
    n=1..9 cells are noise, not evidence."""
    n = 9   # < q min_samples (10) once split across 3 regimes
    outs = [_o(-1.0 if i % 2 else 2.0, i) for i in range(n)]
    consumers = {"spine": {"I": outs}}
    labels = {"I": [["C", "N", "E"][i % 3] for i in range(n)]}
    r = evaluate_scope(consumers, _ctrl(n), labels, _QCFG, ZERO_COST, _RCFG, ["I"])
    cons = r["consumers"]["spine"]
    assert cons["verdict"] == "REGIME_INSUFFICIENT"
    assert r["scope_verdict"] == "REGIME_INSUFFICIENT"
    for g in ("C", "N", "E"):
        assert cons["cells"][g]["gate_verdict"] == "INSUFFICIENT"
        assert cons["cells"][g]["cell_verdict"] == "REGIME_INSUFFICIENT"


def test_uses_real_gate_not_a_fork():
    """Reuse proof: a cell's reported expectancy must equal the canonical EdgeAggregator's NET
    expectancy over that cell's outcomes — the harness aggregates via the real research-layer
    metrics, not a private reimplementation."""
    n = 60
    outs = [_o(2.0 if i % 2 == 0 else -1.0, i) for i in range(n)]
    consumers = {"toy": {"I": outs}}
    labels = {"I": ["E"] * n}
    r = evaluate_scope(consumers, _ctrl(n), labels, _QCFG, ZERO_COST, _RCFG, ["I"])
    cell_E = r["consumers"]["toy"]["cells"]["E"]
    expected = EdgeAggregator().aggregate("x", ["I"], outs, cost_model=ZERO_COST)
    assert cell_E["n"] == expected.n == n
    assert cell_E["expectancy_rr"] == expected.expectancy_rr
    assert r["consumers"]["toy"]["cells"]["C"]["n"] == 0


def test_control_fields_present():
    consumers, controls, labels = _noise_scenario()
    r = evaluate_scope(consumers, controls, labels, _QCFG, ZERO_COST, _RCFG, ["I"])
    cons = r["consumers"]["toy"]
    for key in ("S_real", "p_label", "null_p95", "S_lagged", "beats_nulls", "redundant"):
        assert key in cons
    assert 0.0 <= cons["p_label"] <= 1.0
    for g in ("C", "N", "E"):
        assert "uplift_real" in cons["cells"][g]


def test_regimes_constant_does_not_drift():
    """The harness defines REGIMES locally (research-layer isolation); pin it equal to the
    labeler's so the two cannot drift apart."""
    from interpreters.regime_observer import REGIMES as OBS_REGIMES
    from research.regime_conditioning import REGIMES as COND_REGIMES
    assert OBS_REGIMES == COND_REGIMES == ("C", "N", "E")


# ── Program 4b extension: within-tercile-shuffle control (current_level_series) ────────────
def test_evaluate_scope_without_current_level_series_matches_pre_4b_behavior():
    """Regression guard: calling evaluate_scope() with Program 4's ORIGINAL positional
    signature (no current_level_series) must produce a JSON body with the EXACT SAME key
    set as before the Program 4b extension -- protects F-030's already-registered artifact
    reproducibility. The new fields must be entirely ABSENT, not merely null."""
    consumers, controls, labels = _noise_scenario()
    r = evaluate_scope(consumers, controls, labels, _QCFG, ZERO_COST, _RCFG, ["I"])
    cons = r["consumers"]["toy"]
    assert "S_within_tercile" not in cons
    assert "redundant_lagged" not in cons
    assert "redundant_within_tercile" not in cons
    assert set(cons) == {"verdict", "unconditioned_E", "best_regime", "S_real", "p_label",
                         "null_p95", "S_lagged", "beats_nulls", "redundant", "cells"}


def _level_only_edge_scenario(n: int = 150, seed: int = 321):
    """Plant an edge that depends ONLY on the CURRENT level, with the predicted label set
    EQUAL to the current level (an H=0, zero-skill 'forecast' that just copies the level).
    Shuffling identical values within each current-level bucket is a no-op, so the
    within-tercile control must FULLY reproduce the uplift -> REGIME_REDUNDANT, never
    REGIME_EXPLOITABLE. The lagged control must NOT flag it (labels are random per position,
    so a shift destroys the alignment — same reasoning as `_edge_scenario`)."""
    rng = random.Random(seed)
    current_labels = [rng.choice(["C", "N", "E"]) for _ in range(n)]
    predicted_labels = list(current_labels)
    outs = [_o(2.0 if current_labels[i] == "E" else -1.0, i) for i in range(n)]
    return ({"toy": {"I": outs}}, _ctrl(n), {"I": predicted_labels}, {"I": current_labels})


def _predicted_only_edge_scenario(n: int = 200, seed: int = 555):
    """A genuine PREDICTED-regime edge, INDEPENDENT of the current level: rr depends only on
    the predicted label ('E' -> win), current level drawn with a separate seed. The
    within-tercile-shuffle must NOT reproduce this uplift (scrambling predicted labels within
    current-level buckets destroys a genuinely predicted-label-driven signal, same as a full
    shuffle would) -- proves the new control does not manufacture false negatives."""
    rng_pred = random.Random(seed)
    rng_cur = random.Random(seed + 1)
    predicted_labels = [rng_pred.choice(["C", "N", "E"]) for _ in range(n)]
    current_labels = [rng_cur.choice(["C", "N", "E"]) for _ in range(n)]
    outs = [_o(2.0 if predicted_labels[i] == "E" else -1.0, i) for i in range(n)]
    return ({"toy": {"I": outs}}, _ctrl(n), {"I": predicted_labels}, {"I": current_labels})


def test_level_only_edge_is_redundant_not_exploitable():
    """The core behavioral proof the 5th control does its job: an apparent transition edge
    that is really just the (already-falsified, F-030) level signal must resolve to
    REGIME_REDUNDANT via the within-tercile check, never REGIME_EXPLOITABLE."""
    consumers, controls, predicted, current = _level_only_edge_scenario()
    r = evaluate_scope(consumers, controls, predicted, _QCFG, ZERO_COST, _RCFG, ["I"],
                       current_level_series=current)
    cons = r["consumers"]["toy"]
    assert cons["redundant_within_tercile"] is True
    assert cons["redundant_lagged"] is False
    assert cons["redundant"] is True
    assert cons["verdict"] == "REGIME_REDUNDANT"
    assert r["scope_verdict"] != "REGIME_EXPLOITABLE"


def test_genuine_predicted_edge_survives_within_tercile_control():
    """Avoids false negatives: a genuine predicted-regime edge, independent of the current
    level, must still reach REGIME_EXPLOITABLE — the new control must not suppress real
    transition-forecast skill, only level-redundant impostors."""
    consumers, controls, predicted, current = _predicted_only_edge_scenario()
    r = evaluate_scope(consumers, controls, predicted, _QCFG, ZERO_COST, _RCFG, ["I"],
                       current_level_series=current)
    cons = r["consumers"]["toy"]
    assert cons["redundant_within_tercile"] is False
    assert cons["verdict"] == "REGIME_EXPLOITABLE"


def test_evaluate_scope_deterministic_with_current_level_series():
    consumers, controls, predicted, current = _level_only_edge_scenario()
    a = evaluate_scope(consumers, controls, predicted, _QCFG, ZERO_COST, _RCFG, ["I"],
                       current_level_series=current)
    b = evaluate_scope(consumers, controls, predicted, _QCFG, ZERO_COST, _RCFG, ["I"],
                       current_level_series=current)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
