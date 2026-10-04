# Chapter 19 — The Research Programs: Falsification as a Discipline

**Part VII — Research**
Status of this chapter: Written (research data table expanded Grok pass; Program 9 stalled-run evidence added, reconciliation pass 2026-08-07)

## Why this chapter exists

[Chapter 1](01-why-tradelatest-exists.md) promised that pattern interpreters and, by extension,
trading ideas in general are "measured, never asserted." This chapter is where that promise gets
tested at scale: a numbered sequence of Research Programs, each pre-registered, each run to a
decisive conclusion, and — almost without exception so far — each one closing as an honest null
result. That's not a failure of the research effort. It's the effort working exactly as designed.

## What problem it solves

Gives a reader the shape of the research history **with concrete result data** (not only slogans):
what was tested, sample sizes / key metrics where registered, the verdict, and why "0 PROMOTE"
across program after program is a *credible* finding rather than a broken research pipeline.

## What you need to already know

[Chapter 16](16-config-first-and-promotion.md)'s Authority Ladder — every program below is that
ladder applied to a specific hypothesis: information existing is not the same as economic value,
which is not the same as earned authority.

## The idea

### Research results at a glance (data table)

Primary authority for every row: `docs/current-findings.md` (findings `F-0xx` below). Shared
measurement standard for economic arms unless noted: **intrabar_fixed exit model + 12 bps**
round-trip cost, absolute expectancy gate (E must clear 0 OOS to PROMOTE), plus controls /
permutations as each program pre-registered. All economic cells below are **research-only** —
none of these results grants production fusion weight.

| Prog | Question (one line) | Key data (registered) | Verdict | Finding |
|---|---|---|---|---|
| **1** | Any next-bar directional edge on crypto majors? | Toys: baseline_delta vs random ≈0 (−0.076…+0.033); spine 5–13 trades/inst → n&lt;30; pooled n=30 **E=−0.399** | **0 PROMOTE / KILLED** | F-019 |
| **1b** | Conditional pockets (session×vol×mom, h≤20)? | 25/25 partitions BH-significant but IG≈0.001–0.0036 bits; Stage-3 economics on 74 cells → **0 pockets** | **ENTROPY_LEAD_NO_ECON** | F-020 |
| **1c** | Spine RETEST selection skill beyond session? | Selected−rejected ΔE=+1.17R but **SESSION≡ALL** rejects; ZONE 0/110; SCORE p=0.327 | **Session filter only** | F-021 |
| **1d** | Exit/cost grid rescue expectancy? | Universe n=53,629; **every** SL×TP cell E_oos&lt;0; best −0.271; reality_gap +4.16R (entry info, not exit) | **Exit is not the lever** | F-025 |
| **2** | Completed sweep→disp→retest &gt; bare sweep? | Funnel retest n=47 (~1% completion); excursion_asym(h8)=**−0.319**; loses all 4 controls | **INSUFFICIENT_POWER / FROZEN** | F-026 |
| **3** | H1/H4 rescue directional edge? | **0 PROMOTE** H1 and H4; H1 E_oos −0.136…−0.266; H4 expansion_breakout ~gross 0 then pooled −0.0009 | **CLOSED null** | F-027 |
| **P&F** | Point-and-figure double-top/bottom edge? | BNB n=8554, PF=0.528, E=**−0.454**, WR=0.327; loses random_uniform ΔE=−0.039 | **REJECT / FROZEN** | F-028 |
| **4** | Vol-regime LEVEL consumable directionally? | H_atr=0.885 (vol memory real); **0 REGIME_EXPLOITABLE**; toys n=3.7k–35k still E≈−0.14…−0.35 | **Informative ≠ money** | F-030 |
| **4b** | Markov P^H transition forecast? | 0 REGIME_EXPLOITABLE / 15 scopes; toys **REGIME_REDUNDANT** vs level+lag | **CLOSED redundant** | F-043 |
| **4d** | MTF compression→expansion (Stage1 info / Stage2 econ)? | Stage1 UNIVERSAL p≈0.0005; Stage2 directional consumer **0 PROMOTE** (crypto E −0.25…−0.60R) | **Info yes / money no** | F-040 |
| **5** | Cross-sectional relative-value monetizable? | 5 interpreters, n=722–8,758; momentum PF=0.335; 0 PROMOTE | **KILLED (panel axis)** | F-032 |
| **6** | Carry/basis as signal on spot dispersion? | 8 interpreters n=722–4,373; E∈[−0.0032,−0.0016]; 0 PROMOTE | **KILLED** | F-033 |
| **6b** | Funding cashflow harvest net of costs? | 4 harvest_full REJECT n=104–729; pre-cost +1…+6 bps &lt; ~24 bps RT cost | **KILLED / STOP** | F-034 |
| **FX** | Program-1 null generalizes off crypto? | 5 FX majors; toys n=7.7k–17k PF 0.02–0.10 E −1.5…−2.8R; 0 PROMOTE | **Null generalizes** | F-035 |
| **8** | Weekly Mon–Fri liquidity-sweep ontology (FX)? | 6 scopes; pooled n=512 **E=−0.634R PF=0.457**; 0 PROMOTE | **CLOSED null** | F-042 |
| **7** | Open Interest | Named out-of-scope for P6; **not run** in findings ledger as of book sources | **NOT RUN** | — |
| **9** | M5 multi-TF expansion + OCO straddle | Pre-reg frozen; `resample_parity` PASS; one Stage-1 run attempted 2026-07-04 — **0-byte log, ~2-min pid window, no output JSON** | **PRE-REGISTERED / STALLED RUN** | H-016 (status: open) |

