# 03 · Findings & Evidence

> **GENERATED — do not edit by hand.** Regenerate with `python scripts/context/build_context.py` (the `Compile` trigger).
>
> A *derived view*, not a source of truth (MULTI_LLM_PROTOCOL.md §2: Shared Context is never authoritative on conflict). Edit the source, then re-Compile.
>
> **Sources:** docs/current-findings.md, CLAUDE.md


## Repository Truths Index (thin)

### Repository Truths Index (thin, always-loaded)
Active conclusions — full record + evidence in [`docs/current-findings.md`](docs/current-findings.md),
which is **authoritative on conflict**. This table is enforced ↔ the living doc by
`tests/test_current_findings.py` (every non-terminal finding must appear here and vice-versa):

| F-id | Type | Conclusion | Conf |
|---|---|---|---|
| F-001 | ECON | Intelligence is NOT the binding constraint — governance / throughput / consumption are | Certain |
| F-002 | ECON | The edge is in the decision PROCESS (selection ≫ SL/TP), not a static feature→outcome map | Likely |
| F-004 | ARCH | BitNet is a LIVE hard-reject gate (score < 0.55) and the score IS persisted; only the *adaptive* threshold is dormant | Certain |
| F-005 | ARCH | TradeNet v2 is BUILT but unwired — the fusion neural slot is a permanent stub | Certain |
| F-006 | GOV | `config_integrity` is a REAL check but ORPHANED — it gates nothing at runtime | Certain |
| F-008 | RISK | Concept drift is DETECTED but NOT acted on (no block / size-down) | Certain |
| F-009 | GOV | Per-instrument doctrine validated; global / multi configs underperform | Likely |
| F-010 | RISK | Headline ROI is BACKTEST-only; live PnL (ExecutionPlanner + UltronRiskGate) UNVERIFIED *(OPEN)* | Likely |
| F-011 | ECON | OOS persistence is real but small; persistence ≠ discrimination *(DURABLE)* | Likely |
| F-012 | ARCH | ReplayMemory / CognitiveBus / Cluster / HMF are sidecar-only (zero spine consumption) | Certain |
| F-013 | ARCH | scan→allocate→ExecutionLoop + PortfolioAllocator BUILT but ORPHANED; live runs the single-candle spine | Certain |
| F-014 | ECON | Time-to-first-move is a real, feature-orthogonal POST-ENTRY discriminator; FROZEN pending throughput | Likely |
| F-015 | ECON | Detection-gate relaxation is NOT quality-preserving; cheap throughput is exhausted on BNB/SOL | Likely |
| F-016 | GOV | On `patch`, active config is `v2_multi_2026_04` (pre-TP3); v4 applies only to the TP3 code line — supersedes F-007 | Certain |
| F-017 | ECON | Session policy is NOT a promotable BNBUSDT lever under realistic exits + OOS — supersedes F-003's "proven lever" | Likely |
| F-018 | GOV | Active config (patch) lags HEAD code: required sections absent + knobs hardcoded → data-gate runs on defaults; concrete symptom of F-016 | Certain |
| F-019 | ECON | No existing hypothesis qualifies (M4) across crypto majors under intrabar+12bps; toy entries ≈ random, spine throughput-starved | Likely |
| F-020 | ECON | No candle-conditional directional pocket on crypto majors (session×vol×momentum, h≤20); entropy "significance" saturates at large N, economics finds 0 pockets — extends F-019 to the conditional level | Likely |
| F-021 | ECON | Spine RETEST selection = the (incumbent, F-017-null) SESSION filter; no score/zone skill under intrabar+12bps (ZONE 0 rejects, SCORE noise) — F-002 stale, selection-beyond-session falsified | Likely |
| F-022 | GOV | `opportunities.jsonl` is a DETECTION STREAM, not a trade ledger — outcome/rr only 36.8% self-consistent (SL_HIT on paths that never touch the stop); derive realized truth via governing exit. Frequency illusion: 139,942 detections ≠ trades (spine=13) | Certain |
| F-023 | ECON | Feature morphology separates SHAPE, not expectancy — KMeans k=4 distinct anatomy, all win≈0.34 / mean_R≈0; kills the "just cluster harder" class | Likely |
| F-024 | ECON | Timing asymmetry (de-censored): losers resolve ~immediately (within-trade peak median 1 bar), winners mature over ~90 min (median 6 / p90 18 bars) — NOT 5.5 h; exit-agnostic path peak is random-walk/uninformative. Descriptive, partly mechanical | Likely |
| F-025 | ECON | Exit/cost is a risk/cost lever, NOT expectancy: on powered universe (n=53k) no SL/TP cell clears E>0 OOS (max recoverable +0.30R = cost recovery, still negative); bottleneck is entry information (reality_gap +4.16R, 90.55% plain_stop_loss). 4th falsification (entry/conditional/selection/exit all null) | Likely |
| F-026 | ECON | Program 2/E1: completed sweep→displacement→retest adds NO forward asymmetry beyond sweep (BNBUSDT) — point estimate NEGATIVE, loses to all 4 controls; INSUFFICIENT_POWER (n=47, ~1% funnel completion); calibration passed (instrument valid). Program 2 not advancing to E2 | Likely |
| F-027 | ECON | Program 3A: coarser timeframes (H1/H4) do NOT rescue the directional edge — toy pool 0 PROMOTE at H1/H4 (H4 expansion_breakout only reaches cost-recovery gross≈0), spine non-decisive; extends the M15 four-falsification sweep to the HTF horizon | Likely |
| F-028 | ECON | First real interpreter (P&F PNF-v1, double-top/bottom) carries NO standalone edge on crypto majors — shadow-measured REJECT on BNBUSDT, worse than random controls (Δexpectancy −0.039); FROZEN, reopen only via a NEW ontology not a sweep; extends F-019→F-027 | Likely |
| F-029 | OPER | Feature-pipeline `center=True` swing lookahead AND `volatility_regime` global-rank are both benign for trade generation — byte-identical across CRYPTO MAJORS (BNB/BTC/ETH/SOL, A/B/C/S sweep; extends+graduates trust-layer F1) — the adversarial "FATAL leakage / kill-the-model" verdict is DOC_DRIFT, the alleged training-contamination path doesn't exist, and the "execution successor" (TradeNet v2) is already built; FX/metals NOT INFORMATIVE (0 trades on active config) so cross-asset-class stays OPEN | Likely |

---

## Findings — full record (non-terminal)

## Findings (non-terminal)

### F-001 · Intelligence is NOT the binding constraint
- Type:          ECONOMIC
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-06-03
- Revalidate-by: 2026-09-01
- Evidence:      docs/analysis/phase0-economic-edge-diagnosis-2026-06-03.md (FAIL 0/4); docs/analysis/edge-attribution-2026-06-03.md (per-candle AUC 0.5149, R² 0.004)
- Supersedes:    —
- Reversal:      "We need more/better intelligence (features, clusters, neural)" -> "Phase-0 funding gate failed 0/4 instruments; the binding constraints are governance integrity, throughput policy, and signal consumption — not state/feature discovery."
- Owner:         claude

