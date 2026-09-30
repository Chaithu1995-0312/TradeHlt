# Consolidate everything into grokbotchanges, then watch a run (bar structure + entry/SL/TP)

## Context
User 2026-09-30: stop test/governance/parity gating; get all work merged into `grokbotchanges`, preserving
the bot's changes (ask when a conflict is unclear); then look at what was built and monitor bar structure and
entry/SL/TP on a run.

Verified state:
- `grokbotchanges` HEAD `2d7dde0` (84.1). Wave-1 lanes L-B/C/E/F are already in (as rebased copies).
- NOT in grokbotchanges: `lane/wp84-ld` (84.4, uncommitted in its worktree, 60 files);
  `lane/wp84-a3b` (A3b `454fd54`: engine supplies trade-intent inputs — changes TP1 choice);
  `lane/mc-d0a` (A3b + D0a renames: gaussian->ema_momentum_kernel, zone_gate->feature_cluster_similarity,
  rr->candle_commitment, etc. + the D0a fixes, 9 commits).
- Main tree uncommitted = the bot's work (`.grok/PENDING.md` modified): crt_engine_v2 (+195/-33),
  backtest_v2 (mode-C founding hunk), resolver_overlay, bar_structure_snapshot (Live Run Trace flags),
  server.py (`/api/run_trace/*`), yaml/state-graph files, setup_grid_s4; untracked
  `src/control_plane/run_trace_api.py`, `ui_kits/run_trace/index.html`, `tests/test_run_trace.py`,
  `tests/test_mode_c_resolver_founding.py`, design cards/docs.
- The Run Trace page reads `logs/bar_structure/<run_id>/` written by `bar_structure_snapshot` when a config
  enables `bar_structure_snapshot` (+ `per_run_dir`, `include_features`). Rows carry CRT state and
  `crt_trade_open`, NOT entry/SL/TP; those are in the run's events (`TRADE_OPENED`) / trades ledger.

## Steps
1. **Commit the bot's work first** on grokbotchanges (main tree): the tracked modified files above +
   the untracked code/test/docs listed (not `scratch_run_logs/`, `report.json`, my `results_xau_last_month.log`).
   Secret-scan the staged diff (print file:line only). `--no-verify`. Message: "Grok bot: Live Run Trace +
   mode-C resolver founding + ... (preserved as-is)".
2. **Commit 84.4** in `D:/Tradelatest-wt-wp84-ld`, then `git merge lane/wp84-ld` into grokbotchanges
   (real merge now; backtest_v2 overlaps only in separate regions -> expect auto-merge).
3. **Merge `lane/mc-d0a`** (brings A3b + D0a) — per user answer. Conflicts expected in crt_engine_v2 /
   backtest_v2 / engine_runner / live_engine_hook (bot + 84.4 + A3b + renames). Resolve mechanically where
   both sides' intent is clear (keep both); any hunk where bot logic and A3b/rename logic disagree -> stop
   and ask with the two sides shown. After merge, grep for old engine names in files 84.4 touched.
4. Smoke check only: import `runtime.backtest_v2`, `control_plane.server`; run the chosen backtest.
5. **Monitor run**: run the backtest with bar_structure_snapshot enabled (per_run_dir + include_features) on
   the chosen window/config; start the control plane (`localhost:8787`) and open the Run Trace page in the
   browser pane; show bar structure live. Entry/SL/TP: per user answer.
6. Queue 84.4 done; SESSION LOG entry.
