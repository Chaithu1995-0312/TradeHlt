# Research Provenance Spine — making the LLM→config pipeline mechanically governed

## Context

The requested pipeline already exists in this repo as ~70% built parts, joined by **prose,
not by types**:

```
OHLCV → Deterministic Semantic Features → LLM Knowledge Layer → Semantic Observations
     → Hypothesis Generator → Research Validation → Qualified Strategy Rule → Production Config
```

Feature derivation (ontology → registry → `candle_math`/`derived_math`) and Research
Validation (the M4 gate, `forward_walk`, `metrics_oracle`) are built. Promotion
(`ConfigValidator` → `PromotionManager` → `promotion_log.jsonl`) is a real write-authority
gate. What is missing is the **connective tissue**.

**The binding reason to build this now: the codebase is under active bug-fix.** Every fix
silently invalidates every result produced before it, and *nothing in the repo records that
this happened*. There is no artifact that answers "was this result produced before or after
the fix?" — so results accumulate at an unknown and undeclared level of trust.

Three source-verified symptoms (read this session, not quoted from findings):

1. **Results are not stack-pinned.** `baseline_capture.build_manifest()` records the schema
   hash, config sha256 and two model families — no ontology, no `active_models.yaml`, no
   composite identity. Backtest run records carry no stack identity at all.
2. **`baseline_capture.py:100` hashes the wrong file** — `models/zone_registry.json` while
   the active config's `zone_registry_path` is `models/zone_registry_v4_2026_07.json`. It
   pins the rollback artifact, not what loads. A concrete instance of the general problem.
3. **The trust ladder is ritual, not structure.** §6.5's Authority Ladder and E-001's
   pre-registration check are enforced by discipline. Nothing structurally prevents an
   unvalidated claim from being cited as evidence.

**Intended outcome:** authority becomes a *positional* property of a record's place in an
append-only chain, not a claim any record can make about itself — and every bug fix becomes
a recorded epoch boundary rather than a silent one.

### Standing constraint — findings are UNTRUSTED input

Per user direction: the existing findings corpus (F-019…F-061) is treated as **possibly
bug-contaminated** and is **not** a design premise, evidence, or justification anywhere in
this plan. It is a *subject* of this system, never an input to it. Findings triage —
deciding which conclusions survive — is explicitly **deferred until the code is built and
reviewed**. This plan does not read, cite, revalidate, or flip a single finding.

Corollary that makes this safe to operate *during* the bug-fix period: because a `PROMOTE`
verdict from a superseded `stack_epoch` cannot promote (invariant 3 below), any
observation or validation run minted against buggy code **auto-expires** when the fix bumps
the epoch. Contamination cannot leak into production by age.

---

## The structural idea

> **Authority is positional, not asserted.**

An observation is structurally incapable of reaching `configs/production/` — not by policy,
but because each stage can only be minted from the prior stage's id:

| Stage | Record | Minted from | Authority |
|---|---|---|---|
| Semantic Observation | `OBSERVATION` | nothing (LLM output) | `NONE` — hard-coded |
| Hypothesis | `HYPOTHESIS` | ≥1 `observation_id`; freezes a `preregistration_hash` | `NONE` |
| Research Validation | `VALIDATION_RUN` | one `hypothesis_id` whose prereg hash still matches | evidence only |
| Qualified Rule | `QUALIFIED_RULE` | ≥1 run with `verdict == PROMOTE` at the *current* `stack_epoch` | may propose a config delta |
| Production | existing `promotion_log.jsonl` | one `rule_id` | write authority |

Same shape as `src/journal/`'s tier split (permanent identity vs. churning detail) and
`production_bundle.py`'s conservative-on-conflict rule — reuse the pattern, don't invent one.

**Four refusal invariants** — this is what "harden" means concretely:

1. `PromotionManager` accepts a `rule_id`, never a run/hypothesis/observation id.
2. A run whose `hypothesis.preregistration_hash` no longer matches is dead — the spec was
   edited after the result (anti-p-hacking, currently ritual-only).
3. A `PROMOTE` verdict from a **superseded `stack_epoch`** cannot promote. This is the
   invariant that makes the system safe to run on a codebase still being fixed.
4. A rule's `config_delta` may only touch keys classified BEHAVIORAL by
   `scripts/analysis/behavior_census.py` (§6.5). Research can tune thresholds; it can never
   restructure the engine.

---

## Phase 0 — Stack identity (prerequisite for everything else)

New: `src/config_layer/stack_version.py` — sibling of `production_bundle.py`, read-only,
`authority: NONE` in its meta.

**`behavior_hash`** — only inputs that can move a trade ledger:
1. HOW — `ACTIVE_VERSION` + **sha256 of the whole config file** (the in-file `config_hash`
   covers `params` only; new top-level sections are hash-neutral per §6.5).
