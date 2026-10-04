# AGENTS.md

> **This file is a pointer, not the source of truth.**

The authoritative operating manual for this codebase is **[`CLAUDE.md`](CLAUDE.md)** — it
owns the conventions, the response ritual, the SESSION LOG mandate, the constraints, and the
trigger vocabulary. `AGENTS.md` is retained only because some tools look for a file by this
name; it deliberately does **not** duplicate the doctrine (the previous duplicated copy had
drifted out of date).

**Start here:**
- Grok session? → [`.grok/rules/GROK.md`](.grok/rules/GROK.md) (auto-loaded harness). Repo-root [`GROK.md`](GROK.md) is a pointer only.
- New to the repo? → [`README.md`](README.md) (Quick Start + docs map).
- Operating rules / how to work → [`CLAUDE.md`](CLAUDE.md).
- LLM cold-start recipe → [`docs/architecture/TRIGGER_VOCABULARY.md`](docs/architecture/TRIGGER_VOCABULARY.md).

**Before MODIFYING the repository (non-optional):**
- [`docs/governance/REPOSITORY_CONSTRUCTION_PROTOCOL.md`](docs/governance/REPOSITORY_CONSTRUCTION_PROTOCOL.md)
  — the mandatory change lifecycle. Classify the change against
  [`docs/governance/change_contracts.json`](docs/governance/change_contracts.json), produce a
  BUILD_IMPACT_MANIFEST (STOP on blocking UNKNOWN), implement through the canonical authorities
  (ontology → registry → implementations — never local formula math), then validate completion:
  `python scripts/governance/construction_protocol.py validate-completion <manifest>`.
  One-command floor: `python scripts/governance/construction_protocol.py check`.
  Completion claims are mechanically constrained — the census freshness floor and the CI GREEN_FLOOR
  fail on ungoverned feature math whether or not this file was read.
