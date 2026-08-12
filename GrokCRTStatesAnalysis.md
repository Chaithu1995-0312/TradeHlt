Topic track (your words → later alignment)

Seeded in DOC_TRACKING_INDEX.xlsx → User_Topic_Track (T01–T08). Random now, align later.

┌─────┬───────────────────────────────────────────────────────┬─────────────────┐
│ ID  │ Topic                                                 │ Status          │
├─────┼───────────────────────────────────────────────────────┼─────────────────┤
│ T01 │ Link all layers                                       │ ACTIVE          │
├─────┼───────────────────────────────────────────────────────┼─────────────────┤
│ T02 │ Intent + flow problems                                │ ACTIVE          │
├─────┼───────────────────────────────────────────────────────┼─────────────────┤
│ T03 │ ZONE-X statistical edge                               │ HALTED path (a) │
├─────┼───────────────────────────────────────────────────────┼─────────────────┤
│ T04 │ MT5 live + paper trades                               │ ACTIVE (note)   │
├─────┼───────────────────────────────────────────────────────┼─────────────────┤
│ T05 │ Semantic charts vs broker charts                      │ OPEN_DESIGN     │
├─────┼───────────────────────────────────────────────────────┼─────────────────┤
│ T06 │ Goal via this INFRA                                   │ ACTIVE          │
├─────┼───────────────────────────────────────────────────────┼─────────────────┤
│ T07 │ CRT states from features + ZONE-X + config/thresholds │ ACTIVE          │
├─────┼───────────────────────────────────────────────────────┼─────────────────┤
│ T08 │ Semantic topic links                                  │ ACTIVE          │
└─────┴───────────────────────────────────────────────────────┴─────────────────┘

───

1. Layer stack in the codebase (linked)

GOAL (G001 / goal.md)  ·  ACTIVE_VERSION = v2_multi_2026_04
        │
        ▼
[OHLC]  MT5 terminal / CSV
        mt5_candle_fetcher.py · data/mt5/XAUUSD_M15.csv
        │
        ▼
[MATH ONTOLOGY]  WHAT is measured (FM-*)
        configs/formulas/market_ontology.yaml
        src/features/registry/ · candle_math · derived_math
        │
        ▼
[FEATURE PIPELINE]  39-dim vector
        feature_pipeline.py · feature_schema.py
        │
        ├──────────────────────────────┐
        ▼                              ▼
[CRT STATE MACHINE]              [ENGINE SCORES]
  crt_engine_v2.process_candle     EngineRunner
  VALID_TRANSITIONS (9 states)     CRT score · Gaussian · ZoneGate · RR
  CRTConfig thresholds             │
        │                          ▼
        │                    [FUSION → DECISION]
        │                      FusionEngine · DecisionEngine
        │                          │
        │                          ▼
        │                    [EXECUTION PLAN · RISK]
        │                      ExecutionPlanner · UltronRiskGate
        │                          │
        └──────── semantic ────────┤
                                   ▼
                         order / paper / live (when wired)

PARALLEL / DESCRIPTIVE (not runtime authority):
  market_story_ontology.yaml  →  8 semantic layers · story goldens  →  VA rung S
  ZONE-X (root docs)          →  research geometry + cost  →  OUTSIDE CRT spine
  Measurement Contract        →  economic seal  →  VA rung E (OPEN)
  VA-XAUUSD-M15               →  access doorway S→I→F→E

Intent sources (fetched, not invented):

┌─────────────┬───────────────────────────────────────────────────┬─────────────────────────────────┐
│ Layer       │ Intent                                            │ Authority file                  │
├─────────────┼───────────────────────────────────────────────────┼─────────────────────────────────┤
│ Whole       │ Replay > explainability > telemetry > advisory    │ docs/architecture/goal.md       │
│ system      │ AI; structure ≠ execution safe                    │                                 │
├─────────────┼───────────────────────────────────────────────────┼─────────────────────────────────┤
│ Economic    │ G001 targets in prod config                       │ configs/production/v2_          │
│             │                                                   │ multi_2026_04.json goal         │
├─────────────┼───────────────────────────────────────────────────┼─────────────────────────────────┤
│ CRT         │ “Is structure valid?” — rule SM, no ML            │ active_models.yaml → crt.intent │
├─────────────┼───────────────────────────────────────────────────┼─────────────────────────────────┤
│ Semantic    │ Descriptive validation only; no promote           │ market_story_ontology.yaml      │
│ story       │                                                   │ header                          │
├─────────────┼───────────────────────────────────────────────────┼─────────────────────────────────┤
│ ZONE-X      │ Statistical edge search on gold — path (a) Stop   │ ZONE-X-DECISION-2026-08-06.md   │
├─────────────┼───────────────────────────────────────────────────┼─────────────────────────────────┤
│ VA          │ Access/packaging only                             │ VALIDATION_ACCESS_VA_XAUUSD_M15 │
│             │                                                   │ .md                             │
└─────────────┴───────────────────────────────────────────────────┴─────────────────────────────────┘

Spine map detail: docs/architecture/signal-flow.md.

───

2. Problems on the flow (intent vs reality)

