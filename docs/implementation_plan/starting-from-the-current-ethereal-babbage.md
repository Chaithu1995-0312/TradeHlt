# Research Provenance DAG — backward trace from current architecture to earliest hypotheses

## Context

The repository asserts a provenance topology it has never measured. `docs/knowledge-map.md`
states that every SESSION LOG entry "cites the plan it executed, the analysis it produced, and
the finding it validated," and CLAUDE.md §6.1/§6.2 make zero-intelligence-loss and
zero-silent-truth-divergence the governing doctrine. Nothing in the repo tests whether an
architectural decision can actually be traced back to an originating hypothesis, finding,
evidence artifact, and measurement basis.

Reconnaissance already done in this session says the answer is not flattering, and the numbers
are the deliverable:

| Measured now (read-only) | Value |
|---|---|
| SESSION LOG entries (167 hot + 888 archived, 2026-04-10 → 2026-08-26) | 1,055 |
| Entries citing **zero** typed IDs (F/H/CH/SEM/FM/MC/MP/RF) | **51.0%** |
| Entries citing an `H-*` hypothesis | **1.5%** |
| Findings with `Contract: UNKNOWN` (measurement basis) | **82 / 93 (88.2%)** |
| Measurement runs proven executed (`measurement_result_log.jsonl` `sealed_pass_bound`) | **0** |
| Hypotheses in the registry | 20 — **18 back-seeded in one act on 2026-07-03** |
| Findings bound to any hypothesis | 19 / 93 |
| Finding `evidence_paths` refs not git-tracked (dangling) | 39 / 374 (10.4%) |
| `CH-*` impact manifests / matching completion records | 87 / 41 |

The outcome is a typed, machine-readable DAG plus edge-class percentages. **Gaps are the
result, not a defect to patch** — the instruction is explicit: do not fill gaps. Where a link
does not exist, the edge is `UNKNOWN` and stays `UNKNOWN`.

Authority: research/governance only. No production code, no config, no `ACTIVE_VERSION`, no
finding registration, no G001 (§6.5).

---

## Node model

Full corpus. Decision spine = every SESSION LOG entry; formal registers are typed cross-index
nodes.

| Node type | Source | Count |
|---|---|---|
| `DECISION_SESSION` | `assistant_project.md` + `docs/analysis/session-log-archive/session-log-*.md` | ~1,055 |
| `DECISION_CH` | `docs/governance/build_manifests/*.impact.json` | 87 |
| `DECISION_PROMOTION` | `configs/promotion_log.jsonl` | 15 |
| `DECISION_CLOSURE` | `docs/governance/closure_authority_index.json` | 13 |
| `FINDING` | `data/findings.jsonl` (GENERATED from `docs/current-findings.md`) | 93 |
| `HYPOTHESIS` | `data/hypothesis_registry.jsonl` | 20 |
| `EVIDENCE` | finding `evidence_paths[]`, manifest `affected_files[]`, `docs/analysis/*` | — |
| `MEASUREMENT_BASIS` | `Contract:` field, `configs/research/measurement_contracts/**`, `measurement_result_log.jsonl` | 11 named |

Marker parsing note: the hot log carries **77** `📝`-prefixed and **89** bare `SESSION LOG ENTRY`
markers. `scripts/maintenance/rotate_session_log.py`'s `_MARKER_RE` only recognises `📝`/`??`,
so the extractor must use a tolerant marker regex and **report** the discrepancy (surface, do not
fix — separate authorized turn).

## Edge model

Four slots per decision node, exactly as asked: `originating_hypothesis`,
`originating_finding`, `originating_evidence`, `originating_measurement_basis`.

Edge record: `{src, dst, slot, class, rule_id, witness}` — `witness` is the literal field name or
matched substring, so every classification is auditable back to a byte in a file.

### Classifier (ordered, first match wins, each rule emits its `rule_id`)

**EXPLICIT**
- `E1_STRUCTURED_FIELD` — dst id appears in a dedicated structured field of the src artifact
  (`Contract:`, `findings[]`, `evidence_paths[]`, `ontology_nodes_added`, `authority_granted`,
  `required_checks_ack`) **and** resolves to an existing node.
