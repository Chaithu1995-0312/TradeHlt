"""Render the bulk-candle confirmation page — a CURATION TOOL, not a measurement instrument.

The SEM-034 proxy produces a shortlist; this page lets the human bridge look at each
candidate on a chart and say whether it is actually a parent bulk candle. That confirmation
is the only thing that turns a candidate into a parent, and it is also the hand-labelled set
UNK-007's `resolution_metric` asks for in order to ever validate the proxy.

DELIBERATELY NOT BLINDED. `scripts/analysis/blind_label_sample.py` is the visual precedent
for this page (its SVG candle renderer and frozen-question pattern), but it is a measurement
instrument and hides timestamps to protect an inference. This page is the opposite: the
bridge needs the timestamps, because the output IS a parents file. Saying so on the page
prevents anyone later mistaking a curated list for a blind label set.

That module is also NOT imported: it transitively pulls in `features.feature_pipeline`,
which is on this package's forbidden-import list. The renderer below is stdlib-only.
"""
from __future__ import annotations

import html
import json
from typing import Sequence

from research.sujan_manipulation.bulk_proxy import (
    PROXY_ID,
    PROXY_STATUS,
    RankedCandidate,
)
from research.sujan_manipulation.parent import BULK_CANDLE_EVIDENCE, Bar

#: The one question, frozen. Its wording is the concept's recorded description verbatim.
FROZEN_QUESTION = (
    "Is the marked candle a parent bulk candle - visually dominant, defining a range?"
)
ANSWERS = ("yes", "no", "unsure")

#: Bars of context drawn either side of the marked candle.
CONTEXT_BARS = 40

_CHART_W = 760
_CHART_H = 260
_MARGIN = 12


def _render_candles_svg(window: Sequence[Bar], marked_index: int) -> str:
    """Minimal OHLC candlestick SVG. Pure stdlib, no pandas, no external renderer."""
    highs = [b.high for b in window]
    lows = [b.low for b in window]
    p_min, p_max = min(lows), max(highs)
    span = (p_max - p_min) or 1.0
    n = len(window)
    slot_w = (_CHART_W - 2 * _MARGIN) / n
    body_w = max(1.5, slot_w * 0.6)

    def y(price: float) -> float:
        return _MARGIN + (p_max - price) / span * (_CHART_H - 2 * _MARGIN)

    parts: list[str] = []
    for i, bar in enumerate(window):
        cx = _MARGIN + slot_w * (i + 0.5)
        is_marked = bar.index == marked_index
        up = bar.close >= bar.open
        colour = "#c9522c" if is_marked else ("#3d7f5a" if up else "#8a4a4a")
        width = 2.0 if is_marked else 1.0
        parts.append(
            f'<line x1="{cx:.1f}" y1="{y(bar.high):.1f}" x2="{cx:.1f}" '
            f'y2="{y(bar.low):.1f}" stroke="{colour}" stroke-width="{width}"/>'
        )
        top, bottom = max(bar.open, bar.close), min(bar.open, bar.close)
        h = max(1.0, y(bottom) - y(top))
        parts.append(
            f'<rect x="{cx - body_w / 2:.1f}" y="{y(top):.1f}" width="{body_w:.1f}" '
            f'height="{h:.1f}" fill="{colour}" stroke="{colour}"/>'
        )
        if is_marked:
            parts.append(
                f'<rect x="{cx - slot_w / 2:.1f}" y="{_MARGIN:.1f}" width="{slot_w:.1f}" '
                f'height="{_CHART_H - 2 * _MARGIN:.1f}" fill="#c9522c" opacity="0.10"/>'
            )
    return (
        f'<svg viewBox="0 0 {_CHART_W} {_CHART_H}" width="100%" '
        f'xmlns="http://www.w3.org/2000/svg">{"".join(parts)}</svg>'
    )


def _window(bars: Sequence[Bar], centre: int) -> list[Bar]:
    lo = max(0, centre - CONTEXT_BARS)
    hi = min(len(bars), centre + CONTEXT_BARS + 1)
    return list(bars[lo:hi])


