# Current Findings — Repository Truths (living)

> Created: 2026-06-03 · Updated: 2026-06-24
>
> **What this is.** The repo's *current validated conclusions* — the verdicts that change roadmap
> and funding decisions — each dated, evidence-linked, and confidence-rated. This is the **living
> complement** to [`docs/analysis/`](analysis/readme.md) (which is point-in-time history, "not
> current truth"). The thin always-loaded index lives in [`CLAUDE.md`](../CLAUDE.md) → *Repository
> Truths Index*; this file is the full record.
>
> **See also:** [`knowledge-map.md`](knowledge-map.md) (how the record systems connect) · [`timeline.md`](timeline.md) (when each finding landed) · [`plans/readme.md`](plans/readme.md) (the plans behind them) · [`analysis/readme.md`](analysis/readme.md) (evidence).
>
> **Why it exists.** Cold-start loaded architecture but not conclusions, so sessions re-ran settled
> investigations and even trusted stale audit claims. This layer makes conclusions first-class and
> mechanically fresh (`tests/test_current_findings.py`).
>
> **Discipline (CLAUDE.md §6.2 Findings Mandate).** When a session **validates or overturns** a
> conclusion, add or flip a finding in the *same turn* — set `Validated`/`Revalidate-by`, cite
> `Evidence`, and fill `Reversal` if it overturns a prior belief. **Never delete** a finding —
> mark it `SUPERSEDED`/`RETIRED` and keep the row (append-discipline). `Confidence` vocab matches
> `MEMORY.md`: `Certain` · `Likely` · `Possible`.

---

## Schema (one block per finding)

```
### F-NNN · <one-line conclusion>
- Type:          ARCHITECTURE | ECONOMIC | GOVERNANCE | OPERATIONAL | RISK
- Status:        VALIDATED | OPEN | DURABLE | SUPERSEDED | RETIRED
- Confidence:    Certain | Likely | Possible
- Validated:     YYYY-MM-DD
- Revalidate-by: YYYY-MM-DD        (the mechanical freshness horizon; per-status window below)
- Evidence:      <file:line or docs/analysis/... link>   (REQUIRED, non-empty)
- Supersedes:    F-xxx | —
- Reversal:      "<old assumption>" -> "<current conclusion>"   (when applicable)
- Owner:         user | claude
```

**Revalidation windows (per status).** `Revalidate-by` is checked by CI; the gap from `Validated`
must stay within the status ceiling:

| Status | Window (`Revalidate-by − Validated`) | Freshness-checked? |
|---|---|---|
| `VALIDATED` / `OPEN` | ≤ 180d (default 90d) | yes — fails CI past `Revalidate-by` |
| `DURABLE` | ≤ 400d (default 365d) | yes — annual re-affirm; for stable empirical truths |
| `SUPERSEDED` / `RETIRED` | — | exempt; kept for replay |

`DURABLE` is **not** never-expire: even a stable truth (e.g. *persistence ≠ discrimination*) gets a
yearly sanity check, because "obvious" conclusions still reverse (see F-004). True engineering
invariants (no-lookahead, causal backtest) are design law and live in `goal.md`, not here.

---

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
- Revalidate-by: 2026-09-25
- Evidence:      results/research/qualification/qualify_majors.json + docs/analysis/qualify-majors-2026-06-12.md (intrabar_fixed + 12bps; per-instrument then pooled over BNB/ETH/BTC/SOL). Zero PROMOTE. Toy detectors REJECT on all 4 majors + pooled with baseline_delta vs random_uniform ≈0 (−0.076…+0.033) — entries statistically indistinguishable from random. Spine throughput-starved: 5–13 entries/instrument → INSUFFICIENT (n<30); pooled n=30 E=−0.399 REJECT (gate-2). Sole positive cell spine/SOLUSDT n=7 E=+0.45 PF=2.45 unusable (INSUFFICIENT).
- Supersedes:    —
- Reversal:      "We may already possess a qualifiable edge somewhere in the built pool and simply never measured it broadly" -> "We do not: under the unified intrabar+cost truth standard, every existing hypothesis fails on every major and pooled. The toy entry-edge null (≈random) now holds across all four crypto majors (extends F-001/F-002 beyond BNBUSDT); the spine cannot reach statistical power at its selectivity (ties F-003/F-015 throughput)."
- Owner:         claude
- Note:          A clean falsification, not a tooling failure — it forecloses 'reuse existing ideas' and selects the next phase. Implication: invent-new-entries (Phase C) is NOT yet justified (more geometry-shaped detectors would likely reproduce ≈random); the experiment points to process characterization (Phase B) — find where/whether direction is CONDITIONALLY predictable — before committing to a new entry family. The spine/SOL n=7 cell + the spine's own-backtest BTC +0.62R (positive only under scale-out tp1/tp2, negative under the single-TP research lens) are F-010 leads (live exec PnL unverified), not edges.
- Update:        2026-06-27 (E3 revalidation — finding_dependency_audit Phase B/B2) — re-ran qualify_majors on stabilized HEAD (post 38-feature integration / fusion cleanup / F-038 rr_fusion disable). UNCHANGED: 0 PROMOTE; toy AND spine arms BYTE-IDENTICAL to the 2026-06-12 baseline (verdicts {11 REJECT, 4 INSUFFICIENT}). The spine byte-identity corroborates F-037 (backtest gate is OFF → CRT-only spine; the F-038 rr_fusion disable never reaches research-spine entries). Conclusion: Epoch-3 = stabilized Epoch-2 (stabilization created NO new economic universe). Evidence: results/research/qualification_2026_06_27/qualify_majors.json.

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
- Revalidate-by: 2026-09-25
- Evidence:      results/research/phase_s/phase_s_selection_effect.json + docs/analysis/selection-effect-crypto6-2026-06-13.md (intrabar_fixed+12bps, pooled-by-effect crypto-6, ΔE=selected−rejected retests decomposed by reject-reason). Selected−rejected ΔE=+1.171R p=0.0005 OOS+1.212 4/4 — but SESSION≡ALL (110/112 rejects off-session); genuine skill classes null: ZONE 0/110 rejects (never binds), SCORE 2/110 → p=0.327 OOS−0.291. Trust gate: selected==approved_trades all 6. S0 wired the dormant RETEST_REPLAY emitter (zero callers; behavior-neutral — BNB ledger 0fd8ee6a byte-identical pre/post, records 0→44).
- Supersedes:    — (updates F-002 under the governing exit model)
- Reversal:      "Selection adds +0.145R at the RETEST→EXECUTION gate (F-002)" -> "Under the governing intrabar+12bps standard the selected−rejected effect is large (+1.17R) but ENTIRELY the SESSION filter (SESSION class ≡ ALL class); the score/zone selection-skill classes are non-binding (ZONE 0 rejects) or noise (SCORE n=2, p=0.33, OOS−0.29). The spine's RETEST selection IS the incumbent, F-017-non-improvable session filter — there is no score/zone selection skill. F-002 does not survive as NEW skill; sparse-selection-beyond-session is falsified."
- Owner:         claude
- Note:          The reject-reason decomposition was decisive: the ALL class alone would have FALSELY shown "selection skill" (+1.17R / p<0.001 / 4-of-4 / OOS +1.21); decomposing localizes 100% to SESSION. Structural facts (ZONE 0/110, SCORE 2/110, SESSION 110/112) are power-independent (F-006b: retest score gate non-binding, 134/135 pass), even though N is thin (4 usable instruments; SCORE rests on 2 samples). Three falsifications now stand under intrabar truth — direction (F-019), conditional direction (F-020), selection-beyond-session (F-021); the only working in-spine lever (session) is incumbent + F-017-non-improvable. Remaining unfalsified thread = exit/cost structure (Phase D, the 88% plain_stop_loss).
- Update:        2026-06-27 (E3 revalidation — finding_dependency_audit Phase B/B3) — re-ran phase_s on the stabilized spine: verdict SELECTION_IS_SESSION_ONLY UNCHANGED. SESSION 112 rejects (ΔE +1.171R, p=0.0005, OOS +1.212, sign 4/4); ZONE 0 rejects (never binds); SCORE 2 rejects (OOS ΔE −0.291, p=0.327). Decomposition essentially identical to 2026-06-13; no score/zone skill emerged from stabilization. Evidence: results/research/phase_s_2026_06_27/phase_s_selection_effect.json.

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
- Revalidate-by: 2026-09-25
- Evidence:      results/research/bnbusdt_trade_anatomy/anatomy_summary.json (morphology_clusters: KMeans k=4 on standardized ema_spread/volume_ratio/volatility_ratio/body_ratio/momentum_score/trend_strength/disp_strength/retest_depth/atr over 139,942 opportunities; clusters differ in anatomy/duration but win_rate ≈ 0.334–0.343 and mean_R ≈ −0.000…+0.023 in ALL four) + docs/analysis/BNBUSDT_TRADE_ANATOMY_2026_06_13.md §2 Q5
- Supersedes:    — (updates F-002 under the governing exit; consistent with F-011 "features barely separate")
- Reversal:      "Cluster the feature space harder and a winning morphology will appear" -> "Feature morphology separates trade SHAPE (fast winner / slow grinder / immediate loser / late failure) but NOT economics — every cluster has the same ~34% win-rate and ~0 mean_R. Descriptive, not predictive; this forecloses the 'just cluster harder' class of entry research on BNBUSDT."
- Owner:         claude
- Note:          Descriptive morphology only — no 'cluster N = edge' claim. Scores were NOT available at this grain (spine-only, N=13), so this is a FEATURE-morphology result, not a score-morphology one.
- Update:        2026-06-27 (E3 revalidation — finding_dependency_audit Phase B/B1) — re-ran trade_anatomy clustering with governing forward_walk(intrabar_fixed) labels (NOT the F-022-unreliable artifact outcome/rr). UNCHANGED: all 4 KMeans k=4 clusters win_rate 0.3345–0.3428 (≈0.34±0.01), mean_R −0.0001…+0.0228 (within ±0.023), n=139,942 (dataset_sha256 f8bdabbe…). Morphology = SHAPE not expectancy holds; the "cluster harder" class stays foreclosed. Evidence: results/research/bnbusdt_trade_anatomy_2026_06_27/anatomy_summary.json.

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

### F-031 · Governance caught an overclaim before repository contamination (Program-4 rollup E-001E)
- Type:          GOVERNANCE
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-06-17
- Revalidate-by: 2026-09-15
- Evidence:      src/research/regime_conditioning.py (the pure `_consumer_verdict` rollup helper; `all_insufficient` guard precedes the n_harmful check); docs/governance/EPISTEMIC_INTEGRITY.md (E-001E invariant, sanctioned-precedence clause, mandatory phrase, pre-registration ritual, self-audit §9); tests/governance/test_epistemic_invariants.py (TestEpistemicInvariantE001E::test_red_green_guard_proof — behavioral red→green proof)
- Supersedes:    —
- Reversal:      —
- Owner:         claude
- Note:          Program 4 (regime_conditioning v1.1) originally emitted REGIME_HARMFUL for all-underpowered spine cells (all gate verdicts = INSUFFICIENT, n<30). A human reviewer caught the semantic inflation. The rollup was corrected (v1.1→v1.2): all_insufficient guard added before the n_harmful check. A correction that occurs BEFORE registration is evidence the governance system succeeded — not a failure. The E-001E rollup invariant, the mandatory phrase ("Caught me overclaiming; I owe you a correction."), and the pre-registration ritual were formalized as Program E-001 in response. RECURSIVE SELF-CORRECTION (2026-06-18): the FIRST generation of E-001's own invariant tests were themselves found to overclaim — E-001A/E-001E were substring-grep (not behavioral) and two advisory tests could never fail yet were tabled as "Test asserts" (E-001A + E-001F by the program's own taxonomy). Corrected: the per-consumer rollup was extracted to the pure `_consumer_verdict` helper and the A/E tests rewritten as behavioral with a permanent red→green proof (removing the guard turns the suite red); advisory tests relabeled honestly. The loop: governance caught an overclaim → the governance tests later overclaimed → the tests audited themselves → behavioral enforcement was added. E-001 became subject to E-001. The realistic claim is that the program creates SHORTER CORRECTION LOOPS, not total prevention. The program stays OPEN, not "finished."

