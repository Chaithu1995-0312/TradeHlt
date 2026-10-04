# CRT Web Control Plane Architecture

## Intent
Provide an internal web control plane that orchestrates existing CRT CLI workflows without changing engine internals.

## Components
- `src/control_plane/registry.py`
  - Single source of truth for command metadata, args schema, category, tutorial stage, quickstart notes, and artifact patterns.
- `src/control_plane/jobs.py`
  - Threaded subprocess executor with persisted run records, log capture, and artifact discovery.
- `src/control_plane/server.py`
  - HTTP API + UI surface.
  - Includes tutorial playbook and first-run guided tour.
  - API routes:
    - `GET /commands`
    - `POST /commands/{id}/runs`
    - `GET /runs`
    - `GET /runs/{run_id}`
    - `GET /runs/{run_id}/logs`
    - `GET /runs/{run_id}/artifacts`
    - `POST /runs/{run_id}/stop`
- `scripts/control_plane/run_server.py`
  - Launch entrypoint.

## Tutorial Subsystem
- Tutorial style:
  - Workflow Playbook panel (persistent navigation/checklist)
  - First-run overlay tour (autostart on first visit)
- Tutorial state persistence (browser-local only):
  - `tutorial_seen`
  - `tutorial_dismissed_version`
  - `playbook_completed`
  - `tutorial_progress`
- UI anchors:
  - `#playbookPanel`
  - `#helpBtn`
  - `#tourOverlay` and `#tourCard`

## Using The Tutorial
1. Open control plane and let the first-run tour walk through core controls.
2. Use **Help / Start Tour** to replay guidance anytime.
3. Use the **Tutorial / Playbook** panel to jump to commands and mark progress.
4. Confirm artifacts in Run Inspector before moving to the suggested next step.

## Dependency Graph Reference
The dependency graph is generated, not committed by default:

```bash
python scripts/analysis/gen_pyan.py
```

Expected artifacts:
- `pyan_call_flow.dot`
- `pyan_err.txt`

Attach `pyan_call_flow.dot` to architecture reviews for impact-radius analysis.

## CLI Matrix Sync
Generate docs from registry:

```bash
python scripts/analysis/generate_cli_matrix.py
```

Output:
- `docs/CLI_MATRIX.md`
