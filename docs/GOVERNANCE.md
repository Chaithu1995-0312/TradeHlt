# GOVERNANCE.md

> Everything required to take a candidate config from tuner → production and roll it back safely.
> All governance logic lives in `src/governance/`. The only supported path to production is through `PromotionManager`.

---

## 1. The Promotion Path

```
scripts/training/auto_tuner_multi.py
        │
        ▼  writes
results/tuner/checkpoint_multi.json
        │
        ▼  consumed by
ConfigValidator.validate(params, csv_paths, config_id)
        │
        ▼  returns
ValidationReport {decision: APPROVE|REJECT, metrics, per_instrument, hard_failures, warnings}
        │
        ├──(REJECT)──▶ results/validation/rejected/<config_id>.json
        │                (stop — candidate cannot be promoted)
        │
        └──(APPROVE)─▶ results/validation/approved/<config_id>.json
                         │
                         ▼
              PromotionManager.promote_from_report(report_path, version, notes)
                         │
                         ▼
              1. _compute_config_hash(params)             # SHA256
              2. _build_registry_entry(...)                # full JSON envelope
              3. archive existing active config as
                 configs/production/{version}_archived_{YYYYMMDD_HHMMSS}.json
              4. write configs/production/{new_version}.json
              5. append to configs/promotion_log.jsonl    # immutable audit
```

**Promotion is refused** if any of the following is true:

- `report["decision"] != "APPROVE"`
- `version` already exists in `configs/production/`
- The config-hash computation fails (malformed `params`)
- The registry write fails mid-operation (archive rolls back, log records `PROMOTION_FAILED`)

---

## 2. PromotionManager API

File: `src/governance/promotion_manager.py` — all methods are static.

### 2.1 `promote_from_report(report_path, version, notes="")`

```python
PromotionManager.promote_from_report(
    report_path="results/validation/approved/v2_candidate_001.json",
    version="v2_audusd_refresh_2026_05",
    notes="Refreshed AUDUSD calibration."
)
# → {"status": "PROMOTED", "version": "...", "path": "...", "params": {...}, "score": 0.52}
```

Use this when the `ValidationReport` already exists on disk.

### 2.2 `promote_from_tuner_checkpoint(checkpoint_path, version, csv_paths, notes="", use_llm=False, top_n=1)`

```python
PromotionManager.promote_from_tuner_checkpoint(
    checkpoint_path="results/tuner/checkpoint_multi.json",
    version="v2_multi_2026_05",
    csv_paths={"EURUSD": "data/EURUSD_M15.csv", "AUDUSD": "data/AUDUSD_M15.csv"},
    notes="Monthly refresh.",
    top_n=1,
)
# → full automated: load → validate top_n → promote first APPROVED
```

Use this as the **default** promotion entry point. It runs validation itself and writes both approved/rejected reports before attempting the promote.

### 2.3 `promote_direct(params, version, validation_summary=None, notes="")`

```python
PromotionManager.promote_direct(
    params={...},
    version="v2_hotfix_2026_05",
    validation_summary={"final_score": 0.48, "total_trades": 65, ...},
    notes="Manual hotfix after upstream data correction."
)
# → {"status": "PROMOTED", ...}   (notes prefixed with "[DIRECT_PROMOTION — validation bypassed]")
```

Bypasses `ConfigValidator.validate()`. **Reserved for pre-validated hotfixes** — never used in normal flow. Every such promotion is marked in the log so auditors can filter for direct promotions.

### 2.4 `list_versions(registry_dir="configs/production")`

```python
PromotionManager.list_versions()
# → ["v1_multi_2026_03", "v2_test", ...]
# also prints a human-readable table with created_at, final_score, config_hash
```

### 2.5 `load_version(version, registry_dir="configs/production")`

```python
PromotionManager.load_version("v1_multi_2026_03")
# → full registry entry dict
```

### 2.6 CLI

