"""
trade_net_v2.py
═══════════════════════════════════════════════════════════════════════════════
TradeNet v2 — 3-head survival classifier (pure-numpy inference).

Replaces the single-sigmoid binary win/loss head with three independent
sigmoid heads:

  - p_tp1         : probability the trade reaches the TP1 target
  - p_tp2         : probability the trade reaches the TP2 target
  - p_survives_be : probability the trade reaches the breakeven trigger (>= 1R)

Composite score consumed by FusionEngine.neural:

    tradenet_score = 0.4 * p_tp1 + 0.4 * p_tp2 + 0.2 * p_survives_be

Inputs:
  38-dim canonical feature vector (CANONICAL_FEATURE_ORDER).

Model formats accepted:
  - JSON envelope with schema_version == "tradenet_v2" (numpy forward pass)
  - Legacy v1 PyTorch state_dict .pth (38->32->16->1 sigmoid) — bridge mode

Mode contract for callers:
  TradeNetV2.predict(features) returns:
    - dict {tradenet_score, p_tp1, p_tp2, p_survives_be, schema_version}
      with p_* = None for legacy v1 models
    - None when no model is registered for the instrument; emits
      TRADENET_MISSING (CRITICAL) once at construction time. FusionEngine
      already handles None by renormalising remaining engines.
"""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Optional

import numpy as np

log = logging.getLogger("TradeNetV2")

SCHEMA_VERSION_V2 = "tradenet_v2"
COMPOSITE_WEIGHTS = (0.4, 0.4, 0.2)  # p_tp1, p_tp2, p_survives_be


# ─────────────────────────────────────────────────────────────────────────────
# Numpy ops
# ─────────────────────────────────────────────────────────────────────────────

def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(x, 0.0)


# ─────────────────────────────────────────────────────────────────────────────
# TradeNetV2 inference class
# ─────────────────────────────────────────────────────────────────────────────

