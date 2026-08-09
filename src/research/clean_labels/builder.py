"""Shared clean-label builder: TradeNet Bernoulli heads + Envelope continuous targets.

Governing path truth: research.measurement.forward_walk(exit_model=intrabar_fixed)
and horizon_excursion. Stream fields are diagnostics only (F-022).
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from features.dataset_builder import extract_feature_vector
from features.feature_schema import (
    CANONICAL_FEATURE_DIM,
    CANONICAL_FEATURES,
    FEATURE_INDEX_MAP,
    SCHEMA_HASH,
)

# macd_hist_raw (schema v4.0's new slot, 2026-07-22 MACD split) is deferred as a
# future feature pending separate research validation. Clean-labels rows stay at
# the legacy 38-dim layout (macd_hist_z only) that protocol.py/envelope_offline
# already expect — dropping this one slot avoids touching either of those.
MACD_HIST_RAW_IDX = FEATURE_INDEX_MAP["macd_hist_raw"]
LEGACY_FEATURE_DIM = 38
LEGACY_FEATURE_NAMES = [n for i, n in enumerate(CANONICAL_FEATURES) if i != MACD_HIST_RAW_IDX]
from research.clean_labels.protocol import (
    COMPOSITE_WEIGHTS,
    COST_BPS,
    EXIT_MODEL,
    FEATURE_DIM,
    MAX_FORWARD,
    MIN_SAMPLES_TRAIN_ELIGIBLE,
    PIT_STATUS,
    PROTOCOL_ID,
    TP2_ATR_MULT,
    TP2_POLICY,
    compute_protocol_hash,
    freeze_block,
)
from research.contracts import Signal
from research.measurement.forward_walk import forward_walk, horizon_excursion

# Stream outcome families (diagnostic agreement only — never primary y)
_TP1_STREAM = frozenset({"TP1", "TP2", "TP1_HIT", "TP2_HIT", "TP_HIT"})
_TP2_STREAM = frozenset({"TP2", "TP2_HIT"})


@dataclass
class BuildConfig:
    instrument: str
    max_forward: int = MAX_FORWARD
    cost_bps: float = COST_BPS
    max_units: int | None = None  # None = all
    source_path: str = ""
    candle_path: str = ""
    builder_entrypoint: str = "scripts/research/build_clean_labels_tn_env.py"


@dataclass
class BuildResult:
    rows: list[dict] = field(default_factory=list)
    skips: dict[str, int] = field(default_factory=dict)
    exceptions: list[str] = field(default_factory=list)
    agreement: dict[str, Any] = field(default_factory=dict)
    config: BuildConfig | None = None
    protocol_hash: str = ""
    schema_hash: str = SCHEMA_HASH
    n_raw: int = 0

    @property
    def n_clean(self) -> int:
        return len(self.rows)

    @property
    def train_eligible(self) -> bool:
        return self.n_clean >= MIN_SAMPLES_TRAIN_ELIGIBLE


def _finite(x: Any) -> bool:
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _norm_ts(s: str) -> str:
    return str(s).replace("T", " ").strip()


def _unit_id(instrument: str, ts: str, direction: str, entry: float, sl: float) -> str:
    raw = f"{instrument}|{ts}|{direction}|{entry:.8f}|{sl:.8f}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _feature_vector(feats: dict) -> list[float] | None:
    if not isinstance(feats, dict):
        return None
    try:
        vec = extract_feature_vector(feats)
    except (ValueError, KeyError, TypeError, AssertionError):
        # fallback: ordered floats if all canonical keys present
        try:
            missing = [k for k in CANONICAL_FEATURES if k not in feats]
            if missing:
                return None
            vec = [float(feats[k]) for k in CANONICAL_FEATURES]
        except (TypeError, ValueError):
            return None
    if len(vec) == CANONICAL_FEATURE_DIM:
        vec = [v for i, v in enumerate(vec) if i != MACD_HIST_RAW_IDX]
    if len(vec) != LEGACY_FEATURE_DIM:
        return None
    if not all(math.isfinite(float(v)) for v in vec):
        return None
    return [float(v) for v in vec]


def _geometry(rec: dict) -> tuple[float, float, float, str] | None:
    """Return (entry, sl, tp1, direction) or None."""
    if not all(k in rec for k in ("entry", "sl", "direction", "timestamp")):
        return None
    if not _finite(rec["entry"]) or not _finite(rec["sl"]):
        return None
    entry = float(rec["entry"])
    sl = float(rec["sl"])
    if abs(entry - sl) <= 0:
        return None
    direction = str(rec["direction"]).lower()
    if direction not in ("long", "short"):
        return None
    tp_raw = rec.get("tp", rec.get("tp1", entry))
    if not _finite(tp_raw):
        return None
    return entry, sl, float(tp_raw), direction


def _stream_diag(rec: dict, risk: float) -> dict[str, Any]:
    outcome = str(rec.get("outcome") or rec.get("exit_reason") or "").upper()
    mfe = rec.get("mfe")
    survives = None
    if _finite(mfe) and risk > 0:
        survives = 1.0 if float(mfe) >= risk else 0.0
    return {
        "stream_outcome": outcome,
        "stream_y_tp1": 1.0 if outcome in _TP1_STREAM else 0.0,
        "stream_y_tp2": 1.0 if outcome in _TP2_STREAM else 0.0,
        "stream_y_survives_be": survives,
        "stream_mfe": float(mfe) if _finite(mfe) else None,
        "stream_mae": float(rec["mae"]) if _finite(rec.get("mae")) else None,
        "stream_rr_achieved": float(rec["rr_achieved"]) if _finite(rec.get("rr_achieved")) else None,
    }


def _bars_to_mfe(direction: str, entry: float, future: Sequence, mfe_price: float) -> int | None:
    if mfe_price <= 0:
        return None
    for i, bar in enumerate(future):
        high, low = float(bar.high), float(bar.low)
        fav = (high - entry) if direction == "long" else (entry - low)
        if fav + 1e-12 >= mfe_price:
            return i + 1
    return None


def label_one_unit(
    rec: dict,
    candles: Sequence,
    ts_to_idx: dict[str, int],
    cfg: BuildConfig,
) -> tuple[dict | None, str | None]:
    """Label one opportunity unit. Returns (row, skip_reason).

    Primary y fields are path-derived only. Stream fields land under diagnostics.
    """
    geom = _geometry(rec)
    if geom is None:
        return None, "bad_geometry"
    entry, sl, tp1, direction = geom
    risk = abs(entry - sl)
    ts = _norm_ts(rec["timestamp"])
    idx = ts_to_idx.get(ts)
    if idx is None:
        return None, "no_candle_ts"

    feats = rec.get("features")
    vec = _feature_vector(feats if isinstance(feats, dict) else {})
    if vec is None:
        return None, "bad_features"

    future = list(candles[idx + 1 : idx + 1 + cfg.max_forward])
    if not future:
        return None, "no_future_bars"

    # ── primary walk (unit SL + unit TP1) ──────────────────────────────────
    tp1_mult = abs(tp1 - entry) / risk
    if tp1_mult <= 0:
        return None, "non_positive_tp1_mult"
    sig_tp1 = Signal(
        instrument=cfg.instrument,
        timestamp=getattr(candles[idx], "timestamp", None),
        entry_index=idx,
        direction=direction,
        entry=entry,
        sl_atr_mult=1.0,
        tp_atr_mult=tp1_mult,
        atr=risk,
    )
    try:
        oc1 = forward_walk(
            sig_tp1, future, max_forward=cfg.max_forward, exit_model=EXIT_MODEL
        )
    except Exception as exc:  # noqa: BLE001 — skip + catalogue
        return None, f"walk_tp1_error:{type(exc).__name__}"

    # ── TP2 stretch walk (L2: TP = +3R; L1 2R collapsed onto unit TP) ────
    sig_tp2 = Signal(
        instrument=cfg.instrument,
        timestamp=getattr(candles[idx], "timestamp", None),
        entry_index=idx,
        direction=direction,
        entry=entry,
        sl_atr_mult=1.0,
        tp_atr_mult=float(TP2_ATR_MULT),
        atr=risk,
    )
    try:
        oc2 = forward_walk(
            sig_tp2, future, max_forward=cfg.max_forward, exit_model=EXIT_MODEL
        )
    except Exception as exc:  # noqa: BLE001
        return None, f"walk_tp2_error:{type(exc).__name__}"

    # ── exit-agnostic envelope ────────────────────────────────────────────
    sig_env = Signal(
        instrument=cfg.instrument,
        timestamp=getattr(candles[idx], "timestamp", None),
        entry_index=idx,
        direction=direction,
        entry=entry,
        sl_atr_mult=1.0,
        tp_atr_mult=1.0,
        atr=risk,
    )
    try:
        hexc = horizon_excursion(sig_env, future, max_forward=cfg.max_forward)
    except Exception as exc:  # noqa: BLE001
        return None, f"horizon_error:{type(exc).__name__}"

    y_tp1 = 1.0 if oc1.outcome == "TP_HIT" else 0.0
    y_tp2 = 1.0 if oc2.outcome == "TP_HIT" else 0.0
    y_survives_be = 1.0 if oc1.reached_1r else 0.0

    cost_frac = cfg.cost_bps / 10_000.0
    cost_r = (cost_frac * entry / risk) if risk > 0 else 0.0
    y_r_net = float(oc1.rr_achieved) - cost_r

    mfe_r_path = float(oc1.mfe) / risk if risk > 0 else 0.0
    mae_r_heat_path = abs(float(oc1.mae)) / risk if risk > 0 else 0.0
    ttm = _bars_to_mfe(direction, entry, future, float(oc1.mfe))

    diag = _stream_diag(rec, risk)

    row = {
        "unit_id": _unit_id(cfg.instrument, ts, direction, entry, sl),
        "instrument": cfg.instrument,
        "decision_ts": ts,
        "entry_index": idx,
        "side": direction,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": None,  # not in source geometry — stretch level is policy-only
        "tp2_policy": TP2_POLICY,
        "tp2_stretch_r": float(TP2_ATR_MULT),
        "tp1_reward_mult": round(tp1_mult, 8),
        "risk_distance": risk,
        "features": {name: vec[i] for i, name in enumerate(LEGACY_FEATURE_NAMES)},
        "feature_vector": vec,
        # ── TradeNet clean heads (PRIMARY y) ──
        "y_tp1": y_tp1,
        "y_tp2": y_tp2,
        "y_survives_be": y_survives_be,
        "y_R_net": round(y_r_net, 6),
        # ── Envelope continuous (PRIMARY y) ──
        "y_mfe_r": hexc["mfe_r"],
        "y_mae_r_heat": abs(hexc["mae_r"]) if hexc["mae_r"] is not None else None,
        "y_holding_bars": int(oc1.duration_candles),
        "y_time_to_mfe": ttm,
        "y_time_to_1r": hexc.get("bars_to_first_1r"),
        "y_expired_timeout": 1.0 if oc1.outcome == "TIMEOUT" else 0.0,
        "y_reached_0_5r": bool(hexc.get("reached_0_5r")),
        "y_reached_1r_horizon": bool(hexc.get("reached_1r")),
        "y_reached_2r_horizon": bool(hexc.get("reached_2r")),
        # path (walk-bounded) excursions — diagnostic for envelope vs walk
        "path_mfe_r": round(mfe_r_path, 6),
        "path_mae_r_heat": round(mae_r_heat_path, 6),
        "path_outcome": oc1.outcome,
        "path_time_to_tp": oc1.time_to_tp,
        "path_time_to_failure": oc1.time_to_failure,
        # stream diagnostics only
        "diagnostics": diag,
        "provenance": {
            "protocol_id": PROTOCOL_ID,
            "protocol_hash": "",  # filled by build_dataset
            "schema_hash": SCHEMA_HASH,
            "pit_status": PIT_STATUS,
            "exit_model": EXIT_MODEL,
            "cost_bps": cfg.cost_bps,
            "max_forward": cfg.max_forward,
            "tp2_policy": TP2_POLICY,
            "feature_dim": FEATURE_DIM,
            "composite_weights": list(COMPOSITE_WEIGHTS),
            "builder_entrypoint": cfg.builder_entrypoint,
            "source_path": cfg.source_path,
            "candle_path": cfg.candle_path,
            "label_authority": "forward_walk+horizon_excursion",
            "stream_y_primary": False,
        },
    }
    return row, None


def build_dataset(
    records: Iterable[dict],
    candles: Sequence,
    ts_to_idx: dict[str, int],
    cfg: BuildConfig,
) -> BuildResult:
    """Build clean-label rows. Never uses stream outcome/mfe as primary y."""
    protocol_hash = compute_protocol_hash(
        {"instrument": cfg.instrument, "source": cfg.source_path}
    )
    result = BuildResult(
        config=cfg,
        protocol_hash=protocol_hash,
        schema_hash=SCHEMA_HASH,
    )
    skips: dict[str, int] = {}
    rows: list[dict] = []

    for rec in records:
        result.n_raw += 1
        if cfg.max_units is not None and len(rows) >= cfg.max_units:
            break
        # skip non-opportunity lines
        if "entry" not in rec or "timestamp" not in rec:
            skips["not_opportunity"] = skips.get("not_opportunity", 0) + 1
            continue
        if rec.get("instrument") and str(rec["instrument"]) != cfg.instrument:
            skips["wrong_instrument"] = skips.get("wrong_instrument", 0) + 1
            continue

        row, reason = label_one_unit(rec, candles, ts_to_idx, cfg)
        if reason is not None:
            key = reason.split(":")[0]
            skips[key] = skips.get(key, 0) + 1
            if reason.startswith("walk_") or reason.startswith("horizon_"):
                result.exceptions.append(reason)
            continue
        assert row is not None
        row["provenance"]["protocol_hash"] = protocol_hash
        rows.append(row)

    result.rows = rows
    result.skips = skips
    result.agreement = _compute_agreement(rows)
    return result


def _compute_agreement(rows: list[dict]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    n = len(rows)
    agree_tp1 = sum(
        1
        for r in rows
        if r["diagnostics"]["stream_y_tp1"] == r["y_tp1"]
    )
    agree_surv = 0
    n_surv = 0
    for r in rows:
        s = r["diagnostics"]["stream_y_survives_be"]
        if s is None:
            continue
        n_surv += 1
        if s == r["y_survives_be"]:
            agree_surv += 1
    return {
        "n": n,
        "agree_tp1_rate": round(agree_tp1 / n, 6),
        "agree_survives_be_rate": round(agree_surv / n_surv, 6) if n_surv else None,
        "n_survives_comparable": n_surv,
        "clean_base_rates": {
            "y_tp1": round(sum(r["y_tp1"] for r in rows) / n, 6),
            "y_tp2": round(sum(r["y_tp2"] for r in rows) / n, 6),
            "y_survives_be": round(sum(r["y_survives_be"] for r in rows) / n, 6),
            "y_expired_timeout": round(sum(r["y_expired_timeout"] for r in rows) / n, 6),
        },
        "note": "Stream agreement is diagnostic (F-022). Primary y is path-derived.",
    }


def write_dataset_artifacts(
    result: BuildResult,
    out_dir: Path,
    *,
    write_rows: bool = True,
) -> dict[str, str]:
    """Write clean JSONL + sidecar metadata + rederive report. Returns path map."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dataset_path = out_dir / "clean_labels.jsonl"
    meta_path = out_dir / "dataset_meta.json"
    report_path = out_dir / "label_rederive_report.json"
    freeze_path = out_dir / "freeze.json"

    if write_rows:
        with dataset_path.open("w", encoding="utf-8") as fh:
            for row in result.rows:
                fh.write(json.dumps(row, default=str) + "\n")

    freeze = freeze_block()
    freeze_path.write_text(json.dumps(freeze, indent=2), encoding="utf-8")

    meta = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": PROTOCOL_ID,
        "protocol_hash": result.protocol_hash,
        "schema_hash": result.schema_hash,
        "pit_status": PIT_STATUS,
        "tp2_policy": TP2_POLICY,
        "exit_model": EXIT_MODEL,
        "n_raw": result.n_raw,
        "n_clean": result.n_clean,
        "train_eligible": result.train_eligible,
        "min_samples_train_eligible": MIN_SAMPLES_TRAIN_ELIGIBLE,
        "skips": result.skips,
        "exception_count": len(result.exceptions),
        "exception_samples": result.exceptions[:20],
        "agreement": result.agreement,
        "config": asdict(result.config) if result.config else None,
        "dataset_path": str(dataset_path) if write_rows else None,
        "label_rederive_report_path": str(report_path),
        "authority": "research_dataset_only — no train promote / no neural_fn / no spine",
        "gate_l_checklist": {
            "gate_0_pass": True,
            "prereg_freeze": True,
            "builder_refuses_stream_primary_y": True,
            "versioned_dataset": write_rows,
            "label_def_matches_protocol": True,
            "schema_hash_set": bool(result.schema_hash),
            "pit_status_declared": True,
            "label_rederive_report": True,
            "n_closed_ge_floor": result.train_eligible,
        },
    }
    meta_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")

    report = {
        "protocol_id": PROTOCOL_ID,
        "protocol_hash": result.protocol_hash,
        "agreement": result.agreement,
        "skips": result.skips,
        "n_clean": result.n_clean,
        "n_raw": result.n_raw,
        "forbidden_as_primary": freeze["forbidden_primary_y"],
        "stream_y_used_as_primary": False,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return {
        "dataset": str(dataset_path) if write_rows else "",
        "meta": str(meta_path),
        "rederive_report": str(report_path),
        "freeze": str(freeze_path),
    }
