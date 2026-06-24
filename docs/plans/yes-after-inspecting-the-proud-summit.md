# Plan: Repository Evolution Audit — Liquidity-State Intelligence Thesis

> Created: 2026-06-03 · Updated: 2026-06-03 · Milestone: cross-cutting (Trd track / analysis)

## Context

The user proposed a "liquidity-state intelligence" architecture — liquidity constraints →
state geometry → liquidity archetypes → profitability regions → outcome database — and
suspected, correctly, that much of it may already exist in Tradelatest under different names.
A three-agent mining pass against the **code** (not just docs) confirmed this and corrected
three load-bearing assumptions in the original thesis:

1. **OOS persistence study is COMPLETE, not open** — validated across all 4 instruments
   (BNBUSDT/SOLUSDT/ETHUSDT/BTCUSDT), temporal 70/30 split, no shuffle. Verdict "persistence
   is REAL," but edge is **economically marginal** (+0.02–0.09R).
   ([`feature-region-oos-persistence-2026-06-01.md`](docs/analysis/feature-region-oos-persistence-2026-06-01.md)
   + the multi-instrument follow-up).
2. **ReplayMemory cluster-0 collapse is already FIXED** (2026-06-02): `center`/`centroid`
   fallback + `feature_weights` applied, with regression tests
   ([`test_assign_cluster.py`](tests/replay/test_assign_cluster.py)). It is trustworthy but
   deliberately async / monitoring-only, frozen behind *Schema-Consistency-Before-Fusion*.
3. **The binding ROI lever is GOVERNANCE, not intelligence** — the entire +0.584R edge
   appears at the RETEST→EXECUTION gate (session filter dominant); pre-execution geometry is
   expectancy-neutral ([`gate-contribution-bnbusdt-2026-06-03.md`](docs/analysis/gate-contribution-bnbusdt-2026-06-03.md)).
   Adding ASIA to BNBUSDT sessions moved ROI **+4.91% → +20.59%** with zero new code.

**Outcome intended:** two matched artifacts — (A) a grounded, point-in-time *Repository
Evolution Audit* that maps the thesis onto existing code with completion %, and (B) a reusable
*audit prompt* a fresh Claude session can run to regenerate (A) — laying out both the
governance track and the liquidity-intelligence track neutrally and **making the prioritization
call inside the doc**. This is an analysis/documentation deliverable: **no production code, no
config, no promotion.**

## Deliverables (both, doc-only)

### Artifact A — the audit
`docs/analysis/repository-evolution-audit-liquidity-state-2026-06-03.md` (kebab-case + dated,
per `docs/analysis/` convention: historical, NOT a living doc).

Sections:
1. **Thesis vs reality** — the three corrected assumptions above, each with file:line evidence.
2. **Concept→code completion map** (the table below), each row citing real file:line.
3. **What exists / partial / dead** — the narrow open set: (a) per-instrument registry routing
   in CognitiveBus (designed, unwired), (b) re-homing ReplayMemory to the synchronous
   deterministic path before any non-zero fusion weight, (c) the marginal-edge problem.
4. **Two tracks, neutrally stated, then a recommendation** (user chose "decide in the doc"):
   - *Governance/throughput track* — proven to pay (per-instrument session policy via the
     landed `resolve_allowed_sessions` resolver, [`production_config.py:281`](src/config_layer/production_config.py);
     wiring per-instrument zone registries into `CognitiveBus`).
   - *Liquidity-intelligence track* — Feature Space Intelligence V2 (richer liquidity features,
     archetype registry refinement), bounded by the measured marginal edge.
   - **Recommendation (to be argued in-doc):** lead with governance (evidence-backed, reversible,
     no new intelligence); treat liquidity-intelligence as a measured-only secondary track that
     must beat existing zone features OOS before earning any non-zero fusion weight. Frame the
     #1 risk explicitly: *rebuilding Zone Registry + Feature Space Intelligence under new names.*
5. **Minimal validation experiment** — the single measure-only test that gates the intelligence
   track: do liquidity-state features beat existing 38-dim zone features OOS (same temporal
   70/30 harness, `feature_region_oos_study.py`), and/or can the marginal edge be made to pay?
   Measure-only, additive, no fusion weight — mirrors the Phase-6 ROI pattern.

