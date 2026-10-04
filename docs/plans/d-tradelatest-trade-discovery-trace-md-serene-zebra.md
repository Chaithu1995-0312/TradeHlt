> Created: 2026-05-28 · Updated: 2026-05-28 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Phase 4 — Shadow Governance

> **Status**: Phase 0b ✅ | Phase 1 ✅ | Phase 2b ✅ | Phase 3a ✅ | Phase 3b ✅ (PASS INTEGRITY / PASS PROMOTION GATE) | Phase 4b ✅ (shadow_advisory_only=True) | Phase 5a → threshold sweep ← current

---

## Phase 4 — Shadow Governance

### Context

Phase 3b restored temporal causality (max dwell 209 days → 5.17 days). But the TTL freed the engine for 23 additional cycles, overwhelmingly shadow expansions: 22 shadow trades vs 15 normal, at radically different outcomes.

```
Shadow:  n=22  avg_rr=-0.290  WR=36%
Normal:  n=15  avg_rr=+0.314  WR=60%
```

Shadow is now the throughput driver and the performance drag simultaneously.

**Key diagnostic finding**: S-scores overlap completely (shadow avg=0.551, normal avg=0.543). The scoring model cannot distinguish shadow quality from normal quality. The quality difference is structural, not observable by the S-score at approval time.

**Why shadow underperforms**: Shadow expansions always have `candidate_age_at_entry=4` (displacement from previous HTF window, age=TTL boundary). Normal expansions have `candidate_age_at_entry=1` (fresh displacement). The displacement candle's market context is stale by the time the shadow expansion fires. This staleness is not captured by body_ratio or the G/C score fusion.

**User verdict**: "Shadow is now the weakest component. Earlier we protected shadow. Now evidence says shadow quality < normal quality."

**Prescribed experiment**: `shadow_threshold: OFF / LOW / MEDIUM / HIGH` → measure trades/rr/dd → find minimum threshold where `shadow_avg_rr >= 0`.

---

### Phase 4a — Telemetry Audit (read-only, current data)

Before implementing any gate, establish the baseline discriminator. Key finding from Phase 3b data:

| Metric | Shadow | Normal |
|---|---|---|
| n | 22 | 15 |
| avg_rr | −0.290 | +0.314 |
| WR | 36% | 60% |
| candidate_age_at_entry | 4 (always at TTL boundary) | 1 (fresh) |
| approval score avg | 0.551 | 0.543 |
| expansion episodes | 147 | 55 |
| retest→trade conversion | 26.8% | 28.8% |

S-scores overlap → score-based threshold alone will NOT discriminate. The pending displacement candle's `body_ratio` is the only structural signal available at expansion entry that differs between candidates.

**Missing signal**: `shadow_htf_alignment` — does the pending displacement direction still match the CURRENT HTF candle's range midpoint at expansion entry? This is the theoretically correct discriminator but not yet tracked. Add in Phase 4b.

---

### Phase 4b — Shadow Age-Decay Gate

#### Diagnosis

Body-ratio and S-score distributions overlap completely between shadow (avg=0.551) and normal (avg=0.543) candidates. A body-ratio gate or score threshold cannot discriminate. The quality difference is structural: shadow displacement candles are always from a **prior HTF window** (`candidate_age_at_entry=4`, always at TTL boundary), meaning market context is stale. Normal candidates enter fresh (`candidate_age_at_entry=1`). The staleness is not captured by body_ratio or the G/C fusion — it must be penalised at the point of trade approval, not at expansion entry.

**Architecture: memory → freshness → decide** (not memory → reject)

#### Decision Order (Phase 4b)

For shadow candidates only, in the soft-confirmation approval path:
1. **HTF alignment check** — does the pending displacement direction still match the current HTF range midpoint? (Structural veto — logged; no hard block in 4b, advisory)
2. **Freshness penalty** — `freshness_multiplier = exp(-λ × candidate_age_at_entry)` (λ = `shadow_age_penalty_lambda`)
3. **Effective score** — `effective_S = final_S × freshness_multiplier`
4. **Threshold gate** — compare `effective_S >= tier_2_threshold` (same threshold, softer shadow score)
5. **(Optional, later)** — `shadow_displacement_body_ratio` tracked for Phase 5 training label; no gate in Phase 4b.

For normal candidates: no penalty, no change.

#### New `CRTConfig` keys (after `expansion_age_warn_candles`)

```python
    # ── Shadow age-decay gate (Phase 4b) ─────────────────────────
    # Exponential decay applied to the S-score of shadow candidates at soft-conf approval.
    #
    # Variant A (shadow_age_norm_candles = 0, raw):
    #   effective_score = final_S × exp(−λ × age)
    #   At shadow age=4 (invariant): λ=0.10→×0.670 | λ=0.20→×0.449 | λ=0.35→×0.247
    #   Risk: behaves as threshold shifting when age is constant. λ is not interpretable.
    #
    # Variant B (shadow_age_norm_candles > 0, normalised):
    #   effective_score = final_S × exp(−λ × age / shadow_age_norm_candles)
    #   At age=4, norm=4: λ=0.40→×0.670 | λ=0.80→×0.449 | λ=1.39→×0.247
    #   Benefit: λ=1.0 means "at max shadow age, score → 1/e ≈ 37%". Interpretable.
    #   When normal candidates later carry age=1, both forms remain consistent.
    #
    # 0.0 = OFF (no decay, Phase 3b behavior).
    shadow_age_penalty_lambda: float = 0.0

    # Normalisation denominator for shadow age-decay (0 = raw, no normalisation).
    # Recommended: set to pending_displacement_ttl_candles (= 4) for Variant B.
    # When > 0: freshness_multiplier = exp(−λ × age / shadow_age_norm_candles)
    shadow_age_norm_candles: int = 0

    # Advisory-only shadow: if True, shadow expansions never produce trades.
    # Shadow still tracks through EXPANSION→RETEST for telemetry; EXECUTION is blocked.
    # Fallback: use when no λ satisfies the composite governance gate.
    shadow_advisory_only: bool = False
```

#### Implementation — age-decay in soft-confirmation path (`process_candle()` RETEST branch)

The decay is applied AFTER `final_S` is computed and BEFORE the `tier_2_threshold` comparison. No changes to expansion entry, state machine, or earlier logic.

```python
# In process_candle(), inside the soft-conf evaluation block:

_effective_S      = final_S
_freshness_mult   = 1.0
_shadow_ctx: dict = {}

if self.state._came_from_shadow:
    _age    = self.state._expansion_entry_idx - self.state._displacement_entry_idx
    _lambda = self.config.shadow_age_penalty_lambda
    _norm   = self.config.shadow_age_norm_candles   # Phase 4b Variant B
    if _lambda > 0.0:
        # Variant B (normalised) when norm > 0; Variant A (raw) when norm == 0
        _age_input      = (_age / _norm) if _norm > 0 else _age
        _freshness_mult = math.exp(-_lambda * _age_input)
        _effective_S    = final_S * _freshness_mult
        if approved and _effective_S < self.config.tier_2_threshold:
            approved = False
            reason   = RejectReason.LOW_SCORE
    _shadow_ctx = {
        "age":                  _age,
        "age_normalised":       round(_age / _norm, 3) if _norm > 0 else None,
        "htf_alignment":        self.state._shadow_htf_alignment,
        "freshness_multiplier": round(_freshness_mult, 4),
        "score_before":         round(final_S, 4),
        "score_after":          round(_effective_S, 4),
        "lambda":               _lambda,
        "norm_candles":         _norm,
        "variant":              "B_normalised" if _norm > 0 else "A_raw",
    }
```

`shadow_context.variant` records which formula was active — "A_raw" or "B_normalised" — so post-run queries can distinguish runs without re-reading the config.

#### `shadow_advisory_only` block (approved, unchanged from original design)

Wire into `process_candle()` after `_effective_S >= tier_2_threshold` passes but before `build_trade()`:

```python
# Phase 4b: shadow advisory gate — block trade execution for shadow-sourced setups
if self.config.shadow_advisory_only and self.state._came_from_shadow:
    emit_integrity_event("SHADOW_ADVISORY_BLOCK", "INFO", "crt_engine", {
        "candidate_id":        f"CAND-{self.state._expansion_entry_idx}",
        "score_before":        round(final_S, 4),
        "score_after":         round(_effective_S, 4),
        "freshness_multiplier": round(_freshness_multiplier, 4),
        "candle_index":        candle.index,
    })
    self.sm.reset_to_range(self.state, "shadow_advisory_only", candle, self.ev_log)
    action["action"] = "SHADOW_ADVISORY_BLOCK"
    return action
```

#### Telemetry additions to CANDIDATE_LIFECYCLE (approved)

Add `shadow_context` dict and `shadow_displacement_body_ratio` to `on_candidate_opened()` / `on_candidate_accepted()` / CANDIDATE_LIFECYCLE flush:

```python
# In on_candidate_accepted(), extend signature:
def on_candidate_accepted(
    self, candle_index: int, score_at_approval: float = 0.0,
    shadow_context: Optional[dict] = None,          # Phase 4b
    shadow_displacement_br: float = 0.0,            # Phase 4b (body_ratio of pending disp candle)
) -> None:
    if self._active_candidate is not None:
        self._active_candidate["score_at_approval"]       = score_at_approval
        self._active_candidate["shadow_context"]          = shadow_context or {}
        self._active_candidate["shadow_displacement_br"]  = shadow_displacement_br
        self._close_candidate(candle_index, "ACCEPTED")
```

`shadow_displacement_body_ratio` is computed at the SHADOW_EXPANSION_CONFIRMED path:
```python
# When state._came_from_shadow == True and expanding:
_pdc = state.pending_displacement_candle
_shadow_br = abs(_pdc.close - _pdc.open) / (_pdc.high - _pdc.low) if _pdc and (_pdc.high - _pdc.low) > 0 else 0.0
```

CANDIDATE_LIFECYCLE flush includes both fields. No gate on `shadow_displacement_body_ratio` in Phase 4b — telemetry only for Phase 5 training label.

`shadow_htf_alignment: Optional[bool]` is stored on `EngineState` at shadow expansion entry (set in `try_shadow_pending_to_expansion()`), then read at soft-conf time for the `shadow_context` dict. Add field to `EngineState`:
```python
    _shadow_htf_alignment: Optional[bool] = None   # Phase 4b
```

#### Experiment Matrix

Two variants. All shadows are at `candidate_age_at_entry=4` (invariant from Phase 3b). 

**Variant A — raw (norm=0): `exp(−λ × age)`**

| Run | λ | `norm` | Penalty at age=4 | Avg eff_S | Note |
|---|---|---|---|---|---|
| A0 | 0.00 | 0 | 1.000 | 0.551 | Baseline — Phase 3b reproduced |
| A1 | 0.10 | 0 | 0.670 | 0.369 | Weak shadows cut (S < 0.448 fails) |
| A2 | 0.20 | 0 | 0.449 | 0.247 | Most shadow cut (need S > 0.668) |
| A3 | 0.35 | 0 | 0.247 | 0.136 | ≈ advisory_only; all shadow S fails |

**Variant B — normalised (norm=4): `exp(−λ × age/4)`**

Same penalty levels as A, but λ is now interpretable: "λ=1.0 → at max shadow age, score × 1/e."

| Run | λ | `norm` | Penalty at age=4 | Equiv to A-run | Note |
|---|---|---|---|---|---|
| B1 | 0.40 | 4 | 0.670 | = A1 | Same penalty, semantically bounded λ |
| B2 | 0.80 | 4 | 0.449 | = A2 | |
| B3 | 1.39 | 4 | 0.247 | = A3 | ≈ advisory_only |

**A/B comparison rule**: Runs with identical penalties (A1≡B1, A2≡B2, A3≡B3) should produce identical trade outcomes. If they differ, there is an implementation bug in the normalization path. If they match: normalization is a clean reparametrization, adopt Variant B for all future λ tuning.

Decision gate after experiments:
- Read inspection table (below) first, not PnL.
- If any run achieves composite gate: adopt lowest λ that passes, use that variant's form.
- If no run achieves composite gate: set `shadow_advisory_only: True`.

#### Composite Promotion Gate (replaces weak `shadow_avg_rr >= 0`)

Shadow passes governance when ALL three hold:
1. `shadow_avg_rr >= 0` (net positive expected value)
2. `shadow_wr >= normal_wr - 10%` (win-rate not more than 10pp below normal)
3. `shadow_max_dd <= baseline_max_dd` (drawdown does not exceed Phase 3b 9.23R baseline)

If any condition fails, escalate λ to the next level.

#### Primary Post-Run Inspection Table

Read this table BEFORE PnL summary. The question is: **does shadow quality improve before shadow quantity collapses?**

| Run | λ | norm | shadow_n | shadow_RR | normal_n | normal_RR | total_DD | approval_rate | shadow_quality_improves |
|---|---|---|---|---|---|---|---|---|---|
| A0 | 0.00 | 0 | 22 | −0.290 | 15 | +0.314 | 9.23R | 100% | baseline |
| A1 | 0.10 | 0 | 22 | −0.290 | 15 | +0.314 | 9.23R | 100% | ❌ FALSE — no change (penalty ×0.670 above floor) |
| A2 | 0.20 | 0 | 4  | −0.394 | 15 | +0.336 | 3.18R | 100% | ❌ FALSE — RR WORSENS as n collapses |
| A3 | 0.35 | 0 | 0  | n/a    | 15 | +0.328 | 2.08R | 100% | ❌ FALSE — all shadow eliminated (≡ advisory_only) |
| B1 | 0.40 | 4 | 22 | −0.290 | 15 | +0.314 | 9.23R | 100% | ✅ A1≡B1 parity confirmed |
| B2 | 0.80 | 4 | 4  | −0.394 | 15 | +0.336 | 3.18R | 100% | ✅ A2≡B2 parity confirmed |
| B3 | 1.39 | 4 | 0  | n/a    | 15 | +0.328 | 2.08R | 100% | ✅ A3≡B3 parity confirmed |

