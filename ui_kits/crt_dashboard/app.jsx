// Top-level CRT dashboard — composes all six panels in a 2-column grid
// matching the prototype's overview layout.

function CrtDashboard() {
  return (
    <div className="dash-root">
      <div className="dashboard-grid">
        <div>
          <SectionTitle index="1" title="Runtime / Live Trading Dashboard" subtitle="Live Execution · Model Fusion · Real-time State" />
          <RuntimePage />
        </div>
        <div>
          <SectionTitle index="2" title="Research / Opportunity Explorer (Pipeline B)" subtitle="Unbiased Market Cartography · Opportunity Scanning · Feature Space" />
          <ResearchPage />
        </div>
        <div>
          <SectionTitle index="3" title="Models / Model Registry & Governance" subtitle="Model Catalog · Performance · Promotion · Lineage" />
          <ModelsPage />
        </div>
        <div>
          <SectionTitle index="4" title="Trades / Trade Analytics & Journal" subtitle="Performance · Distribution · Sessions · Detailed Journal" />
          <TradesPage />
        </div>
        <div>
          <SectionTitle index="5" title="Backtests / Backtest Lab" subtitle="Strategy Backtesting · Walk Forward · Robustness" />
          <BacktestsPage />
        </div>
        <div>
          <SectionTitle index="6" title="System / System Health & Data Status" subtitle="Data Integrity · Jobs · Alerts · Infrastructure" />
          <SystemPage />
        </div>
      </div>
    </div>
  );
}

// Expose for deferred mount by realData.js (which fetches live data first).
// If realData.js is not loaded, mount immediately as fallback.
window.CrtDashboard = CrtDashboard;
if (!window._REAL_DATA_LOADING) {
  ReactDOM.createRoot(document.getElementById("root")).render(<CrtDashboard />);
}
