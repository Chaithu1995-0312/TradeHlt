"""render.py — INFRA-CPC-V1 A0 drawing layer (Layer V0 bars + Layer V1 CRTState colour).

Two backends, same contract:
  * `mplfinance` when importable (declared as the OPTIONAL `charts` extra, never a
    runtime dependency — base `[project]` declares none and must stay that way);
  * a stdlib inline-SVG fallback modelled on
    `scripts/analysis/blind_label_sample.py::_render_candles_svg`, so an absent plotting
    library degrades the OUTPUT FORMAT and never the availability of the chart.

Layer V1 is drawn as a translucent background span per contiguous CRTState run, plus a
thin vertical tick at every state change (INFRA-CPC-V1 §3.2: "Transition markers: thin
vertical tick on bar where state changes"). Legend is mandatory on every export (§3.2).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Sequence

from charts.chart_series import (
    CRT_COLOR_TOKENS,
    CRT_TOKEN_HEX,
    CRT_UNAVAILABLE,
    ChartSeries,
)

log = logging.getLogger("charts.render")

UNAVAILABLE_HEX = "#1f2937"     # near-background: visibly "no claim", not a state colour
UP_HEX = "#e5e7eb"
DOWN_HEX = "#111827"
EDGE_HEX = "#9ca3af"


def mplfinance_available() -> bool:
    try:
        import mplfinance  # noqa: F401
        return True
    except Exception:                                            # noqa: BLE001
        return False


def _state_runs(states: Sequence[str]) -> list[tuple[int, int, str]]:
    """Contiguous [start, end] index runs of identical state."""
    if not states:
        return []
    runs: list[tuple[int, int, str]] = []
    s0 = 0
    for i in range(1, len(states) + 1):
        if i == len(states) or states[i] != states[s0]:
            runs.append((s0, i - 1, states[s0]))
            s0 = i
    return runs


def _hex_for(state: str) -> str:
    if state == CRT_UNAVAILABLE:
        return UNAVAILABLE_HEX
    tok = CRT_COLOR_TOKENS.get(state)
    return CRT_TOKEN_HEX.get(tok, UNAVAILABLE_HEX) if tok else UNAVAILABLE_HEX


def _title(series: ChartSeries, i0: int, i1: int) -> str:
    from charts.chart_series import crt_aliasing

    pin = series.config_pin
    head = (
        f"{series.instrument} {series.timeframe}   "
        f"{series.bars[i0].timestamp:%Y-%m-%d} -> {series.bars[i1].timestamp:%Y-%m-%d}   "
        f"[bars {i0}-{i1} of {len(series.bars)}]\n"
        f"ACTIVE_VERSION={pin.get('active_version')}   "
        f"crt={series.crt_state_source}   "
        f"clock={pin.get('session_timestamp_basis')} (broker-server, F-066)"
    )
    # An aliased colour layer must say so ON THE IMAGE — the PNG travels without its
    # legend.json, and a barcode is exactly the kind of artifact that gets screenshotted
    # and read as structure.
    al = crt_aliasing(series)
    if al.get("aliased"):
        head += (
            f"\nWARNING: CRT colour is ALIASED at {series.timeframe} "
            f"(state changes on {al['change_rate']:.0%} of bars) - not structure. Use M15/H1."
        )
    return head


# -- mplfinance backend -------------------------------------------------------
def _render_png(series: ChartSeries, i0: int, i1: int, out_path: Path,
                show_volume: bool = True) -> Path:
    import matplotlib
    matplotlib.use("Agg")                      # headless; no display required
    import matplotlib.patches as mpatches
    import matplotlib.pyplot as plt
    import mplfinance as mpf
    import pandas as pd

    bars = series.bars[i0:i1 + 1]
    states = series.crt_state[i0:i1 + 1]

    df = pd.DataFrame(
        {
            "Open":   [b.open for b in bars],
            "High":   [b.high for b in bars],
            "Low":    [b.low for b in bars],
            "Close":  [b.close for b in bars],
            "Volume": [b.volume for b in bars],
        },
        index=pd.DatetimeIndex([b.timestamp for b in bars]),
    )

    # bool() is load-bearing: pandas returns numpy.bool_, which mplfinance's
    # `isinstance(value, bool)` validator rejects.
    has_vol = bool(show_volume and df["Volume"].abs().sum() > 0)
    mc = mpf.make_marketcolors(up=UP_HEX, down=DOWN_HEX, edge=EDGE_HEX,
                               wick=EDGE_HEX, volume=EDGE_HEX)
    style = mpf.make_mpf_style(base_mpf_style="nightclouds", marketcolors=mc,
                               gridcolor="#374151", facecolor="#0b0f19",
                               figcolor="#0b0f19")

    width = max(12.0, min(40.0, len(bars) / 26.0))
    # NOTE: no tight_layout — it fights the 2-line left-aligned title and clips its
    # first row (the ACTIVE_VERSION / clock provenance line). Margins are set explicitly
    # below instead, so the pin is always legible on the image itself.
    fig, axes = mpf.plot(
        df, type="candle", style=style, volume=has_vol, returnfig=True,
        figsize=(width, 9.5), xrotation=20,
        warn_too_much_data=len(bars) + 10,
    )
    ax = axes[0]

    # Layer V1 — background span per contiguous state run + transition ticks.
    if series.crt_state_source != "NONE":
        for a, b, st in _state_runs(states):
            if st == CRT_UNAVAILABLE:
                continue
            ax.axvspan(a - 0.5, b + 0.5, color=_hex_for(st), alpha=0.16, zorder=0, lw=0)
        for i in range(1, len(states)):
            if states[i] != states[i - 1] and states[i] != CRT_UNAVAILABLE:
                ax.axvline(i - 0.5, color=_hex_for(states[i]), alpha=0.75,
                           lw=0.8, zorder=1)

        present = [s for s in CRT_COLOR_TOKENS if s in set(states)]
        if present:
            ax.legend(
                handles=[mpatches.Patch(color=_hex_for(s), alpha=0.55,
                                        label=f"{s}  ({CRT_COLOR_TOKENS[s]})")
                         for s in present],
                loc="upper left", fontsize=8, framealpha=0.85, ncol=2,
            )

    ax.set_title(_title(series, i0, i1), fontsize=9, loc="left", color="#e5e7eb", pad=10)
    fig.subplots_adjust(top=0.90, left=0.055, right=0.985, bottom=0.09)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=110, facecolor="#0b0f19")
    plt.close(fig)
    return out_path


# -- stdlib SVG fallback ------------------------------------------------------
def _render_svg(series: ChartSeries, i0: int, i1: int, out_path: Path,
                width: int = 1800, height: int = 760) -> Path:
    """Inline SVG, stdlib only — the degradation path when mplfinance is absent."""
    bars = series.bars[i0:i1 + 1]
    states = series.crt_state[i0:i1 + 1]
    if not bars:
        raise ValueError("no bars to render")

    pad_l, pad_r, pad_t, pad_b = 70, 20, 54, 40
    pw, ph = width - pad_l - pad_r, height - pad_t - pad_b
    hi = max(b.high for b in bars)
    lo = min(b.low for b in bars)
    rng = (hi - lo) or 1.0
    n = len(bars)
    step = pw / n
    bw = max(1.0, step * 0.62)

    def x(i: int) -> float:
        return pad_l + (i + 0.5) * step

    def y(p: float) -> float:
        return pad_t + (hi - p) / rng * ph

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#0b0f19"/>',
    ]

    if series.crt_state_source != "NONE":
        for a, b, st in _state_runs(states):
            if st == CRT_UNAVAILABLE:
                continue
            x0 = pad_l + a * step
            out.append(
                f'<rect x="{x0:.2f}" y="{pad_t}" width="{(b - a + 1) * step:.2f}" '
                f'height="{ph}" fill="{_hex_for(st)}" opacity="0.16"/>'
            )

    for i, b in enumerate(bars):
        col = UP_HEX if b.close > b.open else DOWN_HEX
        cx = x(i)
        out.append(
            f'<line x1="{cx:.2f}" y1="{y(b.high):.2f}" x2="{cx:.2f}" '
            f'y2="{y(b.low):.2f}" stroke="{EDGE_HEX}" stroke-width="1"/>'
        )
        top, bot = y(max(b.open, b.close)), y(min(b.open, b.close))
        out.append(
            f'<rect x="{cx - bw / 2:.2f}" y="{top:.2f}" width="{bw:.2f}" '
            f'height="{max(1.0, bot - top):.2f}" fill="{col}" '
            f'stroke="{EDGE_HEX}" stroke-width="0.6"/>'
        )

    for lab, p in (("hi", hi), ("mid", (hi + lo) / 2), ("lo", lo)):
        out.append(
            f'<text x="6" y="{y(p) + 4:.2f}" fill="#9ca3af" '
            f'font-family="monospace" font-size="11">{p:.2f}</text>'
        )

    for j, line in enumerate(_title(series, i0, i1).split("\n")):
        out.append(
            f'<text x="{pad_l}" y="{18 + j * 15}" fill="#e5e7eb" '
            f'font-family="monospace" font-size="12">{line}</text>'
        )

    lx = pad_l
    for st in [s for s in CRT_COLOR_TOKENS if s in set(states)]:
        out.append(f'<rect x="{lx}" y="{height - 24}" width="11" height="11" '
                   f'fill="{_hex_for(st)}" opacity="0.75"/>')
        out.append(f'<text x="{lx + 15}" y="{height - 14}" fill="#9ca3af" '
                   f'font-family="monospace" font-size="10">{st}</text>')
        lx += 20 + 8 * len(st)

    out.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out), encoding="utf-8")
    return out_path


# -- public -------------------------------------------------------------------
def render_tiles(
    series: ChartSeries,
    out_dir: str | Path,
    bars_per_tile: Optional[int] = None,
    fmt: str = "png",
    show_volume: bool = True,
) -> list[str]:
    """Render `series` as one or more tiles. Returns the filenames written."""
    out = Path(out_dir)
    n = len(series.bars)
    if n == 0:
        return []
    per = bars_per_tile or n
    use_png = (fmt == "png") and mplfinance_available()
    if fmt == "png" and not use_png:
        log.warning("mplfinance unavailable - falling back to stdlib SVG")

    names: list[str] = []
    tiles = (n + per - 1) // per
    for t in range(tiles):
        i0 = t * per
        i1 = min(n - 1, i0 + per - 1)
        ext = "png" if use_png else "svg"
        name = f"chart_{series.timeframe}_{t + 1:02d}.{ext}"
        target = out / name
        if use_png:
            _render_png(series, i0, i1, target, show_volume=show_volume)
        else:
            _render_svg(series, i0, i1, target)
        names.append(name)
        log.info("rendered %s (bars %d-%d)", name, i0, i1)
    return names
