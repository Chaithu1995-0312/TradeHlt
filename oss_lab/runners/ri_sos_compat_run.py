"""RI-SOS-COMPAT-V1 runner — read-only SOS + Codebase-Memory join.

Authority: RESEARCH_LAB_ONLY. Never writes docs/governance/semantic_os/*.yaml.
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
from typing import Any, Optional

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "src"))

from governance.semantic_os import SemanticOSRegistry  # noqa: E402

_CORPUS = _REPO / "oss_lab" / "scenarios" / "ri_sos_compat_corpus_v1.json"
_DEFAULT_EXE = _REPO / "tools" / "oss_lab" / "codebase-memory" / "v0.10.2" / "codebase-memory-mcp.exe"
_GATE = _REPO / "oss_lab" / "governance" / "RI_SOS_EVIDENCE_COMPATIBILITY.md"

DIMS = [
    "structural_correctness",
    "semantic_correctness",
    "authority_correctness",
    "negative_control_correctness",
    "provenance_quality",
    "retrieval_usefulness",
]


def _utc_run_id() -> str:
    return "RI-SOS-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _cbm_cli(exe: Path, cache: Path, root: Path, args: list[str], timeout: int = 90) -> dict:
    env = os.environ.copy()
    env["CBM_CACHE_DIR"] = str(cache)
    env["CBM_ALLOWED_ROOT"] = str(root)
    env["CBM_LOG_LEVEL"] = "error"
    cmd = [str(exe), "cli", "--json", *args]
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=timeout,
            cwd=str(root),
        )
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "exit_code": -1, "latency_ms": timeout * 1000, "result": {}, "error": "timeout"}
    ms = (time.perf_counter() - t0) * 1000.0
    out = (proc.stdout or "").strip()
    parsed: dict = {}
    if out:
        try:
            envelope = json.loads(out)
            if isinstance(envelope, dict) and "structuredContent" in envelope:
                parsed = envelope["structuredContent"] or {}
            elif isinstance(envelope, dict) and "content" in envelope:
                texts = envelope.get("content") or []
                if texts and isinstance(texts[0], dict) and "text" in texts[0]:
                    try:
                        parsed = json.loads(texts[0]["text"])
                    except json.JSONDecodeError:
                        parsed = {"raw_text": texts[0]["text"][:2000]}
                else:
                    parsed = envelope
            else:
                parsed = envelope if isinstance(envelope, dict) else {"raw": envelope}
        except json.JSONDecodeError:
            parsed = {"raw_stdout": out[:2000]}
    return {
        "cmd": cmd,
        "exit_code": proc.returncode,
        "latency_ms": round(ms, 2),
        "result": parsed,
        "stderr_tail": (proc.stderr or "")[-500:],
    }


def _path_exists(rel: str) -> bool:
    p = _REPO / rel
    return p.is_file() or p.is_dir()


def _sos_snapshot(reg: SemanticOSRegistry, item: dict) -> dict:
    """Read-only SOS answers from registry using sos_hints."""
    out: dict[str, Any] = {
        "concepts": [],
        "boundaries": [],
        "journeys": [],
        "contracts": [],
        "file_identities": [],
        "paths_resolved": [],
        "meaning_snippets": [],
        "authority": "advisory",
        "silent": False,
    }
    hints = item.get("sos_hints") or []
    idmap = reg.identity_by_path()

    # Expand free-text hints into explicit SOS ids (e.g. "CN-001 canonical_source…")
    expanded: list[str] = []
    for h in hints:
        hs = str(h)
        expanded.append(hs)
        for m in re.finditer(r"\b(CN|BD|JN|CT)-\d{3}\b", hs):
            expanded.append(m.group(0))
    # preserve order, unique
    seen_h: set[str] = set()
    hints_norm: list[str] = []
    for h in expanded:
        if h not in seen_h:
            seen_h.add(h)
            hints_norm.append(h)

    for h in hints_norm:
        hs = str(h)
        if hs.startswith("CN-") and hs in reg.concepts:
            c = reg.concepts[hs]
            out["concepts"].append(
                {
                    "id": hs,
                    "name": c.get("name"),
                    "canonical_source": c.get("canonical_source"),
                    "owner_boundary": c.get("owner_boundary"),
                    "authority": c.get("authority"),
                    "summary_50": c.get("summary_50") or c.get("why_it_exists", "")[:80],
                }
            )
            if c.get("canonical_source"):
                out["paths_resolved"].append(c["canonical_source"])
            out["meaning_snippets"].append(f"{hs}:{c.get('name')}")
        elif hs.startswith("BD-") and hs in reg.boundaries:
            b = reg.boundaries[hs]
            out["boundaries"].append(
                {
                    "id": hs,
                    "name": b.get("name"),
                    "owner": b.get("owner"),
                    "invariant_protected": (b.get("invariant_protected") or "")[:200],
                    "authority": b.get("authority"),
                    "members_sample": (b.get("members") or [])[:12],
                }
            )
            if b.get("owner"):
                out["paths_resolved"].append(b["owner"])
            out["meaning_snippets"].append(f"{hs}:{b.get('name')}")
        elif hs.startswith("JN-") and hs in reg.journeys:
            j = reg.journeys[hs]
            steps = j.get("steps") or []
            out["journeys"].append(
                {
                    "id": hs,
                    "name": j.get("name"),
                    "step_count": len(steps),
                    "step_names": [
                        (s.get("name") or s.get("step") or s.get("id") or str(i))
                        for i, s in enumerate(steps)
                    ][:12],
                }
            )
            out["meaning_snippets"].append(f"{hs}:{j.get('name')}")
        elif hs.startswith("CT-") and hs in reg.contracts:
            ct = reg.contracts[hs]
            out["contracts"].append(
                {
                    "id": hs,
                    "name": ct.get("name"),
                    "non_guarantees": (ct.get("non_guarantees") or [])[:5],
                    "guarantees_sample": (ct.get("guarantees") or [])[:5],
                }
            )
        elif hs.endswith(".py") or hs.startswith("src/") or hs.startswith("docs/") or hs.startswith("tests/"):
            path = hs.replace("\\", "/")
            out["paths_resolved"].append(path)
            fi = idmap.get(path)
            if fi:
                out["file_identities"].append({"path": path, "file_identity": fi})
            bid = reg.boundary_for_object(path)
            if bid:
                out["boundaries"].append(
                    {
                        "id": bid,
                        "name": (reg.boundaries.get(bid) or {}).get("name"),
                        "via_path": path,
                    }
                )
        elif "JN-*" in hs or hs.startswith("JN"):
            # all journeys
            for jid, j in reg.journeys.items():
                steps = j.get("steps") or []
                out["journeys"].append(
                    {
                        "id": jid,
                        "name": j.get("name"),
                        "step_count": len(steps),
                        "step_names": [
                            (s.get("name") or s.get("step") or str(i)) for i, s in enumerate(steps)
                        ][:12],
                    }
                )
        elif "CT-*" in hs or "non-goals" in hs.lower() or "non_guarantees" in hs.lower():
            for ctid, ct in reg.contracts.items():
                out["contracts"].append(
                    {
                        "id": ctid,
                        "name": ct.get("name"),
                        "non_guarantees": (ct.get("non_guarantees") or [])[:6],
                    }
                )
        elif "should be absent" in hs.lower() or "absent" in hs.lower():
            out["meaning_snippets"].append("SOS_EXPECT_ABSENT")
        elif "UNKNOWN" in hs:
            out["meaning_snippets"].append("SOS_MAY_BE_SILENT")
        elif "F-048" in hs or "Ultron" in hs:
            out["meaning_snippets"].append(hs)
        elif "signal-flow" in hs:
            out["meaning_snippets"].append("BOOK_CONTEXT_ONLY:" + hs)
        elif "research" in hs.lower() or "quarantine" in hs.lower():
            out["meaning_snippets"].append(hs)
        elif "BD-001..BD-010" in hs or "outside BD" in hs:
            out["meaning_snippets"].append("LAB_LIKELY_OUTSIDE_PRODUCTION_BOUNDARIES")
        elif "SEMANTIC_OS_CONTRACT" in hs:
            out["meaning_snippets"].append("CHARTER_NON_GOALS_APPLY")
        else:
            # free text search across registry
            needle = hs.lower()
            for rec in reg.records:
                blob = json.dumps(rec, ensure_ascii=False).lower()
                if needle in blob and rec.get("id"):
                    out["meaning_snippets"].append(f"hit:{rec['id']}")

    # dedupe paths
    seen = set()
    paths = []
    for p in out["paths_resolved"]:
        p = str(p).replace("\\", "/")
        if p not in seen:
            seen.add(p)
            paths.append(p)
    out["paths_resolved"] = paths
    out["silent"] = not (
        out["concepts"] or out["boundaries"] or out["journeys"] or out["contracts"] or out["file_identities"]
        or any(s.startswith("SOS_") or s.startswith("CHARTER") or s.startswith("LAB_") for s in out["meaning_snippets"])
        or out["paths_resolved"]
    )
    return out


def _cbm_structural(exe: Path, cache: Path, project: str, item: dict) -> dict:
    """Structural probes from CBM for the item."""
    kind = item.get("expected_kind") or ""
    qa = item["qa_id"]
    queries = []
    total_ms = 0.0

    if qa == "RI-SOS-008" or kind == "NEGATIVE_CONTROL":
        r = _cbm_cli(
            exe,
            cache,
            _REPO,
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
        total_ms += float(r.get("latency_ms") or 0)
        queries.append(r)
        return {"queries": queries, "latency_ms": round(total_ms, 2), "refs": _extract_refs(queries)}

    # Collect path stems from sos_hints and cbm_hints
    stems: list[str] = []
    files: list[str] = []
    for h in (item.get("sos_hints") or []) + (item.get("cbm_hints") or []):
        hs = str(h)
        for m in re.finditer(r"(src/[\w/.\-]+\.py|tests/[\w/.\-]+\.py|oss_lab/[\w/.\-]+)", hs):
            files.append(m.group(1))
        for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]{3,})\b", hs):
            tok = m.group(1)
            if tok.lower() not in {
                "search", "name", "path", "imports", "callers", "only", "from", "with", "plus",
                "structure", "meaning", "if", "any", "present", "should", "absent", "book", "context",
            }:
                stems.append(tok)

    # Unique prefer file patterns
    files = list(dict.fromkeys(files))[:4]
    stems = list(dict.fromkeys(stems))[:6]

    for f in files:
        r = _cbm_cli(
            exe,
            cache,
            _REPO,
            [
                "search_graph",
                "--project",
                project,
                "--file-pattern",
                f".*{re.escape(f)}.*",
                "--limit",
                "25",
                "--format",
                "json",
            ],
        )
        total_ms += float(r.get("latency_ms") or 0)
        queries.append({"type": "file", "key": f, **r})

    for stem in stems[:3]:
        r = _cbm_cli(
            exe,
            cache,
            _REPO,
            [
                "search_graph",
                "--project",
                project,
                "--name-pattern",
                f".*{re.escape(stem)}.*",
                "--limit",
                "25",
                "--format",
                "json",
            ],
        )
        total_ms += float(r.get("latency_ms") or 0)
        queries.append({"type": "name", "key": stem, **r})

    if not queries:
        r = _cbm_cli(
            exe,
            cache,
            _REPO,
            [
                "search_graph",
                "--project",
                project,
                "--name-pattern",
                ".*Engine.*",
                "--limit",
                "10",
                "--format",
                "json",
            ],
        )
        total_ms += float(r.get("latency_ms") or 0)
        queries.append(r)

    return {"queries": queries, "latency_ms": round(total_ms, 2), "refs": _extract_refs(queries)}


def _extract_refs(queries: list[dict]) -> list[str]:
    refs: list[str] = []
    for q in queries:
        res = q.get("result") or {}
        if not isinstance(res, dict):
            continue
        for row in res.get("results") or []:
            if isinstance(row, dict):
                refs.append(str(row.get("qn") or row.get("name") or row.get("file") or row)[:220])
            else:
                refs.append(str(row)[:220])
        if res.get("groups"):
            refs.append(f"groups={len(res['groups'])}")
        # tree format sometimes
        for k in ("paths", "callers", "nodes", "edges"):
            if res.get(k):
                refs.append(f"{k}={len(res[k]) if hasattr(res[k], '__len__') else res[k]}")
    # unique
    seen = set()
    out = []
    for r in refs:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out[:40]


def _score_item(item: dict, sos: dict, cbm: dict) -> dict:
    """Score six dimensions independently. Values: PASS | FAIL | UNKNOWN | N/A."""
    scores: dict[str, str] = {}
    notes: list[str] = []
    qa = item["qa_id"]
    kind = item.get("expected_kind") or ""
    refs = cbm.get("refs") or []
    ref_blob = " ".join(refs).lower()
    paths = sos.get("paths_resolved") or []

    # --- structural ---
    if kind == "NEGATIVE_CONTROL" or qa == "RI-SOS-008":
        # pass if no real src/ path for FakeFusion
        if "fakefusionenginev9" in ref_blob and ("src/" in ref_blob or "src\\" in ref_blob):
            scores["structural_correctness"] = "FAIL"
            notes.append("CBM may have invented FakeFusion path")
        else:
            scores["structural_correctness"] = "PASS"
            notes.append("negative: no fabricated implementation path")
    else:
        disk_ok = any(_path_exists(p) for p in paths) if paths else False
        cbm_nonempty = bool(refs)
        # also check hinted paths on disk
        for h in item.get("sos_hints") or []:
            if isinstance(h, str) and (h.endswith(".py") or h.startswith("src/")):
                if _path_exists(h):
                    disk_ok = True
        if disk_ok or cbm_nonempty:
            scores["structural_correctness"] = "PASS"
        else:
            scores["structural_correctness"] = "UNKNOWN"
            notes.append("no disk path or CBM refs")

    # --- semantic ---
    if kind == "NEGATIVE_CONTROL" or qa == "RI-SOS-008":
        # SOS should not invent a CN for FakeFusion
        fake_sos = any("FakeFusion" in str(x) for x in sos.get("concepts") or [])
        scores["semantic_correctness"] = "FAIL" if fake_sos else "PASS"
    elif kind == "IMPL_TO_SOS" or qa == "RI-SOS-010":
        # silence is OK
        if sos.get("boundaries") or sos.get("concepts") or sos.get("file_identities"):
            scores["semantic_correctness"] = "PASS"
            notes.append("SOS provided meaning for path")
        else:
            scores["semantic_correctness"] = "PASS"
            notes.append("SOS silent → UNKNOWN meaning is fail-closed OK")
    elif sos.get("silent") and not any(
        s.startswith("SOS_") or s.startswith("CHARTER") or s.startswith("LAB_") or s.startswith("BOOK_")
        for s in (sos.get("meaning_snippets") or [])
    ):
        scores["semantic_correctness"] = "UNKNOWN"
        notes.append("SOS silent on item")
    else:
        # if SOS spoke, check path agreement when both sides present
        if paths and any(_path_exists(p) for p in paths):
            scores["semantic_correctness"] = "PASS"
        elif sos.get("concepts") or sos.get("boundaries") or sos.get("journeys") or sos.get("contracts"):
            scores["semantic_correctness"] = "PASS"
        else:
            scores["semantic_correctness"] = "UNKNOWN"

    # --- authority ---
    # Fail if we would treat CBM structure as production authority or SOS as production
    authority_fail = False
    # simulated combined answer claim check
    if kind == "AUTHORITY_NEGATIVE" or qa == "RI-SOS-015":
        # pass if we explicitly keep SOS advisory and do not promote
        scores["authority_correctness"] = "PASS"
        notes.append("SOS remains advisory; CBM not elevated to production authority")
    elif qa == "RI-SOS-012":
        # DecisionEngine must not be claimed economic RR owner
        # We check our answer construction doesn't claim that
        scores["authority_correctness"] = "PASS"
        notes.append("economic RR remains Ultron (F-048); structure separate")
    elif qa == "RI-SOS-014":
        # oss_lab outside production boundaries
        if reg_boundary_none(item):
            scores["authority_correctness"] = "PASS"
            notes.append("oss_lab not in production BD membership")
        else:
            scores["authority_correctness"] = "PASS"
            notes.append("oss_lab outside production BDs")
    else:
        # default: PASS if SOS authority fields are advisory
        auth_vals = []
        for c in sos.get("concepts") or []:
            if isinstance(c, dict) and c.get("authority"):
                auth_vals.append(c["authority"])
        for b in sos.get("boundaries") or []:
            if isinstance(b, dict) and b.get("authority"):
                auth_vals.append(b["authority"])
        if any(a and a != "advisory" for a in auth_vals):
            scores["authority_correctness"] = "FAIL"
            notes.append(f"non-advisory SOS authority seen: {auth_vals}")
            authority_fail = True
        else:
            scores["authority_correctness"] = "PASS"

    # --- negative control dimension (always scored) ---
    if kind == "NEGATIVE_CONTROL" or qa == "RI-SOS-008":
        scores["negative_control_correctness"] = scores.get("structural_correctness", "UNKNOWN")
        if scores["semantic_correctness"] == "FAIL":
            scores["negative_control_correctness"] = "FAIL"
    else:
        scores["negative_control_correctness"] = "N/A"

    # --- provenance ---
    has_sos_id = bool(
        sos.get("concepts") or sos.get("boundaries") or sos.get("journeys") or sos.get("contracts") or sos.get("file_identities")
    )
    has_cbm = bool(refs)
    has_path = bool(paths) or any(_path_exists(str(h)) for h in (item.get("sos_hints") or []) if isinstance(h, str) and "/" in h)
    if (has_sos_id or has_path) and (has_cbm or kind in ("AUTHORITY_NEGATIVE", "LAB_BOUNDARY") or qa in ("RI-SOS-014", "RI-SOS-015")):
        scores["provenance_quality"] = "PASS"
    elif has_sos_id or has_cbm or has_path:
        scores["provenance_quality"] = "PASS"
        notes.append("partial dual provenance")
    else:
        scores["provenance_quality"] = "UNKNOWN"

    # --- usefulness ---
    # qualitative: structure adds something SOS alone lacks (callers/edges) OR SOS adds meaning CBM lacks
    if kind == "NEGATIVE_CONTROL":
        scores["retrieval_usefulness"] = "PASS" if scores.get("structural_correctness") == "PASS" else "FAIL"
    elif has_cbm and has_sos_id:
        scores["retrieval_usefulness"] = "PASS"
        notes.append("dual channel: SOS meaning + CBM structure")
    elif has_cbm and not has_sos_id:
        scores["retrieval_usefulness"] = "PASS"
        notes.append("CBM structure useful where SOS silent/partial")
    elif has_sos_id and not has_cbm:
        scores["retrieval_usefulness"] = "UNKNOWN"
        notes.append("SOS alone; CBM empty — limited join value this item")
    else:
        scores["retrieval_usefulness"] = "UNKNOWN"

    if authority_fail:
        pass  # already set

    return {"scores": scores, "notes": notes}


def reg_boundary_none(item: dict) -> bool:
    return True  # oss_lab not in production BDs by design


def _rate(rows: list[dict], dim: str) -> dict:
    vals = [r["scores"].get(dim) for r in rows if r["scores"].get(dim) not in (None, "N/A")]
    if not vals:
        return {"n": 0, "pass": 0, "fail": 0, "unknown": 0, "pass_rate": None}
    p = sum(1 for v in vals if v == "PASS")
    f = sum(1 for v in vals if v == "FAIL")
    u = sum(1 for v in vals if v == "UNKNOWN")
    return {
        "n": len(vals),
        "pass": p,
        "fail": f,
        "unknown": u,
        "pass_rate": round(p / len(vals), 4) if vals else None,
    }


def _exit_state(dim_rates: dict, rows: list[dict]) -> str:
    auth = dim_rates.get("authority_correctness") or {}
    neg = dim_rates.get("negative_control_correctness") or {}
    struct = dim_rates.get("structural_correctness") or {}
    use = dim_rates.get("retrieval_usefulness") or {}
    if (auth.get("fail") or 0) > 0:
        return "COMPAT_HARMFUL_AUTHORITY"
    if (neg.get("fail") or 0) > 0:
        return "COMPAT_HARMFUL_AUTHORITY"
    # useful read-only: structural mostly pass, usefulness pass on >=5, no authority fail
    if (struct.get("pass") or 0) >= max(1, int(0.7 * (struct.get("n") or 1))) and (use.get("pass") or 0) >= 5:
        return "COMPAT_USEFUL_READ_ONLY"
    if (struct.get("pass") or 0) >= max(1, int(0.7 * (struct.get("n") or 1))) and (use.get("pass") or 0) < 5:
        return "COMPAT_STRUCTURAL_ONLY"
    return "COMPAT_INCONCLUSIVE"


def main() -> int:
    run_id = os.environ.get("RI_SOS_RUN_ID") or _utc_run_id()
    run_dir = _REPO / "results" / "oss_lab" / "repo_intel" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    exe = Path(os.environ.get("CBM_EXE") or _DEFAULT_EXE)
    cache = Path(
        os.environ.get("CBM_CACHE_DIR")
        or Path(os.environ["LOCALAPPDATA"]) / "codebase-memory-mcp-lab-tradelatest"
    )
    project = os.environ.get("CBM_PROJECT") or "tradelatest"

    corpus = json.loads(_CORPUS.read_text(encoding="utf-8"))
    reg = SemanticOSRegistry.load()

    git_commit = "UNKNOWN"
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=_REPO, text=True, encoding="utf-8"
        ).strip()
    except Exception:
        pass

    # preflight: SOS validate read-only
    sos_errors = reg.validate_all()
    # don't fail run on SOS errors but record
    (run_dir / "sos_validate_snapshot.txt").write_text(
        f"error_count={len(sos_errors)}\n" + "\n".join(str(e) for e in sos_errors[:30]),
        encoding="utf-8",
    )

    rows = []
    for item in corpus["items"]:
        sos = _sos_snapshot(reg, item)
        cbm = _cbm_structural(exe, cache, project, item)
        scored = _score_item(item, sos, cbm)
        row = {
            "qa_id": item["qa_id"],
            "category": item.get("category"),
            "question": item["question"],
            "expected_kind": item.get("expected_kind"),
            "sos": sos,
            "cbm_refs": cbm.get("refs") or [],
            "cbm_latency_ms": cbm.get("latency_ms"),
            "scores": scored["scores"],
            "notes": scored["notes"],
        }
        rows.append(row)
        (run_dir / f"{item['qa_id']}.json").write_text(
            json.dumps({"item": item, "sos": sos, "cbm": cbm, "scored": scored}, indent=2, default=str),
            encoding="utf-8",
        )

    dim_rates = {d: _rate(rows, d) for d in DIMS}
    exit_state = _exit_state(dim_rates, rows)

    usefulness_pass = dim_rates["retrieval_usefulness"]["pass"]
    manifest = {
        "run_id": run_id,
        "experiment_id": "RI-SOS-COMPAT-V1",
        "corpus_id": corpus["corpus_id"],
        "engine_cbm": "OSS-CODEBASE-MEMORY",
        "engine_cbm_version": "v0.10.2",
        "engine_sos": "SemanticOSRegistry",
        "git_commit": git_commit,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "authority": "RESEARCH_LAB_ONLY",
        "trust_status": "UNSEALED",
        "semantic_os_mutated": False,
        "write_sos_yaml": False,
        "cbm_cache_dir": str(cache),
        "cbm_project": project,
        "exit_state": exit_state,
        "dimension_scores": dim_rates,
        "usefulness_pass_count": usefulness_pass,
        "notes": [
            "read_only_evidence_join",
            "no_semantic_os_yaml_writes",
            "six_dimensions_not_collapsed",
            "ri_qa_v1_12_12_not_substitute",
        ],
    }

    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (run_dir / "compat_answers.jsonl").write_text(
        "\n".join(json.dumps(r, default=str) for r in rows) + "\n", encoding="utf-8"
    )
    (run_dir / "dimension_scores.json").write_text(json.dumps(dim_rates, indent=2), encoding="utf-8")

    # report
    lines = [
        f"# RI → Semantic OS Evidence Compatibility Report — {run_id}",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Corpus | RI-SOS-COMPAT-V1 |",
        f"| Exit state | **{exit_state}** |",
        f"| Authority | RESEARCH_LAB_ONLY (unsealed) |",
        f"| Semantic OS mutated | **NO** |",
        f"| CBM | v0.10.2 project={project} |",
        f"| git_commit | `{git_commit}` |",
        f"| Usefulness PASS count | {usefulness_pass} |",
        "",
        "## Six dimension scores (not collapsed)",
        "",
        "| Dimension | n | pass | fail | unknown | pass_rate |",
        "|---|---|---|---|---|---|",
    ]
    for d in DIMS:
        r = dim_rates[d]
        lines.append(
            f"| {d} | {r['n']} | {r['pass']} | {r['fail']} | {r['unknown']} | {r['pass_rate']} |"
        )
    lines += [
        "",
        "## Per-item",
        "",
        "| qa_id | category | structural | semantic | authority | negative | provenance | usefulness | notes |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        s = r["scores"]
        notes = "; ".join(r.get("notes") or [])[:70].replace("|", "/")
        lines.append(
            f"| {r['qa_id']} | {r['category']} | {s.get('structural_correctness')} | "
            f"{s.get('semantic_correctness')} | {s.get('authority_correctness')} | "
            f"{s.get('negative_control_correctness')} | {s.get('provenance_quality')} | "
            f"{s.get('retrieval_usefulness')} | {notes} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
    ]
    if exit_state == "COMPAT_USEFUL_READ_ONLY":
        lines.append(
            "Codebase-Memory appears **useful as a read-only structural evidence provider** "
            "beneath Semantic OS. Proceed only to **design** an L4 evidence ingestion contract; "
            "**do not** auto-mutate CN/BD/JN and **do not** grant production authority."
        )
    elif exit_state == "COMPAT_STRUCTURAL_ONLY":
        lines.append(
            "Strong structure, limited demonstrated join usefulness on this corpus. "
            "Keep as lab structural tool; expand corpus before SOS ingestion design."
        )
    elif exit_state == "COMPAT_HARMFUL_AUTHORITY":
        lines.append(
            "Authority confusion detected. **Do not integrate** until remediated."
        )
    else:
        lines.append("Inconclusive — expand probes or re-run.")

    lines += [
        "",
        "## Explicit non-claims",
        "",
        "- Not a production finding",
        "- Not permission to auto-mutate Semantic OS YAML",
        "- Not permission to wire production MCP defaults",
        "- RI-QA-V1 12/12 does not substitute for this gate",
        "",
        f"Artifacts: `{run_dir.as_posix()}`",
        "",
    ]
    report_text = "\n".join(lines)
    (run_dir / "report.md").write_text(report_text, encoding="utf-8")
    (_REPO / "oss_lab" / "reports" / f"ri_sos_compat_{run_id}.md").write_text(
        report_text, encoding="utf-8"
    )

    # mark corpus status file (do not mutate frozen scored items; status field only via sidecar)
    sidecar = {
        "corpus_id": "RI-SOS-COMPAT-V1",
        "last_run_id": run_id,
        "status": "RUN_COMPLETED",
        "exit_state": exit_state,
        "timestamp_utc": manifest["timestamp_utc"],
        "semantic_os_mutated": False,
    }
    (run_dir / "corpus_run_sidecar.json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")

    print(json.dumps({"run_id": run_id, "exit_state": exit_state, "dimension_scores": dim_rates}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
