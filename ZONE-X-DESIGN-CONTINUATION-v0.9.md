# ZONE-X — DESIGN CONTINUATION v0.9 (DRAFT)

**Status:** DESIGN ONLY — does **not** amend frozen `ZONE-X-SPEC-v0.8.md`.  
**Programme decision (binding):** `ZONE-X-DECISION-2026-08-06.md` — **path (a) Stop**; design `c=0.055`; empirical `c=0.0238`.  
**Inputs:** `ZONE-X-SPEC-v0.8.md` (canonical), `ZONE-X-KNOWLEDGE-TRANSFER.md` (operational memory).  
**Authority:** research / programme design only. Grants no production, promotion, or test-year access.  
**Date:** 2026-08-06  

---

## 0. Standing rules (inherited, not renegotiated)

1. Work from v0.8 clause IDs. Do not paraphrase load-bearing numbers.
2. Do not extend the frozen spec in place. Gaps are named here; a future v0.9 *spec* freezes only after O-1 and a path choice.
3. Agreement carries no information. Design spends output on error modes and decision gates.
4. Every load-bearing number is either cited from v0.8 / transfer, or marked `ASSUMED` / `UNKNOWN`.
5. The test year (`2025-05-21 → 2026-05-21`) remains **untouched** until `g`, `k`, `m`, `c`, direction rule, and the hypothesis list are frozen (`V-2`, `V-3`).

---

## 1. Where the programme actually is

| Layer | State | Evidence |
|---|---|---|
| Problem framing | Settled | v0.8 §1–§5, `S-1`…`S-8`, `S-10`…`S-12` |
| First empirical result | Registered null | v0.8 §6, `S-13` |
| Directional permission | Settled (S-9 retracted) | v0.8 §7, `V-9` |
| Cost `c` | **Unblocked** — dual figure | O-1 MEASURED demo; decision D-C1/D-C2 |
| Design default `c` | **0.055 ATR/side** | stop p90 stress; thin n=7 stop sample |
| Empirical baseline `c` | **0.0238 ATR/side** | report/benchmark only |
| O-1 extraction tooling | **Built + executed** | `results/research/xauusd_mt5_cost_calibration/` |
| Path choice 9.2 (a/b/c) | **(a) Stop — recorded** | `ZONE-X-DECISION-2026-08-06.md` |
| Feature search | **HALTED** | path (a) |
| Test year | Sealed | v0.8 §3.1, `V-2` |
| Deferred | `O-3`, `O-4`, `O-5` | transfer §9.3 |

**Design claim of this document:** the next *design* work is not more feature search. It is (i) a cost-to-decision gate, (ii) a stop-protocol that preserves the null, (iii) a declared-prior protocol for path (b) that cannot reintroduce the errors already paid for, and (iv) a venue-change protocol for path (c).

---

## 2. Design goal for v0.9

Produce a **decision-ready programme** such that, once a verified `c` exists:

1. A human can choose (a) stop, (b) continue under declared priors, or (c) change venue — using a pre-written rule, not post-hoc mood.
2. If (b) is chosen, the next probe is **pre-registered**, budget-capped, V-6-safe, drift-netted (`V-9`), and **cannot** silently reuse the §6 eight-feature family as novelty (`S-13`).
3. If (a) or (c) is chosen, the archive states exactly what was and was not established (transfer §8).

Non-goals (still): ontology vocabulary as answer, Sharpe, live tradability claims, opening the test year for exploration.

---

## 3. Phase map (ordered)

```
P0  Cost verification (O-1)          [tool exists; run blocked on MT5 + fills]
P1  Threshold recompute              [arithmetic only; no modelling]
P2  Path decision (a | b | c)        [human; rule table below]
P3a Archive null + stop              [if a]
P3b Declared-prior campaign          [if b]
P3c Venue re-baselining              [if c]
P4  Deferred O-3 / O-4 / O-5         [only after P2; never before P0]
```

