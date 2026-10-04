// Page 2 — Research / Opportunity Explorer (Pipeline B)

function ResearchPage({ oppStats, selectedInstrument, scanJobs, opportunityAnalytics }) {
  // Build KPIs and outcome segments from backend oppStats prop
  function buildKpis(o) {
    if (!o) return {};
    const total  = Math.max(1, o.total_sampled || 1);
    const dist   = o.outcome_distribution || {};
    const tp     = dist.TP_HIT || dist.TP  || 0;
    const to     = dist.TIMEOUT || 0;
    const wl     = o.win_rate_by_direction || {};
    // avgWin = rr_achieved > 0 win rate (NOT the same as TP hit rate)
    const avgWin = ((wl.long||0) + (wl.short||0)) / 2 || tp / total;
    return {
      totalOpps:  { value: total.toLocaleString(), sub: "Sampled records" },
      winRateRR:  (avgWin * 100).toFixed(2) + "%",   // renamed: win = rr>0
      tpHitRate:  ((tp / total) * 100).toFixed(2) + "%", // actual TP_HIT %
      avgRR:      o.avg_rr != null ? (+o.avg_rr).toFixed(3) + " R" : "—",
      timeoutRate:((to / total) * 100).toFixed(2) + "%",
    };
  }
  function buildOutcomes(o) {
    if (!o) return [];
    const total = Math.max(1, o.total_sampled || 1);
    const dist  = o.outcome_distribution || {};
    const tp    = dist.TP_HIT || dist.TP  || 0;
    const sl    = dist.SL_HIT || dist.SL  || 0;
    const to    = dist.TIMEOUT || 0;
    return [
      { label:"TP Hit",  value:tp,  pct:((tp/total)*100).toFixed(1)+"%", color:"#22c55e" },
      { label:"SL Hit",  value:sl,  pct:((sl/total)*100).toFixed(1)+"%", color:"#ef4444" },
      { label:"Timeout", value:to,  pct:((to/total)*100).toFixed(1)+"%", color:"#facc15" },
    ];
  }

  const displayKpis        = buildKpis(oppStats);
  const displayOutcomes    = buildOutcomes(oppStats);
  const displayScanJobs    = scanJobs || [];
  const stackedData        = (opportunityAnalytics && opportunityAnalytics.outcomes_over_time) || [];
  const scatterData        = (opportunityAnalytics && opportunityAnalytics.scatter_points)    || [];
  const stackedXLabels     = stackedData.map(function(b) { return b.period; });

  // Row click is display-only now (TopBar instrument drives all data)
  const [selectedJob, setSelectedJob] = React.useState(null);
  function handleJobClick(job) {
    setSelectedJob(prev => (prev && prev.id === job.id) ? null : job);
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Research / Opportunity Explorer</div>
          <div className="page-sub">Unbiased Market Cartography · Opportunity Scanning · Feature Space</div>
        </div>
        <div style={{ display:"flex", gap:8, alignItems:"center" }}>
          {selectedJob && (
            <span
              onClick={() => setSelectedJob(null)}
              style={{
                fontSize:11, color:"var(--accent)", cursor:"pointer",
                padding:"3px 8px", border:"1px solid rgba(34,211,238,.3)",
                borderRadius:6, background:"rgba(34,211,238,.07)",
              }}
            >← All Jobs</span>
          )}
          <div style={{ fontSize:11, color:"var(--accent)" }}>● M15 · 8Y · Unbiased Mode</div>
        </div>
      </div>

      {/* KPI strip — switches to per-job data when a row is selected */}
      <div className="kpis" style={{ gridTemplateColumns:"1.4fr repeat(4,1fr)" }}>
        <Kpi label="Total Opportunities" tone="num"
             value={(displayKpis.totalOpps && displayKpis.totalOpps.value) || "—"}
             sub={(displayKpis.totalOpps && displayKpis.totalOpps.sub) || ""} />
        <Kpi label="Win Rate (RR>0)" tone="pos" value={displayKpis.winRateRR} />
        <Kpi label="TP Hit Rate"     tone="num" value={displayKpis.tpHitRate} />
        <Kpi label="Avg RR"          tone="num" value={displayKpis.avgRR} />
        <Kpi label="Timeout Rate"    tone="neg" value={displayKpis.timeoutRate} />
      </div>

      <div className="row" style={{ gridTemplateColumns:"1fr 1.3fr" }}>
        {/* Opportunity Outcomes donut — switches to per-job when selected */}
        <div className="card">
          <div className="card-title">
            Opportunity Outcomes
            <span className="right">All Instruments · All Sessions</span>
          </div>
          <div style={{ display:"grid", gridTemplateColumns:"150px 1fr", gap:14, alignItems:"center" }}>
            <DonutChart segments={displayOutcomes} />
            <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
              {displayOutcomes.map(s => (
                <div key={s.label} style={{ display:"flex", justifyContent:"space-between", fontSize:12 }}>
                  <span style={{ color:"#b6c0d6" }}>
                    <span style={{ display:"inline-block", width:7, height:7, borderRadius:"50%", background:s.color, marginRight:7 }} />
                    {s.label}
                  </span>
                  <span className="mono">{s.value.toLocaleString()} <span className="muted">({s.pct})</span></span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Stacked bar — real quarterly data from /api/opportunity_analytics */}
        <div className="card">
          <div className="card-title">Outcomes Over Time
            <span className="legend-row">
              <span><span className="dot" style={{ background:"#22c55e" }} />TP</span>
              <span><span className="dot" style={{ background:"#ef4444" }} />SL</span>
              <span><span className="dot" style={{ background:"#facc15" }} />Timeout</span>
            </span>
          </div>
          <StackedBarChart
            data={stackedData}
            colors={{ tp:"#22c55e", sl:"#ef4444", to:"#facc15" }}
            height={180}
            xLabels={stackedXLabels}
          />
        </div>
      </div>

      <div className="row" style={{ gridTemplateColumns:"1fr 1.2fr", marginTop:12 }}>
        {/* Scatter — real sampled points from /api/opportunity_analytics */}
        <div className="card">
          <div className="card-title">Feature Space (RSI vs RR Distribution)</div>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 90px", gap:8, alignItems:"center" }}>
            <Scatter points={scatterData} />
            <div style={{ display:"flex", flexDirection:"column", gap:6, fontSize:11 }}>
              <span><span className="dot" style={{ background:"#22c55e" }} /> Profitable</span>
              <span><span className="dot" style={{ background:"#facc15" }} /> Breakeven</span>
              <span><span className="dot" style={{ background:"#ef4444" }} /> Losing</span>
            </div>
          </div>
        </div>

        {/* Recent Scan Jobs — clickable rows */}
        <div className="card">
          <div className="card-title">
            Recent Scan Jobs
            {selectedJob && (
              <span className="right muted" style={{ fontSize:10 }}>Click to deselect</span>
            )}
          </div>
          <table className="dt">
            <thead>
              <tr><th>Job ID</th><th>Instrument</th><th>Start Time</th><th>Records</th><th>Status</th></tr>
            </thead>
            <tbody>
              {displayScanJobs.map(j => {
                const isSelected = selectedJob && selectedJob.id === j.id;
                return (
                  <tr
                    key={j.id}
                    onClick={() => handleJobClick(j)}
                    style={{
                      cursor:"pointer",
                      borderLeft: isSelected ? "2px solid var(--accent)" : "2px solid transparent",
                      background: isSelected ? "rgba(34,211,238,.06)" : "transparent",
                    }}
                  >
                    <td className="mono" style={{ color: isSelected ? "var(--accent)" : "" }}>{j.id}</td>
                    <td>{j.inst}</td>
                    <td className="mono">{j.time}</td>
                    <td className="mono">{j.rec}</td>
                    <td><CheckIcon /> <span className="pos" style={{ marginLeft:4 }}>{j.status}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
window.ResearchPage = ResearchPage;
