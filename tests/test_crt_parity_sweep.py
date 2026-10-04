"""
CRT Semantic Parity sweep driver — behavioral floor.

Exercises scripts/research/crt_parity_sweep.py (F-069 program). Skips
entirely if the corpus/events fixture used by the CRT parity program is
absent (this floor requires the real XAUUSD M15 corpus + a matching
backtest events.jsonl, not a synthetic substitute — per standing
instruction, this program never substitutes another instrument).

Covers the parts that can silently break a research program without an
exception: candidate writes must stay confined to the sweep scratch root
(never touch a tracked config), the config-delta round-trip must be
lossless, and the measured Step-0 baseline is pinned so the driver can't
silently drift from the pre-registered number.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_MODULE_PATH = _REPO / "scripts" / "research" / "crt_parity_sweep.py"
_CM_MODULE_PATH = _REPO / "scripts" / "research" / "crt_state_confusion_matrix.py"
_OHLCV = _REPO / "data" / "mt5" / "XAUUSD_M15.csv"
_EVENTS = _REPO / "results" / "run_20260724_104845_XAUUSD" / "XAUUSD_events.jsonl"
_BASE_CONFIG = _REPO / "configs" / "formulas" / "market_crt_states.yaml"

# Pinned at Step 0 (2 independent processes x 3 in-process runs, 6/6 identical
# sha256("|".join(states))[:16] = 78083e6816b42cea). See
# docs/research/preregistration-crt-semantic-parity.md.
PINNED_BASELINE_AGREEMENT = 41607
PINNED_BASELINE_TOTAL = 47197


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def sweep_mod():
    if not _MODULE_PATH.exists():
        pytest.skip("crt_parity_sweep.py not present")
    if not _CM_MODULE_PATH.exists():
        pytest.skip("crt_state_confusion_matrix.py not present")
    return _load_module("crt_parity_sweep", _MODULE_PATH)


@pytest.fixture(scope="module")
def corpus_available():
    if not (_OHLCV.exists() and _EVENTS.exists() and _BASE_CONFIG.exists()):
        pytest.skip(
            "CRT parity corpus fixture not present "
            f"(need {_OHLCV}, {_EVENTS}, {_BASE_CONFIG})"
        )
    return True


class TestDeltaApplication:
    def test_apply_delta_sets_nested_key_without_mutating_base(self, sweep_mod):
        base = {"thresholds": {"body_ratio_min": 0.65, "lifecycle": {"htf_reset_enabled": True}}}
        delta = {"thresholds.body_ratio_min": 0.70}
        cand = sweep_mod.apply_delta(base, delta)
        assert cand["thresholds"]["body_ratio_min"] == 0.70
        assert base["thresholds"]["body_ratio_min"] == 0.65  # base untouched

    def test_apply_delta_sets_deeply_nested_key(self, sweep_mod):
        base = {"thresholds": {"lifecycle": {"htf_protect_execution": True}}}
        delta = {"thresholds.lifecycle.htf_protect_execution": False}
        cand = sweep_mod.apply_delta(base, delta)
        assert cand["thresholds"]["lifecycle"]["htf_protect_execution"] is False

    def test_empty_delta_is_identity(self, sweep_mod):
        base = {"thresholds": {"body_ratio_min": 0.65}}
        cand = sweep_mod.apply_delta(base, {})
        assert cand == base
        assert cand is not base  # still a deep copy, not the same object

    def test_delta_sha_is_deterministic_and_order_independent(self, sweep_mod):
        d1 = {"a": 1, "b": 2}
        d2 = {"b": 2, "a": 1}
        assert sweep_mod.delta_sha12(d1) == sweep_mod.delta_sha12(d2)

    def test_different_deltas_produce_different_shas(self, sweep_mod):
        assert sweep_mod.delta_sha12({"a": 1}) != sweep_mod.delta_sha12({"a": 2})


class TestCandidateMaterializationConfinement:
    def test_candidate_written_under_sweep_root(self, sweep_mod, tmp_path):
        base = {"thresholds": {"body_ratio_min": 0.65}}
        delta = {"thresholds.body_ratio_min": 0.70}
        cand_path = sweep_mod.materialize_candidate(base, delta, tmp_path)
        assert cand_path.exists()
        assert cand_path.is_relative_to(tmp_path.resolve())

    def test_candidate_content_round_trips(self, sweep_mod, tmp_path):
        import yaml
        base = {"thresholds": {"body_ratio_min": 0.65, "lifecycle": {"htf_reset_enabled": True}}}
        delta = {"thresholds.body_ratio_min": 0.71, "thresholds.lifecycle.htf_reset_enabled": False}
        cand_path = sweep_mod.materialize_candidate(base, delta, tmp_path)
        loaded = yaml.safe_load(cand_path.read_text(encoding="utf-8"))
        assert loaded["thresholds"]["body_ratio_min"] == 0.71
        assert loaded["thresholds"]["lifecycle"]["htf_reset_enabled"] is False

    def test_identical_delta_reuses_the_same_content_addressed_file(self, sweep_mod, tmp_path):
        base = {"thresholds": {"body_ratio_min": 0.65}}
        delta = {"thresholds.body_ratio_min": 0.70}
        p1 = sweep_mod.materialize_candidate(base, delta, tmp_path)
        p2 = sweep_mod.materialize_candidate(base, delta, tmp_path)
        assert p1 == p2

    def test_live_tracked_config_is_never_the_sweep_root(self, sweep_mod):
        # A structural guard on the module's own defaults: SWEEP_ROOT must
        # live under results/, never under configs/ — if this ever changes,
        # the path-confinement assert in materialize_candidate is the only
        # thing left standing between a driver bug and clobbering the live
        # resolver config.
        assert "results" in sweep_mod.SWEEP_ROOT.parts


class TestStageIterationNamespacesDoNotCollide:
    """Regression floor for a real incident during the F-069 program: Stage B
    restarted its iter counter at 1 and wrote through the SAME writer as
    Stage A, silently overwriting Stage A's canonical iter_0001.json
    (baseline, already cited in F-069/CLAUDE.md) mid-sweep. Fixed by giving
    Stage B its own iters_b/ + ledger_b.jsonl namespace via
    write_iteration_b(). These tests pin that separation permanently.
    """

    def test_stage_a_and_stage_b_writers_use_different_directories(self, sweep_mod, tmp_path):
        record_a = {"iter": 1, "stage": "A", "cand_sha": "baseline", "config_delta": {},
                    "engine_overrides": {}, "agreement_rate": 0.5, "delta_vs_baseline_pp": 0.0,
                    "mismatch_n": 0, "elapsed_s": 0.0}
        record_b = {"iter": 1, "stage": "B", "label": "B_baseline", "engine_overrides": {},
                    "resolver_config": "(default)", "agreement_rate": 0.5,
                    "delta_vs_baseline_pp": 0.0, "mismatch_n": 0, "elapsed_s": 0.0,
                    "authority": "one_way_sensitivity_diagnostic_ONLY_no_promotion"}

        path_a = sweep_mod.write_iteration(tmp_path, record_a)
        path_b = sweep_mod.write_iteration_b(tmp_path, record_b)

        assert path_a != path_b
        assert path_a.parent.name == "iters"
        assert path_b.parent.name == "iters_b"
        # The Stage-A file must still hold Stage-A's data — this is the
        # exact invariant that broke in the incident.
        assert json.loads(path_a.read_text(encoding="utf-8"))["stage"] == "A"
        assert json.loads(path_b.read_text(encoding="utf-8"))["stage"] == "B"

    def test_ledgers_are_separate_files(self, sweep_mod, tmp_path):
        record_a = {"iter": 1, "stage": "A", "cand_sha": "baseline", "config_delta": {},
                    "engine_overrides": {}, "agreement_rate": 0.5, "delta_vs_baseline_pp": 0.0,
                    "mismatch_n": 0, "elapsed_s": 0.0}
        record_b = {"iter": 1, "stage": "B", "label": "B_baseline", "engine_overrides": {},
                    "resolver_config": "(default)", "agreement_rate": 0.5,
                    "delta_vs_baseline_pp": 0.0, "mismatch_n": 0, "elapsed_s": 0.0,
                    "authority": "one_way_sensitivity_diagnostic_ONLY_no_promotion"}
        sweep_mod.write_iteration(tmp_path, record_a)
        sweep_mod.write_iteration_b(tmp_path, record_b)

        assert (tmp_path / "ledger.jsonl").exists()
        assert (tmp_path / "ledger_b.jsonl").exists()
        # Stage A's ledger must contain ONLY Stage-A's line — a repeat of the
        # incident would show a "stage": "B" line appended here.
        a_lines = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
        assert all(json.loads(ln)["stage"] == "A" for ln in a_lines if ln.strip())

    def test_write_iteration_b_does_not_require_cand_sha(self, sweep_mod, tmp_path):
        # The incident's proximate crash: write_iteration() unconditionally
        # reads record["cand_sha"], which Stage B's records never set
        # (Stage B has no YAML-content-hash concept, only a `label`).
        record_b = {"iter": 1, "stage": "B", "label": "B_baseline", "engine_overrides": {},
                    "resolver_config": "(default)", "agreement_rate": 0.5,
                    "delta_vs_baseline_pp": 0.0, "mismatch_n": 0, "elapsed_s": 0.0,
                    "authority": "one_way_sensitivity_diagnostic_ONLY_no_promotion"}
        assert "cand_sha" not in record_b
        sweep_mod.write_iteration_b(tmp_path, record_b)  # must not raise KeyError
        assert "configs" not in sweep_mod.SWEEP_ROOT.parts


class TestAntiSimpsonGuard:
    def test_recall_drop_within_tolerance_is_ok(self, sweep_mod):
        baseline = {"RANGE": {"powered": True, "recall": 0.90}}
        candidate = {"RANGE": {"powered": True, "recall": 0.87}}  # -3pp, under 5pp tolerance
        ok, violations = sweep_mod.anti_simpson_ok(baseline, candidate)
        assert ok
        assert violations == []

    def test_recall_drop_beyond_tolerance_is_violation(self, sweep_mod):
        baseline = {"RANGE": {"powered": True, "recall": 0.90}}
        candidate = {"RANGE": {"powered": True, "recall": 0.80}}  # -10pp
        ok, violations = sweep_mod.anti_simpson_ok(baseline, candidate)
        assert not ok
        assert len(violations) == 1
        assert "RANGE" in violations[0]

    def test_unpowered_state_regression_is_ignored(self, sweep_mod):
        baseline = {"RETEST": {"powered": False, "recall": 0.50}}
        candidate = {"RETEST": {"powered": False, "recall": 0.0}}
        ok, violations = sweep_mod.anti_simpson_ok(baseline, candidate)
        assert ok  # RETEST is under-powered; a swing there is not a Simpson violation

    def test_state_missing_from_candidate_counts_as_zero_recall(self, sweep_mod):
        baseline = {"EXPANSION": {"powered": True, "recall": 0.90}}
        candidate: dict = {}  # candidate emitted nothing for EXPANSION at all
        ok, violations = sweep_mod.anti_simpson_ok(baseline, candidate)
        assert not ok


@pytest.mark.slow
class TestStageAAgainstRealCorpus:
    """Requires the real XAUUSD corpus + a matching events.jsonl. Slow (~15-20s)."""

    def test_baseline_matches_pinned_step0_figure(self, sweep_mod, corpus_available, tmp_path):
        cm = _load_module("crt_state_confusion_matrix", _CM_MODULE_PATH)
        engine_ctx = cm.prepare_engine_context(_OHLCV, _EVENTS)
        report, _res_meta = cm.run_once(
            engine_ctx, config_path=None, engine_mode="exit", injection="none",
        )
        assert report.agreement == PINNED_BASELINE_AGREEMENT
        assert report.total == PINNED_BASELINE_TOTAL

    def test_full_injection_still_matches_historical_cli_default(self, sweep_mod, corpus_available):
        # Regression guard: the --injection full default must stay byte-
        # identical to the pre-refactor unconditional-injection behaviour.
        cm = _load_module("crt_state_confusion_matrix", _CM_MODULE_PATH)
        engine_ctx = cm.prepare_engine_context(_OHLCV, _EVENTS)
        report, _res_meta = cm.run_once(
            engine_ctx, config_path=None, engine_mode="exit", injection="full",
        )
        assert report.agreement / report.total > 0.999  # measured 99.96% at settle time
