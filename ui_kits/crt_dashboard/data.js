// Static mock data shared across panels.

const RT_KPIS = {
  activeModel: "v4_mirrored",
  modelKind: "Gaussian",
  killSwitch: "SAFE",
  convergence: { value: 0.82, label: "High" },
  regime: { value: "NORMAL", sub: "Range" },
  trades24h: { value: 12, sub: "4W / 8L" },
  pnl24h: 2.63,
};

const FUSION_SEGMENTS = [
  { label: "CRT (Structure)", value: 0.86, color: "#22c55e" },
  { label: "Gaussian (Prob)", value: 0.74, color: "#a78bfa" },
  { label: "Zone Gate",       value: 0.80, color: "#facc15" },
  { label: "RR Miner",        value: 0.71, color: "#ef4444" },
  { label: "TradeNet",        value: 0.79, color: "#22d3ee" },
];

const LIVE_SIGNAL = {
  direction: "LONG", entry: "1.08245",
  confidence: 0.82, expectedRR: 1.74,
  risk: "0.00110", tp: "1.08465",
  sl: "1.08135", session: "15:35",
};

// Equity curve — list of values, simple ascending with noise.
function genEquity(n, start, drift, noise) {
  const out = []; let v = start;
  for (let i = 0; i < n; i++) { v += drift + (Math.random() - 0.5) * noise; out.push(v); }
  return out;
}
const EQ_RUNTIME = (() => {
  // Seed-ish deterministic walk
  const v = [-1.2, -0.6, -0.4, 0.1, 0.8, 1.2, 1.6, 2.1, 1.8, 2.4, 3.1, 2.8, 3.4, 4.1, 3.9, 4.6, 5.2, 5.0, 5.6, 6.1];
  return v;
})();

const RT_TRADES = [
  { id: "CRT-00123", time: "15:12", dir: "LONG",  entry: "1.08301", exit: "1.08401", rr: +1.62, result: "TP", conf: 0.84, regime: "NORMAL" },
  { id: "CRT-00122", time: "14:48", dir: "SHORT", entry: "1.08210", exit: "1.08100", rr: +1.00, result: "TP", conf: 0.78, regime: "NORMAL" },
  { id: "CRT-00121", time: "14:15", dir: "LONG",  entry: "1.08021", exit: "1.07915", rr: -1.00, result: "SL", conf: 0.65, regime: "NORMAL" },
  { id: "CRT-00120", time: "13:42", dir: "SHORT", entry: "1.08350", exit: "1.08460", rr: -1.10, result: "SL", conf: 0.60, regime: "NORMAL" },
];

// Research / Pipeline B
const RESEARCH_KPIS = {
  totalOpps: { value: "1,248,562", sub: "Long + Short" },
  winRateTP: "42.67%",
  avgRR: "0.38 R",
  profitFactor: "1.23",
  timeoutRate: "5.41%",
};

const OUTCOMES_SEGMENTS = [
  { label: "TP Hit",    value: 532142, pct: "42.67%", color: "#22c55e" },
  { label: "SL Hit",    value: 649367, pct: "52.02%", color: "#ef4444" },
  { label: "Timeout",   value: 67053,  pct: "5.41%",  color: "#facc15" },
];

// Stacked bars: ~30 buckets across a year, three series tp/sl/timeout
function genStacked(n) {
  const out = [];
  for (let i = 0; i < n; i++) {
    const tp = 60 + Math.random() * 80;
    const sl = 70 + Math.random() * 90;
    const to = 5 + Math.random() * 15;
    out.push({ tp, sl, to });
  }
  return out;
}
const STACKED_OUTCOMES = (() => {
  // Deterministic-ish via fixed values to render same every render
  const seed = [
    [82,95,12],[90,110,9],[78,100,14],[105,120,11],[95,118,10],[100,130,12],[88,108,9],
    [110,135,15],[120,140,11],[98,118,12],[115,130,9],[125,150,14],[100,125,11],[112,138,13],
    [130,150,12],[140,160,11],[120,148,9],[105,130,14],[122,150,12],[100,132,11],[118,142,13],
    [128,150,12],[110,138,9],[100,128,13],[120,148,14],[115,140,12],[105,128,10],[112,140,11],
    [100,125,13],[120,140,12]
  ];
  return seed.map(([tp,sl,to]) => ({ tp, sl, to }));
})();

