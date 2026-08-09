# Encyclopedia E2 — Research Utilities Index

**Phase:** E2  
**Status:** DONE (category + package + driver index — not 269 prose essays)  
**Date:** 2026-08-07  
**Parent:** [Chapter 24](../24-repository-encyclopedia.md) · [Encyclopedia index](README.md)  
**Architecture narrative:** [Chapter 19](../19-research-programs.md) · [Chapter 20](../20-research-platform.md)

## Scope

| Tree | `.py` files | Role |
|---|---:|---|
| `src/research/` | **143** | Kernels, hypotheses, measurement, adapters — importable library |
| `scripts/research/` | **126** | Thin CLI drivers that write `results/research/**` |
| **Total E2 surface** | **269** | Research-only authority unless a finding says otherwise |

**E2 design rule (from charter):** index by **category + entry point + program link**, not a narrative chapter per file. Deep math stays in pre-registrations + findings.

**Group:** mostly **A-adjacent research** for kernels used by Programs 1–9; **D** for one-off scripts.  
**Relevance:** almost all **RESEARCH** — no production fusion weight without §6.5 Authority Ladder.

---

## How to use this index

1. Start from a **Program** (table below) → kernel + driver + artifact.  
2. Or start from a **`src/research/` package** → file list.  
3. Or start from a **script cluster** → which CLIs exist.  
4. Confirm claims in `docs/current-findings.md` + `results/research/**`.  

**Rule:** a claim without an artifact path (or finding Evidence) is a hypothesis, not a result.

---

## 1. Program → code → driver → artifact (primary map)

| Prog | Question (short) | Primary `src/research` | Typical `scripts/research` drivers | Typical artifacts |
|---|---|---|---|---|
| **1** | Directional edge on crypto majors? | `qualification.py`, `hypotheses/*`, `adapters/spine_signal_source.py`, `controls/*`, `costs.py` | `qualify_majors.py` | `results/research/qualification/` |
| **1b** | Conditional pockets? | `conditional_entropy_grid.py` | `phase_b_conditional_entropy.py` | `results/research/phase_b/` |
| **1c** | RETEST selection skill? | `selection_effect.py` | `phase_s_selection_effect.py` | `results/research/phase_s/` |
| **1d** | Exit/cost grid? | `exit_grid.py`, `costs.py` | `phase_d_exit_grid.py` | `results/research/phase_d/` |
| **2** | Sweep→disp→retest asymmetry? | `structural_asymmetry.py`, `adapters/structural_event_source.py` | `phase_e_structural_asymmetry.py` | `results/research/phase_e/` |
| **3** | H1/H4 rescue? | `resample.py`, adapters + qualification | `build_resampled_data.py`, `qualify_htf.py` | `results/research/qualification_htf/` |
| **P&F / IC** | Interpreter edge? | `src/interpreters/*` + `qualification.py` | `qualify_interpreter.py` | interpreter shadow results |
| **4** | Vol-regime level? | `regime_conditioning.py` | `qualify_regime_conditioning.py` | `results/research/regime/` |
| **4b** | Markov transition? | regime observers + conditioning | `qualify_regime_transition.py` | regime_transition artifacts |
| **4d / transitions** | Compression→expansion info? | `candle_state/*`, `hypotheses/compression_breakout.py` | `transition_information.py`, `qualify_transitions.py` | `results/research/candle_state/` |
| **5** | Cross-sectional RV? | `cross_sectional.py` | `qualify_cross_sectional.py` | `cross_sectional_*.json` |
| **6 / 6b** | Carry signal / harvest? | `cross_sectional.py` + carry configs | `qualify_carry.py`, `qualify_harvest.py` | `carry_*.json`, `harvest_*.json` |
| **8** | Weekly sweep? | `weekly_sweep/weekly_range.py`, `hypotheses/weekly_sweep_reversal.py` | `qualify_weekly_sweep.py` | `results/research/weekly_sweep/` |
| **9** | M5 multi-TF + OCO straddle? | `candle_state/m5_incremental.py`, `mtf_conjunction.py`, `hypotheses/compression_box_straddle.py`, `resample.py` | `m5_mtf_information.py`, `qualify_m5_straddle.py`, `verify_m5_resample_parity.py` | `results/research/m5_mtf/` |
| **FX gen.** | Crypto null on FX? | same M4 stack | `qualify_fx_metals.py`, `qualify_xauusd.py` | FX qualification trees |
| **Zone audits** | ZoneGate labels / inertness? | `zone_mapping/*`, `zone_label_audit.py` | `zone_label_audit.py`, `diagnose_zone_inertness.py`, `discover_zones.py`, … | zone_* under results |
| **RR clean labels** | Honest RR labels? | `clean_labels/*`, `measurement/forward_walk.py` | `rr_l3_label_generation.py`, `rr_shadow_value.py`, `rr_kill_test_clean_l3.py` | `results/rr_research/` etc. |
| **MSIP hyps** | State vector info? | (shadow in `src/msip` — E1) | `run_h_msip_001.py`, `run_h_msip_002.py` | `results/research/h_msip_001/`, `h_msip_002/` |
| **Gate measure** | Fusion gate veto rate? | spine adapters | `gate_measurement_m_gate_01.py` | gate_measurement_* |

