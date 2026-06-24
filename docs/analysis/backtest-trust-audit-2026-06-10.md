# Backtest Trust Audit — 2026-06-10

> **Type:** Point-in-time analysis (not a living doc). Authoritative source = code at the cited `file:line`.
> **Scope:** WS1 of the Backtest Trust Layer — map and verdict every trade-accounting and metric
> calculation before any further sweeps/OOS/M4 are trusted. Read-only; no code changed in this pass.
> **Doctrine:** `replay correctness > explainability > telemetry > advisory-AI > profit`. An error near
> the top of `prices → accounting → PnL → metrics` corrupts everything beneath it.

---

## 0. Verdict summary

| ID | Area | Severity | Verdict | One-line |
|----|------|----------|---------|----------|
| F1 | Feature lookahead | P0 (leakage) | **suspect — quantify** | `center=True` swing detection can absorb future-bar info into the decision-bar reference. |
| F2 | Exit triggering | P0 (realism) | **suspect — quantify** | SL/TP trigger is **close-crossing only**; intrabar wick touches are ignored. |
| F3 | Slippage RNG | P1 (defect) | **defect — fix** | `compute_fill_prices` result discarded then re-drawn; wastes RNG draws, unpairs slips. |
| F4 | Metric formula drift | P1→P2 (clarity) | **drift, but decision-path clean** | 4 modules compute PF/expectancy/DD differently; only `backtest_v2` feeds promotion. |
| F5 | `score_std_dev` | P2 (naming) | **not a true divergence** | Half-std *penalty* vs full-std *telemetry* — different roles, not the same metric. |
| F6 | Validator ROI aggregate | P2 (telemetry) | **minor defect** | `total_return_pct_across` is always `0.0` — key never threaded out of `_run_instrument`. |
| — | Determinism | — | **OK** | `slippage_seed: 42` fixed; research harness sorts + `sort_keys=True`. |
| — | Commission/fees | — | **flag** | No commission/fee layer modelled anywhere — only slippage + spread. |

---

## 1. Trade-accounting trace (per calculation)

| Calculation | Authoritative `file:line` | Formula as written | Units | Verdict |
|-------------|---------------------------|--------------------|-------|---------|
| Entry price (raw) | `backtest_v2.py:785` | `entry_price_raw = trade.entry_price` | price | correct |
| Entry fill | `backtest_v2.py:756` | `entry_fill = entry_price + e_slip + spread_half` | price | correct (but see F3) |
| Spread half | `backtest_v2.py:1622, 2102`; cfg `:370` | `spread_half = candle.close * simulated_spread_pct / 2` (`0.0002`) | price | correct |
| Slippage | `backtest_v2.py:385-396` | `slip ~ U(0, atr_fraction*ATR)`, adverse sign | price | correct math; **F3** hygiene |
| Commission/fees | — | *none* | — | **flag — not modelled** |
| Position size | `backtest_v2.py:320-328, 778` | `size = (capital*risk_pct) / |entry_fill - effective_sl|` | units | correct |
| SL fill-guard | `backtest_v2.py:762-775` | extend SL to `0.2*ATR` min distance if slippage erodes it | price | correct (prevents runaway size) |
| Planned RR | `crt_engine_v2.py:240-244` | `|tp1 - entry| / |entry - sl|` | R | correct |
| Realized RR | `backtest_v2.py:846-848` | `pnl_rr_net = (price_move_net/pip) / risk_pips`, `risk_pips=|entry_fill-sl|/pip` | R | correct |
| Per-trade PnL (R) | `backtest_v2.py:838-848` | directional `exit-entry`, raw & net | R / pips | correct |
| Per-trade PnL ($) | `backtest_v2.py:856-858` | `pnl_per_unit * position_size` → `capital += ` | currency | correct |
| **Exit trigger** | `crt_engine_v2.py:1962-1964` | `hit_sl = close <= sl` (LONG); TP analogous — **close only** | — | **F2 — suspect** |
| **Exit price booked** | `backtest_v2.py:2003,2010,2012` | `exit_raw = sl_price / tp1_price / tp2_price` (the *level*, not close) | price | **correct** (see note) |
| Exit (partial blends) | `backtest_v2.py:2000,2007` | `0.5*tp1 + 0.5*sl` (BE stop) / `0.5*tp1 + 0.5*tp2` (runner→TP2) | price | correct |
| Exit (reset/gap/end) | `backtest_v2.py:1624,2058,2104` | `candle.open` (gap) / `candle.close` (reset, end) | price | correct |