┌─────┬─────────────────────┬───────────────────────────────────────────────────────────────────────┐
│ #   │ Problem             │ Why it hurts your goal                                                │
├─────┼─────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ P1  │ ZONE-X ≠ CRT spine  │ ZONE-X is a separate research programme; path (a) Stop = no more      │
│     │                     │ feature/geometry hunt on gold M15. Cannot drive CRT states from ZONE  │
│     │                     │ -X g(W) without a new decision.                                       │
├─────┼─────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ P2  │ Two “CRT” numbers   │ State machine (CRTState) ≠ fusion crt score (weighted rule over       │
│     │                     │ features). Confusing them breaks charts and LLM explanations.         │
├─────┼─────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ P3  │ CRTConfig split-    │ Programmatic BacktestRunner can miss production JSON thresholds;      │
│     │ brain (F-057)       │ live/CLI path differs. Chart/replay must pin one resolution path.     │
├─────┼─────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ P4  │ Research spine      │ Fusion gate historically OFF in backtest env — “validated” research ≠ │
│     │ often CRT-only (F-  │ full 4-engine live path.                                              │
│     │ 037)                │                                                                       │
├─────┼─────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ P5  │ Gaussian DEGRADED ( │ Live channel near-constant; fusion may look healthy while Gaussian    │
│     │ F-060)              │ adds little.                                                          │
├─────┼─────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ P6  │ Broker clock (F-    │ MT5 session/hour can mislabel ~half of XAU bars if treated as UTC;    │
│     │ 066)                │ chart session tags wrong vs true UTC.                                 │
├─────┼─────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ P7  │ No first-class      │ Semantic layer = states/stories/features, not a broker-matching chart │
│     │ chart product       │ renderer yet (T05 gap).                                               │
├─────┼─────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ P8  │ Paper trade path is │ MT5 demo used for O-1 cost fills; not a clean “paper every CRT        │
│     │ partial             │ EXECUTION” product surface. Noted: demo terminal can place paper      │
│     │                     │ trades.                                                               │
├─────┼─────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ P9  │ E OPEN              │ VA S/I/F green ≠ sealed statistical edge. Measurement contracts still │
│     │                     │ DRAFT.                                                                │
├─────┼─────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ P10 │ Semantic cert vs    │ Feature code surface CLOSED (VA F); RR/Zone still PIT_UNCLEAN for     │
│     │ surface             │ economic reuse.                                                       │
└─────┴─────────────────────┴───────────────────────────────────────────────────────────────────────┘

───

3. How CRT states are formed (features + config — not ZONE-X)

Intent
CRT answers: is institutional structure present right now?
Deterministic SM on OHLCV (+ derived fields). Thresholds = config, not hard-coded magic in intent.

Legal graph (state_identity.py · VALID_TRANSITIONS)

RANGE ─┬─► SWEEP ─► DISPLACEMENT ─► EXPANSION ─┬─► RETEST ─► EXECUTION ─► RESOLUTION ─► RANGE
       │         ╲              ╱              ├─► EXPIRED ─► RANGE
       └─► SHADOW_PENDING ─► SWEEP            └─► RANGE (reset paths)

What feeds transitions (concrete)

┌───────────────┬──────────────────────────────┬────────────────────────────────────────────────────┐
│ Transition    │ What is looked at (OHLC +    │ Config / formula side                              │
│               │ features)                    │                                                    │
├───────────────┼──────────────────────────────┼────────────────────────────────────────────────────┤
│ → SWEEP       │ Wick beyond range, sweep     │ atr_*, body_ratio_min, sweep age; candle math      │
│               │ geometry                     │ body_ratio/wick (FM)                               │
├───────────────┼──────────────────────────────┼────────────────────────────────────────────────────┤
│ →             │ Impulse body/range after     │ atr_min_displacement, body_ratio_min, atr_         │
│ DISPLACEMENT  │ sweep                        │ multiplier_min                                     │
├───────────────┼──────────────────────────────┼────────────────────────────────────────────────────┤
│ → EXPANSION   │ Close extends beyond         │ expansion_atr_min_distance (sensitive — F-057)     │
│               │ displacement                 │                                                    │
├───────────────┼──────────────────────────────┼────────────────────────────────────────────────────┤
│ → RETEST      │ Pullback depth into zone     │ retest_depth_max, retest_atr_depth_fraction        │
├───────────────┼──────────────────────────────┼────────────────────────────────────────────────────┤
│ → EXECUTION   │ Soft confirmation / entry    │ soft-conf EMA spans ema_fast/ema_slow (CRT-local,  │
│               │ window                       │ ≠ pipeline 9/21)                                   │
├───────────────┼──────────────────────────────┼────────────────────────────────────────────────────┤
│ → EXPIRED     │ Expansion TTL                │ max_expansion_age_*                                │
├───────────────┼──────────────────────────────┼────────────────────────────────────────────────────┤
│ Session gate  │ Time window                  │ session_windows (broker-time tuned — F-066         │
│               │                              │ caution)                                           │
└───────────────┴──────────────────────────────┴────────────────────────────────────────────────────┘

Executable SM: src/config_layer/crt_engine_v2.py · process_candle.
WHO contracts (which FM/config per state): active_models.yaml → state_contracts.
Declarative CRT vocabulary: configs/formulas/market_crt_states.yaml.
Feature identities: market_ontology.yaml (FM-010 body_ratio, FM-028 disp ATR ratio, etc.).

ZONE-X role (important)

┌─────────────────────┬─────────────────────────────┬───────────────────────────────────────────────┐
│                     │ CRT                         │ ZONE-X                                        │
├─────────────────────┼─────────────────────────────┼───────────────────────────────────────────────┤
│ Purpose             │ Runtime structure SM on     │ Research statistical-edge / cost protocol     │
│                     │ spine                       │                                               │
├─────────────────────┼─────────────────────────────┼───────────────────────────────────────────────┤
│ Status              │ Active on patch             │ Path (a) Stop — feature search halted         │
├─────────────────────┼─────────────────────────────┼───────────────────────────────────────────────┤
│ Forms CRT states?   │ Yes                         │ No — outside spine                            │
├─────────────────────┼─────────────────────────────┼───────────────────────────────────────────────┤
│ Use with features   │ Config thresholds + FM      │ Dual-c sensitivity if other gold economics    │
│ now                 │                             │ appear                                        │
└─────────────────────┴─────────────────────────────┴───────────────────────────────────────────────┘

You form CRT states from candles + CRTConfig + ontology formulas.
ZONE-X design informs cost/edge research discipline, not the SM transition table.

