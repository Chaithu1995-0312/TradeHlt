# Exit-Model Adoption — Intrabar Touch Becomes Governing (Phase A: Truth)

> **Date:** 2026-06-10 · **Scope:** Resolve Backtest Trust Layer F2 (exit realism) by
> adopting the conservative intrabar-touch exit model as the governed default, re-baseline,
> and report both bounds. **Phase A = truth only — no retuning, no promotion.**
> Point-in-time analysis (not a living doc).

## 1. Decision

The exit-trigger model is now **governed** by `CRTConfig.exit_model` (default
`intrabar_touch`), resolved once in `CRTEngine.__init__` → `self._intrabar_exits`
(precedence: explicit arg > env `TRUST_INTRABAR_TOUCH` > config > default). This promotes
the prior measure-only hook (`crt_engine_v2.py` F2/WS4B) to the governing default.

- **`intrabar_touch` (governing):** SL/TP fire on a high/low **wick touch**, conservative
  same-bar ordering (SL before TP), via `CRTEngine._intrabar_trigger_price`.
- **`close_only` (legacy, optimistic bound):** trigger only when `candle.close` crosses
  the level.

Rationale: F2 established close-only is the *optimistic* bound; for an SL-based strategy
the truth sits near the intrabar figure. A system must optimize for truth, not passing
gates.

## 2. Dual-bound band (oracle-verified, BNBUSDT)

`scripts/analysis/exit_model_band.py` runs the **same** config under both models and
recomputes every metric with the independent `analytics/metrics_oracle.py`
(`reports/exit_model_band.json`):

| Metric | close-only (optimistic) | intrabar (governing) | Δ |
|---|---|---|---|
| Profit factor | **0.942** | **0.459** | inflation_ratio **2.05×** |
| Expectancy (R) | −0.038 | **−0.418** | |
| Win rate | 38.9% | 27.8% | |
| Trade count | 18 | 18 | same entries, different exits |
| Total return | −0.85% | **−7.37%** | |
| Max drawdown | 5.08% | 11.25% | |

Independently reproduces the audit's §4e numbers (PF 0.94↔0.46, WR 38.9%→27.8%).

## 3. Verdict (accepted, not engineered away)

**The active config (`v2_multi_2026_04`) has no edge under realistic exits.** Intrabar
PF 0.46 and expectancy −0.42R (BNBUSDT) are decisively losing; even the optimistic
close-only bound is marginally negative (−0.04R, PF 0.94). The previously-apparent
viability was largely an artifact of the close-only exit model.

`ConfigValidator validate-prod` under intrabar → **REJECT** (final score 0.346, 24 trades,
max-DD 7.2%). **Honest attribution of the verdict:**
- The 4 **hard failures are FX min-trade (0 trades < 10): AUDUSD/GBPUSD/USDJPY/XAUUSD** —
  a **pre-existing** structural condition (those instruments produce no trades under the
  active session config), **not** caused by the exit-model change. The active config was
  already non-promotable on this basis.
- The exit-model change's real effect is the **quality** degradation on the instruments
  that *do* trade: BTCUSDT soft-flagged at expectancy **−0.621R**, and the BNBUSDT band
  collapse in §2. This is the signal Phase A exists to surface — the edge does not survive
  realistic exits.

So: REJECT was expected and is correct, but its *headline driver* is the pre-existing FX
0-trade gate; the *exit-model contribution* is the quality collapse, visible in the band
and the BTCUSDT expectancy. Both are accepted, not engineered away.

## 4. Governance

- This is a governed change (alters the ledger → invalidates the close-only baseline).
- `config_hash` (params-only) is **unaffected** — `exit_model` lives in `crt_engine`.
- Re-baseline: `python src/runtime/baseline_capture.py --label intrabar_2026_06`.
- Re-validate: `python src/config_layer/config_validator.py validate-prod --data-dir data/`
  (records the expected REJECT).
- WS5 freeze gate re-greens under intrabar (oracle parity + replay determinism are
  exit-model-agnostic; new intrabar baseline reconciles). With the exit model now
  governance-decided (= intrabar), the F2 block lifts; the **quality gate** (§3 REJECT) is
  what now correctly gates promotion.

## 5. Boundary — Phase A vs Phase B

Phase A (this note) changes **only** the exit-model default + additive band reporting, and
**accepts the verdict on the unchanged config**. Finding a config that survives intrabar is
**Phase B** (sweeps → OOS → M4 → promotion) — kept strictly separate so any future PF
movement is attributable to parameters, not to the semantic change. The data-validation
stack (L1/L2/L3) is frozen (`DATA_VALIDATION_STACK_VERSION = "3.0"`).
