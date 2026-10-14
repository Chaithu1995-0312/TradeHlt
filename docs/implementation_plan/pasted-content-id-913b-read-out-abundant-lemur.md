# Verify: "Ontology answers producer side of F-116; consumer side empty"

## Context
A pasted read-out claims the WHAT-layer (`configs/formulas/market_ontology.yaml`) already declares units for the
producer side, and that `consumed_by: [UNKNOWN]` on every feature the Set 2/3/4 audits flagged is the real F-116 gap.
Verified against source (read-only, grep + Read, 2026-10-07).

## Verdict: directionally right, overstated in 4 places

### Confirmed
- FM-022 / FM-023: `units: price_scaled`, `normalization_basis: atr_relative`, `known_issue` citing F-061,
  `replacement_identity` FM-030/031, `config_key` (ontology L886-976). FM-023 states the 98.8%/99.9% tanh saturation and REVERSAL collapse.
- FM-030/031: `units: dimensionless`, `active: false` (L986-1059).
- FM-041 `atr`: dimensionless / `normalization_basis: close` (L1573-1585). FM-074: `price_absolute` / `none` (L1605-1617).
- FM-050 `depends_on: [atr_absolute]`, `bounds {0,1,2}` (L2047-2059). FM-064 `vector_index: 11`, rename history (L1947-2007).
- `consumed_by: [UNKNOWN]` on FM-022, 023, 041, 050, 053, 064, 074.
- No `pip_value_per_lot` / `contract_size` anywhere in the ontology (grep: 0 hits). `units_expected` exists nowhere.

### Wrong or overstated
1. **"Producer side is done."** `units:` is declared on only ~12 of 79 FM entries (L897-2339). FM-045, FM-050,
   FM-053, FM-064, FM-089 have none. The producer side is partial, not complete.
2. **"Only SEM-series nodes have non-UNKNOWN consumed_by."** False. FM-027/028/029/070 (L1189-1319),
   FM-061/094, FM-066/067 (L2326/2355) and FM-084 are all populated. Caveat: several list *feature ids or
   modules*, not call sites.
3. **"SEM-031 populated."** `consumers: []` (L3675), not populated. SEM-013/021 are correct.
4. **"FM-089 volume says tick_count."** No `tick_count` and no `units` on FM-089 (L492-515). Its formula is
   "raw bar volume"; the TICK_VOLUME_APPROXIMATE caveat is F-099 prose.
- Minor: FM-064's rename belongs to SCHEMA-V6 / F-107, not "F-064" (F-064 is the XAUUSD dimensional-mix generalisation).
- FM-030/031 consumed_by is `[]`, not `[UNKNOWN]`.

### Schema constraint the read-out missed
Ontology L114 defines `consumed_by` as "SCALAR consumers only (named call sites reading this feature alone), or [UNKNOWN]".
Vector consumers (BitNet/Gaussian reading the 48-dim vector) are meant to resolve via `vector_key`/`vector_index`,
so populating `consumed_by` for FM-022/023 with `detect_regime` etc. is fine, but a consumer-units lint must also
cover vector-slot readers or it would miss the model consumers. The block is `additive_spec_blocks: unread by any runtime path`
(L102), so a governance test is enforceable but nothing is runtime-binding.

### Unverified
- "The audits already named the consumers" (not checked against Set 2/3/4 reports).
- FM-041 "SMA-smoothed, not Wilder" caveat; FM-050 state names; SP-001 `predicate_definition/v1` tree.
- The F-116 record (current-findings L1789) frames it as S5/S6 consumer-contract defects, NOT "add unit declarations";
  the read-out's scoping of F-116 is its own reading.

## Proposed next step (only if you approve)
Pilot on FM-022 only, additive, hash-neutral: add `consumers_declared: [{consumer, units_expected, dtype}]` next to
`consumed_by`, fill from source-grepped call sites (`engine_runner.detect_regime`, `breakout_engine`,
`heuristic_gaussian_engine`, `gate_intelligence`), plus a floor test in `tests/governance/` that fails when a consumer's
`units_expected` != feature `units` without a `known_issue` waiver. Must go through the Construction Protocol
(`change_contracts.json` classify -> manifest) and be a separately authorized turn (§6.8: no silent remediation).
Do NOT add FM-089 `tick_count` or lot-size identities without a separate decision (pip_value is HOW-layer config).

## Verification
`venv/Scripts/python.exe scripts/governance/construction_protocol.py check` and
`check_governance_invariants.py --all`; baseline red count captured first.
