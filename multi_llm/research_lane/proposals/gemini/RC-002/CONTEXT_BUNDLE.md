# CONTEXT_BUNDLE

Generated: 2026-09-03T22:35:45Z

Use ONLY this bundle + PROMPT. Do not invent repo files not listed.


========================================================================
# SOURCE: multi_llm/research_lane/cycles/RC-002/EVIDENCE_DOSSIER.md
# ROLE: the_evidence_read_this_first
========================================================================

# RC-002 — EVIDENCE DOSSIER

> **Read this in full before writing your package.** It is self-contained: every number below
> carries its provenance, every source claim is quoted rather than summarised. Do not assume
> repository facts that are not in this file. If you need a fact that is not here, say
> `UNKNOWN` — do not invent it.
>
> **Authority ceiling:** `promise_rung_max_claim: PL-0`. `economic_claims_allowed: false`.
> Nothing in this cycle promotes a config, edits an ontology, or grants production authority.

---

## 1. The question

Two of the repository owner's own recorded decisions are in conflict, and one of them rests on
an interpretation the executing model (Claude) has since **retracted**.

| | **Source A** | **Source B** |
|---|---|---|
| Claim | Counter-directional `SWEEP -> DISPLACEMENT` is **deliberately illegal** | Occupancy is **missing a construct** for this population |
| Authority | **F-074**, `CH-directional-displacement-contract`, **user-authorized 2026-08-13**, confidence `Certain` | **Position B**, user-decided **2026-09-03** |
| Implemented at | 4 sites: `crt_state_resolver.py:1406` · `crt_engine_v2.py:1107` · `parent_crt.py:162` · `research/visual_crt/geometry.py:14`. Floor: `tests/test_directional_displacement.py` | One documentation entry in `configs/formulas/market_shapes.yaml:blocked_shapes` (that list is read by **no code**) |
| Standing | Intact | **Premise retracted** (see §4) |

F-074's own registered text: *"DISPLACEMENT is a directional impulse away from the swept side
(LONG = bullish close above sweep.price; SHORT = bearish close below). Unsigned energy-only
SWEEP->DISPLACEMENT is no longer legal. Jul 28 XAUUSD 01:15 UTC dump after a LONG sweep is now
REJECT. User-authorized 2026-08-13."*

Note that F-074 **already names and deliberately rejects this exact population**.

Position B, as recorded: *"`SWEEP -> REVERSAL` is a legitimate CRT phenomenon that the ontology
already carries most of the ingredients for; occupancy is missing a representable construct.
The omission is architectural, not observational."*

**The cycle's question:** does Position B survive, and if this population is not "reversal",
what is it?

---

## 2. The measured chain (all of it, with counts)

Corpus: `data/XAUUSD_M15.csv`, **2,038 non-warmup M15 bars**, broker-local timestamps,
**2026-07-07 to 2026-08-06**. Single instrument, single 30-day window, single config epoch.

> **Corpus caveat, stated up front:** this is **not** the repository's frozen Phase-1 admitted
> corpus (`data/mt5/XAUUSD_M15.csv`, sha `4d73f5ce...`, 47,275 bars, ends 2026-05-21). It is a
> separate one-month export. No admission decision attaches to it.

```
675   bars where feature_states["displacement_flag"] == "Displacement"
        ^ FM-069 is a SHAPE-only test (body_size > candle_range * 0.6). No ATR term at all.
127   of those also clear the engine's own magnitude standard
        (candle_range >= 1.0*atr_abs AND |close-open| >= 1.2*atr_abs AND body_ratio >= 0.65)
 88   of those 127 (69.29%) still never reach DISPLACEMENT/EXPANSION occupancy
```

Those 88 were bucketed exhaustively — **zero unattributed**:

| Bucket | n | Meaning |
|---|---|---|
| `FAR` (gap > 10 bars since last SWEEP) | 38 | No SWEEP precondition anywhere near. Funnel behaving as declared. |
| `RECENT` (gap 4-10) | 13 | — |
| `JUST_EXPIRED` (gap <= 3) | 5 | The originally-suspected mechanism. A **minority** pattern. |
| **`DIRECTIONAL_CONTRACT_VIOLATION`** | **32** | **SWEEP held, magnitude passed, candle moved the *opposite* way -> rejected by Gate 0.** |

**All 32 fail on the directional contract, deterministically. Zero sweep-age violations.**
These 32 bars are the entire subject of this cycle.

### What the evidence layer says about those 32

| Measurement | Result |
|---|---|
| `break_of_structure` + `trend_bias` direction-consistent with the candle | **30 / 32 (93.75%)** |
| `change_of_character` (CHoCH) fires and matches | **0 / 32 (0%)** |
| No consistent signal on any of 5 checked features | **1 / 32 (3.1%)** |
| CHoCH becomes consistent at `t+1` or `t+2` (timing lag) | **0 / 32 (0%)** |
| CHoCH never consistent anywhere in `[t-2, t+2]` (true omission) | **30 / 32 (93.8%)** |
| CHoCH already consistent at `t-1`/`t-2`, silent by `t` (anticipatory) | **2 / 32 (6.2%)** |

### Forward-outcome comparison (already run, pre-registered, frozen before computing)

CONTINUATION (n=39) vs REVERSAL-CANDIDATE (n=32), exit-agnostic MFE/MAE in R at horizons
20/40/96 bars, bootstrap CIs, `passive_exposure_r` control.

**Verdict: AMBIGUOUS.** Every net cell's CI crosses zero, both populations, all three
horizons; the between-population difference CI crosses zero at every horizon; neither
population is distinguishable from passive exposure. This was the pre-registered prediction.
**It supports neither side** — do not read it as evidence for either.

---

## 3. The three source facts, quoted

**(a) The gate — `src/features/crt_state_resolver.py:1406`** (the engine twin at
`src/config_layer/crt_engine_v2.py:1107` carries the same contract):

```python
def _displacement_entry_allowed(self, raw):
    """Engine-grade DISPLACEMENT entry (try_sweep_to_displacement).
    ONLY from SWEEP. Gates (all must pass):
      0. directional contract (CH-directional-displacement-contract):
         LONG  -> close > open; SHORT -> close < open
      1. sweep age <= max_sweep_age_candles
      2. abs(close-open) >= atr_min_displacement * atr_abs
      3. body_ratio >= body_ratio_min
      4. candle_range >= atr_multiplier_min * atr_abs """
    ...
    want = int(self._memory.displacement_direction or 0)   # +1 LONG / -1 SHORT at SWEEP entry
    if want == 0: return False                              # fail-closed
    if want > 0 and not (float(close) > float(open_)): return False
    if want < 0 and not (float(close) < float(open_)): return False
```

**(b) CHoCH — `src/features/smc/choch.py`**, in full:

```python
def change_of_character(break_of_structure: float, trend_bias: float) -> float:
    if break_of_structure == 0 or trend_bias == 0:
        return 0.0
    if (break_of_structure > 0) != (trend_bias > 0):
        return break_of_structure
    return 0.0
```

Its own module docstring: *"a break-of-structure event that goes AGAINST the prevailing trend
is a 'change of character'...; a break-of-structure event that **agrees** with the prevailing
trend is **ordinary continuation** (BOS, not CHoCH)."*

**(c) `trend_bias` — `src/features/feature_pipeline.py:991-996`**:

```python
df["trend_bias"] = np.where(df["ema_fast"] > df["ema_slow"], 1,
                   np.where(df["ema_fast"] < df["ema_slow"], -1, 0))
```

Observed vocabulary across all 2,038 bars: `Bullish` 968 / `Bearish` 1,070. **Never neutral.**

---

## 4. RETRACTED — the mechanism Position B was decided on

Position B was taken on this claim, which is **false and withdrawn**:

> *"`trend_bias` is reactive enough that one large-magnitude candle flips the sign within that
> bar — so a genuine reversal candle moves `break_of_structure` and `trend_bias` together, same
> bar, same direction, and CHoCH is structurally unable to fire."*

Measured on the same 32 bars:

- `trend_bias` **does not flip** at `t` on **30 / 32**. Only 2 flip.
- `trend_bias` at `t-1` was **already aligned** with the candle's own direction on **29 / 32 (90.6%)**.

**Corrected mechanism:** nothing flips. The trend was already established in the candle's
direction *before* the candle arrived. BOS and `trend_bias` agree because both reflect the
same already-prevailing direction, and CHoCH is correctly silent because - by its own
definition quoted in section 3(b) - **there is genuinely no character change.**

**This falsification STANDS.** It is a direct observation, not a rate comparison.

**But the replacement reading is ALSO withdrawn - see section 5.** An earlier version of this
dossier concluded from the above that the 32 bars are "trend resumption after a counter-trend
sweep." That conclusion is **not supported** and has been retracted. `SweepReversal` remains a
name with no established referent; the population's identity is **UNKNOWN**.

---

