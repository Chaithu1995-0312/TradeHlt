# Shape Explanations — Level 2 (LLM → human)

> **Authority: NONE.** This file is the *explanation* layer of the shape documentation hierarchy. It
> translates mathematical shape objects into human language. It is **descriptive only** and grants **no**
> authority — not entry filters, not expectancy, not production weight (§6.5). Mathematics is authoritative;
> an explanation here can never become a source of mathematical truth.

## Read order (documentation hierarchy)

```
Level 1  results/research/ic_003b/SHAPE_LIBRARY.md   what mathematically exists   AUTHORITATIVE (generated)
   │                                                  shape ids · gates · medoids · stats
   ▼
Level 2  docs/research-readiness/shape_explanations.md  what each shape means to a human   NO authority  ← this file
   │
   ▼
Level 3  configs/research/market_story_ontology.yaml  closest story family (labels)   NO authority
   │
   ▼
Level 4  results/research/ic_003b/REPORT.md            why it matters / governance   (generated)
```

A coding LLM reads **top-down**: the math (Level 1) is the source of truth; everything below interprets it
and must stay consistent with it. Never let Level 2/3 narrative flow *up* into a mathematical claim.

## Source & scope

- **Source run:** `results/research/ic_003b/` — program verdict **`IC003B_PARTIAL`** (2026-07-17).
- **Owner-note path correction:** the shapes live in **`ic_003b/`** (the sequence-geometry run), *not*
  `ic_003/` (that run is **archived LIBRARY_FAIL** and promoted **no** shapes).
- **What is explained:** the only `LIBRARY_OK` unit — **Arm S, N=4, k\*=6** (6 shapes). Every other
  unit (Arm S N=16/N=8, Arm T all N) is `LIBRARY_FAIL` and promoted no shapes.

## ⚠ Robustness caveat (read before trusting any shape below)

These 6 shapes are the *only* library that passed, and it passed **marginally and fragilely** (per this
session's independent re-derivation + 8-seed robustness sweep, recorded in
[`erp-information-class-boundary.json`](erp-information-class-boundary.json) `IC-003B.robustness`):

- **Marginal:** G2 silhouette = **0.0561** vs a 0.05 floor (clears by ~0.006).
- **Seed-fragile:** the number of shapes (k\*) is **not stable** across seeds (lands 6 only ~6/8 seeds; also
  4 or 12) — the "6 shapes" is itself seed-dependent.
- **Near-noise:** clusters capture only ~10–20% of the variance; silhouette ≈0.06 is far below any
  "real structure" bar (~0.25+). Arm C reads the manifold as a **weak continuum**, not discrete archetypes.

**Consequence for reading:** treat each shape below as a *human gloss on a marginal cluster centroid*, not
as a stable, repeatable market archetype. Every shape carries `stability: LOW`. Outcome rates are **cluster
aggregates** (mostly SL); a shape's *medoid* is one representative trade whose own win/loss says nothing
about the cluster's expectancy. No shape here is predictive or promotable.

---

## IC-003B — Arm S, N=4 (the LIBRARY_OK unit, k*=6)

> Math source: `results/research/ic_003b/SHAPE_LIBRARY.md` (Arm S N=4) + `report.json` (`arm_S["4"].shapes`).
> Medoid features below are the **real entry-bar features** of each cluster's `medoid_trade_id` from the
> XAUUSD trace corpus — not invented. `tp_oos` / `outcome_mix` are OOS cluster aggregates.

### `S_N4_k6_s00` — fade of an overbought, over-extended up-move
- **Math (grounded):** medoid `mean_reversion_010537` (SHORT). RSI **73.4** (overbought), strong up-trend
  (trend_bias +1, strength ≈2.0), price stretched **well above** its EMAs, momentum already negative.
  Cluster n_oos **457**, **tp_oos 0.468**, mix ≈ {TP 0.47 / SL 0.52 / TO 0.01}.
- **Representative trades (oos):** `mean_reversion_014045`, `mean_reversion_013232`, `mean_reversion_012911`.
- **LLM explanation** — *contributor: Claude:* A short that fades an overbought, over-extended rally —
  price stretched above the EMAs with RSI>70 and momentum rolling over. This is the **highest-tp bucket** of
  the six (~0.47 vs the ~0.32 base rate), which is *why it draws attention* — but the lift is on a marginal,
  seed-fragile, near-noise cluster, so it is a description, not an edge.
