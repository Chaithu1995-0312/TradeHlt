# Pipeline Linkage — "Spine-as-Hypothesis"

> Backconstruct a research forensics/qualification run whose hypothesis **is** the full
> production decision spine — so the backtest's every layer and all its data are measured
> under the brutal research truth standard.

**Status:** shipped 2026-06-11. Additive, Pipeline-B–only. Spine untouched.

---

## 1. Why

The BNBUSDT M15 conclusions ("volatility has memory, direction doesn't"; expansion edge
net E[R] = −0.439R; 0 BH-survivors) came **only** from `src/research/` running *toy*
hypotheses (`ExpansionBreakout`, `MeanReversion`) — pure `detect(window) -> Signal` functions
that never touch the production decision spine. The full production backtest
(`backtest_v2.BacktestRunner` → `EngineRunner` → CRT/Gaussian/ZoneGate/RR → Fusion →
RegimeGovernor → Decision → ExecutionPlanner → UltronRiskGate) had **never** been measured
under the research truth standard: `intrabar_fixed` exits, 12 bps round-trip cost,
beats-control, OOS retention, permutation + Benjamini-Hochberg FDR.

This links the two pipelines so we can answer, apples-to-apples: **does the real 8-layer
system produce a *qualified* edge, or does it die under honest exits + cost + controls just
like the toy hypotheses?** — and run the same loss-mechanism forensics on its real trades.

## 2. The key insight

Both surfaces are signal generators with the **same shape**:

| | Research `Hypothesis.detect()` | Production spine entry |
|---|---|---|
| input | `window: list[Candle]`, `features`, `ctx` | candle stream + 35-dim `CANONICAL_FEATURES` |
| output | `list[Signal]` (entry, dir, `sl_atr_mult`, `tp_atr_mult`, `atr`) | `TRADE_OPENED` w/ price-based entry/SL/TP at `EXECUTE` |

So the spine **is** a hypothesis. We wrap it as one and feed it into the *unchanged* research
machinery (`HypothesisRunner` forward-walk, `EdgeAggregator`, the 7-gate `QualificationGate`,
`forensics.py`). All of those already speak `Signal`/`Outcome` — **zero changes** required.

## 3. How it works

```
ProductionSpineSource.entries(instrument)        # src/research/adapters/spine_signal_source.py
   └─ runs the REAL BacktestRunner once (deterministic, invariant #1)
   └─ harvests {instrument}_trades.csv  →  {research_index: SpineEntry(entry, dir, risk, reward)}

SpineHypothesis.detect(window, features, ctx)    # src/research/hypotheses/spine_hypothesis.py
   └─ PURE lookup: is window[-1].index a committed entry?  (no re-running the stateful spine)
   └─ converts spine price geometry -> ATR multiples using research atr(window)
   └─ returns Signal  →  research forward-walk / aggregator / gates / forensics (UNCHANGED)
```

Running the **real** `BacktestRunner` (not a re-implementation of its loop) is deliberate:
it forces all layers + all 35-dim features through the actual spine, makes the entries *be*
the backtest's trades (exact equivalence, nothing to drift), and reuses the file-backed
`{instrument}_trades.csv` artifact.

### Stateful spine vs. pure `detect()`
`detect()` is called per-bar and must be pure/no-lookahead, but the spine is a stateful
stream. We reconcile by **precomputing**: the source runs the spine once and caches entries
by index; `detect()` is then a pure dict lookup. The cache is keyed by instrument, so the
single registry-singleton hypothesis serves `run`, `qualify`, and forensics in one process
with no recomputation or cross-instrument state leak.

### Geometry (price → ATR multiples)
The spine plans absolute prices; research `Signal` uses ATR multiples. `detect()` computes
the **same** research `atr(window)` the toy hypotheses use and sets
`sl_atr_mult = |entry−sl| / atr`, `tp_atr_mult = |tp1−entry| / atr`. Then
`risk_distance = sl_atr_mult * atr` round-trips **byte-exact** to the spine's price distance,
while the multiple stays comparable across hypotheses (and keeps forensics' ATR-normalized
trend proxy meaningful). This requires `apply_signal_defaults=false` in the spine config so
the runner does not overwrite the multiples.

### INDEX CONTRACT (the off-by-one that bites)
`backtest_v2.py:1627` increments `candle_idx` **before** the warmup skip, so the trades CSV
`candle_idx` (a.k.a. `candle_open`) is **1-based** over the `CandleLoader` stream, while the
research runner assigns `c.index = i` **0-based**. Therefore:

```
research_index = candle_idx (CSV) − 1
```

`detect()` additionally cross-checks the entry's `opened_at` against `window[-1].timestamp`
and raises on mismatch — a regression guard against this exact off-by-one.

## 4. Isolation (the one hard constraint)

The coupling points strictly **down** the decision flow (Goal invariant #5; service-boundary
hard rule). Research imports the spine as a proven primitive (exactly as it already imports
`CandleLoader`), in **local scope**, behind the `SpineSignalSource` Protocol. The spine never
imports — and never learns of — research. Enforced by
`tests/research/test_spine_hypothesis.py::test_spine_does_not_import_research`, which scans
`src/{core,engines,config_layer,runtime}` for any `import research`.

## 5. Run it

