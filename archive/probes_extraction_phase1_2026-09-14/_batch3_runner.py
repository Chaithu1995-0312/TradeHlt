from __future__ import annotations
import hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\Tradelatest")
BATCH = "probes_extraction_batch3_2026-09-14"
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

# corpus extend
archive_copy("src/research/probes/corpus.py")
old_corpus = (ROOT/"src/research/probes/corpus.py").read_text(encoding="utf-8")
if "def load_live_rows" not in old_corpus:
    # pull exact bodies from archived/live p001
    p001 = (ROOT/"scripts/analysis/p001_excursion_probe.py").read_text(encoding="utf-8")
    # if already shimmed, get from archive phase1
    src_p001 = ROOT/"archive/probes_extraction_phase1_2026-09-14/scripts/analysis/p001_excursion_probe.py"
    text = src_p001.read_text(encoding="utf-8") if src_p001.exists() else p001
    import ast
    def grab(src, name):
        tree=ast.parse(src); lines=src.splitlines(True)
        for node in tree.body:
            if getattr(node,"name",None)==name:
                return "".join(lines[node.lineno-1:node.end_lineno])
        raise SystemExit(f"missing {name}")
    live = grab(text, "load_live_rows")
    join = grab(text, "join_and_verify")
    new = old_corpus.rstrip()+"\n\n"+live+"\n\n"+join+"\n"
    if "import json" not in new:
        new = new.replace("import csv\n", "import csv\nimport json\n", 1)
    (ROOT/"src/research/probes/corpus.py").write_text(new, encoding="utf-8")
    note_edit("src/research/probes/corpus.py", "added load_live_rows + join_and_verify")
    print("extended corpus")
else:
    print("corpus already has load_live_rows")

# persistence
pers = ROOT/"src/research/probes/persistence.py"
if not pers.exists() or "def walk_episode_chain" not in pers.read_text(encoding="utf-8"):
    spp_arch = ROOT/"scripts/analysis/sweep_state_persistence_probe.py"
    # prefer pre-edit if we already archived in this run later; use live for grab before shim
    import ast
    src = spp_arch.read_text(encoding="utf-8")
    if "from research.probes.persistence import walk_episode_chain" in src:
        # already shimmed somehow; use batch archive or reconstruct from known body
        walk = '''def walk_episode_chain(episodes: list[dict], start_k: int, horizon: int) -> dict:
    """episodes[start_k] is the SWEEP episode itself. Walk forward summing `bars`."""
    cum = 0
    lag_disp = lag_exp = lag_range = None
    k = start_k + 1
    n = len(episodes)
    while k < n and cum < horizon:
        ep = episodes[k]
        cum += ep["bars"]
        if lag_disp is None and ep["state"] == "DISPLACEMENT":
            lag_disp = cum
        elif lag_disp is not None and lag_exp is None and ep["state"] == "EXPANSION":
            lag_exp = cum
        if ep["state"] == "RANGE":
            lag_range = cum
            break
        if ep.get("right_censored"):
            break
        k += 1
    reached_progress = lag_disp is not None
    return {
        "reached_displacement": lag_disp is not None and lag_disp <= horizon,
        "lag_to_displacement": lag_disp if (lag_disp is not None and lag_disp <= horizon) else None,
        "reached_expansion": lag_exp is not None and lag_exp <= horizon,
        "lag_to_expansion": lag_exp if (lag_exp is not None and lag_exp <= horizon) else None,
        "reverted_never_progressed": (lag_range is not None and lag_range <= horizon and not reached_progress),
        "lag_to_reversion": (lag_range if (lag_range is not None and lag_range <= horizon and not reached_progress) else None),
        "right_censored_in_window": k < n and bool(episodes[k].get("right_censored")) and cum <= horizon,
    }
'''
    else:
        tree=ast.parse(src); lines=src.splitlines(True)
        walk=None
        for node in tree.body:
            if getattr(node,"name",None)=="walk_episode_chain":
                walk="".join(lines[node.lineno-1:node.end_lineno]); break
        if not walk: raise SystemExit("walk missing")
    pers.write_text('"""Episode-chain persistence helpers shared by sweep/state probes."""\nfrom __future__ import annotations\n\n\n'+walk+"\n", encoding="utf-8")
    note_created("src/research/probes/persistence.py")
    print("wrote persistence")
