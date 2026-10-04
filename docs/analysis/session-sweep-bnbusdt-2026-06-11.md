# Session-Config Lever — BNBUSDT Sweep (2026-06-11)

> **Point-in-time analysis** (not a living doc). Branch `patch`, prod
> `v2_multi_2026_04 - deepdeektry`, governing exit model `intrabar_touch`. Measure-only:
> `scripts/analysis/session_sweep.py`. No config / `ACTIVE_VERSION` / hash mutated.

## Why this run

The session filter (RETEST→EXECUTION, `crt_engine_v2.py:2604`) was the **last un-falsified**
ROI lever on BNBUSDT — the Phase 6b funnel diagnosis put 64/93 `FILTER_REJECTED` on session
rejects (44 OFF_SESSION + 20 ASIA), not on the score gate. Every other lever was already null:
EMA gate (byte-identical no-op), detection thresholds (non-binding), consensus gate (dormant),
full spine (no net edge under realistic exits). Question: does opening BNBUSDT's sessions
improve **risk-adjusted, out-of-sample** ROI under the now-governing `intrabar_touch` exits?

## Result 1 — the published V0 baseline is stale (first finding)

Legacy full-window run, V0 = current prod sessions (`LONDON / NEWYORK / OVERLAP`):

```
V0 BASELINE HARD GATE
  trades :  15      expected 15      [PASS]
  PF     :  1.0286  expected ~1.79   [FAIL]
  ROI    :  0.12%   expected ~+4.91% [FAIL]
```

The V0 *trade count* reproduces exactly (15) — the harness is deterministic and trustworthy.
What failed is the comparison against the **published baseline constant** (15 / 1.79 / +4.91%,
`session_sweep.py:56`), captured 2026-05-29 **before** the `intrabar_touch` exit-model adoption
(2026-06-10, which collapsed the BNBUSDT band to PF 0.46–0.94). Under the governing realistic
exits, true V0 is **15 / PF 1.03 / +0.12%** — essentially break-even. This is consistent with
`project_exit_model_adoption` and `project_spine_as_hypothesis` (PF 0.805 net).

→ **The `_BASELINE` constant must be reconciled** to the post-`intrabar_touch` truth, else every
future legacy-mode run false-FAILs the V0 gate. Surfaced as a follow-up (not edited here —
this run was measure-and-recommend scope).

## Result 2 — in-sample, session expansion looks good …

Legacy full-window ladder (all variants under the *same* current exit model — deltas are
internally valid even though the stale-constant gate "failed"):

| variant | trades | Δ | WR | PF | ROI% | MAR | maxDD% |
|---|---|---|---|---|---|---|---|
| V0 (LON/NY/OVL) | 15 | — | 47% | 1.03 | +0.12 | 0.03 | 4.89 |
| V1 +ASIA | 23 | +8 | 57% | 1.31 | +3.05 | 1.17 | 2.61 |
| V2 +OFF_SESSION | 27 | +12 | 52% | 1.11 | +1.37 | 0.28 | 4.95 |
| V3 +ASIA+OFF | 35 | +20 | 57% | 1.25 | +3.67 | 1.07 | 3.44 |
| V4 all | 35 | +20 | 57% | 1.25 | +3.67 | 1.07 | 3.44 |

On the full window, opening sessions raises trades **and** PF **and** ROI **and** lowers
drawdown — the only lever that has ever moved the needle. **But this is in-sample.**

## Result 3 — … and it does NOT survive out-of-sample (the decision)

OOS mode, 70/30 split (IS = candles 0–49,056; OOS = 49,056–70,080). G1 incumbent =
prod-resolved `LONDON / NEWYORK / OVERLAP`. Gate: OOS sign-positive AND retention ≥ 0.70 AND
rank-stable AND G1 (≥ +10% rel AND ≥ +1pp abs monthly-ROI vs incumbent).

| variant | IS exp | OOS exp | OOS PF | IS→OOS trades | verdict |
|---|---|---|---|---|---|
| V0 incumbent | −0.075R | +0.374R | 2.10 | 12 → 3 | INCUMBENT |
| V1 +ASIA | +0.082R | +0.283R | 1.98 | 16 → 7 | FAIL (G1) |
| V2 +OFF | +0.104R | **−0.055R** | 0.91 | 18 → 9 | FAIL (flips negative OOS) |
| V3 +ASIA+OFF | +0.164R | +0.042R | 1.09 | 22 → 13 | FAIL (collapses to break-even) |
| V4 all | +0.164R | +0.042R | 1.09 | 22 → 13 | FAIL |

```
RECOMMENDATION: KEEP_INCUMBENT -> V0_baseline (['LONDON', 'NEWYORK', 'OVERLAP'])
No challenger cleared OOS retention + G1 — valid PASS-to-no-change.
```

The best in-sample challenger (V3, +0.21%/mo) decays to +0.07%/mo OOS (PF 1.09 ≈ break-even);
V2 flips outright negative. Even the incumbent flips sign across windows (IS −0.075R / OOS
+0.374R at N=12/N=3) — these are **tiny-N, high-variance** estimates (well under the N≥30
qualification floor). The full-window "edge" was regime-specific overfitting.

## Conclusion

**The session lever is falsified as a promotable BNBUSDT edge** under realistic exits + OOS
discipline. It joins the EMA gate, detection thresholds, the consensus gate, and the full
spine in the null column. Recommendation: **do not expand BNBUSDT sessions** (KEEP_INCUMBENT);
`ACTIVE_VERSION` correctly stays `v2_multi_2026_04`.

Cumulatively, **every in-spine lever explored on BNBUSDT has now been falsified or shown
non-binding under `intrabar_touch`.** The economically-rational next move is not another
in-spine sweep — it is to either (a) accept BNBUSDT has no edge in this spine and redirect
(other instruments, or the research/edge-discovery program M4 QualificationGate), or
(b) question the spine/exit assumptions themselves. The marginal knowledge-ROI of further
single-knob BNBUSDT sweeps is now low.

## Follow-ups (out of this run's scope)

1. **Reconcile `_BASELINE`** in `scripts/analysis/session_sweep.py:56` to the `intrabar_touch`
   truth (15 / PF 1.03 / +0.12%) so legacy-mode V0 stops false-failing. Cross-ref
   `project_exit_model_adoption`, `project_roi_metrics_layer`.
2. Decide redirect target (other instrument / research M4 / spine re-examination).

## Artifacts

- `results/session_sweep/bnbusdt.json` (legacy ladder)
- `results/session_sweep/bnbusdt_oos.json` (OOS / G1)
