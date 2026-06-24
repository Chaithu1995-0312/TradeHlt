# Config-First Doctrine — FROZEN into CLAUDE.md §6.5 (2026-06-15)

> **Status: FROZEN.** The normative doctrine now lives in `CLAUDE.md §6.5` (the always-loaded
> operating manual). This document is the **long-form companion + durable migration-evidence log**.
> It was promoted only after the freeze criterion was met: Batch A (4 live-spine migrations) proven
> byte-identical (BNBUSDT + SOLUSDT), `behavior_census.py` + test gate green, and the full
> determinism+oracle suite green (22 passed, post-migration == baseline). Sequence honored:
> **Practice → Evidence → Census → more Practice → Doctrine** — never Doctrine → Hope → Reality.

---

## 1. North star

The repository should evolve toward **Frozen Engine + Mutable Behavior + Governed Evolution**:

```
Code changes are rare.
Config changes are routine.
Goal-seeking becomes automated (by generating configs, not rewriting engines).
```

Behavioral magic numbers hidden in live-spine Python force a code edit (and bypass the
governance/hash/validation machinery) every time we want to tune. The doctrine moves *behavior*
into config while keeping *structure* frozen.

## 2. Classification framework (the lens for every change)

| Class | Examples | Action |
|---|---|---|
| **STRUCTURAL** | interfaces, dataclass fields, enum members, state-machine transitions, execution order, array/vector dims, ATR/EMA *kernel* periods that define feature shape | **Frozen.** Leave in code. Changing it is expensive — avoid unless unavoidable. |
| **BEHAVIORAL** | thresholds, percentiles, clamps, penalties, accept-rate targets, tier boundaries, multipliers, quotas, warn levels | **Externalize** to config (`cfg.*`), default == current literal. |
| **GOAL-SEEKING** | candidate-config generation, sweeps, optimization, promotion | Behavior is *generated as config*; the engine is untouched. |

## 3. Before writing code — the six questions

For every proposed change, ask: can this become **(1) configuration, (2) data, (3) a plugin,
(4) an interpreter, (5) a strategy module, (6) a policy?** If YES → do **not** modify the engine
logic; expose the behavior through configuration.

## 4. Implementation rules

1. Prefer config changes over code changes.
2. Prefer adding parameters over branching logic.
3. Preserve determinism, oracle parity, replay correctness, existing contracts.
4. Avoid duplicate systems; minimize structural entropy.
5. **FAIL-FAST, NO SILENT DEFAULTS.** Every config knob is read through a `_require`-style strict
   accessor that raises `KeyError` if the key is absent — never `.get(key, literal)`. A missing key
   is a config error to surface, not a value to guess. (A guessed default is precisely how config
   split-brain / F-018 arises.) The production config JSON MUST carry every knob.
6. **Parity proof.** Byte-identical ledger is guaranteed by *the JSON value equalling the prior
   hardcoded literal* + a strict read — not by a code-side default. No silent behavior drift.
7. Reuse existing infrastructure (`get_prod_section`, `_*_require`, `from_prod_config`); never
   invent a new config-loading pattern.

## 4b. Precedence & Authority (frozen 2026-06-15, mirrors CLAUDE.md §6.5)

**Precedence hierarchy:** `Evidence > Doctrine > Preference > Convenience > Elegance`. Corollaries:
**Evidence quality outranks migration quantity**; **never optimize using a measurement instrument
known to be biased** (e.g. the census external-injection blind spot — fix it before ranking on it);
**correcting the instrument often creates more value than optimizing the system** (Phase 3's census
repair shrank the backlog 45→7 and reframed Batch C from 30-knob surgery to a hash-neutral 12-field
config-completeness pass).

**Authority Ladder (anti-self-deception)** — generalizes beyond config (ties to §6.1 + the G001 /
Interpreter-Contract program). **Permanent invariant: evidence has no authority; only demonstrated
G001 improvement grants authority.** Four distinct states:

| Level | Meaning |
|---|---|
| Information exists | phenomenon detected |
| Economic usefulness exists | measurable ΔG001 benefit |
| Authority earned | allowed to influence production |
| Architecture justified | allowed to increase complexity |

Corollaries: Information ≠ value · Value ≠ authority · Authority ≠ architecture. A
`REGIME_EXPLOITABLE`-type finding = information (docs/research/shadow only, never sizing/fusion);
only a `CONSUMER_CANDIDATE` *with measured ΔG001* earns authority — and even then not new
architecture. **A knob becoming `CONFIG_DRIVEN` grants tunability, never authority.**

