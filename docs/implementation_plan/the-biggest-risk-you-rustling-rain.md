# Plan — Experiment-2A: Cross-Asset Lead-Lag (falsification-first)

## Context

The Experiment-1 arc exhaustively falsified **BNB → BNB** (own-series price action: aggregate,
conditional, opportunity — all indistinguishable from random under realistic execution). The
only **genuinely exogenous** information available in the current data (OHLCV M15 only; no
orderflow/news/macro on disk) is **cross-asset**: do BTC/ETH/SOL moves predict BNB? That
hypothesis family was **never attacked** by Experiment-1.

**Posture (confirmed): falsification-first, NOT strategy-building.** Build a small cross-asset
family + run it through the **existing, unchanged** machinery (M4 QualificationGate +
`always_long`/`random_uniform` controls + permutation + BH + the conditional-edge audit). The
deliverable is a **verdict** — most likely another `PROMOTE: none` ("cross-asset OHLCV is
insufficient"), which is a scientific success — exactly like Phase B.

**Universe:** `BNBUSDT` (target) + `BTCUSDT`, `ETHUSDT`, `SOLUSDT` (peers) — all already in
`data/`, all crypto-clean (24/7, ~70k M15 bars, same span; L2/L3 APPROVE).

**Dominant NEW risk = synchronization look-ahead leak.** Every failure so far was "no edge";
the cross-asset inverse risk is *manufacturing a fake edge* by letting `detect()` peek at a peer
bar dated after the decision. Two defenses, baked in: a strict `ts ≤ t` peer guard, and a
**peer-shuffle control** (run every hypothesis with peer series misaligned — any "edge" that
survives the shuffle is a leak/bug, not signal).

## Change 1 — Multi-symbol synchronized-context substrate (the only real new capability)

New `src/research/multi_symbol.py` — `PeerContext`:
- Loads each peer via `CandleLoader`; stores per peer a sorted timestamp array + bars.
- `peer_windows(t, window) -> {sym: [bars with ts ≤ t][-window:]}` via bisect. **Strict
  no-lookahead:** only peer bars with `timestamp ≤ t` (contemporaneous M15 close at `t` is
  allowed — both instruments close simultaneously and the prediction target is BNB `t+1…`;
  forward_walk already reads only BNB bars after `t`). Assert no peer bar with `ts > t` is ever
  returned.
- Injected into the existing `detect(window, features, ctx)` via `ctx["peers"]` — **contract
  unchanged**; the existing single-instrument hypotheses ignore `ctx["peers"]` (backward compatible).

Runner: extend `HypothesisRunner.collect`/`run_instrument` with an optional `PeerContext` so the
**target** (BNB) drives the bar loop and each bar gets its peer context. The target is what is
forward-walked / aggregated / qualified; controls run on the **same** target (apples-to-apples).
Config: additive `cross_asset` section in `configs/research/research_config.json` +
`ResearchConfig` (`target`, `peers`, `peer_window`) → in the provenance hash.

## Change 2 — Cross-asset probe hypotheses (`src/research/hypotheses/cross_asset.py`)

Deliberately simple, **3 distinct mechanisms** (NOT 50 — every added hypothesis widens the BH
universe; keep researcher-degrees-of-freedom minimal). Each declares `economic_rationale`, reads
`ctx["peers"]`, emits a BNB `Signal`, flows through identical measurement/qualification:
- **`xa_leader_momentum`** — BTC's last-k-bar return sign → BNB direction (leader carry: BTC
  leads, BNB follows).
- **`xa_relative_strength`** — basket (BTC/ETH/SOL) strong while BNB lags → long BNB (catch-up).
- **`xa_corr_breakdown`** — BNB return decouples from the basket (opposite sign) → fade BNB back
  toward the basket (correlation-reversion).

Fixed, sensible parameters — **no parameter search, no ATR/stop/exit tuning** (SL/TP inherit the
config defaults via `apply_signal_defaults`, identical to Experiment-1).

## Change 3 — Run through the EXISTING machinery (no new gates, no weakening)

1. `qualify` (M4) on the 3 hypotheses with the BNB `always_long`/`random_uniform` controls — the
   beats-winning-control gate compares cross-asset vs BNB random baseline; BH across the family.
2. **Peer-shuffle leakage control:** re-run with peer series time-shuffled; confirm any apparent
   signal collapses to the random baseline (proves no synchronization leak).
3. Conditional-edge / adversarial audit only **if** something clears M4 (don't pre-fish).

**Explicitly forbidden** (per the arc's lessons): parameter search · ATR/stop/target redesign ·
hypothesis stuffing · weakening M4 · low-power metrics (opportunity profile) · zero-baseline
comparisons · promotion.

## Tests (`tests/research/`)
- `PeerContext`: never returns a peer bar with `ts > t` (no-lookahead); correct window slicing
  with peer gaps/misalignment; bisect alignment correctness.
- Backward-compat: existing single-instrument hypotheses produce **byte-identical** edge_report
  with `ctx["peers"]` present-but-ignored (determinism invariant holds).
- One cross-asset hypothesis fires deterministically on a synthetic 2-instrument fixture.
- **Leakage test:** a fixture with a planted future-peer value must NOT change the signal (guard
  blocks `ts > t`).

## Verification (end-to-end)
1. `python -m pytest tests/research -q` — green incl. no-lookahead + backward-compat.
2. `python -m research.cli qualify` (cross-asset mode) → deterministic verdict; **then** the
   peer-shuffle control → signal must vanish.
3. Isolation lint: no `core.engine_runner`/`promotion_manager`/`config_validator` imports.
4. Deliverable `docs/analysis/cross-asset-experiment-2-2026-06-10.md`: hypotheses, universe,
   controls, M4 verdict, peer-shuffle result, (conditional/adversarial only if a survivor),
   **final verdict — cross-asset OHLCV: useful / useless.**

## Out of scope (hard)
No orderflow/news/macro/funding (no data). No strategy delivery — a verdict only. Governing
`intrabar_fixed`, qualification/M4/promotion, and the **production** config are untouched
(`cross_asset` is additive to the *research* config). A survivor is a PRE-REGISTERED OOS
CANDIDATE, never an edge; promotion still requires M4.5/M4.7 (unbuilt). Most likely outcome:
`PROMOTE: none` → cross-asset OHLCV insufficient → burden moves to data acquisition. That is a
successful Experiment-2.

## Governance / session-log
Append `📝 SESSION LOG ENTRY` per §6 at implementation. Isolated, measure-only research; no
live-spine/config-hash/promotion impact; determinism is a hard invariant.
