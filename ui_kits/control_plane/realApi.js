// realApi.js — Real backend adapter matching mockApi.js interface exactly.
// Fetches from http://localhost:8787. Exposes same global `mockApi` variable
// so all JSX components work without modification.

const BASE = "http://localhost:8787";

const _listeners = [];
let _cache = {
  commands: [], categories: [], workflow_stages: [],
  runs: [], dashboard: { commands: [] },
};
let _runCache  = {};   // run_id -> run snapshot
let _logsCache = {};   // run_id -> logs payload
let _artsCache = {};   // run_id -> artifacts payload
let _monsCache = {};   // run_id -> monitors payload

function _notify() {
  _listeners.forEach(cb => { try { cb(); } catch (_) {} });
}

async function _fetchCommands() {
  try {
    const d = await fetch(BASE + "/commands").then(r => r.json());
    _cache.commands        = d.commands        || [];
    _cache.categories      = d.categories      || [];
    _cache.workflow_stages = d.workflow_stages || [];
    _notify();
  } catch (e) { console.warn("[realApi] fetchCommands failed:", e.message); }
}

async function _fetchRuns(search = "") {
  try {
    const d = await fetch(BASE + `/runs?q=${encodeURIComponent(search)}`).then(r => r.json());
    _cache.runs = d.runs || [];
    _cache.runs.forEach(r => { _runCache[r.run_id] = r; });
    _notify();
  } catch (e) { console.warn("[realApi] fetchRuns failed:", e.message); }
}

async function _fetchDashboard() {
  try {
    const d = await fetch(BASE + "/monitors/dashboard").then(r => r.json());
    _cache.dashboard = d;
    _notify();
  } catch (e) { console.warn("[realApi] fetchDashboard failed:", e.message); }
}

async function _fetchCatalog() {
  try {
    const d = await fetch(BASE + "/catalog").then(r => r.json());
    window.CATALOG = d;
    _notify();
  } catch (e) { console.warn("[realApi] fetchCatalog failed:", e.message); }
}

// --- Startup + 2-second polling ---
Promise.all([_fetchCommands(), _fetchRuns(), _fetchDashboard(), _fetchCatalog()]).catch(() => {});
setInterval(() => Promise.all([_fetchRuns(), _fetchDashboard()]).catch(() => {}), 2000);

// --- Public API (matches mockApi interface exactly) ---
const mockApi = {

  /** Register a change listener. Returns an unsubscribe function. */
  subscribe(cb) {
    _listeners.push(cb);
    return () => {
      const i = _listeners.indexOf(cb);
      if (i >= 0) _listeners.splice(i, 1);
    };
  },

  /** Returns the full command catalogue. */
  commands() {
    return {
      commands:        _cache.commands,
      categories:      _cache.categories,
      workflow_stages: _cache.workflow_stages,
    };
  },

  /** Filtered run list. Triggers a background refresh each call. */
  listRuns(search = "") {
    _fetchRuns(search).catch(() => {});
    const q = (search || "").toLowerCase();
    const runs = q
      ? _cache.runs.filter(r => r.command_id.includes(q) || r.run_id.includes(q))
      : _cache.runs;
    return { runs };
  },

  /** Single run snapshot from local cache. */
  getRun(runId) {
    // Refresh in background for running/queued jobs
    const cached = _runCache[runId];
    if (cached && (cached.status === "running" || cached.status === "queued")) {
      fetch(BASE + `/runs/${runId}`).then(r => r.json()).then(d => {
        if (d.run) { _runCache[d.run.run_id] = d.run; _notify(); }
      }).catch(() => {});
    }
    return { run: cached || null };
  },

  /** Stdout/stderr logs (fetched on demand, cached). */
  logs(runId) {
    if (!_logsCache[runId]) {
      fetch(BASE + `/runs/${runId}/logs`).then(r => r.json()).then(d => {
        _logsCache[runId] = d;
        _notify();
      }).catch(() => {});
      return { logs: { stdout: "Loading…", stderr: "" } };
    }
    // Re-fetch if run is still active
    const run = _runCache[runId];
    if (run && (run.status === "running" || run.status === "queued")) {
      fetch(BASE + `/runs/${runId}/logs`).then(r => r.json()).then(d => {
        _logsCache[runId] = d; _notify();
      }).catch(() => {});
    }
    return _logsCache[runId];
  },

  /** Artifact list (fetched on demand, cached). */
  artifacts(runId) {
    if (!_artsCache[runId]) {
      fetch(BASE + `/runs/${runId}/artifacts`).then(r => r.json()).then(d => {
        _artsCache[runId] = d; _notify();
      }).catch(() => {});
    }
    return _artsCache[runId] || { artifacts: [] };
  },

  /** Monitor fields (always re-fetched so sparklines stay live). */
  monitors(runId) {
    fetch(BASE + `/runs/${runId}/monitors`).then(r => r.json()).then(d => {
      _monsCache[runId] = d; _notify();
    }).catch(() => {});
    return _monsCache[runId] || { fields: [] };
  },

  /** Latest-per-command monitoring dashboard. */
  dashboard() {
    return _cache.dashboard || { commands: [] };
  },

  /**
   * File picker — returns a Promise<{files}>.
   * The LauncherPanel's FileUploader passes a glob and expects an array of paths.
   */
  files(glob) {
    return fetch(BASE + `/files?glob=${encodeURIComponent(glob || "")}`).then(r => r.json());
  },

  /**
   * Start a new run.
   * Returns a placeholder run immediately (sync) so the UI can react.
   * The real run_id arrives async and replaces the placeholder.
   */
  createRun(commandId, args, cmdline) {
    const fakeId = "pending-" + Date.now();
    const placeholder = {
      run_id: fakeId, command_id: commandId, status: "queued",
      args: args || {}, cmdline: cmdline || "",
      started_at: new Date().toISOString(), ended_at: null,
    };
    _runCache[fakeId] = placeholder;
    _cache.runs.unshift(placeholder);
    _notify();

    fetch(BASE + `/commands/${commandId}/runs`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ args: args || {} }),
    }).then(r => r.json()).then(d => {
      if (d.run) {
        _runCache[d.run.run_id] = d.run;
        // Replace placeholder with real run
        _cache.runs = _cache.runs.filter(r => r.run_id !== fakeId);
        _cache.runs.unshift(d.run);
        _notify();
      }
    }).catch(e => { console.error("[realApi] createRun failed:", e.message); });

    return { run: placeholder };
  },

  /** Stop a running job. */
  stop(runId) {
    fetch(BASE + `/runs/${runId}/stop`, { method: "POST" })
      .then(r => r.json())
      .then(d => { if (d.run) { _runCache[d.run.run_id] = d.run; _notify(); } })
      .catch(e => { console.warn("[realApi] stop failed:", e.message); });
    return {};
  },

  /** Request a Claude-powered Context Report for a completed run. */
  contextReport(runId) {
    return fetch(BASE + `/runs/${runId}/context/report`, { method: "POST" })
      .then(r => r.json());
  },
};
