# EPIC-83 Wave 2: prompt for the user to relay (2026-09-27)

Only one prompt in this wave. STORY-83.5 (WP-E) goes to the Grok coding LLM.
BASE = `17e21de` on `grokbotchanges`. Claude reviews and merges.

## Common rules (paste on top)

```
COMMON RULES (EPIC-83, BASE 17e21de)
- Work ONLY in your worktree (path below). Edit ONLY the files listed under OWNED FILES.
  If you need to change anything else: STOP and report "BLOCKED: <file> <why>".
- Python: D:\Tradelatest\venv\Scripts\python.exe, and ALWAYS set PYTHONPATH=<your worktree>\src
  first. Self-check: python -c "import runtime.backtest_v2 as m; print(m.__file__)" must print a
  path inside your worktree.
- This task needs NO market data. Do not create links, junctions or copies under data\.
- NEVER delete anything: no rm, del, Remove-Item, git clean, git worktree remove/prune,
  git branch -D, git reset --hard. If something must go, STOP and report it.
- NEVER: read .env; edit configs/production/ACTIVE_VERSION or v2_htfcrt_2026_08.json (active);
  call promotion_manager promote_*; append to configs/promotion_log.jsonl; git push; git add -A.
- Every factual claim cites file:line or the exact command + its output. Unverifiable = UNVERIFIED.
  Never invent ids (F-, FM-, SEM-, CC-).
- Finish with: git -C <worktree> add <owned files> ; git -C <worktree> commit -m "<story id>: <summary>"
  Then reply with the §3 block: CURRENT_TASK / FILES_CHANGED / COMMANDS_RUN+OUTPUT / RESULT /
  UNVERIFIED / BLOCKED.
```

## Prompt → Grok coding LLM: STORY-83.5 (S1, v5 shadow config)

```
ROLE: Executor for STORY-83.5. Worktree: D:\Tradelatest-wt-wpE-v5-config (branch lane/wpE-v5-config)
OWNED FILES: configs/production/v5_htfcrt_sot_dual_k23_2026_09.json   (new)

GOAL: one shadow config that carries everything the later Setups need, while behaving EXACTLY
like the active config v2_htfcrt_2026_08 today. It is a superset with every knob at the active value.

BUILD IT FROM (read-only sources, all in configs/production/):
  A = v2_htfcrt_2026_08.json            (active; the base: copy it whole)
  S = v4_crt_sot_2026_08.json           (params: 47 keys; A has 5)
  D = v4_dual_construction_2026_09.json (4 top-level sections not in A: bar_structure_parquet,
                                         bar_structure_snapshot, context_attribution,
                                         crt_construction_trace)
  K = v2_htfcrt_k23_shadow_2026_09.json (K23 keys; differs from A in engine_runner, crt_engine,
                                         backtest)

STEPS:
 1. v5 = deep copy of A. Set "version" and "config_id" to v5_htfcrt_sot_dual_k23_2026_09.
    "notes": say it is a SHADOW superset, NOT REGISTERED, NOT ACTIVATED, built by STORY-83.5.
 2. params: add the 42 keys that S has and A lacks.
    For EACH key, the value must equal what the ACTIVE config resolves to TODAY. That is the value
    A holds elsewhere (e.g. crt_engine section), else the CRTConfig code default
    (src/config_layer/crt_engine_v2.py CRTConfig).
    Output a table: key | value in S | value active resolves to (file:line) | value used in v5.
    If S differs from the active value: use the ACTIVE value, and flag the row.
 3. Copy D's 4 sections verbatim, but with each "enabled"-style switch set so today's behaviour is
    unchanged (they are observation sidecars; D's own notes say crt_construction_trace defaults
    false). Report each switch's value and its reader (file:line).
 4. For every key where K differs from A (engine_runner, crt_engine, backtest): make sure the key
    EXISTS in v5, with A's value (e.g. retrace_reset_pct 0.5, sl_anchor as in A). List each one.
 5. Load it:
      ConfigBuilder (src/config_layer/config_builder.py) must raise no "unknown override key(s)".
      Also load through load_prod_config_from_registry (src/config_layer/production_config.py:298)
      for XAUUSD, if it accepts a version argument; else say UNVERIFIED.
 6. Hash: python scripts/maintenance/_compute_hash.py --version v5_htfcrt_sot_dual_k23_2026_09 --write
    Then git status: ONLY the v5 file may be modified or new.
 7. Behaviour check, no data: diff the resolved CRTConfig (dataclasses.asdict) from A vs from v5.
    It must be identical field by field. Paste the diff (expected: empty).

ACCEPTANCE:
  - one new file, nothing else changed (git status --short shows only it)
  - step 2 table complete, every flagged row explained
  - ConfigBuilder: no unknown keys
  - CRTConfig(A) == CRTConfig(v5), all fields
  - config_hash written into v5 only
DO NOT: run backtests, touch data, register or promote anything.
```
