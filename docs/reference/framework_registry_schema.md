# Framework Registry — JSONL Schema

> The single, queryable, append-only map of the codebase against the 6-level trading-system
> hierarchy ([`docs/architecture/TRADING_SYSTEM_FRAMEWORK.md`](../architecture/TRADING_SYSTEM_FRAMEWORK.md)).
> One record per line at [`data/framework_registry.jsonl`](../../data/framework_registry.jsonl).
> Loaded/validated by [`src/governance/framework_registry.py`](../../src/governance/framework_registry.py),
> enforced by [`tests/test_framework_registry.py`](../../tests/test_framework_registry.py).
>
> **Append-only (CLAUDE.md §6.2 rule 4).** A status change is a *new* line with a new
> `last_validated`; prior lines are never mutated or deleted. `load()` keeps the latest line per `id`.

---

## Line schema

Each line is one JSON object with exactly these fields:

```json
{
  "id": "DOMAIN-001",
  "type": "domain",
  "level": 1,
  "name": "CryptoSpot",
  "parent": null,
  "children": ["STYLE-001", "STYLE-002"],
  "evidence": [
    {"path": "scripts/data/fetch_crypto_ccxt.py", "line": 31, "symbol": "_INSTRUMENTS", "type": "code"},
    {"path": "configs/production/v2_multi_2026_04.json", "line": null, "symbol": "session_calendar", "type": "config"}
  ],
  "findings": ["F-019", "F-020"],
  "tests": ["tests/test_dataset_integrity.py"],
  "status": "implicit",
  "created": "2026-06-16T00:00:00Z",
  "last_validated": "2026-06-16T00:00:00Z",
  "notes": "No Domain class exists — domain is implicit in config + data scripts."
}
```

| Field | Type | Rule |
|---|---|---|
| `id` | str | Unique across the file. Convention `TYPE-NNN` (e.g. `DOMAIN-001`, `STYLE-002`). |
| `type` | enum | See **Type enum**. |
| `level` | int 0–6 | Must match `type` for the level-bound types (see **Level binding**). |
| `name` | str | Human label. |
| `parent` | str \| null | An `id` in this file, or `null` for a root. |
| `children` | list[str] | Each must be an `id` in this file. |
| `evidence` | list[obj] | `{path, line, symbol, type}`. `line`/`symbol` may be `null` for non-code evidence. |
| `findings` | list[str] | Each must be an `F-NNN` in [`docs/current-findings.md`](../current-findings.md). |
| `tests` | list[str] | Test file paths (existence-checked). |
| `status` | enum | See **Status enum**. |
| `created` | str | ISO-8601 UTC (`...Z`). |
| `last_validated` | str | ISO-8601 UTC. Bumped on each new line for the same `id`. |
| `notes` | str | Free text — record *why*, especially verified-status corrections. |

## Type enum
`kernel | domain | style | strategy | implementation | intent | risk | execution | component`

## Level enum
`0 | 1 | 2 | 3 | 4 | 5 | 6` (matching the framework hierarchy: 0 Kernel · 1 Domain · 2 Style ·
3 Strategy · 4 Intelligence/AI · 5 Risk · 6 Execution).

### Level binding
These types pin a level; the validator enforces the pair:

| type | level |
|---|---|
| `kernel` | 0 |
| `domain` | 1 |
| `style` | 2 |
| `strategy` | 3 |
| `implementation` | 4 |
| `risk` | 5 |
| `execution` | 6 |

`intent` and `component` are cross-cutting/meta and are **not** level-bound (any level).

## Status enum
`extant | implicit | orphaned | killed | dormant | planned | stub`

- `extant` — exists and is wired into a live path.
- `implicit` — behavior exists but no dedicated class (e.g. domain rules scattered in config/scripts).
- `orphaned` — code exists but has **no runtime callers** (distinct from a *structural* tree orphan).
- `dormant` — built, gated off / sidecar-only.
- `stub` — placeholder / unverified live path.
- `planned` — designed, not built.
- `killed` — retired per a Funding-Ledger decision.

> **`status: "orphaned"` ≠ structural orphan.** `status` describes *runtime* wiring (F-006/F-013).
> `FrameworkRegistry.get_orphaned()` reports *structural* orphans (a node with no parent **and** no
> children — disconnected from the tree). Do not conflate them.

## Evidence type enum
`code | config | doc | test | finding`

- `code` evidence is validated by the §6.3 rule: `path` resolves, `symbol` present within
  ±30 lines of `line` (symbol authoritative, line a hint).
- `config | doc | test` evidence: `path` existence only.
- `finding` evidence: the `symbol` is an `F-NNN` checked against the findings doc.

---

## Validation contract (enforced by `tests/test_framework_registry.py`)

1. Every line parses and passes `FrameworkRegistry.validate_record` (required fields + enums + level binding).
2. Every `evidence[].path` resolves; `code` evidence symbol sits within the ±30-line drift window.
3. Every `findings[]` id exists (non-terminal) in `docs/current-findings.md`.
4. No dangling `parent` / `children[]` ids.
5. `id`s are unique.
6. Appending a line does not mutate existing lines (append-only).

`python scripts/governance/query_registry.py --validate` runs 2–5 as the standing CI gate.
