<!-- ============================================================= -->
<!-- ARCHITECTURE MIGRATION DOCTRINE — keep this block at the top.  -->
<!-- Canonical companion docs live in docs/architecture/.          -->
<!-- ============================================================= -->

# ARCHITECTURE MIGRATION DOCTRINE

> **This file is the permanent record of every session decision since April 2026.**
> Every entry below carries a date and a decision summary in timestamped order, so you can scroll back through the full history without replaying old conversations.
> Governed by [`CLAUDE.md`](CLAUDE.md) §6 (Persistent Logging Mandate).
> Cross-reference: [`CLAUDE.md`](CLAUDE.md) §2 for the companion docs map.
---

**North star — LLM context economy.** We migrate toward an event-driven LLM-event-
microservices architecture so a future LLM loads only the *one* service it needs
(ins → flow → outs) instead of the whole codebase. Microservice boundaries = context
separation. Telemetry is curated into per-episode "LLM logs" so context does not grow
unbounded. Every application flow is documented as a loadable context unit.

**Priority order (ranks above refactor speed):**
replay correctness > explainability > telemetry continuity > advisory-AI >
(structure validity ≠ execution validity).

**The five governance questions — apply as a pre-merge checklist to every change:**
1. Does replay remain deterministic?
2. Does telemetry remain comparable across runs?
3. Can this state be audited later?
4. Can an LLM reason about this event?
5. Is execution authority still isolated?

**Standing rules:**
- **Consolidate on `src/events/event_fabric.py` — never fork the event system.**
- LLMs are advisory governance, **never** execution authority.
- No lookahead in replay; deterministic seeds mandatory; comparison ignores
  `event_id`/`generation`/wall-clock `timestamp`.
- New telemetry is additive; no field removed without a documented superseding field.

**Migration sequencing index** (detail in `docs/implementation_plan/`):
- **M0** — Map & doctrine: `docs/architecture/{CODEBASE_STATE_MAP,EVENT_TAXONOMY,
  SERVICE_BOUNDARY_MAP,REPLAY_GOVERNANCE,LLM_GOVERNANCE_LAYER}.md` + `services/`.
- **M1** — Telemetry normalization (envelope trade writers) + per-episode LLM log.
- **M2** — Event extraction (CRTState transitions + silent EventTypes).
- **M3** — Orchestration de-coupling (kill `live_engine_hook` singletons).
- **M4** — Dependency inversion (governance/analytics stop importing `runtime.backtest_v2`).
- **M5** — LLM-layer hardening (`GOVERNANCE_MODE`, decision-path assertions, advisory event contract).

<!-- ============================================================= -->
<!-- SESSION LOG (newest first). Append new entries below the       -->
<!-- doctrine block, above prior entries.                           -->
<!-- ============================================================= -->

---
SESSION LOG ENTRY
Date: 2026-06-15
Topic: Config-First Migration - Batch A (4 live-spine modules) + Batch B (behavior_census evidence engine). Practice->Evidence; doctrine NOT yet frozen into CLAUDE.md.
Decision/Output: Migrated 4 live-spine modules from hardcoded BEHAVIORAL constants to config, FAIL-FAST (owner directive "no defaults, throw error, fail fast") - NOT R2 .get(default) soft pattern. A1 dynamic_threshold.py/decision_engine.py: _THRESHOLD_PERCENTILE/MIN/MAX -> decision_engine.threshold_* (resolved a doc/code split-brain: header CLAIMED config-driven, code was hardcoded; DynamicThreshold params now required). A2 regime_governor.py -> new regime_governor section + from_prod_config (INERT: ultron_gate_enabled=false). A3 convergence_controller.py -> new convergence_controller section + from_prod_config (INERT: fusion_use_evaluate=false). A4 acceptance_controller.py -> new acceptance_controller section + from_prod_config. All hash-neutral (params untouched). Built scripts/analysis/behavior_census.py (AST classifier STRUCTURAL/BEHAVIORAL/GOAL_SEEKING + config-wired detection; 67 behavioral/45 future opportunities) + tests/test_behavior_census.py regression floor. Staging doctrine docs/research-readiness/config-first-doctrine.md (NOT CLAUDE.md). PARITY BYTE-IDENTICAL on BNBUSDT f61b44ea...e4e9 + SOLUSDT d2721c2c...b591d (baseline==post-A1==combined). 118 module tests + 6 census/reachability green. 1 unrelated red (test_engine_runner_ml_impl, ML deps absent).
Belief Update / ROI / Goal: Goal: make behavior config-mutable so goal-seeking = generating configs, not editing engines. Belief: config-first is provable WITHOUT behavior drift - fail-fast + JSON-value==prior-literal gives byte-identical ledgers; A2/A3 confirmed currently inert. Knowledge ROI: high - established a repeatable from_prod_config strict-boundary pattern + an evidence engine (behavior_census) turning the doctrine into a test floor. Action: hold doctrine in STAGING until >=4 proven migrations + green census (now met); Batch C (CRTConfig ~30 params knobs, needs rehash) deferred.
Open Questions: confirm full determinism+oracle suite green (running at log time, expected green). When to freeze sec.2-4 into CLAUDE.md (criterion now met - owner call).
Next Step: confirm determinism/oracle; offer owner (a) freeze doctrine into CLAUDE.md, (b) Batch C CRTConfig split-brain, or (c) next census batch (crt_gaussian_scorer hard-filters).
---

---
SESSION LOG ENTRY
Date: 2026-06-15
Topic: Config-First Phase 2 - FREEZE doctrine into CLAUDE.md sec.6.5 + upgrade behavior_census with a maturity model. Owner directive: freeze now (before Batch C), GOAL_SEEKING orthogonal, strong fail-fast rule.
Decision/Output: Froze the Config-First doctrine into CLAUDE.md new sec.6.5 (doctrine cluster, between 6.4 and 7): principle (Frozen Engine + Mutable Behavior + Governed Evolution); META-RULE "Evidence outranks doctrine" placed immediately after principle (freeze only after implementation->parity->census->determinism, never reverse); 3 classes STRUCTURAL/BEHAVIORAL/GOAL-SEEKING; maturity ladder HARD_CODED->CONFIG_WIRED->CONFIG_DRIVEN with GOAL_SEEKING ORTHOGONAL (CONFIG_DRIVEN->GOAL_SEEKING, not every module a tuner); hard rule NO silent defaults (strict _require/from_prod_config, missing key=error, soft .get deprecated, parity=JSON==literal + strict read + byte-identical); 6 questions; enforcement contract behavior_census.py <-> test_behavior_census.py; Batch C note. Flipped staging doc header STAGING->FROZEN(2026-06-15). Upgraded behavior_census.py (additive, read-only): per-module maturity + maturity_summary + orthogonal is_goal_seeking marker + maturity table in MD; always-include tracked migrated modules; check_migrated now pins maturity. Verified: maturity CONFIG_DRIVEN 10 / CONFIG_WIRED 6 / HARD_CODED 6; dynamic_threshold=CONFIG_DRIVEN, regime/convergence/acceptance=CONFIG_WIRED (owner table exact). Tests: 7 census/reachability + 18 doc/findings-enforcement green. No code-path change (census read-only, CLAUDE.md prose) -> determinism/oracle untouched, no re-fingerprint. No F-id (engineering doctrine, not a system finding).
Belief Update / ROI / Goal: Goal: make the proven config-first philosophy CONSTRAIN future work instead of waiting on Batch C. Belief: doctrine has crossed from aspiration to experimentally-verified repository truth (4 byte-identical migrations + census + determinism all green) - so freezing is harvesting the lesson, not premature. Knowledge ROI: high - sec.6.5 + the maturity ladder turn "magic-number count" into a maturity model that future migrations (incl. Batch C) inherit; "Evidence outranks doctrine" is the transferable meta-rule. Action: doctrine frozen; Batch C (CRTConfig ~30 params knobs, needs rehash) becomes the FIRST consumer of the doctrine, not its justification.
Open Questions: none blocking. Batch C sequencing (when owner wants it).
Next Step: Batch C - CRTConfig params split-brain repair under the now-frozen sec.6.5 (rehash via scripts/maintenance/_compute_hash.py); or next census HARD_CODED batch (crt_gaussian_scorer hard-filters). Owner's call.
---

