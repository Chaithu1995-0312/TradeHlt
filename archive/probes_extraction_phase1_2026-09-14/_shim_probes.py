from __future__ import annotations
import hashlib, re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\Tradelatest")
ARCH = ROOT / "archive" / "probes_extraction_phase1_2026-09-14"
PROBES = ROOT / "src" / "research" / "probes"
stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# p001
p001_path = ROOT / "scripts/analysis/p001_excursion_probe.py"
p001 = p001_path.read_text(encoding="utf-8")
if "from research.probes.corpus import load_corpus" not in p001:
    insert_after = "from research.contracts import Signal  # noqa: E402"
    if insert_after not in p001:
        raise SystemExit("p001 insert point missing")
    p001 = p001.replace(
        insert_after,
        insert_after
        + "\nfrom research.probes.corpus import load_corpus  # noqa: E402\n"
        + "from research.probes.governance import (  # noqa: E402\n"
        + "    FORBIDDEN_KEYS,\n"
        + "    assert_no_claim_keys,\n"
        + ")\n",
        1,
    )
    p001 = re.sub(r"\nFORBIDDEN_KEYS = \([^)]*\)\n", "\n# FORBIDDEN_KEYS imported from research.probes.governance\n", p001, count=1)
    p001 = re.sub(r"\ndef load_corpus\(path: Path\) -> list\[dict\]:.*?(?=\n\ndef |\n\nclass |\Z)", "\n\n# load_corpus imported from research.probes.corpus\n\n", p001, count=1, flags=re.S)
    p001 = re.sub(r"\ndef assert_no_claim_keys\(obj: Any, path: str = \"\"\) -> None:.*?(?=\n\ndef |\n\nclass |\Z)", "\n\n# assert_no_claim_keys imported from research.probes.governance\n\n", p001, count=1, flags=re.S)
    p001_path.write_text(p001, encoding="utf-8")
    print("shimmed p001")
else:
    print("p001 already shimmed")

# sep
sep_path = ROOT / "scripts/analysis/sweep_structure_economic_probe.py"
sep = sep_path.read_text(encoding="utf-8")
if "from research.probes.horizon import close_at_horizon" not in sep:
    sep = re.sub(r"import importlib\.util\n", "", sep, count=1)
    sep2, n = re.subn(
        r"\n_P001 = ROOT.*?\n_spec\.loader\.exec_module\(p001\)\n",
        "\nfrom research.probes import corpus as p001  # noqa: E402\n"
        "from research.probes.governance import assert_no_claim_keys  # noqa: E402\n"
        "from research.probes.horizon import close_at_horizon  # noqa: E402\n"
        "p001.assert_no_claim_keys = assert_no_claim_keys  # type: ignore[attr-defined]\n",
        sep, count=1, flags=re.S,
    )
    if n != 1:
        raise SystemExit(f"sep p001 block n={n}")
    sep = sep2
    sep, n = re.subn(
        r"\ndef close_at_horizon\(corpus: list\[dict\], bar_index: int, direction: str, atr: float,\n                     horizon: int\) -> Optional\[float\]:.*?(?=\n\ndef )",
        "\n\n# close_at_horizon imported from research.probes.horizon\n\n",
        sep, count=1, flags=re.S,
    )
    print("sep close_at_horizon removed", n)
    sep_path.write_text(sep, encoding="utf-8")
    print("shimmed sep")
else:
    print("sep already shimmed")

