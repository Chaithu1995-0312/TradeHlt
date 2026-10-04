# JARVIS CRT Handover v3 — Repo Snapshot

**Source document:** `C:\Users\Hi\Downloads\Jarvis_CRT_Handover.docx`
**Patch level:** v3
**Reference dataset:** BTCUSDT M15, 49 candles (2024-01-01 00:00 → 12:15 UTC)
**Incorporated on:** 2026-04-17

This file is a diffable, grep-able snapshot of the original `.docx` handover so
the doc's reference math lives next to the code that consumes it. The original
`.docx` remains the canonical source — this markdown is for in-repo reference.

---

## What was incorporated

| Item | Where it lives | Notes |
|------|----------------|-------|
| Sweep type taxonomy (TYPE-A/B/C/D) — geometry classifier | [`src/config_layer/crt_sweep_taxonomy.py`](../../src/config_layer/crt_sweep_taxonomy.py) | Pure-function, zero dependency on production scoring. |
| Sweep archetype METADATA on `SweepEvent` | [`src/config_layer/crt_engine_v2.py`](../../src/config_layer/crt_engine_v2.py) `SweepEvent` + `RangeDetector.detect_sweep` | Two new optional `None`-default fields: `sweep_type`, `sweep_label`. Diagnostics only. |
| Doc-faithful reference harness (Patch v3 with idx-guard reorder fix) | [`tools/btcusdt_crt_v3_replay.py`](../../tools/btcusdt_crt_v3_replay.py) | Standalone CLI. Emits `btcusdt_crt_v3_output.json` per §10 schema. |
| Ground-truth regression test (Candles 23, 38, 43, 13) | [`tests/test_btcusdt_crt_v3_handover.py`](../../tests/test_btcusdt_crt_v3_handover.py) | Pytest. Skips if BTCUSDT fixture CSV missing; unit tests for taxonomy always run. |

## What was intentionally NOT incorporated

| Item | Reason |
|------|--------|
| Doc's `random()*0.05/0.06/0.08` jitter into production heads | CLAUDE.md governance: production scoring must be deterministic. Jitter exists only inside the standalone reference harness for ground-truth reproduction. |
| Replacing production scoring with the doc's 4-head BitNet formulas | Production uses an EURCAD-calibrated empirical Gaussian (`crt_gaussian_scorer.py`) that is the source of truth. The doc's heads were calibrated on a 49-candle BTCUSDT sample — too small to migrate the multi-instrument production stack to. |
| Lowering LLM trigger to `fusion >= 0.46` | Production contract is the `[0.45, 0.65]` uncertainty band in `FusionConfig` and `llm_inference_client.py`. Changing it would require re-running the promotion validators per the governance flow in CLAUDE.md. |
| The doc's idx-guard reorder fix in `RangeDetector.detect_sweep` | The production engine uses range-boundary sweep detection, not geometry-first. There is no idx<4 guard blocking geometric classification. The fix is applied **only** in the standalone reference harness, where it is correct per the doc. |

---

## Key constants captured (for cross-reference)

### §4.2 — Phase weights (`pw`)
| Phase        | pw   |
|--------------|------|
| SCANNING     | 0.00 |
| RANGE        | 0.10 |
| RETEST       | 0.28 |
| SWEEP        | 0.44 |
| CONFIRMATION | 0.54 |
| EXECUTION    | 0.62 |

### §5.3 — Sweep taxonomy
| Type   | Label          | Trigger                                                                  |
|--------|----------------|--------------------------------------------------------------------------|
| TYPE-A | PINBAR BEAR    | upper<0.02 AND lower>0.35 AND body>0.40 AND bearish                      |
| TYPE-B | SHOOTING STAR  | upper>0.40 AND lower<0.12 AND body>0.30 AND bearish                      |
| TYPE-C | HAMMER         | lower>0.40 AND upper<0.12 AND body>0.30 AND bullish                      |
| TYPE-D | PINBAR BULL    | lower<0.02 AND upper>0.35 AND body>0.40 AND bullish                      |

### §7.7 — Fusion weights
`fusion = 0.30·crt + 0.25·gaussian + 0.25·zone + 0.20·rr`
(Identical to `FusionConfig` weights at `src/core/fusion_engine.py:73-76` — no change required.)

### §15 — Ground-truth fusion scores
| Candle | Phase / Type             | Fusion |
|--------|--------------------------|--------|
| 13     | EXECUTION                | 0.5460 |
| 23     | SWEEP TYPE-A PINBAR BEAR | 0.5580 |
| 38     | SWEEP TYPE-D PINBAR BULL | 0.5954 |
| 43     | SWEEP TYPE-B SHOOTING STAR | 0.5355 |

These are asserted (±0.02 tolerance) by `tests/test_btcusdt_crt_v3_handover.py`.

---

## Reproducing the doc's worked examples

```bash
# 1) place the 49-candle BTCUSDT fixture
#    columns: timestamp,open,high,low,close,volume
#    period:  2024-01-01 00:00 → 12:15 UTC
mv your_btcusdt_m15_csv.csv data/btcusdt_m15_2024-01-01.csv

# 2) run the reference harness
python tools/btcusdt_crt_v3_replay.py \
    --csv data/btcusdt_m15_2024-01-01.csv \
    --out results/btcusdt_crt_v3_output.json

# 3) verify against ground-truth (also runs the taxonomy unit tests)
python -m pytest tests/test_btcusdt_crt_v3_handover.py -v
```
