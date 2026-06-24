# Economic Edge Gap Analysis — Phase 0: Economic Edge Diagnosis (2026-06-03)

> **Point-in-time snapshot, NOT a living doc.** The missing document: not *"what exists?"*
> (that is [`repository-evolution-audit-liquidity-state-2026-06-03.md`](repository-evolution-audit-liquidity-state-2026-06-03.md))
> but **"if OOS persistence is real, why is the economic edge marginal?"** Measure-only framing.
>
> **▶ Phase-0 EXECUTED 2026-06-03 → FAIL (0/4 instruments).** The battery (§4 + §7 + §8) ran on
> all 4 instruments: no feature track beat the incumbent +0.328R selection on net rr. Verdict +
> full economics: [`phase0-economic-edge-diagnosis-2026-06-03.md`](phase0-economic-edge-diagnosis-2026-06-03.md)
> (artifact `results/phase0_economic_edge/phase0_diagnosis.json`). **Do not fund Liquidity/BitNet/
> TradeNet/Probability-Surface V2; continue the governance/execution track.** §8 below is now filled
> with the measured numbers. H3 confirmed.

## Why this is the highest-value artifact

After the mining pass, "can we build liquidity-state intelligence?" is answered — the repo is
70–90% there. The strategic question flips to **edge economics**. If persistence is real but ROI
is weak, then *edge creation* — not *architecture creation* — is the bottleneck, and the next
engineering month should be aimed accordingly.

---

## 1. The headline paradox

Three measured facts that do **not** naturally fit together — and therefore likely contain the
real bottleneck:

```
feature AUC ≈ 0.5149   ← which setup you pick barely discriminates outcome
+ OOS persistence real ← profitable regions retain their (small) mean out-of-sample
+ governance gave ~4x  ← +4.91% → +20.59% from session policy alone, zero new code
```

Sources: AUC [`edge-attribution-2026-06-03.md:3`](edge-attribution-2026-06-03.md);
persistence [`feature-region-oos-persistence-2026-06-01.md:38`](feature-region-oos-persistence-2026-06-01.md);
+20.59% [`session-sweep-bnbusdt-2026-06-01.md:44`](session-sweep-bnbusdt-2026-06-01.md).

### Lead hypothesis — H3: the profit center is the decision *process*, not state discovery

If *which* setup you pick is ~coin-flip (AUC 0.515) yet *the decision process* (session policy +
execution-planner SL/TP) moved ROI 4x, then the edge was **never a static feature→outcome map**.
The repo's own conclusion: *"the edge is created by selectivity (which candles are allowed to
trade), not by a static map from features to outcome"* ([`edge-attribution-2026-06-03.md:14`](edge-attribution-2026-06-03.md)).

**A sharper, sobering reading of the +4x:** the session expansion *raised* PF (1.79→2.54) while
*adding* trades (15→35) — ASIA (+8) and OFF_SESSION (+12) composed exactly to +20
([`session-sweep-bnbusdt-2026-06-01.md:44,48`](session-sweep-bnbusdt-2026-06-01.md)). Adding
trades that *raise* PF means the prior session config was **excluding good trades** — the 4x is
largely a **one-time policy correction**, not a repeatable intelligence edge. You can un-exclude
sessions once; the ~35-trade ceiling is then a *detection-supply / policy* limit
([`top-10-roi-actions.md:64`](audit-2026-06-02/top-10-roi-actions.md)), not a feature problem.

**The lead insight, stated plainly: timing *inside* a state beats pattern identity.** The only
feature with durable signal is `candles_since_retest` — retest *timing* (Edge Score 0.48) —
while `hour_of_day` *by itself* is ~0 ([`edge-attribution-2026-06-03.md:8,22`](edge-attribution-2026-06-03.md)).
So the market is not rewarding *which* pattern/state you find; it is rewarding *when, inside a
state, you act*. The productive question becomes **"find the right moment inside an existing
state," not "find a magical new state."** This is the original liquidity-state intuition — now
evidence-backed, and it points the next experiment at contextual timing, not new geometry.

### H3 vs the alternatives

