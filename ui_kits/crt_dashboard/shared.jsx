// Sub-components shared by panels — Sidebar, KPI strip, common pills.

function Sidebar({ active, footer }) {
  const items = [
    { id: "Runtime",   icon: "M4 11 L10 5 L16 11 V16 H4 Z" },
    { id: "Research",  icon: "M6 12 A4 4 0 1 0 14 12 A4 4 0 1 0 6 12" },
    { id: "Models",    icon: "M5 7 H15 V15 H5 Z" },
    { id: "Trades",    icon: "M4 13 L7 9 L10 11 L14 6 L16 8" },
    { id: "Backtests", icon: "M5 9 H15 M5 12 H15 M5 15 H11" },
    { id: "System",    icon: "M10 6 V14 M6 10 H14" },
  ];
  return (
    <aside className="side">
      <div className="brand"><span className="logo" /> CRT</div>
      {items.map(it => (
        <a key={it.id}
           className={it.id === active ? "active" : ""}
           onClick={() => typeof window.__crtNav === 'function' && window.__crtNav(it.id)}
           style={{cursor: 'pointer'}}>
          <svg className="ico" width="14" height="14" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <path d={it.icon} />
          </svg>
          {it.id}
        </a>
      ))}
      <div className="footer">{footer}</div>
    </aside>
  );
}

function Kpi({ label, value, sub, tone, pill, monoSub }) {
  return (
    <div className="kpi">
      <div className="label">{label}</div>
      {pill ? <div><span className={`pill ${pill.kind}`}>{pill.text}</span></div> : <div className={`v ${tone || ""}`}>{value}</div>}
      {sub && <div className={`sub ${monoSub ? "mono" : ""}`}>{sub}</div>}
    </div>
  );
}

function SectionTitle({ index, title, subtitle }) {
  return (
    <div className="section-title">
      <h2>{index}. {title}</h2>
      <div className="sub">{subtitle}</div>
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    Completed: { tag: "ok" },
    ACTIVE:    { tag: "active" },
    Candidate: { tag: "candidate" },
    Archived:  { tag: "archived" },
  };
  const t = map[status] || { tag: "archived" };
  return <span className={`tag ${t.tag}`}>{status}</span>;
}

function CheckIcon({ tone = "#22c55e", size = 12 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={tone} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: "middle" }}>
      <path d="M3 8.5 L6.5 12 L13 4.5" />
    </svg>
  );
}

// ── TopBar ────────────────────────────────────────────────────
const TOP_TABS = [
  "Executive","Runtime","Trades","Models","Backtests","System","Intelligence","Replay Lab"
];

function TopBar({ activePage, onNav, instruments, selectedInstrument, instrumentLoading, status, onInstrumentChange }) {
  const modelVer = (status && status.active_model_version) ? status.active_model_version : "—";

  return (
    <header className="top-bar">
      <div className="top-bar-brand">
        <div className="brand-mark">CRT</div>
        <div className="brand-text">
          <span className="brand-name">CRT / TRADING SYSTEM</span>
          <span className="brand-tag">Intelligence. Traceability. Edge.</span>
        </div>
      </div>
      <nav className="top-bar-tabs">
        {TOP_TABS.map(t => (
          <button key={t}
            className={`top-bar-tab${activePage === t ? " active" : ""}`}
            onClick={() => onNav(t)}
          >{t}</button>
        ))}
      </nav>
      <div className="top-bar-right">

        {/* ── Instrument selector ── */}
        <div style={{ display:"flex", alignItems:"center", gap:6, marginRight:4 }}>
          {instrumentLoading && (
            <span style={{
              display:"inline-block", width:13, height:13, borderRadius:"50%",
              border:"2px solid rgba(167,139,250,0.25)", borderTopColor:"#a78bfa",
              animation:"tb-spin 0.7s linear infinite",
            }} />
          )}
          <select
            value={selectedInstrument || "EURUSD"}
            disabled={instrumentLoading}
            onChange={(e) => onInstrumentChange && onInstrumentChange(e.target.value)}
            style={{
              background:"#0f1e30", color:"#e6edf7", border:"1px solid #23364e",
              borderRadius:6, padding:"4px 10px", fontSize:11, fontWeight:600,
              cursor: instrumentLoading ? "not-allowed" : "pointer",
              opacity: instrumentLoading ? 0.6 : 1,
              outline:"none", appearance:"none", WebkitAppearance:"none",
              paddingRight:22, backgroundImage:
                "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%237f8da6'/%3E%3C/svg%3E\")",
              backgroundRepeat:"no-repeat", backgroundPosition:"right 7px center",
            }}
          >
            {(instruments || ["EURUSD"]).map(inst => (
              <option key={inst} value={inst}>{inst}</option>
            ))}
          </select>
        </div>

        {/* ── Model version pill (per-instrument, dynamic) ── */}
        <div className="tb-pill">
          <span className="live-dot"></span>
          {modelVer !== "—" ? `CRT ${modelVer} (Live)` : "CRT — (Live)"}
        </div>

        <div className="tb-pill">2020-01 → 2025-05</div>
        <div className="tb-pill">M15 ▾</div>
        <div className="tb-icon">☀</div>
        <div className="notif-badge tb-icon">
          🔔<span className="badge">4</span>
        </div>
        <div className="avatar">A</div>
      </div>
    </header>
  );
}

