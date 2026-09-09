"""
Feature-math registry — the AUTHORITATIVE source of feature-mathematics implementation.

Authority model (CLAUDE.md §6.5): the ontology (configs/formulas/market_ontology.yaml) DECLARES
what each quantity means; THIS registry is the single authority for HOW it is computed. Formulas
are NEVER `eval`'d — every declared name resolves to an explicit, named callable.

PUBLIC API (import from `features.formula_registry` facade or here):
    FORMULA_REGISTRY, compute_composition, compute_derived, validate_registry,
    build_lineage_graph, load_ontology

The sub-registries (primitive_/composition_/derived_registry, _loader) are INTERNAL — consumers
must not import them directly (enforced by tests/test_feature_lineage.py). Internal splits may
evolve freely behind this stable surface.
"""
from __future__ import annotations

from typing import Callable

from features.registry._loader import load_ontology, _ONTOLOGY_PATH
from features.registry.primitive_registry import PRIMITIVES, PRIMITIVE_SHORTNAME
from features.registry.composition_registry import compute_composition
from features.registry.derived_registry import DERIVED, compute_derived

# The aggregated executor: every declared impl name -> its explicit Python callable (NO eval).
FORMULA_REGISTRY: dict[str, Callable] = {**PRIMITIVES, **DERIVED}

_VALID_LIFECYCLE = (
    "proposed", "research", "registered", "parity_verified", "consumable", "deprecated",
)

__all__ = [
    "FORMULA_REGISTRY", "compute_composition", "compute_derived",
    "validate_registry", "validate_semantic_registry",
    "load_structural_profiles", "validate_structural_profiles",
    "validate_crt_threshold_refs",
    "build_lineage_graph", "load_ontology", "_ONTOLOGY_PATH",
]


_ITERATED_SECTIONS = ("primitives", "feature_compositions", "derived_metrics", "rolling_indicators",
                      "temporal_context", "structural_states")


def _iter_entries(ont: dict):
    """Yield (section, name, spec) for every governed feature across the iterated sections.

    `rolling_indicators` (windowed ATR/RSI/EMA/... first-class since 2026-07-12) are iterated for
    lineage + id/version/lifecycle governance, but are EXEMPT from the scalar-FORMULA_REGISTRY
    impl-resolution in validate_registry (they carry `computation_class: rolling` and are computed by
    the pipeline — no scalar callable exists; a SERIES-level parity probe binds them instead).
    """
    for section in _ITERATED_SECTIONS:
        for name, spec in (ont.get(section) or {}).items():
            yield section, name, spec


