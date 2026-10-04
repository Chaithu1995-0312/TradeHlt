# Trade-Intent Caller Census V1 — `cached_features` producer vs its consumers

**Date:** 2026-09-16 · **Class:** `OBSERVATION_ONLY` · **Instrument:** XAUUSD M15 (47,197 bars)
**Authority granted:** none. No G001, no finding registered, no config/registry/ledger change.

> Point-in-time snapshot, not a living doc. `docs/analysis/` is **not** scanned by
> `tests/test_doc_citations.py` (that test covers `docs/architecture`, `docs/reference`,
> `docs/topics`), so the `path:line` citations below are hand-verified, not gate-enforced.
> Re-verify before building on them.

## Why this exists

The schema-v6 rename (`CH-schema-v6-normalization-identity`) left a note at
`crt_engine_v2.py:2336` stating that the `pullback` branch of
`ExecutionEngine._derive_trade_intent` is unreachable because `candles_since_sweep` is never present
in `cached_features`. That is true but too narrow to act on, and acting on it as written would have
been wrong. The question this census answers is the one that comes before any fix:

> Is the runtime intent path **deliberately restricted**, or **accidentally starved**?

Answer: accidentally starved — but the remedy is not "add the missing keys."

## 1. The producer

`cached_features` is **not** a feature vector and is not produced by `FeaturePipeline`. It is a
snapshot the CRT state machine takes at one instant — retest confirmation — built at exactly two
sites inside `try_expansion_to_retest`:

| Site | Shape | When |
|---|---|---|
| `crt_engine_v2.py:1764` | 3 keys, all `0.0` | unconditional floor |
| `crt_engine_v2.py:1781` | 6 keys, populated | only if `disp is not None and _atr > 0 and abs(disp.close - disp.open) > 0` |

Values come from the formula registry, not local math: FM-027 `displacement_retrace`
(`derived_math.py:162`), FM-028 `displacement_atr_ratio` (`derived_math.py:179`), and the FM-010
`body_ratio` **of the displacement candle** (`Candle` property).

Lifecycle: created at RETEST → `None` on every reset (`crt_engine_v2.py:1930`) → copied onto the
`Trade` at build time (`crt_engine_v2.py:2453`) so it outlives that reset. Consumers never mutate
it; the BitNet path adds `atr` and `candles_since_retest_state` to a `.copy()`
(`crt_engine_v2.py:2148`).

## 2. The vocabulary mismatch (the actual finding)

`_derive_trade_intent` (`crt_engine_v2.py:2321`) reads **seven** keys. The cache supplies **four**
of the names it looks for. Measured against `CANONICAL_FEATURES` (schema v6.0, 48 names):

| Key the function reads | In cache? | Canonical? |
|---|---|---|
| `sweep_detected` | no | **yes** |
| `double_sweep` | yes | yes |
| `displacement_retrace` | yes | **no** |
| `retest_depth` (legacy fallback) | no | **yes** |
| `candles_since_sweep` | no | **yes** |
| `momentum_score` | no | **yes** |
| `body_ratio` | yes | yes |
| `displacement_atr_ratio` | yes | **no** |
| `disp_strength` (legacy fallback) | no | **yes** |

Every name the function reads is **canonical except the two it actually receives from the cache**.
Inverted: of the cache's six keys, only `body_ratio`, `session` and `double_sweep` are canonical;
`displacement_retrace`, `displacement_atr_ratio` and `retest_index` are CRT-local.

The function speaks the canonical (pipeline) vocabulary. The cache speaks a CRT-local vocabulary.
They overlap on exactly **`body_ratio` and `double_sweep`**. The two FM keys reach the function only
through the CH-002 fallback chains (`:2330-2334`, `:2349-2354`), which were added to bridge that
gap — for the two keys that had an FM counterpart. The three with no counterpart were never bridged
and silently hold their defaults.

Consequences, both structural:

- `pullback` fails on **two independent conditions** — `csr == 99` (never `<= 5`) and `mom == 0.0`
  (never `> 0`). Binding one key would not make it reachable.
- `liq_sweep` rests entirely on `double_sweep`, because `sweep_detected` is absent.

## 3. Two classifiers, one per rail

`ExecutionPlannerV1_2._derive_intent` (`execution_planner.py:331`) is a twin with byte-identical
thresholds and priority order, but it reads the **nine canonical names** — including all three the
cache lacks.