// ── SidebarNew ────────────────────────────────────────────────
const SIDEBAR_SECTIONS = [
  { header:"OVERVIEW", items:[
    { id:"Executive", label:"Executive",       icon:"⬛" },
  ]},
  { header:"RUNTIME", items:[
    { id:"Runtime",       label:"Live Monitor",   icon:"📡" },
    { id:"EventPipeline", label:"Event Pipeline", icon:"⚡" },
    { id:"SignalFlow",    label:"Signal Flow",    icon:"🔀" },
    { id:"Alerts",        label:"Alerts",         icon:"🔔", badge:"4" },
  ]},
  { header:"RESEARCH", items:[
    { id:"Research",    label:"Feature Explorer", icon:"🔬" },
    { id:"Clusters",    label:"Cluster Explorer", icon:"⬡"  },
    { id:"SeqPatterns", label:"Seq. Patterns",    icon:"🔗", isNew:true },
    { id:"RegimeMap",   label:"Regime Map",       icon:"🗺" },
    { id:"OppMap",      label:"Opportunity Map",  icon:"📊" },
  ]},
  { header:"MODELS", items:[
    { id:"Models",       label:"Model Registry", icon:"🏛"  },
    { id:"Lineage",      label:"Lineage Graph",  icon:"🌿", isNew:true },
    { id:"DriftMonitor", label:"Drift Monitor",  icon:"📉" },
    { id:"ShadowCompare",label:"Shadow Compare", icon:"👥" },
    { id:"Promotions",   label:"Promotions",     icon:"🚀" },
  ]},
  { header:"TRADES", items:[
    { id:"Trades",         label:"Trade Explorer",  icon:"📋" },
    { id:"TradeTrace",     label:"Trade Trace",     icon:"🔍", isNew:true },
    { id:"Rejections",     label:"Rejections",      icon:"✗"  },
    { id:"SessionAnalysis",label:"Session Analysis",icon:"⏱" },
  ]},
  { header:"BACKTESTS", items:[
    { id:"Backtests",   label:"Backtest Lab", icon:"🧪" },
    { id:"WalkForward", label:"Walk-Forward", icon:"↗"  },
    { id:"StressTests", label:"Stress Tests", icon:"⚠"  },
    { id:"MonteCarlo",  label:"Monte Carlo",  icon:"🎲" },
  ]},
  { header:"SYSTEM", items:[
    { id:"System",     label:"Infrastructure", icon:"🖥" },
    { id:"DataQuality",label:"Data Quality",   icon:"✓"  },
    { id:"LogsAudit",  label:"Logs & Audit",   icon:"📄" },
    { id:"Settings",   label:"Settings",       icon:"⚙"  },
  ]},
];

const SIDEBAR_PAGE_MAP = {
  Executive:"Executive",
  Runtime:"Runtime", EventPipeline:"Runtime", SignalFlow:"Runtime", Alerts:"Runtime",
  Research:"Research", Clusters:"Research", SeqPatterns:"Intelligence", RegimeMap:"Research", OppMap:"Research",
  Models:"Models", Lineage:"Models", DriftMonitor:"Models", ShadowCompare:"Models", Promotions:"Models",
  Trades:"Trades", TradeTrace:"Trades", Rejections:"Trades", SessionAnalysis:"Trades",
  Backtests:"Backtests", WalkForward:"Backtests", StressTests:"Backtests", MonteCarlo:"Backtests",
  System:"System", DataQuality:"System", LogsAudit:"System", Settings:"System",
};

function SidebarNew({ activePage, activeSub, onNav, onSubNav }) {
  return (
    <nav className="sidebar-new">
      {SIDEBAR_SECTIONS.map(sec => (
        <div key={sec.header}>
          <div className="sidebar-section-header">{sec.header}</div>
          {sec.items.map(item => {
            const isActive = activeSub === item.id ||
              (!activeSub && activePage === item.id) ||
              (!activeSub && item.id === "Executive" && activePage === "Executive");
            return (
              <div key={item.id}
                className={`sidebar-item${isActive ? " active" : ""}`}
                onClick={() => {
                  const page = SIDEBAR_PAGE_MAP[item.id] || item.id;
                  onNav(page);
                  onSubNav(item.id);
                }}
              >
                <span className="si-icon">{item.icon}</span>
                {item.label}
                {item.badge && <span className="si-badge">{item.badge}</span>}
                {item.isNew && <span className="si-new">NEW</span>}
              </div>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

Object.assign(window, { Sidebar, Kpi, SectionTitle, StatusPill, CheckIcon, TopBar, SidebarNew });
