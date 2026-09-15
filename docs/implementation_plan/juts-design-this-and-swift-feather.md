# Fusion/decision ownership walk (W5 segment 1) + BitNet reachability verdict

**Lane:** topic-coverage census (the T1–T15 / W1–W6 partition), continuing directly from the W1
walk. **READ-ONLY on `src/`, `configs/`, `tests/`, `scripts/`, `tools/`.** The only file written is
`assistant_project.md` (the §6 SESSION LOG mandate + the §6.2 correction below).

No code, no config, no CLAUDE.md edit, no F-id, no G001, no change id, no git action — nothing here
modifies behaviour, so no construction-protocol manifest is required.

---

## Context

The W1 walk (T11–T15) closed at **union 192 / 1,668 (11.51%)**. Its Stage-1 exit recommended
walking fusion/decision next as its own topic; the user selected that, plus folding in the BitNet
reachability verdict, plus correcting the record in place.

### Why fusion/decision is a separate topic from W1, and where its boundary sits

Verified at source this session, not recalled:

- `src/core/engine_runner.py` imports `fusion_engine`, `decision_engine`, `acceptance_controller`,
  `convergence_controller`, `signal_audit`, `collector`, `regime_governor` — and the four scoring
  engines from `src/engines/`. `EXPECTED_ENGINES = {"crt","gaussian","zone_gate","rr"}` (line 54).
- `engine_runner.py` **never calls** `ExecutionPlanner` or `UltronRiskGate`. It names
  `UltronRiskGate` three times, every one a *disclaiming comment*: `:42` "NOT the capital-protection
  layer", `:512` "controls RegimeGovernor, NOT UltronRiskGate", `:1026` "enforced by UltronRiskGate
  after SL/TP (live_engine_hook)". `ExecutionPlanner` lives at `src/config_layer/execution_planner.py`
  and is called by the *caller*, not the runner.

That is a source-marked boundary, and it matches the T10 sweep's own path-ownership split
(`fusion_decision 17` | `planner 12` | `ultron 7` | `scoring_engines 27`). **User decision: tight
scope** — this walk owns the fusion/decision segment only. `src/engines/`, planner and ultron stay
separate future topics.

### Corrections carried in (§1.1 / §6.2 — verify before stating; fix the source, not the chat)

Two claims in the previous turn were wrong. Both were caught by re-verification, both are recorded
in `assistant_project.md`, and both are corrected here rather than only in chat:

| Recorded claim | Verified state | Command |
|---|---|---|
| this session's R1–R3 work "landed as commit `40533f7`" | `40533f7` is a **dangling commit** — parent `c782803`, on **no branch**, `git merge-base --is-ancestor 40533f7 HEAD` → **false**, 52 files differ from HEAD. The work actually landed via **`46b17a9`** ("feat(query_trace): add run-identity enforcement and --run-dir"), which **is** an ancestor of HEAD. | `git merge-base --is-ancestor`, `git log -S assert_view_lineage` |
| "the tree has now SETTLED" | **Not settled.** 15 `claude` processes live; HEAD moved `c782803` → `61094ea` since that sentence was written. | `tasklist`, `git log --oneline -3` |

The *conclusion* held (the R1–R3 work survived and is in HEAD); the *attribution* and the
*stability claim* did not. Note the second correction weakens — it does not strengthen — the case
for starting the deferred F-069 re-measurement, which stays deferred.

### What makes this walk safer than W1's

W1 was walked against `crt_state_resolver.py` with +708 staged lines in flight. Here,
`git status --porcelain -- src/core/ src/engines/ src/config_layer/rr/` is **empty**. The surface
being walked is committed and quiet, even though the repo as a whole is not.

---

## Deliverable format (matches T6–T15 exactly — do not invent a new one)

Per named topic, over the **1,668-file denominator** (`src/`+`tests/`+`scripts/`+`tools/` `*.py`
plus `configs/{formulas,production,research,market_reality}`; re-derived and confirmed at 1,668 this
session — 1,582 py + 86 config).

- `OWNED=n` — files this topic owns. The partition is **disjoint**: a file belongs to exactly one
  topic. A file already owned by T1–T15 is *restated*, never double-counted (the T5→T6 precedent).
- `FOOT=n (x.x%)` — footprint by reference.
- An explicit **NOT owned by this topic** list, with a stated reason per exclusion.
- Updated **union owned** and its % of 1,668.

---

## Stage A — record the corrections (the only write, done first)

