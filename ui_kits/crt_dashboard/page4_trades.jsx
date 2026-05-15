// Page 4 — Trades / Trade Analytics & Journal

function TradesPage() {
  const k = TRADE_KPIS;
  return (
    <div className="panel-frame">
      <Sidebar active="Trades" footer={
        <div>
          <div className="muted">Total Trades</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: "#e6edf7" }}>4,218</div>
          <div className="muted">All Time</div>
        </div>
      } />
      <div className="body">
        <div className="kpis" style={{ gridTemplateColumns: "repeat(6, 1fr)" }}>
          <Kpi label="Total PnL (R)"   tone="pos" value={k.totalPnl} />
          <Kpi label="Win Rate"        tone="num" value={k.winRate} />
          <Kpi label="Profit Factor"   tone="num" value={k.profitFactor} />
          <Kpi label="Expectancy (R)"  tone="num" value={k.expectancy} />
          <Kpi label="Avg RR (W/L)"    tone="num" value={k.avgRR} />
          <Kpi label="Max Drawdown (R)" tone="neg" value={k.maxDD} />
        </div>

        <div className="row" style={{ gridTemplateColumns: "1fr 1fr" }}>
          <div className="card">
            <div className="card-title">Equity Curve (R)<span className="right">All Time ▾</span></div>
            <LineChart values={EQ_TRADES} height={180} xLabels={["2022","2023","2024","2025"]} color="#22c55e" areaFill="#22c55e" />
          </div>
          <div className="card">
            <div className="card-title">PnL by Session (R)</div>
            <VerticalBars items={SESSION_PNL} height={200} />
          </div>
        </div>

        <div className="card" style={{ marginTop: 12 }}>
          <div className="card-title">Trade Journal (Recent)</div>
          <table className="dt">
            <thead><tr><th>ID</th><th>Time</th><th>Dir</th><th>Entry</th><th>Exit</th><th>RR (R)</th><th>Result</th><th>Session</th><th>Model Conf</th><th>Exit Reason</th></tr></thead>
            <tbody>
              {TRADE_JOURNAL.map(t => (
                <tr key={t.id}>
                  <td className="mono">{t.id}</td>
                  <td className="mono">{t.time}</td>
                  <td><span className={`tag ${t.dir === "LONG" ? "long" : "short"}`}>{t.dir}</span></td>
                  <td className="mono">{t.entry}</td>
                  <td className="mono">{t.exit}</td>
                  <td className={`mono ${t.rr > 0 ? "pos" : "neg"}`}>{t.rr > 0 ? "+" : ""}{t.rr.toFixed(2)}</td>
                  <td><span className={`tag ${t.result === "TP" ? "tp" : "sl"}`}>{t.result}</span></td>
                  <td>{t.session}</td>
                  <td className="mono">{t.conf.toFixed(2)}</td>
                  <td className="muted">{t.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
window.TradesPage = TradesPage;
