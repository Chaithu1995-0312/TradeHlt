# Shadow Provenance Contract V1

```json
{
  "schema_id": "SHADOW_PROVENANCE_CONTRACT_V1",
  "generated_at_utc": "2026-07-14T10:26:18.740565+00:00",
  "required_fields_per_bar": {
    "schema_version": "MARKET_STATE_VECTOR_SCHEMA_V1 version",
    "config_id": "hash or version of msip_shadow config",
    "repository_commit": "git sha when known",
    "corpus_path": "if batch",
    "corpus_sha256": "if batch",
    "feature_schema_hash": "1ba02abbafdd0786831181677de547c1",
    "feature_order_hash": "235553310100a340",
    "dimension_sources": "map dimension_id \u2192 list of {feature, fm_id?, value_hash_or_value}",
    "parity_audit_refs": "list of audit artifact IDs used",
    "crt_observation": "optional {crt_state, bar_index}"
  },
  "completeness_rule": "provenance incomplete \u21d2 bar status PARTIAL; cannot promote to any authority",
  "retention": "append-only JSONL; no rewrite of historical shadow runs"
}
```
