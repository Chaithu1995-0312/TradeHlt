# Plan — Feature Lineage Matrix + wick_size semantic reconciliation (phased)

## Context

Started as a Feature Lineage Matrix (`OHLCV → Formula → Feature → State → CRT → Gaussian → ZoneGate
→ RR → Fusion Weight`). Building it source-verifiably surfaced the real risk: **`wick_size` /
`body_ratio` semantic divergence across code paths.** Verifying the CRT engine internals **corrected
the severity**:

- **CRT engine** ([crt_engine_v2.py:105-114](src/config_layer/crt_engine_v2.py:105)): `wick_size = high - low`,
  `body_ratio = body/(high-low)` — **identical to the batch pipeline** ([feature_pipeline.py:444](src/features/feature_pipeline.py:444)).
- **Only outlier:** single-row [`crt_feature_builder.py:110`](src/features/crt_feature_builder.py:110)
  `wick_size = (high-low) - body_size` → `body_ratio = body/total_wick` (unbounded).
- **Canonical = `body/range`** (bounded [0,1]; the only metric a `0.70` gate is coherent against, and
  what CRT+pipeline both run). The outlier's only consumer is `build_bitnet_features` → BitNet, which
  is **OFF on active config** (`use_bitnet:false`). ⇒ **dormant latent bug**, not an active one.
  (`crt_feature_builder` is also stale v2.0: builds 35 keys, would `AssertionError` vs the 38-schema —
  likely already dead on the 38-vector path; confirm in Phase 1.)

Correction recorded (E-001): the earlier "three interpretations, ambiguous, ask which is canonical"
framing was an **overclaim** — it is **two** definitions, CRT matches the pipeline, canonical is
`body/range`, and the divergent path is dormant.

**Runtime truth (active `v2_multi_2026_04`, source-verified):** live Gaussian = 3-feat heuristic
(`gaussian_impl:heuristic`); `rr_fusion.enabled:false` (RR = base geometric polarity); `use_bitnet:false`;
ZoneGate 38-key but NON_PIVOTAL (F-036/F-041); fusion weights crt 0.4 / gaussian 0.2 / zone 0.2 / rr 0.2
(config wins over code defaults 0.4/0.3/0.2/0.1); 4-engine fusion OFF in research backtests (F-037).

## Phased approach (evidence-gated — §6.5 "evidence outranks doctrine; parity-prove before freezing")

### Phase 1 — Divergence audit (READ-ONLY diagnostic; the highest-leverage step)
`scripts/analysis/wick_semantics_audit.py` over ~1–2k real candles (BNBUSDT + one FX), computing
`body_ratio` three ways — CRT-Candle property, batch-pipeline column, single-row builder — and
reporting: max/mean divergence, how many bars cross the `0.70` gate under each, and **whether
`build_bitnet_features` is reachable on any live path** (grep call-sites; confirm dead-vs-guarded).
Expected: CRT ≡ pipeline (Δ0), single-row diverges, single-row feeds only BitNet(off). Output a small
JSON under `docs/analysis/`. **This gates Phases 2–5** — if reachable+live, severity escalates.

### Phase 2 — Unify the primitive (the agreed core of your CandleMath idea)
Introduce one immutable primitives module — `src/features/candle_math.py` — with
`body_size/candle_range/upper_wick/lower_wick/total_wick` as pure functions (mechanism in code,
never config, never `eval`). Route all three paths through it so divergence is **structurally
impossible**:
- CRT `Candle.wick_size`/`body_ratio` → call `candle_math` (byte-identical: already `high-low`).
- Batch pipeline `body_size`/`body_ratio` → same (byte-identical).
- **Fix** `crt_feature_builder.py:110` to the canonical `body/range` (this is the actual bug fix;
  behavior-changing **only** if BitNet is later enabled — parity-proved inert on active config since
  BitNet is off).
Add `tests/test_candle_math.py` (primitive identities + cross-path equality on a candle battery incl.
your `O100/H110/L95/C108 → 0.533`). No config hash change (no `params` edit).