**VERDICT (2026-05-28)**: shadow_quality_improves = FALSE for all λ. `shadow_advisory_only = True` applied to production config.

**Normal_n and normal_RR should be stable across all runs** (decay applies only to shadow). If normal stats shift between runs, there is a bug in the shadow-conditional guard.

**Interpretation key**:
- `shadow_quality_improves = True` when `shadow_RR` rises toward 0 as `shadow_n` falls — decay is selecting better shadow candidates.
- `shadow_quality_improves = False` when `shadow_RR` stays near −0.29 even as `shadow_n` collapses — decay is acting as pure threshold shifting (all shadows are equally bad; cutting them by score makes no quality difference).
- If `shadow_quality_improves = False` for all λ: adopt `shadow_advisory_only = True`. Shadow quality problem is structural (all shadows from stale context), not filterable by score.

```powershell
# Run after each backtest — fill one row of the inspection table:
$tel     = Get-Content "results\run_*\BNBUSDT_M15_crt_telemetry.jsonl" | ForEach-Object { $_ | ConvertFrom-Json }
$trades  = Import-Csv "results\run_*\BNBUSDT_M15_trades.csv"
$accepted = $tel | Where-Object { $_.kind -eq "CANDIDATE_LIFECYCLE" -and $_.death_reason -eq "ACCEPTED" }
$shadow_acc = $accepted | Where-Object { $_.shadow_used -eq $true }
$normal_acc = $accepted | Where-Object { $_.shadow_used -eq $false }

# shadow_n, normal_n
"shadow_n=$($shadow_acc.Count)  normal_n=$($normal_acc.Count)"

# shadow_RR and normal_RR from trades (join on candidate_id or use shadow_used from telemetry)
$shadow_ids  = $shadow_acc.candidate_id
$shadow_rr   = ($trades | Where-Object { $shadow_ids -contains "CAND-$($_.entry_candle_idx)" }).pnl_rr_net |
               Measure-Object -Average | Select-Object -ExpandProperty Average
$normal_rr   = ($trades | Where-Object { $shadow_ids -notcontains "CAND-$($_.entry_candle_idx)" }).pnl_rr_net |
               Measure-Object -Average | Select-Object -ExpandProperty Average
"shadow_RR=$shadow_rr  normal_RR=$normal_rr"

# total_DD from report.txt
Select-String "Max drawdown" "results\run_*\BNBUSDT_M15_report.txt"

# approval_rate
"approval_rate=$($accepted.Count) / $($tel | Where-Object { $_.kind -eq 'CANDIDATE_LIFECYCLE' }).Count"

# A/B parity check (B-run only): variant field in shadow_context
$variant = ($shadow_acc | Select-Object -First 1).shadow_context.variant
"formula_variant=$variant"
```

---

### Updated Promotion Gates

> **Phase 4b result (2026-05-28):** shadow_advisory_only=True. Shadow gates below are vacuously satisfied (0 shadow trades). Normal-only baseline: 15 trades, WR=60%, avg_RR=+0.328, DD=2.08R.

| Gate | Condition | Phase 4b (advisory_only=True) | Status |
|---|---|---|---|
| `temporal: max_expansion_days < 7` | `max * 15/60/24 < 7` | 5.17 days | ✅ |
| `shadow_avg_rr >= 0` | shadow trades net positive | 0 shadow trades — vacuous | ✅ (vacuous) |
| `shadow_wr >= normal_wr − 10%` | shadow WR within 10pp of normal | 0 shadow trades — vacuous | ✅ (vacuous) |
| `shadow_max_dd <= baseline_dd` | shadow DD ≤ 9.23R baseline | 0 shadow trades — vacuous | ✅ (vacuous) |
| `shadow_share < 50%` | shadow not majority of trades | 0/15 = 0% | ✅ |
| `freshness_penalty_mean > 0.7` | decay not too aggressive | N/A (advisory_only) | N/A |
| `normal_avg_rr >= 0` | normal trades positive | +0.328R | ✅ |
| `max_dd < 5R` | total drawdown controlled | 2.08R | ✅ |
| `UNBOUNDED_STATE = 0` | | 0 | ✅ |
| `TEMPORAL_PARADOX = 0` | | 0 | ✅ |
| `SHADOW_LEAK = 0` | | 0 | ✅ |
| `expired_share < 10%` | 7/202 = 3.5% | 3.5% | ✅ |
| `approval_rate < 95%` | 100% (pre-existing) | 100% | ❌ Pre-existing |

**Note on `freshness_penalty_mean > 0.7`**: at Variant A λ=0.10, age=4, mean=0.67 (just misses). At Variant B λ=0.40, age/4=1.0, mean=exp(-0.40)=0.67 (same). This gate checks that the lambda is not so aggressive it collapses all signal. If the adopted λ causes `freshness_penalty_mean < 0.7`, the gate fails and shadow_advisory_only is required.

**Note on `approval_rate = 100%` (deferred to Phase 5 — decision selectivity)**: Score modifies but does not govern. The engine can now: discover → remember → age → expire. But it barely chooses: `tier_2_threshold=0.30` is below all candidate score floors (floor ≈0.44), making the decision layer a pass-through. Phase 5 scope: raise threshold until approval_rate < 95%, calibrate tier_1/tier_2 split against realised RR by tier. Do NOT move there yet — N is too small for threshold recalibration until shadow governance is resolved.

---

### Blast Radius (Phase 4b)

| Change | Behavior | Risk |
|---|---|---|
| `shadow_age_penalty_lambda: 0.0` in CRTConfig | New config key; 0.0 = no change | Low |
| `shadow_age_norm_candles: 0` in CRTConfig | New config key; 0 = Variant A (no norm) | Low |
| `shadow_advisory_only: False` in CRTConfig | New config key; False = no change | Low |
| Age-decay in soft-conf approval path | Reduces `effective_S` for shadow candidates | Medium — intended |
| Variant B normalisation (`norm > 0`) | Changes λ → age/norm interpretation | Low — reparametrization |
| `shadow_context.variant` field | "A_raw" or "B_normalised" in telemetry | Low |
| `shadow_context` dict in CANDIDATE_LIFECYCLE | Telemetry only | Low |
| `shadow_displacement_br` in CANDIDATE_LIFECYCLE | Telemetry only | Low |
| `_shadow_htf_alignment` on EngineState | Set at expansion entry, read at soft-conf | Low |
| `SHADOW_ADVISORY_BLOCK` in TRADE_OPENED path | Blocks shadow trades if advisory_only=True | High — hard block |
| No change to `try_shadow_pending_to_expansion()` | Shadow path entry unchanged | None |

---

## Phase 3b Gate — expired_counterfactual_rr (Promotion Blocker)

### Context

Phase 3b implemented a 495-candle TTL guard that expired 7 expansion episodes. The promotion gate requires computing `expired_counterfactual_rr` — a post-hoc simulation answering: **"did TTL remove alpha, or did it correctly cut stale structure?"**

This is a post-processing script only. No engine changes. Output feeds the Phase 3b promotion blocker.

### Data Sources

| Source | Path | Role |
|---|---|---|
| Phase 3b telemetry | `results/run_20260527_134013_BNBUSDT_M15/BNBUSDT_M15_crt_telemetry.jsonl` | Canonical list of 7 expired candidates (EXPANSION_RETRACE_CHECK, ended_by=expired); provides ceiling_at_max |
| Integrity log | `logs/integrity_events.jsonl` | EXPANSION_EXPIRED events (would_trade_if_alive, score, source); 63 total — must filter to Phase 3b run via telemetry |
| M15 CSV | `data/BNBUSDT_M15.csv` | OHLCV rows indexed by candle_index. Columns: timestamp,open,high,low,close,volume |
| Trades CSV | `results/run_20260527_134013_BNBUSDT_M15/BNBUSDT_M15_trades.csv` | Actual trade outcomes for comparison baseline |

### 7 Expired Candidates (Phase 3b canonical)

Recovered from EXPANSION_RETRACE_CHECK records with ended_by=expired:

| candidate_id | episode_start | expiry_candle | source | retest_depth_pct | retest_distance_abs |
|---|---|---|---|---|---|
| CAND-7992 | 7992 | 8488 | normal | 17.25 | 0.0 |
| CAND-13056 | 13056 | 13552 | shadow | 0.0 | 0.8 |
| CAND-26676 | 26676 | 27172 | normal | 0.0 | 0.8 |
| CAND-27492 | 27492 | 27988 | shadow | 61.65 | 0.0 |
| CAND-50488 | 50488 | 50984 | normal | 17.45 | 0.0 |
| CAND-56680 | 56680 | 57176 | shadow | 15.863 | 0.0 |
| CAND-69439 | 69439 | 69935 | shadow | 6.737 | 0.0 |

Note on `retest_depth_pct`: computed as `telemetry._expansion_max_depth / config.retest_depth_max` (uses raw config fraction, not ATR-scaled). High value = depth already exceeded raw threshold (adaptive ceiling different). Low/zero = depth never reached raw threshold.
Note on `retest_distance_abs = 0.0`: depth already past the raw config threshold (adaptive ATR ceiling may still reject).

### Algorithm

```
Script: scripts/analysis/p5a_expired_counterfactual_rr.py

Constants from production config:
  retest_depth_max: 0.3
  retest_atr_depth_fraction: 0.5
  ATR_PERIOD: 14
  SCAN_WINDOW: 200     # candles to scan forward from expiry
  EXIT_WINDOW: 100     # candles to scan for SL/TP hit
  SL_MULT: 1.0         # ATR multiplier for SL (legacy_sl_atr_mult from production config)
  MIN_RR: 1.5          # TP = entry + MIN_RR × (entry − SL) (min_rr_ratio from production config)

Step 1 — Load data:
  candles = pd.read_csv("data/BNBUSDT_M15.csv", parse_dates=["timestamp"])
  candles["ATR14"] = compute_atr(candles, period=14)  # rolling 14-period True Range
  
Step 2 — Load Phase 3b telemetry, build expired_episodes dict:
  For each EXPANSION_RETRACE_CHECK record with ended_by="expired":
    key = episode_start_idx
    value = {ceiling_at_max, episode_end_idx, shadow_used}
  (Should yield exactly 7 entries from Phase 3b run)

Step 3 — Load integrity_events.jsonl, filter to Phase 3b candidates:
  For each EXPANSION_EXPIRED event where candidate_id in expired_episodes:
    Merge: would_trade_if_alive, score, source fields

Step 4 — For each expired candidate:
  a. Get displacement_candle = candles.iloc[episode_start_idx]
  b. Determine direction:
       direction = LONG if displacement_candle.close < displacement_candle.open else SHORT
       (bearish displacement candle → LONG trade setup; bullish → SHORT)
  c. Set range reference approximation:
       l_ref = displacement_candle.low   (LONG)
       h_ref = displacement_candle.high  (SHORT)
  d. Use ceiling_at_max from telemetry as forward_ceiling
     (ATR-scaled at moment of max depth; constant approximation for post-expiry period)
  
Step 5 — Forward scan from episode_end_idx+1 to episode_end_idx+SCAN_WINDOW:
  retest_found = False
  for j in range(episode_end_idx+1, min(episode_end_idx+SCAN_WINDOW, len(candles))):
    c = candles.iloc[j]
    if direction == LONG:
      depth = c.close - l_ref
      structure_broken = c.close < l_ref      # price broke back below range ref → invalid
    else:
      depth = h_ref - c.close
      structure_broken = c.close > h_ref      # price broke back above range ref → invalid
    
    if structure_broken:
      break  # candidate structure failed; no trade
    
    if 0 <= depth < forward_ceiling:
      # RETEST FIRES — simulate trade
      entry = c.close
      atr_j = candles["ATR14"].iloc[j]
      sl = (l_ref - atr_j * SL_MULT) if direction == LONG else (h_ref + atr_j * SL_MULT)
      risk = abs(entry - sl)
      tp = entry + MIN_RR * risk if direction == LONG else entry - MIN_RR * risk
      
      # Scan for SL/TP hit
      rr = simulate_exit(candles, j+1, j+EXIT_WINDOW, sl, tp, direction)
      # rr = +MIN_RR if TP hit, -1.0 if SL hit, 0 if neither (time exit)
      retest_found = True
      break
  
  if not retest_found:
    rr = None  # No retest in SCAN_WINDOW

Step 6 — Report:
  Print table: candidate_id | source | ceiling | direction | found_retest | rr | entry_candle
  Summary:
    n_counterfactual = count(found_retest=True)
    mean_counterfactual_rr = mean(rr for found_retest=True)
    n_normal_cf = count(source=normal and found_retest=True)
    n_shadow_cf = count(source=shadow and found_retest=True)
    mean_normal_cf_rr = mean(rr for normal counterfactuals)
    mean_shadow_cf_rr = mean(rr for shadow counterfactuals)
    
  Compare vs actual trades:
    Load trades CSV, compute actual mean_rr
    Print: "TTL removed alpha?" verdict based on mean_counterfactual_rr sign
```

### Approximations (explicitly noted in script header)

| Approximation | Source of error | Direction of bias |
|---|---|---|
| direction from displacement candle close vs open | Engine uses full sweep/displacement confirmation | Possible misclassification |
| l_ref/h_ref from displacement candle low/high | Engine uses range reference from HTF-defined range | May differ from actual range boundary |
| forward_ceiling = ceiling_at_max from telemetry | ATR changes post-expiry; ceiling_at_max is from peak depth moment | Could over- or under-filter |
| ATR14 from rolling TR | Engine uses internal ATR with specific warmup | Small numerical difference |
| SL = 1.0×ATR from entry | Actual SL from execution_planner uses body/ATR combination | SL may be tighter or wider |
| No soft_conf evaluation | Actual engine requires soft confirmation candle | Script may count retests that engine would reject |