## 5. Proven patterns to copy (do not reinvent)

- Knob-wiring diff shape: commit **6e1048a (R2)** — `bitnet_main_threshold` + `feature_monitor`
  drift-Z. Config JSON key + construction-site wiring + parity proof. **Note:** R2 used a
  `get_prod_section(...).get(key, literal)` soft default; this doctrine supersedes that with a
  **strict fail-fast read** (rule 5) — the soft-default form is deprecated for new migrations.
- Factory: `from_prod_config()` (TrainingTrigger, SLTPComparator, KillSwitch …).
- Strict accessor: `_require`-family (engine_runner / decision_engine / execution_planner).

## 6. Migration log (per-knob evidence)

Each row: constant → config key → parity verdict (ledger byte-identical?) → notes. *Populated as
migrations land.*

Parity baseline (pre-migration, capped 45k candles): **BNBUSDT** `f61b44ea…e4e9` (11 trades,
pf 1.0202) · **SOLUSDT** `d2721c2c…b591d` (5 trades, pf 0.1785).

| # | Module | Constant(s) → config key(s) | Section | Ledger parity | Verdict |
|---|---|---|---|---|---|
| A1 | `core/dynamic_threshold.py` · `core/decision_engine.py` | `_THRESHOLD_PERCENTILE`→`threshold_percentile` (85), `_THRESHOLD_MIN`→`threshold_min` (0.45), `_THRESHOLD_MAX`→`threshold_max` (0.65) | `decision_engine` | **byte-identical** BNB+SOL (hashes unchanged) | DONE — ledger-affecting path, fail-fast wired; resolved the `dynamic_threshold` doc/code split-brain (header claimed config-driven, code was hardcoded) |
| A2 | `core/regime_governor.py` | `MAX_TRADES_PER_BATCH`, `REGIME_PENALTY`, `REGIME_ACCEPT_PERCENTILE`, `DIRECTION_PENALTY`, `FALLBACK_THRESHOLD`, `WINDOW_MIN_SAMPLES`, `WINDOW_MAXLEN` → same-named keys | `regime_governor` (new) | **byte-identical** BNB+SOL | DONE — `from_prod_config()` fail-fast; INERT on active config (`ultron_gate_enabled=false`) → knobs currently dormant (recorded evidence, not hidden) |
| A3 | `core/convergence_controller.py` | `_WARMUP_BARS`, `_THRESH_{MIN,MAX,STEP}`, `_ACCEPT_RATE_{HIGH,LOW}`, `_ABS_QUALITY_FLOOR`, `_SIG_K/_SIG_T`, penalty-sigmoid `8.0/0.5` → `warmup_bars`/`thresh_*`/`accept_rate_*`/`abs_quality_floor`/`sig_*`/`penalty_sig_*` | `convergence_controller` (new) | **byte-identical** BNB+SOL | DONE — `from_prod_config()` fail-fast; convergence/evaluate path gated by `fusion_use_evaluate=false` → effectively dormant on active config |
| A4 | `core/acceptance_controller.py` | `_THETA_MIN`, `_THETA_MAX`, `_MIN_HISTORY`, hardcoded `np.percentile(...,85)` → `theta_min`/`theta_max`/`min_history`/`fusion_percentile` | `acceptance_controller` (new) | **byte-identical** BNB+SOL | DONE — `from_prod_config()` fail-fast injects strict knobs into base config |
| A5 | `core/model_registry.py` | `PROMOTION_MARGIN=0.02` → `promotion_margin` | `governance` | N/A to ledger (GOV-3 promotion gate, off the per-bar spine) — parity = value unchanged (singleton reads 0.02) + 91 model_registry/promotion tests green + determinism spot-check | DONE — chosen by *evidence-guided prioritization* (Phase 3), the cleanest genuine HARD_CODED (low blast, hash-neutral); `from_prod_config()` fail-fast eager singleton |

**Combined A1–A4 parity proof:** capped 45k-candle ledger SHA-256 unchanged vs. baseline —
BNBUSDT `f61b44ea…e4e9` (11 trades, pf 1.0202), SOLUSDT `d2721c2c…b591d` (5 trades, pf 0.1785).
Unit tests: 118 green across the five modules; census + reachability gates green (no DEAD keys).

