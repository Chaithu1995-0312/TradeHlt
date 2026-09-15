"""Floor for the analysis-grain records in run_linkage_registry.json (CH-analysis-trace-linkage).

Two record types live under each instrument alongside the run_id keys:

    _analyses  AN-*  question + claims. Stable across re-measurement.
    _traces    TR-*  one immutable evidence assembly (runs consumed + artifact sha256s).

AN 1-N TR. A re-measurement mints a new TR against the same AN, which is the thing a reused
run_id cannot express (the 2026-09-10 census rebuild inherited run_20260909_202201's id ten
hours after that run was minted).

The load-bearing rule is `test_every_claim_names_a_registered_surface`. The superseded coding-LLM
context pack already carried `claim_protocol.refuse_unnamed_surface: true`, but it could not be
enforced: surfaces lived in the registry keyed by run while claims lived in prose. Co-locating
them turns that rule into a set-membership test -- which is how the `atr_tercile` and `t1_t3`
citations in `withdrawn_claims` were caught.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "docs" / "governance" / "run_linkage_registry.json"

ANALYSES_KEY = "_analyses"
TRACES_KEY = "_traces"

# schema_bridge.surfaces mixes surface status tokens with plain run booleans
# (rebuild_completed, join_logic_fixed_for_future_rebuild). A naive membership test would
# accept `surface: rebuild_completed`, so only string status tokens count as surfaces.
# VALID admits a claim; INVALIDATED is a named refusal, not a silent pass -- before the
# 2026-09-10 surfaces_ruling this set had one token that meant two things (see
# CH-f069-epoch-scope: run_20260909_202201 marked all 8 CREATE surfaces VALID while the
# context pack's forbidden_inferences forbade three of them, and nothing enforced the
# ruling on the machine-readable side).
VALID_SURFACE_TOKENS = {"VALID"}
INVALIDATED_SURFACE_TOKENS = {"INVALIDATED"}
SURFACE_STATUS_TOKENS = VALID_SURFACE_TOKENS | INVALIDATED_SURFACE_TOKENS


def _registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _instruments(reg: dict) -> dict[str, dict]:
    return {k: v for k, v in reg.items() if not k.startswith("_") and isinstance(v, dict)}


def _analyses(reg: dict):
    """Yield (instrument, analysis_id, analysis)."""
    for inst, block in _instruments(reg).items():
        for an_id, an in (block.get(ANALYSES_KEY) or {}).items():
            yield inst, an_id, an


def _traces(reg: dict):
    """Yield (instrument, trace_id, trace)."""
    for inst, block in _instruments(reg).items():
        for tr_id, tr in (block.get(TRACES_KEY) or {}).items():
            yield inst, tr_id, tr


def _run_records(block: dict) -> dict[str, dict]:
    return {k: v for k, v in block.items() if not k.startswith("_") and isinstance(v, dict)}


def _surfaces_for_run(block: dict, run_id: str) -> dict:
    run = _run_records(block).get(run_id) or {}
    bridge = run.get("schema_bridge") or {}
    return bridge.get("surfaces") or {}


def _is_superseded(trace: dict) -> bool:
    return str(trace.get("status", "")).upper() == "SUPERSEDED"


def test_registry_parses_and_reserved_keys_are_not_run_ids():
    reg = _registry()
    for inst, block in _instruments(reg).items():
        for reserved in (ANALYSES_KEY, TRACES_KEY):
            assert reserved.startswith("_"), reserved
        # resolve_artifacts does a keyed run_id lookup; a reserved key must never look like one.
        for key in block:
            if key.startswith("_"):
                assert not key.startswith("run_"), f"{inst}.{key} shadows a run_id"


def test_every_claim_names_a_registered_surface():
    """A claim may only cite a surface some run actually registers, as '<run_id>#<surface>'."""
    reg = _registry()
    checked = 0
    for inst, an_id, an in _analyses(reg):
        block = reg[inst]
        for claim in an.get("claims") or []:
            ref = claim.get("surface")
            assert ref, f"{an_id}.{claim.get('id')} names no surface"
            assert "#" in ref, f"{an_id}.{claim['id']} surface must be '<run_id>#<surface>': {ref}"
            run_id, _, surface = ref.partition("#")
            surfaces = _surfaces_for_run(block, run_id)
            assert surfaces, f"{an_id}.{claim['id']} cites {run_id}, which registers no surfaces"
            assert surface in surfaces, (
                f"{an_id}.{claim['id']} cites unregistered surface {surface!r} on {run_id}"
            )
            value = surfaces[surface]
            assert isinstance(value, str) and value in SURFACE_STATUS_TOKENS, (
                f"{an_id}.{claim['id']} cites {surface!r}, which is not a surface status token "
                f"(got {value!r}) -- booleans in schema_bridge.surfaces are run properties"
            )
            assert value in VALID_SURFACE_TOKENS, (
                f"REFUSED: {an_id}.{claim['id']} cites {run_id}#{surface}, which is "
                f"INVALIDATED -- a claim may not rest on an invalidated surface. See "
                f"{run_id}'s surfaces_ruling for why."
            )
            checked += 1
    assert checked, "no claims found to validate"


def test_claims_reference_a_trace_bound_to_the_same_analysis():
    reg = _registry()
    for inst, an_id, an in _analyses(reg):
        traces = (reg[inst].get(TRACES_KEY) or {})
        for claim in an.get("claims") or []:
            tr_id = claim.get("trace")
            assert tr_id, f"{an_id}.{claim.get('id')} cites no trace"
            assert tr_id in traces, f"{an_id}.{claim['id']} cites unknown trace {tr_id}"
            assert traces[tr_id].get("analysis_id") == an_id, (
                f"{tr_id} does not back-link to {an_id}"
            )


def test_claim_rests_on_artifacts_present_in_its_trace():
    reg = _registry()
    for inst, an_id, an in _analyses(reg):
        traces = reg[inst].get(TRACES_KEY) or {}
        for claim in an.get("claims") or []:
            trace = traces[claim["trace"]]
            known = {a["id"] for a in trace.get("artifacts") or []}
            for art_id in claim.get("rests_on") or []:
                assert art_id in known, (
                    f"{an_id}.{claim['id']} rests on {art_id}, absent from {claim['trace']}"
                )


def test_analysis_and_trace_backlinks_agree_both_ways():
    reg = _registry()
    for inst, an_id, an in _analyses(reg):
        traces = reg[inst].get(TRACES_KEY) or {}
        declared = set(an.get("traces") or [])
        assert declared, f"{an_id} declares no traces"
        for tr_id in declared:
            assert tr_id in traces, f"{an_id} declares unknown trace {tr_id}"
        backlinked = {t for t, tr in traces.items() if tr.get("analysis_id") == an_id}
        assert declared == backlinked, (
            f"{an_id}.traces {sorted(declared)} != traces back-linking to it {sorted(backlinked)}"
        )


def test_every_consumed_run_declares_its_id_basis():
    """analysis run_ids are UTC, backtest run-dir ids are local IST; sorting by id inverts them."""
    reg = _registry()
    for inst, tr_id, tr in _traces(reg):
        if _is_superseded(tr):
            continue
        consumed = tr.get("consumes_runs") or []
        assert consumed, f"{tr_id} consumes no runs"
        for entry in consumed:
            assert entry.get("id_basis") in {"UTC", "IST"}, (
                f"{tr_id} run {entry.get('run_id')} declares no id_basis"
            )
            assert isinstance(entry.get("registered"), bool), (
                f"{tr_id} run {entry.get('run_id')} does not say whether it is registered"
            )


def test_traces_declare_a_clock_basis_and_ordering_key():
    reg = _registry()
    for inst, tr_id, tr in _traces(reg):
        assert tr.get("clock_basis") == "UTC", f"{tr_id} must declare clock_basis UTC"
        assert tr.get("ordering_key") == "generated_at_utc", (
            f"{tr_id} must order by generated_at_utc, never by run_id"
        )


def test_artifacts_are_content_bound_and_run_attribution_is_honest():
    reg = _registry()
    for inst, tr_id, tr in _traces(reg):
        block = reg[inst]
        runs = _run_records(block)
        for art in tr.get("artifacts") or []:
            assert art.get("path"), f"{tr_id} artifact {art.get('id')} has no path"
            sha = art.get("sha256")
            assert sha, f"{tr_id}.{art['id']} is not content-bound"
            if sha != "UNRECOVERABLE":
                assert len(sha) == 64, f"{tr_id}.{art['id']} sha256 malformed"
                assert art.get("generated_at_utc"), (
                    f"{tr_id}.{art['id']} has no generated_at_utc"
                )
            # produced_by_run must be null (honestly unscoped) or a real run in this instrument.
            owner = art.get("produced_by_run", "__missing__")
            assert owner != "__missing__", (
                f"{tr_id}.{art['id']} must state produced_by_run (null is a valid answer)"
            )
            if owner is not None:
                assert owner in runs, f"{tr_id}.{art['id']} claims unknown run {owner}"


def test_superseded_traces_keep_their_supersession_link():
    reg = _registry()
    for inst, tr_id, tr in _traces(reg):
        if not _is_superseded(tr):
            continue
        assert tr.get("superseded_by"), f"{tr_id} is SUPERSEDED with no successor"
        assert tr["superseded_by"] in (reg[inst].get(TRACES_KEY) or {}), (
            f"{tr_id} superseded by unknown trace"
        )
        assert tr.get("analysis_id"), f"{tr_id} must stay bound to its analysis"


def test_withdrawn_claims_are_retained_with_a_reason():
    """Append-discipline (CLAUDE.md 6.2 rule 4): a retracted claim is kept, never deleted."""
    reg = _registry()
    allowed = {"NO_SURFACE", "FORBIDDEN", "SUPERSEDED", "INVALIDATED"}
    for inst, an_id, an in _analyses(reg):
        for w in an.get("withdrawn_claims") or []:
            assert w.get("statement"), f"{an_id} withdrawn entry has no statement"
            assert w.get("reason") in allowed, (
                f"{an_id} withdrawal reason {w.get('reason')!r} not in {sorted(allowed)}"
            )


def test_analyses_carry_no_authority():
    reg = _registry()
    for inst, an_id, an in _analyses(reg):
        assert an.get("authority") == "none", f"{an_id} must not claim authority"
        assert an.get("economic_claims_allowed") is False, (
            f"{an_id} must not enable economic claims"
        )


@pytest.mark.parametrize("bad", ["rebuild_completed", "join_logic_fixed_for_future_rebuild"])
def test_boolean_run_properties_are_not_valid_surfaces(bad):
    """Guards the filter: these live in schema_bridge.surfaces but are not surfaces."""
    reg = _registry()
    for inst, an_id, an in _analyses(reg):
        for claim in an.get("claims") or []:
            assert not claim.get("surface", "").endswith(f"#{bad}"), (
                f"{an_id}.{claim['id']} cites run property {bad!r} as a surface"
            )
