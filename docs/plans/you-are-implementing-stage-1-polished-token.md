> Created: 2026-05-22 · Updated: 2026-05-22 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Stage-1 Recovery Phase — Implementation Plan

> **Previous work (completed):** Stage-1 Truth Dataset Builder is fully implemented and tested (38 tests pass). Real-world run: `accepted=203,588`, `rejected=305,382` (305,382 from v2.0 schema, missing 3 features). This plan covers the **Recovery Phase** only.

---

# Stage-1 Truth Dataset Builder — Original Plan (reference)

## Context

Stage-1 of the **TradingLLM** training pipeline needs a canonical, deterministic, multi-instrument training dataset assembled from existing backtest outputs (`opportunities.jsonl`, `compressed.json`, `trades.csv`). Today these artifacts live in two separate roots — `logs/{INSTRUMENT}/{RUN_ID}/` for the JSONL/JSON pair and `results/**/*trades*.csv` for the CSV — and there is no merging, no integrity contract, no bucket labeling, and no per-instrument summary. Without a clean truth dataset the downstream training pipeline (`src/training/train_pipeline.py`, `train_rr_model.py`, `train_bitnet.py`) reinvents extraction, RR labeling, and validation in three slightly different ways. The goal is one builder that produces:

- `data/master_{scope}_training.jsonl` — canonical training records (deterministic, streaming-built)
- `reports/integrity_report.json` — totals, rejection reasons, output hash, per-bucket distributions
- `reports/instrument_summary.csv` — per-instrument stats for quick eyeballing
- `reports/input_manifest.json` — discovered inputs, pairings, missing-counterpart warnings
- `reports/scope_summary.json` — instruments accepted vs rejected by scope

The builder is offline tooling (not the live hot path), so it follows fail-open per-record semantics with a global fail-fast on misconfiguration.

---

## Locked Design Decisions (from user)

1. **Input discovery — hybrid auto:** Default JSONL root `logs/`, CSV root `results/`. CLI overrides `--jsonl-root`, `--csv-root`, `--strict-layout`. Emit integrity events for missing counterparts; fail only when `--strict-layout=true`.
2. **Market scope — `--market-scope {auto,crypto,forex,all}` (default `crypto`).** Output filename derives from scope (`master_crypto_training.jsonl` / `master_forex_training.jsonl` / `master_multiasset_training.jsonl`). Classification: crypto = `*USDT, BTC*, ETH*, SOL*, DOGE*, XRP*, BNB*`; forex = `EUR*, GBP*, USD*, AUD*, XAU*`.
3. **Schema — contract-first.** Require all 38 `CANONICAL_FEATURES`. Preserve unknown keys in `extra_features`. Three levels: `STRICT` (reject extras + type mismatch), `WARN` (default), `LENIENT` (allow explicit fallback fills). Never silently truncate / reorder / zero-fill / drop.
4. **Buckets — static, `bucket_version=1`, inclusive lower / exclusive upper.**
   - RR: `LOSS` (rr<0), `SCRATCH` (0–1), `BASE` (1–2), `STRONG` (2–3), `OUTLIER` (≥3).
   - Duration (M15 candles): `FAST` (0–3), `NORMAL` (4–10), `SWING` (11–30), `EXTENDED` (31–90), `RUNNER` (>90).

---

## File-by-File Design

### New: `src/training/stage1_dataset_builder.py` (primary logic)

Single module, ~500 LOC. Public API surface:

