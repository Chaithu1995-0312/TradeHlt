# PHASE 1 — OHLCV Truth Closure — PASS B (Blocked-State Adjudication) execution plan

> **Rev 3.** PASS A is complete and frozen (evidence: 9 governance artifacts + census generator +
> manifest + validator test; see layer-audit-manifest.json). The user's adjudication authorizes
> **PASS B as BLOCKED-STATE adjudication**: the expected outcome is
> `OHLCV_CLOSURE_STATUS = BLOCKED:<minimal blocker set>`, derived honestly — not forced either way.
> User adjudication of BC-1…6 (all BLOCKER variants) is a **recommendation to verify, not a
> conclusion to copy** (§13.8: advice is non-binding; evidence decides). Dissent with evidence is
> allowed and must be explicit.

## Context

PASS A proved row-level integrity is clean (0/224 violations) but corpus **identity + semantics +
provenance** are not closed: 9 logical corpora resolve to different bytes under one name; canonical
root crypto descends from the ungated yfinance family; `volume` = 5 quantities under one column;
open-time labeling + yfinance tz + forming-bar protection unproven; canonical XAUUSD ≡ quarantined
bytes. PASS B must adjudicate every BC/CX against the frozen artifacts, derive a fail-closed
machine-readable output contract **from PROVEN guarantees only**, and emit the closure verdict +
remediation prerequisites. **No remediation, no doc edits to PASS-A artifacts, no economic claims,
no Phase 2.**

## Governing rules (from the user's adjudication — mandatory)

1. **Independent verification first**: every BC-1…6 and CX-001…010 re-verified against the frozen
   PASS-A artifacts (+ targeted read-only probes) BEFORE classification. Concur/dissent recorded
   per item with evidence.
2. **C1 verdict grammar**: only `CLOSED` or `BLOCKED:<reason>`; every unresolved item classified
   `BLOCKER` or `PROVEN_NON_BLOCKER` (positive evidence required for the latter); UNKNOWN affecting
   active-path semantics/identity/provenance/reproducibility = BLOCKER.
3. **Contract = current enforcement, not aspiration** (the stated Most Likely Failure Mode): every
   guarantee binds `authoritative_producer` + `runtime_enforcer` + `evidence` (executable/static/
   reproducible refs) + `contradiction_status`, and carries
   `guarantee_status ∈ {PROVEN, UNPROVEN, CONTRADICTED}`. A guarantee with no runtime enforcer is
   at best UNPROVEN even if the data is currently clean. Any handoff-required guarantee UNPROVEN or
   CONTRADICTED ⇒ BLOCKED.
4. **Corpus-family scoped admissibility**: BC-2 adjudicated per family (active acquisition vs
   immutable historical), BC-6 yfinance-scoped; the contract carries a per-family admissibility
   table, not a global verdict.
5. **BC-3 discipline**: do NOT resolve by declaring Binance authoritative — record that current
   canonical-crypto authority is unproven. Adjudication ≠ remediation.
6. **Matrix metrics split**: mutation registration ≠ detection coverage. Closure report + contract
   carry explicit `failure_classes_registered=29 / canonical_seeds_defined=29 /
   detectors_implemented=21 / clean_path_probes_green=NOT_MEASURED /
   mutants_killed=NOT_MEASURED / mutation_score=NOT_MEASURED`. Never allow "29/29 seeds" to read
   as E-MT-01 COMPLETE. (PASS-A matrix JSON stays frozen; metrics live in the new PASS-B
   artifacts.)

## Independent-verification probes (read-only; step 1 of execution)

- **BC-5 lineage probe (the one item that may flip):**
  (a) `reports/dataset_integrity/XAUUSD_M15.json` (+ any XAUUSD entries) — recorded `decision`,
  `hard_failures`, `file_hash` vs census sha for `data/XAUUSD_M15.csv` and
  `data/mt5/_rejected/XAUUSD_M15.csv`;
  (b) `HANDOFF.md` `standing_rules.canonical_corpus` sha `4d73f5ce…` vs census hash — if it matches
  the current bytes, HANDOFF *knowingly* pinned these bytes as canonical (promotion-by-decision
  evidence);
  (c) session-log archives (`docs/analysis/session-log-archive/`) + `assistant_project.md` for the
  H-SECONDLOW XAUUSD quarantine/promotion narrative;
  (d) file mtimes (weak, corroborating only).
  Outcome: BLOCKER (lineage unproven) or PROVEN_NON_BLOCKER (documented known-gap acceptance).
- **CX-006 positive-evidence probe**: grep configs + `.env`-adjacent config surfaces (NOT `.env`
  itself) for `db_url`/timescale wiring; confirm `correlation_engine.py:77` activation condition is
  unreachable on this branch (who calls it, with what config). Target: PROVEN_NON_BLOCKER.
- **CX-005 positive-evidence probe**: re-confirm zero readers of `_rejected/`/`_archive_5wk/`
  (grep already run in PASS A; re-cite) + confirm gate verdict is config-contextual
  (strict_fetch override) → PROVEN_NON_BLOCKER with evidence.
- **BC-1/3/4 spot re-verification**: recompute 2–3 census hashes independently (`sha256sum`) to
  confirm the manifest is faithful; re-cite fetch-script lines.
