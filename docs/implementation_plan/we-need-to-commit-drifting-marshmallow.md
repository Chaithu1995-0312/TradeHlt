# Commit & Push Plan: grokbotchanges Branch State Assessment

**Date:** 2026-10-01  
**Status:** Plan mode (read-only, no changes made yet)

## Current Branch State

### Branch Ahead of Main
The `grokbotchanges` branch is **19+ commits ahead** of `main`:
- Recent merges from lanes: `lane/entry-chain`, `lane/mc-d0a`, `lane/wp84-ld`
- Recent work: CRT entry-chain fixes, TP1-partial ledger fix, config layer hardening, EPIC-84 wave implementations
- **Note:** All code changes appear to have been committed already

---

## Uncommitted Changes Analysis

### 1. **Modified Files** (Should be Committed)

| File | Status | Size | Notes |
|------|--------|------|-------|
| `.claude/settings.local.json` | Modified | Small | User settings — should be committed |
| `assistant_project.md` | Modified | Large | SESSION LOG — must be committed per §6 mandate |
| `docs/research-readiness/ic-003-shape-narratives.md` | Modified | Large | Documentation update — should be committed |
| `logs/README.md` | Modified | Small | README — should be committed |
| `results/README.md` | Modified | Small | README — should be committed |

**Action:** Stage and commit these 5 files

### 2. **Untracked Files** (Needs Triage)

| File/Folder | Type | Size | Disposition |
|-------------|------|------|-------------|
| `docs/implementation_plan/gather-recent-7-days-ancient-waterfall.md` | Plan doc | ~2.6 KB | **IMPORTANT**: Recent analysis of TP1 partial ledger fix (F-110); should be committed |
| `report.json` | Data | ? | **Check if it's analysis output or gitignore** |
| `results_xau_full_trace.log` | Log | Large | **Should be gitignored** (test/debug output) |
| `results_xau_last_month.log` | Log | Large | **Should be gitignored** (test/debug output) |
| `results_xau_last_month_trace.log` | Log | Large | **Should be gitignored** (test/debug output) |
| `scratch_run_logs/` | Directory | 5K | **Should be gitignored** (debug logs; contains `live_full_*.log`) |

**Action:** 
- Commit: `gather-recent-7-days-ancient-waterfall.md`
- Check: `report.json` — verify if it's analysis output or temporary
- Ignore: `results_xau_*.log` files and `scratch_run_logs/` (add to .gitignore)

---

## Code Already Committed (Verified from Git Log)

The following code changes were **already committed** to recent merges:

### Source Code Changes
- ✅ `src/config_layer/crt_engine_v2.py` — Modified (CRT entry-chain work)
- ✅ `src/runtime/backtest_v2.py` — Modified (entry/SL/TP tracing, TP1 partial fix)
- ✅ `src/config_layer/setup.py` — Modified
- ✅ `src/governance/portfolio_validation.py` — Modified

### Test Files
- ✅ `tests/test_entry_chain.py` — **Added** (new tests for entry-chain logic)
- ✅ `tests/test_tp1_partial_ledger.py` — **Added** (new tests for TP1 partial fix)
- ✅ `tests/test_crt_engine_no_defaults.py` — Modified
- ✅ `tests/test_runtime_missing_keys.py` — Modified

### Configuration Files
- ✅ Multiple production configs modified (v2_htfcrt_2026_08.json, v4_*.json, v5_*.json, etc.)

### Documentation
- ✅ `CLAUDE.md` — Modified
- ✅ `docs/current-findings.md` — Modified (findings updates)
- ✅ `docs/reference/config-reference.md` — Modified
- ✅ `docs/topics/crt-spine.md` — Modified

### Build Queue & Metadata
- ✅ `multi_llm/build_queue.jsonl` — Modified (queue state)
- ✅ `assistant_project.md` — Modified (SESSION LOG entries)

---

## Recommended Commit Strategy

### Batch 1: Documentation & Session Log (Immediate)
```
Files:
  - assistant_project.md
  - docs/research-readiness/ic-003-shape-narratives.md
  - logs/README.md
  - results/README.md
  - docs/implementation_plan/gather-recent-7-days-ancient-waterfall.md

Commit message:
"Session log + implementation plan docs: TP1 partial ledger trace (F-110) and recent analysis docs [nolog]"
```

### Batch 2: Settings (Separate)
```
Files:
  - .claude/settings.local.json

Commit message:
"Update Claude Code settings [nolog]"
```

### Batch 3: Gitignore Cleanup (Optional but Recommended)
```
Action: Add to .gitignore if not already present:
  results_xau_*.log
  scratch_run_logs/
  
Check: report.json — if temporary, add to .gitignore; if analysis output, commit it

Commit message:
"Gitignore: exclude test debug logs and scratch runs"
```

---

## Push Readiness Check

### Pre-Push Verification
- [ ] All source code changes already committed (verified above)
- [ ] No uncommitted code files (`git status` shows no `M` on `src/`)
- [ ] Session log staged and ready (`assistant_project.md`)
- [ ] Test files committed (`test_entry_chain.py`, `test_tp1_partial_ledger.py`)
- [ ] Implementation plan documented (`gather-recent-7-days-ancient-waterfall.md`)

### Tests
- Run: `python scripts/maintenance/check_governance_invariants.py --all` (GREEN_FLOOR)
- Verify no regressions on entry-chain and TP1-partial changes

### No Blocking Issues
- No uncommitted source code
- No staged conflicts
- All merges from lanes already integrated

---

## Summary

| Category | Status | Action Required |
|----------|--------|-----------------|
| **Source code** | ✅ All committed | None — ready to push |
| **Tests** | ✅ All committed | None — ready to push |
| **Docs** | ⏳ 5 files modified, 1 untracked | Commit batch 1 + 2 |
| **Logs/Debug** | ⏳ Untracked logs | Gitignore and/or commit cleanup |
| **Ready to push?** | **Yes, after docs committed** | Commit batches 1 & 2, then push |

---

## Next Steps (After Plan Approval)

1. **Stage & commit batch 1** (documentation)
2. **Stage & commit batch 2** (settings)
3. **Handle batch 3** (gitignore or check report.json)
4. **Run GREEN_FLOOR tests** to verify governance passes
5. **Push to grokbotchanges** with no additional commits

---

## Risks & Notes

- ⚠️ `assistant_project.md` is large and frequently modified — ensure it's clean before committing
- ⚠️ No code changes should be missing; all source code work was merged from lanes already
- ⚠️ `[nolog]` markers in recent commits mean session logs were deliberately skipped; confirm this intent before adding new log entries
- ℹ️ The `gather-recent-7-days-ancient-waterfall.md` plan doc is important and should not be lost — must be committed

