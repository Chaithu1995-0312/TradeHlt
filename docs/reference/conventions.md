# CONVENTIONS.md

> Coding and structural conventions observed across the Tradelatest codebase.
> Every rule here is backed by actual usage in `src/`, `scripts/`, or `configs/`.

---

## 1. Naming Conventions

| Element                 | Convention                          | Examples from codebase                                                        |
| ----------------------- | ----------------------------------- | ----------------------------------------------------------------------------- |
| Modules / files         | `snake_case.py`                     | `engine_runner.py`, `ultron_risk_gate.py`, `execution_planner.py`             |
| Packages (folders)      | `lowercase`, short, single-word     | `core/`, `engines/`, `governance/`, `inout/`, `runtime/`                      |
| Classes                 | `PascalCase`                        | `ConfigValidator`, `BacktestRunner`, `ExecutionPlannerV1_2`, `UltronRiskGate` |
| Functions / methods     | `snake_case`                        | `get_prod_section`, `promote_from_checkpoint`, `compute_weighted_cluster_score` |
| Public API methods      | No leading underscore               | `validate`, `run`, `evaluate`, `plan`                                         |
| Private helpers         | `_leading_underscore`               | `_load_validator_cfg`, `_validator_require`, `_safe`, `_params_to_crt_config` |
| Module-level constants  | `SCREAMING_SNAKE_CASE`              | `EXPECTED_ENGINES`, `CANONICAL_FEATURES`, `DUAL_ENGINE_DEFAULTS`              |
| Module-level privates   | `_LEADING_UPPER_SNAKE`              | `_VALIDATOR_CFG`, `_GATE_MIN_TRADES_PER_INSTRUMENT`, `_FITNESS_WEIGHTS`       |
| Enum members            | `UPPER_SNAKE_CASE`                  | `CRTState.DISPLACEMENT`, `Direction.LONG`, `RejectReason.NO_DOUBLE_SWEEP`     |
| Dataclasses             | `PascalCase`                        | `Candle`, `Range`, `Trade`, `BacktestConfig`, `RunRecord`, `CommandSpec`      |
| Config JSON keys        | `snake_case`                        | `min_trades_per_instrument`, `fusion_min_score`, `weight_crt`                 |
| Versioned config files  | `v{N}_{label}_{YYYY_MM}.json`       | `v1_multi_2026_03.json`, `v2_test.json`                                       |
| Archived configs        | `{original}_archived_{YYYYMMDD_HHMMSS}.json` | `v2_test_archived_20260411_200110.json`                               |
| Instrument CSVs         | `{SYMBOL}_{TIMEFRAME}.csv`          | `EURUSD_M15.csv`, `XAUUSD_M15.csv`, `BTCUSDT_M15.csv`                         |
| Models in registry      | Hash-suffixed for immutability      | See `core/model_registry.py` GOV-3 atomic promotion                           |
| JSONL log files         | `{subject}_{action}.jsonl`          | `agent_audit.jsonl`, `expansion_trace.jsonl`, `promotion_log.jsonl`           |

**There are no DB tables in this codebase** (no ORM, no migrations). "Table-like" shapes live in JSON configs and dataclasses.

---

## 2. Folder Placement Rules

Decide where a new file goes by asking "what is it?" then matching against this table.

