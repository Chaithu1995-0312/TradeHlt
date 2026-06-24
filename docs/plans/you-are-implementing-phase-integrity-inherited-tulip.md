> Created: 2026-05-20 · Updated: 2026-05-20 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Phase-Integrity Hardening — Implementation Plan

## Context

The repo already shipped the **first** integrity-hardening pass (LLM fail-open, RR drift bypass, config hash, BitNet debug-safe default, etc.). What remains is the **deterministic integrity spine** — six surfaces where the system still fails-open or fails-silent:

1. `trade_replay_validator.py` blindly trusts `pnl_rr_net` (stub replay), making backtest validation tautological.
2. There is no canonical integrity-event emitter — observability is scattered across `engine_telemetry.py`, ad-hoc `log.warning`, and silent `pass`.
3. Three+ JSONL iterators (`compress_logs_for_llm.py`, `trade_logger.py`, `replay_memory_engine.py`, `analyze_fusion_shadow.py`) discard malformed lines with no count, no event, no ratio gate.
4. `crt_feature_builder.py:117` maps **unknown session strings to 0.0**, which is the index for `london` — silent training contamination.
5. Three incompatible BitNet model schemas (`legacy_6input`, ad-hoc 35-d, ad-hoc 38-d via `CANONICAL_FEATURE_DIM`) coexist with no schema-version enforcement and `bitnet_runner.py:61` silently truncates feature vectors.
6. `feature_order_hash` is computed by `feature_schema.py` and stored by the Gaussian path, but the **BitNet inference path never verifies it**, so reordered features go undetected.

Goal: surgical in-place patches that add **structured integrity telemetry**, convert each fail-open to fail-closed (or fail-visible), preserve all existing CLI / output formats, and keep legacy model loaders working with explicit warnings.

User-confirmed scope decisions:
- Replay validator stays library-style; fail-closed if the caller's trade dict lacks `entry_price` / `sl_price` / `tp1_price` / `tp2_price` / `direction`. No TradeRecord schema change.
- `model_contract.py` imports `CANONICAL_FEATURE_DIM` from `features.feature_schema` (single source of truth) and asserts equality at module load.
- JSONL corruption patch covers `src/replay/replay_memory_engine.py` and `src/runtime/analyze_fusion_shadow.py` in addition to the three files named in the spec.

---

## Critical files

| File | Role in patch |
| --- | --- |
| `src/utils/integrity_events.py` (NEW) | Canonical `emit_integrity_event()` spine; appends to `logs/integrity_events.jsonl`; never raises. |
| `src/bitnet/model_contract.py` (NEW) | `CANONICAL_MODEL_SCHEMA_VERSION="bitnet_v3"`, normalizers for legacy schemas, mismatch checks. |
| `scripts/misc/trade_replay_validator.py` | Replace stub with deterministic candle replay; emit `REPLAY_MISMATCH` / `REPLAY_TRADE_INCOMPLETE` / `REPLAY_NO_CANDLES`. |
| `src/features/crt_feature_builder.py` | Unknown-session detection: encode `-1.0`, emit `SESSION_UNKNOWN`, honour `STRICT_SESSION_VALIDATION`. |
| `src/features/feature_schema.py` | Add `SESSION_UNKNOWN = -1.0` constant; keep `SESSION_MAP` strict-encoding docstring honest. |
| `scripts/analysis/compress_logs_for_llm.py` | Replace silent `continue` with counted malformed + integrity event + ratio gate. |
| `src/journal/trade_logger.py` | Same pattern for `TradeLogger.load_all()`. |
| `src/replay/replay_memory_engine.py` | Same pattern for the batch loader at line 302–303. |
| `src/runtime/analyze_fusion_shadow.py` | Wrap the `json.loads → None` site with an integrity event + counter; preserve `None` return. |
| `src/bitnet/bitnet_inference.py` | Verify `schema_version`, `feature_dim`, `feature_order_hash` at load via `model_contract`. Emit integrity warning for legacy formats. |
| `src/bitnet/bitnet_runner.py` | Remove silent slicing (`ordered_values[:self.expected_input_dim]`). Require exact match; fail-closed `RuntimeError`. |
| `scripts/export/export_bitnet_model.py` | Emit canonical `bitnet_v3` envelope (schema_version, feature_dim, feature_order_hash, feature_names, layers, metadata). |
| `scripts/export/generate_bootstrap_model.py` | Mark output as `legacy_6input` explicitly (already does) but stamp a `feature_order_hash` so loader can warn. |
| `scripts/export/regen_bitnet_35.py` | Wrap output in canonical envelope; preserve 35-d feature_order; mark `schema_version="bitnet_v3"` with `feature_dim=35` (legacy bridge). |

