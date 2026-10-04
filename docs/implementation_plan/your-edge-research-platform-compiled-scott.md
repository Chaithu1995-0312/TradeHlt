# ERP — Shape documentation hierarchy: add the Level-2 explanation layer

## Context
The owner wants shape knowledge organized as a **4-level read-order hierarchy** so any coding LLM knows
where to look, with a strict **authority gradient** — mathematics is authoritative; explanations and
stories are descriptive and carry no authority (never invert into a math source):

```
Level 1  SHAPE_LIBRARY.md            what mathematically exists   (AUTHORITATIVE, generated)
Level 2  shape_explanations.md  NEW  what each shape means to a human (NO authority)
Level 3  market_story_ontology.yaml  closest story family          (labels, no authority)
Level 4  REPORT.md                   why it matters / governance   (generated)
```

The gap is **Level 2** — there is no LLM→human explanation layer today. This increment creates it for the
only `LIBRARY_OK` unit (IC-003B Arm S N=4, 6 shapes `S_N4_k6_s00..s05`) and wires the read-order so it is
discoverable, **without letting explanations acquire authority**. Doc-only; research-only; no code path,
config, gate, or `ACTIVE_VERSION` change (§6.5).

## Governance decisions baked into the design (the reason this is safe)
1. **Authoritative source is `results/research/ic_003b/SHAPE_LIBRARY.md`** (the owner's note said `ic_003/`,
   but IC-003 is the *archived LIBRARY_FAIL* run with **no** shapes; the real shapes are in **`ic_003b/`**).
   Note this correction in the file header.
2. **Level 1 & 4 are GENERATED** — never hand-edit `SHAPE_LIBRARY.md` / `REPORT.md` (re-run clobbers them).
   All hierarchy pointers live in **hand-maintained** docs (the new file + the boundary registry).
3. **Anti-hallucination (H1/H2):** every shape's "Math" block is **grounded in real numbers** — the
   cluster's `medoid_trade_id`'s actual 38 entry features (from the trace corpus) + `outcome_mix_oos` +
   `tp_rate_oos` from `report.json`. No feature adjective is written unless the medoid/centroid numbers
   support it. The "LLM explanation" is an explicit human *gloss on those real numbers*, contributor-tagged.
4. **Robustness caveat with teeth (E-001):** these 6 shapes are the *only* OK unit and are **marginal**
   (G2 0.0561), **seed-fragile** (k\* unstable 4/6/12), and **near-noise** (silhouette ≈0.06, ~10-20%
   variance captured); Arm C reads as a weak continuum, not discrete archetypes. The file header states this
   prominently and every shape carries a `stability: LOW` field, so no reader mistakes a gloss for an
   archetype.

## Files
- **NEW `docs/research-readiness/shape_explanations.md`** (hand-maintained, Level 2). Structure:
  - **Header:** the 4-level read-order diagram; the AUTHORITY BOUNDARY (math authoritative; this file grants
    no authority — §6.5); the ROBUSTNESS CAVEAT (near-noise / seed-fragile / weak-continuum, cite the
    IC-003B robustness block); SOURCE run = `results/research/ic_003b/` verdict `IC003B_PARTIAL`.
  - **Per-shape (×6), run-sectioned `## IC-003B — Arm S N=4`:** `shape_id` · Math (medoid trade + its real
    entry features + `outcome_mix_oos` + `tp_rate_oos` + n_is/n_oos) · Representative trades
    (`representative_trade_ids_oos`) · **LLM explanation** (Claude-seeded, `contributor: Claude` tag; a
    factual gloss on the medoid's numbers) · Research note (`Descriptive only. Not predictive.` +
    `stability: LOW`).
  - **Contributor convention:** other models (GPT/Gemini/Grok) append their own `contributor:`-tagged
    explanation under a shape — never overwrite; disagreement is kept, not resolved into false consensus.
- **MODIFY `docs/research-readiness/erp-information-class-boundary.{json,md}`** — add a thin
  `shape_documentation_hierarchy` pointer (the 4 levels + the "no authority below Level 1" rule) under the
  IC-003B entry, so the ERP machine index carries the read-order. Bump doc-control to v1.3.
- **NEW (optional, recommended) `tests/research/test_shape_explanations.py`** — light floor: file exists;
  carries the no-authority + robustness caveat phrases; every `shape_id` it documents ⊆ the real ids in
  `results/research/ic_003b/report.json` (anti-drift / anti-hallucination). Skips if the results artifact is
  absent (gitignored). Mirrors `test_information_class_registry.py` discipline.
- **MODIFY `assistant_project.md`** — §6 SESSION LOG entry. **NEW memory** update (extend
  `project_ic003b_sequence_geometry.md` with the hierarchy, no new memory file).

## Reuse (do not reinvent)
- Grounding data: `results/research/ic_003b/report.json` (`arm_S["4"].shapes[*]`: `medoid_trade_id`,
  `outcome_mix_oos`, `tp_rate_oos`, `representative_trade_ids_oos`).
- Medoid feature lookup: the trace corpus `results/research/trace_corpus/xauusd/` (traces keyed by
  `trade_id` like `mean_reversion_010537`), same join the corpus builder used.
- Caveat text: the IC-003B `robustness` block already in the boundary registry (this session).
- Floor pattern: `tests/research/test_information_class_registry.py`.

## Explicitly NOT in this increment
No edit to generated `SHAPE_LIBRARY.md` / `REPORT.md`; no story-ontology change (Level 3 mapping is a later,
separate step and needs its own grant); no new engine / config / gate / `ACTIVE_VERSION` change; no
promotion — the explanation + story layers grant **no** authority; explaining a shape ≠ endorsing it.

## Verification
- `python -c "import json; json.load(open('.../erp-information-class-boundary.json'))"` valid.
- `pytest tests/research/test_information_class_registry.py tests/research/test_shape_explanations.py -q` green.
- Grep confirms `shape_explanations.md` documents exactly the 6 real `S_N4_k6_s*` ids, carries the
  no-authority + `stability: LOW` caveats, and its Math blocks cite real medoid trade ids present in the
  corpus (no invented feature adjectives).
