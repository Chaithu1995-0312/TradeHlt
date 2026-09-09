# Gitignore Schema v1

```text
CH-gitignore-schema-v1
2026-09-03
DOCUMENTATION_ONLY
```

| Field | Value |
|---|---|
| Status | **ACTIVE** (workspace law for git; not a layer closure) |
| Lane | governance / workspace hygiene |
| Authority | Git occupancy vs identity. No G001. No live spine. |
| Does not | Put OHLCV, models, logs, or results into git |
| Companion | [`PHYSICAL_STORAGE_ARCHITECTURE.md`](PHYSICAL_STORAGE_ARCHITECTURE.md) §2.3 Class C · [`CANONICAL_LAYER_IDENTITY_CONTRACT.md`](CANONICAL_LAYER_IDENTITY_CONTRACT.md) `RECOMPUTE != RECOVER` |

This document answers one question:

> **What may git carry, and what must stay a local blob named only by a tracked hash?**

It does **not** declare any existing `data/` / `logs/` / `results/` / `models/` file `PRESERVED`. Untracked is not repository-identity ([`PHYSICAL_STORAGE_ARCHITECTURE.md`](PHYSICAL_STORAGE_ARCHITECTURE.md) §1). Class C bindings make a blob *identifiable*; they do not put the blob in git.

---

## 0. The law this schema operationalizes

`RECOMPUTE != RECOVER` ([`goal.md`](../architecture/goal.md) §3.8):

> Rebuilding a layer from upstream with current code produces a *new* object, not the historical one.

A clone that only has HEAD code cannot recover L0–L5 occupancy. It can recover **identity names**: dataset hashes, declaration snapshots small enough to version, measurement-contract evidence that is not occupancy, and findings.

| Action | What it is |
|---|---|
| `git clone` then run the pipeline on a CSV | **RECOMPUTE** — new L1/L2/L3 unless every child PK was stored and matched |
| Load Class B records whose Class A bytes hash-match a Class C binding | **RECOVER** |
| Commit `data/mt5/XAUUSD_M15.csv` | **forbidden this schema** — occupancy in git, not identity |
| Commit `docs/governance/datasets/XAUUSD_MT5_PHASE1_20260521.json` (`sha256=4d73f5ce…`) | **TRACKED_BINDING** — the clone knows which bytes are the corpus |

INV-050…053 named the gap: the OHLC → Feature → CRTState → Geometry → Outcome chain lived only on the local filesystem. The Identity Store (INV-040) made preservation *legal*. This schema makes the git boundary *mechanical*. It does not fill the store.

---

## 1. Classes (closed vocabulary)

Every path is exactly one class. Mixing occupancy into a tracked class is a schema violation.

| Class | Git | What it is | What it is not |
|---|---|---|---|
| **TRACKED_CODE** | tracked | Importable source, tests, scripts, production config | A candle, a model weight, a log line |
| **TRACKED_MEANING** | tracked | Ontology, findings, contracts, topic docs, this schema | Occupancy of any L0–L5 layer |
| **TRACKED_BINDING** | tracked | Class C: PK → content hash → authority status. Dataset Identity records. Sealed `MC-*` evidence under `docs/research-readiness/` | The bytes the hash is over |
| **LOCAL_BLOB** | ignored | Corpus bytes (INV-050). `data/` | Dataset Identity; `FEATURE_ORDER_HASH` snapshots in git |
| **LOCAL_MODEL** | ignored | Serialized inference artifacts (INV-051). `models/` | `active_models.yaml`; zone-manifest *pointers* in docs |
| **LOCAL_RUN** | ignored | Backtest / tuner / validation / scratch reports (INV-052). `results/`, new `reports/` | A finding; a sealed `MC-*` instance |
| **LOCAL_TELEMETRY** | ignored | Append-only JSONL streams (INV-053). `logs/`, `runtime/exec_telemetry/` | The JSONL *claim catalog* (`CC-*`); envelope *shape* |
| **LOCAL_IDENTITY** | ignored | Identity-store Class A snapshots + Class B record files | Class C under `docs/governance/identity_bindings/` |
| **LOCAL_SECRET** | ignored | Credentials | Config knobs |
| **LOCAL_CACHE** | ignored | `__pycache__/`, `venv/`, generated `context/` | Hand-authored docs |
| **MIXED_RESIDUE** | named, not silently rewritten | Already-tracked files that sit inside an ignore rule | A grant to add more of the same |

`.gitignore` section headers **must** use these class names. `tests/test_gitignore_schema.py` pins that.

---

## 2. Path table (clone contract)

| Path | Class | Clone gets it? | How a clone identifies the missing blob |
|---|---|---|---|
| `src/` `scripts/` `tests/` `configs/` | TRACKED_CODE | yes | — |
| `docs/` (except generated scratch) | TRACKED_MEANING | yes | — |
| `docs/governance/datasets/` | TRACKED_BINDING | yes | `canonical_artifact.sha256` |
| `docs/governance/dataset_identity_registry.json` | TRACKED_BINDING | yes | dataset_id → record |
| `docs/governance/identity_bindings/` | TRACKED_BINDING | yes (dir exists; ledgers still empty) | Class C JSONL when written |
| `docs/governance/xauusd_m15_phase1_frozen_candidate.json` | TRACKED_BINDING | yes | `content_hash_sha256` |
| `docs/research-readiness/` | TRACKED_BINDING | yes | sealed `MC-*` evidence; **not** `results/` |
| `configs/research/measurement_result_log.jsonl` | TRACKED_BINDING | yes | append-only measurement audit |
| `data/` | LOCAL_BLOB | **no** (README + `.gitkeep` only) | Dataset Identity / frozen-candidate hash |
| `models/` | LOCAL_MODEL | **no** for *new* files | `active_models.yaml` path + registry; **MIXED_RESIDUE** below |
| `results/` | LOCAL_RUN | **no** (README + `.gitkeep` only) | `docs/research-readiness/` or a finding's tracked Evidence |
| `logs/` | LOCAL_TELEMETRY | **no** (README + `.gitkeep` only) | `jsonl_claim_catalog.yaml` says what a stream *may* prove; it does not ship the stream |
| `reports/` (new files) | LOCAL_RUN | **no** | Durable write-up belongs in `docs/analysis/` |
| `runtime/exec_telemetry/` | LOCAL_TELEMETRY | **no** | recapture via `--exec-log` |
| `objects/` `records/` `identity_store/` | LOCAL_IDENTITY | **no** | Class C hash in `identity_bindings/` |
| `.env` | LOCAL_SECRET | **no** | never |
| `venv/` `__pycache__/` `context/` | LOCAL_CACHE | **no** | regenerate |

