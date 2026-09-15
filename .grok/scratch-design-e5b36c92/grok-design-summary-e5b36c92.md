# Design summary — coding-LLM context pack (revised 2026-09-10)

Design: `C:\Users\Hi\AppData\Local\Temp\grok-Hi\grok-design-doc-e5b36c92.md`
Review: `C:\Users\Hi\AppData\Local\Temp\grok-Hi\grok-design-review-e5b36c92.md` (12/12 addressed)
Lane: measurement / evidence. Run: `run_20260909_202201`. Rebuild not executed.

Pack is a tracked YAML evidence instance (not Context/MC/Finding/ODP). Load first. Trust table = `schema_bridge.surfaces`. `registry_has` is a strict copy of registry `has`; extra facts in `identity_facts`. `variant_id` = `resolver_memory` / `resolver_trendbias` only.

Split refuse: phrase A CREATE-context; phrase B four-arm without pack (coverage pooling). Four-arm ADMIT after load if VALID+unmixed.

pending_dir labels: SHORT 39 / LONG 26 / unlabeled 4. Expire 12:15 is derived (+4 M15), not a stored field.

PRs: PR-1 DOCUMENTATION_ONLY `CH-coding-llm-context-pack-yaml` (YAML + note pointers / DO_NOT_CITE; ack three floors + validate-completion). PR-3 TRACE_OBSERVATION_JOIN `CH-coding-llm-context-pack-has` (has pointer + surfaces pin; TRACE floors will run). Former PR-2 absorbed. No rebuild PR.

Copy Appendix A to `docs/research/phase1_run_20260909_202201_coding_llm_context.yaml`. economic_claims_allowed: false. No IDs minted.
