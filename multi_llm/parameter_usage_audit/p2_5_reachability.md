# P2.5 Reachability — Silent fallbacks for Tier-1 params

**Date:** 2026-09-19 22:21 IST (Asia/Calcutta)  
**Repo SHA (audit mirror):** `1890785daf31e9376c59b27e9f4d0e0998b99377`  
**ACTIVE_VERSION:** `v2_htfcrt_2026_08`  
**Policy:** no silent fallbacks/defaults. FOREX/CRYPTO router class values = **Overrides** (legitimate), NOT defects.

## Naming (real types)

| Alias searched | Real name | Path |
|---|---|---|
| CRTConfig / CrtConfig | `CRTConfig` | `src/config_layer/state_identity.py:137` |
| CRTStateResolver / StateResolver / CrtStateResolver | `CRTStateResolver` | `src/features/crt_state_resolver.py:305` |
| ProductionConfig | `get_prod_config` / `load_prod_config_from_registry` | `src/config_layer/production_config.py:254 / :298` |
| thr.get | `thr = self._config.get("thresholds", {})` then `thr.get("<key>", <fallback>)` | `crt_state_resolver.py` |

Authority (ACTIVE `params` + YAML `thresholds`):  
`body_ratio_min=0.65`, `atr_multiplier_min=1.0`, `expansion_atr_min_distance=0.30`, `retest_depth_max=0.15`.

Illegal CRTConfig/resolver fallback-class:  
`0.70 / 1.5 / 0.20 / 0.25`.

## Verdict

### **Path A (dormant in prod)**

Live CRTEngine never calls thr.get for these four keys (uses self.config.* from get_prod_config/authority); stock CRTStateResolver loads market_crt_states.yaml which already declares all four at authority, so .get second-args are unreachable on prod/review dual-construction. manual_backtest hardcodes fallback-class constants on a non-prod path.

Mixed / adjacent (not Path B for live):
- manual_backtest.py actively uses fallback-class hardcodes (not thr.get) — Defect on manual_backtest path only
- FOREX/CRYPTO market_router.classes values are Overrides (legitimate), not defects
- Bare CRTConfig() dataclass defaults remain Defect surface in tests/provenance, not live

### Q4 — Does live engine ever hit `.get(..., fallback)` for these four?

**No.** Evidence:
1. Gate sites read `self.config.<key>` (`crt_engine_v2.py:1335,1367,1551,1633`) — attribute access, not `dict.get`.
2. Live/backtest product configs come from `load_prod_config_from_registry` / `get_prod_config` (`production_config.py:254+`, `backtest_v2.py:2049`) which merge ACTIVE `params` (authority) onto router class.
3. `CRTStateResolver` is **not** the live execution authority (module docstring: runs alongside engine; engine remains execution authority). Dual-construction review (`crt_construction_trace.py:236`) loads YAML with keys present → `.get` second arg never used.

### Q5 — Critical `manual_backtest` cell

**Constructs without CRTConfig / CRTStateResolver.** Hardcodes fallback-class constants:

| constant | line | value | maps to |
|---|---|---|---|
| `DISP_BODY_MIN` | `manual_backtest.py:48` | **0.70** | body_ratio_min fallback |
| `DISP_WICK_MIN_ATR` | `:49` | **1.5** | atr_multiplier_min fallback |
| `EXPANSION_ATR_MIN` | `:50` | **0.20** | expansion_atr_min_distance fallback |
| `RETEST_RANGE_FRAC` | `:51` | **0.25** | retest_depth_max fallback |

Used at `:434-435` (disp), `:445` (expansion), `:149/:457` (retest ceiling). Path class: **manual_backtest**. Not on live engine path.

## Reachability table