Existing utilities to reuse (do NOT re-implement):
- `src/utils/engine_telemetry.py` — pattern for `_append_jsonl()` + envelope (copy the fail-open file-write idiom).
- `events.event_fabric.make_event_envelope` — optional-import wrap, fallback envelope.
- `src/features/feature_schema._feature_order_hash()` — already canonical; reuse for the contract.
- `src/runtime/backtest_v2.CandleLoader` — referenced only by callers; replay function itself stays candle-list based.

---

## Phase 1 — Replay integrity (`scripts/misc/trade_replay_validator.py`)

**Patch in place.** Keep `classify_outcome`, `validate_all`, and the CSV export at `logs/validator_dataset.csv` byte-identical in the success path.

Rewrite **`replay_single_trade(trade, candles)`** to:

1. **Validate required trade fields** (fail-closed):
   ```
   REQUIRED = ("trade_id", "entry_price", "sl_price", "tp1_price", "tp2_price", "direction")
   missing = [k for k in REQUIRED if trade.get(k) is None]
   if missing:
       emit_integrity_event("REPLAY_TRADE_INCOMPLETE", "ERROR", "trade_replay_validator",
                            {"trade_id": trade.get("trade_id"), "missing_fields": missing})
       return {"error": "incomplete_trade", "trade_id": trade.get("trade_id"), "missing_fields": missing}
   ```
2. **Validate candles**:
   ```
   if not candles:
       emit_integrity_event("REPLAY_NO_CANDLES", "ERROR", "trade_replay_validator",
                            {"trade_id": trade.get("trade_id")})
       return {"error": "no_candles", "trade_id": trade.get("trade_id")}
   ```
3. **Deterministic forward simulation** (LONG ⇄ SHORT mirrored):
   - State: `tp1_hit=False`, `sl_effective=sl_price`, `exit_price=None`, `exit_reason=None`.
   - For each candle in order, read `high`, `low`, `close`, `timestamp`.
   - LONG branch:
     - Pessimistic SL-first (matches `BacktestRunner` semantics): if `low <= sl_effective`, `exit_price=sl_effective`, `exit_reason="SL-BE" if tp1_hit else "SL"`; break.
     - Else if `high >= tp2_price`, `exit_price=tp2_price`, `exit_reason="TP2"`; break.
     - Else if (not `tp1_hit`) and `high >= tp1_price`: set `tp1_hit=True`, `sl_effective=entry_price` (BE move).
   - SHORT branch: mirrored (`high>=sl_effective` for stop; `low<=tp2_price` for TP2; `low<=tp1_price` for TP1).
   - If loop ends without exit: `exit_reason="TIMEOUT"`, `exit_price=candles[-1]["close"]`.
4. **Compute** `recomputed_rr`:
   ```
   risk = abs(entry_price - sl_price)
   sign = +1 if direction == "LONG" else -1
   recomputed_rr = sign * (exit_price - entry_price) / risk   # risk>0 guaranteed by validation above
   ```
   Reject division if `risk == 0` → integrity event `REPLAY_ZERO_RISK`, return error row.
5. **Mismatch detection**:
   ```
   MAX_RR_DELTA = 0.05
   original_rr = float(trade.get("pnl_rr_net", 0.0))
   rr_delta = recomputed_rr - original_rr
   replay_consistent = abs(rr_delta) <= MAX_RR_DELTA
   if not replay_consistent:
       emit_integrity_event("REPLAY_MISMATCH", "WARNING", "trade_replay_validator",
           {"trade_id": trade["trade_id"], "expected_rr": original_rr,
            "recomputed_rr": recomputed_rr, "delta": rr_delta,
            "original_exit_reason": trade.get("exit_reason"),
            "replayed_exit_reason": exit_reason})
   ```
