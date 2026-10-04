"""
retrieval/truth_tier.py — Truth classification for retrieval chunks.

Why this module exists
----------------------
This repository's defining pathology is *truth divergence*, not code error:
F-047, F-048, F-060, F-061, F-085 and F-088 are all "code does X, doc claims Y".
CLAUDE.md 6.8 forbids collapsing CURRENT / INTENDED / RECOMMENDED, and 6.2 rule 4
mandates append-discipline -- so the corpus **contains contradicting records by
design** (a SUPERSEDED row is kept, never deleted).

A conventional retriever blends a doc chunk and a code chunk into one confident
answer, which is exactly the collapse 6.8 forbids, and ranks a RETIRED finding
beside a live one. This module is the mechanism that prevents both: every chunk
carries a *truth class*, a within-class *authority rank*, and a *lifecycle
status*, so the retriever can partition results instead of blending them.

Design constraints
------------------
  * PURE. Path/text in, classification out. No filesystem access, no config
    reads, no imports from src.* -- so it is trivially testable and cannot drift
    against a runtime state.
  * TABLE-DRIVEN, FIRST-MATCH-WINS. Every rule is a data row with an explicit
    `rule` id that travels with the assignment, so a classification can be
    audited ("why is this HISTORICAL?") rather than taken on faith.
  * DEMOTION REQUIRES EVIDENCE. `lifecycle_status` defaults to LIVE. A non-LIVE
    status is only assigned on a positive, anchored marker match, and the
    matching text is recorded in `status_evidence`. This is deliberately the
    conservative direction: mislabelling live truth as retired would hide it.
  * NO SEMANTICS. This module reads surface markers. It does not decide whether
    a claim is true, and it never adjudicates a conflict (6.8: "the reviewer
    does not pick a winner").

Authority ranks are **within-class**, not global. CURRENT and INTENDED sit on
two different ladders -- 4.0 makes `ACTIVE_VERSION` Tier 0 for *runtime* truth,
while 6.6 makes the ontology authority #1 for *meaning*. Ranking them against
each other would itself be a collapse, so we do not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
# vocabularies (closed)
# --------------------------------------------------------------------------- #

#: What kind of truth a chunk carries. Mirrors CLAUDE.md 6.8's three-way split,
#: widened with REFERENCE (explanatory prose that drifts) and HISTORICAL
#: (point-in-time, explicitly not living).
TRUTH_CLASSES: tuple[str, ...] = (
    "CURRENT",     # what actually executes / is enforced right now
    "INTENDED",    # what things are supposed to mean (ontology, contracts)
    "RECORDED",    # registered conclusions, carrying Confidence
    "REFERENCE",   # explanatory documentation; may drift from code
    "HISTORICAL",  # point-in-time; NOT living (6.2: history is kept, not truth)
    "DERIVED",     # generated views -- never truth, excluded from the index
)

#: Lifecycle markers lifted from source text. LIVE is the default; every other
#: value requires positive anchored evidence.
LIFECYCLE_STATUSES: tuple[str, ...] = (
    "LIVE",
    "SUPERSEDED",
    "RETIRED",
    "KILLED",
    "FROZEN",
    "CLOSED",
    "OPEN",
    "RESOLVED",
    "CONFLICTED",  # contradicting markers found -- surfaced, never resolved here
)

#: Statuses that must never be ranked silently beside live truth.
NON_LIVE_STATUSES: frozenset[str] = frozenset(
    {"SUPERSEDED", "RETIRED", "KILLED", "FROZEN", "CONFLICTED"}
)


@dataclass(frozen=True)
class TierAssignment:
    """The classification of one corpus path.

    Attributes:
        truth_class: One of TRUTH_CLASSES.
        authority_rank: Within-class ordering; 0 is most authoritative.
        rule: Id of the rule that matched -- provenance for the classification
            itself, so a surprising assignment can be traced to its cause.
        indexable: False for DERIVED sources, which are excluded outright.
    """
    truth_class: str
    authority_rank: int
    rule: str
    indexable: bool = True


@dataclass(frozen=True)
class StatusAssignment:
    """The lifecycle status of one chunk of text.

    Attributes:
        status: One of LIFECYCLE_STATUSES.
        status_evidence: The literal matched text, or "" when defaulted to LIVE.
            Present so a demotion is auditable rather than magic.
        markers_found: Every distinct marker seen, for CONFLICTED diagnosis.
    """
    status: str
    status_evidence: str = ""
    markers_found: tuple[str, ...] = ()


# --------------------------------------------------------------------------- #
# path classification rules -- ordered, first match wins
# --------------------------------------------------------------------------- #
# Each row: (rule_id, compiled prefix/glob predicate source, truth_class, rank).
# Patterns are matched against a POSIX-normalised repo-relative path.

_RULES: tuple[tuple[str, str, str, int], ...] = (
    # ---- DERIVED: generated views. Excluded; never truth. -------------------
    # MULTI_LLM_PROTOCOL 5 rule 1: context/*.md is a DERIVED VIEW, and
    # *.generated.md is re-rendered from source. Indexing them alongside their
    # sources produces duplicate, drift-prone answers.
    ("derived.context",        r"^context/",                              "DERIVED",   0),
    ("derived.generated",      r"\.generated\.md$",                       "DERIVED",   1),
    ("derived.generated_any",  r"\.generated\.(json|jsonl|yaml)$",        "DERIVED",   2),

    # ---- CURRENT: what executes. 4.0 Runtime Truth Precedence. -------------
    ("current.active_version", r"^configs/production/ACTIVE_VERSION$",    "CURRENT",   0),
    ("current.prod_config",    r"^configs/production/[^/]+\.json$",       "CURRENT",   1),
    ("current.src",            r"^src/.*\.py$",                           "CURRENT",   2),
    # Tests rank just behind source: they encode what is actually *enforced*,
    # which is a distinct and load-bearing fact in this repo (green floor).
    ("current.tests",          r"^tests/.*\.py$",                         "CURRENT",   3),
    ("current.scripts",        r"^scripts/.*\.py$",                       "CURRENT",   4),
    ("current.hooks",          r"^hooks/",                                "CURRENT",   5),
    ("current.configs_other",  r"^configs/(?!formulas/).*\.(json|yaml|yml)$", "CURRENT", 6),

    # ---- INTENDED: what things mean. 6.6 ontology is meaning-authority #1. --
    ("intended.ontology",      r"^configs/formulas/market_ontology\.yaml$", "INTENDED", 0),
    ("intended.formulas",      r"^configs/formulas/.*\.(yaml|yml)$",      "INTENDED",  1),
    ("intended.semantic_os",   r"^docs/governance/semantic_os/.*\.(yaml|yml)$", "INTENDED", 2),
    ("intended.miar",          r"^docs/governance/MODEL_INTENT_AUTHORITY_REGISTER\.md$", "INTENDED", 3),
    ("intended.miar_registry", r"^docs/governance/miar_registry\.json$",  "INTENDED",  4),
    ("intended.contracts",     r"^docs/governance/[^/]*(CONTRACT|PROTOCOL|POLICY|CHARTER)[^/]*\.(md|json)$", "INTENDED", 5),
    ("intended.active_models", r"^active_models\.yaml$",                  "INTENDED",  6),
    ("intended.intent_docs",   r"^docs/intent/",                          "INTENDED",  7),

    # ---- RECORDED: registered conclusions, carrying Confidence. ------------
    ("recorded.findings_doc",  r"^docs/current-findings\.md$",            "RECORDED",  0),
    ("recorded.findings_data", r"^data/findings\.jsonl$",                 "RECORDED",  1),
    ("recorded.closure_index", r"^docs/governance/closure_authority_index\.json$", "RECORDED", 2),
    ("recorded.claude_md",     r"^CLAUDE\.md$",                           "RECORDED",  3),
    ("recorded.registries",    r"^data/(hypothesis_registry|framework_registry|script_registry|jsonl_claim_catalog)\.jsonl$", "RECORDED", 4),
    ("recorded.claim_catalog", r"^docs/governance/jsonl_claim_catalog\.yaml$", "RECORDED", 5),
    ("recorded.governance",    r"^docs/governance/",                      "RECORDED",  6),

    # ---- HISTORICAL: point-in-time. Explicitly NOT living. -----------------
    # docs/analysis/readme.md itself states these are not living docs. The hot
    # session logs rank first (most recent history), the archive last.
    ("historical.session_log",  r"^(assistant_project|llm_project_assistant)\.md$", "HISTORICAL", 0),
    ("historical.log_archive",  r"^docs/analysis/session-log-archive/",   "HISTORICAL", 1),
    ("historical.analysis",     r"^docs/analysis/",                       "HISTORICAL", 2),
    ("historical.impl_plan",    r"^docs/implementation_plan/",            "HISTORICAL", 3),
    ("historical.plans",        r"^docs/plans/",                          "HISTORICAL", 4),
    ("historical.research",     r"^docs/research/",                       "HISTORICAL", 5),
    ("historical.research_rdy", r"^docs/research-readiness/",             "HISTORICAL", 6),
    ("historical.handover",     r"^docs/handover/",                       "HISTORICAL", 7),

    # ---- REFERENCE: explanatory; drifts. -----------------------------------
    ("reference.reference",    r"^docs/reference/",                       "REFERENCE", 0),
    ("reference.architecture", r"^docs/architecture/",                    "REFERENCE", 1),
    ("reference.memory",       r"^docs/memory/",                          "REFERENCE", 2),
    ("reference.topics",       r"^docs/topics/",                          "REFERENCE", 3),
    ("reference.book",         r"^docs/book/",                            "REFERENCE", 4),
    ("reference.operations",   r"^docs/operations/",                      "REFERENCE", 5),
    ("reference.design",       r"^docs/design/",                          "REFERENCE", 6),
    ("reference.readme",       r"^README\.md$",                           "REFERENCE", 7),
    # Catch-all for docs/ singletons (knowledge-map, timeline, PROJECT_HISTORY,
    # CODEBASE_NAVIGATION, ...). Last so the specific rules above win.
    ("reference.docs_other",   r"^docs/",                                 "REFERENCE", 8),
)

_COMPILED_RULES: tuple[tuple[str, re.Pattern[str], str, int], ...] = tuple(
    (rule_id, re.compile(pattern), truth_class, rank)
    for rule_id, pattern, truth_class, rank in _RULES
)

#: Returned when no rule matches. Deliberately not an exception: an unclassified
#: path is a corpus-scope question for a human, not a crash. The test floor
#: `test_retrieval_truth_tiers.py` asserts this set stays empty for the
#: configured corpus, so a new unclassified path surfaces as a red test.
UNCLASSIFIED = TierAssignment(
    truth_class="REFERENCE", authority_rank=99, rule="unclassified", indexable=False
)


def classify_path(rel_path: str) -> TierAssignment:
    """Classify a repo-relative path into its truth class and authority rank.

    Args:
        rel_path: Repo-relative path. Windows separators are normalised.

    Returns:
        TierAssignment. `indexable` is False for DERIVED sources and for
        anything no rule matched.
    """
    norm = rel_path.replace("\\", "/").lstrip("./")
    for rule_id, pattern, truth_class, rank in _COMPILED_RULES:
        if pattern.search(norm):
            return TierAssignment(
                truth_class=truth_class,
                authority_rank=rank,
                rule=rule_id,
                indexable=(truth_class != "DERIVED"),
            )
    return UNCLASSIFIED


# --------------------------------------------------------------------------- #
# lifecycle status extraction
# --------------------------------------------------------------------------- #
# Anchored patterns only. A bare occurrence of the word "superseded" in running
# prose must NOT demote a chunk -- that would silently hide live truth every
# time a doc merely *discusses* supersession (this file would demote itself).
# Each pattern therefore requires a structural position: a status field, a
# bracketed banner, a JSON/YAML key, or an explicit "SUPERSEDED by <id>" phrase.

_STATUS_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # `**Status:** SUPERSEDED`, `Status: RETIRED`, `| Status | KILLED |`
    ("__field__", re.compile(
        r"(?:^|\|)\s*\**\s*(?:Status|status|STATUS)\s*\**\s*[:|]\s*\**\s*"
        r"(SUPERSEDED|RETIRED|KILLED|FROZEN|CLOSED|OPEN|RESOLVED)\b",
        re.MULTILINE,
    )),
    # JSON / YAML keys: "status": "RETIRED"  |  status: KILLED
    ("__json__", re.compile(
        r"[\"']?(?:status|lifecycle|lifecycle_status|state)[\"']?\s*:\s*[\"']?"
        r"(SUPERSEDED|RETIRED|KILLED|FROZEN|CLOSED|OPEN|RESOLVED)\b",
        re.IGNORECASE,
    )),
    # `superseded_by: F-016`  |  "superseded_by": "..."
    ("SUPERSEDED", re.compile(r"[\"']?superseded_by[\"']?\s*[:=]", re.IGNORECASE)),
    # `-- supersedes F-003` / `SUPERSEDED by F-016` in a findings row
    ("SUPERSEDED", re.compile(r"\bSUPERSEDED\s+(?:by|BY)\b")),
    # Bracketed banners used throughout docs/current-findings.md
    ("RESOLVED", re.compile(r"\*?\*?\[(?:RESOLVED|FIX SHIPPED|REMEDIATED)\b")),
    ("RETIRED", re.compile(r"\b(?:retained-but-)?RETIRED\b(?!\s*\?)")),
    ("KILLED", re.compile(r"\bKILLED\b")),
    ("FROZEN", re.compile(r"\bFROZEN\b")),
)


def classify_status(text: str) -> StatusAssignment:
    """Extract a lifecycle status from chunk text using anchored surface markers.

    Defaults to LIVE. A non-LIVE status requires positive evidence, and the
    matched text is returned so the demotion is auditable. When markers
    disagree the result is CONFLICTED -- surfaced for a human, never resolved
    here (6.2 rule 3: never silently resolve a conflict).

    This is a *surface-marker* reader, not a semantic judge. It can be wrong;
    that is why `status_evidence` travels with every assignment.
    """
    if not text:
        return StatusAssignment(status="LIVE")

    found: dict[str, str] = {}
    for label, pattern in _STATUS_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        status = match.group(1).upper() if label.startswith("__") else label
        found.setdefault(status, match.group(0).strip()[:120])

    if not found:
        return StatusAssignment(status="LIVE")

    markers = tuple(sorted(found))
    # OPEN/CLOSED/RESOLVED are progress states and coexist legitimately with a
    # demotion marker; only a clash between two *demoting* states is a conflict.
    demoting = [s for s in markers if s in NON_LIVE_STATUSES]
    if len(demoting) > 1:
        return StatusAssignment(
            status="CONFLICTED",
            status_evidence="; ".join(found[s] for s in demoting),
            markers_found=markers,
        )
    chosen = demoting[0] if demoting else markers[0]
    return StatusAssignment(
        status=chosen, status_evidence=found[chosen], markers_found=markers
    )


# --------------------------------------------------------------------------- #
# governed-id extraction
# --------------------------------------------------------------------------- #
# These ids are the join keys between a retrieved chunk and the Semantic OS
# grounder (6.7 / CT-008). A retrieval hit is NOT a grounding; carrying the ids
# is what makes the later `--ground` round-trip possible.

_ID_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bF-\d{3}\b"),                      # findings
    re.compile(r"\bFM-\d{3}\b"),                     # feature math
    re.compile(r"\bSEM-\d{3}\b"),                    # semantic objects
    re.compile(r"\bGD-\d{3}\b"),                     # divergence ledger
    re.compile(r"\bIC-\d{3}\b"),                     # integrity checks
    re.compile(r"\bE-\d{3}[A-Z]?\b"),                # epistemic programs
    re.compile(r"\b(?:CN|BD|CT|JN)-[A-Za-z0-9_]+\b"),  # Semantic OS nodes
    re.compile(r"\bCC-[A-Z0-9][A-Z0-9-]*\b"),        # claim catalog classes
    re.compile(r"\bMC-[A-Z0-9][A-Z0-9-]*\b"),        # measurement contracts
    re.compile(r"\bMP-[A-Z0-9][A-Z0-9-]*\b"),        # measurement profiles
    re.compile(r"\bRF-[A-Z0-9][A-Z0-9.-]*\b"),       # research families
)


def extract_ids(text: str, limit: int = 40) -> tuple[str, ...]:
    """Extract governed ids (F-/FM-/SEM-/CC-/CT-/MC-...) from chunk text.

    Returns a sorted, deduplicated tuple capped at *limit* so a pathological
    document cannot bloat the index. These are join keys for the grounding
    step, not claims -- presence of an id asserts nothing about it.
    """
    if not text:
        return ()
    hits: set[str] = set()
    for pattern in _ID_PATTERNS:
        hits.update(pattern.findall(text))
    return tuple(sorted(hits)[:limit])


def is_non_live(status: str) -> bool:
    """True when a status must never be ranked silently beside live truth."""
    return status in NON_LIVE_STATUSES
