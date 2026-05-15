// Page 3 — Models / Model Registry & Governance

function ModelsPage() {
  const tabs = ["Gaussian Models", "Zone Gate Models", "RR Miner Models", "TradeNet Models"];
  return (
    <div className="panel-frame">
      <Sidebar active="Models" footer={
        <div>
          <div className="muted" style={{ marginBottom: 6 }}>Model Registry</div>
          <div style={{ color: "#22d3ee" }}>v5 Schema</div>
          <div className="muted" style={{ marginTop: 4 }}>35 Features</div>
        </div>
      } />
      <div className="body">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
          <div style={{ display: "flex", gap: 8 }}>
            {tabs.map((t, i) => (
              <span key={t} style={{
                fontSize: 12, padding: "6px 12px", borderRadius: 6,
                background: i === 0 ? "rgba(167,139,250,0.15)" : "transparent",
                color: i === 0 ? "#a78bfa" : "#7f8da6",
                border: i === 0 ? "1px solid rgba(167,139,250,0.35)" : "1px solid transparent",
                fontWeight: i === 0 ? 600 : 400,
              }}>{t}</span>
            ))}
          </div>
          <button className="btn">+ Compare Models</button>
        </div>

        <div className="card">
          <table className="dt">
            <thead>
              <tr><th>Model Version</th><th>Type</th><th>Corr (Expected RR)</th><th>Cal Error</th><th>Train Samples</th><th>Trained At</th><th>Status</th><th>Action</th></tr>
            </thead>
            <tbody>
              {MODELS.map(m => (
                <tr key={m.ver}>
                  <td>{m.ver}</td>
                  <td className="muted">{m.type}</td>
                  <td className={`mono ${m.corr >= 0 ? "pos" : "neg"}`}>{m.corr >= 0 ? "+" : ""}{m.corr.toFixed(4)}</td>
                  <td className={`mono ${m.cal < 0.05 ? "pos" : m.cal < 0.1 ? "" : "neg"}`}>{m.cal.toFixed(4)}</td>
                  <td className="mono">{m.samples === null ? "—" : m.samples}</td>
                  <td className="mono">{m.trained}</td>
                  <td><StatusPill status={m.status} /></td>
                  <td><button className={m.action === "Promote" ? "btn ghost" : "btn outline"} style={{ padding: "4px 14px", fontSize: 11 }}>{m.action}</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card" style={{ marginTop: 12 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 18 }}>
            <div>
              <div className="muted" style={{ fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 4 }}>Active Model</div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontWeight: 700, fontSize: 15 }}>v4_mirrored</span>
                <span className="tag tp" style={{ fontSize: 10 }}>LIVE</span>
              </div>
            </div>
            <div>
              <div className="muted" style={{ fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 4 }}>Promotion Guard</div>
              <div style={{ fontSize: 12 }}>Min Corr: 0.150</div>
              <div style={{ fontSize: 12 }}>Min Samples: 1,000</div>
            </div>
            <div>
              <div className="muted" style={{ fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 4 }}>Schema</div>
              <div style={{ fontSize: 12 }}>v5 (35 Features)</div>
            </div>
            <div>
              <div className="muted" style={{ fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 4 }}>Lineage</div>
              <div style={{ fontSize: 12 }}>Trained from: SCAN-1582</div>
              <div style={{ fontSize: 12 }}>Parent: v2_gaussian_2026_05</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
window.ModelsPage = ModelsPage;