6. **Extend the return dict** with:
   - `replay_consistent: bool`
   - `rr_delta: float`
   - `replay_path: {candles_processed, tp1_hit_at_index, exit_index, exit_timestamp, exit_reason_replayed}`
   - Preserve every existing key (`recomputed_rr`, `original_rr`, `diff`, `is_match`, `exit_reason`, `candles_processed`, `tp1_hit`, `tp2_hit`, `features`, `outcome`) so CSV downstream is a strict superset, not a replacement.

`validate_all()` stays untouched except: surface an aggregate counter (`replay_consistent_count`, `replay_mismatch_count`) and emit one summary `REPLAY_BATCH_SUMMARY` integrity event at the end.

---

## Phase 2 — Integrity event spine (`src/utils/integrity_events.py`)

New module, ~80 LOC. Mirrors `engine_telemetry._append_jsonl` semantics:

```python
from pathlib import Path
import json, logging, time, sys

_LOG_PATH = Path("logs/integrity_events.jsonl")
_logger = logging.getLogger("IntegrityEvents")

class Severity:
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

_VALID = {Severity.INFO, Severity.WARNING, Severity.ERROR, Severity.CRITICAL}

def emit_integrity_event(event_type: str, severity: str, source: str, payload: dict) -> None:
    """Append one integrity event to logs/integrity_events.jsonl. NEVER raises."""
    try:
        if severity not in _VALID:
            severity = Severity.WARNING
        record = {
            "ts":       time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event":    str(event_type),
            "severity": severity,
            "source":   str(source),
            "payload":  payload if isinstance(payload, dict) else {"raw": str(payload)},
        }
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
    except Exception as exc:                                          # noqa: BLE001
        try:
            _logger.debug("integrity_events: write failed: %s", exc)
            print(f"[integrity_events:FALLBACK] {event_type} {severity} {source} {payload}",
                  file=sys.stderr)
        except Exception:
            pass
```

This is intentionally **smaller** than `engine_telemetry.py` — no envelope, no event_fabric dependency, no class state. The contract is "append-only JSONL, never throws", per spec.

Callers always import lazily inside the function to keep import graphs clean:
```python
from src.utils.integrity_events import emit_integrity_event, Severity
```

---

## Phase 3 — JSONL corruption visibility

Same surgical pattern at five sites. Per file: introduce a small helper or inline counter.

**Shared idiom** (inlined per file, no new shared helper — keeps blast radius minimal):

```python
malformed = 0
valid = 0
for lineno, line in enumerate(fh, 1):
    line = line.strip()
    if not line:
        continue
    try:
        record = json.loads(line)
        valid += 1
        # ... existing yield/append behavior ...
    except json.JSONDecodeError as exc:
        malformed += 1
        emit_integrity_event(
            "JSONL_CORRUPTION", "WARNING", "<module_name>",
            {"path": str(path), "line_number": lineno,
             "raw_preview": line[:160], "error": str(exc)},
        )
        continue

total = malformed + valid
if total and (malformed / total) > 0.10:                              # MAX_CORRUPTION_RATIO
    emit_integrity_event(
        "JSONL_CORRUPTION_THRESHOLD_EXCEEDED", "ERROR", "<module_name>",
        {"path": str(path), "malformed_lines": malformed,
         "valid_lines": valid, "corruption_ratio": malformed / total},
    )
```

Sites to patch (preserve every existing return type, yield semantics, and return value):
- `scripts/analysis/compress_logs_for_llm.py:45-48` (`_iter_records`)
- `src/journal/trade_logger.py:73-76` (`TradeLogger.load_all`)
- `src/replay/replay_memory_engine.py:302-303` (batch loader)
- `src/runtime/analyze_fusion_shadow.py:48-50` — keep the `return None` contract but emit a `JSONL_CORRUPTION` event before returning; this site is single-line, not a loop, so no ratio gate applies.

`MAX_CORRUPTION_RATIO = 0.10` declared as a module-level constant only inside the looping sites.

