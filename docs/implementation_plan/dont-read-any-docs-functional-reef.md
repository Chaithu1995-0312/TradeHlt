# Semantic + Screenshot Layer Review — remediation

## Context

You asked for a review of the semantic and screenshot layers. The review is done (three
Explore/audit passes plus my own source verification). It found **2 defects I introduced last
turn**, **2 Semantic-OS defects**, **2 stale ontology nodes**, and **13 `tools/tv_forensic`
defects**. You authorized fixing everything actionable, and graduating the stale ontology nodes.

**The correction I owe first.** Last turn I wrote, in
[htf_parent_telemetry_extract.py:141](scripts/research/htf_parent_telemetry_extract.py:141), that
I skipped re-running `diff_table` because *"the sidecars' own capture-time computation already
used the correct per-shot interval."* That is false. [capture_tv.py:341](tools/tv_forensic/capture_tv.py:341)
guards the reconciliation with `if str(shot.interval) == "15":` and skips it entirely otherwise —
there was never an H4 computation to be right. I observed the missing key, noted to check why, then
invented the explanation instead of opening the file. The claim propagated into the generated
`ohlc_clock_reconciliation.json`, where it sits eleven lines above its own disproof
(`engine_vs_tv_summary: null` at both H4 positions). Separately I wrote "0/119 bars across shots
**07/08/09**"; 07=82, 08=37, 09=**none**. Neither claim reached `docs/current-findings.md`.

**The structural defect underneath my mistake** is the one worth fixing: a skipped reconciliation
is recorded as an *absent key*, indistinguishable from an unexamined one. Three consumers each had
to guess; mine guessed toward more confidence. That is why the fix is a written-down negative
result, not a better comment.

**What that does to F-075.** Its recorded "0 divergent bars" for preset `jul15-20` credits shots
`07/08/09`. Shot 09 is the **H4 parent** capture and has no reconciliation at all — its "0
divergent" is vacuous. F-075's visual/bar-alignment PASS covers M15 only, while the H4 image
carrying the *parent* half of the parent-vs-child argument has no check that its marks sit on the
right candles. D-2 sharpens this: `OffsetResult.decisive` ranks offsets on means over *unequal*
anchor subsets, ignores its own `anchors_matched`, and returns `True` unconditionally on a single
scored candidate — a hole a smoke test currently enshrines. On M15 the diff table is the backstop.
On H4 there is none.

## Work

### A. My corrections (§6.2 E-001 — fix the source, mark `CORRECTED`, never silent-delete)

- `scripts/research/htf_parent_telemetry_extract.py` — module docstring + the `_ohlc_clock_reconciliation()`
  note string: replace the false sentence with the true mechanism (`capture_tv.py:341` skips
  non-M15 entirely; there is no stored H4 computation), marked `CORRECTED: <old> -> <new>`.
- `reports/monthly_tv_vs_active_production_semantic_comparison.md` row 2 + `.json` — "0/119 across
  07/08/09" → 0/119 across **07/08**, with shot 09 named as unreconciled.
- Regenerate `results/monthly_tv_semantic_report/ohlc_clock_reconciliation.json` from the fixed script.

### B. `tools/tv_forensic` fixes

| ID | Fix |
|---|---|
| **D-1** | `capture_tv.py` `else` branch: write an explicit `"engine_vs_tv": {"status":"NOT_APPLICABLE","reason":"diff_table is M15-only; shot interval <N>"}` instead of omitting the key. Update the three consumers to read it: `annotate.py` caption, and my extractor's rollup to report `unreconciled_shots` explicitly rather than summing silent zeros. |
| **D-2** | `engine_data.py` `OffsetResult.decisive`: require the winner to have matched **all** usable anchors (or a declared floor), and stop returning `True` when only one candidate scored. Fix the `:+d`-on-`None` `TypeError` at `capture_tv.py:132` and `measure_corpus_clock.py:159` so the intended refusal message surfaces instead of a crash. |
| **D-4** | New validator: cross-check every `shot_plan.json` `engine_events` entry against the engine CSV — `time` must exist as a bar, and `level` must match that bar's O/H/L/C within tolerance. Report per-anchor drops in `calibrate_clock` instead of passing on one surviving anchor. |
| **D-6** | `annotate.py` `stagger()`/`rows` keyed on `(event, broker)` not `event` — currently the Jul-20 `RETEST` overwrites the Jul-15 one on shot 09, hiding a mark the sidecar still lists. |
| **D-7** | Caption table: include the date when the frame spans more than one day (`[11:]` currently truncates it away on shots spanning up to a week). |
| **D-8** | A non-zero `divergent` count must mark the payload (and offer a non-zero exit), not just print. |
| **D-9** | Make the frame-fidelity assertion two-sided so an under-zoomed (too-wide) frame fails too. |
| **D-11** | Five-line defined-vs-captured completeness check; fill the `shots_defined_in_shot_plan: None` hole in my extractor. |
| **D-12** | Tests for the logic being changed: `diff_table`, `summarize_diff`, `stagger`, `decisive`'s negative branches, plan-vs-disk completeness. Replace the smoke test that asserts `decisive` on a single anchor — it blesses the wrong contract. |
| **D-13** | Guard `annotate.py` `Frame.y_of`'s zero denominator, matching `tv_bridge.Snapshot.y_of`. |

