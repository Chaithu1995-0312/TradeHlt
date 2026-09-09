# Class C — tracked identity bindings

This directory is the git-tracked Class C home named by
[`PHYSICAL_STORAGE_ARCHITECTURE.md`](../PHYSICAL_STORAGE_ARCHITECTURE.md) §6
and classified by [`GITIGNORE_SCHEMA.md`](../GITIGNORE_SCHEMA.md).

```text
identity PK
  → content hashes of snapshots and payloads
  → authority status (if any)
```

The bytes need not live in git. The **hash** must. A blob whose hash is not in a
tracked binding is not repository-identity.

| File (when written) | Role |
|---|---|
| `corpora.jsonl` | `(instrument, timeframe)` → `corpus_sha256` + clock_basis + status |
| `snapshots.jsonl` | snapshot_kind → sha256 (feature-order, ontology `states:`, topology) |
| `record_manifests.jsonl` | layer → sha256 of Class B identity-record files |

Until those ledgers exist, Dataset Identity
(`docs/governance/datasets/`, `dataset_identity_registry.json`) is the
standing L0 binding. Do not put Class A objects or Class B record files here.
Those are LOCAL_IDENTITY (`objects/`, `records/`, `identity_store/`).

Empty on purpose. Occupancy is not implied.