## 5. Base-rate controls - BOTH Phase 4g statistics are vacuous

The retraction originally shipped with no denominator. Both of its statistics have now been
tested against the correct conditional base rates. **Both fail.**

| Phase 4g statistic | Observed | Correct base rate | Binomial P(>=obs) | Verdict |
|---|---|---|---|---|
| `trend_bias` did **not** flip at `t` | 30/32 (93.8%) | **95.48%** — all bars | **0.826** | **VACUOUS** |
| `trend_bias(t-1)` already aligned with candle dir(t) | 29/32 (90.6%) | **89.66%** — see below | **0.574** | **VACUOUS** |

**Why the second one died.** The first published denominator for it was the global 47.86%
(974/2,035 over all bars), which gave p ~ 4e-07 and looked decisive. That denominator was
**wrong**. The statistic is conditioned by the selection rule: these bars are *defined* as
candles moving against the founding sweep, so if sweeps tend to be counter-trend, the candle
mechanically tends to move *with* the trend. The non-circular question is therefore:

> **Is a founding sweep counter-trend by nature?**

```
bars where sweep_sig fired:                   203
sweep implied direction OPPOSITE trend_bias:  182/203 = 89.66%
the 32 bars:                                   29/32  = 90.62%
P(>=29/32 | corpus rate 0.8966) = 0.5744
```

**Founding sweeps in this construction are counter-trend 89.66% of the time corpus-wide.** The
32 bars' 90.62% is indistinguishable from that. The statistic restates a structural property of
the sweep detector; it says nothing about this population.

Supporting ladder (`trend_bias(t-1)` aligned with candle dir(t)), for completeness:

| Stratum | rate |
|---|---|
| all bars | 974/2,035 = 47.86% |
| magnitude-qualifying | 74/127 = 58.27% |
| SWEEP-held | 329/728 = 45.19% |
| qualifying AND SWEEP-held | 28/36 = 77.78% — **not an independent control; it contains most of the 32** |
| contract-VIOLATING (the 32) | 29/32 = 90.62% |
| contract-OK, reached occupancy (the 39) | 15/39 = 38.46% |

The 90.62% vs 38.46% separation is **exactly what the selection-circularity predicts**, so it
does not rescue the statistic either.

**Provenance of this section:** it exists because the DeepSeek `CRITIQUE`
(`RC-002-CRIT-DEEPSEEK-001`, turn 1 of this cycle) named the missing conditional base rate as a
blocking defect. The measurement was then run and confirmed it. **The relay caught this, not the
executor** - which is the strongest available evidence that role-separated critique adds value
here (`scorecard.md`, D-19).

---

## 5b. What is actually established, and what is not

**Established:**
- All 32 bars fail the directional contract, deterministically (32/32).
- The full 88-bar attribution (38/13/5/32), zero unattributed.
- CHoCH never fires for them and this is not a timing lag (0/32 lag, 30/32 true omission).
- The original "same-bar `trend_bias` flip" mechanism is **false**.
- Founding sweeps are counter-trend 89.66% of the time in this corpus.

**NOT established:**
- That these bars are "reversals" (the mechanism claimed for it was false).
- That these bars are "trend resumption" (the statistics claimed for it are vacuous).
- That they are economically distinct from continuation bars (outcome study: AMBIGUOUS).
- **Any identity for this population at all.** It is `UNKNOWN`.

## 6. Known gaps — declared, not hidden

1. **n = 32, one instrument, one 30-day window, one config epoch.** No holdout, no second
   instrument, no second window.
2. **Non-admitted corpus** (§2 caveat).
3. **The 13 `RECENT` bars were never decomposed further.** They are attributed but not explained.
4. **`sweep_sig` vs `liquidity_sweep` disagree constantly** and this is unexplained by any
   single mechanism: of 203 bars where the governing founding signal fired, **3.45% agree**,
   **58.13%** have the feature layer silent, **38.42%** have it asserting the **opposite** side.
   Volatility and session stratification are flat; only range-age has texture (49.4% opposite
   at 0-5 bars since reset, declining to 23.9% at 11-15).
5. **`change_of_character` appears in exactly zero `when:` clauses** in
   `configs/formulas/market_crt_states.yaml` (grep-confirmed, 0 occurrences). It is computed
   and classified every bar and read by no predicate. **Out of scope for this cycle** —
   recorded so you do not treat it as new.
6. **Dangling citation.** The `market_shapes.yaml:SweepReversal` blocker cites
   `docs/implementation_plan/no-context-from-soruces-humming-tower.md`, which exists on the
   author's disk but is **untracked** — it resolves to nothing from any other clone.

---

## 7. What this cycle may NOT do

No voting; no model's answer is tallied against another's. No ontology edit, no new
`CRTState`, no new `when:` predicate, no retune of `_displacement_entry_allowed`, no reversal
of F-074, no config or `ACTIVE_VERSION` change, no promise-rung change. No economic claim.
No model writes code. Claude implements nothing without a final DECISION from the Principal.


========================================================================
# SOURCE: src/features/smc/choch.py
# ROLE: choch_formula_source
========================================================================

"""features.smc.choch — Change of Character (CHoCH).

Definition (standard ICT/SMC): a break-of-structure event that goes AGAINST the prevailing
trend is a "change of character" (a potential reversal signal); a break-of-structure event that
agrees with the prevailing trend is ordinary continuation (BOS, not CHoCH).

`configs/formulas/market_ontology.yaml:32` explicitly excludes "detection state-machines
(BOS/CHOCH/pivot)" from the ontology layer. This module does NOT reopen that exclusion — it
adds NO new detection state machine and does NO swing/pivot scanning of its own. It is a pure,
stateless algebraic combination of two ALREADY-REGISTERED canonical structural-state features
(`break_of_structure` FM-057, `trend_bias` FM-054), exactly like the ontology's existing
`derived_metrics` computation class combines other registered primitives. The distinction
matters: the exclusion is about NOT building a new BOS/CHoCH state machine in the ontology
layer; reusing the existing, already-governed BOS output is a different, smaller act.
"""

from __future__ import annotations


def change_of_character(break_of_structure: float, trend_bias: float) -> float:
    """Signed {-1, 0, +1}: the direction of a genuine character change, or 0.0 when there is
    no break event, no defined trend to change FROM (`trend_bias == 0`), or the break agrees
    with the prevailing trend (ordinary BOS continuation, not CHoCH).

    `break_of_structure` and `trend_bias` are expected in the same {-1, 0, +1}-ish signed
    convention the canonical vector already uses for both features."""
    if break_of_structure == 0 or trend_bias == 0:
        return 0.0
    if (break_of_structure > 0) != (trend_bias > 0):
        return break_of_structure
    return 0.0


========================================================================
# SOURCE: configs/formulas/market_shapes.yaml
# ROLE: blocked_shapes_incl_sweepreversal_entry
========================================================================

# ═══════════════════════════════════════════════════════════════════════════
# MARKET SHAPES — Layer 5 of the semantic pipeline (roadmap Phase 5, 2026-07-24)
# ═══════════════════════════════════════════════════════════════════════════
# WHAT layer, declarative only (CLAUDE.md §6.5: authority user_approved, grants NO runtime
# authority — shadow layer, nothing on the decision spine consumes it).
#
# A MARKET SHAPE is a recurring bar-level structure, identified two ways:
#
#   FINE identity  — content-addressed: "MS-" + sha256[:16] of the Market Context PROJECTED onto
#                    the `projection` dimensions below. Total function: every bar has one. No
#                    clustering heuristics, no k to pick, no fitted artifact — two bars share a
#                    shape id iff their projected semantic descriptions are IDENTICAL.
#   COARSE label   — the ordered `shapes` predicates below. First match names the bar; a bar
#                    matching nothing keeps its fine id with name UNNAMED (an explicit identity,
#                    not a fallback). Predicates are AND across features, OR within a state list,
#                    and may ONLY reference declared states of vector-bound stateful identities
#                    whose category is inside the projection — the loader REJECTS anything else,
#                    so a typo'd state name is a load error, never a silently-dead predicate.
#
# SCOPE HONESTY (single-bar): these are BAR-level structures readable from one bar's states.
# Multi-bar sequence shapes (rotation legs, exhaustion sequences) are a different construction —
# see `blocked_shapes`. NOTE the IC-003B finding killed *fitted* sequence-shape libraries
# (k* unstable); this layer is deliberately the opposite construction: exact discrete recurrence
# over declared semantics, with zero fitted parameters.
version: 1
authority: user_approved

# Context dimensions that DEFINE shape identity. Time and Volume are deliberately EXCLUDED:
# they are conditioning variables for the statistics layer ("how does LiquidityGrab behave BY
# session / BY participation"), which is only possible if they stay OUTSIDE the shape identity.
# Momentum is excluded because its only stateful identity (rsi_state) has no vector slot.
projection:
  - Trend
  - Volatility
  - Liquidity
  - MarketStructure