Semantic layer help for CRT (links)

┌───────────────────────────────────────────┬───────────────────────────────────────────────────────┐
│ Artifact                                  │ Helps how                                             │
├───────────────────────────────────────────┼───────────────────────────────────────────────────────┤
│ market_story_ontology.yaml structure      │ Only layer with crt_state_map → visual/story labels   │
│ layer                                     │ on CRT path                                           │
├───────────────────────────────────────────┼───────────────────────────────────────────────────────┤
│ Other 7 semantic layers                   │ Trend/liq/vol/… descriptive; crt_state_map: null      │
├───────────────────────────────────────────┼───────────────────────────────────────────────────────┤
│ src/research/synthetic/ + VA S            │ Golden six-layer binding tests                        │
├───────────────────────────────────────────┼───────────────────────────────────────────────────────┤
│ docs/topics/crt-spine.md                  │ Human topic index                                     │
├───────────────────────────────────────────┼───────────────────────────────────────────────────────┤
│ docs/topics/model-intent-and-feature-     │ Who owns which features                               │
│ ownership.md                              │                                                       │
├───────────────────────────────────────────┼───────────────────────────────────────────────────────┤
│ VA I/F                                    │ Impl honesty + feature surface closed                 │
└───────────────────────────────────────────┴───────────────────────────────────────────────────────┘

───

4. Your infra goal (aligned in plain words)

MT5 live (paper on demo) → same broker prices/clock
Semantic layer → own charts of OHLC + states/stories
Compare to MT5 charts
CRT from features + config thresholds
ZONE-X docs as edge-research memory (halted hunt, live cost samples OK)
VA ladder as truth access
Toward G001 under governance

What exists vs missing

┌─────────────────────┬────────────────────────────────┬────────────────────────────────────────────┐
│ Need                │ Exists                         │ Gap                                        │
├─────────────────────┼────────────────────────────────┼────────────────────────────────────────────┤
│ OHLC from MT5       │ mt5_candle_fetcher             │ Continuous live loop productization        │
├─────────────────────┼────────────────────────────────┼────────────────────────────────────────────┤
│ Paper trades on     │ O-1 / trade_generator pattern  │ Explicit paper-on-CRT-EXECUTION path       │
│ demo                │ noted                          │                                            │
├─────────────────────┼────────────────────────────────┼────────────────────────────────────────────┤
│ CRT states          │ Full SM + config               │ Single config resolution for all runners   │
├─────────────────────┼────────────────────────────────┼────────────────────────────────────────────┤
│ Semantic meaning    │ Story ontology + goldens       │ Chart renderer (canvas of bars + state     │
│                     │                                │ overlays)                                  │
├─────────────────────┼────────────────────────────────┼────────────────────────────────────────────┤
│ Broker chart        │ Same symbol feed               │ Side-by-side / export overlay tool         │
│ compare             │                                │                                            │
├─────────────────────┼────────────────────────────────┼────────────────────────────────────────────┤
│ Statistical edge    │ ZONE-X cost measured           │ Path (a) no search; MC E OPEN              │
│ seal                │                                │                                            │
├─────────────────────┼────────────────────────────────┼────────────────────────────────────────────┤
│ Validation access   │ VA S→I→F→E                     │ Already run green/access                   │
└─────────────────────┴────────────────────────────────┴────────────────────────────────────────────┘

───

5. Intent I will not invent — need your pick

To move code without thrashing:

1. First infra slice
   (A) OHLC + CRT state chart (own renderer)
   (B) Paper trade on demo when CRT → EXECUTION
   (C) Side-by-side export vs MT5 screenshot protocol only
   (D) Design doc that freezes A+B+C without coding

2. Chart semantic content (for A)
   Bars only · bars + CRTState color · bars + full 8-layer story tags · bars + FM selected (which?)

3. ZONE-X
   Confirm: treat as reference + cost infra only (no geometry reopen) until you write a superseding decision — (yes/no)

───

Short answers to your core questions

┌─────────────────────────────────────┬─────────────────────────────────────────────────────────────┐
│ Question                            │ Answer                                                      │
├─────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Link all layers?                    │ Stack above; spine = signal-flow; descriptive = story       │
│                                     │ ontology + VA                                               │
├─────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ ZONE-X for statistical edge?        │ Designed yes; currently stopped (path a); use dual-c if     │
│                                     │ economics appear elsewhere                                  │
├─────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ MT5 live paper?                     │ Noted — demo terminal can trade; not fully productized on   │
│                                     │ spine                                                       │
├─────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Charts from semantic layer?         │ Intent yes, product no — next major infra for T05           │
├─────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ CRT states from features + ZONE-X + │ From features + CRTConfig + SM; not from ZONE-X geometry    │
│ thresholds?                         │                                                             │
├─────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Semantic topics help?               │ Yes — structure layer maps CRT; goldens validate; topics    │
│                                     │ docs index                                                  │
└─────────────────────────────────────┴─────────────────────────────────────────────────────────────┘

Topic sheet will keep absorbing random mentions; we align when you prioritize.

───
📝 SESSION LOG ENTRY
Date: 2026-08-06
Topic: Layer/intent/flow discussion + user topic track T01–T08
Decision/Output: Full stack map; flow problems P1–P10; CRT vs ZONE-X clarified; MT5 paper noted; chart gap OPEN_DESIGN; User_Topic_Track seeded. No build.
Belief Update / ROI / Goal: Goal=G001 via broker-parity infra. Belief=CRT=config SM; ZONE-X halted; charting is main product gap. Knowledge ROI=high. Action=await priority A/B/C/D.
Open Questions: chart first vs paper first; semantic chart payload; ZONE-X stay halted.
Next Step: user picks first infra slice.Locked

