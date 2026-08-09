"""Per-model historical offline runners (OBSERVATION_ONLY).

Authority: research only. No promote, retrain, or production wire-up.
Zero silent defaults: every required value comes from CLI or production config.
"""

from research.model_runners.contracts import MODEL_CATALOG, list_models
from research.model_runners.runner import run_model

__all__ = ["MODEL_CATALOG", "list_models", "run_model"]
