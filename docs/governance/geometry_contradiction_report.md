# F-049 Gate-2G — Semantic-Adjudication Contradiction Report

_Point-in-time adversarial review (2026-07-08) of `geometry_semantic_adjudication.jsonl` (110 records,
Census v3). Every correction below was applied to the regenerated artifact; closure re-verified
(tests/test_gate2b_closure.py 5/5). No source remediation performed._

## Challenge outcomes (the 7 mandated classes)

**C1 — canonical sites mis-classified non-equivalent?** NONE found. Spot-checks re-verified:
`crt_feature_builder.py:123-125` are routed `candle_math.*` calls (canonical, dead);
`feature_pipeline.py:452` body/wick_size resolves to canonical F6 (the `wick_size` column IS F2, F-046);
`crt_engine_v2:2540` is the routed `_cm.body_ratio` call (F-047 refactor).

**C2 — equivalence labels inconsistent with the name-governance dimension: 17 CORRECTIONS.**
The relation taxonomy distinguishes MATHEMATICALLY_EQUIVALENT_VARIANT (governed NAME + equivalent math)
from SAME_MATH_DIFFERENT_NAME (equivalent math, non-governed name) and NON_EQUIVALENT_SAME_NAME.
First-pass labels conflated these on duplicate/replica sites:
- → **NON_EQUIVALENT_SAME_NAME (2):** `feature_math_drift_probe.py:55 wick_size` (F5 under the governed F2
  name) and `:56 body_ratio` (GD-001 form under the governed name) — probe replicas, but the *governed
  names* carry non-equivalent math (tooling context, reachability NO beyond reports).
- → **SAME_MATH_DIFFERENT_NAME (15):** flip-probe `body/tw/br/canon_ws`, drift-probe `canonical_ws`,
  `manual_backtest br/ws`, `encoder body/upper/lower`, `s09 prev_body/curr_body/body/total_range/body_pct`.

**C3 — name collisions hidden by formula similarity?** One confirmed earlier as F-050 (scorer
`retest_depth`); no additional hidden collisions found. `crt_sweep_taxonomy:126` floored `body_ratio`
retained as DOMAIN_POLICY_VARIANT (doc-cited Table-3 floor, dead code).

**C4 — reachability overstated: 1 CORRECTION (3 records).** GateIntelligence sites
(`gate_intelligence.py:223/256/257`): `decision_reachable` YES → **UNKNOWN**. Evidence:
`execution_planner.py:208` (Step 2 `reject_engine`) precedes `:246` (Step 5 GateIntelligence), and F-048
makes `run()=="execute"` structurally unreachable → the gate is **never evaluated in practice**; the
in-code chain exists but practical decision reachability is contingent on F-048 remediation. These are the
only remaining reachability UNKNOWNs (3).

**C5 — reachability understated (indirect consumers)?** Checked pipeline aux columns
(`upper_wick`/`lower_wick` :186-187): no downstream reader found (grep) → NO stands. TR chain
(:263-266) → `atr_14` → canonical `atr` → training YES stands (upgraded during Gate 5).

**C6 — multiple DERIVATION_IDs = one implementation?** `feature_monitor.py:301 ×2` and
`test_feature_pipeline.py:571 ×2` verified as DISTINCT statements (separate demo/fixture dict literals) —
legitimately separate records. Probe replicas of GD-001 across 2 files are distinct sites grouped by
FAM-02 (family = the dedupe mechanism, correct).

**C7 — one DERIVATION_ID grouping multiple implementations?** None (census v3 single-pass guarantees
one site per record; regression-tested).

## Preserved contradiction seeds (NOT remediated — Gate-6/Phase-B inputs)
- **GD-001/GD-002** live-hook body_ratio/wick_size (NON_EQUIVALENT_SAME_NAME, decision-reachable-in-code).
- **Table-3 floored-wick family** (FAM-04: crt live diagnostic + dead taxonomy twin; doc-cited floor).
- **F-050** scorer/engine cross-candle `retest_depth` + sibling `disp_str = wick_size/atr` — **Gate-5
  lineage now CONFIRMS the training chain** (see below).
- **CS-2** zero-range policy split (0.0 vs 0.001-floor vs skip-None) — three policies, no canonical
  decision yet.
- **CS-3** F2-as-volume proxy — **Gate-5 resolves as LATENT** (no majority-zero-volume corpus in
  `data/*_M15.csv`; the path never fired on repository corpora; conditional on future corpora).

## Gate-5 lineage resolutions folded into the artifact
- **F-050 chain CONFIRMED (static):** `crt_engine_v2.py:1372` caches the cross-candle retrace as
  `"retest_depth"` (comment `:1368-69`: *"Uses displacement-retrace definition … to match the empirical
  calibration in CRTGaussianScorer"* → the cross-candle definition is **internally intentional**; the
  defect is the **name collision** with FM-021) + `"disp_strength": disp.wick_size/atr` (collides with
  FM-020) → snapshot `:1121-1127` → `opportunities.jsonl` → `stage1_dataset_builder.py` →
  `master_{crypto,forex,multiasset}_training.jsonl` → `trainer.py:807` (BitNet chain). Economic exposure
  bounded by **F-004** (BitNet `use_bitnet:false` on the active config). Train/serve-skew risk if any
  model trained on cached values is ever scored with pipeline FM-021/FM-020 values.
- **Model artifacts embed pipeline canonical features** (rr_model.json 49k rows F-044; zone_registry
  38-dim F-041) → canonical/pipeline records artifact_reachable YES.
- **Live-hook records:** runtime logs only; backtests bypass → NO model-artifact path.
- Remaining reachability UNKNOWNs after Gate 5: **3** (the C4 GATEI records, F-048-contingent).
