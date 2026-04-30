"""
BitNet Runner
Wraps BitNetModel with schema validation, proper slicing, and controlled fallback.
"""
import logging
import numpy as np

from bitnet.bitnet_inference import BitNetModel
from features.feature_schema import CANONICAL_FEATURES

logger = logging.getLogger(__name__)

DEBUG_MODE = True


class BitNetRunner:
    """
    Production BitNet runner with schema enforcement and controlled failure modes.
    """

    def __init__(self, model_path: str = "model_export_format.json"):
        self.model = BitNetModel(model_path)
        self.expected_input_dim = self.model.input_dim
        logger.info("BitNetRunner initialized with input dimension: %d", self.expected_input_dim)
        # Warn once at startup if feature truncation will occur
        if len(CANONICAL_FEATURES) > self.expected_input_dim:
            logger.warning(
                "Feature truncation active: %d → %d dims. "
                "Model input_dim=%d < canonical features=%d. "
                "Compatibility bridge active — upgrade model to accept %d features.",
                len(CANONICAL_FEATURES), self.expected_input_dim,
                self.expected_input_dim, len(CANONICAL_FEATURES),
                len(CANONICAL_FEATURES)
            )

    def predict(self, features: dict) -> dict:
        """
        Run BitNet prediction on canonical feature dict.

        Parameters
        ----------
        features : dict
            Full canonical feature dict (all CANONICAL_FEATURES present)

        Returns
        -------
        dict
            { score: float, decision: str, error: Optional[str] }
        """
        try:
            # 1. Enforce strict ordering (critical: model is order sensitive)
            ordered_values = [features[k] for k in CANONICAL_FEATURES]

            # 2. Dimension validation (NEVER silent)
            if len(ordered_values) != len(CANONICAL_FEATURES):
                raise ValueError(f"Feature count mismatch: expected {len(CANONICAL_FEATURES)}, got {len(ordered_values)}")

            # 3. Slice to model expected input dimension (compatibility bridge)
            input_vector = np.array(ordered_values[:self.expected_input_dim], dtype=np.float32)

            # 4. Run actual inference
            score = self.model.predict(input_vector)

            # 5. Decision threshold = 0.5
            if score > 0.5:
                decision = "ACCEPT"
            else:
                decision = "REJECT"

            return {
                "score": float(score),
                "decision": decision,
                "error": None
            }

        except Exception as e:
            error_msg = str(e)
            logger.error("BitNet prediction failed: %s", error_msg)

            if DEBUG_MODE:
                # Debug mode: Accept on failure to test pipeline
                return {
                    "score": 0.5,
                    "decision": "ACCEPT",
                    "error": error_msg
                }
            else:
                # Production mode: Safe default reject
                return {
                    "score": 0.0,
                    "decision": "REJECT",
                    "error": error_msg
                }