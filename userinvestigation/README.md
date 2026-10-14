# userinvestigation

Local record of XAUUSD investigations. Conversation pages, measurement notes, and frozen probe scripts live here. A number in this folder is a record of the object named in that file. It does not promote a config, change `ACTIVE_VERSION`, or grant production weight.

`economic_claims_allowed` is `false` on the frozen rules in this folder.

## How a page is stored

One discussion is one stem, as a sibling pair:

| File | Role |
|---|---|
| `<stem>.jsonl` | The store. One object per line, oldest first. Fields: `n` (1-based), `role` (`user` or `assistant`), `ts` (`null` on user lines, `YYYY-MM-DD HH:MM` on assistant lines), `text` (verbatim). |
| `<stem>.html` | The view. It fetches the sibling JSONL. A hidden `<textarea id="jsonl-fallback">` holds the same JSONL so the page still renders from `file://`. |

Open the HTML directly, or serve this folder (`python -m http.server`) so the page reads the live JSONL. Keep the textarea copy equal to the JSONL. Leave older pairs unchanged when a new chat starts. A Grok chat puts `grok` in the stem: `session_conversation_grok_YYYYMMDD_HHMM`.

`session_conversation.html` is the 2026-09-22 chat written into the HTML itself. It has no JSONL. `session_conversation_20260923_0229.md` is a markdown note, outside the pair schema.

## Map

### Conversation pages

| Stem | What it holds |
|---|---|
| `session_conversation.html` | 2026-09-22 chat, HTML only |
| `session_conversation_20260923_0058` | Design pair |
| `session_conversation_20260923_0229.md` | Markdown session |
| `session_conversation_20260925_0101` | 2026-09-25 session |
| `session_conversation_grok_20260925_0114` | 2026-09-25 Grok session |
| `session_conversation_grok_20260927_1754` | 2026-09-27 Grok session |
| `flow_20261004` | State formation and the one-month trade funnel (2026-07-06 .. 2026-08-07) |
| `ohlctransformation` | OHLC fetch paths and entry / SL / TP producers |
| `multitpwalk_analysis` | `multi_tp_walk` discussion |
| `second_low_monitor` | Second-low-of-20-trading-days monitor, M15 month |
| `second_low_h4_validation` | Same month rebuilt on H4 |
| `rr_decode_20261009` | Decode of `-0.4389R` (R-multiple: meaning, cash math, not-a-full-stop, soft-gate context) |
| `session_conversation_20261010_0738` | Walkthrough of `researcharctitecuredocs/` (Research SSOT framework docs) |
| `run_id_trace_20261010` | Latest XAUUSD backtest `run_id` family (`run_20261009_215217`, F-101 aliases) |
| `schema_slice_20261010` | XAUUSD M15 close<open 8h/5h slice + canonical schema ranges (2024-05-22 warmup window, then 2024-05-23 full 79-vector). Sibling dumps `_day1.json` / `_later.json` |
| `card_a_trend_filter_20261010.json` | Card A+RRR baseline (n=444) and Card A-T FM-054 agree filter (n=230) on 2024-05-23..29 source XAUUSD M15. Gross, diagnostic, `economic_claims_allowed` false. |

Static views with no JSONL sibling: `CANONICAL_FEATURES.html`, `enriched_df.html`.

### Census and knowledge (2026-10-04)

| Path | Read |
|---|---|
| [`census_20261004/README.md`](census_20261004/README.md) | Movement census on the one-month XAUUSD M15 slice. Stage funnel, movement distribution, GAP-001. |
| [`knowledge_20261004/README.md`](knowledge_20261004/README.md) | Walk × state, and whether price alone predicts displacement. GAP-002. |

### Second low

Root measurements for the 2026-07-06 .. 2026-08-07 window:

| File | Contents |
|---|---|
| `second_low_join_20260706.jsonl` | Every-bar join of `second_low_20d` to FVG, PDH/PDL, and `rr_gross` |
| `second_low_touch_20260706.jsonl` | Long-only touch book (empty on this month) |
| `pnl_sign_trace_20260803.jsonl` | August full-position mark cycle |
| `second_low_h4_join.jsonl`, `second_low_h4_sign_trace.jsonl`, `second_low_h4_20260706_summary.json` | H4 recheck |
| `xauusd_h4_20260706_20260807.csv` | H4 resample of that month (149 bars) |