| Type of file                                    | Lives in                                 | Notes                                                         |
| ----------------------------------------------- | ---------------------------------------- | ------------------------------------------------------------- |
| Importable production module                    | `src/<subpackage>/`                      | Every subpackage has `__init__.py`; packaged via setuptools   |
| New scoring engine (emits `{score, intent}`)    | `src/engines/`                           | Must plug into `EngineRunner`'s `EXPECTED_ENGINES` set        |
| New decision / risk / fusion logic              | `src/core/`                              | Core owns the decision kernel; do not scatter across engines  |
| New validator or config transform               | `src/config_layer/`                      | Builders, validators, decision rules, `llm_inference_client`, planner |
| RR-specific fusion / dataset code               | `src/config_layer/rr/`                   | RR layer kept isolated for independent re-training            |
| Feature extraction or drift code                | `src/features/`                          | Canonical 38-dim schema lives in `feature_schema.py`          |
| Governance / promotion / shadow logic           | `src/governance/`                        | All pre-prod gates live here                                  |
| Live execution (state machine, executor)        | `src/inout/`                             | Strictly live-mode; no backtest logic                         |
| Execution harness (replay, baseline, backtest)  | `src/runtime/`                           | Drives engines over data; no decision logic of its own        |
| Agent / NL-driven automation                    | `src/agent/`                             | Tools go in `tool_registry.py`; plans in `PLAN_REGISTRY`      |
| HTTP server / command registry / UI             | `src/control_plane/`                     | Stdlib only — no FastAPI / Flask                              |
| CLI entry point (runnable script)               | `scripts/<category>/`                    | Import `src.*` packages — never define production logic here  |
| MT5 post-trade analytics module                 | `mt5_analytics/<subpackage>/`            | Separate top-level READ-ONLY subsystem beside `src/` (like `multi_llm/`, `flow_context/`); imports `src.*`; reconstruction kernel + schemas frozen |
| Execution utility that PLACES orders            | `manual_tools/`                          | Deliberately OUTSIDE `mt5_analytics/` (read-only) AND `tests/` (observe-only): *tests observe, generators act*. Demo-only, hard-gated (e.g. `trade_generator.py`) |
| Unit / integration tests                        | `tests/` (flat) or `tests/<subpackage>/` | pytest; `pythonpath=["src","scripts","."]`                    |
| New production config version                   | `configs/production/v{N}_{label}_{YYYY_MM}.json` | Immutable once promoted                               |
| Experimental / spec doc                         | `configs/experimental/spec/*.md`         | Design docs, not runtime                                      |
| Runtime artifacts (never commit)                | `results/`                               | LOCAL_RUN — tuner/baselines/validation; **not git** ([`GITIGNORE_SCHEMA.md`](../governance/GITIGNORE_SCHEMA.md)) |
| JSONL audit logs                                | `logs/`                                  | LOCAL_TELEMETRY — append-only occupancy; **not git**          |
| OHLCV / corpus bytes                            | `data/`                                  | LOCAL_BLOB — identity is Dataset Identity + sha256, not the CSV |
| Serialized models                               | `models/`                                | LOCAL_MODEL — new files ignored; 32 MIXED_RESIDUE still tracked |
| Class C identity bindings                       | `docs/governance/identity_bindings/`     | TRACKED_BINDING — hashes only; Class A/B stay local           |
| Sealed measurement evidence                     | `docs/research-readiness/`               | TRACKED_BINDING — never `results/` (findings gate = `git ls-files`) |
| Documentation (human-facing)                    | `docs/`                                  | Handover, CLI matrix, architecture                            |

**Never place runtime logic in `scripts/`** — scripts are thin CLI wrappers that import from `src/`.

### 2.1 Script inventory (SITS) — phased enforcement

Every runnable path under `scripts/**` and repo-root `*.py` is inventoried by the **Script &
Implementation Traceability System (SITS)**. Inventory authority only — no promote power.

| Artifact | Role |
|---|---|
| `docs/governance/script_registry_stubs.jsonl` | Machine bulk PRIMARY (path-stable `SCR-NNN`) |
| `scripts/governance/seed_script_registry.py` | Curated overlays (purpose / status refinements) |
| `docs/governance/script_registry_grandfather.json` | Phase-1 path freeze pin |
| `data/script_registry.jsonl` | GENERATED projection (gitignored) |
| `docs/reference/script-matrix.md` | Human index (regenerate + sync test) |

**Register a new script (commit path):**

```text
python scripts/analysis/script_census.py --write-stubs docs/governance/script_registry_stubs.jsonl
# update grandfather pin path list if freezing a new epoch (or wait for PR-3 ratchet)
python scripts/governance/seed_script_registry.py
python scripts/analysis/generate_script_matrix.py
```