Script header must state: "APPROXIMATION — counterfactual simulation; not a backtest replay. Results directional only."

### Output Gate

The promotion gate for Phase 3b is satisfied when this script produces a documented output in `results/run_20260527_134013_BNBUSDT_M15/BNBUSDT_M15_phase3b_report.md` containing:
- The 7-candidate table
- `n_counterfactual_trades`, `mean_counterfactual_rr`
- Verdict: "TTL removed alpha: YES/NO/UNCERTAIN"
- Split: normal_cf_rr vs shadow_cf_rr (shadow_advisory_only=True makes the shadow result moot for production, but documents TTL impact on each source)

### Script Arguments

```
python scripts/analysis/p5a_expired_counterfactual_rr.py
  --telemetry results/run_20260527_134013_BNBUSDT_M15/BNBUSDT_M15_crt_telemetry.jsonl
  --integrity-log logs/integrity_events.jsonl
  --data data/BNBUSDT_M15.csv
  --trades results/run_20260527_134013_BNBUSDT_M15/BNBUSDT_M15_trades.csv
  --scan-window 200
  --exit-window 100
  --sl-mult 1.0
  --rr-target 1.5
  [--output results/run_20260527_134013_BNBUSDT_M15/BNBUSDT_M15_phase3b_report.md]
```

### Verification

```powershell
# Confirm 7 candidates found in telemetry
python scripts/analysis/p5a_expired_counterfactual_rr.py --telemetry ... --dry-run
# Output should show exactly 7 expired episodes from the telemetry file

# Full run
python scripts/analysis/p5a_expired_counterfactual_rr.py --telemetry ... --data ... --integrity-log ... --trades ...

# Check output file exists
Test-Path "results\run_20260527_134013_BNBUSDT_M15\BNBUSDT_M15_phase3b_report.md"
```

---

## Phase 5 — Decision Selectivity

### Architecture State After Phase 4b

| Layer | Role | Status |
|---|---|---|
| CRT structure discovery | finds displacement + expansion candidates | ✅ stable |
| TTL guard (Phase 3b) | expires stale structure | ✅ stable |
| Shadow governance (Phase 4b) | blocks stale execution confidence | ✅ stable (advisory_only) |
| **Decision selectivity (Phase 5)** | **ranks valid structure** | ← current frontier |

**Core insight**: "S-scores overlap completely" means current score measures **local pattern quality**, not **market state continuity**. The engine has good structure memory but weak execution ranking. Phase 5 creates meaningful rejection — not fewer trades for its own sake, but trades ranked by market state quality.

**Critical constraint**: Do NOT raise `tier_2_threshold` globally before replay sweep. `normal_avg_rr = +0.328` is the first healthy stable baseline. Global tightening risks destroying it before understanding what the threshold is actually cutting.

**Phase 5 goal**: `approval_rate: 95% → 70–85%` without degrading `normal_avg_rr`.

---

### Phase 5a — Replay Selectivity Sweep

**Mechanism**: backtest experiment sweep only — no live config changes. Mirror structure of Phase 4b lambda sweep.

**Experiment matrix**: `tier_2_threshold ∈ [0.44, 0.48, 0.50, 0.52, 0.55, 0.58, 0.60]`

Rationale for range: candidate score floor ≈ 0.44 (Phase 3b data). Start just above the floor where first rejections appear.

For each run, measure:

| threshold | approvals | approval_rate | WR | avgRR | DD | selectivity_improves |
|---|---|---|---|---|---|---|
| 0.44 | TBD | TBD | TBD | TBD | TBD | baseline |
| 0.48 | TBD | TBD | TBD | TBD | TBD | ? |
| ... | | | | | | |

**Normal_avgRR must remain ≥ +0.300 across all runs.** If raising threshold hurts avgRR, selectivity is cutting quality candidates — the score space is still not predictive.

**Inspection criterion**: `selectivity_improves = True` when both:
1. `approval_rate` drops meaningfully (≥5pp below baseline)
2. `avgRR` does not fall below +0.300 (no expectancy destruction)

If `selectivity_improves = False` for all levels: score space has no predictive structure yet. Do not lock any threshold. Collect more N.

**Config change for each run** (only `tier_2_threshold` in the JSON, re-hash each time):
```json
"tier_2_threshold": 0.44
```

**Telemetry query after each run**:
```powershell
$tel     = Get-Content "results\run_*\BNBUSDT_M15_crt_telemetry.jsonl" | ForEach-Object { $_ | ConvertFrom-Json }
$cands   = $tel | Where-Object { $_.kind -eq "CANDIDATE_LIFECYCLE" }
$accepted = $cands | Where-Object { $_.death_reason -eq "ACCEPTED" }
$rejected = $cands | Where-Object { $_.death_reason -eq "LOW_SCORE" }
"approvals=$($accepted.Count)  rejections=$($rejected.Count)"
"approval_rate=$([math]::Round($accepted.Count / $cands.Count, 3))"
# avgRR from trades CSV
$trades = Import-Csv "results\run_*\BNBUSDT_M15_trades.csv"
($trades.pnl_rr_net | Measure-Object -Average).Average
```

**Preconditions** (check before running):
- `shadow_advisory_only = True` in config ✅ (Done — Phase 4b)
- Phase 3b Gate (expired_counterfactual_rr) documented ❌ (see above — run script first)
- N current = 15 (minimum viable; run on extended date range for N≥30 if possible)

---

### Phase 5b — Counterfactual Reject Audit

After Phase 5a identifies a candidate threshold, audit what was rejected:

**Mechanism**: For each rejected candidate (`death_reason = "LOW_SCORE"` in CANDIDATE_LIFECYCLE), simulate the outcome IF the trade had been taken.

**New telemetry field** (no engine change — add to post-processing only):
```python
rejected_candidate: {
    "candidate_id":   str,
    "score":          float,         # score_at_approval (below threshold)
    "shadow":         bool,          # shadow_used
    "threshold":      float,         # tier_2_threshold at run time
    "decision_distance": float,      # abs(score - threshold) — how close to passing
    "outcome_if_taken": float | None # simulated RR (post-processing, same logic as expired_counterfactual_rr)
}
```

**Question answered**: `mean(outcome_if_taken) < 0` → rejection improved expectancy (threshold is working). `mean(outcome_if_taken) > 0` → rejection is cutting good trades (threshold too high).

**Script**: `scripts/analysis/p5b_reject_audit.py` — same simulation logic as `p3b_gate_expired_counterfactual_rr.py` (reuse the forward-scan simulate_exit() function).

---

### Phase 5c — Decision Distance Telemetry

**One code addition** to `TelemetryCollector` in `crt_engine_v2.py`: emit `decision_distance` in CANDIDATE_LIFECYCLE for every candidate (accepted or rejected):

```python
"decision_distance": round(abs(score_at_approval - config.tier_2_threshold), 4)
```

**Why**: Near-misses (`decision_distance < 0.03`) are the most valuable training labels. A candidate that scores 0.52 when threshold=0.50 may behave identically to one scoring 0.48 — but only one gets approved. Tracking decision_distance enables the training pipeline to:
1. Label near-misses separately from clear rejections
2. Avoid training a model on a boundary artifact
3. Calibrate score granularity vs threshold precision

**Additional**: `htf_transition_distance` on EngineState — candles since HTF window rolled at the moment of candidate entry. Currently shadow candidates cluster near the HTF boundary (candidate_age_at_entry=4, invariant). For normal candidates this varies. `htf_transition_distance` diagnoses whether HTF boundary proximity itself is the poison for shadow — independent of the score.

```python
# EngineState new field (Phase 5c)
_htf_transition_distance: int = 0   # candles since HTF rolled at candidate entry (backtest sets this)
```

Set in `BacktestRunner.run()` at SWEEP_DETECTED / SHADOW_PENDING entry:
```python
engine.state._htf_transition_distance = _htf_position - 1  # 0 = HTF just rolled
```

Include in CANDIDATE_LIFECYCLE flush:
```python
"htf_transition_distance": c.get("htf_transition_distance", None)
```

**Expected finding**: if shadow candidates cluster at `htf_transition_distance ≈ 4` and normal candidates cluster at `htf_transition_distance ≈ 0–1`, this confirms that the shadow decay problem is HTF boundary proximity, not displacement staleness. This unlocks a better discriminator for Phase 6 shadow rehabilitation.

---

### Governance Refinements (Required Before Implementation)

These apply to Phase 4b code and Phase 5 telemetry additions. Document them here so they are not lost.

#### Refinement 1 — Rename `_age` variable (Phase 4b code)

**Current** (in soft-conf decay path):
```python
_cand_age = self.state._expansion_entry_idx - self.state._displacement_entry_idx
```

**Renamed to** `_cross_window_distance` (or `_pending_structure_age`):
```python
_cross_window_distance = self.state._expansion_entry_idx - self.state._displacement_entry_idx
```

**Reason**: The name `age` implies temporal freshness. But this value is `{1 for normal, 4 for shadow}` — a discrete indicator of **cross-window displacement memory**, not true elapsed time. Using "age" risks contaminating future learning when the variable is used as a training feature. The decay formula in the shadow_context dict should also rename: `"age"` → `"cross_window_distance"`, `"age_normalised"` → `"cross_window_distance_normalised"`.

#### Refinement 2 — Advisory block ordering (Phase 4b code)

**Current** ordering in `process_candle()` RETEST branch:
```
threshold check (tier_2_threshold) → advisory_block → build_trade
```

**Corrected** ordering:
```
threshold check → candidate_accept (telemetry) → advisory_block → execution
```

**Why**: Advisory suppression is an **execution gate**, not an **approval mutation**. A shadow candidate that clears the threshold but is blocked by `shadow_advisory_only` should be recorded as `ACCEPTED` in telemetry (approved structure) but `NOT_EXECUTED` at execution layer. This keeps `approval_rate` statistics clean — it measures structure quality, not execution policy.

**Implementation**: call `self.telemetry.on_candidate_accepted(...)` BEFORE the `shadow_advisory_only` block. The `SHADOW_ADVISORY_BLOCK` event fires after acceptance. This does not change trade outcomes; it correctly reflects that the candidate was structurally approved before execution was suppressed.

**New field in CANDIDATE_LIFECYCLE**:
```python
"approval_path": "NORMAL" | "SHADOW" | "SHADOW_DECAYED" | "SHADOW_BLOCKED"
```

Logic:
- `NORMAL`: normal candidate, approved, executed
- `SHADOW`: shadow candidate, λ=0 or no decay applied, executed (when advisory_only=False)
- `SHADOW_DECAYED`: shadow candidate, `freshness_multiplier < 1.0`, still approved after decay, executed
- `SHADOW_BLOCKED`: shadow candidate, approved by threshold, blocked by `shadow_advisory_only=True`

This field makes `decision selectivity` traceable across all sub-paths. Phase 5 analysis can then stratify by `approval_path`.

Set `approval_path` in `on_candidate_accepted()` signature:
```python
def on_candidate_accepted(
    self, candle_index: int, score_at_approval: float = 0.0,
    shadow_context: Optional[dict] = None,
    shadow_displacement_br: float = 0.0,
    approval_path: str = "NORMAL",   # Phase 5c
) -> None:
```

#### Refinement 3 — Add `context_source` to shadow_context dict (Phase 4b telemetry)

**Current** `shadow_context` dict:
```python
{"age": ..., "freshness_multiplier": ..., "variant": "A_raw" | "B_normalised", ...}
```

**Add** `context_source` field:
```python
"context_source": "PRIOR_HTF"   # current shadow is always PRIOR_HTF
# Future values: "SAME_HTF" (delayed same-window continuation), "REGIME_CARRY" (HTF regime carryover)
```

**Reason**: "shadow" is currently one subtype — cross-window displacement memory (PRIOR_HTF). Future paths may include:
- delayed same-window continuation (SAME_HTF): displacement fired near HTF boundary, expansion delayed until next candle in same window
- regime carryover (REGIME_CARRY): HTF structural regime persists across multiple windows without new displacement

Tagging `context_source` now avoids training pipeline confusion later when new shadow subtypes emerge.

#### Refinement 4 — Composite gate: minimum shadow N (Phase 4b / Phase 5)

**Add to composite promotion gate**:
```
shadow passes governance when ALL:
1. shadow_avg_rr >= 0
2. shadow_wr >= normal_wr - 10%
3. shadow_max_dd <= baseline_max_dd
4. shadow_n >= 10   ← NEW: prevent single-survivor luck from passing gate 1
```

At N < 10, `shadow_avg_rr >= 0` is trivially achievable by luck (1 winner among 3 survivors passes). The composite gate must require statistical minimum before any λ is adopted.

---

### Phase 5 Promotion Gates

| Gate | Condition | Status |
|---|---|---|
| `expired_counterfactual_rr documented` | Phase 3b Gate closed | ✅ DONE (2026-05-28) |
| `approval_rate < 95%` at adopted threshold | from Phase 5a sweep | ❌ TBD |
| `normal_avg_rr >= +0.300` at adopted threshold | selectivity does not hurt expectancy | ❌ TBD |
| `reject_audit_mean_rr < 0` | Phase 5b confirms rejections are bad trades | ❌ TBD |
| `decision_distance tracked` | Phase 5c telemetry live | ❌ TBD |
| `htf_transition_distance tracked` | Phase 5c telemetry live | ❌ TBD |
| `approval_path tracked` | Phase 5c telemetry live | ❌ TBD |

### Implementation Order