- **Research note:** Descriptive only. Not predictive. `stability: LOW`. The elevated tp_oos does **not**
  survive the robustness caveat as an entry signal (§6.5); it would need the full M4 gate + OOS + costs.

### `S_N4_k6_s01` — long breakout after a downside sweep
- **Math (grounded):** medoid `expansion_breakout_003065` (LONG). RSI **48** (neutral), mild down-bias,
  momentum **positive**, price below EMAs, entry bar shows a **sweep** (sweep=1, liquidity_sweep=−1).
  Cluster n_oos **294**, **tp_oos 0.374**, mix ≈ {TP 0.37 / SL 0.61 / TO 0.02}.
- **Representative trades (oos):** `mean_reversion_011443`, `mean_reversion_014200`, `mean_reversion_014000`.
- **LLM explanation** — *contributor: Claude:* A long that buys a momentum flip back up right after a
  liquidity grab *below*, against a mildly bearish backdrop — a "sweep-then-reclaim" long.
- **Research note:** Descriptive only. Not predictive. `stability: LOW`.

### `S_N4_k6_s02` — buy-the-dip in a quiet downtrend (the large low-signal bucket)
- **Math (grounded):** medoid `mean_reversion_004834` (LONG). RSI **34** (near-oversold), downtrend
  (bias −1, strength ≈−1.2), **low volatility** (vol_ratio 0.69), price below EMAs. Cluster n_oos **1400**,
  **tp_oos 0.308**, mix ≈ {TP 0.31 / SL 0.69}.
- **Representative trades (oos):** `mean_reversion_013003`, `mean_reversion_011945`, `mean_reversion_015342`.
- **LLM explanation** — *contributor: Claude:* Longs into a quiet, below-EMA down-move near oversold RSI —
  a large, low-distinctiveness "buy-the-dip" bucket whose tp sits essentially at the global base rate.
- **Research note:** Descriptive only. Not predictive. `stability: LOW`.

### `S_N4_k6_s03` — deep-oversold long in a strong downtrend (small)
- **Math (grounded):** medoid `mean_reversion_000140` (LONG). RSI **30.0** (oversold), **strong** downtrend
  (bias −1, strength ≈−1.6), price below EMAs. Small cluster: n_oos **123**, **tp_oos 0.366**,
  mix ≈ {TP 0.37 / SL 0.63}.
- **Representative trades (oos):** `mean_reversion_014814`, `mean_reversion_011302`, `mean_reversion_011735`.
- **LLM explanation** — *contributor: Claude:* Like `s02` but a **steeper** decline and a **smaller**
  sample — catching a strongly-falling market at RSI≈30. Small-N; read with extra caution.
- **Research note:** Descriptive only. Not predictive. `stability: LOW` (also small-N).

### `S_N4_k6_s04` — short an overbought strong uptrend, low vol (the largest bucket)
- **Math (grounded):** medoid `mean_reversion_003732` (SHORT). RSI **71.2** (overbought), **strong** uptrend
  (bias +1, strength ≈2.6), **low volatility** (vol_ratio 0.52), price well above EMAs. Largest cluster:
  n_oos **2538**, **tp_oos 0.317**, mix ≈ {TP 0.32 / SL 0.67 / TO 0.01}.
- **Representative trades (oos):** `mean_reversion_013368`, `expansion_breakout_006991`, `expansion_breakout_006052`.
- **LLM explanation** — *contributor: Claude:* Same *family* as `s00` (fade RSI>70 above the EMAs) but the
  **big, low-vol, low-distinctiveness** version — and its tp collapses to the base rate (~0.32). That `s00`
  and `s04` are the "same idea" at different tp is itself evidence the partition is weak.
- **Research note:** Descriptive only. Not predictive. `stability: LOW`.

### `S_N4_k6_s05` — short momentum-continuation in a high-vol decline
- **Math (grounded):** medoid `expansion_breakout_004750` (SHORT). RSI **31.1** (oversold but falling),
  downtrend (bias −1), **strongly negative momentum**, **elevated volatility** (vol_ratio 1.57), price below
  EMAs. Cluster n_oos **2216**, **tp_oos 0.323**, mix ≈ {TP 0.32 / SL 0.67}.
