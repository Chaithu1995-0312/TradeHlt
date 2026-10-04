# Fix: control-plane UI 404s on `/ui_kits/*.jsx`

## Context
Opening `http://127.0.0.1:8787/ui_kits/control_plane` (no trailing slash) loads a blank UI; console shows 404s for
`/ui_kits/ExplorerPanel.jsx`, `InspectorPanel.jsx`, `WorkflowPanel.jsx`, `AgentPanel.jsx`, `App.jsx`
(the `favicon.ico` 404 is harmless).

## Root cause (verified, not assumed)
- All the files exist in `ui_kits/control_plane/` on this branch.
- `src/control_plane/server.py:1829-1858` serves `/ui_kits/...`; when the path is a directory it silently serves
  `index.html` with 200 (line 1843-1844) **without redirecting to a trailing slash**.
- `ui_kits/control_plane/index.html:18-33` uses relative `src="ExplorerPanel.jsx"` etc., so the browser resolves them against
  `/ui_kits/` → `/ui_kits/ExplorerPanel.jsx` → 404.
- Live curl: `/ui_kits/control_plane` → 200, `/ui_kits/ExplorerPanel.jsx` → 404, `/ui_kits/control_plane/ExplorerPanel.jsx` → 200.

Immediate workaround: use the trailing slash — `http://127.0.0.1:8787/ui_kits/control_plane/` (this is also what `/` redirects to).

## Fix
In `src/control_plane/server.py`, in the `/ui_kits/` branch (~line 1841), when `_fp.is_dir()` and `path` does not end with `/`,
send a `302/301` to `path + "/"` (preserve query string) instead of serving index.html. Reuse the existing redirect pattern
at lines 1860-1866 (`HTTPStatus.FOUND`, `Location`, `Content-Length: 0`, CORS header). Keep the existing
trailing-slash → `index.html` behavior. Applies equally to `crt_dashboard` and `live_monitor`.

Optional (not required): add a tiny `/favicon.ico` 204 to silence the noise — skipping unless asked (scope control).

## Verification
1. Restart the control plane server (it must be restarted to pick up server.py changes).
2. `curl -sI http://127.0.0.1:8787/ui_kits/control_plane` → 302 with `Location: /ui_kits/control_plane/`.
3. `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8787/ui_kits/control_plane/App.jsx` → 200.
4. Open the page in the built-in browser at the no-slash URL; confirm no 404s in console and panels render.
5. Run any existing control-plane server test (`pytest -k control_plane -q`, targeted only) — not the full suite.
