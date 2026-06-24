# Config-First Migration — Practice → Evidence → (later) Doctrine

## Context

**Why this change.** The owner wants the repo to evolve toward *Frozen Engine + Mutable
Behavior + Governed Evolution*: code changes become rare, config changes become routine,
goal-seeking happens by generating configs rather than rewriting engines. Behavioral magic
numbers (thresholds, periods, weights, multipliers, percentiles) currently live as hardcoded
constants inside **live-spine** Python, which means tuning requires code edits and bypasses the
governance/hash/validation machinery.

**Explicit constraint from the prompt.** Do **NOT** add the doctrine to `CLAUDE.md` yet. First
*implement* the philosophy across several live-spine migrations, *prove* it with the existing
determinism / oracle-parity / reachability gates, and only later freeze the doctrine. The
sequence is **Practice → Evidence → Census → more Practice → Doctrine**, never Doctrine → Hope →
Reality.

**Scope decisions (confirmed with owner).**
- Batch A = 4 live-spine modules migrated to config, each proven byte-identical.
- Batch B = build a reusable classifier/census tool (`behavior_census.py`) + a test gate — the
  "evidence engine."
- Batch C (CRT split-brain / ~30 CRTConfig knobs in `params`, requires rehash) is **out of scope
  here** — higher blast radius, deferred to a later, separate change.
- CLAUDE.md is untouched. A *staging* doctrine doc is written instead.

**What already exists and must be reused (do not reinvent):**
- Config load/access: `get_prod_config()`, `get_prod_section()`, `get_active_version()` in
  [production_config.py](src/config_layer/production_config.py). `get_prod_section` fail-fasts on a
  missing section.
- Strict accessors: `_cfg_require()` ([engine_runner.py:112](src/core/engine_runner.py)),
  `_require_decision_cfg()` ([decision_engine.py:63](src/core/decision_engine.py)),
  `_planner_require()` ([execution_planner.py:122](src/core/execution_planner.py)).
- Factory convention: `from_prod_config()` classmethod with graceful default fallback
  (`TrainingTrigger`, `SLTPComparator`, `KillSwitch`, …).
- The exact "wire a hardcoded knob → config" pattern landed in commit **6e1048a (R2)** for
  `bitnet_main_threshold` + `feature_monitor` drift-Z. **Replicate that diff shape.**
- Reachability tooling: [config_reachability.py](scripts/analysis/config_reachability.py) +
  [tests/test_config_reachability.py](tests/test_config_reachability.py).
- Parity/determinism gates that MUST stay green:
  [test_replay_determinism.py](tests/runtime/test_replay_determinism.py),
  [test_metrics_oracle_parity.py](tests/analytics/test_metrics_oracle_parity.py),
  [test_golden_ledgers.py](tests/analytics/test_golden_ledgers.py).

**Hash discipline.** The config hash covers the `params` block only. Batch A touches **only
top-level non-`params` sections** (existing `decision_engine` + three new sections), so it is
**hash-neutral — no rehash required**. This is a deliberate scope boundary; anything needing a
rehash belongs to Batch C.

---

## Classification framework (the lens for every change)

Each constant is labeled before action:

| Class | Examples | Action |
|---|---|---|
| **STRUCTURAL** | interfaces, dataclass fields, enum members, state-machine transitions, execution order, array/vector dims, ATR/EMA *kernel* periods that define the feature shape | **Frozen.** Leave in code. |
| **BEHAVIORAL** | thresholds, percentiles, clamps, penalties, accept-rate targets, tier boundaries, multipliers, quotas, warn levels | **Externalize** to config (`cfg.*`), default == current literal. |
| **GOAL-SEEKING** | candidate-config generation, sweeps, optimization, promotion | Out of scope here; behavior is *generated as config*, engine untouched. |

Rule applied to every candidate: *Can this become configuration / data / a policy?* If yes →
do not modify the engine logic; expose the value through config.

---

## Batch A — four live-spine migrations (hash-neutral)

**Liveness verified:** `engine_runner.py` imports `SignalAuditRecorder`, `AcceptanceController`,
`ConvergenceController`, `UltronGovernor`/`RegimeGovernor` ([engine_runner.py:32-41](src/core/engine_runner.py));
`decision_engine.py` uses `DynamicThreshold` ([decision_engine.py:25,99,123](src/core/decision_engine.py)).
These are spine-imported, not dormant sidecars (contrast cognitive_bus/HMF, F-012).

**Per-module migration recipe (identical shape, mirrors R2 commit 6e1048a):**
1. Add the knob(s) to the target config section in
   [configs/production/v2_multi_2026_04.json](configs/production/v2_multi_2026_04.json), value ==
   current hardcoded literal.
