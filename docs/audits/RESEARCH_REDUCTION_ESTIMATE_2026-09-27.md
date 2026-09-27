# Research Reduction Estimate - 2026-09-27

**Hypothetical only. No code changes, no implementation plan.** This estimates how much research code *could* be removed or consolidated if every open gap were closed (one canonical loader, one HTF authority, one outcome object, one ATR/indicator module, shared stats) without losing any information or finding the research scripts produce. It uses data from `RESEARCH_FUNCTION_CENSUS_2026-09-27.md` and `RESEARCH_AUTHORITY_CENSUS_2026-09-27.md`.

Evidence tags: **STATIC** (measured from source at HEAD `09ffcb1`, dirty tree), **DOC** (from repo docs), **ESTIMATE** (judgement applied to static measurements). Every removal figure below is an ESTIMATE.

LOC = non-blank, non-comment physical lines. Function LOC is measured with `ast` over the function span.

---

## 1. Baseline (STATIC)

| Scope | Files | Code LOC |
|---|---|---|
| `src/research` | 224 | 36,961 |
| `scripts/research` | 175 | 49,135 |
| `scripts/analysis` | 159 | 55,178 |
| **Total** | **558** (527 excluding 31 `__init__.py`, 661 LOC) | **141,274** (167,132 physical lines) |

- Median file: 183 LOC; 90th percentile: 552 LOC.
- The task-1 census counted 492 research files with a different filter; this estimate uses the 527 non-`__init__` files above as its denominator.
- Some duplicated functions live in research-adjacent files outside this baseline (`analytics/sl_tp_comparator`, `replay/timing_reconstructor`, `tools/btcusdt_crt_v3_replay`, `scripts/backtest/manual_backtest`, `interpreters/regime_observer`, `scripts/data/*`). They are included in the category figures and flagged. This makes the percentages slightly generous (roughly 300-450 LOC of the duplicate-logic figures sit outside the baseline).

---

## 2. Whole files retirable (ESTIMATE)

**Rule.** A file is retirable only if ALL of these hold (STATIC checks):
1. No importer anywhere in `src`, `scripts`, `tools`, `tests`, `mt5_analytics` (229 files / 53,773 LOC fail this and are kept).
2. It is not a library leaf under `src/research` (5 files / 534 LOC kept).
3. It is not a Twin, certification, parity, oracle, validation, qualification, label, training or replay file, nor on a label path (60 files / 20,020 LOC kept).
4. It is not cited in `docs/current-findings.md`: those scripts are needed to re-validate findings with a `Revalidate-by` date (27 files / 7,524 LOC kept).
5. Its finding is captured elsewhere: it is named in a narrative doc (`docs/analysis`, `docs/research`, `docs/research-readiness`, `docs/topics`; generated inventories, session logs, plans and governance docs excluded). Files with no narrative doc (93 files / 23,968 LOC) are kept, because their finding exists only in their code or output.

| Band | Condition | Files | LOC | Share of baseline LOC |
|---|---|---|---|---|
| **Low** | Rule 1-5 + a matching `results/` artifact (by filename stem), minus `crt_resolver_economic_comparison` (promotion-study mixer) and `retest_divergence_probe` (R2 Twin) | **20** | **5,540** | 3.9% |
| Middle | Low + experiments named in 2 or more narrative docs | 43 | ~12,500 | 8.9% |
| **High** | Low + every other experiment named in a narrative doc (73 files, 22,544 LOC); excludes 16 tooling generators (4,528 LOC) and 2 R2 Twins (1,160 LOC) | **93** | **28,084** | 19.9% |

Low-band files (STATIC): `ab_rr_slot_xauusd`, `all_states_economic_probe`, `all_states_persistence_probe`, `bnb_ema_gate_ab`, `bnbusdt_conditional_edge`, `bnbusdt_forensics`, `consensus_sweep`, `crt_state_transition_audit_4m`, `detection_sweep`, `e1_retest_depth_max_probe`, `h_rr_threshold_001`, `jse002_engine_state_path_geometry`, `jse003_engine_context_history_path_geometry`, `link001_choch_measurement`, `m5_mtf_information`, `p001_excursion_probe`, `phase6e_shadow_ab`, `sweep_conditional_magnitude_probe`, `sweep_structure_economic_probe`, `ultron_sem_r_shadow`.

