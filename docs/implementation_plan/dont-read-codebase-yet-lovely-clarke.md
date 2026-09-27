# Model-Layer Rewrite + Model Registry — Design Plan (discussion draft)

**Date:** 2026-09-23 · Branch `grokbotchanges` · Active `v2_htfcrt_2026_08`
**Mode:** design only. No agents. Only files read: the pasted session summary + three
`docs/implementation_plan/` precedents (BitNet `tranquil-pretzel`, Gaussian `recursive-lagoon`,
RR `cozy-pie`). Everything cited from them is *their* claim, not re-verified here.

---

## Context

The summary shows the model layer is ungoverned at the naming and contract levels:
- **23 models**, 4 different input dimensions for the same bar (3 / 6 / 38-declared-48 / 48).
- Only Gaussian and BitNet have MIAR in/out declared. Nothing else has a Semantic OS noun.
- Each of the three model families (Gaussian, BitNet, RR) independently hit the **same four
  failures**:
  1. one name covers several objects;
  2. the training population differs from the population the model is served on;
  3. the label answers a different question than the model is supposed to;
  4. an absent or failed vote is silently replaced (a borrowed score, a neutral 0.5, or a zero).
- The 19-specialist + 2-arbiter ensemble is the **measurement instrument** needed for the
  conditional-expectancy table (summary §15). It is not a book improver.

**The intended outcome:**
- one **model registry** that every model is declared in before it runs;
- one **model contract** that makes the four failures structurally impossible;
- a **shadow harness** that runs all declared models without touching decisions.

---

## Design principles (merged from the three precedents — not new)

| # | Principle | Source |
|---|---|---|
| P1 | Keep the estimator, the abstention gate and the consumer separate | RR P1 |
| P2 | Declare the label object inside the artifact (`multi_tp_walk`, never `rr_achieved`) | RR P2, BitNet P2 |
| P3 | Bind features by name through `schema_resolver`; never positionally | RR P3, BitNet P3 |
| P4 | An absent vote is a typed `ABSTAIN`, never a substitute or a neutral fill | RR P4, Gaussian §4.3 |
| P5 | Train on the distribution you serve; declare the reference population as a registered object | BitNet P1, Gaussian C1 |
| P6 | Outputs have a declared scale type (score / tail-prob / calibrated prob); no cross-model delta without a declared metric | Gaussian §4.4 |
| P7 | Correctness ≠ authority. Only measured ΔG001 grants weight | §6.5, all three |

---

## Phase 0 — Model Registry (declarative, zero runtime change)

**Rule: extend existing surfaces; do not create a fifth one (§6.2 rule 1).** Today three
surfaces already exist:
- `miar_registry.json` holds intent;
- `MODEL_CATALOG` (in `src/research/model_runners/`) holds runtime and runnability;
- `active_models.yaml` holds the descriptive mirror.

The registry becomes **one semantic id joining all three**, plus a floor test that they agree.

**Registry row fields:**
- **Identity:** `semantic_id` (`L{layer}_{BLOCK}_{FAMILY}_{ARM}`), `miar_id`, `catalog_model_id`,
  and the Semantic OS noun id.
- **Inputs:** `input_features` as FM ids / canonical names, not positions. `input_schema_hash`.
  `serve_domain`, which is one of `ALL_BARS`, `CRT_STATE:{X}`, or `TRADE_OPENED`.
- **Training basis:** `reference_population_id`, `label_contract_id` (or `null` for heuristics),
  and `cost_model_id`, which must string-match research provenance (fixes summary §5).
- **Output:** `output` = {name, range, `scale_type`, `abstain_reasons[]`}.
- **Authority and lifecycle:** `authority` ∈ {NONE, SHADOW, FUSION_VOTE, VETO}.
  `status` ∈ {DECLARED, SHADOW_RUNNING, EVIDENCE, AUTHORITY}. `evidence` (F-ids).
- **Artifact:** `artifact` = {path, sha256, trained_on_schema}.

**Floor test (sketch):**
- every `MODEL_CATALOG` entry has a registry row;
- every row with `authority > SHADOW` has a MIAR entry and measured-ΔG001 evidence;
- `input_schema_hash` matches the live `SCHEMA_HASH`, or the row is flagged `STALE_SCHEMA`.
  This check catches BitNet's broken enable path mechanically.

**Seed rows:** the 23 existing models (summary §9) plus the 19 specialists and 2 arbiters
(summary §12). All seed as `DECLARED`, authority `NONE`, except the three models live today:
- CRT;
- the heuristic Gaussian, as `FUSION_VOTE`;
- polarity RR, as `FUSION_VOTE`.

