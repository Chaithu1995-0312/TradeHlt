# Trace Sujan's CRT method → mimic it on XAUUSD

## Context

Two source docs sit at repo root: `SujanTraderCRTExp.txt` (1,415 lines) and
`SujanTraderCrtExpPart2.txt` (1,324). They are the **same conversation** — doc 1 is a superset;
`CRT 2.0` appears at `CRTExp:685` and `Part2:602`, and the tails are identical. Treat them as one
corpus, not two sources.

They are **dialogue transcripts between Sujan and an AI**, not a written-up method. That matters
for provenance (below) and it is the same trap F-077 exists to prevent.

Separately, this session reverse-engineered five FX setups Sujan posted as screenshots
(NZDCAD/AUDUSD/AUDCHF/NZDUSD/USDCHF). Those turn out to be **the last three phases of the
documented protocol executed**, which lets the two sources validate each other.

**The synthesis that makes this worth building.** From the screenshots alone I concluded the only
undocumented input was "what makes a sweep count," and that it looked like a hindsight filter. That
was wrong — it is written down as an 8-phase checklist explicitly designed so *"90% of charts get
rejected before you even think about entering"* (`Part2:1122`). What the docs *also* reveal is
something Sujan does not appear to have noticed:

> `Part2:1266-1270` — **`Reward ≥ 1:5` · `Target = HTF CRT objective` · `Stop = CRT invalidation`**

Target and stop are both fixed by structure, so RR is fully determined — nothing is chosen. The
`≥1:5` rule therefore cannot select better trades; it can only select **trades whose invalidation
happens to sit close to entry**. It is a thin-buffer selector wearing the costume of a quality
filter. That predicts the exact pattern measured in the five screenshots: sort by stop distance and
RR falls monotonically, 5 of 5 (86→8.5, 101→5.5, 151→5.0, 175→4.9, 338→4.5), while sorting by
reward gives no order at all (5.5, 8.5, 5.0, 4.9, 4.5).

**Testing that one rule is the highest-value experiment in this program**, and it is original — it
is not a restatement of any existing finding.

---

## Part 1 — The extracted pattern

### Provenance chain (record it; do not repeat F-077's error)

`Romeo CRT Time-Based Model` (the "1-3-5-9 framework", `CRTExp:121`) → Sujan's own HTF-candle-state
practice → co-developed **with the AI** into `CRT Execution Protocol v1.0`, `CRT 2.0`, and
`CRT High-Probability Checklist v1.0`.

Both the four-state model (`Part2:869-872`) and the 8-phase checklist (`Part2:1124+`) are prefaced
by the AI as *"One refinement I'd like us to add"* / *"I think we should add"*. **They are the
interlocutor's proposals, not Sujan's authored method.** F-077 already corrected one Sujan
over-attribution; this plan must not create a second.

### The governing principle

> `Part2:851-857` — *"You're not really trading price. You're trading the state of higher-timeframe
> candles."* Every lower timeframe exists to answer: **"What is the current HTF candle trying to
> accomplish?"**

### The timeframe ladder

`6M` macro objective → `3M` decision zone → `Monthly` → `Weekly` → `Daily` execution environment →
`4H` active candle / execution engine → `1H` microscope for timing → `15M` refinement.

### The 8-phase checklist (`Part2:1124-1305`)

| Phase | Gate | Fail action |
|---|---|---|
| 1 | Macro alignment — 6M/3M/Monthly/Weekly each classified into 4 states | no clear answer → no trade |
| 2 | Alignment score — **all four must agree** | one disagrees → skip |
| 3 | Daily objective — "what is today's objective?" (sweep BSL/SSL, reach OB, fill imbalance) | can't answer → skip |
| 4 | 4H CRT — fresh? inside HTF objective? expanding? accumulating? liquidity taken? | — |
| 5 | Trade location — only Monthly/3M/Weekly/Daily OB, CRT midpoint, CRT high/low. **"Never chase."** | middle of nowhere → reject |
| 6 | Liquidity — external/internal taken? equal highs/lows? | no sweep → no trade |
| 7 | Activation — Rejection → Displacement → Structure shift → Return → Entry | without displacement the CRT is *"sleeping"* |
| 8 | Risk — **Reward ≥ 1:5**, Target = HTF objective, Stop = invalidation | — |

### The 100-point rubric (`Part2:569-580`)

Monthly +15 · Weekly +15 · Daily objective +20 · HTF location +15 · liquidity sweep +10 · rejection
block +10 · displacement +10 · BOS/CHoCH +5. **Sums to exactly 100; trade only at ≥90** — so at most
one 10-point component may be missing. Extremely strict.

