// Inspector — rich per-run tracking: summary card, args, resolved CLI, status timeline,
// monitored fields with sparkline column, stdout/stderr, artifacts.

const { useState: useStateI, useEffect: useEffectI } = React;

function fmtDuration(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  if (h > 0) return `${h}h ${m}m ${sec}s`;
  if (m > 0) return `${m}m ${sec}s`;
  return `${sec}s`;
}
function fmtTs(ts) {
  if (!ts) return "—";
  return ts.replace("T", " ").replace(/\..*/, "") + " UTC";
}
function fmtTsShort(ts) {
  if (!ts) return "—";
  return ts.replace("T", " ").replace(/\..*/, "").slice(11) /* HH:MM:SS */;
}

function useLiveSeconds(active, startedAt) {
  const [now, setNow] = useStateI(Date.now());
  useEffectI(() => {
    if (!active) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active]);
  if (!startedAt) return 0;
  return Math.max(0, (now - new Date(startedAt).getTime()) / 1000);
}

function CopyBtn({ text }) {
  const [copied, setCopied] = useStateI(false);
  return (
    <span
      onClick={async (e) => {
        e.stopPropagation();
        try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1200); }
        catch (_) { /* noop */ }
      }}
      style={{ cursor: "pointer", fontSize: 11, color: copied ? "#22c55e" : "#9fb0c8", marginLeft: 6, fontFamily: "ui-monospace,Menlo,monospace", userSelect: "none" }}
      title="Copy"
    >{copied ? "copied" : "copy"}</span>
  );
}

