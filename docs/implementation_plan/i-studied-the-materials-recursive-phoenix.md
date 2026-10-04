# Truth-Layer Registry v2.0 → v2.1 — Reachability + Machine-Readable Truth Sources

## Context

`active_models.yaml` v2.0 (commit 0c378a9, 2026-07-02) established the 4-layer truth schema (intent/runtime/evidence/status) per model. A multi-LLM handoff analysis identified the next gap: the registry knows *what* each model is, but the machine-readable truth artifacts (findings, hypotheses, telemetry streams) are not reachable from it or from CLAUDE.md — "dark knowledge." The user approved the **full proposal** with two constraints from doctrine review:

- **Drift/conflicts stay as F-id references** — `docs/current-findings.md` remains the single conflict-truth store; no structured drift blocks, no new drift store (`logs/drift_audit.jsonl` stays the runtime stream).
- Anywhere the proposal would duplicate an authoritative store, the artifact is **GENERATED/seeded, never hand-edited** (§6.2), and the `optimization` metadata is **descriptive only** — no promotion thresholds in any registry (§6.5 Authority Ladder).

User-confirmed decisions:
1. Scope = full proposal (reachability pointers + generated findings export + hypothesis registry + optimization metadata + CLAUDE.md table).
2. Hypothesis registry uses the **seed-script pattern** (committed truth = seed script; `data/hypothesis_registry.jsonl` is its deterministic projection — exact `framework_registry` precedent).
3. New guard test is classified **citation-class reference-resolution** and the Executable-Invariant Scope Policy (conventions.md §9) is amended to record it.

## Grounding facts (verified)

- `data/` and `context/` are gitignored; `data/framework_registry.jsonl`'s committed truth is `scripts/governance/seed_framework_registry.py` (pinned timestamps, byte-stable dump); `tests/test_framework_registry.py` reseeds via autouse fixture.
- Finding-block grammar codified in `tests/test_current_findings.py` (`### F-\d{3}` headers, `- Field:` lines) and `src/governance/framework_registry.py::valid_finding_ids()` — the new parser reuses this grammar, never invents a third.
- Telemetry stream paths are module constants (`src/utils/engine_telemetry.py:35-36`, `src/replay/replay_drift_governor.py:55`, `src/utils/trade_logger.py:82`); `EventType` enum at `src/events/event_fabric.py:56`. JSONL schemas doc home = `docs/reference/schemas.md §9`.
- In-memory `HYPOTHESIS_REGISTRY` (`src/research/registry.py`) populated by importing `research.hypotheses` + `research.controls`; M4 gate = `src/research/qualification.py`.
- `tests/test_crt_state_invariants.py` reads only `crt.runtime.{states,state_list,valid_transitions}` — all changes are additive, so it stays green untouched.
- `active_models.yaml` is NOT the production config — no rehash needed.
- Working tree is dirty with many untracked files — every commit must be surgical (`git add <explicit paths>` only).

## Version semantics (avoid split-brain)

`meta.schema_version: 2.0 → 2.1` (file format, additive). `meta.truth_schema.version` **stays 2.0** — canonical layer set `[intent, runtime, evidence, status]` unchanged; new blocks are sub-blocks inside existing entries. This distinction is written into conventions.md §9.

---

## Step 1 — Findings export (generated derived view)

**Create `src/governance/findings_export.py`** (docstring cites §6.2 DERIVED-VIEW rule):
- `parse_findings(doc=Path("docs/current-findings.md")) -> list[dict]` — reuses `test_current_findings.py` grammar exactly. Pure, deterministic, stdlib+`re`.
- `render(records) -> str` — first line = self-describing meta record (no timestamp → deterministic), then one line per finding in doc order, `json.dumps(..., ensure_ascii=False, sort_keys=True)`.

Line shapes:
```python
# line 0: {"kind":"meta","schema":"findings_export/1","source":"docs/current-findings.md","generated_by":"scripts/governance/export_findings.py"}
# per finding: {"kind":"finding","id":"F-NNN","title","type","status","confidence","validated","revalidate_by",
#               "evidence","evidence_paths":[...],"supersedes","superseded_by","reversal","owner","note","terminal":bool}
```

**Create `scripts/governance/export_findings.py`** — thin argparse CLI; default writes `data/findings.jsonl` (gitignored-generated, per D1: committing it would put a second copy of findings truth in every diff); `--check` prints without writing.