### Phase 3 — Fusion weights: config-only, fail-fast (your "no runtime defaults" rule)
Remove the embedded weight defaults so production policy has one authority. `engine_runner` already
uses `_cfg_require` for the four weights ([:384-390](src/core/engine_runner.py:384)); the drift is the
`ENGINE_RUNNER_DEFAULTS` dict ([:107-111](src/core/engine_runner.py:107)) — delete the weight keys (or
assert they're never the source), so a missing `fusion_engine.weight_*` raises at load, not silently
falls back to `0.3/0.1`. Regression test: missing key → `KeyError`/`ValueError`. Scope-limited to
fusion weights this task (a repo-wide "no production-policy defaults" sweep = separate program, filed
as a follow-up — it's large and needs the census instrument, §6.5).

### Phase 4 — Feature Lineage Matrix (the original deliverable, on the reconciled base)
Publish the 38-row matrix (OHLCV→Formula→Feature→State→CRT→Gaussian→ZoneGate→RR→Fusion-weight, every
cell file:line-cited) to **WHO** = [`docs/topics/model-intent-and-feature-ownership.md`](docs/topics/model-intent-and-feature-ownership.md)
(new "Feature Lineage Matrix" section) + machine-readable `feature_lineage:` block in
[`active_models.yaml`](active_models.yaml) (additive, `authority:none`). Branch-scope F-004 in
[`docs/current-findings.md`](docs/current-findings.md) + fix its `:1804`→`:1731` citation. Record the
wick_size reconciliation as a finding/Discussion entry.

### Phase 5 — (DEFERRED / your call) Formula registry as a 3rd authority (WHAT)
Your `configs/formulas/market_ontology.yaml` — CONFIG-**DECLARED**, CODE-**EXECUTED** (a
`FORMULA_REGISTRY` of named lambdas; YAML is the authority, a parity test asserts YAML formula ==
Python impl; **never** `eval`). Clean separation: `active_models.yaml`=WHO · `production/*.json`=HOW ·
`market_ontology.yaml`=WHAT. This is the CONFIG_DRIVEN graduation of feature *compositions*
(`body_ratio.denominator ∈ {range, total_wick, ...}`) enabling no-code permutation research. **Real
but large**, and per §6.5 it earns adoption only after Phases 1–2 prove the primitive layer — so it's
proposed, not committed. Primitives stay immutable-in-code either way.

## TruthConflicts / corrections to record

1. **wick_size** — RESOLVED: 2-way (not 3), canonical `body/range`, single-row builder is the bug,
   dormant on active config. Fix in Phase 2; audit-confirm in Phase 1.
2. **Fusion-weight config vs code default** (`gaussian 0.2/rr 0.2` vs `0.3/0.1`) — removed in Phase 3.
3. **F-004 BitNet branch-scope** (user-approved) + citation fix — Phase 4.
4. **`crt_feature_builder` stale v2.0 (35-dim)** — confirm dead-vs-guarded in Phase 1; note (don't delete, §6.2 r4).

## Files touched (by phase)

- P1: `scripts/analysis/wick_semantics_audit.py` (new, read-only), `docs/analysis/*.json` (output).
- P2: `src/features/candle_math.py` (new), `src/config_layer/crt_engine_v2.py` (Candle props → primitive),
  `src/features/feature_pipeline.py` (→ primitive), `src/features/crt_feature_builder.py` (bug fix),
  `tests/test_candle_math.py` (new).
- P3: `src/core/engine_runner.py` (drop weight defaults), `tests/` (fail-fast regression).
- P4: `docs/topics/model-intent-and-feature-ownership.md`, `active_models.yaml`, `docs/current-findings.md`,
  CLAUDE.md §6.2 index; `tests/test_active_models_registry.py` (extend for `feature_lineage`).
- P5 (deferred): `configs/formulas/market_ontology.yaml`, `src/features/formula_registry.py`, parity test.

## Verification

- P1: run the audit; read its JSON; confirm the reachability grep.
- P2: `pytest tests/test_candle_math.py` + determinism — re-run a BNBUSDT backtest, assert **byte-identical
  ledger** (proves the primitive routing is inert on active config, BitNet off) before/after.
- P3: `pytest` the fail-fast regression; confirm active config still loads (keys present).
- P4: `pytest tests/test_topic_docs.py tests/test_active_models_registry.py tests/test_current_findings.py
  tests/test_doc_citations.py`.
- Every phase: §7.4 SESSION LOG to `assistant_project.md` + Documentation-Drift audit entry for the
  wick_size correction and F-004 branch-scope (§6.2).

## Out of scope (this task)

- No threshold recalibration (`body_ratio_min=0.70` etc.) — the canonical definition is what 0.70 was
  tuned against, so no recal is needed; any future denominator change (Phase 5) would require it and is
  explicitly gated.
- No re-enabling BitNet/rr_fusion/ml-gaussian; no fusion retune; repo-wide default-removal sweep deferred.