### F-002 · The edge is in the decision PROCESS, not a static feature->outcome map
- Type:          ECONOMIC
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-03
- Revalidate-by: 2026-09-01
- Evidence:      docs/analysis/gate-contribution-bnbusdt-2026-06-03.md:18 (entire +0.58R appears at RETEST->EXECUTION; pre-execution geometry expectancy-neutral); docs/analysis/execution-planner-replay-bnbusdt-2026-06-03.md (2x2 attribution: the gate edge is SELECTION +0.145R, not SL/TP structure +0.031R ~4.7x smaller)
- Supersedes:    —
- Reversal:      "Find the magical state/pattern that predicts outcome" -> "Selection + execution structure (session policy, score gate, SL/TP) create the edge; timing inside a state beats pattern identity. Replay confirms it is SELECTION specifically (which candles trade), not SL/TP placement — structure SL/TP is risk-shaping (maxDD 6.0R->3.0R), not alpha."
- Owner:         claude

### F-003 · Throughput (N) is the ROI bottleneck; session policy is the proven lever
- Type:          ECONOMIC
- Status:        SUPERSEDED
- Confidence:    Likely
- Validated:     2026-06-01
- Revalidate-by: 2026-08-30
- Evidence:      docs/analysis/session-sweep-bnbusdt-2026-06-01.md:44 (+4.91% -> +20.59%, PF 1.79->2.54, 15->35 trades); docs/analysis/roi-funnel-diagnosis-bnbusdt-2026-05-30.md (RETEST->EXECUTION binding)
- Supersedes:    —
- Superseded-by: F-017 (the "proven lever" clause only)
- Reversal:      —
- Owner:         user
- Note:          SUPERSEDED 2026-06-11 — PARTIAL. The throughput-is-the-bottleneck clause SURVIVES (refined by F-015: the cheap levers are spent). What is falsified is the "session policy is the *proven* lever" clause: the +20.59% evidence was measured BOTH in-sample AND under the optimistic close-only exit model. Under the governing intrabar_touch exit model + a 70/30 OOS split it does NOT survive (docs/analysis/session-sweep-bnbusdt-2026-06-11.md → KEEP_INCUMBENT; all challengers fail OOS retention + Governance Threshold G1). The published V0 baseline (15 / PF 1.79 / +4.91%) is stale; true governing-exit V0 = 15 / PF 1.03 / +0.12%. See F-017 and docs/analysis/bnbusdt-in-spine-ledger-2026-06-11.md.

### F-004 · BitNet is a LIVE hard rejection gate, and its score IS persisted
- Type:          ARCHITECTURE
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-06-03
- Revalidate-by: 2026-09-01
- Evidence:      src/config_layer/crt_engine_v2.py:1804 · bitnet_main_score gate (`if bitnet_main_score < self.config.bitnet_main_threshold: return False, RejectReason.LOW_SCORE, 0.0`; threshold default at :363 · bitnet_main_threshold); src/runtime/backtest_v2.py:320 · bitnet_score_at_entry (persisted to TradeRecord)
- Supersedes:    —
- Reversal:      "BitNet score is built but not consumed / not persisted (dead-dormant-inventory.md:26)" -> "BitNet hard-gates entries at score<0.55 on the live/backtest CRT path and the score is persisted. What IS dormant is only the ADAPTIVE threshold (hardcoded 0.55; get_bitnet_threshold(regime) never called)."
- Owner:         claude

### F-005 · TradeNet v2 is BUILT but unwired (fusion neural slot is a stub)
- Type:          ARCHITECTURE
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-06-03
- Revalidate-by: 2026-09-01
- Evidence:      src/training/trade_net_v2.py (complete 3-head model); src/core/fusion_engine.py:8 ("Neural model — adaptive layer (stubbed; plug TradeNet GGUF here)"); EngineRunner never passes neural_fn -> defaults None
- Supersedes:    —
- Reversal:      "TradeNet v2 is designed-not-built (dead-dormant-inventory.md:17)" -> "TradeNet v2 is implemented but architecturally isolated; the fusion socket exists and is permanently empty. The risk is rebuilding it, not building it."
- Owner:         claude

### F-006 · config_integrity is a REAL check but ORPHANED (not enforced at runtime)
- Type:          GOVERNANCE
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-06-03
- Revalidate-by: 2026-09-01
- Evidence:      src/governance/config_integrity.py (validation_summary_is_fresh / active_version_is_governed are real hard checks, but the only caller is the one-off cutover script — not backtest_v2/live_engine_hook/promotion_manager runtime paths)
- Supersedes:    —
- Reversal:      "The deepdeektry governance bypass is closed (top-10 #2 'executed')" -> "It was closed by a one-time manual check, not an enforced gate; the integrity guard still gates nothing at runtime."
- Owner:         claude

### F-007 · Active production config is v4_multi_2026_06 (governed)
- Type:          GOVERNANCE
- Status:        SUPERSEDED
- Confidence:    Certain
- Validated:     2026-06-02
- Revalidate-by: 2026-08-31
- Evidence:      configs/production/ACTIVE_VERSION (= v4_multi_2026_06); configs/promotion_log.jsonl (PROMOTED entry, supersedes ungoverned "v2_multi_2026_04 - deepdeektry")
- Supersedes:    —
- Superseded-by: F-016 (branch-scoped correction)
- Reversal:      "Active config is v2_multi_2026_04 (per user-progress-registry, MEMORY)" -> "Active is v4_multi_2026_06 since the 2026-06-02 governed cutover; the registry/MEMORY anchors are stale."
- Owner:         user
- Note:          SUPERSEDED 2026-06-11 — this finding is branch-inaccurate on `patch`. BOTH cited evidences are FALSE on the `patch` working tree: configs/production/ACTIVE_VERSION reads "v2_multi_2026_04 - deepdeektry" (NOT v4), and configs/promotion_log.jsonl contains NO v4_multi_2026_06 PROMOTED entry (only v2 PROMOTED rows through 2026-05-06, then two PROMOTION_FAILED). Git confirms ACTIVE_VERSION on `patch` went v1_multi_2026_03 (5897209) -> "v2_multi_2026_04 - deepdeektry" (eb64269) directly — v4 was NEVER active here and was NOT reverted. Root cause: v4_multi_2026_06.json requires CRTConfig fields (tp3_enabled, tp3_atr_multiplier, score_component_weights) absent from this pre-TP3 engine (src/config_layer/crt_engine_v2.py — zero matches), so v4 was promoted on a NEWER code line; loading it on `patch` raises "ConfigBuilder: unknown override key(s)". v4 self-documents this at configs/research/research_config_spine.json:37. F-007 holds ONLY on the TP3 code line, not on `patch`. See F-016. (Per docs/architecture/pipeline-linkage-spine-as-hypothesis.md §8.)