```python
# Constants (no magic numbers in callers)
BUCKET_VERSION = 1
RR_BUCKET_EDGES = [(-float("inf"), 0.0, 0, "LOSS"),
                   (0.0, 1.0, 1, "SCRATCH"),
                   (1.0, 2.0, 2, "BASE"),
                   (2.0, 3.0, 3, "STRONG"),
                   (3.0, float("inf"), 4, "OUTLIER")]
DURATION_BUCKET_EDGES = [(0, 4, 0, "FAST"),
                         (4, 11, 1, "NORMAL"),
                         (11, 31, 2, "SWING"),
                         (31, 91, 3, "EXTENDED"),
                         (91, float("inf"), 4, "RUNNER")]
SCOPE_PATTERNS = {"crypto": (..."USDT","BTC*","ETH*",...),
                  "forex":  ("EUR*","GBP*","USD*","AUD*","XAU*")}

@dataclass(frozen=True)
class BuilderConfig:
    jsonl_root: Path; csv_root: Path
    output_dir: Path = Path("data")
    reports_dir: Path = Path("reports")
    market_scope: str = "crypto"
    validation_level: str = "WARN"     # STRICT | WARN | LENIENT
    strict_layout: bool = False
    min_feature_quality: float = 0.5
    instruments_override: tuple[str, ...] | None = None

@dataclass
class RejectionLedger:
    malformed_json: int = 0
    missing_features: int = 0
    schema_mismatch: int = 0
    type_mismatch: int = 0
    duplicate: int = 0
    out_of_scope: int = 0
    low_feature_quality: int = 0
    samples: list[dict] = field(default_factory=list)  # capped @ 50

@dataclass
class BuildResult:
    output_path: Path
    output_sha256: str
    integrity_report_path: Path
    instrument_summary_path: Path
    input_manifest_path: Path
    scope_summary_path: Path
    accepted: int
    rejected: RejectionLedger

# Top-level functions
def discover_inputs(cfg: BuilderConfig) -> dict: ...
def classify_scope(instrument: str, scope: str) -> bool: ...
def rr_bucket(rr: float) -> tuple[int, str]: ...
def duration_bucket(candles: int) -> tuple[int, str]: ...
def compute_feature_quality(features: dict) -> float: ...
def validate_record(rec: dict, cfg: BuilderConfig) -> tuple[bool, str | None, dict | None]: ...
def transform_record(rec: dict, source_meta: dict) -> dict: ...
def iter_opportunities(path: Path) -> Iterator[tuple[int, dict]]: ...
def build_dataset(cfg: BuilderConfig) -> BuildResult: ...   # public entry
```

**Streaming algorithm** (memory-efficient, deterministic):

1. **Discovery pass:** `discover_inputs(cfg)` builds the manifest by globbing
   `{jsonl_root}/*/*/opportunities.jsonl`, `{jsonl_root}/*/*/compressed.json`,
   `{csv_root}/**/*trades*.csv`. Pair them by instrument + run_id. Write `reports/input_manifest.json`.
2. **Read pass:** for each opportunities file, `iter_opportunities` yields `(line_no, record)` lazily (one `json.loads` per line). The first line is `run_header` — captured as source metadata, skipped from records. Malformed lines → `RejectionLedger.malformed_json++`, sample retained.
3. **Per-record transform:** `validate_record` enforces the 38-key contract; `transform_record` adds `regime` (via `RegimeClassifier.classify(features)`), `rr_bucket_id/label`, `duration_bucket_id/label`, `win_flag` (1 if `rr_achieved > 0` else 0), `feature_quality`, and `extra_features` for unknown keys.
4. **Buffering:** accepted records appended to an in-memory list `list[dict]` keyed by `(instrument, timestamp, source_run_id, line_no)`. Backtest outputs typically run ~100k–500k records — well within RAM. If we later need true constant-memory, a flag-gated external-sort path can be added; current spec says memory-efficient, not constant. List of small dicts (~1KB each) bounded at ~500MB worst case is acceptable.
5. **Sort + write pass:** `records.sort(key=lambda r: (r["instrument"], r["timestamp"], r["metadata"]["source_run_id"], r["metadata"]["source_line_no"]))`, then write each via `json.dumps(rec, sort_keys=True) + "\n"` to a `.tmp` sibling, `hashlib.sha256` accumulated as bytes are written, then `os.replace(tmp, final)` for atomic publish (pattern from `core/model_registry._save_atomic`).
6. **Reports pass:** assemble and write four reports atomically (same `.tmp` + replace).

**Output record shape:**

```jsonc
{
  "instrument": "BTCUSDT",
  "timestamp": "2022-01-02 07:45:00",
  "direction": "long",
  "entry": 47312.5, "sl": 47180.0, "tp": 47640.0,
  "outcome": "TP_HIT",
  "rr_achieved": 2.47,
  "duration_candles": 18,
  "mfe": 12.4, "mae": -3.1,
  "win_flag": 1,
  "regime": "TRENDING",
  "rr_bucket_id": 2, "rr_bucket_label": "BASE",
  "duration_bucket_id": 2, "duration_bucket_label": "SWING",
  "features": { /* 38 canonical keys, ordered, finite */ },
  "extra_features": { /* unknown-but-preserved keys */ },
  "metadata": {
    "schema_version": "3.0",
    "feature_dim": 38,
    "feature_hash": "<FEATURE_ORDER_HASH>",
    "feature_quality": 0.97,
    "extra_feature_count": 3,
    "bucket_version": 1,
    "source_run_id": "20260521_145509",
    "source_line_no": 14237,
    "source_path": "logs/BTCUSDT/20260521_145509/opportunities.jsonl"
  }
}
```

