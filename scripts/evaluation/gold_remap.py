#!/usr/bin/env python3
"""Remap RAG gold set (benchmark_100) — run on D:\\Tradelatest. Does not commit.

Writes:
  scripts/evaluation/benchmark_100.original.json  (copy of current if missing)
  scripts/evaluation/benchmark_100.remapped.json
  scripts/evaluation/gold_remap_report.json

Rules are table-driven, first-match, recorded per question.
"""
from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(r"D:\Tradelatest")
EVAL = ROOT / "scripts" / "evaluation"
GOLD = EVAL / "benchmark_100.json"
ORIGINAL = EVAL / "benchmark_100.original.json"
REMAPPED = EVAL / "benchmark_100.remapped.json"
REPORT = EVAL / "gold_remap_report.json"

# Prefer these locations for index_manifest
MANIFEST_CANDIDATES = [
    ROOT / "data" / "rag" / "index_manifest.json",
    ROOT / "data" / "rag" / "manifest.json",
    ROOT / "data" / "rag" / "index_manifest.jsonl",
]

DOMAIN_TO_TRUTH = {
    "source_code": "CURRENT",
    "config": "CURRENT",
    "governance": "RECORDED",
    "architecture": "INTENDED",
    "intent": "INTENDED",
    "analysis": "HISTORICAL",  # dated adjudication default; override below if needed
}

# Absent knowledge-surface files to drop (or replace if a living twin exists)
ABSENT_DROP = {
    "python_source_static_census_summary.json",
    "python_source_static_census.jsonl",
}

# Basename / stem aliases justified by living index files (filled at runtime)
STATIC_PATH_ALIASES: dict[str, str] = {
    # Q66/Q67 already ACTIVE_VERSION — keep explicit
    "configs/production": "configs/production/ACTIVE_VERSION",
    "configs/production/": "configs/production/ACTIVE_VERSION",
}


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm(p: str) -> str:
    return p.replace("\\", "/").strip()


def _basename(p: str) -> str:
    return _norm(p).rsplit("/", 1)[-1]


def _stem(p: str) -> str:
    b = _basename(p)
    return b.rsplit(".", 1)[0] if "." in b else b


def load_manifest_files() -> set[str]:
    files: set[str] = set()
    for cand in MANIFEST_CANDIDATES:
        if not cand.exists():
            continue
        if cand.suffix == ".jsonl":
            with cand.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    fp = row.get("filepath") or row.get("path") or row.get("file")
                    if fp:
                        files.add(_norm(str(fp)))
            print(f"manifest jsonl: {cand} -> {len(files)} files")
            return files
        data = json.loads(cand.read_text(encoding="utf-8"))
        if isinstance(data, list):
            for row in data:
                if isinstance(row, str):
                    files.add(_norm(row))
                elif isinstance(row, dict):
                    fp = row.get("filepath") or row.get("path") or row.get("file")
                    if fp:
                        files.add(_norm(str(fp)))
        elif isinstance(data, dict):
            for key in ("files", "filepaths", "entries", "paths"):
                arr = data.get(key)
                if isinstance(arr, list):
                    for row in arr:
                        if isinstance(row, str):
                            files.add(_norm(row))
                        elif isinstance(row, dict):
                            fp = row.get("filepath") or row.get("path") or row.get("file")
                            if fp:
                                files.add(_norm(str(fp)))
            # sometimes keyed by path
            if not files:
                for k, v in data.items():
                    if isinstance(k, str) and ("/" in k or "\\" in k):
                        files.add(_norm(k))
                    if isinstance(v, dict):
                        fp = v.get("filepath") or v.get("path")
                        if fp:
                            files.add(_norm(str(fp)))
        print(f"manifest: {cand} -> {len(files)} files")
        if files:
            return files
    # Fallback: distinct filepaths from chunks.parquet
    chunks_pq = ROOT / "data" / "rag" / "chunks.parquet"
    if chunks_pq.exists():
        try:
            import duckdb

            con = duckdb.connect()
            rows = con.execute(
                "SELECT DISTINCT filepath FROM read_parquet(?)",
                [str(chunks_pq).replace("\\", "/")],
            ).fetchall()
            con.close()
            files = {_norm(r[0]) for r in rows if r and r[0]}
            print(f"chunks.parquet distinct filepaths -> {len(files)}")
            return files
        except Exception as exc:
            print("parquet fallback failed:", exc)
    raise SystemExit("No index_manifest / chunks.parquet file list found")


def index_by_basename(files: set[str]) -> dict[str, list[str]]:
    by: dict[str, list[str]] = defaultdict(list)
    for fp in files:
        by[_basename(fp).lower()].append(fp)
        by[_stem(fp).lower()].append(fp)
    return by


