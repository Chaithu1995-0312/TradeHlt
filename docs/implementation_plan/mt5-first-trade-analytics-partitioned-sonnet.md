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
gotchas already written: [`mt5_analytics/BROKER_VALIDATION.md`](../../mt5_analytics/BROKER_VALIDATION.md).

**Gating prerequisite (USER action — I cannot do this):** acquire a commission-charging ECN/Raw
**MT5** demo (IC Markets *Raw* > Pepperstone *Razor* > Tickmill *Pro* > RoboForex *ECN* > FBS —
**confirm the demo actually posts commission**, many zero it out), and log the terminal into it.

## Gate 0: validate the BROKER first (the real gating uncertainty)
The biggest risk is not the kernel — it is **assuming a "commission-charging" demo actually charges
commission**. Many ECN/Raw *demos* silently set `commission=0` even when the live product charges it.
If so: `commission_charged=False` → `separate_commission_deals=N_A` → **NO NEW EVIDENCE** (the run
tells us nothing about the kernel). So the first assertion, made at dry-run and again post-trade, is
`commission_charged == True`. If it is False, **abort and acquire a different broker** — do **not**
draw any kernel conclusion from a zeroed-commission account. The broker is validated before the kernel.

## The science: three realities, one decision tree (don't force a binary)
Commission is charged **immediately per deal** (no overnight wait, unlike swap). The verify P/L
oracle (`Σ profit+swap+commission` per `position_id` vs `Σ` artifact `net_pnl`) is the **primary**
gate; coverage tells us *which form* commission takes. Reality may be any of three forms — classify
by inspecting the real deals, never by forcing A-vs-B:

- **Case A — folded onto one deal (likely; mirrors the v0.3.1 swap finding).** A trade deal carries
  `volume>0` AND `commission≠0` (e.g. all commission on the close). Kernel already sums
  `profit+swap+commission` per deal ⇒ **`verify` PASS, net_pnl_diff 0, ZERO kernel change.**
  Coverage: `separate_commission_deals` stays **REACHABLE_UNSEEN** (no *separate* deal exists).
- **Case C — split across entry+exit deals (also benign).** Commission spread over both trade deals
  (e.g. entry `−0.35`, exit `−0.35`), each on a `volume>0` deal. Still summed per `position_id` by the
  oracle ⇒ **`verify` PASS, ZERO kernel change**; still **not** a separate-commission deal
  (`separate_commission_deals` REACHABLE_UNSEEN). Documented explicitly so a 2-deal commission split
  is *not* misread as Case B.
- **Case B — a SEPARATE commission deal (the legitimate Gate-2 risk).** A distinct (often
  `volume=0`) commission deal record alongside the trade deals, retaining `position_id`. Coverage:
  `separate_commission_deals` → **OBSERVED**. `verify` PASS *only if* the reconstructor handles the
  separate deal (it claims to via the zero-volume commission/swap path + `is_position_deal` keeping
  the pid). If `verify` **FAIL** → capture the real deal shape → torture fixture → minimal kernel
  patch → re-verify. **This is the earned mutation the architecture exists for.**

The discriminator between A/C (benign) and B is purely *structural*: is commission on a `volume>0`
trade deal (A/C) or on its own record (B)? Either way, success is decided by the oracle, not the form.

## Generator change — DONE (committed `8e9acf9`, the only non-gated piece)
- **`--extra-allow-symbol`** (append/comma-list) merges into the effective allowlist for the run, so a
  suffixed ECN symbol (`EURUSD.r` / `.raw` / `.ecn`) is accepted **explicitly, fails-closed** (no
  `startswith` guessing). Base `SYMBOL_ALLOWLIST` intact; every existing gate preserved (L1 DEMO-only,
  L2 fingerprint pin + `--require-margin`, lot cap, `mt5.symbol_info` validity, `symbol_select`).
  Verified by dry-run: suffixed symbol refuses without the flag, passes with it, base EURUSD
  unaffected. No test file (manual_tools is deliberately outside `tests/`). 74 mt5_analytics green.
- `--require-margin {hedging,netting}` + the `inout` pattern from v0.4.0 reused as-is (commission is
  orthogonal to margin mode). **Nothing else to build before the broker exists.**

