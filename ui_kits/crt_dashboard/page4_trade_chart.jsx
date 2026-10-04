// page4_trade_chart.jsx — Trade Chart tab: TradingView-style candles for a selected run.
//
// Self-fetching (like page3_models.jsx's explainModel) so a 47k-bar corpus request is
// never pulled on the app-wide instrument reload in app.jsx — only when this tab is open
// and an instrument+run are selected.
//
// Draws on `window.LightweightCharts` (vendored, v4.2.0 API — see vendor/README.md).
// CRT state ribbons and gap bands are NOT native lightweight-charts primitives; they are
// drawn on plain <canvas> elements positioned against the chart's own time scale via
// `chart.timeScale().timeToCoordinate()`, redrawn on pan/zoom and resize.
//
// The ENGINE track (this run's own events.jsonl, via /api/chart_series) and the RESOLVER
// track (CRTStateResolver, precomputed offline) are DIFFERENT CONSTRUCTIONS of "CRT state
// at bar t" — F-069 measured 88.16% agreement with EXPANSION recall as low as 10.77%. They
// are rendered as two separate ribbons with an agreement figure, never merged.

// Mirrors charts.chart_series.CRT_TOKEN_HEX (Python) — keep in sync by hand; this is a
// display-only palette, not a source of truth.
const CRT_HEX = {
  RANGE:          "#6b7280",
  SHADOW_PENDING: "#a78bfa",
  SWEEP:          "#38bdf8",
  DISPLACEMENT:   "#f59e0b",
  EXPANSION:      "#f97316",
  RETEST:         "#eab308",
  EXECUTION:      "#22c55e",
  RESOLUTION:     "#3b82f6",
  EXPIRED:        "#ef4444",
  UNAVAILABLE:    "#3a4256",
};
const EVENT_HEX = { SWEEP: "#38bdf8", DISPLACEMENT: "#f59e0b", RETEST: "#eab308",
                    EXECUTION: "#22c55e", RESET: "#7f8da6" };

const TIMEFRAMES = ["M15", "H1", "H4", "D1", "W1", "MN1"];

// Payload timestamps are naive ISO strings (broker-local wall clock, F-066) — no timezone
// suffix. Parsing with `Date.parse` would silently apply the VIEWER's local timezone,
// showing different digits per browser. Read the components literally instead, so the
// chart shows exactly the clock face the payload names, matching the "clock basis" the
// legend already states.
function parseWallClockToUnix(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})/.exec(iso || "");
  if (!m) return null;
  return Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]) / 1000;
}

