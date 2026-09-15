# vendor/

Vendored third-party JS. No CDN loads at runtime — everything here is fetched once and
committed, matching `react.development.js` / `react-dom.development.js` / `babel.min.js`.

| File | Package | Version | Source | sha256 |
|---|---|---|---|---|
| `react.development.js` | react | (pre-existing) | — | — |
| `react-dom.development.js` | react-dom | (pre-existing) | — | — |
| `babel.min.js` | @babel/standalone | (pre-existing) | — | — |
| `lightweight-charts.standalone.production.js` | lightweight-charts | 4.2.0 | `https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js` | `46fc69534ec098f095bbcd1d9a26d693d39a8b9eeff7343536765b3dd28c2bd` |

## lightweight-charts

Apache-2.0 licensed (TradingView, Inc.). Defines a single global, `window.LightweightCharts`.
Added 2026-09-10 for the CRT dashboard's Trade Chart tab (`page4_trade_chart.jsx`).

**Pinned at v4.2.0 deliberately** — v5 replaced `chart.addCandlestickSeries(...)` with
`chart.addSeries(CandlestickSeries, ...)` and removed the old factory methods entirely, so
the two major versions are not drop-in compatible. `page4_trade_chart.jsx` is written
against the v4 API (`addCandlestickSeries`, `addHistogramSeries`, `setMarkers`,
`createPriceLine`, `timeScale().timeToCoordinate()`,
`subscribeVisibleLogicalRangeChange`). Upgrading to v5 requires updating that file's series
construction calls, not just swapping this file.

To re-verify the file matches its declared version/hash:

```bash
sha256sum ui_kits/crt_dashboard/vendor/lightweight-charts.standalone.production.js
```
