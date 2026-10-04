# Phase 6e — `shadow_advisory_only` A/B (BNBUSDT M15, 2026-06-01)

> Point-in-time analysis (NOT a living doc). Measure-only governance re-validation.
> Driver: `scripts/research/phase6e_shadow_ab.py` · Raw: `results/phase6e_shadow_ab/phase6e_ab.json`
> Config: `v2_multi_2026_04 - deepdeektry` · V3 session-expanded (`LONDON,NEWYORK,OVERLAP,ASIA,OFF_SESSION`).

## Question

Phase 6d/6e forensics proved 100% of the 70 "lost" retests in the V3 session-expanded run are blocked
by a single flag: `crt_engine.shadow_advisory_only=True` (the Phase 4b policy). The Phase 4b verdict
was made on a **BNBUSDT-only, n=22-shadow, pre-session, PF-blind, globally-applied** basis, and Phase 4b
itself conditioned revisiting on "N≫22" — now satisfied. **Does the verdict still hold after the
session-expansion regime change?** Single-knob A/B, gated on PF.

## Result

| arm | shadow_advisory_only | trades | PF | WR | avg RR | max DD% | total ret% | funnel exec |
|---|---|---|---|---|---|---|---|---|
| **control** | True (current) | **35** | **2.5351** | 65.7% | +0.545 | 3.1% | +20.6% | 35 |
| **treatment** | False | **89** | **1.5249** | 56.2% | +0.248 | 8.2% | +23.7% | 105 |

- **Control gate PASS** — reproduces the published V3 exactly (35 trades / PF 2.5351), so the harness is trusted.
- **Throughput recovered as predicted:** funnel EXECUTION 35 → 105 (≈ the +70 shadow ceiling); 89 fully-closed trades.

## Verdict — Phase 4b RE-CONFIRMED (flag stays `True`)

Flipping the flag recovers throughput but **fails the quality gate**:
- **PF 2.54 → 1.52 (−40%)** — below the PF≥2.54 acceptance bar.
- avg RR +0.545 → +0.248 (halved); WR −9.5pp; **max DD 3.1% → 8.2% (≈2.6×)**.
- Total return rises only **+3pp** (+20.6% → +23.7%) for **2.5× the trades** — the marginal ~70 shadow
  trades are near-break-even and dilute every quality metric. This is exactly the structural staleness
  Phase 4b identified (shadow displacement from a prior HTF window), now re-confirmed at n=89 (not n=22).

**Decision:** keep `shadow_advisory_only=True`. The 35-trade BNBUSDT ceiling is **correct-by-policy**,
not a bug. Cheap config levers (sessions + shadow) are now **exhausted** for BNBUSDT.

## Caveat (operator's call)

A pure **return-maximizer** would note total return is marginally higher with shadow ON (+23.7% vs
+20.6%). The project doctrine gates on **quality (PF/DD)**, not raw return — and PF/DD degrade sharply —
so under current doctrine the flag stays True. Flipping it would be an explicit objective change
(`goal.md` deviation flag) and is not recommended on this evidence.

## Implications

- **Governance verdict validated under the new regime** — the audit question is answered: YES, Phase 4b
  still holds. No global policy change.
- **Per-instrument (Part 3.4):** re-run this A/B for SOLUSDT before assuming the verdict generalizes
  (the original was BNBUSDT-only).
- **Next throughput lever is upstream**, not governance: detection supply (202 EXPANSION → 134 RETEST).
- **Trd-M6 remains deferred** — intelligence is not the constraint; the cheap levers are exhausted and
  the remaining question is OOS persistence (Part 4A).