### Phase 3 — sharpened census + re-ranking (2026-06-15)
The census was **over-reporting HARD_CODED** (external-injection blind spot): it only saw config
reads *inside the same file*, so config-schema classes built by an external constructor looked
hardcoded. WI-1 added (a) a corpus-wide config-key-read scan and (b) a curated
`_CONFIG_SCHEMA_CLASSES = {CRTConfig, FusionConfig}`; output/`*Result` field defaults are now
STRUCTURAL placeholders. **Effect: future config opportunities 45 → 7; HARD_CODED 6 → 5.** Major
correction: `crt_engine_v2.py`'s "27" = **24 externally-wired CRTConfig fields + 3 genuine** state
defaults — so **"Batch C" is a config-*completeness* task (populate the active JSON `params`/
`crt_engine` + rehash), NOT engine surgery** (the code already reads CRTConfig from config).

**Trustworthy HARD_CODED residue (the real backlog):** `model_registry.PROMOTION_MARGIN` (DONE,
A5) · `crt_engine_v2` 3 state defaults (`decay_factor`, `risk_pct`, `soft_conf_candles`) ·
`signal_audit._TRADE_RATE_WARN` (advisory) · `signal_belief_tracker._DEFAULT_DECAY` (sidecar) ·
`hierarchical_meta_fusion._DEFAULT_WEIGHTS` (DORMANT F-012, skip). Census enforcement extended:
`tests/test_behavior_census.py` now also asserts `fusion_engine.py` is NOT HARD_CODED.

### Phase 4 — Batch C: CRT config-completeness (2026-06-15)
Reframed by Phase 3's instrument repair: NOT engine surgery, NOT a rehash. The CRT *code* already
reads `CRTConfig` from config; the gap was **12 CRTConfig fields absent from `crt_engine`+`params`**,
silently falling back to dataclass defaults (the F-018 CRT split-brain). **WI-C1:** populated all 12
into the `crt_engine` section with `value == current dataclass default` — incl. the **load-bearing
`exit_model='intrabar_touch'`** (previously implicit). **Hash-neutral, no rehash** (owner decision):
`crt_engine` is the architecture's *defaults* layer; the hash protects `params` (tuned overrides).
`allowed_sessions` deliberately EXCLUDED (engine_runner-owned via `resolve_allowed_sessions`).
**Parity:** byte-identical BNB+SOL ledger (config now explicit; behavior unchanged). **WI-C2:** the 3
state defaults reclassified STRUCTURAL in the census (runtime placeholders; their real knobs
`score_decay_lambda`/`sizing_bands`/`soft_conf_max_candles` are already config-driven) →
`crt_engine_v2.py` genuine HARD_CODED 3→0 → CONFIG_WIRED.

**Backlog after Batch C:** census `HARD_CODED 3` / `future opportunities 3` — all
advisory/sidecar/dormant (`signal_audit`, `signal_belief_tracker`, `hierarchical_meta_fusion`). Every
live, behavior-affecting CRT/spine knob is now config-driven. The config-first migration program has
reached its meaningful end; remaining items are explicitly low-value/skip.

## 7. Freeze criterion (when this becomes CLAUDE.md doctrine)

Promote §2–§4 into CLAUDE.md only when **all** hold:
- ≥4 live-spine modules migrated, each proven byte-identical (BNBUSDT + SOLUSDT).
- `behavior_census.py` exists and its test gate is green (zero remaining BEHAVIORAL-hardcoded in
  the migrated modules).
- No new reds in the determinism / oracle-parity / reachability suites vs. the `patch` baseline.

## 8. Required deliverables

### Structural changes (and why unavoidable)
**None to interfaces/contracts/schemas/state-machines.** The only signature changes are
*additive constructor surface*, each backward-compatible:
- `DynamicThreshold.__init__` gains required keyword-only `percentile/t_min/t_max` (the values it
  cannot function without; previously module constants).
- `RegimeGovernor.__init__` gains optional `config`; `ConvergenceController.__init__` gains
  keyword-only knob params (canonical defaults); `AcceptanceController` unchanged signature.
- Three classes gain a `from_prod_config()` classmethod (the strict production boundary).
No dataclass field added, no `CRTConfig`/enum/`VALID_TRANSITIONS` change, no execution-order
change. `params` block untouched → **config hash unchanged, no rehash**.

