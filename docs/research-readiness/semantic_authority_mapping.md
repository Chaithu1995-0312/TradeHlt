# Semantic Authority Mapping (CH-semantic-authority-mapping)

Read-only investigation artifact. No src/config/authority edits.
Generated 2026-10-08 from live authorities (venv).

Authority model: `concept_contracts.yaml` = meaning authority (CLAUDE.md s6.6,
grants no runtime authority); `representation_registry/*.yaml` = single source
representation->concept (I-2); consumers HEURISTIC via `src/semantics/consumers.py`
(I-14, A-6); code = evidence not authority (O-1). `validate_all() = []`.

Counts: 62 concepts (58 ACCEPTED / 4 PROPOSED: GP-07, MKT-C02, MKT-E03, MKT-Z06);
75 representations (fp 34 / crt_engine 25 / parent 9 / live_rail 3 / costs 2 / walks 2);
fp unmapped ratchet 40; zero-consumer concepts 23; live schema 79-dim v9.0.

## Per-word table (word | vector | concept | rep verdict | divs | consumers)

| word | vec | concept | rep verdict | divs | cons |
|---|---|---|---|---|---|
| liquidity_sweep | yes 21 | MKT-E01 ACCEPTED | REP feature_pipeline:liquidity_sweep | 6 | 38 |
| sweep_detected | yes 20 | MKT-E01 ACCEPTED | REP (abs projection) | 6 | 38 |
| double_sweep | yes 6 | MKT-C04 ACCEPTED | REP | 6 | 26 |
| break_of_structure | yes 22 | MKT-C01 ACCEPTED | REP | 1 | 22 |
| trend_bias | yes 10 | MKT-C03 ACCEPTED | REP | 1 | 34 |
| change_of_character | yes 47 | MKT-C07 ACCEPTED | REP choch.py pure combo | 2 | 7 |
| higher_high | yes 25 | MKT-E08 ACCEPTED | REP | 0 | 16 |
| lower_low | yes 26 | MKT-E08 ACCEPTED | REP | 0 | 16 |
| higher_low | yes 72 | NONE (FM-121) | UNMAPPED ratchet | 0 | 0 |
| lower_high | yes 73 | NONE (FM-122) | UNMAPPED ratchet | 0 | 0 |
| sideways | yes 74 | NONE (FM-123) | UNMAPPED ratchet | 0 | 0 |
| swing_high | yes 23 | MKT-L01 ACCEPTED | REP formation flag | 5 | 19 |
| swing_low | yes 24 | MKT-L01 ACCEPTED | REP formation flag | 5 | 19 |
| displacement_flag | no | MKT-E05 ACCEPTED | NON-VECTOR enriched (FM-069) | 1 | 0 |
| retest_flag | no | MKT-E09 ACCEPTED | NON-VECTOR enriched (FM-061; band PROPOSED OQ7) | 1 | 0 |
| rsi_state | no | NONE | NON-VECTOR enriched (FM-068; no slice-1 RSI concept) | 0 | 0 |
| body_commitment | no | NONE | SHADOW L2 magnitude band | 0 | 0 |
| atr_magnitude | no | NONE | SHADOW L2 magnitude band | 0 | 0 |
| momentum_magnitude | no | NONE | SHADOW L2 magnitude band | 0 | 0 |
| liquidity_sweep_e01 | cond | MKT-E01 ACCEPTED | CONDITIONAL E01 (FM-090) | 6 | 38 |
| sweep_detected_e01 | cond | MKT-E01 ACCEPTED | CONDITIONAL E01 (FM-091) | 6 | 38 |
| double_sweep_e01 | cond | MKT-C04 ACCEPTED | CONDITIONAL E01 (FM-092) | 6 | 26 |
| retest_flag_e01 | cond | MKT-E09 ACCEPTED | CONDITIONAL non-vector (FM-094) | 1 | 0 |
| wait_for_next_candle | no | NONE | DECISION STATE FM-128 (confirmation_state.py) | 0 | 0 |
| RANGE | no | MKT-P01.AWAITING_SWEEP | REP crt_engine:CRTState.RANGE | 0 | 2 |
| SWEEP | no | MKT-P01.SWEPT | REP crt_engine:CRTState.SWEEP | 0 | 2 |
| DISPLACEMENT | no | MKT-P01.DISPLACED | REP crt_engine:CRTState.DISPLACEMENT | 0 | 2 |
| EXPANSION | no | MKT-P01.EXTENDED | REP crt_engine:CRTState.EXPANSION | 1 | 2 |
| RETEST | no | MKT-P01.RETESTING | REP crt_engine:CRTState.RETEST | 0 | 2 |
| SHADOW_PENDING | no | MKT-P01.SHADOW_PENDING | REP crt_engine:CRTState.SHADOW_PENDING | 0 | 2 |
| EXECUTION | no | NONE | UNMAPPED BLOCKED L3 v2.0.0 | 0 | 0 |
| RESOLUTION | no | NONE | UNMAPPED BLOCKED L3 v2.0.0 | 0 | 0 |
| EXPIRED | no | NONE | UNMAPPED (TTL undecided) | 0 | 0 |
| 13 shapes | no | NONE | SHADOW LABELS (classifier; 5 blocked) | 0 | 0 |
| 9 profiles | no | MKT-L01 | FOUNDING PARAM values | 5 | 19 |

Full per-word representations, divergence surfaces, and consumer lists:
`semantic_authority_mapping.json` (55 rows).
