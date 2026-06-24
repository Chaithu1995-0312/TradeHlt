# SESSION LOG archive

Older `📝 SESSION LOG ENTRY` blocks spilled out of the live
[`assistant_project.md`](../../../assistant_project.md) to keep that always-referenced file
bounded (CLAUDE.md §6 / the #3 context-ceiling). **Nothing is deleted** — this is the
forensic-replay record; the live file keeps only the newest ~20 entries.

- Produced by [`scripts/maintenance/rotate_session_log.py`](../../../scripts/maintenance/rotate_session_log.py).
- One `session-log-<oldest>_to_<newest>.md` file per rotation run, newest-first within each.
- Durable conclusions are already distilled into [`docs/current-findings.md`](../../current-findings.md)
  and the memory files; this archive exists for full audit-trail replay, not daily reading.
- Fits the §6.2-rule-5 split: `docs/analysis/` is point-in-time history, not living truth.
