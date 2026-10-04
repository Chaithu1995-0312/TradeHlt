# SEM-034 — bulk-candle proxy selector for SEM-033

## Context

Phase 1 shipped on 2026-08-28: `src/research/sujan_manipulation/` (SEM-033) detects a later
candle that purges an externally supplied parent range and closes back fully inside it. It
deliberately ships **no selector** — `BULK_CANDLE_SELECTOR = "UNRESOLVED"`, registered as UNK-007 —
so it cannot run against XAUUSD without a hand-supplied parent list. That list never arrived.

You have now ruled that the repository should find the parents itself. That resolves UNK-007 with
a **mechanical proxy**, which the identity charter permits only when the human bridge approves it,
it is recorded, and it stays linked to the visual original (`SUJAN_CRT_IDENTITY_EXTRACTION_SYSTEM.md`
Primary Rule). The intended outcome is a shortlist you eyeball and confirm, producing both a
runnable parents file **and** the hand-labelled ground truth UNK-007's own `resolution_metric` asks
for.

**Rulings taken during planning:**

| Decision | Ruling |
|---|---|
| Authority | Repo decides — proxy approved, recorded as UNVALIDATED |
| Instrument | Magnitude shortlist, then visual confirmation |
| Size reading | Range-ranked **and** body-ranked, as two separate un-merged lists |
| Comparison | Top-N over the whole corpus |
| N | **50 per list** |
| Source | CSV as source, Parquet as cross-check |
| UNK-007 | Refined in place, stays **open** |

### One correction carried forward

I earlier said Parquet couldn't help because "bulk isn't a column." The dominance judgment isn't,
but the size inputs are: `clean_labels.parquet` and `opportunities.parquet` carry
`features.candle_range`, `features.body_size`, `features.body_ratio`, verified MATCH_EXACT against
`candle_math`. That is why Parquet earns a real role below.

**Why CSV is the source and not Parquet:** `data/mt5/XAUUSD_M15.csv` has **no Parquet twin** —
nothing exists under `data/` at all. The four XAUUSD Parquet corpora live in `logs/` and `results/`,
both gitignored (the Sujan contract forbids citing evidence inside a gitignored tree); their grain
is 1 row per (bar × direction), 94,332 rows = 47,166 timestamps × 2 sides, **109 bars short** of the
CSV's 47,275; and `clean_labels` carries `y_R_net` / `y_tp1` / `y_mfe_r` in the same table, which
would put forward outcomes in the founding's read path.

---

## What gets built

### 1. `src/research/sujan_manipulation/bulk_proxy.py` — the approved proxy

Two separate `ParentSelector` implementations conforming to the existing Protocol in
[`parent.py`](src/research/sujan_manipulation/parent.py). They are **never merged** — that is what
preserves the recorded "often large-bodied" vs "may also be wick-dominant" ambiguity.

```python
from features.candle_math import body_size, candle_range   # FM-001, FM-002

FROZEN_TOP_N = 50          # human bridge, drift log Record 6. Not a default — a recorded value.
PROXY_ID = "SEM-034"
PROXY_STATUS = "UNVALIDATED"

class TopNRangeSelector:   # ranks by candle_range(high, low)
class TopNBodySelector:    # ranks by body_size(open, close)
```

- `n` is a **required** constructor argument — no silent defaults (§6.5 hard rule). The CLI passes
  `FROZEN_TOP_N` explicitly.
- **No local arithmetic.** Both call `candle_math`; `high - low` written inline would be the exact
  ungoverned-feature-math class `feature_math_lint` exists to catch, and the precedent it already
  pins as debt (`mother_range/geometry.py:104-105` computes range inline and survives only because
  that package sits outside `_SCAN_DIRS`).
- **No new FM-\* id.** Nothing enters the 48-dim vector; this is a selection procedure over already-
  registered quantities, not a new emitted feature.
- Ties broken by ascending bar index, explicitly and under test — a float tie must not make the
  output order depend on sort stability.

### 2. `src/research/sujan_manipulation/parquet_check.py` — the cross-check

Optional `--verify-parquet`. Reads only `decision_ts`, `side`, `features.candle_range`,
`features.body_size` from `clean_labels.parquet` via
[`utils.parquet_store.iter_records`](src/utils/parquet_store.py) with `columns=[...]`, dedupes to
`side == "long"`, and asserts agreement with the CSV-derived values on the intersection.

**Fails closed if `parquet_store.parquet_available()` is False.** `iter_records` silently degrades
to reading the 299 MB JSONL source when pyarrow is missing, and pyarrow is installed **only in the
venvs**, not the bare `python` on PATH. A silent degrade here is precisely the F-079 / F-085 /
F-083 silent-gap class — a skipped check indistinguishable from a passed one.

The ~109 unmatched bars are **expected and reported as a count**, never an error.

### 3. `src/research/sujan_manipulation/label_page.py` — the confirmation page

Emits a self-contained HTML page: one chart window per candidate, the marked candle highlighted,
one frozen question:

> **Is the marked candle a parent bulk candle — visually dominant, defining a range?**
> yes / no / unsure