## Coverage/kernel: nothing to pre-build (evidence-first)
`reachable_patterns(margin_mode, commission_charged)` already adds `separate_commission_deals` when
`commission_charged=True`, and `coverage.run` already derives `commission_charged` from the deals
(`any(commission≠0)`). So the **coverage layer handles a commission account with zero changes**. The
only thing that may change is the **kernel**, and only on a real Case-B `verify` FAIL. Per the v0.4.0
discipline (and the user's mm1 ruling), **do not pre-build** anything for a shape not yet observed.

## Execution (fast — commission is immediate; tiny demo lots, demo-gated)
0. **Gate 0 — broker pre-flight.** Dry-run: `python manual_tools/trade_generator.py
   --symbol <EURUSD.suffix> --extra-allow-symbol <EURUSD.suffix>` → confirm `trade_mode==DEMO`, read
   `margin_mode`, capture the new **fingerprint** (`sha256 company|server|login`). After the first
   round-trip (step 2), **assert `commission_charged==True`** in the coverage output. If False →
   **STOP, acquire a different broker** (no kernel conclusion from a zeroed-commission demo).
1. **(merged into Gate 0 — fingerprint capture.)**
2. **Place trades:** `--confirm --account-hash <ecn fp> --require-margin {hedging|netting}
   --extra-allow-symbol <sym> --symbol <sym> --patterns normal,partial --count 1 --max-trades 12`.
   `normal`+`partial` emits commission-bearing deals immediately. (Optional swap+partial add-on:
   `--patterns hold` today → `close` after the daily rollover — secondary, not required for commission.)
3. **Rebuild + verify + coverage into an ISOLATED commission root** via inline cfg override
   (`artifact_root`/`report_root`/`audit_root` → `mt5_analytics/{artifacts,reports,audit}/ecn/`),
   exactly as the netting sprint did (so `verify` reconciles only this broker's deals). The driver is
   a throwaway repo-root script (gitignored artifact roots; delete the script after — as before).
4. **Read against the three-case tree:** confirm `commission_charged==True` (Gate 0), then inspect a
   deal — commission on a `volume>0` trade deal (**A** all-on-close / **C** split entry+exit, both
   benign, verify PASS, zero kernel change) vs on its own record (**B**). Only **B + verify FAIL** ⇒
   Gate-2 (fixture → minimal kernel patch → re-verify; default `account` path stays byte-identical).

## v0.5.0 success criteria (everything else is explanatory metadata)
```
commission_charged == True   (Gate 0 — the broker is real)
AND  verify PASS  (net_pnl_diff 0.0, volume_diff 0.0, manifests OK)
AND  default mt5_analytics suite unchanged (74 green)
```
The Case A/B/C label and the `separate_commission_deals` OBSERVED/REACHABLE_UNSEEN value are
*explanatory metadata* about commission's form — not the pass/fail signal. The oracle decides.

**Gates and authority are orthogonal — keep them as two lists, never one numbered ladder.**

*Temporal gates — "can we proceed?" Failure at any ⇒ **STOP**: no interpretation, no conclusion, no kernel claim.*
```
Gate 0:  commission_charged == True   (the broker actually charges — else NO EVIDENCE)
Gate 1:  trade_mode == DEMO            (generator L1)
Gate 2:  account fingerprint matches   (generator L2 pin)
Gate 3:  verify executed               (a report exists to interpret)
```
*Interpretive authority — "how do we read VALID data?" Only after every gate passes.*
```
1. verify PASS            — financial truth; the P/L oracle; SUPREME
2. coverage classification — structural description (Case A/C/B, OBSERVED/REACHABLE_UNSEEN)
3. MIGRATIONS.md          — human narrative
4. BROKER_VALIDATION.md   — planning / documentation
```
Both truths preserved: `commission_charged==True` is **temporally** supreme (nothing happens without
it); `verify PASS` is **interpretively** supreme (nothing outranks the oracle once data is valid). So
`commission_charged=True` + `verify PASS` + `Case=C` ⇒ **v0.5.0 succeeds**, regardless of whether
`separate_commission_deals` is OBSERVED. The orthogonality also names the weird-but-valid state
`verify PASS ∧ commission_charged==False` — financially correct yet scientifically irrelevant
(commission was never exercised) — which a single numbered list would hide.

## Verification
- **Live:** `verify` **PASS** (net_pnl_diff 0.0, volume_diff 0.0, manifests OK) in the ecn root on an
  account where `commission≠0`; coverage records `account_type` + `commission_charged=True` and the
  Case-A/B/C classification of `separate_commission_deals`.
- **Unit:** existing **74 stay green** (default path untouched) + the `--extra-allow-symbol` flag
  behavior (accepts an opted-in symbol, still refuses a non-opted one) + any **real-shape** commission
  torture fixture only if Case B forces a kernel patch (derived from the captured deal, never assumed).
- **Record** in `MIGRATIONS.md` the observed form (Case A folded-on-close / Case C split entry+exit /
  Case B separate deal — whichever reality gives) and update the `separate_commission_deals` row in
  `BROKER_VALIDATION.md`'s matrix (OBSERVED only under Case B; REACHABLE_UNSEEN under A/C). Commit
  **v0.5.0 "Commission Semantics Verified"** with the broker family named and the scope held to what
  was observed (e.g. "commission folded — separate-deal form still unobserved" if A/C).

## NOT doing
No `.env` programmatic account switching (still deferred; terminal logged in manually). No mm1/exchange
work (separate future Level 4 — write its branch only against observed data). No kernel change unless a
real Case-B `verify` FAIL earns it. No pre-building of commission/exchange semantics. Demo-only,
hard-gated, tiny lots; hedging+netting MetaQuotes results left untouched.