| # | Hypothesis | Verdict on current evidence | What would falsify it |
|---|---|---|---|
| H1 | Features are weak (discrimination ceiling) | **SUPPORTED.** Per-candle AUC 0.5149, R²=0.0042; drop-column marginal ≈0 for all but `candles_since_retest` (ΔR² 0.0024) and `volatility_ratio` (0.0004) ([`edge-attribution-2026-06-03.md:7,22`](edge-attribution-2026-06-03.md)). | A feature track (existing or liquidity-V2) moving OOS AUC materially off 0.5. |
| H2 | Wrong target / label | **OPEN.** `rr_achieved` uses the scanner's SL/TP + 0.5R trail; a different exit definition "could move ranks" ([`edge-attribution-2026-06-03.md:84`](edge-attribution-2026-06-03.md)). Untested. | Re-labelling on TP1 / survival / MFE leaves AUC at chance. |
| H3 | Edge is in the decision process (selection + execution structure), not state | **SUPPORTED.** Entire +0.584R appears at RETEST→EXECUTION ([`gate-contribution-bnbusdt-2026-06-03.md:18`](gate-contribution-bnbusdt-2026-06-03.md)); the one durable feature is `candles_since_retest` — retest *timing* (Edge Score 0.48). | A counterfactual showing the +0.58R jump is feature/geometry-driven, not session+SL/TP. |

**Open conflation (must not over-read H3):** the +0.58R EXECUTION jump conflates *(a)* which
retest candles are selected (session+score) and *(b)* the execution-planner's structure-based
SL/TP vs the counterfactual's vanilla fixed SL/TP — *"this method cannot separate"* them
([`gate-contribution-bnbusdt-2026-06-03.md:29`](gate-contribution-bnbusdt-2026-06-03.md)). The
recommended experiment is to replay the planner's SL/TP on rejected retest candidates.

---

## 2. What the repo ALREADY answers (do not rediscover)

- **Persistence ≠ discrimination.** Regions retain a *small mean* OOS (retention 0.93–1.51) but
  the features barely separate winners from losers (AUC 0.515) — so averaging over a region
  yields a small edge, and 6/8 zones are persistently *negative*
  ([`feature-region-oos-persistence-2026-06-01.md:44,77`](feature-region-oos-persistence-2026-06-01.md)).
- **The edge is at the execution gate.** Pre-execution geometry (SWEEP→RETEST) is
  expectancy-neutral (mean rr ∈ [−0.039, +0.021]R); only DISPLACEMENT nudges +0.048R
  ([`gate-contribution-bnbusdt-2026-06-03.md:17,24`](gate-contribution-bnbusdt-2026-06-03.md)).
- **Accepted-trade lift is real but inconclusive.** Among 439 accepted trades, AUC rises
  0.5149→0.5979 (Δ+0.083) — but R²=−0.2495 (negative; magnitude unpredictable) and N is small
  across heterogeneous configs: *"does not justify building a feature/cluster predictor yet"*
  ([`accepted-trade-attribution-2026-06-03.md:8-9`](accepted-trade-attribution-2026-06-03.md)).
- **The 4x lever is throughput policy**, not intelligence ([`top-10-roi-actions.md`](audit-2026-06-02/top-10-roi-actions.md)),
  and "enabled ≠ consumed" — a backlog of built signals is unwired ([`dead-dormant-inventory.md:45`](audit-2026-06-02/dead-dormant-inventory.md)).

---

## 3. Candidate causes of marginal edge — status + measure-only diagnostic

Each diagnostic is **measure-only**: no fusion weight, no config promotion, additive telemetry.