| | `ExecutionEngine._derive_trade_intent` | `ExecutionPlannerV1_2._derive_intent` |
|---|---|---|
| pullback test | `0.3<=rd<=0.7 and csr<=5 and mom>0` | `0.3<=retest_depth<=0.7 and candles_since_sweep<=5 and momentum_score>0` |
| breakout test | `body>0.6 and disp>thr` | `body_ratio>0.6 and disp_strength>thr` |
| reads | canonical names + FM fallbacks | canonical names, no fallback |
| fed by | the 6-key CRT cache (`:2415`) | the canonical feature dict (`live_engine_hook.py:1024`) |

**The two are rail-disjoint** — neither rail runs both:

- Backtest rail reaches the CRT classifier and never the planner. Self-documented in source:
  `backtest_v2.py:2581` — *"backtest_v2 does not import ExecutionPlannerV1_2 or UltronRiskGate"*.
- Live rail reaches the planner (`live_engine_hook.py:23, :1024`) and has no CRT `ExecutionEngine`
  import at all. Consistent with F-103.

So they are not redundant implementations. Each is its rail's **only** intent classifier, and the
CRT rail's is the starved one.

## 4. Caller census

| Caller | Input object | Vocabulary | `pullback` |
|---|---|---|---|
| `crt_engine_v2.py:2415` — runtime `build_trade` | `state.cached_features or {}` | CRT-local, 6 keys | **unreachable** |
| `scripts/analysis/p4_execution_intent_attribution.py:91` | `state.cached_features or {}` | CRT-local | unreachable |
| `scripts/analysis/p3c1_build_trade_audit.py:143` | `cached_feats` | CRT-local | unreachable |
| `scripts/analysis/crt_episode_number_trace.py:641` | `state.cached_features or {}` | CRT-local | unreachable (faithful mirror of runtime) |
| `scripts/research/build_bar_matrix.py:299` | pipeline feature row | canonical, all 9 | 2,767 (see §5 caveat) |
| `scripts/research/promotion_dryrun.py:104` | hardcoded fixture | **canonical** | no (`csr=9`, `mom=0.0` by fixture design) |
| `scripts/research/live_path_replay.py:439` | — replaces the method by monkeypatch | n/a | n/a |
| `tests/test_breakout_disp_threshold.py`, `tests/test_execution_contract_v1.py` | fixtures | — | — |
| `msip_1_verification_package/.../crt_engine_v2.py:1980` | frozen verification copy | — | not live |

Two rows carry extra weight:

- **`promotion_dryrun.py:104`** exists specifically to assert that the CRT classifier and the
  planner classifier agree — and its fixture is written in **canonical** vocabulary
  (`retest_depth`, `disp_strength`, `candles_since_sweep`, `momentum_score`, `sweep_detected`).
  A parity test proves the intended contract is one vocabulary, and it chose the canonical one.
- **`p4_execution_intent_attribution.py:154-155`** guards its own reads with
  `float(feats.get("retest_depth", 0.0)) if "retest_depth" in feats else None`. The author observed
  the absence and wrote `None`-guards around it rather than treating it as a defect.

## 5. Gate dominance — no single key is load-bearing

Measured on `results/research/bar_matrix/XAUUSD_M15/bar_matrix.parquet` (schema v6.0). `liq_sweep`
short-circuits first and claims 8,939 rows; the funnel below runs on the remaining **38,258**:

| cumulative condition | rows | removed by this gate |
|---|---|---|
| `0.3 <= rd <= 0.7` | 7,784 | — (20.3% of remainder) |
| `+ csr <= 5` | 5,381 | 2,403 |
| `+ mom > 0` | **2,767** | 2,614 |

Marginal pass rate of each gate **alone**: rd band **20.3%**, `csr<=5` 45.9%, `mom>0` 52.0%.

The retest-depth band is the dominant gate, not either missing key, and the two missing keys remove
comparable amounts. Reported `trade_intent` counts on the same file: reversal 34,295 · liq_sweep
8,939 · pullback 2,767 · breakout 1,196.

**Caveat — these two callers are not comparable.** The bar matrix has **no**
`displacement_retrace` and **no** `displacement_atr_ratio` column, so in that path `rd` and `disp`
resolve through the legacy fallbacks to FM-021 `retest_depth` and FM-020 `disp_strength` —
different quantities from the FM-027/FM-028 the cache supplies — and its `body_ratio` is the
**current bar's**, not the displacement candle's. The 2,767 measures the canonical-vocabulary
classifier. It is **not** "what the runtime would have produced."

