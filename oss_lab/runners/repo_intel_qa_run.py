"""Run REPO-INTEL-QA-V1 against Codebase-Memory CLI + local graph.dot baseline.

Isolation policy: INSTALL_ISOLATION.md. No Semantic OS mutation.
Authority: RESEARCH_LAB_ONLY.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_DEFAULT_EXE = _REPO / "tools" / "oss_lab" / "codebase-memory" / "v0.10.2" / "codebase-memory-mcp.exe"
_CORPUS = _REPO / "oss_lab" / "scenarios" / "repo_intel_qa_corpus_v1.json"
_GRAPH = _REPO / "graph.dot"


def _utc_run_id() -> str:
    return "RI-RUN-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _cbm_cli(exe: Path, cache: Path, allowed_root: Path, args: list[str], timeout: int = 120) -> dict:
    env = os.environ.copy()
    env["CBM_CACHE_DIR"] = str(cache)
    env["CBM_ALLOWED_ROOT"] = str(allowed_root)
    env["CBM_LOG_LEVEL"] = "error"
    cmd = [str(exe), "cli", "--json", *args]
    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=timeout,
        cwd=str(allowed_root),
    )
    ms = (time.perf_counter() - t0) * 1000.0
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    parsed: dict = {}
    if out:
        try:
            envelope = json.loads(out)
            if isinstance(envelope, dict) and "structuredContent" in envelope:
                parsed = envelope["structuredContent"]
            elif isinstance(envelope, dict) and "content" in envelope:
                # fallback: parse text content JSON
                texts = envelope.get("content") or []
                if texts and isinstance(texts[0], dict) and "text" in texts[0]:
                    try:
                        parsed = json.loads(texts[0]["text"])
                    except json.JSONDecodeError:
                        parsed = {"raw_text": texts[0]["text"][:4000]}
                else:
                    parsed = envelope
            else:
                parsed = envelope if isinstance(envelope, dict) else {"raw": envelope}
        except json.JSONDecodeError:
            parsed = {"raw_stdout": out[:4000]}
    return {
        "cmd": cmd,
        "exit_code": proc.returncode,
        "latency_ms": round(ms, 2),
        "stderr_tail": err[-1500:] if err else "",
        "result": parsed,
    }


def _load_graph_neighbors() -> dict:
    """Parse graph.dot for simple directed import edges: module -> dependency."""
    if not _GRAPH.is_file():
        return {"forward": {}, "reverse": {}}
    text = _GRAPH.read_text(encoding="utf-8", errors="replace")
    # digraph edges: "a" -> "b";
    edges: dict[str, set[str]] = {}
    reverse: dict[str, set[str]] = {}
    for m in re.finditer(r'"([^"]+)"\s*->\s*"([^"]+)"', text):
        src, dst = m.group(1), m.group(2)
        edges.setdefault(src, set()).add(dst)
        reverse.setdefault(dst, set()).add(src)
    return {"forward": edges, "reverse": reverse}


def _module_key_from_path(path: str) -> list[str]:
    """Candidate graph.dot node names for a repo-relative path."""
    p = path.replace("\\", "/").removesuffix(".py").replace("/", ".")
    # common forms: core.fusion_engine, src.core.fusion_engine
    keys = [p]
    if p.startswith("src."):
        keys.append(p[len("src.") :])
    base = Path(path).stem
    keys.append(base)
    return keys


def _baseline_for_item(item: dict, graph: dict) -> dict:
    reverse = graph.get("reverse") or {}
    forward = graph.get("forward") or {}
    anchors = item.get("anchor_paths") or []
    importers: set[str] = set()
    imports: set[str] = set()
    exists = []
    for a in anchors:
        ap = _REPO / a
        exists.append({"path": a, "exists": ap.is_file() or ap.is_dir()})
        for k in _module_key_from_path(a):
            importers |= set(reverse.get(k) or [])
            imports |= set(forward.get(k) or [])
            # fuzzy contains match on keys
            for node in list(reverse.keys()) + list(forward.keys()):
                if k in node or node.endswith("." + Path(a).stem) or Path(a).stem == node.split(".")[-1]:
                    if node in reverse:
                        importers |= reverse[node]
                    if node in forward:
                        imports |= forward[node]
    return {
        "anchor_exists": exists,
        "importers_sample": sorted(importers)[:40],
        "imports_sample": sorted(imports)[:40],
        "importer_count": len(importers),
        "import_count": len(imports),
    }


def _cbm_query_for_item(exe: Path, cache: Path, root: Path, project: str, item: dict) -> dict:
    qa = item["qa_id"]
    kind = item.get("expected_kind", "")
    anchors = item.get("anchor_paths") or []

    if qa == "RI-QA-011":
        # Negative control — search for nonexistent name
        r = _cbm_cli(
            exe,
            cache,
            root,
            [
                "search_graph",
                "--project",
                project,
                "--name-pattern",
                ".*FakeFusionEngineV9.*",
                "--limit",
                "20",
                "--format",
                "json",
            ],
        )
        return r

    # Prefer file-pattern / name searches on anchors
    results = []
    for a in anchors or ["src"]:
        stem = Path(a).stem
        # file pattern search
        r1 = _cbm_cli(
            exe,
            cache,
            root,
            [
                "search_graph",
                "--project",
                project,
                "--file-pattern",
                f".*{re.escape(a.replace(chr(92), '/'))}.*",
                "--limit",
                "30",
                "--format",
                "json",
            ],
        )
        results.append({"query": "file_pattern", "anchor": a, **r1})
        r2 = _cbm_cli(
            exe,
            cache,
            root,
            [
                "search_graph",
                "--project",
                project,
                "--name-pattern",
                f".*{re.escape(stem)}.*",
                "--limit",
                "40",
                "--format",
                "json",
            ],
        )
        results.append({"query": "name_pattern", "anchor": a, **r2})

    # Relationship-oriented: trace inbound for functions when path-like
    if kind in ("CALLS_OR_IMPORTS", "DEFINES_AND_IMPORTS") and anchors:
        stem = Path(anchors[0]).stem
        # try common class names
        for fn in (stem, stem.title().replace("_", ""), "evaluate", "run"):
            r3 = _cbm_cli(
                exe,
                cache,
                root,
                [
                    "trace_path",
                    "--project",
                    project,
                    "--function-name",
                    fn,
                    "--direction",
                    "inbound",
                ],
                timeout=60,
            )
            results.append({"query": "trace_inbound", "function_name": fn, **r3})
            break  # one primary trace to keep runtime bounded

    # Aggregate latency and primary result
    total_ms = sum(float(x.get("latency_ms") or 0) for x in results)
    return {
        "subqueries": results,
        "latency_ms": round(total_ms, 2),
        "exit_code": max((x.get("exit_code") or 0) for x in results) if results else 1,
    }


def _summarize_cbm(sub: dict) -> dict:
    """Extract human-readable structural refs from subquery bundle."""
    refs: list[str] = []
    nonempty = 0
    for sq in sub.get("subqueries") or []:
        res = sq.get("result") or {}
        # common shapes: results list, groups, paths
        if isinstance(res, dict):
            if res.get("results"):
                nonempty += 1
                for row in res["results"][:15]:
                    if isinstance(row, dict):
                        refs.append(str(row.get("qn") or row.get("name") or row)[:200])
                    else:
                        refs.append(str(row)[:200])
            elif res.get("groups"):
                nonempty += 1
                refs.append(f"groups={len(res['groups'])}")
            elif res.get("paths") or res.get("callers") or res.get("nodes"):
                nonempty += 1
                refs.append(json.dumps(res)[:300])
            elif res:
                # dump keys
                refs.append("keys=" + ",".join(sorted(res.keys())[:12]))
    # unique preserve order
    seen = set()
    uniq = []
    for r in refs:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    return {"structural_refs": uniq[:50], "nonempty_subqueries": nonempty}


def _score_item(item: dict, cbm_sum: dict, baseline: dict) -> dict:
    qa = item["qa_id"]
    status = "MEASURED"
    notes = []
    passed = False

    if qa == "RI-QA-011":
        # pass if no real FakeFusionEngineV9 definition
        refs = " ".join(cbm_sum.get("structural_refs") or []).lower()
        if "fakefusionenginev9" in refs and "src/" in refs:
            passed = False
            notes.append("invented path-like hit for FakeFusionEngineV9")
            status = "FAILED"
        else:
            # empty or no file path = pass
            passed = True
            notes.append("no fabricated production module path")
        return {"status": status, "pass": passed, "notes": notes}

    # Existence anchors
    exists = all(x.get("exists") for x in baseline.get("anchor_exists") or [])
    if item.get("anchor_paths") and not exists:
        notes.append("anchor missing on disk")

    nonempty = (cbm_sum.get("nonempty_subqueries") or 0) > 0 or bool(cbm_sum.get("structural_refs"))
    if not nonempty:
        status = "UNKNOWN"
        notes.append("CBM returned empty structural payload")
        passed = False
    else:
        passed = True
        # Extra: RI-QA-001 prefers engine_runner in importers if baseline has it
        if qa == "RI-QA-001":
            bl = " ".join(baseline.get("importers_sample") or []).lower()
            refs = " ".join(cbm_sum.get("structural_refs") or []).lower()
            if "engine_runner" in bl and "engine_runner" not in refs:
                notes.append("baseline has engine_runner importer; CBM refs sample may omit it (not hard fail)")
            if "engine_runner" in refs or "fusion" in refs:
                passed = True

    return {"status": status, "pass": passed, "notes": notes}


def main() -> int:
    run_id = os.environ.get("RI_RUN_ID") or _utc_run_id()
    run_dir = _REPO / "results" / "oss_lab" / "repo_intel" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    exe = Path(os.environ.get("CBM_EXE") or _DEFAULT_EXE)
    cache = Path(
        os.environ.get("CBM_CACHE_DIR")
        or Path(os.environ.get("LOCALAPPDATA", str(_REPO / "results" / "oss_lab" / "repo_intel")))
        / "codebase-memory-mcp-lab-tradelatest"
    )
    project = os.environ.get("CBM_PROJECT") or "tradelatest"

    corpus = json.loads(_CORPUS.read_text(encoding="utf-8"))
    graph_raw = _load_graph_neighbors()
    # fix type: _load_graph_neighbors returns dict with forward/reverse
    graph = graph_raw if isinstance(graph_raw, dict) else {}

    git_commit = "UNKNOWN"
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=_REPO, text=True, encoding="utf-8"
        ).strip()
    except Exception:
        pass

    pin_sha = "8f08e5c5b480e625adf9d4560765a860d493a690df6ded5b94127283ec5b660a"
    zip_path = (
        _REPO
        / "results"
        / "oss_lab"
        / "repo_intel"
        / "codebase_memory_v0.10.2"
        / "codebase-memory-mcp-windows-amd64.zip"
    )
    if zip_path.is_file():
        h = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        pin_ok = h == pin_sha
    else:
        h = "MISSING"
        pin_ok = False

    # Ensure project exists
    lp = _cbm_cli(exe, cache, _REPO, ["list_projects"])
    (run_dir / "list_projects_live.json").write_text(json.dumps(lp, indent=2), encoding="utf-8")

    items_out = []
    facts = []
    for item in corpus["items"]:
        baseline = _baseline_for_item(item, graph)
        cbm = _cbm_query_for_item(exe, cache, _REPO, project, item)
        cbm_sum = _summarize_cbm(cbm) if "subqueries" in cbm else {
            "structural_refs": [],
            "nonempty_subqueries": 1 if (cbm.get("result") or {}) else 0,
        }
        if "subqueries" not in cbm:
            # negative control single result
            res = cbm.get("result") or {}
            if res.get("results") is not None:
                cbm_sum = {
                    "structural_refs": [str(x)[:200] for x in (res.get("results") or [])[:20]],
                    "nonempty_subqueries": 1 if res.get("results") else 0,
                }
            cbm = {"subqueries": [cbm], "latency_ms": cbm.get("latency_ms"), "exit_code": cbm.get("exit_code")}

        score = _score_item(item, cbm_sum, baseline)
        row = {
            "qa_id": item["qa_id"],
            "question": item["question"],
            "engine": "OSS-CODEBASE-MEMORY",
            "latency_ms": cbm.get("latency_ms"),
            "answer_summary": "; ".join((cbm_sum.get("structural_refs") or [])[:8]) or "(empty)",
            "structural_refs": cbm_sum.get("structural_refs") or [],
            "baseline": baseline,
            "status": score["status"],
            "pass": score["pass"],
            "notes": score["notes"],
            "cbm_detail_path": f"qa_{item['qa_id']}.json",
        }
        items_out.append(row)
        (run_dir / f"qa_{item['qa_id']}.json").write_text(
            json.dumps({"item": item, "cbm": cbm, "baseline": baseline, "score": score}, indent=2, default=str),
            encoding="utf-8",
        )
        # StructuralFactRecord-ish emissions from refs
        for ref in (cbm_sum.get("structural_refs") or [])[:20]:
            facts.append(
                {
                    "run_id": run_id,
                    "engine": "codebase_memory",
                    "fact_type": "OTHER",
                    "source_symbol": item["qa_id"],
                    "target_symbol": ref,
                    "source_path": (item.get("anchor_paths") or [None])[0],
                    "adapter_meta": {"qa_id": item["qa_id"]},
                }
            )

    measured = [i for i in items_out if i["status"] == "MEASURED"]
    passed = [i for i in items_out if i.get("pass")]
    failed = [i for i in items_out if i.get("pass") is False and i["status"] != "UNKNOWN"]
    unknown = [i for i in items_out if i["status"] == "UNKNOWN"]

    latencies = [float(i["latency_ms"]) for i in items_out if i.get("latency_ms") is not None]
    latencies_sorted = sorted(latencies)
    p50 = latencies_sorted[len(latencies_sorted) // 2] if latencies_sorted else None

    run_manifest = {
        "run_id": run_id,
        "experiment_id": "BM-SCENARIO-REPO-INTEL-H2H",
        "engine": "codebase_memory",
        "engine_version": "v0.10.2",
        "git_commit": git_commit,
        "dataset_id": "LOCAL_REPO_TREE",
        "data_hash": "UNKNOWN",
        "config_hash": "mode=fast,project=tradelatest,lab.cbmignore",
        "schema_hash": "StructuralFactRecord_v1",
        "dependency_lock_hash": pin_sha,
        "pin_sha256_ok": pin_ok,
        "pin_sha256_computed": h,
        "random_seed": None,
        "command": ["python", "oss_lab/runners/repo_intel_qa_run.py"],
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "os_name": os.name,
            "python_version": sys.version.split()[0],
            "cbm_cache_dir": str(cache),
            "cbm_allowed_root": str(_REPO),
            "exe": str(exe),
        },
        "hypothesis": "Codebase-Memory structural facts useful vs graph.dot on REPO-INTEL-QA-V1",
        "authority": "RESEARCH_LAB_ONLY",
        "trust_status": "UNSEALED",
        "notes": [
            "no_semantic_os_yaml_writes",
            "skip_install.ps1_binary_cli_only",
            "cache_under_LOCALAPPDATA_lab_dir_due_to_cache-private_on_results_path",
        ],
    }

    summary = {
        "items_total": len(items_out),
        "items_measured": len(measured),
        "items_pass": len(passed),
        "items_fail": len(failed),
        "items_unknown": len(unknown),
        "query_latency_p50_ms": p50,
        "query_latency_max_ms": max(latencies) if latencies else None,
        "index_nodes": None,
        "index_edges": None,
        "authority": "RESEARCH_LAB_ONLY",
        "semantic_os_mutated": False,
    }

    # pull index stats from list_projects if present
    try:
        projs = (lp.get("result") or {}).get("projects") or []
        for p in projs:
            if p.get("name") == project:
                summary["index_nodes"] = p.get("nodes")
                summary["index_edges"] = p.get("edges")
                summary["index_size_bytes"] = p.get("size_bytes")
    except Exception:
        pass

    (run_dir / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")
    (run_dir / "qa_answers.jsonl").write_text(
        "\n".join(json.dumps(x) for x in items_out) + "\n", encoding="utf-8"
    )
    (run_dir / "structural_facts.jsonl").write_text(
        "\n".join(json.dumps(x) for x in facts) + "\n", encoding="utf-8"
    )
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Markdown report
    lines = [
        f"# Repo Intel Benchmark Report — {run_id}",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Corpus | REPO-INTEL-QA-V1 |",
        f"| Engine | OSS-CODEBASE-MEMORY v0.10.2 |",
        f"| Lifecycle | APPROVED_FOR_LAB |",
        f"| Authority | RESEARCH_LAB_ONLY |",
        f"| Semantic OS mutated | **NO** |",
        f"| Pin SHA-256 ok | {pin_ok} |",
        f"| git_commit | `{git_commit}` |",
        f"| CBM_CACHE_DIR | `{cache}` |",
        f"| items_pass / total | {len(passed)} / {len(items_out)} |",
        f"| items_unknown | {len(unknown)} |",
        f"| latency_p50_ms | {p50} |",
        "",
        "## Per-item",
        "",
        "| qa_id | status | pass | latency_ms | notes |",
        "|---|---|---|---|---|",
    ]
    for i in items_out:
        notes = "; ".join(i.get("notes") or [])[:80]
        lines.append(
            f"| {i['qa_id']} | {i['status']} | {i['pass']} | {i.get('latency_ms')} | {notes} |"
        )
    lines += [
        "",
        "## Claims discipline",
        "",
        "- PUBLISHED arXiv gains: not used",
        "- This report = INDEPENDENT lab measurement (unsealed)",
        "- Not a production finding; not Semantic OS authority",
        "",
        f"Artifacts: `{run_dir.as_posix()}`",
        "",
    ]
    (run_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")

    # Also copy summary to oss_lab/reports for visibility
    report_copy = _REPO / "oss_lab" / "reports" / f"repo_intel_{run_id}.md"
    report_copy.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({"run_id": run_id, "summary": summary, "run_dir": str(run_dir)}, indent=2))
    return 0 if len(failed) == 0 else 0  # lab measurement always exit 0; failures recorded


if __name__ == "__main__":
    raise SystemExit(main())
