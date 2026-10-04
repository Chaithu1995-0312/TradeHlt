from __future__ import annotations
import ast, hashlib, json, re, shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\Tradelatest")
BATCH = "probes_extraction_replay_excursion_2026-09-14"
ARCH = ROOT / "archive" / BATCH
stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
ARCH.mkdir(parents=True, exist_ok=True)
rows = ["timestamp_utc,action,original_path,archive_path,sha256_before,reason"]

def archive_copy(rel: str) -> None:
    src, dst = ROOT / rel, ARCH / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    data = src.read_bytes()
    dst.write_bytes(data)
    rows.append(f"{stamp},copied_before_edit,{rel},archive/{BATCH}/{rel},{hashlib.sha256(data).hexdigest()},pre-edit snapshot")

def note_edit(rel: str, reason: str) -> None:
    rows.append(f"{stamp},edited_in_place,{rel},archive/{BATCH}/{rel},{hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()},{reason}")

def note_created(rel: str) -> None:
    rows.append(f"{stamp},created,{rel},,{hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()},new shared probes module")

def grab(src: str, names: set[str]) -> dict[str, str]:
    tree = ast.parse(src)
    lines = src.splitlines(True)
    found: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in names:
                    found[t.id] = "".join(lines[node.lineno - 1 : node.end_lineno])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in names:
            found[node.name] = "".join(lines[node.lineno - 1 : node.end_lineno])
    return found

# --- excursion ---
archive_copy("scripts/analysis/p001_excursion_probe.py")
p001_src = (ROOT / "scripts/analysis/p001_excursion_probe.py").read_text(encoding="utf-8")
bits = grab(p001_src, {"UNREACHABLE_ATR_MULT", "_Bar", "excursion"})
assert set(bits) == {"UNREACHABLE_ATR_MULT", "_Bar", "excursion"}, bits.keys()

header = (
    '"""Uncapped ATR excursion via governed forward_walk (from p001 probe)."""\n'
    "from __future__ import annotations\n\n"
    "from typing import Optional\n\n"
    "from research.contracts import Signal\n"
    "from research.measurement.forward_walk import forward_walk\n\n"
)
body = bits["UNREACHABLE_ATR_MULT"] + "\n\n" + bits["_Bar"].replace("class _Bar:", "class Bar:", 1).replace("_Bar(", "Bar(", 1)
# fix __init__ class body only used Bar once at class def - methods don't use _Bar(
body = bits["_Bar"]
body = body.replace("class _Bar:", "class Bar:", 1)
exc_fn = bits["excursion"].replace("_Bar(", "Bar(")
exc_mod = header + bits["UNREACHABLE_ATR_MULT"] + "\n\n" + body + "\n\n" + exc_fn + "\n\n_Bar = Bar\n"
(ROOT / "src/research/probes/excursion.py").write_text(exc_mod, encoding="utf-8")
note_created("src/research/probes/excursion.py")
print("wrote excursion")

# shim p001
p001 = p001_src
if "from research.probes.excursion import" not in p001:
    p001 = p001.replace(
        "from research.measurement.forward_walk import forward_walk  # noqa: E402\n",
        "from research.measurement.forward_walk import forward_walk  # noqa: E402\n"
        "from research.probes.excursion import (  # noqa: E402\n"
        "    UNREACHABLE_ATR_MULT,\n"
        "    Bar as _Bar,\n"
        "    excursion,\n"
        ")\n",
        1,
    )
    p001 = re.sub(r"\nUNREACHABLE_ATR_MULT = 1e9\n", "\n# UNREACHABLE_ATR_MULT from research.probes.excursion\n", p001, count=1)
    p001 = re.sub(r"\nclass _Bar:.*?(?=\n\n# ──|\n\ndef |\n\n# load_)", "\n\n# _Bar from research.probes.excursion\n\n", p001, count=1, flags=re.S)
    if "class _Bar" in p001:
        p001 = re.sub(r"\nclass _Bar:.*?(?=\n\ndef |\n\n# )", "\n\n# _Bar from research.probes.excursion\n\n", p001, count=1, flags=re.S)
    p001 = re.sub(
        r"\ndef excursion\(corpus: list\[dict\], i: int, atr: float, horizon: int\) -> Optional\[dict\]:.*?(?=\n\ndef )",
        "\n\n# excursion from research.probes.excursion\n\n",
        p001,
        count=1,
        flags=re.S,
    )
    (ROOT / "scripts/analysis/p001_excursion_probe.py").write_text(p001, encoding="utf-8")
    note_edit("scripts/analysis/p001_excursion_probe.py", "re-export excursion")
    print("shimmed p001", "class _Bar left?" , "class _Bar" in p001, "def excursion" in p001)

