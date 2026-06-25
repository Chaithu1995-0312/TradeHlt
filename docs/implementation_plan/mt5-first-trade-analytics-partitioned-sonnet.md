# Level-3 commission-broker validation → v0.5.0 "Commission Semantics Verified"

## Context
v0.4.0 (commits `e4e02f3`/`6f0681e`/`4d4a937`) proved — and **scoped** — the frozen reconstruction
kernel as broker-independent *across MT5 hedging↔netting margin modes, on MetaQuotes-Demo only*.
The next milestone is **not** "prove broker independence" — it is **disprove the strongest remaining
assumption**, which is:

> `commission` is always carried on the trade deal's own `commission` field (i.e. MetaQuotes-Demo's
> zero-commission world generalizes to commission-charging brokers).

MetaQuotes-Demo charges **zero** commission, so `separate_commission_deals` is structurally `N_A`
there — it cannot be manufactured. This sprint exercises it for real on a **commission-charging
ECN/Raw MT5 demo** and runs the netting-validation workflow *unchanged*. Map +
gotchas already written: [`mt5_analytics/BROKER_VALIDATION.md`](../../../D:/Tradelatest/mt5_analytics/BROKER_VALIDATION.md).

**Gating prerequisite (USER action — I cannot do this):** acquire a commission-charging ECN/Raw
**MT5** demo (Pepperstone *Razor* / IC Markets *Raw* / Tickmill *Pro* / RoboForex *ECN* / FBS —
**confirm the demo actually posts commission**, many zero it out), and log the terminal into it.

## The science: two realities, one decision tree
Commission is charged **immediately per deal** (no overnight wait, unlike swap). The verify P/L
oracle (`Σ profit+swap+commission` per `position_id` vs `Σ` artifact `net_pnl`) is the **primary**
gate; coverage tells us *which form* commission takes:

- **Case A — folded (most likely; mirrors the v0.3.1 swap finding).** Deal carries `volume>0` AND
  `commission≠0`. Kernel already sums `profit+swap+commission` per deal ⇒ **`verify` PASS, net_pnl_diff
  0, ZERO kernel change.** Coverage: `separate_commission_deals` stays **REACHABLE_UNSEEN** (no
  *separate* deal exists — the count specifically tracks the separate form). Success signal = verify
  PASS on a `commission_charged=True` account, **not** the coverage flip.
- **Case B — separate commission deal (the legitimate Gate-2 risk).** A distinct (often zero-volume)
  commission deal record alongside the trade deal. Coverage: `separate_commission_deals` →
  **OBSERVED**. `verify` PASS *only if* the reconstructor handles the separate deal (it claims to via
  the zero-volume commission/swap path + `is_position_deal` keeping the pid). If `verify` **FAIL** →
  capture the real deal shape → torture fixture → minimal kernel patch → re-verify. **This is the
  earned mutation the architecture exists for.**

## One small generator change (`manual_tools/trade_generator.py`, stays OUTSIDE `mt5_analytics/`)
- Add **`--extra-allow-symbol`** (append/comma-list) merged into the effective allowlist for the run,
  so a suffixed ECN symbol (`EURUSD.r` / `.raw` / `.ecn`) is accepted **explicitly, fails-closed**.
  Keep the hardcoded base `SYMBOL_ALLOWLIST` intact; preserve every existing gate (L1 DEMO-only,
  L2 fingerprint pin + `--require-margin`, lot cap, `mt5.symbol_info` validity, `symbol_select`).
  Reuse the existing `args.symbol not in <allowlist>` check against the merged set.
- No other generator change. `--require-margin {hedging,netting}` + the `inout` pattern from v0.4.0
  are reused as-is (commission is orthogonal to margin mode — works on whichever mode the ECN demo is).

## Coverage/kernel: nothing to pre-build (evidence-first)
`reachable_patterns(margin_mode, commission_charged)` already adds `separate_commission_deals` when
`commission_charged=True`, and `coverage.run` already derives `commission_charged` from the deals
(`any(commission≠0)`). So the **coverage layer handles a commission account with zero changes**. The
only thing that may change is the **kernel**, and only on a real Case-B `verify` FAIL. Per the v0.4.0
discipline (and the user's mm1 ruling), **do not pre-build** anything for a shape not yet observed.

## Execution (fast — commission is immediate; tiny demo lots, demo-gated)
1. **Dry-run** on the ECN demo: `python manual_tools/trade_generator.py --symbol <EURUSD.suffix>
   --extra-allow-symbol <EURUSD.suffix>` → confirm `trade_mode==DEMO`, read its `margin_mode`, and
   **capture the new fingerprint** (`sha256 company|server|login`) for `--account-hash`.
2. **Place trades:** `--confirm --account-hash <ecn fp> --require-margin {hedging|netting}
   --extra-allow-symbol <sym> --symbol <sym> --patterns normal,partial --count 1 --max-trades 12`.
   `normal`+`partial` is sufficient to emit commission-bearing deals. (Optional swap+partial add-on:
   `--patterns hold` today → `close` after the daily rollover — secondary, not required for commission.)
3. **Rebuild + verify + coverage into an ISOLATED commission root** via inline cfg override
   (`artifact_root`/`report_root`/`audit_root` → `mt5_analytics/{artifacts,reports,audit}/ecn/`),
   exactly as the netting sprint did (so `verify` reconciles only this broker's deals). The driver is
   a throwaway repo-root script (gitignored artifact roots; delete the script after — as before).
4. **Read the result against the decision tree:** verify PASS + `commission_charged=True` ⇒
   commission handled. Inspect a deal to classify **Case A vs Case B**; if Case B and verify FAIL ⇒
   Gate-2 (fixture → minimal kernel patch → re-verify, default `account` path must stay byte-identical).

## Verification
- **Live:** `verify` **PASS** (net_pnl_diff 0.0, volume_diff 0.0, manifests OK) in the ecn root on an
  account where `commission≠0`; coverage records `account_type` + `commission_charged=True` and the
  Case-A/B classification of `separate_commission_deals`.
- **Unit:** existing **74 stay green** (default path untouched) + the `--extra-allow-symbol` flag
  behavior (accepts an opted-in symbol, still refuses a non-opted one) + any **real-shape** commission
  torture fixture only if Case B forces a kernel patch (derived from the captured deal, never assumed).
- **Record** in `MIGRATIONS.md` (Case A folded / Case B separate, whichever reality gives) and flip
  the `separate_commission_deals` row in `BROKER_VALIDATION.md`'s matrix. Commit **v0.5.0 "Commission
  Semantics Verified"** with the broker family named and the scope held to what was observed.

## NOT doing
No `.env` programmatic account switching (still deferred; terminal logged in manually). No mm1/exchange
work (separate future Level 4 — write its branch only against observed data). No kernel change unless a
real Case-B `verify` FAIL earns it. No pre-building of commission/exchange semantics. Demo-only,
hard-gated, tiny lots; hedging+netting MetaQuotes results left untouched.
