> Created: 2026-05-07 · Updated: 2026-05-07 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Make `--version` Optional in `from-report` CLI Subcommand

## Context
Running `promotion_manager.py from-report` without `--version` fails with a hard argparse error even though the `ValidationReport` JSON already contains a `config_id` field that is a suitable version label. The fix makes `--version` optional and auto-derives it from `config_id` in the report when omitted.

---

## Critical File
- `src/governance/promotion_manager.py` — the only file to change

---

## Implementation

### 1. Make `--version` optional in the argparse definition
**Location:** `from_report_p.add_argument` call (lines 585–588)

```python
# Before
from_report_p.add_argument("--version", required=True)

# After
from_report_p.add_argument(
    "--version",
    default=None,
    help="Version label; defaults to config_id from the report"
)
```

### 2. Auto-derive version in the CLI handler
In the `if args.command == "from-report":` branch (just before calling `pm.promote_from_report`), add:

```python
version = args.version
if version is None:
    import json as _json
    with open(args.report) as _f:
        _rpt = _json.load(_f)
    version = _rpt.get("config_id")
    if not version:
        parser.error("--version is required: report contains no config_id to derive from")
    print(f"[promotion_manager] --version not supplied; using config_id '{version}' from report")
```

Then pass `version` (not `args.version`) to `pm.promote_from_report(...)`.

---

## Constraints / No-ops
- `promote_from_report()` signature is unchanged — version is still a required parameter there; the default-derivation is CLI-only.
- No changes to `ValidationReport`, `_execute_promotion`, or any other module.
- The report file is opened once here for version derivation; `promote_from_report` opens it again internally — acceptable duplication for minimal diff.

---

## Verification
1. Re-run the original failing command (no `--version`):
   ```
   python src/governance/promotion_manager.py from-report \
     --report results/validation/approved/report_v2_multi_2026_04.json
   ```
   Expected: prints the derived version and proceeds (or fails on a missing report file, not on missing `--version`).

2. Confirm explicit `--version` still works:
   ```
   python src/governance/promotion_manager.py from-report \
     --report <path> --version v2_multi_2026_04
   ```
   Expected: uses the supplied version unchanged.

3. Confirm error message when report has no `config_id` and no `--version` supplied.