Shared **M4 gate** implementation center of gravity: `src/research/qualification.py` (+ `costs.py`, `measurement/*`, `controls/*`).

---

## 2. Shared research spine (load-bearing root modules)

These top-level modules under `src/research/` are reused across many programs:

| File | Purpose | Relevance |
|---|---|---|
| `qualification.py` | M4 QualificationGate — absolute expectancy, controls, permutations, PROMOTE/REJECT | LIVE-research |
| `costs.py` | Round-trip cost model (e.g. 12 bps standard) | LIVE-research |
| `exit_grid.py` | SL×TP grid evaluations | P1d |
| `cross_sectional.py` | Panel / relative-value kernel | P5/P6/P6b |
| `conditional_entropy_grid.py` | Entropy + economics grid | P1b |
| `selection_effect.py` | Selected vs rejected retest decomposition | P1c |
| `structural_asymmetry.py` | Funnel asymmetry vs controls | P2 |
| `regime_conditioning.py` | Regime × consumer matrix | P4/4b |
| `resample.py` | Deterministic calendar OHLCV resampler | P3, P9 |
| `experiment_spec.py` | Experiment specification objects | ERP hygiene |
| `config.py` | Research config load helpers | all |
| `contracts.py` | Research contract types | ERP |
| `runner.py` / `cli.py` | Generic research runner / CLI glue | ops |
| `registry.py` | Research registry helpers | ERP |
| `provenance.py` | Run provenance stamps | hygiene |
| `forensics.py` | Trade/path forensics helpers | diagnostics |
| `goal_alignment.py` | Goal-layer alignment checks | Ch.01 link |
| `process_diagnostics.py` / `process_characterization.py` | Process / entropy diagnostics | P1b sanity |
| `indicators.py` | Research-side indicators (not production feature authority) | support |
| `band_validation.py` | Band / threshold validation helpers | FM/feature research |
| `shape_statistics.py` | Shape library statistics | IC tracks |
| `mt5_cost_calibration.py` | FX/metals cost calibration | F-035 class |
| `xau_metals_protocol.py` | XAU metals research protocol | metals track |
| `zone_label_audit.py` | Zone label honesty / F-041B class | ZoneGate |
| `__init__.py` | Package marker | — |

**Authority:** research kernels must not silently become production fusion weights. Production path remains EngineRunner spine (E1).

---

## 3. `src/research/` package encyclopedia

### 3.1 `adapters/` (4)

| File | Purpose |
|---|---|
| `spine_signal_source.py` | Research adapter: CRT spine entries as signal source for M4 |
| `structural_event_source.py` | Sweep/disp/retest structural events (Program 2) |
| `shape_signal_source.py` | Shape/interpreter signal source adapter |
| `__init__.py` | Package exports |

### 3.2 `controls/` (3)