```
Phase 5a (run first):
  1. Run p3b_gate_expired_counterfactual_rr.py (closes Phase 3b promotion blocker)
  2. Score distribution analysis from Phase 3b/4b telemetry
  3. Threshold sweep: 7 backtest runs at tier_2_threshold=[0.44..0.60]
  4. Fill inspection table, find minimum threshold where approval_rate < 95%
  5. Verify normal_avg_rr >= +0.300 at that threshold

Phase 5b (after 5a sweep completes):
  6. p5b_reject_audit.py on winning threshold run
  7. Confirm reject_audit_mean_rr < 0

Phase 5c (parallel with 5b, code additions — INCLUDE governance refinements):
  8. Rename _age → _cross_window_distance in soft-conf path + shadow_context dict
  9. Reorder advisory_block after on_candidate_accepted() call
  10. Add approval_path to on_candidate_accepted() + CANDIDATE_LIFECYCLE flush
  11. Add context_source to shadow_context dict
  12. Add decision_distance to CANDIDATE_LIFECYCLE (1 line, TelemetryCollector)
  13. Add _htf_transition_distance to EngineState + BacktestRunner
  14. Re-run with winning threshold — verify new fields in telemetry

Phase 5 promotion:
  15. Lock tier_2_threshold, set tier_1_threshold (if score cluster exists above)
  16. Re-hash config
  17. Run full validation suite, update promotion gates
```

---

## Phase 3b — PASS INTEGRITY / FAIL PROMOTION (archived)

---

## Context

The 20,115-candle expansion episode is not simply stale memory — it reveals that `candidate lifecycle ≠ market lifecycle`. Before adding any TTL, we must determine whether the episode is:

- **Case A — Genuine stale expansion**: displacement candle was valid; expansion state persisted because price never retraced. Needs TTL expiry.
- **Case B — Accounting bug**: `on_expansion_ended()` was never called (e.g. `ended_by="eof"` dominates). Needs state accounting fix.

Phase 3a adds telemetry to diagnose which case applies. Phase 3b implements the expiry, but only after 3a confirms Case A.

---

## Phase 3a — Temporal Audit (telemetry only, no behavior change)

### Goal

Measure `age_candles`, `age_hours_actual`, `age_hours_estimated`, and `ended_by` for every expansion episode. Distinguish accounting bugs from genuine stale state. Emit `UNBOUNDED_STATE` CRITICAL if any episode is pathologically long.

### Additions to `src/config_layer/crt_engine_v2.py`

#### Edit 1 — Add `_expansion_start_ts` + `_last_expansion_seen_idx/ts` to `TelemetryCollector.__init__` (≈ line 442)

`_last_expansion_seen_idx/ts` must be updated every EXPANSION candle so that the RUN_END closure uses the true last-seen position, not the start position. Without this, long open episodes collapse to zero duration at flush time.

```python
        self._expansion_start_idx: int = 0
        self._expansion_start_ts: Optional[datetime] = None   # Phase 3a — for age_hours_actual
        # Phase 3b RC1: track last candle seen while expansion is active (for correct RUN_END closure)
        self._last_expansion_seen_idx: int = 0
        self._last_expansion_seen_ts: Optional[datetime] = None
```

#### Edit 2 — Extend `on_state_entered()` to capture expansion timestamp; update `on_expansion_retrace_check()` to track last-seen candle (≈ line 462)

```python
def on_state_entered(
    self, state_name: str, candle_index: int,
    candle_ts: Optional[datetime] = None,   # Phase 3a
) -> None:
    ...
    if state_name == "EXPANSION":
        self._expansion_active         = True
        self._expansion_start_idx      = candle_index
        self._expansion_start_ts       = candle_ts          # Phase 3a
        self._last_expansion_seen_idx  = candle_index       # Phase 3b RC1
        self._last_expansion_seen_ts   = candle_ts          # Phase 3b RC1
        self._expansion_max_depth      = 0.0
        self._expansion_ceiling_at_max = 0.0
        self._expansion_time_to_max    = 0
```

Pass `candle_ts` from `StateMachine._transition()` (≈ line 850):
```python
if self.telemetry and candle:
    self.telemetry.on_state_entered(target.name, candle.index, candle_ts=candle.timestamp)
```

Also update `on_expansion_retrace_check()` to keep `_last_expansion_seen_*` current on every EXPANSION candle (≈ line 479):
```python
def on_expansion_retrace_check(
    self, candle_index: int, depth_abs: float, ceiling: float,
    candle_ts: Optional[datetime] = None,   # Phase 3b RC1
) -> None:
    if not self._expansion_active:
        return
    if depth_abs > self._expansion_max_depth:
        self._expansion_max_depth      = depth_abs
        self._expansion_ceiling_at_max = ceiling
        self._expansion_time_to_max    = candle_index - self._expansion_start_idx
    # Phase 3b RC1: track last candle seen during this episode
    self._last_expansion_seen_idx = candle_index
    if candle_ts is not None:
        self._last_expansion_seen_ts = candle_ts
```

Call site in `StateMachine.try_expansion_to_retest()`: add `candle_ts=candle.timestamp` to the `telemetry.on_expansion_retrace_check(...)` call.

#### Edit 3 — Add `ended_by` + dual `age_hours` + new fields to `on_expansion_ended()` (≈ line 490)

```python
def on_expansion_ended(
    self, candle_index: int, reason: str,
    end_ts: Optional[datetime] = None,            # Phase 3a — actual end timestamp
    shadow_used: bool = False,                    # Phase 3a — was this a shadow expansion?
    candidate_age_at_entry: int = 0,              # Phase 3a — candles from displacement → expansion
    age_pct_of_threshold: float = 0.0,           # Phase 3b — age/TTL×100; 0 if no TTL active
) -> None:
    if not self._expansion_active:
        return
    self._expansion_active = False
    dwell = candle_index - self._expansion_start_idx
    self._expansion_dwells.append(dwell)

    # Phase 3a: ended_by taxonomy
    _ended_by = (
        "retest"   if reason == "QUALIFIED"
        else "eof"      if reason == "RUN_END"
        else "expired"  if reason == "EXPIRED"
        else "reset"
    )

    # Phase 3a: dual age_hours — never approximate if actual timestamps available
    _age_estimated = round(dwell * 15 / 60, 2)   # M15 approximation
    _age_actual: Optional[float] = None
    if self._expansion_start_ts is not None and end_ts is not None:
        _age_actual = round(
            (end_ts - self._expansion_start_ts).total_seconds() / 3600.0, 2
        )

    # Phase 3a: emit CLOCK_DRIFT — RC2: INFO@10%, WARN@25% (not WARNING@5%)
    # Markets contain gaps, DST, and exchange timestamp variance; 5% is too aggressive.
    if _age_actual is not None and _age_estimated > 0:
        _drift_pct = abs(_age_actual - _age_estimated) / _age_estimated
        if _drift_pct > 0.10:
            _drift_severity = "WARNING" if _drift_pct > 0.25 else "INFO"
            emit_integrity_event(
                "CLOCK_DRIFT", _drift_severity, "crt_engine",
                {
                    "age_hours_actual":    _age_actual,
                    "age_hours_estimated": _age_estimated,
                    "drift_pct":           round(_drift_pct * 100, 1),
                    "candle_index":        candle_index,
                },
            )

    outcome = (
        "QUALIFIED"   if reason == "QUALIFIED"
        else "RUN_END"     if reason == "RUN_END"
        else "EXPIRED"     if reason == "EXPIRED"
        else "INTERRUPTED"
    )
    self._expansion_records.append({
        "kind":                        "EXPANSION_RETRACE_CHECK",
        "episode_start_idx":           self._expansion_start_idx,
        "episode_end_idx":             candle_index,
        "duration_candles":            dwell,
        "age_hours_actual":            _age_actual,             # Phase 3a — None if timestamps absent
        "age_hours_estimated":         _age_estimated,          # Phase 3a — M15 approximation
        "ended_by":                    _ended_by,               # Phase 3a
        "shadow_used":                 shadow_used,             # Phase 3a
        "candidate_age_at_entry":      candidate_age_at_entry,  # Phase 3a
        "age_pct_of_threshold":        age_pct_of_threshold,             # Phase 3b — 0.0 if no TTL active
        "freshness_ratio":             round(age_pct_of_threshold / 100.0, 3),  # RC5: 0.20=fresh, 1.20=stale
        "outcome":                     outcome,
        # ... existing fields (max_retrace_depth_abs etc.) unchanged
    })
```

**Pass new args from callers:**

In `StateMachine._transition()`, when calling `on_expansion_ended` via RETEST entry (≈ line 851):
```python
if target == CRTState.RETEST and self.telemetry._expansion_active:
    self.telemetry.on_expansion_ended(
        candle.index, "QUALIFIED",
        end_ts=candle.timestamp,
        shadow_used=state._came_from_shadow,
        candidate_age_at_entry=(
            state._expansion_entry_idx - state._displacement_entry_idx
        ),
    )
```
Add `_expansion_entry_idx: int = 0` to `EngineState` now (needed for `candidate_age_at_entry`):
```python
    _expansion_entry_idx: int = 0   # Phase 3a — set in _transition() when EXPANSION entered
```
Set it in `_transition()` when `target == CRTState.EXPANSION`:
```python
        if target == CRTState.EXPANSION and candle:
            state._expansion_entry_idx = candle.index
```

In `TelemetryCollector.on_reset()` → `on_expansion_ended` (≈ line 562, inside `on_reset` or wherever `from_state == "EXPANSION"` fires):
```python
        if from_state == "EXPANSION":
            self.on_expansion_ended(
                candle_index, reason,
                end_ts=candle_ts,            # pass candle.timestamp here
                shadow_used=shadow_used,      # pass from reset context
                candidate_age_at_entry=candidate_age_at_entry,
            )
```
Extend `on_reset()` signature with `candle_ts`, `shadow_used`, `candidate_age_at_entry` (all `Optional`/`= 0` defaults). Call site in `reset_to_range()` passes `candle.timestamp`, `state._came_from_shadow`, and `(state._expansion_entry_idx - state._displacement_entry_idx)`.

In `flush()` for `RUN_END` case (≈ line 670) — **RC1 fix: use `_last_expansion_seen_idx/ts`, not `_expansion_start_idx`**:
```python
        if self._expansion_active:
            # RC1: use last-seen candle, not start candle — avoids collapsing long open episodes
            self.on_expansion_ended(
                self._last_expansion_seen_idx, "RUN_END",
                end_ts=self._last_expansion_seen_ts,
            )
```

#### Edit 4 — `UNBOUNDED_STATE` integrity event in `flush()` with revised threshold (≈ line 680) — **RC3**

Threshold: `max(P95×3, median×25)` — P99 with small N is self-referential (it may already contain the anomaly, making `P99×2` ineffective at detecting it).

```python
if len(_dwells) >= 10:
    _sorted_d  = sorted(_dwells)
    _p95       = _sorted_d[int(0.95 * len(_sorted_d))]   # RC3: use P95, not P99
    _median    = _statistics.median(_dwells)
    _threshold = max(_p95 * 3, _median * 25)              # RC3: P95×3 / median×25
    _unbounded = [d for d in _dwells if d > _threshold]
    if _unbounded:
        emit_integrity_event(
            "UNBOUNDED_STATE", "CRITICAL", "crt_engine",
            {
                "state":     "EXPANSION",
                "p95":       _p95,
                "median":    _median,
                "threshold": _threshold,
                "offenders": _unbounded,
            },
        )
```

#### Edit 5 — Add P99 + `ended_by_counts` to `expansion_dwell_stats` in `flush()` (extend existing block)

```python
_dwell_stats: dict = {
    "count":   len(_dwells),
    "mean":    round(_statistics.mean(_dwells), 1)    if _dwells else 0,
    "median":  round(_statistics.median(_dwells), 1)  if _dwells else 0,
    "p90":     _sorted_d[int(0.90 * len(_sorted_d))] if len(_dwells) >= 10 else 0,
    "p99":     _sorted_d[int(0.99 * len(_sorted_d))] if len(_dwells) >= 10 else 0,  # Phase 3a
    "max":     max(_dwells, default=0),
    "ended_by_counts": {   # Phase 3a — key diagnostic for Case A vs B
        "retest":  sum(1 for r in self._expansion_records if r.get("ended_by") == "retest"),
        "reset":   sum(1 for r in self._expansion_records if r.get("ended_by") == "reset"),
        "eof":     sum(1 for r in self._expansion_records if r.get("ended_by") == "eof"),
        "expired": sum(1 for r in self._expansion_records if r.get("ended_by") == "expired"),
    },
}
```

### Decision after Phase 3a re-run

```powershell
$tel = Get-Content "results\BNBUSDT\run_*\BNBUSDT_crt_telemetry.jsonl" | ForEach-Object { $_ | ConvertFrom-Json }

# 1. ended_by distribution — primary Case A/B diagnostic
$eps = $tel | Where-Object { $_.kind -eq "EXPANSION_RETRACE_CHECK" }
$eps | Group-Object ended_by | Select-Object Name, Count

# 2. Shadow-correlated long expansions?
$eps | Sort-Object duration_candles -Descending | Select-Object -First 5 | Format-Table episode_start_idx, duration_candles, ended_by, shadow_used, candidate_age_at_entry

# 3. UNBOUNDED_STATE integrity event
Get-Content "logs\integrity_events.jsonl" | ConvertFrom-Json | Where-Object { $_.event_type -eq "UNBOUNDED_STATE" }

# 4. CLOCK_DRIFT check
Get-Content "logs\integrity_events.jsonl" | ConvertFrom-Json | Where-Object { $_.event_type -eq "CLOCK_DRIFT" }

# 5. P99 and ended_by_counts
($tel | Where-Object { $_.kind -eq "TRANSITION_COUNTER" }).expansion_dwell_stats
```

**Decision gate — three cases:**

| Observation | Conclusion | Next action |
|---|---|---|
| `ended_by=eof` count ≥ 2 | **Case A — accounting bug**: `on_expansion_ended` not called at non-EOF exits | Fix closure before any TTL |
| `ended_by=eof` = 1 AND age extreme = 1 episode | **Case B — genuine stale expansion** | Proceed with Phase 3b |
| `ended_by=retest` dominant AND P99 small | **Case C — no pathology** | No TTL needed; promote |

