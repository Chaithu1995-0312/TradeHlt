> Created: 2026-05-23 · Updated: 2026-05-23 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Fix: Session Label Missing from TRADE_OPENED Event Metadata

## Context

The P3b session histogram always shows `UNKNOWN` for every executed trade because `session_name` is never included in the `TRADE_OPENED` event metadata dict. The session IS correctly detected one block earlier (for the FILTER_REJECTED/off-session guard at line 1622-1626) but the computed `_sess_name` variable is not forwarded into the success path's `ev_log.record("TRADE_OPENED", ...)` call at line 1647. The P3b histogram reader also uses the wrong key (`"session"` instead of `"session_name"`).

This is a read-only schema addendum — adds one key to an existing event type. No trade logic changes.

---

## Files modified (exactly 2)

| File | Change |
|---|---|
| `src/config_layer/crt_engine_v2.py` | Add `"session_name": _sess_name` to TRADE_OPENED metadata dict at line 1651 |
| `scripts/analysis/p3b_session_relax_diag.py` | Change histogram key from `"session"` to `"session_name"` at line 234 |

---

## Surgical edits

### 1. `src/config_layer/crt_engine_v2.py` — lines 1651-1658

`_sess_name` is computed at line 1622 and used by the FILTER_REJECTED branch (line 1631: `"session_name": _sess_name`). Add the same key to the TRADE_OPENED metadata:

**Before (lines 1651-1658):**
```python
                            metadata={
                                "id": trade.id,
                                "S_score": final_S,
                                "sl": trade.sl_price,
                                "tp1": trade.tp1_price,
                                "tp2": trade.tp2_price,
                                "risk_pct": trade.risk_pct,
                            },
```

**After:**
```python
                            metadata={
                                "id": trade.id,
                                "session_name": _sess_name,
                                "S_score": final_S,
                                "sl": trade.sl_price,
                                "tp1": trade.tp1_price,
                                "tp2": trade.tp2_price,
                                "risk_pct": trade.risk_pct,
                            },
```

Key name `session_name` matches the convention already used in FILTER_REJECTED events (line 1631) — no new naming introduced.

### 2. `scripts/analysis/p3b_session_relax_diag.py` — line 234

**Before:**
```python
        sess = e.get("metadata", {}).get("session", "UNKNOWN")
```

**After:**
```python
        sess = e.get("metadata", {}).get("session_name", "UNKNOWN")
```

---

## What does NOT change

- No trade logic, filter logic, or execution path is modified.
- No existing JSONL keys are removed (pure additive change).
- No tests assert TRADE_OPENED metadata fields — zero test updates needed.
- `docs/SCHEMAS.md` does not document the TRADE_OPENED event shape — no doc update needed.
- P4 script computes session via its own monkeypatch; can optionally be simplified later but not in scope here.
- `_sess_name` variable already exists in scope at the call site — no new computation.

---

## Verification

```bash
# Run P3b on any instrument — session histogram should now show named sessions
python scripts/analysis/p3b_session_relax_diag.py --instrument ETHUSDT

# Expected output for "Session histogram of executed trades (patched run)":
#   LONDON         : N
#   NEWYORK        : N
#   OVERLAP        : N
#   ASIA           : N   (if --add-sessions ASIA,OFF_SESSION used)
#   OFF_SESSION    : N
# NOT: UNKNOWN     : 31
```

---

# Parameterise All P-Scripts with --instrument (P3a, P3b, P3c, P3c1, P4)

## Context

All five diagnostic scripts under `scripts/analysis/` (P3a, P3b, P3c, P3c1, P4) share three hardcoded top-level constants: `CSV_PATH`, `INSTRUMENT = "ETHUSDT"`, `OUTPUT_DIR`. P3b and P3c additionally have hardcoded ETHUSDT-specific baseline values (BASELINE_TRADES=4, BASELINE_AVG_RR=0.39, BASELINE_TOTAL_PNL=1.57). To run the same diagnostics on BTC/SOL/BNB without editing files each time, all five scripts need argparse with `--instrument` as a required argument. The data folder now has `{SYMBOL}_M15.csv` for every symbol so no XLSX conversion is needed in the common path (but an XLSX fallback is added for future coverage).

## Files modified (exactly 5)

