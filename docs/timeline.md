# Timeline — Unified "What Changed When"

> The single chronological entry point for **every change/implementation from the start, differentiated
> by time**. One row per work-day, newest first, tying together the three record systems:
>
> | System | What it records | Authority |
> |---|---|---|
> | [`assistant_project.md`](../assistant_project.md) | append-only **SESSION LOG** — what was done, dated | **source of truth** for "what happened" |
> | [`docs/plans/readme.md`](plans/readme.md) | dated plans — what was *planned* (design records) | source of truth for "what was scoped" |
> | [`docs/current-findings.md`](current-findings.md) | validated conclusions `F-0xx` + Funding Ledger | source of truth for "what we now know" |
>
> **Dates:** each row's date is the SESSION LOG `Date:`; plan dates come from the plan's `> Created:`
> header, or file mtime where absent (`~` = inferred — `docs/plans/` is not git-tracked, so mtime is the
> best signal). Findings (`F-0xx`) are dated by their `Validated:` field. Git is deliberately **not** a
> source here (it lags the SESSION LOG and the plans aren't tracked). Keep this file fresh in the same
> turn you append a SESSION LOG entry (per `CLAUDE.md §6`).
>
> **See also:** [`knowledge-map.md`](knowledge-map.md) — how this timeline connects to the other record systems + traversal recipes.

## Eras (high-level arc)

1. **Foundation & enhancement** (2026-04-10 → 04-16) — ordered enhancements, JSON-as-single-source-of-truth, full pytest suite green; `ENHANCEMENT_IMPLEMENTATION_PLAN.md` phases.
2. **Agent + sprints + integration** (2026-04-17 → 05-02) — AI Automation Agent design, Sprints 1–7 (strategies, live hook, governance, Docker), unified execution spine, two-layer (runtime / research) migration.
3. **CRT optimization — Phases 0→6** (2026-05-12 → 05-30) — shadow displacement (`SHADOW_PENDING`), expansion TTL, shadow age-decay, ROI baseline + funnel diagnosis. (See MEMORY phase findings.)
4. **Governance + dual-track + Repository Truths** (2026-05-28 → 06-05) — architecture migration (Trd-M0..M6), idea-governance (Gov-M1/M2), topic-visibility layer, governed cutover to `v4_multi_2026_06`, Repository Truths (`F-001..F-012`) + Funding Ledger, economic-edge diagnosis, doc-alignment + citation-sync (this work).

---

## Dated log (newest first)

| Date | Track / Milestone | Headline (from SESSION LOG) | Plans / Findings |
| --- | --- | --- | --- |
| 2026-06-13 | Trd (Program 2 / E1, measure-only) | **Program 2 opened → Phase E1 trap-continuation asymmetry → FROZEN after one experiment.** PURE structural asymmetry (NO profitability): completed sweep→displacement→retest (BNBUSDT) vs 4 controls incl. **sweep-only D**, multi-horizon MFE/MAE + symmetric first-hit, permutation + OOS + **in-pipeline calibration**. VERDICT **INSUFFICIENT_POWER · POWER INADEQUATE**: test n=47, excursion_asym(h8)=−0.32 / first_hit_delta(L0.5)=−0.11 — **NEGATIVE and loses to ALL controls**; funnel sweep 4529 → disp 391 (8.6%) → retest 47 (**~1% completion**); calibration PASSED (instrument valid, so the result is trustworthy not broken). Per the pre-registered protocol only ASYMMETRY_SURVIVES advances → Program 2 FROZEN (no E2). Determinism byte-identical `AA188E1F`. | findings: **F-026**; ledger: **Program 2 FROZEN**; analysis: `structural-asymmetry-bnbusdt-2026-06-13.md`; core: `src/research/structural_asymmetry.py` |
| 2026-06-13 | Trd (research-program FREEZE) | **Program 1 (Next-Bar Directional Ontology, M15 crypto-majors, intrabar+12bps) — CLOSED / KILLED.** Four independent falsifications under one governing truth standard: entry-edge null (F-019), conditional-direction null (F-020), selection-skill null = incumbent session filter (F-021), exit/cost null = risk/cost lever not expectancy (F-025). Decisive **reality_gap +4.16R** → value is upstream/informational (gross E≈0, 90.55% plain_stop_loss), not exit geometry. Each branch had a decomposition guard that killed a false-positive headline (entropy→economics, selection→reject-reason, grid→ceiling/OOS/N); planted-edge tests make the nulls trustworthy; D4 not entered. **EXHAUSTED ≠ WRONG** — frontier (other target/horizon/asset/objective/labels) = a fresh **Program-2** decision, NOT a parameter pass. | findings: **F-019, F-020, F-021, F-025**; ledger: **Program 1 KILLED**; analysis: `program-1-closure-2026-06-13.md`, `qualify-majors-2026-06-12.md`, `conditional-entropy-majors-2026-06-12.md`, `selection-effect-crypto6-2026-06-13.md`, `exit-grid-crypto6-2026-06-13.md` |
| 2026-06-13 | Trd (cross-instrument anatomy) + Gov | **Cross-instrument anatomy (BNB/BTC/ETH/SOL)** — regenerated BTC/ETH/SOL opportunities (`opportunity_scanner.py`) + generalized the anatomy driver (`--instrument`, BNB byte-identical sha `f8bdabbe…`). ALL findings replicate near-identically: **F-022 repository-wide** (artifact self-consistency 0.36–0.37 on all four; MECHANISM = scanner's 0.5R **trailing stop** → not corruption, "trailing ground-truth ≠ governing fixed-stop"), **F-024 replicates** (within-trade peak losers p50=1 / winners p50=6 on all coins), and **cost-domination** (gross≈0 / net<0 every coin×horizon) **corroborates existing F-025** (exit-grid) — caught + corrected a Phase-2 F-025 id-collision (no new id). | findings: **F-022/F-024 Update (broaden+replicate); F-025 corroborated**; analysis: `cross-instrument-anatomy-2026-06-13.md`; substrates: `results/research/{btcusdt,ethusdt,solusdt}_trade_anatomy/` |
| 2026-06-13 | Trd (measure-only anatomy) + Gov | **BNBUSDT trade-anatomy substrate** — recovered-first study over `opportunities.jsonl` (139,942 detections) × M15 candles, reusing `forward_walk`/`horizon_excursion`. Key discovery = **artifact-integrity defect** (opportunities outcome/rr only 36.8% self-consistent → realized layer DERIVED via governing exit). Froze canonical `trade_dataset_BNBUSDT.csv` (sha256 `f8bdabbe…`, deterministic). De-censoring (PEAK_HORIZON=96) **corrected** the censored "winners peak ~22 bars/5.5h" → within-trade peak winners median 6 (~90m) / losers median 1. F-025 ("cost destroys neutrality") held as watch-only | findings: **F-022, F-023, F-024**; plan: `existing-data-sources-enumerated-feather`; analysis: `BNBUSDT_TRADE_ANATOMY_2026_06_13.md`; substrate: `results/research/bnbusdt_trade_anatomy/` |
| 2026-06-06 | Trd (Trd-M6 on-ramp, measure-only) | **Pattern Timing Library Phase 1 shipped + Phase-2 early-invalidation A/B run** — `time_to_+kR` distributions from existing opportunity data (no model); falsification + incremental-edge gates PASSED (within-cell 54/54 ETH+BNB → feature-orthogonal POST-entry signal); signal-level early-invalidation A/B Net RR +ve 4/4 & all K (ETH +301R…BTC +154R), winner-set avg RR preserved; offline executed-trade A/B (BNB N=35) confirmed mechanism+winners+net-positive but headline MaxDD FLAT → **FROZEN research-complete/production-pending** (no promote/live/spine change; un-freeze needs higher throughput per F-003); zero live-spine change. **+ F-003 throughput pivot:** Phase A funnel diag (DISP→EXPANSION 5% choke confirmed) → Phase B detection sweep (measure-only) **NEGATIVE** — relaxation not quality-preserving (BNB at ceiling ~35-44; SOL unprofitable) → cheap throughput EXHAUSTED → validate via cross-instrument pooling (F-015) | findings: **F-014, F-015**; ledger: Pattern Timing Library = FUNDED (frozen); plan: `with-the-docs-gathered-optimized-kettle`; analysis: `pattern-timing-2026-06-06.md`, `early-invalidation-ab-2026-06-06.md`, `early-invalidation-exectrade-ab-2026-06-06.md`, `funnel-diagnosis-2026-06-06.md`, `detection-sweep-2026-06-06.md` |
| 2026-06-05 | Gov (docs-alignment) | Config-driven `breakout_disp_threshold` (BNB=1.3) governed-not-promoted (execute≠promote); promotion machinery extended but HALTED on pre-existing defects; ODL-G3a/G3b fixes proven via scratch registry. **+ this work: CLAUDE.md doc↔code alignment, citation-sync mandate, plans index + timeline.** | plan: `lets-work-on-claude-goofy-scott` |
| 2026-06-04 | Trd (measure-first) + Gov | RR contract audit + R2 re-run; planner-rejection / UNKNOWN_INTENT / disp_strength sweeps (measure-only); 17-phase Architecture Truth Audit → remediation 8A (doc truth-sync) | plans: `system-mandate-…-tender-hoare` (KILLED), `bitnet-…-ritchie`, `context-current-tradenet-…-lemur` (KILLED) |
| 2026-06-03 | Gov + Trd | Independent architecture audit (8 deliverables); **governed cutover → `v4_multi_2026_06`**; selection-edge studies (decisive); Phase-0 economic-edge diagnosis **FAIL 0/4**; Repository Truths Layer v2 + Funding Ledger + Master Alpha Ledger; execution-planner / R2 live-path replay | findings: **F-001,F-002,F-004,F-005,F-006,F-010**; plans: `assume-…-naur` (KILLED), `i-remember-we-are-golden-yeti`, `open-defect-…-marble` (KILLED), `the-strongest-…-clarke`, `yes-after-…-summit` |
| 2026-06-02 | Gov + Trd | ReplayMemory schema-repair (monitoring-only); Trd-M6 stays-downstream + session override; BNBUSDT session promotion (V3); per-instrument OOS 4/4; backlog roadmap #1–#7; intelligence-artifact evidence map; P1 lineage reconciliation (Option B); architectural-evolution from 56 plans | findings: **F-007,F-008,F-009,F-012**; plans: `claude-go-thrugh-docs-…-finch`, `goal-produce-…-grove`, `probability-surface-advisory` (KILLED), `yes-based-…-sunrise` |
| 2026-06-01 | Gov-M2 + Trd-M3..M6 | Ship **M2 User Progress Registry**; agent-reference refresh (14→17 intent / 20→22 tool drift fix); `idea-governance-framework.md`; **topic-visibility layer + §6.1**; split Gov/Trd milestone tracks; agent-readable execution-memory layer; Trd-M3→M5 infra; session sweep + shadow A/B + OOS persistence (measure-only) | findings: **F-003,F-011**; plans: `one-remaining-gap-…-pixel` (M2), `refer-the-pure-docs-…-lagoon`, `frolicking-foraging-hearth`, `trd-m0-m5-…-bentley`, `trd-m6-…-pascal`, `this-is-a-valuable-pure-flurry` (M1, KILLED) |
| 2026-05-30 | Phase 6b (ROI) | Analyse `assistant_project.md` + user-intention trace; ROI Increase Plan (Phase 6b) implement + funnel-bridge fix; `training.md` + scanner→phase5→calibrated-backtest trace | plans: `analyse-assistant-project-…-flask`, `from-docs-gather-…-swan` |
| 2026-05-29 | M1/M2 + docs | M1 telemetry normalization; **Trigger Vocabulary** in CLAUDE.md; M2 event extraction; GOAL.md north-star; **semantic docs reorg (kebab-case)**; code-map generator; ROI Step (Phase 6) baseline | plans: `how-claude-is-refeering-…-waterfall`, `kind-dazzling-frost` |
| 2026-05-28 | Trd-M0 | Architecture migration M0 (event-driven, LLM-context-economy) + plan-persistence automation; Phase 3b gate + Phase 5 design; Phase 4b results + config update | plans: `claude-architecture-migration-…-wreath` (Trd-M0); see MEMORY phase3b/4b |
| 2026-05-27 | Phases 0–2b | Phase 4b shadow age-decay gate; Phase 0 telemetry; **Phase 1 SHADOW_PENDING** implemented; Phase 2b score-inversion diagnosis + expansion dwell histogram | see MEMORY phase0/1/2b |
| 2026-05-22 | P3/P4/P5 analysis | Execution-contract audit + intent attribution; P4 observability repair; regression-pack investigation | — |
| 2026-05-15 | UI + rename | React UI kits wired to `:8787`; Models/Backtests tabs; **semantic architecture rename (13 files)**; zone-gate + model-quality fixes | — |
| 2026-05-13 | Phase 2–3 (direction) | Registry cleanup + first promoted model; direction-mirroring fix threaded through backtest/engine-runner | plans: `regime-aware-fusion-…-river`, `start-with-regime-aware-fusion-…-waterfall` (≈) |
| 2026-05-12 | Two-layer migration | Two-Layer Architecture Migration (Pipeline A runtime + Pipeline B research) | — |
| 2026-05-02 | Integration | Unified Execution Spine (all 4 phases) | — |
| 2026-05-01 | Sprints 6–7 | Live Hook Integration (orchestrator + killswitch + Telegram + MT5); production governance + Docker + health checker | — |
| 2026-04-30 | Sprints 1–5 | Foundation layer; strategy wrappers (S1–S10); StrategyOrchestrator + FusionEngine; MonteCarlo + KillSwitch + UAT; RR data-integrity audit | — |
| 2026-04-29 | Governance | PromotionManager merge-into-base fix; `SIGNAL_FLOW.md` created | — |
| 2026-04-28 | Cleanup + map | Dead-code archive + Ultron wiring + FeatureStore boundary; `skip_features=True` in tuner workers; backtest perf plan; canonical naming | — |
| 2026-04-26 | Root-cause fixes | BacktestRunner missing `csv_path`; unified bridge live metrics; feature-zeroing root-cause + fix | — |
| 2026-04-25 | Test fix | `test_expansion_governance_bridge.py` patch-target fix | — |
| 2026-04-22 | Misc | Python file count | — |
| 2026-04-18 | Agent design | AI Automation Agent design doc (ChatOps overlay) + Jarvis structural review | plans (≈): `you-are-lead-runtime-…-snowglobe` |
| 2026-04-17 | Handover | Incorporate `Jarvis_CRT_Handover.docx` (Patch v3, BTCUSDT M15) | — |
| 2026-04-16 | Foundation | JSON-as-single-source-of-truth complete; full pytest green (427 passed) | — |
| 2026-04-10 → 04-12 | Phase 1–2 enhancements | `ENHANCEMENT_IMPLEMENTATION_PLAN.md` all phases; baseline + schema-gate; runtime-hook contract hardening; fusion path toggle + shadow rollout + telemetry | — |

---

_Earliest SESSION LOG entry: 2026-04-10. When the
exact plan/finding for a date is ambiguous, the SESSION LOG entry in `assistant_project.md` for
that date is authoritative. `≈` next to a plan = date inferred from file mtime (see plans index)._
