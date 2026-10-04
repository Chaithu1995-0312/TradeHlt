"""P1 Parameter Usage Audit — read-site discovery (measurement only)."""
from __future__ import annotations
import json, re, os
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

ROOT = Path(r"D:\Tradelatest")
WORK = ROOT / "multi_llm" / "parameter_usage_audit"
WORK.mkdir(parents=True, exist_ok=True)

# Candidate YAML sources for declared thresholds
YAML_CANDIDATES = [
    ROOT / "configs" / "formulas" / "market_crt_states.yaml",
    ROOT / "configs" / "formulas" / "market_ontology.yaml",
    ROOT / "configs" / "formulas" / "crt_state_identity.yaml",
    ROOT / "configs" / "formulas" / "crt_resolver_links.yaml",
]

# Also scan for market_crt / threshold yaml by name
for p in (ROOT / "configs").rglob("*.yaml"):
    if any(x in p.name.lower() for x in ("crt", "threshold", "market_state", "gate")):
        if p not in YAML_CANDIDATES:
            YAML_CANDIDATES.append(p)

PARAM_HINTS = [
    "htf_candles_per_range", "max_sweep_age_candles", "max_displacement_age_candles",
    "max_expansion_age_candles", "max_expansion_age_hours", "gap_reset_minutes",
    "pending_displacement_ttl_candles", "range_atr_period", "soft_conf_max_candles",
    "body_ratio_min", "atr_multiplier_min", "atr_min_displacement",
    "expansion_atr_min_distance", "expansion_atr_is_relative", "continuous_disp_to_expansion",
    "retest_depth_max", "retest_atr_depth_fraction",
    "gate_weight_intent", "gate_weight_vol", "gate_weight_liquidity", "gate_weight_structure",
    "gate_approval_threshold", "breakout_disp_threshold",
    "risk_percent", "max_risk_per_trade_pct", "sl_atr_buffer",
    "swing_window", "double_sweep_window", "rsi_overbought", "rsi_oversold",
    "allowed_sessions", "session_windows", "bias_gate_mode",
    "per_trade_investment_inr", "total_capital_inr", "initial_capital",
]

# Extract keys from yaml thresholds blocks (simple regex, no full YAML parse dependency issues)
key_re = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$")
declared: dict[str, list[dict]] = defaultdict(list)

for ypath in YAML_CANDIDATES:
    if not ypath.exists():
        continue
    try:
        text = ypath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        continue
    in_thresholds = False
    thresh_indent = None
    for i, line in enumerate(text.splitlines(), 1):
        if re.match(r"^\s*thresholds\s*:", line) or re.match(r"^\s*threshold_refs\s*:", line):
            in_thresholds = True
            thresh_indent = len(line) - len(line.lstrip(" "))
            block = "thresholds" if "thresholds" in line and "threshold_refs" not in line else "threshold_refs"
            continue
        if in_thresholds:
            if line.strip() and not line.strip().startswith("#"):
                cur_indent = len(line) - len(line.lstrip(" "))
                if cur_indent <= thresh_indent and re.match(r"^[A-Za-z_]", line.lstrip()):
                    # left the block
                    in_thresholds = False
                else:
                    m = key_re.match(line)
                    if m:
                        name = m.group(2)
                        val = m.group(3).split("#")[0].strip()
                        declared[name].append({
                            "file": str(ypath.relative_to(ROOT)).replace("\\", "/"),
                            "line": i,
                            "block": block if 'block' in dir() else "thresholds",
                            "value": val,
                        })
            # track block name properly
        # also harvest PARAM_HINTS anywhere in yaml
        for hint in PARAM_HINTS:
            if re.search(rf"\b{re.escape(hint)}\b\s*:", line):
                m = key_re.match(line)
                if m and m.group(2) == hint:
                    val = m.group(3).split("#")[0].strip()
                    # avoid dup same file:line
                    entry = {"file": str(ypath.relative_to(ROOT)).replace("\\", "/"), "line": i, "block": "anywhere", "value": val}
                    if entry not in declared[hint]:
                        declared[hint].append(entry)