`exec_telemetry/` at repo root is **TRACKED_CODE** (Python package). `runtime/exec_telemetry/` is **LOCAL_TELEMETRY**. Same noun, two classes — do not collapse.

---

## 3. MIXED_RESIDUE (do not silently untrack)

Ignore rules do not untrack files already in the index. Measured 2026-09-03:

| Tree | Ignore rule | Tracked files | This turn |
|---|---|---:|---|
| `data/` | yes | **0** | leave |
| `logs/` | yes | **0** | leave |
| `results/` | yes | **0** | leave |
| `models/` | yes (`models/` since before this schema) | **32** | **MIXED_RESIDUE** — do not `git add` more; do not `git rm --cached` without a separate authorization (clone today still carries those 32) |
| `reports/` | **was not ignored**; 126 tracked + new untracked | 126 | new files ignored going forward; tracked 126 stay until a separate untrack/move-to-`docs/analysis/` pass |

Untracking `models/` would drop `zone_registry.json` / `rr_model.json` from a fresh clone. That is a runtime-resolution change, not a gitignore-schema change. Out of scope here.

---

## 4. What a fresh clone can and cannot do

**Can**

- Load `ACTIVE_VERSION`, ontology, CRT identity YAML, Dataset Identity records.
- Know the XAUUSD M15 frozen candidate is `data/mt5/XAUUSD_M15.csv` at `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56`.
- Read sealed `MC-*` metrics under `docs/research-readiness/` (those are bindings + diagnostic numbers, not L0–L5 occupancy).
- Run tests that skip when the gitignored corpus is absent.

**Cannot**

- Recover L0 bars, L1 vectors, L3 occupancy, or L5 outcomes from git.
- Fold `logs/crt_transitions.jsonl` (also IDENTITY_INCOMPLETE: no RESET).
- Treat “re-run HEAD on whatever CSV is on disk” as recovery.

Tests that need the corpus already `skipif` when it is absent (`tests/research/test_xauusd_corpus_certification.py` and siblings). That is the correct clone behavior.

---

## 5. Workspace sync (what “sync” means)

| Sync | Mechanism | Not |
|---|---|---|
| Meaning / identity names | `git pull` of TRACKED_* | Syncing `data/` |
| Corpus bytes | copy the file whose sha256 matches the Dataset Identity record | “any `XAUUSD_M15.csv`” |
| Identity occupancy | copy Class A/B files named in Class C, then Identity Check | recompute from OHLC |
| Telemetry | recapture; or copy streams as *unidentified* occupancy | claiming a copied `logs/` is the same series |

Two machines are synced on identity when their Class C hashes match. They are synced on occupancy only when the named blobs are present **and** Identity Check returns `PRESERVED`.

---

## 6. Rules for future writes

1. **Never** add paths under `data/`, `logs/`, `results/`, `models/` (except the README / `.gitkeep` exceptions), or `runtime/exec_telemetry/`.
2. **Never** cite occupancy inside those trees as finding `Evidence:` — the findings gate reads `git ls-files` (`tests/test_current_findings.py`; F-071).
3. Sealed measurement artifacts go to `docs/research-readiness/<family>/`, not `results/`.
4. Class C ledgers go to `docs/governance/identity_bindings/`. Class A/B files stay LOCAL_IDENTITY.
5. Durable analysis goes to `docs/analysis/`. `reports/` is LOCAL_RUN for *new* files.
6. Adding a new ignored tree requires a new row in §2 **and** a `.gitignore` section that names the class. The pin test fails if a class header disappears.
7. Untracking MIXED_RESIDUE is a separate authorized change. It is not implied by this schema.

---

## 7. Enforcement

| Check | What it pins |
|---|---|
| `tests/test_gitignore_schema.py` | class headers present; LOCAL paths ignored (`git check-ignore --no-index`); TRACKED_BINDING paths not ignored; README exceptions visible |
| `tests/test_current_findings.py` | Evidence paths resolve from the git index, not the filesystem |
| `tests/research/test_sujan_crt_contract.py` | `MC-*` evidence must not be written into a gitignored tree |

No src or script change. No production-behavior change.

---

## 8. Authority footer

- **Grants:** a closed classification of git occupancy vs identity; a clone contract; ignore-rule headers that match the classes.
- **Does not grant:** committing INV-050…053 lineage; untracking MIXED_RESIDUE; declaring any local blob `PRESERVED`; G001; live rail.
- **Does not reopen:** layer identity, storage preservation, or physical storage closures.
- **Does not claim:** the Identity Store is populated, or that a fresh clone can replay findings' occupancy.
