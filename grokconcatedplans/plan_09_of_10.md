# Concatenated session plans — part 9 of 10

Source directory: `docs/plans/`
Files in this part: 6

## Contents

1. `venv-ps-d-tradelatest-python-zazzy-simon.md` (2649 bytes)
2. `when-doing-planning-and-mossy-teapot.md` (7619 bytes)
3. `with-the-docs-gathered-optimized-kettle.md` (7995 bytes)
4. `yes-after-inspecting-the-proud-summit.md` (8463 bytes)
5. `yes-based-on-the-eventual-sunrise.md` (7072 bytes)
6. `yes-reverse-order-indexed-cookie.md` (20458 bytes)


================================================================================
SOURCE_FILE: docs/plans/venv-ps-d-tradelatest-python-zazzy-simon.md
SOURCE_BYTES: 2649
PART: 9/10 FILE 1/6
================================================================================

> Created: 2026-05-07 · Updated: 2026-05-07 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Make `--version` Optional in `from-report` CLI Subcommand

## Context
Running `promotion_manager.py from-report` without `--version` fails with a hard argparse error even though the `ValidationReport` JSON already contains a `config_id` field that is a suitable version label. The fix makes `--version` optional and auto-derives it from `config_id` in the report when omitted.

---

## Critical File
- `src/governance/promotion_manager.py` — the only file to change

---

## Implementation

### 1. Make `--version` optional in the argparse definition
**Location:** `from_report_p.add_argument` call (lines 585–588)

```python
# Before
from_report_p.add_argument("--version", required=True)

# After
from_report_p.add_argument(
    "--version",
    default=None,
    help="Version label; defaults to config_id from the report"
)
```

### 2. Auto-derive version in the CLI handler
In the `if args.command == "from-report":` branch (just before calling `pm.promote_from_report`), add:

```python
version = args.version
if version is None:
    import json as _json
    with open(args.report) as _f:
        _rpt = _json.load(_f)
    version = _rpt.get("config_id")
    if not version:
        parser.error("--version is required: report contains no config_id to derive from")
    print(f"[promotion_manager] --version not supplied; using config_id '{version}' from report")
```

Then pass `version` (not `args.version`) to `pm.promote_from_report(...)`.

---

## Constraints / No-ops
- `promote_from_report()` signature is unchanged — version is still a required parameter there; the default-derivation is CLI-only.
- No changes to `ValidationReport`, `_execute_promotion`, or any other module.
- The report file is opened once here for version derivation; `promote_from_report` opens it again internally — acceptable duplication for minimal diff.

---

## Verification
1. Re-run the original failing command (no `--version`):
   ```
   python src/governance/promotion_manager.py from-report \
     --report results/validation/approved/report_v2_multi_2026_04.json
   ```
   Expected: prints the derived version and proceeds (or fails on a missing report file, not on missing `--version`).

2. Confirm explicit `--version` still works:
   ```
   python src/governance/promotion_manager.py from-report \
     --report <path> --version v2_multi_2026_04
   ```
   Expected: uses the supplied version unchanged.

3. Confirm error message when report has no `config_id` and no `--version` supplied.


================================================================================
SOURCE_FILE: docs/plans/when-doing-planning-and-mossy-teapot.md
SOURCE_BYTES: 7619
PART: 9/10 FILE 2/6
================================================================================

> Created: 2026-06-06 · Updated: 2026-06-06 · Milestone: architecture (pre-autonomy)

# Plan: Autonomy Preconditions Document

## Context

The user wants an autonomous n8n agent eventually, but correctly argues the next bottleneck is **not** automation — it's a **frozen objective function + frozen accept/kill/escalate rules + the two safety blockers (F-006, F-010)**. Building a research engine before freezing what it optimizes = "faster mistakes." So the first deliverable is **not** an autonomy *architecture* doc (`agent_state.json`, decision policy) — it is an **Autonomy Preconditions** doc that freezes the six things that must be true before autonomy is safe or useful.

This doc does not build the agent. It defines the contract the agent will later be held to, citing thresholds that **already exist in code** (so the rubric is real, not invented).

**Deliverable:** `docs/architecture/autonomy-preconditions.md` + discoverability hooks.

---

## The six preconditions (each = a section with a frozen definition + done-criteria checkbox)

### Precondition 0 — Objective function (frozen)
Two layers, stated as constrained optimization:
- **Hard constraints (never traded off):** the 7 invariants from [`goal.md`](docs/architecture/goal.md) §3 + the priority hierarchy *replay correctness > explainability > telemetry continuity > advisory-AI > (structure validity ≠ execution validity)*.
- **Economic objective (what the agent maximizes within constraints):** selection quality + throughput (N), per **F-001** (intelligence is NOT the constraint), **F-002** (edge is in selection, not pattern identity), **F-003** (throughput is the ROI lever). Profit is the downstream result, not the proximate target.
- Frozen statement: *"The agent maximizes risk-adjusted throughput of high-selection-quality trades, subject to the goal.md invariants as hard constraints. It never optimizes activity (experiment count) as a proxy."*

### Precondition 1 — Promotion / acceptance rubric (frozen, cite code)
Reproduce the existing thresholds as the frozen accept gate (all from real code):
| Gate | Threshold | Source |
|---|---|---|
| Min trades/instrument (HARD) | 10 | `config_validator.py:91` |
| Max drawdown/instrument (HARD) | 35% | `config_validator.py:92` |
| Min fitness score (HARD) | 0.15 | `config_validator.py:95` |
| Min win rate (SOFT) | 35% | `config_validator.py:93` |
| Min expectancy (SOFT) | −0.5R | `config_validator.py:94` |
| Max cross-instrument score std_dev (SOFT) | 0.3 | `config_validator.py:96` |
| APPROVE gate | `decision == "APPROVE"` | `promotion_manager.py:151` |
| Shadow sample size | ≥ 30 trades | `shadow_promotion_gate.py:217` |
| Shadow performance | `shadow_pnl > baseline_pnl` | `shadow_promotion_gate.py:228` |

