# Cost-model identity stamping (backtest_v2 G1/G2 + trade record)

> Status: **PLAN (draft)** — doc authority only. No source/config change is made by this file.
> Runnable after the mandatory governance gate (REPOSITORY_CONSTRUCTION_PROTOCOL, §10).
> Context: the cost-model discussion (F-082/F-087/F-088/F-101) — the gap is that **which cost
> model and which R-denominator produced a given `pnl_rr_net` are not on the trade record.**

## 1. Problem

`pnl_rr_net` on every trade row is cost-blind and denominator-blind. Recovering the cost
requires cross-referencing a *sidecar* (`logs/config_dumps/<run_id>_config.json`) against
source constants. There is no `cost_model_id`, `cost_model_params_hash`, or
`risk_denominator_id`. A scalar `cost_model_bps` exists in `src/utils/run_manifest.py` /
`src/utils/validation_contract.py`, but (a) it is a scalar, not an identity; (b) those are the
research/tool path, not the `backtest_v2.py` output path (`summary.json`, `trades.csv`,
`events.jsonl`); (c) it is not stamped per-trade.

For `run_20260916_101942_XAUUSD` this means: the run's cost is `simulated_spread_pct=0.0002`
+ `slippage_atr_fraction=0.1` (seed 42) — a fourth cost state the research taxonomy
(`flat_12bps` / SEM-015 / SEM-016) does not name — and no artifact says so.

## 2. Goal

Make the cost surface **declared, versioned, and stamped** at run and per-trade level,
**without** changing any PnL math. Pure additive metadata (backward compatible).

- A `cost_model_id` + `cost_model_params_hash` declared on the run config.
- A `risk_denominator_id` naming the R unit each `pnl_rr_*` was divided by.
- All three stamped on every `trades.csv` row alongside `config_version`, and on
  `summary.json` at the run level.

## 3. Current anchor points (verified 2026-09-16)

| Concern | File:line | Current state |
|---|---|---|
| Cost knobs in config | `src/runtime/backtest_v2.py` `BacktestConfig` (L148–208); `from_prod_config` reads `slippage_enabled/fraction/seed`, `simulated_spread_pct`, `pip_size` (L253–265) | scalars, not identity |
| R-denominator used | L1176 `risk_pips = abs(rec.entry_price_fill - rec.sl_price) / self.pip_size`; PnL L1177–1178 | unnamed unit |
| `TradeRecord` | L321–400 | no cost/denominator fields |
| CSV column builder | `to_csv_rows` L1227–1297; `config_version` L1294, `shadow_used` L1295 | → append 3 fields here |
| `run_id` column append | `_write_trades` L1714–1727 (last key; DictWriter header from `rows[0].keys()`) | unchanged |
| Run-level summary | `_write_summary` L1705–1712 (stamps `run_id` L1708) | → add cost identity |
| Slippage model | `self.slip` = `SlippageModel` (entry/exit slips, seed) | identity source |
| Existing manifest scalar | `run_manifest.py` REQUIRED_FIELDS `cost_model_bps`; `validation_contract.py` `_cmp("cost_model_bps")` | scalar only |

## 4. Design (what to add)

### 4.1 Cost-model identity (new, declared on config)

Enumerated ids (exhaustive for the **backtest_v2** path; research ids reserved):

| `cost_model_id` | Meaning |
|---|---|
| `backtest_g1g2_v2` | production backtest: `spread = 2bps of close`, `slip ~ U(0, 0.1×ATR)`, `seed` (default backtest cost) |
| `backtest_zero_cost` | `slippage_enabled=false` and `simulated_spread_pct==0` |
| `flat_12bps` | `research.costs.CostModel` — not reachable by backtest_v2 today (reserved) |
| `metals_mt5_v1` | `research.costs.xau_measured_cost_model()` SEM-015 (reserved; needs wiring, §9) |