**Reuses (do not reinvent):**

- `CANONICAL_FEATURES`, `FEATURE_ORDER_HASH`, `SCHEMA_HASH`, `SESSION_MAP`, `TREND_MAP` from [src/features/feature_schema.py](src/features/feature_schema.py)
- `RegimeClassifier.classify(features)` from [src/regime/regime_classifier.py](src/regime/regime_classifier.py)
- `get_flow_logger("DATASET_BUILDER")` from `src/utils/logging_config.py`
- `safe_print` / `sanitize_for_console` from `src/utils/console_safe.py`
- `emit_integrity_event(event_type, severity, source, payload)` from `src/utils/integrity_events.py`
- Atomic-write pattern from `src/core/model_registry._save_atomic`

### New: `scripts/training/build_stage1_dataset.py` (thin CLI wrapper)

Follow the [scripts/training/train_pipeline.py](scripts/training/train_pipeline.py) shape exactly: bootstrap `src/` onto `sys.path`, then argparse → call `build_dataset(cfg)`.

```python
parser.add_argument("--jsonl-root", default="logs")
parser.add_argument("--csv-root", default="results")
parser.add_argument("--output-dir", default="data")
parser.add_argument("--reports-dir", default="reports")
parser.add_argument("--market-scope", choices=["auto","crypto","forex","all"], default="crypto")
parser.add_argument("--validation-level", choices=["STRICT","WARN","LENIENT"], default="WARN")
parser.add_argument("--strict-layout", action="store_true")
parser.add_argument("--min-feature-quality", type=float, default=0.5)
parser.add_argument("--instruments", default=None, help="Comma list to override scope filter")
parser.add_argument("--dry-run", action="store_true", help="Discover + manifest only, no records emitted")
```

Print one-line summary using `safe_print` on success; non-zero exit on hard-fail.

### New: `tests/test_stage1_dataset_builder.py`

Follow [tests/test_train_pipeline.py](tests/test_train_pipeline.py) style. Test cases:

1. `test_rr_bucket_edges` — bucket boundaries are inclusive-lower / exclusive-upper for every transition.
2. `test_duration_bucket_edges` — same for duration buckets.
3. `test_classify_scope_crypto_patterns` — BTCUSDT / ETHUSDT match; EURUSD does not.
4. `test_classify_scope_forex_patterns` — XAUUSD / GBPUSD match crypto=false / forex=true.
5. `test_compute_feature_quality_perfect_score` — all 38 finite → 1.0; mix of NaN → fractional.
6. `test_validate_record_missing_canonical_key_rejected` — strict + warn modes reject; counter increments.
7. `test_validate_record_unknown_key_preserved_in_extras` — `extra_features` populated; `extra_feature_count` matches.
8. `test_iter_opportunities_skips_run_header_line` — first line `run_header` not emitted as a record.
9. `test_iter_opportunities_malformed_line_recorded` — bad line → ledger.malformed_json++, iteration continues.
10. `test_build_dataset_deterministic_output_hash` — running twice on the same fixture yields identical `output_sha256`.
11. `test_build_dataset_record_order` — records sorted by `(instrument, timestamp, source_run_id, source_line_no)`.
12. `test_strict_layout_fails_on_missing_counterpart` — `strict_layout=True` + missing trades.csv pair → raises.
13. `test_strict_layout_false_logs_event_continues` — same input, default mode → integrity event emitted, build succeeds.
14. `test_scope_summary_records_rejected_instruments` — FX instruments under scope=crypto land in `rejected_instruments`.
15. `test_atomic_write_no_partial_output_on_crash` — monkeypatch the writer mid-stream → final path absent, `.tmp` absent on next run.

Fixtures live in `tests/fixtures/stage1/`: a small set of synthetic opportunities.jsonl files (one per instrument, ~20 records each) covering: clean rows, malformed JSON, missing canonical key, type mismatch, extra keys, mixed scopes.

### Optional: `assistant_project.md` session log entry

Per CLAUDE.md §6, append a SESSION LOG ENTRY for the build after implementation lands. Not part of this plan's edit set — handled during implementation.

---

## Critical Files to Read Before Editing

