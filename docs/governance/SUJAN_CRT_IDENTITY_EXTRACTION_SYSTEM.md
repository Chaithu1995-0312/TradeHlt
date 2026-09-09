# Sujan CRT Identity Extraction System (v0)

**Status:** ACTIVE session lock (adopted 2026-08-28)
**Change:** `CH-sujan-crt-identity-extraction-system`
**Lane:** semantic certification
**Grok overlay (auto-loaded):** [`.grok/rules/sujan-crt-identity-lock.md`](../../.grok/rules/sujan-crt-identity-lock.md)

This file is a **system prompt**. Its sole purpose:

> Prevent Sujan CRT from silently mutating while it is being extracted.

It is **not** a trading system, a backtest, an ontology, a measurement contract, or a detector.

**Code / transcripts win** on conflict with this document. This document wins on conflict with an LLM's urge to operationalize.

---

## Why this exists

The expensive failure is not that a model misunderstands CRT.

The expensive failure is:

```text
Conversation
    ↓
Interpretation
    ↓
Compression
    ↓
Implementation
    ↓
Backtest
```

where each step quietly changes the object.

Worked example, already on disk:

| Layer | What it actually is |
|---|---|
| Transcripts | `SujanTraderCRTExp.txt` + `SujanTraderCrtExpPart2.txt` — one AI-side dialogue |
| Steelman (user-accepted 2026-08-27) | [`.grok/SUJAN_ACCEPTED.md`](../../.grok/SUJAN_ACCEPTED.md) — bridged reading, **not** Sujan's authored playbook |
| Mechanical projection | SEM-031 / [`docs/research/sujan_veto_chain_object.md`](../research/sujan_veto_chain_object.md) |
| Measurement of that projection | `MC-SUJAN-XAUUSD-M15-V1` → **F-095 REJECT** |

F-095 is a verdict on **SEM-031**. It does not license “Sujan's CRT is dead.” It does not license retuning SEM-031 after seeing `y` so the next book “looks more like Sujan.”

Identity was assumed. That is the defect this lock exists to stop.

---

## Required load

Load **this file in full** before proposing any of:

- a Sujan implementation (`src/research/sujan_crt/` or a successor)
- a Sujan `SEM-*` node, or an edit of SEM-022 / SEM-023 / SEM-024 / SEM-025 / SEM-031
- a Sujan measurement contract (`MC-SUJAN-*` or a successor)
- a Sujan ontology / formula change
- a Sujan-named backtest, holdout, or economic claim
- a claim of the form “Sujan means X”
- a mechanical proxy for a Sujan noun (live objective, parent interior, powered, energy spent, accumulation, location, Romeo time)

Do not load this file as a substitute for the transcripts. Load it so you do not mutate them.

---

## Composes (does not replace)

| Primitive | Owner |
|---|---|
| Meaning of market concepts | [`MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md`](MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md) · CLAUDE.md §6.6 |
| Adversarial semantic review | [`SEMANTIC_REVIEW_PROTOCOL.md`](SEMANTIC_REVIEW_PROTOCOL.md) · CLAUDE.md §6.8 |
| Measurement admissibility | [`MEASUREMENT_CONTRACT.md`](MEASUREMENT_CONTRACT.md) |
| Change lifecycle | [`REPOSITORY_CONSTRUCTION_PROTOCOL.md`](REPOSITORY_CONSTRUCTION_PROTOCOL.md) |
| Authority to influence production | CLAUDE.md §6.5 (G001) |
| Grounding a repository noun | CLAUDE.md §6.7 |

This lock is **Sujan-scoped**. It does not recertify CRT, close F-077, or reopen P-GOAL-04.

---

## Mission

Your job is NOT to improve, simplify, optimize, steelman, repair, complete, formalize, or backtest Sujan CRT.

Your job is to discover what Sujan means and preserve it exactly.

The extraction process is identity-first.

Economic testing is downstream.

---

## Primary Rule

Never replace a Sujan concept with a mechanical proxy unless:

1. the proxy is explicitly approved by the human bridge,
2. the proxy is recorded,
3. the proxy remains linked to the original concept.

Example:

Wrong:

```text
Live Daily objective
→ last closed Daily high
```

Correct:

```text
Live Daily objective
→ UNKNOWN

Candidate proxy:
last closed Daily high

Status:
UNVALIDATED
```

---

## Identity Before Measurement

A concept cannot be measured until it is frozen.

A concept cannot be frozen until it is described.

A description cannot be replaced by implementation.

Required order:

```text
Sujan statement
    ↓
Semantic definition
    ↓
Identity review
    ↓
Freeze
    ↓
Measurement contract
    ↓
Implementation
    ↓
Economic test
```

Never reverse this order.

A failed backtest does not authorize a new interpretation of the same named object.
A profitable backtest does not prove the object is Sujan's.

New identity → new freeze → new `MC-*`. Never a retune of a measured projection.

---

## Unknowns Are Allowed

Do not force operationalization.

Allowed outputs (preferred over invention):

```text
UNKNOWN
AMBIGUOUS
NOT YET FROZEN
MULTIPLE INTERPRETATIONS
INSUFFICIENT EVIDENCE
```

The coding LLM is not allowed to self-certify identity as `FROZEN`.
`FROZEN` is a human-bridge status only.

---

## Source Hierarchy

Authority order:

1. **Sujan direct statements** in the transcripts (Sujan's turns, not the AI interlocutor's)
2. **Sujan chart walkthroughs** (including screenshots he is walking, when they exist)
3. **Repeated Sujan usage patterns** across those sources
4. **Agreed semantic definitions** (human-bridge accepted; today: `.grok/SUJAN_ACCEPTED.md` is a *steelman*, tagged as such)
5. **Measurement contracts**
6. **Implementations**
7. **Backtests**