with `BULK_CANDLE_EVIDENCE` shown verbatim as the reader's only guidance. Selections accumulate
into a textarea you copy out as `confirmed_parents.json`.

Deliberately **not blinded** and deliberately **not** importing
`scripts/analysis/blind_label_sample.py`: that module transitively imports `features.feature_pipeline`,
which is on this package's forbidden-import list, and the bridge needs visible timestamps to produce
a parents file. It is cited as the visual precedent for the page layout and frozen-question pattern,
and the ~50-line SVG renderer is reimplemented in stdlib only. The page is a **curation tool, not a
measurement instrument** — stated on the page itself so nobody later mistakes it for one.

### 4. CLI

`__main__.py` gains a `candidates` mode; the existing detect path is unchanged.

```bash
python -m research.sujan_manipulation candidates --corpus data/mt5/XAUUSD_M15.csv --top-n 50 --out docs/research-readiness/sujan_manipulation/candidates --verify-parquet
```

Artifacts: `candidates_range.jsonl`, `candidates_body.jsonl` (un-merged), `candidates.html`,
`candidates_manifest.json` (corpus sha, top-n, proxy id + UNVALIDATED status, the **overlap count
between the two lists**, parquet cross-check result or `SKIPPED`).

---

## Governance — the truth-sync this ruling forces

UNK-007 currently says *"Do not close this by writing a size heuristic."* I wrote that last turn.
It cannot stand unchanged while code does exactly that.

| Artifact | Change |
|---|---|
| **UNK-007** (`market_ontology.yaml`) | Refined **in place**, stays `knowledge_status: UNKNOWN` / `status: open`, `version: 2`. Drop the now-false prohibition and the "ships NO selector" validation rule; record the APPROVED-UNVALIDATED proxy, link it to SEM-034, and keep the rule that only the recorded proxy may select — any other needs a new freeze. `resolution_metric` unchanged: agreement against your hand-labelled set, which this build finally produces. |
| **SEM-034** (new) | `SUJAN_BULK_CANDLE_PROXY_V1`, `CHARACTERIZED`. A first-class, versioned, replaceable object so a future rule change is a new freeze rather than a retune of the detector. Full 25 fields + `epistemic` block. |
| **SEM-033** | `version: 2`. `dependencies` gains SEM-034; restate the validation rule that previously asserted UNRESOLVED. |
| **Drift log Record 6** | The charter's Review Loop template exactly: `Mechanical proxy? Y` / Proxy / `Approved? Y` / `Linked original: UNK-007` / `Status: UNVALIDATED`, plus the five-field drift record and the frozen N=50. |
| **Object spec §5** | Rewritten — it currently says "ships no selector". |
| **Claim catalog** | Stream entry for `candidates_*.jsonl` + one CAN class `CC-SEM033-PROXY-RANK` ("the proxy ranked this bar top-50 by candle_range") with `CC-SEM033-NOT-SUJAN` forbidden. |
| **Manifest** | New `CH-sujan-bulk-proxy-v1.impact.json`, classes `SEMANTIC_REGISTRY_CHANGE` + `JSONL_CLAIM_SURFACE_CHANGE`. The Phase-1 manifest stays as the record of what already shipped. |
| **SESSION LOG** | `assistant_project.md`, citing Record 6. |

### Tests to change (shipped and currently green)

- `test_bulk_candle_selector_is_unresolved` → asserts `"APPROVED_PROXY_UNVALIDATED"`.
- `test_no_bulk_candle_selector_ships` → `test_the_only_selector_is_the_recorded_proxy`.

New: proxy returns exactly N; the two lists are un-merged and their overlap is reported not folded;
tie-break determinism; `candle_math` is the sole source of the size arithmetic (AST-asserted, no
inline `high - low`); parquet check fails closed without pyarrow; the ~109-bar shortfall is reported
as a count; candidate output carries `economic_claims_allowed: false`.

**Still NOT done:** no `MC-*`, no `F-*`, no `RF-*` row, no G001, no production config, no economic
claim. A candidate is a candidate; ranking 50 candles by size makes no statement about the market.

---

## Verification

```bash
python -m pytest tests/research/test_sujan_manipulation.py -v
```

```bash
python scripts/governance/construction_protocol.py validate-impact docs/governance/build_manifests/CH-sujan-bulk-proxy-v1.impact.json
```

```bash
D:\Tradelatest\venv\Scripts\python.exe -m research.sujan_manipulation candidates --corpus data/mt5/XAUUSD_M15.csv --top-n 50 --out docs/research-readiness/sujan_manipulation/candidates --verify-parquet
```

```bash
python -m pytest tests/test_semantic_registry.py tests/test_jsonl_claim_catalog.py tests/test_jsonl_claim_grounding.py tests/test_feature_lineage.py tests/test_semantic_grounding.py -q
```

```bash
python -m pytest tests/test_feature_math_lint.py -q
```

Acceptance: both candidate lists have exactly 50 rows; the manifest reports their overlap and a
parquet cross-check that either **agrees** or names its disagreements; the labelling page renders
all candidates; and GREEN_FLOOR stays at the **same 10 pre-existing failures** measured yesterday —
no new red.

Then you label, and the confirmed set runs through the unchanged detect path.
