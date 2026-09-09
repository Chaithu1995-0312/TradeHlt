# CH-jsonl-claim-surface — implement the JSONL Claim Surface

## Context

`docs/governance/JSONL_CLAIM_SURFACE.md` (961 lines, authored by Grok, Approved 2026-08-25) specifies a
test-guarded refusal surface so an LLM cannot close a repository claim against a JSONL stream that
cannot support it — "a line exists, therefore the trade was profitable" (F-022), "both lines parse,
therefore one object" (F-069), "the contract is schema-valid, therefore it ran" (F-083).

Today that table lives only in a session log and `.grok/PENDING.md` P-FLOW-15. It has no teeth:
`SemanticGrounder.ground_evidence("F-048")` grounds that a *finding exists*; nothing refuses
"opportunities.jsonl says this trade won." The spec closes that by extending the existing CT-008
grounder with one claim kind (`JSONL`) and one status (`REFUSED`) backed by a committed catalog of
named claim classes (`CC-*`), plus a committed measurement result log that makes F-083's
declared-but-unexecuted gap mechanical.

The doc carries a user lock ("design only — do not implement") and is **untracked in git**.
Approving this plan lifts that lock. Scope is PR-1..4; PR-5 stays skipped per the spec.

### Verification pass (done this turn — the spec is a hypothesis until reproduced, §6.8)

Three read-only sweeps checked every `file:line` claim the spec makes. The design is sound and the
join points are real. **Eight claims are wrong**; two would fail the build if implemented verbatim.

| # | Spec claim | Truth | Impact |
|---|---|---|---|
| 1 | Result line field `trust_mt01`; contract key `trust_status.mt01` | Real key is **`trust_status.mt01_matrix_coverage`**; `trust_status` is `additionalProperties:false` | **Blocking** — rename in the result-line schema and every read |
| 2 | `configs/stack_epoch_log.jsonl` is a committed_audit stream | **File does not exist anywhere in the repo** | **Blocking** — drop the row, or the catalog cites a phantom |
| 3 | `GOVERNED_PREFIXES` = only `src/research/`, `src/features/` | 8 entries; **`docs/governance/` is already one** (`:38`) | Conclusion survives (`src/governance/` is still not a prefix); the "prefix tax" reasoning for keeping the result log out of `docs/governance/` is *correct* |
| 4 | `tests/test_measurement_contract.py` is MP-* profile subordination only | It has 4 MC-instance tests incl. a schema-validate loop over `instances/` | Load-bearing half holds: **nothing** compares an instance to the artifacts its run produced |
| 5 | An AST-isolation test pins who may import `identity.*` | `tests/test_identity_store.py` pins the **inverse** (what `identity.*` may import) | The import-set pin must be **written new**, not reused |
| 6 | Semantic OS contract shape validated near the grounder | Validator is `src/governance/semantic_os.py`; guard is `tests/test_semantic_os.py`; CT-008 has **18 required keys** | PR-2 must add `tests/test_semantic_os.py` to its check set |
| 7 | `.gitignore` lines 2–5 ignore data/logs/results | `data`=2, `logs`=3, `results`=5; line 4 is `*results*.zip` | Cosmetic — cite by rule, not line number |
| 8 | `tests/test_semantic_grounding.py` may pin `to_dict()` == 11 keys | **No test anywhere pins Grounding arity or key set** | The spec's warning is moot; additive fields are safe |

Confirmed as stated (the load-bearing ones): `CLAIM_KINDS` is exactly 4 and pinned at
`tests/test_semantic_grounding.py:37` · `STATUSES` is 4 · `Grounding` is 11 fields with `to_dict()`
at `:159-172` · `ground()` at `:304-328` falls through to `ground_evidence` · `truth_mode.py:123-126`
clobbers `status` with `"ok"` and the exception path alone emits `grounding_status` ·
`query_semantic_os.py:84` coalesces `args.token or args.relation` and `:91` exits 2 unless GROUNDED ·
`plan_compiler.py:145` routes `semantic_ground` → `truth.ground_claim` · GREEN_FLOOR at `:69-94`
excludes the three candidate tests · `change_contracts.json` has exactly 15 classes ·
`test_construction_protocol.py:70` asserts `== 15` and `:78-81` requires every `tests/` check on disk ·
CI runs `check_governance_invariants.py --all` · `L5_BASIS` is 3 keys at `tokens.py:48` and all six
frozensets exist · `_check_l5` at `check.py:246-264` needs an L4 parent · all 9 `instances/` are
`mt00: UNRUN` and `MC-CPR-L0` sits outside with `PARTIAL`.