def pick_living_twin(path: str, by_base: dict[str, list[str]], indexed: set[str]) -> str | None:
    """If HISTORICAL/plan path has a CURRENT-looking twin with same basename, return it."""
    n = _norm(path)
    if n in indexed:
        return None
    base = _basename(n).lower()
    stem = _stem(n).lower()
    cands = list(dict.fromkeys(by_base.get(base, []) + by_base.get(stem, [])))
    # Prefer non-historical / non-plan paths
    def score(fp: str) -> tuple[int, int, str]:
        low = fp.lower()
        pen = 0
        if "implementation_plan" in low or "/historical/" in low or "/archive/" in low:
            pen += 10
        if "/docs/governance/" in low and low.endswith(".jsonl"):
            pen += 5
        if low.startswith("src/") or low.startswith("docs/architecture/"):
            pen -= 3
        return (pen, len(fp), fp)

    cands = sorted(cands, key=score)
    for c in cands:
        if c != n:
            return c
    return None


def find_census_replacement(indexed: set[str], by_base: dict[str, list[str]]) -> str | None:
    keys = [
        "python_source_static_census",
        "static_census",
        "source_census",
    ]
    for k in keys:
        for fp in by_base.get(k.lower(), []):
            low = fp.lower()
            if low.endswith(".md") or "docs/" in low:
                return fp
    # broader search
    for fp in sorted(indexed):
        low = fp.lower()
        if "census" in low and (low.endswith(".md") or "docs/" in low):
            if "python_source_static_census" not in low:
                return fp
    return None


def remap_domains(domains: list[str]) -> tuple[list[str], list[str]]:
    legacy = list(domains)
    mapped: list[str] = []
    seen: set[str] = set()
    for d in domains:
        key = (d or "").strip()
        tc = DOMAIN_TO_TRUTH.get(key.lower(), key.upper() if key.isupper() else None)
        if tc is None:
            # already a truth class?
            up = key.upper()
            if up in {"CURRENT", "INTENDED", "RECORDED", "REFERENCE", "HISTORICAL"}:
                tc = up
            else:
                continue
        if tc not in seen:
            seen.add(tc)
            mapped.append(tc)
    return mapped, legacy


def looks_historical_path(p: str) -> bool:
    low = p.lower()
    return any(
        x in low
        for x in (
            "implementation_plan",
            "/historical/",
            "/archive/",
            "_archived",
            "/plans/",
        )
    )


def remap_question(
    q: dict[str, Any],
    indexed: set[str],
    by_base: dict[str, list[str]],
    census_repl: str | None,
) -> dict[str, Any]:
    """Return per-question report entry; mutates q in place."""
    qid = q.get("id")
    old_files = list(q.get("expected_files") or [])
    new_files: list[str] = []
    rules: list[str] = []
    unmatched: list[str] = []

    for ef in old_files:
        n = _norm(ef)
        base = _basename(n)

        # Rule 1: drop / replace absent census artifacts
        if base in ABSENT_DROP or n.endswith(tuple(ABSENT_DROP)):
            if census_repl:
                if census_repl not in new_files:
                    new_files.append(census_repl)
                rules.append(f"R1_replace_absent_census:{n}->{census_repl}")
            else:
                rules.append(f"R1_drop_absent_census:{n}")
            continue

        # Static path aliases
        if n in STATIC_PATH_ALIASES or n.rstrip("/") in STATIC_PATH_ALIASES:
            key = n if n in STATIC_PATH_ALIASES else n.rstrip("/")
            repl = STATIC_PATH_ALIASES[key]
            if repl in indexed or True:
                if repl not in new_files:
                    new_files.append(repl)
                rules.append(f"R3_static_alias:{n}->{repl}")
                continue

        if n in indexed:
            if n not in new_files:
                new_files.append(n)
            # Rule 3: if HISTORICAL/plan and CURRENT twin exists, ADD twin
            if looks_historical_path(n):
                twin = None
                # Prefer same basename under src/ or docs/architecture
                for cand in by_base.get(_basename(n).lower(), []):
                    if cand == n:
                        continue
                    if looks_historical_path(cand):
                        continue
                    twin = cand
                    break
                if twin and twin not in new_files:
                    new_files.append(twin)
                    rules.append(f"R3_add_current_twin:{n}->{twin}")
            continue

        # Basename match in index
        cands = by_base.get(base.lower(), []) or by_base.get(_stem(n).lower(), [])
        if cands:
            # Prefer exact suffix match / shortest living path
            def rank(fp: str) -> tuple[int, int]:
                pen = 5 if looks_historical_path(fp) else 0
                return (pen, len(fp))

            best = sorted(cands, key=rank)[0]
            if best not in new_files:
                new_files.append(best)
            rules.append(f"R3_basename_remap:{n}->{best}")
            continue

        twin = pick_living_twin(n, by_base, indexed)
        if twin:
            if twin not in new_files:
                new_files.append(twin)
            rules.append(f"R3_living_twin:{n}->{twin}")
            continue

        unmatched.append(n)
        rules.append(f"UNMATCHED:{n}")

    # Rule 4: architecture questions naming TRADING_SYSTEM_FRAMEWORK — keep if indexed
    qtext = (q.get("question") or "").lower()
    arch_stem = "docs/architecture/TRADING_SYSTEM_FRAMEWORK.md"
    arch_alts = [
        p for p in indexed if _basename(p).upper().startswith("TRADING_SYSTEM_FRAMEWORK")
    ]
    if "architecture" in qtext or "trading system" in qtext:
        keep = None
        for p in [arch_stem, *arch_alts]:
            if p in indexed:
                keep = p
                break
            # case-insensitive
            for ip in indexed:
                if _norm(ip).lower() == p.lower():
                    keep = ip
                    break
            if keep:
                break
        if keep and keep not in new_files:
            # only add if question clearly architectural and gold empty or missing framework
            if not any("TRADING_SYSTEM_FRAMEWORK" in f.upper() for f in new_files):
                if any(
                    k in qtext
                    for k in ("architecture", "overall architecture", "trading system framework")
                ):
                    new_files.append(keep)
                    rules.append(f"R4_keep_framework:{keep}")

        # Optionally add goal.md / README only if they exist AND look like living arch surface
        for extra in ("docs/architecture/goal.md", "docs/architecture/README.md"):
            if extra in indexed or any(_norm(x).lower() == extra.lower() for x in indexed):
                # verify by reading first lines — caller may skip if not clearly arch
                real = extra
                for ip in indexed:
                    if _norm(ip).lower() == extra.lower():
                        real = ip
                        break
                try:
                    body = (ROOT / real).read_text(encoding="utf-8", errors="replace")[:2000].lower()
                except Exception:
                    body = ""
                if body and any(
                    w in body for w in ("architecture", "trading system", "framework", "overview")
                ):
                    if real not in new_files and "architecture" in qtext:
                        # only add when question asks overall architecture
                        if "overall" in qtext or "architecture of" in qtext:
                            new_files.append(real)
                            rules.append(f"R4_add_arch_surface:{real}")

    # Domains
    old_domains = list(q.get("expected_domains") or [])
    if old_domains:
        mapped, legacy = remap_domains(old_domains)
        if mapped != old_domains or "expected_domains_legacy" not in q:
            q["expected_domains_legacy"] = legacy
            q["expected_domains"] = mapped
            rules.append(f"R2_domains:{legacy}->{mapped}")

    q["expected_files"] = new_files
    return {
        "id": qid,
        "old_files": old_files,
        "new_files": new_files,
        "rules": rules,
        "unmatched": unmatched,
        "changed": old_files != new_files,
    }