### F-008 · Concept drift is detected but NOT acted on
- Type:          RISK
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-06-02
- Revalidate-by: 2026-08-31
- Evidence:      src/runtime/live_engine_hook.py:615 (HARD drift -> logger.error "Trade signal unreliable", trade proceeds; no block/size-down/gate)
- Supersedes:    —
- Reversal:      —
- Owner:         claude

### F-009 · Per-instrument doctrine validated; global/multi configs underperform
- Type:          GOVERNANCE
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-02
- Revalidate-by: 2026-08-31
- Evidence:      docs/analysis/audit-2026-06-02/top-10-roi-actions.md (BNBUSDT promoted; SOLUSDT PF~1 excluded; ETH/BTC off); docs/analysis/session-sweep-bnbusdt-2026-06-01.md
- Supersedes:    —
- Reversal:      —
- Owner:         user

### F-010 · Headline ROI is BACKTEST-only; live PnL is UNVERIFIED
- Type:          RISK
- Status:        OPEN
- Confidence:    Likely
- Validated:     2026-06-03
- Revalidate-by: 2026-09-01
- Evidence:      docs/analysis/economic-edge-gap-analysis-2026-06-03.md (caveats: ExecutionPlannerV1_2 + UltronRiskGate are live-only, NOT in the backtest spine that produced +20.59%); docs/analysis/execution-planner-replay-bnbusdt-2026-06-03.md (PARTIAL: ruled out a lucky-SL/TP artifact — the edge is selection-driven — but the replay still does NOT exercise ExecutionPlanner intent/TTL + UltronRiskGate sizing, so live PnL stays UNVERIFIED)
- Supersedes:    —
- Reversal:      —
- Owner:         user

### F-011 · OOS persistence is real but small; persistence != discrimination
- Type:          ECONOMIC
- Status:        DURABLE
- Confidence:    Likely
- Validated:     2026-06-01
- Revalidate-by: 2027-06-01
- Evidence:      docs/analysis/feature-region-oos-persistence-2026-06-01.md:44,77 (retention 0.93–1.51; 6/8 zones persistently negative; AUC 0.515 — regions retain a small mean, features barely separate winners)
- Supersedes:    —
- Reversal:      —
- Owner:         user

### F-012 · ReplayMemory / CognitiveBus / Cluster / HMF are sidecar-only (zero spine consumption)
- Type:          ARCHITECTURE
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-06-02
- Revalidate-by: 2026-08-31
- Evidence:      docs/analysis/intelligence-artifact-evidence-map-2026-06-02.md; src/replay/replay_memory_engine.py (0 imports in engine_runner/fusion/decision/execution/ultron/live_engine_hook/backtest_v2); cognitive_bus gated off by absent cognitive_layer (src/core/engine_runner.py:436)
- Supersedes:    —
- Reversal:      —
- Owner:         claude