| File | Purpose |
|---|---|
| `random_baseline.py` | Random-uniform / shuffle controls |
| `always_long.py` | Long-only / market control |
| `__init__.py` | Exports |

Every economic PROMOTE path is expected to beat appropriate controls (program-specific).

### 3.3 `hypotheses/` (8) — Stage-2 economic consumers

| File | Purpose | Programs |
|---|---|---|
| `expansion_breakout.py` | Directional expansion breakout consumer | P1, P3, P4 toys |
| `mean_reversion.py` | Mean-reversion consumer | P1, P4 |
| `compression_breakout.py` | Compression→expansion directional consumer | P4d Stage-2 |
| `compression_box_straddle.py` | **Sole** P9 Stage-2 OCO straddle consumer | **P9** |
| `weekly_sweep_reversal.py` | Weekly sweep reversal consumer | **P8** |
| `spine_hypothesis.py` | Spine entry hypothesis wrapper | P1 spine arm |
| `market_shape_hypothesis.py` | Market-shape hypothesis | IC / shape |
| `__init__.py` | Exports | |

### 3.4 `candle_state/` (7) — multi-TF state & Program 9 Stage-1

| File | Purpose |
|---|---|
| `encoder.py` | Candle-state encoding |
| `mtf_conjunction.py` | M15∧H1∧H4 (and extensions) conjunction builder |
| `transition_target.py` | Forward vol/range/transition targets (Program 4 kernels) |
| `m5_incremental.py` | M5-base keys + incremental information gate (**P9 Stage-1**) |
| `info_robustness.py` | Information robustness helpers |
| `reporting.py` | Stage-1 reporting |
| `__init__.py` | Exports |

### 3.5 `measurement/` (4) — honest outcomes

| File | Purpose |
|---|---|
| `forward_walk.py` | Intrabar-aware forward walk labels (anti-F-022 contamination) |
| `metrics.py` | Research metrics (E, PF, …) |
| `bootstrap.py` | Bootstrap CIs |
| `__init__.py` | Exports |

**MC path:** schema in governance; this package is scaffolding toward sealed `MC-*` (still OPEN — Ch.20).

### 3.6 `clean_labels/` (3)

| File | Purpose |
|---|---|
| `builder.py` | Build clean labels from geometry + forward_walk |
| `protocol.py` | Clean-label protocol freeze |
| `__init__.py` | Exports |

### 3.7 `weekly_sweep/` (2)

| File | Purpose |
|---|---|
| `weekly_range.py` | Calendar-locked weekly range + sweep geometry (P8) |
| `__init__.py` | Exports |

### 3.8 `zone_mapping/` (13)

Zone census, historical mapping, rare-zone evals, Gaussian-family shadows, CRT×zone crosstabs — research audits of ZoneGate / geometry (F-036, F-041 class). Files:

`boundary_hypothesis_eval.py`, `build_corpus_zone_map.py`, `collect_trade_opened_features.py`, `crt_zone_crosstab.py`, `displacement_zone_event_study.py`, `gaussian_delta_gap_eval.py`, `gaussian_family_shadow_eval.py`, `historical_zone_mapper.py`, `rare_zone_context_filter_eval.py`, `rare_zone_detection_eval.py`, `rare_zone_fa_characterization.py`, `zone_census.py`, `__init__.py`.

### 3.9 `episodes/` (13+)

Episode store / schema / tensors / projectors for trajectory research (not the live single-candle spine).

Core: `builder.py`, `events.py`, `flat.py`, `policy.py`, `protocol.py`, `query.py`, `schema.py`, `store.py`, `tensors.py`, `projectors/detection.py`, `projectors/spine.py`, `__init__.py`.

### 3.10 `ic002_entry_evolution/` (5)

Trajectory build + separation eval for entry-evolution interpreter candidates: `build_trajectories.py`, `evaluate_separation.py`, `io_util.py`, `schema.py`, `__init__.py`.

### 3.11 `ic003_shapes/` (3)

Shape library: `build_library.py`, `schema.py`, `__init__.py`.

### 3.12 `ic003b_sequence_geometry/` (8)

