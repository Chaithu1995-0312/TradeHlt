# CRT State Hardcoding Census — register as F-082 (report only, no code change)

## Context

`ACTIVE_VERSION = v2_htfcrt_2026_08`. Question asked: **how many places are CRT states
hardcoded into the codebase, other than config?**

The repo runs a config-first doctrine (CLAUDE.md §6.5) with a declarative state layer
(`configs/formulas/market_crt_states.yaml`, `active_models.yaml`), so the expectation is that
state identity + the transition graph are declared once. The census below is what is actually
true today.

**Scope decision (user, this session): report only.** This is an `OBSERVATION_ONLY` audit —
no `src/`, config, or test changes. The census is already complete (findings below); the work
remaining is to record it per the CLAUDE.md §6.2 Findings Mandate so it does not evaporate into
chat, and to file the §6 SESSION LOG.

---

## The census (complete — this is the finding body)

Vocabulary counted: the 12 `CRTState` members (`RANGE`, `SHADOW_PENDING`, `SWEEP`,
`DISPLACEMENT`, `EXPANSION`, `EXPIRED`, `RETEST`, `EXECUTION`, `RESOLUTION`, `RANGE_C1`,
`MANIPULATION_C2`, `DISTRIBUTION_C3`), as typed enum references and as bare string literals.

| Surface | Files | Occurrences |
|---|---|---|
| `src/` — bare string literals | **25** | **267** |
| `src/` — typed `CRTState.X` refs | **4** | **48** |
| `scripts/` | **47** | — |
| `tests/` | **53** | — |
| `docs/governance/` artifacts | **~30** | — |
| **Declaration authorities (the graph itself)** | **3** | — |

**29 distinct `src/` modules** carry hardcoded CRT state vocabulary; only **3 places** declare
the state graph, and all 3 are already mutually parity-gated. The other 26 are ungated.

### Layer 1 — Declaration authorities (3, all gated) ✅

| # | Location | Gate |
|---|---|---|
| 1 | `src/config_layer/state_identity.py:43-61` (enum) + `:85-107` (`VALID_TRANSITIONS`) | §4.0 Tier-1 seed of record |
| 2 | `active_models.yaml:125` `valid_transitions` | fail-closed at **every** `CRTEngine()` construction via `state_contract_loader._validate_transition_graph` → `state_topology.build_runtime_transition_graph` |
| 3 | `configs/formulas/market_crt_states.yaml:245` | `tests/test_crt_states_yaml_transition_parity.py` (SK-0, 2026-08-18) |

(3) carries one declared divergence — `SHADOW_PENDING → EXPANSION` — because
`try_shadow_pending_to_expansion` collapses SHADOW_PENDING→SWEEP→EXPANSION inside one
`process_candle`, so a per-bar observer sees a direct edge. Pinned as an explicit allowance
with a stale-pin ratchet, behaviourally proven rather than grepped from a comment. This layer
is healthy.

### Layer 2 — Hardcoded state *logic* (4 modules, ungated — largely by design)

| Module | Count | What is hardcoded |
|---|---|---|
| `src/config_layer/crt_engine_v2.py` | 25 enum + 60 literals | The `try_*_to_*` guard methods **are** the executable transition machine. Config declares which edges are *legal*; nothing declares which the engine *attempts*. Plus reset-reason→state maps (`:399`, `:483-534`) and ~35 literal `from_state=`/`candidate_to_state=` telemetry pairs. |
| `src/features/crt_state_resolver.py` | 88 literals | Nominally YAML-driven, with a large hardcoded ladder on top: `_STICKY_STATES` (`:1336`), engine-event override ladder (`:463-495`), per-state entry gates (`:828-1005`), default `current_state = "RANGE"` (`:125`). This is the mechanism behind **F-069** (88.16% engine↔resolver parity, EXPANSION recall 10.77%, determined structurally config-unreachable). |
| `src/config_layer/parent_crt.py` | 8 enum refs | Parent 3-candle machine (`:85-154`) fully hardcoded; the YAML mirror of its sub-graph is explicitly documentation-only. |
| `src/config_layer/htf_state.py` | 5 + 4 members | `HTFState` + `ObjectiveStatus` (F-078) — a **second state dimension with no config declaration at all**, not even a documentation mirror. |

### Layer 3 — Ungated state-set duplicates in `src/` (the real drift risk) 🔴

