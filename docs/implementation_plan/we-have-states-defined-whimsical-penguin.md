# SK — Structural Kernel: one governed CRT implementation, research as consumers

## Context

**The problem.** CRT state logic is not single-source. The audit below found the same
boundary-sweep predicate written **verbatim in six places**, and the F-074 directional
displacement contract written in three. Every copy's own docstring says it "mirrors
`RangeDetector.detect_sweep`'s geometry exactly" — and **nothing checks that it still
does**. When F-074 landed (2026-08-13) it had to be hand-propagated to three files. That
is the failure mode: a geometry fix is a manual broadcast, and drift is silent.

**The goal (user-set).** One governed structural implementation + configuration. Research
consumes that same implementation. When research finds something valuable, we can trace
exactly which program produced the evidence and promote it — without minting another
competing CRT implementation.

**The distinction this design turns on.** The existing "research isolation" policy
(`weekly_sweep` / `visual_crt` module docs: *"reimplement the small shared arithmetic
locally; never import the live spine"*) conflated two different independences:

| | Value | Verdict |
|---|---|---|
| **Founding independence** — *what do we call liquidity?* (a weekly calendar range, a chart-visible pool, an M15 structural range) | This is what made F-042 and F-081 legitimate NEW ontologies rather than sweeps of the incumbent. It is the only thing F-028's reopen condition ever asked for. | **Preserve, permanently** |
| **Arithmetic independence** — *how do we test "swept"?* | Bought nothing. Costs correctness: 6 copies, 1 manual broadcast per fix, 0 mechanical checks. | **Eliminate** |

The kernel unifies the arithmetic and the sequencing. The **founding stays pluggable** —
that is the whole point, and it is why this is not a loss of research freedom.

---

## Audit findings (the evidence this design rests on)

### Vocabulary — already single-source ✅
`src/config_layer/state_identity.py:43` owns `CRTState` (12) + `VALID_TRANSITIONS`.
`state_topology.py` / `state_contract.py` / `state_contract_loader.py` are re-exports.
`active_models.yaml:125` is edge-set parity-gated at every `CRTEngine()` construction
([state_contract_loader.py:139](src/config_layer/state_contract_loader.py:139)).

### Transition graph — two declarations, one un-gated ⚠️
`configs/formulas/market_crt_states.yaml:245` declares a **second** graph with no parity
test, and it already differs: `SHADOW_PENDING: [SWEEP, EXPANSION, RANGE]` vs the enum's
`[SWEEP, RANGE]`. The engine reaches EXPANSION from SHADOW_PENDING as a two-step
([crt_engine_v2.py:1057](src/config_layer/crt_engine_v2.py:1057)), so the direct edge is
plausibly a deliberate collapse — but nothing records that, so it is indistinguishable
from drift.

### The duplicated predicate — 6 verbatim copies ❌

`swept_high = high > ref and close < ref` (symmetric for low):

| # | Site |
|---|---|
| 1 | [crt_engine_v2.py:882](src/config_layer/crt_engine_v2.py:882) — `RangeDetector.detect_sweep` (**the authority**) |
| 2 | [parent_crt.py:154](src/config_layer/parent_crt.py:154) — `_detect_parent_sweep` |
| 3 | [weekly_range.py:185](src/research/weekly_sweep/weekly_range.py:185) — `detect_weekly_sweep` |
| 4 | [weekly_range.py:160](src/research/weekly_sweep/weekly_range.py:160) — `_first_sweep_this_week` (a second inline copy in the same file) |
| 5 | [visual_crt/geometry.py:93](src/research/visual_crt/geometry.py:93) — `detect_pool_sweep` |
| 6 | [crt_state_resolver.py:1068](src/features/crt_state_resolver.py:1068) — `_detect_htf_range_sweep` |

F-074 directional impulse (`long: close > open and close > sweep_price`) — 3 copies:
[crt_engine_v2 `try_sweep_to_displacement`](src/config_layer/crt_engine_v2.py:1083),
[parent_crt.py:162](src/config_layer/parent_crt.py:162),
[visual_crt/geometry.py:162](src/research/visual_crt/geometry.py:162).

### State calculators — 9 sites
Production (3): `crt_engine_v2` (M15 machine) · `parent_crt.py:150` (parent TF C1/C2/C3,
armed on `v2_htfcrt_2026_08`) · `htf_state.py:88` (`classify_htf_state`, separate enum).
Second construction (1): `crt_state_resolver.py` (1,545 lines, does **not** import
`CRTState`, YAML-driven; F-069: 88.16% agreement, EXPANSION recall 10.77%, determination
*divergent construction*).
Research re-implementations (5): `visual_crt/geometry.py`+`retest.py` ·
`weekly_sweep/weekly_range.py` · `candle_state/encoder.py` (separate vocabulary) ·
`zone_mapping/displacement_zone_event_study.py` · `regime/market_state_cluster_engine.py`.
Consumers only (~100): `backtest_v2`, `structural_event_source`, `shadow_emitter`,
`features/smc/*`, `terminals/*`, `tools/tv_forensic/*`, ~40 scripts, ~50 tests.

### Governance gap
The sweep and displacement predicates are **not registered anywhere in the ontology**.
`structural_states:` (line 2095) holds feature-vector slots (FM-054…), not these. Under
§6.6 that makes them discovered-but-undefined market semantics — registering them is the
*mandated origin* of this change, not an optional extra.

---

## Design

Four layers. Founding and thresholds are **data**; geometry and sequencing are **one
governed implementation**.

```
L3  configs/formulas/structure_profiles.yaml   ← what a program declares
      profile: founding + clock + thresholds + walk_spec + lifecycle + owner
        │
L2  src/structure/founding.py                  ← where research stays free
      RangeFounding protocol: h_ref / l_ref / formed_at_index / clock_id
      adapters: M15SLR · ParentRange · WeeklyRange · VisualPool · HTFRange
        │
L1  src/structure/walk.py                      ← one sequencing engine
      StructureWalk(spec, predicates, founding) -> events
        │
L0  src/structure/predicates.py                ← one arithmetic
      swept_boundary() · directional_impulse() · retest_band()
      pure · stateless · thresholds are parameters · no defaults
```

**L0 doctrine mirrors [`candle_math.py`](src/features/candle_math.py)** — the existing
precedent for exactly this problem (F-046: `body_ratio` computed in three places that had
to agree). Mechanism not policy; lives in code; never configurable; never `eval`'d.
Thresholds carry **no defaults** — a silent default is the config-illusion class F-056
documented, and `visual_crt/geometry.py` already enforces this convention.

**L2 is the research freedom guarantee.** A new program (the F-081 successor, say) adds a
`RangeFounding` — a new answer to *what is liquidity* — and a profile. It writes **zero**
geometry. F-028's reopen condition ("a NEW ontology, not a sweep") is satisfied by a new
founding, which is exactly what F-042 and F-081 actually were.

**L3 delivers the traceability the user asked for.** Every structural event carries
`profile_id` + `program_id` + `predicate_versions` (`src/structure/events.py`). So:

- *"which research program produced this evidence?"* → read `program_id` off the event.
- *"promote it"* → flip that profile's `lifecycle: RESEARCH → SHADOW → PRODUCTION` through
  the **existing** promotion gate. **No new code, no new implementation.** This is the
  §6.5 maturity ladder applied to structure instead of to a scalar knob.

### Two scope decisions (user-set)

- **Resolver: kernel for geometry only.** `crt_state_resolver.py` routes its predicates
  through L0 but keeps its own declarative sequencing and its own `market_crt_states.yaml`
  graph. The F-069 construction difference is **not** silently resolved — it is registered
  as an open `TruthConflict` for a separate authorized turn. Removing duplicated arithmetic
  must not smuggle in a semantic decision (§6.8: no silent remediation).
- **Kernel includes sequencing.** L1 owns the SWEEP→DISPLACEMENT→RETEST walk, so
  `crt_engine_v2.StateMachine` and `ParentCRTTrack` both become consumers of one walk
  engine driven by different specs. This is the high-value half **and** the risky half —
  it is stateful (shadow memory + TTL, EXPIRED, reset logic, sweep age, soft-confirmation,
  the parent-bias join), so it cannot be proven by a pure-function probe and is sequenced
  **last**, after L0–L3 have already banked most of the benefit.

---

## Milestones

Each is a separate authorized turn under
[`REPOSITORY_CONSTRUCTION_PROTOCOL.md`](docs/governance/REPOSITORY_CONSTRUCTION_PROTOCOL.md)
with a BUILD_IMPACT_MANIFEST. **A milestone that cannot prove byte-identity STOPS and files
a `TruthConflict` — it never reconciles a difference silently.**

### SK-0 — Register the semantics (no behavior change, hash-neutral)
§6.6 requires the ontology to be the origin of the change, so this is genuinely first.
1. New non-frozen `structural_predicates:` section in
   [`market_ontology.yaml`](configs/formulas/market_ontology.yaml) — `SP-001 swept_boundary`,
   `SP-002 directional_impulse`, `SP-003 retest_band`. Each carries `formula`, `impl`,
   `semantics.why_it_exists`, and the 6/3 current call sites under `lineage.produced_by`.
   The frozen runtime sections (`primitives`/`feature_compositions`/`derived_metrics`) are
   untouched — new node types go in a non-frozen sibling (§6.6 constraint 1).
2. New `structural_walks:` section — walk specs as data (`crt_m15_9state`,
   `parent_crt_3candle`).
3. Add `tests/test_crt_states_yaml_transition_parity.py`: `market_crt_states.yaml` vs
   `state_identity.VALID_TRANSITIONS`, with the `SHADOW_PENDING→EXPANSION` edge as an
   **explicitly declared, commented allowance** (the two-step collapse) rather than a
   silent difference. Mirrors the gate at
   [state_contract_loader.py:139](src/config_layer/state_contract_loader.py:139).
4. Register the F-069 resolver construction difference as a `canonical_unknowns:` node with
   an `epistemic:` block (`known_invariants`: 88.16% / 10.77% EXPANSION recall;
   `unknown_mechanism`: whether the declarative EXPANSION entry is semantically equivalent;
   `resolution_metric`; `falsification_conditions`).

**Gate:** `validate_registry() == []`, ontology tests green, config hash unchanged
(non-`params` sections are hash-neutral).

### SK-1 — Predicate kernel
`src/structure/predicates.py`. All 6 sweep sites + 3 impulse sites become kernel calls.
Leaf-first order — **`weekly_range.py` → `visual_crt/geometry.py` → `parent_crt.py` →
`crt_state_resolver.py` → `crt_engine_v2.py` last** (the engine is highest-risk and moves
only once the kernel has four green migrations behind it).

**Gate per site:** (a) exhaustive differential of old vs new predicate over every bar of
every corpus the site's finding rests on — the predicates are pure, so this is decisive;
(b) byte-identical backtest ledger; (c) `feature_math_lint` green.

### SK-2 — Founding providers
`src/structure/founding.py` + 5 adapters. Pure renaming/typing of what each detector
already holds — no arithmetic moves. Byte-identical by construction; ledger diff confirms.

### SK-3 — Profiles + provenance  ← *this is the milestone that delivers the stated goal*
1. `src/structure/profile.py` + `configs/formulas/structure_profiles.yaml`. Strict
   `_require()`, no silent defaults (§6.5 hard rule). Seed profiles reproduce today's
   behavior exactly: `SP-PROF-crt-m15-live` (PRODUCTION), `SP-PROF-parent-h4`
   (PRODUCTION), `SP-PROF-weekly-fx` (RESEARCH, F-042), `SP-PROF-visual-xau`
   (RESEARCH, F-081).
2. `src/structure/events.py` — `profile_id` / `program_id` / `predicate_versions` on every
   emitted event.
3. Back-reference: each affected finding's `evidence:` block in
   [`docs/current-findings.md`](docs/current-findings.md) gains
   `structure_profile: SP-PROF-…`, so F-042/F-081 stay exactly replayable.
4. Document the promotion path in
   [`docs/reference/governance.md`](docs/reference/governance.md): promoting a research
   structure = a profile lifecycle flip through the existing `APPROVE` gate. Grants no
   authority by itself (§6.5 — authority still requires measured ΔG001).

### SK-4 — Sequencing kernel (highest risk, last)
`src/structure/walk.py`. `StateMachine` and `ParentCRTTrack` become consumers of one walk
engine. Must preserve, without behavior change: shadow memory + TTL (F-068's
`pending_displacement_created_idx` fix), EXPANSION TTL/`EXPIRED` (Phase 3b), reset logic
(`retrace_reset_pct` / `extension_reset_fib` / HTF clock), sweep age, the soft-confirmation
window (including F-067's measured-not-fixed double EMA update — **preserved as-is**, since
changing it here would be an unauthorized behavior change), and the parent-bias join at
EXECUTION (CT-009).

**Gate (all required):** byte-identical trade ledger **and** event stream on every corpus a
live finding rests on — XAUUSD, BNB/ETH/BTC/SOL, the 5 FX majors — plus the XAUUSD
freeze-pin vector SHA, `SCHEMA_HASH`, and `FEATURE_ORDER_HASH` unchanged. Any divergence
stops the milestone.

> Note on corpus scope: standing preference is XAUUSD-only for *probes*. This is not a
> probe — it is a parity gate, and its whole purpose is to cover every corpus a registered
> finding depends on. Flagging the distinction rather than assuming it.

### SK-5 — Enforcement + policy supersession
1. Extend [`scripts/analysis/feature_math_lint.py`](scripts/analysis/feature_math_lint.py)
   to structural predicates, reusing its existing `durable_key` AST-fingerprint +
   append-only retirement manifest + monotonic ratchet (the F-047 mechanism). **A new local
   re-derivation of the sweep predicate then fails CI** — competing implementations become
   mechanically impossible, not merely discouraged.
2. Add a `state_calculators:` census to
   [`crt_object_relations.yaml`](docs/governance/crt_object_relations.yaml) listing all 9
   sites with `timeframe` / `vocabulary` / `authority` / `founding`, with
   `tests/test_crt_object_relations.py` asserting exhaustiveness.
3. Mark the module-level isolation policy **SUPERSEDED** (with reason and date) in
   `weekly_sweep/weekly_range.py` and `visual_crt/geometry.py` — §6.2 rule 4, never delete.
4. Register a finding: the arithmetic-vs-founding distinction, and that F-074 required a
   3-file manual broadcast.

---

## No loss of information — four explicit guarantees

1. **Behavioral.** Nothing is replaced until the replacement is proven byte-identical on
   the corpora that matter. A divergence is a **stop condition** and a `TruthConflict`
   (§6.2 rule 3) — never a silent reconcile. SK-1's predicates are pure, so their proof is
   exhaustive rather than sampled.
2. **Evidence.** Profiles are frozen and versioned, never edited in place. F-042 and F-081
   remain replayable via their `structure_profile:` back-reference. No finding's evidence
   chain is invalidated — which is precisely why the resolver's sequencing is left alone
   (folding it in would have invalidated F-069's baseline and every parity artifact built
   on it).
3. **Knowledge.** The existing docstrings encode real decisions — F-074's rationale,
   F-072's `atr_abs`-not-`atr` warning, the pool-visibility rule, the isolation precedent.
   These migrate into the ontology nodes' `semantics:` / `epistemic:` blocks. Deleting a
   docstring without rehoming its reasoning is the intelligence loss §6.1 names.
4. **History.** The superseded isolation policy, the 6-copy census, and the F-069
   divergence are all recorded as `SUPERSEDED` / registered nodes — append-discipline, not
   removal.

## Out of scope

No change to `ACTIVE_VERSION` or any active config's `params`. No re-enabling of
`rr_fusion`. No unification of `candle_state/encoder.py` or
`market_state_cluster_engine.py` (genuinely different vocabularies, not CRT).
`msip_1_verification_package/` is a frozen verification snapshot — **must not** be
migrated. Grants no production or G001 authority (§6.5).

## Verification

Per milestone:

```bash
python -m pytest tests/test_crt_object_relations.py tests/test_state_contracts.py tests/test_crt_state_invariants.py tests/test_state_topology_phase.py tests/test_crt_executable_state_graph.py tests/test_crt_adversarial_closure.py tests/test_directional_displacement.py tests/research/test_weekly_sweep.py tests/research/test_visual_crt_trade_object.py tests/test_parent_crt_track.py -q
```

```bash
python scripts/analysis/feature_math_lint.py && python scripts/governance/construction_protocol.py check
```

Byte-identity gate (SK-1 / SK-2 / SK-4) — XAUUSD ledger + freeze-pin vector SHA:

```bash
python -m src.runtime.backtest_v2 --instrument XAUUSD --data-dir data/mt5 --emit-ledger
```

Grounding for every new noun introduced (§6.7):

```bash
python scripts/governance/query_semantic_os.py --ground --kind NOUN --token SP-001
```
