"""Agent tool-registration modes (pipeline, copilot, governance, findings, log-query, ops)."""

# Import all mode modules to trigger @register_tool registrations
from . import pipeline_mode  # noqa: F401
from . import copilot_mode   # noqa: F401
from . import governance_mode  # noqa: F401
from . import findings_mode   # noqa: F401
from . import log_query_mode  # noqa: F401
from . import ops_mode  # noqa: F401 — GrokAgenticAI OpsDoctor
from . import truth_mode  # noqa: F401 — GrokAgenticAI TruthJanitor
