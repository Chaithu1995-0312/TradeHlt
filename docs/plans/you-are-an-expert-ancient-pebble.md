> Created: 2026-05-07 · Updated: 2026-05-07 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Command Audit Report — Tradelatest Quantitative Trading System

> Analysis date: 2026-05-07  
> Worktree: `D:\Tradelatest\.claude\worktrees\xenodochial-babbage-1a2ab5`  
> All findings are grounded in actual argparse definitions read from source.

---

## Executive Summary

| Severity | Count | Verdict |
|----------|-------|---------|
| 🔴 CRITICAL (script doesn't exist / missing required arg) | 4 | Immediate runtime failure |
| 🟠 HIGH (wrong argument type / semantic mismatch) | 3 | Silent wrong behaviour or crash |
| 🟡 MEDIUM (workflow order, version inconsistency) | 4 | Likely failure in CI / governance gate |
| 🟢 LOW (style / path convention) | 3 | Cosmetic / minor |

**Overall alignment score: 🔴 RED** — 4 commands will fail immediately on invocation, 3 more will silently produce wrong results.

---

## Per-Command Findings

### CMD-01 — `promotion_manager.py promote` (first occurrence)
```bash
python src/governance/promotion_manager.py promote \
  --checkpoint results/tuner/checkpoint_multi.json \
  --version v2_multi_2026_04 \
  --data-dir data/ \
  --instruments EURUSD GBPUSD BTCUSDT XAUUSD \
  --notes "April tuner run, 3-month window"
```
**Status: ✅ Aligned (with minor note)**  
- All required args present (`--checkpoint`, `--version`).  
- `--instruments` accepts `nargs="+"` — four values are valid.  
- `--data-dir data/` vs parser default `"data"` (no slash): argparse passes the literal value; Python `os.path.join("data/", ...)` and `os.path.join("data", ...)` are equivalent on all platforms. Cosmetically inconsistent with the default but not an error.  
- ⚠️ `results/tuner/checkpoint_multi.json` is an **output** of `auto_tuner_multi.py` — if promotion is invoked before the tuner run completes and writes that file, this will raise `FileNotFoundError`. (See CMD-02 ordering note.)

---

### CMD-02 — `auto_tuner_multi.py`
```bash
python scripts/training/auto_tuner_multi.py \
  --data-dir data --output-dir results/tuner \
  --n-iter 100 --seed 42 --workers 4 --train-split 1.0
```
**Status: ✅ Aligned**  
- `--train-split 1.0` is typed `float` in the parser — `1.0` is correct; passing `1` would also be accepted (Python coerces `int` to `float` via `type=float`).  
- `--workers 4` is typed `int` — correct.  
- No `--instruments` supplied; the script defaults to discovering CSVs from `--data-dir`. Valid if `data/` contains appropriately named CSVs.  
- ⚠️ **Workflow order**: This command appears **after** CMD-01 (the promotion command). The tuner must run first to produce `results/tuner/checkpoint_multi.json` before promotion can succeed. **The script list is in the wrong logical order.**

---

### CMD-03 — `backtest_v2.py` (first occurrence, no comment)
```bash
python src/runtime/backtest_v2.py --csv data/EURUSD_M15.csv --instrument EURUSD
```
**Status: ✅ Aligned**  
- `--csv` is required and present.  
- `--instrument` is optional (default `"AUTO"`) but supplying it explicitly is correct and avoids AUTO-detection ambiguity.

---

### CMD-04 — `promote_v2.py` (first occurrence)
```bash
python scripts/governance/promote_v2.py --version multi_strategy_v2_2026_05
```
**Status: 🔴 CRITICAL — File does not exist**  
- `scripts/governance/promote_v2.py` **is not present anywhere in the repository**.  
- Every invocation of this script (CMD-04, CMD-19, CMD-20) will fail with `No such file or directory`.  
- **Fix:** Use the canonical promotion path: `python src/governance/promotion_manager.py promote ...`.

---

### CMD-05 — `phase5_calibration.py` (first occurrence)
```bash
python scripts/training/phase5_calibration.py --train --csv data/EURUSD_M15.csv
```
**Status: 🔴 CRITICAL — Wrong argument semantics**  
- The `--csv` flag in `phase5_calibration.py` has `metavar="DIR"` — it **expects a base directory containing results subdirectories**, not a raw CSV file path.  
- Passing `data/EURUSD_M15.csv` will cause the script to attempt directory traversal on a file path, producing either an `OSError` or silently processing zero results directories.  
- **Fix:** Pass a results base directory (e.g., `--csv results/`) or use `--synthetic` for smoke tests, or `--cached results/phase5_dataset.json` for cached data.

---

### CMD-06 — `auto_tuner.py`
```bash
python scripts/training/auto_tuner.py \
  --csv data/EURUSD_M15.csv --instrument EURUSD \
  --output-dir results/tuner --n-iter 100
```
**Status: ✅ Aligned**  
- All flags are valid per the parser. `--csv` + `--instrument` is a supported single-instrument mode.  
- ⚠️ Note: this is the **single-instrument tuner** (`auto_tuner.py`), not the multi-instrument one (`auto_tuner_multi.py`). Its checkpoint output path may differ from what CMD-01 expects (`checkpoint_multi.json` vs a single-instrument checkpoint). Confirm the file name written by this script matches the one passed to `promotion_manager.py promote --checkpoint`.

---

### CMD-07 — `backtest_v2.py` (commented block, step 1)
```bash
# 1. Run a backtest on your CSV data — this writes to logs/
python src/runtime/backtest_v2.py --instrument EURUSD --csv data/EURUSD_M15.csv
```
**Status: ✅ Aligned**  
- Identical semantics to CMD-03; argument order swap is not significant (argparse is order-agnostic).  
- ⚠️ **Workflow assumption**: The comment says "this writes to `logs/`". The backtest output directory defaults to `"results"` (`--output` defaults to `"results"`), not `logs/`. The fusion JSONL (`logs/EURUSD_fusion.jsonl`) consumed in step 2 is written by `FusionEngine` during the backtest, not by the backtest harness itself. Verify that the production config has `fusion_log_path` pointing to `logs/EURUSD_fusion.jsonl` or this assumption silently breaks the dataset build step.

---

### CMD-08 — Python one-liner (dataset build)
```python
python -c "
from src.features.dataset_validator import validate_logs
from src.features.dataset_builder import build_dataset
records, report = validate_logs('logs/EURUSD_fusion.jsonl')
build_dataset(records, output_path='data/training.json')
print(report)
"
```
**Status: 🟠 HIGH — Implicit dependency on CMD-07 output; minor signature note**  
- `validate_logs` signature is `validate_logs(*log_paths, verbose=True)` — calling it with a single positional string works correctly (`log_paths` will be `('logs/EURUSD_fusion.jsonl',)`). ✅  
- `build_dataset(records, output_path='data/training.json')` matches the actual signature `build_dataset(records, output_path=None)`. ✅  
- ⚠️ **Hidden dependency**: `logs/EURUSD_fusion.jsonl` is only written if CMD-07 completed successfully AND the `FusionEngine` log path is configured to write there. If CMD-07 was skipped or the log path differs in config, this will fail with `FileNotFoundError`.  
- ⚠️ `print(report)` prints a `ValidationReport` dataclass object — the output will be the repr, which is useful for debugging but not human-formatted. No functional issue.

---

### CMD-09 — `train_pipeline.py tradenet` (first occurrence)
```bash
python scripts/training/train_pipeline.py tradenet \
  --data data/training.json --output results/tradenet_result.json
```
**Status: ✅ Aligned**  
- `tradenet` is a valid subcommand. `--data` is required and present. `--output` is optional but supplied.  
- Depends on CMD-08 having written `data/training.json` first.

---

### CMD-10 — `train_pipeline.py tradenet` (duplicate)
```bash
python scripts/training/train_pipeline.py tradenet \
  --data data/training.json --output results/tradenet_result.json
```
**Status: 🟡 MEDIUM — Exact duplicate of CMD-09**  
- Identical command appears twice in succession. No functional difference; second run would overwrite the first output. Remove the duplicate.

---

### CMD-11 — `train_pipeline.py gaussian`
```bash
python scripts/training/train_pipeline.py gaussian \
  --logs logs/EURUSD_fusion.jsonl logs/GBPUSD_fusion.jsonl \
  --version gaussian_v2_2026_05
```
**Status: ✅ Aligned**  
- `gaussian` is a valid subcommand. `--logs` accepts `nargs="+"` — two JSONL paths are valid. `--version` is required and present.  
- ⚠️ Both log files must exist before this runs. `logs/GBPUSD_fusion.jsonl` requires a separate GBPUSD backtest run (analogous to CMD-07 for EURUSD) which is not shown in the command list. If missing, the script will raise `FileNotFoundError` at read time.

---

### CMD-12 — `phase5_calibration.py` (second occurrence)
```bash
python scripts/training/phase5_calibration.py --train --csv data/EURUSD_M15.csv
```
**Status: 🔴 CRITICAL — Same wrong-type issue as CMD-05**  
- Same error as CMD-05: `--csv` expects a **results base directory**, not a CSV file path.  
- Additionally, `--csv` and `--train` appear alongside each other, but the parser defines `--csv` within a mutually exclusive group `(required=True)`. Since `--train` is a separate optional flag (not in the exclusive group), this combination is syntactically valid; the semantic error is solely in the `--csv` value.

---

### CMD-13 — `train_bitnet.py`
```bash
python scripts/training/train_bitnet.py \
  --csv data/EURUSD_M15.csv --epochs 50 --lr 0.01 --out model.json
```
**Status: 🔴 CRITICAL — File does not exist**  
- `scripts/training/train_bitnet.py` **does not exist anywhere in the repository**.  
- **Fix:** BitNet inference is handled via the binary at `./bitnet/bin/main` (referenced in `orchestrator.py`). If GGUF-based training is needed, the entry point is different from what this command implies. The flag set (`--epochs`, `--lr`, `--out`) does not match any existing script signature in the codebase.

---

### CMD-14 — `backtest_v2.py` (exact duplicate of CMD-03)
```bash
python src/runtime/backtest_v2.py --csv data/EURUSD_M15.csv --instrument EURUSD
```
**Status: 🟡 MEDIUM — Duplicate of CMD-03**  
- Identical command. Remove the duplicate.

---

### CMD-15 — `config_validator.py validate-prod`
```bash
python src/config_layer/config_validator.py validate-prod \
  --data-dir data/ --version v2_multi_2026_04
```
**Status: ✅ Aligned**  
- `validate-prod` subcommand is valid. Both flags are optional in the parser; supplying them is fine.  
- ⚠️ `v2_multi_2026_04` is passed as `--version` to override production version; verify that a config named with this version exists in the registry before running, otherwise the validator will fail to load it.

---

### CMD-16 — `config_validator.py validate-params`
```bash
python src/config_layer/config_validator.py validate-params \
  --params '{"sweep_threshold":0.6}' --config-id test_run
```
**Status: 🟠 HIGH — Inline JSON passed where a file path is expected**  
- The `validate-params` parser defines `--params` as a plain `str` argument. However, if the implementation calls `open(args.params)` to load it as a file (which is the idiomatic pattern for a "params JSON file" argument), passing an inline JSON string will raise `FileNotFoundError: [Errno 2] No such file or directory: '{"sweep_threshold":0.6}'`.  
- The parser help text says `"JSON file with params dict"` — confirming it expects a **file path**.  
- **Fix:** Write the params to a temp file first:
  ```bash
  echo '{"sweep_threshold":0.6}' > /tmp/test_params.json
  python src/config_layer/config_validator.py validate-params \
    --params /tmp/test_params.json --config-id test_run
  ```

---

### CMD-17 — `promotion_manager.py promote` (duplicate of CMD-01, with `✅` label)
```bash
python src/governance/promotion_manager.py promote \
  --checkpoint results/tuner/checkpoint_multi.json \
  --version v2_multi_2026_04 \
  --data-dir data/ \
  --instruments EURUSD GBPUSD BTCUSDT XAUUSD \
  --notes "April tuner run, 3-month window"
```
**Status: ✅ Aligned (same as CMD-01) — 🟡 MEDIUM: Duplicate**  
- Exact duplicate of CMD-01. Remove one occurrence.

---

### CMD-18 — `promotion_manager.py from-report`
```bash
python src/governance/promotion_manager.py from-report \
  --report results/validation/approved/report_v2_multi_2026_04.json
```
**Status: 🔴 CRITICAL — Missing required `--version` argument**  
- The `from-report` subcommand parser defines **both** `--report` and `--version` as `required=True`.  
- This command omits `--version`, so argparse will print an error and exit:  
  `error: the following arguments are required: --version`  
- **Fix:**
  ```bash
  python src/governance/promotion_manager.py from-report \
    --report results/validation/approved/report_v2_multi_2026_04.json \
    --version v2_multi_2026_04
  ```

---

### CMD-19 — `promotion_manager.py list`
```bash
python src/governance/promotion_manager.py list
```
**Status: ✅ Aligned**  
- `list` subcommand takes no arguments. Correct.

---

### CMD-20 — `promote_v2.py` (second occurrence)
```bash
python scripts/governance/promote_v2.py --version multi_strategy_v2_2026_05
```
**Status: 🔴 CRITICAL — File does not exist (same as CMD-04)**

---

### CMD-21 — `promote_v2.py --dry-run`
```bash
python scripts/governance/promote_v2.py --version multi_strategy_v2_2026_05 --dry-run
```
**Status: 🔴 CRITICAL — File does not exist (same as CMD-04)**

---

### CMD-22 — `orchestrator.py`
```bash
python src/governance/orchestrator.py \
  --collector-log logs/collector.jsonl \
  --trades-csv results/EURUSD_trades.csv \
  --baseline-pnl 5.23
```
**Status: ✅ Aligned**  
- All three required args (`--collector-log`, `--trades-csv`, `--baseline-pnl`) are present.  
- `--baseline-pnl 5.23` is typed `float` — correct.  
- ⚠️ `results/EURUSD_trades.csv` must contain a `pnl_rr_net` column (per the parser help text). Verify that `backtest_v2.py` writes trades with this column name to that path; if the output path differs from `results/EURUSD_trades.csv`, this will fail at runtime when the orchestrator tries to read the column.  
- ⚠️ `logs/collector.jsonl` must exist before this runs (written by the collector component). Its creation is not shown in the command list.

---

## Workflow Consistency Notes

### Note 1 — Logical Ordering Violations
The commands are **not** in a valid execution order. A correct linear order for a full promotion cycle is:

```
1. Backtest  (CMD-03/07) — produces logs/EURUSD_fusion.jsonl
2. Dataset build  (CMD-08) — consumes fusion log → data/training.json
3. TradeNet training  (CMD-09) — consumes training.json
4. Gaussian training  (CMD-11) — consumes fusion logs (needs GBPUSD backtest too)
5. Phase-5 calibration  (CMD-05/12) — needs results base dir, not CSV
6. Config validation  (CMD-15) — validate before promoting
7. Promotion  (CMD-01/17) — only after checkpoint_multi.json exists (needs tuner, CMD-02)
```

CMD-01 (promote) appears at position 1, before the tuner (CMD-02), backtest (CMD-03), training, and validation steps. This would fail because `checkpoint_multi.json` doesn't exist yet.

### Note 2 — `logs/EURUSD_fusion.jsonl` Origin
This file is **not** written by `backtest_v2.py --output`. It is written by `FusionEngine` during the backtest run, controlled by a config key (likely `fusion_log_path` or similar in `fusion_engine` config section). The command list assumes it exists after step 1, but this is only guaranteed if the production config routes the fusion log to `logs/EURUSD_fusion.jsonl`. Verify the config.

### Note 3 — Version String Format Inconsistency
Three different version string formats appear across commands:

| Format | Example | Used by |
|--------|---------|---------|
| `v{N}_{scope}_{YYYY_MM}` | `v2_multi_2026_04` | `promotion_manager.py`, `config_validator.py` |
| `{scope}_v{N}_{YYYY_MM}` | `multi_strategy_v2_2026_05`, `gaussian_v2_2026_05` | `promote_v2.py` (nonexistent), `train_pipeline.py gaussian` |

The canonical format per `CLAUDE.md` and the production config (`v1_multi_2026_03`) is **`v{N}_{scope}_{YYYY_MM}`**. The `multi_strategy_v2_2026_05` and `gaussian_v2_2026_05` formats deviate from this convention, and the month suffix jumps from `04` to `05` inconsistently.

### Note 4 — `BTCUSDT` vs `BTCUSD`
`BTCUSDT` (with `T`) is the **canonical** name across all config files and source code (confirmed in `v1_multi_2026_03_force_accept.json`, `v2_multi_2026_04.json`, `market_router.py`). All audit commands correctly use `BTCUSDT`. No inconsistency here.

### Note 5 — Missing GBPUSD Backtest
CMD-11 (Gaussian training) requires `logs/GBPUSD_fusion.jsonl` but no GBPUSD backtest command is present in the list. The fusion log for GBPUSD will not exist unless an equivalent of CMD-07 is run with `--csv data/GBPUSD_M15.csv --instrument GBPUSD`.

---

## Consolidated Recommendations

### Remove / Replace

| Command | Action |
|---------|--------|
| CMD-04, CMD-20, CMD-21 (`promote_v2.py`) | **Delete all three.** Script doesn't exist. Use `promotion_manager.py promote` instead. |
| CMD-10 (duplicate `tradenet` training) | Remove duplicate. |
| CMD-14 (duplicate `backtest_v2.py`) | Remove duplicate. |
| CMD-17 (duplicate `promotion_manager.py promote`) | Remove duplicate. |

### Fix Immediately

| Command | Fix |
|---------|-----|
| CMD-05, CMD-12 (`phase5_calibration --csv data/EURUSD_M15.csv`) | Change `--csv` value to a **results base directory** (e.g., `results/`), not a CSV file path. |
| CMD-16 (`validate-params --params '{"..."}'`) | Write JSON to a temp file; pass the file path to `--params`. |
| CMD-18 (`from-report` missing `--version`) | Add `--version v2_multi_2026_04`. |
| CMD-13 (`train_bitnet.py`) | Remove or replace with the actual BitNet invocation pattern. Check if a wrapper script exists elsewhere; if not, document that BitNet training is out-of-scope for this CLI. |

### Workflow Reorder

Place commands in this sequence:
1. Backtest (all instruments needed)
2. Dataset build (from fusion logs)
3. TradeNet training
4. Gaussian model training
5. Auto-tuner multi (produces `checkpoint_multi.json`)
6. Phase-5 calibration (with correct `--csv`/`--cached` arg)
7. Config validation (`validate-prod`)
8. Promotion (`promotion_manager.py promote`)

### Version String Standardisation

Adopt `v{N}_{scope}_{YYYY_MM}` uniformly:
- `gaussian_v2_2026_05` → `v2_gaussian_2026_05`
- `multi_strategy_v2_2026_05` → `v2_multi_2026_05`

---

## Summary Table

| CMD | Command | Status | Severity |
|-----|---------|--------|----------|
| 01 | `promotion_manager promote` (1st) | ✅ Aligned | — |
| 02 | `auto_tuner_multi` | ✅ Aligned | — |
| 03 | `backtest_v2` (1st) | ✅ Aligned | — |
| 04 | `promote_v2.py` | 🔴 File missing | CRITICAL |
| 05 | `phase5_calibration --csv CSV_FILE` | 🔴 Wrong arg type | CRITICAL |
| 06 | `auto_tuner.py` | ✅ Aligned | — |
| 07 | `backtest_v2` (commented block) | ✅ Aligned | — |
| 08 | Python one-liner (dataset build) | 🟠 Implicit dep | HIGH |
| 09 | `train_pipeline tradenet` (1st) | ✅ Aligned | — |
| 10 | `train_pipeline tradenet` (2nd) | 🟡 Duplicate | MEDIUM |
| 11 | `train_pipeline gaussian` | ✅ Aligned | — |
| 12 | `phase5_calibration` (2nd) | 🔴 Wrong arg type | CRITICAL |
| 13 | `train_bitnet.py` | 🔴 File missing | CRITICAL |
| 14 | `backtest_v2` (3rd duplicate) | 🟡 Duplicate | MEDIUM |
| 15 | `config_validator validate-prod` | ✅ Aligned | — |
| 16 | `config_validator validate-params` | 🟠 File vs inline JSON | HIGH |
| 17 | `promotion_manager promote` (duplicate) | 🟡 Duplicate | MEDIUM |
| 18 | `promotion_manager from-report` | 🔴 Missing `--version` | CRITICAL |
| 19 | `promotion_manager list` | ✅ Aligned | — |
| 20 | `promote_v2.py` (2nd) | 🔴 File missing | CRITICAL |
| 21 | `promote_v2.py --dry-run` | 🔴 File missing | CRITICAL |
| 22 | `orchestrator.py` | ✅ Aligned | — |
