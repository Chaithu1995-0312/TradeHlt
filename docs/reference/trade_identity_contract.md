# Trade Identity Contract (v1)

> **Frozen semantic contract.** This document defines what `trade_id` and `alert_id` *mean* and
> guarantee — forever. The schema *shapes* live in code (`src/journal/trade_identity_v1_0.py` and the
> Tier-0B adapter schemas); this doc is the *authority* those schemas implement. Changing an
> invariant here is a breaking change: bump to a `v2` contract, do not silently edit.
>
> Status: **FROZEN 2026-07-05.** Prerequisite for Tier 0B (adapter schemas) and Tier 1 (adapters).

## The two identities

| Field | Identity kind | Minted | Determinism | Purpose |
|---|---|---|---|---|
| `alert_id` | **Research / prediction** | when `LiveEngine.process()` emits an alert | SHA-1[:16] of `symbol\|candle_ts\|regime\|session\|direction` (`src/engines/live_engine.py:796`) — *deterministic on decision-context* | "What did the model predict?" |
| `trade_id` | **Execution intent** | once, at the decision-to-act (`ExecutionIntentV1` → `PROPOSED`) | **opaque `uuid4().hex`** — embeds nothing | "Which real attempt-to-trade is this?" |

`alert_id` is deterministic and therefore **not unique per intent** — the same setup recurring, or a
human acting on one alert twice, yields the same `alert_id`. `trade_id` is the thing that is unique
per intent. They are **separate fields**; `alert_id` is carried alongside `trade_id`, never encoded
inside it.

## The invariants (frozen)

1. **`trade_id` is opaque.** It is a bare `uuid4().hex`. It encodes no `alert_id`, symbol, venue, or
   timestamp. **Never parse it** (no `trade_id.split(':')`); to get the alert lineage, read the
   `alert_id` field.
2. **Cardinality:**
   - `1 alert : N trade_ids` — one prediction may be acted on 0..N times, each a fresh `trade_id`.
   - `1 trade_id : 1 execution intent` — a `trade_id` *is* the intent identity.
   - `1 trade_id : 1..N order attempts` — **broker retries (REQUOTE/REJECT → resend) share the same
     `trade_id`.** The individual order attempts live in `TradeExecutionLinkV1`, not in identity.
   - `1 trade_id : 1..N episodes` — reconstruction may split one intent into multiple
     `PositionEpisode`s (pyramiding / partial closes / reopen). The episode↔trade mapping lives in
     `TradeExecutionLinkV1`.
3. **A "modification" is not a state.** Amending a live intent = `TERMINATED(REPLACED)` of the old
   intent + a new `PROPOSED` with a **new** `trade_id`. Identity is never mutated in place.
4. **`trade_id` survives transport.** It is stable across broker retries **and** venue migration
   (MT5 → FIX → IBKR/REST). Venue/order/deal identifiers are transport, not identity.
5. **`magic ≠ identity` (the load-bearing invariant).** The MT5 `magic` (and `comment`,
   `order_ticket`, `deal_ticket`) are **best-effort correlation carriers only**. Loss, truncation, or
   broker-rewrite of `magic` must **never** destroy or change a `TradeIdentity`; worst case it
   degrades the join to the fallback correlation `(symbol, entry_time≈, entry_price≈, volume)`.
   Identity is authoritative; transport is disposable.
6. **`execution_id` is not identity.** `execution_id` (`EX_` + md5 of `symbol_intent_price_dir`,
   `src/config_layer/execution_planner.py:280`) is a lossy content-hash (collides across time). It is
   a `TradeExecutionLinkV1` attribute, never the identity.

## Where each fact lives (bounded contexts)

| Context (schema) | Answers | Churns? |
|---|---|---|
| `TradeIdentityV1` = `{trade_id, alert_id, created_at}` | *What thing is this?* | No — sacred/permanent |
| `ExecutionIntentV1` (`PROPOSED → {TERMINATED(reason), EXECUTED}`) | *Did someone decide to act, and what happened to the decision?* | Yes — workflow |
| `TradeExecutionLinkV1` = `{trade_id, venue, magic, comment, order_ticket, deal_ticket, position_id, episode_id}` | *How did identity map onto broker reality?* | Yes — transport, disposable |
| `TradeProvenanceV1` = `{trade_id, strategy_id, promotion_version, config_hash, config_version, model_version, captured_at}` | *Why did this trade exist?* | Yes — governance lineage |

`TERMINATED.reason ∈ {REJECTED, EXPIRED, REPLACED, CANCELLED}`. Minimal by design: splitting
`TERMINATED` later is additive; un-merging states after consumers depend on them is not.

## Quick Q&A (the questions this contract exists to answer)

- **Can one alert create multiple trades?** Yes — `1 alert : N trade_ids`.
- **Can one trade_id have multiple orders?** Yes — retries share the `trade_id`.
- **Does trade_id survive a broker retry?** Yes.
- **Does trade_id survive a venue swap (MT5→FIX)?** Yes — it is transport-independent.
- **If `magic` is lost, is the trade lost?** No — identity is authoritative; the join falls back to
  `(symbol, entry_time≈, price≈, volume)`.
- **What is guaranteed forever?** The six invariants above. Everything else may evolve in the
  non-identity contexts without touching `TradeIdentityV1`.