Caveats (ESTIMATE):
- A narrative-doc mention is weaker than "finding fully captured". The high band assumes the doc plus existing `results/` output fully preserve the finding. Where a doc only mentions a script in passing, that file belongs back in the keep set. This is why the high band is an upper bound.
- Retiring a script removes the ability to re-run it. The rule treats a finding as preserved when its doc and output remain; reproducibility of retired studies is lost by construction.
- Adjacent (outside baseline): the 4 M1->M15 corpus builders in `scripts/data` + `scripts/misc` could merge into 1, retiring 3 files (about 60-100 LOC net) once a canonical resampler exists.

---

## 3. Duplicate logic removable inside files that stay (ESTIMATE)

Each duplicated function would be replaced by a 1-2 line call to the canonical module. Low = only implementations semantically equal to the canonical one. High = every independent implementation, assuming the canonical module is parameterised to reproduce each variant exactly (method, smoothing, window, tie-break), so no result changes.

| Category | Implementations measured | Low LOC | High LOC | Reasoning |
|---|---|---|---|---|
| L0 loaders | 13 Shadow (231), 3 competing (47), 4 Unknown (64), 18 Experiment (264) | ~260 | ~600 | Low: Shadow loaders + merging 2 of 3 competing research loaders. High: all non-Authority loader bodies. |
| HTF / resample | `resample_m15` x2 (34) + 2 small builders + 2 inline `.resample` | ~35 | ~95 | Twins (`build_htf_id_timeline`, `build_htf_ids`, `calendar_periods`) kept. |
| ATR / TR | 14 named (128) | 89 | 128 | Low: SMA-equivalent copies (5 `high_acceptance` copies, one verbatim). High adds Wilder, rolling-min_periods, range proxy (need parameters). |
| L9 walks | 9 Shadow/Experiment walk functions (644) | 361 | 644 | Low: fixed SL/TP walks equal to `forward_walk`/`multi_tp_walk` modes (comparator with `optimistic` tie-break, p3b, l003h fixed, zone_x_o4, erp_synth, xauusd trace). High adds trailing walks (`opportunity_scanner._simulate`, `timing_reconstructor`, `l003h` trailing) that need an exact trailing mode. |
| MFE / MAE | 6 measured (212; `jse003` main excluded) | 99 | 212 | High adds the two qualification `build_outcomes*` functions (partly MFE, partly orchestration). |
| Sweep | 5 non-declared detectors (80) | 21 | 80 | Declared-independent detectors (Sujan, visual, weekly; F-077) are kept, not counted. |
| Session | 7 (58) | 0 | 58 | Windows disagree (Asia 0-7 vs 0-8, inclusive ends). Low = 0 because each call must pass its own window; high assumes a parameterised canonical. |
| PF / win rate | 5 PF (32) + WR copies | 26 | 32 | Simple formulas; win-rate copies not separately measured. |
| EMA / RSI | 2 (10) | 10 | 10 | |
| Stats | BH 10 defs (196), bootstrap 3 (95), permutation 9 (263), Wilson 3 (27) | ~240 | ~580 | Low: BH, simple bootstrap and Wilson are algorithmically identical. High adds permutation variants (stratified, block, within-coarse), which are different null designs and need parameters. |
| **Gross** | | **~1,140** | **~2,450** | |
| Overlap with retired files | | -30 | -200 | Duplicate functions inside files already counted as retired (e.g. `consensus_sweep`, `bnbusdt_conditional_edge`; high band also `erp_synth`, `p3b`, `trace_geometry`, `session_cost_audit`, `momentum_continuation_bnbusdt` ...) |
| Call-site stubs added back | | -70 | -140 | ~1-2 lines per replaced function. |
| **Net duplicate logic removable** | | **~1,040** | **~2,110** | 0.7% - 1.5% of baseline LOC |

