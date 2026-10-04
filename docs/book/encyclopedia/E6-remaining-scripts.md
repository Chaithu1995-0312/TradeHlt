# Encyclopedia E6 — Remaining Operator Scripts (Group D residual)

**Phase:** E6  
**Status:** DONE (category catalog for scripts not covered by E2/E3)  
**Date:** 2026-08-07  
**Parent:** [Chapter 24](../24-repository-encyclopedia.md) · [Encyclopedia index](README.md)

## Scope

| Already catalogued | Where |
|---|---|
| `scripts/research/` (126) | [E2](E2-research-utilities.md) |
| `scripts/governance/` (31) | [E3](E3-governance-tooling.md) |
| `scripts/analysis/` (115) | [E3](E3-governance-tooling.md) |
| `scripts/maintenance/` (9) | [E3](E3-governance-tooling.md) |

| E6 residual under `scripts/` | Count |
|---|---:|
| `data/` | 22 |
| `training/` | 13 |
| root `scripts/*.py` | 10 |
| `context/` | 5 |
| `misc/` | 5 |
| `evaluation/` | 3 |
| `export/` | 3 |
| `groq_bridge/` | 3 |
| `backtest/` | 2 |
| `control_plane/` | 1 |
| `metrics/` | 1 |
| `multi_llm/` | 1 |
| `portfolio/` | 1 |
| **E6 total** | **~70** |
| **All `scripts/**/*.py`** | **~351** |

**Design rule:** operator catalog by **job** (fetch data, train model, run backtest, multi-LLM context) — not 70 essays. Prefer `src/` kernels; scripts stay thin.

**Group:** D (operational scripts).  
**Default danger:** many **WRITE** data/, models/, results/, configs hashes.

---

## How to use

| Job | Directory |
|---|---|
| Fetch / convert / verify OHLCV | `scripts/data/` → `src/inout/*` (E1) |
| Train BitNet / RR / TradeNet / Gaussian | `scripts/training/` → `src/training`, `src/bitnet` (E4) |
| Portable Mind / multi-LLM context | `scripts/context/` → Ch.23 |
| Control-plane server | `scripts/control_plane/run_server.py` → Ch.22 |
| Manual / debug backtest | `scripts/backtest/` → `src/runtime/backtest_v2` (E1) |
| Groq bridge workflow | `scripts/groq_bridge/` |
| Model export / bootstrap | `scripts/export/` |
| One-off parity / zone / replay tools | `scripts/misc/` |

Authoritative runnable catalog when regenerated: `docs/reference/cli-matrix.md` + `docs/reference/script-matrix.md` (E3 generators).

---

## 1. `scripts/data/` — market data I/O (22)

**Posture:** LIVE ops for corpora. Writes under `data/`.

### Fetch (thin wrappers over `src/inout`)

| Script | Purpose |
|---|---|
| `fetch_candles_mt5.py` | MT5 → CSV |
| `fetch_candles_alphavantage.py` | Alpha Vantage FX |
| `fetch_candles_hummingbot.py` | Hummingbot/exchange OHLCV |
| `fetch_perp_funding.py` | Binance perp funding/basis |
| `fetch_crypto_ccxt.py` | CCXT crypto fetch |
| `fetch_forex_yfinance.py` | Yahoo Finance forex |
| `fetch_and_verify_binance.py` / `fetch_and_verify_mt5.py` | Fetch + verify pipelines |
| `check_availability.py` / `check_yfinance.py` / `test_yf_periods.py` | Connectivity / period checks |

### Build / convert / verify

| Script | Purpose |
|---|---|
| `convert_binance_m1_to_m15.py` / `misc` cousin resample | M1→M15 resample |
| `convert_bnb_to_csv.py` / `csv_to_excel.py` / `split_bnb_excel.py` | Format converters |
| `build_m15_unified.py` / `unified_data_builder.py` / `prepare_data.py` | Unified dataset builders |
| `build_rr_dataset.py` / `build_tradenet_dataset.py` | Train-set builders (label-sensitive) |
| `generate_vectors.py` | Feature vector generation helper |
| `verify_output.py` | Output verification |

**Prefer:** production loaders + `dataset_integrity` (E5 MIXED) for sequence checks.  
**Danger:** LABEL_SENSITIVE datasets (RR/TradeNet) — F-022 class.

---

## 2. `scripts/training/` — model training CLIs (13)

**Posture:** OFFLINE. Artifacts under `models/`. No automatic production authority.

| Script | Purpose |
|---|---|
| `train_pipeline.py` | Main train pipeline CLI |
| `train_rr_model.py` | RR pattern model train |
| `train_bitnet.py` / `train_bitnet_contract_c.py` | BitNet / CONTRACT-C train |
| `train_trade_net_v2.py` | TradeNet v2 train (unwired fusion — F-005) |
| `train_gaussian_xauusd.py` | Gaussian train path (artifact lineage caution — F-060) |
| `phase5_calibration.py` | Phase-5 calibration gate CLI |
| `build_stage1_dataset.py` | Stage-1 dataset for LLM/train |
| `auto_tuner.py` / `auto_tuner_multi.py` / `auto_tuner_gemini_gate.py` | Parameter tuner family |
| `show_xauusd_gaussian_promotion.py` | Promotion display helper |
| `_write_hashes_closure_narrative.py` | Hash/closure narrative helper |

**Related:** E4 `src/training/`, E4 `src/bitnet/`, E3 promote path for any production registration.

---

## 3. Root `scripts/*.py` (10)

