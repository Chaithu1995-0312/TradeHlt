# XAUUSD Trading Method

Oct 9, 2026 · @Chaithanya

## How we use this doc

This is your method in your words, so it can be tested as you actually trade it. Each section ends with a line marked **Your rule:**. Replace it with what you really do, including the parts that feel like judgement.

- Write it as you would explain it to someone copying your trades.
- If a step is a feeling, describe what you are looking at when you get that feeling.
- Claude only adds questions and test notes; nothing here is a claim that the method works.
- Once a section is written, it is frozen before any test is run on it.

## Market and timeframes

XAUUSD on MT5 is the main market; the method also runs on all forex pairs and crypto coins you monitor; the rest is yours to fill.

**Per-market rules (decided):**

- Crypto runs as its own 24/7 track; its sessions and D1 close use UTC.
- Stops and targets are set in ATR terms per market, not fixed pips.
- Tick value and contract size are set per symbol in config.
- Each symbol has a max-spread filter; no entry while the spread is above it.
- Coins that follow BTC count as one exposure: same-direction coin positions share one risk budget.
- Overnight swap is decided per trade at placement.

* Which timeframe sets the bias (D1, H4)?
* Which one shows the levels (H4, H1)?
* Which one you enter on (H1, M15, M5)?
* Which hours or sessions you actually sit at the screen (in IST or UTC)?

**Your rule:** *write here*

## Structure

The bias comes first: it decides whether you look for longs, shorts, or nothing.

- What makes the trend up, down or sideways for you: higher highs and lows, a break of structure, a moving average, or the daily candle?
- How many swings back do you look?
- Does one change of character flip your bias, or do you wait for a second break?

**Your rule:** *write here*

## Levels

The level is where you are willing to act; everywhere else you wait.

- Which levels do you mark: previous-day high/low, Asia range, equal highs/lows, order blocks, fair value gaps, round numbers?
- How far back do you go, and which levels do you ignore?
- What makes a level "strong" to you: touched several times, recent, on the higher timeframe?
- Does price need to sweep the level first, or just reach it?

**Your rule:** *write here*

## The candle at the level

This is what you read when price arrives at your level.

- Which shapes count: long wick into the level, engulfing, doji, a big body away from it?
- On which timeframe do you read that candle?
- What would make you skip a candle that looks right?

**Your rule:** *write here*

## Confirmation

The cards' main advice is to wait for confirmation, and this is the step our tests never had.

- What exactly confirms: the next candle closing beyond the signal candle, a break of a small structure on a lower timeframe, a retest?
- How long do you wait for it before giving up on the setup?

**Your rule:** *write here*

## Entry

The entry must be exact enough that two people would place the same order.

- Market order at the confirming candle's close, or a limit order back at the level?
- If it is a limit, what happens when it is never filled?

**Your rule:** *write here*

## Stop

The stop decides how often you are wrong; on gold H4 its width alone moved the hit rate from 11% to 57%.

- Beyond the signal candle, beyond the level, or a fixed distance in dollars or ATR?
- Do you add a buffer beyond the wick, and how much?
- Do you ever move the stop to break-even, and when?

**Your rule:** *write here*

## Exit

A 3R target on gold H1 was hit only about 20% of the time, below the 25% needed to break even, so the exit matters.

- Fixed target (1R, 2R, 3R), the next level, or a trail?
- Do you take part of the position off early?
- Do you close by a certain time (end of session, before news, before the weekend)?

**Your rule:** *write here*

## Sizing and risk

The size of the next few hours' move is the one thing the data can forecast (R² 0.38), so sizing is where a rule can use it.

- What do you risk per trade: a fixed amount, or 1% of the account (the repo's live setting)?
- Is there a daily loss limit, or a number of losing trades after which you stop?
- Do you trade smaller when the market is moving fast, or the same size?
- What drawdown would make you pause trading altogether?

**Your rule:** *write here*

## When you do not trade

The days you sit out are part of the method and must be written down too.

- News days (US data, Fed), Monday open, Friday close, holidays?
- After a big move, or when price is in the middle of a range far from any level?

**Your rule:** *write here*

## Test notes

Each part tested alone on gold has not paid so far; the full method, written above, has never been tested as one.

| Part | What the repo measured (XAUUSD) | How we would test your rule |
| --- | --- | --- |
| Structure | All 67 features together: no direction information over 4 hours (AUC 0.496) | Only as part of the full method |
| Levels | Prior-day-low sweep on H1, long, 3R: −0.26R on unseen months, same as entering on any bar | Your own level list, frozen first |
| Candle at the level | 11 patterns alone: none beat bars with the same stop size beyond chance | Only after your level and confirmation |
| Confirmation | Never tested | Your rule, exactly as written |
| Stop and exit | Exit alone is not the main problem (F-087); stop width drives the hit rate | Your rule, one version only |
| Sizing | Next-4h move size is forecastable (R² 0.38 from volatility and time of day) | Volatility sizing on a simple baseline first |

The months 22 May – 6 Oct 2026 are already used, so a clean test of your full method means paper-trading it forward from the day it is frozen.
