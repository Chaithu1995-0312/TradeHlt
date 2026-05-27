// AgentPanel.jsx — Agent-as-driver view + findings tail + audit tail
const { useEffect, useRef, useState, useCallback } = React;

const _agentDiagram = `
flowchart TB
  USER([User / Trader])
  subgraph AGENT_LAYER [" Agent Layer (agent.cli REPL) "]
    direction TB
    A["agent.cli\\nNatural-language REPL"]
    IR["IntentRouter\\nregex → LLM fallback"]
    PC["PlanCompiler\\nPLAN_REGISTRY (17 intents)"]
    EX["Executor\\nconfirm-gate + path-guard"]
    FS["FindingsSynthesizer\\nGroq llama-3.1-70b"]
    A --> IR --> PC --> EX
    EX -.->|on demand| FS
  end

  subgraph CRT_PIPE [" CRT Pipeline (see Workflow tab) "]
    direction LR
    DATA["Data Prep"] --> TUNE["CRT Tuning + Promotion"]
    DATA --> ML["ML Model Training"]
    TUNE --> LIVE["Live Runner"]
    ML --> LIVE
    LIVE -.-> GOV["Governance"]
  end

  USER -->|"types prompt"| A
  EX -->|"dispatch CommandSpec"| CRT_PIPE
  CRT_PIPE -->|"artifacts: logs/, results/, models/"| FS
  FS -->|"append"| FINDINGS[("logs/agent_findings.jsonl")]
  EX -->|"append"| AUDIT[("logs/agent_audit.jsonl")]
  FS -->|"LLM prompts (redacted)"| LLMREQ[("logs/agent_llm_requests.jsonl")]
  FINDINGS -.->|"on-demand recall"| A
  A -->|"reply + alerts"| USER

  classDef agent fill:#ffcc88,stroke:#a86200,stroke-width:2px,color:#000
  classDef pipe fill:#d0e8ff,stroke:#0057b7,stroke-width:1px,color:#000
  classDef store fill:#f0f0f0,stroke:#666,stroke-width:1px,color:#000
  class A,IR,PC,EX,FS agent
  class DATA,TUNE,ML,LIVE,GOV pipe
  class FINDINGS,AUDIT,LLMREQ store
`;

function _Badge({ children, color }) {
  return (
    <span style={{
      display: "inline-block", padding: "1px 6px", borderRadius: 3,
      background: color, color: "#0f1724", fontSize: 10, fontWeight: 600,
      marginRight: 4,
    }}>{children}</span>
  );
}

function _StatusBadge({ status }) {
  const map = {
    completed:             "#7ee787",
    failed:                "#ff7b72",
    running:               "#58a6ff",
    synthesis_unavailable: "#d29922",
    run_not_found:         "#ff7b72",
    disabled_in_config:    "#9fb0c8",
    invalid_input:         "#ff7b72",
  };
  return <_Badge color={map[status] || "#9fb0c8"}>{status || "?"}</_Badge>;
}

function _FindingsList({ findings }) {
  if (!findings || findings.length === 0) {
    return <div style={{ color: "#9fb0c8", fontSize: 11, padding: 8 }}>
      No findings yet. From the REPL: <code style={{ background: "#1a2438", padding: "1px 4px" }}>synthesize run &lt;run_id&gt;</code>
    </div>;
  }
  return (
    <div style={{ overflowY: "auto", maxHeight: 240, fontSize: 11 }}>
      {findings.map((f, i) => (
        <div key={i} style={{ borderBottom: "1px solid #1a2438", padding: "6px 8px" }}>
          <div style={{ display: "flex", gap: 6, alignItems: "baseline", flexWrap: "wrap" }}>
            <_StatusBadge status={f.status} />
            <code style={{ color: "#58a6ff" }}>{(f.run_id || "").slice(0, 8)}</code>
            <span style={{ color: "#9fb0c8" }}>{f.command_id || "—"}</span>
            <span style={{ marginLeft: "auto", color: "#666", fontSize: 10 }}>{f.ts}</span>
          </div>
          {f.summary && (
            <div style={{ marginTop: 4, color: "#e6edf7" }}>{f.summary}</div>
          )}
          {(f.anomalies && f.anomalies.length > 0) && (
            <ul style={{ marginTop: 4, marginBottom: 0, paddingLeft: 18, color: "#d29922" }}>
              {f.anomalies.map((a, j) => <li key={j}>{a}</li>)}
            </ul>
          )}
          {(f.recommended_next && f.recommended_next.length > 0) && (
            <ul style={{ marginTop: 4, marginBottom: 0, paddingLeft: 18, color: "#7ee787" }}>
              {f.recommended_next.map((r, j) => <li key={j}>→ {r}</li>)}
            </ul>
          )}
          {f.error && (
            <div style={{ marginTop: 4, color: "#ff7b72", fontSize: 10 }}>error: {f.error}</div>
          )}
        </div>
      ))}
    </div>
  );
}

