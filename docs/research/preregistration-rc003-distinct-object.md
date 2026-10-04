# Pre-registration — RC-003: are the directional-contract-violation bars a distinct object at all?

**Status:** FROZEN before the driver exists and before any result is computed.
**Authority:** diagnostic only. `PL-0` · `economic_claims_allowed: false`. Grants no G001, no ontology
authority, no promotion path, and no authority to alter F-074 — **regardless of outcome**.
**Cycle:** `RC-003` (Lane R). **Authorized by the Principal 2026-09-04** following RC-002's
`INSUFFICIENT EVIDENCE` closure (`RC-002-DEC-CHATGPT-002`).

---

## 1. Origin, and why this is not a continuation

RC-002 closed: the 32 XAUUSD M15 bars that fail `_displacement_entry_allowed`'s Gate 0 are known
directional-contract violations with **UNKNOWN** semantic identity. F-074 is intact and operating
exactly as documented. Position B (occupancy is missing a representable construct) neither stands nor
is disproven. Two successive interpretations — "reversal" and "trend resumption" — were both
withdrawn, the first because its mechanism was false, the second because its supporting statistics
were vacuous against the correct conditional base rate.

`RC-002-DEC-CHATGPT-002` requested **no grant** and set the condition for any follow-on: it must be a
**new evidence cycle, not a continuation**, because continuation smuggles in the premise that
something is there to find.

**This pre-registration therefore does not ask what these bars are. It asks whether they are a
distinct market object at all.** `NOT_A_DISTINCT_OBJECT` is a fully live, pre-registered outcome and
is the outcome the design expects to be unable to reject.

## 2. Corpus — and the fact that it is a different population

`data/mt5/XAUUSD_M15.csv`, sha256 `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56`,
**47,275 bars, 2024-05-22T01:00:00 → 2026-05-21T23:45:00**, broker-server time labelled UTC (F-066),
`decision_status: FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION`.

**Stated plainly:** RC-002 ran on `data/XAUUSD_M15.csv`, 2026-07-07 → 2026-08-06. Phase-1 ends
2026-05-21. **The windows do not overlap. The original 32 bars are not in this corpus.** This is a
fresh construction of the same object on other data — a **replication, not an extension** — which is
exactly what "must justify itself independently" requires. It also retires the standing caveat that
every number in this thread sat on a non-admitted one-month export.

The corpus is loaded through the governed loader and its resolved sha is printed by the run, not
assumed.

## 3. Populations (construction fixed here, not after seeing counts)

Built by the same chain RC-002 used, re-run on the corpus above:
`FeaturePipeline` → magnitude gate → `CRTStateResolver` occupancy.

