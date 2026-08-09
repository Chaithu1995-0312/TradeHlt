"""
config_reachability.py
======================
INFRASTRUCTURE AUDIT (read-only): build a ConfigReachabilityReport for the ACTIVE
production config — classify every tunable key by how the codebase actually consumes it.

Why
    Research built on dead/inert config keys produces false findings ("I tuned X and
    nothing changed" is indistinguishable from "X is never read"). This tool makes the
    config→code wiring explicit and machine-checkable. It is the missing instrument
    flagged by the research-readiness audit (Phase 3); no equivalent existed.

Method (purely static + the real loader's own merge rules — no spine edit)
    - ACTIVE_VERSION + full registry JSON via production_config (Tier-0 truth, §4.0).
    - CRTConfig field set via dataclasses.fields (the keys that physically load).
    - `params` + `crt_engine` keys map 1:1 onto CRTConfig; a key is USED iff the
      CRTConfig attribute is referenced in src/ (live spine) or scripts/ (tooling)
      OUTSIDE the definition files.
    - Other top-level sections are consumed via get_prod_section("<name>"); a section
      is reachable iff that call exists; each in-section key is USED iff its literal
      string is referenced in src/ or scripts/.
    - Corpus = src/ (live spine) + scripts/ (CLI / research / training tooling); tests/
      is deliberately EXCLUDED (test fixtures are not production consumption).
    - SHADOW_ONLY = all references land only in dormant/sidecar modules (F-012).

Classification (per the mission's ConfigReachabilityReport contract)
    Precedence when a key is referenced in several places (highest wins):
      live src/ (non-dormant) > scripts/ (tooling) > dormant src/ only > nowhere.
    READ_AND_USED      key loads AND is referenced by live (non-dormant) src/ code
    TOOLING_ONLY       referenced only by scripts/ (CLI / research / training) — a real
                       consumer, but NOT the live spine (e.g. tuner / dataset builders)
    READ_BUT_INERT     key loads (CRTConfig field / section present) but never referenced
    SHADOW_ONLY        referenced only inside dormant/sidecar modules
    DOC_ONLY           referenced only in docs/ or comments, not executable code
    DEAD               present in config but cannot be consumed (no field, no section load)
    HARDCODED_OVERRIDE *advisory* — needs manual dataflow confirmation (not auto-assigned)
    METADATA           bookkeeping key (version/hash/notes/…), not a tunable

This is a best-effort STATIC analyzer: it reports evidence (the grep hits) alongside
every verdict so a human can confirm. It mutates nothing.

Usage
    python scripts/analysis/config_reachability.py            # writes the report
    python scripts/analysis/config_reachability.py --check    # exit 1 if DEAD keys found
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
_SCRIPTS = _ROOT / "scripts"          # tooling corpus (CLI / research / training)
_CORPUS_ROOTS = (_SRC, _SCRIPTS)      # tests/ deliberately excluded (not consumption)
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import CRTConfig  # noqa: E402
from config_layer.production_config import (  # noqa: E402
    get_active_version,
    get_full_config_dict,
)

# ── Knowledge inputs (kept explicit so the verdicts are auditable) ───────────

# Top-level keys that are bookkeeping, not tunables.
_METADATA_KEYS = {
    "version", "config_id", "created_at", "promoted_at", "schema_version",
    "config_hash", "notes", "validation_summary",
}

# Sections consumed through the CRTConfig load path (not get_prod_section).
#   params + crt_engine  → merged into CRTConfig
#   engine_runner        → resolvers (sessions / breakout threshold)
_LOAD_PATH_SECTIONS = {"params", "crt_engine", "engine_runner"}

# Meta sub-dicts inside crt_engine that are handled by resolvers, NOT CRTConfig fields.
_CRT_META_SUBDICTS = {
    "instrument_overrides", "allowed_sessions_overrides",
    "breakout_disp_threshold_overrides",
}

# Curated HARDCODED_OVERRIDE map — fields the static pass flags READ_BUT_INERT, but
# manual source review confirms a magic-number literal is used INSTEAD of the config
# knob. Tuning such a knob is a silent no-op. Evidence cites are required so the verdict
# is auditable. (Empty since 2026-06-12 R2: bitnet_main_threshold + feature_monitor
# {soft,hard}_drift_z were WIRED to config — they now classify as READ_AND_USED.)
_HARDCODED_OVERRIDES: dict[str, str] = {}

# Curated indirect-consumer NOTES — annotation only, NEVER changes the verdict. For keys
# whose consumption the static literal/attr pass genuinely cannot see (e.g. a whole sub-dict
# passed as a cfg_override without the key ever being named in code). A note here explains
# the intended wiring for a human; it does NOT reclassify a verdict (that needs a real cited
# file:line, which the static pass would already have caught). Keyed "section.key".
# Empty: the one candidate (dataset_integrity.strict_fetch) turned out to have real literal
# consumers — cfg.get("strict_fetch") in scripts/data/fetch_and_verify_{binance,mt5}.py:57/70
# — so it classifies TOOLING_ONLY on its own once scripts/ is in the corpus. No note needed.
_INDIRECT_CONSUMERS: dict[str, str] = {}

# Dormant / sidecar module path fragments (F-012, F-005, topic "dormant" list).
# A reference that lands ONLY here is SHADOW_ONLY, not live consumption.
_DORMANT_FRAGMENTS = (
    "replay_memory", "cognitive_bus", "cognitivebus", "cluster", "hmf",
    "tradenet", "scanner", "execution_loop", "portfolio_alloc",
    "strategies", "feedback", "journal", "monitoring", "uat",
)

_PY_EXCLUDE_DIRS = {".git", ".venv", "venv", "__pycache__", ".claude", "node_modules"}


def _iter_src_py() -> list[Path]:
    """All .py under the corpus roots (src/ + scripts/), minus excluded dirs.

    scripts/ is included so a knob consumed only by CLI/research/training tooling is
    classified TOOLING_ONLY (a real consumer) instead of a false READ_BUT_INERT. tests/
    is NOT a corpus root — test fixtures are not production consumption.
    """
    out: list[Path] = []
    for root in _CORPUS_ROOTS:
        if not root.exists():
            continue
        out.extend(
            p for p in root.rglob("*.py")
            if not any(part in _PY_EXCLUDE_DIRS for part in p.parts)
        )
    return out


def _load_corpus() -> dict[Path, str]:
    corpus: dict[Path, str] = {}
    for p in _iter_src_py():
        try:
            corpus[p] = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    return corpus


def _references(token: str, corpus: dict[Path, str],
                exclude: tuple[str, ...] = ()) -> list[str]:
    """Return rel-paths of src files that reference `token` as a whole word,
    skipping files whose path contains any `exclude` fragment."""
    pat = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(token) + r"(?![A-Za-z0-9_])")
    hits: list[str] = []
    for path, text in corpus.items():
        rel = path.relative_to(_ROOT).as_posix()
        if any(frag in rel for frag in exclude):
            continue
        if pat.search(text):
            hits.append(rel)
    return sorted(hits)


def _attr_refs(token: str, corpus: dict[Path, str]) -> list[str]:
    """Rel-paths of src files using `token` as an ATTRIBUTE access (`.token`).

    For CRTConfig fields, consumption is `cfg.<field>` / `self.config.<field>`. The
    leading dot cleanly excludes the dataclass declaration line (`field: type = ...`,
    no dot) WITHOUT excluding the file — so the engine logic that lives alongside the
    CRTConfig definition in crt_engine_v2.py is correctly counted as a consumer.
    """
    pat = re.compile(r"\." + re.escape(token) + r"(?![A-Za-z0-9_])")
    hits: list[str] = []
    for path, text in corpus.items():
        if pat.search(text):
            hits.append(path.relative_to(_ROOT).as_posix())
    return sorted(hits)


# f-string key bases, e.g. `f"tp1_atr_multiplier_{intent}"` → base "tp1_atr_multiplier_".
# Captures the literal fragment before the first `{`. The real code assigns the f-string
# to a variable then feeds it to getattr, so we capture bases anywhere and scope to files
# that also call getattr (= dynamic attribute dispatch).
_FSTRING_BASE = re.compile(r"""f["']([a-z0-9_]*?_)\{""", re.IGNORECASE)