# --- phase1_replay ---
archive_copy("scripts/analysis/phase1_resolver_replay_evidence.py")
ev_src = (ROOT / "scripts/analysis/phase1_resolver_replay_evidence.py").read_text(encoding="utf-8")
need = {
    "HORIZON", "STRIDE", "PF_CAP", "MIN_N_LABEL", "CASES_RUBRIC",
    "_Capture", "_dir_to_long_short", "_tb_to_long_short", "_install_collapse_capture",
    "_load_trend_bias_by_ts", "_normalize_ts", "_call_case", "run_shadow_collapse_replay",
}
ev_bits = grab(ev_src, need)
missing = need - set(ev_bits)
assert not missing, missing

replay_parts = [
    '"""Phase-1 resolver replay helpers shared by evidence + sample_acquisition CLIs."""',
    "from __future__ import annotations",
    "",
    "from pathlib import Path",
    "from typing import Any, Optional",
    "",
    "from config_layer.crt_engine_v2 import StateMachine",
    "from config_layer.production_config import PROD_VERSION, load_prod_config_from_registry",
    "from research.costs import ComponentCostModel",
    "from research.probes.costs_path import net_r as net_r_timeout",
    "from research.probes.scoreboard import profit_factor, scoreboard_row",
    "from runtime.backtest_v2 import BacktestConfig, BacktestRunner, CandleLoader, MultiInstrumentRunner",
    "",
]
for k in ["HORIZON", "STRIDE", "PF_CAP", "MIN_N_LABEL", "CASES_RUBRIC"]:
    replay_parts.append(ev_bits[k])
    replay_parts.append("")
for k in [
    "_Capture", "_dir_to_long_short", "_tb_to_long_short", "_install_collapse_capture",
    "_load_trend_bias_by_ts", "_normalize_ts", "_call_case", "run_shadow_collapse_replay",
]:
    replay_parts.append(ev_bits[k])
    replay_parts.append("")
replay_parts.append(
    """
def net_r(corpus, bar_index, direction, atr, cost_model, horizon: int = HORIZON):
    return net_r_timeout(corpus, bar_index, direction, atr, cost_model, horizon)


def make_scoreboard_row(name, net_rs, *, n_universe, n_eligible):
    return scoreboard_row(
        name,
        net_rs,
        n_universe=n_universe,
        n_eligible=n_eligible,
        min_n_label=MIN_N_LABEL,
        pf_cap=PF_CAP,
    )


dir_to_long_short = _dir_to_long_short
tb_to_long_short = _tb_to_long_short
install_collapse_capture = _install_collapse_capture
load_trend_bias_by_ts = _load_trend_bias_by_ts
normalize_ts = _normalize_ts
call_case = _call_case
_net_r = net_r
_scoreboard_row = make_scoreboard_row
_profit_factor = profit_factor
""".strip()
)
rp = ROOT / "src/research/probes/phase1_replay.py"
rp.write_text("\n".join(replay_parts) + "\n", encoding="utf-8")
note_created("src/research/probes/phase1_replay.py")
print("wrote phase1_replay")