**Phased enforcement (v1):**

- **PR-2:** 100% path coverage — unregistered disk paths fail `tests/test_script_registry.py`.
- **PR-3:** grandfather **ratchet** — paths *outside*
  `docs/governance/script_registry_grandfather.json` must have
  `purpose ≠ GRANDFATHER_UNCLASSIFIED` (overlay required; `--write-stubs` alone is not enough).
  Change class: `SCRIPT_LIFECYCLE_CHANGE` in `docs/governance/change_contracts.json`.
- **PR-4:** **CANONICAL_CLI ↔ CommandSpec parity** — seed reverse-maps
  `CommandSpec.script` → `category=CANONICAL_CLI` + `control_plane_id` (intentional catalog
  only; **not** a directory heuristic). ACTIVE CANONICAL_CLI without a CP id must be on
  `docs/governance/script_canonical_allowlist.json`. Query: `query_scripts.py --canonical-gap`.
- **PR-5 (now):** **TTL promotion debt** — `ttl_days=null` (default) never fails CI. Curated
  rows with `ttl_days` set + expired age + no valid promotion plan fail the floor and
  `query_scripts --validate`. Valid plan = non-empty `notes` AND (`dest_modules` non-empty OR
  `wontfix:reason=…`). `--missing-impl --jsonl` is **visibility only** (not CI). Report:
  `query_scripts.py --export-debt-report`.
- **PR-6 (optional extract waves):** move product logic into `src/` with thin `scripts/` CLIs.
  First wave (SITS cores): `src/governance/script_census.py` + `script_seed.py` + existing
  `script_registry.py`. **Spine ban:** must not be imported by `engine_runner` /
  `live_engine_hook` / `backtest_v2` (completion criterion a). Prefer new one-shots under
  `scripts/probes/` or `scripts/tmp/`, not repo-root `_*.py`.

#### Fail matrix (what actually fails)

| # | Surface | When | Failure |
|---|---|---|---|
| F1 | CI (`governance.yml --all`) | every push/PR | coverage + grandfather ratchet |
| F2 | Pre-commit GREEN_FLOOR | staged path under governed prefixes/files | same tests when gate fires |
| F3 | Construction `validate-completion` | manifest declares scripts or class `SCRIPT_LIFECYCLE_CHANGE` | missing SITS floor / required checks |
| F4 | SESSION LOG / HANDOFF | habit | **none** (advisory only) |

**Residuals (honest):** mid-session uncommitted probes can skip registration until the next floor
(same residual as Gate-6). Full `scripts/research/` is **not** a pre-commit `GOVERNED_PREFIX` —
CI `--all` is the backstop. `scripts/probes/` and `scripts/tmp/` **are** governed prefixes.

#### Agent checklist when **committing** a new script (Phase 2+)

1. Place under `scripts/<role>/` (probes → `scripts/probes/`, not repo root).
2. `python scripts/analysis/script_census.py --write-stubs docs/governance/script_registry_stubs.jsonl`
3. **Required:** add a Python **overlay** in `seed_script_registry.py` with
   `purpose ≠ GRANDFATHER_UNCLASSIFIED` (or intentional `CLOSED_EPHEMERAL` probe with a real purpose).
4. `python scripts/governance/seed_script_registry.py`
5. `python scripts/analysis/generate_script_matrix.py`
6. Prefer change class `SCRIPT_LIFECYCLE_CHANGE` on the construction manifest.
7. SESSION LOG SCR-ids (advisory).

Do **not** hand-edit stubs for purpose/category — overlays only.

Design: `docs/implementation_plan/script-implementation-traceability-sits-design.md`.

---

## 3. Error Handling Patterns

Three distinct modes, chosen deliberately per context:

### 3.1 Fail-fast at module import (config load)

Used when a missing value would cause silent incorrect behavior. Applied uniformly via a `_require_key` helper:

```python
def _validator_require(cfg: dict, key: str) -> object:
    if key not in cfg:
        raise KeyError(
            f"Required config key '{key}' missing from config_validator section. "
            f"Add it to configs/production/v1_multi_2026_03.json."
        )
    return cfg[key]

_VALIDATOR_CFG = _load_validator_cfg()
_GATE_MIN_TRADES_PER_INSTRUMENT = int(_validator_require(_VALIDATOR_CFG, "min_trades_per_instrument"))
# Module will not import if key is missing.
```

The loader itself wraps import errors into `RuntimeError` with actionable remediation text:

```python
try:
    from config_layer.production_config import get_prod_section
    cfg = get_prod_section("config_validator")
    if not cfg:
        raise RuntimeError("... Add it to configs/production/v1_multi_2026_03.json.")
    return cfg
except ImportError as exc:
    raise RuntimeError(f"Failed to import production_config: {exc}...") from exc
```

### 3.2 Optional-import guard (non-blocking capability)

Used when a capability is nice-to-have. Never silently ignore — record a feature flag:

```python
try:
    from features.feature_monitor import FeatureMonitor
    _MONITOR_AVAILABLE = True
except Exception:
    FeatureMonitor = None
    _MONITOR_AVAILABLE = False
```

Also used for RR fusion: `_RR_FUSION_IMPORT_ERROR = None` on success, stores the exception otherwise for later surfacing.

### 3.3 Fail-open with circuit breaker (external I/O)

Used for LLM / HTTP calls that must not stall the hot path. Pattern lives in `llm_inference_client.py`:

```python
try:
    response = requests.post(SERVER_URL, ..., timeout=REQUEST_TIMEOUT)
except (requests.RequestException, urllib.error.URLError):
    FAIL_COUNT += 1
    if FAIL_COUNT > fail_count_disable:   # circuit open
        return 1.0                         # neutral score — do not block
```

After `fail_count_disable` consecutive failures the gate returns a neutral score and logs `WARNING` once per state transition.

### 3.4 Structured rejection (decision-path errors)

Business-logic errors (bad params, insufficient data) are **not** raised — they return a structured report with a rejection reason:

```python
return ConfigValidator._reject(
    config_id, params,
    hard_failures=["No CSV paths provided -- nothing to validate."],
)
# → {"decision": "REJECT", "hard_failures": [...], "warnings": [...], ...}
```

This preserves auditability and lets callers diff successive rejections.

---

## 4. "API Response" / Result Wrapper Format

This codebase has **no REST API**. "Results" are Python dicts / dataclasses returned to callers, with a consistent shape:

### 4.1 Decision reports (`ValidationReport`, `GateResult`, engine output)

Every decision-producing function returns a dict with at minimum:

```python
{
    "decision":       "APPROVE" | "REJECT" | "ACCEPT",   # explicit outcome
    "config_id":      str,                               # or signal_id / trade_id
    "validated_at":   ISO-8601 UTC timestamp,
    "metrics":        {...},                             # quantitative detail
    "hard_failures":  [str, ...],                        # blocking issues
    "warnings":       [str, ...],                        # non-blocking
}
```

Examples of this shape: `ValidationReport` (`config_validator.py`), `GateResult` (`ultron_risk_gate.py`), engine results from `EngineRunner.run()`.

### 4.2 Audit log lines (JSONL)

Every JSONL log line is a complete, self-contained JSON object with at minimum `timestamp` and a `kind` discriminator. Lines never reference prior context. `configs/promotion_log.jsonl`, `logs/agent_audit.jsonl`, `logs/expansion_trace.jsonl` all follow this.

### 4.3 Control-plane HTTP responses

`src/control_plane/server.py` returns JSON via stdlib `http.server`:

```python
# response shape:
{"status": "ok" | "error", "data": {...}, "error": str | None}
```

---

## 5. Import Ordering & Module Resolution

Observed order (top of almost every `src/` module):

