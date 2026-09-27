# RR Model — Design Analysis and Enablement Path

**Document type:** investigation record + design.
**Created:** 2026-09-23 · **Branch:** `grokbotchanges` · **Active config:** `v2_htfcrt_2026_08`
**Status:** design only. Grants no authority. No production code, config, or artifact changed.
**Scope note:** everything below was source-verified in-session. Claims that were *not* verified
are labelled `UNVERIFIED`. Where a recorded finding and observed source disagreed, the disagreement
is recorded rather than silently resolved (CLAUDE.md §6.2 rule 3).

---

## 0. How this document came about

A request to discuss **RRModel implementation design** — gathering schema from the codebase, using
`docs/implementation_plan/` for implementation reference only, no multi-agent exploration. Design
theory first, implementation second.

Mid-investigation the scope was extended by a second request: **enable fusion as the next action
item, enable the RR engines, and include parallel-engine monitoring during backtest in the design.**

This document captures the full arc: what was read, what was found, what was decided, what was
explicitly deferred, and what remains open. It is written to be readable by a session that has
none of this context.

**Working constraints observed throughout**
- No subagents (explicit instruction; also CLAUDE.md §1.2 — "Prefer targeted grep first").
- `docs/implementation_plan/` used as reference precedent only, never as authority.
- Plan mode active: read-only investigation; no edits outside the plan file.
- File writes via Write/Edit, never heredoc/`sed` (§1.6).

---

## 1. Executive summary

Five findings, in order of how much they change the work:

1. **No 48-dim RR artifact exists.** Live schema is 48-dim (v6.0); the widest artifact on disk is
   39-dim. Enabling fusion is blocked on a **missing model**, not a config flag.
2. **Flipping `rr_fusion.enabled: true` today is inert.** The width check fail-closes, `is_loaded`
   stays `False`, the scoring block is skipped, and base RR polarity flows through unchanged.
   Config change, zero behaviour change.
3. **The F-038 Gaussian-duplication fail-open is dormant only because nothing loads.** Ship a
   loadable 48-dim artifact, flip the flag, and it becomes live — at roughly 10% of scored bars,
   per the gate's own `target_bypass_fraction`. The abstention fix is therefore a **prerequisite of
   enablement**, not adjacent hygiene. This reversed the author's own initial framing.
4. **The parallel-monitoring rail already exists.** `src/runtime/layer_trace.py` is wired into
   `backtest_v2`, observation-only, with a fixed layer/status vocabulary — and `MODEL_CATALOG`
   already enumerates the five off-spine models that would run in shadow.
5. **"RR" names three unrelated objects**, which is how F-038 was mis-diagnosed once already
   (F-044 corrected the mechanism from "model OOD" to "gate mis-scaled").

Resulting shape: **four gates**, with enablement as Gate 4 and Gates 1–3 as the shortest path to
it that does not reintroduce a known defect.

---

## 2. The three objects named "RR"

The first design problem is nominal. Three things wear the same two letters and answer three
unrelated questions:

| Object | Question it answers | Code | Live on active config? |
|---|---|---|---|
| **Candle polarity** | *How committed is this candle?* | `src/engines/rr_engine.py:45` | **yes** — fusion slot `rr`, `weight_rr: 0.2` |
| **Learned reward** | *What reward behaviour follows this state?* | `src/config_layer/rr/rr_pattern_miner.py`, `rr_fusion.py` | **no** — `engine_runner.rr_fusion.enabled: false` |
| **Economic RR** | *Does this planned trade clear cost-taxed reward:risk?* | `src/core/ultron_risk_gate.py:235` | **yes** — post-planner, sole owner (F-048) |

**What the polarity engine actually computes.** `RREngine.compute` reads only `close/high/low`:

```
candle_range = high - low
upper_body   = (high  - close) / candle_range
lower_body   = (close - low)   / candle_range
polarity     = max(upper_body, lower_body)
```

The module names this honestly at `rr_engine.py:81` (`"semantic": "candle_structure_quality"`) and
its docstring states it is *not* forward RR. MIAR §3.7 codifies the same: intent is
**commitment**; explicit non-goals include *"never compute forward RR from SL/TP"* and *"never
replace Ultron min_rr."*

**Structural observation (descriptive, no authority):** the two terms sum to exactly `1`, so
`max(·)` is bounded below by `0.5`. Output is therefore `{0.0} ∪ [0.5, 1.0]` — the engine
**cannot express low commitment anywhere in `(0, 0.5)`**. The `rr` fusion slot carries roughly half
the dynamic range its 0.2 weight implies. The Semantic OS entry already states this; it is worth an
ontology note and nothing more.

**Authority boundary, already settled.** F-048 removed the DecisionEngine RR gate and assigned
economic reward:risk solely to `UltronRiskGate` (cost-taxed `min_rr_ratio`, applied *after*
`ExecutionPlannerV1_2` derives SL/TP). `decision_engine.rr_threshold` survives as
**retained-but-RETIRED**. Any RR redesign must not reclaim that ownership.

---

## 3. The trained stack — what it is and how it fails

### 3.1 Architecture

`RRPatternTrainer` / `NanoInferenceEngine` (`src/config_layer/rr/rr_pattern_miner.py`) is a
pure-Python, numpy-free inference engine (`__slots__`-based) combining three heads:

