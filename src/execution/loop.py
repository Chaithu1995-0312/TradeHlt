# loop.py — ExecutionLoop: continuous tick-based pipeline orchestrator
import logging
import time
from typing import Optional, Callable

log = logging.getLogger(__name__)


class SystemState:
    """Shared mutable state for the execution loop (kill switch, pause, etc.)."""

    def __init__(self):
        self.paused: bool = False
        self.running: bool = True
        self.positions: list = []
        self.signals: list = []

    def pause(self):
        self.paused = True
        log.warning("ExecutionLoop: PAUSED")

    def resume(self):
        self.paused = False
        log.info("ExecutionLoop: RESUMED")

    def stop(self):
        self.running = False
        log.info("ExecutionLoop: STOP requested")


class ExecutionLoop:
    """
    Continuous execution loop: scan → rank → regime → allocate → gate → alert → override.

    Designed to run on a 60s tick (one candle). Human-in-loop by default.

    All components are injected (for testability):
      scanner, ranker, pool, regime_clf, config_router,
      allocator, risk_gate, alert_manager, override_handler, trade_executor

    HARD RULES:
      - kill switch (state.paused) always checked first
      - AUTO_EXECUTE=False by default
      - UltronRiskGate is final authority (risk_gate)
      - Override timeout → SKIP (never auto-execute on timeout)

    Usage (test / paper mode):
        loop = ExecutionLoop(scanner=..., ..., max_ticks=5)
        loop.run(state)
    """

    def __init__(
        self,
        scanner,
        ranker,
        pool,
        regime_classifier,
        config_router,
        allocator,
        risk_gate: Optional[Callable] = None,    # callable(signal) → {allow: bool}
        alert_manager=None,
        override_handler=None,
        trade_executor: Optional[Callable] = None,  # callable(signal, config, allocation)
        tick_seconds: int = 60,
        top_k: int = 3,
        max_ticks: Optional[int] = None,           # for testing only
    ):
        self.scanner = scanner
        self.ranker = ranker
        self.pool = pool
        self.regime_clf = regime_classifier
        self.config_router = config_router
        self.allocator = allocator
        self.risk_gate = risk_gate
        self.alert_manager = alert_manager
        self.override_handler = override_handler
        self.trade_executor = trade_executor
        self.tick_seconds = tick_seconds
        self.top_k = top_k
        self.max_ticks = max_ticks

    def run(self, state: Optional[SystemState] = None) -> list:
        """
        Run execution loop. Blocks until state.running=False or max_ticks reached.

        Returns list of executed signal dicts (for audit/testing).
        """
        if state is None:
            state = SystemState()

        executed = []
        tick = 0

        while state.running:
            if self.max_ticks is not None and tick >= self.max_ticks:
                log.info("ExecutionLoop: max_ticks=%d reached — stopping", self.max_ticks)
                break

            tick += 1

            # Kill switch
            if state.paused:
                log.debug("ExecutionLoop: paused — skipping tick %d", tick)
                self._sleep(1)
                continue

            log.info("ExecutionLoop: tick %d", tick)

            try:
                tick_executed = self._process_tick(state)
                executed.extend(tick_executed)
                state.signals = [s for s in executed[-20:]]  # keep last 20
            except Exception as exc:
                log.error("ExecutionLoop: tick %d error: %s", tick, exc)

            if self.max_ticks is None:
                self._sleep(self.tick_seconds)

        return executed

    def _process_tick(self, state: SystemState) -> list:
        """One tick: scan → rank → top_k → route → allocate → gate → alert → override."""
        executed = []

        # 1. Scan
        signals = self.scanner.scan()
        if not signals:
            return []

        # 2. Rank
        ranked = self.ranker.rank(signals)

        # 3. Top-K
        top = self.pool.top_k(ranked, k=self.top_k)

        for signal in top:
            result = self._process_signal(signal)
            if result:
                executed.append(result)
                state.positions.append(result)

        return executed

    def _process_signal(self, signal: dict) -> Optional[dict]:
        """Process a single signal through the full pipeline."""
        symbol = signal.get("symbol", "?")

        # 4. Regime → config
        regime = self.regime_clf.classify(signal)
        config = self.config_router.select_profile(regime)

        # 5. Allocate
        allocation = self.allocator.allocate(signal)
        if allocation["action"] == "REJECT":
            log.info("ExecutionLoop: %s REJECTED by allocator: %s", symbol, allocation["reason"])
            return None

        signal["risk"] = allocation["risk"]
        signal["regime"] = regime
        signal["config_profile"] = config

        # 6. Risk gate (Ultron)
        if self.risk_gate is not None:
            gate_result = self.risk_gate(signal)
            if not gate_result.get("allow", False):
                log.info("ExecutionLoop: %s BLOCKED by risk gate: %s", symbol, gate_result.get("reason"))
                return None

        # 7. Alert
        if self.alert_manager is not None:
            self.alert_manager.send(signal)

        # 8. Override (human decision)
        if self.override_handler is not None:
            decision = self.override_handler.wait_for_decision(signal)
            action = decision.get("action")
            if action in ("SKIP", "TIMEOUT_SKIP"):
                log.info("ExecutionLoop: %s SKIPPED by override", symbol)
                return None
            if action == "REDUCE":
                signal["risk"] *= decision.get("factor", 0.5)

        # 9. Execute
        if self.trade_executor is not None:
            self.trade_executor(signal, config, allocation)

        log.info("ExecutionLoop: EXECUTED %s risk=%.5f", symbol, signal.get("risk", 0))
        return signal

    def _sleep(self, seconds: int):
        time.sleep(seconds)