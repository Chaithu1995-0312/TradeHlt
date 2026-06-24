# Repository Truth Audit — one-time pass (Truth Maintenance Doctrine §6.2)

## Context

You asked for a **one-time truth audit**: apply the Repository Truth Maintenance Doctrine
(CLAUDE.md §6.2–§6.4) *now* — scan code / docs / findings / tests for current divergence,
surface conflicts (no new tooling), classify drift, and recommend fixes for approval.

The doctrine prose is already done and non-fragmented (it lives only in CLAUDE.md §6.2–§6.4;
all other docs are pointers). **Mechanical enforcement is ~80% built** (4 pytest gates +
deterministic generators). This audit ran those gates and cross-checked the Tier-0 runtime
truth. It found **3 live divergences** — 2 need a human decision (Rule 3/7), 1 is a safe
mechanical fix.

Evidence gathered this session:
- `python -m pytest tests/test_current_findings.py test_doc_citations.py test_topic_docs.py test_cli_matrix_sync.py` → **3 failed / 10 passed**.
- `configs/production/ACTIVE_VERSION` = `v2_multi_2026_04 - deepdeektry` (read directly).
- `git status` staged-rename inspection + `grep` of real symbol line numbers.

---

## Conflict Register

### TruthConflict #1 — Tier-0 ACTIVE_VERSION is a non-canonical experimental config  **[HIGH · USER DECISION]**

| Source | Authority | Claim |
|---|---|---|
| `configs/production/ACTIVE_VERSION` (file) | **Tier 0** (only runtime truth) | `v2_multi_2026_04 - deepdeektry` |
| CLAUDE.md F-016 + §4.0 | Tier 2/3 | `v2_multi_2026_04` |
| memory `project_trd_m6_downstream` | Tier 4 | `v4_multi_2026_06` |

- **Evidence:** active file is `configs/production/v2_multi_2026_04 - deepdeektry.json` (spaces in
  name, currently git-`MM` = staged+unstaged modifications). A clean `v2_multi_2026_04.json` also
  exists. Three authorities name three different versions.
- **Impact:** the runtime loads an **experimental "deepdeektry" variant** as production. Every
  finding/doc describing live behavior on `patch` may be describing the wrong config. This is the
  most severe class — Tier-0 divergence at the single source of runtime truth.
- **Classification:** `AMBIGUOUS` → escalate. The doctrine forbids silently editing either side.
- **Recommendation (needs your call):**
  - **(a)** If `deepdeektry` is *intentionally* live → I update F-016 + CLAUDE.md §4.0 + the
    `project_trd_m6_downstream` / dataset-integrity memories to name it, and reconcile the v4 claim.
  - **(b)** If it is an accidental promotion → restore `ACTIVE_VERSION` to `v2_multi_2026_04`
    (the canonical file F-016 names). *Config/runtime change — your approval required.*

### TruthConflict #2 — Staged docs reorg not reflected in the working tree  **[MED-HIGH · USER DECISION]**

- **State:** ~22 docs are **staged-renamed** (`RD`) uppercase→lowercase-kebab into
  `docs/reference/`, `docs/architecture/`, `docs/analysis/`, `docs/handover/` (e.g.
  `docs/ARCHITECTURE.md` → `docs/reference/architecture.md`,
  `docs/CLI_MATRIX.md` → `docs/reference/cli-matrix.md`). In the **working tree** the new paths
  are absent and the **old uppercase files still exist**. The rename is staged but reverted on disk.
- **Impact:**
  - `test_cli_matrix_sync.py` **fails** — it expects `docs/reference/cli-matrix.md`; the file is
    still at `docs/CLI_MATRIX.md`.
  - CLAUDE.md §2 companion table + §3.4/§6.2 link the **old** uppercase paths. They resolve *today*
    (old files present) but will break the moment the staged migration lands.
  - Two parallel path systems = exactly the doc-entropy the doctrine targets.
