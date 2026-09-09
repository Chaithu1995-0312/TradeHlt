# Generate the XAUUSD oracle parquet artifacts

## Context

The user remembered a `labels.parquet` / `bar_matrix.parquet` in the repo. Investigation showed
**neither ever existed**:

- `pyarrow` is declared only as an *optional* extra under `mt5_analytics`
  (`pyproject.toml:22`) and is installed in **neither** venv (`venv/` py3.12, `.venv/` py3.14).
- `scripts/research/build_bar_matrix.py:333` attempts `to_parquet` inside a `try`, fails, and
  honestly records `parquet_written: false` + `parquet_skipped_reason` in its manifest. Console
  output correctly prints the **CSV** path.
- `src/research/oracle/labeler.py:330` has **no** `to_parquet` call at all — structurally
  incapable of producing `labels.parquet`.
- Git history contains zero parquet adds or deletes; F-086's evidence line correctly cites
  `labels.csv … sha256 3027ea97…`.

The `.parquet` filename existed only in the prose of a prior chat summary. Every authoritative
surface (code, console, manifest, finding) said CSV and was right.

**Goal:** honor the already-declared `pyarrow` dependency so both parquet artifacts actually
exist as convenience siblings — **without disturbing the CSVs that F-086/F-087/F-088 cite by
hash**. CSV stays canonical.

## Non-negotiable constraint

These two hashes are cited evidence and must be **byte-identical** when this is done:

| artifact | sha256 |
|---|---|
| `results/research/oracle_labels/XAUUSD_M15/labels.csv` | `3027ea973b4a7a2bd71c2ed615a23cb837ff9e319e44af3d1e6d2b33f11b9282` |
| `results/research/bar_matrix/XAUUSD_M15/bar_matrix.csv` | `e409d8333aec585633cf8ebab107eaceeeb0b65b21455ea782efd4e426de394c` |

`labels.csv`'s hash matches the `3027ea97…` cited in F-086 and F-088 exactly. The design below
regenerates into a **scratch dir** and promotes only the `.parquet` files, so the canonical CSVs
are never overwritten — byte-identity holds by construction, not by luck.

## Steps

### 1. Environment
Install the already-declared optional dep into the canonical venv (`venv/`, py3.12 — the one
`project_feature_lineage_candle_math.md` flags; `.venv/` py3.14 is also in use, install there too
if the user runs it):

```bash
venv/Scripts/python.exe -m pip install pyarrow
```

No `pyproject.toml` change — `pyarrow` is already declared. It stays optional; the `try/except`
guards mean nothing breaks if it's absent.

### 2. Add the parquet write to `labeler.py` (additive)
In `src/research/oracle/labeler.py`, immediately after `labels.to_csv(...)` (`:330`), mirror the
existing block at `scripts/research/build_bar_matrix.py:332-337` **verbatim in shape** — same
`try/except`, same `parquet_written` / `parquet_skipped_reason` manifest keys, same "CSV is
canonical" comment rationale. Add the two keys to the `manifest` dict built at `:335+`.

CSV write stays first and unconditional; parquet cannot affect it.

### 3. Regenerate into scratch, then verify
Scratch dir: `C:\Users\Hi\AppData\Local\Temp\claude\D--Tradelatest\<session>\scratchpad\parquet_run\`

```bash
venv/Scripts/python.exe scripts/research/build_bar_matrix.py --instrument XAUUSD --timeframe M15 --out-dir <scratch>/bar_matrix
venv/Scripts/python.exe -m research.oracle.labeler --instrument XAUUSD --timeframe M15 --matrix-dir <scratch>/bar_matrix --out-dir <scratch>/labels
```

`build_bar_matrix` takes ~339s; the labeler ~11s.

Then `sha256sum` both scratch CSVs against the table above.

- **Both match** → proceed to step 4. This also *proves determinism* of the pipeline, a
  worthwhile side-result.
- **Either differs** → **STOP. Do not touch the canonical dir.** A non-reproducing CSV is a far
  more serious result than a missing parquet (it would mean cited evidence can't be regenerated),
  and it gets reported, not worked around. Fallback for delivering the parquet anyway: convert
  the *existing canonical* CSV directly (`pd.read_csv(...).to_parquet(...)`), which guarantees the
  parquet matches the cited artifact.

### 4. Promote parquet only
Copy `bar_matrix.parquet` and `labels.parquet` from scratch into their canonical dirs. Update the
two canonical `manifest.json` files to set `parquet_written: true` and drop
`parquet_skipped_reason`. **Canonical CSVs are not touched.**

### 5. Fix the now-stale comment (§6.2, same turn)
`scripts/research/build_bar_matrix.py:326` asserts *"no parquet engine is installed in this
environment"* — false once step 1 lands. Rewrite to state that parquet is an optional convenience
and CSV remains canonical. Unambiguous `DOC_DRIFT`, auto-fix tier.

## Verification

1. **Byte-identity (the load-bearing check)** — re-`sha256sum` both canonical CSVs after
   promotion; must still equal the table above.
2. **Round-trip** — read each parquet back and compare against its CSV: identical shape, column
   names, and values (dtype-aware; parquet preserves types the CSV round-trip widens).
3. **Floors** — `venv/Scripts/python.exe -m pytest tests/research/test_oracle_labeler.py tests/research/test_multi_tp_walk_parity.py` (31 tests, expect all green).
4. **Manifests** — both report `parquet_written: true` with no `parquet_skipped_reason`.

## Governance notes

- **No finding is created or changed.** No conclusion moves; F-086's `labels.csv` citation stays
  true. Adding a sibling artifact grants no authority (§6.5).
- **No SITS re-registration.** `labeler.py` lives under `src/`, not `scripts/**`; the three
  scripts (`SCR-418/419/420`) are already registered at `EXTRACTED_TO_SRC`.
- **Untracked output.** `results/` is gitignored (`.gitignore:5`), so the parquet artifacts are
  local-only. Only `labeler.py` and the `build_bar_matrix.py` comment are tracked changes.
- **Hash-neutral.** No `configs/production/*` edit, no `params` change, no rehash.
- §6 SESSION LOG entry appended to `assistant_project.md` on completion.