Annotate the existing W1 entry in `assistant_project.md` **in place**, preserving history per §6.2
rule 4 — `CORRECTED: <old> -> <new>`, never silent-delete:

- Line ~388 (`TREE STATUS`): annotate the `40533f7` attribution and the "tree has SETTLED" sentence.
- Line ~395 (`Next Step`): annotate the trailing "`40533f7`'s committed code" reference.

Both annotations name the verifying command, not just the corrected value.

---

## Stage B — the fusion/decision walk

### B1. Re-establish the disjoint baseline

Prior union **192** (T1–T15). Re-confirm the denominator re-derives to 1,668 from the stated globs
before any topic is counted.

### B2. Partition the candidate set

`src/core/` is 21 files and is **not** a single topic — its own docstrings split it cleanly. Walk
each file, read its module docstring, and assign. Expected natural split (to be confirmed by the
walk, not assumed):

| Candidate grouping | Representative files |
|---|---|
| Fusion aggregation | `fusion_engine.py`, `convergence_controller.py`, `acceptance_controller.py`, `dynamic_threshold.py`, `hierarchical_meta_fusion.py` |
| Decision authority | `decision_engine.py`, `signal_belief_tracker.py`, `regime_governor.py`, `gate_intelligence.py` |
| Spine orchestration | `engine_runner.py`, `types.py`, `signal_audit.py`, `collector.py`, `governance_mode.py`, `backtest_port.py`, `__init__.py` |

Plus the `fusion_engine` / `decision_engine` / `engine_runner` sections of
`configs/production/v2_htfcrt_2026_08.json` (**ACTIVE_VERSION**, confirmed this session), and the
owning tests.

### B3. Adjudicate the boundary cases explicitly — each needs a stated verdict, not a silent assignment

- **`model_registry.py`** (63 KB, the largest file in `src/core/`) — "versioned model registry with
  promotion guard". That is governance/W6 by its own docstring, not fusion/decision. Likely
  **excluded**; say why.
- **`ultron_risk_gate.py` / `ultron_live_adapter.py` / `ultron_risk_gate_wrapper.py`** — capital
  protection, past the `run()` boundary. **Excluded** under the tight scope; they are the `ultron 7`
  bucket.
- **`feature_store.py`** — the F-085 canonical ingestion boundary, living in `core/` but doing W1
  work. T11 owned only `src/data_ingestion/*.py`, so this file is currently **unowned by anyone**.
  Decide: restate into T11, or own here. Flag either way.
- **`hierarchical_meta_fusion.py`** — fusion-named, but its layer 6 is TradeNet
  (F-005: built, unwired). T10 (TradeNet) OWNED=8. Confirm it is not one of those 8 before owning it
  here; if it is, restate rather than double-count.
- **`backtest_port.py`** — a dependency-inversion port, not decision logic.
- **`src/config_layer/rr/rr_fusion.py`** — fusion-named and `rr_fusion.enabled: False` on the active
  config (F-038/F-044). It lives outside `src/core/`; decide whether the topic reaches it.
- **`collector.py` / `signal_audit.py`** — journals emitted *by* the spine. Same shape as the W1
  call on `bar_structure_snapshot.py` (excluded as a W2 measurement sidecar). Apply the same test
  and say whether the answer comes out the same.

### B4. Guard against the two inflation traps this lane has already hit twice

- **Token inflation** (T8 `bare-mt5`, T12 `registry`): derive test ownership by **import target**,
  not filename token. A regex over `from core.*` already returns clear non-members
  (`test_model_evidence.py`, `test_historical_zone_mapper_corpus_parity.py`,
  `test_live_rail_dm001_atr.py`) — those are FOOT, not OWNED.
- **Case-sensitivity inflation** (caught during this scoping): `grep -c "bitnet"` on
  `engine_runner.py` returns **0** while `grep -i` returns matches. Every count in the report states
  whether it was case-sensitive.

---

## Stage C — BitNet reachability verdict (folded in per user decision)

**Not** a 43-file map. A short measured statement answering one question: *is BitNet on the live
decision path at all?* Evidence already gathered, to be completed and stated with commands:

- `use_bitnet: False` and `rr_fusion.enabled: False` on `v2_htfcrt_2026_08` (ACTIVE_VERSION).
- F-055 measured enabling it as harmful (pooled ΔE −0.13R, 0/4 instruments improve); F-004 records
  it INERT on the active patch.
- `engine_runner.py` — the orchestrator every decision passes through — contains **zero** lowercase
  `bitnet` references. Its only two `BitNet` strings are `:6` (module docstring) and `:467` (a
  comment).
