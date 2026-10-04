# Current Findings Index (thin, always-loaded)

> **This is the thin always-loaded view of the repo's current conclusions.** It is a **generated
> view** — do **not** hand-edit the F-list below into existence. The authoritative record is the
> living [`docs/current-findings.md`](current-findings.md).
>
> **Discipline (`test_current_findings.py`):** every non-terminal F-id must appear in **both**
> the living doc and this index. When a session validates / overturns a conclusion it edits
> **`docs/current-findings.md`** (never deletes; marks `SUPERSEDED`/`RETIRED`), then regenerates
> this index to match.
>
> **Regenerate (from repo root):**
>
> ```bash
> python scripts/findings/export_findings_index.py --out docs/current-findings-index.md
> ```
>
> **Why it exists (CLAUDE.md §6.2 / Claude-deepseek.md §6):** cold-start sessions load this token-light
> index instead of the full record, so they know which conclusions exist to retrieve without
> re-running settled investigations or trusting a stale audit claim. Full evidence, dates,
> confidence, and reversal history stay in the living doc.

---

## Index — F-id → one-line conclusion (generated)

> Populated on next `export_findings_index.py` run from `docs/current-findings.md` (currently
> **F-001…F-100**, `Certain | Likely | Possible`, statuses `VALIDATED | OPEN | DURABLE |
> SUPERSEDED | RETIRED`).

| F-id | Type | Conclusion | Confidence | Status |
|---|---|---|---|---|
| _(generated)_ | — | see `docs/current-findings.md` (authoritative) | — | — |

---

## How to use

1. **Orient (P1):** scan this index to know the settled-conclusion surface before planning.
2. **Retrieve (P3):** for the evidence behind any F-id, query RAG / open the living
   [`docs/current-findings.md`](current-findings.md) block for that F-id — never reason from
   the one-line summary alone.
3. **Never** treat a summary line as authority; the row's `Evidence` + `Revalidate-by` do.
4. If a claim contradicts a finding here, that is a **§6 TruthConflict** — flag it, cite both,
   do not silently pick a winner.