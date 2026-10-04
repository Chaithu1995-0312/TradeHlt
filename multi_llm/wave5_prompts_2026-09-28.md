# EPIC-83 Wave 5: prompt for the user to relay (2026-09-28)

One prompt: STORY-83.10 (WP-J, resolver reads the production keys, "P-1"). BASE = `2ed75cc` on
`grokbotchanges`.

Not in this wave, and why:
- **83.11 (WP-K, Setup overlay)** waits on your answers to the 83.3 spec §10 questions
  (`docs/implementation_plan/setup-overlay-spec-2026-09.md:593`), and on 83.10 landing.
- **83.12 (WP-L, first grid)** needs `target_policy` and `trade_ttl_candles`, which do not exist
  until 83.11 ships (spec §3.2: "three are new"). It cannot run before 83.11.
- **83.9 (ATR copies)** stays DEFERRED (user decision 2026-09-27).

User decision 2026-09-28: when no config is passed, the resolver **requires an instrument**
(no hidden XAUUSD default). This widens WP-J from 2 files to every caller.

## Common rules (paste on top of the prompt)

```
COMMON RULES (EPIC-83, BASE 2ed75cc)
- Work ONLY in your worktree (path below). Edit ONLY the files under OWNED FILES.
  Anything else: STOP and report "BLOCKED: <file> <why>".
- Python: D:\Tradelatest\venv\Scripts\python.exe, and ALWAYS set PYTHONPATH=<your worktree>\src
  first. Self-check: python -c "import features.crt_state_resolver as m; print(m.__file__)" must
  print a path inside your worktree.
- Data is already COPIED into your worktree (data/mt5/XAUUSD_M15.csv, sha256 4d73f5ce..., checked
  by Claude). Do not add links or junctions.
- NEVER delete files: no rm, del, Remove-Item, rmdir, git clean, git worktree remove/prune,
  git branch -D, git reset --hard, shutil.rmtree outside %TEMP% dirs you created.
  (Removing KEYS from market_crt_states.yaml is the requested edit and is fine.)
- NEVER: read .env; edit configs/production/*; call promote_*; append to promotion_log.jsonl;
  git push; git add -A; edit docs/governance/corpus_read_allowlist.json or run any --regenerate.
- Every factual claim cites file:line or the exact command + its output. Unverifiable = UNVERIFIED.
  Never invent ids (F-, FM-, SEM-, CC-).
- Finish with: git -C <worktree> add <owned files> ; git -C <worktree> commit -m "<story id>: <summary>"
  Reply with the §3 block: CURRENT_TASK / FILES_CHANGED / COMMANDS_RUN+OUTPUT / RESULT /
  UNVERIFIED / BLOCKED.
```

## Prompt → Grok coding: STORY-83.10 (resolver reads the production keys)

