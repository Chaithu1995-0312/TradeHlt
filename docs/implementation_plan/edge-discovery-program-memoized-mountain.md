# Edge Discovery Program — Phase 0 Plan

## Context

**Why this exists.** Tradelatest today is a *single fused strategy* (CRT + Gaussian + Zone Gate + RR, hard-wired) that decides trades on ~17 instruments. The Edge Discovery Program inverts the goal: instead of *running* one strategy, build a **research platform whose job is to falsify hypotheses** and prove — with statistics, out-of-sample data, and paper trading — whether any short-duration continuation edge actually exists across a large crypto universe.

> Core stance (from the brief): **Do not assume an edge exists.** Attempt to falsify every hypothesis before promotion. An edge is real only if `E[profit after fees + slippage + risk] > 0` across large samples, multiple regimes, OOS, and paper trading.

**Decisions locked (user, 2026-06-09):**
1. **Parallel research module** — a new `src/research/` package that *imports* the proven primitives (`Candle`, `CandleLoader`, `FeaturePipeline`, the forward-walk simulator, `Universe`/`MultiSymbolScanner`) but runs its **own** hypothesis→measure→qualify→promote loop, **fully decoupled** from the live CRT spine, production config, and `promotion_manager`. No changes to `engine_runner.py`, `config_validator.py`, or `configs/production/*`.
2. **Existing 17 CSVs first** — prove the loop end-to-end on `data/*.csv`; defer the Binance 500-pair fetcher to a later milestone.
3. **Measurement + qualification first** — build MFE/MAE/time-to-failure/continuation-probability recording and the edge-qualification gate before scaling the universe. *You cannot reject weak hypotheses without first measuring them.*

**Intended outcome.** A self-contained research harness where a new hypothesis is one plugin file, every signal is forward-measured with no lookahead, weak hypotheses are auto-rejected against a random-entry baseline, and only statistically-validated hypotheses land in an append-only research ledger — all without risking the existing governed production system.

---

## What already exists (reuse, do not rebuild)

| Need | Existing asset | Path |
| --- | --- | --- |
| Candle value object | `Candle` dataclass (body_ratio, midpoint, etc.) | `src/config_layer/crt_engine_v2.py:94` |
| Deterministic CSV streaming, no-lookahead | `CandleLoader.stream()` / `.count()` | `src/runtime/backtest_v2.py:605` |
| **Forward-walk MFE/MAE/outcome/RR (no lookahead)** | `_simulate()` — already emits `outcome, rr_achieved, mfe, mae, duration_candles` | `scripts/research/opportunity_scanner.py:53` |
| 35-dim feature enrichment | `FeaturePipeline`, `CANONICAL_FEATURES` | `src/features/feature_pipeline.py`, `src/features/feature_schema.py` |
| Multi-symbol iteration (injectable engine + data fn) | `MultiSymbolScanner`, `Universe` | `src/scanner/scanner.py`, `src/scanner/universe.py` |
| OOS train/test split + degradation flag | `ForwardTester` (pattern to mirror) | `src/bitnet/forward_tester.py` |
| Temporal stability (5-split) | `StabilityChecker` (pattern to mirror) | `src/bitnet/stability_checker.py` |
| PF / expectancy formulas | `portfolio_validation.py:105` | `src/governance/portfolio_validation.py` |
| Registry/decorator pattern to copy | `@register_tool` → `REGISTRY` | `src/agent/tool_registry.py` |

**Gaps the program must build:** a hypothesis *plugin protocol* (none exists — the 4 engines are ad-hoc, no shared interface), time-to-failure + continuation-probability metrics (missing from backtest), an edge-qualification gate with significance testing + a falsification baseline (missing), and an isolated research-promotion ledger.

---

## Architecture (parallel module, dependency-only coupling)

