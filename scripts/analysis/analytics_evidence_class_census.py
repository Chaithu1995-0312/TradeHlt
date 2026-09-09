#!/usr/bin/env python3
"""EC-001: mechanical evidence-class census for analytics lineage rows.

The census is observation-only. It reads the analytics lineage registry, local JSONL
corpora, and declared producer modules; it never changes either analytics registry.
Classes are mutually exclusive and ordered: CORPUS_VERIFIED, CODE_VERIFIED,
DECLARED_ONLY, UNKNOWN.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs/governance/ANALYTICS_LINEAGE_REGISTRY.md"
CLASSIFIER_VERSION = "EC-001.v1"
CLASSIFICATIONS = ("CORPUS_VERIFIED", "CODE_VERIFIED", "DECLARED_ONLY", "UNKNOWN")
ROW_CLASSIFICATIONS = {"EXACT_MATCH", "SAFE_ALIAS", "HOMONYM", "PROHIBITED_ALIAS", "NEW"}
EVENTS_FAMILY_EXCLUDE = {"integrity_events.jsonl", "secondlow_prospective_events.jsonl"}
CORPUS_EVIDENCE_FILES = {
    "crt_construction": "logs/dual_construction_v2_envelope_safe/XAUUSD_crt_construction.jsonl",
    "crt_telemetry": "results/_s0_postedit/_run/run_20260613_001812_BNBUSDT/BNBUSDT_crt_telemetry.jsonl",
    "events": "results/_p1_baseline/run_20260719_113436_XAUUSD/XAUUSD_events.jsonl",
    "opportunities": "logs/XAUUSD/xauusd_phase1_20260723/opportunities.jsonl",
    "clean_labels": "results/clean_labels/XAUUSD/20260723T083443Z/clean_labels.jsonl",
    "bar_structure": "logs/dual_construction_v2_envelope_safe/XAUUSD_bar_structure.jsonl",
}


@dataclass(frozen=True)
class RegistryRow:
    field_name: str
    owner: str
    family: str
    classification: str
    source_jsonl_field: str
    source_jsonl_family: str
    produced_by: str


def read_registry(path: Path = REGISTRY) -> list[RegistryRow]:
    """Parse the fixed-width lineage table, rejecting malformed data rows."""
    rows: list[RegistryRow] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in raw.strip().strip("|").split("|")]
        if len(cells) < 11 or cells[3] not in ROW_CLASSIFICATIONS:
            continue
        rows.append(
            RegistryRow(
                field_name=cells[0],
                owner=cells[1],
                family=cells[2],
                classification=cells[3],
                source_jsonl_field=cells[5],
                source_jsonl_family=cells[6],
                produced_by=cells[9],
            )
        )
    if len(rows) != len({(row.family, row.field_name) for row in rows}):
        raise ValueError("lineage registry has duplicate (family, field_name) keys")
    return rows


def _candidate_files(root: Path, pattern: str, family: str) -> list[Path]:
    if root.resolve() == ROOT.resolve():
        configured = root / CORPUS_EVIDENCE_FILES[family]
        return [configured] if configured.is_file() else []

    # Unit-test roots are intentionally tiny and use disposable fixtures rather than
    # repository evidence paths.
    candidates: list[Path] = []
    for base in (root / "logs", root / "results"):
        if base.exists():
            candidates.extend(base.rglob(pattern))
    if family == "events":
        candidates = [path for path in candidates if path.name not in EVENTS_FAMILY_EXCLUDE]
    return sorted({path.resolve() for path in candidates})


def corpus_evidence(rows: Iterable[RegistryRow], root: Path = ROOT) -> dict[tuple[str, str], str]:
    """Return first observed JSONL location for every registry field found on disk."""
    by_family: dict[str, list[RegistryRow]] = defaultdict(list)
    for row in rows:
        by_family[row.family].append(row)

    evidence: dict[tuple[str, str], str] = {}
    for family, family_rows in by_family.items():
        pattern = family_rows[0].source_jsonl_family
        wanted = {row.source_jsonl_field for row in family_rows if row.source_jsonl_field != "UNKNOWN"}
        for path in _candidate_files(root, pattern, family):
            if wanted.issubset({field for (_, field) in evidence if _ == family}):
                break
            try:
                with path.open(encoding="utf-8") as handle:
                    for line_number, raw in enumerate(handle, start=1):
                        try:
                            record = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        if not isinstance(record, dict):
                            continue
                        for field in wanted.intersection(record):
                            evidence.setdefault((family, field), f"{path.relative_to(root).as_posix()}:{line_number}")
                        if wanted.issubset({field for (_, field) in evidence if _ == family}):
                            break
            except OSError:
                continue
    return evidence


def code_evidence(row: RegistryRow, root: Path = ROOT) -> str | None:
    """Conservative static fallback: direct field token in the declared producer file."""
    if row.produced_by == "UNKNOWN" or not row.produced_by.startswith("src/"):
        return None
    producer = root / row.produced_by
    if not producer.is_file() or row.source_jsonl_field == "UNKNOWN":
        return None
    token = row.source_jsonl_field
    for line_number, line in enumerate(producer.read_text(encoding="utf-8").splitlines(), start=1):
        if token in line:
            return f"{row.produced_by}:{line_number}"
    return None


def classify(rows: Iterable[RegistryRow], root: Path = ROOT) -> list[dict[str, str | None]]:
    rows = list(rows)
    corpus = corpus_evidence(rows, root)
    results: list[dict[str, str | None]] = []
    for row in rows:
        key = (row.family, row.source_jsonl_field)
        if key in corpus:
            status, evidence = "CORPUS_VERIFIED", corpus[key]
        else:
            evidence = code_evidence(row, root)
            if evidence:
                status = "CODE_VERIFIED"
            elif row.source_jsonl_field != "UNKNOWN":
                status, evidence = "DECLARED_ONLY", None
            else:
                status, evidence = "UNKNOWN", None
        results.append({**asdict(row), "evidence_class": status, "evidence": evidence})
    return results


def _git_sha(root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def build_payload(root: Path = ROOT, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    run_id = f"ec001_evidence_class_census_{now.strftime('%Y%m%d_%H%M%S')}"
    rows = read_registry(root / REGISTRY.relative_to(ROOT))
    classified = classify(rows, root)
    counts = Counter(item["evidence_class"] for item in classified)
    registry_bytes = (root / REGISTRY.relative_to(ROOT)).read_bytes()
    return {
        "census_id": "EC-001",
        "classifier_version": CLASSIFIER_VERSION,
        "run_id": run_id,
        "generated_at_utc": now.isoformat(),
        "git_commit_sha": _git_sha(root),
        "registry_path": REGISTRY.relative_to(ROOT).as_posix(),
        "registry_sha256": hashlib.sha256(registry_bytes).hexdigest(),
        "classification_precedence": list(CLASSIFICATIONS),
        "corpus_evidence_files": CORPUS_EVIDENCE_FILES,
        "rules": {
            "CORPUS_VERIFIED": "Field observed in a JSON object from an admissible local JSONL family file.",
            "CODE_VERIFIED": "No corpus observation; direct source-field token in the declared producer module.",
            "DECLARED_ONLY": "No corpus or code proof; a physical source field is declared by the lineage registry.",
            "UNKNOWN": "The lineage row does not declare a physical source JSONL field.",
        },
        "counts": {classification: counts[classification] for classification in CLASSIFICATIONS},
        "rows": classified,
    }


def write_payload(payload: dict, output_dir: Path) -> tuple[Path, Path]:
    date = payload["generated_at_utc"][:10]
    stem = f"analytics_evidence_class_census-{date}"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    if json_path.exists() or md_path.exists():
        raise FileExistsError(f"dated EC-001 artifact already exists: {stem}")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# EC-001 Evidence Class Census",
        "",
        f"- Run: `{payload['run_id']}`",
        f"- Commit: `{payload['git_commit_sha']}`",
        f"- Classifier: `{payload['classifier_version']}`",
        f"- Registry: `{payload['registry_path']}` (`{payload['registry_sha256']}`)",
        "",
        "| Evidence class | Count |",
        "|---|---:|",
        *[f"| {name} | {payload['counts'][name]} |" for name in CLASSIFICATIONS],
        "",
        "This is an observation artifact. It does not promote an analytics-registry column or attribution eligibility.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs/governance")
    parser.add_argument("--dry-run", action="store_true", help="Print counts without writing an artifact.")
    args = parser.parse_args()
    payload = build_payload()
    print(json.dumps(payload["counts"], sort_keys=True))
    if args.dry_run:
        return 0
    json_path, md_path = write_payload(payload, args.output_dir)
    print(f"wrote {json_path.relative_to(ROOT)}")
    print(f"wrote {md_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
