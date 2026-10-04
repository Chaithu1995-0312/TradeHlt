# MC-RNET-OVERLAY-XAUUSD-M15-V1 holdout (2026-08-24)

> Point-in-time. Object: `docs/research/rnet_size_overlay_object.md` (SEM-029).
> Sealed contract: `configs/research/measurement_contracts/instances/MC-RNET-OVERLAY-XAUUSD-M15-V1.json`
> (sha256 `85f9a3bcbe4bea9b72595aabe032737ff41a299fd9fff4b04977696aa557da0c`).
> Metrics: `docs/research-readiness/rnet_overlay/mc_rnet_overlay_xauusd_m15_v1/metrics.json`.
> L3 `validate_dataset` APPROVE (with gap warnings).

**Verdict: DIAGNOSTIC_PASS.** Not economic. mt00/mt01 UNRUN. No G001.
P-GOAL-04 not opened. SEM-028 / SEM-027 PRIMARYs not retuned. Not a side picker.
E>0 was **not** the gate.

Independent entry = every clean_labels `(decision_ts, side)` row. Overlay
`k=0.5`: weight `1.5` on agree, `0.5` on disagree.

| Split | n | E[y] | E[w·y] | overlay Δ | agree mean / P>0 | disagree mean / P>0 |
|---|---:|---:|---:|---:|---|---|
| Train | 75,238 | **−1.022** | −1.016 | **+0.0058** | −1.010 / 0.321 | −1.033 / 0.318 |
| Holdout | 18,906 | **−0.551** | −0.544 | **+0.0064** | −0.538 / 0.336 | −0.563 / 0.328 |

Embargo dropped 182 rows. F-086 stride unspent. 12bps baked into y (F-082 punitive).

**E-001:** sign-match is not usefulness. Overlay lift is **+0.006R** on a holdout
book still at **−0.55R**. Agree/disagree contrast on this walk is only **+0.025R**.
SEM-028's +0.21R MFE prior **does not survive the trade object** — SL/TP walk
compresses it to 0.025R of stored R-net, and the size overlay harvests a quarter
of that (balanced `Δ = 0.25 × contrast`). Hit-rate moves 0.8 pp.

This is F-086 / F-087 on this overlay: you cannot size your way out of a
negative-expectancy independent entry. Do not wire it.

Why the MFE prior does not book: [`mfe-to-rnet-collapse-2026-08-24.md`](mfe-to-rnet-collapse-2026-08-24.md).
