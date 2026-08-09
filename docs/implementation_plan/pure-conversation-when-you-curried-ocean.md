# CRT soft-conf EMA probe + shadow TTL off-by-one

## Context

A multi-model bug trace over the CRT engine (Phases 1–5, XAUUSD / `v2_multi_2026_04`) produced a
list of candidate defects. Source verification confirms five, rejects three, and **corrects the
headline claim's mechanism and direction**.

**The two defects in scope:**

1. **Double EMA update during soft confirmation.** `update_emas` fires twice on the same close for
   every candle of the confirmation window — once unconditionally at `crt_engine_v2.py:2617`
   (pre-chain straight-line code) and again at `:2976` inside `elif self.state.evaluating_soft_conf:`.
   The `elif` at `:2972` only excludes sibling *state* branches; `:2617` is ~60 lines above the chain
   and unguarded. There is **no `RETEST` state branch** in `process_candle`, so every confirmation
   candle falls through to the soft-conf `elif`, and the second update lands *before*
   `approve_with_soft_conf` (`:2983`) reads the EMAs at `:1907`.

   The received analysis called this `EMA(EMA(close))` making momentum "overly sensitive → more false
   approvals." That is backwards. Re-applying the same update gives effective α = 2α−α²:

   | | configured | effective in soft-conf |
   |---|---|---|
   | fast (`ema_fast=2`) | α=0.667, span 2 | α=0.889, **span 1.25** |
   | slow (`ema_slow=5`) | α=0.333, span 5 | α=0.556, **span 2.6** |

   Both EMAs hug price harder. `f_mom` reads the *spread*, not the level, so the spread **compresses
   to ~0.46×** in a trend (inflates ~1.34× in chop). `f_mom` therefore systematically **under-states**
   directional momentum in exactly the trending setups the term rewards — approval gets *harder*. It
   bites twice: weight 0.35 in `C_linear` (`:1927`) plus `min(f_body, f_mom)` weak-link (`:1930`).
   EMAs are seeded once and never cleared (`reset_to_range` reads at `:1698-1701` but does not reset),
   so the perturbation is path-dependent and permanent for the rest of a run.

   Evidence it is accidental: both call sites carry a comment claiming "every candle" — `:2975`'s is
   redundant with `:2616`'s, written without awareness of it. The reference implementation at
   `scripts/backtest/manual_backtest.py:358` updates once per bar.

2. **Shadow-memory TTL off-by-one.** The `[DEADLOCK FIX]` fall-through (`:2643-2646`, deliberate — it
   lets a sweep fire on the freshly-seeded range) means `reset_to_range` sets
   `pending_displacement_ttl = 4` (`:1737`) and the RANGE branch decrements it to 3 (`:2683`) **on the
   same candle**, before `detect_sweep` runs at `:2691`. A configured 4 yields 3 usable bars.

   The received analysis rated this "Low — clearly documented in the code with the comment 'same bar
   burns 1'." **No such comment exists in `crt_engine_v2.py`.** The phrase appears only in
   `assistant_project.md:2353`. The entire basis for the benign rating was a code comment that isn't
   there — which is precisely why the absent comment is worth adding alongside the fix.

**Intended outcome:** the EMA defect is *measured* (observe-only, spine untouched) before any
decision-surface change; the TTL off-by-one is corrected and its true semantics written into the code.

## Constraints and classification

- **EMA work is `OBSERVATION_ONLY`.** No edit to `src/config_layer/crt_engine_v2.py` for the EMA
  defect in this pass. The probe lives in `scripts/analysis/` and monkeypatches within its own
  process, following `scripts/analysis/rr_confidence_probe.py` and
  `b2a_feature_candidate_certification.py`.
- **TTL work is `BEHAVIOR_CHANGE_AUTHORIZED`** (user-authorized this session). It is *not*
  hash-neutral in effect: it widens the shadow-resumption window.