```bash
# Qualification (does the spine PROMOTE/REJECT/INSUFFICIENT through all 7 gates?)
PYTHONPATH=src python -m research.cli run     --hypothesis spine --controls \
    --config configs/research/research_config_spine.json --out results/research
PYTHONPATH=src python -m research.cli qualify \
    --config configs/research/research_config_spine.json --out results/research/qualification

# Forensics (loss decomposition on the spine's real trades) — same driver, spine config
PYTHONPATH=src python scripts/research/bnbusdt_forensics.py --behaviors spine \
    --config configs/research/research_config_spine.json
```

Outputs: deterministic `edge_report.json` (spine NET WR/PF/E vs the same controls the toy
hypotheses faced), `qualification_report.json` (7-gate verdict), and the forensic report
(intrabar-damage matrix, loss mechanisms, opportunity profile, regime/session cuts).

## 6. Governance scoring (Five Questions)

1. **Deterministic?** ✓ — spine is deterministic (invariant #1); edge_report carries no
   wall-clock; verified byte-identical across two runs.
2. **Comparable across runs?** ✓ — same truth standard (`intrabar_fixed`, 12 bps) as the toy
   hypotheses, so the spine result sits in the same ledger.
3. **Auditable later?** ✓ — `config_sha256` + the persisted `{instrument}_trades.csv` under
   `results/research/_spine_entries/`.
4. **LLM-reasonable?** ✓ — one composite hypothesis named `spine`, plain `Signal` outputs.
5. **Execution authority isolated?** ✓ — coupling points down only; spine cannot be triggered
   by research; isolation test enforces it.

## 7. Limitations / follow-ups

- `hypothesis_sha256` hashes only the `SpineHypothesis` class source, not the prod config or
  spine code; provenance of the spine version rests on the active `PROD_VERSION` +
  `config_sha256`. A future step could fold `PROD_VERSION` into the report.
- Single TP: research `Signal` carries one TP; we use `tp1`. `tp2` is retained in `meta`.
- **Version selection:** `spine.prod_version` is load-bearing — the source measures that exact
  registry version by temporarily setting the module-global `PROD_VERSION` (in both
  `production_config` and `backtest_v2`) for the run and restoring it in `finally`. It **never**
  rewrites the governance pointer `ACTIVE_VERSION`. The entries cache is keyed by
  `(instrument, version)` so v2 and v4 coexist in one process. Guarded by
  `test_prod_version_restored_after_run`.
- When `Trd-M4` lands the abstract `BacktestRunner` interface, `ProductionSpineSource` should
  depend on that interface instead of importing `runtime.backtest_v2` directly.

## 8. Active-version caveat (2026-06-11)

`F-007` (`docs/current-findings.md:123`) asserts active = `v4_multi_2026_06`, but the live
`ACTIVE_VERSION` file and the newer `CURRENT_STATE.md` (2026-06-10) both say
`v2_multi_2026_04 - deepdeektry` on the `patch` branch.

**Root cause (confirmed 2026-06-11):** `v4_multi_2026_06.json` carries CRTConfig keys
(`tp3_enabled`, `tp3_atr_multiplier`, `score_component_weights`) that the `patch` branch's
`crt_engine_v2.CRTConfig` does not define — `ConfigBuilder` rejects them with
`unknown override key(s)`. v4 was promoted against a **newer engine schema (TP3 +
component-weighted scoring)**; the `patch` working tree is on the **pre-TP3 code line** and
physically cannot load v4. This is *why* `ACTIVE_VERSION` here is v2. The shipped spine config
therefore measures v2 (the runnable version on this branch); to measure the v4 spine, check out
the code line where v4 was promoted (with the matching engine), then set
`spine.prod_version = v4_multi_2026_06`. The version-selection machinery itself is correct and
needs no change.

## 9. v2-vs-v3 spine comparison (2026-06-11)

v4 is unrunnable here, so we measured **v3_multi_2026_06** (loads; untracked/ungoverned) against v2.
Both deterministic (byte-identical ×2). BNBUSDT, intrabar_fixed, 12 bps, tp2 (2R):

| version | n | WR | PF(net) | E(net) | qualify verdict | top loss-mechanism |
|---|---|---|---|---|---|---|
| **v2** (governed) | 15 | 40% | **0.805** | **−0.145R** | INSUFFICIENT (n<30) | plain_stop_loss 88% |
| **v3** (orphan) | 39 | 41% | 0.561 | **−0.400R** | REJECT (E<0) | plain_stop_loss 84% |
| random_uniform (control) | — | — | — | −0.415R | (winning control) | — |

**Finding:** v3 opens `allowed_sessions` to ASIA + OFF_SESSION (and tightens
displacement/body/sweep), yielding **2.6× the trades (15→39) but collapsing expectancy −0.145R →
−0.400R** — down to control/random level. v2's selective session filter
(LONDON/NEWYORK/OVERLAP) is doing the real work; v3's session expansion **destroys the
entry-quality edge**. This is a clean end-to-end (full-spine, honest-exit) confirmation of F-003
(session policy is the lever) and F-015 (throughput relaxation is value-destroying at a bad rate)
— previously seen only at the detection/toy layer, now measured through all 8 layers.

**Config-pinning fix (load-bearing):** the spine source reads `spine.prod_version` from the file
named by `RESEARCH_SPINE_CONFIG`. `cmd_run` / `cmd_qualify` / the forensics driver now set that
env to their `--config`, so `--config` is authoritative. (A first v3 run silently re-measured v2
because the source defaulted to `research_config_spine.json`; caught via a missing
`BNBUSDT__v3_*` entries dir + impossible byte-identical results despite 6 differing CRTConfig
fields.) When running the spine outside the CLI, set `RESEARCH_SPINE_CONFIG` to match.