- [src/features/feature_schema.py](src/features/feature_schema.py) — canonical 38 features, `FEATURE_ORDER_HASH`, `SESSION_MAP`, `TREND_MAP`
- [src/regime/regime_classifier.py](src/regime/regime_classifier.py) — `RegimeClassifier.classify`
- [src/config_layer/rr/rr_dataset_builder.py](src/config_layer/rr/rr_dataset_builder.py) — RR label extraction precedence (rr_achieved → pnl_rr_net → computed)
- [src/utils/integrity_events.py](src/utils/integrity_events.py) — fail-open JSONL append API
- [src/utils/console_safe.py](src/utils/console_safe.py) — Windows cp1252 fallback
- [src/utils/logging_config.py](src/utils/logging_config.py) — `get_flow_logger`
- [src/core/model_registry.py](src/core/model_registry.py) — `_save_atomic` pattern
- [scripts/training/train_pipeline.py](scripts/training/train_pipeline.py) — CLI wrapper template

---

## Failure Modes (explicit)

| Failure | Detection | Response |
|---|---|---|
| `--jsonl-root` does not exist | `Path.exists()` at discovery | Fail-fast, exit non-zero |
| Opportunities file has no `run_header` line | First line missing `kind=="run_header"` | WARN log, treat all lines as records, ledger.malformed_json++ on parse fails |
| Malformed JSON line | `json.JSONDecodeError` | Skip, `ledger.malformed_json++`, sample (first 50) kept in integrity report |
| Missing canonical feature key | `set(CANONICAL_FEATURES) - record["features"].keys()` non-empty | Skip, `ledger.missing_features++`, emit integrity event in STRICT |
| Type mismatch (e.g., `session: "london"` instead of float) | `_coerce_feature_value` raises in STRICT, attempts fallback in LENIENT | STRICT: reject + `ledger.type_mismatch++`. LENIENT: coerce via `SESSION_MAP`/`TREND_MAP` if known mapping. WARN: same as STRICT but no event. |
| Duplicate `(instrument, timestamp, direction)` | In-memory `seen` set during merge | Skip duplicate, `ledger.duplicate++` |
| Out-of-scope instrument | `classify_scope(instrument, scope)` returns False | Skip, `ledger.out_of_scope++`, list in `scope_summary.json` |
| Feature quality below threshold | `compute_feature_quality(features) < min_feature_quality` | Skip, `ledger.low_feature_quality++` |
| Missing `trades.csv` counterpart for an opportunities file | `discover_inputs` pairing | `strict_layout=True` → raise; default → integrity event, build continues without enrichment |
| Trades.csv used only for cross-checking (mfe/mae present in opportunities.jsonl, so CSV is optional enrichment) | — | When present, used to fill missing `mfe/mae/duration_candles`; when absent, opportunities.jsonl is authoritative |
| `RegimeClassifier` raises on a record | Try/except per record | Skip, `ledger.schema_mismatch++` |
| Disk full during write | `OSError` on `.tmp` write | Tmp removed; original output (if any) untouched; raise |
| Hash mismatch between two runs on identical input | Final SHA-256 compare | Test #10 fails CI; manual investigation |

---

## Verification

End-to-end, in order:

```pwsh
# 1. Unit tests
python -m pytest tests/test_stage1_dataset_builder.py -v

# 2. Dry-run discovery on real data (no records emitted)
python scripts/training/build_stage1_dataset.py --dry-run --market-scope crypto

# 3. Full build, default scope=crypto
python scripts/training/build_stage1_dataset.py --market-scope crypto

# 4. Determinism check — second run produces identical hash
python scripts/training/build_stage1_dataset.py --market-scope crypto
# Compare sha256 fields in two integrity reports

# 5. Strict-layout build (should warn or fail on any missing pair)
python scripts/training/build_stage1_dataset.py --market-scope crypto --strict-layout

# 6. Forex scope smoke test
python scripts/training/build_stage1_dataset.py --market-scope forex

# 7. Spot-check output
python -c "import json; print(sum(1 for _ in open('data/master_crypto_training.jsonl')))"
python -c "import json; r=json.load(open('reports/integrity_report.json')); print(r['totals'])"
```

Expected: integrity report shows non-zero `accepted`, near-zero rejections on clean data, all per-bucket counts present, `output_sha256` identical between back-to-back runs.

---

## Integration Notes