### F-013 · The multi-signal scan→allocate→ExecutionLoop path is BUILT but ORPHANED (live runs the single-candle spine)
- Type:          ARCHITECTURE
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-06-05
- Revalidate-by: 2026-09-03
- Evidence:      docs/analysis/intent-vs-code-reconciliation-2026-06-05.md; zero callers in src/ for `ExecutionLoop` (src/execution/loop.py:31), scanner/ranker/signal_pool/universe (src/scanner/*), and `DecisionEngine.decide_batch` (src/core/decision_engine.py:162); live/backtest use EngineRunner→FusionEngine→decision_engine.evaluate→ExecutionPlannerV1_2→UltronRiskGate. Corollary: PortfolioAllocator + CorrelationEngine (built, src/portfolio/) and zone expectancy (stored in zone_registry, unread by zone_gate_engine.py) are NOT enforced live; portfolio-level risk limits are not applied on the live per-candle path.
- Supersedes:    integration-audit.md (2026-05-02) "regime/orchestrator/correlation not wired" — those ARE wired; the scanner/ExecutionLoop bypass remains
- Reversal:      —
- Owner:         claude

### F-014 · Time-to-first-move is a real, feature-orthogonal POST-ENTRY discriminator
- Type:          ECONOMIC
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-06
- Revalidate-by: 2026-09-04
- Evidence:      docs/analysis/pattern-timing-2026-06-06.md; src/replay/timing_reconstructor.py (shared core); within-cell win-rate separation fast(+0.25R≤3c)−slow = +0.768 ETH / +0.781 BNB, **54/54 cells**, ≈ unconditional gap (orthogonal to session/regime/geometry); decoupled TP_HIT lift +0.016–0.020 (positive but modest)
- Supersedes:    —
- Reversal:      —
- Owner:         claude
- Note:          Built measure-only, no model, by extending the existing opportunity_scanner walk (F-001 consumption doctrine). Strongest/cleanest use is POST-entry (early-invalidation: "no +0.25R by candle 3 ⇒ ~10% win-rate vs ~86%"); the pre-entry RANKING edge is real but modest and must clear a backtest A/B before live enable. Coupled-label (rr>0) separation is partly mechanical (0.5R trail) — see report §3.
- A/B (2026-06-06): signal-level early-invalidation A/B (docs/analysis/early-invalidation-ab-2026-06-06.md) → Net RR POSITIVE 4/4 instruments, all K=2-6 (ETH +301R, SOL +333R, BNB +265R, BTC +154R @k=3); winner-set avg RR PRESERVED (big winners move fast, not cut). BUT margin THIN (forgone offsets ~85-95% of saved) and expectancy lift small; MaxDD (likely main prize) unmeasured on the universe → executed-trade backtest A/B is the decisive next gate.
- Exec-trade A/B (2026-06-06, OFFLINE sanity check, BNB N=35, docs/analysis/early-invalidation-exectrade-ab-2026-06-06.md): mechanism CONFIRMED, winners PRESERVED (winner avg RR flat/up), Net RR +1.6R @k=3 (saved>forgone); Ulcer↓ + Time-under-water↓ BUT headline **MaxDD FLAT** (3.10%→3.10%) and expectancy rose — drawdown thesis only PARTIALLY supported, unprovable at N=35. VERDICT: research-complete / production-pending; FROZEN (no promote, no live, no spine change) until executed-trade throughput materially higher (ties F-003).

### F-015 · Detection-gate relaxation is NOT a quality-preserving throughput lever; cheap throughput is exhausted
- Type:          ECONOMIC
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-06
- Revalidate-by: 2026-09-04
- Evidence:      docs/analysis/detection-sweep-2026-06-06.md (BNB already tuned-loose: best relax expansion×0.66 = +26% trades @ PF 2.05/flat maxDD but FAILS +50% N gate; beyond that edge collapses PF→1.26/maxDD→6.8%; SOL unprofitable PF 0.29, every relaxation just adds losing trades → 0 viable); docs/analysis/funnel-diagnosis-2026-06-06.md (DISP→EXPANSION 5.0% binding); session lever exhausted (Phase 6e)
- Supersedes:    —
- Reversal:      —
- Owner:         claude
- Note:          The CRT funnel choke (DISP→EXPANSION 5%) is real but relaxing it trades quality for quantity at a bad rate — BNB is at its quality-bounded ceiling (~35-44 trades), SOL has no edge to scale. With sessions ALSO exhausted, executed-trade throughput is NOT cheaply expandable on BNB/SOL. IMPLICATION: validate Trd-M6 / F-014 via cross-instrument POOLING of executed trades (rule is per-trade, instrument-agnostic; pool BNB+ETH+BTC+SOL → N~100-200 without relaxing gates), not by manufacturing per-instrument trades. Refines F-003 (throughput is the bottleneck, but the cheap levers are spent).

### F-016 · On the `patch` branch the active production config is v2_multi_2026_04 (pre-TP3 engine); v4 applies only to the TP3 code line
- Type:          GOVERNANCE
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-06-11
- Revalidate-by: 2026-09-09
- Evidence:      configs/production/ACTIVE_VERSION (= "v2_multi_2026_04 - deepdeektry"; runtime print "Active production config: v2_multi_2026_04 - deepdeektry"); configs/promotion_log.jsonl (14 lines — v2_multi_2026_04 PROMOTED through 2026-05-06, then PROMOTION_FAILED 2026-05-10 + 2026-05-14; NO v4_multi_2026_06 entry); git log -- configs/production/ACTIVE_VERSION (v1_multi_2026_03 @5897209 -> "v2_multi_2026_04 - deepdeektry" @eb64269, no v4); src/config_layer/crt_engine_v2.py (zero matches for tp3_enabled / tp3_atr_multiplier / score_component_weights — schema gap); configs/research/research_config_spine.json:37 (v4 self-documents "NOT loadable on the `patch` branch"); docs/architecture/pipeline-linkage-spine-as-hypothesis.md §8
- Supersedes:    F-007 (branch-scoped correction; v4-active claim does not hold on `patch`)
- Reversal:      "Active is v4_multi_2026_06 since the 2026-06-02 governed cutover (F-007)" -> "On `patch`, active is v2_multi_2026_04 — v4 was NEVER active here and was NOT reverted; it was promoted on a NEWER (post-TP3) code line that `patch` predates. F-007 is true only on that line; both its cited evidences (ACTIVE_VERSION=v4, a v4 PROMOTED entry) are FALSE on this working tree."
- Owner:         claude
- Note:          NOT an ungoverned rollback. Git shows v4 never touched ACTIVE_VERSION on `patch`, so there is no revert-without-governance event to flag. The residual governance gap is orthogonal and already covered by F-006: the literal active string "v2_multi_2026_04 - deepdeektry" matches NO exact promotion_log version ("v2_multi_2026_04"), and config_integrity's active_version_is_governed check is orphaned (not enforced at runtime), so the "- deepdeektry" suffix passed unchecked. To MEASURE v4 on `patch`, check out the post-TP3 code line first (per research_config_spine.json:37), then set prod_version=v4_multi_2026_06. Branch-version truth must be stated per-branch, never globally.

### F-017 · Session policy is NOT a promotable BNBUSDT lever under realistic exits + OOS
- Type:          ECONOMIC
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-11
- Revalidate-by: 2026-09-09
- Evidence:      docs/analysis/session-sweep-bnbusdt-2026-06-11.md (OOS 70/30 + Governance Threshold G1 → KEEP_INCUMBENT: V3 +0.21%/mo IS -> +0.07%/mo OOS PF 1.09; V2 flips negative OOS; no challenger clears retention>=0.70 + G1); under governing exit_model intrabar_touch (src/config_layer/crt_engine_v2.py:353); docs/analysis/bnbusdt-in-spine-ledger-2026-06-11.md §A
- Supersedes:    F-003 (the "proven lever" clause; F-003's throughput-bottleneck clause survives via F-015)
- Reversal:      "Session expansion is the proven ROI lever (+4.91% -> +20.59%, F-003)" -> "That gain was in-sample AND measured under the optimistic close-only exit model. Under the governing intrabar_touch model + a 70/30 OOS split it does NOT survive (KEEP_INCUMBENT; all challengers fail G1). The in-sample lift was regime overfitting; the published V0 baseline (15/PF1.79/+4.91%) is stale — true governing-exit V0 = 15/PF1.03/+0.12%."
- Owner:         claude
- Note:          Scope discipline (per docs/analysis/bnbusdt-in-spine-ledger-2026-06-11.md §B): this falsifies the *session/directional* in-spine levers under intrabar truth, NOT "BNBUSDT has no edge, full stop." Three scoring engines that run every candle — Gaussian (NoOpScorer active), Zone Gate, RR — were NEVER isolated; the live UltronRiskGate is not in the backtest spine (F-010/F-013); and the most favorable evidence (v4, 35 trades) was never re-measured under intrabar (F-016). "Every *tested* in-spine lever is null," not "every lever."

---

### F-018 · Active config (patch) lags HEAD code — config↔code split-brain blocks data-gate governance
- Type:          GOVERNANCE
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-06-12
- Revalidate-by: 2026-09-10
- Evidence:      full-suite run (docs/research-readiness/test-gap-report.md): 21×`Section 'dataset_integrity' not found` + 5×`uat` + 2×`live_integration` in v2_multi_2026_04; src/config_layer/config_reachability classifier (docs/research-readiness/config-reachability-report.md) — bitnet_main_threshold + feature_monitor.{hard,soft}_drift_z are HARDCODED_OVERRIDE (config knob unread, magic literal used at src/config_layer/crt_engine_v2.py:1686 and src/features/feature_monitor.py:166)
- Reversal:      "The active config governs the data-integrity gate and the BitNet/drift thresholds" -> "On `patch`, HEAD code expects config sections (dataset_integrity/uat/live_integration) the active pre-TP3 v2 config never carried, and several config knobs are silently overridden by hardcoded literals — so those gates run on code defaults, not governed config. Concrete symptom of F-016's split-brain."
- Owner:         claude
- Note:          Spine + Backtest Trust Layer verified GREEN (metrics oracle parity / golden / invariants / replay determinism); the split-brain is localized to config-section presence + hardcoded knobs, not the scoring/fusion/decision path. Remediation roadmap: docs/research-readiness/research-readiness-report.md (R1/R2).
- Update:        2026-06-12 (R1 done) — the SECTION-ABSENCE half is RESOLVED: `dataset_integrity`/`uat`/`live_integration` added verbatim to configs/production/v2_multi_2026_04.json (hash unchanged — params-only); 75 previously-red tests green; BNBUSDT ledger byte-identical pre/post (1a624761f3a0…, behavior-neutral).
- Update:        2026-06-12 (R2 done) — the HARDCODED-KNOB half is RESOLVED: `bitnet_main_threshold` + `feature_monitor.{hard,soft}_drift_z` WIRED to config (crt_engine gates + FeatureMonitor construction). Behavior-neutral: BNBUSDT 1a624761f3a0… + SOLUSDT 27dabd57e259… ledgers byte-identical pre/post; reachability HARDCODED_OVERRIDE 3→0. Both concrete symptoms of F-018 now remediated; the underlying F-016 branch split-brain (v4/TP3 on the other code line) persists, so F-018 stays VALIDATED (not retired).

---

### F-019 · No existing hypothesis qualifies (M4) across the crypto majors under honest exits + cost
- Type:          ECONOMIC
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-12
- Revalidate-by: 2026-09-10
- Evidence:      results/research/qualification/qualify_majors.json + docs/analysis/qualify-majors-2026-06-12.md (intrabar_fixed + 12bps; per-instrument then pooled over BNB/ETH/BTC/SOL). Zero PROMOTE. Toy detectors REJECT on all 4 majors + pooled with baseline_delta vs random_uniform ≈0 (−0.076…+0.033) — entries statistically indistinguishable from random. Spine throughput-starved: 5–13 entries/instrument → INSUFFICIENT (n<30); pooled n=30 E=−0.399 REJECT (gate-2). Sole positive cell spine/SOLUSDT n=7 E=+0.45 PF=2.45 unusable (INSUFFICIENT).
- Supersedes:    —
- Reversal:      "We may already possess a qualifiable edge somewhere in the built pool and simply never measured it broadly" -> "We do not: under the unified intrabar+cost truth standard, every existing hypothesis fails on every major and pooled. The toy entry-edge null (≈random) now holds across all four crypto majors (extends F-001/F-002 beyond BNBUSDT); the spine cannot reach statistical power at its selectivity (ties F-003/F-015 throughput)."
- Owner:         claude
- Note:          A clean falsification, not a tooling failure — it forecloses 'reuse existing ideas' and selects the next phase. Implication: invent-new-entries (Phase C) is NOT yet justified (more geometry-shaped detectors would likely reproduce ≈random); the experiment points to process characterization (Phase B) — find where/whether direction is CONDITIONALLY predictable — before committing to a new entry family. The spine/SOL n=7 cell + the spine's own-backtest BTC +0.62R (positive only under scale-out tp1/tp2, negative under the single-TP research lens) are F-010 leads (live exec PnL unverified), not edges.

---

### F-020 · No candle-conditional directional pocket on the crypto majors (entropy "significance" ≠ exploitable)
- Type:          ECONOMIC
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-12
- Revalidate-by: 2026-09-10
- Evidence:      results/research/phase_b/phase_b_conditional_entropy.json + docs/analysis/conditional-entropy-majors-2026-06-12.md (paired entropy+economic grid, candle-only, intrabar_fixed+12bps; partition = session×vol-tercile×momentum-regime, horizons 1–20). 25/25 partitions BH-significant (Family A 20/20, Family B pooled 5/5) BUT at the 0.0020 permutation floor with IG≈0.001–0.0036 bits, H(dir|partition)≈0.995–0.999, p_up 0.50–0.52; Stage-3 economics on 74 candidate cells → **0 pockets** (VERDICT ENTROPY_LEAD_NO_ECON). Sanity: BNB@1 H_uncond≈0.9995 reproduces process_diagnostics global ≈0.999.
- Supersedes:    —
- Reversal:      "Direction may become predictable under the right regime/session/vol conditioning" -> "Not on crypto-major M15: no candle-derivable partition (session×vol×momentum, h=1..20, per-instrument or pooled) yields an exploitable directional pocket. Partition permutation-significance SATURATES at large N (25/25 trip; necessary-not-sufficient) — the binding filter is the economic stage, which finds zero pockets. Extends F-001/F-002/F-019 from 'no global edge' to 'no local candle-conditional edge.'"
- Owner:         claude
- Note:          The paired design earned its keep: an entropy-only screen would have reported 25/25 'significant' leads (false, N-driven); requiring BOTH a significant entropy dip AND a cost-aware economic edge filtered all 74 candidate cells to zero. B2 (CRT-event labels) is NOT entered — the advance gate was a genuine lead (entropy pocket AND economic pocket); zero economic pockets = no lead. Redirect off next-bar direction toward non-directional levers: spine selection/throughput (F-015) and exit/cost structure (the 88% plain_stop_loss forensic).

---

### F-021 · The spine's RETEST selection IS the session filter — no score/zone skill under intrabar truth
- Type:          ECONOMIC
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-13
- Revalidate-by: 2026-09-11
- Evidence:      results/research/phase_s/phase_s_selection_effect.json + docs/analysis/selection-effect-crypto6-2026-06-13.md (intrabar_fixed+12bps, pooled-by-effect crypto-6, ΔE=selected−rejected retests decomposed by reject-reason). Selected−rejected ΔE=+1.171R p=0.0005 OOS+1.212 4/4 — but SESSION≡ALL (110/112 rejects off-session); genuine skill classes null: ZONE 0/110 rejects (never binds), SCORE 2/110 → p=0.327 OOS−0.291. Trust gate: selected==approved_trades all 6. S0 wired the dormant RETEST_REPLAY emitter (zero callers; behavior-neutral — BNB ledger 0fd8ee6a byte-identical pre/post, records 0→44).
- Supersedes:    — (updates F-002 under the governing exit model)
- Reversal:      "Selection adds +0.145R at the RETEST→EXECUTION gate (F-002)" -> "Under the governing intrabar+12bps standard the selected−rejected effect is large (+1.17R) but ENTIRELY the SESSION filter (SESSION class ≡ ALL class); the score/zone selection-skill classes are non-binding (ZONE 0 rejects) or noise (SCORE n=2, p=0.33, OOS−0.29). The spine's RETEST selection IS the incumbent, F-017-non-improvable session filter — there is no score/zone selection skill. F-002 does not survive as NEW skill; sparse-selection-beyond-session is falsified."
- Owner:         claude
- Note:          The reject-reason decomposition was decisive: the ALL class alone would have FALSELY shown "selection skill" (+1.17R / p<0.001 / 4-of-4 / OOS +1.21); decomposing localizes 100% to SESSION. Structural facts (ZONE 0/110, SCORE 2/110, SESSION 110/112) are power-independent (F-006b: retest score gate non-binding, 134/135 pass), even though N is thin (4 usable instruments; SCORE rests on 2 samples). Three falsifications now stand under intrabar truth — direction (F-019), conditional direction (F-020), selection-beyond-session (F-021); the only working in-spine lever (session) is incumbent + F-017-non-improvable. Remaining unfalsified thread = exit/cost structure (Phase D, the 88% plain_stop_loss).

---

### F-022 · opportunities.jsonl is a DETECTION STREAM, not a trade ledger (its outcome/rr are internally inconsistent)
- Type:          GOVERNANCE
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-06-13
- Revalidate-by: 2026-09-11
- Evidence:      results/research/bnbusdt_trade_anatomy/anatomy_summary.json (artifact_consistency_rate 0.368; outcome_distribution_artifact 138,091 SL / 1,830 TP / 21 TIMEOUT vs outcome_distribution_governing 91,914 SL / 46,580 TP / 1,448 TIMEOUT) + docs/analysis/BNBUSDT_TRADE_ANATOMY_2026_06_13.md §1 (91,126 SL_HIT rows whose own mae never reaches the stop; consistency check `art_outcome==SL_HIT and art_mae > -risk`); scripts/analysis/bnbusdt_trade_anatomy.py (realized layer DERIVED via governing forward_walk(intrabar_fixed), artifact kept as flagged art_* x-ref)
- Supersedes:    —
- Reversal:      "opportunities.jsonl outcome/rr_achieved are realized trade results" -> "they are detection-time labels, only 36.8% self-consistent (SL_HIT logged on paths that never touch the stop). The file is a DETECTION STREAM, not a trade ledger — realized truth must be DERIVED via the governing intrabar exit; the artifact's outcome/rr/mfe/mae are unreliable and retained only as flagged x-ref. Corollary FREQUENCY ILLUSION: 139,942 detections ≠ trades; the governed spine takes 13."
- Owner:         claude
- Note:          Same governance-integrity family as F-006 (orphaned check) / F-018 (config↔code split-brain) — a truth-layer defect caught BEFORE it could inflate any downstream study (the recovered-first sanity check earned its keep).
- Update:        2026-06-13 (cross-instrument) — **REPOSITORY-WIDE + mechanism named.** BTC/ETH/SOL regenerated and run through the same pipeline: artifact_consistency_rate 0.372 / 0.370 / 0.358 (≈ BNB 0.368); artifact ~98–99% SL_HIT vs governing ~66% SL / ~33% TP on all four. MECHANISM: scripts/research/opportunity_scanner.py (`_simulate` :53) labels outcome/rr under a **0.5R TRAILING stop** — a trailing SL_HIT legitimately has rr>0 / mae>-risk, so the artifact is internally consistent with its OWN trailing model but mismatches the governing intrabar_fixed exit. So this is **NOT corruption**: "trailing-stop ground-truth ≠ governing fixed-stop realized; reading its labels as fixed-stop results is the error." The earlier OPEN follow-up is RESOLVED — the defect DOES broaden to all scanner-generated opportunities.*. Evidence: docs/analysis/cross-instrument-anatomy-2026-06-13.md; results/research/{btcusdt,ethusdt,solusdt}_trade_anatomy/anatomy_summary.json.

### F-023 · Feature morphology separates SHAPE, not expectancy
- Type:          ECONOMIC
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-13
- Revalidate-by: 2026-09-11
- Evidence:      results/research/bnbusdt_trade_anatomy/anatomy_summary.json (morphology_clusters: KMeans k=4 on standardized ema_spread/volume_ratio/volatility_ratio/body_ratio/momentum_score/trend_strength/disp_strength/retest_depth/atr over 139,942 opportunities; clusters differ in anatomy/duration but win_rate ≈ 0.334–0.343 and mean_R ≈ −0.000…+0.023 in ALL four) + docs/analysis/BNBUSDT_TRADE_ANATOMY_2026_06_13.md §2 Q5
- Supersedes:    — (updates F-002 under the governing exit; consistent with F-011 "features barely separate")
- Reversal:      "Cluster the feature space harder and a winning morphology will appear" -> "Feature morphology separates trade SHAPE (fast winner / slow grinder / immediate loser / late failure) but NOT economics — every cluster has the same ~34% win-rate and ~0 mean_R. Descriptive, not predictive; this forecloses the 'just cluster harder' class of entry research on BNBUSDT."
- Owner:         claude
- Note:          Descriptive morphology only — no 'cluster N = edge' claim. Scores were NOT available at this grain (spine-only, N=13), so this is a FEATURE-morphology result, not a score-morphology one.

### F-024 · Continuation timing asymmetry — losers resolve almost immediately; winners mature over ~90 min (NOT 5.5 h)
- Type:          ECONOMIC
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-13
- Revalidate-by: 2026-09-11
- Evidence:      results/research/bnbusdt_trade_anatomy/anatomy_summary.json (peak_timing, de-censored PEAK_HORIZON=96 while realized layer held at MAX_FORWARD=40 byte-stable). bars_to_peak_within_trade (bounded by realized exit): LOSERS p50=1 / p90=6 bars; WINNERS p50=6 / p90=18 bars (~90 min median, ~4.5 h p90). survival_P_not_stopped ½-stopped by ~bar 6 (90 min). Path metric is uninformative: bars_to_peak_path p50 winners 46 ≈ losers 43, p90 pinned at 92/96 (random-walk, still censored). docs/analysis/BNBUSDT_TRADE_ANATOMY_2026_06_13.md §2 Q4/Q1
- Supersedes:    —
- Reversal:      "Winners peak late, ~22 bars / 5.5 h (Phase-1 censored median)" -> "That was a 40-bar-window artifact. De-censored, the EXIT-AGNOSTIC path peak is a random walk (winners≈losers, p90 pinned at the cap) and carries no information; the honest signal is the WITHIN-TRADE peak: losers resolve almost immediately (median 1 bar, then stop out) while winners mature over a median 6 bars (~90 min, p90 18). The asymmetry is early-resolution of losers, not slow 5.5 h maturation of winners."
- Owner:         claude
- Note:          DESCRIPTIVE, not predictive — and partly MECHANICAL: within-trade peak is coupled to duration/survival (a 1-bar SL-hit necessarily peaks by bar 1), so F-024 largely restates F-024's own survival curve from the peak side, not an independent edge. Gated on measurement per the freeze-order discipline: the block was withheld until the de-censored run (PEAK_HORIZON=96) replaced the censored median-22; the de-censoring actively corrected the number (the reason for the gate). No entry/exit lever is claimed.
- Update:        2026-06-13 (cross-instrument) — **REPLICATES near-identically** on BTC/ETH/SOL: within-trade peak winners p50=6 / p90≈18–19, losers p50=1 / p90=6 on all four coins; the exit-agnostic path peak stays random-walk/uninformative everywhere. Confidence held at Likely (descriptive, partly mechanical) but now cross-instrument-robust. docs/analysis/cross-instrument-anatomy-2026-06-13.md.

### F-025 · Exit/cost is a risk/cost lever, NOT an expectancy lever — the fourth falsification
- Type:          ECONOMIC
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-13
- Revalidate-by: 2026-09-11
- Evidence:      results/research/phase_d/phase_d_exit_grid.json + docs/analysis/exit-grid-crypto6-2026-06-13.md (42-cell SL{0.5..3.0}×TP{1.0..5.0} grid, intrabar_fixed+12bps, IS+OOS, entries FIXED). UNIVERSE (n=53,629, decisive): REGIME ENGINEERING (structural_upper_bound −0.175R); every cell E_oos<0 (incumbent 1.0x2.0 −0.569, best 3.0x5.0 −0.271, max_recoverable_E +0.299 = cost recovery only, still negative); loss plain_stop_loss 90.55% + same_bar 9.25%; reality_gap +4.16R, ceiling_utilization −4% (104% of lost value is entries, not exits). SPINE (n=30, relevance): nominal leads (0.75x4.0 E_oos +0.327) but only 2/4 instruments + ~9 OOS trades = tiny-N artifact, NOT promoted, D4 NOT entered.
- Supersedes:    — (confirms/extends F-002's "SL/TP is risk-shaping not alpha" cross-instrument under intrabar)
- Reversal:      "Exit/cost geometry might recover positive expectancy (the last unfalsified branch)" -> "It does not: on the powered universe no SL/TP cell yields E>0 OOS; max recoverable +0.30R is cost/risk shaping, still net-negative. Exits are a risk/cost-management lever, not an expectancy lever. The bottleneck is ENTRY INFORMATION (reality_gap +4.16R; 90.55% plain_stop_loss; gross E≈0 — favorable excursions exist but are uncapturable without foresight). FOURTH falsification: entry (F-019) / conditional (F-020) / selection (F-021) / exit (F-025) are ALL null under the governing truth standard — the first full research-program sweep is closed."
- Owner:         claude
- Note:          The ceiling gate worked as designed: structural ≤0 → ENGINEERING banner printed above the grid, so the +0.30R cost-recovery + lower-MaxDD wide-stop cells read as engineering, never alpha. The spine arm's ALPHA banner/nominal lead correctly surfaced because its 30 entries are gross-positive (+0.5) under a 1:2 geometry — then the strict bar + N-scrutiny (n=30, 2/4 instruments, ~9 OOS trades) correctly demoted it to the named failure mode ("mistaking a tiny better cell for alpha"). D4 deliberately NOT entered (would be the optimization spiral the gate prevents). Open question shifts from "which lever" to "is the next-bar-direction ontology wrong" — a deeper redirect (instrument class / timeframe / target), not another grid. Engineering value (cost/MaxDD reduction via wider stops at flat-negative E) remains for portfolio hygiene, not alpha.
- Update:        2026-06-13 (cross-instrument anatomy corroboration) — the BNB/BTC/ETH/SOL trade-anatomy independently reproduces cost-domination via a SECOND measurement path (detection-stream fixed-time exits, not the exit grid): gross mean_R ≈ 0.000 at EVERY coin × horizon {15,30,45,60,90m}, net (12bps) < 0 everywhere — BNB −0.43 / BTC −0.52 / ETH −0.33 / SOL −0.25 (per-coin magnitude = 0.0012·entry/ATR, so BTC's low ATR/price ratio costs most R). Confirms "signal-neutral, cost makes it negative." docs/analysis/cross-instrument-anatomy-2026-06-13.md. NOTE: the Phase-2 BNBUSDT anatomy work labelled this observation an "F-025 candidate / watch (cost destroys neutrality)" — that was an **id collision**; it is the SAME conclusion as this existing F-025 and is hereby folded in as corroboration (no new finding minted).

### F-026 · Completed sweep→displacement→retest adds NO forward asymmetry beyond sweep alone (BNBUSDT; negative + underpowered)
- Type:          ECONOMIC
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-13
- Revalidate-by: 2026-09-11
- Evidence:      results/research/phase_e/phase_e_structural_asymmetry.json + docs/analysis/structural-asymmetry-bnbusdt-2026-06-13.md (Program 2 Phase E1; PURE asymmetry, NO profitability — multi-horizon MFE/MAE + symmetric first-hit, 4 controls, permutation + OOS + in-pipeline calibration). VERDICT INSUFFICIENT_POWER · POWER INADEQUATE. Funnel: sweep 4529 → disp 391 (P(disp|sweep)=8.6%) → exp 85 → retest 47 (P(retest|disp)=12%) → exec 16 (~1% sweep→retest completion). Test (n=47): excursion_asym(h8)=−0.319, first_hit_delta(L0.5)=−0.106 — NEGATIVE and LOSES to all four controls incl. sweep-only D (every permutation Δ<0, p>0.6). Calibration PASSED (planted 0.55→recovered 0.55 → instrument valid). OOS n=14, CI±0.23.
- Supersedes:    —
- Reversal:      "Maybe completing the trap structure (sweep→displacement→retest) creates forward continuation asymmetry the candle/executed tests missed (the Program-2 thesis)" -> "Not on BNBUSDT M15: the completed-retest population (n=47) shows LESS forward asymmetry than sweep alone and than every control — a NEGATIVE point estimate. N=47 (14 OOS) is too small to PROVE 'no asymmetry' (verdict INSUFFICIENT_POWER, not NULL — the absence-of-evidence guard), but the direction is wrong and the funnel shows ~1% sweep→retest completion (throughput-starved). Calibration passed → trustworthy. Program 2 / E1 does NOT advance to E2."
- Owner:         claude
- Note:          The frozen protocol worked as designed: calibration proved the instrument (the result is real, not broken measurement); the four-way verdict returned INSUFFICIENT_POWER (never a false NULL); the funnel/attrition (P(disp|sweep)=8.6%) is the most valuable output. Per pre-registration, only ASYMMETRY_SURVIVES advances — this does not, so NO E2/conditioning/entry/exit work (the named failure mode avoided). With F-019/020/021/025, the weight of evidence is against the trap-continuation thesis. Reopen only via a NEW structural ontology or a cross-instrument POOLED retest population showing a non-negative, adequately-powered signal — never a threshold tweak.

### F-027 · Coarser timeframes (H1/H4) do NOT rescue the directional edge — the M15 null replicates
- Type:          ECONOMIC
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-13
- Revalidate-by: 2026-09-11
- Evidence:      results/research/qualification_htf/qualify_htf_H1.json + qualify_htf_H4.json (Program 3A = BAR_COUNT_CONSTANT; intrabar_fixed+12bps, per-instrument then pooled crypto-majors, IS+70/30 OOS+BH; H4 body byte-identical re-run 0317fc878d6a…). Drivers scripts/research/qualify_htf.py + scripts/research/build_resampled_data.py; deterministic resampler src/research/resample.py (tests/research/test_resample.py — associativity + SHA-256). Toy directional pool: **0 PROMOTE at H1 AND H4.** H1 every cell REJECT, E_oos −0.136..−0.266. H4 expansion_breakout creeps to gross ≈0 (BNB +0.014 / SOL +0.035 / ETH +0.022) but POOLED −0.0009 and NONE clears BH + beats-control + OOS (SOL p=0.0575); mean_reversion solidly negative (E −0.12..−0.18). Spine arm NON-DECISIVE: H1 pooled n=10 INSUFFICIENT (5/1/2/2 per inst); H4 NOT_MEASURABLE (the spine adapter's INDEX CONTRACT `candle_idx-1 == stream pos`, src/research/adapters/spine_signal_source.py:203, assumes M15-native candle_open and is invalid for resampled candles).
- Supersedes:    —
- Reversal:      "The directional null (F-019/020/021/025) may be an artifact of M15's signal-to-noise; a coarser bar (H1/H4) could rescue the edge" -> "It does not. On crypto-major H1 and H4 the toy directional pool is still REJECT (no qualified edge); H4 expansion_breakout reaches only cost-recovery gross-≈0 (ties F-025: max recoverable = cost recovery, still not edge). Program 3A extends the four-falsification sweep from M15 to the H1/H4 horizon — coarser timeframes are not the missing lever."
- Owner:         claude
- Note:          DECISIVE only for the POWERED toy arm (n=2.7k-22k). The spine arm is NOT a falsification — it is throughput-starved/non-measurable at HTF (recorded NOT_MEASURABLE, never REJECT; fixing the adapter's M15-native index contract would still leave n<30 INSUFFICIENT). OPEN CONTINGENCY: Program 3B (WALL_CLOCK_CONSTANT) was pre-defined NOT built — a null at 3A's bar-count horizon (40 bars = 40h H1 / 160h H4) does not strictly rule out a wall-clock-matched forward horizon, though the directional-null family makes it a low prior. Reopen only via 3B or a NEW ontology (non-directional target / non-crypto universe), never a Program-1 parameter pass.

### F-028 · P&F (PNF-v1) double-top/bottom carries NO standalone edge on crypto majors — first interpreter, REJECTED
- Type:          ECONOMIC
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-14
- Revalidate-by: 2026-09-12
- Evidence:      The FIRST real interpreter, run shadow-only through the UNCHANGED chain (InterpreterHypothesis → HypothesisRunner → forward_walk → M4 QualificationGate), intrabar_fixed+12bps, BNBUSDT. PNF-v1 (box=0.5×ATR(20), 3-box reversal, double-top→LONG / double-bottom→SHORT): n=8554, PF=0.528, E[R]=−0.4538, win_rate=0.327 → VERDICT **REJECT** (gate2 expectancy<0, p=0.991). LOSES to the winning control random_uniform (E[R]=−0.4147) on every Δ: Δexpectancy=−0.039, ΔPF=−0.031, Δcapture=−0.064. Consistent with the directional-null family F-019→F-027 (no directional pocket on crypto majors under realistic exits+cost). Interpreter src/interpreters/point_and_figure.py; driver scripts/research/qualify_interpreter.py; e2e tests/interpreters/test_pnf_shadow_e2e.py; topic docs/topics/interpreter-contract.md. FROZEN in the Funding Ledger.
- Supersedes:    —
- Reversal:      "a classic chart pattern (P&F double-top) might add a directional edge" -> "PNF-v1 is worse than random on BNBUSDT; the contract+chain measured it honestly (REJECT) and it is FROZEN — reopen only via a NEW ontology, never a box/reversal sweep"
- Owner:         claude

### F-029 · Feature-pipeline `center=True` swing lookahead is benign for trade generation — the adversarial "FATAL leakage / kill the model" verdict is DOC_DRIFT vs measured evidence
- Type:          OPERATIONAL
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-15
- Revalidate-by: 2026-09-13
- Evidence:      A 2026-06-15 adversarial design session escalated `center=True` swing detection (src/features/feature_pipeline.py:343) to "FATAL label leakage" and demanded a repo-wide pipeline rewrite + model deletion. Verification against code reconciles it to the already-validated trust-layer **F1** (docs/analysis/backtest-trust-audit-2026-06-10.md §4d): with TRUST_SWING_CAUSAL=1 (src/features/feature_pipeline.py:366), 974/3000 swing flags shift yet the BNBUSDT ledger is byte-identical (0 trades added/removed, edge inflation ≈ 0) because the CRT entry path does not consume swing columns. Two further adversarial premises are FALSE in code: the claimed training-contamination chain `TradeRecord.features → dataset builder → tensor` does not exist (training reads opportunities_*.jsonl via scripts/training/train_trade_net_v2.py), and the proposed "execution-quality successor" already exists as TradeNet v2 (src/training/trade_net_v2.py; wired as a soft neural_fn via src/training/trainer.py make_neural_fn_v2 — see F-005). Program B (measure-only, RESOLVED): `volatility_regime` uses a GLOBAL `rank(pct=True)` (src/features/feature_pipeline.py:306) that IS decision-reachable (src/strategies/s05_grid.py:120 blocks LONG in TRENDING). The TRUST_VOLREGIME_CAUSAL A/B/C hook (global vs expanding vs rolling) was run on v2_multi_2026_04/BNBUSDT via the production spine: all three are byte-identical (13 trades, WR 0.3077, PF 0.5233, ROI −4.63%; 100% decision overlap, 0 added/removed) → `A≈B≈C` ⇒ benign on this config (same class as F1; the governing CRT spine, not s05_grid, drives this config). Recorded in docs/analysis/backtest-trust-audit-2026-06-10.md §4f; driver results/trust/volregime_measure.py. CROSS-UNIVERSE (§4g): the A/B/C/S sweep (+ TRUST_SWING_CAUSAL for F1) across BTC/ETH/SOL + AUDUSD/GBPUSD/USDJPY/XAUUSD is byte-identical (100% decision overlap) on every instrument → both F1 (swing center=True) and F-029 (volregime global-rank) GRADUATE from "BNBUSDT benign" to "CRYPTO-MAJORS benign" (BNB+BTC+ETH+SOL, real trade counts 5/5/7). HONEST CAVEAT: the 4 FX/metals rows are NOT INFORMATIVE — the active multi config approves 0 trades on them (no FX tuning), so their "benign" is vacuous; the cross-asset-class claim stays OPEN pending an FX-trading config. The global→causal conversion (Option 2) stays gated on a future config/instrument showing material divergence.
- Supersedes:    —
- Reversal:      "center=True swing detection is FATAL label leakage that contaminates the model and forces a pipeline rewrite" -> "F1 already measured it byte-identical-benign for trade generation on BNBUSDT; the FATAL framing is DOC_DRIFT, the alleged training-contamination path does not exist, and the proposed successor model is already built — the LIVE-UNSAFE flag stands but no backtest edge depends on it"
- Owner:         claude

---
