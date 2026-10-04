# Plan: Selection-Edge studies — Accepted-Trade Attribution + Gate Contribution Audit

> Created: 2026-06-03 · Updated: 2026-06-03 · Milestone: research / measure-first

## Context

The Edge Attribution study found **near-zero static feature→outcome edge at the per-candle level**
(AUC 0.515, R² 0.004, marginal ΔR² ≈ 0 for all but `candles_since_retest`). But that was measured on
**all scanner opportunities**, not the ~15–35 trades the CRT pipeline actually selects. The leading
hypothesis is now: **the edge is created by the selection process, not a static feature map.** These two
studies test that directly. Both are pure measurement — no production/config/ACTIVE_VERSION change.
(User-approved scope: S1 pooled-all + per-instrument; S2 BNBUSDT-only; backtest/scanner runs allowed —
they write only `results/` + `logs/`.)

---

## Study 1 — Accepted-Trade Attribution (does feature edge EMERGE after selection?)

**Question:** rerun the exact attribution metrics on only the **CRT-accepted/executed trades**. If AUC rises
meaningfully above 0.55 (vs 0.515 on opportunities) and marginal contributions appear, feature edge exists
*post-selection*. If it stays at chance, the edge is purely in the gating sequence — even among winners.

**Data (read-only, exists):** the **731 `results/**/*_trades.csv`** — each row already carries the 38
features at entry (cols 29–64) + `pnl_rr_net` + `instrument` + `opened_at` + `direction`/`entry`.
- **Filter:** drop the known degenerate rows (zero-feature guard: >50% features == 0.0) — the sample showed
  ~60% valid; keep only valid-feature rows.
- **Dedup:** the same trade recurs across re-runs → dedup on `(instrument, opened_at, direction, entry, sl, tp)`.
- **Targets:** `rr = pnl_rr_net`, `win = pnl_rr_net > 0`.
- Expect low thousands of unique accepted trades pooled.

**Method:** reuse the existing attribution engine — refactor `scripts/research/edge_attribution_study.py`
to expose `run_attribution(X, rr, win, ts, inst_labels)` + a `--source accepted` loader
(`load_accepted_trades()` over the trade CSVs), so the *same* importance (Spearman/MI/permutation),
drop-column **marginal**, decile PF/expectancy, temporal & cross-instrument stability, and coverage gate
run unchanged. Add a **global ranking + per-instrument breakdown** (BNB/SOL/ETH/BTC + FX).

**Output:** `docs/analysis/accepted-trade-attribution-2026-06-03.md` (+ JSON). Headline = the
opportunities-vs-accepted comparison: `AUC 0.515 → ?`, and which (if any) features now carry marginal,
durable edge.

**Caveats (non-negotiable):** the 731 runs span **many configs/periods** (heterogeneous — pooled
attribution mixes param regimes); low N per instrument weakens stability columns; survivorship (only
executed trades, no rejected counterfactual here — that's Study 2); features can be stale-zero (filtered).

---

## Study 2 — Gate Contribution Audit (which CRT stage creates vs destroys edge?) — BNBUSDT

**Question:** walk the funnel `RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → SESSION-gate →
EXECUTION` and measure **count, conversion %, and counterfactual expectancy/PF/WR after each stage**.
Which transition concentrates positive-expectancy candidates; which is dead weight; which destroys edge.

**Mechanism (read-only):**
1. **Run one BNBUSDT v4 backtest** (`python src/runtime/backtest_v2.py --csv data/BNBUSDT_M15.csv
   --instrument BNBUSDT`) → executed-trade outcomes (EXECUTION/RESOLUTION expectancy, real) + the funnel
   **counts** (`BacktestMetrics.state_distribution` / transition counts) + `logs/crt_transitions.jsonl`.
2. **Per-candle "max stage reached":** parse `logs/crt_transitions.jsonl` **`payload`** (the enveloped
   record — `state_to`/candle ts live inside `payload`, not top-level; top-level `timestamp` is wall-clock),
   filtered to `instrument == BNBUSDT`, to map each candle → furthest CRT state it reached.
3. **Counterfactual outcome per stage via JOIN:** join (2) to BNBUSDT `opportunities.jsonl`
   (`logs/BNBUSDT/.../opportunities.jsonl`, per-candle simulated `rr_achieved`) on candle timestamp
   (normalize `"YYYY-MM-DD HH:MM:SS"`). → "if a vanilla trade were taken at every candidate that reached
   stage X, what's the mean rr / PF / WR." EXECUTION uses the real trades, not the proxy.
4. **Contingency** (if `payload` lacks a usable candle ts/state): add a **minimal additive sidecar** in the
   CRT loop that emits `logs/bnbusdt_stage_reached.jsonl = {candle_ts, max_stage, direction}` per candle —
   logging only, **no behavior change, backtest ledger byte-identical** — then join as in (3).

**Output:** `docs/analysis/gate-contribution-bnbusdt-2026-06-03.md` — the funnel table
`Stage | count | conv% (from prev) | counterfactual mean_rr | PF | WR | verdict (creates / neutral /
destroys edge)`, plus the explicit answer to "which gate is the edge" and which is dead weight.

**Caveats:** the counterfactual uses the scanner's vanilla SL/TP (not the execution planner's) — it measures
*candidate-population quality* at each stage, not exact realized PnL; counts/period are one BNB run on v4.

**New script:** `scripts/analysis/gate_contribution_audit.py` (models the existing
`scripts/analysis/p3b_gate_expired_counterfactual_rr.py` counterfactual pattern + the funnel-count readers).

---

## Verification
- **S1:** `python scripts/research/edge_attribution_study.py --source accepted` runs; report + JSON written;
  N(unique accepted) and valid-feature % reported; **opportunities-vs-accepted AUC delta** stated plainly
  (the headline). Per-instrument tables present. Same seed → identical ranks.
- **S2:** the BNB backtest completes; `gate_contribution_audit.py` produces the funnel table with all 6
  columns populated; EXECUTION-stage expectancy matches the backtest summary (sanity); join coverage
  (% of stage-reached candles matched to an opportunity outcome) reported — if low, the contingency sidecar
  is used and re-run.
- Both: **pure read-only vs production** — `git status` shows only new scripts + `docs/analysis/*` (+ the
  backtest's own `results/`/`logs/` artifacts); no config, no ACTIVE_VERSION, no promotion. `config_hash`
  + governance guards on v4 unchanged. SESSION LOG (§6) appended; rows added to `docs/analysis/readme.md`.

## Interpretation contract (what each outcome means)
- **S1 AUC rises ≫0.55 with durable marginal features** → feature edge IS real post-selection → a filtered
  predictor (Probability Surface on accepted trades) is worth building.
- **S1 stays ~chance** → edge is the selection sequence itself, not features → deprioritize feature/cluster
  intelligence; invest in selection/throughput policy.
- **S2** names the **edge-creating gate(s)** and any **dead-weight / edge-destroying** gate → directly informs
  whether to tighten, relax, or remove a gate (the session-filter result already hinted RETEST→EXECUTION).
