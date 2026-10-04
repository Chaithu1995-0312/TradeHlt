> Created: 2026-05-19 · Updated: 2026-05-19 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Configurable UI Poll Interval (default 3 min)

## Context
The control plane UI polls `/runs?q=` and `/monitors/dashboard` every **2 seconds** via a hardcoded `setInterval` in `realApi.js`. The `monitors()` method also fires an uncached fetch on every render. Both behaviours generate excessive server log noise. The user wants the interval configurable (single place to change) and defaulted to **3 minutes (180 000 ms)**. Following project convention, all tunables live in the production config — the server surfaces the value to the frontend at startup via the existing `/commands` response.

---

## Files to change

| File | Change |
|---|---|
| `configs/production/v1_multi_2026_03.json` | Add `"control_plane"` section with `"ui_poll_interval_ms": 180000` |
| `src/control_plane/server.py` | Include `poll_interval_ms` in `commands_payload()` response |
| `ui_kits/control_plane/realApi.js` | Read interval from server, use for `setInterval`; add TTL debounce to `monitors()` |

---

## Step-by-step

### 1. `configs/production/v1_multi_2026_03.json`
Add a new top-level section after `"alphavantage_data"`:
```json
"control_plane": {
  "ui_poll_interval_ms": 180000
}
```
Then re-hash: `python scripts/maintenance/_compute_hash.py`

### 2. `src/control_plane/server.py` — `ControlPlaneAPI.commands_payload()`
Load the section and append `poll_interval_ms` to the response so the frontend gets it on the very first call (startup).

```python
# in commands_payload(), before the return:
try:
    from src.config_layer.config_loader import get_prod_section
    cp_cfg = get_prod_section("control_plane")
    poll_ms = int(cp_cfg.get("ui_poll_interval_ms", 180_000))
except Exception:
    poll_ms = 180_000

return {
    "commands": commands,
    "categories": categories,
    "workflow_stages": list(workflow_stage_order()),
    "poll_interval_ms": poll_ms,
}
```

### 3. `ui_kits/control_plane/realApi.js`

**a) Hold the interval until `/commands` resolves, then start polling:**

Replace lines 56-58:
```js
// Before: hardcoded 2-second poll started immediately
// After: interval driven by server config, started after /commands resolves

let _pollIntervalMs = 180_000;  // fallback until server responds
let _pollTimer = null;

function _startPolling(intervalMs) {
  if (_pollTimer) clearInterval(_pollTimer);
  _pollIntervalMs = intervalMs;
  _pollTimer = setInterval(
    () => Promise.all([_fetchRuns(), _fetchDashboard()]).catch(() => {}),
    _pollIntervalMs
  );
}

// Startup: fetch everything, then start timer with server-provided interval
Promise.all([_fetchCommands(), _fetchRuns(), _fetchDashboard(), _fetchCatalog()])
  .then(() => {
    const cmd = _cache;   // _fetchCommands already stored poll_interval_ms in _cache
    _startPolling(_cache.poll_interval_ms || 180_000);
  })
  .catch(() => { _startPolling(180_000); });
```

Store `poll_interval_ms` in `_cache` inside `_fetchCommands()`:
```js
async function _fetchCommands() {
  try {
    const d = await fetch(BASE + "/commands").then(r => r.json());
    _cache.commands        = d.commands        || [];
    _cache.categories      = d.categories      || [];
    _cache.workflow_stages = d.workflow_stages || [];
    _cache.poll_interval_ms = d.poll_interval_ms || 180_000;  // ← add
    _notify();
  } catch (e) { console.warn("[realApi] fetchCommands failed:", e.message); }
}
```

**b) Debounce `monitors()` with a per-run TTL:**
```js
let _monsTtl = {};  // run_id -> last-fetch epoch ms

monitors(runId) {
  const now = Date.now();
  const stale = !_monsTtl[runId] || (now - _monsTtl[runId]) >= _pollIntervalMs;
  if (stale) {
    _monsTtl[runId] = now;
    fetch(BASE + `/runs/${runId}/monitors`).then(r => r.json()).then(d => {
      _monsCache[runId] = d; _notify();
    }).catch(() => {});
  }
  return _monsCache[runId] || { fields: [] };
},
```

---

## Verification
1. Start server: `python src/control_plane/server.py`
2. Open browser console on the control plane UI — confirm `[realApi] fetchCommands` fires once at startup and `setInterval` uses 180 000 ms
3. Watch server logs for 5 minutes — should see at most 2 poll cycles (one at startup + one at 3 min), not a flood of 2-second calls
4. Re-hash after config change: `python scripts/maintenance/_compute_hash.py`
