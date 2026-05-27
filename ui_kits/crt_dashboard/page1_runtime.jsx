// Page 1 — Runtime / Live Trading Dashboard

function RuntimePage({ activeSub, status, equity, trades, selectedInstrument }) {
  // Build KPI shape from backend status (with static scaffold fallbacks)
  const s  = status || {};
  const ks = s.kill_switch || {};
  const k  = {
    activeModel:  s.active_model_version || "—",
    modelKind:    "Gaussian",
    killSwitch:   ks.tripped ? "TRIPPED" : "SAFE",
    convergence:  { value: s.active_model_corr != null ? (+s.active_model_corr).toFixed(4) : "—",
                    label: s.active_model_corr > 0.05 ? "Good" : s.active_model_corr > 0.01 ? "Low" : "Poor" },
    regime:       { value: "NORMAL", sub: "Auto" },
    trades24h:    { value: s.trades_last_24h || 0, sub: "" },
    pnl24h:       0,
  };
  const sp = window.SIGNAL_PIPELINE || [];
  const ev = window.EVENT_STREAM    || [];
  const as = window.ACTIVE_SIGNALS  || {};

  const kConvergenceVal = k.convergence
    ? (typeof k.convergence.value === "number"
        ? k.convergence.value.toFixed(4)
        : k.convergence.value)
    : "—";
  const kConvergenceLbl = k.convergence ? k.convergence.label : "—";

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Runtime / Live Trading Dashboard</div>
          <div className="page-sub">Live Execution · Model Fusion · Real-time State</div>
        </div>
        <div className="tb-pill"><span className="live-dot"></span>Connected — 15:35:42 UTC</div>
      </div>

      {/* Signal Pipeline */}
      <div className="card" style={{ marginBottom:14 }}>
        <div className="card-title">Signal Pipeline</div>
        <div className="signal-pipeline">
          {sp.map((stage, i) => (
            <React.Fragment key={stage.name}>
              <div className="pipeline-stage">
                <div className="ps-icon">{stage.icon}</div>
                <div className="ps-name">{stage.name}</div>
                <div className="ps-val">{stage.val}</div>
                <div className="ps-status" style={{ color: stage.status === "ok" ? "var(--ok)" : "var(--bad)" }}>
                  {stage.status === "ok" ? "●" : "✗"}
                </div>
              </div>
              {i < sp.length - 1 && <div className="pipeline-arrow">→</div>}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* KPI Strip */}
      <div className="kpis" style={{ marginBottom:14 }}>
        <Kpi label="Active Model"  value={k.activeModel || "—"} sub={k.modelKind || ""} />
        <Kpi label="Kill Switch"   pill={{ kind: k.killSwitch === "TRIPPED" ? "danger" : "safe", text: k.killSwitch || "SAFE" }} />
        <Kpi label="Convergence"   tone="num" value={kConvergenceVal} sub={kConvergenceLbl} />
        <Kpi label="Regime"        pill={{ kind: "live", text: (k.regime && k.regime.value) || "NORMAL" }} sub={(k.regime && k.regime.sub) || ""} />
        <Kpi label="Trades (24h)"  value={(k.trades24h && k.trades24h.value) || 0} sub={(k.trades24h && k.trades24h.sub) || ""} />
        <Kpi label="Daily PnL (R)" tone="pos" value={`+${(k.pnl24h || 0).toFixed(2)}`} />
      </div>

      {/* Charts row */}
      <div className="row" style={{ gridTemplateColumns:"1.15fr 0.85fr 1.3fr", marginBottom:14 }}>
        <div className="card">
          <div className="card-title">Model Fusion Score</div>
          <div style={{ display:"grid", gridTemplateColumns:"150px 1fr", gap:14, alignItems:"center" }}>
            <DonutChart segments={window.FUSION_SEGMENTS || []} centerLabel="0.82" centerSub="High Confidence" />
            <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
              {(window.FUSION_SEGMENTS || []).map(s => (
                <div key={s.label} style={{ display:"flex", justifyContent:"space-between", fontSize:12 }}>
                  <span style={{ color:"#b6c0d6" }}>
                    <span style={{ display:"inline-block", width:7, height:7, borderRadius:"50%", background:s.color, marginRight:7 }} />
                    {s.label}
                  </span>
                  <span className="mono" style={{ color:"#e6edf7" }}>{s.value.toFixed(2)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-title">Live Signal <span className="right muted" style={{fontSize:10}}>{selectedInstrument || "—"}</span></div>
          {as.topSignal ? (
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", rowGap:10, columnGap:10, fontSize:12 }}>
              <div>
                <div className="muted" style={{ fontSize:11 }}>Direction</div>
                <div style={{ color:"#22c55e", fontWeight:700, fontSize:15 }}>LONG ↗</div>
              </div>
              <div>
                <div className="muted" style={{ fontSize:11 }}>Entry</div>
                <div className="mono" style={{ fontWeight:600, fontSize:14 }}>{as.topSignal.entry}</div>
              </div>
              <div>
                <div className="muted" style={{ fontSize:11 }}>Confidence</div>
                <div className="cyan" style={{ fontWeight:700, fontSize:14 }}>{as.topSignal.conf.toFixed(2)}</div>
              </div>
              <div>
                <div className="muted" style={{ fontSize:11 }}>Expected RR</div>
                <div className="cyan" style={{ fontWeight:700, fontSize:14 }}>{as.topSignal.rr.toFixed(2)}</div>
              </div>
              <div>
                <div className="muted" style={{ fontSize:11 }}>Instrument</div>
                <div className="mono">{as.topSignal.inst}</div>
              </div>
              <div>
                <div className="muted" style={{ fontSize:11 }}>Stop</div>
                <div className="mono neg">{as.topSignal.stop}</div>
              </div>
              <div>
                <div className="muted" style={{ fontSize:11 }}>Active Signals</div>
                <div className="mono">{as.count || 0}</div>
              </div>
              <div>
                <div className="muted" style={{ fontSize:11 }}>Long / Short</div>
                <div className="mono">{as.long || 0} / {as.short || 0}</div>
              </div>
            </div>
          ) : (
            <div className="muted" style={{ fontSize:12, padding:"12px 0" }}>No active signals</div>
          )}
        </div>

        <div className="card">
          <div className="card-title">Equity Curve (R) <span className="right">All Time ▾</span></div>
          <LineChart values={equity || []} color="#22d3ee" height={170} />
        </div>
      </div>

      {/* Event Stream */}
      <div className="row" style={{ gridTemplateColumns:"1.3fr 0.7fr", marginBottom:14 }}>
        <div className="card">
          <div className="card-title">Event Stream <span className="right">Live ●</span></div>
          <table className="dt">
            <thead><tr><th>Time</th><th>Event</th><th>Instrument</th><th>Status</th><th>Latency</th></tr></thead>
            <tbody>
              {ev.map((e, i) => (
                <tr key={i}>
                  <td className="mono">{e.time}</td>
                  <td>{e.event}</td>
                  <td className="mono">{e.inst}</td>
                  <td><span style={{ color: e.status === "ok" ? "var(--ok)" : "var(--bad)", fontSize:11 }}>●</span></td>
                  <td className="mono muted">{e.latency}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <div className="card-title">Queue Depths</div>
          <div style={{ display:"flex", flexDirection:"column", gap:10, marginTop:6 }}>
            {Object.entries(window.QUEUE_DEPTHS || {}).map(([k, v]) => (
              <div key={k} style={{ display:"flex", justifyContent:"space-between", fontSize:12 }}>
                <span className="muted" style={{ textTransform:"capitalize" }}>{k}</span>
                <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                  <div style={{ width:80, height:6, background:"var(--panel-3)", borderRadius:3, overflow:"hidden" }}>
                    <div style={{ width:`${Math.min(100, v * 20)}%`, height:"100%", background:"var(--accent)", borderRadius:3 }} />
                  </div>
                  <span className="mono">{v}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Trades */}
      <div className="card">
        <div className="card-title">Recent Trades</div>
        <table className="dt">
          <thead><tr><th>ID</th><th>Time</th><th>Dir</th><th>Entry</th><th>Exit</th><th>RR (R)</th><th>Result</th><th>Model Conf</th><th>Regime</th></tr></thead>
          <tbody>
            {(trades || []).slice(0, 10).map(t => (
              <tr key={t.id}>
                <td className="mono">{t.id}</td>
                <td className="mono">{t.time}</td>
                <td><span className={`tag ${t.dir === "LONG" ? "long" : "short"}`}>{t.dir}</span></td>
                <td className="mono">{t.entry}</td>
                <td className="mono">{t.exit}</td>
                <td className={`mono ${t.rr > 0 ? "pos" : "neg"}`}>{t.rr > 0 ? "+" : ""}{t.rr.toFixed(2)}</td>
                <td><span className={`tag ${t.result === "TP" ? "tp" : "sl"}`}>{t.result}</span></td>
                <td className="mono">{t.conf.toFixed(2)}</td>
                <td><span className="tag normal">{t.regime}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
window.RuntimePage = RuntimePage;