# First-match precedence, most specific first. Family groups directional variants for
# coarse-grained statistics.
shapes:
  - name:   DoubleSweepTrap
    family: LiquidityTrap
    when:
      double_sweep: [DoubleSweep]
    description: "Both sides swept in quick succession — a two-sided stop-run; neither side in control."

  - name:   BuySideLiquidityGrab
    family: LiquidityGrab
    when:
      liquidity_sweep: [BuySideSweep]
    description: "Stops above the prior swing high taken and rejected — the CRT founding event, bearish-leaning."

  - name:   SellSideLiquidityGrab
    family: LiquidityGrab
    when:
      liquidity_sweep: [SellSideSweep]
    description: "Stops below the prior swing low taken and rejected — bullish-leaning."

  - name:   BullishBreakoutExpansion
    family: BreakoutExpansion
    when:
      break_of_structure: [BullishBreak]
      volatility_regime:  [HighVolatility]
    description: "Accepted close above structure while volatility is in its top tercile — breakout with energy."

  - name:   BearishBreakoutExpansion
    family: BreakoutExpansion
    when:
      break_of_structure: [BearishBreak]
      volatility_regime:  [HighVolatility]
    description: "Accepted close below structure in a high-volatility regime."

  - name:   BullishStructuralBreak
    family: StructuralBreak
    when:
      break_of_structure: [BullishBreak]
    description: "Accepted close above the prior swing high without the volatility-expansion qualifier."

  - name:   BearishStructuralBreak
    family: StructuralBreak
    when:
      break_of_structure: [BearishBreak]
    description: "Accepted close below the prior swing low without the volatility-expansion qualifier."

  - name:   Compression
    family: Compression
    when:
      volatility_regime:  [LowVolatility]
      liquidity_sweep:    [NoSweep]
      break_of_structure: [NoBreak]
      higher_high:        [NoHigherHigh]
      lower_low:          [NoLowerLow]
      double_sweep:       [NoDoubleSweep]
    description: "Bottom-tercile volatility and zero structural events — coiling; the pre-expansion condition."

# Roadmap shapes that CANNOT be declared honestly from the current state vocabulary. Listed so the
# gap is explicit and greppable instead of approximated away. Do not implement these as predicates
# until their blockers clear.
blocked_shapes:
  - name:    TrendContinuation
    blocker: >
      UNSATISFIABLE as a single-bar predicate — proven by the Layer-6 statistics run (0 matches
      in 3,871 bars) and then derived: higher_high, break_of_structure and liquidity_sweep all
      compare against the SAME reference (prev last_swing_high_price), so HigherHigh (high>ref)
      forces EITHER close>ref (BullishBreak) OR close<=ref (BuySideSweep) — exhaustively. The
      v1 predicate {Bullish, HigherHigh, NoSweep, NoBreak} is therefore a logical contradiction
      (mirror argument for the bearish side). Continuation-with-extension is a SEQUENCE property
      (an extension bar FOLLOWED by holding bars) — same multi-bar blocker class as RangeRotation.
      Removed in spec v1 rather than redefined: weakening the predicate to "aligned trend, no
      events" would absorb most of the residual and mean something different.
  - name:    MeanReversion
    blocker: "needs momentum MAGNITUDE states; FM-022/023 magnitudes are price-level-scaled (F-061) — banding is blocked on FM-030/031 activation"
  - name:    TrendExhaustion
    blocker: "same momentum-magnitude blocker as MeanReversion"
  - name:    RangeRotation
    blocker: "a MULTI-BAR sequence property (legs between bounds); not readable from one bar's states — Phase-5+ sequence construction"
  - name:    SweepReversal
    blocker: >
      UNSATISFIABLE under the current directional-contract gate — measured, not assumed
      (docs/implementation_plan/no-context-from-soruces-humming-tower.md, Phases 4a-4e).
      `_displacement_entry_allowed` requires the candle's close-vs-open sign to match the
      founding SWEEP's implied continuation direction; every magnitude-qualifying, SWEEP-held
      candle moving the OPPOSITE way is rejected (32/32, deterministic — Residual Attribution).
      `break_of_structure` and `trend_bias` independently and correctly identify the reversal on
      30 of those 32 bars (93.75%) — the evidence exists — but `change_of_character` can never
      represent it: its formula (features/smc/choch.py) requires the two inputs to DISAGREE, and
      the trend was ALREADY established in the candle's direction before it arrived, so BOS and
      trend_bias agree and CHoCH is correctly silent (30/32 TRUE_OMISSION, checked t+1/t+2 —
      never a timing lag, Phase 4e).
      CORRECTED 2026-09-04: an earlier version of this entry said the two inputs FLIP TOGETHER
      same-bar on a reversal candle. That was wrong and is retracted. Measured: trend_bias does
      NOT flip at t on 30/32 bars, and was already aligned with the candle's direction at t-1 on
      29/32 (90.6%). These are therefore NOT trend reversals — the founding sweep pointed AGAINST
      an already-prevailing trend and the candle moved WITH that trend (trend resumption after a
      counter-trend sweep). The name `SweepReversal` is retained for traceability but is a
      MISNOMER on this evidence. The directional-contract rejection is correspondingly more
      defensible than first characterised: the engine declines to call a candle moving against a
      sweep a DISPLACEMENT *of that sweep*. User-decided Position B was taken on the pre-correction
      characterisation and should be revisited against this one; representability design remains a
      separate, not-yet-authorized turn.
      CORRECTED AGAIN 2026-09-04 (RC-002 turn 1, DeepSeek CRITIQUE RC-002-CRIT-DEEPSEEK-001):
      the 2026-09-04 "trend resumption" reading above is ALSO withdrawn. Its supporting statistic
      (trend_bias at t-1 already aligned with the candle direction, 29/32 = 90.62%) was published
      against a global base rate of 47.86% and looked decisive at p~4e-07. That denominator was
      WRONG: the population is defined as candles moving against the founding sweep, so the
      statistic is conditioned by the selection rule. Measured on the non-circular question --
      "is a founding sweep counter-trend by nature?" -- the answer is 182/203 = 89.66% corpus-wide,
      against which 29/32 gives p = 0.574. VACUOUS. Both Phase 4g statistics are now dead
      (no-flip p=0.826; pre-aligned p=0.574). What STANDS: the 32/32 directional-contract
      rejection, the 88/88 attribution, the 0/32 CHoCH timing-lag result, and the falsification of
      the original same-bar-flip mechanism (a direct observation, not a rate). What does NOT stand:
      any identity for this population. It is UNKNOWN -- neither "reversal" nor "resumption" is
      established. Position B is therefore neither supported nor refuted by this entry; it remains
      open on the user's decision. Full adjudication:
      multi_llm/research_lane/proposals/deepseek/RC-002/CRITIQUE.md


========================================================================
# SOURCE: docs/governance/SEMANTIC_REVIEW_PROTOCOL.md
# ROLE: the_ten_verdicts_and_never_conclude_defect_from_difference
========================================================================

# Adversarial Semantic Review Protocol

**Status:** ACTIVE charter (adopted 2026-08-13)
**Long-form of:** CLAUDE.md §6.8 (thin rule of the same name)
**Enforcement (floor):** `tests/governance/test_semantic_review_protocol.py`
**Authority:** review discipline only — grants **no** production, promotion, economic, or
ontology-edit authority (§6.5).
**Code wins** on conflict with this document.

> **Non-duplication clause.** This charter **does not restate** the doctrines it composes.
> Each rule below points at its existing owner:
>
> | Primitive | Owner (authoritative) |
> |---|---|
> | Fail-closed on unknown meaning | [`SEMANTIC_OS_CONTRACT.md`](SEMANTIC_OS_CONTRACT.md) rule 4 · CLAUDE.md §6.5 (no silent config defaults) |
> | Never silently resolve a conflict → `TruthConflict` | CLAUDE.md §6.2 rules 3 / 4 · the `CORRECTED: <old> -> <new>` ritual |
> | User-authorization gate calibration | [`DOCUMENTATION_DRIFT_PROTOCOL.md`](DOCUMENTATION_DRIFT_PROTOCOL.md) Step 3 |
> | Grounding a repository claim | CLAUDE.md §6.7 · `scripts/governance/query_semantic_os.py --ground` |
> | Behavior-preservation obligations of the turn | [`TASK_CLASSIFICATION_BEHAVIOR_POLICY.md`](TASK_CLASSIFICATION_BEHAVIOR_POLICY.md) |
> | Overclaim classes + pre-registration ritual | [`EPISTEMIC_INTEGRITY.md`](EPISTEMIC_INTEGRITY.md) (Program E-001) |
> | Meaning of market concepts | [`MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md`](MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md) |
> | Which model owns which market question | [`MODEL_INTENT_AUTHORITY_REGISTER.md`](MODEL_INTENT_AUTHORITY_REGISTER.md) (MIAR) |
> | Change lifecycle once a fix is authorized | [`REPOSITORY_CONSTRUCTION_PROTOCOL.md`](REPOSITORY_CONSTRUCTION_PROTOCOL.md) |
| Sujan CRT identity during extraction | [`SUJAN_CRT_IDENTITY_EXTRACTION_SYSTEM.md`](SUJAN_CRT_IDENTITY_EXTRACTION_SYSTEM.md) — Sujan-scoped overlay; load before any Sujan implementation / contract / ontology / backtest. Does not recertify CRT. |

