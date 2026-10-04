# VALIDATION ACCESS — VA-XAUUSD-M15 (Design Freeze)

| Field | Value |
|---|---|
| **ID** | `VA-XAUUSD-M15` |
| **Frozen** | 2026-08-06 |
| **Status** | DESIGN_FROZEN + IMPLEMENTED (access layer) |
| **Instrument / TF** | XAUUSD · M15 |
| **Parent plan** | Semantic visual / story layer (descriptive validation) |
| **Authority** | Access / packaging only — **no** runtime, fusion, sizing, or promotion authority (§6.5) |

---

## Decisions locked (user 2026-08-06)

1. **Both surfaces, separated:** human CLI ladder report **and** LLM evidence pack (never mixed into one blob).
2. **Default object:** XAUUSD M15 (matches semantic + implementation freezes).
3. **Rung order (gating, not parallel):** **S → I → F → E** (all required, in sequence).

---

## Dual surfaces

| Surface | Audience | Output |
|---|---|---|
| **A — CLI ladder** | Human | stdout status table + short `ladder_cli.md` |
| **B — Evidence pack** | LLM / archive | `results/validation_access/xauusd_m15/<run_id>/` JSON + thin `INDEX.md` |

Same `run_id`. A does not embed B’s full JSON; B does not rewrite A’s live CLI narrative.

---

## Sequential rungs

| Code | Name | Question | Tools mapped |
|---|---|---|---|
| **S** | Story six-layer semantic | Golden stories + ontology binding self-consistent? | `market_story_ontology.yaml`, `src/research/synthetic/`, story library |
| **I** | Implementation / models | Models load/execute without FAIL_OPEN on frozen XAUUSD? | `implementation_model_validation_xauusd.py`, `IMPLEMENTATION_VALIDATION_V1` freeze |
| **F** | Feature-cert / ontology | Feature surface trustworthy as evidence? | `feature_surface_query`, math ontology, cert ledger |
| **E** | Economic / measurement | Any sealed MC-* economic claim? | `MEASUREMENT_CONTRACT.md`, `configs/research/measurement_contracts/*` |

### Gate machine

```
S FAIL           → stop; I/F/E = BLOCKED_BY_S
S PASS           → run I
I FAIL_OPEN > 0  → stop; F/E = BLOCKED_BY_I
I OK             → run F   (DEGRADED/ORPHAN reported honestly, not auto-fail)
F any            → run E status always after F completes
E                → emit OPEN/sealed truth; never invent seals
```

If F is NOT_CERTIFIED / PARTIAL, E still runs as **status-only** (no seal authority).

---

## Non-goals

- No new scoring engine; no Zone-X geometry reopen; no semantic → runtime promotion.
- No profitability claim from green S/I/F.
- No mixing full OHLC dumps into the pack (pointers + hashes only).
- Default I mode = **reuse freeze artifact** (`--live-impl` for full re-harness).

---

## Entry points

```text
PYTHONPATH=src python scripts/governance/validation_access_cli.py
PYTHONPATH=src python scripts/governance/validation_access_cli.py --live-story
PYTHONPATH=src python scripts/governance/validation_access_cli.py --live-impl   # slow
```

Importable: `from validation_access.ladder import run_ladder`

---

## Package layout

| Path | Role |
|---|---|
| `src/validation_access/ladder.py` | S→I→F→E orchestration |
| `src/validation_access/surfaces.py` | Surface A (CLI text) + Surface B (pack) |
| `scripts/governance/validation_access_cli.py` | Thin CLI wrapper |
| `tests/test_validation_access.py` | Floors |

---

## Reopen

Reopen only if: instrument/TF default changes; gate order changes; authority of a rung changes; or dual-surface separation is violated by a proposed merge.
