## Design Document Review: Coding-LLM Reasoning Context Pack — CREATE Join Defect on `run_20260909_202201`

### Summary
**Needs revision.** The design is directionally right, source-verified on the hard repo facts (surfaces, funnel, four-arm numbers, CAD status, clocks, change class), and an engineer could implement from Appendix A after two identity-hygiene fixes. Do not copy Appendix A as-is: it invents a `variant_id` that does not exist on `scoreboard.json`, and its `has:` block is not a strict projection of `schema_bridge.has`.

### Issue 1: Appendix `variant_id` mints a population token the scoreboard does not name
- **Severity**: major
- **Section**: Proposed Design §4 (Identity selectors table); Key Decision 5; Appendix A `sparse_contexts.resolver_memory`
- **Description**: The body says resolver `variant_id` values are “research arm ids already named by `scoreboard.json` `standing_contract` (`resolver_memory` / `resolver_trendbias`)” and “They are not `MC-*` and not `F-*`.” Appendix A then sets `variant_id: resolver_memory_strict_memory`. That string occurs **nowhere** in the repo (grep over `D:\Tradelatest` is empty). `scoreboard.json` `standing_contract` keys are `resolver_memory` and `resolver_trendbias`; arm titles are `Resolver-Memory` / `Resolver-TrendBias`. `context.schema.yaml` treats `variant_id` as an IDENTITY selector when `state_producer=resolver` (required_when, forbid pooling across `variant_id`). Shipping the invented token would create a second name for the same population — the exact “same label, different population” defect class the schema exists to prevent. Key Decision 5 and Appendix A currently contradict each other.
- **Suggestion**: In Appendix A (and any body table that repeats it) set `variant_id: resolver_memory` and `variant_id: resolver_trendbias` exactly as `standing_contract` keys. Put `strict_memory` in `notes:` only. Add a pack-local forbid: do not concatenate arm adjectives into a new `variant_id`.
- **Status**: addressed
- **Response**: Appendix A and the §4 identity table now use `variant_id: resolver_memory` / `resolver_trendbias` exactly. `strict_memory` is notes-only. Pack-local forbid + token `mint_variant_id_adjective` added. Key Decision 5 rewritten so it no longer contradicts the appendix.

### Issue 2: Appendix `has:` is not a strict projection of `schema_bridge.has`
- **Severity**: major
- **Section**: Proposed Design §1 / §8; Appendix A `has:`; Non-goals (“Use **has** only. Missing slots stay omitted.”)
- **Description**: Registry `docs/governance/run_linkage_registry.json` `XAUUSD.run_20260909_202201.schema_bridge.has` has a closed key set (corpus/dataset/CAD/cost/scoreboard/census pointers). Appendix A copies those, then **adds** `active_version`, `source_parquet_config_version`, and `resolve_artifacts` under the same `has:` map. Those facts are true (ACTIVE_VERSION file is `v2_htfcrt_2026_08`; scoreboard provenance `source_config_version` is `v4_dual_construction_2026_09`; `resolve_artifacts` is `method=registry`, `resolved_run=null` — verified in `src/utils/run_linkage.py` and `tests/test_run_linkage.py`). Putting them under `has:` still mints slots the registry does not carry. A successor that treats pack `has` as `schema_bridge.has` will believe those keys are registry-addressable. That violates the pack’s own “has only / missing slots omitted / do not invent” rule and the registry `_doc` (“missing slots are omitted, never invented”).
- **Suggestion**: Split Appendix A into (1) `registry_has:` — byte-key copy of `schema_bridge.has` for this `run_id`, no extras; (2) `identity_facts:` — ACTIVE_VERSION, source parquet `config_version`, `resolve_artifacts` shape. Keep `contract_id` / `MC-*` / `mt00` / `mx_id` / `finding_id` / `record_id` omitted. PR-3 still adds only `has.coding_llm_context_pack` (a real file pointer, same shape as `has.scoreboard`).
- **Status**: addressed
- **Response**: Appendix A `has:` split into `registry_has` (strict copy of today’s `schema_bridge.has` keys, no extras) and `identity_facts` (`active_version`, `source_parquet_config_version`, `resolve_artifacts`). §8 body tables match. PR-3 still adds only `has.coding_llm_context_pack` and then mirrors that key into pack `registry_has` so the projection stays equal.

