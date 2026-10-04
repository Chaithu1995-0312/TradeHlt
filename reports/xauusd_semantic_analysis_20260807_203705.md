# XAUUSD M15 — Semantic Market Reconstruction

**Generated:** 2026-08-07 20:37 UTC
**Numerical authority:** `data/XAUUSD_M15_20260807_203705.xlsx` (sheet `candles`, 1,195 rows)
**Visual context only:** TradingView XAUUSD 15m screenshot (OANDA), live at 2026-08-07 20:20 UTC

---

> ## ⚠ CORRECTED 2026-08-08 — Engine-side numbers in this report used the WRONG HTF window
>
> The ad hoc driver that produced every **engine-side** number below (`97 transitions`, `state
> occupancy RANGE 600 / SWEEP 414 / DISPLACEMENT 58 / EXPANSION 27`, `RETEST=0`, `EXECUTION=0`,
> and the "**the ladder never completes**" narrative in State Transition Report / Final
> Assessment) called `getattr(crt_cfg, "htf_candles_per_range", 96)` against `CRTConfig`. That
> key does **not exist** on `CRTConfig` — it lives under the config's top-level `backtest`
> section (`backtest.htf_candles_per_range = 4` on the active `v2_multi_2026_04`) — so the
> `getattr` silently fell back to my own hardcoded default of **96**, a **24× oversized** HTF
> window. This was caught while building a separate CRT semantic reconstruction and verified
> against `src/runtime/backtest_v2.py:229` (`int(cfg["htf_candles_per_range"])`, strict, no
> silent default) and the raw config JSON.
>
> **Re-run with the corrected value (`htf_candles_per_range=4`) on the identical Excel corpus:**
> 166 transitions (not 97); state occupancy `RANGE 764 / SWEEP 147 / DISPLACEMENT 11 /
> SHADOW_PENDING 5 / EXPANSION 262 / RETEST 2`; **RETEST fires twice** (`2026-07-22 19:00` and
> `2026-07-28 05:30`, both SHORT/LONG expansions reaching RETEST then dying to `FILTER_REJECTED`
> one candle later — a legitimate soft-confirmation zone/session reject per
> `crt_engine_v2.py:3079-3130`, not a defect). **EXECUTION never fires in this window either
> way** — that conclusion survives — but "**RETEST is unreachable in this window**" is **false**;
> it was an artifact of my own default-value bug, not a property of the market data or the
> engine.
>
> The original observation below stands as **a record of what that flawed run produced** (§6.2
> rule 4 — history is preserved, not deleted) but its interpretation is **superseded** by this
> correction. The canonical reproduction used elsewhere this session
> (`scripts/analysis/crt_xauusd_runtime_trace.py`, which reads `backtest.htf_candles_per_range`
> strictly with no fallback) was never affected by this bug.

---

## Summary

| Field | Value |
| --- | --- |
| Symbol | XAUUSD |
| Timeframe | M15 |
| Excel rows used | **1,195** (entire `candles` sheet; no subsetting) |
| Excel range (broker labels) | `2026-07-22 01:00` → `2026-08-07 23:30` |
| Excel range (true UTC) | `2026-07-21 22:00` → `2026-08-07 20:30` |
| Data source | Raw Trading Ltd — server `ICMarketsSC-Demo`, login 52935582 (demo) |
| Screenshot source | OANDA spot gold (a **different feed** from the Excel) |
| Synchronization status | **RECONCILED** — see below |

### Synchronization findings (reported, not assumed)

**1. Clock basis — measured, not inferred.** The Excel's timestamps are **broker-server local, labeled as if UTC**. Measured directly against the terminal: server label `2026-08-07 23:36:06` at true UTC `2026-08-07 20:36:06` → offset **exactly +3.00 h**. Corroborated independently by the session structure: the daily break runs `23:45 → 01:00` broker (92 bars/day), which places the session boundary at 17:00 New York — the CME gold maintenance break — only under a +3 h offset. This confirms repo finding **F-066** on this corpus.