### Two decisions this plan makes (not in the spec)

**A. The F-083 scan universe is `git ls-files`, not the filesystem.** Three of the nine
`instances/MC-*.json` are untracked (`MC-ASYM`, `MC-MRPRIOR`, all of `drafts/`) — and `MC-MRPRIOR`
backs published finding **F-094**. A floor whose universe is "whatever is on disk" gives a different
verdict per clone, which is the F-071 class the surface exists to prevent. Precedent already in the
repo: `tests/test_current_findings.py:62` reads `git ls-files` for exactly this reason. All nine are
UNRUN so the floor passes either way today; this only fixes determinism.

**B. `_norm_path` path-escape stays unfixed, and is filed as a follow-on.** `semantic_grounding.py`
has no containment helper today: `_norm_path` (`:124-128`) strips `./` and flips slashes but rejects
neither `..` nor `C:/`, and `ground_implementation` then does `read_text` + `ast.parse` on
`_ROOT / key`. The new `_contained_repo_path` closes this for `kind=JSONL` only. Hardening the
existing IMPLEMENTATION path is a behaviour change to a different claim kind — §6.8 no-silent-
remediation. Filed as `CH-grounder-path-containment`, not done here.

---

## PR-1 — Catalog PRIMARY + floors (no grounder change)

Encode CAN/CANNOT as data. The grounder is untouched, so an incomplete merge leaves CT-008 exactly
as it is today.

**New files**
- `docs/governance/jsonl_claim_catalog.yaml` — PRIMARY, hand-authored. `schema_version:
  jsonl_claim_catalog/1`, `authority: advisory` pinned. Three sections: `streams` (`STR-*`),
  `claim_classes` (`CC-*`, the 12 CANNOT + 10 CAN rows from spec §5), `forbidden_joins`.
  **Drop the `configs/stack_epoch_log.jsonl` stream row** (correction 2). Header cites identity
  contract §12.3 by section, not by `.gitignore` line number (correction 7).
- `src/governance/jsonl_claim_catalog.py` — `load_catalog()`, `stream_for_path()`,
  `claim_class(cc_id)`, `join_cc(source, target)`, `admissibility(...) -> ADMITTED | REFUSED |
  NOT_ADMITTED | UNKNOWN_CLASS | UNKNOWN_STREAM`, `render() -> str`.
- `tests/test_jsonl_claim_catalog.py`

**Reuse, don't reinvent:** `src/governance/findings_export.py` is the exact pattern — copy `render()`
(static meta line, no timestamps, `json.dumps(..., ensure_ascii=False, sort_keys=True)`, trailing
newline) and copy the `_ensure_exported` autouse fixture from `tests/test_findings_export.py:29-34`
so the gitignored `data/jsonl_claim_catalog.jsonl` regenerates on a fresh clone and a *stale* one
still fails the render-equality assertion.

**Edits**
- `scripts/maintenance/check_governance_invariants.py`: GREEN_FLOOR += `tests/test_jsonl_claim_catalog.py`,
  `tests/test_findings_export.py`, `tests/test_hypothesis_registry.py` — **both candidates measured
  green this turn (14 passed)**, so the E-001F "only if green" gate is satisfied; re-measure in the
  PR checkout before adding. GOVERNED_FILES += `src/governance/jsonl_claim_catalog.py`
  (the YAML is already covered by the `docs/governance/` prefix; list it anyway to document intent).
- `docs/governance/change_contracts.json`: new `JSONL_CLAIM_SURFACE_CHANGE` with the six required
  keys (`description`, `authorities_to_inspect`, `artifacts_to_update`, `required_checks`,
  `rollback_boundary`, `completion_criteria`). `required_checks` lists **only PR-1 files**:
  `tests/test_jsonl_claim_catalog.py`, `tests/test_construction_protocol.py`.
- `tests/test_construction_protocol.py:70`: `== 15` → `== 16`.
- `tests/test_governance_invariant_check.py`: pin the new GOVERNED_FILES entry and the new
  GREEN_FLOOR members. (Membership is not otherwise pinned — only disk existence is — so this is
  additive discipline, not a required fix.)
- `docs/governance/build_manifests/CH-jsonl-claim-surface.impact.json` — mandatory keys are
  `change_id, objective, change_classes, affected_files, required_checks_ack, unknowns,
  rollback_boundary`; `unknowns: []` or the validator STOPs. Model it on
  `CH-identity-store-phase4.impact.json`.
