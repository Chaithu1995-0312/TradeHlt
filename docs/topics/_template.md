# Topic: <NAME>

> **Topic-visibility unit.** One concept, narrated in human language, kept in sync with the
> code on every working response (`CLAUDE.md §6.1`). Read this to understand the topic — what
> code it covers, how it's reached, what tests it, what's still open — **without loading the
> rest of the codebase**. Link, don't inline.
>
> Created: YYYY-MM-DD · Updated: YYYY-MM-DD · Status: <stub | living | stable>

## In plain language
<2–5 sentences: what this topic *is* and why it exists. No jargon-first. The "what good
looks like" for this concept.>

## Code covered
<The modules / classes / functions this topic spans, each with a `file:line` citation.
Cross-reference `docs/analysis/codebase-analysis.md` where a module is already analysed.>
- [`module.py:NN`](path/module.py) — `Symbol` — one-line role.

## Ins / Outs
- **Ins:** <data shapes / dataclasses / dict keys consumed; config sections via `get_prod_section(...)`.>
- **Outs:** <return shapes / dataclasses produced; JSONL lines emitted (path + key fields).>

## Entry points & validations
- **Reached via:** <CLI script / control-plane `CommandSpec` id (cite `src/control_plane/registry.py`) / agent tool / HTTP route>.
- **Validated by:** <what proves it end-to-end — gates, replay check, governance APPROVE, etc.>

## Tests
<The `tests/` files that cover this topic — the coverage view.>
- [`tests/test_xxx.py`](tests/test_xxx.py) — what it asserts.

## Fits in architecture
<Where this sits in the bigger picture — link up the tree: `docs/architecture/signal-flow.md`
step, `code-map` node, the service it belongs to. One or two links, not a tour.>

## Discussion (filled in-session)
> Standing parallel-discussion surface. Append dated entries; never delete — supersede.
> This is the open thread for the topic; the next phase may auto-populate it via LLM.

- **Risks:** <YYYY-MM-DD> …
- **Challenges:** <YYYY-MM-DD> …
- **Blockers:** <YYYY-MM-DD> …
- **Ambiguities:** <YYYY-MM-DD> …
- **Enhancements:** <YYYY-MM-DD> …
- **Need more info:** <YYYY-MM-DD> …