function _AuditList({ audit }) {
  if (!audit || audit.length === 0) {
    return <div style={{ color: "#9fb0c8", fontSize: 11, padding: 8 }}>No agent activity yet.</div>;
  }
  return (
    <div style={{ overflowY: "auto", maxHeight: 240, fontSize: 11, fontFamily: "monospace" }}>
      {audit.map((a, i) => (
        <div key={i} style={{ borderBottom: "1px solid #1a2438", padding: "4px 8px" }}>
          <span style={{ color: "#666" }}>{(a.ts || "").slice(11, 19)}</span>{" "}
          {a.tool && (
            <>
              <_Badge color={a.write ? "#ff7b72" : "#7ee787"}>{a.write ? "W" : "R"}</_Badge>
              <span style={{ color: "#58a6ff" }}>{a.tool}</span>{" "}
              <span style={{ color: a.outcome === "success" ? "#7ee787" : "#ff7b72" }}>{a.outcome}</span>{" "}
              <span style={{ color: "#9fb0c8" }}>{a.latency_ms}ms</span>
            </>
          )}
          {!a.tool && a.intent && (
            <span style={{ color: "#d29922" }}>SESSION {a.intent_key} → {a.outcome}</span>
          )}
        </div>
      ))}
    </div>
  );
}

function AgentPanel() {
  const ref = useRef(null);
  const [findings, setFindings] = useState([]);
  const [audit, setAudit]       = useState([]);
  const [tab, setTab]           = useState("findings");

  const refresh = useCallback(() => {
    fetch("/api/agent/findings?limit=20")
      .then(r => r.ok ? r.json() : { findings: [] })
      .then(j => setFindings(j.findings || []))
      .catch(() => {});
    fetch("/api/agent/audit?limit=30")
      .then(r => r.ok ? r.json() : { audit: [] })
      .then(j => setAudit(j.audit || []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!ref.current || !window.mermaid) return;
    window.mermaid.initialize({ startOnLoad: false, theme: "dark" });
    ref.current.removeAttribute("data-processed");
    ref.current.innerHTML = _agentDiagram;
    window.mermaid.run({ nodes: [ref.current] });
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const tabBtn = (key, label) => (
    <button
      onClick={() => setTab(key)}
      style={{
        background: tab === key ? "#1a2438" : "transparent",
        color: tab === key ? "#58a6ff" : "#9fb0c8",
        border: "1px solid #23364e", padding: "4px 10px",
        borderRadius: 4, cursor: "pointer", fontSize: 11, fontWeight: 600,
      }}>{label}</button>
  );

  return (
    <div style={{ padding: 16, overflowY: "auto", height: "calc(100vh - 56px)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
        <h2 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: "#58a6ff" }}>
          Agent — Post-Run Findings &amp; Audit
        </h2>
        <button onClick={refresh}
          style={{ background: "#1a2438", color: "#58a6ff", border: "1px solid #23364e",
                   padding: "4px 10px", borderRadius: 4, cursor: "pointer", fontSize: 11 }}>
          ↻ Refresh
        </button>
      </div>
      <p style={{ fontSize: 11, color: "#9fb0c8", margin: "0 0 12px" }}>
        Agent.cli wraps every CRT command. On-demand findings via Groq Llama-3.1-70b.
        REPL: <code style={{ background: "#1a2438", padding: "1px 4px" }}>python -m src.agent.cli</code>
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 480px", gap: 14 }}>
        <div className="mermaid" ref={ref} style={{ background: "transparent", overflow: "auto" }} />

        <div style={{ background: "rgba(0,0,0,.2)", borderRadius: 6, border: "1px solid #23364e", padding: 8 }}>
          <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
            {tabBtn("findings", `Findings (${findings.length})`)}
            {tabBtn("audit",    `Audit (${audit.length})`)}
          </div>
          {tab === "findings" ? <_FindingsList findings={findings} /> : <_AuditList audit={audit} />}
        </div>
      </div>
    </div>
  );
}
window.AgentPanel = AgentPanel;
