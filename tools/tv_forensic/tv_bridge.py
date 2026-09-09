"""Deterministic control of a public TradingView chart via its own widget API.

The public Superchart exposes ``window.TradingViewApi`` with no login. Driving the
chart through it removes the whole Go-to-date dialog dance and, more importantly,
lets us read back what the chart actually did — the achieved visible range, the
bars on screen, and the exact time->x / price->y pixel mapping.

Probe-verified on chromium (2026-08-14):

    setSymbol / setResolution / setTimezone / removeAllStudies   work
    mainSeries().requestMoreData(n)                              works
    timeScale().zoomToBarsRange(fromIdx, toIdx)                  works, POSITIONAL args
    timeScale().indexToCoordinate(i)                             pane-relative x
    mainSeries().priceScale().priceToCoordinate(p, firstValue)   pane-relative y

    setVisibleRange / setVisibleTimeRange   BOTH throw "Not implemented" — do not use.
    zoomToBarsRange({from, to})              object form is a silent no-op — positional only.

Pane-relative coordinates are converted to page pixels by adding the chart canvas
bounding rect. With ``device_scale_factor=1`` those page pixels are the same pixels
as the saved PNG, which is what makes the annotator trustworthy.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from playwright.sync_api import Page

CHART_CANVAS = 'canvas[aria-label*="Chart for"]'

_SETUP = """
async ([symbol, resolution, timezone]) => {
  const api = window.TradingViewApi;
  if (!api) return {ok: false, error: 'window.TradingViewApi missing'};
  const c = api.activeChart();
  const p = (f) => new Promise(r => f(r));
  if (c.symbol() !== symbol) await p(cb => c.setSymbol(symbol, cb));
  if (String(c.resolution()) !== String(resolution)) await p(cb => c.setResolution(resolution, cb));
  c.setTimezone(timezone);
  try { c.removeAllStudies(); } catch (e) { /* nothing to remove */ }
  await new Promise(r => setTimeout(r, 2000));
  return {ok: true, symbol: c.symbol(), resolution: String(c.resolution()),
          timezone: c.getTimezone(), studies: c.getAllStudies().map(s => s.name)};
}
"""

# requestMoreData(500) alone stops paging after a few thousand bars: TradingView
# lazy-loads on viewport movement, so a pull with the viewport parked at the right
# edge stops producing anything. Scrolling the time scale to the earliest loaded bar
# between pulls is what keeps history coming. Bails out when the series reports
# end-of-data, or when scroll+pull together stop making progress.
_LOAD_HISTORY = """
async ([targetSec, maxPulls]) => {
  const c = window.TradingViewApi.activeChart();
  const w = c.chartWidget();
  const ts = w.model().timeScale();
  const s = w.model().mainSeries();
  const firstT = () => { const b = s.bars(); const v = b.valueAt(b.firstIndex());
                         return v ? v[0] : null; };
  let pulls = 0, stalled = 0, endOfData = false;
  for (; pulls < maxPulls; pulls++) {
    const before = firstT();
    if (before !== null && before <= targetSec) break;
    try { if (s.endOfData && s.endOfData()) { endOfData = true; break; } } catch (e) {}

    // Park the viewport on the oldest loaded bars so TV requests the next page.
    try { ts.scrollToBar(s.bars().firstIndex()); } catch (e) {}
    await new Promise(r => setTimeout(r, 250));
    try { s.requestMoreData(500); } catch (e) {}
    await new Promise(r => setTimeout(r, 1400));

    if (firstT() === before) { if (++stalled >= 6) break; } else { stalled = 0; }
  }
  const b = s.bars();
  return {pulls, size: b.size(), stalled, endOfData,
          first: b.valueAt(b.firstIndex())[0],
          last: b.valueAt(b.lastIndex())[0],
          reached: b.valueAt(b.firstIndex())[0] <= targetSec};
}
"""

_FRAME = """
async ([fromSec, toSec]) => {
  const c = window.TradingViewApi.activeChart();
  const ts = c.chartWidget().model().timeScale();
  const b = c.chartWidget().model().mainSeries().bars();
  const idxOf = (t) => {
    let best = null, bd = Infinity;
    b.each((i, v) => { const d = Math.abs(v[0] - t); if (d < bd) { bd = d; best = i; } });
    return best;
  };
  const fi = idxOf(fromSec), ti = idxOf(toSec);
  if (fi === null || ti === null) return {ok: false, error: 'no bars loaded'};
  ts.zoomToBarsRange(fi, ti);
  await new Promise(r => setTimeout(r, 2200));
  const vr = c.getVisibleRange();
  return {ok: true, fromIdx: fi, toIdx: ti,
          achievedFrom: vr.from, achievedTo: vr.to,
          barSpacing: ts.barSpacing()};
}
"""

# One call returns everything the annotator needs: the bars on screen, their page-pixel
# x, and two price/y calibration points. Nothing downstream re-measures by hand.
_SNAPSHOT = """
([canvasSel]) => {
  const c = window.TradingViewApi.activeChart();
  const w = c.chartWidget();
  const m = w.model();
  const ts = m.timeScale();
  const series = m.mainSeries();
  const bars = series.bars();

  const el = document.querySelector(canvasSel);
  const r = el.getBoundingClientRect();
  const rect = {x: r.x, y: r.y, w: r.width, h: r.height};

  const vb = ts.visibleBarsStrictRange();
  const first = vb._firstBar, last = vb._lastBar;

  const visible = [];
  for (let i = Math.ceil(first); i <= Math.floor(last); i++) {
    const v = bars.valueAt(i);
    if (!v) continue;
    visible.push({i: i, t: v[0], o: v[1], h: v[2], l: v[3], c: v[4],
                  x: rect.x + ts.indexToCoordinate(i)});
  }

  const ps = series.priceScale();
  const fv = series.firstValue();
  const pr = c.getVisiblePriceRange();
  const cal = [];
  for (const price of [pr.from, pr.to]) {
    cal.push({price: price, y: rect.y + ps.priceToCoordinate(price, fv)});
  }

  return {
    rect: rect,
    visible_range: c.getVisibleRange(),
    visible_price_range: pr,
    bar_spacing: ts.barSpacing(),
    price_calibration: cal,
    bars: visible,
  };
}
"""


@dataclass
class Snapshot:
    """What the chart is actually showing, in both data and pixel space."""

    rect: dict
    visible_range: dict
    visible_price_range: dict
    bar_spacing: float
    price_calibration: list
    bars: list

    @property
    def bars_by_epoch(self) -> dict[int, dict]:
        return {int(b["t"]): b for b in self.bars}

    def y_of(self, price: float) -> float:
        """Linear price -> page-pixel y, from the chart's own calibration points."""
        (p1, y1), (p2, y2) = (
            (c["price"], c["y"]) for c in self.price_calibration
        )
        if p2 == p1:
            raise ValueError("degenerate price calibration")
        return y1 + (price - p1) * (y2 - y1) / (p2 - p1)


