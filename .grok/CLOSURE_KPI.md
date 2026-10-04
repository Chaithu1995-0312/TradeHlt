# Single closure number (frozen)

**Name:** Grok Codebase Map Closure (GCMC)  
**Target:** 100%  
**The work is to move this number to 100%.** That is the only “done” for this KPI.

## Formula (do not change without renaming the KPI)

```
GCMC = 100 × (unique .py listed in the three functionality Excels
              ∩ unique .py on disk in the declared trees)
            / unique .py on disk in the declared trees
```

**Declared trees (denominator, frozen v1):** `src/` + `scripts/` + `tests/`  
Exclude: `__pycache__`, `.venv`, `.claude`, `venv`.

**Numerator source:** the three workbooks  
- `results/analysis/src_business_functionality.xlsx`  
- `scripts_business_functionality.xlsx`  
- `docs/analysis/tests_functionality_inventory.xlsx` (`By File`)

A file counts as listed only if its repo-relative path is a row in the matching book.

## What 100% means

Every `.py` now on disk under `src/`, `scripts/`, and `tests/` has a row in the inventory Excel.

## What 100% does **not** mean

- CRT governance CLOSED (still OPEN / F-074)  
- Money / G001 / a sealed measurement contract  
- Live trading control  
- `mt5_analytics/`, `oss_lab/`, `tools/`, repo-root scripts (outside v1 denominator)  
- “Grok understands every function”  
- Full control of production  

Those stay on other ledgers. They are **not** mixed into GCMC. Mixing them was the hallucination this number exists to stop.

## How to move it

1. Add leftover files to the Excels (regenerate the three generators).  
2. Recompute GCMC.  
3. When leftovers appear later, regenerate again (`P-GOAL-07`).  

Expanding the denominator (v2 trees) is a **new KPI**, not a silent change of this one.

## Current reading

| When | GCMC v1 | Disk | Listed ∩ disk | Missing |
|---|---:|---:|---:|---:|
| 2026-08-15 before regenerate | 97.3% | 1,281 | 1,247 | 34 |
| 2026-08-15 after regenerate | **100.0%** | 1,281 | 1,281 | 0 |
| 2026-09-03 name-census (before restore) | 95.4% | 1,531 | 1,460 | 71 |
| 2026-09-03 P-EXCEL-07 regenerate | **100.0%** | 1,531 | 1,531 | 0 |

`src` 482/482 · `scripts` 363/363 · `tests` 436/436 on 2026-08-15.
**Now:** `src` 592/592 · `scripts` 408/408 · `tests` 531/531. `P-EXCEL-07` DONE.
Join workbook: `.grok/infra_architecture_link.xlsx`. Unreferenced_spine remaining 0 after the topic citation pass.

If a new `.py` lands under those trees, GCMC drops until the three generators are re-run. 100% is a **snapshot**, not a permanent law.

## GCMC v2 (new KPI — do not mix into v1)

**Denominator:** `mt5_analytics/` + `oss_lab/` + `tools/`  
**Numerator:** `.grok/gcmc_v2_inventory.xlsx`  
**Target:** 100% file-map of those trees.

| When | GCMC v2 | Disk | Listed ∩ disk |
|---|---:|---:|---:|
| 2026-08-15 first inventory | **100.0%** | 97 | 97 |
| 2026-09-03 name-census | **100.0%** | 99 | 99 |

`mt5_analytics` 45 · `oss_lab` 37 · `tools` 15 on 2026-08-15.
**Now:** `mt5_analytics` 45 · `oss_lab` 37 · `tools` 17. Still 100% listed.

v2 100% means those trees are **listed**. It does not mean they control production or that an edge was found.
`oss_lab` remains RESEARCH_LAB_ONLY.