Plus a **research-loop acceptance rubric** (NEW — does not exist today): turn Claude's prose verdicts ("interesting / promising / dead end / noise") into numbers. Proposed: a sweep result is *actionable* only if it beats baseline PF by a margin AND clears a minimum-N significance floor (directly addresses the N=5 noise failure in the Phase-2b memory). Mark this as the one genuinely missing acceptance artifact.

### Precondition 2 — Kill / runtime-risk rubric (frozen, cite code)
| Limit | Threshold | Source |
|---|---|---|
| Max daily loss (kill switch) | 3.0% | `ultron_risk_gate.py:280` |
| Max portfolio risk | 5.0% | `ultron_risk_gate.py:305` |
| Max trades/day | 10 | `ultron_risk_gate.py:275` |
| Min R:R ratio | 1.5 | `ultron_risk_gate.py:243` |
| Max per-trade risk | 1.0% | `ultron_risk_gate.py:301` |

Plus **initiative kill conditions** = the Funding Ledger `Reopen Conditions` (current-findings.md): KILLED = Liquidity V2 / TradeNet V2 / Probability Surface V2; FROZEN = BitNet V2. Rule: the agent may **never** silently revive a KILLED/FROZEN initiative (CLAUDE.md §6.2).

### Precondition 3 — Escalation rubric (frozen, NEW)
Hard machine rules for when the agent must stop and hand to the human (today this is Claude's judgment). Escalate when: a goal.md invariant would be violated; a KILLED/FROZEN reopen condition triggers; UltronRiskGate kill switch fires; a result is statistically ambiguous (fails the Precondition-1 significance floor); or a promotion would proceed on backtest-only evidence while **F-010 is OPEN**.

### Precondition 4 — F-006 enforced (safety blocker)
Done-criteria: `config_integrity.py` (`validation_summary_is_fresh` / `active_version_is_governed`) is called on a **runtime path** (backtest_v2 / live_engine_hook / promotion_manager), not just the cutover CLI. Today its only caller is the one-off cutover script — an autonomous agent through an unwired gate is the single highest-risk failure. This precondition *names* the work; the wiring is a downstream code task, not part of this doc.

### Precondition 5 — F-010 resolved (safety blocker)
Done-criteria: live (or live-equivalent) PnL verified through ExecutionPlannerV1_2 + UltronRiskGate, which are live-only and absent from the backtest spine that produced the headline ROI. Until closed, the agent is **forbidden from autonomous promotion** (enforced via Precondition 3 escalation).

---

## Doc structure

`docs/architecture/autonomy-preconditions.md`:
1. **Context / thesis** — autonomy is not the next bottleneck; the objective function + rules are. (1 para, cite the user's "faster mistakes" framing.)
2. **The preconditions checklist** — six `[ ]` items up top for at-a-glance status.
3. **One section per precondition** (0–5) with frozen definition + done-criteria + code citations (`path:line · Symbol` per CLAUDE.md §6.3).
4. **Sequencing** — Tier 0 (F-006, F-010) → Tier 1 (objective + decision policy) → Tier 2 (acceptance rubric) → Tier 3 (run ledger). State: only after all six are `[x]` does autonomy-layer design begin.
5. **What this doc is NOT** — not the autonomy architecture; agent_state.json / decision_policy.json / run_ledger.jsonl come *after*.

---

## Discoverability hooks (consistent with the prior catalog lesson)

- `README.md` Tier 3 table — add a row for `autonomy-preconditions.md`.
- `CLAUDE.md` §2 companion-docs table — add a row.
- `docs/architecture/roadmap.md` — add a note that autonomy is gated behind this checklist (read-only confirm it fits a track; if a clean row exists, add it).

---

## Files Modified

| File | Change |
|---|---|
| `docs/architecture/autonomy-preconditions.md` | **NEW** — the frozen six-precondition doc |
| `README.md` | +1 Tier 3 row |
| `CLAUDE.md` | +1 companion-docs row |
| `docs/architecture/roadmap.md` | +1 note/row gating autonomy behind the checklist |

No code changes. F-006/F-010 wiring and the autonomy layer itself are explicitly out of scope — this doc defines the contract they must satisfy.

---

## Verification

1. Read `autonomy-preconditions.md` — confirm all six sections present, each with a done-criteria checkbox, and that every cited threshold matches the code (`config_validator.py:91/92/95`, `ultron_risk_gate.py:280/305/275/243/301`, `shadow_promotion_gate.py:217/228`, `promotion_manager.py:151`).
2. Confirm the objective-function section states BOTH the goal.md invariant hierarchy (hard constraint) AND the selection+throughput economic objective (F-001/F-002/F-003).
3. Confirm F-006 and F-010 are framed as Tier-0 blockers with explicit done-criteria, and that autonomous promotion is forbidden while F-010 is OPEN.
4. Confirm README + CLAUDE.md + roadmap point to the new doc.
5. Doc-only — run `pytest tests/test_doc_citations.py` to confirm the new `path:line · Symbol` citations resolve.


================================================================================
SOURCE_FILE: docs/plans/with-the-docs-gathered-optimized-kettle.md
SOURCE_BYTES: 7995
PART: 9/10 FILE 3/6
================================================================================

# Pattern Timing Library — Measure-First (No New Model)

> Created: 2026-06-06 · Milestone: Trd-M6 on-ramp (measure-only) · Track: Trading-arch (research / Pipeline B)
> Verdict of the requested audit + the implementation plan + expected data coverage.

## Context (why this is being built)

The user reframed a fragile question ("predict how long a move lasts") into a robust one:
**"Historically, when this exact pattern appears, what happens next — and how fast?"** i.e. compute
empirical *conditional timing distributions* (`time_to_+0.25R / +0.5R / +1R / TP1 / TP2 / SL`) per
pattern cluster, then use them for ranking (throughput, F-003) and in-trade abnormality detection.

This is **exactly the repo's settled doctrine**: F-001 (intelligence is not the constraint — *consume
existing info*), F-002 (the edge is SELECTION), F-012 (sidecars unconsumed). It is also the missing
**empirical foundation for the parked Trd-M6** "dynamic invalidation exit" (roadmap §3) — Trd-M6 was
parked for lack of measured timing on a real sample; this produces precisely that, measure-only.

## Audit verdict: YES — computable today, no new model

A deterministic forward re-walk of candles between a trade's entry and its horizon recovers every
requested metric. All inputs already exist:

| Need | Where it lives | Status |
|---|---|---|
| entry / SL / TP1/TP2/TP3 prices | `TradeRecord` `entry_price_fill`,`sl_price`,`tp1_price`,`tp2_price`,`tp3_price` (`src/runtime/backtest_v2.py:225-231`) | ✅ persisted |
| direction, entry/exit candle idx + ts | `direction`,`candle_open`,`candle_close`,`opened_at`,`closed_at` (`backtest_v2.py:223,234-237`) | ✅ |
| outcome / R | `exit_reason`,`pnl_rr_net` (`backtest_v2.py:233,242`); **R = \|entry_price_fill − sl_price\|** | ✅ derivable |
| candle stream (forward walk) | `CandleLoader.stream()` (`backtest_v2.py:665-691`), M15 CSVs in `data/` | ✅ deterministic, no-lookahead |
| grouping keys | `session`,`bitnet_score_at_entry`,`pattern_hash`(regime embedded),`features`,`crt_path` (`backtest_v2.py:254,276,286,259,285`) | ✅ |

**What is ABSENT** (and why it does NOT block us): MFE/MAE and intermediate level-hit candle indices
are never stored (executor `update_trade` tests TP/SL per close only, `crt_engine_v2.py:2008-2101`).
The re-walk **computes them as a side-effect** — so we get them for free without touching the engine.

**Why no-lookahead is not violated:** we measure the *actual realized path of an already-closed
trade*. Nothing feeds back into a live decision in Phase 1. (Live consumption is gated to Phase 2.)

## Phase 1 — Timing reconstruction + pattern library (measure-only, additive)

Pipeline-B research artifact. **Zero engine change, zero live change, weight 0.0.** Mirrors the
`probability-surface-advisory` measure-first precedent.

**1a. Timing reconstructor** — new module `src/replay/timing_reconstructor.py` (replay-adjacent;
production logic stays out of `scripts/` per CLAUDE.md §3.3). Pure function:
`reconstruct_timing(record, candles) -> dict`. Given a trade/opportunity (entry price, SL, direction,
entry timestamp) and the candle slice forward to a fixed horizon, walk candle-by-candle and record
the **first candle index** where `high`(long)/`low`(short) crosses each level
`entry ± {0.25,0.5,1.0}·R`, `TP1`, `TP2`, plus first SL touch; also track running MFE/MAE. Emit
`{time_to_025R, time_to_05R, time_to_1R, time_to_tp1, time_to_tp2, time_to_sl, mfe_R, mae_R,
bars_to_first_favorable}` in candle counts (×15min = minutes). Same-candle TP-vs-SL ambiguity →
**conservative rule (assume adverse first)**, matching backtest convention. Reuse `CandleLoader` and
`Direction` enum; do not re-implement candle parsing.

**1b. Aggregator + library** — new `scripts/analysis/build_pattern_library.py` (thin CLI wrapper).
Read historical trades (`logs/fusion_trades.jsonl` entry/exit pairs + backtest CSV), call 1a per
trade, group by composite key `(instrument, session, bitnet_bucket, pattern_hash)` with coarser
fallback keys for thin cells, and emit per-cluster distributions (N, win-rate, expectancy, median +
p10/p50/p90 of each `time_to_*`, MFE/MAE, and the **conditional** "if no +0.25R by candle k, win-rate
→ X"). Output `results/analysis/pattern_library_<instrument>.json`. Bitnet buckets via simple
discretization of the persisted `bitnet_score_at_entry`.

**1c. Validation report** answering the user's open questions (`docs/analysis/pattern-timing-<date>.md`):
Do CRT winners move fast? Does time-to-first-move differ by session/regime/instrument/bitnet bucket?
Is timing stable enough to rank on? Tests: `tests/replay/test_timing_reconstructor.py` (synthetic
candle paths with known crossings; conservative-rule + no-lookahead assertions).

## Phase 2 — Consume (GATED on Phase-1 showing stable, discriminating timing)

Only if 1c shows timing separates winners/losers and is stable OOS. Two consumption points, both
already-existing boundaries (no new spine), each shipped measure-only first:
- **Ranking signal** for the orphaned scanner/ranker path (F-013, `src/scanner/*`) — "fastest expected
  payoff / highest expectancy" ranking → directly serves the throughput goal (F-003).
- **In-trade abnormality / dynamic-invalidation exit** — the Trd-M6 surface (roadmap §3): "no +0.25R
  by the cluster's p90 ⇒ deteriorating ⇒ exit/scale." Replaces/augments the static bracket.

## Expected data coverage (the honest caveats — nothing hidden)

- **Executed trades are FEW** — BNBUSDT ~15→37 after gates (F-003). Per-cluster cells will be too
  thin for the 420–1000 the framing imagines; whole-population timing is fine, fine-grained clusters
  are not — from executed trades alone.
- **The real substrate is the OPPORTUNITY/SCANNER dataset**, not gated trades. Timing reconstruction
  needs only entry price + SL + direction + timestamp + candle stream — so it runs on **every detected
  RETEST/EXECUTION candidate**, decoupling sample size from the throughput gate. `ReplayMemoryEngine`
  already loads an `opportunities_dir`. **One open data question to confirm in 1a:** do scanner/
  opportunity records carry (or let us derive via ExecutionPlanner) entry+SL+direction? If yes, N
  jumps from tens to hundreds+. This is the single most important coverage lever.
- **Resolution = 1 candle (15 min)**; intra-candle ordering is unknown (standard backtest limit) →
  timing is ±1 candle and same-candle SL/TP uses the conservative rule. State this in 1c.
- **Grouping keys ready now:** instrument, session, bitnet bucket, pattern_hash (regime embedded),
  features. Zone_id and discrete regime are reconstructable post-hoc from the stored `features` dict
  (zone via `ReplayMemoryEngine._assign_cluster`, regime via `RegimeClassifier`) — Phase-1 optional.

## Verification

- `pytest tests/replay/test_timing_reconstructor.py` — synthetic candle paths with known first-crossings;
  conservative same-candle rule; determinism (same inputs → same timing); no-lookahead.
- Run `python scripts/analysis/build_pattern_library.py --instrument BNBUSDT --data-dir data/` →
  inspect `results/analysis/pattern_library_BNBUSDT.json` + the 1c report. Sanity: median
  `time_to_first_favorable` is small for winners, large/absent for losers (the testable hypothesis).
- Confirm zero diff to the live/backtest decision spine (measure-only): no change to `engine_runner`,
  `fusion_engine`, `decision_engine`, `execution_planner`, `ultron_risk_gate`.

## Out of scope / do-not

- No timing-*prediction* model (the user's own conclusion; <10% value per their estimate, and would
  reopen a KILLED-class "new intelligence" path against F-001). Distributions only.
- No live consumption until Phase-1 evidence clears (advisory-isolation + measure-first doctrine).
- Do not store MFE/MAE by mutating the live `Trade`/executor in Phase 1 — the re-walk yields them
  offline; live instrumentation is a separate, later decision if Phase 2 needs it online.


================================================================================
SOURCE_FILE: docs/plans/yes-after-inspecting-the-proud-summit.md
SOURCE_BYTES: 8463
PART: 9/10 FILE 4/6
================================================================================

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


================================================================================
SOURCE_FILE: docs/plans/yes-based-on-the-eventual-sunrise.md
SOURCE_BYTES: 7072
PART: 9/10 FILE 5/6
================================================================================

# Plan: Reconcile lineage onto v1 canonical + enable rich sections (Option B)

> Created: 2026-06-02 · Updated: 2026-06-02 · Milestone: Production-governance integrity + capability re-activation (P1)
> Decisions: **v1 rich-section lineage = canonical**; **keep validated permissive params + BNB/SOL session overrides**;
> **enable ALL rich sections.** Promotions stop at validated-ready (operator flips `ACTIVE_VERSION`).

## Context — why

The active config (`v2_multi_2026_04 - deepdeektry`) is a **governance bypass**: never promoted (0 `promotion_log` entries; git *"stable before rename"*), hand-edited permissive params (`0.8/0.3/0.6`), and a **stale `validation_summary`** describing the 2026-05-06 governed config (`0.2/0.65/1.0`, score 0.5966) — the integrity hash passes because it only hashes params↔params, so the desync is invisible. It also **omits six engine sections** v1 carries; `get_prod_section` *raises* on an absent section ([production_config.py:336-360](src/config_layer/production_config.py)), so those subsystems are off today.

Chosen direction: adopt **v1_multi_2026_03's full-section lineage as canonical**, carry the **validated permissive params + session overrides** (preserve throughput), and **enable all of v1's rich sections** — turning built-but-dormant intelligence on (the recurring evidence-map theme), under governance.

## What "enable all rich sections" actually does (precise — set expectations)

| Section | Effect when enabled | Decision impact | Action |
|---|---|---|---|
| **strategy_orchestrator** | 5th fusion input `weight_strategy_consensus` >0 (regime profiles 0.10–0.30); runs in **backtest + live** ([backtest_v2.py:1508](src/runtime/backtest_v2.py), [fusion_engine.py:156-158,378](src/core/fusion_engine.py)) | **REAL — changes decisions** | Validate + **regression-measure**; this is the main risk |
| **cognitive_layer** | engine_runner post-decision fire-and-forget emit → ReplayMemory/MarketState/HMF run as **telemetry** | None (sidecar, determinism-safe) | Enable; confirm off the deterministic path |
| **replay_memory** | feeds the cognitive sidecar (now with the 4 repaired per-instrument registries) | None until #6 deterministic wiring | Enable as telemetry; decision-influence stays in the #6 sub-plan |
| **drift_governance** | `replay_drift_governor` — replay package only, **not in spine** | None (won't gate trades) | Enable; note drift→trade-gating is the separate drift→action work |
| **market_state_cluster** | cognitive sidecar prior | None (sidecar) | Enable as telemetry |
| **tradenet_meta** | fusion neural slot is a **stub** ([fusion_engine.py:8](src/core/fusion_engine.py)) | None — **inert** | Enable config; flag that TradeNet is NOT plugged into fusion (separate work) |

Net behavior change = **strategy_orchestrator weight>0** (decisions) + sidecars running (telemetry). The other enables are inert/sidecar today — enabling them is honest config completeness, not new decision power.

## Plan

### B1 — Build the governed canonical candidate `v3_multi_2026_06`
- **Structural base = v1** (all engine sections). **Overlay:** permissive params (`0.8/0.3/0.6`), `retest_atr_depth_fraction=0.5`; `engine_runner.allowed_sessions_overrides` for BNBUSDT (`+ASIA +OFF_SESSION`) and SOLUSDT (validated in #2/#3).
- **Enable flags ON** for the six rich sections. For `strategy_consensus`, adopt v1's intended fusion weights (regime profiles / `weight_strategy_consensus`) — record the exact weight chosen.
- Fresh metadata: clean version key, `created_at`/`promoted_at`, and a **`validation_summary` regenerated from this candidate's own validation** (no stale copy).

### B2 — Validate + regression-measure (the gate)
- Run the override-aware `ConfigValidator.validate` across the production instrument set → require `APPROVE`.
- **Regression report (decision-change is expected here):** per-instrument trades/PF/DD/ROI of `v3` vs current deepdeektry, isolating the **orchestrator-on delta** (run orchestrator weight 0 vs intended weight). Surface the delta; if the orchestrator degrades an instrument, flag it rather than silently shipping.
- **Re-baseline note:** the prior ROI/session-sweep/OOS baselines were measured *without* the orchestrator — they must be **re-measured** on `v3` (the old numbers no longer describe production).

### B3 — Determinism / invariant safety
- Confirm `cognitive_layer`/`drift_governance`/`market_state` run **off the deterministic decision path** (engine_runner emit is post-decision fire-and-forget) → invariant #1 holds. `strategy_orchestrator` is deterministic (S1–S10 over the candle stream, seeded).
- Confirm invariant #2 (four engines) intact — orchestrator is a *5th* additive input, never replaces an engine; absent ⇒ weight 0, not partial fusion.

### B4 — Governance hardening (prevent recurrence)
- **`_load_full_base_config`** ([promotion_manager.py:451,466](src/governance/promotion_manager.py)): prefer the **current ACTIVE governed config** as merge base (v1 is correct *now* under Option B, but hardcoding it is the foot-gun); log the base used.
- **Two guard tests** (`tests/`): (a) **validation-freshness** — fail if `validation_summary` doesn't correspond to `params`; (b) **governed-active** — assert `ACTIVE_VERSION` has a `PROMOTED` entry in `promotion_log.jsonl`. Both should fail on the *current* deepdeektry and pass on `v3`.
- **Naming hygiene:** `ACTIVE_VERSION` must be a clean key (no spaces / ad-hoc suffixes).

### B5 — Stage (no live flip)
- Write `v3_multi_2026_06.json` + `promotion_log` PROMOTED entry. **Operator flips `ACTIVE_VERSION`** after reviewing the regression report (consistent with the prior boundary).

## Critical files
- [`src/governance/promotion_manager.py`](src/governance/promotion_manager.py) — base selection, write/log, ACTIVE flip.
- [`src/config_layer/production_config.py`](src/config_layer/production_config.py) — hash gap, `get_prod_section`, ACTIVE resolution.
- [`src/core/fusion_engine.py`](src/core/fusion_engine.py) — `weight_strategy_consensus` / regime profiles (orchestrator enable).
- [`configs/production/v1_multi_2026_03.json`](configs/production/v1_multi_2026_03.json) (structural base) → new `configs/production/v3_multi_2026_06.json`; `ACTIVE_VERSION`, `promotion_log.jsonl`.

## Verification
- `ConfigValidator` → `APPROVE` for `v3` with a **fresh** matching `validation_summary`.
- Regression report produced (v3 vs deepdeektry, orchestrator-on delta isolated); behavior change understood and accepted, not silent.
- New guard tests fail on deepdeektry, pass on `v3`; `load_version(v3)` clean.
- Full `pytest -q` green; determinism unaffected on the spine; `_load_full_base_config` logs its base.
- `ACTIVE_VERSION` unchanged until operator flip. SESSION LOG (§6) + topic sync (§6.1).

## Out of scope (separate, flagged)
- Flipping `ACTIVE_VERSION` (operator). ReplayMemory→decision wiring (#6 deterministic sub-plan). TradeNet→fusion (un-stub). Drift→trade-gating (drift→action). Re-tuning params.


================================================================================
SOURCE_FILE: docs/plans/yes-reverse-order-indexed-cookie.md
SOURCE_BYTES: 20458
PART: 9/10 FILE 6/6
================================================================================

> Created: 2026-05-22 · Updated: 2026-05-22 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# ROI-First Refinement: Phases P6.1 → P6.4 (Gaussian → Regime → TradeNet → Joint, plus ZoneGate / RR / BitNet)

## Context

Current bottleneck on ROI is **calibration + routing quality**, not raw model capacity. Gaussian is the active live RR/expectancy path; downstream engines (TradeNet, BitNet) inherit Gaussian's label noise. So we refine **in dependency order — cleaner labels first, downstream models second** — instead of the previous parallel/independent refinement of Gaussian and TradeNet.

Order: Gaussian (P6.1) → Regime-aware Gaussian (P6.2) → TradeNet 3-head (P6.3) → Joint optimizer (P6.4), with ZoneGate + RR-engine cleanup running alongside P6.1 and BitNet adaptation held until P6.1–P6.3 stabilize.

Targets:
- `corr_mean > 0.35`, `corr_std < 0.05`, `cal_error < 0.08` (Gaussian)
- `auc_tp2 > 0.65`, `survive_be > 0.70` (TradeNet)
- +10–25% expectancy stability (regime split)

---

## Reconnaissance Summary (what already exists — reuse, don't reinvent)

| Layer | Status | Key files |
|-------|--------|-----------|
| **Gaussian scorer** | Live; `phase5_calibration` section exists in prod config (`cv_n_folds=2`, `max_cal_error=0.25`) | [src/config_layer/crt_gaussian_scorer.py](src/config_layer/crt_gaussian_scorer.py), [src/training/evaluator.py](src/training/evaluator.py) |
| **RR class weights** | **Hardcoded** `[0.0,0.5,1.5,2.5]` | [src/training/trainer.py:43](src/training/trainer.py:43) |
| **Feature schema** | 38-dim (v3.0), v2.0=35 sentinel preserved | [src/features/feature_schema.py:44](src/features/feature_schema.py:44) |
| **Regime classifier** | 4 regimes (TRENDING / RANGING / HIGH_VOLATILITY / UNKNOWN); 5-bar cooldown; exposed as feature idx 30 | [src/regime/regime_classifier.py:25](src/regime/regime_classifier.py:25) |
| **Regime-aware fusion** | `FusionConfig.regime_fusion_weights` already wired; `FusionEngine.compute(regime=...)` already routes weights | [src/core/fusion_engine.py:164](src/core/fusion_engine.py:164), [src/core/engine_runner.py:665](src/core/engine_runner.py:665) |
| **TradeNet v2** | **Already 3-head** (`p_tp1`, `p_tp2`, `p_survives_be`); `--shadow` flag exists; weights `(0.4,0.4,0.2)` hardcoded at line 59 | [scripts/training/train_trade_net_v2.py:59](scripts/training/train_trade_net_v2.py:59), [scripts/training/train_trade_net_v2.py:215](scripts/training/train_trade_net_v2.py:215) |
| **ZoneGate** | K-means trained clusters; per-instrument registry; multiple soft-score / cluster constants hardcoded in engine | [src/engines/zone_gate_engine.py:86](src/engines/zone_gate_engine.py:86), [scripts/analysis/zone_registry_builder.py](scripts/analysis/zone_registry_builder.py) |
| **RR engine (live)** | Candle-polarity index (NOT forward RR); 4 hyperparams already externalized | [src/engines/rr_engine.py:37](src/engines/rr_engine.py:37), `rr_model` config section |
| **BitNet** | Fail-closed schema; per-regime thresholds in `bitnet_thresholds.json` | [src/bitnet/bitnet_runner.py:40](src/bitnet/bitnet_runner.py:40) |
| **Promotion gate** | `ConfigValidator.validate()` w/ hard+soft gates; `score_threshold=0.15`, `max_drawdown_pct=0.35` | [src/config_layer/config_validator.py:287](src/config_layer/config_validator.py:287), [src/governance/promotion_manager.py:97](src/governance/promotion_manager.py:97) |
| **Registries** | All support `instrument` + `run_id` fields → no schema change needed for per-(instrument,regime) entries | `models/{gaussian,rr,tradenet,zone_gate}_registry.json` |

---

## Phase P6.1 — Gaussian refinement (PRIMARY, ROI gate)

**Goal:** raise `corr_mean > 0.35`, drop `corr_std < 0.05`, drop `cal_error < 0.08`.

### 1.1 Externalize hardcoded knobs
- [src/training/trainer.py:43](src/training/trainer.py:43) `_RR_WEIGHTS = [0.0, 0.5, 1.5, 2.5]` → read from `phase5_calibration.rr_class_weights`. Accept either:
  - explicit list (e.g., `[0.0, 0.5, 1.5, 2.5]`), or
  - sentinel `"auto"` → compute per-run from observed `pnl_rr_net` quantiles (25/50/75th percentile boundaries; clamp class-0 anchor at 0.0).
- Add `phase5_calibration.train_ratio` (default 0.70) — replaces implicit complement of `val_ratio`. Allowed sweep: 0.60–0.85.
- Add `phase5_calibration.variance_floor` (default 1e-4) — minimum per-class variance to prevent overconfident calibration when a class has <50 samples.
- Add `phase5_calibration.calibration_threshold` (default 0.50, today inside `gaussian_scorer.execute_p`) — promote to optimizer-visible knob so the sweep can co-tune execute_p with class weights.
- Bump `phase5_calibration.cv_n_folds` 2 → 5 (config-only change; no code change needed).
- Flip `phase5_calibration.require_cv_stable` false → true once corr_std target is met.

### 1.2 Feature pruning (38 → ~28)
- Add `phase5_calibration.feature_subset` (default `null` = full 38). When provided, [src/features/dataset_builder.py](src/features/dataset_builder.py) `extract_feature_vector` returns the indexed subset.
- Prune candidates determined post-hoc from a single Gaussian fit's feature-correlation matrix; never edit `CANONICAL_FEATURES` (would invalidate baseline + every registered model).
- Schema-hash impact: subset is captured *per registered model* in registry `feature_schema` field — no global schema-hash invalidation.

### 1.3 Tighten promotion gate
- In `configs/production/v1_multi_2026_03.json` `config_validator` section: drop `max_cal_error` 0.25 → 0.08, add `min_corr_mean` 0.35, `max_corr_std` 0.05.
- Mirror gates in `ConfigValidator._fitness_score()` so promotion *fails* when calibration regresses, not just warns.

### 1.4 Tuner sweep harness
- Extend [src/training/trainer.py](src/training/trainer.py) sweep loop to read `phase5_calibration.sweep` block (already adjacent to existing tuner config). Sweep axes: `train_ratio`, `rr_class_weights` mode (explicit vs auto), `variance_floor`, `calibration_threshold`, `feature_subset`. Grid is bounded — keep under 36 combos per instrument per run.

### 1.5 Files to modify
- [src/training/trainer.py](src/training/trainer.py) — externalize `_RR_WEIGHTS`, add sweep loop entry
- [src/training/evaluator.py](src/training/evaluator.py) — emit `corr_std` alongside `corr_mean`
- [scripts/training/phase5_calibration.py](scripts/training/phase5_calibration.py) — wire `feature_subset` + `variance_floor`
- [src/config_layer/config_validator.py](src/config_layer/config_validator.py) — new hard gates
- [configs/production/v1_multi_2026_03.json](configs/production/v1_multi_2026_03.json) — `phase5_calibration.*` keys
- Re-hash config: `python scripts/maintenance/_compute_hash.py`

---

## Phase P6.2 — Regime-aware Gaussian (per (instrument, regime) entries)

**Goal:** +10–25% expectancy stability by training a Gaussian per regime, dispatched at inference using existing `RegimeClassifier` output.

### 2.1 Registry layout (no schema change)
Reuse existing `instrument` field; add a `regime` field as separate column. Naming convention:

```
gaussian_EURUSD_TRENDING
gaussian_EURUSD_RANGING
gaussian_EURUSD_HIGH_VOLATILITY
gaussian_EURUSD_UNKNOWN   # always falls back to RANGING per RegimeClassifier
```

Each entry is **independently promotable** with its own `ValidationReport`. Rollback is per-(instrument, regime).

### 2.2 Training partition
- Extend [scripts/training/phase5_calibration.py](scripts/training/phase5_calibration.py) to:
  - Group historical opportunities by regime (regime is already in `CANONICAL_FEATURES` idx 30, so it's already in opportunity logs).
  - Skip any regime bucket with fewer samples than `phase5_calibration.min_samples_per_regime` (default 300).
  - Train one Gaussian per (instrument, regime), reusing the P6.1 sweep harness.
- Each model writes its own envelope; `models/gaussian_registry.json` gets one entry per (instrument, regime).

### 2.3 Inference dispatch
- [src/engines/heuristic_gaussian_engine.py](src/engines/heuristic_gaussian_engine.py) `GaussianRegistry`:
  - Currently picks model by `instrument`. Extend to pick by `(instrument, regime)`, falling back to `(instrument, "*")` then global.
- Caller: `EngineRunner` already detects `current_regime` at [src/core/engine_runner.py:665](src/core/engine_runner.py:665) before fusion. Pass it down into the Gaussian engine call (currently passes only feature vector) — a small signature change.

### 2.4 Promotion
- Per-regime promotion runs the same `ConfigValidator` gates, but on the regime-filtered trade subset (not on global metrics).
- Add `governance.regime_promotion_policy`: `"all_or_nothing"` vs `"per_regime"` (default `per_regime` — atomic per regime, mixed live state is OK because regime is mutually exclusive at any given bar).

### 2.5 Files to modify
- [scripts/training/phase5_calibration.py](scripts/training/phase5_calibration.py) — regime partitioning
- [src/engines/heuristic_gaussian_engine.py](src/engines/heuristic_gaussian_engine.py) — regime-aware lookup
- [src/core/engine_runner.py](src/core/engine_runner.py) — pass `regime` into Gaussian engine call
- [src/governance/promotion_manager.py](src/governance/promotion_manager.py) — per-regime promotion path
- `configs/production/v1_multi_2026_03.json` — `phase5_calibration.min_samples_per_regime`, `governance.regime_promotion_policy`

---

## Phase P6.2b — ZoneGate refinement (parallel with P6.1/P6.2)

**Goal:** externalize hardcoded knobs and add per-instrument re-training cadence.

### Hardcoded → config
- [src/engines/zone_gate_engine.py:88-90](src/engines/zone_gate_engine.py:88) soft-score weights `(0.5, 0.3, 0.2)` → `engine_runner.zone_gate.soft_weights`.
- [src/engines/zone_gate_engine.py:135](src/engines/zone_gate_engine.py:135) cluster spread threshold `0.15` → `engine_runner.zone_gate.cluster_spread_max`.
- [src/engines/zone_gate_engine.py:129](src/engines/zone_gate_engine.py:129) min-neighbours `2` → `engine_runner.zone_gate.min_neighbors`.
- [scripts/analysis/zone_registry_builder.py:53](scripts/analysis/zone_registry_builder.py:53) min cluster size `10` and [scripts/analysis/zone_registry_builder.py:63](scripts/analysis/zone_registry_builder.py:63) `min_score=0.5` → `zone_registry_builder.*`.

### Regime split for zones
- Same per-(instrument, regime) registry layout as Gaussian. Zones in TRENDING differ structurally from RANGING zones; existing global zones smear the boundary.
- Reuse [scripts/analysis/zone_registry_builder.py](scripts/analysis/zone_registry_builder.py) — group profitable trades by `volatility_regime` before KMeans clustering.

### Files to modify
- [src/engines/zone_gate_engine.py](src/engines/zone_gate_engine.py) — read soft-weights + spread from config
- [scripts/analysis/zone_registry_builder.py](scripts/analysis/zone_registry_builder.py) — regime partitioning + config knobs
- `configs/production/v1_multi_2026_03.json` — new `zone_gate` + `zone_registry_builder` subsections

---

## Phase P6.2c — RR engine cleanup (parallel)

The semantic mismatch on `rr_engine.py` (candle polarity, not forward RR) is a known footgun. Resolve in this pass:
- Rename `RREngine` → `CandlePolarityEngine` *inside* the file with backward-compat alias `RREngine = CandlePolarityEngine`.
- Add docstring stating it scores commitment, not expected return. Update `EXPECTED_ENGINES` comment only — do **not** change the registry key `"rr"` (that would invalidate every existing fused result).
- Externalize the 4 already-config-driven knobs (`ridge_alpha`, `drift_threshold`, `confidence_bypass_threshold`, `min_samples`) under the same `phase5_calibration.sweep` so RR ridge regularization gets co-tuned with Gaussian.

### Files to modify
- [src/engines/rr_engine.py](src/engines/rr_engine.py) — docstring + alias (no behaviour change)
- [src/training/trainer.py](src/training/trainer.py) — include `rr_model.ridge_alpha` in sweep when present

---

## Phase P6.3 — TradeNet 3-head as profit miner (shadow only)

**Goal:** use [scripts/training/train_trade_net_v2.py](scripts/training/train_trade_net_v2.py) (already 3-head) as a downstream behaviour miner. Externalize the few remaining hardcoded knobs and backfill missing labels.

### 3.1 MFE backfill (prerequisite)
- New script `scripts/maintenance/backfill_mfe.py`: walks each closed opportunity, re-loads the candle window between `opened_at` and `closed_at`, computes `mfe = max((high-entry)/abs(entry-sl))` for longs (mirror for shorts), writes back to opportunity JSONL.
- Idempotent — skips records already containing `mfe`.
- Verify: post-backfill, `<5%` of closed opportunities should still emit `TRADENET_SURVIVES_BE_UNRESOLVED`.

### 3.2 Externalize head weights & training knobs
- [scripts/training/train_trade_net_v2.py:59](scripts/training/train_trade_net_v2.py:59) `COMPOSITE_WEIGHTS = (0.4, 0.4, 0.2)` → read from new config section `tradenet_v2`:
  ```json
  "tradenet_v2": {
    "head_weights": {"tp1": 0.5, "tp2": 0.5, "survives_be": 0.2},
    "hidden_dims": [32, 16],
    "dropout": 0.20,
    "min_samples": 500
  }
  ```
- Sweep ranges per user spec:
  - `hidden_dims`: `[32,16]`, `[64,32]`
  - `dropout`: 0.10–0.35 (step 0.05)
  - `tp1`/`tp2` heads: 0.4–0.6 (step 0.1)
  - `survives_be`: 0.1–0.3 (step 0.1)
  - `min_samples`: sweep 500 → 2000 (step 500) to find diminishing return knee

### 3.3 Shadow-only deployment
- TradeNet stays under `--shadow` until P6.1 + P6.2 metrics confirm clean upstream. Live promotion gated on:
  - `auc_p_tp1 > 0.65` AND `auc_p_tp2 > 0.65` AND `acc_survives_be > 0.70`
  - No regression vs current live model's `auc_p_tp1`
- Existing `--force-promote` flag stays as escape hatch.

### 3.4 Files to modify
- New: `scripts/maintenance/backfill_mfe.py`
- [scripts/training/train_trade_net_v2.py](scripts/training/train_trade_net_v2.py) — read `tradenet_v2.*` from config
- [configs/production/v1_multi_2026_03.json](configs/production/v1_multi_2026_03.json) — new `tradenet_v2` section, extend `config_validator` with TradeNet shadow gates

---

## Phase P6.3b — BitNet adaptation (HELD until P6.1–P6.3 stable)

BitNet's job is to **compress already-clean intelligence**, not absorb upstream noise. So:
- No architecture retraining in this pass.
- Adapt `bitnet_thresholds.json` per-regime thresholds **after** P6.2 lands: re-compute thresholds from the regime-split Gaussian's calibrated distributions instead of from the global mixed distribution.
- Tunable via `engine_runner.bitnet_main_threshold` per regime → new `engine_runner.bitnet_thresholds_per_regime` block.

### Files to modify
- [src/bitnet/bitnet_runner.py](src/bitnet/bitnet_runner.py) — read per-regime threshold (small change)
- `models/bitnet_thresholds.json` — populate regime-keyed thresholds from P6.2 outputs
- `configs/production/v1_multi_2026_03.json` — `engine_runner.bitnet_thresholds_per_regime`

---

## Phase P6.4 — Joint ROI optimizer

**Goal:** one multi-objective fitness function spanning all 4 (instrument, regime) Gaussian models + their downstream consumers.

### 4.1 New fitness formula
Extend [src/config_layer/config_validator.py](src/config_layer/config_validator.py) `_fitness_score()`:

```
ROI_fitness =
   0.35 * expectancy_rr_norm
 + 0.30 * profit_factor_norm
 + 0.20 * trade_count_norm
 - 0.15 * drawdown_norm
```

Weights become config-driven under `config_validator.roi_fitness_weights`. Old `fitness_weights` retained as fallback (`use_roi_fitness: true|false`).

### 4.2 Cross-regime stability term
Add penalty when expectancy variance across the 4 regime models exceeds `max_regime_expectancy_std` (default 0.15). Promotes consistent performance, not just a single hot regime.

### 4.3 Optimizer loop
- [src/training/trainer.py](src/training/trainer.py) gains a top-level `--joint-optimize` flag. When set, the trainer iterates over all (instrument, regime) tuples once per generation, computes the joint fitness above, and only commits the *whole bundle* if it beats current production.
- Reuses existing `ShadowPromotionGate` for the bundle-vs-prod backtest.

### 4.4 Files to modify
- [src/config_layer/config_validator.py](src/config_layer/config_validator.py) — `_fitness_score` ROI mode
- [src/training/trainer.py](src/training/trainer.py) — joint optimizer entry point
- [src/governance/promotion_manager.py](src/governance/promotion_manager.py) — bundled promotion path
- `configs/production/v1_multi_2026_03.json` — `config_validator.roi_fitness_weights`, `config_validator.max_regime_expectancy_std`

---

## Execution sequencing

```
P6.1 Gaussian externalize + sweep        ──┐
P6.2b ZoneGate externalize + regime split ──┼── parallel (independent file sets)
P6.2c RR engine docstring + sweep entry   ──┘
                  │
                  ▼  (gate: corr_mean>0.35, cal_error<0.08)
P6.2 Regime-aware Gaussian per (instrument, regime)
                  │
                  ▼  (gate: per-regime promotion passes)
P6.3 MFE backfill + TradeNet 3-head shadow sweep
                  │
                  ▼  (gate: auc_tp2>0.65, survive_be>0.70 in shadow)
P6.3b BitNet per-regime threshold refresh
                  │
                  ▼
P6.4 Joint ROI optimizer (bundled promotion)
```

**Do not start P6.2** until P6.1 corr_std target is met — regime splits *amplify* whatever noise the global model has.
**Do not promote TradeNet live** until P6.2 lands — TradeNet inherits Gaussian's label noise.
**Do not retrain BitNet** in this cycle.

---

## Verification

### After P6.1
- `python scripts/training/phase5_calibration.py --train --sweep` → produces sweep summary with `corr_mean / corr_std / cal_error` per combo.
- `python src/config_layer/config_validator.py validate-prod --data-dir data/` → must pass new tighter gates.
- `python src/runtime/baseline_capture.py --label phase6_1` → snapshot.

### After P6.2
- Inspect `models/gaussian_registry.json` for 4 entries per instrument (TRENDING/RANGING/HIGH_VOLATILITY/UNKNOWN).
- `python scripts/auto_train_from_opportunities.py --dry-run` → verify regime dispatch picks correct model per bar.
- Compare per-regime expectancy in backtest output (`BacktestMetrics.distribution["per_regime"]` — add if missing).

### After P6.3 (shadow)
- `python scripts/training/train_trade_net_v2.py --shadow --sweep` → sweep summary.
- Grep `logs/agent_audit.jsonl` for `TRADENET_SURVIVES_BE_UNRESOLVED` count before/after MFE backfill — should drop below 5%.

### After P6.4
- `python src/training/trainer.py --joint-optimize --data-dir data/` → bundle proposal.
- `python src/governance/promotion_manager.py promote --checkpoint results/tuner/checkpoint_joint.json --version v3_<label>_<YYYY_MM> --data-dir data/` → atomic bundle promotion.
- Verify `configs/promotion_log.jsonl` contains a single `PROMOTED` line covering all (instrument, regime) entries.

### Regression suite (every phase)
- `python -m pytest tests/` — full suite must remain green at each phase boundary.
- `python scripts/analysis/compress_logs_for_llm.py --logs logs/**/*.jsonl` — for diff-able training/promotion telemetry.

---

## Out of scope (explicit non-goals)

- No change to `CANONICAL_FEATURES` (would invalidate baseline + every registered model).
- No BitNet architecture retraining.
- No new REST/API surface — control plane stays localhost stdlib.
- No replacement of `rr_engine.py` semantics (only docstring + alias).
- No ORM, no DB — registries remain JSON.

---

## Risk register

| Risk | Mitigation |
|------|-----------|
| Sweep grid explodes combinatorially | Cap to ≤36 combos/instrument/run; tuner already uses `phase2_min_iter` floor. |
| Per-regime sample starvation | `min_samples_per_regime=300` floor; fall back to global Gaussian for that regime if unmet. |
| MFE backfill misreads candle history (lookahead) | Restrict candle window strictly to `[opened_at, closed_at]`; cross-check against existing `exit_reason`. |
| Joint optimizer regresses live ROI on bundle promotion | `ShadowPromotionGate` runs bundle vs prod first; rollback = restore archived configs + re-load. |
| Schema-hash invalidation from feature_subset | Subset is per-model registry field, not global schema mutation. Verified safe. |
| Regime classifier instability flapping models at runtime | Existing 5-bar cooldown already mitigates; verify before P6.2 ships. |
