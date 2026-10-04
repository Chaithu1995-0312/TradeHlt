# EPIC-83 Wave 1: prompts for the user to relay (2026-09-27)

The three prompts are independent. Send all three now. Each agent works **only** in its own
worktree and only on its owned files. Claude reviews and merges.

- BASE commit: `d318f13` on branch `grokbotchanges`.
- Plan: `C:\Users\Hi\.claude\plans\discuss-before-design-and-compiled-jellyfish.md`, section "ACTIVE PLAN".

## Common rules (paste on top of every prompt)

```
COMMON RULES (EPIC-83, BASE d318f13)
- Work ONLY in your worktree (path below). Edit ONLY the files listed under OWNED FILES.
  If you need to change anything else: STOP and report "BLOCKED: <file> <why>".
- Python: D:\Tradelatest\venv\Scripts\python.exe, and ALWAYS set PYTHONPATH=<your worktree>\src
  first. Without it you silently run the MAIN tree's code, not yours.
  Self-check: python -c "import runtime.backtest_v2 as m; print(m.__file__)" must print a path
  inside your worktree.
- Data: data\mt5 in your worktree is a junction to the real corpus
  (XAUUSD M15, sha 4d73f5ce..., 47,275 rows). XAUUSD only.
  Use a time-range subset first, then the full corpus.
- NEVER: read .env; edit configs/production/ACTIVE_VERSION or v2_htfcrt_2026_08.json (active);
  call promotion_manager promote_*; git push; git add -A; commit outside your branch.
- Every factual claim cites file:line or the exact command + its output.
  If you can't verify something, write UNVERIFIED. Never invent ids (F-, FM-, SEM-, CC-).
- Finish with: git -C <worktree> add <owned files> ; git -C <worktree> commit -m "<story id>: <summary>"
  Then reply with the §3 block:
  CURRENT_TASK / FILES_CHANGED / COMMANDS_RUN+OUTPUT / RESULT / UNVERIFIED / BLOCKED.
```

## Prompt 1 → Grok coding LLM: STORY-83.1 (S0 Stage-0 remediation)

```
ROLE: Executor for STORY-83.1. Worktree: D:\Tradelatest-wt-wpA-s0-stamp  (branch lane/wpA-s0-stamp)
OWNED FILES: configs/production/v4_dual_construction_2026_09.json

TASK 1 (D1, edit):
  Line 2 of that file says  "version": "v3_unified_market_structure_2026_09"
  but the file is the v4 dual-construction config.
  - Set it to "v4_dual_construction_2026_09".
  - Change NOTHING else. No reformatting: keep the key order and indentation byte-for-byte.
  - Prove it:
      git diff --stat           -> exactly 1 file, 1 line changed
      python -c "import json;print(json.load(open('configs/production/v4_dual_construction_2026_09.json'))['version'])"
  - If a "config_hash" field exists, report whether it covers "version". Read
    scripts/maintenance/_compute_hash.py (it hashes the `params` block only, per its docstring;
    confirm it).
  - Do NOT run it with --write.

TASK 2 (D2, read-only report, no edits):
  In docs/governance/build_manifests/ there are impact manifests for
  CH-k23-f2-exchange-session-windows, CH-k23-f3-sl-anchor-sweep-extreme,
  CH-k23-f3-oracle-arm-stamping and CH-k23-f4-sweep-htf-exempt, but no *.completion.json
  for them.
  - Confirm with ls.
  - Search the same folder, configs/promotion_log.jsonl and git log for manifests or entries
    naming v4_crt_sot_2026_08 or v4_dual_construction_2026_09.
  - Report a table: config/change -> impact manifest? -> completion manifest? -> promotion_log
    entry?
  - Run: python scripts/governance/construction_protocol.py validate-completion <each manifest
    that exists>, and paste the verdicts.

READ FIRST:
  configs/production/v4_dual_construction_2026_09.json
  configs/production/v4_crt_sot_2026_08.json
  configs/promotion_log.jsonl
  docs/governance/REPOSITORY_CONSTRUCTION_PROTOCOL.md (manifest shape)

ACCEPTANCE: 1-line diff; D2 table complete. Do not create the missing manifests (that is a
separate decision).
```

## Prompt 2 → Grok bot: STORY-83.2 (research Q2 + Q4, read-only)