def _getattr_fstring_bases(corpus: dict[Path, str]) -> dict[str, list[str]]:
    """Map each f-string key-base (ending in '_') → files that use it AND getattr."""
    bases: dict[str, list[str]] = {}
    for path, text in corpus.items():
        if "getattr" not in text:
            continue
        rel = path.relative_to(_ROOT).as_posix()
        for m in _FSTRING_BASE.finditer(text):
            base = m.group(1)
            if len(base) >= 6:                       # avoid spuriously short bases
                bases.setdefault(base, []).append(rel)
    return {b: sorted(set(v)) for b, v in bases.items()}


def _dynamic_family_refs(token: str, bases: dict[str, list[str]]) -> list[str]:
    """A CRTConfig field is dynamically consumed if its name starts with any
    getattr f-string base (so `tp1_atr_multiplier_liq_sweep` matches base
    `tp1_atr_multiplier_` regardless of how many underscores the suffix has)."""
    for base, files in bases.items():
        if token.startswith(base):
            return files
    return []


def _string_literal_refs(token: str, corpus: dict[Path, str]) -> list[str]:
    """Rel-paths of src files where `token` appears as a quoted string literal.

    This is accessor-agnostic: it catches get_prod_section aliases, dict access
    (full_cfg["section"]), and from_prod_config(cfg["section"]) patterns alike —
    the literal section/key name must appear in code regardless of how it is read.
    """
    pat = re.compile(r"""['"]""" + re.escape(token) + r"""['"]""")
    hits: list[str] = []
    for path, text in corpus.items():
        if pat.search(text):
            hits.append(path.relative_to(_ROOT).as_posix())
    return sorted(hits)