# phase1
ph1_path = ROOT / "scripts/analysis/phase1_resolver_replay_evidence.py"
ph1 = ph1_path.read_text(encoding="utf-8")
if "from research.probes.horizon import close_at_horizon" not in ph1:
    ph1 = ph1.replace("import importlib.util\n", "")
    ph1, n = re.subn(
        r"\n# Reuse sep\.close_at_horizon \+ p001\.load_corpus.*?\n_spec\.loader\.exec_module\(sep\)\n",
        "\n# Shared probe helpers (extracted; pre-edit copy in archive/probes_extraction_phase1_2026-09-14/)\n"
        "from research.probes.corpus import load_corpus  # noqa: E402\n"
        "from research.probes.costs_path import net_r as _net_r_shared  # noqa: E402\n"
        "from research.probes.governance import assert_no_claim_keys  # noqa: E402\n"
        "from research.probes.horizon import close_at_horizon  # noqa: E402\n"
        "from research.probes.scoreboard import profit_factor as _profit_factor_shared  # noqa: E402\n"
        "from research.probes.scoreboard import scoreboard_row as _scoreboard_row_shared  # noqa: E402\n",
        ph1, count=1, flags=re.S,
    )
    if n != 1:
        raise SystemExit(f"phase1 inject n={n}")
    ph1 = ph1.replace("gross = sep.close_at_horizon(corpus, bar_index, direction, atr, HORIZON)", "gross = close_at_horizon(corpus, bar_index, direction, atr, HORIZON)")
    ph1 = ph1.replace("sep.p001.load_corpus(", "load_corpus(")
    ph1 = ph1.replace("sep.p001.assert_no_claim_keys(", "assert_no_claim_keys(")
    ph1, n1 = re.subn(r"\ndef _profit_factor\(xs: list\[float\]\) -> float:.*?(?=\n\ndef )", "\ndef _profit_factor(xs: list[float]) -> float:\n    return _profit_factor_shared(xs, pf_cap=PF_CAP)\n\n\n", ph1, count=1, flags=re.S)
    ph1, n2 = re.subn(r"\ndef _scoreboard_row\(\n    name: str,\n    net_rs: list\[float\],\n    \*,\n    n_universe: int,\n    n_eligible: int,\n\) -> dict:.*?(?=\n\ndef )", "\ndef _scoreboard_row(\n    name: str,\n    net_rs: list[float],\n    *,\n    n_universe: int,\n    n_eligible: int,\n) -> dict:\n    return _scoreboard_row_shared(\n        name,\n        net_rs,\n        n_universe=n_universe,\n        n_eligible=n_eligible,\n        min_n_label=MIN_N_LABEL,\n        pf_cap=PF_CAP,\n    )\n\n\n", ph1, count=1, flags=re.S)
    ph1, n3 = re.subn(r"\ndef _net_r\(\n    corpus: list\[dict\],\n    bar_index: int,\n    direction: str,\n    atr: float,\n    cost_model: ComponentCostModel,\n\) -> Optional\[float\]:.*?(?=\n\ndef )", "\ndef _net_r(\n    corpus: list[dict],\n    bar_index: int,\n    direction: str,\n    atr: float,\n    cost_model: ComponentCostModel,\n) -> Optional[float]:\n    return _net_r_shared(corpus, bar_index, direction, atr, cost_model, HORIZON)\n\n\n", ph1, count=1, flags=re.S)
    print(f"wrappers profit={n1} scoreboard={n2} net_r={n3}")
    leftover = [f"{i}:{l}" for i,l in enumerate(ph1.splitlines(),1) if ("sep." in l or "importlib" in l)]
    if leftover:
        print("LEFTOVER:")
        print("\n".join(leftover[:30]))
    ph1_path.write_text(ph1, encoding="utf-8")
    print("rewrote phase1")
else:
    print("phase1 already rewritten")

# manifest update
rows = (ARCH/"MANIFEST.csv").read_text(encoding="utf-8").strip().splitlines()
for rel in sorted(p.relative_to(ROOT).as_posix() for p in PROBES.glob("*.py")):
    rows.append(f"{stamp},created,{rel},,{hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()},new shared probes module")
for rel in ["scripts/analysis/p001_excursion_probe.py","scripts/analysis/sweep_structure_economic_probe.py","scripts/analysis/phase1_resolver_replay_evidence.py"]:
    h=hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
    rows.append(f"{stamp},edited_in_place,{rel},archive/probes_extraction_phase1_2026-09-14/{rel},{h},shim/rewrite after archive copy; original preserved in archive")
(ARCH/"MANIFEST.csv").write_text("\n".join(rows)+"\n", encoding="utf-8")
md = (ARCH/"MANIFEST.md")
md.write_text(md.read_text(encoding="utf-8")+f"\n\n## Post-apply (UTC {stamp})\n\nCreated src/research/probes/*.py; shimmed p001/sep; rewrote phase1 off importlib. Deletes: none.\n", encoding="utf-8")
dump = ROOT/"_extract_dump"
if dump.exists() and not (ARCH/"_extract_dump").exists():
    dump.rename(ARCH/"_extract_dump")
    print("moved _extract_dump to archive")
print("DONE")
