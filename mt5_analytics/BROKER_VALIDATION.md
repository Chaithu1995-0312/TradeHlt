# Broker-Semantics Validation Map

> Extends v0.4.0 ([`MIGRATIONS.md`](MIGRATIONS.md) 2026-06-25). Purpose: close the **UNVALIDATED**
> broker-semantics gaps by acquiring the *minimum* set of MT5 demo accounts that **structurally
> exercise** each unknown — not by reasoning about them. Evidence ordering stands: real broker
> events > synthetic fixtures > unit tests > static reasoning.

## What v0.4.0 actually proved (scope)
The frozen reconstruction kernel is broker-independent **across MT5 hedging↔netting margin modes**,
on `MetaQuotes-Demo` only. The reachability model lives in
[`engines/deal_characterizer.py`](engines/deal_characterizer.py) `reachable_patterns(margin_mode,
commission_charged)`. Two account axes remain unexercised: **commission posting** and
**exchange margin (mm1)**.

## Unknown → account that unlocks it

| Unvalidated unknown | What structurally emits it | Account type to acquire | `margin_mode` | `commission_charged` | Expected coverage flip |
|---|---|---|---|---|---|
| `separate_commission_deals` | per-deal commission posting | an **ECN / Raw-spread MT5 demo** (commission-charging, not spread-only). Examples to verify: Pepperstone *Razor*, IC Markets *Raw*, Tickmill *Pro*, RoboForex *ECN*, FBS. **Confirm the demo actually posts commission** before relying on it — many demos zero it out. | 0 or 2 | **True** | `separate_commission_deals`: `N_A → REACHABLE_UNSEEN → OBSERVED` |
| exchange-margin semantics | exchange-traded instruments (futures/equities) under full exchange margining | an **exchange/futures MT5 demo** (e.g. an MT5 broker offering MOEX or CME-style symbols) reporting `margin_mode = 1` (`MARGIN_MODE_EXCHANGE`) | **1** | varies | new `account_type: "exchange"`; needs an mm1 branch in `reachable_patterns` (coverage-layer, see below) |
| `post_close_swaps` + **swap-across-partial** | open → hold past daily rollover → **partial** close → final close | **any** account, incl. `MetaQuotes-Demo` (the deferred swap+partial run; generator `--patterns hold` then `close`) | any | — | `post_close_swaps: REACHABLE_UNSEEN → OBSERVED` + swap *allocation across legs* verified |
| non-MetaQuotes field/filling quirks | different filling modes, deal/order field shapes, reopen id policy | **any non-MetaQuotes MT5 demo** | — | — | generic robustness; `_filling()` already adapts via `symbol_info().filling_mode` |

## The actual risk hypothesis (where a Gate-2 kernel change could surface)
1. **Commission posting FORM** — the real test. Two forms exist:
   - **(a) folded** into the same deal's `commission` field → kernel already sums
     `profit+swap+commission` per deal ⇒ `net_pnl` correct, **no change expected**.
   - **(b) a SEPARATE commission deal record** (often zero-volume, own ticket). The reconstructor
     claims to handle separate + post-close commission/swap (zero-volume deals) — but **this is
     exactly the assumption MetaQuotes-Demo never exercised**, so it is verified only when a real
     commission-charging account produces it. If `verify` FAILs there → that is the legitimate
     Gate-2 trigger (capture the real deal shape → torture fixture → minimal kernel patch → re-verify).
2. **Exchange margin (mm1)** — higher kernel risk than commission: position lifecycle and deal-entry
   semantics may differ. Treat any mm1 result as a fresh reconstruction validation, not an assumed pass.

## Coverage-layer change to make WHEN mm1 data is in hand (not before)
`reachable_patterns` currently branches `mm0` (netting) vs *else* — so it silently treats `mm1`
(exchange) like `mm2` (hedging). When a real exchange account is connected, add an explicit `mm1`
branch (and `coverage._account_type` already maps `1 → "exchange"`). **Do not pre-build it** —
evidence-first; the branch should be written against observed mm1 deal behavior, not a guess.

## Operational gotchas when adding any new broker (so the path is smooth)
- **New fingerprint.** A new `company|server|login` ⇒ a **new** `account_fingerprint`. Re-capture it
  with a generator dry-run (`python manual_tools/trade_generator.py --symbol <sym>`), then pin it via
  `--account-hash <new fp>`. The DEMO gate (L1) still hard-blocks any non-demo account.
- **Symbol suffixes.** ECN/Raw accounts frequently name symbols `EURUSD.r` / `EURUSD.raw` /
  `EURUSD.ecn`. The generator's `SYMBOL_ALLOWLIST` won't match ⇒ it will **REFUSE (L2)**. Add the
  broker's *actual* symbol string to the allowlist for that run.
- **MT5 only.** The Python API is MT5-exclusive (MT4 has none). The terminal must be **logged into
  the target account** (`.env` programmatic switching is still deferred).
- **Isolated artifact root per broker.** Run rebuild/verify/coverage into
  `mt5_analytics/{artifacts,reports,audit}/<broker_tag>/` (as netting did) so `verify` reconciles
  only that broker's deals. `broker_semantics.json` is already keyed `company|server|mm{margin_mode}`
  so accounts won't OR-merge.

## Validation procedure (reuse the netting sprint verbatim)
1. Connect terminal to the new account; generator **dry-run** → confirm DEMO + capture fingerprint.
2. Place tiny demo trades exercising the target pattern (`--require-margin {hedging,netting}` as
   applicable; add the broker symbol to the allowlist if suffixed).
3. Rebuild + verify + coverage into an **isolated root** (inline cfg override of
   `artifact_root`/`report_root`/`audit_root`).
4. `verify` PASS + coverage flips the target pattern to OBSERVED ⇒ record in `MIGRATIONS.md`.
   `verify` FAIL ⇒ Gate-2 (real deal shape → fixture → minimal kernel patch → re-verify).