## Phase 1 — One model contract

- **Interface:** `score(bar_ctx) -> ModelOutput | Abstain`.
  - `ModelOutput` carries `value`, `scale_type`, `semantic_id`, `input_schema_hash`.
  - `Abstain` carries a reason drawn from the registry row.
- **Input binding:** the harness resolves inputs by name via `schema_resolver`. It refuses on a
  hash mismatch; it never pads or truncates.
- **Serve domain:** outside the declared `serve_domain`, the harness records `NOT_IN_DOMAIN`
  (a ragged panel). It never calls the model there.

## Phase 2 — Shadow harness (two hosts, different questions)

| Host | Where | Population | Answers |
|---|---|---|---|
| **H2 (primary)** | `src/research/model_runners/` per-bar runner | every bar × direction (~94k units, XAUUSD) | how models behave and agree; feeds the §15 table |
| **H1** | `layer_trace` rows on the evidence plane (L5/L6), `module="shadow:<semantic_id>"`, no enum change | TRADE_OPENED bars only (n≈3–30) | what each model said on real entries — permanently underpowered, and that is a finding |

- **Decision neutrality is proven by running, not by citing:** monitoring ON vs OFF, with a
  byte-identical ledger (the `v3_config_parity.py` pattern).
- **New JSONL stream:** needs a `CC-*` class in `jsonl_claim_catalog.yaml` before anyone asserts
  what it proves.

### H2 design — corpus score store + time-range monitor (settled 2026-09-25, not yet built)

**User decisions (chat, 2026-09-25):**
- D1: Parquet under `results/`, queried read-only with DuckDB (CLAUDE.md §4 2026-09-17 exception).
- D2: store raw scores; apply thresholds when the scores are read.
- D3: all catalog models.
- D4: when a stop and a target are both touched in one bar, record both outcomes.

**Grounding (verified 2026-09-25):**
- `MODEL_CATALOG` has **19 rows**. The "23" above is the pre-join count (K17).
- 16 rows are runnable. 3 are blocked: `llm_gate`, `strategies`, `engine_runner`.
- 4 need an artifact: `tradenet`, `rr_trained`, `envelope`, `gaussian_ml`.
- `bitnet` hits gap 1 below.
- "All models" = all 19 get rows. A blocked model gets one `BLOCKED` row per run, not one per bar.
- A per-model runner already exists: `research.model_runners.run_model`, record schema `model_runner_v1`. H2 **extends** it to v2; it does not add a new runner.

**Tables (one Parquet dataset each, joined on `run_id` + `bar_ts`):**

| Table | Grain | Fields |
|---|---|---|
| `run_header` | 1 row per run | `run_id`, instrument, csv path+sha256, window, config path+sha256, `ACTIVE_VERSION`, feature schema version + `SCHEMA_HASH`, full snapshot of `feature_pipeline` and `crt_engine` sections, code provenance, `drift_vs_active` (keys that differ from the active config) |
| `bar_state` | 1 row per bar | `bar_ts`, `bar_idx`, OHLCV, CRT state + event, HTF state, objective status, session ordinal, the 48 canonical features (wide) |
| `model_score` | bar × direction × model | `semantic_id`, `model_id`, `direction` (`LONG`/`SHORT`/`NONE` for direction-free models), `status` ∈ {`OK`, `ABSTAIN`, `NOT_IN_DOMAIN`, `ERROR`, `BLOCKED`}, `reason`, `value` (dominant scalar), `scale_type`, `native_json`, `input_schema_hash`, `serve_domain` |
| `outcome` | bar × direction × geometry | entry / SL / TP1 / TP2 / 1R; `touched_sl`, `touched_tp1`, `touched_tp2`; `same_bar_ambiguous`, plus the bar where it happens; `gross_R_sl_first`, `gross_R_tp_first` |

**Read-time layers (DuckDB views, no re-run):**
- **Threshold profile.** Rows are `metric`, `op`, `threshold`, `profile_id`, `version`.
  - `active_mirror` is built at read time from the active config's own keys. It is never copied.
  - Other profiles are versioned files under `configs/research/`.
  - A score passes when `value op threshold`.
- **Cost.** `net_R = gross_R − cost_R(cost_model_id)`, using the closed `COST_MODEL_IDS` set. The default is `sem015_component_xauusd`.
- **Monitor query.** Inputs are instrument, from/to, profile and cost model. Output is the `run_header` plus a per-bar join of `bar_state` × `model_score` (pass/fail) × `outcome` (both orderings when ambiguous).

