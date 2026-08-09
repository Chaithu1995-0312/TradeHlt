"""Production ZoneGate cluster scorer adapter."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from config_layer.model_resolver import resolve_zone_gate_runtime
from engines.live_engine import BitNetZoneGate
from engines.zone_cluster_score import score_zone_cluster
from features.feature_schema import CANONICAL_FEATURES
from research.model_runners.contracts import ModelContract
from research.model_runners.require_config import require_key, require_section, sha256_file
from research.model_runners.substrate import BarContext


class ZoneGateAdapter:
    def __init__(
        self,
        *,
        contract: ModelContract,
        prod_config: dict[str, Any],
        repo_root: Path,
    ):
        self.contract = contract
        er = require_section(prod_config, "engine_runner")
        zone_registry_path = str(
            require_key(er, "zone_registry_path", path="engine_runner")
        )
        zone_min_samples = int(
            require_key(er, "zone_min_samples", path="engine_runner")
        )
        zone_cluster_threshold = float(
            require_key(er, "zone_cluster_threshold", path="engine_runner")
        )
        execution_mode = str(
            require_key(er, "zone_gate_execution_mode", path="engine_runner")
        )
        zone_gate_cfg = require_key(er, "zone_gate", path="engine_runner")
        if not isinstance(zone_gate_cfg, dict):
            raise KeyError(
                "engine_runner.zone_gate must be a mapping, "
                f"got {type(zone_gate_cfg).__name__}"
            )
        top_k = int(require_key(zone_gate_cfg, "top_k", path="engine_runner.zone_gate"))
        cluster_min_n = int(
            require_key(zone_gate_cfg, "cluster_min_n", path="engine_runner.zone_gate")
        )
        cluster_spread_max = float(
            require_key(
                zone_gate_cfg, "cluster_spread_max", path="engine_runner.zone_gate"
            )
        )

        # R2: full 39-float per-bar vector emission is opt-in. Strict read —
        # model_runners.emit_vectors must exist (no soft default).
        mr = require_section(prod_config, "model_runners")
        self._emit_vectors = bool(
            require_key(mr, "emit_vectors", path="model_runners")
        )

        resolved = resolve_zone_gate_runtime(how_path=zone_registry_path)
        artifact_path = Path(resolved.require_artifact())
        if not artifact_path.is_file():
            # resolve may return relative path
            candidate = repo_root / artifact_path
            if candidate.is_file():
                artifact_path = candidate
            else:
                raise FileNotFoundError(
                    f"zone registry artifact missing: {artifact_path}"
                )

        # Construct gate with explicit path + knobs (no get_zone_gate default path).
        self._gate = BitNetZoneGate(
            zone_path=str(artifact_path),
            enabled=True,
            config={
                "zone_min_samples": zone_min_samples,
                "zone_gate_top_k": top_k,
            },
        )
        self._zone_cluster_threshold = zone_cluster_threshold
        self._cluster_min_n = cluster_min_n
        self._cluster_spread_max = cluster_spread_max
        self._execution_mode = execution_mode

        self.config_sections_read = ["engine_runner", "model_runners"]
        self.config_keys_read = [
            "engine_runner.zone_registry_path",
            "engine_runner.zone_min_samples",
            "engine_runner.zone_cluster_threshold",
            "engine_runner.zone_gate_execution_mode",
            "engine_runner.zone_gate",
            "engine_runner.zone_gate.top_k",
            "engine_runner.zone_gate.cluster_min_n",
            "engine_runner.zone_gate.cluster_spread_max",
            "model_runners.emit_vectors",
        ]
        self.artifact_info = {
            "path": str(artifact_path),
            "sha256": sha256_file(artifact_path),
            "how_path": zone_registry_path,
            "emit_vectors": self._emit_vectors,
        }

    def score_bar(self, bar: BarContext) -> dict[str, Any]:
        missing = [k for k in CANONICAL_FEATURES if k not in bar.features]
        if missing:
            raise KeyError(
                f"zone_gate requires full canonical features; missing={missing[:8]}..."
            )
        feat = {k: float(bar.features[k]) for k in CANONICAL_FEATURES}
        native = score_zone_cluster(
            feat,
            self._gate,
            zone_cluster_threshold=self._zone_cluster_threshold,
            cluster_min_n=self._cluster_min_n,
            cluster_spread_max=self._cluster_spread_max,
            execution_mode=self._execution_mode,
            zone_debug_config=None,
        )
        if not isinstance(native, dict):
            raise TypeError(
                f"score_zone_cluster must return dict, got {type(native)}"
            )
        return _json_safe_zone(native, emit_vectors=self._emit_vectors)


def _json_safe_zone(
    native: dict[str, Any], *, emit_vectors: bool
) -> dict[str, Any]:
    """Ensure zone result is JSON-serializable without inventing fields.

    R2: the scored vector is the model's INPUT, not its output, and is fully
    derivable from the bar. Emitting all 39 floats on every bar bloats artifacts
    (~2.7M redundant floats on a 70k-bar run), so it is opt-in via
    ``model_runners.emit_vectors``. ``vector_len`` is always kept so the width
    is auditable either way.
    """
    out: dict[str, Any] = {}
    for k, v in native.items():
        if k == "vector" and isinstance(v, list):
            out["vector_len"] = len(v)
            if emit_vectors:
                out["vector"] = v
        elif isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, list):
            out[k] = v
        elif isinstance(v, dict):
            out[k] = {
                sk: sv
                for sk, sv in v.items()
                if isinstance(sv, (str, int, float, bool, list, type(None)))
                or sv is None
            }
        else:
            out[k] = str(v)
    return out