**Hard ordering:** `P0 → P1 → P2`. No P3* before P1. No test-year touch before P3b/P3c freeze.

---

## 4. P0 — Cost verification (design contract around existing tool)

### 4.1 What “verified `c`” means

v0.8 `O-1` requires three components **separately**: spread, commission, realized slippage. The built tool also extracts swap (overnight); ZONE-X events are intraday (`h = 12` bars = 3h), so:

| Component | Role in ZONE-X `c` | Required for unblock? |
|---|---|---|
| Spread (half-spread per side) | Core | Yes |
| Commission per oz per side | Core | Yes, or explicit broker-stated 0 with evidence |
| Stop-order slippage median | Core (barriers are stops; 29% gap bars) | Yes for full MEASURED; see 4.3 |
| Swap | **Out of event `c`** at `h=12` unless a position is held across rollover | Report only; do not fold into event `c` by default |

**Definition (design, not yet frozen in v0.8):**

```
c_side_usd = half_spread_usd + commission_per_oz_side + stop_slippage_median_usd
c_side_atr = c_side_usd / ATR14_median_test
```

Cite ATR constants from v0.8 §3.2 — do not recompute a new “authority ATR” for the conversion:

- median ATR14 (test) = **$7.342**
- p10 / p90 = 3.467 / 15.489 (sensitivity only)

Round-trip for straddle remains `2c`; directional pays `c` (v0.8 §5).

### 4.2 Status contract (already implemented — design insists it stays)

| Status | Meaning | May enter decision table? |
|---|---|---|
| `MEASURED` | Real ticks/deals support the number | Yes |
| `INSUFFICIENT_DATA` | Method correct; sample too thin | Only as **interval** with explicit width |
| `UNKNOWN` | Cannot form the quantity | **No** — remains blocked |

`compute_c_per_side` worst-of-three must remain: never substitute 0 for a missing term.

### 4.3 Partial-evidence policy (new design rule)

| Spread | Commission | Stop slip | Action |
|---|---|---|---|
| M | M | M | Full unblock; single `c` point |
| M | M | I/U | Form **bracket**: `c_lo = spread/2 + comm`, `c_hi = c_lo + slip_proxy`; decision uses **`c_hi`** (conservative) |
| M | U | * | Still blocked unless broker schedule documents commission = 0 in writing (attach schedule hash) |
| U | * | * | Still blocked |

**Slip proxy (only for brackets, never as fake MEASURED):**  
`max( observed_market_slip_p90 if any, 0.5 × median_spread, $0.05/oz )` — all three candidates computed; take max. Mark `ASSUMED_BRACKET`.

Repo prior for comparison only (not ZONE-X authority): `xau_metals_protocol_v1.json` primary `usd_round_trip = 0.40` ⇒ **$0.20/side** if split evenly. Map:

```
c_prior_atr ≈ 0.20 / 7.342 ≈ 0.027 ATR/side
```

vs v0.8 working assumption `0.07` ATR/side ≈ $0.51/oz/side at median ATR.

### 4.4 Execution checklist (operator, not research math)

1. MT5 terminal running + logged in; `pip install MetaTrader5`.
2. Smoke:  
   `python scripts/research/xauusd_mt5_cost_calibration.py --tick-days 7 --history-days 30`
3. Production window: `--tick-days 30 --history-days 180`.
4. If stop fills thin: manual small STOP ladder on **demo**, re-run `--skip-ticks` until `stop_status` improves (tool never places orders).
5. Archive: `results/research/xauusd_mt5_cost_calibration/*_LATEST.*` + summary MD.
6. Record in a one-line programme note (future v0.9 §8):  
   `c_side_usd`, `c_side_atr`, status triple, ATR citation, timestamp, artifact sha256.

---

## 5. P1 — Threshold recompute (pure arithmetic)

Once `c` (or conservative `c_hi`) is fixed, recompute — **no model training**:

### 5.1 Directional (primary after S-9 retraction)

