"""stack_version.py — Phase 0 floors (Research Provenance Spine).

Five invariants that make `behavior_hash` trustworthy as a citation key:
  1. determinism   — unchanged inputs -> identical hash across calls
  2. churn guard   — additive-only ontology edits (taxonomy/semantics/notes) never
                     move behavior_hash, but DO move provenance_hash
  3. sensitivity   — an active formula/impl change DOES move behavior_hash
  4. inert model   — mutating a non-executing family's artifact does not
  5. ledger        — append-only, monotonic epoch, provenance-only churn doesn't
                     mint a new epoch

No authority is exercised anywhere in this module — these floors only pin that fact
(no promote/enable/write-to-config surface), consistent with `production_bundle.py`'s
own `authority: NONE` discipline.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from config_layer.stack_version import (
    StackVersionError,
    append_epoch_record,
    compute_stack_version,
    resolve_epoch,
)

_REPO = Path(__file__).resolve().parents[1]


def test_determinism():
    a = compute_stack_version()
    b = compute_stack_version()
    assert a.behavior_hash == b.behavior_hash
    assert a.provenance_hash == b.provenance_hash


def test_churn_guarantee(tmp_path, monkeypatch):
    """Editing an additive-only ontology block (not a frozen runtime key) must move
    provenance_hash and leave behavior_hash byte-identical."""
    ontology_path = _REPO / "configs" / "formulas" / "market_ontology.yaml"
    original = ontology_path.read_text(encoding="utf-8")

    before = compute_stack_version()

    # Append a harmless top-level comment line — touches the file's bytes (moves
    # provenance's full-file sha256) without touching any frozen runtime key.
    try:
        ontology_path.write_text(
            original + "\n# stack_version churn-guarantee test marker\n", encoding="utf-8"
        )
        after = compute_stack_version()
        assert after.behavior_hash == before.behavior_hash, (
            "a comment-only ontology edit must not move behavior_hash"
        )
        assert after.provenance_hash != before.provenance_hash, (
            "a comment-only ontology edit SHOULD move provenance_hash "
            "(full-file sha256 is part of provenance, by design)"
        )
    finally:
        ontology_path.write_text(original, encoding="utf-8")


def test_sensitivity_to_active_formula_change():
    """Changing a frozen runtime key (e.g. a `formula` string) on a real entry DOES
    move behavior_hash — the inverse of the churn guarantee."""
    ontology_path = _REPO / "configs" / "formulas" / "market_ontology.yaml"
    original = ontology_path.read_text(encoding="utf-8")

    before = compute_stack_version()

    # Perturb the FIRST occurrence of a real `formula: "..."` entry — guaranteed to
    # exist per the ontology's own spec_schema.frozen_runtime_keys contract. Must
    # mutate INSIDE the quoted value, not append a trailing comment — YAML strips
    # a `# ...` comment after a quoted scalar, so it would never reach the parsed
    # value and this test would falsely pass.
    lines = original.splitlines(keepends=True)
    target_idx = next(
        i for i, l in enumerate(lines) if l.strip().startswith('formula:') and '"' in l
    )
    lines[target_idx] = lines[target_idx].replace('"', '"MUTATED_', 1)
    mutated = "".join(lines)

    try:
        ontology_path.write_text(mutated, encoding="utf-8")
        after = compute_stack_version()
        assert after.behavior_hash != before.behavior_hash, (
            "mutating a `formula:` value must move behavior_hash"
        )
    finally:
        ontology_path.write_text(original, encoding="utf-8")


def test_inert_model_insensitivity():
    """A family that does not execute a checkpoint (`executes_checkpoint=False`) must
    not appear in the `who_enabled` behavior component — its artifact can churn freely."""
    stack = compute_stack_version()
    from config_layer.production_bundle import load_production_bundle

    bundle = load_production_bundle(active_version=stack.active_version)
    enabled_families = {f for f, _v, _a in stack.components["who_enabled"]}
    for family, member in bundle.members.items():
        if not member.executes_checkpoint:
            assert family not in enabled_families, (
                f"{family} does not execute a checkpoint but leaked into who_enabled"
            )


def test_no_authority_surface():
    """This module exposes no promote/enable/write-to-config function."""
    import config_layer.stack_version as sv

    forbidden_prefixes = ("promote", "enable", "write_config", "activate")
    for name in dir(sv):
        assert not any(name.startswith(p) for p in forbidden_prefixes), (
            f"stack_version exposes {name!r} — looks like a write-authority surface"
        )


class TestEpochLedger:
    def test_first_record_mints_epoch_1(self, tmp_path):
        stack = compute_stack_version()
        log_path = tmp_path / "stack_epoch_log.jsonl"
        rec = append_epoch_record(stack, log_path=log_path)
        assert rec["kind"] == "STACK_EPOCH"
        assert rec["stack_epoch"] == 1

    def test_same_behavior_appends_provenance_not_new_epoch(self, tmp_path):
        stack = compute_stack_version()
        log_path = tmp_path / "stack_epoch_log.jsonl"
        first = append_epoch_record(stack, log_path=log_path)
        second = append_epoch_record(stack, log_path=log_path)
        assert second["kind"] == "STACK_PROVENANCE"
        assert second["stack_epoch"] == first["stack_epoch"] == 1

    def test_ledger_is_append_only(self, tmp_path):
        stack = compute_stack_version()
        log_path = tmp_path / "stack_epoch_log.jsonl"
        append_epoch_record(stack, log_path=log_path)
        append_epoch_record(stack, log_path=log_path)
        lines = log_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        # Every line must remain valid, independently parseable JSON (no rewrite).
        for line in lines:
            json.loads(line)

    def test_resolve_epoch_is_read_only(self, tmp_path):
        stack = compute_stack_version()
        log_path = tmp_path / "stack_epoch_log.jsonl"
        epoch, is_new = resolve_epoch(stack, log_path=log_path)
        assert is_new is True
        assert epoch == 1
        assert not log_path.exists(), "resolve_epoch must never write"


def test_missing_config_raises_stack_version_error(tmp_path):
    with pytest.raises(StackVersionError):
        compute_stack_version(active_version="__does_not_exist__")