**How to read the table:** "0 PROMOTE" means *no cell cleared the fixed absolute-expectancy bar under
the pre-registered cost/exit model* — not "the research code failed." Several rows are
statistically informative (entropy, vol memory, Stage-1 transition IG) yet economically dead for
spot directional (or carry) constructions. That split is the point of the Authority Ladder.

**Where the raw artifacts live** (examples; full paths in each finding's Evidence field):

| Family | Typical artifact roots |
|---|---|
| Program 1 qualify | `results/research/qualification/` |
| Conditional entropy | `results/research/phase_b/` |
| Selection effect | `results/research/phase_s/` |
| Exit grid | `results/research/phase_d/` |
| Structural asymmetry | `results/research/phase_e/` |
| HTF qualify | `results/research/qualification_htf/` |
| Regime / transition | `results/research/regime/`, `results/research/candle_state/` |
| Cross-section / carry | `results/research/cross_sectional_*.json`, `carry_*.json`, `harvest_*.json` |
| Weekly sweep | `results/research/weekly_sweep/` |
| Program 9 M5 | `results/research/m5_mtf/` |
| MSIP shadow hyps | `results/research/h_msip_001/`, `h_msip_002/` |

### The gate every program runs through

Nearly every program in this ledger is tested against the same standard: a pre-registered
hypothesis, an intrabar-realistic exit model with real transaction costs (not close-only fills),
and a decision rule that requires *absolute* expectancy above zero out-of-sample — not just
beating a control. A program is only allowed to "PROMOTE" a finding into production authority if it
clears that bar; anything else is `REJECT`, `INSUFFICIENT_POWER`, or `REDUNDANT` (statistically real
but fully explained by something already known).

### The ladder, program by program (narrative)

- **Program 1 — Next-Bar Directional Ontology.** The foundational sweep: is there *any* directional
  edge in next-bar entries across crypto majors, at any conditioning level (session, volatility,
  momentum)? Ran through qualification, conditional-entropy pocket search, a selection-effect
  isolation, a full trade-anatomy audit, and an exit/cost grid — every stage closed null. **CLOSED /
  KILLED.** This is the foundation the rest of the ladder builds on.
- **Program 2 — Structural Asymmetry.** Does a *completed* sweep→displacement→retest sequence add
  forward asymmetry beyond a bare sweep? One experiment, a negative point estimate, badly
  underpowered (n≈47, roughly 1% funnel completion). **FROZEN after one experiment** — explicitly
  not run further until power improves.
- **Program 3 — Higher-Timeframe Directional Ontology.** Does moving to H1/H4 rescue the directional
  edge Program 1 killed at M15? No — zero promotions at either timeframe. **CLOSED.**
- **Program 4 / 4b — Volatility Regime and Transition.** Does contemporaneous volatility-regime
  *level*, or a forward Markov *transition* forecast, offer a consumable directional edge? Both
  informative (volatility genuinely has memory) but neither consumable — the transition-forecast
  variant (4b) turned out to be statistically redundant with plain current-volatility level, adding
  nothing beyond what was already known. **CLOSED**, both variants.
- **Program 5 — Cross-Sectional Dispersion.** The first program to leave the per-instrument frame
  entirely and ask whether relative-value/market-neutral positioning across instruments is
  monetizable. All five interpreters tested REJECT, well-powered. **KILLED.**
- **Program 6 / 6b — Carry / Basis and Carry Harvest.** Is funding-rate carry a usable signal (6),
  or — separately — is the raw cash-and-carry payoff itself harvestable net of costs (6b)? Both
  null: all eight carry/basis interpreters REJECT, and all four harvest constructions fail to clear
  their own turnover cost even before considering price drag. **Both KILLED**, with an explicit stop
  called after 6b rather than continuing to iterate on cost assumptions.
- **Program 7 — Open Interest.** Named as explicitly out of scope for Program 6 (a distinct payoff),
  but not yet run as of the evidence this chapter draws on.
- **Program 8 — Weekly Liquidity-Sweep Ontology.** A genuinely new calendar-locked geometry (weekly
  accumulation/sweep/reversal, distinct from Program 1/2's local-structural frame) tested on FX
  majors. Zero promotions across all six scopes tested. **CLOSED.**
- **Program 9 — M5-base Multi-TF Expansion Forecasting (Non-Directional Ontology).** See dedicated
  section below (Grok review pass). **Pre-registered; research authority only.**
- **A cross-asset generalization check (not itself numbered as a Program):** does Program 1's
  crypto-majors null generalize to FX majors? Yes — the same entry-information null replicated on
  five FX majors with well-powered, decisively negative toy results.

### Program 9 in depth (Grok review pass — closes the coverage gap)

Earlier book drafts only noted Program 9 from commit history. The frozen pre-registration is
authoritative: [`docs/research/preregistration-program-9.md`](../research/preregistration-program-9.md).

**Why it exists.** Program 4 (F-040) found expansion forecasting **informative but not consumable**
by a spot *directional* consumer. Its reopen clause allows only new data, a new domain, or a new
**non-directional** ontology — never parameter archaeology. Program 9 exercises two reopen keys:

1. **New data:** strict M5 corpus (Binance crypto ~2y; MT5 FX ~270d) that did not exist when F-040
   registered ("no M5 on disk").
2. **New ontology:** a both-sided stop-entry **OCO straddle** at compression-box edges (long-
   volatility payoff), which spot long/short cannot express.

**Two-stage gate (same Authority Ladder as every other program):**

| Stage | Question | Authority level |
|---|---|---|
| **Stage 1** | Does the M5∧M15∧H1∧H4 conjunction carry *incremental* information beyond the M15-base key at the same instant? (Gates A raw IG + B within-K15-cell incremental) | Level 1 — information only |
| **Stage 2** | Sole consumer `compression_box_straddle` through the unchanged M4 QualificationGate | Level 2 — economic |

Stage 2 runs **only if** Stage 1 clears. **Gate A pass + Gate B fail ⇒ `M15_REDUNDANT` = Stage-1
FAIL** (F-043's "real but already-known" lesson, renamed for this program).

**Frozen construction highlights (D1–D7):** reject-bar both-edges cancel (no invented touch order);
no fill-bar TP credit; unfilled straddles excluded from n; first-compression-bar gating only;
chronological 50/50 stability split; sole-consumer rule — no straddle-v2 archaeology inside Program 9.

**Closure rule:** Program 9 is **CLOSED** once hypotheses 9a (vol expansion), 9b (range expansion),
and 9c (compression→expansion transition) each resolve to Stage-1 FAIL (incl. `M15_REDUNDANT`) **or**
Stage-1 PASS + Stage-2 sole-consumer verdict — under the fixed thresholds. No within-program
iteration.

**Status at book time:** pre-registration is frozen and present in-repo; hypothesis registry seed
tracks H-016 as open/pre-reg. This book does **not** invent Stage-1/Stage-2 numeric results — verify
artifacts under `results/research/m5_mtf/` (if present) and `docs/current-findings.md` before
claiming a PROMOTE/REJECT. Authority remains **research/docs only** until a sealed finding says
otherwise.

**More precisely (reconciliation pass, 2026-08-07): the evidence points to a stalled run, not
merely an unresolved one.** `results/research/m5_mtf/` holds direct artifacts from exactly one
attempted Stage-1 run, launched 2026-07-04 03:05: `stage1_run1.pid` (process id `16308`),
`stage1_run1.log` (**0 bytes** — no output ever written), and `stage1_run1.err` (182 bytes, only
2 lines — a `.env` load banner and a production-config load banner, no actual error trace or
Stage-1 result). The `.pid` file's last write is 03:07 — a roughly 2-minute window before the run
went silent. No `m5_mtf_information.json` or `qualify_m5_straddle.json` exists anywhere in the
repository (the exact deterministic artifact names the pre-registration's own epistemic-integrity
clause requires for any claim — `preregistration-program-9.md:118-121`, "no claim without a
file:line citation"). The hypothesis registry (`data/hypothesis_registry.jsonl`, id `H-016`) has
never been updated since creation: `"status": "open"`, `"evidence": []`, `"findings": []`,
`"last_validated": "2026-07-03T00:00:00Z"`. Git history confirms no commit after the three that
built the pre-registration and kernel/drivers (2026-07-03) touches Program 9, `m5_mtf`, `straddle`,
or `compression_box_straddle` again.

This is **Certain**, per the repo's own confidence vocabulary — it rests on direct primary
artifacts (an empty log, an absent output file, a never-updated registry entry), not inference.
What is **not** determined from available evidence is *why* the run stopped (crashed, manually
killed, or simply an interrupted session that was never resumed) — no crash trace or session-log
note explains the cause, so this book does not guess at one. The practical implication for whoever
picks this program back up: **the Stage-1 driver needs to be re-run from scratch** (or its prior
attempt debugged first), not merely "resumed" — there is no partial output to build on.

Related implementation surfaces (orientation, not a full walk): `src/research/candle_state/`
(M5 Stage-1 kernels), `src/research/hypotheses/compression_box_straddle.py` (Stage-2 consumer),
`src/research/resample.py` (calendar OHLCV resampler shared with Program 3).

### Why this is the right outcome, not a broken pipeline

Every one of these closures follows the same discipline as
[Chapter 9](09-interpreters-pattern-contract.md)'s Interpreter Contract: pre-register the test,
apply a fixed, honest cost/exit model, require *absolute* expectancy, and accept the answer even
when it's negative. A research program that only ever produced PROMOTE verdicts on this codebase's
own history would be the actual red flag — it would mean the bar wasn't being held. Programs 1
through 8 closing null, one after another, under the same rigorous standard, is what a functioning
falsification discipline looks like from the outside.

## Classification

| Concept | Status |
|---|---|
| Programs 1, 2, 3, 4, 4b, 5, 6, 6b, 8 | Research — all **CLOSED/KILLED/FROZEN**, null or insufficient-power results |
| Program 9 (M5 multi-TF non-directional straddle) | Research — **PRE-REGISTERED, one Stage-1 run attempted and stalled** (empty log, no output, `H-016` still open); needs a fresh run, not a resume |
| Program 7 (Open Interest) | Named / out-of-scope for Program 6; not independently verified as run |
| FX cross-asset generalization of Program 1's null | Research — confirmed generalizes |

## Authoritative sources

- `docs/current-findings.md` — the Funding Ledger section, Programs 1 through 8, each with its own
  `F-0xx` findings and confidence levels — this chapter's primary source, summarized not reproduced.
- `docs/research/preregistration-program-9.md` — Program 9 frozen pre-registration (primary for P9).
- `docs/research-readiness/program-*-preregistration.md` — the pre-registration for each program
  (e.g. `program-4-nondirectional-preregistration.md`, `program-8-weekly-crt-sweep-preregistration.md`).
- `CLAUDE.md` §6.5 — the Authority Ladder this whole chapter is an application of.

## Unresolved questions

- **Program 9's stalled run** — confirmed from artifacts (empty log, absent output JSON,
  never-updated `H-016` registry entry) that one Stage-1 attempt started and produced nothing; *why*
  it stopped (crash, manual kill, or an abandoned session) is not recorded anywhere and is not
  guessed at here. Whether it should be re-run, debugged, or superseded by a fresh pre-registration
  is a research-execution decision, not a documentation one.
- Program 7 (Open Interest) is named but its current status (planned, in progress, or not started)
  wasn't independently verified this pass.

---
**Previous:** [Chapter 18 — A Field Guide to docs/governance/](18-field-guide-governance.md) · **Next:** [Chapter 20 — The Research Platform](20-research-platform.md)
**Related:** [Chapter 09 — Interpreters and the Pattern Contract](09-interpreters-pattern-contract.md) (the same discipline, one interpreter at a time) · [Chapter 16 — Config-First Doctrine](16-config-first-and-promotion.md) (the Authority Ladder)
**Memory:** none dedicated — see the research-family memory entries indexed in `MEMORY.md` under this session's project files (e.g. cross-sectional, carry-basis, carry-harvest programs).
