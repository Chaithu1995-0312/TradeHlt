const { useEffect, useRef } = React;

// Mermaid node → command id (M5 NodeContextDrawer). Faithful to registry.WORKFLOW_STAGE_ORDER:
// Data Prep → Tuning → Model Training → Validation & Promotion → Replay & Backtest → Live Runner.
const NODE_TO_CMD = {
  AV: "data.fetch_alphavantage", HB: "data.fetch_hummingbot", D1: "data.prepare_data",
  T1: "tuning.auto_tuner_multi", CV: "validation.config_validator", P1: "promotion.manager",
  AT: "training.auto_train", DZ: "training.discover_zones",
  BR: "training.build_rr_dataset", TRR: "training.train_rr_model",
  BT: "backtest.v2",
  L1: "live.inout_runner", G1: "governance.orchestrator",
};
const CMDS = Object.values(NODE_TO_CMD).sort((a, b) => b.length - a.length);
// Orthogonal side-subsystem nodes → flow (M6 Explorer). Keyed by a label substring.
const FLOW_LABELS = { "Research": "research", "AI Agent": "agent", "Telemetry": "telemetry" };

function WorkflowPanel({ onNode, onFlow }) {
  const ref = useRef(null);

  const diagram = `
flowchart TB
  %% ── Data Prep ─────────────────────────────────────────────────
  AV["data.fetch_alphavantage\\n8 forex pairs"]
  HB["data.fetch_hummingbot\\n3 crypto pairs"]
  D1["data.prepare_data\\nNormalize raw CSVs → M15"]
  AV -->|data/*.csv| D1
  HB -->|data/*.csv| D1

  %% ── Tuning → Validation & Promotion ───────────────────────────
  subgraph VP [" Tuning → Validation & Promotion "]
    direction TB
    T1["tuning.auto_tuner_multi\\nGrid-search CRT params\\n→ checkpoint_multi.json"]
    CV["validation.config_validator\\nQuality gates (runs backtests)"]
    P1["promotion.manager\\n→ configs/production/v*.json"]
    T1 -->|checkpoint_multi.json| CV
    CV -->|APPROVE| P1
  end
  D1 -->|"*_M15.csv"| T1

  %% ── Model Training ────────────────────────────────────────────
  subgraph ML [" Model Training "]
    direction TB
    AT["training.auto_train\\n(wraps: opportunity_scanner\\n+ phase5_calibration\\n+ promote_gaussian)"]
    DZ["training.discover_zones"]
    BR["training.build_rr_dataset"]
    TRR["training.train_rr_model"]
    AT -->|opportunities.jsonl| DZ
    AT -->|opportunities.jsonl| BR
    BR -->|rr_dataset.json| TRR
  end
  D1 -->|"*_M15.csv"| AT

  %% ── Replay & Backtest (validate on history before live) ───────
  subgraph RB [" Replay & Backtest "]
    BT["backtest.v2\\nCRT spine per candle\\n→ summary.json / trades.csv"]
  end
  P1 -->|production_config.json| BT
  AT -->|gaussian_registry.json| BT
  DZ -->|zone_registry.json| BT
  TRR -->|rr_model.json| BT
  D1 -->|"*_M15.csv"| BT

  %% ── Live + Governance ─────────────────────────────────────────
  L1["live.inout_runner\\nMulti-instrument live loop"]
  G1["governance.orchestrator\\n(wraps: ShadowPromotionGate\\n+ BitNet LLM)"]
  P1 -->|production_config.json| L1
  AT -->|gaussian_registry.json| L1
  BT -.->|validated| L1
  L1 -.->|flow_collector.log| G1
  G1 -.->|shadow promote| L1

  %% ── Orthogonal subsystems (not pipeline stages — open the Explore tab) ──
  subgraph SS [" Orthogonal subsystems "]
    direction LR
    RS["Research / Edge Discovery\\n(isolated; reads data)"]
    AG["AI Agent\\n(orchestrates via PLAN_REGISTRY)"]
    TE["Telemetry / Event-Bus\\n(all services emit)"]
  end
  D1 -.->|M15| RS
  L1 -.->|events| TE

  %% ── Styles ────────────────────────────────────────────────────
  classDef compound fill:#d0e8ff,stroke:#0057b7,stroke-width:2px
  classDef source fill:#fff8e6,stroke:#b87d00,stroke-width:1px
  classDef live fill:#e6ffe6,stroke:#3a8a00,stroke-width:2px
  classDef side fill:#241f33,stroke:#7a6ca8,stroke-width:1px,color:#cdb8ff
  class AT,P1 compound
  class AV,HB source
  class L1,G1 live
  class RS,AG,TE side
`;

  useEffect(() => {
    if (!ref.current || !window.mermaid) return;
    const host = ref.current;
    window.mermaid.initialize({ startOnLoad: false, theme: "dark", securityLevel: "loose" });
    host.removeAttribute("data-processed");
    host.innerHTML = diagram;
    Promise.resolve(window.mermaid.run({ nodes: [host] })).then(() => {
      host.querySelectorAll(".node").forEach(n => {
        const t = n.textContent || "";
        if (CMDS.some(c => t.includes(c)) || Object.keys(FLOW_LABELS).some(k => t.includes(k))) n.style.cursor = "pointer";
      });
    }).catch(() => {});

    // Delegated, Mermaid-version-independent click routing: command nodes → onNode (M5 drawer);
    // orthogonal side-subsystem nodes → onFlow (M6 Explore). Matched by node label text.
    const handler = (e) => {
      const nodeEl = e.target.closest && e.target.closest(".node");
      if (!nodeEl) return;
      const text = nodeEl.textContent || "";
      const cmd = CMDS.find(c => text.includes(c));
      if (cmd) { if (onNode) onNode(cmd); return; }
      const key = Object.keys(FLOW_LABELS).find(k => text.includes(k));
      if (key && onFlow) onFlow(FLOW_LABELS[key]);
    };
    host.addEventListener("click", handler);
    return () => host.removeEventListener("click", handler);
  }, []);

  return (
    <div style={{ padding: "16px", overflowY: "auto", height: "calc(100vh - 56px)" }}>
      <h2 style={{ marginBottom: "8px", fontSize: "14px", fontWeight: 600, color: "#58a6ff" }}>
        Pipeline Workflow
      </h2>
      <p style={{ fontSize: "11px", color: "#9fb0c8", marginBottom: "16px", margin: "0 0 16px" }}>
        Blue = compound scripts &nbsp;|&nbsp; Solid = file handoff &nbsp;|&nbsp; Dashed = feedback / cross-cutting &nbsp;|&nbsp; <span style={{ color: "#0ea5a3" }}>Click a pipeline node → code + run + docs</span> &nbsp;·&nbsp; <span style={{ color: "#cdb8ff" }}>a side subsystem → Explore</span>
      </p>
      <div className="mermaid" ref={ref} style={{ background: "transparent" }} />
    </div>
  );
}
window.WorkflowPanel = WorkflowPanel;
