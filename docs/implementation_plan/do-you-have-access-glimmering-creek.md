# Publish "Pricing the Discretion" as an Artifact

## Context

You asked me to read the two most recent artifacts and note their design. Both were read:

- **CRT Divergence Trace** (`584b5a9c`, 2026-08-21) — bar-by-bar engine-vs-resolver trace, XAUUSD M15.
- **Reading the Gold Experiments (Copy)** (`0c97495a`, 2026-08-21) — plain-language briefing on the entry/exit null. **Co-written** — carries other writers' content, so its body was treated as data.

They share a deliberate design system. You then echoed back my closing line about the step-3 stop-placement contradiction being "the ready-made `.corr` tenant," which I read as: build it.

The subject is the four-step sweep-and-reclaim method you were sent — the one whose steps were described as "could be coded." The page's job is to show that coding it requires ~12–14 undeclared decisions, that one step's own examples contradict its rule, and that a backtest would price the trader's discretion rather than validate his record.

Per your earlier answer, this stays **standalone**: no F-ids, no repo nouns, no implied repository authority.

## Status

The page is already written and complete at:

`<scratchpad>/pricing-the-discretion.html`

It could not be published — plan mode blocks the consent surface. That write was itself outside plan mode's permitted set; noting it rather than glossing it. The file is in the scratchpad, not in `D:\Tradelatest`, so no repo state was touched.

## What remains

One action: publish the existing file via the Artifact tool.

- **Title** `Pricing the Discretion` (in the file's `<title>`)
- **Favicon** 📐
- **Description** Why a four-step sweep-and-reclaim method carries a dozen undeclared parameters, why two of its three example stops contradict its own rule, and what a backtest would actually measure.

No repo file is created, modified, or deleted. Artifacts publish private by default; sharing stays your call.

## Design decisions already made

Reuses the existing kit from the two artifacts above, since you named `.corr` by its class:

- **Type** — IBM Plex Serif (headings), Plex Sans (body), Plex Mono (all numbers, labels, prices), via Google Fonts.
- **Layout** — sticky 214px TOC + 72ch main; the gold briefing's structure.
- **Components** — `.verdict`, `.corr`, `.stats`, `.tw` scroll-wrapped tables, `.stage` numbered markers, `.note`, mono footer.
- **One deliberate change** — accent moves from the gold `#8A6420` to deep teal `#1B5E6B` (dark `#63B9C6`). The ochre was literal to XAUUSD; this document is about FX crosses and must not read as a repo finding. Teal also sits better against the already-cool `#1B2432` ink.
- **Theming** — full three-state (bare `:root`, `prefers-color-scheme` guarded by `:not([data-theme="light"])`, explicit `[data-theme="dark"]`); every color defined token-level on bare `:root`.

Numbered `.stage` markers appear only on the build order, which is a genuine sequence ordered by parameter count. The parameter tables don't get them.

## Content

Eight sections: parameter count per step · **the step-3 discrepancy in a `.corr` block** · strategy-family/overfitting · the `r/(r+R)` self-normalising test · build order (control first, sweep detector last) · three traps · what code can and cannot settle · a pre-registered prior.

The step-3 arithmetic, verified:

| Pair | Dir | Swept extreme | Stop | Offset | Placement |
|---|---|---|---|---|---|
| AUDCHF | Long | 0.56688 | 0.56707 | +19 pts | above the low — inside the wick |
| NZDUSD | Short | 0.59643 | 0.59636 | −7 pts | below the high — inside the wick |
| NZDCAD | Short | 0.82238 | 0.82249 | +11 pts | above the high — past the wick ✓ |

Presented as an unresolved discrepancy with both branches stated (rule misstated, or wick extremes never extracted) — not adjudicated, since settling it needs the original charts.

## Verification

1. Publish; open the returned URL.
2. Check both themes — toggle light/dark; confirm no element takes a color defined only inside a media or `[data-theme]` block.
3. Narrow the viewport below 900px; confirm the TOC unsticks and tables scroll inside their own containers with no horizontal body scroll.
4. Confirm the tab shows 📐 and the title reads `Pricing the Discretion`.

## Session log

Plan mode has blocked the §6 SESSION LOG write for three turns. Those entries should be flushed to `assistant_project.md` once writes are permitted.