| Script | Purpose | Danger |
|---|---|---|
| `update_config_hash.py` | Config hash helper (pair with maintenance `_compute_hash`) | HASH write |
| `export_model_registry.py` | Export model registry snapshot | read/write artifacts |
| `auto_train_from_opportunities.py` | Auto-train trigger from opportunities stream | TRAIN write |
| `validate_integration.py` | Integration validation harness | — |
| `build_consolidated_docs.py` | Docs consolidation builder | docs write |
| `extract_folder_structure.py` | Repo tree extract | — |
| `rag_index.py` | Build/update RAG index (`src/retrieval`) | optional deps |
| `_gate5_compliance_pass.py` | Gate-5 compliance counting helper | observe |
| `tmp_cert_worktrees.py` | Worktree certification temp helper | ops |
| `__init__.py` | Package marker | — |

---

## 4. `scripts/context/` — Portable Mind / multi-LLM (5)

**Posture:** OPS for multi-LLM workflow (Ch.23). Regenerates gitignored `context/*.md`.

| Script | Purpose |
|---|---|
| `build_context.py` | **Compile** trigger — rebuild Portable Mind `context/*.md` |
| `log_turn.py` | Append multi-LLM turn to ledger |
| `discussion.py` | Discussion reconstruct / rewind |
| `pack_story.py` | Bounded story pack for handoff |
| `seed_build_queue.py` | Seed `multi_llm/build_queue.jsonl` |

**Related:** E4 `src/multi_llm/`, root `multi_llm/`.

---

## 5. `scripts/control_plane/` (1)

| Script | Purpose |
|---|---|
| `run_server.py` | Start localhost control-plane HTTP server (:8787) |

**Related:** E1 `src/control_plane/*`, Ch.22. **No auth / localhost only.**

---

## 6. `scripts/backtest/` (2)

| Script | Purpose |
|---|---|
| `manual_backtest.py` | Manual backtest entry wrapper |
| `backtest_debug_harness.py` | Debug harness around backtest path |

**Related:** E1 `src/runtime/backtest_v2.py`. Prefer official CLI entry points from cli-matrix when present.

---

## 7. `scripts/export/` (3)

| Script | Purpose |
|---|---|
| `export_bitnet_model.py` | Export BitNet model artifacts |
| `generate_bootstrap_model.py` | Bootstrap model generation |
| `regen_bitnet_35.py` | BitNet 3.5 regen helper |

**Danger:** model artifact writes; no auto-promote.

---

## 8. `scripts/evaluation/` (3)

| Script | Purpose |
|---|---|
| `run_benchmark.py` | Benchmark runner |
| `report.py` | Evaluation report generation |
| `__init__.py` | Package marker |

---

## 9. `scripts/groq_bridge/` (3)

| Script | Purpose |
|---|---|
| `prepare_retrospective.py` | Prepare retrospective pack for Groq/LLM |
| `ingest_response.py` | Ingest LLM response into workflow |
| `apply_llm_suggestions.py` | Apply suggestions (review carefully — may write) |

**Danger:** treat apply step as human-gated.

---

## 10. `scripts/misc/` (5)

| Script | Purpose |
|---|---|
| `run_parity.py` | Parity run helper |
| `trade_replay_validator.py` | Trade replay validation |
| `build_zone_registry_from_trades.py` | Zone registry from trades (label-sensitive) |
| `resample_m1_to_m15.py` | Resample utility |
| `bitnet_ternary_inference.py` | BitNet ternary inference probe |

---

## 11. Single-file operator CLIs

| Script | Purpose |
|---|---|
| `metrics/extract_metrics.py` | Extract metrics from run artifacts |
| `multi_llm/initiate_plan.py` | Initiate multi-LLM plan cycle |
| `portfolio/replay_allocator.py` | Portfolio allocator shadow replay (F-013 class) |

---

## Cross-links (do not duplicate)

| Need | See instead of reinventing |
|---|---|
| Research qualify / phase drivers | E2 |
| Promote / SITS / feature DAG | E3 |
| Session log rotate / config hash | E3 maintenance |
| In-repo libraries behind scripts | E1 / E4 |

---

## Danger flags (E6)

| Flag | Meaning |
|---|---|
| **WRITES_DATA** | Touches `data/**` corpora |
| **WRITES_MODELS** | Touches `models/**` |
| **WRITES_CONFIG_HASH** | Production config hash paths |
| **TRAIN_OFFLINE** | No live trading authority |
| **LOCALHOST_ONLY** | Control plane / health |
| **HUMAN_GATE** | Groq apply / auto-train / promote-adjacent |

---

## E6 exit criterion

| Criterion | Status |
|---|---|
| All `scripts/` top-level dirs either in E2/E3 or listed here | **Met** |
| Residual ~70 scripts categorized by job | **Met** |
| Pointers to cli-matrix / script-matrix | **Met** |
| Per-script full API docs | **Out of scope** |

---

## Encyclopedia series status

| Phase | Status |
|---|---|
| E0 Charter | DONE |
| E1 Spine Group A | DONE |
| E2 Research | DONE |
| E3 Governance | DONE |
| E4 Sidecars | DONE |
| E5 Dormant/Archive | DONE |
| **E6 Remaining scripts** | **DONE** |

**Optional later:** E1b (`src/features/` registry depth), per-program research deep-dives, or machine-generated JSONL twin of all encyclopedia rows.

---
**Related:** [E2](E2-research-utilities.md) · [E3](E3-governance-tooling.md) · [E4](E4-sidecar-modules.md) · [Ch.22](../22-control-plane.md) · [Ch.23](../23-multi-llm-coordination.md) · [Ch.24](../24-repository-encyclopedia.md) · `docs/reference/cli-matrix.md`
