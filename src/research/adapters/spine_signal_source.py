"""spine_signal_source.py — run the production CRT spine, harvest its entries.

SCOPE — CRT-only by design (F-037), when the gate is OFF. The backtest's 4-engine fusion veto
(`EngineRunner` → CRT/Gaussian/ZoneGate/RR → Fusion → RegimeGovernor → Decision) is controlled by
`backtest.engine_gate_enabled` in the production config (STRICT key, F-058, shipped 2026-07-23) —
**the active config sets this `true`**, so the fusion gate runs by default; `BACKTEST_ENGINE_GATE`
is now an explicit env-var OVERRIDE only, and only if set (it WARNs when it disagrees with config,
`backtest_v2.py:2054-2063`). Pre-2026-07-23 this adapter's corpus was produced with an untracked
`.env` forcing the gate OFF, so it harvested only the **CRT state machine**'s entries at the
`EXECUTE`/`TRADE_OPENED` bar — that CRT-only object is what F-019/F-036/qualify_majors call "the
spine," and it remains valid for its pre-2026-07-23 epoch (§6.2 rule 4). Since the config epoch
change, running this adapter WITHOUT an explicit `BACKTEST_ENGINE_GATE=0` override produces the
gate-ON, full-fusion object instead (~14% fewer trades historically: BNB 13→11, SOL 7→6; see
F-036/F-037/F-058). A gate-ON re-measurement to reconcile the current-epoch corpus against those
historical figures is queued as M-GATE-01 (`docs/governance/research_family_registry.json`
`RF-CRT-STRUCTURE.L5`). Callers that need the pre-2026-07-23 CRT-only object must set
`BACKTEST_ENGINE_GATE=0` explicitly and accept the resulting WARNING.

The production backtest, at its core, is a signal generator: at the `EXECUTE`/`TRADE_OPENED`
bar it commits an entry with a planned SL/TP. This adapter runs that spine once per instrument,
deterministically
(invariant #1: replay is deterministic), and exposes each committed entry as a `SpineEntry`
keyed by the candle's *research index* (0-based `CandleLoader` stream position).

WHY run the real BacktestRunner instead of re-implementing the loop:
  * faithfulness — every layer + all 35-dim features are forced through the actual spine;
  * zero drift — the entries ARE the backtest's trades, so the equivalence check is exact;
  * isolation — we import the spine as a proven primitive (like `CandleLoader`), in local
    scope, behind the `SpineSignalSource` Protocol; the spine never imports research.

INDEX CONTRACT (load-bearing — see backtest_v2.py:1627): the backtest increments
`candle_idx` BEFORE the warmup skip, so its `candle_open` is 1-based over the CandleLoader
stream, while the research runner assigns `c.index = i` (0-based). Therefore:

    research_index = candle_open (CSV `candle_idx`) - 1

We harvest entries from the backtest's `{instrument}_trades.csv` artifact (the file-backed
idiom) and re-key to research indices. The research forward-walk then owns exits — this
adapter only supplies the spine's ENTRY geometry (entry, SL, TP, direction).
"""

from __future__ import annotations

import csv
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

log = logging.getLogger("research.adapters.spine")

# Default spine research config (carries the `spine` + `universe` blocks this source reads).
# Overridable via env RESEARCH_SPINE_CONFIG so `run`/`qualify`/forensics stay consistent.
DEFAULT_SPINE_CONFIG = "configs/research/research_config_spine.json"


@dataclass(frozen=True)
class SpineEntry:
    """One committed spine entry, expressed in absolute price geometry.

    `risk_distance` / `reward_distance` are price-unit distances (|entry-sl| / |tp1-entry|).
    The hypothesis converts them to ATR multiples at detect() time using the same research
    ATR the toy hypotheses use, so SL/TP semantics are comparable across all hypotheses while
    the 1R / reward distances stay byte-exact.
    """

    entry_index: int            # research 0-based CandleLoader stream position
    entry: float                # spine entry_raw (pre-cost decision price)
    direction: str              # "long" | "short"
    risk_distance: float        # |entry - sl|  (> 0)
    reward_distance: float      # |tp1 - entry| (> 0)
    timestamp: str = ""         # entry candle ISO timestamp (opened_at) — alignment cross-check
    meta: dict = field(default_factory=dict)


