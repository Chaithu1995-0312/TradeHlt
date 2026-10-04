# research_framework_phase0_repair_2026-09-14

- Created (UTC): 2026-09-14T12:36:23Z
- Plan: research-framework consolidation (shim-in-place, archive-tracked), Phase 0 — freeze the existing extraction
- Policy: **no deletes** — broken live bytes copied here byte-exact before the fix

## Why

`probes_extraction_clear18_2026-09-14` rewrote `importlib.util.spec_from_file_location(...)` blocks to
`research.probes.scriptmod.load_py(...)` in 9 `scripts/analysis/` files but recorded none of them in its
MANIFEST.csv. The rewrite dropped the indentation of the replacement statement, leaving
`mod = load_py(...)` at column 0 inside a function body → `IndentationError` on import. Found by running the
14 test files that load these scripts under `venv` (Python 3.12): 35 collection errors.

## Files (fix = re-indent one line by 4 spaces)

| Live path | Broken bytes kept at |
|---|---|
| scripts/analysis/fm021_retest_depth_certification.py | scripts/analysis/fm021_retest_depth_certification.py |
| scripts/analysis/crt_declare_all_knobs_parity.py | scripts/analysis/crt_declare_all_knobs_parity.py |
| scripts/analysis/update_reachability_golden.py | scripts/analysis/update_reachability_golden.py |
| scripts/analysis/hour_of_day_certification.py | scripts/analysis/hour_of_day_certification.py |
| scripts/analysis/reachability_validation_report.py | scripts/analysis/reachability_validation_report.py |
| scripts/analysis/session_certification.py | scripts/analysis/session_certification.py |
| scripts/analysis/trend_strength_certification.py | scripts/analysis/trend_strength_certification.py |
| scripts/analysis/volatility_regime_certification.py | scripts/analysis/volatility_regime_certification.py |
| scripts/analysis/zone_assignment_parity_probe.py | scripts/analysis/zone_assignment_parity_probe.py |

SHA-256 before/after: `MANIFEST.csv`.

## Parity evidence

- `diff` archived-broken vs live: exactly one changed line per file.
- CRLF line count identical before/after (line endings untouched).
- `venv\Scripts\python.exe -m py_compile` clean on all 9.

Not changed: import placement. In `crt_declare_all_knobs_parity.py` and `zone_assignment_parity_probe.py` the
`load_py` import sits above the `sys.path` insert, and `update_reachability_golden.py` /
`reachability_validation_report.py` have no insert at all; `research` still resolves through the editable
install (`pip install -e .`). Left as-is to keep this repair to the one breaking line.
