"""Engine adapters — map native outputs to BenchmarkTradeRecord.

Production spine must never import this package.
Adapters may import from src/ for reuse; never redefine authority.
"""

from oss_lab.adapters.base import EngineAdapter, AdapterCapability

__all__ = ["EngineAdapter", "AdapterCapability"]