def _is_dormant(rel: str) -> bool:
    low = rel.lower()
    return any(frag in low for frag in _DORMANT_FRAGMENTS)


def _is_tooling(rel: str) -> bool:
    """A reference living under scripts/ = CLI / research / training tooling (not spine)."""
    return rel.startswith("scripts/")


def _classify_refs(hits: list[str]) -> str:
    """Given the files that reference a token, derive the verdict by precedence:
    live src/ (non-dormant) > scripts/ (tooling) > dormant src/ only > nowhere.

    A knob read by the live spine is READ_AND_USED even if tooling also reads it; a knob
    read only by a real CLI/training script is TOOLING_ONLY (more alive than a sidecar-only
    knob); a knob read only inside dormant/sidecar modules is SHADOW_ONLY; none = INERT.
    """
    if not hits:
        return "READ_BUT_INERT"
    live_src = [h for h in hits if not _is_tooling(h) and not _is_dormant(h)]
    if live_src:
        return "READ_AND_USED"
    if any(_is_tooling(h) for h in hits):
        return "TOOLING_ONLY"
    return "SHADOW_ONLY"          # remaining hits are all dormant src/


def build_report() -> dict:
    version = get_active_version()
    cfg = get_full_config_dict(version)
    crt_fields = {f.name for f in dataclasses.fields(CRTConfig)}
    corpus = _load_corpus()
    getattr_bases = _getattr_fstring_bases(corpus)

    # Which sections are reachable? A section is loaded if its name appears as a
    # string literal anywhere in src/ — accessor-agnostic (covers get_prod_section
    # aliases, full_cfg["section"] dict access, and from_prod_config patterns).
    section_loaded: dict[str, list[str]] = {}
    for section in cfg:
        section_loaded[section] = _string_literal_refs(section, corpus)

    keys: list[dict] = []

    def add(section: str, key: str, verdict: str, evidence, note: str = "") -> None:
        # curated, manually-verified hardcoded-override reclassification
        if key in _HARDCODED_OVERRIDES and verdict in ("READ_BUT_INERT", "DEAD"):
            verdict = "HARDCODED_OVERRIDE"
            note = _HARDCODED_OVERRIDES[key]
        # curated indirect-consumer NOTE — annotation only, never changes the verdict
        ck = f"{section}.{key}"
        if ck in _INDIRECT_CONSUMERS and not note:
            note = _INDIRECT_CONSUMERS[ck]
        keys.append({
            "section": section, "key": key, "verdict": verdict,
            "evidence": evidence if isinstance(evidence, list) else [evidence],
            "note": note,
        })

    for section, value in cfg.items():
        # ── metadata top-level keys ─────────────────────────────────────────
        if section in _METADATA_KEYS:
            add(section, "<section>", "METADATA", [], "bookkeeping, not a tunable")
            continue

        # ── CRTConfig load-path sections (params / crt_engine) ──────────────
        if section in ("params", "crt_engine") and isinstance(value, dict):
            for key, _ in value.items():
                if key in _CRT_META_SUBDICTS:
                    hits = _references(key, corpus, exclude=("crt_engine_v2.py",))
                    add(section, key, _classify_refs(hits) if hits else "READ_BUT_INERT",
                        hits, "resolver-handled meta sub-dict")
                    continue
                if key in crt_fields:
                    # field loads; is the attribute (`.field`) consumed anywhere?
                    # Attribute-style match excludes the declaration line itself.
                    hits = _attr_refs(key, corpus)
                    if hits:
                        add(section, key, _classify_refs(hits), hits)
                    else:
                        # no static attr access → try dynamic getattr dispatch,
                        # then a literal string read (getattr(cfg, "field")).
                        dyn = _dynamic_family_refs(key, getattr_bases)
                        if dyn:
                            add(section, key, _classify_refs(dyn), dyn,
                                "consumed via dynamic getattr() dispatch")
                        else:
                            lit = _string_literal_refs(key, corpus)
                            if lit:
                                add(section, key, _classify_refs(lit), lit,
                                    "read as string-literal getattr key")
                            else:
                                add(section, key, "READ_BUT_INERT", [],
                                    "loads into CRTConfig but never consumed")
                else:
                    add(section, key, "DEAD", [],
                        "not a CRTConfig field — stripped/ignored at load")
            continue

        # ── engine_runner (resolvers in production_config ARE consumers) ────
        if section == "engine_runner" and isinstance(value, dict):
            for key, _ in value.items():
                hits = _string_literal_refs(key, corpus)
                add(section, key, _classify_refs(hits), hits)
            continue

        # ── all other dict sections: reachable iff the section name appears as
        #    a string literal in src/; per-key consumption via key string literal ─
        if isinstance(value, dict):
            sec_load = section_loaded.get(section, [])
            if not sec_load:
                add(section, "<section>", "DEAD", [],
                    "section name never referenced as a string literal in src/")
                for key in value:
                    add(section, key, "DEAD", [], "parent section never loaded")
                continue
            for key, _ in value.items():
                hits = _string_literal_refs(key, corpus)
                add(section, key, _classify_refs(hits), hits)
        else:
            # scalar top-level non-metadata key
            hits = _string_literal_refs(section, corpus)
            add(section, "<scalar>", _classify_refs(hits), hits)

    # ── summary ─────────────────────────────────────────────────────────────
    summary: dict[str, int] = {}
    for k in keys:
        summary[k["verdict"]] = summary.get(k["verdict"], 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "active_version": version,
        "crtconfig_field_count": len(crt_fields),
        "section_loaded_via_get_prod_section": {
            s: v for s, v in section_loaded.items() if v
        },
        "summary": summary,
        "keys": keys,
    }


