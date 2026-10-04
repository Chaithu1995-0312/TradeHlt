# Architecture Mapping — continued from `.grok/HANDOFF_TO_CLAUDE.md`

**Lane:** semantic certification of existing assets (P-CRT-LANE-01).
**Not an implementation plan.** No `src/` edits, no live, no MT5 order, no mining script, no new MC-*, P-GOAL-04 stays closed.
This file is the working map surface only. Authority stays `.grok/PENDING.md` (P-FLOW-01…11) + `assistant_project.md`.

---

## Context

Grok and the user spent 2026-08-25 naming already-built assets and placing each on one architecture, because the named failure mode (P-FLOW-01) is *another standalone script that does not consume past findings*. Eleven cards are locked; the gap list (P-FLOW-08) is still unplaced. The user asked Claude to continue the mapping, not to build.

What this turn adds: the cards are placed onto architecture that **already exists in the repo**, and four seams are surfaced where a card as stated collides with, or is already answered by, a frozen contract.

---

## The locked machine (five lines)

1. **B first.** LLM reasons on Parquet + semantic/ontology + findings → a *governed* strategy object.
2. That object enters the **existing spine**: 4 engines → fusion → decision → ExecutionPlanner → UltronRiskGate.
3. **MT5 terminal** places the order after Ultron. The LLM never talks to the broker.
4. **Profit is measured on Geometry** (the same geometry that must match TradingView), not loose PnL and not F-022 labels.
5. **Goal is A *through* B** — it should look like an LLM that trades. Built ≠ production-incorporated (F-073).

---

## The one architecture (existing — nothing new drawn)

Three surfaces already in the repo. The map hangs cards on these; it does not invent a fourth.

| Axis | Surface | Status |
|---|---|---|
| **Vertical (objects)** | `docs/governance/CANONICAL_LAYER_IDENTITY_CONTRACT.md` — **L0 OHLC → L1 Feature Values → L2 Feature States → L3 CRT States → L4 Geometry → L5 Outcome** | CLOSED / FROZEN v1.0.0, user-accepted 2026-08-23 |
| **Horizontal (flow)** | `docs/architecture/signal-flow.md` — candle→order spine + 4 async feeders | living map |
| **Rules** | `docs/intent/{000_governance,100_execution,200_risk,300_memory,400_research,500_agent,900_preservation}.md` | domain contracts (INTENDED) |

**Key result:** the layer chain the user has been naming from memory across P-FLOW-03 and P-FLOW-11 (*OHLC → Feature → Feature State → CRT State*; *Geometry, Outcome not collapsed*) is **verbatim the frozen L0–L5 contract**. The mapping does not need a new spine — it needs each card bound to a layer and a producer.

---

## Card placement

| Card | Lands on | Note |
|---|---|---|
| 01 one flow, no orphans | the whole map | intent lock, not yet a GROK.md rule |
| 02 mapping method | — | method, not an asset |
| 03 Visual TV state validation | L0 → L3, then a render | **Seam 1** — producer unnamed |
| 04 Parquet (LLM memory + mining) | projection/storage under Phase-3 physical store; domain `300_memory` | CURRENT unpinned |
| 05 Semantic + Ontology + Formula registry | §6.6 ontology = authority #1 · §6.7 Semantic OS grounding · formula registry = L1 formula identity | three nouns, deliberately not collapsed |
| 06 Multi-agent access | `500_agent` (in-repo `PLAN_REGISTRY`) **and** §13 `multi_llm/` | two distinct doors, plus Grok INFRA = three |
| 07 Research layer + reasoning LLM | `400_research` — isolated, forbidden from importing the spine | must consume F-019…F-094 |
| 08 gap list | the empty slots below | unplaced |
| 09 B first / A-through-B | **Seam 2** — the LLM's one legal entry point | |
| 10 MT5 auto-placement | after Ultron = live rail | **Seam 4** — blocker is F-073, not the y/N gate |
| 11 Profit on Geometry | L4 + L5 | **Seam 3** — L4 alone cannot carry profit |

**Still empty (P-FLOW-08):** spine after CRT (4 engines · fusion · decision · planner · Ultron) · Geometry+Outcome as their own cards · live rail · promotion/governance · measurement contract · G001 · BitNet/TradeNet · parent-CRT/HTF · identity/storage · clock · findings-as-input.

---

## Four seams found this turn

