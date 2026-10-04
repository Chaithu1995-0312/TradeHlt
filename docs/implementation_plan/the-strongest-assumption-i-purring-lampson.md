# Program 3 — Higher-Timeframe Directional Ontology (H1/H4 resampler + M4 gate)

## Context

A user critique ("Phase 7 — Belief Falsification Audit") challenged the assumption that the
trading paradigm is dead, arguing the conclusion rests on a narrow envelope: BNBUSDT/crypto-majors
**M15** only. The critique is epistemically correct **and already partly encoded** in the repo —
Program 1 is `KILLED` *only* for "next-bar direction · M15 · crypto-majors" with an explicit
**untouched frontier** (FX/equities/commodities · H1/H4/D · non-directional targets) recorded as the
sanctioned reopen path ([program-1-closure-2026-06-13.md:69-86](docs/analysis/program-1-closure-2026-06-13.md);
Funding Ledger reopen conditions, [current-findings.md:432](docs/current-findings.md)).

Three of the critique's *specific* claims conflict with the living record and must NOT be encoded
as new "unknowns" (CLAUDE.md §6.2 rule 3 — never silently resolve a conflict):

| Critique claim | Record (authoritative) | Disposition |
|---|---|---|
| F-021 "+ASIA edge found, rejected only by governance" → INCONCLUSIVE | Those are STALE close-only/in-sample numbers; under intrabar_touch+70/30 OOS V2 flips negative, no challenger clears retention≥0.70+G1; ΔE is *entirely* the (incumbent) session filter (F-017, F-021) | **Stale** — failed OOS statistically, not just policy |
| "No Hurst/autocorrelation in repo" (Unanswered Q#4) | Already measured: H_atr=0.885, H_returns=0.527, ARCH-LM reject (F-020 / `process_diagnostics.py`) | **Already answered** |
| "Widen stop to 2.5 ATR — untested" (Exit Q#3) | F-025 ran full 42-cell SL{0.5–3.0}×TP{1.0–5.0}; best 3.0×5.0 still E_oos −0.27; re-running is named "archaeology, out-of-bounds" | **Answered + forbidden** |

**Decision (user, this session):** the highest-value untouched axis to attack first is **timeframe**
(the "M15 is too noisy" hypothesis), via an **H1/H4 resampler**, pre-registered as a NEW ontology
(**Program 3**) — not a parameter pass on Program 1. Exit/cost is off the table (falsified +
out-of-bounds). Docs fold into the existing truth system (one scannable matrix), not 3 new root docs.

**Intended outcome:** a deterministic M15→H1/H4 OHLCV resampler + a pre-registered HTF qualification
run through the *existing* M4 gate, yielding either a genuine HTF lead (→ F-010-style follow-up) or a
clean, in-scope falsification (→ new F-id + Program 3 verdict). Either way the "paradigm vs envelope"
question gets a real answer instead of an assumption.

## Doctrine guardrails (must hold)
- **New ontology, not archaeology.** Different *horizon* = a separate program per Program 1 reopen
  conditions. Pre-register BEFORE running (hypothesis, universe, truth standard, advance/kill criteria).
- **Governing truth standard reused verbatim:** `forward_walk(intrabar_fixed)` + `CostModel` 12bps +
  IS / 70-30 OOS + BH — via the existing `research.qualification` core. Add NO new statistics.
- **Additive + isolated to `src/research/` + `scripts/research/` + `configs/research/`.** No edits to
  `runner.py`, `forward_walk.py`, `qualification.py`, or any live-spine module.
- **Determinism is the headline property** (matches the edge_report discipline): byte-identical
  re-runs for both the resampled CSVs and the qualify JSON body (no wall-clock in content).

## Build (all additive)

### 1. `src/research/resample.py` — deterministic OHLCV resampler
- Pure function `resample(candles: list[Candle], rule: str) -> list[Candle]` for `rule in {"H1","H4"}`.
- **Calendar-boundary bucketing** (deterministic, gap/weekend-safe): bucket key = timestamp floored to
  the hour (H1) / 4-hour boundary aligned to 00:00 UTC (H4). Aggregate children: `open=first.open`,
  `high=max(high)`, `low=min(low)`, `close=last.close`, `volume=sum`, `timestamp=bucket start`,
  reindex `index` to stream position. Reuses the `Candle` dataclass
  ([crt_engine_v2.py:95](src/config_layer/crt_engine_v2.py)).
- **Causality:** emit a bucket only after it closes (next bucket's first child arrives); **drop the
  trailing partial bucket**. No lookahead is introduced — downstream `forward_walk` keeps its own
  no-lookahead guard on the resampled stream.
- CSV writer emitting the canonical OHLCV schema that `CandleLoader` re-reads (timestamp/open/high/
  low/close/volume), so the rest of the harness consumes resampled files with zero changes.

### 2. `scripts/research/build_resampled_data.py` — thin CLI
- Read each crypto-major M15 CSV via the proven `CandleLoader` ([backtest_v2.py:626](src/runtime/backtest_v2.py)),
  call `resample`, write `data/resampled/{INST}_{TF}.csv`. Sorted iteration, no wall-clock in content.
- Scope: `BNBUSDT, ETHUSDT, BTCUSDT, SOLUSDT` (same majors as qualify_majors), TF ∈ {H1, H4}.

### 3. `configs/research/research_config_htf_majors.json` + `research_config_spine_htf_majors.json`
- Copies of `research_config_majors.json` / `research_config_spine_majors.json` repointed at
  `data/resampled` with pattern `*_{TF}.csv`. **Horizon pre-registration choice (documented in the
  config + Program 3 note):** keep harness `warmup/window_size/max_forward` in **bars** (each timeframe
  is its own world; ATR and bar-relative horizon scale naturally) — the standard ontology test. The
  wall-clock implication (40 H1 bars = 40h vs 10h at M15) is recorded explicitly so it is a *chosen*,
  not accidental, parameter. Default chosen: **bar-count-constant**.

### 4. `scripts/research/qualify_htf.py` — thin HTF qualification driver
- Mirror `qualify_majors.py` structure ([qualify_majors.py](scripts/research/qualify_majors.py)),
  reusing `research.qualification` (`evaluate_pre_bh`/`benjamini_hochberg`/`finalize`) and
  `HypothesisRunner` **verbatim** — re-scope over the resampled universe per TF. No new stats, no
  promotion, no spine/config edits. Deterministic JSON body + separate wall-clock manifest, exactly
  like qualify_majors. (Keep qualify_majors.py untouched; this is a sibling driver, not a refactor.)

## Pre-registration (doctrine-required, BEFORE running)
- Add **"Program 3: Higher-Timeframe Directional Ontology" = RESEARCH** to the Funding Ledger in
  [docs/current-findings.md](docs/current-findings.md) with the hypothesis, universe (crypto-majors
  H1/H4), governing truth standard, advance/kill criteria (PROMOTE survives M4 gates 1–7 + BH IS&OOS,
  else in-scope falsification), and an explicit "this is a NEW horizon ontology, not a Program-1
  parameter pass" clause.

## Docs — fold into existing system (NOT 3 new root docs)
- Add ONE scannable **"Research Envelope / Scope Matrix"** — single section in
  [docs/current-findings.md](docs/current-findings.md) (the living authority; §6.2 rule 1/5
  doc-minimization) or one linked `docs/research-envelope.md`. Columns: finding (F-019…F-026) ×
  {universe, timeframe, exit, cost, N, OOS tested} → SCOPE STATUS
  `FALSIFIED-IN-SCOPE` / `ALREADY-ANSWERED` / `UNTESTED-FRONTIER`. Uses the repo's *correct* values —
  marks conditional-direction, Hurst, and exit/cost as ALREADY-ANSWERED (closing the critique's three
  stale "unknowns"); marks timeframe + non-crypto universe as UNTESTED-FRONTIER (Program 3 attacks the
  first). This IS the additive "belief falsification" structure, minus the duplication of the existing
  Reversal/Reopen fields.

## Run + record (same turn as the run)
1. `python scripts/research/build_resampled_data.py` → `data/resampled/*.csv` (verify byte-identical re-run).
2. `python scripts/research/qualify_htf.py --tf H1` and `--tf H4` → `results/research/qualification_htf/`.
3. Record the verdict: a new **F-id** (HTF falsification, if null) or an F-010-class lead (if a cell
   PROMOTEs), and flip the Funding Ledger Program 3 status — in the **same turn** per §6.2 Findings Mandate.

## Verification
- **Resampler unit tests** (`tests/research/test_resample.py`): golden small fixture (hand-computed
  M15→H1 bucket), determinism/idempotence (byte-identical re-run), boundary + intra-hour-gap handling,
  trailing-partial-bucket drop, OHLC invariants (bucket high = max children high, low = min, open=first,
  close=last; H≥max(O,C), L≤min(O,C)).
- **Determinism gate:** qualify_htf JSON body byte-identical across two runs (edge_report discipline).
- **No regression:** full suite stays green — the change is additive; runner/forward_walk/qualification
  untouched. Run `pytest` per [docs/reference/testing.md](docs/reference/testing.md), plus the spine +
  Backtest Trust Layer subset to confirm GREEN is preserved.
- **End-to-end sanity:** confirm resampled bar counts ≈ M15_count/4 (H1) and /16 (H4) per instrument,
  and that the HTF run produces non-empty per-instrument + pooled reports.

## Out of scope (explicit)
- No exit/cost grids, TP-ratio/trailing/session sweeps, score-threshold or entropy re-runs (Program 1
  archaeology, forbidden).
- No FX/equities universe yet (the *other* untouched axis — deferred; revisit after the H1/H4 verdict).
- No live-spine, promotion, or config-version changes; measure-only research.