// Scatter — UMAP feature space.
const SCATTER_POINTS = (() => {
  const cluster = (cx, cy, n, color, jitter=22) => {
    const out = [];
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2;
      const r = Math.random() * jitter;
      out.push({ x: cx + Math.cos(a)*r, y: cy + Math.sin(a)*r, color });
    }
    return out;
  };
  return [
    ...cluster(75,  85,  140, "#22c55e", 30),  // profitable
    ...cluster(165, 70,  120, "#facc15", 26),  // breakeven
    ...cluster(225, 100, 130, "#ef4444", 32),  // losing
    ...cluster(140, 130, 80,  "#a78bfa", 22),  // overlap region
  ];
})();

const SCAN_JOBS = [
  {
    id: "SCAN-1582", inst: "EURUSD", time: "2025-05-15 01:10", rec: "242,398", status: "Completed",
    kpis: { totalOpps:{value:"242,398",sub:"EURUSD · Long + Short"}, winRateTP:"43.21%", avgRR:"1.84 R", profitFactor:"1.38", timeoutRate:"3.21%" },
    outcomes: [
      { label:"TP Hit",  value:104660, pct:"43.2%", color:"#22c55e" },
      { label:"SL Hit",  value:129966, pct:"53.6%", color:"#ef4444" },
      { label:"Timeout", value:7772,   pct:"3.2%",  color:"#facc15" },
    ],
  },
  {
    id: "SCAN-1581", inst: "XAUUSD", time: "2025-05-14 23:30", rec: "198,552", status: "Completed",
    kpis: { totalOpps:{value:"198,552",sub:"XAUUSD · Long + Short"}, winRateTP:"38.91%", avgRR:"2.12 R", profitFactor:"1.29", timeoutRate:"7.14%" },
    outcomes: [
      { label:"TP Hit",  value:77288,  pct:"38.9%", color:"#22c55e" },
      { label:"SL Hit",  value:107127, pct:"54.0%", color:"#ef4444" },
      { label:"Timeout", value:14137,  pct:"7.1%",  color:"#facc15" },
    ],
  },
  {
    id: "SCAN-1580", inst: "BTCUSD", time: "2025-05-14 21:45", rec: "312,671", status: "Completed",
    kpis: { totalOpps:{value:"312,671",sub:"BTCUSD · Long + Short"}, winRateTP:"46.82%", avgRR:"1.63 R", profitFactor:"1.51", timeoutRate:"4.88%" },
    outcomes: [
      { label:"TP Hit",  value:146416, pct:"46.8%", color:"#22c55e" },
      { label:"SL Hit",  value:150983, pct:"48.3%", color:"#ef4444" },
      { label:"Timeout", value:15272,  pct:"4.9%",  color:"#facc15" },
    ],
  },
  {
    id: "SCAN-1579", inst: "GBPUSD", time: "2025-05-14 19:20", rec: "215,332", status: "Completed",
    kpis: { totalOpps:{value:"215,332",sub:"GBPUSD · Long + Short"}, winRateTP:"41.04%", avgRR:"1.72 R", profitFactor:"1.32", timeoutRate:"5.62%" },
    outcomes: [
      { label:"TP Hit",  value:88346,  pct:"41.0%", color:"#22c55e" },
      { label:"SL Hit",  value:114940, pct:"53.4%", color:"#ef4444" },
      { label:"Timeout", value:11906,  pct:"5.5%",  color:"#facc15" },
    ],
  },
];

// Models
const MODELS = [
  { ver: "v4_mirrored",      type: "Gaussian (ML)",        corr: +0.2066,  cal: 0.0491, trained: "2026-05-12", samples: 0,   status: "ACTIVE",    action: "View" },
  { ver: "v4_val_test",      type: "Gaussian (ML)",        corr: +0.2056,  cal: 0.0560, trained: "2026-05-13", samples: 0,   status: "Candidate", action: "Promote" },
  { ver: "v4_long_only",     type: "Gaussian (ML)",        corr: +0.2027,  cal: 0.0478, trained: "2026-05-12", samples: 0,   status: "Archived",  action: "View" },
  { ver: "v4_force_test",    type: "Gaussian (ML)",        corr: +0.0067,  cal: 0.0195, trained: "2026-05-12", samples: 0,   status: "Archived",  action: "View" },
  { ver: "v2_gaussian_2026_05", type: "Gaussian (ML)",     corr: -0.0162,  cal: 0.0000, trained: "2026-05-06", samples: 28,  status: "Archived",  action: "View" },
  { ver: "import_fix_v1",    type: "Gaussian (ML)",        corr: -0.0811,  cal: 0.0716, trained: "2026-03-25", samples: 105, status: "Archived",  action: "View" },
  { ver: "v2",               type: "Gaussian (Heuristic)", corr:  0.0500,  cal: 0.1000, trained: "—",          samples: null, status: "Archived",  action: "View" },
];

