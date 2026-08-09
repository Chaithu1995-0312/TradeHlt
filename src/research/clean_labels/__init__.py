"""Clean-label builders for TradeNet + EnvelopeNet (GATE-L / ENV-L research tooling).

Authority: research datasets only. Grants no spine wire, no train promote, no KEEP/RETIRE.
Primary y is always path-derived via forward_walk / horizon_excursion — never stream outcome/mfe.
"""
from research.clean_labels.builder import (
    BuildConfig,
    BuildResult,
    build_dataset,
    label_one_unit,
    write_dataset_artifacts,
)
from research.clean_labels.protocol import (
    PROTOCOL_ID,
    TP2_POLICY,
    compute_protocol_hash,
    freeze_block,
)

__all__ = [
    "BuildConfig",
    "BuildResult",
    "PROTOCOL_ID",
    "TP2_POLICY",
    "build_dataset",
    "compute_protocol_hash",
    "freeze_block",
    "label_one_unit",
    "write_dataset_artifacts",
]