Sequence geometry / DTW clustering: `build_all.py`, `cluster_dtw.py`, `cluster_euclid.py`, `continuum.py`, `dtw.py`, `schema.py`, `summarize.py`, `__init__.py`.

### 3.13 `secondlow_v1/` (5)

Second-low detector track: `corpus.py`, `depth_metrics.py`, `detector.py`, `regime_metrics.py`, `__init__.py`.

### 3.14 `path/` (2)

`ambiguity_census.py` — path ambiguity census (intrabar / touch-order class issues).

### 3.15 `envelope_offline/` (3)

Offline envelope train/shadow: `train.py`, `shadow.py`, `__init__.py` (TradeNet/envelope research — not live fusion authority).

### 3.16 `model_runners/` (23)

Generic offline model runner stack: `runner.py`, `envelope.py`, `contracts.py`, `require_config.py`, `schema_resolver.py`, `stats.py`, `substrate.py`, plus `adapters/*` for model families. **Research execution substrate**, not EngineRunner.

### 3.17 `synthetic/` (10)

Synthetic story ontology for controlled experiments: `ontology.py`, `story_builder.py`, `story_registry.py`, `story_spec.py`, `stories/*`.

### 3.18 Root-only modules

Listed in §2 shared spine table (27 root `.py` including package init).

---

## 4. `scripts/research/` — driver clusters (126 files)

Thin wrappers: **prefer** importing `src/research` kernels; scripts should not reinvent gate math.

### 4.1 Qualify / M4 gate (16) — primary economic runners

`qualify_majors.py`, `qualify_htf.py`, `qualify_fx_metals.py`, `qualify_xauusd.py`, `qualify_transitions.py`, `qualify_regime_conditioning.py`, `qualify_regime_transition.py`, `qualify_cross_sectional.py`, `qualify_carry.py`, `qualify_harvest.py`, `qualify_weekly_sweep.py`, `qualify_m5_straddle.py`, `qualify_interpreter.py`, `qualify_shape_xauusd.py`, `qualify_zone_topk.py`, `xauusd_gaussian_m4_qualify.py`.

**When to run:** only against a **pre-registration** and frozen config; write under `results/research/`.

### 4.2 Phase / Program 1 sub-drivers (4)

`phase_b_conditional_entropy.py`, `phase_d_exit_grid.py`, `phase_e_structural_asymmetry.py`, `phase_s_selection_effect.py`.

### 4.3 Regime / transition information (1+)

`transition_information.py` (Stage-1 info); economic twin often `qualify_transitions.py` / regime qualify scripts.

### 4.4 Program 9 M5 (2+)

`m5_mtf_information.py` (Stage-1), `verify_m5_resample_parity.py`, `qualify_m5_straddle.py` (Stage-2, listed under qualify).

### 4.5 Zone / ZoneGate research (14)

`discover_zones.py`, `zone_label_audit.py`, `diagnose_zone_inertness.py`, `zone_gate_threshold_sweep.py`, `ablate_zone_thr_xauusd_fusion.py`, `convert_zones_v1_to_gaussian.py`, `build_zone_census.py`, `build_crt_zone_crosstab.py`, `build_displacement_zone_event_study.py`, rare-zone builders, `trace_zone_gate_xauusd.py`, `zone_x_o4_gap_study.py`, …

### 4.6 RR / clean labels (11)

`rr_l3_label_generation.py`, `rr_l2_feature_truth.py`, `rr_l4_research_execution.py`, `rr_shadow_value.py`, `rr_kill_test_clean_l3.py`, `build_clean_labels_tn_env.py`, `build_rr_dataset_from_clean_labels.py`, `analyze_clean_labels_tn_env.py`, `h_rr_threshold_001.py`, `gaussian_rr_scatter.py`, `bitnet_population_label_audit.py`.

### 4.7 BitNet / Gaussian / TradeNet diagnostics (8)

`bitnet_r25_kill_test.py`, `bitnet_shadow_diagnostic.py`, `diagnose_gaussian_pivotality.py`, Gaussian family/delta builders, XAUUSD Gaussian econ ledgers, TradeNet report patches.