**Artifact regeneration:** D-6/D-7 require re-annotating from existing sidecars (Pillow only — **no
Playwright, no network, no new capture**). Shot 09's annotated PNG/JSON are cited by F-077, and
`tools/tv_forensic/` is untracked (D-3) so there is no diff history — preserve the prior files
as `*_PRE_D6.*` rather than overwriting (§6.2 rule 4).

**Deliberately excluded — D-3 (untracked in git).** Tracking ~2 MB of PNGs plus the layer is a
repo-policy decision, not a code fix, and you told me earlier this session to leave git alone.
Flagged in the review, not actioned.

### C. Semantic OS fixes

- **S-1** `src/governance/semantic_grounding.py:668-706` — `ground_implementation` currently
  proceeds when the file is absent from disk but present in the stale generated projection, takes
  symbol names from that projection, and stamps `evidence_class=PROVEN` with `on_disk: False`.
  Contradicts its own docstring ("must exist on disk", "Fail closed") and CT-008's "Unknown tokens
  fail closed". Fix: fail closed to `UNKNOWN` when the path is not on disk. Same hole in
  `_ground_object_path` and the NOUN→IMPLEMENTATION fallback. Add the missing test for exactly
  `on_disk=False + projection-hit` — no current test covers it.
- **S-2** `ground_evidence` — a SUPERSEDED/retired finding grounds as `PROVEN` with no caveat.
  Surface terminality rather than asserting `PROVEN` blind.

### D. Ontology graduation (§6.6, refine **in place**, no duplicates)

- **UNK-001** — `knowledge_status: UNKNOWN` → `CHARACTERIZED`, `status: open` → resolved, citing
  F-069's source-verified entry-stage mechanism (`_resolve_from_features` skips
  `_expansion_entry_allowed()` under `continuous_disp_to_expansion: false`). This satisfies UNK-001's
  own falsification condition #1 verbatim, and its own `traceability` field instructs this exact
  graduation. Preserve the original observation text.
- **SEM-001** — its evidence quotes `engine EXPANSION=4604 resolver EXPANSION=1125` from
  `reports/crt_state_confusion_matrix.json`; that file today holds `4625`/`4625` with
  `htf_mode: "engine"` (oracle-assist) and `agreement_rate 0.9996` — the contaminated run F-069
  explicitly disowns. Repoint to F-069's honest config-only measurement (88.16%, EXPANSION recall
  498/4,625), marked `CORRECTED`, original retained.

### E. Governance

- Note on **F-075** narrowing the visual/bar-alignment PASS to M15 shots (shot 09 unreconciled) —
  a scope correction, `Reversal:`-qualified; the M15 evidence itself stands.
- Note on **F-077** (uses shot 09's annotated PNG, affected by D-6).
- One **new F-id** for the review's material architectural conclusion: the screenshot layer records
  skipped reconciliation as absent data, and the Semantic-OS grounding surface could return
  `GROUNDED/PROVEN` for a non-existent file. Both are governance-mechanism facts, not economic
  claims — research/governance authority only, no G001.
- Re-run SITS (`script_census` → `seed_script_registry` → `generate_script_matrix`) if script
  purposes change; append the §6 SESSION LOG.

## Verification

1. `pytest tests/test_tv_forensic_smoke.py tests/test_semantic_grounding.py tests/test_semantic_identity.py tests/test_semantic_registry.py -q` — including the new negative tests; the replaced single-anchor `decisive` test must now assert refusal.
2. Re-run both extraction scripts; confirm the regenerated `ohlc_clock_reconciliation.json` carries no false note and reports `unreconciled_shots: [03_h4_jul27_31, 09_h4_jul15_20]` explicitly instead of silent zeros.
3. Re-annotate shot 09; confirm **both** the Jul-15 `RETEST` and `OFF_SESSION` marks render (D-6), that caption rows carry dates (D-7), and that `*_PRE_D6.*` backups exist.
4. `validate_semantic_registry()` returns `[]` after the ontology edits; `pytest tests/test_current_findings.py tests/test_findings_export.py -q` after Notes; regenerate `data/findings.jsonl`.
5. Prove S-1 fails closed: ground a path present in the projection but absent from disk → must return `UNKNOWN`, not `GROUNDED`.
6. Posture: `configs/production/ACTIVE_VERSION` still `v2_htfcrt_2026_08`; no file under `configs/` modified; **no new capture** — `tools/tv_forensic/shots/` gains only the `_PRE_D6` backups and regenerated annotations, no new base shot.

## Out of scope

- D-3 (git-tracking the layer) — repo-policy decision, see above.
- D-5 (SUPERSEDED events drawn) — audited as intentional, correctly scoped and labelled.
- Re-capturing any TradingView shot, or widening coverage beyond the existing 7.
- Any production config, `ACTIVE_VERSION`, or spine change. The Semantic OS layer is advisory
  (zero `src/config_layer|runtime|core` imports); none of this touches trading behavior.
