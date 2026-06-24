# Topic: Context Report

> **Topic-visibility unit.** Read this to understand the Context Report feature — what code it
> covers, how it's reached, what tests it, what's still open — without loading the rest of the
> codebase.
>
> Created: 2026-06-01 · Updated: 2026-06-01 · Status: living

## In plain language
Context Report is the 🧠 button next to a finished run in the control-plane UI. Click it and the
system gathers everything about that run — the command line, the last chunk of stdout/stderr,
the artifacts it produced, and (the clever part) the **actual Python functions that ran** — and
asks Claude to explain, in structured form, *why the run did what it did* and *what to do next*.
It is an **operational-intelligence engine, not a chatbot**: one call in, one structured JSON
out. The LLM here is advisory — it reads the run, it does not change anything.

## Code covered
- [`src/control_plane/code_context_extractor.py`](../../src/control_plane/code_context_extractor.py) — pure-stdlib **AST** extractor. `extract_code_context()` ([`:94`](../../src/control_plane/code_context_extractor.py)) returns up to 8 code blocks most relevant to a run, in priority order: (1) functions hit at exact traceback line, (2) all top-level symbols of the main script, (3) remaining traceback-file symbols. Helpers `_find_script_path()` ([`:28`](../../src/control_plane/code_context_extractor.py)), `_ast_symbols()` ([`:57`](../../src/control_plane/code_context_extractor.py)), `_symbols_hitting_line()` ([`:89`](../../src/control_plane/code_context_extractor.py)).
- [`src/control_plane/context_report.py`](../../src/control_plane/context_report.py) — `ContextReportAPI.context_analysis()` ([`:162`](../../src/control_plane/context_report.py)) builds the prompt, calls Claude, parses structured JSON. `_build_prompt()` ([`:65`](../../src/control_plane/context_report.py)) assembles RUN METADATA / STDOUT / STDERR / ARTIFACTS / EXECUTED CODE CONTEXT under a token budget. `_load_dotenv()` ([`:47`](../../src/control_plane/context_report.py)) reads `ANTHROPIC_API_KEY`.
- [`src/control_plane/server.py:1915`](../../src/control_plane/server.py) — the `POST /runs/{id}/context/report` route: pulls run snapshot + logs + artifacts, splits the cmdline, calls `extract_code_context()` ([`:1926`](../../src/control_plane/server.py)) then `context_api.context_analysis()` ([`:1932`](../../src/control_plane/server.py)). `ContextReportAPI` is wired in `ControlPlaneServer.__init__` ([`server.py:1995`](../../src/control_plane/server.py)).
- [`ui_kits/control_plane/LauncherPanel.jsx:309`](../../ui_kits/control_plane/LauncherPanel.jsx) — the 🧠 icon button; [`InspectorPanel.jsx:279`](../../ui_kits/control_plane/InspectorPanel.jsx) renders the report; [`realApi.js:196`](../../ui_kits/control_plane/realApi.js) `contextReport(runId)` does the fetch.

## Ins / Outs
- **Ins:** `run` dict (command_id, status, exit_code, args, command_line), `logs` (stdout/stderr), `artifacts` (path/exists/size list), and the derived `code_context` (AST symbol blocks). `ANTHROPIC_API_KEY` from `.env`/env.
- **Outs:** `{"ok": True, "sections": {root_cause, architecture_notes, artifact_analysis, recommendations[]}, "model", "code_context_count"}` — or `{"ok": False, "error": ...}`. Model: `claude-haiku-4-5-20251001`, `max_tokens=1024`, `temperature=0.1`.

## Entry points & validations
- **Reached via:** control-plane HTTP route `POST /runs/{run_id}/context/report` ([`server.py:1915`](../../src/control_plane/server.py)), triggered by the 🧠 button. Localhost-only (no auth/TLS — `CLAUDE.md §4`).
- **Validated by:** optional-import guard on `anthropic`; missing-key and API-error paths return `{"ok": False}`; non-JSON LLM output falls back to raw text in `root_cause` with a `parse_warning`. No run state is mutated — read-only over run artifacts.

## Tests
- None yet — no `tests/test_context_report*.py` exists. **Gap** (see Discussion → Need more info).

## Fits in architecture
Sits in the **control plane** (the stdlib HTTP surface, `CLAUDE.md §3.3`), downstream of any run
the launcher executes. It is an instance of the **LLM-is-advisory** principle
([`docs/architecture/llm-governance-layer.md`](../architecture/llm-governance-layer.md)): the
model reads execution context and advises; it never re-enters the decision spine. This topic is
the **model/precedent** for the planned Topic Report (see Discussion → Enhancements).

## Discussion (filled in-session)
- **Risks:** `2026-06-01` LLM advisory output could be mistaken for ground truth by an operator; it's haiku at temp 0.1 over truncated logs (3000/1500 chars) — root-cause can miss earlier failures scrolled out of the tail.
- **Challenges:** `2026-06-01` AST extractor only sees the *main script* top-level symbols + traceback-hit functions; deeply nested helper calls with no traceback are invisible to the report.
- **Blockers:** `2026-06-01` none.
- **Ambiguities:** `2026-06-01` an earlier mental model called this "AST dependency check + reuse + confidence score" — that does **not** exist in the code; the real feature is run-context analysis with no confidence score. Recorded so the misconception isn't reintroduced.
- **Enhancements:** `2026-06-01` generalize `extract_code_context()` from run→**topic** to power a "Topic Report" button (the planned next phase) that writes `docs/topics/<topic>.md` directly.
- **Need more info:** `2026-06-01` should this feature have test coverage? No test asserts the prompt shape or the JSON-fallback path today.