**Magnitude gate** (the engine's own standard, read from the active config, not hardcoded):
`candle_range >= atr_multiplier_min * atr_abs` AND `|close - open| >= atr_min_displacement * atr_abs`
AND `body_ratio >= body_ratio_min`.

- **VIOLATING** — occupancy is `SWEEP` at the bar, magnitude passes, and the candle's own direction
  (`close` vs `open`) is **opposite** the founding sweep's implied direction
  (`sweep_sig > 0` → SHORT implied; `sweep_sig < 0` → LONG implied).
- **CONTINUATION (control)** — magnitude passes, `displacement_flag == "Displacement"`, and occupancy
  reached `DISPLACEMENT` or `EXPANSION`. This is Gemini's designated control
  (`RC-002-CRIT-GEMINI-001`), not a new invention.

The founding SWEEP bar for each VIOLATING bar is the first bar of its contiguous `SWEEP` streak.

**`sweep_sig` is read from inside `resolve()`** via the RC-003 evidence capture, at the moment the
resolver actually uses it — not recomputed externally after `resolve()` has mutated memory, which is
what the RC-002 harness did.

## 4. The swept extreme — two referents, both pre-registered

Grok's falsifier (`RC-002-PROP-GROK-001`) turns on "the held sweep's extreme on the swept side,"
which admits more than one referent. Both are declared here; neither is chosen after the fact.

- **Referent A (PRIMARY)** — the HTF range bound the founding detector actually tests against:
  `range_h_ref` when the high side was swept, `range_l_ref` when the low side was swept, read at the
  founding SWEEP bar. This is the semantically correct referent under the active
  `thresholds.sweep_geometry: htf_range`.
- **Referent B (SECONDARY)** — the founding SWEEP candle's own extreme (`high` / `low` at that bar).

**Their disagreement is a declared output, not a robustness footnote:** the run reports the count of
bars where A and B give different answers, and whether the primary verdict flips between them.

## 5. Tests

**Primary confirmatory test — exactly one, α = 0.05.**
Geometric, Referent A: does the VIOLATING candle **close beyond** the swept extreme on the swept side
(`close > ref` for a high-side sweep; `close < ref` for a low-side sweep)? `close` rather than wick,
matching this repository's own break-of-structure semantics ("accepted close above structure").
Compared against the CONTINUATION control as a two-proportion contrast with a CI from the block
bootstrap of §6.

**Pre-registered secondaries — three, Bonferroni α = 0.0167, and explicitly unable to rescue a null
primary.**
- **S1** — the same test under Referent B.
- **S2** — *extend* beyond (wick: `high > ref` / `low < ref`) under Referent A.
- **S3** — Gemini's duration test: bars elapsed from the event bar to the next `liquidity_sweep` or
  `break_of_structure`, VIOLATING vs CONTINUATION, log-rank.

No test outside this list of four may be run on this population, and none may be added after seeing
any result.

## 6. Serial dependence is measured, not assumed

`RC-002-CRIT-GEMINI-001` marked `n_eff` `UNKNOWN` and then proceeded on an assumed design effect of 2.
RC-003 measures it: a **block bootstrap / block permutation over the event series**, reusing
`src/research/measurement/bootstrap.py::bootstrap_ci` and the block-permutation precedent established
by F-086. The run reports **raw n, measured n_eff, and the resulting power** for every test. A
p-value computed under an independence assumption is not reported alone.

## 7. Decision rules — interpretation, fixed here, kept separate from the p-values

Grok's kill map, pre-registered as the reading of the outcome:

- VIOLATING bars do **not** close beyond the swept extreme → **`SAME_SIDE_CONTINUATION_THROUGH_SWEEP`
  dies.**
- They **do**, and CONTINUATION bars leave the **other** side → **`NOT_A_DISTINCT_OBJECT` and
  `INDEPENDENT_IMPULSE_WITH_LIVE_SWEEP` die.**
- Neither pattern holds cleanly → no candidate dies; identity stays `UNKNOWN`.

`MISPARENTED_DISPLACEMENT` is **not** tested by this design. Stated so it is not silently treated as
surviving by default.

## 8. Stop conditions

- **Raw n < 150 in either group** → `INSUFFICIENT`. No claim, no test reported as decisive.
- **Primary null AND S3 null** → `NOT_A_DISTINCT_OBJECT` is not rejected; identity remains `UNKNOWN`;
  **RC-003 closes and no further cycle is opened on this population.**
- **No secondary test may be fished from the results** (`RC-002-CRIT-GEMINI-001` §5).
- **D-16 holds:** no OHLCV directional expectancy on these bars. Neither metric is expectancy, by
  construction — both are unsigned with respect to the selection rule, per
  `RC-002-CRIT-DEEPSEEK-001`'s contamination rule.
- A null is a result. It is registered, not re-cut.

## 9. What this explicitly is not

- **Not an `MC-*` measurement contract.** All 13 existing instances declare
  `labels.label_family: forward_walk_economic`; there is no non-economic precedent. RC-003 has no
  entry, exit, cost model, or R. Filing an `MC-*` would require declaring schema-required
  `costs`/`exits` as fictions and would overclaim economic apparatus.
- **Not an economic claim, at any outcome.** Even a decisive positive earns *information*, never
  authority (§6.5 Authority Ladder).
- **Not a re-opening of Position B.** Position B's disposition stays `INSUFFICIENT EVIDENCE` unless a
  separately authorized turn revisits it.
- **Not authority to change anything.** No ontology edit, no new `CRTState`, no `when:` predicate, no
  retune of `_displacement_entry_allowed`, no F-074 change, no config or `ACTIVE_VERSION` change.

## 10. Frozen predictions (stated before computing)

1. **The design expects to be unable to reject `NOT_A_DISTINCT_OBJECT`.** Every prior test on this
   population — outcome comparison, both Phase 4g statistics, the CHoCH analysis — has returned null,
   ambiguous, or vacuous. A positive here would be the first.
2. **Referents A and B will disagree on a non-trivial minority of bars**, concentrated on candles that
   clear the founding candle's extreme without clearing the range bound.
3. **Measured n_eff will be materially below raw n** for both groups, because sweeps cluster.

## 11. Evidence artifacts — every path must exist after the run

The F-083 failure was a sealed contract declaring measurements the run never executed, with nothing
comparing the two. The driver **must** emit all of the following, and the run is a FAILURE if any is
missing:

- `docs/research-readiness/rc003_distinct_object/population_fingerprint.json`
- `docs/research-readiness/rc003_distinct_object/metrics.json`
- `docs/research-readiness/rc003_distinct_object/referent_disagreement.json`
- `docs/research-readiness/rc003_distinct_object/ledger.jsonl`
- `docs/research-readiness/rc003_distinct_object/run_manifest.json` (corpus path + resolved sha +
  active version + config hash + this file's sha256)

---

## 12. EXECUTED — result

*(append-only; nothing above this line is edited after a result is seen)*

### Run manifest

| | |
|---|---|
| Corpus | `data/mt5/XAUUSD_M15.csv`, sha256 `4d73f5cebe33ec91…b26aba56` — **matches the Phase-1 pin** |
| Bars | 47,275 raw / 47,197 after warmup |
| VIOLATING | **n = 553** |
| CONTINUATION (control) | **n = 1,100** |
| Declared floor | 150 per group → **not INSUFFICIENT** |
| Active version | `v2_htfcrt_2026_08` (unchanged) |
| Frozen-prefix sha verified at run | `731ccbcf…` |

### Results

| Test | p(VIOLATING) | p(CONTROL) | diff | 95%/98.3% CI | crosses zero |
|---|---|---|---|---|---|
| **PRIMARY** close-beyond, Referent A | **0.8047** | 0.3891 | **+0.4156** | (+0.3681, +0.4621) | **No** |
| S1 close-beyond, Referent B | 0.7468 | **0.0000** | +0.7468 | (+0.7022, +0.7882) | No — **but INVALID, see below** |
| S2 extend-beyond, Referent A | 0.9042 | 0.4155 | +0.4887 | (+0.4372, +0.5387) | No |
| S3 duration to next structural event | 1.54 bars | 1.88 bars | −0.34 bars | (−0.6101, −0.0507) | No |

Block bootstrap, block = 96 bars (one M15 trading day). Effective blocks: 307 (VIOLATING) / 366
(CONTROL) against raw 553 / 1,100.

Referent disagreement: **32 of 553 = 5.79%**; the primary verdict does **not** flip between
referents.

### Frozen prediction scorecard (§10)

1. *"The design expects to be unable to reject `NOT_A_DISTINCT_OBJECT`."* — **WRONG.** The primary
   is decisively non-null and well powered. This is the first non-null result on this population in
   the entire programme.
2. *"Referents A and B will disagree on a non-trivial minority."* — **WEAKER THAN PREDICTED.** 5.79%
   is a small minority, and the verdict does not flip. The referent choice mattered far less than the
   RC-002 analysis argued it would.
3. *"Measured n_eff will be materially below raw n."* — **CONFIRMED.** 307/553 and 366/1,100.

### Two defects found AFTER seeing the numbers — declared, not repaired

**(a) S1 is invalid by construction.** Its control asks whether a CONTINUATION bar's `close` exceeds
that bar's **own high** (or falls below its own low) — mathematically impossible, so `p(CONTROL) ≡ 0`.
The perfect `0.0000` is what exposed it. S1's +0.7468 is an artefact of a degenerate control and
**must not be read as the strongest result in the table.** It is reported here rather than deleted.

**(b) The PRIMARY control is not matched on proximity — and this is the load-bearing caveat.**
VIOLATING bars sit inside a `SWEEP` state, i.e. price has *just probed the very bound the test asks
about*. CONTINUATION bars are asked a structurally analogous question against their own range bound,
but they are **not positioned near that bound by construction**. So the measured gap
(0.8047 vs 0.3891) cannot presently distinguish:

- *"these candles genuinely break through the swept side"* (the real effect), from
- *"these candles are simply closer to the reference and therefore likelier to cross it"* (a
  proximity selection effect).

This is the same **class** of defect DeepSeek identified in RC-002 — a statistic contaminated by how
the population was selected — in a different dimension: not direction, but **position**.

**Neither defect is repaired inside RC-003.** §8 forbids fishing a new test from the results, and a
proximity-matched control designed after seeing this table would be exactly that. Repairing and
re-running here would convert a pre-registered study into a post-hoc one.

### Kill map (§7), applied exactly as written

- *"VIOLATING bars do **not** close beyond the swept extreme → `SAME_SIDE_CONTINUATION_THROUGH_SWEEP`
  dies."* — They **do** (80.47%). **The candidate does not die.**
- *"They **do**, and CONTINUATION bars leave the **other** side → `NOT_A_DISTINCT_OBJECT` and
  `INDEPENDENT_IMPULSE_WITH_LIVE_SWEEP` die."* — The second clause was **not measured**. The control
  was asked a *mirror* question (did it clear its own bound in its own direction), **not** "did it
  leave the other side." **So these two candidates do NOT die.**
- `MISPARENTED_DISPLACEMENT` was never tested by this design, as §7 states.

**Net: nothing is killed.** One candidate is strongly supported but confounded; two survive
untested; one was out of scope.

### Verdict

**Semantic identity remains `UNKNOWN`.** But the state of evidence has changed materially: the
population is **no longer indistinguishable from its control**, which is what every prior test on it
returned. `SAME_SIDE_CONTINUATION_THROUGH_SWEEP` — Grok's geometric dual of DISPLACEMENT, impulse
*through* the raided side rather than away from it — is now the **leading hypothesis with real,
well-powered, and openly confounded support**.

S3 is statistically non-null but substantively negligible: 1.54 vs 1.88 bars, a third of a bar, with
both groups saturated at ~2 bars because structural events fire almost continuously on this corpus.
It should not be cited as independent corroboration.

### Authority — unchanged

`PL-0` · `economic_claims_allowed: false`. **No ontology edit, no new `CRTState`, no `when:`
predicate, no retune of `_displacement_entry_allowed`, no F-074 change, no config or
`ACTIVE_VERSION` change.** A positive result earns *information*, never authority (§6.5). F-074
remains intact and is not challenged by this finding: the contract's job is to decide what counts as
DISPLACEMENT *of a given sweep*, and a candle breaking through the swept side is — if the effect is
real — a **different object**, not a mis-rejected one.

### What would settle it, in a separately authorized cycle

A **proximity-matched control**: bars equidistant from the same range bound, in the same state, that
did *not* fail the directional contract. That is a new pre-registration, not a re-cut of this one.

### Provenance caveat — the run did not execute against committed HEAD

`src/features/crt_state_resolver.py` carried **3,382 lines of uncommitted working-tree change**
from concurrent sessions when this ran. The run therefore executed against
sha256 `ea5d7068ca958efd2f30d8748c1d04f1168bb5d10807aa81f5d1553ac49e4788`, **not** against `HEAD` (`0fa3768`).

This is verifiable and was checked, not assumed: `tests/test_crt_state_resolver_sweep_geometry.py::
test_funnel_sweep_to_displacement_bypasses_pipeline_flag` **passes at committed HEAD** and **fails
against the working tree** — both before and after RC-003's own additive capture, so the failure is
neither RC-003's nor HEAD's.

**Consequence, stated plainly:** these results are reproducible only against that working-tree state.
They are not reproducible from a clean checkout of `0fa3768`. This is the **F-071 class** — the
committed repository not being the running system — and it bounds the standing of every number in
this section independently of the two methodological defects already declared above.

The driver now records `resolver_source_sha256` in `run_manifest.json` so a future run carries this
pin in the artifact itself rather than in prose. The manifest for **this** run predates that field.

**Reproducibility that IS established:** the run was executed twice end-to-end and reproduced
**exactly** — identical n (553 / 1,100) and identical statistics to 4 decimal places on all four
tests.