**Key nuance (F2 scope).** Once a close-crossing trigger fires, realized PnL is booked at the **level
price** (`sl_price`/`tp1`/`tp2`), which is conservative and correct. F2 is therefore **not** a fill-price
overstatement — it is a *triggering* defect: a bar whose **high** touches TP but **close** falls back
never books the win; a bar whose **low** touches SL but **close** recovers never books the loss
(optimistic survival). Net bias direction is ambiguous and must be **measured** (WS4B), not assumed.

---

## 2. Metric formula trace (aggregate)

Canonical owner = `MetricsEngine` / `BacktestMetrics` in `backtest_v2.py`.

| Metric | `file:line` | Formula | Units |
|--------|-------------|---------|-------|
| Win rate | `backtest_v2.py:992-994` | `wins / (wins+losses)` | frac |
| Win/loss split | `backtest_v2.py:1069-1070` | win = `pnl_rr_net > 0`; loss = `pnl_rr_net <= 0` (**0R counts as loss**) | — |
| Avg RR (≈expectancy) | `backtest_v2.py:997-999` | `total_pnl_rr_net / (wins+losses)` (mean-R form) | R |
| Profit factor | `backtest_v2.py:1096-1101` | `gross_win_rr / |gross_loss_rr|`; sentinel `999.0` if no losses | R |
| Max DD (%) | `backtest_v2.py:347-356` | equity-curve peak-trough `(peak-eq)/peak` | % |
| Max DD (R) | `backtest_v2.py:1114-1120` | cumulative-R peak-trough `peak-eq` | R |
| Total return % | `backtest_v2.py:359-360` | `(final-initial)/initial` | % |
| CAGR | `backtest_v2.py:1107-1112` | `(1+ret)^(1/years) - 1`, `years = candles*15 / (365*24*60)` | % |
| MAR / return-to-DD | `backtest_v2.py:1105` | `total_return_pct / max_dd_pct` | ratio |
| Monthly R | `backtest_v2.py:1080-1082` | `Σ pnl_rr_net` keyed by `YYYY-MM` (**R, not %** — name is a misnomer) | R |
| Trade/funnel counts | `backtest_v2.py:1056-1063` | summations + CRT-state funnel | int |

---

## 3. Decision-path consumption (resolves F4 severity)

The only path to promotion consumes **canonical `backtest_v2` metrics exclusively**:

- `ConfigValidator._run_instrument` → reads `m.win_rate`, `m.avg_rr_net`, `m.max_drawdown_pct`,
  `m.total_pnl_rr_net` (`config_validator.py:157-161`) → `_fitness_score` (`:114-136, 162`).
- `_aggregate_metrics` → `final_score = mean_score - consistency_penalty` (`config_validator.py:198`).
- `PromotionManager` → `score_std_dev` from the per-instrument fitness **scores** (`promotion_manager.py:379-384`).

**Therefore F4 (PF×3, expectancy×4, max-DD×3, win-rate×2) does NOT corrupt promotion decisions** — the
divergent copies live in non-decision analytics: `analytics/performance.py:33-77` (currency-unit, classical
expectancy), `analytics/sl_tp_comparator.py:217`, and `research/measurement/metrics.py:61-106` (isolated
edge-discovery platform). The real risk is **human confusion**: two reports quoting "PF" can disagree
because they use different units/definitions. Remedy = WS2B (single source or explicit quarantine).

**F5 reclassified.** `config_validator.py:197` computes `consistency_penalty = std * 0.5` (a *penalty*
folded into `final_score`); `promotion_manager.py:382` computes `score_std_dev` (full std, *logged
telemetry*). These are different quantities serving different roles — **not** one metric computed two
ways. Action = rename for clarity in WS2B; no correctness bug.

**F6 (new).** `config_validator.py:203` reads `v["total_return_pct"]`, but `_run_instrument` (`:164-172`)
never puts that key in its return dict → `roi_vals` is always empty → `total_return_pct_across` is always
`0.0`. Cosmetic/telemetry only (ROI is measure-only, never gated), but the surfaced number is dead. Thread
`total_return_pct` out of `_run_instrument` (cheap) — fold into WS2B.

