# Candle theory reference cards

User-supplied study cards (2026-10-08), kept as the **visual vocabulary** for:
- reviewing charts and artifacts (e.g. the XAUUSD bar-features page),
- reading live charts.

Numbered in reading order, from one candle to market structure to trade management.

CORRECTED 2026-10-14: the images in `01_…` and `08_…` were swapped. `01_` held the trend card (Day 4) and `08_` held the candlestick-basics card (Day 1). The two files were renamed so each image matches its name and row; nothing was deleted.

Some cards are partly written in Hausa: 02, 06, 07, 08 and 10. The diagrams carry the meaning, and each row below gives the English concept.

**These cards are teaching material, not repo evidence.** The patterns they describe have not been shown to give an edge on XAUUSD. The repo's measured results say the opposite so far:
- F-086: the feature/state vocabulary does not mark a profitable entry bar.
- F-097: no context family adds expectancy beyond CRT state alone.
- 2026-10-08 profitable-zone study: zone starts look like strong counter-moves, but entering on those features is net-negative after cost.

Use the cards to name what you see. Never use them as a reason a trade will work.

## Index: card → concept → where the repo measures it

| # | Card | Concept | Repo representation (canonical slot / FM id) |
|---|---|---|---|
| 01 | [01_candlestick_anatomy_body_wicks.jpg](01_candlestick_anatomy_body_wicks.jpg) | Candle anatomy. Body = open↔close, upper wick = high, lower wick = low. Long body = strong move, long wick = rejection. | `body_size` FM-001, `candle_range` FM-002, `upper_wick` FM-003, `lower_wick` FM-004, `body_ratio` FM-010 (`src/features/candle_math.py`) |
| 02 | [02_candle_ohlc_bullish_bearish_pressure.jpg](02_candle_ohlc_bullish_bearish_pressure.jpg) | OHLC. Green = close > open (buyers), red = close < open (sellers); a big candle = strong pressure. Wait for confirmation candles before entering. | Raw slots 0–3 (`open/high/low/close`); candle direction from close vs open; size via `body_size` / `disp_strength` |
| 03 | [03_hammer_bullish_reversal_long_lower_wick.jpg](03_hammer_bullish_reversal_long_lower_wick.jpg) | Hammer. Small body near the top, long lower wick, after a downtrend or at support → possible bullish reversal. | `hammer` FM-107 (slot 58), `pin_lower` FM-105, `lower_wick_ratio` FM-104, `rejection_intensity_lower` FM-117 (`src/features/candle_patterns.py`; trend context is NOT part of the definition). On the XAUUSD page, the bullish "rejection block" = the lower wick of a confirmed swing low. |
| 04 | [04_shooting_star_bearish_reversal_long_upper_wick.jpg](04_shooting_star_bearish_reversal_long_upper_wick.jpg) | Shooting star. Small body, long upper wick, after an uptrend or at resistance → possible bearish reversal. | `shooting_star` FM-108 (slot 59), `pin_upper` FM-106, `upper_wick_ratio` FM-103, `rejection_intensity_upper` FM-119. The page's bearish rejection block = the upper wick of a confirmed swing high. |
| 05 | [05_doji_indecision.jpg](05_doji_indecision.jpg) | Doji. Open ≈ close: indecision. Means reversal at support/resistance, nothing in a range; needs confirmation. | `doji_material` FM-109, `dragonfly_doji` FM-110, `gravestone_doji` FM-111 (material = range ≥ 0.5 × ATR). |
| 06 | [06_confirmation_engulfing_pinbar_morningstar_doji.jpg](06_confirmation_engulfing_pinbar_morningstar_doji.jpg) | Confirmation candles: engulfing, pin bar (rejection candle), morning star, doji. Use = find S/R → wait for confirmation → enter. | `engulfing_bull` FM-112 / `engulfing_bear` FM-113 + `engulfing_strength` FM-118; pin bar `pin_lower` FM-105 / `pin_upper` FM-106; doji FM-109..111; morning star `morning_star` FM-120 (slot 71). |
| 07 | [07_reversal_signals_hammer_star_engulfing.jpg](07_reversal_signals_hammer_star_engulfing.jpg) | Reversal signals: hammer, shooting star, bullish/bearish engulfing. | Same as 03/04/06. |
| 08 | [08_trend_bullish_bearish_market_hh_hl_lh_ll.jpg](08_trend_bullish_bearish_market_hh_hl_lh_ll.jpg) | Bull market = higher highs + higher lows; bear = lower highs + lower lows; sideways. Don't chase; wait for confirmation. | `higher_high` FM-055, `lower_low` FM-056, `trend_bias` FM-054 (EMA-based, not swing-based) |
| 09 | [09_market_structure_bos_choch.jpg](09_market_structure_bos_choch.jpg) | Market structure: uptrend, downtrend, break of structure (BOS), change of character (CHoCH = first break against the trend). | `break_of_structure` FM-057, `change_of_character` FM-083, `swing_high/low` FM-045/046 (causal, k = `swing_window`) |
| 10 | [10_support_resistance_zones.jpg](10_support_resistance_zones.jpg) | Support = buyers defend a level; resistance = sellers defend it. Buy near support, sell near resistance, only with confirmation. | Swing levels FM-045/046, `liquidity_distance`, `pdh/pdl_distance` FM-079/080, `eqh/eql_distance` FM-081/082 + `eqh/eql_present` FM-101/102 (concept MKT-L01). Sweeps of these levels: `liquidity_sweep` FM-058 / `sweep_detected` FM-059 |
| 11 | [11_fair_value_gap_fvg_bullish_bearish_retest.jpg](11_fair_value_gap_fvg_bullish_bearish_retest.jpg) | FVG = 3-candle imbalance (candle 1 high < candle 3 low, bullish; mirror for bearish); price often returns and is rejected; works with liquidity and order blocks. | `fvg_distance` FM-076 + `fvg_present` FM-098 (MKT-Z02, `src/features/smc/fvg.py`, same 3-candle rule); order blocks `order_block_distance/present` FM-075/097 |
| 12 | [12_entry_confirmation_inside_bar_breakout_momentum_rejection.jpg](12_entry_confirmation_inside_bar_breakout_momentum_rejection.jpg) | Entry confirmations: inside bar, breakout candle through resistance, strong momentum candle, rejection candle at support. | Momentum: `disp_strength`, `momentum_score`; breakout: `break_of_structure`; rejection: `pin_*` FM-105/106, `rejection_intensity_*` FM-116..119. Inside bar: `inside_bar` FM-114 + `compression_ratio` FM-115. |
| 13 | [13_risk_management_stop_target_rr_leverage.jpg](13_risk_management_stop_target_rr_leverage.jpg) | Stop loss below support, take profit at resistance, reward ≥ risk (e.g. 1:3), never over-leverage, risk 1–2% per trade. | Planner/risk path: `ExecutionPlannerV1_2` (SL/TP), `UltronRiskGate` (`min_rr_ratio`), `risk_percent` (F-111: 1% live); backtest stop anchor `backtest.sl_anchor` |