Pipelines never fail. Only visibility changes.

---

## Phase 4 — Unknown-session coercion fix

**`src/features/feature_schema.py`** — add the explicit sentinel right under `SESSION_MAP` (line ~94):

```python
SESSION_UNKNOWN: float = -1.0   # explicit out-of-band marker; never collides with any mapped session.
```

**`src/features/crt_feature_builder.py:116-117`** — replace:

```python
session = str(candle.get("session", "unknown")).lower().strip()
if session in SESSION_MAP:
    features["session"] = SESSION_MAP[session]
else:
    features["session"] = SESSION_UNKNOWN
    raw = candle.get("session")
    from src.utils.integrity_events import emit_integrity_event, Severity
    emit_integrity_event(
        "SESSION_UNKNOWN", "WARNING", "crt_feature_builder",
        {"raw_session": repr(raw), "normalized": session,
         "encoded_value": SESSION_UNKNOWN},
    )
    if os.environ.get("STRICT_SESSION_VALIDATION", "false").lower() == "true":
        raise ValueError(f"Unknown session value: {raw!r}")
```

Notes:
- `.strip()` added to match `live_engine_hook._normalize_session` whitespace handling.
- `os` import is already present in the module (check at edit time; add if missing).
- Default remains non-fatal; strict mode opt-in via env var (matches the `BITNET_DEBUG` precedent).
- The `SESSION_MAP` docstring claim ("Unknown values raise ValueError") becomes truthful **only when strict mode is on**. Update the comment to reflect this.

---

## Phase 5 — Canonical BitNet serialization contract

**New** `src/bitnet/model_contract.py`:

```python
"""Canonical BitNet serialization contract. Legacy formats still loadable; mismatches fail-closed."""
from __future__ import annotations
import hashlib, json
from typing import Any
from features.feature_schema import CANONICAL_FEATURE_DIM as _SCHEMA_DIM, CANONICAL_FEATURES, FEATURE_ORDER_HASH

CANONICAL_MODEL_SCHEMA_VERSION = "bitnet_v3"
CANONICAL_FEATURE_DIM = _SCHEMA_DIM            # single source of truth
assert CANONICAL_FEATURE_DIM == 38, "BitNet v3 contract requires 38-feature canonical schema"

LEGACY_SCHEMAS = {"legacy_6input", "bitnet_export_v1"}

def feature_order_hash(feature_names: list[str]) -> str:
    payload = json.dumps(list(feature_names), sort_keys=False).encode()
    return hashlib.sha256(payload).hexdigest()[:16]

def build_envelope(layers: list, *, feature_names: list[str] | None = None,
                   metadata: dict | None = None) -> dict:
    names = list(feature_names) if feature_names else list(CANONICAL_FEATURES)
    return {
        "schema_version": CANONICAL_MODEL_SCHEMA_VERSION,
        "feature_dim": len(names),
        "feature_order_hash": feature_order_hash(names),
        "feature_names": names,
        "layers": layers,
        "metadata": metadata or {},
    }

def normalize_loaded(model: dict) -> dict:
    """Return a normalized view: {schema_version, feature_dim, feature_order_hash, feature_names, layers, raw}.
    Emits an integrity event for legacy formats; NEVER silently reinterprets dims."""
    from src.utils.integrity_events import emit_integrity_event, Severity
    schema = model.get("schema_version") or model.get("schema") or "unknown"
    if schema == CANONICAL_MODEL_SCHEMA_VERSION:
        return {
            "schema_version": schema,
            "feature_dim": int(model["feature_dim"]),
            "feature_order_hash": model.get("feature_order_hash", ""),
            "feature_names": list(model.get("feature_names", [])),
            "layers": model["layers"],
            "raw": model,
        }
    # Legacy normalization
    if schema in LEGACY_SCHEMAS or "layer1_w" in model or "layers" in model:
        # infer dim
        if "input_dim" in model:
            dim = int(model["input_dim"])
        elif "layer1_w" in model:
            dim = 6
        elif "layers" in model and model["layers"]:
            first = model["layers"][0]
            dim = int(first.get("in", len(first.get("weights", [[None]])[0])))
        else:
            raise RuntimeError(f"BitNet model_contract: cannot infer feature_dim from schema={schema!r}")
        names = list(model.get("feature_order", []))
        h = feature_order_hash(names) if names else ""
        emit_integrity_event(
            "BITNET_LEGACY_LOAD", "WARNING", "bitnet.model_contract",
            {"schema": schema, "feature_dim": dim, "feature_order_hash": h,
             "note": "loaded under legacy bridge; upgrade to bitnet_v3"},
        )
        return {"schema_version": schema, "feature_dim": dim,
                "feature_order_hash": h, "feature_names": names,
                "layers": model.get("layers", []), "raw": model}
    raise RuntimeError(f"BitNet model_contract: unrecognized schema={schema!r}")
```