## 6. Same class elsewhere

- **`gate_intelligence`** (`src/core/gate_intelligence.py:213-219`, constructed at
  `execution_planner.py:247`) reads `body_ratio`, `disp_strength`, `retest_depth`,
  `candles_since_sweep`, `momentum_score`, `sweep_detected`, `double_sweep` — canonical vocabulary.
  On the live rail it receives the canonical dict, so it is **fed correctly**; it is only the CRT
  rail that has no path to it. Not a second F-065 instance. (F-065 itself — `volume_ma20` →
  `vol_score` structurally 0.0 — is a different mechanism and remains OPEN.)
- **`fusion_engine.py:234`** documents its input as "raw `cached_features` dict from crt_engine_v2
  (may include `atr_vol`)". **No build site writes `atr_vol`.** Repo-wide, `atr_vol` appears in
  exactly two places: that docstring, and `scripts/misc/trade_replay_validator.py:333`, which reads
  it off a *trade journal row*, not off `cached_features`. The docstring claim is unsupported —
  `DOCUMENTATION GAP`, no behaviour attached.
- **`CRTGaussianScorer.compute`** (`src/config_layer/crt_gaussian_scorer.py:74`) is the **only**
  consumer whose docstring enumerates the cache's real keys, `retest_index` included — and the only
  one that works unaided. It was authored against the producer.

## 7. Determination

Per §6.8, closing on exactly one: **`TEST / CONTRACT GAP`.**

`cached_features` is a producer that was never contracted against its consumers' declared
vocabulary, and no test compares the two. Not `CONFIRMED DEFECT`: the live rail's planner classifies
intent correctly on the canonical dict, and nothing that was ever validated depends on the CRT
rail's classifier reaching `pullback`. Not `INTENTIONAL SEMANTIC SEPARATION`: a deliberate
restriction would not have duplicated the dead conditions verbatim in both classifiers, and would
not be contradicted by a parity test written in the other vocabulary.

Scenario mapping: this is **contract mismatch**, with direction identified —
`_derive_trade_intent` was authored against the canonical vocabulary and later wired to the
CRT-local cache.

**No finding registered.** The evidence establishes the mismatch but not who should own intent on
the CRT rail, and a `TEST / CONTRACT GAP` on that evidence does not earn an F-id.

Git archaeology cannot date any of this: the only commits touching the cache build site are the
F-071 squashed restoration (`5897209 "commit"`, `b34d6a8 "stable before rename"`).

## 8. Open, and explicitly not authorized here

1. **Who owns intent on the CRT rail?** Either bind the cache to the canonical vocabulary, or delete
   the CRT classifier and let the planner own intent (the F-048 treatment, where the DecisionEngine
   RR gate was removed rather than repaired). This is an **ownership adjudication**, not a
   missing-key fix.
2. Wiring `sweep_detected` / `candles_since_sweep` / `momentum_score` into `cached_features` would
   change `tp1_atr_multiplier_<intent>` selection and therefore the trade ledger. It needs its own
   authorization and a measured ΔG001 (§6.5). §5 gives no reason to expect it to pay.
3. `fusion_engine.py:234`'s `atr_vol` docstring claim — corrected here, not in source.

## 9. Shadow measurement of option C (2026-09-16)

User selected **option C** (the F-048 treatment: delete the CRT classifier, let
`ExecutionPlannerV1_2._derive_intent` own intent) as the target, and chose to measure it in shadow
before authorizing any edit. Probe: `scripts/analysis/trade_intent_ownership_shadow.py` (SCR-472,
`OBSERVATION_ONLY`, **no `src/` edit**, so ledger identity is structural). Artifact:
`docs/governance/trade_intent_ownership_shadow.LATEST.json`. Both arms were given the engine's
resolved `breakout_disp_threshold` (1.5), as `execution_planner.DEFAULT_CONFIG`'s own comment
requires, so disagreement is not manufactured by a threshold mismatch.

Population: every CRT retest confirmation on XAUUSD M15, schema 6.0, active `v2_htfcrt_2026_08`.
**n = 6 retest confirmations, of which 2 became trade-opens. 0 feature-lookup misses.**

| | Arm CURRENT (cache) | Arm C (canonical row) |
|---|---|---|
| distribution | `reversal` 5, `breakout` 1 | `REVERSAL` 4, `LIQ_SWEEP` 1, `UNKNOWN` 1 |
| labels disagree | — | **3 of 6** |
| TP1 multiplier changes | — | **3 of 6** |
| new reject path | none (always classifies) | **1 of 6** would `reject_unknown_intent` |