---

## 4. Total (ESTIMATE)

| | Low | High |
|---|---|---|
| Whole files retired | 20 files (3.8% of 527) | 93 files (17.6% of 527) |
| LOC from retired files | 5,540 | 28,084 |
| LOC from duplicate logic (files stay) | ~1,040 | ~2,110 |
| **Total LOC** | **~6,600 (4.7%)** | **~30,200 (21.4%)** |
| Files touched but kept (duplicate logic swapped for a call) | ~45 | ~75 |

Reading: whole-file retirement dominates. Duplicate logic is spread thin (dozens of 5-100 LOC functions) and removing it is worth about 1-2% of LOC. Its value is semantic (one tie-break, one clock gate, one ATR), not size.

---

## 5. Must NOT be removed (and why)

| Keep | Size (STATIC) | Why |
|---|---|---|
| Twins: `oracle/reference_walker`, `scripts/misc/trade_replay_validator`, `oracle/exit_analysis`, R2 reconstruction probes (`crt_range_rebuild_probe`, `crt_state_confusion_matrix`, `trace_sweep_geometry`, `retest_divergence_probe`), certification oracles (`oracle_true_range`, `fm021`/`fm027` oracles, `session_certification`, `feature_dag_*`) | part of the 60 protected + 2 twin files | Independent verification is information (e.g. 300/300 `reference_walker` agreement, RUNTIME). |
| Experiments with no narrative doc | 93 files / 23,968 LOC | Their finding exists only in their code or output. |
| Scripts cited in `docs/current-findings.md` | 27 files / 7,524 LOC | Needed to re-validate findings (`Revalidate-by` dates, DOC). |
| Anything imported by another file | 229 files / 53,773 LOC | Feeds another producer or a test. |
| Label, training, qualification and replay paths (`clean_labels`, `episodes`, `oracle/labeler`, `build_bar_matrix`, `rr_l3_label_generation`, `opportunity_scanner`, `gate0_tn_env_feasibility`, `qualify_*`, `execution_planner_replay`, `phase_s_selection_effect`) | within the 60 protected | Label and qualification lineage must stay reproducible. |
| Declared-independent objects: Sujan 4H CRT, `mother_range`, `secondlow_v1`, visual/weekly sweep | - | F-077 (DOC): not the same object, so not duplicates. |
| Variant methods, until a canonical module reproduces them exactly: Wilder ATR, median TR (`corpus_gate`), range-proxy ATR, stratified/block permutation, session windows, trailing walks, TP2-first tie-break | - | Removing them without an exact parameterised equivalent would change numbers, which counts as losing a finding. |
| `analytics/sl_tp_comparator` (as a TP2-first variant) | 1 file | Its output is cited in F-002/F-010 evidence (DOC). The RUNTIME TP2-first vs SL-first delta shows it is a different measurement, not a duplicate. |
| Execution-side authorities and layering duplicates (`CandleLoader`, `HTFBuilder`, `crt_engine_v2`, `feature_pipeline`, `features/calendar_periods`) | outside baseline | Execution must not import research; these duplicates are intentional (DOC). |
| Tooling generators (`generate_script_matrix`, `gen_pyan`, `gen_citation_map`, ...) | 16 files / 4,528 LOC | They regenerate docs; not research findings. |
| `results/` artifacts and docs themselves | - | They carry the preserved findings that justify any retirement above. |

---

## 6. Method notes

- Importer detection matched `import`/`from` statements by module stem (STATIC). Scripts launched by path string or subprocess would be missed, which biases the retirable counts upward. This is another reason to treat the high band as an upper bound.
- "Matching results artifact" = the file stem (at least 6 characters) appears in a `results/` file or directory name (STATIC). Artifacts with unrelated names were not credited.
- All runs were read-only, in memory, with `PYTHONDONTWRITEBYTECODE=1`.
