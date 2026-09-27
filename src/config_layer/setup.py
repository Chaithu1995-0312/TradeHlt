"""Setup value object — the execution-side variant surface (STORY-83.11, EPIC-83 S3).

See docs/implementation_plan/setup-overlay-spec-2026-09.md for the full design and the
recorded user decisions (§10). A Setup = a production config (by version) plus the small
declared overlay of §3, whose every key defaults to today's behaviour (§3.1). Frozen: read
once, never re-read mid-run — same idiom as runtime.layer_trace.LayerTraceConfig.from_prod_config
(src/runtime/layer_trace.py:108-130).

Dependency direction (§4): research imports execution; execution never imports research
(verified: `git grep -n 'from research\\.|import research\\b' -- src/':!src/research'` → 0 hits).
This module lives in config_layer precisely so research MAY import it without creating the
reverse edge.

Not the overlay's authority (§6.5): the overlay grants tunability, never authority. Whether a
Setup's non-default value ever reaches production is a separate, later, authorized decision
(S5, hand registration) — this module only resolves and validates the declared value.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

#: §3.2 key 2 allowed values.
TARGET_POLICIES = ("fixed_r", "structural_tp2")
#: §3.2 key 4 allowed values.
DECIDERS = ("engine", "resolver")
#: §3.2 key 1 / K23 F3 allowed values (existing, mirrors BacktestConfig.from_prod_config).
SL_ANCHORS = ("displacement", "sweep_extreme")
#: §3.2 key 6 / K23 F2 allowed values (existing).
SESSION_WINDOW_BASES = ("broker_static", "exchange_local")

#: §3.2 DEFAULT column — every key's default equals today's behaviour, byte-for-byte.
DEFAULTS: dict = {
    "sl_anchor": "displacement",
    "target_policy": "fixed_r",
    "trade_ttl_candles": None,
    "decider": "engine",
    "retrace_reset_pct": 0.5,
    "session_window_basis": "broker_static",
    "htf_reset_exempt_sweep": False,
}


@dataclass(frozen=True)
class Setup:
    """Resolved Setup: the seven §3.2 keys, at one stated production config `version`.

    Keys 1 and 5-7 (`sl_anchor`, `retrace_reset_pct`, `session_window_basis`,
    `htf_reset_exempt_sweep`) are EXISTING config keys (K23 F1/F2/F3/F4) — a Setup reads them
    here only for its own self-description (§3.7 stamping / §10 Q9 "inherit, not re-state").
    `BacktestConfig.from_prod_config` (src/runtime/backtest_v2.py) remains their real load path
    into the engine; this class does not re-declare or re-validate them for that purpose, only
    reads the same value under the same rule so a Setup can describe itself completely.
    Keys 2-4 (`target_policy`, `trade_ttl_candles`, `decider`) are new and load ONLY here
    (§3.3 Option A — one new top-level `setup` section, user decision 2026-09-28).
    """

    version: str
    sl_anchor: str
    target_policy: str
    trade_ttl_candles: Optional[int]
    decider: str
    retrace_reset_pct: float
    session_window_basis: str
    htf_reset_exempt_sweep: bool

    @classmethod
    def from_prod_config(cls, version: str) -> "Setup":
        """Build a Setup for `version`.

        §3.6 load rules: an absent key resolves to its §3.2 DEFAULT; a present key is strictly
        validated and raises **at load**, never at first use. `setup` is itself an optional
        section — absent entirely means every new key (2-4) is at default.
        """
        from config_layer.production_config import get_prod_section

        try:
            setup_section = get_prod_section("setup", version=version)
        except RuntimeError:
            setup_section = {}

        target_policy = setup_section.get("target_policy", DEFAULTS["target_policy"])
        if target_policy not in TARGET_POLICIES:
            raise ValueError(
                f"Setup: setup.target_policy={target_policy!r} must be one of {TARGET_POLICIES}"
            )

        trade_ttl_candles = setup_section.get("trade_ttl_candles", DEFAULTS["trade_ttl_candles"])
        if trade_ttl_candles is not None:
            if (
                not isinstance(trade_ttl_candles, int)
                or isinstance(trade_ttl_candles, bool)
                or trade_ttl_candles < 1
            ):
                raise ValueError(
                    "Setup: setup.trade_ttl_candles must be an int >= 1 or null (no time-stop), "
                    f"got {trade_ttl_candles!r}"
                )

        decider = setup_section.get("decider", DEFAULTS["decider"])
        if decider not in DECIDERS:
            raise ValueError(f"Setup: setup.decider={decider!r} must be one of {DECIDERS}")

        backtest = get_prod_section("backtest", version=version)
        sl_anchor = backtest.get("sl_anchor", DEFAULTS["sl_anchor"])
        if sl_anchor not in SL_ANCHORS:
            raise ValueError(f"Setup: backtest.sl_anchor={sl_anchor!r} must be one of {SL_ANCHORS}")
        session_window_basis = backtest.get(
            "session_window_basis", DEFAULTS["session_window_basis"]
        )
        if session_window_basis not in SESSION_WINDOW_BASES:
            raise ValueError(
                f"Setup: backtest.session_window_basis={session_window_basis!r} must be "
                f"one of {SESSION_WINDOW_BASES}"
            )
        htf_reset_exempt_sweep = backtest.get(
            "htf_reset_exempt_sweep", DEFAULTS["htf_reset_exempt_sweep"]
        )
        if not isinstance(htf_reset_exempt_sweep, bool):
            raise ValueError(
                "Setup: backtest.htf_reset_exempt_sweep must be a JSON boolean, got "
                f"{htf_reset_exempt_sweep!r}"
            )

        crt_engine = get_prod_section("crt_engine", version=version)
        retrace_reset_pct = crt_engine.get("retrace_reset_pct", DEFAULTS["retrace_reset_pct"])
        if (
            not isinstance(retrace_reset_pct, (int, float))
            or isinstance(retrace_reset_pct, bool)
            or not (0 < float(retrace_reset_pct) <= 1)
        ):
            raise ValueError(
                f"Setup: crt_engine.retrace_reset_pct={retrace_reset_pct!r} must be in (0, 1]"
            )

        return cls(
            version=version,
            sl_anchor=sl_anchor,
            target_policy=target_policy,
            trade_ttl_candles=trade_ttl_candles,
            decider=decider,
            retrace_reset_pct=float(retrace_reset_pct),
            session_window_basis=session_window_basis,
            htf_reset_exempt_sweep=htf_reset_exempt_sweep,
        )

    def non_default_keys(self) -> dict:
        """§3.7 stamping: every overlay key whose value differs from its §3.2 DEFAULT.

        A run must stamp this in its own summary — an empty dict means the Setup is v5 itself
        (§8 P-1 inertness); a non-empty dict names exactly what makes this run not reproducible
        from v5 alone.
        """
        return {
            key: getattr(self, key)
            for key, default in DEFAULTS.items()
            if getattr(self, key) != default
        }