| Script | Hardcoded to remove | Script-specific new args |
|---|---|---|
| `scripts/analysis/p3a_zone_attribution_diag.py` | CSV_PATH, INSTRUMENT, OUTPUT_DIR | none |
| `scripts/analysis/p3b_session_relax_diag.py` | CSV_PATH, INSTRUMENT, OUTPUT_DIR, BASELINE_TRADES, BASELINE_AVG_RR, BASELINE_TOTAL_PNL | `--add-sessions`, `--min-r-exp`, `--max-dd` |
| `scripts/analysis/p3c_zone_relax_diag.py` | CSV_PATH, INSTRUMENT, OUTPUT_DIR, ZONE_RELAX_PCT, BASELINE_TRADES, BASELINE_AVG_RR, BASELINE_TOTAL_PNL | `--zone-relax-pct` |
| `scripts/analysis/p3c1_build_trade_audit.py` | CSV_PATH, INSTRUMENT, OUTPUT_DIR | none |
| `scripts/analysis/p4_execution_intent_attribution.py` | CSV_PATH, INSTRUMENT, OUTPUT_DIR | none |

No changes to any file under `src/`. Diagnostics only.

---

## Argparse interface (per script)

### Common args (all 5 scripts)

```
--instrument   SYMBOL       Required. E.g. BTCUSDT, SOLUSDT, BNBUSDT, ETHUSDT
--csv          PATH         Optional. Explicit path to data file (CSV or XLSX).
                             Auto-resolved if omitted (see resolution order below).
--output-dir   PATH         Default: results
```

### P3b-specific

```
--add-sessions  ASIA,OFF_SESSION   Comma-separated sessions to add to allowed_sessions
                                    Default: ASIA,OFF_SESSION
--min-r-exp     0.39               Quality gate: min R expectancy on ADDED trades
--max-dd        0.0132             Quality gate: max drawdown (decimal)
```

### P3c-specific

```
--zone-relax-pct  0.60             Replaces the editable ZONE_RELAX_PCT constant
                                    (second run: pass 0.67)
```

### Example invocations

```bash
python scripts/analysis/p3a_zone_attribution_diag.py --instrument BTCUSDT
python scripts/analysis/p3b_session_relax_diag.py   --instrument SOLUSDT
python scripts/analysis/p3b_session_relax_diag.py   --instrument BNBUSDT --min-r-exp 0.20
python scripts/analysis/p3c_zone_relax_diag.py      --instrument BTCUSDT --zone-relax-pct 0.67
python scripts/analysis/p3c1_build_trade_audit.py   --instrument SOLUSDT
python scripts/analysis/p4_execution_intent_attribution.py --instrument BNBUSDT
```

---

## Data file resolution (shared helper — same logic in all 5 scripts)

Add a `_resolve_data_file(instrument: str, csv_override: str | None) -> str` function near the top of each script:

```python
def _resolve_data_file(instrument: str, csv_override: str | None) -> str:
    if csv_override:
        p = Path(csv_override)
        if not p.exists():
            sys.exit(f"[ERROR] --csv path not found: {csv_override}")
        return str(p)
    candidates = [
        _ROOT / "data" / f"{instrument}_M15.csv",
        _ROOT / "data" / f"{instrument}_M15_2year.csv",
        _ROOT / "data" / f"{instrument}_M15_2year.xlsx",
        _ROOT / "data" / f"{instrument}_M15.xlsx",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    checked = "\n  ".join(str(c) for c in candidates)
    sys.exit(f"[ERROR] No data file found for {instrument}. Checked:\n  {checked}")
```

If the resolved path ends with `.xlsx`, use an inline `_xlsx_stream()` + `_xlsx_count()` pair (using `openpyxl.load_workbook(read_only=True)`) that yields the same `Candle` objects as `CandleLoader.stream()`. Since all symbols now have `*_M15.csv`, this path is a future-proofing fallback only.

---

## P3b — two-run auto-baseline (replace BASELINE_* constants)

P3b currently hardcodes ETHUSDT baseline values (BASELINE_TRADES=4, BASELINE_TOTAL_PNL=1.57). Replace with an automatic two-run approach inside the same script invocation:

**Run 0 (baseline):** instantiate `BacktestRunner` with the original (unpatched) CRTConfig and the instrument's data file. Call `runner.run(...)`. Capture `baseline_metrics`.