def validate_registry(ontology: dict | None = None) -> list[str]:
    """
    Return a list of consistency problems between the ontology and the registry.
    Empty list == the WHAT authority and the executor agree. Used by the parity/lineage tests.

    Checks: every impl resolves; primitives/derived carry a formula; compositions carry
    numerator+denominator that resolve to primitives; ids unique; version is an int; lifecycle valid.
    """
    ont = ontology or load_ontology()
    problems: list[str] = []
    seen_ids: dict[str, str] = {}

    for section, name, spec in _iter_entries(ont):
        # id uniqueness + presence
        fid = spec.get("id")
        if not fid:
            problems.append(f"{section} '{name}': missing id")
        elif fid in seen_ids:
            problems.append(f"{section} '{name}': duplicate id {fid!r} (also {seen_ids[fid]!r})")
        else:
            seen_ids[fid] = name
        # version
        if not isinstance(spec.get("version"), int):
            problems.append(f"{section} '{name}': version must be an int")
        # lifecycle
        lc = spec.get("lifecycle")
        if lc not in _VALID_LIFECYCLE:
            problems.append(f"{section} '{name}': invalid lifecycle {lc!r}")

        if section == "feature_compositions":
            for side in ("numerator", "denominator"):
                ref = spec.get(side)
                if ref not in PRIMITIVE_SHORTNAME:
                    problems.append(f"composition '{name}': {side} {ref!r} not a known primitive")
        elif section == "rolling_indicators":
            # WINDOWED-impl exemption: no scalar callable exists (the pipeline is the computation
            # authority). Require a formula + a named computation authority + the class marker.
            if not str(spec.get("formula", "")).strip():
                problems.append(f"rolling_indicators '{name}': missing formula declaration")
            if not str(spec.get("impl", "")).strip():
                problems.append(f"rolling_indicators '{name}': missing impl (pipeline computation authority)")
            if spec.get("computation_class") not in ("rolling", "rolling_stateful"):
                problems.append(f"rolling_indicators '{name}': missing computation_class rolling/rolling_stateful")
        elif section == "temporal_context":
            # CALENDAR-impl exemption (Item-2, 2026-07-19): per-bar projections of the bar's own
            # timestamp. No scalar market-math callable exists (and derived_math.py is explicitly
            # scalar float->float ATR/price-relative), so like rolling_indicators these are exempt
            # from FORMULA_REGISTRY resolution; `impl` names the pipeline computation authority.
            if not str(spec.get("formula", "")).strip():
                problems.append(f"temporal_context '{name}': missing formula declaration")
            if not str(spec.get("impl", "")).strip():
                problems.append(f"temporal_context '{name}': missing impl (pipeline computation authority)")
            if spec.get("computation_class") != "calendar":
                problems.append(f"temporal_context '{name}': missing computation_class calendar")
        elif section == "structural_states":
            # EVENT/CLASSIFICATION-impl exemption (v1.4, 2026-07-24): these emit a small enumerated
            # domain (a detection event or a classification), not a magnitude. Like
            # rolling_indicators/temporal_context there is no scalar market-math callable, so they
            # are exempt from FORMULA_REGISTRY resolution; `impl` names the pipeline authority.
            # UNLIKE those two, a non-empty `states` block is REQUIRED — recording the legal values
            # without recording what they MEAN is the gap this section exists to close.
            if not str(spec.get("formula", "")).strip():
                problems.append(f"structural_states '{name}': missing formula declaration")
            if not str(spec.get("impl", "")).strip():
                problems.append(f"structural_states '{name}': missing impl (pipeline computation authority)")
            if spec.get("computation_class") != "structural_state":
                problems.append(f"structural_states '{name}': missing computation_class structural_state")
            if not spec.get("states"):
                problems.append(f"structural_states '{name}': requires a non-empty `states` block")
        else:
            impl = spec.get("impl")
            if impl not in FORMULA_REGISTRY:
                problems.append(f"{section} '{name}': impl {impl!r} not in FORMULA_REGISTRY")
            if not str(spec.get("formula", "")).strip():
                problems.append(f"{section} '{name}': missing formula declaration")
        # registered+ must resolve its impl (compositions resolve via primitives, handled above)
        if lc in ("registered", "parity_verified", "consumable", "deprecated") and not fid:
            problems.append(f"{section} '{name}': lifecycle {lc!r} requires an id")

    problems.extend(_validate_spec_schema(ont))
    return problems


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE SPECIFICATION SCHEMA (ontology v1.4) — deliberately ISOLATED from the
# per-section checks above. Those validate the EXECUTION contract (does the impl
# resolve, is the computation class declared); this validates the KNOWLEDGE
# contract (is the feature self-describing).
#
# SCOPE LIMIT (non-negotiable): referential integrity on `depends_on` is a plain
# set-inclusion test. No DAG traversal, no topological sort, no derivation-depth
# computation happens here. `derivation_depth` is a DESCRIPTIVE integer in the
# YAML, and the acyclic/grounded property is already asserted offline by
# tests/test_feature_lineage.py::test_dependency_graph_acyclic_and_grounded —
# duplicating it inside a function that runs on the live CRT import path would
# add cost and create a second source of truth for the same property.
# ─────────────────────────────────────────────────────────────────────────────

_SPEC_BLOCKS = ("taxonomy", "semantics", "states", "lineage")