function MetricCell({ label, value, mono, tone }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
      <span style={{ fontSize: 10, color: "#9fb0c8", letterSpacing: ".08em", textTransform: "uppercase" }}>{label}</span>
      <span style={{ fontSize: 12, color: tone || "#e6edf7", fontFamily: mono ? "ui-monospace,Menlo,monospace" : "inherit", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{value}</span>
    </div>
  );
}

function RunSummary({ run }) {
  const startedAt = run.started_at;
  const endedAt = run.ended_at;
  const isActive = run.status === "running" || run.status === "queued";
  const liveSec = useLiveSeconds(isActive, startedAt);
  const duration = endedAt && startedAt
    ? (new Date(endedAt).getTime() - new Date(startedAt).getTime()) / 1000
    : (startedAt ? liveSec : 0);
  const exitTone = run.exit_code === 0 ? "#22c55e" : run.exit_code != null ? "#ef4444" : "#9fb0c8";
  return (
    <div style={{ background: "#0f1b2e", border: "1px solid #23364e", borderRadius: 10, padding: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
          <StatusPill status={run.status} />
          <span style={{ fontSize: 13, fontWeight: 600, color: "#e6edf7", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{run.command_id}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center" }}>
          <span style={{ fontSize: 11, color: "#9fb0c8", fontFamily: "ui-monospace,Menlo,monospace" }}>{run.run_id.slice(0, 12)}</span>
          <CopyBtn text={run.run_id} />
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, paddingTop: 8, borderTop: "1px solid #23364e" }}>
        <MetricCell label="Duration" value={fmtDuration(duration)} mono tone={isActive ? "#f59e0b" : "#0ea5a3"} />
        <MetricCell label="Exit" value={run.exit_code ?? "—"} mono tone={exitTone} />
        <MetricCell label="Started" value={fmtTs(startedAt)} mono />
        <MetricCell label="Ended" value={fmtTs(endedAt)} mono />
      </div>
    </div>
  );
}

function ArgsBlock({ args }) {
  const entries = Object.entries(args || {}).filter(([, v]) => v !== null && v !== undefined && v !== "");
  if (entries.length === 0) {
    return <div style={{ fontSize: 12, color: "#9fb0c8" }}>No arguments.</div>;
  }
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <tbody>
        {entries.map(([k, v]) => (
          <tr key={k}>
            <td style={{ padding: "4px 8px 4px 0", fontSize: 12, color: "#9fb0c8", verticalAlign: "top", width: "30%", fontFamily: "ui-monospace,Menlo,monospace" }}>{k}</td>
            <td style={{ padding: "4px 0", fontSize: 12, color: "#e6edf7", fontFamily: "ui-monospace,Menlo,monospace", wordBreak: "break-all" }}>
              {Array.isArray(v) ? v.join(", ") : (typeof v === "boolean" ? String(v) : String(v))}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TimelineBlock({ events, status }) {
  if (!events || events.length === 0) {
    return <div style={{ fontSize: 12, color: "#9fb0c8" }}>No events yet.</div>;
  }
  const eventColor = (ev) => {
    if (ev === "failed") return "#ef4444";
    if (ev === "stopped") return "#ef4444";
    if (ev === "succeeded") return "#22c55e";
    if (ev === "started") return "#f59e0b";
    if (ev === "created") return "#9fb0c8";
    return "#0ea5a3";
  };
  return (
    <div style={{ position: "relative", paddingLeft: 14 }}>
      {/* spine */}
      <div style={{ position: "absolute", left: 4, top: 6, bottom: 6, width: 1, background: "#23364e" }} />
      {events.map((e, i) => (
        <div key={i} style={{ position: "relative", paddingBottom: i === events.length - 1 ? 0 : 10 }}>
          <span style={{ position: "absolute", left: -14, top: 4, width: 8, height: 8, borderRadius: "50%", background: eventColor(e.event), boxShadow: "0 0 0 2px #122033" }} />
          <div style={{ fontSize: 12, color: "#e6edf7" }}>
            <span style={{ color: eventColor(e.event), fontWeight: 600 }}>{e.event}</span>
            <span style={{ color: "#9fb0c8", fontFamily: "ui-monospace,Menlo,monospace", marginLeft: 8 }}>{fmtTsShort(e.ts)}</span>
          </div>
          {e.note && <div style={{ fontSize: 11, color: "#9fb0c8", marginTop: 2 }}>{e.note}</div>}
        </div>
      ))}
      {(status === "running" || status === "queued") && (
        <div style={{ position: "relative" }}>
          <span style={{ position: "absolute", left: -14, top: 4, width: 8, height: 8, borderRadius: "50%", background: "#f59e0b", animation: "tlpulse 1.4s ease-in-out infinite" }} />
          <div style={{ fontSize: 11, color: "#9fb0c8", marginLeft: 0 }}>…in progress</div>
        </div>
      )}
      <style>{`@keyframes tlpulse { 0%,100% { opacity: 1 } 50% { opacity: .35 } }`}</style>
    </div>
  );
}

function MonitoredFieldsTable({ fields, history }) {
  if (!fields || fields.length === 0) {
    return <div style={{ fontSize: 12, color: "#9fb0c8" }}>No tracked fields configured for this command.</div>;
  }
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr>
          <th style={th}>Field</th>
          <th style={th}>Value</th>
          <th style={{ ...th, width: 90, textAlign: "right" }}>Trend</th>
        </tr>
      </thead>
      <tbody>
        {fields.map((f, i) => {
          const series = history?.[f.label];
          return (
            <tr key={i}>
              <td style={td}>{f.label}</td>
              <td style={{ ...td, fontFamily: "ui-monospace,Menlo,monospace", color: "#0ea5a3" }}>{fmtMonitorValue(f)}</td>
              <td style={{ ...td, textAlign: "right" }}>{series && series.length >= 2 ? <Sparkline points={series} /> : <span style={{ color: "#6b7a93", fontSize: 11 }}>—</span>}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

const th = { borderBottom: "1px solid #23364e", padding: "6px 4px", fontSize: 12, textAlign: "left", color: "#9fb0c8" };
const td = { borderBottom: "1px solid #23364e", padding: "6px 4px", fontSize: 12 };

function SectionTitle({ children, right }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "14px 0 6px" }}>
      <h3 style={{ fontSize: 13, margin: 0, fontWeight: 600, color: "#e6edf7" }}>{children}</h3>
      {right}
    </div>
  );
}

function InspectorPanel({ run, artifacts, monitors, onReport, onContext }) {
  const [synth, setSynth] = useStateI("idle"); // "idle"|"loading"|"done"|"error"

  const onSynthesize = () => {
    if (!run || synth === "loading") return;
    setSynth("loading");
    fetch("/api/agent/synthesize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: run.run_id }),
    })
      .then(r => r.json())
      .then(j => setSynth(j.ok ? "done" : "error"))
      .catch(() => setSynth("error"))
      .finally(() => setTimeout(() => setSynth("idle"), 3000));
  };

  if (!run) {
    return (
      <Panel title="Run Inspector" id="inspectorPanel">
        <div style={{ fontSize: 12, color: "#9fb0c8" }}>No run selected. Click a row in Run History to inspect.</div>
      </Panel>
    );
  }
  return (
    <Panel title="Run Inspector" id="inspectorPanel">
      <RunSummary run={run} />
      <div style={{ display: "flex", gap: 8, margin: "10px 0 4px" }}>
        <Button onClick={() => onReport && onReport(run.run_id)}>📋 Report</Button>
        <Button onClick={() => onContext && onContext(run.run_id)} style={{ background: "#1a2e4a", border: "1px solid #0ea5a3", color: "#0ea5a3" }}>🧠 Context</Button>
        <Button
          onClick={onSynthesize}
          disabled={synth === "loading"}
          style={{
            background: synth === "done" ? "#1a3a2a" : synth === "error" ? "#3a1a1a" : "#1a2438",
            border: `1px solid ${synth === "done" ? "#7ee787" : synth === "error" ? "#ff7b72" : "#7b3f00"}`,
            color: synth === "done" ? "#7ee787" : synth === "error" ? "#ff7b72" : "#d29922",
            opacity: synth === "loading" ? 0.6 : 1,
          }}>
          {synth === "loading" ? "..." : synth === "done" ? "[+] Synthesized" : synth === "error" ? "[!] Failed" : "Synthesize"}
        </Button>
      </div>

      <SectionTitle right={<CopyBtn text={run.cmdline || ""} />}>Resolved Command</SectionTitle>
      <Pre>{run.cmdline || "—"}</Pre>

      <SectionTitle>Arguments</SectionTitle>
      <ArgsBlock args={run.args} />

      <SectionTitle right={<span style={{ fontSize: 11, color: "#9fb0c8" }}>{(run.timeline || []).length} event{(run.timeline || []).length === 1 ? "" : "s"}</span>}>Timeline</SectionTitle>
      <TimelineBlock events={run.timeline} status={run.status} />

      <SectionTitle>Monitored Fields</SectionTitle>
      <MonitoredFieldsTable fields={monitors?.fields} history={run.field_history} />

      {run.log_paths && Object.keys(run.log_paths).length > 0 && (
        <React.Fragment>
          <SectionTitle>Log Files</SectionTitle>
          <div style={{ fontSize: 11, color: "#9fb0c8", marginBottom: 4 }}>
            Run ID: <span style={{ fontFamily: "ui-monospace,Menlo,monospace", color: "#e6edf7" }}>{run.run_id}</span>
          </div>
          {Object.entries(run.log_paths).map(([key, path]) => (
            <div key={key} style={{ display: "flex", gap: 8, fontSize: 11, padding: "3px 0", borderBottom: "1px dashed #1a2e4a" }}>
              <span style={{ color: "#9fb0c8", width: 60, flexShrink: 0 }}>{key}</span>
              <span style={{ fontFamily: "ui-monospace,Menlo,monospace", color: "#0ea5a3", wordBreak: "break-all" }}>{path}</span>
            </div>
          ))}
        </React.Fragment>
      )}

      <SectionTitle right={<span style={{ fontSize: 11, color: "#9fb0c8" }}>{(artifacts?.artifacts || []).length}</span>}>Artifacts</SectionTitle>
      {(artifacts?.artifacts || []).length === 0 && <div style={{ fontSize: 12, color: "#9fb0c8" }}>No artifacts.</div>}
      {(artifacts?.artifacts || []).map((a, i) => (
        <div key={i} style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 12, padding: "5px 0", borderBottom: "1px dashed #23364e" }}>
          <span style={{ fontFamily: "ui-monospace,Menlo,monospace", color: "#e6edf7", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.path}</span>
          <span style={{ color: a.exists ? "#22c55e" : "#ef4444", flexShrink: 0 }}>{a.exists ? "exists" : "missing"}</span>
        </div>
      ))}
    </Panel>
  );
}

// ── ContextModal ────────────────────────────────────────────────────────────
function ContextModal({ runId, run, onClose }) {
  const [state, setStateCtx] = useStateI("idle"); // idle | loading | done | error
  const [data, setData]     = useStateI(null);
  const [openCode, setOpenCode] = useStateI(false);

  useEffectI(() => {
    if (!runId) return;
    setStateCtx("loading");
    setData(null);
    mockApi.contextReport(runId)
      .then(d => { setData(d); setStateCtx(d.ok ? "done" : "error"); })
      .catch(e => { setData({ error: String(e) }); setStateCtx("error"); });
  }, [runId]);

  const sections = data?.sections || {};
  const recs     = Array.isArray(sections.recommendations) ? sections.recommendations : [];

  return (
    <React.Fragment>
      {/* Backdrop */}
      <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)", zIndex: 300 }} />
      {/* Modal */}
      <div style={{
        position: "fixed", top: "50%", left: "50%",
        transform: "translate(-50%,-50%)",
        zIndex: 301, width: "min(820px,92vw)", maxHeight: "85vh",
        background: "#122033", border: "1px solid #0ea5a3", borderRadius: 12,
        display: "flex", flexDirection: "column", overflow: "hidden",
      }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "14px 18px", borderBottom: "1px solid #23364e", flexShrink: 0 }}>
          <div>
            <span style={{ fontSize: 15, fontWeight: 700, color: "#0ea5a3" }}>🧠 Context Report</span>
            <span style={{ fontSize: 11, color: "#9fb0c8", fontFamily: "ui-monospace,Menlo,monospace", marginLeft: 10 }}>{runId?.slice(0, 12)}</span>
          </div>
          <span onClick={onClose} style={{ cursor: "pointer", fontSize: 18, color: "#9fb0c8", lineHeight: 1 }}>✕</span>
        </div>

        {/* Body */}
        <div style={{ overflowY: "auto", padding: "16px 18px", flex: 1 }}>

          {/* Loading */}
          {state === "loading" && (
            <div style={{ textAlign: "center", padding: "40px 0", color: "#9fb0c8", fontSize: 13 }}>
              <div style={{ fontSize: 22, marginBottom: 10 }}>⏳</div>
              Analyzing execution context…
            </div>
          )}

          {/* Error */}
          {state === "error" && (
            <div style={{ background: "#2d1515", border: "1px solid #ef4444", borderRadius: 8, padding: 14, color: "#ef4444", fontSize: 13 }}>
              <strong>Analysis failed:</strong> {data?.error || "Unknown error"}
            </div>
          )}

          {/* Done */}
          {state === "done" && (
            <React.Fragment>
              {/* Execution Summary */}
              {run && (
                <React.Fragment>
                  <div style={ctxSectionTitle}>Execution Summary</div>
                  <div style={{ background: "#0f1b2e", borderRadius: 8, padding: 12, fontSize: 12, color: "#e6edf7", fontFamily: "ui-monospace,Menlo,monospace", marginBottom: 14 }}>
                    <div><span style={{ color: "#9fb0c8" }}>command  </span>{run.command_id}</div>
                    <div><span style={{ color: "#9fb0c8" }}>status   </span><span style={{ color: run.status === "succeeded" ? "#22c55e" : run.status === "failed" ? "#ef4444" : "#f59e0b" }}>{run.status}</span></div>
                    <div><span style={{ color: "#9fb0c8" }}>exit code</span> {run.exit_code ?? "—"}</div>
                    {data.model && <div style={{ marginTop: 6, color: "#6b7a93" }}>model: {data.model} · symbols: {data.code_context_count ?? 0}</div>}
                  </div>
                </React.Fragment>
              )}

              {/* Root Cause */}
              {sections.root_cause && (
                <React.Fragment>
                  <div style={ctxSectionTitle}>Root Cause</div>
                  <div style={ctxBox}>{sections.root_cause}</div>
                </React.Fragment>
              )}

              {/* Architecture Notes */}
              {sections.architecture_notes && (
                <React.Fragment>
                  <div style={ctxSectionTitle}>Architecture Notes</div>
                  <div style={ctxBox}>{sections.architecture_notes}</div>
                </React.Fragment>
              )}

              {/* Artifact Analysis */}
              {sections.artifact_analysis && (
                <React.Fragment>
                  <div style={ctxSectionTitle}>Artifact Analysis</div>
                  <div style={ctxBox}>{sections.artifact_analysis}</div>
                </React.Fragment>
              )}

              {/* Recommendations */}
              {recs.length > 0 && (
                <React.Fragment>
                  <div style={ctxSectionTitle}>Recommendations</div>
                  <ol style={{ margin: "0 0 14px 0", paddingLeft: 22 }}>
                    {recs.map((r, i) => (
                      <li key={i} style={{ fontSize: 13, color: "#e6edf7", padding: "3px 0" }}>{r}</li>
                    ))}
                  </ol>
                </React.Fragment>
              )}

              {/* Code Context — collapsible */}
              {(data.code_context_count ?? 0) > 0 && (
                <React.Fragment>
                  <div style={{ ...ctxSectionTitle, cursor: "pointer", userSelect: "none" }} onClick={() => setOpenCode(v => !v)}>
                    Code Context {openCode ? "▲" : "▼"}
                    <span style={{ fontSize: 11, color: "#9fb0c8", marginLeft: 8 }}>{data.code_context_count} symbol{data.code_context_count !== 1 ? "s" : ""} extracted</span>
                  </div>
                  {openCode && (
                    <div style={{ fontSize: 11, color: "#9fb0c8", fontStyle: "italic", marginBottom: 8 }}>
                      (Code context is embedded in the prompt sent to Claude — expand here for reference only)
                    </div>
                  )}
                </React.Fragment>
              )}

              {data.parse_warning && (
                <div style={{ marginTop: 10, fontSize: 11, color: "#f59e0b" }}>⚠ {data.parse_warning}</div>
              )}
            </React.Fragment>
          )}
        </div>

        {/* Footer */}
        <div style={{ padding: "10px 18px", borderTop: "1px solid #23364e", display: "flex", justifyContent: "flex-end", flexShrink: 0 }}>
          <Button onClick={onClose}>Close</Button>
        </div>
      </div>
    </React.Fragment>
  );
}

const ctxSectionTitle = { fontSize: 12, fontWeight: 700, color: "#0ea5a3", textTransform: "uppercase", letterSpacing: ".08em", marginBottom: 6, marginTop: 0 };
const ctxBox = { background: "#0f1b2e", borderRadius: 8, padding: 12, fontSize: 13, color: "#e6edf7", lineHeight: 1.6, marginBottom: 14, whiteSpace: "pre-wrap", wordBreak: "break-word" };

window.ContextModal = ContextModal;
window.InspectorPanel = InspectorPanel;
