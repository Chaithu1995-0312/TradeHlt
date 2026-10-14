# Plan — decode the "Trace Sujan docs" UNKNOWNs that the data can actually answer

## Context
The user asked: "we have the codebase, can't we decode the unknowns?" Answer: only some of them.
The trace has ~20 UNKNOWN rows of three different kinds, and the identity lock
(`docs/governance/SUJAN_CRT_IDENTITY_EXTRACTION_SYSTEM.md` §Primary Rule, §Measurement Firewall)
says data can produce **candidate proxies only** (status UNVALIDATED until the user approves), and a
profitable backtest never proves what Sujan does.

| Kind | Examples | Can the repo decode it? |
|---|---|---|
| **A. Facts about his own chart / trade** | which "weekly open" his red line is (4309.273 / 4255.613); where SL 4269 sits vs the 1H C1/C2 wicks; which 1H candles were C1/C2/C3 for BUY 4276.30; target 4299 vs which range high | **Yes, as candidates** — the bars exist in `data/mt5/XAUUSD_M15_2026-04-20_to_2026-10-06.csv` (covers 2026-09-21..26) |
| **B. Choices we can measure but not attribute** | stop buffer, wait time, break-even, partials | Measures what *works*, not what *he does*. Records 7–8 already did this for proxies (all ~0R/FAIL). Not proposed. |
| **C. Only he can answer** | "strong confirmation", news/no-trade days, screen hours, loss limits | No. Stays UNKNOWN → `.grok/SUJAN_QUESTIONS.md` |

Read-only probe this turn already shows why A needs care: his prices have **3 decimals** (our MT5
feed has 2 → different broker), and 4309.27 matches the *close* of 2026-09-02 05:30 while 4255.66
matches 2026-09-24 12:15 — coincidental hits are easy, so every match is a candidate with a tolerance,
never an identity.

## Approach (category A only, read-only research script, no `src/` change)
1. **Pin the trade window.** Record 7 chat 2026-09-25 21:29–21:36 (IST, assumed — state it). Load the
   corpus through the Corpus SSOT (`corpus_store.load` → `AdmittedCorpus`, F-119/F-120 so bars are UTC),
   aggregate M15 → 1H on the candidate grids.
2. **Weekly-open candidates** — compute each, report distance to 4309.273 and 4255.613:
   ISO-week first M15 open (broker), Sunday 17:00 New York open (market calendar
   `configs/data_provenance/market_calendar.json`), Monday 00:00 UTC, daily opens of each day that week,
   prior-week close. Tolerance = broker spread scale (≤ ~$0.5); report all, pick none.
3. **C1/C2/C3 around BUY 4276.30**: list the 1H candles in the 12 h before the chat; mark which pair
   satisfies "C2 swept C1 extreme and closed inside C1" (reuse `ParentCRTTrack` sweep predicate
   `structure.predicates.swept_high/low` read-only, or plain OHLC compare), then where 4269 (SL) and
   4299 (TP) sit vs C1/C2 high/low, PDH/PDL, and each weekly-open candidate.
4. Output a small table to the trace doc's Levels / Stop / Exit rows as **"Candidate (UNVALIDATED)"**,
   plus a drift-log Record 9 (original concept · candidate · evidence · status UNVALIDATED). No SEM,
   no MC, no backtest, no outcome numbers.

Files: one new script `scripts/research/sujan_trade_decode.py` (SITS-register: `script_census.py
--write-stubs` → `seed_script_registry.py` → `generate_script_matrix.py`), output to
`userinvestigation/`; edits to the Trace doc rows and `docs/research/sujan_identity_drift_log.md`;
session log.

## Verification
- Script prints the data path + row count for 2026-09-21..26 before computing.
- Every candidate row shows its numeric distance; any candidate within tolerance for BOTH red lines
  is reported, ties shown, none chosen.
- `check_governance_invariants.py --all` baseline before/after (script registry floor).
- User decides which candidate (if any) is his — only then the trace row changes from UNKNOWN.