else:
    print("persistence exists")

# init
archive_copy("src/research/probes/__init__.py")
(ROOT/"src/research/probes/__init__.py").write_text('''"""Shared research probe helpers."""
from research.probes.corpus import join_and_verify, load_corpus, load_live_rows
from research.probes.governance import FORBIDDEN_KEYS, assert_no_claim_keys
from research.probes.horizon import close_at_horizon
from research.probes.costs_path import load_cost_model, net_r
from research.probes.persistence import walk_episode_chain
from research.probes.scoreboard import profit_factor, scoreboard_row

__all__ = [
    "load_corpus", "load_live_rows", "join_and_verify",
    "FORBIDDEN_KEYS", "assert_no_claim_keys",
    "close_at_horizon", "load_cost_model", "net_r",
    "walk_episode_chain", "profit_factor", "scoreboard_row",
]
''', encoding="utf-8")
note_edit("src/research/probes/__init__.py", "export new helpers")

# shim p001 live/join if bodies still present
archive_copy("scripts/analysis/p001_excursion_probe.py")
p001=(ROOT/"scripts/analysis/p001_excursion_probe.py").read_text(encoding="utf-8")
if "from research.probes.corpus import load_corpus" in p001 and "load_live_rows" in p001 and "def load_live_rows" in p001:
    p001=p001.replace(
        "from research.probes.corpus import load_corpus  # noqa: E402\n",
        "from research.probes.corpus import (  # noqa: E402\n    join_and_verify,\n    load_corpus,\n    load_live_rows,\n)\n",
        1,
    )
    p001=re.sub(r"\ndef load_live_rows\(path: Path\) -> list\[dict\]:.*?(?=\n\ndef )", "\n\n# load_live_rows imported from research.probes.corpus\n\n", p001, count=1, flags=re.S)
    p001=re.sub(r"\ndef join_and_verify\(live: list\[dict\], corpus: list\[dict\]\) -> tuple\[list\[dict\], dict\]:.*?(?=\n\ndef )", "\n\n# join_and_verify imported from research.probes.corpus\n\n", p001, count=1, flags=re.S)
    (ROOT/"scripts/analysis/p001_excursion_probe.py").write_text(p001, encoding="utf-8")
    note_edit("scripts/analysis/p001_excursion_probe.py", "re-export load_live_rows/join_and_verify")
    print("shimmed p001")
elif "join_and_verify" in p001 and "from research.probes.corpus import (" in p001:
    print("p001 already exports live/join")
else:
    print("WARN p001 state", "def load_live_rows" in p001)

# shim spp
archive_copy("scripts/analysis/sweep_state_persistence_probe.py")
spp=(ROOT/"scripts/analysis/sweep_state_persistence_probe.py").read_text(encoding="utf-8")
if "from research.probes.persistence import walk_episode_chain" not in spp:
    if 'sys.path.insert(0, str(ROOT / "src"))\n' not in spp:
        raise SystemExit("spp path insert missing")
    spp=spp.replace('sys.path.insert(0, str(ROOT / "src"))\n', 'sys.path.insert(0, str(ROOT / "src"))\n\nfrom research.probes.persistence import walk_episode_chain  # noqa: E402\n', 1)
    spp=re.sub(r"\ndef walk_episode_chain\(episodes: list\[dict\], start_k: int, horizon: int\) -> dict:.*?(?=\n\ndef )", "\n\n# walk_episode_chain imported from research.probes.persistence\n\n", spp, count=1, flags=re.S)
    (ROOT/"scripts/analysis/sweep_state_persistence_probe.py").write_text(spp, encoding="utf-8")
    note_edit("scripts/analysis/sweep_state_persistence_probe.py", "re-export walk_episode_chain")
    print("shimmed spp")
else:
    print("spp already shimmed")

def migrate_persistence_style(rel, sep_pattern_name):
    archive_copy(rel)
    txt=(ROOT/rel).read_text(encoding="utf-8")
    if "from research.probes.persistence import walk_episode_chain" in txt and "importlib" not in txt:
        print(rel, "already done"); return
    txt=re.sub(r"import importlib\.util\n", "", txt, count=1)
    return txt