```bash
python src/governance/promotion_manager.py promote \
  --checkpoint results/tuner/checkpoint_multi.json \
  --version   v2_<label>_<YYYY_MM> \
  --data-dir  data/
```

`--data-dir` is discovered via glob (`*_M15.csv`) and populates `csv_paths` for the validator.

---

## 3. Registry Layout

```
configs/production/
├── v1_multi_2026_03.json                        # ACTIVE (by convention: latest promoted-at)
├── v1_multi_2026_03_force_accept.json           # sibling test variants (not active)
├── v2_test.json
├── v2_test_archived_20260411_200110.json        # prior v2_test — archived automatically
└── regime_map.json                              # shared regime definitions (not a version)
```

### 3.1 Archive naming

```
{version}_archived_{YYYYMMDD}_{HHMMSS}.json
```

Example: `v2_test_archived_20260411_200110.json` — the `v2_test` config active before `2026-04-11 20:01:10`.

### 3.2 Which version is "active"?

Active selection is not encoded in a single variable. Consumers read via `get_prod_section(name)` which resolves through `src/config_layer/production_config.py`. In practice this loader picks the file that matches `PROD_VERSION` (the registry pointer). Rollback changes the pointer — it does not delete files.

### 3.3 Module-level constants in `promotion_manager.py`

| Constant                      | Value                                   |
| ----------------------------- | --------------------------------------- |
| `PRODUCTION_REGISTRY_DIR`     | `"configs/production"`                  |
| `PROMOTION_LOG_FILE`          | `"configs/promotion_log.jsonl"`         |
| `VALIDATION_APPROVED_DIR`     | `"results/validation/approved"`         |
| `VALIDATION_REJECTED_DIR`     | `"results/validation/rejected"`         |

---

## 4. `configs/promotion_log.jsonl`

Append-only, immutable audit trail. One JSON object per line.

### 4.1 Successful promotion

```json
{
  "event":         "PROMOTED",
  "version":       "v2_test",
  "config_id":     "v2_test_candidate_1",
  "params":        {"retest_depth_max": 0.3, "body_ratio_min": 0.65, ...},
  "config_hash":   "05dd285cfb1363a9...",
  "score":         0.6023,
  "score_std_dev": 0.0,
  "timestamp":     "2026-04-11T19:32:48.073713",
  "notes":         ""
}
```

### 4.2 Failed promotion

```json
{
  "event":     "PROMOTION_FAILED",
  "version":   "v2_bad_candidate",
  "reason":    "ValidationReport decision=REJECT: hard_failures=['min_trades']",
  "timestamp": "2026-04-11T19:40:12.001234"
}
```

### 4.3 Field semantics

| Field          | Appears in              | Meaning                                                        |
| -------------- | ----------------------- | -------------------------------------------------------------- |
| `event`        | all                     | `"PROMOTED" \| "PROMOTION_FAILED"` (also `"ROLLBACK"` planned) |
| `version`      | all                     | Target registry version string                                 |
| `config_id`    | PROMOTED                | Validator config id                                            |
| `params`       | PROMOTED                | Full params dict that was promoted                             |
| `config_hash`  | PROMOTED                | SHA-256 of `params` (deterministic)                            |
| `score`        | PROMOTED                | `final_score` from the approving `ValidationReport`            |
| `score_std_dev`| PROMOTED                | Cross-instrument stability metric (0 if single instrument)    |
| `timestamp`    | all                     | ISO-8601, no `Z` suffix in this log specifically               |
| `notes`        | PROMOTED                | Free-form; `[DIRECT_PROMOTION — validation bypassed]` prefix if direct |
| `reason`       | PROMOTION_FAILED        | Machine-readable failure reason                                |

**Never edit or truncate this file.** It is the source of truth for every prod transition.

---

## 5. Shadow Promotion Gate

File: `src/governance/shadow_promotion_gate.py`. Optional second-stage gate used by governance-mode workflows. Enabled via the `governance` section of the production config.

### 5.1 Constructor

