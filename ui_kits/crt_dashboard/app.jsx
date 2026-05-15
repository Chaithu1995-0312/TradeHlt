// Top-level CRT dashboard — single-panel navigation.
// Click a sidebar item to switch sections; only the active panel renders.

function CrtDashboard() {
  const [activePage, setActivePage] = React.useState("Runtime");

  // Expose setter so Sidebar <a> onClick can call window.__crtNav(id)
  window.__crtNav = setActivePage;

  const PAGES = [
    { id: "Runtime",   index: 1, title: "Runtime / Live Trading Dashboard",             sub: "Live Execution · Model Fusion · Real-time State",                    Component: RuntimePage   },
    { id: "Research",  index: 2, title: "Research / Opportunity Explorer (Pipeline B)", sub: "Unbiased Market Cartography · Opportunity Scanning · Feature Space", Component: ResearchPage  },
    { id: "Models",    index: 3, title: "Models / Model Registry & Governance",          sub: "Model Catalog · Performance · Promotion · Lineage",                 Component: ModelsPage    },
    { id: "Trades",    index: 4, title: "Trades / Trade Analytics & Journal",            sub: "Performance · Distribution · Sessions · Detailed Journal",          Component: TradesPage    },
    { id: "Backtests", index: 5, title: "Backtests / Backtest Lab",                      sub: "Strategy Backtesting · Walk Forward · Robustness",                  Component: BacktestsPage },
    { id: "System",    index: 6, title: "System / System Health & Data Status",          sub: "Data Integrity · Jobs · Alerts · Infrastructure",                   Component: SystemPage    },
  ];

  const active = PAGES.find(p => p.id === activePage) || PAGES[0];

  return (
    <div className="dash-root">
      <SectionTitle index={active.index} title={active.title} subtitle={active.sub} />
      <active.Component />
    </div>
  );
}

// Expose for deferred mount by realData.js (which fetches live data first).
// If realData.js is not loaded, mount immediately as fallback.
window.CrtDashboard = CrtDashboard;
if (!window._REAL_DATA_LOADING) {
  ReactDOM.createRoot(document.getElementById("root")).render(<CrtDashboard />);
}
