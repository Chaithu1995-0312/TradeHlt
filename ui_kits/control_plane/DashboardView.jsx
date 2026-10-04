function DashboardView({ entries, commands }) {
  const cmdMeta = Object.fromEntries(commands.map(c => [c.id, c]));
  return (
    <Panel title="Monitoring Dashboard — latest per command">
      <div style={{ fontSize: 12, color: "#9fb0c8", marginBottom: 8 }}>Most recent run per monitored command. Auto-refreshes every 2 s for running jobs.</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(320px,1fr))", gap: 12 }}>
        {entries.map(entry => {
          const cmd = cmdMeta[entry.command_id] || { title: entry.command_id };
          const tsLabel = entry.started_at ? entry.started_at.replace("T", " ").replace(/\..*/, "") + " UTC" : "no runs yet";
          const runLabel = entry.run_id ? entry.run_id.slice(0, 8) : "—";
          return (
            <div key={entry.command_id} style={{ background: "#0f1b2e", border: "1px solid #23364e", borderRadius: 10, padding: 10 }}>
              <h3 style={{ fontSize: 13, margin: "0 0 6px 0", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, fontWeight: 600 }}>
                <span>{cmd.title}</span>
                <StatusPill status={entry.status || "queued"} />
              </h3>
              <div style={{ fontSize: 12, color: "#9fb0c8", marginBottom: 4, fontFamily: "ui-monospace,Menlo,monospace" }}>Run {runLabel} · {tsLabel}</div>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <tbody>
                  {(entry.fields || []).length === 0 && (
                    <tr><td colSpan={2} style={{ color: "#9fb0c8", fontSize: 12, padding: 4 }}>No data yet — run this command first.</td></tr>
                  )}
                  {(entry.fields || []).map((f, i) => (
                    <tr key={i}>
                      <td style={{ padding: "4px 0", fontSize: 12, borderBottom: "1px solid #23364e", color: "#9fb0c8" }}>{f.label}</td>
                      <td style={{ padding: "4px 0", fontSize: 12, borderBottom: "1px solid #23364e", fontFamily: "ui-monospace,Menlo,monospace", color: "#0ea5a3", textAlign: "right" }}>
                        {fmtMonitorValue(f)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}
window.DashboardView = DashboardView;
