// app.jsx — Runtime Store + Shell
// Owns ALL runtime state. Pages are pure projections receiving data via props.
// ApiClient (window.ApiClient) is the only fetch surface.

function CrtDashboard() {
  // ── Navigation ────────────────────────────────────────────────────────────
  const [activePage, setActivePage] = React.useState("Executive");
  const [activeSub,  setActiveSub]  = React.useState("Executive");
  window.__crtNav = (page) => { setActivePage(page); setActiveSub(page); };

  // ── Instrument state ──────────────────────────────────────────────────────
  const [instruments,       setInstruments]       = React.useState(["EURUSD"]);
  const [selectedInstrument,setSelectedInstrument]= React.useState(
    () => localStorage.getItem("crt_instrument") || "EURUSD"
  );
  const [instrumentLoading, setInstrumentLoading] = React.useState(true);

  // ── Runtime data state ────────────────────────────────────────────────────
  const [status,         setStatus]         = React.useState(null);
  const [trades,         setTrades]         = React.useState([]);
  const [tradeKpis,      setTradeKpis]      = React.useState(null);
  const [equity,         setEquity]         = React.useState([]);
  const [oppStats,       setOppStats]       = React.useState(null);

  // ── Global (non-instrument-scoped) registry data ──────────────────────────
  const [models,         setModels]         = React.useState(window.MODELS         || []);
  const [zoneModels,     setZoneModels]     = React.useState(window.ZONE_GATE_MODELS|| []);
  const [rrModels,       setRrModels]       = React.useState(window.RR_MODELS      || []);
  const [tradenetModels, setTradenetModels] = React.useState(window.TRADENET_MODELS|| []);
  const [backtestHistory,setBacktestHistory]= React.useState([]);
  const [scanJobs,             setScanJobs]             = React.useState([]);
  const [opportunityAnalytics, setOpportunityAnalytics] = React.useState(null);

  // ── Helpers ───────────────────────────────────────────────────────────────
  function mapTrades(recs) {
    return (recs || []).map(t => ({
      id:         t.trade_id  || "—",
      time:       t.opened_at ? t.opened_at.slice(0, 16).replace("T", " ") : "—",
      dir:        (t.direction || "").toUpperCase(),
      entry:      "—",
      exit:       "—",
      rr:         +(t.pnl_rr_net || 0),
      result:     (t.exit_reason || "").toUpperCase().includes("TP") ? "TP" : "SL",
      session:    t.session    || "—",
      exitReason: t.exit_reason|| "—",
    }));
  }

  function deriveTradeKpis(recs) {
    if (!recs || recs.length === 0) return null;
    const wins     = recs.filter(t => (t.pnl_rr_net || 0) > 0);
    const total    = recs.length;
    const totalPnl = recs.reduce((s, t) => s + (t.pnl_rr_net || 0), 0);
    const avgW     = wins.length ? wins.reduce((s,t)=>s+t.pnl_rr_net,0)/wins.length : 0;
    const losses   = recs.filter(t => (t.pnl_rr_net||0) <= 0);
    const avgL     = losses.length ? losses.reduce((s,t)=>s+Math.abs(t.pnl_rr_net||0),0)/losses.length : 1;
    return {
      totalPnl:     (totalPnl >= 0 ? "+" : "") + totalPnl.toFixed(2),
      winRate:      ((wins.length / total) * 100).toFixed(2) + "%",
      profitFactor: avgL ? (avgW * wins.length / (avgL * losses.length || 1)).toFixed(2) : "—",
      expectancy:   (totalPnl / total).toFixed(2),
      avgRR:        avgW.toFixed(2) + " / -" + avgL.toFixed(2),
      maxDD:        "—",
    };
  }

  function mapEquity(pts) {
    return (pts || []).map(p => +(p.cumulative_pnl_rr || 0));
  }

  // ── On mount: fetch instrument list ──────────────────────────────────────
  React.useEffect(() => {
    window.ApiClient.fetchInstruments()
      .then(d => {
        const list = d.instruments || ["EURUSD"];
        setInstruments(list);
        // Validate stored instrument is still valid
        const stored = localStorage.getItem("crt_instrument");
        if (stored && !list.includes(stored)) {
          localStorage.setItem("crt_instrument", list[0]);
          setSelectedInstrument(list[0]);
        }
      })
      .catch(() => {/* keep default ["EURUSD"] */});
  }, []);

  // ── On mount + instrument change: full data reload ────────────────────────
  React.useEffect(() => {
    setInstrumentLoading(true);
    localStorage.setItem("crt_instrument", selectedInstrument);

    Promise.allSettled([
      window.ApiClient.fetchStatus(selectedInstrument),
      window.ApiClient.fetchTrades(selectedInstrument),
      window.ApiClient.fetchEquityCurve(selectedInstrument),
      window.ApiClient.fetchOpportunityStats(selectedInstrument),
      window.ApiClient.fetchModels(),
      window.ApiClient.fetchZoneGateModels(),
      window.ApiClient.fetchRRModels(),
      window.ApiClient.fetchTradeNetModels(),
      window.ApiClient.fetchBacktestHistory(),
      window.ApiClient.fetchScanJobs(selectedInstrument),
      window.ApiClient.fetchOpportunityAnalytics(selectedInstrument),
    ]).then(([sR, tR, eR, oR, mR, zgR, rrR, tnR, btR, sjR, oaR]) => {
      if (sR.status === "fulfilled") setStatus(sR.value);

      if (tR.status === "fulfilled") {
        const recs = tR.value.records || [];
        setTrades(mapTrades(recs));
        setTradeKpis(deriveTradeKpis(recs));
      }

      if (eR.status === "fulfilled") setEquity(mapEquity(eR.value.curve));
      if (oR.status === "fulfilled") setOppStats(oR.value);

      if (mR.status  === "fulfilled") {
        setModels((mR.value.models || []).map(m => ({
          ver:        m.version || "—",
          type:       "Gaussian (ML)",
          corr:       +(m.corr_expected_rr  || 0),
          cal:        +(m.calibration_error || 0),
          trained:    (m.trained_at || "—").slice(0, 10),
          samples:    m.n_train || null,
          status:     m.active ? "ACTIVE" : "Archived",
          action:     m.active ? "Active" : "Promote",
          run_id:     m.run_id     || null,
          instrument: m.instrument || null,
        })));
      }
      if (zgR.status === "fulfilled") {
        setZoneModels((zgR.value.models || []).map(m => ({
          ver:        m.version || "—",
          nZones:     m.n_zones || 0,
          nClusters:  m.n_clusters_requested || 0,
          trained:    (m.trained_at || "—").slice(0, 10),
          modelFile:  (m.model_file || "").split(/[\\/]/).pop() || "—",
          fileExists: !!m.file_exists,
          status:     m.active ? "ACTIVE" : "Archived",
          action:     m.active ? "Active" : "Promote",
          run_id:     m.run_id     || null,
          instrument: m.instrument || null,
        })));
      }
      if (rrR.status === "fulfilled") {
        setRrModels((rrR.value.models || []).map(m => ({
          ver:         m.version || "—",
          samples:     m.n_samples,
          features:    m.n_features || 35,
          ridgeAlpha:  m.ridge_alpha,
          modelExists: !!m.model_exists,
          trained:     (m.trained_at || "—").slice(0, 10),
          status:      m.active ? "ACTIVE" : "Archived",
          action:      m.active ? "Active" : "Promote",
          run_id:      m.run_id     || null,
          instrument:  m.instrument || null,
        })));
      }
      if (tnR.status === "fulfilled") {
        setTradenetModels((tnR.value.models || []).map(m => ({
          ver:        m.version || "—",
          modelFile:  (m.model_file || "").split(/[\\/]/).pop() || "—",
          trained:    (m.trained_at || "—").slice(0, 10),
          fileExists: !!m.file_exists,
          status:     m.active ? "ACTIVE" : "Archived",
          action:     m.active ? "Active" : "Promote",
          run_id:     m.run_id     || null,
          instrument: m.instrument || null,
        })));
      }
      if (btR.status === "fulfilled") {
        setBacktestHistory((btR.value.backtests || []).map(b => ({
          ver:      b.version || "—",
          type:     "Gaussian",
          corr:     +(b.corr_expected_rr || 0),
          cal:      +(b.calibration_error || 0),
          trained:  b.trained_at ? b.trained_at.slice(0, 10) : "—",
          samples:  b.n_samples || 0,
          verdict:  b.verdict || "—",
          approved: !!b.integration_approved,
        })));
      }
      if (sjR.status === "fulfilled") setScanJobs(sjR.value.jobs || []);
      if (oaR.status === "fulfilled") setOpportunityAnalytics(oaR.value);

      setInstrumentLoading(false);
    });
  }, [selectedInstrument]);

  // ── 30s lightweight refresh (status + trades + equity only) ──────────────
  React.useEffect(() => {
    const id = setInterval(function () {
      Promise.allSettled([
        window.ApiClient.fetchStatus(selectedInstrument),
        window.ApiClient.fetchTrades(selectedInstrument),
        window.ApiClient.fetchEquityCurve(selectedInstrument),
      ]).then(function ([sR, tR, eR]) {
        if (sR.status === "fulfilled") setStatus(sR.value);
        if (tR.status === "fulfilled") {
          const recs = tR.value.records || [];
          setTrades(mapTrades(recs));
          setTradeKpis(deriveTradeKpis(recs));
        }
        if (eR.status === "fulfilled") setEquity(mapEquity(eR.value.curve));
      });
    }, 30000);
    return function () { clearInterval(id); };
  }, [selectedInstrument]);

  // ── Shared runtime props (passed to every page) ───────────────────────────
  const runtimeProps = {
    selectedInstrument,
    instruments,
    instrumentLoading,
    status,
    trades,
    tradeKpis,
    equity,
    oppStats,
    models,
    zoneModels,
    rrModels,
    tradenetModels,
    backtestHistory,
    scanJobs,
    opportunityAnalytics,
    // Setters needed by pages that promote/mutate registry data
    setModels,
    setZoneModels,
    setRrModels,
    setTradenetModels,
  };

  // ── Pages ─────────────────────────────────────────────────────────────────
  const PAGES = [
    { id: "Executive",    Component: ExecutivePage    },
    { id: "Runtime",      Component: RuntimePage      },
    { id: "Research",     Component: ResearchPage     },
    { id: "Models",       Component: ModelsPage       },
    { id: "Trades",       Component: TradesPage       },
    { id: "Backtests",    Component: BacktestsPage    },
    { id: "System",       Component: SystemPage       },
    { id: "Intelligence", Component: IntelligencePage },
    { id: "Replay Lab",   Component: ReplayPage       },
  ];
  const active = PAGES.find(p => p.id === activePage) || PAGES[0];

  return (
    <div className="app-shell">
      <TopBar
        activePage={activePage}
        onNav={(p) => { setActivePage(p); setActiveSub(p); }}
        instruments={instruments}
        selectedInstrument={selectedInstrument}
        instrumentLoading={instrumentLoading}
        status={status}
        onInstrumentChange={(inst) => setSelectedInstrument(inst)}
      />
      <div className="app-body">
        <SidebarNew
          activePage={activePage}
          activeSub={activeSub}
          onNav={setActivePage}
          onSubNav={setActiveSub}
        />
        <div className="content-area">
          <active.Component
            activeSub={activeSub}
            setActiveSub={setActiveSub}
            {...runtimeProps}
          />
        </div>
      </div>
    </div>
  );
}

// Mount immediately — realData.js is being phased out
window.CrtDashboard = CrtDashboard;
ReactDOM.createRoot(document.getElementById("root")).render(<CrtDashboard />);
