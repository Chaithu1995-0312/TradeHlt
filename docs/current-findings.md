# Current Findings — Repository Truths (living)

> Created: 2026-06-03 · Updated: 2026-06-03
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
- Evidence:      src/config_layer/crt_engine_v2.py:1749 · bitnet_main_score<0.55 (`if bitnet_main_score < 0.55: return False, RejectReason.LOW_SCORE, 0.0`; threshold default at :363 · bitnet_main_threshold); src/runtime/backtest_v2.py:276 · bitnet_score_at_entry (persisted to TradeRecord)
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
- Evidence:      src/inout/live_engine_hook.py:676 (HARD drift -> logger "Trade signal unreliable", trade proceeds; no block/size-down/gate)
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
- Update:        2026-06-12 (R1 done) — the SECTION-ABSENCE half is RESOLVED: `dataset_integrity`/`uat`/`live_integration` added verbatim to configs/production/v2_multi_2026_04.json (hash unchanged — params-only); 75 previously-red tests green; BNBUSDT ledger byte-identical pre/post (1a624761f3a0…, behavior-neutral). The HARDCODED-KNOB half (A-2 / R2: bitnet_main_threshold, feature_monitor drift_z) remains OPEN — finding stays VALIDATED.

---

## Funding Ledger (initiative-level capital allocation)

> A **finding** is an observation; **funding** is a capital-allocation decision derived from
> findings — and one finding (e.g. F-001) kills or funds many initiatives. This ledger keeps the
> two adjacent but separate. **Never silently revive a `KILLED`/`FROZEN` initiative:** its
> `Reopen Conditions` must be met *and* a SESSION LOG entry filed (per `CLAUDE.md §6.2`).
> Status vocab: `FUNDED · FROZEN · KILLED · RESEARCH · UNFUNDED`. `Evidence` cites finding IDs
> (CI checks they resolve); `FROZEN`/`KILLED` require non-empty `Reopen Conditions`.

### Liquidity V2 — KILLED
- Date:    2026-06-03
- Evidence: F-001, F-011 (Phase-0 economic-edge gate FAIL 0/4)
- Reopen Conditions: a feature track shows ΔAUC ≥ +0.03 OOS **and** positive expectancy lift surviving the gate **and** a cross-instrument pass (the §7 kill-criteria of economic-edge-gap-analysis-2026-06-03.md)

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

---

## Terminal (SUPERSEDED / RETIRED) — kept for replay

_(none yet — when a finding above is overturned, flip its Status here and add the superseding F-id.)_