def _validate_spec_schema(ont: dict) -> list[str]:
    """Validate the v1.4 Feature Specification blocks. Returns a list of problems."""
    schema = ont.get("spec_schema") or {}
    categories = set(schema.get("category_vocabulary") or ())
    knowledge_classes = set(schema.get("knowledge_class_vocabulary") or ())
    if not categories or not knowledge_classes:
        return ["spec_schema: missing category_vocabulary / knowledge_class_vocabulary"]

    known = {name for _s, name, _sp in _iter_entries(ont)}
    known |= set(ont.get("base_inputs") or ())

    problems: list[str] = []
    for section, name, spec in _iter_entries(ont):
        where = f"{section} '{name}'"

        for block in _SPEC_BLOCKS:
            if block not in spec:
                problems.append(f"{where}: missing required spec block {block!r}")
        # `states` is the one block whose EMPTY form is meaningful (continuous features), so it
        # must be a list — never None. A YAML `null` here would deserialize to None and make
        # `spec.get("states", [])` return None, breaking every downstream iteration.
        if "states" in spec and not isinstance(spec["states"], list):
            problems.append(
                f"{where}: `states` must be a list (use [] for continuous features, never null)"
            )

        tax = spec.get("taxonomy") or {}
        cat, kcls = tax.get("category"), tax.get("knowledge_class")
        if cat not in categories:
            problems.append(f"{where}: taxonomy.category {cat!r} not in category_vocabulary")
        if kcls not in knowledge_classes:
            problems.append(
                f"{where}: taxonomy.knowledge_class {kcls!r} not in knowledge_class_vocabulary"
            )

        sem = spec.get("semantics") or {}
        for field in ("description", "why_it_exists", "interpretation"):
            if not sem.get(field):
                problems.append(f"{where}: semantics.{field} is empty")

        lin = spec.get("lineage") or {}
        for field in ("derivation_depth", "produced_by", "consumed_by", "vector_key", "vector_index"):
            if field not in lin:
                problems.append(f"{where}: lineage.{field} is absent (declare [] when unbound)")
        if lin.get("consumed_by") is None:
            problems.append(f"{where}: lineage.consumed_by is null — use [] or [UNKNOWN]")

        # An ENUMERATED domain ("{0, 1}") carries meaning per value, so it must name its states.
        # A RANGE ("[0, 100]") does not — rsi_14 has no meaningful per-value semantics.
        bounds = str(spec.get("bounds") or "").strip()
        if bounds.startswith("{") and not spec.get("states"):
            problems.append(
                f"{where}: declares an enumerated domain {bounds} but has no `states` block"
            )

        # Referential integrity ONLY — set inclusion, no traversal (see scope limit above).
        for dep in (spec.get("depends_on") or ()):
            if dep not in known:
                problems.append(
                    f"{where}: depends_on {dep!r} is neither a registered entry nor a base_input"
                )

    return problems


