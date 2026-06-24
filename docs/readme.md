# docs/ — Documentation index

The repo front door is [`../README.md`](../README.md) (Quick Start + the tiered docs map).
This file is the **map of `docs/` itself**: what each folder holds and the naming rule new
docs must follow.

## Folder layout (semantic)

| Folder | Holds | Examples |
|---|---|---|
| [`reference/`](reference/) | Stable "how it works / how to work" + process references. | `architecture.md`, `conventions.md`, `schemas.md`, `config-reference.md`, `cli-matrix.md`, `testing.md`, `governance.md`, `agent-reference.md`, `control-plane.md`, `example-service.py` |
| [`architecture/`](architecture/) | The "own the codebase" maps / loadable context units. | `goal.md`, `signal-flow.md`, `codebase-state-map.md`, `service-boundary-map.md`, `event-taxonomy.md`, `code-map.md` (+ `code-map.generated.md`), `replay-governance.md`, `llm-governance-layer.md`, `trigger-vocabulary.md`, `services/` |
| [`analysis/`](analysis/) | Historical, point-in-time analyses & audits — **not living docs**. | dated reports; see [`analysis/readme.md`](analysis/readme.md) |
| [`plans/`](plans/) | Session implementation plans (auto-mirrored from `~/.claude/plans/`). | `claude-architecture-migration-eager-wreath.md` |
| [`handover/`](handover/) | Handover notes. | `jarvis-crt-handover-v3.md` |
| [`human-language-analysis/`](human-language-analysis/) | Plain-language per-module/script walkthroughs. | `src-core-*.txt`, `gaussian.txt` |

## Naming convention (apply to every new doc)

- **Files:** `kebab-case` with a lowercase extension — `config-reference.md`, `code-map.md`.
  (The old `SCREAMING_SNAKE.md` style is retired.) Dated reports keep the date suffix
  (`system-analysis-report-2026-04-21.md`). A leading `_` is allowed for templates
  (`services/_template.md`).
- **Folders:** `lowercase-kebab` named for their *semantic category*, not a tool or author.
- **Generated files** carry a `.generated.` segment and a "do not edit" header
  (`code-map.generated.md`); regenerate them, don't hand-edit.

## Authoritative-source rule

When two docs seem to disagree, the owner wins: operating rules → [`../CLAUDE.md`](../CLAUDE.md);
goal/invariants → [`architecture/goal.md`](architecture/goal.md); runtime flow →
[`architecture/signal-flow.md`](architecture/signal-flow.md); events + CRT states →
[`architecture/event-taxonomy.md`](architecture/event-taxonomy.md); commands →
[`reference/cli-matrix.md`](reference/cli-matrix.md); config → `configs/production/*.json`.