// Non-Gaussian model registries (overwritten by realData.js on live load)
const ZONE_GATE_MODELS = [];
const RR_MODELS = [];
const TRADENET_MODELS = [];

// Trade analytics
const TRADE_KPIS = {
  totalPnl: "+356.42",
  winRate: "54.37%",
  profitFactor: "1.38",
  expectancy: "0.42",
  avgRR: "1.62 / -1.03",
  maxDD: "-8.46",
};
const EQ_TRADES = (() => {
  // Multi-year curve climbing from 0 to ~400
  const out = []; let v = 0;
  for (let i = 0; i < 60; i++) { v += 6 + (Math.random() - 0.4) * 12; out.push(v); }
  return out;
})();
const SESSION_PNL = [
  { label: "Asian",   value: 68.42,  color: "#22c55e" },
  { label: "London",  value: 142.78, color: "#22c55e" },
  { label: "NY",      value: 98.31,  color: "#22c55e" },
  { label: "Overlap", value: 46.91,  color: "#22c55e" },
];
const TRADE_JOURNAL = [
  { id: "CRT-00123", time: "2026-05-15 15:12", dir: "LONG",  entry: "1.08123", exit: "1.08301", rr: +1.62, result: "TP", session: "London", conf: 0.84, reason: "TP2" },
  { id: "CRT-00122", time: "2026-05-15 14:48", dir: "SHORT", entry: "1.08210", exit: "1.08100", rr: +1.00, result: "TP", session: "London", conf: 0.78, reason: "TP1" },
  { id: "CRT-00121", time: "2026-05-15 14:15", dir: "LONG",  entry: "1.08021", exit: "1.07915", rr: -1.00, result: "SL", session: "Asian",  conf: 0.65, reason: "STOPPED" },
  { id: "CRT-00120", time: "2026-05-15 13:42", dir: "SHORT", entry: "1.08350", exit: "1.08460", rr: -1.10, result: "SL", session: "Asian",  conf: 0.60, reason: "STOPPED" },
];

// Backtests
const BT_KPIS = {
  totalPnl: "+287.64",
  cagr: "18.74%",
  winRate: "52.11%",
  profitFactor: "1.31",
  maxDD: "-6.32",
  sharpe: "1.42",
};
const EQ_BACKTEST = (() => {
  const out = []; let v = 0;
  for (let i = 0; i < 60; i++) { v += 6 + (Math.random() - 0.3) * 10; out.push(v); }
  return out;
})();
const DRAWDOWN = (() => {
  const out = []; let v = 0;
  for (let i = 0; i < 60; i++) {
    v += (Math.random() - 0.55) * 1.6;
    if (v > 0) v = 0;
    if (v < -9) v = -9 + Math.random() * 2;
    out.push(v);
  }
  return out;
})();
const MONTHLY_RETURNS = (() => {
  // 6 years × 12 months, values roughly in [-4, +6]
  const years = [2025, 2024, 2023, 2022, 2021, 2020];
  const rows = years.map(y => {
    const cells = [];
    for (let m = 0; m < 12; m++) {
      const v = (Math.random() - 0.45) * 8;
      cells.push(+v.toFixed(1));
    }
    return { year: y, cells };
  });
  return rows;
})();

// System
const SYS_KPIS = {
  dataFeeds: { value: "12 / 12", sub: "Healthy" },
  lastData: { value: "15m ago", sub: "EURUSD M15" },
  storage: { value: "62.4 GB", sub: "of 500 GB" },
  jobsRunning: { value: "1", sub: "0 Failed" },
  alerts: { value: "0", sub: "Active" },
};
const DATA_INTEGRITY = [
  { name: "OHLC Completeness", value: "100%" },
  { name: "Timestamp Integrity", value: "100%" },
  { name: "No Duplicates",       value: "100%" },
  { name: "Gap Free",            value: "100%" },
  { name: "Feature Schema",      value: "v5 (35)" },
];
const RECENT_JOBS = [
  { id: "JOB-8842", type: "Opportunity Scan", time: "2025-05-15 01:10", status: "Completed" },
  { id: "JOB-8841", type: "Model Training",   time: "2025-05-15 00:15", status: "Completed" },
  { id: "JOB-8840", type: "RR Dataset Build", time: "2025-05-14 23:45", status: "Completed" },
  { id: "JOB-8839", type: "Log Compression",  time: "2025-05-14 21:30", status: "Completed" },
];

