// apiClient.js — Centralized fetch surface for the CRT dashboard.
// Sets window.ApiClient. All dashboard fetch() calls go through here.
// No side effects, no state, pure fetch wrappers only.
// Loaded as a plain <script> (not Babel) before all JSX files.

(function () {
  "use strict";

  var BASE = "http://localhost:8787";

  function get(url) {
    return fetch(BASE + url).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status + " " + url);
      return r.json();
    });
  }

  window.ApiClient = {
    // Instrument discovery (reads from active prod config)
    fetchInstruments: function () {
      return get("/api/instruments");
    },

    // Per-instrument runtime status (model version, kill switch, trades_24h)
    fetchStatus: function (instrument) {
      return get("/api/status?instrument=" + encodeURIComponent(instrument));
    },

    // Per-instrument trade records
    fetchTrades: function (instrument) {
      return get("/api/trades?instrument=" + encodeURIComponent(instrument) + "&per_page=50");
    },

    // Per-instrument equity curve (cumulative PnL)
    fetchEquityCurve: function (instrument) {
      return get("/api/equity_curve?instrument=" + encodeURIComponent(instrument));
    },

    // Per-instrument opportunity / research stats
    fetchOpportunityStats: function (instrument) {
      return get("/api/opportunity_stats?instrument=" + encodeURIComponent(instrument));
    },

    // Per-instrument backtest runs (run dropdown) — results/run_<ts>_<INSTR>/
    fetchRuns: function (instrument) {
      return get("/api/runs?instrument=" + encodeURIComponent(instrument));
    },

    // Per-run consolidated Executive Overview payload
    fetchExecutive: function (instrument, run_id) {
      return get("/api/executive?instrument=" + encodeURIComponent(instrument) +
                 "&run_id=" + encodeURIComponent(run_id));
    },

    // Per-run OHLC + CRT-state (engine + resolver) + trades + event pins + gap bands +
    // dataset-integrity verdict, for the Trade Chart tab. `run_id` optional (defaults to
    // the latest run); `from`/`to` are ISO timestamps, optional (default: tail `limit` bars).
    fetchChartSeries: function (instrument, run_id, timeframe, limit, from_ts, to_ts) {
      var q = "/api/chart_series?instrument=" + encodeURIComponent(instrument);
      if (run_id)    q += "&run_id="   + encodeURIComponent(run_id);
      if (timeframe) q += "&timeframe=" + encodeURIComponent(timeframe);
      if (limit)     q += "&limit="    + encodeURIComponent(limit);
      if (from_ts)   q += "&from="     + encodeURIComponent(from_ts);
      if (to_ts)     q += "&to="       + encodeURIComponent(to_ts);
      return get(q);
    },

    // Per-instrument scan job history (list of scanner runs)
    fetchScanJobs: function (instrument) {
      return get("/api/scan_jobs?instrument=" + encodeURIComponent(instrument));
    },

    // Per-instrument analytics: scatter points + quarterly outcomes over time
    fetchOpportunityAnalytics: function (instrument) {
      return get("/api/opportunity_analytics?instrument=" + encodeURIComponent(instrument));
    },

    // Global model registries (not instrument-scoped)
    fetchModels:          function () { return get("/api/models"); },
    fetchZoneGateModels:  function () { return get("/api/zone_gate_models"); },
    fetchRRModels:        function () { return get("/api/rr_models"); },
    fetchTradeNetModels:  function () { return get("/api/tradenet_models"); },
    fetchBacktestHistory: function () { return get("/api/backtest_history"); },

    fetchKnowledgeSearch: function (q, opts) {
      opts = opts || {};
      var params = new URLSearchParams();
      params.set("q", q || "");
      if (opts.top_k) params.set("top_k", String(opts.top_k));
      if (opts.truth_class) params.set("truth_class", opts.truth_class);
      if (opts.include_historical === false) params.set("include_historical", "0");
      if (opts.explain) params.set("explain", "1");
      return get("/api/knowledge/search?" + params.toString());
    },
    fetchKnowledgeStatus: function () {
      return get("/api/knowledge/status");
    },

    fetchModelVersions:   function () { return get("/api/model_versions"); },

    // Groq AI explanation of a model's training results
    explainModel: function (model_type, version) {
      return fetch(BASE + "/api/explain_model", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ model_type: model_type, version: version }),
      }).then(function (r) { return r.json(); });
    },
  };
})();
