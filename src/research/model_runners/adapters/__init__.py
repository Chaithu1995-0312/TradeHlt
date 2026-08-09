"""Model adapters — call production engines only."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from research.model_runners.contracts import ModelContract, get_contract
from research.model_runners.substrate import BarContext


class ModelAdapter(Protocol):
    contract: ModelContract
    config_sections_read: list[str]
    config_keys_read: list[str]
    artifact_info: dict[str, Any] | None

    def score_bar(self, bar: BarContext) -> dict[str, Any]:
        ...


def build_adapter(
    model_id: str,
    *,
    prod_config: dict[str, Any],
    instrument: str,
    repo_root: Path,
    artifact: Path | None = None,
    emit: str | None = None,
    ohlcv_csv: Path | None = None,
) -> ModelAdapter:
    contract = get_contract(model_id)
    if not contract.runnable:
        raise RuntimeError(
            f"model_id={model_id!r} is catalogued but not runnable "
            f"({contract.audit_status}): {contract.description}"
        )

    if model_id == "rr":
        from research.model_runners.adapters.rr_polarity import RRPolarityAdapter

        return RRPolarityAdapter(contract=contract, prod_config=prod_config)
    if model_id in ("regime", "trap", "breakout"):
        from research.model_runners.adapters.dual_engine import build_dual_adapter

        return build_dual_adapter(
            model_id, contract=contract, prod_config=prod_config
        )
    if model_id == "decision":
        from research.model_runners.adapters.decision import DecisionAdapter

        return DecisionAdapter(
            contract=contract,
            prod_config=prod_config,
            instrument=instrument,
            repo_root=repo_root,
        )
    if model_id == "execution_plan":
        from research.model_runners.adapters.execution_plan import (
            ExecutionPlanAdapter,
        )

        return ExecutionPlanAdapter(
            contract=contract,
            prod_config=prod_config,
            instrument=instrument,
            repo_root=repo_root,
        )
    if model_id == "gaussian":
        from research.model_runners.adapters.gaussian import GaussianAdapter

        return GaussianAdapter(
            contract=contract, prod_config=prod_config, instrument=instrument
        )
    if model_id == "zone_gate":
        from research.model_runners.adapters.zone_gate import ZoneGateAdapter

        return ZoneGateAdapter(
            contract=contract, prod_config=prod_config, repo_root=repo_root
        )
    if model_id == "crt_score":
        from research.model_runners.adapters.crt_score import CrtScoreAdapter

        return CrtScoreAdapter(contract=contract, prod_config=prod_config)
    if model_id == "fusion_compute":
        from research.model_runners.adapters.fusion_compute import FusionComputeAdapter

        return FusionComputeAdapter(
            contract=contract,
            prod_config=prod_config,
            instrument=instrument,
            repo_root=repo_root,
        )
    if model_id == "bitnet":
        from research.model_runners.adapters.bitnet import BitNetAdapter

        return BitNetAdapter(contract=contract, prod_config=prod_config)
    if model_id == "tradenet":
        if artifact is None:
            raise ValueError("tradenet requires --artifact")
        from research.model_runners.adapters.tradenet import TradeNetAdapter

        return TradeNetAdapter(
            contract=contract,
            prod_config=prod_config,
            artifact=artifact,
            instrument=instrument,
        )
    if model_id == "rr_trained":
        if artifact is None:
            raise ValueError("rr_trained requires --artifact")
        from research.model_runners.adapters.rr_trained import RRTrainedAdapter

        return RRTrainedAdapter(
            contract=contract, prod_config=prod_config, artifact=artifact
        )
    if model_id == "crt_state_machine":
        if ohlcv_csv is None:
            raise ValueError("crt_state_machine requires ohlcv_csv path")
        if emit is None:
            raise ValueError("crt_state_machine requires --emit events|all")
        from research.model_runners.adapters.crt_state_machine import (
            CrtStateMachineAdapter,
        )

        return CrtStateMachineAdapter(
            contract=contract,
            prod_config=prod_config,
            instrument=instrument,
            ohlcv_csv=ohlcv_csv,
            emit=emit,
        )
    if model_id == "gaussian_ml":
        if artifact is None:
            raise ValueError(
                "gaussian_ml requires --artifact (trained GaussianNB json under models/)"
            )
        from research.model_runners.adapters.gaussian_ml import GaussianMLAdapter

        return GaussianMLAdapter(
            contract=contract,
            prod_config=prod_config,
            artifact=artifact,
            instrument=instrument,
            repo_root=repo_root,
        )
    if model_id == "envelope":
        if artifact is None:
            raise ValueError(
                "envelope requires --artifact (bundle dir or envelope_bundle.json)"
            )
        from research.model_runners.adapters.envelope_net import EnvelopeNetAdapter

        return EnvelopeNetAdapter(
            contract=contract,
            prod_config=prod_config,
            artifact=artifact,
            repo_root=repo_root,
        )
    raise KeyError(f"no adapter for model_id={model_id!r}")
