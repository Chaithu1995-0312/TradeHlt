# Plan: Formalize manual CRT analysis checklist as a docs/topics/ entry

## Context
Following the CRTClaude.pdf note-taking pass (see below), the user wants the repeatable input
template (reference timeframe / entry timeframe / pre-marked key levels) and the probability/
quality scorecard that emerged ad hoc in that chat **formalized into a standing checklist**, and
linked to Tradelatest's actual "ins/outs" rather than living as a one-off chat artifact.

Explore agent findings: there is **no existing discretionary/manual-chart-analysis concept** in
the repo.
- `src/inout/` is pure market-data plumbing (candle fetchers: Hummingbot, AlphaVantage, MT5,
  perp-funding) — not a manual-input layer.
- `manual_tools/trade_generator.py` is a DEMO-only MT5 *test-trade fixture generator* for broker-
  semantics validation — unrelated to discretionary chart reading.
- `docs/topics/` (the concept↔code↔tests index, [readme.md](docs/topics/readme.md)) has 26 topics
  covering the **automated** spine (CRT engine → Fusion → Decision → ExecutionPlanner →
  UltronRiskGate) but nothing for a human discretionary workflow.

So per CLAUDE.md §6.2 rule 1 (existing-doc-first) there is genuinely no doc that owns this topic —
a new one is the correct (not the lazy) choice, structured per the `_template.md` pattern so it's
governed the same way every other topic is (Topic Sync Mandate, §6.4).

The "link with Tradelatest in and outs" instruction is interpreted as: cross-reference the doc to
the real automated **Ins/Outs** of the spine (per `_template.md`'s own "Ins / Outs" section) so the
manual SOP explicitly states where it *feeds* the automated system (or explicitly that it
currently doesn't) — not as literal code under `src/inout/`.

## What will be created
**New file:** `docs/topics/manual-crt-checklist.md`, filled from `_template.md`'s skeleton:

- **In plain language:** discretionary CRT (romeoopt model) chart-reading SOP — human applies it
  manually in TradingView; not executed by any Tradelatest engine. Exists to make repeatable what
  was previously re-derived turn-by-turn in chat.
- **Code covered:** none (by design) — note explicitly: *"no Tradelatest module implements this;
  it is a human-side companion to the automated CRT spine, not a code path."* Cross-link
  `docs/topics/crt-spine.md` only as the conceptual cousin (range/AMD ideas the automated
  `crt_engine_v2.py` formalizes differently), not as a shared implementation.
- **Ins / Outs** (the actual checklist):
  - **Ins (inputs the user must supply each time):**
    1. Reference CRT timeframe (Monthly/Weekly/Daily/4H) — which candle defines CRT High/Low.
    2. Entry/execution timeframe (1H/15m) — where the LTF confirmation (CSD) is sought.
    3. Pre-marked key levels already on the chart (PMH/PML, PWH/PWL, rejection/order
       blocks, FVGs) — Claude must not invent these from a raw screenshot.
  - **Outs (what the checklist produces):**
    1. CRT High / CRT Low for each timeframe in the top-down stack.
    2. Purge status per level: not-yet-purged / wick-only / closed-back-inside (Turtle Soup
       confirmed).
    3. Directional bias + target level.
    4. **Probability/quality scorecard** (the BTCUSD rubric, generalized):
       - Setup Quality score (/10): + inside bars within CRT, + CSD confirmation present, +
         clean single-wick purge, + timeframe coupling honored (HTF key levels referenced).
       - Probability band (e.g. 65-70%) with explicit **factors-for** / **factors-against** table.
       - Invalidation condition (level that kills the setup) + confirmation triggers (levels that
         must be reclaimed) — always stated, never omitted.
- **Entry points & validations:** "Reached via: manual chat/session walkthrough with Claude, not a
  CLI or control-plane route." "Validated by: none (discretionary, no backtest/replay gate) — this
  is explicitly **outside** the §6.5 Authority Ladder; it earns no production authority no matter
  how good a scorecard looks."
- **Tests:** none — explicitly state why (manual/discretionary, not governed code).
- **Fits in architecture:** one link to `docs/architecture/signal-flow.md` noting this sits
  *outside* the spine entirely — a human pre-trade research aid, parallel to but not feeding the
  automated candle→order path.
- **Discussion:** seed with one dated entry noting the origin (CRTClaude.pdf chat, 2026-06-26) and
  the open question: *should this ever become a real `Interpreter` (per
  `docs/topics/interpreter-contract.md`) so it's measurable against G001?* — flag as a future
  option, not a commitment (Authority Ladder: information ≠ authority).

**Edit:** `docs/topics/readme.md` — add one row to the Topic index table:
`| Manual CRT checklist (discretionary) | manual/research | _none (human SOP)_ | manual chat
session | _none_ | stub | [manual-crt-checklist.md](manual-crt-checklist.md) |`

## Why "stub" status, not "living"
Per the status legend, `stub` = row only / doc exists but isn't tied to maintained code. This is
honest: there's no code to drift against yet. If/when this becomes an `Interpreter` per the
Interpreter Contract layer, promote to `living` then.

## Verification
Doc-only change — no tests to run. Sanity check: confirm the new file follows `_template.md`'s
section headers exactly (so `Sync`/`Audit` tooling that scans `docs/topics/*.md` doesn't choke),
and confirm the new readme.md row matches the existing table's column count/order.