**`src/bitnet/bitnet_inference.py`** — patch `__init__`:
- After `self.model = json.load(f)`, call `meta = normalize_loaded(self.model)`.
- Store `self.schema_version`, `self.feature_dim`, `self.feature_order_hash`, `self.feature_names`.
- Keep existing branch logic for the forward pass selection (legacy vs export) — only the metadata layer becomes canonical.
- If `self.feature_dim != model_dim_inferred_from_layers`, raise `RuntimeError("BitNet feature dimension mismatch")`.

**`src/bitnet/bitnet_runner.py:54-61`** — fail-closed:

```python
ordered_values = [features[k] for k in CANONICAL_FEATURES]
if len(ordered_values) != self.expected_input_dim:
    from src.utils.integrity_events import emit_integrity_event
    emit_integrity_event(
        "BITNET_DIM_MISMATCH", "CRITICAL", "bitnet.runner",
        {"runtime_features": len(ordered_values),
         "model_input_dim": self.expected_input_dim,
         "model_schema_version": getattr(self.model, "schema_version", "unknown"),
         "model_feature_order_hash": getattr(self.model, "feature_order_hash", "")},
    )
    raise RuntimeError(
        f"BitNet feature dimension mismatch: runtime={len(ordered_values)} "
        f"model={self.expected_input_dim} — refusing to truncate. "
        f"Re-export model with schema_version={CANONICAL_MODEL_SCHEMA_VERSION}."
    )
input_vector = np.array(ordered_values, dtype=np.float32)
```

**Legacy bridge for 6-input models**: special-case `if self.model.schema_version == "legacy_6input"`: take only the six fields named in the model's `feature_order` (not a prefix slice) and emit one `BITNET_LEGACY_FEATURE_SUBSET` integrity event per process start. This preserves the existing operational behavior for the `legacy_6input` GA path without ever silently reinterpreting features.

**Export scripts**:
- `scripts/export/export_bitnet_model.py` — wrap the dict it currently writes via `model_contract.build_envelope(layers, feature_names=list(CANONICAL_FEATURES), metadata={"source": "export_bitnet_model"})`.
- `scripts/export/regen_bitnet_35.py` — same wrap, but pass the 35-element feature_order it already declares; resulting envelope has `schema_version="bitnet_v3"` + `feature_dim=35` + `feature_order_hash` for the 35-d ordering. Loaders treat any v3 model as canonical regardless of dim.
- `scripts/export/generate_bootstrap_model.py` — keep emitting `schema="legacy_6input"` (do NOT upgrade — this is a bootstrap path) but add `feature_order_hash` so the loader's warning carries the hash.

---

## Phase 6 — Runtime graph stabilization

Three additions, all inside `bitnet_inference.py` / `bitnet_runner.py` (no new files):

1. At BitNet load: compare `self.feature_order_hash` against `features.feature_schema.FEATURE_ORDER_HASH` **when** `self.schema_version == "bitnet_v3"` AND `self.feature_dim == CANONICAL_FEATURE_DIM`. Mismatch → CRITICAL `BITNET_FEATURE_ORDER_HASH_MISMATCH` + raise.
2. At BitNet load: if `schema_version` missing entirely AND the model has `layers` in the new shape, emit CRITICAL `BITNET_MISSING_SCHEMA_VERSION` and raise (only refuses true ambiguous models; legacy schemas still load via the legacy bridge above).
3. The `BITNET_DIM_MISMATCH` event from Phase 5 already covers runtime feature-count drift. Add the same check at the top of `BitNetModel.predict()` for defense-in-depth (already raises a `ValueError` there — just emit the integrity event before raising).