def build_summary(report: dict) -> dict:
    """The STABLE semantic subset of a report — the L3 golden surface (drift detection).

    Excludes everything volatile: generated_at, evidence paths, key ordering, prose. Two
    reports with the same build_summary() are semantically equivalent even if their bytes
    (timestamp / notes) differ. Used by tests/test_reachability_golden.py — a golden that
    DETECTS truth changes; it never DEFINES truth (see docs/research-readiness/README.md
    Test-Authority Ladder). Accepts either a fresh build_report() dict or a committed
    config-reachability-report.json loaded from disk.
    """
    keys = report.get("keys", [])
    def _named(verdict: str) -> list[str]:
        return sorted(f"{k['section']}.{k['key']}" for k in keys if k["verdict"] == verdict)
    return {
        "active_version": report.get("active_version"),
        "verdict_counts": dict(report.get("summary", {})),
        "dead_keys": _named("DEAD"),
        "tooling_only_keys": _named("TOOLING_ONLY"),
    }


def render_md(report: dict) -> str:
    lines = [
        "# Config Reachability Report",
        "",
        f"> Generated `{report['generated_at']}` · ACTIVE_VERSION = "
        f"`{report['active_version']}` · branch-scoped (CLAUDE.md §4.0).",
        "> Auto-generated by `scripts/analysis/config_reachability.py` — re-run to refresh.",
        "",
        "## Verdict summary",
        "",
        "| Verdict | Count |",
        "|---|---|",
    ]
    for verdict in ("READ_AND_USED", "TOOLING_ONLY", "READ_BUT_INERT", "SHADOW_ONLY",
                    "DOC_ONLY", "DEAD", "HARDCODED_OVERRIDE", "METADATA"):
        if verdict in report["summary"]:
            lines.append(f"| {verdict} | {report['summary'][verdict]} |")
    lines += [
        "",
        "**Legend** — READ_AND_USED: loads and consumed by live src/ code · TOOLING_ONLY: "
        "consumed only by scripts/ (CLI / research / training) — a real consumer, not the "
        "live spine · READ_BUT_INERT: loads but never referenced · SHADOW_ONLY: only "
        "dormant/sidecar code reads it (F-012) · DEAD: cannot be consumed · METADATA: "
        "bookkeeping. HARDCODED_OVERRIDE is advisory and requires manual dataflow "
        "confirmation (not auto-assigned).",
        "",
        "## Per-key verdicts",
        "",
        "| Section | Key | Verdict | Evidence (first ref) | Note |",
        "|---|---|---|---|---|",
    ]
    for k in report["keys"]:
        ev = k["evidence"][0] if k["evidence"] else "—"
        n_more = len(k["evidence"]) - 1
        ev_str = f"`{ev}`" + (f" (+{n_more})" if n_more > 0 else "")
        lines.append(
            f"| {k['section']} | `{k['key']}` | {k['verdict']} | {ev_str} | {k['note']} |"
        )
    # Flag the inert / dead for quick scanning
    flagged = [k for k in report["keys"]
               if k["verdict"] in ("READ_BUT_INERT", "DEAD", "SHADOW_ONLY")]
    lines += ["", "## Flagged (inert / dead / shadow)", ""]
    if flagged:
        for k in flagged:
            lines.append(f"- **{k['verdict']}** `{k['section']}.{k['key']}` — {k['note'] or 'no live reference found'}")
    else:
        lines.append("_None._")
    # ── Confidence & limitations (travels with the artifact; §6.5 Authority Ladder) ──
    lines += [
        "",
        "## Confidence & limitations",
        "",
        "This is a **best-effort STATIC analyzer** (string-literal + attribute matching over "
        "the src/ + scripts/ corpus — no dataflow). Read the verdicts at their true confidence:",
        "",
        "- **DEAD = structurally decidable → Certain.** A key with no CRTConfig field and no "
        "section-literal load genuinely cannot be consumed. `--check` gates on this.",
        "- **READ_AND_USED → referenced is Likely, *consumed in a decision* is only Possible.** "
        "A literal match proves the name appears in live code, not that its value influences an "
        "outcome (it may be logged, shadowed by a hardcoded value, or read-then-discarded).",
        "- **TOOLING_ONLY / SHADOW_ONLY / READ_BUT_INERT → advisory.** TOOLING_ONLY = a real "
        "consumer but outside the spine (tuner / dataset builders); INERT here means *no literal "
        "reference in src/+scripts/*, NOT provably dead — confirm via the evidence column and the "
        "curated notes before treating any as removable.",
        "",
        "**Scope:** scans `src/` (live spine) + `scripts/` (tooling); `tests/` is excluded. "
        "String-literal matching can over-count (same-named unrelated strings) and can miss "
        "keys consumed only as a whole-dict cfg_override (see curated notes).",
        "",
        "**§6.5 caveat — GREEN certifies plumbing, not correctness.** 0 DEAD + no link-rot means "
        "nothing is structurally orphaned; it says NOTHING about whether a knob behaves correctly "
        "or carries economic authority (*tunable ≠ authority*). Authority is earned only by "
        "demonstrated ΔG001, never by appearing here.",
    ]
    lines.append("")
    return "\n".join(lines)