---

## 4. Determinism (OK, with caveats)

- `slippage_seed: 42` (non-zero) — `configs/production/v1_multi_2026_03.json:369`; `SlippageModel.__init__`
  uses system randomness only when seed == 0 (`backtest_v2.py:387`). Replay is deterministic as configured.
- Research harness: sorted instrument iteration + `json.dumps(..., sort_keys=True)` (`research/runner.py:102,124`).
- **Caveat (F3):** `on_trade_opened` (`backtest_v2.py:750`) calls `compute_fill_prices(...)` and discards all
  four outputs, then re-draws `entry_slip` at `:755`. Per trade-open this consumes 3 RNG draws (2 wasted) and
  the *used* entry slip is not paired with the *used* exit slip. Still deterministic given the fixed seed, but
  it is a defect: deterministic ≠ correct. Fixing it WILL shift the ledger → run in isolation (WS2A) with a
  pre/post delta report so the change is fully attributable.

---

## 4b. WS2A — F3 fix applied + ledger-delta report (BNBUSDT, active config `v2_multi_2026_04`)

Fix landed at `backtest_v2.py:749-756` (removed the discarded `compute_fill_prices` call; entry-open
now consumes exactly one `entry_slip` draw). Pre/post full-run BNBUSDT comparison:

| Metric | Baseline (pre-F3) | Post-F3 | Δ |
|--------|-------------------|---------|---|
| Trades | 18 | 18 | **0** |
| Win rate | 38.89% | 38.89% | 0 |
| Avg RR net | −0.0367R | −0.0383R | −0.0016R |
| Total PnL net | −0.6615R | −0.6901R | −0.0286R |
| Profit factor | 0.9438 | 0.9417 | −0.0021 |
| Max DD % | 4.88% | 5.08% | +0.20pp |
| Total return % | −0.82% | −0.85% | −0.03pp |

**Ledger diff:** 18/18 trades matched by id — **0 added, 0 removed, 0 exit-reason changes**; only
realized `rr_net` shifts (max single-trade |Δ| = 0.25R, the rest sub-0.01R). **Interpretation:** F3 is a
pure slippage-fill hygiene change — it does not alter trade *generation* or *exit* logic, only the
realized fill prices via the corrected RNG draw sequence, exactly as predicted. Post-fix run is
deterministic (two runs byte-identical). **Ledger frozen at this point** — no later workstream in this plan
touches trade generation/fills. (Measurement harness + artifacts under gitignored `results/trust/`.)

## 4c. WS2B — formula authority resolved (refined finding)

Closer reading showed F4 is **not one metric duplicated four times** — it is *domain-specific
metrics that merely share names*, and the promotion decision path is already single-source
(§3). Resolution applied accordingly:

- **`analytics/sl_tp_comparator.py`** — same R-domain → **unified onto the oracle**. `win_rate`,
  `expectancy_rr`, `max_drawdown_r` now call `metrics_oracle`. Behavior-preserving (its
  `expectancy_rr` was algebraically `expectancy_mean`); existing tests green.
- **`analytics/performance.py`** — **quarantined** (label). Different domain: currency-unit
  live-feedback dicts, AI-feedback loop only, never a promotion path.
- **`research/measurement/metrics.py`** — **quarantined** (label). The Edge Discovery platform's
  own isolated, determinism-proven metric layer; intentionally not routed through the oracle.
- **F5** — clarifying comments at both sites (`config_validator.py` half-std *penalty*;
  `promotion_manager.py` full-std *telemetry*). **No rename** — `promotion_log.jsonl` schema is
  load-bearing.
- **F6** — fixed: `ConfigValidator._run_instrument` now threads `total_return_pct`, so
  `total_return_pct_across` is live (verified `0.0063` on a 2-instrument synthetic vs the prior
  dead `0.0`). ROI remains additive/measure-only — never folded into `final_score`.

## 4d. WS4A — F1 leakage quantification (measure-only, BNBUSDT)

Added a measure-only hook: `TRUST_SWING_CAUSAL=1` delays swing-pivot availability by
`SWING_WINDOW` (=2) bars so the decision-bar reference is causal (`feature_pipeline.py`,
compute_structure_liquidity). Default off — no production-config/hash change.