┌───┬────────────────────────────────────────────────────┬─────────────────────────────────────┐
│ # │ Your choice                                        │ Frozen as                           │
├───┼────────────────────────────────────────────────────┼─────────────────────────────────────┤
│ 1 │ D — design only                                    │ A + B + C designed, no code         │
├───┼────────────────────────────────────────────────────┼─────────────────────────────────────┤
│ 2 │ Bars + CRTState color + 8-layer tags + FM selected │ Full chart payload in design        │
├───┼────────────────────────────────────────────────────┼─────────────────────────────────────┤
│ 3 │ ZONE-X as ref                                      │ Reference only — no geometry reopen │
└───┴────────────────────────────────────────────────────┴─────────────────────────────────────┘

Doc: docs/governance/INFRA_CHART_PAPER_COMPARE_V1.md (INFRA-CPC-V1)

───

What’s frozen inside

A — Own charts
• V0 OHLC bars (MT5-pinned series)
• V1 CRTState colors + transition ticks
• V2 All 8 story layers as tags (structure ↔ CRT; others descriptive; no invent in LIVE_PARTIAL)
• V3 Selected FMs — default set below

B — Paper
• MT5 demo only, on CRT EXECUTION
• Planner/risk sizing; fail-closed if not demo
• Log JSONL + ticket id

C — Broker compare
• Same symbol/TF/account · export pack · human checklist · no edge claim from match

ZONE-X
• Spec/decision/cost docs = reference
• Does not form CRT states or chart authority

───

FM selected — FM_CHART_CORE_V1 (recommended default)

┌────────────────────────────────────────┬───────────────────────────────────────────────────────┐
│ On chart                               │ Why                                                   │
├────────────────────────────────────────┼───────────────────────────────────────────────────────┤
│ FM-010 body_ratio                      │ Core CRT gates                                        │
├────────────────────────────────────────┼───────────────────────────────────────────────────────┤
│ FM-002 / candle_range                  │ Sweep / range geometry                                │
├────────────────────────────────────────┼───────────────────────────────────────────────────────┤
│ FM-028 disp ATR ratio                  │ Expansion / strength                                  │
├────────────────────────────────────────┼───────────────────────────────────────────────────────┤
│ FM-027 displacement_retrace            │ Retest path (not confused with pipeline retest_depth) │
├────────────────────────────────────────┼───────────────────────────────────────────────────────┤
│ retest_depth (FM-021)                  │ Shown separately labeled                              │
├────────────────────────────────────────┼───────────────────────────────────────────────────────┤
│ atr                                    │ Threshold scale                                       │
├────────────────────────────────────────┼───────────────────────────────────────────────────────┤
│ disp_strength                          │ Story + displacement narrative                        │
├────────────────────────────────────────┼───────────────────────────────────────────────────────┤
│ sweep_detected / liquidity_sweep       │ Event markers                                         │
├────────────────────────────────────────┼───────────────────────────────────────────────────────┤
│ ema_fast / ema_slow (CRT config spans) │ Soft-conf context                                     │
├────────────────────────────────────────┼───────────────────────────────────────────────────────┤
│ session / hour_of_day                  │ Chips; clock basis labeled (F-066)                    │
├────────────────────────────────────────┼───────────────────────────────────────────────────────┤
│ volatility_ratio / volatility_regime   │ Vol story                                             │
└────────────────────────────────────────┴───────────────────────────────────────────────────────┘

Off by default: saturated momentum_score / ema_spread (F-060/F-064), full 39-dim, RR/Zone ribbons, ZONE-X features.

Expand later via FM_CHART_EXTENDED if you want more.

───

Build order (when you authorize)

A0 (bars + CRT color) → A1 (8-layer tags) → A2 (FM panel) → C0 (compare pack) → B0 (paper on EXECUTION)

───

Your one-liner next

• build A0 — start implementation
• amend FM — change core feature set first
• hold — leave design frozen

Topic track updated (T03 REFERENCE_ONLY · T04/T05 DESIGNED_NOT_BUILT).

───
📝 SESSION LOG ENTRY
Date: 2026-08-06
Topic: INFRA-CPC-V1 design freeze (D)
Decision/Output: Design doc written; FM_CHART_CORE_V1 frozen; ZONE-X ref; no code.
Belief Update / ROI / Goal: Goal=broker-parity infra. Belief=ready for A0. Knowledge ROI=high. Action=await authorize.
Open Questions: optional FM_EXTENDED.
Next Step: user build A0 / amend FM / hold.

Amended

File: docs/governance/INFRA_CHART_PAPER_COMPARE_V1.md
Header: Amended 2026-08-06 — Layer V3 FM labels

What changed

FM_CHART_CORE_V1 table now has:
• FM id · vector name · idx · config knobs · formation one-liner · why · pane

┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Included with full FM labels                                                                      │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ FM-010 body_ratio · FM-002 candle_range · FM-041 atr · FM-020 disp_strength · FM-028 / FM-027 (   │
│ distinct) · FM-021 retest_depth · FM-058/059 sweeps · FM-043/044 pipeline EMAs (9/21) · FM-051    │
│ /052 hour/session · FM-024/050 vol                                                                │
└───────────────────────────────────────────────────────────────────────────────────────────────────┘

New dual-EMA section:
• crt_live_ema_fast/slow → no FM, not in vector, CRTConfig 2/5
• Must not reuse FM-043/044 labels
• Optional via FM_CHART_CRT_EMA mode

Legend ACs: A-AC3 (FM id + name) · A-AC3b (no EMA conflation)

EXTENDED corrected: FM-057, FM-060, FM-049, FM-053, FM-042

No code. Still design-frozen until you authorize build.

