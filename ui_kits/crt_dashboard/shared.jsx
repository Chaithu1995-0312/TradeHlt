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
        <a key={it.id} className={it.id === active ? "active" : ""}>
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

Object.assign(window, { Sidebar, Kpi, SectionTitle, StatusPill, CheckIcon });
