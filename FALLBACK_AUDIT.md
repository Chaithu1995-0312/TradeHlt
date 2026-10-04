# FALLBACK_AUDIT.md — Repository-Wide Ambiguity-Hiding Fallback Sweep

> Objective: **remove ambiguity-hiding fallbacks; escalate uncertainty.** The test per site is
> *"was this masking corruption?"* — not *"does a default exist?"* (plan:
> `~/.claude/plans/claude-prompt-glittery-rabbit.md`).
>
> Classification (FROZEN four-way): **REMOVE** (FORBIDDEN corruption-masker) · **KEEP** (ALLOWED
> documented resilience) · **AMBIGUOUS-A** (evidence-resolvable by fire-test) · **AMBIGUOUS-B**
> (semantic → user decision, see `AMBIGUITY_REPORT.md`).
>
> Truth hierarchy: Evidence > Schema > Version-branch > User > Documented-resilience.
> Byte-identicality is **empirical** (validated by determinism/golden/oracle gates), never assumed.

Active config (branch `patch`): **v2_multi_2026_04** (`configs/production/ACTIVE_VERSION`).

---

## Batch 1 — `src/config_layer/` — ✅ REMOVALS APPLIED + VERIFIED (2026-06-16)

**Result:** config-load masks removed in `rr_fusion.py`, `rr_pattern_miner.py`,
`crt_gaussian_scorer.py` (RR-005); RR-001 (`_rr_min`/`_rr_max` → constants); RR-002/003
(`execution_planner` `selected_direction` strict, atomic with fixtures RR-004). All byte-identical
gates GREEN (determinism 14, golden+invariants+oracle 225, rr_fusion 9, planner 45,
config-integrity). See `CLEANUP_PATCHES.md` P1-P4 + `RESOLUTION_REGISTRY.md` RR-001..005.
Full-suite delta pending (`fallback_sweep_after_b1.txt`).

### Config-load masks (module-load-time `try: get_prod_section(...) except Exception: {}`)

| File | Line | Pattern | Key in active cfg? | Category | Action |
|---|---|---|---|---|---|
| `rr/rr_fusion.py` | 23-30 | outer `except Exception: _DRIFT_THRESHOLD = 1.5` wrapping `_get_section("rr_model").get("drift_threshold", 1.5)` | `rr_model.drift_threshold = 1.5` ✅ (matches literal) | REMOVE (config mask + soft default) · outer-except is AMBIGUOUS-A (import resilience?) | strict `_get_section("rr_model")["drift_threshold"]`; keep inner ImportError dual-path (ALLOWED); fire-test removal of outer `except` |
| `rr/rr_pattern_miner.py` | 25-42 | outer `except Exception: _RR_CFG = {}` + 9 soft `.get(k, literal)` | 7 present & matching ✅; `score_weights._rr_min` / `_rr_max` ABSENT (defaults fire) | REMOVE 7 present keys → strict; outer-except AMBIGUOUS-A; `_rr_min`/`_rr_max` AMBIGUOUS-B (inline clamp constants, not in cfg) | strict reads for present keys; escalate `_rr_min`/`_rr_max` |
| `crt_gaussian_scorer.py` | 14-18 | outer `except Exception: _GS_CFG = {}` | `gaussian_scorer` section present ✅ (all keys consumed downstream) | REMOVE (config mask) · outer-except AMBIGUOUS-A | strict `_get_section("gaussian_scorer")`; keep ImportError dual-path; fire-test |

**Note on the outer `except Exception`:** identical idiom in all three modules — it executes at
*import time* and may be load-bearing import resilience (tests / standalone scripts importing the
module without a full prod config) rather than corruption-masking. Classified **AMBIGUOUS-A** and
resolved empirically: remove → run full suite + determinism. Green ⇒ dead resilience, removal is
truth-restoring. New reds (esp. import errors) ⇒ revert + reclassify AMBIGUOUS-B.

### Multi-key lookups (`d.get("a", d.get("b", literal))`)

| File | Line | Pattern | Category | Action |
|---|---|---|---|---|
| `execution_planner.py` | 215, 343 | `engine_result.get("direction", engine_result.get("selected_direction", 0))` | AMBIGUOUS-B (are `direction`/`selected_direction` synonyms or distinct schema fields? what does `0` mean for direction?) | escalate — do NOT mechanically collapse |
| `insight_reporter.py` | 136 | `score_result.get("gaussian", score_result.get("final_score", 0.0))` | KEEP — user-facing report formatting via `_safe_fmt` (display value) | leave |
| `insight_reporter.py` | 256 | `metrics.get("total_trades", metrics.get("approved_trades"))` | KEEP — display value | leave |

