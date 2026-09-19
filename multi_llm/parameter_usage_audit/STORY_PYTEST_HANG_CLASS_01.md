# STORY-PYTEST-HANG-CLASS-01 — Suite does not complete under 120s per-test timeout

**Status:** OPEN (harness) — **not related to fail-closed Path A**
**Opened:** 2026-09-20
**Unrelated to:** STORY-PARAM-AUDIT-01 / fail-closed CRTConfig

## Symptom

The conditioned full-suite run cannot finish under `--timeout=120 --timeout-method=thread`. At least three tests hit the 120s ceiling in **different** subsystems. Each conditioned attempt aborts in the first ~30% of the suite once a timeout stops forward progress.

## Members observed

1. `tests/research/test_trace_corpus.py::test_pit_alignment_features_join_by_stream_position`
   - Path: FeaturePipeline → SMC `detect_causal_swings`
   - Family: SMC / causal swings
2. `tests/research/test_xauusd_spine_smoke.py::test_spine_collect_runs_on_frozen_candidate_without_active_version_drift`
   - Path: same FeaturePipeline → `detect_causal_swings`
   - Family: SMC / causal swings (sibling of #1)
3. `tests/test_blind_label_harness.py::test_html_leaks_no_answer_value`
   - Path: blind-label harness (HTML leak check)
   - Family: **not SMC** — proves one-at-a-time deselect will not converge

## Members pending discovery

Populated by the `--timeout=30` triage pass (`triage_timeouts.txt` / `HANG_DESELECT_LIST.txt`).

## Hypotheses

- (a) Genuine infinite loops / hot loops in N tests
- (b) 120s is too aggressive for this environment (CI/desktop overhead)
- (c) Test-order dependence
- (d) Shared fixture leaking state across tests

## Timeout method note

Orchestrator already passes `--timeout-method=thread` (required for C-extension hot loops; `signal` would be decorative on Windows). `pyproject.toml` `[tool.pytest.ini_options]` does **not** set a default timeout method — method must stay explicit on the CLI.

## Not related to fail-closed A

Confirmed: BEFORE and AFTER surfaces both hang on the same nodes. Path A verification (PERMISSIVE pad 13/13 green; expected provenance reds; pre-existing census/reachability) is a separate track. This story is harness confidence for the full-surface name-diff.

## Measurement handling

After triage: deselect **all** enumerated hangs in one shot on both sides of the conditioned BEFORE/AFTER diff. Do not drip-feed single deselects.

## Resolution (separate)

Classify each member as hung vs merely slow; fix or quarantine. Out of scope for commit A.

## Hang #3 isolate (2026-09-20)

Ran 	est_html_leaks_no_answer_value alone with `--timeout=600 --timeout-method=thread`.

**Result:** ERROR at setup in 121s — not a pytest-timeout kill.

Fixture `_run_sampler` uses `subprocess.run(..., timeout=120)` on `scripts/analysis/blind_label_sample.py`. That hard cap expires first. So #3 is either:
- sampler slower than 120s on this machine, or
- sampler hung (needs direct run without the fixture cap to distinguish).

pytest-timeout=600 never engaged. Different failure class from SMC hangs #1/#2.


## Triage result (2026-09-20 ~01:29 IST)

**Status line:** TRIAGE_DONE exit=1 elapsed_sec=201.5 timeout_nodes=0 failed_or_error=0

### Hang #3 direct sampler probe

hang3_sampler_direct.txt: **HUNG_OR_SLOWER_THAN_300S** (ELAPSED_SEC=300.0).
Verdict: sampler did not finish inside 300s wall — treat as hang-class member (slow vs infinite not further split). Empty hang3_sampler_out/.

### Full-suite --timeout=30 --timeout-method=thread

- Log: 	riage_timeout30.txt progressed to ~25% then dumped a pytest-timeout stack on
  	ests/research/test_trace_corpus.py::test_pit_alignment_features_join_by_stream_position
  inside FeaturePipeline -> detect_causal_swings / breaker path.
- Suite did **not** produce a short-test summary; _run_triage.py regex extract therefore wrote
  **empty** HANG_DESELECT_LIST.txt and empty 	riage_failed_or_error.txt.
- Enumeration is **incomplete** — runner aborted/stuck around hang #1 before scanning the rest.

### Members after triage (still the known three; list file empty)

1. 	ests/research/test_trace_corpus.py::test_pit_alignment_features_join_by_stream_position — reconfirmed in 30s triage dump
2. 	ests/research/test_xauusd_spine_smoke.py::test_spine_collect_runs_on_frozen_candidate_without_active_version_drift — prior member (suite died before re-hit)
3. 	ests/test_blind_label_harness.py::test_html_leaks_no_answer_value — sampler >=300s direct; fixture 120s TimeoutExpired

**timeout_method:** orch CLI already passes --timeout-method=thread; pyproject.toml has no default method.

**Next (user choose):** deselect-all known three + dual conditioned re-run, **or** ship Path A with this harness track left open. Do not drip-feed one-at-a-time deselects.
