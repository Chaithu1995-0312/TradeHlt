# Path A — Findings vs four MATCH atlases (2026-08-28)

> Point-in-time governance audit. Not a fifth atlas. Not G001.
> Atlases (all MATCH 2026-08-27/28): leakage · state_value · asymmetry · lifecycle.
> Question: which findings are **supported by those outputs**, and which carry
> **interpretation beyond what the atlases prove**.

Authority ladder: atlas row = information. Finding = claim. G001 = not earned here.

---

## Scope

Only F-ids that (a) cite these atlases, (b) are cited **by** the atlas write-ups, or
(c) are used to explain an atlas row. F-019…F-042 crypto/FX nulls are out of scope
unless an atlas is used as their evidence (none are).

Path-conditioned = rates/MFE **after** t=0 on stored walks (`y_tp1`, `y_mfe_r`,
reached-0.5/1/2R). Not t=0 policy. Leakage extra keys set `"lookahead": true`.

---

## Verdict table

| F-id | Atlas relation | Exact evidence of the **finding** | Atlas rows that exist | Overstate? | Authority from path-conditioned evidence? |
|---|---|---|---|---|---|
| **F-088** | Atlas **cites** F-088. Finding does **not** cite the atlas (predates it, 2026-08-21). | `forward_walk` vs production partial/trail; `_intrabar_trigger_price` SL-first; 6.81% of 188,628 units, +0.0866R. `docs/current-findings.md` F-088 Evidence. | Leakage exclusive `leak_reached_2_missed_tp=28007` (0.297). Nested 2R-missed-TP same count. | **Not in the finding.** Overstate is in the **spec lock** (below): atlas *count* ≠ SL-first *mechanism*. | **No** for F-088 itself (walk kernel). **Yes** if anyone treats 28,007 as proof of SL-first. |
| **F-091** | Finding **refuses** the full-sample atlas as gate. | Sealed `MC-ASYM-XAUUSD-M15-V1` holdout: contrast +0.415→+0.469; E[ΔMFE] +0.438→**−0.546**. `asymmetry-holdout-2026-08-24.md`. | Asymmetry unconditional E[ΔMFE]=**+0.239**, P(Δ>0)=0.531, n=47,166. trend_bias spread 0.457. | Finding is **stricter** than atlas §3 “gold’s long-side path bias.” Atlas mix is what F-091 discarded. | Contrast is on ΔMFE (path). Finding already says not book PnL, not side picker. **No extra authority.** |
| **F-066** | Atlas **caveats** hour/session with F-066. Finding does not cite atlas. | BTC cross-corr + NFP; 53.36% session relabel. `mt5_candle_fetcher.py`. | state_value hour E[MFE] spread 3.13; session 2.20. Asymmetry hour ΔMFE spread 0.923. | Finding not overstated by atlas. **Atlas hour/session cells are not UTC edges.** | Using those cells as session policy would infer authority from F-066-contaminated path MFE. Finding forbids that. |
| **F-086** | Atlases say “does not reverse F-086.” Finding does not cite these four files. | Every-bar×side oracle, 377,256 units, 0/84 cells clear zero. Different object. | Leakage 0.476 1R-missed-TP; state_value path_net=0 except side ±0.239. | No. Different grain (vocabulary at t=0 vs path after entry). | Do not read leakage 47.6% as “the vocabulary marks winners.” |
| **F-092** | Same split as F-091. Not an atlas gate. | MC-MAGPRIOR holdout Arm S +0.265→+0.209. | state_value trend_bias E[MFE] spread 0.239 (both-sides, path_net=0). | state_value trend_bias spread is **not** F-092’s given-side prior. Same column, different y. | Conflating the two would invent a side picker. Finding already says not a side picker. |
| **F-093** | Note uses 2R-missed-TP + F-088. | MC-RNET overlay +0.0058→+0.0064 on −0.55R book. | Leakage 28,007 2R-missed-TP. | **Note over-attributes:** “2R-missed-TP leak holds +0.50R extra MFE and +0.006R booked **(F-088 SL-first)**.” Overlay numbers are the MC. SL-first is imported, not measured in F-093. | Tiny overlay on a losing book: finding already E-001. SL-first sentence is Path C residue. |
| **F-069** | Lifecycle caveated as engine not resolver. | Engine vs resolver 88.16%, Category C. | lifecycle transitions n=5269 including RESET folds; TRADE_OPENED=3. | Finding not based on this journal. Journal is one engine run. | Treating journal RANGE occupancy as resolver state would collapse F-069. Bot already named this. |
| **F-022** | Atlas governing y = `y_tp1`, never stream `outcome`. | opportunities.jsonl 36.8% self-consistent. | (negative citation) | Atlas discipline holds. | Using `outcome` as leakage y would be F-022 authority theft. Not done in these four runs. |
| **F-065** | Asymmetry volume_spike spread 0.159. | volume_spike unused by CRT `when:`. | Asymmetry extra cells. | Atlas reports a contrast. Finding says unused as CRT predicate. Contrast ≠ gate. | No. |
| **F-089 / F-021** | Lifecycle FILTER_REJECTED 19 OFF_SESSION; RETEST_REPLAY 19/23. | F-089: 4 reason-flips, 0 outcome-flips, **different configs**. F-021: BNBUSDT session selection. | 19 off_session on **this** `v2_multi` journal. | Do not merge 19 with F-089’s 4, or with F-021’s crypto spine. Process fact only. | n=3 / n=19 is not session-edge authority. |

No finding in the table **earned G001** from an atlas row.

---

## The one spec sentence that overstates (not an F-id)

`docs/research/parquet_evidence_layer.md` “Demonstrated vs unproven”:

> Discover path-level information — Proven — 47.6% reach ≥1R and miss unit TP; **2R-missed-TP is F-088 SL-first**

Split:

| Clause | Status |
|---|---|
| 47.6% = 44,858/94,332 reached 1R missed unit TP | **Atlas-proven** (leakage MATCH). Path-conditioned. |
| 28,007 reached 2R missed TP | **Atlas-proven.** Exclusive ladder. |
| “is F-088 SL-first” | **Not atlas-proven.** F-088 is a walk-kernel finding. The atlas does not inspect `_intrabar_trigger_price`. |

That clause is the “travel, oscillate, and eventually resolve” class: mechanism inferred from a count. Corrected in the spec this turn (count stays; mechanism tagged hypothesized). Path C remains the attack on F-088 itself.

---

## What the four MATCH files actually prove

| Atlas | Proves | Does not prove |
|---|---|---|
| leakage | Path vs frozen 2R unit TP on this ledger | t=0 policy; SL-first; production partial/trail |
| state_value | E[MFE]/time/TP1 by stored column; path_net=0 except side ±0.239 | CRT engine state; UTC session; expectancy |
| asymmetry | Full-sample E[ΔMFE]=+0.239 mix; FM-054 scales excursion | Side picker; holdout (that is F-091, different artifact) |
| lifecycle | This journal’s funnel and RESET_HTF 1442/1798; TRADE_OPENED=3 | Resolver occupancy; NS 16-trade walk; economics |

---

## Bot

No drop job this turn. Cited counts already MATCH in `leakage/` `state_value/` `asymmetry/` `lifecycle/` reports. Independent re-read not in doubt.

## Residue (not this audit)

- **P-PATH-C:** attack F-088 SL-first on the 28,007 cell (source, not atlas).
- **P-PATH-B:** t=0 geometry on 3 TRADE_OPENED.
- **P-PATH-D:** provenance map of the table above.