### Issue 3: PR-1 understates `DOCUMENTATION_ONLY` required checks
- **Severity**: minor
- **Section**: PR Plan / PR-1; Rollout Plan step 2
- **Description**: PR-1 classifies as `DOCUMENTATION_ONLY` and says required checks are “doc floors that do not require a findings-table row (`tests/test_doc_citations.py` if any `path:line` citations are added; otherwise the YAML is citation-free).” `docs/governance/change_contracts.json` `DOCUMENTATION_ONLY.required_checks` is the set `{tests/test_current_findings.py, tests/test_doc_citations.py, tests/test_topic_docs.py}`. `construction_protocol.py validate-completion` **executes** that full set (never log-trusted) and requires `required_checks_ack` to cover it. An engineer following PR-1 literally will fail `validate-impact` for unacked checks, or skip two floors. The YAML itself should not trip those tests (no F-id, no topic doc, citation-free) — the gap is the PR contract, not a predicted red.
- **Suggestion**: PR-1 `required_checks_ack` list all three DOCUMENTATION_ONLY floors plus `scripts/governance/construction_protocol.py validate-completion`. Keep “do not add a findings row.” Name a real `change_id` instead of `<change_id>` (e.g. `CH-coding-llm-context-pack-yaml`).
- **Status**: addressed
- **Response**: PR-1 `change_id` is `CH-coding-llm-context-pack-yaml`. `required_checks_ack` lists `tests/test_current_findings.py`, `tests/test_doc_citations.py`, `tests/test_topic_docs.py`, and `construction_protocol.py validate-completion` on that manifest. Still no findings row.

### Issue 4: PR-2 pointer text is unspecified; owning note still advertises INVALIDATED cells
- **Severity**: minor
- **Section**: Proposed Design §10; PR Plan / PR-2; Background “Chat is not a pin”
- **Description**: PR-2 says “one load-first line under the CORRECTED 2026-09-10 banner” but does not give the sentence. `docs/research/phase1_shadow_create_economic_census_note.md` already has the CORRECTED banner, then **still prints** Headline H20 (`memory_dir` n=65 E=−0.1577, `always_long` n=69 E=+0.5650) and age-bucket H20. The design’s motivation is that prose banners are skipped and JSON looks like results — the same trap remains in the owning markdown after a one-line see-also. The pack’s refuse list cannot fire if the successor never loads it and quotes the note table instead.
- **Suggestion**: Specify the three exact pointer sentences in PR-2 (census / evidence / timing-race). On the census note only, add a one-line `DO_NOT_CITE` / `surface=create_H20_context_economics INVALIDATED` immediately above the Headline H20 and bucket tables. Do not delete the tables (history preserved). Do not rewrite the CORRECTED banner.
- **Status**: addressed
- **Response**: §10 now quotes the exact census / evidence / timing-race sentences, plus `DO_NOT_CITE` lines above Headline H20 and `## age_at_reset`. Tables kept. CORRECTED banner not rewritten. Those note edits ship in merged PR-1 (Issue 12).

