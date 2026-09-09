# Repair the context-finding-odp design pack (v0.5 → v0.5.1)

## Context

The v0.5 edit landed the D2/D3/L4 doctrine well: `state_producer` + `variant_id` are now
identity fields, `identity_selector_fields` is an explicit allowlist, continuous floats and
`mechanism*` are excluded from identity, the polarity collapse is recorded as an intentional
v1 assumption, `execution_policy.schema.yaml` is marked `SUPERSEDED-IN-PART` rather than
deleted (correct §6.2 rule 4), the matrix is marked provisional with D1 OPEN, and all three
examples were updated.

Two problems remain, one of which is blocking:

1. **4 of the 11 YAML files in the package do not parse.** Verified by read-only
   `yaml.safe_load` sweep. Two breaks were introduced by the v0.5 edit; two are pre-existing
   and were **missed by my own first review** — that review verified source pointers and
   semantics but never checked machine-readability, which was a gap in the review itself.
2. **D2 is half-closed.** The population key is declared in `context.schema.yaml`, but the
   artifact that actually performs the lookup (`odp.schema.yaml`) is untouched at v0.3.0 and
   still says "exact non-null keys" — which re-admits `mechanism_confidence: none` into the
   match and contradicts the new identity rule. And nothing yet forbids a PolicyOpinion that
   gates the **engine** path from consuming a **resolver**-produced ODP.

Outcome: the pack parses, D2 closes on both the identity and the actionability half, and the
identity allowlist stops inferring.

## A. Mechanical — make the pack parse (blocking)

Verified failures, exact locations:

| File | Line | Cause | Origin |
|---|---|---|---|
| `schemas/context.schema.yaml` | 10 | `resolves:` / `open:` indented under the scalar `status: design_draft` | v0.5 edit |
| `examples/policy_example_read_odp.yaml` | 11–14 | `state_producer` placed inside `context_selector`, but `variant_id` and `state` hoisted to the `reads:` level, then `structure:` re-indented | v0.5 edit |
| `schemas/execution_policy.schema.yaml` | 131 | `{ type: list[string] | null }` — the `[` breaks a flow mapping | pre-existing v0.3 |
| `schemas/finding_registry.schema.yaml` | 42 | `{ type: list[string], required: true, min_items: 1 }` — same class | pre-existing v0.3 |

- **context.schema.yaml:9-11** — move `resolves:` / `open:` out from under `status:` into a
  sibling block (e.g. a top-level `defect_status:` mapping).
- **policy_example_read_odp.yaml:11-14** — restore one indentation level: `state_producer`,
  `variant_id`, `state`, `structure`, `transition`, `location` all belong **inside**
  `context_selector`. As written the Context selector no longer contains its own state, which
  is a semantic error independent of the parse error.
- **Both `list[...]`-in-flow-mapping cases** — quote the value (`type: "list[string] | null"`)
  in every affected line, not just the two the parser stops at. Fix by scanning each file for
  `{ type: list[` rather than by line number, since the parser reports only the first.

## B. Complete D2 — the half that is still open

- **`odp.schema.yaml` (bump 0.3.0 → 0.5.0).** Replace `lookup_rules` "exact non-null keys"
  with exact-match on `identity_selectors` only, and state the admissible population key as
  `contract_ref + identity_selectors` in the artifact that owns the lookup. Without this, D2
  lives only in the Context schema and the ODP side still matches on annotations.
- **Add the producer-match rule** to `POLICY_OPINION_SOCKET_ADAPTER_CONTRACT.md` (and mirror
  in `execution_policy.schema.yaml`): a PolicyOpinion may consume an ODP only when its
  `state_producer` matches the producer on the live decision path. The live path is the
  engine, so resolver-produced ODPs are observation-only. Recording the producer makes the
  divergence visible; only this rule makes acting across it illegal.
- **`context.schema.yaml:68` — delete `default_for_odp_measurement: engine`.** A default on a
  `required: true` identity field re-opens D2 through the back door: an ODP that omits the
  producer silently becomes `engine`. This is the silent-default class §6.5 closed after F-018;
  identity must fail closed.

## C. Identity hygiene

- **`identity_selector_fields:` — replace the `structure.*` and `transition.*` wildcards with
  the explicit field names.** A wildcard re-inserts inference into an allowlist whose whole
  purpose is explicitness: when `breaker_polarity` is added later (the polarity doctrine
  already anticipates it), it would silently join identity and re-key every Context.

## D. Evidence correction

- **`context.schema.yaml:66`** — "~69–88% agree depending on run" is not supported. F-069's
  authoritative figure is **88.16%** (`injection=none`, 41,607/47,197 XAUUSD M15); the 64–99%
  band is recorded *in F-069 itself* as a stale in-session estimate produced under
  unconditional engine-oracle injection that "never measured configuration alone". Replace with
  88.16% and cite F-069.
- **`DESIGN_DEFECTS_D1_D2_D3_L4.md:68` — "L4 — polarity (unchanged)"** understates what
  shipped: `context.schema.yaml:225-245` added a full `structure_polarity_doctrine` with the
  assumption and the "silent equivalence forbidden" clause. Also note the polarity fields it
  names (`breaker_polarity`, `order_block_polarity`, `choch_direction`) do not exist as fields
  yet, so a MeasurementContract cannot currently "declare" them — either add them as optional
  null fields or mark them explicitly as not-yet-expressible.

## Out of scope

D1 stays OPEN — belief-vs-preference is a doctrine choice, not a defect, and the matrix is
correctly marked provisional. Nothing in `src/`. No config. Design-only throughout.

## Verification

```bash
venv/Scripts/python.exe -c "
import yaml,glob
for p in sorted(glob.glob('docs/design/context-finding-odp/**/*.yaml',recursive=True)):
    try: yaml.safe_load(open(p,encoding='utf-8')); print('OK  ',p)
    except Exception as e: print('FAIL',p,getattr(e,'problem',''))
"
```

Expect 11/11 `OK` (currently 7/11). Then confirm by inspection:
`identity_selector_fields` contains no `*`; `default_for_odp_measurement` is gone;
`odp.schema.yaml` is 0.5.0 and its lookup rule names `identity_selectors`; the producer-match
rule appears in the PolicyOpinion contract; `policy_example_read_odp.yaml`'s `context_selector`
contains `state`.
