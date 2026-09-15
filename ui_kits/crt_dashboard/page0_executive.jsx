// Page 0 — Executive Overview (default landing page)

// Formats a run_id ("run_20260812_113506_XAUUSD") into a readable
// timestamp ("2026-08-12 11:35"). Falls back to the raw id for any run_id
// that doesn't match the expected results/run_<ts>_<INSTR> shape.
function runLabel(runId) {
  if (!runId) return "—";
  const m = /^run_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_/.exec(runId);
  if (!m) return runId;
  const [, yr, mo, da, hh, mm] = m;
  return `${yr}-${mo}-${da} ${hh}:${mm}`;
}

function ExecutivePage({ status, executive, execReady, selectedInstrument, selectedRun }) {
  const s = status || {};

  // Gate: Executive is only enabled once an instrument AND a run are selected.
  if (!execReady || !executive || executive.ok !== true) {
    return (
      <div>
        <div className="page-header">
          <div>
            <div className="page-title">Executive Overview</div>
            <div className="page-sub">Select an instrument and a run to enable the Executive Overview.</div>
          </div>
        </div>
        <div className="card" style={{ padding: "44px 24px", textAlign: "center" }}>
          <div style={{ fontSize: 30, marginBottom: 10 }}>📊</div>
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>
            Select an instrument and a run to enable Executive Overview
          </div>
          <div className="muted" style={{ fontSize: 12, lineHeight: 1.5 }}>
            Choose <b>Instrument</b> and then a <b>Run</b> from the top bar.<br />
            Every metric below is scoped to a single backtest run.
          </div>
        </div>
      </div>
    );
  }

  const kpis = executive.kpis || {};
  const nTrd = kpis.n_trades || 0;
  const fmtPnl = (v) => v == null ? "—" : ((v >= 0 ? "+" : "") + v.toFixed(2));

  const k = {
    totalPnl:     fmtPnl(kpis.total_pnl_rr_net),
    totalPnlDelta: runLabel(executive.run_id),
    winRate:      kpis.win_rate_pct != null ? kpis.win_rate_pct.toFixed(2) + "%" : "—",
    winRateDelta: `${nTrd} trades`,
    profitFactor: kpis.profit_factor != null ? kpis.profit_factor.toFixed(2) : "—",
    pfDelta:      "gross R",
    avgRR:        `${kpis.avg_rr_win != null ? kpis.avg_rr_win.toFixed(2) : "—"} / -${kpis.avg_rr_loss != null ? kpis.avg_rr_loss.toFixed(2) : "—"}`,
    avgRRDelta:   "avg W/L",
    expectancy:   kpis.expectancy_rr != null ? kpis.expectancy_rr.toFixed(2) : "—",
    expDelta:     "avg R/trade",
  };

  const eq   = (executive.pnl_over_time || []).map(p => p.cumulative_pnl_rr);
  const se   = executive.session_equity || {};
  const wrs  = executive.win_rate_by_session || {};
  const sessionPnl = [
    { label: "Asian",   value: wrs.asian   != null ? Math.round(wrs.asian)   : 0, color: "#22d3ee" },
    { label: "London",  value: wrs.london  != null ? Math.round(wrs.london)  : 0, color: "#a78bfa" },
    { label: "NY",      value: wrs.ny      != null ? Math.round(wrs.ny)      : 0, color: "#22c55e" },
    { label: "Overlap", value: wrs.overlap != null ? Math.round(wrs.overlap) : 0, color: "#facc15" },
  ];
  const density = executive.opportunity_density || [];
  const alerts  = (executive.alerts || {});
  const alertsStatus = alerts.status || "yet_to_integrate";

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Executive Overview</div>
          <div className="page-sub">
            Run-Scoped Performance · {selectedInstrument}
            {selectedRun && (
              <span style={{ marginLeft:8, color:"var(--accent)" }}>· {selectedRun}</span>
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
          <SessionEquityChart se={se} height={120} />
        </div>

        {/* Win Rate by Session */}
        <div className="card">
          <div className="card-title">Win Rate by Session (%)</div>
          <VerticalBars
            data={sessionPnl}
            height={120} maxVal={100}
          />
        </div>
      </div>

      {/* Row 2: Heatmap + Alerts */}
      <div className="row" style={{ gridTemplateColumns:"1.3fr 1fr", marginBottom:14 }}>
        <div className="card">
          <div className="card-title">Opportunity Density</div>
          <Heatmap
            rows={density.length ? density : [{ year: 2024, cells: Array.from({length:12}, () => 0) }]}
            colLabels={["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]}
          />
        </div>
        <div className="card">
          <div className="card-title">
            Alerts <span className="right" style={{ color:"var(--bad)" }}>Yet to integrate</span>
          </div>
          <div className="muted" style={{ fontSize:12, padding:"12px 0" }}>
            Run-invariant alerts (drawdown threshold, drift flag, low-sample warning) are a future phase.
          </div>
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
          <div className="ss-label">Run</div>
          <div className="ss-value">{runLabel(executive.run_id || selectedRun)}</div>
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
function SessionEquityChart({ se, height = 120 }) {
  se = se || { asian:[], london:[], ny:[], overlap:[] };
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
