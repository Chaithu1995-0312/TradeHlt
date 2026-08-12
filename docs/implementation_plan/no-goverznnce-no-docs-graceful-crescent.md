# OSS-lab adapter: correct the PnL unit, then derive risk — Tradelatest baseline

## Context

The OSS lab's `TradelatestBaselineAdapter` normalizes Tradelatest trade rows into the
cross-engine `BenchmarkTradeRecord` contract. A read-only trace against a **fresh
Phase-1-pinned backtest** (`results/run_20260812_113506_XAUUSD/XAUUSD_trades.csv`, 1 trade,
`CRT-0001`) showed the adapter recognizes only ~4 of ~24 markable fields, and — more
seriously — that its one PnL mapping is unit-incorrect in a way that becomes actively
corrupting the moment a second field is fixed.

Implementation was gated on independently verifying the `net_pnl` unit from source. **That
verification is complete.**

### Verified from source

- `pnl_rr_net` is a **dimensionless R-multiple** — `backtest_v2.py:1051-1053`:
  `risk_pips = |entry_price_fill − sl_price| / pip_size`; `pnl_rr_net = (price_move_net /
  pip_size) / risk_pips`. `pip_size` cancels.
- `capital_after − capital_before` is **account currency** — `CapitalCurve.apply_trade`
  (`:421-427`): `dollar_pnl = pnl_per_unit × position_size`.
- `position_size` (`:411-419`) = `current_risk_amount / |entry − sl|`, so
  `size × price_distance = dollars` by construction.
- **Artifact precision** (`to_csv_rows`, `:1109-1128`): prices (`entry_raw`, `entry_fill`,
  `sl`, `tp1`, `tp2`, `exit_fill`) are written at full float precision; `position_size` and
  `capital_*` are rounded to 2dp, `pnl_pips_*` to 1dp, `pnl_rr_*` to 4dp.
- TP1/TP2 are **sequential ladder legs, not alternatives** — `:1335` counts a TP2 exit as
  also a TP1 hit; `tp1_hits`/`tp2_hits` are tracked and reported separately (`:1189-1190`,
  `:1247-1248`, `:1559`).
- Arithmetic closes on CRT-0001: price risk `1.1239`; money risk `889.73 × 1.1239 =
  1000.00` (1% of 100k); `−0.0430/1.1239 = −0.0383 = −38.27/1000`.

### The hazard this fixes

Today `net_pnl ← pnl_rr_net` (R) while the contract states unsuffixed fields are money
(`trade_record.py:107`). `initial_risk` is absent, so `expectancy_r` correctly reports
`UNKNOWN` (`canonical.py:143-148`). **Populating `initial_risk` without first fixing the
unit would compute `R ÷ price_distance` and label it `MEASURED`** — converting an honest
gap into a silent error. Hence the strict ordering below.

## Scope

`oss_lab/adapters/tradelatest/adapter.py` only. No spine/engine changes, no config, no
promotion path. See Open Decision re: repo governance mandates.

## Implementation

### Step 1 — Establish money as the contract unit (must be first)

| Contract field | Source | Note |
|---|---|---|
| `net_pnl` | `capital_after − capital_before` | replaces `pnl_rr_net` |
| `gross_pnl` | `pnl_pips_raw × pip_size × position_size` | derived |
| `spread_cost` | `spread_pips × pip_size × position_size` | derived |
| `slippage_cost` | `slippage_pips × pip_size × position_size` | derived |

`pip_size` is not a CSV column — take it from the adapter call site or infer via
`(exit_fill − entry_fill) / pnl_pips_net`; do **not** hardcode 0.01. If unavailable, leave
the three derived fields `NOT_AVAILABLE` — `net_pnl` needs no `pip_size`.

`fees`, `financing_cost`, `other_costs` stay `NOT_AVAILABLE` — no commission/swap model
exists in `TradeJournal`.

### Step 2 — Derive `initial_risk` (only after Step 1)