### Silent coercion

| File | Line | Pattern | Category | Action |
|---|---|---|---|---|
| `crt_engine_v2.py` | 2243 | `float(getattr(st, "atr", 0.0) or 0.0)` | AMBIGUOUS-A (can `st.atr` be missing/None/0 on the replay path? is the `or 0.0` reachable?) | fire-test; if `atr` always a valid float → tighten, else escalate |

## Batch 2 — `src/core/` — CLASSIFIED (site-by-site per RR-006); escalation/keep-heavy, ~0 clean removals

**Headline finding (confirms F-001-style health):** core has **no unambiguous FORBIDDEN
corruption-maskers** to remove. Every multi-key / default site is one of: telemetry-KEEP,
documented-contract-ESCALATE, or boundary-AMBIGUOUS-B. This validates "core is escalation-heavy,
not removal-heavy" — the architecture is healthier than the raw `.get` count suggests.

| File:Line | Pattern | Evidence | Class |
|---|---|---|---|
| `convergence_controller.py:197-201` | `scores.get("crt"/"gaussian"/"zone_gate"/"rr", 0.5)` | documented neutral-fusion contract; `missing_engines` reported (line 202) | **KEEP/ESCALATE** (contract — do NOT remove) |
| `fusion_engine.py:375-381` `_extract_score` | `.get(engine, {})` + neutral | fusion neutral-score contract | **ESCALATE** (contract) |
| `fusion_engine.py:246` | `float(result.get("final", result.get("score", 0.5)))` | `final`/`score` multi-name + 0.5 neutral on fusion path | **AMBIGUOUS-B** (AC-001) |
| `engine_runner.py:639` | `int(input_data.get("direction", input_data.get("signal_dir", 1)) or 1)` | backtest sets `direction`==`signal_dir`==`trade_direction` (backtest_v2:2128-30); `or 1`=default-LONG for gaussian mirroring (comment 635-7) | **AMBIGUOUS-B** (AC-002) |
| `engine_runner.py:563` | `float(input_data.get("close", input_data.get("price", 0.0)))` | **audit-only** (`start_bar`, no-op unless debug_mode); telemetry | **KEEP** (display/audit) |
| `engine_runner.py:538` | `(context or {}).get("candle_idx", input_data.get("candle_idx", 0))` | candle index from context-or-input | **AMBIGUOUS-A** (does default fire on spine?) |
| `engine_runner.py:682` | `float(rr_fusion_result.get("final_score", rr_result.get("score", 0.0)))` | cross-dict fallback (rr_fusion vs rr) + 0.0 | **AMBIGUOUS-B** (AC-003) |
| `ultron_risk_gate.py:251` | `trade.get("symbol", trade.get("instrument", ""))` | `instrument`=dominant internal name; `symbol`=broker/live boundary (mt5_bridge, journal); `""`→`if instrument:` skips optional FRAG-2 guard (documented) | **AMBIGUOUS-B** (AC-004) — `""` part is benign structured-skip |
| `collector.py:88/104/128/132` | nested `context.get(...).get(...)` telemetry chains | collector = telemetry/observation stream (not decision) | **KEEP** (display) |
| `hierarchical_meta_fusion.py:204` | `rr_result.get("expected_rr", rr_result.get("rr", 0.0))` | HMF is sidecar-only (F-012, zero spine consumption) | **AMBIGUOUS-B** (AC-005) — low priority (sidecar) |
| `regime_governor.py:227-249` | `breakout.get("direction", 0)` / `(selected or {}).get("direction", 0)` | per-engine direction with 0=no-opinion (modeled, like RR-003) | **KEEP** (modeled 0; single-name, not multi-key) |

**Disposition:** 5 AMBIGUOUS-B core sites (AC-001..005) seeded into `AMBIGUITY_REPORT.md`. Per
**RR-006** (semantic debt is inventory) these are NOT auto-decided — they share the RR-002/RR-003
*class* (multi-name alias + sentinel) but each needs an evidence-confirmed canonical or a
"legitimate boundary-translation" ruling. **STOP for user decision.** No core edits made.

(Batches 3-5 appended as worked.)