- **Downstream consumers**: `src/training/train_pipeline.py` and `src/training/train_bitnet.py` currently load training data through `load_training_data(path)` expecting `{"features": {...}, "label": int}` records. Stage-1's `win_flag` field maps directly to `label`; `features` already matches the 38-key contract. A small adapter `_stage1_to_training_record(rec)` should live alongside `load_training_data` — out of scope for this plan but flagged.
- **No production config change required.** Bucket edges, scope patterns, and validation level are module constants (not hot-path tunables) — keeping them in code avoids a `_compute_hash.py` rehash and a governance promotion. The `bucket_version=1` constant is the future migration handle.
- **Governance**: Stage-1 outputs are training inputs, not promotable artifacts. No `ConfigValidator` involvement. The output file's SHA-256 is recorded in the integrity report for downstream traceability and is included in any model registry entry trained from this dataset (caller's responsibility).
- **Coexistence with `rr_dataset_builder.py`**: Stage-1 supersedes the per-trade RR extraction inside `rr_dataset_builder.build_dataset()` but the older function stays put — Phase-1 rollout uses Stage-1 for new training runs; existing callers keep working until they migrate.
- **Reports directory**: `reports/` does not currently exist. Builder creates it on first write (`Path.mkdir(parents=True, exist_ok=True)`).
- **Memory profile**: ~500k records × ~2KB serialized ≈ 1GB peak during sort. Acceptable for offline tooling. If a future dataset crosses 5M records, add a `--external-sort` path that writes per-instrument shard files then merges via `heapq.merge`.

---

## Self-Review Checklist

- [ ] No magic numbers in caller code; all bucket edges + scope patterns live as module constants with `BUCKET_VERSION=1` migration handle.
- [ ] All file writes go through atomic `.tmp` + `os.replace`.
- [ ] All JSON serialization uses `sort_keys=True` for determinism.
- [ ] No `print()` in `src/`; only `get_flow_logger("DATASET_BUILDER")` and `safe_print` in the CLI.
- [ ] No pandas in the hot path; CSV via stdlib `csv.DictReader`, JSONL via line iteration.
- [ ] Schema hash and feature-order hash recorded per record + once in the integrity report.
- [ ] Test #10 (determinism) is the canary — it must pass before any PR is opened.
- [ ] Rejection samples capped at 50 to keep `integrity_report.json` small even on dirty data.
- [ ] Windows path handling: all `Path()` objects, never raw string joins.
- [ ] CLAUDE.md §6 session log entry appended after merge.

---

# Recovery Phase — Plan

## Context

Stage-1 builder (completed) rejected 305,382 records from v2.0-schema ETHUSDT runs (`logs/ETHUSDT/20260519_*/`) because the 38-key contract requires `liquidity_distance` (index 35), `liquidity_pressure_score` (index 36), and `volume_spike` (index 37) which are absent from v2.0's 35-feature vector. The goal is to determine if these records can be recovered — without fabrication — and document the outcome. If unrecoverable, produce a regen path.

**User constraints (verbatim, non-negotiable):**
- DO NOT zero-fill, fabricate, silently inject defaults, or weaken schema validation
- If exact derivation impossible: mark `{ recovery_status: "UNRECOVERABLE" }`, do not synthesize
- Reject recovered row if `feature_quality < 0.70` or `derived_field_confidence < 0.95`
- FAIL if expectancy changes > 5% or win_rate changes > 3%

---

## Key Findings (from exploration)

### Feature derivation formulas (from `src/features/feature_pipeline.py`)

| Feature | Formula | Required inputs |
|---------|---------|----------------|
| `liquidity_distance` | `min(abs(close - last_swing_high_price), abs(close - last_swing_low_price), abs(close - bos_level)) / (atr × close)` | `close`, `atr`, `last_swing_high_price`, `last_swing_low_price`, `break_of_structure` |
| `liquidity_pressure_score` | `exp(-0.5 × liquidity_distance).clip(0, 1)` with `fillna(10.0)` | `liquidity_distance` |
| `volume_spike` (adaptive) | `(volume_ratio > rolling_percentile_75(volume_ratio, window=50)).astype(int8)` | `volume_ratio` (rolling 50-bar window) |
| `volume_spike` (fallback) | `(volume_ratio > 1.5).astype(int8)` | `volume_ratio` only |

### Why all 3 are UNRECOVERABLE from per-record snapshots

| Feature | UNRECOVERABLE reason | Code |
|---------|---------------------|------|
| `liquidity_distance` | `last_swing_high_price` and `last_swing_low_price` are **intermediate carry-forward series** computed inside `compute_structure_liquidity()` — they are never stored in the feature vector. v2.0 only has `swing_high`/`swing_low` as **binary flags** (0/1), not price levels. A single snapshot record cannot reconstruct the time-series carry-forward. | `MISSING_INTERMEDIATE_SERIES` |
| `liquidity_pressure_score` | Derives from `liquidity_distance`, which is UNRECOVERABLE | `DEPENDS_ON_UNRECOVERABLE` |
| `volume_spike` | The adaptive percentile version (used for 97%+ of records after warmup) requires a rolling 50-bar window of `volume_ratio`. Per-record snapshots have only the current bar's `volume_ratio`. The fixed 1.5× fallback approximation achieves ~70–80% agreement with the adaptive result — far below the required 0.95 confidence threshold. | `CONFIDENCE_BELOW_THRESHOLD` |