---
SESSION LOG ENTRY
Date: 2026-06-15
Topic: Config-First Phase 3 - evidence-guided prioritization: extra doctrine (precedence hierarchy + authority ladder), SHARPEN behavior_census (external-injection blind spot), migrate PROMOTION_MARGIN, re-rank. Owner sequence: fix the biased instrument BEFORE migrating.
Decision/Output: WI-0 froze into CLAUDE.md sec.6.5 + staging doc: precedence hierarchy Evidence>Doctrine>Preference>Convenience>Elegance; "Evidence quality outranks migration quantity"; "Never optimize using a biased measurement instrument"; AUTHORITY LADDER (anti-self-deception, generalizes beyond config, ties sec.6.1+G001): permanent invariant "evidence has no authority; only demonstrated G001 improvement grants authority"; 4 distinct states Information->Economic usefulness->Authority earned->Architecture justified; corollaries Information!=value, value!=authority, authority!=architecture; REGIME_EXPLOITABLE=information not authority, only CONSUMER_CANDIDATE w/ measured dG001 earns authority; CONFIG_DRIVEN grants tunability not authority. WI-1 sharpened behavior_census: corpus config-key-read scan + curated _CONFIG_SCHEMA_CLASSES{CRTConfig,FusionConfig} + *Result/Record field defaults=STRUCTURAL placeholders; per-const externally_wired/hardcoded split. EFFECT: future config opportunities 45->7, HARD_CODED 6->5, fusion_engine HARD_CODED->CONFIG_WIRED. MAJOR CORRECTION: crt_engine_v2 "27" = 24 externally-wired CRTConfig fields + 3 genuine state defaults => "Batch C" is config-COMPLETENESS (populate active params/crt_engine + rehash) NOT engine surgery. WI-2 migrated model_registry.PROMOTION_MARGIN=0.02 -> governance.promotion_margin via ModelRegistry.from_prod_config() fail-fast (eager singleton); value unchanged 0.02; 91 model_registry/promotion tests green. WI-3 recorded sharpened ranking in staging doc (A5 row + Phase-3 section). Verified: 26 census/reachability/doc-enforcement green; determinism spot-check BNBUSDT f61b44ea...e4e9 BYTE-IDENTICAL (governance/census edits don't touch spine). New test asserts fusion_engine not over-reported.
Belief Update / ROI / Goal: Goal: use the census AS INTENDED (evidence->prioritization->migration) instead of picking Batch C by habit. Belief: the prioritization instrument was BIASED (over-reported HARD_CODED via external-injection blind spot) - fixing it first was higher-leverage than any migration; the genuine backlog is tiny (7 opps) and Batch C is much smaller/different than feared (config-completeness, not 30-knob engine surgery). Knowledge ROI: high - sharpened census now gives trustworthy rankings for all future migrations; PROMOTION_MARGIN harvested as the clean genuine win; authority ladder is the transferable anti-self-deception doctrine. Action: trustworthy backlog established; remaining genuine HARD_CODED are advisory/dormant/3-state-defaults; Batch C = config-completeness task (owner's call, needs rehash).
Open Questions: Batch C (CRTConfig active-config completeness + rehash) timing - owner's call. The 3 crt_engine_v2 state defaults (decay_factor/risk_pct/soft_conf_candles) - migrate or leave (low value).
Next Step: owner decision: Batch C config-completeness (populate params/crt_engine + rehash) OR sweep remaining tiny HARD_CODED OR stop (backlog now trustworthy + small).
---

---
SESSION LOG ENTRY
Date: 2026-06-15
Topic: Config-First Phase 4 (Batch C) - CRT config-completeness, REFRAMED by Phase-3 instrument repair: NOT engine surgery, NOT rehash. Hash-neutral crt_engine population + state-default classification.
Decision/Output: Investigation: load_prod_config builds CRTConfig={**crt_engine,**params}, hash covers params ONLY -> crt_engine is the unhashed defaults layer. Exact gap = 12 CRTConfig fields absent from crt_engine+params (of 48), each resolving to dataclass default. WI-C1: populated all 12 into crt_engine with value==dataclass default (breakout_disp_threshold 1.5, exit_model 'intrabar_touch' [load-bearing governing exit, previously IMPLICIT], score_threshold 0.45, use_bitnet false, extension_reset_fib 1.618, pending_displacement_ttl_candles 4, max_expansion_age_candles 495/hours 124, expansion_age_warn_candles 342, shadow_advisory_only false, shadow_age_norm_candles 0, shadow_age_penalty_lambda 0.0). HASH-NEUTRAL, NO rehash (owner: crt_engine=defaults layer, params=tuned/hashed). allowed_sessions EXCLUDED (engine_runner-owned via resolve_allowed_sessions; would create new split-brain). PARITY BYTE-IDENTICAL BNB f61b44ea...e4e9 + SOL d2721c2c...b591d. WI-C2: 3 state defaults (RiskScore.decay_factor/Trade.risk_pct/EngineState.soft_conf_candles) classified STRUCTURAL placeholders (real knobs score_decay_lambda/sizing_bands/soft_conf_max_candles already config-driven) via census _RESULT_SCHEMA_RE+State + _RUNTIME_STATE_CLASSES -> crt_engine_v2 genuine HARD_CODED 3->0 -> CONFIG_WIRED. WI-C3: added §6.5 + staging-doc corollary "correcting the instrument often creates more value than optimizing the system". WI-C4: census re-run HARD_CODED 5->3, opportunities 7->3 (only signal_audit advisory + signal_belief_tracker sidecar + HMF dormant remain). Verified: config loads+hash OK; 27 census/reachability/doc-enforcement green; new crt_engine_v2 + fusion_engine census assertions green. determinism+oracle suite running (corroboration; fingerprint already byte-identical).
Belief Update / ROI / Goal: Goal: close the F-018 CRT split-brain (config = explicit source of truth). Belief: Batch C was MUCH smaller than the original "30-knob engine surgery + rehash" fear - the instrument repair revealed it as a 12-field hash-neutral config-completeness pass; the program has reached its meaningful END (every live behavior-affecting knob now config-driven; remaining 3 are advisory/sidecar/dormant). Knowledge ROI: high - "Batch C needs rehash" belief RETIRED (evidence outranks expectations); the governing exit_model is now explicit in config (was implicit). Action: config-first migration program COMPLETE for live knobs; remaining HARD_CODED are intentionally skipped (advisory/sidecar/dormant).
Open Questions: none blocking. Optional micro-items: signal_audit warn thresholds (advisory) if ever wanted; otherwise STOP - backlog is intentionally empty of high-value items.
Next Step: program effectively done. Optional: commit the work; or migrate the 3 advisory/sidecar knobs only if their modules become live (don't - F-012 theater). Goal-seeking (generating candidate configs over the now-complete crt_engine) is the natural next CAPABILITY, separate from migration.

---
📝 SESSION LOG ENTRY
Date: 2026-07-09T12:05:00Z
Topic: Commit CH-002 F-050 remediation (selective stage)
Decision/Output: Staged CH-001 foundation + CH-002 emission rename + CRT closure docs/tests + geometry census/gate2b regen only. Excluded unrelated dirty tree (prod config, engine_runner, research fleet, zone_gate_registry, etc.). Commit message covers F-050 rename + CRT CLOSED.
Belief Update / ROI / Goal:
  Goal: durable git checkpoint for F-050 remediation without contaminating commit with unrelated WIP.
  Belief: CH-002 is commit-ready as a self-contained foundation+rename set.
  Knowledge ROI: medium (hygiene / recoverability).
  Action: commit then stop (no push).
Open Questions: historical training corpus rebuild under FM keys (optional).
Next Step: user may push or continue OI-ER-001 / other backlog.
---
📝 SESSION LOG ENTRY
Date: 2026-07-09T11:40:00Z
Topic: CH-002 complete — census/adjudication regenerated; IMPACT APPROVED; 130 tests green
Decision/Output: Regenerated geometry_census + gate2b adjudication after emission rename; gate2b T-table line numbers updated for crt_engine_v2/crt_gaussian_scorer/derived_math FM-027/028. construction_protocol validate-impact APPROVED. Full required floor 130 passed. CRT_CLOSURE_STATUS=CLOSED stands.
Belief Update / ROI / Goal:
  Goal: complete construction-protocol floor for F-050 rename.
  Belief: CH-002 is machine-closed (census fresh, adjudication closed, F-050 seed preserved as remediated history).
  Knowledge ROI: high.
  Action: STOP.
Open Questions: historical training corpus rebuild under FM keys (optional).
Next Step: OI-ER-001 or other backlog; do not re-introduce retest_depth/disp_strength as CRT cache keys.
---
📝 SESSION LOG ENTRY
Date: 2026-07-09T11:35:00Z
Topic: CH-002 F-050 emission rename → CRT_CLOSURE_STATUS=CLOSED
Decision/Output: Remediated F-050 emission keys under construction protocol CH-002. crt_engine_v2 cached_features + crt_gaussian_scorer now emit displacement_retrace (FM-027) + displacement_atr_ratio (FM-028) via derived_math; pipeline FM-021/020 unchanged. BitNet call-site maps FM→legacy input names. F-050 VALIDATED+REMEDIATED; CLAUDE.md index updated. crt_closure_report → CLOSED. Adversarial+findings+derived/formula tests green (50). No production config change.
Belief Update / ROI / Goal:
  Goal: honest CRT emission identity for train/serve and closure.
  Belief: CRT boundary name collision is fixed; residual is historical JSONL + BitNet schema adapter.
  Knowledge ROI: high — unblocks CRT CLOSED; enables safe downstream work without false feature names.
  Action: STOP; optional next OI-ER-001 or HC config-first backlog.
Open Questions: when to rebuild historical training corpora under FM keys.
Next Step: Optional OI-ER-001 admission provenance; do not re-emit under retest_depth/disp_strength on CRT cache.
---
📝 SESSION LOG ENTRY
Date: 2026-07-09T11:10:00Z
Topic: CRT Closure Phase 8 — closure report + verdict
Decision/Output: Wrote docs/governance/crt_closure_report.md + tests/test_crt_closure_report.py. Verdict CRT_CLOSURE_STATUS=BLOCKED:F-050_BOUNDARY_NAME_COLLISION. Criteria 1–6,8–9 PASS; criterion 7 FAIL (F-050 name collision documented+enforced but not remediated). 13/13 candidates explained; authority UNIQUE; 33 diversions; config matrix complete; adversarial suite green. No production remediation. No new findings.
Belief Update / ROI / Goal:
  Goal: declare CRT closed only when boundary identity is honest.
  Belief: CRT is inventory-complete and CI-enforced; blocking gap is emission naming (F-050), not unknown control flow.
  Knowledge ROI: high — freezes CRT denominator; next work is F-050 remediation not rediscovery.
  Action: STOP program; next = F-050 rename under construction protocol.
Open Questions: none for Phase 8 checklist; OI-ER-001 remains downstream.
Next Step: Remediate F-050 (emission keys → FM-027/028) then re-run adversarial + re-evaluate CLOSED.
---
📝 SESSION LOG ENTRY
Date: 2026-07-09T10:50:00Z
Topic: CRT Closure Phase 7 — adversarial validation
Decision/Output: Added tests/test_crt_adversarial_closure.py (21 tests) + docs/governance/crt_adversarial_validation.md. Covers formula drift, F-050 name≠math, illegal transition non-mutation, reset cleanup, 13-candidate required sequences, dead/legacy config flags, hardcoded shadows, diversion floor, unique authority, displacement body gate. Controls pass. Related CRT suite 36 passed. No production code changes. PHASE7 PASS.
Belief Update / ROI / Goal:
  Goal: machine-enforce CRT contracts so future edits fail CI.
  Belief: CRT closure artifacts are now load-bearing; silent graph/config/candidate drift will fail tests.
  Knowledge ROI: high — turns Phases 1–6 documentation into enforcement.
  Action: STOP; await Phase 8 closure report.
Open Questions: none for Phase 7.
Next Step: Phase 8 — CRT closure report and CLOSED/BLOCKED verdict.
---
📝 SESSION LOG ENTRY
Date: 2026-07-09T10:30:00Z
Topic: CRT Closure Phase 6 — 13-candidate CRT provenance
Decision/Output: Reconstructed all 13 CRT TRADE_OPENED from baseline events (no new backtest). docs/governance/crt_13_candidate_provenance.{json,md}. 7 GOLDEN + 6 SHADOW paths; all COMPLETE; S_score 0.371–0.571 (tier_2); risk_pct=0.005. 11 journaled / 2 CRT-only (CRT-0001, CRT-0011) = ER veto residual. PHASE6 PASS. CRT-side only.
Belief Update / ROI / Goal:
  Goal: every CRT candidate has one causal chain to TRADE_OPENED.
  Belief: no unexplained CRT opens; shadow path is 6/13 of admits; residual 2 are post-CRT.
  Knowledge ROI: high — closes candidate-truth criterion for CRT closure checklist.
  Action: STOP; await Phase 7.
Open Questions: none for CRT emission; OI-ER-001 for the 2 non-journaled.
Next Step: Phase 7 — adversarial CRT validation tests.
---
📝 SESSION LOG ENTRY
Date: 2026-07-09T10:00:00Z
Topic: CRT Closure Phase 5 — config reachability
Decision/Output: Wrote docs/governance/crt_config_reachability.{json,md}. 48 CRTConfig fields mapped: 42 REACHABLE, 4 CONSUMED_DYNAMIC (intent TP1), 1 LEGACY_ONLY (score_threshold soft-conf path), 1 DEAD_LOADED (news_blackout_minutes). Hardcoded HIGH: G-weights 0.35/0.25/0.20/0.20; retest min_depth 0.1*atr. BNB market_router class=FOREX (latent; prod params override). Load chain params>crt_engine documented. tests/test_crt_config_reachability.py. PHASE5 PASS. No remediation.
Belief Update / ROI / Goal:
  Goal: every CRT behavior knob traced to consumption or proven dead/legacy.
  Belief: primary soft-conf path ignores score_threshold; news minutes dead; structural G weights not config-first.
  Knowledge ROI: high — freezes config truth before candidate provenance.
  Action: STOP; await Phase 6.
Open Questions: whether to externalize G-weights/min_depth in future remediation batch.
Next Step: Phase 6 — 13 CRT-side candidate causal provenance from baseline artifacts.
---
📝 SESSION LOG ENTRY
Date: 2026-07-09T09:40:00Z
Topic: CRT Closure Phase 4 — diversion/reset census
Decision/Output: Registered 33 CRT diversions in docs/governance/crt_diversion_registry.jsonl + .md. Baseline activation mapped (HTF reset 14775, session filter 31, expansion TTL 16, soft-conf 47→16 EXECUTION→13 TRADE_OPENED, inverted-SL residual 3). Prod-inactive: BitNet/shadow advisory/shadow decay. Observation OI-CRT-EXEC-NO-TRADE (EXECUTION without trade after inverted SL). No remediation. PHASE4 PASS.
Belief Update / ROI / Goal:
  Goal: every CRT diversion registered before config reachability.
  Belief: session filter is the dominant post-retest absorb on BNB baseline; inverted-SL can leave EXECUTION without trade.
  Knowledge ROI: high — freezes diversion denominator for Phase 5–7.
  Action: STOP; await Phase 5.
Open Questions: sticky EXECUTION-without-trade frequency outside BNB; hardcoded 0.1 min retest depth config externalization.
Next Step: Phase 5 — CRT configuration reachability matrix.
---
📝 SESSION LOG ENTRY
Date: 2026-07-09T09:05:00Z
Topic: CRT Closure Phase 3 — 9-state executable graph
Decision/Output: Froze docs/governance/crt_executable_state_graph.{json,md} reconstructed from crt_engine_v2. 9 states; VALID_TRANSITIONS parity; force-reset side-channel documented; shadow double-transition governed; soft-conf flag-dispatch and retest-before-TTL order rules recorded. Added tests/test_crt_executable_state_graph.py (8 checks) + state invariants — 9 passed. PHASE3 PASS. No remediation.
Belief Update / ROI / Goal:
  Goal: CRT state truth machine-checked before diversions census.
  Belief: Graph is complete; RANGE arrivals often via reset_to_range bypass; RETEST progress is flag-driven not elif s==RETEST.
  Knowledge ROI: high — freezes transition denominator for Phase 4 diversion registry.
  Action: STOP; await Phase 4.
Open Questions: none for graph structure; diversion exhaustiveness is Phase 4.
Next Step: Phase 4 — diversion/reset/veto census.
---
📝 SESSION LOG ENTRY
Date: 2026-07-09T08:35:00Z
Topic: CRT Closure Phase 2 — input/formula contract
Decision/Output: Wrote docs/governance/crt_formula_contract.{json,md}. All CRT raw/derived values classified (0 unaccounted). F-050 boundary documented: CRT cached retest_depth=FM-027 displacement_retrace; disp_strength=FM-028 displacement_atr_ratio; body_ratio FM-010 aligned. Third retest concept (range depth_abs) documented. G-score weights hardcoded noted for Phase 5. Confirmed F-046/F-047/F-050; NEW_FINDINGS none. No remediation. PHASE2 PASS.
Belief Update / ROI / Goal:
  Goal: CRT isolated formula truth before state-graph and remediation.
  Belief: CRT formula surface is fully accountable; remaining risk is name collision at emission boundary (known F-050), not hidden math.
  Knowledge ROI: high — freezes formula denominator for Phase 3+ and blocks false Gate-6 scope creep into rediscovery.
  Action: STOP; await Phase 3 authorization.
Open Questions: G-weight config externalization (Phase 5); rename timing for FM-027/028 keys.
Next Step: Phase 3 — 9-state executable graph code↔VALID_TRANSITIONS parity.
---
📝 SESSION LOG ENTRY
Date: 2026-07-09T08:05:00Z
Topic: CRT Closure Phase 1 — executable surface freeze
Decision/Output: Froze CRT production surface in docs/governance/crt_executable_surface.{json,md}. Authority UNIQUE: crt_engine_v2.CRTEngine (process_candle L2257); sole runtime SM caller backtest_v2. Parallel names classified (engines.crt_engine ACTIVE score-slot; s01 wrapper; dead feature builder; weekly research). Live path does not wire SM (OI-LIVE-SM). Open items frozen: OI-ER-001, OI-F048-E2E, OI-GATE6, OI-ARCH-MS. PHASE1 PASS. No production code changes. No Phase 2 yet.
Belief Update / ROI / Goal:
  Goal: close CRT as isolated trusted subsystem before downstream/model audits.
  Belief: SM authority is unique; "CRT" name collision with fusion score slot is a role distinction, not split-brain. Live SM unwired is a separate open item.
  Knowledge ROI: high — freezes denominator for Phases 2–8 without expanding to EngineRunner.
  Action: STOP for user review; await Phase 2 authorization.
Open Questions: Which CRTConfig fields are dead/shadowed (Phase 5)? F-050 boundary semantics (Phase 2)?
Next Step: User authorizes Phase 2 (input/formula contract) or requests Phase 1 adjustments.
---
📝 SESSION LOG ENTRY
Date: 2026-07-09T07:30:00Z
Topic: Pre-remediation baseline backtest (BNBUSDT, gate-ON, frozen)
Decision/Output: Ran canonical backtest_v2 BNBUSDT twice with BACKTEST_ENGINE_GATE=1; wrote reports/PRE_REMEDIATION_BASELINE.md. Bare CLI loads .env→gate OFF (13 trades); official prod-fidelity gate ON = 11 trades, 2× invalid_session rejects, PnL net −4.251R, PF 0.509, WR 27.3%. Deterministic equality YES (summary/trades/report/events byte-identical). F048_REPRODUCED=NO (trades journaled; low_rr not observed as journal absorb). No code/config/model changes. No new findings.
Belief Update / ROI / Goal:
  Goal: freeze a reproducible behavioral baseline before Gate 6 remediation.
  Belief: bare backtest_v2 is NOT fusion-live-equivalent without forcing BACKTEST_ENGINE_GATE=1; F-037 13→11 confirmed; F-048 low_rr is source-true in isolation but not the observed journal absorb on CRT candidates in this harness.
  Knowledge ROI: high (pins commit+hashes+funnel+determinism; prevents post-remediation false deltas).
  Action: STOP; use reports/PRE_REMEDIATION_BASELINE.md as the pre-Gate-6 reference; do not remediate from this turn.
Open Questions: Are the 11 ER admits true DecisionEngine execute vs fail-soft allow? Clean-checkout parity under dirty worktree?
Next Step: Proceed to Gate 6 remediation only when ready; re-run the exact gate-ON command for post-remediation delta.
---
📝 SESSION LOG ENTRY
Date: 2026-07-08
Topic: Gate-2 Step 7c (REOPENED) — EngineRunner.run() decision-flip harness + E-001 correction of premature Gate-2 "complete"
Decision/Output: CORRECTED an overclaim: last turn I declared Gate 2 complete with observed_decision_flips=not_measured (score drift ≠ decision drift). Built read-only feature_math_decision_flip_probe.py driving the REAL EngineRunner.run() twice/candle (Branch A current body/total_wick vs Branch B canonical), A/B sharing the same evolved adaptive state via deepcopy snapshot per candle + a frozen-threshold sensitivity pass. Debugged three harness-fidelity confounds before the number meant anything: (1) session-encoding mismatch (pipeline SESSION_MAP 0=london vs trap_validator 0=asia) — fixed by passing string session; (2) zone_gate_invalid rejects EVERY candle in run() (DecisionEngine:129 needs zone_gate['valid'] which run() never sets) — bypassed class-level exactly as backtest_v2 does (orthogonal to body_ratio); (3) deepcopy+instance-monkeypatch state-leak — fixed with class-level patch so self resolves to the copy. RESULT: 0 decision flips / 39,456 score-gated / 70,002 candles (adaptive AND frozen); 0 approvals either branch. GD-001/002 are score-material (96.7%) but DECISION-INERT — fused-Δ (0.4·ΔCRT ≈ 0.002-0.013) never crosses the score/rr/threshold gauntlet. Re-ranked remediation from measured flips: GD-001/002 dropped from "#1 behavior-changing" to hygiene; GD-005/004 (rename) now top. Froze Matrix v2-final. E-001 fix-the-SOURCE: corrected the premature "Matrix v2 frozen / #1 behavior-changing" in the adjudication doc, F-047, CLAUDE.md §6.2 row, memory, and annotated the archived 2026-07-07 session-log entry CORRECTED. ZERO edits to the 10 divergent sites (durable-key floor green = byte-proof); lint floor GREEN, 10 lint tests pass.
Belief Update / ROI / Goal: Goal: measure whether canonicalizing GD-001/002 changes real decisions. Belief FLIPPED TWICE: last turn "score-material → likely behavior-changing"; this turn "DECISION-INERT (0/39,456 flips) → hygiene". The 96.7% score-channel drift propagates to 0 decisions because hard gates (zone/session/rr) + the adaptive threshold dominate. Knowledge ROI: high — converted a score-drift alarm into a measured decision null, and caught my own premature-completion overclaim. Action: de-prioritize GD-001/002; rename GD-004/005 first in Phase B. Guard: the harness bounds (not exhaustively measures) the ~13 CRT-gated live setups — a CRT-spine harness is the residual step.
Open Questions: Among the ~13 real CRT-EXECUTION-gated live setups (which this per-candle harness doesn't reproduce), does body_ratio ever flip? (needs a CRT-spine harness). Should the two incidental finds (session-encoding mismatch; zone_gate_invalid always-rejects in run()) get their own findings?
Next Step: (user-gated) file the two incidental findings; Phase-B remediation in re-ranked order (GD-005/004 rename → GD-003/010 parity → GD-001/002 hygiene → GD-006/007 → GD-008/009 delete), retiring each GD via the manifest as its site resolves.
---
📝 SESSION LOG ENTRY
Date: 2026-07-08
Topic: 7c harness validation — RETRACT invalid 0-flip + V1-V10 → POSITIVE_CONTROL_NOT_CONSTRUCTIBLE (structural decision-inertia)
Decision/Output: Step 0 (E-001 #2): retracted the finalized 7c result at every source (pins→not_measured, adjudication doc + json un-frozen, F-047, CLAUDE.md §6.2, memory). V1-V10 validation of the decision-flip harness: V1 deepcopy DOES isolate in-memory decision state (state-surface mapped); V4 corpus parity FAILS (score probe 19,922 vs decision probe 70,002); V5 prior harness was 2-field (body_ratio+wick_size) — correct is body_ratio-only (no decision-path reads input_data["wick_size"], grep-confirmed). V9 POSITIVE CONTROL = NOT CONSTRUCTIBLE, and the reason is structural: run() can NEVER return execute — DecisionEngine rr gate compares RREngine polarity rr_ratio∈[0,1] (rr_engine.py:79) against rr_threshold=1.5 → low_rr fires on every candle after the score passes (0/70,002 executes, empirically); AND in the backtest run() is a VETO (backtest_v2:2182) whose only non-veto reject-reason is zone_gate_invalid (bypassed), which is body_ratio-independent. body_ratio reaches only the fused SCORE (CRT weight 0.4) → it can move the reject REASON (low_score↔low_rr) but never execute/veto. ⇒ body_ratio is DECISION-INERT at the run() boundary BY STRUCTURE (source-confirmed). Building a legit positive control would require bypassing the rr gate = replacing production decision logic → V9 escape clause → STOP. Wrote reports/decision-flip-validation.md. FINAL STATUS = POSITIVE_CONTROL_NOT_CONSTRUCTIBLE. Did NOT re-run the full corpus, freeze Matrix v2, or re-rank.
Belief Update / ROI / Goal: Goal: prove whether canonicalizing body_ratio flips real decisions. Belief FLIPPED AGAIN (3rd time) — from "score-material→likely behavior-changing" (turn 1) → "decision-inert, 0 flips" (turn 2, RETRACTED) → "not measurable at run(); decision-inert BY STRUCTURE (rr/zone body_ratio-independent, execute unreachable)" (this turn). Knowledge ROI: high — the counterfactual harness was the WRONG instrument; source structure gives a stronger inertia proof AND explains why the number was 0. Caught a second premature-completion overclaim. Action: recommend a backtest-LEDGER diff as the correct empirical instrument (predicted 0). LESSON: a reproducible number from an instrument that structurally can't produce the alternative outcome is not evidence — prove the instrument can detect the effect (positive control) BEFORE trusting a null.
Open Questions: Confirm the structural prediction empirically via a backtest-ledger diff (canonical vs current body_ratio → CRT trades surviving the run() veto)? File the 3 incidental findings (low_rr [0,1]-vs-1.5 always-reject; session-encoding mismatch; rotate-log same-date overwrite)?
Next Step: (user-gated) build the backtest-ledger differential (the correct instrument) OR accept the source-structural decision-inertia; file the incidental findings; then Phase-B remediation (hygiene if inert).
---
📝 SESSION LOG ENTRY
Date: 2026-07-08
Topic: Decision-boundary integrity + RR contract adjudication (read-only) → F-048 candidate filed; body_ratio instrument BLOCKED
Decision/Output: Read-only investigation (Gates 1-3). GATE 1 (RR contract): RREngine is the "Candle Polarity Index (formerly misnamed RR Engine)" — rr_ratio = polarity∈[0.5,1], a LEGACY field name, semantic="candle_structure_quality", explicitly "not forward RR" (git b34d6a8 "stable before rename"). engine_runner:957 wires this polarity into DecisionEngine's fusion["rr"] < rr_threshold=1.5 gate → low_rr fires every candle → run() can NEVER execute (0/70,002). Consumer intent = TRUE RR ratio (test_crt_fixes:224 injects fusion={"rr":2.0} to get execute). Real RR check is in UltronRiskGate (reads ExecutionPlanner SL/TP-derived trade rr_ratio, ultron_risk_gate:230-245) — SEPARATE, exactly as RREngine docstring states. Verdict: SEMANTIC_MISMATCH / NAME_COLLISION at engine_runner:957. GATE 2 (decision-boundary census): LIVE = run()→ExecutionPlanner(HARD-gates on run()=="execute", execution_planner:208)→UltronRiskGate→alert → structurally can NEVER admit a trade (run() always rejects); consistent w/ F-010; live_engine_hook only called by agent pipeline_mode:160 (not a verified prod loop). BACKTEST_GATE_ON = CRT state machine opens trade + run() VETO (backtest_v2:2182, bypasses zone_gate_invalid). BACKTEST_GATE_OFF/RESEARCH = CRT state machine ONLY (run() not called, F-037) — the trade admitter for ALL findings. GATE 3: the three boundaries are NON_EQUIVALENT (different owners/gates/RR-semantics). GATE 4: body_ratio instrument = RR_CONTRACT_REMEDIATION_REQUIRED — run() is structurally invalid + non-authoritative for research; body_ratio's live-hook divergence feeds only run()'s inert score, and never the authoritative CRT displacement gate (which uses the canonical Candle.body_ratio, F-046). Filed F-048 (CANDIDATE, not BUG — mismatch Certain, intent open). Did NOT build the ledger differential, remediate, re-freeze, or re-rank.
Belief Update / ROI / Goal: Goal: prove which decision boundary is authoritative before choosing a body_ratio instrument. Belief: the RR contract mismatch is a MORE fundamental defect than the body_ratio divergence — it structurally breaks the LIVE decision path (can't admit a trade) and explains why run() can't measure flips. The authoritative research/backtest boundary is the CRT state machine, which doesn't even consume the divergent body_ratio. Knowledge ROI: very high — reframed the whole 7c question; the instrument-hunt was chasing a non-authoritative, structurally-broken boundary. Action: adjudicate RR contract intent (bug vs dormant-live) before any body_ratio work. LESSON: prove the boundary is authoritative before measuring against it (don't move the boundary until a result appears).
Open Questions: Is the RR mis-wire an unintended bug or an intentionally-dormant live path (needs design-doc/git intent evidence)? Should the DecisionEngine rr gate consume UltronRiskGate's SL/TP-derived rr_ratio instead of RREngine polarity? Is live_engine_hook meant to be operational at all (F-010)?
Next Step: (user-gated) adjudicate F-048 intent (tests/git/design) → decide remediation (fix the wire vs document dormant-live); only after that select the body_ratio instrument (likely the CRT-spine boundary, not run()). File the 3 sibling candidates (session-encoding, zone-always-reject, rotate-log overwrite).
---
📝 SESSION LOG ENTRY
Date: 2026-07-08
Topic: F-048 intent + remediation-options adjudication (read-only) → Option B identified (gated); mismatch CONFIRMED, git-intent unrecoverable
Decision/Output: GATE 1 (git): history SQUASHED — only "stable before rename"/"commit" touch rr_engine; even b34d6a8 already returns rr_ratio=polarity, so the true-RR era predates recoverable history → original intent NOT reconstructable from git. GATE 2 (tests): NO test exercises production run()→real DecisionEngine rr gate→execute; the two execute-asserting tests use _DummyDecision (always execute) + injected fusion={"rr":2.0} (test_crt_fixes:224) → MOCK_ONLY / synthetic (B), proving the CONSUMER expects a true RR≥1.5 but NOT that production can satisfy it. The always-reject is a TEST GAP. GATE 3 (config): rr_threshold=1.5 (decision) == min_rr_ratio=1.5 (ultron) — SAME threshold → the DecisionEngine gate was meant as a DUPLICATE of Ultron's true-RR check; the rr check is UNCONDITIONAL (no disable flag); no active/historical config supplies a true RR to fusion_ctx["rr"]. Availability: the true RR (CRT trade risk_reward_tp1 / ExecutionPlanner SL-TP) is computed AFTER run() and is NOT in run()'s input → UNAVAILABLE at DecisionEngine (Step 7) time. GATE 4 (options): A (rewire to true RR) INFEASIBLE (true RR not available at DecisionEngine time; ordering/circular); B (remove the redundant broken DecisionEngine rr gate; UltronRiskGate is the sole true-RR enforcer) SEMANTICALLY CORRECT but activates run()=execute → unvalidated live/gate-on behavior; C (retune to polarity floor) incoherent (duplicates RREngine fusion contribution); D (document run()-decision/live path dormant, no behavior change) lowest-risk interim. GATE 5: F048_REMEDIATION_OPTION_IDENTIFIED = Option B, GATED behind (a) gate-on backtest ledger differential + (b) live-activation safety OR Option-D dormancy guard. NOTE: run() has ≥2 always-reject gates (rr AND zone_gate_invalid) → removing rr alone may NOT activate live (zone still blocks) — reduces activation risk but confirms systemic decision-boundary integrity issues. Did NOT implement, remediate, or edit src/.
Belief Update / ROI / Goal: Goal: pick the smallest architecture-preserving F-048 correction. Belief: the DecisionEngine rr gate is a REDUNDANT, mis-wired duplicate of UltronRiskGate's true-RR check (same 1.5 threshold), broken because true RR isn't available at DecisionEngine time — Option B (remove it) is correct but its live-activation surface is the real risk; and there are MULTIPLE broken always-reject gates (rr+zone) so the run() decision boundary is systemically non-functional-as-an-approver (veto-only in practice). Knowledge ROI: high — narrowed 5 options to B-gated with a concrete failure surface, and confirmed intent is unrecoverable from squashed git (so remediation must be justified by architecture, not history). Action: recommend F-048 CANDIDATE→CONFIRMED (mismatch); design a governed gate-on-backtest differential before any Option-B implementation; do not touch live activation without validation.
Open Questions: Is the live/EngineRunner-decision path intended to be operational (Option D) or fixed-and-activated (Option B)? Does removing the rr gate activate live given the zone gate also blocks? What's the gate-on backtest trade-count delta if run() can execute?
Next Step: (user-gated) upgrade F-048 to CONFIRMED; design (not run) the governed gate-on-backtest ledger differential for Option B; decide live dormancy (Option D) vs activation. Still no body_ratio work, no Matrix freeze, no GD re-rank.
---
📝 SESSION LOG ENTRY
Date: 2026-07-08
Topic: F-049 Geometry Canonicalization + Blast-Radius Audit — installment 1 (read-only): zero-range policy + census + ENFORCEMENT_BYPASS_FOUND
Decision/Output: Froze F-048/gate/7c/body_ratio per user pivot. Began F-049 read-only audit vs frozen spec F1-F9. GATE 0 (zero-range): policies DIVERGE across producers — candle_math/feature_pipeline/rr_engine return 0.0 on zero-range; crt_engine_v2:1044 + crt_sweep_taxonomy epsilon-FLOOR the denominator to max(range,0.001) (finite large ratio, not 0). No single canonical zero-range policy. GATE 1 (census, repo-wide write-sites for the 10 geometry quantities across name=/dict[..]=/df[..]=/.attr= surfaces): ~57 real src/ sites + tests 68/scripts 25/tools 13/governance 3/uat 3/strategies 5/analytics 1/utils 3/research 1 (.claude worktrees + .venv excluded as copies). GATE 4 (bypass audit): ENFORCEMENT_BYPASS_FOUND — the ownership lint (feature_math_lint) has ≥3 false-negative classes: (1) _SCAN_DIRS=only 5 live-spine dirs → scripts/tools/tests/governance/uat/strategies/analytics/utils/research all bypass; (2) _target_names yields only ast.Name → Subscript writes (df["body_ratio"]=) uncaught; (3) Attribute writes (self.x=) uncaught. So F-047's "mechanically enforced/AUTHORITATIVE WHAT layer" is OVERSTATED — DOWNGRADED the claim in current-findings.md per the user guard. GATES 2/3/5/6/7 (full semantic adjudication, F7-F9 oracle/property/cross-producer parity, blast-radius graph, matrix freeze, remediation units) NOT done — audit INCOMPLETE. No production changes, no formula replacement, no retrain, no artifact deletion.
Belief Update / ROI / Goal: Goal: prove (not assume) whether geometry math is repository-wide canonical + enforced before trusting downstream evidence. Belief: it is NOT — enforcement is live-spine-Name-only (3 bypass classes), zero-range policy is inconsistent, and ~128 out-of-lint-scope write-sites are unclassified. The F-047 WHAT-authority claim was premature. Knowledge ROI: high — a single grep + lint-scope read invalidated the "authoritative+enforced" claim and surfaced a zero-range divergence, before any downstream measurement was trusted. Action: complete the census→adjudication→oracle→blast-radius→matrix; upgrade the lint (dirs + Subscript/Attribute targets) only AFTER the bypass census freezes. LESSON: an enforcement layer's AUTHORITY = its coverage; prove coverage before claiming authority.
Open Questions: Which zero-range policy is canonical (return-0.0 vs epsilon-floor)? Full classification of the ~128 out-of-scope sites (real derivations vs transport vs test-oracle)? Blast-radius of any NON_EQUIVALENT out-of-scope derivation into training/model artifacts?
Next Step: (user-gated) GATE 0 policy decision; complete GATE 1 census with DERIVATION_IDs for all sites; GATE 2 adjudication; GATE 3 oracle+property+cross-producer parity (incl. F7-F9 upper/lower_wick_ratio, wick_ratio — NOT currently registered/tested); then GATE 5/6. Upgrade the lint scope+target-surfaces after the bypass census freezes.
---
📝 SESSION LOG ENTRY
Date: 2026-07-08
Topic: F-049 installment 2 — census methodology FROZEN (Gates 1A-1G) + zero-range evidence matrix (Gate 0)
Decision/Output: Built scripts/analysis/geometry_census.py: 3 INDEPENDENT discovery methods (NAME=AST usage of governed names incl. string-args/dict-keys/kwargs; EXPRESSION=normalized-AST formula patterns F1-F9 + eps/clip/np.where/np.divide/Series.div variants + single-level alias & helper-return resolution; SINK=writes into governed sinks incl. df columns/assign kwargs/dict.update/tuple-unpack), reconciled into docs/governance/geometry_census.jsonl (content-based ordinal-stable OCCURRENCE_IDs + DERIVATION_IDs, line-movement invariant) + geometry_census_summary.json (universe manifest: 477 tracked + 243 untracked-exec py files scanned; .claude/venv/archive/generated excluded; 21 untracked-other disclosed unscanned). COUNTS: 373 occurrences / 83 derivations / 80 producers / 85 transport / 198 consumers / 3 test-oracles / 7 UNKNOWN. Reconciliation: NAME_ONLY 198 · EXPRESSION_ONLY 47 (hidden derivations WITHOUT governed names — incl. scripts/backtest/manual_backtest.py independent body_ratio/wick_size impl; crt_gaussian_scorer:187-190 disp_move/retest_retrace; crt_engine_v2 F1_BODY 'move' sites 1211/1378/2104) · SINK_ONLY 90 · NAME_AND_SINK 24 · ALL_THREE 14. GATE 1G adversarial floor tests/test_geometry_census.py: 29/29 green — 100% synthetic recall on 17 bypass fixtures (attr/subscript/df-col/dict.update/assign/tuple/helper-return/alias-OHLC/np.divide/Series.divide/np.where/eps-floor/clip/name-free formulas/GD-001 form), 0 false positives on 7 negative controls, ID uniqueness + line-movement stability proven. GATE 0 evidence (reports/zero-range-evidence.json, NO policy decision): true zero-range candles = 0 on crypto majors, 1-2 on FX majors, 61,477/70,080 (87.7%) DOGE + 23,964 (34.2%) XRP (price-granularity artifacts); ohlcv_schema:188 PERMITS high==low; KEY: the 0.001 eps-floor (crt_engine_v2:1044/crt_sweep_taxonomy:122) is PRICE-SCALE-DEPENDENT — binds on 75-91% of FX-major candles (distorting normalized wick ratios there) but 0% of crypto majors; policies diverge only on NEAR-zero range. Read-only/additive; no Gate 2, no remediation, no lint change.
Belief Update / ROI / Goal: Goal: make the geometry census reproducible+completeness-tested before semantic adjudication. Belief: name-based search WAS insufficient — expression-first discovery found 47 derivations invisible to governed-name search (incl. an independent scripts/ implementation); and the eps-floor zero-range policy is not one repo-wide behavior but an asset-class-dependent distortion (FX 75-91% bind vs crypto 0%). Knowledge ROI: high — the census instrument is now provably better than the enforcement lint it audits. Action: Gate 2 semantic adjudication may begin (census frozen); zero-range POLICY decision still open (user-gated), with the FX bind-rate as the decisive new evidence. LESSON: measure the measuring instrument first (synthetic recall floor), then measure the world.
Open Questions: Zero-range canonical policy (0.0 vs floor — floor now shown FX-distorting on 75-91% of candles, but only in decision-unreachable diagnostic sites)? Gate 2: classify the 83 derivations (esp. the 47 EXPRESSION_ONLY hidden ones + 7 UNKNOWN writes)? Are DOGE/XRP corpora fit for any geometry-dependent research (87.7%/34.2% zero-range)?
Next Step: (user-gated) GATE 2 semantic adjudication over the frozen census artifact; then Gate 3 oracle/property/cross-producer floors (F7-F9 currently untested); zero-range policy decision from the evidence matrix.
---
📝 SESSION LOG ENTRY
Date: 2026-07-08
Topic: F-049 GATE 2A COMPLETE — census defects repaired, universe expanded, Census v2 FROZEN (STOP before Gate 2B per directive)
Decision/Output: Repaired 4 census-tool defect classes found via residuals: (1) IfExp ternary-guard resolution (was hiding GD-001's OWN site live_engine_hook:362 — now correctly NC_BODY_OVER_TOTALW); (2) literal/ternary-transport roles (7 UNKNOWNs → 0); (3) SAME-CANDLE guard via price-token base identity (killed cross-candle false-positives: crt_gaussian_scorer:190 DIV(BODY,BODY), crt_engine_v2:1380 _retrace, s09:250 dup); (4) SINGLE-PASS scope resolution (v1 walked module+function scopes twice → duplicate DERIVATION_IDs for one site — root-caused and removed); (5) SUB-EXPRESSION discovery (strong-token only; caught TR/ATR kernels: crt_engine_v2:1010 tr, 5×H-SECONDLOW, p3b/purge_delay/gaussian_rr_scatter tr) with a governed-sink-only rule for UNKNOWN_FORM (first attempt exploded 13k noise-derivations repo-wide — caught by negative controls, fixed). Universe v2: += H-SECONDLOW-002_Complete_Package (19 SOLE-COPY research files, NOT duplicates) + root-level *.py (2 broken-syntax scratch, skip cleanly) → unscanned-other = 0. CENSUS v2 FROZEN: 398 occurrences / 115 derivations (112 producers, 3 test-oracles) / 85 transport / 198 consumers / 0 UNKNOWN; ids unique + line-movement stable. Adversarial floor: 36/36 (19 positive incl. IfExp/GD-001-guard/subexpression fixtures; 9 negatives incl. cross-candle + literal-fixture + guarded-dict-read; 100% synthetic recall, 0 false positives). Delta v1→v2: +37 sites added / -5 false-pos removed. Registry executors (composition_registry:34, derived_registry:33) = config-driven derivations flagged for explicit Gate-2B admission. STOPPED before Gate 2B per directive; pre-classified table = HYPOTHESIS INPUT ONLY (evidence-first protocol acknowledged).
Belief Update / ROI / Goal: Goal: a census that cannot silently miss geometry derivations. Belief: adversarial fixtures + negative controls are what actually validate a static-analysis instrument — they caught a 13,000-row noise explosion AND a same-candle semantic bug within minutes; and the v1 census (which looked complete) was missing GD-001's own site behind a ternary. Knowledge ROI: high. Action: request Gate-2B approval with the frozen v2 artifact.
Open Questions: Gate 2B evidence-first adjudication of the 115 derivations (approval pending); registry-executor admission evidence (parity floor citation); H-SECONDLOW package research-only classification.
Next Step: (user-gated) Gate 2B per the evidence-first protocol: independent per-derivation extraction → provisional classification → hypothesis comparison (CONFIRMED/CONTRADICTED/PARTIAL/UNKNOWN) → 2G contradiction report.
---
📝 SESSION LOG ENTRY
Date: 2026-07-08
Topic: F-049 Gate 2B-P0 calibration batch COMPLETE (20 sites, evidence-first) — STOP before repository-wide 2B
Decision/Output: Adjudicated 20 representative sites from the frozen Census-v2 static detection surface (docs/governance/geometry_semantic_adjudication_p0.jsonl) under the evidence-first protocol (fresh source extraction → provisional verdict → THEN hypothesis comparison). Hypothesis: 12 CONFIRMED / 5 PARTIAL / 3 UNKNOWN / 0 CONTRADICTED. Classes: 3 CANONICAL (incl. 2 manually-admitted config-driven registry executors w/ parity-floor citations) / 2 NON_EQUIVALENT_SAME_QUANTITY (GD-001/002) / 6 NAME_COLLISION_DISTINCT / 4 MATH_EQUIVALENT / 2 SUBEXPRESSION(TR) / 2 TRANSPORT / 1 TEST_ORACLE. 10 semantic families discovered. CALIBRATION CATCHES: (CS-1) crt_gaussian_scorer:190-192 emits cross-candle retrace AS "retest_depth" — a SECOND retest_depth definition != FM-021 (new name-collision, missed by all prior audits); (CS-2) s09 zero-range policy = return-None SKIP (a THIRD policy: 0.0 / 0.001-floor / None-skip) → formula match ≠ family (policy is a grouping dimension — proven necessary); (MD-1) census env-alias propagation over-claims transports as derivations (live_engine_hook auxiliary dict alias of :362); (MD-2) unlisted coercion helpers (_to_float) at governed sinks → false derivation role (collector:112); (MD-3) derived_registry executor has no local math → needs executor_dispatch role. Table-3 floor sites: doc-cited DOMAIN_POLICY (handover spec), floored F7/F8-like archetype ratios, diagnostic-only. RECOMMENDED GRANULARITY: HYBRID — SEMANTIC_FAMILY level for classification/math (est. ~30-40 families over 115 sites), DERIVATION_SITE level for reachability + zero-range policy (CS-2 proves policy can split formula-equal groups). Schema changes required before scaling: semantic_family_id, family_relation(A-F), alias_of_derivation, zero_range_policy enum, executor_dispatch role, coercion-helper allowlist, hypothesis_comparison. STOPPED per directive; no remediation/formula/lint/retrain/Matrix-freeze; language corrected ("frozen Census-v2 static detection surface under the declared methodology").
Belief Update / ROI / Goal: Goal: validate the adjudication method before scaling to 115 sites. Belief: the method WORKS but the census roles need 3 fixes first (MD-1..3), and family grouping MUST include zero-range policy + candle-identity (not just formula) — P0 caught a brand-new production-relevant name collision (retest_depth) that formula-level auditing missed for 40+ findings. Knowledge ROI: high — calibration prevented scaling a subtly wrong method. Action: request approval to scale 2B with the schema changes.
Open Questions: CS-1 retest_depth collision — does the scorer's cross-candle retrace ever co-mingle with FM-021 retest_depth in training data (Gate-5 lineage question)? Apply MD-1..3 census fixes as census v3 before full 2B, or annotate in adjudication only?
Next Step: (user-gated) scale Gate 2B to remaining ~95 Census-v2 derivations under the hybrid granularity + fixed schema; then 2G full contradiction pass; then 2H closure.
---