> **All timestamps in this report are quoted verbatim as they appear in the Excel (broker-local).** Subtract 3 h for true UTC. Session attributions below are computed explicitly from that offset, never assumed from the label.

**2. Initial coverage gap — closed by re-fetch, not interpolation.** The first export ended `2026-08-06 23:45`, ~23.5 h short of the screenshot, missing the chart's most prominent move. Data was **re-fetched** to close it; no candle was synthesized or interpolated.

**3. A fetch-boundary defect was found and worked around.** `scripts/data/fetch_candles_mt5.py --end 2026-08-08` returned bars only through label `20:30` while the server was already serving `23:30` — the `--end` bound is applied as a UTC instant against server-labeled bars, silently truncating exactly the 3 h offset from the tail. Worked around by passing `--end 2026-08-09`. Also observed: the first fetch after terminal idle returned a partial window (54 bars) and required a re-run. **Neither is fixed in code** — both are live traps for anyone using this fetcher.

**4. Price reconciliation across feeds.** Last Excel close `4340.05` vs the screenshot's live `4339.59` — a **0.46** difference, consistent with OANDA-spot vs IC-Markets-CFD pricing. The two feeds agree on structure; the Excel governs every number below.

**5. Coverage.** The Excel now spans the full screenshot-visible window. **Nothing visible on the chart is left without numerical backing**, and nothing is claimed beyond `2026-08-07 23:30`.

---

## Semantic Timeline

Two independent readings were produced and are reported side by side:

- **Engine** — the repo's canonical `CRTEngine` state machine (`src/config_layer/crt_engine_v2.py`) under the ACTIVE config `v2_multi_2026_04`, driven directly from the Excel.
- **Structural** — an independent OHLC read (causal pivots only; no centered windows, per F-051/F-029 lookahead contamination).

> **Loader note (material):** the repo's `CandleLoader` could **not** be used. `CandleLoader.__init__` → `guard_xauusd_csv_path()` rewrites *any* XAUUSD M15 request to a frozen Phase-1 corpus (different range, 47,275 rows). Using it would have silently analyzed a different file. The driver constructs `Candle` objects straight from the Excel, so the Excel-authority rule holds structurally, not by convention.

### Phase A — Balanced range (Jul 22 → Aug 4)

| | |
| --- | --- |
| Range high | **4166.06** (`2026-07-22 18:45`) |
| Range low | **3995.97** (`2026-07-29 17:00`) |
| Width | 170.09 (~4.1%) over 920 bars |
| Median ATR(14) | 5.85 – 9.86 per day |

Two-way rotation with no directional resolution. The structural read returns **21 BOS flips** in this stretch alternating UP/DOWN — the signature of a range, where each "break" is immediately reclaimed. Representative pair:

| Timestamp (broker) | O | H | L | C | Event |
| --- | --- | --- | --- | --- | --- |
| `2026-07-31 09:15` | — | — | — | 4085.03 | BOS_UP above 4083.31 |
| `2026-07-31 10:15` | — | — | — | 4072.69 | BOS_DOWN below 4072.83 — **reversed within 4 bars** |

**Interpretation:** the market was *building* the inventory it would later use, not trending. Confidence: **high** (920 bars, unambiguous).

### Phase B — The break (Aug 5, Wednesday)

| Timestamp (broker) | O | H | L | C | Vol | Role |
| --- | --- | --- | --- | --- | --- | --- |
| `2026-08-05 05:30` | 4103.59 | 4128.78 | 4101.54 | **4128.24** | 15,301 | Displacement, body 24.65 = **2.77× ATR** |
| `2026-08-05 09:00` | 4161.56 | 4174.36 | 4160.12 | **4173.27** | 8,609 | **First close above the 4166.06 range high** |