| Head | Produces | Mechanism |
|---|---|---|
| Ridge regression | `expected_rr` | `Σ X[i]·W[i] + b`, clamped to `[RR_SCORE_MIN, RR_SCORE_MAX]` = `[-3.0, 5.0]` |
| Gaussian Naive Bayes | `probability_of_win` | per-class log-likelihood → softmax |
| Ledoit-Wolf Mahalanobis | `confidence` | `exp(-0.5·d_sq)` over the precision matrix |

Blended as `final_score = 0.5·gaussian + 0.3·ml_score + 0.2·confidence`
(`rr_model.score_weights`), where `ml_score = sigmoid(expected_rr / 3.0)`.

**Design smell worth naming:** that blend sums a probability, an expectancy pushed through a
sigmoid, and a *self-reliability* measure onto one 0–1 scale. Confidence is a meta-quantity *about*
the estimate — including it in the score means a model that is merely **sure** outranks one that is
**optimistic**. This is a category error independent of any calibration issue.

`RR_SCORE_MIN`/`RR_SCORE_MAX` are deliberately **structural constants in code, not config knobs**
(RR-001): "algorithm boundaries belong in code, not config — no fallback, no degrees of freedom."

### 3.2 F-044 — the confidence gate is mis-specified for its dimensionality

The sharpest design lesson in the RR history, and the reason the trained stack is off.

The legacy gate bypasses when `confidence = exp(-0.5·d_sq) < confidence_bypass_threshold (0.3)`,
which requires `d_sq < 2.408`. But `d_sq` is a Mahalanobis distance over a **rank-27** form (38
dims minus 11 `zero_indices`), whose in-distribution expectation is `E[d_sq] = dof = 27`. So
in-distribution confidence sits near `exp(-13.5) ≈ 1.4e-6` — four orders of magnitude below the
threshold.

The probe was decisive: **100% bypass on the model's own 49,000 training rows.** Minimum in-sample
`d_sq` was 4.30, already above the 2.408 needed to clear the gate; mean 26.7 ≈ dof 27, textbook
χ²(27). *A model cannot be out-of-distribution on the data it was fit to* — therefore the defect is
the **gate**, not the model, and **retraining alone cannot fix it** because any well-fit model
reproduces the `exp(-0.5·dof)` floor.

This **refined rather than reversed** F-038: mechanism moved from "model OOD when fed correctly" to
"gate mis-scaled to dimensionality." F-038's remediation (disable `rr_fusion`) stayed correct.

**The generalisable principle: abstention is a policy with an operating point, not an arithmetic
side-effect of the score function.** A correctly-fit estimator behind a mis-scaled acceptance gate
is externally indistinguishable from a broken estimator.

The fix already shipped, additively and behind config. `_confidence_bypass(d_sq_raw, dof, confidence)`
now supports four modes:

| Mode | Rule |
|---|---|
| `legacy_scalar` (parity default) | `confidence < _CONF_BYPASS` — byte-identical to the original line |
| `chi2_tail` | bypass iff `Q(dof/2, d_sq/2) < p_threshold` |
| `dof_scaled` | bypass iff `d_sq/dof > dof_scaled_max` |
| `percentile` | bypass iff `d_sq > d_sq_cut`, calibrated from the **empirical** training-d_sq CDF |

The active config selects `percentile` with `d_sq_cut: 40.4212`, `target_bypass_fraction: 0.1`.
`percentile` was chosen over the theory-implied `chi2_tail` for a measured reason: the empirical
`d_sq` distribution is **heavier-tailed than χ²(dof)**, so theory p-values mis-estimate real bypass.
The trainer now persists `training_distribution` (`n`, `effective_dof`, `d_sq` p50/p90/p95/p99) so
the operating point is a reproducible contract rather than an implicit assumption.

Note the default-selection discipline: a missing `confidence_gate` subsection maps to the
**identity** behaviour (`legacy_scalar`), not to a new and possibly-wrong default — mirroring
`engine_runner.rr_fusion.full_feature_vector`.

### 3.3 F-038 — the abstention fail-open

`_passthrough()` (`src/config_layer/rr/rr_fusion.py:39`) returns `final_score = gaussian_score`, and
`src/core/engine_runner.py:786` reads that straight into the `rr` slot. Six statuses route there:
`disabled`, `model_not_loaded`, `drift_detected`, `bypassed_low_confidence`,
`feature_dimension_mismatch`, `inference_error`.

Consequence when the layer is active: the four-engine weighted fusion carries **Gaussian twice** —
once in its own slot at 0.2 and once wearing the RR slot's 0.2 — while the completeness check still
counts four independent votes. F-038's remediation was to disable `rr_fusion` in the active config;
it was code-verified structural (`RRFusionLayer` never constructed when `enabled: false`, base
`RREngine.compute()` flows through unmutated, hash-neutral) and pinned by
`test_rr_fusion_disabled_is_base_rr_identity` (full-object identity).

### 3.4 Reachability — exactly when the fail-open fires

Source-traced, and load-bearing for the whole plan:

| State | `is_loaded` | Path taken | Fail-open live? |
|---|---|---|---|
| `enabled: false` (**today**) | layer never constructed | base RR polarity | **no** |
| `enabled: true` + 39-dim artifact vs 48-dim live (**today, if flipped**) | `False` — width check refuses | `:758` block skipped → base RR polarity | **no** |
| `enabled: true` + loadable 48-dim artifact | `True` | `score()` → gate → `_passthrough` on bypass | **YES** |

The relevant guards: `engine_runner.py:399` sets `self._rr_fusion_enabled = bool(self.rr_fusion.is_loaded)`,
and `:758` gates the whole scoring block on `if self.rr_fusion and self.rr_fusion.is_loaded:`.

**This is the reordering insight.** The defect's dormancy is a property of the *broken artifact*,
not of the code. Fixing the artifact — which is precisely what "enable fusion" requires — is what
makes the defect live, at ~10% of bars per the configured `target_bypass_fraction`.

### 3.5 Label provenance — F-022 → F-045 → F-059 → F-088

`rr_dataset_builder.extract_target` resolves the regression target in priority order
`rr_achieved` → `pnl_rr_net` → computed `|tp−entry| / |entry−sl|`, and the win label from the
`outcome` string (`WIN`/`W`/`TP`/`TP_HIT`/`1`), falling back to `rr > 0`.

That is the **F-022 stream** — a *detection* stream, only 36.8% self-consistent, with `SL_HIT`
stamped on paths that never touched the stop.

| Finding | Result |
|---|---|
| **F-045** | Contaminated-label kill-test: apparent OOS AUC **0.605** vs shuffle 0.505, `rr_corr` 0.074. Declared **INDETERMINATE** — *"the model may be predicting the mislabeling structure, not real outcomes."* Correctly refused a Keep/Retire verdict. Two E-001 pre-registration corrections caught before a false RETIRE was registered. |
| **F-059** | Clean-label re-test under frozen protocol `RR_L1_FREEZE_2026_07_21_V1`, n=139,942, labels via `forward_walk(intrabar_fixed)` net 12bps. AUC collapsed to **0.512**. `rr_corr` **0.167**. Top-decile mean `y_rr` **−0.154** vs random-decile **−0.434**. Overall mean `y_rr` **−0.436**. Verdict: **KEEP_CANDIDATE, research-only.** `RR_FUSION_REENABLE: false`. |
| **F-088** | Even the clean labels measured the **wrong trade object**. `forward_walk` models one TP, no partial, no trail. Production realises 50% at TP1, trails the stop to the half-way point, runs the remainder to TP2. |

The honest reading of F-059: **real discrimination on a book that still loses money.** Ranking
better than random is not the same as earning.

`multi_tp_walk` (SEM-017, `src/research/oracle/multi_tp_walk.py`) reproduces the production object
as a pure function, and carries two corrections worth preserving:

- **Effective precedence is SL-FIRST.** `ExecutionEngine.update_trade` *declares* a
  `TP2 > SL > TP1` branch order, but is fed a single scalar trigger from
  `crt_engine_v2._intrabar_trigger_price`, which tests `sl_touch` **before** any target. The
  declared branch order almost never binds. The docstring exists specifically to prevent
  misreading the comment as the rule.
- **A naming trap retained on purpose.** `partial_tp_breakeven_enabled` does **not** do breakeven —
  it is a half-way trail (`trail_fraction: 0.5`). Documented at the authoritative surfaces and
  pinned by a guard *"so nobody 'fixes' the code to match the name."*

### 3.6 Schema binding — three artifacts quarantined for one reason

`models/rr_model.json` carries its own epitaph in a `quarantine_reason` field:

> Positional `scale_mu`/`scale_sigma`/`ridge_w` (38) + `zero_indices` are aligned to the schema
> v3.0 **name order**. Schema v4.0 renamed two of those names and inserted `macd_hist_z` at index
> 19, so every index from 19 on is shifted: the vectors are structurally invalid under v4 and
> **CANNOT be remapped positionally.**

It also refuses to fabricate provenance: *"No `schema_hash` is added: these files never carried
one, and inventing it now would fabricate provenance."*

The solved pattern is `src/research/model_runners/schema_resolver.py`, the single live→trained
authority. Its contract: artifact declares its own `feature_schema`; every trained name resolves to
a live canonical name via `SCHEMA_V3_ALIASES` (the one alias authority — the module never defines
its own rename literals); vectors are built **by name, in trained order**, never by positional
slicing, zero-fill, pad, or truncate; unknown schema id, unresolvable name, duplicate resolution, or
missing live feature all **raise**.

It also freezes historical widths deliberately: `canonical_38_v3` stays exactly 38-dim regardless of
how far live grows, because otherwise "the v3 schema" would be silently redefined every time
`CANONICAL_FEATURES` grew.

### 3.7 Artifact census — the blocking fact

Live: `CANONICAL_FEATURE_DIM = 48`, `SCHEMA_VERSION = 6.0`.