**Run 1 (patched):** apply `dataclasses.replace(crt_cfg, allowed_sessions=patched_sessions)`. Run again. Capture `patched_metrics`.

Delta computation replaces all `BASELINE_*` references:
```python
added_trades     = patched_metrics.approved_trades - baseline_metrics.approved_trades
added_pnl        = patched_metrics.total_pnl_rr_net - baseline_metrics.total_pnl_rr_net
r_expectancy_added = added_pnl / max(added_trades, 1)
```

Run 0 uses `overrides={"diagnostic": "P3b_baseline", "instrument": args.instrument}`.
Run 1 uses `overrides={"diagnostic": "P3b_session_relax", "instrument": args.instrument}`.

The funnel baseline column in the report is drawn from Run 0's event log, not hardcoded constants. The report format and verdict logic are otherwise identical.

## P3c — two-run auto-baseline + configurable zone-relax-pct

Same two-run approach as P3b. ZONE_RELAX_PCT becomes `args.zone_relax_pct` (float, default 0.60). The BASELINE_* constants are replaced by Run 0's computed metrics.

---

## Structural edit pattern (identical for all 5 scripts)

1. **Add `import argparse` and `import sys`** at the top (alongside existing imports).
2. **Replace the 3-line config block** (CSV_PATH / INSTRUMENT / OUTPUT_DIR) with `_resolve_data_file()` helper + argparse parse call.
3. **Thread `args.instrument` and `args.output_dir`** through to `BacktestConfig`, `CandleLoader`, `BacktestRunner`, `runner.run()`, and the events-JSONL glob.
4. **P3b/P3c only:** wrap the existing single-run block into a `def _run_one(crt_cfg, label) -> BacktestMetrics` helper, call it twice, compute delta.
5. **P3b/P3c only:** replace `BASELINE_TRADES`, `BASELINE_TOTAL_PNL`, `BASELINE_AVG_RR` references with computed delta values.
6. **P3c only:** replace `ZONE_RELAX_PCT` with `args.zone_relax_pct`.
7. **Update each script's docstring** `Usage:` block with the new argparse interface.

---

## What does NOT change (in any script)

- The monkeypatch mechanism (`dataclasses.replace` on CRTConfig, EventLogger / ExecutionEngine / CRTEngine monkeypatching) — untouched.
- The events JSONL parsing, funnel table, FILTER_REJECTED breakdown, trade metrics, criteria table, and verdict logic — layout identical.
- `load_prod_config_from_registry(PROD_VERSION, args.instrument)` — this call already accepts instrument.
- `MultiInstrumentRunner.INSTRUMENT_PIP.get(args.instrument, 0.0001)` — unchanged.
- No changes to any file under `src/`.

---

## Verification (run in order)

```bash
# 1. ETHUSDT — should produce same verdict as before for each script
python scripts/analysis/p3a_zone_attribution_diag.py  --instrument ETHUSDT
python scripts/analysis/p3b_session_relax_diag.py    --instrument ETHUSDT
python scripts/analysis/p3c_zone_relax_diag.py       --instrument ETHUSDT --zone-relax-pct 0.60
python scripts/analysis/p3c1_build_trade_audit.py    --instrument ETHUSDT
python scripts/analysis/p4_execution_intent_attribution.py --instrument ETHUSDT

# 2. BTCUSDT — main failing symbol
python scripts/analysis/p3b_session_relax_diag.py    --instrument BTCUSDT
python scripts/analysis/p3c_zone_relax_diag.py       --instrument BTCUSDT --zone-relax-pct 0.60

# 3. SOLUSDT + BNBUSDT — check session gate adds trades
python scripts/analysis/p3b_session_relax_diag.py    --instrument SOLUSDT
python scripts/analysis/p3b_session_relax_diag.py    --instrument BNBUSDT

# 4. Explicit csv override test
python scripts/analysis/p3b_session_relax_diag.py --instrument BTCUSDT --csv data/BTCUSDT_M15.csv

# 5. Error path — bad instrument
python scripts/analysis/p3b_session_relax_diag.py --instrument FAKECOIN  # should exit with clear message
```

Expected for BTC/SOL/BNB: Run 0 produces the known trade counts (2/5/8). Run 1 should add session-unblocked trades. PASS/MIXED/NONE verdict driven by the computed delta.
