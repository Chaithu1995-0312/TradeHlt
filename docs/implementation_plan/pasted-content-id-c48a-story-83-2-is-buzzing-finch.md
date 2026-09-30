# Plan: EPIC-83 Wave 4 prompts (83.7, 83.8), with Claude doing 83.13 in parallel (2026-09-27)

## Context
S0 to S2 are done. The v5 shadow config is behaviour-identical to the active config on the full XAUUSD five-way parity (merge `093e6d3`).

The user asked for the Wave 4 prompts, and for 83.13 to run in parallel.

User decisions this turn:
- **83.9 (WP-I, ATR copies) is DEFERRED.** No canonical ATR series function exists; the ATR is inline at `feature_pipeline.py:610-615`.
- **83.8 keeps the old walk.**
  - The replay reports `simulate_exit` and `multi_tp_walk` side by side.
  - `sl_tp_comparator` is not archived now; that becomes a later story.

Facts verified this turn (read-only):
- **Gate precedent:** `scripts/research/build_bar_matrix.py:382`, which calls `adm = admit_corpus(csv_path, instrument, write_report=False)` and then reads from `adm.filepath`.
  - `admit_corpus` is at `src/data_ingestion/corpus_gate.py:233`.
  - Identity failures always raise.
  - An unreviewed clock (BNBUSDT, per 83.2) will be REFUSED. That's the intended fail-closed outcome.
- **The two loaders:**
  - `scripts/research/rr_l3_label_generation.py:59-76` (`_load_candles`, allowlist durable_key f42821e2639f6511)
  - `scripts/analysis/bnbusdt_trade_anatomy.py:87-103` (`load_candles`, key 5d2e15d1e7cd71b4)
  - The second is imported by `build_clean_labels_tn_env.py:26`, `build_episodes.py:28`, `gate0_tn_env_feasibility.py:34` and `zone_label_audit.py:40`. Its return shape `(candles, ts_to_idx, closes)` must not change.
- **The replay:** `scripts/research/execution_planner_replay.py`
  - It imports `simulate_exit`, `_aggregate_variant_results` and `SLTPComparator` from `analytics.sl_tp_comparator` (:39-42).
  - `simulate_exit` is called at :151.
  - Candles are loaded by `SLTPComparator.load_candles_from_csv` (:203), an ungated corpus read.
  - The default instrument is BNBUSDT (:179), which the gate will refuse, so it must run on XAUUSD.
- **The two walks differ:**
  - `simulate_exit` is a WHOLE-position exit, TP2 > SL > TP1 (`sl_tp_comparator.py:149-205`).
  - `multi_tp_walk` is the partial + half-way-trail production object (F-088), `src/research/oracle/multi_tp_walk.py:125-160`, with `tie_break="optimistic"` = the same precedence.
  - So the new numbers WILL differ by design.
- **Manifests:**
  - Completion schema: `construction_protocol.py:49-51` (`change_id`, `declared_files`, `checks_executed`, `repo_state_hash`, `completion_status`).
  - `validate_completion` (:130-208) re-runs each class's required checks.
  - The four k23 impact manifests are all `RUNTIME_DECISION_PATH_CHANGE`, and their checks include `test_geometry_census` / `test_feature_math_lint` / `test_current_findings`, which are already red at BASE.
  - Precedent for honest non-COMPLETE: `CH-resolver-engine-envelope.completion.json` (`BLOCKED_PREEXISTING_DIRTY_TREE` + `completion_note`).

## Step 1: set up the worktrees (Claude; copies only, no links, no deletes)
- WP-G: `git worktree add ../Tradelatest-wt-wpG-loader-gate -b lane/wpG-loader-gate grokbotchanges`
- WP-H: `git worktree add ../Tradelatest-wt-wpH-replay-walk -b lane/wpH-replay-walk grokbotchanges`
- Into each, with `cp -n`:
  - the 3 bound corpora: `data/mt5/XAUUSD_M15.csv`, `XAUUSD_W2026-07-06-to-2026-08-07.csv`, `W2026-08-03_to_2026-09-23/XAUUSD_M15.csv`. The registry validates every bound record.
  - WP-H also gets `models/` and `results/research/xauusd_mt5_cost_calibration/`.
- Check each copy's sha against the registry.