# all_states_persistence
rel="scripts/analysis/all_states_persistence_probe.py"
archive_copy(rel)
txt=(ROOT/rel).read_text(encoding="utf-8")
if "spec_from_file_location" in txt:
    txt=re.sub(r"import importlib\.util\n", "", txt, count=1)
    txt,n=re.subn(r"\n_SEP = ROOT.*?\n_spec\.loader\.exec_module\(sep\)\n",
        "\nfrom research.probes.corpus import load_corpus  # noqa: E402\nfrom research.probes.costs_path import load_cost_model  # noqa: E402\nfrom research.probes.horizon import close_at_horizon  # noqa: E402\nfrom research.probes.persistence import walk_episode_chain  # noqa: E402\n",
        txt, count=1, flags=re.S)
    if n!=1: raise SystemExit(f"asp sep n={n}")
    txt,n=re.subn(r"\n_SPP = ROOT.*?\nspec2\.loader\.exec_module\(spp\)\n", "\n", txt, count=1, flags=re.S)
    print("asp spp removed", n)
    txt=txt.replace("spp.walk_episode_chain(", "walk_episode_chain(")
    txt=txt.replace("cost_model = sep.load_cost_model()", "cost_model = load_cost_model()")
    txt=txt.replace("corpus = sep.p001.load_corpus(ROOT / args.csv)", "corpus = load_corpus(ROOT / args.csv)")
    txt=txt.replace("gross = sep.close_at_horizon(", "gross = close_at_horizon(")
    bad=[f"{i}:{l}" for i,l in enumerate(txt.splitlines(),1) if re.search(r"\bsep\.|\bspp\.|importlib", l)]
    if bad: raise SystemExit(str(bad[:10]))
    (ROOT/rel).write_text(txt, encoding="utf-8"); note_edit(rel, "off importlib"); print("migrated", rel)
else:
    print(rel, "already clean")

# sweep_conditional
rel="scripts/analysis/sweep_conditional_magnitude_probe.py"
archive_copy(rel)
txt=(ROOT/rel).read_text(encoding="utf-8")
if "spec_from_file_location" in txt:
    txt=re.sub(r"import importlib\.util\n", "", txt, count=1)
    txt,n=re.subn(r"\n_SPP = ROOT.*?\n_spec2\.loader\.exec_module\(sep\)\n",
        "\nfrom research.probes.corpus import load_corpus  # noqa: E402\nfrom research.probes.costs_path import load_cost_model  # noqa: E402\nfrom research.probes.horizon import close_at_horizon  # noqa: E402\nfrom research.probes.persistence import walk_episode_chain  # noqa: E402\n",
        txt, count=1, flags=re.S)
    if n!=1: raise SystemExit(f"scm n={n}")
    txt=txt.replace("spp.walk_episode_chain(", "walk_episode_chain(")
    txt=txt.replace("corpus = sep.p001.load_corpus(ROOT / args.csv)", "corpus = load_corpus(ROOT / args.csv)")
    txt=txt.replace("cost_model = sep.load_cost_model()", "cost_model = load_cost_model()")
    txt=txt.replace("gross = sep.close_at_horizon(", "gross = close_at_horizon(")
    bad=[f"{i}:{l}" for i,l in enumerate(txt.splitlines(),1) if re.search(r"\bsep\.|\bspp\.|importlib", l)]
    if bad: raise SystemExit(str(bad[:10]))
    (ROOT/rel).write_text(txt, encoding="utf-8"); note_edit(rel, "off importlib"); print("migrated", rel)
else:
    print(rel, "already clean")

# shadow census
rel="scripts/analysis/phase1_shadow_create_economic_census.py"
archive_copy(rel)
txt=(ROOT/rel).read_text(encoding="utf-8")
if "sweep_structure_economic_probe" in txt and "spec_from_file_location" in txt:
    txt,n=re.subn(r"\n_SEP = ROOT.*?\n_ps\.loader\.exec_module\(p001\)\n",
        "\nfrom research.probes.corpus import load_corpus  # noqa: E402\nfrom research.probes.governance import assert_no_claim_keys  # noqa: E402\nfrom research.probes.horizon import close_at_horizon  # noqa: E402\n\n# excursion() still on p001 until forward_walk extraction.\n_P001 = ROOT / \"scripts\" / \"analysis\" / \"p001_excursion_probe.py\"\n_ps = importlib.util.spec_from_file_location(\"p001_excursion_probe\", _P001)\np001 = importlib.util.module_from_spec(_ps)\nassert _ps.loader is not None\n_ps.loader.exec_module(p001)\n",
        txt, count=1, flags=re.S)
    if n!=1: raise SystemExit(f"shadow n={n}")
    txt=txt.replace("gross = sep.close_at_horizon(", "gross = close_at_horizon(")
    txt=txt.replace("corpus = sep.p001.load_corpus(_CSV)", "corpus = load_corpus(_CSV)")
    txt=txt.replace("sep.p001.assert_no_claim_keys(", "assert_no_claim_keys(")
    bad=[f"{i}:{l}" for i,l in enumerate(txt.splitlines(),1) if "sep." in l]
    if bad: raise SystemExit(str(bad))
    (ROOT/rel).write_text(txt, encoding="utf-8"); note_edit(rel, "probes + importlib only for excursion"); print("migrated", rel)
