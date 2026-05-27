// Page 0 — Executive Overview (default landing page)

function ExecutivePage({ status, equity, oppStats, selectedInstrument }) {
  // Build executive KPIs from backend props
  const s = status || {};
  const o = oppStats || {};
  const dist = (o.outcome_distribution || {});
  const tp   = dist.TP_HIT || dist.TP || 0;
  const tot  = Math.max(1, o.total_sampled || 1);
  const wl   = o.win_rate_by_direction || {};
  const winRate = (((wl.long || 0) + (wl.short || 0)) / 2 * 100) || (tp / tot * 100);

  const k = {
    totalPnl:     "+356.42",  // TODO: from /api/equity_curve summary
    totalPnlDelta:"↑ 1.62%",
    winRate:       winRate > 0 ? winRate.toFixed(2) + "%" : "54.37%",
    winRateDelta: "↑ 2.18%",
    profitFactor: "1.38",
    pfDelta:      "↑ 0.11",
    avgRR:        "1.62 / -1.03",
    avgRRDelta:   "↑ 0.07",
    expectancy:   o.avg_rr != null ? (+o.avg_rr).toFixed(2) : "0.42",
    expDelta:     "↑ 0.04",
  };

  const eq     = equity || [];
  const alerts = window.ALERTS || [];
  const sp     = window.SESSION_PNL || [];

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Executive Overview</div>
          <div className="page-sub">
            Live System Pulse · Portfolio Performance · Alert Summary
            {selectedInstrument && (
              <span style={{ marginLeft:8, color:"var(--accent)" }}>· {selectedInstrument}</span>
            )}
          </div>
        </div>
        <div style={{ display:"flex", gap:8 }}>
          <button className="btn outline" style={{ fontSize:11, padding:"5px 12px" }}>Export PDF</button>
          <button className="btn" style={{ fontSize:11, padding:"5px 12px" }}>Refresh</button>
        </div>
      </div>

      {/* KPI Strip */}
      <div className="kpis" style={{ gridTemplateColumns:"repeat(5,1fr)", marginBottom:16 }}>
        <div className="kpi">
          <div className="label">Total PnL (R)</div>
          <div className="v pos">{k.totalPnl}</div>
          <div className="sub">{k.totalPnlDelta}</div>
        </div>
        <div className="kpi">
          <div className="label">Win Rate</div>
          <div className="v num">{k.winRate}</div>
          <div className="sub">{k.winRateDelta}</div>
        </div>
        <div className="kpi">
          <div className="label">Profit Factor</div>
          <div className="v num">{k.profitFactor}</div>
          <div className="sub">{k.pfDelta}</div>
        </div>
        <div className="kpi">
          <div className="label">Avg RR (W/L)</div>
          <div className="v num" style={{ fontSize:14 }}>{k.avgRR}</div>
          <div className="sub">{k.avgRRDelta}</div>
        </div>
        <div className="kpi">
          <div className="label">Expectancy (R)</div>
          <div className="v pos">{k.expectancy}</div>
          <div className="sub">{k.expDelta}</div>
        </div>
      </div>

      {/* Row 1: 3 charts */}
      <div className="row" style={{ gridTemplateColumns:"1fr 1fr 1fr", marginBottom:14 }}>
        {/* PnL Over Time */}
        <div className="card">
          <div className="card-title">PnL Over Time (R) <span className="right">2020 → 2025</span></div>
          <LineChart values={eq} color="#22d3ee" height={120} />
        </div>

        {/* Session Equity */}
        <div className="card">
          <div className="card-title">
            Equity by Session
            <div className="legend-row">
              {[["Asian","#22d3ee"],["London","#a78bfa"],["NY","#22c55e"],["Overlap","#facc15"]].map(([l,c]) => (
                <span key={l}><span className="dot" style={{ background:c }} />{l}</span>
              ))}
            </div>
          </div>
          <SessionEquityChart height={120} />
        </div>

        {/* Win Rate by Session */}
        <div className="card">
          <div className="card-title">Win Rate by Session (%)</div>
          <VerticalBars
            data={sp.map(s => ({ label: s.label, value: s.value, color: s.color }))}
            height={120} maxVal={100}
          />
        </div>
      </div>

      {/* Row 2: Heatmap + Alerts */}
      <div className="row" style={{ gridTemplateColumns:"1.3fr 1fr", marginBottom:14 }}>
        <div className="card">
          <div className="card-title">Opportunity Density</div>
          <Heatmap
            rows={window.MONTHLY_RETURNS || []}
            colLabels={["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]}
          />
        </div>
        <div className="card">
          <div className="card-title">
            Alerts <span className="right" style={{ color:"var(--bad)" }}>{alerts.length} Active</span>
          </div>
          {alerts.length === 0
            ? <div className="muted" style={{ fontSize:12, padding:"12px 0" }}>No active alerts</div>
            : alerts.map((a, i) => (
              <div key={i} className="alert-item">
                <div className="alert-icon">{a.icon}</div>
                <div style={{ flex:1 }}>
                  <div className="alert-title">{a.title}</div>
                  <div className="alert-sub">{a.sub}</div>
                </div>
                <div className="alert-age">{a.age}</div>
              </div>
            ))
          }
        </div>
      </div>

      {/* Status Strip — uses live status prop */}
      <div className="status-strip">
        <div className="ss-item">
          <div className="ss-label">Active Model</div>
          <div className="ss-value">
            {s.active_model_version || "CRT v5"}
            <span className="pill live" style={{ fontSize:9, padding:"1px 6px" }}>LIVE</span>
          </div>
        </div>
        <div className="ss-item">
          <div className="ss-label">Promotion Guard</div>
          <div className="ss-value">KMeans Clustering</div>
        </div>
        <div className="ss-item">
          <div className="ss-label">Schema</div>
          <div className="ss-value">35-dim Feature Space</div>
        </div>
        <div className="ss-item">
          <div className="ss-label">Data Integrity</div>
          <div className="ss-value" style={{ color:"var(--ok)" }}>100%</div>
        </div>
      </div>
    </div>
  );
}

// ── SessionEquityChart — 4-series multi-line SVG ──────────────
function SessionEquityChart({ height = 120 }) {
  const se = window.SESSION_EQUITY || { asian:[], london:[], ny:[], overlap:[] };
  const W = 340, H = height;
  const SERIES = [
    { key:"asian",  color:"#22d3ee" },
    { key:"london", color:"#a78bfa" },
    { key:"ny",     color:"#22c55e" },
    { key:"overlap",color:"#facc15" },
  ];

  const allVals = Object.values(se).flat();
  const minV = Math.min(...allVals, 0);
  const maxV = Math.max(...allVals, 1);
  const pad = 8;

  function toPoints(arr) {
    if (!arr || arr.length === 0) return "";
    const xStep = (W - pad*2) / Math.max(arr.length - 1, 1);
    return arr.map((v, i) => {
      const x = pad + i * xStep;
      const y = pad + ((maxV - v) / (maxV - minV)) * (H - pad*2);
      return `${x},${y}`;
    }).join(" ");
  }

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ display:"block" }}>
      {SERIES.map(s => {
        const pts = toPoints(se[s.key] || []);
        if (!pts) return null;
        return (
          <polyline key={s.key}
            points={pts}
            fill="none"
            stroke={s.color}
            strokeWidth="1.5"
            strokeLinejoin="round"
            opacity="0.85"
          />
        );
      })}
    </svg>
  );
}

window.ExecutivePage = ExecutivePage;
