// page10_admin.jsx - Admin / Historical Run (UI design only - NOT wired to any backend).
// Pure projection: receives `instruments` / `selectedInstrument` via props from app.jsx
// runtimeProps (same list the TopBar instrument selector uses). No fetches here.

// Placeholder list - used ONLY when the app has not provided an instruments list
// (runtime list comes from ApiClient.fetchInstruments() in app.jsx).
const HR_PLACEHOLDER_INSTRUMENTS = ["XAUUSD", "BTCUSD", "ETHUSD", "EURUSD", "GBPUSD", "USDJPY"];

function hrIsoDate(d) {
  const z = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
}

function hrDaysAgo(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return hrIsoDate(d);
}

function AdminPage({ activeSub, instruments, selectedInstrument }) {
  const fromApp = Array.isArray(instruments) && instruments.length > 0;
  const list = fromApp ? instruments : HR_PLACEHOLDER_INSTRUMENTS;

  const [selected, setSelected] = React.useState(() =>
    selectedInstrument && list.includes(selectedInstrument) ? [selectedInstrument] : []
  );
  const [filter, setFilter]   = React.useState("");
  const [fromDate, setFromDate] = React.useState(() => hrDaysAgo(90));
  const [toDate, setToDate]     = React.useState(() => hrIsoDate(new Date()));
  const [preset, setPreset]     = React.useState("90d");
  const [lastRequest, setLastRequest] = React.useState(null);

  // Drop selections that are no longer in the list (e.g. after instruments load).
  React.useEffect(() => {
    setSelected((s) => s.filter((x) => list.includes(x)));
  }, [list.join("|")]);

  const visible = list.filter((x) => x.toLowerCase().includes(filter.trim().toLowerCase()));
  const toggle = (inst) =>
    setSelected((s) => (s.includes(inst) ? s.filter((x) => x !== inst) : [...s, inst]));
  const selectAll  = () => setSelected((s) => Array.from(new Set([...s, ...visible])));
  const selectNone = () => setSelected([]);

  const PRESETS = [
    { id: "30d", label: "Last 30d", days: 30 },
    { id: "90d", label: "Last 90d", days: 90 },
    { id: "1y",  label: "Last 1y",  days: 365 },
  ];
  const applyPreset = (p) => {
    setPreset(p.id);
    setFromDate(hrDaysAgo(p.days));
    setToDate(hrIsoDate(new Date()));
  };

  const datesValid = !!fromDate && !!toDate && fromDate <= toDate;
  const canRun = selected.length > 0 && datesValid;
  let blocker = "";
  if (selected.length === 0) blocker = "Select at least one instrument.";
  else if (!fromDate || !toDate) blocker = "Pick both From and To dates.";
  else if (!datesValid) blocker = "From date must be on or before To date.";

  const spanDays = datesValid
    ? Math.round((new Date(toDate) - new Date(fromDate)) / 86400000) + 1
    : null;

  function onRun() {
    if (!canRun) return;
    const req = {
      coins: list.filter((x) => selected.includes(x)), // keep list order
      from: fromDate,
      to: toDate,
      requested_at: new Date().toISOString(),
    };
    // TODO(admin/historical-run): wire to backend here, e.g.
    //   window.ApiClient.startHistoricalRun(req).then(...)
    // No such ApiClient method / endpoint exists yet - design only, nothing is started.
    console.log("[HistoricalRun] Run request (design only - not wired):", req);
    setLastRequest(req);
  }

  const labelStyle = { fontSize: 11, display: "block", marginBottom: 4 };

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Admin / Historical Run</div>
          <div className="page-sub">
            Queue a historical run across instruments and a date range
            <span style={{ marginLeft: 8, color: "var(--warn)" }}>{"\u00b7"} design only {"\u2014"} not wired</span>
          </div>
        </div>
      </div>

      <div className="row" style={{ gridTemplateColumns: "minmax(260px, 1fr) 1.4fr", alignItems: "start" }}>
        {/* -- Instruments ------------------------------------------------ */}
        <div className="card">
          <div className="card-title">
            Instruments
            <span className="right muted" style={{ textTransform: "none", letterSpacing: 0 }}>
              {selected.length} / {list.length} selected
            </span>
          </div>
          <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
            <input className="input" placeholder="Filter instruments..." value={filter}
                   onChange={(e) => setFilter(e.target.value)} />
            <button className="btn ghost" style={{ whiteSpace: "nowrap" }} onClick={selectAll}>Select all</button>
            <button className="btn outline" style={{ whiteSpace: "nowrap" }} onClick={selectNone}>None</button>
          </div>
          <div style={{ maxHeight: 360, overflowY: "auto", border: "1px solid var(--line)", borderRadius: 6 }}>
            {visible.length === 0 && (
              <div className="muted" style={{ padding: 10, fontSize: 12 }}>No instruments match "{filter}".</div>
            )}
            {visible.map((inst) => {
              const on = selected.includes(inst);
              return (
                <label key={inst}
                  style={{
                    display: "flex", alignItems: "center", gap: 10, padding: "7px 10px",
                    borderBottom: "1px solid var(--line)", cursor: "pointer", fontSize: 12,
                    background: on ? "rgba(34,211,238,0.08)" : "transparent",
                    color: on ? "var(--text)" : "var(--muted-2)",
                  }}>
                  <input type="checkbox" checked={on} onChange={() => toggle(inst)}
                         style={{ accentColor: "#22d3ee" }} />
                  <span className="mono" style={{ fontWeight: on ? 700 : 500 }}>{inst}</span>
                  {inst === selectedInstrument && <span className="tag normal" style={{ marginLeft: "auto" }}>current</span>}
                </label>
              );
            })}
          </div>
          <div className="muted" style={{ fontSize: 10, marginTop: 8 }}>
            Source: {fromApp ? "app instrument list (ApiClient.fetchInstruments via app.jsx)" : "static placeholder list (no instruments from app)"}
          </div>
        </div>

        {/* -- Date range + Run ------------------------------------------ */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="card">
            <div className="card-title">Date Range</div>
            <div className="row" style={{ gridTemplateColumns: "1fr 1fr", marginBottom: 10 }}>
              <div>
                <label className="muted" style={labelStyle}>From</label>
                <input className="input" type="date" value={fromDate} max={toDate || undefined}
                       style={{ colorScheme: "dark" }}
                       onChange={(e) => { setFromDate(e.target.value); setPreset(""); }} />
              </div>
              <div>
                <label className="muted" style={labelStyle}>To</label>
                <input className="input" type="date" value={toDate} min={fromDate || undefined}
                       style={{ colorScheme: "dark" }}
                       onChange={(e) => { setToDate(e.target.value); setPreset(""); }} />
              </div>
            </div>
            <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
              <span className="muted" style={{ fontSize: 11, marginRight: 4 }}>Presets</span>
              {PRESETS.map((p) => (
                <button key={p.id} className={`btn ${preset === p.id ? "ghost" : "outline"}`}
                        style={{ padding: "4px 10px", fontSize: 11 }}
                        onClick={() => applyPreset(p)}>{p.label}</button>
              ))}
              <span className="muted mono" style={{ fontSize: 11, marginLeft: "auto" }}>
                {spanDays != null ? `${spanDays} day${spanDays === 1 ? "" : "s"}` : "\u2014"}
              </span>
            </div>
          </div>

          <div className="card">
            <div className="card-title">Run</div>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <button className="btn" disabled={!canRun} onClick={onRun}
                      title={canRun ? "Build run request (design only)" : blocker}
                      style={{ padding: "8px 22px", opacity: canRun ? 1 : 0.45, cursor: canRun ? "pointer" : "not-allowed" }}>
                {"\u25B6"} Run
              </button>
              <span className={canRun ? "muted" : "neg"} style={{ fontSize: 12 }}>
                {canRun
                  ? `${selected.length} instrument${selected.length === 1 ? "" : "s"} \u00b7 ${fromDate} \u2192 ${toDate}`
                  : blocker}
              </span>
            </div>
          </div>

          {lastRequest && (
            <div className="card" style={{ borderColor: "rgba(250,204,21,0.45)" }}>
              <div className="card-title">
                Run request
                <span className="tag candidate" style={{ letterSpacing: 0 }}>design only {"\u2014"} not wired</span>
              </div>
              <div className="mono" style={{ fontSize: 12, lineHeight: 1.7, color: "var(--text)" }}>
                <div><span className="muted">coins=</span>[{lastRequest.coins.join(", ")}]</div>
                <div><span className="muted">from=</span>{lastRequest.from}</div>
                <div><span className="muted">to=</span>{lastRequest.to}</div>
                <div className="muted" style={{ fontSize: 10 }}>built {lastRequest.requested_at} {"\u00b7"} logged to console {"\u00b7"} no API called, no backtest started</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { AdminPage });