### Config changes (key · default · purpose · future automation)
`decision_engine`: `threshold_percentile`=85, `threshold_min`=0.45, `threshold_max`=0.65 —
adaptive-threshold percentile + clamp band. *Automation:* sweep band per instrument/regime.
`regime_governor` (new): `max_trades_per_batch`=3, `regime_penalty`/`regime_accept_percentile`
(per-regime dicts), `direction_penalty`=0.1, `fallback_threshold`=0.45, `window_min_samples`=10,
`window_maxlen`=100 — Step-6 signal-quality gate. *Automation:* regime-conditional penalty search
(only once `ultron_gate_enabled` is turned on).
`convergence_controller` (new): `warmup_bars`=10, `thresh_min`=0.3, `thresh_max`=0.9,
`thresh_step`=0.02, `accept_rate_high`=0.3, `accept_rate_low`=0.1, `abs_quality_floor`=0.3,
`sig_k`=8.0, `sig_t`=0.6, `penalty_sig_k`=8.0, `penalty_sig_t`=0.5 — fusion stability layer.
*Automation:* calibrate sigmoid + accept-rate band once `fusion_use_evaluate` is on.
`acceptance_controller` (new): `theta_min`=0.5, `theta_max`=0.95, `min_history`=10,
`fusion_percentile`=85 — adaptive acceptance bounds. *Automation:* target-acceptance-rate tuning.

### Hardcoded constants remaining (with reason)
Census (`behavior_census.py`): **BEHAVIORAL 67 · STRUCTURAL 4 · GOAL_SEEKING 9 · UNCLASSIFIED 55**,
**45 future config opportunities**. The migrated 4 modules are clean (regression gate green). The
remaining 67 behavioral literals are out of THIS batch's scope by design:
- Canonical defaults kept in the migrated modules as constructor-signature/None-sentinel fallbacks
  for unit-test/standalone construction — the *live* path always overrides them via
  `from_prod_config` (verified config-wired). Not runtime constants.
- Behavioral constants in **dormant/sidecar** modules (`hierarchical_meta_fusion`,
  `signal_belief_tracker`, etc.) — migrating dead code is config-first theater (F-012/F-013);
  deferred until/if those modules join the spine.
- The **CRTConfig split-brain (~30 knobs in `params`)** — Batch C, deferred: touches `params` →
  requires rehash, higher blast radius.

### Future config opportunities
Auto-derived: see `docs/research-readiness/behavior-census-report.md` →
*Future config opportunities* (BEHAVIORAL constants in non-config-wired live modules). Top
candidates for the next batch: `core/convergence_controller` residuals already done; next is the
`crt_gaussian_scorer` hard-filter bounds + `decision_engine` `_FALLBACK_TOP_N` family, then Batch C.

### Self-review
- **Assumptions:** every live `DecisionEngine`/controller construction path carries its config
  section (verified: backtest merges `decision_engine` at `backtest_v2.py:1843`; live merges it at
  `live_engine_hook.py:230`; the three new sections reach the controllers via `from_prod_config`).
- **Invariants preserved:** four-engine completeness, no-lookahead, frozen `CRTConfig` fields,
  determinism, oracle parity, strict-accessor fail-fast (now extended, not weakened).
- **Edge cases:** missing section/key → `from_prod_config`/`_require_decision_cfg` raises
  (fail-fast, no silent default — the doctrine's core rule). Bare/partial-config test construction
  → canonical defaults, byte-identical to prior behavior.
- **Failure modes:** a wrong JSON value would change the ledger → caught by the byte-identical
  fingerprint gate. A missing key in production → hard crash at construction (intended).
- **Tests added/updated:** `tests/test_behavior_census.py` (new gate); `tests/test_crt_fixes.py`
  updated for the required `DynamicThreshold` params. 118 module tests green; 6 census/reachability
  green.
- **Oracle/parity & determinism risks:** LOW — proven byte-identical on BNB+SOL for A1 alone and
  A1–A4 combined; A2/A3 inert on the active config (`ultron_gate_enabled`/`fusion_use_evaluate`
  false), A4 bounds unchanged.
- **Structural entropy:** *decreased* — removed the `dynamic_threshold` doc/code split-brain;
  added one analysis script mirroring `config_reachability.py`; no new abstraction or duplicate
  system.
- **Pre-existing unrelated red:** `test_gaussian_impl_switch::test_engine_runner_ml_impl` (ML
  engine deps absent → heuristic fallback) — untouched by this work.