- **BC-2/6**: verify the NARRATIVE-ONLY tags are still the strongest available repo evidence (no
  overlooked executable proof, e.g. parity tests between mt5 and binance overlapping instruments —
  there are none: families don't overlap instruments except via root copies).

## Deliverables (all NEW files; PASS-A artifacts untouched)

| # | Artifact | Content |
|---|---|---|
| 1 | `docs/governance/ohlcv-output-contract-2026-07-10.json` | Machine-readable contract: (a) `guarantees[]` — each with id, statement, scope (global or family), authoritative_producer, runtime_enforcer (or `none`), evidence[{type: executable/static/reproducible/narrative, ref}], contradiction_refs, `guarantee_status`; (b) `corpus_families{}` — per family: identity binding requirements (`logical_corpus_id + physical_path + sha256 + authority_class + source_family + transformation_chain`), volume_semantic, timestamp_semantic (+status), admissibility (`ADMISSIBLE_WITH_BINDING / NOT_ADMISSIBLE_AS_AUTHORITATIVE / EXCLUDED`); (c) `handoff_required_guarantees[]` (the set whose non-PROVEN status blocks closure); (d) `forbidden_substitutions[]` (from Prompt-2 §7 + T-003/T-006); (e) `trust_status` with the 6-metric matrix split; (f) verdict echo. Fail-closed: consumers must reject a corpus lacking a binding entry |
| 2 | `docs/governance/ohlcv-closure-report-2026-07-10.md` | CRT closure grammar: header (pinned commit, twins); **BC/CX adjudication table** — per item: user classification, independent verification result, final `BLOCKER / PROVEN_NON_BLOCKER`, concur/dissent + evidence; 12-criteria closure-gate walk (each PASS/FAIL with refs); matrix metrics split; guarantee rollup (n PROVEN / UNPROVEN / CONTRADICTED); **remediation prerequisites** — per final BLOCKER, the minimal proof/mechanism that would flip it (design-level only, no changes); return block ending with the literal verdict token |
| 3 | `docs/governance/layer-audit-manifest.json` (UPDATE — the one intentionally-stable mutable manifest) | phase_status → `PASS_B_ADJUDICATED`; `closure_verdict = "BLOCKED:<minimal blocker set>"` (exact composition decided by the verification, e.g. `BLOCKED:BC-1,BC-2[acquisition-families],BC-3,BC-4,BC-5?,BC-6[yfinance]`); closure_report + output_contract paths; refreshed artifact hash list incl. the two new artifacts |
| 4 | `tests/test_ohlcv_output_contract.py` | Validator: schema shape; **no guarantee may be PROVEN with only narrative evidence**; no guarantee PROVEN with `runtime_enforcer: none` unless evidence type is executable; every handoff-required guarantee non-PROVEN ⇒ manifest verdict MUST be BLOCKED (fail-closed consistency); matrix metrics keys present and mutation_score ≠ implied-complete |
| 5 | SESSION LOG entry in `assistant_project.md` (+ finding decision: file a new F-05x GOV finding for the identity-unbound conclusion in `docs/current-findings.md`? — **only with user approval per §6.2 gate**; the plan DEFERS the finding registration and lists it as a follow-up question in the closure report) |

## Execution order

1. Run the independent-verification probes (read-only) → record concur/dissent per BC/CX.
2. Derive the guarantee inventory from the frozen temporal/transformation/census artifacts →
   assign guarantee_status (expect: STATIC/EXECUTABLE-backed rows PROVEN; NARRATIVE-ONLY rows
   UNPROVEN; CX-003/CX-008-touched rows CONTRADICTED or UNPROVEN as evidence dictates).
3. Build the per-family admissibility table (mt5 / binance / yfinance / data_root FX / data_root
   crypto / resampled / archive / quarantine / perp-excluded).
4. Write the output contract JSON (#1), then the closure report (#2) with the 12-criteria walk and
   the final minimal blocker set.
5. Update the layer manifest (#3), write the contract validator test (#4).
6. Verify: `venv/Scripts/python.exe -m pytest tests/test_layer_audit_manifest.py
   tests/test_ohlcv_output_contract.py -q` green; census `--check` still PASS (PASS-A artifacts
   unmodified); `git status` = new files + manifest + session log only.
7. SESSION LOG append; final report with the verdict token; **STOP** — remediation design is a
   separate follow-up authorization.

## Hard constraints

- No modification of PASS-A artifacts, production code, configs, findings, or existing docs
  (the layer manifest is the sole designed-mutable file; its hash-guard test is regenerated with it).
- No remediation of any kind (no re-fetching, no re-pointing canonical paths, no declaring Binance
  authoritative, no volume metadata implementation).
- Verdict grammar strict: final line is exactly `OHLCV_CLOSURE_STATUS = BLOCKED:<reason>` (or
  `CLOSED` in the unlikely event verification dissolves every blocker — do not force either way).
- `.env` never read. No economic claims. Do not begin Phase 2.

## Verification

1. Both validator tests green; existing `tests/data_ingestion/` still green.
2. `ohlcv_census.py --check` = PASS (proves PASS-A evidence untouched).
3. `grep "OHLCV_CLOSURE_STATUS" docs/governance/ohlcv-closure-report-2026-07-10.md` returns exactly
   one verdict line matching the C1 grammar; the manifest's `closure_verdict` matches it.
4. Contract JSON: every PROVEN guarantee has ≥1 non-narrative evidence ref (enforced by test #4).
5. Final response: adjudication table (concur/dissent per BC/CX), guarantee rollup, minimal blocker
   set, remediation prerequisites summary, SESSION LOG — and stops before any remediation.
