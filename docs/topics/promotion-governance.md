# Topic: Promotion / Governance

> **Topic-visibility unit.** The only path to production. How a validated config becomes the live
> config — with an APPROVE gate, SHA-256 hashing, and an append-only audit trail.
>
> Created: 2026-06-01 · Updated: 2026-06-03 (v4 governed cutover — full-config session-override promotion) · Status: living

## In plain language
`PromotionManager` is the gate between a validated config and production. It refuses to promote
anything whose `ValidationReport.decision != "APPROVE"`, and — when given the CSVs — **re-runs
validation** before promoting so a stale or hand-edited report can't sneak through. Every
promotion (success or failure) is written to an append-only log, and the promoted config is
SHA-256 hashed so production always knows exactly what's running. There is no other way in.

## Code covered
- [`src/governance/promotion_manager.py:97`](../../src/governance/promotion_manager.py) — `PromotionManager` (all operations logged, human-readable). `promote_from_report(report_path, version, csv_paths, notes="")` ([`:104`](../../src/governance/promotion_manager.py)): **GAP-4 fix** rejects any non-APPROVE report ([`:140`](../../src/governance/promotion_manager.py)); re-runs `ConfigValidator.validate()` on the report's `params` to confirm currency ([`:155`](../../src/governance/promotion_manager.py)). Sibling APIs (per `governance.md`): `promote_from_tuner_checkpoint`, `promote_direct`, `list_versions`, `load_version`.
- **Audit:** `configs/promotion_log.jsonl` — append-only `PROMOTED` / `PROMOTION_FAILED` / `VALIDATED_READY` lines.
- **Merge base (2026-06-02):** `_load_full_base_config` now prefers the **current ACTIVE governed config** as merge base, but only when it is a *section-superset* of the `_BASE_VERSION_FALLBACK` (v1) — so a promotion never silently drops engine sections; logs the base chosen. Previously hardcoded to v1.
- **Integrity guards (2026-06-02):** [`src/governance/config_integrity.py`](../../src/governance/config_integrity.py) — `validation_summary_is_fresh` (fails when `validation_summary.params_fingerprint != sha256(params)` — catches hand-edited params with a stale validation record, which `config_hash` alone misses) and `active_version_is_governed` (ACTIVE_VERSION must be a clean key with a `PROMOTED` log entry). Born from the `v2_multi_2026_04 - deepdeektry` incident: an ungoverned active config with a stale `validation_summary`.
- **Full-config session-override cutover (2026-06-03):** `PromotionManager.promote_*` carries only the 5 flat `params` + metadata and **inherits engine sections from a merge base** — so it *cannot* promote a config whose change lives in `engine_runner` (e.g. `allowed_sessions_overrides`); it would silently drop the override. The governed path for such a change is a **direct full-config write**: validate the changed instrument via `ConfigValidator.validate(..., engine_runner=candidate)`, then write the full config file + flip `ACTIVE_VERSION` + append a `PROMOTED` line + embed `validation_summary.params_fingerprint`. Precedent + repeatable script: [`scripts/maintenance/_promote_v4_bnb_cutover.py`](../../scripts/maintenance/_promote_v4_bnb_cutover.py) (promoted `v4_multi_2026_06` = governed `deepdeektry` lineage + BNBUSDT all-sessions; closed the bypass + both guards green).

## Ins / Outs
- **Ins:** an approved `ValidationReport` JSON path (or tuner checkpoint), a `version` label (e.g. `v1_multi_2026_03`), `csv_paths` for re-validation; config section `governance`.
- **Outs:** promotion result `{status, paths}`; production registry updated; `promotion_log.jsonl` line appended; archived prior config as `{version}_archived_{ts}.json`.

## Entry points & validations
- **Reached via:** CLI `python src/governance/promotion_manager.py promote --checkpoint results/tuner/checkpoint_multi.json --version v2_<label>_<YYYY_MM> --data-dir data/`; also via the agent `promote_*` intents (`PLAN_REGISTRY`).
- **Validated by:** the APPROVE gate (`:140`), mandatory re-validation (`:155`), SHA-256 config hash, and the append-only log. Rollback = restore the archived `{version}_archived_{ts}.json` and re-load.

## Tests
- [`tests/test_shadow_promotion_gate.py`](../../tests/test_shadow_promotion_gate.py) — `ShadowPromotionGate` two-gate flow.
- [`tests/test_sprint7_governance.py`](../../tests/test_sprint7_governance.py) — governance sprint coverage.
- [`tests/test_meta_governor_executor.py`](../../tests/test_meta_governor_executor.py) — `MetaGovernorExecutor`.

## Fits in architecture
The terminal governance feeder that joins the spine off-line (`signal-flow.md` kitchen feeders).
Upstream: [`config-validation.md`](config-validation.md) (the APPROVE source). Authoritative
reference: [`docs/reference/governance.md`](../reference/governance.md). Distinct from *model*
promotion (`ModelRegistry`, see [`docs/reference/training.md`](../reference/training.md)).

## Discussion (filled in-session)
- **Risks:** `2026-06-01` only one production config is active at a time; rollback is manual (restore archive + re-load), so a bad promotion has a recovery delay. No hot-swap (`CLAUDE.md §4`).
- **Challenges:** `2026-06-01` re-validation on promote (`:155`) duplicates backtest cost; necessary for the anti-staleness guarantee but makes promotion slow on many instruments.
- **Blockers:** `2026-06-01` none.
- **Ambiguities:** `2026-06-01` two promotion systems share the word "promote" — config promotion (this topic) vs model promotion (`ModelRegistry`, GOV-3, `PROMOTION_MARGIN=2%`). Keep separate; `governance.md` owns config, `training.md` owns models.
- **Enhancements:** `2026-06-01` the idea-governance framework (`idea-governance-framework.md`) lacks `DEMOTED`/`EXPIRED`/`KILLED` line schemas in `promotion_log.jsonl` (noted in plan `this-is-a-valuable-pure-flurry.md`) — soft demotions currently leave no audit event.
- **Need more info:** `2026-06-01` exact `promotion_log.jsonl` line schemas (PROMOTED/PROMOTION_FAILED fields) — cross-check `schemas.md §9` on next touch.
- **Trd-M4 (2026-06-01):** dependency inversion in the governance/portfolio path — `src/governance/portfolio_validation.py` no longer imports `runtime.backtest_v2` at module level nor **monkey-patches `BacktestRunner.run`**; it now builds the runner via the neutral `core.backtest_port` factory and reads closed trades from the run's CSV via `_read_journal_trades()` (behavior-identical). Same inversion applied to the `config_validator` pre-promotion gate.
