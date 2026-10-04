# Fix 6 stale doc citations (CLAUDE.md §6.3 Citation Sync)

## Context
`tests/test_doc_citations.py::test_every_code_citation_resolves` is RED. The test
(`tests/test_doc_citations.py`) scans mapped docs for dual-form `path:line · Symbol`
citations and asserts the symbol sits within ±30 lines of the cited line. Six citations
drifted because code moved underneath them. The fix is purely mechanical "code moved,
docs didn't" — update each cited line number to the symbol's current location (and
normalize/qualify two ambiguous paths). **Doc-only; no code changes.** `docs/` is
gitignored on `patch`, so edits live on disk only — expected.

Live locations confirmed via grep + the test's own DRIFT report.

## Edits

**1. `docs/current-findings.md:98`** (F-004 Evidence) — keep conclusion, fix line only.
- `crt_engine_v2.py:1805 · bitnet_main_score` → `:1756` (the `if bitnet_main_score < 0.55:`
  line the prose quotes; symbol cluster is 1749–1757).
- Leave the same line's `:363 · bitnet_main_threshold` untouched (not regex-matched, not flagged).

**2. `docs/architecture/entry-exit-map.md:29`** (Live tick row)
- `src/runtime/live_engine_hook.py:590 · process` → `:523` (`def process(` is at line 523).

**3. `docs/architecture/entry-exit-map.md:46`** (Config promotion row)
- `src/governance/promotion_manager.py:583 · _write_to_registry` → `:499` (`def _write_to_registry` at 499).
- Leave the same line's `:723 · _log_event` untouched (not flagged).

**4. `docs/architecture/entry-exit-map.md:62`** (load-bearing caveat prose)
- `live_engine_hook.py:590 · process` → `src/runtime/live_engine_hook.py:523 · process`
  (fix line AND add the `src/runtime/` prefix to normalize the bare basename).

**5. `docs/topics/ai-automation-agent.md:21`** (AMBIGUOUS — two `cli.py` exist)
- `cli.py:49 · main` → `src/agent/cli.py:49 · main` (line 49 is already correct; just qualify
  the path to the agent CLI, disambiguating from `src/research/cli.py`).

**6. `docs/topics/crt-spine.md:20`** (two citations on this line)
- `crt_engine_v2.py:1099 · VALID_TRANSITIONS` (enforcement) → `:1050` — this is the RED one.
- `crt_engine_v2.py:1074 · VALID_TRANSITIONS` (the def) → `:1025` — currently passes the
  window but is inaccurate; refresh while here (def is at 1025).

## Optional accuracy fix (not test-enforced)
**`CLAUDE.md §4`** CRTState bullet cites `VALID_TRANSITIONS` (`crt_engine_v2.py:981`). This is
the symbol-before-path form, so the test regex does NOT match it (not RED). The line is stale
(def now at 1025). Refresh `:981` → `:1025` for accuracy. Doc-only, low risk.

## Verification
```
python -m pytest tests/test_doc_citations.py -q
```
Expect `2 passed`. (`test_mapped_docs_exist` + `test_every_code_citation_resolves`.)

## Per CLAUDE.md §6: append the SESSION LOG ENTRY block to `assistant_project.md` on completion.