| id | file:line | Constructs | Passes four keys? | Runtime (auth / fallback / override) | Path class | Hits thr.get fallback? |
|---|---|---|---|---|---|---|
| R01 | `src/config_layer/production_config.py:254` | Config (via ConfigBuilder.build / PRODUCTION_MERGED) | yes | body_ratio_min=authority; atr_multiplier_min=authority; expansion_atr_min_distance=authority; retest_depth_max=authority | prod | False |
| R02 | `src/runtime/backtest_v2.py:2049` | Config (load_prod_config_from_registry) then CRTEngine(self.crt_cfg) @2561 | yes | body_ratio_min=authority; atr_multiplier_min=authority; expansion_atr_min_distance=authority; retest_depth_max=authority | backtest | False |
| R03 | `src/config_layer/crt_engine_v2.py:1335` | Consumer (CRTEngine gates); does not construct Config | yes (via injected CRTConfig) | body_ratio_min=authority (when cfg from get_prod_config); atr_multiplier_min=authority (when cfg from get_prod_config); expansion_atr_min_distance=authority (when cfg from get_prod_config); retest_depth_max=authority (when cfg from get_prod_config) | prod | False |
| R04 | `src/runtime/crt_construction_trace.py:236` | Resolver (CRTStateResolver(config_path=cfg.ontology_source)) | yes (via market_crt_states.yaml thresholds) | body_ratio_min=authority (YAML thr; .get 2nd arg dormant); atr_multiplier_min=authority (YAML thr; .get 2nd arg dormant); expansion_atr_min_distance=authority (YAML thr; .get 2nd arg dormant); retest_depth_max=authority (YAML thr; .get 2nd arg dormant) | prod | False |
| R05 | `src/features/crt_state_resolver.py:1803` | Resolver definition sites for thr.get | depends on loaded YAML | body_ratio_min=fallback 0.70 ONLY if key missing (line 1803); atr_multiplier_min=fallback 1.5 ONLY if key missing (line 1820); expansion_atr_min_distance=fallback 0.20 ONLY if key missing (line 1887); retest_depth_max=fallback 0.25 ONLY if key missing (line 1598) | other | conditional_key_missing |
| R06 | `src/config_layer/market_router.py:116` | Config (CRTConfig(**classes[market_type])) | yes (FOREX/CRYPTO class profiles) | body_ratio_min=OVERRIDE FOREX=0.6 / CRYPTO=0.5 (then params merge may replace); atr_multiplier_min=OVERRIDE FOREX=1.5 / CRYPTO=1.0; expansion_atr_min_distance=OVERRIDE FOREX=0.08 / CRYPTO=0.15; retest_depth_max=OVERRIDE FOREX=0.35 / CRYPTO=0.25 | prod | False |
| R07 | `src/config_layer/state_identity.py:140` | Config dataclass field defaults | defaults only (no loaded keys) | body_ratio_min=dataclass default = fallback 0.7; atr_multiplier_min=dataclass default = fallback 1.5; expansion_atr_min_distance=dataclass default = fallback 0.2; retest_depth_max=dataclass default = fallback 0.25 | other | False |
| R08 | `scripts/backtest/manual_backtest.py:48` | Neither Config nor Resolver — standalone hardcoded constants | no | body_ratio_min=hardcode DISP_BODY_MIN=0.70 (=fallback class); atr_multiplier_min=hardcode DISP_WICK_MIN_ATR=1.5 (=fallback class); expansion_atr_min_distance=hardcode EXPANSION_ATR_MIN=0.20 (=fallback class); retest_depth_max=hardcode RETEST_RANGE_FRAC=0.25 (=fallback class) | manual_backtest | False |
| R09 | `scripts/research/retest_divergence_probe.py:135` | Resolver + local thr.get('retest_depth_max', 0.25) | partial (retest via thr; others via resolver YAML) | retest_depth_max=authority if YAML present else fallback 0.25; body_ratio_min=via resolver YAML / thr.get inside resolver; atr_multiplier_min=via resolver; expansion_atr_min_distance=via resolver | research | conditional_key_missing |
| R10 | `tests/* (aggregate):0` | CRTConfig() bare (~70) and CRTStateResolver() bare (~41) | no for bare CRTConfig(); yes for bare Resolver (default YAML) | body_ratio_min=CRTConfig()→0.70 fallback; Resolver→0.65 authority from YAML; atr_multiplier_min=CRTConfig()→1.50; Resolver→1.0; expansion_atr_min_distance=CRTConfig()→0.20; Resolver→0.30; retest_depth_max=CRTConfig()→0.25; Resolver→0.15 | test | False |
| R11 | `src/agent/modes/pipeline_mode.py / copilot_mode.py:137` | Config via get_prod_config | yes | body_ratio_min=authority; atr_multiplier_min=authority; expansion_atr_min_distance=authority; retest_depth_max=authority | prod | False |
| R12 | `src/runtime/live_engine_hook.py:302` | Reads get_prod_metadata/crt_engine section (execution planner); CRT thresholds via engine CRTConfig elsewhere | partial (SL/TP atr multipliers; four Tier-1 gates are on CRTEngine.config) | body_ratio_min=N/A at this file — gates live on CRTEngine.self.config from get_prod_config path; atr_multiplier_min=N/A at this file — gates live on CRTEngine.self.config from get_prod_config path; expansion_atr_min_distance=N/A at this file — gates live on CRTEngine.self.config from get_prod_config path; retest_depth_max=N/A at this file — gates live on CRTEngine.self.config from get_prod_config path | prod | False |

