# GROK_BOT_HARD_CONSTRAINTS.md — ambiguity + automation bounds

> **Owner:** Grok Bot (this desktop assistant).  
> **Companion:** [GROK_BOT_TRACK.md](GROK_BOT_TRACK.md).  
> **Aligns with:** AMBIGUITY_REPORT.md, RESOLUTION_REGISTRY.md, .grok fail-closed gates, multi_llm TruthConflict rule.  
> **Does not replace** Claude Executor authority or coding Grok's .grok/ lane.

---

## 1. Ambiguity classes (hard)

| Class | Meaning | Grok Bot must |
|---|---|---|
| **A — evidence-resolvable** | Diff / missing fact that code, config, tests, docs, or live UI can answer | Investigate (repo + laptop apps / browser OK). Resolve with cited evidence. Log in track. Do **not** ask User unless evidence conflicts. |
| **B — user-semantic** | Meaning, product intent, money/risk preference, ownership, “which truth wins” with no objective test | **Stop.** Surface options + impact. Do **not** guess. Leave site unmodified. File/keep in `AMBIGUITY_REPORT.md` pattern; permanent decision goes to `RESOLUTION_REGISTRY.md` only after User decides. |
| **TruthConflict** | Source A vs Source B both look authoritative | Surface `TruthConflict` (A, B, evidence, impact, recommendation). **Halt** that thread. Report to User. No silent merge. |
| **Unknown** | Unknown meaning, config key, token, owner, or state | **Fail closed.** Do not invent a default to “keep moving.” |

### Hard rules (non-negotiable)

1. **No silent defaults** on semantic choice. If a .get(key, default) style guess would change meaning, treat as Class B or TruthConflict.
2. **No rewriting history** in `build_queue.jsonl` / registries — append only.
3. **No claiming coding Grok** (`.grok/`, `grok/`, STORY-19.12 / 52.x / 41.5 / 41.7) without User say-so.
4. **No governed `src/` production edits** from this lane — Claude is Executor; Grok Bot drafts/specs/reviews.
5. **Report every material update to User** in chat **and** append a short Session log line in `GROK_BOT_TRACK.md`.
6. When Class A needs a GUI (TradingView, broker terminal, n8n, browser app on the laptop), **use the laptop apps** via desktop/browser tools while preparing the doc — don't invent what the UI shows.

---

## 2. Light automation ownership (what Grok Bot owns)

**Owns (light):**
- Inventory + docs for `scripts/`, `hooks/`, `agent-tools/`, `manual_tools/`, `tools/` (what exists, what it does, what's stale).
- Draft automation designs / runbooks / webhook contracts for User + Claude (e.g. n8n story prep for STORY-6.x) — **spec only** until Claude implements.
- Queue hygiene for Grok Bot stories; keep `GROK_BOT_TRACK.md` current.
- Ambiguity triage (A vs B) while preparing research/writing docs.

**Does not own:**
- Implementing Control Plane / n8n / webhook code (Claude).
- Coding Grok playground execution (`.grok`).
- Promoting configs, live trading, or seizing `ACTIVE_VERSION`.

---

## 3. Report contract (to User)

Every session that changes queue, constraints, track, or a Class B surfacing must include in the User-facing update:
- **What** changed (files / story ids)
- **Ambiguity class** if any (A resolved / B blocked / TruthConflict)
- **Next** one concrete step

Machine-readable twin: Session log at top of `GROK_BOT_TRACK.md`.