- **No test in the repo would catch either defect.** `crt_engine_v2.py` is not SHA-pinned by the
  feature-layer freeze, and the pin explicitly disclaims the CRT path
  (`tests/test_feature_layer_freeze.py:151-179` asserts `crt_state_machine: False`,
  `trade_count: None`). The XAUUSD vector SHA never constructs a `CRTEngine`. A green suite proves
  nothing here — new floors are mandatory, not optional.
- **Authority Ladder (§6.5):** both items are correctness/observability. Neither grants activation
  authority nor carries an economic claim.
- **Not in scope** (user declined this pass; file as tracked items only): BitNet fail-closed guard
  nesting at `:1976/:1983`, the three partial `pending_*` teardowns, dead `approve()` at `:2030`.

## Measurability — read before designing the probe

XAUUSD on the active config is throughput-starved:

- `data/mt5/XAUUSD_M15.csv` — 47,275 rows, SHA `4d73f5ce…` (pinned `tests/test_crt_baseline_trace.py:213`)
- 8-week freeze slice: `total_setups=0`, `SHADOW_PENDING=5`, `RETEST=3`
  (`results/XAUUSD/backtests/run_20260719_021925_XAUUSD/XAUUSD_summary.json`)
- Full corpus: `total_setups=1`, `SHADOW_PENDING=43`, `RETEST=17`, `EXECUTION=5`
  (`assistant_project.md:1116`)

**A trade-ledger A/B is structurally impossible.** The measurable surface is:

- **EMA →** `score_actual` in the `DECISION_DISTANCE` telemetry. Three records on the freeze slice —
  0.31081, 0.33007, 0.47721 against `tier_2_threshold=0.30`. Two sit within 0.031 of the threshold,
  so `f_mom` changes will move them visibly. All three were approved and then killed by the
  discount/premium zone filter (`:3050-3059`) → `FILTER_REJECTED`, 0 trades. So the EMA fix is
  **ledger-neutral on available XAUUSD evidence**; only the S-score vector responds.
- **TTL →** state distribution (`SHADOW_PENDING`, `SWEEP`) and setup count.

Per the standing instruction: measure on XAUUSD only. Do **not** substitute a crypto major to make
the probe produce events — a thin result on XAUUSD is the honest result.

---

## Phase A — EMA double-update probe (observe-only)

### A1. `scripts/analysis/soft_conf_ema_double_update_probe.py` (new, READ-ONLY)

Load the production config exactly as `backtest_v2` does — `get_prod_config("XAUUSD")` →
`ConfigBuilder.build` — never the FOREX router profile alone (F-057). Stream
`data/mt5/XAUUSD_M15.csv` through a real `CRTEngine`.

**Counterfactual construction.** EMAs feed *only* `compute_soft_confirmation` (`:1907`), the
`_ema_aligned` reset telemetry (`:1699`), and `get_live_metrics` (`:3249-3250`) — they never feed a
state transition. So a single-update trajectory can be carried in parallel:

- Wrap `EngineState.update_emas` in the probe process (not in `src/`) to also maintain
  `ema_fast_single` / `ema_slow_single`, advanced **once per `candle.index`**, seeded identically.
- At every `compute_soft_confirmation` call, capture the EMA-independent terms `f_body`, `f_dist`,
  `f_disp` and the geometric `G`, then recompute `f_mom'`, `C'`, `S'` from the single-update pair
  using the same arithmetic (`:1927-1933`, `conf_weights`, `weak_link_weight`, `conf_floor`,
  `conf_alpha`/`conf_beta`).

**Exactness boundary — state and honour it.** The counterfactual is *exact* while both arms share a
state trajectory. The first candle where the approval decision flips (`S` vs `tier_1`/`tier_2`) is a
divergence point; everything after is indicative only. The probe must record `first_divergence_idx`
and label subsequent rows `POST_DIVERGENCE`. Do not report post-divergence rows as measurements.

**Per-evaluation record:** `candle_index`, `timestamp`, `soft_conf_candle_num`, `direction`,
`atr_abs`, `f_body`/`f_dist`/`f_disp`, `ema_fast`/`ema_slow` both arms, `f_mom` both arms, `C` both
arms, `G`, `S` both arms, `tier_1`/`tier_2`, `approved` both arms, `flipped`, `regime` (trend vs chop
by sign persistence of the spread, to test the compression prediction).

