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
  { id: "SCAN-1582", inst: "EURUSD", time: "2025-05-15 01:10", rec: "242,398", status: "Completed" },
  { id: "SCAN-1581", inst: "XAUUSD", time: "2025-05-14 23:30", rec: "198,552", status: "Completed" },
  { id: "SCAN-1580", inst: "BTCUSD", time: "2025-05-14 21:45", rec: "312,671", status: "Completed" },
  { id: "SCAN-1579", inst: "GBPUSD", time: "2025-05-14 19:20", rec: "215,332", status: "Completed" },
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

Object.assign(window, {
  RT_KPIS, FUSION_SEGMENTS, LIVE_SIGNAL, EQ_RUNTIME, RT_TRADES,
  RESEARCH_KPIS, OUTCOMES_SEGMENTS, STACKED_OUTCOMES, SCATTER_POINTS, SCAN_JOBS,
  MODELS,
  TRADE_KPIS, EQ_TRADES, SESSION_PNL, TRADE_JOURNAL,
  BT_KPIS, EQ_BACKTEST, DRAWDOWN, MONTHLY_RETURNS,
  SYS_KPIS, DATA_INTEGRITY, RECENT_JOBS,
});