### F-030 · Contemporaneous volatility-regime LEVEL conditioning is economically non-consumable in spot directional architectures
- Type:          ECONOMIC
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-17
- Revalidate-by: 2026-09-15
- Evidence:      results/research/regime/regime_conditioning.json + docs/research-readiness/program-4-nondirectional-preregistration.md (Program 4 = regime-conditioned consumption; 3×3 cross-matrix {expansion_breakout,mean_reversion,spine}×{C,N,E} over crypto-majors, intrabar_fixed+12bps, IS+70/30 OOS + cohort BH + a label-permutation null + a lagged-regime persistence control). Calibration PASSED (BNBUSDT H_atr=0.885027, H_ret=0.526847 — reproduces the vol-memory prior). **0 REGIME_EXPLOITABLE** cells anywhere. WELL-POWERED toy arm (cells n=3.7k–35k): best regime always 'E' beats random/shuffled nulls (p_label≈0.0025) yet expectancy stays NEGATIVE everywhere (E[R]≈−0.14…−0.35, every cell REJECT gate2); mean_reversion ETH/SOL = REGIME_REDUNDANT (S_lagged≈/≥S_real → persistence, not skill). Spine arm INSUFFICIENT (all cells n=1–11 < 30; throughput-starved per F-019/F-022) — no spine conclusion. Code: src/interpreters/regime_observer.py (trailing-window labeler, NOT global-rank — guards F-029), src/research/regime_conditioning.py (reuses forward_walk + QualificationGate verbatim); tests tests/test_regime_observer.py + tests/test_regime_conditioning.py (15 green). DETERMINISM: byte-identical replay 2026-06-17 — `regime_conditioning.json` reproduces sha256=288abd6c3e36e38b3edeeaa9091f16e4d633f53f4eff6c8c664bdab5d8386fc6 across two independent runs (deterministic body, no wall-clock).
- Supersedes:    —
- Reversal:      "Volatility memory (H_atr=0.885) is the highest-prior non-directional edge — conditioning a directional strategy on the vol regime should improve it" -> "It does not. Contemporaneous regime-LEVEL conditioning is statistically informative (best regime beats nulls, p≈0.0025) but economically worthless — the best regime's expectancy never crosses 0 (Authority-Ladder Level 1, not Level 2); 2 cells are pure persistence (REDUNDANT). The spine arm is underpowered, not harmful (no conclusion). Vol is predictable but not consumable in a spot long/short architecture — the binding constraint is the EXECUTION MODEL / entry information, not regime predictability."
- Owner:         claude
- Note:          FIRST falsification in the NON-DIRECTIONAL ontology (Program 1 was directional). SCOPE = the regime-LEVEL channel; it is conclusive on the powered toys (contemporaneous regime = best-case predictor under H=0.885, so a noisier P^H forecast cannot rescue it). The TRANSITION-forecast channel (forward Markov P^H — anticipating a regime CHANGE) is a genuinely different information channel and is UNTESTED → Program 4b (separate pre-registration), NOT a parameter pass on Program 4. Self-review correction baked in: the run's rollup originally printed the spine as REGIME_HARMFUL, but all spine cells are gate-INSUFFICIENT (n<30) so that was a noise artifact — the harness was fixed (conditioning v1.2: all-underpowered consumer → REGIME_INSUFFICIENT) and re-run; "spine is harmed" is NOT claimed.

### F-032 · Cross-sectional dispersion (relative-value, market-neutral) on crypto majors is NOT monetizable net of costs
- Type:          ECONOMIC
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-18
- Revalidate-by: 2026-09-16
- Evidence:      results/research/cross_sectional_report.json + docs/research-readiness/program-5-cross-sectional-preregistration.md (Program 5 = cross-sectional relative-value; rank 6 crypto majors {BNB,BTC,DOGE,ETH,SOL,XRP} each rebalance, long top-2 / short bottom-2 equal-weight market-neutral, hold H bars, net of 12bps/leg; M15 close-to-close, IS+70/30 OOS + cohort BH + 5 controls incl. equal_weight_market & reversed & shuffled). **0 PROMOTE / 0 REDUNDANT — all 5 interpreters REJECT, WELL-POWERED** (n=722–8,758 non-overlapping rebalances; not INSUFFICIENT). Cross-sectional MOMENTUM actively *loses* (xs_mom_96_16 E=−0.00509, PF=0.335, p=1.0; the `reversed` control is the lone positive E=+0.00031 → a faint short-horizon cross-sectional REVERSAL tilt). The single positive interpreter (xs_rev_32_32: E=+0.000637, PF=1.111, OOS=+0.00164>IS) FAILS gate-4 because its own LONG LEG beats the market-neutral spread (long_only E=+0.000756, baseline_delta=−0.000119) and is statistically insignificant (p=0.569) → the faint sign is a long-leg/beta artifact, NOT dispersion alpha. Code src/research/cross_sectional.py (panel inner-join + 5 weight formers + qualify; reuses qualification.permutation_p_value + benjamini_hochberg + costs.DEFAULT_ROUND_TRIP_BPS VERBATIM — no trade geometry); driver scripts/research/qualify_cross_sectional.py; config configs/research/research_config_cross_sectional.json; tests tests/research/test_cross_sectional.py (9 green: no-lookahead, alignment fail-fast, control sanity, cost monotonicity, verdict ladder, determinism). DETERMINISM: byte-identical replay 2026-06-18 (config_sha256=00687f8b…; deterministic body, no wall-clock).
- Supersedes:    —
- Reversal:      "Every prior null (F-019…F-031) was per-instrument DIRECTIONAL; maybe a market-neutral cross-sectional spread (relative strength between coins) monetizes the dispersion" -> "It does not on crypto majors net of costs. Cross-sectional momentum loses outright (PF 0.335); the only positive cell is a faint reversal tilt that is a long-leg/beta artifact (loses to long_only) and insignificant (p=0.57). Market-neutral dispersion carries no monetizable, beta-orthogonal edge — first falsification on the PANEL (cross-sectional) axis, extending the sweep beyond the per-instrument frame."
- Owner:         claude
- Note:          FIRST cross-sectional (panel) falsification — distinct from F-019…F-031 (all single-name). The object tested was DISPERSION (momentum/reversal/inverse-vol are interpreters of it), so this kills the dispersion-monetizability question for these interpreters, not one indicator. The economic signature mirrors F-030's Authority-Ladder Level-1-not-2: a statistically-detectable cross-sectional reversal sign exists but is economically worthless after costs and is beta-redundant. Per the §6.5 Authority Ladder this earns research authority only; NO `CrossSectional` style layer is built on a single null. Scope = M15 spot crypto majors; the FX/metals + perps/funding/carry axes stay UNTOUCHED-FRONTIER (perps data-blocked).
- 2026-06-18 input-availability update (NOT a finding change; no edge claim): the carry/basis axis is **partially un-blocked** — `scripts/data/fetch_perp_funding.py` + `src/inout/perp_funding_fetcher.py` now acquire Binance perp **funding-rate** (8h) and **premium-index/basis** (M15) full history into `data/perp/`, byte-identical to spot timestamps (verified 100% basis↔spot overlap on BNBUSDT). **Funding history: UNBLOCKED · Basis history: UNBLOCKED · Open interest: STILL BLOCKED** (`openInterestHist` ~30-day retention). This changes INPUT AVAILABILITY only; per the §6.5 Authority Ladder no carry/basis edge is asserted until a carry/basis interpreter runs through the M4 gate. **Resolved 2026-06-18 by F-033** (the interpreter ran → null).