---

## Phase 3b — Expiry (✅ IMPLEMENTED — PASS INTEGRITY / FAIL PROMOTION)

> **5 required changes from final reviews:**
> 1. RUN_END closure must use `_last_expansion_seen_idx/ts`, not `_expansion_start_idx`
> 2. CLOCK_DRIFT: INFO if >10%, WARN if >25% (not WARNING at 5%)
> 3. UNBOUNDED_STATE threshold: `max(P95×3, median×25)` (not `max(P99×2, median×20)`)
> 4. **Closure priority hierarchy**: RETEST (4) > EXPIRED (3) > RESET (2) > RUN_END (1) — try retest BEFORE TTL check; document via `_CLOSURE_PRIORITY`
> 5. **Expiry recoverability**: EXPANSION_EXPIRED must carry `retest_distance_abs`, `retest_depth_pct`, `freshness_ratio` so that post-hoc `expired_counterfactual_rr` can be computed
>
> **Promotion blocker**: Do not promote Phase 3b to production until a distribution report exists: P50/P90/P95/P99/MAX of expansion ages, ended_by distribution, and `expired_counterfactual_rr`.
>
> **Additional additions:** `age_pct_of_threshold` + `freshness_ratio` fields on every expansion record; `TEMPORAL_STALE_WIN` WARN event on winning stale trades; pre-expiry promotion gates.

### Phase 3a Diagnosis Summary

| ended_by | Count | Notes |
|---|---|---|
| retest | 66 (71%) | dominant — state accounting is CORRECT |
| reset | 26 (28%) | **all 26 are shadow expansions** |
| eof | 1 (1%) | expected: episode open at run end |
| expired | 0 | Phase 3b not yet active |

**Case B confirmed**: The 20,115-candle episode ended via `retest` (not eof) — no accounting bug. The displacement was normal (not shadow). Shadow expansions self-terminate quickly via retrace resets — they are "probe → invalidate" behaviour. TTL guard was simply absent.

**Shadow not pathological**: All 26 resets are shadow expansions. Normal expansions never reset mid-episode. Shadow path is healthy — it probes and self-corrects.

### TTL Derivation: `min(P99_non_outlier, 7_days)`

From Phase 3a data (N=93 episodes, excluding top 1% outlier → N=92):
- P99 of 92 non-pathological = **495 candles** (≈ 123.75 h ≈ 5.2 days)
- 7 days = 7 × 24 × 4 candles = 672 candles (M15)
- `min(495, 672) = 495` candles

**Frozen config values:**
```json
"max_expansion_age_candles": 495,
"max_expansion_age_hours": 124
```

This expires only the obvious anomaly (20,115 candles). The 5 longest non-pathological episodes (342–495 candles) sit right at the boundary — those at ≤495 candles are legitimate continuation structures. Setting TTL at P99 (not P95) avoids cutting valid episodes on first pass; tighten later once more data accumulates.

### New config keys in `CRTConfig` (after `pending_displacement_ttl_candles`, ≈ line 370)
```python
    # ── Expansion TTL guard (Phase 3b) ────────────────────────────
    # Expire if EITHER limit exceeded. Derived: min(P99_non_outlier, 7d).
    # Phase 3a data: P99=495 candles (123.75h). 7d=672 candles → TTL=495.
    max_expansion_age_candles: int = 495
    max_expansion_age_hours:   int = 124
```

### New `EXPIRED` state in `CRTState` and `VALID_TRANSITIONS`
```python
class CRTState(Enum):
    ...
    EXPANSION      = auto()
    EXPIRED        = auto()   # Phase 3b — soft archive before reset
    RETEST         = auto()
    ...

VALID_TRANSITIONS = {
    ...
    CRTState.EXPANSION: [CRTState.RETEST, CRTState.EXPIRED, CRTState.RANGE],
    CRTState.EXPIRED:   [CRTState.RANGE],
    ...
}
```

### New EngineState fields (after `_came_from_shadow`)
```python
    _expansion_entry_idx: int               = 0    # Phase 3b
    _expansion_entry_ts:  Optional[datetime] = None # Phase 3b
```

Set in `StateMachine._transition()` when `target == CRTState.EXPANSION`.

### Closure priority hierarchy (RC-Closure) — `_CLOSURE_PRIORITY` constant + retest-first ordering

Add near the top of `TelemetryCollector` or as a module-level constant:
```python
# Phase 3b RC-Closure: Closure reason priority — higher wins when multiple apply simultaneously.
# Execution success (RETEST) must dominate; RUN_END is last resort.
_CLOSURE_PRIORITY: dict[str, int] = {
    "QUALIFIED": 4,  # Retest fired — structure delivered
    "EXPIRED":   3,  # TTL guard fired
    "RESET":     2,  # HTF or other reset interrupted
    "RUN_END":   1,  # Flush at end of run
}
```

**Critical ordering change in `process_candle()` EXPANSION branch**: try retest FIRST, then TTL.
If both would apply on the same candle, RETEST (priority=4) must win over EXPIRED (priority=3).

```python
elif s == CRTState.EXPANSION:
    # RC-Closure: RETEST has higher priority than EXPIRED — check first
    if self.sm.try_expansion_to_retest(self.state, candle, self.ev_log):
        action["action"] = "RETEST_QUALIFIED"
        return action

    # ── Phase 3b: Expansion TTL guard (runs only if retest did NOT fire) ────
    _exp_age_c = candle.index - self.state._expansion_entry_idx
    ...
```

**Guard in `on_expansion_ended()`** — defend against out-of-order calls. Add `_expansion_ended_reason: str = ""` field to `TelemetryCollector.__init__`. In `on_expansion_ended()`:
```python
def on_expansion_ended(self, candle_index, reason, ...):
    if not self._expansion_active:
        # Allow higher-priority override (e.g. if RETEST fires after a RUN_END was queued)
        new_prio = _CLOSURE_PRIORITY.get(reason, 0)
        old_prio = _CLOSURE_PRIORITY.get(self._expansion_ended_reason, 0)
        if new_prio <= old_prio:
            return   # Lower or equal priority — ignore
        # Higher priority — fall through to update the last record
        if self._expansion_records:
            last = self._expansion_records[-1]
            # Re-derive ended_by from new reason and patch the record
            last["ended_by"] = (
                "retest" if reason == "QUALIFIED"
                else "eof" if reason == "RUN_END"
                else "expired" if reason == "EXPIRED"
                else "reset"
            )
            last["outcome"] = reason if reason in ("QUALIFIED", "RUN_END", "EXPIRED") else "INTERRUPTED"
        return
    self._expansion_active = False
    self._expansion_ended_reason = reason
    ...  # rest unchanged
```

This ensures the TRANSITION_COUNTER `ended_by_counts` reflects the semantically correct reason even if closure paths fire in unexpected order.

### TTL check in EXPANSION branch in `process_candle()` (after `try_expansion_to_retest` — RC-Closure ordering)

```python
elif s == CRTState.EXPANSION:
    # ── Phase 3b: Expansion TTL guard ───────────────────────────
    _exp_age_c = candle.index - self.state._expansion_entry_idx
    _max_c = self.config.max_expansion_age_candles
    _max_h = self.config.max_expansion_age_hours
    _age_h: float = (_exp_age_c * 15 / 60)  # M15 approximation; use ts delta if available

    if self.state._expansion_entry_ts is not None:
        _age_h = (candle.timestamp - self.state._expansion_entry_ts).total_seconds() / 3600.0

    _ttl_exceeded = (
        (_max_c > 0 and _exp_age_c > _max_c)
        or (_max_h > 0 and _age_h > _max_h)
    )

    if _ttl_exceeded:
        # ── would_trade_if_alive: structural quality of displacement candle ──
        _dc = self.state.displacement_candle
        _would_trade = False
        if _dc is not None:
            _body = abs(_dc.close - _dc.open)
            _rng  = _dc.high - _dc.low
            _br   = _body / _rng if _rng > 0 else 0.0
            _would_trade = _br >= self.config.body_ratio_min

        # freshness_ratio = age/ttl (0.20=fresh, 0.80=aging, 1.20=stale — can exceed 1.0)
        _freshness_ratio = round(_exp_age_c / _max_c, 3) if _max_c > 0 else 0.0
        # age_pct_of_threshold: same value as percentage (100% = exactly at TTL, 120% = 20% over)
        _age_pct = round(_freshness_ratio * 100, 1)

        # Structural G-score snapshot for training label (max_score_seen may be 0 if
        # no retest ever fired; record the body_ratio as the fallback quality signal)
        _body_ratio = 0.0
        if _dc is not None:
            _rng2 = _dc.high - _dc.low
            _body_ratio = abs(_dc.close - _dc.open) / _rng2 if _rng2 > 0 else 0.0

        # RC5 — retest_distance: how close was price to triggering a retest at expiry?
        # Uses telemetry.on_expansion_retrace_check depth data for current depth estimate.
        # current_depth = max retrace seen so far (telemetry._expansion_max_depth)
        # retest_threshold = configured fraction of ATR (retest_depth_max * last ATR)
        # Both are approximations; exact values require state internals from try_expansion_to_retest().
        _current_depth_abs  = self.telemetry._expansion_max_depth   # best available depth proxy
        _retest_threshold   = self.config.retest_depth_max          # config fraction (not ATR-scaled)
        _retest_distance_abs = max(0.0, _retest_threshold - _current_depth_abs)
        _retest_depth_pct    = round(_current_depth_abs / _retest_threshold, 3) if _retest_threshold > 0 else 0.0
        # retest_depth_pct: 0.9 = almost triggered retest; 0.1 = very far from retest

        emit_integrity_event("EXPANSION_EXPIRED", "WARNING", "crt_engine", {
            "candidate_id":          f"CAND-{self.state._expansion_entry_idx}",
            "expansion_age_candles": _exp_age_c,
            "expansion_age_hours":   round(_age_h, 1),
            "source":                "shadow" if self.state._came_from_shadow else "normal",
            "shadow_used":           self.state._came_from_shadow,
            "would_trade_if_alive":  _would_trade,
            "freshness_ratio":       _freshness_ratio,   # RC5: 0.20=fresh, 0.80=aging, 1.20=stale
            "age_pct_of_threshold":  _age_pct,           # e.g. 400/500 → 80.0%
            "retest_distance_abs":   round(_retest_distance_abs, 6),  # RC5: how far from retest trigger
            "retest_depth_pct":      _retest_depth_pct,  # RC5: fraction of way to retest (0-1+)
            "score":                 round(_body_ratio, 4),
            "candle_index":          candle.index,
        })
        self.telemetry.on_expansion_ended(
            candle.index, "EXPIRED",
            end_ts=candle.timestamp,
            shadow_used=self.state._came_from_shadow,
            candidate_age_at_entry=(
                self.state._expansion_entry_idx - self.state._displacement_entry_idx
            ),
            age_pct_of_threshold=_age_pct,   # pass through to EXPANSION_RETRACE_CHECK record
        )
        self.sm._transition(self.state, CRTState.EXPIRED, "expansion_ttl_exceeded", candle, self.ev_log)
        action["action"] = "EXPANSION_EXPIRED"
        return action
    # ... existing try_expansion_to_retest unchanged
```

### `EXPIRED` branch (new `elif` after EXPANSION block)
```python
elif s == CRTState.EXPIRED:
    self.sm.reset_to_range(self.state, "expansion_ttl_exceeded", candle, self.ev_log)
    action["action"] = "EXPANSION_TTL_RESET"
```

### Clear new fields in `reset_to_range()` cleanup block (after `_came_from_shadow`)
```python
        state._came_from_shadow    = False  # [Phase 2b]
        state._expansion_entry_idx = 0      # [Phase 3a/3b]
        state._expansion_entry_ts  = None   # [Phase 3b]
```

### `TEMPORAL_PARADOX` integrity event (Phase 3b — wire into TRADE_OPENED path)

If a trade is opened and `structure_age > max_expansion_age_candles`, the trade is newer than the structure validity window. Emit CRITICAL before allowing execution:

```python
# In process_candle() TRADE_OPENED path, after approval:
_struct_age = candle.index - self.state._expansion_entry_idx
if (self.config.max_expansion_age_candles > 0
        and _struct_age > self.config.max_expansion_age_candles):
    emit_integrity_event(
        "TEMPORAL_PARADOX", "CRITICAL", "crt_engine",
        {
            "candidate_id":     f"CAND-{self.state._expansion_entry_idx}",
            "structure_age":    _struct_age,
            "max_allowed":      self.config.max_expansion_age_candles,
            "shadow_used":      self.state._came_from_shadow,
            "candle_index":     candle.index,
        },
    )
    # Do NOT open the trade — return without TRADE_OPENED action
    return action
```

`TEMPORAL_PARADOX` acts as the last-resort guard: TTL expiry should have caught this first. If TEMPORAL_PARADOX fires, it means the TTL check has a gap.

### `TEMPORAL_STALE_WIN` integrity event (Phase 3b — wire into TRADE_OPENED path, alongside TEMPORAL_PARADOX)

A winning trade opened from an expansion older than P95 is dangerous: it may be hiding a gap in temporal causality even if TTL hasn't expired yet. P95 of non-pathological episodes = 342 candles → add `expansion_age_warn_candles: int = 342` to `CRTConfig`.

```python
# CRTConfig — after max_expansion_age_hours:
expansion_age_warn_candles: int = 342   # P95 from Phase 3a; warn if trade opened above this age
```

