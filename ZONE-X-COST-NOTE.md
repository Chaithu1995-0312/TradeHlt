# ZONE-X COST NOTE (O-1) — MEASURED via live MT5 demo

**Date:** 2026-08-06  
**Status:** `c_per_side` **MEASURED** (after seeding XAUUSD fills on installed demo terminal)  
**Programme decision:** see **`ZONE-X-DECISION-2026-08-06.md`** — design default **`c=0.055`**, empirical baseline **`c=0.0238`**, path **(a) Stop**  
**Authority:** RESEARCH_ONLY — does not amend `ZONE-X-SPEC-v0.8.md`  
**Artifacts:** `results/research/xauusd_mt5_cost_calibration/`  
**Manifest:** `xauusd_mt5_cost_calibration_manifest_20260806T084013Z.json`  
**Spec citation:** v0.8 §3.2 / §8.1; design `ZONE-X-DESIGN-CONTINUATION-v0.9.md` §4  

---

## 1. How the terminal was used

| Step | Tool | What |
|---|---|---|
| Connect | `MetaTrader5` + `MT5Adapter` | ICMarketsSC-Demo (Raw Trading Ltd), DEMO |
| Seed market fills | `manual_tools/trade_generator.py` | 4× XAUUSD 0.01-lot open/close (commission) |
| Seed STOP fills | `scripts/research/xauusd_mt5_cost_seed_stops.py` | near-market BUY/SELL STOP ladder; 7 stop fills |
| Measure | `scripts/research/xauusd_mt5_cost_calibration.py` | ticks + history → `c_per_side` |

Fingerprint pin (demo only): `e483bcffd1b66747cf7573623d0814950610a34131a311503b443f208ce7438c`

**Sign fix applied same session:** MT5 `deal.commission` is a signed debit (negative).  
`compute_c_per_side` now uses `abs(commission)` so cost is not understated.

---

## 2. Status table

| Quantity | Status | Value |
|---|---|---|
| Spread median (full $/oz) | **MEASURED** | **0.0900** |
| Half-spread ($/oz/side) | derived | **0.0450** |
| Commission ($/oz/side) | **MEASURED** | **0.0400** ($4.00/lot/side ÷ 100 oz) |
| Stop-order slippage median | **MEASURED** (n=7) | **0.0900** |
| Stop slip p90 | MEASURED | 0.3200 |
| Swap long / short ($/oz/night) | MEASURED | −0.5601 / +0.3834 (not in event `c`) |
| **`c_per_side`** | **MEASURED** | **$0.1750 / oz / side** |

```
c = half_spread + |commission| + stop_slip_median
  = 0.045 + 0.040 + 0.090
  = 0.175 USD/oz/side
```

---

## 3. ATR conversion (v0.8 §3.2 constants)

| Basis | `c` ATR/side |
|---|---|
| Median ATR $7.342 | **0.0238** |
| p10 ATR $3.467 | 0.0505 |
| p90 ATR $15.489 | 0.0113 |

| Reference | ATR/side | vs measured 0.0238 |
|---|---|---|
| v0.8 assumed | **0.0700** | measured **~2.9× lower** |
| v0.8 optimistic alt | 0.0300 | measured still lower |
| Metals protocol $0.20/side | 0.0272 | close (measured slightly cheaper) |

---

## 4. Directional gate impact (v0.8 §8.1 arithmetic)

With `k=1.5`, `m=1.0`, generation long base **0.4071**:

```
p* = (m + c) / (k + m) = (1 + 0.0238) / 2.5 = 0.4095
gap_long = p* − 0.4071 = +0.0024  (~0.24 pp)
```

Compare to assumed c=0.07 → gap **+2.09 pp**.  
**Toll collapsed ~9×.** Path table in design §6: `c ≤ 0.03` → **(b) allowed** (declared priors).

Caveats (honest):

1. **Stop sample n=7** near-market demo stops — likely **understates** true gap-driven barrier slip (ZONE-X m=1.0 ATR stops on 29% gapping bars). p90 slip already **$0.32**.
2. **Conservative recompute** using stop p90:  
   `c_hi = 0.045 + 0.040 + 0.32 = 0.405 USD` → **0.055 ATR** → still below v0.8 0.07; path table → **(a) preferred / (b) exceptional** if you adopt p90.
3. Demo fills ≠ live book depth; commission form matched IC Raw case_c_folded and is the strongest of the three terms.

**Adopted (2026-08-06) — see `ZONE-X-DECISION-2026-08-06.md`:**  
- **Design default:** `c = 0.055 ATR/side` (p90 stop stress; thin sample)  
- **Empirical baseline:** `c = 0.0238 ATR/side` (report / benchmark)  
- **Optional legacy:** `c = 0.070 ATR/side` (v0.8 reference in sensitivity only)  
- **Path: (a) Stop**

---

## 5. Path decision — RECORDED 2026-08-06

| Role | `c` ATR/side | Use |
|---|---|---|
| **Design default (D-C1)** | **0.055** | Research / design until live stop sample is large across regimes |
| **Empirical baseline (D-C2)** | **0.0238** | Reporting and benchmarking only |
| Optional legacy (D-C3) | 0.070 | Sensitivity vs v0.8 literature |

| Path | Choice |
|---|---|
| **(a) Stop** | **Chosen** — no further ZONE-X geometry search on XAUUSD M15; §6 null stands |

Sensitivity + ontology stability rule: decision D-S1 / D-S2.

---

## 6. What remains open

| Item | Status |
|---|---|
| O-1 triple (spread, commission, stop slip) | **Done at MEASURED** (demo) |
| Path a/b/c | **Closed: (a)** |
| Live stop sample across vol regimes | **Open** — may revise D-C1; does not auto-reopen search |
| O-4 gap study | **Done** — `results/research/zone_x_o4_gap_study/` (avg m penalty ~0; rare gap-through) |
| O-3 / O-5 | still deferred |

---

## 7. Reproduce

```text
# market commission seed (DEMO)
python manual_tools/trade_generator.py --symbol XAUUSD --lot 0.01 --count 4 --patterns normal \
  --confirm --account-hash <fp> --require-margin hedging

# stop slip seed (DEMO)
python scripts/research/xauusd_mt5_cost_seed_stops.py --confirm --account-hash <fp> \
  --require-margin hedging --pairs 4 --wait-seconds 120

# measure
python scripts/research/xauusd_mt5_cost_calibration.py --symbol XAUUSD --tick-days 1 --history-days 90
```
