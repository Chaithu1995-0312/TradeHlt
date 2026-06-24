# RETEST selection effect under the governing truth standard — crypto-6

> **Point-in-time analysis (history, not living truth).** Date: 2026-06-13 · Branch: `patch` ·
> Phase S1. Artifact: `results/research/phase_s/phase_s_selection_effect.json` (deterministic).
> Driver: `scripts/research/phase_s_selection_effect.py`; core: `src/research/selection_effect.py`.
> Telemetry source wired by S0 (see below). Conclusion promoted to the living record as **F-021**.

## Why this run

Direction is falsified globally (F-019) and conditionally (F-020). The last unfalsified branch was
**sparse SELECTION**. F-002 once measured a **+0.145R selection edge at the RETEST→EXECUTION gate**,
but that predates the governing **intrabar_touch exit model + 12bps** (2026-06-10) — stale, like
F-003/F-017's session lever. Phase S1 re-measures the selection effect
`ΔE = E[net-RR | selected retests] − E[net-RR | rejected retests]` under **intrabar_fixed + 12bps**,
**pooled by EFFECT** (weight `min(n_sel,n_rej)`, not raw entries → respects F-009), **decomposed by
reject-reason class**, with stratified-permutation significance + OOS + sign-consistency. The
rejected retests are a natural matched control (same instrument, same gate chain).

## S0 prerequisite (a finding in itself)

The `RETEST_REPLAY` telemetry this study consumes was **dormant**: `CRTEngine.on_retest_replay`
existed (R4) but had **zero callers** — `_retest_replay_records` stayed empty in every backtest, so
`execution_planner_replay.py`'s "telemetry exists" claim was false on `patch` HEAD. **S0 wired the
emit** at the RETEST→EXECUTION decision (`crt_engine_v2.py`, both accept + reject branches),
**emit-only / behavior-neutral**: BNBUSDT trades-ledger SHA **byte-identical** pre/post
(`0fd8ee6a…`), and a backtest now emits the records (BNB: 0 → 44).

## Result — `VERDICT: SELECTION_IS_SESSION_ONLY`

Usable instruments (selected **and** rejected present): **4** — BNB/BTC/ETH/SOL (XRP: 2 retests, 0
selected; DOGE: 0 retests). Trust gate passes: `selected == approved_trades` for all 6.

| Reject-reason class | pooled ΔE | perm p | ΔE OOS | sign-consistency | n_inst | total rejects |
|---|---:|---:|---:|:--:|:--:|---:|
| **ALL** | **+1.171** | **0.0005** | +1.212 | 4/4 | 4 | 112 |
| **SESSION** | **+1.171** | **0.0005** | +1.212 | 4/4 | 4 | **110** |
| **ZONE** | n/a | 1.000 | n/a | 0/0 | 0 | **0** |
| **SCORE** | +1.154 | **0.327** | **−0.291** | 2/2 | 2 | **2** |
| **OTHER** | n/a | 1.000 | n/a | 0/0 | 0 | 0 |

## What this means

1. **The selected-vs-rejected effect is large and real (+1.17R, p<0.001, OOS +1.21, 4/4) — but it
   is ENTIRELY the SESSION filter.** `SESSION ≡ ALL`: 110 of 112 rejects are off-session; the pooled
   effect, OOS, significance, and sign-consistency are identical between the two. Selected
   (in-session) retests beat session-rejected (off-session) retests — which is exactly the
   already-deployed session filter doing its job.

2. **The genuine selection-skill classes (SCORE/ZONE) are non-binding / null.** `ZONE` **never
   fires** (0/110 — the discount/premium-zone filter rejects no score-approved retest). `SCORE` has
   **2 rejects total** (BTC 1, ETH 1) → p=0.33 and **OOS flips negative (−0.29)**: statistically
   nothing. This is structural, not just low-power: F-006b already showed the retest score gate is
   non-binding (134/135 pass), so even with more data the score/zone gates would still pass ~all of
   what reaches them. **Beyond the session filter, the spine's RETEST selection adds nothing.**

3. **F-002 does not survive as NEW skill under intrabar truth.** The "+0.145R selection edge" was a
   pre-intrabar, no-cost, BNB-only number. Under the governing standard, what survives is the
   **incumbent session filter** — and F-017 already showed that filter is **non-improvable** by
   re-optimizing session boundaries OOS. So the SESSION ΔE is the value of an *already-deployed*,
   *non-extractable-further* lever, not a new edge. (It is also partly a confound: "off-session
   bars have worse forward-RR" is a market regularity the filter exploits, not spine "skill.")

4. **Doctrine guard worked.** Without the reject-reason decomposition we would have seen `ALL` ΔE=
   +1.17 / p=0.0005 / 4-of-4 / OOS +1.21 and **falsely declared selection skill**. The decomposition
   localized 100% of it to the SESSION class — the precise failure mode this design was built to
   prevent ("measuring a resurrected session filter and calling it selection skill").

## Roadmap implication

Three falsifications now stand under the governing truth standard: **direction (F-019)**,
**conditional direction (F-020)**, and **selection-beyond-session (F-021)**. The only in-spine lever
that "works" is the **session filter**, which is incumbent and F-017-non-improvable. **Every in-spine
entry/selection lever is now exhausted.** The remaining unfalsified thread is **exit/cost structure
(Phase D)** — the 88%-plain_stop_loss + cost-drag forensic — which is a different problem class
(post-entry, not entry/selection). 

## Caveats (kept for replay)

- **N is thin:** effectively 4 instruments; SCORE rests on 2 rejected samples. The SCORE *estimate*
  is underpowered — but the *structural* facts (ZONE 0/110, SCORE 2/110, SESSION 110/112) are
  power-independent: the retest funnel is gated by SESSION, not score/zone.
- The SESSION ΔE compares in-session vs off-session populations (off-session rejects can't be
  session-matched, by construction) — so it is inherently the session-filter confound, not
  isolable "skill."

## Reproduce
```
python scripts/research/phase_s_selection_effect.py
```
Deterministic: JSON body carries no wall-clock; a second run is byte-identical.