### Issue 5: Load-contract refusal phrase does not match `required_before`
- **Severity**: minor
- **Section**: Proposed Design §2 Load contract; Appendix A `load_first`
- **Description**: `load_first.required_before` includes “four-arm / session / HTF / parent / H20 claims about this run.” `if_not_loaded.phrase` is only “CREATE-context inference refused….” Section 2 then says four-arm H20 “may still be cited **after** the pack is loaded” because those surfaces are VALID. An implementer cannot tell whether citing four-arm without the pack is REFUSE or allowed-with-warning. The admit algorithm refuses if the pack is not loaded for `claim.run_id` with no four-arm exception.
- **Suggestion**: Split refusal: (a) CREATE-context / session / HTF / parent / CREATE-H20 → REFUSE with the existing phrase; (b) four-arm economics/H20 without pack → REFUSE with a distinct phrase (`four-arm citation refused: pack not loaded; surfaces are VALID but coverage pooling is the failure mode`). Keep four-arm ADMIT after load when the named surface is VALID and unmixed.
- **Status**: addressed
- **Response**: Load contract, admit algorithm, and Appendix A `load_first.if_not_loaded` now split phrase A (CREATE-context…) vs phrase B (four-arm citation refused… coverage pooling). After load, four-arm ADMIT only when the named surface is VALID and unmixed.

### Issue 6: Two join tokens for the same defect, unexplained
- **Severity**: minor
- **Section**: Appendix A `has.create_census_context_join` vs `index_join.create_census_join`; Proposed Design §6
- **Description**: Census `index_join.create_census_join` is `ENGINE_CANDLE_INDEX` (verified `census.json` line 4945). Registry `has.create_census_context_join` is `ENGINE_CANDLE_INDEX_PLUS_62`. Appendix A copies **both**. That is source-faithful, but a successor can read them as two different joins. They name the same defect (engine `candle_index` stored in a CSV-index field; offset 62 on all 69).
- **Suggestion**: Add one line under `index_join`: `same_defect_as_registry_has: create_census_context_join=ENGINE_CANDLE_INDEX_PLUS_62`. Do not collapse the strings; registry and census remain sources of truth.
- **Status**: addressed
- **Response**: Added `index_join.same_defect_as_registry_has: create_census_context_join=ENGINE_CANDLE_INDEX_PLUS_62` in Appendix A and a two-token table in §6. Strings not collapsed.

### Issue 7: Event-native `pending_dir` labels omit the four unlabeled rows
- **Severity**: minor
- **Section**: Proposed Design §3 mixing examples; §7; Appendix A `two_clocks` / `authoritative_numbers`
- **Description**: The mixing example treats `pending_dir SHORT 39` as a usable label count. On-disk `census.json` `rows` (n=69) are `SHORT=39, LONG=26, None=4` (counted). The H20 `pending_dir` bucket table is the same 39/26 because it drops unlabeled rows — and that table is `create_H20_context_economics` INVALIDATED. Quoting n=39 as if it were a complete event-native census of the 69 launders a H20-table denominator. Labels are still usable; the missing four are not.
- **Suggestion**: Record `pending_dir_event_native: {SHORT: 39, LONG: 26, unlabeled: 4}` under authoritative numbers as labels only. Keep E/PF/WR on pending_dir in the refuse list. Do not cite 39/26 from `bucket_tables_H20_memory_dir`.
- **Status**: addressed
- **Response**: Counted on `census.json` rows: 65 labeled keys + 4 rows omitting `pending_dir`. Recorded `{SHORT: 39, LONG: 26, unlabeled: 4}` under §7 and Appendix `authoritative_numbers.pending_dir_event_native`. Mixing example no longer treats n=39 as a complete census of 69. E/PF/WR on pending_dir remains INVALIDATED.

