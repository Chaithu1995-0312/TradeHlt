"""
inout/runner.py
═══════════════════════════════════════════════════════════════════════════════
INOUT Strategy — Main Runner Loop

Standalone event loop for the INOUT strategy.
Completely independent from live_engine_hook.py and EngineRunner.

Responsibilities
----------------
    1. Fetch M1/M5 candles for all configured symbols
    2. Feed candles to INOUTScanner
    3. Forward signals to INOUTController
    4. Feed price ticks to INOUTController for state machine evaluation
    5. Resurrect unclosed trades on startup
    6. Emit heartbeat to logs/inout_heartbeat.jsonl

Architecture
------------
    INOUTRunner owns the polling loop.
    INOUTScanner owns pattern detection.
    INOUTController owns signal acceptance + trade lifecycle.
    INOUTStateMachine owns state transition logic.
    INOUTExecutor owns broker interaction.
    INOUTDatabase owns persistence.

Data source (Phase 1 — stub):
    _fetch_candles() returns synthetic data for testing.
    Phase 2: replace with python-binance or ccxt websocket stream.

Usage
-----
    # Run forever:
    python -m inout.runner

    # Run for N cycles (testing):
    python -m inout.runner --cycles 10

    # Use custom config:
    INOUT_CONFIG_PATH=path/to/config.json python -m inout.runner
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import signal as _signal
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import INOUTConfig
from .controller import INOUTController
from .db import INOUTDatabase
from .executor import INOUTExecutor
from .probability_engine import INOUTScannerProbAdapter, ProbabilityEngine
from .scanner import INOUTScanner
from .state_machine import INOUTStateMachine

# ── Logging setup ─────────────────────────────────────────────────────────────

def _setup_logging(cfg: INOUTConfig) -> None:
    level_name = cfg.logging_cfg("log_level", "INFO")
    level = getattr(logging, level_name.upper(), logging.INFO)

    Path("logs").mkdir(exist_ok=True)

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    # Console
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # File — stamped per run so each invocation writes its own file
    from utils.logging_config import get_log_path
    fh = logging.FileHandler(get_log_path("inout_runner"), encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)


logger = logging.getLogger("INOUT.RUNNER")


# ── Runner ────────────────────────────────────────────────────────────────────

class INOUTRunner:
    """
    Main INOUT event loop.

    Polling interval is M1 (every ~60 seconds in live mode).
    In testing mode (dry_run), cycles immediately.

    Extension points
    ----------------
        Phase 2: replace _fetch_candles() with websocket stream
        Phase 2: replace polling loop with async event-driven loop
        Phase 3: add Gemini context injection before each signal
    """

    def __init__(self, cfg: INOUTConfig) -> None:
        self._cfg = cfg
        self._running = False
        self._cycle_count = 0
        self._heartbeat_path = Path(cfg.logging_cfg("audit_log_path", "logs/inout_audit.jsonl"))
        self._heartbeat_path = Path("logs/inout_heartbeat.jsonl")

        # Wire up components
        self._db      = INOUTDatabase(cfg)
        self._exec    = INOUTExecutor(cfg)
        self._sm      = INOUTStateMachine(cfg)
        self._scanner = INOUTScanner(cfg)

        # Load Ultron config from production config if available
        ultron_cfg = self._load_ultron_cfg()
        self._ctrl  = INOUTController(cfg, self._db, self._exec, self._sm, ultron_cfg)

        # Probability engine wiring (Phase 2 activation)
        self._prob_cfg = self._load_prob_cfg()
        self._prob_engine = ProbabilityEngine.from_config(self._prob_cfg)
        self._prob_adapter: INOUTScannerProbAdapter | None = None
        loaded = self._prob_engine.load()
        if loaded:
            self._prob_adapter = INOUTScannerProbAdapter(self._prob_engine, self._prob_cfg)
            logger.info(
                "INOUT.RUNNER: probability engine loaded (approach=%s, n_trained=%d)",
                self._prob_engine.approach, self._prob_engine.n_trained,
            )
        else:
            logger.info("INOUT.RUNNER: probability engine not fitted — using rule-based scoring")
        self._auto_retrain_n = int(self._prob_cfg.get("auto_retrain_n", 50))
        self._last_retrain_count = 0

        # Graceful shutdown handler
        _signal.signal(_signal.SIGINT, self._handle_shutdown)
        _signal.signal(_signal.SIGTERM, self._handle_shutdown)

    def run(self, max_cycles: int = 0) -> None:
        """
        Main loop. Runs forever unless max_cycles is set (for testing).
        """
        logger.info("INOUT.RUNNER: starting — dry_run=%s", self._exec.is_dry_run)

        # Boot: resurrect any unclosed trades from previous session
        resurrected = self._ctrl.resurrect()
        if resurrected:
            logger.warning("INOUT.RUNNER: %d trade(s) resurrected from previous session", resurrected)

        self._running = True
        symbols = self._cfg.scanner("allowed_symbols", ["BTCUSDT", "ETHUSDT"])
        scan_tfs = self._cfg.scanner("scan_timeframes", ["M1", "M5"])

        while self._running:
            cycle_start = time.time()
            self._cycle_count += 1

            try:
                self._run_cycle(symbols, scan_tfs)
            except Exception as exc:
                logger.error("INOUT.RUNNER: cycle error: %s", exc, exc_info=True)

            # Heartbeat
            self._write_heartbeat()

            # Exit condition for testing
            if max_cycles and self._cycle_count >= max_cycles:
                logger.info("INOUT.RUNNER: max_cycles=%d reached — stopping", max_cycles)
                break

            # Sleep until next M1 candle close (Phase 1: 5 seconds for testing)
            # Phase 2: replace with websocket event-driven trigger
            elapsed = time.time() - cycle_start
            sleep_sec = max(0, 5.0 - elapsed)   # 5s polling in dry-run; 60s in live
            if sleep_sec > 0:
                time.sleep(sleep_sec)

        logger.info("INOUT.RUNNER: stopped after %d cycles", self._cycle_count)

    def _run_cycle(self, symbols: list[str], timeframes: list[str]) -> None:
        """One scanning + monitoring cycle."""
        now = datetime.now(timezone.utc)

        for symbol in symbols:
            for tf in timeframes:
                # Step 1: Fetch candles (stub → Phase 2: real exchange)
                candles = self._fetch_candles(symbol, tf, count=50)
                if not candles:
                    continue

                # Step 2: Scan for explosive signal (with optional prob adapter)
                signal = self._scanner.scan(
                    symbol=symbol,
                    timeframe=tf,
                    candles=candles,
                    prob_adapter=self._prob_adapter,
                )
                if signal is not None:
                    result = self._ctrl.on_signal(signal)
                    logger.info(
                        "INOUT.RUNNER: signal result %s %s accepted=%s reason=%s",
                        symbol, tf, result.get("accepted"), result.get("reason"),
                    )

                # Step 3: Feed latest price to state machine for all open trades
                current = candles[-1]
                price = float(current["close"])
                atr = float(current.get("atr", 0.0))
                actions = self._ctrl.on_price_tick(
                    symbol=symbol,
                    price=price,
                    current_time=now,
                    atr=atr if atr > 0 else None,
                )
                if actions:
                    logger.info(
                        "INOUT.RUNNER: %d action(s) executed for %s", len(actions), symbol
                    )

        # Auto-retrain probability engine when enough closed trades accumulate
        self._maybe_retrain()

    # ── Probability engine helpers ────────────────────────────────────────────

    def _load_prob_cfg(self) -> dict[str, Any]:
        """Load the inout.probability section from the production config."""
        try:
            import os
            path = (
                os.environ.get("INOUT_CONFIG_PATH")
                or "production_configs/v1_multi_2026_03.json"
            )
            if Path(path).exists():
                with open(path, "r", encoding="utf-8") as f:
                    full = json.load(f)
                return full.get("inout", {}).get("probability", {})
        except Exception as exc:
            logger.warning("INOUT.RUNNER: failed to load prob config: %s", exc)
        return {}

    def _maybe_retrain(self) -> None:
        """
        Trigger a probability engine retraining cycle when enough new closed
        trades have accumulated since the last training run.
        Auto-retrain threshold is config-driven (auto_retrain_n).
        """
        closed = self._db.count_closed_trades()
        new_since_last = closed - self._last_retrain_count
        if new_since_last < self._auto_retrain_n:
            return

        logger.info(
            "INOUT.RUNNER: auto-retrain triggered — %d new closed trades since last run",
            new_since_last,
        )
        db_path = self._prob_cfg.get("db_path") or self._cfg.db("db_path", "logs/inout_trades.db")
        n = self._prob_engine.train(db_path=db_path, save_dataset=True)
        min_records = int(self._prob_cfg.get("min_train_records", 10))
        if n >= min_records:
            self._prob_engine.save()
            self._prob_adapter = INOUTScannerProbAdapter(self._prob_engine, self._prob_cfg)
            self._last_retrain_count = closed
            logger.info(
                "INOUT.RUNNER: probability engine retrained on %d records (approach=%s) — adapter active",
                n, self._prob_engine.approach,
            )
        else:
            logger.info(
                "INOUT.RUNNER: retrain skipped — only %d records (need %d)",
                n, min_records,
            )

    # ── Data source (Phase 1 stub) ────────────────────────────────────────────

    def _fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        count: int = 50,
    ) -> list[dict[str, Any]]:
        """
        STUB — returns synthetic candle data for dry-run testing.

        Phase 2: Replace with real exchange data:
            from binance.client import Client
            raw = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1MINUTE, limit=count)
            return [_parse_binance_kline(k) for k in raw]

        Candle format:
            {
                "open": float, "high": float, "low": float, "close": float,
                "volume": float, "atr": float
            }
        """
        # Generate synthetic candles for testing
        base_price = {"BTCUSDT": 65000.0, "ETHUSDT": 3200.0, "SOLUSDT": 180.0, "BNBUSDT": 600.0}.get(symbol, 100.0)
        base_vol = 1000.0
        candles = []
        seed = hash(symbol + timeframe + str(int(time.time() / 60))) % (2**31)

        import random
        rng = random.Random(seed)

        price = base_price
        for i in range(count):
            change = rng.uniform(-0.002, 0.002)
            open_ = price
            close = round(open_ * (1 + change), 5)
            high = round(max(open_, close) * (1 + abs(rng.uniform(0, 0.001))), 5)
            low  = round(min(open_, close) * (1 - abs(rng.uniform(0, 0.001))), 5)
            vol  = base_vol * rng.uniform(0.5, 1.5)
            # Occasionally generate explosive candle to test scanner
            if i == count - 2:  # second to last = normal
                pass
            elif i == count - 1 and rng.random() < 0.1:  # 10% chance of explosive last candle
                close = round(open_ * 1.012, 5)  # 1.2% move
                high = round(close * 1.002, 5)
                low = round(open_ * 0.999, 5)
                vol = base_vol * 4.0  # volume spike

            # Simple ATR estimate
            tr = high - low
            atr = tr * 1.2  # rough ATR approximation

            candles.append({
                "open": open_, "high": high, "low": low,
                "close": close, "volume": vol, "atr": atr,
            })
            price = close

        return candles

    # ── Config helpers ────────────────────────────────────────────────────────

    def _load_ultron_cfg(self) -> dict[str, Any]:
        """Load Ultron config from production config file."""
        try:
            import os
            path = (
                os.environ.get("INOUT_CONFIG_PATH")
                or "production_configs/v1_multi_2026_03.json"
            )
            if Path(path).exists():
                with open(path, "r", encoding="utf-8") as f:
                    full = json.load(f)
                return full.get("ultron_risk_gate", {})
        except Exception as exc:
            logger.warning("INOUT.RUNNER: failed to load Ultron config: %s", exc)
        return {}

    # ── Heartbeat ─────────────────────────────────────────────────────────────

    def _write_heartbeat(self) -> None:
        try:
            self._heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "cycle": self._cycle_count,
                "open_trades": self._db.count_open_trades(),
                "open_risk_pct": self._db.open_risk_pct(),
                "dry_run": self._exec.is_dry_run,
            }
            with open(self._heartbeat_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as exc:
            logger.warning("INOUT.RUNNER: heartbeat write failed: %s", exc)

    # ── Shutdown ──────────────────────────────────────────────────────────────

    def _handle_shutdown(self, signum: int, frame: Any) -> None:
        logger.info("INOUT.RUNNER: shutdown signal received — stopping after current cycle")
        self._running = False


# ── CLI entrypoint ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="INOUT Strategy Runner")
    parser.add_argument(
        "--cycles", type=int, default=0,
        help="Number of cycles to run (0 = infinite)",
    )
    parser.add_argument(
        "--config", type=str, default=None,
        help="Path to config JSON (overrides INOUT_CONFIG_PATH env var)",
    )
    args = parser.parse_args()

    cfg = INOUTConfig.load()
    _setup_logging(cfg)

    logger.info("=" * 60)
    logger.info("INOUT Strategy Runner — Phase 1 (Stub/Dry-Run)")
    logger.info("=" * 60)

    runner = INOUTRunner(cfg)
    runner.run(max_cycles=args.cycles)


if __name__ == "__main__":
    main()