**Toggle is active** (verified: 974/3000 `swing_high` flags and 840/3000
`last_swing_high_price` values shift under causal mode). **Result — full-run BNBUSDT,
center=True vs causal:**

| Metric | center=True (leaky) | causal | Δ |
|--------|--------------------|--------|---|
| Trades | 18 | 18 | **0** |
| Win rate | 38.89% | 38.89% | 0 |
| Avg RR net | −0.0383R | −0.0383R | 0 |
| Profit factor | 0.9417 | 0.9417 | 0 |
| Max DD % | 5.08% | 5.08% | 0 |
| Total return % | −0.85% | −0.85% | 0 |

**Edge inflation ≈ 0.** Byte-identical ledger (0 added/removed). The `center=True` lookahead
perturbs the swing *feature columns* but does **not** flip any trade decision or outcome on
this instrument/config — the CRT structural gating + scorers don't depend on those columns in
a decision-changing way. **Verdict:** F1 is real but empirically **benign for trade
generation** here; it must still be made causal before live mode (the `LIVE-UNSAFE` note
stands). *Caveat: single instrument (BNBUSDT) / active config; not yet swept cross-universe.*

> **Reconciliation (2026-06-15, F-029).** A later adversarial design session re-escalated this same
> `center=True` lookahead to "FATAL label leakage" and demanded a repo-wide pipeline rewrite + model
> deletion. That framing is **DOC_DRIFT** against the byte-identical evidence above — recorded and
> superseded as finding **F-029** (`docs/current-findings.md`). The verification also found the
> alleged training-contamination chain (`TradeRecord.features → dataset builder → tensor`) does not
> exist and the proposed "execution successor" is the already-built TradeNet v2. The one genuinely
> new, un-audited item it surfaced — `volatility_regime`'s **global** `rank(pct=True)`
> (`feature_pipeline.py`, decision-reachable via `s05_grid.py`) — is the subject of a separate
> measure-only pass (§4f below / F-029 OPEN sub-thread).

## 4e. WS4B — F2 exit realism (measure-only, BNBUSDT) — ⚠ MATERIAL

Added a measure-only hook: `TRUST_INTRABAR_TOUCH=1` switches SL/TP detection from
close-only to **intrabar high/low touch** with a *conservative* same-bar ordering (SL
assumed before TP when a bar spans both — the pessimistic bound), via
`CRTEngine._intrabar_trigger_price` (`crt_engine_v2.py`). Default off — no config/hash change.

**Full-run BNBUSDT, close-only vs intrabar touch:**

| Metric | close-only (prod) | intrabar touch | Δ |
|--------|-------------------|----------------|---|
| Trades | 18 | 18 | 0 |
| Win rate | 38.89% | 27.78% | **−11.1pp** |
| Avg RR net | −0.038R | −0.418R | **−0.380R** |
| Total PnL net | −0.69R | −7.52R | **−6.83R** |
| Profit factor | 0.9417 | 0.4594 | **−0.482** |
| Max DD % | 5.08% | 11.25% | **+6.2pp** |
| Total return % | −0.85% | −7.37% | **−6.5pp** |

Exit-reason mix: `TP2 6→3`, `STOPPED 12→15` — **3 of 18 trades flip from TP2 win to stop-out**.
Entries are unchanged (entry gating is correctly close-based, no lookahead), so the entire
divergence is in exit modelling.

**Verdict — this is the most consequential finding.** Close-only exits **materially inflate**
results: they treat wicks that pierce SL but close back inside as survivals. The strategy's
measured profile moves from ~breakeven (PF 0.94) to clearly losing (PF 0.46) under realistic
fills. The two models bracket the truth — close-only is the *optimistic* bound, conservative
intrabar the *pessimistic* bound — and the band is enormous (PF 0.94 ↔ 0.46). **Current
backtest metrics cannot be trusted for promotion decisions until the exit model is resolved.**
This is empirical justification for the WS5 freeze, not just procedure. *Caveat: single
instrument/config; conservative ordering is a worst-case bound — a path-aware model would land
between, but for an SL-based strategy much closer to the intrabar figure than to close-only.*

## 4f. F-029 / Program B — `volatility_regime` rank causality (measure-only, BNBUSDT)

