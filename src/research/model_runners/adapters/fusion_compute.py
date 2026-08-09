"""Compose four live engines → FusionEngine.compute (no DecisionEngine)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.fusion_engine import FusionConfig, FusionEngine, GaussianAdapter
from research.model_runners.adapters.crt_score import CrtScoreAdapter
from research.model_runners.adapters.gaussian import GaussianAdapter as LiveGaussian
from research.model_runners.adapters.rr_polarity import RRPolarityAdapter
from research.model_runners.adapters.zone_gate import ZoneGateAdapter
from research.model_runners.contracts import ModelContract, get_contract
from research.model_runners.require_config import require_key, require_section
from research.model_runners.substrate import BarContext


class FusionComputeAdapter:
    def __init__(
        self,
        *,
        contract: ModelContract,
        prod_config: dict[str, Any],
        instrument: str,
        repo_root: Path,
    ):
        self.contract = contract
        fe = require_section(prod_config, "fusion_engine")
        # Build FusionConfig with production weights only (no dataclass default reliance).
        cfg = FusionConfig(
            weight_crt=float(require_key(fe, "weight_crt", path="fusion_engine")),
            weight_gaussian=float(
                require_key(fe, "weight_gaussian", path="fusion_engine")
            ),
            weight_zone_gate=float(
                require_key(fe, "weight_zone_gate", path="fusion_engine")
            ),
            weight_rr=float(require_key(fe, "weight_rr", path="fusion_engine")),
            gaussian_weight=float(
                require_key(fe, "gaussian_weight", path="fusion_engine")
            ),
            neural_weight=float(require_key(fe, "neural_weight", path="fusion_engine")),
            llm_weight=float(require_key(fe, "llm_weight", path="fusion_engine")),
            llm_lower_band=float(
                require_key(fe, "llm_lower_band", path="fusion_engine")
            ),
            llm_upper_band=float(
                require_key(fe, "llm_upper_band", path="fusion_engine")
            ),
            enable_llm=bool(require_key(fe, "enable_llm", path="fusion_engine")),
            tier_full=float(require_key(fe, "tier_full", path="fusion_engine")),
            tier_half=float(require_key(fe, "tier_half", path="fusion_engine")),
            tier_quarter=float(require_key(fe, "tier_quarter", path="fusion_engine")),
            conflict_resolution_policy=str(
                require_key(fe, "conflict_resolution_policy", path="fusion_engine")
            ),
            min_consensus_signals=int(
                require_key(fe, "min_consensus_signals", path="fusion_engine")
            ),
            min_consensus_agreement=float(
                require_key(fe, "min_consensus_agreement", path="fusion_engine")
            ),
        )
        # compute() does not call gaussian_adapter; still required by constructor.
        live_g = LiveGaussian(
            contract=get_contract("gaussian"),
            prod_config=prod_config,
            instrument=instrument,
        )
        self._fusion = FusionEngine(
            # R5: public accessor, not `live_g._engine` private reach.
            gaussian_adapter=GaussianAdapter(live_g.engine),
            neural_fn=None,
            llm_fn=None,
            config=cfg,
        )
        self._crt = CrtScoreAdapter(
            contract=get_contract("crt_score"), prod_config=prod_config
        )
        self._gauss = live_g
        self._zone = ZoneGateAdapter(
            contract=get_contract("zone_gate"),
            prod_config=prod_config,
            repo_root=repo_root,
        )
        self._rr = RRPolarityAdapter(
            contract=get_contract("rr"), prod_config=prod_config
        )

        sections = set()
        keys: list[str] = []
        for ad in (self._crt, self._gauss, self._zone, self._rr):
            sections.update(ad.config_sections_read)
            keys.extend(ad.config_keys_read)
        sections.add("fusion_engine")
        keys.extend(
            [
                "fusion_engine.weight_crt",
                "fusion_engine.weight_gaussian",
                "fusion_engine.weight_zone_gate",
                "fusion_engine.weight_rr",
                "fusion_engine.gaussian_weight",
                "fusion_engine.neural_weight",
                "fusion_engine.llm_weight",
                "fusion_engine.llm_lower_band",
                "fusion_engine.llm_upper_band",
                "fusion_engine.enable_llm",
                "fusion_engine.tier_full",
                "fusion_engine.tier_half",
                "fusion_engine.tier_quarter",
                "fusion_engine.conflict_resolution_policy",
                "fusion_engine.min_consensus_signals",
                "fusion_engine.min_consensus_agreement",
            ]
        )
        self.config_sections_read = sorted(sections)
        self.config_keys_read = keys
        self.artifact_info = {
            "path": None,
            "note": "compose of four live engines + FusionEngine.compute",
            "neural_fn": None,
            "llm_fn": None,
            "zone_artifact": self._zone.artifact_info,
        }
        self._weights = {
            "crt": cfg.weight_crt,
            "gaussian": cfg.weight_gaussian,
            "zone_gate": cfg.weight_zone_gate,
            "rr": cfg.weight_rr,
        }

    def score_bar(self, bar: BarContext) -> dict[str, Any]:
        crt_n = self._crt.score_bar(bar)
        g_n = self._gauss.score_bar(bar)
        z_n = self._zone.score_bar(bar)
        rr_n = self._rr.score_bar(bar)
        engine_results = {
            "crt": crt_n,
            "gaussian": g_n,
            "zone_gate": z_n,
            "rr": rr_n,
        }
        fused = self._fusion.compute(engine_results)
        if not isinstance(fused, dict):
            raise TypeError(f"FusionEngine.compute must return dict, got {type(fused)}")
        out = dict(fused)
        out["component_native"] = {
            "crt": crt_n,
            "gaussian": g_n,
            "zone_gate": {
                k: z_n[k]
                for k in z_n
                if k in ("score", "passed", "best_zone_id", "cluster_score")
            },
            "rr": rr_n,
        }
        out["weights_used"] = dict(self._weights)
        if "score" not in out and "final_score" in out:
            out["score"] = out["final_score"]
        return out
