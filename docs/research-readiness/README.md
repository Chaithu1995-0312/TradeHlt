# Research-Readiness Audit — 2026-06-12

> **Mission:** prove the repository is a clean, deterministic, auditable instrument *before*
> new trading research begins. Research built on bugs, dead configs, split-brain version truth,
> dormant paths, telemetry gaps, or doc drift produces **false findings**. This bundle is the
> evidence that the lab itself is trustworthy. **Infrastructure-only** — zero strategy/entry/exit/
> config-tuning changes.

**Branch-scoped truth (CLAUDE.md §4.0):** all statements below are for branch `patch`,
`ACTIVE_VERSION = v2_multi_2026_04` (F-016). v4/TP3 applies only to the post-TP3 code line.

## Active program (living)

| Program | Files | Role |
|---|---|---|
| **Edge Research Platform** (`EDGE_RESEARCH_PLATFORM`) | **[Decision board](erp-decision-board-and-story-authority.md)** · **[Phased plan](edge-research-platform-phased-plan.md)** · **[Promise ladder](edge-research-platform-promise-ladder.md)** · **[MLLM HOW](edge-research-platform-mllm-how.md)** · **[Research lane](../../multi_llm/research_lane/README.md)** · **[Before/after](edge-research-platform-before-after.md)** · [program](edge-research-platform-program.md) | Multi-LLM Research Lane **initiated**. PL-0. Next: Implement P1. |

Update the MD+JSON pair in the same turn when program state changes. Grants no production authority.

## Deliverables

| # | Deliverable | File | Kind |
|---|---|---|---|
| 1 | Finding inventory (severity + research_blocking) | [finding-inventory.md](finding-inventory.md) | report |
| 2 | Pipeline maps (8 pipelines) | [pipeline-maps.md](pipeline-maps.md) | report |
| 3 | Config reachability report | [config-reachability-report.md](config-reachability-report.md) | **auto-generated** by `scripts/analysis/config_reachability.py` |
| 4 | Metric integrity report | [metric-integrity-report.md](metric-integrity-report.md) | report + oracle extension |
| 5 | Determinism report | [determinism-report.md](determinism-report.md) | report + gate extension |
| 6 | Telemetry completeness report | [telemetry-report.md](telemetry-report.md) | report |
| 7 | Test coverage gap report | [test-gap-report.md](test-gap-report.md) | report |
| 8 | Research readiness score + roadmap | [research-readiness-report.md](research-readiness-report.md) | **hub** |

## Verification gates built this engagement (additive, audit/test-only)

- **`scripts/analysis/config_reachability.py`** + `tests/test_config_reachability.py` — classifies
  every active-config key READ_AND_USED / TOOLING_ONLY / READ_BUT_INERT / SHADOW_ONLY /
  HARDCODED_OVERRIDE / DEAD (corpus = `src/` live spine + `scripts/` tooling; `tests/` excluded).
- **`src/analytics/metrics_oracle.py`** extended with independent `sharpe()` + `recovery_factor()`,
  parity-checked against production `PortfolioAnalytics` Sharpe + invariant-tested.
- **`tests/runtime/test_replay_determinism.py`** extended to assert telemetry-artifact identity
  across runs and to cover a second instrument.

## Test-Authority Ladder (reachability validation) — 2026-07-04

The reachability validators form an explicit authority ladder. **Higher tiers are truth; lower
tiers only observe or alarm.** A golden changing does **not** mean behavior changed — treating it as
truth is the trap this ladder exists to prevent. Ties to CLAUDE.md §6.5 (evidence has no authority;
only demonstrated behavior does).

| Level | Instrument | Authority |
|---|---|---|
| **L1** Behavioral invariants | `tests/test_config_reachability.py::test_no_dead_config_keys`, `tests/test_crt_state_invariants.py` | **CAN FAIL BUILDS** |
| **L2** Generated evidence | `reports/reachability_validation.{json,md}`, `docs/research-readiness/config-reachability-report.{json,md}` | **OBSERVATIONAL** (records what is; no `guards_passed` — CI runs the guards) |
| **L3** Semantic goldens | `tests/test_reachability_golden.py` (config + registry) | **DRIFT DETECTION ONLY** |
| — Human prose | this README, report narratives | lowest |

> **Golden Rule.** *Semantic goldens may DETECT truth changes; they never DEFINE truth. Truth comes
> from code + generators + behavioral invariants.* On an intentional change, accept it explicitly:
> `python scripts/analysis/update_reachability_golden.py` then commit — never edit a golden by hand.

**Enforce this for every new validator added to the repo:** invariant (L1) > generated evidence
(L2) > semantic golden (L3) > prose. New goldens are drift alarms, not truth sources.

## Headline

The **core spine + Backtest Trust Layer are sound** (metrics oracle parity, golden ledgers,
invariants, replay determinism all GREEN; spine determinism proven byte-identical). The lab's
untrustworthiness is concentrated, not diffuse: a **config↔code split-brain** (the active pre-TP3
config lacks sections HEAD code expects), a handful of **hardcoded config knobs that silently
no-op when tuned**, **branch-mixed tests** polluting the suite, and **dormant-sidecar** noise.
None of these touch the scoring→fusion→decision→backtest→metrics path. See
[research-readiness-report.md](research-readiness-report.md) for grades + remediation roadmap.