| Hypothesis | Status from repo | Diagnostic (measure-only) |
|---|---|---|
| Feature quality (weak discrimination) | **[partially answered]** AUC≈0.515; marginal≈0 | per-feature & liquidity-V2 AUC vs outcome on the OOS **test** split (the gating experiment, §4) |
| Wrong target (label) | **[open]** | re-label the opportunity set on alt targets (TP1 vs survival vs MFE), recompute AUC; reuse scanner outcomes |
| Weak execution layer | **[partially answered]** edge *is* execution, but selection-vs-SL/TP unseparated | replay `ExecutionPlannerV1_2` SL/TP on the rejected retest candidates (the gate-contribution "recommended next experiment") |
| Insufficient leverage / sizing | **[open]** | `risk_percent` → ROI elasticity from existing backtest runs; no new trades needed |
| Over-averaging (region too coarse) | **[open]** | retention vs `k` (n_clusters) and per-zone sample-size curve in `feature_region_oos_study.py` |
| Wrong clustering (geometry / weights) | **[partially answered]** inverse-std fixed price-domination | inverse-std vs alternative weighting retention comparison (both already runnable) |
| Missing path information | **[open]** | does ReplayMemory path-stat (per-cluster win_rate/trap_freq) add AUC **beyond** static zone features? |
| Regime dilution | **[open]** | per-regime (MarketStateClusterEngine, 6 regimes) expectancy decomposition |

---

## 4. The one experiment that gates everything

> **Can *any* feature track — the existing 38-dim set OR a liquidity-V2 set — move outcome AUC
> materially off 0.5 on the OOS test split?**

Reuse [`scripts/research/feature_region_oos_study.py`](../../scripts/research/feature_region_oos_study.py)
(temporal 70/30, no shuffle, inverse-std weights). If the answer is **no**, then no
intelligence-V2 layer can pay — the Probability-Surface / cluster-space / TradeNet thesis is an
*engineering-saving negative result* ([`edge-attribution-2026-06-03.md:9`](edge-attribution-2026-06-03.md))
— and the governance/execution track is the only rational investment. Measure-only, additive,
weight 0.0.

---

## 5. Opportunity-cost / funding matrix

Where the next engineering month goes, ranked by effort × evidence (priority aligns to the
funding doctrine — immediate vs gated):

| Initiative | Effort | Evidence | Priority |
|---|---|---|---|
| Governance / session policy (per-instrument) | Low | **Measured** (+4.91→+20.59%, [`session-sweep`](session-sweep-bnbusdt-2026-06-01.md)) | **Very High** (one-time, ceilinged) |
| Phase-0 AUC diagnosis (the §4 experiment) | Low | — (the test itself) | **High** (unlocks everything below) |
| Per-instrument registry routing (CognitiveBus) | Med | Partial (designed) | **High** |
| Wire dormant signals (drift→size-down, zone expectancy, bitnet persist) | Low–Med | Partial (built, unconsumed) | Medium (capital protection) |
| ReplayMemory → synchronous deterministic path | Med | Unknown | Medium (gated) |
| Liquidity-feature V2 | High | **Hypothesis** (AUC≈0.515 today) | **Low until Phase-0** |
| BitNet V2 | Very High | Weak | **Very Low until Phase-0** |
| TradeNet V2 | Very High | Weak (slot is a stub) | **Very Low until Phase-0** |

The "until Phase-0" rows are exactly the ones the kill criteria (§7) gate **before** funding.

---

## 6. Decision gate + the single question

**Rule.** Governance/execution levers (Track G) proceed now — proven, reversible, no new code.
**No** Liquidity / BitNet / TradeNet / Probability-Surface V2 work is funded until Phase 0
(a) reconciles the H3 paradox (separate selection from SL/TP) and (b) shows a feature track
beats AUC 0.5 OOS with execution-layer headroom exhausted.

> **The question to answer before any implementation begins:**
> *"If feature discrimination is ~0.515, why did governance create a ~4x ROI improvement?"*

The working answer (H3, this doc): because the edge was always in the **decision process**, and
the prior session policy was leaving good trades on the table — a correction worth banking once,
not a feature edge worth building V2 intelligence to chase. Confirm or refute it with §4 before
committing the month.

---

## 7. Kill Criteria — converting research into capital allocation

A hard, falsifiable stop-funding threshold so Phase-0 cannot decay into endless exploration.

**The rule (binary, no escape hatch):**