def render(
    bars: Sequence[Bar],
    ranked: dict[str, Sequence[RankedCandidate]],
    *,
    corpus_path: str,
    overlap: Sequence[int],
) -> str:
    """Build the standalone confirmation page.

    `ranked` maps ranking name -> shortlist. Lists are rendered SEPARATELY and never merged.
    """
    by_index = {bar.index: bar for bar in bars}
    evidence = "".join(f"<li>{html.escape(e)}</li>" for e in BULK_CANDLE_EVIDENCE)
    overlap_set = set(overlap)

    sections: list[str] = []
    for ranking, candidates in ranked.items():
        cards: list[str] = []
        for c in candidates:
            bar = by_index[c.parent.index]
            both = " &middot; <b>also in the other list</b>" if c.parent.index in overlap_set else ""
            ts = c.parent.timestamp.isoformat(sep=" ")
            cards.append(
                f'<div class="card" data-ts="{html.escape(ts)}" data-ranking="{html.escape(ranking)}">'
                f'<div class="hdr">#{c.rank} &middot; {html.escape(ts)} &middot; '
                f"{html.escape(ranking)}={c.magnitude:.2f}{both}</div>"
                f"{_render_candles_svg(_window(bars, c.parent.index), c.parent.index)}"
                f'<div class="q">{html.escape(FROZEN_QUESTION)}</div>'
                + "".join(
                    f'<label><input type="radio" name="{html.escape(ranking)}-{c.parent.index}" '
                    f'value="{a}" onchange="mark(this)"> {a}</label>'
                    for a in ANSWERS
                )
                + "</div>"
            )
        sections.append(
            f'<h2>{html.escape(ranking)} &mdash; {len(candidates)} candidates</h2>'
            f'<div class="grid">{"".join(cards)}</div>'
        )

    return f"""<!doctype html>
<meta charset="utf-8">
<title>SEM-034 bulk-candle candidates</title>
<style>
 body{{font:14px/1.5 system-ui,sans-serif;margin:24px;max-width:900px;color:#222}}
 .warn{{background:#fdf3e7;border-left:4px solid #c9522c;padding:12px 16px;margin:16px 0}}
 .card{{border:1px solid #ddd;border-radius:6px;padding:12px;margin:16px 0}}
 .hdr{{font-family:ui-monospace,monospace;font-size:12px;margin-bottom:6px;color:#555}}
 .q{{margin:8px 0 4px;font-weight:600}}
 label{{margin-right:14px}}
 textarea{{width:100%;height:180px;font-family:ui-monospace,monospace;font-size:12px}}
 h2{{margin-top:36px;border-bottom:1px solid #ddd;padding-bottom:4px}}
</style>
<h1>SEM-034 bulk-candle candidates</h1>
<div class="warn">
 <b>Curation tool, not a measurement instrument.</b> This page is deliberately NOT blinded:
 timestamps are visible because its output is a parents file you author. Nothing here is a
 result, and the candidate count says nothing about the market.<br><br>
 <b>{html.escape(PROXY_ID)} status: {html.escape(PROXY_STATUS)}.</b> These candles were shortlisted
 by a mechanical proxy for a visual concept. The proxy has never been agreement-checked
 against your own reading &mdash; your answers here are what would make that possible.
 <code>UNK-007</code> stays open.<br><br>
 Corpus: <code>{html.escape(corpus_path)}</code>. The two lists below are ranked by
 <b>different quantities and are never merged</b>; {len(overlap_set)} candles appear in both.
 <br><br>Recorded evidence for what a bulk candle is &mdash; your only guidance:
 <ul>{evidence}</ul>
</div>
{"".join(sections)}
<h2>Confirmed parents</h2>
<p>Answer above, then copy this into <code>confirmed_parents.json</code> and run the detector.</p>
<textarea id="out" readonly>{{"timestamps": []}}</textarea>
<script>
const picked = new Map();
function mark(el) {{
  const card = el.closest('.card');
  picked.set(card.dataset.ts + '|' + card.dataset.ranking, el.value);
  const yes = [...new Set([...picked.entries()].filter(e => e[1] === 'yes')
                  .map(e => e[0].split('|')[0]))].sort();
  document.getElementById('out').value = JSON.stringify({{timestamps: yes}}, null, 2);
}}
</script>
"""


def confirmed_parents_template() -> str:
    """The empty parents file shape, for reference."""
    return json.dumps({"timestamps": []}, indent=2) + "\n"