A 2026-06-15 reconciliation pass (finding **F-029**, `docs/current-findings.md`) closed the
adversarial "FATAL center=True" re-escalation as DOC_DRIFT against §4d, and surfaced one genuinely
new, un-audited item: `volatility_regime` buckets ATR by a **global** `rank(pct=True)`
(`feature_pipeline.py`), a whole-column statistic (slice-length dependent) that — unlike the swing
columns — **is** decision-reachable (`s05_grid.py` blocks LONG in the TRENDING regime).

Added a measure-only A/B/C hook `TRUST_VOLREGIME_CAUSAL` (`feature_pipeline.py`,
`compute_volatility_regime`; default off, no config/hash change): **A** = current global rank;
**B** = `expanding().rank(pct=True)` (time-causal); **C** = `rolling(200).rank(pct=True)`
(trailing). Three full backtests on the branch-active config (`v2_multi_2026_04`), BNBUSDT, via the
production spine (`session_sweep._run_one` → `BacktestRunner` → `FeaturePipeline`):

| Metric | A global | B expanding | C rolling | Δ |
|--------|----------|-------------|-----------|---|
| Trades | 13 | 13 | 13 | **0** |
| Win rate | 30.77% | 30.77% | 30.77% | 0 |
| Avg RR net | −0.3574R | −0.3574R | −0.3574R | 0 |
| Profit factor | 0.5233 | 0.5233 | 0.5233 | 0 |
| Total return % | −4.63% | −4.63% | −4.63% | 0 |
| Max DD % | 6.64% | 6.64% | 6.64% | 0 |

**Decision divergence** (entry-ts + direction identity): A-vs-B, A-vs-C, B-vs-C all show **100%
overlap — 0 trades added, 0 removed, no first-differing timestamp.** Per the F-029 interpretation
grid this is the `A≈B≈C ⇒ benign` cell: the global-rank slice-dependence does **not** flip any trade
decision on this instrument/config. The regime column is decision-reachable in principle but the
governing path here (the CRT spine, not `s05_grid`) renders it inert — the same real-but-benign
conclusion class as F1. *Caveat: single instrument (BNBUSDT) / active config; not yet swept
cross-universe — the global→causal conversion (Option 2) remains gated on a future config/instrument
showing material divergence. Driver: `results/trust/volregime_measure.py` (measure-only).*

## 4g. Cross-universe graduation — F1 + F-029 (measure-only)

To retire the single-instrument BNBUSDT caveat on **both** lookaheads, the driver was generalized to a
4-variant sweep per instrument on the branch-active config (`v2_multi_2026_04`): **A** baseline,
**B** `TRUST_VOLREGIME_CAUSAL=expanding`, **C** `TRUST_VOLREGIME_CAUSAL=rolling`, **S**
`TRUST_SWING_CAUSAL=1`. Decision-identity overlap (entry-ts + direction) of A↔B, A↔C (volregime/F-029)
and A↔S (swing/F1):

| Instrument | Class | Trades (A) | A↔B | A↔C | A↔S | Verdict | Informative? |
|---|---|---|---|---|---|---|---|
| BTCUSDT | crypto | 5 | 100% | 100% | 100% | benign | **yes** |
| ETHUSDT | crypto | 5 | 100% | 100% | 100% | benign | **yes** |
| SOLUSDT | crypto | 7 | 100% | 100% | 100% | benign | **yes** |
| AUDUSD | FX | 0 | — | — | — | benign | no (0 trades) |
| GBPUSD | FX | 0 | — | — | — | benign | no (0 trades) |
| USDJPY | FX | 0 | — | — | — | benign | no (0 trades) |
| XAUUSD | metal | 0 | — | — | — | benign | no (0 trades) |

**Honest read.** On the **crypto majors** (BTC/ETH/SOL — non-trivial trade counts) every variant is
**byte-identical** to baseline (100% overlap + identical metrics). Together with BNBUSDT (§4d/§4f) this
graduates F1 and F-029 from *"BNBUSDT benign"* to **"crypto-majors benign"** (BNB+BTC+ETH+SOL): neither
`center=True` swing lookahead nor `volatility_regime` global-rank flips any governing decision on the
crypto-major universe under the active config.