**Create `tests/test_findings_export.py`** (mirrors `test_context_compiler.py`): (1) render twice → byte-identical; (2) every `### F-NNN` in doc appears exactly once, counts match; (3) meta line present; (4) non-terminal records have non-empty evidence; (5) autouse fixture regenerates `data/findings.jsonl` if absent + asserts on-disk == fresh render (hand-edit guard).

**Doc sync:** `schemas.md` new **§9.5 `data/findings.jsonl` (GENERATED)** — key set + "never hand-edit; regenerate via the script; truth stays `docs/current-findings.md`".

## Step 2 — Hypothesis registry (seed-script pattern)

**Create `src/governance/hypothesis_registry.py`** — mirrors `FrameworkRegistry` (load/validate_record/append/dump via `utils.jsonl_writer`); reuse `framework_registry.valid_finding_ids` (do not re-implement). Record shape:

```python
{"id":"H-NNN", "statement":str, "family":str|None,
 "status":"open"|"validated"|"falsified"|"frozen"|"superseded",
 "authority":"research",                 # PINNED literal — validator rejects anything else (§6.5)
 "findings":["F-019",...],               # must resolve via valid_finding_ids()
 "models":["crt",...],                   # top-level keys of active_models.yaml (minus meta/philosophy)
 "code_hypotheses":["expansion_breakout",...],  # names in research HYPOTHESIS_REGISTRY (may be [])
 "programs":[...], "evidence":[{path,line,symbol,type}],
 "created":ts, "last_validated":ts, "notes":str}
```
No `promotion_requirements` / `min_delta_g001` style keys exist; validator rejects unknown keys. Promotion standard stated once in docstring + §9.6 doc: "`validated` is a research verdict; the only promotion path remains M4 `QualificationGate` → `ConfigValidator`/`PromotionManager`; this registry defines no thresholds."

**Create `scripts/governance/seed_hypothesis_registry.py`** (clone seed_framework_registry shape: pinned `_TS`, `_rec()`, dump → `data/hypothesis_registry.jsonl`). Seed ~16 records harvested from the falsification programs (statements written with the finding text open at implementation):

| H-id | gist | status | findings |
|---|---|---|---|
| H-001 | CRT structural completion has standalone directional edge | falsified | F-019, F-021, F-026 |
| H-002 | Candle-conditional directional pockets exist | falsified | F-020 |
| H-003 | Exit/SL-TP structure is an expectancy lever | falsified | F-025 |
| H-004 | HTF (H1/H4) rescues the edge | falsified | F-027 |
| H-005 | P&F interpreter carries standalone edge | frozen | F-028 |
| H-006 | Vol-regime LEVEL conditioning consumable | falsified | F-030 |
| H-007 | Markov P^H forecast adds beyond vol level | falsified | F-043 |
| H-008 | MTF compression→expansion directionally consumable | falsified | F-040 |
| H-009 | Cross-sectional dispersion monetizable | falsified | F-032 |
| H-010/011 | Carry/basis signal · carry harvest | falsified | F-033 / F-034 |
| H-012 | Entry-info null generalizes to FX | validated | F-035 |
| H-013 | Weekly liquidity-sweep ontology clears M4 | falsified | F-042 |
| H-014 | Feature-pipeline lookahead is fatal contamination | falsified (benign) | F-029 |
| H-015 | ZoneGate neighborhood quality is pivotal | falsified | F-036, F-041 |
| H-016 | Program 9: M5 multi-TF OCO straddle | open | — (pre-reg only) |

`code_hypotheses` filled where twins exist (`expansion_breakout`, `mean_reversion`, `compression_breakout`→H-008, `weekly_sweep_reversal`→H-013, `spine_hypothesis`→H-001).

**Create `scripts/governance/query_hypotheses.py`** — sibling of `query_registry.py`: `--summary`, `--finding`, `--model`, `--status`, `--validate` (exit 1 on error).

**Create `tests/test_hypothesis_registry.py`** — mirror the 8 framework contract tests: loads-valid · findings-exist · models-exist (keys of active_models.yaml excl. meta/philosophy) · code-hypotheses ⊆ HYPOTHESIS_REGISTRY (after importing research.hypotheses+controls) · programs/evidence paths resolve · unique-ids · authority-pinned + status-enum · append-only-immutable. Autouse reseed fixture.

**Doc sync:** `schemas.md` **§9.6** (key set + authority note + regenerate command); one cross-link line in `docs/reference/framework_registry_schema.md`.

