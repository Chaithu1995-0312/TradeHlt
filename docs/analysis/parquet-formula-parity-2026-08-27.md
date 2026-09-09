# Parquet feature values vs ontology formulas (2026-08-27)

> Point-in-time. Not a living spec. Not an F-id. Not G001.
> Lane: measurement / evidence. Question: can a parquet-access LLM trust the stored numbers
> as the semantic formulas behind them?

**Population:** `clean_labels.parquet` unique long bars n=47,166
(`2024-05-23 05:00` … `2026-05-21 23:30`), joined to `data/mt5/XAUUSD_M15.csv`
(provenance `candle_path` in the file). Companion numbers:
[`parquet-formula-parity-2026-08-27.json`](parquet-formula-parity-2026-08-27.json).

Three comparisons, not one:

| Layer | Question | Result |
|---|---|---|
| A | Formula(stored inputs) == stored output? | Geometry / ATR-scaled identities hold (float32). |
| B | Stored OHLC == cited CSV? | Exact. 0 miss. |
| C | Stored 38 cols == HEAD `FeaturePipeline.run()`? | Bit-identical on all 38 overlapping columns. |

`RECOMPUTE != RECOVER` still holds as law: this is a recompute that *happened to match*.
It does not make the parquet an identity store.

---

## Verdict (what to trust)

**Trust the stored numbers as a faithful copy of today's default FeaturePipeline
on the 38 overlapping columns.** They are not a corrupted dump.

**Do not trust them as skill / UTC / current schema / trades.**

| Surface | Trust? | Why |
|---|---|---|
| L0 OHLC (`open/high/low/close/volume`) | Yes, as this CSV | Exact vs `data/mt5/XAUUSD_M15.csv` |
| FM-001 `body_size`, FM-002 `candle_range`, FM-010 `body_ratio` | Yes | Match `candle_math` (canonical body/range, **not** body/total_wick) |
| `disp_strength`, `volatility_ratio`, `trend_bias` | Yes, as the registered formula | Match `derived_math` on stored inputs (float32) |
| `ema_spread`, `momentum_score` | Yes as **FM-022/023** (`atr_relative`); **No** as scale-free skill | Values match HEAD. Formula is the F-061 defect. Empirical `legacy/corrected` median = 3313.67 = median close. |
| `session`, `hour_of_day` | Yes as **broker_local**; **No** as UTC | Values match HEAD. Formula is the F-066 defect. |
| Swing / BOS / liquidity structure cols | Yes as **today's causal HEAD emitter** | Bit-identical vs HEAD, including `swing_high/low`. |
| 9 v5 SMC columns | Absent | Schema 38 vs live 48. `SCHEMA_HASH` stored `c87a1aba…` ≠ HEAD `f52bf5d3…`. Absence ≠ “no FVG in the market.” |
| L2 feature states | Not in file | Unjoinable |
| `outcome` / `rr_achieved` | No | F-022. Use `y_tp1`. |
| Protocol `pit_status=PIT_UNCLEAN_STORED_FEATURES` | Label is conservative on **this** file | F-051's 63% centered-vs-causal disagreement does **not** reproduce here: stored swings == HEAD causal pipeline. Does not reverse F-051 as a historical finding. |

---

## Layer A — formula on stored inputs

Unique long bars, 47,166.

| Column | Formula | Verdict | Notes |
|---|---|---|---|
| `body_size` | `|close-open|` (FM-001) | MATCH_EXACT | |
| `candle_range` | `high-low` (FM-002) | MATCH_EXACT | |
| `body_ratio` | `body/range` (FM-010) | MATCH_FLOAT32 | med abs 6.9e-9 |
| `body_ratio` vs `body/total_wick` | GD-001 anti-check | DRIFT (wanted) | med abs 0.37. Archive is canonical, not the live-hook dead identity. |
| `volatility_ratio` | `(high-low)/(atr*close)` | MATCH_FLOAT32 | |
| `disp_strength` | `clip(body/(atr*close),0,3)` | MATCH_FLOAT32 | |
| `retest_depth` vs **ungated** math | `|close-ema_fast|/(atr*close)` | DRIFT | Expected: pipeline zeros when `retest_flag!=1`. Not corruption. |
| `ema_spread` vs FM-022 | `(ema_f-ema_s)/atr` | NEAR | Reconstructing from float32 components; **HEAD bit-identical** so the stored column *is* FM-022. |
| `ema_spread` vs FM-030 | `/ (atr*close)` | DRIFT | med abs 1,566. Active config is `atr_relative`, not the correction. |
| `momentum_score` vs FM-023 | `close.diff()/atr` | NEAR | Same float32 reconstruction story; HEAD bit-identical. |
| `momentum_score` vs FM-031 | `/ (atr*close)` | DRIFT | med abs 1,248. F-061. |
| `trend_bias` | `sign(ema_fast-ema_slow)` | MATCH_EXACT | |

F-061 identity measured on this file: median(`ema_spread_legacy / ema_spread_atr`) = **3313.67** = median close **3313.66**.

---

## Layer B — L0 vs corpus

CSV join miss = **0 / 47,166**. `open/high/low/close/volume` MATCH_EXACT.

---

## Layer C — HEAD pipeline recompute

`FeaturePipeline.run()` on the same CSV: 47,275 → 47,197 after 78-row warmup.
Join on timestamp: 47,166.

**All 38 overlapping columns MATCH_EXACT** (max abs 0):  
`open high low close volume volume_ratio double_sweep ema_fast ema_slow ema_spread trend_bias trend_strength momentum_score atr volatility_ratio rsi_14 macd_line macd_signal macd_hist_z sweep_detected liquidity_sweep break_of_structure swing_high swing_low higher_high lower_low body_size candle_range body_ratio volatility_regime session hour_of_day disp_strength retest_depth candles_since_retest liquidity_distance liquidity_pressure_score volume_spike`.

`opportunities.parquet` vs `clean_labels.parquet` on those 38: **0 DRIFT columns** (same timestamps).

HEAD is schema v5.0 / 48-dim. The extra 9 SMC slots are not in the parquet. That is a **schema-family gap**, not a value error on the 38.

Active defaults that therefore **are** in the file: `normalization_basis=atr_relative` (FM-022/023, F-061/F-064), `session_timestamp_basis=broker_local` (F-066).

---

## What this does not authorize

- Treating parquet as L0–L5 identity storage
- Treating FM-022/023 magnitudes as skill
- Treating `session` as UTC
- Joining 38-dim archive onto 48-dim as current
- G001 / promotion / P-GOAL-04
- Reopening F-086 because numbers are faithful — faithful zeros are still zeros

Bot paste-pack updated: [`.grok/PARQUET_BOT_BRIEF.md`](../../.grok/PARQUET_BOT_BRIEF.md).