## Defect vs Override split (Tier-1)

### Defects (illegal silent defaults / shadows)

| site | values | class |
|---|---|---|
| `CRTConfig` dataclass defaults `state_identity.py:140-152` | 0.70 / 1.50 / 0.20 / 0.25 | Defect (silent default) |
| `CRTStateResolver` `thr.get(..., fallback)` `:1598,:1803,:1820,:1887` | same | Defect (silent fallback) — **dormant** when YAML keys present |
| `retest_divergence_probe.py:135` `thr.get("retest_depth_max", 0.25)` | 0.25 | Defect (research duplicate) |
| `manual_backtest.py:48-51` hardcodes | 0.70 / 1.5 / 0.20 / 0.25 | Defect (hardcoded shadow) — **active on that script only** |

### Overrides (legitimate — NOT defects)

| site | FOREX | CRYPTO | note |
|---|---|---|---|
| `market_router.classes` in ACTIVE JSON (`market_router.py:116` builds `CRTConfig(**classes[...])`) | body 0.6, atr_mult 1.5, exp 0.08, retest 0.35 | body 0.5, atr_mult 1.0, exp 0.15, retest 0.25 | Class profile; `get_prod_config` then overlays `params` → product authority 0.65/1.0/0.30/0.15 |

## Counts

| bucket | count / note |
|---|---|
| Prod callers **with** governed config (get_prod / load_prod / ConfigBuilder PRODUCTION_MERGED) | ≥5 primary sites (production_config, backtest_v2, pipeline_mode, copilot_mode, certify, charts overlay, unified_replay, portfolio_validation) — **authority** |
| Prod callers **without** config hitting thr.get fallback for these four | **0** |
| Prod review Resolver (`crt_construction_trace`) | 1 — YAML keys present → thr.get fallback **dormant** |
| Test bare `CRTConfig()` | ~70 — hit dataclass defaults (fallback-class) |
| Test/research bare `CRTStateResolver()` | ~41 tests + ~2 research — default YAML → **authority**, thr.get dormant |
| Research without governed CRTConfig | manual_backtest (hardcodes); various research scripts using Resolver with default/explicit YAML |

## Blockers

- **ListMachines / cursor MCP** not provisioned for this executor subagent (`MCP server "cursor" not found`). Worked from box mirror `/workspace/tradelatest_audit` (SHA `{sha}`). Parent should CopyFromBox / Shell-write to `D:\Tradelatest` if Windows tree differs.
- No code/YAML/JSON threshold changes made (read-only mission).

## Evidence anchors

- YAML authority: `configs/formulas/market_crt_states.yaml:304-305,309,328`
- ACTIVE params: `configs/production/v2_htfcrt_2026_08.json` `params` = 0.65 / 1.0 / 0.3 / 0.15
- Router overrides: same file `market_router.classes.FOREX|CRYPTO`