- `CLAUDE.md` machine-readable sources table: catalog YAML row (PRIMARY → GENERATED).
- `docs/reference/schemas.md` §9.15: catalog line schema.
- `docs/topics/event-fabric.md`: one-line Discussion entry (§6.4 — surgical, bump `Updated:`).
- **`git add docs/governance/JSONL_CLAIM_SURFACE.md`** — the spec itself is untracked today.

**Do not** stub `tests/test_jsonl_claim_grounding.py` so PR-1 can pre-list it —
`test_construction_protocol.py:78-81` requires every `tests/` check to exist, and an empty stub is
enforcement theatre.

**Planted defects the catalog test must catch:** a stream listing `CC-F022-CONTAMINATED` in
`allowed_cc` (CANNOT ids must never appear there; `forbidden_cc` ⊆ CANNOT ids); a glob in a
`generated_registry`/`committed_audit` `path`; a hand-edited GENERATED JSONL.

---

## PR-2 — `JSONL` kind + `REFUSED` status on SemanticGrounder

**Depends on PR-1.**

`src/governance/semantic_grounding.py`:
- `CLAIM_KINDS` += `"JSONL"` (`:53`); `STATUSES` += `REFUSED` (`:60`).
- `Grounding` += `refusal_class: Optional[str] = None`, `catalog_stream_status: Optional[str] = None`;
  both emitted by `to_dict()` (`:159-172`) as `None` on the four existing kinds. Nothing pins arity,
  so this is safe. Note `to_dict()` returns `payload` **by reference** (`:169`) — return fresh dicts
  from `ground_jsonl`, never a cached catalog row.
- Insert `if kind == "JSONL": return self.ground_jsonl(...)` **before** the `:328` fall-through.
- `ground_jsonl(token, *, relation="", source="", target="")` implementing spec §6's 7-step
  algorithm exactly: relation required → closed vocabulary → **join first** (order-insensitive; hits
  REFUSE even when `relation` is a CAN; token may be empty) → polarity CANNOT always REFUSED →
  per-class token grammar → `allowed_cc` miss is UNANSWERABLE → class-specific extra checks.
- `_contained_repo_path()` per spec §6: reject absolute / NUL / `..` escape → `UNKNOWN`, never
  `open()`. Reads use allowlisted catalog paths, not the raw token.

`scripts/governance/query_semantic_os.py`: when `kind == "JSONL"`, pass `args.token` **as-is** —
`:84`'s `args.token or args.relation` would coalesce an omitted `--token` into the CC id and break
join-only calls. Leave other kinds unchanged. `--source` (`:49`) and `--dest`/`--target` (`:50`/`:44`,
both reach `target=` via the `:87` fallback) already exist; **no new flags**. Exit stays 0 iff GROUNDED.

`src/agent/modes/truth_mode.py`: copy `hit.status` into `out["grounding_status"]` **before**
`out["status"] = "ok"` at `:124`; same `token`-as-is rule at `:117`; `kind.desc` (`:87`) += `JSONL`.
`passed` stays `hit.status == "GROUNDED"` — do not change the envelope contract.

**Tests** — `tests/test_jsonl_claim_grounding.py` is a **per-CC expected-status fixture**
(`cc_id × token × source × target × expected`), never `for cc in CAN: assert GROUNDED`. Required
pins: every CANNOT row → REFUSED · missing `relation` → UNANSWERABLE · invented `CC-*` →
UNANSWERABLE · `CC-FINDING-EXPORT` + `producer:engine`×`producer:resolver` → REFUSED
`CC-L3-FORBIDDEN-JOIN` · `**/opportunities.jsonl` × `CC-FINDING-EXPORT` → UNANSWERABLE ·
`C:\Windows\...` and `../` → UNKNOWN with no file access · agent dict carries `grounding_status`
before the envelope clobber · CLI join-only with no `--token` reaches `ground_jsonl` as `""`.

PR-2 GROUNDs only clone-visible CANs. **`CC-FINDING-EXPORT` grounds from PRIMARY
`docs/current-findings.md`** — that is what `ground_evidence` itself gates on
(`framework_registry.valid_finding_ids()` regex-scans the markdown; `data/findings.jsonl` is
enrichment only and its absence yields a caveat, not a failure). Do not require the gitignored file.
`CC-MC-*` are expected UNANSWERABLE here; their grammar ships in PR-3.

`tests/test_semantic_grounding.py:37` must move from `== {four}` to include `JSONL`; keep the
existing positives byte-identical (CN-001, CT-008, F-048, F-007, FM-041, `DecisionAct`,
`ACTIVE_VERSION`, EngineRunner, the two relationships).

