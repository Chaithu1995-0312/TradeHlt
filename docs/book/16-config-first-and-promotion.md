# Chapter 16 — Config-First Doctrine and the Promotion Path

**Part VI — Governance**
Status of this chapter: Written

## Why this chapter exists

Parts II–V described the engine as it exists at one point in time. This chapter starts Part VI by
explaining how that engine is meant to *change over time* — through configuration, under a formal
gate — rather than through direct code edits chasing whatever the latest backtest suggested.

## What problem it solves

Answers two related questions: what's allowed to be a config knob versus what has to stay in code,
and what a config has to prove before it's allowed to become the one running in production.

## What you need to already know

[Chapter 2](02-invariants-and-happy-flow.md)'s invariant #4 (no config reaches production without
governance) — this chapter is that invariant's full mechanism.

## The idea

### Config-First: the target end-state

The doctrine's stated target is **"Frozen Engine + Mutable Behavior + Governed Evolution."** Code
changes should become rare; config changes should become routine; and the system should improve by
*generating configs* — sweeps, tuning, promotion — rather than by rewriting engines. Every constant
in the codebase is meant to be classified into one of three tiers before it's touched:

| Class | Examples | What happens to it |
|---|---|---|
| **STRUCTURAL** | interfaces, enum members, the CRT transition graph, execution order, vector dimensions | Stays frozen in code — changing it is expected to be rare and expensive |
| **BEHAVIORAL** | thresholds, weights, percentiles, clamps, tier boundaries | Externalized into a config section |
| **GOAL-SEEKING** | candidate-config generation, sweeps, promotion itself | Generated *as* config; the engine underneath stays untouched |

A knob climbs a maturity ladder — `HARD_CODED → CONFIG_WIRED → CONFIG_DRIVEN` — with goal-seeking
(automated search) as an orthogonal, optional further step, not a requirement for every knob.

### The hard rule: no silent defaults

New behavioral knobs must be introduced through a strict `_require()` boundary — a missing config
key is an **error**, never a soft `.get(key, some_literal)` fallback. This closes a specific,
previously-real failure class where an active production config quietly lagged the code schema and
ran on undocumented defaults without anyone noticing. Every migration to config additionally needs a
parity proof: the new JSON value must equal the prior hardcoded literal, read strictly, producing a
byte-identical backtest ledger — any drift means the JSON default was wrong, and the determinism
gate catches it.

### The Authority Ladder — tunable is not the same as trusted

A knob becoming config-driven grants **tunability**, never **authority**. The doctrine draws four
distinct rungs, and conflating them is exactly the mistake this ladder exists to prevent:

```
Information exists  →  Economic usefulness exists  →  Authority earned  →  Architecture justified
```

A statistically detectable signal is not automatically economically useful; an economically useful
signal doesn't automatically earn production/fusion weight; and even a successful consumer of a
signal doesn't automatically justify adding more architectural complexity around it. Only a
*demonstrated* improvement to the system's own economic goal metric (`G001`, [Chapter 1](01-why-tradelatest-exists.md))
earns a rung. This is the same discipline behind [Chapter 9](09-interpreters-pattern-contract.md)'s
Interpreter Contract and [Chapter 19](19-research-programs.md)'s research falsification programs,
stated here at the level of a general rule.

### The promotion path itself

A new config's journey to production is a fixed pipeline:

```
AutoTuner → results/tuner/checkpoint_multi.json
          → ConfigValidator.validate(params, csv_paths, config_id)
              — runs a per-instrument backtest against quality gates:
                HARD: min trade count, max drawdown
                SOFT: win rate, expectancy, cross-instrument variance
          → ValidationReport{decision: APPROVE | REJECT}
              REJECT → results/validation/rejected/
              APPROVE → results/validation/approved/
          → PromotionManager.promote_from_report()
              — computes a SHA-256 config hash
              — archives the currently-active config
              — writes the new configs/production/{version}.json
              — appends an immutable line to configs/promotion_log.jsonl
```

Promotion refuses outright on a non-APPROVE decision, a duplicate version name, a hash-computation
failure, or a write failure — and a write failure triggers an automatic rollback plus a
`PROMOTION_FAILED` log entry, never a silent partial write. This is what makes
`configs/production/ACTIVE_VERSION` (the Tier-0 runtime truth per `CLAUDE.md` §4.0) trustworthy: it
can only ever point at something that passed this exact gate.

## Classification

| Concept | Status |
|---|---|
| Config-First Doctrine (classification tiers, maturity ladder, no-silent-defaults rule) | Production doctrine, actively enforced (`behavior_census.py` + test floor) |
| The Authority Ladder | Production doctrine, cited throughout Parts VI–VII |
| `PromotionManager` / promotion pipeline | Production |
| `ConfigValidator.validate()` hard/soft gates | Production |

## Authoritative sources

- `CLAUDE.md` §6.5 — the full Config-First Doctrine, including the Authority Ladder and the
  behavioral-vs-structural classification table.
- `docs/reference/governance.md` — the full `PromotionManager` API (`promote_from_report`,
  `promote_from_tuner_checkpoint`, `promote_direct`, `list_versions`, `load_version`, rollback
  procedure) — this chapter summarizes §1 of it; the rest is a direct reference, not duplicated here.
- `src/governance/promotion_manager.py`, `src/config_layer/config_validator.py`.
- `scripts/analysis/behavior_census.py` + `tests/test_behavior_census.py` — the enforcement contract
  pinning each migrated module's maturity so it can't silently drift back into code.
- `docs/topics/promotion-governance.md`, `docs/topics/config-validation.md` — the always-synced topic docs.

## Unresolved questions

None — this is one of the most thoroughly, explicitly documented doctrines in the repository.

---
**Encyclopedia:** [E3 — Governance Tooling](encyclopedia/E3-governance-tooling.md)

**Previous:** [Chapter 15 — Live Execution and INOUT](15-live-execution-and-inout.md) · **Next:** [Chapter 17 — Truth Maintenance](17-truth-maintenance.md)
**Related:** [Chapter 12 — The Decision Engine](12-decision-engine.md) (F-048 as a worked Config-First-adjacent example) · [Chapter 19 — The Research Programs](19-research-programs.md) (the Authority Ladder applied to research findings)
**Memory:** `docs/memory/governance-memory.md`.
