"""Frozen contract for the Opportunity Episode research substrate.

Changing any field in `freeze_block()` requires a new EPISODE_PROTOCOL_ID — episodes
built under a superseded protocol stay readable but are never silently mixed with a
new epoch (non-transferable evidence, same discipline as clean_labels/protocol.py).

Design authority: docs/architecture/opportunity-episode-research-substrate.md
(wins on principle conflict) + docs/architecture/opportunity-episode-platform-design.md
(module layout). Pre-registration: docs/research-readiness/opportunity-episode-prereg.md

Authority: NONE (CLAUDE.md §6.5). Research infrastructure only — no promotion, no
fusion, no live wiring. PRODUCTION_BEHAVIOR_CHANGED = NO.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

PROTOCOL_ID = "OE_L1"
"""First Opportunity Episode epoch."""

PROTOCOL_ID_SUPERSEDED = ""

# ── Root abstraction ────────────────────────────────────────────────────────
ROOT_TYPE = "OpportunityEpisode"

POPULATIONS = (
    "DETECTION_STREAM",    # opportunity_scanner long/short per bar (first corpus)
    "HYPOTHESIS_SIGNAL",   # research.contracts.Signal from Hypothesis.detect
    "SPINE_TRADE",         # CRT TRADE_OPENED → accepted ledger trade
    "SPINE_REJECTED",
    "STRUCTURAL_EVENT",
    "CUSTOM",
)

# ── Timeline convention (substrate §23 decision 2 — FROZEN) ────────────────
# t=0 is the ENTRY BAR observation; the entry bar is carried for context only.
# Every exit policy walks t>=1 exclusively, which is exactly `forward_walk`'s
# no-lookahead contract (it asserts bar.index > signal.entry_index).
T_ZERO_IS_ENTRY_BAR = True
POLICY_WALK_STARTS_AT_T = 1

# ── Observation schema (substrate §23 decision 4 — FROZEN, minimal) ────────
# Immutable facts only. ATR is NOT an observation: it is a rolling indicator
# (FM-041) whose period is config-driven (CLAUDE.md §6.5 exception, 2026-07-18),
# so pinning it per-step would silently bind episodes to a config epoch. The
# entry ATR lives in the entry snapshot; per-step ATR is an opt-in annotation.
OBSERVATION_SCHEMA_VERSION = 1
OBSERVATION_FIELDS = (
    "t",
    "bar_index",
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
)

# ── Exit policy set (v1 — FROZEN) ──────────────────────────────────────────
# EXACTLY the three modes `research.measurement.forward_walk` already implements.
# Adding a policy that the audited kernel cannot express would require a SECOND
# exit simulator — substrate §18 rates that risk CRITICAL. Multi-level exits
# (TP1/TP2 + partial_tp_fraction, F-056) are therefore a declared NON-GOAL of
# this program and need their own pre-registration.
V1_POLICIES = ("intrabar_fixed", "trailing", "close_only")
GOVERNING_POLICY = "intrabar_fixed"
POLICY_KERNEL = "research.measurement.forward_walk"

MAX_FORWARD = 40
COST_BPS = 12.0  # round-trip; diagnostic only — never mutates canonical steps

# ── Two feature namespaces (FROZEN) ────────────────────────────────────────
# Research features must NOT be forced through the production vector. Keeping the
# two apart is what stops the next 38->39-class migration from happening at all:
#
#   canonical  — the 39-dim ordered CANONICAL_FEATURES contract. FROZEN here;
#                changing it is a FEATURE_IDENTITY_CHANGE against the ontology.
#                Episodes do not STORE it — features join by `bar_index`.
#   candidate  — a free-form dict[str, float] on the entry snapshot. Any names,
#                any count, may grow or shrink between research runs.
#
# A dict has no dimension constant, so there is nothing to go stale. The 38->39
# debt exists precisely because a variable-length research idea was expressed as a
# fixed-width contract with a hardcoded length.
#
# Candidate features carry NO authority (§6.5): they may justify research, docs and
# shadow measurement, never sizing, fusion or production weight. A candidate
# graduates into `CANONICAL_FEATURES` only via demonstrated ΔG001 and the existing
# FEATURE_IDENTITY_CHANGE change-class — there is no separate promotion machinery.
FEATURE_NAMESPACES = ("canonical", "candidate")
CANONICAL_NAMESPACE_IS_FROZEN = True
CANDIDATE_NAMESPACE_AUTHORITY = "none"

# ── Contamination discipline ───────────────────────────────────────────────
# F-022: opportunities.jsonl is a DETECTION stream, not a trade ledger (~36.8%
# self-consistent). Its outcome/rr/mfe/mae fields may only land under
# metadata.diagnostics and may NEVER become canonical episode or label fields.
FORBIDDEN_AS_CANONICAL = (
    "stream.outcome",
    "stream.rr_achieved",
    "stream.mfe",
    "stream.mae",
)

# F-051: stored opportunity features may predate the FC1-A causal swings.
PIT_STATUS = "PIT_UNCLEAN_STORED_FEATURES"

TIMEFRAME = "M15"
ARTIFACT_ROOT = "results/research/episodes"

AUTHORITY = "research_substrate_only"


def freeze_block() -> dict[str, Any]:
    """Machine-readable freeze payload (hashed into the protocol hash)."""
    return {
        "protocol_id": PROTOCOL_ID,
        "supersedes": PROTOCOL_ID_SUPERSEDED,
        "root_type": ROOT_TYPE,
        "populations": list(POPULATIONS),
        "t_convention": {
            "t_zero_is_entry_bar": T_ZERO_IS_ENTRY_BAR,
            "policy_walk_starts_at_t": POLICY_WALK_STARTS_AT_T,
        },
        "observation_schema_version": OBSERVATION_SCHEMA_VERSION,
        "observation_fields": list(OBSERVATION_FIELDS),
        "feature_namespaces": {
            "namespaces": list(FEATURE_NAMESPACES),
            "canonical_is_frozen": CANONICAL_NAMESPACE_IS_FROZEN,
            "candidate_authority": CANDIDATE_NAMESPACE_AUTHORITY,
            "candidate_excluded_from_content_hash": True,
            "graduation": "candidate -> canonical only via ΔG001 + FEATURE_IDENTITY_CHANGE",
        },
        "v1_policies": list(V1_POLICIES),
        "governing_policy": GOVERNING_POLICY,
        "policy_kernel": POLICY_KERNEL,
        "max_forward": MAX_FORWARD,
        "cost_bps": COST_BPS,
        "pit_status": PIT_STATUS,
        "timeframe": TIMEFRAME,
        "artifact_root": ARTIFACT_ROOT,
        "forbidden_as_canonical": list(FORBIDDEN_AS_CANONICAL),
        "invariants": {
            "episode_is_policy_independent": True,
            "exit_policy_hash_lives_on_labelset_not_episode": True,
            "events_are_derived_never_stored_in_episode": True,
            "observations_immutable_annotations_versioned": True,
            "no_second_exit_kernel": True,
            "production_behavior_changed": "NO",
        },
        "non_goals": [
            "live / hot-path episode construction",
            "TradeJournal writing the research store",
            "nested episodes inside opportunities.jsonl as system of record",
            "multi-level (partial TP / TP1+TP2) exit policies",
            "training tensors as canonical storage",
            "promotion / fusion / spine-wiring authority",
        ],
        "authority": AUTHORITY,
    }


def compute_protocol_hash(extra: dict[str, Any] | None = None) -> str:
    """Stable SHA-256 over freeze_block (+ optional scope, e.g. instrument)."""
    payload = freeze_block()
    if extra:
        payload = {**payload, "extra": extra}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
