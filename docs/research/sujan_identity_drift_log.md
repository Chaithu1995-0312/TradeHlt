# Sujan identity drift log

Created 2026-08-28 on first identity-extraction record, per
[`docs/governance/SUJAN_CRT_IDENTITY_EXTRACTION_SYSTEM.md`](../governance/SUJAN_CRT_IDENTITY_EXTRACTION_SYSTEM.md).

This file records **unapproved semantic replacements** and **identity extracts that are not frozen**.
It is not a playbook, not a `SEM-*`, not a measurement contract.

`FROZEN` is a human-bridge status only. This log never self-certifies it.

---

## Record 11 — 2026-10-06 — Sujan Theory 2: bridge chart rulings + bridge audit adopted; ready for a sealed test

**Kind:** identity extract plus labelled proxies. Records 8–10 stand as written. **Not** a freeze of the visual concepts; the proxies below are approved for **measurement only**.
**Naming:** the bridge's audit proposed renaming the model (from "Sujan Theory 2" to "user CRT"). The bridge then ruled: "sujan is fine keep as designed by you". The name stays "Sujan Theory 2"; the bridge's "my own knowledge" origin is recorded in Record 10.

### New bridge statements (GBPCHF 1m charts + circled AUDCHF read)

- "Crt h & low kinda key level undali … deenlo madhyalo vachindi key level": the HTF key level must lie **inside** the CRT range; here it sits in the middle.
- "Like this, big bearish bar violently takes liquidity of **recent low or range low**": the swept level can be a recent low inside the range, not only the range low.
- "Green ribbon down below … 1D FVG acts as a key level. In 1 hr Ltf, marking crt range high & low (black lines)". "forget blue line".
- The bridge circled this AUDCHF read: range high 0.58826 (target), HTF key location 0.57558 inside the range, range low 0.57317 swept, closed back inside.
- Analyst reading of GBPCHF, shown to the bridge and neither confirmed nor rejected: CRT range 1.09953 / 1.09832; key level 1.09874 (pink) in the middle; the recent low 1.09878 taken by the big bearish bar down to 1.09858, through the key level.

### Rulings (bridge audit 2026-10-06, adopted)