### The four HTF states — two conflicting definitions in the same doc

- **A** (`Part2:869-872`): Expansion / Accumulation / Distribution *(reversal-warning)* / Reversal
- **B** (`Part2:991-994`): Accumulation ⭐⭐⭐⭐⭐ / Expansion ⭐⭐ / Exhaustion ⭐⭐⭐ / Redistribution-Reaccumulation ⭐⭐⭐⭐⭐
- Plus a "traffic light" overlay (`Part2:1319-1323`): 🟢 accumulation complete · 🟡 don't chase · 🔴 stand aside

**Adopt A and declare it** — `src/config_layer/htf_state.py:42` already implements exactly those four
members. B is recorded as an unimplemented variant, not silently merged.

### The one rule

> `Part2:1311` — **"Never trade an Expansion CRT. Trade the Accumulation before the next Expansion."**

### The 3-candle CRT profile (`CRTExp:787-791`)

expansion → small accumulation/base → recovery, i.e. **move → pause → move**. Note this is *not*
range→sweep→impulse, which is what shipped as `RANGE_C1`/`MANIPULATION_C2`/`DISTRIBUTION_C3` — the
divergence F-077 already records. Do not re-conflate them.

### Screenshot ↔ doc correspondence (the two sources validating each other)

| Screenshot behaviour | Checklist phase |
|---|---|
| Sweep of prior swing extreme | Phase 6 |
| Entry on reclaim at the level | Phase 7 (rejection → return → entry) |
| Stop just past the sweep wick | Phase 8 "Stop = CRT invalidation" |
| Target = opposite end of prior range | Phase 8 "Target = HTF CRT objective" |
| Every posted RR in 4.5–8.5 | Phase 8 "Reward ≥ 1:5" |
| HTF Open line on all five charts | the parent-candle ladder itself |

---

## Part 2 — XAUUSD design

XAUUSD is the docs' own worked example (6M equilibrium 3825, 3M OB 4325, ~500-point objective,
`Part2:1006-1015`) and the repo's standing research instrument
(`memory/feedback_xauusd_only_and_distrust_evidence.md`).

### Scope boundaries — declare these before building, not after

1. **6M/3M are unmeasurable on this corpus.** `data/mt5/XAUUSD_M15.csv` spans 2024-05-22 →
   2026-05-21 — exactly 2 years, 47,275 bars = **4 six-month candles and 8 three-month candles**.
   Phase 1's mandatory 6M/3M gate cannot be evaluated at that count, and a 6M gate partitions the
   whole corpus into four blocks. Build the ladder **Monthly-down**; carry 6M/3M as a declared,
   explicitly-unmeasured tier. (Same call the earlier `study-sujantrader-docs` plan already took.)
2. **The five screenshots are not a fidelity test set.** The corpus ends 2026-05-21, his posts are
   ~Aug 2026, and three of his five pairs (NZDCAD, AUDCHF, USDCHF) have no data in the repo at all.
   Using them would require an MT5 fetch extension — out of scope here, worth noting as the only
   route to a true fidelity check.
3. **No G001 authority.** Research only (§6.5). Nothing touches an active config.

### New package `src/research/sujan_crt/`

Follows the sanctioned **reimplement-locally** precedent of `weekly_sweep/` and `visual_crt/`;
production must never import `src/research/`.

| Module | Job | Reuses (do not re-derive) |
|---|---|---|
| `ladder.py` | calendar-true M/W/D/4H parent candles from M15 | `ParentCandleBuilder` via `src/features/htf_bars.py` (F-080 already proved the grid phase) |
| `state.py` | per-TF state + objective | **`src/config_layer/htf_state.py`** — `classify_htf_state`, `resolve_objective`, `HTFState`, `ObjectiveStatus`. Already Sujan's four states; wrap per-TF, do not rewrite |
| `location.py` | Phase 5 location gate | the 9 SMC canonical features from F-076 (order block / breaker / mitigation / PDH-PDL / EQH-EQL) + parent midpoint/high/low |
| `liquidity.py` | Phase 6 sweep | `visual_crt/pools.py` + `geometry.py` (built, tested, F-074-compliant) |
| `activation.py` | Phase 7 chain | `visual_crt/retest.py` for the return leg; F-074 directional displacement |
| `score.py` | the 100-point rubric + ≥90 gate | weights are BEHAVIORAL → config, strict `_require()`, no silent defaults (§6.5) |
| `driver.py` | funnel orchestration + per-phase telemetry | `visual_crt/driver.py` shape |

