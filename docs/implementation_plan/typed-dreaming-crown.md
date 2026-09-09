# Plan — install the `/insights` harness suggestions (hooks, skills, DuckDB MCP)

## Context

The `/insights` report proposed a SessionStart preflight hook, a PostToolUse lint hook, two custom
skills, and a DuckDB MCP server. The user asked for all of it. Verified against this machine first
(per the §1.1 discipline installed earlier today) — **the supplied config is broken in four ways and
carries one governance hazard**, so it cannot be pasted in as written:

| # | As supplied | Verified on this machine |
|---|---|---|
| 1 | `./.venv/bin/python` | Windows uses `Scripts/python.exe`; and `.venv` is the Python 3.14 venv with **no pytest**. `venv` (3.12.10) is the working one. |
| 2 | `ruff check --fix` | **ruff is not installed** in either venv or on PATH; no ruff/black/flake8/mypy config exists in the repo. |
| 3 | `$CLAUDE_TOOL_FILE_PATH` | **Not a real hook variable.** Hooks receive JSON on **stdin** (`.tool_input.file_path` / `.tool_response.filePath`). `$f` would be empty and the `case` would silently no-op. |
| 4 | (documented `jq` extraction) | **jq is not installed** — extraction must go through Python. |
| 5 | `--fix` rewrites files | It mutates source *after* every Edit/Write. This repo's claims rest on byte-parity and freeze-pins; a silent reformat can invalidate a parity proof after the fact. |
| 6 | `uvx mcp-server-duckdb --db-path ./data/corpus.duckdb` | **uv/uvx not installed, duckdb module not installed, `data/corpus.duckdb` does not exist.** 38 parquet files exist, but under `logs/` and `results/`. |

Intended outcome: the two hooks and two skills live as tracked files that actually run, and the
DuckDB MCP server is stood up against the parquet corpora that really exist.

**User decisions (this turn):** PostToolUse = read-only syntax check, no mutation · DuckDB = install
and wire up · files = new `.claude/settings.json` + `.claude/skills/`, force-added.

## 1. Hooks → new `.claude/settings.json`

No `.claude/settings.json` exists (only a 14 KB tracked `settings.local.json` holding permissions).
Create it with hooks only; do not touch `settings.local.json`.

**SessionStart** — worktree preflight, the one that addresses the real recurring failure (dirty tree
or wrong interpreter invalidating a measurement run):

```
echo '--- WORKTREE PREFLIGHT ---'; git rev-parse --abbrev-ref HEAD; git status --porcelain | head -40; echo '--- PY ---'; venv/Scripts/python.exe -c "import sys; print(sys.prefix)"
```

`git stash list` added per the original suggestion. `head -40` matters: this tree carries 1,000+
untracked paths (F-071).

**PostToolUse** (`matcher: "Edit|Write"`) — read-only syntax check. No jq (absent), no ruff
(absent), no mutation:

```
venv/Scripts/python.exe -c "import sys,json,py_compile; d=json.load(sys.stdin); f=(d.get('tool_response') or {}).get('filePath') or (d.get('tool_input') or {}).get('file_path') or ''; sys.exit(0) if not f.endswith('.py') else py_compile.compile(f, doraise=True)" 2>&1 | tail -5
```

Add `"timeout": 15` and a `statusMessage`. Wrap with `|| true` **only after** the pipe-test passes.

**Verification for each hook (the update-config ritual, non-negotiable — a silently-dead hook is
worse than none):**
1. Pipe-test raw: `echo '{"tool_name":"Edit","tool_input":{"file_path":"src/features/candle_math.py"}}' | <cmd>` — expect exit 0 and no output; then against a deliberately broken temp .py — expect a SyntaxError line.
2. Schema check: `python -c` JSON parse of `.claude/settings.json` (jq is absent), asserting `hooks.PostToolUse[0].hooks[0].command` reads back.
3. Prove it fires: temporarily prefix with `echo "$(date) fired" >> <scratchpad>/hook-check.txt;`, trigger one Edit, read the sentinel, then **strip the prefix**.
4. If it does not fire despite 1–2 passing, the settings watcher was not watching `.claude/` at session start — tell the user to open `/hooks` or restart. I cannot do that myself.

## 2. Skills → `.claude/skills/<name>/SKILL.md`

Both as supplied, with repo-specific corrections folded in (`.claude/skills/` does not exist yet):

