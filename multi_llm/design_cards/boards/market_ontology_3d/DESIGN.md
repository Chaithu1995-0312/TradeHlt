# Market ontology × 3-day real market — DESIGN FIRST

**Status:** design locked for narrative · data fetched · video pending your OK  
**Instrument:** `GC=F` (gold futures proxy for XAU stack in configs)  
**Sessions:** 2026-09-15, 2026-09-16, 2026-09-17 (ET)  
**Hard rule:** ontology **labels / observations only** — not signals, not edge, DryRun

## Design boards (image-first)

| # | Board | Purpose |
|---|---|---|
| 01 | overview | WHAT layer → time axis → event cards → fail-closed |
| 02 | day strips | T-2 / T-1 / T0 event pins |
| 03 | shot list | screenshot slots + Jarvis VO beats |
| 04 | filled timeline | binding design to last 3 sessions |

## Real data fetched

- `GC_F_5m_5d.csv`, `GC_F_1h_10d.csv`, `GC_F_1d_10d.csv`
- Charts with overlays: `chart_GC_F_2026-09-15.png` … `09-17.png`
- Event JSON: `ontology_events_last3.json`

## Timestamp highlights (observations)

### 2026-09-15 — typical ATR
- Swing low ~**09:00** ET · swing highs **14:00**, **19:00**
- Structure obs: HH after prior swing high @ **19:00** (label only)

### 2026-09-16 — elevated ATR
- Swing high **17:00** · swing low **19:00**
- Structure obs: LL after prior swing low @ **19:00** (label only)

### 2026-09-17 — compressed ATR
- Swing high **12:00** (day high region) · swings **07:00** / **10:00** / **15:00**
- Structure obs: HH after prior swing high @ **12:00** (label only)

## Ontology mapping (Tradelatest)

Source: `configs/formulas/market_ontology.yaml` — primitives → compositions → rolling → structural categories.  
Tags used in overlays: FM-040/041 ATR family, temporal session context, MarketStructure swings.  
**Not** claiming certified BOS/CHOCH engine verdicts on this pass.

## Next (video)

Jarvis VO over boards 01→04 + day charts, explaining *what the ontology would call* at those times.  
Say **make video** to generate.