The **FX/metals** rows are **NOT INFORMATIVE**: the active multi config approves **0 trades** on
AUDUSD/GBPUSD/USDJPY/XAUUSD (it carries no FX-specific tuning), so their "benign" is vacuous — an empty
comparison, not cross-asset-class evidence. The cross-asset-class claim therefore remains **open**: it
needs an FX-trading config to be testable, which is the residual reopen path. Universe verdict
`all_measured_benign=True` but only **3 of 7 rows are informative** (the crypto majors). Driver:
`results/trust/volregime_measure.py`; summary `results/trust/volregime/xuniverse_result.json`
(measure-only).

## 5. Workstream status (all complete)

| WS | Status | Outcome |
|----|--------|---------|
| WS1 | ✅ | This audit; 6 findings classified. |
| WS2A | ✅ | F3 fixed, isolated, ledger-delta reported, ledger frozen (§4b). |
| WS3 | ✅ | Independent oracle + parity gate (10/10) + replay gate (byte-identical) green. |
| WS3.5/WS3.6 | ✅ | Golden ledgers A–E + invariants — 113 tests, exact to 1e-12. |
| WS2B | ✅ | sl_tp_comparator unified onto oracle; performance.py + research/metrics.py quarantined; F5 comments; F6 fixed (§4c). |
| WS4A | ✅ | F1 leakage = **0** on BNBUSDT (§4d). |
| WS4B | ✅ | F2 close-only inflation = **large** (PF 0.94→0.46) (§4e). |
| WS5 | ✅ | Freeze gate + Five Questions below. |

## 6. Governance — institutional freeze gate

**MANDATORY GATE.** No `session_sweep` / `detection_sweep` / OOS run / M4 qualification /
promotion may be trusted until ALL THREE are green on the target config:

1. `pytest tests/analytics/test_metrics_oracle_parity.py` — oracle reconciles with `BacktestMetrics`.
2. `pytest tests/runtime/test_replay_determinism.py` — same CSV+seed+config ⇒ byte-identical ledger.
3. **Baseline reconciliation** — the frozen post-WS2A ledger reproduces (§4b).

Plus the now-resolved exit-model question (F2): **promotion is additionally blocked until the
exit model is governance-decided** (keep close-only as a documented conservative-the-other-way
assumption, OR adopt intrabar touch and re-baseline). Until then, treat all PF/expectancy/ROI
numbers as the *optimistic* bound (§4e).

### Five Governance Questions (scored)

| # | Question | This change |
|---|----------|-------------|
| 1 | Does replay remain deterministic? | **Yes** — F3 preserves seed=42 determinism (verified two byte-identical runs); WS4A/WS4B hooks are env-gated, default off. |
| 2 | Does telemetry remain comparable across runs? | **Yes** — F6 adds an additive ROI field; no field removed; measurement hooks don't alter default output. |
| 3 | Can this state be audited later? | **Yes** — this doc + the oracle/golden/invariant tests are the durable audit trail. |
| 4 | Can an LLM reason about this event? | **Yes** — findings are file:line-cited with explicit verdicts and deltas. |
| 5 | Is execution authority still isolated? | **Yes** — no change to gates/promotion authority; quarantine labels reinforce that only `ConfigValidator`/`BacktestMetrics` feed promotion. |

### Regression outcome

Full suite: **1397 passed, 46 failed, 18 skipped**. All 46 failures verified **pre-existing on
this `patch` branch** and unrelated to this work — tests written ahead of absent features
(`CRTConfig.tp3_enabled`, `PromotionManager._build_registry_entry(crt_engine_overrides=...)`,
`MLGaussianEngine`), the mid-flight docs migration (`test_doc_citations`, `test_cli_matrix_sync`,
`test_codebase_structure_doc`), network-dependent LLM connectivity, and the known-red
`on_retest_replay`. No failure names any trust-layer file; every directly-affected suite is green
(`test_sl_tp_comparator`, `test_analytics`, oracle parity/replay, golden ledgers, invariants).
**Zero regressions introduced.**

**Deviation note (vs approved plan):** WS4A/WS4B use env-var hooks (default off) rather than
production-config flags + rehash, to avoid touching the load-bearing schema hash for a
measure-only study. F4/F5 resolved as quarantine+comments rather than a risky cross-domain
merge or schema-breaking rename. All within the plan's "explicit quarantine" branch and
measure-only intent.