2. Constructor gains typed params with defaults == current literals; the class uses
   `self.<knob>` instead of the module constant. (Keep the module constant only as the default
   source if convenient, or delete once unused.)
3. The construction site (engine_runner / decision_engine) wires values from
   `get_prod_section("<section>")` with `.get(key, <literal>)` defensive fallback + explicit
   `int()/float()` cast — exactly the `FeatureMonitor` wiring in
   [backtest_v2.py:1426](src/runtime/backtest_v2.py).
4. Prove byte-identical ledger + oracle parity (see Verification).

### A1 — `dynamic_threshold.py` → existing `decision_engine` section  *(flagship)*
- Constants ([dynamic_threshold.py:19-21](src/core/dynamic_threshold.py)): `_THRESHOLD_PERCENTILE=85`,
  `_THRESHOLD_MIN=0.45`, `_THRESHOLD_MAX=0.65`. The file header **already claims** these are
  "tuned via …→ decision_engine" but they are never read — a documented-but-unwired split-brain
  (DOC_DRIFT / F-018 symptom). Fixing it also resolves that TruthConflict.
- Wire: `DynamicThreshold.__init__(window, percentile=85, t_min=0.45, t_max=0.65)`; `compute()`
  uses `self._percentile/_min/_max`. `DecisionEngine.__init__` passes them from its already-present
  `self.config` via `_require_decision_cfg`-style reads (add keys `threshold_percentile`,
  `threshold_min`, `threshold_max` to the `decision_engine` JSON). Pattern already proven in-file
  by `_FALLBACK_TOP_N` ([decision_engine.py:38,101](src/core/decision_engine.py)).
- New keys: `decision_engine.threshold_percentile=85`, `.threshold_min=0.45`, `.threshold_max=0.65`.

### A2 — `regime_governor.py` → new `regime_governor` section
- Constants ([regime_governor.py:103-120](src/core/regime_governor.py)): `MAX_TRADES_PER_BATCH=3`,
  `REGIME_PENALTY` dict, `REGIME_ACCEPT_PERCENTILE` dict, `DIRECTION_PENALTY=0.10`,
  `FALLBACK_THRESHOLD=0.45`, `WINDOW_MIN_SAMPLES=10`, `WINDOW_MAXLEN=100`.
- Add `RegimeGovernor.from_prod_config()` (matches existing factory convention); engine_runner uses
  it. New top-level `regime_governor` section carries the dicts/scalars verbatim.
- `WINDOW_MAXLEN`/`WINDOW_MIN_SAMPLES` are borderline STRUCTURAL (buffer geometry) — classify in
  the doc; still externalizable as behavior since they change accept dynamics. Default == literal.

### A3 — `convergence_controller.py` → new `convergence_controller` section
- Constants ([convergence_controller.py:39-58](src/core/convergence_controller.py)): `_WARMUP_BARS=10`,
  `_THRESH_MIN/MAX/STEP=0.30/0.90/0.02`, `_ACCEPT_RATE_HIGH/LOW=0.30/0.10`,
  `_ABS_QUALITY_FLOOR=0.30`, `_SIG_K/_SIG_T=8.0/0.6`.
- Constructor params + `from_prod_config()`; new section verbatim.

### A4 — `acceptance_controller.py` → new `acceptance_controller` section
- Constants ([acceptance_controller.py:34-38](src/core/acceptance_controller.py)): `_THETA_MIN=0.50`,
  `_THETA_MAX=0.95`, `_MIN_HISTORY=10`.
- Constructor params + `from_prod_config()`; new section verbatim.

**Expected-finding note.** If a module turns out to be constructed-but-inert on the spine, the
byte-identical proof passes trivially — that is itself evidence (the knob is currently inert) and
will be recorded per module in the migration log, not hidden.

---

## Batch B — `behavior_census.py` (the evidence engine)

New tool, sibling to `config_reachability.py`:
- **Path:** `scripts/analysis/behavior_census.py`.
- **Input:** live-spine source under `src/core/`, `src/engines/`, `src/config_layer/` (exclude
  `src/research/`, `scripts/`, `tests/`, dormant sidecars).
- **Output:** JSON + Markdown report under `docs/research-readiness/` classifying each module's
  numeric/behavioral literals into `STRUCTURAL` / `BEHAVIORAL` / `GOAL_SEEKING`, plus a
  `BEHAVIORAL` + still-hardcoded list = the "Future Config Opportunities" deliverable. Shape:
  ```json
  { "src/core/dynamic_threshold.py": { "behavioral": ["_THRESHOLD_PERCENTILE=85"], "structural": [], "goal_seeking": [] } }
  ```