| Artifact | `n_features` | declared schema |
|---|---|---|
| `models/ETHUSDT/20260519_113806/rr_model_202605_v1.json` | 35 | `canonical_35` |
| `models/ETHUSDT/20260519_134711/rr_model_v5_auto_2026_06_eth2.json` | 35 | `canonical_35` |
| `models/rr_model.json` | 38 | `canonical_38`, v3.0 — **quarantined** |
| `models/rr_model_202605_bnb_v1.json` | 38 | `canonical_38`, v3.0 |
| `models/rr_model_202605_bnb_v2.json` | 38 | `canonical_38`, v3.0 |
| `models/XAUUSD/20260728_v39/rr_model_20260728_v39_xau.json` | 39 | `canonical_39`, v4.0 — **the configured one** |
| — | **48** | **v6.0 — what live requires. Does not exist.** |

The active config's own `confidence_gate.note` concedes the gap: *"Model is now trained on a 39-dim
schema, one generation behind this config's 48-dim live vector — `rr_fusion.enabled` stays false."*

F-076 records the same for every model family: all six (zone_gate / rr / rr_fusion / gaussian /
bitnet / tradenet) went stale at the 39→48 bump, and the gates were "left exactly as inert/degraded
as they already were," with retrain deferred as separate authorized work.

---

## 4. Active configuration (verified in-session)

`configs/production/ACTIVE_VERSION` → `v2_htfcrt_2026_08`.

```jsonc
"rr_model": {
  "ridge_alpha": 10.0, "gnb_var_smoothing": 1e-09,
  "drift_threshold": 1.5, "mahal_clip": 500.0,
  "confidence_bypass_threshold": 0.3,
  "min_samples": 20, "dataset_min_samples": 20,
  "score_weights": { "gaussian": 0.5, "ml": 0.3, "confidence": 0.2 },
  "model_path":   "models/XAUUSD/20260728_v39/rr_model_20260728_v39_xau.json",
  "dataset_path": "models/XAUUSD/20260728_v39/rr_dataset.json",
  "confidence_gate": {
    "mode": "percentile", "p_threshold": 0.01, "dof_scaled_max": 3.0,
    "d_sq_cut": 40.4212, "target_bypass_fraction": 0.1,
    "calibration_artifact": "results/rr_confidence_probe/rr_v39_xau_gate_calibration.json"
  }
},
"engine_runner": { "rr_fusion": {
  "enabled": false,
  "model_path": "models/XAUUSD/20260728_v39/rr_model_20260728_v39_xau.json",
  "threshold": 0.5, "full_feature_vector": true
}},
"fusion_engine": {
  "weight_crt": 0.4, "weight_gaussian": 0.2,
  "weight_zone_gate": 0.2, "weight_rr": 0.2,
  "tier_full": 0.75, "tier_half": 0.6, "tier_quarter": 0.5
}
```

`EXPECTED_ENGINES = {"crt", "gaussian", "zone_gate", "rr"}` (`engine_runner.py:54`).

**Important:** `d_sq_cut: 40.4212` was calibrated against the **39-dim** model's empirical CDF. A
48-dim retrain changes `dof`, so carrying that cut forward unchanged would repeat F-044 in a new
dimension.

---

## 5. Fusion mechanics — how an absent vote is handled today

### 5.1 The completeness gate is key-presence only

```python
expected = ("crt", "gaussian", "zone_gate", "rr")
missing  = [name for name in expected if name not in engine_results]
if missing:
    return {"final_score": 0.0, "scores": {...zeros...},
            "missing_engines": missing, "reason": "missing_engine_outputs"}
```

It asks *"is the key there?"*, never *"does the value mean anything?"* — which is exactly why a
passthrough-borrowed Gaussian score satisfies it.

`_extract_score` returns `0.0` for any payload it cannot parse, so simply emitting a malformed
result silently becomes a **zero vote at full weight** — materially different from abstaining.

### 5.2 Weight renormalisation already exists

`FusionEngine.compute` already handles a dead engine by zeroing its weight and dividing by the
surviving sum:

```python
w_zonegate = 0.0 if zone_gate_dead else w_zone
total_w    = (w_crt + w_gaussian + w_zonegate + w_rr + w_consensus) or 1.0
weighted   = (w_crt*score_crt + w_gaussian*score_gaussian
              + w_zonegate*score_zonegate + w_rr*score_rr
              + w_consensus*score_consensus) / total_w
```

`zone_gate_dead` comes from a health tracker (`mean=0, var=0` ⇒ dead) and is surfaced in the return
payload. **Abstention should generalise this existing, tested mechanism rather than invent one.**

---

## 6. Design theory — the five principles

Derived from the failures above; each is a rule a redesign must not re-break.

**P1 — Separate the estimator, the gate, and the consumer.**
An estimator is a pure function of the feature vector. Abstention is a *separately calibrated
policy* with a declared operating point. What an absent vote means is a *fusion* decision. Fusing
all three into one `predict()` is what made F-044 invisible for as long as it was.

**P2 — The label object is the model's meaning, not a preprocessing detail.**
Regress on `multi_tp_walk` and you have a model of the trade the system actually takes. Regress on
`forward_walk` and you have a model of a simpler hypothetical trade. Regress on `rr_achieved` and
you have a model of a **labelling artifact**. All three are legitimate objects; only one is
production; the artifact must state which, in writing, inside itself.

**P3 — Bind features by name; positional binding is a latent time-bomb.**
Three quarantined artifacts, one cause. Carry `{schema_id, feature_order, schema_hash}` in the
artifact and resolve through `schema_resolver`, so the next schema bump produces a **clean refusal**
instead of a silent index shift.