### Issue 8: PR-3 test pin is described, not specified; change_id is a placeholder
- **Severity**: minor
- **Section**: API / Interface Changes; PR Plan / PR-3
- **Description**: PR-3 is the right third step (YAML exists → `has` pointer → pin `surfaces`). An engineer still has to invent: the `change_id`; the exact assertion set; whether the test **opens** the YAML or only compares the path string. `TRACE_OBSERVATION_JOIN.required_checks` in `change_contracts.json` are `test_crt_construction_trace.py`, `test_crt_construction_trace_envelope.py`, `test_resolver_metadata.py`, `test_construction_protocol.py` — they **will** run, not “if demanded.” That is the CH-runid-schema-bridge precedent (`docs/governance/build_manifests/CH-runid-schema-bridge.impact.json`); the “if” in PR-3 is misleading. `src/utils/run_linkage.py` lines 179–180 already pass `schema_bridge` through — verified, no `src/` edit expected.
- **Suggestion**: Name `CH-coding-llm-context-pack-has` (or similar). Require `required_checks_ack` to list the four TRACE_OBSERVATION_JOIN floors **plus** `tests/test_run_linkage.py`. Specify assertions: `has["coding_llm_context_pack"] == "docs/research/phase1_run_20260909_202201_coding_llm_context.yaml"`; `surfaces` key→token map equals registry (VALID ×5, INVALIDATED ×3, `rebuild_completed is False`, `join_logic_fixed_for_future_rebuild is True`); omitted-ID assertions unchanged; optional read of YAML `trust_table` vs registry (registry wins). If `run_linkage.py` diffs, STOP.
- **Status**: addressed
- **Response**: PR-3 `change_id` is `CH-coding-llm-context-pack-has`. `required_checks_ack` lists the four TRACE_OBSERVATION_JOIN floors plus `tests/test_run_linkage.py` and states they **will** run. Assertions copied as specified. `run_linkage.py` diff → STOP.

### Issue 9: Expire-row `12:15` is derived, not a field on `expire_rows_timing[0]`
- **Severity**: nit
- **Section**: Proposed Design §5 Two clocks; Appendix A `two_clocks.clock_a_engine_candle_timestamp.expire_row_0`
- **Description**: `memory_timing_race.json` `expire_rows_timing[0]` has `hour_broker_local=12`, `session_hour_bucket_broker_local=LONDON_8_13`, `created_idx=1073`, `expire_idx=1077` — **no `timestamp` key**. `2024-06-07 12:15:00` is inferred (CREATE event `2024-06-07T11:15:00` + 4 M15 bars). CSV bar 1139 is `2024-06-07 12:15:00` (verified), so the derivation is correct on this row, but presenting it as a stored probe field is slightly stronger than the artifact.
- **Suggestion**: Label it `derived_expire_ts_from_create_plus_4_m15: "2024-06-07 12:15:00"` and keep `hour_broker_local: 12` as the on-disk field. Do not mix that derivation with census parquet session.
- **Status**: addressed
- **Response**: Appendix `expire_row_0` now uses `derived_expire_ts_from_create_plus_4_m15` and keeps `hour_broker_local: 12` as the on-disk field, with a note that `expire_rows_timing[0]` has no `timestamp` key. Mermaid, pain-point 2, and Key Decision 7 match.

### Issue 10: Appendix `existing_f_ids_cited_not_minted` is a subset of the body
- **Severity**: nit
- **Section**: References; Appendix A `existing_f_ids_cited_not_minted`
- **Description**: Body/References cite F-066, F-069, F-077, F-079, F-083, F-098. Appendix lists only F-066, F-069, F-077, F-098. F-079/F-083 are the silent-gap analogies (skipped load ≡ absent gate). Omitting them from the copyable instance is not a minting error; it is a drift surface between pack and design.
- **Suggestion**: Either add F-079 and F-083 to the appendix list as cited-not-minted, or state in the pack that analogical F-ids live only in the design doc.
- **Status**: addressed
- **Response**: Chose to add F-079 and F-083 to Appendix `existing_f_ids_cited_not_minted` so pack and design do not drift. Still cited-not-minted.

