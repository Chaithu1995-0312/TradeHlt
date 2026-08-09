# Module Attribution Ledger — 100% Closure Coverage of `src/`

## Context

**Problem.** The Closure & Authority Index (`docs/governance/closure_authority_index.json`) covers
**11 surfaces** — 2 `CLOSED`, 2 `COMPLETE`, 1 `AUTHORITY_ACTIVE`, 5 `AUDITED`, 1 `OPEN` — over a
codebase of **461 `.py` files / 110,797 LOC across 40 packages**. It is the only governance ledger in
the repo that is hand-curated **with no declared denominator**, so the question "what fraction of
`src/` is governed by any surface?" is currently unanswerable, and a coverage percentage is
unexpressible.

**Two sibling ledgers already solved this.** `data/script_registry.jsonl` holds **371/371** runnable
paths with a GREEN_FLOOR test that fails CI on an unregistered path; the feature certification ledger
holds **39/39** canonical slots (F-062). Both use the same shape: mechanical enumeration → per-item
status → ratchet test. This plan applies that proven pattern to `src/` modules. No new governance
mechanism is invented.

**What "100%" means here (user ruling).** 100% = **every `src/` module is claimed by exactly one
surface with a declared status**. It does **not** mean every surface reaches `CLOSED` — statuses stay
honestly mixed (`CLOSED` / `AUDITED` / `ORPHANED` / `RESEARCH` / `OPEN`). Forcing `CLOSED` everywhere
would be a multi-year program, would freeze the repo against change, and would still be an overclaim:
**all 11 surfaces today carry `economically_validated: false`**, and the Measurement Contract layer is
`OPEN` with 0 sealed `MC-*` instances.

**Outcome.** A permanently-enforced claim that 100% of `src/` is attributed, plus — as a direct
byproduct of subtraction — explicit ownership of the live decision path from CRT's exit to the order,
which today **no surface claims**.

### The gap this exposes on day one

CRT's own `scope_boundary` states it *"Does NOT include EngineRunner admission, DecisionEngine
low_rr, live SM wiring."* Cross-checking every other surface's boundary confirms:
`engine_runner → fusion_engine → decision_engine → execution_planner → ultron_risk_gate` is owned by
**zero surfaces**. Per user ruling this becomes one new surface, `DECISION_SPINE`, boundary
`CRT TRADE_OPENED → ORDER`.

`src/engines/` also proves attribution must be **per-module, not per-package**: its 12 modules split
across 5 existing surfaces (`crt_engine`→CRT, the 3 gaussian engines→GAUSSIAN_LINEAGE,
`zone_gate_engine`/`zone_cluster_score`→ZONEGATE_LINEAGE, `rr_engine`→RR_LINEAGE,
`tradenet_meta_engine`→TRADENET_LINEAGE) plus 4 currently unowned (`scoring_engine`, `live_engine`,
`llm_engine`, `trap_validator_engine`).

---

## Design

### Ledger line schema

Mirrors `script_registry`'s `owner_kind`/`owner_ref` split, which already carries many-to-many truth
without breaking a denominator.

```json
{
  "module_path": "src/core/engine_runner.py",
  "owner_surface": "DECISION_SPINE",
  "participates_in": ["CRT", "GAUSSIAN_LINEAGE", "ZONEGATE_LINEAGE", "RR_LINEAGE"],
  "regime": "DECISION",
  "grade": "G1",
  "reachability": "LIVE_DECISION",
  "economically_validated": false,
  "evidence": [{"path": "...", "symbol": "...", "type": "code"}],
  "last_validated": "2026-08-07T00:00:00Z"
}
```

- `owner_surface` — **exactly one, mandatory**. This is what makes the percentage well-defined.
- `participates_in` — 0..n, informational only. Never confers ownership or closure.
- `regime` ∈ `DECISION | RESEARCH | PLATFORM | SUBSTRATE | MODEL_LINEAGE | TERMINAL`.
- `grade` ∈ `G0 ATTRIBUTED | G1 DECLARED | G2 AUDITED | G3 CLOSED` (cost ladder; only `DECISION`
  modules are expected to pursue G2/G3).
- `economically_validated` — **per-module (user ruling)**, almost universally `false`. Prevents a
  green attribution percentage from being misread as soundness.

### Regime partition (hypothesis — the census tests it, it is not a measurement)

