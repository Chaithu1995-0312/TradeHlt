// Page 8 — Replay Lab (NEW)
// Market/signal replay with candlestick chart + playback controls

function ReplayPage({ activeSub, selectedInstrument: globalInstrument }) {
  const [playing,    setPlaying]    = React.useState(false);
  const [frame,      setFrame]      = React.useState(14);  // current candle index
  const [speed,      setSpeed]      = React.useState("1×");
  // Default replay instrument to TopBar selection, but allow local override
  const [instrument, setInstrument] = React.useState(globalInstrument || "EURUSD");
  const [replayDate, setReplayDate] = React.useState("2024-04-15");

  // Sync local instrument when global changes (first load)
  React.useEffect(() => {
    if (globalInstrument && instrument === "EURUSD") setInstrument(globalInstrument);
  }, [globalInstrument]);

  // Generate deterministic OHLCV candles for the replay chart
  const N_CANDLES = 30;
  const candles = React.useMemo(() => {
    const out = [];
    let price = 1.0820;
    for (let i = 0; i < N_CANDLES; i++) {
      // Deterministic noise based on index
      const seed = ((i * 2654435761) >>> 0) / 4294967296;
      const seed2 = (((i + 13) * 2246822519) >>> 0) / 4294967296;
      const move   = (seed  - 0.5) * 0.0030;
      const wick   = seed2  * 0.0015;
      const open   = price;
      const close  = price + move;
      const high   = Math.max(open, close) + wick;
      const low    = Math.min(open, close) - wick * 0.5;
      out.push({ open, high, low, close });
      price = close;
    }
    return out;
  }, []);

  // Playback tick
  React.useEffect(() => {
    if (!playing) return;
    const speedMap = { "0.5×":2000, "1×":1000, "2×":500, "5×":200 };
    const ms = speedMap[speed] || 1000;
    const timer = setInterval(() => {
      setFrame(f => {
        if (f >= N_CANDLES - 1) { setPlaying(false); return f; }
        return f + 1;
      });
    }, ms);
    return () => clearInterval(timer);
  }, [playing, speed]);

  // SVG candlestick chart
  const W = 560, H = 200, PAD_L = 8, PAD_R = 8, PAD_T = 8, PAD_B = 8;
  const visible = candles.slice(0, frame + 1);
  const allH = visible.map(c => c.high);
  const allL = visible.map(c => c.low);
  const maxP = allH.length ? Math.max(...allH) : 1.09;
  const minP = allL.length ? Math.min(...allL) : 1.07;
  const priceRange = maxP - minP || 0.001;
  const candleW = Math.max(4, Math.floor((W - PAD_L - PAD_R) / N_CANDLES) - 2);
  const toY = p => PAD_T + ((maxP - p) / priceRange) * (H - PAD_T - PAD_B);
  const toX = i => PAD_L + i * ((W - PAD_L - PAD_R) / N_CANDLES) + candleW / 2;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Replay Lab</div>
          <div className="page-sub">Market Replay · Signal Overlay · Step-through Analysis</div>
        </div>
        <button className="btn" style={{ fontSize:11, padding:"5px 14px" }}>Export Replay</button>
      </div>

      {/* Controls */}
      <div className="card" style={{ marginBottom:14 }}>
        <div style={{ display:"flex", gap:14, alignItems:"flex-end", flexWrap:"wrap" }}>
          <div>
            <div className="muted" style={{ fontSize:10, marginBottom:4 }}>Instrument</div>
            <select className="select" value={instrument} onChange={e => setInstrument(e.target.value)}>
              {["EURUSD","GBPUSD","AUDUSD","USDJPY","USDCAD","USDCHF","NZDUSD","EURGBP"].map(s => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </div>
          <div>
            <div className="muted" style={{ fontSize:10, marginBottom:4 }}>Date</div>
            <input className="input" type="date" value={replayDate}
              onChange={e => setReplayDate(e.target.value)}
              style={{ fontFamily:"monospace", fontSize:12 }} />
          </div>
          <div>
            <div className="muted" style={{ fontSize:10, marginBottom:4 }}>Speed</div>
            <select className="select" value={speed} onChange={e => setSpeed(e.target.value)}>
              {["0.5×","1×","2×","5×"].map(s => <option key={s}>{s}</option>)}
            </select>
          </div>
          <div style={{ marginLeft:"auto", fontSize:12, color:"var(--muted)" }}>
            Candle <span className="mono" style={{ color:"var(--text)" }}>{frame + 1}</span> / {N_CANDLES}
          </div>
        </div>
      </div>

      {/* Candlestick chart */}
      <div className="card" style={{ marginBottom:14 }}>
        <div className="card-title">
          {instrument} M15 — {replayDate}
          <span className="right muted" style={{ fontSize:11 }}>
            {candles[frame] ? `O:${candles[frame].open.toFixed(5)}  H:${candles[frame].high.toFixed(5)}  L:${candles[frame].low.toFixed(5)}  C:${candles[frame].close.toFixed(5)}` : ""}
          </span>
        </div>
        <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display:"block", background:"var(--panel-2)", borderRadius:6 }}>
          {/* Price grid lines */}
          {[0.25, 0.5, 0.75].map(pct => {
            const y = PAD_T + pct * (H - PAD_T - PAD_B);
            const price = maxP - pct * priceRange;
            return (
              <g key={pct}>
                <line x1={PAD_L} y1={y} x2={W - PAD_R} y2={y} stroke="rgba(255,255,255,.05)" strokeWidth="1" />
                <text x={W - PAD_R - 2} y={y - 2} fontSize="7" fill="#5a6a82" textAnchor="end">{price.toFixed(5)}</text>
              </g>
            );
          })}

          {/* Candles */}
          {candles.slice(0, frame + 1).map((c, i) => {
            const bull = c.close >= c.open;
            const color = bull ? "#22c55e" : "#ef4444";
            const bodyTop = toY(Math.max(c.open, c.close));
            const bodyBot = toY(Math.min(c.open, c.close));
            const bodyH   = Math.max(1, bodyBot - bodyTop);
            const cx      = toX(i);
            return (
              <g key={i} opacity={i === frame ? 1 : 0.85}>
                {/* Wick */}
                <line x1={cx} y1={toY(c.high)} x2={cx} y2={toY(c.low)} stroke={color} strokeWidth="1" />
                {/* Body */}
                <rect x={cx - candleW / 2} y={bodyTop} width={candleW} height={bodyH}
                  fill={color} rx="1" opacity={bull ? 0.9 : 0.8} />
                {/* Highlight current frame */}
                {i === frame && (
                  <rect x={cx - candleW / 2 - 1} y={bodyTop - 1} width={candleW + 2} height={bodyH + 2}
                    fill="none" stroke="#22d3ee" strokeWidth="1.5" rx="2" />
                )}
              </g>
            );
          })}

          {/* Cursor vertical line */}
          <line x1={toX(frame)} y1={PAD_T} x2={toX(frame)} y2={H - PAD_B}
            stroke="#22d3ee" strokeWidth="1" strokeDasharray="3,3" opacity="0.6" />
        </svg>
      </div>

      {/* Playback controls + scrubber */}
      <div className="card">
        <div style={{ display:"flex", flexDirection:"column", gap:12 }}>
          {/* Scrubber */}
          <div style={{ display:"flex", alignItems:"center", gap:10 }}>
            <span className="mono muted" style={{ fontSize:10, minWidth:24 }}>0</span>
            <input type="range" min={0} max={N_CANDLES - 1} value={frame}
              onChange={e => { setFrame(+e.target.value); setPlaying(false); }}
              style={{ flex:1, accentColor:"var(--accent)" }} />
            <span className="mono muted" style={{ fontSize:10, minWidth:24 }}>{N_CANDLES}</span>
          </div>

          {/* Transport buttons */}
          <div style={{ display:"flex", justifyContent:"center", gap:10 }}>
            {[
              { icon:"⏮", title:"Start",    fn:() => { setFrame(0); setPlaying(false); } },
              { icon:"⏭", title:"Prev",     fn:() => setFrame(f => Math.max(0, f - 1)) },
              {
                icon: playing ? "⏸" : "▶",
                title: playing ? "Pause" : "Play",
                fn: () => setPlaying(p => !p),
                primary: true,
              },
              { icon:"⏭", title:"Next",  fn:() => setFrame(f => Math.min(N_CANDLES - 1, f + 1)) },
              { icon:"⏭", title:"End",   fn:() => { setFrame(N_CANDLES - 1); setPlaying(false); } },
            ].map((b, i) => (
              <button key={i} title={b.title}
                onClick={b.fn}
                style={{
                  width:40, height:40, borderRadius:"50%", fontSize:16,
                  background: b.primary ? "var(--accent)" : "var(--panel-2)",
                  color:      b.primary ? "#0f1724" : "var(--text)",
                  border:     b.primary ? "none" : "1px solid var(--line)",
                  cursor:"pointer", display:"flex", alignItems:"center", justifyContent:"center",
                }}>{b.icon}</button>
            ))}
          </div>

          {/* Time readout */}
          <div style={{ textAlign:"center", fontSize:12, color:"var(--muted)" }}>
            {replayDate} <span className="mono" style={{ color:"var(--text)" }}>
              {String(Math.floor(frame * 15 / 60) + 9).padStart(2,"0")}:{String((frame * 15) % 60).padStart(2,"0")} UTC
            </span>
            {" · "}Frame {frame + 1} / {N_CANDLES}
          </div>
        </div>
      </div>
    </div>
  );
}
window.ReplayPage = ReplayPage;