// ── New globals for prototype design ──────────────────────────
const EXEC_KPIS = {
  totalPnl: "+356.42", totalPnlDelta: "↑ 1.62%",
  winRate: "54.37%",   winRateDelta:  "↑ 2.18%",
  profitFactor: "1.38", pfDelta:      "↑ 0.11",
  avgRR: "1.62 / -1.03", avgRRDelta:  "↑ 0.07",
  expectancy: "0.42",  expDelta:      "↑ 0.04",
};

const ALERTS = [
  { icon:"⚠", title:"Model Drift Detected",  sub:"RR_Miner_v2",       age:"2m ago",  level:"warn" },
  { icon:"⚠", title:"Win Rate Drop (London)", sub:"-12% vs 7D avg",    age:"5m ago",  level:"warn" },
  { icon:"⚠", title:"High SL Hit Rate",       sub:"Current: 63%",      age:"13m ago", level:"warn" },
  { icon:"⚠", title:"Data Delay Detected",    sub:"EURUSD M15",        age:"9m ago",  level:"warn" },
];

const STATUS_STRIP = {
  activeModel: "CRT v5", promotionGuard: "KMeans Clustering",
  schema: "35-dim Feature Space", dataIntegrity: "100%",
};

const SESSION_EQUITY = (() => {
  const walk = (start, len) => {
    const out = [start]; let v = start;
    for (let i = 1; i < len; i++) { v += (Math.random() - 0.45) * 8; out.push(+v.toFixed(1)); }
    return out;
  };
  return { asian: walk(0,60), london: walk(0,60), ny: walk(0,60), overlap: walk(0,60) };
})();

const SIGNAL_PIPELINE = [
  { name:"Market Data",   val:"Live",       status:"ok", icon:"📡" },
  { name:"Feature Engine",val:"98%",        status:"ok", icon:"⚙"  },
  { name:"Gaussian Gate", val:"12 / 18",    status:"ok", icon:"🔵" },
  { name:"Zone Gate",     val:"8 / 12",     status:"ok", icon:"📍" },
  { name:"RR Miner",      val:"Top: 2.45",  status:"ok", icon:"📈" },
  { name:"Exec Planner",  val:"2 Signals",  status:"ok", icon:"📋" },
  { name:"Risk Manager",  val:"Approved",   status:"ok", icon:"✓"  },
  { name:"Orders",        val:"1 Live",     status:"ok", icon:"💹" },
];

const EVENT_STREAM = [
  { time:"13:24", event:"Order Filled",      inst:"EURUSD", status:"ok", latency:"50ms" },
  { time:"13:21", event:"Signal Approved",   inst:"EURUSD", status:"ok", latency:"27ms" },
  { time:"13:18", event:"Zone Gate Passed",  inst:"EURUSD", status:"ok", latency:"41ms" },
  { time:"13:16", event:"Gaussian Accepted", inst:"EURUSD", status:"ok", latency:"18ms" },
  { time:"13:12", event:"Feature Generated", inst:"EURUSD", status:"ok", latency:"23ms" },
];

const ACTIVE_SIGNALS = {
  count: 2, long: 1, short: 1,
  topSignal: { inst:"EURUSD", conf:0.80, rr:2.45, entry:1.08134, stop:1.07990 },
};

const LATENCY_SERIES = {
  ingestion: [45,42,50,38,46], feature: [22,25,20,24,23],
  model: [18,20,17,21,19], execution: [30,28,35,31,29],
};

const QUEUE_DEPTHS = { ingestion:1, feature:3, signal:3 };

const FEATURE_DRIFT = [
  { name:"RSI_14",         psi:0.08, color:"#22c55e", status:"OK"    },
  { name:"Volatility Ratio",psi:0.14, color:"#facc15", status:"WARN"  },
  { name:"Swing High",      psi:0.06, color:"#22c55e", status:"OK"    },
  { name:"Hour of Day",     psi:0.04, color:"#22c55e", status:"OK"    },
  { name:"Candles Since Retest",psi:0.23, color:"#ef4444", status:"ALERT" },
];