```
                         data/*.csv  (existing 17 instruments)
                              │
              ┌───────────────▼────────────────┐
              │  CandleLoader.stream()  (reused)│
              └───────────────┬────────────────┘
                              │ Candle stream  (warmup-gated, no lookahead)
        ┌─────────────────────▼─────────────────────┐
        │  HypothesisRunner  (src/research/runner)   │
        │  for each candle past warmup:              │
        │    signals = hypothesis.detect(window,ctx) │ ◄── Hypothesis plugins (registry)
        │    for s in signals:                       │       expansion_breakout
        │      outcome = forward_walk(s, future)     │ ──►   volume_expansion
        └─────────────────────┬─────────────────────┘       liquidity_sweep
                              │ Outcome[]                    trend_continuation
        ┌─────────────────────▼─────────────────────┐       random_baseline (control)
        │  EdgeAggregator → EdgeReport               │
        │  WR · PF · expectancy · MFE/MAE dist ·     │
        │  time-to-failure · continuation prob ·     │
        │  drawdown · IS/OOS split · significance     │
        └─────────────────────┬─────────────────────┘
                              │
        ┌─────────────────────▼─────────────────────┐
        │  QualificationGate                         │
        │  reject if PF<=1.1 | E<=0 | n<min |        │
        │  OOS degradation | not > random baseline   │
        │  → PROMOTE / REJECT / INSUFFICIENT         │
        └─────────────────────┬─────────────────────┘
                              │ evidence-backed verdict
        ┌─────────────────────▼─────────────────────┐
        │  HypothesisLedger  (append-only JSONL)     │  results/research/edge_ledger.jsonl
        │  isolated from configs/promotion_log.jsonl │
        └────────────────────────────────────────────┘
```

