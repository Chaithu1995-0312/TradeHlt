// Page 7 — Intelligence (NEW)
// Causal Network · Sequential Patterns · Market State Machine

function IntelligencePage({ activeSub, selectedInstrument }) {
  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Intelligence</div>
          <div className="page-sub">
            Causal Graph · Sequential Patterns · Market State Machine
            <span className="muted" style={{ marginLeft:8, fontSize:10 }}>Global data · not instrument-filtered</span>
          </div>
        </div>
        <div style={{ display:"flex", gap:8, alignItems:"center" }}>
          {selectedInstrument && (
            <span style={{ fontSize:11, color:"var(--accent)", padding:"2px 8px", border:"1px solid rgba(34,211,238,.3)", borderRadius:6, background:"rgba(34,211,238,.07)" }}>
              {selectedInstrument}
            </span>
          )}
          <div style={{ fontSize:11, color:"var(--accent)" }}>● Unbiased Analysis Mode</div>
        </div>
      </div>

      {/* Row 1: Causal Network + Sequential Patterns */}
      <div className="row" style={{ gridTemplateColumns:"1.1fr 0.9fr", marginBottom:14 }}>

        {/* Causal Network Graph (pure SVG) */}
        <div className="card">
          <div className="card-title">Intelligence Graph <span className="right muted">Causal Network</span></div>
          <svg width="100%" viewBox="0 0 480 260" style={{ display:"block" }}>
            {/* Edges */}
            {[
              [240,130, 100,60],  // CRT v5 → Cluster Drift
              [240,130, 100,200], // CRT v5 → Sweep
              [240,130, 240,210], // CRT v5 → Range
              [240,130, 380,60],  // CRT v5 → Pattern
              [380,60,  380,200], // Pattern → TP2 Hit
              [100,60,  100,200], // Cluster Drift → Sweep
              [240,210, 380,200], // Range → TP2 Hit
              [100,200, 240,210], // Sweep → Range
            ].map(([x1,y1,x2,y2], i) => (
              <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
                stroke="rgba(34,211,238,.25)" strokeWidth="1.5" />
            ))}
            {/* Edge labels */}
            <text x="148" y="78"  fontSize="9" fill="#7f8da6" textAnchor="middle">0.62</text>
            <text x="148" y="178" fontSize="9" fill="#7f8da6" textAnchor="middle">0.41</text>
            <text x="240" y="180" fontSize="9" fill="#7f8da6" textAnchor="middle">0.38</text>
            <text x="322" y="78"  fontSize="9" fill="#7f8da6" textAnchor="middle">0.71</text>
            <text x="380" y="135" fontSize="9" fill="#7f8da6" textAnchor="middle">0.55</text>
            {/* Nodes */}
            {[
              { x:240, y:130, label:"CRT v5",       r:30, color:"#22d3ee", textColor:"#0f1724", bold:true },
              { x:100, y:60,  label:"Cluster Drift", r:22, color:"#a78bfa", textColor:"#fff",   bold:false },
              { x:100, y:200, label:"Sweep",         r:22, color:"#22c55e", textColor:"#fff",   bold:false },
              { x:240, y:210, label:"Range",         r:22, color:"#facc15", textColor:"#0f1724",bold:false },
              { x:380, y:60,  label:"Pattern",       r:22, color:"#f97316", textColor:"#fff",   bold:false },
              { x:380, y:200, label:"TP2 Hit",       r:22, color:"#22c55e", textColor:"#fff",   bold:false },
              { x:60,  y:130, label:"SL",            r:16, color:"#ef4444", textColor:"#fff",   bold:false },
            ].map(n => (
              <g key={n.label}>
                <circle cx={n.x} cy={n.y} r={n.r} fill={n.color} opacity="0.92" />
                <text x={n.x} y={n.y + 1} textAnchor="middle" dominantBaseline="middle"
                  fontSize={n.r > 25 ? 10 : 8} fontWeight={n.bold ? 800 : 600}
                  fill={n.textColor}>{n.label}</text>
              </g>
            ))}
          </svg>
          <div className="muted" style={{ fontSize:10, marginTop:6 }}>Edge weights = conditional probability of causal link (bootstrap CI 95%)</div>
        </div>

        {/* Sequential Pattern Explorer */}
        <div className="card">
          <div className="card-title">Sequential Pattern Explorer</div>
          <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
            {(window.SEQ_PATTERNS || []).map((p, i) => (
              <div key={i} style={{
                padding:"10px 12px", background:"var(--panel-2)",
                border:"1px solid var(--line)", borderRadius:8,
              }}>
                <div style={{ display:"flex", gap:5, flexWrap:"wrap", marginBottom:6 }}>
                  {p.chain.map((step, j, arr) => (
                    <React.Fragment key={j}>
                      <span style={{
                        fontSize:10, padding:"2px 8px", borderRadius:12, fontWeight:600,
                        background:"rgba(34,211,238,.12)", color:"var(--accent)",
                        border:"1px solid rgba(34,211,238,.3)",
                      }}>{step}</span>
                      {j < arr.length - 1 && <span style={{ color:"var(--muted)", fontSize:10, alignSelf:"center" }}>→</span>}
                    </React.Fragment>
                  ))}
                </div>
                <div style={{ display:"flex", justifyContent:"space-between", fontSize:11 }}>
                  <span className="muted">Win Rate: <span style={{ color:p.color, fontWeight:700 }}>{p.rate}</span></span>
                  <span className="muted">n = <span className="mono">{(p.n||0).toLocaleString()}</span></span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Row 2: Market State Machine */}
      <div className="card">
        <div className="card-title">Market State Machine <span className="right muted">Transition Probabilities</span></div>
        <div style={{ display:"grid", gridTemplateColumns:"220px 1fr", gap:20, alignItems:"center" }}>

          {/* SVG circle of states */}
          <svg width="220" height="220" viewBox="0 0 220 220">
            {/* Center hub */}
            <circle cx="110" cy="110" r="28" fill="rgba(34,211,238,.15)" stroke="#22d3ee" strokeWidth="1.5" />
            <text x="110" y="107" textAnchor="middle" fontSize="9" fontWeight="700" fill="#22d3ee">CRT</text>
            <text x="110" y="118" textAnchor="middle" fontSize="9" fontWeight="700" fill="#22d3ee">Engine</text>
            {/* State nodes around the circle */}
            {[
              { label:"Range",        x:110, y:22,  color:"#facc15" },
              { label:"Trending",     x:197, y:66,  color:"#22c55e" },
              { label:"Volatile",     x:197, y:155, color:"#ef4444" },
              { label:"Low Vol",      x:110, y:198, color:"#a78bfa" },
              { label:"Breakout",     x:23,  y:155, color:"#f97316" },
              { label:"Sweep Zone",   x:23,  y:66,  color:"#22d3ee" },
            ].map(s => (
              <g key={s.label}>
                <line x1="110" y1="110" x2={s.x} y2={s.y} stroke="rgba(255,255,255,.08)" strokeWidth="1" />
                <circle cx={s.x} cy={s.y} r="20" fill={s.color} opacity="0.85" />
                <text x={s.x} y={s.y + 1} textAnchor="middle" dominantBaseline="middle"
                  fontSize="7" fontWeight="700" fill="#0f1724">{s.label}</text>
              </g>
            ))}
          </svg>

          {/* Probability table */}
          <table className="state-table">
            <thead>
              <tr>
                <th>Current State</th>
                <th>Next: Range</th>
                <th>Next: Trending</th>
                <th>Next: Volatile</th>
                <th>Hold Prob</th>
              </tr>
            </thead>
            <tbody>
              {[
                { state:"Range",     r:"—",   t:"0.31", v:"0.22", h:"0.47" },
                { state:"Trending",  r:"0.18",t:"—",    v:"0.29", h:"0.53" },
                { state:"Volatile",  r:"0.34",t:"0.24", v:"—",    h:"0.42" },
                { state:"Low Vol",   r:"0.41",t:"0.19", v:"0.12", h:"0.28" },
                { state:"Breakout",  r:"0.21",t:"0.45", v:"0.18", h:"0.16" },
                { state:"Sweep Zone",r:"0.28",t:"0.22", v:"0.31", h:"0.19" },
              ].map(r => (
                <tr key={r.state}>
                  <td><span className="tag normal" style={{ fontSize:10 }}>{r.state}</span></td>
                  <td className="mono">{r.r}</td>
                  <td className="mono">{r.t}</td>
                  <td className="mono">{r.v}</td>
                  <td className="mono" style={{ color:"var(--accent)", fontWeight:600 }}>{r.h}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
window.IntelligencePage = IntelligencePage;