───
📝 SESSION LOG ENTRY
Date: 2026-08-06
Topic: Amend INFRA-CPC-V1 FM labels
Decision/Output: Layer V3 rewritten with FM id/idx/config/formation; dual-EMA trap; A-AC3/3b.
Belief Update / ROI / Goal: Goal=chart labels match ontology. Belief=ambiguity closed. Knowledge ROI=high. Action=hold until build authorize.
Open Questions: none.
Next Step: hold or build A0.
---Short answer

Yes — CRT states are knowable, ordered, and already defined in this codebase.
No — they are not discovered from “trained data” as learned classes.
They are rule-formed by the CRT state machine. Infra (charts + FMs) shows and checks them; it does not invent them from model training.

───

What forms CRT states

┌────────────────┬────────────────────────────────────────────────────────────────────────┐
│                │                                                                        │
├────────────────┼────────────────────────────────────────────────────────────────────────┤
│ Engine         │ crt_engine_v2.process_candle                                           │
├────────────────┼────────────────────────────────────────────────────────────────────────┤
│ Inputs         │ OHLCV stream + CRTConfig thresholds + some feature / structure signals │
├────────────────┼────────────────────────────────────────────────────────────────────────┤
│ Outputs        │ CRTState enum (9 values) + transitions                                 │
├────────────────┼────────────────────────────────────────────────────────────────────────┤
│ Legal sequence │ VALID_TRANSITIONS in state_identity.py (frozen graph)                  │
├────────────────┼────────────────────────────────────────────────────────────────────────┤
│ Not            │ RR / Gaussian / BitNet / ZoneGate / story tags “predicting” the state  │
└────────────────┴────────────────────────────────────────────────────────────────────────┘

So: sequence and meaning are design + code authority, not a supervised label set from a trained classifier.

───

Individual meaning of each state (intent)

From CRT intent (active_models.yaml + SM): “Is institutional structure valid?” — liquidity → impulse → pullback → entry.

┌───────────────┬─────────────────────────────────────────┬─────────────────────────────────────────┐
│ State         │ Meaning (plain)                         │ Rough “what just happened”              │
├───────────────┼─────────────────────────────────────────┼─────────────────────────────────────────┤
│ RANGE         │ Structure idle / building               │ Range context; waiting for sweep or     │
│               │                                         │ shadow                                  │
├───────────────┼─────────────────────────────────────────┼─────────────────────────────────────────┤
│ SHADOW_       │ Displacement memory without full sweep  │ HTF/reset path; waiting for sweep       │
│ PENDING       │ confirm                                 │                                         │
├───────────────┼─────────────────────────────────────────┼─────────────────────────────────────────┤
│ SWEEP         │ Liquidity taken beyond a level,         │ Stop-run style event vs range/refs      │
│               │ structure event                         │                                         │
├───────────────┼─────────────────────────────────────────┼─────────────────────────────────────────┤
│ DISPLACEMENT  │ Impulsive move away after sweep         │ Strong body/move vs ATR/config gates    │
├───────────────┼─────────────────────────────────────────┼─────────────────────────────────────────┤
│ EXPANSION     │ Move continues / structure extends      │ Close extends past displacement by ATR  │
│               │                                         │ distance                                │
├───────────────┼─────────────────────────────────────────┼─────────────────────────────────────────┤
│ RETEST        │ Price returns toward the zone           │ Pullback depth within configured band   │
├───────────────┼─────────────────────────────────────────┼─────────────────────────────────────────┤
│ EXECUTION     │ Soft-conf / entry window accepted       │ Tradeable structural approval (spine)   │
├───────────────┼─────────────────────────────────────────┼─────────────────────────────────────────┤
│ RESOLUTION    │ Setup closed out                        │ Cycle end → back toward RANGE           │
├───────────────┼─────────────────────────────────────────┼─────────────────────────────────────────┤
│ EXPIRED       │ Expansion timed out                     │ TTL archive → RANGE                     │
└───────────────┴─────────────────────────────────────────┴─────────────────────────────────────────┘

That is semantic meaning in the design, not “mean of a neural embedding for state k.”

───

Sequence they form (legal graph)

Golden path (most common story):

RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION → RESOLUTION → RANGE

Also legal branches:

RANGE ↔ SHADOW_PENDING → SWEEP → …
EXPANSION → EXPIRED → RANGE
Many states → RANGE  (reset / fail paths)
SWEEP → EXPANSION     (skip paths exist in the graph)

Full authority: VALID_TRANSITIONS — not free-form, not trained.

Infra charts (V1 color) are meant to paint this sequence bar-by-bar once the SM has run — same order the code already enforces.

───

“Trained data” — what you do / don’t have

┌───────────────────────────────────────┬───────────────────────────────────────────────────────────┐
│ Asset                                 │ Relation to CRT states                                    │
├───────────────────────────────────────┼───────────────────────────────────────────────────────────┤
│ Historical OHLCV (MT5 / CSV)          │ Replay SM → empirical state sequences on real bars        │
├───────────────────────────────────────┼───────────────────────────────────────────────────────────┤
│ Story goldens (synthetic library)     │ Scripted paths that must bind to CRT structure layer      │
├───────────────────────────────────────┼───────────────────────────────────────────────────────────┤
│ VA S / I / F                          │ Checks stories, models, features — not “state classifier  │
│                                       │ training”                                                 │
├───────────────────────────────────────┼───────────────────────────────────────────────────────────┤
│ RR / Gaussian / BitNet / ZoneGate     │ Scores / gates around structure; do not define CRTState   │
│ artifacts                             │                                                           │
├───────────────────────────────────────┼───────────────────────────────────────────────────────────┤
│ ZONE-X                                │ Reference research; outside CRT SM                        │
└───────────────────────────────────────┴───────────────────────────────────────────────────────────┘

So you can answer, with data you already have:

1. Meaning — from design (docs + ontology + active_models)
2. Legal sequence — from VALID_TRANSITIONS
3. Observed sequence on XAUUSD M15 — run SM on corpus → counts, dwell, path frequencies

