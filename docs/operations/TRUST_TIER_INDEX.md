# Document Trust Tier Index

> **Which source to trust for what kind of question.**
>
> Not all documents are equally reliable. Some are authoritative by design. Others are
> point-in-time snapshots that drift. This index tells you which source to use for each
> type of question, and how much confidence to place in the answer.
>
> Last updated: 2026-06-10

---

## Tier 1 — Source Code (Highest Authority)

| Question | What to read | Why |
|----------|-------------|-----|
| "Is this config key actually consumed?" | The actual consumer `.py` file | Source truth. Not documentation. |
| "Does this module call X?" | The module's import statements + call sites | Only way to know for sure. |
| "What does this function return?" | The function body | Documentation drifts; code doesn't. |

**Heuristic:** If a config claim in a `.md` file has not been source-confirmed, treat it as provisional.

---

## Tier 2 — Runtime Config Reachability Audit

| Question | What to read | Why |
|----------|-------------|-----|
| "Which config keys are actually live?" | `reports/runtime_config_reachability.md` (Tier A findings) | Source-confirmed consumer-by-consumer. |
| "Is this key an illusion?" | `docs/operations/KNOWN_ILLUSIONS.md` | Extracted from Tier A audit findings. |
| "What's the effective value vs config value?" | `reports/runtime_config_reachability.md` §H-class | Documents where DynamicThreshold or hardcoded constants override config. |

**Heuristic:** Tier A findings are strong enough to act on without further verification. Tier B findings need source confirmation.

---

## Tier 3 — Authoritative Design Documents

| Question | What to read | Why |
|----------|-------------|-----|
| "How does a candle become an order?" | `docs/SIGNAL_FLOW.md` | Authoritative by declaration (CLAUDE.md). |
| "What CLI commands exist?" | `docs/CLI_MATRIX.md` | Auto-generated from registry. |
| "What events does the CRT engine emit?" | `docs/architecture/EVENT_TAXONOMY.md` | Authoritative event catalogue. |
| "What are the system goals and invariants?" | `docs/architecture/GOAL.md` | Authoritative north-star document. |
| "What is the replay determinism contract?" | `docs/architecture/REPLAY_GOVERNANCE.md` | Authoritative replay rules. |

**Heuristic:** These documents are declared authoritative in CLAUDE.md. If they conflict with Tier 4 docs, the Tier 3 doc wins.

---

## Tier 4 — Reference Documentation (May Drift)

| Question | What to read | Why |
|----------|-------------|-----|
| "What config keys exist?" | `docs/CONFIG_REFERENCE.md` | Generated from `v1_multi_2026_03.json`. May drift if config was updated. |
| "What are the dataclass/enum shapes?" | `docs/SCHEMAS.md` | Known to have drifted (fitness_weights documentation wrong). |
| "What are the conventions and anti-patterns?" | `docs/CONVENTIONS.md` | Stable — conventions change slowly. |
| "How do I run the tests?" | `docs/TESTING.md` | Stable — test structure is mature. |

**Heuristic:** If CONFIG_REFERENCE.md or SCHEMAS.md says something different from the actual JSON or code, the JSON/code wins.

---

## Tier 5 — History and Analysis (Not Operational Truth)

| Question | What to read | Why |
|----------|-------------|-----|
| "Why does this code exist?" | `docs/PROJECT_HISTORY.md` | Captures reasoning, mistakes, evolution. Not reliable for current wiring. |
| "What happened on date X?" | `assistant_project.md` | Append-only session log. |
| "What did the hidden wiring audit find?" | `reports/hidden_wiring_audit.md` | 20 findings — some corrected by later reachability audit. |

**Heuristic:** Use these for understanding context, not for making operational decisions. Always verify operational claims against Tiers 1-3 before acting.

---

## Quick Reference Table

| Source | Trust Level | Best For |
|--------|-------------|----------|
| Source code | HIGH | "What does this actually do?" |
| `reports/runtime_config_reachability.md` (Tier A) | HIGH | "Is this config key live?" |
| `docs/operations/KNOWN_ILLUSIONS.md` | HIGH | "Which config keys are illusions?" |
| `docs/SIGNAL_FLOW.md` | HIGH | "How does a candle become an order?" |
| `docs/CLI_MATRIX.md` | HIGH | "How do I run X?" |
| `docs/architecture/EVENT_TAXONOMY.md` | HIGH | "What events exist?" |
| `docs/architecture/GOAL.md` | HIGH | "What invariants must hold?" |
| `docs/CONFIG_REFERENCE.md` | MEDIUM | "What config keys exist?" (may drift) |
| `docs/SCHEMAS.md` | LOW | "What are the dataclass shapes?" (known drift) |
| `docs/CONVENTIONS.md` | HIGH | "What are the coding rules?" |
| `docs/TESTING.md` | HIGH | "How do I run tests?" |
| `docs/PROJECT_HISTORY.md` | LOW (historical) | "Why was this decision made?" |
| `docs/operations/CURRENT_STATE.md` | MEDIUM | "What's the current snapshot?" (date-stamped) |
| `assistant_project.md` | LOW (historical) | "What happened during session X?" |
| `reports/hidden_wiring_audit.md` | MEDIUM | "What findings existed?" (some corrected) |

---

## How This Index Was Created

Trust levels were assigned based on:

1. **Declared authority** — Documents like SIGNAL_FLOW.md and EVENT_TAXONOMY.md are declared authoritative in CLAUDE.md.
2. **Source confirmation** — Audits that cross-reference actual code (runtime_config_reachability Tier A) are ranked above audits that don't.
3. **Known drift history** — SCHEMAS.md was found to have incorrect `fitness_weights` documentation on 2026-06-06, lowering its trust tier.
4. **Generation method** — CLI_MATRIX.md is auto-generated from the command registry, making it harder to drift than hand-written docs.

This index should itself be verified periodically (e.g., every 3 months or after major architectural changes).