**P4 — Abstain, never substitute.**
An abstaining model emits `ABSTAIN`, not another engine's number. Let the fusion completeness policy
decide what an absent vote means — renormalise, veto, or neutral prior — where it can be audited,
rather than laundering the decision inside a model's return dict.

**P5 — Correctness is not authority.**
A cleaner gate, a better AUC, or a loadable artifact grant *tunability* and *information*, never
production weight. Only measured ΔG001 does (§6.5 Authority Ladder:
`information exists → economic usefulness → authority earned → architecture justified`).

---

## 7. The design — four gates

Enablement is Gate 4. Gates 1–3 are the shortest path to it that does not reintroduce a known
defect.

### Gate 1 — Ownership and abstention *(prerequisite for Gate 4)*

#### Contract A — Identity separation (declarative; zero runtime change)

**Principle: rename the meaning, pin the identifiers.** Four rename surfaces, triaged by blast
radius — only (a) is touched:

| Surface | Example | Cost of renaming | Verdict |
|---|---|---|---|
| (a) emitted semantic key | `"semantic": "candle_structure_quality"` (already present) | free, additive | **rename / extend** |
| (b) fusion slot key `"rr"` | `engine_results`, `scores`, regime weight profiles | `EXPECTED_ENGINES`, `FusionEngine.expected`, 4 regime profiles, convergence `raw_scores`, **and every persisted events/JSONL payload** → breaks historical joins | **pin** |
| (c) config keys | `fusion_engine.weight_rr`, `engine_runner.rr_fusion.*` | hash-neutral (not in `params`), but strict `_cfg_require` ⇒ breaking migration across every config file | **pin** |
| (d) module/file paths | `src/engines/rr_engine.py` | breaks `tests/test_doc_citations.py` (±30-line window), `MODEL_CATALOG.entry_point`, Semantic OS `physical_path`, imports | **pin** |

This is not a compromise — it is the pattern this repository has already paid for twice:
F-088 pinned `partial_tp_breakeven_enabled`; F-048 kept `decision_engine.rr_threshold` as
retained-but-RETIRED, hash-neutral.

The indirection layer already exists. `docs/governance/semantic_os/file_identities.yaml` carries
`engines.candle_polarity_scorer` → `src/engines/rr_engine.py` with
`filename_semantic_status: MISLEADING`, aliases `[rr_engine, candle structure quality, rr_ratio]`,
and a `filename_status_reason` that cites the arithmetic and points at
`ultron_risk_gate.py:230-245` for where economic RR actually lives. The repo already decided
identity lives there, not in filenames.

Three identities to register:

| Identity | Semantic name | MIAR id | Emitted `semantic` | Non-goal |
|---|---|---|---|---|
| Candle polarity | Candle Polarity Scorer | `rr_engine` | `candle_structure_quality` | never forward RR from SL/TP |
| Learned reward | Learned Reward Estimator | `rr_trained` | `rr_trained_nano_inference_raw` | never set economic SL/TP alone; never claim retrieval |
| Economic RR | Ultron economic gate | — | — | sole owner (F-048) |

Synchronise (§6.2 r6, §6.3, §6.4): the three module docstrings, the **one** owning `docs/topics/`
file, and `active_models.yaml` (descriptive mirror; MIAR wins on intent conflict).

**Candidate DOC_DRIFT — adjudicate, do not silently fix.** `file_identities.yaml` maps
`engines.candle_polarity_scorer` → `miar_entry: crt`, while MIAR §3.7 `rr_engine` names that exact
file as its own `primary_code`. Both `rr_engine` and `rr_trained` are valid ids in
`miar_registry.json`, and `miar_entry` elsewhere carries real MIAR ids (`gaussian`,
`decision_fusion`, `feature_pipeline`). This reads as §6.2 rule-2 `DOC_DRIFT` in the auto-fix band
(changes no registered conclusion) — but confirm the field's own definition before editing (§6.8:
*different ≠ wrong*).

#### Contract B — Abstention

1. `_passthrough()` → abstain result `{status, reason, abstained: True}` with **no** borrowed
   `final_score`. The six existing statuses become the abstain reasons; nothing new invented.
2. `engine_runner.py:786` under abstain carries the **base `RREngine` polarity** — the honest
   independent vote that was always there. Never Gaussian.
3. Completeness gate unchanged: key-presence only, so an abstaining engine keeps its key and does
   not trip `missing_engine_outputs`.
4. Abstaining engine contributes `w = 0.0`, excluded from `total_w`, exactly as `zone_gate_dead`.
   The payload records which engines abstained.
5. `rr_fusion.enabled` stays `false` **through Gate 1**.

#### Contract C — Name pinning

A guard test asserting the four pinned names still carry their documented-but-misleading meaning,
so a future session cannot "fix" code to match a name. Style: the existing
`test_rr_fusion_disabled_is_base_rr_identity` full-object identity test.

### Gate 2 — Parallel engine monitoring *(the ΔG001 instrument)*

The third request, and simultaneously the only mechanism that can legitimately unlock Gate 4:
§6.5 grants authority on **measured ΔG001**, which requires running candidate engines against real
bars without letting them touch decisions.

