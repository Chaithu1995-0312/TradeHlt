# 6 · Validation Audit (Phase E-2) — Constraints 2 & 4

> Point-in-time audit, 2026-06-02. What blocks production, what blocks trade throughput, which gates have
> measured evidence, and the validator's own fidelity gaps.

## What blocks PRODUCTION (ConfigValidator)

`ConfigValidator.validate()` (`config_validator.py:288-339`) runs a per-instrument backtest and applies:

| Gate | Type | Threshold | Behavior |
|------|------|-----------|----------|
| Min trade count / instrument | **HARD** | config | reject |
| Max drawdown / instrument | **HARD** | config | reject |
| Min fitness (final_score) | **HARD** | config | reject |
| Min win rate | SOFT | config | warn |
| Min expectancy (R) | SOFT | config | warn |
| Cross-instrument score variance | SOFT | config | warn |

## What blocks TRADE THROUGHPUT (runtime rejection points)

Ordered by where they fire in the candle→decision path:

1. **CRT session filter** (`allowed_sessions`, `RejectReason.OUTSIDE_SESSION`) — **the binding constraint.**
   RETEST→EXECUTION = **11.2%**; **64 valid retests discarded** (OFF_SESSION/ASIA). *Policy, not capability.*
2. **News filter / spread check** (`RejectReason.NEWS_FILTER`, `HIGH_SPREAD`).
3. **Adapter gate** — score ≤ 0 → hard reject (`engine_runner.py:591`).
4. **Completeness gate** — any of the 4 engines missing → hard reject (`engine_runner.py:748`).
5. **Fusion baseline** — `final_score < fusion_min_score(0.25)` (`engine_runner.py:823`).
6. **DecisionEngine** — `score<0.45 · p_win<0.4 · rr<1.5 · weak>0.4` → reject (`decision_engine.py:130`).
   *(Note: 134/135 retests PASS the score gate — score is NOT the throughput limiter.)*
7. **RegimeGovernor** — quota/percentile cap **inactive** (`ultron_gate_enabled=false`).
8. **UltronRiskGate** (live-only) — TTL/RR/daily-limit/kill-switch/exposure.

**Conclusion (C2):** the throughput valve is overwhelmingly the **session policy**, not detection or scoring.
Fixing it is a config change (per-coin `allowed_sessions_overrides`), already validated in `v3`.

## The live ≠ backtest divergence

`UltronRiskGate` and `ExecutionPlannerV1_2` are **not in the backtest spine** — they are constructed only in
`live_engine_hook`. So the measured backtest ROI (e.g. BNB +20.59%) **does not exercise the capital gate or
the entry/TTL planner**. Live behavior on the same config is therefore *unverified by the backtest*. This is
a measurement gap that must be flagged whenever a backtest number is used to justify a live decision.

## Validator fidelity gaps (C4)

1. **Was session-config-blind** — `validate()` built one `_params_to_crt_config(params)` for all instruments
   and never read `allowed_sessions`; it would score BNB at default sessions (~15 trades, not 35). Fixed
   2026-06-02 (#1) to be override-aware via `resolve_allowed_sessions()`.
2. **crt_engine-fidelity gap (still open)** — `_params_to_crt_config` builds `CRTConfig` from **5 flat params
   + DEFAULTS**, not the full `crt_engine` section → **systematically pessimistic vs the production path**:
   - BNB validator **39** vs production-path sweep **35** (different, and validator misses the real PF 2.54).
   - SOL validator **PF 0.98** vs sweep **PF 1.17**.
   Promotions are gated on numbers the live engine wouldn't reproduce.

## Gates: evidence vs assumption

Same verdict as the governance audit — **all runtime thresholds are hardcoded assumptions** (session list,
`fusion_min_score=0.25`, decision thresholds, `zone_min_samples=50`, `drift_threshold=1.5`). The OOS feature
studies are the *only* gate-adjacent numbers with measured backing, and even those carry honest caveats
(persist_share conditioned on train-profitability; fixed-seed K-Means artifact; edge ≤+0.09R).

## Bottom line (C2 + C4)

Throughput is limited by **policy** (session filter) and promotions are judged by a **pessimistic, partly
blind validator** against **uncalibrated thresholds**. Both are fixable without new intelligence: promote the
validated per-coin session policy, give the validator full-`crt_engine` fidelity, and calibrate the gates from
data. → [top-10-roi-actions.md](top-10-roi-actions.md) #1, #4, #5.