- **Representative trades (oos):** `mean_reversion_012504`, `mean_reversion_011093`, `expansion_breakout_007336`.
- **LLM explanation** — *contributor: Claude:* Shorts that press a strongly-declining, below-EMA market with
  high downside momentum and elevated vol — momentum-continuation rather than mean-reversion, despite many
  members carrying `mean_reversion` labels (the label is the *generator*, not the shape).
- **Research note:** Descriptive only. Not predictive. `stability: LOW`.

---

## IC-003B — shape → story family (Level 3)

> **Level 3 = descriptive nearest-family label** (into
> [`configs/research/market_story_ontology.yaml`](../../configs/research/market_story_ontology.yaml)). A
> label says which story family a shape is *closest to* — **not** that the shape "is" that setup. **No
> authority** (§6.5). **Proxy caveat:** shapes cluster on the *trajectory* (t-15..t+20 path summary); the
> family match here uses the **medoid's entry-bar morphology** (one facet), so treat it as an approximate
> nearest-neighbour, not a structural claim.

**Rubric (transparent, not fiat):** assign by (1) direction intent (fade / continue / reversal), (2) the
dominant observable in the medoid (sweep? RSI extreme? momentum? trend state?), matched to the family's
`description` + `key_features`. **Confidence:** HIGH = direction + ≥2 signature features + an *active*
family · MED = clear morphology but a *planned* family or a single signature feature · LOW = no
distinctive structure / ambiguous / small-N.

**Headline:** the 4 active families do **not** cleanly capture this shape set. Only **2/6** map (MED) to an
active family; **4/6** are counter-trend fades whose best match is the **planned** `trend_reversal` family
(which has no stories). A weak, planned-dominated mapping is exactly what a near-noise / under-determined
library should produce — it earns **no** authority and adds no `stability` above `LOW`.

| shape_id | closest_family | status | confidence | basis (from the medoid morphology above) |
|----------|----------------|--------|-----------|------------------------------------------|
| `S_N4_k6_s00` | `trend_reversal` | planned | MED | SHORT fade of RSI 73 overbought, price stretched above EMAs, momentum rolled over — trend-exhaustion reversal; no *active* family models a counter-trend fade |
| `S_N4_k6_s01` | `liquidity_reversal` | active | MED | LONG after a **downside sweep** (medoid `sweep_detected=1`, `liquidity_sweep=−1`) then reclaim — matches sweep→reversal |
| `S_N4_k6_s02` | `trend_reversal` | planned | LOW | LONG buy-dip near RSI 34 in a quiet downtrend; no sweep/structure — ambiguous, low-distinctiveness bucket |
| `S_N4_k6_s03` | `trend_reversal` | planned | LOW | LONG deep-oversold (RSI 30) catch in a strong downtrend; small-N |
| `S_N4_k6_s04` | `trend_reversal` | planned | LOW | SHORT fade of RSI 71 overbought (same family as s00) but low-vol, base-rate tp, largest bucket — low distinctiveness |
| `S_N4_k6_s05` | `trend_continuation` | active | MED | SHORT momentum-continuation into a strongly-declining, high-vol, below-EMA market — matches trend continuation (down) |

_Secondary families considered (not primary): `s01` also near `breakout` (sweep→expansion); `s02` also near
`range_rotation` (fade-to-mean); `s05` also near `breakout`. Primary = nearest by the rubric above._

---

## Contributor convention (multi-LLM)

Other models (GPT / Gemini / Grok) **append** their own explanation under a shape as a new
`— contributor: <model>:` bullet. **Never overwrite** another model's gloss; **keep disagreement** rather
than collapsing it into a false consensus (per the multi-LLM authority rule — advice is shared, none is
authority; Reality/Tests/Findings decide). Every added explanation must (a) cite only real fields from
Level 1 / `report.json`, and (b) keep the `no-authority` + `stability: LOW` framing.

## Maintenance

- Level 1 (`SHAPE_LIBRARY.md`) and Level 4 (`REPORT.md`) are **generated** — a re-run regenerates them; do
  **not** hand-edit. When a new run changes the shapes, add a **new run-section** here (do not silently
  rewrite the IC-003B section — append-discipline, §6.2).
- Shape ids documented here must stay ⊆ the real ids in `results/research/ic_003b/report.json` — enforced by
  `tests/research/test_shape_explanations.py`.
