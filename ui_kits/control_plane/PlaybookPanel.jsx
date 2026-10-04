function PlaybookPanel({ commands, stages, completedMap, onJump, onToggle }) {
  const byStage = (stage) => commands.filter(c => (c.workflow_stage || c.category) === stage);
  return (
    <Panel title="Tutorial / Playbook" id="playbookPanel">
      <div style={{ fontSize: 12, color: "#9fb0c8" }}>Workflow checklist and command navigation.</div>
      <div style={{ marginTop: 8 }}>
        {stages.map(stage => {
          const items = byStage(stage);
          return (
            <div key={stage} style={{ border: "1px solid #23364e", borderRadius: 8, padding: 8, marginBottom: 8 }}>
              <h3 style={{ fontSize: 13, margin: "0 0 6px 0", fontWeight: 600 }}>{stage}</h3>
              {items.length === 0 && <div style={{ fontSize: 12, color: "#9fb0c8" }}>No commands</div>}
              {items.map(cmd => {
                const completed = !!completedMap[cmd.id];
                const next = (cmd.recommended_next_command_ids || []).join(", ");
                return (
                  <div key={cmd.id} style={{ fontSize: 12, margin: "4px 0", padding: 6, background: "#0f1b2e", border: "1px solid #23364e", borderRadius: 6 }}>
                    <div><strong style={{ color: "#e6edf7", fontWeight: 600 }}>{cmd.title}</strong><Chip completed={completed}>{completed ? "Completed" : "Pending"}</Chip></div>
                    <div style={{ fontSize: 12, color: "#9fb0c8", marginTop: 3 }}>{cmd.description}</div>
                    <div style={{ fontSize: 12, color: "#9fb0c8" }}>{next ? `Suggested next: ${next}` : "Suggested next: -"}</div>
                    <div style={{ display: "flex", gap: 6, marginTop: 5 }}>
                      <Button autoWidth variant="ghost" onClick={() => onJump(cmd.id)} style={{ fontSize: 11, padding: "4px 8px" }}>Jump</Button>
                      <Button autoWidth variant="ghost" onClick={() => onToggle(cmd.id)} style={{ fontSize: 11, padding: "4px 8px" }}>{completed ? "Mark pending" : "Mark complete"}</Button>
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </Panel>
  );
}
window.PlaybookPanel = PlaybookPanel;
