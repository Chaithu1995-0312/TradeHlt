# Review — Program E-001 (Epistemic Integrity Sweep) + Remediation

## Context

A multi-LLM session built Program E-001 to formalize the invariant *"no layer may possess
greater certainty than the layer beneath it"* after the F-030 incident (a `regime_conditioning`
rollup printed `REGIME_HARMFUL` from all-`INSUFFICIENT` cells). The user asked for a review of
the delivered changes. This file records what was verified, the gaps found, and a remediation
plan. **The headline gap is an irony: the invariant *tests* themselves partly instantiate the
very failure classes (E-001A overclaim, E-001F decorative wiring) the program was built to
catch.** Per the program's own ritual: *"Caught me overclaiming; I owe you a correction."*

## What is genuinely solid (verified)

- **Charter** [`docs/governance/EPISTEMIC_INTEGRITY.md`](docs/governance/EPISTEMIC_INTEGRITY.md) — defines all six failure classes, the invariant, the mandatory phrase, the 6-question ritual. Well structured.
- **The real fix is real.** [`src/research/regime_conditioning.py:324`](src/research/regime_conditioning.py) — the `all_insufficient` guard (line 327-328) correctly precedes the `n_harmful > n_beneficial` emission (line 331). The F-030 bug is genuinely closed in code.
- **F-031 registered** ([`docs/current-findings.md:410`](docs/current-findings.md)) with evidence links that resolve; F-030 documents the corrected case.
- **Evidence-link test is substantive and binds** — its header/field regexes (`### F-NNN`, `- Confidence:`, `- Evidence:`) match the real findings format, so it actually parses 30 findings and checks each Certain/Likely finding cites a resolvable file. Not vacuous.
- **Tests run as claimed:** `15 passed, 1 skipped`.
- **CLAUDE.md §6.2** carries the pre-registration ritual + mandatory phrase (wired).

## Gaps found (the corrections owed)

1. **E-001A / E-001E tests are substring-grep, not behavioral** ([`tests/governance/test_epistemic_invariants.py:124`](tests/governance/test_epistemic_invariants.py), `:178`). They assert `"all_insufficient" in code` and string-position ordering — they never construct an all-`INSUFFICIENT` population and assert the verdict is `REGIME_INSUFFICIENT`. Consequences: a correctness-preserving rename/refactor *fails* (false positive); logically-broken code that keeps the strings *passes* (false negative). The charter/summary claim "the F-030 bug pattern is now a test failure" is **stronger than the grep supports** → itself an E-001A overclaim.

2. **E-001B test cannot fail** (`:375`) — it `pytest.skip`s when it finds concerning lines, otherwise passes. Same for `test_possible_findings_can_be_artifact_or_explanation` (`:243`). A test that never enforces is **decorative wiring (E-001F)** by the program's own definition, yet the charter §6 table lists "Test asserts."

3. **Charter status drift (DOC_DRIFT).** §9 still reads *"Pending sweep results from Phases 2–3"* and §10 marks phases 2a–4 as ⬜ PENDING, contradicting the COMPLETE claim. The charter contradicts itself.

4. **Evidence-link checks existence only, not support.** `_resolve_evidence` (`:84`) verifies `src/foo.py` exists but ignores the `:line` and never checks the file mentions the claim. Crude E-001C guard sold as "resolves to a real artifact."

5. **Second rollup layer unguarded** (minor). `scope_verdict` ([`regime_conditioning.py:355`](src/research/regime_conditioning.py)) can surface `REGIME_HARMFUL` at scope level from one harmful consumer among insufficients. Deliberate cross-consumer precedence, but it's an undocumented exception to the stated invariant and outside test coverage.

## Remediation plan

**Goal:** make Track B (the tests) actually enforce the invariant, and remove the program's own
overclaim/decorative-wiring instances. Track A (governance docs) needs only the drift fix.

### R1 — Make E-001A/E-001E behavioral (the core fix)
- Refactor the verdict-decision block ([`regime_conditioning.py:324-334`](src/research/regime_conditioning.py)) into a pure helper, e.g. `_consumer_verdict(cells_out, all_insufficient, redundant, n_harmful, n_beneficial, has_exploitable) -> str`. The surrounding loop calls it with the same args — **byte-identical behavior**, no logic change (verify by running `tests/test_regime_conditioning.py`).
- Replace the grep tests with behavioral ones: call `_consumer_verdict` with a synthetic all-`INSUFFICIENT` cell set and assert the result is `REGIME_INSUFFICIENT` (and that a single-harmful-among-insufficient set is *not* `REGIME_HARMFUL`). This binds the *behavior*, surviving refactors.
- Note `regime_conditioning.py` is a research harness — refactoring its verdict block is inside scope (the charter's "do not touch" list is spine / `qualification.py` / prod configs, not this file).

### R2 — Stop the decorative tests from masquerading as enforcement
Pick one per the user's call (see question): either (a) turn E-001B + the possible-findings test into real asserts (fail on violation), or (b) relabel them honestly as advisory and correct the charter §6 table so it no longer claims "Test asserts" for non-enforcing rows.

### R3 — Fix charter status drift
Update [`EPISTEMIC_INTEGRITY.md`](docs/governance/EPISTEMIC_INTEGRITY.md) §9 (record the sweep result) and §10 (mark 2a–4 ✅ DONE). Append the scope_verdict precedence (gap 5) as an explicit, documented exception to the invariant.

### R4 (optional) — Strengthen the evidence-link guard
Extend `_resolve_evidence` to also assert the cited file is non-empty and, where a `:line` is given, that the line exists. Full content-supports-claim verification is out of scope (needs semantics).

### R5 — Apply the program's own ritual
Register the meta-correction: a one-line note on F-031 (or a SESSION LOG entry) recording that the E-001 *test suite* itself was found to overclaim and was corrected to behavioral enforcement — the mandatory phrase applies, and a pre-registration correction is governance succeeding.

## Verification
- `python -m pytest tests/governance/test_epistemic_invariants.py tests/test_regime_conditioning.py tests/test_current_findings.py -q` → all green.
- Prove R1 inert: `tests/test_regime_conditioning.py` (15) still passes byte-identically after the helper extraction.
- Confirm the new behavioral test *fails* if the `all_insufficient` guard is removed (deliberately break it locally, see red, restore) — the true test of "the bug is now a test failure."
- Per CLAUDE.md §6: append the SESSION LOG entry.

## Hard boundaries (unchanged from the original program)
No edits to the CRT spine (`crt_engine_v2.py`), the M4 gate (`qualification.py`), or production
configs. R1's refactor is confined to the research harness's presentation block and is proven
inert by the existing determinism test.
