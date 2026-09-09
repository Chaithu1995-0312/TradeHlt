# Close out `v2_htfcrt_2026_08` verification + correct Sujan provenance + add the HTF-state/objective dimension

## Context

The `CH-htfcrt-parent-candle-smc-v1` program has **already shipped** (Phases 0–6): calendar-true
parent candles, a 3-candle parent-CRT state machine (`CRTState` 9→12), 9 SMC primitives as canonical
features (schema 39→48, v4.0→v5.0), and a promoted active version `v2_htfcrt_2026_08`. Findings
**F-075** and **F-076** are registered.

Three things are now outstanding, from two separate causes.

**(a) Verification is not fully closed.** The parity evidence landed and is good — background job
`bc4bqjaj8` returned `46997/47197`, exactly the figure already recorded in F-076, with both failures
being a stale pre-existing pin (`# measured 99.96% at settle time`), so **no new CRT-parity
regression**. But the full-suite tally was lost (job piped through `tail`, which buffers to EOF →
0 bytes), determinism was never run twice, and the `post_htfcrt` baseline successor to Phase 0's
`pre_htfcrt` was never captured.

**(b) A provenance overclaim I introduced, found by review and confirmed against source.** A review
challenged whether `C1=Range / C2=Manipulation / C3=Distribution` is Sujan vocabulary. Checked
against the primary docs — it is not, and more sharply, it *conflicts*:

| Token | Occurrences across both SujanTrader docs |
|---|---|
| `manipulation` | **0** |
| `C1` / `C2` / `C3` / "first candle" | **0** |
| `objective` | **51** |
| `accumulation` | 20 |
| `distribution` | 5 |

`SujanTraderCrtExpPart2.txt:869-872` defines a **four-state** model — *"State 1 – Expansion · State 2
– Accumulation · **State 3 – Distribution (look for reversal evidence)** · State 4 – Reversal"*. So
Sujan's *Distribution* is a **reversal-warning** state, while the shipped `DISTRIBUTION_C3` is a
**directional impulse** — near-inverted. Sujan's own 3-candle profile (`SujanTraderCRTExp.txt:787-791`)
is *expansion → small accumulation/base → recovery* (move→**pause**→move), not range→**sweep**→impulse.

The labels came from the **user's own directive** and are standard ICT/CRT vocabulary — they are not
invented, and the shipped state definitions carry no Sujan attribution. But two artifacts *do* borrow
Sujan's authority and must be corrected (E-001):
- [`src/config_layer/parent_crt.py:97-99`](D:/Tradelatest/src/config_layer/parent_crt.py) — *"mirrors the **source framework's** own 'has this CRT completed its objective?' discipline"*
- `docs/governance/build_manifests/CH-htfcrt-parent-candle-smc-v1.impact.json:4` — juxtaposes the three labels with `"Source: SujanTrader…txt study"`

**(c) The genuinely missing Sujan layer.** Objective is Sujan's dominant concept (51 hits, per-TF
`Monthly Objective` headers, checklist item *"☐ Has the 6M objective been reached?"*) and Accumulation
is his preferred trade location (`Accumulation ⭐⭐⭐⭐⭐ (Best place to prepare)` vs `Expansion ⭐⭐
(Usually avoid chasing)`). Neither exists in the build.

**User decisions taken:** keep the C1/C2/C3 names and fix attribution with a *stronger provenance
boundary* — "Sujan is evidence for the parent-candle philosophy and the four-state HTF model; it is
**not** authority for the C1/C2/C3 state-machine design" — modelling profile and HTF-state as **two
explicit dimensions**; and build the missing layer **wired into the spine**.

---

## Stage 1 — Close verification (do first; no new code)

1. **Full suite, unbuffered.** `python -m pytest tests/ -q > <scratch>/full.txt 2>&1` — redirect to a
   file, never pipe through `tail` (that's what lost the last run). Triage against the known
   pre-existing baseline (7 failures at Phase-4 close + the 2 stale-pin parity + 2
   `test_reachability_golden` + `test_agents_path_alignment` + 4 script-registry grandfather, all
   already attributed).
2. **Determinism.** Run the XAUUSD backtest twice; assert byte-identical vector + trade ledger.
3. **Baseline successor.** `python src/runtime/baseline_capture.py --label post_htfcrt`, then diff
   against Phase 0's `pre_htfcrt` manifest. Every delta must map to a named mechanism (schema
   39→48, `SCHEMA_HASH`, `ACTIVE_VERSION`) — an unexplained delta is a defect.
4. Record the resulting tallies in the completion manifest's `checks_result`, replacing the current
   prose estimate with measured numbers.

**Do not** regenerate `test_reachability_golden`'s golden — `active_models.yaml` is being edited by
concurrent sessions, so an isolated regeneration would capture unrelated in-progress state.

## Stage 2 — Provenance correction (E-001, same turn as Stage 1)

Cheap, no config/closure churn. Nothing is renamed.

- **`parent_crt.py:97-99`** — drop the "source framework" appeal; state the mechanical rationale
  directly (*a swept range is not a confirmed narrative until the impulse away from it confirms*).
