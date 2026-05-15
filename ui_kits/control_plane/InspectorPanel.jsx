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

function InspectorPanel({ run, logs, artifacts, monitors }) {
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

      <SectionTitle right={<CopyBtn text={run.cmdline || ""} />}>Resolved Command</SectionTitle>
      <Pre>{run.cmdline || "—"}</Pre>

      <SectionTitle>Arguments</SectionTitle>
      <ArgsBlock args={run.args} />

      <SectionTitle right={<span style={{ fontSize: 11, color: "#9fb0c8" }}>{(run.timeline || []).length} event{(run.timeline || []).length === 1 ? "" : "s"}</span>}>Timeline</SectionTitle>
      <TimelineBlock events={run.timeline} status={run.status} />

      <SectionTitle>Monitored Fields</SectionTitle>
      <MonitoredFieldsTable fields={monitors?.fields} history={run.field_history} />

      <SectionTitle>Stdout</SectionTitle>
      <Pre>{logs?.stdout || ""}</Pre>

      <SectionTitle>Stderr</SectionTitle>
      <Pre>{logs?.stderr || ""}</Pre>

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

window.InspectorPanel = InspectorPanel;
