# Semantic OS v2 Memory — the meaning plane (navigation)

> **Last generation:** 2026-10-02 (branch `semanticos_impl`: slices `abc641d` / `0d05bcf` /
> `4a929b6`, grounding `f2e44ae`)
> **Code-first:** `src/semantics/registry.py` (validator) and the registries win over this file.
> **Spec:** [`SEMANTIC_OS_V2_MEANING_PLANE.md`](../governance/SEMANTIC_OS_V2_MEANING_PLANE.md) §§1–15.

## Purpose

One canonical answer to "what does this trading word MEAN in this repo" — a sweep, a thesis, a
stop, a position — with every place the existing code says something different recorded, not
fixed. **Meaning authority only** (CLAUDE.md §6.6): no runtime, promotion or G001 authority.
Nothing in `src/semantics/` is wired into the engine, the pipeline or the live rail.
Existing code is **evidence, not authority**: there is no parity oracle (decision O-1).

## The four layers (I-12: a concept may only use its own or lower layers)

| Layer | Id prefix | Holds | Must never represent |
|---|---|---|---|
| GEOMETRY | `GP-01…07` | bar-vs-level predicates (pierce `>`, beyond `>`, reach `>=`, …) | meaning |
| MARKET | `MKT-L/Z/E/C/P` | levels, zones, events, conditions, the CRT episode + stages (`MKT-P01.SWEPT`) | roles, policy, position state |
| TRADING | `TRS-01…08` | thesis, objective, invalidation, entry, stop, target, cost, outcome | market facts, fills |
| DECISION_EXECUTION | `DEX-01…09` | size, portfolio admission, fill, approval, position, exit schedule, exit rule, carry, position result | market meaning |

Three distinctions people get wrong: a level is not its role (I-10); a market event (50% retrace)
≠ a thesis invalidation ≠ a position stop (I-11); an episode stage ≠ a position state.

## Artifacts

| What | Where |
|---|---|
| Concept contracts (one record per id: definition, rule, parameters + `identity_bearing`, inputs, availability, absence, authority, divergences) | `configs/formulas/concept_contracts.yaml` |
| Code → concept mappings, one shard per producer (`representations` / `deprecated` / shrink-only `unmapped`) | `configs/formulas/representation_registry/` — `feature_pipeline`, `crt_engine`, `parent_crt`, `research_walks`, `research_costs`, `live_rail` |
| Engine RESET reason → terminal authority / class | `configs/formulas/terminal_reason_map.yaml` |
| Runtime value objects (call existing authorities, never copy them) | `src/semantics/geometry.py`, `src/semantics/market/`, `src/semantics/trading/`, `src/semantics/execution/` |
| Validator (V-1…V-19) and loaders | `src/semantics/registry.py` (`validate_all()`) |
| Derived consumers (HEURISTIC) | `src/semantics/consumers.py` |
| Grounding of concepts / representations | `src/governance/concept_grounding.py` via `governance.semantic_grounding.SemanticGrounder` |
| Implementation briefs (history of each slice) | `docs/implementation_plan/semantic-os-v2-slice{1,2,3}-handoff.md` |

## Grounding (CLAUDE.md §6.7, spec §15)

```text
python scripts/governance/query_semantic_os.py --ground --kind CONCEPT --token sweep
python scripts/governance/query_semantic_os.py --ground --kind REPRESENTATION --token crt_engine:Trade.pnl
python scripts/governance/query_semantic_os.py --ground --kind RELATIONSHIP --relation represents --source crt_engine:Trade.pnl --dest DEX-09
python scripts/governance/query_semantic_os.py --ground --kind RELATIONSHIP --relation input_of --source TRS-07 --dest DEX-09
```

| Answer | Means |
|---|---|
| CONCEPT GROUNDED | id, name or alias resolved; payload has rule, divergences, representations, consumers |
| CONCEPT GROUNDED + `PROPOSED` caveat | the concept is named but its rule is not accepted — never assert the rule, never bind code to it (G-1) |
| REPRESENTATION UNKNOWN "unmapped" | the code item has no concept yet; the reason is quoted (G-2) |
| REPRESENTATION REFUSED | marked dead (I-13) — do not assert it |
| AMBIGUOUS | a name matches two concepts / a bare key two shards — use the id / `producer:key` |
| `--kind NOUN` | the **v1** vocabulary only; it never finds v2 concepts (G-3) |

`consumers` in a payload are HEURISTIC (AST name match): a list of where to look, never proof.

## Workflows

1. **Before stating what a trading term means** — ground it with `--kind CONCEPT`. Quote the rule
   and the divergences; do not infer meaning from a variable or config-key name (several names lie:
   `tp*_atr_multiplier` multiplies R, `partial_tp_breakeven_enabled` trails half way).
2. **Before stating what a code field means** — `--kind REPRESENTATION --token producer:key`.
3. **Add or amend a concept** (design discussion with the user first):
   record in `concept_contracts.yaml` → map its code in a shard (or list it in `unmapped`) →
   `validate_all() == []` → update the unmapped pin in `tests/governance/test_representation_registry.py`
   if a list shrank → spec amendment (`A-n`) or decisions table → gate + floor.
