# EPIC-83 Wave 4: prompts for the user to relay (2026-09-27)

Two independent prompts; send both now. BASE = `adba177` on `grokbotchanges`.
83.9 (ATR copies) is DEFERRED by user decision. 83.13 (k23 completion manifests) is done by Claude
in parallel. Claude reviews and merges.

## Common rules (paste on top of each prompt)

```
COMMON RULES (EPIC-83, BASE adba177)
- Work ONLY in your worktree (path below). Edit ONLY the files under OWNED FILES.
  Anything else: STOP and report "BLOCKED: <file> <why>".
- Python: D:\Tradelatest\venv\Scripts\python.exe, and ALWAYS set PYTHONPATH=<your worktree>\src
  first. Self-check: python -c "import runtime.backtest_v2 as m; print(m.__file__)" must print a
  path inside your worktree.
- Data is already COPIED into your worktree (sha-checked by Claude). Do not add links or junctions.
- NEVER delete anything: no rm, del, Remove-Item, rmdir, git clean, git worktree remove/prune,
  git branch -D, git reset --hard, shutil.rmtree outside %TEMP% dirs you created.
- NEVER: read .env; edit configs/production/*; call promote_*; append to promotion_log.jsonl;
  git push; git add -A; edit docs/governance/corpus_read_allowlist.json or run any --regenerate.
- Every factual claim cites file:line or the exact command + its output. Unverifiable = UNVERIFIED.
  Never invent ids (F-, FM-, SEM-, CC-).
- Finish with: git -C <worktree> add <owned files> ; git -C <worktree> commit -m "<story id>: <summary>"
  Reply with the §3 block: CURRENT_TASK / FILES_CHANGED / COMMANDS_RUN+OUTPUT / RESULT /
  UNVERIFIED / BLOCKED.
```

## Prompt 1 → Grok coding: STORY-83.7 (label loaders → corpus gate)

```
ROLE: Executor for STORY-83.7. Worktree: D:\Tradelatest-wt-wpG-loader-gate (branch lane/wpG-loader-gate)
OWNED FILES:
  scripts/research/rr_l3_label_generation.py      (_load_candles, :59-76)
  scripts/analysis/bnbusdt_trade_anatomy.py        (load_candles, :87-103)

WHY: both loaders read CSVs directly, with no gate. STORY-83.2 found every BNBUSDT label set was
built on data/BNBUSDT_M15.csv, whose clock was never reviewed. From now on they must go through the
corpus gate, which refuses unreviewed corpora.

DO:
 1. In each loader, before opening the file:
      from data_ingestion.corpus_gate import admit_corpus
      adm = admit_corpus(csv_path, instrument, write_report=False)
      csv_path = Path(adm.filepath)
    Precedent, copy its shape: scripts/research/build_bar_matrix.py:382-383.
    admit_corpus: src/data_ingestion/corpus_gate.py:233 (identity failures always raise).
 2. instrument: derive it from the filename stem before the first "_" (e.g. XAUUSD_M15.csv -> XAUUSD),
    unless the function already receives it. Say which you did.
 3. Keep each function's signature and return shape EXACTLY (bnbusdt_trade_anatomy.load_candles
    returns (candles, ts_to_idx, closes) and is imported by build_clean_labels_tn_env.py:26,
    build_episodes.py:28, gate0_tn_env_feasibility.py:34, zone_label_audit.py:40).
 4. Nothing else in those files changes.

ACCEPTANCE (paste outputs):
  a. XAUUSD same data: for each loader, load data/mt5/XAUUSD_M15.csv with the ORIGINAL function
     (git show adba177:<file> into %TEMP%) and the NEW one; print count, first/last timestamp, and
     sha256 of "ts,o,h,l,c,v" lines joined. Must be equal.
  b. BNBUSDT refused: calling each new loader on data/BNBUSDT_M15.csv (already copied into your
     worktree) must RAISE. Paste the exception class and first line of the message.
  c. Importers still import: python -c "import build_clean_labels_tn_env" (etc., with the right
     sys.path) for all 4.
  d. python scripts/analysis/corpus_read_lint.py : the two sites (durable keys f42821e2639f6511,
     5d2e15d1e7cd71b4) should now be listed as SHRUNK. The lint's NEW-CORPUS failure
     _build_run_story.py:34 is pre-existing (another session) — report, don't fix.
  e. git status --short shows only the two owned files.
```

## Prompt 2 → DeepSeek: STORY-83.8 (execution_planner_replay: gated load + multi_tp_walk arm)

```
ROLE: Executor for STORY-83.8. Worktree: D:\Tradelatest-wt-wpH-replay-walk (branch lane/wpH-replay-walk)
OWNED FILES: scripts/research/execution_planner_replay.py ; output only under results/execution_planner_replay/

WHY: the replay's forward exits use analytics.sl_tp_comparator.simulate_exit (:39-42, called :151),
which closes the WHOLE position at the first of TP2 > SL > TP1 (src/analytics/sl_tp_comparator.py:149-205).
Production closes 50% at TP1 and trails the rest half-way (F-088). The canonical walk of that object
is src/research/oracle/multi_tp_walk.py:125-160. Also its candles load ungated via
SLTPComparator.load_candles_from_csv (:203).

USER DECISION: keep the old walk. Report BOTH walks side by side. Do NOT touch
src/analytics/sl_tp_comparator.py, src/control_plane/registry.py, or any test.

DO:
 1. Gate the candle load: admit_corpus(csv, instrument, write_report=False)
    (src/data_ingestion/corpus_gate.py:233; precedent scripts/research/build_bar_matrix.py:382-383),
    then load from adm.filepath. Prove the candle list equals the old loader's for XAUUSD
    (count, first/last ts, sha of OHLCV lines).
 2. Add a second exit arm per cell (A/B/C/D):
      multi_tp_walk(entry, "long"/"short", sl, tp1, tp2, future,
                    tie_break="optimistic", partial_fraction=0.5, trail_fraction=0.5,
                    max_forward=<the same horizon simulate_exit uses>)
    tie_break "optimistic" = the same TP2>SL>TP1 precedence as simulate_exit; the difference left
    is the partial + trail object. Aggregate it the same way as the old arm (reuse
    _aggregate_variant_results if the dict shape fits; if not, say what you mapped).
 3. The OLD arm must reproduce the unmodified script EXACTLY: run the original
    (git show adba177:scripts/research/execution_planner_replay.py > %TEMP%\orig.py) and the new one
    on the same input, diff the old-arm numbers (expect identical).
 4. Run on XAUUSD: --instrument XAUUSD --csv data/mt5/XAUUSD_M15.csv (default is BNBUSDT, which the
    gate now refuses; show that refusal once). The script runs its own backtest on the ACTIVE config
    and reads RETEST_REPLAY telemetry from it (:69-114). This is the full corpus; it may take long,
    run in the background and log to results/execution_planner_replay/xauusd.log.
REPORT: a table per cell A/B/C/D: n, mean R (simulate_exit), mean R (multi_tp_walk), difference;
  the trust gate (cell B vs real executed expectancy) under both walks; the 2x2 selection vs SL/TP
  decomposition under both walks. No economic claim (research only).
ACCEPTANCE: git status --short shows only the owned script.
```
