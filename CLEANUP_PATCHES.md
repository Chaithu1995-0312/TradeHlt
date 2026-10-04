# CLEANUP_PATCHES.md — Applied FORBIDDEN removals

> Every diff that converts a corruption-masking fallback to fail-fast. Each entry records the
> class, the corruption-masking justification, and the **empirical** byte-identical confirmation
> (determinism + golden + oracle + full-suite delta vs `fallback_sweep_before.txt`).
>
> Rule: a removal that drifts any gate is **reverted** and the site reclassified AMBIGUOUS — it is
> NOT kept. So every entry below is, by construction, gate-green.

**Baseline (pre-sweep):** `fallback_sweep_before.txt` — **10 failed, 1787 passed, 32 skipped, 2
xfailed** (1309s). The 10 failures are pre-existing and unrelated (replay/cluster zone-registry +
`test_agents_path_alignment`); recorded in `.fallback_before_failures.txt`.

---

## Batch 1 — `src/config_layer/` (config-load masks + RR-001/002/003/005)

### P1 · `rr/rr_pattern_miner.py` — RR-001 + RR-005
- **Removed:** outer `except Exception: _RR_CFG = {}` config mask; 7 soft `.get(key, literal)` reads
  (all keys present + matching in active cfg); the `_rr_min`/`_rr_max` absent-key soft defaults.
- **Now:** strict `_get_section("rr_model")` + strict `_RR_CFG["..."]` reads; clamp bounds are
  module constants `RR_SCORE_MIN=-3.0` / `RR_SCORE_MAX=5.0` (RR-001). Inner `ImportError`
  dual-path preserved.
- **Justification:** the `except → {}` swallowed config-absence into an empty dict that would let
  every downstream `.get` silently use coded defaults. Section + keys are governed → strict.
- **Byte-identical:** ✅ rr_fusion engine tests (9), golden+invariants+oracle (225), determinism (14).

### P2 · `rr/rr_fusion.py` — RR-005
- **Removed:** outer `except Exception: _DRIFT_THRESHOLD = 1.5` + soft `.get("drift_threshold", 1.5)`.
- **Now:** strict `_get_section("rr_model")["drift_threshold"]`; inner `ImportError` dual-path preserved.
- **Justification:** `rr_model.drift_threshold = 1.5` is present in active cfg; the doubled fallback
  masked both import failure and config-absence.
- **Byte-identical:** ✅ (same gate run).

### P3 · `crt_gaussian_scorer.py` — RR-005
- **Removed:** `except Exception: _GS_CFG = {}` config mask.
- **Now:** strict `_get_section("gaussian_scorer")`; added `ImportError` dual-path (preserved).
- **Justification:** `gaussian_scorer` section present in active cfg; `{}` fallback would silently
  degrade the scorer to defaults on any load error.
- **Byte-identical:** ✅ (golden/oracle/determinism green).

### P4 · `execution_planner.py` — RR-002 + RR-003 (atomic, RR-004)
- **Removed (input read, lines 215, 342-343):**
  `int(engine_result.get("direction", engine_result.get("selected_direction", 0)))`
- **Now:** `int(engine_result["selected_direction"])`.
- **Atomic fixture updates (RR-004):** docstring `:172`; in-module `__main__` fixtures `:425`,`:469`;
  test fixtures `tests/test_execution_planner.py` `_engine` helper + `:214/:258/:264`;
  `tests/test_breakout_disp_threshold.py:23` — all `"direction"` → `"selected_direction"`.
- **Untouched (different contracts):** plan **output** field `direction` (`:287`) + its assertions;
  per-engine fusion/gate dicts; `engine_runner.py:639` input-side (separate AMBIGUOUS-B).
- **New test:** `test_missing_selected_direction_fails_loud` locks RR-003 (absence → KeyError).
- **Behavior table:** `1`/`-1`→trade · `0`→reject_invalid (unchanged) · missing→KeyError (new, intended).
- **Byte-identical (spine):** ✅ planner suite 45 pass, golden/oracle/determinism green — the
  rename is spine-neutral (EngineRunner already emits `selected_direction`).

**Full-suite delta vs baseline:** `fallback_sweep_after_b1.txt` = **2 failed, 1796 passed, 32
skipped, 2 xfailed** (baseline: 10 failed / 1787 passed). **NEW failures vs baseline = 0** ✅
(acceptance criterion met). The 2 remaining are both pre-existing (`test_agents_path_alignment`,
`test_timing_reconstructor::test_scanner_path_matches_offline_rewalker`). 8 baseline failures
(`tests/replay/test_assign_cluster.py`) flipped to passing — **confirmed pre-existing full-suite
order/isolation flakiness, NOT a Batch-1 side effect** (file passes 12/12 in isolation on the
modified tree; the touched modules — rr/gaussian/planner — are unrelated to replay zone-clustering).

---

(Batches 2-5 appended as worked.)