### Issue 11: CREATE Context sketch `structure: {}` vs schema-required structure fields
- **Severity**: nit
- **Section**: Proposed Design §4 sparse CREATE sketch; Appendix A `sparse_contexts`; `context.schema.yaml` `fields.structure.required: true`
- **Description**: `context.schema.yaml` requires `structure` with named booleans (`breaker_present`, …). The body sketch uses `structure: {}`. Appendix CREATE / engine / resolver sketches omit `structure` entirely. The pack correctly says these are **not** sealed Contexts (no `contract_ref`, ODP key not satisfied). Empty `{}` is the one form that looks like a filled Context and would fail the schema if copied into an instance later.
- **Suggestion**: Drop `structure:` from the body sketch to match Appendix A. Keep a one-liner: sketches are not schema-valid Context documents; `structure` stays omitted (not empty).
- **Status**: addressed
- **Response**: Dropped `structure: {}` from the §4 body sketch. One-liner added: sketches are not schema-valid Context documents; `structure` stays omitted (not empty). Appendix A already omitted it.

### Issue 12: Three PRs are independently reviewable but PR-1+PR-2 are a single docs commit in practice
- **Severity**: nit
- **Section**: PR Plan; Rollout Plan
- **Description**: Ordering is correct (YAML path must exist before note pointers and before a test that opens the file). Splitting “add file” from “three one-liners” is ceremony. Not wrong. Collapsing PR-1+PR-2 still leaves PR-3 as the TRACE_OBSERVATION_JOIN boundary, which is the load-bearing split (docs vs registry+test).
- **Suggestion**: Keep PR-3 separate. Optionally merge PR-1 and PR-2 into one DOCUMENTATION_ONLY commit if the user prefers less process. Do not merge PR-3 into the docs PRs.
- **Status**: addressed
- **Response**: Chose merge: PR-1 is YAML + note pointers (`DOCUMENTATION_ONLY`, `CH-coding-llm-context-pack-yaml`). PR-3 stays the separate `TRACE_OBSERVATION_JOIN` (`CH-coding-llm-context-pack-has`). No third docs PR.

### Strengths
- **Repo-specific facts are correct** (verified, not taken on faith):
  - `context.schema.yaml` v0.5.0: Context is a join key, not `S_t`; `state_producer` required; Engine EXP ≠ Resolver EXP (F-069 88.16%, injection=none).
  - `schema_bridge.surfaces` for `run_20260909_202201`: VALID `four_arm_economics`, `four_arm_H20`, `create_lifecycle_counts`, `create_timing_race_counts`, `create_age_at_reset_distributions`; INVALIDATED `create_session_hour_tables`, `create_htf_parent_context_tables`, `create_H20_context_economics`; `rebuild_completed: false`.
  - `census.json` `index_join`: `four_arm_path=CSV_PARQUET_BAR_INDEX`, `create_census_join=ENGINE_CANDLE_INDEX`, `offset_csv_minus_engine=62`, `n_creates_offset_checked=69`, `offset_constant=true`, `do_not_infer` list matches the design.
  - Funnel: 69 = 45 EXPIRED_TTL + 18 CLEARED_OR_OVERWRITTEN + 6 RESTORED_TO_EXPANSION; raw 45 EXPIRE + 17 CLEAR + 1 OVERWRITE + 6 RESTORE. Not “17 CLEAR” as the remainder.
  - Four-arm table matches `scoreboard.json` / evidence note (n, coverage %, E, PF, WR rounded as in the note). Coverage denominator 47255. Never 31/148. Engine EXP 148 ≠ Resolver EXP 31. Direction agree 0/31. Case A interpretive only.
  - CSV verified: bar 785 = 2024-06-03 15:45:00 O=2333.18 C=2334.07; bar 1073 = 2024-06-06 18:45:00 (misjoin); bar 1135 = 2024-06-07 11:15:00 (true CREATE).
  - CAD `decision_status` is `FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION`, not UNRESOLVED (`run_linkage_registry.json` + `XAUUSD_MT5_PHASE1_20260521.json`).
  - Two clocks: timing-race `hour_bucket(e["timestamp"])` vs census parquet-join on `created_idx`; expire row 0 Clock A `LONDON_8_13` / hour 12 vs census `NY_17_22` / hour 18.0.
  - `age_at_reset` VALID as engine-domain ages; H20 on those buckets INVALIDATED. CREATE `parent_crt` selector inadmissible until rebuild.