---

## 1. Purpose

A semantic review determines whether repository behavior **means** what it claims — not merely
what it does. It exists because the repository's expensive failures have been *meaning*
failures, in both directions:

- **False negatives** — real semantic defects that survived because each layer looked
  internally consistent (F-060's Gaussian kernel degenerating to a near-constant; F-061/F-064's
  dimensional mix saturating four consumers; F-066's broker-clock session mislabel).
- **False positives** — differences reported as defects that were architecture working as
  designed (F-037's gate-OFF research spine, USER-CLASSIFIED INTENDED; F-036's zone knobs,
  tunable-but-inert by redundancy, whose first mechanism claim was itself an overclaim).

Both classes cost the same review budget. This protocol makes the reviewer carry the burden of
semantic analysis and end in an explicit classification, rather than in an edit.

**The user is not assumed to be a trading-domain expert.** Do not ask the user to resolve
domain semantics that standard market knowledge, repository contracts, architecture, config,
naming, lifecycle semantics, or existing evidence can establish. Ask only where the repository
genuinely does not establish which *policy* is intended (§16).

---

## 2. The five review questions

Every semantic investigation answers these, in order:

1. What does the behavior **currently mean**?
2. What **should** it mean, per domain semantics?
3. Has the repository **established** that meaning?
4. Does the implementation **violate** it?
5. Is a change **authorized**?

A review that answers 1 and 4 but skips 2, 3, or 5 is incomplete, not fast.

---

## 3. Two authority ladders — and their reconciliation

The repository already carries authority orderings (CLAUDE.md §4.0 Runtime Truth Precedence,
§6.5 Authority Ladder and precedence hierarchy, MIAR §0, the ontology contract). **This charter
adds none.** It states the one distinction a reviewer needs, so that answering question 1 and
answering question 2 do not use the same list.

### 3.1 The CURRENT-truth ladder — *what does the system do today?*

| Rung | Source |
|---:|---|
| 1 | Executable source code and observed runtime behavior |
| 2 | Active production configuration (`configs/production/ACTIVE_VERSION` → §4.0 Tier 0) |
| 3 | State topology and lifecycle definitions |
| 4 | Tests that encode intentional contracts |
| 5 | Governance records / findings / certified evidence |
| 6 | Architecture documentation and knowledge artifacts |
| 7 | Historical analysis (`docs/analysis/` — point-in-time, not living) |
| 8 | LLM inference or convention |

Documentation explains intent; it does not establish what the code does. Semantic OS,
encyclopedia, and knowledge-book artifacts are advisory and are never production authority.

### 3.2 The MEANING ladder — *what is this concept?*

**Unchanged and cited, not restated:** the market ontology is authority #1 for meaning with
literal supersession (`MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md`), followed by the feature
pipeline, MIAR (model intent), implementations, then research (`MODEL_INTENT_AUTHORITY_REGISTER.md`
§0 ranks 1–5).

### 3.3 Reconciliation clause (non-optional)

The two ladders answer **different questions** and neither supersedes the other:

- The **CURRENT** ladder never grants meaning. That the code computes X does not make X the
  correct definition of the concept it is named for.
- The **MEANING** ladder never asserts runtime state. That the ontology defines X does not
  make X what the active configuration executes. `configs/production/ACTIVE_VERSION` remains
  Tier 0 for runtime truth (§4.0); "ontology first" governs the **origin and requirement** of a
  change, not automatic unvalidated runtime mutation (`MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md`,
  mechanical constraint 2).

**Divergence between the two ladders is the finding.** Report it as a §6.2 `TruthConflict`
(source A, source B, evidence, impact, recommendation). A reviewer does not pick a winner.

### 3.4 Evidence-quality bands

A **banding of the CURRENT ladder**, not a new scale:

| Band | Rungs | Examples |
|---|---|---|
| **HIGH** | 1–4 | executable source behavior, active config, authoritative ontology node, explicit contract, deterministic test contract, independently reproduced runtime trace |
| **MEDIUM** | 5–7 | architecture documentation, canonical knowledge book, repository encyclopedia, governance descriptions |
| **LOW** | 8 | comments, names, historical notes, previous LLM interpretations, assumptions |

LOW evidence is never promoted into a production semantic claim without corroboration.

**Distinct from claim strength.** `HIGH/MEDIUM/LOW` grades *the source*. `Certain · Likely ·
Possible` grades *the claim* (§6.2 Findings Mandate). Do not merge the vocabularies: a HIGH
source can support a `Possible` claim, and a `Certain` claim always requires HIGH evidence.

---

## 4. The primary rule

**Never conclude "defect" from difference alone.** Six rules, all load-bearing:

- **Different ≠ wrong.** Two layers using different vocabularies may be answering different questions.
- **Unreachable ≠ bug.** A branch not reached under the active configuration may be dormant-but-valid.
- **Configured ≠ must be reachable.** A config token is not a promise that every consumer can emit it.
- **Validated ≠ fully valid.** A validator's PASS promises only what that validator owns.
- **Absent ≠ defective.** An unused value, unexercised branch, or unobserved state violates nothing unless a contract says so.
- **Current ≠ correct.** "The code does X, therefore X is right" is not an argument. State: *the code does X; the domain meaning is Y; the architecture indicates Z; therefore X is / is not consistent with the intended contract.*

None of the following is, by itself, evidence of a defect: two configs with different
vocabularies · one layer producing a value another cannot · a validator accepting what another
rejects · similar names · a token unused by one consumer · a branch unreachable under the active
config · a check present in one implementation and not another · a test expecting what feels
intuitive · another model calling it a bug · behavior that looks inconsistent in isolation.

### Candidate explanations (consider before concluding)

**A** real semantic defect · **B** intentional architectural separation · **C** compatibility
boundary · **D** derived vocabulary · **E** policy vocabulary · **F** lifecycle-specific
vocabulary · **G** dormant but legitimate capability · **H** stale / legacy vocabulary ·
**I** defense in depth · **J** incomplete contract · **K** genuinely unresolved design decision.

---

## 5. CURRENT / INTENDED / RECOMMENDED — never collapsed

Three tiers that must stay textually separate in every review:

| Tier | Question | Existing repository anchor |
|---|---|---|
| **CURRENT** | What do code, config, and tests do today? | §3.1 ladder · `active_models.yaml` `runtime` / `evidence` layers |
| **INTENDED** | What should this mean in the domain? | Ontology (meaning) · MIAR (model intent; an implementation contradicting MIAR is *Semantic Drift*, not a silent redefinition) · `active_models.yaml` `intent` layer |
| **RECOMMENDED** | What should the repository ideally do? | Non-binding. CLAUDE.md §13.8 — advice is everyone's; **no model's advice, including Claude's own, is authority.** |

Collapsing CURRENT into INTENDED produces "the code is correct because it is the code."
Collapsing RECOMMENDED into INTENDED smuggles a preference in as a contract.

---

## 6. Domain-first reasoning

Establish domain meaning **before** implementation terminology. Assume the reader is not a
trading expert; explain the concept in plain language first.

Concepts whose domain meaning must be established before reviewing code that claims them:
candles · OHLC geometry · sessions · market structure · liquidity · displacement · sweep ·
range · expansion · retest · execution · direction · entry · stop loss · take profit · ATR ·
volatility · timeframe · clock and session boundaries · risk · reward:risk · data integrity ·
validation · chronology · causal ordering.

Separate four levels, and never let one impersonate another:

1. **Universal market/domain semantics** — use the standard meaning.
2. **Repository-specific CRT semantics** — trace the repository (`state_identity.py`
   `VALID_TRANSITIONS`, `state_topology.py`, `docs/architecture/event-taxonomy.md`).
3. **Repository-specific strategy policy** — a choice, not a fact.
4. **Implementation detail** — never a source of meaning.

Do not invent proprietary strategy semantics. If none of the four establishes the meaning with
sufficient confidence: **USER AUTHORIZATION REQUIRED** (§16).

---

## 7. Semantic ownership analysis

When two layers appear inconsistent, identify **what question each layer answers**.

For models and engines the ownership answer **already exists** — reuse it, do not rebuild it:
MIAR §4 market-question ownership matrix (exactly one Owner per question),
`docs/topics/model-intent-and-feature-ownership.md` (feature × model matrices), and
`WHAT_HOW_WHO_EXECUTABLE_BOUNDARY_MAP_V1.md`.

This section governs the concepts those do **not** cover — session, ATR units, validation,
direction, timeframe, timestamps, configuration tokens, state labels, identifiers, model
scores. Build the table:

| Layer | Question answered | Input vocabulary | Output vocabulary | Authority | Consumer |
|---|---|---|---|---|---|

Worked shape — "session" legitimately means five different things:

| Layer | Question answered |
|---|---|
| Feature classification | What market/session label does this timestamp belong to? |
| Execution filter | Is execution permitted at this time? |
| CRT structural window | Is this timestamp inside the lifecycle's permitted window? |
| Scoring | How favorable is this time? |
| Adapter / gate | Does this feature label pass this consumer's policy? |

Then ask the only question that matters: **must these vocabularies be identical?** Never unify
two layers merely because they share a word. F-066 is the worked precedent — the session
*feature* was a mislabel and was fixed; the session *filter* was empirically tuned on broker
time and was deliberately left untouched, because relabeling it is an economic decision, not a
bug fix.

---

## 8. Vocabulary reachability

When a configuration carries a token one runtime path cannot emit, do not classify it as a
defect. Answer all twelve:

1. Who owns the vocabulary? 2. Who consumes the configuration? 3. Are there multiple consumers?
4. Does each consumer use the same semantic vocabulary? 5. Is the value derived rather than
configured? 6. Is it adapter vocabulary? 7. Is it compatibility vocabulary? 8. Is it dormant but
intentionally retained? 9. Is it legacy/stale? 10. Would making it reachable change domain
semantics or execution policy? 11. Would removing it break another consumer? 12. Does an
existing test incorrectly assume vocabulary identity?

**Exit rule.** Declare a reachability defect **only** where the architecture establishes that
producer and consumer are supposed to share a vocabulary. Where that relationship is not
established: **USER AUTHORIZATION REQUIRED**.

---

## 9. Validation ownership

Not every validator must validate everything. For each validation layer determine: what it
owns · what it can observe · what another layer can observe that it cannot · its scope (row /
file / sequence / dataset / runtime / execution) · whether it is a hard safety gate or an
informational pre-flight · what PASS actually promises · which layer is the final gate.

A validation split is **valid** when ownership is explicit and the final invariant is still
fail-closed before harmful downstream use. It becomes **unsafe** when a consumer mistakes
partial validation for complete validation, a downstream safety gate can be bypassed, a
research path bypasses the canonical validation rail, a validator's *name* promises more than
its contract, or an accepted artifact can reach an economic consumer with the missing invariant
never enforced anywhere.

**The load-bearing distinction:**

> "validator does not check X"  **is not**  "system permits X to reach the trading engine."

F-039 is the worked precedent: the L3 dataset-integrity pre-flight runs at only two call sites,
every other consumer streams with the always-on inline L1/L2 backstop. The correct verdict was
a *single-layer fragility* plus a corrected overclaim in a docstring — explicitly **not** an
invalidation of the research built on those streams, because the backstop did enforce schema
and chronology. L3 adds confidence, not validity.

---

## 10. Contamination analysis

For every suspected validation or semantic gap, determine whether invalid meaning propagates:

```text
INPUT → VALIDATION → NORMALIZATION → FEATURES → STATE → CONTEXT → SHAPE → CRT
      → MODEL TESTIMONY → DECISION → EXECUTION GEOMETRY → RISK → ORDER
```

Ask: can the invalid object survive? which derived quantities become contaminated? can it reach
ATR, structure, direction, SL/TP, RR, model scores, research conclusions, production execution?

**Severity rule:** a gap is materially more serious the more boundaries an invalid semantic
object crosses before rejection. A gap that is contained at the next boundary is a
defense-in-depth observation; a gap that reaches EXECUTION GEOMETRY or RISK is a defect.

---

## 11. Lifecycle and naming semantics

**Lifecycle.** Never reason about a state or value from its name alone. Trace
`CREATED → TRANSFORMED → CLASSIFIED → CONSUMED → REPLACED → EXPIRED → RESOLVED`. For state
machines: legal transitions, reset transitions, implicit transitions, shadow states,
expiration, rollback, terminal states, event ordering, timestamp ordering, causal ordering.

Keep these five distinct — they are routinely conflated:
**STATE TRANSITION** · **RESET** · **EVENT** · **OBSERVATION** · **DERIVED LABEL**.
A graph edge, a log event, and the runtime mutation are three different objects. F-068 is the
worked precedent: a `[DEADLOCK FIX]` fall-through meant a *reset* path delivered a shadow into
the same candle's TTL countdown, so a configured TTL of N yielded N−1 usable bars.

**Naming.** Names are **evidence, not authority**. When name and behavior disagree: identify
what the implementation computes · what the name claims · callers · consumers · contracts · then
whether the name is correct, historical, misleading, compatibility-preserved, a split identity,
or genuinely wrong. **Do not rename anything during review.** A misleading name is not
automatically a production bug (F-046: three apparent definitions of `body_ratio` were one
canonical definition plus one dead outlier with zero call sites).

---

## 12. Configuration semantics

Trace every relevant value: `DECLARATION → LOAD → NORMALIZATION → RUNTIME OBJECT → CONSUMER →
EFFECT`. Determine active version, source section, defaults, overrides, fallback, merge,
normalization, canonicalization, downstream consumers.

Two config keys with similar names need not share a semantic owner. A configuration discrepancy
is a defect **only** where the architecture establishes the values should be identical.

**Presence is not governance.** A key that is declared and strictly read but whose value never
reaches behavior is a *config illusion* (F-056: `partial_tp_fraction` was strict-read then
discarded against a hardcoded blend at three sites). Follow the value to the behavior, not to
the read.

---

## 13. Test semantics

Tests are **evidence of contracts**, not proof the contract is correct. When a test conflicts
with domain semantics, identify the test's intended contract, the domain meaning, and
repository ownership; then classify the test as correct, stale, over-constrained,
under-specified, characterization-only, or encoding an accidental implementation detail.

**Never** modify a test merely to make the current implementation green.
**Never** delete an xfail because it is inconvenient, and never invert one.
**Never** convert an unresolved semantic question into a passing test without resolving the
underlying meaning. An xfail that represents an unresolved semantic decision is **kept**.

---

## 14. The adversarial method

When a suspected defect is reported, reproduce the claim independently. Do **not** begin by
agreeing or disagreeing.

1. **Reproduce** — the exact configuration, code path, input, timestamp, state, consumer, test.
2. **Trace** — upstream and downstream.
3. **Identify the semantic owner** (§7).
4. **Establish domain meaning** (§6) — outside the implementation.
5. **Compare** — CURRENT implementation vs domain semantics vs architectural contract (§5).
6. **Classify** (§15).
7. **Assess risk** — production, research, data contamination, execution, replay, governance.
8. **Recommend** the smallest semantically correct action.
9. **Authorization gate** — if the repository does not establish the intended behavior, stop at
   the recommendation (§16).

### 14.1 External claims are hypotheses (non-optional)

A claim that "X is a bug" arriving from another model, an audit report, a generated document,
or a previous analysis is a **hypothesis**, never evidence. Reproduce it against source before
repeating it. Ask: what domain principle supports it? what repository contract? what consumer
depends on it? what alternative interpretation exists? what breaks if it is wrong — and if it is
right?

Two worked precedents where an external trace was source-verified and found **wrong**:

- **F-067** — a received bug-trace called the double `update_emas` call `EMA(EMA(close))` making
  momentum "overly sensitive." Source-verified **backwards**: double application gives effective
  α = 2α − α², which *compresses* the trend spread and makes approval harder.
- **F-068** — a bug-trace claimed the off-by-one was "documented in the code with the comment
  'same bar burns 1'." That comment **did not exist in source**; it existed only in a prior
  session log. The claim was `CORRECTED`, and the comment was then added for real.

This is CLAUDE.md §13.8 applied to review: other models *propose*; the reviewer verifies.

---

## 15. Required review output

For every unresolved semantic question, produce exactly this structure:

```text
# [QUESTION]
## RECOMMENDATION            KEEP CURRENT ARCHITECTURE | CHANGE REQUIRED | DOCUMENTATION ONLY
                             | TEST CONTRACT ONLY | INVESTIGATE FURTHER | USER AUTHORIZATION REQUIRED
## CONFIDENCE                HIGH | MEDIUM | LOW — and why
## DOMAIN REASONING          plain language first; no implementation terms until the concept is clear
## CURRENT BEHAVIOR          files, symbols, line ranges, active config, consumers, tests, runtime path
## INTENDED SEMANTICS        universal domain / repository-specific / strategy policy, separated
## CODEBASE EVIDENCE         concrete, ranked by §3.4 band
## SEMANTIC OWNERSHIP        the §7 table when multiple layers are involved
## ALTERNATIVE INTERPRETATION  the strongest reasonable alternative — never a strawman — plus the
                             evidence that would make it correct
## FAILURE / CONTAMINATION RISK   what goes wrong if the behavior is misunderstood or bypassed (§10)
## WHAT SHOULD BE TESTED     semantic contracts, not implementation details
## WHAT SHOULD NOT YET BE CHANGED   explicit list: code, config, tests, contracts, xfails
## USER AUTHORIZATION REQUIRED     the decision, as a small number of plain-language choices
```

Do not cite a file because its name sounds relevant. Repository nouns, joins, symbols, and
evidence ids in **CODEBASE EVIDENCE** are subject to §6.7 grounding — if
`query_semantic_os.py --ground` does not return `GROUNDED`, state the status and do not
introduce the token.

---

## 16. Final decision discipline

Every review closes with **exactly one**:

`CONFIRMED DEFECT` · `INTENTIONAL SEMANTIC SEPARATION` · `STALE / LEGACY ARTIFACT` ·
`COMPATIBILITY ARTIFACT` · `DEFENSE-IN-DEPTH OPPORTUNITY` · `TEST / CONTRACT GAP` ·
`DOCUMENTATION GAP` · `DORMANT BUT VALID` · `INSUFFICIENT EVIDENCE` ·
`USER AUTHORIZATION REQUIRED`.

**Do not use the word "bug" unless you can name the violated semantic contract.**

### When authorization is required

The user is not expected to decide semantics that standard domain knowledge or repository
evidence can establish. The user **must** authorize changes to: trading session policy · what a
state means · execution eligibility · risk semantics · the meaning of a configuration field ·
validation ownership · a lifecycle transition · a canonical vocabulary · removal of a
compatibility token · converting an xfail into a passing contract · a production invariant.

Present a small number of understandable choices — for example: **A.** preserve the current
semantic separation · **B.** unify the two concepts · **C.** introduce a new explicit policy.
Do not require implementation knowledge to choose. Then **stop at the recommendation.**

---

## 17. No silent remediation

During review, do **not**: edit production code · edit active configuration · modify or delete
production tests · delete or invert xfails · rename modules · change contracts · change the
ontology · change session windows · change risk rules · change execution rules · or "fix" a
semantic issue because it looks obviously wrong.

Review is for understanding and recommendation. **Implementation is a separate authorized
turn**, and once authorized it runs through `REPOSITORY_CONSTRUCTION_PROTOCOL.md`, not directly
from the review.

Prefer preserving explicit architectural boundaries over unifying concepts for aesthetic
consistency. Do not create duplicate validation, vocabularies, ownership, calculations, state
machines, session calendars, or semantic registries unless the additional layer has an explicit
contract and safety purpose. "Defense in depth" is valid only when its ownership and PASS
semantics are clear.

---

## 18. High-risk trading surfaces

Treat these as high-risk: OHLC geometry · timestamp basis · timezone / broker clock · session
windows · timeframe aggregation · ATR units · price units vs normalized units · direction ·
entry price · stop-loss geometry · take-profit geometry · reward:risk · intrabar vs close-only
exits · lookahead · state transition ordering · reset ordering · causal feature construction ·
future data leakage · execution eligibility · capital and risk gates.

Each of these has already produced a real finding here:

| Surface | Finding |
|---|---|
| Broker clock / session basis | F-066 — MT5 server time labeled UTC; 53.36% of XAUUSD bars mis-labeled |
| ATR units (price vs relative) | F-072 — canonical ATR is close-relative but SL/TP geometry required price units |
| Normalization basis | F-061 / F-064 — `legacy ≡ corrected × close`; four consumers saturated on crypto |
| Lookahead / PIT | F-051 — centered-swing binding leaks future bars into 10 of 38 canonical dims |
| Exit model | F-025 — close-only vs intrabar changes the sign of the conclusion |
| Reset ordering | F-068 — reset fall-through consumed one bar of a configured TTL |

**A mistake in these areas produces a system that is internally consistent while being
economically or causally wrong.** Semantic consistency alone is therefore not sufficient. Always
ask: *does this behavior represent the market concept it claims to represent?*

---

## 19. Enforcement

| Mechanism | Path | Enforces |
|---|---|---|
| Structure floor | `tests/governance/test_semantic_review_protocol.py` | this charter's required sections, the 10 classifications, the required output headings, the §3.3 reconciliation clause, and the CLAUDE.md §6.8 thin rule |
| Green floor | `scripts/maintenance/check_governance_invariants.py` | `docs/governance/` and `tests/governance/` are governed prefixes — a change here runs the curated floor |
| Grounding | `scripts/governance/query_semantic_os.py --ground` · `tests/test_semantic_grounding.py` | CODEBASE EVIDENCE tokens (§15) |
| Session log | `tests/test_session_log.py` | the §6 mandate every review turn closes with |

**Honest residuals (disclosed, not hidden):**

1. The floor is a **presence/structure** check, like `test_documentation_drift_protocol.py`. It
   cannot detect a review that follows the headings while reasoning badly.
2. Nothing mechanically prevents a session from performing remediation *without* first
   declaring a review. §17 binds a turn that has entered review, not every turn.
3. The §3.4 evidence bands are applied by judgment; there is no machine grader.
4. The §7 ownership tables for non-model concepts are built per-review and are not yet
   accumulated into a durable registry. If that recurs, the correct move is to extend the
   existing ownership artifacts, not to start a parallel one (§17).

---

## Authority

This protocol grants **no new authority**. It never bypasses the §6 SESSION LOG,
write-authority / path-guard, the `y/N` confirm, the `APPROVE` promotion gate, or user approval
for irreversible or outward-facing actions. It changes no §4.0 precedence, adds no rung to the
§6.5 Authority Ladder, and does not alter the ontology's meaning-authority under §6.6 or MIAR §0.

A completed review earns *documentation and recommendation* standing only. Production authority
is still earned solely by demonstrated G001 improvement (§6.5) — a correct semantic analysis is
not a licence to change behavior.


========================================================================
# SOURCE: docs/governance/MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md
# ROLE: identity_first_refinement_ladder_unknown_nodes
========================================================================

# Canonical Market Ontology Evolution Contract

> **Adopted 2026-07-25** (user directive). The long-form of CLAUDE.md §6.6. The machine-readable
> authority lives in `configs/formulas/market_ontology.yaml` (`spec_schema.semantic_registry`);
> this doc is the human-language charter. Enforced by `tests/test_semantic_registry.py` via
> `features.registry.validate_semantic_registry`.

## Purpose

The market ontology is the **permanent semantic authority** of the repository. It defines every
market concept — feature, formula, derived mathematics, state, transition, pattern, regime,
context, structure, zone, geometry, liquidity/volatility/execution/risk behaviour, model
input/output, validation rule, invariant. Every implementation, model, config, report, and
research artifact derives its **meaning** from the ontology. No market behaviour may exist outside
it: discovered-but-undefined behaviour becomes an explicit `UNKNOWN_*` node, never a TODO or a
buried comment.

## Authority (user decision: LITERAL SUPERSESSION)

The ontology is authority **#1**, first-mover. For **meaning/semantics**, runtime, models, and the
historical §4.0 / §6.5 precedence derive from it: a semantic change originates in the ontology and
everything else synchronizes.

### Two mechanical constraints (physical — keep supremacy coherent, NOT doctrine-overridable)

1. **Frozen runtime keys stay flat + additive.** `primitives` / `feature_compositions` /
   `derived_metrics` are read by `crt_engine_v2` at import (`fm_resolve.bind_phase2_crt_callables`).
   The ontology may change first, but frozen-key edits are additive-only or the engine hard-crashes
   on import. New node types live in the **non-frozen** sibling sections
   (`spec_schema.semantic_registry.sections`), invisible to `_ITERATED_SECTIONS`, the runtime
   binding, and `validate_registry`.
2. **Behaviour cascades are governed.** An ontology change that would alter **production behaviour**
   still cascades through parity-proof + the promotion gate before it reaches runtime. "Ontology
   first" governs the **origin and requirement** of a change — it must originate in and be recorded
   by the ontology — not an automatic unvalidated runtime mutation (this preserves the
   anti-split-brain guarantee of §4.0 and the earned-authority ladder of §6.5).

## Node schema

Every node in a semantic section carries the full `semantic_node_required_fields` set (id,
canonical_name, aliases, semantic_category, knowledge_status, description, observed_behaviour,
mathematical_definition, units, formula, dependencies, required_inputs, produced_outputs,
producers, consumers, transitions, validation_rules, confidence, evidence, origin, status, version,
owner, traceability, notes). A field's **value** may be `UNKNOWN` / `[]` until discovered — the key
must be **present**. **Never fabricate** a value the evidence does not support. `id` is unique
across the whole ontology (FM-0NN frozen ids and SEM-/UNK- semantic ids share one namespace).

## Refinement ladder (knowledge axis, distinct from `lifecycle`)

`UNKNOWN → OBSERVED → CHARACTERIZED → MATHEMATICALLY_DEFINED → FORMULA_DERIVED → VALIDATED →
PRODUCTION_CERTIFIED → STABLE`

A node **refines in place** up this ladder; its identity never changes and **no duplicate node** is
created. `UNKNOWN` is a valid, permanent citizen — it participates in dependency graphs, validation,
and traceability until resolved. `PRODUCTION_CERTIFIED` is earned only by measured G001 (§6.5) —
evidence alone never grants production authority.

## Epistemic discipline — separate the levels (mandatory for UNKNOWN)

The single most important rule: **a node must never mix measured facts, validated knowledge, and
hypotheses into one statement.** Hypotheses harden into "facts" by repetition otherwise. A
research-stage node carries an `epistemic:` block keeping the levels distinct:

| Component                  | Purpose                                    | May change?             |
| -------------------------- | ------------------------------------------ | ----------------------- |
| `observation`†             | measured facts                             | rarely                  |
| `known_invariants`         | facts already validated                    | only with new evidence  |
| `unknown_mechanism`        | the single unanswered question             | yes                     |
| `candidate_hypotheses`     | explicitly-untested guesses (NOT truth)    | yes                     |
| `resolution_metric`        | how the question will be answered          | can evolve if improved  |
| `falsification_conditions` | what evidence would DISPROVE the hypotheses | can evolve              |

† `observation` is the node's existing `observed_behaviour`; `evidence` is the node's `evidence`
field. The `epistemic` block holds the remaining five keys.

The block is **mandatory when `knowledge_status == UNKNOWN`** and **encouraged for OBSERVED /
CHARACTERIZED**; whenever present (any status) it is validated. `falsification_conditions` is the
newest discipline — good research documents not only how a theory is supported but how it could be
proven wrong. State invariants factually: prefer *"current evidence indicates X is not explained by
the previously identified defect Y"* over *"X is not an artifact"* — ruling out one known defect
does not rule out an unrelated, not-yet-identified one.

## Automatic Semantic Discovery ritual (every investigation)

While investigating, actively search for: undefined behaviours, duplicate/equivalent semantics,
hidden transformations, implicit assumptions, missing formulas/transitions/consumers/producers/
invariants/lifecycle rules. **Each discovery becomes a canonical ontology node** the same turn —
seeded at the honest `knowledge_status` with `evidence` + `origin` filled, and a contamination
caveat in `notes` when the source is a single run / shadow path / possibly-contaminated upstream.
Do not force a new behaviour into an existing node because it "looks similar"; if evidence is
insufficient, create a new node (or an `UNKNOWN_*`) and refine it as evidence accumulates.

## Cross-layer synchronization order

`ontology → formula registry → feature registry → feature schema → feature pipeline → models →
configuration → validation → documentation`. The ontology changes first; behaviour-affecting
cascades remain governed (constraint 2).

## Enforcement

`features.registry.validate_semantic_registry(ontology)` (sibling to `validate_registry`, reads its
vocabularies from `spec_schema.semantic_registry` — ontology-first) checks: required fields present;
id present + globally unique; version int; category ∈ vocabulary; knowledge_status ∈ ladder;
evidence + origin non-empty above UNKNOWN; `canonical_unknowns` nodes stay UNKNOWN/OBSERVED; list
fields `[]` not null. Floor: `tests/test_semantic_registry.py`. The frozen path (`validate_registry`)
is unaffected — additive by construction.

## Seed nodes (2026-07-25, this session)

`SEM-001 EXPANSION_DWELL_DIVERGENCE` (OBSERVED), `SEM-002 HTF_PROTECTION` (CHARACTERIZED),
`SEM-003 STATE_OCCUPANCY_VS_DWELL_SPAN` (MATHEMATICALLY_DEFINED, invariant), `UNK-001` (the UNKNOWN
root mechanism of the resolver EXPANSION under-dwell). `FM-002 candle_range` (aliases `wick_size`,
`resolved_renamed_v4`) is the in-tree STABLE ladder exemplar. All grant no production authority.

## Long-term objective

The ontology becomes a complete mathematical + semantic **digital twin** of the trading system —
every behaviour, feature, state, transition, execution rule, model, report, and validation
representable as ontology objects with full mathematical identity, semantic lineage, implementation
traceability, and runtime verification. No part of the system may rely on undocumented semantics or
implicit assumptions. (Guardrail: build incrementally from evidence — §6.5 "no premature
framework"; a node earns complexity only when a real behaviour demands it.)


========================================================================
# SOURCE: docs/governance/EPISTEMIC_INTEGRITY.md
# ROLE: e001_preregistration_ritual_and_authority_ladder
========================================================================

# Program E-001 — Epistemic Integrity Sweep & Invariantization

> **Created:** 2026-06-17
> **Status:** ACTIVE
> **Mandate:** Every conclusion must be traceable to the evidence that supports it.
> No layer may possess greater certainty than the layer beneath it.

---

## 1. Why this exists

The F-030 incident revealed a systematic vulnerability:

```
Evidence:
  all spine cells = INSUFFICIENT (n < 30)

     ↓ hidden inference

  negative sign counts in rollup

     ↓ presentation

  REGIME_HARMFUL
```

Nothing crashed. Tests passed. Yet the semantic meaning became stronger than the evidence.

That is **epistemic corruption** — worse than a bug.

A manual correction followed (regime_conditioning v1.1→v1.2), but **no invariant guaranteed recurrence prevention**. This program formalizes the missing invariants.

---

## 2. The Invariant

**No layer may claim greater certainty than its supporting evidence — unless an explicit,
documented precedence policy exists.**

(Prose form generalized to an evidence *graph* — relations are often a DAG, not a tree.
"Layer beneath it" was the original tree-shaped phrasing; this is the durable generalization.)

Formally, in the default (tree) case:

```
certainty(parent) ≤ min(certainty(children))
```

Equivalently: a verdict cannot be stronger than the weakest cell that supports it.

**The program's objective, stated permanently:**

> **E-001 creates shorter correction loops, not total prevention.**

No governance system eliminates error. E-001 governs the *speed of correction* (error lifetime),
not the *frequency of mistakes*. The F-030→F-031 chain (governance caught an overclaim → the
governance *tests* later overclaimed → the tests audited themselves → behavioral enforcement was
added) is the loop working as intended, not a failure.

### Sanctioned precedence rules

The invariant's "unless" clause is real, and the difference is load-bearing:

- **Undocumented** precedence looks like inflation (an E-001E bug).
- **Documented** precedence is *policy*.

First sanctioned precedence rule: the **scope-level** rollup in
[`src/research/regime_conditioning.py`](../../src/research/regime_conditioning.py) (`scope_verdict`)
lets an *informative* consumer dominate an *underpowered* (INSUFFICIENT) consumer in the same
scope — so a real signal from one consumer is not masked by another's noise. This is intentional
cross-consumer precedence, not parent-over-children inflation, and is therefore exempt from the
E-001E invariant. The per-consumer rollup (the F-030 site) is **not** exempt and is enforced
behaviorally (see §6).

---

## 3. Failure Classes

### E-001A — Overclaim
Conclusion stronger than evidence supports.

Example:
```
INSUFFICIENT → HARMFUL
```
Pattern: `if sign < 0: verdict = REGIME_HARMFUL` missing `if n < minimum: verdict = INSUFFICIENT`

---

### E-001B — Statistical ≠ Economic
p-value significance interpreted as economic edge.

Example:
```
if p < 0.05:
    useful = True
```
without `expectancy > 0`. Authority-Ladder violation: Level 1 (statistical) masquerading as Level 2 (economic).

---

### E-001C — Prose Registration
Finding registered from narrative instead of artifact.

Example: a finding that cites a conversation summary instead of a file:line with reproducibility information.

---

### E-001D — Silent Default
Unmeasured fallback masquerading as truth.

Example:
```
value = x.get("threshold", 0.5)
```
where `0.5` was invented, not measured.

---

### E-001E — Rollup Inflation
Aggregate verdict exceeds the support of its components.

Example:
```
children:
  INSUFFICIENT
  INSUFFICIENT
  INSUFFICIENT

parent:
  HARMFUL
```

Parent confidence cannot exceed child confidence.

---

### E-001F — Decorative Wiring
Configuration or metadata presented as active while ignored.

Example: a config key documented as controlling X, but the code path for X has no consumer of that key (H-Dead / H-Shadow pattern from `KNOWN_ILLUSIONS.md`).

---

## 4. Mandatory Phrase

Whenever any E-001 failure class is discovered:

> **"Caught me overclaiming; I owe you a correction."**

A correction that occurs **before registration** is evidence the governance system succeeded — not a failure.

---

## 5. The Pre-Registration Ritual

Before every finding registration, ask:

1. **What artifact supports this?** (file:line required)
2. **Could INSUFFICIENT explain the observation?**
3. **Am I upgrading sign noise into meaning?**
4. **Is this statistical or economic?** (Authority-Ladder check)
5. **Is the parent stronger than the children?**
6. **Would I phrase this differently after seeing raw counts?**

If any answer exposes uncertainty, confidence must be downgraded or status set to HYPOTHESIS.

---

## 6. CI-Enforced Invariants (Track B)

The following are checked by `tests/governance/test_epistemic_invariants.py`. Two distinct
strengths — and the table says which honestly (per R2: a test that cannot fail is **not**
enforcement and must not be presented as such):

| Invariant | Rule | Strength |
|-----------|------|----------|
| E-001A | An all-underpowered (all-INSUFFICIENT) population must roll up to INSUFFICIENT, never HARMFUL | **ENFORCED (behavioral)** — drives the pure `_consumer_verdict` rollup with synthetic inputs and asserts the output; a logically-broken guard goes red (proven by the red→green test) |
| E-001E | A consumer verdict may not be stronger than its weakest child cell | **ENFORCED (behavioral)** — same helper; `test_red_green_guard_proof` permanently encodes the guard's load-bearing difference |
| Evidence-link | Every confident (Likely/Certain) finding in `docs/current-findings.md` resolves to a real artifact (file exists; line exists when cited) | **ENFORCED** — parses the live findings file and fails on unresolvable evidence |
| E-001B | Statistical ≠ Economic: a p-value line should carry economic context | **ADVISORY (does not fail)** — surfaces candidates via skip for human review; cannot be mechanized without semantics (future E-002). Honestly *not* an assertion |
| Possible-evidence | Possible-confidence findings get a lower evidence bar | **ADVISORY (does not fail)** |

The **behavioral** rows mean the claim *"the F-030 bug pattern is now a test failure"* is literal:
removing the `all_insufficient` guard turns the suite red (demonstrated, then restored). The
**advisory** rows are documentation-as-tooling and are labeled as such — they do not enforce.

These tests must pass for any PR that touches affected files.

---

## 7. Relationship to Existing Governance

| Existing | E-001 Relationship |
|----------|-------------------|
| M4 Qualification Gate (7-gate pipeline) | Correct — the F-030 overclaim was NOT in the qualification gate; it was in the *presentation/rollup* layer. E-001 complements, does not replace. |
| `KNOWN_ILLUSIONS.md` | Covers E-001F (decorative wiring). E-001 extends to the *epistemic* layer (E-001A–E). |
| `docs/current-findings.md` schema | Confidence / Evidence / Reversal fields provide structure. E-001 adds the pre-registration ritual and CI assertions. |
| Pre-registration discipline (Programs 1–4) | Culturally exists but was not formalized. E-001 enshrines it. |
| `CONVENTIONS.md`, `TRIGGER_VOCABULARY.md` | E-001's mandatory phrase is a new trigger: "Caught me overclaiming; I owe you a correction." |

---

## 8. Scope Boundaries

E-001 does **not** modify:

- CRT spine (`src/config_layer/crt_engine_v2.py`)
- M4 Qualification gate (`src/research/qualification.py`)
- Production configs (`configs/production/`)

The bug lives in the **presentation/aggregation** layer — not in the underlying statistics.

---

## 9. Known Violations Discovered

- **F-030 rollup** (regime_conditioning v1.1): spine cells all INSUFFICIENT → rollup printed REGIME_HARMFUL. Corrected in v1.2 (`all_insufficient` guard). Root cause: missing E-001E invariant. Now enforced behaviorally (§6).
- **E-001 self-audit (2026-06-18):** the *first* generation of E-001's own invariant tests overclaimed — E-001A/E-001E were substring-grep (not behavioral), and E-001B + the possible-evidence test could never fail yet were tabled as "Test asserts." Per the program's own classification this is E-001A (overclaim) + E-001F (decorative wiring). Corrected: the per-consumer rollup was extracted to the pure `_consumer_verdict` helper and the A/E tests rewritten to be behavioral with a permanent red→green proof; the advisory tests were relabeled honestly. **This is the recursive loop the program is designed to produce — E-001 became subject to E-001.** Memorialized as F-031.

---

## 10. Program Status

**The program is OPEN, not "finished."** The most likely failure mode is declaring E-001 complete
and never re-subjecting it to its own standard — the self-audit in §9 is the counter-practice.

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 1 | `EPISTEMIC_INTEGRITY.md` (this file) | ✅ DONE |
| 2a | Expand `CLAUDE.md` §6 with Epistemic Integrity ritual | ✅ DONE |
| 2b | Sweep `docs/current-findings.md` | ✅ DONE |
| 2c | Sweep `src/research/` harnesses | ✅ DONE |
| 2d | Re-verify `KNOWN_ILLUSIONS.md` | ✅ DONE |
| 3 | `tests/governance/test_epistemic_invariants.py` | ✅ DONE |
| 3b | Fix violations found (incl. the E-001 self-audit, §9) | ✅ DONE |
| 4 | Register F-031 | ✅ DONE |
| — | Behavioral-invariantization remediation (R1–R5, 2026-06-18) | ✅ DONE; program remains OPEN/recursive |

========================================================================
# SOURCE: multi_llm/research_lane/RESEARCH_ROLES.md
# ROLE: your_role_and_the_no_voting_rule
========================================================================

# Research Lane — Role HOW Map

> Dual-lane default (AMB-01 B). Does **not** replace `multi_llm/roles/ROLE_*.md` for Implementation Lane.

| Role | Default model | Lane | Writes | Never |
|---|---|---|---|---|
| **Principal** | You | Both | DECISION (capital, phase grants) | Delegate capital to LLM |
| **Architect** | ChatGPT | Research | PROPOSAL, DECISION (freeze/branch drafts) | Sole-sign PL-5; write prod code |
| **Hypothesis diversity** | Grok | Research | PROPOSAL (counters, new families) | Approve own H; execute |
| **Technical critic** | DeepSeek | Research | CRITIQUE | Execute unfrozen RUN |
| **Executor** | Claude | Both | EXECUTION_EVIDENCE; code/tests | Raise PL alone; invent metrics |
| **Impl planner** | DeepSeek | Implementation | plan handoffs | Own ERP DECISION |
| **Impl navigator** | Gemini | Implementation | gaps/next | Own ERP DECISION |
| **Impl interpreter** | ChatGPT | Implementation | explain/expand | Execute code |

## Handoff rule

```text
Same problem → different roles → different package kinds
Never: four models answer same prompt and vote
```

## Speech rule

| Role output | Max wealth language |
|---|---|
| Any PROPOSAL/CRITIQUE | PL-0 wording unless package binds higher *after* DECISION |
| DECISION upgrading PL | Must cite EXECUTION_EVIDENCE package_ids |


========================================================================
# SOURCE: multi_llm/research_lane/package_schema.json
# ROLE: package_contract_your_output_must_validate
========================================================================

{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "tradelatest.multi_llm.research_lane.package.v1",
  "title": "ResearchLanePackage",
  "type": "object",
  "required": [
    "package_id",
    "kind",
    "cycle_id",
    "created_at",
    "author_role",
    "summary",
    "status"
  ],
  "properties": {
    "schema_version": { "type": "string", "const": "1.0" },
    "package_id": { "type": "string", "minLength": 3 },
    "kind": {
      "type": "string",
      "enum": ["PROPOSAL", "CRITIQUE", "EXECUTION_EVIDENCE", "DECISION"]
    },
    "cycle_id": { "type": "string", "pattern": "^RC-[0-9]{3,}$" },
    "created_at": { "type": "string" },
    "author_role": {
      "type": "string",
      "enum": [
        "principal",
        "architect",
        "hypothesis_diversity",
        "technical_critic",
        "executor",
        "system"
      ]
    },
    "author_model": {
      "type": "string",
      "description": "e.g. grok, chatgpt, deepseek, claude, human"
    },
    "claim_type": {
      "type": "string",
      "enum": ["H_tool", "H_market", "process", "none"]
    },
    "summary": { "type": "string", "minLength": 1 },
    "binds": {
      "type": "object",
      "properties": {
        "entrypoint": { "type": "string" },
        "lens": { "type": "string" },
        "active_version": { "type": "string" },
        "instruments": { "type": "array", "items": { "type": "string" } },
        "phase": { "type": "string" },
        "promise_rung_max_claim": {
          "type": "string",
          "enum": ["PL-0", "PL-1", "PL-2", "PL-3", "PL-4", "PL-5", "PL-5+"]
        }
      }
    },
    "falsifier": { "type": "string" },
    "h1_h2_h3_risks": {
      "type": "array",
      "items": { "type": "string" }
    },
    "artifact_paths": {
      "type": "array",
      "items": { "type": "string" }
    },
    "related_package_ids": {
      "type": "array",
      "items": { "type": "string" }
    },
    "status": {
      "type": "string",
      "enum": ["PROPOSED", "ACCEPTED", "REJECTED", "SUPERSEDED", "BLOCKED"]
    },
    "notes": { "type": "string" }
  },
  "additionalProperties": true
}