```
p* = (m + c) / (k + m)     with k=1.5, m=1.0  →  p* = (1 + c) / 2.5
gap_long  = p* − 0.4071    # generation long baseline, v0.8 §5.2
gap_short = p* − 0.3712
```

v0.8 §8.1 table is the template; extend only by inserting the measured `c` row.

### 5.2 Straddle (secondary diagnostic)

```
required_lift = 2c
capture_frac  = 2c / (k − m) = 2c / 0.50
```

### 5.3 Power sketch (directional proportions)

With independent blocks `B_test = 736` and coverage `cov`:

```
n ≈ cov × (admissible test windows) / 24     # block-adjusted spirit of V-4
# For a one-sided lift δ = gap_long on a base p≈0.40:
# rough n_min ≈ (z_{1-α}√(p(1-p)) + z_power √(p'(1-p')))² / δ²
```

**Design rule:** recompute `n_min` and implied `M` **after** `c` is known; do not reuse the straddle `N_min = 266` as if it were directional power (`V-4` still applies; formula differs).

### 5.4 Headroom gate (`V-7`)

Reject cells requiring capture > 40% of max available edge, or sd < 0.5.  
At very low `c`, headroom improves; do not spend that by exploding hypothesis count.

---

## 6. P2 — Path decision table (human gate, pre-committed)

This table is the design’s main anti-mood device. Choose **before** inventing features.

| Measured `c` (ATR/side) | Directional gap vs long 0.4071 | Default path | Rationale |
|---|---|---|---|
| `c ≤ 0.03` | ≲ +0.5 pp | **(b) allowed** | Toll is small enough that a *declared* common region could be resolvable; still not a hunting license |
| `0.03 < c ≤ 0.05` | ~0.5–1.3 pp | **(b) only if M≤4 declared** | Budget tight; open search forbidden |
| `0.05 < c ≤ 0.08` | ~1.3–2.3 pp | **(a) preferred; (b) exceptional** | Matches current assumed world; four null probes already at chance |
| `c > 0.08` | ≳ +2.3 pp | **(a) or (c)** | Geometry-at-M15-gold is the wrong fight under this toll |

**Overrides (must be written, not vibes):**

- Override to **(a)** even at low `c` if the operator values the registered null as terminal.
- Override to **(c)** if the scientific claim wanted is about *method*, not *gold M15*.
- Override to **(b)** at high `c` only if a **single** declared prior has external evidence strong enough to justify a one-shot test (still M=1, full Bonferroni trivial).

Path labels match transfer §9.2:

- **(a) Stop** — archive null; do not mine further on this venue/horizon.
- **(b) Continue with constraint relaxed** — declared priors only (Part 7).
- **(c) Change instrument or timeframe** — re-baseline everything (Part 8).

---

## 7. P3b — Declared-prior campaign (the only untried research lever)

### 7.1 What “relaxed constraint” means — and what it must not mean

v0.8 §2 excludes ontology, pattern names, session labels, trading rules, etc.  
Transfer §9.2(b) allows **declared priors** — written in advance, testable, not hidden.

**Design resolution (proposed for a future v0.9 freeze, not active now):**

| Allowed | Forbidden |
|---|---|
| A finite list `H_1…H_M` written **before** any generation evaluation of those H | Open-ended feature search, then “declaring” winners |
| Each H is a **decidable** membership + optional direction map `d(g(W))` | Selecting direction by observed outcome (still banned, §7.1) |
| Priors motivated by external theory, other markets, or pure math | Priors reverse-engineered from the generation year’s labels |
| Reuse of measurement machinery (windows, barriers, V-*) | Reuse of §6’s eight survivors as a *new* claim without citing `S-13` |
| Semantic *names* as **labels for humans** after declaration | Semantic names as **search operators** (“find all pin bars”) |

**Ordering preserved:** discover (under a declared H) → explain → decide.  
Explanation still comes after measurement; declaration is not explanation.

### 7.2 Hypothesis object (schema)

Each declared hypothesis is a record:

```text
H_id:            H-ZX-00N
claim:           one sentence, falsifiable
g_definition:    function of the L=12 window only (no bar ≥ t+L)
direction_rule:  long | short | f(g) fitted ONLY on generation
coverage_target: ∈ (0.13, 0.65]   # rare setups unprovable (transfer §4.2)
V6_inputs:       list of raw series used; each must pass |corr|≤0.10 vs anchor ATR & local kurtosis
objective:       directional primary; straddle optional diagnostic
status:          DECLARED | FITTED_GEN | TESTED | RETIRED
```

**Freeze file (proposed path):** `ZONE-X-HYPOTHESIS-REGISTER.jsonl`  
Append-only. `V-3` Bonferroni denominator = count of rows with `status ∈ {DECLARED,FITTED_GEN,TESTED}` at the moment the test year is first opened — not the count of rows that look good later.

### 7.3 Budget accounting

| Spend | Counts toward M? | Notes |
|---|---|---|
| §6 eight-feature GBM family | **Yes — 1 family already spent** as registered null | Do not re-bill as 8 separate H unless thresholds are re-declared as new H |
| Independent DeepSeek/Grok probes | Historical corroboration; **not** re-spent | Cite transfer §6.2; do not re-run as novelty |
| New declared H_i | **+1 each** | Hard cap depends on `c` (Part 6 table): M≤4 mid, M≤6 only if `c≤0.03` |
| Nested threshold tuning on generation | **Does not** add H if ranges were pre-declared | If you invent a new threshold axis after seeing folds, that is a new H |

**Working cap (design default at assumed c≈0.07):** **M_remaining = 4**.  
If measured `c≤0.03`, raise to 6. If `c>0.08`, M_remaining = 0 (path a/c).

### 7.4 Fit / evaluate protocol (generation free, test sealed)

```
1. Write H_1…H_M to the register (all DECLARED). Record M.
2. On GENERATION only:
   a. Compute g for each H; run V-6; fail → RETIRED with reason (does not free the slot if it was declared — still in Bonferroni).
   b. Fit direction / thresholds under purged chronological CV (embargo ≥ 240 windows, as §6).
   c. Record oof metrics; these are NOT evidence for X.
3. Freeze: c, k, m, H list, fitted parameters, direction maps.
4. Open TEST once:
   a. Evaluate all non-RETIRED H (report all; no cherry-pick).
   b. Block bootstrap on 736 blocks (V-4).
   c. Directional results net of constant-direction benchmark (V-9).
   d. Baseline under identical (k,m,c) on test (V-5).
5. Decision per H: FAIL / INCONCLUSIVE / PASS_CANDIDATE
   PASS_CANDIDATE still grants NO tradability claim (v0.8 §16).
```

### 7.5 What family to declare (design guidance, not a shopping list)

§6 established: **obvious scale-free scalar geometry of the 12-bar window is null.**  
Therefore new H must not be “eight more scalars of the same kind.”

**Eligible design classes (examples of *class*, not pre-approved H):**

| Class | Why it is not §6 | Primary failure mode |
|---|---|---|
| **C1 Path-order statistics** | §6 used aggregates; first-passage *inside* W (e.g. time-of-max-range) is different | Still martingale; easy to overfit breakpoints |
| **C2 Half-window contrast** | Early vs late third of W under scale-free map | Leakage into momentum = drift capture → V-9 must kill it |
| **C3 Multi-window state, single decision** | Membership uses only last W, but prior windows as declared context features that are still pre-anchor | Contiguity / admissibility bugs; independence illusion |
| **C4 Declared external transfer** | Prior from another market/timeframe, parameters frozen before gold generation fit | Transfer invalid; becomes free parameter if refit freely |
| **C5 Cost-aware region** | Membership predicts *resolvability* or *slippage regime*, not direction | May pass EV via cost, not edge — must separate gross vs net |

**Ineligible (already burned or invalid):**

