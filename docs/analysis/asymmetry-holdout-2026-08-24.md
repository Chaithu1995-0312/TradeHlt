# MC-ASYM-XAUUSD-M15-V1 holdout (2026-08-24)

> Point-in-time. Object: `docs/research/asymmetry_object.md` (SEM-027).
> Sealed contract: `configs/research/measurement_contracts/instances/MC-ASYM-XAUUSD-M15-V1.json`
> (sha256 `363ebd4cc6f817c1de875c380ec06bfe2ed6114088dbdc6b575b1cc58cfdfba2`).
> Metrics: `docs/research-readiness/asymmetry/mc_asym_xauusd_m15_v1/metrics.json`.
> L3 `validate_dataset` APPROVE (with gap warnings) on `data/mt5/XAUUSD_M15.csv`.

**Verdict: DIAGNOSTIC_PASS.** Not economic. mt00/mt01 UNRUN. No G001.

PRIMARY (frozen): `contrast = E[ΔMFE | trend_bias=+1] − E[ΔMFE | trend_bias=−1]`.
Success: holdout n≥30, both cells n≥30, sign(holdout contrast)==sign(train contrast).

| Split | n pairs | E[ΔMFE] | +1 n / E[ΔMFE] | −1 n / E[ΔMFE] | contrast |
|---|---:|---:|---|---|---:|
| Train (≤ 2025-12-23 19:15) | 37,621 | **+0.438** | 21,431 / +0.616 | 16,188 / +0.201 | **+0.415** |
| Holdout (≥ 2025-12-24 19:15) | 9,454 | **−0.546** | 4,942 / −0.322 | 4,511 / −0.791 | **+0.469** |

Embargo dropped 91 pairs. F-086 stride unspent. Full-sample atlas is not this split.

**E-001:** the PRIMARY contrast **keeps sign**. The **unconditional** mean **flips** (train long-path bias, holdout short-path bias). The 2026-08-24 full-sample E[ΔMFE]=+0.239 mixed those windows. Relative information in FM-054 is not the same object as “gold just goes up.”

Session/hour were OUT OF PATH for the gate. Holdout session=4 is the only session cell still positive (E[ΔMFE]=+0.332); that is reported, not gated, and still F-066-contaminated.

ΔMFE is path excursion, not book PnL. `economic_claims_allowed` remains false.

Follow-on (same object, PRIMARY not retuned): cell-level mean/median/P(Δ>0)/n and the magnitude-vs-hit-rate split live in [`asymmetry-decomposition-2026-08-24.md`](asymmetry-decomposition-2026-08-24.md).