# Seed inventory with hints even if not found in yaml
for h in PARAM_HINTS:
    declared.setdefault(h, [])

# P1: grep read sites in src/, scripts/, tools/ (py only)
SEARCH_ROOTS = [ROOT / "src", ROOT / "scripts", ROOT / "tools"]
skip_parts = {".venv", "venv", "__pycache__", ".git", "node_modules", "logs", "results"}
reads: dict[str, list[dict]] = defaultdict(list)
fallbacks: dict[str, list[dict]] = defaultdict(list)

# patterns for .get("name", default) and ["name"] and thr["name"]
get_pat_cache = {}
def get_pats(name: str):
    if name not in get_pat_cache:
        get_pat_cache[name] = [
            re.compile(rf"""\.get\(\s*["']{re.escape(name)}["']\s*,\s*([^)]+)\)"""),
            re.compile(rf"""\[['\"]{re.escape(name)}['\"]\]"""),
            re.compile(rf"""getattr\([^,]+,\s*['\"]{re.escape(name)}['\"]"""),
            re.compile(rf"""\b{re.escape(name)}\b"""),
        ]
    return get_pat_cache[name]

py_files = []
for sr in SEARCH_ROOTS:
    if not sr.exists():
        continue
    for p in sr.rglob("*.py"):
        if any(part in skip_parts for part in p.parts):
            continue
        py_files.append(p)

print(f"scanning {len(py_files)} py files for {len(declared)} params...")

for p in py_files:
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    rel = str(p.relative_to(ROOT)).replace("\\", "/")
    lines = text.splitlines()
    for name in list(declared.keys()):
        # cheap prefilter
        if name not in text:
            continue
        get_re, idx_re, getattr_re, word_re = get_pats(name)
        for i, line in enumerate(lines, 1):
            if name not in line:
                continue
            # skip comments-only mentions lightly
            stripped = line.strip()
            kind = "mention"
            fb = None
            gm = get_re.search(line)
            if gm:
                kind = "get_with_fallback"
                fb = gm.group(1).strip()
                fallbacks[name].append({"file": rel, "line": i, "fallback": fb, "snippet": stripped[:180]})
            elif idx_re.search(line) or getattr_re.search(line):
                kind = "direct_read"
            elif word_re.search(line):
                kind = "mention"
            else:
                continue
            reads[name].append({"file": rel, "line": i, "kind": kind, "snippet": stripped[:180]})

# Classify preliminary (P1 only — no P3)
inventory = []
for name in sorted(declared.keys()):
    decl = declared[name]
    rs = reads[name]
    fbs = fallbacks[name]
    # unique read sites (file:line)
    uniq = {(r["file"], r["line"], r["kind"]) for r in rs}
    direct = [r for r in rs if r["kind"] in ("direct_read", "get_with_fallback")]
    # declared values
    decl_vals = sorted({d["value"] for d in decl if d.get("value")})
    fb_vals = sorted({f["fallback"] for f in fbs})
    mismatch = []
    for dv in decl_vals:
        for fv in fb_vals:
            # normalize quotes
            dvs = dv.strip().strip("'\"")
            fvs = fv.strip().strip("'\"")
            if dvs and fvs and dvs != fvs and not (dvs.replace(".0","") == fvs.replace(".0","")):
                mismatch.append({"declared": dv, "fallback": fv})
    if not decl and not direct:
        status = "unreferenced_hint"
    elif not direct:
        status = "dead_candidate"  # declared or mentioned but no clear read
    elif mismatch:
        status = "duplicated_fallback_mismatch"
    elif direct:
        status = "read"
    else:
        status = "unknown"
    inventory.append({
        "name": name,
        "declared_sites": decl,
        "declared_values": decl_vals,
        "read_sites": [{"file": f, "line": ln, "kind": k} for f, ln, k in sorted(uniq)],
        "read_count": len(uniq),
        "direct_read_count": len({(r["file"], r["line"]) for r in direct}),
        "fallback_sites": fbs,
        "fallback_values": fb_vals,
        "declared_vs_fallback_mismatch": mismatch,
        "p1_status": status,
    })

