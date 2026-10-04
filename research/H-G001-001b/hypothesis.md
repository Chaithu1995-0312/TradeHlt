# H-G001-001b — Liquidity Sweep Veto on XAUUSD (CRT-only lens)

**Parent:** H-G001-001 (fusion gate ON → REJECT_INSUFFICIENT, n=1)  
**Program:** G001 economic research  
**Status:** MEASURE-ONLY · NON-PROMOTABLE  
**Date opened:** 2026-07-26

## Why a new H-id

H-G001-001 measured the veto under **fusion gate ON** and found n=1 spine entries.
Per research discipline, changing the validation lens is a **new experiment**, not a
silent redefinition of 001.

## Question (only one)

> Does a liquidity-sweep veto improve M4 performance of the **CRT-only** production spine
> on the canonical XAUUSD corpus?

## Fixed components

Same as H-G001-001 **except**:

| Component | Value |
|---|---|
| `BACKTEST_ENGINE_GATE` | **0** (CRT-only; F-037 research spine) |
| All other knobs | Unchanged from 001 |

## Treatment

Identical to 001: discard spine entries where `liquidity_sweep != 0` on the entry bar (FM-058).

## Decision rule

Unchanged: positive useful ΔG001 → QUALIFY_CANDIDATE (research only); else REJECT*; no ontology/FM/production edits.

## Relationship to 001

| ID | Lens | Prior result |
|---|---|---|
| H-G001-001 | fusion ON | REJECT_INSUFFICIENT (n=1) |
| H-G001-001b | CRT-only OFF | this run |
