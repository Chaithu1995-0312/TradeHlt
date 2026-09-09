"""
live_engine.py
═══════════════════════════════════════════════════════════════════════════════
Live trading decision + Telegram alert system.

Design principles:
  - NO auto-trading, NO broker calls, NO order placement
  - Human is ALWAYS final executor
  - Gaussian = primary signal, ML = advisory layer
  - Every alert (sent or suppressed) is logged to logs/live_alerts.jsonl
  - Per-symbol cooldown + duplicate setup filter prevent spam
  - Kill switch via env var LIVE_ENGINE_ENABLED=0

Usage:
    from live_engine import LiveEngine, LiveEngineConfig
    engine = LiveEngine(LiveEngineConfig.from_env())
    result = engine.process(trade_data, gaussian_model, scaler, neural_fn)
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

log = logging.getLogger("LiveEngine")

try:
    from utils.registry_refresh import RegistryWatcher
except Exception:  # pragma: no cover — keep live engine importable in stripped envs
    class RegistryWatcher:  # type: ignore[no-redef]
        def __init__(self, *_a, **_kw): pass
        def needs_reload(self) -> bool: return False
        def mark_loaded(self) -> None: pass

LOGS_DIR       = Path("logs")
ALERT_LOG_PATH = LOGS_DIR / "live_alerts.jsonl"

# Default zone runtime artifact — layout owned by ModelPaths (Phase 0).
# Version selection remains models/zone_gate_registry.json via ModelResolver.
from config_layer.model_paths import ModelPaths as _ModelPaths
ZONE_REGISTRY_PATH = str(_ModelPaths.ZONE_GATE_RUNTIME_ALIAS)

# ─────────────────────────────────────────────────────────────────────────────
# BITNET ZONE GATE
# ─────────────────────────────────────────────────────────────────────────────

def get_zone_registry_path(instrument: str, base_dir: str = "models/bitnet") -> str:
    """
    Return the per-instrument BitNet registry path if it exists,
    otherwise fall back to the global registry.
    """
    inst = (instrument or "").upper()
    if inst:
        cand = os.path.join(base_dir, inst, "zone_registry.json")
        if os.path.exists(cand):
            return cand
    return ZONE_REGISTRY_PATH


class ZoneFeatureOrderError(RuntimeError):
    """The zone registry's trained `feature_order` cannot be aligned to the live feature schema.

    Raised at LOAD time, never per-bar, and never swallowed by the fail-open registry handlers.
    A hard gate (F-041) that scores a misaligned vector decides confidently and wrongly, which is
    strictly worse than not starting.
    """


class BitNetZoneGate:
    """
    Trade filter using discovered BitNet zones.

    Loads the zone registry (written by BitNetSearchEngine / run_bitnet_search)
    and gates incoming trades: only trades whose Gaussian score >= zone threshold
    are allowed through.

    Design principles
    -----------------
    - FAIL OPEN: if registry missing or malformed → gate is disabled, all trades pass
    - Non-blocking: gate never raises, logs warnings on errors
    - Transparent: always logs the gate decision with score details

    Usage
    -----
        gate = BitNetZoneGate()          # loads registry on init
        gate = BitNetZoneGate.from_path("models/zone_registry.json")

        decision = gate.check(features)
        # {"allowed": True/False, "score": 0.78, "threshold": 0.72, "zone_id": "zone_001"}
    """

    def __init__(
        self,
        zones:     list = None,
        zone_path: str  = ZONE_REGISTRY_PATH,
        enabled:   bool = True,
        config:    dict = None,
    ):
        """
        Parameters
        ----------
        zones     : pre-loaded zone list (if None, loaded from zone_path)
        zone_path : path to zone_registry.json (default ZONE_REGISTRY_PATH)
        enabled   : if False, gate is a no-op pass-through (default True)
        config    : optional config dict. Supports:
                    ``zone_min_samples`` (int, default 50) — if the total
                    training sample count across all zones is below this
                    threshold, the gate auto-bypasses with reason
                    "underpowered_zone_registry" rather than producing
                    spurious rejections from an under-trained registry.
        """
        self.enabled    = enabled
        self._zone_path = zone_path
        self._zones: list = []
        self._underpowered: bool = False
        # SCHEMA-V4 SAFETY NET (2026-07-22): the feature-name order the on-disk zone vectors
        # (`mu`/`sigma`/`weights`) are aligned to. Read from the registry's own top-level
        # `feature_order`; None means the registry predates the field and the caller must fall
        # back to the ambient canonical order. See _validate_feature_order.
        self.feature_order: list | None = None
        # Number of top zone scores surfaced as ``top_scores`` for cluster weighting.
        # The live spine enforces this fail-fast at the engine_runner config boundary
        # (engine_runner.zone_gate.top_k); the soft default here serves only standalone /
        # manual callers (direct instantiation, _smoke_test.py). Default 3 = historical.
        self._top_n: int = int((config or {}).get("zone_gate_top_k", 3))
        # Hot-reload watcher: detects discover_zones promotion mid-session.
        self._watcher = RegistryWatcher(zone_path)

        if not enabled:
            log.info("BitNetZoneGate: disabled (pass-through mode)")
            return

        if zones is not None:
            self._zones = zones
        else:
            self._load_registry(zone_path)
        self._watcher.mark_loaded()

        log.info(f"BitNetZoneGate: loaded {len(self._zones)} zones from {zone_path}")

        # ── Underpowered-registry guard ─────────────────────────────────────
        # The zone "weight" field tracks the number of training samples in each
        # cluster.  If the total is below zone_min_samples the registry was
        # built from too few trades (often a cross-instrument bootstrap) and
        # will produce noisy similarity scores.  In that case the gate
        # auto-bypasses rather than injecting spurious rejections.
        _cfg = config or {}
        # T-22: NOT a silent config default. This is the standalone/unit-test tier of the
        # same two-tier pattern used by core.acceptance_controller.__init__ — the live path
        # always arrives via get_zone_gate(), which is fed from engine_runner's fail-fast
        # _cfg_require("zone_min_samples"). A caller that constructs this class directly with
        # no config is by definition not the configured spine, so there is no config to
        # silently fall back FROM. Do not "fix" this to a strict read: it would break
        # standalone construction without closing any real config-drift hole.
        _min_samples = float(_cfg.get("zone_min_samples", 50))
        _total_samples = sum(float(z.get("weight", 0)) for z in self._zones)
        if self._zones and _total_samples < _min_samples:
            self._underpowered = True
            log.warning(
                "BitNetZoneGate: registry has only %.0f training samples "
                "(threshold %.0f).  Gate will auto-bypass with reason "
                "'underpowered_zone_registry'.  Rebuild the registry with "
                ">= %.0f per-instrument profitable trades to re-activate.",
                _total_samples, _min_samples, _min_samples,
            )

    @classmethod
    def from_path(cls, path: str = ZONE_REGISTRY_PATH) -> "BitNetZoneGate":
        """Factory: create gate from registry path."""
        return cls(zone_path=path)

    @classmethod
    def disabled(cls) -> "BitNetZoneGate":
        """Factory: create a disabled gate (always allows trades)."""
        return cls(enabled=False)

    def _validate_feature_order(self, path: str) -> None:
        """Read + validate the registry's `feature_order` against the live schema (FAIL-CLOSED).

        WHY THIS EXISTS (2026-07-22). `models/zone_registry.json` has always stored a
        `feature_order` name list alongside the zone vectors, but NOTHING read it: the scoring
        vector was built from the ambient `CANONICAL_FEATURE_ORDER` and
        `zone_gate_engine._extract_vector` SILENTLY TRUNCATED anything longer (a v2.0(35)->v3.0(38)
        back-compat path). ZoneGate is the only LIVE hard gate (F-041, zone_mode=hard) and every
        other trained consumer is inert or off (F-004/F-005/F-038/F-060), so a schema change that
        reordered or extended the vector would have made this gate score against misaligned
        `mu`/`sigma` and raise nothing at all.

        A misalignment is NOT fail-open. Failing open would silently disable a hard gate; failing
        closed per-bar would be a silent outage. So this raises ONCE, at load, and refuses to
        construct — the process does not start rather than mis-decide.
        """
        try:
            with open(path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return   # generic load failure is handled (fail-open) by the caller's except blocks

        order = raw.get("feature_order")
        if not order:
            log.warning(
                "BitNetZoneGate: registry %s has no `feature_order`; falling back to the ambient "
                "canonical order. This is only safe while the schema is unchanged since training.",
                path,
            )
            return

        from features.feature_schema import CANONICAL_FEATURE_ORDER
        live = set(CANONICAL_FEATURE_ORDER)
        missing = [n for n in order if n not in live]
        if missing:
            raise ZoneFeatureOrderError(
                f"zone registry {path} was trained on feature(s) absent from the live schema: "
                f"{missing}. The registry must be remapped or retrained before this gate can "
                f"score — refusing to start rather than score against a misaligned vector."
            )
        self.feature_order = list(order)

    def _load_registry(self, path: str) -> None:
        """Load zone registry from JSON. Fail-safe: empty zones on any error.

        EXCEPTION: `ZoneFeatureOrderError` is deliberately NOT caught — see _validate_feature_order.
        """
        try:
            from bitnet.zone_cosine_searcher import load_zone_registry
            self._validate_feature_order(path)
            zones = load_zone_registry(path)
            # Validate expected BitNet schema (mu/sigma/weights/threshold)
            valid = [
                z for z in zones
                if isinstance(z, dict)
                and "mu" in z
                and "sigma" in z
                and "weights" in z
                and "threshold" in z
            ]
            if zones and not valid:
                log.warning(
                    "BitNetZoneGate: invalid zone registry schema (missing mu/sigma/weights/threshold); "
                    "gate disabled (fail-open)"
                )
                self._zones = []
            else:
                if len(valid) != len(zones):
                    log.warning(
                        f"BitNetZoneGate: filtered {len(zones) - len(valid)} invalid zones "
                        f"from registry {path}"
                    )
                self._zones = valid
        except ZoneFeatureOrderError:
            # Vector-alignment failure — NEVER fail open. A hard gate scoring a misaligned vector
            # is worse than no gate, because it decides confidently and wrongly.
            raise
        except ImportError:
            # bitnet module not yet installed — fail open
            log.warning("BitNetZoneGate: bitnet module not available, gate disabled")
            self._zones = []
        except Exception as e:
            log.warning(f"BitNetZoneGate: registry load error ({e}), gate disabled")
            self._zones = []

    @property
    def is_loaded(self) -> bool:
        """True if at least one zone is loaded."""
        return self.enabled and len(self._zones) > 0

    def check(self, features: list) -> dict:
        """
        Gate an incoming trade based on its feature vector.

        Parameters
        ----------
        features : list[float] — 11-dim feature vector from rr_dataset_builder

        Returns
        -------
        dict:
            allowed   : bool  — True = trade passes the gate
            score     : float — best Gaussian score across all zones
            threshold : float — threshold of the zone that was tested
            zone_id   : str   — ID of the best-matching zone
            reason    : str   — human-readable gate decision reason
        """
        # Hot-reload: if zone_registry.json was rewritten since last check,
        # refresh in place. Cheap stat() per candle.
        if self.enabled and self._watcher.needs_reload():
            log.info("BitNetZoneGate: registry changed at %s; reloading", self._zone_path)
            self.reload()

        # Gate explicitly disabled → always allow
        if not self.enabled:
            return {
                "allowed":   True,
                "score":     1.0,
                "threshold": 0.0,
                "zone_id":   None,
                "reason":    "gate_disabled",
            }

        # Underpowered registry → auto-bypass (avoid spurious rejections from
        # a registry built on too few / cross-instrument training samples).
        if self._underpowered:
            return {
                "allowed":   True,
                "score":     1.0,
                "threshold": 0.0,
                "zone_id":   None,
                "reason":    "underpowered_zone_registry",
                "top_scores": [],
            }

        # No zones loaded → CRITICAL log + fail-CLOSED.
        #
        # NAMING CORRECTED (was "no_zones_fail_open", which stated the opposite of the
        # behaviour): omitting `top_scores` below makes zone_cluster_score._model_fn fall
        # through to `result.get("score", 0.5)` → 0.0, which fails any positive
        # zone_cluster_threshold (0.25 on the active config) → every candle BLOCKS.
        # The omission is deliberate and load-bearing — do not add `top_scores` here
        # without deciding the pass/block question explicitly.
        #
        # Contrast with the two branches above, which DO pass: `gate_disabled` and
        # `underpowered_zone_registry` both return score 1.0. Blocking on an empty
        # registry is the intended asymmetry — an unloadable registry must not silently
        # admit unfiltered trades.
        if not self._zones:
            log.critical(
                "BitNetZoneGate: no zones loaded — gate is BLOCKING all trades "
                "(fail-closed). Run BitNetSearchEngine.run_search() + save_zones() "
                "first. No trade can pass the zone gate until the registry loads."
            )
            return {
                "allowed":   False,
                "score":     0.0,
                "threshold": 0.0,
                "zone_id":   "none",
                "reason":    "no_zones_fail_closed",
            }

        # Score against all zones; allow if ANY zone passes
        try:
            from bitnet.zone_cosine_searcher import compute_gaussian_score as _cgs
        except ImportError:
            return {
                "allowed": True, "score": 1.0, "threshold": 0.0,
                "zone_id": "none", "reason": "bitnet_unavailable",
            }

        best_score    = 0.0
        best_zone_id  = "none"
        best_thresh   = 0.0
        allowed       = False
        all_scores: list = []

        # NOTE: the per-zone `allowed`/`reason` decision computed below is part of this
        # method's standalone return contract, but it is BYPASSED by the live spine. The
        # real gate decision is made in engines.zone_cluster_score.score_zone_cluster:
        #   compute_weighted_cluster_score(top_scores) >= zone_cluster_threshold.

        # `top_scores` (length = self._top_n, config: engine_runner.zone_gate.top_k) is the
        # only field the live path consumes from this result.
        for zone in self._zones:
            try:
                score  = _cgs(features, zone)
                thresh = float(zone.get("threshold", 0.7))
                zid    = zone.get("id", "unknown")
                all_scores.append(float(score))

                if score > best_score:
                    best_score   = score
                    best_zone_id = zid
                    best_thresh  = thresh

                if score >= thresh:
                    allowed = True
                    # Don't break — we want the best_score logged
            except Exception as e:
                log.debug(f"Zone scoring error for {zone.get('id', '?')}: {e}")

        # Return top-k scores for nearest-neighbour cluster weighting (k = self._top_n)
        top_scores = sorted(all_scores, reverse=True)[: self._top_n]

        reason = "zone_passed" if allowed else "zone_rejected"
        return {
            "allowed":    allowed,
            "score":      round(best_score,  4),
            "threshold":  round(best_thresh, 4),
            "zone_id":    best_zone_id,
            "reason":     reason,
            "top_scores": top_scores,
        }

    def reload(self) -> None:
        """Reload zone registry from disk (useful for hot-reload in live sessions)."""
        self._load_registry(self._zone_path)
        log.info(f"BitNetZoneGate reloaded: {len(self._zones)} zones")


# Singleton — one gate instance shared across LiveEngine instances.
# Lazy-loaded on first use. Thread-safe for read-only access.
_ZONE_GATE: Optional["BitNetZoneGate"] = None


def get_zone_gate(
    path: str = ZONE_REGISTRY_PATH,
    min_samples: int = 50,
    top_n: int = 3,
) -> "BitNetZoneGate":
    """
    Get (or create) the singleton BitNetZoneGate.

    Lazy-loads on first call. Subsequent calls return the same instance.
    Call get_zone_gate().reload() to force refresh from disk.

    Parameters
    ----------
    path        : Path to zone registry JSON.
    min_samples : Minimum total training samples required before the gate is
                  active.  Registries with fewer samples auto-bypass.
                  Mirrors ``engine_runner.zone_min_samples`` in the prod config.
    top_n       : Number of top-scoring zones returned as ``top_scores`` for the
                  downstream cluster-weighting step.  Mirrors
                  ``engine_runner.zone_gate.top_k`` in the prod config; the spine
                  always supplies it via fail-fast _cfg_require (default 3 here
                  preserves the historical behaviour for standalone callers).
    """
    global _ZONE_GATE
    if _ZONE_GATE is None:
        _ZONE_GATE = BitNetZoneGate(
            zone_path=path,
            config={"zone_min_samples": min_samples, "zone_gate_top_k": top_n},
        )
    return _ZONE_GATE


# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LiveEngineConfig:
    """
    All live engine parameters. Load from env with LiveEngineConfig.from_env().

    Environment variables:
        TELEGRAM_BOT_TOKEN       : required for sending alerts
        TELEGRAM_CHAT_ID         : required for sending alerts
        LIVE_ENGINE_ENABLED      : set to "1" to enable (default: disabled)
        LIVE_RR_THRESHOLD        : minimum expected RR to consider (default 1.5)
        LIVE_CONF_MIN            : minimum confidence to avoid BLOCK (default 0.55)
        LIVE_CONF_STRONG         : confidence threshold for strong setup (default 0.60)
        LIVE_ML_OVERRIDE         : ML score threshold for WATCH signal (default 0.75)
        LIVE_COOLDOWN_SECONDS    : per-symbol alert cooldown (default 60)
        LIVE_DEDUP_CANDLES       : same setup dedup window in candles (default 4)
    """
    bot_token:              str   = ""
    chat_id:                str   = ""
    enabled:                bool  = False
    rr_threshold:           float = 1.5
    confidence_min:         float = 0.55
    confidence_strong:      float = 0.60
    ml_override_threshold:  float = 0.75
    alert_cooldown_seconds: int   = 60
    dedup_candles:          int   = 4

    @classmethod
    def from_env(cls) -> "LiveEngineConfig":
        return cls(
            bot_token              = os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            chat_id                = os.environ.get("TELEGRAM_CHAT_ID",   ""),
            enabled                = os.environ.get("LIVE_ENGINE_ENABLED", "0") == "1",
            rr_threshold           = float(os.environ.get("LIVE_RR_THRESHOLD",    "1.5")),
            confidence_min         = float(os.environ.get("LIVE_CONF_MIN",        "0.55")),
            confidence_strong      = float(os.environ.get("LIVE_CONF_STRONG",     "0.60")),
            ml_override_threshold  = float(os.environ.get("LIVE_ML_OVERRIDE",     "0.75")),
            alert_cooldown_seconds = int(os.environ.get("LIVE_COOLDOWN_SECONDS",  "60")),
            dedup_candles          = int(os.environ.get("LIVE_DEDUP_CANDLES",     "4")),
        )

    def validate(self) -> list[str]:
        """Return list of config warnings (non-fatal)."""
        issues = []
        if not self.bot_token:
            issues.append("TELEGRAM_BOT_TOKEN not set — alerts will be logged only")
        if not self.chat_id:
            issues.append("TELEGRAM_CHAT_ID not set — alerts will be logged only")
        if not self.enabled:
            issues.append("LIVE_ENGINE_ENABLED=0 — engine is in DRY RUN mode")
        return issues


# ─────────────────────────────────────────────────────────────────────────────
# DECISION LOGIC
# ─────────────────────────────────────────────────────────────────────────────

def decide_trade(
    expected_rr:  float,
    confidence:   float,
    ml_score:     Optional[float],
    threshold:    float = 1.5,
    conf_min:     float = 0.55,
    conf_strong:  float = 0.60,
    ml_override:  float = 0.75,
) -> tuple[str, str]:
    """
    Deterministic decision engine. Returns (decision, reason).

    Decision ladder (evaluated top-to-bottom, first match wins):
      1. confidence < conf_min             → BLOCK  (low_confidence)
      2. rr >= threshold AND conf >= strong → EXECUTE (strong_setup)
      3. rr >= threshold AND conf < strong  → WARN   (rr_good_but_low_conf)
      4. ml_score > ml_override AND rr < t  → WATCH  (ml_disagrees_positive)
      5. otherwise                          → BLOCK  (no_edge)

    Parameters
    ----------
    expected_rr  : Gaussian expected risk/reward
    confidence   : max P(class) from Gaussian
    ml_score     : optional neural/ML score (None if not available)
    threshold    : minimum expected_rr to execute (default 1.5)
    conf_min     : below this → always block (default 0.55)
    conf_strong  : threshold for 'strong' confidence (default 0.60)
    ml_override  : ML score that triggers WATCH even if rr below threshold
    """
    # Rule 1: Hard block on low confidence
    if confidence < conf_min:
        return "BLOCK", "low_confidence"

    # Rule 2: Strong setup — both RR and confidence meet bars
    if expected_rr >= threshold and confidence >= conf_strong:
        return "EXECUTE", "strong_setup"

    # Rule 3: RR good but confidence borderline
    if expected_rr >= threshold and confidence < conf_strong:
        return "WARN", "rr_good_but_low_conf"

    # Rule 4: ML has strong positive view despite weak Gaussian
    if ml_score is not None and ml_score > ml_override and expected_rr < threshold:
        return "WATCH", "ml_disagrees_positive"

    # Default: no clear edge
    return "BLOCK", "no_edge"


# ─────────────────────────────────────────────────────────────────────────────
# TELEGRAM SENDER
# ─────────────────────────────────────────────────────────────────────────────

def send_telegram_alert(
    message:   str,
    bot_token: str,
    chat_id:   str,
    timeout:   int = 5,
) -> tuple[bool, Optional[str]]:
    """
    Send a Telegram message. Fail-safe — never raises.

    Returns (success: bool, error: str | None)
    """
    if not bot_token or not chat_id:
        log.debug("Telegram not configured — message suppressed (bot_token or chat_id missing)")
        return False, "not_configured"

    try:
        import requests  # type: ignore
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id":    chat_id,
            "text":       message,
            "parse_mode": "Markdown",
        }
        resp = requests.post(url, json=payload, timeout=timeout)
        if resp.status_code == 200:
            return True, None
        else:
            err = f"HTTP {resp.status_code}: {resp.text[:200]}"
            log.warning(f"Telegram send failed: {err}")
            return False, err
    except ImportError:
        log.warning("requests not installed — Telegram alert skipped")
        return False, "requests_not_installed"
    except Exception as e:
        log.warning(f"Telegram exception: {e}")
        return False, str(e)


# ─────────────────────────────────────────────────────────────────────────────
# MESSAGE FORMATTER
# ─────────────────────────────────────────────────────────────────────────────

_DECISION_ICONS = {
    "EXECUTE": "✅",
    "WARN":    "⚠️",
    "WATCH":   "👀",
    "BLOCK":   "❌",
}

def format_alert_message(
    symbol:      str,
    expected_rr: float,
    confidence:  float,
    decision:    str,
    reason:      str,
    ml_score:    Optional[float] = None,
    probabilities: Optional[list] = None,
    regime:      str = "UNKNOWN",
    session:     str = "UNKNOWN",
    time_decay:  float = 1.0,
    timeframe:   str = "M15",
) -> str:
    """
    Format clean, actionable Telegram alert message.
    """
    icon = _DECISION_ICONS.get(decision, "❓")
    ml_line = f"🧠 *ML Score:* `{ml_score:.2f}`\n" if ml_score is not None else ""

    prob_line = ""
    if probabilities and len(probabilities) == 4:
        p_loss, p_small, p_mid, p_big = [round(p, 2) for p in probabilities]
        prob_line = (
            f"📉 Loss `{p_loss:.0%}`  "
            f"📊 Small `{p_small:.0%}`  "
            f"📈 Mid `{p_mid:.0%}`  "
            f"🔥 Big `{p_big:.0%}`\n"
        )

    msg = (
        f"🚨 *TRADE SETUP DETECTED*\n\n"
        f"*Symbol:* `{symbol}`  ·  *TF:* `{timeframe}`\n\n"
        f"📊 *Gaussian Analysis:*\n"
        f"  RR: `{expected_rr:.2f}`\n"
        f"  Confidence: `{confidence:.0%}`\n"
        f"{prob_line}"
        f"\n{ml_line}"
        f"⚖️ *Decision:* {icon} `{decision}`\n"
        f"*Reason:* `{reason}`\n\n"
        f"🔥 Regime: `{regime}`\n"
        f"⏱ Session: `{session}`\n"
        f"⌛ Time Decay: `{time_decay:.2f}`\n\n"
        f"👉 _Accept within 30s or skip_"
    )
    return msg


# ─────────────────────────────────────────────────────────────────────────────
# ALERT STATE (cooldown + dedup)
# ─────────────────────────────────────────────────────────────────────────────

class _AlertState:
    """Tracks per-symbol cooldown and setup deduplication."""

    def __init__(self, cooldown_seconds: int = 60, dedup_candles: int = 4) -> None:
        self._cooldown   = cooldown_seconds
        self._dedup      = dedup_candles
        self._last_time: dict[str, float] = {}
        self._last_setup: dict[str, tuple[str, int]] = {}  # symbol → (setup_hash, candle_idx)

    def _setup_hash(self, symbol: str, session: str, regime: str) -> str:
        key = f"{symbol}:{session}:{regime}"
        return hashlib.md5(key.encode()).hexdigest()[:8]

    def should_alert(self, symbol: str, session: str, regime: str, candle_idx: int = 0) -> tuple[bool, str]:
        now = time.time()

        # Cooldown check
        last = self._last_time.get(symbol, 0.0)
        if now - last < self._cooldown:
            wait = int(self._cooldown - (now - last))
            return False, f"cooldown ({wait}s remaining)"

        # Duplicate setup check
        h = self._setup_hash(symbol, session, regime)
        last_setup = self._last_setup.get(symbol)
        if last_setup:
            last_h, last_cidx = last_setup
            if last_h == h and (candle_idx - last_cidx) < self._dedup:
                return False, f"duplicate_setup (same structure within {self._dedup} candles)"

        return True, "ok"

    def record(self, symbol: str, session: str, regime: str, candle_idx: int = 0) -> None:
        self._last_time[symbol] = time.time()
        h = self._setup_hash(symbol, session, regime)
        self._last_setup[symbol] = (h, candle_idx)


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT LOGGER
# ─────────────────────────────────────────────────────────────────────────────

def _log_alert(entry: dict) -> None:
    """Append alert entry to logs/live_alerts.jsonl (fail-safe)."""
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with ALERT_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        log.warning(f"Audit log write failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# TRAINING-TRIGGER (throttled live-mode evaluation)
# ─────────────────────────────────────────────────────────────────────────────
# Module-level counter — TrainingTrigger.should_trigger() walks the integrity
# log + opportunity glob, which is disk-heavy. We piggyback on LiveEngine.process
# (called every M15 candle) but only do the full check every N invocations.
_BYPASS_CHECK_COUNTER: int = 0
_BYPASS_CHECK_EVERY_N: int = 50  # ~12.5h between checks at 1 candle/15min


def _maybe_telegram_training_alert(
    symbol:     str,
    instrument: str,
    bot_token:  str,
    chat_id:    str,
) -> None:
    """Throttled TrainingTrigger evaluation. On fire: send a Telegram message
    with the pre-filled CLI command and emit TRAINING_RECOMMENDED.

    Cheap counter path runs every call; the heavy gate check + Telegram +
    emit only fires once per _BYPASS_CHECK_EVERY_N invocations. Never raises
    — failure to evaluate the trigger must not break the live decision loop.
    """
    global _BYPASS_CHECK_COUNTER
    _BYPASS_CHECK_COUNTER += 1
    if _BYPASS_CHECK_COUNTER < _BYPASS_CHECK_EVERY_N:
        return
    _BYPASS_CHECK_COUNTER = 0
    try:
        from training.training_trigger import TrainingTrigger
        from utils.integrity_events import emit_integrity_event
        trig = TrainingTrigger.from_prod_config()
        if not trig.should_trigger():
            return
        run_id = time.strftime("%Y%m%d_%H%M%S")
        cli_cmd = (
            "python scripts/auto_train_from_opportunities.py "
            f"--instruments {instrument} --refresh-zones "
            f"--promote-if-approved --run-id {run_id}"
        )
        message = (
            "📊 *Training Recommended*\n"
            f"Symbol: `{symbol}`\n"
            "RR fusion bypass threshold exceeded.\n\n"
            "Run:\n"
            f"`{cli_cmd}`"
        )
        sent, err = send_telegram_alert(
            message=message, bot_token=bot_token, chat_id=chat_id,
        )
        emit_integrity_event(
            "TRAINING_RECOMMENDED", "WARNING", "live_engine",
            {"instrument":     instrument,
             "symbol":         symbol,
             "trigger_source": "live_rr_drift",
             "telegram_sent":  bool(sent),
             "telegram_error": err,
             "cli_cmd":        cli_cmd,
             "run_id":         run_id},
        )
        trig.mark_fired()
    except Exception as exc:  # noqa: BLE001 — never block the live loop
        log.debug("TrainingTrigger live-check failed (non-fatal): %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# LIVE ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class LiveEngine:
    """
    Main live engine orchestrator.

    Integrates:
      - dataset_builder feature construction (single source of truth)
      - GaussianNBModel inference (expected_rr + confidence)
      - Optional neural/ML advisory score
      - Deterministic decision rules
      - Telegram alert dispatch
      - Per-symbol cooldown + dedup filter
      - Audit log (every signal, sent or suppressed)
      - Kill switch (LIVE_ENGINE_ENABLED env var)

    Human remains final executor — this system NEVER places orders.
    """

    def __init__(self, config: Optional[LiveEngineConfig] = None) -> None:
        self.config = config or LiveEngineConfig()
        self._state = _AlertState(
            cooldown_seconds = self.config.alert_cooldown_seconds,
            dedup_candles    = self.config.dedup_candles,
        )

        # Warn about missing config at startup
        issues = self.config.validate()
        for issue in issues:
            log.warning(f"LiveEngine config: {issue}")

    def process(
        self,
        trade_data:     dict,
        gaussian_model,
        scaler,
        neural_fn       = None,
        candle_idx:     int   = 0,
        timeframe:      str   = "M15",
    ) -> dict:
        """
        Full live inference pipeline for one trade setup.

        Parameters
        ----------
        trade_data     : dict with CRT trade fields (see dataset_builder.build_feature_vector)
        gaussian_model : GaussianNBModel from load_active_gaussian_scorer()
        scaler         : StandardScaler from load_active_gaussian_scorer()
        neural_fn      : optional neural callable (from load_active_neural_fn()) — None = skip
        candle_idx     : current candle index for dedup tracking
        timeframe      : label for the alert message

        Returns
        -------
        dict: {decision, reason, expected_rr, confidence, ml_score, sent, suppressed_reason}
        """
        symbol  = str(trade_data.get("symbol", "UNKNOWN"))
        session = str(trade_data.get("session", "UNKNOWN"))
        regime  = str(trade_data.get("regime",  "NEUTRAL"))

        result = {
            "timestamp":        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "symbol":           symbol,
            "decision":         "BLOCK",
            "reason":           "not_processed",
            "expected_rr":      0.0,
            "confidence":       0.0,
            "ml_score":         None,
            "ml_info":          None,
            "probabilities":    None,
            "sent":             False,
            "suppressed_reason": None,
        }

        # ── Kill switch ───────────────────────────────────────────────────────
        if not self.config.enabled:
            log.debug(f"LiveEngine disabled (kill switch) — skipping {symbol}")
            result["suppressed_reason"] = "kill_switch_disabled"
            _log_alert(result)
            return result

        # ── Step 1: Build + validate feature vector ───────────────────────────
        try:
            from features.dataset_builder import build_feature_vector, validate_feature_vector
            from features.feature_schema import CANONICAL_FEATURES
            vec = build_feature_vector(trade_data, lambda_decay=0.05)
            validate_feature_vector(vec, context="LiveEngine.process")
        except Exception as e:
            log.error(f"Feature build failed for {symbol}: {e}")
            result["reason"] = f"feature_error: {e}"
            _log_alert(result)
            return result

        # Snapshot the canonical feature dict + a stable alert_id into the
        # result so logs/live_alerts.jsonl carries the decision context.
        # ingest_live_outcomes.py pairs outcomes against alert_id later.
        feature_snapshot = {
            k: float(trade_data[k])
            for k in CANONICAL_FEATURES
            if k in trade_data
        }
        result["features"]  = feature_snapshot
        result["direction"] = str(trade_data.get("direction", ""))
        result["candle_ts"] = trade_data.get("timestamp") or trade_data.get("candle_ts")
        # Stable per-(symbol, candle_ts, regime, direction) ID — collisions only
        # within the same decision context, which is the dedup level we want.
        _id_seed = f"{symbol}|{result['candle_ts']}|{regime}|{session}|{result['direction']}"
        result["alert_id"] = hashlib.sha1(_id_seed.encode("utf-8")).hexdigest()[:16]

        # ── Step 2: Scale ─────────────────────────────────────────────────────
        try:
            vec_scaled = scaler.transform_one(vec)
        except Exception as e:
            log.error(f"Scaler transform failed for {symbol}: {e}")
            result["reason"] = f"scaler_error: {e}"
            _log_alert(result)
            return result

        # ── Step 3: Gaussian inference ────────────────────────────────────────
        try:
            expected_rr, confidence, probabilities = gaussian_model.predict_expected_rr(vec_scaled)
            result["expected_rr"]   = round(expected_rr,  4)
            result["confidence"]    = round(confidence,   4)
            result["probabilities"] = [round(p, 4) for p in probabilities]
        except Exception as e:
            log.error(f"Gaussian inference failed for {symbol}: {e}")
            result["reason"] = f"gaussian_error: {e}"
            _log_alert(result)
            return result

        # ── Step 4: RR Pattern Miner advisory score (fail-open) ───────────────
        # Uses RRFusionLayer as primary ML source; falls back to neural_fn if
        # the RR model is not loaded. Neither source can override CRT/Gaussian.
        ml_score = None
        ml_info  = None
        try:
            from config_layer.rr.rr_fusion import get_fusion_layer as _get_rr_layer
            _rr_layer = _get_rr_layer()
            if _rr_layer.is_loaded:
                # Augment trade_data with Gaussian results for fusion formula.
                # gaussian_score = Gaussian confidence (0-1 normalized).
                # gaussian_p_win = max class probability from Gaussian model.
                _aug = dict(trade_data)
                _aug["gaussian_score"] = confidence
                _aug["gaussian_p_win"] = (
                    max(probabilities) if probabilities else 0.5
                )
                ml_info  = _rr_layer.score(_aug, threshold=self.config.confidence_min)
                ml_score = ml_info.get("final_score")
        except Exception as e:
            log.debug(f"RR fusion skipped for {symbol}: {e}")

        # Fallback: legacy neural_fn if RR model not available
        if ml_score is None and neural_fn is not None:
            try:
                ml_score = float(neural_fn(vec))
                ml_score = max(0.0, min(1.0, ml_score))
            except Exception as e:
                log.debug(f"ML inference (neural_fn) skipped for {symbol}: {e}")
                ml_score = None

        result["ml_score"] = round(ml_score, 4) if ml_score is not None else None
        result["ml_info"]  = ml_info

        # ── Step 5: Decision ──────────────────────────────────────────────────
        decision, reason = decide_trade(
            expected_rr  = expected_rr,
            confidence   = confidence,
            ml_score     = ml_score,
            threshold    = self.config.rr_threshold,
            conf_min     = self.config.confidence_min,
            conf_strong  = self.config.confidence_strong,
            ml_override  = self.config.ml_override_threshold,
        )
        result["decision"] = decision
        result["reason"]   = reason

        # ── Step 6: Cooldown + dedup filter ──────────────────────────────────
        if decision in ("BLOCK",):
            # Blocked by decision logic — don't even check cooldown
            _log_alert(result)
            return result

        ok_to_alert, suppress_reason = self._state.should_alert(symbol, session, regime, candle_idx)
        if not ok_to_alert:
            result["suppressed_reason"] = suppress_reason
            log.debug(f"Alert suppressed for {symbol}: {suppress_reason}")
            _log_alert(result)
            return result

        # ── Step 7: Format message ────────────────────────────────────────────
        time_decay = float(trade_data.get("time_decay_feature",
                    math.exp(-0.05 * int(trade_data.get("candles_since_retest", 0)))))

        message = format_alert_message(
            symbol        = symbol,
            expected_rr   = expected_rr,
            confidence     = confidence,
            decision       = decision,
            reason         = reason,
            ml_score       = ml_score,
            probabilities  = probabilities,
            regime         = regime,
            session        = session,
            time_decay     = time_decay,
            timeframe      = timeframe,
        )

        # ── Step 8: Send Telegram ─────────────────────────────────────────────
        sent, err = send_telegram_alert(
            message   = message,
            bot_token = self.config.bot_token,
            chat_id   = self.config.chat_id,
        )
        result["sent"] = sent

        if sent:
            self._state.record(symbol, session, regime, candle_idx)
            log.info(
                f"Alert sent | {symbol} | {decision} | "
                f"RR={expected_rr:.2f} conf={confidence:.0%}"
            )
        else:
            log.warning(f"Alert NOT sent for {symbol}: {err}")
            result["suppressed_reason"] = f"telegram_error: {err}"

        # ── Step 9: Audit log ─────────────────────────────────────────────────
        _log_alert(result)

        # ── Step 10: Throttled training-trigger evaluation ────────────────────
        # Cheap per-candle (counter increment); full disk-walk + Telegram only
        # on every Nth call. Never raises.
        _maybe_telegram_training_alert(
            symbol     = symbol,
            instrument = symbol,
            bot_token  = self.config.bot_token,
            chat_id    = self.config.chat_id,
        )
        return result

    def dry_run(
        self,
        trade_data:     dict,
        gaussian_model,
        scaler,
        neural_fn       = None,
        candle_idx:     int = 0,
        timeframe:      str = "M15",
    ) -> dict:
        """
        Run the full pipeline without sending Telegram — for testing/backtesting.
        All validation, inference, and decision logic still executes.
        """
        orig = self.config.enabled
        self.config.enabled = True  # override kill switch so pipeline runs
        orig_token = self.config.bot_token
        self.config.bot_token = ""  # blank token → send_telegram_alert returns (False, not_configured)

        try:
            return self.process(trade_data, gaussian_model, scaler, neural_fn, candle_idx, timeframe)
        finally:
            self.config.enabled   = orig
            self.config.bot_token = orig_token


# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE: standalone alert from raw scores (no model needed)
# ─────────────────────────────────────────────────────────────────────────────

def alert_from_scores(
    symbol:      str,
    expected_rr: float,
    confidence:  float,
    ml_score:    Optional[float] = None,
    regime:      str = "NEUTRAL",
    session:     str = "UNKNOWN",
    time_decay:  float = 1.0,
    config:      Optional[LiveEngineConfig] = None,
    timeframe:   str = "M15",
) -> dict:
    """
    Send a Telegram alert directly from pre-computed scores.
    Useful when Gaussian and ML inference are run outside LiveEngine.

    Returns result dict.
    """
    cfg = config or LiveEngineConfig.from_env()

    decision, reason = decide_trade(
        expected_rr = expected_rr,
        confidence  = confidence,
        ml_score    = ml_score,
        threshold   = cfg.rr_threshold,
        conf_min    = cfg.confidence_min,
        conf_strong = cfg.confidence_strong,
        ml_override = cfg.ml_override_threshold,
    )

    msg = format_alert_message(
        symbol       = symbol,
        expected_rr  = expected_rr,
        confidence   = confidence,
        decision     = decision,
        reason       = reason,
        ml_score     = ml_score,
        regime       = regime,
        session      = session,
        time_decay   = time_decay,
        timeframe    = timeframe,
    )

    sent, err = send_telegram_alert(msg, cfg.bot_token, cfg.chat_id)

    entry = {
        "timestamp":   time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "symbol":      symbol,
        "decision":    decision,
        "reason":      reason,
        "expected_rr": round(expected_rr, 4),
        "confidence":  round(confidence, 4),
        "ml_score":    round(ml_score, 4) if ml_score is not None else None,
        "sent":        sent,
        "suppressed_reason": None if sent else f"telegram_error: {err}",
    }
    _log_alert(entry)
    return entry


# ─────────────────────────────────────────────────────────────────────────────
# QUICK SELF-TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)-8s %(message)s")

    print("\n=== LiveEngine self-test ===\n")

    # Test decision logic
    cases = [
        (1.8, 0.63, None,  "EXECUTE"),
        (1.8, 0.57, None,  "WARN"),
        (0.8, 0.72, None,  "BLOCK"),   # low RR, no ML
        (0.8, 0.72, 0.80,  "WATCH"),   # low RR but ML strong
        (1.5, 0.45, None,  "BLOCK"),   # low confidence
    ]
    all_pass = True
    for rr, conf, ml, expected in cases:
        dec, reason = decide_trade(rr, conf, ml)
        ok = dec == expected
        status = "✅" if ok else "❌"
        print(f"  {status} RR={rr:.1f} conf={conf:.2f} ml={ml} → {dec} ({reason}) [expected {expected}]")
        if not ok:
            all_pass = False

    print(f"\n  Decision logic: {'ALL PASS' if all_pass else 'FAILURES DETECTED'}")

    # Test message formatter
    msg = format_alert_message(
        symbol="BTCUSDT", expected_rr=1.72, confidence=0.67,
        decision="EXECUTE", reason="strong_setup",
        ml_score=0.71, probabilities=[0.18, 0.21, 0.35, 0.26],
        regime="EXPANSION", session="LONDON", time_decay=0.88,
    )
    print("\n  Sample alert message:")
    print("  " + "\n  ".join(msg.split("\n")))

    # Test schema validation guard in dry_run path
    print("\n  Schema validation test:")
    try:
        from features.dataset_builder import validate_feature_vector
        validate_feature_vector([0.0] * 9, "self_test")
        print("  ❌ ERROR: should have raised ValueError")
    except ValueError as e:
        print(f"  ✅ Schema guard correct: {str(e)[:70]}...")

    print("\n=== Self-test complete ===\n")
