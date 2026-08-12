"""Canonical contracts for OSS Lab evidence normalization."""

from oss_lab.contracts.trade_record import (
    BenchmarkTradeRecord,
    FieldProvenance,
    Presence,
    Side,
)
from oss_lab.contracts.dataset_manifest import DatasetManifest
from oss_lab.contracts.run_manifest import RunManifest, EnvironmentFingerprint
from oss_lab.contracts.metric_cell import MetricCell, MetricStatus
from oss_lab.contracts.fill_model import FillModelDeclaration
from oss_lab.contracts.structural_fact import StructuralFactRecord

__all__ = [
    "BenchmarkTradeRecord",
    "FieldProvenance",
    "Presence",
    "Side",
    "DatasetManifest",
    "RunManifest",
    "EnvironmentFingerprint",
    "MetricCell",
    "MetricStatus",
    "FillModelDeclaration",
    "StructuralFactRecord",
]
