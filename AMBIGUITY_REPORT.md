# AMBIGUITY_REPORT.md — Sites requiring USER decision (AMBIGUOUS-B)

> Semantic questions no test can answer. Claude must **NOT** guess. Each site stays **unmodified**
> until the user decides; decisions are then recorded permanently in `RESOLUTION_REGISTRY.md`.
> AMBIGUOUS-A (evidence-resolvable) sites are NOT here — they are resolved by fire-test and logged
> in `FALLBACK_AUDIT.md`.

---

> **STATUS UPDATE 2026-06-16:** AB-001 and AB-002 were decided by the user and are now ACTIVE
> doctrine in `RESOLUTION_REGISTRY.md` (RR-001, RR-002, RR-003) and implemented in Batch 1. Rows
> kept below for the record (append-discipline, §6.2 rule 4). No open AMBIGUOUS-B items remain.

## AB-001 — `rr_pattern_miner.py` `score_weights._rr_min` / `_rr_max` — RESOLVED → RR-001

- **File / Line:** `src/config_layer/rr/rr_pattern_miner.py:38-39`
- **Current behavior:** `_RR_MIN = _RR_CFG.get("score_weights", {}).get("_rr_min", -3.0)` /
  `_RR_MAX = ... .get("_rr_max", 5.0)`. The active config `rr_model.score_weights` contains only
  `gaussian/ml/confidence` — `_rr_min`/`_rr_max` are **absent**, so the `-3.0`/`5.0` defaults
  **fire** on every load.
- **Who consumes this?** Clamp bounds for the RR score normalization in the nano inference engine.
- **Can it fire on replay?** Yes — fires unconditionally (keys not in config).
- **What invariant does it protect?** The RR raw-score clamp range `[-3.0, 5.0]`.
- **Alternatives:** (a) add `_rr_min`/`_rr_max` to `rr_model.score_weights` in the config and
  read strict (Config-First migration, requires rehash); (b) move them to explicit module-level
  named constants (they are clamp structure, not a tunable) and drop the `.get` form; (c) leave
  as-is (status quo soft default).
- **Question for user:** Are `_rr_min`/`_rr_max` intended as **config-tunable knobs** (→ add to
  config) or **structural clamp constants** (→ make explicit named constants, no fallback)? This
  is not corruption-masking, so no auto-removal.

---

## AB-002 — `execution_planner.py` direction multi-key lookup — RESOLVED → RR-002 / RR-003

- **File / Line:** `src/config_layer/execution_planner.py:215, 343`
- **Current behavior:** `int(engine_result.get("direction", engine_result.get("selected_direction", 0)))`
  — tries `direction`, then `selected_direction`, then `0`.
- **Who consumes this?** Execution planner deriving trade direction from the engine result.
- **Can it fire on replay?** Needs fire-test, but the *semantic* question stands regardless.
- **What invariant does it protect?** A non-null direction for plan construction.
- **Alternatives:** (a) `direction`/`selected_direction` are synonyms → pick the canonical one
  (which?); (b) they are distinct schema-version fields → explicit version branch; (c) `0`
  (no direction) is a real sentinel the planner handles downstream → keep but document.
- **Question for user:** Are `direction` and `selected_direction` the **same concept under two
  names** (collapse to one) or **two distinct fields** (version branch)? And is `0` a legitimate
  "no-trade" sentinel or a corruption-masking default?

---

# Batch 2 — `src/core/` AMBIGUOUS-B sites (OPEN — awaiting user decision)

> All share the RR-002/RR-003 *class* (multi-name alias + sentinel default). Each carries my
> evidence + recommendation; none auto-decided (RR-006). The `0.5`/neutral *fusion* defaults
> (`convergence_controller`, `fusion_engine._extract_score`) are deliberately NOT here — they are
> the documented neutral-fusion **contract** (KEEP).

## AC-001 — `fusion_engine.py:246` `final` vs `score` (+ 0.5)
- **Current:** `_clamp(float(result.get("final", result.get("score", 0.5))))`.
- **Who consumes:** per-engine score extraction inside fusion.
- **Evidence:** `final`/`score` look like two names for an engine's scalar output; `0.5`=neutral.
- **Recommendation:** confirm canonical (likely `score`) then apply RR-002; the `0.5` is the
  same neutral-fusion contract as `convergence_controller` → likely KEEP the neutral, remove only
  the alias. **Needs canonical confirmation.**

## AC-002 — `engine_runner.py:639` `direction` vs `signal_dir` (+ `or 1`)
- **Current:** `int(input_data.get("direction", input_data.get("signal_dir", 1)) or 1)`.
- **Who consumes:** sets `_gauss_dir` for gaussian short/long feature mirroring.
- **Evidence:** backtest sets `direction`==`signal_dir`==`trade_direction` (same int,
  `backtest_v2.py:2128-30`); live sets `direction` (`live_engine_hook.py:678`). Comment (635-7):
  "Falls back to 'long' when direction is absent (live path without explicit direction)."
- **Question:** are `direction`/`signal_dir` synonyms (→ RR-002 collapse to `direction`)? And is
  `or 1` (default-LONG) an intended live-path default or a corruption-mask? Note this is the
  *input-side* sibling deferred from RR-002.
- **Recommendation:** collapse alias to `direction`; **escalate the `or 1`** — defaulting an
  absent/0 direction to LONG for mirroring may be intended (live) or masking.

## AC-003 — `engine_runner.py:682` `final_score` vs `score` cross-dict (+ 0.0)
- **Current:** `float(rr_fusion_result.get("final_score", rr_result.get("score", 0.0)))`.
- **Evidence:** falls back from `rr_fusion_result.final_score` to a *different dict*
  `rr_result.score`, then `0.0`. Cross-object fallback (not a pure alias).
- **Question:** is reading `rr_result.score` when `rr_fusion_result.final_score` is absent a real
  contract (fusion-disabled path) or a mask? Is `0.0` a valid RR score or corruption?
- **Recommendation:** **escalate** — this is a cross-dict fallback, higher risk; needs the
  fusion-enabled/disabled contract clarified.

## AC-004 — `ultron_risk_gate.py:251` `symbol` vs `instrument` (+ `""`)
- **Current:** `trade.get("symbol", trade.get("instrument", ""))`.
- **Evidence:** `instrument` = dominant internal name (telemetry/agent/logging); `symbol` =
  broker/live boundary (`mt5_bridge.py`, `journal/trade_logger.py`). `""` → `if instrument:` skips
  the optional FRAG-2 duplicate-guard (documented legacy-caller path — benign structured-skip).
- **Question:** are `symbol`/`instrument` the same concept (→ pick canonical, RR-002) or a
  legitimate broker↔internal **boundary translation** to keep?
- **Recommendation:** likely a real boundary alias — either KEEP (boundary translation) or add an
  explicit normalization at the boundary. The `""`-skip is benign; leave it.

## AC-005 — `hierarchical_meta_fusion.py:204` `expected_rr` vs `rr` (+ 0.0)  [LOW PRIORITY]
- **Current:** `rr_result.get("expected_rr", rr_result.get("rr", 0.0))`.
- **Evidence:** HMF is **sidecar-only** (F-012, zero spine consumption) — lowest risk/priority.
- **Recommendation:** defer; collapse alias to canonical when HMF is next touched.