def build_graph(report: dict) -> dict:
    """Config-key -> consumer-file graph (target-strategy-architecture.md §13 item9 /
    §14.H "generated config->consumer graph"). A thin re-projection of the SAME
    evidence `build_report()` already resolved — no new analysis, no new corpus scan.

    Node ids are namespaced so config keys and file paths never collide:
      "cfg:<section>.<key>"   — a config key
      "file:<path>"           — a consumer file (evidence entry)
    Edges are directed key -> file ("this file reads this key"), one per
    (key, evidence-file) pair, deduplicated.
    """
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    seen_edges: set[tuple[str, str]] = set()

    for row in report["keys"]:
        key_id = f"cfg:{row['section']}.{row['key']}"
        if key_id not in nodes:
            nodes[key_id] = {
                "id": key_id, "type": "config_key",
                "section": row["section"], "key": row["key"],
                "verdict": row["verdict"],
            }
        for ev in row["evidence"]:
            file_id = f"file:{ev}"
            if file_id not in nodes:
                nodes[file_id] = {"id": file_id, "type": "file", "path": ev}
            edge_key = (key_id, file_id)
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                edges.append({"from": key_id, "to": file_id})

    return {
        "generated_at":   report["generated_at"],
        "active_version": report["active_version"],
        "source":         "scripts/analysis/config_reachability.py --graph "
                           "(re-projection of build_report()'s evidence — no new scan)",
        "node_count":     len(nodes),
        "edge_count":     len(edges),
        "nodes":          list(nodes.values()),
        "edges":          edges,
    }


