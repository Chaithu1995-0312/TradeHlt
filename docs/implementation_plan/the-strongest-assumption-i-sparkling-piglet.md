# Intelligence Compounding Doctrine — Integration Plan

## Context

The user's north star for Tradelatest is **zero intelligence loss + continuous intelligence
compounding** — the repository as a self-describing *intelligence substrate*, not a pile of
Python files. The concrete, freezable ask underneath the essay: codify an **Intelligence
Compounding Doctrine** into the operating manual, and make it *operational* (run every turn)
rather than aspirational prose that gets ignored.

The doctrine's core claim: tool outputs / artifacts are **not** intelligence. They become
intelligence only when their *meaning, purpose, ROI toward the user's economic goals, and the
belief change they produce* are captured and preserved. Modules are "frozen thoughts"; the
true loss is losing **why** something exists and how it compounds long-term wealth.

This is doc-only and additive. It complements — does not replace — the §6 Persistent Logging
Mandate. The user explicitly warned against premature heavy frameworks (graph DB / ontology /
vector DB / n8n); this is the **Stage-1 markdown-checklist** step on that evolution path.

### Decisions locked (via AskUserQuestion)
- **Footprint:** condensed doctrine inline in `CLAUDE.md` + full long-form companion doc.
- **Operationalize:** add a `Belief Update / ROI` line to the SESSION LOG block **and** a
  rule that durable belief changes are written as memory files (tying into the auto-memory
  substrate so beliefs persist across sessions, not just within one session log).

### On-disk facts that shape placement
- `CLAUDE.md` runs **§6 → §7 directly**; there is **no §6.1** on the `patch` branch. (Memory
  references a "§6.1 Topic Sync Mandate" — that is from another branch and is *absent here*.)
- §7, §8, §12 are cross-referenced **by number** inside the file, so a renumber is costly →
  insert as **§6.1** to avoid touching them. Flag: if Topic Sync §6.1 later merges in, one of
  the two renumbers to §6.2.
- `CLAUDE.md` is deliberately terse with token-control rules (§8) and offloads detail to
  companion docs via the §2 doc-map table → condensed inline, full text in a companion doc.
- The `📝 SESSION LOG ENTRY` block (defined in §7.4, mandated in §6) is the **one mechanism
  that already fires every response** — the correct, no-new-framework place to operationalize.

---

## Changes

### 1. `CLAUDE.md` — insert condensed doctrine as new §6.1 (after §6, before §7)

Insert immediately after line 118 (end of §6 bullets) / before the `---` at line 120. Keep it
terse to honor §8. Target ~25 lines:

```markdown
## 6.1 Intelligence Compounding Doctrine (non-optional)

> Complements §6. The repository's purpose is **zero intelligence loss + continuous
> compounding**, not file preservation. Full long-form: [`docs/architecture/intelligence-compounding.md`](docs/architecture/intelligence-compounding.md).

**Intelligence ≠ information.** Intelligence is a *persistent change in beliefs that improves
future decisions toward the user's long-term (economic) goals.* Data, logs, artifacts, and
tool outputs are **not** intelligence until their meaning + ROI + belief-impact are captured.

**Meaning over data.** Never treat a tool output as an isolated fact. Interpret every artifact
through: `Artifact → Purpose → User Intent → Goal Contribution → ROI → Belief Update`.
`Tool output → Memory` (raw) is forbidden; the path is `Tool → Output → ROI eval → Belief
update → Memory`.

**Modules are frozen thoughts.** Understanding *what* code does is insufficient; reverse to
*why it exists* — `Module → Purpose → User Thought → Economic Meaning → Long-Term Value`. The
true intelligence loss is losing the economic *why*, not the recoverable code.

**Per-result ROI check.** After a consequential tool result, ask: (1) which goal did this
serve? (2) did it move the probability of that goal? (3) what belief changed? (4) what should
stop being explored? (5) what next? A null/negative financial result with a clear conclusion
(e.g. "EMA gate non-binding, stop optimizing it") is **high knowledge-ROI** — preserve it.

**Operational hook:** every response's SESSION LOG carries a `Belief Update / ROI` line
(§7.4). Durable belief changes (confirmed/invalidated hypotheses, dead ends, economic meaning,
confidence shifts) are saved as a **memory file** (`feedback`/`project` type) per the Memory
mandate — not left only in the session log. The enemy is fragmented meaning, not missing data.
```

### 2. `CLAUDE.md` §7.4 — extend the SESSION LOG block (operational hook)