You cannot honestly say: “the trained model learned that SWEEP means X.”
You can say: “on this corpus, SWEEP→DISPLACEMENT happened N times under config pin C.”

───

What this INFRA gives you (when built)

┌───────────────────────┬───────────────────────────────────────────────────────────────┐
│ Infra piece           │ Role for CRT states                                           │
├───────────────────────┼───────────────────────────────────────────────────────────────┤
│ Bars + CRTState color │ See which state on which bar                                  │
├───────────────────────┼───────────────────────────────────────────────────────────────┤
│ Transition ticks      │ See when sequence advances                                    │
├───────────────────────┼───────────────────────────────────────────────────────────────┤
│ FM overlays           │ See why a gate might pass/fail (body_ratio, sweeps, ATR, …)   │
├───────────────────────┼───────────────────────────────────────────────────────────────┤
│ 8-layer story tags    │ Human/LLM story beside structure (only structure maps to CRT) │
├───────────────────────┼───────────────────────────────────────────────────────────────┤
│ Paper on EXECUTION    │ Act only when SM reaches that state                           │
├───────────────────────┼───────────────────────────────────────────────────────────────┤
│ Broker compare        │ Same prices; your state overlay is internal truth             │
└───────────────────────┴───────────────────────────────────────────────────────────────┘

Infra = visibility + paper path on top of an SM that already finds states.

───

Direct answers to your wording

┌──────────────────────────────────┬────────────────────────────────────────────────────────────────┐
│ Question                         │ Answer                                                         │
├──────────────────────────────────┼────────────────────────────────────────────────────────────────┤
│ With this infra, can’t you find  │ SM already finds them. Infra will display them on the same     │
│ CRT states?                      │ OHLC as the broker.                                            │
├──────────────────────────────────┼────────────────────────────────────────────────────────────────┤
│ With trained data, individual    │ Meaning is designed, not trained. Data gives frequency /       │
│ meaning of states?               │ context, not a new dictionary of meaning.                      │
├──────────────────────────────────┼────────────────────────────────────────────────────────────────┤
│ Sequence they form?              │ Yes — fixed legal sequence in code; data shows which legal     │
│                                  │ paths dominate on XAUUSD.                                      │
└──────────────────────────────────┴────────────────────────────────────────────────────────────────┘

───

One precision (important)

Pipeline sweep_detected / liquidity_sweep (FM-058/059) ≠ always CRTState.SWEEP.
CRT SWEEP is the state machine’s transition; features are inputs / relatives. Chart should keep V1 = CRTState and markers = FM-058/059 so you don’t merge two truths.

───

Bottom line: You already have state meanings and sequences as first-class CRT design. Trained model artifacts don’t own them. Historical candles + SM give empirical trajectories. INFRA is how you see and act on that — not how states are invented.

If you want next (still discussion or a small probe): a read-only state census on XAUUSD_M15 (counts per state + top transition paths under ACTIVE_VERSION) — no chart build. Say if you want that.

───
📝 SESSION LOG ENTRY
Date: 2026-08-06
Topic: CRT states vs INFRA vs trained data — clarification
Decision/Output: CRT states = rule SM + VALID_TRANSITIONS + designed meanings; not ML labels. Infra visualizes; trained engines don’t define states. Pipeline sweep FMs ≠ CRT SWEEP identity.
Belief Update / ROI / Goal: Goal=correct mental model for charts/paper. Belief=user can rely on designed state semantics + corpus replay for sequence stats. Knowledge ROI=high. Action=hold build unless user wants state census probe.
Open Questions: optional XAUUSD state-path census.
Next Step: user choice.Rule authority chain

VALID_TRANSITIONS  →  only legal edges
        │
process_candle     →  once per bar: ATR, EMAs, then branch on current_state
        │
try_* / detect_*   →  boolean guards (OHLC + range memory + CRTConfig)
        │
_transition()      →  refuse if edge not in VALID_TRANSITIONS; else set state

File: src/config_layer/crt_engine_v2.py
Legal graph: src/config_layer/state_identity.py VALID_TRANSITIONS
Thresholds: CRTConfig (production merge / crt_engine section)
Not: trained models, pipeline FM-058 alone, ZONE-X

Every transition is: current state + this candle’s OHLC (+ memory) + config comparison.

───

Layer 0 — Legal graph (hard rule)

RANGE          → SWEEP | SHADOW_PENDING
SHADOW_PENDING → SWEEP | RANGE
SWEEP          → DISPLACEMENT | EXPANSION | RANGE
DISPLACEMENT   → EXPANSION | RANGE
EXPANSION      → RETEST | EXPIRED | RANGE
EXPIRED        → RANGE
RETEST         → EXECUTION | RANGE
EXECUTION      → RESOLUTION
RESOLUTION     → RANGE

_transition rejects any other edge (log ILLEGAL …).
No ML can add a state or skip this map.

───

Layer 1 — Every bar setup (process_candle)

Before state branch:

┌─────────┬─────────────────────────────────────────────────────────────────────────────────────────┐
│ Step    │ Rule                                                                                    │
├─────────┼─────────────────────────────────────────────────────────────────────────────────────────┤
│ Index   │ current_candle_index += 1                                                               │
├─────────┼─────────────────────────────────────────────────────────────────────────────────────────┤
│ Buffer  │ keep last atr_period × atr_buffer_multiplier candles                                    │
├─────────┼─────────────────────────────────────────────────────────────────────────────────────────┤
│ ATR     │ atr_abs = SMA(true_range, atr_period) — absolute price, not pipeline FM-041             │
├─────────┼─────────────────────────────────────────────────────────────────────────────────────────┤
│ CRT     │ update_emas(close, ema_fast, ema_slow) — spans from CRTConfig (typ. 2/5), not FM-043    │
│ EMAs    │ /044                                                                                    │
├─────────┼─────────────────────────────────────────────────────────────────────────────────────────┤
│ Reset   │ optional HTF/range reset → force RANGE, then fall through (same bar can still sweep)    │
└─────────┴─────────────────────────────────────────────────────────────────────────────────────────┘

