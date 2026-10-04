# Grok parallel window — parquet model binding

> Not auto-loaded. Other windows (DeepSeek cost-model, Claude UNKNOWN) should leave these paths alone.

**Window id:** `parquet-model-binding`  
**Agent:** Grok  
**Date:** 2026-09-16  
**Change:** `CH-model-parquet-binding-docs` (DOCUMENTATION_ONLY)

## This window owns

- `docs/implementation_plan/model-parquet-column-binding.md`
- `docs/research/parquet_evidence_layer.md` section "Model × Parquet name authority"
- `docs/topics/model-intent-and-feature-ownership.md` 2026-09-16 Discussion pointer
- `docs/governance/build_manifests/CH-model-parquet-binding-docs.*.json`
- this file

## This window does not own

- `docs/implementation_plan/cost-model-identity-stamping.md` (DeepSeek)
- ontology UNKNOWN / construction-UNKNOWN work (Claude)
- `query_trace.py` `--model` (later PR, not this landing)
- schema-v6 working-tree residue already dirty at session start

## Status

PR-1 docs landed. `--model` CLI, `RESEARCH_QUERY_BINDING` class, and null-`state__*` fill are **not** started.