**Size:** XAUUSD 47,197 bars × 2 directions × 19 models ≈ 1.8M `model_score` rows.

**Build order (each step is its own authorized turn):**
1. Runner v2 record + Parquet writer. v1 JSONL output stays byte-identical.
2. `bar_state`: read CRT/HTF states from an existing CRT-rail run's `layer_trace` rows before recomputing anything.
3. `outcome` via `multi_tp_walk`. It already takes `tie_break` ∈ {`TIE_BREAK_PRODUCTION` (SL-first per F-088), `TIE_BREAK_OPTIMISTIC`}, and `oracle/labeler.py` already labels both (`TIE_BREAKS`). Reuse the labeler; add only the `same_bar_ambiguous` flag.
4. Threshold-profile reader + DuckDB views.
5. Monitor CLI, with SITS registration and a `CC-*` class for the new streams.

**Verification:**
- Planted-signal instrument gate (F-086 pattern).
- Runner v1 artifacts unchanged.
- CRT-0003 (`run_20260916_225925`, 2025-02-25 15:45) must show `same_bar_ambiguous = true`, with TP-first +2R and SL-first −1R. Its fill bar has low 2933.07 < SL 2933.21 and high 2938.05 > TP2 2936.75.

**Open:**
- Which models are direction-free? This may need a `direction_mode` catalog field.
- Should `bar_state` come from the CRT rail only, or also from Engine-rail replays? This depends on the rail names.

## Phase 3 — Specialists and arbiters

- **Build the 19 block heuristics first.** They need no labels and no training.
- **Then the L5 temporal tracker:** `disagreement_index` and `drift_flag`.
- **Then the L6 arbiter**, research-only.
- **Variant arms** (MLP / NB / DENSITY / CRT) come later, each with its own registry row and
  label contract.

## Phase 4 — Conditional-expectancy table (summary §15)

- **Shape:** 19 blocks × quartiles = 76 cells.
- **Outcome:** `pnl_rr_net` under `ComponentCostModel`.
- **Discipline:** pre-registered, walk-forward, Bonferroni, n reported per cell.
- **Stratifier:** the CRT state is a stratifier, not a selector.

## Phase 5 — Family re-founds, each gated on its own precedent (unchanged)

- **RR:** Gates 1–4 from `cozy-pie`. Abstention comes first; the 48-dim artifact is the real blocker.
- **Gaussian:** Option B (density/novelty) from `recursive-lagoon`. It needs constraints C1–C4 and
  the reference population registered first.
- **BitNet:** Option B (toxicity veto) from `tranquil-pretzel`.
  - Move the call site to order 8.
  - Read `disagreement_index` / `drift_flag` from L5.
  - Stay in parallel with the ensemble, not stacked on it.

## Pre-existing gaps to clear before any per-bar run (recorded, not yet authorized)

1. BitNet: `LEGACY6_KEYS` `candles_since_sweep` vs the injected `candles_since_retest` → KeyError.
2. `enc_canonical38_v1`: `dim()` returns 48, while `DEFAULT_INPUT_DIM` is 38.
3. `CRTGaussianScorer` has two unconditional `print()` calls, which would produce ~94k lines per run.
4. Stale v5.0 / 38-dim labels in `feature_pipeline.py`, `docs/topics/feature-schema.md` and `CLAUDE.md`.

## Naming collision to resolve BEFORE Phase 0 (new observation)

The `L{n}` prefix already means **three different things**:
- feature-DAG layers `L0–L6`;
- `layer_trace` layers `L0–L9` (L5–L6 = evidence plane);
- the proposed model layer in `L{layer}_{BLOCK}_...`.

"L5 populated" in summary §12 conflates the first and third. The model id needs a distinct
prefix, or an explicit declaration that the model layer = the feature-DAG layer of its inputs.

## Verification (per phase, once implemented)

- **Before any change:** baseline `check_governance_invariants.py --all`. The last recorded
  result was 13 failed / 574 passed, and the script exited 0 on failure (flagged in `cozy-pie`).
- **Phase 0:** the new registry floor test, `test_miar_registry.py`, `test_active_models_registry.py`.
- **Phase 2:** byte-identical XAUUSD ledger with the harness ON vs OFF, plus a forced-injection
  abstain test (the F-102 lesson).
- **Phase 4:** a planted-signal instrument gate first (the F-086 pattern). A null from a broken
  harness looks identical to a real null.