const LINEAGE_NODES = [
  { ver:"CRT v4.2", date:"2025-01", active:false },
  { ver:"CRT v4.3", date:"2025-06", active:false },
  { ver:"CRT v4.4", date:"2025-11", active:false },
  { ver:"CRT v5",   date:"2026-05", active:true  },
];

const SHADOW_COMPARE = {
  active: { ver:"v4_mirrored", winRate:"54.37%", pf:"1.38", avgRR:"1.62", dd:"-8.46", trades:412 },
  shadow: { ver:"v4_val_test", winRate:"56.12%", pf:"1.44", avgRR:"1.70", dd:"-7.21", trades:398 },
  readiness: 82,
};

const PROMOTION_HISTORY = [
  { from:"CRT v4.3", to:"CRT v4.4", date:"2025-11-02", reason:"Win rate +4.2%",      by:"Auto-Promoter" },
  { from:"CRT v4.4", to:"CRT v5",   date:"2026-05-12", reason:"Corr improved 0.21",  by:"Auto-Promoter" },
];

const REGIME_PERF = [
  { regime:"Trending",      trades:1862, winRate:"58.21%", pf:"1.91" },
  { regime:"Range",         trades:682,  winRate:"49.12%", pf:"1.12" },
  { regime:"Low Volatile",  trades:420,  winRate:"60.34%", pf:"1.89" },
  { regime:"High Volatile", trades:318,  winRate:"60.34%", pf:"1.89" },
];

const TRADE_TRACE = [
  { time:"20:12:34", event:"Order Filled",       sub:"Fill: 1.08245",      dot:"ok"    },
  { time:"20:12:31", event:"Risk Approved",       sub:"UltronRiskGate: OK", dot:"ok"    },
  { time:"20:12:28", event:"RR Score 2.45",       sub:"RR Miner score",     dot:"ok"    },
  { time:"20:12:26", event:"Zone Gate Passed",    sub:"Zone 3 of 8",        dot:"ok"    },
  { time:"20:12:24", event:"Gaussian Accepted",   sub:"Corr: +0.2066",      dot:"ok"    },
  { time:"20:12:20", event:"Features Generated",  sub:"35-dim vector",      dot:"muted" },
  { time:"20:12:18", event:"Market Data",         sub:"EURUSD M15 bar",     dot:"muted" },
];

const SEQ_PATTERNS = [
  { chain:["Sweep","Displacement","Retest","TP2"],   rate:"62.4%", n:1842, color:"#22c55e" },
  { chain:["Sweep","Retest","TP1"],                  rate:"51.2%", n:984,  color:"#facc15" },
  { chain:["Range","Break","Retest","TP2"],          rate:"58.7%", n:712,  color:"#22c55e" },
  { chain:["Sweep","Displacement","SL"],             rate:"37.6%", n:622,  color:"#ef4444" },
];

// ── Runtime-backed globals (now owned by app.jsx / ApiClient) ────────────────
// RT_KPIS, MODELS, ZONE_GATE_MODELS, RR_MODELS, TRADENET_MODELS,
// TRADE_JOURNAL, TRADE_KPIS, EQ_TRADES, EQ_RUNTIME, RESEARCH_KPIS,
// OUTCOMES_SEGMENTS, BT_HISTORY, BT_KPIS, EQ_BACKTEST → REMOVED.
// Pages receive these via props from app.jsx. Do not re-add here.

Object.assign(window, {
  // Static scaffold: no backend endpoint exists yet
  // TODO: replace each with /api/{endpoint} when backend is ready
  FUSION_SEGMENTS, LIVE_SIGNAL, STACKED_OUTCOMES, SCATTER_POINTS, SCAN_JOBS,
  DRAWDOWN, MONTHLY_RETURNS,
  SYS_KPIS, DATA_INTEGRITY, RECENT_JOBS,
  EXEC_KPIS, ALERTS, STATUS_STRIP, SESSION_EQUITY,
  SIGNAL_PIPELINE, EVENT_STREAM, ACTIVE_SIGNALS, LATENCY_SERIES, QUEUE_DEPTHS,
  FEATURE_DRIFT, LINEAGE_NODES, SHADOW_COMPARE, PROMOTION_HISTORY,
  REGIME_PERF, TRADE_TRACE, SEQ_PATTERNS,
});