```python
ShadowPromotionGate(
    active_config_path="configs/production/v1_multi_2026_03.json",
    governance_config=None,   # if None, reads governance section from active_config_path
)
# Raises ValueError if min_shadow_trades is not a positive integer.
```

### 5.2 Instance attributes (from `governance` config)

| Attribute            | Default                                  | From config key          |
| -------------------- | ---------------------------------------- | ------------------------ |
| `min_shadow_trades`  | `30`                                     | `governance.min_shadow_trades` |
| `data_csv`           | `"data/AUDUSD_M15.csv"`                  | `governance.shadow_data_csv`   |
| `output_csv`         | `"results/shadow_trades.csv"`            | `governance.shadow_output_csv` |

### 5.3 Workflow

```python
gate = ShadowPromotionGate()

# 1. Stage candidate (writes configs/production/candidate.json)
gate.stage_candidate({"decision_engine": {"score_threshold": 0.50}})

# 2. Execute shadow backtest (spawns backtest_bitnet.py as subprocess)
shadow_pnl, n_trades = gate.execute_shadow_test()

# 3. Compare and decide
result = gate.promote_if_superior(baseline_pnl=0.40, shadow_pnl=shadow_pnl, n_shadow_trades=n_trades)
# → {"promoted": bool, "reason": str}
```

### 5.4 Two gates enforced in `promote_if_superior`

| Gate           | Rule                                                              |
| -------------- | ----------------------------------------------------------------- |
| Sample size    | `n_shadow_trades >= min_shadow_trades`                            |
| Performance    | `shadow_pnl > baseline_pnl` (strict — ties reject)                |

Failing either gate returns `{"promoted": False, "reason": "<why>"}` without touching the registry.

---

## 6. Meta-Governor

File: `src/governance/meta_governor_executor.py`. Drives an autonomous promotion cycle by prompting the BitNet model with a reflection dataset and letting it propose a config patch.

### 6.1 Constructor

```python
MetaGovernorExecutor(
    bitnet_bin="./bitnet/bin/main",
    model_path="./models/bitnet_b1_58_70b.gguf",
    audit_log_path="logs/governance_audit.jsonl",
)
```

### 6.2 Public methods

| Method                                                                                             | Purpose                                                                                                  |
| -------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `run_inference(prompt_path="logs/meta_prompt.txt") -> str`                                         | Run BitNet with the prompt at `prompt_path`; returns raw model output.                                  |
| `extract_and_validate_config(raw_output: str) -> dict`                                             | Extract JSON from the raw output via regex; validate that `"fusion_min_score"` is present; return dict.  |
| `log_governance_event(event_type, engine_id, metrics_snapshot, decision, audit_log_path=None)`    | Append a JSONL record with `{timestamp, event_type, engine_id, metrics_snapshot, decision}` (UTC, `Z`). |

The meta-governor **never promotes directly**. Its output is a candidate patch consumed by `ShadowPromotionGate.stage_candidate()`.

### 6.3 Governance audit log → `logs/governance_audit.jsonl`

```json
{
  "timestamp":        "2026-04-25T00:00:00Z",
  "event_type":       "CANDIDATE_PROPOSED",
  "engine_id":        "meta_governor",
  "metrics_snapshot": {"win_rate": 0.52, "expectancy_rr": 0.15, ...},
  "decision":         {"patch": {"decision_engine": {"score_threshold": 0.50}}}
}
```

Non-dict payloads are normalised before writing. Required fields are enforced (see `tests/test_meta_governor_executor.py`).

---

## 7. Portfolio Validation

File: `src/governance/portfolio_validation.py`. Multi-instrument universality check — guards against curve-fitting by validating a **shared** CRT config across 8 markets.

### 7.1 Scope

```python
INSTRUMENTS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURCAD", "XAUUSD", "BTCUSDT", "ETHUSDT"]
```

(The same tree as `data/*_M15.csv`.)

### 7.2 Key types

