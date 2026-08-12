# RESOLUTION_REGISTRY.md — Fallback-sweep decision memory

> Converts ambiguity into doctrine so the same semantic question is never re-debated across
> sessions. One entry per resolved site. **Checked at the start of each batch** so prior decisions
> are reused, not rediscovered. Every AMBIGUOUS-B user decision lands here permanently.

Format:
```
ID · Date · File(s) · Pattern · Evidence · Decision (REMOVE|KEEP) · Classification · Rationale · Tests proving it · Future rule
```

---

## RR-001 — `_rr_min` / `_rr_max` clamp bounds
- **Status:** ACTIVE · **Date:** 2026-06-16 · **Classification:** AMBIGUOUS-B (user-decided)
- **File(s):** `src/config_layer/rr/rr_pattern_miner.py:38-39` (was), now `:34-37`
- **Pattern:** `_RR_CFG.get("score_weights", {}).get("_rr_min", -3.0)` / `_rr_max` 5.0 — keys ABSENT
  from active config, so the literals fired unconditionally.
- **Evidence:** active config `rr_model.score_weights` contains only `gaussian/ml/confidence`;
  `_rr_min`/`_rr_max` are not config keys. They are clamp bounds for the RR raw score
  (`expected_rr = min(RR_SCORE_MAX, max(RR_SCORE_MIN, expected_rr))`).
- **Decision:** REMOVE fallback → module-level structural constants
  `RR_SCORE_MIN = -3.0` / `RR_SCORE_MAX = 5.0` (no config, no `.get`).
- **Rationale:** clamp boundaries are algorithm structure, not business/optimizer knobs. Putting
  them in config would add rehashes + false degrees of freedom + optimizer-abuse surface.
- **Tests proving it:** `tests/test_engine_runner_rr_fusion.py` (9 pass); golden+oracle byte-identical.
- **Future rule:** **Algorithm/clamp boundaries are code constants, not config knobs.**

## RR-002 — `direction` vs `selected_direction` (planner input)
- **Status:** ACTIVE · **Date:** 2026-06-16 · **Classification:** AMBIGUOUS-B (user-decided)
- **File(s):** `src/config_layer/execution_planner.py:215, 342-343`
- **Pattern:** `engine_result.get("direction", engine_result.get("selected_direction", 0))` — two
  names for one concept (multi-name corruption-masker / schema drift).
- **Evidence (contract-backed):** `core/types.py:60` types `selected_direction: int  # 1=BUY,
  -1=SELL,0=none`; `engine_runner.py:948` EMITS `selected_direction`; `spine_adapter.py:82`
  CONSUMES `selected_direction`. The `direction` alias is drift, not flexibility.
- **Decision:** REMOVE the `direction` alias → strict `engine_result["selected_direction"]`.
- **Rationale:** one concept → one name; no multi-name `.get` chains.
- **Tests proving it:** `tests/test_execution_planner.py` (45 pass), `tests/test_breakout_disp_threshold.py`.
- **Future rule:** **One concept → one name.**

## RR-003 — planner direction sentinel `0` (absence vs modeled NONE)
- **Status:** ACTIVE · **Date:** 2026-06-16 · **Classification:** AMBIGUOUS-B (user-decided)
- **File(s):** `src/config_layer/execution_planner.py:215, 342-343`
- **Pattern:** the `, 0)` default in the multi-key read silently mapped *missing field* → `0`.
- **Evidence (refined the decision):** `0` is a *modeled* value (`0=none`, `core/types.py:60`)
  already rejected by the existing gate `if direction not in (1,-1): return reject_invalid`
  (`execution_planner.py:216`). So `0` is NOT corruption; *absence of the field* is.
- **Decision:** REMOVE the silent `0` default. Behavior table: `1`/`-1` → trade; `0` → graceful
  `reject_invalid` (unchanged); **missing field → KeyError (fail loud)**.
- **Rationale:** absence must fail; explicit NONE is allowed; never silently map missing→NONE.
- **Tests proving it:** `tests/test_execution_planner.py::test_missing_selected_direction_fails_loud`
  (new), `::test_reject_invalid_direction_zero` (0→reject preserved).
- **Future rule:** **Absence must fail; do not silently map a missing field to NONE.**

## RR-004 — partial-migration guard (general doctrine)
- **Status:** ACTIVE · **Date:** 2026-06-16 · **Classification:** doctrine (applies to every rename)
- **Pattern:** renaming a canonical field in production without renaming its fixtures/consumers.
- **Decision:** Canonical-field renames are **atomic** — production + in-module fixtures + tests
  change in the **same commit**.
- **Evidence:** execution-planner input contract (RR-002/003 touched production `:215/343`,
  in-module fixtures `:425/469`, and 5 test-fixture sites in 2 test files).
- **Tests:** `test_execution_planner.py`, `test_breakout_disp_threshold.py`.
- **Future rule:** **No half-migrations.**

## RR-005 — config-load `except → {}` / `except → literal` masks (3 config_layer modules)
- **Status:** ACTIVE · **Date:** 2026-06-16 · **Classification:** AMBIGUOUS-A → FORBIDDEN (fire-tested)
- **File(s):** `rr/rr_fusion.py:23-30`, `rr/rr_pattern_miner.py:24-32`, `crt_gaussian_scorer.py:14-18`
- **Pattern:** module-load `try: _CFG = get_prod_section(...) except Exception: _CFG = {} / literal`
  + downstream soft `.get(key, literal)` on present keys.
- **Evidence (fire-test):** the `rr_model` / `gaussian_scorer` sections + all read keys are present
  in the active config and the literals MATCH the config values. Removing the outer `except` and
  hardening present-key reads to strict was confirmed **byte-identical**: determinism (14),
  golden+invariants+oracle (225), rr_fusion (9), config-integrity all GREEN. The outer `except`
  was dead import-resilience, not load-bearing.
- **Decision:** REMOVE outer `except` mask + present-key soft `.get` → strict section/key reads.
  KEEP the inner `ImportError` dual-path (package vs standalone-script) — legitimate optional import.
- **Future rule:** A governed config section/key is read STRICT; only the import mechanism may be
  guarded, never the config presence.

## RR-006 — escalation density / semantic-debt governor
- **Status:** ACTIVE · **Date:** 2026-06-16 · **Classification:** process doctrine
- **Pattern:** semantic-heavy batches (mostly AMBIGUOUS-B sites, e.g. `src/core/`).
- **Decision:** Limit concurrent AMBIGUOUS-B sites — never open more semantic questions than can be
  resolved in one session. Work **site-by-site** (one question at a time), not module-by-module.
- **Rationale:** unresolved ambiguities accumulate like technical debt; **semantic debt is
  inventory.** Optimize escalation-heavy batches for *semantic* throughput, not code throughput.
- **Future rule:** **Never open more semantic questions than can be resolved in one session.**
