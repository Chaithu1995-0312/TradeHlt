> Created: 2026-06-01 · Updated: 2026-06-01 · Milestone: Pre-existing failure audit + contract audit

# Context

23 pre-existing test failures across 5 groups. User correctly identified this as a **contract audit** problem, not a simple bug-bash. Before fixing, each group needs its authoritative layer established. Contract audit complete — findings below.

---

# Contract Audit Findings

## Group 1 — `gaussian_shadow` missing attribute (8 failures) — RUNTIME BUG ✗

**Verdict: Fix immediately. No policy ambiguity.**

- `src/core/engine_runner.py:671` accesses `self.gaussian_shadow` during `runner.run()`
- `EngineRunner.__init__` never initialises this attribute
- This is on the main execution spine (`engine_runner → fusion → decision`). Risk: HIGH.
- **Fix:** Add `self.gaussian_shadow = ...` initialisation. Need to read the class to determine correct default.

---

## Group 2 — LLM fail-open returns `0.5` instead of `1.0` (11 failures) — RUNTIME BUG ✗

**Verdict: Runtime is wrong. Tests and docs agree.**

All three sources speak:
- `docs/reference/architecture.md:206` — "returns neutral `1.0`"
- `src/config_layer/llm_scorer.py:116` (docstring) — "fail-open 1.0"
- `tests/test_llm_connectivity.py:135,140,145,150` — explicit `assert score == 1.0  # fail-open sentinel`

Runtime at `llm_scorer.py:85,101,109,220` returns `0.5`.

**Fix:** Change those four lines from `return 0.5` → `return 1.0`.

---

## Group 3 — Feature schema fail-open (1 failure) — POLICY DECISION NEEDED ⚠️

**Verdict: Docs are silent. Tests and runtime disagree. User must decide.**

- `src/features/feature_schema.py:248`: `def check_compatibility(cls, version, fail_closed: bool = True)`
- Default is `fail_closed=True` → unregistered schema version → returns `False` (reject)
- Test expects unregistered version → returns `True` (allow through)
- `docs/reference/schemas.md` and `docs/reference/conventions.md` are both silent on this

Two valid positions:
- **Fail-open (allow unknown):** innovation-friendly, matches test intent — change default to `fail_closed=False`
- **Fail-closed (reject unknown):** governance-friendly, consistent with CLAUDE.md §4 emphasis on validation gates — update test to pass `fail_closed=False` explicitly when testing the opt-in path

---

## Group 4 — ReplayMemoryEngine load failure (2 failures) — INVESTIGATION NEEDED ⚠️

**Verdict: zone_id is optional at code level, but something causes silent load abort.**

Contract audit confirms:
- `zone.get("zone_id", 0)` — optional at runtime
- Test fixtures don't include zone_id — correct per design
- BUT load still fails with: `"load failed (fail-open) — 'zone_id'"`

Root cause is deeper — possibly `z["zone_id"]` bracket access at `replay_memory_engine.py:425` inside a dict comprehension on the zone registry (not the replay records). Need to read the full `_load()` method to confirm before fixing.

---

## Group 5 — Gaussian ML impl mismatch (1 failure) — TEST FIXTURE ISSUE ✗

**Verdict: Test-only fix. No product risk.**

- Production config: `gaussian_impl=heuristic`
- Test expects `MLGaussianEngine`
- Fix: inject `gaussian_impl=ml` in the test fixture's config before constructing EngineRunner

---

# Recommended Execution (pending policy decision on Group 3)

### Phase A — Unambiguous runtime fixes
1. **Group 1:** Initialise `gaussian_shadow` in `engine_runner.py` → removes 8 failures
2. **Group 2:** Change `llm_scorer.py` returns from `0.5` → `1.0` at 4 lines → removes 11 failures
3. **Group 5:** Patch test fixture `gaussian_impl=ml` → removes 1 failure

### Phase B — After policy decision
4. **Group 3:** Either change `fail_closed` default OR update test to use `fail_closed=False` → removes 1 failure

### Phase C — After deeper investigation
5. **Group 4:** Read `_load()` method fully, identify root cause of `'zone_id'` KeyError → removes 2 failures

---

# Verification

After Phase A:
```
pytest tests/test_engine_runner_dual_gate.py tests/test_engine_runner_rr_fusion.py tests/test_llm_scorer.py tests/test_gaussian_impl_switch.py -v
```
Expected: 20 newly passing, 0 regressions.

After Phase B+C:
```
pytest tests/features/test_feature_schema_registry.py tests/replay/test_replay_memory_engine.py -v
```
Expected: 3 newly passing.

Full suite regression check:
```
pytest --tb=no -q
```
Expected: 23 fewer failures, same 1188 passing.