def render_graph_md(graph: dict) -> str:
    by_file: dict[str, list[str]] = {}
    for e in graph["edges"]:
        by_file.setdefault(e["to"], []).append(e["from"])

    lines = [
        "# Config -> Consumer Graph",
        "",
        f"> Generated `{graph['generated_at']}` · ACTIVE_VERSION = `{graph['active_version']}`.",
        "> Auto-generated by `scripts/analysis/config_reachability.py --graph` — re-run to "
        "refresh. Re-projection of config-reachability-report.json's evidence; not a new scan.",
        "",
        f"{graph['node_count']} nodes ({sum(1 for n in graph['nodes'] if n['type'] == 'config_key')} "
        f"config keys, {sum(1 for n in graph['nodes'] if n['type'] == 'file')} consumer files), "
        f"{graph['edge_count']} edges.",
        "",
        "## Consumer file -> config keys it reads",
        "",
    ]
    for file_id in sorted(by_file):
        path = file_id[len("file:"):]
        keys = sorted(k[len("cfg:"):] for k in by_file[file_id])
        lines.append(f"- `{path}`")
        for k in keys:
            lines.append(f"  - {k}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Config reachability analyzer (read-only).")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any DEAD key is found (CI guard)")
    ap.add_argument("--out-dir", default="docs/research-readiness")
    ap.add_argument("--graph", action="store_true",
                    help="also emit the config->consumer graph (§13 item9 / §14.H) to "
                         "docs/architecture/config-consumer-graph.generated.{json,md}")
    args = ap.parse_args()

    report = build_report()
    out_dir = _ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "config-reachability-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / "config-reachability-report.md").write_text(
        render_md(report), encoding="utf-8")

    print(f"ACTIVE_VERSION = {report['active_version']}")
    for verdict, n in sorted(report["summary"].items()):
        print(f"  {verdict:<18} {n}")
    print(f"Report → {args.out_dir}/config-reachability-report.{{json,md}}")

    if args.graph:
        graph = build_graph(report)
        graph_dir = _ROOT / "docs" / "architecture"
        graph_dir.mkdir(parents=True, exist_ok=True)
        (graph_dir / "config-consumer-graph.generated.json").write_text(
            json.dumps(graph, indent=2), encoding="utf-8")
        (graph_dir / "config-consumer-graph.generated.md").write_text(
            render_graph_md(graph), encoding="utf-8")
        print(f"Graph → docs/architecture/config-consumer-graph.generated.{{json,md}} "
              f"({graph['node_count']} nodes, {graph['edge_count']} edges)")

    if args.check:
        dead = [k for k in report["keys"] if k["verdict"] == "DEAD"]
        if dead:
            print(f"\nDEAD keys ({len(dead)}):")
            for k in dead:
                print(f"  {k['section']}.{k['key']}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
