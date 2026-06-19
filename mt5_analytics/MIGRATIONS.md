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
