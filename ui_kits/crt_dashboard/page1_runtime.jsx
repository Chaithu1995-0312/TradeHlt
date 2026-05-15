// Page 1 — Runtime / Live Trading Dashboard

function RuntimePage() {
  const k = RT_KPIS;
  return (
    <div className="panel-frame">
      <Sidebar active="Runtime" footer={
        <div>
          <div><span className="dot" />Live Mode</div>
          <div style={{ color: "#22c55e", marginTop: 2, fontWeight: 600 }}>CONNECTED</div>
          <div style={{ marginTop: 4, opacity: 0.8 }}>15:35:42 UTC+5:30</div>
        </div>
      } />
      <div className="body">
        <div className="kpis">
          <Kpi label="Active Model" value={k.activeModel} sub={k.modelKind} />
          <Kpi label="Kill Switch"  pill={{ kind: "safe", text: k.killSwitch }} />
          <Kpi label="Convergence"  tone="num" value={k.convergence.value.toFixed(2)} sub={k.convergence.label} />
          <Kpi label="Regime"       pill={{ kind: "live", text: k.regime.value }} sub={k.regime.sub} />
          <Kpi label="Trades (24h)" value={k.trades24h.value} sub={k.trades24h.sub} />
          <Kpi label="Daily PnL (R)" tone="pos" value={`+${k.pnl24h.toFixed(2)}`} />
        </div>

        <div className="row" style={{ gridTemplateColumns: "1.15fr 0.85fr 1.3fr" }}>
          <div className="card">
            <div className="card-title">Model Fusion Score</div>
            <div style={{ display: "grid", gridTemplateColumns: "150px 1fr", gap: 14, alignItems: "center" }}>
              <DonutChart segments={FUSION_SEGMENTS} centerLabel="0.82" centerSub="High Confidence" />
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {FUSION_SEGMENTS.map(s => (
                  <div key={s.label} style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                    <span style={{ color: "#b6c0d6" }}>
                      <span style={{ display: "inline-block", width: 7, height: 7, borderRadius: "50%", background: s.color, marginRight: 7 }} />
                      {s.label}
                    </span>
                    <span className="mono" style={{ color: "#e6edf7" }}>{s.value.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-title">Live Signal</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", rowGap: 10, columnGap: 10, fontSize: 12 }}>
              <div>
                <div className="muted" style={{ fontSize: 11 }}>Direction</div>
                <div style={{ color: "#22c55e", fontWeight: 700, fontSize: 15 }}>LONG ↗</div>
              </div>
              <div>
                <div className="muted" style={{ fontSize: 11 }}>Entry</div>
                <div className="mono" style={{ fontWeight: 600, fontSize: 14 }}>{LIVE_SIGNAL.entry}</div>
              </div>
              <div>
                <div className="muted" style={{ fontSize: 11 }}>Confidence</div>
                <div className="cyan" style={{ fontWeight: 700, fontSize: 14 }}>{LIVE_SIGNAL.confidence.toFixed(2)}</div>
              </div>
              <div>
                <div className="muted" style={{ fontSize: 11 }}>Expected RR</div>
                <div className="cyan" style={{ fontWeight: 700, fontSize: 14 }}>{LIVE_SIGNAL.expectedRR.toFixed(2)}</div>
              </div>
              <div>
                <div className="muted" style={{ fontSize: 11 }}>Risk (1R)</div>
                <div className="mono">{LIVE_SIGNAL.risk}</div>
              </div>
              <div>
                <div className="muted" style={{ fontSize: 11 }}>TP (2R)</div>
                <div className="mono pos">{LIVE_SIGNAL.tp}</div>
              </div>
              <div>
                <div className="muted" style={{ fontSize: 11 }}>SL (1R)</div>
                <div className="mono neg">{LIVE_SIGNAL.sl}</div>
              </div>
              <div>
                <div className="muted" style={{ fontSize: 11 }}>Session</div>
                <div className="mono">{LIVE_SIGNAL.session}</div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-title">Equity Curve (R)<span className="right">All Time ▾</span></div>
            <LineChart values={EQ_RUNTIME} height={170} xLabels={["May 10","May 12","May 14","May 15"]} color="#22d3ee" areaFill="#22d3ee" />
          </div>
        </div>

        <div className="card" style={{ marginTop: 12 }}>
          <div className="card-title">Recent Trades</div>
          <table className="dt">
            <thead><tr><th>ID</th><th>Time</th><th>Dir</th><th>Entry</th><th>Exit</th><th>RR (R)</th><th>Result</th><th>Model Conf</th><th>Regime</th></tr></thead>
            <tbody>
              {RT_TRADES.map(t => (
                <tr key={t.id}>
                  <td className="mono">{t.id}</td>
                  <td className="mono">{t.time}</td>
                  <td><span className={`tag ${t.dir === "LONG" ? "long" : "short"}`}>{t.dir}</span></td>
                  <td className="mono">{t.entry}</td>
                  <td className="mono">{t.exit}</td>
                  <td className={`mono ${t.rr > 0 ? "pos" : "neg"}`}>{t.rr > 0 ? "+" : ""}{t.rr.toFixed(2)}</td>
                  <td><span className={`tag ${t.result === "TP" ? "tp" : "sl"}`}>{t.result}</span></td>
                  <td className="mono">{t.conf.toFixed(2)}</td>
                  <td><span className="tag normal">{t.regime}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
window.RuntimePage = RuntimePage;