Each re-declares a *subset* of the state set as a private literal collection; none is covered
by a parity test, so each silently mis-handles any state added to the enum.

- `src/utils/pattern_hasher.py:36-42` — a **7-state** alphabet (`RANGE→R … RESOLUTION→Z`).
  Missing `SHADOW_PENDING`, `EXPIRED`, and all 3 parent states → **5 of 12 silently unhashable.**
- `src/research/adapters/structural_event_source.py:24` — `_STAGES = ("SWEEP","DISPLACEMENT","EXPANSION","RETEST")`, plus a second literal list at `:88`.
- `src/msip/disagreement.py:92-95` — hardcoded 4-state "structural" subset.
- `src/research/zone_mapping/*.py` — 58 literals across 6 files (`rare_zone_fa_characterization` 22, `rare_zone_context_filter_eval` 18, `gaussian_family_shadow_eval` 14, `crt_zone_crosstab` 10, `boundary_hypothesis_eval` 3, `gaussian_delta_gap_eval` 3).
- `src/utils/episode_summarizer.py` (5), `src/research/synthetic/stories/*` (4 files, 8), + 6 single-occurrence modules.

**Name collision:** `src/research/candle_state/encoder.py:37` defines `VOL_EXPANSION = "EXPANSION"`
— a *volatility-regime* label whose string value equals the CRT state `EXPANSION`. Any
cross-module join keyed on the bare string conflates two unrelated vocabularies. Same shape as
the F-063 `trend_strength` collision.

### Layer 4 — Outside `src/`

47 `scripts/`, 53 `tests/`, ~30 `docs/governance/` artifacts. Four governance artifacts
independently record the transition graph (`crt_executable_state_graph.json`,
`CRT_TRANSITION_COVERAGE_MATRIX_V1.json`,
`crt_architecture_adjudication_v1/CRT_9_STATE_EXECUTABLE_GRAPH_V1.json`,
`semantic_os/concepts.yaml` CN-004) — all generated/census artifacts, not authorities, none
mechanically pinned to the enum.

---

## Work to perform

Three files, all documentation. **No `src/`, config, or test changes.**

### 1. `docs/current-findings.md` — add F-082

Append a new `### F-082 · …` entry immediately before the `## Funding Ledger` section, using
the exact field block that F-081 (`:1216-1226`) uses: `Type` / `Family` / `Contract` / `Status`
/ `Confidence` / `Validated` / `Revalidate-by` / `Evidence` / `Supersedes` / `Reversal` /
`Owner` / `Note`.

- Type: `ARCHITECTURE`
- Status: `VALIDATED`, Confidence: `Certain` (mechanical census, source-verified, not inferred)
- Validated: `2026-08-19`; Revalidate-by: a date consistent with neighbouring ARCH findings
- Contract: `UNKNOWN` (per the repo-wide state — `MEASUREMENT_LAYER_STATUS = OPEN`)
- Evidence: the Layer 1–4 tables above, with the `file:line` citations verbatim
- Note must state: **grants no authority (§6.5)** · **no G001** · `ACTIVE_VERSION` unchanged
  (`v2_htfcrt_2026_08`) · CRT closure stays **REOPENED**, this does not touch it ·
  `OBSERVATION_ONLY`, nothing remediated · relates to F-069 (resolver ladder), F-078
  (`HTFState` dimension), F-063 (prior name-collision precedent)

Follow §6.8 discipline in the wording: Layer 2 is `INTENTIONAL SEMANTIC SEPARATION` (transition
control flow is STRUCTURAL per §6.5 and correctly lives in code) — **not** a defect. Only
Layer 3 is a `TEST / CONTRACT GAP`. Do not call Layer 2 a bug.

### 2. `CLAUDE.md` §6.2 — add the F-082 row to the Repository Truths Index

One row in the truths table (`| F-082 | ARCH | … | Certain |`). This is **bidirectionally
enforced** by `tests/test_current_findings.py` — every non-terminal finding must appear in both
the living doc and the index, so omitting this row fails the floor.

### 3. `assistant_project.md` — append the §6 SESSION LOG entry

The codebase log (governed code/doc surface → `assistant_project.md`, not
`llm_project_assistant.md`). Include the `Belief Update / ROI / Goal` line per §7.4.

## Verification

```bash
python -m pytest tests/test_current_findings.py tests/test_session_log.py -q
```

Also confirm nothing behavioural moved (should be trivially true — doc-only change):

```bash
git status --short src/ configs/
```
