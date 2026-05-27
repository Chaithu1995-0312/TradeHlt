// Page 3 — Models / Model Registry & Governance
// All 4 sub-tabs (Gaussian, Zone Gate, RR Miner, TradeNet) are functional.
// + Compare Models: select 2 versions within the active tab for side-by-side diff.

function ModelsPage({ activeSub, models, zoneModels, rrModels, tradenetModels, setModels, setZoneModels, setRrModels, setTradenetModels, selectedInstrument }) {
  const ALL_TABS = [
    "Gaussian Models","Zone Gate Models","RR Miner Models","TradeNet Models",
    "Lineage Graph","Drift Monitor","Shadow Compare","Promotions",
  ];

  // Sync sub from sidebar click (Lineage → "Lineage Graph", etc.)
  const SUB_TO_TAB = {
    Lineage:"Lineage Graph", DriftMonitor:"Drift Monitor",
    ShadowCompare:"Shadow Compare", Promotions:"Promotions",
  };
  const [activeTab, setActiveTab] = React.useState(() => SUB_TO_TAB[activeSub] || "Gaussian Models");

  // Model lists come from app.jsx runtime store via props (no local state needed)
  const gaussianModels = models        || [];
  const zoneGateModels = zoneModels    || [];
  const rrMinerModels  = rrModels      || [];
  const tradenetMdls   = tradenetModels|| [];

  // Compare state
  const [selectedForCompare, setSelectedForCompare] = React.useState([]);
  const [showCompare,        setShowCompare]         = React.useState(false);

  // View state
  const [viewModel,   setViewModel]   = React.useState(null);
  const [viewLoading, setViewLoading] = React.useState(false);

  // Clear selection when switching tabs
  React.useEffect(() => {
    setSelectedForCompare([]);
    setShowCompare(false);
  }, [activeTab]);

  const API = "http://localhost:8787";

  // Mapping helpers — same shape as realData.js (preserve run_id + instrument for grouping)
  function mapGaussian(m)  { return { ver: m.version||"—", type:"Gaussian (ML)", corr:+(m.corr_expected_rr||0), cal:+(m.calibration_error||0), samples:m.n_train, trained:(m.trained_at||"—").slice(0,10), status:m.active?"ACTIVE":"Archived", action:m.active?"Active":"Promote", run_id:m.run_id||null, instrument:m.instrument||null }; }
  function mapZoneGate(m)  { return { ver: m.version||"—", nZones:m.n_zones||0, nClusters:m.n_clusters_requested||0, trained:(m.trained_at||"—").slice(0,10), modelFile:(m.model_file||"").split(/[\\/]/).pop()||"—", fileExists:!!m.file_exists, status:m.active?"ACTIVE":"Archived", action:m.active?"Active":"Promote", run_id:m.run_id||null, instrument:m.instrument||null }; }
  function mapRR(m)        { return { ver: m.version||"—", samples:m.n_samples, features:m.n_features||35, ridgeAlpha:m.ridge_alpha, modelExists:!!m.model_exists, trained:(m.trained_at||"—").slice(0,10), status:m.active?"ACTIVE":"Archived", action:m.active?"Active":"Promote", run_id:m.run_id||null, instrument:m.instrument||null }; }
  function mapTradeNet(m)  { return { ver: m.version||"—", modelFile:(m.model_file||"").split(/[\\/]/).pop()||"—", trained:(m.trained_at||"—").slice(0,10), fileExists:!!m.file_exists, status:m.active?"ACTIVE":"Archived", action:m.active?"Active":"Promote", run_id:m.run_id||null, instrument:m.instrument||null }; }

  // Setters come from app.jsx runtime store via props
  const TAB_CFG = {
    "Gaussian Models":  { postEp: "/api/promote_model",    getEp: "/api/models",          setter: setModels,         mapFn: mapGaussian,  type: "gaussian"  },
    "Zone Gate Models": { postEp: "/api/promote_zone_gate", getEp: "/api/zone_gate_models", setter: setZoneModels,     mapFn: mapZoneGate,  type: "zone_gate" },
    "RR Miner Models":  { postEp: "/api/promote_rr",        getEp: "/api/rr_models",        setter: setRrModels,       mapFn: mapRR,        type: "rr"        },
    "TradeNet Models":  { postEp: "/api/promote_tradenet",  getEp: "/api/tradenet_models",  setter: setTradenetModels, mapFn: mapTradeNet,  type: "tradenet"  },
  };

  // ── Collapsible groups ───────────────────────────────────────────────────
  const [collapsedGroups, setCollapsedGroups] = React.useState({});
  function toggleGroup(key) {
    setCollapsedGroups(prev => ({ ...prev, [key]: !prev[key] }));
  }

  // Build grouped structure from a flat model list
  function groupModels(list) {
    const groups = {};
    list.forEach(m => {
      const inst   = m.instrument || "—";
      const run    = m.run_id     || null;
      const key    = inst + "/" + (run || "legacy");
      if (!groups[key]) groups[key] = { instrument: inst, run_id: run, models: [] };
      groups[key].models.push(m);
    });
    // Sort: newest run first, legacy last
    const sorted = Object.keys(groups).sort((a, b) => {
      if (a.endsWith("/legacy") && !b.endsWith("/legacy")) return 1;
      if (!a.endsWith("/legacy") && b.endsWith("/legacy")) return -1;
      return b.localeCompare(a);
    });
    return sorted.map(k => ({ key: k, ...groups[k] }));
  }

  // Filter model list to the currently selected instrument (keep legacy/untagged always)
  function filterByInstrument(list) {
    if (!selectedInstrument) return list;
    return list.filter(m => !m.instrument || m.instrument === selectedInstrument);
  }

  // ── Groq Explain state ───────────────────────────────────────────────────
  const [explainResult,  setExplainResult]  = React.useState(null);
  const [explainLoading, setExplainLoading] = React.useState(false);

  function openExplain(ver) {
    const cfg = TAB_CFG[activeTab];
    if (!cfg) return;
    setExplainResult(null);
    setExplainLoading(true);
    window.ApiClient.explainModel(cfg.type, ver)
      .then(d  => { setExplainResult(d);                         setExplainLoading(false); })
      .catch(e => { setExplainResult({ ok:false, error:String(e) }); setExplainLoading(false); });
  }

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

  function openView(ver) {
    const cfg = TAB_CFG[activeTab];
    if (!cfg) return;
    setViewLoading(true);
    fetch(API + cfg.getEp)
      .then(r => r.json())
      .then(data => {
        const list = data.models || [];
        const entry = list.find(m => (m.version || m.ver) === ver) || {};
        setViewModel({ ver, type: activeTab, rawData: entry });
      })
      .catch(() => setViewModel({ ver, type: activeTab, rawData: {} }))
      .finally(() => setViewLoading(false));
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
    "Zone Gate Models": zoneGateModels,
    "RR Miner Models":  rrMinerModels,
    "TradeNet Models":  tradenetMdls,
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
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Models / Model Registry &amp; Governance</div>
          <div className="page-sub">Model Catalog · Performance · Promotion · Lineage</div>
        </div>
      </div>

        {/* ── Sub-tab bar ──────────────────────────────────────────────── */}
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:10, flexWrap:"wrap", gap:6 }}>
          <div style={{ display:"flex", gap:6, flexWrap:"wrap" }}>
            {ALL_TABS.map(t => (
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
                {groupModels(filterByInstrument(gaussianModels)).map(g => (
                  <React.Fragment key={g.key}>
                    <tr className="model-group-header" onClick={() => toggleGroup(g.key)} style={{
                      padding:"8px 12px", background:"var(--panel-2)",
                      borderLeft:"3px solid var(--accent)", cursor:"pointer",
                    }}>
                      <td colSpan={9} style={{ padding:"7px 12px", fontSize:12 }}>
                        <span style={{ marginRight:8 }}>{collapsedGroups[g.key] ? "▶" : "▼"}</span>
                        <span style={{ color:"var(--accent)", fontWeight:600 }}>{g.instrument}</span>
                        {g.run_id
                          ? <span className="muted" style={{ marginLeft:8 }}>
                              · Run {g.run_id} · {g.run_id.slice(0,4)}-{g.run_id.slice(4,6)}-{g.run_id.slice(6,8)} {g.run_id.length >= 15 ? g.run_id.slice(9,11)+":"+g.run_id.slice(11,13) : ""}
                            </span>
                          : <span className="muted" style={{ marginLeft:8 }}>· Legacy (no run link)</span>
                        }
                        <span className="muted" style={{ marginLeft:8 }}>· {g.models.length} model{g.models.length !== 1 ? "s" : ""}</span>
                      </td>
                    </tr>
                    {!collapsedGroups[g.key] && g.models.map(m => (
                      <tr key={m.ver}>
                        <td>
                          <input type="checkbox" checked={selectedForCompare.includes(m.ver)} onChange={() => toggleSelect(m.ver)}
                            disabled={!selectedForCompare.includes(m.ver) && selectedForCompare.length >= 2}
                            style={{ cursor:"pointer", accentColor:"#a78bfa" }} />
                        </td>
                        <td>{m.ver}</td>
                        <td className="muted">{m.type}</td>
                        <td className={`mono ${m.corr >= 0 ? "pos" : "neg"}`}>{m.corr >= 0 ? "+" : ""}{m.corr.toFixed(4)}</td>
                        <td className={`mono ${m.cal < 0.05 ? "pos" : m.cal < 0.1 ? "" : "neg"}`}>{m.cal.toFixed(4)}</td>
                        <td className="mono">{m.samples == null ? "—" : m.samples}</td>
                        <td className="mono">{m.trained}</td>
                        <td><StatusPill status={m.status} /></td>
                        <td style={{ display:"flex", gap:4, alignItems:"center", flexWrap:"wrap" }}>
                          <button className="btn outline" style={{ padding:"3px 8px", fontSize:10 }} onClick={() => openView(m.ver)} disabled={viewLoading}>View</button>
                          <button className={m.action === "Promote" ? "btn ghost" : "btn outline"} style={{ padding:"3px 10px", fontSize:10 }} onClick={() => m.action === "Promote" && promote(m.ver)}>{m.action}</button>
                          <button className="btn outline" style={{ padding:"3px 8px", fontSize:10, borderColor:"rgba(34,211,238,.3)", color:"var(--accent)" }} onClick={() => openExplain(m.ver)} title="AI Explain">🤖 Explain</button>
                        </td>
                      </tr>
                    ))}
                  </React.Fragment>
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
                {groupModels(filterByInstrument(zoneGateModels)).map(g => (
                  <React.Fragment key={g.key}>
                    <tr className="model-group-header" onClick={() => toggleGroup(g.key)} style={{ background:"var(--panel-2)", borderLeft:"3px solid var(--accent)", cursor:"pointer" }}>
                      <td colSpan={9} style={{ padding:"7px 12px", fontSize:12 }}>
                        <span style={{ marginRight:8 }}>{collapsedGroups[g.key] ? "▶" : "▼"}</span>
                        <span style={{ color:"var(--accent)", fontWeight:600 }}>{g.instrument}</span>
                        {g.run_id ? <span className="muted" style={{ marginLeft:8 }}>· Run {g.run_id}</span> : <span className="muted" style={{ marginLeft:8 }}>· Legacy</span>}
                        <span className="muted" style={{ marginLeft:8 }}>· {g.models.length} model{g.models.length !== 1 ? "s" : ""}</span>
                      </td>
                    </tr>
                    {!collapsedGroups[g.key] && g.models.map(m => (
                      <tr key={m.ver}>
                        <td><input type="checkbox" checked={selectedForCompare.includes(m.ver)} onChange={() => toggleSelect(m.ver)} disabled={!selectedForCompare.includes(m.ver) && selectedForCompare.length >= 2} style={{ cursor:"pointer", accentColor:"#a78bfa" }} /></td>
                        <td>{m.ver}</td>
                        <td className="mono">{m.nZones}</td>
                        <td className="mono">{m.nClusters}</td>
                        <td className="mono">{m.trained}</td>
                        <td className="muted" style={{fontSize:11,maxWidth:180,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{m.modelFile}</td>
                        <td className={`mono ${m.fileExists ? "pos" : "neg"}`}>{m.fileExists ? "OK" : "Missing"}</td>
                        <td><StatusPill status={m.status} /></td>
                        <td style={{ display:"flex", gap:4, alignItems:"center", flexWrap:"wrap" }}>
                          <button className="btn outline" style={{ padding:"3px 8px", fontSize:10 }} onClick={() => openView(m.ver)} disabled={viewLoading}>View</button>
                          <button className={m.action === "Promote" ? "btn ghost" : "btn outline"} style={{ padding:"3px 10px", fontSize:10 }} onClick={() => m.action === "Promote" && promote(m.ver)}>{m.action}</button>
                          <button className="btn outline" style={{ padding:"3px 8px", fontSize:10, borderColor:"rgba(34,211,238,.3)", color:"var(--accent)" }} onClick={() => openExplain(m.ver)} title="AI Explain">🤖 Explain</button>
                        </td>
                      </tr>
                    ))}
                  </React.Fragment>
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
                {groupModels(filterByInstrument(rrMinerModels)).map(g => (
                  <React.Fragment key={g.key}>
                    <tr className="model-group-header" onClick={() => toggleGroup(g.key)} style={{ background:"var(--panel-2)", borderLeft:"3px solid var(--accent)", cursor:"pointer" }}>
                      <td colSpan={9} style={{ padding:"7px 12px", fontSize:12 }}>
                        <span style={{ marginRight:8 }}>{collapsedGroups[g.key] ? "▶" : "▼"}</span>
                        <span style={{ color:"var(--accent)", fontWeight:600 }}>{g.instrument}</span>
                        {g.run_id ? <span className="muted" style={{ marginLeft:8 }}>· Run {g.run_id}</span> : <span className="muted" style={{ marginLeft:8 }}>· Legacy</span>}
                        <span className="muted" style={{ marginLeft:8 }}>· {g.models.length} model{g.models.length !== 1 ? "s" : ""}</span>
                      </td>
                    </tr>
                    {!collapsedGroups[g.key] && g.models.map(m => (
                      <tr key={m.ver}>
                        <td><input type="checkbox" checked={selectedForCompare.includes(m.ver)} onChange={() => toggleSelect(m.ver)} disabled={!selectedForCompare.includes(m.ver) && selectedForCompare.length >= 2} style={{ cursor:"pointer", accentColor:"#a78bfa" }} /></td>
                        <td>{m.ver}</td>
                        <td className="mono">{m.samples != null ? m.samples.toLocaleString() : "—"}</td>
                        <td className="mono">{m.features}</td>
                        <td className="mono">{m.ridgeAlpha != null ? m.ridgeAlpha : "—"}</td>
                        <td className={`mono ${m.modelExists ? "pos" : "neg"}`}>{m.modelExists ? "OK" : "Missing"}</td>
                        <td className="mono">{m.trained}</td>
                        <td><StatusPill status={m.status} /></td>
                        <td style={{ display:"flex", gap:4, alignItems:"center", flexWrap:"wrap" }}>
                          <button className="btn outline" style={{ padding:"3px 8px", fontSize:10 }} onClick={() => openView(m.ver)} disabled={viewLoading}>View</button>
                          <button className={m.action === "Promote" ? "btn ghost" : "btn outline"} style={{ padding:"3px 10px", fontSize:10 }} onClick={() => m.action === "Promote" && promote(m.ver)}>{m.action}</button>
                          <button className="btn outline" style={{ padding:"3px 8px", fontSize:10, borderColor:"rgba(34,211,238,.3)", color:"var(--accent)" }} onClick={() => openExplain(m.ver)} title="AI Explain">🤖 Explain</button>
                        </td>
                      </tr>
                    ))}
                  </React.Fragment>
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
                {groupModels(filterByInstrument(tradenetMdls)).map(g => (
                  <React.Fragment key={g.key}>
                    <tr className="model-group-header" onClick={() => toggleGroup(g.key)} style={{ background:"var(--panel-2)", borderLeft:"3px solid var(--accent)", cursor:"pointer" }}>
                      <td colSpan={7} style={{ padding:"7px 12px", fontSize:12 }}>
                        <span style={{ marginRight:8 }}>{collapsedGroups[g.key] ? "▶" : "▼"}</span>
                        <span style={{ color:"var(--accent)", fontWeight:600 }}>{g.instrument}</span>
                        {g.run_id ? <span className="muted" style={{ marginLeft:8 }}>· Run {g.run_id}</span> : <span className="muted" style={{ marginLeft:8 }}>· Legacy</span>}
                        <span className="muted" style={{ marginLeft:8 }}>· {g.models.length} model{g.models.length !== 1 ? "s" : ""}</span>
                      </td>
                    </tr>
                    {!collapsedGroups[g.key] && g.models.map(m => (
                      <tr key={m.ver}>
                        <td><input type="checkbox" checked={selectedForCompare.includes(m.ver)} onChange={() => toggleSelect(m.ver)} disabled={!selectedForCompare.includes(m.ver) && selectedForCompare.length >= 2} style={{ cursor:"pointer", accentColor:"#a78bfa" }} /></td>
                        <td>{m.ver}</td>
                        <td className="muted" style={{fontSize:11,maxWidth:220,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{m.modelFile}</td>
                        <td className="mono">{m.trained}</td>
                        <td className={`mono ${m.fileExists ? "pos" : "neg"}`}>{m.fileExists ? "OK" : "Missing"}</td>
                        <td><StatusPill status={m.status} /></td>
                        <td style={{ display:"flex", gap:4, alignItems:"center", flexWrap:"wrap" }}>
                          <button className="btn outline" style={{ padding:"3px 8px", fontSize:10 }} onClick={() => openView(m.ver)} disabled={viewLoading}>View</button>
                          <button className={m.action === "Promote" ? "btn ghost" : "btn outline"} style={{ padding:"3px 10px", fontSize:10 }} onClick={() => m.action === "Promote" && promote(m.ver)}>{m.action}</button>
                          <button className="btn outline" style={{ padding:"3px 8px", fontSize:10, borderColor:"rgba(34,211,238,.3)", color:"var(--accent)" }} onClick={() => openExplain(m.ver)} title="AI Explain">🤖 Explain</button>
                        </td>
                      </tr>
                    ))}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ── Lineage Graph ─────────────────────────────────────────── */}
        {activeTab === "Lineage Graph" && (
          <div className="card">
            <div className="card-title">Model Lineage <span className="right muted">Deployment History</span></div>
            <div className="lineage-flow">
              {(window.LINEAGE_NODES || []).map((node, i, arr) => (
                <React.Fragment key={node.ver}>
                  <div className={`lineage-node${node.active ? " active-node" : ""}`}>
                    <div className="ln-ver">{node.ver}</div>
                    <div className="ln-date">{node.date}</div>
                    {node.active && <div style={{ fontSize:9, color:"var(--ok)", marginTop:4, fontWeight:700 }}>● LIVE</div>}
                  </div>
                  {i < arr.length - 1 && <div className="lineage-arrow">→</div>}
                </React.Fragment>
              ))}
            </div>
            <div style={{ marginTop:16, display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:12 }}>
              {[
                { label:"Total Versions", value:(window.LINEAGE_NODES||[]).length },
                { label:"Active Version", value:((window.LINEAGE_NODES||[]).find(n=>n.active)||{}).ver||"—" },
                { label:"Schema", value:"35-dim Feature Space" },
              ].map(c => (
                <div key={c.label} style={{ background:"var(--panel-2)", borderRadius:6, padding:"8px 12px" }}>
                  <div className="muted" style={{ fontSize:10, textTransform:"uppercase", letterSpacing:".07em", marginBottom:3 }}>{c.label}</div>
                  <div style={{ fontWeight:700 }}>{c.value}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Drift Monitor ─────────────────────────────────────────── */}
        {activeTab === "Drift Monitor" && (
          <div className="card">
            <div className="card-title">Feature Drift Monitor <span className="right muted">PSI vs Training Distribution</span></div>
            {(window.FEATURE_DRIFT || []).map(f => (
              <div key={f.name} className="drift-row">
                <div className="drift-name">{f.name}</div>
                <div className="drift-bar-wrap">
                  <div className="drift-bar" style={{ width:`${Math.min(100, f.psi * 500)}%`, background:f.color }} />
                </div>
                <div className="drift-psi mono">{f.psi.toFixed(3)}</div>
                <div className="drift-status-pill" style={{
                  background: f.status === "OK" ? "rgba(34,197,94,.15)" : f.status === "WARN" ? "rgba(245,158,11,.15)" : "rgba(239,68,68,.15)",
                  color:      f.status === "OK" ? "var(--ok)" : f.status === "WARN" ? "var(--warn)" : "var(--bad)",
                }}>{f.status}</div>
              </div>
            ))}
            <div className="muted" style={{ fontSize:10, marginTop:10 }}>PSI &lt; 0.1 = stable · 0.1–0.2 = monitor · &gt;0.2 = retrain</div>
          </div>
        )}

        {/* ── Shadow Compare ────────────────────────────────────────── */}
        {activeTab === "Shadow Compare" && (() => {
          const sc = window.SHADOW_COMPARE || { active:{}, shadow:{}, metrics:[] };
          return (
            <div>
              <div className="row" style={{ gridTemplateColumns:"1fr 1fr", gap:14 }}>
                <div className="card">
                  <div className="card-title">Side-by-Side Metrics</div>
                  <table className="dt">
                    <thead><tr><th>Metric</th><th style={{ color:"var(--ok)" }}>Active</th><th style={{ color:"var(--accent)" }}>Shadow</th></tr></thead>
                    <tbody>
                      {(sc.metrics || []).map(r => (
                        <tr key={r.label}>
                          <td className="muted">{r.label}</td>
                          <td className="mono">{r.active}</td>
                          <td className="mono">{r.shadow}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="card">
                  <div className="card-title">Promotion Readiness</div>
                  <div style={{ textAlign:"center", padding:"20px 0" }}>
                    <div style={{ fontSize:36, fontWeight:800, color:"var(--accent)" }}>{sc.readiness || "72%"}</div>
                    <div className="muted" style={{ fontSize:12, marginTop:6 }}>Shadow vs Active</div>
                    <div style={{ marginTop:14, fontSize:12 }}>
                      {sc.verdict === "PROMOTE" ? (
                        <span style={{ color:"var(--ok)", fontWeight:700 }}>✓ Recommend Promote</span>
                      ) : (
                        <span style={{ color:"var(--warn)", fontWeight:700 }}>⚠ Needs more evaluation</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })()}

        {/* ── Promotions ────────────────────────────────────────────── */}
        {activeTab === "Promotions" && (
          <div className="card">
            <div className="card-title">Promotion History</div>
            <div className="trade-trace-list">
              {(window.PROMOTION_HISTORY || []).map((ev, i) => (
                <div key={i} className="trace-item">
                  <div className={`trace-dot${ev.type === "promote" ? "" : " muted"}`} style={{
                    background: ev.type === "promote" ? "var(--ok)" : ev.type === "archive" ? "var(--warn)" : "var(--muted)"
                  }} />
                  <div className="trace-time">{ev.date}</div>
                  <div>
                    <div className="trace-event">{ev.ver} — {ev.label}</div>
                    <div className="trace-sub">{ev.sub}</div>
                  </div>
                </div>
              ))}
              {(!window.PROMOTION_HISTORY || window.PROMOTION_HISTORY.length === 0) && (
                <div className="muted" style={{ fontSize:12, padding:"12px 0" }}>No promotion history recorded</div>
              )}
            </div>
          </div>
        )}

        {/* ── Footer info card (registry tabs only) ───────────────── */}
        {FOOTER && (
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
        )}

        {/* ── Groq Explain modal ───────────────────────────────────────── */}
        {(explainLoading || explainResult) && (
          <div onClick={() => { setExplainResult(null); setExplainLoading(false); }} style={{ position:"fixed", inset:0, background:"rgba(0,0,0,0.55)", zIndex:400 }}>
            <div onClick={e => e.stopPropagation()} style={{
              position:"fixed", top:"50%", left:"50%", transform:"translate(-50%,-50%)",
              background:"#122033", border:"1px solid #23364e", borderRadius:10,
              padding:24, width:580, maxWidth:"95vw", maxHeight:"82vh", overflowY:"auto", zIndex:401,
            }}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:14 }}>
                <div style={{ fontSize:13, fontWeight:700 }}>
                  🤖 AI Analysis — {explainResult ? explainResult.version : "…"}
                </div>
                <span onClick={() => { setExplainResult(null); setExplainLoading(false); }} style={{ cursor:"pointer", color:"#7f8da6", fontSize:18, lineHeight:1 }}>✕</span>
              </div>
              <div style={{ fontSize:12, color:"var(--accent)", marginBottom:10, opacity:0.7 }}>
                {activeTab} · Powered by Groq (llama-3.1-70b-versatile)
              </div>
              {explainLoading && (
                <div className="muted" style={{ fontSize:13 }}>Asking Groq… (may take ~5s)</div>
              )}
              {explainResult && !explainResult.ok && (
                <div style={{ color:"var(--bad)", fontSize:13 }}>Error: {explainResult.error}</div>
              )}
              {explainResult && explainResult.ok && (
                <div style={{ whiteSpace:"pre-wrap", color:"var(--text)", fontSize:13, lineHeight:1.7 }}>
                  {explainResult.explanation}
                </div>
              )}
              <div style={{ display:"flex", justifyContent:"flex-end", marginTop:16 }}>
                <button className="btn outline" style={{ fontSize:11 }} onClick={() => { setExplainResult(null); setExplainLoading(false); }}>Close</button>
              </div>
            </div>
          </div>
        )}

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

        {/* ── View modal ───────────────────────────────────────────────── */}
        {viewModel && (
          <ViewModal model={viewModel} onClose={() => setViewModel(null)} />
        )}

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

// ── View Modal ────────────────────────────────────────────────────────────────
function ViewModal({ model, onClose }) {
  const { ver, type, rawData } = model;

  // Scalar top-level fields (exclude arrays/objects for main table)
  const SCALAR_LABELS = {
    version: "Version", active: "Active", trained_at: "Trained At",
    model_file: "Model File", dataset_file: "Dataset File",
    n_zones: "N Zones", n_clusters_requested: "N Clusters Req.",
    n_samples: "N Samples", n_features: "N Features",
    model_exists: "Model Exists", file_exists: "File Exists",
    corr_expected_rr: "Corr (Expected RR)", calibration_error: "Cal Error",
    n_train: "Train Samples", n_val: "Val Samples",
    schema_version: "Schema Version",
  };

  const scalarRows = Object.entries(SCALAR_LABELS)
    .filter(([k]) => rawData[k] !== undefined && rawData[k] !== null)
    .map(([k, label]) => {
      const v = rawData[k];
      let display = typeof v === "boolean" ? (v ? "✓ Yes" : "✗ No")
                  : typeof v === "number"  ? v
                  : v || "—";
      return { label, value: display, key: k };
    });

  const metrics = rawData.metrics && typeof rawData.metrics === "object"
    ? Object.entries(rawData.metrics) : [];

  const schema = Array.isArray(rawData.feature_schema) ? rawData.feature_schema
               : Array.isArray(rawData.feature_order)  ? rawData.feature_order
               : [];

  return (
    <>
      {/* Backdrop */}
      <div onClick={onClose} style={{ position:"fixed", inset:0, background:"rgba(0,0,0,0.55)", zIndex:300 }} />
      {/* Modal */}
      <div style={{
        position:"fixed", top:"50%", left:"50%", transform:"translate(-50%,-50%)",
        background:"#122033", border:"1px solid #23364e", borderRadius:10,
        padding:24, width:560, maxWidth:"95vw", maxHeight:"85vh",
        overflowY:"auto", zIndex:301,
      }}>
        {/* Header */}
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:16 }}>
          <div>
            <div style={{ fontSize:14, fontWeight:700 }}>View — {ver}</div>
            <div style={{ fontSize:11, color:"#7f8da6", marginTop:2 }}>{type}</div>
          </div>
          <span onClick={onClose} style={{ cursor:"pointer", color:"#7f8da6", fontSize:18, lineHeight:1 }}>✕</span>
        </div>

        {/* Registry fields */}
        {scalarRows.length > 0 && (
          <>
            <div style={{ fontSize:10, color:"#7f8da6", textTransform:"uppercase", letterSpacing:".08em", marginBottom:6 }}>Registry Fields</div>
            <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12, marginBottom:16 }}>
              <tbody>
                {scalarRows.map(row => (
                  <tr key={row.key} style={{ borderTop:"1px solid #1e3148" }}>
                    <td style={{ padding:"6px 8px", color:"#9fb0c8", width:"45%" }}>{row.label}</td>
                    <td style={{ padding:"6px 8px", fontFamily:"monospace", color:"#e6edf7" }}>{String(row.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {/* Metrics */}
        {metrics.length > 0 && (
          <>
            <div style={{ fontSize:10, color:"#7f8da6", textTransform:"uppercase", letterSpacing:".08em", marginBottom:6 }}>Metrics</div>
            <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12, marginBottom:16 }}>
              <tbody>
                {metrics.map(([k, v]) => (
                  <tr key={k} style={{ borderTop:"1px solid #1e3148" }}>
                    <td style={{ padding:"6px 8px", color:"#9fb0c8", width:"45%" }}>{k}</td>
                    <td style={{ padding:"6px 8px", fontFamily:"monospace", color:"#e6edf7" }}>{v == null ? "—" : String(v)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {/* Feature Schema */}
        {schema.length > 0 && (
          <>
            <div style={{ fontSize:10, color:"#7f8da6", textTransform:"uppercase", letterSpacing:".08em", marginBottom:6 }}>
              Feature Schema <span style={{ color:"#4b6a8a", fontWeight:400 }}>({schema.length} features)</span>
            </div>
            <div style={{ display:"flex", flexWrap:"wrap", gap:4, maxHeight:120, overflowY:"auto", marginBottom:16, padding:"4px 0" }}>
              {schema.map((f, i) => (
                <span key={i} style={{
                  fontSize:10, padding:"2px 7px", borderRadius:4,
                  background:"rgba(167,139,250,0.1)", color:"#a78bfa",
                  border:"1px solid rgba(167,139,250,0.2)", fontFamily:"monospace",
                }}>{f}</span>
              ))}
            </div>
          </>
        )}

        {/* Raw JSON */}
        <div style={{ fontSize:10, color:"#7f8da6", textTransform:"uppercase", letterSpacing:".08em", marginBottom:6 }}>Raw Registry Entry</div>
        <pre style={{
          background:"#0d1a27", border:"1px solid #1e3148", borderRadius:6,
          padding:"10px 12px", fontSize:10, color:"#9fb0c8", maxHeight:160,
          overflowY:"auto", overflowX:"auto", whiteSpace:"pre-wrap", wordBreak:"break-all",
          marginBottom:16,
        }}>{JSON.stringify(rawData, null, 2)}</pre>

        {/* Footer */}
        <div style={{ display:"flex", justifyContent:"flex-end" }}>
          <button className="btn outline" style={{ fontSize:11 }} onClick={onClose}>Close</button>
        </div>
      </div>
    </>
  );
}

window.ModelsPage = ModelsPage;
