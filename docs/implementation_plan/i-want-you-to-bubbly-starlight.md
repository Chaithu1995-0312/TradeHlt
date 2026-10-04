# Plan: answer "what is liquidity_sweep" on the H4 validation page

## Context
User continues the second-low thread on `userinvestigation/second_low_h4_validation.jsonl`
(turn n=4 already gave the FM-058 formula on the 4 H4 bars). New ask: what `liquidity_sweep`
*is* (meaning), recorded on the same page.

## Answer content (assistant turn n=6), sourced from `configs/formulas/market_ontology.yaml`
- FM-058, vector index 21, Liquidity / Structural, values {-1, 0, +1}.
- Meaning: a stop-run. Price trades through a structural reference (the last published swing
  high/low) and closes back inside it. Resting stops sit beyond swing points; the sweep is the
  market taking them and rejecting the level, not accepting a break.
- +1 buy-side sweep (above the swing high, close back below). -1 sell-side sweep (below the swing
  low, close back above). 0 none. The sign names the side swept, not the trade direction:
  -1 is "often bullish in consequence".
- Mutually exclusive with break_of_structure on the same reference (close stays outside = break).
- It is the founding event of the CRT ontology; `sweep_detected` (=sweep != 0),
  `candles_since_sweep` and the retest flag are built from it (`feature_pipeline.py:1051-1155`).
- Active arm is `latest_unconsumed`: only the latest swing, never consumed (why 4084.24 fired
  three times on Aug 4–5). FM-090 `liquidity_sweep_e01` (any active level, consumed once) is
  registered but inactive (F-112).
- On the H4 page: the 08-03 16:00 -1 took the swing low 4020.93 (= that day's PDL); it is
  a different, much nearer level than `second_low_20d` 3969.34 (gap 49.74). No order.

## Edits
1. Append to `userinvestigation/second_low_h4_validation.jsonl`: n=5 user (verbatim:
   "continue discussion and update in jsonl second_low_h4_validation.jsonl what is liquidity_sweep"),
   n=6 assistant (text above + SESSION LOG block). Use Write/Edit tool (no heredoc, CLAUDE.md §1.6).
2. Add the same two rows, HTML-escaped, inside `<textarea id="jsonl-fallback">` of
   `second_low_h4_validation.html` (after the n=4 line, line 33).
3. Append the SESSION LOG entry to `assistant_project.md`.

No code, config, or schema change.

## Verification
- Parse every line of the jsonl with `json.loads` (venv python); check n is 1..6 in order.
- Grep the HTML for `&quot;n&quot;: 6`.
