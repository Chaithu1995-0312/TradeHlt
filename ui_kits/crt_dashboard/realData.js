// realData.js — Fetches live data from http://localhost:8787/api/* and
// overwrites the static globals defined in data.js.
// Must be loaded AFTER all JSX files (so window.CrtDashboard is defined)
// and AFTER data.js (so fallback globals already exist).
//
// Signals app.jsx that deferred mount is expected via window._REAL_DATA_LOADING.

window._REAL_DATA_LOADING = true;

const _API = "http://localhost:8787";
const _DEFAULT_INSTRUMENT = "EURUSD";

// Helper: clamp value inside [min, max]
function _clamp(v, min, max) { return Math.min(max, Math.max(min, +v || 0)); }

// Fetch a single instrument list to allow the UI to reflect real instruments
async function _fetchInstruments() {
  try {
    const d = await fetch(_API + "/api/instruments").then(r => r.json());
    return (d.instruments || [_DEFAULT_INSTRUMENT]);
  } catch (_) { return [_DEFAULT_INSTRUMENT]; }
}

async function _init() {
  const instrument = _DEFAULT_INSTRUMENT;

  const [statusR, modelsR, modelVersionsR, oppStatsR, tradesR, eqR, btR] =
    await Promise.allSettled([
      fetch(_API + "/api/status").then(r => r.json()),
      fetch(_API + "/api/models").then(r => r.json()),
      fetch(_API + "/api/model_versions").then(r => r.json()),
      fetch(_API + `/api/opportunity_stats?instrument=${instrument}`).then(r => r.json()),
      fetch(_API + `/api/trades?instrument=${instrument}&per_page=50`).then(r => r.json()),
      fetch(_API + `/api/equity_curve?instrument=${instrument}`).then(r => r.json()),
      fetch(_API + "/api/backtest_history").then(r => r.json()),
    ]);

  // ── /api/status → RT_KPIS ────────────────────────────────────────────────
  if (statusR.status === "fulfilled") {
    const s = statusR.value;
    const corr = +((s.active_model_corr) || 0);
    const ks   = s.kill_switch || {};
    window.RT_KPIS = {
      activeModel: s.active_model_version || "—",
      modelKind:   "Gaussian",
      killSwitch:  ks.tripped ? "TRIPPED" : "SAFE",
      convergence: {
        value: corr.toFixed(4),
        label: corr > 0.05 ? "Good" : corr > 0.01 ? "Low" : "Poor",
      },
      regime:    { value: "NORMAL", sub: "Auto" },
      trades24h: { value: s.trades_last_24h || 0, sub: "" },
      pnl24h:    0,
    };
  }

  // ── /api/model_versions → model version panel data ───────────────────────
  if (modelVersionsR.status === "fulfilled") {
    window._MODEL_VERSIONS = modelVersionsR.value;
  }

  // ── /api/models → MODELS (Gaussian registry table) ──────────────────────
  if (modelsR.status === "fulfilled") {
    const entries = modelsR.value.models || [];
    window.MODELS = entries.map(m => ({
      ver:     m.version || "—",
      type:    "Gaussian (ML)",
      corr:    +(m.corr_expected_rr || 0),
      cal:     +(m.calibration_error || 0),
      trained: m.trained_at ? m.trained_at.slice(0, 10) : "—",
      samples: m.n_train || null,
      status:  m.active ? "ACTIVE" : "Archived",
      action:  m.active ? "Active" : "Promote",
    }));
  }

  // ── /api/opportunity_stats → RESEARCH_KPIS, OUTCOMES_SEGMENTS ───────────
  if (oppStatsR.status === "fulfilled") {
    const o     = oppStatsR.value;
    const total = Math.max(1, o.total_sampled || 1);
    const dist  = o.outcome_distribution || {};

    // Handle both server naming conventions
    const tp  = dist.TP_HIT  || dist.TP  || 0;
    const sl  = dist.SL_HIT  || dist.SL  || 0;
    const to  = dist.TIMEOUT || dist.TO  || 0;

    const winLong  = (o.win_rate_by_direction || {}).long  || 0;
    const winShort = (o.win_rate_by_direction || {}).short || 0;
    const avgWin   = ((winLong + winShort) / 2) || (tp / total);

    window.RESEARCH_KPIS = {
      totalOpps:    { value: total.toLocaleString(), sub: "Sampled records" },
      winRateTP:    (avgWin * 100).toFixed(2) + "%",
      avgRR:        o.avg_rr != null ? o.avg_rr.toFixed(3) + " R" : "—",
      profitFactor: "—",
      timeoutRate:  ((to / total) * 100).toFixed(2) + "%",
    };

    window.OUTCOMES_SEGMENTS = [
      { label: "TP Hit",  value: tp, pct: ((tp / total) * 100).toFixed(2) + "%", color: "#22c55e" },
      { label: "SL Hit",  value: sl, pct: ((sl / total) * 100).toFixed(2) + "%", color: "#ef4444" },
      { label: "Timeout", value: to, pct: ((to / total) * 100).toFixed(2) + "%", color: "#facc15" },
    ];

    // Session win-rate bars
    const swr = o.win_rate_by_session || {};
    const SESSION_LABELS = { "1.0": "Asian", "2.0": "London", "3.0": "New York" };
    window.SESSION_PNL = Object.entries(swr).map(([k, rate]) => ({
      label: SESSION_LABELS[String(k)] || String(k),
      value: +(rate * 100).toFixed(2),
      color: rate > 0.45 ? "#22c55e" : rate > 0.35 ? "#facc15" : "#ef4444",
    }));
  }

  // ── /api/trades → RT_TRADES, TRADE_JOURNAL, TRADE_KPIS ──────────────────
  if (tradesR.status === "fulfilled") {
    const recs = tradesR.value.records || [];

    // Recent live trades shown on Runtime panel
    window.RT_TRADES = recs.slice(0, 10).map(t => ({
      id:     t.trade_id || "—",
      time:   t.opened_at ? t.opened_at.slice(11, 16) : "—",
      dir:    (t.direction || "").toUpperCase(),
      entry:  "—",
      exit:   "—",
      rr:     +(t.pnl_rr_net || 0),
      result: (t.exit_reason || "").toUpperCase().includes("TP") ? "TP" : "SL",
      conf:   0,
      regime: "NORMAL",
    }));

    // Full trade journal (Trades panel)
    window.TRADE_JOURNAL = recs.map(t => ({
      id:        t.trade_id || "—",
      time:      t.opened_at || "—",
      dir:       (t.direction || "").toUpperCase(),
      entry:     "—",
      exit:      "—",
      rr:        +(t.pnl_rr_net || 0),
      result:    (t.exit_reason || "").toUpperCase().includes("TP") ? "TP" : "SL",
      session:   t.session || "—",
      conf:      0,
      exitReason: t.exit_reason || "—",
    }));

    // Aggregate KPIs from trade list
    if (recs.length > 0) {
      const wins  = recs.filter(t => (t.pnl_rr_net || 0) > 0);
      const total = recs.length;
      const totalPnl = recs.reduce((s, t) => s + (t.pnl_rr_net || 0), 0);
      const avgW  = wins.length  ? wins.reduce((s,t) => s + t.pnl_rr_net, 0) / wins.length  : 0;
      const avgL  = (total - wins.length) ? recs.filter(t => (t.pnl_rr_net||0) <= 0).reduce((s,t)=>s+Math.abs(t.pnl_rr_net||0),0) / (total-wins.length) : 1;
      window.TRADE_KPIS = {
        totalPnl:     (totalPnl >= 0 ? "+" : "") + totalPnl.toFixed(2),
        winRate:      ((wins.length / total) * 100).toFixed(2) + "%",
        profitFactor: avgL ? (avgW * wins.length / (avgL * (total - wins.length))).toFixed(2) : "—",
        expectancy:   (totalPnl / total).toFixed(2),
        avgRR:        avgW.toFixed(2) + " / -" + avgL.toFixed(2),
        maxDD:        "—",
      };
    }
  }

  // ── /api/equity_curve → EQ_RUNTIME, EQ_TRADES ───────────────────────────
  if (eqR.status === "fulfilled") {
    const pts  = eqR.value.curve || [];
    const vals = pts.map(pt => +(pt.cumulative_pnl_rr || 0));
    if (vals.length > 0) {
      window.EQ_RUNTIME  = vals;
      window.EQ_TRADES   = vals;
      window.EQ_BACKTEST = vals;
    }
  }

  // ── /api/backtest_history → BT data ─────────────────────────────────────
  if (btR.status === "fulfilled") {
    const bts = btR.value.backtests || [];
    window.BT_HISTORY = bts.map(b => ({
      ver:     b.version || "—",
      type:    "Gaussian",
      corr:    +(b.corr_expected_rr || 0),
      cal:     +(b.calibration_error || 0),
      trained: b.trained_at ? b.trained_at.slice(0, 10) : "—",
      samples: b.n_samples || 0,
      verdict: b.verdict || "—",
      approved: !!b.integration_approved,
    }));

    // Update BT KPIs header if data is available
    if (bts.length > 0) {
      const latest = bts[0];
      window.BT_KPIS = Object.assign(window.BT_KPIS || {}, {
        totalPnl: "—",
        cagr:     "—",
        winRate:  "—",
        profitFactor: "—",
        maxDD:    "—",
        sharpe:   "—",
      });
    }
  }

  // ── /api/zone_gate_models, /api/rr_models, /api/tradenet_models ─────────
  const [zgR, rrModR, tnR] = await Promise.allSettled([
    fetch(_API + "/api/zone_gate_models").then(r => r.json()),
    fetch(_API + "/api/rr_models").then(r => r.json()),
    fetch(_API + "/api/tradenet_models").then(r => r.json()),
  ]);

  if (zgR.status === "fulfilled") {
    window.ZONE_GATE_MODELS = (zgR.value.models || []).map(m => ({
      ver:       m.version || "—",
      nZones:    m.n_zones || 0,
      nClusters: m.n_clusters_requested || 0,
      trained:   m.trained_at || "—",
      modelFile: (m.model_file || "").split(/[\\/]/).pop() || "—",
      fileExists: !!m.file_exists,
      status:    m.active ? "ACTIVE" : "Archived",
      action:    m.active ? "Active" : "Promote",
    }));
  }

  if (rrModR.status === "fulfilled") {
    window.RR_MODELS = (rrModR.value.models || []).map(m => ({
      ver:        m.version || "—",
      samples:    m.n_samples,
      features:   m.n_features || 35,
      ridgeAlpha: m.ridge_alpha,
      modelExists: !!m.model_exists,
      trained:    m.trained_at || "—",
      status:     m.active ? "ACTIVE" : "Archived",
      action:     m.active ? "Active" : "Promote",
    }));
  }

  if (tnR.status === "fulfilled") {
    window.TRADENET_MODELS = (tnR.value.models || []).map(m => ({
      ver:       m.version || "—",
      modelFile: (m.model_file || "").split(/[\\/]/).pop() || "—",
      trained:   m.trained_at || "—",
      fileExists: !!m.file_exists,
      status:    m.active ? "ACTIVE" : "Archived",
      action:    m.active ? "Active" : "Promote",
    }));
  }

  // ── Deferred React mount ─────────────────────────────────────────────────
  // app.jsx exports window.CrtDashboard and skips its own mount when
  // window._REAL_DATA_LOADING === true. We mount here after data is ready.
  const root = document.getElementById("root");
  if (root && window.CrtDashboard) {
    ReactDOM.createRoot(root).render(
      React.createElement(window.CrtDashboard)
    );
  } else {
    console.error("[realData] window.CrtDashboard not defined — check JSX load order");
  }

  console.info("[realData] Live data loaded. Refreshing in 30s…");

  // Periodic refresh (update globals + force re-render via root replacement)
  setTimeout(async function _refresh() {
    try {
      const [sR, tR, eR] = await Promise.allSettled([
        fetch(_API + "/api/status").then(r => r.json()),
        fetch(_API + `/api/trades?instrument=${instrument}&per_page=50`).then(r => r.json()),
        fetch(_API + `/api/equity_curve?instrument=${instrument}`).then(r => r.json()),
      ]);
      if (sR.status === "fulfilled") {
        const s = sR.value;
        const corr = +((s.active_model_corr) || 0);
        window.RT_KPIS = Object.assign(window.RT_KPIS || {}, {
          activeModel: s.active_model_version || "—",
          killSwitch:  (s.kill_switch || {}).tripped ? "TRIPPED" : "SAFE",
          convergence: { value: corr.toFixed(4), label: corr > 0.05 ? "Good" : "Low" },
          trades24h:   { value: s.trades_last_24h || 0, sub: "" },
        });
      }
      if (tR.status === "fulfilled") {
        const recs = tR.value.records || [];
        window.RT_TRADES = recs.slice(0, 10).map(t => ({
          id: t.trade_id||"—", time: t.opened_at?t.opened_at.slice(11,16):"—",
          dir:(t.direction||"").toUpperCase(), entry:"—",exit:"—",
          rr:+(t.pnl_rr_net||0),
          result:(t.exit_reason||"").toUpperCase().includes("TP")?"TP":"SL",
          conf:0,regime:"NORMAL",
        }));
      }
      if (eR.status === "fulfilled") {
        const pts = eR.value.curve || [];
        if (pts.length > 0) {
          const vals = pts.map(p => +(p.cumulative_pnl_rr || 0));
          window.EQ_RUNTIME = vals; window.EQ_TRADES = vals;
        }
      }
      // Re-render to pick up updated globals
      if (document.getElementById("root") && window.CrtDashboard) {
        ReactDOM.createRoot(document.getElementById("root")).render(
          React.createElement(window.CrtDashboard)
        );
      }
    } catch (e) { console.warn("[realData] Refresh failed:", e.message); }
    setTimeout(_refresh, 30000);
  }, 30000);
}

_init().catch(err => {
  console.warn("[realData] Initial fetch failed — falling back to mock data:", err.message);
  // Fallback: mount with mock globals from data.js
  const root = document.getElementById("root");
  if (root && window.CrtDashboard) {
    ReactDOM.createRoot(root).render(React.createElement(window.CrtDashboard));
  }
});
