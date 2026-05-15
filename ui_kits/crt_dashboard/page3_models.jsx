// Page 3 — Models / Model Registry & Governance
// All 4 sub-tabs (Gaussian, Zone Gate, RR Miner, TradeNet) are functional.
// + Compare Models: select 2 versions within the active tab for side-by-side diff.

function ModelsPage() {
  const tabs = ["Gaussian Models", "Zone Gate Models", "RR Miner Models", "TradeNet Models"];
  const [activeTab, setActiveTab] = React.useState("Gaussian Models");

  // Local state for each model list — seeded from globals, refreshed after promote
  const [gaussianModels, setGaussianModels] = React.useState(window.MODELS || []);
  const [zoneModels,     setZoneModels]     = React.useState(window.ZONE_GATE_MODELS || []);
  const [rrModels,       setRrModels]       = React.useState(window.RR_MODELS || []);
  const [tradenetModels, setTradenetModels] = React.useState(window.TRADENET_MODELS || []);

  // Compare state
  const [selectedForCompare, setSelectedForCompare] = React.useState([]);
  const [showCompare,        setShowCompare]         = React.useState(false);

  // Clear selection when switching tabs
  React.useEffect(() => {
    setSelectedForCompare([]);
    setShowCompare(false);
  }, [activeTab]);

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

  // Toggle a version in/out of the compare selection (max 2)
  function toggleSelect(ver) {
    setSelectedForCompare(prev => {
      if (prev.includes(ver)) return prev.filter(v => v !== ver);
      if (prev.length >= 2) return prev; // max 2
      return [...prev, ver];
    });
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

  // Compare button label
  const compareBtnLabel =
    selectedForCompare.length === 0 ? "+ Compare Models" :
    selectedForCompare.length === 1 ? "Select 1 more to compare" :
                                      "Compare 2 Versions →";

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
          <button
            className={selectedForCompare.length === 2 ? "btn" : "btn outline"}
            style={{ opacity: selectedForCompare.length === 0 ? 0.5 : 1, minWidth: 170 }}
            onClick={() => selectedForCompare.length === 2 && setShowCompare(true)}
          >{compareBtnLabel}</button>
        </div>

        {/* ── Gaussian table ──────────────────────────────────────────── */}
        {activeTab === "Gaussian Models" && (
          <div className="card">
            <table className="dt">
              <thead>
                <tr>
                  <th style={{width:32}}></th>
                  <th>Model Version</th><th>Type</th><th>Corr (Expected RR)</th><th>Cal Error</th><th>Train Samples</th><th>Trained At</th><th>Status</th><th>Action</th>
                </tr>
              </thead>
              <tbody>
                {gaussianModels.map(m => (
                  <tr key={m.ver}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedForCompare.includes(m.ver)}
                        onChange={() => toggleSelect(m.ver)}
                        disabled={!selectedForCompare.includes(m.ver) && selectedForCompare.length >= 2}
                        style={{ cursor: "pointer", accentColor: "#a78bfa" }}
                      />
                    </td>
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
                <tr>
                  <th style={{width:32}}></th>
                  <th>Version</th><th>N Zones</th><th>N Clusters Req.</th><th>Trained At</th><th>Model File</th><th>File</th><th>Status</th><th>Action</th>
                </tr>
              </thead>
              <tbody>
                {zoneModels.map(m => (
                  <tr key={m.ver}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedForCompare.includes(m.ver)}
                        onChange={() => toggleSelect(m.ver)}
                        disabled={!selectedForCompare.includes(m.ver) && selectedForCompare.length >= 2}
                        style={{ cursor: "pointer", accentColor: "#a78bfa" }}
                      />
                    </td>
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
                <tr>
                  <th style={{width:32}}></th>
                  <th>Version</th><th>Samples</th><th>Features</th><th>Ridge α</th><th>Model</th><th>Trained At</th><th>Status</th><th>Action</th>
                </tr>
              </thead>
              <tbody>
                {rrModels.map(m => (
                  <tr key={m.ver}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedForCompare.includes(m.ver)}
                        onChange={() => toggleSelect(m.ver)}
                        disabled={!selectedForCompare.includes(m.ver) && selectedForCompare.length >= 2}
                        style={{ cursor: "pointer", accentColor: "#a78bfa" }}
                      />
                    </td>
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
                <tr>
                  <th style={{width:32}}></th>
                  <th>Version</th><th>Model File</th><th>Trained At</th><th>File</th><th>Status</th><th>Action</th>
                </tr>
              </thead>
              <tbody>
                {tradenetModels.map(m => (
                  <tr key={m.ver}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedForCompare.includes(m.ver)}
                        onChange={() => toggleSelect(m.ver)}
                        disabled={!selectedForCompare.includes(m.ver) && selectedForCompare.length >= 2}
                        style={{ cursor: "pointer", accentColor: "#a78bfa" }}
                      />
                    </td>
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

        {/* ── Compare modal ────────────────────────────────────────────── */}
        {showCompare && selectedForCompare.length === 2 && (
          <CompareModal
            activeTab={activeTab}
            activeModels={activeModels}
            selected={selectedForCompare}
            onClose={() => setShowCompare(false)}
            onPromote={(ver) => { promote(ver); setShowCompare(false); setSelectedForCompare([]); }}
          />
        )}

      </div>
    </div>
  );
}

// ── Compare Modal ─────────────────────────────────────────────────────────────
function CompareModal({ activeTab, activeModels, selected, onClose, onPromote }) {
  const [a, b] = selected.map(ver => activeModels.find(m => m.ver === ver) || {});

  const FIELDS = {
    "Gaussian Models": [
      { label: "Corr (Expected RR)", key: "corr",    fmt: v => v == null ? "—" : (v >= 0 ? "+" : "") + (+v).toFixed(4), better: "higher" },
      { label: "Cal Error",          key: "cal",     fmt: v => v == null ? "—" : (+v).toFixed(4),                        better: "lower"  },
      { label: "Train Samples",      key: "samples", fmt: v => v == null ? "—" : v.toLocaleString(),                     better: "higher" },
      { label: "Trained At",         key: "trained", fmt: v => v || "—",                                                  better: null     },
      { label: "Status",             key: "status",  fmt: v => v || "—",                                                  better: null     },
    ],
    "Zone Gate Models": [
      { label: "N Zones",          key: "nZones",    fmt: v => v ?? "—",                           better: "higher" },
      { label: "N Clusters Req.",  key: "nClusters", fmt: v => v ?? "—",                           better: null     },
      { label: "File OK",          key: "fileExists",fmt: v => v ? "✓ OK" : "✗ Missing",           better: null     },
      { label: "Trained At",       key: "trained",   fmt: v => v || "—",                           better: null     },
      { label: "Status",           key: "status",    fmt: v => v || "—",                           better: null     },
    ],
    "RR Miner Models": [
      { label: "Train Samples", key: "samples",     fmt: v => v == null ? "—" : v.toLocaleString(), better: "higher" },
      { label: "Features",      key: "features",    fmt: v => v ?? "—",                              better: null     },
      { label: "Ridge α",       key: "ridgeAlpha",  fmt: v => v ?? "—",                              better: null     },
      { label: "Model File",    key: "modelExists", fmt: v => v ? "✓ OK" : "✗ Missing",             better: null     },
      { label: "Trained At",    key: "trained",     fmt: v => v || "—",                              better: null     },
      { label: "Status",        key: "status",      fmt: v => v || "—",                              better: null     },
    ],
    "TradeNet Models": [
      { label: "Model File", key: "modelFile",  fmt: v => v || "—",                      better: null },
      { label: "File OK",    key: "fileExists", fmt: v => v ? "✓ OK" : "✗ Missing",     better: null },
      { label: "Trained At", key: "trained",    fmt: v => v || "—",                      better: null },
      { label: "Status",     key: "status",     fmt: v => v || "—",                      better: null },
    ],
  }[activeTab] || [];

  function winner(field, valA, valB) {
    if (field.better === "higher") return valA > valB ? "A" : valB > valA ? "B" : null;
    if (field.better === "lower")  return valA < valB ? "A" : valB < valA ? "B" : null;
    return null;
  }

  const canPromoteA = a && a.action === "Promote";
  const canPromoteB = b && b.action === "Promote";

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{ position:"fixed", inset:0, background:"rgba(0,0,0,0.55)", zIndex:300 }}
      />
      {/* Modal */}
      <div style={{
        position:"fixed", top:"50%", left:"50%", transform:"translate(-50%,-50%)",
        background:"#122033", border:"1px solid #23364e", borderRadius:10,
        padding:24, width:580, maxWidth:"95vw", maxHeight:"80vh",
        overflowY:"auto", zIndex:301,
      }}>
        {/* Header */}
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:14 }}>
          <div style={{ fontSize:14, fontWeight:700 }}>Compare — {activeTab}</div>
          <span onClick={onClose} style={{ cursor:"pointer", color:"#7f8da6", fontSize:18, lineHeight:1 }}>✕</span>
        </div>

        {/* Comparison table */}
        <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
          <thead>
            <tr>
              <th style={{ textAlign:"left", padding:"6px 8px", color:"#7f8da6", width:"34%" }}>Metric</th>
              <th style={{ textAlign:"center", padding:"6px 8px", color:"#a78bfa", width:"33%", borderBottom:"2px solid rgba(167,139,250,0.4)" }}>
                {a.ver || "—"}
                {a.status === "ACTIVE" && <span style={{ fontSize:9, marginLeft:5, color:"#22c55e" }}>LIVE</span>}
              </th>
              <th style={{ textAlign:"center", padding:"6px 8px", color:"#a78bfa", width:"33%", borderBottom:"2px solid rgba(167,139,250,0.4)" }}>
                {b.ver || "—"}
                {b.status === "ACTIVE" && <span style={{ fontSize:9, marginLeft:5, color:"#22c55e" }}>LIVE</span>}
              </th>
            </tr>
          </thead>
          <tbody>
            {FIELDS.map(field => {
              const valA = a[field.key];
              const valB = b[field.key];
              const w = winner(field, valA, valB);
              return (
                <tr key={field.label} style={{ borderTop:"1px solid #23364e" }}>
                  <td style={{ padding:"7px 8px", color:"#9fb0c8" }}>{field.label}</td>
                  <td style={{
                    padding:"7px 8px", textAlign:"center", fontFamily:"monospace",
                    background: w === "A" ? "rgba(34,197,94,0.12)" : "transparent",
                    color:      w === "A" ? "#22c55e" : "#e6edf7",
                  }}>
                    {field.fmt(valA)}{w === "A" && " ✓"}
                  </td>
                  <td style={{
                    padding:"7px 8px", textAlign:"center", fontFamily:"monospace",
                    background: w === "B" ? "rgba(34,197,94,0.12)" : "transparent",
                    color:      w === "B" ? "#22c55e" : "#e6edf7",
                  }}>
                    {field.fmt(valB)}{w === "B" && " ✓"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {/* Footer actions */}
        <div style={{ display:"flex", gap:8, marginTop:16, justifyContent:"flex-end" }}>
          {canPromoteA && (
            <button className="btn ghost" style={{ fontSize:11 }} onClick={() => onPromote(a.ver)}>
              Promote {a.ver}
            </button>
          )}
          {canPromoteB && (
            <button className="btn ghost" style={{ fontSize:11 }} onClick={() => onPromote(b.ver)}>
              Promote {b.ver}
            </button>
          )}
          <button className="btn outline" style={{ fontSize:11 }} onClick={onClose}>Close</button>
        </div>
      </div>
    </>
  );
}

window.ModelsPage = ModelsPage;
