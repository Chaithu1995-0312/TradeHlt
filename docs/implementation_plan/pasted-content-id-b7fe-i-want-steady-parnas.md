# Plan: extract the candle-theory cards into checkable rules

## Context

The user saved 13 study cards at `docs/reference/candle_theory/01..13_*.jpg` (index: `README.md`, 2026-10-08) and asked to "check that and extract". I read all 13 images. Two things came out:

1. **Two files carry the wrong name.** `01_candlestick_anatomy_body_wicks.jpg` actually shows "Day 4: bullish/bearish market, HH/HL, LH/LL, uptrend/sideways/downtrend"; `08_trend_bullish_bearish_market_hh_hl_lh_ll.jpg` actually shows "Day 1: candlestick basics, body/upper wick/lower wick". The README rows for 01 and 08 describe the file names, not the pictures, so the index is crossed for those two. The other 11 match.
2. The README maps each card to a repo FM id, but it does not write down **what the card actually claims** as a rule that can be checked against the repo formula. That is the useful extraction: the card's rule, in plain words and as a condition, next to the repo's rule, with the difference called out. This also feeds the open branches in the divergence report (rejection, FVG, CHoCH, HH/LL).

## What the cards say (extracted, to be written into the README)

| Card | Card's rule (as drawn/written) | Repo rule | Match? |
|---|---|---|---|
| Basics (file 08) | body = open↔close, upper wick to high, lower wick to low; long body = strong move, long wick = rejection | FM-001..004, FM-010 | same anatomy; "long" has no threshold on the card |
| OHLC (02) | green close>open = buyers, red = sellers; big candle = strong pressure; look at several candles before entry | raw slots 0–3, `body_size` | same; "big" undefined |
| Hammer (03) | small body near the top, long lower wick, weak upper wick; after a downtrend / at support | FM-107 shape only | shape matches; card requires a prior downtrend + support, repo does not (by design, F-118) |
| Shooting star (04) | mirror: small body at bottom, long upper wick, after uptrend / at resistance; wait for confirmation | FM-108 shape only | same split as hammer |
| Doji (05) | open ≈ close, wicks both sides; reversal at S/R, frequent in ranges, neutral alone | FM-109..111 | repo adds a size floor (range ≥ 0.5 ATR); card has none |
| Confirmation (06) | engulfing: big candle covers the previous one; pin bar: long wick + small body; morning star (red, small, green); doji; use = find S/R → confirm → enter | FM-112/113, FM-105/106; morning star not registered | card's engulfing is drawn covering the whole previous candle incl. wicks — check against FM-112's body-only or full-range test |
| Reversal signals (07) | hammer, shooting star, bullish/bearish engulfing, each drawn at the end of a trend | same as above | context (end of trend) not in repo |
| Trend (file 01) | bull = higher highs + higher lows, bear = lower highs + lower lows, plus sideways; don't buy just because price is rising | FM-055/056 (HH/LL), FM-054 EMA trend_bias | card is swing-to-swing; repo `trend_bias` is EMA-based; matches the open HH/LL branch (2,625 / 1,158 bars) |
| Structure (09) | uptrend HH+HL, downtrend LH+LL, BOS = close beyond previous high, CHoCH = first break against the trend | FM-057, FM-083 | matches the open CHoCH branch (179 bars) |
| S/R (10) | support/resistance are **zones** (boxes), touched more than once; buy at support / sell at resistance only with confirmation | swing levels, PDH/PDL, EQH/EQL | repo uses single levels, card uses multi-touch zones |
| FVG (11) | 3 candles, middle one a large impulse; gap = candle-1 high to candle-3 low (bull), mirror for bear; price returns into the zone **and is rejected** | FM-076/098, same 3-candle gap | card treats a retest into the gap as the trade, not as the end of the gap — matches the open FVG-fill branch (343 bars) |
| Entry setups (12) | inside bar, breakout close through resistance, strong momentum candle, rejection candle at support; find level → confirm → enter | FM-114/115, BOS, `disp_strength`, FM-105/106/116..119 | "breakout" and "momentum candle" not registered as named patterns |
| Risk (13) | stop beyond support, target at resistance, 1:3 reward:risk example, over-leverage → liquidation, risk ≤ 1–2% per trade | planner SL/TP, `min_rr_ratio`, `risk_percent` 1% (F-111) | consistent; 1:3 is an example, not a repo setting |

(The table above is my reading of the images; the step-2 check below confirms the engulfing/doji details against code before writing.)

## Steps

1. **Fix the 01/08 swap** by renaming the two files so names match content (`git mv` is not possible — the folder is untracked; plain rename, nothing deleted), and swap their README rows. Nothing else references these paths (grep `candle_theory` first; the memory file `reference_candle_theory_cards.md` lists only the folder).
2. **Verify the repo side** of each "Match?" cell against source before writing: `src/features/candle_patterns.py` (engulfing body vs range, doji floor), `configs/formulas/market_ontology.yaml` FM-103..119, and the divergence report's branch counts (`results/divergence_h4.json`).
3. **Write the extraction into the existing README** (existing-doc-first, §6.2): add a column "Card's rule" and a column "Difference from repo", keep the "teaching material, not evidence" header. No new file.
4. **Cross-link** the four cards that back an open report branch (01-trend, 09, 11, rejection via 03/04/12) to the branch ids, so the cards appear as the "textbook" side when the user decides those branches.
5. Update the memory file `reference_candle_theory_cards.md` (note the swap correction) and append the session log entry.

## Not in scope

No code, no feature changes, no new patterns registered (morning star, breakout candle stay listed as gaps). Branch decisions stay the user's.

## Verification

- Open both renamed images and confirm the title on each matches its new name.
- Every FM id in the README resolves in `market_ontology.yaml` (grep).
- README links resolve (all 13 file names exist).
