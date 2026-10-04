#!/usr/bin/env python3
"""Research provenance DAG: trace every architectural decision backwards to its origin.

Answers one question mechanically, for the whole repository history: *for each architectural
decision, can the originating hypothesis, finding, evidence artifact and measurement basis be
recovered from the record - and is that link EXPLICIT, INFERRED, or UNKNOWN?*

READ-ONLY. Reads the record systems only (SESSION LOG + archive, build manifests, promotion log,
closure index, the GENERATED findings/hypothesis exports, the family registry, measurement
contracts). Writes two governance artifacts and nothing else. No src/, config, model or
ACTIVE_VERSION surface is read for control flow or written.

GAPS ARE THE RESULT. Where no link exists the edge is UNKNOWN and stays UNKNOWN; nothing is
backfilled, guessed, or filled from a sibling artifact.

  python scripts/analysis/research_dag_provenance.py
  python scripts/analysis/research_dag_provenance.py --date 2026-08-26 --json OUT.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date as _date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------- sources (all read-only)
SRC_HOT_LOG = ROOT / "assistant_project.md"
SRC_LOG_ARCHIVE = ROOT / "docs" / "analysis" / "session-log-archive"
SRC_MANIFESTS = ROOT / "docs" / "governance" / "build_manifests"
SRC_PROMOTION = ROOT / "configs" / "promotion_log.jsonl"
SRC_CLOSURE = ROOT / "docs" / "governance" / "closure_authority_index.json"
SRC_FINDINGS = ROOT / "data" / "findings.jsonl"
SRC_FINDINGS_DOC = ROOT / "docs" / "current-findings.md"
SRC_HYPOTHESES = ROOT / "data" / "hypothesis_registry.jsonl"
SRC_FAMILIES = ROOT / "docs" / "governance" / "research_family_registry.json"
SRC_MC_DIR = ROOT / "configs" / "research" / "measurement_contracts"
SRC_MRESULTS = ROOT / "configs" / "research" / "measurement_result_log.jsonl"

OUT_DIR = ROOT / "docs" / "governance"
OUT_LATEST_PTR = OUT_DIR / "research_dag_provenance.LATEST.json"

# ---------------------------------------------------------------- parsing
# Tolerant marker: the hot log carries BOTH the canonical emoji form and a bare form.
# rotate_session_log.py's _MARKER_RE recognises only the emoji / "??" forms; widened HERE only
# (that script is deliberately not edited - the discrepancy is reported, not fixed).
_MARKER_RE = re.compile("^(?:\U0001F4DD|\\?\\?)?\\s?SESSION LOG ENTRY[ \t]*$")
_HR_RE = re.compile(r"^---\s*$")
_DATE_RE = re.compile(r"^Date:\s*(\d{4})-(\d{2})-(\d{2})", re.M)
_TOPIC_RE = re.compile(r"^Topic:\s*(.+)$", re.M)

ID_RE = {
    "F": re.compile(r"\bF-\d{3}\b"),
    "H": re.compile(r"\bH-\d{3}\b"),
    "CH": re.compile(r"\bCH-[A-Za-z0-9][A-Za-z0-9_\-]*"),
    "MC": re.compile(r"\bMC-[A-Z0-9][A-Z0-9\-]*"),
    "MP": re.compile(r"\bMP-[A-Z0-9][A-Z0-9\-]*"),
}
# Evidence-class prefixes ONLY. src/ and configs/ are CHANGE TARGETS, not evidence, and are
# deliberately excluded so the evidence slot keeps its meaning (documented in the write-up).
EVIDENCE_PREFIXES = ("docs/analysis/", "docs/governance/", "results/", "reports/",
                     "tests/", "scripts/analysis/", "scripts/research/", "logs/")
# A manifest listing its OWN path, or any build manifest, is bookkeeping - not evidence.
EVIDENCE_EXCLUDE_PREFIXES = ("docs/governance/build_manifests/",)
PATH_RE = re.compile(r"\b(?:docs|results|reports|tests|scripts|logs)/[A-Za-z0-9_\-./]*"
                     r"[A-Za-z0-9_\-/](?:\.[A-Za-z0-9]+)?")
# Origin-programme tokens that predate the H-* registry. EXTRACTED, never invented.
PRE_REGISTRY_TOKEN_RE = re.compile(
    r"\b(?:ENHANCEMENT_IMPLEMENTATION_PLAN|Trd-M\d|Gov-M\d|Sprint\s+\d|Phase\s+\d[A-Za-z]?|"
    r"Program\s+\d[A-Za-z]?|IC-\d{3}|PLAN-\d{3}|GD-\d{3}|SUR-\d{3})")

# timeline.md era boundaries (START dates, quoted from docs/timeline.md "Eras").
# Era 3's stated end (05-30) OVERLAPS era 4's start (05-28) in the source; start-date
# partitioning is used and the overlap is reported, not silently resolved.
ERAS = [
    ("2026-04-10", "E1 Foundation & enhancement"),
    ("2026-04-17", "E2 Agent + sprints + integration"),
    ("2026-05-12", "E3 CRT optimization Phases 0-6"),
    ("2026-05-28", "E4 Governance + dual-track + Repository Truths"),
    ("2026-06-06", "E5 Research-falsification sweep + config-first"),
    ("2026-06-27", "POST_ERA_5 (not covered by timeline.md's era list)"),
]
GATE6_DATE = "2026-07-08"   # CH-* BUILD_IMPACT_MANIFEST regime begins (CLAUDE.md 3.3b)

SLOTS = ("originating_hypothesis", "originating_finding",
         "originating_evidence", "originating_measurement_basis")

RULE_CLASS = {
    "E1_STRUCTURED_FIELD": "EXPLICIT",
    "E2_INLINE_CITATION": "EXPLICIT",
    "I1_HYPOTHESIS_BACKSEED": "INFERRED",
    "I2_FAMILY_JUDGEMENT": "INFERRED",
    "I3_DATE_COLOCATION": "INFERRED",
    "I4_FILE_OVERLAP": "INFERRED",
    "I5_VIA_CITED_FINDING": "INFERRED",
    "U1_DECLARED_UNKNOWN": "UNKNOWN",
    "U2_NO_CANDIDATE": "UNKNOWN",
    "U3_DANGLING_CITATION": "UNKNOWN",
    "U4_DECLARED_NOT_EXECUTED": "UNKNOWN",
}


def _git_tracked() -> set[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    return set(out.stdout.splitlines())


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def _jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(line) for line in _read(p).splitlines() if line.strip()]


def parse_session_entries(text: str, source: str) -> list[dict]:
    """Split a SESSION LOG file into entries.

    Mirrors rotate_session_log.parse_log's shape (marker -> next `---` / marker / EOF) with the
    widened marker regex.
    """
    lines = text.splitlines()
    out: list[dict] = []
    i, n = 0, len(lines)
    while i < n:
        if _MARKER_RE.match(lines[i]):
            start = i + 1
            body: list[str] = []
            i += 1
            while i < n and not _HR_RE.match(lines[i]) and not _MARKER_RE.match(lines[i]):
                body.append(lines[i])
                i += 1
            if i < n and _HR_RE.match(lines[i]):
                i += 1
            b = "\n".join(body).rstrip()
            dm, tm = _DATE_RE.search(b), _TOPIC_RE.search(b)
            out.append({
                "source": source, "line": start,
                "date": "-".join(dm.groups()) if dm else None,
                "topic": (tm.group(1).strip() if tm else "")[:240],
                "body": b,
            })
        else:
            i += 1
    return out


def era_of(d: str | None) -> str:
    if not d:
        return "UNDATED"
    if d < ERAS[0][0]:
        return "PRE_TIMELINE"
    label = ERAS[0][1]
    for start, lab in ERAS:
        if d >= start:
            label = lab
    return label


# ---------------------------------------------------------------- ground truth
_DOC_FINDING_RE = re.compile(r"^###\s+(F-\d{3})\b", re.M)
_DOC_FIELD_RE = re.compile(r"^-\s+(Contract|Family):\s*(.+?)\s*$", re.M)


def _findings_doc_fields() -> dict[str, dict]:
    """Read Contract:/Family: from the AUTHORITATIVE findings doc.

    data/findings.jsonl is the GENERATED view. Until 2026-08-26 governance.findings_export._FIELDS
    omitted BOTH `Family` and `Contract` - the two fields the 2026-08-06 measurement-contract work
    added - so the machine-readable export could not answer "what measurement basis?" at all.
    That gap is now closed (CH-measurement-provenance-boundary), but the doc stays the read here:
    it is the authoritative store, and `export_missing_fields` in the payload keeps MEASURING the
    divergence rather than assuming it stays closed.
    """
    if not SRC_FINDINGS_DOC.exists():
        return {}
    text = _read(SRC_FINDINGS_DOC)
    marks = [(m.group(1), m.start()) for m in _DOC_FINDING_RE.finditer(text)]
    out: dict[str, dict] = {}
    for i, (fid, start) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        out[fid] = {k.lower(): v for k, v in _DOC_FIELD_RE.findall(text[start:end])}
    return out


def load_ground_truth() -> dict:
    findings = {r["id"]: r for r in _jsonl(SRC_FINDINGS) if r.get("kind") == "finding"}
    doc_fields = _findings_doc_fields()
    # Which of the doc's Contract:/Family: fields never survive into the GENERATED export.
    exported_keys = set().union(*[set(r) for r in findings.values()]) if findings else set()
    export_gap = sorted(f for f in ("Contract", "Family") if f.lower() not in exported_keys)
    for fid, rec in findings.items():
        extra = doc_fields.get(fid, {})
        rec["contract_present"] = "contract" in extra
        rec["contract"] = extra.get("contract", "UNKNOWN")
        rec["family"] = extra.get("family", "")
    hypotheses = {r["id"]: r for r in _jsonl(SRC_HYPOTHESES) if r.get("id")}

    fam = json.loads(_read(SRC_FAMILIES))
    finding_to_family: dict[str, list[str]] = defaultdict(list)
    for f in fam.get("families", []):
        for layer, cell in (f.get("cells") or {}).items():
            for claim in cell.get("claims") or []:
                finding_to_family[claim].append(f"{f['family_id']}.{layer}")

    finding_to_hyp: dict[str, list[str]] = defaultdict(list)
    for hid, h in hypotheses.items():
        for fid in h.get("findings") or []:
            finding_to_hyp[fid].append(hid)

    contracts = {p.stem: str(p.relative_to(ROOT)).replace("\\", "/")
                 for p in SRC_MC_DIR.rglob("*.json") if p.stem.startswith(("MC-", "MP-"))}
    # Profile files are named crypto_majors.v1.json etc.; their MP-* id lives inside.
    for p in SRC_MC_DIR.glob("*.json"):
        try:
            body = json.loads(_read(p))
        except Exception:
            continue
        pid = body.get("profile_id") or body.get("id") or body.get("contract_id")
        if isinstance(pid, str) and pid.startswith(("MP-", "MC-")):
            contracts[pid] = str(p.relative_to(ROOT)).replace("\\", "/")

    # A Contract may be CONTENT-addressed: the sha256 of the sealed instance file itself, the
    # workaround used before id-citation existed (RC-1, 2026-08-19). Resolving by id ALONE made
    # every such field look like a record gap when the byte-exact link was there all along - the
    # 2026-08-26 audit reported 6 of them as unresolvable on that basis. Resolution, not backfill:
    # a hash that matches nothing stays UNKNOWN.
    contract_content_hashes: dict[str, str] = {}
    for p in sorted(SRC_MC_DIR.rglob("*.json")):
        try:
            body = json.loads(_read(p))
        except Exception:
            continue
        cid = body.get("contract_id") or body.get("profile_id")
        if isinstance(cid, str) and cid.startswith(("MC-", "MP-")):
            contract_content_hashes[hashlib.sha256(p.read_bytes()).hexdigest()] = cid

    # Rewrite a resolvable content hash to the id it names, recording the original so the
    # substitution is auditable (never silent).
    for rec in findings.values():
        c = rec.get("contract")
        if isinstance(c, str) and len(c) == 64 and c in contract_content_hashes:
            rec["contract_sha256_cited"] = c
            rec["contract"] = contract_content_hashes[c]

    mres = _jsonl(SRC_MRESULTS)
    executed = {r.get("contract_id") for r in mres
                if r.get("kind") != "meta" and r.get("contract_id")}
    sealed_bound = next((r.get("sealed_pass_bound") for r in mres if r.get("kind") == "meta"), None)

    manifests: dict[str, dict] = {}
    for p in sorted(SRC_MANIFESTS.glob("*.impact.json")):
        try:
            body = json.loads(_read(p))
        except Exception:
            continue
        cid = body.get("change_id") or p.stem.replace(".impact", "")
        manifests[cid] = {"path": str(p.relative_to(ROOT)).replace("\\", "/"), **body}
    completions = set()
    for p in sorted(SRC_MANIFESTS.glob("*.completion.json")):
        try:
            completions.add(json.loads(_read(p)).get("change_id", p.stem.replace(".completion", "")))
        except Exception:
            completions.add(p.stem.replace(".completion", ""))

    return {
        "findings": findings, "hypotheses": hypotheses,
        "finding_to_family": dict(finding_to_family), "finding_to_hyp": dict(finding_to_hyp),
        "contracts": contracts, "executed_contracts": executed, "sealed_pass_bound": sealed_bound,
        "manifests": manifests, "completions": completions,
        "families_meta": fam.get("provenance", {}),
        "findings_doc_fields_read": len(doc_fields),
        "export_missing_fields": export_gap,
    }


# ---------------------------------------------------------------- decision nodes
def build_decisions(gt: dict) -> list[dict]:
    nodes: list[dict] = []

    files = [(SRC_HOT_LOG, "assistant_project.md")] + [
        (p, "docs/analysis/session-log-archive/" + p.name)
        for p in sorted(SRC_LOG_ARCHIVE.glob("session-log-*.md"))]
    seq = 0
    for path, rel in files:
        for e in parse_session_entries(_read(path), rel):
            seq += 1
            nodes.append({
                "node_id": "D-SESSION-%04d" % seq, "type": "DECISION_SESSION",
                "date": e["date"], "era": era_of(e["date"]),
                "source_path": rel, "source_locator": "%s:%d" % (rel, e["line"]),
                "title": e["topic"] or "(no Topic line)", "_text": e["body"],
                "_structured": {},
            })

    for cid, m in sorted(gt["manifests"].items()):
        nodes.append({
            "node_id": "D-CH-" + cid, "type": "DECISION_CH",
            "date": m.get("date_utc"), "era": era_of(m.get("date_utc")),
            "source_path": m["path"], "source_locator": m["path"],
            "title": (m.get("objective") or "")[:240],
            "_text": json.dumps({k: v for k, v in m.items() if k != "path"}, ensure_ascii=False),
            "_structured": {
                "affected_files": m.get("affected_files") or [],
                "authority_granted": m.get("authority_granted") or "",
                "objective": m.get("objective") or "",
                "has_completion": cid in gt["completions"],
            },
        })

    for i, r in enumerate(_jsonl(SRC_PROMOTION), 1):
        d = (r.get("timestamp") or "")[:10] or None
        nodes.append({
            "node_id": "D-PROMO-%03d" % i, "type": "DECISION_PROMOTION",
            "date": d, "era": era_of(d),
            "source_path": "configs/promotion_log.jsonl",
            "source_locator": "configs/promotion_log.jsonl:%d" % i,
            "title": "%s: %s" % (r.get("event"), (r.get("reason") or "")[:180]),
            "_text": json.dumps(r, ensure_ascii=False), "_structured": {},
        })

    closure = json.loads(_read(SRC_CLOSURE))
    for s in closure.get("surfaces", []):
        blob = json.dumps(s, ensure_ascii=False)
        m = re.search(r"(\d{4}-\d{2}-\d{2})", blob)
        d = m.group(1) if m else None
        nodes.append({
            "node_id": "D-CLOSURE-" + s["surface_id"], "type": "DECISION_CLOSURE",
            "date": d, "era": era_of(d),
            "source_path": "docs/governance/closure_authority_index.json",
            "source_locator": "docs/governance/closure_authority_index.json#" + s["surface_id"],
            "title": "%s = %s" % (s.get("surface_name"), s.get("status")),
            "_text": blob,
            "_structured": {"authoritative_artifact": s.get("authoritative_artifact") or ""},
        })
    return nodes


# ---------------------------------------------------------------- classifier
def _clean_path(tok: str) -> str:
    return tok.rstrip(".,;:)]}`'\"")


def classify(node: dict, gt: dict, tracked: set[str]) -> list[dict]:
    """Return one edge record per slot.

    Ordered rules; within a slot the BEST resolvable link wins and unresolvable citations are
    recorded separately - a dangling cite never scores EXPLICIT, but it also does not erase a
    resolvable one cited alongside it.
    """
    text, st = node["_text"], node["_structured"]
    edges: list[dict] = []

    cited_f = sorted(set(ID_RE["F"].findall(text)))
    cited_h = sorted(set(ID_RE["H"].findall(text)))
    cited_mc = sorted(set(ID_RE["MC"].findall(text)) | set(ID_RE["MP"].findall(text)))
    live_f = [f for f in cited_f if f in gt["findings"]]
    dead_f = [f for f in cited_f if f not in gt["findings"]]
    live_h = [h for h in cited_h if h in gt["hypotheses"]]
    dead_h = [h for h in cited_h if h not in gt["hypotheses"]]
    live_mc = [c for c in cited_mc if c in gt["contracts"]]
    dead_mc = [c for c in cited_mc if c not in gt["contracts"]]

    def emit(slot, rule, dst, witness, extra=None):
        e = {"src": node["node_id"], "slot": slot, "dst": dst,
             "class": RULE_CLASS[rule], "rule_id": rule, "witness": witness}
        if extra:
            e.update(extra)
        edges.append(e)

    # ---- slot 1: originating hypothesis
    if live_h:
        emit("originating_hypothesis", "E2_INLINE_CITATION", live_h,
             "H-id cited in %s: %s" % (node["source_locator"], ",".join(live_h)))
    elif dead_h:
        emit("originating_hypothesis", "U3_DANGLING_CITATION", [],
             "H-id cited but not in hypothesis registry: " + ",".join(dead_h))
    else:
        via = sorted({h for f in live_f for h in gt["finding_to_hyp"].get(f, [])})
        fams = sorted({fa for f in live_f for fa in gt["finding_to_family"].get(f, [])})
        if via:
            emit("originating_hypothesis", "I1_HYPOTHESIS_BACKSEED", via,
                 "hypothesis_registry.findings[] binds %s -> %s; registry cites the finding, "
                 "no finding cites an H-*" % (",".join(live_f), ",".join(via)))
        elif fams:
            emit("originating_hypothesis", "I2_FAMILY_JUDGEMENT", fams,
                 "research_family_registry cell claims[] binds %s -> %s (self-declared AUTHORED "
                 "JUDGEMENT, verified_against_filesystem=false)" % (",".join(live_f), ",".join(fams)))
        else:
            emit("originating_hypothesis", "U2_NO_CANDIDATE", [], "no H-* reachable by any rule")

    # ---- slot 2: originating finding
    if live_f:
        structured_blob = st.get("objective", "") + st.get("authority_granted", "")
        rule = ("E1_STRUCTURED_FIELD"
                if node["type"] == "DECISION_CH" and any(f in structured_blob for f in live_f)
                else "E2_INLINE_CITATION")
        emit("originating_finding", rule, live_f,
             "F-id cited in %s: %s" % (node["source_locator"], ",".join(live_f)),
             {"dangling_also_cited": dead_f} if dead_f else None)
    elif dead_f:
        emit("originating_finding", "U3_DANGLING_CITATION", [],
             "F-id cited but absent from data/findings.jsonl: " + ",".join(dead_f))
    else:
        same_day = sorted([f for f, r in gt["findings"].items()
                           if node.get("date") and r.get("validated") == node["date"]])
        if same_day:
            emit("originating_finding", "I3_DATE_COLOCATION", same_day,
                 "finding Validated: == decision date %s; neither cites the other" % node["date"])
        else:
            emit("originating_finding", "U2_NO_CANDIDATE", [], "no F-* reachable by any rule")

    # ---- slot 3: originating evidence
    def _is_evidence(p: str) -> bool:
        return (p.startswith(EVIDENCE_PREFIXES)
                and not p.startswith(EVIDENCE_EXCLUDE_PREFIXES)
                and p != node["source_path"])

    declared = [p for p in st.get("affected_files", []) if _is_evidence(p)]
    inline = sorted({_clean_path(t) for t in PATH_RE.findall(text)
                     if _is_evidence(_clean_path(t))})
    via_finding = sorted({p for f in live_f
                          for p in (gt["findings"][f].get("evidence_paths") or [])})
    if declared:
        live = [p for p in declared if p in tracked]
        dead = [p for p in declared if p not in tracked]
        if live:
            emit("originating_evidence", "E1_STRUCTURED_FIELD", live,
                 "manifest affected_files[] evidence-class entries, git-tracked: %d" % len(live),
                 {"dangling_also_cited": dead} if dead else None)
        else:
            emit("originating_evidence", "U3_DANGLING_CITATION", [],
                 "manifest affected_files[] evidence entries none git-tracked: "
                 + ",".join(dead[:5]))
    elif inline:
        live = [p for p in inline if p in tracked]
        dead = [p for p in inline if p not in tracked]
        if live:
            more = (" (+%d more)" % (len(live) - 1)) if len(live) > 1 else ""
            emit("originating_evidence", "E2_INLINE_CITATION", live,
                 "evidence-class path cited in body and git-tracked: %s%s" % (live[0], more),
                 {"dangling_also_cited": dead} if dead else None)
        else:
            emit("originating_evidence", "U3_DANGLING_CITATION", [],
                 "evidence-class path cited but not git-tracked: " + ",".join(dead[:5]))
    elif via_finding:
        live = [p for p in via_finding if p in tracked]
        if live:
            emit("originating_evidence", "I5_VIA_CITED_FINDING", live,
                 "reached one hop through cited finding(s) %s; the decision itself names no "
                 "evidence artifact" % ",".join(live_f))
        else:
            emit("originating_evidence", "U3_DANGLING_CITATION", [],
                 "cited finding's evidence_paths none git-tracked: " + ",".join(via_finding[:5]))
    elif node["type"] == "DECISION_CLOSURE" and st.get("authoritative_artifact"):
        a = st["authoritative_artifact"]
        if a in tracked:
            emit("originating_evidence", "E1_STRUCTURED_FIELD", [a],
                 "closure_authority_index.authoritative_artifact = " + a)
        else:
            emit("originating_evidence", "U3_DANGLING_CITATION", [],
                 "authoritative_artifact not git-tracked: " + a)
    else:
        overlap = sorted({p for p in st.get("affected_files", []) if p in tracked})
        if overlap:
            emit("originating_evidence", "I4_FILE_OVERLAP", overlap[:20],
                 "manifest affected_files[] carries %d tracked non-evidence-class paths only "
                 "(change targets, not evidence)" % len(overlap))
        else:
            emit("originating_evidence", "U2_NO_CANDIDATE", [], "no evidence artifact reachable")

    # ---- slot 4: originating measurement basis
    #  U-rules dominate this slot: a basis that is named but never executed is not a basis.
    contracts_via_finding = (sorted({(gt["findings"][f].get("contract") or "UNKNOWN")
                                     for f in live_f}) if live_f else [])
    named = live_mc or [c for c in contracts_via_finding if c and c != "UNKNOWN"]
    if named:
        unexecuted = [c for c in named if c not in gt["executed_contracts"]]
        if unexecuted:
            emit("originating_measurement_basis", "U4_DECLARED_NOT_EXECUTED", named,
                 "basis named (%s) but measurement_result_log.jsonl proves no run "
                 "(sealed_pass_bound=%s)" % (",".join(named[:4]), gt["sealed_pass_bound"]),
                 {"declared_basis": named})
        else:
            emit("originating_measurement_basis", "E1_STRUCTURED_FIELD", named,
                 "basis named and execution proven in measurement_result_log.jsonl: "
                 + ",".join(named))
    elif dead_mc:
        emit("originating_measurement_basis", "U3_DANGLING_CITATION", [],
             "MC/MP id cited but no contract file resolves: " + ",".join(dead_mc))
    elif contracts_via_finding and all(c == "UNKNOWN" for c in contracts_via_finding):
        emit("originating_measurement_basis", "U1_DECLARED_UNKNOWN", [],
             "cited finding(s) %s carry Contract: UNKNOWN" % ",".join(live_f))
    else:
        emit("originating_measurement_basis", "U2_NO_CANDIDATE", [],
             "no measurement contract reachable by any rule")

    return edges


# ---------------------------------------------------------------- rollups
def _pct(c: Counter, t: int) -> dict:
    return {k: (round(100.0 * c.get(k, 0) / t, 2) if t else 0.0)
            for k in ("EXPLICIT", "INFERRED", "UNKNOWN")}


def rollup(nodes: list[dict], edges: list[dict], gt: dict, tracked: set[str]) -> dict:
    idx = {n["node_id"]: n for n in nodes}

    def cls(pred) -> Counter:
        return Counter(e["class"] for e in edges if pred(e))

    overall = Counter(e["class"] for e in edges)
    total = sum(overall.values())

    per_slot = {}
    for s in SLOTS:
        c = cls(lambda e, s=s: e["slot"] == s)
        per_slot[s] = {"counts": dict(c), "pct": _pct(c, sum(c.values()))}

    per_type = {}
    for t in sorted({n["type"] for n in nodes}):
        c = cls(lambda e, t=t: idx[e["src"]]["type"] == t)
        per_type[t] = {"decisions": sum(1 for n in nodes if n["type"] == t),
                       "counts": dict(c), "pct": _pct(c, sum(c.values()))}

    per_era = {}
    for lab in [l for _, l in ERAS] + ["PRE_TIMELINE", "UNDATED"]:
        c = cls(lambda e, lab=lab: idx[e["src"]]["era"] == lab)
        if sum(c.values()):
            per_era[lab] = {"decisions": sum(1 for n in nodes if n["era"] == lab),
                            "counts": dict(c), "pct": _pct(c, sum(c.values()))}

    gate6 = {}
    for lab, test in (("pre_gate6", lambda d: bool(d) and d < GATE6_DATE),
                      ("post_gate6", lambda d: bool(d) and d >= GATE6_DATE)):
        c = cls(lambda e, test=test: test(idx[e["src"]].get("date")))
        gate6[lab] = {"decisions": sum(1 for n in nodes if test(n.get("date"))),
                      "counts": dict(c), "pct": _pct(c, sum(c.values()))}

    hyp_edges = {e["src"]: e for e in edges if e["slot"] == "originating_hypothesis"}
    reach = Counter()
    for n in nodes:
        e = hyp_edges.get(n["node_id"])
        if not e:
            continue
        if e["class"] == "EXPLICIT":
            reach["explicit_H"] += 1
        if e["rule_id"] == "I1_HYPOTHESIS_BACKSEED":
            reach["inferred_H_via_backseed"] += 1
        if e["rule_id"] == "I2_FAMILY_JUDGEMENT":
            reach["family_question_only"] += 1
        if e["class"] == "UNKNOWN":
            reach["no_hypothesis_reachable"] += 1

    first_h = min((h.get("created", "")[:10] for h in gt["hypotheses"].values()), default=None)
    pre_reg = [n for n in nodes if n.get("date") and first_h and n["date"] < first_h
               and hyp_edges.get(n["node_id"], {}).get("class") == "UNKNOWN"]
    tokens: Counter = Counter()
    for n in pre_reg:
        for t in PRE_REGISTRY_TOKEN_RE.findall(n["_text"]):
            tokens[re.sub(r"\s+", " ", t).strip()] += 1

    fired = Counter(e["rule_id"] for e in edges)
    dangling: Counter = Counter()
    for e in edges:
        if e["rule_id"] == "U3_DANGLING_CITATION":
            dangling[e["slot"]] += 1
        if e.get("dangling_also_cited"):
            dangling[e["slot"] + "::alongside_resolvable"] += 1

    return {
        "totals": {"decisions": len(nodes), "edges": total, "slots_per_decision": len(SLOTS),
                   "conservation_ok": total == len(nodes) * len(SLOTS),
                   "counts": dict(overall), "pct": _pct(overall, total)},
        "per_slot": per_slot, "per_decision_type": per_type, "per_era": per_era,
        "gate6_split": gate6,
        "rule_firings": {r: fired.get(r, 0) for r in sorted(RULE_CLASS)},
        "backward_reachability_to_hypothesis": dict(reach),
        "terminus_census": {
            "first_hypothesis_created": first_h,
            "decisions_before_first_hypothesis_with_no_H_reachable": len(pre_reg),
            "observed_pre_registry_origin_tokens": dict(tokens.most_common(30)),
            "note": "Tokens are EXTRACTED from the decision text, never invented. They name the "
                    "programme a pre-registry decision belongs to; no H-* exists for them.",
        },
        "dangling_citations": dict(sorted(dangling.items())),
        "measurement_layer": {
            "sealed_pass_bound": gt["sealed_pass_bound"],
            "contracts_on_disk": len(gt["contracts"]),
            "contracts_with_proven_execution": len(gt["executed_contracts"]),
            "findings_contract_declared_unknown": sum(
                1 for r in gt["findings"].values()
                if r.get("contract_present") and r.get("contract") == "UNKNOWN"),
            "findings_contract_field_absent": sorted(
                f for f, r in gt["findings"].items() if not r.get("contract_present")),
            "findings_contract_named": sorted(
                [f, r.get("contract")] for f, r in gt["findings"].items()
                if r.get("contract_present") and r.get("contract") != "UNKNOWN"),
            "findings_contract_named_sha_only": sorted(
                f for f, r in gt["findings"].items()
                if isinstance(r.get("contract"), str)
                and r["contract"] not in ("UNKNOWN",)
                and not r["contract"].startswith(("MC-", "MP-"))),
            "findings_contract_resolved_by_content_hash": sorted(
                [f, r["contract"], r["contract_sha256_cited"]]
                for f, r in gt["findings"].items() if r.get("contract_sha256_cited")),
            "note": "A sha-only Contract that matches no sealed instance's CONTENT resolves to "
                    "nothing and is counted as named, never as executed. One that DOES match is "
                    "resolved to the id it names (recorded in findings_contract_resolved_by_"
                    "content_hash); resolution is still not execution.",
        },
        "corpus_integrity": {
            "manifests_impact": len(gt["manifests"]),
            "manifests_with_completion": sum(1 for c in gt["manifests"] if c in gt["completions"]),
            "findings": len(gt["findings"]), "hypotheses": len(gt["hypotheses"]),
            "findings_export_missing_fields": gt["export_missing_fields"],
            "findings_export_missing_fields_note":
                "governance.findings_export._FIELDS omits these, so data/findings.jsonl - the "
                "GENERATED machine-readable findings view - cannot answer them at all. This "
                "extractor reads them from the authoritative doc instead.",
            "findings_bound_to_any_hypothesis": len(gt["finding_to_hyp"]),
            "finding_evidence_path_refs": sum(
                len(r.get("evidence_paths") or []) for r in gt["findings"].values()),
            "finding_evidence_path_refs_untracked": sum(
                1 for r in gt["findings"].values()
                for p in (r.get("evidence_paths") or []) if p not in tracked),
        },
    }


def build_payload(date_str: str) -> tuple[dict, list[dict], list[dict]]:
    tracked = _git_tracked()
    gt = load_ground_truth()
    nodes = build_decisions(gt)
    edges = [e for n in nodes for e in classify(n, gt, tracked)]
    roll = rollup(nodes, edges, gt, tracked)

    hot = _read(SRC_HOT_LOG)
    loose_re = re.compile(r"^.{0,4}SESSION LOG ENTRY.*$", re.M)
    corpus_files = [SRC_HOT_LOG] + sorted(SRC_LOG_ARCHIVE.glob("session-log-*.md"))
    loose_total = sum(len(loose_re.findall(_read(p))) for p in corpus_files)
    parsed = sum(1 for n in nodes if n["type"] == "DECISION_SESSION")
    marker_forms = {
        "hot_canonical_emoji": len(re.findall("^\U0001F4DD SESSION LOG ENTRY[ \t]*$", hot, re.M)),
        "hot_bare": len(re.findall("^SESSION LOG ENTRY[ \t]*$", hot, re.M)),
        "corpus_markers_loose_scan": loose_total,
        "corpus_entries_parsed": parsed,
        "parse_coverage_pct": round(100.0 * parsed / loose_total, 2) if loose_total else 0.0,
        "unparsed": loose_total - parsed,
        "note": "rotate_session_log.py:_MARKER_RE recognises only the emoji / '??' forms; the "
                "bare form is invisible to it. Reported, not fixed (separate authorized turn). "
                "`unparsed` is the shortfall between a loose marker scan and strict entry "
                "parsing - reported so any dropped decision is visible, never silently absorbed.",
    }

    payload = {
        "schema": "research_dag_provenance/1",
        "generated_for_date": date_str,
        "generated_by": "scripts/analysis/research_dag_provenance.py",
        "authority": "research/governance only - grants no production authority (CLAUDE.md 6.5)",
        "doctrine": "GAPS ARE THE RESULT. No edge is backfilled, guessed, or filled from a "
                    "sibling artifact. UNKNOWN means the record does not carry the link.",
        "rule_classes": RULE_CLASS,
        "slots": list(SLOTS),
        "evidence_prefixes": list(EVIDENCE_PREFIXES),
        "eras": [{"start": s, "label": l} for s, l in ERAS],
        "session_log_marker_forms": marker_forms,
        "family_registry_provenance_stance": gt["families_meta"],
        "rollup": roll,
        "nodes": [{k: v for k, v in n.items() if not k.startswith("_")} for n in nodes],
        "edges": edges,
    }
    return payload, nodes, edges


def main() -> int:
    ap = argparse.ArgumentParser(description="Research provenance DAG extractor (read-only).")
    ap.add_argument("--date", default=_date.today().isoformat(),
                    help="Artifact date; dated files are immutable and this is the payload's "
                         "only clock (so two runs on the same date are byte-identical)")
    ap.add_argument("--json", metavar="PATH", help="Override the dated artifact path")
    ap.add_argument("--no-pointer", action="store_true", help="Skip the LATEST pointer write")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    payload, nodes, edges = build_payload(a.date)
    body = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    out = Path(a.json) if a.json else OUT_DIR / ("research_dag_provenance-%s.json" % a.date)
    out.write_text(body, encoding="utf-8")
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()

    roll = payload["rollup"]
    if not a.no_pointer:
        OUT_LATEST_PTR.write_text(json.dumps({
            "path": str(out.relative_to(ROOT)).replace("\\", "/"),
            "generated_for_date": a.date, "payload_sha256": sha,
            "decisions": roll["totals"]["decisions"], "edges": roll["totals"]["edges"],
            "pct": roll["totals"]["pct"],
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if not a.quiet:
        t = roll["totals"]
        print("decisions=%d edges=%d conservation=%s" % (
            t["decisions"], t["edges"], t["conservation_ok"]))
        print("OVERALL  EXPLICIT %.2f%%  INFERRED %.2f%%  UNKNOWN %.2f%%" % (
            t["pct"]["EXPLICIT"], t["pct"]["INFERRED"], t["pct"]["UNKNOWN"]))
        for s in SLOTS:
            p = roll["per_slot"][s]["pct"]
            print("  %-34s E %6.2f%%  I %6.2f%%  U %6.2f%%" % (
                s, p["EXPLICIT"], p["INFERRED"], p["UNKNOWN"]))
        print("wrote %s  sha256=%s" % (out.relative_to(ROOT), sha[:16]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
