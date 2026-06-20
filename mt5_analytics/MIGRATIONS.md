# mt5_analytics — migration log

Append-only record of changes that alter stored-artifact meaning (so a future reader knows
when a rebuild is required). Schema versions are frozen per record type
(`PositionEpisode` / `FeatureRecord` / manifest / `VerificationReport` / `RunSummary` = `1.0`);
`registry.engine_registry.ENGINE_REGISTRY` stamps engine versions into every artifact.

## 2026-06-19 — UTC timestamp normalization (REBUILD REQUIRED)
**What:** MT5 reports `deal.time` / candle `time` as the trade *server's* wall clock
(MetaQuotes-Demo = EEST/EET, UTC+3) labelled as UTC. `core/mt5_adapter` now auto-detects the
server↔UTC offset at connect and normalizes **both** deals and candles to **true UTC** (query
bounds + returned times), uniformly, so deal↔candle alignment — hence reconstruction / MFE /
duration — is unchanged; only absolute timestamps (and therefore session/hour features) are
corrected. Override: `analytics.json:server_utc_offset_hours` (null ⇒ auto-detect).

**Why it forces a rebuild:** `episode_id = f"{position_id}:{entry_time}…"`. Normalizing
server→UTC changes `entry_time`, hence `episode_id`. Old (server-time) and new (UTC) episodes
have **different ids** and would coexist in the same partition (doubling per-position P/L,
failing `verify`). **Action:** delete `mt5_analytics/artifacts/` and re-run `rebuild` once.
Schema versions did NOT change (field shapes are identical) — only timestamp *values*.

**Also in this change:** `MT5Adapter` is reference-counted (`mt5.initialize()/shutdown()` are
process-global; nested `with MT5Adapter()` — e.g. a harness adapter that also calls
`rebuild.run` — must not tear down the shared connection).

## 2026-06-19 — server offset PINNED explicitly + account-aware coverage (Phase 9B/9C)
**Offset (config, no code change):** the tick-based auto-detect (`server_utc_offset_hours: null`)
is a **market-hours-only** convenience — when the market is closed the last tick is stale and
yields a WRONG offset (observed: +3h during market hours, −5h off-market), which silently shifts
`history_deals_get` query bounds and drops recent deals from narrow windows. **Fix:** pin
`analytics.json:server_utc_offset_hours = 3` (MetaQuotes-Demo is EET/EEST; **+3 = EEST/summer**).
**DST caveat:** flip to **+2** at the EU DST end (late Oct) — or set back to `null` and only run
coverage/verify during market hours so auto-detect is reliable. This does NOT change `episode_id`
(the pinned +3 equals the in-market auto-detected +3), so **no rebuild required**.

**Account-aware coverage (Phase 9 — Reality Classification):** `coverage_score` is now
`observed / reachable` where `reachable = f(margin_mode, fee_model)` — a pattern the broker cannot
structurally emit is **N_A**, not a failing gap. Three explicit states (`PatternStatus`): OBSERVED /
REACHABLE_UNSEEN / N_A. `deal_coverage.json` / `coverage_gaps.json` gained `account_type`,
`reachable`, `classification`, `reachable_unseen`, `n_a`. Report-format change only; the
account-agnostic functions stay backward-compatible (`reachable=None`).