## Step 3 — `schemas.md §9.4`: event-fabric stream table (prereq for Step 4 pointers)

Add **§9.4 "Event-fabric streams (uniform envelope)"**: the `make_event_envelope` key set once + thin table `EventType → stream file → emitter module` covering at least: ENGINE_TELEMETRY, DECISION_LINEAGE, DRIFT_AUDIT, TRADE_LIFECYCLE, STATE_TRANSITION, LLM_TURN (paths/emitters per grounding facts above).

Also scope the §9 preamble rule: "`timestamp`+`kind` applies to **audit/event streams**; registry-class JSONL (§9.5–9.6, framework_registry) uses `created`/`last_validated`" — auto-fixable DOC_DRIFT (framework_registry.jsonl already deviates undocumented).

## Step 4 — `active_models.yaml` v2.1 (additive) + guard test

**Modify `active_models.yaml`** — additions only, no renames/removals:

1. `meta.schema_version: 2.1`; extend `meta.migration` (`breaking_changes: false`); add `meta.machine_readable_sources` block mapping each of {findings_export, hypothesis_registry, framework_registry} → `{path, generator, guard}`.
2. Per model (crt, gaussian, bitnet, zone_gate, rr_model, strategies, engine_runner) a `reachability` block:
```yaml
reachability:
  config_sections: [crt_engine]      # top-level keys in configs/production/<ACTIVE_VERSION>.json
  telemetry:
    - {event_type: STATE_TRANSITION, stream: <path>, emitter: src/config_layer/crt_engine_v2.py}
  tests: [tests/test_crt_state_invariants.py]
  topics: [docs/topics/model-intent-and-feature-ownership.md]
  framework_ids: [IMPL-00X]          # optional link into framework_registry
```
Every path verified by grep before writing.
3. Per model `evidence.conflicts:` — plain F-id list (zone_gate: `[F-041]`; others `[]`/omitted). **No structured drift blocks** (fixed decision).
4. Per model `evidence.hypotheses:` — H-id lists (crt: `[H-001, H-002, H-004, H-012, H-013]`, zone_gate: `[H-015]`, gaussian: `[H-014]`, …).
5. Per model `optimization` block — **descriptive only**:
```yaml
optimization:
  authority: "none — descriptive; see CLAUDE.md §6.5 (tunability ≠ authority; promotion only via M4 QualificationGate + PromotionManager)"
  tunable_class: BEHAVIORAL
  config_sections: [crt_engine]      # caveat: CRTConfig params split-brain, §6.5
  frozen_structural: "CRTState members, VALID_TRANSITIONS, feature dims — code-frozen"
  census: docs/research-readiness/behavior-census-report.md
  promotion_standard:
    research:   src/research/qualification.py
    production: src/governance/promotion_manager.py
```
No numeric thresholds anywhere in the block; no per-knob inventories (census's job; `crt.runtime.thresholds` stays as-is).

**Create `tests/test_active_models_registry.py`** — docstring classifies it as *citation-class reference-resolution* (sibling of `test_doc_citations.py`), NOT a semantic YAML↔code invariant. Reseed fixture for both `data/*.jsonl`. Checks:
1. YAML parses; `meta.schema_version == 2.1`; canonical_layers unchanged.
2. Every F-id in `evidence.findings`/`evidence.conflicts`/`philosophy.authority.findings` ∈ `valid_finding_ids()`.
3. Every H-id resolves in the reseeded hypothesis registry.
4. Every reachability path + `machine_readable_sources.{path,generator,guard}` resolves from repo root.
5. Every `telemetry.event_type` ∈ `EventType`; stream basename appears in emitter module source text.
6. Every `config_sections` entry is a top-level key of the JSON named by `configs/production/ACTIVE_VERSION` (branch-scoped §4.0).
7. `optimization.authority` startswith "none" + mentions §6.5; **negative guard**: no key matching `promotion_requirements|min_delta|threshold` inside `optimization` (authority-creep regression).
8. `framework_ids` resolve in the reseeded framework registry.

**Doc sync (§6.3/§6.4):**
- `conventions.md §9`: (a) v2.1 note under Truth-Layer Standard (sub-blocks; truth_schema.version stays 2.0; meta.schema_version tracks file format); (b) Executable-Invariant Scope Policy amendment: add the new test as "reference-resolution (citation-class), no semantic pinning", drift evidence = F-041. **[User approved this amendment.]**
- `docs/topics/model-intent-and-feature-ownership.md`: pointer to per-model optimization/reachability blocks + dated Discussion entry + bump `Updated:`.
- No finding changes (nothing validated/overturned) — state explicitly in SESSION LOG.

## Step 5 — CLAUDE.md thin reachability table + SESSION LOG

Under the §2 companion table add (~9 lines):

```markdown
**Machine-readable truth sources** (artifacts are GENERATED/seeded — edit the source/seed, never the artifact):
| Artifact | Source of truth | Regenerate | Guard |
|---|---|---|---|
| data/findings.jsonl | docs/current-findings.md | scripts/governance/export_findings.py | tests/test_findings_export.py |
| data/hypothesis_registry.jsonl | scripts/governance/seed_hypothesis_registry.py | run the seed | tests/test_hypothesis_registry.py |
| data/framework_registry.jsonl | scripts/governance/seed_framework_registry.py | run the seed | tests/test_framework_registry.py |
| active_models.yaml (v2.1) | hand-maintained, source-verified | — | tests/test_active_models_registry.py + test_crt_state_invariants.py |
| context/*.md | canonical docs (Compile) | scripts/context/build_context.py | tests/test_context_compiler.py |
```

In passing (unambiguous DOC_DRIFT, auto-fix): the `active_models.yaml` row in the §2 table has a malformed leading `| |` and says "10 states" (stale vs corrected 9).

Then append the mandated `📝 SESSION LOG ENTRY` to `assistant_project.md` (§6), including the Executable-Invariant amendment justification.

## What is explicitly NOT built (doctrine)

- No new telemetry emitters (`crt_candidates.jsonl` etc.) — 15 streams exist; the gap was discoverability.
- No hand-maintained `evidence/findings.jsonl` second truth store — generated export only.
- No drift-registry JSONL / structured drift blocks — findings + `logs/drift_audit.jsonl` already own this.
- No auto-tune promotion thresholds in any registry — §6.5 Authority Ladder; the negative-guard test enforces it.

## Files summary

**Create:** `src/governance/findings_export.py`, `src/governance/hypothesis_registry.py`, `scripts/governance/export_findings.py`, `scripts/governance/seed_hypothesis_registry.py`, `scripts/governance/query_hypotheses.py`, `tests/test_findings_export.py`, `tests/test_hypothesis_registry.py`, `tests/test_active_models_registry.py`.
**Modify:** `active_models.yaml`, `docs/reference/schemas.md` (§9 preamble + §9.4–9.6), `docs/reference/conventions.md` (§9), `docs/reference/framework_registry_schema.md` (1 line), `docs/topics/model-intent-and-feature-ownership.md`, `CLAUDE.md` (§2 table), `assistant_project.md` (SESSION LOG).
**Reuse:** `FrameworkRegistry` pattern + `valid_finding_ids` (`src/governance/framework_registry.py`), `utils/jsonl_writer.py`, `test_current_findings.py` grammar, seed/reseed-fixture pattern (`scripts/governance/seed_framework_registry.py`, `tests/test_framework_registry.py`).

## Verification

```bash
# baseline
python -m pytest tests/test_crt_state_invariants.py tests/test_current_findings.py tests/test_framework_registry.py tests/test_context_compiler.py -q
# step 1
python scripts/governance/export_findings.py
python -m pytest tests/test_findings_export.py tests/test_current_findings.py -q
# step 2
python scripts/governance/seed_hypothesis_registry.py
python scripts/governance/query_hypotheses.py --validate
python -m pytest tests/test_hypothesis_registry.py tests/research/test_registry.py -q
# step 3
python -m pytest tests/test_doc_citations.py -q
# step 4
python -c "import yaml; yaml.safe_load(open('active_models.yaml', encoding='utf-8'))"
python -m pytest tests/test_active_models_registry.py tests/test_crt_state_invariants.py tests/test_topic_docs.py -q
# step 5 + regression sweep
python scripts/governance/query_registry.py --validate
python -m pytest tests/test_current_findings.py tests/test_doc_citations.py tests/test_topic_docs.py tests/test_context_compiler.py tests/test_framework_registry.py tests/test_findings_export.py tests/test_hypothesis_registry.py tests/test_active_models_registry.py tests/test_crt_state_invariants.py -q
```

Each step is independently green-able; Step 4's H-id checks depend on Step 2, its stream-table pointer on Step 3 — hence the ordering. Commits: surgical `git add <explicit paths>` only (dirty tree).