archive_copy("src/research/probes/__init__.py")
(ROOT / "src/research/probes/__init__.py").write_text(
    '"""Shared research probe helpers."""\n'
    "from research.probes.corpus import join_and_verify, load_corpus, load_live_rows\n"
    "from research.probes.governance import FORBIDDEN_KEYS, assert_no_claim_keys\n"
    "from research.probes.horizon import close_at_horizon\n"
    "from research.probes.costs_path import load_cost_model, net_r\n"
    "from research.probes.persistence import walk_episode_chain\n"
    "from research.probes.scoreboard import profit_factor, scoreboard_row\n"
    "from research.probes.excursion import UNREACHABLE_ATR_MULT, Bar, excursion\n"
    "from research.probes import phase1_replay\n\n"
    "__all__ = [\n"
    '    "load_corpus", "load_live_rows", "join_and_verify",\n'
    '    "FORBIDDEN_KEYS", "assert_no_claim_keys",\n'
    '    "close_at_horizon", "load_cost_model", "net_r",\n'
    '    "walk_episode_chain", "profit_factor", "scoreboard_row",\n'
    '    "UNREACHABLE_ATR_MULT", "Bar", "excursion",\n'
    '    "phase1_replay",\n'
    "]\n",
    encoding="utf-8",
)
note_edit("src/research/probes/__init__.py", "export excursion + phase1_replay")

archive_copy("src/research/probes/shadow_collapse.py")
(ROOT / "src/research/probes/shadow_collapse.py").write_text(
    '"""SHADOW to EXP collapse capture — re-exports phase1_replay helpers."""\n'
    "from __future__ import annotations\n\n"
    "from research.probes.phase1_replay import (\n"
    "    install_collapse_capture,\n"
    "    run_shadow_collapse_replay,\n"
    ")\n\n"
    '__all__ = ["install_collapse_capture", "run_shadow_collapse_replay"]\n',
    encoding="utf-8",
)
note_edit("src/research/probes/shadow_collapse.py", "re-export phase1_replay")

# sample_acquisition
archive_copy("scripts/analysis/phase1_resolver_replay_sample_acquisition.py")
sa = (ROOT / "scripts/analysis/phase1_resolver_replay_sample_acquisition.py").read_text(encoding="utf-8")
sa = re.sub(r"import importlib\.util\n", "", sa, count=1)
sa2, n = re.subn(
    r"\n_EV = ROOT.*?\n_spec\.loader\.exec_module\(ev\)\n(?:from research\.probes\.corpus import load_corpus  # noqa: E402\nfrom research\.probes\.governance import assert_no_claim_keys  # noqa: E402\n)?",
    "\nfrom research.probes.corpus import load_corpus  # noqa: E402\n"
    "from research.probes.governance import assert_no_claim_keys  # noqa: E402\n"
    "from research.probes import phase1_replay as ev  # noqa: E402\n",
    sa,
    count=1,
    flags=re.S,
)
print("sa n", n)
if n != 1:
    raise SystemExit("sample_acquisition replace failed")
sa = sa2
# dedupe probe imports
while sa.count("from research.probes.corpus import load_corpus  # noqa: E402\n") > 1:
    sa = sa.replace("from research.probes.corpus import load_corpus  # noqa: E402\n", "", 1)
    sa = "from research.probes.corpus import load_corpus  # noqa: E402\n" + sa
while sa.count("from research.probes.governance import assert_no_claim_keys  # noqa: E402\n") > 1:
    # keep first near ev import
    first = sa.find("from research.probes.governance import assert_no_claim_keys  # noqa: E402\n")
    second = sa.find("from research.probes.governance import assert_no_claim_keys  # noqa: E402\n", first + 1)
    if second < 0:
        break
    sa = sa[:second] + sa[second + len("from research.probes.governance import assert_no_claim_keys  # noqa: E402\n") :]
if "importlib" in sa or "spec_from_file" in sa:
    raise SystemExit("sa still importlib")
(ROOT / "scripts/analysis/phase1_resolver_replay_sample_acquisition.py").write_text(sa, encoding="utf-8")
note_edit("scripts/analysis/phase1_resolver_replay_sample_acquisition.py", "phase1_replay; no importlib")
print("migrated sa")

# atlas
archive_copy("scripts/analysis/build_decision_atlas.py")
atlas = (ROOT / "scripts/analysis/build_decision_atlas.py").read_text(encoding="utf-8")
atlas = re.sub(r"import importlib\.util\n", "", atlas, count=1)
atlas2, n = re.subn(
    r"\n# excursion\(\) still on p001 until forward_walk extraction\.\n_P001 = ROOT.*?\n_spec\.loader\.exec_module\(p001\)\n",
    "\nfrom research.probes.excursion import excursion  # noqa: E402\n",
    atlas,
    count=1,
    flags=re.S,
)
print("atlas n", n)
if n != 1:
    raise SystemExit("atlas replace failed")