**Reuse, do not build.** Two rails already exist, both `OBSERVATION_ONLY`:

*`src/runtime/layer_trace.py`* — the v5 `LayerProof` spine. One flat JSONL row per (bar, layer)
carrying `run_id` + `trace_id` + `span_id`. Already wired into `backtest_v2`
(`_build_layer_trace_emitter`:2576; constructed :2973-2981). Defaults `enabled: true`. Fixed
vocabularies that **raise** on unknown values:

```
LAYERS   = {L0..L9}
STATUSES = {PASS, REJECT, NOT_REACHED, EXCEPTION, UNVERIFIED}
LAYER_PLANE = {L0-L4: observation, L5-L6: evidence, L7: execution,
               L8: observation, L9: measurement}
```

Its stated invariant: every `emit()` happens **after** the layer's own decision is final; nothing is
read back into `EngineRunner`/`FusionEngine`/`DecisionEngine`/the CRT state machine; `emit()` returns
`None` and no caller consumes a value. `NOT_REACHED` is a first-class status, never a missing row —
the same fail-closed discipline as F-079.

It also documents the run-identity problem candidly: three independently-minted run ids already
exist in one backtest run (F-101), and this module mints a fourth canonical one rather than
pretending to collapse them.

*`src/research/model_runners/`* — `substrate × adapter → artifacts`, with `iter_bar_contexts`,
`RunManifest`/`RunRecord` envelopes, code provenance collection, and `sha256_file` artifact
stamping. `RRTrainedAdapter._raw_ml()` already recomputes the model arithmetic **bypassing the
confidence gate** for exactly this observation purpose — *"the live gate is mis-scaled for its rank,
so raw outputs are the honest observation surface."* It also refuses to guess a schema: an artifact
that does not declare `feature_schema` raises rather than defaulting to a generation.

**The parallel set is already enumerated** — `MODEL_CATALOG` phase 3, `spine_active=False`,
`runnable=True`:

| model_id | audit_status |
|---|---|
| `rr_trained` | OFF_SPINE |
| `bitnet` | DORMANT |
| `gaussian_ml` | EXPERIMENTAL |
| `tradenet` | UNWIRED |
| `envelope` | EXPERIMENTAL |

**Design:** a shadow monitor that, per bar in the backtest loop, scores the enabled phase-3 adapters
and emits one `layer_trace` row each, joined to the spine on `trace_id`. Bind to the **evidence
plane** (`L5`/`L6`) with `module="shadow:<model_id>"` — **no change to the `LAYERS` enum**, so the
fixed vocabulary stays fixed. Config-gated, default **off**, strict `_require` (§6.5 A1, no silent
defaults).

**Invariant to prove, not assert:** decision-neutrality via the harness `layer_trace`'s own
docstring names — run monitoring ON vs OFF, byte-identical trade ledger
(`scripts/analysis/v3_config_parity.py` is the established pattern). That full-corpus parity run has
**not** been executed even for `layer_trace` itself; its docstring tracks it as a follow-up and
explicitly warns against citing tests that do not exist. It must be **run here**, not cited.

### Gate 3 — A loadable 48-dim artifact *(the real blocker)*

Design decisions, not a task list:

- **Label object:** `multi_tp_walk` (SEM-017), recording the kernel and its parameters **inside the
  artifact**. Per P2 and F-088.
- **Not `rr_achieved`:** the F-022 stream. F-045 → INDETERMINATE; F-059 → AUC collapsed 0.605 → 0.512.
- **Schema binding by name** via `schema_resolver`. Never pad, truncate, or zero-fill.
- **Self-describing artifact:** `{model_id, schema_id, feature_order, schema_hash, label_kernel,
  label_kernel_params, cost_model, train_corpus_sha, n_train, training_distribution}`. The trainer
  already persists `training_distribution` for the gate; extend the same habit to the label side so
  *"what object was this trained to predict"* is answerable from the file rather than by archaeology.
  F-083 is the cautionary tale — a sealed contract declared an OOS split the driver never executed,
  and 1 of 8 declared evidence artifacts existed on disk.
- **Gate recalibration** to the new `dof` via `rr_confidence_probe.py`. Carrying `d_sq_cut: 40.4212`
  forward unchanged repeats F-044 in a new dimension.
- **Cost model:** F-082 measured XAUUSD research cost as ~11× too punitive under flat 12bps, *and*
  stop fills as free. Both corrections exist behind default-off gates (SEM-015 `ComponentCostModel`,
  SEM-016 `AdverseFill`). A new label run should declare which it used.

### Gate 4 — Enable

Flip `engine_runner.rr_fusion.enabled: true` only when **all four** hold:

1. Gate 1 shipped — abstention cannot emit Gaussian into the RR slot.
2. Gate 3 artifact **loads** — 48-dim, `is_loaded: True` *verified, not assumed*.
3. Gate 2 shadow stream shows a **measured ΔG001** for the RR channel.
4. Gate recalibrated to the new `dof`.