### F-033 · Carry/basis is NOT an informative signal for cross-sectional spot dispersion on crypto majors
- Type:          ECONOMIC
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-18
- Revalidate-by: 2026-09-16
- Evidence:      results/research/carry_report.json + docs/research-readiness/program-6-carry-basis-preregistration.md (Program 6 = carry/basis as a SIGNAL on cross-sectional SPOT dispersion: rank 6 crypto majors {BNB,BTC,DOGE,ETH,SOL,XRP} by trailing-mean perp funding-rate / premium-index at rebalance t, long bottom-2 / short top-2 equal-weight market-neutral, hold H, measure the long-short SPOT close-to-close spread net of 12bps/leg; funding forward-filled 8h→M15 (last settlement ≤ t, no-lookahead), basis native M15; IS+70/30 OOS + cohort BH + the 5 Program-5 controls). **0 PROMOTE / 0 REDUNDANT — all 8 interpreters REJECT, WELL-POWERED** (n=722–4,373 non-overlapping rebalances; not INSUFFICIENT). Every cell is *economically* negative AND *statistically* insignificant: E(net) ∈ [−0.00319, −0.00158], PF ∈ [0.55, 0.82], p ∈ [0.76, 1.00] — both signs of both signals (carry/carry_inv/basis/basis_inv) at L∈{96,672}/H∈{16,96}. Every interpreter loses to a control (`equal_weight_market` or `long_only`) at gate-4 — the carry/basis-sorted spread is *worse* than just holding the basket, so it does not even reach Authority-Ladder Level-1 *information* (unlike F-032's xs_rev which at least had a positive-but-beta-redundant cell). Reuses the Program-5 kernel VERBATIM (`research.cross_sectional` Panel+funding/basis side-channels + `scores` carry/basis kinds; `qualify` / `permutation_p_value` / `benjamini_hochberg` / `DEFAULT_ROUND_TRIP_BPS` UNCHANGED — Program 5 stays byte-identical, 9 tests green). Driver scripts/research/qualify_carry.py; config configs/research/research_config_carry.json; tests tests/research/test_carry.py (6 green: ffill no-lookahead, basis alignment, score signs, Panel backward-compat, missing-corpus fail-fast, determinism). DETERMINISM: byte-identical replay 2026-06-18 (config_sha256=00687f8b…; deterministic body, no wall-clock; 70,080 rebalance bars).
- Supersedes:    —
- Reversal:      "Perps were the advisors' highest-rated untested axis; now that funding/basis are acquired (the F-032 input-availability unblock), maybe a coin's funding/basis rank predicts its forward cross-sectional spot return" -> "It does not on crypto majors net of costs. All 8 carry/basis interpreters (both signs) are net-negative, sub-1 PF, insignificant, and each loses to the market-basket / long-only control. Carry/basis is not an informative cross-sectional SPOT-dispersion signal — the first non-null-data axis to be tested and falsified, extending F-019…F-032 onto the carry/basis information source."
- Owner:         claude
- Note:          SCOPE — this falsifies carry/basis as a *ranking signal for the spot-dispersion payoff*; it does NOT test the literal carry-HARVEST payoff (holding the perp to earn funding ± basis convergence), which is a DIFFERENT return construction (Program 6b — built + run, see F-034). Open interest remains data-blocked (Program 7, deferred). Acquisition layer (the data) stays a permanent asset regardless — the null is about the signal's economic content, not the corpus (which is complete: 6×{2,190 funding / 70,080 basis}, coverage 1.0000, frozen). Per §6.5 this earns research authority only. The pre-registered prior (REJECT/REDUNDANT expected) was recorded BEFORE the run — a clean confirmation, not a rationalized null.

### F-034 · Carry HARVEST does not clear costs on crypto majors — funding income is real but economically negligible vs turnover
- Type:          ECONOMIC
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-18
- Revalidate-by: 2026-09-16
- Evidence:      results/research/harvest_report.json + docs/research-readiness/program-6b-carry-harvest-preregistration.md (Program 6b = the carry CASHFLOW payoff, distinct from F-033's signal: long low-funding / short high-funding equal-weight market-neutral PERP basket, hold H, return = perp price move [≈ spot + premium-index change ⇒ basis convergence] + funding accrued over (t,t+H] − 12bps/leg; funding accrued from DISCRETE 8h settlements, no-lookahead). **0 PROMOTE — all 4 tradeable `harvest_full` REJECT** (n=104–729, WELL-POWERED), each losing to the `cash` or `reversed` control: E(net) ∈ [−0.00845, −0.00260], PF 0.56–0.83, p 0.84–1.00. The diagnostic appendix is the key economic content: **funding income is structurally POSITIVE but tiny** (pre-cost +0.000125…+0.000608 per rebalance ≈ +1…+6 bps) — *smaller than the ~24 bps/rebalance round-trip cost* — so all 4 funding-only twins are `DIAGNOSTIC_NEGATIVE` (the cashflow does not even cover its own turnover), and adding the price/basis term makes the full trade more negative still. The lowest-turnover cell tested (H=672/1w, the largest pre-cost income) still REJECTs (PF 0.83) — the low-turnover end is inside the frozen grid and does not rescue it. AUTHORITY SEPARATION held: funding-only (a PnL decomposition, not a trade) could ONLY receive DIAGNOSTIC_* and was excluded from the BH cohort + the promotion surface (Refinement 1). Reuses the Program-5/6 kernel VERBATIM (`harvest_net_series` + `qualify_harvest` add the `cash` benchmark via a defaulted `_evaluate(control_names, market_key)`; `_finalize` / permutation / BH UNCHANGED — Programs 5 & 6 stay byte-identical, 15 tests green). Driver scripts/research/qualify_harvest.py; config configs/research/research_config_harvest.json; tests tests/research/test_harvest.py (7 green: discrete settle, accrual no-lookahead boundary, positive income, decomposition identity, cash control, diagnostic-only authority, determinism). DETERMINISM: byte-identical replay 2026-06-18 (config_sha256=00687f8b…).
- Supersedes:    —
- Reversal:      "F-033 killed carry as a SIGNAL but not as a CASHFLOW — maybe the funding stream a market-neutral perp basket accrues (± basis convergence) exceeds costs" -> "It does not on crypto majors. The funding income is real and positive but economically negligible — smaller than the round-trip cost — so the harvest is net-negative even before the price/basis drag, across 1d/3d/1w holds. Carry harvest as constructed does not clear costs."
- Owner:         claude
- Note:          SCOPE — the kill is for the harvest *as tested* (rebalanced long-low/short-high perp basket, flat 12bps/leg, H∈{96,288,672}); the diagnostic shows funding income EXISTS but is ~1–6 bps vs ~24 bps turnover. This does NOT claim funding is worthless in the abstract; a lower-turnover / netting cash-and-carry construction is a DIFFERENT trade — but pursuing it now is forbidden parameter archaeology under the F-033/F-034 STOP discipline (any reopen needs a fresh structural thesis + pre-registration, not an H/cost tweak). Open interest (Program 7) and FX/metals stay deferred — NOT automatic. The perp data corpus remains a permanent asset. Per §6.5 research authority only. The pre-registered prior ("funding income positive, overwhelmed by cost/price drag") was recorded BEFORE the run — confirmed (and sharpened: it fails to clear cost even before the price drag).

### F-035 · The entry-information null generalizes from crypto to FX majors — first non-crypto asset-class test
- Type:          ECONOMIC
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-19
- Revalidate-by: 2026-09-17
- Evidence:      results/research/qualification_fx_metals/qualify_fx_metals.json (DETERMINISTIC body sha256=48a0193c…, byte-identical 2-run replay 2026-06-19). First cross-ASSET-CLASS run of the existing hypothesis pool through the M4 gate — the same VERBATIM machinery as qualify_majors (intrabar_fixed, 12bps round-trip, alpha=0.05, n_perm=2000), re-scoped to **5 FX majors** [EURUSD, AUDUSD, EURCAD, GBPUSD, USDJPY], 2yr M15 freshly fetched via MT5 (49.5k bars each, dataset_integrity APPROVE/WARN 0.00% missing). **0 PROMOTE.** Toy family WELL-POWERED and decisively negative: `expansion_breakout` ALL REJECT (per-inst n=7,711–8,915, PF 0.015–0.076, E(net) −1.73…−2.80R, p 0.59–1.00); `mean_reversion` ALL REJECT (n=13,710–17,103, PF 0.024–0.102, E(net) −1.52…−2.53R, p=0.0005 = significantly NEGATIVE, i.e. reliably worse than control). Spine arm INSUFFICIENT per-instrument (n=2–8 trades — corroborates F-029: the spine barely fires on FX), POOLED n=30 REJECT (E −5.99R). So no toy, conditional, or spine signal earns promotion on FX — the F-019…F-028 entry-information null (built on crypto-directional) holds on a NEW asset class. Driver scripts/research/qualify_fx_metals.py; configs configs/research/research_config_fx_metals.json + research_config_spine_fx_metals.json (clones of the *_majors pair, universe re-scoped); fetch layer src/inout/mt5_candle_fetcher.py + scripts/data/fetch_candles_mt5.py.
- Supersedes:    —
- Reversal:      "The directional/entry-info null (F-019…F-028) might be a crypto-specific artifact — a different asset class (FX) could carry the edge the crypto majors lack" -> "It is not crypto-specific. On 5 FX majors (2yr M15), the same toy pool + spine through the same M4 gate produces 0 PROMOTE, well-powered — the entry-information bottleneck generalizes across asset classes."
- Owner:         claude
- Note:          COST CAVEAT (E-001 honesty) — the 12bps round-trip was kept identical to the crypto run for comparability, but it is UNREALISTICALLY HARSH for FX: it equals 1.8–2.5× the median FX M15 bar range (EURUSD 0.048%, USDJPY 0.066%), versus a tiny fraction of a crypto bar. So the −1.5…−2.8R magnitude is COST-DOMINATED, not a measure of raw signal — this extends F-025's cost-domination theme to FX, where it is even more acute (tiny ATR). The DIRECTION null is nonetheless robust to the cost choice: PF 0.02–0.10 is so far below 1.0 that even a 0bps rerun would not cross the gate, and mean_reversion is significantly negative — a realistic-FX-cost rerun (≈1bps) would lift expectancy toward −1R but not into promotion, so the "asset-appropriate cost" follow-up is NOT a near-miss and was not run. SCOPE — FX majors only (one MT5 broker, one timeframe); XAUUSD/metals EXCLUDED this pass (its 26h holiday gap REJECTs the FX-tuned dataset_integrity gap gate — the Stage-2 metals/holiday calendar, not corrupt data). Per §6.5 research authority only. Pre-registration = the two fixed research configs written before the run; existing hypotheses reused, NO new ones.

---

### F-036 · zone_gate top_k / cluster knobs are TUNABLE but INERT — ΔG001 ≡ 0 (mechanism CORRECTED; live-path now tested)
- Type:          ECONOMIC
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-24
- Revalidate-by: 2026-09-22
- Evidence:      scripts/research/qualify_zone_topk.py (driver; results/research/zone_topk_sweep/zone_topk_sweep.json, DETERMINISTIC body sha256=0e8221da…). Measures ΔG001 of the just-shipped `engine_runner.zone_gate` config knobs (see [[project_zone_gate_topk_config]]). The zone registry is LIVE (`models/zone_registry.json`, 8 zones, total_weight 139,942 ≫ underpowered floor 50), so the knob is NOT dormant-by-emptiness. Sweep `top_k ∈ {1,2,3,5,8}` (cluster_min_n=2, cluster_spread_max=0.15) × BNB/ETH/BTC/SOL, governing intrabar_touch (Layer 1 = the spine's own goal_report) + the VERBATIM M4 gate (Layer 2, intrabar_fixed/12bps/2000perm/alpha 0.05 vs always_long+random controls). RESULT: spine entry sets are **byte-identical at every top_k** ⇒ **ΔG001 ≡ 0 exactly** (Δexpectancy_r = +0.0000 for every cell × instrument; identical trade counts BNB 13 / ETH 5 / BTC 5 / SOL 7). M4: **0 PROMOTE** — per-instrument INSUFFICIENT (n<30); POOLED n=30, E(net)=−0.399, REJECT — identical to F-019's spine arm. V0 self-check byte-identical (the get_prod_section injection is neutral at defaults).

  **CORRECTION (2026-06-25, E-001 — "caught me overclaiming"):** the original mechanism claim here — *"the zone cluster score enters Fusion at weight 0.2 and flips ZERO decisions … the same perfect-no-op as the EMA gate"* — is **WITHDRAWN as an overclaim**. The follow-up diagnosis (`scripts/research/diagnose_zone_inertness.py`) found the engine_runner **FUSION GATE is DISABLED in the backtest harness**: `.env` sets `BACKTEST_ENGINE_GATE=0`, and only `backtest_v2.py` honors that flag (the live path does **not**). So in this entire research corpus the 4-engine fusion (CRT/Gaussian/zone/RR) + DecisionEngine veto **never runs** — backtest entries are produced by the **CRT state machine alone**. `top_k` is therefore inert in the backtest **trivially** (nothing in fusion executes), **NOT** because zone is non-pivotal in a live-equivalent fusion. Probe (12k BNB candles): gate-ON → the lone CRT candidate is REJECTed (0 trades); gate-OFF → 1 trade — i.e. the gate is highly consequential when on. The **ΔG001≡0-in-backtest headline and the tunability-not-authority verdict still stand**, but the fusion-mechanism attribution does not, and **live-path zone pivotality is UNTESTED**. Stage B not entered (moot under the corpus correction). See F-037 for the corpus-scope finding.

  **UPDATE (2026-06-25) — live-path pivotality now TESTED (gate-ON ablation), confidence restored Possible→Likely:** re-ran the ablation with `BACKTEST_ENGINE_GATE=1` (`results/research/zone_inertness_gateon/`, body sha in manifest) so the 4-engine fusion actually runs (live-equivalent spine: BNB 11 / ETH 4 / BTC 5 / SOL 6). Sweeping `weight_zone_gate ∈ {0.0,0.2,0.4,0.6}` × `bitnet_zone_threshold ∈ {0.0,0.25,0.5}` → **every cell byte-identical** ⇒ **zone is non-pivotal on the REAL fusion spine** (removing it, tripling its weight, or forcing its vote on/off changes zero entries). MECHANISM (Phase-2 audit, 13 bars, real scores): zone is **NOT weak** (mean 0.608, median 0.718, **+0.358 above** the 0.25 threshold, ≥0.25 on 85% of bars) and **NOT under-weighted** (3× weight = no change) → the cause is **redundancy / decision-domination** — zone is a near-constant strong "yes" vote that never moves the fused score across the DecisionEngine cut; the real fusion vetoes (CRT 13→11 etc.) are **zone-independent** (CRT/Gaussian/RR/decision drive them). Non-pivotality is byte-exact/deterministic (robust to tiny N) → Likely. Side flag (untested): `gaussian`≡`rr` audit mean 0.7468 — possible rr_fusion coupling, separate question.
- Supersedes:    —
- Reversal:      "Making the zone top-k tunable might let a non-default value improve the goal (G001)" -> "top_k is config-TUNABLE but economically INERT. In the CRT-only backtest corpus ΔG001≡0 trivially (fusion gate off); and on the REAL gate-ON fusion spine zone is MEASURED non-pivotal (redundant/decision-dominated, not weak, not under-weighted — UPDATE above). The migration grants tunability, never authority (§6.5) — default top_k=3 stays; a non-default value is unjustified. The interim 'fusion weight 0.2 flips no decision' claim was an overclaim while the gate was off, since re-measured gate-ON and now SUPPORTED."
- Owner:         claude
- Note:          Extends F-021 (zone-selection-beyond-session null: ZONE produced 0 rejects) and F-019 (spine INSUFFICIENT, pooled n=30 REJECT) to the explicit config-knob level. This is the §6.5 Authority-Ladder discipline closing the loop on a config migration: a BEHAVIORAL knob earned CONFIG_DRIVEN tunability, then was measured against G001 and earned NO authority. A clean 0-PROMOTE / ΔG001≡0 is a successful experiment (high knowledge-ROI null, §6.1), not a failure. Research authority only. SCOPE per F-037: measured on the CRT-only research spine (fusion gate off by design).

---

### F-037 · The research "spine" is CRT-only by design — the 4-engine fusion gate is OFF in backtests
- Type:          ARCHITECTURE
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-06-25
- Revalidate-by: 2026-12-22
- Evidence:      Direct probe (instrumented `EngineRunner.run` call-counter on the spine-adapter backtest) → `run()` is called 0 times; root cause `BACKTEST_ENGINE_GATE=0` is set by `.env` (confirmed: NOT in the shell env; one line in `.env`; loaded via dotenv with override=False) and is honored ONLY by `src/runtime/backtest_v2.py:1838` (the live path `live_engine_hook` does NOT read it). So every research backtest harvests the **CRT state-machine** entries; the `EngineRunner` 4-engine fusion (CRT/Gaussian/ZoneGate/RR) + `DecisionEngine` veto NEVER RUNS in research. Gate-ON vs gate-OFF full-history impact (results/research/_gate_impact/summary.json): the fusion veto is real but modest — BNB 13→11 trades, SOL 7→6 (entries_changed=True both); gate-OFF reproduces the F-036/F-019 corpus EXACTLY (13/7). USER-CLASSIFIED **INTENDED** (CRT-spine isolation), not a defect → resolution was DOC-side: corrected the `spine_signal_source.py` docstring (was claiming it runs the full CRT→Fusion→Decision→Ultron stack) to state the CRT-only scope.
- Supersedes:    —
- Reversal:      "The research spine (spine_signal_source.py / SpineHypothesis) measures the full production CRT→Fusion→RegimeGovernor→Decision→Ultron stack, as its docstring claimed" -> "It measures the CRT state machine only; the 4-engine fusion veto is gated OFF in backtest by .env (BACKTEST_ENGINE_GATE=0), by design. The full-fusion spine is a separate gate-ON object (~14% fewer trades)."
- Owner:         claude
- Note:          Scope-correction, NOT a conclusion reversal: the fusion gate REMOVES trades (more restrictive), so the gate-ON spine is even smaller-N → the F-019…F-036 entry-information null is unaffected in direction (still INSUFFICIENT/REJECT). What changes is the SCOPE LABEL on the corpus: "the spine" = CRT-only. This corrected F-036's withdrawn fusion-mechanism overclaim (E-001). The one-off gate-ON zone ablation WAS run (`results/research/zone_inertness_gateon/`): the gate runs (audit non-empty, EngineRunner.run called) and vetoes 2/1 CRT entries, but those vetoes are **zone-independent** (removing/tripling zone weight + threshold sweeps all byte-identical) → see F-036 UPDATE. The research default is UNCHANGED (CRT-only by design); gate-ON is a separate live-equivalent lens, not the corpus default.

---

### F-038 · In the gate-ON fusion the "RR" engine is a GAUSSIAN DUPLICATE — rr_fusion degrades to gaussian on ~all candidate bars [FIX SHIPPED — rr_fusion disabled 2026-06-26]
- Type:          ARCHITECTURE
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-06-25
- Revalidate-by: 2026-12-22
- Evidence:      Instrumented gate-ON full-history probe (FusionEngine.compute + RRFusionLayer.score_dict counters) across BNB/ETH/BTC/SOL: **`rr_score == gaussian_score` EXACTLY on 26/26 fusion bars** (BNB 11/11, ETH 4/4, BTC 5/5, SOL 6/6; per-bar identical to 1e-9, Pearson r=1.0 — NOT the r≈0 an LLM-advisor claimed). Code chain (committed source = the reproducible basis for this architectural claim): `src/config_layer/rr/rr_fusion.py:35` (`_passthrough()` returns `final_score = gaussian_score`; the drift/low-confidence return paths at `:142`/`:174`) and `src/core/engine_runner.py:694` (the `final_score` adoption into `rr_result["score"]` at `:694-701`) — and because `engine_runner.rr_fusion.enabled=true`, the **base RREngine score from `self.rr.compute()` is discarded**. The passthrough fires via two graceful-degradation paths: **`bypassed_low_confidence` 23/26** (the rr_fusion NanoInference model's confidence is below `rr_model.confidence_bypass_threshold=0.3`, so it returns gaussian) + **`drift_detected` 3/26** (`disp_strength > rr_model.drift_threshold=1.5` on displacement/execution bars). So the rr_fusion layer NEVER contributes an independent RR prediction in this corpus. NET: the nominal "4-engine" fusion (CRT/Gaussian/ZoneGate/RR) carries only ~2.5 INDEPENDENT signals — the gaussian score occupies BOTH the gaussian and rr slots, so its effective fusion weight is `weight_gaussian + weight_rr` (0.2+0.2 under the active scalar profile; regime profiles may differ), against CRT (0.4) and zone (0.2). Driver: instrumented probes (probe outputs gitignored, non-load-bearing — the architectural mechanism is the committed code cited above, not the probe artifacts).
- Supersedes:    —
- Reversal:      "The 4-engine fusion combines 4 independent engine signals (CRT/Gaussian/ZoneGate/RR)" -> "Three independent signals at most: the RR slot is a gaussian DUPLICATE (rr_fusion low-confidence-bypass + drift passthrough returns the gaussian score on 100% of measured fusion bars; the base RR engine is discarded). Gaussian is effectively double-weighted."
- Owner:         claude
- Note:          Compounds F-036: the fused decision is dominated by CRT + a DOUBLED, near-constant gaussian (~0.883 on active bars), which is WHY zone (and rr) are non-pivotal. **ROOT CAUSE CONFIRMED = DEFECT (not intended graceful-degradation)** [2026-06-25, instrumented NanoInferenceEngine.predict probe, BNB gate-ON]: the rr_fusion model expects **38 features** (`len(W)=38`, 11 price-features zeroed at train → ~27 real expected), but the inference path `score_dict()` → `_empty_canonical_features()` populates **only 2–3 features** (`retest_depth/body_ratio/disp_strength`) and zeros the rest. Those ~24 artificially-zeroed features sit far outside their training distribution, so the Mahalanobis `d_sq` saturates (→ `_MAHAL_CLIP`) and `confidence = exp(-0.5·d_sq) ≈ 1e-88…1e-66` — astronomically below `confidence_bypass_threshold=0.3` → **bypass on 100% of bars**. The model is STARVED of inputs, not genuinely unconfident; the "advisory degradation" masks a feature-interface bug (engine_runner passes 3 scalars to rr_fusion; the model needs the full canonical vector that the other engines already receive in `input_data`). FIX DIRECTION (code, needs owner go-ahead + parity/validation): feed rr_fusion the full canonical feature vector (or disable rr_fusion to restore the base RREngine's independent signal). SCOPE: gate-ON backtest, crypto majors, full history (n=26 fusion bars, small); live-path unverified (rr_fusion runs identically live). Corrects an external "r=0.005 / independent" claim. Separate untested observation: the gaussian heuristic score is near-constant ~0.883 on active bars (non-discriminating) — own evidence needed before any finding. **Evidence re-pointed to committed `src/` citations 2026-06-26** (E-001 reproducibility — the original `config_layer/...` / `core/...` package-relative paths did not resolve under the evidence-link test's `src/`-rooted resolver, and the gitignored `results/research/_rr_probe2` probe outputs are non-reproducible; conclusion UNCHANGED).

  **FIX A SHIPPED — configurable full-vector, but NECESSARY-yet-INSUFFICIENT [2026-06-26]:** added `engine_runner.rr_fusion.full_feature_vector` (bool, default **false** = byte-identical legacy path; `src/core/engine_runner.py` routes through the existing `RRFusionLayer.score()` full-vector path when true, instead of the 3-feature `score_dict()` stub). VALIDATED gate-ON: default-off reproduces the baseline ledgers byte-identically (BNB 11 `aab9783b`, SOL 6 `a6f795fb`); full-mode (`true`) genuinely feeds the model **28–33 nonzero features** (vs 2–3) and lifts confidence by **~60 orders of magnitude** (1e-88…1e-66 → 2.3e-25…**5.0e-5**) — BUT max confidence 5e-5 is **still ≪ `confidence_bypass_threshold=0.3`**, so the model STILL bypasses to gaussian on 100% of bars → ledgers byte-identical to default, rr still == gaussian. CONCLUSION: the defect has TWO layers — (1) feature starvation [Fix A resolves the interface], (2) the rr_fusion model is **out-of-distribution / mis-calibrated** on live bars even when fed real features [UNRESOLVED]. Feeding the full vector is necessary but not sufficient; making rr contribute a real independent signal needs model **recalibration/retrain** (or a drastically lower bypass threshold, which would admit ~zero-confidence noise) — **or disable rr_fusion (the earlier "Fix B") to restore the base RREngine**. Knob default stays `false` (full mode changes nothing until the model is fixed). Test: `tests/test_rr_fusion_full_vector.py` (3 green). NOTE: rr_fusion has BOTH `score()` (full-vector, was unused) and `score_dict()` (3-feature stub, was wired) — Fix A just routes to the former.

  **FIX B SHIPPED — rr_fusion disabled on the active config [2026-06-26]:** flipped `engine_runner.rr_fusion.enabled` to `false` in `configs/production/v2_multi_2026_04.json` (the file `ACTIVE_VERSION` points to). Per CLAUDE.md §6.5 Authority Ladder, rr_fusion never demonstrated ΔG001 improvement and the active behavior was a known integrity defect (silent Gaussian duplication), so removal is the conservative/evidence-aligned action, not Option-B retraining-first. Code re-verified directly against current `patch` branch (not from memory): `src/core/engine_runner.py:341` defaults `self.rr_fusion = None`; `RRFusionLayer` is only *constructed* if `_cfg_require(rr_fusion_cfg, "enabled", ...)` is `True` (`:349`) — so with `enabled=false`, `self.rr_fusion` stays `None` for the runner's lifetime (no load attempt, no race). `rr_result = self.rr.compute(input_data)` (`:678`, genuine base `RREngine`) is unconditional; the guard `if self.rr_fusion and self.rr_fusion.is_loaded:` (`:682`) short-circuits `False` on `None`, so the fusion-mutation block (`:683-725`, including the `"rr_fusion"` metadata-key injection at `:713-716`) never executes — `engine_results["rr"]` is structurally guaranteed byte-identical to the base `RREngine` output, not just behaviorally likely. Grep-verified no downstream consumer assumes `engine_results["rr"]["rr_fusion"]` exists (`src/core/collector.py:92` and `src/control_plane/dashboard_api.py:234` both read *different* dicts via `.get(..., default)`, already safe). Config change is hash-neutral: `rr_fusion` lives under top-level `engine_runner`, not the literal `params` dict that `scripts/maintenance/_compute_hash.py` hashes (`retest_depth_max`/`retest_atr_depth_fraction`/`body_ratio_min`/`atr_multiplier_min`/`expansion_atr_min_distance` only) — no rehash performed or required. New regression test `tests/test_engine_runner_rr_fusion.py::test_rr_fusion_disabled_is_base_rr_identity` asserts full-object identity (`runner.fusion.last["rr"] == base_rr`, not just `["score"]`) so a future change mutating `confidence`/`reason`/metadata without touching `score` would still be caught. Also fixed a stale, unrelated test-harness gap discovered en route: `_build_runner()` in the same test file never set `_rr_fusion_full_vector`, causing `test_rr_fusion_applies_score_before_fusion` to silently mis-fire via an `AttributeError`-triggered fallback (masking its actual intent) — added the missing attribute; all 6 tests in the file now pass for their stated reasons. Fusion now runs CRT + Gaussian + ZoneGate + base RREngine = an honest (if still only ~3-independent-signal, since F-036 found zone non-pivotal/redundant) stack, with no silent Gaussian double-weighting. **Confidence raised to Certain** (was Likely) — the mechanism is now both proven AND remediated, with a structural (not just behavioral) guarantee. Option-B retrain/recalibration (model validation script, schema-version guard on `NanoInferenceEngine.predict`'s silent truncation at `rr_pattern_miner.py:309-310`, `promotion_manager`-gated re-promotion) remains open as a separate, non-blocking research track — see Funding Ledger.

  **CORRECTED 2026-06-27 (deployment-state, Documentation Drift Protocol worked example):** the Fix-B parenthetical "(the file `ACTIVE_VERSION` points to)" was DOC_DRIFT against committed reality. At HEAD `1a8a260`, `configs/production/ACTIVE_VERSION` = `v2_multi_2026_04 - deepdeektry`, which the resolver (`src/config_layer/production_config.py:60`→`:116`, `Path(registry_dir)/f"{version}.json"`) loads as `v2_multi_2026_04 - deepdeektry.json` where `rr_fusion.enabled: true` — so the Fix-B edit landed on `v2_multi_2026_04.json` (`enabled:false`) but that file was NOT the active one at HEAD; **the fix was code-present, not deployed**. It becomes deployed only with `ACTIVE_VERSION=v2_multi_2026_04` (the working-tree value, matching F-016) committed. Verification: `static`+`runtime` (`git show HEAD:configs/production/ACTIVE_VERSION` vs working tree; `enabled` read at `v2_multi_2026_04.json:34`=false vs `… - deepdeektry.json:50`=true). The F-038 *conclusion* (RR=gaussian duplicate; disable is the fix) is UNCHANGED — only the "shipped/deployed" claim is corrected. RESIDUAL `TruthConflict` **RESOLVED 2026-06-27** (user-approved archive): the deepdeektry variant (`enabled:true`/`gaussian_impl:ml`) was found NON-LOADABLE on the patch engine (its `governance` section lacks the required `promotion_margin` key → `model_registry.from_prod_config` KeyError) and was the stale pin of the default research config (`research_config_spine.json`). Verified the canonical `v2_multi_2026_04` runs the BNBUSDT spine clean (13 entries), repointed `research_config_spine.json` → canonical, and archived the deepdeektry file to `configs/production/v2_multi_2026_04_deepdeektry_archived_20260627_160227.json`. Split-brain removed; one runtime config truth (`v2_multi_2026_04.json`, `enabled:false`). Audit row: [`docs/governance/finding_dependency_audit.md`](governance/finding_dependency_audit.md) Audit Log.

---

### F-039 · The L3 dataset-integrity pre-flight is `backtest_v2`-only; every other CandleLoader path relies solely on the inline L1/L2 backstop
- Type:          ARCHITECTURE
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-06-26
- Revalidate-by: 2026-09-24
- Evidence:      **Repo-wide static census (2026-06-26)** of all `CandleLoader(` instantiations + `validate_dataset` call sites — a DATED OBSERVATION, not a permanent guarantee about future code (re-checked by `Revalidate-by`). As of that date the census identified **only two `validate_dataset` pre-flight call sites, both in `src/runtime/backtest_v2.py`** — `_preflight_dataset` (`:2769`, single-instrument) + `validate_universe` (`:2586`, multi-instrument). **Every other `CandleLoader.stream()` consumer streams with NO L3 pre-flight**, relying solely on the always-on inline L1/L2 backstop inside `stream()` (`src/runtime/backtest_v2.py:704-769`: L1 duplicate-header reject + L2 duplicate/out-of-order timestamp + Phase-1 column / Phase-2 value checks, all raising): in `src/`, the entire `src/research/` qualification pipeline (`runner.py:70`, `forensics.py:40`, `cross_sectional.py:118`, `adapters/spine_signal_source.py:168`, `adapters/structural_event_source.py:57`) + `analytics/sl_tp_comparator.py:599`, `governance/portfolio_validation.py:342`, `runtime/exit_model_band.py:58`, `runtime/unified_replay_harness.py:171`, `config_layer/config_validator.py:153`; AND repo-wide the entire `scripts/` fleet — training auto-tuners (`scripts/training/auto_tuner*.py`), **all** `scripts/research/*` phase drivers (incl. those that produced F-019…F-035), **all** `scripts/analysis/*` diagnostics — and the `tests/` harnesses. So the inline backstop is the universal integrity layer across the whole tooling surface; L3 is `backtest_v2`-confined. The `dataset_integrity.py:24` docstring claiming `validate_dataset()` is *"the pre-flight gate every backtest entry point calls"* was DOC_DRIFT (code wins) — corrected this turn to state the real scope.
- Supersedes:    —
- Reversal:      "`validate_dataset` is the pre-flight gate every backtest entry point calls before CandleLoader streams" -> "Only `backtest_v2` wires the L3 pre-flight; the research / analytics / governance / replay / config-validator paths rely entirely on the inline L1/L2 backstop in `CandleLoader.stream()`. The no-lookahead guarantee on those paths is the conjunction of the inline backstop + generator causal-ordering, with no L3 net behind it."
- Owner:         claude
- Note:          SCOPE GUARD (anti-overclaim, E-001) — **L3 increases confidence but is not required for the validity of prior research conclusions, because the L1/L2 invariants remained active on all historical execution paths.** Concretely: this does **NOT** invalidate F-019…F-035 — the inline L1/L2 backstop in `stream()` *did* enforce schema correctness + strictly-increasing chronology on every research run, so those corpora are causally sound (confidence ≠ validity). F-039 only locates **where** the no-lookahead guarantee comes from on each path and flags a latent **single-layer fragility**: the inline backstop is the *only* integrity layer on the research paths, so the "most likely failure mode" (making `stream()` permissive — silent row-skips, auto-sort, inferred timestamps) would remove the sole net there and could manufacture an optimistic backtest. Per the §6.5 Authority Ladder this is *information/architecture* → it earns doc/research authority only (no production authority); whether to add an L3 pre-flight to the research paths is a separate, evidence-gated decision, NOT implied by this finding. The doctrine it confirms: critical invariants get multiple enforcement layers, not a single point of failure.

---

### F-040 · The volatility-EXPANSION / compression→expansion TRANSITION channel (F-030's untested successor) is INFORMATIVE but NOT economically consumable in the spot directional architecture — Program 4 CLOSED
- Type:          ECONOMIC
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-26
- Revalidate-by: 2026-12-22
- Evidence:      Two-stage gate on the M15∧H1∧H4 candle-state conjunction (M15 base + H1/H4 *derived* via `src/research/resample.py`; no M5 on disk), pre-registered in [`docs/research/preregistration-program-4bcd.md`](research/preregistration-program-4bcd.md) BEFORE any run. **Stage 1 (information, non-directional — driver `scripts/research/transition_information.py`, artifact `results/research/candle_state/transition_information.json`, 2000-perm seeded):** forward **vol-expansion (4b)**, **range-expansion (4b)** and **compression→expansion transition (4d)** are each permutation-significant at the floor (pooled crypto AND FX p≈0.0005), **cross-market UNIVERSAL**, and **persistent** (half-life = 8 bars = horizon ceiling; 2024→2025 IG retention 0.874 / 0.994 / 0.672 ≥ the frozen 0.50). **State persistence (4c)** is NOT informative (p≈0.97, half-life 1, REJECTED). **Stage 2 (economic — driver `scripts/research/qualify_transitions.py`, artifact `qualify_transitions.json`, the NEW `src/research/hypotheses/compression_breakout.py` through the UNCHANGED M4 QualificationGate, intrabar_fixed + 12bps):** the directional breakout consumer is **0 PROMOTE**, well-powered REJECT everywhere — crypto (n=4,000–17,751) E −0.247…−0.596R, WR ≈0.31–0.34, PF 0.43–0.70; FX (n=2,631–15,024) cost-dominated PF 0.02–0.08, WR 0.11–0.23. NET = the **Stage-1-PASS / Stage-2-FAIL** outcome: the conjunction carries robust, priced-in information; the directional consumer cannot monetize it net of cost.
- Supersedes:    — (EXTENDS F-030; does not overturn it. Also: crypto Stage-2 WR ≈0.33 independently reproduces F-023's "all clusters win ≈0.34")
- Reversal:      F-030 note "the TRANSITION-forecast channel (anticipating a regime CHANGE, e.g. compression→expansion) is a genuinely different information channel and is UNTESTED → Program 4b" -> "TESTED: the transition channel IS informative (universal, persistent) but is NOT economically consumable by a spot directional consumer — the binding constraint is the EXECUTION MODEL (spot long/short cannot express a long-vol payoff), not predictability, exactly as F-030 concluded for the LEVEL channel."
- Owner:         claude
- Note:          SCOPE GUARD (anti-overclaim, E-001): (1) The Stage-1 information is **consistent with — and not separated from — known volatility memory** (F-030 H_atr=0.885; vol/range expansion is mechanically autocorrelated). The permutation test controls cell-cardinality but I did **NOT** isolate whether the *multi-TF conjunction* adds IG beyond a single-TF (M15) vol state, so **no "MTF conjunction is a novel information source" claim is made** — only that the channel is informative, which was already plausible. The durable, decisive result is the **economic** one (Stage 2), which needs no MTF-novelty. (2) "Stage-2 FAIL" means the DIRECTIONAL breakout construction fails under the fixed standard (spot long/short, intrabar_fixed, 12bps); it is NOT a proof that no instrument could ever monetize a vol forecast (a long-vol/straddle payoff is simply not expressible in this architecture — that is the point). (3) FX magnitude is cost-dominated (12bps ≈ 1.8–2.5× the FX M15 bar, per F-035), but PF≪1 + WR≪random keep the FX direction null robust. (4) Authority: research/docs only (§6.5) — a Stage-1 PASS earned docs, never sizing/fusion; Stage 2 earned nothing (0 PROMOTE). **Program 4 CLOSED** per the pre-registered rule (4b/4c/4d all resolved to Stage-1-FAIL or Stage-1-PASS+Stage-2-FAIL); see Funding Ledger.

---

### F-041 · ZoneGate runtime scores through `models/zone_registry.json` (8 zones, HARD gate) — NOT the version manifest; manifest `active` diverges; stored zone labels ~98% SL-hit (root cause = Phase-5 gate, not yet asserted)
- Type:          GOVERNANCE
- Status:        OPEN
- Confidence:    Certain
- Validated:     2026-06-27
- Revalidate-by: 2026-09-25
- Evidence:      Active config `configs/production/v2_multi_2026_04.json` → `engine_runner.zone_registry_path = "models/zone_registry.json"`, `zone_mode = "hard"` (config-verified); `BitNetZoneGate` loads that path ([`src/engines/live_engine.py:202`](../src/engines/live_engine.py), [`src/engines/zone_gate_engine.py:230`](../src/engines/zone_gate_engine.py) fail-open 0.5/pass on error). That file (`schema_version=v2_gaussian`, `source=discover_zones_v1_converted_to_gaussian`, 38-dim, 8 zones) has 6/8 zones with negative `mean_rr` and `sl_hit_rate` 0.959–0.989 (zone_0 n=20,708, tp=0.0132, sl=0.9865, mean_rr=−0.029) in stored meta. `models/zone_gate_registry.json` is a **version manifest** (version-key→`model_file`); its `active:true`→`models/BNBUSDT/.../zone_registry_BNBUSDT_202605_bnb_v1.json` sha256[:16]=`aade29c4f8c5ac9c` ≠ the config-loaded file's `e73e08934add02c9` → manifest ≠ scoring path.
- Supersedes:    —
- Reversal:      (intra-session, E-001) "zone_gate_registry.json is empty (0 zones) → ZoneGate may be silently fail-open in production" -> "CORRECTED: zone_gate_registry.json is a *populated version manifest* keyed by version (the 0-zones read was a parse artifact looking for a `zones` list); the scored centroid file is `models/zone_registry.json` (8 zones), loaded as the config directs."
- Owner:         claude
- Note:          TWO distinct facts, do not conflate. (1) CERTAIN now: the SCORING path is `models/zone_registry.json` as a HARD gate, and the version manifest's `active` flag points to a different file (bookkeeping `TruthConflict` per §6.2 — surfaced, NOT auto-reconciled; user decides). (2) OBSERVATION pending verification: the stored ~98% SL-hit / negative-mean_RR zone labels *suggest* label/exit-quality is the dominant ZoneGate defect (consistent with F-038 "OOD even when fed correctly" and F-025 "90.55% plain_stop_loss"), but whether the meta reflects honest intrabar_fixed outcomes vs a labeling artifact is the explicit **Phase-5 Go/No-Go gate** — NOT asserted here. Authority: research/docs + governance-hygiene only (§6.5); no architectural change rides on (2) until Phase 5. Plan: `docs/topics/model-intent-and-feature-ownership.md`.

---

## Funding Ledger (initiative-level capital allocation)

> A **finding** is an observation; **funding** is a capital-allocation decision derived from
> findings — and one finding (e.g. F-001) kills or funds many initiatives. This ledger keeps the
> two adjacent but separate. **Never silently revive a `KILLED`/`FROZEN` initiative:** its
> `Reopen Conditions` must be met *and* a SESSION LOG entry filed (per `CLAUDE.md §6.2`).
> Status vocab: `FUNDED · FROZEN · KILLED · RESEARCH · UNFUNDED`. `Evidence` cites finding IDs
> (CI checks they resolve); `FROZEN`/`KILLED` require non-empty `Reopen Conditions`.

### Program 4 — Candle-State Transition Frontier (4b/4c/4d) — KILLED
- Date:    2026-06-26
- Evidence: F-040 (4b/4c/4d two-stage gate: vol/range-expansion + compression→expansion are informative/universal/persistent but the directional consumer is 0 PROMOTE; 4c persistence not informative), extends F-030
- Reopen Conditions: per the pre-registered closure rule ([`docs/research/preregistration-program-4bcd.md`](../research/preregistration-program-4bcd.md)) Program 4 reopens ONLY via **new data** (e.g. an on-disk M5 corpus — the M5-based hypotheses were never runnable here), a **new market domain**, or a **new ontology** — specifically a *non-directional execution architecture* that can express a long-vol/straddle payoff (the binding constraint per F-040/F-030). **NEVER a parameter pass** — no further θ/horizon/threshold/conjunction-cardinality sweeps on 4b/4c/4d (4e/4f/4g = archaeology, out of bounds, mirrors the Program-1 closure). The candle_state encoder + MTF-conjunction + transition-target kernels are preserved as reusable assets.

### Interpreter: P&F (PNF-v1) — FROZEN
- Date:    2026-06-14
- Evidence: F-028 (first real interpreter; shadow-measured REJECT, worse than random controls on BNBUSDT)
- Reopen Conditions: a NEW P&F **ontology** (different target / horizon / signal-set, or a non-crypto universe) earning a non-negative shadow Δ vs controls — **NEVER a parameter pass** (box size / reversal count / signal-threshold sweep is forbidden archaeology, per the Plan-5 scope guard). A `PNF-v2` is a distinct decision, not a rescue of PNF-v1. This is the falsified-interpreters ledger: a rejected interpreter is preserved knowledge so future sessions do not rebuild it.

### Liquidity V2 — KILLED
- Date:    2026-06-03
- Evidence: F-001, F-011 (Phase-0 economic-edge gate FAIL 0/4)
- Reopen Conditions: a feature track shows ΔAUC ≥ +0.03 OOS **and** positive expectancy lift surviving the gate **and** a cross-instrument pass (the §7 kill-criteria of economic-edge-gap-analysis-2026-06-03.md)

### RR Fusion Model Retrain/Recalibration — RESEARCH
- Date:    2026-06-26
- Evidence: F-038 (rr_fusion disabled in production after confirmed Gaussian-duplicate defect; the underlying Mahalanobis model is OOD/mis-calibrated even when fed the full feature vector — likely BNB-specific training data per filename hint, stale since 2026-05-24)
- Reopen Conditions: a calibration-validation script (per F-038's Option-B design: coverage check `P(d_sq < mahal_clip)`, confidence-distribution check, per-instrument breakdown) demonstrates a retrained/recalibrated model clears `confidence_bypass_threshold` on a material fraction of current multi-instrument live-like data, **and** the candidate model shows measured ΔG001 improvement over the disabled-rr_fusion baseline through `promotion_manager` — per the §6.5 Authority Ladder, tunability/buildability never substitutes for demonstrated authority. Until then, rr_fusion stays disabled; this is RESEARCH (not FROZEN/KILLED) because it was never funded in the first place — Phase 1 (disable) shipped without needing Phase 2 to run.

### TradeNet V2 — KILLED
- Date:    2026-06-03
- Evidence: F-001, F-005 (Phase-0 FAIL; the fusion neural slot is a built-but-unwired stub)
- Reopen Conditions: same Phase-0 gate clears **and** wiring TradeNet v1 into the fusion slot earns measured weight (weight-0.0 A/B lift)

### Probability Surface V2 — KILLED
- Date:    2026-06-03
- Evidence: F-001, F-012 (Phase-0 FAIL; would duplicate the sidecar ReplayMemory cluster path-stats)
- Reopen Conditions: same Phase-0 gate clears **and** ReplayMemory path-stats show AUC lift beyond static zone features (RESEARCH item below succeeds)

### BitNet V2 (adaptive threshold) — FROZEN
- Date:    2026-06-03
- Evidence: F-004 (BitNet v1 gate is live at hardcoded 0.55; the adaptive infrastructure is unused)
- Reopen Conditions: enough `bitnet_score_at_entry` outcomes accrue to fit per-instrument/per-regime thresholds **and** the adaptive threshold beats the static 0.55 gate on net rr

### Governance/execution wiring (integrity gate + drift->size-down) — FUNDED
- Date:    2026-06-03
- Evidence: F-001, F-006, F-008
- Reopen Conditions: —

### Per-instrument session/throughput sweeps — FUNDED
- Date:    2026-06-03
- Evidence: F-003, F-009
- Reopen Conditions: —

### ReplayMemory -> deterministic advisory path — RESEARCH
- Date:    2026-06-03
- Evidence: F-012, F-008
- Reopen Conditions: —

### Pattern Timing Library — FUNDED (Phase-1 shipped; early-invalidation FROZEN research-complete/production-pending)
- Date:    2026-06-06
- Evidence: F-001, F-002, F-014
- Reopen Conditions: — (Phase-1 measure-only SHIPPED: timing core + library + advisor, weight 0.0. Consumer A early-invalidation: signal-level A/B Net RR +ve 4/4 & all K, winners protected (thin margin); offline executed-trade A/B (N=35) confirmed mechanism + winner-preservation + net-positive but headline MaxDD FLAT / drawdown thesis only partial — UNPROVABLE at this N. FROZEN: no promote / no live / no spine change. UN-FREEZE gate = executed-trade throughput materially higher (ties F-003 session/detection supply), then spine-integrated A/B (adds capital-recycling) shows material MaxDD↓ with expectancy intact across instruments+OOS. Consumer B ranking stays HOLD behind its OWN A/B.)

### Execution-planner replay experiment (selection vs SL/TP) — RESEARCH
- Date:    2026-06-03
- Evidence: F-010, F-002
- Reopen Conditions: —

### Program 1: Next-Bar Directional Ontology (M15 crypto majors, intrabar_fixed+12bps) — KILLED
- Date:    2026-06-13
- Evidence: F-019, F-020, F-021, F-025
- Reopen Conditions: ONLY a genuinely NEW ontology with a pre-registered hypothesis — a different target (vol/range/persistence), horizon (H1/H4/D), asset class (FX/equities/commodities), objective (market-making/carry/relative-value), or label space (event/structural regimes) = a SEPARATE Program 2 decision. NOT reopenable by any parameter pass (no further SL/TP grids, TP ratios, trailing, entropy partitions, score thresholds, or session sweeps; no re-running F-019/020/021/025 with tweaked knobs) — that is archaeology, explicitly out-of-bounds. Closure synthesis: docs/analysis/program-1-closure-2026-06-13.md. Decisive: reality_gap +4.16R (value is upstream/informational; exits reshape risk not expectancy).

### Program 2: Structural Asymmetry (trap/sweep continuation) — FROZEN
- Date:    2026-06-13
- Evidence: F-026
- Reopen Conditions: E1 (the single decisive measure-only experiment) returned INSUFFICIENT_POWER with a NEGATIVE point estimate (completed sweep→displacement→retest loses to sweep-only on BNBUSDT M15, n=47, ~1% funnel completion; calibration passed so the result is trustworthy). FROZEN after one experiment per the pre-registered protocol (only ASYMMETRY_SURVIVES advances to E2). Reopen ONLY if a cross-instrument POOLED retest population reaches adequate power (CI ≤ power_ci_max) AND shows a NON-NEGATIVE, control-beating asymmetry — OR a genuinely NEW structural ontology is pre-registered. NOT reopenable by threshold search (no changing h/L sets, no E2/conditioning on this result) — that is the named failure mode. Synthesis: docs/analysis/structural-asymmetry-bnbusdt-2026-06-13.md.

### Program 3: Higher-Timeframe Directional Ontology (H1/H4 crypto majors) — FROZEN
- Date:    2026-06-13
- Program State: FALSIFIED (3A)   (state machine: PRE_REGISTERED → RUNNING → {ADVANCED | FALSIFIED | EXHAUSTED}; 3A reached FALSIFIED, decisive toy arm; 3B not run)
- Evidence: F-027 (3A verdict: 0 PROMOTE at H1 and H4); F-019, F-020, F-021, F-025 (Program 1's four-falsification closure scoped the kill to *next-bar · M15 · crypto-majors* and recorded an UNTOUCHED FRONTIER — H1/H4/D horizons among it — as the sanctioned reopen path; docs/analysis/program-1-closure-2026-06-13.md §"EXHAUSTED ≠ WRONG")
- Hypothesis (pre-registered, BEFORE running): the directional null (F-019/020/021/025) is specific to the M15 horizon's signal-to-noise; on a coarser bar the SAME hypothesis pool (toy expansion_breakout/mean_reversion + the production spine) may clear the M4 gate. NONE was implied to contain edge.
- Design: deterministic M15→{H1,H4} resampler (src/research/resample.py, calendar-boundary, causal trailing-drop, byte-identical/SHA-stable — tests/research/test_resample.py) feeds the EXISTING audited spine VERBATIM (forward_walk intrabar_fixed + CostModel 12bps + IS/70-30 OOS + BH; research.qualification). Drivers: scripts/research/build_resampled_data.py + scripts/research/qualify_htf.py. Configs: configs/research/research_config_htf_majors.json + research_config_spine_htf_majors.json.
- Horizon split (avoids the two-questions trap): 3A = BAR_COUNT_CONSTANT (PRIMARY, RUN — FALSIFIED) — harness bar-counts held constant (max_forward=40 = 10h M15 / 40h H1 / 160h H4); the null reads as "this bar-relative ontology failed." 3B = WALL_CLOCK_CONSTANT (CONTINGENT, pre-defined NOT built) — disambiguates horizon length from timeframe structure if ever warranted.
- Verdict (3A): toy directional pool 0 PROMOTE at H1 and H4 (F-027); spine arm non-decisive (H1 n≤10 INSUFFICIENT; H4 NOT_MEASURABLE — adapter index contract). Coarser timeframes are not the missing lever.
- Reopen Conditions: ONLY (a) Program 3B (WALL_CLOCK_CONSTANT) showing a candidate clear the M4 gate IS&OOS at a wall-clock-matched horizon, OR (b) a genuinely NEW ontology (non-directional target — vol/range/persistence — or a non-crypto universe — FX/metals/equities; data present in data/) with a pre-registered hypothesis. NOT reopenable by any Program-1 parameter pass (no SL/TP/session/entropy/score tweaks, no re-running 3A with tuned knobs) — that is archaeology.

### Program 4: Non-Directional Target — Regime LEVEL Conditioning (crypto majors, intrabar_fixed+12bps) — KILLED
- Date:    2026-06-17
- Evidence: F-030 (0 REGIME_EXPLOITABLE; powered toys statistically-informative-but-economically-worthless + 2 REDUNDANT; spine INSUFFICIENT)
- Reopen Conditions: ONLY a genuinely NEW ontology with a pre-registered hypothesis — NOT a parameter pass. The pre-registration's §5 fixed parameters (tercile_window=480, lag_k=50, atr_period=14, min_cell_samples=30, harmful_margin, redundant_tol, null_relabelings) are explicitly forbidden reopen routes ("Program 4 with a bigger window / more regimes / extra consumers" is mechanically out-of-bounds archaeology). The TRANSITION channel is NOT a reopen of Program 4 — it is the separately pre-registered Program 4b below. Synthesis: docs/research-readiness/program-4-nondirectional-preregistration.md.

### Program 4b: Non-Directional Target — Regime TRANSITION Forecast (forward Markov P^H) — RESEARCH (pre-registration pending)
- Date:    2026-06-17
- Evidence: F-030 (the regime-LEVEL channel is closed; the TRANSITION channel — anticipating a regime CHANGE, e.g. compression→expansion, which a contemporaneous label cannot express — is a genuinely different information channel and is untested)
- Reopen Conditions: — (this is a NEW ontology, not a reopen; it inherits Program 4's full governance: single pass, hypothesis-free 3×3, four+ controls incl. a within-tercile-shuffle that isolates transition dynamics from vol level, label-permutation null, cohort BH, anti-archaeology, a HARD calibration gate (H_atr 0.885±0.03), and lag_k = forecast horizon H. Pre-registration: docs/research-readiness/program-4b-transition-preregistration.md. ONE shot — no Program 4b.1/4b.2.)

### Program 5: Cross-Sectional Relative-Value (dispersion, market-neutral; crypto majors, intrabar close-to-close+12bps) — KILLED
- Date:    2026-06-18
- Evidence: F-032 (0 PROMOTE / 0 REDUNDANT; all 5 interpreters REJECT, well-powered n=722–8,758; cross-sectional momentum loses, the lone positive cell is a long-leg/beta artifact and insignificant)
- Reopen Conditions: ONLY a genuinely NEW axis with a pre-registered hypothesis — NOT a parameter pass. The §8 fixed parameters (the 5-interpreter grid, k=2, the 5-control set, oos_split=0.30, n_permutations=2000, 12bps, close-to-close, the 6-coin universe) are explicitly forbidden reopen routes ("Program 5 with k=3 / more lookbacks / longer holds" is mechanically out-of-bounds archaeology). Distinct NEW axes (each a separate decision): cross-sectional on a DIFFERENT asset class (FX/metals — data thin; equities — no data), or a DIFFERENT payoff structure entirely (carry / funding / basis / volatility / market-making — most currently data-blocked). Pre-registration + synthesis: docs/research-readiness/program-5-cross-sectional-preregistration.md.

### Program 6: Carry/Basis Signal on Cross-Sectional Spot Dispersion (crypto majors, close-to-close+12bps) — KILLED
- Date:    2026-06-18
- Evidence: F-033 (0 PROMOTE / 0 REDUNDANT; all 8 carry/basis interpreters REJECT, well-powered n=722–4,373; both signs net-negative E∈[−0.0032,−0.0016], PF 0.55–0.82, p 0.76–1.0, each loses to market/long_only control — below Authority-Level-1). First axis tested on the newly-acquired perp corpus.
- Reopen Conditions: ONLY a genuinely NEW axis with a pre-registered hypothesis — NOT a parameter pass. The pre-registration's fixed parameters (the 8-interpreter carry/basis grid, k=2, L∈{96,672}, H∈{16,96}, the 5-control set, 12bps, close-to-close, the 6-coin universe, signal-on-spot-dispersion payoff) are forbidden reopen routes ("Program 6 with more lookbacks / k=3 / longer holds" is archaeology). Distinct NEW axes (each a separate decision): the **carry-HARVEST payoff** (Program 6b — now run, F-034), open-interest as a signal (Program 7, data-blocked ~30d), or carry/basis on a DIFFERENT asset class. The frozen data corpus (Program Carry Acquisition) is a permanent asset and is NOT part of this kill. Pre-registration: docs/research-readiness/program-6-carry-basis-preregistration.md.

### Program 6b: Carry HARVEST — funding cashflow + price/basis (crypto majors, 12bps) — KILLED
- Date:    2026-06-18
- Evidence: F-034 (0 PROMOTE; all 4 tradeable harvest_full REJECT, n=104–729; funding income real but ~1–6 bps < ~24 bps turnover cost ⇒ all 4 funding-only twins DIAGNOSTIC_NEGATIVE; lowest-turnover H=672 still REJECTs PF 0.83; loses to cash/reversed). Carry harvest as constructed does not clear costs.
- Reopen Conditions: ONLY a genuinely NEW structural thesis with a fresh pre-registration — NOT a parameter pass. The pre-registration's fixed parameters (long-low/short-high perp basket, k=2, L∈{1,96}, H∈{96,288,672}, the 6 controls incl. cash, 12bps/leg, the 6-coin universe) are forbidden reopen routes ("6b with more holds / lower cost / netting / different rebalance" is archaeology). A genuinely different LOW-TURNOVER cash-and-carry construction (position-netting to slash the cost drag) would be a new program with its own thesis + pre-registration, not an H/cost tweak here. STOP discipline (F-033/F-034): pause after this; Program 7 (OI) / FX-metals are NOT automatic. Pre-registration: docs/research-readiness/program-6b-carry-harvest-preregistration.md.

---

## Terminal (SUPERSEDED / RETIRED) — kept for replay

_(none yet — when a finding above is overturned, flip its Status here and add the superseding F-id.)_

---

## Research Envelope / Scope Matrix

> **What this is.** The scannable answer to "is the paradigm dead, or was the experiment too
> narrow?" Each falsification (F-019…F-026) is a verdict *within a measured envelope*; this matrix
> makes the envelope — and the **untouched frontier** — explicit so a null is never over-read as a
> global claim. Authoritative on conflict = the finding rows above + the Program-1 closure
> (docs/analysis/program-1-closure-2026-06-13.md). `Updated: 2026-06-13`.
>
> Status vocab: `FALSIFIED-IN-SCOPE` (null under the governing truth standard, scope stated) ·
> `ALREADY-ANSWERED` (a frequently-proposed "unknown" that the repo has in fact measured) ·
> `UNTOUCHED-FRONTIER` (not yet tested; a legitimate reopen axis — a NEW program, not archaeology).

| Axis | Tested envelope | Status | Evidence / note |
|---|---|---|---|
| Entry edge (next-bar direction) | crypto-majors · **M15** · intrabar_fixed+12bps · IS+70/30 OOS | FALSIFIED-IN-SCOPE | F-019 (toys ≈ random on all 4 majors + pooled; spine throughput-starved) |
| Conditional direction (session×vol×momentum) | crypto-majors · M15 · h≤20 · paired entropy+economics | FALSIFIED-IN-SCOPE | F-020 (25/25 entropy-"significant" at N but 0 economic pockets) |
| Selection skill (RETEST selected−rejected) | crypto-6 · M15 · decomposed by reject-reason | FALSIFIED-IN-SCOPE | F-021 (the +1.17R ΔE is ENTIRELY the incumbent SESSION filter; ZONE/SCORE null) |
| Exit/cost geometry | crypto-6 · M15 · **42-cell SL{0.5–3.0}×TP{1.0–5.0}** grid, entries fixed | ALREADY-ANSWERED | F-025 (every cell E_oos<0 incl. 3.0×5.0; "widen the stop to 2.5 ATR" is *inside* this grid — re-running is Program-1 archaeology, out-of-bounds) |
| Structural asymmetry (sweep→disp→retest) | BNBUSDT · M15 · multi-horizon, 4 controls | FALSIFIED-IN-SCOPE | F-026 (negative + INSUFFICIENT_POWER, ~1% funnel completion) |
| Process memory (Hurst / autocorrelation / vol-clustering) | crypto-majors · M15 · N≈70k | ALREADY-ANSWERED | F-020 / process_diagnostics.py (H_atr=0.885 vs H_returns=0.527; ARCH-LM reject; "vol has memory, direction doesn't") — NOT an open unknown |
| Session policy as a promotable lever | BNBUSDT · M15 · intrabar_touch + 70/30 OOS | ALREADY-ANSWERED | F-017 (the in-sample/close-only "+ASIA" gains decay/flip OOS; failed *statistically*, not merely on a governance threshold) |
| **Timeframe horizon (H1/H4)** | crypto-majors · **H1 + H4** · intrabar_fixed+12bps · IS+70/30 OOS+BH (Program 3A) | FALSIFIED-IN-SCOPE | F-027 (0 PROMOTE at H1/H4; H4 expansion_breakout only reaches cost-recovery gross≈0; spine non-decisive). Daily (D) + Program 3B WALL_CLOCK_CONSTANT remain untouched |
| Non-crypto universe (FX/metals/equities) | — (crypto-majors only) | UNTOUCHED-FRONTIER (deferred) | data present (AUDUSD/GBPUSD/USDJPY/XAUUSD/EURCAD M15); a separate future program after the HTF verdict |
| Non-directional target — regime LEVEL conditioning | crypto-majors · M15 · intrabar_fixed+12bps · IS+70/30 OOS+BH + label-permutation null + lagged control | FALSIFIED-IN-SCOPE | F-030 (0 exploitable; powered toys significant-but-economically-worthless, best regime never E>0; 2 REDUNDANT; spine INSUFFICIENT) |
| Non-directional target — regime TRANSITION forecast (Markov P^H) | — | UNTOUCHED-FRONTIER (Program 4b, pre-registration pending) | a genuinely different information channel (anticipating a regime CHANGE); separate pre-registration, not a Program-4 reopen |
| **Cross-sectional relative-value (dispersion, market-neutral)** | crypto-6 · **M15** · close-to-close+12bps/leg · IS+70/30 OOS+BH · 5 controls (Program 5) | FALSIFIED-IN-SCOPE | F-032 (0 PROMOTE; momentum loses PF 0.335, lone positive cell is a long-leg/beta artifact, insignificant p=0.57). FIRST panel-axis null; cross-sectional on FX/perps/other payoff structures stays untouched |
| **Carry/basis as a cross-sectional signal** | crypto-6 · **M15** · close-to-close+12bps/leg · perp funding(8h ffill)+basis(M15) · IS+70/30 OOS+BH · 5 controls (Program 6) | FALSIFIED-IN-SCOPE | F-033 (0 PROMOTE; all 8 cells both signs E(net)<0, PF 0.55–0.82, p 0.76–1.0, each loses to market/long_only — below even Authority-Level-1). FIRST axis tested on NEWLY-ACQUIRED data. Does NOT test the funding-PnL carry-HARVEST payoff (Program 6b) or OI (Program 7) |
| **Carry-HARVEST payoff (hold perp to earn funding ± basis convergence)** | crypto-6 · perp basket · 12bps/leg · H∈{1d,3d,1w} · cash+5 controls (Program 6b) | FALSIFIED-IN-SCOPE | F-034 (0 PROMOTE; funding income real but ~1–6 bps < ~24 bps turnover ⇒ net-negative before price drag; lowest-turnover H=672 still REJECTs). Distinct from F-033 (cashflow not signal). A low-turnover/netting cash-and-carry is a separate untested construction (new thesis, not a tweak) |
| Non-directional targets (range/persistence, other) | — | UNTOUCHED-FRONTIER (deferred) | per Program-1 closure §"EXHAUSTED ≠ WRONG"; objective ≠ directional speculation |