**Artifact:** `results/analysis/soft_conf_ema_double_update.LATEST.json` — immutable, with
`config_version`, `config_hash`, corpus SHA, `git_sha`, row counts. Mirror the artifact shape of
`b2a_feature_candidate_certification.LATEST.json`.

> **Provenance blocker.** The working tree is structurally diverged from HEAD (836 untracked files,
> 68 in `src/`). Record `git_sha` **plus** a `tree_dirty: true` flag and a note; do not stamp a clean
> SHA that misrepresents what ran.

### A2. Prediction to falsify (pre-register before running)

The spread compresses under double-update in trends → `f_mom_double < f_mom_single` on trending
evaluations → `S_double < S_single`. If the observed sign is mixed or reversed, the mechanism above
is wrong and the finding must be downgraded, not rationalised.

### A3. `tests/test_soft_conf_ema_probe.py` (new floor)

Behavioral, not grep-based (E-001: a test that cannot fail is not enforcement).

- Synthetic monotone-trend series: assert double-update spread < single-update spread, and that a
  double-updated EMA equals the closed form α_eff = 2α−α².
- Assert the probe's counterfactual recomputation of `C`/`S` reproduces
  `compute_soft_confirmation` exactly when fed the double-update EMAs (self-consistency).
- Artifact-schema assertions, `skipif` on absence.

### A4. Registration

- **Finding** in `docs/current-findings.md` + the mirrored row in `CLAUDE.md`'s Repository Truths
  Index (both required — `tests/test_current_findings.py` enforces the pair). Next free id — verify
  against the living doc; `F-066` is currently the highest. Run the §6.2 six-question
  pre-registration ritual; if the S-delta is small or sign-mixed, register as `HYPOTHESIS`, not a
  conclusion. `Authority: research/architecture only.`
- **Ontology (§6.6):** register the confirmation-momentum quantity as a canonical node with an
  `epistemic` block — `known_invariants` (two call sites, α_eff closed form), `unknown_mechanism`
  (economic consequence, unmeasurable on XAUUSD at n=3), `resolution_metric`,
  `falsification_conditions`. Non-frozen sibling section; do not touch the flat frozen runtime keys.
- **No code fix in this phase.** The decision to remove `:2976` is a separate gated turn once the
  probe reports.

---

## Phase B — Shadow TTL off-by-one (authorized behavior change)

### B1. Fix — `src/config_layer/crt_engine_v2.py`

Add `pending_displacement_created_idx: int = 0` to `EngineState` (near `:266-273`). Set it in
`reset_to_range`'s `_create_shadow` block (`:1734-1745`). Guard the decrement at `:2682-2683` to skip
the creating bar:

```
if self.state.pending_displacement_ttl > 0 \
        and candle.index != self.state.pending_displacement_created_idx:
```

Chosen over `ttl = N + 1` because it encodes the intent rather than hiding the off-by-one behind a
magic increment.

Add the comment that the received analysis assumed existed — at the decrement site, naming the
`[DEADLOCK FIX]` fall-through at `:2643-2646` as the cause and stating that a configured TTL of N now
yields N usable bars.

**Do not introduce a new stale field.** Clear `pending_displacement_created_idx` in every path that
already clears `pending_displacement_ttl`: the consumed path (`:2827-2834`), the `SHADOW_LEAK`
handler (`:2797-2799`), the TTL-expiry path (`:2684-2689`), and the non-HTF reset in `reset_to_range`
(`:1746-1750`). This is scoped to the new field only — the pre-existing four-field leak across those
same paths stays out of scope per the user's decision.

### B2. `tests/test_shadow_ttl_lifecycle.py` (new floor)

Deterministic, no corpus:

- Shadow created on bar N with `pending_displacement_ttl_candles=4` survives bars N+1…N+4 and expires
  on N+5 — the assertion that fails on today's code and passes after.
