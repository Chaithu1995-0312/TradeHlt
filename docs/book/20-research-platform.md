# Chapter 20 — The Research Platform: src/research/

**Part VII — Research**
Status of this chapter: Written (platform map + artifact index expanded Grok pass)

## Why this chapter exists

[Chapter 19](19-research-programs.md) covered the *findings* and **numeric results** the research
effort produced. This chapter covers the *machinery* that produces them: `src/research/`, the single
largest subpackage in the entire codebase (416 files — more than double the next largest), plus its
companion pre-registration corpus in `docs/research-readiness/` and the on-disk result trees under
`results/research/`.

## What problem it solves

Explains why there's so much code here, what shape it takes, **where research configs and outputs
live**, and — importantly — flags a real gap between the research platform's ambition and its
current Measurement Contract implementation state.

## What you need to already know

[Chapter 19](19-research-programs.md) — this chapter is that one's supporting infrastructure.
Read the **Research results at a glance** table there before this map.

## The idea

### Research data map (where things live on disk)

| Layer | Path | What you find |
|---|---|---|
| Living conclusions | `docs/current-findings.md` | `F-0xx` rows with Evidence, Confidence, Status |
| Pre-registrations | `docs/research/preregistration-*.md`, `docs/research-readiness/program-*-preregistration.md` | Frozen hypotheses **before** runs |
| Research configs | `configs/research/research_config*.json`, `configs/research/experiments/` | Per-program / per-asset research knobs |
| Measurement profiles | `configs/research/measurement_contracts/*.v1.json` | `MP-*` profiles (schema ready; MC instances not sealed) |
| Code kernels | `src/research/**` | Drivers, adapters, controls, consumers |
| CLI drivers | `scripts/research/**` | Thin entry points that write artifacts |
| Run artifacts | `results/research/**` | JSON/JSONL ledgers (qualification, phase_*, regime, m5_mtf, weekly_sweep, h_msip_*, …) |
| Family registry | `docs/governance/research_family_registry.json` | Object × layer atlas; most cells `Contract:UNKNOWN` |

**Rule:** a claim without a file under `results/research/` (or an Evidence path in
`current-findings.md`) is not a research result — it is a hypothesis.

### The shape of `src/research/`

Structured as ~17 subpackages plus loose top-level modules. Map of **what research data each
cluster owns**:

| Subpackage / module | Research data role | Tied programs |
|---|---|---|
| `adapters/` | Spine / signal sources for research harnesses | P1 spine arm |
| `candle_state/` | MTF conjunction, transition targets, M5 kernels | P4 / P9 Stage-1 |
| `controls/` | Negative controls every economic arm must beat | All M4 programs |
| `hypotheses/` | Economic consumers (e.g. `compression_box_straddle`) | P9 Stage-2 |
| `weekly_sweep/` | Calendar-locked weekly sweep geometry | P8 |
| `clean_labels/` | Honest label re-derivation (forward_walk class) | RR / Zone audits |
| `cross_sectional.py` | Panel / relative-value kernel | P5 / P6 / P6b |
| `exit_grid.py`, `costs.py` | SL/TP grid + cost model | P1 exit falsification |
| `conditional_entropy_grid.py` | Entropy + economics grid | P1 conditional pockets |
| `resample.py` | Deterministic OHLCV resampler | P3 HTF, P9 MTF |
| `measurement/` | Measurement-contract scaffolding | MC path (OPEN) |
| `ic002_*` / `ic003_*` | Interpreter-candidate shape research | shape / sequence IC tracks |
| `zone_mapping/` | Zone assignment research | ZoneGate audits |
| `secondlow_v1/`, `path/`, `episodes/` | Path / episode / second-low experiments | specialized tracks |
| `synthetic/`, `envelope_offline/`, `model_runners/`, `forensics.py` | Synthetic data, offline envelope, model runners, forensics | supporting |

Loose shared modules also include: `experiment_spec.py`, `goal_alignment.py`.

### The Edge Research Platform (ERP)

`docs/research-readiness/` documents a broader design — the "Edge Research Platform" — covering how
research should flow end-to-end: an information-class boundary, a phased plan, a "promise ladder"
(explicitly the doctrine-side counterpart of the Authority Ladder from [Chapter 16](16-config-first-and-promotion.md)),
and how multiple LLMs collaborate on research work (tying into [Chapter 23](23-multi-llm-coordination.md)).
This directory also holds every individual program's pre-registration document
(`program-N-*-preregistration.md`) and a series of individual hypothesis pre-registrations (`h-*`
files) for smaller, single-hypothesis tests that don't rise to full-Program scale.

### An honest gap: the Research Measurement Contract exists on paper, not yet in code