Wire into `process_candle()` TRADE_OPENED path (emit AFTER the trade is opened, not instead of it):
```python
# After trade opens successfully (TRADE_OPENED confirmed):
_warn_age = self.config.expansion_age_warn_candles
if _warn_age > 0 and _struct_age > _warn_age:
    emit_integrity_event(
        "TEMPORAL_STALE_WIN", "WARNING", "crt_engine",
        {
            "candidate_id":      f"CAND-{self.state._expansion_entry_idx}",
            "structure_age":     _struct_age,
            "warn_threshold":    _warn_age,
            "shadow_used":       self.state._came_from_shadow,
            "candle_index":      candle.index,
        },
    )
    # Note: trade still executes — this is a WARNING, not a block
```

A `TEMPORAL_STALE_WIN` event in the results log answers: "was this trade from stale structure?" and allows the training pipeline to label these trades separately.

### Pre-expiry promotion gates (verify Phase 3a data before enabling Phase 3b TTL in production)

These confirm the closure system is healthy before activating expiry:

| Gate | Value from Phase 3a | Pass? |
|---|---|---|
| `ended_by[eof] < 5%` | 1/93 = 1.1% | ✅ PASS |
| `max_age_pct < 150%` (non-pathological max / P99_non_outlier) | 495/495 = 100% | ✅ PASS |
| `clock_drift_warn == 0` | 0 | ✅ PASS |

All three pre-expiry gates passed on Phase 3a data. Phase 3b TTL is cleared for production config.

### Promotion Blocker — Distribution Report (required before production deploy)

**Do not promote Phase 3b config to production** until the following report is produced from the Phase 3b verification run. Missing any field = BLOCK.

```powershell
# Run after Phase 3b backtest completes. This is NOT part of the backtest itself.
$tel  = Get-Content "results\run_*\BNBUSDT_crt_telemetry.jsonl" | ForEach-Object { $_ | ConvertFrom-Json }
$iev  = Get-Content "logs\integrity_events.jsonl"               | ForEach-Object { $_ | ConvertFrom-Json }
$eps  = $tel | Where-Object { $_.kind -eq "EXPANSION_RETRACE_CHECK" }
$ages = $eps.duration_candles | Sort-Object

# 1. expansion_age_distribution
[PSCustomObject]@{
    P50 = $ages[[int]($ages.Count * 0.50)];  P90 = $ages[[int]($ages.Count * 0.90)]
    P95 = $ages[[int]($ages.Count * 0.95)];  P99 = $ages[[int]($ages.Count * 0.99)]
    MAX = ($ages | Measure-Object -Maximum).Maximum
} | Format-Table

# 2. ended_by_distribution
$eps | Group-Object ended_by | Select-Object Name, Count | Format-Table

# 3. expired_counterfactual_rr — post-hoc: for each expired episode where would_trade_if_alive=True,
#    scan forward in original CSV from episode_end_idx and check if price reached retest depth.
#    Report: count of would-have-traded, mean RR of those simulated trades vs actual trade mean RR.
$expired = $iev | Where-Object { $_.event_type -eq "EXPANSION_EXPIRED" -and $_.would_trade_if_alive -eq $true }
"expired_with_trade_potential: $($expired.Count)"
# Full counterfactual RR requires Python post-processing script — see Phase 4 verification notes.
```

`expired_counterfactual_rr` is computed by a post-processing script (not the engine) that:
1. Reads all `EXPANSION_EXPIRED` events where `would_trade_if_alive=True`
2. For each, scans forward in the original M15 CSV from `candle_index`
3. Checks if price would have reached the retest depth threshold within 50 candles
4. If yes, simulates the trade using the same SL/TP logic and records the RR
5. Reports: n_counterfactual_trades, mean_counterfactual_rr, vs actual trade mean_rr

**Gate**: `expired_counterfactual_rr` must be computed and documented in `results/run_*/BNBUSDT_phase3b_report.md` before production promotion. This answers: "did TTL remove alpha?"

### Production config update (frozen from Phase 3a P99_non_outlier)
```json
"max_expansion_age_candles": 495,
"max_expansion_age_hours": 124,
"expansion_age_warn_candles": 342
```
Re-hash with `python scripts/maintenance/_compute_hash.py`.

---

## Verification (Phase 3b)

```powershell
$tel = Get-Content "results\run_*\BNBUSDT_crt_telemetry.jsonl" | ForEach-Object { $_ | ConvertFrom-Json }

# 1. EXPANSION_EXPIRED fired (the 20,115-candle episode must be among them)
$expired_eps = $tel | Where-Object { $_.kind -eq "EXPANSION_RETRACE_CHECK" -and $_.ended_by -eq "expired" }
$expired_eps.Count   # must be >= 1

# 2. max expansion days < 7 (promotion gate — 495 candles = 5.2 days < 7)
$tc = $tel | Where-Object { $_.kind -eq "TRANSITION_COUNTER" }
"max_days = $(($tc.expansion_dwell_stats.max * 15) / 60 / 24)"   # must be < 7.0

# 3. Trade count (the 20,115-episode produced 1 trade — it should be lost after 3b)
$trades = Import-Csv "results\run_*\BNBUSDT_trades.csv"
$trades.Count   # expect 13 (was 14; 1 trade from pathological episode removed)

# 4. shadow_share (< 60% raised from 50% — Phase 3a confirmed shadow not pathological)
"shadow_share = $([int]($trades | Where-Object { $_.shadow_used -eq '1' }).Count / [math]::Max($trades.Count,1))"

# 5. approval_rate
$cands = $tel | Where-Object { $_.kind -eq "CANDIDATE_LIFECYCLE" }
"approval_rate = $($cands | Where-Object { $_.death_reason -eq 'ACCEPTED' }).Count / [math]::Max($cands.Count,1)"

# 6. UNBOUNDED_STATE and TEMPORAL_PARADOX must both be 0
Get-Content "logs\integrity_events.jsonl" | ConvertFrom-Json | 
    Where-Object { $_.event_type -in @("UNBOUNDED_STATE","TEMPORAL_PARADOX") } | 
    Measure-Object | Select-Object Count   # must be 0

# 7. SHADOW_LEAK still 0 (regression check from Phase 1)
Get-Content "logs\integrity_events.jsonl" | ConvertFrom-Json | 
    Where-Object { $_.event_type -eq "SHADOW_LEAK" } | Measure-Object | Select-Object Count

# 8. Closure priority — verify no RETEST was replaced by EXPIRED (ended_by=retest must dominate)
$expired_eps = $tel | Where-Object { $_.kind -eq "EXPANSION_RETRACE_CHECK" -and $_.ended_by -eq "expired" }
$retest_eps  = $tel | Where-Object { $_.kind -eq "EXPANSION_RETRACE_CHECK" -and $_.ended_by -eq "retest" }
"retest=$($retest_eps.Count)  expired=$($expired_eps.Count)  (retest must exceed expired)"

# 9. freshness_ratio and retest_distance fields present on expired episodes (RC5)
$expired_eps | Select-Object -First 1 | Format-List freshness_ratio, retest_distance_abs, retest_depth_pct

# 10. Promotion blocker: distribution report fields present
($tel | Where-Object { $_.kind -eq "TRANSITION_COUNTER" }).expansion_dwell_stats | 
    Format-List count, mean, median, p90, p99, max, ended_by_counts
```

---

## Promotion Gates

| Gate | Pass condition | Severity | Notes |
|---|---|---|---|
| `max_expansion_days < 7` | `max * 15 / 60 / 24 < 7` | Hard | TTL at 495 candles (5.2d) must cap worst case under 7 days |
| `UNBOUNDED_STATE = 0` | No records in `integrity_events.jsonl` | Hard | After 3b TTL is active; any hit = replay not trustworthy |
| `TEMPORAL_PARADOX = 0` | No records after 3b active | Hard | No trade should survive past its structure TTL |
| `approval_rate < 95%` | `accepted / total < 0.95` | Hard | Decision layer must be binding before promotion |
| `shadow_share < 60%` | `shadow_trades / total < 0.60` | Soft | Raised from 50%: Phase 3a confirmed shadow is not pathological |
| `SHADOW_LEAK = 0` | Preserved from Phase 1 | Hard | No regression on shadow integrity |

---

## Blast Radius

| Change | Phase | Behavior change | Risk |
|---|---|---|---|
| `on_state_entered(candle_ts=)` signature | 3a | None | Low |
| `_expansion_start_ts` tracking | 3a | None | Low |
| `ended_by` + `age_hours` in EXPANSION_RETRACE_CHECK | 3a | None (telemetry only) | Low |
| P99 + `ended_by_counts` in TRANSITION_COUNTER | 3a | None (telemetry only) | Low |
| `UNBOUNDED_STATE` integrity event | 3a | Logs CRITICAL to `integrity_events.jsonl` | Low |
| `_CLOSURE_PRIORITY` constant + retest-first ordering | 3b RC-Closure | **Behavior change**: RETEST wins over EXPIRED on same candle | Low — correct direction |
| `_expansion_ended_reason` guard in `on_expansion_ended()` | 3b RC-Closure | Allows priority-based override of early lower-priority records | Low |
| `freshness_ratio` + `retest_distance_abs` + `retest_depth_pct` | 3b RC5 | Telemetry only — enables counterfactual RR computation | Low |
| `EXPIRED` state + VALID_TRANSITIONS | 3b | New legal state | Low — additive |
| `_expansion_entry_idx/ts` on EngineState | 3b | None until TTL check | Low |
| TTL check in EXPANSION branch | 3b | **Behavior change** | Medium — intended |
| `EXPIRED` branch | 3b | **Behavior change** | Medium — intended |
| Config keys + re-hash | 3b | New config | Low |

---

---

# Archived Plan: Phase 2b — Score Inversion Diagnosis (COMPLETE ✅)

## Context — Why Phase 2b Before Zone Model

Phase 1 re-run (`run_20260527_083602_BNBUSDT`, isolated dataset, 14,016 candles) showed:
- **Real uplift**: 2→5 trades, −0.42R→+2.02R (+2.44R delta). Shadow path fired (SHADOW_PENDING=16).
- **Score inversion** (N=5): `score→outcome Pearson = −0.936`. Higher score = worse outcome. With N=5 this is noisy, but the direction is dangerous and must be explained before promotion.
- **100% approval rate**: All 5 candidates cleared `tier_2_threshold=0.30` on candle 1. Decision layer contributes nothing — it is currently a pass-through.
- **EXPANSION dwell**: EXPANSION=6,616 candle-dwell across 14K candles (≈47% of all candles). Average episode length ~413 candles (≈103 hours). Retest never fires on most entries — price continues trending without retracing to the ATR depth ceiling.

Zone model is deferred until these three questions are answered:
1. Is score inversion real, or a shadow-path artefact from a stale displacement candle?
2. At what `tier_2_threshold` does the decision layer actually reject trades?
3. What is the expansion episode dwell distribution — are there a few pathologically long episodes?

---

## Investigation Framework

### Root Cause Hypotheses for Score Inversion

The S-score fuses:
- **G (structural)**: body_ratio + wick/ATR from `state.displacement_candle`
- **C (confirmation)**: EMA alignment + distance + body at retest

For shadow trades, `state.displacement_candle = state.pending_displacement_candle` (prior HTF window).
**Key**: the displacement candle's structural quality (body_ratio, wick) is intrinsic — it does NOT change based on age. Shadow trades and normal trades produce **structurally identical S-scores** from the same displacement candle quality.

Therefore, the −0.936 correlation is most likely explained by:
1. **N=5 sample bias** — the critical value for |r|=0.878 at α=0.05 with N=5 is on the boundary; one trade can swing the sign
2. **Shadow retest timing** — displacement candle is from prior window; the retest happens N>4 candles later; market structure may have shifted enough that the displacement's quality no longer predicts the retest outcome
3. **ATR regime shift** — if ATR expands between displacement and retest, the retest depth ceiling shrinks, making the retest marginally valid but structurally weak

Phase 2b must stratify correlation by `shadow_used` to test hypothesis 2. If inversion is confined to `shadow_used=True` trades, shadow path needs a quality gate before promotion.

---

## Phase 2b Additions (telemetry only — no behavior change)

### Addition 1: `shadow_used` flag on candidate lifecycle and TradeRecord

**Where to add the flag:** `TelemetryCollector._active_candidate` dict (in `crt_engine_v2.py`).

**Step 1** — Extend `on_candidate_opened()` signature:
```python
def on_candidate_opened(
    self, candidate_id: str, candle_index: int, ts: str,
    shadow: bool = False,          # NEW: True if opened via SHADOW_SWEEP_DETECTED
) -> None:
    self._active_candidate = {
        "candidate_id":  candidate_id,
        "first_seen_idx": candle_index,
        "first_seen_ts":  ts,
        "entered_states": [],
        "max_score_seen": 0.0,
        "shadow_used":    shadow,          # NEW
    }
```

**Step 2** — Pass `shadow=True` from the RANGE branch in `CRTEngine.process_candle()` when shadow path fires:
```python
# Existing call at SHADOW_SWEEP_DETECTED path:
self.telemetry.on_candidate_opened(
    f"CAND-{candle.index}", candle.index, candle.timestamp.isoformat(),
    shadow=True,     # ADD THIS
)
```
Normal path call stays `shadow=False` (default).

**Step 3** — Include `shadow_used` in `flush()` → CANDIDATE_LIFECYCLE record:
```python
{
    "kind":           "CANDIDATE_LIFECYCLE",
    "candidate_id":   c["candidate_id"],
    ...
    "shadow_used":    c.get("shadow_used", False),   # ADD
}
```

**Step 4** — Add `shadow_used: bool = False` to `TradeRecord` dataclass (in `backtest_v2.py` or `schemas`). Set it in the backtest loop when `TRADE_OPENED` and action came from shadow path. Mechanism: check `action.get("shadow_source_htf")` (already set in SHADOW_EXPANSION_CONFIRMED action dict) — non-empty means shadow trade.

