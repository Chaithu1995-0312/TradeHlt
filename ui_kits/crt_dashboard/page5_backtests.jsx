// Page 5 — Backtests / Backtest Lab
// All 6 sub-tabs functional: Overview, Trades, Stats, Walk Forward, Monte Carlo, Parameters.

function BacktestsPage() {
  const k = window.BT_KPIS || BT_KPIS;

  const [activeSubTab, setActiveSubTab] = React.useState("Overview");

  const SUB_TABS = ["Overview", "Trades", "Stats", "Walk Forward", "Monte Carlo", "Parameters"];

  // ── Walk Forward data (derived from EQ_BACKTEST — 60 pts → 6 year windows) ──
  const eq = window.EQ_BACKTEST || EQ_BACKTEST || [];
  const WF_YEARS = ["2020", "2021", "2022", "2023", "2024", "2025"];
  const wSize = Math.max(1, Math.floor(eq.length / WF_YEARS.length));
  const wfRows = WF_YEARS.map((yr, i) => {
    const s = eq[i * wSize] || 0;
    const e = eq[Math.min((i + 1) * wSize - 1, eq.length - 1)] || 0;
    const pnl = e - s;
    return { yr, startV: s.toFixed(1), endV: e.toFixed(1), pnl: pnl.toFixed(1), positive: pnl >= 0 };
  });

  // ── Monte Carlo (CLT normal approximation — deterministic, no Math.random) ──
  const deltas = eq.slice(1).map((v, i) => v - eq[i]);
  const mcMean = deltas.length ? deltas.reduce((s, d) => s + d, 0) / deltas.length : 0;
  const mcStd  = deltas.length
    ? Math.sqrt(deltas.reduce((s, d) => s + (d - mcMean) ** 2, 0) / deltas.length)
    : 1;
  const N = deltas.length || 1;
  const mcPcts = [
    { label: "5th",  z: -1.645 },
    { label: "25th", z: -0.674 },
    { label: "50th", z:  0     },
    { label: "75th", z:  0.674 },
    { label: "95th", z:  1.645 },
  ].map(p => ({
    label: p.label,
    finalPnl: (mcMean * N + p.z * mcStd * Math.sqrt(N)).toFixed(1),
  }));

  // ── Trades / Stats data ───────────────────────────────────────────────────
  const trades = window.TRADE_JOURNAL || TRADE_JOURNAL || [];
  const wins   = trades.filter(t => (t.rr || 0) > 0);
  const losses = trades.filter(t => (t.rr || 0) <= 0);
  const longs  = trades.filter(t => (t.dir || "").toUpperCase() === "LONG");
  const shorts = trades.filter(t => (t.dir || "").toUpperCase() === "SHORT");
  const longWins  = longs.filter(t => (t.rr || 0) > 0);
  const shortWins = shorts.filter(t => (t.rr || 0) > 0);
  const avgWin  = wins.length   ? (wins.reduce((s, t) => s + (t.rr || 0), 0) / wins.length).toFixed(2) : "—";
  const avgLoss = losses.length ? (losses.reduce((s, t) => s + Math.abs(t.rr || 0), 0) / losses.length).toFixed(2) : "—";
  const totalPnl = trades.reduce((s, t) => s + (t.rr || 0), 0);
  // Max consecutive wins/losses
  let maxWinStreak = 0, maxLossStreak = 0, curW = 0, curL = 0;
  trades.forEach(t => {
    if ((t.rr || 0) > 0) { curW++; curL = 0; maxWinStreak = Math.max(maxWinStreak, curW); }
    else { curL++; curW = 0; maxLossStreak = Math.max(maxLossStreak, curL); }
  });

  const sessionPnl = window.SESSION_PNL || SESSION_PNL || [];

  return (
    <div className="panel-frame">
      <Sidebar active="Backtests" footer={
        <div>
          <div className="muted">Backtest Engine</div>
          <div style={{ color: "#e6edf7", fontWeight: 700 }}>v5.2</div>
        </div>
      } />
      <div className="body">

        {/* ── Controls row ─────────────────────────────────────────────────── */}
        <div className="row" style={{ gridTemplateColumns: "1fr 1fr 1.2fr 1.2fr 0.7fr", marginBottom: 12 }}>
          <div>
            <label className="muted" style={{ fontSize: 11, display: "block", marginBottom: 4 }}>Strategy</label>
            <select className="select"><option>CRT v5</option><option>CRT v4</option></select>
          </div>
          <div>
            <label className="muted" style={{ fontSize: 11, display: "block", marginBottom: 4 }}>Model Set</label>
            <select className="select"><option>v4_mirrored</option><option>v4_val_test</option></select>
          </div>
          <div>
            <label className="muted" style={{ fontSize: 11, display: "block", marginBottom: 4 }}>Period</label>
            <input className="input" defaultValue="2020-01-01 → 2025-05-15" />
          </div>
          <div>
            <label className="muted" style={{ fontSize: 11, display: "block", marginBottom: 4 }}>Mode</label>
            <select className="select"><option>Walk Forward</option><option>Standard</option></select>
          </div>
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <button className="btn warning" style={{ width: "100%", padding: "8px 12px" }}>Run Backtest</button>
          </div>
        </div>

        {/* ── KPI strip (always visible) ────────────────────────────────────── */}
        <div className="kpis" style={{ gridTemplateColumns: "repeat(6, 1fr)" }}>
          <Kpi label="Total PnL (R)"   tone="pos" value={k.totalPnl} />
          <Kpi label="CAGR"            tone="num" value={k.cagr} />
          <Kpi label="Win Rate"        tone="num" value={k.winRate} />
          <Kpi label="Profit Factor"   tone="num" value={k.profitFactor} />
          <Kpi label="Max DD (R)"      tone="neg" value={k.maxDD} />
          <Kpi label="Sharpe"          tone="num" value={k.sharpe} />
        </div>

        {/* ── Sub-tab bar ──────────────────────────────────────────────────── */}
        <div className="tabs" style={{ marginBottom: 12 }}>
          {SUB_TABS.map(t => (
            <span
              key={t}
              className={`tab${activeSubTab === t ? " active" : ""}`}
              onClick={() => setActiveSubTab(t)}
              style={{ cursor: "pointer" }}
            >{t}</span>
          ))}
        </div>

        {/* ── Overview: 3 charts ───────────────────────────────────────────── */}
        {activeSubTab === "Overview" && (
          <div className="row" style={{ gridTemplateColumns: "1fr 1fr 1.4fr" }}>
            <div className="card">
              <div className="card-title">Equity Curve (R)</div>
              <LineChart values={eq} height={170} xLabels={WF_YEARS} color="#facc15" areaFill="#facc15" />
            </div>
            <div className="card">
              <div className="card-title">Drawdown (R)</div>
              <DrawdownChart values={window.DRAWDOWN || DRAWDOWN} height={170} color="#ef4444" />
            </div>
            <div className="card">
              <div className="card-title">Monthly Returns (R)</div>
              <Heatmap
                rows={window.MONTHLY_RETURNS || MONTHLY_RETURNS}
                colLabels={["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]}
                height={180}
              />
            </div>
          </div>
        )}

        {/* ── Trades ───────────────────────────────────────────────────────── */}
        {activeSubTab === "Trades" && (
          <div className="card">
            <table className="dt">
              <thead>
                <tr>
                  <th>#</th><th>Date / Time</th><th>Direction</th>
                  <th>Entry</th><th>Exit</th><th>PnL (R)</th>
                  <th>Result</th><th>Session</th><th>Exit Reason</th>
                </tr>
              </thead>
              <tbody>
                {trades.length === 0 ? (
                  <tr><td colSpan={9} style={{ textAlign:"center", color:"#7f8da6", padding:16 }}>No trade data — run a backtest first</td></tr>
                ) : trades.map((t, i) => (
                  <tr key={t.id || i}>
                    <td className="muted">{i + 1}</td>
                    <td className="mono">{t.time || t.opened_at || "—"}</td>
                    <td className={(t.dir||"").toUpperCase() === "LONG" ? "mono pos" : "mono neg"}>
                      {(t.dir || "—").toUpperCase()}
                    </td>
                    <td className="mono">{t.entry || "—"}</td>
                    <td className="mono">{t.exit || "—"}</td>
                    <td className={`mono ${(t.rr||0) >= 0 ? "pos" : "neg"}`}>
                      {(t.rr||0) >= 0 ? "+" : ""}{(+(t.rr||0)).toFixed(2)}
                    </td>
                    <td>
                      <StatusPill status={
                        (t.result||"").toUpperCase() === "TP" || (t.result||"").toUpperCase() === "COMPLETED"
                          ? "Completed" : "Archived"
                      } />
                    </td>
                    <td className="muted">{t.session || "—"}</td>
                    <td className="muted" style={{ fontSize: 11 }}>{t.exitReason || t.reason || "—"}</td>
                  </tr>
                ))}
              </tbody>
              {trades.length > 0 && (
                <tfoot>
                  <tr style={{ borderTop: "2px solid #23364e" }}>
                    <td colSpan={5} style={{ padding:"6px 8px", color:"#7f8da6", fontSize:11 }}>
                      {trades.length} trades · {wins.length}W / {losses.length}L
                    </td>
                    <td className={`mono ${totalPnl >= 0 ? "pos" : "neg"}`} style={{ fontWeight: 700 }}>
                      {totalPnl >= 0 ? "+" : ""}{totalPnl.toFixed(2)}
                    </td>
                    <td colSpan={3}></td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        )}

        {/* ── Stats ────────────────────────────────────────────────────────── */}
        {activeSubTab === "Stats" && (
          <div className="row" style={{ gridTemplateColumns: "1fr 1fr" }}>
            {/* Left — numeric breakdown */}
            <div className="card">
              <div className="card-title">Performance Breakdown</div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <tbody>
                  {[
                    ["Total Trades",         trades.length],
                    ["Wins / Losses",         `${wins.length} / ${losses.length}`],
                    ["Win Rate",              trades.length ? ((wins.length / trades.length) * 100).toFixed(1) + "%" : "—"],
                    ["Avg Win (R)",           avgWin],
                    ["Avg Loss (R)",          avgLoss],
                    ["Long Win Rate",         longs.length ? ((longWins.length / longs.length) * 100).toFixed(1) + "%" : "—"],
                    ["Short Win Rate",        shorts.length ? ((shortWins.length / shorts.length) * 100).toFixed(1) + "%" : "—"],
                    ["Max Consec. Wins",      maxWinStreak],
                    ["Max Consec. Losses",    maxLossStreak],
                    ["Total PnL (R)",         totalPnl >= 0 ? "+" + totalPnl.toFixed(2) : totalPnl.toFixed(2)],
                  ].map(([label, val]) => (
                    <tr key={label} style={{ borderBottom: "1px solid #1d2f42" }}>
                      <td style={{ padding: "6px 8px", color: "#9fb0c8" }}>{label}</td>
                      <td style={{ padding: "6px 8px", textAlign: "right", fontFamily: "monospace", color: "#e6edf7" }}>{val}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Right — session bars */}
            <div className="card">
              <div className="card-title">Win Rate by Session (%)</div>
              {sessionPnl.length > 0 ? (
                <VerticalBars
                  items={sessionPnl.map(s => ({ value: s.value, label: s.label, color: s.color || "#22c55e" }))}
                  height={200}
                />
              ) : (
                <div style={{ color: "#7f8da6", fontSize: 12, padding: 16 }}>No session data available</div>
              )}
            </div>
          </div>
        )}

        {/* ── Walk Forward ─────────────────────────────────────────────────── */}
        {activeSubTab === "Walk Forward" && (
          <div className="row" style={{ gridTemplateColumns: "1fr 1fr" }}>
            <div className="card">
              <div className="card-title">Rolling Year Performance</div>
              <table className="dt">
                <thead>
                  <tr><th>Year</th><th>Start (R)</th><th>End (R)</th><th>PnL (R)</th><th>Trend</th></tr>
                </thead>
                <tbody>
                  {wfRows.map(r => (
                    <tr key={r.yr}>
                      <td className="mono">{r.yr}</td>
                      <td className="mono">{r.startV}</td>
                      <td className="mono">{r.endV}</td>
                      <td className={`mono ${r.positive ? "pos" : "neg"}`}>
                        {r.positive ? "+" : ""}{r.pnl}
                      </td>
                      <td style={{ fontSize: 14 }}>{r.positive ? "▲" : "▼"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="card">
              <div className="card-title">PnL per Window (R)</div>
              <VerticalBars
                items={wfRows.map(r => ({
                  value: Math.abs(parseFloat(r.pnl)),
                  label: r.yr,
                  color: r.positive ? "#22c55e" : "#ef4444",
                }))}
                height={200}
              />
            </div>
          </div>
        )}

        {/* ── Monte Carlo ──────────────────────────────────────────────────── */}
        {activeSubTab === "Monte Carlo" && (
          <div className="row" style={{ gridTemplateColumns: "1fr 1fr" }}>
            <div className="card">
              <div className="card-title">Outcome Distribution (1,000 Paths)</div>
              <div className="muted" style={{ fontSize: 11, marginBottom: 10 }}>
                CLT normal approximation · {N} period increments · mean={mcMean.toFixed(3)} σ={mcStd.toFixed(3)}
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr>
                    <th style={{ padding:"6px 8px", textAlign:"left", color:"#7f8da6" }}>Percentile</th>
                    <th style={{ padding:"6px 8px", textAlign:"right", color:"#7f8da6" }}>Expected Final PnL (R)</th>
                  </tr>
                </thead>
                <tbody>
                  {mcPcts.map(p => {
                    const v = parseFloat(p.finalPnl);
                    return (
                      <tr key={p.label} style={{ borderBottom: "1px solid #1d2f42" }}>
                        <td style={{ padding:"7px 8px", color:"#9fb0c8" }}>{p.label} percentile</td>
                        <td style={{ padding:"7px 8px", textAlign:"right", fontFamily:"monospace",
                          color: v >= 0 ? "#22c55e" : "#ef4444", fontWeight: p.label === "50th" ? 700 : 400 }}>
                          {v >= 0 ? "+" : ""}{p.finalPnl}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="card">
              <div className="card-title">Percentile Outcome Bars</div>
              <VerticalBars
                items={mcPcts.map(p => ({
                  value: Math.abs(parseFloat(p.finalPnl)),
                  label: p.label,
                  color: parseFloat(p.finalPnl) >= 0 ? "#22c55e" : "#ef4444",
                }))}
                height={200}
              />
            </div>
          </div>
        )}

        {/* ── Parameters ───────────────────────────────────────────────────── */}
        {activeSubTab === "Parameters" && (
          <div className="card">
            <div className="card-title">Backtest Configuration</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 32px", fontSize: 12 }}>
              {[
                ["Strategy",         "CRT v5"],
                ["Model Set",        (window.RT_KPIS || RT_KPIS || {}).activeModel || "v4_mirrored"],
                ["Period",           "2020-01-01 → 2025-05-15"],
                ["Mode",             "Walk Forward"],
                ["Feature Schema",   "v5 (35 features)"],
                ["Engines",          "CRT · Gaussian · Zone Gate · RR"],
                ["Min Corr Gate",    "0.150"],
                ["Min Samples",      "1,000"],
                ["Risk Model",       "UltronRiskGate"],
                ["Fusion Strategy",  "Weighted completeness"],
                ["SL/TP Rule",       "ATR-based · ExecutionPlannerV1_2"],
                ["Data Source",      "M15 OHLCV — EURUSD"],
              ].map(([label, val]) => (
                <div key={label} style={{ display:"flex", justifyContent:"space-between", borderBottom:"1px solid #1d2f42", padding:"7px 0" }}>
                  <span style={{ color:"#9fb0c8" }}>{label}</span>
                  <span style={{ fontFamily:"monospace", color:"#e6edf7" }}>{val}</span>
                </div>
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
window.BacktestsPage = BacktestsPage;
