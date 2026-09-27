## STORY-GOV-IDENTITY-001 — Run Identity Governance (EFAP) mandatory identity header

**Id**: `STORY-GOV-IDENTITY-001` · **Area**: LLM workflow governance (Run-Identity / EFAP) · **Status**: IN PROGRESS

### Acceptance criteria (9 = 8 originals + `identity_status`)

A. **Single authority** — one canonical `build_identity()` in `src/governance/run_identity.py`; the
   record is never assembled from local formula math at a call site.
B. **6-field record** — every stamped artifact carries `run_id`, `config_version`, `config_hash`,
   `dataset_hash`, `artifact_timestamp`, `identity_status`.
C. **`identity_status` is first-class** — any missing/unprovable field ⇒ `UNVERIFIED`; nothing less
   than all six self-consistent fields is `VERIFIED`.
D. **UNVERIFIED inherits down** — a derived report built on an UNVERIFIED source is UNVERIFIED.
E. **No backfill recovery** — historic pre-2026-09-16 runs stay UNVERIFIED; no hash is invented
   (RECOMPUTE != RECOVER).
F. **Always-on stamping** — `run_identity.json` plus the summary/report header are written for every
   run that records a `run_id`; row/event `identity_status` carriers are emitted when a record exists.
G. **Join gate denies the weakened cases** — `can_join()` denies UNVERIFIED operands, cross-run, and
   config-drift; same-run verified joins are allowed.
H. **Worker is a sink** — the backtest writer never recomputes status; it stamps the authority's
   record verbatim.
I. **CLI gate** — `python -m governance.run_identity validate-join` exposes the same boolean decision
   with a parseable reason and exit code.

### Verification
- `tests/test_run_identity.py` (14 cases) — units A–I.
- `python scripts/governance/construction_protocol.py validate-impact docs/governance/build_manifests/CH-run-identity-efap.impact.json` → APPROVED.
- Writer end-to-end smoke: `run_identity.json` + summary block + row/event status + report header.