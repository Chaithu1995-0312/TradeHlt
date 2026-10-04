# SHIP — Fail-closed Path A (four CRTConfig keys)

**Shipped:** 2026-09-20 (branch `grokbotchanges`)
**Scope:** declare/load only for `body_ratio_min`, `atr_multiplier_min`, `expansion_atr_min_distance`, `retest_depth_max`. Missing key = fail closed. No silent `.get(..., default)`.

## Verification (sufficient; full-suite name-diff deferred)

| Check | Result |
|---|---|
| P2.5 reachability | Prod fallbacks dormant for the four keys when YAML/prod present |
| J-file 13 SIGNAL | Fixture-incomplete `PERMISSIVE`; padded → **13/13 green** |
| Unexpected-A in ~30% window | None beyond expected classes |
| Full-suite BEFORE/AFTER | Deferred — harness hang class (STORY_PYTEST_HANG_CLASS_01); not an A blocker |

## Named reds / residuals that travel with the ship

1. **Provenance bare `CRTConfig()`** — STORY_PARAM_AUDIT_01_ADDENDUM (deferred design Q: schema vs loaded fingerprint)
2. **Census drift** — DRIFT_PARAM_CENSUS_01 (pre-existing)
3. **Reachability matrix drift** — DRIFT_PARAM_REACHABILITY_01 (pre-existing)
4. **Helper soft-fill** — STORY_PARAM_AUDIT_01_HELPER (residual; does not block A)
5. **Pytest hang class** — STORY_PYTEST_HANG_CLASS_01 (harness track; separate)

## Code surface

- `src/config_layer/state_identity.py` — four fields required (no defaults)
- `src/features/crt_state_resolver.py` — `thr[key]` not `.get`
- `tests/helpers/crt_config.py` — test helper
- `tests/Claude/_fixtures.py` (+ Grok) — `PERMISSIVE` pad for required keys
- scripts/tests touching construction census / provenance as needed

## Explicitly not in this ship

- HTF clock structural-break trigger (next track; W already ≥12 via `htf_candles_per_range=16` on active prod config)
- Full-suite conditioned DIFF_COMPLETE
- Soft-fill helper hardening A/B/C