- Coil / ATR-ratio compression → expansion (pre-registered false positive; transfer §6.3)
- Raw volume slope/dispersion (failed V-6; volume ≡ vol proxy here)
- Any H whose g correlates |ρ|≥0.10 with anchor ATR
- Long-only rules without V-9 net-of-drift (generation long base 0.4071 is drift)

### 7.6 Acceptance criteria (test year)

For a single H to be `PASS_CANDIDATE`:

1. Coverage in band pre-declared (default target 0.65 only if H is common; rare H need higher effect and still face power wall).
2. Directional win rate net of constant-direction benchmark ≥ `p*` with block-adjusted significance under pre-declared α (default α = 0.05 / M).
3. Sign of edge stable under `c` bracket if slip was not fully MEASURED.
4. `V-7` headroom satisfied.
5. `V-8` regime disclosure: claim is about 2025–26 vol regime only (`S-15`).

Failing any → not X. Multiple testing is not optional.

### 7.7 Interaction with Tradelatest spine (boundary)

ZONE-X is **outside** the governed CRT spine. Design boundary:

| May reuse from repo | Must not do |
|---|---|
| MT5 cost tool, candle CSV loaders, block bootstrap utilities if any | Wire H into `EngineRunner` / fusion / promotion |
| Epistemic style (UNKNOWN, never invent) | Register a finding that grants production authority from a research PASS_CANDIDATE |
| Comparison to `xau_metals_protocol_v1` cost prior | Treat metals protocol entry ontology as ZONE-X g(W) |

If a future PASS_CANDIDATE ever graduates, that is a **new** governed programme with its own authority ladder — not automatic.

---

## 8. P3a — Stop protocol (path a)

If path (a):

1. Do **not** delete artifacts. Mark programme status:  
   `FEATURE_SEARCH_HALTED_ON_NULL + COST_VERIFIED|UNVERIFIED`.
2. Freeze narrative (already in transfer §12); only update the cost line when O-1 lands.
3. Explicit non-claims remain (transfer §8 “Not established”).
4. Allowed residual work without reopening search:
   - Finish O-1 documentation
   - Optional O-4 measurement as *descriptive* gap study (does not seek X)
   - No new g-family on gold M15 under ZONE-X branding

---

## 9. P3c — Venue / timeframe change (path c)

If path (c), **nothing numerical transfers** except protocol shape.

### 9.1 What transfers

- Window/outcome definitions (v0.8 §4–§5)
- Validation IDs `V-1`…`V-9`
- Error catalogue (transfer §7)
- Null-registration discipline

### 9.2 What must be re-measured

| Item | Why |
|---|---|
| Contiguity, session structure, gap rate | Gold’s Mon–Fri / hour-00-absent is market-specific |
| ATR median, ATR/SD | Scale |
| Long/short baselines | Drift differs |
| `c` | Broker + instrument |
| B, M, power | Sample structure |
| V-6 survivors | Feature–vol correlations change |

### 9.3 Suggested first alternate venues (design shortlist, not decision)

| Candidate | Why interesting | Why dangerous |
|---|---|---|
| XAUUSD M5 | Same metal, finer path | Cost/edge ratio often worse; independence harder |
| XAUUSD H1 | Fewer bars, cleaner moves | B collapses; rare events unprovable |
| Major FX M15 | Different efficiency | Cross-asset null already common in repo research (F-035 class) — do not “forum shop” |
| Less liquid metal / index future | Less efficient? | Data quality, gaps, `c` worse |

**Design rule:** pick **one** alternate, re-run P0–P1 fully, and treat gold M15 null as **venue-scoped**, not method-refuted.

---

## 10. Deferred items (design hooks only)

### 10.1 O-3 — drawdown → f

Needs human max-DD. Until then, capital frame v0.8 §12 stays illustrative.  
No position sizing experiments under ZONE-X.

### 10.2 O-4 — gap penalty

Descriptive measurement on generation (allowed) without seeking X:

```
For each stop resolution, realized_adverse = |fill − barrier| in ATR
report: P(gap_affects_stop), E[realized_m]/m, tail p90
```