```python
@dataclass
class InstrumentConfig:
    name:         str
    csv_path:     str
    pip_size:     float
    spread_pct:   float
    htf_candles:  int
    warmup:       int

class PortfolioAnalytics:
    def aggregate(self) -> dict:
        # returns: total_trades, wins, losses, win_rate,
        #          avg_rr_net, expectancy_rr, total_pnl_rr,
        #          profit_factor, sharpe_per_trade, max_drawdown_rr
```

Portfolio validation is typically run before any promotion that changes cross-market behaviour; a regression here is a hard stop.

---

## 8. Rollback

### 8.1 Safe rollback procedure

1. Identify the archived file for the version you want to revert to:
   ```
   configs/production/v1_multi_2026_03_archived_20260411_200110.json
   ```
2. Copy it (do **not** move) back to the active filename:
   ```
   cp configs/production/v1_multi_2026_03_archived_20260411_200110.json \
      configs/production/v1_multi_2026_03.json
   ```
3. Update `PROD_VERSION` (registry pointer in `src/config_layer/production_config.py`) if the version string itself is changing.
4. Re-hash: `python scripts/maintenance/_compute_hash.py`.
5. Append a manual `ROLLBACK` entry to `configs/promotion_log.jsonl`:
   ```json
   {"event": "ROLLBACK", "to_version": "v1_multi_2026_03", "from_version": "v2_test", "reason": "...", "timestamp": "..."}
   ```
6. Smoke-test immediately:
   ```bash
   pytest tests/test_fusion_and_validator_regression.py tests/test_schema_contracts.py -v
   ```

### 8.2 Restrictions

- **No hot-swap.** Consumers load the active config at import time — a restart of any long-running process (live executor, control plane) is required.
- **Rollback does not undo trades.** Any positions opened under the rolled-forward config must be closed manually if desired.
- **Archived configs are immutable.** If an archive is missing (filesystem loss), you cannot rollback to it automatically — you must reconstruct from the `promotion_log.jsonl` `params` field.

---

## 9. Pre-Promotion Checklist

Before running `PromotionManager`:

- `ConfigValidator.validate()` returns `decision=="APPROVE"` with `hard_failures==[]`.
- `score_std_dev <= max_score_std_dev` across instruments tested.
- `tests/test_fusion_and_validator_regression.py` passes.
- `tests/test_schema_contracts.py` passes (feature schema stable).
- `tests/test_shadow_promotion_gate.py` passes if you will use `ShadowPromotionGate`.
- `python src/runtime/baseline_capture.py --label pre_<version>` snapshotted.
- `python scripts/maintenance/_compute_hash.py` produces a hash matching `config_hash` in the new file.
- If this is a direct promotion (bypassing validator), `notes` documents why and links to the evidence.

---

## 10. Who writes to what (enforcement summary)

| Artifact                                        | Written by                              | Writable outside governance path? |
| ----------------------------------------------- | --------------------------------------- | --------------------------------- |
| `configs/production/<version>.json`             | `PromotionManager._write_to_registry`   | No                                |
| `configs/production/<v>_archived_<ts>.json`     | `PromotionManager._write_to_registry`   | No                                |
| `configs/promotion_log.jsonl`                   | `PromotionManager._log_event`           | Manual `ROLLBACK` line only       |
| `results/validation/approved/<id>.json`         | `ConfigValidator` via `PromotionManager`| Read-only for consumers           |
| `results/validation/rejected/<id>.json`         | `ConfigValidator` via `PromotionManager`| Read-only for consumers           |
| `logs/governance_audit.jsonl`                   | `MetaGovernorExecutor.log_governance_event` | Append-only                   |
| `configs/production/candidate.json`             | `ShadowPromotionGate.stage_candidate`   | Overwritten each stage; transient |
| `results/shadow_trades.csv`                     | `ShadowPromotionGate.execute_shadow_test` (subprocess) | Overwritten each run   |

Any other process writing to the registry, the promotion log, or `logs/governance_audit.jsonl` is a **convention break** — call it out before producing the change.