Add one field to the canonical block at lines 139–148 (and mirror the wording in §6 if a
sample block is shown there). New field, inserted after `Decision/Output`:

```
Belief Update / ROI: {what belief changed + toward which goal; "none" if pure mechanics}
```

The block becomes Date / Topic / Decision-Output / **Belief Update-ROI** / Open Questions /
Next Step. This is the minimal Stage-1 mechanism — no new framework, reuses the existing
every-turn ritual.

### 3. New companion doc: `docs/architecture/intelligence-compounding.md`

Holds the **full long-form** doctrine the user authored, lightly structured to match the
`docs/architecture/` house style (kebab-case filename, matching the repo's renamed-doc
convention visible in git status). Sections to include verbatim/condensed from the essay:

- **One Goal** — zero intelligence loss + continuous compounding; intelligence = Information ×
  Utility (ROI toward a goal).
- **The chain** — `Artifact → Purpose → User Intent → Goal → Economic Value → ROI → Belief
  Update → Future Decisions` (the diagrams).
- **Three permanent checklists** — User: `Think → Decide → Review`; Claude: `Extract → Align →
  Compound`; System: `Capture → Preserve → Reuse`. Plus the Artifact checklist (Metadata /
  Logic / Governance status `Loose|Forming|Frozen|Killed`, confidence `Certain|Likely|
  Possible|Speculative`).
- **7-level intelligence ladder** — what / why / which user thought / which goal / economic
  value / belief to update / how future decisions change.
- **Memory Rule** — remember meaning + purpose + ROI + assumptions + belief updates, never
  artifacts alone. Ties to `C:\Users\Hi\.claude\projects\D--Tradelatest\memory\`.
- **Evolution path** — Stage 1 markdown checklists (today) → … → Stage 7 Unified Intelligence
  Substrate; with the explicit "do not build ontology/graph-DB/n8n early" guardrail.
- **Weekly Alignment Sweep** checklist (code orphans / dead configs / split-brains / event
  lineage / doc drift / new canonical truths) — note it as *aspirational future*, not a
  current mandate, so it doesn't silently become an unmet obligation.

### 4. Register the companion doc (discoverability)

- Add a row to the **§2 doc-map table** in `CLAUDE.md` (the table ending ~line 30, before the
  `assistant_project.md` row) pointing to `docs/architecture/intelligence-compounding.md` with
  a one-line "Covers" blurb.
- Add the same doc to the **README docs map** (the 4-tier map referenced in `README.md`) under
  the architecture tier, consistent with how `goal.md` / `trigger-vocabulary.md` are listed.

---

## Files to modify

| File | Change |
| --- | --- |
| `CLAUDE.md` | New §6.1 (condensed doctrine); §7.4 SESSION LOG block +1 field; §2 table row |
| `docs/architecture/intelligence-compounding.md` | **New** — full long-form doctrine + 3 checklists + evolution path |
| `README.md` | One row in the docs map under the architecture tier |

No code, config, or hash changes. Nothing touches `src/`, production JSON, or governance — so
no re-hash, no promotion, no `ConfigValidator` involvement.

---

## Verification

Doc-only, so verification is consistency + the operational hook, not pytest:

1. **Numbering integrity** — confirm `CLAUDE.md` reads §6 → §6.1 → §7 with no broken
   `per §7` / `§8` / `§12` cross-references (grep for `§7`, `§8`, `§12`, `§6` mentions).
2. **Link resolves** — `docs/architecture/intelligence-compounding.md` exists and both the §2
   table link and the README map link point to it (relative paths valid).
3. **SESSION LOG hook live** — the very next response (this plan's own log entry, and every
   one after) includes the new `Belief Update / ROI` line, proving the mechanism fires.
4. **Memory-save rule exercised** — a durable belief from this work is written as a memory
   file with an index line in `MEMORY.md` (e.g. a `project`-type note recording that the
   Intelligence Compounding Doctrine was frozen, and *why* — meaning, not just the artifact).
5. **No convention break** — doctrine introduces no new pattern in `src/`, adds no magic
   numbers, skips no gate; it is advisory orchestration only (consistent with §12 trigger
   doctrine that triggers grant no new authority).

---

## Open flags (non-blocking)

- **§6.1 collision risk** with the off-branch "Topic Sync Mandate §6.1" — if that ever merges
  into `patch`, renumber one to §6.2. Called out so it's a known, not a surprise.
- The Weekly Alignment Sweep is documented as **future intent**, not a new per-response
  mandate — adding it as a hard obligation now would itself create the "complicated framework
  too early" failure mode the user named.
