# BG-005 Population Equivalence Analysis

**Status:** OBSERVATION ONLY · READ-ONLY · NO AUTHORITY · NO PROMOTION  
**Date:** 2026-09-09  
**Commit:** `7864ed9`  
**Question:** do the MeasurementContract's embedded `population` block and the L-003 `Omega` Population Registry describe the same sets? They share a word; BG-001 §7 disclaimed knowing whether they share a referent.

---

## 1. Scope

| Path | Read |
|---|---|
| `configs/research/measurement_contracts/` | 15 MC-* `population` blocks |
| `docs/governance/population_registry.json` | 3 Omega populations |
| `docs/governance/measurement_contract.schema.json` | frozen `population` field definitions (read, never written) |
| `docs/research/reports/schemas/population.schema.json` | Omega field definitions |
| `results/research/*_trade_anatomy/trade_dataset_*.csv` | 4 files, M2 recomputation only |

MP-* profiles are excluded: BG-001 established they carry no `population` block at all (a shape difference, not a gap).

## 2. Method

Pure read; one file written (this report). Two measurements deliberately kept apart because they answer different questions:

- **M1 — dimensional commensurability.** Field-by-field comparison of the two vocabularies, each dimension classified `SHARED` / `ONE_SIDED` / `TYPE_MISMATCH` / `DISJOINT_VALUES`. This asks whether the two can be compared *at all*.
- **M2 — Omega internal reproducibility.** Each Omega `n_observed` recomputed from its **own** declared `membership_rule` against the on-disk anatomy CSVs. This is an **integrity check of Omega alone** — it is *not* equivalence evidence and must not be read as such.

`Y_scanner` and `Y_oracle` are projected via columns `art_outcome` and `outcome` respectively, per `MEASUREMENT_OBJECT_REGISTRY.md` (`related_columns`). The columns are projections of the MeasurementObjects, not the objects themselves.

## 3. M1 — Dimensional commensurability