atlas = atlas2.replace("p001.excursion(", "excursion(")
if "p001." in atlas or "spec_from_file" in atlas:
    raise SystemExit("atlas leftover")
(ROOT / "scripts/analysis/build_decision_atlas.py").write_text(atlas, encoding="utf-8")
note_edit("scripts/analysis/build_decision_atlas.py", "excursion from probes; no importlib")
print("migrated atlas")

# shadow census
archive_copy("scripts/analysis/phase1_shadow_create_economic_census.py")
sh = (ROOT / "scripts/analysis/phase1_shadow_create_economic_census.py").read_text(encoding="utf-8")
sh = re.sub(r"import importlib\.util\n", "", sh, count=1)
sh2, n = re.subn(
    r"\n# excursion\(\) still on p001 until forward_walk extraction\.\n_P001 = _ROOT.*?\n_ps\.loader\.exec_module\(p001\)\n",
    "\nfrom research.probes.excursion import excursion  # noqa: E402\n",
    sh,
    count=1,
    flags=re.S,
)
print("shadow n", n)
if n != 1:
    raise SystemExit("shadow replace failed")
sh = sh2.replace("p001.excursion(", "excursion(")
if "p001." in sh or "spec_from_file" in sh:
    raise SystemExit("shadow leftover " + str([l for l in sh.splitlines() if "p001." in l or "spec_from_file" in l][:5]))
(ROOT / "scripts/analysis/phase1_shadow_create_economic_census.py").write_text(sh, encoding="utf-8")
note_edit("scripts/analysis/phase1_shadow_create_economic_census.py", "excursion from probes; no importlib")
print("migrated shadow")

(ARCH / "MANIFEST.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
(ARCH / "MANIFEST.md").write_text(f"# {BATCH}\nUTC {stamp}\nNo deletes.\n", encoding="utf-8")
idx = ROOT / "archive/ARCHIVE_INDEX.md"
t = idx.read_text(encoding="utf-8")
if BATCH not in t:
    idx.write_text(t + f"\n## {BATCH}\n- UTC: {stamp}\n- Manifest: archive/{BATCH}/MANIFEST.csv\n- Deletes: none\n", encoding="utf-8")
manifests = ROOT / "docs/governance/build_manifests"
impact = {
    "change_id": "CH-probes-extract-replay-excursion-2026-09-14",
    "when_utc": stamp,
    "archive_batch": f"archive/{BATCH}/",
    "created": ["src/research/probes/excursion.py", "src/research/probes/phase1_replay.py"],
    "importlib_removed_from": [
        "scripts/analysis/phase1_resolver_replay_sample_acquisition.py",
        "scripts/analysis/build_decision_atlas.py",
        "scripts/analysis/phase1_shadow_create_economic_census.py",
    ],
    "completion_status": "COMPLETE_LOCAL",
}
(manifests / "CH-probes-extract-replay-excursion-2026-09-14.impact.json").write_text(json.dumps(impact, indent=2) + "\n", encoding="utf-8")
(manifests / "CH-probes-extract-replay-excursion-2026-09-14.completion.json").write_text(
    json.dumps({"change_id": impact["change_id"], "completion_status": "COMPLETE_LOCAL", "declared_files": impact["created"] + impact["importlib_removed_from"]}, indent=2) + "\n",
    encoding="utf-8",
)
audit = ROOT / "docs/research/probes_extraction_audit_2026-09-14.md"
a = audit.read_text(encoding="utf-8")
if BATCH not in a:
    audit.write_text(
        a
        + f"\n## Batch 5 — replay helpers + excursion (`{BATCH}`)\n"
        "Created `research.probes.excursion` + `research.probes.phase1_replay`. "
        "Dropped importlib from sample_acquisition, build_decision_atlas, phase1_shadow_create_economic_census.\n",
        encoding="utf-8",
    )
print("DONE")