```
cost_model_params_hash = sha256( canonical_json({
    slippage_enabled, slippage_atr_fraction, slippage_seed,
    simulated_spread_pct, pip_size
}))  # 16 hex chars; deterministic, fail-closed (absent knob -> raises)
```

### 4.2 `risk_denominator_id`

For the backtest path the denominator is exactly L1176. Enumerate:

| id | Radicot | Where |
|---|---|---|
| `entry_fill_to_sl` | `|entry_price_fill − sl_price| / pip_size` | backtest_v2 (this plan) |
| `entry_raw_to_sl` | `|entry_price_raw − sl_price| / pip_size` | research `forward_walk` planner object (reserved) |
| `atr_1_0` | `1.0 × ATR_abs` | research ATR arm (reserved) |

The id must be a string, never re-derived from other columns at read time.

### 4.3 Defaults & back-compat

- New `TradeRecord` fields default `""` so old record loads stay valid.
- If `cost_model_id` key is absent from config, **derive** it from the existing cost knobs
  (fail-closed: `slippage_enabled or simulated_spread_pct>0` → `backtest_g1g2_v2`; both off →
  `backtest_zero_cost`; missing required knob → raise, never silent default — mirrors
  `from_prod_config`'s existing required-key behaviour).
## 5. Implementation checklist

- [ ] **`BacktestConfig`** (L148): add fields `cost_model_id: str = ""`, `cost_model_params_hash: str = ""`.
- [ ] **`from_prod_config`** (L253): compute both from the four cost knobs via module-level helpers
      `_cost_model_id(...)` / `_cost_params_hash(...)` (pure, testable).
- [ ] **`TradeRecord`** (L321): add `cost_model_id`, `cost_model_params_hash`, `risk_denominator_id`
      with `""` defaults.
- [ ] **`TradeJournal.on_trade_opened`** (L1066): accept + store the three ids on `rec` (threaded
      from the runner cfg like `sl_atr_buffer` at L1031).
- [ ] **constant `RISK_DENOM_BACKTEST = "entry_fill_to_sl"`** set on `rec.risk_denominator_id` at open.
- [ ] **`to_csv_rows`** (L1227): add the three columns next to `config_version` (L1294);
      append-only, never re-order existing columns (same discipline as `run_id` append L1719–1722).
- [ ] **`_write_summary`** (L1705): add `cost_model_id`, `cost_model_params_hash`,
      `risk_denominator_id` at the summary level (mirroring `run_id` stamp at L1708).
- [ ] **`_write_report`** (`TRADE COSTS` block): one line — `Cost model applied: <id>`.
- [ ] **(research path, separate)** add `cost_model_id`/`cost_model_params_hash` to
      `run_manifest.py` REQUIRED_FIELDS and `validation_contract._cmp`; keep `cost_model_bps`
      as scalar complement. No per-trade stamp there (no per-trade CSV consumer yet).

## 6. Schema / derived values

- `cost_r` stays recoverable as `pnl_rr_raw − pnl_rr_net` (no new field).
- No PnL formula changes. Net behavior difference: zero (purely additive metadata).

## 7. Tests

- [ ] `tests/test_backtest_config.py` (or nearest): `cost_model_params_hash` deterministic
      given the same four knobs; changes when any knob changes.
- [ ] `tests/test_backtest_output.py`: `trades.csv` rows carry all three new fields, constant
      across rows, equal to the values also present in `summary.json`.
- [ ] `tests/test_backtest_output.py`: old-record load (missing fields) yields `""`/derived id,
      no crash (back-compat).
- [ ] Fixture: `simulated_spread_pct=0.0002, slippage_atr_fraction=0.1, slippage_seed=42`
## 11. Resolved decisions (act-mode post-review, 2026-09-16) — the plan now carries the answers

These resolutions were decided during review and DURING implementation; they are recorded in the
impact manifest `docs/governance/build_manifests/CH-cost-model-identity-stamp.impact.json` and are
repeated here so the plan doc is self-contained (the plan is the spec, not the manifest alone).

1. **`pip_size` ownership — (b), the R-denominator.** From source (`backtest_v2.py` L1176):
   `risk_pips = |entry_fill − sl| / pip_size` is the exact denominator `pnl_rr_*` uses. Cost in
   PRICE units derives from `simulated_spread_pct` (spread_half) and `slippage_atr_fraction`
   (slippage), neither of which reads `pip_size`. So `pip_size` is **excluded from
   `cost_model_params_hash`** and belongs to `risk_denominator_id`. Cross-consistency: a
   `pip_size` change bumps `risk_denominator_id` (new version), never the cost hash.

2. **`risk_denominator_id` versioning — (a).** `risk_denominator_id` values are versioned; when
   the denominator formula changes, a NEW id is emitted and old ids remain valid for historical
   rows. **Silent semantic drift of an existing id is forbidden.** Current: `entry_fill_to_sl__v1`.

3. **`cost_model_bps` disposition — leave in place, and this change does not touch it.**
   `run_manifest.py` / `validation_contract.py` are byte-unchanged. `cost_model_bps` remains the
   research-path scalar identity; `cost_model_id` is the production-path identity. Reconciling
   them is out of scope; F-082's scope note ("the finding applies to the research cost world
   only") is the interim record.

4. **`backtest_zero_cost` — (iii) reserve-only.** Derivation is single-valued: whenever the four
   knobs are present, `cost_model_id == "backtest_g1g2_v2"` unconditionally — including a
   zero-cost config (which yields a distinct `cost_model_params_hash`). `backtest_zero_cost` is
   declared but NEVER generated. Test asserts no current `configs/production/*.json` `backtest`
   section maps to it.

5. **Strict reads (negative test made a contract, not a docstring).** `from_prod_config`
   already `_require`s the four cost knobs (missing key → `KeyError`). `_cost_params_hash` is a
   pure function over parsed knobs. Test `test_missing_any_cost_knob_raises` asserts that
   removing ANY of the four knobs raises — never `""` / a default id / an empty hash.
      → `cost_model_id == "backtest_g1g2_v2"` (reproduces this run).
- [ ] `tests/test_run_manifest.py` + `tests/test_validation_contract.py`: new required fields
      enforced (H1/H3) when the research path adopts them.

## 8. Acceptance

1. Rerun the `run_20260916_101942_XAUUSD` config path → `trades.csv` and `summary.json` state
   `cost_model_id=backtest_g1g2_v2`, `cost_model_params_hash=<stamped>`,
   `risk_denominator_id=entry_fill_to_sl`.
2. A reader of the CSV can reconstruct the cost without the sidecar config dump.
3. `git diff` shows **zero** PnL/value drift vs a baseline rerun (byte-identical `pnl_rr_*`).

## 9. Out of scope / future

- Wiring `ComponentCostModel` (SEM-015) / `AdverseFill` (SEM-016) **into** backtest_v2 so
  `flat_12bps` / `metals_mt5_v1` become reachable on the production path (then the stamped
  `cost_model_id` actually switches the charged surface).
- A config schema `cost_model` block (enumerated arms + version), deferred until SEM-015 is
  ported; until then the ids are derived, not declared.

## 10. Executing this plan (mandatory governance gate)

Per AGENTS.md / CLAUDE.md this is a **behavioral/config/source** change; before touching `src/`
or `configs/`:

1. Classify the change against `docs/governance/change_contracts.json`.
2. Produce a `BUILD_IMPACT_MANIFEST` (STOP on blocking UNKNOWN).
3. Implement through canonical authorities (ontology → registry → implementations); no local
   formula math.
4. Validate completion: `python scripts/governance/construction_protocol.py validate-completion <manifest>`
   and `python scripts/governance/construction_protocol.py check`.
5. Run the §7 test suite; confirm §8 acceptance.