- `E2_INLINE_CITATION` — dst id appears verbatim in src free text (session-log entry body,
  manifest `objective`) **and** resolves.

**INFERRED** — the link exists only through a third artifact; neither endpoint cites the other.
- `I1_HYPOTHESIS_BACKSEED` — via `hypothesis_registry.findings[]`. The registry cites the
  finding; no finding cites an `H-*`. 18 of 20 hypotheses were authored on a single day
  (2026-07-03) about work done weeks earlier ⇒ post-hoc attribution, never explicit-at-origin.
- `I2_FAMILY_JUDGEMENT` — via `research_family_registry.json` cell `claims[]`. Self-declared:
  `verified_against_filesystem: false`, and the finding→family/layer assignment is
  "AUTHORED JUDGEMENT, not machine-derived." All cells `UNVERIFIED_HISTORICAL`.
- `I3_DATE_COLOCATION` — decision and target share a SESSION LOG date / `docs/timeline.md` row
  but neither cites the other.
- `I4_FILE_OVERLAP` — manifest `affected_files[]` ∩ finding `evidence_paths[]` ≠ ∅.

**UNKNOWN**
- `U1_DECLARED_UNKNOWN` — the slot field literally reads `UNKNOWN` (the 82 findings' `Contract:`).
- `U2_NO_CANDIDATE` — no E- or I-rule produced any candidate.
- `U3_DANGLING_CITATION` — an id/path **is** cited but does not resolve (the 39 untracked
  evidence paths, any `F-`/`CH-` id with no node). Cited ≠ traceable; this is UNKNOWN, not EXPLICIT.
- `U4_DECLARED_NOT_EXECUTED` — a measurement basis is named (`MC-*`/`MP-*`/sha256) but
  `measurement_result_log.jsonl` proves no run. Currently **every** named basis, since
  `sealed_pass_bound: 0`. Reported as its own bucket (`EXPLICIT_DECLARED / EXECUTION_UNKNOWN`)
  so neither side is overstated.

Precedence guard: `U3` and `U4` are evaluated **before** `E1`/`E2`, so a citation that cannot be
resolved never scores as explicit.

## Quantification

Denominator = 4 × |decision nodes| (one slot per decision per question asked).

Reported cuts:
1. **Overall** — % EXPLICIT / INFERRED / UNKNOWN.
2. **Per slot** — hypothesis / finding / evidence / measurement basis separately (they will
   differ by an order of magnitude; a single blended number would hide that).
3. **Per decision type** — session vs CH vs promotion vs closure.
4. **Per era** — the five eras in `docs/timeline.md`, to show whether provenance discipline
   improved after Gate 6 (2026-07-08) introduced `CH-*` manifests.
5. **Backward reachability** — fraction of decisions with any path terminating at an `H-*`, and
   the depth distribution of those paths.
6. **Terminus census** — the earliest origin nodes reached. The `H-*` registry only begins
   2026-07-03; April–June origins (`ENHANCEMENT_IMPLEMENTATION_PLAN` phases, CRT Phases 0–6,
   Trd-M0..M6) exist only as archive prose and are emitted as `PRE_REGISTRY_ORIGIN` nodes with
   whatever edge class the rules actually yield. Not backfilled.

## Files

| File | Action |
|---|---|
| `scripts/analysis/research_dag_provenance.py` | **new** — read-only extractor/classifier/reporter |
| `docs/governance/research_dag_provenance-2026-08-26.json` | **new** — dated immutable artifact (nodes + edges + rollups) |
| `docs/governance/research_dag_provenance.LATEST.json` | **new** — pointer, mirrors `feature_38_lineage_census.LATEST.json` |
| `docs/analysis/research-dag-provenance-2026-08-26.md` | **new** — write-up: Mermaid layer graph, percentage tables, per-slot ledger, explicit gap register |
| `tests/test_research_dag_provenance.py` | **new** — test floor |
| `docs/governance/build_manifests/CH-research-dag-provenance.impact.json` | **new** — BUILD_IMPACT_MANIFEST |
| `docs/analysis/readme.md` | edit — index the new study |
| `assistant_project.md` | append — SESSION LOG entry (§6) |

Reuse, do not reinvent:
- Artifact + `LATEST` pointer + dated-immutable convention: copy
  [`scripts/analysis/feature_38_lineage_census.py`](scripts/analysis/feature_38_lineage_census.py)
  (`OUT_JSON` / `OUT_LATEST_PTR` / `write_text(..., encoding="utf-8")`).
- Entry parsing: reuse the marker/date/`_HR_RE` splitting logic in
  [`scripts/maintenance/rotate_session_log.py`](scripts/maintenance/rotate_session_log.py)
  (`parse_log`, `_DATE_RE`) rather than writing a second parser — widen the marker regex locally
  in the new script, do not edit the rotator.
- Findings are read from the GENERATED `data/findings.jsonl` (produced by
  `scripts/governance/export_findings.py`), never by re-parsing `docs/current-findings.md`.
- Windows console: `src/utils/console_safe.safe_print` for any non-ASCII stdout.

## Governance steps (non-optional, in order)

1. Write `CH-research-dag-provenance.impact.json`; classes `DOCUMENTATION_ONLY` +
   `SCRIPT_LIFECYCLE_CHANGE`; `production_behavior_changed: "NO"`; `unknowns: []`.
   Run `python scripts/governance/construction_protocol.py validate-impact <manifest>`.
2. Implement + run the extractor.
3. SITS registration for the new script (CLAUDE.md §3.1b — unregistered paths fail GREEN_FLOOR):
   `script_census.py --write-stubs` → `seed_script_registry.py` → `generate_script_matrix.py`.
4. `construction_protocol.py validate-completion <manifest>`.
5. SESSION LOG entry with the `Belief Update / ROI / Goal` field (§7.4).

## Surfaced, NOT fixed (§6.2 rule 3 — needs your gate)

These are drift the audit will formalize. I will present each as a `TruthConflict` and take no
edit without approval:

- `docs/knowledge-map.md` claims every SESSION LOG entry cites its plan/analysis/finding.
  Measured: 51.0% cite no typed ID at all. Candidate `DOC_DRIFT`.
- `assistant_project.md` header claims "every session decision since April 2026"; the hot file's
  earliest entry is 2026-06-15 (the rest is in the archive). Candidate `DOC_DRIFT` (scope
  sentence).
- `rotate_session_log.py:_MARKER_RE` does not recognise the 89 bare `SESSION LOG ENTRY` markers
  in the hot file. Candidate `TEST / CONTRACT GAP` — a maintenance-script defect, out of scope
  here.

No finding is registered by this plan (your "Analysis package" choice). If the result warrants an
`F-id`, I will surface the proposed row and wait.

## Verification

1. **Determinism** — run the extractor twice; the two dated JSON payloads must be byte-identical
   (sorted keys, single `generated_at`, no wall-clock inside the payload). Same gate the repo
   already applies to research artifacts.
2. **Test floor** — `pytest tests/test_research_dag_provenance.py`:
   - schema of every node/edge record;
   - byte-identical double run;
   - **classifier reachability**: fixtures that force each of `E1/E2/I1/I2/I3/I4/U1/U2/U3/U4` to
     fire at least once, so no rule is dead code (E-001: a test that cannot fail is not
     enforcement, and a classifier that can only return one class is not a classifier);
   - **conservation**: EXPLICIT + INFERRED + UNKNOWN == 4 × |decisions|, no double-count;
   - **precedence**: a dangling citation fixture classifies `U3`, never `E2`.
3. **Cross-check against hand counts** — the extractor's totals must reproduce the reconnaissance
   numbers in the Context table above (82 `Contract: UNKNOWN`, 39 dangling evidence paths, 20
   hypotheses, 0 executed measurement runs). A mismatch means the parser is wrong, not the repo.
4. **Governance floor** — `python scripts/governance/construction_protocol.py check` green.
5. **Spot audit** — manually verify 10 randomly sampled edges (one per `rule_id`) against the
   cited file:line. Any edge whose `witness` does not appear at the named location is a parser bug.
