// ExplorerPanel (M6) — browse all flows + their modules start→end; select a flow or a module to
// see its Docs + Code + Input/Output, plus a $0 Copy/Export-for-Claude bundle.
const { useState: useStateE, useEffect: useEffectE } = React;

function ExplorerPanel({ initialFlow }) {
  const [flows, setFlows] = useStateE([]);
  const [openFlow, setOpenFlow] = useStateE(initialFlow || null);  // expanded flow in the list
  const [sel, setSel] = useStateE(null);               // { flow, module|null }
  const [detail, setDetail] = useStateE(null);
  const [state, setState] = useStateE("idle");         // idle | loading | done | error
  const [openCode, setOpenCode] = useStateE(false);

  useEffectE(() => {
    mockApi.flows().then(d => {
      setFlows(d.flows || []);
      // Deep-link from a Workflow side-subsystem node → auto-select that flow.
      if (initialFlow && (d.flows || []).some(f => f.flow === initialFlow)) select(initialFlow);
    }).catch(() => setFlows([]));
  }, []);

  const select = (flow, module) => {
    setSel({ flow, module: module || null });
    setState("loading"); setDetail(null); setOpenCode(false);
    mockApi.flowContext(flow, module)
      .then(d => { setDetail(d); setState(d && d.error ? "error" : "done"); })
      .catch(e => { setDetail({ error: String(e) }); setState("error"); });
  };

  const arch = detail?.architecture || null;
  const isModule = detail?.scope === "module";

  return (
    <main style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 14, padding: 14, minHeight: "calc(100vh - 56px)", boxSizing: "border-box" }}>
      {/* ── Left: flows → modules (start→end) ── */}
      <Panel title="Flows" id="explorerFlows">
        <div style={{ fontSize: 12, color: "#9fb0c8", marginBottom: 8 }}>All flows; expand for modules (start → end). Select a flow or a module.</div>
        {flows.map(f => {
          const expanded = openFlow === f.flow;
          const flowSelected = sel && sel.flow === f.flow && !sel.module;
          return (
            <div key={f.flow} style={{ border: "1px solid #23364e", borderRadius: 8, marginBottom: 8, overflow: "hidden" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "7px 9px", background: flowSelected ? "#13283f" : "#0f1b2e" }}>
                <span onClick={() => select(f.flow)} style={{ cursor: "pointer", fontWeight: 600, color: flowSelected ? "#0ea5a3" : "#e6edf7", fontSize: 13 }}>{f.flow}</span>
                <span onClick={() => setOpenFlow(expanded ? null : f.flow)} style={{ cursor: "pointer", color: "#9fb0c8", fontSize: 12, userSelect: "none" }}>{expanded ? "▲" : "▼"} {(f.modules || []).length}</span>
              </div>
              {expanded && (
                <div style={{ padding: "4px 9px 8px" }}>
                  {(f.modules || []).map((m, i) => {
                    const modSelected = sel && sel.module === m;
                    return (
                      <div key={m} onClick={() => select(f.flow, m)}
                        style={{ cursor: "pointer", fontSize: 11.5, fontFamily: "ui-monospace,Menlo,monospace", padding: "3px 6px", borderRadius: 4, color: modSelected ? "#0ea5a3" : "#9fb0c8", background: modSelected ? "#13283f" : "transparent" }}>
                        <span style={{ color: "#6b7a93" }}>{i === 0 ? "┌ " : i === f.modules.length - 1 ? "└ " : "├ "}</span>{m}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
        {flows.length === 0 && <div style={{ fontSize: 12, color: "#9fb0c8" }}>No flows found.</div>}
      </Panel>

      {/* ── Right: detail ── */}
      <Panel title={sel ? (sel.module || sel.flow) : "Select a flow or module"} id="explorerDetail">
        {!sel && <div style={{ fontSize: 13, color: "#9fb0c8" }}>Pick a flow (or drill into a module) on the left to see its docs, code, and input/output.</div>}
        {state === "loading" && <div style={{ fontSize: 13, color: "#9fb0c8", padding: "20px 0" }}>Loading…</div>}
        {state === "error" && <div style={{ background: "#2d1515", border: "1px solid #ef4444", borderRadius: 8, padding: 12, color: "#ef4444", fontSize: 13 }}>{detail?.error || "Failed"}</div>}
        {state === "done" && detail && (
          <React.Fragment>
            <div style={{ fontSize: 12, color: "#9fb0c8", marginBottom: 12 }}>
              {detail.title}{isModule && detail.role ? <span> — {detail.role}</span> : null}
            </div>

            {/* Input / Output */}
            <div style={exHead}>Input / Output</div>
            {isModule ? (
              <div style={exBox}>
                <div><span style={{ color: "#9fb0c8" }}>depends on (consumes): </span>{(detail.depends_on || []).join(", ") || "—"}</div>
                <div style={{ marginTop: 4 }}><span style={{ color: "#9fb0c8" }}>imported by (impact radius): </span>{(detail.imported_by || []).join(", ") || "—"}</div>
              </div>
            ) : (
              <div style={exBox}>
                <div><span style={{ color: "#9fb0c8" }}>inputs:  </span>{(detail.inputs || []).join("  ·  ") || "—"}</div>
                <div style={{ marginTop: 4 }}><span style={{ color: "#9fb0c8" }}>outputs: </span>{(detail.outputs || []).join("  ·  ") || "—"}</div>
              </div>
            )}

            {/* Documents */}
            <div style={exHead}>Documents</div>
            <div style={{ ...exBox, color: detail.doc ? "#0ea5a3" : "#9fb0c8" }}>{detail.doc || "No flow document."}</div>

            {/* Code */}
            <div style={{ ...exHead, cursor: "pointer", userSelect: "none" }} onClick={() => setOpenCode(v => !v)}>
              Code {openCode ? "▲" : "▼"} <span style={{ fontSize: 11, color: "#9fb0c8", fontWeight: 400 }}>{(detail.code || []).length} symbol(s)</span>
            </div>
            {openCode && (detail.code || []).map((c, i) => (
              <div key={i} style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 11, color: "#9fb0c8", fontFamily: "ui-monospace,Menlo,monospace" }}>{c.kind} {c.symbol} · {c.file && c.file.split(/[\\/]/).slice(-1)[0]}:{c.start_line}</div>
                <pre style={{ ...exCode }}>{c.code}</pre>
              </div>
            ))}

            {/* Architecture / Export */}
            {arch && arch.available !== false && (
              <React.Fragment>
                <div style={exHead}>Architecture (Claude)</div>
                {arch.source === "export" ? (
                  <React.Fragment>
                    <div style={{ fontSize: 12, color: "#9fb0c8", marginBottom: 8 }}>
                      $0 — paste into Claude Code{arch.prompt_file ? <span> · saved to <code style={{ color: "#0ea5a3" }}>{arch.prompt_file}</code></span> : null}.
                    </div>
                    <Button onClick={() => { try { navigator.clipboard.writeText(arch.prompt || ""); } catch (e) {} }} style={{ marginBottom: 8 }}>Copy / Export for Claude</Button>
                  </React.Fragment>
                ) : (
                  ["executive_summary", "architecture_notes", "code_flow", "impact_radius", "structural_observations"].map(k =>
                    (arch.sections || {})[k] ? (
                      <React.Fragment key={k}>
                        <div style={{ ...exHead, fontSize: 11 }}>{k.replace(/_/g, " ")}</div>
                        <div style={k === "code_flow" ? exCodeFlow : exBox}>{arch.sections[k]}</div>
                      </React.Fragment>
                    ) : null
                  )
                )}
              </React.Fragment>
            )}
          </React.Fragment>
        )}
      </Panel>
    </main>
  );
}

const exHead = { fontSize: 12, fontWeight: 700, color: "#0ea5a3", textTransform: "uppercase", letterSpacing: ".08em", margin: "14px 0 6px" };
const exBox = { background: "#0f1b2e", borderRadius: 8, padding: 10, fontSize: 12.5, color: "#e6edf7", lineHeight: 1.6, whiteSpace: "pre-wrap", wordBreak: "break-word" };
const exCode = { background: "#0b1424", border: "1px solid #23364e", borderRadius: 6, padding: 8, fontSize: 11, color: "#cdd9ec", fontFamily: "ui-monospace,Menlo,monospace", overflowX: "auto", margin: "2px 0 0" };
const exCodeFlow = { ...exBox, fontFamily: "ui-monospace,Menlo,monospace", fontSize: 12 };

window.ExplorerPanel = ExplorerPanel;