In `BacktestRunner.run()`, after `TRADE_OPENED`:
```python
if "TRADE_OPENED" in action and engine.state.active_trade:
    _is_shadow = bool(result.get("shadow_source_htf"))  # set by SHADOW_EXPANSION_CONFIRMED
    engine.state.active_trade.shadow_used = _is_shadow
```

Add to CSV output in `_trade_row()`:
```python
"shadow_used": int(r.shadow_used),
```

---

### Addition 2: Score distribution per candidate in CANDIDATE_LIFECYCLE

Currently, `max_score_seen` captures the peak S-score. Add `score_at_approval` — the specific score that triggered the approval decision (scores evaluated on each soft_conf candle; the first one that exceeds tier_2_threshold is the approval score).

**Where:** `TelemetryCollector.on_candidate_score()` already tracks `max_score_seen`. Add `score_at_approval` field, populated in `on_candidate_accepted()`:

```python
def on_candidate_accepted(self, candle_index: int, score_at_approval: float = 0.0) -> None:
    if self._active_candidate is not None:
        self._active_candidate["score_at_approval"] = score_at_approval
        self._close_candidate(candle_index, "ACCEPTED")
```

Pass `score_at_approval=final_S` from `process_candle()` at the TRADE_OPENED call site:
```python
self.telemetry.on_candidate_accepted(candle.index, score_at_approval=final_S)
```

Include in CANDIDATE_LIFECYCLE flush:
```python
"score_at_approval": c.get("score_at_approval", 0.0),
```

---

### Addition 3: Expansion episode dwell histogram

The EXPANSION=6,616 candle-dwell concern needs quantification. Currently, the TRANSITION_COUNTER telemetry has `state_entry_counts` (how many times each state was entered), but not the dwell distribution per episode.

Add `on_expansion_episode_end(candle_index, entry_idx)` to `TelemetryCollector`:
```python
def on_expansion_episode_end(self, candle_index: int, entry_idx: int) -> None:
    dwell = candle_index - entry_idx
    self._expansion_dwells.append(dwell)
```

Track `_expansion_entry_idx` inside `TelemetryCollector._expansion_active` (already managed via `on_expansion_ended`). Emit dwell stats in `flush()` TRANSITION_COUNTER record:
```python
"expansion_dwell_stats": {
    "count":  len(self._expansion_dwells),
    "mean":   statistics.mean(self._expansion_dwells) if self._expansion_dwells else 0,
    "median": statistics.median(self._expansion_dwells) if self._expansion_dwells else 0,
    "max":    max(self._expansion_dwells, default=0),
    "p90":    sorted(self._expansion_dwells)[int(0.9 * len(self._expansion_dwells))] if len(self._expansion_dwells) >= 10 else 0,
},
```

Call `on_expansion_episode_end()` from `StateMachine`:
- In `_transition()`: when `from CRTState.EXPANSION to CRTState.RETEST` (normal qualified exit)
- In `reset_to_range()`: when `state.current_state == CRTState.EXPANSION` (interrupted exit)

---

## Decision Queries After Re-run

```powershell
$tel = Get-Content "results\run_*\BNBUSDT_crt_telemetry.jsonl" | ForEach-Object { $_ | ConvertFrom-Json }

# 1. Score at approval by shadow_used
$cands = $tel | Where-Object { $_.kind -eq "CANDIDATE_LIFECYCLE" -and $_.death_reason -eq "ACCEPTED" }
$cands | Group-Object shadow_used | ForEach-Object {
    $g = $_.Name; $scores = $_.Group.score_at_approval
    "$g: count=$($_.Count) avg_score=$(($scores | Measure-Object -Average).Average)"
}

# 2. Approval threshold sensitivity (from trades CSV — no re-run needed)
$trades = Import-Csv "results\run_*\BNBUSDT_trades.csv"
foreach ($thr in @(0.30, 0.40, 0.50, 0.55, 0.65)) {
    $approved = $trades | Where-Object { [float]$_.risk_score -ge $thr }
    $wr = ($approved | Where-Object { [float]$_.pnl_rr_net -gt 0 }).Count / [math]::Max($approved.Count, 1)
    "thr=$thr trades=$($approved.Count) WR=$wr"
}

# 3. Expansion dwell stats (from TRANSITION_COUNTER record)
$tc = $tel | Where-Object { $_.kind -eq "TRANSITION_COUNTER" }
$tc.expansion_dwell_stats

# 4. Score-outcome correlation split by shadow_used
$shadow_trades = $trades | Where-Object { $_.shadow_used -eq "1" }
$normal_trades = $trades | Where-Object { $_.shadow_used -eq "0" }
# Compute Pearson correlation for each group in Python
```

---

## Blast Radius Summary

| Change | Files | Behavior | Risk |
|---|---|---|---|
| `shadow_used` in `on_candidate_opened()` | `crt_engine_v2.py` TelemetryCollector | None (telemetry only) | Low |
| `shadow_used` in CANDIDATE_LIFECYCLE flush | `crt_engine_v2.py` | None | Low |
| `shadow_used: bool` on `TradeRecord` | `backtest_v2.py` (or shared schema) | None | Low |
| Set `shadow_used` from `shadow_source_htf` action | `backtest_v2.py` run loop | None | Low |
| `score_at_approval` field | `crt_engine_v2.py` TelemetryCollector + process_candle | None | Low |
| Expansion dwell histogram | `crt_engine_v2.py` TelemetryCollector + StateMachine | None | Low |

All additions are telemetry-only. No state machine, no thresholds, no config keys changed.

---

## Verification

1. Syntax check both files
2. Re-run on isolated dataset (`Part_1_Isolated.csv`): verify CANDIDATE_LIFECYCLE records have `shadow_used` and `score_at_approval` fields
3. Re-run on full BNBUSDT dataset: compute stratified correlation
4. Check `expansion_dwell_stats` in TRANSITION_COUNTER: flag if p90 > 100 candles (25 hours)
5. Threshold sensitivity: if tier_2_threshold 0.30→0.55 drops approval rate below 80%, the threshold is now binding — worth raising for Phase 3

---

## Phase 2b → Phase 3 Gates

| Gate | Proceed if |
|---|---|
| Score inversion confined to shadow | Add shadow quality gate (min S-score for shadow candidates) before promotion |
| Score inversion in both shadow and normal | Recalibrate G/C weights; score module has a measurement problem |
| Score inversion is N=5 noise (full dataset r > −0.50) | No score change needed; current thresholds viable |
| Expansion p90 > 200 candles | Add expansion TTL (max_expansion_candles config key) |
| tier_2_threshold=0.55 drops trades < 5% from 0.30 | Raise threshold; most candidates cluster well above 0.30 |

Zone model decision is gated behind Phase 2b completion.

---

# Archived Plan: Phase 0b Telemetry + Shadow Displacement Protection

## Context

Phase 0 telemetry (run_20260527_074732_BNBUSDT, 2,649 records) answered all structural unknowns.
The original hypothesis — EXPANSION→RETEST at 3–4% survival is the primary bottleneck, fix
`retest_depth_max` — was **wrong**. True bottleneck: DISPLACEMENT→EXPANSION at 5.2% (8/154),
driven by HTF resets (98.1% of all 2,033 resets). EXPANSION→RETEST actual survival = 87.5%.

This plan covers the next two phases:
- **Phase 0b** — two additional telemetry fields to confirm the HTF-position hypothesis before
  any structural change (would_expand_without_htf_reset + HTF window position counter)
- **Phase 1** — shadow displacement protection (pending_displacement memory that survives one
  HTF reset with a TTL), implemented as a behaviorally safe fallback path

Zone filter question answered: the "Not in discount/premium zone" check is **hardcoded range
midpoint** (`mid = (h_ref + l_ref) / 2`), NOT the BNBUSDT zone model. A zone model WAS trained
(`models/BNBUSDT/bnbusdt_training_20260524/zone_registry_BNBUSDT_202605_bnb_v1.json`, 8 clusters)
but is not wired into the production CRT pipeline. The midpoint filter killed 3/7 retest episodes.

---

## Phase 0 Confirmed Facts (do not re-measure)

| Transition | Actual | Old hypothesis |
|---|---:|---|
| SWEEP→DISPLACEMENT | 154/600 = 25.7% | ~14% |
| DISPLACEMENT→EXPANSION | 8/154 = **5.2%** | not considered |
| EXPANSION→RETEST | 7/8 = **87.5%** | ~3–4% (wrong by 25×) |
| RETEST→EXECUTION | 2/7 = 28.6% | ~33% |

Reset breakdown: 1,995/2,033 (98.1%) are HTF-driven. 116/146 DISPLACEMENT resets are HTF-driven.
Decision distance: 7 evaluations, all approved on candle 1. Zero S-score rejections.
RETEST kills: 3× range-midpoint zone filter, 2× session filter. Not threshold, not S-score.

**Invalidated candidates:** `retest_depth_max` (not binding), `soft_conf_max_candles` (not binding).

---

## Phase 0b — Two Telemetry Additions (no behavior change)

### Addition 1: `would_expand_score` in RESET_ATTRIBUTED

**Constraint:** NOT a boolean `from_state=="DISPLACEMENT" and "HTF" in reason`.
That only proves interruption happened, not that expansion would have occurred.
Replace with a **computed score** that estimates expansion probability at reset time.

**Where:** `TelemetryCollector.on_reset()` in `src/config_layer/crt_engine_v2.py`

Pass additional context from `StateMachine.reset_to_range()` → `TelemetryCollector.on_reset()`
by extending the call signature:

```python
# Extended on_reset signature:
def on_reset(
    self, from_state: str, reason: str, candle_index: int,
    displacement_age_candles: int = 0,   # candles since displacement entered
    ema_aligned: bool = False,           # True if ema_fast > ema_slow (bullish) or < (bearish) per direction
    remaining_htf_candles: int = 0,      # candles left in current HTF window at reset time
    direction_consistent: bool = False,  # True if current candle close direction matches displacement
) -> None:
```

Score formula (telemetry only, not used in execution decisions):
```python
_would_expand_score: float = 0.0
if from_state == "DISPLACEMENT" and "HTF" in reason:
    _would_expand_score = (
        min(displacement_age_candles / 3, 1.0) * 0.3   # age weight (max out at 3+ candles)
        + (0.3 if ema_aligned else 0.0)                 # momentum alignment
        + (0.25 if direction_consistent else 0.0)       # close direction
        + min(remaining_htf_candles / 4, 1.0) * 0.15   # time available in window
    )  # range: 0.0 – 1.0
```

Add to RESET_ATTRIBUTED record dict:
```python
"would_expand_score":           _would_expand_score,   # 0.0 if not DISPLACEMENT+HTF
"would_expand_threshold":       0.55,                  # candidates above this are "likely would-expand"
"would_expand":                 _would_expand_score >= 0.55,
```

**In `StateMachine.reset_to_range()`**, compute and pass these values before the telemetry call:
```python
if self.telemetry and candle:
    _disp_age = state.current_candle_index - getattr(state, '_displacement_entry_idx', 0)
    _ema_al   = (state.ema_fast_val > state.ema_slow_val) == (state.direction == Direction.LONG)
    _dir_con  = (candle.close > candle.open) == (state.direction == Direction.LONG)
    self.telemetry.on_reset(
        state.current_state.name, reason, candle.index,
        displacement_age_candles=_disp_age,
        ema_aligned=_ema_al,
        remaining_htf_candles=0,   # not available without HTF context; placeholder
        direction_consistent=_dir_con,
    )
```

`remaining_htf_candles` cannot be computed inside the engine (no HTF context there). Option:
pass it from `BacktestRunner.run()` via `engine.state` — store `_htf_remaining_candles` on
`EngineState` and update it from the backtest loop (same place as `_htf_position` counter).

**What `would_expand_score` measures:** A candidate that was deep into displacement, had aligned
EMAs, consistent direction, and plenty of time remaining in the HTF window had high probability of
continuing to expansion. A score near 1.0 = architecture interruption cost this trade.
A score near 0.0 = displacement was likely to fail even without the HTF reset.

### Addition 2: HTF Window Position Counter

**Where:** `src/runtime/backtest_v2.py` — the main candle loop, NOT the engine itself.

Add a local counter in `BacktestRunner.run()` just before the candle loop:
```python
_htf_position: int = 0          # 1-based position within current 4-candle HTF window
_prev_htf_id:  str = ""
_htf_remaining: int = cfg.htf_candles_per_range   # candles left in current window
```

Inside the loop, after `htf.push(candle)` and before `engine.process_candle(...)`:
```python
if htf.current_htf_id != _prev_htf_id:
    _htf_position  = 1
    _prev_htf_id   = htf.current_htf_id
    _htf_remaining = cfg.htf_candles_per_range - 1
else:
    _htf_position  += 1
    _htf_remaining -= 1
# Expose to engine state so reset_to_range() can access it
engine.state.htf_remaining_candles = _htf_remaining
```

After `action = engine.process_candle(candle, htf.current_htf_id)`:
```python
if action.get("action") == "DISPLACEMENT_CONFIRMED":
    engine.telemetry.on_displacement_htf_position(_htf_position, _htf_remaining)
```

Add `on_displacement_htf_position(self, position: int, remaining: int)` to `TelemetryCollector`:
```python
def on_displacement_htf_position(self, position: int, remaining: int) -> None:
    if self._active_candidate is not None:
        self._active_candidate["disp_htf_pos"]       = position
        self._active_candidate["disp_htf_remaining"] = remaining
```

Add `htf_remaining_candles: int = 0` to `EngineState` — used by `reset_to_range()` to compute
`remaining_htf_candles` for the `would_expand_score`.

In RESET_ATTRIBUTED dict in `on_reset()`, also add:
```python
"htf_window_position": self._active_candidate.get("disp_htf_pos") if self._active_candidate else None,
```

