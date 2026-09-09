"""Floor for RC-003.

Enforces the things that would otherwise fail silently: that the frozen pre-registration
has not been edited, that the driver's constants still equal what that document declares,
that the block bootstrap actually resamples blocks (not bars), that the resolver evidence
capture is decision-neutral, and that every evidence artifact §11 declares is emitted by
the run rather than merely promised (the F-083 failure class).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
PREREG = REPO / "docs" / "research" / "preregistration-rc003-distinct-object.md"
OUT = REPO / "docs" / "research-readiness" / "rc003_distinct_object"

DECLARED_ARTIFACTS = (
    "population_fingerprint.json",
    "metrics.json",
    "referent_disagreement.json",
    "ledger.jsonl",
    "run_manifest.json",
)


def _driver():
    import sys

    sys.path.insert(0, str(REPO / "src"))
    from research.rc003_distinct_object import driver as d

    return d


def test_preregistration_exists_and_is_frozen() -> None:
    assert PREREG.is_file(), "RC-003 pre-registration missing"
    d = _driver()
    actual = d.frozen_prefix_sha256()
    assert actual == d.PREREG_SHA256, (
        "The frozen pre-registration was edited. Section 12 is append-only; the text ABOVE "
        f"its marker must not change. pinned={d.PREREG_SHA256} actual={actual}"
    )


def test_driver_constants_match_the_frozen_document() -> None:
    """A constant drifting away from what the document declares is exactly the silent gap
    this floor exists to close."""
    d = _driver()
    text = PREREG.read_text(encoding="utf-8")
    assert "alpha = 0.05" in text.replace("α", "alpha")
    assert d.ALPHA_PRIMARY == 0.05
    assert "0.0167" in text and d.ALPHA_SECONDARY == 0.0167
    assert "150" in text and d.N_MIN_PER_GROUP == 150


def test_preregistration_declares_every_artifact_the_driver_writes() -> None:
    text = PREREG.read_text(encoding="utf-8")
    for name in DECLARED_ARTIFACTS:
        assert name in text, f"{name} is written by the driver but not declared in section 11"


def test_no_economic_claim_is_authorised() -> None:
    text = PREREG.read_text(encoding="utf-8")
    assert "economic_claims_allowed: false" in text
    assert "PL-0" in text


def test_block_bootstrap_resamples_blocks_not_bars() -> None:
    """With every event inside one block, resampling blocks cannot vary the statistic.
    A bar-level bootstrap would produce a non-degenerate CI here."""
    d = _driver()
    a = [(i, 1) for i in range(0, 40)]  # all inside block 0 at block=96
    b = [(i, 0) for i in range(0, 40)]
    r = d.block_bootstrap_prop_diff(a, b, key="unit|degenerate", n_boot=200, block=96)
    assert r["n_a_eff_blocks"] == 1 and r["n_b_eff_blocks"] == 1
    assert r["ci_lo"] == pytest.approx(1.0) and r["ci_hi"] == pytest.approx(1.0)


def test_block_bootstrap_reports_effective_not_just_raw_n() -> None:
    d = _driver()
    a = [(i * 96, 1) for i in range(10)]  # 10 separate blocks
    b = [(i * 96, 0) for i in range(10)]
    r = d.block_bootstrap_prop_diff(a, b, key="unit|spread", n_boot=200, block=96)
    assert r["n_a_raw"] == 10 and r["n_a_eff_blocks"] == 10
    assert set(("n_a_eff_blocks", "n_b_eff_blocks", "block_bars")).issubset(r)


def test_block_bootstrap_is_deterministic_under_its_seed() -> None:
    d = _driver()
    a = [(i * 7, i % 2) for i in range(60)]
    b = [(i * 5, (i + 1) % 2) for i in range(60)]
    r1 = d.block_bootstrap_prop_diff(a, b, key="unit|det", n_boot=300)
    r2 = d.block_bootstrap_prop_diff(a, b, key="unit|det", n_boot=300)
    assert r1 == r2


def test_resolver_evidence_capture_is_default_off() -> None:
    """The capture must never be on unless a caller asks — otherwise it is not additive."""
    import sys

    sys.path.insert(0, str(REPO / "src"))
    from features.crt_state_resolver import CRTStateResolver

    r = CRTStateResolver()
    assert r.record_resolver_evidence is False
    assert r.last_resolver_evidence is None


def test_resolve_signature_unchanged() -> None:
    """resolve() must still return a bare state string; every existing caller depends on it."""
    import inspect
    import sys

    sys.path.insert(0, str(REPO / "src"))
    from features.crt_state_resolver import CRTStateResolver

    sig = inspect.signature(CRTStateResolver.resolve)
    assert sig.return_annotation in ("str", str), (
        "resolve() return type changed — the RC-003 capture must stay additive"
    )


# ── CH-resolution-site: decision provenance (2026-09-05) ─────────────────────
#
# F-069 classified every residual mismatch by CELL (engine_state -> resolver_state)
# and never by CODE PATH, so it cannot say whether an `EXPANSION -> RANGE` bar came
# from a TTL expiry, a dwell hold, or predicate exhaustion. `resolution_site` adds
# that dimension. These tests exist because the instrument is only trustworthy if
# its site vocabulary is EXHAUSTIVE — an unnamed return silently under-attributes,
# which is the F-056/F-079/F-083/F-085 silent-gap class this repo keeps paying for.


def _resolver_source_tree():
    import ast

    src = (REPO / "src" / "features" / "crt_state_resolver.py").read_text(encoding="utf-8")
    return ast.parse(src), src.splitlines()


def test_every_funnel_return_sets_a_resolution_site() -> None:
    """THE guard. Walk every `return` in _resolve_from_features and require that the
    statement immediately preceding it assigns `self._last_funnel_site`.

    If someone adds a 17th return without naming it, that bar's provenance silently
    falls back to a stale/None site and the pre-predicate split quietly drifts. This
    test makes that a red build instead of a wrong number.
    """
    import ast

    tree, _ = _resolver_source_tree()
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_resolve_from_features"
    )

    # Map each return to the assignment that should precede it, by walking every
    # statement-list body in the function.
    unnamed: list[int] = []

    def _check_body(body: list) -> None:
        for i, stmt in enumerate(body):
            if isinstance(stmt, ast.Return):
                prev = body[i - 1] if i > 0 else None
                ok = (
                    isinstance(prev, ast.Assign)
                    and any(
                        isinstance(t, ast.Attribute) and t.attr == "_last_funnel_site"
                        for t in prev.targets
                    )
                )
                if not ok:
                    unnamed.append(stmt.lineno)
            for field in ("body", "orelse", "finalbody"):
                inner = getattr(stmt, field, None)
                if isinstance(inner, list):
                    _check_body(inner)

    _check_body(fn.body)
    assert not unnamed, (
        "return(s) in _resolve_from_features with no preceding "
        f"`self._last_funnel_site = ...`: lines {unnamed}. Every funnel exit must "
        "name its site or the resolution_site measurement under-attributes silently."
    )


def test_funnel_site_count_matches_the_declared_vocabulary() -> None:
    """The 16 funnel returns must be covered by exactly the 16 funnel site ids."""
    import ast
    import sys

    sys.path.insert(0, str(REPO / "src"))
    from features.crt_state_resolver import _RESOLUTION_SITES

    tree, lines = _resolver_source_tree()
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_resolve_from_features"
    )
    returns = [r for r in ast.walk(fn) if isinstance(r, ast.Return)]
    assert len(returns) == 16, (
        f"_resolve_from_features has {len(returns)} returns, expected 16. If a branch was "
        "added or removed, update _RESOLUTION_SITES and this count together."
    )

    # Every site literal assigned inside the funnel must be a declared id.
    assigned = {
        n.value.value
        for n in ast.walk(fn)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Attribute) and t.attr == "_last_funnel_site" for t in n.targets)
        and isinstance(n.value, ast.Constant)
    }
    undeclared = assigned - set(_RESOLUTION_SITES)
    assert not undeclared, f"funnel assigns undeclared site id(s): {sorted(undeclared)}"
    assert len(assigned) == 16, (
        f"expected 16 DISTINCT funnel site ids, got {len(assigned)}: {sorted(assigned)}. "
        "Two returns sharing an id destroys the measurement — `sweep_age_expiry` and "
        "`ground_state_fallthrough` both return RANGE for opposite reasons."
    )


def test_stage1_lifecycle_reset_has_its_own_site() -> None:
    """The lifecycle/force_reset -> RANGE path returns from resolve() and NEVER enters
    the funnel, so it needs its own site or those bars carry a stale/None one."""
    import ast

    tree, _ = _resolver_source_tree()
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "resolve"
    )
    assigned = {
        n.value.value
        for n in ast.walk(fn)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Attribute) and t.attr == "_last_funnel_site" for t in n.targets)
        and isinstance(n.value, ast.Constant)
        and isinstance(n.value.value, str)
    }
    assert "lifecycle_reset_range" in assigned, (
        "resolve()'s lifecycle-reset early return does not set lifecycle_reset_range"
    )


def test_pre_predicate_split_is_a_subset_of_the_vocabulary() -> None:
    """The pre/post-predicate split is declared ONCE. A second copy on the analysis
    side would drift, and the headline number would silently become wrong."""
    import sys

    sys.path.insert(0, str(REPO / "src"))
    from features.crt_state_resolver import _PRE_PREDICATE_SITES, _RESOLUTION_SITES

    assert _PRE_PREDICATE_SITES <= set(_RESOLUTION_SITES)
    # The five predicate-derived funnel sites must NOT be in the pre-predicate set.
    for site in (
        "funnel_entry_sweep_override",
        "sticky_protects_range_match",
        "predicate_match",
        "sticky_hold_no_match",
        "ground_state_fallthrough",
    ):
        assert site in _RESOLUTION_SITES
        assert site not in _PRE_PREDICATE_SITES, f"{site} evaluates `when:` — not pre-predicate"


def test_resolution_site_is_not_published_when_capture_is_off() -> None:
    """Sites are computed unconditionally (so the default path exercises the same
    branches), but nothing is PUBLISHED unless a caller asks."""
    import sys

    sys.path.insert(0, str(REPO / "src"))
    from features.crt_state_resolver import CRTStateResolver

    r = CRTStateResolver()
    assert r.record_resolver_evidence is False
    assert r.last_resolver_evidence is None
    r._publish_resolution_evidence(
        funnel_state="RANGE", validity_state="RANGE", final_state="RANGE"
    )
    assert r.last_resolver_evidence is None, "publish leaked with capture off"


def test_injection_precedence_beats_validity_and_funnel() -> None:
    """resolution_site must name the DECIDING stage. A bar whose funnel said EXPANSION
    but which stage 3 or 4 rewrote must NOT be billed to the funnel."""
    import sys

    sys.path.insert(0, str(REPO / "src"))
    from features.crt_state_resolver import CRTStateResolver

    r = CRTStateResolver()
    r.record_resolver_evidence = True

    # stage 3 rewrote the funnel's answer
    r.last_resolver_evidence = {}
    r._last_funnel_site = "expansion_dwell_hold"
    r._last_injection_site = None
    r._publish_resolution_evidence(
        funnel_state="EXPANSION", validity_state="RANGE", final_state="RANGE"
    )
    ev = r.last_resolver_evidence
    assert ev["resolution_site"] == "transition_validity_rewrite"
    assert ev["funnel_site"] == "expansion_dwell_hold"   # still visible, not lost
    assert ev["validity_rewrote"] is True
    assert ev["pre_predicate"] is False

    # stage 4 overrode both
    r.last_resolver_evidence = {}
    r._last_funnel_site = "ground_state_fallthrough"
    r._last_injection_site = "engine_injection_expansion"
    r._publish_resolution_evidence(
        funnel_state="RANGE", validity_state="RANGE", final_state="EXPANSION"
    )
    assert r.last_resolver_evidence["resolution_site"] == "engine_injection_expansion"
    assert r.last_resolver_evidence["injection_applied"] is True

    # unchanged through both later stages -> the funnel decided
    r.last_resolver_evidence = {}
    r._last_funnel_site = "sweep_age_expiry"
    r._last_injection_site = None
    r._publish_resolution_evidence(
        funnel_state="RANGE", validity_state="RANGE", final_state="RANGE"
    )
    assert r.last_resolver_evidence["resolution_site"] == "sweep_age_expiry"
    assert r.last_resolver_evidence["pre_predicate"] is True


def test_injection_that_changed_the_answer_without_a_site_is_named_not_silent() -> None:
    """An override with no recorded branch must surface as unattributed, never be
    credited to the funnel — that would be the silent gap in miniature."""
    import sys

    sys.path.insert(0, str(REPO / "src"))
    from features.crt_state_resolver import CRTStateResolver

    r = CRTStateResolver()
    r.record_resolver_evidence = True
    r.last_resolver_evidence = {}
    r._last_funnel_site = "predicate_match"
    r._last_injection_site = None
    r._publish_resolution_evidence(
        funnel_state="SWEEP", validity_state="SWEEP", final_state="EXPANSION"
    )
    assert r.last_resolver_evidence["resolution_site"] == "engine_injection_unattributed"


def test_resolve_end_to_end_populates_a_declared_resolution_site() -> None:
    """End-to-end: a REAL resolve() call must fill resolution_site with a declared id.

    The isolated _publish_resolution_evidence tests above prove the precedence logic;
    this proves the wiring — that some site is actually set on the live path, so the
    field cannot be structurally present but always None (F-056's config-illusion
    shape: declared, read, and never reaching behaviour).
    """
    import sys

    sys.path.insert(0, str(REPO / "src"))
    from features.crt_state_resolver import (
        CRTStateResolver,
        _PRE_PREDICATE_SITES,
        _RESOLUTION_SITES,
    )

    fv = {
        "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5,
        "atr": 0.001, "body_ratio": 0.5, "candle_range": 2.0,
        "liquidity_sweep": 0.0, "sweep_detected": 0.0, "break_of_structure": 0.0,
        "displacement_flag": 0.0, "double_sweep": 0.0, "higher_high": 0.0,
        "lower_low": 0.0, "retest_flag": 0.0, "swing_high": 0.0, "swing_low": 0.0,
        "volume_spike": 0.0, "volatility_regime": 1.0, "trend_bias": 0.0,
        "session": 1.0, "change_of_character": 0.0, "rsi_state": 0.0,
        "rsi_14": 50.0,
    }
    r = CRTStateResolver()
    r.record_resolver_evidence = True
    state = r.resolve(fv, timestamp=None)
    ev = r.last_resolver_evidence
    assert ev is not None, "capture was on but nothing was published"
    assert ev["resolution_site"] in _RESOLUTION_SITES, ev["resolution_site"]
    assert isinstance(ev["pre_predicate"], bool)
    assert ev["pre_predicate"] == (ev["resolution_site"] in _PRE_PREDICATE_SITES)
    # the intermediate states must be published too, so a rewrite is visible
    for k in ("funnel_site", "funnel_state", "validity_state", "injection_state"):
        assert k in ev, k
    assert ev["injection_state"] == state, "published final state != returned state"


@pytest.mark.skipif(not OUT.is_dir(), reason="RC-003 has not been run in this checkout")
def test_every_declared_artifact_was_actually_emitted() -> None:
    """F-083: a declared-but-unexecuted measurement must be indistinguishable from nothing."""
    missing = [n for n in DECLARED_ARTIFACTS if not (OUT / n).is_file()]
    assert not missing, f"declared in section 11 but not emitted by the run: {missing}"


@pytest.mark.skipif(not (OUT / "run_manifest.json").is_file(), reason="RC-003 not run")
def test_run_manifest_pins_the_prereg_and_the_corpus() -> None:
    m = json.loads((OUT / "run_manifest.json").read_text(encoding="utf-8"))
    d = _driver()
    assert m["prereg_frozen_prefix_sha256"] == d.PREREG_SHA256
    assert re.fullmatch(r"[0-9a-f]{64}", m["corpus_sha256"])
    assert m["economic_claims_allowed"] is False
    assert m["promise_rung_max_claim"] == "PL-0"
