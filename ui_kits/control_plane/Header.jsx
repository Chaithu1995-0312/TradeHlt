function Header({ view, onToggleView, onHelp }) {
  return (
    <header style={{ padding: "14px 18px", borderBottom: "1px solid #23364e", display: "flex", justifyContent: "space-between", alignItems: "center", background: "rgba(0,0,0,.18)" }}>
      <h1 style={{ fontSize: 18, margin: 0, fontWeight: 700, color: "#58a6ff" }}>CRT Web Control Plane</h1>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <span style={{ fontSize: 12, color: "#9fb0c8" }}>Data Prep → Tuning → Validation & Promotion → Replay & Backtest → Live Runner</span>
        <Button autoWidth onClick={onToggleView}>{view === "dashboard" ? "← Back to Runs" : "Dashboard"}</Button>
        <Button autoWidth onClick={onHelp}>Help / Start Tour</Button>
      </div>
    </header>
  );
}
window.Header = Header;