Trade-open subset (n=2): one unchanged (`reversal`→`REVERSAL`, TP1 1.0→1.0); one **changed**
(`breakout`→`REVERSAL`, **TP1 1.5→1.0**, a 33% tighter first target). Neither would have been
rejected.

### Two results that bear on the decision

**(a) Option C's `UNKNOWN` is a real semantic hole, not just stricter.** The one `UNKNOWN`
(2024-08-21 22:15, a LONG) has `ema_fast` 2512.91 > `ema_slow` 2510.74 with `direction = +1`. The
planner's `REVERSAL` test is `(ema_fast > ema_slow and dir == -1) or (ema_fast < ema_slow and dir == +1)`,
so a **trend-ALIGNED** entry that is not a breakout, pullback or sweep falls through to `UNKNOWN` —
and `reject_unknown_intent` is `True` by default. Option C would therefore *reject trend-aligned
entries* the CRT rail currently opens as `reversal`. That is a defect in the target architecture,
and it must be fixed before C ships, not after.

**(b) Options A/B and C are NOT interchangeable — they gate `pullback` on different quantities.**
Occupancy of the 0.3–0.7 pullback depth band over the same 6 records:

| depth quantity | in band |
|---|---|
| FM-027 `displacement_retrace` (what A/B would keep) | **3 of 6** |
| FM-021 `retest_depth` (what C switches to) | **0 of 6** |

So binding the cache's missing keys while keeping FM-027 (options A/B) puts half the population in
the pullback band; switching wholesale to the pipeline quantity (option C) puts none of it there.
The choice between A/B and C is a choice of *depth definition*, not only of reject semantics. This
is §5's caveat (L2) turning out to be materially load-bearing rather than a footnote.

### Sealed predictions, scored honestly

Registered in the script docstring before any result was read. **3 of 5 passed.**

| | prediction | result |
|---|---|---|
| P1 | Arm CURRENT `reversal` on ≥90% of records | **FAIL** — 5/6 = 83%, one `breakout` |
| P2 | Arm CURRENT emits zero `pullback` | PASS |
| P3 | Arm C emits at least one `PULLBACK` | **FAIL** — zero, see (b) |
| P4 | Arm C emits at least one `UNKNOWN` | PASS — 1 |
| P5 | n < 30, economically INSUFFICIENT | PASS — n=6 |

P3's failure is the informative one: the bar matrix carries 2,767 `pullback` rows corpus-wide (§5),
yet **none** of them lands on a CRT retest bar. CRT retest confirmations are a strongly selected
subpopulation with shallow pipeline retest depth. The intuition that binding the missing keys
"unlocks" `pullback` on the CRT rail is **falsified on this population**.

### Authority

**None.** n=6 with 2 trade-opens measures MECHANISM — does the label move, does a new reject appear
— and nothing else. No expectancy claim is derivable and none is made. No finding registered; no
config, registry or ledger touched. The `UNKNOWN`-reject hole (a) is the item that must be resolved
before option C could be authorized.

## 10. Schema comparison, UNKNOWN trace, and the alignment change (2026-09-16)

Change set `CH-intent-schema-alignment` (impact manifest APPROVED). User decisions: align by
**identity**; **fix the classifier**; then, once the gate measurement below existed, keep the fix
**classifier-only with the gate untouched**.

### 10.1 The two schemas share no quantity

Read from the ontology rather than inferred from key names:

| | Arm A — CRT cache (episode-scoped) | Arm C — canonical row (bar-scoped) |
|---|---|---|
| depth | FM-027 `clip(\|retest_close−disp_open\|/\|disp_close−disp_open\|,0,1)` | FM-021 `retest_flag==1 ? \|close−ema_fast\|/atr_abs : 0.0` |
| displacement | FM-028 `candle_range/atr_abs`, **displacement** candle | FM-020 `clip(body_size/atr_abs,0,3)`, **current** bar |
| `body_ratio` | FM-010, **displacement** candle | FM-010, **current** bar |
| `double_sweep` | the episode's `sweep_event.double_confirmed` | FM-060 rolling(5), both signs |

`body_ratio` shares a formula but not a subject; `double_sweep` shares only a name. The "overlap on two
keys" in §2 was name-level; at the quantity level there is none. FM-021 is not a retrace depth at all —
it is distance from price to the 9-EMA, and `feature_pipeline.py` masks it to a `0.0` "no retest"
sentinel whenever `retest_flag == 0` (41.93% of bars).

