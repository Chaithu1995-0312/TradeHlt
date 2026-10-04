# ZoneGate investigation — CLOSED (2026-07-22)

## Outcome

The ZoneGate engineering investigation is complete. Three defects found by the original
trace were remediated, and the last open ZoneGate question (the 41.4% assignment parity)
is resolved. **No further work on this surface is warranted** — continuing to reinterpret a
metric on a gate proven decision-inert would be optimization theater (§6.5).

**Honest value accounting:** zero economic value. ZoneGate was inert before (F-036
ΔG001 ≡ 0) and is inert after; nothing here earned it authority. What was bought:

- a live gating artifact went from **unreproducible → reproducible** (converter recovered),
- a test file that **could not fail** now can (and the scoring kernel has its first tests),
- **two lying labels corrected** (`no_zones_fail_open` blocked; "the live gate partitions"),
- one recorded oddity **retired with measured evidence** instead of left as a latent defect.

## What shipped

| Item | Result |
|---|---|
| `tests/test_zone_gate.py` | rewritten; 8/9 dead tests removed; first direct unit tests of `compute_gaussian_score`; mutation-verified |
| `tests/test_unified_replay_harness.py` | new home for the misfiled replay test |
| `scripts/analysis/zone_registry_provenance_probe.py` | provenance `RECONSTRUCTED_EXACT` |
| `scripts/research/convert_zones_v1_to_gaussian.py` | recovered converter; `--compare` = IDENTICAL |
| `scripts/analysis/zone_assignment_parity_probe.py` | parity measured; oracle reproduced exactly (delta 0.0) |
| `src/engines/live_engine.py` | `no_zones_fail_open` → `no_zones_fail_closed` (behavior unchanged) |
| docs: findings · topic · lineage audit · `zone_label_audit` docstring | scoring-vs-partitioning correction + closure |

`PRODUCTION_BEHAVIOR_CHANGED = NO` throughout. No new finding filed — confirming a metric
behaves as its construction implies is not a discovery.

## Three corrections worth carrying forward (method, not ZoneGate)

1. **Judge against the right baseline.** Zone_3 looked anomalous against *label* share and
   was not against the *runtime* marginal (lift +0.0495, 2nd smallest). The wrong baseline
   manufactures anomalies.
2. **Never average a bimodal statistic.** My own `mean_gradient` collapsed opposing signs
   into `instability_driven = False` and would have shipped that into the findings doc.
3. **A wrong name outlives a wrong number.** Both defects this session were *labels*
   asserting what code does not do, and both had propagated into tests that encoded them.

## Residual items — NOT mine to close silently

| Item | Why it is open |
|---|---|
| 4× `tests/test_engine_runner_dual_gate.py` RED | Pre-existing: working tree refactored `engine_runner.run_zone_gate_engine` → `score_zone_cluster`, test still monkeypatches the old symbol. Never touched by this session. |
| `tests/test_session_log.py` — 2 entries missing `Open Questions` | Blocks #48/#49 are another session's XAUUSD R2.5 entries. Not edited: I don't know their open questions and writing "none" would fabricate governance content. |
| `assistant_project.md` over the 30-entry cap (now 50 blocks) | `rotate_session_log.py` archives content — needs an explicit decision, not a silent trim. |
| `test_current_findings` RED (`'RESEARCH'` type) | Pre-existing, unrelated to ZoneGate. |

## Next frontier (decision value, per direction given)

The CRT–geometry thread, precisely stated:

- **F-047** established the ontology as authoritative and pinned GD-001…GD-010. The
  load-bearing one is the NON-CANONICAL `body_ratio` (body/total_wick) at
  `live_engine_hook.py:361`, decision-reachable **in code** but execution **conditional**.
- **Its remediation is BLOCKED behind F-048**, whose intent question is still open:
  the DecisionEngine RR gate compares `fusion["rr"]` — an RREngine *polarity* score ∈[0.5,1]
  — against `rr_threshold = 1.5`, so `low_rr` fires every candle and `run()` returned
  `execute` 0/70,002 times. `ExecutionPlanner:208` hard-gates on `run()=="execute"`.
- **The open decision is binary and yours:** *unintended mis-wire* (the live path can
  structurally never admit a trade — which would bear directly on F-010's unverified live
  PnL) or *dormant-live-by-design*. F-047 recorded the mismatch as Certain but left intent
  undetermined; no positive control for the body_ratio work is constructible until it is
  settled.

This has real decision value in a way the parity metric never did: it is about whether the
live path can trade at all, not about how a telemetry field partitions.

**Not started.** Opening it requires the intent decision first — that is a judgment call
about original design intent, not something to infer from code.