- **`state_identity.py:59-61`** — add a short block comment: these are **profile-position** labels for
  the three parent candles, **not** Sujan's four HTF state labels; `DISTRIBUTION_C3` does **not**
  inherit Sujan's *Distribution*.
- **Impact manifest** — split `Source:` into `Trigger:` (the SujanTrader study prompted the work) vs
  the actual provenance of the labels (user directive + standard CRT vocabulary).
- **New finding F-077** (`RF-CRT-STRUCTURE`, `Contract: UNKNOWN`, Certain) recording the semantic
  divergence with the occurrence counts and the `Part2:869-872` citation, so it cannot silently
  re-propagate. Add the row to CLAUDE.md's Repository Truths Index; re-run
  `scripts/governance/export_findings.py`.
- Cross-reference from F-075's Note.

## Stage 3 — The second dimension: HTF state + objective + activation

Two orthogonal axes, per the agreed model:

```
                 PARENT CRT
          ┌──────────┴──────────┐
   CANDLE PROFILE            HTF STATE
    C1 → C2 → C3      Expansion/Accumulation/Distribution/Reversal
          └──────────┬──────────┘
                 OBJECTIVE → OBJECTIVE STATUS
                          ↓
                    LOWER-TF CRT → ACTIVATION → EXECUTION
```

**Design constraints (each is a real, verified hazard):**
- **New `HTFState` enum — do NOT extend `CRTState` again.** It is a separate dimension; extending
  `CRTState` would reopen the state topology a second time and conflate the axes.
- **Do not add a 4th expansion/compression implementation.** Three already exist:
  `CandleStateEncoder` (`src/research/candle_state/encoder.py:35-37`), `RegimeLabeler`
  (`src/interpreters/regime_observer.py:41`), and `volatility_regime`
  (`market_ontology.yaml:1748`). Production must not import `src/research/` (backwards layering) —
  follow the sanctioned `weekly_sweep`/`parent_crt` **reimplement-locally** precedent, with
  thresholds read from config via strict `_require()`, no silent defaults (§6.5).
- **Name clash:** `weekly_range.py:24` `ACCUMULATION_WEEKDAYS` means Mon/Tue, *not* Wyckoff
  accumulation. Namespace the new states on the enum; never a bare module constant.
- **Ontology first (§6.6):** register `HTFState` + `Objective` as canonical nodes in
  `market_ontology.yaml` **non-frozen sibling sections** before production use — the frozen runtime
  keys stay flat + additive. `market_story_ontology.yaml:149` already reserves
  `wyckoff (status: planned, "accumulation/distribution: spring, upthrust")` as the descriptive seam.
- **Activation ≠ bias veto.** `DISTRIBUTION_C3` must not become trade permission — structure validity
  is not execution validity. Objective-status gates *activation*; the parent-bias gate stays a veto.

**Sequencing (each step verifiable on its own):**
1. `HTFState` enum + a pure classifier over closed parent candles, config-driven thresholds. Unit-test
   against synthetic candles like `weekly_sweep` does.
2. Typed `Objective` / `ObjectiveStatus` (exists / achieved / invalidated) derived from HTF state +
   parent range levels. Distinct from `GoalSpec` (`goal_schema.py:78`), which is the **economic** G001
   objective — different concept, must not be conflated.
3. Ontology registration + `validate_registry()` green.
4. **Wire it — behind a config gate, default OFF, and prove byte-identical ledgers first.** This also
   closes F-075's open gap that *nothing currently threads `parent_state`*, so the shipped gate is
   unreachable. Flipping the gate ON is a **separate, explicitly-verified step** with its own before/
   after ledger diff — that ordering is what keeps §6.5 intact (wiring grants reachability;
   only measured ΔG001 grants authority).
5. New impact manifest for the wiring (it is a `RUNTIME_DECISION_PATH_CHANGE` on an already-promoted
   config), findings, topic sync, session log.

**Explicitly out of scope:** 3M/6M tiers (Sujan's checklist starts at 6M, but the 2-year corpus gives
only 24 monthly candles — deferred by earlier decision); retraining the 6 stale model families;
renaming any shipped state.

---

## Verification

- **Stage 1** is itself the verification gate — Stage 2/3 should not start until the full-suite tally,
  determinism, and `post_htfcrt` diff are recorded.
- **Stage 2:** `pytest tests/test_current_findings.py tests/test_findings_export.py
  tests/test_doc_citations.py tests/test_topic_docs.py` + confirm zero remaining Sujan-attribution
  claims (`grep -rn "source framework\|Sujan" src/ configs/`).
- **Stage 3:** classifier unit tests; `validate_registry() == []`; **byte-identical XAUUSD ledger with
  the new gate OFF** (the hard gate — a diff here means a wrong config default); then a separately
  attributed diff with it ON.
- Close with `construction_protocol.py validate-completion <manifest>` and the §6 SESSION LOG.
- **No economic claim** is admissible from any of this: E rung stays OPEN (0 sealed `MC-*`), F rung is
  PARTIAL until the 9 SMC slots carry `CLOSURE_STATUS` rows.