> If no feature track **materially exceeds the AUC 0.515 baseline OOS** (on the temporal test
> split) after **all three** exhaustion conditions —
> (i) re-labeling on alternate targets (TP1 / survival / MFE),
> (ii) path enrichment (ReplayMemory per-cluster path stats),
> (iii) regime decomposition (MarketStateClusterEngine, 6 regimes) —
> then **Liquidity V2, BitNet V2, and TradeNet V2 do not receive funding.**

**"Materially" is a number, not a judgment call:**

| Outcome | Statistical test | Economic test | Funding decision |
|---|---|---|---|
| **PASS** | ΔAUC **≥ +0.03** OOS *and* a positive expectancy lift that survives the gate context (not a train-set bump) | upside (§8) **>** migration cost | **FUND** |
| **FAIL** | ΔAUC < +0.03 OOS, *or* lift does not survive the gate | — | **DO NOT FUND** |
| **STAT-PASS / ECON-FAIL** | ΔAUC ≥ +0.03 | upside ≤ migration cost | **DO NOT FUND** (see §8) |

After the experiment runs there is **no "investigate a bit more" branch** — the result is PASS or
FAIL, and FAIL means stop.

**Burden of proof is on the challenger.** The existing architecture is the default and is presumed
correct until *measured improvement > migration cost*. Liquidity V2 must prove **superiority, not
parity** — this guards against the "0.515 → 0.518, let's rebuild anyway" trap that quietly burns
months of engineering time.

---

## 8. Expected Maximum Upside — AUC → ROI translation (ΔAUC ≠ ΔROI)

A real, statistically-significant discrimination gain can still be economically trivial. Before
funding a large V2 effort, estimate the ROI a hypothetical AUC gain would actually produce, via
the system's own identity `ROI ≈ N × R̄ × risk%`
([`roi-funnel-diagnosis-bnbusdt-2026-05-30.md:9`](roi-funnel-diagnosis-bnbusdt-2026-05-30.md)),
anchored to the measured baseline (PF 1.79, R̄ +0.328R, N≈15–35,
[`roi-baseline-bnbusdt-2026-05-29.md`](roi-baseline-bnbusdt-2026-05-29.md)).

**Bracket three scenarios so funding is never planned around best-case** (filled by the Phase-0
run, 2026-06-03; conservative AUC→R̄ proxy, order-of-magnitude):

| Scenario | ΔAUC OOS | Expected ROI delta |
|---|---|---|
| Conservative | +0.03 | **+0.42pp** |
| Base | +0.06 | **+0.84pp** |
| Optimistic | +0.09 | **+1.26pp** |

**This is the decisive number.** Even the optimistic +0.09 AUC scenario yields **~+1.3pp** of ROI —
against a measured governance lever that moved BNB **+4.91% → +20.59% (~+15.7pp)**. A best-case
intelligence gain is **~12× smaller** than the proven throughput-policy lever. And Phase-0 measured
**realized** legit ΔAUC = **+0.05** with selected net rr (+0.15R) **below the incumbent +0.328R** →
realized economic floor **does not clear**. ΔAUC ≠ ΔROI, decisively.

**Sobering anchor:** the persistent OOS gradient is only ~+0.02–0.09R and any surface enters at a
**low / 0.0 advisory weight** (never a primary gate, per the frozen
*Schema-Consistency-Before-Fusion* invariant) — so even a real AUC bump moves ROI very little.

**Decision coupling.** The §7 statistical floor (ΔAUC ≥ +0.03) is **necessary but not
sufficient**: the upside must also exceed the migration cost. Phase-0 result: **statistical FAIL
(legit ΔAUC +0.05 with negative economic translation) → do not fund.** Both gates must clear to
green-light V2; neither did.

---

## Caveats

- Every number is **backtest-measured** on specific BNBUSDT (and pooled multi-instrument) runs;
  `UltronRiskGate` + `ExecutionPlannerV1_2` are live-only, not in the backtest spine — live PnL unverified.
- The per-candle attribution is on scanner *opportunities* (every candle → a setup), not executed
  trades — near-chance AUC there is *expected* and does not mean the live system lacks edge.
- N for the accepted-trade study is 439 across heterogeneous configs — single-feature spikes are noisy.
</content>