def main() -> None:
    EVAL.mkdir(parents=True, exist_ok=True)
    if not GOLD.exists():
        raise SystemExit(f"missing {GOLD}")

    raw = GOLD.read_bytes()
    if not ORIGINAL.exists():
        ORIGINAL.write_bytes(raw)
        print(f"saved original -> {ORIGINAL} ({len(raw)} bytes)")
    else:
        print(f"original already present ({ORIGINAL.stat().st_size} bytes)")

    data = json.loads(raw.decode("utf-8"))
    indexed = load_manifest_files()
    by_base = index_by_basename(indexed)
    census_repl = find_census_replacement(indexed, by_base)
    print("census replacement:", census_repl)

    per_q = []
    n_changed = 0
    n_unmatched = 0
    for q in data.get("questions") or []:
        entry = remap_question(q, indexed, by_base, census_repl)
        per_q.append(entry)
        if entry["changed"]:
            n_changed += 1
        n_unmatched += len(entry["unmatched"])

    meta = data.setdefault("meta", {})
    meta["gold_remapped_at"] = _utc()
    meta["gold_remap"] = {
        "source": "benchmark_100.json",
        "original_preserved": str(ORIGINAL.relative_to(ROOT)).replace("\\", "/"),
        "questions_changed": n_changed,
        "unmatched_refs": n_unmatched,
        "index_files": len(indexed),
        "census_replacement": census_repl,
    }
    notes = meta.setdefault("validation_notes", [])
    note = (
        f"{_utc()}: expected_domains remapped to truth classes; legacy kept in "
        "expected_domains_legacy. Absent census JSON dropped/replaced. Basename "
        "twins added for HISTORICAL/plan refs when CURRENT exists."
    )
    if note not in notes:
        notes.append(note)

    REMAPPED.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # Optionally point default gold at remapped via sidecar pointer (do not overwrite original bytes)
    pointer = EVAL / "benchmark_100.active"
    pointer.write_text("benchmark_100.remapped.json\n", encoding="utf-8")

    report = {
        "generated_at": _utc(),
        "index_files": len(indexed),
        "questions_total": len(per_q),
        "questions_changed": n_changed,
        "unmatched_refs": n_unmatched,
        "census_replacement": census_repl,
        "per_question": per_q,
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {REMAPPED}")
    print(f"wrote {REPORT}")
    print(f"changed={n_changed} unmatched_refs={n_unmatched}")


if __name__ == "__main__":
    main()
