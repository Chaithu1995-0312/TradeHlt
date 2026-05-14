"""
inout/state_machine.py
═══════════════════════════════════════════════════════════════════════════════
INOUT Strategy — SEP-01 State Machine

Enforces the exact SEP-01 lifecycle for each active trade.
All state transitions write to DB BEFORE any broker action.

States
------
    PENDING   → created, awaiting broker fill confirmation
    ACTIVE    → position open, monitoring for Tier 1
    PROTECTED → Tier 1 hit, SL moved to breakeven, monitoring for Tier 2
    HARVESTED → Tier 2 hit, running Tier 3 with trailing stop
    CLOSED    → all position exited (normal path)
    TIMEOUT   → time-stop fired (no Tier 1 reached in time window)
    FAILED    → unexpected error / emergency exit

Transition table
----------------
    PENDING   → ACTIVE | FAILED
    ACTIVE    → PROTECTED | TIMEOUT | FAILED | CLOSED (SL hit before T1)
    PROTECTED → HARVESTED | TIMEOUT | FAILED | CLOSED (SL hit between T1/T2)
    HARVESTED → CLOSED | TIMEOUT | FAILED
    CLOSED    → (terminal)
    TIMEOUT   → (terminal)
    FAILED    → (terminal)

Design principles
-----------------
    - State machine is a pure evaluator: it observes price + time,
      decides what action to take, returns ActionInstruction.
    - It does NOT call brokers directly (executor.py does that).
    - It does NOT modify DB directly (controller.py coordinates DB + executor).
    - Deterministic: same inputs always produce same action.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .config import INOUTConfig

logger = logging.getLogger("INOUT.SM")

# ── Probability snapshot defaults ─────────────────────────────────────────────
# Returned by _load_prob() when prob_snapshot is absent, NULL, or unparseable.
# confidence=0.0 guarantees _prob_trusted() returns False → all prob branches
# are skipped and existing static logic runs unchanged (backward compat).
_PROB_DEFAULTS: dict[str, Any] = {
    "tp1_prob": 0.45,
    "tp2_prob": 0.30,
    "runner_prob": 0.15,
    "expected_time_tp1": 5.0,
    "expected_time_tp2": 9.0,
    "expected_rr": 0.5,
    "confidence": 0.0,   # intentionally 0.0 — NOT 0.1 — so priors never activate
    "n_samples": 0,
    "warnings": [],
}

# ── Action types ──────────────────────────────────────────────────────────────

class ActionType(str, Enum):
    NONE         = "NONE"          # No action needed this tick
    MOVE_SL      = "MOVE_SL"       # Update stop-loss on broker
    EXIT_PARTIAL = "EXIT_PARTIAL"  # Partial exit (Tier 1 or Tier 2)
    EXIT_FULL    = "EXIT_FULL"     # Full exit (SL hit, time-stop, or runner close)
    UPDATE_TRAIL = "UPDATE_TRAIL"  # Update trailing stop for runner


@dataclass
class ActionInstruction:
    """
    Returned by INOUTStateMachine.evaluate().
    The controller reads this and coordinates DB + executor.
    """
    action: ActionType
    trade_id: str
    symbol: str
    direction: str                      # LONG | SHORT
    new_state: str | None               # Target state after action
    fraction: float = 0.0               # Fraction of original size to exit
    exit_tier: int | None = None        # 1 | 2 | 3 | 99 (SL/time-stop)
    exit_reason: str = ""
    new_sl: float | None = None         # New SL price (for MOVE_SL / UPDATE_TRAIL)
    target_price: float | None = None   # Expected exit price (for slippage calc)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def is_exit(self) -> bool:
        return self.action in (ActionType.EXIT_PARTIAL, ActionType.EXIT_FULL)


# ── State machine ─────────────────────────────────────────────────────────────

class INOUTStateMachine:
    """
    Pure evaluator: given current price, time, and trade record,
    returns the appropriate ActionInstruction.

    Usage (called by INOUTController on every price tick / candle close):
        sm = INOUTStateMachine(cfg)
        instruction = sm.evaluate(trade_record, current_price, current_time)
        # controller then executes instruction
    """

    def __init__(self, cfg: INOUTConfig) -> None:
        self._cfg = cfg

    # ── Main evaluate ─────────────────────────────────────────────────────────

    def evaluate(
        self,
        trade: dict[str, Any],
        current_price: float,
        current_time: datetime | None = None,
        current_atr: float | None = None,
    ) -> ActionInstruction:
        """
        Evaluate current market vs trade state.

        Parameters
        ----------
        trade        : row from inout_trades (as dict)
        current_price: latest market price
        current_time : UTC datetime (defaults to now)
        current_atr  : current ATR for trailing stop update

        Returns ActionInstruction.
        """
        now = current_time or datetime.now(timezone.utc)
        trade_id = trade["trade_id"]
        symbol = trade["symbol"]
        direction = trade["direction"]
        state = trade["state"]

        _noop = ActionInstruction(
            action=ActionType.NONE,
            trade_id=trade_id,
            symbol=symbol,
            direction=direction,
            new_state=None,
        )

        if state in {"CLOSED", "FAILED", "TIMEOUT"}:
            return _noop

        # ── Time-stop check (applies to ALL non-terminal states) ──────────────
        time_stop_action = self._check_time_stop(trade, now)
        if time_stop_action is not None:
            return time_stop_action

        # ── Route to state handler ────────────────────────────────────────────
        if state == "PENDING":
            return _noop   # Waiting for broker fill — controller handles

        if state == "ACTIVE":
            return self._evaluate_active(trade, current_price, current_atr, now)

        if state == "PROTECTED":
            return self._evaluate_protected(trade, current_price, current_atr, now)

        if state == "HARVESTED":
            return self._evaluate_harvested(trade, current_price, current_atr)

        return _noop

    # ── State handlers ────────────────────────────────────────────────────────

    def _evaluate_active(
        self,
        trade: dict[str, Any],
        price: float,
        atr: float | None,
        now: datetime,
    ) -> ActionInstruction:
        """
        ACTIVE → monitor for SL hit or Tier 1 hit.
        """
        trade_id = trade["trade_id"]
        symbol = trade["symbol"]
        direction = trade["direction"]
        entry = float(trade["entry_price"])
        sl = float(trade["stop_loss"])
        tp1 = float(trade["tp1_price"])
        tp1_frac = float(self._cfg.exit("tp1_fraction", 0.30))

        # Probability data + elapsed time (for prob-gated early exit below)
        prob = self._load_prob(trade)
        p75_factor = float(self._cfg.exit("p75_factor", 1.4))
        elapsed_min_active = 0.0
        created_raw = trade.get("created_at")
        if created_raw:
            try:
                created_dt = datetime.fromisoformat(str(created_raw))
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
                elapsed_min_active = (now - created_dt).total_seconds() / 60.0
            except (ValueError, TypeError):
                pass

        # ── SL hit → full exit ────────────────────────────────────────────────
        if self._sl_hit(direction, price, sl):
            logger.info("INOUT.SM: SL hit trade=%s price=%.5f sl=%.5f", trade_id, price, sl)
            return ActionInstruction(
                action=ActionType.EXIT_FULL,
                trade_id=trade_id, symbol=symbol, direction=direction,
                new_state="CLOSED",
                fraction=1.0,
                exit_tier=99,
                exit_reason="SL",
                target_price=sl,
            )

        # ── Tier 1 hit (price-based) — PRIMARY trigger ────────────────────────
        if self._tp_hit(direction, price, tp1):
            logger.info("INOUT.SM: TIER1 hit trade=%s price=%.5f tp1=%.5f", trade_id, price, tp1)
            # Move SL to breakeven (entry + small buffer)
            sl_precision = self._price_precision(symbol)
            be_buffer = float(trade.get("atr", 0.0)) * 0.1   # 10% ATR buffer
            new_sl = round(
                entry + be_buffer if direction == "LONG" else entry - be_buffer,
                sl_precision,
            )
            return ActionInstruction(
                action=ActionType.EXIT_PARTIAL,
                trade_id=trade_id, symbol=symbol, direction=direction,
                new_state="PROTECTED",
                fraction=tp1_frac,
                exit_tier=1,
                exit_reason="TP1",
                new_sl=new_sl,
                target_price=tp1,
            )

        # ── Prob-gated early TP1 exit — SECONDARY trigger ─────────────────────
        # Fires at p75×0.9 — just before soft time-stop at p75×1.0 — so it
        # takes a partial PROTECTED exit rather than a full TIMEOUT.
        # Three guards (FIX 1/2/3) prevent false triggers:
        #   FIX 1: trust filter (confidence + n_samples)
        #   FIX 2: structure guard — skip if price is nearly at TP1 naturally
        #   FIX 3: slippage guard — skip in high-volatility (ATR > 1% of price)
        if self._prob_trusted(prob) and elapsed_min_active > 0.0:
            atr_val = float(trade.get("atr") or 0.0)
            tp1_near = float(self._cfg.exit("tp1_near_threshold", 0.002))
            high_atr_skip = float(self._cfg.exit("high_atr_pct_skip", 0.01))
            tp1_distance_pct = abs(price - tp1) / tp1 if tp1 > 0 else 1.0
            atr_pct = atr_val / price if price > 0 else 0.0

            if tp1_distance_pct < tp1_near:
                # FIX 2: price nearly at TP1 — let it hit naturally, don't exit early
                pass
            elif atr_pct > high_atr_skip:
                # FIX 3: high volatility — model unreliable, SL/TP handles it
                pass
            else:
                early_exit_time = prob["expected_time_tp1"] * p75_factor * 0.9
                if elapsed_min_active >= early_exit_time:
                    logger.info(
                        "INOUT.SM: PROB EARLY-TP1 trade=%s elapsed=%.1f >= %.1f "
                        "tp1_prob=%.2f conf=%.2f n=%d",
                        trade_id, elapsed_min_active, early_exit_time,
                        prob["tp1_prob"], prob["confidence"], prob["n_samples"],
                    )
                    sl_precision = self._price_precision(symbol)
                    be_buffer = atr_val * 0.1
                    new_sl = round(
                        entry + be_buffer if direction == "LONG" else entry - be_buffer,
                        sl_precision,
                    )
                    return ActionInstruction(
                        action=ActionType.EXIT_PARTIAL,
                        trade_id=trade_id, symbol=symbol, direction=direction,
                        new_state="PROTECTED",
                        fraction=tp1_frac,
                        exit_tier=1,
                        exit_reason="TP1_PROB_TIME",
                        new_sl=new_sl,
                        target_price=price,   # market price — not fixed TP1
                        meta={
                            "elapsed_min": round(elapsed_min_active, 2),
                            "early_exit_time": round(early_exit_time, 2),
                            "tp1_prob": prob["tp1_prob"],
                            "confidence": prob["confidence"],
                            "n_samples": prob["n_samples"],
                        },
                    )

        return ActionInstruction(
            action=ActionType.NONE,
            trade_id=trade_id, symbol=symbol, direction=direction, new_state=None,
        )

    def _evaluate_protected(
        self,
        trade: dict[str, Any],
        price: float,
        atr: float | None,
        now: datetime,
    ) -> ActionInstruction:
        """
        PROTECTED → Tier 1 already exited. SL at breakeven.
        Monitor for SL (now at BE) or Tier 2 hit.
        """
        trade_id = trade["trade_id"]
        symbol = trade["symbol"]
        direction = trade["direction"]
        sl = float(trade["stop_loss"])          # now at breakeven
        tp2 = float(trade["tp2_price"])
        tp2_frac = float(self._cfg.exit("tp2_fraction", 0.50))

        # ── SL hit (breakeven) → exit remaining position ──────────────────────
        if self._sl_hit(direction, price, sl):
            logger.info("INOUT.SM: BE-SL hit trade=%s price=%.5f sl=%.5f", trade_id, price, sl)
            return ActionInstruction(
                action=ActionType.EXIT_FULL,
                trade_id=trade_id, symbol=symbol, direction=direction,
                new_state="CLOSED",
                fraction=1.0,
                exit_tier=99,
                exit_reason="BE_SL",
                target_price=sl,
            )

        # ── TP2 low-prob abandon (FIX 1: prob trust filter) ──────────────────────
        # If probability engine says TP2 is unlikely to be reached, close the
        # remaining position now at market rather than holding through TP2.
        # new_state="CLOSED" (not "TIMEOUT") — this is a deliberate model-informed
        # decision, not a time-driven exit.  Default prior tp2_prob=0.30 > abandon
        # threshold 0.25 so missing prob_snapshot never triggers this branch.
        prob = self._load_prob(trade)
        tp2_abandon = float(self._cfg.exit("tp2_abandon_prob", 0.25))
        if self._prob_trusted(prob) and prob["tp2_prob"] < tp2_abandon:
            logger.info(
                "INOUT.SM: TP2 LOW-PROB ABANDON trade=%s tp2_prob=%.2f conf=%.2f n=%d",
                trade_id, prob["tp2_prob"], prob["confidence"], int(prob.get("n_samples", 0)),
            )
            return ActionInstruction(
                action=ActionType.EXIT_FULL,
                trade_id=trade_id, symbol=symbol, direction=direction,
                new_state="CLOSED",
                fraction=1.0,
                exit_tier=99,
                exit_reason="TP2_LOW_PROB",
                meta={"tp2_prob": prob["tp2_prob"], "confidence": prob["confidence"]},
            )

        # ── Tier 2 hit → partial exit, start trailing runner ──────────────────
        if self._tp_hit(direction, price, tp2):
            logger.info("INOUT.SM: TIER2 hit trade=%s price=%.5f tp2=%.5f", trade_id, price, tp2)
            trail_sl = self._compute_trail_sl(trade, price, atr, direction)
            return ActionInstruction(
                action=ActionType.EXIT_PARTIAL,
                trade_id=trade_id, symbol=symbol, direction=direction,
                new_state="HARVESTED",
                fraction=tp2_frac,
                exit_tier=2,
                exit_reason="TP2",
                new_sl=trail_sl,
                target_price=tp2,
            )

        return ActionInstruction(
            action=ActionType.NONE,
            trade_id=trade_id, symbol=symbol, direction=direction, new_state=None,
        )

    def _evaluate_harvested(
        self,
        trade: dict[str, Any],
        price: float,
        atr: float | None,
    ) -> ActionInstruction:
        """
        HARVESTED → runner (20%) active with ATR trailing stop.
        Update trail every candle close; exit when trail is hit.
        """
        trade_id = trade["trade_id"]
        symbol = trade["symbol"]
        direction = trade["direction"]
        trail_sl = float(trade["runner_trail_sl"])
        runner_frac = float(self._cfg.exit("runner_fraction", 0.20))

        # ── Runner trail hit → full close ─────────────────────────────────────
        if self._sl_hit(direction, price, trail_sl):
            logger.info(
                "INOUT.SM: RUNNER trail hit trade=%s price=%.5f trail=%.5f",
                trade_id, price, trail_sl,
            )
            return ActionInstruction(
                action=ActionType.EXIT_FULL,
                trade_id=trade_id, symbol=symbol, direction=direction,
                new_state="CLOSED",
                fraction=runner_frac,
                exit_tier=3,
                exit_reason="RUNNER_TRAIL",
                target_price=trail_sl,
            )

        # ── Update trailing stop — adaptive multiplier driven by runner_prob ────
        # FIX 1: prob trust filter gates the adaptive mult selection.
        # r_prob >= 0.4  → wide trail (×1.2)  — let the runner extend
        # r_prob <  0.2  → tight trail (×0.6) — protect gains aggressively
        # else / untrusted → base multiplier (config default, e.g. 2.5×)
        if atr is not None:
            base_mult = float(self._cfg.exit("runner_trail_atr_mult", 2.5))
            prob = self._load_prob(trade)

            if self._prob_trusted(prob):
                r_prob = prob["runner_prob"]
                extend_thresh = float(self._cfg.exit("runner_extend_prob_threshold", 0.4))
                tight_thresh  = float(self._cfg.exit("runner_tight_prob_threshold", 0.2))
                if r_prob >= extend_thresh:
                    effective_mult = base_mult * 1.2     # wide — let it run
                elif r_prob < tight_thresh:
                    effective_mult = base_mult * 0.6     # tight — lock in gains
                else:
                    effective_mult = base_mult
            else:
                effective_mult = base_mult

            new_trail = self._compute_trail_sl_adaptive(trade, price, atr, direction, effective_mult)
            if new_trail is not None and self._trail_improved(direction, new_trail, trail_sl):
                return ActionInstruction(
                    action=ActionType.UPDATE_TRAIL,
                    trade_id=trade_id, symbol=symbol, direction=direction,
                    new_state=None,
                    new_sl=new_trail,
                    meta={"trail_mult": round(effective_mult, 3)},
                )

        return ActionInstruction(
            action=ActionType.NONE,
            trade_id=trade_id, symbol=symbol, direction=direction, new_state=None,
        )

    # ── Time-stop ─────────────────────────────────────────────────────────────

    def _check_time_stop(
        self,
        trade: dict[str, Any],
        now: datetime,
    ) -> ActionInstruction | None:
        """
        Fire time-stop if:
            - state == ACTIVE and default_time_min exceeded (Tier 1 not hit)
            - any state and max_time_min exceeded (hard cap)

        Returns ActionInstruction or None.
        """
        created_raw = trade.get("created_at")
        if not created_raw:
            return None

        try:
            created = datetime.fromisoformat(str(created_raw))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None

        elapsed_min = (now - created).total_seconds() / 60.0
        state = trade["state"]
        trade_id = trade["trade_id"]
        symbol = trade["symbol"]
        direction = trade["direction"]

        # Load probability data for dynamic thresholds
        prob = self._load_prob(trade)
        p75_factor   = float(self._cfg.exit("p75_factor", 1.4))
        cfg_max_min  = float(self._cfg.time("max_time_min", 15))
        min_floor    = float(self._cfg.time("min_time_min", 3))

        # Hard cap — dynamic when prob is trusted, static otherwise
        # Prob engine can only SHORTEN the hard cap (capped at cfg_max_min)
        # Floor of min_floor prevents pathological near-zero firing
        if self._prob_trusted(prob):
            raw_hard = prob["expected_time_tp2"] * p75_factor
            hard_stop_min = max(min(raw_hard, cfg_max_min), min_floor)
        else:
            hard_stop_min = cfg_max_min

        if elapsed_min >= hard_stop_min:
            logger.info(
                "INOUT.SM: HARD TIME-STOP trade=%s elapsed=%.1f min >= %.1f "
                "(prob_driven=%s)",
                trade_id, elapsed_min, hard_stop_min, self._prob_trusted(prob),
            )
            runner_frac = float(self._cfg.exit("runner_fraction", 0.20))
            remaining_frac = self._remaining_fraction(state, runner_frac)
            return ActionInstruction(
                action=ActionType.EXIT_FULL,
                trade_id=trade_id, symbol=symbol, direction=direction,
                new_state="TIMEOUT",
                fraction=remaining_frac,
                exit_tier=99,
                exit_reason="MAX_TIME_STOP",
                meta={
                    "elapsed_min": round(elapsed_min, 2),
                    "hard_stop_min": round(hard_stop_min, 2),
                    "prob_driven": self._prob_trusted(prob),
                },
            )

        # Soft cap — ACTIVE state only (Tier 1 not yet hit)
        # Dynamic when prob trusted, falls back to config default
        if state == "ACTIVE":
            min_min = float(self._cfg.time("min_time_min", 3))
            if self._prob_trusted(prob):
                soft_stop_min = max(prob["expected_time_tp1"] * p75_factor, min_min)
            else:
                soft_stop_min = float(self._cfg.time("default_time_min", 8))

            if elapsed_min >= soft_stop_min and elapsed_min >= min_min:
                logger.info(
                    "INOUT.SM: SOFT TIME-STOP trade=%s elapsed=%.1f min >= %.1f "
                    "(prob_driven=%s)",
                    trade_id, elapsed_min, soft_stop_min, self._prob_trusted(prob),
                )
                return ActionInstruction(
                    action=ActionType.EXIT_FULL,
                    trade_id=trade_id, symbol=symbol, direction=direction,
                    new_state="TIMEOUT",
                    fraction=1.0,
                    exit_tier=99,
                    exit_reason="SOFT_TIME_STOP",
                    meta={
                        "elapsed_min": round(elapsed_min, 2),
                        "soft_stop_min": round(soft_stop_min, 2),
                        "prob_driven": self._prob_trusted(prob),
                    },
                )

        return None

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _sl_hit(direction: str, price: float, sl: float) -> bool:
        if direction == "LONG":
            return price <= sl
        return price >= sl

    @staticmethod
    def _tp_hit(direction: str, price: float, tp: float) -> bool:
        if direction == "LONG":
            return price >= tp
        return price <= tp

    @staticmethod
    def _trail_improved(direction: str, new_trail: float, current_trail: float) -> bool:
        """True if new trail is more protective (closer to current price)."""
        if direction == "LONG":
            return new_trail > current_trail
        return new_trail < current_trail

    def _load_prob(self, trade: dict[str, Any]) -> dict[str, Any]:
        """
        Load and validate the probability snapshot stored at entry time.

        Returns a typed dict with all required keys present.
        Falls back to _PROB_DEFAULTS (confidence=0.0) on any error, which
        guarantees all prob-gated branches are skipped when data is unavailable.

        Handles:
            - NULL / missing prob_snapshot column
            - Empty string
            - Already-decoded dict (unit tests bypass JSON encoding)
            - Malformed JSON
        """
        raw = trade.get("prob_snapshot")
        parsed: dict[str, Any] = {}

        if raw is None or raw == "":
            pass  # keep parsed = {}, fall through to defaults
        elif isinstance(raw, dict):
            parsed = raw  # already decoded (e.g. from unit test fixture)
        else:
            try:
                parsed = json.loads(str(raw))
            except (json.JSONDecodeError, TypeError, ValueError):
                logger.debug(
                    "INOUT.SM: prob_snapshot parse error trade=%s — using defaults",
                    trade.get("trade_id", "?"),
                )

        result = dict(_PROB_DEFAULTS)
        for key in (
            "tp1_prob", "tp2_prob", "runner_prob",
            "expected_time_tp1", "expected_time_tp2",
            "expected_rr", "confidence",
        ):
            if key in parsed:
                try:
                    result[key] = float(parsed[key])
                except (TypeError, ValueError):
                    pass  # keep default
        if "n_samples" in parsed:
            try:
                result["n_samples"] = int(parsed["n_samples"])
            except (TypeError, ValueError):
                pass
        if "warnings" in parsed:
            result["warnings"] = list(parsed.get("warnings", []))

        return result

    def _prob_trusted(self, prob: dict[str, Any]) -> bool:
        """
        FIX 1 — Probability Trust Filter.

        Returns True only when BOTH conditions hold:
          (a) confidence > min_confidence_for_prob_exit  (model quality gate)
          (b) n_samples >= min_prob_samples              (sample size gate)

        Prevents small-sample overfitting from driving exit decisions.
        When prob_snapshot is absent, _load_prob() returns confidence=0.0 and
        n_samples=0, so this always returns False → full backward compatibility.
        """
        min_conf = float(self._cfg.exit("min_confidence_for_prob_exit", 0.2))
        min_samp = int(self._cfg.exit("min_prob_samples", 20))
        return (
            float(prob.get("confidence", 0.0)) > min_conf
            and int(prob.get("n_samples", 0)) >= min_samp
        )

    def _compute_trail_sl(
        self,
        trade: dict[str, Any],
        price: float,
        atr: float | None,
        direction: str,
    ) -> float | None:
        if atr is None or atr == 0.0:
            return None
        mult = float(self._cfg.exit("runner_trail_atr_mult", 2.5))
        prec = self._price_precision(trade["symbol"])
        if direction == "LONG":
            return round(price - atr * mult, prec)
        return round(price + atr * mult, prec)

    def _compute_trail_sl_adaptive(
        self,
        trade: dict[str, Any],
        price: float,
        atr: float | None,
        direction: str,
        mult: float,
    ) -> float | None:
        """
        Identical to _compute_trail_sl but takes an explicit multiplier.
        Used only by _evaluate_harvested() for prob-adaptive trailing.
        _compute_trail_sl() remains unchanged for _evaluate_protected().
        """
        if atr is None or atr == 0.0:
            return None
        prec = self._price_precision(trade["symbol"])
        if direction == "LONG":
            return round(price - atr * mult, prec)
        return round(price + atr * mult, prec)

    @staticmethod
    def _remaining_fraction(state: str, runner_frac: float) -> float:
        """Fraction still open depending on how far through SEP-01 we are."""
        if state in ("PENDING", "ACTIVE"):
            return 1.0
        if state == "PROTECTED":
            # T1 done (30%), remaining = 70%
            return 1.0 - 0.30
        if state == "HARVESTED":
            # T1+T2 done, remaining = runner
            return runner_frac
        return 1.0

    @staticmethod
    def _price_precision(symbol: str) -> int:
        precision_map = {
            "BTCUSDT": 2, "ETHUSDT": 2, "BNBUSDT": 3,
            "SOLUSDT": 3, "XRPUSDT": 5,
        }
        return precision_map.get(symbol.upper(), 5)