`initial_risk = |entry_filled − sl| × position_size` (money, matching Step 1) = 1000.00.

Mark `PRESENT`, `native_field="derived:|entry_filled − sl| × position_size"`, with reason:
**"deterministically derived from available artifact fields; precision bounded by the
producer's CSV rounding"** — *not* "exact." The price factors are full-precision but
`position_size` is 2dp, and the pip-derived cost fields are coarsest (`pnl_pips_*` at 1dp),
which is what produces the −38.26 vs −38.27 reconstruction residual. The contract must not
encode a stronger precision guarantee than the artifact provides.

**Never** alias `risk_score` here: it is CRT fusion decision-confidence (`:2240-2241`), a
0–1 score, not a risk amount.

### Step 3 — Safe aliases (source-confirmed)

`entry_raw→entry_requested`, `entry_fill→entry_filled`, `exit_fill→exit`,
`position_size→quantity`, `opened_at→fill_ts`. `opened_at` is set on the same bar as the
fill (`:960`, `:994-995`) — there is no separate signal/decision/order clock, so
`signal_ts`/`decision_ts`/`order_ts` stay `NOT_AVAILABLE`. `closed_at` has no contract
field → sidecar.

### Step 4 — `tp` → `NOT_APPLICABLE`

Reason string must carry the semantics explicitly: **"source has an applicable multi-leg
TP ladder (tp1→tp2) that this single-scalar contract field cannot represent"** — i.e.
`NOT_APPLICABLE` means *the contract shape is insufficient*, not *the data is missing*.
Do **not** add `legs[]`; do **not** pick `tp1` or `tp2`. `exit` carries the realized
aggregate.

### Step 5 — Testimony to sidecar

`adapter_meta["tradelatest"]`: `risk_score`, `risk_pct`, `htf_id`, `state_path`, `session`,
`shadow_used`, `bitnet_score_at_entry`, `config_version`, and the 39 canonical feature
columns. Never contract fields — `adapter_meta` is documented non-metric input
(`trade_record.py:121-122`) and `canonical.py` never reads it. Optionally set `intent` to a
comparable, metric-inert semantic label.

### Frozen boundary — never do these

`risk_score → initial_risk` · `pnl_rr_net → net_pnl` · `tp1 → tp` · `tp2 → tp`

### Out of scope

MFE/MAE stay `NOT_AVAILABLE`. They *are* computed (`observe_open_bar` `:912-939`,
`mfe_rr`/`mae_rr` `:1067-1068`) but dropped by `to_csv_rows` — recovering them is a
producer-side emission change to `backtest_v2`, not touched here.

## Verification

1. `venv/Scripts/python.exe -m pytest tests/test_oss_lab.py -q` — 11/11 stay green.
2. Normalize the real artifact through the adapter; assert on CRT-0001: `net_pnl ≈ −38.27`,
   `initial_risk = 1000.00`, `tp` presence `NOT_APPLICABLE`, `initial_risk` provenance
   marked derived-with-bounded-precision.
3. **Verify `canonical.py` consumes the normalized money-denominated PnL fields as
   intended** — read the actual implementation; do not infer denomination from the adapter
   change. (The backtest's *native* metrics are R-oriented — `total_pnl_rr_net`,
   `expectancy_rr`, `max_drawdown_rr` — and are a separate surface that this change does
   not alter.)
4. **Verify `expectancy_r` is reconstructed as `net_pnl / initial_risk` and equals the
   engine's own `pnl_rr_net` (−0.0383) to rounding** — two independent paths agreeing is
   the real correctness test.
5. Confirm no record mixes R and money within the PnL block.

## Open decision (blocking — see below)

Writing adapter code would normally trigger `CLAUDE.md` §6's SESSION LOG mandate, which
`tests/test_session_log.py` enforces (I have not checked whether it would fail on a skipped
entry). This thread has run under an explicit "no governance, no docs" instruction. That
choice is yours, not mine to assume.
