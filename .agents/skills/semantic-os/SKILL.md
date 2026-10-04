---
name: semantic-os
description: Use the Semantic OS v2 meaning plane - ground what a trading term or code field means, add or amend a concept contract, map code to concepts, record a divergence, or review src/semantics code against the contracts
---

Full reference: `docs/memory/semantic-os-memory.md` (read it first; this skill is only the procedure).

## A. "What does <trading term / code field> mean here?"

1. Concept: `venv/Scripts/python.exe scripts/governance/query_semantic_os.py --ground --kind CONCEPT --token <id|name|alias>`
2. Code field: `... --ground --kind REPRESENTATION --token <producer:key>`
3. Report the status verbatim. GROUNDED → quote the rule and every divergence. PROPOSED caveat →
   say the rule is not accepted. UNKNOWN / REFUSED / AMBIGUOUS → do not assert a meaning.
4. Never infer meaning from a variable or config-key name, and never use `--kind NOUN` for v2.

## B. Add or amend a concept / mapping

1. Discuss the design with the user before writing anything (definition, layer, parameters and which
   are identity-bearing, inputs, availability, absence, divergences).
2. Edit `configs/formulas/concept_contracts.yaml`; map the code in its producer shard under
   `configs/formulas/representation_registry/` or list it in `unmapped` with a reason.
3. `venv/Scripts/python.exe -c "from semantics.registry import validate_all; print(validate_all())"` → `[]`.
4. If an `unmapped` list shrank, update the pin in `tests/governance/test_representation_registry.py`.
5. Record the decision in the spec (`docs/governance/SEMANTIC_OS_V2_MEANING_PLANE.md`, decisions table or `A-n`).
6. Run the gate (memory doc "Commands") and the floor; compare to the recorded baseline reds.

## C. Code disagrees with a contract

Add `{surface: "<file:line>", current, contract, disposition: RECORDED}` to the concept's
`divergences`. Do not fix the code in the same turn; fixing is a separate user-approved change.
An unsettled question: `decide_in` + `decision`; settled: `decided_in` + `resolution`.

## D. Review src/semantics code

Check, with file:line: authorities called, not copied (I-8); `concept_id` / `parameterization_id` /
`available_at` on every value object, never earlier than an input's bar (I-6); `None` for absence (I-7);
no level-status writes (I-10); thesis has invalidation + stop (I-11); outcomes name walk, basis,
cost model (I-15). Then `validate_all()`, the gate and the floor.

## Repo-specific

- `.Codex/` is gitignored: this skill is local to this clone; the tracked reference is the memory doc.
- Stage explicit paths only; never `git add -A` (concurrent sessions).
