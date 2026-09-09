# Design defect resolutions — D1 (OPEN), D2, D3, L4

**Status:** design-only. No `src/` changes.  
**Date:** 2026-09-06 (rev 3)  
**Priority:** D2 (gate) → D3 → L4; **D1 remains OPEN**

**rev 3 note:** rev 2's population key was declared in `context.schema.yaml` only. The artifact
that actually performs the ODP lookup (`odp.schema.yaml`) was still v0.3.0 with an "exact
non-null keys" rule that re-admitted `mechanism_confidence` into the match — closed this rev
(`odp.schema.yaml` → v0.5.0, `lookup_rules` rewritten to `identity_selectors` only). Also added
the producer-actionability rule this rev: recording `state_producer` makes divergence visible;
this rule makes acting across it illegal — a resolver-produced ODP may inform a Finding but may
never back a PolicyOpinion on the (engine-only) live path. Also: 4 of 11 YAML files in the
package failed to parse (2 introduced by rev 2's edit, 2 pre-existing since v0.3 and missed by
the review that produced rev 2) — fixed; `identity_selector_fields` wildcards (`structure.*`,
`transition.*`) replaced with the explicit field list; `default_for_odp_measurement: engine`
removed as a silent default on a required identity field; F-069 agreement figure corrected to
88.16% (the 64–99% range was a retracted estimate, not the authoritative figure).

## D2 — IDENTITY / POPULATION GATE (strengthened)

**Status:** RETIRED (verified 2026-09-06) — population key = `contract_ref + identity_selectors`; `identity_selector_fields` byte-identical in `context.schema.yaml` and `odp.schema.yaml` v0.5.1 (no wildcards); `producer_actionability_rule` inlined in PolicyOpinion contract v1.2 and ODP schema. **Guarded mechanically as of 2026-09-08** by `tests/governance/test_design_schema_identity_selectors.py` (raw-text + parsed equality) — the byte-identity claim now rests on a floor test in `GREEN_FLOOR`, not solely on the dated manual verification above.


**Class:** same label, different population — invalid aggregation.

Engine SWEEP ≠ Resolver SWEEP; Resolver SWEEP (variant A) ≠ Resolver SWEEP (variant B) if `variant_id` / enabled_links differ.

**Not enough:** `(state)` or even `(state_producer, variant_id, state)` alone.

**Admissible ODP population key:**

```
contract_ref + identity_selectors
```

where identity_selectors include (as applicable):

- `state_producer` (`engine` | `resolver`)
- `variant_id` (required when `resolver`; null when `engine`)
- `state`
- other **discrete** Context identity selectors (structure enums/bools, `htf_bucket`, …)

`contract_ref` binds measurement surfaces (lookahead, metric, inclusion/exclusion, corpus).  
Next resolver sweep / ontology revision must bump `variant_id` and/or `contract_ref` — never silently reuse the old population.

**Producer-actionability rule (rev 3):** an ODP with `state_producer=resolver` is
observation-only. A PolicyOpinion gating the live decision path (CRTEngine, `state_producer=engine`)
may only consume ODPs whose producer matches. On no engine-producer match, treat as
`on_odp_fallback` — never silently fall back to a resolver-produced row.

Patched: `context.schema.yaml` **v0.5.0**, `odp.schema.yaml` **v0.5.0** (rev 3 — lookup rule was
previously undeclared on the artifact that performs the match),
`POLICY_OPINION_SOCKET_ADAPTER_CONTRACT.md` (producer-match doctrine row + `odp_ref` note),
`execution_policy.schema.yaml` (`on_odp_fallback` description).

## D1 — OPEN (belief vs preference boundary)

**Not closed.** Not merely “thresholds allowed vs forbidden.”

The repository already permits **dynamic** DecisionEngine thresholds (truth-estimation calibration).

**Unresolved doctrine choice:**

> May PolicyOpinion move DecisionEngine thresholds for **preference** reasons?

| Pole | Meaning |
|------|---------|
| Belief boundary | DecisionEngine thresholds estimate “what we believe?” — Policy must not retune them; ABSTAIN-only (v1.1 matrix default **working hypothesis**) |
| Preference boundary | Some threshold moves are explicit preferences (“what we want?”) and could be legal Policy opinions |

**Status:** **OPEN** — architectural doctrine, not an evidence finding.  
Socket Adapter Matrix v1.1 remains the **provisional** implementer guide (ABSTAIN-only) until this doctrine is decided.  
`execution_policy.schema.yaml` threshold-mutation surfaces stay **provisionally superseded**, not permanently closed.

## D3 — Identity ≠ Measurement (strengthened beyond mechanism)

**Bigger than `mechanism*`:** continuous floats in identity explode cardinality.

**Out of identity (measurements / observations):**

- `location.htf_percentile`
- `location.distance_to_boundary_atr`
- `mechanism`, `mechanism_confidence`
- `resolver_state` (sidecar)

**In identity (discrete selectors):**

- `htf_bucket` (not the raw percentile)
- producer / variant / state, and each `structure.*` / `transition.*` field individually —
  `context.schema.yaml`'s `identity_selector_fields` enumerates them explicitly (no wildcards,
  rev 3): a field added later to `structure:`/`transition:` is not automatically an identity
  selector, it must be added to the list or it cannot be selected on.

## L4 — polarity (formalized as an explicit assumption, not merely unchanged)

Intentional v1 cardinality reduction for boolean breaker/OB/CHoCH; signed `liquidity_sweep_direction`
retained. `context.schema.yaml` §`structure_polarity_doctrine` now states this as an explicit
architectural ASSUMPTION (not settled doctrine) with a named falsification test: measure the same
Context boolean-vs-signed under one MeasurementContract and compare outcome distributions — if the
signed split yields materially different shapes, the boolean collapse is destroying information and
must be promoted to signed fields; if indistinguishable, the collapse is free and the assumption is
discharged. Under §6.6 this stays `epistemic: unknown_mechanism` until that experiment runs — a
design choice, however reasonable, is not evidence.

`breaker_polarity` / `order_block_polarity` / `choch_direction` do NOT exist as schema fields yet —
they are named only as the future extension shape. A MeasurementContract cannot currently "declare"
them; until added as optional `-1 | 0 | 1 | null` fields, any contract needing polarity must say so
explicitly in its `population.inclusion`/`exclusion` prose rather than reference a field name that
does not resolve.

## Architecture trajectory

```
Market Construction
  → Identity (producer + variant + discrete selectors)
  → Context
  → ODP Measurement   (keyed by contract_ref + identity_selectors)
  → Policy Opinion    (D1 open on belief vs preference)
  → Socket Adapters
  → Existing Runtime Owners
```

Not: Semantic Resolver → Execution Ontology → Trade Object (new authorities).