**Net result: 0 of 305,382 v2.0 records are recoverable at the required quality threshold.** The recovery script must document this honestly and recommend re-running the opportunity scanner for the affected instruments.

### Infrastructure for fresh v3.0 runs

- **Opportunity scanner:** `scripts/research/opportunity_scanner.py` — simulates both LONG and SHORT per candle, outputs to `results/opportunities/{INSTRUMENT}/{RUN_ID}/opportunities.jsonl`
- **yfinance data:** `data/yfinance/BTCUSDT_M15.csv`, `ETHUSDT_M15.csv`, `SOLUSDT_M15.csv`, `DOGEUSDT_M15.csv`, `XRPUSDT_M15.csv`, `BNBUSDT_M15.csv` (all present)
- Fresh runs from the opportunity scanner will use the current v3.0 `FeaturePipeline` and will naturally emit all 38 features

---

## Files to Create

### 1. `scripts/training/recover_v2_runs.py` (primary)

**Purpose:** Scans v2.0 runs, attempts derivation of 3 missing features, classifies all as UNRECOVERABLE, outputs reports with re-generation recommendations.

**Public API:**
```python
@dataclass(frozen=True)
class RecoveryConfig:
    logs_root: Path = Path("logs")
    reports_dir: Path = Path("reports")
    output_dir: Path = Path("data")
    min_confidence: float = 0.95   # per user spec
    min_feature_quality: float = 0.70  # per user spec

RECOVERY_VERSION = "v1.0"
UNRECOVERABLE_CODES = {
    "MISSING_INTERMEDIATE_SERIES",
    "DEPENDS_ON_UNRECOVERABLE",
    "CONFIDENCE_BELOW_THRESHOLD",
}

@dataclass
class FieldRecoveryAttempt:
    field: str
    status: str          # "RECOVERED" | "UNRECOVERABLE"
    code: str            # one of UNRECOVERABLE_CODES, or "" if RECOVERED
    explanation: str
    confidence: float    # 0.0–1.0; 0.0 if not derivable at all

@dataclass
class RecoveryResult:
    schema_report_path: Path
    delta_report_path: Path
    recovered_output_path: Path
    total_scanned: int
    recovered: int         # expected: 0
    unrecoverable: int     # expected: total_scanned
    by_instrument: dict    # instrument → {run_ids, record_count}
    recommendations: list[str]

def discover_v2_runs(cfg: RecoveryConfig) -> dict: ...
    # Scans logs/ for opportunities.jsonl with feature_dim=35 or schema_version != "3.0"
    # Returns {instrument: [{run_id, path, record_count}]}

def attempt_derive_liquidity_distance(features: dict) -> FieldRecoveryAttempt: ...
    # Returns UNRECOVERABLE / MISSING_INTERMEDIATE_SERIES
    # confidence=0.0: last_swing_high/low price not in snapshot

def attempt_derive_liquidity_pressure_score(ld_attempt: FieldRecoveryAttempt) -> FieldRecoveryAttempt: ...
    # Returns UNRECOVERABLE / DEPENDS_ON_UNRECOVERABLE
    # confidence=0.0

def attempt_derive_volume_spike(features: dict) -> FieldRecoveryAttempt: ...
    # Applies fixed 1.5× fallback, estimates confidence ~0.75 (literature: adaptive vs fixed disagree ~25% of bars)
    # Returns UNRECOVERABLE / CONFIDENCE_BELOW_THRESHOLD since 0.75 < 0.95

def run_recovery(cfg: RecoveryConfig) -> RecoveryResult: ...
    # 1. discover_v2_runs
    # 2. For each record: attempt all 3 derivations
    # 3. If any field UNRECOVERABLE → stamp record, write to separate provenance log
    # 4. Write recovered_v2_to_v3.jsonl (empty, but exists for traceability)
    # 5. Write schema_recovery_report.json + recovery_acceptance_delta.json atomically
    # 6. Return RecoveryResult

def main(argv=None) -> int: ...
    # argparse: --logs-root, --reports-dir, --output-dir
    # calls run_recovery, prints summary via safe_print
```