**Expectation to hold against.** F-059 is the only clean-label measurement of this family:
`rr_corr` 0.167, top-decile mean `y_rr` −0.154 vs random −0.434, overall **−0.436**. Real
discrimination on a losing book. A better label object may move that; it is not entitled to. **If
ΔG001 is null, the correct outcome is that fusion stays off** — and Gates 1–2 remain permanent wins
(a closed fail-open and a monitoring rail). Enablement is the goal, not a foregone conclusion.

---

## 8. Critical files

| Path | Relevance |
|---|---|
| `src/core/fusion_engine.py` | `compute()`: `expected` (~:310), weight resolution / `total_w` (~:480-498), `scores_dict` (~:536), `zone_gate_dead` (:390) |
| `src/core/engine_runner.py` | `EXPECTED_ENGINES` (:54), rr_fusion construction (:352-409), slot assignment (:758-798) |
| `src/config_layer/rr/rr_fusion.py` | `_passthrough` (:39) and its six call sites |
| `src/config_layer/rr/rr_pattern_miner.py` | `NanoInferenceEngine.predict`, `_confidence_bypass`, `RRPatternTrainer` |
| `src/config_layer/rr/rr_dataset_builder.py` | `extract_target` — label provenance |
| `src/engines/rr_engine.py` | polarity engine (docstring only) |
| `src/runtime/layer_trace.py` | monitoring rail |
| `src/runtime/backtest_v2.py` | :2576, :2973-2981 — emitter wiring |
| `src/research/model_runners/` | `runner.py`, `schema_resolver.py`, `adapters/rr_trained.py`, `contracts.py` |
| `src/research/oracle/multi_tp_walk.py` | SEM-017 production trade object |
| `docs/governance/semantic_os/file_identities.yaml` | `engines.candle_polarity_scorer` (~:1242) |
| `docs/governance/MODEL_INTENT_AUTHORITY_REGISTER.md` | §3.7 / §3.8 + `miar_registry.json` |

**Reference precedent (not authority):** `docs/implementation_plan/1-does-rrfusionlayer-ever-cryptic-frost.md`
— the F-044 plan. Its structure is the model to copy: the empirical probe was a **hard gate** with an
explicit STOP branch, under the rule *"No math-first promotion: Evidence → Finding → Math, never
Math → Finding → Evidence."*

---

## 9. Verification

1. **Baseline first** — done, recorded in §10. A pre-existing red is *reported*, never fixed mid-task.
2. **Ledger byte-identity (Gates 1 & 2).** XAUUSD M15 on `v2_htfcrt_2026_08` before/after: identical
   trades, identical rejection set, identical CRT event sequence, unchanged `config_hash` /
   `SCHEMA_HASH`. For Gate 1 this must hold *because* the path is unreachable — if it does not, the
   reachability analysis in §3.4 was wrong and the change stops. For Gate 2 it is the
   decision-neutrality proof, run ON vs OFF.
3. **Forced-reachability test** — what byte-identity cannot prove. Stub an `RRFusionLayer` that is
   `enabled` **and** `is_loaded`, returning each of the six abstain statuses; assert the `rr` slot
   carries base polarity (never `gaussian_score`), completeness does not fire, and `total_w`
   renormalises. This is the F-102 lesson: a dormant path needs **forced injection**, not observation.
4. **Keep green:** `test_rr_fusion_disabled_is_base_rr_identity`, `tests/test_rr_fusion_full_vector.py`,
   `tests/test_engine_runner_rr_fusion.py`, `tests/test_layer_trace.py`, `tests/test_doc_citations.py`,
   `tests/test_miar_registry.py`, plus `scripts/maintenance/check_governance_invariants.py --all`.
5. **Concurrency discipline** — see §10.

---

## 10. Session operational record

### 10.1 Worktree preflight (CLAUDE.md §1.5)

Branch `grokbotchanges`, HEAD `09ffcb1`. Interpreter confirmed `D:\Tradelatest\venv`, Python 3.12.14
(the `venv`, **not** `.venv` — the latter has no pytest). One unrelated stash present
(`stash@{0}: WIP on patch`).

**18 modified + 5 untracked files under `src/` and `configs/`**, from a concurrent session. §1.5
requires STOP-and-report on this. Investigated rather than assumed, and both overlaps proved
**disjoint** from every region this design touches:

- `src/core/engine_runner.py` — a single hunk at `:504-509`, changing
  `SignalAuditRecorder(debug_mode=...)` → `.from_prod_config(debug_mode=...)`. Target regions are
  `:54`, `:352-409`, `:758-798`. No overlap.
- `configs/production/v2_htfcrt_2026_08.json` — additive only: `signal_belief`, INR position-sizing
  keys across `portfolio`/`execution_planner`/`inout`, a `notes` append, and three new top-level
  sections (`signal_audit`, `trade_journal`, `multi_strategy_validator`). Touches **no** `rr_model`,
  `engine_runner.rr_fusion`, or `fusion_engine.weight_rr` key. `params` untouched ⇒ hash-neutral.

**Standing rule:** ~15 concurrent Claude sessions write to this repo. **Never `git add -A`.** Stage
only files this work edits; re-check `git status` before every commit.

### 10.2 Baseline — governance green floor, captured BEFORE any change

`venv/Scripts/python.exe scripts/maintenance/check_governance_invariants.py --all`

**Result: 13 failed, 574 passed, 1 skipped, 8 warnings in 526.99s (8:46).**