2. WHAT — digest over frozen runtime sections (`primitives`, `feature_compositions`,
   `derived_metrics`, `rolling_indicators`) taking only
   `{id, version, lifecycle, formula, impl, numerator, denominator, clip, active}`.
   Excluding `taxonomy`/`semantics`/`lineage`/`notes` is what buys churn-free versioning.
3. EXECUTION — `SCHEMA_VERSION` + `CANONICAL_FEATURE_DIM` + `SCHEMA_HASH`, **plus sha256 of
   `candle_math.py` and `derived_math.py` sources**. Required: `SCHEMA_HASH` is md5 over
   joined feature *names* (`feature_schema.py:178`) and is blind to a formula change — which
   is exactly the bug-fix case this plan exists to catch.
4. WHO-enabled — only families where `BundleMember.executes_checkpoint` is True:
   `(family, selected_version, artifact_sha256)`. A disabled family cannot move a ledger.

**`provenance_hash`** — the above plus full-file sha256 of `market_ontology.yaml` and
`active_models.yaml`, ontology `version` + `spec_schema.semantic_registry.version`,
`meta.schema_version`, `state_contract_schema_version`, **all** families with their
`execution_status`, every model-registry sha256, `ProductionBundle.divergences`, and git SHA
**explicitly flagged unreliable** (the working tree structurally diverges from HEAD — a bare
git SHA is a false pin; verify tree state at implementation time).

Reuse, don't rebuild: `load_production_bundle()` already reconciles Selected vs Enabled
across all 6 families and already withholds `executes_checkpoint` on conflict. The
"checklist per version (CRT / zone / RR / TradeNet / trained models)" **is**
`ProductionBundle.executing_families()` — it exists.

**Epoch ledger** — `configs/stack_epoch_log.jsonl`, append-only, `promotion_log.jsonl`
discipline. `stack_epoch` increments only on a previously-unseen `behavior_hash`; a
provenance-only change appends `kind: "STACK_PROVENANCE"` against the current epoch. Never
rewrite a line (§6.2 rule 4). **Every bug fix that changes executed math produces a new
epoch — that is the point.**

**Also fix here:** the `baseline_capture.py:100` zone-registry path bug, and replace its 3
hardcoded registry hashes + 2-family `get_active*` calls by delegating to
`load_production_bundle()`.

---

## Phase 1 — Stamp results and analysis (the actual "harden" ask)

Every artifact under `results/` and every research driver run emits a `VALIDATION_RUN`
record. Additive; **must be parity-proven byte-identical** on the ledger (the module is
read-only, so any diff means an import side-effect).

```
{"kind":"VALIDATION_RUN","run_id","hypothesis_id"|null,"stack_epoch","behavior_hash",
 "dataset_fingerprint","ledger_path","ledger_sha256","gate_spec",
 "metrics":{...from metrics_oracle...},"verdict":"PROMOTE|REJECT|INSUFFICIENT",
 "authority":"evidence_only","timestamp"}
```

`hypothesis_id` is nullable so **existing** drivers can be stamped immediately without
waiting on Phase 2. `dataset_fingerprint` must record *which* `dataset_integrity` layers
actually ran (L1/L2/L3 coverage is not uniform across entry points — verify call sites at
implementation time), never assert all three.

**Payoff from this phase onward:** results produced before and after any given bug fix become
mechanically distinguishable. No retroactive claim is made about existing results — they
simply carry no epoch, which is itself the honest answer. Triage of the historical corpus is
**out of scope until the code is built and reviewed**.

---

## Phase 2 — Observation and hypothesis ledgers

```
OBSERVATION  {observation_id, stack_epoch, feature_scope:[FM-0NN...], instrument_scope,
              timeframe, claim, falsification_condition (REQUIRED), generated_by,
              prompt_hash, authority:"NONE", status:"UNVALIDATED"}
HYPOTHESIS   {hypothesis_id, observation_ids:[...], interpreter_spec, gate_spec,
              preregistration_hash, frozen_at, authority:"NONE"}
```

`falsification_condition` is non-nullable — §6.6's epistemic block made a schema constraint
instead of a ritual. `interpreter_spec` compiles to the existing Level-4 Interpreter Contract
so a hypothesis runs through the unchanged M4 gate; **confirm that API shape before
implementing** — it was not re-read this session.

**Storage location decision:** these are PRIMARY records (not regenerable, not runtime
noise), so they cannot live under gitignored `data/`. Proposed: a tracked `research_ledger/`
at repo root, sibling in discipline to `configs/promotion_log.jsonl`. Verify against
`.gitignore` before creating.

---

## Phase 3 — The promotion gate (first write-authority change)