One specific piece is worth flagging precisely because it's easy to miss: `docs/governance/MEASUREMENT_CONTRACT.md`
defines a frozen (as of 2026-07-10) schema meant to make every research claim's measurement basis —
label derivation, cost model, gate mode, clock basis — explicit and comparable across experiments,
backed by a 27-seed adversarial mutation test matrix. As of the most recent verification available
to this book, **zero `MC-*` instances have been sealed and none of the 27 probes have been
implemented** — every finding in `docs/current-findings.md` currently carries `Contract: UNKNOWN`.
This does not invalidate the Program 1–8 findings in [Chapter 19](19-research-programs.md) — they
were run under their own program-specific rigor (pre-registration, honest costs, absolute-expectancy
bar) — but it does mean the *cross-program comparability* layer the Measurement Contract is meant to
provide doesn't exist yet. Anyone tempted to compare two programs' results side by side should treat
that comparison as informal until this layer is built.

### Proposed path to close the gap (Grok review — roadmap, not an implement claim)

The review correctly treats 0 sealed `MC-*` instances as a **research-infrastructure** gap, not a
failure of Programs 1–8. A minimal credible path (still owner-gated; this book does not execute it):

| Step | Deliverable | Why it matters |
|---|---|---|
| **1. Seal one profile-bound MC** | One `MC-*` instance bound to an existing measurement profile (`configs/research/measurement_contracts/*.v1.json`, `MP-*` namespace) for a *closed* program (e.g. Program 8 or F-040's Stage-2) | Proves the schema is fillable from real artifacts, not only from theory |
| **2. Implement E-MT-00 + E-MT-01** | First two probes of the 27-seed mutation matrix | Turns "frozen schema" into "adversarially checked schema" |
| **3. Bind registry rows** | Update `docs/governance/research_family_registry.json` object×layer cells from `Contract:UNKNOWN` → sealed id for the programs just covered | Makes the atlas machine-queryable |
| **4. Stop the bleed** | New research programs refuse to register findings without an `MC-*` id (policy + optional test floor) | Prevents the UNKNOWN set from growing while history is backfilled |
| **5. Backfill selectively** | Only re-seal programs when a comparison claim is needed — do **not** require rewriting all of F-019…F-043 before any new work | Matches L0 sufficiency (§10 of the contract): hygiene spend is bounded |

**What this does *not* claim:** sealing contracts does not reverse any null result, does not grant
fusion/production authority, and does not replace per-program pre-registration. It only makes
"these two experiments measured the same thing" a checkable statement.

### Reports that check the platform's own hygiene

`docs/research-readiness/` also holds a set of integrity reports that audit the research
*infrastructure* itself rather than any one finding: `determinism-report.md` (is the same experiment
reproducible), `metric-integrity-report.md`, `config-reachability-report.md`, `test-gap-report.md`,
`behavior-census-report.md`. These exist so that a null result can be trusted as a genuine null,
rather than an artifact of broken plumbing.

## Classification

| Concept | Status |
|---|---|
| `src/research/` subpackages | Research infrastructure, actively used (Programs 1–8) |
| ERP design docs (`docs/research-readiness/edge-research-platform-*`) | Design doctrine, partially implemented |
| Research Measurement Contract | **Frozen schema, unimplemented** — 0/27 probes built, all findings `Contract: UNKNOWN` |
| Research-readiness integrity reports | Production tooling (self-audits the research platform) |

## Authoritative sources

- `src/research/` — the 17 subpackages and shared modules listed above.
- `docs/research-readiness/README.md` and its ~60 sibling files (ERP design series, program and
  hypothesis pre-registrations, integrity reports).
- `docs/governance/MEASUREMENT_CONTRACT.md` — the frozen, unimplemented contract schema.
- `docs/topics/research-measurement-contract.md` — the always-synced topic doc for this specific gap.

## Unresolved questions

- **Sealed `MC-*` count** — re-verify against `docs/governance/research_family_registry.json` and
  `MEASUREMENT_CONTRACT.md` before claiming any seal; book snapshot remains `OPEN` / 0 sealed unless
  those artifacts say otherwise.
- This chapter did not individually verify every one of the 17 `src/research/` subpackages' current
  wiring status (research-only vs. touching any promotable artifact) — flagged in [A2](A2-unresolved-questions.md).

---
**Encyclopedia:** [E2 — Research Utilities Index](encyclopedia/E2-research-utilities.md) (269-file program/driver map)

**Previous:** [Chapter 19 — The Research Programs](19-research-programs.md) · **Next:** [Chapter 21 — The AI Automation Agent](21-ai-automation-agent.md)
**Related:** [Chapter 23 — Multi-LLM Coordination](23-multi-llm-coordination.md) (the ERP's multi-LLM research-collaboration design)
**Memory:** the session memory entry on the research family registry + measurement profiles (title:
"Research family registry + measurement profiles") records the Measurement Contract's
frozen-since-2026-07-10, zero-implementation status — consult it via the assistant's memory index,
not a repo-relative path (it lives outside this repository).
