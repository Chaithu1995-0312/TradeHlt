# Target Strategy Architecture — Compliance Check

## Context

The user asked for a compliance check of the codebase against
[`docs/architecture/target-strategy-architecture.md`](../../../D:/Tradelatest/docs/architecture/target-strategy-architecture.md)
("target architecture" — TSA), the repo's "city plan" doc. TSA is not read-only reference; it carries
a live `§14 Not yet built / incomplete checklist` (40+ checkboxes with explicit `[x]`/`[ ]` claims) and
a `§10 Current vs Target` table, last updated **2026-07-28**. Per CLAUDE.md §1.1 (Evidence &
Verification Discipline) and §6.2 (Repository Truth Maintenance Doctrine), a doc's own checkmarks are
not evidence — every claim has to be re-verified at source before being trusted, and any drift found
must be classified (`ALIGNED` / `DOC_DRIFT` / `CODE_DRIFT` / `AMBIGUOUS`) per rule 2, never silently
resolved per rule 3.

Three parallel Explore agents source-verified every checkable claim in TSA §14.A–G plus checked for
structural drift the doc predates (findings F-073…F-078, F-076 land after the doc's last edit).

## Findings — TSA's own checklist (23 checkable items)

**Result: 23/23 ALIGNED.** Every `[x]` in §14.A–F still matches source; every `[ ]` is still correctly
unchecked. No self-contradiction found in the doc's own bookkeeping.

| § | Claim | Verdict | Evidence |
|---|---|---|---|
| 14.A.1 | F-057 `market_router` config-driven, `ConfigBuilder` authoritative on programmatic path | ALIGNED | `src/config_layer/market_router.py:44-45,66,89-105,109` |
| 14.A.2 | Unknown instrument fail-closed (`UnknownInstrumentError`, no FOREX default) | ALIGNED | `market_router.py:36,76,111` |
| 14.A.3 | F-058 `engine_gate_enabled`/`bypass_zone_invalid` config-declared, strict-read, env WARNs on disagreement | ALIGNED | `src/runtime/backtest_v2.py:136-145,2507-2520,2528-2541` |
| 14.A.4 | `ledger_parity.py` proves programmatic == CLI ledger | ALIGNED | `scripts/analysis/ledger_parity.py:1-26` |
| 14.A.5 | Behavior-census corpus widened by "runtime + 3 more" | ALIGNED | `scripts/analysis/behavior_census.py:64-71` — `{core,engines,config_layer}` + `{features,runtime,journal,governance}` = exactly +4 |
| 14.B (unchecked) | No F/T/D/R/E section-mapping doc exists | ALIGNED (still open) | repo-wide grep — only the checklist line itself matches |
| 14.C.1–2 | `StrategyPackage` shape + `content_hash()`/`config_hash` | ALIGNED | `src/strategies/strategy_package.py:43-49,62-66,102,111` |
| 14.C.3 (unchecked) | Research harness has zero `StrategyRegistry`/`strategy_id` refs | ALIGNED (still open) | `src/research/{config,runner,cli}.py` — no matches |
| 14.C.4 | Package doesn't redefine ontology FMs | ALIGNED | `strategy_package.py:8`, `strategy_registry.py:1-13` |
| 14.D.1 | `provenance.py` deliberately excludes `strategy_id` (no such `ResearchConfig` field) | ALIGNED | `src/research/provenance.py` docstring; `ResearchConfig` fields ~L24-75 |
| 14.D.2 | `job_kind ∈ {threshold_search, model_retrain, unspecified}` enforced | ALIGNED | `src/research/config.py` |
| 14.D.3 | Zero `configs/production` refs in `src/research/*.py` | ALIGNED | grep clean |
| 14.E.1 | `use_bitnet: false` on active config | ALIGNED (see drift below re: *which* file) | active config `.use_bitnet` = `false` |
| 14.E.2 | `model_shadow_protocol.py` generalizes the BitNet-only shadow driver | ALIGNED | docstring + `--label` param confirm genuine generalization |
| 14.F.1–4 | `feature_vector_sha`/`gates_fired` present on backtest, absent on live; `_build_provenance_base` shared; live `trade_id` still synthesized `f"{symbol}_{candle_idx}"` | ALIGNED | `backtest_v2.py:3122,3083-3123,1872,1966`; `live_engine_hook.py:1245-1246,830` — no `feature_vector_sha`/`gates_fired` matches in live |
| 14.G (unchecked) | `market_shapes.yaml`/`market_crt_states.yaml` stay research/resolver-only, no new production wiring | ALIGNED | all hits confined to `src/features/market_shape.py`, `crt_state_resolver.py`, `crt_construction_trace.py` — none in the backtest/live decision path |

## Findings — drift the doc doesn't know about (post-2026-07-28)

These are **not** contradictions of anything TSA asserts — they're gaps: things that changed in the
6.5 weeks since, that TSA's diagrams/tables would need to reflect to stay accurate for a reader.

| Item | Verdict | Evidence | Why it matters |
|---|---|---|---|
| **`ACTIVE_VERSION`** | DOC_DRIFT | `configs/production/ACTIVE_VERSION` = `v2_htfcrt_2026_08`, not `v2_multi_2026_04` (TSA §8 example, CLAUDE.md §4.0 both assume the old value); current branch is `feature/trace-parquet-duckdb-query`, not `patch` | Low-risk — stale example/reference, not a structural claim |
| **`docs/reference/config-reference.md`** | DOC_DRIFT (worse) | Still cites `v1_multi_2026_03.json` as "the single source of truth" (line 3) — two versions further behind than TSA itself | Same class, different doc — flagging for completeness, out of TSA's own scope |
| **Feature schema dimension** | Silent drift (AMBIGUOUS, not a false claim) | `src/features/feature_schema.py:292,297,305`: `SCHEMA_VERSION = "5.0"`, 48-dim (`+9 SMC primitives`, per F-076, 2026-08-20ish) vs TSA's implicit "canonical feature vector" references (§2) which never state a dimension count | TSA never says "38-dim," so it isn't technically wrong — but it also gives a reader no signal the vector grew, right where F-076 says "all 6 model families now stale on ≤39-dim schemas" |
| **Parent-CRT / HTF-CRT construct (F-075/078)** | **DOC_DRIFT (structural, most significant finding)** | `CRTState` 9→12 states (`state_identity.py:15`), `parent_crt.enabled` gating reachable from `BacktestRunner` (`backtest_v2.py:2380,2394,3487`, `crt_engine_v2.py:2687,3355`, `runtime/parent_crt_feed.py:153`) — **zero** mentions of "parent"/"HTF"/"ParentCRT" anywhere in TSA §2 (CRT topology, declared STRUCTURAL/frozen), §7 (production spine), or §16 (summary diagram) | TSA explicitly freezes "CRT state **topology** / legal transitions" as STRUCTURAL and shows it as a single dimension. A second CRT dimension is now live-reachable and entirely undocumented in the city-plan doc — this is the kind of split the doc exists to prevent |
| **No production live execution rail (F-073)** | DOC_DRIFT | TSA §7 shows "Target live trading path" and "Today live path" both terminating in `Execute`/`live/backtest` with no caveat; F-073 (OPEN since 2026-08-19) confirms only paper callers exist (`LiveRailOrchestrator`, `--paper` mode), `ACTIVE_VERSION` has no `live_rail` | A reader following §7 could believe a live rail exists; it doesn't |

## Overall verdict

**The doc is honest about itself** (23/23 self-checks hold) but **stale about the world around it** —
all drift is code/config that moved forward after 2026-07-28 without a corresponding TSA update, which
is exactly the "documentation entropy" failure mode CLAUDE.md §6.2 is designed to catch. No
`TruthConflict` (rule 3) was found — every item resolves cleanly to one side, none are ambiguous
authority disputes.

## Recommended next step (per CLAUDE.md §6.2 Documentation Drift Protocol — gated, not silent)

Per the protocol's gate calibration: *auto-fix* unambiguous drift that changes no registered
conclusion; *require approval* for anything touching structural claims or an active-config reference.

- **Auto-fixable (no approval needed):** update TSA's `ACTIVE_VERSION` example/filename references
  (§8, §10, §14.E.1's caveat) from `v2_multi_2026_04` → current; these are stale pointers, not
  conclusions.
- **Requires your approval before I touch it** (structural / could read as changing what TSA asserts):
  1. Add the parent-CRT/HTF-CRT construct to TSA §2 (topology) and §7 (spine) — this is a genuine
     addition to a section TSA calls STRUCTURAL/frozen, not a typo fix.
  2. Add a caveat to TSA §7 that no production live rail exists yet (mirrors F-073).
  3. Note the 48-dim/v5.0 schema next to TSA's "canonical feature vector" language so it doesn't read
     as silently behind F-076.
  4. Whether to also flag `docs/reference/config-reference.md`'s deeper staleness (out of TSA's own
     scope, found incidentally).

I have not edited anything — this plan is the compliance report itself. On approval I'll make the
edits above as surgical, additive changes to TSA (never touching production code/config), record a
Documentation Drift Protocol audit-trail entry, and append the CLAUDE.md §7.4 SESSION LOG block.

## Verification

- Re-run the same grep/read checks in the table above against current source to confirm each verdict.
- After any doc edit: `pytest tests/test_doc_citations.py` (±30-line citation window) and
  `python scripts/maintenance/check_governance_invariants.py --all` (GREEN_FLOOR) still pass, since
  TSA is test-enforced infrastructure per CLAUDE.md's "Editing THIS file is test-enforced" note (that
  note is about CLAUDE.md itself, but the same citation-sync test (`tests/test_doc_citations.py`)
  covers `path:line` citations repo-wide, including TSA's).