4. **Found code that disagrees with a contract** — add a divergence `{surface, current, contract,
   disposition: RECORDED}` on the concept. Never fix the code in the same turn. A question the user
   must settle later takes `decide_in: slice_N` + `decision`; once settled, `decided_in` + `resolution` (A-10).
5. **Review an implementation** — authorities are called, never copied (I-8); every value object has
   `concept_id`, `parameterization_id`, `available_at` (I-6: never earlier than an input's bar);
   absence is `None`, never a sentinel (I-7); roles never write a level's status (I-10); a thesis
   needs an invalidation and a stop (I-11); an outcome names walk, basis, cost model (I-15).

## Validator (`validate_all()`)

| Check | Catches | Invariant |
|---|---|---|
| V-1 | duplicate ids / keys, missing fields, alias clashes | identity |
| V-2 | ACCEPTED without REPO/USER_DECISION evidence or with an untracked source | ACCEPTED |
| V-3 | an input from a higher layer | I-12 |
| V-4 | a parameter without `identity_bearing` | I-17 |
| V-5 | a MEASUREMENT without unit + normalisation basis | I-4 |
| V-6 | a representation of a missing or PROPOSED concept | I-18 |
| V-7 | an out-of-domain value without `legacy_values` + `divergence_ref` (config refs resolved first) | I-2 |
| V-8 | two representations with one identity | identity |
| V-9 / V-10 | a canonical feature slot / CRTState / HTFState / ObjectiveStatus / `Trade` field not covered | coverage |
| V-11 | an `unmapped` list that grew | ratchet |
| V-12 | an engine RESET reason with no terminal-map entry | I-3 |
| V-13 | a THESIS without invalidation + stop roles | I-11 |
| V-14 | an OUTCOME representation without walk + basis (gross needs cost `none`) | I-15 |
| V-15 | a `.status` write or `.with_status(` in trading / execution code | I-10 |
| V-16 | an open `decide_in: slice_3` deferral; a `decided_in` without `resolution` | D2-2, A-10 |
| V-17 | execution code moving a thesis or mutating an object | I-3 |
| V-18 | position exit reasons out of step with `ExitReason` | I-9 |
| V-19 | a PROPOSED concept id used as a string constant in `src/semantics/` | I-18 |

## Commands

```text
venv/Scripts/python.exe -m pytest tests/semantics tests/governance/test_concept_contracts.py tests/governance/test_representation_registry.py tests/governance/test_terminal_reason_map.py tests/governance/test_concept_grounding.py -q
venv/Scripts/python.exe -c "from semantics.registry import validate_all; print(validate_all())"
venv/Scripts/python.exe scripts/maintenance/check_governance_invariants.py --all
```

The floor carried 7 pre-existing reds on this branch (schema-version census, model-path literals ×3,
script-registry grandfather ×2, corpus-read lint) — re-measure before claiming a regression.

## Integration run (semantic conformance test, spec §16)

`venv/Scripts/python.exe scripts/governance/semantic_os_integration.py` runs the REAL backtest twice
on one XAUUSD corpus (default `data/mt5/XAUUSD_W2026-07-06-to-2026-08-07.csv`), refuses to judge
unless both event streams are identical (replay gate), then compares every bar with the contracts
(`src/semantics/integration/`): verdicts AGREE / EXPECTED_DIVERGENCE (attributed to a recorded
divergence by an explicit `(concept, surface)` pair) / UNEXPLAINED (candidate semantic defect) /
NOT_CHECKABLE, plus a D-level per concept. Never reports P&L (R1-D). Run 1 found 2 defect classes
(normalised as R1-A wick reference price, R1-B stage-dependent rollover expiry); run 2 on the same
corpus: 0 UNEXPLAINED. The month opens no trades: C5/C6 need a trade-exercising slice (R1-C).
Spot-check every UNEXPLAINED row at source before calling it a defect.

## Pitfalls

- Homonyms: `atr` is close-relative in the feature vector and price-unit in the engine; `.status`
  exists on many classes. The consumer scan can list false consumers — read the module.
- `unmapped` is shrink-only, and its pin test asserts equality: removing an entry needs the pin updated.
- Settings are not identity (I-17): a config value enters identity only through an identity-bearing
  parameter; a dotted REP value (`backtest.sl_anchor`) is resolved against `ACTIVE_VERSION`.
- PROPOSED concepts (e.g. `MKT-E03 choch`, `GP-07 in_band`) have zero representations and no bound code.
- Open program items: acting on recorded divergences (Phase B, each fix needs user approval), wiring
  into the engine, the deferred list in spec §11.

## Reading order

1. Spec §3 (layers), §5 (identity), §9 (invariants), then the slice section you need (§13 trading,
   §14 decision/execution, §15 grounding).
2. The concept records you are touching in `concept_contracts.yaml`.
3. The matching shard in `representation_registry/`.
4. The `src/semantics/` module, then its tests under `tests/semantics/`.
