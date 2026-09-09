# models/ — LOCAL_MODEL (INV-051)

Serialized inference artifacts. **New files are not in git.** See
[`docs/governance/GITIGNORE_SCHEMA.md`](../docs/governance/GITIGNORE_SCHEMA.md) §3.

`active_models.yaml` names what the spine intends to load. That registry is
tracked; the weight files are occupancy.

**MIXED_RESIDUE:** some files were committed before the ignore rule. They stay
in the index until a separate untrack authorization. Do not add more.
