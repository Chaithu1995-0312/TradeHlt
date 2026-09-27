# EPIC-83 Wave 3: prompt for the user to relay (2026-09-27)

STORY-83.6 (WP-F) goes to the Grok coding LLM. BASE = `6f32d42` on `grokbotchanges`.
Claude reviews, SITS-registers the script and merges.

## Common rules (paste on top)

```
COMMON RULES (EPIC-83, BASE 6f32d42)
- Work ONLY in your worktree (path below). Edit/create ONLY the files under OWNED FILES.
  Anything else: STOP and report "BLOCKED: <file> <why>".
- Python: D:\Tradelatest\venv\Scripts\python.exe, and ALWAYS set PYTHONPATH=<your worktree>\src
  first. Self-check: python -c "import runtime.backtest_v2 as m; print(m.__file__)" must print a
  path inside your worktree.
- NEVER delete anything: no rm, del, Remove-Item, rmdir, git clean, git worktree remove/prune,
  git branch -D, git reset --hard, shutil.rmtree on any path you did not create in %TEMP%.
  If something must go, STOP and report it.
- NEVER: read .env; edit configs/production/ACTIVE_VERSION or any configs/production/*.json;
  call promotion_manager promote_*; append to configs/promotion_log.jsonl; git push; git add -A.
- Every factual claim cites file:line or the exact command + its output. Unverifiable = UNVERIFIED.
  Never invent ids (F-, FM-, SEM-, CC-).
- Finish with: git -C <worktree> add <owned files> ; git -C <worktree> commit -m "<story id>: <summary>"
  (results/ is gitignored: do not force-add it; paste the key numbers instead.)
  Reply with the §3 block: CURRENT_TASK / FILES_CHANGED / COMMANDS_RUN+OUTPUT / RESULT /
  UNVERIFIED / BLOCKED.
```

## Prompt → Grok coding LLM: STORY-83.6 (S2, five-way parity: v5 vs active)

```
ROLE: Executor for STORY-83.6. Worktree: D:\Tradelatest-wt-wpF-parity-v5 (branch lane/wpF-parity-v5)
OWNED FILES: scripts/research/parity_v5.py (new) ; results/parity_v5/ (new, output only)

QUESTION: does v5_htfcrt_sot_dual_k23_2026_09 behave byte-identically to the active
v2_htfcrt_2026_08 on XAUUSD? (Their CRTConfig is already proven equal, 53/53 fields. This run tests
the whole pipeline, not just CRTConfig.)

DATA (a COPY, never a link or junction):
  Copy exactly these two files from D:\Tradelatest\data\mt5\ into <worktree>\data\mt5\ and
  print sha256 of each copy:
    XAUUSD_W2026-07-06-to-2026-08-07.csv  expect dcaf88a76b927d53...  (2,300 rows, user_reviewed)
    XAUUSD_M15.csv                        expect 4d73f5cebe33ec91...  (47,275 rows)
  If the first file is missing in D:\Tradelatest\data\mt5, STOP and report
  "BLOCKED: short window not restored". Do NOT cut the full corpus yourself:
  dataset_integrity rejects truncated copies (src/utils/isolated_config_root.py:120-126).

REUSE, DO NOT REIMPLEMENT:
  - src/utils/isolated_config_root.py : build_config_root(repo, root, version) gives each arm its own
    configs/ copy and its own ACTIVE_VERSION (the real one is never touched); run_backtest(...) runs
    backtest_v2 inside that root. Build the roots under %TEMP%.
  - scripts/analysis/v3_config_parity.py : compare(a, b, instrument, label) for events.jsonl /
    crt_telemetry.jsonl / trades.csv / summary.json. It already ignores run_id and handles the
    config_version stamp. Import it; do not copy it. Precedent for the pattern:
    scripts/research/emit_dual_construction_trace.py.

FIVE SURFACES, arm A = v2_htfcrt_2026_08, arm B = v5_htfcrt_sot_dual_k23_2026_09:
  1. trade ledger (trades.csv, summary.json)          -> compare()
  2. engine state sequence (events.jsonl, crt_telemetry.jsonl) -> compare()
  3. resolver states: src/charts/resolver_overlay.py build_and_cache(instrument, csv_path).
     TRAP: its cache key is corpus sha + variant ONLY, NOT config version (resolver_overlay.py:35,49-50).
     Run it with cwd = each arm's own root so each arm writes its own fresh results/ cache. Compare
     the per-bar track files between arms (byte, or row-wise if a timestamp/run stamp differs; name it).
  4. oracle labels: src/research/oracle/labeler.py (main :355; --out-dir, --matrix-dir). Run once per
     arm root with that arm's config; compare labels.csv (byte) and manifest.json (field-wise; list
     every field that differs and why).
  5. layer_trace joins: src/runtime/layer_trace.py. Find where a backtest emits layer_trace rows
     (grep LayerTraceEmitter / layer_trace in src/runtime/backtest_v2.py). If they are emitted in
     each arm's output: join by trade_id and compare. If layer_trace is OFF in both configs, report
     "NOT EMITTED (config key + file:line)", do NOT turn it on.

KNOWN EXPECTED DIFFERENCES (declare them, do not hide them): config_version / version / config_id,
config_hash (A 7de09f62..., B e496a94c... — params-hash differs because B carries 47 params), run_id.
Any other difference is a FINDING: report it per surface with the first 5 differing rows.
Do not "fix" anything to force a pass.

ORDER:
  a. Short window first (2,300 rows): all five surfaces.
  b. Only if (a) finished without errors: full corpus (47,275 rows): all five surfaces. The full
     run may take long: run it in the background, write output to results/parity_v5/full.log, and
     report its exit code.

OUTPUT: results/parity_v5/{short,full}/verdict.json with, per surface:
  {surface, arm_a_path, arm_b_path, n_rows_a, n_rows_b, verdict: IDENTICAL | DIFFERS | NOT_EMITTED,
   ignored_fields, first_diffs}
  And print one line per surface per window.

ACCEPTANCE: script + both verdict files; every verdict backed by command output; no file outside
OWNED FILES changed (git status --short shows only scripts/research/parity_v5.py).
```