```python
# 1. __future__ (if used)
from __future__ import annotations

# 2. Standard library — alphabetised
import json
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# 3. Third-party — alphabetised
import numpy as np
import pandas as pd
import requests

# 4. Path bootstrap (if module is run as script)
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 5. Internal imports — by subpackage, absolute paths rooted at src/
from config_layer.production_config import get_prod_section
from core.engine_runner import EngineRunner
from engines.trap_validator_engine import TrapValidatorEngine
from utils.logging_config import get_flow_logger
```

### 5.1 Module resolution rules

* Packages are rooted at `src/` (`[tool.setuptools.packages.find] where = ["src"]`).
* Scripts in `scripts/` get `src/` on `sys.path` via pytest config (`pythonpath = ["src","scripts"]`) or explicit bootstrap.
* **Absolute imports only** — no `from .foo import bar` in production modules.
* `src/` is never prefixed in imports: write `from core.engine_runner import X`, not `from src.core.engine_runner import X`.

---

## 6. Logging Conventions

Every module gets a named flow logger:

```python
from utils.logging_config import get_flow_logger
logger = get_flow_logger("ENGINE_RUNNER")   # uppercase, underscore-separated, subject-named
```

Levels used by this codebase:

| Level    | Use case                                                                 |
| -------- | ------------------------------------------------------------------------ |
| DEBUG    | Soft drift (Z>2.5), per-candle trace, per-engine score breakdown         |
| INFO     | Normal pipeline progress, validation start/end, config load success       |
| WARNING  | Hard drift (Z>3.0), circuit-breaker state changes, soft-gate failures    |
| ERROR    | Caught exceptions that did not halt execution                            |
| CRITICAL | Reserved (not currently used in `src/`)                                  |

**Never `print()` in `src/` modules.** `print()` is only acceptable in `scripts/` CLI entry points and `ConfigValidator.validate()` banners (legacy artifact).

---

## 7. Dataclass / Type Conventions

* `@dataclass` for all value objects (`Candle`, `Range`, `Trade`, `BacktestConfig`, `RunRecord`).
* `@dataclass(frozen=True)` for config-derived objects that travel across layers (used in CommandSpec).
* Prefer `Enum` for finite state sets (`CRTState`, `Direction`, `RejectReason`) — never stringly-typed.
* `from_prod_config(cls, cfg: dict) -> "Self"` class method is the canonical config→dataclass bridge.
* Type annotations are required for all public methods; `Any` is acceptable only for config-dict payloads.

---

## 8. Anti-Patterns Explicitly Avoided

| Anti-pattern                           | Rule                                                                                 | Enforcement site                                                   |
| -------------------------------------- | ------------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| **Magic numbers in Python**            | Every tunable value lives in `configs/production/*.json`                             | Modules fail-fast at import if config keys are absent              |
| **Partial fusion (silent)**            | If any engine of `{crt, gaussian, zone_gate, rr}` is missing → hard reject           | `engine_runner.EXPECTED_ENGINES` completeness check                |
| **Lookahead in backtest**              | Candle-by-candle streaming only; feature builder cannot see future bars              | `src/runtime/backtest_v2.py` design contract                       |
| **Silent promotion**                   | Promotion without an approved `ValidationReport` is impossible                       | `PromotionManager` checks `report["decision"] == "APPROVE"` + SHA-256 hash |
| **Unbounded parameter mutation**       | Expansion engine enforces `PARAM_BOUNDS` per mutable parameter                       | `src/expansion/policy_schema.py`                                   |
| **Mutable production configs**         | Prod configs are versioned; promotion archives the prior version with timestamp      | `{version}_archived_{ts}.json` pattern                             |
| **LLM in the hot path without fallback** | `llm_inference_client` enforces timeout + circuit breaker + neutral 1.0 fallback   | `fail_count_disable`, `request_timeout` in config                  |
| **Schema drift without guard**         | `CANONICAL_FEATURES` hash is baselined; schema changes require explicit re-baseline  | `src/runtime/baseline_capture.py`                                  |
| **Decisions without audit**            | Every ACCEPT / REJECT flows through `Collector` + signal-specific audit              | `src/core/collector.py`, `src/core/signal_audit.py`                |
| **Hidden randomness in decision paths** | Deterministic inputs → deterministic outputs; randomness confined to training only  | Codebase-wide                                                      |
| **Unicode-unsafe console output**      | Windows cp1252 fallback for non-ASCII; no raw `print` of arbitrary strings           | `src/utils/console_safe.py`                                        |
| **Re-explaining context mid-session**  | Agent sessions reference session-log entries instead of repeating                    | Per `CLAUDE.md` token control rules                                |