`PromotionManager.promote_from_qualified_rule(rule_id, version)` enforcing the four refusal
invariants. Requires user approval per §6.2 — it changes the only path to production.

---

## Phase 4 — The Claude-as-observer protocol

"Pure Claude coding agent" is read here as: **the LLM Knowledge Layer is a governed protocol,
not a new service.** No LLM microservice, no new runtime dependency — consistent with
CLAUDE.md §4 ("LLM is a tie-breaker, not a hot-path dependency") and `agent/`'s deterministic
`PLAN_REGISTRY` design.

Deliverable: a skill + output contract that makes a Claude session emit valid `OBSERVATION`
records from deterministic feature evidence — required `feature_scope` in FM ids, required
falsification condition, `authority: NONE` stamped structurally. The vocabulary for market
narratives already exists in `configs/research/market_story_ontology.yaml` +
`src/research/synthetic/`; reuse it rather than inventing a parallel one.

Placed last for dependency reasons only (it needs the ledgers to write into). It is *not*
blocked on the codebase being bug-free — invariant 3 makes observations minted against buggy
code expire on their own.

*Alternative if a scripted generator is preferred:* route through the existing
`llm_inference_client` (already fails to neutral 1.0 after `fail_count_disable`). Costlier,
and adds a runtime dependency the repo has deliberately avoided.

---

## Files

| File | Change |
|---|---|
| `src/config_layer/stack_version.py` | NEW — `compute_stack_version()`, `resolve_epoch()`, `append_epoch_record()` |
| `src/config_layer/production_bundle.py` | additive helper only; no logic change |
| `src/runtime/baseline_capture.py` | delegate to bundle; **fix** the zone-registry path bug |
| `src/runtime/backtest_v2.py` | stamp `stack_epoch` + `behavior_hash` on the run record |
| `src/governance/promotion_manager.py` | Phase 3 — `promote_from_qualified_rule` + 4 invariants |
| `configs/stack_epoch_log.jsonl` | NEW append-only |
| `research_ledger/*.jsonl` | NEW append-only (location to confirm vs `.gitignore`) |
| `docs/reference/schemas.md` §9 | document all 5 line shapes |
| `docs/knowledge-map.md` | record the chain (§6.2 rule 1 — update the doc that owns the topic) |

## Tests (floors)

`tests/test_stack_version.py`
1. **Determinism** — two calls, unchanged inputs, identical `behavior_hash`.
2. **Churn guarantee** — editing `semantics`/`notes`/`taxonomy` moves `provenance_hash`,
   leaves `behavior_hash` byte-identical.
3. **Sensitivity** — an ACTIVE formula, a `params` value, or an *enabled* artifact does move
   it. Includes the bug-fix case: change a `derived_math` function body, assert the hash moves.
4. **Inert-model insensitivity** — mutating a non-executing family does not.
5. **Ledger** — append-only, monotonic epoch, provenance-only change does not increment.

`tests/test_research_provenance.py`
6. **Positional authority** — an observation/hypothesis/run id passed to `PromotionManager` is refused.
7. **Pre-registration immutability** — editing a hypothesis post-run invalidates the chain.
8. **Stale epoch refused** — a `PROMOTE` from a superseded epoch cannot promote.
9. **Behavioral-only delta** — a rule touching a STRUCTURAL key is refused.
10. **Append-only** — no line rewrite in any ledger.

## Verification

1. `pytest tests/test_stack_version.py tests/test_research_provenance.py -v`.
2. Compute on HEAD, re-run after only a `notes:` edit in `market_ontology.yaml` — assert
   epoch unchanged, provenance changed. Then edit a `derived_math` body — assert epoch moves.
3. **Parity proof**: XAUUSD freeze-pin backtest byte-identical before/after Phases 0–1.
   Known caveat: byte-identity only covers exercised paths and XAUUSD yields 0 trades on the
   freeze slice — also run BNBUSDT gate-ON.
4. `python src/runtime/baseline_capture.py --label stackver` — confirm the manifest carries
   the ontology, the WHO layer, all 6 families, and the **v4** zone registry.
5. Existing floors green: `test_active_models_registry.py`, `test_feature_lineage.py`,
   `test_doc_citations.py`.

## Open — surfaced, deliberately not resolved (§6.2 rule 3)

`active_models.yaml` `gaussian.identity.runtime_binding.compatibility.feature_schema_dim: 38`
vs `feature_schema.py` `CANONICAL_FEATURE_DIM = 39` / `SCHEMA_VERSION = "4.0"`. Both values
read directly from source this session — this is a file-vs-file disagreement, not a finding.
Exactly the drift class `stack_version` exists to surface, so it is a motivating exhibit, but
resolving it needs a user decision (does 38 mean the scored subset, as zone_gate's
`scored_dims: 38` does, or is it stale post-v4?). Not touched by this plan.
