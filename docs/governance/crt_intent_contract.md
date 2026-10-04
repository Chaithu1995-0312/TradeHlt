# CRT Intent Contract — Freeze + Code-Grounded Audit (MIAR steps 1–3)

**Program:** MIAR alignment workflow — CRT (the designated `start_with` model), steps 1–3
(`freeze semantic contract` → `agree intent and non-goals` → `audit implementation`).
**Date (UTC):** 2026-07-28
**Authority:** Intent/documentation only — **no production scoring behaviour changed**. This
artifact ratifies the existing MIAR `crt` contract and audits code against it; it grants CRT no
new authority and removes none (Authority Ladder, CLAUDE.md §6.5).
**Prerequisite (cite, do not reopen/duplicate):** CRT is already **CLOSED** for structure/formula
correctness + empirical parity — [`crt_closure_report.md`](crt_closure_report.md) ("CRT
rediscovery is permanently frozen … Do not re-run Phases 1–8"). The quantity-level contract is
[`crt_formula_contract.md`](crt_formula_contract.md) (Phase 2). This document is a **different
axis** — *model intent* (what CRT is for, its non-goals, its ownership boundary), not formula
correctness.

> **Scope guard.** Steps **4 (fix drift)** and **5 (lock → flip `alignment` to `ALIGNED`)** are
> **out of scope**. The unresolved drift found in §C/§D means `alignment` **stays
> `SEMANTIC_DRIFT` (🟡)** — it cannot be locked to `ALIGNED` until the §D conflict is resolved by
> a step-4 decision. §E is a **written proposal only** — no code is touched.

---

## Verdict

```text
CRT_INTENT_CONTRACT      = FROZEN (steps 1–3 complete)
INTENT_AGREED            = YES (16 MIAR fields + stage-family row + locked vocabulary)
ALIGNMENT                = SEMANTIC_DRIFT (unresolved — unchanged)
PRIMARY_DRIFT            = spine config_layer/crt_engine_v2.py::CRTEngine approves + executes trades
SECONDARY_DRIFT          = dual math paths (FSM RiskScore.final vs engines compute_scores); score != state
CLEAN_SURFACE            = engines/crt_engine.py::compute (score, never probability, never approves)
RECONCILIATIONS_APPLIED  = 3 JSON<->MD wording fixes + 1 added mandatory Stage-1 non-goal (additive, no deletion)
STEPS_4_5                = out of scope (fix drift / lock)
NEXT                     = step 4 — resolve the §D approval-authority conflict (user decision)
```

---

## §A — Frozen contract, line by line

Every clause is ratified **verbatim** from its authority. Sources: `M` =
[`MODEL_INTENT_AUTHORITY_REGISTER.md`](MODEL_INTENT_AUTHORITY_REGISTER.md), `J` =
[`miar_registry.json`](miar_registry.json). Line numbers are at time of freeze.

### A.1 The 16 MIAR `crt` fields + stage-family row

| # | Clause | Frozen text | Source | Agreed |
|---|---|---|---|---|
| 1 | **id** | `crt` | J:117 · M:243 | ✅ |
| 2 | **stage / order** | `market_understanding` · order **1** (first Stage-1 engine; `start_with` of the alignment workflow) | J:152-153 · M:244 | ✅ |
| 3 | **stage-family row** | Family = *Market understanding (Stage 1)*; locked question *"What is the market?"*; **May approve a trade? — Never** | user stage-family law (this session) | ✅ |
| 4 | **intent** | "What structural state is the market in?" | J:118 · M:245 | ✅ |
| 5 | **hypothesis** | "Sweep→displacement→expansion→retest sequences mark actionable structure." | M:246 (canonical, see §B.1) | ✅ |
| 6 | **inputs** | Raw OHLCV (+ internal EMA/ATR); fusion score path also uses structure features | M:247 · J:120-123 | ✅ |
| 7 | **outputs** | FSM state/actions; fusion `structure_rule_score` (separate path) | M:248 · J:124-127 | ✅ |
| 8 | **semantic_meaning** | "Structural classification / structure-rule score — **not** p(win)" | M:249 · J:128 | ✅ |
| 9 | **consumer** | Backtest/live spine `TRADE_OPENED`; fusion slot `crt` (score path); BitNet at approve if enabled | M:250 · J:129-133 | ✅ |
| 10 | **authority_boundary** | "Structure detection and structure-rule scoring; may open structural path to risk" | M:251 (canonical, see §B.3) | ✅ |
| 11 | **explicit_non_goals** | **Never** estimate win probability; **never** own economic RR; **never** classify statistical neighbourhood (ZoneGate); **never decide whether to trade** (added §B.4) | M:252 · J:135-139 (+§B.4) | ✅ |
| 12 | **dependencies** | `feature_pipeline` (score path), `market_ontology` | M:253 (canonical, see §B.2) · J:140-143 | ✅ |
| 13 | **falsification** | "Structure completion adds no path asymmetry (e.g. F-026-class) → purpose as *edge source* weakened; structure *description* may remain" | M:254 · J:144 | ✅ |
| 14 | **implementation_status** | `EXECUTABLE` (dual surfaces: FSM + fusion scorer) | M:255 · J:145 | ✅ |
| 15 | **alignment** | 🟡 `SEMANTIC_DRIFT` — dual math paths (FSM vs `compute_scores` retest); score ≠ state | M:256 · J:146 | ✅ (stays 🟡) |
| 16 | **primary_code** | `config_layer/crt_engine_v2.py` · `engines/crt_engine.py` · `engines/scoring_engine.py` | M:257 · J:147-151 | ✅ |
| 17 | **notes** | "MIAR treats FSM + fusion scorer as one *intent owner* with two outputs; do not invent a second owner." | M:258 | ✅ |

### A.2 Locked vocabulary the CRT contract leans on

Frozen verbatim from `M §0.3` (semantic drift stop-list) / `J locked_vocabulary`. **Never
interchangeable: Probability ≠ Score ≠ Confidence** (M:133).

| Term | Frozen definition | Source |
|---|---|---|
| **Structure** | "Current market organization inferred from OHLCV (CRT owns classification of structural *state*)." | M:120 · J:749 |
| **Score** | "Ordinal / utility value **without** probabilistic interpretation." | M:129 · J:757 |
| **Probability** | "A **calibrated** chance an event occurs. Implies calibration; not an arbitrary score." | M:128 · J:756 |
| **Confidence** | "Reliability of the **model's own output**, not P(trade success)." | M:130 · J:758 |

**Contract reading:** CRT emits a **Score** (ordinal, no probabilistic interpretation). It must
**never** emit a **Probability** (`p_win`) — enforced by non-goal "never estimate win probability."

### A.3 The Stage-1 hard rule that binds CRT

Frozen verbatim, M:46:

> "A Stage-1 model that influences entry *only* via fusion must still declare non-goal **'never
> decide whether to trade.'** Fusion (Stage 4) is the sole owner of trade approval among scoring
> engines; Ultron/planner own economic execution gates **after approval**."

This is why §B.4 adds the missing non-goal, and it is the exact boundary the §D drift violates.

---

## §B — Reconciliations applied (additive; before → after)

The two authorities (`M` prose, `J` machine twin) were not byte-consistent on four points. Fixed
**additively** — no intent removed, no field blanked. Recorded here so nothing is silently changed.

| # | Field | Before | After (canonical) | Rationale |
|---|---|---|---|---|
| B.1 | `hypothesis` | J:119 "Sweep to retest sequences mark actionable structure." | "Sweep→displacement→expansion→retest sequences mark actionable structure." (J ASCII-flattened) | M is the fuller form and matches the **actual golden path** `RANGE→SWEEP→DISPLACEMENT→EXPANSION→RETEST→…` (`state_identity.py:69-79`). J updated to M. |
| B.2 | `dependencies` | M:253 "ontology geometries" | name `market_ontology` explicitly (as J already does, J:140-143) | Align M prose to the structured J id; removes an ambiguous phrase. |
| B.3 | `authority_boundary` | J:134 "Structure detection and structure-rule scoring" | append "; may open structural path to risk" (as M:251) | J was the bare form; M carries the boundary qualifier. J updated to M. |
| B.4 | `explicit_non_goals` | 3 items (win-prob / economic-RR / zone-neighbourhood) | **append** "never decide whether to trade" | **Mandated by the charter's own Stage-1 hard rule (M:46)** and by the stage-family law (Stage 1 "may approve a trade? Never"). CRT's list omitted it. Purely additive. |

> B.4 is semantically loaded: adding this non-goal makes the contract **internally consistent**
> with the charter — and simultaneously makes the §D code-vs-contract drift **formal and
> explicit**. That is the intended outcome of an audit, not a side effect.

`alignment` is **not** touched (stays `SEMANTIC_DRIFT`). `updated` timestamp bumped in J.

---

## §C — Code audit (step 3)

CRT has **two runtime surfaces** (MIAR notes M:258 treat them as one *intent owner* with two
outputs — do not invent a second owner). Audited separately because they behave very differently.

### C.1 Surface 1 — fusion-slot scorer `engines/crt_engine.py::compute` → `scoring_engine.compute_scores`

| Contract clause | Code evidence | Verdict |
|---|---|---|
| Emits a **Score**, not a Probability | `compute` returns `{"score": result["final"]}` (`engines/crt_engine.py:36`); `compute_scores` returns a bounded `[0,1]` weighted blend `sweep/breakout/retest/time` (`scoring_engine.py:40-61`) | **ALIGNED** |
| Never estimates win probability | grep `p_win`/`probability`/`win` on this path → **0 hits** | **ALIGNED** |
| Never approves / never decides whether to trade | no boolean approval, no veto, no `execute`/`reject` emitted; delegates and logs only | **ALIGNED** |
| No silent HOW default (weights) | requires `context["score_component_weights"]`, raises `KeyError` if absent (`crt_engine.py:19-24`); `EngineRunner` injects strictly from prod config | **ALIGNED** — consistent with "no defaults/fallbacks"; the `(0.35,0.25,0.20,0.20)` in `scoring_engine.py:28` is a **direct-construction/test parity** arg, not the production value (F-052) |
| Score consumed only as a fusion vote (cannot gate alone) | fed to `FusionEngine.compute` weighted by `weight_crt`; **`DecisionEngine.evaluate()` is the ONLY place that emits "execute"/"reject"; EngineRunner NEVER returns "Approved"** (`engine_runner.py:1007-1008`) | **ALIGNED** |

**Surface 1 result: fully within the frozen intent.** ✅

### C.2 Surface 2 — spine state machine `config_layer/crt_engine_v2.py::CRTEngine`

This is the **runtime spine** (driven candle-by-candle by `runtime/backtest_v2.py`; declared entry
point `config_layer.crt_engine_v2.CRTEngine.process_candle` in
`research/model_runners/contracts.py`). It contains an **embedded `UltronRiskEngine`** and does far
more than "understand structure."

| Contract clause | Code evidence | Verdict |
|---|---|---|
| Emits a **Score**, not a Probability | `RiskScore.final` is a weighted `sweep/breakout/retest/time × decay` blend (`crt_engine_v2.py:197-208`) — a Score, not a Probability | **ALIGNED** (on the score's semantics) |
| **Never approves a trade** | `UltronRiskEngine.approve(state) -> (bool, RejectReason)` returns `True, None` = **APPROVED** (`crt_engine_v2.py:2016, 2094`); `approve_with_soft_conf(...) -> (approved, reason, final_S)` with geometric fusion `S=G^α·C^β`, tiered APPROVED/REJECTED (`:1930-2012`) | **DRIFT** |
| **Never decides whether to trade** (§B.4 / M:46) | on approval → `try_retest_to_execution` → `build_trade` → **`open_trade`** → `action["action"]="TRADE_OPENED"` (`:2265, 3103-3116`); rejection emits `FILTER_REJECTED`/`CONFIRMATION_FAILED`/`SHADOW_ADVISORY_BLOCK` | **DRIFT** |
| Never own economic RR | position sizing `resolve_risk_pct(adjusted_score)` on approval (`:2091`); SL/TP built into the opened trade | **DRIFT (boundary)** — spine drives execution economics, not just structure |
| Score ≠ state (dual math) | FSM `RiskScore.final` (`:197-208`) is a *different* computation from Surface-1 `compute_scores` (`scoring_engine.py:40-61`) — the pre-existing 🟡 reason (M:256) | **DRIFT (documented, secondary)** |

**Surface 2 result: the structure/score semantics are aligned, but the surface crosses the
Stage-1 boundary — it approves, sizes, and executes trades.** ⚠️ → see §D.

---

## §D — TruthConflict (primary, §6.2 shape)

| Field | Content |
|---|---|
| **Conflict** | The frozen contract says CRT **never approves / never decides whether to trade** (§A.3, §B.4); the runtime spine **does approve, size, and open trades**. |
| **Source A (contract)** | Stage-family law "CRT — may approve a trade? **Never**" + charter Stage-1 hard rule M:46 ("Fusion (Stage 4) is the sole owner of trade approval … Ultron/planner own economic execution gates **after approval**") + added non-goal §B.4. |
| **Source B (code)** | `config_layer/crt_engine_v2.py`: `UltronRiskEngine.approve` (`:2016-2094`), `approve_with_soft_conf` (`:1930-2012`), `open_trade` + `TRADE_OPENED` (`:2265, 3103-3116`), `resolve_risk_pct` sizing (`:2091`). |
| **Evidence** | `approve` returns `True, None` = APPROVED (`:2094`); the spine path has **no separate Stage-4 fusion approval** — the embedded `UltronRiskEngine` *is* the approval authority, then `open_trade` fires directly. (Contrast: the Stage-4 `FusionEngine`/`DecisionEngine` approval lives on the *EngineRunner* path and is OFF by default in backtest — F-037 `BACKTEST_ENGINE_GATE`.) |
| **Root cause** | `crt_engine_v2.py` is a **pre-decomposition monolith** that conflates MIAR Stages **1 (structure)** + **3 (safety/BitNet veto)** + **4 (approval)** + **5 (execution/sizing)** inside one class. The MIAR stage decomposition wants these owned by CRT / BitNet / Fusion-Decision / ExecutionPlanner respectively. Even the charter's own M:46 draws the line the monolith crosses: Ultron should own execution gates *after* approval, not *be* the approval. |
| **Impact** | Contract-level, **not** a production-loss claim (F-010/F-037: headline ROI is backtest-only; the spine's own economics are a separate track). The MIAR node "crt" cannot be `ALIGNED` while the spine self-approves. |
| **Recommendation** | **Do not resolve here.** This is a **step-4** decision requiring a user call: how to unbundle approval/execution from the Stage-1 structure model **without deleting any intent** (§E). Until then `alignment` stays `SEMANTIC_DRIFT`. |

---

## §E — Proposed step-4 remediation (PROPOSAL — NOT ACTION)

> Written per the decision to "document + propose fix." **No code is changed by this document.**
> Hard rule for whoever executes step 4: **no intent is deleted** — the approval/sizing/veto
> logic is *relocated to / owned by the correct stage*, never removed. Any of these is a
> user-gated design choice, not a foregone conclusion.

**Option 1 — Ownership relabel, zero behaviour change (lightest).** Keep `crt_engine_v2.py`
byte-identical, but formally register the embedded `UltronRiskEngine` as a **Stage-3/4 authority
that happens to be co-located** in the CRT file, and split MIAR into two nodes' worth of ownership
documentation. Risk: contradicts MIAR note M:258 ("do not invent a second owner"); needs the
user's ruling on whether co-located ≠ owned-by-CRT is acceptable.

**Option 2 — Physical extraction (true decomposition).** Move `UltronRiskEngine` +
`open_trade`/sizing out of `crt_engine_v2.py` into a Stage-4/5 module the spine *calls*, leaving
`CRTEngine.process_candle` emitting **structure state + score only**. Highest alignment value;
largest blast radius (spine is CLOSED per `crt_closure_report.md` — extraction must prove
byte-identical ledgers before/after, and must not reopen closure phases). This is the
"Frozen-Engine + Mutable-Behavior" end-state for CRT.

**Option 3 — Accept documented drift (status quo + honesty).** Keep the monolith, keep
`alignment: SEMANTIC_DRIFT` permanently with this document as the standing explanation, and gate
any *new* approval logic to the decomposed path only. Cheapest; never reaches `ALIGNED`.

**Recommended sequencing:** get the user's ruling on Option 1 vs 2 vs 3 **before** any step-4
code. Options 1/3 are doc-only; Option 2 is a governed extraction under the CRT closure's
parity constraint.

---

## §F — Key file map

| Role | Path |
|---|---|
| Intent contract (this freeze) | `docs/governance/crt_intent_contract.md` |
| Machine intent twin | `docs/governance/miar_registry.json` (`crt` entry :116-154) |
| Charter (prose) | `docs/governance/MODEL_INTENT_AUTHORITY_REGISTER.md` (§3.3 :239-258; §0.3 vocab; M:46 hard rule) |
| Clean surface (fusion-slot scorer) | `src/engines/crt_engine.py::compute` · `src/engines/scoring_engine.py::compute_scores` |
| Drifting surface (spine) | `src/config_layer/crt_engine_v2.py::CRTEngine` (`UltronRiskEngine.approve` :2016 · `approve_with_soft_conf` :1930 · `open_trade` :2265 · `TRADE_OPENED` :3103-3116 · `RiskScore.final` :197) |
| Spine driver | `src/runtime/backtest_v2.py` · entry point `src/research/model_runners/contracts.py` |
| Decision authority (Stage 4) | `src/core/engine_runner.py:1007-1008` (DecisionEngine sole EXECUTE/REJECT) |
| State identity | `src/config_layer/state_identity.py` (9 states, VALID_TRANSITIONS :69-79; weight-identity "never alias" note :112-121) |
| Prereq — closure (do not reopen) | `docs/governance/crt_closure_report.md` |
| Prereq — formula contract | `docs/governance/crt_formula_contract.md` |
| Human spine picture | `docs/topics/crt-spine.md` |

---

## §G — Final return

```text
CRT_INTENT_CONTRACT_STATUS = FROZEN (steps 1–3)
ALIGNMENT                  = SEMANTIC_DRIFT (unchanged — cannot lock while §D open)
CLEAN                      = engines/crt_engine.py::compute (Score, not Probability; never approves)
DRIFTED                    = config_layer/crt_engine_v2.py::CRTEngine (approves + sizes + executes)
RECONCILED                 = hypothesis, dependencies, authority_boundary (J<->M) + added Stage-1 non-goal
DO_NOT                     = flip alignment to ALIGNED · edit crt_engine_v2.py · reopen CRT closure phases · delete any intent
NEXT                       = step 4 — user rules on §E Option 1/2/3, then resolve drift; step 5 = lock
```
