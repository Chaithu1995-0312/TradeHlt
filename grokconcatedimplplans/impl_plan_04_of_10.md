# Concatenated implementation plans — part 4 of 10

Source directory: `docs/implementation_plan/`
Files in this part: 16

## Contents

1. `do-we-have-xauusd-valiant-gray.md` (8893 bytes)
2. `do-you-have-access-glimmering-creek.md` (4442 bytes)
3. `dont-read-any-docs-functional-reef.md` (9930 bytes)
4. `dont-read-current-code-lively-lake.md` (6178 bytes)
5. `dont-update-any-docs-eager-blossom.md` (36377 bytes)
6. `edge-discovery-program-memoized-mountain.md` (17012 bytes)
7. `erp-ic001-closure-and-ic-roadmap.md` (14763 bytes)
8. `erp-ic001-implementation-details.md` (18411 bytes)
9. `existing-data-sources-enumerated-feather.md` (8504 bytes)
10. `extract-xauusd-one-month-vast-newell.md` (15663 bytes)
11. `f-041-recursive-catmull.md` (10804 bytes)
12. `feature-layer-tracking-2026-07-19.md` (75315 bytes)
13. `for-only-this-session-dapper-possum.md` (3731 bytes)
14. `from-claude-md-pick-curried-toast.md` (15980 bytes)
15. `from-mt5-terminal-we-drifting-hollerith.md` (6032 bytes)
16. `FULL_BUILD_SPECIFICATION.md` (105041 bytes)


================================================================================
SOURCE_FILE: docs/implementation_plan/do-we-have-xauusd-valiant-gray.md
SOURCE_BYTES: 8893
PART: 4/10 FILE 1/16
================================================================================

# Register F-089 — the parent-CRT bias gate is decision-neutral on XAUUSD

## Context

**What prompted this.** The question "are those state transitions prod active version or independent?"
Verifying the answer (they ARE `ACTIVE_VERSION = v2_htfcrt_2026_08`, loaded through
`load_prod_config_from_registry` with `verify_hash=True`) surfaced something unplanned: the
5,269-event CRT state sequence is **byte-identical** to the older `v2_multi_2026_04` run.

**Why that is not trivial.** The two registry configs have **identical `params`** (same
`config_hash` `7de09f62…` — `parent_crt` is a non-`params` section, hash-neutral per §6.5) and no
differing top-level keys. The single behavioural difference is `parent_crt.enabled`: **true** on
the active config, **false** on the old one. So this is a clean natural A/B of the F-075 gate.

**Measured result (already obtained, read-only):**

| Check | Result |
|---|---|
| State sequence (STATE_TRANSITION + RESET, n=5,269) | **byte-identical**, sha `4f09654ac8f50700` both |
| Full event profile | identical across all 10 event kinds |
| Trades | 3 opened / 1 TP1 / 1 TP2 / 2 stopped — identical |
| `FILTER_REJECTED` timestamps | **same set**, 19 vs 19, none only-in-one |
| Rejection **reasons** that differ | **exactly 4** |

```
2025-01-31 21:00  off_session -> Against parent-timeframe bias (LONG)
2025-07-10 20:15  off_session -> Against parent-timeframe bias (SHORT)
2026-02-19 11:30  off_session -> Against parent-timeframe bias (LONG)
2026-03-18 11:30  off_session -> Against parent-timeframe bias (SHORT)
```

**The claim:** arming `parent_crt` fires 4 times over the full 2-year corpus and every one of those
4 candidates was **already** being rejected by the off-session filter. It changes the *reason*,
never the *outcome*. This refines F-075 — which records the gate as "reachable on the armed
config" — with the measured next step: reachable, fires, and **non-pivotal**. Same shape as F-036
(zone tunable-but-inert) and F-070 (fusion vetoes 0/30). *Reachable ≠ pivotal.*

**User decisions:** record it properly as a finding with a reproducible probe; **XAUUSD only** (per
the standing instruction never to swap in other instruments to force events).

**Explicitly NOT claimed:** that `parent_crt` should be disabled, that it is inert on any other
instrument or corpus, or anything economic. n=4 gate firings supports no economic claim whatever.

---

## Work

### 1. `scripts/research/parent_crt_pivotality_probe.py` — the reproducible probe

Must be **self-contained from a clean clone** — it may not depend on the gitignored
`results/research/_spine_entries/…` artifact I compared by hand.

Design: run the spine twice through the **governed registry loader**, once per config version, and
diff. Reuse — do not reimplement — `charts.crt_overlay.run_spine_for_states(instrument, csv_path,
version=...)`, which already takes an explicit `version`, rebinds `PROD_VERSION` in both modules,
and restores in `finally`. Cache dirs are already version-scoped, so the two runs cannot collide.

Three **blocking validity gates**, in this order, before any verdict is emitted:

1. **Configs differ ONLY in `parent_crt.enabled`** — assert identical `params`, identical
   `config_hash`, no differing top-level keys. Without this the A/B is confounded, and a future
   config edit would silently turn this probe into a comparison of two unrelated things.
2. **Non-vacuity** — assert the gate actually fired (≥1 `FILTER_REJECTED` carrying a parent-bias
   reason) on the gate-ON arm. A gate that never fires is *untested*, not *neutral* (the F-070
   guard).
3. **Corpus identity** — assert the Phase-1 sha256, so a drifted corpus fails closed rather than
   producing a comparison of different data.

Then compare: state-sequence sha, per-event-kind counts, trade counts, and the
`FILTER_REJECTED` timestamp→reason map. Emit `PIVOTAL` / `DECISION_NEUTRAL` / `VACUOUS` /
`INVALID_AB` plus counts to stdout and a JSON artifact. `--json <path>` optional; read-only w.r.t.
all governed state (no config write, `ACTIVE_VERSION` untouched).

### 2. `tests/test_parent_crt_pivotality.py` — floor

Unit-level, no spine run (the probe itself is minutes-long):
- the config-equivalence gate rejects a confounded pair (differing `params`);
- the non-vacuity gate returns `VACUOUS` when no parent-bias rejection is present;
- reason-only differences classify `DECISION_NEUTRAL`;
- an outcome difference (extra/missing rejection timestamp, or differing trade counts) classifies
  `PIVOTAL` — i.e. the probe *can* fail, per the E-001 "a test that can't fail isn't enforcement"
  lesson;
- corpus-sha mismatch fails closed.

### 3. `docs/current-findings.md` — add F-089

Next free id (F-088 is the highest). Fields per the house block format:

```
Type:          ARCHITECTURE
Family:        RF-HTF          (same family as F-075)
Contract:      UNKNOWN
Status:        VALIDATED
Confidence:    Certain
Validated:     2026-08-22
Revalidate-by: 2027-02-22
Supersedes:    —
Reversal:      — refines F-075, reverses nothing
```

**Confidence note (judgment call, flagged deliberately):** `Certain`, because the claim is a
deterministic, reproducible byte-comparison — not an inference. The neighbours F-036 and F-070 sit
at `Likely`, but each embeds an inferred *driver*; this one will not. Any generalisation beyond
"this corpus, these two configs" is excluded in the finding text rather than absorbed into a
softer grade.

**Evidence must cite TRACKED paths only** — `tests/test_current_findings.py:280-313` reads
`git ls-files` and the fix is *"`git add`-ing the path, not widening the ratchet"*. `results/` and
`data/` are gitignored, so cite: the probe script, `src/charts/crt_overlay.py`,
`configs/production/v2_htfcrt_2026_08.json`, `configs/production/v2_multi_2026_04.json`,
`src/config_layer/parent_crt.py`, and the new test. **The probe script and `src/charts/` must be
`git add`ed** (targeted paths only — never `git add -A`, per the concurrent-sessions constraint)
or the findings floor fails. Staging is sufficient; `git ls-files` reads the index.

### 4. Sync the surfaces that are mechanically enforced

- **`CLAUDE.md` §6.2 Repository Truths Index** — add the F-089 row. `test_current_findings.py:244`
  enforces the index and the living doc agree on every non-terminal id, both directions.
- **`data/findings.jsonl`** — regenerate via `python scripts/governance/export_findings.py`
  (GENERATED artifact; never hand-edited).
- **SITS** — register the probe the same turn: `script_census.py --write-stubs` → add an OVERLAY in
  `scripts/governance/seed_script_registry.py` → `seed_script_registry.py` →
  `scripts/analysis/generate_script_matrix.py` (note: it lives under `scripts/analysis/`, not
  `scripts/governance/`). Do **not** hand-edit the stubs JSONL.
- **`docs/current-findings.md` F-075** — append a pointer line noting F-089 measured its gate as
  non-pivotal on XAUUSD. Append-only; do not rewrite or downgrade F-075 (§6.2 rule 4).
- **`reports/xauusd_visual_pass.md`** — add the measurement to §4, since that report's funnel
  numbers came from this exact run.
- **`assistant_project.md`** — SESSION LOG entry (§6).

---

## Verification

1. `venv/Scripts/python.exe -m pytest tests/test_parent_crt_pivotality.py -q` — floor green.
2. `venv/Scripts/python.exe -m pytest tests/test_current_findings.py -q` — findings contract,
   index sync, and the tracked-evidence gate all green.
3. `venv/Scripts/python.exe scripts/research/parent_crt_pivotality_probe.py --instrument XAUUSD`
   → expect `DECISION_NEUTRAL`, `reasons_changed=4`, `outcomes_changed=0`, state-sequence shas
   equal. First run is slow (two full spine passes); subsequent runs hit the version-scoped cache.
4. `venv/Scripts/python.exe -m pytest tests/test_script_registry.py tests/test_script_matrix_sync.py -q`
   — SITS floors stay green (they are green today, 52/52).
5. `git ls-files scripts/research/parent_crt_pivotality_probe.py` returns the path — the evidence
   gate's actual condition.

## Known-red, not mine, not touched

The construction floor is RED with 7 failures that predate this work and are unrelated to it:
`test_geometry_census` ×2 / `test_gate2b_closure` ×2 / `test_feature_math_lint` — all driven by 88
unregistered derivations in `msip_1_verification_package/` plus removed ones in
`feature_pipeline.py`/`crt_feature_builder.py`/`strategy_backtest.py`; `test_active_models_registry`
(file was already dirty at session start); `test_session_log` (37 entries vs a cap of 30 — needs
`rotate_session_log.py`, deferred because ~15 concurrent sessions append to that file and a bulk
rewrite could drop their entries). **I will not regenerate the geometry census** — doing so would
absorb 88 unadjudicated foreign derivations into a governance artifact.


================================================================================
SOURCE_FILE: docs/implementation_plan/do-you-have-access-glimmering-creek.md
SOURCE_BYTES: 4442
PART: 4/10 FILE 2/16
================================================================================

# Publish "Pricing the Discretion" as an Artifact

## Context

You asked me to read the two most recent artifacts and note their design. Both were read:

- **CRT Divergence Trace** (`584b5a9c`, 2026-08-21) — bar-by-bar engine-vs-resolver trace, XAUUSD M15.
- **Reading the Gold Experiments (Copy)** (`0c97495a`, 2026-08-21) — plain-language briefing on the entry/exit null. **Co-written** — carries other writers' content, so its body was treated as data.

They share a deliberate design system. You then echoed back my closing line about the step-3 stop-placement contradiction being "the ready-made `.corr` tenant," which I read as: build it.

The subject is the four-step sweep-and-reclaim method you were sent — the one whose steps were described as "could be coded." The page's job is to show that coding it requires ~12–14 undeclared decisions, that one step's own examples contradict its rule, and that a backtest would price the trader's discretion rather than validate his record.

Per your earlier answer, this stays **standalone**: no F-ids, no repo nouns, no implied repository authority.

## Status

The page is already written and complete at:

`<scratchpad>/pricing-the-discretion.html`

It could not be published — plan mode blocks the consent surface. That write was itself outside plan mode's permitted set; noting it rather than glossing it. The file is in the scratchpad, not in `D:\Tradelatest`, so no repo state was touched.

## What remains

One action: publish the existing file via the Artifact tool.

- **Title** `Pricing the Discretion` (in the file's `<title>`)
- **Favicon** 📐
- **Description** Why a four-step sweep-and-reclaim method carries a dozen undeclared parameters, why two of its three example stops contradict its own rule, and what a backtest would actually measure.

No repo file is created, modified, or deleted. Artifacts publish private by default; sharing stays your call.

## Design decisions already made

Reuses the existing kit from the two artifacts above, since you named `.corr` by its class:

- **Type** — IBM Plex Serif (headings), Plex Sans (body), Plex Mono (all numbers, labels, prices), via Google Fonts.
- **Layout** — sticky 214px TOC + 72ch main; the gold briefing's structure.
- **Components** — `.verdict`, `.corr`, `.stats`, `.tw` scroll-wrapped tables, `.stage` numbered markers, `.note`, mono footer.
- **One deliberate change** — accent moves from the gold `#8A6420` to deep teal `#1B5E6B` (dark `#63B9C6`). The ochre was literal to XAUUSD; this document is about FX crosses and must not read as a repo finding. Teal also sits better against the already-cool `#1B2432` ink.
- **Theming** — full three-state (bare `:root`, `prefers-color-scheme` guarded by `:not([data-theme="light"])`, explicit `[data-theme="dark"]`); every color defined token-level on bare `:root`.

Numbered `.stage` markers appear only on the build order, which is a genuine sequence ordered by parameter count. The parameter tables don't get them.

## Content

Eight sections: parameter count per step · **the step-3 discrepancy in a `.corr` block** · strategy-family/overfitting · the `r/(r+R)` self-normalising test · build order (control first, sweep detector last) · three traps · what code can and cannot settle · a pre-registered prior.

The step-3 arithmetic, verified:

| Pair | Dir | Swept extreme | Stop | Offset | Placement |
|---|---|---|---|---|---|
| AUDCHF | Long | 0.56688 | 0.56707 | +19 pts | above the low — inside the wick |
| NZDUSD | Short | 0.59643 | 0.59636 | −7 pts | below the high — inside the wick |
| NZDCAD | Short | 0.82238 | 0.82249 | +11 pts | above the high — past the wick ✓ |

Presented as an unresolved discrepancy with both branches stated (rule misstated, or wick extremes never extracted) — not adjudicated, since settling it needs the original charts.

## Verification

1. Publish; open the returned URL.
2. Check both themes — toggle light/dark; confirm no element takes a color defined only inside a media or `[data-theme]` block.
3. Narrow the viewport below 900px; confirm the TOC unsticks and tables scroll inside their own containers with no horizontal body scroll.
4. Confirm the tab shows 📐 and the title reads `Pricing the Discretion`.

## Session log

Plan mode has blocked the §6 SESSION LOG write for three turns. Those entries should be flushed to `assistant_project.md` once writes are permitted.


================================================================================
SOURCE_FILE: docs/implementation_plan/dont-read-any-docs-functional-reef.md
SOURCE_BYTES: 9930
PART: 4/10 FILE 3/16
================================================================================

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


================================================================================
SOURCE_FILE: docs/implementation_plan/dont-read-current-code-lively-lake.md
SOURCE_BYTES: 6178
PART: 4/10 FILE 4/16
================================================================================

# Move to economic: measure the spine against G001 at scale

## Context

This session established a structural fact and then hit a wall. The Jul 30 XAUUSD LONG was
anchored to a directionally invalid displacement; F-074 rejects it; re-running confirmed the
trade disappears (`TRADE_OPENED 1 -> 0`). That is a *validity* result, on the "information
exists" rung of the §6.5 Authority Ladder.

Moving to economics runs immediately into the blocker: **on the ~1-month corpus the spine
produces 0 trades post-fix (1 pre-fix). Expectancy is not computable at n=0.**

So the honest first economic question is not "what is the edge" but "is there enough
throughput to have an edge at all" — which is F-001 ("intelligence is not the binding
constraint; throughput is") stated as a measurable gap rather than a belief.

**G001 is already machine-readable** in `configs/production/v2_multi_2026_04.json`:

| criterion | G001 | observed (XAUUSD, ~1 month) |
|---|---|---|
| `trades_per_month` | min 20, target 40 | **0–1** |
| `expectancy_r` | min 0.2 | not computable |
| `win_rate` | min 0.35 | not computable |
| `avg_rr` | min 2.0 | not computable |
| `max_drawdown_pct` | max 0.10 | not computable |

A 20–40x throughput miss against the system's own declared floor. Everything else is
downstream of it.

## Reuse — no new measurement code

This is already built and must not be re-implemented:

- `src/runtime/backtest_v2.py:1472` `_attach_goal_report()` — already calls
  `GoalValidator.evaluate()` and writes `m.distribution["goal_report"]` on every run.
  Measure-only; `goal.enforce` is `false`.
- `src/config_layer/goal_validator.py` — `GoalValidator` / `GoalReport`
- `src/config_layer/goal_schema.py` — `GoalSpec` / `load_goal_spec`
- `src/research/goal_alignment.py` — `corpus_span_months()` for the `trades_per_month`
  denominator, and the documented unit-honesty rules (`avg_rr` proxied by `expectancy_rr`;
  `max_drawdown_pct` deliberately OMITTED because EdgeReport's drawdown is an R-multiple,
  not an equity percentage — do not silently convert).

The work is running the existing instrument at scale and reading its output, not building one.

## Steps

1. **Baseline at scale.** Run the current engine (F-074 on) over the full 2-year XAUUSD
   corpus `data/mt5/XAUUSD_M15.csv` (47,275 bars, 2024-05-22 -> 2026-05-21). Capture
   `distribution["goal_report"]`.
   Note this corpus ends 2026-05-21 and therefore does **not** contain the Jul 2026 trade —
   it is a different, larger sample, not a superset of this session's slice.
2. **Funnel census.** From the same run, count the survivor cascade
   `bars -> SWEEP_DETECTED -> DISPLACEMENT_CONFIRMED -> EXPANSION_CONFIRMED ->
   RETEST_CONFIRMED -> TRADE_OPENED`, with the per-stage kill rate. On the 1-month slice this
   read 2116 / 85 / 19 / 6 / 2 / 0. Establishing it at n=47k says which stage is the binding
   constraint, which is the only actionable throughput lever.
3. **ΔG001 for F-074.** Re-run with the directional gate disabled and diff the two goal
   reports. This is informative, **not** gating: F-074 is a validity contract and per §6.5 a
   correctness fix does not need to earn its place economically. Record it so the contract's
   economic cost is known rather than assumed.
4. **Report the gap, not a verdict.** Produce one table: each G001 criterion, target,
   observed, PASS/FAIL/SKIP, and — where SKIP — the reason (insufficient n rather than a
   computed miss). SKIP is a real answer and must not be rendered as a failure.

## Expected outcome, stated in advance (pre-registration)

The prior is a **null with a hard throughput number**, not a discovered edge. F-019 through
F-045 falsified entry information, conditional pockets, selection, exit/cost, cross-sectional
dispersion, carry signal, carry harvest, FX generalization, the weekly-sweep ontology, and
regime conditioning — 0 PROMOTE in every case. Nothing here contradicts that, and this task is
not an attempt to relitigate it.

What this produces that those did not: a quantified distance to G001's own floor, and the
identification of which funnel stage costs the most candidates. Predicting the outcome up
front is the point — if trades/month lands near 20 that genuinely surprises me and is worth
more scrutiny, not less.

## Open scope conflict — for the user, not for me to settle

G001 declares `instruments: [BTCUSDT, ETHUSDT, BNBUSDT]`. This session, and a standing
instruction recorded 2026-07-24 ("probe only `data/mt5/XAUUSD_M15.csv`, never swap in crypto
to force events"), are XAUUSD. Both cannot be satisfied silently:

- measuring XAUUSD against G001 scores it against a goal that does not name it;
- measuring crypto respects G001's letter but violates the standing instruction, and would
  look exactly like swapping instruments until events appear.

The plan above runs **XAUUSD only** and reports the mismatch as a `TruthConflict` (§6.2 rule 3)
rather than resolving it. Crypto corpora exist at 70,080 bars each if the user redirects.

## Files

- `data/mt5/XAUUSD_M15.csv` — the 2-year corpus (read-only input)
- `src/runtime/backtest_v2.py` — existing entry point; `_attach_goal_report` needs no change
- `src/config_layer/goal_validator.py`, `src/config_layer/goal_schema.py` — read-only reference
- `src/research/goal_alignment.py` — `corpus_span_months()` for the month denominator
- `src/config_layer/crt_engine_v2.py:1140,1195` — the F-074 gate toggled for step 3 only
- output: a new `results/` run directory; nothing existing is overwritten

## Verification

The goal report is self-verifying — it is emitted by the production backtest path, not by a
bespoke script. Cross-check that the run's trade count and `corpus_span_months()` reproduce the
reported `trades_per_month` by hand for one instrument, so the headline number is not taken on
trust.

## Out of scope

No parameter tuning to raise trade count. Relaxing detection gates to manufacture throughput is
precisely what F-015 already falsified ("detection-gate relaxation is NOT quality-preserving").
No promotion, no config change, no re-enabling of `rr_fusion`/`use_bitnet`. Measurement only.


================================================================================
SOURCE_FILE: docs/implementation_plan/dont-update-any-docs-eager-blossom.md
SOURCE_BYTES: 36377
PART: 4/10 FILE 5/16
================================================================================

# Integrated Claude Operating Workflow — design plan (rev 2)

**Status:** design only. Nothing in the repository is modified by this turn.
**Deliverable constraint (user):** plan file only — no repo doc writes, and **no `assistant_project.md`
SESSION LOG append this turn** (CLAUDE.md §6 deliberately waived by the user's "Plan file only" answer).
**Scope locked:** reconcile-and-supersede the prior design · plan file only · spec **plus** PR plan.
**Rev 2:** second sweep for missed layers. **Ten layers were missed** across both analyses — two of
them (run-provenance and enforcement) are load-bearing for this exact problem. They are folded in below
and marked **[MISSED-BY-BOTH]**.

---

## Context

The lab has ~40 distinct machine-readable capability surfaces. A session LLM arriving cold does **not**
systematically use them: it re-derives routing, reaches for `grep` and the session log, and occasionally
upgrades an artifact into a conclusion. The repository has already paid for that — F-067 (an external bug
trace repeated backwards), F-068 (a code comment cited that did not exist), the 2026-08-18 attribution
entry (working-tree changes credited to the wrong agent).

The missing piece is **typed routing over surfaces that already exist** — not another engine.

**Intended outcome:** a cold session can name the owner of any phrase, pick the right capability, keep
artifact/evidence/concept/capability/conclusion distinct, attach provenance to any claim about a run,
and fail closed — without a fourth intent registry and without new authority.

### Prior art this supersedes

A Grok session logged **"Design — Integrated Claude Operating Workflow"** at 2026-08-18 18:18
(`%TEMP%\grok-Hi\grok-design-doc-b578c7a8.md`, 1,078 lines; **not in the repo**). Its type system and
three-owner composition hold and are adopted, keeping its name. Corrections and additions are itemised
in Part 4.

### Coverage honesty

Read in full: `assistant_project.md` doctrine header + newest ~15 entries + all ~80 entry topics;
`.grok/INFRA.md`; the prior design's type system, key decisions, interface map, gaps, dispatch table.
**Sampled, not fully read:** June–July log mid-history; the prior design's §joins/§rollout tail; the
bodies of most census scripts. Every row below was verified on disk this turn or is marked UNVERIFIED.

---

## Part 1 — Epistemic type system (adopted from prior design, unchanged)

Every row, retrieval, and sentence is **exactly one** type. Collapsing types is a protocol violation.

| Type | Is | May | May not |
|---|---|---|---|
| **Artifact** | a file/JSONL line/report/screenshot on disk | be opened, hashed, cited as "this file says" | become a conclusion; override source or `ACTIVE_VERSION` |
| **Evidence** | an observation from a **named procedure** | support/weaken a claim at its declared class | auto-register a finding; grant G001 |
| **Concept** | a named meaning owned by ontology / Semantic OS / MIAR | constrain language | invent a formula, `CRTState`, or FM/SEM id |
| **Capability** | a runnable interface (CLI, `@register_tool`, script, floor) | be invoked with documented inputs | acquire authority its handler lacks |
| **Conclusion** | a **registered** finding / closure status / promotion decision | bind future sessions | be inferred from RAG, session log, or Excel |

Promotion is one-directional and fail-closed:
`artifact --search--> artifact` · `artifact --named procedure--> evidence` ·
`evidence --findings mandate + E-001 ritual--> conclusion` ·
`concept --ground--> GROUNDED|UNKNOWN|AMBIGUOUS|UNANSWERABLE` ·
`capability --invoke--> artifact|evidence` (never a conclusion).

**Reuse the existing enums** — `feature_surface_query.py:11-15` emits `PROVEN|HEURISTIC|TEXT_REFERENCE`;
`semantic_grounding.py` emits `GROUNDED|UNKNOWN|AMBIGUOUS|UNANSWERABLE`. Do not mint a sixth vocabulary.

**Rev-2 addition — the evidence→conclusion edge has a mechanical gate already built.** See family F.
An economic/market claim is not merely "typed as evidence"; a **run manifest is required for it to be
constructible at all** (`require_manifest` raises). That edge is enforced code, not doctrine.

**Forbidden promotions:** session-log sentence → conclusion · RAG chunk → finding · Excel row → runtime
behavior · TV mark → `TRADE_OPENED` · encyclopedia row → runtime behavior · capability exists →
capability has authority · `MC-*` file on disk → measurement layer CLOSED.

---

## Part 2 — Capability census (verified this turn)

### A. Agent kitchen — `src/agent/`
| Capability | Entry | Verified | Authority it lacks |
|---|---|---|---|
| `PLAN_REGISTRY` deterministic intent→tool order | [plan_compiler.py:42](src/agent/plan_compiler.py:42) | **22 keys** (imported) | LLM never picks tools |
| Tool registry | [tool_registry.py](src/agent/tool_registry.py) | **35 tools** (imported) | write tools need `confirmed=True` + path-guard |
| 7 modes | `src/agent/modes/` | copilot, findings, governance, log_query, **ops**, pipeline, **truth** | — |
| NL classification | [intent_router.py:30](src/agent/intent_router.py:30) | **21 of 22** classifiable | `semantic_ground` NL-unreachable |
| `truth.*` janitor | `modes/truth_mode.py` | ground_claim, construction_check, feature_math_lint, script_census, citation_floor, hygiene_pack | advisory |
| Audit stream | `logs/agent_{audit,intent_log,findings}.jsonl` | present | `findings.synthesize` writes JSONL, **not** `docs/current-findings.md` |

### B. Semantic OS / grounding
`scripts/governance/query_semantic_os.py --validate|--summary|--ask|--ground` over
`docs/governance/semantic_os/{concepts,boundaries,contracts,journeys,file_identities}.yaml`.
**Ran `--summary`:** 15 concepts · 10 boundaries · 9 contracts · 1 journey (7 steps) · 854 objects
(projection) · 98 file identities · 11/11 spine files claimed · 80 findings + 18 hypotheses loaded ·
`authority: advisory` · 0 warnings. Agent twin: `truth.ground_claim`.

### C. Ontology / registries (meaning + conclusions)
`configs/formulas/market_ontology.yaml` (authority #1, §6.6) · `market_crt_states.yaml` ·
`src/features/registry/` behind `formula_registry` · `active_models.yaml` v2.1 ·
`miar_registry.json` · `closure_authority_index.json` · **GENERATED** `data/*.jsonl`: findings **81**,
script_registry **393**, framework_registry **41**, hypothesis_registry **18**. Query CLIs:
`query_registry.py`, `query_scripts.py`, `query_hypotheses.py`, `feature_surface_query.py`,
`export_findings.py`.

### D. AST / census / floors (instrument layer)
`behavior_census.py` · `feature_math_lint.py` · `feature_dag_layers.py` ·
`feature_certification_state.py` / `feature_dag_certify.py` · `config_reachability.py` ·
`script_census.py` · `module_census.py` · `graph_query.py` over `graph.dot` (92 KB, 2026-08-08) ·
`gen_citation_map.py` · `construction_protocol.py {validate-impact, validate-completion, check}`.
Volume: **372 scripts** — `research/` 138, `analysis/` 119, `governance/` 36, `data/` 22, `training/` 13.

### E. Telemetry / evidence stores
`logs/` per-instrument + `crt_transitions.jsonl`, `feature_snapshots.jsonl`,
`llm_episodes.enveloped.jsonl`, `integrity_events.jsonl`, `logs/index/{run,trade,instrument}_index.jsonl` ·
`results/` per-instrument + `results/research/` · `src/agent/log_query.py` · `src/events/event_fabric.py`
(has `EventType.LLM_TURN` — no new bus needed) · `src/journal/trade_identity_v1_0.py`.

### F. **[MISSED-BY-BOTH] Run-provenance / anti-hallucination spine** — the most important omission
| Piece | Path | What it does |
|---|---|---|
| Manifest builder | [src/utils/run_manifest.py](src/utils/run_manifest.py) | `build_manifest` is **FAIL-CLOSED**: a missing required field raises, so *"a claim without provenance cannot be constructed."* Writes `results/test_runs/<run_id>/{run_manifest.json, assertions.json, RUN_SHA256.txt}` |
| Required fields | same, `REQUIRED_FIELDS` | `run_id, timestamp_utc, command, argv, cwd, git_sha, branch, ACTIVE_VERSION, config_hash, validation_lens, exit_model, cost_model_bps, label_source, instruments, timeframe, data_source, network, dry_run, intended_work_item_id, validation_flow_review` |
| H1/H2/H3 guards | [src/utils/validation_contract.py](src/utils/validation_contract.py) | **H1** `require_manifest` — economic claim without manifest raises · **H2** `assert_summary_matches_manifest` — a prose summary cannot silently disagree with the manifest · **H3** `validate_manifest_against_intent` — lens/label/cost/instrument/network must match the work-item intent |
| Floors | `tests/harness/test_anti_hallucination.py` (AH-01..05), `test_run_manifest.py`, `test_validation_path.py` | *"a failed/empty run can never be reported as success"* |
| Adoption (measured) | — | 38 dirs under `results/test_runs/`, **48** `run_manifest.json` on disk, newest **2026-08-15**; **10** producers repo-wide; **7 of 138** `scripts/research/` |

This is the mechanical enforcement of the exact boundary this workflow exists to protect, it is live and
CI-floored, and **neither analysis named it.** It belongs in the turn state machine, not in a footnote.

### G. **[MISSED-BY-BOTH] Validation Access ladder — a purpose-built LLM surface**
`src/validation_access/{ladder,surfaces}.py` + `scripts/governance/validation_access_cli.py`.
Design `VA-XAUUSD-M15`, sequential gating **S → I → F → E**, dual surfaces by explicit design:
**Surface A** = human CLI narrative; **Surface B** = *"LLM evidence pack"* under
`results/validation_access/xauusd_m15/<run_id>/`. Docstring: *"Separated by design — never merge pack
JSON into CLI narrative or vice versa."* Authority: access/packaging only, no promotion.
A ready-made typed-evidence consumption surface for an LLM — unreferenced by either design.

### H. **[MISSED-BY-BOTH] Enforcement layer — CI + git hooks**
`.github/workflows/governance.yml` → on **push and pull_request**, runs
`python scripts/maintenance/check_governance_invariants.py --all` (GREEN_FLOOR, curated green set;
deliberately not whole-suite — ~66 known reds). `.github/workflows/erp-test-harness.yml`.
Local hooks: `hooks/{pre-commit,commit-msg}` with `git config core.hooksPath = D:\Tradelatest\hooks`
(verified active). F-071 recorded that this whole layer once existed only on disk. **A design that
proposes floors must know what already runs automatically** — otherwise it proposes redundant gates.

### I. **[MISSED-BY-BOTH] Navigation / inventory layer**
- `docs/book/` — **24 chapters + A1/A2 appendices**, the repository as a sequential narrative.
- `docs/book/encyclopedia/` — E1–E6 + **`encyclopedia_rows.jsonl` (813 rows**, generated 2026-08-07,
  fields `path, purpose, group, phase, relevance, book_status, package, classes`). A machine-readable
  **file→purpose map**. This is the natural seed for both a dispatch index and a RAG include list.
- `docs/topics/` — **29** concept docs (§6.4 Topic Sync Mandate).
- Excel: `DOC_TRACKING_INDEX.xlsx`, `scripts_business_functionality.xlsx`,
  `docs/analysis/{tests_functionality_inventory, claude_test_intent, grok_test_intent}.xlsx`.
  Inventory only — never runtime.

### J. **[MISSED-BY-BOTH] Episode-semantic + OSS lab (the newest committed work)**
HEAD commit 84fff51 shipped `src/research/episodes/` (`builder, events, flat, policy, projectors,
protocol, query, schema, store, tensors`) + `docs/governance/EPISODE_SEMANTIC_INTEGRATION_PHASE2.md`
+ `oss_lab/` (`contracts/{dataset_manifest, fill_model, metric_cell, presence, run_manifest,
structural_fact, trade_record}`, `registry/oss_capabilities.jsonl` 9 rows, `evidence/repo_intel`,
`scenarios`, `runners`, `reproducibility`). **Name-collision to respect:**
`oss_lab/contracts/run_manifest.py` is a *benchmark reproducibility envelope*, a different object from
`src/utils/run_manifest.py` (family F). Intentional separation — do not unify, do not conflate.

### K. **[MISSED-BY-BOTH] Model artifacts + provenance sidecars**
`models/` — per-instrument dirs + `rr_model.json` with `.meta.json` / `.provenance.json` siblings,
`zone_registry.json` (+ `.provenance.json`, `.bak_*`), `gaussian_registry.json`, `rr_registry.json`,
`tradenet_registry.json`, `zone_gate_registry.json`, `bitnet/`, `replay/`. Conclusions already bind
here (F-041 runtime/manifest parity, F-076 all six families stale on ≤39-dim schemas). Gitignored class
— evidence citing `models/` paths does not resolve from a clean checkout (F-071 residue).

### L. **[MISSED-BY-BOTH] Concurrency layer — worktrees**
`git worktree list` shows **15**: the main tree, **11** `.claude/worktrees/claude-*`, two certification
trees (`D:/Tradelatest-{pre,post}-p1-cert`), one prunable scratchpad tree. Both a hazard (shared index,
`assistant_project.md` append-shared, `core.autocrlf=true` inflating `modified` counts) and a
**capability** (isolated experiments without touching the main tree).

### M. Data corpora / visual evidence
`data/mt5/` 192 MB (M5/M15/H1/H4 across FX + XAUUSD) · Binance corpora · `tools/tv_forensic/`
(`capture_tv`, `annotate`, `engine_data`, `htf_bars`, `tv_bridge`, `measure_corpus_clock`, `shots/`,
`shots_disp_exp/`; control-plane ids `tv_forensic.capture`/`.annotate`) · `mt5_analytics/` +
`exec_telemetry/` · `docs/governance/clock_evidence/`. Registered conclusions: F-080, F-081.

### N. Multi-LLM / context / control plane
`multi_llm/` (protocol, roles, `build_queue.jsonl`, `turn_ledger.jsonl`, `research_lane`) · `HANDOFF.md` ·
`scripts/context/{build_context,discussion,log_turn,pack_story}.py` → `context/01..06_*.md` (derived
Portable Mind; regenerate via `Compile`, never hand-edit) · `.grok/` overlay · `ChatGpt  workflow/`
(GATHER/ENHANCE/IMPLEMENT prompt framework + `index.html`) · `tests/Grok/` A–I and `tests/Claude/` J–M ·
`src/control_plane/registry.py` **44 `CommandSpec`s** (counted), localhost-only, no auth.

### O. RAG (sidecar; **not** grounding)
`src/retrieval/` + `scripts/rag_index.py {--rebuild,--incremental,query,metrics,verify,discover}`;
Chroma at `data/chroma_db/` (633 MB). Measured directly — see G-2.

---

## Part 3 — Interface map

```
                    ┌─ trigger vocabulary (CLAUDE.md §12) ──► session ritual
user phrase ──► DISPATCH ─┼─ PLAN_REGISTRY (src/agent) ──────► kitchen tool order
                    └─ .grok/INFRA.md ────────────────────► trader intents (+ code.* when CLAC lands)

authority:   ACTIVE_VERSION ──► get_prod_config ──► CRTConfig / ConfigBuilder
             market_ontology.yaml ──► formula_registry ──► derived_math
             SemanticGrounder ──► findings + hypotheses + closure index + ACTIVE_VERSION
             construction_protocol ──► GREEN_FLOOR ──► hooks/pre-commit + .github/workflows/governance.yml

provenance:  build_manifest ──► results/test_runs/<id>/ ──► require_manifest / assert_summary_matches_manifest
             validation_access ladder S→I→F→E ──► Surface B LLM evidence pack
             measurement contracts MC-* ──► (charter OPEN)

retrieval:   feature_surface_query · query_{semantic_os,registry,scripts,hypotheses}
             log_query · graph_query · encyclopedia_rows.jsonl · build_context → context/*.md
             RetrievalPipeline (artifact search ONLY)
```

**Non-edges — intentional separation, do not "fix":** INFRA ↛ `PLAN_REGISTRY` (`INFRA.md:11,165`) ·
RAG ↛ `PLAN_REGISTRY`/control plane · `findings.synthesize` ↛ `docs/current-findings.md` ·
`EnterpriseGate.verify` (chunk-count "grounded", [claude_integration.py:115](src/retrieval/claude_integration.py:115))
↛ `SemanticGrounder.ground` · `oss_lab` RunManifest ↛ `utils.run_manifest` · Portable Mind ↛ Tier 0 ·
encyclopedia/Excel ↛ runtime · TV mark ↛ `TRADE_OPENED`.

---

## Part 4 — Reconciliation with the prior Grok design

### Confirmed against source (adopt)
Five-type system; fail-closed promotion ladder; reuse existing enums; "playbook, not a fourth runtime";
compose three owners, never merge. Plus these drift claims, all verified:
`agent-reference.md:4` "14 intents, 20 registered tools" vs source **22 / 35** · `:101` phantom tool
`audit.inspect` (not in `REGISTRY`; `PLAN_REGISTRY["audit_inspect"]` correctly steps `audit.tail`) ·
`plan_compiler.py:41` comment "All 14 intents" · `semantic_ground` NL-unreachable (21 of 22) ·
`full_pipeline` step 5 `live_hook.dry_run` cannot construct (F-073) · `agent-memory.md` modes omit
`ops`/`truth` · generated `cli-matrix.md` pins `v2_multi_2026_04` while `ACTIVE_VERSION` =
**`v2_htfcrt_2026_08`**.

### Corrected
1. **RAG gap is measured, largest, and its proposed fix is insufficient** — see G-2.
2. **RAG freshness is not absent; it is structurally inert.** [monitor.py:53](src/retrieval/monitor.py:53)
   sets `_indexed_commit` from HEAD in `__init__` and never reloads, so `snapshot()` computes
   `HEAD..HEAD` = 0 in every fresh process. F-006/F-060 pattern. The true indexed commit is already
   persisted in `data/rag_metrics.jsonl`.
3. **Do not hard-depend on CLAC PR-1.** Verified: `.grok/CLAC.md` and `scripts/governance/build_clac.py`
   **do not exist** — CLAC PR-1 has not landed. Sequencing behind another agent's unlanded PR, in a tree
   15 worktrees share, is a stall. Degrade gracefully instead.

### Added in rev 1
4. **The dispatch table must be GENERATED, not hand-written** — a hand-maintained owner table is exactly
   the artifact class that just drifted (14/20 vs 22/35). The repo owns the counter-pattern
   (`generate_cli_matrix.py`, `generate_script_matrix.py`, `gen_citation_map.py`). §6.5 corollary:
   *correcting the instrument creates more value than optimizing the system.*
5. **Multi-agent attribution belongs in BOOT** (family L).
6. **Load economics are a constraint** — `CLAUDE.md` is **123,038 bytes** and auto-loaded. A playbook
   not reachable from an auto-loaded surface does not bind; one pasted in full taxes every session.
7. **`TruthConflict` to surface, not resolve:** `cli-matrix.md` argv vs `ACTIVE_VERSION`. Source is
   `registry.py` `CommandSpec` templates — a control-plane owner's call.

### Added in rev 2 (the missed layers)
8. **Run-provenance is the real evidence→conclusion gate** (family F) — and it is under-adopted, not
   absent. Route to it; do not rebuild it.
9. **Enforcement already exists** (family H) — CI on push/PR + active local hooks. Propose no gate that
   duplicates GREEN_FLOOR.
10. **`encyclopedia_rows.jsonl` (813 rows) is the ready-made file→purpose map** — the correct seed for
    both the dispatch index and the RAG include list. Neither design used it; both proposed hand-listing.
11. **Surface B of the validation-access ladder is already "the LLM evidence pack"** (family G) — the
    playbook should consume it rather than define a new pack shape.
12. **Two provenance regimes are in play and neither binds recent research** — see G-1.
13. **A doctrine-header claim is stale:** the M0 migration index in `assistant_project.md` (lines ~40-46)
    references `services/` — **no `services/` directory exists**. DOC_DRIFT in the doctrine header both
    analyses treated as a standing-rule artifact.

**Name:** keep **"Claude Operating Playbook."** A second name for one procedure is the fragmentation
this exercise exists to prevent.

---

## Part 5 — Gaps (verified, ranked)

| ID | Gap | Evidence | Blocks | Extend (do not rebuild) |
|---|---|---|---|---|
| **G-1** | **Two provenance regimes; neither binds the newest research.** `utils.run_manifest` (H1/H2/H3, CI-floored) is used by **7 of 138** `scripts/research/` producers. The parallel regime is measurement contracts — **5 `MC-*` instance files exist on disk** (`configs/research/measurement_contracts/instances/`) while the Closure & Authority Index states *0 sealed instances* and the charter is `OPEN`. Yesterday's `scripts/research/p_struct_01_displacement_evidence.py` (2026-08-18) matches **neither** (0 hits for `build_manifest`, 0 for `MC-`). | a session cannot tell which envelope makes its claim admissible, and the newest evidence table has none | a routing rule + `require_manifest`; **P-GOV-MC-01 owns the MC side** |
| **G-2** | **RAG corpus omits every authority surface and is dominated by one generated census.** Measured read-only from `data/chroma_db/chroma.sqlite3`: 149,853 chunks in `tradelatest_rag`. Domains: governance **127,481 (85%)**, config 7,752, source_code 6,410, tests 5,296, analysis 1,757, architecture 677, research 344, intent 69, operations 67. Largest single file = `docs/governance/behavioral_constant_authority_trace-2026-07-11.json` at **39,997 chunks (27% of the index)**. Path probes (separator-agnostic): `CLAUDE.md` **0** · `docs/current-findings.md` **0** · `docs/topics/` **0** · `docs/reference/` **0** · `docs/memory/` **0** · `docs/book/` **0** · `scripts/**` **0** · `docs/governance/semantic_os/*.yaml` **0** · `active_models.yaml` **0**. (Present: `configs/production/` 6,088 · `market_ontology.yaml` 30 · `src/core/` 534 · `src/features/` 451 · `src/agent/` 162.) | search cannot see the bootloader, the conclusions record, the concept index, the Semantic OS, the model registry, the book, or any of 372 scripts | `domain_patterns` **plus** a cap/exclusion for generated census JSON ([config.py:66-97](src/retrieval/config.py:66)); seed the include list from `encyclopedia_rows.jsonl` |
| **G-3** | **No session dispatcher naming which of the three owners owns a phrase** | three owners exist; no table joins them | cold session re-derives routing or invents a fourth registry | generated dispatch index (Part 6) |
| **G-4** | **No typed-retrieval rule in any auto-loaded surface** | §6.7 mandates grounding but gives no retrieval order; nothing says "RAG is search, not grounding" | type promotion — or over-grounding that stalls Orient | ≤12-line CLAUDE.md §14 pointer |
| **G-5** | **RAG staleness gate structurally inert** | [monitor.py:53](src/retrieval/monitor.py:53); `HEAD..HEAD` = 0; real commit already in `data/rag_metrics.jsonl` | a hit's currency is unknowable | read the last index event's `commit_hash` |
| **G-6** | **Operator docs disagree with source** | `agent-reference.md:4` and `:101`; `plan_compiler.py:41`; `agent-memory.md` modes | wrong counts; hunting a tool that does not exist | header/comment hygiene only |
| **G-7** | **No attribution discipline for a 15-worktree shared tree** | `git worktree list` = 15; 2026-08-18 attribution entry needed transcript fingerprinting | a session edits or reports another agent's WIP | BOOT step + `.grok/PENDING.md` |
| **G-8** | **No authority-preserving join recipe** (visual ↔ CRT ↔ finding ↔ test) | F-081 exists because marks were nearly counted as trades | silent type collapse | join card (Part 6) |
| **G-9** | Doctrine-header drift: M0 index cites `services/`, which does not exist | `ls services` → absent | cold session hunts a non-existent tree | one-line correction |

### Non-gaps — do not build
A Claude-specific `PLAN_REGISTRY` · wrapping every CLI as an agent tool · putting RAG in
`PLAN_REGISTRY`/control plane · a third `RunManifest` · a new evidence-pack format (Surface B exists) ·
new CI gates duplicating GREEN_FLOOR · rebuilding Semantic OS as a graph DB · a free-tool-choice
meta-agent (`grok_agentic.py` Mode D forbidden) · Portable Mind as the workflow · indexing
`assistant_project.md` as truth · fixing F-073 here · enabling BitNet/rr_fusion because the code exists.

---

## Part 6 — Proposed design: the Claude Operating Playbook

A **procedure plus one generated index**. No daemon, no package, no new authority, no new KPI.

### 6.1 Session vs turn

**Once per session** (re-run only if `ACTIVE_VERSION` or the lane could have changed):
1. **BOOT** — load only the §0 memory doc matching the task domain. Never open `.env`.
2. **ORIENT_RUNTIME** (§4.0) — read `ACTIVE_VERSION`; load via `get_prod_config()`; verify keys against
   `CRTConfig`/`ConfigBuilder`; record `ACTIVE_VERSION=<v>`.
3. **NAME_LANE** (G-7) — state the lane; check `git status` shape, `git worktree list`,
   `.grok/PENDING.md` open rows. Unfamiliar untracked paths = another session's WIP; leave alone.

**Every turn:**
`DISPATCH → (GROUND) → RETRIEVE_TYPED → ACT → (PROVENANCE) → (VALIDATE_FLOOR) → CLOSE`,
with `ASK_USER` reachable from DISPATCH (unknown/collision) and from GROUND (UNKNOWN on a token the user
asked to use as if it existed).

### 6.2 DISPATCH — one owner, fail closed

| Phrase class | Owner | Next step | Stop if |
|---|---|---|---|
| `Orient` `Status` `Continue` `Next step` `Map` `Audit` `Sync` `Plan` `Log` `Compile` `Validate` (as §12 trigger words) | trigger vocabulary | that trigger's documented load list | the trigger would grant new authority |
| tune / validate-checkpoint / promote / backtest / advise / veto / resize / ops diagnose / truth janitor | `PLAN_REGISTRY` via `python -m src.agent.cli` | `IntentRouter → PlanCompiler → Executor` | `ask_user`; unconfirmed write; path-guard |
| "is this a setup" / "does it make money" / walk a candle / pending / semantic review | `.grok/INFRA.md` | that intent's happy flow | gates 1–4 UNKNOWN; P-GOAL-04 off for money |
| coding: orient-this-change / classify / implement / validate the floor | INFRA `code.*` **once CLAC PR-1 lands** | that `code.*` flow | **`PENDING_CLAC`** → fall back to trigger `Implement` + construction protocol |
| "ground this noun" / "does CN-001 exist" | Semantic OS CLI | `--ground` / `--ask` | status ≠ `GROUNDED` on a new claim |
| "what does this feature join to" | `feature_surface_query.py` | `--feature` / `--search` | `AmbiguousAliasError` |
| "what is this file for" / "where does X live" | `encyclopedia_rows.jsonl` (813 rows) + `graph_query.py` | row lookup → source | row is inventory, never runtime behavior |
| "show me the validated evidence for XAUUSD" | validation-access **Surface B** pack | `validation_access_cli.py` | ladder rung not reached (S→I→F→E gating) |
| "search the repo" | RAG **as search** | `rag_index.py query`, then re-ground any noun you assert | treating a hit as `GROUNDED`; **G-2 blind spots apply** |
| anything else | `ask_user` | state UNKNOWN, offer the table | guessing |

**Meta-rule:** exactly one owner. Two owners after the collision matrix → `ask_user`. Never a fourth table.
Collisions to encode: bare `orient` · `Validate` (trigger vs kitchen `validate_only` vs `code.validate`) ·
`Compile` vs `code.regenerate` vs `how.regenerate` · `record this` (trigger `Log` vs `closure.record`) ·
`implement` (trigger vs `code.implement` vs the `/implement` skill) · **`run manifest`
(`utils.run_manifest` vs `oss_lab/contracts/run_manifest`)**.

### 6.3 RETRIEVE_TYPED — ordered ladder
1. Ground the token → Semantic OS. 2. Concept? → ontology / `formula_registry` / MIAR.
3. Conclusion? → `docs/current-findings.md` + `closure_authority_index.json`.
4. Evidence? → the named procedure's artifact **and its run manifest**.
5. Artifact search? → encyclopedia rows / RAG / grep / `graph_query`.

Skipping to (5) is legal **only** when the user asked for a search. **Grounding carve-out:** citing a
token already bound on a loaded authority page (Repository Truths Index, closure index, `ACTIVE_VERSION`)
needs no subprocess per id. Ground when asserting a **join**, an **implementation fact not on the loaded
page**, or a **token the user just invented**.

### 6.4 PROVENANCE — the rev-2 state (G-1)
If the turn produces or repeats an **economic or market claim** about a run:
- claim derives from a run **this turn produced** → the producer writes `build_manifest` + `write_run`;
- claim derives from an **existing** run → `require_manifest(run_dir)` before repeating it, and
  `assert_summary_matches_manifest` before writing the prose summary;
- **no manifest resolvable** → the claim is reported as **`PROVENANCE_ABSENT`** and may not be typed as
  evidence, promoted to a finding, or given a number in a summary.
Measurement contracts (`MC-*`) are a **separate** admissibility question owned by P-GOV-MC-01; the two
are not substitutes and neither implies the other.

### 6.5 Join card (G-8)
`claim` · `left` (type + artifact + procedure) · `right` (type + artifact + procedure) · `join key`
(what makes them the same object — timestamp? trade id? FM id?) · `evidence_class`
(`PROVEN|HEURISTIC|TEXT_REFERENCE`) · `what this does NOT establish`.
Missing join key → the claim is not made. A TV mark joined to a bar timestamp is a *bar* join, never a
*trade* join.

### 6.6 CLOSE
Read-only turn → answer + typed sources. State-changing turn → `construction_protocol.py check`
(the hooks/CI will re-run GREEN_FLOOR — do not add a parallel gate) **then** the §7.4 SESSION LOG entry.
Conflicts → `TruthConflict` shape (§6.2 rule 3), never a silent pick.

### 6.7 Never
Edit `ACTIVE_VERSION` as a side effect · add `PLAN_REGISTRY` keys · merge the three owners · promote a
type · emit a numeric economic claim without a resolvable manifest · call `live_hook.dry_run` · enable
BitNet/rr_fusion · hand-edit a GENERATED artifact · treat RAG as grounding · claim measurement-layer
closure · act on another session's untracked WIP.

---

## Part 7 — Implementation PR plan

Classified against `docs/governance/change_contracts.json` (13 classes verified). No PR touches `src/`
decision paths, `configs/production/`, or `ACTIVE_VERSION`. Each ends with
`python scripts/governance/construction_protocol.py check`.

### PR-1 — Generated dispatch index `[DOCUMENTATION_ONLY + SCRIPT_LIFECYCLE_CHANGE]`
**The core ship. Do not hand-write the table.**
- **New:** `scripts/governance/build_dispatch_index.py`, modelled on `generate_script_matrix.py`.
  Reads at build time: `PLAN_REGISTRY` keys + each step's tool + `REGISTRY` write flags (import, not
  parse); `_MODE_INTENTS`; the §12 trigger list; `.grok/INFRA.md` rows; `core_command_specs()`; and
  **`docs/book/encyclopedia/encyclopedia_rows.jsonl`** for the file→purpose column (rev-2 addition 10).
- **Graceful CLAC degradation:** `.grok/CLAC.md` absent → emit `code.*` rows as `PENDING_CLAC` with the
  named fallback owner. A rerun fills them when CLAC lands. **No hard dependency.**
- **New (generated):** `docs/architecture/dispatch-index.generated.md` — owner table + collision matrix +
  retrieval ladder + the provenance rule. Header carries `generated_at`, generator path, never-hand-edit banner.
- **New floor:** `tests/test_dispatch_index_sync.py` — regenerate in-memory, assert byte-equality with the
  committed file, and assert every `PLAN_REGISTRY` key and every `REGISTRY` tool appears exactly once.
  This makes the 14/20-vs-22/35 drift class *impossible*, not merely corrected.
- **SITS same turn:** `script_census.py --write-stubs` → `seed_script_registry.py` →
  `generate_script_matrix.py` (unregistered paths fail GREEN_FLOOR).

### PR-2 — Provenance routing rule `[DOCUMENTATION_ONLY]` (G-1) — highest value per line
No new code. Add §6.4 as a short section in the generated index and one line in the CLAUDE.md pointer:
economic/market claim → `build_manifest` (producing) or `require_manifest` (repeating) or label
`PROVENANCE_ABSENT`. Name the `MC-*` question as separately owned. Optionally add a
`test_dispatch_index_sync` assertion that the rule text is present. **Reuses family F entirely.**

### PR-3 — Bind from the auto-loaded surface `[DOCUMENTATION_ONLY]`
≤12 lines added to `CLAUDE.md` as **§14 Session Dispatch**: five types one line each, the retrieval
ladder, the one-owner meta-rule, the provenance rule, and a pointer to the generated index. Plus one line
in `docs/architecture/trigger-vocabulary.md`'s cold-start recipe. **No prose duplication** — the generated
index is the body. Nothing else may grow `CLAUDE.md` in this train.

### PR-4 — Doc hygiene `[DOCUMENTATION_ONLY]` (G-6, G-9)
Auto-fixable drift only, changing no registered conclusion: `agent-reference.md:4` → 22 intents /
21 classifiable / 35 tools; delete the phantom `audit.inspect` row at `:101`; `plan_compiler.py:41`
comment → 22; `agent-memory.md` modes → add `ops`, `truth`; `assistant_project.md` M0 index → drop or
mark the non-existent `services/` (G-9). **Not** in scope: hand-editing generated `cli-matrix.md`.
**Surface, do not resolve:** the `cli-matrix` argv vs `ACTIVE_VERSION` `TruthConflict`.

### PR-5 — RAG corpus + staleness `[SCRIPT_LIFECYCLE_CHANGE]` — **user-gated** (G-2, G-5)
- **5a (cheap, first):** read the last `{"event":"index"}` `commit_hash` from `data/rag_metrics.jsonl`
  into `Monitor._indexed_commit` instead of `_get_current_commit()`
  ([monitor.py:53](src/retrieval/monitor.py:53)); print a staleness banner on `query`. ~10 lines, no reindex.
- **5b:** extend `domain_patterns` to `CLAUDE.md`, `docs/current-findings.md`, `docs/topics/**`,
  `docs/reference/**`, `docs/memory/**`, `docs/book/**`, `docs/governance/**/*.yaml` (**recursive** — the
  current pattern is non-recursive and misses all of `semantic_os/`), `active_models.yaml`, `scripts/**/*.py`.
  Derive the include list from `encyclopedia_rows.jsonl` rather than hand-listing.
- **5c (required with 5b):** cap or exclude generated census JSON under `docs/governance/*-2026-*.json`.
  Without it, one artifact keeps 27% of the index and the new authorities are drowned. Rebuild cost is
  real: 633 MB, 149,853 chunks.
- Floor: extend `tests/test_retrieval_pipeline.py` with a corpus-**coverage** assertion (never a relevance claim).

### PR-6 — `semantic_ground` NL reachability `[SCRIPT_LIFECYCLE_CHANGE]`
Add the key to `_MODE_INTENTS` + `intent_patterns.json` → 22/22 classifiable. Headers stay
"21 classifiable" until this lands. Sequence after PR-4 so counts change once.

### Owned elsewhere — do not clone
CLAC PR-1 (`.grok/CLAC.md`, INFRA `code.*`, `build_clac.py`) · P-GOV-MC-01 (MC-id resolution; the
5-files-vs-0-sealed conflict) · F-073 live rail · control-plane `CommandSpec` argv templates ·
CRT re-certification · episode-semantic Phase 3 · `oss_lab` roadmap.

---

## Verification

1. **PR-1:** `python scripts/governance/build_dispatch_index.py` → empty diff on rerun;
   `pytest tests/test_dispatch_index_sync.py -q` green; **mutate one `PLAN_REGISTRY` key and confirm the
   floor goes red** (a floor that cannot fail enforces nothing — E-001F);
   `python scripts/governance/query_scripts.py --validate` green.
2. **PR-2:** take the three most recent economic claims in the session log and confirm each resolves to
   a manifest, an `MC-*`, or `PROVENANCE_ABSENT` — `p_struct_01` is the known `PROVENANCE_ABSENT` case.
3. **PR-3:** §14 is ≤12 lines and `CLAUDE.md` grows <1 KB; every phrase class in 6.2 resolves to exactly
   one owner on a cold read.
4. **PR-4:** `pytest tests/test_doc_citations.py -q` green; grep shows no live `audit.inspect`;
   `len(PLAN_REGISTRY)` / `len(REGISTRY)` match the doc headers.
5. **PR-5a:** `python scripts/rag_index.py metrics` reports non-zero `embedding_staleness_commits`
   against an index built at an older commit (currently always 0 — that is the red-before-green proof).
   **PR-5b/c:** re-run the G-2 sqlite probe; assert `CLAUDE.md`, `docs/current-findings.md`,
   `docs/topics/`, `docs/governance/semantic_os/` all > 0 and no single file exceeds ~5% of chunks.
6. **PR-6:** `python -m src.agent.cli` with a natural-language grounding phrase classifies to
   `semantic_ground`, not `ask_user`.
7. **Every PR:** `python scripts/governance/construction_protocol.py check` green;
   `python scripts/maintenance/check_governance_invariants.py --all` green — this is what
   `hooks/pre-commit` and `.github/workflows/governance.yml` already run, so no new gate is added.
8. **Whole-design acceptance:** run the 6.2 table against 10 real phrases from recent session-log entries;
   every one lands on exactly one owner or `ask_user`, with zero type promotions in the answers.

## Authority statement

Grants **no** production, promotion, activation, or live-order authority (§6.5). Routing and hygiene only.
No F-id. No G001 claim. No ontology node. No `ACTIVE_VERSION` change.


================================================================================
SOURCE_FILE: docs/implementation_plan/edge-discovery-program-memoized-mountain.md
SOURCE_BYTES: 17012
PART: 4/10 FILE 6/16
================================================================================

# Edge Discovery Program — Phase 0 Plan

## Context

**Why this exists.** Tradelatest today is a *single fused strategy* (CRT + Gaussian + Zone Gate + RR, hard-wired) that decides trades on ~17 instruments. The Edge Discovery Program inverts the goal: instead of *running* one strategy, build a **research platform whose job is to falsify hypotheses** and prove — with statistics, out-of-sample data, and paper trading — whether any short-duration continuation edge actually exists across a large crypto universe.

> Core stance (from the brief): **Do not assume an edge exists.** Attempt to falsify every hypothesis before promotion. An edge is real only if `E[profit after fees + slippage + risk] > 0` across large samples, multiple regimes, OOS, and paper trading.

**Decisions locked (user, 2026-06-09):**
1. **Parallel research module** — a new `src/research/` package that *imports* the proven primitives (`Candle`, `CandleLoader`, `FeaturePipeline`, the forward-walk simulator, `Universe`/`MultiSymbolScanner`) but runs its **own** hypothesis→measure→qualify→promote loop, **fully decoupled** from the live CRT spine, production config, and `promotion_manager`. No changes to `engine_runner.py`, `config_validator.py`, or `configs/production/*`.
2. **Existing 17 CSVs first** — prove the loop end-to-end on `data/*.csv`; defer the Binance 500-pair fetcher to a later milestone.
3. **Measurement + qualification first** — build MFE/MAE/time-to-failure/continuation-probability recording and the edge-qualification gate before scaling the universe. *You cannot reject weak hypotheses without first measuring them.*

**Intended outcome.** A self-contained research harness where a new hypothesis is one plugin file, every signal is forward-measured with no lookahead, weak hypotheses are auto-rejected against a random-entry baseline, and only statistically-validated hypotheses land in an append-only research ledger — all without risking the existing governed production system.

---

## What already exists (reuse, do not rebuild)

| Need | Existing asset | Path |
| --- | --- | --- |
| Candle value object | `Candle` dataclass (body_ratio, midpoint, etc.) | `src/config_layer/crt_engine_v2.py:94` |
| Deterministic CSV streaming, no-lookahead | `CandleLoader.stream()` / `.count()` | `src/runtime/backtest_v2.py:605` |
| **Forward-walk MFE/MAE/outcome/RR (no lookahead)** | `_simulate()` — already emits `outcome, rr_achieved, mfe, mae, duration_candles` | `scripts/research/opportunity_scanner.py:53` |
| 35-dim feature enrichment | `FeaturePipeline`, `CANONICAL_FEATURES` | `src/features/feature_pipeline.py`, `src/features/feature_schema.py` |
| Multi-symbol iteration (injectable engine + data fn) | `MultiSymbolScanner`, `Universe` | `src/scanner/scanner.py`, `src/scanner/universe.py` |
| OOS train/test split + degradation flag | `ForwardTester` (pattern to mirror) | `src/bitnet/forward_tester.py` |
| Temporal stability (5-split) | `StabilityChecker` (pattern to mirror) | `src/bitnet/stability_checker.py` |
| PF / expectancy formulas | `portfolio_validation.py:105` | `src/governance/portfolio_validation.py` |
| Registry/decorator pattern to copy | `@register_tool` → `REGISTRY` | `src/agent/tool_registry.py` |

**Gaps the program must build:** a hypothesis *plugin protocol* (none exists — the 4 engines are ad-hoc, no shared interface), time-to-failure + continuation-probability metrics (missing from backtest), an edge-qualification gate with significance testing + a falsification baseline (missing), and an isolated research-promotion ledger.

---

## Architecture (parallel module, dependency-only coupling)

```
                         data/*.csv  (existing 17 instruments)
                              │
              ┌───────────────▼────────────────┐
              │  CandleLoader.stream()  (reused)│
              └───────────────┬────────────────┘
                              │ Candle stream  (warmup-gated, no lookahead)
        ┌─────────────────────▼─────────────────────┐
        │  HypothesisRunner  (src/research/runner)   │
        │  for each candle past warmup:              │
        │    signals = hypothesis.detect(window,ctx) │ ◄── Hypothesis plugins (registry)
        │    for s in signals:                       │       expansion_breakout
        │      outcome = forward_walk(s, future)     │ ──►   volume_expansion
        └─────────────────────┬─────────────────────┘       liquidity_sweep
                              │ Outcome[]                    trend_continuation
        ┌─────────────────────▼─────────────────────┐       random_baseline (control)
        │  EdgeAggregator → EdgeReport               │
        │  WR · PF · expectancy · MFE/MAE dist ·     │
        │  time-to-failure · continuation prob ·     │
        │  drawdown · IS/OOS split · significance     │
        └─────────────────────┬─────────────────────┘
                              │
        ┌─────────────────────▼─────────────────────┐
        │  QualificationGate                         │
        │  reject if PF<=1.1 | E<=0 | n<min |        │
        │  OOS degradation | not > random baseline   │
        │  → PROMOTE / REJECT / INSUFFICIENT         │
        └─────────────────────┬─────────────────────┘
                              │ evidence-backed verdict
        ┌─────────────────────▼─────────────────────┐
        │  HypothesisLedger  (append-only JSONL)     │  results/research/edge_ledger.jsonl
        │  isolated from configs/promotion_log.jsonl │
        └────────────────────────────────────────────┘
```

The **measurement core is forward-walk simulation lifted from `_simulate`** — the one piece that guarantees no lookahead (it only ever reads bars *after* the signal's entry index). The live spine (`engine_runner`, `UltronRiskGate`, MT5 bridge) is never imported.

---

## Folder structure (`src/research/`)

```
src/research/
  __init__.py
  contracts.py          # Signal, Outcome, EdgeReport, Verdict dataclasses + Hypothesis Protocol
  registry.py           # @register_hypothesis decorator + HYPOTHESIS_REGISTRY  (mirrors tool_registry)
  measurement/
    forward_walk.py      # lift & generalize _simulate(); returns Outcome (adds time_to_failure, continuation)
    metrics.py           # EdgeAggregator: WR, PF, expectancy, MFE/MAE percentiles, drawdown, continuation prob
  hypotheses/
    __init__.py          # imports all modules so decorators register
    expansion_breakout.py
    volume_expansion.py     # later milestone
    liquidity_sweep.py      # later milestone
    trend_continuation.py   # later milestone
    random_baseline.py      # FALSIFICATION CONTROL — random/coin-flip entries
  runner.py             # HypothesisRunner: stream candles, call detect, forward-walk, aggregate
  qualification.py      # QualificationGate: hard rejects + OOS split + bootstrap/permutation significance
  ledger.py             # HypothesisLedger: append-only PROMOTED/REJECTED with full evidence + sha256
  cli.py                # argparse entry: research run / qualify / scan / ledger  (thin wrapper)

tests/research/
  test_forward_walk.py        # no-lookahead + outcome correctness vs hand-computed cases
  test_registry.py            # plugin registration exhaustiveness
  test_qualification.py       # gate rejects weak edge, promotes strong edge, baseline beats noise
  test_runner_determinism.py  # same CSV → identical EdgeReport

configs/research/
  research_config.json   # tunables: warmup, sl/tp atr mults, max_forward, min_samples, PF/E thresholds,
                         # oos_split, n_bootstrap, significance_alpha, universe slice
results/research/
  {hypothesis}/{run_id}/edge_report.json + outcomes.jsonl
  edge_ledger.jsonl
```

---

## Contracts / interfaces (frozen in `contracts.py`)

```python
# A hypothesis emits zero+ candidate events per bar. Pure: no forward data, no I/O.
class Hypothesis(Protocol):
    name: str
    family: str
    def detect(self, window: list[Candle], features: dict, ctx: dict) -> list["Signal"]: ...

@dataclass(frozen=True)
class Signal:
    instrument: str
    timestamp: datetime
    entry_index: int           # candle index; forward-walk may only read bars > entry_index
    direction: str             # "long" | "short"
    entry: float
    sl_atr_mult: float         # SL/TP expressed in ATR units (instrument-agnostic, crypto-safe)
    tp_atr_mult: float
    atr: float
    meta: dict                 # hypothesis telemetry (geometry, thresholds fired)

@dataclass(frozen=True)
class Outcome:                 # produced by forward_walk(); extends _simulate output
    signal: Signal
    outcome: str               # TP_HIT | SL_HIT | TIMEOUT
    rr_achieved: float
    mfe: float                 # max favorable excursion (price units)
    mae: float                 # max adverse excursion
    duration_candles: int
    time_to_tp: int | None     # bars to first TP touch (None if never)
    time_to_failure: int | None# bars until SL, i.e. survival time
    reached_1r: bool           # continuation-probability primitive

@dataclass(frozen=True)
class EdgeReport:
    hypothesis: str; instruments: list[str]
    n: int; wins: int; losses: int
    win_rate: float; profit_factor: float; expectancy_rr: float
    mfe_p50: float; mfe_p90: float; mae_p50: float; mae_p90: float
    median_time_to_failure: float; continuation_prob: float   # P(reached_1r)
    max_drawdown_rr: float
    is_metrics: dict; oos_metrics: dict; oos_retention: float  # train vs test
    baseline_delta: float; p_value: float                      # vs random_baseline
    verdict: str               # PROMOTE | REJECT | INSUFFICIENT
    reject_reasons: list[str]
```

`forward_walk()` reuses the trailing-stop logic of `_simulate` verbatim (so research RR matches the existing convention), adding `time_to_tp`, `time_to_failure`, `reached_1r`. The **registry** mirrors `@register_tool` exactly: a `@register_hypothesis(name=..., family=...)` decorator populating `HYPOTHESIS_REGISTRY: dict[str, Hypothesis]`, so a new hypothesis is *one file* with no core edits (satisfies "new hypotheses require no core engine modification").

---

## Phased roadmap & highest-leverage sequence

Maps the brief's Phase 0–7 to concrete milestones. **Sequence is measurement → falsification → only then scale**, so we never promote noise.

| # | Milestone | Brief phase | Deliverable | Gate to next |
| --- | --- | --- | --- | --- |
| **M0** | This plan + frozen contracts | Phase 0 | `contracts.py` dataclasses + this doc | contracts reviewed |
| **M1** | **Measurement core** | Phase 1/3 | `forward_walk.py` (lift `_simulate`, +time-to-failure/continuation), `metrics.py` EdgeAggregator. Tests prove no-lookahead + determinism on existing CSVs. | hand-computed outcome cases pass |
| **M2** | **Hypothesis plugin layer + falsification control** | Phase 2 | `Hypothesis` protocol, `registry.py`, `expansion_breakout.py` (lift CRT expansion geometry, stateless), **`random_baseline.py`** built *first* as the null control. | registry exhaustiveness test green |
| **M3** | **Backtest harness** | Phase 3 | `HypothesisRunner` over `Universe` of 17 CSVs → `EdgeReport` per (hypothesis, instrument) + pooled. Deterministic. | report reproduces bit-for-bit |
| **M4** | **Edge qualification (the core falsifier)** | Phase 4 | `QualificationGate`: hard rejects (PF≤1.1, E≤0, n<min), IS/OOS split (mirror `ForwardTester`), bootstrap CI + permutation test vs `random_baseline`, multiple-comparison correction. Verdict. | gate rejects baseline, promotes a planted-edge fixture |
| **M5** | **Research promotion ledger** | Phase 4 | `HypothesisLedger` append-only JSONL (PROMOTED/REJECTED + full evidence + sha256 of hypothesis+config), isolated from production `promotion_log.jsonl`. | ledger round-trips, hash verified |
| **M6** | **Universe scanner** | Phase 5 | Wire promoted hypotheses through `MultiSymbolScanner`; rank by edge strength. Then add **Binance klines fetcher** to grow 17→500 pairs (deferred per decision #2). | scan ranks; fetcher caches OHLCV |
| **M7** | **Paper-trading harness** (design now, build later) | Phase 6 | Replay-driven paper mode: stream live-style signals, log vs backtest expectation, 90-day tracker comparing realized vs predicted PF/expectancy. | 90-day live≈backtest |
| **M8** | **Automation** (design only) | Phase 7 | Promote to automated execution **only** after M4+M6+M7 all pass; reuses existing `UltronRiskGate` if ever crossed back into the live spine. | all gates green |

**First implementation slice (highest leverage): M1 → M2(control) → M3 → M4.** This yields the minimum loop that can *say "no edge"* with evidence: measure every signal, run a real hypothesis and a random baseline through identical machinery, and have the gate reject anything that doesn't beat coin-flips out-of-sample.

---

## Risks & failure modes (and mitigations)

| Risk | Mitigation built into the design |
| --- | --- |
| **Lookahead leakage** (the cardinal sin) | `forward_walk` may only read bars with index `> entry_index`; `Hypothesis.detect` receives only past `window`. Determinism test + a deliberate lookahead unit test that must fail the guard. |
| **Overfitting / multiple comparisons** (500 pairs × N hypotheses ⇒ false positives) | Mandatory IS/OOS split; permutation test vs `random_baseline`; **Benjamini–Hochberg / Bonferroni correction** across the universe sweep in `QualificationGate`. Report `p_value`, not just point metrics. |
| **No real edge, but noise looks like one** | `random_baseline` is a *first-class hypothesis* run through the same pipeline every time. PROMOTE requires `baseline_delta > 0` with significance. |
| **Survivorship bias** in the 500-pair universe | When fetcher lands (M6), include delisted/low-cap pairs; record universe snapshot + listing dates in the run header. |
| **Data quality / gaps** | Reuse `CandleLoader` OHLC-integrity validation; add gap detection to run header; reject instruments below min-candle threshold. |
| **Cost realism** | Forward-walk RR must net fees + slippage (reuse existing slippage convention); expectancy gate is on **net** RR, not gross. |
| **Regime non-stationarity** | OOS split is temporal (no shuffle); optionally mirror `StabilityChecker` 5-split to require positive edge in ≥3 chunks. |
| **Continuation-probability ambiguity** | Define precisely: `continuation_prob = P(reached_1r)` = fraction of signals whose MFE ≥ 1R before SL. Documented in `metrics.py`. |
| **Scope creep into the live system** | Hard rule: `src/research/` imports value objects + loaders only; never `engine_runner`, never writes `configs/production/*` or `promotion_log.jsonl`. Enforced by an import-lint test. |

---

## Verification

- **Unit (M1):** `pytest tests/research/test_forward_walk.py` — hand-constructed candle sequences with known TP/SL/timeout outcomes; assert `outcome`, `rr_achieved`, `mfe`, `mae`, `time_to_failure`, `reached_1r`. Include a lookahead-attempt case that must raise.
- **Determinism (M3):** run `python -m research.cli run --hypothesis expansion_breakout --data data/` twice; assert identical `edge_report.json` (byte-compare).
- **Falsification (M4):** `pytest tests/research/test_qualification.py` — (a) `random_baseline` on real CSVs must get `verdict=REJECT`; (b) a synthetic CSV with a *planted* continuation edge must get `verdict=PROMOTE`; (c) a 50-trade sample must get `INSUFFICIENT`.
- **End-to-end (M3–M5):** `python -m research.cli run --hypothesis expansion_breakout --data data/ --qualify` → produces `EdgeReport` + writes a verdict line to `results/research/edge_ledger.jsonl`; verify sha256 round-trip via `research.cli ledger --verify`.
- **Isolation:** a lint test asserting no `src/research/**` file imports `src.core.engine_runner`, `src.governance.promotion_manager`, or `src.config_layer.config_validator`.

Per CLAUDE.md §6, each implementation response appends a `📝 SESSION LOG ENTRY` to `assistant_project.md` (cannot do so now under plan mode).


================================================================================
SOURCE_FILE: docs/implementation_plan/erp-ic001-closure-and-ic-roadmap.md
SOURCE_BYTES: 14763
PART: 4/10 FILE 7/16
================================================================================

# Implementation Plan — IC-001 Closure + ERP Information-Class Roadmap

> **Status:** PLAN · **Phase 1 EXECUTED 2026-07-17** (IC-001 fence docs + test)  
> **Date:** 2026-07-17  
> **Authority:** Research / documentation / governance only (§6.5). **No** new engines, **no** threshold tuning, **no** production promote from this plan.  
> **Parents:** User handoff (IC taxonomy + Dual-Read Bar 78) · existing  
> [`docs/research-readiness/erp-information-class-boundary.md`](../research-readiness/erp-information-class-boundary.md) ·  
> XAUUSD descriptive enrichment · H-RR-THRESHOLD-001 (running / research-only) · RR contracts A/B/C/D wiring.

---

## 0. One-screen Orient

| Item | State |
|------|--------|
| **Chapter to close** | **IC-001** = Static entry-time OHLCV-derived information (XAUUSD certified corpus) |
| **Not closed** | “Entry research forever” — only this information class on this corpus |
| **Permanent teaching artifact** | Dual-Read Bar 78 (library #1 vs #4) |
| **Next research chapter** | **IC-002 / RC-005** Entry Evolution (post-entry trajectory) — OHLCV-only |
| **Hard guardrail** | No new engines · no threshold tuning · no re-analyzing IC-001 with a different model |
| **H-RR-THRESHOLD-001** | Orthogonal production R-threshold study (admission/exit knobs); **not** a reopening of IC-001 entry discrimination |

---

## 1. Canonical scientific statement (freeze this wording)

### 1.1 Measured boundary (authoritative)

> **Within Information Class IC-001 (static entry-time OHLCV-derived information), no practically useful outcome discrimination was observed on the certified XAUUSD corpus under the evaluated research conditions.**

### 1.2 Explicit non-claims

| Do **not** say | Correct |
|----------------|---------|
| “Entry research is dead forever” | IC-001 static entry math is **characterized** on this corpus |
| “Nothing beyond OHLCV can help” | Unmeasured classes remain **open**; not measured ≠ uninformative |
| “Order flow is required next” | Current ERP stays **OHLCV-centered** until that surface is exhausted |
| “AUC 0.51 is the main result” | Dual-read / agreement≠skill / path failure structure are the **teaching** results |

### 1.3 Independent attacks already on the record (IC-001 saturation)

| Attack | Artifact / surface |
|--------|-------------------|
| Static 38 features / distributions | `trace_corpus`, `DISTRIBUTIONS.md` |
| Engines + fusion + calibration | `ENGINE_EVALUATION.md`, `FAMILY_CALIBRATION.md` |
| Near-miss path structure | `NEAR_MISS_PROFILE.md` |
| Morphology clusters (F-023 class) | `geometry/CLUSTERS.md` |
| Representative library + dual-read | `REPRESENTATIVE_LIBRARY.md` (#1 vs #4) |
| Non-linear OOF (GBT) + **time-series CV** | `ROBUSTNESS_XVRP.md`, `TIME_SERIES_CV_X.md` |
| Continuous R + permutation | `ROBUSTNESS_XVRP.md` |
| Cross-asset entry null priors | F-019…F-042 (context; not XAU-only) |

**Verdict for plan:** IC-001 is **COMPLETE as a measured chapter** — documentation/archive work, not more static-entry models.

---

## 2. Taxonomy map (user IC-xxx ↔ existing RC-xxx)

Keep **both** IDs: user-facing **IC-*** for chapter language; machine **RC-*** already in the boundary JSON.

| User IC | Name | Maps to | Status after this plan | OHLCV-native? |
|---------|------|---------|------------------------|---------------|
| **IC-001** | Static Entry Mathematics | Measured boundary (no RC id) | **COMPLETE** (archive) | Yes |
| **IC-002** | Entry Evolution | **RC-005** Temporal Evolution | OPEN · **NEXT design** | Yes |
| **IC-003** | Trade Trajectory / Shape families | RC-005 extension + path geometry | OPEN (after IC-002) | Yes |
| **IC-004** | Cross-Instrument Generalization | *(new RC or IC-004 registry row)* | OPEN | Yes |
| **IC-005** | Execution Layer | **RC-007** Execution Effects | OPEN | Yes (policy); not microstructure |
| — | Higher-TF context | RC-006 | OPEN (later) | Yes |
| — | Order flow / macro / alt | RC-008…010 | OPEN · **data-gated** · not ERP focus now | No |

**OHLCV-first doctrine (user-aligned):**  
Research effort stays on  
`OHLCV → 38 features → trace → geometry → shape library → shape evolution → representative shapes → interpretation → prereg hypotheses`  
until that stack is exhausted. Order flow remains an honesty bound (“not measured”), not a pivot.

---

## 3. Permanent ERP teaching example — Dual-Read Bar 78

### 3.1 Facts (do not paraphrase away)

| | #1 | #4 |
|--|----|----|
| Trade ID | `expansion_breakout_000007` | `mean_reversion_000012` |
| Bar | **2024-05-22 20:30**, index **78**, price **2387.55** | **identical** |
| Features / engines | body 0.576 · CRT 0.45 · G 0.88 · Z 0.2 · RR 0.77 · Fusion 0.56 | **identical** |
| Direction / family | SHORT / expansion | LONG / mean_reversion |
| Outcome | **TP_HIT +2R** | **SL_HIT −1R** |

### 3.2 Lesson (one sentence)

> Entry-time mathematics restates candle morphology; it does **not** adjudicate direction/family forks on the same vector.

### 3.3 Implementation actions (documentation)

| # | Action | Deliverable |
|---|--------|-------------|
| T1 | Promote dual-read to a **named permanent example** | `docs/research-readiness/erp-teaching-dual-read-bar78.md` (1 page) |
| T2 | Cross-link from library, IC-001 closure, boundary doc | Links only |
| T3 | Ensure `representative_exemplars.jsonl` categories remain `typical_tp` + `dual_read` with tags `dual_read_bar_78` | Already mostly done (UX polish) |
| T4 | Optional: 1 slide-ready table in `REPRESENTATIVE_LIBRARY.md` “Teaching openers” section | Small MD edit |

---

## 4. Archive IC-001 (not “Entry Research”)

### 4.1 What “archive” means here

| Do | Don’t |
|----|-------|
| Mark IC-001 **COMPLETE** in boundary registry | Delete artifacts |
| Write a **closure chapter** with statement + attack matrix + links | Claim global entry null across all assets without IC-004 |
| Treat artifacts as a **conceptual fence** against re-work | Re-run XGBoost/LSTM on the same 38 static dims as “new research” |
| Keep H-RR-THRESHOLD-001 under **execution / config R** (RC-007-adjacent) | Fold H-RR into “IC-001 failed so change R to find edge” without prereg gates |

### 4.2 Deliverables

| # | Deliverable | Path (proposed) |
|---|-------------|-----------------|
| A1 | IC-001 closure chapter | `docs/research-readiness/ic-001-xauusd-static-entry-closure.md` |
| A2 | Update boundary MD+JSON | Add IC-001 COMPLETE; map IC-002…; dual-read pointer; list new attacks (GBT, TS-CV, near-miss, family cal) |
| A3 | Optional thin finding | F-xxx only if owner wants living-findings index row (research authority only) |
| A4 | Program tracker note | One row in edge-research-platform program if present |

### 4.3 Closure chapter outline (A1)

1. Canonical statement (§1.1)  
2. Corpus pin (path, n=23,447 / 23,428 scored, families)  
3. Attack matrix with artifact paths  
4. Dual-Read Bar 78  
5. Engine characterization table (CRT / G / Zone / RR / Fusion)  
6. What remains **forbidden** under IC-001  
7. Pointer to **IC-002** as next chapter  
8. Authority banner DESCRIPTIVE / RESEARCH_ONLY  

---

## 5. H-RR-THRESHOLD-001 — how it plugs in (running job)

### 5.1 Status at plan time

- Job: `scripts/research/h_rr_threshold_001.py`  
- Observed: still in harvest (~30+ min CPU, ~70k bars × 4 instruments × 2 families); no result artifacts yet  
- **When complete:** fold summary into RC-007 / config-governance evidence, **not** as IC-001 entry skill  

### 5.2 Interpretation rules (pre-committed)

| Outcome | Use |
|---------|-----|
| Arm B all E_oos &lt; 0 | Consistent with **F-025** — exit R is risk/cost, not alpha |
| Arm A admit_rate structure | Documents honest D-wiring (e.g. planned TP1 1.0 fails min_rr 1.5) |
| Any PROMOTE_RESEARCH | **Config proposal only** — human governance; not engine work |
| Runtime too long | Optional later: pin cached entries artifact to skip re-harvest (prereg-compatible if population unchanged) |

### 5.3 Plan step when results land

| # | Action |
|---|--------|
| H1 | Read `results/research/h_rr_threshold_001/REPORT.md` |
| H2 | Append 1 paragraph to IC-001 closure “Related but distinct: production R-threshold study” |
| H3 | If live reject spike + H-RR null → config hygiene only; if PROMOTE_RESEARCH → separate promote PR |

---

## 6. Implementation phases

### Phase 0 — Wait / capture H-RR (in flight)

| Step | Owner | Exit |
|------|-------|------|
| 0.1 | Let runner finish or kill+restart with progress logging | `REPORT.md` exists |
| 0.2 | Record program_verdict in SESSION LOG | Logged |

**Estimate:** remaining harvest-dominated; could be **~20–60+ min** total from start (already ~30+ min).

---

### Phase 1 — Documentation fence (IC-001 COMPLETE) — **no code engines**

| Step | Work | Est. |
|------|------|------|
| 1.1 | Write `ic-001-xauusd-static-entry-closure.md` | 0.5–1 h |
| 1.2 | Write `erp-teaching-dual-read-bar78.md` | 0.25 h |
| 1.3 | Update `erp-information-class-boundary.{md,json}`: IC aliases, COMPLETE IC-001, dual-read, attack list | 0.5 h |
| 1.4 | Library “Teaching openers” blurb + dual-read table | 0.25 h |
| 1.5 | SESSION LOG + optional F-id (owner call) | 0.25 h |

**Exit criteria:** A human/LLM reading only the closure + boundary docs cannot reasonably re-open “train another model on 38 static features for XAUUSD entry.”

**Guardrail sentence (paste into every future ERP prompt):**

> **Do not create new engines. Do not tune thresholds. Do not optimize features. Future work must introduce genuinely new information classes rather than re-analyzing IC-001.**

---

### Phase 2 — Design IC-002 / RC-005 only (pre-register, do not run until grant)

**Question:**  
How does the **mathematical state evolve** over the first **N** bars after entry (OHLCV-derived trajectory), and does that trajectory family separate outcomes better than the IC-001 snapshot?

| Step | Work | Est. |
|------|------|------|
| 2.1 | Define trajectory object: per-bar feature vector or reduced shape path for t=0…N | Design |
| 2.2 | Freeze N ∈ {4, 8, 16} (closed set — no free N search) | Design |
| 2.3 | Population: same frozen XAUUSD entries (or crypto majors if generalizing later) | Design |
| 2.4 | Controls: shuffled path, static snapshot-only, time-reversed path (diagnostic) | Design |
| 2.5 | Metrics: path-cluster purity vs outcome; OOS; **no** entry-score rehash | Design |
| 2.6 | Write `h-ic002-entry-evolution-preregistration.md` + JSON twin | 1–2 h |
| 2.7 | **STOP** until user says Run | — |

**Explicitly not IC-002:**

- New CRT states  
- rr_fusion enable  
- Feature formula changes  
- Same 38 dims at t=0 only with a new classifier  

**Data:** pure OHLCV + existing FeaturePipeline / causal rules — **no order flow.**

---

### Phase 3 — IC-003 Shape library (after IC-002 has a first measurement)

| Step | Work |
|------|------|
| 3.1 | Compress trajectories → canonical shapes (cluster / prototype paths) |
| 3.2 | Representative shape library (human + LLM), analogous to trade exemplars |
| 3.3 | Stories **only as documentation of shapes**, never as priors that invent shapes |
| 3.4 | Separate prereg before any expectancy claim |

---

### Phase 4 — IC-004 Cross-instrument (fence test)

| Step | Work |
|------|------|
| 4.1 | Replicate IC-001 **descriptive** battery on EURUSD / BTC / (optional NAS100) with same protocol |
| 4.2 | Ask: same null region vs different morphology |
| 4.3 | Does **not** require IC-002 success |

Can run **in parallel** with Phase 2 design if owner wants fence strength; still not “new engines.”

---

### Phase 5 — IC-005 / RC-007 Execution layer

| Step | Work |
|------|------|
| 5.1 | Incorporate H-RR-THRESHOLD-001 results as first R-admission/exit cell study |
| 5.2 | Optional later: path-aware exits **only** under new prereg (not near-miss post-hoc) |
| 5.3 | Keep separate from IC-001 entry skill claims |

---

## 7. Pipeline picture (target architecture)

```text
OHLCV
  → Canonical mathematics (38 features / ontology)
  → Mathematical Trace Corpus
  → Geometry / clusters          [IC-001: DONE on XAUUSD entry snapshot]
  → Shape evolution (paths)      [IC-002]
  → Shape library                [IC-003]
  → Representative shapes
  → LLM mathematical interpretation (descriptive)
  → Pre-registered hypotheses
  → ERP validation (M4 / OOS / costs) — authority ladder
```

Stories attach **after** shapes, not before.

---

## 8. Hard guardrails (non-negotiable for next coding LLM)

1. **No new engines** (no “EntryNet v3”, no re-enable rr_fusion without ΔG001 + F-044/F-045).  
2. **No threshold tuning** as research theater on IC-001.  
3. **No feature optimization** on the same static entry vector.  
4. **No claiming** order-flow necessity; also **no** claiming OHLCV is the only possible information in nature.  
5. **One IC at a time** for design+run (IC-002 next).  
6. **RR contracts stay split:** A polarity · B shadow · C no polarity-as-RR · D SL/TP true RR.  
7. Production config changes only via **governance promote**, never from descriptive AUC.

---

## 9. Work queue (recommended order)

| Priority | Item | Depends on |
|----------|------|------------|
| P0 | Finish or recover H-RR-THRESHOLD-001 results | Running job |
| P1 | Phase 1 docs (IC-001 closure + dual-read + boundary update) | None |
| P2 | Phase 2 IC-002 prereg only | P1 preferred |
| P3 | User grant → implement IC-002 measure pipeline | P2 |
| P4 | IC-003 / IC-004 as separate grants | P3 or parallel design |

---

## 10. Success criteria for *this plan*

| Criterion | Met when |
|-----------|----------|
| IC-001 fence | Closure doc + boundary say COMPLETE; dual-read is the default teaching opener |
| No IC-001 reopen | Future sessions cite guardrail sentence |
| Next chapter clear | IC-002 prereg exists before any trajectory code lands |
| H-RR integrated correctly | Results filed under execution/R-threshold, not “entry edge found” |
| OHLCV program intact | Roadmap does not pivot to order flow |

---

## 11. Immediate next user choices

| Say… | Effect |
|------|--------|
| **Execute Phase 1** | Write closure + dual-read + boundary updates now |
| **Continue waiting on H-RR** | Only monitor; fold when `REPORT.md` appears |
| **Kill H-RR / restart lean** | Progress logging + optional entry cache (if harvest too slow) |
| **Draft IC-002 prereg** | Phase 2 design only |
| **Implement IC-002** | Only after prereg frozen + explicit run grant |

---

## 12. Document control

| Version | Date | Note |
|---------|------|------|
| v1 | 2026-07-17 | Initial plan from user handoff + existing RC registry + live H-RR job |


================================================================================
SOURCE_FILE: docs/implementation_plan/erp-ic001-implementation-details.md
SOURCE_BYTES: 18411
PART: 4/10 FILE 8/16
================================================================================

# Implementation Details — IC-001 Closure + IC-002… Roadmap

> Companion to [`erp-ic001-closure-and-ic-roadmap.md`](erp-ic001-closure-and-ic-roadmap.md).  
> This file is the **how**: files, schemas, functions, gates, and order of work.  
> **Authority:** research/docs only unless a step explicitly says otherwise.  
> **Date:** 2026-07-17

---

## 0. Repository surfaces you will touch

| Layer | Path | Role |
|-------|------|------|
| IC boundary (living) | `docs/research-readiness/erp-information-class-boundary.{md,json}` | COMPLETE / OPEN registry |
| Plan | `docs/implementation_plan/erp-ic001-closure-and-ic-roadmap.md` | Strategy |
| **This file** | `docs/implementation_plan/erp-ic001-implementation-details.md` | Build steps |
| XAUUSD corpus | `results/research/trace_corpus/xauusd/` | IC-001 evidence (gitignored) |
| Feature math | `src/features/feature_pipeline.py` · `feature_schema.py` · registry | OHLCV → 38-dim |
| Path geometry | `src/research/measurement/forward_walk.py` · `exit_grid.py` | MFE/MAE / R paths |
| H-RR study | `scripts/research/h_rr_threshold_001.py` · prereg under `docs/research-readiness/` | R thresholds (≠ IC-001) |
| RR contracts | `decision_engine.py` · `live_engine_hook.py` · `rr_engine.py` | A/B/C/D already split |

**Do not touch for IC work:** production fusion weights, `rr_fusion.enabled`, CRT `VALID_TRANSITIONS`, new engines under `src/engines/`.

---

## Phase 1 — IC-001 documentation fence (no research runner)

### 1.1 New file: IC-001 closure chapter

**Create:** `docs/research-readiness/ic-001-xauusd-static-entry-closure.md`

**Required sections (copy structure):**

```markdown
# IC-001 — XAUUSD Static Entry Mathematics (CLOSED)

> DESCRIPTIVE / RESEARCH_ONLY · Information Class COMPLETE on this corpus

## Canonical statement
[exact wording from plan §1.1]

## Corpus pin
- instrument, path, n traces, n scored, families, date range
- pointer: results/research/trace_corpus/xauusd/

## Attack matrix
| Attack | Artifact | Result summary |

## Permanent teaching example
→ link dual-read doc

## Engine characterization table
CRT / Gaussian / Zone / RR / Fusion

## Forbidden re-openings
(list models on same 38 static dims)

## Next chapter
IC-002 / RC-005 only
```

**Attack matrix rows (fill from existing artifacts):**

| Attack | File(s) under `results/research/trace_corpus/xauusd/` |
|--------|------------------------------------------------------|
| Distributions | `DISTRIBUTIONS.md`, `distributions.json` |
| Engines | `ENGINE_EVALUATION.md` |
| Family cal | `FAMILY_CALIBRATION.md` |
| Near-miss | `NEAR_MISS_PROFILE.md`, `near_miss_profile.json` |
| Clusters | `geometry/CLUSTERS.md` |
| Library | `REPRESENTATIVE_LIBRARY.md`, `representative_exemplars.jsonl` |
| Robustness X/V/R/P | `ROBUSTNESS_XVRP.md` |
| Time-series CV | `TIME_SERIES_CV_X.md` |
| Enriched corpus | `trace_corpus_enriched.jsonl` |

**Acceptance:** a cold LLM session that reads only this file + boundary JSON will state IC-001 COMPLETE and refuse “train another classifier on entry features.”

---

### 1.2 New file: Dual-Read Bar 78 teaching card

**Create:** `docs/research-readiness/erp-teaching-dual-read-bar78.md`

**Content skeleton:**

```markdown
# ERP Teaching Example — Dual-Read Bar 78

## One-line lesson
Entry-time mathematics restates morphology; it does not adjudicate direction/family forks.

## Table
| | expansion_breakout_000007 | mean_reversion_000012 |
| trade_id, entry_index=78, timestamp, price, features, engines, direction, outcome |

## How to use
- Opening slide for IC-001
- LLM eval: "explain why engines cannot separate these"
- Regression: exemplar pair must remain in representative library

## Links
REPRESENTATIVE_LIBRARY.md #1 #4
representative_exemplars.jsonl categories typical_tp + dual_read
```

**Code check (no change required if already present):**

```text
representative_exemplars.jsonl
  trade_id == expansion_breakout_000007 → tags include dual_read_bar_78
  trade_id == mean_reversion_000012     → category == dual_read
```

**Optional test** `tests/research/test_erp_teaching_dual_read.py` (lightweight):

```python
def test_dual_read_bar78_pair_present():
    rows = load_exemplars()
    a = by_id(rows, "expansion_breakout_000007")
    b = by_id(rows, "mean_reversion_000012")
    assert a["entry_index"] == b["entry_index"] == 78
    assert a["outcome"] == "TP_HIT" and b["outcome"] == "SL_HIT"
    assert a["direction"] != b["direction"]
    # same engine vector within float tol
    for k in ("engine_crt_score", "engine_gaussian_score", "engine_zone_score", "engine_rr_score"):
        assert abs(a[k] - b[k]) < 1e-6
```

---

### 1.3 Update boundary registry (MD + JSON together)

**Edit:** `docs/research-readiness/erp-information-class-boundary.md`  
**Edit:** `docs/research-readiness/erp-information-class-boundary.json`

**JSON additions (conceptual patch):**

```json
{
  "measured_boundary": {
    "ic_id": "IC-001",
    "status": "COMPLETE",
    "statement": "Within Information Class IC-001 ...",
    "teaching_example": "docs/research-readiness/erp-teaching-dual-read-bar78.md",
    "closure_doc": "docs/research-readiness/ic-001-xauusd-static-entry-closure.md",
    "measured_surfaces": [
      "...existing...",
      "engine descriptive evaluation + family calibration",
      "near-miss SL path profile",
      "non-linear OOF (GBT) + time-series CV",
      "continuous R calibration + permutation tests",
      "representative library (incl. dual-read bar 78)"
    ]
  },
  "ic_alias_map": {
    "IC-001": "measured_boundary",
    "IC-002": "RC-005",
    "IC-003": "RC-005_extension_shape_library",
    "IC-004": "IC-004_cross_instrument",
    "IC-005": "RC-007"
  },
  "hard_guardrail": "Do not create new engines. Do not tune thresholds. Do not optimize features. Future work must introduce genuinely new information classes rather than re-analyzing IC-001.",
  "open_information_classes": [
    { "id": "RC-005", "ic_alias": "IC-002", "next": true, "...": "..." }
  ]
}
```

**MD:** mirror the same under “Measured boundary” + “IC alias map” + guardrail quote box.

---

### 1.4 Library UX (small)

**Edit:** `results/research/trace_corpus/xauusd/REPRESENTATIVE_LIBRARY.md` (gitignored — regenerate via script if preferred)

Add at top after “How to use”:

```markdown
## Teaching openers (start here)
1. Dual-Read Bar 78 — #1 vs #4 (same vector, opposite outcome)
2. High-agreement block — #10–#13 (agreement ≠ skill)
```

If library is only in `results/`, also mirror a **short** dual-read section into the teaching doc under `docs/` (docs are versioned; results may not be).

---

### 1.5 Phase 1 definition of done

- [ ] Closure MD exists with canonical statement  
- [ ] Dual-read teaching MD exists  
- [ ] Boundary MD+JSON: `IC-001` COMPLETE + aliases + guardrail  
- [ ] Optional dual-read regression test green  
- [ ] SESSION LOG entry  

**Still no:** new Python research pipeline for trajectories.

---

## Phase 2 — IC-002 Entry Evolution (design + implement later)

### 2.1 What is new (information class)

| IC-001 | IC-002 |
|--------|--------|
| One 38-vector at **entry bar** | Sequence of vectors / derived path over **bars after entry** |
| “Does snapshot rank outcome?” | “Does **trajectory shape** separate outcomes?” |

If you only re-score t=0 with XGBoost → **you reopened IC-001**. Reject that PR.

---

### 2.2 Data contract

#### Input population

Reuse frozen XAUUSD trade entries from enriched corpus:

```text
source: results/research/trace_corpus/xauusd/trace_corpus_enriched.jsonl
keys:   trade_id, family, direction, entry_index, entry_timestamp,
        outcome, rr_achieved, mfe, mae, duration_candles,
        feature_* (t=0 snapshot, optional baseline)
OHLCV:  data/mt5/XAUUSD_M15.csv  OR  data/XAUUSD_M15.csv (pin which exists)
```

**Pin at run:** sha256 of OHLCV + entry list in `results/research/ic_002/manifest.json`.

#### Trajectory object (proposed)

```python
@dataclass(frozen=True)
class EntryTrajectory:
    trade_id: str
    family: str
    direction: str          # long | short
    entry_index: int
    outcome: str
    rr_achieved: float
    N: int                  # horizon bars
    # shape (N, D) — D = len(TRAJECTORY_FEATURE_IDS)
    X: tuple[tuple[float, ...], ...]
    # path economics (from forward_walk or bar path)
    mfe_r_path: tuple[float, ...]   # optional length N
    mae_r_path: tuple[float, ...]
    # provenance
    feature_ids: tuple[str, ...]
    pit_ok: bool
```

#### Frozen horizons (closed set — from plan)

```text
N ∈ {4, 8, 16}   # bars after entry; no other N without new prereg
```

#### Feature subset for trajectories (closed set)

Do **not** dump all 38 if some are non-PIT or level-dominated. Pre-register a **morphology-first** subset, e.g.:

```text
TRAJECTORY_FEATURE_IDS = [
  body_ratio, disp_strength, retest_depth, rsi_14,
  atr, volatility_ratio, volume_ratio,
  trend_bias, momentum_score,  # if PIT-safe on causal pipeline
  # exclude absolute OHLC levels open/high/low/close unless z-scored path-relative
]
```

**Path-relative transform (recommended):**

```text
For each dim d at lag k=1..N:
  z[k,d] = (x[entry+k,d] - x[entry,d]) / scale_d
  # or pure delta; freeze one definition in prereg
```

Absolute price levels must not dominate clusters (same lesson as geometry.md).

---

### 2.3 Computation pipeline (modules)

**New package (suggested):**

```text
src/research/ic002_entry_evolution/
  __init__.py
  schema.py          # EntryTrajectory, TRAJECTORY_FEATURE_IDS, N_GRID
  build_trajectories.py
  cluster_paths.py
  evaluate_separation.py
  io.py              # jsonl read/write
```

**New script (thin CLI):**

```text
scripts/research/ic002_build_trajectories.py
scripts/research/ic002_evaluate.py
```

#### Algorithm: `build_trajectories`

```text
1. Load OHLCV → DataFrame with chronological index
2. FeaturePipeline(df).run() → enriched_df aligned to bar index
   # MUST be causal / PIT; same rules as production research
3. For each trade in enriched corpus with valid entry_index:
     if entry_index + N >= len(df): skip
     X = []
     for k in 1..N:
        row = enriched_df.iloc[entry_index + k]
        X.append([row[f] for f in TRAJECTORY_FEATURE_IDS])
     apply path-relative transform vs entry bar row
     attach outcome labels from corpus
4. Write results/research/ic_002/trajectories_N{N}.jsonl
   + trajectories_N{N}.npz (optional, for clustering)
```

**Performance note:** Do **not** call `FeaturePipeline` per trade. Run **once** per instrument series, then slice rows — same lesson as H-RR harvest slowness (70k × detect).

#### Algorithm: path economics (optional joint object)

Reuse existing:

```python
from research.measurement.forward_walk import forward_walk, horizon_excursion
from research.exit_grid import Entry, net_rr
```

For each trade, can attach `mfe_r`, `mae_r` paths without inventing new exit math.

#### Algorithm: `cluster_paths` (descriptive)

```text
Flatten X → vector length N*D
  or use DTW / PCA-then-kmeans (freeze one in prereg)
k ∈ {4, 6, 8} closed silhouette pick (like geometry k=4)
Report:
  - cluster size
  - outcome mix (SL/TP/TIMEOUT %)  # expect ~uniform if null
  - mean path of body_ratio / MFE under each cluster
```

#### Algorithm: `evaluate_separation` (gates)

Pre-register metrics **before** run:

| Metric | Null expectation |
|--------|------------------|
| Cluster outcome entropy vs global | ≈ global if no path info |
| AUC of “path embedding → TP” with **time-series OOF** | ≈ 0.50 |
| Δ vs IC-001 static baseline embedding | path must beat static if claiming new IC value |

**Static baseline control (mandatory):**  
For each trade, repeat the model using only **repeated t=0 vector** N times (or single snapshot). If path model ≈ static model → **no new information class value**.

---

### 2.4 IC-002 preregistration (before any measure)

**Create (before code lands):**

```text
docs/research-readiness/h-ic002-entry-evolution-preregistration.md
docs/research-readiness/h-ic002-entry-evolution-experiment-definition.json
```

**Must freeze:**

- N grid, feature ids, path-relative formula  
- clustering method + k set  
- OOS scheme (time-ordered)  
- static baseline control  
- verdict vocabulary: INSUFFICIENT / REJECT / RESEARCH_SUPPORTIVE / …  
- **STOP after one primary run**  
- Authority: RESEARCH_ONLY  

**Forbidden in same prereg:** trailing exits, engine reweight, full 38-level features without justification.

---

### 2.5 IC-002 definition of done (measurement)

- [ ] Prereg frozen  
- [ ] One-pass FeaturePipeline build  
- [ ] `trajectories_N*.jsonl` + manifest sha  
- [ ] Cluster report + static baseline comparison  
- [ ] Time-series OOF discrimination table  
- [ ] REPORT.md with authority banner  
- [ ] Boundary RC-005 status update (MEASURED / still OPEN if null)  

---

## Phase 3 — IC-003 Shape library (after IC-002)

### 3.1 Object

```text
Shape = prototype trajectory (centroid or medoid path)
ShapeLibrary = { shape_id → prototype, membership, outcome mix, exemplars }
```

### 3.2 Implementation sketch

```text
src/research/ic003_shapes/
  library.py       # build from IC-002 trajectories
  representatives.py
scripts/research/ic003_build_shape_library.py
results/research/ic_003/
  SHAPE_LIBRARY.md
  shapes.json
  representative_shapes.jsonl
```

### 3.3 Stories

```text
docs only: shape_id → human narrative
NEVER: narrative → invent shape or filter without prereg
```

---

## Phase 4 — IC-004 Cross-instrument

### 4.1 Minimal replication battery (descriptive)

For each instrument in closed set `{EURUSD, BTCUSDT, …}`:

| Step | Reuse |
|------|--------|
| Trace corpus build | same scripts as XAUUSD enrichment |
| Distributions + engines | same probes |
| Dual-read style check | same-bar opposite family if data allows |
| Closure sentence | per-instrument IC-001 status |

**Do not** require IC-002 first.  
**Do** keep separate artifact roots:

```text
results/research/trace_corpus/{instrument}/
```

---

## Phase 5 — IC-005 / H-RR integration

### 5.1 H-RR-THRESHOLD-001 (already coded)

| Piece | Location |
|-------|----------|
| Prereg | `docs/research-readiness/h-rr-threshold-001-*.md/json` |
| Runner | `scripts/research/h_rr_threshold_001.py` |
| Output | `results/research/h_rr_threshold_001/` |

**Known implementation issue:** harvest loops every bar with hypothesis `detect` — **very slow** on 70k×4×2.  

**Lean restart options (if killed):**

1. Progress prints after each instrument/family (already partially there — move print earlier).  
2. Cache entries to `entries.jsonl` after first harvest; skip detect on re-run.  
3. Optional: subsample instruments for smoke test (requires prereg amendment if not primary).

### 5.2 How to read results into ERP

```text
if Arm B all E_oos < 0:
    → consistent F-025; IC-005 "fixed R exit" not alpha on this entry stream
if Arm A admit_rate(min_rr=1.5) << 1:
    → documents D-wiring honesty (planned TP1 vs Ultron floor)
NEVER:
    → "IC-001 failed so we found edge by changing TP"
```

### 5.3 Production config path (only if PROMOTE_RESEARCH + human)

```text
configs/production/v2_multi_2026_04.json
  ultron_risk_gate.min_rr_ratio
  crt_engine.tp1_atr_multiplier*
→ rehash + promote_manager  (governance)
NOT research scripts writing ACTIVE_VERSION
```

---

## Phase 0 — H-RR job (ops detail)

| Check | Command / path |
|-------|----------------|
| Process alive? | Task PID from runner / `Get-Process python` |
| Log | session `terminal/call-…h_rr_threshold_001….log` |
| Done? | `Test-Path results/research/h_rr_threshold_001/REPORT.md` |
| If stuck &gt; 2h in harvest | Kill; add entry cache; re-run |

---

## Shared engineering rules (all IC phases)

### Performance

| Bad | Good |
|-----|------|
| FeaturePipeline per trade | One pipeline run per series |
| Hypothesis detect every bar without progress | Log every instrument/family; cache entries |
| Shuffle CV for claims | Time-ordered OOS / expanding window |

### PIT / no lookahead

- Trajectory features at bar `t` may only use data ≤ `t`  
- Centered swings: obey FC1-A / F-051 policy already in pipeline  
- `forward_walk` future slice starts at `entry_index+1` only  

### Tests to add (by phase)

| Phase | Test |
|-------|------|
| 1 | Dual-read pair present + opposite outcomes |
| 2 | Trajectory builder: length N; no NaN; entry_index+N in bounds; static baseline runs |
| 2 | PIT smoke: last bar of trajectory doesn’t use future close (unit with synthetic series) |
| 5 | H-RR grid equals prereg JSON (no CLI override) — already intended |

### Authority banners (every artifact)

```text
> DESCRIPTIVE / RESEARCH_ONLY — information not authority (§6.5)
> IC-00X — not a production promote
```

---

## Suggested execution order (concrete checklist)

```text
[ ] Phase 1.1  ic-001-xauusd-static-entry-closure.md
[ ] Phase 1.2  erp-teaching-dual-read-bar78.md
[ ] Phase 1.3  erp-information-class-boundary.md + .json
[ ] Phase 1.4  library teaching openers (docs-side at minimum)
[ ] Phase 1.5  optional test_erp_teaching_dual_read.py
[ ] Phase 0    H-RR REPORT.md appears → 1-paragraph fold into IC-001 related / IC-005
[ ] Phase 2.0  h-ic002-*-preregistration.md + json  (STOP for user Run grant)
[ ] Phase 2.1  src/research/ic002_entry_evolution/* + scripts
[ ] Phase 2.2  run once → results/research/ic_002/
[ ] Phase 3+   only after IC-002 measured
```

---

## What “implement IC-002” means in PRs (when granted)

| PR | Contents | Behavior change? |
|----|----------|------------------|
| PR-A | Prereg MD+JSON only | No |
| PR-B | `ic002_entry_evolution` package + build script + tests | No prod |
| PR-C | Evaluation script + REPORT (results gitignored) | No prod |
| PR-D | Boundary RC-005 status update | Docs only |

Never combine “new engine” with IC-002 PRs.

---

## Quick reference — canonical statement

> Within Information Class IC-001 (static entry-time OHLCV-derived information), no practically useful outcome discrimination was observed on the certified XAUUSD corpus under the evaluated research conditions.

## Quick reference — guardrail

> Do not create new engines. Do not tune thresholds. Do not optimize features. Future work must introduce genuinely new information classes rather than re-analyzing IC-001.


================================================================================
SOURCE_FILE: docs/implementation_plan/existing-data-sources-enumerated-feather.md
SOURCE_BYTES: 8504
PART: 4/10 FILE 9/16
================================================================================

# BNBUSDT Trade Anatomy — Measure-First (Existing-Data-First)

## Context

The user wants a **measurement-only** anatomy of BNBUSDT trades: frequency, MFE/MAE,
time-to-peak, hold-time expectancy, feature clusters (winners vs losers), failure modes, and a
materialized per-trade dataset. Explicit constraints: **do not optimize, do not tune, reuse
existing artifacts, only derive what is genuinely missing, and list recovered-vs-derived up front.**

This aligns with the repo's measure-only research doctrine and with standing findings
(F-019/020/021, `exit_model_adoption`, `session_sweep`): under intrabar + 12 bps costs BNBUSDT
shows no promotable edge. The job here is to **measure and report neutrally**, possibly
re-confirming those findings at finer grain — not to chase an edge.

Decisions locked with the user:
- **Population = Both grains.** Opportunities (~140k) own anatomy/clusters/time/MFE-MAE;
  governed spine (~13–15) owns real PnL/costs/scores. Each output answered at its best grain.
- **Cost basis = gross + net, headline net 12 bps.**

## What is RECOVERED from existing logs vs DERIVED (the mandate, stated first)

**Recovered (reused as-is — Priority 1):**
| Field | Source |
|---|---|
| timestamp, direction, entry, sl, tp | `logs/BNBUSDT/20260530_011521/opportunities.jsonl` (139,943 rows) |
| outcome, rr_achieved, duration_candles, **mfe, mae** | same |
| 38-dim feature vector (ema/atr/volume/body/momentum/regime/session/disp/retest…) | same (`features{}`) |
| realized PnL, costs (slippage/spread), `bitnet_score_at_entry`, session, exit_reason | `results/.../BNBUSDT_trades.csv` (governed spine, ~13–15 rows) |
| per-engine scores (gaussian/zone/rr/crt/fusion) | `logs/collector.jsonl` + `logs/archive/202605/BNBUSDT_fusion.jsonl` (join to spine grain only) |
| logged ENTRY/EXIT trades (~3,899) w/ pnl_rr_net, win | `logs/trade_lifecycle.jsonl` (secondary cross-check grain) |

**Derived (genuinely absent everywhere — Priority 2, from `data/BNBUSDT_M15.csv`, 70,081 bars):**
| Field | Method |
|---|---|
| `return_15/30/45/60/90m` (=1/2/3/4/6 M15 bars fwd) | close-delta from entry candle; gross + net 12 bps |
| `time_to_peak`, `time_to_bottom` | argmax/argmin favorable excursion bar within horizon |
| horizon excursion (mfe_r, reached_Nr, favorable_first, bars_to_first_1r) | **reuse** `horizon_excursion()` in `src/research/measurement/forward_walk.py` |
| fixed 15/30/45/60/90m exit expectancy | mark-to-close at each cap, gross + net 12 bps |
| `capture_ratio = realized_return / MFE` | recovered realized rr ÷ recovered mfe |

Nothing else is recomputed. opportunities.jsonl's own `mfe`/`mae` are trusted for realized values;
candle-walk is used ONLY for the horizon/time fields that no artifact stores.

## Deliverables

1. **`results/research/bnbusdt_trade_anatomy/trade_dataset_BNBUSDT.csv`** — one row per
   opportunity: timestamp, direction, entry, mfe, mae, time_to_peak, return_15/30/45/60/90m
   (gross+net), duration, outcome, regime, session, all 38 features, capture_ratio. Governed-trade
   columns (bitnet_score, costs, realized_pnl) joined where a spine trade matches by timestamp.
   *(pyarrow is absent → `.parquet` only emitted if user installs pyarrow; plan ships CSV as the
   guaranteed format and notes the one-line `pip install pyarrow` to add parquet.)*
2. **`docs/analysis/BNBUSDT_TRADE_ANATOMY_2026_06_13.md`** — point-in-time report (history lives
   in `docs/analysis/` per truth doctrine) answering all 9 outputs + the user's added sections,
   opening with the recovered-vs-derived table above and the honesty caveats.
3. CLAUDE.md mandates on execution: append `📝 SESSION LOG ENTRY` to `assistant_project.md`; if a
   durable belief lands (e.g. continuation decays by bar K), write a `project`/`feedback` memory
   file + index line, and add/flip a finding in `docs/current-findings.md` only if a prior
   conclusion is validated/overturned.

## Implementation

Single driver script: **`scripts/analysis/bnbusdt_trade_anatomy.py`** (thin analysis wrapper,
sibling of existing `scripts/analysis/generate_cli_matrix.py`; imports research primitives, writes
no production logic). Steps:

1. **Load candle index** from `data/BNBUSDT_M15.csv` → list of `Candle` + `timestamp→index` map.
2. **Stream opportunities.jsonl** (skip `run_header`); for each row build a `research.Signal`
   (`atr=|entry−sl|`, `sl_atr_mult=1.0`, `tp_atr_mult=|tp−entry|/atr`, `entry_index` via the map).
3. For each opportunity: recover mfe/mae/outcome/rr/features; **derive** return_Nm (gross+net),
   time_to_peak/bottom, and reuse `horizon_excursion()` for R-excursion/continuation primitives.
   No-lookahead is enforced by the primitive (raises on `bar.index ≤ entry_index`).
4. **Build dataframe** → write CSV (parquet if pyarrow present).
5. **Aggregations** (pandas/numpy/scipy):
   - *Frequency*: total + per day/week/month/year; split by hour/weekday/session/month/regime
     (opportunity grain) **and** governed-trade frequency (spine grain) — reported separately, never conflated.
   - *Time decay*: `P(return_Nm > 0)` for N∈{15,30,45,60,90}; time_to_peak median/mean/p90;
     median time_to_failure (survival of SL_HIT).
   - *Hold-time research*: expectancy (mean R) of fixed 15/30/45/60/90m exits, gross + net 12 bps;
     report which horizon maximizes net expectancy and where continuation edge decays.
   - *MFE capture efficiency*: capture_ratio distribution; "are winners peaking by 30–45m?", "does
     90m give back?", "what % of MFE is harvested?".
   - *Feature clusters (winners vs losers)*: standardize the listed features (ema_spread/slope,
     volume_ratio, atr/volatility_ratio, body_ratio, momentum_score, trend_strength, regime,
     session, disp_strength, retest_depth) → **sklearn KMeans** (sklearn 1.8 present) on the pooled
     set, then compare win-rate/expectancy per cluster (multivariate, not single-variable). Fallback
     to quantile cross-tabs only if a fit fails. Reuse `src/analytics/clustering.py` if its API fits;
     otherwise inline sklearn in the script.
6. **Cost model**: net = gross − 0.0012 round-trip (in price-fraction for return_Nm; in R as
   `0.0012·entry/risk_distance` for R metrics). Cost always reduces magnitude toward zero.

## The 9 required outputs (+ user additions) — all answered in the report

1 total trades · 2 avg monthly opportunity count · 3 avg MFE & MAE · 4 median time-to-peak ·
5 recommended holding duration (net-12bps expectancy max) · 6 top feature clusters ·
7 failure modes · 8 confidence level · 9 final recommendation. Plus: opportunity-frequency splits,
hold-time decay probabilities, MFE-capture efficiency, winners-vs-losers clusters, and the
materialized dataset.

## Honesty caveats baked into the report

- opportunities.jsonl is **unfiltered detection** (sampled ≈ 39,509 SL_HIT / 482 TP_HIT, fixed
  SL/TP touch, no costs) — **not** what the spine trades; opportunity frequency ≫ tradeable frequency.
- Engine/fusion scores exist only at the spine grain (~15 trades) → score-clusters are low-N and
  flagged as indicative only.
- Headline numbers are net 12 bps; gross shown alongside to expose where cost bites.
- Findings F-019/020/021 already establish no promotable BNBUSDT edge under intrabar+12bps; this
  measurement is reported as confirmation/anatomy, **not** a search for a lever. No tuning performed.

## Verification

- `python scripts/analysis/bnbusdt_trade_anatomy.py` runs clean; row count of CSV == non-header
  opportunity lines (139,942); no-lookahead assertion never trips.
- Spot-check: 3 random rows' return_Nm recomputed by hand from `data/BNBUSDT_M15.csv` match.
- mfe/mae columns equal the opportunities.jsonl source values (recovered, not recomputed).
- Sanity: P(return_Nm>0) monotonic-ish and capture_ratio ∈ plausible range; net < gross everywhere.
- Report opens with the recovered-vs-derived table and states confidence + final recommendation.

## Files

- **New:** `scripts/analysis/bnbusdt_trade_anatomy.py`,
  `results/research/bnbusdt_trade_anatomy/trade_dataset_BNBUSDT.csv`,
  `docs/analysis/BNBUSDT_TRADE_ANATOMY_2026_06_13.md`
- **Reused (read-only):** `src/research/measurement/forward_walk.py` (`horizon_excursion`),
  `src/research/contracts.py` (`Signal`/`Candle`), `src/analytics/clustering.py` (if API fits)
- **Appended:** `assistant_project.md` (session log); memory + `docs/current-findings.md` only if a
  durable belief is validated/overturned.


================================================================================
SOURCE_FILE: docs/implementation_plan/extract-xauusd-one-month-vast-newell.md
SOURCE_BYTES: 15663
PART: 4/10 FILE 10/16
================================================================================

# Visual CRT State Fidelity — engine states vs. what an independent observer sees on the chart

> **Prior work in this session (COMPLETE, shipped):** the XAUUSD one-month OHLC odds comparison —
> 100% M15 coverage, 99.15% agreement, 30/30 divergences on the daily-open bar, F-080's
> double-counted denominator corrected to 1,378/21. Artifacts: `reports/xauusd_month_tv_engine_odds.md`,
> `scripts/research/tv_engine_odds.py`. **That work is done and is not revisited here.**

## Context

The odds comparison tested whether *the same numbers* appear on both feeds. It cannot detect a state
machine that is internally consistent but semantically wrong — it feeds the engine its own rules
twice. This plan tests a different thing:

> **Does the deterministic engine's CRT classification correspond to what an independent observer
> can actually see on the TradingView chart?**

Three findings from exploration reshape the design, and the plan is built around them:

**1. "What state is this candle" has no answer.** CRT state is path-dependent.
`configs/formulas/market_crt_states.yaml`'s own header states that memory-requiring states *"cannot
be resolved from a single bar's feature vector alone"*, and F-069 is the empirical proof — a per-bar
predicate resolver reproduces the engine at **10.77% EXPANSION recall**. `process_candle`
(`crt_engine_v2.py:2859`) dispatches on `state.current_state`, so an identical bar is evaluated
against completely different predicates depending on the path. The comparison must therefore ask
about **events at a marked bar given visible context**, in trader language, never "label this candle."

**2. The dominant confound is already measured and it is large.** The engine's swept envelope is a
trailing 14/16-bar count-window extreme (`m15_structural_range.py::from_child_window`), rebuilt on
every reset — not a level anyone would draw. `reports/monthly_tv_vs_active_production_semantic_comparison.md`
already scored this month's 84 sweeps against chart-visible levels: **5 of 84** align tightly with a
production SMC level, **51 of 84 touch no SMC level at all**, 30/84 match a prior closed H4 high/low.
A bare-chart observer will therefore disagree with most sweeps for a *known structural reason*. The
two-arm design below exists specifically to separate that cause from genuine classification
disagreement; without it the experiment mostly re-measures something already known.

**3. Only ~23% of the month is legibly captured.** Pixels-per-candle is exactly `1743 / n_bars`.
Shots 04/07/08/14 are ≥8px; the four wide shots covering the rest are 3.2–5.6px and are unusable for
per-candle work *by design* (`shot_plan.json` says so three times). Cropping cannot rescue them —
a crop is a crop. Re-capture narrow.

**Authority:** research/docs only. Grants no production, economic, or promotion authority (§6.5).
Descriptive fidelity is Authority-Ladder *"information exists"* and nothing more.

---

## Decisions taken (confirmed with user)

- **Two arms**: bare chart AND the same bars with the engine's range level drawn (states never shown).
- **Event-anchored sample + blind controls** (controls are non-optional — without them only agreement
  on engine-positives is measurable, and events the engine *missed* are undetectable).
- **Fresh cold subagents classify; user adjudicates a random subsample** to establish a reliability ceiling.
- **Full pre-registration with sealed user predictions**, cloning `docs/research/preregistration-blind-label-descriptive-fidelity.md`.

---

## A pre-declared limit, stated before anything is built

The month contains **2 RETESTs and 6 EXPANSIONs**. Under the `< 15 minority-class instances →
INSUFFICIENT` rule those cells **cannot produce a result at any effort level**, and DISPLACEMENT
(n=19) is marginal. Only **SWEEP (n=84)** can carry a real number. This is a property of the corpus,
declared now so a thin cell cannot later be presented as a null (E-001: underpowered ≠ negative).
TradingView history exists only for this month, so extending n means a new capture campaign on a
different window — out of scope here.

---

## Phase A — Pre-registration (before any image is generated)

Write `docs/research/preregistration-visual-crt-state-fidelity.md`, cloning the structure and the
frozen "Order of operations" of the existing prereg. It must freeze:

**The four questions** — trader language, no thresholds, no CRT vocabulary. The existing prereg's
doctrine governs here: asking *"did the high exceed h_ref while the close came back below it"* would
make the labeler a slow computer and measure nothing. **No rule card with engine thresholds is given
to the classifier** — the definitional collision *is* the measurement.

| # | Question shown | Options | Scored against |
|---|---|---|---|
| V1 | At the marked bar, did price spike beyond a prior extreme and then close back inside? | Above / Below / Neither | engine `SWEEP` + direction |
| V2 | Is the marked bar a strong directional push away from that spike? | Up / Down / Neither | engine `DISPLACEMENT` + direction |
| V3 | Does the marked bar carry that push further in the same direction? | Yes / No | engine `EXPANSION` |
| V4 | Has price come back close to the level it originally broke? | Yes / No | engine `RETEST` |

Plus per item: **confidence** (HIGH/MEDIUM/LOW) and **free-text visible evidence** — the mismatch
dossier fields (body/wick structure, relation to previous candle, location within the drawn range).

**My predictions, in the clear** (falsifiable, recorded before any label exists):

| Cell | Prediction |
|---|---|
| V1 SWEEP, Arm 1 (bare) | κ ∈ [0.15, 0.35] — most swept levels are invisible |
| V1 SWEEP, Arm 2 (level drawn) | κ ≥ 0.65 |
| **V1 Arm2 − Arm1 delta** | **≥ +0.30** — the load-bearing prediction; this is the decomposition |
| V2 DISPLACEMENT | Arm 1 κ ∈ [0.30, 0.50]; Arm 2 κ ∈ [0.45, 0.65]; likely reported INSUFFICIENT at n=19 |
| V3 / V4 | INSUFFICIENT by construction (n=6, n=2) |
| Controls, Arm 1 | observers call a sweep on ≥20% of engine-silent bars — the false-negative channel |
| LLM-vs-human ceiling | κ ≥ 0.55, below the 0.75 the feature-level prereg predicted (states are harder) |

**Pre-registered interpretation** (fixed now):
- Arm 2 high, Arm 1 low, delta large → engine classification is faithful *given its own level*; the
  divergence from a chart reading is **level choice, not state logic**. Doc/finding about level
  visibility; **no engine defect**.
- Arm 2 **also** low → the state logic diverges from an observer given the *same* level. This is the
  only branch that would warrant a §6.8 semantic review.
- High observer-positive rate on controls → engine misses chart-visible sweeps. Information about
  **coverage**, not correctness.
- Ceiling < 0.5 on a question → that question is ambiguous for this classifier; **no conclusion about
  the engine** is drawn from it (guard against blaming the engine for a badly-posed question).
- Any cell < 15 minority instances → `INSUFFICIENT`, never a null.

Then: user writes `docs/research/visual-crt-user-predictions.SEALED.md`; I record its SHA-256 in the
prereg **before** any item is generated, and do not open it until scoring is complete.

## Phase B — Legible capture

Add a `month-legible` preset to `tools/tv_forensic/shot_plan.json`: ~19–24 M15 shots of **~150–160
bars each with ≥50-bar overlap**, tiling the full 2,116-bar corpus at ~11px/candle (proven legible —
shot 04 reads fine at 8.63). Overlap guarantees every item has a full 48-bar context window inside a
single shot.

Run as **one invocation** (`--preset month-legible`): `calibrate_clock` runs once per invocation
(`capture_tv.py:710`) and `bridge.setup` no-ops while symbol+interval are unchanged, so batched cost
is ~30–45s fixed + ~10s/shot ≈ **5–8 min**, versus 30–40 min as one-off invocations.

Two known hazards, both already documented in the tool: `frame_shot`'s two-sided assertion
(`capture_tv.py:213-225`) **aborts the whole run**, not one shot — and it has permanently defeated
`02_h4_july_setup`. Put every edge on a live-market bar (the shot-02 defect was an *edge* in a gap,
not an internal weekend). **Do not loosen the assertion**; narrow and split on refusal, and record it.

## Phase C — Item generation (blinded, seeded)

New `scripts/research/visual_state_sample.py`, modelled on `scripts/analysis/blind_label_sample.py`
(whose manifest-as-answer-key pattern and mechanically-tested blinding are the precedent to copy).

**Engine ground truth** — join on `timestamp`, **never** `candle_index` (bases differ by a constant
per-run offset; `crt_state_confusion_matrix.py::remap_event_indices_to_ohlcv:96` exists for exactly this):
- Events: `results/htfcrt_1month_parent_wired/run_20260816_011239_XAUUSD/XAUUSD_events.jsonl` (active
  config, parent-CRT wired; 84 SWEEP / 19 DISP / 6 EXP / 2 RETEST).
- Per-bar range level for Arm 2: `results/crt_survey_trace/20260815T062829Z/trace.jsonl`
  → `crt_inputs.active_range.h_ref / l_ref`.
- **Fail closed on a config mismatch.** These two artifacts come from different runs. Verify the state
  sequences agree on shared timestamps before using them together; if they disagree, re-run
  `scripts/analysis/xauusd_excel_feature_state_trace.py --csv data/XAUUSD_M15.csv` against the active
  config rather than reconciling by hand. The known 85-vs-84 sweep delta is explained (one sweep sits
  inside the 78-bar backtest warmup) and is not a mismatch.

**Sample**: all 111 engine transitions + ~111 controls drawn from `action == NONE` bars, **matched on
session and candle-range percentile** so controls are not trivially distinguishable from positives.
Seeded RNG, seed recorded in the manifest. Presentation order shuffled. Items carry **opaque hashed
filenames** (`item_a3f9c2.png`) with no timestamp or instrument in the name.

**Two renders per item**, from the same crop:
- **Arm 1** — bare crop, 48-bar context, marked bar indicated by a neutral tick outside the plot area.
- **Arm 2** — identical crop plus two **unlabelled, neutral-coloured horizontal lines** at `h_ref` /
  `l_ref`, drawn via `annotate.py`'s `Frame.y_of` (`:93-101`) off the sidecar `plot.price_calibration`.
  No vertical event markers, no state names, no direction-encoding colours.

Crop geometry from the sidecar: `bars[].x` for time→x, `plot.rect` for bounds — the same mapping
`annotate.py` consumes, so nothing new is derived.

`manifest.json` is the answer key and is **never referenced by any labeling surface**.

## Phase D — Classification

**Arm 1 and Arm 2 must be labelled by different cold subagents.** Reusing one agent across arms
anchors Arm 2 on Arm 1 and destroys the delta — which is the load-bearing measurement.

Each subagent receives **only** the image path and the frozen question text. It is instructed not to
read repo artifacts. **Disclose honestly:** unlike `blind_label_sample.py`, where the HTML
mechanically contains no answers, subagent blinding is **procedural, not mechanical** — a tool-using
agent could in principle look. Hashed filenames make accidental lookup much harder but do not
eliminate the hole. The user-adjudicated subsample *is* mechanically blind, which is part of why it matters.

Then: the user adjudicates a random ~30-item subsample → **LLM-vs-human ceiling**. Bulk numbers are
reported as a fraction of that ceiling, never at face value.

## Phase E — Scoring and report

New `scripts/research/visual_state_score.py`. **Reuse `build_confusion`**
(`scripts/research/crt_state_confusion_matrix.py:601`) — it is generic over two aligned label lists
plus `source_indices` and accepts a visual column verbatim; only a CSV loader shim is needed. Do not
reimplement the matrix.

Outputs: per-question Cohen's κ (linear-weighted where ordinal) per arm; the **Arm2−Arm1 delta**;
per-state recall/precision; control false-positive rate; κ reported both pooled and split on an
`overlaps_prior_item` flag (event-anchored items cluster, so context windows overlap and answers are
not fully independent — mirroring how the existing prereg splits Q4 on off-screen references); and a
**mismatch dossier** per disagreement in the format you specified (engine / visual / OHLC-match /
confidence / visible evidence).

Report to `reports/xauusd_visual_crt_state_fidelity.md`. Every conclusion records
`engine_state`, `visual_state`, `visual_confidence`, `visual_evidence` — **never** a column called
`TradingView_state`, because TradingView declares no state.

## Phase F — Governance

1. `BUILD_IMPACT_MANIFEST` → `docs/governance/build_manifests/CH-visual-crt-state-fidelity.impact.json`, `OBSERVATION_ONLY`.
2. `tests/test_visual_state_harness.py`: blinding (no answer reachable from any labeling surface),
   determinism under seed, and a scorer that **distinguishes perfect from random labels**. Each floor
   must be mutation-verified to fail against a leaky manifest or a degenerate scorer.
3. SITS-register both new scripts (`script_census --write-stubs` → overlay in `seed_script_registry.py`
   → `seed` → `generate_script_matrix`).
4. Open the sealed prediction file, re-verify its SHA-256 against the recorded value.
5. Findings decision is **gated** (§6.2): bring results before editing any finding. The default is
   *no new F-id* — a clean measurement is not a discovery.
6. SESSION LOG entry in `assistant_project.md`.

**Governance ceiling, stated up front:** anything read off pixels is a **VISUAL** claim under the
`smc_visual_verification.py:19-30` split — *"never self-certifies; renders the evidence and stops."*
The headline verdict will be `RENDERED_PENDING_HUMAN_ADJUDICATION`, bounded by the measured ceiling.
F-079 is the standing warning: a skipped measurement and an absent one must never look identical.

---

## Verification

```bash
python tools/tv_forensic/capture_tv.py --preset month-legible
```

```bash
python -m pytest tests/test_visual_state_harness.py tests/test_tv_forensic_smoke.py -q
```

```bash
python scripts/research/visual_state_sample.py --seed 20260818 --out-dir results/visual_crt_state_fidelity
```

```bash
python scripts/research/visual_state_score.py --labels results/visual_crt_state_fidelity/labels --out reports/xauusd_visual_crt_state_fidelity.md
```

Pass conditions, each named:
- **Legibility**: every generated item ≥ 8 px/candle; assert at generation, fail closed below it.
- **Blinding**: no item filename, image, or labeling instruction contains a timestamp, price, state
  name, or engine field; test asserts this over the whole generated set.
- **Determinism**: same seed reproduces the item set byte-identically.
- **Ground-truth join**: 100% of items resolve to an engine record by timestamp; zero index-based joins.
- **Config consistency**: events and trace artifacts agree on state at every shared timestamp, or the run aborts.
- **Control balance**: controls and positives statistically indistinguishable on candle-range percentile
  and session (report the balance check, don't assert a p-value).
- **Scorer sanity**: perfect labels → κ = 1.0; shuffled labels → κ ≈ 0.
- **Arm independence**: Arm 1 and Arm 2 label files come from different agent invocations (recorded in the manifest).

## Out of scope

No engine, config, or model change. No re-fetch of the corpus. No promotion, retrain, or CRT
re-closure. This measures **descriptive fidelity** — whether the engine's labels match what is
visible — and says nothing about predictive or economic value; F-019…F-043 answered that separately
and this cannot revise them.


================================================================================
SOURCE_FILE: docs/implementation_plan/f-041-recursive-catmull.md
SOURCE_BYTES: 10804
PART: 4/10 FILE 11/16
================================================================================

# F-041 — Close the ZoneGate finding (Phase-5 label verdict → manifest reconciliation)

## Context

F-041 (GOV, **OPEN**, Certain) records two facts that must not be conflated:

1. **CERTAIN (bookkeeping):** the runtime hard gate scores through `models/zone_registry.json`
   (8 gaussian zones, sha `e73e0893`), loaded directly from `engine_runner.zone_registry_path`.
   The version manifest `models/zone_gate_registry.json` has `active:true` → a *different*,
   pre-conversion file (`models/BNBUSDT/bnbusdt_training_20260524/zone_registry_BNBUSDT_202605_bnb_v1.json`,
   sha `aade29c4`) that nothing at runtime loads → an unreconciled §6.2 TruthConflict.
2. **OBSERVATION (pending Phase-5):** stored zone labels are ~98% SL-hit / 6-of-8 negative
   `mean_rr`. Whether that reflects **honest intrabar_fixed outcomes** or a **labeling artifact**
   is the explicit **Phase-5 Go/No-Go gate** — *not yet asserted*.

Two mechanisms found during exploration make both halves tractable:

- **Label provenance:** `scripts/research/discover_zones.py:129-130` reads `rr_achieved`/`outcome`
  straight from `opportunities_*.jsonl` — the exact stream **F-022** found only 36.8%
  self-consistent (SL_HIT stamped on paths that never touch the stop). So the stored labels
  inherit F-022 contamination *by construction*. Phase-5 is therefore a re-derivation test.
- **Manifest divergence cause:** the runtime file is `source=discover_zones_v1_converted_to_gaussian`
  — a zone_v1→v2_gaussian **conversion** wrote `models/zone_registry.json` directly and bypassed
  `register_zone_gate`/`promote_zone_gate`, so the manifest's `active` was never updated. The
  manifest is *stale*, not *authoritative* — runtime truth (§4.0 Tier-0 config) wins.

**Runtime caveat that scopes the verdict (do not overclaim):** the live gate is **purely
geometric** — `zone_gate_engine.py` scores weighted-Gaussian distance to zone centroids and
**never reads** `sl_hit_rate`/`mean_rr`/`tp_hit_rate` (sidecar metadata only). F-036 already
proved ZoneGate is `NON_PIVOTAL` (ΔG001≡0). So Phase-5 cannot claim labels "gate badly"; it can
only establish whether (a) the stored labels are honest, and (b) the zone *geometry* separates
honest expectancy at all. Authority: **research/docs + governance-hygiene only** (§6.5); no
architectural change rides on this.

**Intended outcome:** produce the deferred Phase-5 verdict with honest evidence, then reconcile
the stale manifest to runtime truth — moving F-041 from OPEN to a resolved/closed state (or a
sharpened OPEN if the evidence surprises us).

---

## Part A — Phase-5 label verification (research; run first)

**Goal:** decide the Go/No-Go — are the stored zone labels honest, and does zone geometry
separate honest expectancy?

**New reusable logic** — `src/research/zone_label_audit.py`:
- `assign_zone(vector_38, registry) -> zone_id` — assign each opportunity to a zone using the
  **runtime** geometry (max weighted-Gaussian score via the existing
  `src/bitnet/zone_cosine_searcher.py::compute_gaussian_score`, i.e. nearest active centroid),
  NOT the 35-dim raw KMeans. This guarantees the audit partitions members the way the live gate
  actually sees them.
- `honest_outcome(opportunity, candles) -> Outcome` — build a `research.contracts.Signal`
  (entry/atr/direction/entry_index from the opportunity record) and call the **unchanged**
  `src/research/measurement/forward_walk.py::forward_walk(..., exit_model="intrabar_fixed")` —
  the governing exit truth. Reuse the entry/ATR/direction extraction already proven in
  `scripts/analysis/bnbusdt_trade_anatomy.py` (F-022/F-024 re-derivation).
- `audit_zones(...) -> report` — per zone: `n`, stored `(sl_hit_rate, mean_rr)` vs **honest**
  `(sl_hit_rate, mean_rr)` re-derived under intrabar_fixed, the delta, and a
  sufficiency/consistency flag (reuse the `SufficiencyLevel`/`min_n=30` discipline from the
  metrics-oracle / insight-report pattern — below `min_n` makes **no** expectancy claim).

**Thin driver** — `scripts/research/zone_label_audit.py` (argparse wrapper only, per §3.3; no
business logic in the script):
- Inputs: `--registry models/zone_registry.json`,
  `--opportunities logs/BNBUSDT/bnbusdt_training_20260524/opportunities.jsonl`,
  `--candles data/BNBUSDT_M15.csv` (the source run that built the zones — both confirmed on disk).
- Emits a deterministic JSON/markdown report under `docs/analysis/` (point-in-time study, not a
  living doc) + prints the verdict.

**Verdict logic (pre-registered before running — E-001):**
- **CONTAMINATED_LABELS** — stored `sl_hit_rate` ≫ honest `sl_hit_rate` (F-022 artifact
  confirmed): the "~98% SL-hit" was a stream artifact, not honest exit truth.
- **HONEST_LABELS** — stored ≈ honest: the zones genuinely sit in loss-dominated territory.
- **Cross-cut (the real Go/No-Go):** on **honest** relabels, does any well-powered zone (n≥30)
  clear `E>0` under intrabar_fixed+12bps? Expected NO (consistent with F-036 NON_PIVOTAL, F-023
  morphology≠expectancy, and the F-019…F-040 entry-null) → **label-quality is NOT the dominant
  ZoneGate defect; the entry-information null is.** If a zone *does* clear E>0, that is a rare
  candidate → route to the M4 `QualificationGate`, do **not** promote here (§6.5 Authority Ladder).

**E-001 pre-registration guards (must pass before registering any finding):**
1. Artifact for every claim = `file:line` in the emitted report.
2. INSUFFICIENT (n<30) zones make no expectancy claim (zone_5 n=172, zone_6 n=1,162 are the
   small ones — flag, don't infer).
3. Statistical ≠ economic (Authority-Ladder L1 vs L2): a label-honesty delta is L1 information,
   never "edge."
4. Phrase the verdict only after seeing raw honest counts.

---

## Part B — Manifest reconciliation (governance-hygiene; gated on Part A + user approval)

The manifest is stale bookkeeping; runtime config is Tier-0 truth (§4.0). Reconcile the manifest
**to** runtime, not vice-versa. Options, to present to the user with Part A's verdict:

- **B1 (recommended):** register the converted runtime file as a proper version and promote it,
  so `zone_gate_registry.json.active` → `models/zone_registry.json` (sha `e73e0893`) — the file
  that actually loads. Use the existing `core.model_registry::register_zone_gate` /
  `promote_zone_gate` (the same API `discover_zones.py` calls) so the conversion step no longer
  bypasses registration. Adds a manifest entry; no runtime behavior change (config already loads
  this file), hash-neutral for the production config.
- **B2 (fallback):** add an explicit `note`/advisory marker on the manifest stating it is not the
  runtime source (runtime is config-driven), leaving the surfaced conflict documented.

**Gate (§6.2 DDP):** editing `models/` governance artifacts requires **user approval** — do not
auto-apply. Present B1 vs B2 with the verdict; the user picks.

---

## Documentation / findings sync (same-turn obligations, §6.2)

- **`docs/current-findings.md` F-041** — set the Phase-5 result: fill `Validated`/`Revalidate-by`,
  cite honest-relabel `Evidence`, and if the verdict confirms "labels contaminated + geometry
  doesn't separate honest expectancy," record it as resolving the OBSERVATION half and (post-B)
  the bookkeeping half → move toward closure. **Never delete**; supersede in place.
- **`CLAUDE.md` Repository Truths Index** — the F-041 row must stay in sync
  (`tests/test_current_findings.py` enforces both directions).
- **`docs/topics/model-intent-and-feature-ownership.md`** — update the ZoneGate row
  (line ~125) and the Challenges/Ambiguities Discussion entries (lines 163-165) with the verdict;
  bump `Updated:` (Topic Sync Mandate §6.4, `tests/test_topic_docs.py`).
- **`active_models.yaml`** ZoneGate `evidence.conflicts` — reflect F-041 resolution
  (`tests/test_active_models_registry.py`).

---

## Critical files

| Role | Path |
|---|---|
| Reuse — exit truth | `src/research/measurement/forward_walk.py` (`forward_walk`, `exit_model="intrabar_fixed"`) — **unchanged** |
| Reuse — zone geometry | `src/bitnet/zone_cosine_searcher.py::compute_gaussian_score` |
| Reuse — re-derivation pattern | `scripts/analysis/bnbusdt_trade_anatomy.py` (F-022/F-024) |
| Reuse — sufficiency gating | metrics-oracle / insight-report `SufficiencyLevel` (min_n=30) |
| New — audit logic | `src/research/zone_label_audit.py` |
| New — thin driver | `scripts/research/zone_label_audit.py` |
| New — tests | `tests/test_zone_label_audit.py` |
| Registry API (Part B) | `src/core/model_registry.py` (`register_zone_gate`/`promote_zone_gate`) |
| Runtime zone data | `models/zone_registry.json` (read-only in Part A) |
| Manifest (Part B, gated) | `models/zone_gate_registry.json` |

---

## Verification

1. **Determinism:** run the driver twice on the fixed source JSONL + candles → byte-identical
   report (KMeans assignment is seeded; forward_walk is deterministic). This is the research
   equivalent of the parity gate.
2. **No-lookahead:** `forward_walk` already asserts every future bar `.index >
   signal.entry_index` (raises otherwise) — inherited for free; add one test that a leaked bar
   raises.
3. **Unit tests** (`tests/test_zone_label_audit.py`): (a) `assign_zone` picks the max-Gaussian
   zone on a synthetic 3-zone registry; (b) honest relabel of a hand-built SL-first path returns
   `SL_HIT`; (c) a sub-`min_n` zone yields `expectancy=None` (no claim); (d) report schema
   stable.
4. **Sanity cross-check:** honest zone-0 (n=20,708) SL-hit rate should land near the F-022-implied
   *true* rate, materially below the stored 0.9865 if CONTAMINATED — the headline number of the
   verdict.
5. **Doc floors:** `pytest tests/test_current_findings.py tests/test_topic_docs.py
   tests/test_active_models_registry.py` green after the sync edits.
6. **SESSION LOG** (§6/§7.4) appended to `assistant_project.md` with the Belief/ROI/Goal line.

---

## Risks / guards

- **Over-claiming that labels "break" the gate** — they don't; the gate is geometric and F-036
  NON_PIVOTAL. Keep the verdict scoped to label-honesty + geometry-separation. (E-001 guard 3.)
- **35-dim vs 38-dim mismatch** — `discover_zones` KMeans is 35-dim; the runtime file is 38-dim
  gaussian. Assign via the 38-dim runtime geometry (`compute_gaussian_score`) so the audit matches
  what the live gate sees; do not re-cluster.
- **Data drift** — the audit is scoped to the *exact* source run
  (`bnbusdt_training_20260524`); a different opportunities file would not reproduce the stored
  zones. Preflight-assert the run_id in the JSONL `run_header` matches the manifest path.
- **Part B is user-gated** — no `models/` edit or finding downgrade without approval (§6.2 DDP).


================================================================================
SOURCE_FILE: docs/implementation_plan/feature-layer-tracking-2026-07-19.md
SOURCE_BYTES: 75315
PART: 4/10 FILE 12/16
================================================================================

# Feature Layer — Working Tracker (opened 2026-07-19)

> ### FREEZE (2026-07-20) — queue closed for free-form work
>
> **`FEATURE_LAYER_MUTATION_FREEZE = ACTIVE`**  
> Policy: [`docs/governance/feature-layer-mutation-freeze-2026-07-20.md`](../governance/feature-layer-mutation-freeze-2026-07-20.md)  
> Pin + vector regression: [`docs/governance/feature-layer-freeze-pin-2026-07-20.json`](../governance/feature-layer-freeze-pin-2026-07-20.json)  
> Floor: `tests/test_feature_layer_freeze.py`  
> **Engineering focus shifted to:**
> [`backtest-runtime-roadmap-2026-07-20.md`](backtest-runtime-roadmap-2026-07-20.md)
>
> Do **not** start a parallel feature tracker. Residual items proceed only as
> **accepted future programs** listed in the freeze pin (M16 consumer phase, T-5/T-6,
> T-11 feeder handshake, T-17/18/19, stateful-6, superseded-vector migration with plan).

**Purpose:** one list, worked one item at a time, no drift. Opened at user request after the
2026-07-18/19 feature-governance session. Update this file as items close; do not start a new
tracker.

**Scope note:** this file is a *working queue*. It does not grant authority. Economic/activation
claims still require the CLAUDE.md Section 6.5 Authority Ladder. **As of 2026-07-20 the queue
is FROZEN** except accepted future programs — see banner above.

---

## 0. CORRECTION FIRST — two things I reported earlier were wrong

### C-1. "MACD is deferred to a named B2/B3 review" — WRONG, based on a stale comment

`configs/formulas/market_ontology.yaml:442` says *"Full FM-id registration + parity wiring is a
separate architectural review (deferred, B2/B3)."* **That comment is stale.** MACD was
certified and promoted by the *successor* programme without ever going through B2/B3:
`docs/governance/feature_completion_alignment_census-2026-07-14.json:45-47` lists `macd_line`,
`macd_signal`, `macd_hist` as `PROMOTED_PRODUCTION`, `D2_FORMULA: PASS`,
`D9_PRODUCTION_BINDING: BOUND_CANONICAL_VECTOR` (indices 16/17/18).

What actually remains for MACD is **only ontology registration debt** — tracked as
`M16-WU-ONTOLOGY-REGISTRATION` (Priority 7), `BLOCKS_ACTIVATION: false`. Not a review, not a
gate. **Fixing the stale ontology comment is itself a tracked item (T-9 below).**

### C-2. The "B0/B1/B2A/B2B/B3" ladder was ABANDONED mid-way, not paused

| Phase | Real status | Evidence |
|---|---|---|
| B0/B1 | **COMPLETE** — identity governance only, `PRODUCTION_BEHAVIOR_CHANGED=NO` | ontology v1.2, `tests/test_b0b1_feature_semantic_migration.py` 14 green |
| B2A | **COMPLETE — verdict PROMOTE** (eligibility only; *"activation authority NONE"*) | F-053; `docs/governance/b2a_feature_candidate_certification-2026-07-12.{json,md}` |
| B2B | **FROZEN / KILLED** — superseded | `docs/current-findings.md:765-768`: *"bottom-up certification replaces the B2B-first direction"* (F-054) |
| B2 activation | **NOT STARTED** — reframed as **"L6 ACTIVATION"** | `docs/current-findings.md:763` |
| B3 | **Never run as B3.** Its ATR/RSI boundary-freeze half executed inside F-054 (freeze lifted, FM-040..046); its volume/session/liquidity half absorbed into L1–L4 DAG certification | |

So: **do not plan work in B-phase terms.** The live programme is the L0–L6 DAG certification
(F-054) and its remediation frontier (below). Phase letters are used inconsistently across docs
— "B2" and "B2B" are interchanged in places, and B0 is never defined separately from B1.

---

## 1. The authoritative frontier ALREADY EXISTS — do not invent a parallel list

`docs/governance/feature_completion_alignment_census-2026-07-14.json:3127-3348` defines **8
prioritized work units** (`M16-WU-*`). Identity certification is **exhausted** (48 DAG nodes:
46 PROMOTED_PRODUCTION, 2 SUPERSEDED, 0 READY, 0 BLOCKED):

```
FEATURE_IDENTITY_FRONTIER_EXHAUSTED:   YES
FEATURE_COMPLETION_FRONTIER_EXHAUSTED: NO
FEATURE_PROGRAM_CLOSED:                NO
NEXT_AUTHORIZED_ACTION:                STOP     <- pending user adjudication
```

| P | Work unit | Blocks activation? |
|---|---|---|
| 1 | `M16-WU-SESSION-ENCODING` — canonical session int8 0/1/2 permuted vs `SESSION_MAP`/dashboard | **yes** |
| 2 | `M16-WU-TREND-STRENGTH-COLLISION` — `dual_engine` local `trend_strength = abs(ema_spread)` != canonical | **yes** |
| 3 | `M16-WU-VOLREGIME-S05` — `s05_grid` reads string `TRENDING`, canonical is int8 tercile | **yes** |
| 4 | `M16-WU-SUPERSEDED-VECTOR-MIGRATION` — FM-030/031 certified but UNBOUND; vector still emits superseded legacy dims | **yes** |
| 5 | `M16-WU-FM025-PROVENANCE` — FM-025 certified with empty SHA | **yes** |
| 6 | `M16-WU-EMPTY-SHA-FAMILY` — 26 features with empty/placeholder SHA | no |
| 7 | `M16-WU-ONTOLOGY-REGISTRATION` — MACD family + L3/L4 FM registration (see C-1) | no |
| 8 | `M16-WU-L6-PREP` — activation readiness | **yes** |

**Note P1/P2/P3 are consumer-alignment defects** — the canonical feature and its *consumer*
disagree on encoding. These are live correctness issues, higher priority than any registration
work.

---

## 2. This session's items, merged in

| ID | Item | State |
|---|---|---|
| **T-1** | Config-driven indicator periods (11 keys) + Section 6.5 scoped exception | **DONE** — parity-proven byte-identical |
| **T-2** | `feature_pipeline.py` docstrings 32 -> 38 (4 sites) | **DONE** |
| **T-3** | `ma_200` restore + `ma_periods: [20,50,200]` | **DONE 2026-07-19** — verified drop still 78, vector unchanged |
| **T-4** | `lookback` / `config_key` duplicate source-of-truth (grew 4 -> 9 entries) | **DONE 2026-07-19** — enforced by `tests/test_ontology_config_parity.py`; see section 16 |
| **T-5** | `_warmup_budget = 300` over-sized vs measured 78 | **OPEN** (deferred by user) — see SF-006. Note its original arithmetic was never load-bearing (ma_200 is not canonical) |
| **T-6** | `finalize()` survivorship guard is advisory-only (logs, never raises) | **OPEN** (deferred by user) — SF-006 |
| **T-7** | `causal_structure.py` `_DOUBLE_SWEEP_WINDOW_DEFAULT = 5` was an independent copy of the batch `window` (while `SWING_WINDOW` IS shared by import) | **DONE 2026-07-19** — added `feature_pipeline.resolve_double_sweep_window()` as the single source; both public `causal_structure` fns default to `None`-means-config (explicit arg still wins); the literal default is deleted. Divergence proof: batch == live at windows {3,5,8}, and the value FLIPS 0->1 at 8 (knob is live, not inert). Sub-gap found+fixed: `FeatureStore._liquidity_sweep_history` was `maxlen=10`, which would have truncated any window >10 — now `max(10, window)`, byte-identical today |
| **T-8** | `feature_builder.py:45-46` `config.get("ema_fast_period", 9)` / `("ema_slow_period", 21)` — same values as T-1 under different key names with soft defaults | **DONE 2026-07-20** — dead attrs removed; period authority = `feature_pipeline.ema_*_span` only |
| **T-9** | Stale ontology comment `market_ontology.yaml` indicator_identities ("deferred, B2/B3") — see C-1 | **DONE 2026-07-20** — SUPERSEDED comment + MACD FM-047/048/049 registration status recorded |
| **T-10** | `behavior_census` could not see the feature layer (dir excluded AND function-body constants never collected) | **DONE 2026-07-19** — both gaps closed additively; see section 18 |
| **T-11** | Live ingress substituted silent defaults for missing feeder fields | **DONE 2026-07-19 (fallbacks)** — all silent defaults removed, fail-closed; see section 19. **Period-symmetry vs the external feeder remains OPEN** (needs the version handshake) |
| **T-12** | XAUUSD 2-month backtest | **RAN 2026-07-19** — see §13 (`run_20260719_021925_XAUUSD`, 0 trades: all candidates off-session). Original blocker (L2 gate rejects `results/` location) resolved by exporting to `data/`. Closable on review. (This cell previously read "never ran / PAUSED" — reconciled 2026-07-19 per §6.2 against the §13 run record and the `:1121` status line.) |

Detail for T-4..T-11 lives in
`docs/analysis/session-findings-2026-07-18-xauusd-window-and-feature-governance.md` (SF-001..007).

---

## 3. User decisions recorded (do not re-litigate)

- **Stateful detection (6 features)** — `double_sweep`, `sweep_detected`, `liquidity_sweep`,
  `break_of_structure`, `higher_high`, `lower_low`: **EXCLUDED for now**, revisit in a future
  phase once the feature pipeline is stable. (Consistent with the ontology's own standing
  boundary: *"Stateful detection state-machines (BOS/CHOCH/pivot) remain out of this layer"* —
  these were certified LEDGER-ONLY with no ontology/registry edit.)
- **`ma_200`** — restored (T-3), not left deleted.
- **Warmup guard** (T-5/T-6) — deferred, recorded as findings, not implemented.
- **Other instruments** (DOGE/XRP data-precision observation) — out of scope; data may be stale.
- **MT5 integration** — parked for future paper-trade / automation phases.
- **Consumer-alignment defects (M16 P1/P2/P3)** — `M16-WU-SESSION-ENCODING`,
  `M16-WU-TREND-STRENGTH-COLLISION`, `M16-WU-VOLREGIME-S05`: **DEFERRED to the future phase that
  works on `live_engine_hook`** (user decision 2026-07-19). They remain live correctness bugs and
  all three still carry `BLOCKS_ACTIVATION: true` — deferring them defers activation, which is
  the accepted trade.

---

## 4. Answer to the standing question: does "16/38 mapped" gate configurability?

**No — these are two different axes, and conflating them would misdirect the work.**

| Layer | Artifact | Executable? | What it governs |
|---|---|---|---|
| **WHAT** | `configs/formulas/market_ontology.yaml` | **NO** — `formula:` strings are documentation, explicitly *never* `eval`'d ("CONFIG-DECLARED, CODE-EXECUTED") | *meaning* / identity (FM-0NN) |
| **HOW** | `configs/production/*.json` | values only | *parameters* (periods, thresholds) |
| **CODE** | `feature_pipeline.py` etc. | yes — sole computation authority | the actual math |

So you **cannot** "import the YAML into the pipeline" to execute formulas — that is not what the
ontology is, and the registry deliberately holds only 15 scalar callables (rolling indicators
have *no* scalar form by design).

**Configurability comes from the HOW layer, and does not require a WHAT-layer FM id.** Today's
migration proves it empirically: of the 11 periods made configurable, only **4** correspond to
features with an FM id (rsi_14/atr/ema_fast/ema_slow). MA periods, Bollinger, MACD periods and
`trend_strength_window` were made configurable **despite those features having no FM id at all**.

Practical reading: registration (16/38) and configurability are independent. Register for
*meaning and lineage*; externalize to config for *tunability*. Neither blocks the other.

---

## 5. Suggested order of work

Consumer-alignment defects first — they are live correctness issues, cheap, and unblock the
rest:

1. **T-9** (stale comment) + **T-4** (parity test) — minutes each, closes debt this session created.
2. **M16-WU-SESSION-ENCODING** (P1) — canonical vs consumer disagreement, blocks activation.
3. **M16-WU-TREND-STRENGTH-COLLISION** (P2) and **M16-WU-VOLREGIME-S05** (P3) — same class.
4. **T-10** (`behavior_census` scan dirs) — makes the remaining ~35-constant backlog *measurable*
   before deciding whether to extend the Section 6.5 exception further.
5. **T-11** (live-path period verification) — highest consequence, needs a design decision.
6. **T-7 / T-8** — small, contained.
7. **T-5 / T-6** — deferred by user; revisit when the pipeline is stable.
8. **M16-WU-SUPERSEDED-VECTOR-MIGRATION** (P4) — the FM-030/031 binding gap. Large: touches
   `CANONICAL_FEATURES`, pipeline emission order, and model retrain/rebind. Explicit stop
   boundary: *"No silent dim swap; requires migration plan + retrain gates."*

**Standing caveat carried from the census:** the F-019..F-025 entry-information null bounds the
expected downstream *economic* value of this entire programme. The work is justified as
correctness/governance hygiene, not as an expected-edge improvement.

---

## 6. Why "only ontology registration debt" understates the cost (discussion, 2026-07-19)

Registration is not bookkeeping — **registration is what turns enforcement on.**

`scripts/analysis/feature_math_lint.py` is the tool that prevents a governed quantity from being
re-derived elsewhere. Its watch-list comes from `_registered_names()` (`:204-206`), whose
docstring is explicit: *"The governed feature set (ontology names) plus code/column aliases"* —
built by `load_ontology()` (`:51`). **A feature with no FM id is therefore un-flaggable by
construction**, regardless of how many divergent copies of its math exist.

Consequence for the 14 PROMOTED-but-unregistered features (MACD family, `session`,
`trend_strength`, `volatility_regime`, `hour_of_day`, `candles_since_retest`, and the 6 structure
features): any module may reimplement their math and **no check in this repo will notice**.
Contrast `body_ratio` (FM-010, registered) — the GD-001..GD-010 ledger exists *because* those
quantities had FM ids for the lint to key on.

Two live instances of exactly this failure mode already exist, both on unregistered features:
- **T-7** — `causal_structure.py` `_DOUBLE_SWEEP_WINDOW_DEFAULT = 5` independently copied the batch
  `window`. `double_sweep` is unregistered -> invisible to the lint. **Resolved 2026-07-19** (single
  source via `resolve_double_sweep_window()`), but resolved *by hand* — the lint still could not
  have caught it, so this remains a valid illustration of the registration-debt mechanism.
- **M16 P2** — `dual_engine` computes its own `trend_strength = abs(ema_spread)`, colliding with
  the canonical `trend_strength`. Also unregistered -> invisible to the lint.

So the census's `BLOCKS_ACTIVATION: false` is true in the narrow sense (it does not gate L6) but
misleading as a priority signal: registration debt is the *mechanism* by which the deferred
consumer-collision bugs became possible, and by which further ones can appear silently.

Mitigating: the work is `ESTIMATED_COMPLEXITY: M`, hash-neutral when descriptive, with a hard
stop boundary — *"No formula change; registration must match certified identities."*

---

## 7. `ma_200` — corrections to the record (2026-07-19)

- **`ma_300` does not exist** anywhere in `src/`, `configs/`, or `scripts/`. The moving averages
  are `ma_20`, `ma_50`, `ma_200` only. (Checked in response to a recollection of "ma200 ma300".)
- **`ma_200` is classified `IMPLEMENTATION_INTERMEDIATE`** by
  `scripts/analysis/phase1_run15a_quantity_role_adjudication.py:621`, grouped with `ma_20`,
  `ma_50`, `bb_*`, `prev_close`, `upper_wick`, `lower_wick`, `direction`, with consumers recorded
  as *"downstream pipeline features within same module."*
  **That classification is accurate for its siblings but NOT for `ma_200`:** `ma_20` really does
  feed `price_vs_ma20`/`ma_slope_20`->`trend_strength`; `ma_50` feeds `price_vs_ma50`; `ma_200`
  feeds **nothing**. It was bucketed by pattern, not by tracing actual consumers. Small
  documented-vs-actual mismatch — **new tracker item T-13**.
- **PROOF that `ma_200` never affected warmup** (measured, `head(400)` of the XAUUSD corpus):
  rows 78..198 have `ma_200 == NaN` and are **KEPT**; only rows 0..77 are dropped. Total drop 78
  vs `ma_200` NaN count 199 — the two numbers are unrelated because
  `dropna(subset=CANONICAL_FEATURES)` only inspects the 38 canonical columns and `ma_200` is not
  one of them. The old comment's arithmetic (`ma_200(200) + z-score(50) + swing(4) ~= 300`) summed
  a term that never participated. **True both before the deletion and after the restore** — which
  is why the restore did not, and could not, fix T-5.

| ID | Item | State |
|---|---|---|
| **T-13** | `phase1_run15a_quantity_role_adjudication.py:621` records `ma_200` as an intermediate "consumed downstream in same module" — it has zero consumers | **DONE 2026-07-20** — split from generic intermediate bucket; `consumers=[]` + accurate note |
| **T-14** | Ontology registration, partial: `macd_line` FM-047, `macd_signal` FM-048, `macd_hist` FM-049, `volatility_regime` FM-050 | **DONE 2026-07-19** |
| **T-15** | **PRE-EXISTING (not caused by this session):** `tests/test_feature_math_lint.py` is RED — 3 failures | **DONE 2026-07-20** — see section 20 |
| **T-16** | `feature_math_lint._registered_names()` excluded `rolling_indicators` -> all 11 windowed identities (FM-040..050) were UNPOLICED | **DONE 2026-07-19** — see section 11 |
| **T-20** | CRT `state.atr` vs canonical FM-041 `atr` | **DONE 2026-07-19** — DIAGNOSIS CORRECTED: not duplicate implementations of one quantity but a NAME COLLISION between two different quantities (absolute vs close-relative). Resolved by renaming `EngineState.atr` -> `atr_abs`. See section 17 |
| **T-21** | The lint's enforcement model assumes a scalar registry callable exists ("route through the registry"), which is **false by design** for `rolling_indicators`. Policing them therefore has no legal remedy path for legitimate producers | **OPEN** — design gap, surfaced by T-16 |
| **T-17** | FM-049 `macd_hist` — emitted value is z-scored by `compute_normalization`, not the raw difference | **FUTURE PHASE** (user-flagged to revisit) |
| **T-18** | FM-050 `volatility_regime` — window 200 + tercile cuts 0.33/0.66 still hardcoded, outside the Section 6.5 exception; sibling `_global_batch`/`_expanding_causal` identities unregistered | **FUTURE PHASE** (user-flagged to revisit) |
| **T-19** | `candles_since_retest` is **misnamed** — it counts bars since the last **liquidity_sweep**, not since a retest | **OPEN** — semantic finding, see below |

---

## 8. Ontology registration pass — result (2026-07-19)

**Registered 4** of the 14 `M16-WU-ONTOLOGY-REGISTRATION` targets, in `rolling_indicators`,
`lifecycle: registered`, no formula change:

| FM | feature | depends_on | notes |
|---|---|---|---|
| FM-047 | `macd_line` | `close` | `config_keys: [macd_fast, macd_slow]` |
| FM-048 | `macd_signal` | `macd_line` | `config_key: macd_signal` |
| FM-049 | `macd_hist` | `macd_line`, `macd_signal` | **emitted value is Z-SCORED** (compute_normalization overwrites in place) — recorded in the entry `note` so it can't be misread from the formula line |
| FM-050 | `volatility_regime` | `atr` (FM-041) | **no `config_key`** — window 200 + 0.33/0.66 cuts were deliberately NOT migrated; sibling `_global_batch`/`_expanding_causal` identities intentionally left unregistered |

**Verified:** `validate_registry() == []`; lineage edges resolve and `used_by` transposes
correctly (`atr` now shows `volatility_regime` among its 9 consumers);
`tests/test_feature_lineage.py` + `tests/test_formula_registry.py` **17 passed**; 38-dim vector
**unchanged** (3,871 rows, shape `(3871, 38)`, NaN-free) — registration is descriptive, as intended.

**The enforcement question that motivated this pass — MY CLAIM WAS WRONG. CORRECTED 2026-07-19
(E-001).**

I reported: *"registering these names puts them inside `feature_math_lint`'s watch-list. Result:
ZERO violations — no module re-derives them outside the registry. Clean."* **That result was
vacuous.** `feature_math_lint._registered_names()` iterates only:

```python
for section in ("primitives", "feature_compositions", "derived_metrics"):
```

**`rolling_indicators` is not scanned at all** (`grep rolling_indicators feature_math_lint.py` ->
no matches). Measured directly:

```
macd_line   policed_by_lint=False      body_ratio  policed_by_lint=True
macd_signal policed_by_lint=False      upper_wick  policed_by_lint=True
macd_hist   policed_by_lint=False
volatility_regime policed_by_lint=False
atr / rsi_14 / ema_fast  policed_by_lint=False
```

Zero violations because **the lint never looked**, not because the code is clean.

**What this registration pass actually delivered** (still real, just narrower than I claimed):
stable FM ids, DAG/lineage membership (`depends_on` + `used_by`), machine-readable identity, and
the documented z-scoring caveat on `macd_hist`. **It did NOT deliver lint enforcement.**

**Wider consequence — this is a pre-existing hole, not one I created.** All **11**
`rolling_indicators` names are unpoliced: `atr`, `rsi_14`, `ema_fast`, `ema_slow`, `true_range`,
`swing_high`, `swing_low` (FM-040..046, since 2026-07-12) plus my 4. So the F-054 promotion of
ATR/RSI/EMA to "first-class registered identities" also did not confer enforcement.

**Dry-run of closing it** (add `"rolling_indicators"` to that tuple — a one-line change): **8 new
violations surface, all `atr` re-derivations**:

```
analytics/sl_tp_comparator.py:358        config_layer/crt_engine_v2.py:2486
config_layer/crt_engine_v2.py:2562       core/feature_store.py:125
features/causal_structure.py:60          strategies/intent_builder.py:112
training/stage1_dataset_builder.py:334   research/secondlow_v1/detector.py:136
```

That is genuine signal — 8 sites re-deriving ATR outside the registry, currently invisible.
**New tracker item T-16.** Should be its own change with triage (pin as GD-0NN with evidence, or
route through the registry), not folded into a registration pass.

### Not registered, with reasons (do not retry blindly)

- `trend_strength` — **BLOCKED**: `depends_on: [ma_20]`, and `ma_20` is neither registered nor a
  base input, so `test_dependency_graph_acyclic_and_grounded` would fail. Unblock by registering
  `ma_20` first (precedented — `true_range` FM-040 is a registered non-canonical intermediate).
  Note its emitted value is **also z-scored**. Decide whether `ma_50`/`ma_200` follow for symmetry.
- `candles_since_retest` — **BLOCKED**: depends on `liquidity_sweep`, which is in the
  user-deferred stateful bucket.
- `session`, `hour_of_day` — **WRONG SHAPE**: pure timestamp derivations with no window;
  `computation_class` must be `rolling`/`rolling_stateful`, so declaring either would be false.
  Needs a placement decision — new section, or scalar registration in `derived_metrics` (which
  WOULD require real callables in `derived_math.py`, since that section's `impl` must resolve in
  `FORMULA_REGISTRY`).
- The 6 stateful-detection features — deferred by the user.

### T-15 — the lint floor was ALREADY red before this session

`tests/test_feature_math_lint.py`: `test_floor_is_green`, `test_pins_have_no_stale_durable_keys`,
`test_universe_reconciliation_with_census` all fail. **Established as pre-existing, not caused by
the registration:**
- The violations are exclusively `body_ratio`/`body_size`/`wick_size`/`upper_wick`/`lower_wick`
  (FM-001/002/003/004/010) — all registered long before this session. None of the 4 new names appear.
- `_durable_key` is computed from the **violation site's** `(file, qualname, target, kind,
  ast.dump(rhs))` — **nothing from the ontology** — so an ontology edit cannot stale a pin.
- Decisive: `src/config_layer/crt_sweep_taxonomy.py` is **unmodified in the worktree** (identical
  to HEAD) yet its GD-008/GD-009 pins are stale, i.e. the pins were already out of sync with
  *committed* code.
- The pytest floor scans a **wider universe** than the `--check` CLI (includes `scripts/` and
  `tests/`), which is why it reports more sites: `manual_backtest.py`, `strategy_backtest.py`,
  `s09_pattern_recog.py`, `test_feature_pipeline.py`, `crt_xauusd_runtime_trace.py`,
  `feature_math_drift_probe.py`, `live_path_replay.py`, `story_builder.py`.

Remediation is a separate work unit: re-adjudicate GD-006..GD-009 (retire via the manifest if
resolved, or re-pin the new sites) and triage the wider violation set. **Not attempted here** —
it is untouched pre-existing debt and mixing it into this pass would obscure both.

---

## 8b. Full-suite triage — 35 failed / 3284 passed (64 min, 2026-07-19)

Every failure below was tested for causality by **isolation** (temporarily removing my change and
re-running), not by inference.

### MINE — found and fixed (3)

| # | Failure / defect | Cause | Fix |
|---|---|---|---|
| 1 | **FM-050 declared `depends_on: [atr]` — a FALSE LINEAGE CLAIM.** No test caught this; found while triaging. | `compute_volatility_regime` reads `df["atr_14"]` (**absolute**, = SMA14 of true_range). FM-041 `atr` is `atr_14_raw / close` (**close-relative**, canonical idx 13). Different quantities. | `depends_on: [true_range]` (FM-040, the registered ancestor of the absolute chain) + explicit note. `true_range.used_by` now correctly `[atr, volatility_regime]` — **siblings**, not ancestor/descendant. |
| 2 | `test_feature_dag_layers::test_ontology_crosscheck_only_known_rollups` | My FM-050 added a 5th divergence to a 4-item `allowed` whitelist. **Isolation-proved mine** (passed with FM-050 removed). | Per user decision: tightened `_NODES["volatility_regime"]` from `["close","high","low"]` to `["true_range"]` + `"FM-050"`, so ontology and DAG agree exactly. **Alarm stays armed** — no whitelist suppression. M14B's conclusion unchanged; only edge granularity. |
| 3 | `test_config_reachability::test_no_dead_config_keys` | I added a `_comment_ema` key to `crt_engine` (a *scanned* section) -> flagged DEAD. Renaming to `_comment` did **not** help: the checker scans `crt_engine` but does not scan the brand-new `feature_pipeline` section at all, which is why `feature_pipeline._comment` passes. | Removed the key entirely. The EMA-collision disambiguation already lives in 3 places: `feature_pipeline._comment`, the `compute_canonical_ema_features` docstring, and the CLAUDE.md Section 6.5 exception. |

### PRE-EXISTING — isolation-verified, logged, NOT touched

| Failure(s) | Isolation evidence |
|---|---|
| `test_feature_dag_invalidation::test_transitive_downstream_of_atr` | Still fails with FM-050 removed. **User decision: log only, don't touch.** It asserts `volatility_regime` is downstream of `atr` — which contradicts both the code (`df["atr_14"]`, absolute) and the M14B analysis. Likely a stale expectation, but correcting a governance floor deserves its own change. |
| `test_reachability_golden` ×2 | Removing my entire `feature_pipeline` config section -> **identical** failures. Comparison artifact `config-reachability-report.json` was already modified in the worktree before this session. |
| `test_three_authority_surplus_census::test_freshness_summary_matches_live_scan` | Same isolation run -> **identical** `frozen=39 live=41`. Note `change_contracts.json` already referenced `feature_pipeline` twice, in a file I never touched. |
| `test_feature_math_lint` ×3 | `_durable_key` derives from the violation SITE's `(file, qualname, target, kind, ast.dump(rhs))` — **nothing from the ontology**. Decisive: `crt_sweep_taxonomy.py` is byte-identical to HEAD yet its GD-008/009 pins are already stale. |
| `test_geometry_census` ×2 | `geometry_census.jsonl` / `_summary.json` were both already modified in the worktree pre-session. |
| ~26 others | Not individually triaged. Includes several known-red floors (e.g. `test_agents_path_alignment`). |

**Net: of 35 failures, 2 were mine — both fixed.** The third fix (FM-050 lineage) was a real
correctness defect that *no test caught*; it surfaced only because triaging the crosscheck failure
forced me to read the M14B comment. Post-fix: `test_config_reachability`, `test_feature_dag_layers`,
`test_feature_lineage`, `test_formula_registry`, `test_feature_pipeline`, `test_candle_math` =
**63 passed**. 38-dim vector re-verified **unchanged** (3,871 rows, `(3871, 38)`, NaN-free).

---

## 9. `candles_since_retest` — context for the blocked dependency

The blocker is not incidental; it reflects what the feature actually measures.

```python
# feature_pipeline.compute_canonical_temporal_features
if "liquidity_sweep" in df.columns:
    sweep_groups = (df["liquidity_sweep"] != 0).astype(int).cumsum()
else:
    sweep_groups = df["retest_flag"].eq(1).cumsum()      # fallback
bars_since_sweep = df.groupby(sweep_groups).cumcount()
df["candles_since_retest"] = np.where(sweep_groups > 0, bars_since_sweep, 0)
```

**Despite its name, it counts bars since the last SWEEP, not since a retest.** The in-code comment
records this as a deliberate fix: grouping by `retest_flag` made `cumcount()==0` at every retest
candle (the retest candle *is* the first of its own group), producing zero variance in training
data. Grouping by sweep events yields N=2..5 at a typical retest candle — real signal.

Three consequences:
1. **Registration is genuinely blocked** — its true dependency is `liquidity_sweep`, which sits in
   the user-deferred stateful-detection bucket. Declaring `depends_on: [retest_flag]` to dodge the
   grounding test would be a false lineage claim. Correct to wait.
2. **The name is misleading** (T-19). Anyone reading `candles_since_retest` in a model or finding
   will reasonably assume retest-relative timing. Renaming is a canonical-schema change (index 34)
   — not cheap; may be better handled as an ontology `note` + alias when it is registered.
3. **There is a silent fallback path** — on a DataFrame lacking `liquidity_sweep` (minimal test
   frames, partial runs) the feature switches to the degenerate `retest_flag` grouping *without
   warning*, producing the zero-variance behaviour the fix was meant to eliminate. Worth a log line.

---

## 10. `session` / `hour_of_day` — placement design

**Constraint discovered while designing:** enforcement lives only in `primitives`,
`feature_compositions`, `derived_metrics` (T-16). So placement determines whether registration is
documentation-only or actually policed. This matters here more than anywhere else, because
`session` **already has a known 3-way collision**: pipeline hour buckets (`<8`/`<16`), the
`dataset_integrity` tradability calendar, and `inout.scanner.s06_scalping.session_hours_start/end`
(**7/17** — different values, different module). `M16-WU-SESSION-ENCODING` (P1, blocks activation)
is a *fourth* variant. This is exactly the class the lint exists to catch.

**Blocking prerequisite for any option:** `timestamp` is **not** a base input — the ontology's
`base_inputs` are `open/high/low/close/volume/close_delta/ref_high/ref_low/bos_level/disp_open/
disp_close/retest_close`. Any entry declaring `depends_on: [timestamp]` fails the grounding test.
Precedent exists for adding it: `ref_high`/`ref_low`/`bos_level` are declared leaves with the
comment *"structural — out of scope, a leaf."*

### Options

| Option | Mechanism | Enforcement? | Cost / risk |
|---|---|---|---|
| **A — `derived_metrics` + scalar callables** | add `timestamp` to `base_inputs`; write `hour_of_day(ts)` / `session(hour)` in `derived_math.py`; register in `DERIVED` | **YES** | **Type conflict**: `derived_math.py`'s charter is explicitly *"All functions are scalar (float -> float)"* for ATR/price-relative math. A datetime-in/int-out calendar projection violates both its stated contract and its documented purpose. Would need the module's charter widened. |
| **B — new `temporal_context` section** | new ontology section; extend `_ITERATED_SECTIONS`, `validate_registry` branch, `test_feature_lineage._entries()`, and the lint's section tuple | **YES** (if added to the lint tuple) | Honest semantics — these genuinely are neither scalar market math nor windowed indicators. Touches registry + tests + lint. Medium. |
| **C — `rolling_indicators`** | reuse existing section | **NO** (T-16) | Cheapest, but `computation_class` must be `rolling`/`rolling_stateful` — false for a per-bar calendar projection. Rejected: dishonest AND unenforced. |
| **D — leave unregistered** | document only | **NO** | Zero cost, but leaves the one feature with a known live 4-way collision completely ungoverned. |

### Recommendation

**B, sequenced after T-16.** Reasoning: (1) it is the only option that is both semantically honest
and enforceable; (2) `session`'s collision history is the strongest existing evidence that
enforcement is needed for exactly this feature; (3) doing T-16 first means the new section can be
added to a lint that is already section-aware, rather than building a second unpoliced tier.
Sequence: **T-16 (close the rolling_indicators hole + triage the 8 atr sites) -> add `timestamp`
to `base_inputs` -> create `temporal_context` with `session` + `hour_of_day` -> add the section to
both the registry iterator and the lint.**

Do **not** do B before T-16 — that would repeat this pass's mistake of registering into a tier
that looks governed but isn't.

---

## 11. ITEM 1 / T-16 — lint coverage for `rolling_indicators` (DONE 2026-07-19)

**Change (2 parts, `scripts/analysis/feature_math_lint.py`):**
1. `_registered_names()` section tuple += `"rolling_indicators"` — the actual coverage fix.
2. Two classifier corrections, because coverage surfaced 2 false positives:
   - `_COERCION_CALLS` += `asarray/array/astype/asfarray` — numpy dtype coercion carries its
     argument's class, exactly like `float()`. `np.asarray(atr, dtype=float)` on a *parameter* is
     transport. `np.asarray(high * low)` still recurses to a BinOp -> derivation.
   - `ast.BoolOp` moved out of the blanket-derivation branch and classified like `IfExp` /
     `_BOUND_CALLS`: derivation only if an operand computes. `x or 0.0` is null-coalescing
     defaulting, not arithmetic. `a > b or c > d` still resolves via its `Compare` operands.

**Method — violation-SET diff, not exit code** (the floor was already red, so pass/fail proves
nothing):

| Stage | Violations |
|---|---|
| Baseline (before any change) | **4** (`upper_wick`/`lower_wick` x2 files) |
| After adding `rolling_indicators` | **8** (+4 `atr`) |
| After classifier fixes | **6** (+2 `atr`, genuine) |

**SAFETY GATE PASSED:** `comm -23 baseline final` is **empty** — not one previously-detected
violation was masked by the classifier change. The only removals are the 2 confirmed false
positives. `tests/test_feature_math_lint.py` still fails on **exactly** the same 3 pre-existing
tests (`test_floor_is_green`, `test_pins_have_no_stale_durable_keys`,
`test_universe_reconciliation_with_census`) — **no new test breakage**.

**Triage of the 4 surfaced sites:**

| Site | RHS | Verdict |
|---|---|---|
| `config_layer/crt_engine_v2.py:2486` (`CRTEngine.initialise_range`, key `a44121317317d14d`) | `self.detector.compute_atr(candles, cfg.atr_period)` | **GENUINE** — second ATR implementation |
| `config_layer/crt_engine_v2.py:2562` (`CRTEngine.process_candle`, key `af495620f5557850`) | same | **GENUINE** — same |
| `core/feature_store.py:125` | `float(d.get("atr", 0.0) or 0.0)` | FALSE POSITIVE — fixed by the `BoolOp` change |
| `features/causal_structure.py:60` | `np.asarray(atr, dtype=float)` | FALSE POSITIVE — fixed by the coercion change |

Note the earlier dry-run predicted **8** new sites; the CLI surfaced **4**, because
`_SCAN_DIRS = ("features","core","config_layer","engines","runtime")` excludes the `analytics/`,
`strategies/`, `training/`, `research/` sites the ad-hoc dry-run had included. The pytest floor
scans a wider universe and may still report those.

### The blocker this exposed (T-20 / T-21)

The 2 genuine sites **cannot be resolved by either sanctioned mechanism**:
- **Cannot pin.** `test_grandfather_set_monotonic` asserts `CURRENT ∪ RETIRED == BASELINE` where
  BASELINE is exactly `GD-001..010`. A `GD-011` fails `current <= baseline` ("foreign pin ids").
  The ratchet is a deliberate one-way design — grandfathering was a one-time amnesty, and the
  test docstring explicitly names the workaround it blocks ("retire 2, add 2 back").
- **Cannot route.** The lint's remedy text says "route through candle_math/derived_math/registry",
  but `rolling_indicators` are **exempt from `FORMULA_REGISTRY` by design** — the registry holds
  no scalar ATR callable, because none exists for a windowed indicator. There is nothing to route
  to.

So the enforcement model has a structural gap for windowed identities (**T-21**), and the real
remedy for these 2 sites is architectural: make the CRT engine **consume** the pipeline's ATR
rather than compute its own from its own buffer with its own `crt_engine.atr_period` (**T-20**) —
a behaviour-affecting change requiring a parity proof, deliberately not attempted here.

**Net position:** the 2 duplicate ATR implementations are now **visible** instead of invisible,
which was the entire point of T-16. The floor stays red — but it was red before, and no
previously-green test was broken.

---

## 12. ITEM 2 — `session` / `hour_of_day` registration (DONE 2026-07-19)

**New ontology section `temporal_context`** — a THIRD computation class, chosen because both
existing sections would have required a false declaration:
- not `rolling_indicators` (`computation_class` must be `rolling`/`rolling_stateful`; a per-bar
  calendar projection has no window),
- not `derived_metrics` (its `impl` must resolve in `FORMULA_REGISTRY`, and `derived_math.py`'s
  charter is explicitly *"scalar float -> float"* ATR/price-relative math — a datetime-in/int-out
  projection violates both contract and purpose).

Entries: **FM-051 `hour_of_day`** (`depends_on: [timestamp]`), **FM-052 `session`**
(`depends_on: [hour_of_day]` — what the code actually does). `session` carries a `note`
documenting the 4-way collision.

**Prerequisite:** `timestamp` added to ontology `base_inputs` as a declared leaf — same rule as
`ref_high`/`ref_low`/`bos_level`, and it was **already** a raw input in
`feature_dag_layers._RAW_INPUTS`, so this aligned the ontology to the DAG rather than inventing a
concept.

**Wired into all 5 places** (missing any one leaves it half-governed):
| # | File | Change |
|---|---|---|
| a | `src/features/registry/__init__.py` | `_ITERATED_SECTIONS` += `temporal_context` |
| b | `src/features/registry/__init__.py` | `validate_registry()` branch — requires `formula` + `impl` + `computation_class == "calendar"`; CALENDAR-impl exemption from FORMULA_REGISTRY |
| c | `tests/test_feature_lineage.py` | `_entries()` + skip in `test_registered_plus_resolve_impl` |
| d | `scripts/analysis/feature_math_lint.py` | `_registered_names()` += `temporal_context` — **the enforcement point** |
| e | `scripts/analysis/feature_dag_layers.py` | FM ids added; `session` edge tightened `["timestamp"] -> ["hour_of_day"]` to match the ontology exactly (crosscheck divergence-free, same approach as FM-050) |

**Verified:** `validate_registry() == []`; `session`/`hour_of_day` `policed=True`; lineage grounded
(`session -> hour_of_day -> timestamp`, `timestamp ∈ base_inputs`); ontology<->DAG crosscheck clean.

### The payoff — a FIFTH session definition, found because registration turned the lint on

Violation-set diff surfaced 2 new `session` sites (nothing masked):

**1. `runtime/backtest_v2.py:1932` — GENUINE name collision, now FIXED.**
`session = self._session(candle.timestamp)` returns a **string** session name resolved from
`crt_cfg.session_windows` (config-driven), defaulting to `"OFF_SESSION"`. Canonical FM-052 is an
**int8 {0,1,2}** from hardcoded 8/16 cutoffs. Same bare name, **different type, different source,
different concept** — `semantic_class: name_collision_distinct`, the GD-006/007 category.
Since the ratchet forbids new pins, resolved the way those pins' own `review_trigger` recommends:
**renamed the local to `session_label`** (used on exactly 2 adjacent lines; behaviour-neutral) with
a comment stating it is the CRT-engine session LABEL, not the canonical feature. Violation cleared.

So the count of `session` definitions in this repo is now documented at **five**: pipeline int8
(8/16), scanner `s06_scalping` 7/17, `dataset_integrity` tradability calendar,
`M16-WU-SESSION-ENCODING`'s canonical-vs-`SESSION_MAP` permutation, and this CRT string label.

**2. `features/crt_feature_builder.py:144` — left open, deliberately.**
`str(raw_session ...).strip().lower()` is string NORMALIZATION of an already-supplied session, not
a re-derivation of the bucket — a false positive of the `.strip()`/`.lower()` family. **The module
is dead (0 callers, documented in `candle_math.py:14` and the gate2b adjudication rows).** Not
worth expanding classifier surface for a 0-caller file; logged rather than fixed.

**Final lint state: 7 violations** = 4 pre-existing (`upper_wick`/`lower_wick`) + 2 `atr` (T-20,
structurally unresolvable here) + 1 dead-module `session`. **Nothing masked at any step.**

---

## 13. ITEM 4 — XAUUSD 2-month backtest (RAN 2026-07-19)

**Run dir (for reuse — do not re-run):**
`results/XAUUSD/backtests/run_20260719_021925_XAUUSD/`
Artifacts: `XAUUSD_summary.json`, `XAUUSD_events.jsonl` (1,561 records),
`XAUUSD_crt_telemetry.jsonl` (1,245), `XAUUSD_report.txt`.
Input: `data/XAUUSD_W2026-03-23-to-2026-05-21.csv` (3,949 rows, parent sha `4d73f5ce…`).

**The blocker is cleared.** L2 gate returns **WARN**, not REJECT (`hard_failures: []`;
41 intra-session gaps, **0 missing candles**, largest 12 — within thresholds). Guard passthrough
confirmed: the path is returned unchanged, not rewritten.

**Dataset identity confirmed — the guard-substitution risk is definitively falsified:**
```
FeaturePipeline | finalize | rows_before=3949 rows_after=3871 drop=78 drop_pct=1.98%
```
3,949 in / 3,871 out — the 2-month window, **not** the 47,275-row corpus. This also confirms the
78-row / 1.98% warmup figure in a real run (the earlier "254 rows / 6.4%" was my error).

**Result: 0 trades.** Reported plainly; **no edge claim in either direction** (Section 6.5).

### The CRT state trace (the in/out-of-state data)

**Correction to my own plan:** I said transitions land in `XAUUSD_crt_telemetry.jsonl`. They do
**not** — that file holds aggregate counters (`kind: TRANSITION_COUNTER`, `RESET_ATTRIBUTED`,
`CANDIDATE_LIFECYCLE`, `DECISION_DISTANCE`, …) with no `event` field. The per-event transitions are
in **`XAUUSD_events.jsonl`** (327 `STATE_TRANSITION` records).

| Transition | Count |
|---|---|
| `RANGE -> SWEEP` | 285 |
| `SWEEP -> DISPLACEMENT` | 24 |
| `RANGE -> SHADOW_PENDING` | 5 |
| `SHADOW_PENDING -> SWEEP` | 5 |
| `SWEEP -> EXPANSION` | 5 |
| `EXPANSION -> RETEST` | 3 |
| `RETEST -> EXECUTION` | **0** |

State entry counts (`TRANSITION_COUNTER`): RANGE 943, SWEEP 290, DISPLACEMENT 24,
SHADOW_PENDING 5, EXPANSION 5, RETEST 3. `SHADOW_LEAK: 0` (clean).

### Why 0 trades — the SESSION filter, not the scorer

All 3 retests were **APPROVED** by the CRT scorer (`DECISION_DISTANCE`: scores 0.311 / 0.330 /
0.477 vs threshold 0.30, `accepted: true`, `rejection_reason: "APPROVED"`). Every one was then
killed by `FILTER_REJECTED`:

| Timestamp | Reason |
|---|---|
| 2026-05-07 10:45 | `off_session:OFF_SESSION` |
| 2026-05-15 05:45 | `off_session:OFF_SESSION` |
| 2026-05-20 02:15 | `off_session:ASIA` |

**HYPOTHESIS REFUTED (mine).** I predicted this would be F-048's mechanism — the DecisionEngine
`rr` gate firing `low_rr` because RREngine emits a polarity in [0.5,1] against `rr_threshold=1.5`,
making `run()` structurally unable to execute. **It was not.** The candidates never reached that
gate; the CRT session filter rejected them first. Checked before claiming: zero `low_rr` /
`_engine_vetoed` / engine-rejection entries anywhere in the run log. F-048 is neither confirmed
nor contradicted by this run.

Two things worth noting:
1. **`off_session:ASIA`** — ASIA is a *named* session yet was still filtered, so the allowed-session
   set excludes it. Consistent with F-017 (session policy is not a promotable lever) and directly
   relevant to the session-collision work in Item 2.
2. The very feature registered as **FM-052 `session`** in Item 2 — the one with the documented
   4-way (now five-way) collision — is what gated 100% of this run's trade candidates.

**Run configuration:** `BACKTEST_ENGINE_GATE=1` (**gate ON**, logged explicitly), production config
`v2_multi_2026_04`, `gaussian_impl=heuristic`, ZoneGate 8 zones from `models/zone_registry.json`.
Note this differs from F-037's documented research-spine setting (`.env` = 0, CRT-only) — this run
had the full fusion stack wired in, though no candidate survived far enough to exercise it.

**Statistical standing: INSUFFICIENT.** 3 candidates, 0 trades, over ~2 months. Nothing here
supports or refutes any economic hypothesis.

---

## 14. Table-B migration, PHASE A — 24 literals -> config (DONE 2026-07-19)

**Three-tier classification** (user directive: *"actually tunable policy, not identity — if
tunable then it needs to be in config"*). The prior two-tier split forced a false choice.

| Tier | Rule | Code comment template |
|---|---|---|
| **STRUCTURAL** | no meaningful alternative value; changing it breaks the definition or the arithmetic | `STRUCTURAL — defines the identity of <feature>; do not move to config per §6.5.` |
| **TUNABLE STRUCTURAL** (new) | shapes a REGISTERED identity *and* has legitimate alternatives -> goes to config, but carries two extra obligations | `TUNABLE STRUCTURAL — config-driven, but changing it redefines <FM-0NN>; requires ontology formula sync + artifact re-certification.` |
| **BEHAVIORAL** | tunable, target feature has no FM id | plain config reference |

**Migrated: 24 keys** (12 Tier 3 + 12 Tier 2). Left in code: enum encodings, RSI definitional
constants, `ddof=1`, degenerate sentinels, epsilons, and `finalize()` 300/0.02 (T-5/T-6 deferred).

### The obligation Tier 2 created — 6 ontology formulas were about to become FALSE

Migrating a literal that is *written into* an ontology `formula:` string makes that string a false
claim about runtime the moment config diverges. Synced (formula now names the config key, current
value shown as default) + `config_key(s)` added:

| FM | Was | Now |
|---|---|---|
| FM-020 `disp_strength` | `clip(…, 0.0, 3.0)` | `clip(…, <…clip_low>, <…clip_high>)  # defaults 0.0, 3.0` |
| FM-021 `retest_depth` | `clip(…, 0.0, 1.0)` | `clip(…, <…clip_low>, <…clip_high>)  # defaults 0.0, 1.0` |
| FM-026 `liquidity_pressure_score` | `exp(-0.5 * …); nan -> 10.0` | `exp(<…decay_coeff> * …); nan -> <…nan_sentinel>` |
| FM-049 `macd_hist` | `rolling(50) z-scored` | `rolling(<…zscore_window>) z-scored  # default 50` |
| FM-050 `volatility_regime` | `rolling(200)…cuts at 0.33/0.66` | config-key form; **note also corrected** — it had asserted the window/cuts "remain hardcoded", now false |
| FM-052 `session` | `< 8 … < 16` | `< <…asia_end_hour> … < <…london_end_hour>` |

Verified: **0** stale literal assertions remain (`grep` of the old patterns returns 0);
`validate_registry() == []`; 12 entries now carry `config_key`/`config_keys`.

### `causal_structure` — parameter added, but NOT yet single-source

`_DOUBLE_SWEEP_WINDOW` (module global, read at two sites) -> `_DOUBLE_SWEEP_WINDOW_DEFAULT`, with
an explicit `double_sweep_window` keyword on **both** `causal_structure_series` and
`causal_structure_at_bar`.

**Correction to my own comment during implementation:** I first wrote that the config value "is
threaded into causal_structure so the two can no longer drift". **False** — `feature_pipeline`
**never calls** `causal_structure`; the only production caller is `core/feature_store.py:141`
(live path), which still resolves the signature default. So the two are no longer *hardcoded
copies*, but they are not one source either. **T-7 stays OPEN** until FeatureStore threads config.

**T-7 CLOSED 2026-07-19** (supersedes the paragraph above; kept per §6.2 rule 4). The signature
default was removed entirely rather than threaded at the call site: both public `causal_structure`
functions now take `double_sweep_window: int | None = None`, and `None` resolves through the new
`feature_pipeline.resolve_double_sweep_window()` — the same `None`-means-config contract Phase B
gave `k`/`swing_window`. Putting the resolution in `causal_structure` (not in `FeatureStore`) means
a future second live caller cannot reintroduce the divergence. `FeatureStore` therefore needed no
call-site change; it needed a *different* fix — its `_liquidity_sweep_history` ring was
`maxlen=10`, which caps the history handed to `causal_structure_at_bar` and would have silently
truncated any window >10. Now `max(10, window)`; byte-identical at today's value of 5.

**Residual (NOT closed, needs a decision):** `FeatureStore._compute_derived`'s fallback
double_sweep path — which fires only when `_apply_causal_structure` raises — scans the *entire*
deque and ignores `double_sweep_window` altogether. Making it window-aware would change behavior on
that degraded path today (10 -> 5), so it is deliberately left alone rather than silently
"fixed" (§6.2 rule 3). Filed for a user decision.

### Verification (all gates passed)

| Gate | Result |
|---|---|
| Parity, full XAUUSD corpus (47,197 rows) | **byte-identical** `np.array_equal`, shape `(47197, 38)` |
| Config actually READ (parity alone can't prove this) | 6 keys mutated one at a time -> output moved every time |
| Strictness | incomplete cfg raises `KeyError` |
| Lint violation-set diff | **7 -> 7**, nothing new, nothing masked |
| Live-path `causal_structure` | default ≡ explicit-5; param provably plumbed (25 differs) |
| Tests | **81 passed** across pipeline/candle_math/derived_math/lineage/registry/dag_layers/fc1a/reachability |

**Finding surfaced by the "is it read?" gate:** `rsi_overbought`/`rsi_oversold` move
`df['rsi_state']` but **not the 38-dim vector** — `rsi_state` is non-canonical. A repo-wide grep
finds **no consumer of `rsi_state` outside `feature_pipeline.py`**, so these two knobs are
currently inert w.r.t. every model and decision path. Config-driven, but tuning them changes
nothing downstream today. Worth an explicit dead-knob check before anyone sweeps them.

### Phase B (NOT started) — `swing_window`

Deliberately excluded and sequenced last: it is imported cross-module by
`causal_structure.py:21`, sets the **FC1-A PIT causal delay** (`available_at = t+k`) as well as
the pivot half-window, and defines `lookback: 2` on **two** registered identities (FM-045/046).
Own commit, own parity + live-path proof.

---

## 15. Table-B migration, PHASE B — `swing_window` (DONE 2026-07-19)

User chose **full migration** over keeping it STRUCTURAL. Executed with the provenance layer
included, because that was the actual risk.

### What made this different from Phase A

`SWING_WINDOW` was not a local constant — it was a **published interface with 9 module-level
importers**: `causal_structure.py` (live path), **6 governance/certification scripts**, and 2 test
modules. Six of those scripts write `"swing_window": SWING_WINDOW` into durable artifacts as a
**provenance fact**.

The naive approach (module default + config override used only inside `FeaturePipeline`) would
have produced **governance artifacts asserting a value the pipeline did not use** — strictly worse
than leaving it hardcoded, because it injects the drift into the provenance layer itself.

### Design: PEP 562 lazy module attribute

```python
def resolve_swing_window(cfg=None) -> int:   # THE single source of truth
def __getattr__(name):                        # PEP 562
    if name == "SWING_WINDOW": return resolve_swing_window()
```

Two properties that made this the right tool:
1. **All 9 `from features.feature_pipeline import SWING_WINDOW` statements keep working** — so the
   6 certification scripts became provenance-correct with **zero edits**; they now record the
   resolved config value automatically.
2. **No import-time config load.** A module-level assignment would create a
   `features -> config_layer` edge *at module execution*, the exact cycle risk the deferred
   imports elsewhere guard against (`config_layer.rr.rr_dataset_builder` and
   `config_layer.crt_engine_v2` import `features.*` in the other direction).

**`causal_structure.py`:** removed the module-level `from features.feature_pipeline import
SWING_WINDOW` (it would have forced a config load at *that* module's import). Both public
functions now take `k: int | None = None`, resolved at call time via `_resolve_k()` — explicit
arg wins, else config. Same resulting value, no import coupling.

**`feature_pipeline.compute_structure_liquidity`** now reads `self._fp_cfg["swing_window"]` — the
instance config, not the module attribute, so an injected `cfg` is honoured.

### Provenance fixes actually required: 2 (not 6)

Only `phase1_run1_feature_truth.py` had **hardcoded literals** rather than the import:
`parameters={"SWING_WINDOW": 2}` at `:481` and `:514`, plus a formula string
`"rolling(center=True,k=2) …"`. All three now resolve from the imported (config-derived) value.
Repo-wide grep for a hardcoded swing literal in `scripts/`: **none remain**.

### Ontology

FM-045/FM-046 formulas rewritten to name the config key (`k = <feature_pipeline.swing_window>`,
default shown), `config_key` added to both, and FM-045 carries a `note` recording that `k` sets
the FC1-A PIT contract and that changes require **re-certification, not a re-run**.

### Verification (all gates passed)

| Gate | Result |
|---|---|
| Parity, full XAUUSD corpus | **byte-identical**, `(47197, 38)` |
| `swing_window` actually read | `k=3` changes output |
| PEP 562 import path | `SWING_WINDOW` == resolver == 2; unknown attr still raises |
| `causal_structure` lazy `k` | auto ≡ explicit `k=2`; `k=4` differs (provably plumbed) |
| **Live-path call parity** | `feature_store.py:141`'s exact call signature ≡ explicit `(k=2, dsw=5)` |
| Lint violation-set diff | **7 -> 7**, nothing new, nothing masked |
| `validate_registry()` | `[]` |
| Tests | **78 passed** (incl. `test_fc1a_swing_causal`, `test_phase1_duplicate_formula_identity_closure`) |

### Honest debt note — T-4 exposure GREW

Entries carrying **both** `lookback` and `config_key` went from **4 -> 9** (`atr`, `rsi_14`,
`ema_fast`, `ema_slow`, `macd_line`, `macd_signal`, `volatility_regime`, `swing_high`,
`swing_low`). `lookback` is kept for human readability but **nothing enforces it matches the
resolved config value** — so all 9 can now silently lie if a config value is changed. T-4's parity
test (assert `lookback == resolved config value` for every entry declaring both) is no longer a
nice-to-have; it is the guard for the whole migration. **T-4 priority raised.**

Only `true_range` (lookback 1) still has a `lookback` with no `config_key` — correctly, since its
period derives from `atr_period`.

---

## 16. T-4 — ontology <-> config parity, ENFORCED (DONE 2026-07-19)

**Scope was larger than "add a test".** Inspection found **6 entries already lying**: they
declared `config_key` while their `formula:` still inlined the literal, because they predated the
`<feature_pipeline.X>` token convention introduced in Phase A — `atr` (SMA(14)), `rsi_14`
(SMA(14)), `ema_fast` (span=9), `ema_slow` (span=21), `macd_line` (span=12/26), `macd_signal`
(span=9). Change `rsi_period` to 21 and FM-042's formula would still have claimed 14.

**Part 1 — 6 formulas rewritten** to the token form
(`close.ewm(span=<feature_pipeline.ema_fast_span>, …)  # default 9`).

**Part 2 — schema disambiguation.** Two entries carried `lookback` alongside *plural*
`config_keys`, so "which key does the lookback mirror" was unassertable. Added
`lookback_config_key`: `macd_line -> feature_pipeline.macd_slow` (the longer span = effective
warmup), `volatility_regime -> feature_pipeline.volatility_percentile_window` (the tercile cuts
are thresholds, not lookbacks).

**Part 3 — `tests/test_ontology_config_parity.py`** (new; dedicated file rather than folding into
`test_feature_lineage.py`, which is a pure-ontology fixture with no config dependency):

| Rule | Asserts |
|---|---|
| **A** | every `config_key`/`config_keys`/`lookback_config_key` names a key that EXISTS in config |
| **B** | singular `config_key` + `lookback` -> must be EQUAL to the live config value |
| **C** | plural `config_keys` + `lookback` -> MUST declare `lookback_config_key`, and match it |
| **D** | every `<feature_pipeline.X>` token in any `formula`/`note` resolves |
| **E** | **regression guard** — declaring `config_key(s)` OBLIGES the formula to contain a token |
| sanity | the population is non-trivial (>=12 bound, >=8 with lookback) so an empty-set pass is impossible |

Rule E is what makes this durable: *if you say the value comes from config, the formula must say
where.* Structural, no numeric heuristics, no false positives — and it is exactly the rule whose
absence let the 6 entries in Part 1 rot.

### Verification — the guard was proven to FAIL, not just to pass

A test that cannot fail is not enforcement, so each rule was broken deliberately and restored:

| Deliberate break | Caught by | Message |
|---|---|---|
| config `rsi_period` 14 -> 21 | **B** | `rsi_14: lookback=14 but feature_pipeline.rsi_period=21` |
| strip the token from `ema_fast`'s formula | **E** | declares config binding but formula inlines the literal |
| rename `config_key` to a nonexistent key | **A** (+B) | `not present in config` |

Other gates: `test_ontology_config_parity` **6 passed**; combined governance run **29 passed**
(`+ test_feature_lineage`, `test_formula_registry`, `test_feature_dag_layers`);
`validate_registry() == []`; lint violation-set diff **7 -> 7** (nothing new, nothing masked);
feature vector **unchanged** `(47197, 38)` — this pass is metadata/doc only, zero runtime effect.

### Also closed this session: T-7

`causal_structure` now resolves BOTH `k` and `double_sweep_window` through config-backed
resolvers under the same `None`-means-config contract. Verified: the live-style call (passing
neither) equals the explicit config value, and an explicit override provably changes output. The
previous latent batch/live split — where FeatureStore silently ignored
`feature_pipeline.double_sweep_window` — is gone.

---

## 17. T-20 — CRT ATR (DONE 2026-07-19). **My diagnosis was wrong; the fix is a rename.**

### The correction

I had recorded T-20 as "2 genuine duplicate-ATR implementations" and recommended *"CRT consumes
the pipeline ATR"*. **That recommendation would have been a serious bug.** The two are
**different quantities sharing a bare name**:

| | CRT `EngineState.atr` | Canonical FM-041 `atr` |
|---|---|---|
| Value | **ABSOLUTE**, price units | `atr_14_raw / close` — **close-relative**, dimensionless |
| Evidence | `atr_min_displacement * atr` compared to price moves; `candle.wick_size < mult * atr`; `expansion_atr_min_distance * atr` | canonical vector index 13 |
| Config key | `crt_engine.atr_period` | `feature_pipeline.atr_period` |
| Warmup | partial-window mean (works with <14 bars) | `rolling(14)` -> NaN |

Feeding the relative value into CRT's absolute-price comparisons would be a ~1000x error on gold.
The code already knew: `crt_engine_v2.py:1102` tags it `"source_class": "CRT_LOCAL_DERIVED"`.

**This is the third time the bare name `atr` has misled in this repo** — FM-050's `depends_on`,
the `volatility_regime` DAG edge, and this diagnosis. The lint flagged it on TARGET NAME, which is
why it looked like a re-derivation.

### The fix

`EngineState.atr` -> `EngineState.atr_abs`, with the distinction documented at the field. **50
reference sites across 6 files** (crt_engine_v2 34, backtest_v2 7, crt_xauusd_runtime_trace 4,
crt_gaussian_scorer 2, 2 test modules).

### A regression I introduced and caught by byte-diffing

The mechanical rename **silently broke telemetry**. `crt_engine_v2.py:2529` used a *string-based*
`getattr(st, "atr", 0.0)` — invisible to an attribute-name regex — so `RETEST_REPLAY` records
started emitting `"atr": 0.0` instead of the real values (10.71 / 14.92 / 5.91).

**Nothing else would have caught it:** the run summary was identical ("0 trades"),
`events.jsonl` was byte-identical, and every test passed. Only the telemetry byte-diff exposed it.
Swept for the pattern and found two more (`crt_baseline_trace.py:206`,
`p3c1_build_trade_audit.py:105`, both defaulting to `None`); all three now use the real attribute,
and the site carries a comment explaining why the string-access form was dangerous.

### Verification

| Gate | Result |
|---|---|
| `XAUUSD_events.jsonl` (the ledger) | **byte-identical** |
| `XAUUSD_crt_telemetry.jsonl` | **byte-identical** (after the getattr fix; DIFFERED before it) |
| `XAUUSD_summary.json` | identical excl. run id |
| Lint violations | **7 -> 5** — both `atr` violations resolved; the `upper_wick`/`lower_wick` pair merely shifted line (:900->:905) from a comment insertion |
| GD stale-pin set | **unchanged** (durable_key is content-based, so the line shift staled nothing) |
| Tests | **87 passed** |

### T-21 partially dissolves

I had framed T-21 as *"the lint's remedy is impossible for rolling indicators"*. For **this**
instance that is moot — it was never a genuine re-derivation, just a name collision, and renaming
resolved it cleanly. The lint-model gap remains real in principle for a genuine second producer of
a windowed identity, but **these two sites were not evidence for it**. T-21 keeps no open example.

### Residual (documented, not fixed)

Two ATR implementations still exist with a real behavioural difference — CRT's partial-window mean
vs the pipeline's NaN warmup. Defensible: they run in different execution contexts (live candle
buffer vs batch DataFrame). Also unchanged: the BitNet feature map at `crt_engine_v2.py:1955/2024`
injects the ABSOLUTE atr under the canonical key `"atr"` — that is the known **F-055** finding
(`atr` fed raw/unnormalized), on a path inert while `use_bitnet: false`. Deliberately not touched.

---

## 18. T-10 — behavior_census can now see the feature layer (DONE 2026-07-19)

### The one-line fix would have produced a FALSE GREEN

`_SCAN_DIRS` excluded `features/`, so the obvious fix was to add it. But `_collect_constants`
only gathers **module/class-level** assignments (its own docstring: *"NOT function-body /
signature"*), and nearly every remaining `feature_pipeline` literal lives inside a `compute_*`
method body. Adding the directory alone would have scanned it and reported ~nothing — a green
result meaning *"we didn't look"*, which is worse than not running the tool.

**Two gaps, both closed:**
1. `_SCAN_DIRS` += `"features"`.
2. New `_collect_function_constants()` — walks `FunctionDef`/`AsyncFunctionDef` bodies.

### Reported ADDITIVELY, on purpose

Function-body constants land in new keys (`function_constants`, `function_behavioral`), **not**
merged into `behavioral`/`hardcoded`. Existing floors assert those lists are empty
(`test_crt_engine_no_genuine_hardcoded`, `test_dynamic_threshold_has_no_behavioral_constants`).
Merging would have broken them **not because anything regressed, but because the measurement
definition changed** — a misleading break. Additive keeps every existing assertion's meaning
intact while making the new layer visible. **All 7 existing floors still pass.**

### A second blind spot found while wiring it

`feature_pipeline.py` was STILL skipped after adding the directory. The skip test
(`if not consts: continue`) ran **before** function collection, and the module now has **zero**
module/class-level constants — `SWING_WINDOW` became a lazy `__getattr__` in Phase B. So the most
constant-dense module in the layer was being skipped outright and would have read as "clean".
Fixed by collecting function constants before the skip decision.

### What it now shows — the migration is confirmed thorough

`features/feature_pipeline.py`: module/class-level behavioral **0**, hardcoded **0**;
function-body constants **2**, of which **1 BEHAVIORAL** — `_warmup_budget = 300` (L1016), which
is precisely **T-5**, already deferred by decision. Seven `features/` modules are now visible
where zero were before.

**Honest scope limit:** the census collects `NAME = <numeric literal>` assignments. Literals
appearing INLINE inside expressions (e.g. the `0.02` in `max(300, int(n_before * 0.02))`, or the
`1e-9` guards) are still not collected — true for the pre-existing scanned packages too. This is
a real improvement in visibility, not total coverage.

### Verification

95 tests passed across census / ontology-parity / feature-pipeline / CRT / config-reachability;
lint violations unchanged at 5; feature vector unchanged `(3871, 38)`.

---

## 19. T-11 — no silent fallbacks on the live ingress (DONE 2026-07-19)

User rule, verbatim: **"No silent Fall Back. Hard rule."** Audited the source (not docs), fixed
every violation found in the live path AND in my own session code.

**Decisions:** fail closed on FeatureStore failure (no kill-switch flag — such a flag gets
switched on under pressure and left on); ALL consumed fields required (no tiering, no
"acceptable" default, no future adjudication about where the line sits).

### What was fixed, worst first

**1. The FeatureStore try/except — the biggest hole.** It caught every exception, logged a
WARNING, and continued with the un-validated `_safe_float` dict. Since
`FeatureStore._ensure_required()` is the ONLY enforcement of the canonical field contract,
**the validation failure was itself what disabled the validation** — a real decision then scored
on defaulted data. Now propagates: a validation failure REJECTS the tick.

**2. `ema_fast`/`ema_slow` defaulted to `close`** — a PRICE substituted for a moving average.
Cascaded: `ema_spread` -> 0, `trend_bias` -> 0, and `ema_spread`'s own fallback was
`ema_fast - ema_slow` = 0. Three canonical features became plausible, wrong, and mutually
consistent — undetectable by any range check.

**3. `atr` defaulted to `0.0`** — silently disabling every `if state.atr_abs > 0` CRT guard
(`crt_engine_v2.py:1193/1373/1892/1903/2712/2805`). The engine did not error; it quietly stopped
applying its own logic.

**4. `_derive_session` returned `"london"` when the feeder sent nothing** — fabricating a
specific trading session. Session gates trade admission: the 2026-07-19 XAUUSD run had **100%**
of its candidates rejected by the session filter. An invented "london" could admit or reject
trades on fiction. Also `_normalize_session(None) -> "london"`, and unknown values were passed
through raw; both now raise.

**5. `symbol` defaulted to `"EURUSD"` at two sites** — inventing a concrete instrument, so
orchestrator routing and logging would misattribute the decision to the wrong market.
(`"UNKNOWN"` elsewhere is at least honest; a real ticker is not.) New `_require_symbol()`.

**6. ~30 feature fields defaulting to `0.0`/`1.0`** — `0.0` is a LEGITIMATE value for most
structure flags, so a defaulted field was **indistinguishable from a real one**. All now
mandatory via the new `_require_feature_value()`, which mirrors the existing
`_require_ohlcv_value()` pattern already in the file.

**7. `context` re-read `candles_since_retest`/`sweep_detected`/`double_sweep` from raw
`trade_data` with defaults** while the same fields were strict in `engine_input` — the same value
could be real in one path and defaulted in the other. Now read from the validated frame.
(`double_sweep` especially: FeatureStore derives it from history, so the feeder's raw value was
the wrong source regardless.)

**8. My own session code — same sin, 7 sites.** `float(st.atr_abs or 0.0)`,
`getattr(state, "atr_abs", None)` x2, and 4x `float(self.state.atr_abs or 0.0)`. All dead
defaults on a non-optional dataclass field — but **exactly the pattern that had silently zeroed
telemetry an hour earlier**. Now direct attribute access, so a future rename fails loudly.

### Deliberately NOT fallbacks (kept, documented)

- `double_sweep: 0.0` in the auxiliary dict — a placeholder that `FeatureStore._compute_derived()
  overwrites with the history-correct value; never read as data.
- `disp_str` as an alias for `disp_strength` — a naming variant, not a default: if neither
  spelling is present the strict accessor still raises.
- The three `is_asia`/`is_london`/`is_newyork` `_safe_float(..., 0.0)` reads — these test WHICH
  flag is set, not substitute a value; if none is set, `_derive_session` raises.

### Verification

| Gate | Result |
|---|---|
| Positive — complete `trade_data` | builds identically (strict path changes no values, only rejects incomplete input) |
| Negative — delete each of `ema_fast`/`ema_slow`/`atr`/`body_ratio`/`retest_depth`/`session`/`symbol` | **each raises `ValueError` naming the field** (previously: silent `close`/`0.0`/`"london"`/`"EURUSD"`) |
| `_normalize_session(None)` | raises (was `"london"`) |
| Live-hook tests | **51 passed** — existing fixtures were already complete, so no test needed loosening |
| Batch path | backtest `events.jsonl` AND `crt_telemetry.jsonl` **byte-identical** |
| Broad regression | **127 passed**; lint violations unchanged at 5 |

### Still OPEN under T-11

The **versioned feed contract** (`feed_schema_version` handshake) and the **batch/live period
symmetry check** — asserting the feeder's EMA/ATR periods match `feature_pipeline.*`. Both need
the producer (external EA repo) to participate, so they are a coordinated change, not a
unilateral one. The asymmetry noted earlier stands: sweeping `ema_fast_span` still changes
batch/training with no live effect. What this pass removed is the *silent* part — a missing or
malformed field now fails loudly instead of resolving to a plausible lie.

---

## 20. Queue pass 2026-07-20 — T-8 / T-9 / T-13 / T-15 closed

Worked the remaining **actionable** queue items (not deferred/paused/external). User decisions
in §3 still hold: M16 P1/P2/P3 deferred to live_engine_hook phase; T-5/T-6 warmup deferred;
stateful 6 excluded; T-17/T-18 future phase.

### T-9 — stale MACD B2/B3 comment

`configs/formulas/market_ontology.yaml` `indicator_identities` header: the line claiming
*"Full FM-id registration + parity wiring is a separate architectural review (deferred, B2/B3)"*
is now marked SUPERSEDED with the C-1 truth (MACD PROMOTED as FM-047/048/049; residual is
registration-hygiene only, not a review gate).

### T-8 — dead EMA soft defaults

`src/features/feature_builder.py`: removed `ema_fast_period` / `ema_slow_period` soft-default
attributes (never read by `build()` or any caller). Period authority remains solely
`feature_pipeline.ema_fast_span` / `ema_slow_span` (T-1).

### T-13 — ma_200 consumer claim

`scripts/analysis/phase1_run15a_quantity_role_adjudication.py`: `ma_200` split out of the
generic intermediate bucket. Role stays `IMPLEMENTATION_INTERMEDIATE` but `consumers=[]` with
an explicit note that ma_20/ma_50 feed downstream columns while ma_200 feeds nothing. (ma_200
was not present in the 2026-07-10 frozen universe artifact — correction is in the adjudicator
source so a future re-run cannot re-lie.)

### T-15 — feature_math_lint floor GREEN

Three pre-existing failures closed:

| Failure | Fix |
|---|---|
| `test_floor_is_green` (4 wick re-derivations + 1 session) | Locals renamed: `upper_wick`/`lower_wick` → `sweep_uw_frac`/`sweep_lw_frac` in `detect_sweep` + `candle_geometry` (NOT `upper_wick_ratio` — that is itself FM-011/012 and re-trips the lint). Dead-module `session` local → `session_label`. |
| `test_pins_have_no_stale_durable_keys` (GD-006..009) | Pins **retired** via append-only `feature-math-grandfather-retirements.json` (same change that removed the sites). Remaining pin: GD-010 only. |
| `test_universe_reconciliation_with_census` (16 missing) | 16 Gate-2B adjudications appended to `geometry_semantic_adjudication.jsonl` for out-of-lint-universe registered-name derivations (scripts/tests/strategy/research). |

**Verified:** `tests/test_feature_math_lint.py` + `tests/test_btcusdt_crt_v3_handover.py` →
**23 passed, 7 skipped**. Lint report: `new_violations=0`, `stale_pins=0`, `current_pins=1`
(GD-010), `retired=9`. Behaviour-neutral renames only — no scoring/decision path change.

### Remaining OPEN on this tracker (do not invent work)

| ID | State | Why still open |
|---|---|---|
| **T-5 / T-6** | DEFERRED by user | warmup budget / finalize guard |
| **T-11 residual** | needs external feeder | `feed_schema_version` + batch/live period symmetry |
| **T-12** | PAUSED by user | (XAUUSD 2-month already ran — §13; item may be closable on review) |
| **T-17 / T-18** | FUTURE PHASE | macd_hist z-score semantics; volregime knobs |
| **T-19** | OPEN (semantic) | `candles_since_retest` misnamed — rename is schema-index-34 change |
| **T-21** | design gap, no live example | rolling_indicators remedy path; T-20 dissolved its only "evidence" |
| **M16 P1/P2/P3** | DEFERRED by user | consumer-alignment; still `BLOCKS_ACTIVATION: true` |
| **M16 P4+** | not started | superseded-vector migration etc. — large, own plan |

---

## 21. FREEZE + focus shift (2026-07-20)

| Artifact | Path |
|---|---|
| Freeze policy | `docs/governance/feature-layer-mutation-freeze-2026-07-20.md` |
| Freeze pin + benchmarks | `docs/governance/feature-layer-freeze-pin-2026-07-20.json` |
| Floor test | `tests/test_feature_layer_freeze.py` |
| Active engineering roadmap | `docs/implementation_plan/backtest-runtime-roadmap-2026-07-20.md` |
| Closure index surface | `FEATURE_LAYER_MUTATION_FREEZE` status **COMPLETE**, `frozen: true` |

**Freeze class:** `GOVERNANCE_FREEZE` — scientifically extensible via accepted programs /
waivers; not “never touch features again.”

**Feature regression pin (scope 2026-07-20b — XAUUSD only):**

| Corpus | Vector |
|---|---|
| `data/XAUUSD_W2026-03-23-to-2026-05-21.csv` | (3871, 38) float32 SHA `adad1a0b…` + coverage metadata |

**Removed from feature pin:** BNB head benchmark (belongs in runtime suite R-1/R-2).

**What freeze is not:** L6 activation, economic validation, full-path behavioral equivalence,
or clearance of M16 `BLOCKS_ACTIVATION` items. Coverage block on the pin lists paths
**not** exercised by the feature matrix hash.

**Default next work:** backtest/runtime roadmap R-1 / R-2 / R-3 (measurement honesty,
BNB gate ON/OFF *runtime* baselines, filter-stack map, F-048 intent decision).


================================================================================
SOURCE_FILE: docs/implementation_plan/for-only-this-session-dapper-possum.md
SOURCE_BYTES: 3731
PART: 4/10 FILE 13/16
================================================================================

# OHLCV load-path coverage assessment (report-only)

**User decision: report only, NO CODE.** This file is the deliverable, not an implementation plan.
It refreshes the validation-coverage matrix after the B1–B5 loader work and names what is still
pending. No source changes proposed.

## What changed since the last table

- **B1** moved header resolution to `ohlcv_schema.resolve_ohlcv_column_indices` (SSOT) — L1 is now
  one authority for every `CandleLoader.stream()` consumer; `tick_volume` resolves.
- **B4** added source/line context to numeric coercion (still L2-inline value).
- **B5** added mid-file-blank detection (new L2-inline sequence check).
- All three live *inside* `stream()`, so every Path-A consumer inherits them at once.

## The matrix is really TWO paths, not one

**Path A — `CandleLoader.stream()`** (row-streaming): backtest CLI, `config_validator`,
`portfolio_validation`, `exit_model_band`, `unified_replay_harness`, `sl_tp_comparator`, and the
research adapters (`spine_signal_source`, `structural_event_source`, `cross_sectional`,
`forensics`, `runner`).

| Path-A consumer | Pin | L1 presence | L2 value (+B4) | L2 sequence (+B5) | L3 preflight |
|---|---|---|---|---|---|
| backtest_v2 CLI | ✅ | ✅ | ✅ | ✅ | ✅ |
| research adapters | ✅ | ✅ | ✅ | ✅ | ❌ |
| validator/portfolio/exit_model/replay/sl_tp | ✅ | ✅ | ✅ | ✅ | ❌ |

**Path B — raw `pd.read_csv` → `FeaturePipeline`** (bypasses the loader): `zone_mapping/*`,
`ic002_entry_evolution/build_trajectories`, `secondlow_v1/detector`. Validation is
`FeaturePipeline._validate_input` only = `require_ohlcv_columns` + `pd.to_numeric` +
`validate_ohlcv_frame`.

| Path-B consumer | Pin | L1 presence | L2 value | L2 sequence | L3 preflight |
|---|---|---|---|---|---|
| `collect_trade_opened_features` | ✅ (guards) | ✅ | ✅ (NaN-coerce) | ❌ | ❌ |
| other zone_mapping / ic002 / secondlow | ❌ | ✅ | ✅ (NaN-coerce) | ❌ | ❌ |

(Within `backtest_v2` itself both paths run on the same file — the candle stream sequence-checks
what the feature DataFrame does not, so they cover each other. Standalone Path-B scripts have no
such cover.)

## Pending — ranked by materiality

1. **Path-B sequence + pin gap (MORE material).** Standalone raw-`read_csv` research scripts get
   **no duplicate / out-of-order / blank check** and **no corpus pin** (except one). A gappy,
   duplicated, or out-of-order file would flow into features silently. This is a genuine hole, not
   just a confidence gap — the inline backstop that protects Path A is simply absent here.
2. **L3-preflight gap on non-backtest Path-A consumers (F-039, LOWER).** Confidence only: per
   F-039's scope guard the inline L1/L2 backstop already enforces schema + chronology, so missing
   modal-timeframe / future-ts / gap-threshold analysis does **not** invalidate their results — it
   removes one net, not the net.

## Closed / not pending

- Header-alias drift (former B1 triplication) — **closed**, single authority.
- L2-inline value + sequence on Path A — **complete**, and now stronger (B4/B5).
- Corpus pin on all Path-A consumers — **present** (fires in `CandleLoader.__init__`).

## If remediation is ever wanted (not now)

- Path-B gap → a shared `load_validated_ohlcv_frame()` helper that runs the pin + full L1/L2
  (including sequence) before handing a DataFrame to `FeaturePipeline`; route the bypass scripts
  through it. Behaviour-changing (a tolerated-today gappy file would raise).
- L3 gap → call `dataset_integrity.validate_dataset` in the non-backtest Path-A entry points.
  Lowest value, widest surface; flips gappy files from WARN-and-run to REJECT.

Both deferred by the report-only decision.


================================================================================
SOURCE_FILE: docs/implementation_plan/from-claude-md-pick-curried-toast.md
SOURCE_BYTES: 15980
PART: 4/10 FILE 14/16
================================================================================

# Plan — Backtest a 2-month XAUUSD window + record the corpus-guard finding

## Context

Earlier this session we established the canonical XAUUSD corpus (`data/mt5/XAUUSD_M15.csv`,
sha `4d73f5ce…`, 47,275 rows) and built `scripts/analysis/export_xauusd_window.py`, which
produced a 2-month Excel export (3,949 rows, 2026-03-23 → 2026-05-21).

The user now wants that 2-month window run through `backtest_v2`. Two blockers were found:

1. **The corpus guard silently substitutes the full corpus.** `guard_xauusd_csv_path` is
   called at four sites in `backtest_v2`, and `is_xauusd_m15_request`
   ([xauusd_phase1_candidate.py:200-215](src/data_ingestion/xauusd_phase1_candidate.py:200))
   matches on filename prefix *with no extension check*, **and** on a second branch
   (`instrument == "XAUUSD"` AND `"M15"` in filename). Any such path is rewritten to the
   frozen 47,275-row corpus with only an `INFO` log. A user believing they ran a 2-month
   backtest would actually have run the full 2-year one.
2. **`.xlsx` cannot be read.** Three independent readers parse the input — `CandleLoader.stream`
   ([:723](src/runtime/backtest_v2.py:723), stdlib `csv`), `BacktestRunner.__init__`
   ([:1651](src/runtime/backtest_v2.py:1651), `pd.read_csv`), and the L2 integrity gate
   ([dataset_integrity.py:530](src/data_ingestion/dataset_integrity.py:530), stdlib `csv`).

**User decisions:** export CSV rather than teach three readers `.xlsx` (the L2 gate is the
one net remaining on most paths per F-039 — not where to add a format branch under time
pressure); and **log** the guard defect rather than fix it, in a new timestamped findings file.

Intended outcome: a real backtest over exactly the 2-month window, plus a recorded finding.

## Filename design (the non-obvious part)

The output name must satisfy three constraints simultaneously:

| Constraint | Requirement |
|---|---|
| Dodge guard branch 1 | must NOT start with `XAUUSD_M15` |
| Dodge guard branch 2 | must NOT contain `M15` (fires when `--instrument XAUUSD` is passed) |
| Keep L2 symbol parsing | `_parse_symbol_tf` ([dataset_integrity.py:456](src/data_ingestion/dataset_integrity.py:456)) does `stem.rsplit("_", 1)` — the text before the LAST underscore must be exactly `XAUUSD`. **CORRECTED 2026-07-18:** the reason originally given here — "or the market-class/session calendar is misdetected and the gap gate misfires" — was WRONG for gold. `classify_market` ([:114](src/data_ingestion/dataset_integrity.py:114)) only tests for a crypto quote suffix (USDT/USDC/BUSD), so a garbled XAUUSD symbol still resolves to `WEEKDAY`, identical to the clean one. **Actual** enforcement is `_check_path_consistency` ([:516](src/data_ingestion/dataset_integrity.py:516)): `instrument.upper() != symbol.upper()` is a HARD failure → REJECT. The wrong-calendar failure mode is real but applies only to CRYPTO symbols, where garbling breaks the suffix test. |
| **Canonical data root — MISSED in the first pass** | `_check_path_consistency` ([:506](src/data_ingestion/dataset_integrity.py:506)) requires the file to sit under `roots: ['data']`. The `results/` export **REJECTs** — confirmed by running `validate_dataset` on the shipped file. `backtest_v2` then aborts via `sys.exit(1)` ([:2811](src/runtime/backtest_v2.py:2811)) before streaming a single candle. The earlier "verification" checked guard passthrough but never ran the preflight gate. |

Chosen: **`XAUUSD_W2026-03-23-to-2026-05-21.csv`**
→ `rsplit("_",1)` = `("XAUUSD", "W2026-03-23-to-2026-05-21")` → symbol `XAUUSD` correct;
unparseable TF falls back to `default_bar_minutes: 15`
([v2_multi_2026_04.json:648](configs/production/v2_multi_2026_04.json:648)), which matches
the real modal delta, so the timeframe-consistency check passes. Dates stay in the filename.
`--instrument XAUUSD` still resolves `pip_size = 0.01`
([backtest_v2.py:2608](src/runtime/backtest_v2.py:2608)) — a fake instrument would silently
get the 0.0001 FX default, a 100x error in spread/slippage.

## Implementation

### 1. `scripts/analysis/export_xauusd_window.py` — add CSV output

- New `--format {xlsx,csv,both}`, default `xlsx` (existing behavior unchanged).
- CSV branch writes the guard-safe name above via `df.to_csv(index=False)`; xlsx branch keeps
  the current `XAUUSD_M15_{start}_to_{end}.xlsx` name.
- Reuse the existing `export_window()` slice logic verbatim — only the write step and the
  filename template branch. The source read stays `guard_xauusd_csv_path`-resolved, so the
  export is still provably a slice of the frozen corpus.
- Print the parent lineage (`parent_sha256=4d73f5ce…`, row range) alongside the output path.

### 2. Run the backtest

```
python src/runtime/backtest_v2.py \
  --csv results/XAUUSD/exports/XAUUSD_W2026-03-23-to-2026-05-21.csv \
  --instrument XAUUSD --output results/XAUUSD/backtests
```

Record in the run notes whether `BACKTEST_ENGINE_GATE` was on or off (F-037: `.env` sets `0`
⇒ CRT-only, no 4-engine fusion veto). Do **not** read `.env` — report the effective value from
the run's own config dump / log output.

**Expect a low trade count.** ~3,949 candles minus FeaturePipeline warmup (~254 rows, 6.4%
here vs 0.5% on the full corpus) minus HTF seed. This will land below the `min_trades` gates
in `config_validator`. That is an expected INSUFFICIENT-power result, not a bug — report it
as such and make no edge claim either way (§6.5 Authority Ladder).

### 3. New findings file

`docs/analysis/session-findings-2026-07-18-xauusd-window-backtest.md` — `docs/analysis/` is
the repo's home for point-in-time, non-living documents (§6.2 rule 5), which is what a
session-scoped findings file is. Same table shape as `docs/current-findings.md`
(id · type · conclusion · confidence · evidence · date).

Use **session-scoped IDs (`SF-001…`), not `F-0NN`.** An `F-` id would have to appear in both
`docs/current-findings.md` and the CLAUDE.md Repository Truths Index — `tests/test_current_findings.py`
enforces that correspondence in both directions, so minting one here would break the floor.
Note in the doc that any entry may be promoted to a real `F-` id later.

Entries to record:
- **SF-001 (ARCH):** the guard's extension-blind + instrument-branch substitution, with the
  `.xlsx` worked example and the `INFO`-only log line. Include that this session's export
  deliberately uses a guard-invisible filename, so the bypass is **declared, not silent** —
  with parent sha, row count, and exact time range as the derivation record (the G-10
  "declared synthesis is admissible, undeclared is the defect" rule).
- **SF-002 (ARCH):** `.xlsx` files in `data/` (e.g. `BNBUSDT_M15_2year.xlsx`) fail with an
  obscure `UnicodeDecodeError` rather than a clear "CSV only" error; three readers involved.
- **SF-003 (GOV):** carried-over drift from earlier this session — the stale
  `SECONDLOW_RESEARCH_DATA_POLICY.md:61-62` duplicate claim, and the two guard-bypassing
  scripts (`_enrich_xauusd_corpus.py:35`, `trace_zone_gate_xauusd.py:50`).

## Verification

1. Run the exporter with `--format csv`; confirm stdout reports source sha `4d73f5ce…`.
2. **Prove the guard did not swap the file** — the whole point:
   ```python
   from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path
   p = "results/XAUUSD/exports/XAUUSD_W2026-03-23-to-2026-05-21.csv"
   assert guard_xauusd_csv_path(p, "XAUUSD") == p   # unchanged => reaches the loader intact
   ```
3. Confirm the CSV is an exact row-for-row match to the existing .xlsx (same 3,949 rows).
4. Run the backtest. Confirm from the log that the loaded row count is ~3,949 and **not**
   47,275 — the direct falsification of blocker 1.
5. Inspect `results/XAUUSD/backtests/run_*/XAUUSD_summary.json` for trade count and metrics;
   state the count plainly and flag INSUFFICIENT power rather than reporting an edge.
6. `pytest tests/test_current_findings.py tests/test_session_log.py -q` — confirm the new
   findings file breaks neither floor (it shouldn't; it's a separate doc with non-`F-` ids).
7. Append the §6 SESSION LOG entry to `assistant_project.md`.

## Out of scope

- Fixing the guard (user chose log-only). SF-001 records it.
- `.xlsx` reader support — DEFERRED to future phases, see below.
- The two guard-bypassing research scripts and the stale SECONDLOW policy row (SF-003).
- MT5 integration — parked by the user for future paper-trade/automation phases.

---

## FUTURE PHASES (deferred, not scheduled)

Parked by the user 2026-07-18. Nothing below is started; each needs its own pre-registration
before implementation.

### FP-1 — Native `.xlsx` ingestion for `backtest_v2`

**Why deferred:** the current path is unblocked by exporting CSV instead
(`export_xauusd_window.py --format csv`), so this is a convenience/robustness item, not a
blocker. It touches the L2 integrity gate, which per F-039 is the single remaining net on
most `CandleLoader.stream()` consumers — not a change to make under time pressure.

**Real scope — FOUR readers, not one.** A single-instrument run reads the input file
start-to-finish four times, and every one is CSV-native:

| Pass | Call site | Reader | Purpose |
|---|---|---|---|
| 1 | `main` → `_preflight_dataset` ([backtest_v2.py:2811](../../src/runtime/backtest_v2.py)) | `open()` + `csv.reader` ([dataset_integrity.py:530](../../src/data_ingestion/dataset_integrity.py)) | L2 whole-sequence integrity gate |
| 2 | `BacktestRunner.__init__` ([:1651](../../src/runtime/backtest_v2.py)) | `pd.read_csv` | whole-frame `FeaturePipeline` (rolling windows) |
| 3 | `loader.count()` ([:790](../../src/runtime/backtest_v2.py)) | `open()` + line count | progress-bar row total |
| 4 | `loader.stream()` ([:723](../../src/runtime/backtest_v2.py)) | `open()` + `csv.reader` | sequential candle loop (no-lookahead) |

Passes 2 and 4 cannot be merged — 2 needs the whole frame for vectorized rolling windows,
4 must be sequential to preserve the no-lookahead guarantee. That opposition is why they
join on **timestamp string** rather than row index ([:1672](../../src/runtime/backtest_v2.py)).

**Work required:** a shared suffix-dispatching loader used by all four; the existing
`load_ohlcv` at [src/research/secondlow_v1/detector.py:44](../../src/research/secondlow_v1/detector.py)
is the closest pattern, but it sets `timestamp` as the **index**, which `FeaturePipeline`
rejects (it wants a timestamp *column*) — so it needs adapting, not reusing as-is. Plus
tests across both formats, and a decision on whether the L2 gate's strict row-by-row
validation is reproducible over a pandas-loaded frame.

**Latent bug this would fix (SF-002):** `data/` already contains `.xlsx` files
(`BNBUSDT_M15_2year.xlsx`, `BTCUSDT_M15_2year.xlsx`, `AUDUSD_M15_1year.xlsx`). Passing one
today produces a `UnicodeDecodeError` on ZIP bytes rather than a clear "CSV only" message.
A cheap partial win, independent of full support: an explicit suffix check in
`CandleLoader.__init__` that raises a readable error.

### FP-2 — Redundant-read cleanup (SF-004)

Pass 3 has no justification beyond a cosmetic progress percentage and is a full extra file
scan; `stream()` already knows how many rows it yielded. Also, all four passes independently
re-invoke `guard_xauusd_csv_path`, each re-hashing the full 47,275-row corpus (SHA-256 ×3–4
per run). Both are pure waste, but touching them means touching the hot path — needs a
parity proof (byte-identical ledger) per §6.5, not a casual edit.

### FP-4 — Close the timeframe-consistency gap (SF-005)

**Status: NEEDS TO FIX — deferred until the user's full analysis pass is done, 2026-07-18.**
**Decision made:** option (a) below — move the check into `CandleLoader.stream()`. Not yet
implemented; do not implement until the user says to resume this item.

CONFIRMED real gap, not present-and-missed. The modal-inter-bar-delta check exists and
works ([dataset_integrity.py:378-385](../../src/data_ingestion/dataset_integrity.py)) —
an M5 file mislabeled M15 is caught **when `validate_dataset` runs**. The gap is *reach*:
per F-039, that gate runs on only two call sites (`backtest_v2`'s `_preflight_dataset` /
`validate_universe`). Every other `CandleLoader.stream()` consumer — the entire
`src/research/` pipeline, `config_validator`, `portfolio_validation`,
`unified_replay_harness` — streams with only the **inline** L1/L2 backstop inside
`stream()` ([backtest_v2.py:759-770](../../src/runtime/backtest_v2.py)), which checks
duplicate/out-of-order timestamps but has **no timeframe check at all**. A mislabeled
file sails through those paths silently; every rolling-window feature
(RSI(14)/ATR(14)/MA(200)/the z-score windows) then computes over the wrong time span
with no error, no warning, nothing in the run's own logs to indicate it.

**Chosen fix — move the modal-delta check into `CandleLoader.stream()`'s always-on inline
backstop** ([backtest_v2.py:759-770](../../src/runtime/backtest_v2.py)), alongside the
existing duplicate/out-of-order checks, so it applies to **every** `stream()` caller —
not just the two `backtest_v2` entry points that currently opt into the separate
`validate_dataset` pre-flight. Rejected alternative: auditing + wiring `validate_dataset`
as a pre-flight call at each of the 5+ other consumer sites individually — matches the
existing "L2 is opt-in per caller" design but requires touching every call site instead
of the one shared streamer, and each site could drift again later.

**Implementation shape (for when this is picked up):** the modal-delta computation at
[dataset_integrity.py:378-385](../../src/data_ingestion/dataset_integrity.py) needs the
*whole* delta sequence (`statistics.mode(deltas)`), but `stream()` yields candles one at
a time — so it can't raise on the first bar the way duplicate/order checks do. Likely
shape: accumulate a bounded rolling window of deltas (or the running mode over what's
been seen so far) and raise once a stable modal mismatch is detected, OR require the
expected `bar_minutes` be passed into `CandleLoader.__init__` (already resolvable from
the filename via `_parse_symbol_tf`/`_TF_MINUTES`, or from config) and compare each
inter-candle delta against it directly — the latter is simpler and doesn't need to wait
for a mode to stabilize. Needs a parity check that existing correctly-labeled corpora
(BNB/ETH/BTC/SOL/EURUSD/XAUUSD) still pass unchanged — this touches shared code
(`ohlcv_schema.py` / `CandleLoader`), not a leaf script, so every `stream()` consumer is
in the blast radius.

### FP-5 — Duplicate-timestamp handling: VERIFIED already correct, no action needed

**User asked, 2026-07-18:** should a duplicate timestamp (same bar-time, two different
`close` values) stop execution with an error? **Answer: it already does, on two
independent layers, both verified by reading the enforcement code (not the docstring):**

1. L2 pre-flight ([dataset_integrity.py:341-345](../../src/data_ingestion/dataset_integrity.py))
   — first duplicate seen → `hard.append(...)` → `decision=REJECT` →
   `backtest_v2` `sys.exit(1)` before any candle streams.
2. Inline backstop in `CandleLoader.stream()`
   ([backtest_v2.py:764-767](../../src/runtime/backtest_v2.py)) — raises
   `DatasetIntegrityError` mid-stream on the second occurrence, independent of whether
   the pre-flight gate ran. This is what protects the F-039 non-preflighted consumers.

No implementation item here. Recorded so this doesn't get re-flagged as open work later.

### FP-3 — MT5 live/paper-trade integration

Parked. Read path (candles, deals) is live and load-bearing; write path (`MT5Bridge.send_order`,
[src/live/mt5_bridge.py:212](../../src/live/mt5_bridge.py)) is built but inert behind three
gates: `live_integration.mt5.enabled=false`, `dry_run=true`, and no non-test caller of the
live hook. Relevant when paper trading / automation testing on live data begins. See F-010
(live PnL UNVERIFIED).


================================================================================
SOURCE_FILE: docs/implementation_plan/from-mt5-terminal-we-drifting-hollerith.md
SOURCE_BYTES: 6032
PART: 4/10 FILE 15/16
================================================================================

# EXECUTION ownership claim — verification results + recording plan

## Context
An architecture summary was proposed for the EXECUTION stage (Feature Pipeline → engines → Fusion → Decision → ExecutionPlanner → `compute_crt_levels` → Ultron Risk Gate → MT5). I verified it against source, read-only. **Most of it is correct for the live path**, but it contains three factual errors and omits the single most important fact: **SL/TP has two independent implementations that disagree.** (My verification subagent died on the session limit; everything below I read directly.)

## Verdict

### Correct
- `ExecutionPlannerV1_2` produces **intent + entry + gate**, and explicitly **not** SL/TP — stated verbatim at `src/config_layer/execution_planner.py:8-9`, and its layer diagram (`:11-16`) matches the proposed chain exactly.
- Intent classes (BREAKOUT / PULLBACK / LIQ_SWEEP / REVERSAL) are decided there before geometry (`:6`).
- "Gate Intelligence → SL/TP" is right: `compute_crt_levels` lives at `src/core/gate_intelligence.py:24-84`.
- `Trade` carries entry / sl / tp1 / tp2 / risk_pct / direction (`crt_engine_v2.py:2276-2286`); lifecycle events `TRADE_OPENED` (`:3159`), `TRADE_TP1/TP2/STOPPED` (`:2683`), `TRADE_ABORTED` (`:2655`) all exist.
- TradeNet does not generate Entry/SL/TP.

### Wrong
1. **TradeNet does not participate before Fusion.** `EXPECTED_ENGINES = {"crt", "gaussian", "zone_gate", "rr"}` (`src/core/engine_runner.py:54`) — four engines, no TradeNet. `src/core/fusion_engine.py:8` calls the neural slot *"stubbed; plug TradeNet GGUF here"*. Consistent with **F-005 (Certain): TradeNet is BUILT but unwired.**
2. **`ExecutionPlanner → compute_crt_levels` is not a call edge.** `execution_planner.py` imports only the `GateIntelligence` *class* (`:34`), never the function. The actual caller is **`src/runtime/live_engine_hook.py:911`**.
3. **"Feature Pipeline (39 features) → CRT State Machine" is not the CRT spine.** `process_candle` consumes a `Candle` (OHLCV) — not a feature vector. `state.cached_features` is built *at RETEST* (`:1605-1629`) and holds 3–6 keys, not 39.

### The omission that matters: two SL/TP authorities

|  | Backtest CRT spine | Live path |
| --- | --- | --- |
| Caller | `process_candle:3153` | `live_engine_hook:911` |
| SL/TP producer | `ExecutionEngine.build_trade` (`crt_engine_v2.py:2191-2292`) | `compute_crt_levels` (`gate_intelligence.py:24-84`) |
| **SL anchor** | **displacement candle** `.low`/`.high` (`:2215`, `:2222`) | **current candle** `low`/`high` (`:914-915`) |
| ExecutionPlanner used? | No | Yes |
| `compute_crt_levels` used? | **No** — `crt_engine_v2` never imports `gate_intelligence` | Yes |

The two produce **different stops for the same setup** whenever the entry candle isn't the displacement candle — which is essentially always, since entry is the retest close (`:2202`). `build_trade`'s own comment (`:2204-2208`) states the doctrine the live path does not follow: *"SL anchored to displacement candle extreme… CRT doctrine: SL beyond the displacement candle = trade is structurally invalid."* This is the same duplicate-ownership class as `INV-009`, but semantic rather than structural.

### Documentation drift (2 instances, both in `gate_intelligence.py`)
- `:5-6` and `:37` claim `compute_crt_levels` *"mirrors crt_engine_v2.py lines 1162-1201 exactly."* Lines 1162-1201 are today inside `try_sweep_to_displacement`'s sweep-age and body_ratio guards — not SL/TP code at all. The real SL/TP is at `:2204-2258`. **Stale line citation.**
- `:6` and `execution_planner.py:8-9` both assert *"CRT is sole SL/TP authority."* False — `crt_engine_v2.ExecutionEngine.build_trade` is a second, independent authority. And "mirrors … exactly" is substantively wrong given the different SL anchor.

### Flagged, not re-verified this pass
A memory note (2026-07-29) records `compute_crt_levels` receiving close-relative ATR (FM-041) while treating it as price units → SL buffer ~2,343× too small on XAUUSD. `EngineState.atr_abs`'s own comment (`:244-249`) documents exactly this FM-041-vs-absolute-ATR confusion class. **Not re-confirmed here** — recorded as an open item requiring its own check, not asserted as fresh evidence.

## Recording plan (documentation only)

**Carry-over from the previous approved plan** (plan mode interrupted it — the `.md` invariants landed, the rest did not):
- `reports/crt_semantic_execution_reconstruction.json` — mirror `INV-006`…`INV-011` into `invariants[]` with a `verdict` field.
- Both files — add `FMODE-009 execution_deadend_on_build_trade_none` and `FMODE-010 shadow_memory_partial_teardown`.
- `.md` **Open Questions** — the `EXECUTION→RANGE` and unguarded-shadow-path items.

**New from this pass**, into the same two artifacts:
- `FMODE-011 dual_sl_tp_authority_divergent_anchor` — the two implementations and the displacement-vs-current-candle anchor split, with the table above.
- `DRIFT-004` — `gate_intelligence.py:5-6,37` stale line citation (1162-1201 → 2204-2258).
- `DRIFT-005` — the "sole SL/TP authority" claim contradicted by `build_trade`.
- **Open Questions** — whether the live path's current-candle SL anchor is intentional or drift from the CRT doctrine `build_trade` states; and the FM-041 ATR-basis item above.

No `docs/current-findings.md` entry this pass: these are descriptive architecture observations, and registering the anchor divergence would imply a remediation decision that is the user's (§6.5 — observation grants no authority).

## Verification
- Every line cited was read in source this session; no claim rests on a code comment alone — the two drift items are precisely *comments contradicted by source*.
- After editing: JSON parses, `invariants[]` = 11, `failure_modes[]` = 11, `drift_records[]` = 5, `.md` section count unchanged at 16.
- Strictly descriptive: no `src/`, config, `params`, or `ACTIVE_VERSION` change; no fix to the anchor divergence, the dead-end, or the teardown paths; no promotion.


================================================================================
SOURCE_FILE: docs/implementation_plan/FULL_BUILD_SPECIFICATION.md
SOURCE_BYTES: 105041
PART: 4/10 FILE 16/16
================================================================================

# Full Build Specification: Domain-First Trading Architecture

> **Purpose:** This document is the complete, unredacted specification for transforming
> the Tradelatest codebase from a strategy-centric monolithic system to a domain-first,
> evidence-linked, n8n-orchestrated trading architecture.
>
> **How to use:** Give this entire document to Claude LLM (or any coding agent). It contains
> every decision, every schema, every risk, and every checklist. The agent must implement
> each story in order, validate each checklist, and log every action.
>
> **Source:** Full conversation 2026-06-15 (Plan Mode). Every question, answer, and decision
> captured below.
>
> **Status:** Specification complete. Ready for implementation.
> **Total effort:** ~220 hours across 44 stories, 10 epics
> **New code:** ~4,640 lines across 38 new files, 32 modified files
> **Architecture risk:** 2 high-risk stories (5.4, 8.1) — both behind feature flags

---

# Table of Contents

1. [Conviction Statement](#1-conviction-statement)
2. [The Architecture Inversion Problem](#2-the-architecture-inversion-problem)
3. [Target Architecture](#3-target-architecture)
4. [Foundational Documents Already Written](#4-foundational-documents-already-written)
5. [Codebase Readiness Audit](#5-codebase-readiness-audit)
6. [Implementation Ritual](#6-implementation-ritual)
7. [Epic 1: Repair the Spine](#7-epic-1-repair-the-spine)
8. [Epic 2: Wire or Remove Dead Config](#8-epic-2-wire-or-remove-dead-config)
9. [Epic 3: Framework Registry + Findings Applier](#9-epic-3-framework-registry--findings-applier)
10. [Epic 4: Domain Layer Extraction](#10-epic-4-domain-layer-extraction)
11. [Epic 5: Style Layer + Strategy Reorganization](#11-epic-5-style-layer--strategy-reorganization)
12. [Epic 6: n8n Integration](#12-epic-6-n8n-integration)
13. [Epic 7: Claude Gate Integration](#13-epic-7-claude-gate-integration)
14. [Epic 8: Enable UltronRiskGate + Wire Portfolio](#14-epic-8-enable-ultronriskgate--wire-portfolio)
15. [Epic 9: Documentation + Validation](#15-epic-9-documentation--validation)
16. [Epic 10: Findings Integration](#16-epic-10-findings-integration)
17. [JSONL Registry Schema Reference](#17-jsonl-registry-schema-reference)
18. [Claude Gate Prompt Templates](#18-claude-gate-prompt-templates)
19. [Troubleshooting Guide](#19-troubleshooting-guide)
20. [Audit Trail Template](#20-audit-trail-template)
21. [Implementation Order (Critical Path)](#21-implementation-order-critical-path)

---

# 1. Conviction Statement

**The goal:** Transform the codebase from a strategy-centric monolithic system to a domain-first,
evidence-linked trading architecture where every component is documented, classified, validated,
and traceable. The registry drives execution. Findings steer behavior. n8n orchestrates workflows.
Claude LLM tweaks only when config gates trigger.

**Why this matters (from the user's own words):**
- "Different markets require different assumptions. Strategies are domain-dependent. AI should sit
  above the domain and strategy layers, not define them."
- "Your current architecture may be too strategy-centric."
- "Trading systems are usually overfit because they start with indicators. Robust systems start
  with domain → style → strategy → implementation."
- Research findings F-019 through F-028 show the current ontology has been empirically falsified
  for crypto majors under realistic costs. The system works correctly but the *domain assumptions*
  were wrong.

**What success looks like:**
1. Registry coverage = 100% — every production module in `src/` has a registry entry
2. Gap audit = 0 P0 items — no architecture inversions (CRT as mandatory engine is P0)
3. Validation passes — evidence paths exist, findings are linked, no dangling references
4. 1208/1208 tests passing (23 failures fixed)
5. n8n orchestrates the full pipeline: data → tune → validate → Claude gate → promote → live
6. UltronRiskGate enabled and non-bypassable

**The ritual:**
```
Document → JSONL → Checklist → Logs → Validation → Next Phase
```

---

# 2. The Architecture Inversion Problem

## 2.1 Wrong Order (Current Codebase)

The current architecture builds the system around tools, not around the problem:

```
CRT Engine → Gaussian → Zone Gate → RR Engine → everything else
```

These 4 engines are treated as the **foundation** (mandatory, `EXPECTED_ENGINES` hardcoded).
Everything else is bolted on top.

**Consequences (proven by research):**
- F-019: No edge on crypto majors under realistic costs
- F-020: No candle-conditional directional pocket on crypto majors
- F-021: Spine RETEST selection = session filter only (no score/zone skill)
- F-025: Exit/cost is a risk lever, NOT expectancy
- F-026: CRT retest adds no forward asymmetry beyond sweep
- F-027: Coarser timeframes do NOT rescue the directional edge
- F-028: First real interpreter (P&F) carries NO standalone edge

The architecture *faithfully implements* the chosen market ontology — but that ontology has been
empirically falsified for crypto majors. This is not a code bug. It's an architecture inversion.

## 2.2 Correct Order (Target)

```
Level 0: Universal Trading Kernel       (domain-independent plumbing)
Level 1: Market Domain Layer            (crypto / forex / equities / futures / options)
Level 2: Trading Style Layer            (trend / reversion / momentum / reaction / stat-arb)
Level 3: Strategy Layer                 (concrete rule sets per style)
Level 4: Intelligence / AI Layer        (regime / drift — advisory only)
Level 5: Risk Layer                     (pre-trade, in-trade, portfolio)
Level 6: Execution Layer                (order dispatch, venue routing, slippage model)
```

**CRT/Gaussian/Zone/RR are no longer mandatory engines.**
They become strategy plugins under specific styles. CRT becomes a strategy under ReactionBased
style. Gaussian becomes a fused signal (if useful) or a strategy plugin.

## 2.3 The User's Framework (from conversation)

```
Market Domain
    ↓
Trading Style
    ↓
Strategy
    ↓
Implementation
```

This is the one-sentence version of the full 6-level hierarchy. Every architecture decision
must pass this test: "Does this serve the domain first, or the strategy first?"

---

# 3. Target Architecture

## 3.1 Complete End-to-End Flow

```
n8n (Docker, localhost:5678)
    │
    ├── Trigger: Scheduled (daily 02:00 UTC) / Webhook (user click)
    │
    ├── [Stage 1: Data Prep]           HTTP POST → control_plane:/api/run-stage
    ├── [Stage 2: Tuning]              Parallel 4 instruments
    ├── [Stage 3: Claude Gate]         HTTP POST → Claude API (Anthropic)
    │   ├── Decision: tweak → re-run Stage 2
    │   ├── Decision: promote → Stage 4
    │   └── Decision: escalate → notify user
    ├── [Stage 4: Validate + Promote]
    └── [Stage 5: Live Runner]
    │
    ▼
Control Plane (localhost:8787)
    │
    ├── POST /api/run-stage      → runs script, returns {status, metrics, config}
    ├── POST /api/claude-gate    → calls Anthropic API, returns decision
    ├── GET  /api/registry       → query framework registry
    └── GET  /api/status         → current system state
    │
    ▼
Framework Registry (data/framework_registry.jsonl)
    │
    ├── Query: get_tree("DOMAIN-001")           → full CryptoSpot hierarchy
    ├── Query: find_by_finding("F-026")         → which components affected
    ├── Query: get_orphaned()                   → dead/waste modules
    └── Query: get_active_strategies(domain)    → what to run
    │
    ▼
FindingsApplier (src/governance/findings_applier.py)
    │
    ├── Reads findings from registry records
    ├── Computes effective weights/configs
    │   ├── F-026 → CRT weight: 1.0 → 0.3
    │   ├── F-021 → sessions: all → London/NY/Overlap only
    │   └── F-025 → SL floor: 1x → 2x ATR minimum
    └── Two modes: RESEARCH (shadow) or ACTIVE (live)
    │
    ▼
Engine Spine (reads registry + findings)
    │
    ├── Domain → CryptoSpot
    ├── Styles → [ReactionBased, Breakout, MeanReversion]
    ├── Strategies per style → [CRT, LiquiditySweep, RSI+BB, ...]
    ├── Apply findings → modified weights + restrictions
    └── Run only strategies with weight > 0
    │
    ▼
Risk Layer (non-bypassable)
    │
    ├── PreTradeRiskGate (UltronRiskGate — ENABLED)
    ├── InTradeRisk (breakeven, trailing, time stop)
    └── PortfolioRisk (exposure, concentration, correlation)
    │
    ▼
Execution Layer
    │
    ├── Order dispatch (market/limit/iceberg)
    ├── Slippage model (dynamic, spread-based)
    └── Audit (JSONL per trade)
    │
    ▼
Feedback Loop
    │
    ├── Backtest → metrics
    ├── Metrics → new finding or validate existing
    ├── Finding → registry → findings applier → engine
    └── Loop
```

## 3.2 Key Design Decisions (from conversation)

| Decision | Why | Source |
|----------|-----|--------|
| n8n orchestrates, not Python | Visual workflow, parallel branches, built-in LLM nodes | User: "n8n workflow Claude LLM only tweak required ones" |
| Claude calls ONLY when needed | Avoid unnecessary API costs; Claude is a gate, not the engine | User: "Claude LLM only tweak required ones" |
| 4 parallel branches | Tune 4 instruments (BNB, BTC, ETH, SOL) simultaneously | User: "parallel 4" |
| Local n8n Docker | File-backed, no cloud deps, matches existing architecture | User: "n8n in local" |
| Anthropic API for Claude | Existing GROQ key but user chose Claude | User: "Claude API (Anthropic)" |
| Registry is JSONL | Append-only, evidence-linked, queryable, matches existing JSONL pattern | User: "JSONL advantages — link till evidences, map entire codebase" |
| Findings as directives | Natural language: when to trade, when to risk, when NOT to trade + confidence | User: "share direction of finding in sentence" |
| Findings drive engine behavior | Not just documentation — findings modify configs/weights at runtime | User: "The engine reads the registry and executes what it finds" |
| Document → JSONL → Checklist → Logs → Validation → Next | Never skip a step. Every phase follows this ritual. | User: "Document jsonl checklist logs validation next phase" |
| Control plane stays alongside n8n | n8n doesn't replace existing UI. Both serve different purposes. | User: "sitalong side" |
| Codebase fixes first | 23 failing tests + dead config must be fixed before n8n layer can be trusted | User: "if any bugs or not as intended then results will be not trusted" |

---

# 4. Foundational Documents Already Written

These files exist and are referenced throughout this specification:

| File | Content | Authoritative For |
|------|---------|-------------------|
| `docs/architecture/TRADING_SYSTEM_FRAMEWORK.md` | Complete 6-level hierarchy with ABC contracts, schemas, end-to-end flow | Level definitions, component boundaries |
| `docs/implementation_plan/001_FRAMEWORK_REGISTRY.md` | Original phased plan for registry + gap audit | Milestone structure, file inventory |
| `docs/current-findings.md` | F-001 through F-029 with evidence and confidence | All active findings |
| `docs/STRATEGIES.md` | S01-S10 strategy modules | Strategy descriptions, config mapping |
| `reports/hidden_wiring_audit.md` | 20 dead/orphaned config sections | Everything that needs to be wired or removed |
| `docs/intent/100_execution.md` | Execution domain contract | Must/MustNever requirements for the spine |
| `docs/intent/200_risk.md` | Risk domain contract | Risk gate requirements |
| `CLAUDE.md` | Master context file, session log mandate | Operating conventions |
| `docs/architecture/signal-flow.md` | End-to-end candle→order flow | Pipeline order, module boundaries |

---

# 5. Codebase Readiness Audit

## 5.1 Test Results (from `pytest_output.txt`)

**1231 collected, 1188 passed, 23 failed, 18 skipped, 2 xfailed**

### Failed Tests Detail

```
FAILED tests/features/test_feature_schema_registry.py::test_unregistered_fail_open
    → Feature schema registry's unregistered-feature fallback doesn't match test.
    → Files: 1 (test or src/features/)
    → Fix: ±5 lines, 0.5h

FAILED tests/replay/test_replay_memory_engine.py::test_cluster_stats_built
FAILED tests/replay/test_replay_memory_engine.py::test_decay_weighting
    → Replay memory engine cluster stats and decay weighting broken.
    → Sidecar only (F-012: zero spine consumption).
    → Files: 1 (src/replay/)
    → Fix: ±15 lines, 2h

FAILED tests/test_engine_runner_dual_gate.py::test_dual_gate_trend_selects_breakout
FAILED tests/test_engine_runner_dual_gate.py::test_dual_gate_range_selects_trap
FAILED tests/test_engine_runner_dual_gate.py::test_dual_gate_neutral_low_confidence_rejects
FAILED tests/test_engine_runner_dual_gate.py::test_layered_flow_fusion_runs_before_dual_veto
    → Dual gate mode selection logic broken.
    → Secondary path behind fusion_use_evaluate flag.
    → Files: 1 (src/core/engine_runner.py)
    → Fix: ±15 lines, 3h

FAILED tests/test_engine_runner_rr_fusion.py::test_rr_fusion_applies_score_before_fusion
FAILED tests/test_engine_runner_rr_fusion.py::test_rr_fusion_failure_falls_back_to_base_rr
FAILED tests/test_engine_runner_rr_fusion.py::test_fusion_compare_mode_records_evaluate_shadow
FAILED tests/test_engine_runner_rr_fusion.py::test_fusion_use_evaluate_overrides_final_score
    → RR fusion scoring pipeline bug.
    → Files: 1 (src/config_layer/rr/ or src/core/fusion_engine.py)
    → Fix: ±20 lines, 3h

FAILED tests/test_gaussian_impl_switch.py::test_engine_runner_ml_impl
    → Gaussian engine switching regression.
    → Files: 1 (src/engines/ or engine_runner.py)
    → Fix: ±10 lines, 2h

FAILED tests/test_llm_connectivity.py::TestLlmScore::test_unparseable_output_returns_one
FAILED tests/test_llm_connectivity.py::TestLlmScore::test_timeout_returns_one
FAILED tests/test_llm_connectivity.py::TestLlmScore::test_url_error_returns_one
FAILED tests/test_llm_connectivity.py::TestLlmScore::test_generic_exception_returns_one
FAILED tests/test_llm_connectivity.py::TestLlmScore::test_failopen_when_both_backends_down
FAILED tests/test_llm_connectivity.py::TestGroqScore::test_unparseable_returns_one
FAILED tests/test_llm_connectivity.py::TestGroqScore::test_unavailable_returns_one_empty
FAILED tests/test_llm_connectivity.py::TestGroqScore::test_request_error_returns_one
FAILED tests/test_llm_connectivity.py::TestLlmScoreSafe::test_server_down_returns_one_fail_open
FAILED tests/test_llm_connectivity.py::TestLlmScoreSafe::test_timeout_returns_one_fail_open
FAILED tests/test_llm_connectivity.py::TestLlmScoreBatch::test_server_down_safe_mode
    → 10 failures. Fallback returns 0.5 but tests expect 1.0.
    → Code was changed (fallback 1.0→0.5) but tests weren't updated.
    → This is a contract ambiguity, not a runtime bug.
    → Files: 1 (src/engines/llm_inference_client.py or tests/)
    → Fix: ±10 lines, 1h
```

**Total to fix:** 23 failures, ±75 lines across 6 files, ~11.5 hours.

## 5.2 Known Architecture Issues (from reports)

### Dead/Unwired Config (must fix before n8n can be trusted)

| Config Section | Problem | Impact | Found In |
|----------------|---------|--------|----------|
| `capital_management` | COMPLETELY UNWIRED. Daily loss limit, max risk per trade, kill-switch thresholds never read | Tuning kill-switch params has zero effect | hidden_wiring_audit.md #1 |
| `data_ingestion` | References nonexistent PostgreSQL. Codebase has NO database | Misleads developers | hidden_wiring_audit.md #2 |
| `gate_intelligence` | No consumer in the spine. Designed as signal filter but bypassed | Tuning gate weights does nothing | hidden_wiring_audit.md #3 |
| `sl_tp_comparison` | Self-declares dead ("used ONLY by SLTPComparator, never in live path") | Analytical only, but pollutes config | hidden_wiring_audit.md #4 |
| `strategy_engine.s01..s10` | Advisory only — consensus may not be invoked (65% probability) | Tuning 10 strategies may be decorative | hidden_wiring_audit.md #5 |
| `regime_fusion_weights` | Exists in config but NEVER read by FusionEngine | Regime-adaptive weighting has zero effect | hidden_wiring_audit.md #6 |
| `PROMOTION_MARGIN=2%` | Hardcoded in model_registry.py, not configurable | Can't tune without editing Python | hidden_wiring_audit.md #7 |
| `ultron_gate_enabled: false` | Risk gate disabled in active production config | Capital protection bypassed | Active config line 66 |

### Active Findings (F-001 to F-029, from `docs/current-findings.md`)

| Finding | Conclusion | Affects Building n8n? | Action Required |
|---------|-----------|----------------------|-----------------|
| F-001 | Intelligence is NOT the binding constraint | Informational | None |
| F-002 | Edge is in decision PROCESS, not feature→outcome map | Design validation | Ensure findings applier doesn't optimize wrong things |
| F-004 | BitNet is LIVE hard-reject gate (score < 0.55) | Architecture | BitNet stays as AI advisory layer |
| F-005 | TradeNet v2 built but unwired | Waste tracking | Registry will show as orphaned |
| F-006 | config_integrity is real but ORPHANED | Must fix | Wire or remove |
| F-008 | Concept drift DETECTED but NOT acted on | Must fix | Wire drift → action |
| F-010 | Live PnL UNVERIFIED | Must fix | Execution quality model needed |
| F-012 | ReplayMemory/CognitiveBus/Cluster/HMF sidecar-only | Informational | Registry marks as sidecar |
| F-013 | PortfolioAllocator built but ORPHANED | Must fix | Wire into spine (Story 8.2) |
| F-016 | Active config = v2_multi_2026_04 (patch) | Version truth | Ensure registry references this version |
| F-019 | No edge on crypto majors under cost | Business impact | n8n may find no edge to promote |
| F-021 | RETEST selection = session filter only | Strategy guidance | CRT deweight, sessions restricted |
| F-025 | Exit/cost is risk lever, not expectancy | Risk guidance | SL floor = 2x ATR |
| F-026 | CRT retest adds NO forward asymmetry | Strategy guidance | CRT weight reduced to 0.3 |

## 5.3 Existing Components Ready for n8n

These scripts already work as CLI commands and can be called by n8n immediately:

| Component | Path | n8n Call Method | Args |
|-----------|------|----------------|------|
| Data Prep | `scripts/data/prepare_data.py` | `python scripts/data/prepare_data.py --source binance --instrument BNBUSDT` | --source, --files, --instrument, --output, --already-m15, --validate-only |
| Unified Data Builder | `scripts/data/unified_data_builder.py` | `python scripts/data/unified_data_builder.py EURUSD GBPUSD` | instruments positional, --data-dir, --output-dir, --validate-only, --dry-run |
| Auto Tuner Multi | `scripts/training/auto_tuner_multi.py` | `python scripts/training/auto_tuner_multi.py --instrument BNBUSDT --n-iter 100` | --csv, --instrument, --data-dir, --instruments, --output-dir, --n-iter, --seed, --workers, --train-split, --no-llm |
| Auto Tuner | `scripts/training/auto_tuner.py` | `python scripts/training/auto_tuner.py --instrument BNBUSDT --n-iter 100` | --csv, --instrument, --data-dir, --instruments, --output-dir, --n-iter, --seed, --resume, --multi, --verbose |
| Config Validator | `src/config_layer/config_validator.py` | `python src/config_layer/config_validator.py validate-prod` | subcommand positional, --data-dir, --version, --output |
| Promotion Manager | `src/governance/promotion_manager.py` | `python src/governance/promotion_manager.py promote --checkpoint ...` | promote/from-report/list/load subcommands |
| Backtest v2 | `src/runtime/backtest_v2.py` | `python src/runtime/backtest_v2.py --csv data/BNBUSDT_M15.csv` | --csv, --config, --output-dir |
| Fetch Crypto | `scripts/data/fetch_crypto_ccxt.py` | `python scripts/data/fetch_crypto_ccxt.py --instrument BNBUSDT` | --all, --instrument, --start, --end, --append |
| Fetch Forex | `scripts/data/fetch_forex_yfinance.py` | `python scripts/data/fetch_forex_yfinance.py --instrument AUDUSD` | --all, --instrument, --start, --end, --append |
| Opportunity Scanner | `scripts/auto_train_from_opportunities.py` | `python scripts/auto_train_from_opportunities.py` | various args |
| Live Engine Hook | `src/runtime/live_engine_hook.py` | `python src/runtime/live_engine_hook.py` | various args |

---

# 6. Implementation Ritual

**Every story follows this exact sequence. Do not skip steps.**

```
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: DOCUMENT                                             │
│   Write the design/spec as a doc or update existing doc.     │
│   Include: purpose, schema, contract, failure modes.         │
│   Output: docs/.../*.md                                      │
├─────────────────────────────────────────────────────────────┤
│ STEP 2: JSONL                                                 │
│   Update data/framework_registry.jsonl with the new          │
│   component. Include evidence links (file:line) and          │
│   parent/children references.                                │
│   Output: data/framework_registry.jsonl (+1 line)            │
├─────────────────────────────────────────────────────────────┤
│ STEP 3: IMPLEMENT                                             │
│   Write and commit the code.                                 │
│   Follow the contracts from the framework document.          │
│   Add feature flags for risky changes.                       │
│   Output: code changes                                       │
├─────────────────────────────────────────────────────────────┤
│ STEP 4: CHECKLIST                                             │
│   Run through the story's checklist. Mark each item.         │
│   Do not proceed until all checkboxes are ✓.                 │
│   Output: checklist in story doc                             │
├─────────────────────────────────────────────────────────────┤
│ STEP 5: LOGS                                                  │
│   Append session log entry to assistant_project.md.          │
│   Include: what was built, what changed, what risks remain.  │
│   Output: assistant_project.md (+1 entry)                    │
├─────────────────────────────────────────────────────────────┤
│ STEP 6: VALIDATION                                            │
│   Run all affected tests. Run full regression.               │
│   For risky changes: byte-identity backtest verification.    │
│   Output: test results + verification report                 │
├─────────────────────────────────────────────────────────────┤
│ STEP 7: NEXT                                                  │
│   Only proceed to next story when validation passes.         │
│   If validation fails: fix → re-validate → then proceed.    │
│   Output: "Ready for story N+1"                              │
└─────────────────────────────────────────────────────────────┘
```

---

# 7. Epic 1: Repair the Spine

**Goal:** Fix all 23 failing tests so the codebase produces trustworthy results.
**Total:** 6 stories, 6 files modified, ±75 lines, 11.5 hours.
**Prerequisite for:** All other epics. Nothing gets built on a broken foundation.

## Story 1.1: Fix LLM Connectivity Test Contract

**Files:** `src/engines/llm_inference_client.py` or `tests/test_llm_connectivity.py`
**Lines:** ±10 lines
**Time:** 1 hour
**Confidence:** 95%

**Problem:** 10 tests fail because fallback returns 0.5 but tests expect 1.0. The code was changed
(fallback from 1.0 to 0.5) but tests weren't updated.

**Decision needed:** Is the correct fallback behavior 0.5 (neutral abstention) or 1.0 (pass)?
- Look at `src/engines/llm_inference_client.py` and the `_groq_score` / `llm_score` functions.
- The log says: "all backends failed... Returning 0.5 (neutral abstention)."
- If 0.5 is intentional (neutral = doesn't influence fusion), update tests to expect 0.5.
- If 1.0 is required (fail-open = pass), update code to return 1.0.

**Checklist:**
- [ ] Determine correct fallback value (check with user or FusionEngine contract)
- [ ] Update either code or tests to match
- [ ] All 10 LLM connectivity tests pass
- [ ] Regression: remaining 1200+ tests pass

**Evidence to update in registry:**
- `src/engines/llm_inference_client.py` — update evidence line reference if code changed

---

## Story 1.2: Fix Dual Gate Engine Runner

**Files:** `src/core/engine_runner.py` (dual gate section, ~20 lines)
**Lines:** ±15 lines
**Time:** 3 hours
**Confidence:** 70%

**Problem:** `test_engine_runner_dual_gate.py` has 4 failures in trend/range selection and fusion flow.
The dual gate (regime-aware strategy selection) has a logic bug.

**Root cause investigation:**
1. Read the failing test assertions — what exact value does each test expect vs receive?
2. Trace `engine_runner.py` dual gate flow: where does it decide trend vs range vs neutral?
3. Is `fusion_use_evaluate` flag affecting this path? (It defaults to FALSE in config)
4. Are the regime labels from the regime classifier matching the test expectations?

**Checklist:**
- [ ] Identify root cause of each failure
- [ ] Fix dual gate logic
- [ ] All 4 dual gate tests pass
- [ ] Dual gate runs behind feature flag (`fusion_use_evaluate` or new flag)
- [ ] Byte-identity backtest verified (BNBUSDT + SOLUSDT) — should be unchanged since dual gate is secondary path

**Critical constraint:** The dual gate is a secondary path. The primary path (fusion_compare)
must NOT be affected by this fix. If the fix requires changing the primary path, stop and escalate.

---

## Story 1.3: Fix RR Fusion Scoring

**Files:** `src/config_layer/rr/rr_fusion.py` or `src/core/fusion_engine.py`
**Lines:** ±20 lines
**Time:** 3 hours
**Confidence:** 65%

**Problem:** `test_engine_runner_rr_fusion.py` has 4 failures in score application and fallback.

**Root cause investigation:**
1. The tests cover: score-before-fusion, fallback-to-base-rr, compare-mode, evaluate-mode
2. Find which method is producing wrong scores
3. Is `rr_fusion.enabled` flag affecting this? (Current config: `"enabled": true`)
4. Is the issue in `RREngine` or `RRFusionLayer`?

**Checklist:**
- [ ] Identify root cause
- [ ] Fix RR fusion scoring pipeline
- [ ] All 4 RR fusion tests pass
- [ ] Byte-identity backtest verified (RR fusion affects final scores)

**Risk:** If RR fusion is fundamentally broken (not just a logic bug), the fix may require larger
refactor. In that case: disable RR fusion (`rr_fusion.enabled: false`), fix the 4 tests to pass
with disabled fusion, and open a separate tech debt story.

---

## Story 1.4: Fix Gaussian Implementation Switch

**Files:** `src/engines/ml_gaussian_engine.py` or `src/core/engine_runner.py` (switch logic)
**Lines:** ±10 lines
**Time:** 2 hours
**Confidence:** 80%

**Problem:** `test_gaussian_impl_switch.py` fails — ML vs heuristic Gaussian engine switch broken.

**Root cause investigation:**
1. The switch is controlled by `gaussian_impl` config key ("ml" vs "heuristic")
2. Find where the switch is evaluated in `engine_runner.py` or Gaussian engine loader
3. Is it a renamed method? Changed import? Wrong conditional?

**Checklist:**
- [ ] Identify root cause
- [ ] Fix Gaussian implementation switch
- [ ] Test passes for both "ml" and "heuristic" modes
- [ ] Byte-identity backtest verified

---

## Story 1.5: Fix Replay Memory Engine Failures

**Files:** `src/replay/replay_memory_engine.py`
**Lines:** ±15 lines
**Time:** 2 hours
**Confidence:** 90%

**Problem:** `test_cluster_stats_built` and `test_decay_weighting` fail. Sidecar code (F-012).

**Root cause investigation:**
1. These are sidecar components — zero impact on trading spine
2. Likely a refactoring regression (renamed method or changed return type)
3. Fix is straightforward: align code with test expectations

**Checklist:**
- [ ] Fix `test_cluster_stats_built`
- [ ] Fix `test_decay_weighting`
- [ ] All replay tests pass
- [ ] No spine code touched

---

## Story 1.6: Fix Feature Schema Registry Test

**Files:** `tests/test_feature_schema_registry.py` or `src/features/feature_schema_registry.py`
**Lines:** ±5 lines
**Time:** 0.5 hours
**Confidence:** 95%

**Problem:** `test_unregistered_fail_open` fails. Unregistered-feature fallback doesn't match test.

**Checklist:**
- [ ] Fix assertion or behavior
- [ ] Test passes
- [ ] All feature schema tests pass

---

# 8. Epic 2: Wire or Remove Dead Config

**Goal:** Every config section has a consumer. No decorative config.
**Total:** 6 stories, 10 files (+1 new, +9 modified), +200/-50 lines, 20 hours.
**Prerequisite for:** Registry seeding (Epic 3) — if config is dead, registry entry must say so.

## Story 2.1: Wire `capital_management` into UltronRiskGate

**Files:**
- NEW: `docs/reference/capital_management_schema.md` (+80 lines)
- MODIFIED: `src/core/ultron_risk_gate.py` (+40 lines)
- MODIFIED: `src/config_layer/production_config.py` (+5 lines)

**Lines:** +125, -0
**Time:** 6 hours
**Confidence:** 85%

**What to build:**
1. `capital_management_schema.md` — document every field (total_capital_inr, max_risk_per_trade_pct,
   kill_switch_daily_loss_inr, kill_switch_monthly_drawdown_pct, position_sizing_method)
2. In `UltronRiskGate.evaluate()`, add 3 new checks before the existing 7:
   - Daily loss check: if today's PnL < -max_daily_loss_pct * total_capital → REJECT
   - Monthly drawdown check: if equity curve drawdown > max_monthly_drawdown_pct → REJECT
   - Max risk per trade check: if proposed position risk > max_risk_per_trade_pct → size down
3. `from_prod_config` should read `capital_management` section from production config

**Critical design decision:**
- If `capital_management` keys are missing or zero, what happens?
- Answer: If value is 0 or negative, treat as "no limit" (backward compatible).
- If section is entirely missing, log a warning but don't crash (fail-open, same as existing pattern).

**Checklist:**
- [ ] `capital_management_schema.md` written
- [ ] 3 new checks added to `UltronRiskGate.evaluate()`
- [ ] Missing/zero values treated as "no limit" (backward compatible)
- [ ] Existing UltronRiskGate tests still pass
- [ ] New tests for capital management checks added
- [ ] Byte-identity backtest verified (capital management checks are new, but all values may be zero
      in active config → behavior unchanged)

---

## Story 2.2: Remove `data_ingestion` Config Section

**Files:**
- MODIFIED: `configs/production/v2_multi_2026_04.json` (-25 lines)
- MODIFIED: `docs/reference/config-reference.md` (-1 section)

**Lines:** +0, -30
**Time:** 1 hour
**Confidence:** 95%

**What to do:**
1. Search entire codebase for `data_ingestion` references (config keys, imports, etc.)
2. If NO references found: delete the section from config and config-reference.md
3. If references found: deprecate instead of delete (add `_deprecated: true` to section)

**Checklist:**
- [ ] Searched codebase for `data_ingestion` references
- [ ] If no references: section deleted
- [ ] If references found: section deprecated, not deleted
- [ ] Tests pass (no import regression)

---

## Story 2.3: Wire or Remove `gate_intelligence`

**Files:**
- MODIFIED: `src/core/engine_runner.py` (+30 lines if wired)
- MODIFIED: `configs/production/v2_multi_2026_04.json` (±15 lines)
- MODIFIED: `docs/reference/config-reference.md` (±1 section)

**Lines:** +30/-15 (depending on decision)
**Time:** 4 hours
**Confidence:** 60%

**Decision needed:** Wire as pre-fusion gate, or delete?

**Arguments for delete:**
- 4 weights + threshold with no documented design intent
- Adding a pre-fusion gate changes engine behavior
- Simplest safe option: delete

**Arguments for wire:**
- The config specifies weights for intent, volume, liquidity, structure
- This could be useful as a pre-fusion signal quality filter
- Can be behind feature flag default=OFF

**Recommendation (from conversation):** Delete. The weights have never been tuned. A new
gate with unknown behavior is riskier than no gate. If needed later, the weights are
documented in the registry as "available for future gate."

**Checklist:**
- [ ] Decision made: wire or delete
- [ ] If wired: feature flag default=OFF, new gates added to engine_runner.py
- [ ] If deleted: section removed from config, config-reference.md updated
- [ ] Tests pass
- [ ] Byte-identity backtest verified

---

## Story 2.4: Verify StrategyOrchestrator Invocation

**Files:**
- MODIFIED: `src/core/engine_runner.py` (+15 lines if not wired)
- MODIFIED: `docs/STRATEGIES.md` (+10 lines)

**Lines:** +25
**Time:** 3 hours
**Confidence:** 75%

**What to do:**
1. Trace the live/backtest path: is `StrategyOrchestrator.compute()` called?
   - Search `engine_runner.py` for `strategy_orchestrator` or `strategy_consensus_score`
   - Check if it's behind a flag, or only in live, or only in backtest, or never
2. If NOT called: wire it into `EngineRunner.run()` before fusion. Add a new config key
   `strategy_orchestrator_enabled: true` (default: true) to gate it.
3. Document the invocation condition in `docs/STRATEGIES.md`

**Checklist:**
- [ ] Verified whether StrategyOrchestrator is invoked in active path
- [ ] If not wired: added to engine_runner.py behind feature flag
- [ ] If already wired: documented the invocation condition
- [ ] Tests pass
- [ ] Byte-identity backtest verified (if this changes scores, behavior changes by design)

---

## Story 2.5: Wire `regime_fusion_weights` into FusionEngine

**Files:**
- MODIFIED: `src/core/fusion_engine.py` (+30 lines)
- MODIFIED: `src/config_layer/production_config.py` (+5 lines)

**Lines:** +35
**Time:** 5 hours
**Confidence:** 70%

**What to build:**
1. Read `regime_fusion_weights` section from config in FusionConfig
2. In `FusionEngine.compute()`, after receiving the regime label from RegimeClassifier:
   - Look up the regime in `regime_fusion_weights` (TRENDING/RANGING/VOLATILE/UNKNOWN)
   - Use regime-specific weights instead of flat weights
   - If regime not found in the map → fall back to flat weights (no crash)
3. Behind feature flag `fusion_use_regime_weights: false` (default: false)

**Critical design decision:** Regime labels must be consistent. If the regime classifier
produces "trending" but the config uses "TRENDING" (case mismatch), fall back to flat weights.
Add a test for case-insensitive matching.

**Checklist:**
- [ ] `regime_fusion_weights` read from config
- [ ] Regime-adaptive weight selection in FusionEngine.compute()
- [ ] Feature flag `fusion_use_regime_weights` default=false
- [ ] Case-insensitive regime label matching
- [ ] If weight not found for regime → flat weight fallback
- [ ] Tests pass for both flag=true and flag=false
- [ ] Byte-identity backtest verified (flag=false = current behavior)

---

## Story 2.6: Externalize `PROMOTION_MARGIN` to Config

**Files:**
- MODIFIED: `src/core/model_registry.py` (-5 lines, +5 lines)
- MODIFIED: `configs/production/v2_multi_2026_04.json` (+3 lines)

**Lines:** +3, -5
**Time:** 1 hour
**Confidence:** 95%

**What to do:**
1. Find `PROMOTION_MARGIN = 0.02` in `src/core/model_registry.py`
2. Replace with config read: `get_prod_section("model_registry").get("promotion_margin", 0.02)`
3. Add `"promotion_margin": 0.02` to config under a new `model_registry` section

**Checklist:**
- [ ] Hardcoded constant replaced with config read
- [ ] Config has `promotion_margin` key
- [ ] Default 0.02 preserved (backward compatible)
- [ ] Tests pass

---

# 9. Epic 3: Framework Registry + Findings Applier

**Goal:** Build the queryable, append-only, evidence-linked registry + the findings applier that
drives engine behavior.
**Total:** 6 stories, 10+ new files, +1,595 lines, 41 hours.
**Prerequisite for:** All architecture changes must be registered here first.

## Story 3.1: Registry Schema + Python Module

**Files:**
- NEW: `src/governance/framework_registry.py` (+250 lines)
- NEW: `docs/reference/framework_registry_schema.md` (+80 lines)
- NEW: `tests/test_framework_registry.py` (+200 lines)

**Lines:** +530
**Time:** 10 hours
**Confidence:** 90%

**JSONL Schema (one line per component):**

```json
{
  "id": "DOMAIN-001",
  "type": "domain",
  "level": 1,
  "name": "CryptoSpot",
  "parent": null,
  "children": ["STYLE-001", "STYLE-002"],
  "evidence": [
    {
      "path": "scripts/data/fetch_crypto_ccxt.py",
      "line": 31,
      "symbol": "_INSTRUMENTS",
      "type": "code"
    }
  ],
  "findings": [
    {
      "id": "F-019",
      "confidence": "Likely",
      "action": "inform",
      "modifier": 1.0
    }
  ],
  "tests": ["tests/test_dataset_integrity.py"],
  "status": "extant",
  "created": "2026-06-15T00:00:00Z",
  "last_validated": "2026-06-15T00:00:00Z",
  "notes": "First domain class"
}
```

**Type enum:** `kernel | domain | style | strategy | implementation | intent | risk | execution | component | workflow_node`
**Level enum:** `0 | 1 | 2 | 3 | 4 | 5 | 6`
**Status enum:** `extant | implicit | orphaned | killed | dormant | planned | stub`
**Evidence type enum:** `code | config | doc | test | finding`
**Finding action enum:** `deweight | disable | restrict_session | restrict_spread | enforce_sl | inform | escalate`

**Public API (FrameworkRegistry class):**

| Method | Purpose |
|--------|---------|
| `load(path)` | Load JSONL, keep latest per id. Returns int (count). |
| `filter(type=None, level=None, status=None, parent=None)` | Query registry. Returns list[dict]. |
| `get(id)` | Get component by id. Returns dict. |
| `get_tree(root_id)` | Recursively build parent→children tree. Returns dict (nested). |
| `find_by_finding(finding_id)` | All components linked to a finding. Returns list[dict]. |
| `get_orphaned()` | Components with no parent reference. Returns list[dict]. |
| `validate_evidence()` | Check every evidence path+line exists. Returns list[ValidationError]. |
| `validate_findings()` | Check every finding id exists in docs/current-findings.md. Returns list[ValidationError]. |
| `append(record)` | Append one line, raises on schema violation. Returns None. |
| `to_dataframe()` | Export as pandas DataFrame. Returns DataFrame. |
| `summary()` | Counts per type, level, status. Returns dict. |

**Tests (8 tests minimum):**

| Test | What it validates |
|------|-------------------|
| `test_registry_loads_valid_jsonl` | All lines parse, no schema violations |
| `test_every_evidence_path_exists` | Every `evidence[].path` is a real file |
| `test_every_finding_exists` | Every `findings[].id` is in docs/current-findings.md |
| `test_no_dangling_parent` | Every `parent` id exists in the registry |
| `test_no_dangling_child` | Every `children[]` id exists in the registry |
| `test_level_matches_type` | `type=domain` implies `level=1`, etc. |
| `test_unique_ids` | No duplicate `id` across lines |
| `test_append_only_immutable` | Appending does not mutate existing lines |

**Checklist:**
- [ ] `docs/reference/framework_registry_schema.md` written with full schema
- [ ] `src/governance/framework_registry.py` with all 11 methods
- [ ] `tests/test_framework_registry.py` with 8+ tests
- [ ] All 8 tests pass
- [ ] Schema validation raises on invalid records
- [ ] Evidence validation catches missing files
- [ ] Finding validation catches missing IDs

---

## Story 3.2: Seed Registry from Codebase

**Files:**
- NEW: `scripts/governance/seed_framework_registry.py` (+100 lines)
- NEW: `data/framework_registry.jsonl` (+35 lines — one per component)

**Lines:** +135
**Time:** 5 hours
**Confidence:** 85%

**Classification table (seed data, user-verified):**

| Existing Code | id | type | level | Status |
|--------------|-----|------|-------|--------|
| `src/core/engine_runner.py` | KERNEL-001 | kernel | 0 | extant |
| `src/core/fusion_engine.py` | KERNEL-002 | kernel | 0 | extant |
| `src/core/decision_engine.py` | KERNEL-003 | kernel | 0 | extant |
| `src/features/feature_pipeline.py` | KERNEL-004 | kernel | 0 | extant |
| `src/runtime/backtest_v2.py` | KERNEL-005 | kernel | 0 | extant |
| `src/core/collector.py` | KERNEL-006 | kernel | 0 | extant |
| `scripts/data/fetch_crypto_ccxt.py` | DOMAIN-001 | domain | 1 | implicit |
| `scripts/data/fetch_forex_yfinance.py` | DOMAIN-002 | domain | 1 | dormant |
| `configs/production/v2_multi_2026_04.json` | DOMAIN-CONFIG-001 | domain | 1 | extant |
| `src/strategies/s01_crt_wrapper.py` | STRAT-001 | strategy | 3 | extant |
| `src/strategies/s02_mean_reversion.py` | STRAT-002 | strategy | 3 | extant |
| `src/strategies/s03_breakout.py` | STRAT-003 | strategy | 3 | extant |
| `src/strategies/s04_stat_arb.py` | STRAT-004 | strategy | 3 | extant |
| `src/strategies/s05_grid.py` | STRAT-005 | strategy | 3 | extant |
| `src/strategies/s06_scalping.py` | STRAT-006 | strategy | 3 | extant |
| `src/strategies/s07_news_sentiment.py` | STRAT-007 | strategy | 3 | extant |
| `src/strategies/s08_ml_ensemble.py` | STRAT-008 | strategy | 3 | extant |
| `src/strategies/s09_pattern_recog.py` | STRAT-009 | strategy | 3 | extant |
| `src/strategies/s10_trap_strategy.py` | STRAT-010 | strategy | 3 | extant |
| `src/engines/crt_engine.py` | IMPL-001 | implementation | 4 | extant |
| `src/engines/heuristic_gaussian_engine.py` | IMPL-002 | implementation | 4 | extant |
| `src/engines/ml_gaussian_engine.py` | IMPL-003 | implementation | 4 | extant |
| `src/engines/zone_gate_engine.py` | IMPL-004 | implementation | 4 | extant |
| `src/engines/rr_engine.py` | IMPL-005 | implementation | 4 | extant |
| `src/config_layer/execution_planner.py` | EXEC-001 | execution | 6 | extant |
| `src/core/ultron_risk_gate.py` | RISK-001 | risk | 5 | extant |
| `src/inout/executor.py` | EXEC-002 | execution | 6 | stub |
| `src/agent/` | AI-001 | component | 4 | extant |
| `src/bitnet/bitnet_inference.py` | AI-002 | component | 4 | extant |
| `src/governance/promotion_manager.py` | GOV-001 | component | 0 | extant |
| `src/portfolio/` | PORT-001 | risk | 5 | orphaned |
| `src/cognitive/` | AI-003 | component | 4 | orphaned |

**Evidence extraction rules:**
- For each module, extract the first `class` or `def` line as evidence
- For config, extract the first relevant line
- For data scripts, extract the line where the instrument list is defined

**Checklist:**
- [ ] `seed_framework_registry.py` written
- [ ] 35+ initial records in `data/framework_registry.jsonl`
- [ ] Each record has at least 1 evidence link
- [ ] Parent/children relationships are correct (user verification required)
- [ ] All 8 registry validation tests pass on seeded data
- [ ] No dangling parent references
- [ ] All evidence paths exist

---

## Story 3.3: CLI Query Tool

**Files:**
- NEW: `scripts/governance/query_registry.py` (+200 lines)

**Lines:** +200
**Time:** 6 hours
**Confidence:** 90%

**Usage:**

```
python scripts/governance/query_registry.py --summary
python scripts/governance/query_registry.py --type strategy
python scripts/governance/query_registry.py --tree DOMAIN-001
python scripts/governance/query_registry.py --finding F-021
python scripts/governance/query_registry.py --orphaned
python scripts/governance/query_registry.py --validate
```

**Output format for --tree:**

```
DOMAIN-001 CryptoSpot
├── STYLE-001 ReactionBased
│   ├── STRAT-001 CRT
│   │   └── IMPL-001 CRTEngine
│   └── STRAT-010 LiquiditySweep
├── STYLE-002 Breakout
│   └── STRAT-003 BOS+Volume
└── STYLE-003 MeanReversion
    ├── STRAT-002 RSI+BB
    └── STRAT-004 StatArb
```

**Checklist:**
- [ ] All 7 query modes work
- [ ] `--validate` runs full validation (evidence + findings + dangling refs)
- [ ] `--tree` produces correct hierarchy
- [ ] Exit code 0 on success, 1 on validation failure
- [ ] Help text (`--help`) documents all options

---

## Story 3.4: Registry Report Generator

**Files:**
- NEW: `scripts/governance/framework_registry_report.py` (+150 lines)
- NEW: `reports/framework_registry_report.md` (generated)

**Lines:** +150
**Time:** 4 hours
**Confidence:** 85%

**Report sections:**
1. Summary table — count per level per status
2. Gap analysis — which framework levels are empty or implicit
3. Orphan report — components not connected to the tree
4. Finding coverage — which findings are linked to components, which findings have no linked components
5. Evidence health — count of valid vs broken evidence paths
6. Hierarchy visualization — ASCII tree of the full registry

**Checklist:**
- [ ] Report generates without errors
- [ ] Report contains all 6 sections
- [ ] Report is valid Markdown
- [ ] Report is saved to `reports/framework_registry_report.md`

---

## Story 3.5: Findings Applier Module

**Files:**
- NEW: `src/governance/findings_applier.py` (+180 lines)
- NEW: `tests/test_findings_applier.py` (+150 lines)

**Lines:** +330
**Time:** 8 hours
**Confidence:** 75%

**What it does:**
Takes a component (from registry) and its active findings, returns the modified config/weight.

```python
class FindingsApplier:
    def apply(self, component: dict, mode: str = "research") -> dict:
        """Apply findings to component.
        
        Args:
            component: Registry record for a strategy/implementation/etc.
            mode: "research" (log only) or "active" (actually modify)
            
        Returns:
            Component dict with effective_weight, effective_status, effective_config
        """
```

**Mode behavior:**
- RESEARCH mode: logs what WOULD change, doesn't change anything
- ACTIVE mode: applies changes to the component's config before passing to engine

**Finding actions and how they modify components:**

| `findings[].action` | Effect on Component |
|---------------------|-------------------|
| `deweight` | `component.weight *= modifier` (default modifier=0.5) |
| `disable` | `component.status = "disabled"` |
| `restrict_session` | Add `session_restriction` to component config |
| `restrict_spread` | Add `max_spread_bps` to component config |
| `enforce_sl` | Add `min_sl_atr_mult` to component config |
| `inform` | No change (log only) |
| `escalate` | No change (log as escalation) |

**Aggregation rules:**
- Multiple `deweight` actions: weights multiply (compounding)
- `disable` overrides all other actions
- Confidences are applied only if >= threshold:
  - ACTIVE mode: only `Certain` and `Likely` findings are applied
  - RESEARCH mode: all findings are logged but none applied

**Tests:**

| Test | What it validates |
|------|-------------------|
| `test_deweight_reduces_weight` | Single deweight action reduces weight correctly |
| `test_multiple_deweight_compounds` | Multiple deweights multiply |
| `test_disable_overrides` | Disable action overrides all other actions |
| `test_research_mode_logs_only` | Research mode does not modify |
| `test_confidence_threshold` | Low confidence findings not applied in active mode |
| `test_unknown_action_raises` | Unknown action raises ValueError |
| `test_restrict_session_adds_filter` | Session restriction added to config |
| `test_enforce_sl_adds_minimum` | SL minimum added to config |

**Checklist:**
- [ ] `findings_applier.py` with all 8+ methods
- [ ] `test_findings_applier.py` with 8+ tests
- [ ] All tests pass
- [ ] Research mode does not modify components
- [ ] Active mode modifies only with sufficient confidence
- [ ] Multiple findings compound correctly
- [ ] Disable action properly overrides

---

## Story 3.6: Validate Finding Directives via Backtest

**Files:**
- NEW: `scripts/research/validate_finding.py` (+200 lines)
- NEW: `docs/reference/finding_validation_schema.md` (+50 lines)

**Lines:** +250
**Time:** 8 hours
**Confidence:** 70%

**What it does:**
Runs an A/B backtest for a finding:

```
Backtest A (baseline): Run WITHOUT the finding's directive applied
Backtest B (treatment): Run WITH the finding's directive applied
Result: B outperforms A → finding VALIDATED
        B underperforms A → finding REFUTED
        B == A → finding IRRELEVANT
```

**Usage:**

```
python scripts/research/validate_finding.py \
    --finding F-021 \
    --instrument BNBUSDT \
    --data data/BNBUSDT_M15.csv \
    --config configs/production/v2_multi_2026_04.json \
    --output results/finding_validation_F-021.json
```

**Validation output schema:**

```json
{
  "finding_id": "F-021",
  "directive_summary": "Session filter is the only non-random discriminator",
  "instrument": "BNBUSDT",
  "timerange": "2024-01-01..2026-05-01",
  "baseline_config_hash": "sha256:a1b2c3...",
  "treatment_config_diff": {
    "engine_runner.allowed_sessions": ["london", "new_york", "overlap"]
  },
  "baseline": {
    "expectancy": -0.15,
    "trades": 143,
    "win_rate": 0.34,
    "max_drawdown": -0.22,
    "sharpe": -0.1
  },
  "treatment": {
    "expectancy": -0.02,
    "trades": 47,
    "win_rate": 0.41,
    "max_drawdown": -0.15,
    "sharpe": 0.05
  },
  "delta": {
    "expectancy": 0.13,
    "trades": -96,
    "win_rate": 0.07,
    "max_drawdown": 0.07,
    "sharpe": 0.15
  },
  "verdict": "VALIDATED",
  "confidence_delta": "Increased from Possible to Likely",
  "created": "2026-06-15T00:00:00Z"
}
```

**Verdict logic:**
- VALIDATED: treatment expectancy > baseline expectancy AND treatment trades >= 10
- REFUTED: treatment expectancy <= baseline expectancy
- INCONCLUSIVE: treatment trades < 10 (insufficient data)
- ERROR: backtest failed (config error, data error)

**Checklist:**
- [ ] `validate_finding.py` written
- [ ] `finding_validation_schema.md` written
- [ ] Can run A/B backtest for any finding
- [ ] Produces structured validation result JSON
- [ ] Works with parallel backtests (for faster validation)
- [ ] Validated findings auto-register in registry

---

# 10. Epic 4: Domain Layer Extraction

**Goal:** Create formal domain abstractions. No existing code changes — new code coexists.
**Total:** 4 stories, 10 new files, +575 lines, 17 hours.
**Prerequisite for:** Style layer + n8n multi-domain support.

## Story 4.1: Create `TradingDomain` Abstract Base Class

**Files:**
- NEW: `src/domain/__init__.py` (+5 lines)
- NEW: `src/domain/base.py` (+80 lines)
- NEW: `tests/test_domain_base.py` (+100 lines)

**Lines:** +185
**Time:** 6 hours
**Confidence:** 90%

**ABC Contract:**

```python
class TradingDomain(ABC):
    @abstractmethod
    def domain_name(self) -> str  # "CryptoSpot", "Forex", etc.
    @abstractmethod
    def calendar(self) -> TradingCalendar
    @abstractmethod
    def cost_model(self, instrument: str) -> CostModel
    @abstractmethod
    def leverage_model(self) -> LeverageModel
    @abstractmethod
    def position_rules(self) -> PositionRules
    @abstractmethod
    def risk_rules(self) -> RiskRules
    @abstractmethod
    def allowed_styles(self) -> list[str]
```

**Supporting dataclasses:**

```python
@dataclass
class TradingCalendar:
    session_bounds: list  # [(start_hour, end_hour, timezone), ...]
    holidays: list[int]    # UTC epoch ms
    gap_handling: str      # "fill_flat" / "fill_previous" / "reject"
    weekly_break: Optional[tuple[int, int]]

@dataclass
class CostModel:
    taker_fee: float
    maker_fee: float
    min_commission: float
    spread_bps: float
    periodic_cost: float         # per-hour holding cost (funding/swap)
    periodic_cost_interval_h: float

@dataclass
class LeverageModel:
    max_leverage: float
    margin_type: str             # "cash" / "cross" / "isolated" / "reg_t"
    maintenance_margin_pct: float
    liquidation_buffer_pct: float

@dataclass
class PositionRules:
    allow_short: bool
    min_notional: float
    size_increment: float
    price_precision: int
    max_positions_same_instrument: int
    max_positions_total: int

@dataclass
class RiskRules:
    max_daily_loss_pct: float
    max_drawdown_pct: float
    max_correlation_exposure: float
    volatility_scaling: bool
    gap_risk_buffer_pct: float
    liquidation_risk_monitoring: bool
```

**Checklist:**
- [ ] `src/domain/__init__.py` created
- [ ] `src/domain/base.py` with ABC + all 6 dataclasses
- [ ] All abstract methods defined with docstrings
- [ ] `tests/test_domain_base.py` with tests for each dataclass
- [ ] Domain package is importable without side effects (no config loading at import time)

---

## Story 4.2: Implement `CryptoSpotDomain`

**Files:**
- NEW: `src/domain/crypto_spot.py` (+100 lines)

**Lines:** +100
**Time:** 4 hours
**Confidence:** 85%

**Values to extract from current implicit behavior:**
- Calendar: continuous 24/7, no session bounds, no weekly break, gap_handling = "reject" (crypto has no gaps, any gap is data quality issue)
- Cost: taker_fee=0.00075 (Binance spot), maker_fee=0.00075, min_commission=0, spread_bps=3.0 (0.03%), periodic_cost=0 (no funding on spot), periodic_cost_interval_h=0
- Leverage: max_leverage=1.0, margin_type="cash"
- Position: allow_short=false, min_notional=10, size_increment=0.001 (BTC), price_precision=8, max_positions_same=1, max_positions_total=5
- Risk: max_daily_loss=0.05, max_drawdown=0.20, vol_scaling=true, gap_risk=0.02
- Styles: ["ReactionBased", "Breakout", "MeanReversion", "Momentum", "Pattern", "Grid"]

**Checklist:**
- [ ] `CryptoSpotDomain` implements all abstract methods
- [ ] All values are informed by current config and behavior (user verification recommended)
- [ ] Tests assert all methods return non-None values
- [ ] Domain is registered in framework_registry.jsonl
- [ ] Domain is NOT wired into engine yet (coexistence only)

---

## Story 4.3: Implement `ForexDomain` (Dormant → Extant)

**Files:**
- NEW: `src/domain/forex.py` (+100 lines)

**Lines:** +100
**Time:** 4 hours
**Confidence:** 70%

**Values:**
- Calendar: 24/5, Sun 17:00 - Fri 17:00 UTC, session_bounds=[Tokyo 00-09, London 08-17, NY 13-22], gap_handling="fill_flat" (weekends are filled with flat bars or rejected)
- Cost: taker_fee=0 (spread-only retail), maker_fee=0, min_commission=0, spread_bps=1.5 (EURUSD typically), periodic_cost=swap_rate/365 (overnight holding), periodic_cost_interval_h=24
- Leverage: max_leverage=30.0 (retail typical), margin_type="margin"
- Position: allow_short=true, min_notional=1000 (1k units), size_increment=1000, price_precision=5, max_positions_same=1, max_positions_total=5
- Risk: max_daily_loss=0.05, max_drawdown=0.20, vol_scaling=true, gap_risk=0.01 (forex gaps smaller than crypto)
- Styles: ["ReactionBased", "TrendFollowing", "Breakout", "MeanReversion"]

**Warning:** Forex cost model is broker-dependent. The spread_bps=1.5 is a reasonable average
but may not match any specific broker. Add a comment: "Default values — verify against your
broker's actual costs before promoting to active."

**Checklist:**
- [ ] `ForexDomain` implements all abstract methods
- [ ] Calendar correctly handles 24/5 vs 24/7
- [ ] Cost model accounts for swap/holding costs
- [ ] Domain is registered in framework_registry.jsonl as `status=extant`
- [ ] Domain is NOT wired into engine yet

---

## Story 4.4: Create Domain Stubs

**Files:**
- NEW: `src/domain/crypto_futures.py` (+40 lines)
- NEW: `src/domain/equities.py` (+40 lines)
- NEW: `src/domain/futures.py` (+40 lines)
- NEW: `src/domain/options.py` (+40 lines)

**Lines:** +160
**Time:** 3 hours
**Confidence:** 95%

**Each stub must include:**
- Calendar (basic, may be approximate)
- Cost model (may be minimal)
- Leverage model (may be placeholder)
- Position rules (may be minimal)
- Risk rules (may be default)
- Allowed styles (may be empty)

**Status:** All stubs registered as `status=planned` in registry. Future work.

**Checklist:**
- [ ] 4 domain stubs created
- [ ] Each implements all abstract methods (can return default/placeholder values)
- [ ] Each is registered in framework_registry.jsonl as `status=planned`
- [ ] All domain tests still pass

---

# 11. Epic 5: Style Layer + Strategy Reorganization

**Goal:** Group 10+ strategies under styles. Make CRT a strategy plugin, not a mandatory engine.
**Total:** 4 stories, 12 files (+8 new, +3 modified), +375/-5 lines, 20 hours.
**Highest risk:** Story 5.4 changes the fundamental engine invariant.

## Story 5.1: Create `TradingStyle` Abstract Base Class

**Files:**
- NEW: `src/styles/__init__.py` (+5 lines)
- NEW: `src/styles/base.py` (+60 lines)
- NEW: `tests/test_style_base.py` (+80 lines)

**Lines:** +145
**Time:** 4 hours
**Confidence:** 90%

**ABC Contract:**

```python
class TradingStyle(ABC):
    @abstractmethod
    def name(self) -> str
    @abstractmethod
    def allowed_strategies(self) -> list[str]
    @abstractmethod
    def preferred_instruments(self, domain: TradingDomain) -> list[str]
    @abstractmethod
    def max_hold_bars(self) -> int
    @abstractmethod
    def regime_preferences(self) -> list[str]
    @abstractmethod
    def required_engines(self) -> set[str]
```

**Checklist:**
- [ ] `src/styles/__init__.py` created
- [ ] `src/styles/base.py` with ABC
- [ ] `tests/test_style_base.py` with tests for each method
- [ ] Style package is importable without side effects

---

## Story 5.2: Classify 10 Existing Strategies Under Styles

**Files:**
- NEW: `src/styles/reaction_based.py` (+30 lines — references CRT, LiquiditySweep, NewsSentiment)
- NEW: `src/styles/mean_reversion.py` (+20 lines — references RSI+BB, StatArb)
- NEW: `src/styles/breakout.py` (+20 lines — references BOS+Volume)
- NEW: `src/styles/momentum.py` (+20 lines — references MACD)
- NEW: `src/styles/grid.py` (+15 lines — references ATRGrid)
- NEW: `src/styles/pattern.py` (+15 lines — references Candlestick)
- NEW: `src/styles/ml_hybrid.py` (+15 lines — references ML Ensemble)
- MODIFIED: `src/strategies/strategy_orchestrator.py` (+30 lines — add style-aware selection)

**Lines:** +165
**Time:** 6 hours
**Confidence:** 75%

**Style assignments:**

| Style | Strategies | Required Engines | Regime |
|-------|-----------|-----------------|--------|
| ReactionBased | CRT, LiquiditySweep, NewsSentiment | {crt} | ranging |
| MeanReversion | RSI+BB, StatArb | {gaussian} | ranging |
| Breakout | BOS+Volume | {zone_gate} | trending |
| Momentum | MACD | {} | trending |
| Grid | ATRGrid | {} | ranging |
| Pattern | Candlestick | {} | any |
| ML/Hybrid | ML Ensemble | {rr} | any |

**StrategyOrchestrator change:** Add a new method `get_strategies_for_regime(regime: str)` that
returns only strategies whose style matches the current regime. Old consensus scoring still
works for backward compatibility.

**Checklist:**
- [ ] 8 style modules created
- [ ] Each style correctly lists its allowed strategies (by id)
- [ ] Each style lists required engines
- [ ] StrategyOrchestrator has style-aware selection method
- [ ] Old consensus scoring path still works (backward compatible)
- [ ] Registry updated: each strategy has `parent=<style_id>`
- [ ] All tests pass

---

## Story 5.3: Add TrendFollowing Style + MA_Cross Strategy

**Files:**
- NEW: `src/styles/trend_following.py` (+20 lines)
- NEW: `src/strategies/s11_ma_cross.py` (+80 lines)
- MODIFIED: `configs/production/v2_multi_2026_04.json` (+20 lines)
- MODIFIED: `docs/STRATEGIES.md` (+15 lines)

**Lines:** +135
**Time:** 5 hours
**Confidence:** 80%

**MA Cross Strategy Logic:**

```python
class MACrossStrategy:
    """Simple trend-following: fast MA crosses above slow MA → long.
    Exit: price crosses below slow MA or time stop.
    """
    
    def compute(self, candle, features, state):
        fast_ma = state.fast_ma  # 10-period
        slow_ma = state.slow_ma  # 50-period
        
        if fast_ma > slow_ma and state.prev_fast <= state.prev_slow:
            return Signal(direction=1, confidence=0.6)
        elif fast_ma < slow_ma and state.prev_fast >= state.prev_slow:
            return Signal(direction=-1, confidence=0.6)
        return None
```

**Config:**

```json
{
  "strategy_engine.s11_ma_cross": {
    "enabled": false,
    "fast_period": 10,
    "slow_period": 50,
    "min_volume_ratio": 1.0,
    "session_restriction": "london,new_york,overlap",
    "regime_restriction": "trending",
    "min_adx": 25,
    "warmup_bars": 60
  }
}
```

**Critical:** MA Cross is registered BUT disabled by default (`enabled: false`). It's available
for research only until validated. This prevents the new strategy from affecting existing behavior.

**Checklist:**
- [ ] TrendFollowing style created
- [ ] S11 MA Cross strategy implemented
- [ ] Config section added (enabled: false)
- [ ] STRATEGIES.md updated
- [ ] Registry updated with new strategy + style
- [ ] All existing tests pass (new strategy is disabled)

---

## Story 5.4: Style-Scoped Engine Completeness Check

**Files:**
- MODIFIED: `src/core/engine_runner.py` (-5 lines, +30 lines)
- MODIFIED: `src/styles/base.py` (+5 lines — add `required_engines` property)

**Lines:** +30, -5
**Time:** 5 hours
**Confidence:** 60% — **HIGHEST RISK STORY**

**What changes:**
Replace the global `EXPECTED_ENGINES = {"crt", "gaussian", "zone_gate", "rr"}` with
style-scoped checks. Each style specifies its required engines. The engine completeness
check becomes style-scoped.

**Before (current):**
```python
EXPECTED_ENGINES = {"crt", "gaussian", "zone_gate", "rr"}
# ...
if missing := EXPECTED_ENGINES - set(engine_results.keys()):
    raise ValueError(f"Missing engines: {missing}")
```

**After (new):**
```python
# Global fallback (backward compatible)
EXPECTED_ENGINES = {"crt", "gaussian", "zone_gate", "rr"}

# Style-scoped check (feature-flagged)
if config.get("style_scoped_engines", False):
    active_styles = get_active_styles_for_regime(current_regime)
    required = set().union(*[s.required_engines for s in active_styles])
    if missing := required - set(engine_results.keys()):
        raise ValueError(f"Missing engines for style {missing}")
else:
    # Old behavior (default)
    if missing := EXPECTED_ENGINES - set(engine_results.keys()):
        raise ValueError(f"Missing engines: {missing}")
```

**Feature flag:** `style_scoped_engines: false` (default: false → backward compatible).

**Checklist:**
- [ ] Global EXPECTED_ENGINES preserved as fallback
- [ ] Feature flag `style_scoped_engines` added to config (default=false)
- [ ] Style-scoped check implemented behind flag
- [ ] When flag=false: behavior is identical to current (byte-identity verified)
- [ ] When flag=true: only engines required by active styles are checked
- [ ] Registry updated: each style has `required_engines` field
- [ ] Byte-identity backtest verified for flag=false
- [ ] Byte-identity backtest verified for flag=true (may differ by design)

**Escalation condition:** If fixing this causes >50 line changes, stop and raise:
the style-scoped engine check may need a separate engine runner path rather than modifying
the existing one.

---

# 12. Epic 6: n8n Integration

**Goal:** Docker Compose for n8n + webhook receiver + parallel workdir isolation + workflow.
**Total:** 5 stories, 7+ files (+3 new, +4 modified), +945 lines, 25 hours.
**Prerequisite for:** All automated orchestration.

## Story 6.1: Docker Compose for n8n

**Files:**
- NEW: `docker-compose.yml` (+40 lines)

**Lines:** +40
**Time:** 2 hours
**Confidence:** 90%

```yaml
version: '3.8'
services:
  n8n:
    image: n8nio/n8n:latest
    ports:
      - "5678:5678"
    volumes:
      - ./data/n8n:/home/node/.n8n
      - ./:/data/tradelatest
    environment:
      - N8N_SECURE_COOKIE=false
      - WEBHOOK_URL=http://localhost:5678/
    networks:
      - tradelatest
    restart: unless-stopped

  control_plane:
    build: .
    ports:
      - "8787:8787"
    volumes:
      - ./:/app
    command: python scripts/control_plane/run_server.py
    networks:
      - tradelatest
    restart: unless-stopped

volumes:
  n8n_data:

networks:
  tradelatest:
```

**Checklist:**
- [ ] `docker-compose.yml` written
- [ ] `docker compose up n8n` starts n8n at localhost:5678
- [ ] `docker compose up control_plane` starts control plane at localhost:8787
- [ ] Both containers can communicate (n8n → control_plane via hostname "control_plane")

---

## Story 6.2: n8n Webhook Receiver in Control Plane

**Files:**
- MODIFIED: `src/control_plane/server.py` (+80 lines)
- MODIFIED: `src/control_plane/registry.py` (+30 lines)

**Lines:** +110
**Time:** 8 hours
**Confidence:** 75%

**Two new endpoints:**

### POST `/api/run-stage`

**Input (JSON body):**
```json
{
  "stage": "tuning",
  "instrument": "BNBUSDT",
  "workdir": "/tmp/tradelatest/BNBUSDT/run_001",
  "config": {
    "n_iter": 100,
    "seed": 42,
    "workers": 4
  }
}
```

**Output (JSON):**
```json
{
  "status": "success",
  "stage": "tuning",
  "instrument": "BNBUSDT",
  "metrics": {
    "expectancy": -0.02,
    "trades": 47,
    "win_rate": 0.41,
    "max_drawdown": -0.15
  },
  "config_hash": "sha256:a1b2c3...",
  "artifacts": ["results/tuner/BNBUSDT/checkpoint.json"],
  "duration_seconds": 342,
  "error": null
}
```

**Error output:**
```json
{
  "status": "error",
  "stage": "tuning",
  "instrument": "BNBUSDT",
  "error": "No data found for BNBUSDT",
  "error_type": "DataNotFoundError",
  "duration_seconds": 2,
  "artifacts": []
}
```

### POST `/api/claude-gate`

**Input (JSON body):**
```json
{
  "stage": "tuning",
  "instrument": "BNBUSDT",
  "config": { "...": "..." },
  "backtest_results": {
    "expectancy": -0.15,
    "trades": 143,
    "win_rate": 0.34,
    "max_drawdown": -0.22
  },
  "findings": [
    {"id": "F-021", "directive": "Session filter is only discriminator"},
    {"id": "F-026", "directive": "CRT retest adds no edge, deweight"}
  ]
}
```

**Output (JSON — Claude's decision):**
```json
{
  "action": "tweak" | "promote" | "escalate" | "skip",
  "confidence": 0.0-1.0,
  "tweak": {
    "section": "params",
    "key": "retest_depth_max",
    "from": 0.8,
    "to": 0.6,
    "reason": "F-026 shows CRT retest adds no edge. Reducing from 0.8 to 0.6.",
    "expected_impact": "Reduce noise trades ~20%"
  },
  "findings_referenced": ["F-026"],
  "next_action": "re-run backtest"
}
```

**Security:** Both endpoints are localhost-only (same as existing control plane). No auth required.
If exposed externally, must add API key validation.

**Checklist:**
- [ ] `POST /api/run-stage` implemented
- [ ] `POST /api/claude-gate` implemented
- [ ] Both endpoints return correct JSON
- [ ] Error responses include error_type for n8n to route on
- [ ] Endpoints are localhost-only
- [ ] Existing control plane functionality unchanged

---

## Story 6.3: Parallel Workdir Isolation for Scripts

**Files:**
- MODIFIED: `scripts/training/auto_tuner_multi.py` (+10 lines)
- MODIFIED: `scripts/training/auto_tuner.py` (+10 lines)
- MODIFIED: `scripts/data/prepare_data.py` (+10 lines)
- MODIFIED: `src/runtime/backtest_v2.py` (+15 lines)
- MODIFIED: `src/governance/promotion_manager.py` (+10 lines)

**Lines:** +55
**Time:** 6 hours
**Confidence:** 70%

**What changes:**
Each script gets a new optional arg `--workdir <path>`. When provided:
- All output paths are relative to workdir (not hardcoded `results/` or `data/`)
- Temp files are created in workdir
- Lock files are created in workdir (to prevent concurrent writes)

**Pattern:**

```python
# In each script's argument parser
parser.add_argument("--workdir", type=str, default=None,
                    help="Working directory for output isolation")

# At start of main()
workdir = args.workdir
if workdir:
    os.makedirs(workdir, exist_ok=True)
    output_dir = os.path.join(workdir, "results")
    data_dir = os.path.join(workdir, "data")
else:
    output_dir = args.output_dir or DEFAULT_OUTPUT_DIR
    data_dir = args.data_dir or DEFAULT_DATA_DIR
```

**Critical:** If a script uses absolute paths (hardcoded `results/tuner/`), the workdir
flag must override that path. Audit each script for hardcoded paths before implementing.

**Checklist:**
- [ ] 5 scripts modified with `--workdir` flag
- [ ] All output paths respect workdir when provided
- [ ] Backward compatible (no workdir = current behavior)
- [ ] Parallel runs with different workdirs don't collide
- [ ] Tests pass for both with and without workdir

---

## Story 6.4: n8n Workflow JSON Export

**Files:**
- NEW: `configs/n8n/trading_workflow.json` (+500+ lines)

**Lines:** +500
**Time:** 4 hours
**Confidence:** 80%

**Workflow nodes (in order):**

1. **Webhook Trigger** — accepts `POST` with `{"instruments":["BNBUSDT","BTCUSDT","ETHUSDT","SOLUSDT"]}`
2. **Split In Batches** — splits into 4 parallel branches (one per instrument)
3. **Data Prep** — HTTP POST to `http://control_plane:8787/api/run-stage` with stage="data_prep"
4. **Tuning** — HTTP POST to control_plane with stage="tuning"
5. **Validation** — HTTP POST to control_plane with stage="validation"
6. **Claude Gate** — HTTP POST to control_plane with stage="claude_gate"
   - If "tweak" → loop back to Tuning (max 3 iterations)
   - If "promote" → proceed to Promotion
   - If "escalate" → stop, log to escalation queue
7. **Promotion** — HTTP POST to control_plane with stage="promotion"
8. **Live Runner** — HTTP POST to control_plane with stage="live_runner"

**Checklist:**
- [ ] Workflow JSON exported and saved to `configs/n8n/`
- [ ] Import into n8n works without errors
- [ ] Each node correctly calls the control plane webhook
- [ ] Claude Gate node correctly handles all 3 outputs (tweak/promote/escalate)
- [ ] Tweak loop has max 3 iterations (prevent infinite loops)
- [ ] Escalation stops the workflow and logs to file

---

## Story 6.5: Stage Result Schema + Validation

**Files:**
- NEW: `docs/reference/stage_result_schema.md` (+60 lines)
- NEW: `src/control_plane/stage_result.py` (+80 lines)
- NEW: `tests/test_stage_result.py` (+100 lines)

**Lines:** +240
**Time:** 5 hours
**Confidence:** 85%

**Schema validation rules:**
- `status` must be "success" or "error"
- `stage` must be one of: "data_prep", "tuning", "validation", "claude_gate", "promotion", "live_runner"
- `instrument` must be a non-empty string
- `metrics` must contain at least `expectancy` and `trades` if status="success"
- `error` must be non-empty if status="error"
- `artifacts` must be a list of strings (file paths)
- `duration_seconds` must be a positive number

**Checklist:**
- [ ] `stage_result_schema.md` written
- [ ] `stage_result.py` with validation function
- [ ] `test_stage_result.py` with tests for each schema rule
- [ ] Validation raises on invalid input
- [ ] Validation returns sanitized dict on valid input

---

# 13. Epic 7: Claude Gate Integration

**Goal:** Claude gate webhook + prompt templates + registry config for LLM gates.
**Total:** 3 stories, 7 files (+5 new, +2 modified), +495 lines, 16 hours.

## Story 7.1: Claude Gate Webhook Handler

**Files:**
- NEW: `src/control_plane/claude_gate.py` (+200 lines)
- NEW: `tests/test_claude_gate.py` (+150 lines)
- MODIFIED: `src/control_plane/server.py` (+5 lines — register route)

**Lines:** +355
**Time:** 10 hours
**Confidence:** 75%

**Handler logic:**

```python
class ClaudeGateHandler:
    def __init__(self, api_key: str, prompt_templates_dir: str):
        self.api_key = api_key
        self.prompt_templates_dir = prompt_templates_dir
    
    def evaluate(self, context: dict) -> dict:
        """Call Claude API with prompt built from context.
        
        Args:
            context: {stage, instrument, config, backtest_results, findings, findings_prompt}
            
        Returns:
            {action, confidence, tweak, findings_referenced, next_action}
        """
        # 1. Load prompt template for this stage
        template = self._load_template(context["stage"])
        
        # 2. Build prompt from template + context
        prompt = self._build_prompt(template, context)
        
        # 3. Call Anthropic Claude API
        response = self._call_claude(prompt)
        
        # 4. Parse and validate response
        decision = self._parse_response(response)
        
        # 5. Log the interaction
        self._log_interaction(context, prompt, decision)
        
        return decision
```

**Prompt template variables:**
- `{{config}}` — current config section relevant to this stage
- `{{backtest_results}}` — expectancy, trades, win_rate, max_drawdown
- `{{findings}}` — list of active findings with directives
- `{{instrument}}` — instrument name
- `{{stage}}` — current workflow stage

**Rate limiting:** Max 3 calls to Claude per workflow per instrument. Configurable.
If limit reached → auto-escalate.

**Checklist:**
- [ ] `claude_gate.py` written with full handler
- [ ] `test_claude_gate.py` with tests for prompt building, API calling, response parsing
- [ ] API key loaded from `.env` or config (not hardcoded)
- [ ] Response parsing handles invalid JSON gracefully (log warning, return "escalate")
- [ ] Rate limiting implemented (max N calls per workflow)
- [ ] All interactions logged to file for audit

---

## Story 7.2: Claude Prompt Templates in Config

**Files:**
- NEW: `configs/production/claude_prompts/tuning_gate.json` (+30 lines)
- NEW: `configs/production/claude_prompts/validation_gate.json` (+30 lines)
- NEW: `configs/production/claude_prompts/promotion_gate.json` (+30 lines)

**Lines:** +90
**Time:** 3 hours
**Confidence:** 80%

**Tuning Gate Prompt Template:**

```json
{
  "stage": "tuning",
  "system_prompt": "You are the config tweaker for a crypto trading bot called Tradelatest. Your job: read backtest results + current config + active findings, and suggest the MINIMUM config change to improve expectancy. RULES: (1) Change ONE parameter at most. (2) If expectancy is positive, recommend promote. (3) If no tweak is obvious, escalate. (4) You may reference findings (F-001 to F-029) to justify. (5) Never suggest structural code changes. Config only. RESPONSE FORMAT (JSON only): {\"action\": \"tweak\" | \"promote\" | \"escalate\", \"confidence\": 0.0-1.0, \"tweak\": {\"section\": \"...\", \"key\": \"...\", \"from\": value, \"to\": value, \"reason\": \"...\", \"expected_impact\": \"...\", \"findings_referenced\": [\"...\"]}, \"next_action\": \"...\"}",
  "user_prompt_template": "Stage: {{stage}}\nInstrument: {{instrument}}\nConfig: {{config}}\nBacktest Results: {{backtest_results}}\nActive Findings: {{findings}}\nFinding Directive Summary: {{findings_prompt}}\n\nSuggest one config tweak."
}
```

**Validation Gate Prompt Template:**

```json
{
  "stage": "validation",
  "system_prompt": "You are the validation gate for Tradelatest. Your job: decide if a tuned config should be promoted to production. RULES: (1) Promote only if expectancy > 0 AND trades >= 10. (2) If expectancy is positive but marginal (<0.1R), recommend additional tuning. (3) If expectancy is negative, escalate. RESPONSE FORMAT (JSON only): {\"action\": \"promote\" | \"re-tune\" | \"escalate\", \"confidence\": 0.0-1.0, \"reason\": \"...\", \"findings_referenced\": [\"...\"]}",
  "user_prompt_template": "..."
}
```

**Checklist:**
- [ ] 3 prompt templates created
- [ ] Each template has valid JSON structure
- [ ] Templates use consistent variable naming ({{variable}})
- [ ] Tuning gate template enforces "one change at most" rule
- [ ] Validation gate template enforces "expectancy>0" rule

---

## Story 7.3: Claude Gate Config in Registry

**Files:**
- MODIFIED: `docs/reference/framework_registry_schema.md` (+30 lines)
- MODIFIED: `src/governance/framework_registry.py` (+20 lines — handle new type)

**Lines:** +50
**Time:** 3 hours
**Confidence:** 85%

**New type in registry: `workflow_node`**

```json
{
  "id": "NODE-TUNING-GATE",
  "type": "workflow_node",
  "level": 0,
  "name": "Tuning Claude Gate",
  "parent": "WORKFLOW-001",
  "children": [],
  "evidence": [
    {"path": "src/control_plane/claude_gate.py", "line": 1, "symbol": "ClaudeGateHandler", "type": "code"}
  ],
  "llm_gate": {
    "enabled": true,
    "trigger_conditions": ["soft_fail", "expectancy_below_0", "new_instrument"],
    "max_iterations": 3,
    "prompt_template": "configs/production/claude_prompts/tuning_gate.json",
    "allowed_actions": ["tweak", "promote", "escalate"],
    "on_escalate": "notify_user"
  },
  "status": "extant",
  "notes": "Claude gate for tuning stage. Triggers on soft_fail or negative expectancy."
}
```

**Checklist:**
- [ ] Schema updated with `workflow_node` type
- [ ] `llm_gate` field documented in schema
- [ ] Registry module handles new type in summaries
- [ ] Workflow nodes registered for each Claude gate stage

---

# 14. Epic 8: Enable UltronRiskGate + Wire Portfolio

**Goal:** Turn on the risk gate, wire portfolio module, wire drift detection action.
**Total:** 3 stories, 3-4 files, +66 lines, 11 hours.
**Highest risk (second):** Story 8.1 enables a disabled gate.

## Story 8.1: Enable UltronRiskGate in Config

**Files:**
- MODIFIED: `configs/production/v2_multi_2026_04.json` (1 line change)

**Lines:** +0, -0 (1 value changed)
**Time:** 2 hours
**Confidence:** 50% — **SECOND HIGHEST RISK STORY**

**What changes:**
Line 66 of `configs/production/v2_multi_2026_04.json`:
```
"ultron_gate_enabled": false  →  "ultron_gate_enabled": true
```

**Why this is risky:** Enabling the risk gate for the first time will reject trades
that were previously accepted. This is BY DESIGN, but the impact on trade count and
metrics is unknown. The risk gate checks:
- TTL expiry → may reject trades with long hold times
- RR floor → may reject trades with low expected RR
- Daily trade limit → may cap number of trades
- Kill switch (daily loss) → may shut down after losing streak
- Portfolio exposure → may reject correlated trades
- SL distance checks → may reject trades with tight SLs

**Procedure:**
1. Run backtest with `ultron_gate_enabled: false` (current) → record metrics
2. Run backtest with `ultron_gate_enabled: true` → record metrics
3. Compare: how many trades were rejected? Which check rejected them?
4. If rejection rate is reasonable (e.g., <20% of previously accepted trades), proceed
5. If rejection rate is too high (>50%), adjust risk gate thresholds
6. Set conservative limits initially: daily loss=10%, drawdown=25%, trade limit=10/day

**Checklist:**
- [ ] Backtest run with gate disabled (baseline metrics recorded)
- [ ] Backtest run with gate enabled (treatment metrics recorded)
- [ ] Rejection analysis: how many, which check, which instruments
- [ ] If rejection rate acceptable: gate enabled in config
- [ ] If rejection rate too high: thresholds adjusted
- [ ] Byte-identity verified (baseline matches existing, treatment is new)
- [ ] Risk gate tests pass with new config

---

## Story 8.2: Wire PortfolioAllocator into Spine

**Files:**
- MODIFIED: `src/core/engine_runner.py` (+15 lines)
- MODIFIED: `src/portfolio/__init__.py` (+10 lines — expose API)

**Lines:** +25
**Time:** 4 hours
**Confidence:** 65%

**What changes:**
After `UltronRiskGate.evaluate()` approves a trade (or concurrently), call
`PortfolioAllocator.evaluate()` to check portfolio-level constraints:

- Net exposure ≤ max_leverage
- Gross exposure ≤ max_gross
- Concentration (single instrument ≤ max_pct)
- Correlation exposure (correlated bets ≤ threshold)

If portfolio check fails → REJECT (even if risk gate approved).

**Integration point:**
```python
# In engine_runner.py, after risk gate
if config.get("portfolio_check_enabled", False):
    if not portfolio_allocator.check(portfolio_state, proposed_trade):
        logger.warning("Portfolio check rejected trade")
        rejected_by = "portfolio"
        continue  # or log and skip
```

**Feature flag:** `portfolio_check_enabled: false` (default: false).

**Checklist:**
- [ ] Portfolio module API exposed
- [ ] Portfolio check integrated into engine_runner.py after risk gate
- [ ] Feature flag `portfolio_check_enabled` default=false
- [ ] Tests pass for both flag=true and flag=false
- [ ] Byte-identity backtest verified for flag=false

---

## Story 8.3: Wire Drift Detector Action (Fix F-008)

**Files:**
- MODIFIED: `src/features/feature_monitor.py` (+30 lines)
- MODIFIED: `src/core/engine_runner.py` (+10 lines)

**Lines:** +40
**Time:** 5 hours
**Confidence:** 70%

**What changes:**
F-008 says concept drift is "DETECTED but NOT acted on." The feature monitor already
computes drift Z-scores. Now add actions:

- HARD drift (Z > 3.0 for 2+ consecutive bars): PAUSE affected strategies
- SOFT drift (Z > 2.5 for 3+ consecutive bars): SIZE DOWN 50%

**Implementation:**

```python
# In feature_monitor.py
class FeatureMonitor:
    def check_drift(self, features):
        drift = self.compute_drift(features)
        actions = []
        for feature_name, z_score in drift.items():
            if z_score > 3.0:
                self.drift_streak[feature_name] = self.drift_streak.get(feature_name, 0) + 1
                if self.drift_streak[feature_name] >= 2:
                    actions.append({"feature": feature_name, "z_score": z_score, "action": "pause"})
            elif z_score > 2.5:
                self.drift_streak[feature_name] = self.drift_streak.get(feature_name, 0) + 1
                if self.drift_streak[feature_name] >= 3:
                    actions.append({"feature": feature_name, "z_score": z_score, "action": "size_down"})
            else:
                self.drift_streak[feature_name] = 0  # reset streak
        return actions
```

**Feature flag:** `drift_action_enabled: false` (default: false).

**Checklist:**
- [ ] Drift action callbacks implemented in feature_monitor.py
- [ ] EngineRunner registers drift callbacks
- [ ] HARD drift pauses affected strategies after 2 consecutive bars
- [ ] SOFT drift sizes down 50% after 3 consecutive bars
- [ ] Streak resets when drift subsides
- [ ] Feature flag `drift_action_enabled` default=false
- [ ] Tests pass for both flag=true and flag=false

---

# 15. Epic 9: Documentation + Validation

**Goal:** All reference docs updated. Integration tests added. Regression verified.
**Total:** 4 stories, 4+ files, +280 lines, 17 hours.

## Story 9.1: Update All Reference Docs

**Files:**
- MODIFIED: `docs/reference/architecture.md` (+50 lines)
- MODIFIED: `docs/reference/schemas.md` (+30 lines)
- MODIFIED: `docs/reference/config-reference.md` (+20 lines)
- MODIFIED: `docs/STRATEGIES.md` (+30 lines)

**Lines:** +130
**Time:** 6 hours
**Confidence:** 80%

**Architecture.md additions:**
- Domain layer (src/domain/) with ABC and implementations
- Style layer (src/styles/) with ABC and implementations
- Strategy reorganization (CRT as plugin, not mandatory)
- Registry (data/framework_registry.jsonl)
- n8n orchestration layer
- Control plane webhook endpoints

**Checklist:**
- [ ] Architecture.md updated with new layers
- [ ] Schemas.md updated with domain/style/schemas
- [ ] Config-reference.md updated with new sections
- [ ] STRATEGIES.md updated with style grouping, MA Cross

---

## Story 9.2: Add Registry + Findings Validation Tests

Already counted in Story 3.1 and 3.5. This story covers the testing effort.

**Time:** 4 hours
**Confidence:** 85%

**Checklist:**
- [ ] All 8 registry tests pass
- [ ] All 8 findings applier tests pass
- [ ] Registry validation catches broken evidence paths
- [ ] Registry validation catches missing findings

---

## Story 9.3: Add n8n Integration Tests

**Files:**
- NEW: `tests/test_control_plane_webhooks.py` (+150 lines)

**Lines:** +150
**Time:** 4 hours
**Confidence:** 80%

**Tests:**
- POST `/api/run-stage` with valid input → returns 200 + valid stage result
- POST `/api/run-stage` with invalid stage → returns 400 + error
- POST `/api/claude-gate` with valid input → returns 200 + valid decision
- POST `/api/claude-gate` with missing API key → returns 503 + error
- Both endpoints reject non-JSON bodies
- Both endpoints accept only POST (reject GET/PUT/DELETE)

**Checklist:**
- [ ] Webhook endpoint tests pass
- [ ] Claude gate endpoint tests pass
- [ ] Error handling tests pass

---

## Story 9.4: Full Regression Test

**Files:** 0 (test runner only)
**Lines:** 0
**Time:** 3 hours (test runtime)
**Confidence:** 90%

**What to run:**
```
pytest tests/ --tb=short -q
```

**Expected:** 1208+ passed, 0 failed, 18 skipped, 2 xfailed (or whatever the current
skip/xfail count is).

**Byte-identity verification (if spine code changed):**
```
python scripts/analysis/verify_determinism.py \
    --config configs/production/v2_multi_2026_04.json \
    --data data/BNBUSDT_M15.csv \
    --baseline results/baseline/BNBUSDT_ledger.json
```

**Checklist:**
- [ ] All 1200+ tests pass
- [ ] Byte-identity verified for BNBUSDT (if spine changed)
- [ ] Byte-identity verified for SOLUSDT (if spine changed)
- [ ] Regression report saved

---

# 16. Epic 10: Findings Integration

**Goal:** Validate all 29 existing findings against historical data. Promote validated ones.
**Total:** 3 stories, 3+ files, +108 lines, 37-45 hours (dominated by backtest runtime).

## Story 10.1: Validate All 29 Existing Findings

**Files:**
- NEW: `data/finding_validations.jsonl` (+29 lines)
- NEW: `reports/finding_validation_report.md` (generated)

**Lines:** +29
**Time:** 30 hours (backtest runtime) / ~8 hours (parallelized)
**Confidence:** 60%

**Expected outcomes (based on existing research):**

| Finding | Expected Verdict | Confidence Change |
|---------|-----------------|-------------------|
| F-001 | INCONCLUSIVE (architectural, not testable via backtest) | No change |
| F-002 | INCONCLUSIVE (requires research, not backtest) | No change |
| F-004 | VALIDATED (BitNet gate score is persisted) | Certain → Certain |
| F-005 | INCONCLUSIVE (TradeNet v2 not wired, can't test) | No change |
| F-006 | VALIDATED (config_integrity runs but gates nothing) | Certain → Certain |
| F-008 | VALIDATED (drift detected but not acted, will see in logs) | Certain → Certain |
| F-009 | INCONCLUSIVE (per-instrument doctrine, history) | No change |
| F-010 | INCONCLUSIVE (live PnL unverifiable in backtest) | No change |
| F-011 | INCONCLUSIVE (OOS persistence, long backtest needed) | No change |
| F-012 | INCONCLUSIVE (architectural, not testable) | No change |
| F-013 | VALIDATED (portfolio module exists, not wired) | Certain → Certain |
| F-016 | INCONCLUSIVE (version truth, config check) | No change |
| F-017 | VALIDATED (session policy backtest shows no improvement) | Likely → Certain |
| F-019 | VALIDATED (no crypto major shows positive expectancy) | Likely → Certain |
| F-020 | VALIDATED (no conditional pocket found) | Likely → Certain |
| F-021 | VALIDATED (session restriction improves expectancy) | Likely → Certain |
| F-025 | VALIDATED (SL/TP tuning doesn't fix negative edge) | Likely → Certain |
| F-026 | VALIDATED (CRT retest removal improves metrics) | Likely → Certain |
| F-027 | VALIDATED (H1/H4 no better than M15) | Likely → Certain |
| F-028 | VALIDATED (P&F no standalone edge) | Likely → Certain |
| F-029 | INCONCLUSIVE (center=True benign, needs specific test) | No change |

**Checklist:**
- [ ] All 29 findings validated via A/B backtest
- [ ] Validation results saved to `data/finding_validations.jsonl`
- [ ] Validation report generated at `reports/finding_validation_report.md`
- [ ] Each validation includes baseline vs treatment metrics
- [ ] Each validation includes verdict and any confidence change

---

## Story 10.2: Promote Validated Findings to Active

**Files:**
- MODIFIED: `data/framework_registry.jsonl` (+29 lines — findings linked to components)

**Lines:** +29
**Time:** 4 hours (review + registry updates)
**Confidence:** 70%

**Procedure:**
1. For each finding that validated: add to registry under affected components
2. For each finding that refuted: note as `SUPERSEDED` in findings doc
3. For each finding that is inconclusive: leave as-is, note "needs more data"
4. Run findings applier in RESEARCH mode: verify correct modifications
5. If verified: promote findings applier to ACTIVE mode

**Checklist:**
- [ ] Validated findings linked to affected components in registry
- [ ] Refuted findings marked as SUPERSEDED in findings doc
- [ ] Inconclusive findings noted as "needs more data"
- [ ] Findings applier in RESEARCH mode produces expected modifications
- [ ] If verified: applier promoted to ACTIVE

---

## Story 10.3: Continuous Validation Pipeline

**Files:**
- MODIFIED: `configs/n8n/trading_workflow.json` (+1 node)
**Lines:** +50
**Time:** 3 hours
**Confidence:** 85%

**New n8n node:** Weekly validation workflow that runs `validate_finding.py` for new
findings. Runs every Sunday at 02:00 UTC.

**Checklist:**
- [ ] Weekly validation workflow added to n8n
- [ ] New findings auto-validated
- [ ] Validation results logged to JSONL
- [ ] User notified if finding verifies or refutes

---

# 17. JSONL Registry Schema Reference

## 17.1 Component Record

```json
{
  "id": "DOMAIN-001",
  "type": "domain",
  "level": 1,
  "name": "CryptoSpot",
  "parent": null,
  "children": ["STYLE-001", "STYLE-002"],
  "evidence": [
    {
      "path": "scripts/data/fetch_crypto_ccxt.py",
      "line": 31,
      "symbol": "_INSTRUMENTS",
      "type": "code"
    }
  ],
  "findings": [
    {
      "id": "F-019",
      "confidence": "Likely",
      "action": "deweight",
      "modifier": 0.5
    }
  ],
  "tests": ["tests/test_dataset_integrity.py"],
  "status": "extant",
  "created": "2026-06-15T00:00:00Z",
  "last_validated": "2026-06-15T00:00:00Z",
  "findings_policy": {
    "aggregate_mode": "multiplicative",
    "floor_weight": 0.1,
    "auto_disable_at": 0.0
  },
  "notes": "First domain class"
}
```

## 17.2 Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `id` | YES | string | Unique identifier. Format: `{TYPE}-{NUMBER}` |
| `type` | YES | enum | `kernel \| domain \| style \| strategy \| implementation \| intent \| risk \| execution \| component \| workflow_node` |
| `level` | YES | int | 0-6 (matching TRADING_SYSTEM_FRAMEWORK.md hierarchy) |
| `name` | YES | string | Human-readable component name |
| `parent` | YES | string or null | Parent component id (null for root) |
| `children` | YES | list[string] | Child component ids (empty list for leaf) |
| `evidence` | YES | list[EvidenceObject] | At least 1 evidence link |
| `findings` | YES | list[FindingLink] | Empty list if none |
| `tests` | YES | list[string] | Test file paths |
| `status` | YES | enum | `extant \| implicit \| orphaned \| killed \| dormant \| planned \| stub` |
| `created` | YES | string (ISO 8601) | Creation timestamp |
| `last_validated` | YES | string (ISO 8601) | Last validation timestamp |
| `findings_policy` | NO | dict | Aggregation rules |
| `notes` | NO | string | Free-text notes |

## 17.3 Evidence Object

```json
{
  "path": "src/core/engine_runner.py",
  "line": 52,
  "symbol": "EXPECTED_ENGINES",
  "type": "code"
}
```

**`type` enum:** `code | config | doc | test | finding`

## 17.4 Finding Link

```json
{
  "id": "F-026",
  "confidence": "Likely",
  "action": "deweight",
  "modifier": 0.3
}
```

**`confidence` enum:** `Certain | Likely | Possible`
**`action` enum:** `deweight | disable | restrict_session | restrict_spread | enforce_sl | inform | escalate`

## 17.5 Workflow Node Extra Fields

```json
{
  "llm_gate": {
    "enabled": true,
    "trigger_conditions": ["soft_fail", "expectancy_below_0"],
    "max_iterations": 3,
    "prompt_template": "configs/production/claude_prompts/tuning_gate.json",
    "allowed_actions": ["tweak", "promote", "escalate"],
    "on_escalate": "notify_user"
  }
}
```

---

# 18. Claude Gate Prompt Templates

## 18.1 Tuning Gate

**System prompt:**
```
You are the config tweaker for a crypto trading bot called Tradelatest.
Your job: read backtest results + current config + active findings, and suggest
the MINIMUM config change to improve expectancy.

RULES:
- Change ONE parameter at most. Never change 2+ things at once.
- If expectancy is already positive, recommend promotion.
- If expectancy is negative but a tweak is obvious, return the tweak with expected impact.
- If no tweak is obvious, escalate with a clear reason.
- You may reference findings (F-001 to F-029) to justify your decision.
- Never suggest structural code changes. Config only.
- Never suggest changing more than one parameter.

RESPONSE FORMAT (JSON only):
{
  "action": "tweak" | "promote" | "escalate",
  "confidence": 0.0-1.0,
  "tweak": {
    "section": "params",
    "key": "parameter_name",
    "from": current_value,
    "to": new_value,
    "reason": "Why this change (reference findings if applicable)",
    "expected_impact": "Quantified expected impact",
    "findings_referenced": ["F-XXX"]
  },
  "next_action": "re-run backtest"
}
```

## 18.2 Validation Gate

**System prompt:**
```
You are the validation gate for Tradelatest.
Your job: decide if a tuned config should be promoted to production.

RULES:
- Promote only if expectancy > 0 AND trades >= 10.
- If expectancy is positive but marginal (< 0.1R), recommend re-tuning instead.
- If expectancy is negative, escalate with analysis.
- Consider active findings in your decision.

RESPONSE FORMAT (JSON only):
{
  "action": "promote" | "re-tune" | "escalate",
  "confidence": 0.0-1.0,
  "reason": "Why this decision",
  "findings_referenced": ["F-XXX"]
}
```

## 18.3 Promotion Gate

**System prompt:**
```
You are the promotion gate for Tradelatest.
Your job: confirm that a validated config should be promoted to production.

RULES:
- Confirm only if expectancy > 0 AND validated at least twice (A/B backtest).
- If this is the first validation, recommend additional validation.
- If expectancy is negative, block promotion.

RESPONSE FORMAT (JSON only):
{
  "action": "confirm" | "re-validate" | "block",
  "confidence": 0.0-1.0,
  "reason": "Why this decision",
  "evidence": ["validation run IDs"]
}
```

---

# 19. Troubleshooting Guide

## 19.1 Test Failures After Implementation

| Symptom | Likely Cause | Check |
|---------|-------------|-------|
| 10+ LLM tests fail | Fallback value mismatch (0.5 vs 1.0) | Story 1.1 |
| Dual gate tests fail | Regime classifier labels mismatch | Story 1.2 |
| RR fusion tests fail | RRFusionLayer import or method renamed | Story 1.3 |
| Gaussian switch fails | `gaussian_impl` flag path changed | Story 1.4 |
| Registry tests fail | JSONL schema mismatch | Story 3.1, check `framework_registry_schema.md` |
| Webhook tests fail | Route registration conflict | Story 6.2, check `server.py` route table |
| Claude gate tests fail | API key not set | Story 7.1, check `.env` |
| Risk gate tests fail | `ultron_gate_enabled` still false | Story 8.1, check config line 66 |

## 19.2 Runtime Errors After Implementation

| Error | Likely Cause | Check |
|-------|-------------|-------|
| "Missing engines: crt" after enabling style-scoped engines | ReactionBased style not registered or incorrect engine list | Story 5.4, check style.required_engines |
| "No module named src.domain" | Domain package not installed | Run `pip install -e .` or check pyproject.toml |
| Claude gate returns "action: escalate" for every call | Prompt template too restrictive, or no tweak possible | Story 7.2, check prompt template |
| n8n workflow fails at Claude gate | API key invalid or rate limited | Story 7.1, check `.env` for ANTHROPIC_API_KEY |
| Parallel backtests produce different results | Workdir isolation not working | Story 6.3, check `--workdir` flag in scripts |
| All trades rejected after enabling risk gate | Risk gate thresholds too tight | Story 8.1, check `capital_management` values |
| Registry validation shows broken evidence | File moved or renamed | Run `query_registry.py --validate` to list broken paths |
| Findings not applied to engine | FindingsApplier mode = "research" | Story 3.5, check mode parameter |

## 19.3 Performance Issues

| Issue | Likely Cause | Fix |
|-------|-------------|-----|
| Backtest takes 30+ min per finding | No parallelization | Use `--parallel` flag in validate_finding.py |
| n8n workflow takes hours | Sequential stages | Enable parallel branches in workflow |
| Claude API calls slow (5+ sec each) | API rate limiting | Reduce max_iterations or batch calls |
| Registry JSONL file grows too large | Too many append operations | Archive old records monthly |

## 19.4 Rollback Procedure

If a story causes regression:

1. **If feature-flagged:** Set flag to `false` (original behavior restored)
2. **If not feature-flagged:** Revert the commit:
   ```
   git revert <commit-hash>
   ```
3. **If config only:** Restore previous config version:
   ```
   python src/governance/promotion_manager.py load --version v2_multi_2026_04
   ```
4. **If registry corrupt:** Restore from backup:
   ```
   cp data/framework_registry.jsonl.bak data/framework_registry.jsonl
   ```
   (Always keep a backup before modifying registry)

## 19.5 Pre-Flight Checks Before Any Story

Before starting any story, always:

1. **Run the full test suite** → record baseline: `pytest tests/ -q --tb=short 2>&1 | tee before_story.log`
2. **Run byte-identity backtest** → record baseline: `python scripts/backtest/v2.py --csv data/BNBUSDT_M15.csv --output results/baseline/BNBUSDT_before.json`
3. **Backup registry** → `cp data/framework_registry.jsonl data/framework_registry.jsonl.bak`
4. **Backup config** → `cp configs/production/v2_multi_2026_04.json configs/production/v2_multi_2026_04.json.bak`

After the story:

1. **Run the full test suite** → compare to baseline: any NEW failures?
2. **Run byte-identity backtest** → compare to baseline: any changes in trade ledger?
3. **If regressions found:** fix or revert. Do not proceed to next story.

---

# 20. Audit Trail Template

Every story must produce this audit record. Append to `assistant_project.md` after each story.

```
---
📝 SESSION LOG ENTRY
Date: {timestamp}
Epic: {epic name}
Story: {story number}: {story title}

Files Changed:
  - NEW: path/to/file.py (+N lines)
  - MODIFIED: path/to/file.py (+N/-M lines)

Key Decisions:
  - {decision 1 with rationale}
  - {decision 2 with rationale}

Belief Update / ROI / Goal:
  Goal: {goal this story serves}
  Belief: {what was believed before vs after}
  Knowledge ROI: {High/Medium/Low — was this worth doing?}
  Action: {next step}

Risks Remaining:
  - {risk 1}
  - {risk 2}

Validation Results:
  - Tests: {passed/failed count}
  - Byte-identity: {PASS/FAIL/not applicable}
  - Registry validation: {passed/failed}

Open Questions:
  - {any unresolved items}

Next Story:
  - {next story number}: {next story title}
---
```

---

# 21. Implementation Order (Critical Path)

## Phase 1: Foundation (must build first — trust the codebase)

**Order matters. Do not skip.**

```
Story 1.1 → Fix LLM tests (1h)
Story 1.4 → Fix Gaussian switch (2h)
Story 1.5 → Fix replay memory (2h)
Story 1.6 → Fix feature schema (0.5h)
Story 1.2 → Fix dual gate (3h)
Story 1.3 → Fix RR fusion (3h)
  → ALL 23 FIXES VERIFIED. FULL REGRESSION. ~11.5h
```

## Phase 2: Measurement (build the registry)

```
Story 3.1 → Registry schema + module (10h)
Story 3.2 → Seed registry (5h)
Story 3.3 → CLI query tool (6h)
Story 3.4 → Report generator (4h)
  → REGISTRY FUNCTIONAL. CAN QUERY ARCHITECTURE. ~25h
```

## Phase 3: Config cleanup (make config trustworthy)

```
Story 2.6 → Externalize PROMOTION_MARGIN (1h)
Story 2.2 → Remove data_ingestion (1h)
Story 2.4 → Verify StrategyOrchestrator (3h)
Story 2.1 → Wire capital management (6h)
Story 2.3 → Wire/remove gate_intelligence (4h)
Story 2.5 → Wire regime_fusion_weights (5h)
  → ALL CONFIG CONSUMED. NO DEAD SECTIONS. ~20h
```

## Phase 4: Findings (make findings drive behavior)

```
Story 3.5 → Findings applier module (8h)
Story 3.6 → Validate finding directives (8h)
Story 10.1 → Validate all 29 findings (30h parallelized)
Story 10.2 → Promote validated findings (4h)
  → FINDINGS DRIVE ENGINE. ~50h
```

## Phase 5: Risk (turn on protection)

```
Story 8.3 → Wire drift detector action (5h)
Story 8.2 → Wire portfolio allocator (4h)
Story 8.1 → Enable UltronRiskGate (2h)
  → RISK ACTIVE. NON-BYPASSABLE. ~11h
```

## Phase 6: Architecture (domain + style layers)

```
Story 4.1 → Domain ABC (6h)
Story 4.2 → CryptoSpotDomain (4h)
Story 5.1 → Style ABC (4h)
Story 5.2 → Classify strategies (6h)
Story 5.3 → Add TrendFollowing + MA_Cross (5h)
Story 5.4 → Style-scoped engines (5h) ← HIGH RISK
  → ARCHITECTURE CORRECT. ~30h
```

## Phase 7: Automation (n8n + Claude)

```
Story 6.1 → Docker Compose (2h)
Story 6.2 → Webhook receiver (8h)
Story 6.3 → Parallel workdir isolation (6h)
Story 7.2 → Claude prompt templates (3h)
Story 7.3 → Claude gate in registry (3h)
Story 7.1 → Claude gate handler (10h)
Story 6.4 → n8n workflow JSON (4h)
Story 6.5 → Stage result schema (5h)
Story 9.3 → n8n integration tests (4h)
  → AUTOMATION RUNNING. ~45h
```

## Phase 8: Documentation + Final Validation

```
Story 4.3 → ForexDomain (4h)
Story 4.4 → Domain stubs (3h)
Story 9.1 → Update reference docs (6h)
Story 9.2 → Registry validation tests (4h) [already counted in Phase 2]
Story 9.4 → Full regression test (3h)
Story 10.3 → Continuous validation pipeline (3h)
  → EVERYTHING DONE. ~23h
```

## Total: ~220 hours (5-6 weeks full-time)

---

**End of specification. Hand this document to Claude LLM for implementation.**