CT-008 refined **in place** in `docs/governance/semantic_os/contracts.yaml:288-328` — id unchanged,
all **18** required keys preserved, `enforced_by_tests` += `tests/test_jsonl_claim_grounding.py`.
Add `tests/test_semantic_os.py` to the class's `required_checks` (correction 6). Protocol text ships
here, not PR-4: `CLAUDE.md` §6.7, `docs/governance/SEMANTIC_OS_CONTRACT.md` §10,
`docs/reference/schemas.md` §9.14, `docs/topics/ai-automation-agent.md` Discussion.

GOVERNED_FILES += `src/governance/semantic_grounding.py`. GREEN_FLOOR += the new grounding test.
Amend `JSONL_CLAIM_SURFACE_CHANGE.required_checks` += the two grounding tests +
`tests/test_semantic_os.py`.

---

## PR-3 — Measurement result log + F-083 floor

**Depends on PR-1, PR-2.**

- `configs/research/measurement_result_log.jsonl` — committed, append-only, meta line only at ship
  (`scan_universe: instances/ (tracked); sealed_pass_bound: 0`). Sibling of
  `configs/promotion_log.jsonl`. **Not** a `GOVERNED_FILE` — appends must not re-run GREEN_FLOOR.
- `src/governance/measurement_result_log.py` — `append_measurement_result`, `lines_for_contract`,
  `classify_l5_basis`.

**Line schema (§9.16), with correction 1 applied:** the trust field is
`"trust_mt01_matrix_coverage": Literal["UNRUN","COMPLETE","INCOMPLETE"]` — mirroring the contract's
real `trust_status.mt01_matrix_coverage`. `economic_claims_allowed: False` and `authority:
"research"` are const-pinned.

`classify_l5_basis` requires **five** keys against five frozensets — `walk_kernel` (`WALK_KERNELS`),
`cost_model_id` (`COST_MODEL_IDS`), `fill_model_id` (`FILL_MODEL_IDS`), `geometry_kind`
(`GEOMETRY_KINDS`), `geometry_schema` (`GEOMETRY_SCHEMAS`), plus optional `timeframe` against
`TIMEFRAMES`. **Do not iterate `identity.tokens.L5_BASIS`** — verified 3 keys at `tokens.py:48` with
no geometry; iterating it marks an incomplete basis `BASIS_DECLARED`. Returns
`UNIDENTIFIED | BASIS_DECLARED | N_A`, never `PRESERVED`.

**Never call `identity_check("L5", …)` on a result line** — `_check_l5` (`check.py:246-264`) demands
a full L4 parent plus `L5_PAYLOAD`; a measurement *run* is not one trade, so every line would come
back UNIDENTIFIED and `CC-MC-RESULT-BINDING` could never GROUND.

Import discipline: `from identity.tokens import WALK_KERNELS, …` only. Never `import identity` —
`identity/__init__.py:11` re-exports `identity_check`. This needs a **new** AST pin in
`tests/test_measurement_result_log.py`; the existing `tests/test_identity_store.py` pins the
opposite direction (correction 5).

**Scan universe = tracked `instances/MC-*.json`** (decision A), via `git ls-files`, following
`tests/test_current_findings.py:62`. `drafts/`, MP-* profiles, and the parent-dir
`MC-CPR-L0-XAUUSD-M15-UTC-V1.json` (`mt00: PARTIAL`) stay out of scan and are **not** rewritten.
`_F083_GRANDFATHER` ships empty and shrink-only.

Rule: a scanned instance with `mt00 != UNRUN` **must** have a result line, `declared_artifacts_exist`
true, and every non-null `evidence_artifacts` path hash-matching `artifact_hashes`. All nine are
UNRUN today, so the floor ships green and vacuous — that is the point: the next sealed instance
cannot skip it silently.

Grounder wiring for the three `CC-MC-*` classes (token = `MC-*` id or a contained `instances/` path;
resolve via instance JSON + result log, never `stream_for_path`). Pins: `MC-VCRT-XAUUSD-M15-V2` ×
`CC-MC-SCHEMA-SHAPE` → GROUNDED (shape; UNRUN is legal) · × `CC-MC-RESULT-BINDING` → REFUSED
`CC-MC-DECLARED-UNEXECUTED` · synthetic tmp `MC-JSONL-CLAIM-FIXTURE-V1` with `trust_mt00=FAIL` +
honest result line + matching hashes + `l5_basis=None` → **GROUNDED** with `basis_status=N_A`
(executed ≠ passed — the payload shows FAIL). The fixture never enters the real `instances/` tree.

