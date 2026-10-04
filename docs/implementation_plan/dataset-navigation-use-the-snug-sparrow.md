# Plan: Configurable Mother-Range / Inside-Close Detector (XAUUSD M15)

## Context

New OHLCV-derived market-structure concept, generalized from the user's 4-hour formulation to
an **arbitrary configurable block size `x`**:

1. Group M15 bars into blocks of `x` bars (`x=16` → 4-hour, `x=96` → "1 day", any `x`).
2. Block 1 is the **mother range**: `H₁ = max(high)`, `L₁ = min(low)`, `R₁ = H₁ − L₁`.
3. Block 2's **last close** `C₂` is tested: `inside = L₁ ≤ C₂ ≤ H₁`.
4. **`InsideScore = (C₂ − L₁) / (H₁ − L₁)`** — 0.0 = closed at mother low, 1.0 = at mother high.
5. Optional **big-mother filter** so only genuine expansions qualify: `R₁ > k·ATR` or
   `R₁ > P₉₀(trailing R)`.

Thesis: a large expansion followed by a close back *inside* it means the expansion was not
accepted — absorption / failed continuation / balance returning after imbalance.

Fully causal: every quantity uses only bars at or before `C₂`'s own bar.

### Pre-verified — the concept fires (measured on the real 47,275-bar dataset)

| Blocking | Blocks | Inside-close (all) | Inside-close (**big mother only**) |
|---|---|---|---|
| positional `x=16` | 2,954 | 51.8% | **67.9%** (n=321) |
| calendar 4H | 3,095 | 51.7% | **71.8%** (n=351) |
| positional `x=96` | 492 | 50.3% | **68.1%** (n=69) |
| calendar 24H | 516 | 50.9% | **56.8%** (n=74) |

Baseline is a coin-flip (~51%); **the big-mother filter lifts it to 68–72%** — a ~16–20pp
lift. The hypothesis is real and worth instrumenting. `InsideScore` median ≈ 0.53–0.60 when
inside (closes cluster mid-range, not at the edges).

### Data-truth correction the spec needs (verified)

**This dataset's trading day is 92 bars, not 96.** Measured: `bars/day` median **92** (496 of
516 days); the **00:00–00:45 UTC hour is absent** (75-minute daily gap, 394 occurrences;
weekend gaps 2,955 min). A day runs 01:00 → 23:45 UTC.

Consequences, which the implementation must handle rather than paper over:
- `x=96` is **not** "1 day" here. Positional 96-bar blocks absorb 4 bars of the next day and
  the phase **drifts 4 bars per day, compounding**.
- `92 mod 16 = 12`, so positional 16-bar blocks also do not stay aligned to wall-clock 4-hour
  boundaries across days.

### Design decision taken (no user round-trip needed)

Rather than force a choice, **both blocking modes are implemented on one code path** and
reported side by side, because the divergence is itself a finding (positional `x=96` 68.1% vs
calendar 24H 56.8% — 11pp apart on the headline number):

- **`positional`** — every `x` consecutive rows. Always exactly `x` bars. Drifts vs wall-clock.
  This is what the `x` parameter literally means.
- **`calendar`** — anchored to real UTC boundaries derived from `x` (`x=16` → 4H boundaries,
  `x=96` → daily). Matches what a trader sees on a chart. Bar counts vary (3–16 observed) at
  the daily gap and weekend edges.

## Approach

Single new read-only script: **`scripts/analysis/mother_range_inside_close.py`**.
No `src/` module, no config change, no ontology registration — this is a research-stage
descriptive measurement, following the precedent of the two scripts already built this session
([semantic_layer_validation.py](scripts/analysis/semantic_layer_validation.py),
[mature_semantic_audit.py](scripts/analysis/mature_semantic_audit.py)).

### CLI

```
--csv          data/mt5/XAUUSD_M15.csv
--block-bars   x (repeatable; default: 16 96) -- the configurable block size
--blocking     both | positional | calendar   (default both)
--big-rule     percentile | atr_mult | none   (default percentile)
--big-pct      90        (P90 of trailing block ranges)
--big-k        1.5       (for atr_mult: R1 > k*ATR)
--lookback     100       (trailing window for the big-mother threshold)
--output-dir   results/mother_range
```

### Traceability (the explicit requirement)

Every block pair emits a fully hand-verifiable record — CSV + JSONL:

`x` · `blocking_mode` · `pair_id` · block-1 `[row_start, row_end]` + `[ts_start, ts_end]` +
`n_bars` · **`H1` with the row index & timestamp of the bar that set it (argmax)** ·
**`L1` with the argmin bar's index & timestamp** · `R1` · block-2 `[row_start, row_end]` ·
`C2` with its row index & timestamp · `inside` · `InsideScore` · `big_threshold_value` ·
`big_rule_used` · `big_pass` · `max_source_row_index` (the causality proof: must be ≤ `C2`'s
row index).

Anyone can take a `pair_id`, open the CSV at the cited row range, and re-derive `H1`/`L1`/`C2`
by hand.

### Causality discipline

The big-mother threshold is computed from **prior blocks only** (`.shift(1)` on the trailing
rolling quantile / ATR), never including the block being judged — unambiguously causal, no
self-referential threshold. Asserted in-script.

### Outputs

- `results/mother_range/mother_range_x{X}_{mode}_blocks.csv` — the per-block trace
- `results/mother_range/mother_range_stats.json` — statistics across every `x` × mode
- `results/mother_range/mother_range_report.md` — the readable comparison: inside-close rate
  (all vs big-filtered), lift over baseline, `InsideScore` distribution, block-count and
  bars-per-block sanity, the positional-vs-calendar divergence, and worked hand-verifiable
  examples (largest mother range; deepest inside close; a clean failure/outside case).

### Critical files

- `scripts/analysis/mother_range_inside_close.py` — the only new file
- [data/mt5/XAUUSD_M15.csv](data/mt5/XAUUSD_M15.csv) — source (gitignored; 47,275 bars)
- [scripts/analysis/semantic_layer_validation.py](scripts/analysis/semantic_layer_validation.py) — structural precedent (arg parsing, `_native()` JSON coercion, SHA-256 provenance header, rule-selected examples)

## Verification

- **Determinism**: two runs → byte-identical outputs excluding the timestamp header.
- **Block integrity**: positional blocks assert exactly `x` bars each; calendar blocks report
  their true bar counts and never silently pad.
- **Causality assertion**: for every record, `max_source_row_index ≤ C2_row_index` — fails
  loudly otherwise. Plus an explicit check that the big-threshold at block *i* is computed
  only from blocks `< i`.
- **Hand re-derivation**: pick 3 records at random, independently recompute `H1`/`L1`/`C2`
  straight from the raw CSV rows at the cited indices, and confirm exact match.
- **Reproduce the pre-verified numbers**: positional `x=16` must yield 2,954 blocks / 51.8%
  baseline / 67.9% big-filtered; calendar 4H → 3,095 / 51.7% / 71.8%. A deviation means the
  implementation drifted from the probe and must be explained, not accepted.
- **Boundary cases**: `x` larger than a day, `x=1`, and `x` not dividing the dataset evenly —
  confirm the trailing partial block is dropped, never silently truncated into a short block.