`05:30` broker = **02:30 UTC** (Asia session) — the impulse originated *outside* the liquid Western sessions, then confirmed the breakout at `09:00` broker = **06:00 UTC** (London open).

Aug 5 closed at 4246.73 from an open of 4077.72: **+168.99 in one session**, the regime pivot of the entire window. Confidence: **high**.

### Phase C — Trend continuation (Aug 6 → Aug 7)

Aug 6 extended to 4304.08 and consolidated (close 4240.38). Aug 7 resumed and produced the window's defining candle:

| Timestamp (broker) | O | H | L | C | Vol | Role |
| --- | --- | --- | --- | --- | --- | --- |
| `2026-08-07 15:30` | 4309.95 | 4370.81 | 4309.95 | **4367.12** | **32,161** | Body 57.17 = **4.56× ATR** — largest in window |
| `2026-08-07 15:45` | 4367.12 | 4371.78 | 4355.68 | 4361.38 | 19,557 | Window **high 4371.78**; first rejection |
| `2026-08-07 17:00` | 4348.23 | 4349.13 | 4327.50 | 4334.62 | — | Pullback confirmed |

**`15:30` broker = 12:30 UTC = 08:30 New York**, and **2026-08-07 is the first Friday of August** — precisely the US employment-report release slot. The candle's profile (open == low 4309.95, i.e. no downside wick, on 32,161 volume ≈ 2× the next-largest bar) is a textbook scheduled-release expansion.

> **Epistemic caveat:** this is a **time-slot and volume-profile alignment**, not a verified news event — no news feed was consulted. The mechanism (instantaneous one-directional expansion on anomalous volume at an exact scheduled minute) is strongly consistent with a data release, but the specific release is **inferred, not confirmed**. Confidence in the alignment: **high**; in the causal attribution: **moderate**.

---

## Structural Analysis

**Trend.** Two distinct regimes, not one. Range-bound Jul 22 → Aug 4 (170-point band, 21 alternating BOS), then a directional expansion Aug 5 → Aug 7 of **+262.33** net (4109.45 open → 4340.05 close), carrying price from 4065.40 to 4371.78.

**Swing hierarchy** (causal, K=4, confirmed 4 bars after the pivot): 85 confirmed swing highs, 84 swing lows. In Phase A these alternate at similar levels (balance). From Aug 5 they form a strict higher-high / higher-low staircase — the structural definition of trend.

**Liquidity.** 544 sweep events (a prior confirmed pivot exceeded intrabar, then closed back inside). The distribution is the story: dense and two-sided through Phase A, then increasingly **one-sided** in Phase C, where highs are taken and *held* rather than rejected. That distinction — taken-and-held vs taken-and-rejected — is what separates a continuation breakout from a liquidity grab.

**Major expansions** (body ≥ 1.2× ATR; 95 total). Top 3 by ATR ratio:

| Timestamp (broker) | Dir | Body | ATR | Ratio | Close |
| --- | --- | --- | --- | --- | --- |
| `2026-08-07 15:30` | UP | 57.17 | 12.54 | **4.56** | 4367.12 |
| `2026-07-29 21:00` | UP | 37.00 | 12.20 | 3.03 | 4081.13 |
| `2026-08-05 05:30` | UP | 24.65 | 8.91 | 2.77 | 4128.24 |

The two largest *outside* the release candle are both the Phase-B ignition and a Phase-A failed breakout — the same mechanism, different outcomes.

**Volatility.** ATR(14) min 3.12 / median 7.29 / max 22.30. Daily median ATR rises from ~5.9–6.9 (Aug 3–4, the tightest compression in the window) to ~9.0 (Aug 5–7). **The lowest-volatility days immediately precede the largest expansion** — a textbook compression → expansion sequence.

**Important zones.** `4166.06` (old range high → breakout pivot), `3995.97` (range floor, untested since), `4371.78` (window high, the active supply level), `4304.08` (Aug 6 high, reclaimed Aug 7 and now the nearest structural support).

