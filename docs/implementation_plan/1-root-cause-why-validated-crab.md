# Agent Session Economy — measured best practices

## Context

A recent agentic session ran 1h13m / 25.5k tokens, and the standing full-suite command
(`venv/Scripts/python.exe -m pytest tests/ -q ... | tail -40`) was reported as "causing issue."
Rather than accept the generic "cumulative context inflation" diagnosis, this plan is grounded in
measurements taken against this repo on 2026-07-23. Two of the assumed causes turned out to be
wrong, and the two dominant real causes were not in the original analysis at all.

### What was measured

**Fixed per-session context floor (re-sent on every inference):**

| Artifact | Size | ~tokens |
|---|---|---|
| `CLAUDE.md` (auto-loaded) | 93 KB | ~23k |
| `MEMORY.md` index (auto-loaded) | 19 KB | ~5k |
| **Floor before the user types** | **112 KB** | **~28k** |

The documented cold-start ritual makes it far worse: `docs/architecture/trigger-vocabulary.md:16-30`
directs a fresh session to read `docs/current-findings.md` (210 KB, ~52k tok), and the CLAUDE.md
model-registry table says `active_models.yaml` (78 KB, ~20k tok) is "loaded first in every session."
**A session obeying the written ritual spends ~100k tokens before doing any work.**

**Full-suite runtime (measured, not estimated):** `7,983.88s = 2:13:03`;
73 failed / 3,900 passed / 25 skipped / 2 xfailed.

| Slice | Time | Share |
|---|---|---|
| Top 6 tests | 6,443s | **80.7%** |
| Top 25 tests | 7,492s | 93.8% |
| Remaining 3,975 tests | **492s** | 6.2% |

The three `tests/runtime/test_replay_determinism.py` tests alone are 3,943s (**49.4%**). Three of the
top six are *fixture setup* time — full backtests inside fixtures, billed to whichever test touches
them first.

### Corrections to the original diagnosis

- **"cp1252 UnicodeEncodeError debugging"** — real, and *structural*: `.claude/settings.local.json`
  has no `env` block, so `PYTHONIOENCODING` is unset every session. Not bad luck; recurring by
  construction.
- **Network/MT5 hangs** — NOT a cause. `tests/test_llm_connectivity.py` fully mocks `urlopen`; no
  unguarded network/MT5/Playwright call exists in the suite. Ruled out by inspection.
- **`-p no:randomly`** — a no-op. `pytest-randomly` is not installed or configured.
- **Turn-count context accumulation** — real but *secondary here*. The ~28k fixed floor multiplied
  by turn count dominates the incremental tool-output growth.

### Intended outcome

Cut the two dominant costs (context floor, test wall-clock) without weakening any governance gate.
Every change below is additive or config-level; none removes a check.

---

## Tier 1 — Harness fixes (mechanical, no doctrine)

**1. Kill the encoding loop at the source.** Add an `env` block to `.claude/settings.local.json`:
`PYTHONIOENCODING=utf-8` (and `PYTHONUTF8=1`). This removes an entire recurring failure class that
currently costs ~3 turns whenever it fires. Complements — does not replace — `src/utils/console_safe.py`,
which stays the rule for production CLI output per `docs/reference/conventions.md:271`.

**2. Rebuild the permission allowlist.** The 130 `allow` entries are archaeology — one-off
`mv Backup/Codebase_Backup1.zip …` lines from a 2026-06 file reorg. Almost none cover the recurring
read-only commands, so prompts still fire. Use the existing `/fewer-permission-prompts` skill to
regenerate from actual transcript history rather than hand-writing entries.

**3. Pin one interpreter.** The allowlist shows four in rotation (`python`, `py -3.11`,
`venv/Scripts/python.exe`, a hardcoded `Python312\python.exe`). `venv/Scripts/python.exe` is the one
that works (already recorded as a GOTCHA in `project_feature_lineage_candle_math.md`). State it once
in the harness config so it stops being rediscovered.

**4. Set `addopts` in `pyproject.toml` `[tool.pytest.ini_options]`.** Currently absent, so bare
`pytest` emits full tracebacks for 73 pre-existing failures. Add `--tb=short --no-header -q`.

## Tier 2 — Test wall-clock (the 2:13 → ~8 min lever)

