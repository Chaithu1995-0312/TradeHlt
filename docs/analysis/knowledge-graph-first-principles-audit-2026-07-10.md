# First-Principles Audit: Knowledge Graph + Preregistered Experiments

> **Point-in-time analysis (2026-07-10).** Not living truth. Does **not** flip
> `docs/current-findings.md` economic verdicts. Treats historical F-xxx results as
> **untrusted observations requiring replication**, not evidence for closure.

**Artifacts:** `knowledge_graph.json` (audited → decontaminated to v0.4),  
`preregistered_experiments.md` (revised under same assumption).  
**Excluded from economic adjudication:** F-xxx verdicts, result ledgers, Program 1–8 closures.  
**Structural context only:** `data/perp/*_FUNDING_8H.csv`, `*_BASIS_M15.csv`, OHLCV under `data/`.

---

## Governing assumption (Certain)

> Repository findings, backtest results, lineage verdicts, profitability claims,
> null results, and falsifications are **not admissible as finalized economic
> evidence** until the relevant bugs are resolved and the measurement pipeline is
> revalidated.

**Most likely failure mode:** allowing contaminated repository conclusions to
silently bias the knowledge graph and prereg set, prematurely eliminating
hypotheses that were never validly tested.

**Required architecture:**

```text
KNOWLEDGE GRAPH
      ↓
THEORETICAL / EMPIRICAL LITERATURE COVERAGE
      ↓
HYPOTHESIS SPACE
      ↓
PREREGISTERED EXPERIMENTS
      ↓
DEPENDENCY + DATA REQUIREMENTS
      ↓
MEASUREMENT-TRUST GATE
      ↓
NEW CLEAN EXPERIMENTAL RESULTS
      ↓
ONLY THEN: VALIDATED / FALSIFIED / INCONCLUSIVE
```

---

## 1. GRAPH COVERAGE

### 1.1 Inventory (as audited)

| Layer | Content |
|-------|---------|
| Taxonomy | B1 Market Structure · B2 Time Horizons · B3 Information Sets · B4 Strategy Archetypes · B5 Execution & Infrastructure · cross-dims Risk/Liquidity/Regime |
| Method nodes | **37** at audit time (`MOM-*`, `MR-*`, structural, OF, candle/MTF, regime, ML, alt, exec/size/risk) |
| Gap nodes | **6** (agent ecology, narrative contagion, RWA, causal interventions, critical-transition EWS, secular drift) |
| Edges | **19** |
| Literature | ~17 nodes with ≥1 seminal cite; **~20** thin / `EVIDENCE_PENDING` |

### 1.2 Strengths (structure, not economics)

1. Classical quant spine present (momentum, MR, VRP, carry, arb, MM, OFI, regimes, ML, sizing, TCA, EWS).
2. Payoff-space thinking exists (regime → sizing / funding / LP edges).
3. Defensive science hooks (`OF-IMBALANCE ⟂ CANDLE-STATE`; GAP-04 causal critique of associative ML).
4. Taxonomy falsification boundaries per branch.
5. Gap set is high-novelty (not a re-label of textbook factors).

### 1.3 Structural defects

| Defect | Impact |
|--------|--------|
| **Contamination by untrusted repo conclusions** (`C-F030` as law; `repo_status` asserting VALIDATED/FALSIFIED/PRIORITIZED) | Silently closes/prioritizes regions before clean replication |
| Incomplete method schemas (assumptions/bounds/kill_markers missing on most nodes) | Nodes are labels more than testable objects |
| Sparse causal graph (19 edges / 43 entities; many isolates) | Understates dependencies |
| Branch tag inconsistency (`B2/Medium-Long` vs `B2/MediumLong`) | Harder coverage enumeration |
| Evidence layer incomplete by own admission | Ranking by “evidence strength” premature |
| Phase-3 plan: “falsified-region removal” via findings export | Would formalize untrusted closures |

### 1.4 Branch density (not quality)

High: B4/ML, B4/Structural. Medium: MR, order-flow, regime, exec/capital. Thin: pure OHLCV beyond candle FSM, ultra-low latency as first class, CrossDim/Risk, multi-asset TS ensemble / lead-lag, **correlation-regime**.

---

## 2. MISSING KNOWLEDGE FAMILIES

Judged by literature / experimentability — **not** prior repo nulls.

### 2.1 High priority (added as UNTESTED stubs in v0.4 graph)