Pre-existing failures on this branch:

```
tests/governance/test_schema_version_registry.py::test_schema_version_symbol_census_is_fully_accounted_for
tests/test_current_findings.py::test_nonterminal_findings_are_fresh
tests/test_doc_citations.py::test_every_code_citation_resolves
tests/test_session_log.py::test_session_log_entry_count_is_bounded
tests/test_feature_math_lint.py::test_universe_reconciliation_with_census
tests/test_geometry_census.py::test_geometry_census_is_fresh
tests/test_geometry_census.py::test_adjudication_closed_against_fresh_census
tests/test_model_paths_literals.py::test_no_new_unauthorized_models_path_literals
tests/test_model_paths_literals.py::test_debt_is_exact_match_ratchet
tests/test_model_paths_literals.py::test_scanner_cli_exits_zero
tests/test_script_registry.py::test_grandfather_paths_match_stubs
tests/test_script_registry.py::test_grandfather_ratchet_live_universe
tests/test_corpus_read_lint.py::test_floor_is_green
```

**Observation (`UNVERIFIED` as to intent):** the script printed *"Governance-invariant gate FAILED
(Program E-001)"* yet **exited with code 0**. If `--all` is meant to be gating, a zero exit on 13
failures would be a silent-gap of the F-079/F-085 class — a skipped gate indistinguishable from a
passing one. Flagged for adjudication; **not** asserted as a defect, and not in scope here.

### 10.3 Rule conflicts encountered, and how they were resolved

| Conflict | Resolution |
|---|---|
| Harness asked for shell-based file editing (`sed`, heredocs); CLAUDE.md §1.6 forbids heredocs in this repo | Followed the **repo rule** — reads/searches via Bash, writes via Write/Edit. §1.6 requires stating which and why when they conflict; the repo rule is the one "paid for in repair cycles." |
| Plan-mode workflow defaults to Explore/Plan subagents; the request said no multi-agent | Followed the **explicit instruction**; all investigation was targeted grep/read, consistent with §1.2. |
| CLAUDE.md §6 mandates a SESSION LOG append every response; plan mode forbids writes outside the plan file | Logged in-response and flagged as **pending persistence** to `assistant_project.md` on the first write-enabled turn. Not silently skipped. |

---

## 11. Open questions

1. **Gate 2 breadth** — shadow-score all five phase-3 models on the first pass, or `rr_trained` only?
2. **Gate 3 corpus** — XAUUSD only (consistent with the standing probe corpus), or multi-instrument?
3. **`miar_entry: crt`** on `engines.candle_polarity_scorer` — genuine DOC_DRIFT, or does the field
   mean something other than "the MIAR entry describing this file"?
4. **Abstain-reason vocabulary** — reuse the six existing statuses verbatim, or collapse
   `disabled`/`model_not_loaded` into one?
5. **`check_governance_invariants.py --all` exit code** — is exit 0 on 13 failures intended?
6. **The blend** — does a Gate-3 model keep `0.5·gaussian + 0.3·ml + 0.2·confidence`, given the §3.1
   category-error argument, or emit its heads separately and let fusion weight them?

---

## 12. Explicit non-goals

- Renaming files, config keys, or the `rr` fusion slot key.
- Touching `UltronRiskGate` — economic RR stays sole-owned (F-048).
- Re-enabling `rr_fusion` on a flag flip alone, or on anything short of measured ΔG001.
- Any economic claim before Gate 4.
- Retraining as part of Gates 1–2.
- "Fixing" `partial_tp_breakeven_enabled` to match its name (F-088 pins it deliberately).

---

## 13. Findings referenced

| id | Relevance here |
|---|---|
| **F-022** | `opportunities.jsonl` is a detection stream, 36.8% self-consistent — the contaminated label source |
| **F-038** | RR was a Gaussian duplicate under gate-ON fusion; remediated by disabling `rr_fusion` |
| **F-044** | The confidence gate is mis-specified for its rank — 100% in-sample bypass; retrain alone cannot fix it |
| **F-045** | Contaminated-label kill-test INDETERMINATE; two E-001 corrections caught pre-registration |
| **F-048** | DecisionEngine RR gate removed; economic RR sole-owned by `UltronRiskGate` |
| **F-059** | Clean-label kill-test: KEEP_CANDIDATE, research-only, overall mean `y_rr` −0.436 |
| **F-076** | Schema 39→48 (v5.0); all six model families went stale, retrain deferred |
| **F-079** | Fail-closed on skipped-vs-absent measurement — the silent-gap class |
| **F-082** | XAUUSD cost ~11× too punitive *and* stop fills free; both corrected behind default-off gates |
| **F-083** | A sealed contract declared measurements the run never executed |
| **F-085** | Missing `global` kept a fail-closed guard unreachable — dormant-defect precedent |
| **F-088** | `forward_walk` measured the wrong trade object; `multi_tp_walk` reproduces production |
| **F-101** | Three independently-minted run ids in one backtest run |
| **F-102** | A gate failing open on exception; proven only by forced injection |
| **F-107** | Schema v6.0 rename — `trend_strength_z` / `candles_since_sweep`, bit-identical by position |

---

*End of document. No production code, configuration, or model artifact was modified in producing it.*
