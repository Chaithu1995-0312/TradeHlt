// Page 6 — System / System Health & Data Status

function SystemPage() {
  const k = SYS_KPIS;
  return (
    <div className="panel-frame">
      <Sidebar active="System" footer={
        <div>
          <div className="muted" style={{ marginBottom: 6 }}>System Status</div>
          <div><span className="dot" style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", background: "#22c55e", marginRight: 6, boxShadow: "0 0 6px #34d399" }} />HEALTHY</div>
        </div>
      } />
      <div className="body">
        <div className="kpis" style={{ gridTemplateColumns: "repeat(5, 1fr)" }}>
          <Kpi label="Data Feeds"   tone="num" value={k.dataFeeds.value} sub={k.dataFeeds.sub} />
          <Kpi label="Last Data"    value={k.lastData.value} sub={k.lastData.sub} />
          <Kpi label="Storage Used" value={k.storage.value} sub={k.storage.sub} />
          <Kpi label="Jobs Running" tone="num" value={k.jobsRunning.value} sub={k.jobsRunning.sub} />
          <Kpi label="Alerts"       tone="pos" value={k.alerts.value} sub={k.alerts.sub} />
        </div>

        <div className="row" style={{ gridTemplateColumns: "1fr 1.4fr 0.9fr" }}>
          <div className="card">
            <div className="card-title">Data Integrity</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {DATA_INTEGRITY.map(d => (
                <div key={d.name} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12 }}>
                  <span><CheckIcon /> <span style={{ marginLeft: 6, color: "#b6c0d6" }}>{d.name}</span></span>
                  <span className="pos mono" style={{ fontWeight: 600 }}>{d.value}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="card-title">Recent Jobs</div>
            <table className="dt">
              <thead><tr><th>Job ID</th><th>Type</th><th>Start Time</th><th>Status</th></tr></thead>
              <tbody>
                {RECENT_JOBS.map(j => (
                  <tr key={j.id}>
                    <td className="mono">{j.id}</td>
                    <td style={{ color: "#22d3ee" }}>{j.type}</td>
                    <td className="mono">{j.time}</td>
                    <td><CheckIcon /> <span className="pos" style={{ marginLeft: 6 }}>{j.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card" style={{ textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
            <div className="card-title" style={{ width: "100%", textAlign: "left" }}>System Alerts</div>
            <div style={{ width: 64, height: 64, borderRadius: "50%", background: "rgba(34,197,94,0.15)", display: "flex", alignItems: "center", justifyContent: "center", margin: "8px 0" }}>
              <CheckIcon tone="#22c55e" size={36} />
            </div>
            <div style={{ fontSize: 14, fontWeight: 700 }}>No Active Alerts</div>
            <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>All systems operational</div>
          </div>
        </div>

        <div className="card" style={{ marginTop: 12 }}>
          <div className="card-title">Quick Links</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 8 }}>
            {[
              { l: "View Logs", i: "M5 4 H12 L15 7 V16 H5 Z" },
              { l: "Data Explorer", i: "M4 10 A6 3 0 1 0 16 10 A6 3 0 1 0 4 10 M4 10 V14 A6 3 0 0 0 16 14 V10" },
              { l: "Model Registry", i: "M5 5 H15 V15 H5 Z M5 9 H15" },
              { l: "Job Monitor", i: "M10 4 V10 L13 12 M10 4 A6 6 0 1 1 4 10" },
              { l: "Config", i: "M10 6 V14 M6 10 H14" },
              { l: "Documentation", i: "M5 5 H13 L15 7 V16 H5 Z M7 9 H13 M7 12 H13" },
            ].map(b => (
              <button key={b.l} className="btn outline" style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 6, padding: "8px 10px", fontWeight: 500 }}>
                <svg width="14" height="14" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d={b.i} /></svg>
                {b.l}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
window.SystemPage = SystemPage;
