"""adapters — bridges that let the isolated research harness consume the live spine.

The ONLY coupling between Pipeline-B (research) and Pipeline-A (the production decision
spine) lives here, and it points strictly DOWN the decision flow: the adapter imports the
spine as a proven primitive (exactly as the rest of research imports `CandleLoader`); the
spine never imports — and never learns of — research. This preserves Goal invariant #5
("execution authority stays isolated") and the service-boundary hard rule.
"""

from research.adapters.spine_signal_source import (  # noqa: F401
    ProductionSpineSource,
    SpineEntry,
    SpineSignalSource,
)

__all__ = ["ProductionSpineSource", "SpineEntry", "SpineSignalSource"]
