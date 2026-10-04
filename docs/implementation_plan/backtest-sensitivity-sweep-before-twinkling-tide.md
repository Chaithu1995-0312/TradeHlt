# Plan: BNBUSDT Session OOS/G1 Evaluation → Conditional Promotion

## Context

The sensitivity-sweep arc is done and the bottlenecks are resolved (consensus gate proven
dormant; ROI/PF metrics layer implemented; `session_sweep.py`/`detection_sweep.py` restored;
session-override resolver `resolve_allowed_sessions` confirmed present at
`production_config.py:162`). Full-window evidence is strong — **+ASIA (V1): 15→23 trades,
PF 1.79→2.54, ROI +4.91%→+13.29%, flat drawdown**; V3 (+ASIA+OFF) reaches +17.11% at PF 2.20.

We are now in **promotion-governance territory**, where over-analysis is the main risk. Full-window
numbers are not promotable on their own — they need out-of-sample validation under the existing
Governance Threshold G1. This plan runs that evaluation and defines the **conditional, user-gated**
promotion path. No new analysis tooling is built.

## Step 1 — Run the OOS/G1 evaluation (measure-only, immediate)

```bash
python scripts/analysis/session_sweep.py --instrument BNBUSDT --train-split 0.7
```
This drives `_run_oos_mode` (session_sweep.py:175): runs the V0→V4 ladder on IS=[0,0.7) and
OOS=[0.7,end], ranks by Expected Monthly ROI, and emits a per-variant verdict +
RECOMMENDATION. Output: `results/session_sweep/bnbusdt_oos.json`. Writes only under `results/`.

## Step 2 — Read the verdict (no new logic; the tool already decides)

The decision rule is already encoded (session_sweep.py:247–275). A challenger is `PASS` only if
**all** hold vs the prod-resolved incumbent:
- OOS sign gate: `oos_exp > 0 AND oos_pf > 1.0`
- Retention: `oos_exp / is_exp ≥ 0.70` (`_OOS_RETENTION_MIN`)
- Rank stability: top-K by Expected Monthly ROI in BOTH IS and OOS (`--top-k`, default 5)
- G1: `≥ +10% relative AND ≥ +1pp absolute` Expected Monthly ROI vs incumbent
  (`_G1_REL_MIN` / `_G1_ABS_MIN`)

The tool prints `RECOMMENDATION: PROMOTE <variant>` or `KEEP_INCUMBENT`. **`KEEP_INCUMBENT` is a
valid, correct outcome** — a no-churn result, not a failure. Read it; do not re-derive it.

Expected primary candidate: **V1 (+ASIA)** (quality + frequency both improved full-window → best
odds of surviving train/test). V3 is the higher-ROI but lower-PF alternative to watch.

## Step 3 — Conditional promotion (governed, explicit go-ahead only)

**Only if Step 2 yields `PROMOTE <variant>`.** This is a deliberate governance action — do NOT
auto-execute; surface the recommendation and get explicit user confirmation first. Mechanism for a
per-instrument BNBUSDT session change (e.g. +ASIA):

1. **Edit active prod config** `configs/production/v2_multi_2026_04.json` — add under
   `engine_runner`:
   ```json
   "allowed_sessions_overrides": { "BNBUSDT": ["LONDON","NEWYORK","OVERLAP","ASIA"] }
   ```
   (Key currently absent; resolved by `resolve_allowed_sessions` — global sessions untouched for
   other instruments. Use the exact session tuple of the PROMOTED variant.)
2. **Rehash:** `python scripts/maintenance/_compute_hash.py` (schema hash is load-bearing).
3. **Validate:** `ConfigValidator.validate(...)` must return `decision == "APPROVE"` (hard +
   soft quality gates). Promotion is blocked otherwise.
4. **Promote** via `promotion_manager.py` (append-only `promotion_log.jsonl`, SHA-256, archive of
   prior version). This is the only path to production per CLAUDE.md §3.1 / §11.

Per memory ([[project_trd_m6_downstream]]), a BNBUSDT instrument-scoped session promotion is the
#1 un-park item — this is that step, now evidence-backed.

## Out of scope (do not touch)
TP3 partial exits, frequency_boost_mode, tier-threshold sweeps, new architecture. Lower ROI than
completing the session OOS→promotion cycle.

## Verification
- Step 1: command exits 0 (no `ImportError` — resolver confirmed present); `bnbusdt_oos.json`
  written with `rows[].decision` + `recommendation`.
- Step 2: V0 IS/OOS reproduces a sane baseline; verdict table prints; recommendation is explicit.
- Step 3 (if taken): rehash succeeds, `ConfigValidator` returns APPROVE, `promotion_log.jsonl`
  gets a `PROMOTED` line, prior config archived. Rollback = restore archived
  `{version}_archived_{ts}.json` + ACTIVE_VERSION.
