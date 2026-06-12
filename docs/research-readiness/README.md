# Research-Readiness Audit — 2026-06-12

> **Mission:** prove the repository is a clean, deterministic, auditable instrument *before*
> new trading research begins. Research built on bugs, dead configs, split-brain version truth,
> dormant paths, telemetry gaps, or doc drift produces **false findings**. This bundle is the
> evidence that the lab itself is trustworthy. **Infrastructure-only** — zero strategy/entry/exit/
> config-tuning changes.

**Branch-scoped truth (CLAUDE.md §4.0):** all statements below are for branch `patch`,
`ACTIVE_VERSION = v2_multi_2026_04` (F-016). v4/TP3 applies only to the post-TP3 code line.

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
  every active-config key READ_AND_USED / READ_BUT_INERT / SHADOW_ONLY / HARDCODED_OVERRIDE / DEAD.
- **`src/analytics/metrics_oracle.py`** extended with independent `sharpe()` + `recovery_factor()`,
  parity-checked against production `PortfolioAnalytics` Sharpe + invariant-tested.
- **`tests/runtime/test_replay_determinism.py`** extended to assert telemetry-artifact identity
  across runs and to cover a second instrument.

## Headline

The **core spine + Backtest Trust Layer are sound** (metrics oracle parity, golden ledgers,
invariants, replay determinism all GREEN; spine determinism proven byte-identical). The lab's
untrustworthiness is concentrated, not diffuse: a **config↔code split-brain** (the active pre-TP3
config lacks sections HEAD code expects), a handful of **hardcoded config knobs that silently
no-op when tuned**, **branch-mixed tests** polluting the suite, and **dormant-sidecar** noise.
None of these touch the scoring→fusion→decision→backtest→metrics path. See
[research-readiness-report.md](research-readiness-report.md) for grades + remediation roadmap.
