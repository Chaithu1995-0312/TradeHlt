"""chart_series.py — INFRA-CPC-V1 A0 series builder (pure; no drawing).

The `series` file is the AUTHORITY for a chart export; the PNG is a view of it
(INFRA-CPC-V1 §8: "No mixing Surface 'pretty PNG' as sole audit trail").

Timeframe ladder is DELEGATED, never reimplemented:
  * M15/H1/H4/D1 -> `research.resample.resample`   (causal: drops the trailing partial
    bucket unconditionally, never fabricates candles across weekend/holiday gaps)
  * W1/MN1       -> `features.calendar_periods.aggregate_calendar`

§3.1 invariant: the row for bar `t` uses only data <= `t`. Both aggregators satisfy this
by construction; the CRT overlay is resolved on the M15 base and downsampled to a bucket
by taking the state as of the bucket's LAST child (i.e. at bucket close), which is the
only causal choice.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from config_layer.crt_engine_v2 import Candle
from features.calendar_periods import aggregate_calendar, period_key
from research.resample import bucket_floor, resample

# Timeframes served by the two delegated aggregators.
_RESAMPLE_RULES = ("M15", "H1", "H4", "D1")
_CALENDAR_RULES = ("W1", "MN1")
TIMEFRAMES = _RESAMPLE_RULES + _CALENDAR_RULES

# INFRA-CPC-V1 §3.2 Layer V1 — colour TOKEN NAMES are frozen by the design; the hex
# values are this implementation's choice and may be restyled without amending the freeze.
CRT_COLOR_TOKENS: dict[str, str] = {
    "RANGE":          "crt.range",
    "SHADOW_PENDING": "crt.shadow",
    "SWEEP":          "crt.sweep",
    "DISPLACEMENT":   "crt.disp",
    "EXPANSION":      "crt.exp",
    "RETEST":         "crt.retest",
    "EXECUTION":      "crt.exec",
    "RESOLUTION":     "crt.res",
    "EXPIRED":        "crt.expired",
}

CRT_TOKEN_HEX: dict[str, str] = {
    "crt.range":   "#6b7280",   # neutral grey  - nothing committed
    "crt.shadow":  "#a78bfa",   # violet        - shadow branch
    "crt.sweep":   "#38bdf8",   # cyan          - liquidity taken
    "crt.disp":    "#f59e0b",   # amber         - directional impulse (F-074)
    "crt.exp":     "#f97316",   # orange        - expansion
    "crt.retest":  "#eab308",   # yellow        - retest window
    "crt.exec":    "#22c55e",   # green         - committed entry
    "crt.res":     "#3b82f6",   # blue          - resolved
    "crt.expired": "#ef4444",   # red           - TTL expiry
}

# Sentinel used when the overlay could not be resolved. NEVER a real CRTState —
# INFRA-CPC-V1 §3.2: "missing tag = UNKNOWN / empty, never invent".
CRT_UNAVAILABLE = "UNAVAILABLE"

SERIES_HEADER = ("time", "open", "high", "low", "close", "volume", "crt_state")


@dataclass(frozen=True)
class ChartSeries:
    """One renderable, exportable series. `bars[i]` pairs with `crt_state[i]`."""
    instrument: str
    timeframe: str
    bars: list[Candle]
    crt_state: list[str]
    crt_state_source: str          # "RESOLVED:<version>" | "UNAVAILABLE:<reason>" | "NONE"
    config_pin: dict = field(default_factory=dict)
    # Base-series facts needed to judge whether this timeframe SAMPLES the CRT state
    # process finely enough to represent it (see `crt_aliasing`). Optional so a caller
    # holding only an HTF series can still build one.
    base_bars: Optional[int] = None
    base_transitions: Optional[int] = None

    def __post_init__(self) -> None:
        if len(self.bars) != len(self.crt_state):
            raise ValueError(
                f"ChartSeries misaligned: {len(self.bars)} bars vs "
                f"{len(self.crt_state)} states"
            )

    @property
    def start(self) -> Optional[datetime]:
        return self.bars[0].timestamp if self.bars else None

    @property
    def end(self) -> Optional[datetime]:
        return self.bars[-1].timestamp if self.bars else None

    def state_changes(self) -> list[int]:
        """Indices where crt_state differs from the previous bar (transition ticks)."""
        return [i for i in range(1, len(self.crt_state))
                if self.crt_state[i] != self.crt_state[i - 1]]


# -- base corpus load ---------------------------------------------------------
def load_base_candles(csv_path: str | Path, instrument: str) -> list[Candle]:
    """Stream the M15 base corpus through the governed loader.

    Goes through `CandleLoader`, NOT a bare csv read, so the XAUUSD fail-closed identity
    guard (`guard_xauusd_csv_path`: path + sha256 + rows + range) stays on the load path.
    """
    from runtime.backtest_v2 import CandleLoader
    return list(CandleLoader(str(csv_path), instrument).stream())


def to_timeframe(base: Sequence[Candle], timeframe: str) -> list[Candle]:
    """Aggregate M15 `base` to `timeframe`. M15 is a pass-through copy."""
    if timeframe not in TIMEFRAMES:
        raise ValueError(
            f"unsupported timeframe {timeframe!r} (expected {list(TIMEFRAMES)})")
    if timeframe == "M15":
        return list(base)
    if timeframe in _RESAMPLE_RULES:
        return resample(list(base), timeframe)
    return aggregate_calendar(list(base), timeframe)


def downsample_states(
    base: Sequence[Candle],
    base_states: Sequence[str],
    htf: Sequence[Candle],
    timeframe: str,
) -> list[str]:
    """Project per-M15 CRT states onto `htf` bars: state as of each bucket's LAST child.

    Causal by construction — a bucket's colour is the state once the bucket has closed,
    never a state from a later bucket. Buckets with no resolved child fall back to
    CRT_UNAVAILABLE rather than borrowing a neighbour's state.
    """
    if timeframe == "M15":
        return list(base_states)

    if timeframe in _RESAMPLE_RULES:
        def key(ts: datetime):
            return bucket_floor(ts, timeframe)
    else:
        def key(ts: datetime):
            return period_key(ts, timeframe)

    last_by_bucket: dict = {}
    for c, s in zip(base, base_states):
        last_by_bucket[key(c.timestamp)] = s

    return [last_by_bucket.get(key(h.timestamp), CRT_UNAVAILABLE) for h in htf]


def slice_window(
    bars: Sequence[Candle],
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> tuple[list[Candle], list[int]]:
    """Inclusive [start, end] window. Returns (bars, original indices)."""
    idx = [i for i, c in enumerate(bars)
           if (start is None or c.timestamp >= start)
           and (end is None or c.timestamp <= end)]
    return [bars[i] for i in idx], idx


# -- export pack (INFRA-CPC-V1 §3.3) ------------------------------------------
def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def build_config_pin(instrument: str, csv_path: str | Path) -> dict:
    """ACTIVE_VERSION + config hash + corpus identity.

    Best-effort per field, but every field records WHY it is absent rather than silently
    omitting itself — an unresolved pin must be visible, not invisible (the silent-gap
    class of F-079/F-083/F-085).
    """
    pin: dict = {
        "active_version": None,
        "config_hash": None,
        "corpus_path": str(csv_path).replace("\\", "/"),
        "corpus_sha256": None,
        "instrument": instrument,
        "session_timestamp_basis": None,
    }
    try:
        from config_layer.production_config import get_active_version
        pin["active_version"] = get_active_version()
    except Exception as exc:                                    # noqa: BLE001
        pin["active_version"] = f"UNRESOLVED: {exc}"
    try:
        from config_layer.production_config import get_prod_metadata
        pin["config_hash"] = get_prod_metadata().get("config_hash")
    except Exception as exc:                                    # noqa: BLE001
        pin["config_hash"] = f"UNRESOLVED: {exc}"
    try:
        pin["corpus_sha256"] = sha256_file(csv_path)
    except Exception as exc:                                    # noqa: BLE001
        pin["corpus_sha256"] = f"UNRESOLVED: {exc}"
    # F-066: broker-server stamps. The legend MUST name the basis; 53.36% of XAUUSD
    # session labels are wrong under the uncorrected basis, so an unlabelled chart is
    # actively misleading about time.
    try:
        from config_layer.production_config import get_prod_section
        fp = get_prod_section("feature_pipeline") or {}
        pin["session_timestamp_basis"] = fp.get("session_timestamp_basis", "broker_local")
    except Exception:                                           # noqa: BLE001
        pin["session_timestamp_basis"] = "broker_local (default; config section unread)"
    return pin


def crt_aliasing(series: ChartSeries) -> dict:
    """Is the CRT colour layer legible at this timeframe, or is it UNDERSAMPLED?

    This is a SAMPLING question, not a busyness question. CRT is an M15 state machine; a
    chart bar that spans more base bars than the state's mean dwell cannot represent it —
    the flips happen *inside* the bar and its close-state is close to a random draw.

    Criterion: `bars_per_bucket > mean_dwell`, where
    `mean_dwell = base_bars / base_transitions`.

    Measured on XAUUSD under `v2_htfcrt_2026_08` (2,382 transitions / 47,275 M15 bars,
    dwell ~19.8 bars ~= 5 h): D1 spans ~92 base bars -> ALIASED (~5 flips lost per bar,
    and the render is a barcode); H4 spans ~15 -> legible; H1/M15 comfortably legible.

    CORRECTED 2026-08-22: the first implementation flagged on state-CHANGE RATE > 0.5.
    That measured the wrong thing and would have passed D1 — the real D1 rate is 0.327
    (168 changes / 514) because one state (SWEEP, 69% of buckets) dominates, so most
    adjacent buckets agree even though ~5 transitions were swallowed inside each one. A
    low change rate is exactly what heavy undersampling of a dominant-state process looks
    like. Change rate is still reported, as description, but no longer decides.

    Never suppresses the layer — the operator may still want it. It records the fact next
    to it, so nobody reads aliased colour as structure.
    """
    n = len(series.bars)
    if n < 2 or series.crt_state_source == "NONE":
        return {"change_rate": None, "aliased": False, "mean_dwell_base_bars": None,
                "bars_per_bucket": None, "note": "no CRT layer on this export"}

    rate = len(series.state_changes()) / (n - 1)
    out: dict = {"change_rate": round(rate, 4), "mean_dwell_base_bars": None,
                 "bars_per_bucket": None}

    if not series.base_bars or not series.base_transitions:
        out["aliased"] = False
        out["note"] = (
            f"CRT state changes on {rate:.0%} of {series.timeframe} bars. Aliasing "
            "UNDETERMINED: base-series dwell was not supplied, so undersampling could "
            "not be checked. Treat HTF colour with caution."
        )
        return out

    dwell = series.base_bars / series.base_transitions
    per_bucket = series.base_bars / n
    aliased = per_bucket > dwell
    out["mean_dwell_base_bars"] = round(dwell, 2)
    out["bars_per_bucket"] = round(per_bucket, 2)
    out["aliased"] = aliased
    out["note"] = (
        f"ALIASED: one {series.timeframe} bar spans ~{per_bucket:.0f} base bars but CRT "
        f"state persists only ~{dwell:.0f} bars, so ~{per_bucket / dwell:.0f} transitions "
        "occur INSIDE each bar and its colour is a near-random sample of a faster "
        "process. Do NOT read this colour as structure - use a finer timeframe."
    ) if aliased else (
        f"Legible: one {series.timeframe} bar spans ~{per_bucket:.0f} base bars, within "
        f"the ~{dwell:.0f}-bar mean CRT state dwell, so states survive sampling "
        f"(colour changes on {rate:.0%} of bars)."
    )
    return out


def build_legend(series: ChartSeries) -> dict:
    """A-AC3: colour tokens by name + clock basis + the state source."""
    present = sorted(set(series.crt_state))
    return {
        "crt_aliasing": crt_aliasing(series),
        "design_id": "INFRA-CPC-V1",
        "workstream": "A0",
        "layers": {
            "V0_bars": True,
            "V1_crt_state_color": series.crt_state_source != "NONE",
            "V2_story_tags": False,          # A1 - not implemented
            "V3_fm_panel": False,            # A2 - not implemented
        },
        "instrument": series.instrument,
        "timeframe": series.timeframe,
        "bars": len(series.bars),
        "crt_state_source": series.crt_state_source,
        "crt_color_tokens": {st: tok for st, tok in CRT_COLOR_TOKENS.items()
                             if st in present},
        "crt_token_hex": {tok: CRT_TOKEN_HEX[tok] for st, tok in CRT_COLOR_TOKENS.items()
                          if st in present},
        "states_present": present,
        "session_timestamp_basis": series.config_pin.get("session_timestamp_basis"),
        "clock_note": (
            "Timestamps are broker-server time as stored (F-066). Session labels are NOT "
            "UTC-corrected on this chart; price geometry is the primary comparison surface."
        ),
        # A-AC3b: these names collide across modules; the legend states the distinction
        # even though A0 draws no EMA, so a later A2 pass cannot quietly conflate them.
        "ema_label_guard": (
            "FM-043/FM-044 (pipeline ema_fast/ema_slow, spans 9/21) are DISTINCT from "
            "crt_live_ema_fast/slow (CRTConfig ema_fast/ema_slow, spans ~2/5). A0 draws "
            "neither."
        ),
    }


def write_export(series: ChartSeries, out_dir: str | Path,
                 chart_files: Sequence[str] = ()) -> Path:
    """Write the §3.3 pack: series.csv + legend.json + config_pin.json + INDEX.md."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # series.csv - the authority surface. repr() floats round-trip exactly.
    lines = [",".join(SERIES_HEADER)]
    for c, st in zip(series.bars, series.crt_state):
        lines.append(",".join([
            c.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            repr(float(c.open)), repr(float(c.high)),
            repr(float(c.low)), repr(float(c.close)),
            repr(float(c.volume)), st,
        ]))
    (out / "series.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    (out / "legend.json").write_text(
        json.dumps(build_legend(series), indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    (out / "config_pin.json").write_text(
        json.dumps(series.config_pin, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")

    idx = [
        f"# Chart export - {series.instrument} {series.timeframe}",
        "",
        "Design: `INFRA-CPC-V1` Workstream **A0** (bars + CRTState colour).",
        "",
        f"- Bars: **{len(series.bars)}**",
        f"- Range: `{series.start}` -> `{series.end}`",
        f"- CRT state source: `{series.crt_state_source}`",
        f"- ACTIVE_VERSION: `{series.config_pin.get('active_version')}`",
        f"- Corpus sha256: `{series.config_pin.get('corpus_sha256')}`",
        f"- Clock basis: `{series.config_pin.get('session_timestamp_basis')}` (F-066)",
        "",
        "## Files",
        "- `series.csv` - **authority**; the PNG is a view of this.",
        "- `legend.json` - colour tokens, clock basis, state source.",
        "- `config_pin.json` - ACTIVE_VERSION, config hash, corpus identity.",
    ]
    idx += [f"- `{f}`" for f in chart_files]
    idx += [
        "",
        "## Authority",
        "Descriptive only. This export grants **no** economic claim, **no** G001 claim,",
        "and **no** promotion authority (INFRA-CPC-V1 §8, CLAUDE.md §6.5).",
    ]
    (out / "INDEX.md").write_text("\n".join(idx) + "\n", encoding="utf-8")
    return out