- **Method:** AST walk for module/class-level numeric assignments; a small curated allow/deny
  classifier (structural names: `*_period`, `*_dim`, `maxlen`, enum/transition tables; behavioral
  names: `*_threshold`, `*_pct`, `*_penalty`, `*_weight`, `*_min/_max`, `percentile`). Deterministic
  output (sorted keys) so the report is reproducible.
- **Test gate:** `tests/test_behavior_census.py` — (a) tool importable & runs; (b) report has the
  expected verdict shape; (c) **regression floor:** the four Batch-A modules report **zero
  remaining BEHAVIORAL-hardcoded** constants (proves the migration and prevents backsliding).
  Mirror [test_config_reachability.py](tests/test_config_reachability.py).

---

## Staging doctrine doc (NOT CLAUDE.md)

- **Path:** `docs/research-readiness/config-first-doctrine.md`, clearly headed *"STAGING — not yet
  frozen into CLAUDE.md."*
- Contents: the classification framework table above; the "before writing code" checklist; the
  per-module **migration log** (constant → config key → parity hash → verdict); the Required
  Deliverables below; the freeze criterion (*after N≥? successful migrations + green census gate,
  promote to CLAUDE.md*).
- Cross-link from [docs/current-findings.md](docs/current-findings.md) only if a finding flips
  (e.g., the dynamic_threshold split-brain resolved); otherwise no findings change.

---

## Required deliverables (produced into the staging doc)

1. **Structural changes** — list every interface/dataclass/contract modified and *why
   unavoidable* (expected: none; only constructor signatures gain optional params with defaults).
2. **Config changes** — every new key: default value, purpose, future-automation opportunity.
3. **Hardcoded constants remaining** — every magic number left, with the reason it can't yet be
   externalized (e.g., structural kernel period, dormant module out of scope).
4. **Future config opportunities** — auto-derived from `behavior_census.py`.
5. **Self-review** — assumptions, invariants preserved, edge cases, failure modes, tests added,
   oracle/parity risks, determinism risks, structural entropy introduced.

---

## Verification (end-to-end)

Run after **each** Batch-A migration (parity must hold per knob), and again after the full batch:

1. **Determinism / byte-identical ledger** (the parity proof):
   `pytest tests/runtime/test_replay_determinism.py -v` — ledger + all artifacts byte-identical
   pre/post on BNBUSDT **and** SOLUSDT (two instruments, not CSV-specific).
2. **Oracle parity:** `pytest tests/analytics/test_metrics_oracle_parity.py tests/analytics/test_golden_ledgers.py -v`.
3. **Reachability:** `python scripts/analysis/config_reachability.py` — new keys classify
   `READ_AND_USED`, zero `DEAD`; `pytest tests/test_config_reachability.py`.
4. **Census gate:** `python scripts/analysis/behavior_census.py` + `pytest tests/test_behavior_census.py`
   — the four migrated modules show zero remaining BEHAVIORAL-hardcoded.
5. **Full suite sanity:** `pytest` (expect no NEW reds vs. the documented `patch` baseline of
   pre-existing fails; branch-scoped TP3/v4 skips remain skipped).
6. Capture the two ledger SHA-256s in the migration log + (when committed) the commit message,
   exactly as R2 did.

**Self-document:** append a `📝 SESSION LOG ENTRY` to `assistant_project.md` (CLAUDE.md §6) and
write/refresh a `project`-type memory file for the Config-First migration per the Memory mandate.

---

## Self-review (plan-level)

- **Assumptions:** the four modules are live-imported (verified); defaults == literals guarantees
  parity; touching only non-`params` sections is hash-neutral (verified: hash = params-only).
- **Invariants preserved:** four-engine completeness, no-lookahead, frozen `CRTConfig` *fields*
  (no new dataclass fields in Batch A), strict-accessor fail-fast, determinism, oracle parity.
- **Edge cases:** missing config section → `get_prod_section` raises (fail-fast) OR `.get(default)`
  fallback == literal (chosen: defensive fallback, matching R2); inert module → trivial parity pass
  (recorded).
- **Failure modes:** a knob that *does* change the ledger → determinism test fails → that knob's
  JSON default was wrong; fix to match literal. No silent drift possible (gate is byte-identical).
- **Oracle/parity & determinism risks:** LOW — values unchanged by construction; the gates are the
  proof. Risk concentrated in A1 (ledger-affecting); A2-A4 may be inert (still valid evidence).
- **Structural entropy introduced:** MINIMAL — no new abstractions; new config sections follow the
  existing section pattern; one new analysis script mirroring `config_reachability.py`. Net entropy
  *decreases* (removes the dynamic_threshold doc/code split-brain).