- The creating bar does not decrement.
- A matching-direction sweep on the final TTL bar still resumes via `SHADOW_PENDING`.
- `pending_displacement_created_idx` is cleared on consume, leak, expiry, and non-HTF reset.

### B3. Measurement

Run XAUUSD before/after and diff `state_distribution` (`SHADOW_PENDING`, `SWEEP`, `RETEST`) and
`total_setups`. Expect ≥ as many `SHADOW_PENDING` resumptions. Report the delta plainly; with
`total_setups=1` on the full corpus, **make no economic claim** — this is a correctness fix with an
observable state-distribution delta and unknown economic value.

### B4. Registration

Finding + `CLAUDE.md` index row (paired), including the explicit correction that the mitigating code
comment cited in the received analysis does not exist. Ontology node for the shadow-TTL lifecycle per
§6.6.

---

## Cross-cutting (both phases)

- **§6.3 Citation Sync** — line numbers shift in `crt_engine_v2.py` from Phase B. Check
  `docs/architecture/citation-map.generated.md` and repair citations the same turn
  (`tests/test_doc_citations.py`, ±30-line window).
- **§6.4 Topic Sync** — update the one topic doc covering CRT state/shadow memory; bump `Updated:`,
  append a dated Discussion entry.
- **SITS** — both new scripts must be registered the same turn: `script_census.py --write-stubs` →
  `seed_script_registry.py` → `generate_script_matrix.py`. Unregistered paths fail GREEN_FLOOR.
- **§6 SESSION LOG** — append to `assistant_project.md` (codebase log; this is governed code/config).
- **Memory** — the durable belief changes worth persisting: the α_eff = 2α−α² spread-compression
  mechanism (with the correction that it is *not* `EMA(EMA(close))`), and the meta-lesson that a
  fabricated code comment carried an entire severity rating. The second reinforces the existing
  `verify-source-not-comments` entry — update it rather than creating a duplicate.

## Verification

Use the venv interpreter (`venv/Scripts/python.exe`); a bare `python` may resolve elsewhere.

Baseline / after, per phase — pass `--instrument XAUUSD` explicitly, since `AUTO` derives
`XAUUSD_M15` from the CSV stem (`backtest_v2.py:3023-3027`, hazard pinned in
`tests/test_f057_f058_config_authority.py:39`). Set **no** `BACKTEST_ENGINE_GATE` — config is the
authority since the F-058 fix (`backtest_v2.py:2050-2063`, `engine_gate_enabled: true`); setting the
env var logs a WARNING that the ledger is off-epoch.

```bash
venv/Scripts/python.exe src/runtime/backtest_v2.py --csv data/mt5/XAUUSD_M15.csv --instrument XAUUSD --output results/ttl_before
```

```bash
venv/Scripts/python.exe scripts/analysis/soft_conf_ema_double_update_probe.py --csv data/mt5/XAUUSD_M15.csv --instrument XAUUSD
```

```bash
venv/Scripts/python.exe -m pytest tests/test_soft_conf_ema_probe.py tests/test_shadow_ttl_lifecycle.py tests/test_crt_state_invariants.py tests/test_crt_adversarial_closure.py tests/test_crt_baseline_trace.py -q
```

```bash
venv/Scripts/python.exe -m pytest tests/test_current_findings.py tests/test_doc_citations.py tests/test_topic_docs.py tests/test_script_registry.py tests/test_script_matrix_sync.py tests/test_semantic_registry.py -q
```

**Acceptance:**

- Phase A: probe artifact exists with a stated `first_divergence_idx`; the trend-compression
  prediction is either confirmed with a sign and magnitude, or explicitly falsified. `src/` unchanged.
- Phase B: `test_shadow_ttl_lifecycle.py` fails on pre-fix code and passes after; the XAUUSD
  state-distribution delta is recorded; feature-layer freeze (`test_feature_layer_freeze.py`) stays
  green, since `crt_engine_v2.py` is outside its pins.
- Both: findings paired between `docs/current-findings.md` and `CLAUDE.md`; SESSION LOG appended.