### 4.8 CRT parity / resolver (7)

`crt_parity_*.py`, `crt_state_confusion_matrix.py`, `validate_crt_state_resolver.py`, `crt_range_rebuild_probe.py`, `crt_resolver_economic_comparison.py`.

### 4.9 IC / shapes (6)

`ic002_build_trajectories.py`, `ic002_evaluate.py`, `ic003_build_shape_library.py`, `ic003b_build.py`, `ic003b_derive_information.py`, `shape_statistics_survey.py`.

### 4.10 Episodes / corpus / path (13)

`build_episodes.py`, `build_trace_corpus.py`, `analyze_trace_corpus.py`, `certify_xauusd_corpus.py`, path ambiguity / knn / geometry tracers, enrich helpers.

### 4.11 XAU / metals / FX cost (8)

`run_xau_metals_protocol_v1.py`, `xauusd_mt5_cost_calibration.py`, `rerun_xau_metals_m4.py`, MT5 CRT runners, library build helpers.

### 4.12 MSIP hypothesis runners (2)

`run_h_msip_001.py`, `run_h_msip_002.py` — research-only; no CRT production authority.

### 4.13 Gate measurement (2)

`gate_measurement_m_gate_01.py` (F-070 class), `gate_o_nonlinear_probe.py`.

### 4.14 Private / underscore helpers (4+)

`_verify_outputs.py`, `_watch_h_rr.py`, `_fix_eval_auc.py`, `_show_top_decile_n9.py`, `_corpus_inspect.py`, … — operator helpers, not programs.

### 4.15 Uncategorized residual (~28)

Includes forensics (`bnbusdt_forensics.py`), attribution studies, envelope train/shadow, story library, promotion dry-run, opportunity scanner, dimensional-mix diagnostics, FM030 band validation, model offline runners, etc. **Treat as ops/research tools:** read the module docstring before running; assume **write to `results/`** unless proven read-only.

---

## 5. Configs, pre-regs, artifacts (not code but E2 surface)

| Kind | Path |
|---|---|
| Research configs | `configs/research/research_config*.json`, `configs/research/experiments/` |
| Measurement profiles | `configs/research/measurement_contracts/*.v1.json` |
| Pre-registrations | `docs/research/preregistration-*.md`, `docs/research-readiness/program-*-preregistration.md` |
| Findings | `docs/current-findings.md` |
| Family registry | `docs/governance/research_family_registry.json` |
| Outputs | `results/research/**` |

---

## 6. Danger / authority flags

| Flag | Meaning |
|---|---|
| **RESEARCH_ONLY** | Default for all of E2 — no fusion/production weight |
| **WRITES_ARTIFACTS** | Most `scripts/research/*` write under `results/` |
| **LABEL_SENSITIVE** | RR/zone label scripts — F-022 contamination class; prefer `forward_walk` / clean_labels |
| **COST_MODEL** | Changing bps or exit model invalidates cross-program comparison (Measurement Contract gap) |
| **PRE_REG_REQUIRED** | New economic claims need a frozen pre-registration first |
| **OBSERVE_ONLY** | Parity/trace/counter scripts must not change spine math |

---

## E2 exit criterion

| Criterion | Status |
|---|---|
| Every `src/research` **subpackage** has a purpose row | **Met** (§3) |
| Shared root kernels listed | **Met** (§2) |
| Programs 1–9 mapped to kernels/drivers/artifacts | **Met** (§1) |
| All 126 scripts classified into clusters (or residual) | **Met** (§4) |
| Per-file essay for all 269 | **Out of scope** (charter: index, not encyclopedia essays) |

---

## Next

- **E3** — Governance tooling (`src/governance/`, `scripts/governance/`, `scripts/analysis/`).  
- Optional deep-dives: one program appendix (e.g. P9 only) if Stage-1/2 re-runs are planned.

---
**Related:** [Ch.19](../19-research-programs.md) · [Ch.20](../20-research-platform.md) · [E1 spine](E1-spine-implementation.md) · [Ch.24](../24-repository-encyclopedia.md)