class TradeNetV2:
    """Per-instrument TradeNet v2 inference.

    Construction modes
    ------------------
    TradeNetV2(model_path=...)
        Load the explicit path. Path extension and JSON ``schema_version``
        decide v2-numpy vs. legacy v1 .pth.

    TradeNetV2(instrument="ETHUSDT")
        Look up the active version in ``TradeNetRegistry`` and load it.
        If no active version exists for the instrument, switches to
        "missing" mode — ``predict`` returns None.
    """

    def __init__(
        self,
        model_path: Optional[str | Path] = None,
        *,
        instrument: Optional[str] = None,
    ) -> None:
        self.instrument: Optional[str] = instrument
        self.model_path: Optional[Path] = Path(model_path) if model_path else None
        self.version: Optional[str] = None
        self.schema_version: str = "unknown"

        # Mode: "v2" (numpy envelope), "legacy_v1" (.pth via torch), "missing"
        self._mode: str = "missing"
        # v2 weights
        self._trunk: list[tuple[np.ndarray, np.ndarray]] = []
        self._heads: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self._scaler_mean: Optional[np.ndarray] = None
        self._scaler_std: Optional[np.ndarray] = None
        self._feature_names: Optional[list[str]] = None
        # legacy v1
        self._v1_model = None
        self._v1_scaler = None
        self._v1_n_features: int = 0

        self._resolve_and_load()

    # ── Path resolution ──────────────────────────────────────────────────────

    def _resolve_and_load(self) -> None:
        if self.model_path is None and self.instrument:
            self._resolve_from_registry()

        if self.model_path is None or not self.model_path.exists():
            self._enter_missing_mode()
            return

        # Decide route by file shape — .pth is always legacy; JSON is inspected.
        suffix = self.model_path.suffix.lower()
        if suffix == ".pth":
            self._load_legacy_v1()
            return

        try:
            envelope = json.loads(self.model_path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.error("TradeNetV2: failed to read envelope %s — %s", self.model_path, exc)
            self._enter_missing_mode()
            return

        if envelope.get("schema_version") == SCHEMA_VERSION_V2:
            self._load_v2_envelope(envelope)
        else:
            # JSON file but wrong / missing schema_version — treat as legacy attempt.
            log.warning(
                "TradeNetV2: envelope %s has schema_version=%r (expected %r). "
                "Attempting legacy bridge.",
                self.model_path, envelope.get("schema_version"), SCHEMA_VERSION_V2,
            )
            self._load_legacy_v1()

    def _resolve_from_registry(self) -> None:
        try:
            from core.model_registry import (
                get_active_tradenet_version,
                get_active_tradenet_entry,
            )
        except Exception as exc:
            log.warning("TradeNetV2: cannot import model_registry — %s", exc)
            return
        version = get_active_tradenet_version(self.instrument or "")
        if not version:
            return
        entry = get_active_tradenet_entry(self.instrument)
        if not entry:
            return
        self.version = version
        mf = entry.get("model_file")
        if mf:
            self.model_path = Path(mf)

    def _enter_missing_mode(self) -> None:
        self._mode = "missing"
        self._emit_event(
            "TRADENET_MISSING", "CRITICAL",
            {
                "instrument": self.instrument,
                "model_path": str(self.model_path) if self.model_path else None,
                "note": "no v2 envelope and no legacy v1 .pth found for instrument; "
                        "TradeNet will return None and FusionEngine will renormalize "
                        "remaining engines.",
            },
        )
        log.error(
            "TradeNetV2: no model resolved for instrument=%r — predict() will return None.",
            self.instrument,
        )

    # ── v2 envelope load (numpy) ─────────────────────────────────────────────

    def _load_v2_envelope(self, envelope: dict) -> None:
        try:
            from features.feature_schema import CANONICAL_FEATURE_DIM
        except Exception:
            CANONICAL_FEATURE_DIM = 38  # noqa: N806


        feature_dim = int(envelope.get("feature_dim", 0))
        if feature_dim != CANONICAL_FEATURE_DIM:
            self._emit_event(
                "TRADENET_V2_FEATURE_DIM_MISMATCH", "CRITICAL",
                {
                    "instrument": self.instrument,
                    "envelope_feature_dim": feature_dim,
                    "expected": CANONICAL_FEATURE_DIM,
                    "model_path": str(self.model_path),
                },
            )
            self._enter_missing_mode()
            return

        self._feature_names = list(envelope.get("feature_names") or [])

        # Trunk: list of {"type": "linear", "weight", "bias"} interleaved with
        # {"type": "relu"} markers. We collect only linear layers — activation is
        # implicit (relu after each linear except the last in trunk; heads have
        # their own sigmoid applied in predict()).
        trunk = []
        for layer in envelope.get("trunk", []):
            if not isinstance(layer, dict):
                continue
            if layer.get("type") == "linear":
                w = np.asarray(layer["weight"], dtype=np.float32)
                b = np.asarray(layer["bias"], dtype=np.float32)
                trunk.append((w, b))
        self._trunk = trunk

        # Heads: dict head_name -> {weight, bias}. weight shape (1, 16); bias (1,).
        heads_raw = envelope.get("heads", {}) or {}
        expected_heads = ("p_tp1", "p_tp2", "p_survives_be")
        for hn in expected_heads:
            h = heads_raw.get(hn)
            if not isinstance(h, dict) or "weight" not in h or "bias" not in h:
                self._emit_event(
                    "TRADENET_V2_HEAD_MISSING", "CRITICAL",
                    {"instrument": self.instrument, "head": hn,
                     "model_path": str(self.model_path)},
                )
                self._enter_missing_mode()
                return
            w = np.asarray(h["weight"], dtype=np.float32)
            b = np.asarray(h["bias"], dtype=np.float32)
            self._heads[hn] = (w, b)

        scaler = envelope.get("scaler") or {}
        if "mean" in scaler and "std" in scaler:
            self._scaler_mean = np.asarray(scaler["mean"], dtype=np.float32)
            self._scaler_std = np.asarray(scaler["std"], dtype=np.float32)
        # std==0 protection
        if self._scaler_std is not None:
            self._scaler_std = np.where(self._scaler_std < 1e-8, 1.0, self._scaler_std)

        self._mode = "v2"
        self.schema_version = SCHEMA_VERSION_V2
        self.version = envelope.get("metadata", {}).get("version") or self.version
        log.info(
            "TradeNetV2: loaded v2 envelope path=%s instrument=%s heads=%s",
            self.model_path, self.instrument, list(self._heads.keys()),
        )

    # ── Legacy v1 bridge (.pth via torch) ────────────────────────────────────

    def _load_legacy_v1(self) -> None:
        try:
            import torch
            from training.trainer import _build_model, load_tradenet_scaler
        except Exception as exc:
            log.error("TradeNetV2: torch unavailable for legacy load — %s", exc)
            self._enter_missing_mode()
            return

        try:
            model = _build_model()
            state = torch.load(self.model_path, map_location="cpu")
            model.load_state_dict(state)
            model.eval()
        except Exception as exc:
            log.error(
                "TradeNetV2: legacy .pth load failed path=%s — %s",
                self.model_path, exc,
            )
            self._enter_missing_mode()
            return

        # Scaler is stored alongside as {stem}_scaler.json in the SAME directory
        # as the .pth (not necessarily MODELS_DIR root). load_tradenet_scaler()
        # expects a name relative to MODELS_DIR — fall back to direct read.
        scaler_path = self.model_path.parent / f"{self.model_path.stem}_scaler.json"
        scaler = None
        if scaler_path.exists():
            try:
                from training.trainer import StandardScaler
                scaler = StandardScaler.from_dict(json.loads(scaler_path.read_text()))
            except Exception as exc:
                log.warning(
                    "TradeNetV2: legacy scaler load failed path=%s — %s",
                    scaler_path, exc,
                )

        # Infer n_features from first linear layer
        try:
            n_features = int(next(model.parameters()).shape[1])
        except Exception:
            n_features = 38

        self._v1_model = model
        self._v1_scaler = scaler
        self._v1_n_features = n_features
        self._mode = "legacy_v1"
        self.schema_version = "legacy_v1"
        self._emit_event(
            "TRADENET_LEGACY_LOAD", "CRITICAL",
            {
                "instrument": self.instrument,
                "model_path": str(self.model_path),
                "n_features": n_features,
                "note": "loaded legacy v1 .pth under bridge; only tradenet_score is "
                        "produced (p_tp1/p_tp2/p_survives_be = None). Train and "
                        "promote a v2 envelope for this instrument to upgrade.",
            },
        )
        log.warning(
            "TradeNetV2: legacy v1 bridge active for instrument=%s path=%s",
            self.instrument, self.model_path,
        )

    # ── Inference ────────────────────────────────────────────────────────────

    def predict(self, features: dict) -> Optional[dict]:
        """Run forward pass.

        Returns
        -------
        dict | None
            ``None`` when no model is available for this instrument (mode=missing).
            For v2 envelopes: full dict with all probabilities and composite.
            For legacy v1 .pth: composite is the single v1 sigmoid; head fields
            are ``None``.
        """
        if self._mode == "missing":
            return None

        try:
            from features.dataset_builder import extract_feature_vector
            vec = extract_feature_vector(features)
        except Exception as exc:
            log.warning("TradeNetV2: feature extraction failed — %s", exc)
            return None

        if self._mode == "v2":
            return self._predict_v2(vec)
        if self._mode == "legacy_v1":
            return self._predict_legacy(vec)
        return None

    def _predict_v2(self, vec: list) -> dict:
        x = np.asarray(vec, dtype=np.float32)
        if self._scaler_mean is not None and self._scaler_std is not None:
            x = (x - self._scaler_mean) / self._scaler_std

        # Trunk: linear -> relu -> linear -> relu  (two linears, relu after each)
        h = x
        for w, b in self._trunk:
            h = _relu(h @ w.T + b)

        scores = {}
        for hn in ("p_tp1", "p_tp2", "p_survives_be"):
            w, b = self._heads[hn]
            logit = float((h @ w.T + b).item()) if w.ndim == 2 else float(h @ w + b)
            scores[hn] = _sigmoid(logit)

        composite = (
            COMPOSITE_WEIGHTS[0] * scores["p_tp1"]
            + COMPOSITE_WEIGHTS[1] * scores["p_tp2"]
            + COMPOSITE_WEIGHTS[2] * scores["p_survives_be"]
        )
        return {
            "tradenet_score": float(composite),
            "p_tp1": float(scores["p_tp1"]),
            "p_tp2": float(scores["p_tp2"]),
            "p_survives_be": float(scores["p_survives_be"]),
            "schema_version": SCHEMA_VERSION_V2,
        }

    def _predict_legacy(self, vec: list) -> dict:
        import torch
        n = self._v1_n_features or len(vec)
        if len(vec) > n:
            vec = vec[:n]
        elif len(vec) < n:
            # Mismatched dimensionality — refuse rather than zero-pad.
            log.error(
                "TradeNetV2 legacy: feature vector len=%d < model n_features=%d",
                len(vec), n,
            )
            return {
                "tradenet_score": 0.5,
                "p_tp1": None, "p_tp2": None, "p_survives_be": None,
                "schema_version": "legacy_v1",
            }
        if self._v1_scaler is not None:
            try:
                vec = self._v1_scaler.transform_one(vec)
            except Exception:
                pass
        try:
            x = torch.tensor(vec, dtype=torch.float32).unsqueeze(0)
            with torch.no_grad():
                score = float(self._v1_model(x).item())
        except Exception as exc:
            log.warning("TradeNetV2 legacy forward failed — %s", exc)
            score = 0.5
        return {
            "tradenet_score": max(0.0, min(1.0, score)),
            "p_tp1": None, "p_tp2": None, "p_survives_be": None,
            "schema_version": "legacy_v1",
        }

    # ── Telemetry ────────────────────────────────────────────────────────────

    def _emit_event(self, event: str, severity: str, payload: dict) -> None:
        try:
            from utils.integrity_events import emit_integrity_event
            emit_integrity_event(event, severity, "trade_net_v2", payload)
        except Exception:
            pass


__all__ = ["TradeNetV2", "SCHEMA_VERSION_V2", "COMPOSITE_WEIGHTS"]