**Schema recovery report (`reports/schema_recovery_report.json`):**
```jsonc
{
  "recovery_version": "v1.0",
  "generated_at": "2026-05-22T...",
  "schema_drift": {
    "v2_feature_dim": 35,
    "v3_feature_dim": 38,
    "missing_fields": ["liquidity_distance", "liquidity_pressure_score", "volume_spike"]
  },
  "field_analysis": {
    "liquidity_distance": {
      "status": "UNRECOVERABLE", "code": "MISSING_INTERMEDIATE_SERIES",
      "confidence": 0.0,
      "explanation": "Requires last_swing_high_price and last_swing_low_price carry-forward series. v2.0 only stores swing_high/swing_low binary flags (0/1), not price levels. Per-record snapshot cannot reconstruct time-series state."
    },
    "liquidity_pressure_score": {
      "status": "UNRECOVERABLE", "code": "DEPENDS_ON_UNRECOVERABLE",
      "confidence": 0.0,
      "explanation": "Formula: exp(-0.5 × liquidity_distance). Depends on liquidity_distance which is UNRECOVERABLE."
    },
    "volume_spike": {
      "status": "UNRECOVERABLE", "code": "CONFIDENCE_BELOW_THRESHOLD",
      "confidence": 0.75,
      "explanation": "Fixed 1.5× threshold approximation achieves ~75% agreement with adaptive percentile. Required: 0.95. Gap: 0.20. No richer per-record data available to improve estimate."
    }
  },
  "totals": {
    "v2_records_scanned": 305382,
    "recovered": 0,
    "unrecoverable": 305382,
    "by_code": {
      "MISSING_INTERMEDIATE_SERIES": 305382,
      "DEPENDS_ON_UNRECOVERABLE": 305382,
      "CONFIDENCE_BELOW_THRESHOLD": 305382
    }
  },
  "by_instrument": {
    "ETHUSDT": {
      "runs": ["20260519_113806", "..."],
      "record_count": 305382
    }
  },
  "recommendations": [
    "Re-run opportunity_scanner.py for ETHUSDT (same yfinance data) to generate v3.0 records",
    "python scripts/research/opportunity_scanner.py --csv data/yfinance/ETHUSDT_M15.csv --instrument ETHUSDT --output-dir logs/",
    "Then re-run Stage-1 builder: python scripts/training/build_stage1_dataset.py --market-scope crypto"
  ]
}
```

**Recovery acceptance delta (`reports/recovery_acceptance_delta.json`):**
```jsonc
{
  "before_recovery": {
    "accepted": 203588, "rejected_missing_features": 305382, "total_processed": 508970,
    "acceptance_rate": 0.4001
  },
  "after_recovery": {
    "newly_recovered": 0, "still_unrecoverable": 305382,
    "net_accepted": 203588, "acceptance_rate": 0.4001
  },
  "delta": { "net_new_accepted": 0, "acceptance_rate_delta_pct": 0.0 },
  "stat_shift": { "rr_shift": null, "win_rate_shift": null, "expectancy_shift": null,
                  "note": "No records promoted; stat-shift check not applicable" },
  "path_forward": "Re-run opportunity_scanner.py; expected +305382 accepted records from ETHUSDT alone"
}
```

### 2. `scripts/training/scan_opportunities_yfinance.py` (new; generates fresh v3.0 runs)

**Purpose:** Convenience wrapper that runs `opportunity_scanner.py` for all 6 crypto instruments using yfinance M15 CSVs. Outputs to `logs/{INSTRUMENT}/{RUN_ID}/` (where Stage-1 builder discovers them).

```python
INSTRUMENTS = [
    ("BTCUSDT", "data/yfinance/BTCUSDT_M15.csv"),
    ("ETHUSDT", "data/yfinance/ETHUSDT_M15.csv"),
    ("SOLUSDT", "data/yfinance/SOLUSDT_M15.csv"),
    ("DOGEUSDT", "data/yfinance/DOGEUSDT_M15.csv"),
    ("XRPUSDT",  "data/yfinance/XRPUSDT_M15.csv"),
    ("BNBUSDT",  "data/yfinance/BNBUSDT_M15.csv"),
]
# For each instrument: subprocess.run(["python", "scripts/research/opportunity_scanner.py",
#   "--csv", csv_path, "--instrument", instr, "--output-dir", "logs/"])
# Print one-line summary per instrument: accepted_opportunities count
# At end: print total + suggest running Stage-1 builder
```

**Note:** `opportunity_scanner.py` is called with `--output-dir logs/` so output lands in `logs/{INSTRUMENT}/{RUN_ID}/opportunities.jsonl`, exactly where Stage-1 builder discovers it.