**5. Mark the top-6 heavyweights `@pytest.mark.slow`.** The marker is already declared in
`pyproject.toml` but used in only one file (`tests/research/test_trace_corpus.py`). Apply it to:
- all three in `tests/runtime/test_replay_determinism.py`
- `tests/test_historical_zone_mapper_corpus_parity.py::test_corpus_parity_mapper_vs_engine_runner_zone_stage`
- `tests/research/test_xauusd_spine_smoke.py::test_spine_collect_runs_on_frozen_candidate_without_active_version_drift`
- `tests/analytics/test_metrics_oracle_parity.py::test_trade_count_parity`

**6. Document a two-lane convention in `docs/reference/testing.md`** (existing doc — §6.2 rule 1):
- *fast lane* `pytest tests/ -m "not slow"` — ~8 min, for iteration
- *full lane* `pytest tests/` — 2:13, unchanged, **required before promotion**

**Do NOT** put `-m "not slow"` in `addopts`. These are determinism and byte-identity proofs — the
governance backbone. Default behavior must stay full; the fast lane is opt-in. This is the
`§6.5 Authority Ladder` distinction: a faster loop earns *convenience*, never *authority*.

**7. Scope collection away from the nested worktree.** `.pytest_cache` recorded 4,241 nodeids
including `.claude/worktrees/wizardly-neumann-923c0e/tests/` — a second repo copy, contributing 2 of
the cached failures. Add `norecursedirs = [".claude", "venv"]`.

## Tier 3 — Context budget

**8. Fix the cold-start recipe** in `docs/architecture/trigger-vocabulary.md:16-30`. Replace "read
`docs/current-findings.md`" (210 KB) with "read the Repository Truths Index table already inlined in
CLAUDE.md; open `docs/current-findings.md` only for a specific F-id." The index exists precisely so
the full doc need not be loaded — the ritual currently defeats its own purpose.

**9. Resolve the plan-directory ambiguity.** Cold-start says `docs/plans/*.md` (68 files); CLAUDE.md
§12 `Continue` says `docs/implementation_plan/*.md` (97 files). Both exist and both are live. Name
one as authoritative in both places.

**10. Correct the `active_models.yaml` claim.** CLAUDE.md calls it "Loaded first in every Claude
session" (78 KB). It is not auto-loaded and should not be — reword to "read when the task touches
model intent," matching how every other row in that table is scoped. `DOC_DRIFT` per §6.2 rule 2.

---

## Files to modify

| File | Change |
|---|---|
| `.claude/settings.local.json` | add `env` block; regenerate `permissions.allow` |
| `pyproject.toml` | `addopts`, `norecursedirs` under `[tool.pytest.ini_options]` |
| `tests/runtime/test_replay_determinism.py` + 3 others | add `@pytest.mark.slow` |
| `docs/reference/testing.md` | document the two lanes |
| `docs/architecture/trigger-vocabulary.md` | fix cold-start reading list + plan dir |
| `CLAUDE.md` | fix `active_models.yaml` row + §12 plan dir |

Doctrine home: `docs/governance/AGENT_SESSION_ECONOMY.md` (long form) + a ~6-line CLAUDE.md pointer.
A full inline section would add several KB to the very floor this plan is cutting.

## Verification

1. **Encoding** — `venv/Scripts/python.exe -c "print('✓ ──')"` succeeds without
   `UnicodeEncodeError`.
2. **Fast lane** — `venv/Scripts/python.exe -m pytest tests/ -m "not slow" -q` completes in ~8 min
   and reports **3,994 selected / 6 deselected**.
3. **Full lane unchanged** — `pytest tests/` still selects 4,000 and still runs the six proofs. The
   pass/fail set must be **identical to this baseline (73F/3900P/25S/2X)**; marking a test must not
   change its outcome.
4. **Worktree excluded** — `pytest tests/ --collect-only -q | tail -1` shows no
   `.claude/worktrees/` node.
5. **Docs** — `pytest tests/test_doc_citations.py tests/test_topic_docs.py tests/test_current_findings.py -q`
   green (the §6.3/§6.4 mandates).

## Out of scope

The **73-vs-59 failure delta** is unexplained. The cached run had different scope (it swept the
worktree), so the two numbers are not directly comparable. This plan deliberately treats the 73 as a
frozen baseline to verify against, and does not attempt to fix or explain any of them — that is
separate work, and several are governance freshness checks (`test_geometry_census`,
`test_feature_layer_freeze`) that likely reflect the modified working tree, not real regressions.
