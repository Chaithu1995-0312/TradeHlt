const { useEffect, useRef } = React;

function WorkflowPanel() {
  const ref = useRef(null);

  const diagram = `
flowchart TB
  %% ── Data Sources ──────────────────────────────────────────────
  AV["data.fetch_alphavantage\\n8 forex pairs"]
  HB["data.fetch_hummingbot\\n3 crypto pairs"]
  D1["data.prepare_data\\nNormalize raw CSVs → M15"]

  AV -->|data/*.csv| D1
  HB -->|data/*.csv| D1

  %% ── CRT Hyperparameter Loop ───────────────────────────────────
  subgraph CRT [" CRT Hyperparameter Loop "]
    direction TB
    T1["tuning.auto_tuner_multi\\nGrid-search CRT params\\n→ checkpoint_multi.json"]
    P1["promotion.manager\\n(wraps: ConfigValidator)\\n→ configs/production/v*.json"]
    T1 -->|checkpoint_multi.json| P1
  end

  D1 -->|"*_M15.csv"| T1

  %% ── ML Model Training ─────────────────────────────────────────
  subgraph ML [" ML Model Training "]
    direction TB
    AT["training.auto_train\\n(wraps: opportunity_scanner\\n+ compress_logs\\n+ phase5_calibration\\n+ promote_gaussian)"]
    DZ["training.discover_zones"]
    BR["training.build_rr_dataset"]
    TRR["training.train_rr_model"]
    AT -->|opportunities.jsonl| DZ
    AT -->|opportunities.jsonl| BR
    BR -->|rr_dataset.json| TRR
  end

  D1 -->|"*_M15.csv"| AT

  %% ── Live + Governance ─────────────────────────────────────────
  L1["live.inout_runner\\nMulti-instrument live loop"]
  G1["governance.orchestrator\\n(wraps: ShadowPromotionGate\\n+ BitNet LLM)"]

  P1 -->|production_config.json| L1
  AT -->|gaussian_registry.json| L1
  DZ -->|zone_registry.json| L1
  TRR -->|rr_model.json| L1

  L1 -.->|flow_collector.log| G1
  G1 -.->|shadow promote| L1

  %% ── Styles ────────────────────────────────────────────────────
  classDef compound fill:#d0e8ff,stroke:#0057b7,stroke-width:2px
  classDef source fill:#fff8e6,stroke:#b87d00,stroke-width:1px
  classDef live fill:#e6ffe6,stroke:#3a8a00,stroke-width:2px
  class AT,P1 compound
  class AV,HB source
  class L1,G1 live
`;

  useEffect(() => {
    if (!ref.current || !window.mermaid) return;
    window.mermaid.initialize({ startOnLoad: false, theme: "dark" });
    ref.current.removeAttribute("data-processed");
    ref.current.innerHTML = diagram;
    window.mermaid.run({ nodes: [ref.current] });
  }, []);

  return (
    <div style={{ padding: "16px", overflowY: "auto", height: "calc(100vh - 56px)" }}>
      <h2 style={{ marginBottom: "8px", fontSize: "14px", fontWeight: 600, color: "#58a6ff" }}>
        Pipeline Workflow
      </h2>
      <p style={{ fontSize: "11px", color: "#9fb0c8", marginBottom: "16px", margin: "0 0 16px" }}>
        Blue nodes = compound scripts (wrap multiple sub-scripts internally) &nbsp;|&nbsp; Solid = file handoff &nbsp;|&nbsp; Dashed = feedback loop
      </p>
      <div className="mermaid" ref={ref} style={{ background: "transparent" }} />
    </div>
  );
}
window.WorkflowPanel = WorkflowPanel;