**Failure points.** The `15:45`–`17:00` rejection from 4371.78 back to 4334.62 is the only material counter-move in Phase C. As of the last Excel bar (`23:30`, close 4340.05) price had stabilized above the reclaimed 4304.08 level — the pullback held.

---

## State Transition Report

**Engine result:** 1,195 bars → **97 transitions**, 106 non-`NONE` actions.

State occupancy (bars): `RANGE` 600 · `SWEEP` 414 · `DISPLACEMENT` 58 · `EXPANSION` 27.

| Transition | Count |
| --- | --- |
| RANGE → SWEEP | 34 |
| SWEEP → DISPLACEMENT | 22 |
| DISPLACEMENT → RANGE | 15 |
| SWEEP → RANGE | 12 |
| DISPLACEMENT → EXPANSION | **7** |
| EXPANSION → RANGE | **7** |

Actions: `SWEEP_DETECTED` 34 · `RESET` 33 · `DISPLACEMENT_CONFIRMED` 22 · `SWEEP_EXPIRED` 10 · `EXPANSION_CONFIRMED` 7.

### The ladder never completes

**`RETEST` = 0. `EXECUTION` = 0. `RESOLUTION` = 0. `SHADOW_PENDING` = 0. `EXPIRED` = 0.**

All 7 EXPANSIONs died the same way — reverting to RANGE on a `50% retrace hit`:

| Entered EXPANSION | Died | Retrace | Close at death |
| --- | --- | --- | --- |
| `2026-07-31 17:00` | `17:15` | 0.782 | 4038.85 |
| `2026-08-03 13:30` | `14:45` | 1.111 | 4062.54 |
| `2026-08-03 23:30` | `2026-08-04 03:00` | 1.610 | 4063.74 |
| `2026-08-04 05:30` | `06:30` | 0.631 | 4052.92 |
| `2026-08-05 02:00` | `02:15` | 1.018 | 4067.23 |
| `2026-08-07 03:45` | `04:00` | 1.018 | 4244.25 |
| `2026-08-07 15:45` | `17:00` | 0.568 | 4334.62 |

**Mechanism — source-verified, not inferred** (`crt_engine_v2.py:2395-2400`):

```python
disp    = state.displacement_candle
move    = abs(disp.close - disp.open)          # ONE candle's body
retrace = abs(price - disp.close) / move       # ABSOLUTE distance — direction-agnostic
if retrace >= self.config.retrace_reset_pct:   # 0.5 on the active config
    return True, f"50% retrace hit (retrace={retrace:.3f})"
```

Two properties make completion structurally very hard in a trending market:

1. **It is direction-agnostic.** `abs(price - disp.close)` fires whether price moves *against* the setup or *further in its favour*. A strong continuation resets the state machine exactly as a failure does.
2. **It is scaled to a single candle's body**, not to ATR or the range. Once one displacement candle prints, any subsequent move of half that body — in either direction — invalidates.

The retrace values make this concrete: **5 of 7 exceeded 1.0** (up to 1.610), meaning price had travelled *more than a full displacement body* away. On `2026-08-05 05:30` the engine confirmed a `SHORT` displacement on a candle that closed **+24.65 higher** (O 4103.59 → C 4128.24): the setup was labeled short because price swept the range **high** (4085.84), per CRT's reversal premise (`crt_engine_v2.py:897`). Price then continued up, and the reset fired at `08:30` with retrace 1.187.

**This is the central engine finding:** across the window the engine took **34 SHORT vs 29 LONG** setups while the market delivered a +262-point *up*-trend. Its sweep-of-high → expect-reversal premise was systematically wrong-footed by a market where high sweeps were **continuation breakouts**, not liquidity grabs.

### Where the two readings disagree

