> Created: 2026-05-12 · Updated: 2026-05-12 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Timing Instrumentation for `opportunity_scanner.py`

## Context
The user produced a detailed theoretical time-estimate for `opportunity_scanner.py` (16–25s on an i7-7500U for 121K-row EURUSD M15 CSV). The goal is to add `time.perf_counter()` checkpoints to `scan()` so the wall-clock breakdown can be compared against the estimate in a single run.

No new abstractions needed — the existing pattern in `src/strategies/strategy_orchestrator.py:225,241` (`t0 = time.perf_counter()` → `elapsed_ms = (time.perf_counter() - t0) * 1000.0`) is the template to follow.

## Critical File

- **`scripts/research/opportunity_scanner.py`** — only file to change

## Change: Add 4 `perf_counter` checkpoints in `scan()`

The three phases are:
- **Phase 1 — CSV load:** `_load_csv()` (line 117)
- **Phase 2 — FeaturePipeline:** `pipeline.run()` (line 119)
- **Phase 3 — simulation + I/O:** main `for` loop lines 134–173 (I/O is interleaved, so phases 2+3 are timed as one block, then phase 1 carve-out gives us a clean split)

### Imports to add (line 26, after `import sys`)
```python
import time
```

### Instrumentation in `scan()` — surgical edits only

```python
def scan(...) -> Path:
    t_start = time.perf_counter()
    df = _load_csv(csv_path)
    t_load = time.perf_counter()

    pipeline = FeaturePipeline(df)
    enriched_df, _ = pipeline.run()
    t_pipeline = time.perf_counter()

    # ... existing validation + setup unchanged ...

    with out_path.open("w", encoding="utf-8") as fout:
        for idx in range(start, n - 1):
            # ... existing loop body unchanged ...
    t_loop = time.perf_counter()

    logger.info(
        "OpportunityScanner: wrote %s | long=%d short=%d | TP_HIT=%d SL_HIT=%d TIMEOUT=%d",
        out_path, counts["long"], counts["short"],
        counts["TP_HIT"], counts["SL_HIT"], counts["TIMEOUT"],
    )
    logger.info(
        "Timing | csv_load=%.2fs | feature_pipeline=%.2fs | sim+io=%.2fs | total=%.2fs",
        t_load - t_start,
        t_pipeline - t_load,
        t_loop - t_pipeline,
        t_loop - t_start,
    )
    return out_path
```

No changes to `_simulate`, `_load_csv`, `main`, or any other file.

## Verification

Run with the EURUSD CSV used in the estimate:
```
python scripts/research/opportunity_scanner.py \
  --csv data/EURUSD_M15.csv \
  --instrument EURUSD \
  --max-forward-candles 40 \
  --warmup-candles 30 \
  --output-dir logs
```

Expected log output (two lines):
```
... | OpportunityScanner | OpportunityScanner: wrote logs/opportunities_EURUSD.jsonl | ...
... | OpportunityScanner | Timing | csv_load=0.XX s | feature_pipeline=X.XX s | sim+io=XX.XX s | total=XX.XX s
```

Compare against estimate:
| Phase | Estimate | Actual |
|-------|----------|--------|
| csv_load | ~0.5s | ? |
| feature_pipeline | 3–5s | ? |
| sim+io | 12–20s | ? |
| **total** | **16–25s** | **?** |