- `assert_serve_allowed(use_bitnet=False)` is an explicit **no-op** by its own docstring
  (`bitnet_registry.py:223` "use_bitnet=false → no-op (inert spine path)").

Two observations to classify, **report-only** (§6.8 *no silent remediation*; §1.2 scope control —
fixing either is a separate authorized turn):

1. **`engine_runner.py:6`** docstring: *"All four engines run unconditionally (CRT, Gaussian,
   **BitNet**, RR)"* vs `EXPECTED_ENGINES = {"crt","gaussian","zone_gate","rr"}` at `:54`. The
   docstring names BitNet where the completeness set names `zone_gate`. Classify per §6.2 rule 2
   (`DOC_DRIFT` is the likely call — code wins — but state the classification, do not assume it).
2. **`convergence_controller.py:12/70/222`** — a live fusion step named **"BitNet dampening"** that
   computes `zone_gate_score ** 4`. No BitNet is involved. Classify per §6.8's closing vocabulary
   (`STALE / LEGACY ARTIFACT` vs `DOCUMENTATION GAP` — name which, and the violated contract if any).

Close the verdict with exactly one §6.8 verdict token. `unreachable ≠ bug` and
`configured ≠ must be reachable`: BitNet being inert is a **configuration state**, not a fault.

---

## Stage D — report

One `📝 SESSION LOG ENTRY` appended to `assistant_project.md` carrying: the Stage-A corrections,
per-topic `OWNED`/`FOOT`, the NOT-owned exclusions with reasons, updated union owned + %, the
BitNet verdict, and a `Belief Update / ROI / Goal` block. No other file is written. No atlas publish,
no new doc file, no `docs/topics/` edit.

---

## Guardrails

- **Read-only except `assistant_project.md`.** No `src/`, `configs/`, `tests/`, `scripts/`, `tools/`
  or CLAUDE.md edits. **No git add/commit/stash** — 15 concurrent sessions are live.
- **Use Edit, never heredoc/sed** on `assistant_project.md` (§1.6 — this repo has paid for that rule).
- **Ownership is disjoint.** A file already owned by T1–T15 is restated, never double-counted.
- **Interpreter** `venv\Scripts\python.exe`. Prefer targeted grep over agent fan-out (§1.2).
- **No F-id.** A census is not a finding, and a reachability verdict is not a finding. The F-069 gap
  stays deferred and is *further* deferred by the "tree not settled" correction above.
- **§6.8:** do not conclude "defect" from difference. Name the violated contract or do not say "bug".

---

## Verification

Census work is verified by reproducibility and by the partition's own invariants, not by pytest:

1. **Denominator reproducible** — re-derives to 1,668 from the stated globs (already confirmed:
   1,582 py + 86 config).
2. **Disjointness holds** — assert pairwise intersection of every topic's owned set is empty
   *programmatically*, not in prose (the T7∩T8 precedent, and the check that caught the T12 35-vs-34
   slip).
3. **Union arithmetic checks** — `192 + <new owned> = <reported union>`, and the % matches 1,668.
4. **Every `src/core/` file is accounted for** — each of the 21 is newly owned, restated as
   already-owned, or on the NOT-owned list with a reason. No file silently unassigned.
5. **Spot-check FOOT two ways** — recompute two topics' footprints by import-target and by token,
   and report the gap. A large gap is the inflation signature, not a bigger number.
6. **Corrections landed** — `grep -c "CORRECTED" assistant_project.md` shows the Stage-A
   annotations present, and the original text is still readable beside them (history preserved).

No test suite is expected to change. If one does, something non-read-only happened — stop.

---

## Deferred (explicitly not this task)

- **`src/engines/` scoring engines** (~27-file bucket), **planner** (12), **ultron** (7) — the rest
  of W5. Natural next topics; not started.
- **The F-069 gap (68.69% measured vs 88.16% registered).** Still deferred, and now *more* clearly
  so: the tree is not settled. If re-measured later and the gap persists, raise a §6.2 rule-3
  `TruthConflict` naming both sources and let the user adjudicate — never silently pick a winner.
- **`jsonschema` undeclared** despite the hard import at `dataset_registry.py:21` (carried across
  four plan phases now, still out of scope).
- **Fixing** the `engine_runner.py:6` docstring or the "BitNet dampening" name — both are Stage-C
  *observations*; remediation is a separate authorized turn (§6.8).