Each `*.jsonl` row file has a sibling `*_summary.json` where one was written.

`second_low_algo/` is the research tool. It sends no orders.

```text
python second_low_algo/second_low_algo.py backtest --csv <csv> [--csv <csv>] --out-dir <dir>
python second_low_algo/second_low_algo.py live --rule second_low_algo/rule_frozen.json --forward-start 2026-10-07 --out-dir <dir>
```

| File | Contents |
|---|---|
| `second_low_algo.py` | Level, trigger, long order, `multi_tp_walk`, learn, live |
| `walk_forward.py`, `walk_forward_summary.json` | Walk-forward of the learned rule |
| `rule_frozen.json` | Frozen H4 rule, condition `at_or_above_pdl`. Forward paper only |
| `rule_frozen.pre_realtime_20261006T231114.json` | Copy from before the realtime tail change |
| `backtest_M15.jsonl`, `backtest_H1.jsonl`, `backtest_H4.jsonl`, `backtest_summary.json` | Backtest rows |
| `live_candidates.jsonl`, `live_runs.jsonl`, `live_task.log`, `run_live.cmd` | Live-path output |
| `reclaim_arm.py`, `reclaim_arm_freeze.json`, `reclaim_arm_rows.jsonl`, `reclaim_arm_summary.json` | Arm B reclaim. Status `EXPLORATORY_POST_HOC` |

`second_low_20d` is the second-smallest prior daily low over 20 trading days. It is not a canonical feature slot.

### H4 C1 / C2 / C3 probes

Unvalidated proxies. The entry summary names the object as calendar H4 `ParentCRTTrack` C1/C2/C3 used as an entry. That is a separate object from identity-certified Sujan CRT.

| File | Contents |
|---|---|
| `h4_c1c2c3_entry_xauusd.jsonl` | Entry proxy on `data/mt5/XAUUSD_M15.csv` |
| `h4_c1c2c3_keylevel_xauusd.jsonl` | Same arm plus a PDH/PDL/week-open filter |
| `h4_c1c2c3_near_level_frozen.py` | Frozen near-level rule (C2 extreme within 0.5 × prior H4 ATR14 of PDH/PDL/week open) |
| `h4_c1c2c3_near_level_oos_20260522_20261006.*` | Out-of-sample run of that rule, eval start 2026-05-22 |
| `h4_c1c2c3_1h_confirm_frozen.py` | Successor. Entry is the first 1H close in the trade direction inside C3. The freeze file records the predecessor's out-of-sample result as already known |
| `h4_c1c2c3_1h_confirm_insample.*` | In-sample run of the 1H-confirm rule |
| `h4_c1c2c3_1h_confirm_oos_reused.*` | Same holdout window reused. The freeze file says this is not an independent test |

Each frozen `*.py` has a sibling `*_freeze.json`.

### Model and state notes

| File | Contents |
|---|---|
| `model_layer_tracker.md` | Model-layer rewrite tracker (K1–K17, phases) |
| `RRModelAnalysis.md` | RR model design record. Design only |
| `TradenetModel.txt` | Feature-schema to model notes |
| `linkcostmodelstateengineschema.txt` | Engine state machine: enter, work, exit, with reference-run counts |

### Sujan decode

`sujan_trade_decode/sujan_trade_decode.json` stores candidates. Its `authority` field is none. The human bridge decides identity. Load `docs/governance/SUJAN_CRT_IDENTITY_EXTRACTION_SYSTEM.md` before treating anything in that file as the object Sujan described.

## Adding a page

1. Pick a new stem. Dated chats use `session_conversation_YYYYMMDD_HHMM` or `session_conversation_grok_YYYYMMDD_HHMM`. A one-token analysis stem (`flow_YYYYMMDD`, `second_low_monitor`) is also a pair.
2. Append the user line, then the assistant line, to the JSONL.
3. Refresh the HTML textarea in the same step.
4. Leave prior stems as they are.

`__pycache__/` is generated from the frozen `*.py` files. It is not part of the record.