| | Engine | Structural |
| --- | --- | --- |
| `2026-08-07 15:30` (release candle) | `SWEEP → DISPLACEMENT`, direction **SHORT** | Largest **UP** displacement in window (4.56× ATR) |
| `2026-08-05 05:30` | `SWEEP → DISPLACEMENT`, direction **SHORT** | **UP** displacement, 2.77× ATR, breakout ignition |
| Aug 5–7 overall | 7 EXPANSIONs, all invalidated, 0 executions | Clean higher-high/higher-low trend, +262.33 |

The disagreement is **reported, not resolved by preference**. Both are computed from identical Excel rows; they differ because the engine encodes a mean-reversion premise while the structural read is premise-free. Per repo doctrine (§6.5 Authority Ladder) this is an **observation**, not authority — it grants no config change and no promotion.

---

## Final Assessment

**What the market was trying to do.** For two weeks (Jul 22 → Aug 4) gold did what a market does when it has no reason to move: it rotated inside a 170-point band, repeatedly probing both edges and reclaiming every break. The 21 alternating BOS flips are not 21 failed trends — they are one balanced auction. Volatility compressed into Aug 3–4 (daily median ATR ~5.99, the window's tightest).

**What changed.** On Aug 5 at `05:30` broker (02:30 UTC, Asia) a 2.77× ATR impulse broke the pattern, and by `09:00` broker (06:00 UTC, London open) price closed above the 4166.06 range high and never returned. Compression resolved into expansion — the classic sequence, with the low-volatility days sitting immediately before the largest move.

**Why it changed.** The Aug 5 break established direction; the Aug 7 `15:30` candle — 08:30 New York on the first Friday of the month, opening exactly on its low with no downside wick, on double the next-highest volume — supplied the catalyst that carried price to 4371.78. Structurally, once 4166.06 flipped from resistance to support, each subsequent high sweep was *held* rather than rejected, which is the mechanical definition of trend continuation.

**The phase it ended in.** As of the last Excel bar (`2026-08-07 23:30`, close 4340.05), price had rejected 4371.78, pulled back to 4334.62, and stabilized above the reclaimed 4304.08 — an intact uptrend in its first pullback, not a reversal. No claim is made beyond this bar.

### What OHLC alone could not have told us

1. **That the two regimes are one story.** The Excel shows a range and a trend; only the chart makes it visually obvious that the *same* 4166.06 level defined both — as the ceiling in Phase A and the floor in Phase C.
2. **That 4371.78 is a rejection, not just a maximum.** In the data it is one number. On the chart it is a visible wick into thinning volume — the shape carries the meaning.
3. **The event context.** OHLC cannot know that 08:30 NY on the first Friday is a scheduled-release slot. That interpretation came entirely from outside the numbers, which is why it is flagged as inferred.
4. **That the engine's SHORT labels were wrong-footed.** The engine emitted `SHORT` on the window's two biggest **up** candles. Only by looking at the chart is it immediately obvious these were breakouts, not grabs — the numbers alone report a sweep either way.

### Registered caveats

- **No economic claim.** Zero executions occurred; there is no trade ledger, no expectancy, no PnL. Nothing here supports a promotion or a config change (§6.5: information ≠ authority).
- **Sample size.** One instrument, 1,195 bars, ~2.5 weeks. The 7-of-7 EXPANSION invalidation rate is mechanically explained but statistically thin.
- **Session labels** derive from the measured +3 h offset. Per F-066 the live `crt_engine.session_windows` filter remains on broker time by deliberate decision — untouched here.
- **Demo feed.** Data is from an IC Markets *demo* server; spreads/fills differ from live.
- **Not the frozen corpus.** This analysis deliberately bypasses the Phase-1 frozen XAUUSD binding and is therefore **not** comparable to frozen-corpus artifacts.

---

*Method: `CRTEngine` (`v2_multi_2026_04`) driven directly from the Excel; independent causal structural read; all quoted OHLC verified byte-equal against the `candles` sheet.*