def build_lineage_graph(ontology: dict | None = None) -> dict:
    """
    Build the feature dependency DAG from the ontology's `depends_on` edges.

    Returns {"depends_on": {name: [deps]}, "used_by": {name: [users]}, "nodes": [...],
             "base_inputs": [...]}. `used_by` is COMPUTED as the transpose of `depends_on`
    (never stored). Nodes include registered features and declared base_inputs.
    """
    ont = ontology or load_ontology()
    base_inputs = list(ont.get("base_inputs") or [])

    depends_on: dict[str, list[str]] = {}
    for _section, name, spec in _iter_entries(ont):
        depends_on[name] = list(spec.get("depends_on") or [])

    nodes = set(depends_on) | set(base_inputs)
    for deps in depends_on.values():
        nodes |= set(deps)

    used_by: dict[str, list[str]] = {n: [] for n in nodes}
    for name, deps in depends_on.items():
        for d in deps:
            used_by.setdefault(d, []).append(name)

    return {
        "depends_on": depends_on,
        "used_by": {k: sorted(v) for k, v in used_by.items()},
        "nodes": sorted(nodes),
        "base_inputs": base_inputs,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CANONICAL MARKET ONTOLOGY EVOLUTION CONTRACT (2026-07-25) — semantic-registry validator.
#
# Sibling to validate_registry, but over the NON-frozen semantic sections declared in
# spec_schema.semantic_registry.sections. These sections are invisible to _ITERATED_SECTIONS, the
# frozen runtime binding (fm_resolve), and validate_registry — so they get their OWN validator.
# Ontology-first: every vocabulary (ladder / categories / required fields) is READ FROM the
# ontology's spec_schema, never hard-coded here.
# ─────────────────────────────────────────────────────────────────────────────

def _semantic_field_empty(value, unknown_token: str) -> bool:
    """A field counts as 'not filled in' when it is UNKNOWN, empty, or the UNKNOWN sentinel list."""
    if value is None:
        return True
    if value == unknown_token or value == [unknown_token] or value == []:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


_SEMANTIC_LIST_FIELDS = (
    "aliases", "dependencies", "required_inputs", "produced_outputs",
    "producers", "consumers", "transitions", "validation_rules",
)


def validate_semantic_registry(ontology: dict | None = None) -> list[str]:
    """
    Enforce the Canonical Market Ontology Evolution Contract over the non-frozen semantic sections.
    Returns a list of problems; empty list == contract satisfied.

    Checks (per node): every required field PRESENT (value may be UNKNOWN/[] — never fabricated);
    id present + globally unique across ALL sections (FM-0NN and SEM-/UNK- ids); version is int;
    semantic_category in vocabulary; knowledge_status in the ladder; evidence + origin non-empty
    once knowledge_status is above UNKNOWN; canonical_unknowns nodes stay UNKNOWN/OBSERVED (they
    graduate IN PLACE into a typed section, never duplicate); list fields are [] not null.
    """
    ont = ontology or load_ontology()
    sr = (ont.get("spec_schema") or {}).get("semantic_registry") or {}
    sections = tuple(sr.get("sections") or ())
    ladder = tuple(sr.get("knowledge_status_ladder") or ())
    categories = set(sr.get("semantic_category_vocabulary") or ())
    required = tuple(sr.get("semantic_node_required_fields") or ())
    epistemic_fields = tuple(sr.get("epistemic_fields") or ())
    unknown = sr.get("unknown_token", "UNKNOWN")

    if not sections or not ladder or not categories or not required or not epistemic_fields:
        return [
            "spec_schema.semantic_registry: missing sections / knowledge_status_ladder / "
            "semantic_category_vocabulary / semantic_node_required_fields / epistemic_fields "
            "declaration"
        ]
    ladder_set = set(ladder)

    # Global id namespace: seed with the FROZEN FM ids so semantic ids can never collide with them.
    seen_ids: dict[str, str] = {}
    for _s, name, spec in _iter_entries(ont):
        fid = spec.get("id")
        if fid:
            seen_ids[fid] = name

    problems: list[str] = []
    for section in sections:
        block = ont.get(section)
        if block is None:
            continue  # a declared section may be empty until seeded
        if not isinstance(block, dict):
            problems.append(f"semantic section {section!r}: must be a mapping (got {type(block).__name__})")
            continue
        for name, spec in block.items():
            where = f"{section} '{name}'"
            if not isinstance(spec, dict):
                problems.append(f"{where}: node must be a mapping")
                continue

            for field in required:
                if field not in spec:
                    problems.append(
                        f"{where}: missing required field {field!r} "
                        f"(declare {unknown}/[] if undiscovered — never omit)"
                    )

            fid = spec.get("id")
            if not fid or fid == unknown:
                problems.append(f"{where}: id must be present and not {unknown}")
            elif fid in seen_ids:
                problems.append(f"{where}: duplicate id {fid!r} (also {seen_ids[fid]!r})")
            else:
                seen_ids[fid] = name

            if not isinstance(spec.get("version"), int):
                problems.append(f"{where}: version must be an int")

            cat = spec.get("semantic_category")
            if cat not in categories:
                problems.append(f"{where}: semantic_category {cat!r} not in semantic_category_vocabulary")

            ks = spec.get("knowledge_status")
            if ks not in ladder_set:
                problems.append(f"{where}: knowledge_status {ks!r} not in knowledge_status_ladder")
            elif ks != "UNKNOWN":
                if _semantic_field_empty(spec.get("evidence"), unknown):
                    problems.append(f"{where}: evidence must be non-empty once knowledge_status is above UNKNOWN")
                if _semantic_field_empty(spec.get("origin"), unknown):
                    problems.append(f"{where}: origin must be non-empty once knowledge_status is above UNKNOWN")

            if section == "canonical_unknowns" and ks not in ("UNKNOWN", "OBSERVED"):
                problems.append(
                    f"{where}: canonical_unknowns node must be UNKNOWN/OBSERVED — graduate its "
                    "knowledge_status IN PLACE and move it into a typed section on refinement"
                )

            for lf in _SEMANTIC_LIST_FIELDS:
                if lf in spec and spec[lf] is None:
                    problems.append(f"{where}: {lf} is null — use [] (absent-means-empty is a trap)")

            # Epistemic-block discipline: separate epistemic LEVELS so a hypothesis cannot become a
            # "fact" by repetition. MANDATORY when knowledge_status == UNKNOWN; validated whenever
            # present (any status). `observation` = the node's observed_behaviour; not re-checked.
            epi = spec.get("epistemic")
            if ks == "UNKNOWN" and not isinstance(epi, dict):
                problems.append(
                    f"{where}: knowledge_status UNKNOWN requires an `epistemic` block "
                    f"(known_invariants / unknown_mechanism / candidate_hypotheses / "
                    f"resolution_metric / falsification_conditions)"
                )
            elif isinstance(epi, dict):
                for ef in epistemic_fields:
                    if ef not in epi:
                        problems.append(
                            f"{where}: epistemic.{ef} missing (declare {unknown}/[] if undiscovered)"
                        )
                for lf in ("known_invariants", "candidate_hypotheses", "falsification_conditions"):
                    if lf in epi and epi[lf] is None:
                        problems.append(f"{where}: epistemic.{lf} is null — use []")

    return problems


# ─────────────────────────────────────────────────────────────────────────────
# STRUCTURE PROFILES (RC-9, 2026-08-19) — the FOUNDING half of the structural kernel.
#
# Sibling of the ontology, NOT a `spec_schema.semantic_registry.sections` entry: a section
# entry would force all 25 `semantic_node_required_fields` onto a nine-field profile table and
# run it through the wrong walker. Own file, own closed validator, reached through
# `spec_schema.semantic_registry.external_sections.structural_profiles`.
#
# FAIL-CLOSED, NEVER FAIL-AT-IMPORT: a missing sibling yields a validator PROBLEM, never an
# exception. `load_ontology` is on the path of `from features.registry import FORMULA_REGISTRY`,
# which `crt_engine_v2` imports — raising here would break the engine over a missing
# research-declaration file. Pinned by a test that hides the sibling and imports the engine.
# ─────────────────────────────────────────────────────────────────────────────

import re as _re
from pathlib import Path as _Path

_PROFILE_REQUIRED_KEYS = (
    "id", "aliases", "founding", "walk", "status", "owner", "evidence", "origin", "version",
)
_PROFILE_STATUSES = ("research", "registered")
_PROFILE_ID_RE = _re.compile(r"^SPP-\d+$")


def _external_section_path(ontology: dict, name: str):
    """Absolute path for a declared external section, or None when the pointer is absent."""
    sr = (ontology.get("spec_schema") or {}).get("semantic_registry") or {}
    rel = (sr.get("external_sections") or {}).get(name)
    if not rel:
        return None
    return (_Path(_ONTOLOGY_PATH).resolve().parents[2] / rel).resolve()


def load_structural_profiles(ontology: dict | None = None) -> dict:
    """Load the structure-profiles sibling. Returns {} when the pointer or file is absent.

    Reuses `load_ontology(path)` — already a generic, mtime-keyed YAML cache — so the sibling
    gets its own independent cache entry with no new caching machinery.
    """
    ont = ontology if ontology is not None else load_ontology()
    path = _external_section_path(ont, "structural_profiles")
    if path is None or not path.exists():
        return {}
    return load_ontology(path)


def _declared_ontology_ids(ont: dict) -> set:
    """Every id a profile is allowed to reference (frozen + semantic sections)."""
    ids = set()
    for _sec, _name, spec in _iter_entries(ont):
        if spec.get("id"):
            ids.add(spec["id"])
    sr = (ont.get("spec_schema") or {}).get("semantic_registry") or {}
    for section in tuple(sr.get("sections") or ()):
        for spec in (ont.get(section) or {}).values():
            if isinstance(spec, dict) and spec.get("id"):
                ids.add(spec["id"])
    return ids


def validate_structural_profiles(ontology: dict | None = None) -> list:
    """Validate structure profiles against their own closed contract. [] == satisfied."""
    ont = ontology if ontology is not None else load_ontology()
    path = _external_section_path(ont, "structural_profiles")
    if path is None:
        return []                                # no pointer declared: nothing to validate
    if not path.exists():
        return [
            f"external_sections.structural_profiles points at {path}, which does not exist "
            "(fail-closed: a problem here, never an import-time raise)"
        ]

    doc = load_structural_profiles(ont)
    problems: list = []
    if doc.get("schema") != "structure_profiles/v1":
        problems.append(f"structure_profiles: unsupported schema {doc.get('schema')!r}")

    block = doc.get("structural_profiles")
    if not isinstance(block, dict) or not block:
        problems.append("structure_profiles: `structural_profiles` must be a non-empty mapping")
        return problems

    known_ids = _declared_ontology_ids(ont)
    seen: dict = {}

    for name, prof in block.items():
        where = f"structural_profiles '{name}'"
        if not isinstance(prof, dict):
            problems.append(f"{where}: profile must be a mapping")
            continue

        for key in _PROFILE_REQUIRED_KEYS:
            if key not in prof:
                problems.append(f"{where}: missing required key {key!r}")

        pid = prof.get("id")
        if not isinstance(pid, str) or not _PROFILE_ID_RE.match(pid or ""):
            problems.append(f"{where}: id {pid!r} must match ^SPP-<digits>$")
        elif pid in seen:
            problems.append(f"{where}: duplicate id {pid!r} (also {seen[pid]!r})")
        else:
            seen[pid] = name

        if prof.get("status") not in _PROFILE_STATUSES:
            problems.append(
                f"{where}: status {prof.get('status')!r} not in {list(_PROFILE_STATUSES)} "
                "(the semantic-node `status`, never an FM `lifecycle` token)"
            )

        if not isinstance(prof.get("version"), int):
            problems.append(f"{where}: version must be an int")

        for list_key in ("aliases", "evidence"):
            if list_key in prof and not isinstance(prof[list_key], list):
                problems.append(f"{where}: {list_key} must be a list")

        walk = prof.get("walk")
        if isinstance(walk, str) and walk != "UNKNOWN" and walk not in known_ids:
            problems.append(f"{where}: walk {walk!r} is not a declared ontology id")

        for pred in (prof.get("predicates") or []):
            if pred != "UNKNOWN" and pred not in known_ids:
                problems.append(f"{where}: predicate {pred!r} is not a declared ontology id")

        founding = prof.get("founding")
        if not isinstance(founding, dict):
            problems.append(f"{where}: founding must be a mapping")
            continue

        fid = founding.get("identity")
        if fid is None:
            problems.append(f"{where}: founding.identity absent (declare UNKNOWN if none exists)")
        elif fid != "UNKNOWN" and fid not in known_ids:
            problems.append(f"{where}: founding.identity {fid!r} is not a declared ontology id")

        # thresholds are NAMES, never VALUES — a number here is a second source of truth
        for tname, tval in (founding.get("threshold_refs") or {}).items():
            if isinstance(tval, (int, float)) and not isinstance(tval, bool):
                problems.append(
                    f"{where}: threshold_refs.{tname} is a VALUE ({tval!r}); a profile carries "
                    "the NAME of a CRTConfig / production-JSON / MC-* field, never its value"
                )

    return problems


# ─────────────────────────────────────────────────────────────────────────────
# CRT THRESHOLD REFS (Phase D, CH-crt-sot-2026-08-31)
# ─────────────────────────────────────────────────────────────────────────────
# configs/formulas/market_crt_states.yaml:threshold_refs is a SEPARATE file/section from the
# ontology's structural_profiles above -- not reached via load_ontology(), not an
# external_sections pointer. Housed here anyway, consistent with validate_structural_profiles'
# own precedent immediately above (also not an ontology `sections` entry; this module is where
# closed-contract validators over the CRT/structural artifact family live, by convention, not
# strictly by ontology membership).

_CRT_STATES_YAML_PATH = _Path("configs/formulas/market_crt_states.yaml")

#: Closed set of legal `kind` values for a threshold_refs entry — see market_crt_states.yaml's
#: own THRESHOLD REFS header comment for what each means.
_VALID_THRESHOLD_REF_KINDS = frozenset({
    "crtconfig_duplicate",
    "crtconfig_duplicate_dead",
    "name_alias_documented",
    "resolver_only",
    "dead_unconsumed",
})


#: Repo root computed from THIS file's own location, not cwd -- same pattern as
#: features/registry/_loader.py's _ONTOLOGY_PATH. (Corrected 2026-08-31, Phase E0 / CR-3: the
#: prior default of `_Path(".")` made the no-arg call only work when invoked from the repo root;
#: this file lives at src/features/registry/__init__.py, 3 parents up from repo root.)
_DEFAULT_REPO_ROOT = _Path(__file__).resolve().parents[3]


def _load_market_crt_states(repo_root: _Path | None = None) -> dict:
    root = repo_root if repo_root is not None else _DEFAULT_REPO_ROOT
    path = root / _CRT_STATES_YAML_PATH
    import io as _io
    import yaml as _yaml
    # market_crt_states.yaml contains non-ASCII bytes that break cp1252 (Windows default) --
    # force utf-8. Hit repeatedly elsewhere this session; documented here too.
    with _io.open(path, encoding="utf-8") as fh:
        return _yaml.safe_load(fh)


def validate_crt_threshold_refs(
    doc: dict | None = None, *, repo_root: _Path | None = None
) -> list[str]:
    """Validate market_crt_states.yaml's `threshold_refs` block against its own closed contract.

    [] == satisfied. Checks:
      1. every `thresholds` key (including `lifecycle.<subkey>`, dot-qualified) has EXACTLY one
         `threshold_refs.refs` entry -- no silent gap, no orphaned ref for a retired key;
      2. every entry's `kind` is one of the 5 declared values;
      3. every entry naming a `ref` under kind crtconfig_duplicate / crtconfig_duplicate_dead
         names a REAL CRTConfig field (cross-checked against
         config_layer.crt_config_completeness.all_crtconfig_fields(), not hand-maintained twice);
      4. no `resolver_only` / `dead_unconsumed` entry carries a non-null `ref` (that would be a
         fabricated reference to nothing);
      5. `crtconfig_duplicate` / `crtconfig_duplicate_dead` / `name_alias_documented` entries
         carry a non-null `ref`.

    Does NOT validate that `consumed` matches actual resolver source code — that is a source-code
    fact re-verified by hand when the resolver changes, not mechanically derivable from this
    validator without parsing crt_state_resolver.py itself (out of scope here).
    """
    d = doc if doc is not None else _load_market_crt_states(repo_root)
    problems: list[str] = []

    thresholds = d.get("thresholds") or {}
    scalar_keys = {k for k in thresholds if k != "lifecycle"}
    lifecycle_keys = {f"lifecycle.{k}" for k in (thresholds.get("lifecycle") or {})}
    expected_keys = scalar_keys | lifecycle_keys

    tr = d.get("threshold_refs")
    if not isinstance(tr, dict):
        return ["threshold_refs: section absent or not a mapping"]
    refs = tr.get("refs")
    if not isinstance(refs, dict) or not refs:
        return ["threshold_refs.refs: must be a non-empty mapping"]

    declared_keys = set(refs)
    missing = expected_keys - declared_keys
    orphaned = declared_keys - expected_keys
    if missing:
        problems.append(f"threshold_refs.refs: missing entries for {sorted(missing)}")
    if orphaned:
        problems.append(
            f"threshold_refs.refs: entries for keys not in thresholds: {sorted(orphaned)} "
            "(a threshold was renamed/retired without updating this section)"
        )

    try:
        from config_layer.crt_config_completeness import all_crtconfig_fields
        crt_fields = all_crtconfig_fields()
    except ImportError:
        crt_fields = None  # src not importable in this context — skip ref-name cross-check

    for name, entry in refs.items():
        where = f"threshold_refs.refs[{name!r}]"
        if not isinstance(entry, dict):
            problems.append(f"{where}: entry must be a mapping")
            continue
        kind = entry.get("kind")
        if kind not in _VALID_THRESHOLD_REF_KINDS:
            problems.append(f"{where}: kind {kind!r} not one of {sorted(_VALID_THRESHOLD_REF_KINDS)}")
            continue
        ref = entry.get("ref")
        if kind in ("resolver_only", "dead_unconsumed"):
            if ref is not None:
                problems.append(f"{where}: kind={kind} must not carry a ref, got {ref!r}")
        else:
            if not ref:
                problems.append(f"{where}: kind={kind} requires a non-null ref")
            elif kind in ("crtconfig_duplicate", "crtconfig_duplicate_dead") and crt_fields is not None:
                if ref not in crt_fields:
                    problems.append(
                        f"{where}: ref {ref!r} is not a real CRTConfig field name "
                        "(fabricated or renamed reference)"
                    )
        if "consumed" not in entry or not isinstance(entry.get("consumed"), bool):
            problems.append(f"{where}: consumed must be present and a bool")

    return problems