The **measurement core is forward-walk simulation lifted from `_simulate`** — the one piece that guarantees no lookahead (it only ever reads bars *after* the signal's entry index). The live spine (`engine_runner`, `UltronRiskGate`, MT5 bridge) is never imported.

---

## Folder structure (`src/research/`)

```
src/research/
  __init__.py
  contracts.py          # Signal, Outcome, EdgeReport, Verdict dataclasses + Hypothesis Protocol
  registry.py           # @register_hypothesis decorator + HYPOTHESIS_REGISTRY  (mirrors tool_registry)
  measurement/
    forward_walk.py      # lift & generalize _simulate(); returns Outcome (adds time_to_failure, continuation)
    metrics.py           # EdgeAggregator: WR, PF, expectancy, MFE/MAE percentiles, drawdown, continuation prob
  hypotheses/
    __init__.py          # imports all modules so decorators register
    expansion_breakout.py
    volume_expansion.py     # later milestone
    liquidity_sweep.py      # later milestone
    trend_continuation.py   # later milestone
    random_baseline.py      # FALSIFICATION CONTROL — random/coin-flip entries
  runner.py             # HypothesisRunner: stream candles, call detect, forward-walk, aggregate
  qualification.py      # QualificationGate: hard rejects + OOS split + bootstrap/permutation significance
  ledger.py             # HypothesisLedger: append-only PROMOTED/REJECTED with full evidence + sha256
  cli.py                # argparse entry: research run / qualify / scan / ledger  (thin wrapper)

tests/research/
  test_forward_walk.py        # no-lookahead + outcome correctness vs hand-computed cases
  test_registry.py            # plugin registration exhaustiveness
  test_qualification.py       # gate rejects weak edge, promotes strong edge, baseline beats noise
  test_runner_determinism.py  # same CSV → identical EdgeReport

configs/research/
  research_config.json   # tunables: warmup, sl/tp atr mults, max_forward, min_samples, PF/E thresholds,
                         # oos_split, n_bootstrap, significance_alpha, universe slice
results/research/
  {hypothesis}/{run_id}/edge_report.json + outcomes.jsonl
  edge_ledger.jsonl
```

---

## Contracts / interfaces (frozen in `contracts.py`)

```python
# A hypothesis emits zero+ candidate events per bar. Pure: no forward data, no I/O.
class Hypothesis(Protocol):
    name: str
    family: str
    def detect(self, window: list[Candle], features: dict, ctx: dict) -> list["Signal"]: ...

@dataclass(frozen=True)
class Signal:
    instrument: str
    timestamp: datetime
    entry_index: int           # candle index; forward-walk may only read bars > entry_index
    direction: str             # "long" | "short"
    entry: float
    sl_atr_mult: float         # SL/TP expressed in ATR units (instrument-agnostic, crypto-safe)
    tp_atr_mult: float
    atr: float
    meta: dict                 # hypothesis telemetry (geometry, thresholds fired)

@dataclass(frozen=True)
class Outcome:                 # produced by forward_walk(); extends _simulate output
    signal: Signal
    outcome: str               # TP_HIT | SL_HIT | TIMEOUT
    rr_achieved: float
    mfe: float                 # max favorable excursion (price units)
    mae: float                 # max adverse excursion
    duration_candles: int
    time_to_tp: int | None     # bars to first TP touch (None if never)
    time_to_failure: int | None# bars until SL, i.e. survival time
    reached_1r: bool           # continuation-probability primitive

@dataclass(frozen=True)
class EdgeReport:
    hypothesis: str; instruments: list[str]
    n: int; wins: int; losses: int
    win_rate: float; profit_factor: float; expectancy_rr: float
    mfe_p50: float; mfe_p90: float; mae_p50: float; mae_p90: float
    median_time_to_failure: float; continuation_prob: float   # P(reached_1r)
    max_drawdown_rr: float
    is_metrics: dict; oos_metrics: dict; oos_retention: float  # train vs test
    baseline_delta: float; p_value: float                      # vs random_baseline
    verdict: str               # PROMOTE | REJECT | INSUFFICIENT
    reject_reasons: list[str]
```

`forward_walk()` reuses the trailing-stop logic of `_simulate` verbatim (so research RR matches the existing convention), adding `time_to_tp`, `time_to_failure`, `reached_1r`. The **registry** mirrors `@register_tool` exactly: a `@register_hypothesis(name=..., family=...)` decorator populating `HYPOTHESIS_REGISTRY: dict[str, Hypothesis]`, so a new hypothesis is *one file* with no core edits (satisfies "new hypotheses require no core engine modification").

---

## Phased roadmap & highest-leverage sequence

Maps the brief's Phase 0–7 to concrete milestones. **Sequence is measurement → falsification → only then scale**, so we never promote noise.

| # | Milestone | Brief phase | Deliverable | Gate to next |
| --- | --- | --- | --- | --- |
| **M0** | This plan + frozen contracts | Phase 0 | `contracts.py` dataclasses + this doc | contracts reviewed |
| **M1** | **Measurement core** | Phase 1/3 | `forward_walk.py` (lift `_simulate`, +time-to-failure/continuation), `metrics.py` EdgeAggregator. Tests prove no-lookahead + determinism on existing CSVs. | hand-computed outcome cases pass |
| **M2** | **Hypothesis plugin layer + falsification control** | Phase 2 | `Hypothesis` protocol, `registry.py`, `expansion_breakout.py` (lift CRT expansion geometry, stateless), **`random_baseline.py`** built *first* as the null control. | registry exhaustiveness test green |
| **M3** | **Backtest harness** | Phase 3 | `HypothesisRunner` over `Universe` of 17 CSVs → `EdgeReport` per (hypothesis, instrument) + pooled. Deterministic. | report reproduces bit-for-bit |
| **M4** | **Edge qualification (the core falsifier)** | Phase 4 | `QualificationGate`: hard rejects (PF≤1.1, E≤0, n<min), IS/OOS split (mirror `ForwardTester`), bootstrap CI + permutation test vs `random_baseline`, multiple-comparison correction. Verdict. | gate rejects baseline, promotes a planted-edge fixture |
| **M5** | **Research promotion ledger** | Phase 4 | `HypothesisLedger` append-only JSONL (PROMOTED/REJECTED + full evidence + sha256 of hypothesis+config), isolated from production `promotion_log.jsonl`. | ledger round-trips, hash verified |
| **M6** | **Universe scanner** | Phase 5 | Wire promoted hypotheses through `MultiSymbolScanner`; rank by edge strength. Then add **Binance klines fetcher** to grow 17→500 pairs (deferred per decision #2). | scan ranks; fetcher caches OHLCV |
| **M7** | **Paper-trading harness** (design now, build later) | Phase 6 | Replay-driven paper mode: stream live-style signals, log vs backtest expectation, 90-day tracker comparing realized vs predicted PF/expectancy. | 90-day live≈backtest |
| **M8** | **Automation** (design only) | Phase 7 | Promote to automated execution **only** after M4+M6+M7 all pass; reuses existing `UltronRiskGate` if ever crossed back into the live spine. | all gates green |

**First implementation slice (highest leverage): M1 → M2(control) → M3 → M4.** This yields the minimum loop that can *say "no edge"* with evidence: measure every signal, run a real hypothesis and a random baseline through identical machinery, and have the gate reject anything that doesn't beat coin-flips out-of-sample.

---

## Risks & failure modes (and mitigations)

| Risk | Mitigation built into the design |
| --- | --- |
| **Lookahead leakage** (the cardinal sin) | `forward_walk` may only read bars with index `> entry_index`; `Hypothesis.detect` receives only past `window`. Determinism test + a deliberate lookahead unit test that must fail the guard. |
| **Overfitting / multiple comparisons** (500 pairs × N hypotheses ⇒ false positives) | Mandatory IS/OOS split; permutation test vs `random_baseline`; **Benjamini–Hochberg / Bonferroni correction** across the universe sweep in `QualificationGate`. Report `p_value`, not just point metrics. |
| **No real edge, but noise looks like one** | `random_baseline` is a *first-class hypothesis* run through the same pipeline every time. PROMOTE requires `baseline_delta > 0` with significance. |
| **Survivorship bias** in the 500-pair universe | When fetcher lands (M6), include delisted/low-cap pairs; record universe snapshot + listing dates in the run header. |
| **Data quality / gaps** | Reuse `CandleLoader` OHLC-integrity validation; add gap detection to run header; reject instruments below min-candle threshold. |
| **Cost realism** | Forward-walk RR must net fees + slippage (reuse existing slippage convention); expectancy gate is on **net** RR, not gross. |
| **Regime non-stationarity** | OOS split is temporal (no shuffle); optionally mirror `StabilityChecker` 5-split to require positive edge in ≥3 chunks. |
| **Continuation-probability ambiguity** | Define precisely: `continuation_prob = P(reached_1r)` = fraction of signals whose MFE ≥ 1R before SL. Documented in `metrics.py`. |
| **Scope creep into the live system** | Hard rule: `src/research/` imports value objects + loaders only; never `engine_runner`, never writes `configs/production/*` or `promotion_log.jsonl`. Enforced by an import-lint test. |

---

## Verification

- **Unit (M1):** `pytest tests/research/test_forward_walk.py` — hand-constructed candle sequences with known TP/SL/timeout outcomes; assert `outcome`, `rr_achieved`, `mfe`, `mae`, `time_to_failure`, `reached_1r`. Include a lookahead-attempt case that must raise.
- **Determinism (M3):** run `python -m research.cli run --hypothesis expansion_breakout --data data/` twice; assert identical `edge_report.json` (byte-compare).
- **Falsification (M4):** `pytest tests/research/test_qualification.py` — (a) `random_baseline` on real CSVs must get `verdict=REJECT`; (b) a synthetic CSV with a *planted* continuation edge must get `verdict=PROMOTE`; (c) a 50-trade sample must get `INSUFFICIENT`.
- **End-to-end (M3–M5):** `python -m research.cli run --hypothesis expansion_breakout --data data/ --qualify` → produces `EdgeReport` + writes a verdict line to `results/research/edge_ledger.jsonl`; verify sha256 round-trip via `research.cli ledger --verify`.
- **Isolation:** a lint test asserting no `src/research/**` file imports `src.core.engine_runner`, `src.governance.promotion_manager`, or `src.config_layer.config_validator`.

Per CLAUDE.md §6, each implementation response appends a `📝 SESSION LOG ENTRY` to `assistant_project.md` (cannot do so now under plan mode).