Feeds conservative `m_eff` later; does not change `m=1.0` until a v0.9 freeze.

### 10.3 O-5 — horizon grid

Already known: economics improve, power dies; hard ceiling `L+h ≤ ~92` (transfer §6.4).  
Do not reopen unless path (c) changes bar size.

---

## 11. Error modes this design is built to prevent

| # | Failure | Guard |
|---|---|---|
| E1 | Re-derive §6 null as novel | `S-13` citation mandatory; register blocks reuse without citation |
| E2 | Open search under “declared prior” branding | Append-only register + freeze-before-fit |
| E3 | Long bias = drift sold as edge | `V-9` net benchmark mandatory |
| E4 | Coil/compression revival | Explicit ineligible class |
| E5 | `c=0` when slip unknown | worst-of status; conservative `c_hi` |
| E6 | First-passage sentinel bug | Keep dual-implementation discipline for any new label code (v0.8 §5.4) |
| E7 | `1 − y_long` as short | Separate short label always |
| E8 | Test-year peek during design | No test metrics in this document; none allowed in H register until freeze |
| E9 | Bonferroni after selection | Denominator = declared count at unseal |
| E10 | Shrinking L,h for fake B | `L+h≥24` hard floor remains |

---

## 12. Deliverables checklist (design → later build)

| ID | Deliverable | Depends | Status now |
|---|---|---|---|
| D0 | Run O-1 tool → cost artifacts | MT5 + optional stop fills | Tool ready / results missing |
| D1 | `ZONE-X-COST-NOTE.md` (measured c + statuses) | D0 | not started |
| D2 | Threshold table refresh (extend §8.1) | D1 | not started |
| D3 | Path decision recorded (a/b/c) | D2 | not started |
| D4 | `ZONE-X-HYPOTHESIS-REGISTER.jsonl` schema + empty freeze | D3=b | designed here |
| D5 | Generation-only harness for declared H (no test) | D4 | not started |
| D6 | Single-shot test evaluation harness | D5 + freeze | not started |
| D7 | Stop archive note | D3=a | not started |
| D8 | Venue rebase checklist instance | D3=c | not started |

---

## 13. Recommended immediate next step

**Not more geometry. Not v0.9 freeze. Not test year.**

1. **Execute P0** (operator): run `xauusd_mt5_cost_calibration.py` with a logged-in MT5 session.  
2. **Write D1** from artifacts (even if commission/slip are INSUFFICIENT — then use `c_hi` bracket).  
3. **Apply Part 6 table** → choose a/b/c in writing.  
4. Only if **(b)**: open D4 and declare ≤M hypotheses *before* any new generation scores.

If MT5 cannot be run in this environment, the programme stays correctly blocked at `O-1`; design is ready to consume `c` the hour it appears.

---

## 14. One-paragraph continuation (for cold start)

v0.8 registered that obvious 12-bar geometry on gold M15 carries no forward edge at the straddle or directional bar, while the market matches a martingale. The programme is now blocked only on the real all-in cost per ounce; tooling to measure it exists but has not been run. This design freezes a cost→threshold→path gate, forbids re-searching the burned feature family, and specifies the only remaining research move: a small, append-only, pre-declared hypothesis register with generation-only fitting and a single test-year unseal — or else stop / change venue. Nothing here opens the test year or amends the frozen spec.

---

## 15. Change log (design doc)

| Ver | Change |
|---|---|
| v0.9-DRAFT | First design continuation after v0.8 null + knowledge transfer; O-1 tool acknowledged as built-unrun; path a/b/c operationalized; declared-prior schema + budget + failure modes. |
| v0.9-DRAFT+decision | O-1 MEASURED; operator chose path **(a)**, design `c=0.055`, empirical `c=0.0238`, sensitivity grid + COST_STABLE rule — see `ZONE-X-DECISION-2026-08-06.md`. Declared-prior campaign (P3b) **not** entered. |