## What each card claims vs the repo rule (extracted 2026-10-14)

Read from the images and checked against `src/features/candle_patterns.py`, `configs/formulas/market_ontology.yaml`
and the active config's `feature_pipeline.candle_patterns` thresholds. "Branch" = an open decision on
the H4 divergence report (<https://claude.ai/artifact/AZnzfViBRctbrFARiCdBrt>, built by `tools/feature_audit/`),
where the card is the textbook side.

| # | The card's rule | The repo's rule | Difference |
|---|---|---|---|
| 01 | Body = open to close; upper wick reaches the high, lower wick the low. Long body = strong move; long wick = rejection; green = buyers, red = sellers. | FM-001..004 anatomy, FM-010 body_ratio = body / range. | Same anatomy. The card gives no number for "long". |
| 02 | Green = close above open, red = close below. A big candle is strong pressure. Read several candles before entering. | Raw slots 0–3; body size; `disp_strength`. | Same. "Big" has no threshold. |
| 03 | Hammer: small body near the top, long lower wick, weak upper wick; after a downtrend, strongest at support. | FM-107: lower wick ≥ 2 × body, upper wick ≤ 10% of range, low at or below the prior 5-bar low, range ≥ 0.5 × ATR. | The repo asks for a fresh 5-bar low, not a downtrend or a support level. |
| 04 | Shooting star: mirror of the hammer, after an uptrend, strongest at resistance; wait for confirmation. | FM-108: mirror of FM-107 at the prior 5-bar high. | Same split as 03. |
| 05 | Doji: open ≈ close, wicks on both sides; a possible reversal at support or resistance, common in ranges, neutral on its own. | FM-109: body ≤ 10% of range, wick sizes within 0.2 of each other, range ≥ 0.5 × ATR. Dragonfly/gravestone FM-110/111: body ≤ 5%, one wick ≥ 75%. | The repo ignores tiny bars (the ATR floor); the card does not. |
| 06 | Engulfing: the strong candle covers the previous one (drawn covering the whole candle, wicks included). Pin bar: long wick, small body. Morning star: red, small, green. Use: find support/resistance → wait for confirmation → enter. | FM-112/113 compare **bodies only**: the new body covers the previous body and is larger. Pin FM-105/106: wick ≥ 60%, body ≤ 25%, other wick ≤ 15%. Morning star FM-120: bodies ≥ 60%, middle ≤ 25%, no trend condition. | The repo's engulfing is looser than the drawing: the wicks do not have to be covered. |
| 07 | Hammer, shooting star and engulfing, each drawn at the end of a trend. | Same functions as 03, 04 and 06. | The repo does not require the end of a trend. |
| 08 | Bull market = higher highs and higher lows; bear = lower highs and lower lows; or sideways. Don't buy only because price is rising. | `higher_high` / `lower_low` FM-055/056; `trend_bias` FM-054 comes from EMAs. | The card compares swing to swing. Branch `hh-ll-swing-sequence` (2,625 bars). |
| 09 | Uptrend = HH + HL; downtrend = LH + LL. BOS = close through the previous high. CHoCH = the first break against the trend. | FM-057 `break_of_structure`, FM-083 `change_of_character`. | Branch `choch-swing-structure` (179 bars). Branch `swing-strict-fractal` (3 bars) covers the pivots themselves. |
| 10 | Support and resistance are **zones** (boxes) that price touches more than once. Buy at support, sell at resistance, only with confirmation. | Single levels: swing points, PDH/PDL FM-079/080, EQH/EQL FM-081/082/101/102. | The repo has no multi-touch zone. |
| 11 | FVG: three candles with a large impulse in the middle; the gap runs from candle 1's high to candle 3's low (bullish), mirrored for bearish. Price **returns into the gap and is rejected**; it works best with liquidity and order blocks. | FM-076/098: the same 3-candle gap. | Same gap. The card's trade is the retest into the gap; branch `fvg-full-fill` (343 bars) is about whether the repo ends the gap at that first touch. |
| 12 | Inside bar (small candle inside a larger one), breakout candle closing through resistance, strong momentum candle, rejection candle at support. Find the level → confirm → enter. | Inside bar FM-114 (range inside the previous range, inclusive), FM-115 compression; BOS FM-057; `disp_strength`; pins and rejection intensities FM-105/106/116..119. | "Breakout candle" and "momentum candle" are not named patterns in the repo. The rejection-candle-at-support idea is behind branch `rejection-textbook-invalidation` (775 bars). |
| 13 | Stop beyond support, target at resistance, reward bigger than risk (1:3 drawn), over-leverage leads to liquidation, risk at most 1–2% per trade. | Planner SL/TP, `min_rr_ratio`, `risk_percent` 1% (F-111). | Consistent. The 1:3 is an example, not a repo setting. |

## Reading a live chart with these cards

1. **Structure first** (09, 08). Find the trend and the last BOS/CHoCH. On the page: `break_of_structure`, `change_of_character`, `higher_high` / `lower_low`.
2. **Levels** (10, 11). Find support/resistance, previous-day high/low, equal highs/lows and open FVGs/order blocks. On the page these are the SMC zone boxes; the `*_present` flags tell "no zone" apart from "on the zone".
3. **The candle at the level** (01, 03, 04, 05). Read body vs wicks. A long wick into a level is a rejection; a doji is indecision; a big body is pressure.
4. **Confirmation** (06, 07, 12). Wait for the next candle(s) to confirm. A single pattern alone is the weakest read.
5. **Risk** (13). Before entering, decide the stop beyond the level and a target with reward > risk.

## Gaps these cards expose (not built; listed so they stay visible)

**Registered 2026-10-08 (F-118, schema v8.0, slots 54-70):** pin bar, hammer, shooting star, doji
(material / dragonfly / gravestone), engulfing, inside bar, compression ratio and rejection
intensities — FM-103..FM-119 in `configs/formulas/market_ontology.yaml`, math in
`src/features/candle_patterns.py`, thresholds in `feature_pipeline.candle_patterns`. They are
observations: direction comes from context (structure, levels, session), not from the pattern name.

CORRECTED 2026-10-14: morning star is registered as FM-120 (vector slot 71, `features.candle_patterns.morning_star`); it was listed here as missing.

Still with no registered identity:
- evening star (3-candle; FM-120 deliberately has no evening star)
- breakout candle and "strong momentum candle" as named patterns (covered only indirectly by
  `break_of_structure`, `disp_strength`, `momentum_score`)