New test module `tests/test_measurement_result_log.py` — do **not** extend
`tests/test_measurement_contract.py`. GREEN_FLOOR += the new module. GOVERNED_FILES += the module
(not the log file). GOVERNED_PREFIXES += `configs/research/measurement_contracts/instances/` so
flipping an instance to `PASS` fires pre-commit; do not govern the whole tree.

`docs/reference/schemas.md` §9.16 · CLAUDE.md sources row for the log ·
`docs/topics/research-measurement-contract.md` Discussion · amend the change class.

---

## PR-4 — Refuse meaning-from-log

**Depends on PR-2.**

Fill catalog `meaning_authority` for every stream and class: a list of SEM/CN/FM ids, or the
sentinel `INVENTORY_NOT_MARKET`. Floor: each id either is the sentinel or `ground("NOUN", id)` is
GROUNDED — so no invented ids can enter. Grounder tests: "what RANGE means" against
`crt_transitions.jsonl` **and** against `findings.jsonl` → REFUSED `CC-MEANING-NOT-LOG`.
`docs/topics/event-fabric.md` Discussion notes emitter `payload.ontology_ids` is explicitly **not**
this program.

---

## Verification

Run from the repo root with `D:/Tradelatest/venv/Scripts/python.exe`.

Per PR:
```bash
D:/Tradelatest/venv/Scripts/python.exe -m pytest tests/test_jsonl_claim_catalog.py tests/test_jsonl_claim_grounding.py tests/test_semantic_grounding.py tests/test_semantic_os.py tests/test_measurement_result_log.py tests/test_construction_protocol.py tests/test_governance_invariant_check.py -q
```

Full floor (what CI runs) before each merge:
```bash
D:/Tradelatest/venv/Scripts/python.exe scripts/maintenance/check_governance_invariants.py --all
```

Construction protocol, which re-executes the class's `required_checks` rather than trusting a log:
```bash
D:/Tradelatest/venv/Scripts/python.exe scripts/governance/construction_protocol.py validate-completion docs/governance/build_manifests/CH-jsonl-claim-surface.completion.json
```

End-to-end through the real CLI (PR-2 onward) — these are the behaviours the whole program exists for:
```bash
D:/Tradelatest/venv/Scripts/python.exe scripts/governance/query_semantic_os.py --ground --kind JSONL --token logs/crt_transitions.jsonl --relation CC-L3-GLOBAL-UNIDENTIFIED
```
expect `REFUSED`, `refusal_class: CC-L3-GLOBAL-UNIDENTIFIED`, exit 2.

```bash
D:/Tradelatest/venv/Scripts/python.exe scripts/governance/query_semantic_os.py --ground --kind JSONL --relation CC-FINDING-EXPORT --source producer:engine --dest producer:resolver
```
join-only, no `--token`: expect `REFUSED` / `CC-L3-FORBIDDEN-JOIN` (a CAN must not survive a
forbidden join), and `token` reaching `ground_jsonl` as `""`.

```bash
D:/Tradelatest/venv/Scripts/python.exe scripts/governance/query_semantic_os.py --ground --kind JSONL --token docs/current-findings.md --relation CC-FINDING-EXPORT
```
expect `GROUNDED`, exit 0, on a checkout with no `data/` directory.

Regression guard: the four pre-existing claim kinds must be byte-identical —
`ground("EVIDENCE","F-048")`, `ground("NOUN","CN-001")`, `ground("NOUN","CT-008")`,
`ground("IMPLEMENTATION","src/core/engine_runner.py", symbol="EngineRunner")`.

Per §6, every turn appends a `📝 SESSION LOG ENTRY` to `assistant_project.md` (codebase log — this
is governed code/config, not workflow).

---

## Out of scope (unchanged from the spec)

No G001, no promotion, no `ACTIVE_VERSION` change, no live rail, no new agent intent, no new
detector. Do not reopen Canonical Layer Identity / Storage Preservation / Physical Storage. Do not
stamp frozen PKs onto historical JSONL (§12.3). Do not mutate the frozen
`measurement_contract.schema.json`. Do not emit `payload.ontology_ids` from `crt_engine_v2`. PR-5
(Semantic OS CN for the catalog) stays skipped.

Named follow-ons, **not** this program:
- `CH-p-flow-14-doc-and-fid` — fix `docs/architecture/signal-flow.md` scope **and** register an
  F-id (code wins: EngineRunner/`backtest_v2` do not call ExecutionPlanner/UltronRiskGate).
- `CH-grounder-path-containment` — harden `_norm_path` / `ground_implementation` against `..` and
  absolute paths (decision B).
- Tracking `MC-ASYM`, `MC-MRPRIOR`, and `drafts/` — `MC-MRPRIOR` backs published finding F-094 while
  absent from git.
