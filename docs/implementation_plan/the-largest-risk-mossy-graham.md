# IC-007 / PLAN-002 closure bookkeeping — wire F-052 into the truth index + log the closure

## Context

DeepSeek executed the PLAN-002 closure correction (remove the second engines-path CODE
authority — the `(0.35,0.25,0.20,0.20)` fallback tuple in `engines.crt_engine.compute`) while I
was away. Review of the actual repo state confirms the **implementation is correctly done**:

- `src/engines/crt_engine.py` — missing `context["score_component_weights"]` now `raise`s a
  `KeyError` *inside* the existing `try/except Exception`, so `compute()` returns
  `{"score": 0.0, "reason": "score_component_weights missing…"}` — **fail-closed, no silent CODE
  literal**. (The reviewer's wording concern is real and is **already pre-corrected** in F-052's
  Note: it does NOT propagate an exception externally.)
- All real callers pass the key explicitly: `engine_runner.py:678` (config-injected),
  `s01_crt_wrapper.py` (new `_load_score_component_weights()` from prod config, fail-closed),
  both probes (`feature_math_drift_probe.py`, `pit_swing_blast_radius.py`) pass explicit legacy
  vectors. Tests either monkeypatch `crt_compute` (dual-gate/rr-fusion) or assert the fail-closed
  path (`test_plan002_dual_weights_how.py`).
- **F-052 is recorded** in `docs/current-findings.md` (call-site census 18 matches / 0 legit
  implicit-default callers, files changed, 38/38 focused tests, Reversal, precise fail-closed
  Note) with Type=GOVERNANCE, Status=VALIDATED, Confidence=Certain.

**Two gaps remain — both governance bookkeeping, matching the reviewer's "What We Don't Know":**

1. **F-052 is absent from the CLAUDE.md Repository Truths Index**, so the enforcement floor
   `tests/test_current_findings.py::test_index_and_doc_agree_on_nonterminal_ids` is **RED**
   (`non-terminal findings absent from CLAUDE.md Repository Truths Index: ['F-052']`). This is
   the *only* failing check across the whole construction floor (121 passed / 1 failed).
2. **No §6 SESSION LOG entry** records this closure correction (DeepSeek wrote the finding but
   not a log entry).

**Broader-suite status (the reviewer's other "don't know") — resolved by read-only verification:**
the affected surface is **green**: `test_plan002_dual_weights_how` + engine_runner dual-gate +
rr-fusion + zone_gate + crt_fixes + crt_adversarial_closure + active_models + golden ledgers =
**102 passed / 8 skipped**; construction `check` = 121 passed, the single red being the F-052
index row. The two PLAN-002 manifests' `declared_files` are the dirty-tree union, so they already
cover the closure-correction files (`crt_engine.py`, `s01_crt_wrapper.py`, the probes) — no
manifest churn needed.

## Change (docs-only; zero code/config edits)

1. **Wire F-052 into the truth index.** Insert one row into the CLAUDE.md "Repository Truths
   Index" table immediately after the F-051 row (CLAUDE.md:360), matching the existing
   `| F-id | TYPE | conclusion | Conf |` format:
   `| F-052 | GOV | PLAN-002 closure — the 2nd engines-path CODE authority (the (0.35,0.25,0.20,0.20) fallback in engines.crt_engine.compute) removed: missing score_component_weights now FAIL-CLOSED (returns score 0.0 + reason, not a silent CODE literal, not a propagated exception); all real callers (EngineRunner, S01CRTWrapper, probes) inject the HOW key; conf_weights + risk_score_weights untouched; the two weight identities stay distinct | Certain |`
   This turns the RED floor green (index ↔ doc agree).

2. **Append a §6 SESSION LOG entry** to `assistant_project.md` recording: the closure-correction
   review verdict (implementation sound, F-052 already recorded, wording pre-corrected), the
   index-row wiring, the read-only broader-suite verification (102 passed on affected surface +
   121/1 construction), and the precise fail-closed behavior statement. Rotate first if the log
   is at the 30-entry cap (`rotate_session_log.py`, collision-check the archive name).

## Explicitly NOT doing (reviewer's guardrails)

- No IC-007 implementation changes; no touching `crt_engine.compute` logic, weight values,
  `conf_weights`, or merging the two identities.
- No new broad audit; no PLAN-003 (stays REVISED/not-started — heterogeneous); no surplus
  cleanup beyond this closure.
- Do not modify PLAN-001.

## Verification

- `venv/Scripts/python.exe -m pytest tests/test_current_findings.py -q` → all green (the index
  ↔ doc agreement test flips red→green).
- `venv/Scripts/python.exe scripts/governance/construction_protocol.py check` → **GREEN**
  (was 121 passed / 1 failed = the F-052 index row).
- `git diff --stat` shows only `CLAUDE.md` + `assistant_project.md` changed (docs-only; no
  `src/`, `configs/`, `models/` edits) — confirming pure bookkeeping.
- Stop after the floor is green for the user to select the next surplus-census candidate (do not
  auto-start the next implementation).
