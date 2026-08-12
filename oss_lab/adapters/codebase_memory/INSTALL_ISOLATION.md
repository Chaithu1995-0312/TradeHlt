# Codebase-Memory — Install Isolation Policy (lab only)

| Field | Value |
|---|---|
| Pin | **v0.10.2** (`b377c62a4e8b7ad64ccd295e4aa88abc8d275180`) |
| Status | **APPROVED_FOR_LAB** — isolation chosen; binary **not yet activated**; extract only under this policy |
| Authority | RESEARCH_LAB_ONLY |

## Allowed locations

| Purpose | Path |
|---|---|
| Extracted/install tree | `tools/oss_lab/codebase-memory/v0.10.2/` |
| Pin archive (verified) | `results/oss_lab/repo_intel/codebase_memory_v0.10.2/codebase-memory-mcp-windows-amd64.zip` |
| CBM graph cache | Preferred: `results/oss_lab/repo_intel/cbm_cache/`. **Windows note:** if `cache-private` fails under `results/`, use `%LOCALAPPDATA%\codebase-memory-mcp-lab-tradelatest` (lab-named; not production venv). |
| Benchmark evidence | `results/oss_lab/repo_intel/<run_id>/` |
| Gate evidence (small) | `oss_lab/evidence/repo_intel/codebase_memory_v0.10.2/` |

## Forbidden locations

- `venv/`, `.venv/`, or any production Python env
- Writing into `docs/governance/semantic_os/`
- Writing into `configs/production/` or `src/`
- Default global agent MCP config mutation during lab install

## Required environment (lab)

```text
CBM_CACHE_DIR = <repo>/results/oss_lab/repo_intel/cbm_cache
CBM_ALLOWED_ROOT = <repo root absolute path>
CBM_LOG_LEVEL = info
```

## Required install flags

Prefer **binary-only / skip agent config**:

```powershell
# After extract into tools/oss_lab/codebase-memory/v0.10.2/
# Use install.ps1 options that skip agent auto-config when available.
# Prefer: --skip-config (or equivalent) so Claude/Cursor/VS Code configs are NOT mutated.
```

If the installer cannot skip config, **do not run install** — use CLI-from-extracted-path only after manual review.

## Secrets / .env

Before any `index_repository` of Tradelatest:

1. Confirm `.env` is not indexed (gitignore + `.cbmignore`).
2. Create/append `.cbmignore` (lab) for: `.env`, `**/.env`, `*.pem`, `secrets/`, `credentials*`.
3. Never print secrets into session logs.

## Pre-execute verification residual

SHA-256 of Windows zip already matched pin. Before first execute, recommended:

```text
gh attestation verify <zip> --repo DeusData/codebase-memory-mcp ...
cosign verify-blob --bundle <zip>.bundle <zip>
```

## Network residual

SECURITY.md documents a best-effort GitHub `releases/latest` check after MCP `initialize`. Lab may block outbound GitHub after pin download if zero-network is required.