Two further facts surfaced:

- `retest_flag == 1` on **58.07%** of bars, yet it was **0 on 4 of the 6** bars where the CRT engine
  confirmed RETEST. The two rails have unrelated "retest" concepts sharing a name. Recorded, not fixed.
- The `0.0` sentinel sits inside a numeric band predicate. Benign for the current `0.3 ≤ rd ≤ 0.7`
  test; a latent hazard for any future lower-bounded one. Per §6.8 `different ≠ wrong` — recorded, not
  called a defect.

One self-correction: `momentum_score`'s **magnitude** is F-061-saturated, but the planner reads only
`mom > 0`, and F-061 records sign-only consumers as unaffected. That test is sound.

### 10.2 UNKNOWN traced — 2024-08-21 22:15, LONG

| branch | values | result |
|---|---|---|
| LIQ_SWEEP | `sweep_detected` 0.0, `double_sweep` 0.0 | skip |
| PULLBACK | `rd` 0.0950, `csr` 6, `mom` −218.2 | fails all three gates independently |
| BREAKOUT | `body_ratio` 0.1116, `disp_strength` 0.0809 | fails both |
| REVERSAL | `ema_fast` 2512.907 > `ema_slow` 2510.742, dir **+1** | neither clause |
| → | | **UNKNOWN → `reject_unknown_intent`** |

The same bar in Arm A has `rd` 0.4059 **inside** the pullback band and `body_ratio` 0.9238 **above** the
breakout threshold. One bar, two true descriptions of different objects. The hole: `REVERSAL` is
strictly counter-trend, so every with-trend entry that is not a sweep/pullback/breakout reaches UNKNOWN —
**40.70% of bars (LONG), 31.97% (SHORT).**

### 10.3 Part 1 — identity without vector membership