| Family | ID | Why |
|--------|-----|-----|
| Measurement / labeling integrity | `MEAS-INTEGRITY` | Substrate for all economic claims |
| Seasonality / calendar microstructure | `SEAS-CAL` | Cheap on OHLCV; large empirical literature |
| Cross-asset lead-lag | `XASSET-LEADLAG` | Distinct from MOM-XS |
| Correlation / dispersion regimes | `REGIME-CORR` | Not vol-only |
| Funding cashflow harvest | `CARRY-FUNDING-HARVEST` | Split from funding-as-signal |
| Cash-and-carry joint (basis+funding) | `CARRY-CASH-AND-CARRY` | Data present under `data/perp/` |
| Meta-labeling / triple-barrier | `METHOD-METALABEL` | Hygiene + secondary model family |
| Simple crypto factor zoo | `FACTOR-CRYPTO-SIMPLE` | Literature baseline before architecture |
| Liquidity proxies (Amihud/roll/Kyle-λ) | `LIQ-PROXY` | Gates short-horizon claims |

### 2.2 Medium priority (not all stubbed this pass)

Options skew/term-structure; deeper on-chain cohorts; smart-money clustering; Glosten–Milgrom decomposition; CPPI/portfolio insurance; macro surprise calendars; EXEC-SOR; MVO/RP beyond HRP; jump/crash risk premium; token unlock calendars; stablecoin peg dynamics.

### 2.3 Correctly deferred (feasibility, not falsification)

GAP-03 RWA legal-oracle; GAP-06 secular drift; equities PEAD/accounting multi-factor as scope-out (not kill); production LOB MM / DeepLOB (latency + L2 cost).

---

## 3. REDUNDANCIES

| Cluster | Recommendation |
|---------|----------------|
| REGIME-HMM / CPD / MoE | Keep distinct; MoE = router, not detector |
| MOM-TS / MOM-BRK | Shared baseline protocol |
| OF-IMBALANCE → DEEPLOB → HAWKES | Test imbalance before deep models |
| ML-TREES / ML-DEEPSEQ | One nested comparison |
| ALT-NLP / ML-LLM / GAP-02 | Contagion only after polarity baseline |
| CANDLE-STATE / MTF-MODELS | Audit (E-P2-05), not production bet by default |
| CARRY-CRYPTO / basis / harvest | Split signal vs harvest vs joint cash-and-carry |
| SIZE-KELLY / SIZE-VOLTARGET | Different principles; do not privilege vol-target via contaminated prior |
| RISK-EWS / GAP-05 | Classic EWS metrics before TDA/flickering complexity |

---

## 4. EXPERIMENT COVERAGE (original seven)

| ID | Role | Status under untrusted measurement |
|----|------|-------------------------------------|
| E-P2-01 | Vol → non-dir consumption | Defer until E-VOL-00; strip “validated H_atr”; optional directional arm |
| E-P2-02 | OFI ⟂ candle | Park until L2 |
| E-P2-03 | Critical-transition EWS | Keep stage 1; consumption path separate stage-2 |
| E-P2-04 | Funding natural experiment | **Promote** (causal; data partial) |
| E-P2-05 | Candle incremental audit | **Promote** (defensive) |
| E-P2-06 | Narrative contagion | Low rank (cost/DF) |
| E-P2-07 | Cross-ex dispersion | Medium; multi-venue needed |

**Missing axes in original seven:** measurement trust; literature baselines; pure vol predictability (info-level); directional consumption (explicitly pre-excluded via C-F030); seasonality; lead-lag; factor zoo; meta-label; dedicated TCA/cost experiment.

---

## 5. MISSING EXPERIMENTS (new IDs)

| ID | Name | Tier |
|----|------|------|
| E-MT-00 | Measurement-Trust Gate | 0 blocking |
| E-MT-01 | Label re-derivation protocol | 0 blocking |
| E-BASE-01…05 | TS mom, naive vol-target, funding harvest, MR, seasonality | 1 |
| E-VOL-00 | Pure vol/regime predictability (info only) | 1 |
| E-VOL-DIR | Directional vol/regime consumption (re-opened) | 2 after E-VOL-00 |
| E-CARRY-JOINT | Basis+funding cash-and-carry | 2 |
| E-XASSET-01 | BTC→alt lead-lag | 2 |
| E-META-01 | Meta-label passing bases | 3 |
| E-COST-01 | Impact/slippage calibration | 3 |

---

## 6. SCIENTIFIC DEFECTS

### 6.1 Contaminating protocol (critical)

1. C-F030 as architectural law from untrusted F-030.
2. Phase-3 “falsified-region removal” via findings export.
3. E-P2-01 assumes validated H_atr.
4. E-P2-01 Arm A requires existing positive-expectancy base (may be empty under clean measurement).
5. Economic SUPPORTED/HARMFUL without measurement-trust gate.

### 6.2 Design / stats

Portfolio-level multiplicity unstated; n≥100 often underpowered for ΔSharpe 0.15; AUC≥0.65 arbitrary; liquidation event lookahead risk; L2 latency mismatch; social PIT / researcher DF; no explicit leakage battery appendix.

### 6.3 Target quality

