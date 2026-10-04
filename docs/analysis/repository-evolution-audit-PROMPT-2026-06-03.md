# Reusable Prompt — Repository Evolution Audit (Liquidity-State Thesis)

> **Point-in-time artifact (2026-06-03), but designed to be re-run.** Paste the prompt below into
> a fresh Claude session rooted at the Tradelatest repo to regenerate
> [`repository-evolution-audit-liquidity-state-2026-06-03.md`](repository-evolution-audit-liquidity-state-2026-06-03.md)
> and [`economic-edge-gap-analysis-2026-06-03.md`](economic-edge-gap-analysis-2026-06-03.md).
> The seed anchors below are dated — re-verify each `file:line` before trusting it.

## Why this prompt exists (the lesson it encodes)

The **first** pass at this thesis used a docs-only scan and produced **three wrong assumptions**
(OOS open, ReplayMemory broken, intelligence missing). A code-grounded mining pass overturned all
three. **The non-negotiable rule of this audit: read code, not just docs.** Docs lag; `file:line`
does not.

---

## THE PROMPT (copy below this line)

```
ROLE: Repository Evolution Auditor for the Tradelatest quant trading repo.

GOAL: Determine how much of a proposed "liquidity-state intelligence" architecture
  (liquidity constraints → state geometry → liquidity archetypes → profitability
  regions → outcome/path database) ALREADY EXISTS under different names, and — if
  persistence is real but edge is marginal — WHY the edge is marginal.

HARD RULES:
  1. READ CODE, NOT JUST DOCS. Every claim about what exists must cite a real
     file:line (verify with Read/Grep). Docs-only scans have produced wrong
     assumptions here before. Distinguish MEASURED vs HYPOTHESIS vs [Likely].
  2. Do NOT propose or write production code. This is analysis only — no config
     edits, no promotion, no fusion-weight changes.
  3. Extend, do not rebuild, the prior audit in docs/analysis/audit-2026-06-02/.

DELIVERABLE 1 — REPOSITORY EVOLUTION AUDIT. For each subsystem below, report:
  (a) where it lives (file:line), (b) what the code actually does, (c) live /
  dormant / dead, (d) known bugs or schema mismatches. Subsystems:
    - CRT state machine (VALID_TRANSITIONS, the 9 states)
    - Zone Registry (discovery: KMeans? weights? storage schema? consumption)
    - ReplayMemory (the center/centroid + cluster-0-collapse history; is it
      trustworthy now? is it sync or async? does it feed fusion?)
    - Zone Gate / "Probability Surface" (is a NAMED surface module built, or is
      the capability just the Zone Gate + the OOS study?)
    - Opportunity Scanner, MarketStateClusterEngine, Gaussian, RR, TradeNet, BitNet
    - Feature space (CANONICAL_FEATURES — how many dims? which are "liquidity"?)
  Then emit a CONCEPT→CODE MAPPING TABLE with columns:
    | liquidity-state concept | exists as | file:line | status | A/B/C/D | completion % |
  where A=already implemented, B=partially, C=implemented-under-different-name,
  D=contradicts existing architecture. Estimate completion ∈ {0,25,50,75,100}%.
  Close with: the genuinely OPEN set (what is missing/partial) and the #1 risk
  (rebuilding existing capability under a new name).

DELIVERABLE 2 — ECONOMIC EDGE GAP ANALYSIS (only if the audit finds persistence
  real but edge marginal). Lead with the three-fact paradox, reconcile it
  (which hypothesis: H1 features weak / H2 wrong label / H3 edge is in the
  decision process not state discovery?), enumerate candidate causes each with a
  MEASURE-ONLY diagnostic, define the single gating experiment (can any feature
  track move outcome AUC off 0.5 OOS?), give an opportunity-cost/funding matrix
  (effort × evidence × expected ROI), and end with the one question that gates
  all V2 work: "If feature discrimination is ~0.515, why did governance create a
  ~4x ROI improvement?"

METHOD: launch parallel Explore agents (Zone/Replay, Feature-Space, CRT/funnel)
  to read code; verify every load-bearing number against its dated source doc in
  docs/analysis/ before quoting it.
```

---

## Seed anchors (ground truth — re-verify before trusting)

**Code:**
- `VALID_TRANSITIONS` (9 states) — [`crt_engine_v2.py:1021`](../../src/config_layer/crt_engine_v2.py); enum [:63](../../src/config_layer/crt_engine_v2.py); session filter ~[:2589](../../src/config_layer/crt_engine_v2.py)
- `CANONICAL_FEATURES` 38-dim, liquidity idx 35–37 — [`feature_schema.py:46`](../../src/features/feature_schema.py); DIM [:76](../../src/features/feature_schema.py)
- Zone Gate — [`zone_gate_engine.py:191`](../../src/engines/zone_gate_engine.py)
- ReplayMemory `_assign_cluster` [:394](../../src/replay/replay_memory_engine.py), `_build_cluster_stats` [:432](../../src/replay/replay_memory_engine.py)
- MarketStateClusterEngine [`market_state_cluster_engine.py:95`](../../src/regime/market_state_cluster_engine.py)
- `resolve_allowed_sessions` [`production_config.py:281`](../../src/config_layer/production_config.py); `_canon_session` [:266](../../src/config_layer/production_config.py)
- OOS harness [`feature_region_oos_study.py`](../../scripts/research/feature_region_oos_study.py); discovery [`discover_zones.py`](../../scripts/research/discover_zones.py)
- Regression test for the 2026-06-02 RME fix — [`tests/replay/test_assign_cluster.py`](../../tests/replay/test_assign_cluster.py)

**Dated analysis (numbers):**
- AUC 0.5149 / R² 0.0042 — [`edge-attribution-2026-06-03.md:3`](edge-attribution-2026-06-03.md)
- Accepted-trade AUC 0.5979 (inconclusive) — [`accepted-trade-attribution-2026-06-03.md:8`](accepted-trade-attribution-2026-06-03.md)
- Edge at RETEST→EXECUTION +0.584R — [`gate-contribution-bnbusdt-2026-06-03.md:18`](gate-contribution-bnbusdt-2026-06-03.md)
- OOS retention 0.93–1.51, 4/4 instruments — [`feature-region-oos-persistence-2026-06-01.md:38,62`](feature-region-oos-persistence-2026-06-01.md)
- +4.91%→+20.59% session sweep — [`session-sweep-bnbusdt-2026-06-01.md:44`](session-sweep-bnbusdt-2026-06-01.md); baseline [`roi-baseline-bnbusdt-2026-05-29.md`](roi-baseline-bnbusdt-2026-05-29.md)
- Dead/dormant + top-10 ROI (governance > intelligence) — [`audit-2026-06-02/`](audit-2026-06-02/readme.md)

## Expected conclusion (what the last run found — confirm, don't assume)
The thesis is **Feature-Space Intelligence V2, not a rebuild** — 70–90% already present. Edge is
**marginal because it was never a feature map**; the decision process (selection + execution
structure) is the profit center, and governance's ~4x is largely a one-time policy correction.
Gate all V2 intelligence behind the single AUC-off-0.5 experiment.
</content>