```
ROLE: Executor for STORY-83.10. Worktree: D:\Tradelatest-wt-wpJ-resolver-p1 (branch lane/wpJ-resolver-p1)

WHY: CRTStateResolver keeps its own copy of 12 thresholds the engine also uses
(configs/formulas/market_crt_states.yaml `thresholds:`, classified in `threshold_refs:` :420-590).
User decision 2026-09-27: every shared quantity gets ONE number, the production key, so a shadow
config moves engine and resolver together. Today the values are equal, so resolver output must not
change at all.

SHARED KEYS (read from CRTConfig from now on; delete the YAML literal):
  body_ratio_min, atr_multiplier_min, atr_min_displacement, expansion_atr_min_distance,
  retest_depth_max, max_sweep_age_candles, max_expansion_age_candles, max_expansion_age_hours,
  score_threshold, soft_conf_max_candles,
  lifecycle.pending_displacement_ttl_candles  -> CRTConfig.pending_displacement_ttl_candles
  range_atr_period                            -> CRTConfig.atr_period
DEAD KEYS (delete from `thresholds:` and from `threshold_refs:`):
  retest_atr_depth_fraction (0.50; production is 0.3 -- do NOT carry 0.50 anywhere),
  rsi_overbought, rsi_oversold
OUT OF SCOPE (leave exactly as is): sweep_geometry, expansion_atr_is_relative,
  continuous_disp_to_expansion, max_displacement_age_candles, every other lifecycle.* key
  (incl. htf_candles_per_range and gap_reset_minutes, which alias backtest.*, not CRTConfig).

Claude verified the values are equal today (get_prod_config('XAUUSD'), ACTIVE_VERSION
v2_htfcrt_2026_08): atr_period 14, body_ratio_min 0.65, atr_multiplier_min 1.0,
atr_min_displacement 1.2, expansion_atr_min_distance 0.3, retest_depth_max 0.15,
max_sweep_age_candles 20, max_expansion_age_candles 495, max_expansion_age_hours 124,
score_threshold 0.45, soft_conf_max_candles 3, pending_displacement_ttl_candles 4. Re-print these
yourself before editing (acceptance a).

OWNED FILES:
  src/features/crt_state_resolver.py
  configs/formulas/market_crt_states.yaml
  src/features/registry/__init__.py            (validate_crt_threshold_refs :594 only, if needed)
  callers (constructor call sites only, plus the minimal plumbing to get an instrument there):
    src/charts/resolver_overlay.py
    src/research/rc003_distinct_object/driver.py
    src/runtime/crt_construction_trace.py
    scripts/analysis/phase1_resolver_replay_evidence.py
    scripts/governance/feature_surface_query.py
    scripts/research/crt_range_rebuild_probe.py
    scripts/research/crt_resolver_economic_comparison.py
    scripts/research/crt_state_confusion_matrix.py
    scripts/research/link001_choch_measurement.py
    scripts/research/retest_divergence_probe.py
    scripts/research/run_crt_state_on_mt5_xauusd.py
    scripts/research/validate_crt_state_resolver.py
  tests (call sites + new tests):
    tests/governance/test_crt_predicate_supply_contract.py
    tests/governance/test_crt_resolver_links.py
    tests/research/test_rc003_distinct_object.py
    tests/test_crt_states_yaml_state_names.py
    tests/test_crt_state_resolver_b1h_polish.py
    tests/test_crt_state_resolver_displacement_gate.py
    tests/test_crt_state_resolver_gate_parity.py
    tests/test_crt_state_resolver_sweep_geometry.py
    tests/test_resolver_metadata.py
    tests/test_resolver_supply.py
    tests/test_crt_threshold_refs.py
  output only under results/wpj/ (new) and %TEMP%

DO:
 0. BEFORE any edit: capture the baseline.
    a. Test baseline: run every test file listed above at BASE; paste passed/failed counts.
    b. Resolver baseline on the full XAUUSD corpus: charts.resolver_overlay.build_and_cache(
       "XAUUSD", "data/mt5/XAUUSD_M15.csv") (check the exact signature at resolver_overlay.py:70).
       Copy the resulting states.csv + meta.json to results/wpj/before/. It is a multi-minute
       run: run it in the background, log to results/wpj/before.log, wait for the exit status.
 1. Constructor: add two keyword-only args to CRTStateResolver.__init__ (:315):
       instrument: str | None = None, crt_config: "CRTConfig | None" = None
    Rules (fail closed, no hidden default):
      - neither given           -> raise ConfigLoadError naming both args
      - both given              -> raise ConfigLoadError (ambiguous)
      - instrument only         -> crt_config = get_prod_config(instrument)
                                   (src/config_layer/production_config.py:254). Import it INSIDE
                                   __init__ (lazy) to avoid a features -> config_layer import
                                   cycle; if you find a cycle anyway, report it.
      - crt_config only         -> use it as given.
    Keep the resolved config's source on the instance (instrument or "caller-supplied", plus
    version if the object carries one) and expose it on the existing metadata surface
    (tests/test_resolver_metadata.py shows what exists). Say what you added.
 2. Wiring, minimal-diff approach (use this unless it cannot work; if not, say why):
      - After _load_config(), FAIL (ConfigLoadError) if the YAML `thresholds:` (or
        thresholds.lifecycle for pending_displacement_ttl_candles) still contains ANY shared key
        -- so a second copy can never come back silently.
      - Then write the CRTConfig values into self._config["thresholds"] under the resolver's
        existing key names (range_atr_period <- atr_period;
        lifecycle.pending_displacement_ttl_candles <- pending_displacement_ttl_candles) BEFORE
        _load_lifecycle() and the range_atr_period read (:376) run. Every read site then works
        unchanged.
      - Convert each shared-key read that has a literal fallback to a strict read (thr["key"]):
        :376, :917, :1616, :1797, :1991, :2007, :2014, :2095-2096 (verify each line; list them).
        The values come from CRTConfig, so the fallbacks are dead and would hide a missing key.
 3. YAML (market_crt_states.yaml):
      - Delete the 12 shared literals and the 3 dead keys from `thresholds:`.
      - threshold_refs: for the 12 shared keys KEEP the row but change it to
          kind: crtconfig_read   ref: <CRTConfig field>   consumed: true
        (meaning: no literal here; the resolver reads CRTConfig.<ref>). Rewrite the header comment
        block (:371-419) to say wiring is DONE for these keys (it currently says "a separate,
        later, parity-provable phase"). Delete the rows of the 3 dead keys.
      - Update validate_crt_threshold_refs (registry/__init__.py:594) ONLY as needed to accept
        kind crtconfig_read for a key that is absent from `thresholds:` and still require its
        `ref` to be a real CRTConfig field. Nothing else in that file changes.
 4. Callers: pass instrument= at every construction. Use the instrument the caller already has
    (argument / CLI arg / variable). If the caller is XAUUSD-only with no variable, pass
    instrument="XAUUSD" explicitly. List each call site and what you passed.
    Special cases -- report what you did for each:
      - Callers that tune a SHARED key through a custom YAML/config_path (e.g.
        tests/test_crt_state_resolver_sweep_geometry.py:67 range_atr_period=4, :395 body_ratio_min)
        must instead pass crt_config=dataclasses.replace(get_prod_config("XAUUSD"), <field>=<v>)
        (CRTConfig is a frozen dataclass, src/config_layer/state_identity.py:136-137). Keep every
        assertion's meaning; do NOT weaken or delete an assertion. If a test cannot be kept
        equivalent: BLOCKED.
      - scripts/research/validate_crt_state_resolver.py has an interactive "set <key> <value>"
        (:560). For a shared key it must rebuild the resolver with a replaced crt_config, or
        refuse with a clear message. Say which.
      - scripts/research/crt_state_confusion_matrix.py (the F-069 threshold sweep): if it sweeps
        a shared key via YAML, route it through crt_config the same way; if that is not possible
        without redesign: BLOCKED, report.
 5. New tests (in tests/test_crt_threshold_refs.py or tests/test_resolver_metadata.py):
      - neither arg -> raises; both -> raises
      - a YAML that still carries a shared key -> raises
      - CRTStateResolver(instrument="XAUUSD") thresholds equal get_prod_config("XAUUSD") for all 12
      - a replaced crt_config (e.g. body_ratio_min=0.9) reaches the resolver's threshold

ACCEPTANCE (paste outputs):
  a. The 12 values printed from get_prod_config("XAUUSD") at BASE (step 0) equal Claude's list.
  b. After: build_and_cache on the full corpus again -> results/wpj/after/. states.csv
     BYTE-IDENTICAL to results/wpj/before/states.csv (sha256 of both). meta.json: list every
     differing key; only built_at/timing and the new config-source field(s) may differ.
  c. Every test file above: after-counts vs step-0 counts. No test that passed at BASE fails.
  d. python scripts/maintenance/check_governance_invariants.py --all : failed/passed counts at
     BASE and after; list any NEW red (Claude measured 15 failed at the Wave 4 commit, all pre-existing).
  e. python scripts/analysis/feature_math_lint.py : same result as at BASE.
  f. Each owned script: python <script> --help (or import, if it has no CLI) succeeds.
  g. grep in the worktree: no remaining CRTStateResolver() call without instrument= or
     crt_config= anywhere under src/, scripts/, tests/.
  h. git status --short shows only owned files (plus results/wpj/, which you do NOT commit).
```
