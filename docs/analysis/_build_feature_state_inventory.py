"""One-shot builder: feature + state inventory workbook (2026-08-19).

Reads live authorities (feature_schema.py text, market_ontology.yaml,
market_crt_states.yaml, state_identity.py, htf_state.py). Writes a dated
xlsx. Not a production script — do not register in SITS unless promoted.
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.series import DataPoint
from openpyxl.drawing.fill import PatternFillProperties, ColorChoice
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.drawing.line import LineProperties
from openpyxl.chart.marker import DataPoint as _unused  # noqa: F401 — keep import surface stable

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs" / "analysis" / "feature-identity-state-inventory-2026-08-19.xlsx"

NAVY = "1B365D"
TEAL = "0F6C6C"
GOLD = "C4A35A"
SLATE = "334155"
WHITE = "FFFFFF"
ICE = "F4F7FB"
MINT = "E8F5F0"
AMBER = "FFF4D6"
ROSE = "FDECEC"
LILAC = "F3EEF8"
ROW_ALT = "F8FAFC"

FILL_NAVY = PatternFill("solid", fgColor=NAVY)
FILL_TEAL = PatternFill("solid", fgColor=TEAL)
FILL_GOLD = PatternFill("solid", fgColor=GOLD)
FILL_SLATE = PatternFill("solid", fgColor=SLATE)
FILL_ICE = PatternFill("solid", fgColor=ICE)
FILL_MINT = PatternFill("solid", fgColor=MINT)
FILL_AMBER = PatternFill("solid", fgColor=AMBER)
FILL_ROSE = PatternFill("solid", fgColor=ROSE)
FILL_LILAC = PatternFill("solid", fgColor=LILAC)
FILL_ALT = PatternFill("solid", fgColor=ROW_ALT)
FILL_WHITE = PatternFill("solid", fgColor=WHITE)

FONT_TITLE = Font(name="Calibri", size=18, bold=True, color=NAVY)
FONT_H = Font(name="Calibri", size=11, bold=True, color=WHITE)
FONT_SUB = Font(name="Calibri", size=12, bold=True, color=TEAL)
FONT_BODY = Font(name="Calibri", size=10, color="1E293B")
FONT_MUTED = Font(name="Calibri", size=9, italic=True, color="64748B")
FONT_KPI = Font(name="Calibri", size=22, bold=True, color=NAVY)
FONT_KPI_LBL = Font(name="Calibri", size=9, bold=True, color=SLATE)

THIN = Border(
    left=Side(style="thin", color="D0D7DE"),
    right=Side(style="thin", color="D0D7DE"),
    top=Side(style="thin", color="D0D7DE"),
    bottom=Side(style="thin", color="D0D7DE"),
)
WRAP = Alignment(wrap_text=True, vertical="center")
WRAP_TOP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(wrap_text=True, vertical="center", horizontal="center")


def _load_canonical() -> list[str]:
    src = (REPO / "src" / "features" / "feature_schema.py").read_text(encoding="utf-8")
    m = re.search(r"CANONICAL_FEATURES = tuple\(\[(.*?)\]\)", src, re.S)
    if not m:
        raise SystemExit("CANONICAL_FEATURES not found")
    names = re.findall(r'"([^"]+)"', m.group(1))
    if len(names) != 48:
        raise SystemExit(f"expected 48 canonical names, got {len(names)}")
    return names


def _schema_meta(index: int, name: str) -> tuple[str, str]:
    """Return (schema_version_introduced, note)."""
    if name in {"macd_hist_raw", "macd_hist_z"}:
        return "v4.0", "MACD histogram split: one v3 slot became two named quantities"
    if name == "candle_range":
        return "v2.0 slot / v4.0 name", "Rename of wick_size; math always high-low"
    if name == "session":
        return "v2.0 slot / v4.0 domain", "Name unchanged; domain 3-value partition → 5-value window"
    if 0 <= index <= 17:
        return "v2.0", "Present since original 35-dim vector"
    if 20 <= index <= 35:
        return "v2.0", "v2 tail; index +1 after v4 MACD split"
    if 36 <= index <= 38:
        return "v3.0", "Added with liquidity / volume-spike promotion"
    if 39 <= index <= 47:
        return "v5.0", "SMC primitive (CH-htfcrt-parent-candle-smc-v1)"
    return "unknown", ""


def _walk_fm(obj, acc, section="", key=""):
    if isinstance(obj, dict):
        fid = obj.get("id")
        if isinstance(fid, str) and re.fullmatch(r"FM-\d+", fid):
            acc.append((fid, section, key, obj))
        for k, v in obj.items():
            if k in {
                "primitives",
                "feature_compositions",
                "derived_metrics",
                "rolling_indicators",
                "temporal_context",
                "structural_states",
                "migration_candidates",
            }:
                if isinstance(v, dict):
                    for nk, nv in v.items():
                        _walk_fm(nv, acc, k, nk)
                else:
                    _walk_fm(v, acc, k, key)
            else:
                _walk_fm(v, acc, section, key)
    elif isinstance(obj, list):
        for item in obj:
            _walk_fm(item, acc, section, key)


def _join(xs) -> str:
    if xs is None:
        return ""
    if isinstance(xs, (list, tuple)):
        return ", ".join(str(x) for x in xs if x not in (None, [], ""))
    return str(xs)


def _state_names(states) -> str:
    if not states:
        return ""
    names = []
    for s in states:
        if isinstance(s, dict) and s.get("name"):
            names.append(str(s["name"]))
        elif isinstance(s, str):
            names.append(s)
    return ", ".join(names)


def _first_line(text) -> str:
    if not text:
        return ""
    return " ".join(str(text).split())


def extract():
    names = _load_canonical()
    ont = yaml.safe_load((REPO / "configs" / "formulas" / "market_ontology.yaml").read_text(encoding="utf-8"))
    crt_yaml = yaml.safe_load((REPO / "configs" / "formulas" / "market_crt_states.yaml").read_text(encoding="utf-8"))

    sys.path.insert(0, str(REPO / "src"))
    from config_layer.state_identity import (  # noqa: WPS433
        CRTState,
        Direction,
        EXECUTION_TIMEFRAME_STATES,
        PARENT_TIMEFRAME_STATES,
        RejectReason,
        VALID_TRANSITIONS,
    )
    from config_layer.htf_state import HTFState, ObjectiveStatus  # noqa: WPS433
    from execution.execution_intent_v1_0 import (  # noqa: WPS433
        IntentState,
        TerminationReason,
        VALID_TRANSITIONS as INTENT_TRANSITIONS,
    )

    fm_rows = []
    seen = {}
    raw = []
    _walk_fm(ont, raw)
    for fid, section, key, spec in raw:
        if section == "migration_candidates":
            continue
        if fid in seen:
            continue
        seen[fid] = True
        lineage = spec.get("lineage") or {}
        tax = spec.get("taxonomy") or {}
        sem = spec.get("semantics") or {}
        states = spec.get("states") or []
        vk = lineage.get("vector_key") or spec.get("vector_key") or ""
        if isinstance(vk, list):
            vk = vk[0] if vk else ""
        vi = lineage.get("vector_index")
        if isinstance(vi, list):
            vi = ""
        fm_rows.append(
            {
                "id": fid,
                "key": key,
                "section": section,
                "lifecycle": spec.get("lifecycle") or "",
                "computation_class": spec.get("computation_class") or "",
                "category": tax.get("category") or "",
                "knowledge_class": tax.get("knowledge_class") or "",
                "formula": _first_line(spec.get("formula")),
                "impl": spec.get("impl") or "",
                "depends_on": _join(spec.get("depends_on")),
                "vector_key": vk if vk not in ([], None) else "",
                "vector_index": vi if vi not in ([], None) else "",
                "description": _first_line((sem.get("description") if isinstance(sem, dict) else "") or spec.get("description")),
                "why": _first_line(sem.get("why_it_exists") if isinstance(sem, dict) else ""),
                "states": states if isinstance(states, list) else [],
                "state_names": _state_names(states),
                "state_count": len(states) if isinstance(states, list) else 0,
                "active": spec.get("active", ""),
            }
        )
    fm_rows.sort(key=lambda r: r["id"])
    if len(fm_rows) != 65:
        raise SystemExit(f"expected 65 unique FM ids (ex-migration_candidates), got {len(fm_rows)}")

    by_vector: dict[str, list[dict]] = defaultdict(list)
    for r in fm_rows:
        if r["vector_key"]:
            by_vector[r["vector_key"]].append(r)

    vector_rows = []
    for i, name in enumerate(names):
        ver, note = _schema_meta(i, name)
        fms = by_vector.get(name, [])
        vector_rows.append(
            {
                "index": i,
                "name": name,
                "schema": ver,
                "note": note,
                "fm_ids": ", ".join(f["id"] for f in fms),
                "fm_count": len(fms),
                "section": ", ".join(sorted({f["section"] for f in fms})) if fms else "base_input / unbound",
                "lifecycle": ", ".join(sorted({f["lifecycle"] for f in fms if f["lifecycle"]})) if fms else "",
                "category": ", ".join(sorted({f["category"] for f in fms if f["category"]})) if fms else "",
                "formula": " | ".join(f["formula"] for f in fms if f["formula"]),
                "state_names": " | ".join(f["state_names"] for f in fms if f["state_names"]),
                "has_states": "YES" if any(f["state_count"] for f in fms) else "NO",
                "description": " | ".join(f["description"] for f in fms if f["description"]),
            }
        )

    # Feature-level discrete states from ontology
    feature_state_rows = []
    for r in fm_rows:
        for s in r["states"]:
            if not isinstance(s, dict):
                continue
            feature_state_rows.append(
                {
                    "source": f"ontology.{r['section']}",
                    "owner_id": r["id"],
                    "feature": r["key"],
                    "vector_key": r["vector_key"],
                    "state": s.get("name") or "",
                    "value": s.get("value") if s.get("value") is not None else "",
                    "condition": _first_line(s.get("condition")),
                    "description": _first_line(s.get("description")),
                    "family": "feature discrete state",
                }
            )

    # CRT yaml feature_states (declared vocabularies)
    yaml_feature_states = crt_yaml.get("feature_states") or {}
    for feat, states in yaml_feature_states.items():
        for st in states or []:
            feature_state_rows.append(
                {
                    "source": "market_crt_states.yaml feature_states",
                    "owner_id": "",
                    "feature": feat,
                    "vector_key": feat if feat in names else "",
                    "state": st,
                    "value": "",
                    "condition": "declared vocabulary for CRT resolver predicates",
                    "description": "",
                    "family": "resolver feature-state vocabulary",
                }
            )

    machine_rows = []

    def add_machine(family, name, value, authority, graph, successors, description):
        machine_rows.append(
            {
                "family": family,
                "state": name,
                "value": value,
                "authority": authority,
                "graph": graph,
                "successors": successors,
                "description": description,
            }
        )

    crt_desc = {
        "RANGE": "Default / ground — no active structural event on the M15 execution machine",
        "SHADOW_PENDING": "Cross-window displacement memory; awaiting confirming sweep",
        "SWEEP": "Liquidity taken and closed back inside the founding range",
        "DISPLACEMENT": "Directional impulse away from the swept side (F-074)",
        "EXPANSION": "Post-displacement extension",
        "EXPIRED": "EXPANSION TTL exceeded — one-bar soft archive before RANGE",
        "RETEST": "Price returned to the displacement origin / EMA band",
        "EXECUTION": "Trade opened after soft confirmation",
        "RESOLUTION": "Trade closed (TP/SL); one bar then RANGE",
        "RANGE_C1": "Parent-timeframe C1 — reference candle whose H/L become h_ref/l_ref",
        "MANIPULATION_C2": "Parent-timeframe C2 — sweeps C1 and closes back inside",
        "DISTRIBUTION_C3": "Parent-timeframe C3 — directional impulse away from swept side",
    }
    for st in CRTState:
        succs = VALID_TRANSITIONS.get(st, [])
        if st in PARENT_TIMEFRAME_STATES:
            graph = "parent-timeframe (disjoint C1/C2/C3)"
        else:
            graph = "M15 execution (9-state)"
        add_machine(
            "CRTState",
            st.name,
            st.name,
            "src/config_layer/state_identity.py · CRTState",
            graph,
            ", ".join(s.name for s in succs),
            crt_desc.get(st.name, ""),
        )

    htf_desc = {
        "UNKNOWN": "Classifier could not assign a posture",
        "EXPANSION": "Parent range large vs prior closed parent — expansion posture",
        "ACCUMULATION": "Parent range small vs prior — accumulation posture",
        "DISTRIBUTION": "Sujan large-in-range / look-for-reversal posture (NOT DISTRIBUTION_C3)",
        "REVERSAL": "Reversal posture vs prior parent",
    }
    for st in HTFState:
        add_machine(
            "HTFState",
            st.name,
            st.value,
            "src/config_layer/htf_state.py · HTFState",
            "orthogonal to CRTState (F-077 / F-078)",
            "",
            htf_desc.get(st.name, ""),
        )

    obj_desc = {
        "NONE": "No open parent objective",
        "EXISTS": "Completed parent narrative still has an open objective",
        "ACHIEVED": "Objective reached",
        "INVALIDATED": "Objective invalidated",
    }
    for st in ObjectiveStatus:
        add_machine(
            "ObjectiveStatus",
            st.name,
            st.value,
            "src/config_layer/htf_state.py · ObjectiveStatus",
            "derived from ParentCRTTrack.bias + C1 vs last parent close",
            "",
            obj_desc.get(st.name, ""),
        )

    for st in Direction:
        add_machine(
            "Direction",
            st.name,
            st.value,
            "src/config_layer/state_identity.py · Direction",
            "trade / sweep side",
            "",
            "Trade or structural side. NONE is the unset sentinel.",
        )

    rej_desc = {
        "LOW_SCORE": "Score below threshold",
        "OUTSIDE_SESSION": "Outside configured session window",
        "NO_DOUBLE_SWEEP": "Double-sweep confirmation missing",
        "NEWS_FILTER": "News filter active",
        "HIGH_SPREAD": "Spread too high",
        "INVALID_STATE": "Current CRT state is not legal for execution",
    }
    for st in RejectReason:
        add_machine(
            "RejectReason",
            st.name,
            st.value,
            "src/config_layer/state_identity.py · RejectReason",
            "signal rejection (not a CRTState)",
            "",
            rej_desc.get(st.name, ""),
        )

    intent_desc = {
        "PROPOSED": "Intent created, not yet acted",
        "EXECUTED": "Intent filled / acted — terminal",
        "TERMINATED": "Intent ended without fill — terminal",
    }
    for st in IntentState:
        succs = INTENT_TRANSITIONS.get(st, ())
        add_machine(
            "IntentState",
            st.name,
            st.value,
            "src/execution/execution_intent_v1_0.py · IntentState",
            "execution-intent workflow (not CRT)",
            ", ".join(s.name for s in succs) or "(terminal)",
            intent_desc.get(st.name, ""),
        )

    term_desc = {
        "REJECTED": "Human / risk gate declined",
        "EXPIRED": "Signal TTL lapsed before action",
        "REPLACED": "Superseded by a re-proposed intent",
        "CANCELLED": "Withdrawn before execution",
    }
    for st in TerminationReason:
        add_machine(
            "TerminationReason",
            st.name,
            st.value,
            "src/execution/execution_intent_v1_0.py · TerminationReason",
            "reason attached when IntentState=TERMINATED",
            "",
            term_desc.get(st.name, ""),
        )

    # Resolver CRT states from yaml (the 9 declared `states:` plus parent graph keys)
    resolver_rows = []
    for block in crt_yaml.get("states") or []:
        when = block.get("when") or {}
        when_txt = "; ".join(f"{k}={_join(v)}" for k, v in when.items()) if when else "(memory / not feature-detectable)"
        resolver_rows.append(
            {
                "name": block.get("name"),
                "requires_memory": "YES" if block.get("requires_memory") else "NO",
                "when": when_txt,
                "description": _first_line(block.get("description")),
                "notes": _first_line(block.get("notes")),
            }
        )

    file_rows = scan_declaration_files(names, fm_rows, machine_rows, resolver_rows)
    return {
        "names": names,
        "fm_rows": fm_rows,
        "vector_rows": vector_rows,
        "feature_state_rows": feature_state_rows,
        "machine_rows": machine_rows,
        "resolver_rows": resolver_rows,
        "yaml_feature_states": yaml_feature_states,
        "file_rows": file_rows,
    }


# ── file × identity scan (declaration / emission, not every mention) ─────

_IMPL_FILE = (
    ("features.smc.order_block", "src/features/smc/order_block.py"),
    ("features.smc.fvg", "src/features/smc/fvg.py"),
    ("features.smc.breaker", "src/features/smc/breaker.py"),
    ("features.smc.mitigation", "src/features/smc/mitigation.py"),
    ("features.smc.levels", "src/features/smc/levels.py"),
    ("features.smc.choch", "src/features/smc/choch.py"),
    ("features.session_classifier", "src/features/session_classifier.py"),
    ("features.feature_pipeline", "src/features/feature_pipeline.py"),
    ("feature_pipeline", "src/features/feature_pipeline.py"),
    ("candle_math", "src/features/candle_math.py"),
    ("derived_math", "src/features/derived_math.py"),
    ("scoring_engine", "src/engines/scoring_engine.py"),
    ("config_layer.crt_engine_v2", "src/config_layer/crt_engine_v2.py"),
    ("crt_engine_v2", "src/config_layer/crt_engine_v2.py"),
)

_SEARCH_ROOTS = ("src", "configs/formulas")
_SKIP_DIR = {"__pycache__", ".git", "msip_1_verification_package"}
_TEXT_SUFFIX = {".py", ".yaml", ".yml"}


def _rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def _resolve_impl(symbol: str) -> str | None:
    if not symbol:
        return None
    s = str(symbol).strip()
    best = None
    best_len = -1
    for prefix, dest in _IMPL_FILE:
        if s == prefix or s.startswith(prefix + ".") or s.startswith(prefix + " "):
            if len(prefix) > best_len:
                best, best_len = dest, len(prefix)
    return best


def scan_declaration_files(names, fm_rows, machine_rows, resolver_rows):
    """Map each inventory id to files that declare the identity or emit its value.

    Roots: src/ + configs/formulas/ only. Tests, docs, session logs excluded
    so a mention of 'atr' in a comment dump does not count as a declaration.
    """
    fm_by_id = {r["id"]: r for r in fm_rows}
    fm_by_key = {r["key"]: r for r in fm_rows}
    key_to_fm = {}
    for r in fm_rows:
        key_to_fm.setdefault(r["key"], []).append(r["id"])
        if r["vector_key"]:
            key_to_fm.setdefault(r["vector_key"], []).append(r["id"])
    feature_names = set(names) | {r["key"] for r in fm_rows} | {
        r["vector_key"] for r in fm_rows if r["vector_key"]
    }
    # longest names first so macd_hist_raw wins over a hypothetical macd
    feature_sorted = sorted(feature_names, key=len, reverse=True)
    assign_re = re.compile(
        r"""(?:\[\s*['"](%s)['"]\s*\]|\.get\(\s*['"](%s)['"])"""
        % ("|".join(re.escape(n) for n in feature_sorted),
           "|".join(re.escape(n) for n in feature_sorted))
    )
    assign_eq_re = re.compile(
        r"""\[\s*['"](%s)['"]\s*\]\s*="""
        % "|".join(re.escape(n) for n in feature_sorted)
    )
    fm_re = re.compile(r"\b(FM-\d{3})\b")

    family_members = defaultdict(list)
    for row in machine_rows:
        family_members[row["family"]].append(row["state"])
    state_token_re = {}
    for family, members in family_members.items():
        state_token_re[family] = re.compile(
            r"\b" + re.escape(family) + r"\.(" + "|".join(re.escape(m) for m in members) + r")\b"
        )
    yaml_state_re = re.compile(
        r"^  - name:\s+("
        + "|".join(re.escape(r["name"]) for r in resolver_rows if r.get("name"))
        + r")\s*$",
        re.M,
    )

    hits: dict[str, dict] = {}

    def _bucket(rel: str) -> dict:
        b = hits.get(rel)
        if b is None:
            b = {
                "fm": set(),
                "features": set(),
                "states": set(),
                "roles": set(),
            }
            hits[rel] = b
        return b

    def add(rel, *, fm=None, feature=None, state=None, role=None):
        if not rel:
            return
        b = _bucket(rel)
        if fm:
            b["fm"].add(fm)
            row = fm_by_id.get(fm)
            if row:
                if row["key"]:
                    b["features"].add(row["key"])
                if row["vector_key"]:
                    b["features"].add(row["vector_key"])
        if feature:
            b["features"].add(feature)
            for fid in key_to_fm.get(feature, ()):
                b["fm"].add(fid)
        if state:
            b["states"].add(state)
        if role:
            b["roles"].add(role)

    # Authority seeds — these files own the identities even before a scan.
    add("src/features/feature_schema.py", role="IDENTITY")
    for n in names:
        add("src/features/feature_schema.py", feature=n, role="IDENTITY")
    add("configs/formulas/market_ontology.yaml", role="IDENTITY")
    for r in fm_rows:
        add("configs/formulas/market_ontology.yaml", fm=r["id"], feature=r["key"], role="IDENTITY")
        dest = _resolve_impl(r["impl"])
        if dest:
            add(dest, fm=r["id"], feature=r["key"], role="EMITS")
        dest2 = _resolve_impl(r.get("impl") or "")
        # produced_by is not on fm_rows — re-read from key only via impl above
        add(dest2, fm=r["id"], role="EMITS") if dest2 else None
    add("src/config_layer/state_identity.py", role="IDENTITY")
    add("src/config_layer/htf_state.py", role="IDENTITY")
    add("src/execution/execution_intent_v1_0.py", role="IDENTITY")
    add("configs/formulas/market_crt_states.yaml", role="IDENTITY")
    for row in machine_rows:
        if row["family"] == "CRTState":
            add("src/config_layer/state_identity.py", state=f"CRTState.{row['state']}", role="IDENTITY")
        elif row["family"] in {"Direction", "RejectReason"}:
            add("src/config_layer/state_identity.py", state=f"{row['family']}.{row['state']}", role="IDENTITY")
        elif row["family"] in {"HTFState", "ObjectiveStatus"}:
            add("src/config_layer/htf_state.py", state=f"{row['family']}.{row['state']}", role="IDENTITY")
        elif row["family"] in {"IntentState", "TerminationReason"}:
            add("src/execution/execution_intent_v1_0.py", state=f"{row['family']}.{row['state']}", role="IDENTITY")
    for r in resolver_rows:
        add("configs/formulas/market_crt_states.yaml", state=f"CRTResolver.{r['name']}", role="IDENTITY")

    # produced_by from ontology (may differ from impl)
    ont_text = (REPO / "configs" / "formulas" / "market_ontology.yaml").read_text(encoding="utf-8")
    # already have fm_rows.impl; walk produced_by off the live yaml again
    ont = yaml.safe_load(ont_text)
    raw = []
    _walk_fm(ont, raw)
    for fid, _section, key, spec in raw:
        if _section == "migration_candidates":
            continue
        for field in (spec.get("impl"), (spec.get("lineage") or {}).get("produced_by")):
            dest = _resolve_impl(field or "")
            if dest:
                add(dest, fm=fid, feature=key, role="EMITS")

    # Walk files
    for root_name in _SEARCH_ROOTS:
        root = REPO / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in _TEXT_SUFFIX:
                continue
            if any(part in _SKIP_DIR for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            rel = _rel(path)

            for fid in set(fm_re.findall(text)):
                if fid in fm_by_id:
                    # identity line vs mere mention
                    if re.search(r"id:\s*" + re.escape(fid) + r"\b", text):
                        add(rel, fm=fid, role="IDENTITY")
                    elif (
                        "registry" in rel.replace("\\", "/")
                        or assign_eq_re.search(text)
                        or f'"{fid}"' in text
                        or f"'{fid}'" in text
                    ):
                        add(rel, fm=fid, role="EMITS")
                    else:
                        add(rel, fm=fid, role="REFERENCES")

            for m in assign_eq_re.finditer(text):
                add(rel, feature=m.group(1), role="EMITS")

            for family, cre in state_token_re.items():
                for m in cre.finditer(text):
                    token = f"{family}.{m.group(1)}"
                    # assignment / transition target vs comparison
                    start = max(0, m.start() - 40)
                    window = text[start:m.end() + 8]
                    if re.search(r"(?<![!=<>])=(?!=)\s*" + re.escape(m.group(0)), window) or \
                       re.search(r"return\s+" + re.escape(m.group(0)), window):
                        add(rel, state=token, role="EMITS")
                    elif rel.endswith("state_identity.py") or rel.endswith("htf_state.py") or rel.endswith("execution_intent_v1_0.py"):
                        add(rel, state=token, role="IDENTITY")
                    else:
                        add(rel, state=token, role="REFERENCES")

            if path.suffix.lower() in {".yaml", ".yml"}:
                for m in yaml_state_re.finditer(text):
                    add(rel, state=f"CRTResolver.{m.group(1)}", role="IDENTITY")

    rows = []
    for rel, b in hits.items():
        # drop files that only accumulated empty authority seeds
        if not (b["fm"] or b["features"] or b["states"]):
            continue
        fm_sorted = sorted(b["fm"])
        feat_sorted = sorted(b["features"])
        state_sorted = sorted(b["states"])
        pretty_parts = []
        seen_feat = set()
        for fid in fm_sorted:
            row = fm_by_id.get(fid)
            label = fid
            if row:
                label = f"{fid} {row['key']}"
                seen_feat.add(row["key"])
                if row["vector_key"]:
                    seen_feat.add(row["vector_key"])
            pretty_parts.append(label)
        for feat in feat_sorted:
            if feat not in seen_feat:
                pretty_parts.append(feat)
        pretty_parts.extend(state_sorted)
        roles = b["roles"]
        if "IDENTITY" in roles and "EMITS" in roles:
            role = "IDENTITY + EMITS"
        elif "IDENTITY" in roles:
            role = "IDENTITY"
        elif "EMITS" in roles:
            role = "EMITS"
        elif "REFERENCES" in roles:
            role = "REFERENCES"
        else:
            role = ""
        # Prefer declaration/emission files; keep REFERENCES only if they also emit or identify
        # OR if they bind an FM id (user asked to find each id). Keep REFERENCES that have FM ids.
        if role == "REFERENCES" and not fm_sorted:
            continue
        rows.append(
            {
                "filename": rel,
                "features": "; ".join(pretty_parts),
                "count": len(pretty_parts),
                "role": role,
                "fm_ids": ", ".join(fm_sorted),
                "feature_keys": ", ".join(feat_sorted),
                "states": ", ".join(state_sorted),
            }
        )

    def _sort_key(r):
        role_rank = {"IDENTITY + EMITS": 0, "IDENTITY": 1, "EMITS": 2, "REFERENCES": 3}.get(r["role"], 9)
        return (role_rank, -r["count"], r["filename"])

    rows.sort(key=_sort_key)
    return rows


def _header(ws, headers, fill=FILL_NAVY):
    for col, h in enumerate(headers, 1):
        cell = ws.cell(1, col, h)
        cell.font = FONT_H
        cell.fill = fill
        cell.alignment = CENTER
        cell.border = THIN
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    ws.sheet_properties.tabColor = fill.fgColor.rgb if fill.fgColor and fill.fgColor.rgb else NAVY


def _write_rows(ws, rows, keys, fills_for=None):
    for r_i, row in enumerate(rows, 2):
        fill = FILL_ALT if r_i % 2 == 0 else FILL_WHITE
        extra = fills_for(row) if fills_for else None
        if extra:
            fill = extra
        for c, k in enumerate(keys, 1):
            val = row.get(k, "")
            if val is None:
                val = ""
            cell = ws.cell(r_i, c, val)
            cell.font = FONT_BODY
            cell.fill = fill
            cell.border = THIN
            cell.alignment = WRAP
    ws.auto_filter.ref = f"A1:{get_column_letter(len(keys))}{max(1, len(rows) + 1)}"


def _widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _style_kpi(ws, cell_ref, value, label, fill):
    c = ws[cell_ref]
    c.value = value
    c.font = FONT_KPI
    c.fill = fill
    c.alignment = Alignment(horizontal="center", vertical="center")
    c.border = THIN
    lbl = ws.cell(c.row + 1, c.column, label)
    lbl.font = FONT_KPI_LBL
    lbl.alignment = CENTER
    lbl.fill = fill
    lbl.border = THIN


def build(data):
    wb = Workbook()

    # ── Cover ──────────────────────────────────────────────────────────
    cover = wb.active
    cover.title = "Cover"
    cover.sheet_properties.tabColor = NAVY
    cover.sheet_view.showGridLines = False
    cover.merge_cells("B2:H2")
    cover["B2"] = "Feature & State Inventory"
    cover["B2"].font = FONT_TITLE
    cover.merge_cells("B3:H3")
    cover["B3"] = (
        "Point-in-time snapshot 2026-08-19 · extracted from live authorities · "
        "not economic evidence · not CRT CLOSED · not a promotion artifact"
    )
    cover["B3"].font = FONT_MUTED

    n_vec = len(data["vector_rows"])
    n_fm = len(data["fm_rows"])
    n_vec_bound = sum(1 for r in data["fm_rows"] if r["vector_key"] in {v["name"] for v in data["vector_rows"]})
    n_vec_unbound_fm = n_fm - n_vec_bound
    n_vec_no_fm = sum(1 for r in data["vector_rows"] if r["fm_count"] == 0)
    n_feat_states = len(data["feature_state_rows"])
    n_machine = len(data["machine_rows"])
    n_resolver = len(data["resolver_rows"])
    n_yaml_vocab = sum(len(v or []) for v in data["yaml_feature_states"].values())
    ont_state_rows = [r for r in data["feature_state_rows"] if r["family"] == "feature discrete state"]
    n_ont_states = len(ont_state_rows)
    n_fm_with_states = sum(1 for r in data["fm_rows"] if r["state_count"] > 0)

    _style_kpi(cover, "B6", n_vec, "Decision-vector slots", FILL_MINT)
    _style_kpi(cover, "D6", n_fm, "Registered FM identities", FILL_LILAC)
    _style_kpi(cover, "F6", n_machine, "Machine / workflow states", FILL_AMBER)
    _style_kpi(cover, "H6", n_ont_states, "Ontology discrete feature-states", FILL_ICE)
    cover.row_dimensions[6].height = 36
    cover.row_dimensions[7].height = 28
    for col in ("B", "D", "F", "H"):
        cover.column_dimensions[col].width = 16
        cover.merge_cells(f"{col}6:{col}6")

    cover.merge_cells("B9:H9")
    cover["B9"] = "These three numbers are not additive. Do not add 48 + 65 + states."
    cover["B9"].font = Font(name="Calibri", size=11, bold=True, color="9A3412")
    cover["B9"].fill = FILL_AMBER

    bullets = [
        ("What 48 is", "CANONICAL_FEATURES in src/features/feature_schema.py — schema v5.0, CANONICAL_FEATURE_DIM=48. This is the ordered float vector every engine / model is supposed to consume. Hash-invalidating."),
        ("What 65 is", "Unique FM-* identities in configs/formulas/market_ontology.yaml (migration_candidates FM-030/031 duplicates excluded). Registered meaning / math. Many have no vector slot."),
        ("What states are", "Three families: (1) machine states — CRTState 12, HTFState 5, ObjectiveStatus 4, Direction 3, RejectReason 6, IntentState 3, TerminationReason 4; (2) ontology discrete states on FM entries; (3) CRT-resolver feature-state vocabularies in market_crt_states.yaml."),
        ("Join", f"{n_vec - n_vec_no_fm} of 48 vector slots have ≥1 FM identity. {n_vec_no_fm} slots are raw OHLCV / unbound. {n_vec_bound} of 65 FM ids declare a vector_key that is on the 48. {n_vec_unbound_fm} FM ids have no decision-vector slot."),
        ("Lane", "measurement / evidence inventory. Grants no G001, no promotion, no CRT recert."),
        ("Sources", "src/features/feature_schema.py · configs/formulas/market_ontology.yaml · configs/formulas/market_crt_states.yaml · src/config_layer/state_identity.py · src/config_layer/htf_state.py · src/execution/execution_intent_v1_0.py"),
        ("How to read", "Start on Cover → Decision Vector (48) → FM Identities (65) → Feature States → Machine States → CRT Resolver States → Coverage → Files declaring values. Filters on every data sheet."),
    ]
    cover["B11"] = "How to read this workbook"
    cover["B11"].font = FONT_SUB
    cover.merge_cells("B11:H11")
    row = 12
    for title, body in bullets:
        cover.cell(row, 2, title).font = Font(name="Calibri", size=10, bold=True, color=NAVY)
        cover.merge_cells(start_row=row, start_column=3, end_row=row, end_column=8)
        cell = cover.cell(row, 3, body)
        cell.font = FONT_BODY
        cell.alignment = WRAP
        cover.row_dimensions[row].height = 36
        row += 1

    cover["B20"] = "Sheet map"
    cover["B20"].font = FONT_SUB
    cover.merge_cells("B20:H20")
    sheet_map = [
        ("Cover", "This page — counts, disclaimer, sources"),
        ("Decision Vector (48)", "One row per CANONICAL_FEATURES slot, joined to FM ids"),
        ("FM Identities (65)", "One row per unique FM-* identity"),
        ("Feature States", "Every discrete state declared on an FM or in CRT yaml vocabularies"),
        ("Machine States", "CRT / HTF / Objective / Direction / Reject / Intent enums"),
        ("CRT Resolver States", "Declarative when: predicates from market_crt_states.yaml"),
        ("Coverage", "Join table: which of the 48 lack an FM, which of the 65 lack a slot"),
        ("Files declaring values", "filename | features in that file — identity + emission sites under src/ and configs/formulas/"),
    ]
    cover["B21"] = "Sheet"
    cover["C21"] = "Contents"
    cover["B21"].font = FONT_H
    cover["C21"].font = FONT_H
    cover["B21"].fill = FILL_TEAL
    cover["C21"].fill = FILL_TEAL
    cover.merge_cells("C21:H21")
    for i, (name, desc) in enumerate(sheet_map):
        cover.cell(22 + i, 2, name).font = FONT_BODY
        cover.cell(22 + i, 2).fill = FILL_ICE if i % 2 == 0 else FILL_WHITE
        cover.merge_cells(start_row=22 + i, start_column=3, end_row=22 + i, end_column=8)
        cover.cell(22 + i, 3, desc).font = FONT_BODY
        cover.cell(22 + i, 3).fill = FILL_ICE if i % 2 == 0 else FILL_WHITE

    cover.column_dimensions["A"].width = 3
    cover.column_dimensions["B"].width = 28
    cover.column_dimensions["C"].width = 18
    cover.column_dimensions["E"].width = 14
    cover.column_dimensions["G"].width = 14
    cover.column_dimensions["H"].width = 22
    cover.row_dimensions[2].height = 28
    cover.print_title_rows = "1:3"
    cover.page_setup.orientation = "landscape"
    cover.page_setup.fitToPage = True
    cover.page_setup.fitToWidth = 1
    cover.page_setup.fitToHeight = 1
    cover.oddHeader.left.text = "Tradelatest · Feature & State Inventory"
    cover.oddFooter.left.text = "2026-08-19 · observation only"
    cover.oddFooter.right.text = "Page &P of &N"

    # ── Decision vector ────────────────────────────────────────────────
    ws = wb.create_sheet("Decision Vector (48)")
    headers = [
        "Index",
        "Feature name",
        "Schema version",
        "Note",
        "FM id(s)",
        "FM count",
        "Ontology section",
        "Lifecycle",
        "Category",
        "Has discrete states",
        "State names",
        "Formula / identity",
        "Description",
    ]
    keys = [
        "index",
        "name",
        "schema",
        "note",
        "fm_ids",
        "fm_count",
        "section",
        "lifecycle",
        "category",
        "has_states",
        "state_names",
        "formula",
        "description",
    ]
    _header(ws, headers, FILL_NAVY)

    def vec_fill(row):
        if row["fm_count"] == 0:
            return FILL_AMBER
        if str(row["schema"]).startswith("v5"):
            return FILL_LILAC
        return None

    _write_rows(ws, data["vector_rows"], keys, vec_fill)
    _widths(ws, [8, 28, 22, 42, 18, 10, 28, 16, 18, 14, 40, 50, 55])
    ws.row_dimensions[1].height = 22
    for r in range(2, 2 + len(data["vector_rows"])):
        ws.row_dimensions[r].height = 32
    ws.auto_filter.ref = f"A1:M{1 + len(data['vector_rows'])}"
    note = ws.cell(51, 1, "Amber = vector slot with no FM identity (raw OHLCV or unbound). Lilac = v5.0 SMC addition. Filter any column.")
    note.font = FONT_MUTED
    ws.merge_cells("A51:M51")

    # ── FM identities ──────────────────────────────────────────────────
    ws = wb.create_sheet("FM Identities (65)")
    headers = [
        "FM id",
        "Ontology key",
        "Section",
        "Lifecycle",
        "Computation class",
        "Category",
        "Knowledge class",
        "On decision vector?",
        "Vector key",
        "Vector index",
        "State count",
        "State names",
        "Formula",
        "Impl",
        "Depends on",
        "Description",
        "Why it exists",
    ]
    keys = [
        "id",
        "key",
        "section",
        "lifecycle",
        "computation_class",
        "category",
        "knowledge_class",
        "on_vector",
        "vector_key",
        "vector_index",
        "state_count",
        "state_names",
        "formula",
        "impl",
        "depends_on",
        "description",
        "why",
    ]
    vec_names = {r["name"] for r in data["vector_rows"]}
    fm_out = []
    for r in data["fm_rows"]:
        d = dict(r)
        d["on_vector"] = "YES" if d["vector_key"] in vec_names else "NO"
        fm_out.append(d)
    _header(ws, headers, FILL_TEAL)

    def fm_fill(row):
        if row["on_vector"] == "NO":
            return FILL_ROSE
        if row["state_count"]:
            return FILL_MINT
        return None

    _write_rows(ws, fm_out, keys, fm_fill)
    _widths(ws, [10, 28, 22, 16, 18, 16, 14, 16, 26, 12, 12, 36, 48, 36, 28, 50, 50])
    ws.row_dimensions[1].height = 22
    for r in range(2, 2 + len(fm_out)):
        ws.row_dimensions[r].height = 30
    ws.auto_filter.ref = f"A1:Q{1 + len(fm_out)}"
    note = ws.cell(68, 1, "Rose = registered identity with no decision-vector slot. Mint = identity declares discrete states. 65 unique FM ids; FM-030/031 migration_candidates copies excluded.")
    note.font = FONT_MUTED
    ws.merge_cells("A68:Q68")

    # ── Feature states ─────────────────────────────────────────────────
    ws = wb.create_sheet("Feature States")
    headers = [
        "Family",
        "Source",
        "Owner id",
        "Feature / key",
        "Vector key",
        "State name",
        "Value",
        "Condition",
        "Description",
    ]
    keys = [
        "family",
        "source",
        "owner_id",
        "feature",
        "vector_key",
        "state",
        "value",
        "condition",
        "description",
    ]
    _header(ws, headers, FILL_GOLD)
    for col in range(1, 10):
        ws.cell(1, col).font = Font(name="Calibri", size=11, bold=True, color=NAVY)

    def fs_fill(row):
        if row["family"] == "resolver feature-state vocabulary":
            return FILL_AMBER
        return None

    _write_rows(ws, data["feature_state_rows"], keys, fs_fill)
    _widths(ws, [32, 36, 12, 26, 22, 22, 10, 50, 55])
    for r in range(2, 2 + len(data["feature_state_rows"])):
        ws.row_dimensions[r].height = 28
    ws.auto_filter.ref = f"A1:I{1 + len(data['feature_state_rows'])}"
    last = 2 + len(data["feature_state_rows"])
    note = ws.cell(last, 1, "Ontology rows are meaning (what the value is). YAML vocabulary rows are what the CRT resolver is allowed to name in when: predicates. Same English name in both places is a join, not proof they are one identity (FM-058 vs SP-001 is the cautionary case).")
    note.font = FONT_MUTED
    ws.merge_cells(start_row=last, start_column=1, end_row=last, end_column=9)

    # ── Machine states ─────────────────────────────────────────────────
    ws = wb.create_sheet("Machine States")
    headers = [
        "Family",
        "State",
        "Stored value",
        "Code authority",
        "Graph / role",
        "Legal successors",
        "Description",
    ]
    keys = ["family", "state", "value", "authority", "graph", "successors", "description"]
    _header(ws, headers, FILL_SLATE)
    family_fill = {
        "CRTState": FILL_MINT,
        "HTFState": FILL_LILAC,
        "ObjectiveStatus": FILL_ICE,
        "Direction": FILL_WHITE,
        "RejectReason": FILL_AMBER,
        "IntentState": FILL_ROSE,
        "TerminationReason": FILL_ROSE,
    }

    def ms_fill(row):
        return family_fill.get(row["family"])

    _write_rows(ws, data["machine_rows"], keys, ms_fill)
    _widths(ws, [20, 22, 22, 52, 48, 40, 62])
    for r in range(2, 2 + len(data["machine_rows"])):
        ws.row_dimensions[r].height = 30
    ws.auto_filter.ref = f"A1:G{1 + len(data['machine_rows'])}"
    last = 2 + len(data["machine_rows"])
    note = ws.cell(
        last,
        1,
        "CRTState is 12 members (9 M15 + 3 parent, disjoint graphs). HTFState / ObjectiveStatus are a second parent-CRT dimension (F-078), not CRTState members. DISTRIBUTION (HTF) ≠ DISTRIBUTION_C3 (F-077). IntentState is the execution-intent workflow, not a market state.",
    )
    note.font = FONT_MUTED
    ws.merge_cells(start_row=last, start_column=1, end_row=last, end_column=7)

    # ── CRT resolver ───────────────────────────────────────────────────
    ws = wb.create_sheet("CRT Resolver States")
    headers = ["State", "Requires memory", "when: predicates", "Description", "Notes"]
    keys = ["name", "requires_memory", "when", "description", "notes"]
    _header(ws, headers, FILL_TEAL)
    _write_rows(ws, data["resolver_rows"], keys)
    _widths(ws, [18, 16, 70, 50, 70])
    for r in range(2, 2 + len(data["resolver_rows"])):
        ws.row_dimensions[r].height = 48
    ws.auto_filter.ref = f"A1:E{1 + len(data['resolver_rows'])}"
    last = 2 + len(data["resolver_rows"])
    note = ws.cell(
        last,
        1,
        "Declarative shadow resolver (market_crt_states.yaml). CRT engine remains execution authority. Parent C1/C2/C3 appear in this file's valid_transitions for parity with state_identity.py but the resolver does not emit those labels (documentation-only on this path).",
    )
    note.font = FONT_MUTED
    ws.merge_cells(start_row=last, start_column=1, end_row=last, end_column=5)

    # ── Coverage ───────────────────────────────────────────────────────
    ws = wb.create_sheet("Coverage")
    ws.sheet_properties.tabColor = GOLD
    ws["A1"] = "Coverage join"
    ws["A1"].font = FONT_TITLE
    ws.merge_cells("A1:F1")
    ws["A2"] = "Which of the 48 lack an FM identity, and which of the 65 lack a decision-vector slot."
    ws["A2"].font = FONT_MUTED
    ws.merge_cells("A2:F2")

    # summary table for the chart
    ws["A4"] = "Bucket"
    ws["B4"] = "Count"
    for col in (1, 2):
        ws.cell(4, col).font = FONT_H
        ws.cell(4, col).fill = FILL_NAVY
        ws.cell(4, col).alignment = CENTER
    buckets = [
        ("Vector slots (48)", n_vec),
        ("Vector slots with ≥1 FM", n_vec - n_vec_no_fm),
        ("Vector slots with no FM", n_vec_no_fm),
        ("FM identities (65)", n_fm),
        ("FM on the 48-vector", n_vec_bound),
        ("FM off-vector", n_vec_unbound_fm),
        ("FM that declare discrete states", n_fm_with_states),
        ("Ontology discrete state rows", n_ont_states),
        ("YAML resolver vocab values", n_yaml_vocab),
        ("Machine / workflow states", n_machine),
        ("CRT resolver when: states", n_resolver),
    ]
    for i, (label, n) in enumerate(buckets):
        ws.cell(5 + i, 1, label).font = FONT_BODY
        ws.cell(5 + i, 2, n).font = FONT_BODY
        fill = FILL_ALT if i % 2 == 0 else FILL_WHITE
        ws.cell(5 + i, 1).fill = fill
        ws.cell(5 + i, 2).fill = fill
        ws.cell(5 + i, 1).border = THIN
        ws.cell(5 + i, 2).border = THIN

    chart = BarChart()
    chart.type = "bar"
    chart.style = 10
    chart.title = "Inventory counts (not additive)"
    chart.y_axis.title = None
    chart.x_axis.title = None
    data_ref = Reference(ws, min_col=2, min_row=4, max_row=4 + len(buckets))
    cats = Reference(ws, min_col=1, min_row=5, max_row=4 + len(buckets))
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats)
    chart.shape = 4
    chart.legend = None
    chart.dataLabels = DataLabelList()
    chart.dataLabels.showVal = True
    chart.height = 10
    chart.width = 18
    ws.add_chart(chart, "D4")

    # unbound vector slots
    start = 18
    ws.cell(start, 1, "Vector slots with no FM identity").font = FONT_SUB
    ws.merge_cells(start_row=start, start_column=1, end_row=start, end_column=3)
    for col, h in enumerate(["Index", "Feature name", "Why unbound"], 1):
        c = ws.cell(start + 1, col, h)
        c.font = FONT_H
        c.fill = FILL_NAVY
        c.alignment = CENTER
    unbound = [r for r in data["vector_rows"] if r["fm_count"] == 0]
    why = {
        "open": "Raw OHLCV base input — ontology leaf, not an FM",
        "high": "Raw OHLCV base input — ontology leaf, not an FM",
        "low": "Raw OHLCV base input — ontology leaf, not an FM",
        "close": "Raw OHLCV base input — ontology leaf, not an FM",
        "volume": "Raw OHLCV base input — ontology leaf, not an FM",
    }
    for i, r in enumerate(unbound):
        ws.cell(start + 2 + i, 1, r["index"]).font = FONT_BODY
        ws.cell(start + 2 + i, 2, r["name"]).font = FONT_BODY
        ws.cell(start + 2 + i, 3, why.get(r["name"], "No ontology lineage.vector_key points here")).font = FONT_BODY
        for c in range(1, 4):
            ws.cell(start + 2 + i, c).fill = FILL_AMBER
            ws.cell(start + 2 + i, c).border = THIN

    # off-vector FMs
    start2 = start + 3 + len(unbound)
    ws.cell(start2, 1, "FM identities with no decision-vector slot").font = FONT_SUB
    ws.merge_cells(start_row=start2, start_column=1, end_row=start2, end_column=5)
    for col, h in enumerate(["FM id", "Ontology key", "Section", "Declared vector_key", "Why off-vector"], 1):
        c = ws.cell(start2 + 1, col, h)
        c.font = FONT_H
        c.fill = FILL_TEAL
        c.alignment = CENTER
    off = [r for r in fm_out if r["on_vector"] == "NO"]
    for i, r in enumerate(off):
        ws.cell(start2 + 2 + i, 1, r["id"]).font = FONT_BODY
        ws.cell(start2 + 2 + i, 2, r["key"]).font = FONT_BODY
        ws.cell(start2 + 2 + i, 3, r["section"]).font = FONT_BODY
        ws.cell(start2 + 2 + i, 4, r["vector_key"] or "(none)").font = FONT_BODY
        reason = "Registered meaning / correction / engine-only / structural flag — not a CANONICAL_FEATURES name"
        if r["vector_key"] and r["vector_key"] not in vec_names:
            reason = f"Declares vector_key={r['vector_key']!r} which is not a CANONICAL_FEATURES name"
        ws.cell(start2 + 2 + i, 5, reason).font = FONT_BODY
        for c in range(1, 6):
            ws.cell(start2 + 2 + i, c).fill = FILL_ROSE
            ws.cell(start2 + 2 + i, c).border = THIN
            ws.cell(start2 + 2 + i, c).alignment = WRAP
        ws.row_dimensions[start2 + 2 + i].height = 22

    _widths(ws, [36, 28, 22, 26, 62, 18])
    ws.freeze_panes = "A5"

    # ── Files declaring values ─────────────────────────────────────────
    ws = wb.create_sheet("Files declaring values")
    headers = [
        "filename",
        "features in that file",
        "count",
        "role",
        "FM ids",
        "feature keys",
        "states",
    ]
    keys = [
        "filename",
        "features",
        "count",
        "role",
        "fm_ids",
        "feature_keys",
        "states",
    ]
    _header(ws, headers, FILL_NAVY)

    def file_fill(row):
        role = row.get("role") or ""
        if role == "IDENTITY + EMITS":
            return FILL_MINT
        if role == "IDENTITY":
            return FILL_LILAC
        if role == "EMITS":
            return FILL_ICE
        if role == "REFERENCES":
            return FILL_AMBER
        return None

    _write_rows(ws, data["file_rows"], keys, file_fill)
    _widths(ws, [52, 90, 10, 20, 40, 50, 50])
    ws.row_dimensions[1].height = 22
    for r in range(2, 2 + len(data["file_rows"])):
        n = data["file_rows"][r - 2]["count"]
        ws.row_dimensions[r].height = 18 + min(48, 4 * max(1, n // 4))
    ws.auto_filter.ref = f"A1:G{1 + len(data['file_rows'])}"
    last = 2 + len(data["file_rows"])
    note = ws.cell(
        last,
        1,
        "Scope: src/ + configs/formulas/ only. IDENTITY = owns the id (ontology / schema / enum / yaml). "
        "EMITS = assigns the value (df['name']=, CRTState.X =, impl/produced_by). "
        "REFERENCES = file names an FM-id or qualified state without assigning it. "
        "Tests, docs, and session logs are excluded. This is a declaration map, not a consumer census.",
    )
    note.font = FONT_MUTED
    ws.merge_cells(start_row=last, start_column=1, end_row=last, end_column=7)

    # freeze + print on data sheets
    for name in [
        "Decision Vector (48)",
        "FM Identities (65)",
        "Feature States",
        "Machine States",
        "CRT Resolver States",
        "Coverage",
        "Files declaring values",
    ]:
        s = wb[name]
        s.page_setup.orientation = "landscape"
        s.page_setup.fitToPage = True
        s.page_setup.fitToWidth = 1
        s.page_setup.fitToHeight = 0
        s.page_setup.paperSize = s.PAPERSIZE_A4
        s.page_setup.horizontalCentered = True
        s.sheet_properties.pageSetUpPr.fitToPage = True
        s.oddHeader.left.text = f"Tradelatest · {name}"
        s.oddFooter.left.text = "Extracted 2026-08-19 · observation only · not G001"
        s.oddFooter.right.text = "Page &P of &N"
        s.page_setup.leftMargin = 0.4
        s.page_setup.rightMargin = 0.4
        s.page_setup.topMargin = 0.6
        s.page_setup.bottomMargin = 0.5
        s.print_title_rows = "1:1"

    # named ranges for the three headline counts
    from openpyxl.workbook.defined_name import DefinedName

    wb.defined_names.add(DefinedName(name="N_VECTOR_48", attr_text="Cover!$B$6"))
    wb.defined_names.add(DefinedName(name="N_FM_65", attr_text="Cover!$D$6"))
    wb.defined_names.add(DefinedName(name="N_MACHINE_STATES", attr_text="Cover!$F$6"))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    return {
        "path": OUT,
        "n_vec": n_vec,
        "n_fm": n_fm,
        "n_machine": n_machine,
        "n_ont_states": n_ont_states,
        "n_feat_state_rows": n_feat_states,
        "n_vec_no_fm": n_vec_no_fm,
        "n_fm_off": n_vec_unbound_fm,
        "n_resolver": n_resolver,
        "n_declaring_files": len(data["file_rows"]),
    }


if __name__ == "__main__":
    stats = build(extract())
    print("WROTE", stats["path"])
    for k, v in stats.items():
        if k != "path":
            print(f"  {k}={v}")