| Regime | Packages | ~Modules | Treatment |
|---|---|---|---|
| RESEARCH | `research`, `llm_research`, `interpreters`, `msip`, `retrieval`, `expansion`, `regime`, `search` | ~180 | **one** surface under Measurement Contract (user ruling) |
| PLATFORM | `governance`, `control_plane`, `agent`, `utils`, `multi_llm`, `journal`, `events`, `monitoring`, `uat`, `validation_access`, `ui` | ~87 | one-or-few surfaces, G1 |
| TERMINAL | `replay`, `cognitive`, `portfolio`, `scanner`, `feedback`, `analytics`, `strategies`, `data_ingestion` | ~50 | `SIDECAR`/`ORPHANED` per F-012/F-013, G1 |
| SUBSTRATE | `features`, `config_layer` | ~56 | largely covered by CANONICAL_FEATURE_CODE_SURFACE |
| MODEL_LINEAGE | `bitnet`, `training`, model engines | ~35 | already AUDITED |
| **DECISION** | `core`, `engines`, `runtime`, `execution`, `inout`, `live` | **~55** | the only set needing G2/G3 |

If this holds, **~12% of `src/` needs expensive treatment**. Confirming or refuting this ratio is the
first job of Phase 1.

### Invariants to preserve

- `CLOSURE IS BOUNDARY-SCOPED AND NON-TRANSITIVE` — `participates_in` must never be read as
  ownership; `downstream_not_implied_closed` stays mandatory on every new surface row.
- The ratchet enforces **attribution only**. `grade`/status may only advance when a named
  `authoritative_artifact` exists. No bulk status promotion, ever.

---

## Files

**New — mirror the SITS chain exactly:**

| New file | Mirrors |
|---|---|
| `scripts/analysis/module_census.py` | `scripts/analysis/script_census.py` |
| `docs/governance/module_attribution_stubs.jsonl` (PRIMARY, tracked) | `docs/governance/script_registry_stubs.jsonl` |
| `scripts/governance/seed_module_attribution.py` (stubs + overlays → JSONL) | `scripts/governance/seed_script_registry.py` |
| `tests/test_module_attribution.py` (the ratchet) | `tests/test_script_registry.py` |

Generated output: `data/module_attribution.jsonl` (GENERATED, gitignored — never hand-edit).

**Modified:**
- `docs/governance/closure_authority_index.json` — add `DECISION_SPINE`, `RESEARCH_REGIME`,
  `PLATFORM`, and terminal surfaces, each with `scope_boundary`, `status`, `authoritative_artifact`,
  `reopen_conditions`, `downstream_not_implied_closed`.
- `CLAUDE.md` §6.2 Closure & Authority Index table — add the new rows (thin, pointer only).
- `docs/reference/schemas.md` — new §9.9 documenting the JSONL line schema (per §3.2 mandate; follows
  the §9.8 `script_registry` entry).
- SITS registration for the two new scripts: `script_census.py --write-stubs` →
  `seed_script_registry.py` → `scripts/analysis/generate_script_matrix.py`, same turn they are added.

---

## Phasing — the 100% claim lands at Phase 4, not at the end

1. **Census + schema.** Build `module_census.py`, emit all 461 modules, `UNATTRIBUTED` permitted,
   ratchet in **warn** mode. Report the real regime histogram against the hypothesis table above.
2. **Bulk regime assignment.** RESEARCH / PLATFORM / TERMINAL via overlays — clears the large
   majority in one pass. Cite F-012/F-013 as evidence for terminal rows.
3. **Declare the decision surfaces at G1.** Register `DECISION_SPINE` in the closure index with its
   `CRT TRADE_OPENED → ORDER` boundary; attribute the ~55 modules; resolve the 4 orphan engines.
4. **Flip the ratchet to fail.** "100% attributed" becomes true and permanently enforced.
5. **Onward (no end date).** G2/G3 earned per surface, one at a time, never in bulk. The 100% claim
   remains true throughout without these completing.

---

## Verification

- `python scripts/analysis/module_census.py --dry-run` → module count reconciles with
  `find src -name "*.py" | wc -l` (461) and with the 347 importable modules in
  `docs/architecture/code-map.generated.md`.
- `python scripts/governance/seed_module_attribution.py` → regenerates `data/module_attribution.jsonl`
  deterministically (run twice, byte-identical).
- `pytest tests/test_module_attribution.py` — asserts: every `src/**/*.py` appears exactly once;
  every `owner_surface` resolves to a row in `closure_authority_index.json`; no `UNATTRIBUTED`
  survives after Phase 4.
- `pytest tests/test_closure_authority_index.py tests/test_script_registry.py tests/test_script_matrix_sync.py`
  — existing floors stay green after the index and SITS additions.
- `python scripts/governance/construction_protocol.py check` — the one-command governance floor.
- **Zero runtime impact expected**: this program adds no `src/` behavior. Confirm with the standard
  XAUUSD freeze-pin vector SHA / `SCHEMA_HASH` check — must be unchanged.
- Findings Mandate: register the DECISION_SPINE ownership gap as a finding in
  `docs/current-findings.md` the same turn it is confirmed (ARCH, evidence = the boundary-subtraction
  over `closure_authority_index.json`).