- **Change-class honesty is right.** YAML+notes = `DOCUMENTATION_ONLY`. `has` pointer + test = `TRACE_OBSERVATION_JOIN` (same class and rationale as `CH-runid-schema-bridge`). Not `RUNTIME_DECISION_PATH_CHANGE`. `production_behavior_changed: NO`. Rebuild is not a PR.
- **Appendix A is copyable YAML** (not an examples/ stub, not results/-only). `does_not_replace: [Context, MeasurementContract, Finding, ODP]` plus omitted ID slots prevents a fifth chain artifact. Future join rule is specified (`created_idx` = event timestamp → CSV `bar_index`; keep `engine_candle_index`; age stays engine-domain) and `assemble_creates` already implements it; `rebuild_completed` stays false.
- **Key Decisions 1–4, 6–12 are complete and consistent** with ontology, registry, and the freeze. Decision 5 is the exception (see Issue 1).
- **Alternatives A–D are real.** Pin-only is the status quo that already failed; rebuild is unauthorized; minting F-*/MC-* is forbidden; the pack is the remaining control. Trade-offs (drift, ignored load contract, pack-as-MC) are named with mitigations.
- **PR order is realistic:** tracked YAML → note pointers → registry `has` + surfaces pin. No rebuild PR. No production/config/spine. Rollback is delete/revert. Residual risk (successor ignores the pack) is stated as High for knowledge / None for spine — accurate for a social-mechanical gate.
- **Forbidden-inference token list is specific enough to implement** (coverage 31/148, clock mix, 6/6 restore, dashboard `resolved_run=null`, attach H20 to valid ages, treat pack as MC).

---

## Revision Summary

Date: 2026-09-10. All 12 open issues addressed in `grok-design-doc-e5b36c92.md`. No `wontfix`. No `needs-user-input`. CREATE context not rebuilt. No F-* / MC-* minted.

| Issue | What changed |
|---|---|
| 1 major | `variant_id` is `resolver_memory` / `resolver_trendbias` (standing_contract keys). `strict_memory` notes-only. Forbid concatenating arm adjectives. |
| 2 major | Pack `has:` split into `registry_has` (strict `schema_bridge.has` copy) and `identity_facts` (ACTIVE_VERSION / parquet config_version / resolve_artifacts). |
| 3 minor | PR-1 `change_id=CH-coding-llm-context-pack-yaml`; acks all three DOCUMENTATION_ONLY floors + `validate-completion`. |
| 4 minor | Exact pointer sentences in §10; `DO_NOT_CITE` above Headline H20 and age-bucket tables; tables kept. |
| 5 minor | Split refusal phrases A (CREATE-context) vs B (four-arm without pack / coverage pooling). Four-arm ADMIT after load if VALID+unmixed. |
| 6 minor | `index_join.same_defect_as_registry_has: create_census_context_join=ENGINE_CANDLE_INDEX_PLUS_62`. Strings not collapsed. |
| 7 minor | `pending_dir_event_native: {SHORT: 39, LONG: 26, unlabeled: 4}` as labels only. |
| 8 minor | PR-3 `change_id=CH-coding-llm-context-pack-has`; TRACE floors + `test_run_linkage.py` will run; assertions specified; `run_linkage.py` diff → STOP. |
| 9 nit | Expire 12:15 labeled `derived_expire_ts_from_create_plus_4_m15`; `hour_broker_local=12` is the on-disk field. |
| 10 nit | F-079 and F-083 added to Appendix cited-not-minted list. |
| 11 nit | Dropped `structure: {}`; sketches omit `structure` (not empty). |
| 12 nit | Merged former PR-1+PR-2 into one DOCUMENTATION_ONLY PR-1. PR-3 stays separate TRACE_OBSERVATION_JOIN. |

Appendix A remains copyable to `docs/research/phase1_run_20260909_202201_coding_llm_context.yaml`.