- **Classification:** `AMBIGUOUS` (which path system wins?) → escalate.
- **Recommendation (needs your call):** either **complete** the migration (move files to the new
  paths on disk, repoint CLAUDE.md/README/test inputs) or **abort** the staged renames
  (`git restore --staged docs/`). Until decided, the cli-matrix test stays red.

### TruthConflict #3 — Stale `path:line · Symbol` doc citations (code moved)  **[LOW-MED · SAFE FIX]**

`test_doc_citations.py` (±30-line window) flags 6, plus 1 the test can't see:

| Doc citation | Cited line | Actual line(s) | Verdict |
|---|---|---|---|
| `docs/current-findings.md:98` · `bitnet_main_score` | 1805 | 1749–1757 | DOC_DRIFT → bump to 1749 |
| `docs/architecture/entry-exit-map.md:29,63` · `process` | 590 | 523–555 | DOC_DRIFT → bump to 523 |
| `docs/architecture/entry-exit-map.md:46` · `_write_to_registry` | 583 | 288–499 | **verify** (symbol may be renamed) |
| `docs/topics/crt-spine.md:20` · `VALID_TRANSITIONS` | 1099 | 1025 | DOC_DRIFT → bump to 1025 |
| `docs/topics/ai-automation-agent.md:21` · `main` (`cli.py`) | 49 | agent/ vs research/ | AMBIGUOUS path → qualify to `src/agent/cli.py` |
| CLAUDE.md §4 (line 121) · `VALID_TRANSITIONS` `crt_engine_v2.py:981` | 981 | 1025 | **test-invisible** (single-form cite) → fix to 1025 |

- **Classification:** `DOC_DRIFT` (code is authoritative; line numbers are stale hints). All
  doc-only, additive, reversible.
- **Recommendation (auto-fixable on approval):** correct the 6 line numbers + disambiguate the
  `cli.py` path. The CLAUDE.md §4 `:981` cite is the same `VALID_TRANSITIONS` drift the topic doc
  has — fix both to keep them coherent. Re-run `gen_citation_map.py` if desired (regenerates the
  reverse map). Note CLAUDE.md §4 also says `crt_engine_v2.py:981` in the bullet — same fix.

---

## Recommended remediation (in order)

1. **#3 (mechanical, low-risk)** — bump the 6 citation lines + the CLAUDE.md §4 `:981`→`:1025`,
   qualify `cli.py`→`src/agent/cli.py`. Then `pytest tests/test_doc_citations.py` goes green.
   *I can do this immediately on approval — no judgment needed.*
2. **#1 (Tier-0)** — you pick (a) adopt deepdeektry in docs/memory or (b) restore canonical
   `ACTIVE_VERSION`. I execute the chosen side and sync all 3 authorities.
3. **#2 (docs reorg)** — you pick complete-vs-abort. I then fix `test_cli_matrix_sync` inputs +
   CLAUDE.md links to match the winning path system.

Conflicts #1 and #2 are **surfaced, not resolved** — per Doctrine Rule 3 (never silently resolve)
and Rule 7 (human confirmation when authorities disagree).

## What this audit did NOT do
- No new tooling (`ConflictReport`/`TruthConflict` classes) — out of scope per your choice.
- No semantic re-validation of findings (whether F-001…F-017 are still *true*) — only structural
  + citation + Tier-0 checks. Findings staleness is already gated by `test_current_findings.py`
  (passed: no finding is past its Revalidate-by).

## Verification
- After #3: `python -m pytest tests/test_doc_citations.py -q` → green.
- After #2: `python -m pytest tests/test_cli_matrix_sync.py -q` → green; CLAUDE.md links resolve.
- After #1: `python -c "from src.config_layer.production_config import get_active_version; print(get_active_version())"` matches the agreed version; F-016 + memory restated.
- Full gate: `python -m pytest tests/test_current_findings.py tests/test_doc_citations.py tests/test_topic_docs.py tests/test_cli_matrix_sync.py -q` → 13 passed.

> SESSION LOG note: §6 mandate is deferred — plan mode forbids editing `assistant_project.md`.
> The log block is shown in chat this turn and will be persisted once plan mode exits.