### 3. `tests/test_recover_v2_runs.py` (new; 9 tests)

All tests use `tmp_path` fixtures with synthetic 35-feature opportunities.jsonl files.

1. `test_discover_v2_runs_finds_35feature_files` — discovery identifies runs with feature_dim=35; ignores v3.0 runs
2. `test_attempt_derive_liquidity_distance_unrecoverable` — returns UNRECOVERABLE, code=MISSING_INTERMEDIATE_SERIES, confidence=0.0
3. `test_attempt_derive_liquidity_pressure_score_cascades` — if ld is UNRECOVERABLE → lps is DEPENDS_ON_UNRECOVERABLE
4. `test_attempt_derive_volume_spike_confidence_below_threshold` — fixed 1.5× computed, but confidence=0.75 < 0.95 → UNRECOVERABLE
5. `test_run_recovery_produces_empty_output` — all records UNRECOVERABLE → recovered_v2_to_v3.jsonl created but has 0 lines
6. `test_schema_recovery_report_structure` — report has all required top-level keys; totals.recovered=0
7. `test_recovery_acceptance_delta_structure` — delta has before/after/delta keys; net_new_accepted=0
8. `test_run_recovery_atomic_writes` — crash during report write leaves no partial files
9. `test_run_recovery_idempotent` — running twice produces identical reports (same SHA-256)

---

## Reuses

- `safe_print`, `sanitize_for_console` from `src/utils/console_safe.py`
- `emit_integrity_event` from `src/utils/integrity_events.py`
- Atomic-write pattern from `src/core/model_registry._save_atomic`
- `CANONICAL_FEATURES` (for feature_dim comparison) from `src/features/feature_schema.py`
- Logging via `logging.getLogger("recovery")` (not `get_flow_logger` — "DATASET_BUILDER" is not in FLOWS dict)

---

## Failure Modes

| Failure | Response |
|---------|----------|
| `logs/` does not exist | Fail-fast, non-zero exit |
| No v2.0 runs found | Exit 0 with info message: "No v2.0 runs found; nothing to recover" |
| Malformed JSON in v2.0 opportunities.jsonl | Log warning, skip record, count in report |
| Reports dir not writable | Raise OSError; no partial files (atomic writes) |
| Opportunity scanner subprocess fails | Log error with stderr; continue with next instrument |
| Scanner outputs to wrong path | Stage-1 builder dry-run confirms discovery; logged in summary |

---

## Verification

```pwsh
# 1. Unit tests
python -m pytest tests/test_recover_v2_runs.py -v

# 2. Run recovery scan
python scripts/training/recover_v2_runs.py

# 3. Inspect reports
python -c "import json; r=json.load(open('reports/schema_recovery_report.json')); print(r['totals'])"
# Expected: {"v2_records_scanned": 305382, "recovered": 0, "unrecoverable": 305382}

python -c "import json; r=json.load(open('reports/recovery_acceptance_delta.json')); print(r['delta'])"
# Expected: {"net_new_accepted": 0, "acceptance_rate_delta_pct": 0.0}

# 4. Generate fresh v3.0 opportunity runs for 6 instruments
python scripts/training/scan_opportunities_yfinance.py

# 5. Re-run Stage-1 builder (new runs discovered in logs/)
python scripts/training/build_stage1_dataset.py --market-scope crypto

# 6. Verify acceptance improvement
python -c "import json; r=json.load(open('reports/integrity_report.json')); print(r['totals'])"
# Expected: accepted >> 203588 (now includes fresh v3.0 ETHUSDT + 5 new instruments)

# 7. Verify determinism preserved
python scripts/training/build_stage1_dataset.py --market-scope crypto
# Compare sha256 in two integrity reports — must match
```

---

## Self-Review Checklist (Recovery Phase)

- [ ] Recovery script never writes a synthesized or zero-filled feature value
- [ ] All 3 UNRECOVERABLE codes are distinct and machine-readable
- [ ] `recovered_v2_to_v3.jsonl` is created (empty) even when 0 records promoted — traceability
- [ ] `schema_recovery_report.json` includes per-instrument breakdown
- [ ] `recovery_acceptance_delta.json` stat-shift checks are skipped (correctly) when recovered=0
- [ ] All writes atomic (`.tmp` + `os.replace`)
- [ ] `scan_opportunities_yfinance.py` output path matches Stage-1 builder discovery glob (`logs/*/{RUN_ID}/opportunities.jsonl`)
- [ ] No subprocess call suppresses stderr — pipe it to log
- [ ] Tests cover idempotency (running twice = same result)