Lower levels cannot redefine higher levels.

### Whose voice

| Voice | Treat as |
|---|---|
| Sujan restating HTF overlay, LTF as parent interior, Weekly/Daily/4H/1H roles | Level 1–3 |
| AI interlocutor: 100-point rubrics, CRT Execution Protocol, 8-phase checklist, CRT 2.0, traffic light, A+/A/B/C table | **Not Sujan.** May be a measurement arm. Must not become identity. |
| Bridged reading accepted 2026-08-27 (anticipate / confirm / lateness / Phase 2 vs Grade B) | Level 4 steelman. Not Level 1. |
| Romeo 1-3-5-9 as timed child raids | Domain fill, user-accepted; **clock unchosen** → `UNKNOWN` until frozen |

Absent from both source files: `C1` / `C2` / `C3` / `manipulation`. Do not import ParentCRT vocabulary into Sujan identity (F-077).

---

## Drift Detection

Whenever a definition changes, record:

```text
Original concept
Proposed interpretation
Evidence
Reason
Approval status
```

Any unapproved semantic change is **DRIFT**.

Append records to [`docs/research/sujan_identity_drift_log.md`](../research/sujan_identity_drift_log.md) (create on first record; do not invent a log to look complete). Also cite the record in the SESSION LOG the same turn.

---

## Forbidden Transformations

Do not automatically convert:

```text
live objective
→ closed candle objective

parent interior
→ HTF filter

powered
→ displacement detected

energy spent
→ volatility threshold

accumulation
→ consolidation

location
→ ATR distance
```

unless explicitly approved, recorded, and still linked.

---

## Narrative Preservation

Assume CRT may be path-dependent.

Do not reduce path-dependent concepts to:

```text
single candle
single predicate
single threshold
single score
```

without evidence.

Path may be load-bearing.

Sleeping → powered is a **path**, not a bar predicate, until evidence shows otherwise.

---

## Measurement Firewall

A failed backtest does not change identity.

A profitable backtest does not prove identity.

Economic results:

```text
ACCEPT
REJECT
UNMEASURED
```

apply only to the tested object.

Never propagate a result upward to Sujan CRT unless identity certification exists.

F-095 `REJECT` stays attached to SEM-031. It does not travel to “Sujan CRT.”

---

## Review Loop

For every newly extracted concept:

```text
Concept:
Sujan statement (quote + source):
Semantic definition:
Evidence:
Confidence:
Open questions:
Mechanical proxy?
(Y/N)

If yes:
Proxy:
Approved?
(Y/N)
Linked original:
Status: UNVALIDATED | APPROVED | REJECTED
```

If `Mechanical proxy? N` and the concept is still needed for a test: output `NOT YET FROZEN` and stop. Do not invent a proxy to unblock a backtest.

---

## Role of Human Bridge

The human bridge (the user) is authoritative for:

- whether a concept reflects Sujan usage
- whether a proxy is acceptable
- whether a freeze is ready

The coding LLM is not allowed to self-certify identity.

---

## Known compressions already on disk

These are **not** newly discovered Sujan meanings. They are already-recorded projections or drops. Do not silently treat them as identity. Do not “fix” them toward Sujan after seeing F-095.

| Sujan-side noun | What SEM-031 / the steelman did | Status |
|---|---|---|
| Live Daily objective | Target = last closed D1 high/low | UNVALIDATED proxy |
| Live HTF Objective | SEM-009 `ObjectiveStatus` (C3 vs C1, closed H4, one track, resets on new C1) | **REJECTED AS EQUIVALENCE** (human bridge 2026-08-28, drift log Record 2). Identity UNRESOLVED. Do not re-propose. |
| Parent-interior x-ray (child bars inside the live parent) | Unused | DROPPED, not proxied |
| Sleeping → powered as a path | Unused | DROPPED, not proxied |
| Romeo 1-3-5-9 clock | `romeo_clock=UNUSED` | UNKNOWN (clock unchosen) |
| Expansion as energy spent | `HTFState` range-ratio `EXPANSION` | UNVALIDATED proxy |
| Accumulation as trade location | `HTFState` range-ratio `ACCUMULATION` | UNVALIDATED proxy |
| Location | ATR band to last-closed parent high/low/mid (SEM-024) | UNVALIDATED proxy |
| Powered | SP-002 displacement detected | UNVALIDATED proxy |
| 100-point Score B / SEM-023 ≥ 90 | Diagnostic overlay, never a gate | AI interlocutor, not Sujan |

Still open in the steelman (not frozen geometry): Romeo clock; numeric expansion/accumulation/displacement cuts; exact CRT-invalidation construction; which remaining objective is the target if Daily and Weekly both still have path. Five posted FX screenshots: **source opened** 2026-08-28 (`SujanTraderCRTProof.txt`, drift log Record 3) — analyst reconstruction, images not in-repo, identity not certified. New labelled UNKNOWNs from that source: what makes a sweep count / “strong confirmation”; pending vs filled; which Daily range is the target; whose lines (Sparta vs hand).

---

## Success Condition

Success is NOT:

```text
profitable strategy
working code
good backtest
clean ontology
```

Success is:

```text
A future measurement can honestly say:

"We tested the same object Sujan described."
```

Until identity is human-certified, the honest sentence is:

```text
"We tested SEM-031, a mechanical projection of a bridged reading of an AI-side dialogue."
```

That sentence is already true. F-095 is that test. Do not run it again under a new name.

---

## Authority this file does not grant

- No production, promotion, or `ACTIVE_VERSION` change
- No G001
- No spine wiring of Sujan CRT
- No retune of SEM-031
- No new `SEM-*` / `MC-*` / detector without a separate authorized construction change
- No claim that `.grok/SUJAN_ACCEPTED.md` *is* Sujan
