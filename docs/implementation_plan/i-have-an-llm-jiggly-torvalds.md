# Trade-Mining System Prompt for the CRT Episode Trace

## Context

The user has an external LLM (a separate chat surface, not Claude Code) that can be handed the
files in `results/crt_episode_trace/20260813T124158Z/` as attachments. They want a **system
prompt** to paste into that LLM so it performs "trade mining" over those sources.

The problem this solves: that folder is ~1.3 MB across 12 files, four of which are 260–314 KB
per-bar walkthroughs with heavily repeated 39-feature ledgers. Dropped into an LLM cold, the
model will linearly chew the biggest files, blow its context on repeated feature tables, and
produce vague narration. It also has no way to know what A0/A3 mean, that the two arms are
confounded, or which numbers are engine-emitted vs recomputed. The system prompt has to carry
that map.

**User decisions (from clarification):** all four analysis jobs in scope (diagnose the no-trade
chain, mine setup patterns, audit the trace, explain the mechanism in plain language);
**no governance rails** (no E-001 / Authority Ladder / evidence-class jargon, no repo governance
vocabulary); **markdown report only** (no §3 handoff block, no JSON).

> One flag, then proceeding as specified: with no rails, this prompt's output is not safe to
> paste back into findings/docs unvetted — an LLM handed 47 bars will readily produce
> confident-sounding edge claims from n=2. The prompt keeps a single plain-analyst line ("every
> number you cite must appear in one of the attached files") because a prompt without it yields
> unusable output, but that is hygiene, not governance framing. Vetting the output stays manual.

## Deliverable

One new file: `multi_llm/research_lane/prompts/TRADE_MINING_SYSTEM_PROMPT.md`

Chosen over `ChatGpt  workflow/Agents Prompts/` (that dir holds only `.docx` role cards, and its
literal name has a double space that breaks paths). `multi_llm/research_lane/prompts/` already
holds exactly this kind of artifact — a hand-carried prompt template — see the existing
[PLAN_DESIGN_PROMPT.md](multi_llm/research_lane/prompts/PLAN_DESIGN_PROMPT.md), whose format
(H1 title → blockquote provenance line → `---`-separated sections → tables for structure) this
file matches.

The prompt is written **generic over any `results/crt_episode_trace/<RUN_ID>/` folder**, with the
`20260813T124158Z` run's values as the worked example, so it stays reusable when the trace is
regenerated.

## Structure of the prompt file

| Section | Content |
|---|---|
| Role | Analyst reading a read-only forensic trace of one trading engine's decisions. States that the engine is not modifiable from this seat and nothing here is a live order. |
| What you were given | The 12-file map + **reading order** (see below). This is the highest-value section. |
| How to read the domain | CRT state machine vocabulary, the gate chain, the two arms, the SL formula. |
| Four jobs | The four analyses, each with its own output contract. |
| Traps in this data | Six concrete gotchas that will otherwise produce wrong conclusions. |
| Output format | A fixed markdown skeleton. |

## Content the prompt must encode

### Reading order (routing — prevents context burn)

1. `journeys.md` (6.5 KB) — the whole story; read first, completely.
2. `proof_*.md` (1–2 KB × 4) — the SL arithmetic with engine-parity check.
3. `operands.csv` (2.5 KB) — every SL input with its source.
4. `bars.csv` (23 KB, 47 rows, 74 cols) — the tabular spine; use this for anything comparative.
5. `episodes.json` (95 KB) — machine mirror of the above; use only to resolve a disagreement.
6. `episode_*_{A0,A3}.md` (260–314 KB × 4) — **sample, never read linearly.** Per-bar sections
   are `## BAR nn <ts> [state_before → state_after] action=X`; the 39-feature ledgers appear only
   on decision bars, inside `<details>` blocks. Jump to `## BAR` headers with `***DECISION BAR***`
   and to the tail sections `### SL operands` / `### Execution geometry` / `### Engine-parity proof`.

### Domain facts

- **Instrument/scope:** XAUUSD M15, broker-local timestamps, source
  `data\XAUUSD_M15_20260807_203705.xlsx` (sha256 `74f04a43…`), `active_version v2_multi_2026_04`,
  feature schema v4.0 (39 canonical features).
- **Two episodes only:** `2026-07-22 19:15:00 SHORT`, `2026-07-28 05:45:00 LONG`. Bars 60–73
  rendered per episode.
- **CRT sequence:** `RANGE → SWEEP → DISPLACEMENT → (EXPANSION) → RETEST → EXECUTION`. The trace
  starts at the SWEEP that opened each episode.
- **Gate chain** (this is the diagnostic backbone):
  `RETEST_CONFIRMED → soft-conf score → shadow age-decay → zone → SESSION → shadow advisory → build_trade → SL guard`.
- **Arms:** `A0` = production config as-is; terminal `FILTER_REJECTED` at SESSION
  (`off_session:OFF_SESSION`) — so `build_trade` is never reached and the SL geometry is
  invisible. `A3` = `session_windows` overridden open; reaches `build_trade`, terminal
  `TRADE_BUILD_FAILED` at the SL guard. Both arms, both episodes, zero trades.
- **SL geometry:** SHORT `sl = disp_high + sl_atr_buffer*atr`; LONG `sl = disp_low − sl_atr_buffer*atr`;
  `sl_atr_buffer = 0.2`; `atr = state.atr_abs` **on the soft-confirmation bar, not the RETEST bar**.
  Guard: SHORT needs `sl > entry`, LONG needs `sl < entry`; failure → `build_trade` returns None,
  TP1/TP2/risk_dist never computed.
- **The two numeric outcomes** (so the model can check its own arithmetic):
  - 07-22 SHORT: entry 4154.55, disp_high 4146.75, atr 9.562143 → sl 4148.6624 — below entry, guard FALSE.
  - 07-28 LONG: entry 4044.31, disp_low 4046.38, atr 6.571429 → sl 4045.0657 — above entry, guard FALSE.
  - Shape in both: the retest close sits *past* the displacement extreme, so the protective buffer
    lands on the wrong side. Give this to the model as the observation, and make finding *why the
    retest closes there* one of the mining targets.

### Traps to name explicitly

1. **The arms are confounded.** A3's `session_windows` override also feeds the risk engine's
   time score, so A3 raises `final_S` too (0.4957→0.5980 on 07-22; 0.4670→0.5628 on 07-28). A3 is
   not "A0 with only the session gate opened." Any A0-vs-A3 delta attributed purely to session is wrong.
2. **A session *rejection* is emitted; a session *pass* is not.** In A3 the pass is known only
   because `build_trade` was subsequently called. Don't read the two as equally observed.
3. **Two different ATRs exist per episode** — on the RETEST bar and on the soft-conf bar. Only the
   soft-conf one reproduces the engine's SL. `operands.csv` labels both.
4. **`momentum_score` and `ema_spread` are price-scaled, not normalized ratios** — values in the
   thousands are expected in this dump. Do not interpret them as z-scores or read magnitude as strength.
5. **Warmup holes are real data**, e.g. `trend_strength = NOT_YET_AVAILABLE (needs 79 bars, have 62)`.
   Not a bug to report, and not a value to impute.
6. **`session` feature = 2 while the engine reports `OFF_SESSION`, and `active_range.session = UNKNOWN`.**
   Flag as an audit target rather than silently picking one.
7. **n = 2 episodes.** The pattern-mining job produces *candidate* signatures and the test that
   would confirm them — never a rate, hit-rate, or edge estimate.

### The four jobs, with output contracts

- **J1 — No-trade chain.** For each episode×arm: the ordered gate list, which gate bound, the
  operands that made it bind, and what would have to be true numerically for it not to bind.
  Then: rank gates by how many of the 4 episode×arm cells they kill.
- **J2 — Setup signatures.** From `bars.csv`, the per-bar feature/state values at SWEEP,
  DISPLACEMENT and RETEST for both episodes; note what the two share and where they diverge;
  emit each as a named candidate signature with the measurement that would test it on a full corpus.
- **J3 — Trace audit.** Recheck every arithmetic line in the `proof_*.md` files; check the parity
  deltas; check that each claim in `journeys.md` is supported by a value in `operands.csv` /
  `bars.csv`; list anything asserted more strongly than its source supports.
- **J4 — Plain-language mechanism.** Bar-by-bar narration of both episodes: what price did, what
  the state machine saw, why it moved state, why it ended without a trade. No hypotheses, no jargon
  the report hasn't defined.

### Output skeleton the prompt fixes

```
# Trade Mining — <RUN_ID>
## 1. What this run contains        (instrument, window, episodes, arms, terminal outcomes)
## 2. Why no trade                  (J1 — gate table + binding-gate ranking)
## 3. Setup signatures               (J2 — candidate table + the test for each)
## 4. Trace audit                    (J3 — arithmetic recheck + overstated claims)
## 5. The story, bar by bar          (J4 — one subsection per episode)
## 6. What I could not determine     (explicit; anything the files don't answer)
```

Plus one standing instruction: every number cited must appear in one of the attached files, with
the filename beside it; if a value isn't there, write what's missing instead of estimating.

## Verification

1. Read the written file end to end — it must be self-contained (an LLM with only these
   attachments and this prompt needs no repo access).
2. Cross-check every embedded fact against source:
   `results/crt_episode_trace/20260813T124158Z/journeys.md`, `operands.csv`, `proof_*.md`,
   `episodes.json` (header block), and `bars.csv` (header row).
3. Confirm no governance vocabulary leaked in (no F-ids, FM-ids, "Authority Ladder", "E-001",
   OBSERVED/DERIVED/INFERRED_BY_ORDER as *taxonomy* — the words may appear only where quoting
   what the files literally contain).
4. Confirm generality: the prompt reads correctly if `<RUN_ID>` is a different trace folder.
5. Live test (user-run): paste as system prompt, attach the 12 files, send "mine this run" —
   the report should follow the 6-section skeleton and should not claim a win rate or edge.
