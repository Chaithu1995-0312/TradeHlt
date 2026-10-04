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