**Ontology first (§6.6):** register the objective ladder, alignment score, trade-location gate and
the 1:5 rule as canonical nodes in `market_ontology.yaml` **non-frozen sibling sections** before any
production use. `validate_registry() == []` is a gate, not a nicety.

### The measurement design

The 8-phase gate is *built* to reject ~90% of charts, so a faithful implementation lands directly in
the F-026 trap (n=47, INSUFFICIENT_POWER, ~1% funnel completion). The answer is to measure the
**funnel**, not just the final ledger — every rung reported with its own n:

| Rung | Gate | Expected n |
|---|---|---|
| 0 | Phase 6+7 only (sweep + activation) | ≈ F-081's object, n≈944 known |
| 1 | + Phase 5 location | — |
| 2 | + Phase 3/4 daily & 4H objective | — |
| 3 | + Phase 1/2 macro alignment (Monthly/Weekly only) | — |
| 4 | + Phase 8 `≥1:5` | — |
| 5 | full ≥90 rubric | likely single digits — claim nothing |

**The funnel is itself the finding.** It answers "does each phase add or destroy value?" with real
power at the loose end, and makes a small n at Rung 5 legible instead of fatal.

**The headline experiment — Rung 4 with and without the `≥1:5` filter.** Pre-register the
prediction: *the 1:5 gate reduces expectancy, because with target and stop both structurally fixed
it selects thin buffers rather than good trades.* This is the one test that could genuinely surprise,
in either direction.

### Measurement contract — sealed before the detector exists

`MC-SUJAN-XAUUSD-M15-V1` under `configs/research/measurement_contracts/instances/`, floor-green
**before** any detector code (F-081 did this right; F-083 caught what it did wrong — declared but
never executed). Every declared artifact must actually be produced.

- **Cost:** SEM-015 `ComponentCostModel` **ON** — flat 12bps is ~11× too punitive on XAU (F-082).
- **Fills:** SEM-016 `AdverseFill` **ON** — `forward_walk` otherwise books every stop at exactly
  −1.000R.
- **Kernel:** `forward_walk(intrabar_fixed)`. This is **correct here and must be justified in
  writing** against F-088: Sujan's Phase 8 is genuinely one-target, no partial, no trail, so
  `forward_walk` models *his* trade object exactly. Using `multi_tp_walk` would measure a trade he
  does not take. State it so it does not read as a regression.
- **Controls, declared and executed** (`src/research/controls/`): `random_entry`, `long_only`
  (mandatory — gold drift beat 156 of 156 long cells in F-087), plus a **funnel-matched control**:
  same n drawn at random from bars passing Phases 1–2 only. That last one isolates the marginal
  value of Phases 5–8 and is the control F-081 lacked.
- **OOS** split with embargo + purge, actually run, both partitions reported.
- **Null:** block-permutation (F-086's method) for the alignment score, with measured
  autocorrelation → effective n, not raw bar count.

### Build order — cheapest decisive test first

1. **Contract + ontology nodes + controls.** No detector. Floor green.
2. **`ladder.py` + `state.py`** on XAUUSD; assert calendar-true grid and per-TF state series.
   Cheap and independently verifiable.
3. **Rung 0** — reproduce F-081's n≈944 as a calibration check. *If Rung 0 does not roughly
   reproduce, the harness is wrong and everything downstream is noise.*
4. **Rungs 1→5** with per-phase telemetry.
5. **The 1:5 experiment.**
6. Finding + topic sync + session log + `construction_protocol.py validate-completion`.

Stop after step 3 if calibration fails. Steps 1–3 are the afternoon's work and carry most of the
information.

---

## Verification

- `validate_registry() == []`; new ontology nodes present in non-frozen sections only.
- **Byte-identical XAUUSD ledger with the new package absent from the import graph** — this is
  research-side only; nothing in `src/` production may change. `SCHEMA_HASH`, `FEATURE_ORDER_HASH`,
  freeze-pin vector SHA all unchanged.
- Rung 0 n within a stated tolerance of F-081's 944 (calibration gate).
- Every `evidence_artifacts` path in the sealed contract exists on disk **and is git-tracked**
  (the findings gate reads `git ls-files`, not the filesystem).
- `pytest tests/test_current_findings.py tests/test_findings_export.py tests/test_measurement_contract.py tests/test_topic_docs.py tests/test_doc_citations.py`
- Provenance check: `grep -rn "Sujan" src/ configs/` returns **no authority claim** — the docs are
  the *trigger*, and the four-state model and checklist are the AI interlocutor's proposals.
- Determinism: run the driver twice, assert byte-identical funnel counts and ledger.