Prefer forward-walk economic labels under fixed exit/cost. Separate information metrics (IC/AUC) from economic metrics (net E, deflated Sharpe). Retain INSUFFICIENT ≠ HARMFUL vocabulary as **governance**, not as F-031 economic authority.

---

## 7. EXPECTED INFORMATION GAIN

| Rank | Experiment | EIG |
|------|------------|-----|
| 1 | E-MT-00/01 | Maximal — gates all economic claims |
| 2 | E-BASE battery | Very high — rewrites global prior |
| 3 | E-VOL-00 | Very high — honest gate for consumption research |
| 4 | E-P2-04 | High — causal |
| 5 | E-P2-05 | High — complexity justification |
| 6 | E-CARRY-JOINT / E-BASE-03 | High — data-present structural |
| 7 | E-P2-01 revised | Medium-high **after** E-VOL-00 |
| 8–10 | Lead-lag, seasonality, E-P2-07, E-VOL-DIR | Medium |
| 11+ | E-P2-03, meta/cost, E-P2-02, E-P2-06 | Medium → low near-term |

---

## 8. COST

| Tier | Items | Data |
|------|-------|------|
| Low | E-MT-*, E-BASE-*, E-VOL-00, E-P2-05 | OHLCV + funding/basis + code audit |
| Medium | E-P2-01 revised, E-P2-04, E-P2-07, E-CARRY-JOINT, E-XASSET | Multi-asset; multi-venue optional |
| High | E-P2-03 (liquidation tape), E-P2-02 (L2), E-P2-06 (social) | External feeds |
| Defer | GAP-01 sim, GAP-03, GAP-06 | Horizon/infra mismatch |

**On disk (availability only):** `data/perp/{BNB,BTC,ETH,SOL,DOGE,XRP}USDT_{FUNDING_8H,BASIS_M15}.csv`; majors + FX OHLCV. **Not observed:** L2, social firehose, options chains, full liquidation micro-events.

---

## 9. RANKED RESEARCH PORTFOLIO

**Rule:** No experiment’s economic verdict is final until E-MT-00 passes for the pipeline that produced its labels and fills. Historical F-xxx → replication targets only, never closure.

| Tier | Fund |
|------|------|
| **0** | E-MT-00, E-MT-01 |
| **1** | E-BASE-*, E-VOL-00, E-P2-05, E-P2-04 |
| **2** | E-P2-01 revised (+ optional E-VOL-DIR), E-CARRY-JOINT, E-P2-07, E-XASSET-01 |
| **3** | E-P2-03 s1, E-META-01, E-COST-01, E-P2-02 (if L2), E-P2-06 (if cheap PIT) |

**Not portfolio closures:** “kill candle because prior null,” “skip directional vol because F-030,” “skip funding harvest because F-034,” “skip XS because F-032.”

---

## 10. STOPPING CONDITIONS

| Condition | Action |
|-----------|--------|
| E-MT-00 fails | Freeze economic adjudication; substrate repair only |
| E-MT-00 pass + all E-BASE net-null | Raise prior edge ≠ simple OHLCV direction; reallocate to structural/execution — without a priori closing complex regions |
| E-VOL-00 fails | Deprioritize E-P2-01; keep E-P2-04/05 |
| E-VOL-00 pass + all E-P2-01 arms fail net | *Information without consumable authority* |
| E-P2-05 ΔIC ≈ 0 | Simplification ticket; not HARMFUL without negative contribution |
| E-P2-06 DF/budget explosion | Hard stop social line |

Per-experiment kill criteria retained as **local** rules; strip “F-030 stands” as global law. Dual-report information + net economic metrics. Stage gates: E-P2-03 s2 ← s1; E-P2-01 ← E-VOL-00; E-P2-02 ← L2.

**Never stops research alone:** a single historical finding ID; underpowered n with dramatic story; gate-OFF/ON spine differences without identity proof; architecture elegance without Δ economic objective.

---

## Decision summary

| Question | Answer |
|----------|--------|
| Prior F-xxx grounds to drop regions? | **No** — replication only |
| Is the KG useful? | **Yes** as search-space scaffold; **not** as settled economics map |
| Are seven preregs adequate? | **No** — missing MT, baselines, pure vol info, reopened directional, seasonality/lead-lag/carry splits |
| Highest leverage | Institutionalize E-MT-00 + decontaminate C-F030 closures; fund Tier 1 |
| This audit’s economic claims | **None** — methodology + portfolio ranking only |

---

## Companion edits (same turn)

1. `knowledge_graph.json` → v0.4-UNTRUSTED-MEASUREMENT: constraints → untrusted priors; neutralized contaminated `repo_status`; missing-family stubs; phase_3 redefinition.
2. `preregistered_experiments.md` → measurement-trust gate; new stubs; E-P2-* decontaminated and re-sequenced.
3. This file indexed in `docs/analysis/README.md`.
