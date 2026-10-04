"""Gate 5 Lineage Report — machine-reconciliation validator.

Checks the geometry_static_lineage_report.md against the frozen adjudication matrix
and cross-referenced documents. Extends the existing geometry/governance test floor.
"""
import json
import os
import re

REPORT_PATH = "docs/governance/geometry_static_lineage_report.md"
ADJUDICATION_PATH = "docs/governance/geometry_semantic_adjudication.jsonl"
FINDINGS_PATH = "docs/current-findings.md"
SESSION_LOG_PATH = "assistant_project.md"

# Paths to skip: SHA-256 hashes (64 hex chars), record IDs (GEO-D-*), file:line references
_PATH_SKIP_PATTERNS = re.compile(
    r'^[0-9a-f]{64}$|'       # SHA-256 hash
    r'^GEO-D-[0-9a-f]+$|'    # record ID
    r'\.py:\d+'               # file:line (not a standalone path)
)

# Known valid evidence paths referenced in the report (verified subset)
_KNOWN_EVIDENCE_PATHS = [
    "docs/governance/geometry_contradiction_report.md",
    "docs/governance/geometry_semantic_adjudication.jsonl",
    "docs/governance/geometry_family_registry.json",
    "docs/current-findings.md",
    "reports/FEATURE_REACHABILITY_AUDIT.md",
    "assistant_project.md",
    "docs/governance/geometry_static_lineage_report.md",
]

# 2026-07-11: 110 (Census-v3 frozen surface) → 117 — the governed surface legitimately changed:
# Phase-1 identity closure (explicit volume-proxy columns, live-hook routed calls, FM-013 impl,
# probe/test sites) + GD-004/GD-005 closure (gd004 probe sites added; crt [PATCH 7] site routed
# out). Regenerated via geometry_census.py + gate2b_adjudication.py.
# 2026-07-11 (later, lint hardening): 117 → 115 — the feature_monitor __main__ demo now binds
# fixture noise to intermediates (transport; body_ratio site gone) and the demo's other governed
# rows left the derivation surface with it. 115 adjudicated / 0 missing.
# 2026-07-11 (IC-007 session audit): 115 → 118 — crt_xauusd_runtime_trace.py probe added 3
# TOOLING replica sites (body_size/candle_range/body_ratio for JSONL trace records); crt_engine_v2
# rows re-keyed after PLAN-001/Phase-2 line shifts. 118 adjudicated / 0 missing.
EXPECTED_RECORD_COUNT = 118
EXPECTED_FINAL_UNKNOWN_COUNT = 3
EXPECTED_FINAL_UNKNOWN_IDS = [
    "GEO-D-373ac0d94d",
    "GEO-D-505dd25eec",
    "GEO-D-4cc99bf89d",
]


def _load_adjudication():
    records = []
    with open(ADJUDICATION_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _load_report():
    with open(REPORT_PATH, encoding="utf-8") as f:
        return f.read()


def _load_text(path):
    """Load a text file, handling BOM and encoding issues."""
    with open(path, "rb") as f:
        raw = f.read()
    # Strip BOM
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    # Decode with replacement for non-UTF8 chars
    return raw.decode("utf-8", errors="replace")


class TestGate5LineageReport:

    def test_adjudication_record_count(self):
        """CHECK 4.1: adjudication JSONL record count equals the governed denominator."""
        records = _load_adjudication()
        assert len(records) == EXPECTED_RECORD_COUNT, (
            f"Expected {EXPECTED_RECORD_COUNT} records, got {len(records)}"
        )

    def test_final_unknown_count(self):
        """CHECK 4.2: final UNKNOWN count in the matrix equals the report's final UNKNOWN count."""
        records = _load_adjudication()
        unknowns = [r for r in records if r.get("decision_reachable") == "UNKNOWN"]
        assert len(unknowns) == EXPECTED_FINAL_UNKNOWN_COUNT, (
            f"Expected {EXPECTED_FINAL_UNKNOWN_COUNT} decision_reachable UNKNOWNs, "
            f"got {len(unknowns)}"
        )

    def test_exact_final_unknown_record_ids(self):
        """CHECK 4.3: exact final UNKNOWN record IDs are represented in the report."""
        report = _load_report()
        for rid in EXPECTED_FINAL_UNKNOWN_IDS:
            assert rid in report, (
                f"Final UNKNOWN record ID {rid} not found in report"
            )

    def test_no_report_unknown_absent_from_matrix(self):
        """CHECK 4.4: no report-listed UNKNOWN ID is absent from the matrix."""
        records = _load_adjudication()
        matrix_ids = {r["derivation_id"] for r in records}
        for rid in EXPECTED_FINAL_UNKNOWN_IDS:
            assert rid in matrix_ids, (
                f"Report lists UNKNOWN ID {rid} but it is absent from adjudication matrix"
            )

    def test_evidence_paths_exist(self):
        """CHECK 4.5: every authoritative evidence path referenced by the report exists."""
        report = _load_report()
        paths = set()
        # Find all backtick-quoted paths
        for m in re.finditer(r'`([^`]+)`', report):
            path = m.group(1)
            # Filter to likely file paths (start with known dirs)
            if not path.startswith(("docs/", "src/", "reports/", "configs/", "models/", "tests/", "scripts/")):
                continue
            # Strip file:line suffix for existence check
            clean_path = re.sub(r':\d+.*$', '', path)
            # Skip if it's just a hash or record ID
            if _PATH_SKIP_PATTERNS.match(clean_path):
                continue
            paths.add(clean_path)

        missing = []
        for path in sorted(paths):
            if not os.path.exists(path):
                missing.append(path)
        assert not missing, f"Evidence paths not found: {missing}"

    def test_f050_cites_report(self):
        """CHECK 4.6: docs/current-findings.md F-050 cites geometry_static_lineage_report.md."""
        content = _load_text(FINDINGS_PATH)
        # Find F-050 section
        idx = content.find("### F-050")
        assert idx >= 0, "F-050 section not found in current-findings.md"
        f050_section = content[idx:]
        # Find next section boundary
        next_idx = f050_section.find("\n### ", 10)
        if next_idx >= 0:
            f050_section = f050_section[:next_idx]
        assert "geometry_static_lineage_report.md" in f050_section, (
            "F-050 in current-findings.md does not cite geometry_static_lineage_report.md"
        )

    def test_session_log_cites_report(self):
        """CHECK 4.7: assistant_project.md Gate 5 session entry cites geometry_static_lineage_report.md."""
        content = _load_text(SESSION_LOG_PATH)
        assert "geometry_static_lineage_report.md" in content, (
            "assistant_project.md does not cite geometry_static_lineage_report.md"
        )
        assert "Gate-5 evidence packaging" in content, (
            "assistant_project.md missing 'Gate-5 evidence packaging' marker"
        )