### Artifact B — the reusable prompt
`docs/analysis/repository-evolution-audit-PROMPT-2026-06-03.md` — a self-contained
"REPOSITORY EVOLUTION AUDIT" prompt (the template the user sketched, hardened): instructs a
fresh session to audit CRT / Zone Registry / ReplayMemory / Probability Surface / Opportunity
Scanner / BitNet / TradeNet / Gaussian against a liquidity-state thesis, emit the concept→code
mapping table with A/B/C/D classification + completion %, and **read code not just docs**
(the original docs-only scan produced the three wrong assumptions corrected above). Includes
the canonical file:line anchors below as ground-truth seeds.

## The completion map (ground truth for both artifacts)

| Liquidity-state concept | Exists as | Anchor (file:line) | Status | % |
|---|---|---|---|---|
| Liquidity feature space | `CANONICAL_FEATURES` idx 35–37 | [`feature_schema.py:46`](src/features/feature_schema.py) | LIVE | 90 |
| State-transition geometry | CRT `VALID_TRANSITIONS`, 9 states | [`crt_engine_v2.py:1021`](src/config_layer/crt_engine_v2.py) | LIVE | 100 |
| Liquidity archetypes | Zone Registry (KMeans, inv-std wts) | `scripts/research/discover_zones.py` | LIVE | 85 |
| Profitability regions | Zone Gate / probability surface | [`zone_gate_engine.py:191`](src/engines/zone_gate_engine.py) | LIVE, fused @0.20 | 80 |
| Path-profitability DB | ReplayMemory cluster stats | [`replay_memory_engine.py:432`](src/replay/replay_memory_engine.py) | LIVE, async, monitor-only | 70 |
| Region health monitoring | MarketStateClusterEngine + ReplayDriftGovernor | [`market_state_cluster_engine.py:95`](src/regime/market_state_cluster_engine.py) | LIVE | 75 |
| Temporal persistence validation | OOS study | `scripts/research/feature_region_oos_study.py` | COMPLETE | 100 |

## Critical files to cite (read-confirmed in mining pass)
- [`src/config_layer/crt_engine_v2.py`](src/config_layer/crt_engine_v2.py) — `VALID_TRANSITIONS` (1021), session filter (2589–2611)
- [`src/features/feature_schema.py`](src/features/feature_schema.py) — 38-dim `CANONICAL_FEATURES`, v2.0=35 / v3.0=38
- [`src/engines/zone_gate_engine.py`](src/engines/zone_gate_engine.py) — `run_zone_gate_engine`, hard gate
- [`src/replay/replay_memory_engine.py`](src/replay/replay_memory_engine.py) — `_assign_cluster` (394), `_build_cluster_stats` (432), 2026-06-02 fix
- [`src/regime/market_state_cluster_engine.py`](src/regime/market_state_cluster_engine.py)
- [`src/config_layer/production_config.py`](src/config_layer/production_config.py) — `resolve_allowed_sessions` (281), `_canon_session` (266)
- [`src/runtime/backtest_v2.py`](src/runtime/backtest_v2.py) — `scorer_mode` (1461), `_score_outcome_correlation` (605)
- Dated analysis: `roi-funnel-diagnosis-bnbusdt-2026-05-30.md`, `gate-contribution-bnbusdt-2026-06-03.md`, `feature-region-oos-persistence-2026-06-01.md` (+ multi follow-up), `roi-baseline-bnbusdt-2026-05-29.md`, `top-10-roi-actions.md`

## Conventions to honor
- `docs/analysis/` = historical / point-in-time; both files dated `2026-06-03`, kebab-case.
- Distinguish **MEASURED** vs **HYPOTHESIS** vs **[Likely]** throughout (the doc's whole value is grounding).
- No new doc-tree wiring beyond an optional one-line index entry in [`docs/analysis/readme.md`](docs/analysis/readme.md).
- §6 SESSION LOG entry appended to `assistant_project.md` on the implementing turn.
- No topic doc to sync (this is analysis, not a code/topic change) unless we promote a topic stub.

## Verification
This is documentation. Verify by:
1. Every file:line citation in both artifacts resolves to the named symbol (spot-check via Read/Grep — the `Audit` trigger discipline).
2. Both files render (markdown tables well-formed) and live under `docs/analysis/` with dated kebab-case names.
3. The completion table in A and the seed anchors in B agree (no drift between the two artifacts).
4. No code/config/test files modified — `git status` shows only the two new docs (+ optional readme index line + session log).

## Out of scope
- Building any liquidity-intelligence module, per-instrument routing wiring, or fusion changes.
- Promotion / config edits / re-hash. The doc may *recommend* the minimal experiment; it does not run it.