### Seam 1 — P-FLOW-03 has two producers, and equating them is forbidden

The frozen contract (§7.2) closes `producer_id` to exactly two: `engine` (`CRTEngine._transition`) and `resolver` (`CRTStateResolver`). It then states a **hard forbidden equality**: engine occupancy ≠ resolver occupancy at the same bar.

The user's chain *"CRT State **from feature states**"* is the **resolver**. The thing that actually trades is the **engine**. F-069 measured them at 88.16% agreement on 47,197 XAUUSD bars, EXECUTION structurally unreachable on the resolver, residual declared *divergent construction* (96.1%), config-unreachable.

⇒ A TradingView state-validation run must declare which producer it renders. Validating the resolver against TV validates the resolver, not the trading engine.

### Seam 2 — the LLM in P-FLOW-09 has exactly one legal entry point

Two INTENDED contracts block the obvious reading:
- `100_execution` Must-Never #2 — *never allow the LLM to approve or reject a trade (advisory only, observed only)*.
- `500_agent` Must-Never #1 — *never allow the LLM to plan tool sequences* (`PLAN_REGISTRY` is a hard prefix).

So the LLM cannot join the decision path at runtime. But CLAUDE.md §6.5 already defines the seam that works: the **GOAL-SEEKING** class — *"behavior is generated as config; the engine is untouched."*

⇒ `LLM → candidate config / strategy object → ConfigValidator (APPROVE) → PromotionManager → ACTIVE_VERSION → deterministic spine → Ultron → MT5`. The LLM writes **config**, never a decision. That is what makes A-through-B legal under the repo's own contracts, and it re-reads P-FLOW-09's "governed strategy object" as *a candidate config + a sealed `MC-*` + a measured G001* — not a signal.

### Seam 3 — P-FLOW-11 as stated is not measurable on L4 alone

Frozen contract §8/§9: **L4 Geometry** = entry/SL/TP frozen at open. **L5 Outcome** = realized R of one geometry *under one walk + cost + fill basis*; §9 adds that the same entry set under a different basis is a **different** L5 object (F-082, F-088).

⇒ "Profit measured on Geometry" resolves to: **R at L5 over an L4 geometry, with the basis named.** Keeping Outcome uncollapsed (which the user already required) is exactly what forces the basis to be declared. The production-shaped ruler already exists: `geometry_schema = dual_tp_partial` + `multi_tp_walk` (SEM-017) + SEM-015 measured broker cost + SEM-016 adverse fill — the corrections behind F-082 and F-088.

### Seam 4 — P-FLOW-10's blocker is not the human-confirm gate

`500_agent` Must #3 (y/N on every write) governs **agent tool writes to the repo**, not order dispatch. Unattended MT5 placement does not violate it.

⇒ The real blocker is F-073: no **production** live rail. Paper callers exist (`LiveRailOrchestrator`, `live_hook.dry_run`, `run_live_rail.py --paper`); `ACTIVE_VERSION` has no `live_rail` section. Plus F-010 (live PnL UNVERIFIED) and F-085 (the canonical ingestion boundary never ran on the live path until it was fixed — certified by replay only, no production consequence).

---

## Two open decisions for the user

1. **Which gap to place next** — spine-after-CRT · live+promotion+MT5 · measurement+G001+findings-as-input · Geometry+Outcome.
2. **Whether CURRENT pins from disk are authorized.** Every card carries "CURRENT vs INTENDED unpinned." Grok deliberately kept `src/` closed. Resolving those needs read-only source pins, one named asset at a time.

Two facts sit in memory and are explicitly **not asserted** here until pinned: (a) the 2026-08-23 lineage census recorded the declared **L2→L3 edge as not existing** and Feature States / CRT States as ephemeral — load-bearing for P-FLOW-03 and P-FLOW-04; (b) the parquet layer was recorded as a **projection over JSONL**, with JSONL remaining system of record — load-bearing for P-FLOW-04.

---

## Verification (for a mapping turn, not code)

- Each placed card names a layer (L0–L5) **or** a spine stage **or** a domain contract — no card floats.
- No card asserts CURRENT without either a registered finding (F-###) or an authorized source pin.
- Every seam cites the frozen artifact it derives from.
- On close: `.grok/PENDING.md` rows updated in place (never deleted) + a `📝 SESSION LOG ENTRY` in `assistant_project.md` per §6. **Both require leaving plan mode.**