else:
    print(rel, "already migrated or unexpected")

# build_decision_atlas
rel="scripts/analysis/build_decision_atlas.py"
archive_copy(rel)
txt=(ROOT/rel).read_text(encoding="utf-8")
if "p001.load_corpus" in txt:
    txt,n=re.subn(r"\n_P001 = ROOT.*?\n_spec\.loader\.exec_module\(p001\)\n",
        "\nfrom research.probes.corpus import (  # noqa: E402\n    join_and_verify,\n    load_corpus,\n    load_live_rows,\n)\nfrom research.probes.governance import assert_no_claim_keys  # noqa: E402\n\n# excursion() still on p001 until forward_walk extraction.\n_P001 = ROOT / \"scripts\" / \"analysis\" / \"p001_excursion_probe.py\"\n_spec = importlib.util.spec_from_file_location(\"p001_excursion_probe\", _P001)\np001 = importlib.util.module_from_spec(_spec)\n_spec.loader.exec_module(p001)\n",
        txt, count=1, flags=re.S)
    if n!=1: raise SystemExit(f"atlas n={n}")
    txt=txt.replace("corpus = p001.load_corpus(ROOT / args.csv)", "corpus = load_corpus(ROOT / args.csv)")
    txt=txt.replace("live = p001.load_live_rows(ROOT / args.stream)", "live = load_live_rows(ROOT / args.stream)")
    txt=txt.replace("joined, integrity = p001.join_and_verify(live, corpus)", "joined, integrity = join_and_verify(live, corpus)")
    txt=txt.replace("p001.assert_no_claim_keys(meta)", "assert_no_claim_keys(meta)")
    (ROOT/rel).write_text(txt, encoding="utf-8"); note_edit(rel, "probes + importlib only for excursion"); print("migrated", rel)
else:
    print(rel, "already migrated")

(ARCH/"MANIFEST.csv").write_text("\n".join(rows)+"\n", encoding="utf-8")
(ARCH/"MANIFEST.md").write_text(f"# {BATCH}\nUTC {stamp}\nNo deletes.\n", encoding="utf-8")
idx=ROOT/"archive/ARCHIVE_INDEX.md"
idx.write_text(idx.read_text(encoding="utf-8")+f"\n## {BATCH}\n- UTC: {stamp}\n- Manifest: archive/{BATCH}/MANIFEST.csv\n- Deletes: none\n", encoding="utf-8")
manifests=ROOT/"docs/governance/build_manifests"
impact={"change_id":"CH-probes-extract-batch3-2026-09-14","when_utc":stamp,"archive_batch":f"archive/{BATCH}/","completion_status":"COMPLETE_LOCAL"}
(manifests/"CH-probes-extract-batch3-2026-09-14.impact.json").write_text(json.dumps(impact,indent=2)+"\n", encoding="utf-8")
(manifests/"CH-probes-extract-batch3-2026-09-14.completion.json").write_text(json.dumps({"change_id":impact["change_id"],"completion_status":"COMPLETE_LOCAL","declared_files":[f"archive/{BATCH}/MANIFEST.csv"]},indent=2)+"\n", encoding="utf-8")
audit=ROOT/"docs/research/probes_extraction_audit_2026-09-14.md"
if audit.exists():
    audit.write_text(audit.read_text(encoding="utf-8")+f"\n## Batch 3 (`{BATCH}`)\nMigrated all_states_persistence + sweep_conditional fully; shadow census + build_decision_atlas partial (excursion importlib remains).\n", encoding="utf-8")
print("DONE")