Then: if current_state == … only the matching branch runs.

───

Layer 2 — Detection / transition rules (golden path)

1) RANGE geometry (context, not a transition)

detect_htf_range over window:

h_ref = max(highs),  l_ref = min(lows)

Stored as active_range. Sweep is vs this range, not pipeline swings.

───

2) RANGE → SWEEP
detect_sweep · try_range_to_sweep

┌───────────┬────────────────────────────────┐
│ Side      │ Predicate (all on this candle) │
├───────────┼────────────────────────────────┤
│ Buy-side  │ high > h_ref and close < h_ref │
├───────────┼────────────────────────────────┤
│ Sell-side │ low < l_ref and close > l_ref  │
└───────────┴────────────────────────────────┘

If either true → build SweepEvent → _transition(RANGE → SWEEP).
Direction set from which side swept.

Not the same as pipeline FM-058 (uses prior swing refs, not HTF range).

Alt: if pending shadow memory matches sweep direction → RANGE → SHADOW_PENDING instead.

───

3) SWEEP → DISPLACEMENT
try_sweep_to_displacement — all must pass

┌────┬───────────┬───────────────────────────────────────────┬──────────────────────────────────────┐
│ #  │ Guard     │ Formula                                   │ Config                               │
├────┼───────────┼───────────────────────────────────────────┼──────────────────────────────────────┤
│ G1 │ Body move │ |close−open| ≥ atr_min_displacement ×     │ atr_min_displacement                 │
│    │           │ atr_abs                                   │                                      │
├────┼───────────┼───────────────────────────────────────────┼──────────────────────────────────────┤
│ G2 │ Sweep age │ index − sweep_index ≤ max_sweep_age_      │ max_sweep_age_candles                │
│    │           │ candles                                   │                                      │
├────┼───────────┼───────────────────────────────────────────┼──────────────────────────────────────┤
│ G3 │ Body      │ candle.body_ratio ≥ body_ratio_min        │ body_ratio_min · FM-010 path         │
│    │ ratio     │                                           │                                      │
├────┼───────────┼───────────────────────────────────────────┼──────────────────────────────────────┤
│ G4 │ Range     │ candle.wick_size ≥ atr_multiplier_min ×   │ atr_multiplier_min · wick ≡ range (  │
│    │ size      │ atr_abs                                   │ FM-002)                              │
└────┴───────────┴───────────────────────────────────────────┴──────────────────────────────────────┘

Pass → store displacement_candle → DISPLACEMENT.
Fail G2 can expire sweep → RANGE.

───

4) DISPLACEMENT → EXPANSION
try_displacement_to_expansion

┌────┬──────────────────┬────────────────────────────────────────────────────────┬──────────────────┐
│ #  │ Guard            │ LONG                                                   │ SHORT            │
├────┼──────────────────┼────────────────────────────────────────────────────────┼──────────────────┤
│ D1 │ Directional bar  │ close > open                                           │ close < open     │
├────┼──────────────────┼────────────────────────────────────────────────────────┼──────────────────┤
│ D2 │ Beyond disp      │ close > disp.close                                     │ close < disp.    │
│    │ close            │                                                        │ close            │
├────┼──────────────────┼────────────────────────────────────────────────────────┼──────────────────┤
│ D3 │ ATR extension    │ |close − disp.close| ≥ expansion_atr_min_distance ×    │ same             │
│    │                  │ atr_abs                                                │                  │
└────┴──────────────────┴────────────────────────────────────────────────────────┴──────────────────┘

Config: expansion_atr_min_distance (F-057 sensitive).

───

5) EXPANSION → RETEST
try_expansion_to_retest (priority over TTL same bar)

┌────┬─────────────────────┬──────────────────────────────────────────────┬─────────────────────────┐
│ #  │ Guard               │ Formula                                      │ Config                  │
├────┼─────────────────────┼──────────────────────────────────────────────┼─────────────────────────┤
│ R0 │ Range present       │ active_range ≠ null                          │ —                       │
├────┼─────────────────────┼──────────────────────────────────────────────┼─────────────────────────┤
│ R1 │ Min depth           │ depth_abs ≥ retest_min_depth_atr_fraction ×  │ floor                   │
│    │                     │ atr                                          │                         │
├────┼─────────────────────┼──────────────────────────────────────────────┼─────────────────────────┤
│ R2 │ Max depth           │ depth_abs ≤ adaptive_ceiling                 │ ceiling                 │
├────┼─────────────────────┼──────────────────────────────────────────────┼─────────────────────────┤
│ R3 │ Disp not            │ FM-028(disp.wick, atr) ≤ max_displacement    │ max_displacement        │
│    │ overextended        │ _strength                                    │ _strength               │
└────┴─────────────────────┴──────────────────────────────────────────────┴─────────────────────────┘

Depth:

LONG:  depth_abs = close − l_ref
SHORT: depth_abs = h_ref − close

static_ceiling  = retest_depth_max × range.size
atr_ceiling     = retest_atr_depth_fraction × atr
adaptive_ceiling = max(static_ceiling, atr_ceiling)

On pass: cache FM-027 retrace, FM-010 body_ratio, FM-028 disp ATR ratio → RETEST, open soft-conf window.

───

6) EXPANSION → EXPIRED (if retest fails)

age_candles > max_expansion_age_candles
  OR age_hours > max_expansion_age_hours

→ EXPIRED → next bar EXPIRED → RANGE.

───

7) RETEST → EXECUTION (soft-confirmation, not pure geometry)

After retest, evaluating_soft_conf = True. Each bar:

approved, S = risk.approve_with_soft_conf(state, candle)
  uses CRT EMAs (2/5), score components, conf weights, tiers…
optional shadow age: S_eff = S × exp(−λ · age…)
if S_eff < tier_2_threshold → reject

if approved:
  LONG:  entry close must be in discount (≤ mid of range)
  SHORT: entry close must be in premium (≥ mid)
  session / other filters may still reject
→ try_retest_to_execution → EXECUTION

This step is still rule/score gates, not a trained state classifier.

───

8) EXECUTION → RESOLUTION → RANGE

Trade SL/TP/close via executor → try_execution_to_resolution → reset RANGE.

───

Layer 3 — Sequence as a decision tree

                    ┌─ no ── stay RANGE
RANGE ─ detect_sweep ─┤
                    └─ yes ─► SWEEP ──┬─ 4-gate FAIL ─► stay / RANGE
                                      └─ 4-gate PASS ─► DISPLACEMENT
                                              │
                                    extension 3-gate?
                                      ├─ no ─ stay DISPLACEMENT
                                      └─ yes ─► EXPANSION
                                              │
                                    retest depth gates?
                                      ├─ yes ─► RETEST ─ soft_conf ─► EXECUTION ─► RESOLUTION ─► RANGE
                                      └─ no + TTL ─► EXPIRED ─► RANGE

Shadow branch: RANGE → SHADOW_PENDING → … (can resume expansion with weaker displacement re-check).

───

What the rules use vs do not use

┌────────────────────────────────────────┬───────────────────────────────────────┐
│ Used in SM rules                       │ Not used to define CRTState           │
├────────────────────────────────────────┼───────────────────────────────────────┤
│ OHLC of this candle                    │ Trained RR / Gaussian / BitNet labels │
├────────────────────────────────────────┼───────────────────────────────────────┤
│ active_range h_ref/l_ref               │ Pipeline FM-058 as the sweep detector │
├────────────────────────────────────────┼───────────────────────────────────────┤
│ atr_abs (absolute SMA TR)              │ Pipeline FM-041 as the ATR gate value │
├────────────────────────────────────────┼───────────────────────────────────────┤
│ body_ratio (FM-010 identity on candle) │ “Mean of a state embedding”           │
├────────────────────────────────────────┼───────────────────────────────────────┤
│ CRTConfig thresholds                   │ ZONE-X g(W)                           │
├────────────────────────────────────────┼───────────────────────────────────────┤
│ CRT EMA 2/5 for soft-conf only         │ Pipeline EMA 9/21 as soft-conf        │
└────────────────────────────────────────┴───────────────────────────────────────┘

Pipeline FMs can chart/explain the same ideas; the SM often recomputes local equivalents.

───

One-line definition of each state (rule view)

┌────────────────┬────────────────────────────────────────────────────────────────────────┐
│ State          │ Rule meaning                                                           │
├────────────────┼────────────────────────────────────────────────────────────────────────┤
│ RANGE          │ No active setup; range geometry held; watching for range breach-reject │
├────────────────┼────────────────────────────────────────────────────────────────────────┤
│ SWEEP          │ Breach of h_ref/l_ref with close back inside (this bar)                │
├────────────────┼────────────────────────────────────────────────────────────────────────┤
│ DISPLACEMENT   │ Post-sweep impulse passed body/move/wick/age gates                     │
├────────────────┼────────────────────────────────────────────────────────────────────────┤
│ EXPANSION      │ Close extended beyond displacement close by ≥ k·ATR, directional bar   │
├────────────────┼────────────────────────────────────────────────────────────────────────┤
│ RETEST         │ Close retraced into adaptive depth band; not overextended disp         │
├────────────────┼────────────────────────────────────────────────────────────────────────┤
│ EXECUTION      │ Soft-conf + zone filters approved                                      │
├────────────────┼────────────────────────────────────────────────────────────────────────┤
│ RESOLUTION     │ Trade lifecycle finished                                               │
├────────────────┼────────────────────────────────────────────────────────────────────────┤
│ EXPIRED        │ Expansion aged out without retest                                      │
├────────────────┼────────────────────────────────────────────────────────────────────────┤
│ SHADOW_PENDING │ Cross-window displacement memory + confirming sweep path               │
└────────────────┴────────────────────────────────────────────────────────────────────────┘

───

Link back to “infra shows, does not invent”

┌─────────────────────┬─────────────────────────────────────────────────────────────────────────────┐
│ Infra               │ Relation to these rules                                                     │
├─────────────────────┼─────────────────────────────────────────────────────────────────────────────┤
│ Chart CRTState      │ Paint state.current_state after this SM runs                                │
│ color               │                                                                             │
├─────────────────────┼─────────────────────────────────────────────────────────────────────────────┤
│ FM overlays         │ Parallel feature series; only some share math (FM-010, FM-028 at retest     │
│                     │ cache)                                                                      │
├─────────────────────┼─────────────────────────────────────────────────────────────────────────────┤
│ Paper on EXECUTION  │ Fire when this rule path reaches EXECUTION                                  │
└─────────────────────┴─────────────────────────────────────────────────────────────────────────────┘

Bottom line: states are boolean predicates + config thresholds + legal graph, executed bar-by-bar in process_candle. That is the full rule.

───
📝 SESSION LOG ENTRY
Date: 2026-08-06
Topic: CRT state-machine rule trace
Decision/Output: Traced VALID_TRANSITIONS + per-edge guards (sweep geometry, 4-gate disp, expansion ATR distance, adaptive retest + FM-028, TTL, soft-conf→EXECUTION). Absolute atr_abs vs FM-041 noted.
Belief Update / ROI / Goal: Goal=exact rule visibility. Belief=states = deterministic guards, not training. Knowledge ROI=high. Action=none.
Open Questions: none.
Next Step: user.
---