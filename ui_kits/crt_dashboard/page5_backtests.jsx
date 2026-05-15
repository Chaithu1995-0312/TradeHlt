// Page 5 — Backtests / Backtest Lab

function BacktestsPage() {
  const k = BT_KPIS;
  return (
    <div className="panel-frame">
      <Sidebar active="Backtests" footer={
        <div>
          <div className="muted">Backtest Engine</div>
          <div style={{ color: "#e6edf7", fontWeight: 700 }}>v5.2</div>
        </div>
      } />
      <div className="body">
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

        <div className="kpis" style={{ gridTemplateColumns: "repeat(6, 1fr)" }}>
          <Kpi label="Total PnL (R)"   tone="pos" value={k.totalPnl} />
          <Kpi label="CAGR"            tone="num" value={k.cagr} />
          <Kpi label="Win Rate"        tone="num" value={k.winRate} />
          <Kpi label="Profit Factor"   tone="num" value={k.profitFactor} />
          <Kpi label="Max DD (R)"      tone="neg" value={k.maxDD} />
          <Kpi label="Sharpe"          tone="num" value={k.sharpe} />
        </div>

        <div className="row" style={{ gridTemplateColumns: "1fr 1fr 1.4fr" }}>
          <div className="card">
            <div className="card-title">Equity Curve (R)</div>
            <LineChart values={EQ_BACKTEST} height={170} xLabels={["2020","2021","2022","2023","2024","2025"]} color="#facc15" areaFill="#facc15" />
          </div>
          <div className="card">
            <div className="card-title">Drawdown (R)</div>
            <DrawdownChart values={DRAWDOWN} height={170} color="#ef4444" />
          </div>
          <div className="card">
            <div className="card-title">Monthly Returns (R)</div>
            <Heatmap rows={MONTHLY_RETURNS} colLabels={["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]} height={180} />
          </div>
        </div>

        <div className="tabs">
          <span className="tab active">Overview</span>
          <span className="tab">Trades</span>
          <span className="tab">Stats</span>
          <span className="tab">Walk Forward</span>
          <span className="tab">Monte Carlo</span>
          <span className="tab">Parameters</span>
        </div>
      </div>
    </div>
  );
}
window.BacktestsPage = BacktestsPage;