function fmtWallClock(unixSec) {
  if (unixSec == null) return "—";
  const d = new Date(unixSec * 1000);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())} ` +
         `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`;
}

function integrityTone(decision) {
  if (decision === "APPROVE") return { bg: "rgba(34,197,94,0.15)", fg: "#22c55e" };
  if (decision === "WARN")    return { bg: "rgba(250,204,21,0.15)", fg: "#facc15" };
  if (decision === "REJECT")  return { bg: "rgba(239,68,68,0.15)", fg: "#ef4444" };
  return { bg: "rgba(127,141,166,0.15)", fg: "#7f8da6" };
}

function sourceTone(source) {
  return (source || "").startsWith("RESOLVED")
    ? { bg: "rgba(34,211,238,0.12)", fg: "#22d3ee" }
    : { bg: "rgba(127,141,166,0.15)", fg: "#7f8da6" };
}

// One row of colour-coded rectangles under the chart, aligned to the chart's own time
// scale. `chart` and `canvas` are refs' current values; `bars`/`states` are the SAME
// windowed arrays fed to the candle series (1:1, same length).
function drawRibbon(chart, canvas, bars, states) {
  if (!chart || !canvas || !bars || !bars.length) return;
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const w = Math.max(1, Math.round(rect.width)), h = Math.max(1, Math.round(rect.height));
  if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
    canvas.width = w * dpr; canvas.height = h * dpr;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);

  const ts = chart.timeScale();
  const xs = bars.map((b) => ts.timeToCoordinate(b.time));
  for (let i = 0; i < bars.length; i++) {
    const x = xs[i];
    if (x == null) continue;
    const nextX = i + 1 < xs.length && xs[i + 1] != null ? xs[i + 1]
                : i > 0 && xs[i - 1] != null ? x + (x - xs[i - 1]) : x + 6;
    const width = Math.max(1, nextX - x);
    ctx.fillStyle = CRT_HEX[states[i]] || CRT_HEX.UNAVAILABLE;
    ctx.fillRect(x - width / 2, 0, width, h);
  }
}

// Semi-transparent bands over the price pane for wide inter-bar gaps (dataset_integrity's
// aggregate stats don't carry windows to draw — this is chart_api's own per-window scan).
function drawGapBands(chart, canvas, gapBands) {
  if (!chart || !canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const w = Math.max(1, Math.round(rect.width)), h = Math.max(1, Math.round(rect.height));
  if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
    canvas.width = w * dpr; canvas.height = h * dpr;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  if (!gapBands || !gapBands.length) return;

  const ts = chart.timeScale();
  ctx.fillStyle = "rgba(239,68,68,0.08)";
  gapBands.forEach((g) => {
    const x0 = ts.timeToCoordinate(parseWallClockToUnix(g.from));
    const x1 = ts.timeToCoordinate(parseWallClockToUnix(g.to));
    if (x0 == null || x1 == null) return;
    ctx.fillRect(Math.min(x0, x1), 0, Math.max(2, Math.abs(x1 - x0)), h);
  });
}

function TradeChartPanel({ selectedInstrument, selectedRun, runs }) {
  const containerRef   = React.useRef(null);
  const gapCanvasRef    = React.useRef(null);
  const engineCanvasRef = React.useRef(null);
  const resolverCanvasRef = React.useRef(null);

  const chartRef        = React.useRef(null);
  const candleSeriesRef = React.useRef(null);
  const volumeSeriesRef = React.useRef(null);
  const priceLinesRef   = React.useRef([]);
  const drawStateRef    = React.useRef({ bars: [], engine: [], resolver: [], gaps: [] });

  const [timeframe, setTimeframe] = React.useState("M15");
  const [overlays, setOverlays] = React.useState({
    crt: true, resolverRibbon: true, trades: true, events: true, gaps: true,
  });
  const [data, setData]       = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [errorMsg, setErrorMsg] = React.useState(null);

  const runLabel = React.useMemo(() => {
    const r = (runs || []).find((x) => x.run_id === selectedRun);
    return r ? runOptionLabel(r) : selectedRun;
  }, [runs, selectedRun]);

  // ── fetch ──────────────────────────────────────────────────────────────
  React.useEffect(() => {
    if (!selectedInstrument || !selectedRun) { setData(null); setErrorMsg(null); return; }
    let ignore = false;
    setLoading(true);
    setErrorMsg(null);
    window.ApiClient.fetchChartSeries(selectedInstrument, selectedRun, timeframe, 1500)
      .then((d) => {
        if (ignore) return;
        setData(d);
        setLoading(false);
        if (!d.ok) setErrorMsg(d.error || "chart series request failed");
      })
      .catch((e) => {
        if (ignore) return;
        setLoading(false);
        setErrorMsg(String(e && e.message || e));
      });
    return () => { ignore = true; };
  }, [selectedInstrument, selectedRun, timeframe]);

  // ── create chart once ─────────────────────────────────────────────────
  React.useEffect(() => {
    if (!containerRef.current || !window.LightweightCharts) return;
    const chart = window.LightweightCharts.createChart(containerRef.current, {
      layout: { background: { color: "transparent" }, textColor: "#7f8da6",
                fontFamily: "Inter, system-ui" },
      grid: { vertLines: { color: "#1e2a44" }, horzLines: { color: "#1e2a44" } },
      rightPriceScale: { borderColor: "#1e2a44" },
      timeScale: { borderColor: "#1e2a44", timeVisible: true, secondsVisible: false },
      crosshair: { mode: 1 },
      autoSize: true,
    });
    const candleSeries = chart.addCandlestickSeries({
      upColor: "#22c55e", downColor: "#ef4444", borderVisible: false,
      wickUpColor: "#22c55e", wickDownColor: "#ef4444",
    });
    candleSeries.priceScale().applyOptions({ scaleMargins: { top: 0.06, bottom: 0.26 } });
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" }, priceScaleId: "vol", color: "#22d3ee",
    });
    volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.86, bottom: 0 } });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    const redraw = () => {
      const st = drawStateRef.current;
      drawGapBands(chart, gapCanvasRef.current, overlays.gaps ? st.gaps : []);
      drawRibbon(chart, engineCanvasRef.current, st.bars, st.engine);
      drawRibbon(chart, resolverCanvasRef.current, st.bars, st.resolver);
    };
    chart.timeScale().subscribeVisibleLogicalRangeChange(redraw);
    const resizeObs = new ResizeObserver(redraw);
    resizeObs.observe(containerRef.current);

    return () => {
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(redraw);
      resizeObs.disconnect();
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── push data + overlays into the chart ───────────────────────────────
  React.useEffect(() => {
    const chart = chartRef.current;
    const candleSeries = candleSeriesRef.current;
    const volumeSeries = volumeSeriesRef.current;
    if (!chart || !candleSeries || !data || !data.ok) return;

    const bars = data.bars.map((b) => ({
      time: parseWallClockToUnix(b.time), open: b.open, high: b.high, low: b.low, close: b.close,
    })).filter((b) => b.time != null);
    const engineStates   = data.crt_state.engine.states || [];
    const resolverStates = data.crt_state.resolver.states || [];

    const displayBars = overlays.crt ? bars.map((b, i) => {
      const hex = CRT_HEX[engineStates[i]] || CRT_HEX.UNAVAILABLE;
      return { ...b, color: hex, wickColor: hex, borderColor: hex };
    }) : bars;
    candleSeries.setData(displayBars);

    volumeSeries.setData(data.bars.map((b) => {
      const t = parseWallClockToUnix(b.time);
      return t == null ? null : {
        time: t, value: b.volume,
        color: b.close >= b.open ? "rgba(34,197,94,0.5)" : "rgba(239,68,68,0.5)",
      };
    }).filter(Boolean));

    // Trade + event markers.
    const markers = [];
    if (overlays.trades) {
      (data.trades || []).forEach((t) => {
        const openT = parseWallClockToUnix(t.opened_at);
        if (openT != null) {
          markers.push({
            time: openT, position: t.direction === "LONG" ? "belowBar" : "aboveBar",
            color: t.direction === "LONG" ? "#22c55e" : "#ef4444",
            shape: t.direction === "LONG" ? "arrowUp" : "arrowDown",
            text: t.direction || "",
          });
        }
        const closeT = parseWallClockToUnix(t.closed_at);
        if (closeT != null) {
          const rr = t.pnl_rr_net;
          markers.push({
            time: closeT, position: "aboveBar",
            color: rr != null && rr >= 0 ? "#22c55e" : "#ef4444", shape: "circle",
            text: rr != null ? `${rr >= 0 ? "+" : ""}${rr.toFixed(2)}R` : (t.exit_reason || ""),
          });
        }
      });
    }
    if (overlays.events) {
      (data.event_pins || []).forEach((ev) => {
        const t = parseWallClockToUnix(ev.timestamp);
        if (t == null) return;
        markers.push({
          time: t, position: "belowBar", color: EVENT_HEX[ev.event] || "#7f8da6",
          shape: "circle", text: (ev.event || "?")[0],
        });
      });
    }
    markers.sort((a, b) => a.time - b.time);
    candleSeries.setMarkers(markers);

    // SL / TP1 / TP2 price lines for every trade in the window.
    (priceLinesRef.current || []).forEach((pl) => { try { candleSeries.removePriceLine(pl); } catch (e) {} });
    const newLines = [];
    if (overlays.trades) {
      (data.trades || []).forEach((t) => {
        if (t.sl != null) newLines.push(candleSeries.createPriceLine(
          { price: t.sl, color: "#ef4444", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "SL" }));
        if (t.tp1 != null) newLines.push(candleSeries.createPriceLine(
          { price: t.tp1, color: "#22c55e", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "TP1" }));
        if (t.tp2 != null) newLines.push(candleSeries.createPriceLine(
          { price: t.tp2, color: "#22c55e", lineWidth: 1, lineStyle: 3, axisLabelVisible: true, title: "TP2" }));
      });
    }
    priceLinesRef.current = newLines;

    drawStateRef.current = {
      bars, engine: engineStates, resolver: resolverStates,
      gaps: data.gap_bands || [],
    };
    chart.timeScale().fitContent();
    drawGapBands(chart, gapCanvasRef.current, overlays.gaps ? (data.gap_bands || []) : []);
    drawRibbon(chart, engineCanvasRef.current, bars, engineStates);
    drawRibbon(chart, resolverCanvasRef.current, bars, resolverStates);
  }, [data, overlays]);

  const toggleOverlay = (key) => setOverlays((o) => ({ ...o, [key]: !o[key] }));

  if (!selectedInstrument || !selectedRun) {
    return (
      <div className="card" style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>
        Select an instrument and a run (top bar) to open its Trade Chart.
      </div>
    );
  }

  const integrity = data && data.ok ? data.integrity : null;
  const legend = data && data.ok ? data.legend : null;
  const engineSource = data && data.ok ? data.crt_state.engine.source : null;
  const resolverSource = data && data.ok ? data.crt_state.resolver.source : null;
  const iTone = integrityTone(integrity && integrity.decision);
  const eTone = sourceTone(engineSource);
  const rTone = sourceTone(resolverSource);
  const statesPresent = legend ? legend.states_present || [] : [];
  const aliasing = legend ? legend.crt_aliasing : null;

  return (
    <div>
      {/* ── toolbar ─────────────────────────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 10 }}>
        <span style={{ fontSize: 13, color: "var(--muted)" }}>
          <span className="mono">{runLabel || selectedRun}</span>
        </span>
        {integrity && (
          <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 6,
                          background: iTone.bg, color: iTone.fg }}>
            integrity {integrity.decision || "?"}
            {integrity.missing_pct != null ? ` · ${integrity.missing_pct}% missing` : ""}
          </span>
        )}
        {engineSource && (
          <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 6,
                          background: eTone.bg, color: eTone.fg }}>
            engine {engineSource}
          </span>
        )}
        {resolverSource && (
          <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 6,
                          background: rTone.bg, color: rTone.fg }}>
            resolver {resolverSource}
          </span>
        )}
        {loading && <span style={{ fontSize: 11, color: "var(--muted)" }}>loading…</span>}

        <span style={{ marginLeft: "auto", display: "flex", gap: 2, border: "1px solid rgba(127,141,166,0.3)",
                        borderRadius: 6, overflow: "hidden" }}>
          {TIMEFRAMES.map((tf) => (
            <span key={tf} onClick={() => setTimeframe(tf)} style={{
              fontSize: 12, padding: "4px 10px", cursor: "pointer",
              background: tf === timeframe ? "rgba(34,211,238,0.15)" : "transparent",
              color: tf === timeframe ? "var(--accent)" : "var(--muted)",
              fontWeight: tf === timeframe ? 600 : 400,
            }}>{tf}</span>
          ))}
        </span>
      </div>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 8, fontSize: 12, color: "var(--muted)" }}>
        {[
          ["crt", "CRT ribbon (engine)"],
          ["resolverRibbon", "resolver ribbon"],
          ["trades", "trades + SL/TP"],
          ["events", "event pins"],
          ["gaps", "gap bands"],
        ].map(([key, label]) => (
          <label key={key} style={{ display: "flex", alignItems: "center", gap: 5, cursor: "pointer" }}>
            <input type="checkbox" checked={!!overlays[key]} onChange={() => toggleOverlay(key)} />
            {label}
          </label>
        ))}
      </div>

      {errorMsg && (
        <div className="card" style={{ padding: 14, marginBottom: 10, color: "#ef4444", fontSize: 13 }}>
          {errorMsg}
        </div>
      )}

      {/* ── chart + overlay canvases ────────────────────────────────── */}
      <div className="card" style={{ padding: "10px 12px 4px" }}>
        <div style={{ position: "relative", height: 420 }}>
          <div ref={containerRef} style={{ position: "absolute", inset: 0 }} />
          <canvas ref={gapCanvasRef} style={{ position: "absolute", inset: 0, width: "100%",
                                               height: "100%", pointerEvents: "none" }} />
        </div>
        {overlays.crt && (
          <div style={{ marginTop: 4 }}>
            <div style={{ position: "relative", height: 14 }}>
              <canvas ref={engineCanvasRef} style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }} />
            </div>
            <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 1 }}>engine (spine)</div>
          </div>
        )}
        {overlays.resolverRibbon && (
          <div style={{ marginTop: 4 }}>
            <div style={{ position: "relative", height: 14 }}>
              <canvas ref={resolverCanvasRef} style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }} />
            </div>
            <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 1 }}>
              resolver (CRTStateResolver — different construction, see F-069)
            </div>
          </div>
        )}
      </div>

      {/* ── legend + provenance footer ──────────────────────────────── */}
      {legend && (
        <div style={{ marginTop: 10, fontSize: 11.5, color: "var(--muted)" }}>
          <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 6 }}>
            {statesPresent.map((st) => (
              <span key={st} style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: CRT_HEX[st] || CRT_HEX.UNAVAILABLE,
                                display: "inline-block" }} />
                {st.toLowerCase()}
              </span>
            ))}
          </div>
          <div>
            clock basis {legend.session_timestamp_basis || "?"} (F-066, session labels not UTC-corrected)
            {" · "}corpus sha {(data.config_pin.corpus_sha256 || "").slice(0, 12)}
            {" · "}{aliasing && aliasing.note}
          </div>
          {/* G4 (2026-09-10): the RUN's own config, not the CURRENT active config — an
              archived run's states were produced under whatever config was active when
              it ran, which can differ from ACTIVE_VERSION today. */}
          <div style={{ marginTop: 2 }}>
            run config {data.config_pin.run_config_version || "?"}
            {data.config_pin.active_version && data.config_pin.run_config_version
              && data.config_pin.active_version !== data.config_pin.run_config_version && (
              <span style={{ color: "var(--warn, #c77)" }}>
                {" "}(current active is {data.config_pin.active_version} — do not read this chart as current behaviour)
              </span>
            )}
            {" · "}htf clock {data.config_pin.run_htf_clock_basis || "?"}
            {data.config_pin.run_htf_candles_per_range != null
              && ` (${data.config_pin.run_htf_candles_per_range} candles/window)`}
          </div>
          <div style={{ marginTop: 2 }}>descriptive only — no economic claim, no G001 (CLAUDE.md §6.5)</div>
        </div>
      )}
    </div>
  );
}
window.TradeChartPanel = TradeChartPanel;
