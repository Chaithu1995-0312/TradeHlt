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

## 2026-06-26 — Commission Semantics Verified: IC Markets Raw (v0.5.0, ZERO kernel change)
**What:** First **commission-charging** and first **non-MetaQuotes** broker — IC Markets
(`Raw Trading Ltd` / `ICMarketsSC-Demo` / login `52935582`, margin_mode=2 hedging). Placed tiny demo
`normal`+`partial` trades; rebuilt+verified+scored coverage in an isolated `ecn/` root.
**Gate 0 PASS — `commission_charged=True`** (Σ commission −0.23 across 5 deals). **`verify` PASS,
ZERO kernel change.**
- **Form = Case C (split entry+exit, folded onto `volume>0` trade deals)** — every trade deal carries
  commission (BUY entry −0.04, SELL exit −0.04; the 0.02 entry −0.07 + two 0.01 exits −0.04 each).
  **NOT a separate zero-volume commission deal (Case B).** The kernel's per-deal
  `net_pnl = Σ(profit+swap+commission)` summed it correctly: episodes `pid 1730353606 net_pnl −0.08`
  (=−0.04−0.04) and `pid 1730353681 net_pnl −0.15` (=−0.07−0.04−0.04); `verify` `net_pnl_diff ≈ 2.8e-17`
  (≈0), `volume_diff 0.0`, manifests OK, 2 positions → 2 episodes. The deposit deal (type=2, pid=0,
  +200) correctly skipped by `is_position_deal`.
- **Coverage:** `partial_closes` OBSERVED; **`separate_commission_deals` REACHABLE_UNSEEN** — commission
  is real but *folded/split onto trade deals*, so the SEPARATE-deal reconstruction path stays
  UNVALIDATED (honest scope: "commission folded — separate-deal form still unobserved"). Bronze 1/3.
- **Server offset:** ICMarketsSC-Demo is also **+3** (server tick 14:33 vs UTC 11:33), so the pinned
  `server_utc_offset_hours=3` is correct here too — no rebuild/offset change. (Process note: the only
  hitch was a too-narrow query window — deals at 06-26 09:45 UTC fell past a 06-26 00:00 upper bound;
  widened to 06-27. No code defect.)
- **Gate-2 NOT triggered.** Kernel unchanged; Case B (separate commission deal) remains the only
  unobserved commission form and the standing reopen condition for this axis.

## 2026-06-25 — Broker Semantics Verified: netting reality validation (v0.4.0, ZERO kernel change)
**What:** Placed tiny demo trades on a second MT5 demo account — **NETTING** (`108830159`,
`margin_mode=0`), the first non-hedging broker the kernel has seen — exercising normal / partial /
pyramid / **INOUT reversal** / reopen, then rebuilt + verified + scored coverage in an **isolated
netting root** (`mt5_analytics/{artifacts,reports,audit}/netting/`, gitignored).
**Finding (SCOPED — do NOT over-generalize): the FROZEN reconstruction kernel is broker-independent
ACROSS MT5 hedging↔netting margin modes — `verify` PASS with ZERO kernel change.** First non-hedging
broker observed, `MetaQuotes-Demo` only. NOT "broker-independent forever": commission-bearing deals,
a swap+partial COMBINED lifecycle, exchange-margin (mm1), and non-MetaQuotes brokers remain
**UNVALIDATED**. Evidence ordering = real broker events > synthetic fixtures > unit tests > static
reasoning; this advances the margin_mode axis only.
- INOUT keystone: `BUY 0.01 → SELL 0.02 → BUY 0.01` netted to **`position_id=9270517338` → 2
  episodes** (long 0.01 then flipped short 0.01) at the `DEAL_ENTRY_INOUT` boundary — same
  position_id, distinct episode_ids, correct directions/VWAP/net_pnl. `verify`: 6 position_ids → 7
  episodes (the +1 is the INOUT split), `net_pnl_diff=0.0`, `volume_diff=0.0`, manifests OK.
- Coverage: `inout_reversals` + `pyramids` + `partial_closes` → **OBSERVED** (netting Silver 3/5);
  `reopens` → **REACHABLE_UNSEEN** — MT5 netting assigns a **fresh `position_id` on re-open** (each
  reopen leg got a new id 9270518727 / 9270519445), so a reused-id "reopen" never materialized. An
  honest reality finding, not a defect.

**One coverage-layer fix (NOT the kernel):** `broker_semantics.json` `broker_key` now includes
`|mm{margin_mode}` (was `company|server` only). Both demo accounts share
`MetaQuotes Ltd.|MetaQuotes-Demo`, so in a shared root the monotonic OR-merge would have falsely
attributed netting-only INOUT/pyramid capability to the hedging account. Keying by margin_mode keeps
mm2 (hedging) and mm0 (netting) as distinct capability rows. No stored-artifact *meaning* change for
existing hedging runs (new key path) — but a fresh broker_semantics.json is written going forward.

## 2026-06-24 — Phase 9A: post-close swap captured; swap is FOLDED (coverage-layer only)
Held a 0.01 EURUSD demo position ~51.6h across rollovers (swap accrued −0.02). **Finding:**
MetaQuotes-Demo **folds swap into the close deal** (the OUT deal has `volume>0` AND `swap≠0`) — NOT
a separate zero-volume swap record. **Reconstruction was already correct** (`net_pnl −10.62 =
gross −10.6 + swap −0.02`, `verify` PASS, 8=8, P/L diff 0.0) — **zero kernel change**. Only the
characterizer's swap detector was broadened (`_incurred_swap` = any deal with `swap≠0`, folded or
separate) so coverage recognizes the broker's real swap form. Result: hedging broker now **Platinum
(2/2 reachable)** — every structurally-possible pattern observed + verified; pyramid/INOUT/reopen/
separate-commission remain honestly N/A. This is a coverage-layer refinement (Gate-2-lite), not a
reconstruction defect.