No other engines are touched. Per the spec: "preserve runtime behavior unless explicitly fixing corruption/fail-open behavior".

---

## Verification

End-to-end checks (read-only commands the user can run after the patch lands):

1. **Replay integrity** — synthesize a trade dict with known entry/SL/TP1/TP2/direction + a fabricated candle list that hits TP1 then SL:
   ```
   python -c "from scripts.misc.trade_replay_validator import replay_single_trade; ..."
   ```
   Assert: `replay_consistent==True`, `recomputed_rr` matches by-hand calc, `rr_delta` within `±0.05`.
   Then corrupt one OHLCV bar to force a mismatch and confirm `REPLAY_MISMATCH` lands in `logs/integrity_events.jsonl`.

2. **Integrity spine** — `python -c "from src.utils.integrity_events import emit_integrity_event; emit_integrity_event('SELFTEST','INFO','plan','{}')"` then tail `logs/integrity_events.jsonl`.

3. **JSONL corruption** — append a single malformed line to `logs/trade_journal.jsonl`, then call `TradeLogger().load_all()`; expect one `JSONL_CORRUPTION` event, no crash, all valid records loaded.

4. **Unknown session** — call `build_bitnet_features({"session": "tokyo", ...})`; expect `features["session"] == -1.0` and a `SESSION_UNKNOWN` event. Re-run with `STRICT_SESSION_VALIDATION=true` and confirm `ValueError`.

5. **BitNet contract** — load `model.json` (legacy_6input): expect `BITNET_LEGACY_LOAD` event, no truncation, model still runs for its declared 6 features. Load `model_export_format.json`: expect normalization to `bitnet_v3` semantics. Then construct a 4-dim weight matrix masquerading as `bitnet_v3` + 38-dim → expect `BITNET_FEATURE_ORDER_HASH_MISMATCH` and `RuntimeError`.

6. **pytest** — run the existing suite. The patch is BC for tests that pass valid trade dicts; replay tests that previously used the stub will need new fixtures (out-of-scope for this plan, called out in "remaining risks").

7. **Regression** — run one short backtest with `BacktestRunner` end-to-end, confirm no new `RuntimeError` paths, and `logs/integrity_events.jsonl` contains only expected lifecycle events.

---

## Self-review (mandatory artifacts)

### 1. File-by-file changelog
- **NEW** `src/utils/integrity_events.py` — `emit_integrity_event`, `Severity` enum, fail-open JSONL append.
- **NEW** `src/bitnet/model_contract.py` — `build_envelope`, `normalize_loaded`, `feature_order_hash`, `CANONICAL_MODEL_SCHEMA_VERSION`.
- **MOD** `scripts/misc/trade_replay_validator.py` — real candle replay; integrity events; preserved CSV.
- **MOD** `src/features/feature_schema.py` — add `SESSION_UNKNOWN = -1.0`.
- **MOD** `src/features/crt_feature_builder.py:116-117` — explicit unknown branch, integrity event, strict mode.
- **MOD** `scripts/analysis/compress_logs_for_llm.py:45-48` — count + emit + ratio gate.
- **MOD** `src/journal/trade_logger.py:73-76` — same pattern.
- **MOD** `src/replay/replay_memory_engine.py:302-303` — same pattern.
- **MOD** `src/runtime/analyze_fusion_shadow.py:48-50` — emit on JSONDecodeError, preserve `return None`.
- **MOD** `src/bitnet/bitnet_inference.py` — schema_version + feature_order_hash verification at load.
- **MOD** `src/bitnet/bitnet_runner.py:54-61` — remove silent slice; fail-closed dim mismatch; legacy bridge.
- **MOD** `scripts/export/export_bitnet_model.py` — wrap in `bitnet_v3` envelope.
- **MOD** `scripts/export/regen_bitnet_35.py` — wrap in `bitnet_v3` envelope (35-d).
- **MOD** `scripts/export/generate_bootstrap_model.py` — stamp `feature_order_hash`; keep `legacy_6input` schema label.