class TVBridge:
    """Thin, verified wrapper over the chart's widget API."""

    def __init__(self, page: Page) -> None:
        self.page = page

    def wait_for_chart(self, timeout_ms: int = 60000) -> None:
        self.page.wait_for_selector(CHART_CANVAS, timeout=timeout_ms)
        self.page.wait_for_timeout(1200)

    def available(self) -> bool:
        return bool(self.page.evaluate("() => !!window.TradingViewApi"))

    def setup(self, symbol: str, resolution: str, timezone: str = "Etc/UTC") -> dict:
        res = self.page.evaluate(_SETUP, [symbol, str(resolution), timezone])
        if not res.get("ok"):
            raise RuntimeError(f"chart setup failed: {res.get('error')}")
        self.wait_for_chart()
        return res

    def load_history(self, target_epoch: int, max_pulls: int = 30) -> dict:
        res: dict[str, Any] = self.page.evaluate(
            _LOAD_HISTORY, [int(target_epoch), int(max_pulls)]
        )
        if not res.get("reached"):
            raise RuntimeError(
                f"history only reaches {res.get('first')}, need {target_epoch} "
                f"(after {res.get('pulls')} pulls, {res.get('size')} bars). "
                "The window may predate what this feed serves."
            )
        return res

    def frame(self, from_epoch: int, to_epoch: int) -> dict:
        res = self.page.evaluate(_FRAME, [int(from_epoch), int(to_epoch)])
        if not res.get("ok"):
            raise RuntimeError(f"framing failed: {res.get('error')}")
        return res

    def snapshot(self) -> Snapshot:
        return Snapshot(**self.page.evaluate(_SNAPSHOT, [CHART_CANVAS]))
