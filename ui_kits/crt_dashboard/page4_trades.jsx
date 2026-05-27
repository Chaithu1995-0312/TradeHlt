// Page 4 — Trades / Trade Analytics & Journal

function TradesPage({ activeSub, trades, tradeKpis, equity, selectedInstrument }) {
  const k = tradeKpis || {};
  const TABS = ["Trade Explorer","Trade Trace","Rejections","Session Analysis"];
  const SUB_TO_TAB = { TradeTrace:"Trade Trace", Rejections:"Rejections", SessionAnalysis:"Session Analysis" };
  const [activeTab, setActiveTab] = React.useState(() => SUB_TO_TAB[activeSub] || "Trade Explorer");

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Trades / Trade Analytics &amp; Journal</div>
          <div className="page-sub">Performance · Distribution · Sessions · Detailed Journal · <span style={{color:"var(--accent)"}}>{selectedInstrument || "—"}</span></div>
        </div>
      </div>

      {/* KPI strip — always visible */}
      <div className="kpis" style={{ gridTemplateColumns:"repeat(6,1fr)", marginBottom:12 }}>
        <Kpi label="Total PnL (R)"    tone="pos" value={k.totalPnl    || "+356.42"} />
        <Kpi label="Win Rate"         tone="num" value={k.winRate      || "54.37%"} />
        <Kpi label="Profit Factor"    tone="num" value={k.profitFactor || "1.38"} />
        <Kpi label="Expectancy (R)"   tone="num" value={k.expectancy   || "0.42"} />
        <Kpi label="Avg RR (W/L)"     tone="num" value={k.avgRR        || "1.62 / -1.03"} />
        <Kpi label="Max Drawdown (R)" tone="neg" value={k.maxDD        || "-12.4"} />
      </div>

      {/* Sub-tab bar */}
      <div style={{ display:"flex", gap:8, marginBottom:12 }}>
        {TABS.map(t => (
          <span key={t} onClick={() => setActiveTab(t)} style={{
            fontSize:12, padding:"6px 12px", borderRadius:6, cursor:"pointer",
            background: t === activeTab ? "rgba(34,211,238,.12)" : "transparent",
            color:      t === activeTab ? "var(--accent)" : "var(--muted)",
            border:     t === activeTab ? "1px solid rgba(34,211,238,.35)" : "1px solid transparent",
            fontWeight: t === activeTab ? 600 : 400,
          }}>{t}</span>
        ))}
      </div>

      {/* ── Trade Explorer ──────────────────────────────────────────── */}
      {activeTab === "Trade Explorer" && (
        <div>
          <div className="row" style={{ gridTemplateColumns:"1fr 1fr", marginBottom:14 }}>
            <div className="card">
              <div className="card-title">Equity Curve (R)<span className="right">All Time ▾</span></div>
              <LineChart values={equity || []} color="#22c55e" height={180} />
            </div>
            <div className="card">
              <div className="card-title">PnL by Session (R)</div>
              <VerticalBars
                data={(window.SESSION_PNL || []).map(s => ({ label:s.label, value:s.value, color:s.color }))}
                height={180} maxVal={100}
              />
            </div>
          </div>

          <div className="card">
            <div className="card-title">Trade Journal (Recent)</div>
            <table className="dt">
              <thead>
                <tr>
                  <th>ID</th><th>Time</th><th>Dir</th><th>Entry</th><th>Exit</th>
                  <th>RR (R)</th><th>Result</th><th>Session</th><th>Model Conf</th><th>Exit Reason</th>
                </tr>
              </thead>
              <tbody>
                {(trades || []).map(t => (
                  <tr key={t.id}>
                    <td className="mono">{t.id}</td>
                    <td className="mono">{t.time}</td>
                    <td><span className={`tag ${t.dir === "LONG" ? "long" : "short"}`}>{t.dir}</span></td>
                    <td className="mono">{t.entry}</td>
                    <td className="mono">{t.exit}</td>
                    <td className={`mono ${t.rr > 0 ? "pos" : "neg"}`}>{t.rr > 0 ? "+" : ""}{(+t.rr).toFixed(2)}</td>
                    <td><span className={`tag ${t.result === "TP" ? "tp" : "sl"}`}>{t.result}</span></td>
                    <td>{t.session}</td>
                    <td className="mono">{t.conf != null ? (+t.conf).toFixed(2) : "—"}</td>
                    <td className="muted">{t.reason || t.exitReason || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Trade Trace ─────────────────────────────────────────────── */}
      {activeTab === "Trade Trace" && (
        <div className="row" style={{ gridTemplateColumns:"1fr 1.4fr", gap:14 }}>
          <div className="card">
            <div className="card-title">Trade Trace <span className="right muted">Most Recent</span></div>
            <div className="trade-trace-list">
              {(window.TRADE_TRACE || []).map((ev, i) => (
                <div key={i} className="trace-item">
                  <div className={`trace-dot${ev.dot === "ok" ? "" : " muted"}`} />
                  <div className="trace-time">{ev.time}</div>
                  <div>
                    <div className="trace-event">{ev.event}</div>
                    {ev.sub && <div className="trace-sub">{ev.sub}</div>}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="card">
            <div className="card-title">RR Distribution</div>
            <VerticalBars
              data={[
                { label:"< -1",  value:18, color:"#ef4444" },
                { label:"-1–0",  value:24, color:"#f97316" },
                { label:"0–1",   value:31, color:"#facc15" },
                { label:"1–2",   value:42, color:"#22c55e" },
                { label:"2–3",   value:28, color:"#22d3ee" },
                { label:"> 3",   value:15, color:"#a78bfa" },
              ]}
              height={180} maxVal={50}
            />
          </div>
        </div>
      )}

      {/* ── Rejections ──────────────────────────────────────────────── */}
      {activeTab === "Rejections" && (
        <div className="card">
          <div className="card-title">Rejected Signals <span className="right muted">Last 200 bars</span></div>
          <table className="dt">
            <thead><tr><th>Time</th><th>Instrument</th><th>Direction</th><th>Reason</th><th>Engine</th><th>Score</th></tr></thead>
            <tbody>
              {[
                { time:"13:42", inst:"EURUSD", dir:"LONG",  reason:"Zone Gate Reject", engine:"Zone Gate", score:"0.31" },
                { time:"13:38", inst:"GBPUSD", dir:"SHORT", reason:"Low Gaussian Conf", engine:"Gaussian",  score:"0.44" },
                { time:"13:25", inst:"EURUSD", dir:"LONG",  reason:"RR Below Min",      engine:"RR Miner",  score:"1.18" },
                { time:"13:10", inst:"AUDUSD", dir:"SHORT", reason:"Kill Switch Active", engine:"Risk Gate", score:"—" },
                { time:"12:58", inst:"EURUSD", dir:"SHORT", reason:"Fusion Score Low",   engine:"Fusion",    score:"0.52" },
              ].map((r, i) => (
                <tr key={i}>
                  <td className="mono">{r.time}</td>
                  <td className="mono">{r.inst}</td>
                  <td><span className={`tag ${r.dir === "LONG" ? "long" : "short"}`}>{r.dir}</span></td>
                  <td>{r.reason}</td>
                  <td className="muted">{r.engine}</td>
                  <td className="mono">{r.score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Session Analysis ─────────────────────────────────────────── */}
      {activeTab === "Session Analysis" && (
        <div className="row" style={{ gridTemplateColumns:"1fr 1fr", gap:14 }}>
          <div className="card">
            <div className="card-title">Win Rate by Session (%)</div>
            <VerticalBars
              data={(window.SESSION_PNL || []).map(s => ({ label:s.label, value:s.value, color:s.color }))}
              height={200} maxVal={100}
            />
          </div>
          <div className="card">
            <div className="card-title">Session Breakdown</div>
            <table className="dt">
              <thead><tr><th>Session</th><th>Trades</th><th>Win Rate</th><th>Avg RR</th><th>PnL (R)</th></tr></thead>
              <tbody>
                {[
                  { sess:"Asian",   trades:812,  wr:"51.2%", rr:"1.48", pnl:"+62.4" },
                  { sess:"London",  trades:1840, wr:"57.8%", rr:"1.71", pnl:"+184.2" },
                  { sess:"New York",trades:1124, wr:"53.4%", rr:"1.59", pnl:"+94.6" },
                  { sess:"Overlap", trades:442,  wr:"60.1%", rr:"1.88", pnl:"+58.1" },
                ].map(r => (
                  <tr key={r.sess}>
                    <td>{r.sess}</td>
                    <td className="mono">{r.trades}</td>
                    <td className="mono">{r.wr}</td>
                    <td className="mono">{r.rr}</td>
                    <td className="mono pos">{r.pnl}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
window.TradesPage = TradesPage;
