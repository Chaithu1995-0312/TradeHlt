// Page 2 — Research / Opportunity Explorer (Pipeline B)

function ResearchPage() {
  const k = RESEARCH_KPIS;
  return (
    <div className="panel-frame">
      <Sidebar active="Research" footer={
        <div>
          <div className="muted" style={{ marginBottom: 6 }}>Data Universe</div>
          <div style={{ color: "#22d3ee" }}>● M15 · 8Y</div>
          <div className="muted" style={{ marginTop: 4 }}>Unbiased Mode</div>
        </div>
      } />
      <div className="body">
        <div className="kpis" style={{ gridTemplateColumns: "1.4fr repeat(4, 1fr)" }}>
          <Kpi label="Total Opportunities" tone="num" value={k.totalOpps.value} sub={k.totalOpps.sub} />
          <Kpi label="Win Rate (TP)"   tone="pos" value={k.winRateTP} />
          <Kpi label="Avg RR"          tone="num" value={k.avgRR} />
          <Kpi label="Profit Factor"   tone="num" value={k.profitFactor} />
          <Kpi label="Timeout Rate"    tone="neg" value={k.timeoutRate} />
        </div>

        <div className="row" style={{ gridTemplateColumns: "1fr 1.3fr" }}>
          <div className="card">
            <div className="card-title">Opportunity Outcomes<span className="right">All Instruments · All Sessions</span></div>
            <div style={{ display: "grid", gridTemplateColumns: "150px 1fr", gap: 14, alignItems: "center" }}>
              <DonutChart segments={OUTCOMES_SEGMENTS} />
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {OUTCOMES_SEGMENTS.map(s => (
                  <div key={s.label} style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                    <span style={{ color: "#b6c0d6" }}>
                      <span style={{ display: "inline-block", width: 7, height: 7, borderRadius: "50%", background: s.color, marginRight: 7 }} />
                      {s.label}
                    </span>
                    <span className="mono">{s.value.toLocaleString()} <span className="muted">({s.pct})</span></span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-title">Outcomes Over Time
              <span className="legend-row">
                <span><span className="dot" style={{ background: "#22c55e" }} />TP</span>
                <span><span className="dot" style={{ background: "#ef4444" }} />SL</span>
                <span><span className="dot" style={{ background: "#facc15" }} />Timeout</span>
              </span>
            </div>
            <StackedBarChart
              data={STACKED_OUTCOMES}
              colors={{ tp: "#22c55e", sl: "#ef4444", to: "#facc15" }}
              height={180}
              xLabels={["Apr 21","Oct 21","Apr 22","Oct 22","Apr 23","Oct 23","Apr 24","Apr 25","May 25"]}
            />
          </div>
        </div>

        <div className="row" style={{ gridTemplateColumns: "1fr 1.2fr", marginTop: 12 }}>
          <div className="card">
            <div className="card-title">Feature Space (UMAP 2D Projection)</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 90px", gap: 8, alignItems: "center" }}>
              <Scatter points={SCATTER_POINTS} />
              <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 11 }}>
                <span><span className="dot" style={{ background: "#22c55e" }} /> Profitable</span>
                <span><span className="dot" style={{ background: "#facc15" }} /> Breakeven</span>
                <span><span className="dot" style={{ background: "#ef4444" }} /> Losing</span>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-title">Recent Scan Jobs</div>
            <table className="dt">
              <thead><tr><th>Job ID</th><th>Instrument</th><th>Start Time</th><th>Records</th><th>Status</th></tr></thead>
              <tbody>
                {SCAN_JOBS.map(j => (
                  <tr key={j.id}>
                    <td className="mono">{j.id}</td>
                    <td>{j.inst}</td>
                    <td className="mono">{j.time}</td>
                    <td className="mono">{j.rec}</td>
                    <td><CheckIcon /> <span className="pos" style={{ marginLeft: 4 }}>{j.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <style>{`.legend-row .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px; vertical-align: middle; }`}</style>
      </div>
    </div>
  );
}
window.ResearchPage = ResearchPage;