## Step 2: write the Wave 4 prompts
File: `multi_llm/wave4_prompts_2026-09-27.md`, plus a Desktop copy. Common rules are the same as Wave 3: no deletes, no links, PYTHONPATH self-check, owned files only, §3 block.

**83.7 (WP-G) → Grok coding.**
- Owned files: the two loader files only.
- Route each loader through `admit_corpus(path, instrument, write_report=False)` (the build_bar_matrix precedent) and read `adm.filepath`. Keep the return shapes byte-identical.
- Instrument hint: take it from the caller or the filename; say which.
- Acceptance:
  - Loading `data/mt5/XAUUSD_M15.csv` returns the same candles as before (count, first/last timestamp, sha of the serialized OHLC).
  - Loading `data/BNBUSDT_M15.csv` now RAISES. Quote the error class and message.
  - All 4 importers still import. Run `python -c "import ..."` for each.
  - `corpus_read_lint`: the two allowlist sites now show as SHRUNK. Do NOT edit the allowlist or run `--regenerate`; Claude handles that.
  - Tests: `tests/test_corpus_read_lint.py` result (pre-existing red is `_build_run_story.py:34`), plus any tests of these scripts.

**83.8 (WP-H) → DeepSeek.**
- Owned file: `scripts/research/execution_planner_replay.py`; outputs under `results/execution_planner_replay/`.
1. Gate the candle load through `admit_corpus`. It must produce the same candle list as `SLTPComparator.load_candles_from_csv` for XAUUSD; prove it.
2. Add a `multi_tp_walk(tie_break="optimistic", partial_fraction=0.5, trail_fraction=0.5, max_forward=<same horizon>)` arm next to `simulate_exit`.
   - Each cell A/B/C/D reports both walks.
   - The old `simulate_exit` numbers must be reproduced exactly (show the diff against a run on the unmodified script).
3. Run on XAUUSD.
   - Where does RETEST_REPLAY telemetry come from for XAUUSD? UNVERIFIED; find it or report BLOCKED.
   - Report the per-cell n / mean R for both walks and the trust gate (cell B).
- Do not touch `sl_tp_comparator.py`, `registry.py` or tests.

**83.9 (WP-I):** deferred. Mark it in the queue: "DEFERRED 2026-09-27 (user): no canonical ATR series helper yet; engine copy owned by WP-K".

## Step 3: 83.13, done by Claude in the main tree, in parallel
For each of the 4 k23 changes, write `docs/governance/build_manifests/CH-k23-*.completion.json`:
- `declared_files` = that impact manifest's `affected_files` + the completion file itself.
- `checks_executed` = the class's required checks, run under **venv**. Record the pass/fail tail per check.
- `repo_state_hash` = current hash if the governed tree is clean at run time, else `PENDING` with the observed hash in the note (precedent).
- `completion_status`:
  - `COMPLETE` only if `validate-completion` passes.
  - Otherwise `BLOCKED_PREEXISTING_RED_FLOOR`, with a `completion_note` naming each red check and showing it's red at BASE (`d318f13`), not caused by k23.
- `evidence`:
  - The change's own unit tests (e.g. `tests/test_sl_anchor_sweep_extreme.py`).
  - STORY-83.6 parity: v5 carries all K23 knobs at legacy defaults and is identical to the active config on the full corpus (merge `093e6d3`), which proves default-off byte-identity.
  - `production_behavior_changed: NO` (K23 is set on the shadow config only).
- Run `construction_protocol.py validate-completion <each>` and record the verdicts verbatim.
- Commit the 4 files, the SESSION LOG entry and the queue (83.13 → done or blocked-with-reason) with `[nolog]`-free normal commit rules. Use `--no-verify` only if the hook again uses the bare python (reason stated in the message).

## Step 4: bookkeeping
- Queue: 83.7 / 83.8 → in_progress; 83.9 → DEFERRED note; 83.13 → result.
- HANDOFF `current_story` / `next_actor`.
- `test_handoff_state.py` passes.

## Verification
- Worktree data copies match the registry shas; `git status` in each worktree is clean before the relay.
- 83.13: four `validate-completion` verdicts pasted into the manifests' notes; `tests/test_construction_protocol.py` passes.
- Nothing deleted: no `rm` / `worktree remove` / `git clean`.