| Dimension | Contract `population` | Omega registry | Class | Note |
|---|---|---|---|---|
| identity | no `population_id` field (9 required fields, none is an id) | `population_id` (required, e.g. `Omega_bnb_anatomy`) | **ONE_SIDED** | There is nothing on the contract side to reference *with*, independent of whether a target exists. |
| instruments | ['XAUUSD'] | ['BNBUSDT', 'BTCUSDT', 'ETHUSDT', 'SOLUSDT'] | **DISJOINT_VALUES** | Intersection = EMPTY SET. No contract and no Omega population share a single instrument. |
| timeframe | required, all `M15` | field absent from the schema entirely | **ONE_SIDED** | Omega sets carry no timeframe; the anatomy row is the unit, and its bar timeframe is not declared at the population level. |
| unit vocabulary | closed enum, 6 members: ['candle', 'signal_event', 'trade_decision', 'settlement_event', 'panel_row', 'rebalance'] | free prose (e.g. "anatomy trade_dataset opportunity row (one scanner/oracle dual-path opportunity)") | **TYPE_MISMATCH** | A closed enum and open prose cannot be compared without an invented mapping. Omega's unit has no unambiguous image in the enum -- `signal_event` and `trade_decision` are both defensible and choosing one would be invention (CLAUDE.md 6.6). Left UNDECIDED. |
| unit values in use | {'signal_event': 4, 'candle': 5, 'trade_decision': 6} | 3 distinct prose strings, one per population | **TYPE_MISMATCH** | Contracts already spread across 3 enum members; Omega prose does not partition the same way. |
| membership definition | `inclusion_rule` + `exclusion_rule` (2 prose fields; exclusions are explicit and load-bearing) | `membership_rule` (1 prose field; no exclusion field) | **TYPE_MISMATCH** | Different arity. Contract exclusions carry real content (e.g. MC-VCRT-V2 excludes a named 2,116-bar audit corpus by sha256); Omega has nowhere to put an exclusion. |
| substrate | `data/mt5/XAUUSD_M15.csv` (47,275 bars), sha256 pinned INLINE in the rule | `results/research/{inst}_trade_anatomy/trade_dataset_{INST}.csv`, SHA pins live in a DIFFERENT file (L-003G JSON, per registry notes) | **DISJOINT_VALUES** | Different files, different derivation depth: raw MT5 OHLCV vs a derived analytics join. Both trees are gitignored (`/data/*`, `/results/*`), so neither is git-reachable; they differ in whether the pin travels with the definition. |
| n semantics | `n_declared_min` = [0, 30] -- a pre-registered FLOOR | `n_observed` = [559768, 139942, 176471] -- MEASURED COUNTS | **TYPE_MISMATCH** | Different kinds of quantity. The contract value is a constant threshold carrying no information about set size; comparing the two numerically would be a category error. |
| hierarchy | absent -- populations are flat and independent per contract | `parent_population` (2 of 3 declare a parent) | **ONE_SIDED** | Omega models subset relationships; the contract block cannot express one. |
| lifecycle status | absent at population level (the CONTRACT has status, the population does not) | `status` = ['REGISTERED_STUB'] | **ONE_SIDED** | All 3 Omega entries are REGISTERED_STUB -- not fully registered. |
| detection_vs_trade | required closed enum, values in use ['detection_stream', 'hybrid_explicit', 'not_applicable', 'trade_ledger'] | field absent | **ONE_SIDED** | The detection-stream vs trade-ledger distinction (F-022's lesson) has no Omega counterpart. |
| population_hash_inputs | required list (6-15 entries) naming what the population hash is taken over | field absent | **ONE_SIDED** | Contracts declare a reproducible population identity input set; Omega does not. |

**Tally:** 0 SHARED · 6 ONE_SIDED · 4 TYPE_MISMATCH · 2 DISJOINT_VALUES, over 12 dimensions.

**Zero dimensions are SHARED.** Instrument intersection is `EMPTY`: contracts cover ['XAUUSD'], Omega covers ['BNBUSDT', 'BTCUSDT', 'ETHUSDT', 'SOLUSDT'].

## 4. M2 — Omega internal reproducibility

| Population | Declared `n_observed` | Recomputed | Match | Basis |
|---|---|---|---|---|
| `Omega_anatomy_opportunity` | 559,768 | 559,768 | **yes** | rows across the 4 instrument anatomy CSVs |
| `Omega_bnb_anatomy` | 139,942 | 139,942 | **yes** | BNBUSDT anatomy CSV rows |
| `STATE_SL_TP_anatomy` | 176,471 | 176,471 | **yes** | rows where (art_outcome, outcome) == (SL_HIT, TP_HIT) |

Per-instrument row counts: `BNBUSDT` 139,942, `BTCUSDT` 139,942, `ETHUSDT` 139,942, `SOLUSDT` 139,942.

All declared counts reproduce exactly from the registry's own membership rules.

Joint-state distribution actually observed across the 4 anatomy corpora (`(art_outcome, outcome)` pairs, top 9):

| Y_scanner | Y_oracle | count |
|---|---|---|
| `SL_HIT` | `SL_HIT` | 367,923 |
| `SL_HIT` | `TP_HIT` | 176,471 |
| `TP_HIT` | `TP_HIT` | 7,634 |
| `SL_HIT` | `TIMEOUT` | 7,312 |
| `TP_HIT` | `SL_HIT` | 280 |
| `TIMEOUT` | `TIMEOUT` | 148 |

## 5. Verdict

**Classification: DISJOINT POPULATIONS OVER INCOMMENSURABLE VOCABULARIES.**

Two independent reasons, either sufficient on its own:

1. **Extensional.** The instrument sets are disjoint — contracts are entirely XAUUSD, Omega entirely crypto. No contract population and no Omega population can denote the same set of units today, whatever the vocabularies say.
2. **Intensional.** Even setting instruments aside, 0 of 12 dimensions are SHARED. The two describe sets over different substrates (raw MT5 OHLCV vs a derived analytics join), with different unit type systems (closed enum vs free prose), different membership arity (inclusion+exclusion vs membership), and `n` fields that are different *kinds* of quantity (a pre-registered floor vs a measured count).

The shared word "population" is a **homonym** — the same relationship L-003M established for `SL_HIT` under `Y_scanner` versus `Y_oracle`: a shared token whose equality does not imply a shared referent.

Consequence for BG-003's declared-only `MeasurementContract -> Population Registry` link: a reference from a contract would have **no valid target** in the registry as it stands, and the contract has no id field to carry the reference. That is a measurement, not a recommendation.

## 6. Non-claims

This analysis does **not** determine:

- whether the two vocabularies *ought* to be reconciled, or how;
- whether either definition is correct, well-formed, or fit for its purpose;
- whether an Omega population could be defined for XAUUSD, or a contract for crypto — only that neither exists today;
- the right enum member for Omega's `unit` prose: `signal_event` and `trade_decision` are both defensible and no mapping was invented (§6.6);
- anything economic, or anything about `src/`, production config, or the live path.

M2 is an integrity check of Omega against its own declared rules. It is **not** evidence of equivalence with any contract, and a passing M2 says nothing about M1.

No registry entry was added, edited, promoted, or lifted off `REGISTERED_STUB`. No contract was modified. No frozen schema was touched. Grants no authority (§6.5).

## 7. Recommended next observations

Observation proposals only; no architectural change is proposed.

1. **Omega coverage of the XAUUSD corpus.** Measure whether any *derived* artifact over `data/mt5/XAUUSD_M15.csv` would satisfy an Omega-shaped membership rule. This decides whether the disjointness is incidental (nobody built one) or structural (the anatomy join does not exist for metals).
2. **Contract-to-contract population overlap.** Several XAUUSD contracts explicitly declare each other's populations as *different* (MC-CTXATTR names SEM-012 / SEM-026 / SEM-031 as separate). Measuring their pairwise overlap on the shared corpus would test whether that prose distinction is borne out by the units each actually selects.
3. **Re-run M2 when the anatomy corpora change.** Both trees are gitignored, so these counts are reproducible only on a machine holding the same derived artifacts.

---

_Read-only. Contracts examined: 15. Omega populations: 3. Anatomy rows scanned: 559,768. No file other than this report was written._
