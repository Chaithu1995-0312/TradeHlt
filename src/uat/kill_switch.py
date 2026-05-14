"""
kill_switch.py
================================================================================
KillSwitch — stateful daily/weekly loss gate for live trading protection.

Maintains a JSON state file that persists across process restarts. On every
trade completion, the realised P&L is registered. If cumulative loss exceeds
daily or weekly threshold, the switch trips and blocks all new signals until
manually reset.

State file: logs/kill_switch_state.json  (path from config)

Usage
-----
    ks = KillSwitch.from_prod_config()
    ks.register_trade(pnl_inr=-800.0)
    if ks.is_tripped():
        logger.warning("Kill switch active — trading halted")
    ks.reset()  # manual operator reset

Config section: uat.kill_switch in production JSON.
================================================================================
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from config_layer.production_config import get_prod_section   # type: ignore
from utils.logging_config import get_flow_logger               # type: ignore

logger = get_flow_logger("LIVE_HOOK")

_ISO_DAY = "%Y-%m-%d"
_ISO_WEEK = "%Y-W%W"


def _today() -> str:
    return date.today().strftime(_ISO_DAY)


def _this_week() -> str:
    return date.today().strftime(_ISO_WEEK)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class KillSwitch:
    """
    Stateful daily/weekly loss gate.

    State persisted to JSON so the gate survives process restarts.
    Thread-safety: single-process assumed (file lock not implemented).

    Attributes (from state file)
    ----------------------------
    tripped          bool — True when any threshold is breached
    trip_reason      str  — "daily" | "weekly" | ""
    trip_ts          str  — ISO timestamp of the trip event
    daily_loss_inr   float — cumulative loss for current calendar day
    weekly_loss_inr  float — cumulative loss for current ISO week
    current_day      str  — "YYYY-MM-DD" of the last registered trade
    current_week     str  — "YYYY-WNN"  of the last registered trade
    """

    def __init__(
        self,
        daily_limit_inr: float = 10_000.0,
        weekly_limit_inr: float = 25_000.0,
        state_file: Path = Path("logs/kill_switch_state.json"),
    ) -> None:
        self.daily_limit  = daily_limit_inr
        self.weekly_limit = weekly_limit_inr
        self._state_path  = Path(state_file)
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state       = self._load_state()

    @classmethod
    def from_prod_config(cls) -> "KillSwitch":
        cfg = (get_prod_section("uat") or {}).get("kill_switch", {})
        return cls(
            daily_limit_inr  = float(cfg.get("daily_loss_limit_inr",  10_000.0)),
            weekly_limit_inr = float(cfg.get("weekly_loss_limit_inr", 25_000.0)),
            state_file       = Path(cfg.get("state_file", "logs/kill_switch_state.json")),
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    def register_trade(self, pnl_inr: float) -> bool:
        """
        Record a completed trade P&L.

        Parameters
        ----------
        pnl_inr  Realised P&L in INR. Positive = profit, negative = loss.

        Returns
        -------
        True if the kill switch just tripped on this trade, False otherwise.
        """
        if self._state["tripped"]:
            logger.warning(
                "KillSwitch already tripped (%s). Ignoring new trade registration.",
                self._state.get("trip_reason", ""),
            )
            return False

        today = _today()
        week  = _this_week()

        # Roll over daily/weekly accumulators on date change
        if self._state["current_day"] != today:
            self._state["daily_loss_inr"] = 0.0
            self._state["current_day"]    = today
        if self._state["current_week"] != week:
            self._state["weekly_loss_inr"] = 0.0
            self._state["current_week"]    = week

        # Only losses accumulate toward the gate
        if pnl_inr < 0:
            loss = abs(pnl_inr)
            self._state["daily_loss_inr"]  += loss
            self._state["weekly_loss_inr"] += loss

        # Check thresholds
        just_tripped = False
        if self._state["daily_loss_inr"] >= self.daily_limit:
            self._trip(reason="daily")
            just_tripped = True
        elif self._state["weekly_loss_inr"] >= self.weekly_limit:
            self._trip(reason="weekly")
            just_tripped = True

        self._save_state()
        return just_tripped

    def is_tripped(self) -> bool:
        """True when trading should be halted."""
        return bool(self._state.get("tripped", False))

    def trip_reason(self) -> str:
        """'daily' | 'weekly' | '' — reason the switch tripped."""
        return str(self._state.get("trip_reason", ""))

    def daily_loss_inr(self) -> float:
        return float(self._state.get("daily_loss_inr", 0.0))

    def weekly_loss_inr(self) -> float:
        return float(self._state.get("weekly_loss_inr", 0.0))

    def reset(self) -> None:
        """
        Operator reset — clears trip state but preserves loss accumulators.
        Must be called explicitly; never auto-resets.
        """
        self._state["tripped"]     = False
        self._state["trip_reason"] = ""
        self._state["trip_ts"]     = ""
        self._save_state()
        logger.info("KillSwitch manually reset by operator.")

    def status_dict(self) -> dict:
        return {
            "tripped":          self._state["tripped"],
            "trip_reason":      self._state["trip_reason"],
            "trip_ts":          self._state["trip_ts"],
            "daily_loss_inr":   round(self._state["daily_loss_inr"], 2),
            "weekly_loss_inr":  round(self._state["weekly_loss_inr"], 2),
            "daily_limit_inr":  self.daily_limit,
            "weekly_limit_inr": self.weekly_limit,
            "current_day":      self._state["current_day"],
            "current_week":     self._state["current_week"],
        }

    # ── Private ────────────────────────────────────────────────────────────────

    def _trip(self, reason: str) -> None:
        self._state["tripped"]     = True
        self._state["trip_reason"] = reason
        self._state["trip_ts"]     = _now_iso()
        logger.warning(
            "KillSwitch TRIPPED: %s limit breached. "
            "daily=INR%.0f weekly=INR%.0f. All trading halted.",
            reason,
            self._state["daily_loss_inr"],
            self._state["weekly_loss_inr"],
        )

    def _load_state(self) -> dict:
        if self._state_path.exists():
            try:
                return json.loads(self._state_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                logger.warning("KillSwitch: corrupt state file — resetting.")
        return self._default_state()

    def _save_state(self) -> None:
        try:
            self._state_path.write_text(
                json.dumps(self._state, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            logger.error("KillSwitch: failed to persist state: %s", exc)

    @staticmethod
    def _default_state() -> dict:
        return {
            "tripped":          False,
            "trip_reason":      "",
            "trip_ts":          "",
            "daily_loss_inr":   0.0,
            "weekly_loss_inr":  0.0,
            "current_day":      _today(),
            "current_week":     _this_week(),
        }