Promoting FM-027/FM-028 to vector slots (48 → 50 dims, schema v7.0) is **not constructible**:
`feature_pipeline.py` has zero occurrences of `disp_open` / `disp_close` / `displacement_candle`, and
FM-027 needs a displacement↔retest candle pairing that exists only in the state machine. A slot would
need a second state machine (whose retest definition already disagrees with the engine's, 10.1) or a
sentinel on ~99% of bars. Delivered instead, and approved with that reasoning stated:

- FM-027 and FM-028 refined **in place** (ids kept, version 1 → 2) with `lineage.scope: EPISODE`, a new
  optional field declared in `spec_schema.additive_spec_blocks.lineage` (unread by any runtime path).
- Distinctness from FM-021 / FM-020 written onto both nodes. For FM-028 stated precisely: the *formula*
  is computable on any bar; the *identity* is bound to the displacement candle.
- Stale `source_of_truth` citations corrected (`:1372` → `:1771`, `:1355` → `:1776`).
- Formula / impl / depends_on strings byte-identical. `CANONICAL_FEATURES`, `SCHEMA_HASH`,
  `FEATURE_ORDER_HASH` untouched. `validate_registry()` and `validate_semantic_registry()` both `[]`.
- Freeze pin: waiver-log SHA refresh with **measured** attribution — inverting this change's edits on an
  in-memory copy re-hashes to exactly the prior pin. (A first LF-only inversion failed to match because
  the file is CRLF; that was a bug in the check, not foreign drift, and is recorded as such.) The
  ontology `version` bump moves no certification: `feature_dag_certify.compute_formula_hash` hashes
  `{formula_id, witness, deps}`, not `version`.

### 10.4 Part 2 — CONTINUATION, classifier only

`ExecutionPlannerV1_2._derive_intent` now splits the EMA test: `REVERSAL` (counter-trend) unchanged,
new **`CONTINUATION`** (with-trend). `ttl_continuation_sec` added to `_TTL_MAP`,
`REQUIRED_CONFIG_KEYS`, `DEFAULT_CONFIG` and the active config at **180 = `ttl_unknown_sec`** (parity with
the entries it took over, not a tuning). Params hash `7de09f62…` identical before and after — hash-neutral
measured, not assumed.

Re-measured on the full corpus with the **real** classifier, not a reimplementation:

| | LIQ_SWEEP | PULLBACK | BREAKOUT | REVERSAL | CONTINUATION | UNKNOWN |
|---|---|---|---|---|---|---|
| LONG before | 8,939 | 2,767 | 1,196 | 15,086 | — | 19,209 (40.70%) |
| LONG after | 8,939 | 2,767 | 1,196 | 15,086 | 19,207 | **2 (0.004%)** |
| SHORT before | 8,939 | 2,767 | 1,196 | 19,207 | — | 15,088 (31.97%) |
| SHORT after | 8,939 | 2,767 | 1,196 | 19,207 | 15,086 | **2 (0.004%)** |

`CONTINUATION` equals old UNKNOWN minus new UNKNOWN exactly, both directions, and no other label moved.
The corpus holds 3 exact EMA ties; one is caught by an earlier branch.

**Why classifier-only.** `GateIntelligence._intent_score` has no branch for a new label and scores it
`0.0`. Measured over a 3,000-bar sample per direction:

| gate intent score for CONTINUATION | approval |
|---|---|
| gate as-is (0.0) | **0.0%** |
| sign-only momentum confirmation | ~37% |
| upper bound (1.0) | ~66% |

So a classifier fix alone moves these entries from `reject_unknown_intent` to `reject_gate` with an honest
label; giving them a gate score is what would change decisions, and it swings approval 0–66%. That is
a separate, evidence-gated call. Copying `REVERSAL`'s `1 − min(1, |mom|)` would inherit F-061 saturation.
The 0.0% is a **measurement on this corpus, not a structural guarantee**: with intent at 0.0 the other
three gate weights still sum to 0.65 > 0.55, and production never emits `volume_ma20` (F-065 H7), which
plausibly holds approval down. The planner docstring was corrected mid-change from an overclaimed
"no approval decision changes" to exactly this.

**Third classifier copy.** `sl_tp_comparator.derive_intent_from_features` claims to mirror the planner
"exactly"; updated in lock-step, with `CONTINUATION` mapped to UNKNOWN's legacy TP fallback so comparator
levels cannot move. A new test makes the "mirrors exactly" docstring a checked fact.

**Tests encoded the hole.** Three fixtures — `test_reject_unknown_intent_by_default`,
`test_allow_unknown_intent_when_configured`, and the comparator's `test_unknown` — each used a with-trend
entry as their canonical "no pattern" case (one with the comment *"fast > slow, direction=1 → not
REVERSAL"*). Each keeps its property with an exact EMA tie; the old fixtures are retained as new
`CONTINUATION` pins. `test_continuation_gate_score_is_deliberately_zero` guards the gate decision so it
is not "fixed" by copying the saturated formula.

### 10.5 Blast radius, proved structurally

A transitive AST import closure over `src/` — lazy function-level imports included — shows
`runtime.backtest_v2` (140 modules) reaches **none** of `config_layer.execution_planner`,
`analytics.sl_tp_comparator`, `core.gate_intelligence`. The same method finds `execution_planner` and
`gate_intelligence` from `runtime.live_engine_hook`, so the negative is not vacuous. The backtest ledger
therefore cannot move. F-073 still applies: no production live rail, so no realized-PnL validation exists.

The empirical XAUUSD ledger diff was **BLOCKED, not passed** — see 10.6.

### 10.6 Two things found along the way

- **Another session's broken file.** `src/runtime/backtest_v2.py` (mtime 14:50, +76 lines,
  `CH-cost-model-identity-stamp`, its impact manifest untracked beside this one) inserts defaulted
  `cost_model_id` / `cost_model_params_hash` fields ahead of non-default ones, so the module raises at
  import. It blocks the ledger diff, the shadow re-run, `test_f057_f058_config_authority`, and — through
  `tests/governance/test_bar_structure_grounding.py` — collection of the governance floor itself. Not
  touched here.
- **My own stale pin from the v6 rename.** `test_feature_layer_freeze::test_source_file_pins_match` was
  failing on `feature_pipeline.py`. Traced from the session transcript: the pin was refreshed at ~04:32Z,
  then two edits at 04:45:28Z / 04:45:30Z updated the F-064 warning text (99.70% → 99.81%). Inverting
  exactly those two edits reproduces the stale pin. Both are a log literal and a comment; the vector
  regression still passes. Pin refreshed with a waiver-log entry, and the v6 completion manifest's
  "freeze test green" claim marked `CORRECTED` at source. Uncaught before because
  `test_feature_layer_freeze.py` is not in the GREEN_FLOOR.

### 10.7 Authority

None. Identity documentation plus a live-rail label change that, on this corpus, alters no approval
decision. No CANONICAL_FEATURES change, no schema v7.0, no gate change, no promotion, no G001.
