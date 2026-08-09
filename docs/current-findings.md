# Current Findings — Repository Truths (living)

> Created: 2026-06-03 · Updated: 2026-08-06
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
>
> **Measurement identity (added 2026-08-06).** Every non-terminal finding carries `Family` (which
> research object it is about — an `RF-*` id from
> [`governance/research_family_registry.json`](governance/research_family_registry.json)) and
> `Contract` (the measurement basis it was produced under). `Contract: UNKNOWN` is permitted and
> honest, but a claim with an unknown contract **is not comparable to any other claim and settles
> nothing**. All 66 non-terminal findings seed as `UNKNOWN` — that is the recorded state of the
> evidence, not a defect. See [`governance/MEASUREMENT_CONTRACT.md`](governance/MEASUREMENT_CONTRACT.md) §9–§10.

---

## Schema (one block per finding)

```
### F-NNN · <one-line conclusion>
- Type:          ARCHITECTURE | ECONOMIC | GOVERNANCE | OPERATIONAL | RISK
- Family:        RF-* id from docs/governance/research_family_registry.json | — (not a market object)
- Contract:      <measurement identity> | UNKNOWN     (non-terminal findings only)
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
- Family:        — (not a market object; see docs/governance/research_family_registry.json)
- Contract:      UNKNOWN
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
- Family:        RF-CRT-STRUCTURE
- Contract:      UNKNOWN
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

### F-004 · BitNet is a hard rejection gate WHEN ENABLED (`use_bitnet`); inert on the active config
- Type:          ARCHITECTURE
- Family:        RF-NEURAL-CONSUMERS
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-06-03
- Revalidate-by: 2026-09-01
- Evidence:      LIVE gate — src/config_layer/crt_engine_v2.py `if self.config.use_bitnet: bn_score = bitnet_score(features); if bn_score < self.config.bitnet_main_threshold: return False` inside the CALLED `approve_with_soft_conf` (~:1733, invoked ~:2602); defaults `bitnet_main_threshold=0.55` / `use_bitnet=False` (~:364-365). The earlier citation :1804 pointed at the `approve()` method (~:1766), whose BitNet gate (~:1806) is UNGUARDED but DEAD — `approve()` has no call site in src/. Persistence: src/runtime/backtest_v2.py reads `state.bitnet_main_score` (absent attr → not evaluated).
- Supersedes:    —
- Reversal:      "BitNet score is built but not consumed / not persisted (dead-dormant-inventory.md:26)" -> "BitNet hard-gates entries at score<0.55 on the CRT path WHEN `use_bitnet` is enabled, and the score is persisted; only the ADAPTIVE threshold (hardcoded 0.55; get_bitnet_threshold(regime) never called) is dormant."
- Branch-scope:  2026-07-05 (§6.2 r7, user-approved) — the live gate is behind `use_bitnet`, which is **false on the active config `v2_multi_2026_04`**, so the gate is INERT on the active patch (never computes/persists a score) and `candles_since_retest` (its distinctive input) reaches no live decision. The "live hard-reject + persisted" claim holds **only where `use_bitnet:true`**. Scope + citation correction (:1804→:1733), NOT a reversal — real on the enabled code line. Consistent with active_models.yaml `bitnet.enabled:false` and the Feature Lineage Matrix (candles_since_retest role=unused, fusion_weight inert:0).
- Owner:         claude

### F-005 · TradeNet v2 is BUILT but unwired (fusion neural slot is a stub)
- Type:          ARCHITECTURE
- Family:        RF-NEURAL-CONSUMERS
- Contract:      UNKNOWN
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
- Family:        — (not a market object; see docs/governance/research_family_registry.json)
- Contract:      UNKNOWN
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
- Family:        — (not a market object; see docs/governance/research_family_registry.json)
- Contract:      UNKNOWN
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
- Family:        — (not a market object; see docs/governance/research_family_registry.json)
- Contract:      UNKNOWN
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
- Family:        RF-EXIT-COST-PATH
- Contract:      UNKNOWN
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
- Family:        RF-CRT-STRUCTURE
- Contract:      UNKNOWN
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
- Family:        — (not a market object; see docs/governance/research_family_registry.json)
- Contract:      UNKNOWN
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
- Family:        — (not a market object; see docs/governance/research_family_registry.json)
- Contract:      UNKNOWN
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
- Family:        RF-EXIT-COST-PATH
- Contract:      UNKNOWN
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
- Family:        RF-CRT-STRUCTURE
- Contract:      UNKNOWN
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
- Family:        — (not a market object; see docs/governance/research_family_registry.json)
- Contract:      UNKNOWN
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
- Family:        RF-SESSION-TIME
- Contract:      UNKNOWN
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
- Family:        — (not a market object; see docs/governance/research_family_registry.json)
- Contract:      UNKNOWN
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
- Family:        RF-CRT-STRUCTURE
- Contract:      UNKNOWN
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
- Family:        RF-REGIME-DYNAMICS
- Contract:      UNKNOWN
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
- Family:        RF-SESSION-TIME
- Contract:      UNKNOWN
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
- Family:        RF-LABEL-TRUTH
- Contract:      UNKNOWN
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
- Family:        RF-SHAPES-TRAJECTORIES
- Contract:      UNKNOWN
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
- Family:        RF-EXIT-COST-PATH
- Contract:      UNKNOWN
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
- Family:        RF-EXIT-COST-PATH
- Contract:      UNKNOWN
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
- Family:        RF-CRT-STRUCTURE
- Contract:      UNKNOWN
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
- Family:        RF-HTF
- Contract:      UNKNOWN
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
- Family:        RF-SHAPES-TRAJECTORIES
- Contract:      UNKNOWN
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
- Family:        RF-FEATURE-ONTOLOGY
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-15
- Revalidate-by: 2026-09-13
- Evidence:      A 2026-06-15 adversarial design session escalated `center=True` swing detection (src/features/feature_pipeline.py:343) to "FATAL label leakage" and demanded a repo-wide pipeline rewrite + model deletion. Verification against code reconciles it to the already-validated trust-layer **F1** (docs/analysis/backtest-trust-audit-2026-06-10.md §4d): with TRUST_SWING_CAUSAL=1 (src/features/feature_pipeline.py:366), 974/3000 swing flags shift yet the BNBUSDT ledger is byte-identical (0 trades added/removed, edge inflation ≈ 0) because the CRT entry path does not consume swing columns. Two further adversarial premises are FALSE in code: the claimed training-contamination chain `TradeRecord.features → dataset builder → tensor` does not exist (training reads opportunities_*.jsonl via scripts/training/train_trade_net_v2.py), and the proposed "execution-quality successor" already exists as TradeNet v2 (src/training/trade_net_v2.py; wired as a soft neural_fn via src/training/trainer.py make_neural_fn_v2 — see F-005). Program B (measure-only, RESOLVED): `volatility_regime` uses a GLOBAL `rank(pct=True)` (src/features/feature_pipeline.py:306) that IS decision-reachable (src/strategies/s05_grid.py:120 blocks LONG in TRENDING). The TRUST_VOLREGIME_CAUSAL A/B/C hook (global vs expanding vs rolling) was run on v2_multi_2026_04/BNBUSDT via the production spine: all three are byte-identical (13 trades, WR 0.3077, PF 0.5233, ROI −4.63%; 100% decision overlap, 0 added/removed) → `A≈B≈C` ⇒ benign on this config (same class as F1; the governing CRT spine, not s05_grid, drives this config). Recorded in docs/analysis/backtest-trust-audit-2026-06-10.md §4f; driver results/trust/volregime_measure.py. CROSS-UNIVERSE (§4g): the A/B/C/S sweep (+ TRUST_SWING_CAUSAL for F1) across BTC/ETH/SOL + AUDUSD/GBPUSD/USDJPY/XAUUSD is byte-identical (100% decision overlap) on every instrument → both F1 (swing center=True) and F-029 (volregime global-rank) GRADUATE from "BNBUSDT benign" to "CRYPTO-MAJORS benign" (BNB+BTC+ETH+SOL, real trade counts 5/5/7). HONEST CAVEAT: the 4 FX/metals rows are NOT INFORMATIVE — the active multi config approves 0 trades on them (no FX tuning), so their "benign" is vacuous; the cross-asset-class claim stays OPEN pending an FX-trading config. The global→causal conversion (Option 2) stays gated on a future config/instrument showing material divergence.
- Supersedes:    —
- Reversal:      "center=True swing detection is FATAL label leakage that contaminates the model and forces a pipeline rewrite" -> "F1 already measured it byte-identical-benign for trade generation on BNBUSDT; the FATAL framing is DOC_DRIFT, the alleged training-contamination path does not exist, and the proposed successor model is already built — the LIVE-UNSAFE flag stands but no backtest edge depends on it"
- Owner:         claude
- Note:          **Scope refinement 2026-07-11 (F-051):** F-029's claim is **trade-generation ledger identity under TRUST_SWING_CAUSAL / causal structure intervention on gate-OFF** — reconfirmed (BNB 13≡13). It does **not** authorize keeping centered publication as production PIT-clean semantics: Phase A proved value-level contamination of the 10-dim structure closure, CRT/Zone input exposure, and live default-absent zeros. Structural importance for gate-ON ledgers remains INCONCLUSIVE (PC-2 failed). Do not read F-029 as "lookahead is free."

### F-031 · Governance caught an overclaim before repository contamination (Program-4 rollup E-001E)
- Type:          GOVERNANCE
- Family:        — (not a market object; see docs/governance/research_family_registry.json)
- Contract:      UNKNOWN
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
- Family:        RF-REGIME-DYNAMICS
- Contract:      UNKNOWN
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
- Family:        RF-CROSS-SECTIONAL-PANEL
- Contract:      UNKNOWN
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
- Family:        RF-CARRY-BASIS
- Contract:      UNKNOWN
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
- Family:        RF-CARRY-BASIS
- Contract:      UNKNOWN
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
- Family:        RF-CRT-STRUCTURE
- Contract:      UNKNOWN
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
- Family:        RF-ZONE-GEOMETRY
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-06-24
- Revalidate-by: 2026-09-22
- Evidence:      scripts/research/qualify_zone_topk.py (driver; results/research/zone_topk_sweep/zone_topk_sweep.json, DETERMINISTIC body sha256=0e8221da…). Measures ΔG001 of the just-shipped `engine_runner.zone_gate` config knobs (see [[project_zone_gate_topk_config]]). The zone registry is LIVE (`models/zone_registry.json`, 8 zones, total_weight 139,942 ≫ underpowered floor 50), so the knob is NOT dormant-by-emptiness. Sweep `top_k ∈ {1,2,3,5,8}` (cluster_min_n=2, cluster_spread_max=0.15) × BNB/ETH/BTC/SOL, governing intrabar_touch (Layer 1 = the spine's own goal_report) + the VERBATIM M4 gate (Layer 2, intrabar_fixed/12bps/2000perm/alpha 0.05 vs always_long+random controls). RESULT: spine entry sets are **byte-identical at every top_k** ⇒ **ΔG001 ≡ 0 exactly** (Δexpectancy_r = +0.0000 for every cell × instrument; identical trade counts BNB 13 / ETH 5 / BTC 5 / SOL 7). M4: **0 PROMOTE** — per-instrument INSUFFICIENT (n<30); POOLED n=30, E(net)=−0.399, REJECT — identical to F-019's spine arm. V0 self-check byte-identical (the get_prod_section injection is neutral at defaults).

  **CORRECTION (2026-06-25, E-001 — "caught me overclaiming"):** the original mechanism claim here — *"the zone cluster score enters Fusion at weight 0.2 and flips ZERO decisions … the same perfect-no-op as the EMA gate"* — is **WITHDRAWN as an overclaim**. The follow-up diagnosis (`scripts/research/diagnose_zone_inertness.py`) found the engine_runner **FUSION GATE is DISABLED in the backtest harness**: `.env` sets `BACKTEST_ENGINE_GATE=0`, and only `backtest_v2.py` honors that flag (the live path does **not**). So in this entire research corpus the 4-engine fusion (CRT/Gaussian/zone/RR) + DecisionEngine veto **never runs** — backtest entries are produced by the **CRT state machine alone**. `top_k` is therefore inert in the backtest **trivially** (nothing in fusion executes), **NOT** because zone is non-pivotal in a live-equivalent fusion. Probe (12k BNB candles): gate-ON → the lone CRT candidate is REJECTed (0 trades); gate-OFF → 1 trade — i.e. the gate is highly consequential when on. The **ΔG001≡0-in-backtest headline and the tunability-not-authority verdict still stand**, but the fusion-mechanism attribution does not, and **live-path zone pivotality is UNTESTED**. Stage B not entered (moot under the corpus correction). See F-037 for the corpus-scope finding.

  **UPDATE (2026-06-25) — live-path pivotality now TESTED (gate-ON ablation), confidence restored Possible→Likely:** re-ran the ablation with `BACKTEST_ENGINE_GATE=1` (`results/research/zone_inertness_gateon/`, body sha in manifest) so the 4-engine fusion actually runs (live-equivalent spine: BNB 11 / ETH 4 / BTC 5 / SOL 6). Sweeping `weight_zone_gate ∈ {0.0,0.2,0.4,0.6}` × `zone_cluster_threshold ∈ {0.0,0.25,0.5}` → **every cell byte-identical** ⇒ **zone is non-pivotal on the REAL fusion spine** (removing it, tripling its weight, or forcing its vote on/off changes zero entries). MECHANISM (Phase-2 audit, 13 bars, real scores): zone is **NOT weak** (mean 0.608, median 0.718, **+0.358 above** the 0.25 threshold, ≥0.25 on 85% of bars) and **NOT under-weighted** (3× weight = no change) → the cause is **redundancy / decision-domination** — zone is a near-constant strong "yes" vote that never moves the fused score across the DecisionEngine cut; the real fusion vetoes (CRT 13→11 etc.) are **zone-independent** (CRT/Gaussian/RR/decision drive them). Non-pivotality is byte-exact/deterministic (robust to tiny N) → Likely. Side flag (untested): `gaussian`≡`rr` audit mean 0.7468 — possible rr_fusion coupling, separate question.
- Supersedes:    —
- Reversal:      "Making the zone top-k tunable might let a non-default value improve the goal (G001)" -> "top_k is config-TUNABLE but economically INERT. In the CRT-only backtest corpus ΔG001≡0 trivially (fusion gate off); and on the REAL gate-ON fusion spine zone is MEASURED non-pivotal (redundant/decision-dominated, not weak, not under-weighted — UPDATE above). The migration grants tunability, never authority (§6.5) — default top_k=3 stays; a non-default value is unjustified. The interim 'fusion weight 0.2 flips no decision' claim was an overclaim while the gate was off, since re-measured gate-ON and now SUPPORTED."
- Owner:         claude
- Note:          Extends F-021 (zone-selection-beyond-session null: ZONE produced 0 rejects) and F-019 (spine INSUFFICIENT, pooled n=30 REJECT) to the explicit config-knob level. This is the §6.5 Authority-Ladder discipline closing the loop on a config migration: a BEHAVIORAL knob earned CONFIG_DRIVEN tunability, then was measured against G001 and earned NO authority. A clean 0-PROMOTE / ΔG001≡0 is a successful experiment (high knowledge-ROI null, §6.1), not a failure. Research authority only. SCOPE per F-037: measured on the CRT-only research spine (fusion gate off by design).

---

### F-037 · The research "spine" is CRT-only by design — the 4-engine fusion gate is OFF in backtests
- Type:          ARCHITECTURE
- Family:        RF-CRT-STRUCTURE
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-06-25
- Revalidate-by: 2026-12-22
- Evidence:      Direct probe (instrumented `EngineRunner.run` call-counter on the spine-adapter backtest) → `run()` is called 0 times; root cause `BACKTEST_ENGINE_GATE=0` is set by `.env` (confirmed: NOT in the shell env; one line in `.env`; loaded via dotenv with override=False) and is honored ONLY by `src/runtime/backtest_v2.py:1838` (the live path `live_engine_hook` does NOT read it). So every research backtest harvests the **CRT state-machine** entries; the `EngineRunner` 4-engine fusion (CRT/Gaussian/ZoneGate/RR) + `DecisionEngine` veto NEVER RUNS in research. Gate-ON vs gate-OFF full-history impact (results/research/_gate_impact/summary.json): the fusion veto is real but modest — BNB 13→11 trades, SOL 7→6 (entries_changed=True both); gate-OFF reproduces the F-036/F-019 corpus EXACTLY (13/7). USER-CLASSIFIED **INTENDED** (CRT-spine isolation), not a defect → resolution was DOC-side: corrected the `spine_signal_source.py` docstring (was claiming it runs the full CRT→Fusion→Decision→Ultron stack) to state the CRT-only scope.
- Supersedes:    —
- Reversal:      "The research spine (spine_signal_source.py / SpineHypothesis) measures the full production CRT→Fusion→RegimeGovernor→Decision→Ultron stack, as its docstring claimed" -> "It measures the CRT state machine only; the 4-engine fusion veto is gated OFF in backtest by .env (BACKTEST_ENGINE_GATE=0), by design. The full-fusion spine is a separate gate-ON object (~14% fewer trades)."
- Owner:         claude
- Note:          Scope-correction, NOT a conclusion reversal: the fusion gate REMOVES trades (more restrictive), so the gate-ON spine is even smaller-N → the F-019…F-036 entry-information null is unaffected in direction (still INSUFFICIENT/REJECT). What changes is the SCOPE LABEL on the corpus: "the spine" = CRT-only. This corrected F-036's withdrawn fusion-mechanism overclaim (E-001). The one-off gate-ON zone ablation WAS run (`results/research/zone_inertness_gateon/`): the gate runs (audit non-empty, EngineRunner.run called) and vetoes 2/1 CRT entries, but those vetoes are **zone-independent** (removing/tripling zone weight + threshold sweeps all byte-identical) → see F-036 UPDATE. The research default is UNCHANGED (CRT-only by design); gate-ON is a separate live-equivalent lens, not the corpus default. **EPOCH-QUALIFIED 2026-08-06 (F-058):** the "research default" described here is the pre-2026-07-23 epoch. Since 2026-07-23 the active config declares `engine_gate_enabled:true`; `.env` is now an explicit override (WARNs if it disagrees, F-058). Whether the *current* default epoch still reproduces this gate-OFF CRT-only corpus, or requires an override to do so, is unverified — `src/research/adapters/spine_signal_source.py`'s docstring is stale on this point and needs a matching fix. `RF-CRT-STRUCTURE.L5` queues a gate-ON re-measurement (M-GATE-01) to reconcile against the 13→11 / 7→6 figures recorded above under the current config epoch, not merely re-cite them.

---

### F-038 · In the gate-ON fusion the "RR" engine is a GAUSSIAN DUPLICATE — rr_fusion degrades to gaussian on ~all candidate bars [FIX SHIPPED — rr_fusion disabled 2026-06-26]
- Type:          ARCHITECTURE
- Family:        RF-RR
- Contract:      UNKNOWN
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

  **MECHANISM REFINED 2026-07-04 (not reversed) — see F-044.** This block's "layer (2)" diagnosis — *"the rr_fusion model is out-of-distribution / mis-calibrated on live bars even when fed real features"* — is CORRECTED to a more precise root cause: **the confidence GATE is mis-specified for its dimensionality, not the model OOD.** An in-sample probe (`results/rr_confidence_probe/report.json`, n=49,000 training rows through `NanoInferenceEngine`) shows **100% bypass on the model's OWN training data** — a model cannot be out-of-distribution on the data it was fit to, so the bypass cannot be an OOD/calibration property of the model. The observed full-vector confidence ~5e-5 is ≈ the *expected in-distribution floor* `exp(-0.5·dof)` for a rank-27 Mahalanobis form (min in-sample `d_sq`=4.30 already exceeds the `d_sq<2.41` needed to clear `confidence_bypass_threshold=0.3`; mean `d_sq`=26.7 ≈ dof 27, textbook χ²(27)). CONSEQUENCE for F-038's "Option-B retrain": **retraining alone will NOT lift confidence** under the current gate — any well-fit model reproduces this floor. The F-038 *conclusion* (RR=gaussian duplicate when rr_fusion enabled; disable is the correct remediation) is UNCHANGED; only the mechanism label ("model OOD" → "gate mis-scaled to dof") is refined. `CORRECTED: "rr_fusion model is OOD/mis-calibrated even when fed real features" -> "the exp(-0.5·d_sq)<0.3 gate is mis-specified for a rank-27 Mahalanobis distance; the model bypasses on its own training data, so the defect is the gate, not model OOD"`.

---

### F-039 · The L3 dataset-integrity pre-flight is `backtest_v2`-only; every other CandleLoader path relies solely on the inline L1/L2 backstop
- Type:          ARCHITECTURE
- Family:        — (not a market object; see docs/governance/research_family_registry.json)
- Contract:      UNKNOWN
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
- Family:        RF-REGIME-DYNAMICS
- Contract:      UNKNOWN
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

### F-041 · ZoneGate runtime scores through `models/zone_registry.json` (8 zones, HARD gate); stored zone labels ~98% SL-hit are an F-022 labeling ARTIFACT (Phase-5/F-041B RESOLVED 2026-07-05: honest SL≈0.66, 0/8 zones honest-positive → label-quality NOT the rescuable defect) + manifest divergence RECONCILED (F-041A, B1 2026-07-05)
- Type:          GOVERNANCE
- Family:        RF-ZONE-GEOMETRY
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-07-22
- Revalidate-by: 2026-09-25
- Evidence:      Active config `configs/production/v2_multi_2026_04.json` → `engine_runner.zone_registry_path = "models/zone_registry.json"`, `zone_mode = "hard"` (config-verified); `BitNetZoneGate` loads that path ([`src/engines/live_engine.py:202`](../src/engines/live_engine.py), [`src/engines/zone_gate_engine.py:230`](../src/engines/zone_gate_engine.py) fail-open 0.5/pass on error). That file (`schema_version=v2_gaussian`, `source=discover_zones_v1_converted_to_gaussian`, 38-dim, 8 zones) has 6/8 zones with negative `mean_rr` and `sl_hit_rate` 0.959–0.989 (zone_0 n=20,708, tp=0.0132, sl=0.9865, mean_rr=−0.029) in stored meta. `models/zone_gate_registry.json` is a **version manifest** (version-key→`model_file`); its `active:true`→`models/BNBUSDT/.../zone_registry_BNBUSDT_202605_bnb_v1.json` sha256[:16]=`aade29c4f8c5ac9c` ≠ the config-loaded file's `e73e08934add02c9` → manifest ≠ scoring path. **Phase-5 (F-041B) RESOLVED 2026-07-05** — driver [`scripts/research/zone_label_audit.py`](../scripts/research/zone_label_audit.py) + logic [`src/research/zone_label_audit.py`](../src/research/zone_label_audit.py) re-derived ALL 139,942 source opportunities (`logs/BNBUSDT/bnbusdt_training_20260524/opportunities.jsonl`) through the governing `forward_walk(intrabar_fixed)` over the ORIGINAL seeded-KMeans membership. `membership_verification = VERIFIED` (all 8 zones reproduce stored n+mean_rr+sl_hit_rate to 4dp, ruling out a permuted partition — the label-honesty delta is contamination, not re-clustering). Artifact [`docs/analysis/f041b-zone-label-audit-BNBUSDT.json`](analysis/f041b-zone-label-audit-BNBUSDT.json): stored `sl_hit_rate` 0.959–0.989 vs **honest 0.649–0.663** (Δ≈−0.33 every zone) → **CONTAMINATED** — the ~98% SL-hit is an F-022 stream artifact (also sign-flipped: zones 4/5/6 stored `mean_rr`>0 but honest E_net<0). AND no zone clears honest E>0: net-of-cost expectancy −0.17…−0.56R, bootstrap CI entirely <0 ∀8 zones → underlying **HONEST_NO_EDGE** (honest win≈0.34 re-confirms F-023; extends F-025). Separately, runtime Gaussian *argmax* assignment agrees with the label partition only **41.4%** (per-zone 0.06–0.70) (governance sub-finding, distinct from contamination). **RESOLVED 2026-07-22 — see the Note's item (3); the earlier gloss "the live gate partitions differently than the labels describe" is CORRECTED: the live gate does not partition at all.**
- Supersedes:    —
- Reversal:      (intra-session, E-001) "zone_gate_registry.json is empty (0 zones) → ZoneGate may be silently fail-open in production" -> "CORRECTED: zone_gate_registry.json is a *populated version manifest* keyed by version (the 0-zones read was a parse artifact looking for a `zones` list); the scored centroid file is `models/zone_registry.json` (8 zones), loaded as the config directs."
- Owner:         claude
- Note:          TWO distinct facts, do not conflate. (1) CERTAIN now: the SCORING path is `models/zone_registry.json` as a HARD gate, and the version manifest's `active` flag points to a different file (bookkeeping `TruthConflict` per §6.2 — surfaced, NOT auto-reconciled; user decides). (2) RESOLVED 2026-07-05 (Phase-5, F-041B): the stored labels ARE a labeling artifact — honest intrabar_fixed SL≈0.66 ≪ stored ≈0.98 on VERIFIED-identical membership — so label-quality is NOT the dominant/rescuable ZoneGate defect: even honestly relabeled, 0/8 zones carry positive expectancy, so re-training the labels creates no edge. The binding constraint remains the entry-information null (F-019…F-040, F-025), consistent with F-036 (ZoneGate NON_PIVOTAL, ΔG001≡0). Note the live gate never reads these labels (purely geometric) → no runtime/execution risk today; contamination affects research/interpretability/promotion/docs only. (3) **Assignment-parity sub-finding RESOLVED 2026-07-22** (probe `scripts/analysis/zone_assignment_parity_probe.py`, artifact [`docs/analysis/zone-assignment-parity.LATEST.json`](analysis/zone-assignment-parity.LATEST.json); recorded 0.4140 reproduced EXACTLY, delta 0.0 on all 8 per-zone values, so the pipeline is validated before extending it). **The core category error: the runtime SCORES, it never PARTITIONS.** The live decision is `top_scores` → `compute_weighted_cluster_score` → `>= zone_cluster_threshold` → pass/block — a continuous top-k aggregate against a threshold. No record is ever assigned to a zone; `best_zone_id` is telemetry with no downstream consumer (`live_engine.check()` states this in-code). "Assignment parity" therefore measures a partitioning the runtime does not perform, which is why a low value implies nothing about gate behaviour. **Why it is low is now mechanical:** KMeans minimises unnormalised squared-Euclidean over all 38 RAW dims while the Gaussian divides by a global sigma and zero-weights 13 dims — and those 13 zeroed dims carry **99.9983%** of the variance driving the KMeans objective (`volume` alone 97.58%), so KMeans partitioned by volume/price level while the runtime scores candle shape. Judge against the majority-class baseline **0.3264** (not 1/8): 41.4% is ~9pp above trivial, κ=0.238. Measured structure (information only, no authority): all 8 zones show POSITIVE lift over their runtime marginal (so the agreement is weak but real everywhere); the runtime argmax concentrates **77.7%** on zones 2+7 vs their 51.8% label share; margins are tiny corpus-wide (~95% of records have top1−top2 < 0.05), and the per-zone margin gradient is **BIMODAL** — attractor zones 2/7 agree MORE when confident (near-tie instability) while disfavoured zones 0/1/3 fall to ≈0.000 agreement at high margin (systematic re-routing). Two mechanisms operate at once, so no single scalar describes the 41.4%. Anomaly criterion (pre-declared, measured against the RUNTIME marginal — not the label share) selects zones 5/6/7; **zone_3 is NOT anomalous** (lift +0.0495, 2nd smallest — its low parity is explained by the runtime seldom picking it, correcting an earlier "2nd-largest zone yet 0.13" framing that wrongly used label share as the baseline). **F-041A RECONCILED 2026-07-05 (B1, user-approved §6.2):** registered+promoted `v2_gaussian_runtime_2026_07` via `core.model_registry.{register,promote}_zone_gate` so `zone_gate_registry.json` active `model_file = models/zone_registry.json` (sha `e73e0893` == config-loaded) — single-source-of-truth restored, behavior-neutral (manifest is orphaned bookkeeping; production config untouched → hash-neutral). New permanent invariant `tests/test_zone_manifest_runtime_parity.py::test_active_zone_manifest_matches_runtime` (red pre-B1, green post-B1) machine-enforces manifest.active-sha == runtime-sha so this drift class cannot recur. Both halves now resolved → Status VALIDATED. Authority: research/docs + governance-hygiene only (§6.5). Plan: `docs/topics/model-intent-and-feature-ownership.md`.

---

### F-042 · The weekly liquidity-sweep ontology (ICT/CRT Mon+Tue accumulation -> Wed-Fri sweep -> reversal) does NOT clear the M4 gate on FX majors — Program 8 CLOSED
- Type:          ECONOMIC
- Family:        RF-WEEKLY-CALENDAR
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-07-01
- Revalidate-by: 2026-12-28
- Evidence:      Pre-registered in [`docs/research-readiness/program-8-weekly-crt-sweep-preregistration.md`](research-readiness/program-8-weekly-crt-sweep-preregistration.md) BEFORE any run. New geometry module `src/research/weekly_sweep/weekly_range.py` (calendar Mon+Tue ISO-week accumulation range, range-LOCKED only once a Tuesday bar closes so sweeps can only fire Wed-Fri; boundary-cross-then-close-back-inside sweep test reimplementing `crt_engine_v2.RangeDetector.detect_sweep`'s geometry against a WEEKLY range — CRT itself has zero weekly memory) feeds the new `weekly_sweep_reversal` hypothesis (entry OPPOSITE the swept boundary, range-width-derived exit targeting the opposite boundary) through the UNCHANGED M4 QualificationGate (intrabar_fixed + 12bps). Driver `scripts/research/qualify_weekly_sweep.py`, artifact `results/research/weekly_sweep/qualify_weekly_sweep.json`. **0 PROMOTE across all 6 scopes** (5 FX majors + POOLED, same F-035 universe): every scope REJECTs at gate 2 (absolute net expectancy < 0) — EURUSD n=93 E=-0.937R PF=0.298; AUDUSD n=105 E=-0.643R PF=0.424; EURCAD n=109 E=-0.661R PF=0.455; GBPUSD n=107 E=-0.628R PF=0.467; USDJPY n=98 E=-0.313R PF=0.688; POOLED n=512 E=-0.634R PF=0.457. All 6 scopes DO beat their winning control (`random_uniform`, own E -1.67…-2.78R) with permutation p=0.0005 (the seeded floor) — the candidate loses money but reliably loses LESS than a control trading every bar; that relative edge is real (gate 4 passes) but is moot because the absolute-expectancy gate (2) fails first and is load-bearing. Direction×Vol 3×3 diagnostic (POOLED, informational only, `regime_breakdown` in the artifact): 8 of 9 cells net-negative; the lone positive cell (DOJI/EXPANSION, n=13, E=+0.154R) is a single small-N cell — NOT a claim (Authority Ladder §6.5: information ≠ authority; no per-cell significance testing was attempted, by design).
- Supersedes:    — (extends F-019…F-041's directional-consumer-null track record to a genuinely NEW weekly-CALENDAR ontology, distinct from Program 1's next-bar/M15-local frame and Program 2's intraday structural-asymmetry frame — neither tested a Monday/Tuesday accumulation range)
- Reversal:      — (confirms the pre-registered prior; no reversal)
- Owner:         claude
- Note:          Permutation-scope caveat (pre-registered, §7 of the pre-registration doc, verified against `qualification.py:94-128` during design): the M4 permutation test is an exact two-sample permutation over per-*outcome* (per detected weekly-sweep event) RR values — Level-4A-equivalent (naive-shuffle-floor), and cannot by itself isolate weekly-sequence-specific alpha from generic regime clustering. Moot here since the result REJECTed on the absolute-expectancy gate, not the permutation gate. Program 8 CLOSED after this one pre-registered pass — no parameter archaeology (no `min_accumulation_bars`/`sl_range_frac`/window sweep), no automatic continuation variant. Authority: research only (§6.5).

---

### F-043 · A forward Markov P^H regime-transition forecast is REDUNDANT with the current vol level and persistence — Program 4b CLOSED
- Type:          ECONOMIC
- Family:        RF-REGIME-DYNAMICS
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-07-01
- Revalidate-by: 2026-12-28
- Evidence:      Pre-registered in [`docs/research-readiness/program-4b-transition-preregistration.md`](research-readiness/program-4b-transition-preregistration.md) (2026-06-17, design frozen) BEFORE this run. New `MarkovRegimeForecaster` (`src/interpreters/regime_observer.py`: trailing `P_t^H` transition-matrix projection, `w_markov=480`, `h=8`, reuses `RegimeLabeler`'s `S_t` verbatim — never reimplemented) feeds the UNCHANGED `regime_conditioning.evaluate_scope` cross-matrix (`src/research/regime_conditioning.py`), extended ADDITIVELY with a within-tercile-shuffle 5th control (`current_level_series` param, default `None` reproduces Program 4's F-030 artifact byte-identical — re-verified this session by re-running the original driver and diffing), conditioning Program 4's own toy consumers (`expansion_breakout`, `mean_reversion`) on the PREDICTED regime `Ŝ_{t+H}` instead of the contemporaneous one. Hard calibration gate PASSED (BNBUSDT `H_atr=0.885027`, band `[0.855,0.915]`). Driver `scripts/research/qualify_regime_transition.py`, artifact `results/research/regime_transition/regime_transition.json` (determinism re-verified: byte-identical across two independent runs). **0 REGIME_EXPLOITABLE across all 15 scopes** (2 toy consumers × 5 scopes + spine × 5 scopes). Toy consumers: **all 10 combinations resolve to REGIME_REDUNDANT**, well-powered (n=3,645–35,525 per best cell) and statistically significant vs. the label-permutation null (p=0.0025–0.045 ≤ α=0.05) — the apparent uplift is real (`beats_nulls=True` everywhere, e.g. POOLED `expansion_breakout` S_real=0.1705) but BOTH redundancy controls fire on every cell: `redundant_lagged=True` (a stale, same-horizon-lag regime reproduces it — POOLED `expansion_breakout` S_lagged=0.1293 vs. S_real=0.1705) AND `redundant_within_tercile=True` (shuffling the predicted label WITHIN current-level buckets fully or OVER-reproduces it — same cell S_within_tercile=0.1750 ≥ S_real) — meaning the forecast adds ZERO information beyond the current vol level, which F-030 already showed is not economically consumable. Spine: `REGIME_INSUFFICIENT` across all 5 scopes (n=9–10 per cell, matches F-019/F-022's spine-throughput pattern — no claim).
- Supersedes:    — (extends F-030; the pre-registered "different information channel" hypothesis is now TESTED and closed, not merely deferred)
- Reversal:      F-030's Program-4b ledger note "the TRANSITION-forecast channel (anticipating a regime CHANGE) is a genuinely different information channel and is UNTESTED" -> "TESTED: a literal Markov `P^H` forecast of the transition is well-powered and statistically real, but REDUNDANT with information already known at F-030's closure (current level + persistence) — no incremental forecast skill demonstrated."
- Owner:         claude
- Note:          E-001 pre-registered prior (stated 2026-07-01, before running): given F-040 already established a related transition channel is informative-but-non-consumable due to the EXECUTION MODEL constraint, the stated expectation was `REGIME_INFORMATIONAL`/`REGIME_HARMFUL`/`REGIME_INSUFFICIENT` at best. The actual result (`REGIME_REDUNDANT`, decisively, on well-powered cells) is a MORE specific and MORE informative null than the stated prior — it pinpoints WHY (persistence + level, not the execution model) at least for these toy consumers, which never reach the execution-model question at all since they are killed earlier, at the redundancy gate. **Doc-drift correction (§6.2):** the Funding Ledger's "Program 4b: ... RESEARCH (pre-registration pending)" entry (2026-06-17) was stale after F-040 (2026-06-26) closed a DIFFERENTLY-CONSTRUCTED "Program 4b/4c/4d" grouping (an MTF candle-state conjunction, `docs/research/preregistration-program-4bcd.md` — a distinct hypothesis, never tested this literal Markov forecast); finalized this turn. The pre-registration's reserved finding number "F-031" was superseded by an unrelated governance finding — this result is registered as **F-043**, the corrected assignment. Authority: research only (§6.5).

---

### F-044 · The RR-fusion confidence gate is MIS-SPECIFIED for its dimensionality — it bypasses to Gaussian on 100% of inputs including in-sample (refines F-038's mechanism)
- Type:          ARCHITECTURE
- Family:        RF-RR
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-07-04
- Revalidate-by: 2026-12-31
- Evidence:      In-sample probe `results/rr_confidence_probe/report.json` (`scripts/analysis/rr_confidence_probe.py`, READ-ONLY): all **49,000 training rows** of `models/rr_model.json` run back through `NanoInferenceEngine` → **in-sample bypass fraction = 100.0000%**; **min in-sample `d_sq` = 4.30 > the `d_sq < 2.408` needed** to clear `confidence_bypass_threshold=0.3` (`rr_pattern_miner.py:339-342`), so NOT ONE training point passes; max confidence = 0.116. Mechanism: `confidence = exp(-0.5·d_sq)` where `d_sq` is a Mahalanobis distance over a **rank-27** quadratic form (38 canonical dims − 11 `zero_indices`; static 1B validation in the artifact confirms `len(conf_mu)=len(conf_P)=38`, dense 38×38 precision, constant-zero columns == `zero_indices` exactly). An in-distribution rank-27 Mahalanobis has `E[d_sq]=27` (measured mean 26.7, median 21.5 — textbook χ²(27)), so in-distribution confidence ≈ `exp(-13.5) ≈ 1.4e-6 ≪ 0.3`. Faithfulness: the probe's `d_sq` replication matches `engine.predict()` confidence to 3.75e-16 (float noise), status agreement 100%. The legacy 3-feature `score_dict()` stub ALSO bypasses 100%.
- Supersedes:    — (refines F-038's mechanism; F-038 conclusion + remediation unchanged)
- Reversal:      F-038's "the rr_fusion model is out-of-distribution / mis-calibrated on live bars even when fed real features" -> "the gate `exp(-0.5·d_sq)<0.3` is mis-specified for a rank-27 Mahalanobis distance; the model bypasses on its OWN training data (100% in-sample), so the defect is the GATE, not model OOD — and retrain alone cannot fix it (any well-fit model reproduces the `exp(-0.5·dof)` floor)."
- Owner:         claude
- Note:          Decisive test = a model cannot be OOD on its own training data (100% in-sample bypass ⇒ gate defect, not model defect). CONSEQUENCE: F-038's "Option-B retrain" is necessary-but-insufficient — the gate must be re-specified (dof-aware: χ²-tail `Q(dof/2, d_sq/2) < p` or `d_sq/dof` threshold) BEFORE any retrain or re-enable. This finding grants **no authority** to re-enable `rr_fusion` (stays `enabled:false`, §6.5 Authority Ladder — correctness ≠ production weight; re-enable needs a measured ΔG001, tracked separately). Track-3 gate-fix is additive + config-behind + parity-proved with default `legacy_scalar` (byte-identical). **Calibration refinement 2026-07-05:** the empirical training-d_sq is heavy-tailed vs χ²(dof) (P99 empirical 101.4 ≫ theory 47.0; P95 56.9 vs 40.1), so a theoretical χ²-tail p mis-estimates real bypass (`chi2_tail p=0.01` → 7.33% empirical bypass, not 1%). Any future non-legacy operating point is therefore chosen by the CANONICAL rule `target_bypass_fraction → empirical d_sq cut` (from the training-d_sq CDF), not a theory p-value; a `percentile` gate mode (bypass iff `d_sq > cut`, most robust to the heavy tail) was added alongside `chi2_tail`/`dof_scaled`. Calibration table + empirical CDF in `results/rr_confidence_probe/report.json` (`empirical_calibration`). Still inert (default legacy, rr_fusion disabled). Authority: architecture/governance only.

---

### F-045 · The RR-model economic kill-test is INDETERMINATE — apparent OOS discrimination is measured against F-022-contaminated labels
- Type:          GOVERNANCE
- Family:        RF-RR
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-07-05
- Revalidate-by: 2026-12-31
- Evidence:      `results/research/rr_shadow_value/report.json` (`scripts/research/rr_shadow_value.py`, READ-ONLY, 5-fold CV on the 38-dim BNB corpus, n=49,000). The RR model's RAW outputs (ridge `expected_rr`, GNB `p_win` — computed BYPASSING the confidence gate so the F-044 gate doesn't hide the signal) show APPARENT OOS discrimination: `AUC(p_win,y_win)=0.605` vs shuffle-null 0.505, `rr_corr=0.074`, top-decile-by-RR mean `y_rr=+0.042` vs random `−0.078`. **But the labels are contaminated:** `y_win`/`y_rr` derive from the trade `outcome`/`rr_achieved` field (`rr_dataset_builder.py:125-206`), the SAME stream F-022 found only 36.8% self-consistent, and F-041B is precedent that this exact contamination produced labels that FLIPPED on `forward_walk(intrabar_fixed)` re-derivation. `y_rr` is also near-degenerate (every win == +1.0 exactly → `y_rr ≈ y_win`, not a continuous RR target). So the apparent discrimination is NOT credible economic evidence — the model may be predicting the *mislabeling structure*, not real outcomes.
- Supersedes:    — (extends F-022 / F-041B contamination pattern to the RR training dataset)
- Reversal:      Prior expectation "a correctly-fed, correctly-gated RR is a clean RETIRE (per F-001/F-002/F-023/F-025)" -> "kill-test is INDETERMINATE, not RETIRE: RR shows apparent (weak) OOS discrimination, but on a contaminated label, so no Keep/Retire verdict is defensible yet."
- Owner:         claude
- Note:          **REQUIRED next step for any Keep/Retire:** re-derive `y` via `forward_walk(intrabar_fixed)` on the source opportunities+candles (the F-041B remedy) and re-run the kill-test. **Two E-001 pre-registration corrections (governance succeeded):** (1) the pre-registered Tier-3 rule had a logic bug — it auto-RETIREd when the heavy-tail filter didn't *improve* signal, even though Tiers 1-2 already showed signal WITHOUT the filter ("filter doesn't add" ≠ "no signal"); corrected to a diagnostic. (2) The pre-registration lacked a LABEL-VALIDITY gate (Tier 0), which is the actual binding constraint. Caught before registering a false RETIRE. This finding grants NO authority; `rr_fusion` stays `enabled:false`. Authority: research/governance only (§6.5).
- Update:        **2026-07-21 — REQUIRED next step COMPLETED.** Clean L3 labels (`forward_walk(intrabar_fixed)` net 12bps) + preregistered 5-fold kill-test under `RR_L1_FREEZE_2026_07_21_V1` → see **F-059**. F-045's original claim remains VALIDATED: the 2026-07-05 contaminated-label kill-test was INDETERMINATE and must not be cited as Keep/Retire. Contaminated AUC≈0.605 does **not** transfer to clean labels (clean AUC≈0.51). This update grants **no** production authority.

### F-059 · Clean-label RR kill-test (L1 freeze protocol) classifies KEEP_CANDIDATE research-only — modest OOS discrimination, still negative mean R; no fusion authority
- Type:          ARCHITECTURE
- Family:        RF-RR
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-07-21
- Revalidate-by: 2026-10-31
- Evidence:      Epoch kill-test `results/rr_research/epoch/RR_L1_FREEZE_2026_07_21_V1/kill_test/report.json` (`scripts/research/rr_kill_test_clean_l3.py`). Protocol: signed L1 `RR_L1_FREEZE_2026_07_21_V1` (`protocol_hash=521fc88f…`), L3 clean dataset n=**139,942** (features L2 PIT-clean production pipeline; y = `forward_walk(intrabar_fixed)` net 12bps; entry stream geometry-only). 5-fold CV trains ridge+GNB on train folds; OOS heads **confidence-gate bypassed** (F-044). Tier0 label_validity **PASS** (frac win∧y_rr≈1.0 = 0.0). Tier1: rr_corr=**0.167** (>0.03), PR-AUC=0.490 vs shuffle 0.482 (margin +0.02 alone fails; disc_pass via rr_corr OR), AUC=0.512 vs shuffle 0.498. Tier2: top-decile mean y_rr=**−0.154** > random-decile **−0.434** (still negative absolute). Classification under prereg: **KEEP_CANDIDATE**. Overall mean y_rr=**−0.436**. Hard flags: RR_FUSION_REENABLE false.
- Supersedes:    Completes F-045's required clean re-test; does **not** delete F-045 (contaminated-test history preserved)
- Reversal:      F-045 "no Keep/Retire yet" (on clean path) -> "KEEP_CANDIDATE research-only on clean labels under frozen protocol"; contaminated F-045 AUC~0.60 is **not** confirmed economic discrimination
- Owner:         grok
- Note:          **§6.5:** KEEP_CANDIDATE ≠ production weight ≠ architecture. Mean R and top-decile R remain **negative** — ranking skill vs random is not expectancy. `rr_fusion` stays `enabled:false`. No promote. Authority: research/docs only.

### F-060 · The live Gaussian channel is an UNPARAMETERIZED kernel that degenerates to a near-CONSTANT — the deferred FM-031 scale defect, consumed
- Type:          ARCHITECTURE
- Family:        RF-GAUSSIAN
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-07-22
- Revalidate-by: 2026-12-31
- Evidence:      Three source-verified claims, each independently checkable. **(1) ZERO LEARNED PARAMETERS.** `HeuristicGaussianEngine.compute` (`src/engines/heuristic_gaussian_engine.py:325-333`) computes `exp(-(x-mu)^2/2sigma^2)`, `x=(ema_diff+tanh(momentum_score))/2`. `mu`/`sigma` resolve through `_normalize_registry_entry` (`:42-53`), which defaults `mu=0.0, sigma=1.0` (`:49-50`). All 11 entries of `models/gaussian_registry.json` were dumped: **none carries a `mu` or `sigma` key** (they carry version/model_file/feature_schema/schema_version/metrics/trained_at/active). The defaults therefore fire on a SUCCESSFUL load — live score is `exp(-x^2/2)`, byte-identical to the no-registry path; the trained `.json` bundles are never opened by the live engine. **(2) DEGENERATE TO A CONSTANT.** Measured over the full corpus (70,002 bars x 4 majors = 280,008): score mean 0.8825-0.8838, std 2.9e-03…1.24e-02, min 0.870, and `|tanh(momentum_score)|>0.999999` on **93.42% (SOL) / 98.12% (BNB) / 99.64% (ETH) / 99.90% (BTC)** of bars. Mechanism: `momentum_score = close.diff()/atr` (`feature_pipeline.py:765`) divides an ABSOLUTE price change by a RELATIVE atr (`atr = atr_14_raw/close`, `:718-721`), giving range +/-4622…+5766 (FeatureHealth log) so `tanh` saturates to exactly +/-1; with `ema_diff` ~1e-3, `x` pins at +/-0.5 and — since `mu=0` makes the kernel SYMMETRIC, discarding the sign — the score is `exp(-0.125)=0.8825` almost always. Live-run confirmation (gate-ON BNBUSDT): every emitted `gaussian_score` in the FLOW:COLLECTOR stream is 0.8824-0.8842 with `meta.x` in [-0.5003,+0.4999]. **(3) WRONG TRAINER AUDITED + F-022 CONFIRMED.** `docs/governance/gaussian_lineage_audit.md:68,185` names `train_pipeline.run_gaussian_update`, which produced NONE of the 4 artifacts on disk; the builder of record is `scripts/training/phase5_calibration.py` (`run_calibration:623` -> `train_gaussian:642`, dataset `from_opportunities:382`), whose labels are `float(rec.get("rr_achieved", 0.0))` (`:434`) read raw from the F-022 stream (36.8% self-consistent) with no `forward_walk` re-derivation anywhere in the Gaussian training path — upgrading the audit's "may inherit contamination" (`:45`) to CONFIRMED. Its docstrings at `:387`/`:391` ("unbiased ground-truth labels", "this is the unbiased training path") are contradicted by F-022/F-041B. Floor: `tests/test_gaussian_live_parameterization.py` (6 tests; fails if `mu`/`sigma` are ever added, which would be a live-behavior change).
- Supersedes:    Refines `gaussian_lineage_audit.md`'s `TRAINED_ARTIFACT = INERT` and F-005's "trained model unwired"; does not reverse either
- Reversal:      "Registry active entries supply mu/sigma to the heuristic" (`gaussian_lineage_audit.md:76,160`) -> **CORRECTED**: the registry read is a NO-OP, supplying nothing at any fidelity. The distinction matters — "INERT" reads as "trained weights unused at reduced fidelity"; the truth is that no learned parameter reaches the scoring path at all.
- Owner:         claude
- Note:          **SCOPE / E-001 CALIBRATION.** This finding does NOT discover the dimensional defect behind claim (2) — `market_ontology.yaml:253-257` already registers it (`known_issue: close_delta (absolute price) / dimensionless atr -> SCALES with price level`, `replacement_identity: FM-031`, `migration_class: FORMULA_CORRECTION_DEFERRED`), and F-053 certified the corrected FM-030/FM-031 variants while deliberately leaving them inactive. What is new is the **CONSUMPTION CONSEQUENCE**, which nobody had connected: the deferred correction does not merely make a feature scale-dependent, it collapses a live fusion channel into a constant. `tanh` is the amplifier — any input of magnitude >~10 saturates, and the legacy identity guarantees magnitudes in the thousands. This is the first demonstrated case of `FORMULA_CORRECTION_DEFERRED` having a *decision-surface* cost rather than a representational one, and it raises the priority of the FM-030/031 activation question (which remains gated and is NOT authorized here). **Claim (2) is a DESCRIPTIVE measurement, not an economic claim** — that the channel is near-constant does not by itself establish it is harmful, worthless, or removable (a constant at weight 0.2 still shifts the fused score against `tier_*` thresholds, i.e. it acts as a calibration bias). Pivotality is measured separately by `scripts/research/diagnose_gaussian_pivotality.py` (F-036 ledger-sha method, seam `HeuristicGaussianEngine.compute`, gate forced ON; injection neutrality self-check PASSED byte-identical on BNBUSDT). **RESULT (2026-07-22, `results/research/gaussian_pivotality/gaussian_pivotality.json`, body_sha256 `8b3613b5…`): `GAUSSIAN_INFORMATION_INERT` — and stronger than pre-registered.** All THREE cells (baseline / pinned-at-saturation 0.8825 / pinned-0.5) produce byte-identical trade ledgers on every instrument (BNB 11/11/11 sha `9bcba138`, ETH 4/4/4 `25a7e34f`, BTC 5/5/5 `6326e7fc`, SOL 6/6/6 `f6ba7dd2`); baseline counts reproduce F-037's gate-ON 11/4/5/6 exactly, confirming the fusion gate really ran. So not only does the channel's VARIATION move no trade (information test), even a 0.38 LEVEL shift to the neutral vote moves no trade (level test) — the channel is non-pivotal on BOTH axes, consistent with F-036 (fusion decisions are CRT-dominated / veto-independent). This is a proof (exact zero, no bootstrap needed), NOT an expectancy claim: pooled gate-ON n=26 is below the `min_samples: 30` floor, so the ablation establishes non-pivotality but grants no economic verdict on the channel. Grants **NO** authority (§6.5): no re-weight, no removal, no `gaussian_impl=ml` switch, no retrain, no promote. Residual (recorded, NOT fixed): 7 of 11 registry entries dangle; `v4_mirrored` has no artifact yet `ui_kits/crt_dashboard/data.js:4,145,324` shows it ACTIVE; `auto_train_from_opportunities.py:98` omits `--gaussian` so the nightly trainer hard-exits rc=1; `get_active_gaussian()` is hardcoded to EURUSD (`model_registry.py:637-640`) which has no `__active__` key, forcing the Phase-5 `NoOpScorer`; the `gaussian_scorer` config block's only consumer (`crt_gaussian_scorer.py`) has zero production importers. Authority: architecture/governance only.

### F-061 · The FM-022/023 dimensional mix is a DECISION-surface defect on crypto, not a representational one — four consumers degenerate to constants and the `dual_engine` thresholds are inert; correction is now config-gated (inactive)
- Type:          ARCHITECTURE
- Family:        RF-FEATURE-ONTOLOGY
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-07-22
- Revalidate-by: 2026-12-31
- Evidence:      **THE ARITHMETIC.** `FM-022 ema_spread = (ema_fast-ema_slow)/atr` and `FM-023 momentum_score = close_delta/atr` (`feature_pipeline.py` `compute_canonical_ema_features`) divide an ABSOLUTE-price numerator by the close-relative `atr` (`atr_14_raw/close`). Therefore `legacy == corrected * close` exactly — the defect's magnitude IS the instrument's price level. Verified as a closed form to float32 precision (max rel err 9.9e-08 over 3,000 BNBUSDT bars) in `tests/test_fm030_031_normalization_basis.py`. **THE CONSEQUENCE (read-only probe, full corpora via `FeaturePipeline.run()`).** Median `|ema_spread|`: BNBUSDT 320.3 (close≈647), BTCUSDT 38,110 (close≈88,480), EURUSD 0.528 (close≈1.14); corrected: 0.471 / 0.457 / 0.471 — i.e. the corrected identity is instrument-scale invariant and the legacy one is not. Against the ACTIVE config's `engine_runner.dual_engine` thresholds (`trend_strength_threshold=0.15`, `momentum_threshold=0.3`, `v2_multi_2026_04.json`), FOUR consumers degenerate on crypto: **(1)** `detect_regime` (`src/core/engine_runner.py:150`) returns `"trend"` on **98.86% (BNB) / 99.94% (BTC)** of bars vs 54.57% on EURUSD — under the corrected identity 52.70% / 52.75% / 50.11%, i.e. it discriminates and is instrument-invariant; **(2)** `breakout_engine` (`:165`) `score = clip((|spread|+|momentum|)/2, 0, 1)` is pinned at exactly 1.0 on **99.99% / 100.00%** of bars (corrected: 6.75% / 6.78%); **(3)** `heuristic_gaussian_engine.py:329` `tanh(momentum_score)` saturates on **98.78% / 99.94%** (this is F-060's mechanism, here shown to be one instance of a general pattern); **(4)** `gate_intelligence.py:237` REVERSAL intent scores `1 - min(1, |mom|)` → constant **0.0** on crypto. So the thresholds are TUNABLE but INERT on crypto and binding only where `close ≈ 1` (FX) — a threshold sweep on crypto could never have moved anything. THREE other consumers read only the SIGN (`momentum_score > 0`) and are invariant to the correction: `execution_planner.py:364`, `crt_engine_v2.py:2138`, `sl_tp_comparator.py:83`. **THE REMEDIATION (this session).** FM-030/031 promoted from ontology `migration_candidates:` prose to first-class registered identities (`derived_math.ema_spread_atr` / `momentum_score_atr`, registry-dispatched, never `eval`'d), selected by a new strict config key `feature_pipeline.normalization_basis` ∈ {`atr_relative`, `atr_absolute`}. Default is `atr_relative` = the legacy math verbatim; parity proof = the XAUUSD freeze-pin vector SHA is UNCHANGED (`tests/test_feature_layer_freeze.py` green) plus a 12-assertion floor (`tests/test_fm030_031_normalization_basis.py`) pinning the closed form, scale invariance (100x price leaves FM-030/031 unchanged and multiplies FM-022/023 by 100), scalar↔pipeline parity, and fail-closed config discipline (missing key → KeyError, unknown value → ValueError, no silent fall-through). Corrected arm is reachable ONLY via the non-promoted shadow config `v2_multi_dimfix_shadow_2026_07.json` (differs from active in exactly one value; key-diff verified). Freeze waiver: `FM-030-031-DIMENSIONAL-MIX-MIGRATION` in `feature-layer-freeze-pin-2026-07-20.json`.
- Supersedes:    Generalizes F-060 (Gaussian saturation) from one channel to the whole dimensional-mix consumer set; extends F-053's certification of FM-030/031 from "mathematically sound" to "measurably consequential". Reverses neither.
- Reversal:      The ontology's `migration_class: FORMULA_CORRECTION_DEFERRED` (2026-07-12) framed the defect as representational — a feature that "SCALES with price level". **CORRECTED → `FORMULA_CORRECTION_CONFIG_GATED`**: it also silently disables four live scoring consumers on crypto. The 2026-07-12 record is preserved in place (the `migration_candidates:` block is retained and marked `SUPERSEDED_BY`, per §6.2 rule 4), not deleted.
- Owner:         claude
- Note:          **DESCRIPTIVE / MECHANISM ONLY — grants NO authority (§6.5).** The saturation percentages are arithmetic facts about the feature distribution, NOT a claim that the correction earns money, that the legacy arm costs money, or that FM-030/031 may be activated. Activation would additionally require (a) demonstrated ΔG001 improvement and (b) recalibration of the `dual_engine` thresholds, which are tuned to the legacy magnitudes and are deliberately NOT recalibrated in the shadow arm (recalibrating them would confound the A/B). `ACTIVE_VERSION` unchanged; FM-030/031 stay `active: false`; no retrain of `rr_model` / gaussian-38 / BitNet (all inactive or INERT on the active patch per F-004/F-005/F-038/F-060, so none blocks and none is disturbed); the four magnitude-sensitive consumers are untouched. **E-001 calibration:** a "constant regime label" is not automatically harmful — F-060's own ablation found the Gaussian channel non-pivotal (`GAUSSIAN_INFORMATION_INERT`, byte-identical ledgers), and F-036 found the fusion path CRT-dominated, so the prior is that these degeneracies may cost nothing economically. That is exactly why the economic question is routed to a shadow measurement rather than asserted here. Shadow driver: `scripts/research/dimensional_mix_shadow_diagnostic.py` (forces `BACKTEST_ENGINE_GATE=1` — the affected consumers live inside `EngineRunner.run()`, which the gate-OFF research path never calls, F-037/F-058; the F-036 method). **MEASURED 2026-07-22 (BNBUSDT, gate-ON; frozen record `docs/governance/fm030_031_implementation_validation-2026-07-22.json`, floor `tests/test_fm030_031_implementation_validation.py`):** the implementation is VALIDATED on all four questions. **(1) The gated path executes** — the corrected arm emits four rejection reasons only the RegimeGovernor can produce (`regime_trend_no_direction` ×1, `regime_range_no_direction` ×2, `neutral_low_confidence` ×1), unreachable unless FM-030/031 reached `detect_regime` through the production `PROD_VERSION` path. **(2) The legacy arm is byte-identical across the change** — trade-ledger SHA `9bcba138775d4109` on all NINE runs (5 pre-change 2026-07-18, 4 post-change 2026-07-22), the same SHA F-060's pivotality artifact recorded; XAUUSD feature-matrix SHA also unchanged. **(3) The decision surface changes exactly as predicted** — `REGIME_CLASSIFICATION` is emitted on *change only*, and over 70,080 candles the legacy arm emits **1** event (the initial `null→trend`, i.e. the regime label is a literal constant and the 0.15/0.3 thresholds never bind) while the corrected arm emits **7** across trend/neutral/range. **(4) The ledger delta is attributable to the identity alone** — corrected is a strict SUBSET (11→7, **zero** additions), the 4 dropped trades (`CRT-0004/0006/0007/0013`) equal the 4 new regime rejections, surviving trades keep byte-identical geometry, `total_setups`=13 in *both* arms (so the CRT state machine never diverged), the two configs differ in exactly one behavioral key, and the corrected ledger `9e28abef01761758` reproduced on 3 independent runs. **ECONOMICS: INSUFFICIENT, no claim** — legacy E −0.3865 (n=11, PF 0.509) vs corrected E −0.3864 (n=7, PF 0.5108), Δ +0.0001R; both net-negative, n ≪ 30, quarantined under `NON_AUTHORITATIVE_ECONOMICS`. Consistent with F-019…F-043 and with F-060's own `GAUSSIAN_INFORMATION_INERT`: a degenerate scoring layer is not automatically a costly one. **A DESIGN ASSUMPTION WAS FALSIFIED (and corrected before it propagated):** the driver inherited BitNet's caveat "entry sets are NOT nested — a reject resets the CRT state machine". True for BitNet, which vetoes *inside* `UltronRiskEngine.approve_with_soft_conf`; **false here**, because the basis is consumed only downstream of CRT, so the regime layer is a pure veto and the sets nest cleanly. The driver's docstring/report now state the corrected claim with the original retained (§6.2 rule 4), and `nested` is reported per run so a future break is visible. **Scope caveat:** measured on the BATCH pipeline path (`backtest_v2` constructs `FeaturePipeline`). The LIVE ingress (`live_engine_hook` / `FeatureStore`) is a separate surface and is NOT covered by this knob — that is consumer-alignment work under M16, not this program. Authority: architecture/governance only.

### F-062 · [FIX SHIPPED 2026-07-31] The feature-DAG spine was stale against schema v4.0, so `feature_surface_query --summary` reported `surface_status: CLOSED` while 3 of 39 canonical slots had no certification-ledger row
- Type:          GOVERNANCE
- Family:        — (not a market object; see docs/governance/research_family_registry.json)
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-07-31
- Revalidate-by: 2026-12-31
- Evidence:      `scripts/analysis/feature_dag_layers.py`'s hand-maintained `_NODES` dict still declared the v3.0 names `wick_size`/`macd_hist` after schema v4.0 (2026-07-22, SCHEMA-V4-VECTOR-MIGRATION) renamed the canonical slot to `candle_range` and split `macd_hist` into `macd_hist_raw`/`macd_hist_z`. Recomputing `build_dag()` before the fix gave `missing_canonical=['candle_range','macd_hist_raw','macd_hist_z']`, `n_canonical_covered=36/39` — yet the stale artifact `docs/governance/feature_dag_layers.LATEST.json` (dated 2026-07-14) still claimed `[]`/38, and `scripts/governance/feature_surface_query.py --summary` printed `surface_status: CLOSED` with `closure: {CLOSED: 36, None: 3}` in the same breath — a self-contradictory report. Consequence: those 3 slots had no DAG node and therefore no certification-ledger row (`scripts/governance/feature_certification_state.py status` showed `{PROMOTED_PRODUCTION: 46, SUPERSEDED: 2}` = 48, reading fully closed while 3 shipping vector dims were uncertified). FIX: renamed the three `_NODES` entries to the v4.0 names with correct deps/layers (`feature_dag_layers.py:79-116`), which certified all three (`candle_range`/`macd_hist_raw`/`macd_hist_z` now `PROMOTED_PRODUCTION`). Post-fix: `feature_dag_layers.py` reports `is_dag=True nodes=49 canonical=39/39 missing_canonical=[]`; `feature_surface_query --summary` reports `closure: {'CLOSED': 39}`, no `None` rows. Byte-identity preserved: XAUUSD (`n=19,922`) 39-dim vector SHA-256 unchanged before/after (`4cd69d921e69303576291a70bbccec6b43d0992fa8c2d19f654733ba215a2343`), `SCHEMA_HASH`/`FEATURE_ORDER_HASH` unchanged, `config_hash` untouched. Also de-literalized the `== 38` assertion in `tests/test_feature_dag_layers.py` and the residual `/38` text in `feature_dag_layers.py`'s own report strings.
- Supersedes:    —
- Reversal:      "`feature_surface_query --summary`'s `surface_status: CLOSED` means the canonical feature surface is fully certified" -> "That claim was FALSE for 3/39 dims since 2026-07-22 (the report's own `closure` breakdown already showed `None: 3` alongside the `CLOSED` headline — the inconsistency was visible, just unexamined). A `CLOSED` headline is only trustworthy when its own `closure` breakdown carries zero `None` rows."
- Owner:         claude
- Note:          Declaration+fix only (Semantic Layer Certification Audit, 2026-07-31, Tier 1 — hash-neutral). Grants no new authority; does not reopen or alter any other CLOSED surface in the `CLAUDE.md` Closure & Authority Index. Authority: governance/hygiene only.

### F-063 · [FIX SHIPPED 2026-07-31] Two canonical vector slots (`trend_strength`, `candles_since_retest`) had no ontology identity because a same-name execution-code collision blocked registration; both now registered, the CRT engine's distinct quantity separated under a new FM id
- Type:          ARCHITECTURE
- Family:        RF-FEATURE-ONTOLOGY
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-07-31
- Revalidate-by: 2026-12-31
- Evidence:      `market_ontology.yaml` reserved FM-064 (`trend_strength`) and attempted-then-withdrew FM-065 (`candles_since_retest`) on 2026-07-24 because registering either name tripped `tests/test_feature_math_lint.py`'s ownership floor red on an unrelated same-named local: `src/core/engine_runner.py:151` computed `abs(ema_spread)` into a local literally named `trend_strength` (an unrelated regime-detection quantity, `dual_engine.detect_regime`'s threshold input — nothing to do with the ontology's rolling-z-score `trend_strength`); `src/config_layer/crt_engine_v2.py`'s `approve()`/`approve_with_soft_conf()` wrote `state.current_candle_index - state.retest_candle_index` (bars since the RETEST CANDLE, feeding the transient BitNet input dict) into a local dict key also named `candles_since_retest` — a DIFFERENT quantity from the pipeline's canonical vector column of the same name (bars since the last SWEEP, `feature_pipeline.py:988-997`), the exact FM-027/FM-028 (F-050) collision pattern. `tests/test_feature_lineage.py`'s `_UNREGISTERED_VECTOR_SLOTS` ratchet recorded both as the ONLY two of 39 canonical slots with no ontology identity. FIX: renamed the `engine_runner.py:151` local to `ema_spread_abs` (pure rename, zero behavior change) and registered FM-064 `trend_strength`; registered the CRT engine's distinct quantity as a NEW identity, FM-070 `candles_since_retest_state` (`src/features/derived_math.py::candles_since_retest_state`, dispatched via `src/features/registry/derived_registry.py` and `src/features/fm_resolve.py`'s Phase-2 CRT slice), renamed `crt_engine_v2.py`'s two emission sites to write `candles_since_retest_state` internally with an explicit legacy-name alias (`_bn_in["candles_since_retest"] = ...`) added ONLY at the BitNet call boundary — the same CH-002 pattern already used for FM-027/FM-028's `retest_depth`/`disp_strength` aliases. `_UNREGISTERED_VECTOR_SLOTS` is now empty; `tests/test_feature_lineage.py`, `tests/test_feature_math_lint.py`, `tests/test_semantic_registry.py` all pass; XAUUSD 39-dim vector SHA-256 unchanged (byte-identical — the BitNet input dict's legacy-key value is numerically unchanged, and `use_bitnet=false` on the active config regardless, F-004).
- Supersedes:    —
- Reversal:      "Resolving the `candles_since_retest` collision requires renaming one emission, which is a MODEL_INPUT_CHANGE and out of scope for a declarative-only change set" (2026-07-24 withdrawal note) -> "The rename is local to two transient dict-construction sites inside `crt_engine_v2.py`'s approve* methods, never escapes those functions except via an explicit legacy-aliased BitNet input that is numerically unchanged — a zero-behavior-change refactor, not a MODEL_INPUT_CHANGE. `_ORIGINAL_BASELINE_IDS` (the frozen GD-pin ledger) did not need to change; the correct resolution is a new registered identity (FM-070) plus a rename, not a lint allowlist."
- Owner:         claude
- Note:          Declaration+fix only (Semantic Layer Certification Audit, 2026-07-31, Tier 1 — hash-neutral). Authority: architecture/governance only.

### F-064 · The FM-022/023 dimensional-mix decision-surface defect (F-061) generalizes from crypto to XAUUSD — measured, not activated
- Type:          ARCHITECTURE
- Family:        RF-FEATURE-ONTOLOGY
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-07-31
- Revalidate-by: 2026-12-31
- Evidence:      F-061 measured FM-022 `ema_spread`/FM-023 `momentum_score`'s price-scaling defect on BNBUSDT/BTCUSDT/EURUSD. Re-measured on XAUUSD (`data/mt5/XAUUSD_M15.csv`, `FeaturePipeline.run()`, n=19,922 bars post-warmup): `momentum_score` ranges [-13,515.8, +16,595.0] and `ema_spread` ranges [-6,657.5, +5,856.6] (both should be O(1) under the corrected FM-030/FM-031 identity). `|tanh(momentum_score)| > 0.999` on **99.70%** of bars (the `heuristic_gaussian_engine.py` saturation mechanism F-060/F-061 already characterized on crypto). `|ema_spread| > 0.15` (the active `engine_runner.dual_engine.trend_strength_threshold`) on **99.99%** of bars. A synthetic ×100 price-shift probe confirms the mechanism directly: `ema_spread`/`momentum_score` scale by **exactly 100.000×**, while every other ATR-normalized canonical dim (`disp_strength`, `volatility_ratio`, `retest_depth`, `liquidity_distance`, `body_ratio`, `atr`) scales by **1.000×** (unchanged) — the closed-form relation `legacy == corrected * close` (F-061) confirmed on a fourth, non-crypto instrument.
- Supersedes:    Generalizes F-061 (measured on BNBUSDT/BTCUSDT/EURUSD) to XAUUSD; does not reverse or narrow it.
- Reversal:      — (extension, not a reversal)
- Owner:         claude
- Note:          **DESCRIPTIVE / MECHANISM ONLY — grants NO authority (§6.5), same discipline as F-061.** `normalization_basis` stays `atr_relative` (the SUPERSEDED-in-the-certification-ledger identity remains ACTIVE by explicit decision); FM-030/FM-031 stay `active: false`. This session added a one-time startup log warning (`src/features/feature_pipeline.py::_warn_once_if_superseded_basis`, fires once per process when `normalization_basis == "atr_relative"`) — log-only, changes no emitted feature value, no config, no decision path; XAUUSD 39-dim vector SHA-256 unchanged. Activation would additionally require demonstrated ΔG001 improvement plus `dual_engine` threshold recalibration, per F-061's own Note. Authority: architecture/governance only.

### F-065 · The participation (volume) channel is declared in two places on the live decision path and consumed by neither — `gate_intelligence`'s liquidity vol_score is a structural constant zero, and `volume_spike` is declared in the CRT state resolver's predicate vocabulary but referenced by no state
- Type:          ARCHITECTURE
- Family:        RF-FEATURE-ONTOLOGY
- Contract:      UNKNOWN
- Status:        OPEN
- Confidence:    Certain
- Validated:     2026-07-31
- Revalidate-by: 2026-12-31
- Evidence:      **(H7)** `src/core/gate_intelligence.py::GateIntelligence._liquidity_score` computes `vol_score = min(1.0, max(0.0, (vol/vm20)/2.0)) if vm20 > 0 else 0.0`, documented as a 50% component of the returned liquidity score (the other 50% is sweep-extent). `vm20 = features.get("volume_ma20", 0.0)` — grep-confirmed absent from both `src/runtime/live_engine_hook.py` and `src/runtime/backtest_v2.py`, the only two production feature builders; `volume_ma20` exists only as a non-canonical intermediate pipeline column (`src/features/feature_pipeline.py:432`, no vector slot) and a hardcoded test fixture (`src/config_layer/execution_planner.py:502`). Consequence: `vm20` defaults to `0.0` on every real bar, so `vol_score` is a structural constant `0.0` and `_liquidity_score` always resolves to exactly `0.5 * sweep_score` — never the documented blend. This feeds `GateIntelligence.decide` at `gate_weight_liquidity=0.20`. **(H8)** `configs/formulas/market_crt_states.yaml`'s `feature_states:` block declares `volume_spike: [NoSpike, VolumeSpike]` (line 81) for the CRT state resolver's predicate vocabulary; grep-confirmed this is the ONLY occurrence of `volume_spike` in that file — no CRT state's `when:` block references it, so the resolver's predicate set never actually gates on participation.
- Supersedes:    —
- Reversal:      — (newly discovered gap, not an overturned prior claim)
- Owner:         claude
- Note:          **Declaration only — no code behavior changed.** Registered as `configs/formulas/market_ontology.yaml` semantic-registry node `SEM-004` (`execution_behaviours`, `knowledge_status: CHARACTERIZED`) plus an inline pointer comment at `gate_intelligence.py`'s `vm20` assignment, and an inline annotation on `market_crt_states.yaml`'s `volume_spike` line. Fixing H7 (emitting `volume_ma20` from a production feature builder) changes live decision-path scores on every bar — explicitly OUT of scope for a hash-neutral documentation/declaration pass; it requires a separately authorized behavior-change program (§6.5: tunability/reachability is not authority). Authority: architecture/governance only.

### F-066 · MT5-sourced `session`/`hour_of_day` (FM-052) are derived from broker-server time labeled as UTC — 53.36% of XAUUSD bars carry the wrong session label; config-gated correction shipped, inactive by default
- Type:          ARCHITECTURE
- Family:        RF-SESSION-TIME
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-08-01
- Revalidate-by: 2026-12-31
- Evidence:      Investigation opened from a blind-labeling descriptive-fidelity program (`docs/research/preregistration-blind-label-descriptive-fidelity.md`) preparing a Comet chart-comparison prompt; a 516-day boundary census on `data/mt5/XAUUSD_M15.csv` (every day `01:00→23:45`, zero Sunday bars, DST-invariant) showed the timestamp column cannot be UTC. TWO independent tests, pre-registered, both CONFIRMED: **(A, assumption-free)** cross-correlating XAUUSD's 15-min realized-range profile against Binance BTCUSDT (genuinely UTC-epoch klines) finds the best alignment shift is exactly `-3h00m` Apr-Sep (r=0.675) and exactly `-2h00m` Nov-Feb (r=0.709) — on-the-hour, differing by precisely the DST step. **(B, event-based)** NFP release (08:30 America/New_York, first Friday/month) lands at the SAME server-clock time (15:30) in BOTH seasons (8/11 summer, 4/12+2-adjacent winter) — season-invariance is exactly what an EET/EEST-tracking server predicts; true-UTC stamps would alternate 12:30↔13:30. **New sub-finding: the DST rule is US, not EU** — the daily `01:00→23:45` boundary holds through the 2025-03-10…27, 2025-10-27…31, and 2024-10-28…11-01 US/EU DST-mismatch windows; under EU (Europe/Athens) rules the boundary would shift during those weeks, and it doesn't. Mechanism: `src/inout/mt5_candle_fetcher.py:186` calls `datetime.fromtimestamp(r["time"], tz=timezone.utc)` on MT5's `copy_rates` `time` field, which is a documented broker-server epoch, not UTC. Measured impact: **25,225/47,275 bars (53.36%)** change `session` label under the correction (ASIA 12,381→14,448; CLOSED 6,008→4,085; systematic flows, not noise — e.g. 5,488 CLOSED bars are actually NEWYORK).
- Supersedes:    —
- Reversal:      — (newly discovered defect, not an overturned prior claim)
- Owner:         claude
- Note:          **Scope-bounded — affects MT5-sourced corpora ONLY.** Every Binance-sourced corpus (`data/binance/*.csv`) uses genuinely UTC epochs and is unaffected; F-017 (session policy not a promotable lever) and F-021 (`SELECTION_IS_SESSION_ONLY`) were measured on BNBUSDT = Binance data and are UNTOUCHED by this finding. Only MT5-derived session work (XAUUSD, the F-035 FX arm) is in scope. **Two surfaces, deliberately treated differently:** the FEATURE (`session`/`hour_of_day`, `feature_pipeline.session_windows_utc`) is a mislabel — fixed. The FILTER (`crt_engine.session_windows`, the live trading-eligibility gate) was empirically tuned ON broker-time data; converting its timestamps while keeping its band numbers would silently move the actually-traded hours by 2-3h and cannot be compensated by a static band (the required correction is seasonal). The filter is therefore left untouched — a live-vs-broker-time relabeling of it is a separate, evidence-gated economic decision, not a bug fix. **Shipped, config-gated, INACTIVE by default** — new strict-read key `feature_pipeline.session_timestamp_basis` (`src/features/feature_pipeline.py`, `_FP_CFG_KEYS`), mirrors the `normalization_basis`/F-061 pattern exactly: `"broker_local"` (DEFAULT on all 3 configs carrying a `feature_pipeline` section — byte-identical to every pipeline run before this key existed, proven by `tests/test_session_timestamp_basis.py::test_broker_local_is_byte_identical_to_raw_timestamp_hour`) vs `"utc_corrected"` (derives from the new `src/features/broker_clock.py::mt5_server_to_utc`, an NY-DST-aware conversion — NOT Europe/Athens). Hash-neutral: `feature_pipeline` is a top-level config section, not `params` (`config_hash` verifies `params` only, confirmed via `production_config.py:346-348`); raw `timestamp` column itself is never mutated by either arm (only `hour_of_day`/`session` derivation reads through the selector). **Scope warning caught same-session (E-001):** an initial code-comment draft claimed `utc_corrected` was "a no-op on Binance data" — false; the conversion has no provenance detection and would wrongly shift already-true-UTC timestamps if misapplied. Corrected before landing; regression `test_utc_corrected_is_not_a_noop_on_true_utc_timestamps` pins the correct (dangerous) behavior instead of a false safety claim. Activating `utc_corrected` on the ACTIVE config is a separate, explicitly-gated decision (feature-vector SHA changes on ~53% of bars ⇒ `feature-layer-freeze-pin-2026-07-20.json` re-pin + revalidation of anything trained on `session`/`hour_of_day` required) — NOT made by this session. Authority: architecture/governance only (§6.5) — grants no promotion, no fusion weight, no live-filter change.

### F-067 · Soft-confirmation `update_emas` fires twice per candle during the RETEST window — compresses the fast/slow spread in a trend (α_eff=2α−α²), NOT the "overly sensitive" inflation an earlier bug-trace claimed; measured, not fixed
- Type:          ARCHITECTURE
- Family:        RF-CRT-STRUCTURE
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-08-04
- Revalidate-by: 2026-12-31
- Evidence:      A multi-model bug trace flagged a double `EngineState.update_emas` call during soft confirmation and characterized it as `EMA(EMA(close))` making momentum "overly sensitive" (more false approvals). Source-verified the call sites are real but the mechanism is backwards: `crt_engine_v2.py:2629` fires unconditionally at the top of `process_candle`, every candle, before the state-machine chain; `crt_engine_v2.py:2998` fires again inside `elif self.state.evaluating_soft_conf:` — there is **no `RETEST` state branch** in `process_candle`, so every RETEST-state candle falls through to this `elif`, and the second update lands before `approve_with_soft_conf` (`:1953`) reads the EMAs inside `compute_soft_confirmation` (`:1898`, reads at `:1919`). Re-applying the same update is NOT nested composition — it is equivalent to one update at effective α_eff = 2α−α² (closed form, `tests/test_soft_conf_ema_probe.py::test_double_update_equals_closed_form_alpha`, exact to 1e-12): for the production `ema_fast=2`/`ema_slow=5`, α_eff_fast=8/9 (span 1.25, not 2) and α_eff_slow=5/9 (span 2.6, not 5). Both EMAs hug price harder; `f_mom` reads the SPREAD, so the spread COMPRESSES in a trend and the term systematically UNDER-states directional momentum in exactly the setups it exists to reward — approval gets HARDER, not easier. It bites twice (weight in `C_linear` and again via `min(f_body,f_mom)` weak-link, `crt_engine_v2.py:1939,1942`). EMAs seed once and are never cleared by `reset_to_range`, so the perturbation is path-dependent for the life of a run. OBSERVATION_ONLY probe `scripts/analysis/soft_conf_ema_double_update_probe.py` (monkeypatches `EngineState.update_emas` in-process only, no `src/` edit) ran the full XAUUSD corpus (`data/mt5/XAUUSD_M15.csv`, 47,275 bars): n=17 soft-conf evaluations (matches the RETEST=17 state-distribution count exactly — internal consistency check), trend-only mean spread ratio (double/single) = 0.4673 (10 evaluations) vs the closed-form prediction of ~0.457–0.467 — CONFIRMED. The chop leg of the pre-registered prediction (toy alternating-series inflation ~1.34x) did NOT replicate on real data (chop-only ratio 0.9698, 7 evaluations) — real market "chop" includes near-zero EMA crossings that can sign-flip between arms (e.g. candle_index=37273) rather than scale like a clean alternating synthetic series; reported as observed, not forced to fit. 0/17 tier-bucket flips (`first_divergence_idx=null`) — the fix is ledger-neutral on available XAUUSD evidence. Self-consistency: the probe's pure reimplementation of `compute_soft_confirmation`'s arithmetic (`crt_engine_v2.py:1898-1951`) reproduces the real function's output with `max_c_self_consistency_err=0.0` (bit-exact) across all 17 real evaluations plus 5 synthetic parametrized cases in the test floor. Artifact: `results/analysis/soft_conf_ema_double_update.LATEST.json`. Floor: `tests/test_soft_conf_ema_probe.py` (12 tests, all pass).
- Supersedes:    —
- Reversal:      "Double EMA update = `EMA(EMA(close))`, makes momentum overly sensitive, causes MORE false approvals (Medium odds)" -> "Double application = effective α=2α−α² (a DIFFERENT closed-form quantity, not nested composition), COMPRESSES the trend spread, makes `f_mom` UNDER-state momentum, making approval HARDER, not easier — the received characterization had the mechanism and the direction both backwards."
- Owner:         claude
- Note:          **No code fix in this pass — OBSERVATION_ONLY by user decision ("measure first, fix after").** The finding validates the mechanism and measures its magnitude on the only available XAUUSD evidence; it does NOT decide whether to remove the duplicate call at `crt_engine_v2.py:2998` — that is a separate BEHAVIOR_CHANGE_AUTHORIZED turn, gated the same way F-068 below was. n=17 is thin (XAUUSD is throughput-starved, F-035/F-045-class corpus limits apply) — the 0-flip / ledger-neutral result is a property of THIS corpus and this config's tier thresholds, not a general economic claim; a different instrument or a threshold near one of the observed S-values could flip. Authority: research/architecture only (§6.5) — grants no fix authority, no activation, no production-behavior claim.

### F-068 · Shadow-memory TTL off-by-one — the `[DEADLOCK FIX]` reset fall-through meant a configured TTL of N yielded only N−1 usable bars; fixed
- Type:          ARCHITECTURE
- Family:        RF-CRT-STRUCTURE
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-08-04
- Revalidate-by: 2026-12-31
- Evidence:      `reset_to_range`'s `[DEADLOCK FIX]` fall-through (`crt_engine_v2.py:2655`, deliberate — lets a sweep fire on the freshly-seeded range on the SAME candle rather than losing a bar) means that when an HTF-triggered reset creates shadow memory (`_create_shadow` at `crt_engine_v2.py:1734`, sets `pending_displacement_ttl = config.pending_displacement_ttl_candles`), the RANGE branch of `process_candle` runs on that SAME candle, immediately after creation — and, pre-fix, unconditionally decremented `pending_displacement_ttl` there too. A configured TTL of N therefore yielded only N−1 usable subsequent bars. Fixed by adding `EngineState.pending_displacement_created_idx` (set once at creation to `candle.index`) and guarding the RANGE-branch decrement (`crt_engine_v2.py:2700-2701`) to skip when `candle.index == pending_displacement_created_idx`. The new field is cleared on all four existing teardown paths (consumed at `:2856`, `SHADOW_LEAK` at `:2820`, TTL-exhaustion at `:2709`, non-HTF-reset expiry at `:1762`) — verified by grep, no fifth stale field introduced. Regression floor `tests/test_shadow_ttl_lifecycle.py` (6 tests) drives a real `CRTEngine.process_candle()` through the actual `ResetLogic.should_reset` → `reset_to_range` → RANGE-branch fall-through path (not a reimplementation of the guard). `test_shadow_survives_configured_ttl_then_expires` was verified to FAIL against the pre-fix guard by temporarily reverting it, running the test (observed sequence `[2,1,0,0]` instead of the expected `[3,2,1,0]` — exactly the predicted one-bar-short pattern), then restoring the fix and re-confirming green. XAUUSD full-corpus before/after (`results/ttl_before` vs `results/ttl_after`, identical config/corpus otherwise): `SHADOW_PENDING` 43→51 (+8), `SWEEP` 6995→6987 (−8), `DISPLACEMENT`/`EXPANSION`/`RETEST`/`EXECUTION`/`RANGE`/`total_setups` byte-identical — a bounded, contained delta consistent with the wider shadow-resumption window and nothing else.
- Supersedes:    —
- Reversal:      A separate bug-trace rated this "Low — clearly documented in the code with the comment 'same bar burns 1'." That comment does NOT exist in `crt_engine_v2.py` (grep-verified) — it appears only in a prior session's `assistant_project.md` entry, never in source. CORRECTED: the mitigating rationale was fabricated; the defect was real and unmitigated. The fix adds the comment the claim assumed already existed.
- Owner:         claude
- Note:          Correctness-only; no economic claim. `total_setups` is unchanged at 1 on the full 47,275-bar XAUUSD corpus — at that N, no economic conclusion (positive or negative) is derivable from this fix; report the state-distribution delta, not an implied backtest-quality improvement. Authority: architecture/governance only (§6.5).

### F-069 · CRTStateResolver cannot reach engine parity through configuration alone — EXPANSION entry uses a structurally different construction, not a mistuned threshold
- Type:          ARCHITECTURE
- Family:        RF-CRT-PARITY
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-08-05
- Revalidate-by: 2026-11-03
- Evidence:      CRT Semantic Parity Report (`reports/crt_semantic_parity_report.md`), machine-readable `results/analysis/crt_semantic_parity.classified.json`, pre-registration `docs/research/preregistration-crt-semantic-parity.md`, ledger `results/analysis/crt_parity_sweep/ledger.jsonl` (33 candidates). Config-only (`--injection none`, `engine_mode=exit`) baseline over the full 47,197-bar aligned XAUUSD M15 corpus: 88.1560% (41,607/47,197); RANGE/SWEEP/DISPLACEMENT already 96.4–97.6% recall, EXPANSION only 10.77% (498/4,625). A full coordinate-descent sweep (6 parameter groups, 32 non-baseline candidates covering every resolver-side threshold with an engine-side counterpart) found the best anti-Simpson-safe candidate at 88.4590% (`thresholds.body_ratio_min=0.55` + `thresholds.max_expansion_age_candles=250`, +0.30pp) — EXPANSION recall barely moved (10.16%). Several higher-raw-agreement candidates (up to 89.77%) were found and correctly REJECTED by the anti-Simpson guard because they achieved the gain by zeroing EXPANSION recall to 0.00% entirely (Simpson's-paradox trade). Mechanism (source-verified, `src/features/crt_state_resolver.py`): with the settled `thresholds.continuous_disp_to_expansion: false`, `_resolve_from_features` skips `_expansion_entry_allowed()` — the resolver's analogue of the engine's ATR-extension gate — entirely for DISPLACEMENT/SWEEP→EXPANSION; the resolver can only reach EXPANSION via the declarative `when: {displacement_flag:[Displacement]}` predicate or sticky-dwell carry-over, a different construction from the engine's `try_displacement_to_expansion()` state machine (`src/config_layer/crt_engine_v2.py`). Volume-weighted classification of the 22 residual confusion-matrix cells: Category C (`C-GEOMETRY`, divergent construction) = 96.1% of mismatched bars (6 EXPANSION-involving cells, dominated by EXPANSION→RANGE 3,374 and RANGE→EXPANSION 870), Category D (`D-UNKNOWN`, uninvestigated) = 3.8% (14 cells, each ≤50 bars), Category B (`B-UNREACHABLE-STATE`) = 0.1%. Unweighted cell-count aggregation is separately reported as Inconclusive (14/22 cells unclassified) — both views are stated in the report; the volume view is load-bearing for this finding because cell magnitudes span 3 orders of magnitude (1 to 3,374 bars).
- Supersedes:    —
- Reversal:      Corrects two stale/contaminated in-session estimates before this finding's own measurement: the historical instrument (`scripts/research/crt_state_confusion_matrix.py`) ran with the resolver's `engine_reset`/`engine_state_to` oracle-assist parameters UNCONDITIONALLY enabled, producing 64–99% figures that do not answer "configuration alone" (the resolver was fed the engine's own transitions). The script's injection axis was made explicit (`INJECTION_MODES = (none, reset, state_to, full)`); `none` is the only mode measuring the stated question and is now this program's primary metric.
- Owner:         claude
- Note:          Two structurally unreachable states (EXECUTION: `_continuous_gates_pass` requires a `score`/`risk_score`/`crt_score` feature absent from `CANONICAL_FEATURES`; RESOLUTION/EXPIRED: declared `when: {}` in `configs/formulas/market_crt_states.yaml`) are Category B by deductive code fact, not a statistical claim, so classified even at low n (EXECUTION n=5). RETEST (17/17 mismatched, n at the `MIN_CELL_N=15` power floor) is a downstream cascade of the same EXPANSION defect — `_continuous_gates_pass` requires memory state EXPANSION/RETEST to enter RETEST — not an independent finding. Determination: **structurally config-unreachable** — no threshold value in `market_crt_states.yaml` bridges a different construction; closing it requires a resolver code change, which is out of this program's repository freeze. Grants no authority to modify the resolver or engine (§6.5); an optional gated `--promote` write-back of the +0.30pp winning threshold values into the tracked `market_crt_states.yaml` was deferred pending explicit user confirmation. Stage B (engine-side `CRTConfig` sensitivity, one-way diagnostic, promotion forbidden) run separately; see the report for its results.

### F-070 · M-GATE-01: on the active config epoch, the 4-engine fusion gate vetoes 0/30 CRT-committed entries across crypto majors — F-037's recorded 14% gate-ON reduction (BNB 13→11, SOL 7→6) does not reproduce today
- Type:          ARCHITECTURE
- Family:        RF-CRT-STRUCTURE
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-08-06
- Revalidate-by: 2026-11-04
- Evidence:      `scripts/research/gate_measurement_m_gate_01.py` (SITS-registered, SCOPE measurement, authority NONE per §6.5) — two-arm A/B via unmodified `ProductionSpineSource`, same corpus, same `spine.prod_version=v2_multi_2026_04` (active config): OFF arm forces `BACKTEST_ENGINE_GATE=0` (the pre-2026-07-23 F-037 object), ON arm leaves the env var unset so `backtest.engine_gate_enabled:true` governs (the current F-058 object). Non-vacuity guard PASSED: `EngineRunner.run()` call count == entry count on every instrument (BNB 13, ETH 5, BTC 5, SOL 7 — not the 0-call failure mode F-037's original probe hit). Result, all 4 crypto majors, full historical window: ON entry set == OFF entry set BYTE-IDENTICAL (same indices, same timestamps; `removed_by_gate_indices: []` and `added_by_gate_indices: []` on every instrument). Cross-checked against the run's OWN native artifact, not just the adapter's parsing: `BNBUSDT_summary.json` reports `rejected_trades: 0`, `rejection_reasons: {}`, report.txt "Approved / Rejected: 13 / 0" — confirms the zero-veto result independently. F-037's recorded gate-ON figures (BNB 13→11, SOL 7→6, measured 2026-06-25) do NOT reproduce: measured today is 13→13 and 7→7. Artifact: `results/research/gate_measurement_2026_08_06/summary.json`.
- Supersedes:    —
- Reversal:      Does NOT reverse F-037's own historical measurement (that 2026-06-25 run is presumably accurate for its own config/code state, per §6.2 rule 4 — history is preserved). What changes: "the gate-ON epoch removes ~14% of gate-OFF entries" is no longer descriptive of the ACTIVE config today. "The fusion gate is a real, if modest, veto" -> "under the active config, on this historical corpus, the fusion gate is currently a complete pass-through (0/30 vetoed)."
- Owner:         claude
- Note:          CONFIDENCE=Likely, not Certain, because the CAUSAL MECHANISM is a plausible, dated, well-grounded hypothesis, not independently isolated in this run (E-001 discipline — do not upgrade a timing correlation into a proven mechanism). Between F-037's measurement (2026-06-25) and this one, at least two ARCH remediations targeting exactly this veto path shipped and are independently VALIDATED in this same index: F-038 (rr_fusion disabled 2026-06-26 — the day after F-037 — because it degraded to a gaussian duplicate whose confidence gate drove spurious low-confidence rejections) and F-048 (the DecisionEngine RR gate REMOVED 2026-07-24 — economic reward:risk moved solely to UltronRiskGate, downstream of this measurement point). Confirmed in the active config: `engine_runner.fusion_engine.rr_fusion.enabled = false`. Either or both plausibly explain the vanished veto pressure; this run does not isolate which. Grants NO authority (§6.5) — does not re-enable rr_fusion, does not claim the fusion gate is "inert" in general (only that it is a pass-through on THIS specific 30-entry historical corpus under the active config), and does not economically qualify anything. Registers `RF-CRT-STRUCTURE.L5` in `docs/governance/research_family_registry.json` (cell moves from bare F-037 to F-037+F-070, still `UNVERIFIED_HISTORICAL` pending a sealed `MC-*` instance). Closes the F-058 residue for this run specifically: `resolved_engine_gate_mode` is written into `summary.json` per arm, not merely WARNed. Open: isolate F-038 vs F-048 as the driver (a third arm with rr_fusion forced back on, pre-F-048 DecisionEngine config, would disambiguate) — not done here, out of this measurement's scope. Authority: architecture/research only.

### F-046 · `wick_size`/`body_ratio` had a divergent (dead) definition; canonical = body/candle_range, now unified behind one primitive
- Type:          ARCHITECTURE
- Family:        RF-FEATURE-ONTOLOGY
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-07-05
- Revalidate-by: 2026-12-31
- Evidence:      Two definitions existed, not three. CRT engine `Candle` property (`src/config_layer/crt_engine_v2.py` `wick_size = high-low`, `body_ratio = body/(high-low)`) ≡ batch pipeline (`src/features/feature_pipeline.py` compute_canonical_price_features). The lone outlier was the single-row `src/features/crt_feature_builder.py` (`wick_size = (high-low)-body_size` → `body/total_wick`, unbounded), which has ZERO call sites (grep) — DEAD code (sibling in `archive/dead_code/`). Canonical = `body/candle_range` (bounded [0,1]) — the only definition the CRT displacement gate `body_ratio >= 0.70` is coherent against, and the one both live paths compute. Unified all paths through new immutable `src/features/candle_math.py` (parity-tested `tests/test_candle_math.py`; the WHAT-layer `configs/formulas/market_ontology.yaml` + `src/features/formula_registry.py` declare it, `tests/test_formula_registry.py` locks the binding). Byte-identical: 210 golden/determinism tests green (CRT+pipeline were already canonical).
- Supersedes:    —
- Reversal:      Session overclaim "three interpretations of wick_size, ambiguous which is canonical" -> "TWO definitions; the CRT engine matches the batch pipeline (body/range); the third path (crt_feature_builder body/total_wick) is DEAD; canonical is body/range; ZERO runtime impact (the live BitNet path — itself off, F-004 — reads the canonical cached `disp.body_ratio`, never the dead builder)." Caught before registering a false 'production-impacting bug'.
- Owner:         claude
- Note:          Grants NO authority. Any future change to the ACTIVE `body_ratio` denominator (the `market_ontology.yaml` variants) is a policy change requiring threshold recalibration (`body_ratio_min=0.70`) and is gated (§6.5) — the variants are research-time only. Authority: architecture/governance only.

### F-047 · The market ontology is now the AUTHORITATIVE source for feature mathematics (geometry + deterministic derived metrics), mechanically enforced; the live path re-derives a NON-CANONICAL `body_ratio` [flagged, Phase-B deferred]
- Type:          ARCHITECTURE
- Family:        RF-FEATURE-ONTOLOGY
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-07-07
- Revalidate-by: 2026-12-31
- Evidence:      Extends F-046 from geometry to deterministic NORMALIZED metrics and adds enforcement. (1) The ontology (`configs/formulas/market_ontology.yaml`) gained a `derived_metrics` section (disp_strength/retest_depth/ema_spread/momentum_score/volatility_ratio parity_verified; liquidity_distance/liquidity_pressure_score registered) with per-feature stable IDs (`FM-0NN`), `version`, `lifecycle`, `depends_on` DAG and `source_of_truth` provenance; formulas transcribed VERBATIM from `feature_pipeline.py`. (2) The registry is the authoritative implementation, split into `src/features/registry/{primitive,composition,derived}_registry.py` behind the stable `formula_registry` facade + new scalar `src/features/derived_math.py`; NEVER `eval`'d. (3) TWO enforcement mechanisms + one exhaustiveness invariant: a parity battery binds the vectorized pipeline columns to the scalar registry (`tests/test_derived_math.py`); an OWNERSHIP-lint (`scripts/analysis/feature_math_lint.py`, semantics-not-syntax — flags assignment to a registered name whose RHS is not a registry call; transport/dict-reads/clamps exempt) fails on any NEW re-derivation; and `tests/test_feature_lineage.py` proves every feature resolves Feature→registry→impl→parity→vector with an acyclic OHLC-grounded graph. (4) The lint census (live surface) pinned 10 pre-existing divergences as grandfathered debt — the load-bearing one: `src/runtime/live_engine_hook.py:361-362` computes `wick_size = (high-low)-body_size` then `body_ratio = body_size/wick_size` = **body/total_wick**, the ontology's research-only `wick_based` variant (`market_ontology.yaml`), NOT canonical body/candle_range. `src/config_layer/crt_engine_v2.py:2539` (byte-identical inline body_ratio) was routed through `candle_math.body_ratio` (parity-neutral, determinism-gated). Hash-neutral (WHAT layer is outside the production-config hash).
- Supersedes:    —
- Reversal:      —
- Owner:         claude
- Note:          Enforcement-only; grants NO authority (§6.5 — a knob becoming registry-owned grants tunability, not production authority). **ADJUDICATION UPDATE 2026-07-07 (Matrix v1, [`docs/analysis/feature-math-divergence-adjudication.md`](analysis/feature-math-divergence-adjudication.md)):** the 10 grandfathered divergences were adjudicated read-only into a durable GD-001…GD-010 ledger (`durable_key` AST-fingerprint + append-only retirement manifest + monotonic ratchet). The earlier "live DECISION impact UNVERIFIED / lands in an auxiliary dict" is SHARPENED with a source-verified call-chain (E-001: tightening, not reversal): live `body_ratio` (=body/total_wick) IS decision-reachable IN CODE — `pipeline_mode.py:160`→`LiveEngineHook`→`_build_ohlcv_and_auxiliary`→FeatureStore(no recompute)→`EngineRunner.run():570`→`crt_compute:654`→`crt_engine:22 features['body_ratio']`→`compute_scores s_breakout:40`→`fusion:787`→APPROVE/REJECT (resolving a two-trace contradiction; `trade_id="Test:"` is a cosmetic label, :654 is inside live `run()`). SCOPE PRESERVED: execution is CONDITIONAL (live-hook path only; backtests use the canonical pipeline; live PnL F-010-unverified, F-037 backtests run gate-OFF) → still NOT a confirmed production-loss claim; a gate-ON decision-flip rate (Gate 2) will bound *potential* impact only. Gate-2 drift measurement applies to exactly GD-001/GD-002 (same_quantity+non_equivalent+decision-reachable); `scoring_engine:31` & `crt_engine_v2:1355` are name-collision DISTINCT quantities (rename, not formula fixes — `move=features['disp_strength']`); the `upper/lower_wick` ratios are decision-unreachable diagnostics; `crt_sweep_taxonomy.candle_geometry` is dead. **MATRIX v2 (Gate-2 read-only probe, `reports/feature-math-drift-probe.md`, BNBUSDT 19,922 bars):** the non-canonical `body_ratio` differs on **97.0%** of bars, is ≥ canonical on **99.2%** (systematic inflation, since candle_range≥total_wick), and **violates the [0,1] bound on 46%** (body_ratio>1); it changes the real CRT score on **96.7%** of bars (|Δ| p95 0.060). **Step-7c decision-flip = NOT MEASURED (RETRACTED 2026-07-08, E-001 second correction).** A first attempt (`feature_math_decision_flip_probe.py`) reported 0 flips but FAILED causal-validity controls: corpus parity (score probe 19,922 vs decision probe 70,002 candles), single-variable isolation (A/B differed in body_ratio AND wick_size), and — fatally — NO positive control proving the harness can DETECT a flip, so the 0 is uninterpretable. **V1–V10 validation (`reports/decision-flip-validation.md`) → POSITIVE_CONTROL_NOT_CONSTRUCTIBLE:** `run()` STRUCTURALLY never executes (the DecisionEngine rr gate compares RREngine polarity `rr_ratio∈[0,1]` vs `rr_threshold=1.5` → `low_rr` always; 0/70,002 executes) AND is a VETO whose only pass-path (`zone_gate_invalid` bypass) is body_ratio-independent; body_ratio reaches only the fused SCORE → moves the reject-REASON but never execute/veto ⇒ **decision-inert at the run() boundary BY STRUCTURE** (source-confirmed, not a counterfactual). A per-candle run() harness is the wrong instrument; the correct one is a **backtest-ledger diff** (predicted 0, NOT yet empirically measured). `observed_decision_flips` stays not_measured (empirically). GD-001/002 stay at Matrix-v1 status (same_quantity, non_equivalent, decision-reachable), urgency UNDETERMINED pending the ledger diff. F-010/F-037 → NO production-loss claim either way. Incidental (separate findings): session-encoding mismatch (pipeline 0=london vs adapter 0=asia); `zone_gate_invalid` always-rejects in run(). All remediation deferred to per-GD Phase-B findings. Boundary frozen at geometry + deterministic derived metrics. **AUTHORITY CLAIM DOWNGRADED 2026-07-08 (F-049 bypass audit):** the "mechanically enforced / AUTHORITATIVE" claim is QUALIFIED — the ownership-lint enforces only NAME-assignments in 5 live-spine dirs (`features/core/config_layer/engines/runtime`); it does NOT cover `scripts/tools/tests/governance/uat/strategies/analytics/utils/research`, nor Subscript (`df["body_ratio"]=`) or Attribute (`self.x=`) writes anywhere. So the WHAT layer is NOT yet repository-wide authoritative; see F-049 (geometry canonicalization + blast-radius audit, IN PROGRESS). Zero-range policy also diverges across producers (return-0.0 vs 0.001-denominator-floor). Authority: architecture/governance only.

---

### F-048 · The DecisionEngine RR gate consumed candle polarity against a reward/risk threshold — RESOLVED by removing the gate: DecisionEngine is now semantic-approval only; economic RR is owned solely by UltronRiskGate [RESOLVED 2026-07-24]
- Type:          ARCHITECTURE
- Family:        RF-RR
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-07-08
- Revalidate-by: 2026-12-31
- Resolution:    [SHIPPED 2026-07-24] The ownership question ("who owns RR?") was decided by the user: DecisionEngine answers ONLY "is this a valid market opportunity?" (semantic evidence — score / p_win / zone validity / weak-component) and knows nothing of fees / slippage / capital / reward:risk. The RR gate was **removed** from `DecisionEngine.evaluate` (not shimmed): `_economic_rr_from_fusion` deleted, both `rr_threshold` reads deleted, the `low_rr` reject path deleted — `src/core/decision_engine.py`. `engine_runner.py` fusion_ctx no longer stamps `rr`/`rr_semantic` (the dead shim keys); `candle_polarity` is retained on the ctx for the collector audit record only (non-decision). Economic reward:risk is owned SOLELY by `UltronRiskGate.evaluate` Check 2 (cost-taxed `min_rr_ratio`, `ultron_risk_gate.py:228`), after `ExecutionPlanner` derives SL/TP (contract D) — this was already the real economic gate; the DecisionEngine duplicate is gone. Config: `decision_engine.rr_threshold` retained-but-RETIRED (sibling marker `rr_threshold__retired`; hash-neutral — the key is in `decision_engine`, not `params`; no strict read remains). PARITY: no production/backtest path ever supplied an economic RR to DecisionEngine (`engine_runner` omits `true_rr`, only test injectors set it) ⇒ removal is definitional, not behavioral; on the sole XAUUSD gate-ON candidate in 47,275 bars the reject fires at `zone_gate_invalid` three gates BEFORE the (now-removed) RR gate, so the ledger is byte-identical. Tests: `tests/test_rr_contract_wiring.py` rewritten (contract C = DecisionEngine owns no RR; contract D = UltronRiskGate owns economic RR); `tests/test_crt_fixes.py` unchanged and green (its injected `rr:2.0` was above the old threshold ⇒ inert either way). UNBLOCKS: the GD-001/GD-002 body_ratio remediation and instrument selection that this finding's Note said were "BLOCKED behind this" are now unblocked (not acted on here).
- Evidence:      RREngine (`src/engines/rr_engine.py:2,79,81`) is the "Candle Polarity Index (formerly misnamed RR Engine)": `rr_ratio = round(polarity,4)` with `polarity = max(upper_body,lower_body) ∈ [0.5,1]` — a **legacy field name** (`semantic:"candle_structure_quality"`, docstring "not forward RR"; git `b34d6a8 stable before rename`). `engine_runner.py:957-960` wires `fusion_ctx["rr"] = engine_results["rr"]["rr_ratio"]` (the polarity) into `DecisionEngine.evaluate`, which rejects `low_rr` when `fusion["rr"] < rr_threshold=1.5` (`decision_engine.py:144`; config `v2_multi_2026_04.json:130`). Since polarity ≤ 1 < 1.5, `low_rr` fires on EVERY candle after the score gate → `run()` can never `execute` (empirical: **0/70,002** executes). The consumer's INTENDED contract is a TRUE RR ratio: `tests/test_crt_fixes.py:224` gets `execute` only by injecting `fusion={"rr":2.0}`. The REAL RR check is elsewhere — `UltronRiskGate` reads the ExecutionPlanner SL/TP-derived trade `rr_ratio` (genuine reward/risk, can be ≥1.5) at `ultron_risk_gate.py:230-245`, SEPARATE from RREngine exactly as its docstring states. DOWNSTREAM: `ExecutionPlanner.plan` hard-gates on `run()=="execute"` (`execution_planner.py:208-213`) → the live path `live_engine_hook` (`run→ExecutionPlanner→UltronRiskGate→alert`, `:682/708/717/863`) can structurally **never admit a trade** (consistent with F-010 live-PnL-unverified; live_engine_hook's only caller is `agent/modes/pipeline_mode.py:160`, not a verified production loop). NOT a research/backtest defect: gate-OFF backtests + qualification never call `run()` (F-037) — the CRT state machine is the trade admitter there; gate-ON backtests use `run()` only as a VETO (`backtest_v2.py:2182`).
- Supersedes:    —
- Reversal:      "CANDIDATE mismatch — remediation gated on intent adjudication (mis-wire vs dormant-by-design)" -> "RESOLVED as an OWNERSHIP decision: the intent question is moot because the gate does not belong in DecisionEngine at all. Removed, not adjudicated-then-shimmed. DecisionEngine = semantic approval; economic RR = UltronRiskGate. The earlier working-tree shim (`_economic_rr_from_fusion`, skip-if-polarity) was a half-measure that left DecisionEngine holding economics; it is deleted."
- Owner:         claude
- Note:          RESOLVED 2026-07-24 by removing the gate (see Resolution above). The original source-confirmed MISMATCH stands as historical evidence (kept below), but the "remediation gated / BLOCKED behind this" framing is superseded — the resolution did not require deciding mis-wire-vs-dormant because the correct architecture removes the gate regardless. The pre-shim mechanism the Evidence paragraph describes (`engine_runner.py:957-960` wiring polarity into a `rr_threshold=1.5` gate) is the state as of 2026-07-08; current code no longer wires it. Sibling candidates still open (separate findings, not filed here): session-encoding mismatch (pipeline 0=london vs adapter 0=asia); `zone_gate_invalid` always-rejects in `run()` (surfaced again by the F-048/Layer-7 XAUUSD survey — zone score 0.77 yet `valid`=False); `rotate_session_log.py` same-date-archive overwrite. Authority: architecture/governance only.

### F-050 · `retest_depth` had TWO mathematical definitions under one name — CRT emission renamed to FM-027/FM-028 [REMEDIATED CH-002]
- Type:          ARCHITECTURE
- Family:        RF-FEATURE-ONTOLOGY
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-07-09
- Revalidate-by: 2026-10-31
- Evidence:      docs/governance/build_manifests/CH-002-f050-emission-rename.impact.json; src/config_layer/crt_engine_v2.py; src/config_layer/crt_gaussian_scorer.py; src/features/derived_math.py; configs/formulas/market_ontology.yaml; tests/test_crt_adversarial_closure.py — **CH-001 (2026-07-08):** registered FM-027 `displacement_retrace` + FM-028 `displacement_atr_ratio` in ontology/`derived_math` (math intentional). **CH-002 (2026-07-09):** CRT `state.cached_features` now emits `displacement_retrace` / `displacement_atr_ratio` / `body_ratio` via `derived_math` (retest cache + `extract_features`); pipeline CANONICAL_FEATURES still use FM-021 `retest_depth` + FM-020 `disp_strength` (distinct, correct for pipeline). BitNet call-site maps FM-027/028 → legacy model input names only when `use_bitnet` (still false on active config, F-004). Live-metrics expose FM names + legacy journal aliases of the same values. Adversarial suite enforces emission keys. Residual: historical `opportunities`/`master_*_training.jsonl` retain pre-CH-002 keys until rebuild; BitNet retrain should use FM keys if re-enabled.
- Supersedes:    —
- Reversal:      CORRECTED 2026-07-09: emission-key collision REMEDIATED by CH-002 (old claim "remediation deferred" → keys renamed). Math was never wrong — name was.
- Owner:         grok
- Note:          Pre-remediation evidence: Gate-5 lineage report (`docs/governance/geometry_static_lineage_report.md`: `crt_engine_v2` cache → opportunities → stage1 → trainer BitNet). CRT Closure Program Phase 8 blocked on this; CH-002 re-opens CLOSED path. Authority: architecture/governance; grants no model promotion.

### F-051 · Centered-swing production binding is non-PIT and contaminates 10 canonical dims + model inputs; final-ledger structural importance remains INCONCLUSIVE (PC-2 failed) — F-029 scope refined, not reversed
- Type:          ARCHITECTURE
- Family:        RF-FEATURE-ONTOLOGY
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-07-11
- Revalidate-by: 2026-10-09
- Evidence:      docs/governance/pit_phaseA_swing_blast_radius-2026-07-11.json (A: BNB any-of-10 differ_rate≈0.635; B1 leakage PROVED — centered swing_high flips 0→1 when future bars arrive; B2a CRT final differ_rate≈0.071; B2b Zone VALUE mass 40%, SCORE differ≈0.63, HARD flip≈0.0001; B3 live default-absent path live-zero CONDITIONAL_PROVEN at live_engine_hook.py:394-402; C: rr_model zero_indices leaves 10/10 contaminated dims ACTIVE); docs/governance/pit_phaseA_gateon_ab-2026-07-11.json (isolation PASS; PC-1 PASS; PC-2 FAIL — zero-all-10 also 11≡11; gate-ON BNB 11≡11 + SOL 6≡6; gate-OFF F-029 replay 13≡13); feature_pipeline.py:391-460 (center=True production bind + structure graph); docs/governance/pit_phaseA_centered_swing_decision_record-2026-07-11.md; FC1-A contract docs/governance/FC1-A-SWING-CAUSAL-implementation-contract-2026-07-11.md
- Supersedes:    —
- Reversal:      "center=True is only a trade-generation non-issue (F-029) so production can keep centered swings" -> "F-029 still stands for gate-OFF trade-generation identity under causal intervention, but centered publication is non-PIT, materially changes ~63% of bars on the 10-dim structure closure, exposes CRT/ZoneGate/model inputs, and creates train/serve skew vs live default-absent zeros; final-ledger structural importance is INCONCLUSIVE because end-to-end PC-2 sensitivity was not demonstrated — null ledger ≠ structure-vector-insensitive"
- Owner:         grok
- Note:          Scope discipline (binding): proved = non-PIT + value/channel exposure + live-zero default path + RR/Zone artifact PIT-unclean provenance. **Not** proved = "spine is structure-vector-insensitive." Defensible ledger sentence: under tested BNB/SOL × v2_multi_2026_04, causal 10-feature and zero-all-10 interventions did not change final ledgers, but PC-2 failed so structural importance remains inconclusive. RR operational rule: artifacts tagged PIT_UNCLEAN_CENTERED_SWINGS — must not promote/re-enable/use as economic evidence without causal re-dataset/retrain/revalidation; no immediate retrain (rr_fusion disabled F-038; F-044/F-045). Authority: architecture/governance only; grants no ΔG001 / fusion weight. **FC1-A IMPLEMENTED 2026-07-11 (CH-fc1a-swing-causal).** **FC1-D IMPLEMENTED 2026-07-11:** production `volatility_regime` → rolling causal N=200. **Surface gate 2026-07-11:** `CANONICAL_FEATURE_CODE_SURFACE_STATUS=CLOSED` (38/0/0/0) after census re-export + wick_size↔candle_range alias — does **not** imply artifact economic admissibility.

### F-052 · PLAN-002 closure — second engines-path CODE authority for `score_component_weights` removed; both score-weight identities now HOW-owned
- Type:          GOVERNANCE
- Family:        — (not a market object; see docs/governance/research_family_registry.json)
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-07-11
- Revalidate-by: 2026-10-09
- Evidence:      Call-site census (18 matches across codebase; 0 legitimate callers relied on implicit CODE defaulting); `src/engines/crt_engine.py` — `compute()` now fails closed: missing `context["score_component_weights"]` returns `{"score": 0.0, "reason": "score_component_weights missing from context..."}` instead of silently using `(0.35, 0.25, 0.20, 0.20)` CODE literal; `src/core/engine_runner.py:680` injects `self._score_component_weights` from production config `crt_engine.score_component_weights`; `src/strategies/s01_crt_wrapper.py` loads weights via `_load_score_component_weights()`; research callers (`scripts/analysis/feature_math_drift_probe.py`, `scripts/analysis/pit_swing_blast_radius.py`) updated to pass explicit legacy vector; test files (`tests/test_plan002_dual_weights_how.py`, `tests/test_engine_runner_dual_gate.py`, `tests/test_engine_runner_rr_fusion.py`) updated for fail-closed assertion and `_score_component_weights` attribute. Regression suite: 38/38 passed (PLAN-002 identity tests + EngineRunner dual-gate + RR-fusion). Files changed: 7 (`src/engines/crt_engine.py`, `src/strategies/s01_crt_wrapper.py`, `scripts/analysis/feature_math_drift_probe.py`, `scripts/analysis/pit_swing_blast_radius.py`, `tests/test_plan002_dual_weights_how.py`, `tests/test_engine_runner_dual_gate.py`, `tests/test_engine_runner_rr_fusion.py`).
- Supersedes:    —
- Reversal:      "PLAN-002's second behavioral authority (the CODE fallback tuple in `engines.crt_engine.compute`) was an open defect" -> "Removed: missing `score_component_weights` now fails closed; both production paths (EngineRunner, S01CRTWrapper) inject the HOW-owned key; `conf_weights` untouched; `risk_score_weights` (Ultron path) unchanged; the two weight identities remain separate and distinct."
- Owner:         claude
- Note:          PLAN-002 and IC-007 are now CLOSED at implementation + focused-regression level. The "raises KeyError" wording in the closure result is corrected here: `crt_engine.compute()` does NOT propagate an exception — its broad `except Exception` catches the `KeyError` and returns `{"score": 0.0, "reason": "..."}`. This is fail-closed behavior (no silent CODE literal), not an externally propagated exception. PLAN-001 remains separately closed. No additional implementation work is justified for IC-007. A broader test suite beyond the 38 focused tests was not run; the survival of those broader tests is unknown. Authority: governance/hygiene only — records a completed governance closure, not an economic claim.

### F-053 · B2A — the FM-030/FM-031 candidate formulas (`ema_spread_atr`/`momentum_score_atr`) are CERTIFIED mathematically/temporally sound (PROMOTE = B2B-eligible only)
- Type:          ARCHITECTURE
- Family:        RF-FEATURE-ONTOLOGY
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-07-12
- Revalidate-by: 2027-01-05
- Evidence:      Observe-only certification probe `scripts/analysis/b2a_feature_candidate_certification.py` (READ-ONLY) + permanent floor `tests/test_b2a_feature_candidate_certification.py` (8/8) + immutable artifact `docs/governance/b2a_feature_candidate_certification-2026-07-12.md` (resolve via `b2a_feature_candidate_certification.LATEST.json`, sha256-pinned). Both candidates PROMOTE across the synthetic + BNB/BTC/ETH/SOL arms on ALL certification invariants: (1) THREE-path reconstruction — independent raw-OHLC float64 (`TR_abs → SMA14 = ATR_abs`; `(EMA9−EMA21)/ATR_abs`, `close.diff()/ATR_abs`) ≡ linked `atr_relative*close` (tight, max resid ~1e-7; independent SMA14(TR) == pipeline `atr_14_raw`) ≡ emitted legacy-column identity `legacy/close` (float32 band, resid ≤3e-4 = pipeline float32 `ema_fast−ema_slow` cancellation, price-scaled, NOT a formula error); (2) scale-invariance (independent float64 ×1 vs ×100, err ~1e-14 < 1e-6) while the LEGACY defect reproduces at ~100× (non-authoritative diagnostic); (3) NaN/Inf discipline (finite ⇔ atr>0 & close>0, 0 Inf); (4) deterministic recompute; (5) scalar↔vector parity; (6) PIT/prefix invariance both variants.
- Supersedes:    —
- Reversal:      —
- Owner:         claude
- Note:          Certification is candidate-FORMULA only. All prior behavioral/decision-impact/threshold-crossing/economic/model-performance/cross-instrument evidence for these formulas is treated as UNKNOWN for certification; any such metric computed here lives under `NON_AUTHORITATIVE_DOWNSTREAM_DIAGNOSTICS` (authority: none) and never gates the verdict. PROMOTE makes the candidate math ELIGIBLE for fresh B2B downstream-impact evaluation ONLY. **Decision impact: UNKNOWN · Economic value: UNKNOWN · Activation authority: NONE.** No registered impl, engine, config, or model was touched; ontology FM-030/FM-031 remain inactive `proposed_correction`; canonical vector stays 38-dim; `PRODUCTION_BEHAVIOR_CHANGED = NO`. After B2A, stop — B2B must regenerate all downstream evidence from the certified semantics (retrain inactive artifacts + recalibrate `dual_engine` thresholds remain the deferred B2 gate per the B0/B1 STOP boundary). Extends the B0/B1 semantic-migration governance. Authority: research/governance only. **[CONDITION RESOLVED 2026-07-12 by F-054]** the B2A certification was conditional on the (then-uncertified) ATR/EMA semantics. The bottom-up program independently certified + promoted ATR/EMA as first-class `rolling_indicators` (FM-041/043/044), so FM-030/031 were re-certified against promoted dependencies and PROMOTED as the production-intended identity in the certification ledger — legacy FM-022/023 SUPERSEDED, downstream (rr_model idx9/12, gaussian-38, `dual_engine` thresholds, pre-correction backtests) marked STALE. Still NOT ACTIVATED: no live pipeline math swap / retrain / recalibration (L6, gated on a fully clean DAG). B2B (consumer/economic impact) STOPPED, replaced by the bottom-up program.

### F-054 · Bottom-up feature-DAG certification: L0→L2 frontier PROMOTED with mechanical transitive invalidation; B2A conditionality resolved; B2B STOPPED
- Type:          ARCHITECTURE
- Family:        RF-FEATURE-ONTOLOGY
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-07-12
- Revalidate-by: 2027-01-05
- Evidence:      Built the missing certification spine: topological DAG + L0–L6 semantic layering `scripts/analysis/feature_dag_layers.py` (48 nodes, 38/38 canonical, acyclic, layer-monotone; fixed two fc05-DEPS bugs — `disp_strength`→body_size edge, duplicate `double_sweep`) + floor `tests/test_feature_dag_layers.py`; append-only certification ledger `docs/governance/feature_certification_ledger.jsonl` (schema `feature_certification_ledger.schema.json`, resolver `scripts/governance/feature_certification_state.py`) + descriptive-only floor `tests/test_feature_certification_ledger.py`; transitive-invalidation engine `scripts/governance/feature_dag_certify.py` (`formula_hash`/`dependency_contract_hash` = canonical `sha256(json.dumps sort_keys)`; ordering gate refuses certify while any dep unpromoted; STALE cascade) + floor `tests/test_feature_dag_invalidation.py`; series-parity + PIT rolling-indicator certification `scripts/analysis/feature_dag_rolling_certification.py` (7/7 CERTIFIED) + floor `tests/test_feature_dag_rolling_certification.py`. Executed frontier: raw+L0(candle primitives)+L1(ATR/RSI/EMA/true_range/swings promoted to first-class `rolling_indicators` FM-040..046, lifting the B3 boundary freeze — `market_ontology.yaml` v1.3, `registry/__init__.py` windowed-impl exemption; `validate_registry()==[]`)+L2(derived) = 28 PROMOTED_PRODUCTION. FM-030/031 re-certified against PROMOTED ATR and PROMOTED as the production-intended identity; legacy FM-022/023 (`ema_spread`/`momentum_score`) SUPERSEDED (2 nodes). All 54 new floors + registry/lineage/lint/derived/pipeline suite (84) green.
- Supersedes:    —
- Reversal:      "preserve a legacy formula because consumers bind to it (B2B-first)" -> "correct upstream mathematics/semantics FIRST in topological order; consumers/models/thresholds/evidence migrate afterward — consumer compatibility earns no authority (invariant: a dependent cannot be certified until every upstream dependency is independently certified + promoted)."
- Owner:         claude
- Note:          Milestone 1 (L0→L2) reaches PROMOTED_PRODUCTION (formula-IDENTITY decided), NOT ACTIVATED. **No live `feature_pipeline.py` math swapped, no model retrained, no `dual_engine` threshold recalibrated; canonical vector stays 38-dim; `PRODUCTION_BEHAVIOR_CHANGED = NO`.** Promotion = ledger event + descriptive ontology registration (rolling indicators byte-identical wrappers of existing pipeline math) + a mechanical STALE cascade over downstream *evidence records* (rr_model idx9/12, gaussian-38, `dual_engine` thresholds, pre-correction backtests, the B2A F-053 cert). Certification is DESCRIPTIVE (§6.5) — promotion authority stays in `src/governance/promotion_manager.py` / `src/research/qualification.py` (every PROMOTED event attributes it there). **Decision impact: UNKNOWN · Economic value: UNKNOWN · Activation authority: NONE.** L3 structural / L4 composite / L5 temporal deferred; L6 ACTIVATION (live surface swap + retrain + recalibrate + downstream economic re-eval = the former "B2B") is gated on a fully clean DAG. Scoping notes: the dependencies-before-dependents ordering gate lives in the certify tool + `tests/test_feature_dag_invalidation.py` (not a `construction_protocol.py` edit, to avoid destabilizing that gate); pre-existing unrelated red `test_change_contracts_drafted` (FC1-A/D status drift) untouched. Authority: research/governance only. **[Milestone 2 — L3 swing-structural family, 2026-07-12]** ATOMICALLY certified + promoted the strongly-coupled family `higher_high`/`lower_low`/`break_of_structure`/`liquidity_sweep` (all-or-none family transaction: `certify-family`/`promote-family`, single-block writes). LEDGER-ONLY (no ontology/registry edit — stateful structural detection stays out of the WHAT layer). Certified by TWO oracles both == pipeline int8 exactly across synthetic+4 majors: a formula-parity centered reconstruction AND an independent CAUSAL online oracle (sequential, bar t publishes pivot t−k from bars ≤t — the causality proof, re-proving FC1-A for these flags); inclusive sweep boundary (`close<=ref_high`/`close>=ref_low`, pinned from feature_pipeline.py:478-479) exercised on ~275 real BNB boundary rows; PIT dependency-bound to `pit_phaseC` + a fresh `repo_state_hash`. Evidence `scripts/analysis/feature_dag_structural_certification.py` + floor `tests/test_feature_dag_structural_certification.py` (4, incl. online-oracle prefix-invariance) + artifact `feature_dag_structural_certification.LATEST.json`. Frontier advanced 28→**32 PROMOTED** (2 SUPERSEDED · 11 READY · 3 BLOCKED); the promotion mechanically flipped `sweep_detected`/`double_sweep`/`candles_since_retest`/`retest_depth`/`liquidity_distance` BLOCKED→READY. Still ledger-only / not activated; STOPPED before derivatives. `PRODUCTION_BEHAVIOR_CHANGED=NO`. **[Milestone 3 — L3 `sweep_detected`, 2026-07-12]** Certified + promoted the single node `sweep_detected` = `(liquidity_sweep != 0).astype(int8)` (feature_pipeline.py:590 — direction-agnostic sweep-presence flag over the promoted `liquidity_sweep`). Independently certified by extending the structural probe: both oracles derive `sweep_detected` from their OHLC-grounded `liquidity_sweep` and match the pipeline int8 exactly (synthetic+4 majors); causality + prefix-invariance inherited from `liquidity_sweep`. Zero feature-DAG consumers → promotion staled nothing (no `invalidates`); the ~52 code references are transport-only value-readers, unaffected (formula certified as-is, not corrected). Frontier 32→**33 PROMOTED** (2 SUPERSEDED · 10 READY · 3 BLOCKED). Ledger-only, not activated. `PRODUCTION_BEHAVIOR_CHANGED=NO`. **[Milestone 4 — L3 `double_sweep`, 2026-07-12]** Mandatory DAG-vs-code gate PASSED: `feature_pipeline.py:612-626` confirms `double_sweep` deps = `liquidity_sweep` ONLY (directional >0/<0 conjunction over a TRAILING 5-bar window, `rolling(5,min_periods=1)`, int8) — NOT `sweep_detected`, NOT a count threshold (`>=2`/`==2`); DAG contract matched reality, no correction needed. Certified + promoted `double_sweep` via the structural probe extended with a `_double_sweep` windowed helper computed in both oracles from their OHLC-grounded `liquidity_sweep` (both == pipeline int8, synthetic+4 majors); floor adds an exact-window-boundary property test (up@t+down@t+4→1, up@t+down@t+5→0, two ups→0) + an EXPLICIT `double_sweep` prefix-invariance test (not inherited). Provenance-safe: certified against the DATED immutable artifact; the M2/M3 ledger lines verified BYTE-UNCHANGED (no rebinding). Zero DAG consumers → staled nothing. Frontier 33→**34 PROMOTED** (2 SUPERSEDED · 9 READY · 3 BLOCKED). Ledger-only, not activated. `PRODUCTION_BEHAVIOR_CHANGED=NO`. **[Milestone 5 — L3 `candles_since_retest`, 2026-07-12]** Gate PASS: `feature_pipeline.py:655-672` resets on `liquidity_sweep != 0` (grouped cumcount; SWEEP bar=0, +1/non-sweep bar, 0 pre-first-sweep, int16) — DAG contract `deps=[liquidity_sweep]` matched. TWO findings: (1) **NAME MISNOMER** — despite "retest" it counts bars since the last SWEEP, not since `retest_flag` (so NO shared state with `retest_depth`, which resets on `retest_flag`; coupled-family assumption rejected); (2) **input-schema-dependent formula** — the col-absent `retest_flag` fallback branch classified **B (test-only shim), non-authoritative**, mechanically proven unreachable in production (`run()` computes `liquidity_sweep` @:896 before `candles_since_retest` @:905). Certified the PRODUCTION `liquidity_sweep` branch via an independent ONLINE state-machine recurrence (both oracles == pipeline int16); floor adds the counter battery (before/after-sweep split, event-bar=0, first-after=1, consecutive=0, separated resets, prefix-invariance, int16 dtype) + the class-B fence (runtime spy asserting `liquidity_sweep` present at temporal-feature entry; source-order secondary; deterministic synthetic branch-discrimination liq{3,8}≠rf{5}). Provenance-safe (dated artifact; prior 106 ledger lines byte-unchanged). Zero DAG consumers → staled nothing. Frontier 34→**35 PROMOTED** (2 SUPERSEDED · 8 READY · 3 BLOCKED). Ledger-only, not activated. `PRODUCTION_BEHAVIOR_CHANGED=NO`. **[Milestone 6 — L3 `liquidity_distance` FM-025, 2026-07-12]** Gate PASS: `feature_pipeline.py:692-718` consumes swings (ref_high/ref_low), break_of_structure (bos_level), atr, close — NOTHING else; DAG contract `[atr,break_of_structure,close,swing_high,swing_low]` COMPLETE + EXACT. First ontology-REGISTERED node certified (FM-025, `derived_math.liquidity_distance`, lifecycle registered — scalar↔pipeline parity was DEFERRED; this cert supplies it, ontology lifecycle field unchanged). Certified via the REGISTRY-AUTHORITATIVE scalar `derived_math.liquidity_distance` (not a copy of the pipeline vectorized min) fed with independently-reconstructed levels (ref_high/ref_low/bos_level from promoted swings+BOS via the M2 oracle) + independent close-relative atr; float32 parity vs pipeline on both oracles. Floor adds the FM-025 property battery: pos/neg/no-BOS, distance-exactly-zero, ATR-zero→NaN, ATR-warmup→NaN, scale-invariance (×1 vs ×100), always≥0, no-Inf/NaN-policy, bos_level-ffill prefix-invariance, float parity. GOTCHA fixed: bos_level ffill + atr must be computed over the FULL frame (not the idx subset) or the ffill loses contiguity. Provenance-safe (dated artifact; prior 108 ledger lines byte-unchanged). Frontier 35→**36 PROMOTED** (2 SUPERSEDED · 8 READY · 2 BLOCKED); the promotion mechanically flipped `liquidity_pressure_score` (FM-026, its only dep) BLOCKED→READY. Ledger-only, not activated. `PRODUCTION_BEHAVIOR_CHANGED=NO`. **[M9 / F-054-DR — FM-027 displacement_retrace, 2026-07-14]** Single-node CERTIFY+PROMOTE of CRT-only cross-candle retrace (FM-027). Intended quantity ALIGNED: clip(|retest_close-disp_open|/|disp_close-disp_open|,0,1); zero body→0.0. Gate-2 ROLE_LABEL_GROUNDING_ALIGNED (ontology roles vs DAG open/close; allowlisted). Semantic class: pure algebraic kernel + event-gated CRT emission. Independent oracle + property battery + CRT emission parity → CERTIFIED. Evidence docs/governance/fm027_displacement_retrace_certification-2026-07-14.json sha256=6dabf84b4be5feded29c2891eba2c93c0add59aba473c75b181711bc5f29c821 (non-empty). Ledger CERTIFIED+PROMOTED (authority src/research/qualification.py); 0 STALE downstream. Frontier 40→41 PROMOTED · 2 SUPERSEDED · 5 READY · 0 BLOCKED. Resolver fix: accept M6R PROVENANCE_REMEDIATION (target_feature). PRODUCTION_BEHAVIOR_CHANGED=NO; not in 38-vector; L6 unchanged. Floor 	ests/test_fm027_displacement_retrace_certification.py (12). STOP. **[M10 / F-054-RD — retest_depth gated composition, 2026-07-14]** IDENTITY_SPLIT_REQUIRED resolved: FM-021 remains kernel-only (derived_math/ontology formula unchanged); canonical retest_depth = GATED_PRODUCTION_COMPOSITION where(retest_flag==1 & atr>0 & close>0, kernel, 0.0)→float32→clip→float32 (feature_pipeline.py:599-610,648-653). DAG deps corrected live _NODES → [atr,close,ema_fast,liquidity_sweep] (no SEEDED rewrite; retest_flag not a node). Independent online oracle (no pandas rolling) + component/gate/full-series parity. Evidence docs/governance/fm021_retest_depth_certification-2026-07-14.json sha256=da916a77f3b0f5c78fcdd69b1e6d5269fc675d022acecf4d3313ad71524861fd. CERTIFY+PROMOTE; 0 STALE. Frontier 41→42 PROMOTED · 2 SUPERSEDED · 4 READY. PRODUCTION_BEHAVIOR_CHANGED=NO. STOP. **[M11 — hour_of_day, 2026-07-14]** Pure timestamp wall-clock hour: pd.to_datetime→.dt.hour.astype(int8); deps=[timestamp]; domain 0..23 int8; no TZ conversion; NaT fails cast (no soft sentinel). Independent oracle (per-element pydatetime.hour) CERTIFIED. Evidence hour_of_day_certification-2026-07-14.json sha256=dec24c8b16a59bb9b29494ad60b5ab58478022b43ce3bba6bb2b11d4a3a54212. CERTIFY+PROMOTE; 0 STALE; session NOT coupled (DAG session deps=[timestamp] though code uses hour intermediate). Frontier 42→43 PROMOTED · 3 READY remain. PRODUCTION_BEHAVIOR_CHANGED=NO. STOP. **[M12B — session CERTIFY+PROMOTE, 2026-07-14]** Canonical FeaturePipeline session PROMOTED: int8 0=Asia(h00-07)/1=London(h08-15)/2=NY(h16-23) from pd.to_datetime wall-clock hour, no TZ conversion; DAG deps=[timestamp] (EXECUTABLE_REUSE_BUT_TIMESTAMP_IDENTITY). Independent branch oracle; encoding isolation vs SESSION_MAP asian=2. Evidence session_certification-2026-07-14.json sha256=27fd76eef09784270035136ee21b7df34aed7c8b0b7c24a3088ce7368de73e10. Frontier 43→44 PROMOTED; READY left: trend_strength, volatility_regime. Multi-surface session encoding debt STILL_DEFERRED. PRODUCTION_BEHAVIOR_CHANGED=NO. STOP. **[M13B — trend_strength CERTIFY+PROMOTE, 2026-07-14]** Nested rolling SMA10(diff(SMA20(close))) PROMOTED; first finite index 29; deps=[close]; independent deque SMA oracle; float64 column / float32 vector; dual_engine ema_spread name collision deferred. Evidence trend_strength_certification-2026-07-14.json sha256=823ac058ea56e65c6c24cba19831bd1e529a25ba2ad24a3db5a40284ec75a74e. Frontier 44→45 PROMOTED; READY left: volatility_regime. PRODUCTION_BEHAVIOR_CHANGED=NO. STOP. **[M14B — volatility_regime CERTIFY+PROMOTE, 2026-07-14]** DAG deps corrected atr→[high,low,close] (absolute atr_14, not relative atr). Identity: TR→SMA14→rolling(200,min_periods=1).rank(pct=True,average)→tercile 0.33/0.66; NaN→2; int8. Independent oracle CERTIFIED. Evidence volatility_regime_certification-2026-07-14.json sha256=8543bc5b82bd032426b4bd695dd9ab128f7b1c23af2ad06446fd184275d5a1b8. Frontier 45→46 PROMOTED · 0 READY (identity-certification frontier exhausted; FEATURE_PROGRAM_CLOSED=NO). PRODUCTION_BEHAVIOR_CHANGED=NO. STOP.

### F-055 · Enabling the EXISTING BitNet gate does NOT improve the CRT spine — book expectancy degrades or is inert; enablement stays unjustified (§6.5)
- Type:          ARCHITECTURE
- Family:        RF-NEURAL-CONSUMERS
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Likely
- Validated:     2026-07-18
- Revalidate-by: 2026-10-16
- Evidence:      Shadow A/B via `scripts/research/bitnet_shadow_diagnostic.py`: the CRT spine run gate-OFF (active `v2_multi_2026_04`, `use_bitnet:false`) vs gate-ON (non-active clone `v2_multi_bitnet_shadow_2026_07`, `use_bitnet:true`, the SAME `model.json`) across BNB/ETH/BTC/SOL, expectancy from the spine's own governed ledger (`SpineEntry.meta.backtest_pnl_rr_net`). POOLED book-level: E_off=+0.156R (PF 1.29, n=26) → E_on=+0.023R (PF 1.04, n=24), ΔE=−0.133R; **0/4 instruments improve** (BNB ΔE=0 NEUTRAL; ETH/BTC INERT, 0 rejects; SOL HARMFUL ΔE=−0.35R). MECHANISM: the gate is a state-machine-perturbing VETO, not a filter — on BNB it fired 50 `LOW_SCORE` rejects yet net trades stayed 11→11 because a reject RESETS the CRT state machine (`src/config_layer/crt_engine_v2.py:1960`, `bitnet_score` `src/bitnet/bitnet_inference.py:317`), so gate-ON is a DIVERGENT trajectory (removed≠added). SCOPE/E-001: (1) underpowered — pooled n<30 min-samples floor, so the −0.13R magnitude is NOT a hard economic claim, but the direction has 0 positive instruments and is consistent with the entry-information null F-019…F-041 (binding constraint = execution model, not predictability); (2) measures the EXISTING model, which carries the F-050 train/serve skew (trained pipeline FM-020/021, served CRT FM-027/028 under the same legacy names) + a raw unnormalized `atr` input (not scale-invariant across instruments) — so this is "what flipping the flag does today", not a governed retrain; (3) a faithful retrain is not even trainable (spine commits ~5-13 entries/instrument, F-019). Authority: research/governance only (§6.5) — no ΔG001 improvement ⇒ no authority earned; `use_bitnet` stays false on the active config; the shadow config is neither active nor promoted. Extends F-004/F-050; quantifies the F-050 conditional-skew as economically negative. Detail audit: `docs/governance/bitnet_lineage_audit.md`.
- Supersedes:    —
- Reversal:      —
- Owner:         claude

### F-056 · `backtest_v2` had three trade-affecting constants declared in NO config — one was a config illusion (read-then-discarded); all three now declared + strictly read (REMEDIATED)
- Type:          ARCHITECTURE
- Family:        — (not a market object; see docs/governance/research_family_registry.json)
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-07-20
- Revalidate-by: 2026-10-16
- Evidence:      Three constants on the backtest decision path were declared in no config file: (1) `execution_planner.partial_tp_fraction` was strict-read at `src/runtime/backtest_v2.py` and then DISCARDED while hardcoded `0.5/0.5` blend literals executed at THREE sites (`:2347`,`:2354`, and a third at `:2426` — `TP1_BE_RESET` — missed by the initial audit, caught only by a source-grep assertion) — a config illusion: editing the key had zero effect on output; (2) the SL-distance floor was a `0.2 * atr` literal whose comment claimed to match `crt_engine.sl_atr_buffer` but never read it; (3) the Phase-5 veto `p_win < 0.35` was a bare literal gating every trade under the default `scorer_mode="calibrated"`. REMEDIATED 2026-07-19: `partial_tp_fraction` wired at all three blend sites, `sl_atr_buffer` threaded via a required `TradeJournal` param, `phase5_calibration.min_p_win` added and read strictly. Parity: BNBUSDT `events.jsonl`/`crt_telemetry.jsonl`/`trades.csv` BYTE-IDENTICAL before/after (11 trades both), `params` hash unchanged. Floor: `tests/test_backtest_declared_constants.py` (10 tests). Same class as F-018 (hardcoded knobs override config) but distinct mechanism (read-then-discard illusion).
- Supersedes:    —
- Reversal:      "A config key that is present and strict-read is governed" -> "Presence + a strict read is NOT sufficient — `partial_tp_fraction` was read then discarded while a literal executed; a config key is only governed once the read VALUE actually reaches the behavior. Byte-identity only proves neutrality on paths the corpus exercises (this corpus fired 0 partial-TP exits), so a source-grep assertion is required alongside it."
- Owner:         claude
- Note:          Discovered while auditing the backtest layer for config-vs-code. Authority: architecture/governance only — records a completed remediation + a governance lesson, not an economic claim.

### F-057 · CRTConfig resolution is split-brain on the programmatic entry path — `market_router`'s hardcoded profiles win when `crt_config is None`, so the production JSON is never opened (OPEN)
- Type:          ARCHITECTURE
- Family:        — (not a market object; see docs/governance/research_family_registry.json)
- Contract:      UNKNOWN
- Status:        OPEN
- Confidence:    Certain
- Validated:     2026-07-20
- Revalidate-by: 2026-10-16
- Evidence:      Which CRT geometry numbers win depends on the entry point. CLI (`python backtest_v2.py`) merges `{**crt_engine, **params}` so JSON wins. But the programmatic path — `BacktestRunner(cfg)` with `cfg.crt_config is None` (tuner workers, tests, embedding harnesses) at `src/runtime/backtest_v2.py:1633` — calls `ConfigBuilder.build(instrument)` with NO overrides, so `src/config_layer/market_router.py:12-27`'s hardcoded FOREX/CRYPTO profiles win and the production JSON is never opened. Divergence is large and gold classifies FOREX: `expansion_atr_min_distance` 0.08 (market_router FOREX) vs 0.30 (JSON `params`) = 3.75× on the DISPLACEMENT→EXPANSION gate; `retest_depth_max` 0.35 vs 0.15; `atr_multiplier_min` 1.5 vs 1.0. `src/config_layer/production_config.py:382` explicitly names hardcoding in market_router "the failure mode" — and `:1633` routes straight into it. Also a `"EURUSD"` fallback literal on the same line silently mis-classifies an unknown instrument.
- Supersedes:    —
- Reversal:      "The production config governs CRT geometry for every backtest" -> "Only on the CLI path; the programmatic `crt_config is None` path silently uses market_router's hardcoded market profiles, so tuner/test/embedded runs measure DIFFERENT entry-geometry knobs than production."
- Owner:         claude
- Note:          Fix is backtest Phase 2 (make JSON authoritative on the `crt_config is None` path + raise on unknown instrument); recorded here per the §6.2 Findings Mandate, remediation tracked separately. Authority: architecture/governance only.

### F-058 · `BACKTEST_ENGINE_GATE` code default is ON ("1"), contradicting F-037/`active_models.yaml` which document OFF — RESOLVED: config now declares the gate, active config sets it ON (epoch change)
- Type:          GOVERNANCE
- Family:        — (not a market object; see docs/governance/research_family_registry.json)
- Contract:      UNKNOWN
- Status:        VALIDATED
- Confidence:    Certain
- Validated:     2026-07-23
- Revalidate-by: 2026-10-21
- Evidence:      Originally `src/runtime/backtest_v2.py:1884` read `os.getenv("BACKTEST_ENGINE_GATE", "1")` — effective default ON but declared nowhere, so behavior depended on an untracked `.env`. **SHIPPED 2026-07-23 (T-16):** `backtest.engine_gate_enabled` is now a strictly-required config key (`_require_bt_cfg(...)`, `backtest_v2.py:2050-2053`), present and `true` on `v1_multi_2026_03.json`, `v2_multi_2026_04.json` (active), `v2_multi_2026_04_v3session_probe.json`, `v4_multi_2026_06.json`. The env var is now an explicit OVERRIDE only — if set, it wins, but logs a WARNING when it disagrees with config (`backtest_v2.py:2054-2063`), so silent divergence can no longer happen. Pinned by `tests/test_feature_warmup_coupling.py:161` (required bool, raises at construction if absent). `active_models.yaml:1082-1085` mirrors the resolution. Empirically confirmed pre-fix: a plain BNBUSDT run produced 11 trades = F-037's recorded GATE-ON figure (13 gate-OFF → 11 gate-ON) — i.e. the silent default was already what executed, config declaration made it honest rather than changing behavior. A second undeclared env switch, `BACKTEST_BYPASS_ZONE_INVALID`, was fixed the same way (`backtest_v2.py:2065-2067`, F-058-class fix, 2026-07-29).
- Supersedes:    —
- Reversal:      "Backtests run CRT-only (gate OFF), as F-037 documents" -> "The active config declares the gate ON since 2026-07-23; the gate-OFF corpus behind F-019/F-036/F-037 is valid for its pre-2026-07-23 epoch only, not for the current config."
- Owner:         claude
- Note:          RESOLVED — `backtest.engine_gate_enabled` shipped 2026-07-23 across all 4 configs carrying a `backtest` section; env-var silent-default dependency removed (override-with-WARNING only). CORRECTED 2026-08-06 (E-001): this row was left `Status: OPEN` / "Implementation = backtest Phase 3" after the fix shipped — a session repeated the stale status without checking source, which the fix itself was designed to make impossible for the *runtime* (WARNING on env/config disagreement) but did not prevent for *documentation*. Residue not yet closed: the resolved gate mode is logged (WARNING) but not written onto any run's output artifact, so a run's actual gate state still is not recoverable from the artifact alone — tracked as the concrete first consumer of the measurement-contract layer (`docs/governance/MEASUREMENT_CONTRACT.md` §9/§10, `docs/governance/research_family_registry.json` RF-CRT-STRUCTURE.L5). Remaining open item: the entire gate-OFF research corpus (F-019…F-042, the `qualify_*` fleet) has not been re-measured gate-ON since the 2026-07-23 config declaration — see M-GATE-01 (queued). `src/research/adapters/spine_signal_source.py`'s docstring still describes the pre-fix `.env`-authority world and needs a matching update. Authority: governance only.

---

## Funding Ledger (initiative-level capital allocation)

> A **finding** is an observation; **funding** is a capital-allocation decision derived from
> findings — and one finding (e.g. F-001) kills or funds many initiatives. This ledger keeps the
> two adjacent but separate. **Never silently revive a `KILLED`/`FROZEN` initiative:** its
> `Reopen Conditions` must be met *and* a SESSION LOG entry filed (per `CLAUDE.md §6.2`).
> Status vocab: `FUNDED · FROZEN · KILLED · RESEARCH · UNFUNDED`. `Evidence` cites finding IDs
> (CI checks they resolve); `FROZEN`/`KILLED` require non-empty `Reopen Conditions`.

### Bottom-up Feature-DAG Certification (L0→L6) — RESEARCH
- Date:    2026-07-12
- Evidence: F-054 (Milestone 1 L0→L2 executed: DAG spine + certification ledger + transitive-invalidation engine + rolling-indicator first-class registration + FM-030/031 adjudication), F-053, F-046, F-047
- Reopen Conditions: n/a — active. Next: certify L3 structural / L4 composite / L5 temporal in topological order; L6 ACTIVATION (live surface swap + retrain inactive artifacts + `dual_engine` recalibration) is a separate authorized gate on a fully clean DAG.

### B2B Consumer / Economic Impact Evaluation — FROZEN
- Date:    2026-07-12
- Evidence: F-054 (bottom-up certification replaces the B2B-first direction), F-053, F-025 (entry-info null bounds expected downstream value)
- Reopen Conditions: the full feature DAG is certified + promoted clean AND L6 activation (live corrected-surface swap + retrain of the inactive rr_model/gaussian-38 + `dual_engine` recalibration) is authorized — only then may downstream consumer/economic evidence be regenerated, and ONLY from the corrected promoted identities, NEVER the superseded legacy `ema_spread`/`momentum_score` (FM-022/023).

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

### Program 4b: Non-Directional Target — Regime TRANSITION Forecast (forward Markov P^H) — KILLED
- Date:    2026-07-01
- Evidence: F-043 (0 REGIME_EXPLOITABLE across all 15 scopes; all 10 toy consumer×scope combinations REGIME_REDUNDANT, well-powered and statistically significant but fully explained by persistence + current vol level; spine REGIME_INSUFFICIENT — no claim)
- Doc-drift note (§6.2, resolved 2026-07-01): this entry previously read "RESEARCH
  (pre-registration pending)" after F-040 (2026-06-26) closed a DIFFERENTLY-CONSTRUCTED
  "Program 4b/4c/4d" grouping (an MTF candle-state conjunction,
  `docs/research/preregistration-program-4bcd.md`) — a distinct hypothesis that never tested
  this literal Markov `P^H` transition-matrix forecast. The pre-registration's reserved
  finding number "F-031" was superseded by an unrelated governance finding; the real result
  is registered as F-043.
- Reopen Conditions: ONLY a genuinely NEW ontology with a pre-registered hypothesis — NOT a parameter pass. The pre-registration's §5 fixed parameters (`atr_period=14`, `tercile_window=480`, `w_markov=480`, `h=8`, `min_cell_samples=30`, `harmful_margin`/`redundant_tol=0.05`, `null_relabelings=200`) are explicitly forbidden reopen routes ("Program 4b with a bigger w_markov / different H / more controls" is mechanically out-of-bounds archaeology, per the pre-registration's own "ONE shot" rule). A genuinely different transition-forecast construction (e.g. a non-Markov forecaster, a non-crypto universe, or a non-spot execution architecture that could express the long-vol payoff the redundancy gate never even reached) would be a new program with its own pre-registration, not a tweak here. Pre-registration: docs/research-readiness/program-4b-transition-preregistration.md.

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

### Program 8: Weekly Liquidity-Sweep Ontology (Direction×Vol diagnostic; FX majors, intrabar_fixed+12bps) — KILLED
- Date:    2026-07-01
- Evidence: F-042 (0 PROMOTE across 6 scopes; every scope REJECTs at the absolute-expectancy gate despite beating its winning control; Direction×Vol 3×3 diagnostic shows no exploitable cell beyond one small-N DOJI/EXPANSION positive)
- Reopen Conditions: ONLY a genuinely NEW structural thesis with a fresh pre-registration — NOT a parameter pass. The pre-registration's fixed parameters (calendar Mon+Tue accumulation, reversal-not-continuation, range-width-derived exit, `sl_range_frac=0.25`/`min_accumulation_bars=40`/`atr_period=14`, the 5-FX-major universe, 12bps/2000-perm/α=0.05) are forbidden reopen routes ("Program 8 with a different sl_range_frac / bigger accumulation window / continuation entry" is archaeology). A genuinely different weekly-calendar construction (a continuation variant, or a non-FX universe) would be a new program with its own thesis + pre-registration, not a tweak here. Pre-registration: docs/research-readiness/program-8-weekly-crt-sweep-preregistration.md.

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
| Non-directional target — regime TRANSITION forecast (Markov P^H) | crypto-majors · M15 · intrabar_fixed+12bps · IS+70/30 OOS+BH + label-permutation null + lagged control + within-tercile-shuffle control (Program 4b) | FALSIFIED-IN-SCOPE | F-043 (0 REGIME_EXPLOITABLE; all 10 toy consumer×scope combos REGIME_REDUNDANT — well-powered, statistically real, but fully explained by persistence + current level; spine INSUFFICIENT) |
| **Cross-sectional relative-value (dispersion, market-neutral)** | crypto-6 · **M15** · close-to-close+12bps/leg · IS+70/30 OOS+BH · 5 controls (Program 5) | FALSIFIED-IN-SCOPE | F-032 (0 PROMOTE; momentum loses PF 0.335, lone positive cell is a long-leg/beta artifact, insignificant p=0.57). FIRST panel-axis null; cross-sectional on FX/perps/other payoff structures stays untouched |
| **Carry/basis as a cross-sectional signal** | crypto-6 · **M15** · close-to-close+12bps/leg · perp funding(8h ffill)+basis(M15) · IS+70/30 OOS+BH · 5 controls (Program 6) | FALSIFIED-IN-SCOPE | F-033 (0 PROMOTE; all 8 cells both signs E(net)<0, PF 0.55–0.82, p 0.76–1.0, each loses to market/long_only — below even Authority-Level-1). FIRST axis tested on NEWLY-ACQUIRED data. Does NOT test the funding-PnL carry-HARVEST payoff (Program 6b) or OI (Program 7) |
| **Carry-HARVEST payoff (hold perp to earn funding ± basis convergence)** | crypto-6 · perp basket · 12bps/leg · H∈{1d,3d,1w} · cash+5 controls (Program 6b) | FALSIFIED-IN-SCOPE | F-034 (0 PROMOTE; funding income real but ~1–6 bps < ~24 bps turnover ⇒ net-negative before price drag; lowest-turnover H=672 still REJECTs). Distinct from F-033 (cashflow not signal). A low-turnover/netting cash-and-carry is a separate untested construction (new thesis, not a tweak) |
| **Weekly liquidity-sweep ontology (ICT/CRT Mon+Tue accumulation → Wed-Fri sweep → reversal)** | FX-5 majors · M15 · intrabar_fixed+12bps · IS+70/30 OOS+BH (Program 8) | FALSIFIED-IN-SCOPE | F-042 (0 PROMOTE across 6 scopes; REJECT at the absolute-expectancy gate despite beating controls; Direction×Vol 3×3 diagnostic shows no exploitable cell beyond one small-N DOJI/EXPANSION positive). FIRST test of a weekly-CALENDAR ontology (distinct from Program 1's next-bar/M15-local frame and Program 2's intraday structural-asymmetry frame) |
| Non-directional targets (range/persistence, other) | — | UNTOUCHED-FRONTIER (deferred) | per Program-1 closure §"EXHAUSTED ≠ WRONG"; objective ≠ directional speculation |
