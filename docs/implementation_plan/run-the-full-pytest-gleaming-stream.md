# Full-suite triage run — measurement only

## Context

You asked for a full pytest run, root-cause clustering, and a fleet of worktree agents that fix
each cluster and commit. Exploration turned up four facts that made the fix-and-commit half
untrustworthy on this repo, and you chose **measurement only** in response:

1. **A `/tmp` worktree would measure the wrong code.** 92 test files under `tests/` are untracked
   and 131 are modified (223 of 534 on disk = 42% differ from HEAD); 103 `src/` paths are dirty.
   `/data/*` is fully gitignored (`git ls-files data/` = 0), so a fresh worktree has an empty
   corpus. Reproduction and "no regressions" checks inside it would both be measuring something
   other than the system you run.
2. **The failure population is governance ratchets, not ordinary bugs.** The last full run's 35
   failures are dominated by freshness / golden / byte-identical / hash-match checks (geometry
   census, findings export "not hand-edited", flow-graph manifests, reachability golden,
   layer-audit manifest). CLAUDE.md §1.1 and §1.5 say a pre-existing red is to be **reported, not
   fixed ad hoc** (F-018, E-001F), and §6.2 rule 3 gates regenerating a governed artifact behind
   your approval because it can silently flip a registered finding.
3. **The machine is crowded.** 13 `claude.exe` processes and 12 existing worktrees are live
   against this repo right now. 74 test files write into `logs/`, `results/`, `reports/`.
4. **No JSON plugin exists.** pytest 9.0.3 with no `pytest-json-report` and no `pytest-xdist`.

**Outcome intended:** one trustworthy, timestamped measurement of the working tree, with every
failure assigned to a root-cause cluster and a proposed remedy, written to
`reports/test_triage.json` — so you can decide what gets fixed, rather than having agents decide
by regenerating governed artifacts.

**Not in scope (your call):** no worktrees, no fix agents, no commits, no artifact regeneration.
So the final summary will carry **no commit SHAs** — "fixed" is empty by construction.

---

## Step 1 — Preflight and record the measurement basis

The repo's §1.5 Working Tree Preflight, recorded *into the report* rather than just echoed —
this repo has been burned by results whose basis was never written down (F-083).

- `git rev-parse HEAD`, `git status --porcelain | wc -l`, `git stash list`
- `venv/Scripts/python.exe -c "import sys; print(sys.prefix)"` → must be `D:\Tradelatest\venv`
  (**not** `.venv`, which is Python 3.14 with no pytest)
- Count tracked / modified / untracked under `tests/` and `src/`

State plainly in the report: **this run measures the WORKING TREE at timestamp T, not HEAD**, and
13 other sessions can write to that tree mid-run. That caveat is part of the result, not a footnote.

## Step 2 — JSON-emitting pytest plugin (no install)

Write a small plugin to the **scratchpad**, not the repo — keeps it out of SITS registration
(§3.1b applies to `scripts/**` and repo-root `*.py`) and out of everyone else's tree:

`<scratchpad>/pytest_json_emit.py`, loaded via `PYTHONPATH=<scratchpad>` + `-p pytest_json_emit`.

Hooks and fields:
- `pytest_runtest_logreport` — capture on failure/error: `nodeid`, `file`, `lineno`, `when`
  (setup/call/teardown), `outcome`, `duration`, full `longrepr` text, exception class, and the
  final assertion/error line (the clustering key).
- `pytest_collectreport` — **collection errors produce no test report** and would otherwise vanish.
  Import failures from the dirty tree are an expected and important cluster.
- `pytest_sessionfinish` — totals, duration, and atomic write of the raw JSON.

Raw output → `<scratchpad>/pytest_full_report.json`. Console tee → `<scratchpad>/pytest_full_run.log`.

## Step 3 — Run the full suite once, in background

```
venv/Scripts/python.exe -m pytest -p pytest_json_emit --json-out=<scratchpad>/pytest_full_report.json -q
```

- **Background, single run.** Last measured 1:04:28 (35 failed / 3,284 passed / 33 skipped); the
  suite has grown since, so budget longer.
- No `-x`, no `-k` — the whole population is the point.
- Owner-gated markers `shadow_economic` / `capital_micro` are **not** deselected: `pyproject.toml`
  sets no default `-m` filter, so a bare run is what "the full suite" means here. If either turns
  out to hit real capital or a live broker, I stop and report rather than proceeding.
- No repo files written by me; tests themselves write into `logs/`/`results/` as they always do.

## Step 4 — Cluster by root cause

Assign every failure by its **actual traceback signature**, not by filename. Starting taxonomy,
drawn from the July run — revised against what this run actually produces:

| Cluster | Signature | Likely disposition |
|---|---|---|
| `stale_governed_artifact` | freshness / golden / byte-identical / hash-match assertions | report-only (§6.2 gate) |
| `config_split_brain` | prod config missing keys a test requires (F-018 class) | genuinely-broken-upstream |
| `feature_math_lint` | `feature_math_lint.py` ownership reds | report-only |
| `doc_citation_drift` | `test_doc_citations.py` ±30-line window | mechanical, low risk |
| `session_log_contract` | session-log / "cites report" assertions | mechanical |
| `collection_error` | import fails before any test runs | genuine or environment |
| `missing_corpus` | test needs a `data/` file absent on disk | environment-only |
| `missing_optional_dep` | pyarrow / MetaTrader5 / mplfinance / websockets guards | environment-only |
| `genuine_logic_bug` | real assertion on computed values in `src/` | genuine |

For each cluster record: member nodeids, the shared root cause **in one sentence**, blast radius
(files a fix would touch), the exact remediation command if one exists (e.g.
`python scripts/governance/export_findings.py`), and whether remediation would regenerate a
governed artifact — the flag that decides whether it needs your approval.

Where a cluster's cause is not decidable from the traceback alone, it is labelled `UNVERIFIED`
rather than guessed (§1.1). I will read source to resolve what I can, but I will not invent a
root cause to make the board look complete.

## Step 5 — Write `reports/test_triage.json`

Note: `/reports/*` is gitignored, so this lands untracked — which is correct for a run artifact.

```jsonc
{
  "measurement_basis": {
    "timestamp": "...", "head_sha": "...", "branch": "feature/truth-registry-v2",
    "working_tree_dirty_paths": 816, "tests_untracked": 92, "tests_modified": 131,
    "interpreter": "D:\\Tradelatest\\venv", "concurrent_sessions_observed": 13,
    "caveat": "measures WORKING TREE, not HEAD; tree is shared with live sessions"
  },
  "totals": { "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "duration_s": 0 },
  "clusters": [
    {
      "id": "stale_governed_artifact",
      "status": "REPORT_ONLY",           // REPORT_ONLY | ACTIONABLE | ENVIRONMENT | UNVERIFIED
      "category": "stale-artifact",       // genuine | stale-artifact | environment | upstream
      "root_cause": "one sentence",
      "members": ["tests/...::test_x"],
      "blast_radius": ["path/a.py"],
      "remediation_command": "python scripts/... ",
      "regenerates_governed_artifact": true,
      "needs_user_approval": true,
      "evidence": "tests/...::test_x — AssertionError: ..."
    }
  ],
  "unclustered": []
}
```

## Step 6 — Summary

Single report in the terminal, in your three buckets:

- **fixed** — empty, by your measurement-only decision (stated, not silently omitted)
- **genuinely-broken-upstream** — real defects, with the cluster that owns each
- **environment-only** — missing corpus / optional deps / interpreter
- plus **stale-governed-artifact**, which is the fourth bucket this repo actually needs and the
  one that likely holds the plurality of failures

No commit SHAs — nothing is committed.

## Step 7 — Session log (§6, non-optional)

Append the `📝 SESSION LOG ENTRY` block to `assistant_project.md` (codebase log — this is
engineering on the trading system, not workflow). Includes the `Belief Update / ROI / Goal` line.

---

## Verification

- Plugin correctness before trusting the big run: exercise it on one known-red file
  (`venv/Scripts/python.exe -m pytest -p pytest_json_emit tests/test_geometry_census.py`) and
  confirm the JSON's failure count matches pytest's own tail line.
- Cross-check the full run: `totals` in `reports/test_triage.json` must equal the pytest summary
  line in `pytest_full_run.log`. A mismatch means the plugin dropped reports — I say so rather
  than shipping the board.
- Conservation check: `sum(len(cluster.members)) + len(unclustered) == failed + errors`. Every
  failure is either in a cluster or explicitly unclustered; none silently disappear.
- Spot-verify two clusters by re-running their members directly and confirming the same traceback.

## Deferred: the fix phase, if you later want it

Recording your stated preference so it isn't re-derived: fix agents would get isolated trees from
a **snapshot of the working tree** — build a commit object via a temp `GIT_INDEX_FILE` (never
touches the real index or HEAD, so it is safe alongside the 13 live sessions), place it on a
scratch ref, branch each `/tmp` worktree from that, and junction `data/` `models/` `logs/` in.
Each agent re-runs its own cluster plus one final full run at the end, not a full run apiece.
`core.hooksPath` is active, so any `src/**` commit needs a same-day SESSION LOG entry or `[nolog]`.
