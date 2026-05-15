// Page 3 — Models / Model Registry & Governance
// All 4 sub-tabs (Gaussian, Zone Gate, RR Miner, TradeNet) are functional.

function ModelsPage() {
  const tabs = ["Gaussian Models", "Zone Gate Models", "RR Miner Models", "TradeNet Models"];
  const [activeTab, setActiveTab] = React.useState("Gaussian Models");

  // Local state for each model list — seeded from globals, refreshed after promote
  const [gaussianModels, setGaussianModels] = React.useState(window.MODELS || []);
  const [zoneModels,     setZoneModels]     = React.useState(window.ZONE_GATE_MODELS || []);
  const [rrModels,       setRrModels]       = React.useState(window.RR_MODELS || []);
  const [tradenetModels, setTradenetModels] = React.useState(window.TRADENET_MODELS || []);

  const API = "http://localhost:8787";

  // Mapping helpers — same shape as realData.js
  function mapGaussian(m)  { return { ver: m.version||"—", type:"Gaussian (ML)", corr:+(m.corr_expected_rr||0), cal:+(m.calibration_error||0), samples:m.n_train, trained:(m.trained_at||"—").slice(0,10), status:m.active?"ACTIVE":"Archived", action:m.active?"Active":"Promote" }; }
  function mapZoneGate(m)  { return { ver: m.version||"—", nZones:m.n_zones||0, nClusters:m.n_clusters_requested||0, trained:(m.trained_at||"—").slice(0,10), modelFile:(m.model_file||"").split(/[\\/]/).pop()||"—", fileExists:!!m.file_exists, status:m.active?"ACTIVE":"Archived", action:m.active?"Active":"Promote" }; }
  function mapRR(m)        { return { ver: m.version||"—", samples:m.n_samples, features:m.n_features||35, ridgeAlpha:m.ridge_alpha, modelExists:!!m.model_exists, trained:(m.trained_at||"—").slice(0,10), status:m.active?"ACTIVE":"Archived", action:m.active?"Active":"Promote" }; }
  function mapTradeNet(m)  { return { ver: m.version||"—", modelFile:(m.model_file||"").split(/[\\/]/).pop()||"—", trained:(m.trained_at||"—").slice(0,10), fileExists:!!m.file_exists, status:m.active?"ACTIVE":"Archived", action:m.active?"Active":"Promote" }; }

  const TAB_CFG = {
    "Gaussian Models":  { postEp: "/api/promote_model",    getEp: "/api/models",          setter: setGaussianModels, mapFn: mapGaussian  },
    "Zone Gate Models": { postEp: "/api/promote_zone_gate", getEp: "/api/zone_gate_models", setter: setZoneModels,     mapFn: mapZoneGate  },
    "RR Miner Models":  { postEp: "/api/promote_rr",        getEp: "/api/rr_models",        setter: setRrModels,       mapFn: mapRR        },
    "TradeNet Models":  { postEp: "/api/promote_tradenet",  getEp: "/api/tradenet_models",  setter: setTradenetModels, mapFn: mapTradeNet  },
  };

  function promote(version) {
    const cfg = TAB_CFG[activeTab];
    if (!cfg) return;
    fetch(API + cfg.postEp, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ version }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.ok) {
          fetch(API + cfg.getEp)
            .then(r => r.json())
            .then(data => cfg.setter((data.models || []).map(cfg.mapFn)));
        } else {
          alert("Promote failed: " + (d.reason || d.error || "unknown"));
        }
      })
      .catch(e => alert("Promote error: " + e.message));
  }

  const activeModels = {
    "Gaussian Models":  gaussianModels,
    "Zone Gate Models": zoneModels,
    "RR Miner Models":  rrModels,
    "TradeNet Models":  tradenetModels,
  }[activeTab] || [];

  const activeEntry = activeModels.find(m => m.status === "ACTIVE");

  const FOOTER = {
    "Gaussian Models":  { guard: "Min Corr: 0.150 · Min Samples: 1,000", schema: "v5 (35 Features)" },
    "Zone Gate Models": { guard: "KMeans clustering",                     schema: "35-dim feature space" },
    "RR Miner Models":  { guard: "Ridge + GaussianNB",                    schema: "35 Features" },
    "TradeNet Models":  { guard: "Ternary neural net",                    schema: "35 Features (PTH)" },
  }[activeTab];

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

        {/* ── Sub-tab bar ──────────────────────────────────────────────── */}
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:10 }}>
          <div style={{ display:"flex", gap:8 }}>
            {tabs.map(t => (
              <span key={t} onClick={() => setActiveTab(t)} style={{
                fontSize: 12, padding: "6px 12px", borderRadius: 6, cursor: "pointer",
                background: t === activeTab ? "rgba(167,139,250,0.15)" : "transparent",
                color:      t === activeTab ? "#a78bfa" : "#7f8da6",
                border:     t === activeTab ? "1px solid rgba(167,139,250,0.35)" : "1px solid transparent",
                fontWeight: t === activeTab ? 600 : 400,
              }}>{t}</span>
            ))}
          </div>
          <button className="btn">+ Compare Models</button>
        </div>

        {/* ── Gaussian table ──────────────────────────────────────────── */}
        {activeTab === "Gaussian Models" && (
          <div className="card">
            <table className="dt">
              <thead>
                <tr><th>Model Version</th><th>Type</th><th>Corr (Expected RR)</th><th>Cal Error</th><th>Train Samples</th><th>Trained At</th><th>Status</th><th>Action</th></tr>
              </thead>
              <tbody>
                {gaussianModels.map(m => (
                  <tr key={m.ver}>
                    <td>{m.ver}</td>
                    <td className="muted">{m.type}</td>
                    <td className={`mono ${m.corr >= 0 ? "pos" : "neg"}`}>{m.corr >= 0 ? "+" : ""}{m.corr.toFixed(4)}</td>
                    <td className={`mono ${m.cal < 0.05 ? "pos" : m.cal < 0.1 ? "" : "neg"}`}>{m.cal.toFixed(4)}</td>
                    <td className="mono">{m.samples == null ? "—" : m.samples}</td>
                    <td className="mono">{m.trained}</td>
                    <td><StatusPill status={m.status} /></td>
                    <td>
                      <button
                        className={m.action === "Promote" ? "btn ghost" : "btn outline"}
                        style={{ padding:"4px 14px", fontSize:11 }}
                        onClick={() => m.action === "Promote" && promote(m.ver)}
                      >{m.action}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ── Zone Gate table ─────────────────────────────────────────── */}
        {activeTab === "Zone Gate Models" && (
          <div className="card">
            <table className="dt">
              <thead>
                <tr><th>Version</th><th>N Zones</th><th>N Clusters Req.</th><th>Trained At</th><th>Model File</th><th>File</th><th>Status</th><th>Action</th></tr>
              </thead>
              <tbody>
                {zoneModels.map(m => (
                  <tr key={m.ver}>
                    <td>{m.ver}</td>
                    <td className="mono">{m.nZones}</td>
                    <td className="mono">{m.nClusters}</td>
                    <td className="mono">{m.trained}</td>
                    <td className="muted" style={{fontSize:11,maxWidth:180,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{m.modelFile}</td>
                    <td className={`mono ${m.fileExists ? "pos" : "neg"}`}>{m.fileExists ? "OK" : "Missing"}</td>
                    <td><StatusPill status={m.status} /></td>
                    <td>
                      <button
                        className={m.action === "Promote" ? "btn ghost" : "btn outline"}
                        style={{ padding:"4px 14px", fontSize:11 }}
                        onClick={() => m.action === "Promote" && promote(m.ver)}
                      >{m.action}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ── RR Miner table ──────────────────────────────────────────── */}
        {activeTab === "RR Miner Models" && (
          <div className="card">
            <table className="dt">
              <thead>
                <tr><th>Version</th><th>Samples</th><th>Features</th><th>Ridge α</th><th>Model</th><th>Trained At</th><th>Status</th><th>Action</th></tr>
              </thead>
              <tbody>
                {rrModels.map(m => (
                  <tr key={m.ver}>
                    <td>{m.ver}</td>
                    <td className="mono">{m.samples != null ? m.samples.toLocaleString() : "—"}</td>
                    <td className="mono">{m.features}</td>
                    <td className="mono">{m.ridgeAlpha != null ? m.ridgeAlpha : "—"}</td>
                    <td className={`mono ${m.modelExists ? "pos" : "neg"}`}>{m.modelExists ? "OK" : "Missing"}</td>
                    <td className="mono">{m.trained}</td>
                    <td><StatusPill status={m.status} /></td>
                    <td>
                      <button
                        className={m.action === "Promote" ? "btn ghost" : "btn outline"}
                        style={{ padding:"4px 14px", fontSize:11 }}
                        onClick={() => m.action === "Promote" && promote(m.ver)}
                      >{m.action}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ── TradeNet table ──────────────────────────────────────────── */}
        {activeTab === "TradeNet Models" && (
          <div className="card">
            <table className="dt">
              <thead>
                <tr><th>Version</th><th>Model File</th><th>Trained At</th><th>File</th><th>Status</th><th>Action</th></tr>
              </thead>
              <tbody>
                {tradenetModels.map(m => (
                  <tr key={m.ver}>
                    <td>{m.ver}</td>
                    <td className="muted" style={{fontSize:11,maxWidth:220,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{m.modelFile}</td>
                    <td className="mono">{m.trained}</td>
                    <td className={`mono ${m.fileExists ? "pos" : "neg"}`}>{m.fileExists ? "OK" : "Missing"}</td>
                    <td><StatusPill status={m.status} /></td>
                    <td>
                      <button
                        className={m.action === "Promote" ? "btn ghost" : "btn outline"}
                        style={{ padding:"4px 14px", fontSize:11 }}
                        onClick={() => m.action === "Promote" && promote(m.ver)}
                      >{m.action}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ── Footer info card ────────────────────────────────────────── */}
        <div className="card" style={{ marginTop: 12 }}>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr 1fr", gap:18 }}>
            <div>
              <div className="muted" style={{ fontSize:10, letterSpacing:"0.08em", textTransform:"uppercase", marginBottom:4 }}>Active Model</div>
              <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                <span style={{ fontWeight:700, fontSize:15 }}>{activeEntry ? activeEntry.ver : "—"}</span>
                {activeEntry && <span className="tag tp" style={{ fontSize:10 }}>LIVE</span>}
              </div>
            </div>
            <div>
              <div className="muted" style={{ fontSize:10, letterSpacing:"0.08em", textTransform:"uppercase", marginBottom:4 }}>Promotion Guard</div>
              <div style={{ fontSize:12 }}>{FOOTER.guard}</div>
            </div>
            <div>
              <div className="muted" style={{ fontSize:10, letterSpacing:"0.08em", textTransform:"uppercase", marginBottom:4 }}>Schema</div>
              <div style={{ fontSize:12 }}>{FOOTER.schema}</div>
            </div>
            <div>
              <div className="muted" style={{ fontSize:10, letterSpacing:"0.08em", textTransform:"uppercase", marginBottom:4 }}>Total Versions</div>
              <div style={{ fontSize:12 }}>{activeModels.length} version{activeModels.length !== 1 ? "s" : ""} in registry</div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
window.ModelsPage = ModelsPage;