| Item | Ruling | Status |
|---|---|---|
| Trigger | candle CLOSES above the manipulation candle HIGH (short: below its LOW) | CONFIRMED. "Close back inside" = non-model **control** |
| Key touch | the manipulation must reach the HTF key-level zone; the zone lies anywhere inside the range | CONFIRMED. "Only inside the range" = control |
| Timing | any later candle; the setup cancels on a new extreme beyond the manipulation candle, or if the target is hit first | CONFIRMED. "Next candle only" = control |
| TF pairs | 1W→4H, 1D→1H, 4H→15M | CONFIRMED (1W→4H from the bridge's weekly-FVG/4H example) |
| TF pair 15M→1M | proposed in the audit from the GBPCHF 1m screenshot; the bridge's words for that chart were "1D FVG … 1 hr Ltf" | NOT CONFIRMED; optional extra |
| CRT range | two forms: (a) high/low of one location-TF candle (NAS100); (b) range on the execution chart around the key level (GBPCHF, AUDCHF) | CONFIRMED (both) |

### Proxies (labelled; approved for measurement only; each linked to its concept)

| Concept | Proxy | Variants |
|---|---|---|
| Range form (b), "black lines by eye" | the nearest confirmed swing high above and swing low below the key level, before the manipulation (pivot, k=2 bars each side, usable only once confirmed) | — |
| "Recent low" | lowest low of the last N execution bars inside the range | N = 20 primary; 10, 40 robustness |
| "Thick / violent" | body ≥ X·ATR14 (price units); body/ATR recorded on every candidate | X ∈ {0.5 (default), 1.0, 1.5} |
| OB zone (for "touch") | the zone the manipulation must intersect | full candle (wick to wick) · body |
| Bearish OB | mirror of the bullish rule (a bullish candle taking the high of ≥1 preceding bearish candle) | never stated; proxy |

### Still open (does not block a sealed research test)

Rejection Block definition · a full bearish chart walk-through to confirm the mirror · whether 15M→1M is a real pair · the exact GBPCHF line assignment above.

```text
Status: identity NOT YET FROZEN (visual concepts). Measurement object defined:
next = MC-SUJANT2-XAUUSD-V1, sealed before code results, then src/research/sujan_t2/.
Live automation: OUT until a variant passes the sealed test (F-073).
```

---

## Record 10 — 2026-10-05 — Sujan Theory 2 from the bridge's OWN words (refines Records 8–9)

**Kind:** identity extract. Records 8–9 stand as written. **Not** a freeze.
**Source:** the bridge's own messages from the teaching chat, relayed verbatim 2026-10-05. Every AI turn is excluded: its summaries, level picks, the AUDCHF/USDJPY/USDCHF reads. This is the highest-authority source on disk for Theory 2. The bridge calls it "my own knowledge … my model"; it is named Theory 2 on the bridge's instruction. **Stated end goal:** a live algorithm that places trades in the bridge's broker account, once the model is "perfect".

### Bridge's own statements (quoted)

| # | Quote (abridged) | Rule it states |
|---|---|---|
| Q1 | "down thick close bearish candle … shaking out the old low (dumb money) … then, bullish close above down thick bearish candle. Tats an bullish entry (pale blue line). … range high & low marked with black lines alongside, a htf key level (redline) on downside. This is an entire system. Target is opp. Range" | Type A + trigger + range + key level below + target |
| Q2 | "It's a complete close of thick bearish downclose candle. Bullish entry after this." | manipulation must close first |
| Q3 | "C2 on charts. Plz don't consider … tat C2 has different rules" · "plz don't call C2, or with other names … I'm showing you entire system" | no C2 / no other labels |
| Q4 | "Whenever there is a key level on HTF whether it's a FVG, order block, rejection block. All these acts as a key level. Without HTF key levels, no crt forms" | location prerequisite |
| Q5 | "weekly fvg, we treat as a location to trade the CRT model above it … range in 4 hr ltf … two black lines (crt high & crt low) … red line (tats a entry trigger) … tat candle only takes the liquidity of existing previous low & closes back inside crt range tats manipulation" | Type B; on this chart red = entry trigger |
| Q6 | "manipulations happen in two phases … down thick close bearish candle … other … thick bullish wick sweeps the old low (liquidation). Any bullish candle closed above tat thick wick tats a trigger & opposite side is the target" | two manipulation types; trigger |
| Q7 | "Bullish candle closed above manipulation candle. Tats an entry." | trigger |
| Q8 | "For buy crt trade to happen it must exists near HTF location. Tat thick bearish bodied candle swept the previous **bullish** candle low defines as a order block … must sweep the previous candle low atleast 1 candle. If two more candles tats big one" · "Preceding candle must sweep" | OB definition |
| Q9 | "15 min. How range forms exactly near 4 hr order block … if low purges with thick bearish down close candle … I ll be alert for bullish entry targeting opposite range" · "It's a 4 hr candle high & low" | range = a 4H candle, executed on 15M |
| Q10 | "htf location window must be higher time frame than execution time frames … 1 D … then ltf executions would be on 1 hr" | TF hierarchy (only 1D→1H stated in words) |
| Q11 | "1D htf orderblock swept preceding 2 candles … marking red line (key level) … low black line for preceding 2 candles sweep … 1+ more sweeps, it increases probability of hitting targets" | OB strength (hypothesis) |
| Q12 | "if there is an immediate close of right candle bullish candle then, odds are high … left side sweep & right bullish close … tat red line acts as a magnet for retest" | OB quality (hypothesis) |
| Q13 | "1D … 157.414 (htf location) … thick candle sweeps preceding candles … comes down to 1 hr ltf, there is a thick down close candle sweeps low & **immediate** bullish up candle & closed **inside range** near 1D order block … engine always works same, we need to see with right lens" | Type A trigger = next candle, closing back inside |
| Q14 | "wait how price reacts at htf orderblock … if it **touches htf pd array & closes back inside range**, then, it's a buy trigger" | a third trigger wording; manipulation must touch the zone |

### What changes vs Records 8–9

1. **Middle rule.** Q14 ("touches htf pd array") and Q8/Q9 ("near HTF location", "range forms exactly near 4 hr order block") point to: the manipulation must **touch** the HTF zone. Record 9's AMBIGUOUS leans to "touch"; the bridge still needs to confirm it.
2. **Type A.** Q13 says the thick candle sweeps the low and the next candle "closed inside range". That implies the thick candle itself closes **outside** (below) the range. This supports Record 8 row 4a.
3. **Trigger: three wordings that disagree.**
   - Q7/Q1: close above the manipulation candle (bridge ruling: above its HIGH).
   - Q13: the **immediate** next bullish candle closes **back inside the range**.
   - Q14: price **touches the PD array and closes back inside the range**.
   - Q6 adds "**any** bullish candle closed above".
   - Unresolved: "next candle only" vs "any later candle", and "above the manipulation high" vs "back inside the range". These are different conditions whenever the manipulation high sits below the range low.
4. **OB.** The swept preceding candle is **bullish** (Q8). This is new.
5. **Line colours are not consistent and are never rules.** Red = HTF key level (Q1, Q11) but red = entry trigger (Q5). Pale blue = entry (Q1). Black = range or swept low.
6. **Range candle.** Q9: the range is a **4H candle's** high/low, watched on 15M, near a 4H OB. Q5/Q13: the range is drawn on the execution chart (4H under a weekly FVG; 1H under a 1D OB). Whether the range candle is the location candle, a candle one TF above execution, or something else stays OPEN.
7. **The other LLM's "HTF C2 manipulation-complete" rule is dropped.** The bridge used the label once, defined it, then withdrew it (Q3).

```text
Status: NOT YET FROZEN. Blocking: trigger (point 3) and range candle (point 6).
```

---

## Record 9 — 2026-10-05 — Sujan Theory 2: design extracted from the bridge's teaching transcript (refines Record 8)

**Kind:** identity extract. Refines Record 8, which stays as written. **Not** a freeze.
**Source:** the bridge relayed a long teaching chat with another LLM (Level 4) and asked to "ignore noise, extract the design". Only items the bridge **confirmed in that chat** ("Got it… clear now", "Exactly… resolves", "completely clear") or wrote in their own words are kept. That LLM's own chart reads (AUDCHF 0.5820–0.5830, USDJPY 156.756 as an entry, USDCHF "close back inside") are noise and are excluded; the bridge rejected one of them outright ("You're right — I misread…").

### Architecture (bridge: "the engine always works the same; we need to see it through the right lens")

```text
HTF key location (FVG | Order Block | Rejection Block)   ← WHERE. Never an entry by itself.
  → CRT range = HIGH/LOW of one candle                     (confirmed: "4H candle → its HIGH & LOW = CRT range")
  → execution TF below it: watch the range extreme
  → manipulation at the range extreme (Type A | Type B)   ← must complete (close) first
  → trigger: a candle closes beyond the manipulation candle
  → target: the opposite side of the CRT range
```

### Rules confirmed in the transcript (status changes vs Record 8)

| # | Rule | Evidence in transcript | Status |
|---|---|---|---|
| R1 | No HTF key level ⇒ no CRT. Location says WHERE, the LTF reaction says WHEN. | repeated, bridge-affirmed | CONFIRMED (bridge, relayed) |
| R2 | Location TF > execution TF (1Mo→1D, 1W→4H, 1D→1H, 4H→15M). | "Yes, buddy — completely clear" | CONFIRMED |
| R3 | CRT range = the high and low of a single candle (NAS100: the 4H OB candle, executed on 15M). It is **not** built from LTF swing points. | "Ahh, yes — that clears my first question completely" | CONFIRMED (supersedes Record 8 row 4's "forms at/around") |
| R4 | OB (bullish): a thick bearish-bodied candle that sweeps the low of the **immediately preceding, adjacent** candle(s). ≥1 swept = valid OB; 2, 3, … consecutive swept = stronger (a **quality** variable, never a requirement). In the 2-candle example the black line = the low of the swept candles. | "Got it, buddy. Clear now." / "Exactly, buddy." | CONFIRMED |
| R5 | The thick bearish down-close (Type A) is the **shakeout/manipulation**, not the entry. It must close completely; the long comes only after. | bridge words: "It's a complete close of thick bearish down-close candle. Bullish entry after this." | CONFIRMED |
| R6 | Type B: a thick lower wick takes the previous low and closes back inside the CRT range. | "These images resolve the two doubts" | CONFIRMED |
| R7 | Trigger = a candle **closes** above the manipulation candle (a wick crossing it is not enough). Record 8 rule 6: above its HIGH. Bridge words for Type B: "**Any** bullish candle closed above that thick wick is a trigger." | bridge words | CONFIRMED. Resolves Record 8 row 6a toward "the first such close, not only the next candle" (still pending the bridge's explicit yes) |
| R8 | Target = the opposite side of the CRT range. | repeated, affirmed | CONFIRMED |
| R9 | Chart "C2" labels follow different rules and are **not** used to define this model. | bridge correction in the transcript | CONFIRMED (excludes the C2 definition the other LLM "locked" earlier) |

### Still open (not resolved by the transcript)

| Item | Why it stays open |
|---|---|
| Which candle is the CRT range candle, and on which TF | Shown only by example: NAS100 = the 4H OB candle itself. In the Weekly-FVG example the range is drawn on 4H with no candle rule, and the bridge was going to redraw it without the FVG. The general rule is unstated. |
| Middle rule | The Weekly-FVG example had the CRT low on the FVG boundary; the bridge also said the key level can be "in the middle". "Must touch" vs "anywhere inside the range" is still AMBIGUOUS. |
| Type A close location | The other LLM asked (does the thick candle have to close below the old low?) and was never answered in the transcript; Record 8 row 4a remains a relayed answer only. |
| OB zone and the red key line | The red line (e.g. 157.414, 156.756) marks the "key level from the OB"; which price of the OB candle it is (open, body, low) is unstated. |
| Bearish OB | The mirror (a thick bullish candle sweeping the preceding highs) is never stated. |
| "Thick" | Still visual; no proxy approved. |
| Rejection Block | Named only. |
| Model #1's FVG | The handwritten Model #1 lists "displacement → FVG → entry"; the FVG's role in entry was asked and never answered. Later examples run without it. |
| Invalidation (new low before trigger) | Inferred by the relaying LLM, never stated. |

### Observations kept as HYPOTHESES (never rules)

- More preceding candles swept ⇒ higher chance of reaching the target (bridge observation; "a probability/quality variable until tested").
- An OB with a left-side sweep and an immediate right-side bullish close acts as a "magnet": price returns to the red key level and then continues.

```text
Mechanical proxy?   Approved: FVG (Record 8, 3a/3b), trigger above manipulation HIGH (6), stop = manipulation extreme ∓ spread (7).
Status:             NOT YET FROZEN.
```

---

## Record 8 — 2026-10-05 — Sujan Theory 2 (HTF location → LTF range → manipulation → trigger → target): rule extract, NOT frozen

**Kind:** identity extract of a SECOND Sujan theory. **Not** a freeze, **not** a `SEM-*`, **not** a measurement contract.
**Lane:** semantic certification.
**Named by:** human bridge, 2026-10-05: "Consider as Sujan 2nd theory."
**Source:** a "CRT Model Master Specification" the bridge relayed from another LLM's chat (Level 4: bridged reading), plus the bridge's own rulings in this session (marked APPROVED). The relayed answers also said "Yours … not Sujan's". The bridge's direct instruction ("Sujan 2nd theory") governs, and that conflict is recorded here rather than resolved.
**Separation:** Theory 2 is its own object. It is NOT an edit of Theory 1 (SEM-031 / SEM-033 / Record 7), and no Theory 1 result (F-095 or the Record 7 proxies) transfers to it, in either direction. One visible difference: Theory 1's C2 manipulation "closed inside first range" (Record 7, 21:29–21:36), while Theory 2's Type A manipulation closes BELOW the range low (rule 4a).

| # | Rule | Statement | Status |
|---|---|---|---|
| 1 | Location first | Trade reactions at an HTF location, never a pattern alone. No HTF FVG / OB / Rejection Block ⇒ no setup. | Relayed (Level 4), not reviewed |
| 2 | Timeframe pairs | Location TF > execution TF: 1Mo→1D, 1W→4H, 1D→1H, 4H→15M. | Relayed, not reviewed |
| 3a | FVG | Standard 3-candle wick gap. Bullish: c1.high < c3.low, zone [c1.high, c3.low]. Bearish mirror. | APPROVED (bridge, 2026-10-05) |
| 3b | FVG fill | An FVG that price has traded into at all no longer counts. | APPROVED (reading pending confirmation) |
| 3c | Order block | Bullish OB: a "thick" bearish candle that sweeps the low of ≥1 preceding candle; sweeping ≥2 consecutive candles = stronger. Bearish mirror NOT stated. OB zone extent NOT stated. | Relayed; mirror + zone UNKNOWN |
| 3d | Rejection Block | Mentioned only. | UNKNOWN |
| 4 | CRT range | Range high/low = the range candle's high/low (NAS100 example: the 4H OB candle). Forms at/around the HTF location. | Relayed, not reviewed |
| 4a | Manipulation Type A | Thick bearish candle sweeps the range low and closes BELOW it. | Relayed answer, not reviewed |
| 4b | Manipulation Type B | Candle with a long lower wick sweeps the range low and closes back inside. | Relayed, not reviewed |
| 5 | Middle rule | The HTF level may sit anywhere inside the range (top/middle/bottom); the manipulation must happen "at/into" it. Codeable form UNKNOWN (zone merely inside the range vs. manipulation candle must touch the zone). | AMBIGUOUS |
| 6 | Trigger | A candle closes above the manipulation candle's HIGH (short: below its LOW). Entry = that close; the first SL/TP check is the next bar. | APPROVED (bridge, 2026-10-05) |
| 6a | Trigger timing | "The immediate bullish close above": the next candle only, or the first such close whenever it comes? No time limit stated. | MULTIPLE INTERPRETATIONS |
| 6b | Invalidation | A new low below the manipulation low before the trigger cancels the setup. The relayed answer says "implied by the stop placement", i.e. inferred, not stated. | INFERRED, needs confirmation |
| 7 | Stop loss | Manipulation candle extreme ∓ one spread (XAUUSD measured 0.09 USD/oz, F-082). | APPROVED (bridge, 2026-10-05) |
| 8 | Target | The opposite side of the CRT range. | Relayed, not reviewed |
| 9 | "Thick" | Visual/discretionary; no definition. Candidates relayed (body > 50% of range; body > 1.5× ATR14). | UNKNOWN; no proxy approved |
| 10 | Multiple sweeps raise target probability | Claim. | HYPOTHESIS, not a rule |
| 11 | Ignore | C2 chart annotations, blue lines, generic CRT/ICT terminology. | Relayed |

```text
Mechanical proxy?   Only rules 3a, 6, 7 (bridge-approved 2026-10-05). Everything else: N.
Status:             NOT YET FROZEN. No detector, SEM-*, or MC-* until 5, 6a, 6b and 9 are decided.
```

---

## Record 7 — 2026-09-26 — Five mechanical proxies measured as "Sujan" without identity review (DRIFT)

**Kind:** unapproved semantic replacements, recorded after the fact. **Not** a freeze. **Not** an identity certification.
**Lane:** measurement (research-only scripts under `results/pdh_pdl_weekly_open/2026-09-25/`, `results/user_rules_sleeve/2026-09-25/`).
**Named by:** human bridge, 2026-09-26: "The report successfully falsified several simplified versions of the idea, but it did not yet test the complete causal chain that Sujan claims to use."
**What went wrong:** this charter was not loaded before the 2026-09-25 tests. Test *designs* were bridge-approved as plans, but the equivalence of each proxy to Sujan's concept was never reviewed, and the published report (https://claude.ai/artifact/DwR7b67EdJhSMoc4d4UyB2, v1–v5) labelled results as Sujan's method. That breaks the Measurement Firewall (`:276-294`). CORRECTED in the report 2026-09-26 (scope banner + section 25).

### New Level-1 Sujan statements (relayed by the bridge, 2026-09-25; chat text, not transcripts)

- 15:55: "Upper line (PDH) & lower line (PDL) · RED LINE (WEEKLY OPEN) · every time, we need to see PDH & PDL (range) · Up/down - weekly open (key level) - location important." Plus: "Htf resistance - weekly open discuss on this first."
- XAU reference map (screenshot, Level 2): HTF resistance 4399–4404 → SWEEP (4435 possibly) → bearish reaction → 5m/15m displacement → RETEST → SHORT 4045 → 3942 | BREAK → ACCEPT 4481 → 4548. "Vol 100 - sell (distribution)".
- 21:02–21:05: "Put 1 hr candle close after sweep, not 15 min … we are trading daily range acting as a weekly open key level, so 1 hr confirmation require … 15 min data is good 3% per month profitability."
- 21:29–21:36: "1 hr crt happening in xau gold … 3rd candle distribution candle is happening … C1 accumulation, C2 manipulation done & closed inside first range … & C3 distribution candle … tats all we need to automate … C2 manipulation must occur at htf location." Live trade screenshot: BUY 0.4 @ 4276.30, SL 4269, TP 4299; TradingView "XAUUSD (1H) 1H-1D Model · Bias: Bullish · SMT: —".
- Note vs `:205`: C1/C2/C3/manipulation now appear in Sujan's own words. That does **not** make them equal to `ParentCRTTrack`'s C1/C2/C3 (F-077 still holds until reviewed).

### Proxies used (all UNVALIDATED; results apply to the proxy only)

| Sujan concept | Proxy measured | Approved as identity? | Status |
|---|---|---|---|
| PDH / PDL "range" | last closed broker-day D1 high/low | N | UNVALIDATED |
| Weekly open (red line) | open of first M15 bar of the ISO week (broker time). His chart's red lines 4309.273 / 4255.613 do NOT equal it (4373.77 for w/c 21 Sep) | N | UNVALIDATED — likely WRONG object |
| "Location important" | two readings, premium/discount vs trend side; later L1 (C2 wick swept PDH/PDL) and L2 (+weekly/day open) | N | UNVALIDATED |
| Sweep → reaction → displacement → retest → entry | single M15 (or H1) sweep bar, entry next open; displacement and retest DROPPED | N | UNVALIDATED (chain truncated) |
| Break → accept | two consecutive M15 (or H1) closes beyond | N | UNVALIDATED |
| C1 / C2 / C3 | `ParentCRTTrack` on closed H1; C2 close strictly inside C1; entry = C3 open; target = C1 far side; stop = C2 wick ± 0.50 or midpoint | N | UNVALIDATED |

### Dropped, not proxied (never measured)

HTF resistance zone construction · 5m/15m displacement · retest object · 5m entry trigger · stop rule (his 4269 is not C2's wick) · target rule (4045 → 3942 is not C1's far side) · "Vol 100 – distribution" · 1H-1D Model bias · SMT · invalidation / no-trade rules.

### Measurement Firewall statement

All 2026-09-25 results (15m sweep ~0R; break = gold drift; 1H variants; CRT proxy 57–62% wins below a 60–64% breakeven) are attached to the proxies above. They do **not** travel to "Sujan CRT." Identity: NOT YET FROZEN.

---

## Record 6 — 2026-08-29 — Bulk-candle proxy APPROVED (SEM-034), UNK-007 stays open

**Kind:** approved mechanical proxy. **Not** an identity certification and **not** a resolution of UNK-007.
**Lane:** implementation, under an approved proxy.
**Named by:** human bridge ("use the parquet layer to find them using OHLC parent bulk-candle timestamps").
**Built:** `src/research/sujan_manipulation/bulk_proxy.py` · SEM-034 · [object spec §5](sujan_manipulation_object.md)
**Supersedes:** Record 5c (`BULK_CANDLE_SELECTOR = UNRESOLVED`, `Mechanical proxy? N`). Record 5c is history and stands as written; it is not edited.

This is the first proxy approved anywhere in the Sujan lane. It is recorded in full because
charter `:98-102` permits one only when it is approved, recorded, **and still linked**.

---

### Review loop (charter `:300-320`)

```text
Concept:                 Parent bulk candle - "a visually dominant candle that defines a range."

Sujan statement
(quote + source):        NONE. This concept has no Sujan quote in the repository. The four
                         recorded evidence lines ("visually dominant" / "often large-bodied" /
                         "may also be wick-dominant" / "no approved percentage threshold
                         exists") come from the Phase-1 specification, which is bridge-authored.
                         No quote is fabricated to fill this field.

Semantic definition:     UNRESOLVED. Unchanged by this record.

Evidence:                The four lines above, and nothing else.

Confidence:              Possible (unchanged).

Open questions:          What "visually dominant" is a property OF - the candle alone, the
                         candle against its neighbours, its place in a higher structure, or
                         something that is not a bar property at all.

Mechanical proxy?        Y

Proxy:                   Top-N over the WHOLE corpus, computed twice and never merged:
                           - by FM-002 candle_range (high - low), and
                           - by FM-001 body_size (|close - open|)
                         Ties break by ascending bar index. N = 50.
                         No window, no percentile, no volatility normalisation, no threshold.

Approved?                Y - human bridge, 2026-08-29.

Linked original:         UNK-007 UNKNOWN_FOUNDING__SUJAN_BULK_CANDLE (stays status: open)

Status:                  UNVALIDATED
```

---

### Drift record (charter `:211-219`)

```text
Original concept:        Parent bulk candle = a VISUAL judgement, mechanically undefined.

Proposed interpretation: The 50 largest candles by range, and separately the 50 largest by
                         body, are CANDIDATES for that judgement.

Evidence:                None supporting the rule itself. Size is the only property of a
                         candle the recorded evidence mentions at all, and it mentions two
                         incompatible versions of it.

Reason:                  Bridge instruction to have the repository find parents from OHLC
                         rather than wait for a hand-supplied list that had not arrived.
                         The shortlist doubles as the hand-labelled set UNK-007's own
                         resolution_metric requires, so the proxy is also the instrument
                         for eventually testing the proxy.

Approval status:         APPROVED (proxy) / UNVALIDATED (as a reading of the concept)
```

---

### What stops this from silently becoming the definition

- `BULK_CANDLE_SELECTOR` reads `APPROVED_PROXY_UNVALIDATED`, never `RESOLVED`.
- UNK-007 stays `knowledge_status: UNKNOWN`, `status: open`, v2.
- **A candidate is not a parent.** The detector consumes only bridge-confirmed timestamps;
  `run_candidates` never feeds the detector.
- SEM-034 is a **separate versioned node**, so a future rule change is a new freeze rather
  than a retune of the detector (charter `:159`: new identity → new freeze).
- The confirmation page states on its face that it is a curation tool, not a measurement
  instrument, and that the proxy is UNVALIDATED.

### The v1 prohibition this overrides

UNK-007 v1 read: *"Do not close this by writing a size heuristic; a percentage, ATR or
body-ratio rule here would be exactly the forbidden visual-to-magnitude transformation."*
That was written 2026-08-28 by the coding layer. The bridge overrode it on 2026-08-29.

It is **retired as a block and retained as a caveat**, because the first run supplies
measured support for the caveat rather than against it:

| Measurement (XAUUSD M15, 47,275 bars, N=50) | Value |
|---|---|
| Overlap between the two rankings | **34 of 50** — the two size readings disagree on a third of the list |
| Corpus months represented (range / body) | **4 / 5 of 25** — 20+ months return no candidate at all |
| Parquet cross-check | AGREES, 47,166 rows, 0 mismatches, 109 csv_only as expected |

Size is measurable and the arithmetic is corroborated. Neither fact makes size the concept.

### Forbidden transformations (this record)

```text
SEM-034 shortlist        ->  the set of bulk candles
a candidate              ->  a parent
proxy APPROVED           ->  proxy VALIDATED
proxy VALIDATED          ->  UNK-007 resolved
overlap 34/50            ->  a fact about the market
20 empty months          ->  those months contain no bulk candles
a size rule              ->  what "visually dominant" means
an economic result       ->  evidence for or against this proxy
```

### Stop

UNK-007 stays **OPEN**. SEM-034 stays **UNVALIDATED**. "Strong confirmation" stays **UNKNOWN**.
No `MC-*`, no `F-*`, no economic claim, no G001, no production authority. The honest sentence
is unchanged: *we detected SEM-033, an object the human bridge specified* — now with the
addition that its parents were shortlisted by a proxy nobody has yet checked against a chart.

---

## Record 5 — 2026-08-28 — SEM-033 Phase-1 manipulation detector

**Kind:** bridge-authorised construction + four recorded semantic decisions. Not an identity certification.
**Lane:** implementation, downstream of semantic certification.
**Named by:** human bridge (`SUJAN_MANIPULATION_RESEARCH_PHASE_1` specification).
**Built:** [`src/research/sujan_manipulation/`](../../src/research/sujan_manipulation/) · SEM-033 · UNK-007 · [object spec](sujan_manipulation_object.md)
**Authority used:** charter `:392` — "No new `SEM-*` / `MC-*` / detector without a separate authorized construction change." This turn is that authorisation. Manifest: `docs/governance/build_manifests/CH-sujan-manipulation-phase1.impact.json`.

Detection only. No entry, target, stop, outcome, `MC-*`, `F-*`, G001, or production surface.

---

### 5a — What makes a sweep count (the Record 3 UNKNOWN / Q10)

```text
Original concept:        "What makes a sweep count / strong confirmation"
                         (Record 3, new UNKNOWN; packed to Sujan as Q10 in Record 4)

Proposed interpretation: A later candle that (1) purges the parent range high OR low
                         and (2) closes back inside the parent range.

Evidence:                Human bridge states this is Sujan's own answer (Level 1).

Reason:                  Answers the open question for THIS construction.

Approval status:         APPROVED (human bridge, 2026-08-28)
```

**Provenance caveat, recorded rather than smoothed over.** The charter's review-loop template
requires `Sujan statement (quote + source)`. **The verbatim wording is not in this repository.**
The definition reached the code as a bridge transmission, not as a pasted quote, and no quote is
fabricated to fill the field. Until his raw wording lands here, the honest status of this record
is: *bridge-asserted Level 1, source text absent.*

**Scope.** This closes the Q10 gap **for SEM-033 only**. It does not close it for SEM-031, for the
five FX screenshots, or for "Sujan CRT" generally. Record 3's other UNKNOWNs (which Daily range,
pending vs filled, whose lines, entry as band-edge) are untouched. Q10's second half — *strong
confirmation*, the filter that let XAUUSD be voided after the fact — is **NOT** answered by this
record and stays UNKNOWN.

---

### 5b — Vocabulary import: "manipulation"

```text
Original concept:        Charter :205 — "Absent from both source files: C1 / C2 / C3 /
                         manipulation. Do not import ParentCRT vocabulary into Sujan
                         identity (F-077)."

Proposed interpretation: The object is named SUJAN_MANIPULATION_RESEARCH_PHASE_1 and its
                         alert is SUJAN_MANIPULATION_DETECTED.

Evidence:                The bridge specified the name and, on being shown the :205
                         prohibition and offered two neutral alternatives, kept it.

Reason:                  Bridge naming choice; the collision is declared, not hidden.

Approval status:         APPROVED (human bridge, 2026-08-28), linked to the original
```

**Linked original.** SEM-033 is **not** `CRTState.MANIPULATION_C2` and not `ParentCRTTrack`.
`config_layer.parent_crt` is on SEM-033's forbidden-import list and the isolation is AST-enforced.
The shared English word carries no shared semantics: F-077 stands.

---

### 5c — BULK_CANDLE_SELECTOR

```text
Original concept:        Parent bulk candle - "a visually dominant candle that defines a
                         range." Evidence: visually dominant; often large-bodied; may also
                         be wick-dominant; NO approved percentage threshold exists.

Proposed interpretation: NONE. Mechanical proxy? N.

Evidence:                The four statements above are the entire evidence base. They are
                         jointly insufficient to separate bulk from non-bulk, and two of
                         them point at different quantities (body size vs wick size).

Reason:                  The specification instructs that this not be self-resolved.

Approval status:         UNRESOLVED - registered as UNK-007, a permanent citizen
```

Per charter `:320`, `Mechanical proxy? N` and the concept is still needed ⇒ the honest output is
`NOT YET FROZEN`, and no proxy is invented to unblock the build. The package ships **no selector**;
parents are supplied externally and every run manifest records `BULK_CANDLE_SELECTOR: UNRESOLVED`.
A percentage, ATR or body-ratio rule here would be the forbidden `location → ATR distance` class of
transformation.

---

### 5d — "Closes back inside the parent range"

```text
Original concept:        "Closes back inside the parent range."

Two readings:            (A) FULLY inside: range_low < close < range_high
                         (B) back past the PURGED side only - bare SP-001 semantics,
                             which admits a candle that purges the high and closes
                             below the range low

Evidence:                (A) is what the words say. (B) is what the repository already
                         implements in SP-001, and the difference is invisible until an
                         outside candle appears.

Reason:                  Bridge chose the literal reading.

Approval status:         APPROVED (A) - (B) preserved, not discarded
```

**How (B) is preserved.** Every alert carries `bar_close`, `range_high`, `range_low`, `bar_high`
and `bar_low`, so reading (B) is fully re-derivable from any artifact without re-running anything.
The choice is pinned by `test_purge_high_closing_below_range_low_is_not_manipulation`, which fails
under (B) — the reading is enforced mechanically, not asserted in prose.

---

### 5e — Reduction to a single-candle predicate

```text
Original concept:        Charter :259-272 (Narrative Preservation) - "Do not reduce
                         path-dependent concepts to single candle / single predicate /
                         single threshold / single score without evidence. Path may be
                         load-bearing."

Proposed interpretation: Manipulation is evaluated as properties of ONE later candle.

Evidence:                The specification two numbered conditions are stated as
                         properties of a single candle ("A later candle: 1 ... AND 2 ...").

Reason:                  Bridge-specified. NOT model-inferred and NOT evidence-derived.

Approval status:         APPROVED as specified; the path reading stays open
```

This is recorded because the charter says the reduction needs evidence and **there is none** — only
a bridge instruction. The multi-candle reading (purge on one bar, reclaim on a later one) is listed
as a preserved ambiguity in the object spec §6 and is deliberately not implemented. Whether
manipulation is a bar property or a path stays **UNKNOWN**.

---

### 5f — A case the specification did not cover

```text
Original concept:        side is HIGH_SWEEP or LOW_SWEEP.

Observed gap:            An outside candle can purge BOTH boundaries and still close
                         fully inside, satisfying the frozen definition while matching
                         neither enumerated side.

Proposed interpretation: A third value, BOTH.

Reason:                  The definition admits the case; the enum did not enumerate it.
                         BOTH is a label for an observed case, not a proxy for a concept.

Approval status:         APPROVED (human bridge, 2026-08-28)
```

Neither side is silently picked and the event is not silently dropped. Pinned by
`test_both_boundaries_purged_emits_side_both`.

---

### Forbidden transformations (this construction)

```text
visually dominant candle  ->  size / percentage / ATR / body-ratio rule
manipulation (SEM-033)    ->  CRTState.MANIPULATION_C2 or ParentCRT C2
SEM-033 alert count       ->  a rate, a quality, or an edge
SEM-033 detection         ->  entry, stop, target, or outcome
Q10 answer for SEM-033    ->  Q10 answered for Sujan CRT generally
"strong confirmation"     ->  answered (it is not; still UNKNOWN)
a future SEM-033 result   ->  a statement about Sujan CRT
SEM-031 / F-095           ->  anything in this object (no import, no retune)
```

### Stop

`BULK_CANDLE_SELECTOR` remains **UNRESOLVED** (UNK-007). "Strong confirmation" remains **UNKNOWN**.
Identity of the object as *Sujan's* manipulation is **NOT CERTIFIED** — the coding layer cannot
self-award that. No `MC-*`, no `F-*`, no economic claim, no G001, no production authority.

The honest sentence is: *we detected SEM-033, an object the human bridge specified.*

---

## Record 4 — 2026-08-28 — Questions packed for Sujan (human bridge)

**Kind:** outbound identity questions. Not a freeze. Not a proxy.
**Lane:** semantic certification.
**Pack:** [`.grok/SUJAN_QUESTIONS.md`](../../.grok/SUJAN_QUESTIONS.md)
**Rule:** paste only §2 to Sujan. §1 stays with the bridge. Answers return as his words; bridge certifies freeze.

Q1–Q8 = Record 1 Live HTF Objective. Q9–Q11 = Record 3 (sweep count / which Daily range / pending vs filled). Q12–Q16 = steelman still-open (sleeping→powered, stop, 1:5, Romeo, accumulation). Do not translate his answers into C1/C2/C3 or SEM-ids unless he says those things.

---

## Record 3 — 2026-08-28 — Third source opened: `SujanTraderCRTProof.txt`

**Kind:** source opened for UNKNOWN-gathering. Not a freeze. Not Sujan speech.
**Lane:** semantic certification.
**Named by:** human bridge (“analyse … and gather UNKNOWNs”).
**File:** repo-root `SujanTraderCRTProof.txt` (223 lines; concatenated analyst turns, 2026-08-28 mtime).
**Images:** the five phone screenshots are **not in this repo**. The file refers to `/mnt/user-data/uploads` (external). This record is of the **reconstruction text**, not of the pixels.

### Whose voice

| Voice | Treat as |
|---|---|
| This `.txt` | Analyst (not Sujan) reverse-engineering five posted charts. Same class as the AI interlocutor: **trigger, not identity**. |
| Fragments attributed to the poster | “1D CRT”; claimed RR 1:4.5–1:8.5; XAUUSD “invalid — not seeing strong confirmation”; “90% target reached”; rupee running totals. Reported, not quoted from `SujanTraderCRTExp.txt`. |
| Chart geometry as described | Level 2–3 **if** the images existed here. They do not. Treat reconstructed prices as **UNVALIDATED observation**. |

Do **not** treat the 2026-08-22 session claim that “the five FX setups validate Phases 6/7/8” / “the sweep-validity rule is fully specified.” This file’s own load-bearing gap is the opposite: **what makes a sweep count / strong confirmation is unwritten**, and XAUUSD was voided after it failed.

### Analyst reconstruction (not identity)

Four steps the analyst says all five charts obey (`:99-107`):

1. Wait for a sweep of a prior swing extreme.
2. Entry = reclaim at the swept level (pink/gray box boundary).
3. Stop ≈ just past the sweep wick (revised `:178-180`: past the extreme on NZDCAD and AUDCHF; **inside the wick** on NZDUSD).
4. Target = opposite end of the **prior daily range**.

Also claimed (`:140-144`): green dotted **HTF Open** on all five; Daily open as pivot; “1D CRT” executed on 1H/2H/3H is not a mismatch.

Independently triple-read rows (analyst): NZDCAD, AUDUSD, NZDUSD. AUDCHF/USDCHF stops or targets were **RR-derived** (`:192-207`) — circular if used as evidence that RR is an output of stop distance.

Boxes sit **to the right of the last candle** (`:129-132`): pending projections, not fills, at post time.

### UNKNOWN inventory after this source

Status tokens only. No freeze.

| UNKNOWN (owner) | This file | Status now |
|---|---|---|
| How known while the HTF candle is open (Record 1) | Pending boxes in future chart space; no one-sentence job written on the shot. HTF Open is a drawn line, not a naming procedure. | **UNKNOWN** as a procedure. **OBSERVED:** geometry can be drawn before a fill. |
| Completion vs invalidation (Record 1) | XAUUSD voided *after* failure: “not seeing strong confirmation” (`:7`, `:123-125`). One result reported as “90% target reached,” not closed (`:15`). | **UNKNOWN.** Post-hoc void is not a completion rule. |
| One TF, two jobs (Record 1) | Five **pairs**, one macro thesis (USD strength / CHF/antipodean). Not two jobs on one candle. | **AMBIGUOUS** unchanged. |
| Daily vs Weekly remaining target (steelman) | Analyst: target = opposite **prior daily** range; Weekly unused on these five. Also: Daily **Open** as live pivot. “Prior daily range” vs “today’s range from Open” are **two readings in the same reconstruction**. | **AMBIGUOUS.** Sample-only. Not a freeze. Does not license SEM-031 last-closed D1. |
| Romeo 1-3-5-9 | Absent. Chart TFs 1H/2H/3H. Post clocks 22:43–02:34, 12:11. | **UNKNOWN** unchanged. |
| Numeric expansion / accumulation / displacement cuts | Absent. | **UNKNOWN** unchanged. |
| CRT-invalidation construction (steelman) | Stop ≈ beyond sweep wick, with a documented NZDUSD inside-wick exception and sub-10px error bars (`:180-182`). Sparta indicator draws pink/gray boxes (`:58`). | **INSUFFICIENT / MULTIPLE INTERPRETATIONS.** Not frozen. |
| Live HTF Objective ≡ SEM-009 | Not reopened. Daily-range opposite ≠ H4 C3-vs-C1 `ObjectiveStatus`. | Record 2 **REJECTED AS EQUIVALENCE** stands. |
| What is an objective (job set, Record 1) | These five only show **range-traverse to the other Daily boundary**. CRTExp also lists OB mitigate, FVG fill, sweep yesterday, etc. | **PARTIAL** on this sample. Does not close or kill the broader example set. |
| Parent-interior x-ray | LTF charts of a Daily thesis. Visual usage, no rule. | **OBSERVED**, not frozen. |
| Sleeping → powered | Sweep-then-reclaim is described; “strong confirmation” is the void filter and is undefined. | **UNKNOWN** unchanged. |

### New UNKNOWNs this file names (did not exist as labelled gaps before)

| UNKNOWN | Why it is unknown |
|---|---|
| **What makes a sweep count / “strong confirmation”** | The file’s own remaining gap (`:120-125`). The input that let XAUUSD be voided after the fact. |
| **Pending vs filled** | Boxes in empty future space. The file asks whether any of the five were filled; no answer in-file. |
| **Which Daily range is the target** | “Prior daily range” (`:50`, `:106`) vs “Daily open as pivot, purge one side of **the** daily range” (`:144`). Closed yesterday vs live today. |
| **Whose lines** | Sparta indicator vs hand-drawn band (three crimson lines on AUDUSD `:135-136`) vs dashed diagonal on USDCHF (`:138`). |
| **Entry as band-edge vs price** | AUDUSD stack 0.71271 / 0.71233 / 0.71230 (`:135-136`). Adds a parameter the four-step list does not name. |

### Forbidden transformations (this source)

```text
five FX screenshots     →  identity-certified Sujan method
analyst 4-step list     →  SEM-* / detector
target = prior daily    →  Live HTF Objective freeze
target = prior daily    →  SEM-031 last-closed D1 (already UNVALIDATED)
HTF Open line           →  live-naming procedure
XAUUSD post-hoc void    →  invalidation geometry
Sparta boxes            →  Sujan-authored levels
Phases 6/7/8 checklist  →  proven by these shots
```

### Stop

Third source is **OPENED**, not certified. `Mechanical proxy? N`. Identity of Live HTF Objective remains **UNRESOLVED**. No `SEM-*`, no `MC-*`, no detector, no SEM-031 retune.

---

## Record 2 — 2026-08-28 — Live HTF Objective ≠ SEM-009

**Kind:** human-bridge equivalence verdict (not a freeze, not a SEM-009 defect).
**Lane:** semantic certification.
**Named by:** human bridge.
**Does not change:** SEM-009 math, `objective_gate`, ParentCRT, F-078, F-095.

```text
Original concept:
Live HTF Objective

Proposed interpretation:
SEM-009 ObjectiveStatus

Evidence:
SEM-009 resets on new C1.
Single parent track.
Single parent timeframe on ACTIVE.
Sticky snapshot after closed H4.

Reason:
Observed behavior differs from transcript narrative.

Approval status:
REJECTED AS EQUIVALENCE

Identity status:
UNRESOLVED
```

SEM-009 remains the ParentCRT C3-range snapshot (`htf_state.resolve_objective`). That object is CURRENT and MATHEMATICALLY_DEFINED for the repo. It is **not** the Sujan noun. `different ≠ wrong`. Do not “fix” SEM-009 toward the transcript. Do not retune SEM-031. Do not invent a proxy to replace the rejected mapping.

Live HTF Objective stays **NOT YET FROZEN**. Remaining UNKNOWNs (live-naming procedure, completion vs invalidation, one-TF multi-job, Daily vs Weekly remaining target) are unchanged from Record 1.

---

## Record 1 — 2026-08-28 — Live HTF Objective

**Kind:** identity extraction opened (not a freeze).
**Lane:** semantic certification.
**Named by:** human bridge.
**Mechanical proxy:** none approved. Status: **NOT YET FROZEN**.
**Equivalence stamp (Record 2):** SEM-009 `ObjectiveStatus` = **REJECTED AS EQUIVALENCE**. Identity of Live HTF Objective = **UNRESOLVED**.

### Drift already on disk (do not treat as this identity)

| Original concept | Proposed interpretation | Evidence | Reason | Approval |
|---|---|---|---|---|
| Live HTF Objective | SEM-031 trade target = last closed Daily high/low | `docs/research/sujan_veto_chain_object.md` §4.9; SEM-031 `mathematical_definition` | A **price of a closed candle** standing in for a **named unfinished job of an open candle** | Unapproved. Recorded as UNVALIDATED proxy in the identity lock. |
| Live HTF Objective | SEM-009 `ObjectiveStatus` EXISTS/ACHIEVED/INVALIDATED from last **closed** parent close vs C1 range | `market_ontology.yaml` SEM-009 | Post-close range-touch of a ParentCRT C3 narrative. Not a live job. F-077: not Sujan vocabulary. | **REJECTED AS EQUIVALENCE** (human bridge, Record 2). |
| Live HTF Objective | SEM-022 ladder aligned iff every rung `EXISTS` and **same direction** | `market_ontology.yaml` SEM-022 | Direction agreement is not “named job agreement.” | Not this concept. |
| Live HTF Objective | Steelman: “anticipate unfinished HTF objective; cannot name it → flat” | `.grok/SUJAN_ACCEPTED.md` | Bridged reading (Level 4). Useful. Not Level 1. | Steelman, not freeze. |

Do not retune SEM-031 toward this extract after F-095.

### Review loop

```text
Concept:
Live HTF Objective

Sujan statement (quote + source):
See §Quotes below. Direct Sujan turns are not isolated in the files.
The load-bearing restatements are AI interlocutor, Levels 2–3 of the source hierarchy,
plus one thesis the interlocutor attributes to Sujan (4325 → 3825).

Semantic definition:
CHARACTERIZED, not frozen.

An HTF objective is the named job a higher-timeframe candle is trying to
accomplish before that candle closes. It is not a bullish/bearish label.
It is supposed to be writable as one sentence while the candle is still open.
If it cannot be named, there is no trade. Completion is a separate question
from existence. The trade’s target, when one is taken, is that named job.

Evidence:
Transcript usage (51 hits in CRTExp; homonym “objective”=impartial excluded).
Steelman. SEM-031/SEM-009 are contrast, not support.

Confidence:
High that the concept is load-bearing.
Medium that the semantic definition above is the right reading.
None that a formula exists.

Open questions:
What is an objective?          → PARTIAL (job, not direction; example set open)
How known while candle open?   → UNKNOWN (naming act; no test)
Can multiple coexist?          → PARTIAL (across TFs yes; one TF AMBIGUOUS)
When considered complete?      → UNKNOWN / MULTIPLE INTERPRETATIONS

Mechanical proxy?
N

If yes: n/a
```

### Quotes (whose voice)

**The live-before-close question** (AI restating the framework):

> “What is the higher-timeframe candle trying to accomplish before it closes?”
> (`SujanTraderCRTExp.txt:278`)

> “If you can define the objective before the candle completes, then the lower
> timeframe becomes a tool for confirmation rather than prediction.”
> (`SujanTraderCRTExp.txt:448`)

> “What must today’s Daily CRT accomplish before it closes?”
> Examples: sweep yesterday’s high; sweep previous week’s low; mitigate Daily OB; fill Daily FVG.
> “Now every lower timeframe must support that objective.”
> (`SujanTraderCRTExp.txt:519-528`)

> Write one sentence only: “This week’s objective is to seek ______.”
> If Monthly unclear → no trade.
> (`SujanTraderCRTExp.txt:496-511`)

**Existence vs completion** (AI-proposed addition):

> Instead of “Is this a bullish CRT?” ask “Has this CRT completed its objective?”
> (`SujanTraderCRTExp.txt:454-458`)

> “I think we should add one more concept: ‘Objective achieved?’”
> (`SujanTraderCRTExp.txt:1188-1190`)
> — the interlocutor treats completion as **not already frozen**.

**Sujan-attributed worked example** (interlocutor: “your thesis”):

> If the 3M CRT rejects from its supply zone around 4325, its objective could be
> the 6M equilibrium around 3825 (~500-point downside).
> (`SujanTraderCRTExp.txt:1089-1119`)

**X-ray while candles are open** (AI walking gold; not a closed-bar lookup):

- Monthly: not yet complete; job appears to be “continue rebalancing higher…” (`:793-801`)
- Weekly: “still wants to test liquidity above” (`:836-841`)
- 4H: “trying to continue with the Daily objective” (`:888`)
- Late: “buying where the higher-timeframe candle is already close to completing its immediate objective” (`:918`)

**Checklist examples** (AI, Phase 3 / Phase 8):

> “What is today’s objective?” Sweep buy side / sell side / reach Monthly OB / reach Weekly OB / fill imbalance. Cannot answer → skip.
> (`SujanTraderCRTExp.txt:1271-1287`)

> Target = HTF CRT objective. (`:1359`)

### Answers from evidence (not freeze)

**What is an objective?**

A **named unfinished job**, distinct from bias. Jobs that appear as examples, not a closed set: seek external liquidity; sweep a stated high/low; mitigate an HTF order block; fill an imbalance/FVG; reach a higher-timeframe level (Monthly OB, Weekly OB, 6M equilibrium); test liquidity above; continue a higher TF’s job.

It is **not**: close>open, last-closed high/low, SEM-009 range-touch, GoalSpec/G001.

**How is it known while the candle is open?**

The corpus **asserts** it must be named before the candle completes. The test given is: write one sentence; if you cannot, skip. No formula. No closed-bar lookup. **UNKNOWN** as a mechanical procedure.

Anticipate vs confirm (AI, `:291-295`) is asked of Sujan and **not answered in-file**.

**Can multiple objectives coexist?**

- **Across timeframes: yes.** 6M/3M/MN/W/D each have one. Nested example: 4H continues Daily; 3M job is 6M equilibrium.
- **A+ filter (AI):** only when they “point toward the **same** objective.”
- **One TF, two jobs at once:** AMBIGUOUS. Phase 3 lists alternatives. Steelman says one target.
- **Which remaining job is the trade target** if Daily and Weekly both still have path: still open (steelman).

**When is an objective considered complete?**

MULTIPLE INTERPRETATIONS, none frozen:

| Candidate | Support | Problem |
|---|---|---|
| Price reached the named level | 3825 as 6M midpoint; “reach Monthly OB” | Reaching ≠ holding; 4325 is a decision zone, not auto-complete |
| Stated liquidity taken | “sweep completed?” | Sweep can be the job or the activation of a different job |
| 3-candle sequence finished | Monthly “not yet complete”; no completed reversal or continuation | Sequence complete ≠ job complete |
| Candle close | “before it closes” is about **knowing** the job, not completing it | Homonym with closed-bar proxies |
| Invalidated rather than complete | 3M close strongly above 4325 → stop expecting 3825 | Invalidation ≠ achievement |

The AI adding “Objective achieved?” as a new question is evidence completion was **not** a settled primitive in the chat.

### Forbidden transformations (this extract)

Do not automatically convert:

```text
live HTF objective  →  last closed Daily high/low
live HTF objective  →  SEM-009 ObjectiveStatus
live HTF objective  →  body bias (close>open)
live HTF objective  →  any ATR band
```

### Stop

`Mechanical proxy? N` → **NOT YET FROZEN**. No `SEM-*`, no `MC-*`, no detector, no retune of SEM-031.
Remaining UNKNOWNs go to the human bridge and/or Sujan.
