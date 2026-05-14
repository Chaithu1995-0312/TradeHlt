"""
inout/db.py
═══════════════════════════════════════════════════════════════════════════════
INOUT Strategy — SQLite Persistence Layer

Stores the full SEP-01 trade lifecycle state machine.
All writes are atomic (WAL mode). All reads are non-blocking.

Schema
------
    inout_trades      — one row per trade, full state machine
    inout_exits       — one row per partial/full exit event
    inout_audit       — append-only signal/decision log

State machine transitions (enforced at DB level):
    PENDING → ACTIVE → PROTECTED → HARVESTED → CLOSED
    Any state → FAILED  (emergency path)
    Any state → TIMEOUT (time-stop path)

Design principles
-----------------
    - WAL mode: concurrent reads never block writes
    - Atomic: state written BEFORE API call fired (resurrection safety)
    - Append-only exits: partial exits never overwrite, always append
    - No DELETE ever issued on inout_trades or inout_exits

Extension points
----------------
    Phase 2: add probability_snapshot column (stores P50/P75/P90 at entry)
    Phase 3: add gemini_context column (Gemini reasoning at entry)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from .config import INOUTConfig

logger = logging.getLogger("INOUT.DB")

# ── Valid state transitions ───────────────────────────────────────────────────
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "PENDING":   {"ACTIVE", "FAILED"},
    "ACTIVE":    {"PROTECTED", "TIMEOUT", "FAILED", "CLOSED"},
    "PROTECTED": {"HARVESTED", "TIMEOUT", "FAILED", "CLOSED"},
    "HARVESTED": {"CLOSED", "TIMEOUT", "FAILED"},
    "CLOSED":    set(),   # terminal
    "FAILED":    set(),   # terminal
    "TIMEOUT":   set(),   # terminal
}

_TERMINAL_STATES = {"CLOSED", "FAILED", "TIMEOUT"}


class INOUTDatabase:
    """
    Thread-safe SQLite persistence for the INOUT state machine.

    One instance should be created per runner process and shared
    across scanner, state_machine, and executor.

    Usage
    -----
        db = INOUTDatabase(cfg)
        trade_id = db.create_trade(signal, risk_result, plan)
        db.transition(trade_id, "ACTIVE", meta={"fill_price": 50100.0})
        db.record_exit(trade_id, tier=1, fraction=0.30, fill_price=50500.0, pnl_rr=1.02)
        db.transition(trade_id, "PROTECTED")
        trade = db.get_trade(trade_id)
    """

    def __init__(self, cfg: INOUTConfig) -> None:
        self._path = Path(cfg.db("path", "logs/inout_trades.db"))
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._timeout = float(cfg.db("timeout", 5.0))
        self._wal = bool(cfg.db("wal_mode", True))
        self._lock = threading.RLock()   # in-process serialization
        self._init_schema()

    # ── Schema ────────────────────────────────────────────────────────────────

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                -- Core trade record (one row per signal/trade)
                CREATE TABLE IF NOT EXISTS inout_trades (
                    trade_id         TEXT PRIMARY KEY,
                    symbol           TEXT NOT NULL,
                    direction        TEXT NOT NULL,        -- LONG | SHORT
                    state            TEXT NOT NULL,        -- state machine
                    entry_price      REAL,
                    stop_loss        REAL,
                    tp1_price        REAL,
                    tp2_price        REAL,
                    runner_trail_sl  REAL,                 -- updated as runner moves
                    position_size    REAL,
                    risk_pct         REAL,
                    rr_ratio         REAL,
                    signal_score     REAL,
                    signal_meta      TEXT,                 -- JSON blob
                    created_at       TEXT NOT NULL,
                    activated_at     TEXT,
                    closed_at        TEXT,
                    time_stop_at     TEXT,                 -- when time-stop fires
                    close_reason     TEXT,
                    total_pnl_rr     REAL,
                    -- Extension point: Phase 2
                    prob_snapshot    TEXT,                 -- JSON: {p50, p75, p90}
                    -- Extension point: Phase 3
                    gemini_context   TEXT                  -- Gemini reasoning blob
                );

                -- Partial / full exit events (append-only)
                CREATE TABLE IF NOT EXISTS inout_exits (
                    exit_id          TEXT PRIMARY KEY,
                    trade_id         TEXT NOT NULL REFERENCES inout_trades(trade_id),
                    tier             INTEGER NOT NULL,     -- 1 | 2 | 3 | 99 (time-stop/SL)
                    fraction         REAL NOT NULL,        -- fraction of original size
                    fill_price       REAL NOT NULL,
                    target_price     REAL,                 -- expected price
                    slippage_pct     REAL,                 -- fill vs target
                    pnl_rr           REAL,
                    exit_reason      TEXT NOT NULL,        -- TP1 | TP2 | RUNNER | TIMESTOP | SL
                    exited_at        TEXT NOT NULL
                );

                -- Append-only signal/decision audit log
                CREATE TABLE IF NOT EXISTS inout_audit (
                    audit_id         TEXT PRIMARY KEY,
                    trade_id         TEXT,
                    event_type       TEXT NOT NULL,        -- SIGNAL | RISK_CHECK | STATE_CHANGE | EXIT
                    symbol           TEXT,
                    payload          TEXT NOT NULL,        -- JSON blob
                    logged_at        TEXT NOT NULL
                );

                -- Indexes for common queries
                CREATE INDEX IF NOT EXISTS idx_trades_symbol_state
                    ON inout_trades (symbol, state);
                CREATE INDEX IF NOT EXISTS idx_trades_state
                    ON inout_trades (state);
                CREATE INDEX IF NOT EXISTS idx_exits_trade
                    ON inout_exits (trade_id);
            """)
        logger.info("INOUT.DB: schema initialized at %s", self._path)

    # ── Trade lifecycle ───────────────────────────────────────────────────────

    def create_trade(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        tp1_price: float,
        tp2_price: float,
        position_size: float,
        risk_pct: float,
        rr_ratio: float,
        signal_score: float,
        signal_meta: dict[str, Any] | None = None,
        time_stop_at: datetime | None = None,
    ) -> str:
        """
        Insert a new trade in PENDING state.
        Returns trade_id (UUID4).
        Call transition(trade_id, "ACTIVE") once broker confirms fill.
        """
        trade_id = str(uuid.uuid4())
        now = _now_iso()
        time_stop_iso = time_stop_at.isoformat() if time_stop_at else None

        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO inout_trades (
                    trade_id, symbol, direction, state,
                    entry_price, stop_loss, tp1_price, tp2_price,
                    runner_trail_sl, position_size, risk_pct, rr_ratio,
                    signal_score, signal_meta,
                    created_at, time_stop_at
                ) VALUES (
                    ?, ?, ?, 'PENDING',
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?,
                    ?, ?
                )
                """,
                (
                    trade_id, symbol, direction,
                    entry_price, stop_loss, tp1_price, tp2_price,
                    stop_loss,              # runner trail starts at initial SL
                    position_size, risk_pct, rr_ratio,
                    signal_score,
                    json.dumps(signal_meta or {}),
                    now, time_stop_iso,
                ),
            )

        self._audit(trade_id, "SIGNAL", symbol, {
            "direction": direction,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "tp1": tp1_price,
            "tp2": tp2_price,
            "rr_ratio": rr_ratio,
            "signal_score": signal_score,
        })
        logger.info("INOUT.DB: trade CREATED %s %s %s @ %.5f", trade_id, symbol, direction, entry_price)
        return trade_id

    def transition(
        self,
        trade_id: str,
        new_state: str,
        meta: dict[str, Any] | None = None,
    ) -> bool:
        """
        Atomically advance the trade state machine.

        Returns True on success, False if transition is invalid
        (trade not found or illegal transition).

        Write happens BEFORE any external API call (resurrection safety).
        """
        with self._lock:
            trade = self.get_trade(trade_id)
            if trade is None:
                logger.error("INOUT.DB: transition — trade not found: %s", trade_id)
                return False

            current = trade["state"]
            if new_state not in _VALID_TRANSITIONS.get(current, set()):
                logger.error(
                    "INOUT.DB: ILLEGAL transition %s → %s for trade %s",
                    current, new_state, trade_id,
                )
                return False

            now = _now_iso()
            updates: dict[str, Any] = {"state": new_state}

            if new_state == "ACTIVE":
                updates["activated_at"] = now
            if new_state in _TERMINAL_STATES:
                updates["closed_at"] = now
                if meta:
                    updates["close_reason"] = meta.get("reason", new_state)

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [trade_id]

            with self._conn() as conn:
                conn.execute(
                    f"UPDATE inout_trades SET {set_clause} WHERE trade_id = ?",
                    values,
                )

        self._audit(trade_id, "STATE_CHANGE", trade.get("symbol", ""), {
            "from": current,
            "to": new_state,
            **(meta or {}),
        })
        logger.info("INOUT.DB: trade %s %s → %s", trade_id, current, new_state)
        return True

    def record_exit(
        self,
        trade_id: str,
        tier: int,
        fraction: float,
        fill_price: float,
        exit_reason: str,
        target_price: float | None = None,
        pnl_rr: float | None = None,
    ) -> str:
        """
        Append an exit event. Never overwrites existing exits.
        Returns exit_id.
        """
        exit_id = str(uuid.uuid4())
        slippage = None
        if target_price and target_price != 0.0:
            slippage = round(abs(fill_price - target_price) / target_price * 100, 6)

        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO inout_exits (
                    exit_id, trade_id, tier, fraction,
                    fill_price, target_price, slippage_pct,
                    pnl_rr, exit_reason, exited_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    exit_id, trade_id, tier, fraction,
                    fill_price, target_price, slippage,
                    pnl_rr, exit_reason, _now_iso(),
                ),
            )

        self._audit(trade_id, "EXIT", None, {
            "tier": tier,
            "fraction": fraction,
            "fill": fill_price,
            "target": target_price,
            "slippage_pct": slippage,
            "pnl_rr": pnl_rr,
            "reason": exit_reason,
        })
        return exit_id

    def update_runner_trail(self, trade_id: str, new_trail_sl: float) -> None:
        """Update the trailing stop for the runner (Tier 3)."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE inout_trades SET runner_trail_sl = ? WHERE trade_id = ?",
                (new_trail_sl, trade_id),
            )

    def update_total_pnl(self, trade_id: str, total_pnl_rr: float) -> None:
        """Record final realized P&L in RR units after trade closes."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE inout_trades SET total_pnl_rr = ? WHERE trade_id = ?",
                (total_pnl_rr, trade_id),
            )

    # ── Query helpers ─────────────────────────────────────────────────────────

    def get_trade(self, trade_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM inout_trades WHERE trade_id = ?", (trade_id,)
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def get_active_trades(self) -> list[dict[str, Any]]:
        """Return all trades in non-terminal states."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM inout_trades WHERE state NOT IN ('CLOSED','FAILED','TIMEOUT')"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_active_by_symbol(self, symbol: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM inout_trades
                   WHERE symbol = ? AND state NOT IN ('CLOSED','FAILED','TIMEOUT')""",
                (symbol,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_exits_for_trade(self, trade_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM inout_exits WHERE trade_id = ? ORDER BY exited_at",
                (trade_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def count_open_trades(self) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM inout_trades WHERE state NOT IN ('CLOSED','FAILED','TIMEOUT')"
            ).fetchone()
        return row[0] if row else 0

    def open_risk_pct(self) -> float:
        """Sum of risk_pct across all open (non-terminal) trades."""
        with self._conn() as conn:
            row = conn.execute(
                """SELECT COALESCE(SUM(risk_pct), 0.0) FROM inout_trades
                   WHERE state NOT IN ('CLOSED','FAILED','TIMEOUT')"""
            ).fetchone()
        return float(row[0]) if row else 0.0

    def count_closed_trades(self) -> int:
        """Count trades in terminal states — used by auto-retrain logic."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM inout_trades WHERE state IN ('CLOSED','FAILED','TIMEOUT')"
            ).fetchone()
        return row[0] if row else 0

    def update_prob_snapshot(self, trade_id: str, prob_dict: dict[str, Any]) -> None:
        """
        Persist probability engine output to the prob_snapshot column.
        Called after create_trade() when probability engine is active.
        """
        with self._conn() as conn:
            conn.execute(
                "UPDATE inout_trades SET prob_snapshot = ? WHERE trade_id = ?",
                (json.dumps(prob_dict), trade_id),
            )

    # ── Resurrection query (system boot recovery) ─────────────────────────────

    def get_unclosed_trades(self) -> list[dict[str, Any]]:
        """
        Called on system boot. Returns trades that were not cleanly closed.
        Controller uses this to re-establish monitoring.
        """
        return self.get_active_trades()

    # ── Internal ──────────────────────────────────────────────────────────────

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(
            str(self._path),
            timeout=self._timeout,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        if self._wal:
            conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _audit(
        self,
        trade_id: str | None,
        event_type: str,
        symbol: str | None,
        payload: dict[str, Any],
    ) -> None:
        try:
            with self._conn() as conn:
                conn.execute(
                    """INSERT INTO inout_audit
                       (audit_id, trade_id, event_type, symbol, payload, logged_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        str(uuid.uuid4()),
                        trade_id,
                        event_type,
                        symbol,
                        json.dumps(payload, default=str),
                        _now_iso(),
                    ),
                )
        except Exception as exc:
            # Audit must never crash the main flow
            logger.warning("INOUT.DB: audit write failed: %s", exc)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