- **`verify-claims`** — content as given. Add one line pointing at the existing grounding tool rather than inventing a new mechanism: `python scripts/governance/query_semantic_os.py --ground --kind ...` (CLAUDE.md §6.7), and note that a claim resting on a session summary or another model's analysis is STALE by default (§1.1).
- **`commit-batch`** — content as given, plus three facts this repo has already paid for: never `git add -A` (~15 concurrent Claude sessions write here); the pre-existing baseline command is `python scripts/maintenance/check_governance_invariants.py --all` (currently **14 failed / 521 passed** on `feature/truth-registry-v2`); and the `commit-msg` hook needs a same-day SESSION LOG entry or `[nolog]`.

## 3. DuckDB MCP server

Nothing here exists yet, so build it in order and stop at the first failure:

1. `venv/Scripts/python.exe -m pip install uv duckdb` — puts `uvx.exe` in `venv/Scripts/` (no admin, no winget).
2. **Verify the package before registering it** — `venv/Scripts/uvx.exe mcp-server-duckdb --help`. The package name is **UNVERIFIED** (came from the report, not checked against a registry). If it does not resolve, stop and report rather than registering a server that fails on first use.
3. Create `data/corpus.duckdb` with **views, not copies** — `/data/*` is already gitignored, so the DB stays untracked automatically and `results/clean_labels` (1.2 GB) is never duplicated. Hive-partitioned trees need `read_parquet('<dir>/**/*.parquet', hive_partitioning=1)`:
   - `bar_structure` → `logs/bar_structure/XAUUSD_bar_structure.parquet` (partitioned by `crt_state_after`)
   - `opportunities` → `logs/XAUUSD/xauusd_phase1_20260723/opportunities.parquet`
   - `clean_labels` → `results/clean_labels/XAUUSD/20260723T083443Z/clean_labels.parquet`
   - `crt_telemetry` / `events` → `results/research/_spine_entries/XAUUSD__v2_multi_2026_04/run_20260822_162108_XAUUSD/` (partitioned by `kind` / `event`)
   - `high_acceptance*` (3), `zone_x_*` (2), `mother_range_ledger`
   - Skip `results/research/hypothesis_parquet_revalidation/_tmp/` — temp files.
4. Register with an absolute uvx path, read-only if the server supports it: `claude mcp add duckdb -- D:/Tradelatest/venv/Scripts/uvx.exe mcp-server-duckdb --db-path D:/Tradelatest/data/corpus.duckdb`.
5. Smoke test one query and report the row count.

**Scope caveat to state, not bury:** the repo's own measured finding is that gzip beat Parquet on
`crt_telemetry` and the query win tracks row *width*, not file size. This adds a query surface; it
does not make the corpus more trustworthy, and the DB is an ungoverned derived store — read-only by
preference, never an evidence source for a finding.

## 4. Tracking (the F-071 lesson)

`.gitignore:56` ignores `.claude` wholesale, yet `.claude/settings.local.json` is tracked — so new
files under `.claude/` are invisible to any other clone unless force-added.

- `git add -f .claude/settings.json .claude/skills/verify-claims/SKILL.md .claude/skills/commit-batch/SKILL.md`
- Propose (do **not** apply without approval) narrowing `.gitignore:56` from `.claude` to
  `.claude/worktrees/`, so config stops being silently ignored. This is a governed-file edit.
- Do not stage `data/corpus.duckdb` — already covered by `/data/*`.

## Files

- `.claude/settings.json` (new) · `.claude/skills/{verify-claims,commit-batch}/SKILL.md` (new)
- `data/corpus.duckdb` (new, untracked derived artifact)
- `assistant_project.md` — append the §6/§7.4 SESSION LOG entry
- Not touched: `.claude/settings.local.json`, `CLAUDE.md`, any `src/` or config path

## Verification

1. Hooks: the 4-step ritual above (pipe-test → JSON schema read-back → sentinel proof → cleanup).
2. Skills: `/verify-claims` and `/commit-batch` appear in the skill listing; invoke `verify-claims` once on a trivial claim and confirm it produces the table and stops.
3. DuckDB: `uvx mcp-server-duckdb --help` resolves; one `SELECT count(*)` through the MCP tool returns a real row count from `bar_structure`.
4. Nothing else regressed: `venv/Scripts/python.exe -m pytest -q tests/test_session_log.py` and confirm `git status --porcelain` shows only the intended new paths.