```
ROLE: Research auditor for STORY-83.2. Worktree: D:\Tradelatest-wt-wpB-research-q2q4  (branch lane/wpB-research-q2q4)
OWNED FILES: docs/audits/RESEARCH_Q2_Q4_2026-09-27.md   (new; the ONLY file you write)
Any helper script goes to %TEMP%, never into the repo.

Q2: Which corpora did the two UNGATED label loaders actually read?
  Loader A: scripts/research/rr_l3_label_generation.py  _load_candles (~:59-76, plain csv parser)
  Loader B: scripts/analysis/bnbusdt_trade_anatomy.py  load_candles,
            imported by scripts/research/build_clean_labels_tn_env.py:26
  For each loader:
  - List every CSV path it can receive (defaults, argparse, callers). Find callers with:
      grep -rn "rr_l3_label_generation\|bnbusdt_trade_anatomy" scripts src
  - For each path:
    - does it exist on disk
    - its sha256 prefix
    - is it registered in configs/data_provenance/ohlcv_clock_registry.json, and with
      what review status
    - is it on the corpus_read_allowlist (docs/governance/corpus_read_allowlist.json)
  - Name which label artifacts on disk were produced by each path, if provenance says so
    (e.g. clean_labels*.jsonl provenance). Say UNVERIFIED where provenance is silent.
  Verdict per loader: READ_REVIEWED_ONLY / READ_UNREVIEWED / UNKNOWN.

Q4: Are the qualification "shadow walks" numerically equal to the canonical forward_walk?
  Canonical: src/research/measurement/forward_walk.py
  Shadows:
    scripts/research/xauusd_gaussian_m4_qualify.py
    scripts/research/run_xau_metals_protocol_v1.py
    scripts/research/gate0_tn_env_feasibility.py
  For each shadow:
  - Locate its private walk (file:line).
  - Build the same signal set (entries, SL, TP, direction) on a ONE-MONTH XAUUSD subset of
    data/mt5/XAUUSD_M15.csv.
  - Run BOTH the shadow walk and forward_walk(intrabar_fixed) on it.
  - Report n, and the counts where exit reason / exit bar / R differ, with the first 5 diffs.
  - State the tie-break each one uses: SL-first vs TP-first (production is SL-first, F-088).
  Verdict per shadow: EQUAL / DIFFERS(<axis>) / NOT_COMPARABLE(<why>).

READ FIRST:
  docs/audits/RESEARCH_AUTHORITY_CENSUS_2026-09-27.md (your own prior census)
  src/data_ingestion/corpus_gate.py
  src/research/oracle/multi_tp_walk.py (tie_break options)

ACCEPTANCE: every row cites file:line + command output; no repo file other than the owned doc
changes.
```

## Prompt 3 → DeepSeek: STORY-83.3 (design spec only, no code)

```
ROLE: Planner/spec writer for STORY-83.3. Worktree: D:\Tradelatest-wt-wpC-setup-spec  (branch lane/wpC-setup-spec)
OWNED FILES: docs/implementation_plan/setup-overlay-spec-2026-09.md   (new; spec only, NO code)

GOAL:
  Production and research differ only by a "Setup":
  - Setup = the v5 shadow config + a small declared overlay.
  - The research lab runs N Setups through the SAME L0-L9 path (never re-implements a layer).
  - Production = one promoted Setup.
  Specify the overlay and the run unit.

SPEC MUST DEFINE:
  1. Overlay keys. For each key give: name, section, type, allowed values, DEFAULT (must equal
     today's behaviour exactly), and the code site that would consume it (file:line).
     a. stop anchor: backtest.sl_anchor ∈ {displacement, sweep_extreme} (exists today;
        backtest_v2.py:165-200)
     b. target policy ∈ {fixed_r (today: tp1/tp2 R-multiples of |entry-sl|),
        structural_tp2 (opposite side of active_range)}. Site: ExecutionEngine.build_trade
        (src/config_layer/crt_engine_v2.py ~:2421)
     c. trade TTL in candles (int|null; null = today = no time-stop). Outcome TIMEOUT.
        Note open_candle_index (crt_engine_v2.py ~:217) is declared but never set.
     d. decider ∈ {engine (today), resolver} = "mode C": the resolver founds the setup and hands
        over 4 objects (active_range, sweep event, displacement candle, retest candle). The engine
        keeps geometry + exits. The resolver must run with engine-oracle injection OFF
        (src/features/crt_state_resolver.py ~:247-251). Resolver objects are held at ~:147-150.
     e. K23 switches F1 retrace_reset_pct, F2 session_window_basis, F4 htf_reset_exempt_sweep:
        cite their current keys.
  2. Where the Setup object lives:
     - execution-side (src/config_layer/). Research imports it; execution never imports
       research.
     - Relation to src/config_layer/production_bundle.py ProductionBundle.
  3. Run unit: src/research/experiment_spec.py ExperimentSpec (has production_config_ref,
     authority="NONE", 0 users today).
     - Define one spec = N Setups x corpus.
     - Define the report fields: net %, max DD, trade count, win rate at a FIXED risk_pct;
       R per variant.
     - Ranking only where src/governance/measurement_basis.py can_compare (~:185-230) allows.
       It returns DENY_REFERENCE_LEVEL_MISMATCH across stop anchors: keep it and explain why.
  4. Parity rule: with every overlay key at default, ledger + engine states + resolver states +
     oracle labels + layer_trace joins must be byte-identical to v5.
  5. Open questions list (do not answer them yourself where they are the user's decisions).

DO NOT:
  - write code
  - invent new layers or doctrine
  - propose changing measurement_basis
  - propose a new config file other than the v5 shadow
  Mark anything unverified as UNVERIFIED.

READ FIRST:
  crt_engine_v2.py :2300-2700 (build_trade, update_trade, ResetLogic)
  backtest_v2.py :165-200
  experiment_spec.py
  measurement_basis.py
  production_bundle.py
  configs/production/v2_htfcrt_k23_shadow_2026_09.json (K23 keys)
  docs/governance/CANONICAL_LAYER_IDENTITY_CONTRACT.md :60-80 (names)
```