---

## 9. Truth-Layer Standard (schema v2.0)

**Canonical shape for *knowledge / registry / mixed-truth* artifacts** — files that must simultaneously
record what something was *designed* to do, what it *actually runs*, and what the *evidence* says.
Adopt these four layers verbatim (do not invent near-equivalents like `purpose / implementation /
research / state`) so the repository grows one convention, not many — preventing *truth-layer drift*.

| Layer | Meaning | Authority |
| ----- | ------- | --------- |
| `intent`   | Why it was designed | Architectural |
| `runtime`  | What executes today (code is authority) | Tier-0 (§4.0) |
| `evidence` | Findings supporting/refuting it | Research (§6.2 findings) |
| `status`   | Operational rollup (`active`/`orphaned`/`experimental`/`dormant`) | Governance |

**Scope (deliberately narrow):** applies to registries, model catalogs, feature-ownership docs, and
research/runtime hybrid artifacts — **NOT** every markdown file (prose docs, plans, findings keep
their own shapes). Avoids documentation bureaucracy.

**Reference implementation:** [`active_models.yaml`](../../active_models.yaml) (`meta.truth_schema`,
`canonical_layers: [intent, runtime, evidence, status]`). **Backward readability:** a top-level
`status:` rollup may be retained alongside nested `runtime.active:`. New knowledge artifacts should
declare `meta.truth_schema.version` and cite this section.

**v2.1 sub-blocks (additive; layer set unchanged).** `active_models.yaml` file-format v2.1 adds
`reachability` (per-model pointers: config sections, telemetry streams with a descriptive
`schema`/`purpose`/`llm_questions` semantic contract, tests, topics, framework-registry ids),
`optimization` (descriptive tunability only — `authority: none`, §6.5; never promotion thresholds),
and `evidence.conflicts` / `evidence.hypotheses` (F-id / H-id **reference lists** — conflict truth
stays in `docs/current-findings.md`, hypothesis truth in `data/hypothesis_registry.jsonl`, schemas.md
§9.5–9.6). These are sub-blocks *inside* existing entries, so `meta.truth_schema.version` stays
**2.0** while `meta.schema_version` (the file format) tracks 2.1 — do not conflate the two versions.

### Executable-Invariant Scope Policy

Executable YAML↔code (or doc↔code) invariants are justified only when
ALL of the following hold:

1. Demonstrated historical drift
2. Architectural-contract status
3. Low expected churn (stable semantics)
4. High cost of misunderstanding

Current approved scope:
- CRT State Machine (`tests/test_crt_state_invariants.py`)
- v2.1 reachability references (`tests/test_active_models_registry.py`) — **citation-class
  reference resolution only** (paths exist, F-/H-/framework-ids registered, EventType members
  real, §6.5 negative guard on `optimization`); sibling of `tests/test_doc_citations.py`, NOT a
  semantic YAML↔code invariant. Drift evidence: F-041 (pointer/registry rot).

Why CRT qualifies:
- D1 (`states: 10 → 9`) and D9 (`RESOLUTION` transition) demonstrate
  historical drift.
- `VALID_TRANSITIONS` is an architectural contract.
- State semantics are stable and intentionally low-churn.
- Misunderstanding the state machine has high downstream cost.

Do NOT add executable invariants for:
- Intentionally evolving implementations
- Engine composition lists
- Experimental models
- Runtime heuristics

New executable invariants require:
- Evidence of historical drift OR explicit architectural-contract status
- SESSION LOG justification
- Review under the Truth-Layer Standard