**Decision histogram query (after re-run):**
```powershell
$tel = Get-Content "...BNBUSDT_crt_telemetry.jsonl" | ForEach-Object { $_ | ConvertFrom-Json }
$resets = $tel | Where-Object { $_.kind -eq "RESET_ATTRIBUTED" -and $_.from_state -eq "DISPLACEMENT" }
$resets | Where-Object { $_.reason -like "*HTF*" } | Group-Object htf_window_position | Sort-Object Name
# would_expand candidates (architecture cost)
($resets | Where-Object { $_.would_expand -eq $true }).Count
```

---

## Phase 1 — Shadow Displacement Protection (APPROVE WITH CONSTRAINTS)

### Constraint 2: Explicit SHADOW_PENDING State (no SWEEP bypass)

**Rejected path:** RANGE → EXPANSION (bypassing SWEEP entirely)
**Required path:** RANGE → SHADOW_PENDING → SWEEP → EXPANSION

SHADOW_PENDING is an explicit `CRTState` value. It preserves auditability: every trade can be
traced through a visible state sequence. The shadow path is not a shortcut — it still requires
a sweep to confirm direction, it just skips the displacement strength check since that already
passed in the prior window.

**State machine addition:**

In `CRTState` enum (near line where CRTState is defined):
```python
class CRTState(Enum):
    RANGE        = "RANGE"
    SHADOW_PENDING = "SHADOW_PENDING"   # NEW: pending displacement memory active
    SWEEP        = "SWEEP"
    DISPLACEMENT = "DISPLACEMENT"
    EXPANSION    = "EXPANSION"
    RETEST       = "RETEST"
    EXECUTION    = "EXECUTION"
    RESOLUTION   = "RESOLUTION"
```

In `VALID_TRANSITIONS` dict:
```python
VALID_TRANSITIONS = {
    CRTState.RANGE:           [CRTState.SWEEP],
    CRTState.SHADOW_PENDING:  [CRTState.SWEEP, CRTState.RANGE],   # NEW
    CRTState.SWEEP:           [CRTState.DISPLACEMENT, CRTState.RANGE],
    CRTState.DISPLACEMENT:    [CRTState.EXPANSION, CRTState.RANGE],
    CRTState.EXPANSION:       [CRTState.RETEST,  CRTState.RANGE],
    CRTState.RETEST:          [CRTState.EXECUTION, CRTState.RANGE],
    CRTState.EXECUTION:       [CRTState.RESOLUTION, CRTState.RANGE],
    CRTState.RESOLUTION:      [CRTState.RANGE],
}
```

**State transition flow:**

```
HTF reset fires while state == DISPLACEMENT:
  1. reset_to_range() stores pending memory → state = RANGE

Next HTF window, RANGE branch:
  2. sweep detected, same direction, pending active → state = SHADOW_PENDING

SHADOW_PENDING branch (new elif in process_candle):
  3. try_shadow_pending_to_sweep() → state = SWEEP (uses pending displacement candle as context)
  4. try_shadow_sweep_to_expansion() → state = EXPANSION (skips body_ratio/atr displacement check)

From EXPANSION onwards: identical to normal path.
```

### Constraint 3: Pending Memory Origin Fields

**Where:** `EngineState` (new fields), populated in `reset_to_range()`.

```python
# Shadow displacement memory (survives HTF reset, expires after TTL)
pending_displacement_candle:  Optional[Candle]   = None
pending_displacement_dir:     Direction          = Direction.NONE
pending_displacement_ttl:     int                = 0
pending_displacement_source_htf:    str          = ""   # HTF ID when displacement was formed
pending_displacement_formed_idx:    int          = 0    # candle_index when displacement formed
pending_displacement_age_at_reset:  int          = 0    # candle age when HTF reset fired
pending_displacement_reason_created: str         = ""   # reset reason that created this memory
```

In `reset_to_range()`, before clearing `state.displacement_candle`:
```python
if (state.displacement_candle is not None
        and "HTF" in reason
        and state.current_state == CRTState.DISPLACEMENT):
    state.pending_displacement_candle          = state.displacement_candle
    state.pending_displacement_dir             = state.direction
    state.pending_displacement_ttl             = self.config.pending_displacement_ttl_candles
    state.pending_displacement_source_htf      = state.active_range.htf_candle_id if state.active_range else ""
    state.pending_displacement_formed_idx      = getattr(state, '_displacement_entry_idx', 0)
    state.pending_displacement_age_at_reset    = state.current_candle_index - state.pending_displacement_formed_idx
    state.pending_displacement_reason_created  = reason
```

Also add `_displacement_entry_idx: int = 0` to `EngineState`, set in `_transition()` when
`target == CRTState.DISPLACEMENT`.

**The origin fields allow:** Training pipeline to separate `natural_expansion` (displacement
→ expansion in same HTF window) from `shadow_expansion` (cross-window memory). Feature
distributions may differ, and a model trained without separation would confuse the two.

### Constraint 4: TTL = 4 candles (one HTF window)

**Config key:** `pending_displacement_ttl_candles: 4` (not 8).

Rationale: "pause → compress → continue" happens within the adjacent HTF window.
If the market did not continue in the next 4 candles (1 hour), the displacement context is stale.
Two windows (8 candles) risks using displacement context that is structurally obsolete.

Production config change: `configs/production/v2_multi_2026_04 - deepdeektry.json` → `crt_engine`:
```json
"pending_displacement_ttl_candles": 4
```

### SHADOW_LEAK Integrity Event (Constraint 5)

When a shadow resume fires, validate that the sweep was legitimate. If not, emit SHADOW_LEAK.

**Where:** `CRTEngine.process_candle()`, SHADOW_PENDING branch, after sweep re-check.

```python
# Integrity check: shadow resume requires valid sweep in same direction
if sweep is None or sweep.direction != self.state.pending_displacement_dir:
    # Shadow memory exists but no valid confirming sweep — this is a SHADOW_LEAK
    from utils.integrity_events import emit_integrity_event
    emit_integrity_event(
        "SHADOW_LEAK", "ERROR", "crt_engine",
        {
            "candidate_id":     f"CAND-{candle.index}",
            "pending_dir":      self.state.pending_displacement_dir.value,
            "sweep_dir":        sweep.direction.value if sweep else "NONE",
            "candle_index":     candle.index,
        },
    )
    # Expire the pending memory to prevent further contamination
    self.state.pending_displacement_ttl           = 0
    self.state.pending_displacement_candle        = None
    return action  # do not resume
```

SHADOW_LEAK is an ERROR-severity integrity event that surfaces in `logs/integrity_events.jsonl`.
A non-zero SHADOW_LEAK count invalidates the replay run.

### Counterfactual Replay Output (Constraint 5)

After Phase 1 re-run, `BacktestRunner` should produce a counterfactual section alongside the
standard summary. **Where:** `BacktestRunner._print_summary()` or a new method.

```python
# In BacktestRunner.run(), after writing telemetry:
_shadow_trades   = [t for t in journal.closed_trades if "SHADOW" in getattr(t, "source_path", "")]
_baseline_trades = [t for t in journal.closed_trades if t not in _shadow_trades]
_tel_records     = engine.dump_telemetry()
_shadow_exp      = sum(1 for r in _tel_records if r.get("kind") == "TRANSITION_COUNTER"
                       and "SHADOW_PENDING" in r.get("state_entry_counts", {}))
```

Report structure:
```
COUNTERFACTUAL COMPARISON
  Baseline  trades: X | avg_rr: Y
  Shadow    trades: X | avg_rr: Y  (shadow resume path only)
  SHADOW_LEAK: 0 (must be 0 for replay to be valid)
```

This isolates gains from the shadow path so the RR impact is attributable.

---

## Decision Gates

### Phase 0b → Phase 1 gate

After Phase 0b re-run, evaluate:

```
HTF position histogram:
  If position 4/4 kill rate ≥ 2× positions 1-3 → HTF timing is causal → proceed with SHADOW_PENDING
  If positions 1-4 fail at equal rate → timing is NOT causal → investigate body_ratio/atr gates first

would_expand score distribution:
  Count candidates with would_expand_score >= 0.55 → upper bound on shadow protection gain
  If count < 5 → shadow protection likely yields < 1 additional trade → deprioritize
  If count >= 20 → high potential; worth the architectural complexity
  
SHADOW_LEAK gate (Phase 1 only):
  SHADOW_LEAK count must be 0 after Phase 1 re-run
  Any SHADOW_LEAK → stop replay, debug before promotion
```

### Zone Filter Gate (deferred)

Do not modify midpoint filter in Phase 1. First measure:
- `midpoint_rr`: realized RR of trades where entry_price was within 10% of midpoint vs >10%
- `zone_model_rr`: what RR distribution the BNBUSDT zone model assigns to those RETEST episodes
Compare. If zone model significantly outperforms midpoint, wire it in for Phase 2.

The 3 zone-killed retest episodes had `structure_valid = True` (reached RETEST legitimately).
These should be logged as `structure_valid / execution_rejected` for training label value — they
are false negatives with known feature vectors.

---

## Blast Radius Summary

| Change | Files | Behavior change | Risk |
|---|---|---|---|
| `would_expand_score` in RESET_ATTRIBUTED | `crt_engine_v2.py` TelemetryCollector + EngineState | None (telemetry only) | Low |
| HTF position counter + on_displacement_htf_position | `backtest_v2.py` loop + `crt_engine_v2.py` TelemetryCollector | None (telemetry only) | Low |
| `htf_remaining_candles` on EngineState | `crt_engine_v2.py` EngineState + backtest_v2.py | None (used only for score calc) | Low |
| `SHADOW_PENDING` added to CRTState + VALID_TRANSITIONS | `crt_engine_v2.py` enum + dict | New legal state; old tests that enumerate states will need updating | Medium |
| `pending_displacement_*` fields on EngineState (8 fields) | `crt_engine_v2.py` EngineState | None until reset_to_range() populates them | Low |
| Shadow memory creation in reset_to_range() | `crt_engine_v2.py` StateMachine.reset_to_range() | New: stores memory on HTF+DISPLACEMENT reset | Medium |
| SHADOW_PENDING branch + shadow resume in process_candle() | `crt_engine_v2.py` CRTEngine.process_candle() | New path: DISPLACEMENT→SHADOW_PENDING→SWEEP→EXPANSION | Medium |
| Config key `pending_displacement_ttl_candles: 4` | production JSON + rehash | None until shadow fires | Low |
| SHADOW_LEAK integrity event | `crt_engine_v2.py` + `utils/integrity_events.py` | Logs ERROR, halts shadow resume | Low |
| Counterfactual section in summary output | `backtest_v2.py` BacktestRunner | None (reporting only) | Low |

---

## Implementation Order

```
Phase 0b — Telemetry additions (no behavior change, re-run required)
│
│  Edit 1: EngineState — add htf_remaining_candles: int = 0
│  Edit 2: TelemetryCollector.on_reset() — extend signature + add would_expand_score fields
│  Edit 3: StateMachine.reset_to_range() — pass ema_aligned, direction_consistent, htf_remaining
│  Edit 4: TelemetryCollector — add on_displacement_htf_position(position, remaining)
│  Edit 5: BacktestRunner.run() — add _htf_position/_htf_remaining counters,
│           update engine.state.htf_remaining_candles, call on_displacement_htf_position
│
│  Re-run same backtest (no config change). Inspect histogram + would_expand counts.
│
└── Decision gate → proceed to Phase 1 only if histogram confirms HTF-timing as causal

Phase 1 — Shadow Displacement Protection
│
│  Edit 6: CRTState enum — add SHADOW_PENDING
│  Edit 7: VALID_TRANSITIONS — add SHADOW_PENDING transitions
│  Edit 8: EngineState — add 8 pending_displacement_* fields + _displacement_entry_idx
│  Edit 9: StateMachine._transition() — set _displacement_entry_idx on DISPLACEMENT entry
│  Edit 10: StateMachine.reset_to_range() — create pending memory on HTF+DISPLACEMENT reset
│  Edit 11: CRTEngine.process_candle() — add SHADOW_PENDING branch with SHADOW_LEAK guard
│  Edit 12: CRTConfig — add pending_displacement_ttl_candles: int = 4
│  Edit 13: Production JSON + rehash
│  Edit 14: BacktestRunner._print_summary() — add counterfactual comparison section
│
│  Re-run. Verify:
│    - SHADOW_LEAK count == 0 (hard gate)
│    - SHADOW_PENDING entry count > 0 (shadow fired)
│    - EXPANSION count > 8 (shadow added episodes)
│    - DISPLACEMENT→EXPANSION survival > 5.2%
│    - Trade count and RR distribution vs baseline
│
└── Governance gate: ConfigValidator.validate() before any promotion

Zone attribution (parallel, no re-run)
│
│  Add structure_valid / execution_rejected fields to RESET_ATTRIBUTED records
│  for candidates that reached RETEST before zone/session filter fired
```

---

## Verification

After Phase 0b re-run:
```powershell
$tel = Get-Content "results\BNBUSDT\run_*\BNBUSDT_crt_telemetry.jsonl" | ForEach-Object { $_ | ConvertFrom-Json }
$resets = $tel | Where-Object { $_.kind -eq "RESET_ATTRIBUTED" -and $_.from_state -eq "DISPLACEMENT" }

# HTF position histogram (causal test)
$resets | Where-Object { $_.reason -like "*HTF*" } | Group-Object htf_window_position | Sort-Object Name

# would_expand gate
($resets | Where-Object { $_.would_expand -eq $true }).Count
```

After Phase 1 shadow protection:
```powershell
# SHADOW_LEAK count — must be 0
($tel | Where-Object { $_.kind -eq "INTEGRITY_EVENT" -and $_.event_type -eq "SHADOW_LEAK" }).Count

# Expansion episode count (should exceed baseline of 8)
($tel | Where-Object { $_.kind -eq "TRANSITION_COUNTER" }).state_entry_counts

# Counterfactual output is in BNBUSDT_report.txt under "COUNTERFACTUAL COMPARISON" section
```