### 2. Fail-open behaviors removed
- `replay_single_trade` blindly trusting `pnl_rr_net` → real replay; mismatch is now visible.
- `SESSION_MAP.get(session, 0.0)` unknown→London → unknown→-1.0 + event.
- Silent `except JSONDecodeError: pass/continue` in four loaders → counted + visible.
- `BitNetRunner` `[:self.expected_input_dim]` silent slice → `RuntimeError`.
- `BitNetModel.__init__` accepting any JSON with `layers` → requires schema_version OR matches legacy bridge.

### 3. New fail-closed behaviors
- Replay: missing trade fields → `ERROR` event + error row.
- Replay: zero-risk trade → `ERROR` event + error row.
- BitNet load: missing `schema_version` on new-shape model → `RuntimeError`.
- BitNet load: `feature_order_hash` mismatch on canonical model → `RuntimeError`.
- BitNet predict: runtime/model dim mismatch → `RuntimeError` (previously silent slice).
- Optional via env: `STRICT_SESSION_VALIDATION=true` → `ValueError` on unknown session.

### 4. Backward-compatibility matrix

| Surface | Before | After | BC? |
| --- | --- | --- | --- |
| `replay_single_trade(trade, candles)` signature | unchanged | unchanged | yes |
| `validate_all` → `logs/validator_dataset.csv` columns | exists | superset (new cols appended) | yes (additive) |
| `TradeLogger.load_all()` return type | `list[dict]` | `list[dict]` | yes |
| `_iter_records` yield semantics | yields dicts | yields dicts (skips malformed, now logged) | yes |
| `analyze_fusion_shadow.py` return on bad JSON | `None` | `None` (also logs) | yes |
| `BitNetModel(path)` for legacy_6input | input_dim=6 | input_dim=6 + warning event | yes |
| `BitNetModel(path)` for bitnet_export_v1 | input_dim from JSON | normalized to v3 view + warning event | yes |
| `BitNetRunner.predict(features)` when dims match | works | works | yes |
| `BitNetRunner.predict(features)` when dims mismatch | silent slice + score | `RuntimeError` | **NO — intentional fail-closed** |
| `build_bitnet_features({"session":"tokyo"})` | encodes as 0.0 | encodes as -1.0 + event | **NO — intentional fix** |
| `build_bitnet_features({"session":"tokyo"})` with `STRICT_SESSION_VALIDATION=true` | encodes as 0.0 | raises ValueError | **NO — opt-in only** |

### 5. Replay validation flow
`caller assembles trade dict (entry/sl/tp1/tp2/direction/pnl_rr_net) and candle list → replay_single_trade → validate fields → validate candles → forward sim (direction-aware, BE on TP1 hit) → compute recomputed_rr → compare against pnl_rr_net → if |delta|>0.05 emit REPLAY_MISMATCH → return enriched row → validate_all aggregates → CSV at logs/validator_dataset.csv (superset) + REPLAY_BATCH_SUMMARY event`.

### 6. JSONL corruption flow
`loader opens file → per line: try json.loads → on success increment valid → on JSONDecodeError increment malformed + emit JSONL_CORRUPTION with line_number + raw_preview[:160] + continue → at EOF: if malformed/(malformed+valid) > 0.10 emit JSONL_CORRUPTION_THRESHOLD_EXCEEDED → return original data type unchanged`.

### 7. BitNet schema migration flow
`exporter calls model_contract.build_envelope(layers, feature_names) → writes JSON with {schema_version:"bitnet_v3", feature_dim, feature_order_hash, feature_names, layers, metadata}`.
`loader: model_contract.normalize_loaded(json) → if bitnet_v3 → verify feature_order_hash against features.feature_schema.FEATURE_ORDER_HASH when feature_dim==CANONICAL_FEATURE_DIM → else if legacy_6input/bitnet_export_v1 → emit BITNET_LEGACY_LOAD warning → continue working → else → raise`.
`runtime: BitNetRunner asserts len(canonical features)==model.feature_dim → never slices`.

