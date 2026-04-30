# override_handler.py — Human-in-loop decision gate
import logging
import time
from typing import Optional

log = logging.getLogger(__name__)

_ACTIONS = {"y": "EXECUTE", "n": "SKIP", "r": "REDUCE"}
_DEFAULT_TIMEOUT = 30
_DEFAULT_REDUCE_FACTOR = 0.5


class OverrideHandler:
    """
    Presents a trade signal to the human operator and waits for a decision.

    Responses:
      y → EXECUTE (full risk)
      n → SKIP
      r → REDUCE (risk × reduce_factor)
      timeout → TIMEOUT_SKIP

    AUTO_EXECUTE = False is the default — system never auto-executes.
    Can be set to True for fully automated mode (testing/paper trading only).

    For testing: inject input_fn to avoid blocking stdin.
    """

    AUTO_EXECUTE: bool = False

    def __init__(
        self,
        timeout: int = _DEFAULT_TIMEOUT,
        reduce_factor: float = _DEFAULT_REDUCE_FACTOR,
        input_fn: Optional[callable] = None,  # inject for testing
    ):
        self.timeout = timeout
        self.reduce_factor = reduce_factor
        self._input_fn = input_fn or input

    def wait_for_decision(self, signal: dict) -> dict:
        """
        Present signal and wait for human decision.

        Returns:
            {"action": "EXECUTE"|"SKIP"|"REDUCE"|"TIMEOUT_SKIP", "factor": float}
        """
        if self.AUTO_EXECUTE:
            log.warning("OverrideHandler: AUTO_EXECUTE=True — bypassing human gate")
            return {"action": "EXECUTE", "factor": 1.0}

        symbol = signal.get("symbol", "?")
        log.info(
            "OverrideHandler: awaiting decision for %s (timeout=%ds)",
            symbol, self.timeout,
        )

        deadline = time.time() + self.timeout

        while time.time() < deadline:
            try:
                user_input = self._input_fn(
                    f"[{symbol}] Decision (y=execute / n=skip / r=reduce, {int(deadline - time.time())}s left): "
                ).strip().lower()
            except (EOFError, KeyboardInterrupt):
                log.info("OverrideHandler: input interrupted — SKIP")
                return {"action": "TIMEOUT_SKIP", "factor": 1.0}

            if user_input in _ACTIONS:
                action = _ACTIONS[user_input]
                factor = self.reduce_factor if action == "REDUCE" else 1.0
                log.info("OverrideHandler: %s decision=%s", symbol, action)
                return {"action": action, "factor": factor}

        log.info("OverrideHandler: timeout — SKIP %s", symbol)
        return {"action": "TIMEOUT_SKIP", "factor": 1.0}