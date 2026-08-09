# Topic: Capital Pressure Ratio (CPR) — Capital Semantics Layer

> **Topic-visibility unit.** Latent pre-OHLC capital layer (research registration).  
> Created: 2026-08-08 · Updated: 2026-08-08 · Status: living (UNKNOWN ontology; MC-CPR-L0 PREREGISTERED; no runtime)

## In plain language

Markets move because capital seeks opportunities on one side or the other. This topic names that
idea carefully: **Capital Pressure Ratio (CPR)** is a *latent* imbalance between buy-seeking and
sell-seeking capital. We never observe CPR directly in this repository — we observe **OHLC**
and everything after it (features, CRT, fusion, execution, risk). CPR is registered so agents
do not invent a “capital flow” engine that silently contradicts OHLC→CRT ownership. It is a
**proposed semantic parent** of candle morphology, not a replacement for the CRT spine.

## Code covered

**No production implementation.** Ontology + sealed measurement preregistration only:

- [`configs/formulas/market_ontology.yaml`](../../configs/formulas/market_ontology.yaml) — `canonical_unknowns`:
  - `UNK-002` `UNKNOWN_LATENT__GLOBAL_CAPITAL`
  - `UNK-003` `UNKNOWN_LATENT__INVESTMENT_POOL`
  - `UNK-004` `UNKNOWN_LATENT__DIRECTIONAL_INVESTMENT` (BI / SI)
  - `UNK-005` `UNKNOWN_LATENT__CAPITAL_PRESSURE_RATIO` (CPR)
- Measurement contract (schema-valid, **mt00=UNRUN**):
  - [`configs/research/measurement_contracts/MC-CPR-L0-XAUUSD-M15-UTC-V1.json`](../../configs/research/measurement_contracts/MC-CPR-L0-XAUUSD-M15-UTC-V1.json)
  - [`docs/research-readiness/mc-cpr-l0-xauusd-m15-preregistration.md`](../research-readiness/mc-cpr-l0-xauusd-m15-preregistration.md)
- Validation: `features.registry.validate_semantic_registry` (via `tests/test_semantic_registry.py`)

**Explicit non-coverage (do not conflate):**

- Trader capital / risk% — [`src/core/ultron_risk_gate.py`](../../src/core/ultron_risk_gate.py)
- Portfolio allocation — [`src/portfolio/`](../../src/portfolio/)
- CRT geometry / state — [`src/config_layer/crt_engine_v2.py`](../../src/config_layer/crt_engine_v2.py)
- Features — [`src/features/feature_pipeline.py`](../../src/features/feature_pipeline.py)

## Ins / Outs

- **Ins (proposed latent):** Global capital → Investment pool → BI, SI → CPR = BI/SI (candidate formula; **not validated**).
- **Outs (proposed manifestation):** OHLC body/range/ATR/displacement/sweep/retest/continuation — already measured by the existing feature + CRT stack.
- **Outs (forbidden without authority):** automatic risk%, fusion weight, or `TRADE_OPENED` from CPR.

## Layer placement (non-contradiction)

```text
UNK-002 Global Capital
    → UNK-003 Investment Pool
        → UNK-004 BI / SI
            → UNK-005 CPR          ← latent cause (proposed)
                → OHLC manifestation
                    → Feature Pipeline     ← repository starts here today
                        → CRT State
                            → Execution Intent
                                → Trade Entry / SL geometry
                                    → Position Size
                                        → Ultron capital risk
```

Repository **owns OHLC onward**. CPR sits **before** OHLC as explanation, not as a hot-path input.

## Entry points & validations

- **Reached via:** documentation / ontology only — no CLI, no EngineRunner key, no config section.
- **Validated by:** `validate_semantic_registry()` — node shape + epistemic block for UNKNOWN status.
- **Authority:** **NONE** (§6.5). `PRODUCTION_CERTIFIED` only after measured G001 under a sealed measurement contract.

## Tests

- [`tests/test_semantic_registry.py`](../../tests/test_semantic_registry.py) — semantic registry floor (includes new UNK nodes once ontology loads).

## Fits in architecture

- Upstream conceptual parent of Step 1 in [`docs/architecture/signal-flow.md`](../architecture/signal-flow.md) (candle ingest) — **not** a new spine step.
- Related research discipline: [`research-measurement-contract.md`](research-measurement-contract.md), Authority Ladder in `CLAUDE.md` §6.5.
- Distinct from portfolio capital: [`portfolio-allocation.md`](portfolio-allocation.md).

## Discussion (filled in-session)

- **Enhancements:** 2026-08-08 — Registered UNK-002…UNK-005 as Capital Semantics Layer. Formula CPR=BI/SI and risk-ladder examples (0.25%…2%) recorded as **candidate hypotheses only** inside epistemic blocks / notes. No runtime wiring.
- **Enhancements:** 2026-08-08 — Sealed preregistration `MC-CPR-L0-XAUUSD-M15-UTC-V1` (OHLCV-only synthetic Buy/SellPressure, residualization vs 39-dim, BH-FDR, L1 info gate only; `Program_CPR_L0` not Program 6). Schema validation errors=0. economic_claims_allowed=false.
- **Ambiguities:** 2026-08-08 — Whether BI/SI is identifiable from M15 OHLCV alone (circularity risk). Tape/OI requires a **new** MC id if ever pursued.
- **Risks:** 2026-08-08 — Agents may over-claim CPR as “the” cause of inverted-SL or zone rejects. Those failures were adjudicated as geometry/wiring/score without any CPR object.
- **Blockers:** 2026-08-08 — E-MT-01 incomplete; global Measurement Contract layer still OPEN.
- **Enhancements:** 2026-08-08 — Observe-only harness `scripts/research/mc_cpr_l0_residual_harness.py` ran on `data/mt5/XAUUSD_M15.csv` (n=47275). **L1_FAIL**: no BH-FDR association of residual η; N=16 max ΔR²(eta|39dim) ≤ 0. Artifacts under `results/research/mc_cpr_l0/`. UNK-005 stays UNKNOWN; no production authority.
- **Need more info:** 2026-08-08 — Optional: OI/tape as new MC id only if authorized; do not reopen L0 with N/cost tweaks.

## What good looks like

1. CPR remains **latent** until residual tests under MC-CPR-L0 pass L1 (then UNK-005 → OBSERVED in place).  
2. OHLC→CRT→risk ownership never short-circuited by a CPR number.  
3. Any future CPR→risk% program is **config-gated**, Ultron-subordinate, and G001-proven before authority.  
4. Ontology nodes refine **in place** (UNKNOWN → … → STABLE); no duplicate “CPR v2” files.  
5. `economic_claims_allowed` stays false until E-MT-00 PASS + E-MT-01 COMPLETE.