### 8. Integrity event examples
```json
{"ts":"2026-05-20T14:03:11Z","event":"REPLAY_MISMATCH","severity":"WARNING","source":"trade_replay_validator","payload":{"trade_id":"T-7421","expected_rr":1.92,"recomputed_rr":1.04,"delta":-0.88,"original_exit_reason":"TP2","replayed_exit_reason":"SL-BE"}}
{"ts":"2026-05-20T14:03:11Z","event":"JSONL_CORRUPTION","severity":"WARNING","source":"src.journal.trade_logger","payload":{"path":"logs/trade_journal.jsonl","line_number":4172,"raw_preview":"{\"trade_id\":\"T-7421\",\"pnl\":1.92,\"resu","error":"Unterminated string starting at: line 1 column 41 (char 40)"}}
{"ts":"2026-05-20T14:03:11Z","event":"SESSION_UNKNOWN","severity":"WARNING","source":"crt_feature_builder","payload":{"raw_session":"'TOKYO'","normalized":"tokyo","encoded_value":-1.0}}
{"ts":"2026-05-20T14:03:11Z","event":"BITNET_LEGACY_LOAD","severity":"WARNING","source":"bitnet.model_contract","payload":{"schema":"legacy_6input","feature_dim":6,"feature_order_hash":"a1b2c3d4e5f60718","note":"loaded under legacy bridge; upgrade to bitnet_v3"}}
{"ts":"2026-05-20T14:03:11Z","event":"BITNET_DIM_MISMATCH","severity":"CRITICAL","source":"bitnet.runner","payload":{"runtime_features":38,"model_input_dim":35,"model_schema_version":"bitnet_v3","model_feature_order_hash":"f1e2d3c4b5a69708"}}
```

### 9. Performance impact analysis
- `emit_integrity_event` is one append-only `fh.write(json.dumps(...))` per event. Same cost as existing `engine_telemetry._append_jsonl`. Negligible (<50µs typical).
- Replay simulation is O(candles) per trade; was previously O(1) but tautological. New cost ≈ candle-loop already paid by `BacktestRunner` for the same trades.
- JSONL counters add one integer increment and one division per file load. Imperceptible.
- Session-unknown branch: one extra `dict in` check per candle on the cold path; hot path (known sessions) is unchanged.
- BitNet load: one extra dict normalization at load (per process). One hash compare. Inference path unchanged.

### 10. Remaining unfixed risks
- **Replay coverage gap**: nothing in the current codebase actually constructs the rich trade dict from `trade_journal.jsonl` — that schema lacks entry/SL/TP/direction. Until a caller (likely a new audit pipeline) is built, the replay validator only catches mismatches when callers feed it from `BacktestRunner`'s in-memory `Trade` objects. The integrity events make this gap **visible** (`REPLAY_TRADE_INCOMPLETE` count climbs) but don't close it.
- **Test fixtures**: existing tests that exercised the stub `replay_single_trade` will now hit `REPLAY_TRADE_INCOMPLETE` paths unless their fixtures are extended. Implementation should update fixtures alongside the code patch; this plan flags it but doesn't enumerate them.
- **Legacy 6-input feature mapping**: the `legacy_6input` bridge in `BitNetRunner` will need to pluck the six fields by name from the model's `feature_order`. If a deployed legacy model's `feature_order` is somehow missing, the runner raises — this is fail-closed by design but may surprise an operator whose model file was hand-edited.
- **Cross-process race on `logs/integrity_events.jsonl`**: append-only mode on POSIX is atomic for small writes, but on Windows two simultaneous appenders can interleave. Acceptable given the spec ("never throws, fallback stderr print"). A future improvement could route through a single writer thread; out of scope here.
- **`SESSION_MAP` upstream callers**: any code path that reads `features["session"]` and treats `< 0` as a sentinel will need to handle `-1.0`. The change is small but downstream consumers (zone-gate, scoring) should be grep'd for `features["session"] >= 0` patterns during implementation. Not enumerated in this plan to avoid scope creep — flagged as a verification step.
- **`assistant_project.md` session log**: CLAUDE.md mandates a SESSION LOG ENTRY appended on every response. This plan-mode session writes only the plan file per Plan-mode rules; the session log entry should be appended in the **implementation** session, not here.