@runtime_checkable
class SpineSignalSource(Protocol):
    """Supplies the spine's committed entries for an instrument, keyed by research index."""

    def entries(self, instrument: str) -> dict[int, SpineEntry]:
        ...


def _normalize_direction(raw: str) -> str | None:
    """Map a TradeRecord.direction string (incl. enum repr like 'Direction.LONG') to long/short."""
    s = str(raw).strip().lower()
    if "long" in s or "buy" in s or "bull" in s or s in ("1", "+1", "l", "b"):
        return "long"
    if "short" in s or "sell" in s or "bear" in s or s in ("-1", "s"):
        return "short"
    return None


class ProductionSpineSource:
    """Runs the real BacktestRunner per instrument and caches its entries.

    Heavy on first call per instrument (one full backtest pass), O(1) thereafter. The cache
    is keyed by instrument, so a single registry-singleton hypothesis can serve `run`,
    `qualify`, and forensics within one process without recomputation or state leakage.
    """

    def __init__(self, config_path: str | None = None, *,
                 out_root: str = "results/research/_spine_entries") -> None:
        import os
        self._config_path = config_path or os.environ.get("RESEARCH_SPINE_CONFIG", DEFAULT_SPINE_CONFIG)
        self._out_root = Path(out_root)
        # cache keyed by (instrument, prod_version) so v2 and v4 entries coexist in one process.
        self._cache: dict[tuple[str, str], dict[int, SpineEntry]] = {}
        self._spine_cfg: dict | None = None

    # -- config (lazy) --------------------------------------------------------
    def _cfg(self) -> dict:
        if self._spine_cfg is None:
            self._spine_cfg = json.loads(Path(self._config_path).read_text(encoding="utf-8"))
        return self._spine_cfg

    def _resolve_version(self) -> str:
        """The production registry version to measure (spine.prod_version, else active)."""
        from config_layer.production_config import PROD_VERSION
        return self._cfg().get("spine", {}).get("prod_version") or PROD_VERSION

    def _resolve_csv(self, instrument: str) -> str:
        uni = self._cfg().get("universe", {})
        data_dir = Path(uni.get("data_dir", "data"))
        pattern = uni.get("pattern", "*_M15.csv")
        for p in sorted(data_dir.glob(pattern)):
            if p.stem.split("_")[0] == instrument:
                return str(p)
        # Convention fallback: data/<INSTRUMENT>_M15.csv
        fallback = data_dir / f"{instrument}_M15.csv"
        if fallback.exists():
            return str(fallback)
        raise FileNotFoundError(
            f"ProductionSpineSource: no CSV for {instrument} under {data_dir}/{pattern}")

    # -- public ---------------------------------------------------------------
    def entries(self, instrument: str) -> dict[int, SpineEntry]:
        key = (instrument, self._resolve_version())
        if key not in self._cache:
            self._cache[key] = self._compute_entries(instrument, key[1])
        return self._cache[key]

    # -- the spine run (local-scope imports: the only research→spine coupling) -
    def _compute_entries(self, instrument: str, version: str) -> dict[int, SpineEntry]:
        # Imported here (not module-top) to keep import-time isolation and mirror the
        # established `from runtime.backtest_v2 import CandleLoader` primitive pattern.
        import config_layer.production_config as _pc
        import runtime.backtest_v2 as _bt

        spine_block = self._cfg().get("spine", {})
        csv_path = self._resolve_csv(instrument)
        out_dir = self._out_root / f"{instrument}__{_safe_name(version)}"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Measure the REQUESTED registry version without touching the governance pointer
        # (ACTIVE_VERSION). get_prod_section / get_full_config_dict / from_prod_config read the
        # module-global PROD_VERSION at call time, so set it (in both modules — backtest_v2
        # binds its own copy for trade-record stamping) for the run, then restore in finally.
        _pc_prev, _bt_prev = _pc.PROD_VERSION, _bt.PROD_VERSION
        _crt = logging.getLogger("CRT")
        _crt_prev = _crt.level
        _crt.setLevel(logging.ERROR)   # spine is deterministic (invariant #1); silence its noise
        try:
            _pc.PROD_VERSION = version
            _bt.PROD_VERSION = version
            crt_cfg = _pc.load_prod_config_from_registry(version, instrument)
            cfg = _bt.BacktestConfig.from_prod_config(
                instrument=instrument,
                pip_size=_bt.MultiInstrumentRunner.INSTRUMENT_PIP.get(instrument, 0.0001),
                crt_config=crt_cfg,
            )
            cfg.scorer_mode = spine_block.get("scorer_mode", "calibrated")
            loader = _bt.CandleLoader(csv_path, instrument)
            runner = _bt.BacktestRunner(cfg, csv_path=csv_path, overrides={"_spine_adapter": "1"})
            runner.run(loader.stream(), loader.count(), str(out_dir))
        finally:
            _pc.PROD_VERSION = _pc_prev
            _bt.PROD_VERSION = _bt_prev
            _crt.setLevel(_crt_prev)

        # ReportWriter nests output under a run-scoped subdir (run_<RUN_ID>_<instrument>/),
        # so locate the trades artifact recursively and take the most recent.
        trades = sorted(out_dir.rglob(f"{instrument}_trades.csv"), key=lambda p: p.stat().st_mtime)
        if not trades:
            log.warning("ProductionSpineSource: no trades CSV found under %s for %s", out_dir, instrument)
            return {}
        return self._parse_trades(trades[-1], instrument)

    def _parse_trades(self, path: Path, instrument: str) -> dict[int, SpineEntry]:
        out: dict[int, SpineEntry] = {}
        if not path.exists():
            log.warning("ProductionSpineSource: no trades written for %s (%s)", instrument, path)
            return out
        # Which planned target defines the reward distance. The spine scales out (tp1=1R first
        # target, tp2=2R full target); single-TP research can't replicate scale-out, so we pick
        # one lens. Default tp2 keeps the spine in the same 2R regime as the toy hypotheses.
        tp_col = self._cfg().get("spine", {}).get("tp_target", "tp2")
        if tp_col not in ("tp1", "tp2"):
            tp_col = "tp2"
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                direction = _normalize_direction(row.get("direction", ""))
                if direction is None:
                    continue
                try:
                    candle_idx = int(float(row["candle_idx"]))        # 1-based stream position
                    entry = float(row["entry_raw"])
                    sl = float(row["sl"])
                    tp = float(row[tp_col])
                except (KeyError, ValueError):
                    continue
                risk = abs(entry - sl)
                reward = abs(tp - entry)
                if risk <= 0.0 or reward <= 0.0:
                    continue
                research_index = candle_idx - 1                        # see INDEX CONTRACT
                out[research_index] = SpineEntry(
                    entry_index=research_index, entry=entry, direction=direction,
                    risk_distance=risk, reward_distance=reward,
                    timestamp=row.get("opened_at", ""),
                    meta={
                        "sl": sl, "tp_target": tp_col, "tp": tp,
                        "tp1": _safe_float(row.get("tp1")),
                        "tp2": _safe_float(row.get("tp2")),
                        "backtest_exit_reason": row.get("exit_reason", ""),
                        "backtest_pnl_rr_net": _safe_float(row.get("pnl_rr_net")),
                        "risk_score": _safe_float(row.get("risk_score")),
                        "session": row.get("session", ""),
                    },
                )
        log.info("ProductionSpineSource: %s -> %d spine entries", instrument, len(out))
        return out


def _safe_float(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _safe_name(s: str) -> str:
    """Filesystem-safe slug for a version string (which may contain spaces / punctuation)."""
    return re.sub(r"[^0-9A-Za-z._-]+", "_", str(s)).strip("_")