summary = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "scope": "P1 read-site discovery (+ P2 mismatch from .get fallbacks). Measurement only. No param changes.",
    "py_files_scanned": len(py_files),
    "yaml_sources": [str(p.relative_to(ROOT)).replace("\\", "/") for p in YAML_CANDIDATES if p.exists()],
    "param_count": len(inventory),
    "by_status": {},
}
for row in inventory:
    summary["by_status"][row["p1_status"]] = summary["by_status"].get(row["p1_status"], 0) + 1

report = {"summary": summary, "parameters": inventory}
(WORK / "parameter_usage_audit_p1.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

# Markdown
lines = []
lines.append("# Parameter Usage Audit — P1 (read sites)")
lines.append("")
lines.append(f"> Generated: {summary['generated_at']}")
lines.append("> **Measurement only.** No parameter/threshold/behavior changes. P3 replay not run yet.")
lines.append("")
lines.append("## Summary")
lines.append("")
lines.append(f"- Python files scanned: **{summary['py_files_scanned']}**")
lines.append(f"- Parameters inventoried: **{summary['param_count']}**")
lines.append("- By P1 status:")
for k, v in sorted(summary["by_status"].items()):
    lines.append(f"  - `{k}`: {v}")
lines.append("")
lines.append("## YAML sources")
for s in summary["yaml_sources"]:
    lines.append(f"- `{s}`")
lines.append("")
lines.append("## Drift class notes (pending P3)")
lines.append("- **Shadowed** (binds but upstream limiter preempts) — needs P3; not asserted in P1.")
lines.append("- **Duplicated** — flagged when YAML declared value ≠ `.get(..., fallback)`.")
lines.append("- **Dead candidate** — no direct_read/get_with_fallback site found in src/scripts/tools.")
lines.append("")
lines.append("## Parameters")
lines.append("")
for row in inventory:
    lines.append(f"### `{row['name']}`")
    lines.append(f"- P1 status: **{row['p1_status']}**")
    lines.append(f"- Declared values: `{row['declared_values'] or '—'}`")
    lines.append(f"- Fallback values: `{row['fallback_values'] or '—'}`")
    if row["declared_vs_fallback_mismatch"]:
        lines.append(f"- **Mismatch:** `{row['declared_vs_fallback_mismatch']}`")
    lines.append(f"- Read sites ({row['read_count']}; direct={row['direct_read_count']}):")
    if not row["read_sites"]:
        lines.append("  - _(none)_")
    else:
        for r in row["read_sites"][:25]:
            lines.append(f"  - `{r['file']}:{r['line']}` ({r['kind']})")
        if len(row["read_sites"]) > 25:
            lines.append(f"  - … +{len(row['read_sites'])-25} more")
    lines.append("")

md_path = WORK / "parameter_usage_audit_p1.md"
# also copy stub into docs/architecture
arch = ROOT / "docs" / "architecture" / "parameter_usage_audit.md"
md_path.write_text("\n".join(lines), encoding="utf-8")
arch.write_text("\n".join(lines), encoding="utf-8")
(WORK / "parameter_usage_audit_p1.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
# machine-readable authority map path promised in story
(ROOT / "docs" / "architecture" / "parameter_usage_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

print(json.dumps(summary, indent=2))
# print mismatches and dead
print("\n=== MISMATCHES ===")
for row in inventory:
    if row["declared_vs_fallback_mismatch"]:
        print(row["name"], row["declared_vs_fallback_mismatch"])
print("\n=== DEAD CANDIDATES ===")
for row in inventory:
    if row["p1_status"] == "dead_candidate":
        print(row["name"], "declared=", row["declared_values"])
