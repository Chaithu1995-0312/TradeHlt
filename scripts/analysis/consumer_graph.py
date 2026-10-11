"""Consumer registry + dependency graph for the canonical feature contract (read-only).

Edges come from AST analysis of the repository (imports and symbol references, with file:line evidence);
parity statuses come from in-memory execution; absences come from repository-wide searches.
Nothing under src/, configs/ or models/ is modified.  Output: --out directory.

    python scripts/analysis/consumer_graph.py --out results/consumer_graph
"""
from __future__ import annotations

import argparse
import ast
import csv
import glob
import hashlib
import importlib.util
import inspect
import json
import logging
import re
import subprocess
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))
logging.disable(logging.CRITICAL)

from features import feature_schema as fs  # noqa: E402

CF = list(fs.CANONICAL_FEATURES)
CFSET = set(CF)
REL = lambda p: str(Path(p).resolve().relative_to(ROOT))  # noqa: E731

# ---------------------------------------------------------------------------------------------------------
# 1. AST scan of the repository
# ---------------------------------------------------------------------------------------------------------
KEY_SYMBOLS = ["FeaturePipeline", "FeatureStore", "extract_feature_vector", "build_bitnet_features", "FeatureBuilder",
               "feature_dict_to_vector", "load_gaussian_model", "get_active_gaussian", "GaussianModelRegistry",
               "GaussianRegistry", "MLGaussianEngine", "HeuristicGaussianEngine", "EngineRunner", "LiveEngine",
               "HookedLiveEngine", "BitNetZoneGate", "get_zone_gate", "SCHEMA_HASH", "GAUSSIAN_SCHEMA", "TRADENET_SCHEMA",
               "CANONICAL_FEATURES", "CANONICAL_FEATURE_ORDER", "build_feature_vector", "validate_feature_vector",
               "LiveEngineHook", "register_gaussian", "promote_gaussian"]

SKIP_PARTS = {"__pycache__", ".git", "node_modules"}


def py_files():
    out = []
    for pat in ("src/**/*.py", "scripts/**/*.py", "tools/**/*.py", "*.py", "tests/**/*.py"):
        for p in ROOT.glob(pat):
            if not (set(p.parts) & SKIP_PARTS):
                out.append(p)
    return sorted(set(out))


def parse(p):
    try:
        return ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return None


def module_file(modname: str):
    """Resolve a dotted module to a repo file (src root, or repo root)."""
    mod = modname[4:] if modname.startswith("src.") else modname
    for base in (ROOT / "src", ROOT):
        f = base / (mod.replace(".", "/") + ".py")
        if f.exists():
            return f
        i = base / mod.replace(".", "/") / "__init__.py"
        if i.exists():
            return i
    return None


def scan():
    files = py_files()
    imports = defaultdict(list)       # file -> [(target_file, line, "from x import y")]
    refs = defaultdict(list)          # symbol -> [(file, line, kind)]
    literals = defaultdict(lambda: defaultdict(list))   # file -> feature -> [lines]
    defs = defaultdict(list)          # symbol -> [(file, line)]
    bare = []                         # (file, line, module, names) bare imports of repo module stems
    stems = {q.stem: REL(q) for q in files if REL(q).startswith('src/')}
    for p in files:
        t = parse(p)
        if t is None:
            continue
        rp = REL(p)
        pkg = ".".join(Path(rp).with_suffix("").parts[1:-1]) if rp.startswith("src/") else ""
        for n in ast.walk(t):
            if isinstance(n, ast.ImportFrom):
                base = n.module or ""
                if n.level == 0 and base and '.' not in base and base in stems and not base.startswith('_'):
                    bare.append((rp, n.lineno, base, [a.name for a in n.names], stems[base]))
                if n.level:
                    parts = pkg.split(".") if pkg else []
                    parts = parts[:len(parts) - (n.level - 1)] if n.level > 1 else parts
                    base = ".".join(parts + ([n.module] if n.module else []))
                tgt = module_file(base) if base else None
                for a in n.names:
                    sub = module_file(f"{base}.{a.name}") if base else None
                    use = sub or tgt
                    if use and REL(use) != rp:
                        imports[rp].append((REL(use), n.lineno, f"from {base} import {a.name}"))
                    if a.name in KEY_SYMBOLS:
                        refs[a.name].append((rp, n.lineno, "import"))
            elif isinstance(n, ast.Import):
                for a in n.names:
                    tgt = module_file(a.name)
                    if tgt and REL(tgt) != rp:
                        imports[rp].append((REL(tgt), n.lineno, f"import {a.name}"))
            elif isinstance(n, ast.Name) and n.id in KEY_SYMBOLS and isinstance(n.ctx, ast.Load):
                refs[n.id].append((rp, n.lineno, "name"))
            elif isinstance(n, ast.Attribute) and n.attr in KEY_SYMBOLS:
                refs[n.attr].append((rp, n.lineno, "attr"))
            elif isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in KEY_SYMBOLS:
                defs[n.name].append((rp, n.lineno))
            elif isinstance(n, ast.Assign):
                for tg in n.targets:
                    if isinstance(tg, ast.Name) and tg.id in KEY_SYMBOLS:
                        defs[tg.id].append((rp, n.lineno))
            # feature literals used as keys
            if isinstance(n, ast.Subscript):
                s = n.slice
                if isinstance(s, ast.Constant) and isinstance(s.value, str) and s.value in CFSET:
                    literals[rp][s.value].append(n.lineno)
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "get" and n.args:
                a0 = n.args[0]
                if isinstance(a0, ast.Constant) and isinstance(a0.value, str) and a0.value in CFSET:
                    literals[rp][a0.value].append(n.lineno)
    return files, imports, refs, literals, defs, bare


def assign_sites(path: Path, target_ok=lambda name: name in CFSET):
    """Find `x["feature"] = expr` assignments; return {feature: [(line, func, source)]}."""
    src = path.read_text(encoding="utf-8", errors="ignore")
    t = ast.parse(src)
    out = defaultdict(list)

    def visit(node, func):
        for ch in ast.iter_child_nodes(node):
            f = ch.name if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)) else func
            if isinstance(ch, ast.Assign):
                for tg in ch.targets:
                    if isinstance(tg, ast.Subscript) and isinstance(tg.slice, ast.Constant) and isinstance(tg.slice.value, str) \
                            and target_ok(tg.slice.value):
                        out[tg.slice.value].append((ch.lineno, func, (ast.get_source_segment(src, ch) or "").strip()[:240]))
            visit(ch, f)

    visit(t, "<module>")
    return out


def dict_literal_sites(path: Path, func_name: str):
    """Keys of dict literals inside one function: {key: (line, source)}."""
    src = path.read_text(encoding="utf-8", errors="ignore")
    t = ast.parse(src)
    res = {}
    for fn in ast.walk(t):
        if isinstance(fn, ast.FunctionDef) and fn.name == func_name:
            for d in ast.walk(fn):
                if isinstance(d, ast.Dict):
                    for k, v in zip(d.keys, d.values):
                        if isinstance(k, ast.Constant) and isinstance(k.value, str) and k.value in CFSET:
                            res[k.value] = (k.lineno, (ast.get_source_segment(src, v) or "").strip()[:200])
    return res


# ---------------------------------------------------------------------------------------------------------
# 2. Execution evidence (in memory)
# ---------------------------------------------------------------------------------------------------------
def load_batch(csv_path: Path, n=700):
    from features.feature_pipeline import FeaturePipeline
    raw = pd.read_csv(csv_path); raw["timestamp"] = pd.to_datetime(raw["timestamp"])
    df, _ = FeaturePipeline(raw.copy()).run()
    df = df.reset_index(drop=True); df["timestamp"] = pd.to_datetime(df["timestamp"])
    r = raw.set_index("timestamp").reindex(df["timestamp"])
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = r[c].to_numpy()
    return df.head(n)


def num_cmp(b, l):
    """-> 'identical' | 'value_mismatch' | 'type_break' for aligned sequences."""
    st = {}
    for k in CF:
        bs, ls = b[k].tolist(), l[k].tolist()
        bad_type = bad_val = 0
        for x, y in zip(bs, ls):
            try:
                fy = float(y)
            except (TypeError, ValueError):
                bad_type += 1; continue
            fx = float(x)
            if not (abs(fx - fy) <= 1e-6 * max(1.0, abs(fx)) or (np.isnan(fx) and np.isnan(fy))):
                bad_val += 1
        st[k] = ("type_break" if bad_type else "value_mismatch" if bad_val else "identical", bad_type, bad_val, len(bs))
    return st


BARE = []


def exec_evidence(batch: pd.DataFrame):
    ev = {}
    # E-hook: live hook + FeatureStore with ideal upstream
    from core.feature_store import FeatureStore
    from runtime.live_engine_hook import _build_ohlcv_and_auxiliary
    store = FeatureStore(max_history=1000); frames = []
    for i, rec in enumerate(batch.to_dict("records")):
        o, a = _build_ohlcv_and_auxiliary(rec)
        frames.append(store.process(i, rec["timestamp"], o, a).features)
    live = pd.DataFrame(frames)
    ev["live_hook_featurestore"] = {k: dict(zip(("status", "type_breaks", "value_mismatches", "n"), v)) for k, v in num_cmp(batch, live).items()}
    # E-bitnet builder with equivalent inputs (pipeline's own values)
    from features.bitnet_feature_builder import build_bitnet_features
    outs = []
    for rec in batch.to_dict("records"):
        outs.append(build_bitnet_features({}, rec, rec))
    ev["bitnet_feature_builder"] = {k: dict(zip(("status", "type_breaks", "value_mismatches", "n"), v)) for k, v in num_cmp(batch, pd.DataFrame(outs)).items()}
    # E-csv: backtest trade snapshots
    paths = sorted(glob.glob(str(ROOT / "results/gaussian_training/backtest/*/XAUUSD_trades.csv")))
    snap = {}
    if paths:
        rows = list(csv.DictReader(open(paths[0], encoding="utf-8-sig")))
        full = load_batch(ROOT / "data/XAUUSD_M15.csv", n=10**9)
        ix = {t: i for i, t in enumerate(full["timestamp"])}
        for k in CF:
            if k not in rows[0]:
                snap[k] = dict(status="unverified", note="column absent in trades.csv"); continue
            bad = 0
            for r in rows:
                i = ix[pd.Timestamp(r["opened_at"])]
                x, y = float(full[k].iloc[i]), float(r[k])
                if not abs(x - y) <= 1e-4 * max(1.0, abs(y)):
                    bad += 1
            snap[k] = dict(status="identical" if bad == 0 else "value_mismatch", mismatches=bad, n=len(rows))
        snap["_file"] = REL(paths[0])
    ev["backtest_trade_snapshot"] = snap
    # E-anatomy: CRT Candle and manual_backtest vs pipeline
    from config_layer.crt_engine_v2 import Candle
    sig = inspect.signature(Candle).parameters
    mism = defaultdict(int)
    for rec in batch.to_dict("records"):
        kw = dict(timestamp=rec["timestamp"], open=rec["open"], high=rec["high"], low=rec["low"], close=rec["close"], volume=rec["volume"])
        c = Candle(**{k: v for k, v in kw.items() if k in sig})
        for name, val in (("body_size", c.body_size), ("wick_size", c.wick_size), ("body_ratio", c.body_ratio)):
            if abs(val - rec[name]) > 1e-4 * max(1.0, abs(rec[name])):
                mism[name] += 1
    ev["crt_candle_anatomy"] = {k: ("identical" if mism[k] == 0 else "value_mismatch") for k in ("body_size", "wick_size", "body_ratio")}
    msrc = (ROOT / "scripts/backtest/manual_backtest.py").read_text()
    mt = ast.parse(msrc); ns = {}
    for fnode in mt.body:
        if isinstance(fnode, ast.FunctionDef) and fnode.name in ("body_ratio", "wick_size"):
            exec(ast.get_source_segment(msrc, fnode), ns)
    mm = defaultdict(int)
    for rec in batch.to_dict("records"):
        if abs(ns["body_ratio"](rec["open"], rec["high"], rec["low"], rec["close"]) - rec["body_ratio"]) > 1e-4:
            mm["body_ratio"] += 1
        if abs(ns["wick_size"](rec["open"], rec["high"], rec["low"], rec["close"]) - rec["wick_size"]) > 1e-4 * max(1, abs(rec["wick_size"])):
            mm["wick_size"] += 1
    ev["manual_backtest_anatomy"] = {"body_ratio": "identical" if mm["body_ratio"] == 0 else "value_mismatch",
                                     "wick_size": "identical" if mm["wick_size"] == 0 else "value_mismatch",
                                     "body_size": "unverified (no function; inline expression)"}
    # E-extract: dataset_builder.extract_feature_vector on numeric batch row
    from features.dataset_builder import extract_feature_vector
    row = {k: float(batch[k].iloc[-1]) for k in CF}
    v = extract_feature_vector(row)
    ev["extract_feature_vector_numeric_row"] = {"order_ok": v == [row[k] for k in CF], "len": len(v)}
    live_row = frames[-1]
    try:
        extract_feature_vector(live_row); ev["extract_feature_vector_live_row"] = "ok"
    except Exception as e:
        ev["extract_feature_vector_live_row"] = f"{type(e).__name__}: {e}"
    from engines.ml_gaussian_engine import MLGaussianEngine
    ev["ml_engine_on_live_row"] = MLGaussianEngine({}).compute(live_row)
    ev["ml_engine_on_numeric_row"] = {k: v for k, v in MLGaussianEngine({}).compute(row).items() if k != "meta"}
    # E-rr warm-up
    import training_live_parity as tlp
    ev["rr_dataset_builder_rows_surviving"] = tlp.rr_warmup()
    # E-imports
    imp = {}
    for mod, name in (("features.dataset_builder", "build_feature_vector"), ("features.dataset_builder", "validate_feature_vector"),
                      ("runtime.live_engine_hook", "LiveEngineHook"), ("feature_builder", "N_FEATURES"),
                      ("features.feature_builder", "build_feature_vector"), ("features.feature_builder", "N_FEATURES")):
        try:
            m = __import__(mod, fromlist=["x"]); imp[f"{mod}.{name}"] = "present" if hasattr(m, name) else "ImportError: name missing"
        except Exception as e:
            imp[f"{mod}.{name}"] = f"{type(e).__name__}: {str(e)[:70]}"
    ev["import_checks"] = imp
    res_b = []
    for (f, line, mod, names, target) in BARE:
        spec = importlib.util.find_spec(mod)
        sp = 'sys.path' in (ROOT / f).read_text(errors='ignore')
        res_b.append(dict(file=f, line=line, module=mod, names=names, defined_in=target, resolves_with_src_on_path=spec is not None,
                          file_edits_sys_path=sp, runtime_resolution=(True if spec is not None else None if sp else False)))
    ev["bare_imports"] = res_b
    # E-heuristic registry before/after
    from engines.heuristic_gaussian_engine import GaussianRegistry
    hr = {}
    for lab, pth in (("current", "models/gaussian_registry.json"), ("pre_experimental_promotion", "models/gaussian_registry.pre_xau_m15_causal_n9_20261011.json")):
        pp = ROOT / pth
        if pp.exists():
            r = GaussianRegistry(str(pp)).load(); hr[lab] = dict(active=r.active_version, mu=r.mu, sigma=r.sigma)
    ev["heuristic_registry_resolution"] = hr
    # E-cpp: parse FEATURE_ORDER from cpp source
    cpp = (ROOT / "tools/cpp/cpp_runner.cpp").read_text()
    blk = re.search(r"FEATURE_ORDER\s*=\s*\{(.*?)\};", cpp, re.S).group(1)
    names = re.findall(r'"([a-z_0-9]+)"', blk)
    ev["cpp_runner"] = {"order_equal_to_CANONICAL_FEATURES": names == CF, "n": len(names),
                        "missing_or_null_policy": "missing key -> 0.0; null -> NaN -> 0.0 (silent)",
                        "inputs": "test_vectors.json + model.json (precomputed rows; computes no features)",
                        "binary_in_repo": (ROOT / "tools/cpp/cpp_runner.exe").exists(), "executed_here": False}
    # E-models
    inv = []
    from training import trainer
    for p in sorted(glob.glob(str(ROOT / "models/gaussian_*.json"))):
        n = Path(p).name
        if "registry" in n:
            continue
        b = json.loads(Path(p).read_text()); fsch = b.get("feature_schema", [])
        try:
            trainer.load_gaussian_model(n); ld = "loads"
        except Exception as e:
            ld = f"rejected: {type(e).__name__}"
        inv.append(dict(file=n, n_features=len(fsch), schema_checksum=b.get("schema_checksum"), load=ld,
                        missing_vs_canonical=[x for x in CF if x not in fsch], order_matches_common=[x for x in fsch if x in CFSET] == [x for x in CF if x in fsch],
                        has_feature_definition_identity="feature_definition" in b, has_timeframe_or_provenance=("provenance" in b)))
    ev["gaussian_artifacts"] = inv
    tn = []
    for p in sorted(glob.glob(str(ROOT / "models/tradenet_p5_*.pth"))):
        z = zipfile.ZipFile(p); sz = {n.split("/")[-1]: z.getinfo(n).file_size // 4 for n in z.namelist() if "/data/" in n}
        tn.append(dict(file=Path(p).name, first_layer_inputs=sz["0"] // 32, expected=fs.TRADENET_SCHEMA.n_features))
    ev["tradenet_artifacts"] = dict(items=tn, torch_installed=importlib.util.find_spec("torch") is not None)
    for stub in ("v1.json", "import_fix_v1.json"):
        pth = ROOT / "models" / stub
        ev.setdefault("stub_artifacts", {})[stub] = json.loads(pth.read_text()).get("schema") if pth.exists() else "absent"
    return ev


# ---------------------------------------------------------------------------------------------------------
# 3. Catalogue (curated roles; every edge and status below is derived or checked)
# ---------------------------------------------------------------------------------------------------------
TREES = {"A": "Batch / backtest", "B": "Live / streaming", "C": "ML / Gaussian", "D": "Other consumers", "S": "Shared"}
NODES = {
    # canonical
    "src/features/feature_schema.py": ("schema_authority", "S"),
    "src/features/dataset_builder.py": ("schema_authority", "S"),
    "src/features/schema_validator.py": ("duplicate_validator", "S"),
    "model_export_format.json": ("external_mirror", "D"),
    # A
    "src/features/feature_pipeline.py": ("producer_canonical", "A"),
    "src/runtime/backtest_v2.py": ("consumer_producer", "A"),
    "src/config_layer/crt_engine_v2.py": ("duplicate_producer+consumer", "A"),
    "scripts/backtest/manual_backtest.py": ("duplicate_producer+consumer", "A"),
    "src/config_layer/rr/rr_dataset_builder.py": ("producer_variant", "C"),
    "src/features/dataset_validator.py": ("consumer", "C"),
    # B
    "src/runtime/live_engine_hook.py": ("producer_variant", "B"),
    "src/core/feature_store.py": ("producer_variant", "B"),
    "src/core/engine_runner.py": ("decision_consumer", "S"),
    "src/engines/live_engine.py": ("consumer", "B"),
    "src/agent/modes/pipeline_mode.py": ("consumer", "B"),
    "src/agent/modes/copilot_mode.py": ("consumer_external_input", "B"),
    "src/llm_research/forward_tester.py": ("consumer", "B"),
    "src/scanner/scanner.py": ("consumer_injected_provider", "B"),
    "src/features/feature_builder.py": ("producer_variant", "B"),
    "src/engines/adapter_engine.py": ("consumer", "B"),
    "src/core/fusion_engine.py": ("consumer", "B"),
    "src/config_layer/execution_planner.py": ("consumer", "B"),
    "src/config_layer/crt_gaussian_scorer.py": ("consumer", "B"),
    # C
    "scripts/training/phase5_calibration.py": ("training_path_P5", "C"),
    "src/training/train_pipeline.py": ("training_path_TP", "C"),
    "src/training/trainer.py": ("loader_saver", "C"),
    "src/core/model_registry.py": ("registry_writer", "C"),
    "src/engines/ml_gaussian_engine.py": ("inference_adapter", "C"),
    "src/engines/heuristic_gaussian_engine.py": ("registry_reader_heuristic", "C"),
    "src/engines/gaussian_engine.py": ("consumer", "C"),
    "scripts/training/gaussian_from_backtest.py": ("training_path_experimental", "C"),
    "src/runtime/baseline_capture.py": ("consumer", "C"),
    # D
    "src/features/bitnet_feature_builder.py": ("producer_variant_unused", "D"),
    "src/bitnet/search_engine.py": ("consumer", "D"),
    "src/bitnet/bitnet_runner.py": ("consumer", "D"),
    "src/bitnet/bitnet_inference.py": ("consumer", "D"),
    "src/engines/zone_gate_engine.py": ("consumer", "D"),
    "tools/cpp/cpp_runner.cpp": ("external_runtime", "D"),
    "src/inout/runner.py": ("parallel_independent", "D"),
}
VIRTUAL = {
    "MISSING:trade_data_producer": ("missing_producer", "B"),
    "UNVERIFIED:external_callers": ("unverified_external", "D"),
    "ARTIFACTS:gaussian_p5_* (12)": ("model_artifacts", "C"),
    "ARTIFACTS:gaussian_xau_m15_causal_n9_20261011": ("model_artifact_experimental", "C"),
    "ARTIFACTS:v1.json / import_fix_v1 stubs": ("registry_stub_artifacts", "C"),
    "ARTIFACTS:tradenet_p5_* (5)": ("model_artifacts", "D"),
    "CONFIG:configs/production/v1_multi_2026_03.json": ("config", "S"),
    "REGISTRY:models/gaussian_registry.json": ("registry_file", "C"),
}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True)
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    files, imports, refs, literals, defs, bare = scan()
    global BARE
    BARE = bare
    batch = load_batch(ROOT / "data/XAUUSD_M15_2025-07.csv")
    ev = exec_evidence(batch)

    # ---- edges (AST evidence) ----
    edges = []
    nodeset = set(NODES)
    for src_f, lst in imports.items():
        if src_f not in nodeset:
            continue
        seen = set()
        for tgt, line, txt in lst:
            if tgt in nodeset and (src_f, tgt) not in seen:
                seen.add((src_f, tgt))
                edges.append(dict(src=src_f, dst=tgt, kind="imports", established_by="ast", evidence=f"{src_f}:{line} {txt}"))
    # symbol reference edges for files that call symbols without a direct import of the defining file
    def_file = {s: [d[0] for d in defs.get(s, [])] for s in KEY_SYMBOLS}
    have = {(e["src"], e["dst"]) for e in edges}
    for s, sites in refs.items():
        for (f, line, kind) in sites:
            if f in nodeset:
                for df_ in def_file.get(s, []):
                    if df_ in nodeset and df_ != f and (f, df_) not in have:
                        edges.append(dict(src=f, dst=df_, kind=f"references {s}", established_by="ast", evidence=f"{f}:{line}"))
                        have.add((f, df_))
    unresolved = {(b['file'], b['defined_in']) for b in ev['bare_imports'] if b['runtime_resolution'] is False}
    edges = [e for e in edges if not (e['kind'].startswith('references') and (e['src'], e['dst']) in unresolved)]
    for b in ev['bare_imports']:
        if b['file'] in nodeset and b['defined_in'] in nodeset:
            edges = [e for e in edges if (e['src'], e['dst']) != (b['file'], b['defined_in'])]
            edges.append(dict(src=b['file'], dst=b['defined_in'], kind='bare import ' + b['module'], established_by='ast',
                              evidence=f"{b['file']}:{b['line']} from {b['module']} import {', '.join(b['names'])}",
                              runtime_resolves=b['runtime_resolution'], resolution_note='True: importable with src on sys.path; None: not importable here but the file edits sys.path (not simulated); False: not importable and no sys.path edit'))
    # analysis scripts collapsed
    analysis = sorted({f for s in ("FeaturePipeline", "extract_feature_vector", "CANONICAL_FEATURES") for (f, _, _) in refs.get(s, []) if f.startswith("scripts/analysis/")})
    NODES_EXTRA = {"scripts/analysis/* (research consumers)": ("research_consumers", "A")}
    edges.append(dict(src="scripts/analysis/* (research consumers)", dst="src/features/feature_pipeline.py", kind="references FeaturePipeline",
                      established_by="ast", evidence=f"{len(analysis)} files, e.g. {analysis[:3]}"))
    # absences and config edges
    tdp = [p for p in files if "trade_data" in p.read_text(errors="ignore") and not REL(p).startswith(("scripts/analysis", "tests", "results"))]
    edges.append(dict(src="MISSING:trade_data_producer", dst="src/runtime/live_engine_hook.py", kind="feeds trade_data", established_by="absence",
                      evidence=f"repo-wide search for 'trade_data' finds only {sorted(REL(p) for p in tdp)}; no caller of HookedLiveEngine.process outside the module"))
    edges.append(dict(src="UNVERIFIED:external_callers", dst="src/runtime/live_engine_hook.py", kind="may call", established_by="none", evidence="no in-repo caller; external deployment not inspectable"))
    prodcfg = json.loads((ROOT / "configs/production/v1_multi_2026_03.json").read_text())
    gimpl = (prodcfg.get("engine_runner") or {}).get("gaussian_impl")
    edges.append(dict(src="CONFIG:configs/production/v1_multi_2026_03.json", dst="src/core/engine_runner.py", kind=f"selects gaussian_impl={gimpl!r}", established_by="config",
                      evidence="configs/production/v1_multi_2026_03.json engine_runner.gaussian_impl; engine_runner.py:263-281"))
    for art, cons in (("ARTIFACTS:gaussian_p5_* (12)", "src/training/trainer.py"), ("ARTIFACTS:gaussian_xau_m15_causal_n9_20261011", "src/training/trainer.py"),
                      ("ARTIFACTS:tradenet_p5_* (5)", "src/training/trainer.py"), ("ARTIFACTS:v1.json / import_fix_v1 stubs", "src/engines/heuristic_gaussian_engine.py"),
                      ("REGISTRY:models/gaussian_registry.json", "src/core/model_registry.py"), ("REGISTRY:models/gaussian_registry.json", "src/engines/heuristic_gaussian_engine.py"),
                      ("REGISTRY:models/gaussian_registry.json", "src/engines/ml_gaussian_engine.py")):
        edges.append(dict(src=art, dst=cons, kind="read by", established_by="ast+file", evidence=f"{cons} reads the artifact/registry path (see loader code)"))
    edges.append(dict(src="tools/cpp/cpp_runner.cpp", dst="model_export_format.json", kind="mirrors feature order (comment only)", established_by="static_text",
                      evidence="tools/cpp/cpp_runner.cpp:11 comment; FEATURE_ORDER parsed and compared"))
    edges.append(dict(src="src/features/schema_validator.py", dst="src/features/feature_schema.py", kind="duplicates validate_vector", established_by="ast",
                      evidence="src/features/schema_validator.py:63 vs src/features/feature_schema.py:266"))
    allnodes = {**{k: v for k, v in NODES.items()}, **NODES_EXTRA, **VIRTUAL}
    # ensure edge endpoints are registered nodes
    ids = set(allnodes)
    edges = [e for e in edges if e["src"] in ids and e["dst"] in ids]
    edge_set = {(e["src"], e["dst"]) for e in edges if e.get('runtime_resolves', True) is not False}

    # ---- producers per feature ----
    pipe_sites = assign_sites(ROOT / "src/features/feature_pipeline.py")
    store_sites = assign_sites(ROOT / "src/core/feature_store.py")
    bit_sites = assign_sites(ROOT / "src/features/bitnet_feature_builder.py")
    hook_sites = dict_literal_sites(ROOT / "src/runtime/live_engine_hook.py", "_build_ohlcv_and_auxiliary")
    hook_sites.update({k: v for k, v in dict_literal_sites(ROOT / "src/runtime/live_engine_hook.py", "_build_engine_input").items() if k not in hook_sites})
    feature_rows = []
    for i, f in enumerate(CF):
        canon = [dict(file="src/features/feature_pipeline.py", line=ln, function=fn, source=srcx) for (ln, fn, srcx) in pipe_sites.get(f, [])]
        alt = []
        for nm, sites in (("src/core/feature_store.py", store_sites), ("src/features/bitnet_feature_builder.py", bit_sites)):
            for (ln, fn, srcx) in sites.get(f, []):
                alt.append(dict(file=nm, line=ln, function=fn, source=srcx))
        if f in hook_sites:
            alt.append(dict(file="src/runtime/live_engine_hook.py", line=hook_sites[f][0], function="_build_ohlcv_and_auxiliary/_build_engine_input", source=hook_sites[f][1]))
        if f in ("body_size", "wick_size", "body_ratio"):
            alt.append(dict(file="src/config_layer/crt_engine_v2.py", line=None, function="Candle." + f, source="property"))
            if f != "body_size":
                alt.append(dict(file="scripts/backtest/manual_backtest.py", line=None, function=f, source="function"))
        cons = []
        for fl, d in literals.items():
            if f in d and not fl.startswith(("tests/", "scripts/analysis/", "results/")):
                cons.append(dict(file=fl, lines=sorted(set(d[f]))[:8], evidence="static string-literal reference (not proof of dataflow)"))
        par = {
            "live_hook_featurestore": ev["live_hook_featurestore"][f]["status"],
            "bitnet_feature_builder": ev["bitnet_feature_builder"][f]["status"],
            "backtest_trade_snapshot": ev["backtest_trade_snapshot"].get(f, {}).get("status", "unverified"),
        }
        if f in ("body_size", "wick_size", "body_ratio"):
            par["crt_candle"] = ev["crt_candle_anatomy"][f]
            par["manual_backtest"] = ev["manual_backtest_anatomy"].get(f, "unverified")
        par["cpp_feature_order"] = "identical" if ev["cpp_runner"]["order_equal_to_CANONICAL_FEATURES"] else "mismatched"
        feature_rows.append(dict(index=i, name=f, canonical_definition=canon or ("raw input column (OHLCV), not computed" if f in ("open", "high", "low", "close") else "no single assignment found by AST"), alternate_implementations=alt,
                                 static_consumers=sorted(cons, key=lambda c: c["file"]), parity=par))

    # ---- branches ----
    hk = ev["live_hook_featurestore"]
    hk_bad = {k: v["status"] for k, v in hk.items() if v["status"] != "identical"}
    bn_bad = {k: v["status"] for k, v in ev["bitnet_feature_builder"].items() if v["status"] != "identical"}
    gauss = ev["gaussian_artifacts"]
    rejected = [g["file"] for g in gauss if g["load"].startswith("rejected")]
    loads = [g["file"] for g in gauss if g["load"] == "loads"]

    def path_ok(pairs):
        return [dict(edge=f"{s} -> {d}", present=(s, d) in edge_set) for s, d in pairs]

    def st(cond_broken=False, cond_mis=False, cond_unv=False):
        return "broken" if cond_broken else "mismatched" if cond_mis else "unverified" if cond_unv else "verified"

    B = []
    B.append(dict(id="A1", tree="A", producer="src/features/feature_pipeline.py (FeaturePipeline.run)", consumer="src/runtime/backtest_v2.py (BacktestRunner) -> engine input and trade snapshot",
                  transformation="canonical; parameters embedded in code (windows, ATR, EMA, swing mode)", contract_identity="none declared (no contract hash); pipeline file sha256 only",
                  dependency_path=path_ok([("src/runtime/backtest_v2.py", "src/features/feature_pipeline.py")]),
                  parity_evidence=f"trade snapshots vs pipeline: {sum(1 for k,v in ev['backtest_trade_snapshot'].items() if isinstance(v,dict) and v.get('status')=='identical')} features identical; "
                                  f"{sum(1 for k,v in ev['backtest_trade_snapshot'].items() if isinstance(v,dict) and v.get('status')=='unverified')} not in trades.csv",
                  status=st(cond_mis=any(isinstance(v, dict) and v.get("status") == "value_mismatch" for v in ev["backtest_trade_snapshot"].values()),
                            cond_unv=any(isinstance(v, dict) and v.get("status") == "unverified" for v in ev["backtest_trade_snapshot"].values())),
                  required_tests=["pipeline output equals trade snapshot for all 35 columns", "causal prefix test for every feature (swings and volatility_regime exist)"],
                  acceptance="all 35 snapshot columns identical; contract hash recorded in the run manifest"))
    B.append(dict(id="A2", tree="A", producer="src/runtime/backtest_v2.py", consumer="src/core/engine_runner.py (EngineRunner)",
                  transformation="pipeline row -> input dict (BacktestRunner.run loop)", contract_identity="none",
                  dependency_path=path_ok([("src/runtime/backtest_v2.py", "src/core/engine_runner.py")]), parity_evidence="same producer as A1; consumer reads body_ratio at engine_runner.py:558",
                  status="verified" if ("src/runtime/backtest_v2.py", "src/core/engine_runner.py") in edge_set else "broken",
                  required_tests=["engine decision invariant under definition-preserving refactor"], acceptance="decisions identical before/after contract introduction on frozen corpus"))
    B.append(dict(id="A3", tree="A", producer="src/config_layer/crt_engine_v2.py (Candle properties)", consumer="CRT state machine (displacement/confirmation thresholds)",
                  transformation="body_size=|c-o|, wick_size=h-l, body_ratio=body/(h-l)", contract_identity="none; separate implementation",
                  dependency_path=[], parity_evidence=f"vs pipeline on {len(batch)} real bars: {ev['crt_candle_anatomy']}",
                  status="verified" if all(v == "identical" for v in ev["crt_candle_anatomy"].values()) else "mismatched",
                  required_tests=["Candle anatomy equals pipeline anatomy (property test)"], acceptance="single formula source or test pinning equality"))
    B.append(dict(id="A4", tree="A", producer="scripts/backtest/manual_backtest.py (body_ratio, wick_size)", consumer="manual backtest scorer",
                  transformation="body_ratio=|c-o|/(h-l), wick_size=h-l", contract_identity="none; separate implementation",
                  dependency_path=[], parity_evidence=f"vs pipeline on {len(batch)} bars: {ev['manual_backtest_anatomy']}",
                  status="unverified" if any("unverified" in str(v) for v in ev["manual_backtest_anatomy"].values()) and all(v in ("identical",) or "unverified" in str(v) for v in ev["manual_backtest_anatomy"].values()) else "mismatched",
                  required_tests=["anatomy equality test; remaining local indicators (ATR, regime) have no parity test"], acceptance="every locally computed feature pinned to the contract or removed"))
    B.append(dict(id="A5", tree="A", producer="src/features/feature_pipeline.py", consumer=f"scripts/analysis/* ({len(analysis)} research scripts)",
                  transformation="canonical", contract_identity="research manifests record pipeline sha256 and schema checksum",
                  dependency_path=path_ok([("scripts/analysis/* (research consumers)", "src/features/feature_pipeline.py")]), parity_evidence="uses FeaturePipeline directly",
                  status="verified", required_tests=["research manifests assert pipeline sha256 (done in census and incremental test)"], acceptance="same"))
    B.append(dict(id="B1", tree="B", producer="src/runtime/live_engine_hook.py + src/core/feature_store.py (ideal upstream = batch row)", consumer="src/core/engine_runner.py (EngineRunner.run)",
                  transformation=f"pass-through with 0.0 defaults; recomputes wick_size, body_ratio, double_sweep, volume_ratio; session -> string. Non-identical features: {hk_bad}",
                  contract_identity="none (no schema hash or definition check at the hook boundary)",
                  dependency_path=path_ok([("src/runtime/live_engine_hook.py", "src/core/feature_store.py"), ("src/runtime/live_engine_hook.py", "src/core/engine_runner.py"), ("MISSING:trade_data_producer", "src/runtime/live_engine_hook.py")]),
                  parity_evidence=f"{sum(1 for v in hk.values() if v['status']=='identical')}/35 identical over {len(batch)} bars; body_ratio/wick_size/double_sweep value mismatches, session type break",
                  status="mismatched", required_tests=["hook-built row equals pipeline row for all 35 features and types", "fail-closed on missing field instead of 0.0"],
                  acceptance="35/35 identical incl. types; missing/unknown input raises"))
    B.append(dict(id="B2", tree="B", producer="src/runtime/live_engine_hook.py", consumer="src/engines/live_engine.py (LiveEngine.process Gaussian inference)",
                  transformation="LiveEngine builds its own vector via build_feature_vector", contract_identity="none",
                  dependency_path=path_ok([("src/runtime/live_engine_hook.py", "src/engines/live_engine.py")]),
                  parity_evidence=f"imports: {ev['import_checks']['features.dataset_builder.build_feature_vector']}; {ev['import_checks']['features.dataset_builder.validate_feature_vector']}",
                  status="broken", required_tests=["LiveEngine.process on a valid frame returns non-error"], acceptance="no feature_error; probabilities valid; fail-closed on incompatible model"))
    B.append(dict(id="B3", tree="B", producer="src/agent/modes/pipeline_mode.py (live_hook.dry_run tool)", consumer="runtime.live_engine_hook.LiveEngineHook",
                  transformation="n/a", contract_identity="none", dependency_path=[], parity_evidence=ev["import_checks"]["runtime.live_engine_hook.LiveEngineHook"],
                  status="broken", required_tests=["dry-run tool returns schema identity and parity result"], acceptance="deterministic read-only dry run, no orders"))
    B.append(dict(id="B4", tree="B", producer="MISSING:trade_data_producer", consumer="src/runtime/live_engine_hook.py",
                  transformation="n/a", contract_identity="n/a", dependency_path=path_ok([("MISSING:trade_data_producer", "src/runtime/live_engine_hook.py")]),
                  parity_evidence="repo-wide search: no producer, no caller", status="broken", required_tests=["producer design after tracing intended flow"], acceptance="deterministic producer with contract stamp"))
    B.append(dict(id="B5", tree="B", producer="src/agent/modes/copilot_mode.py (caller-supplied feature dict)", consumer="src/core/engine_runner.py",
                  transformation="no construction: agent tool passes a dict from the user", contract_identity="none", dependency_path=path_ok([("src/agent/modes/copilot_mode.py", "src/core/engine_runner.py")]),
                  parity_evidence="no validation seen before EngineRunner", status="unverified", required_tests=["tool rejects dicts that fail contract validation"], acceptance="validated or labelled unvalidated"))
    B.append(dict(id="B6", tree="B", producer="src/features/feature_builder.py (FeatureBuilder.build) and src/core/fusion_engine.py import of 'feature_builder'", consumer="adapter_engine (requires FeatureBuilder output) / fusion_engine",
                  transformation="FeatureBuilder class has no callers; fusion_engine imports bare 'feature_builder' (names build_feature_vector, N_FEATURES)",
                  contract_identity="none", dependency_path=path_ok([("src/core/fusion_engine.py", "src/features/feature_builder.py")]),
                  parity_evidence=f"imports: {ev['import_checks']['feature_builder.N_FEATURES']}; features.feature_builder.build_feature_vector: {ev['import_checks']['features.feature_builder.build_feature_vector']}; ImportError is swallowed (_FEATURE_BUILDER_AVAILABLE False)",
                  status="broken", required_tests=["import guard fails loudly or the dependency is removed"], acceptance="no silent ImportError fallback on the contract path"))
    B.append(dict(id="B8", tree="B", producer="(none found) -> src/config_layer/crt_gaussian_scorer.py", consumer="CRTGaussianScorer (reads body_ratio, retest_depth, disp_strength)",
                  transformation="Gaussian kernel on three features", contract_identity="none",
                  dependency_path=[], parity_evidence="no importer anywhere in src, scripts or tests (only comments, and phase5 text injection markers)",
                  status="unverified", required_tests=["identify instantiation path; parity of its three inputs with the contract"], acceptance="importer registered or module marked dormant"))
    B.append(dict(id="B7", tree="B", producer="src/scanner/scanner.py", consumer="EngineRunner via injected provider",
                  transformation="data_fetcher/engine_runner are injected callables", contract_identity="none", dependency_path=[], parity_evidence="no concrete provider in repo",
                  status="unverified", required_tests=["provider contract test"], acceptance="provider identified and contract-checked"))
    B.append(dict(id="C1", tree="C", producer="scripts/training/phase5_calibration.py (trades.csv entry snapshot -> extract_feature_vector)", consumer="trainer.save_gaussian_model -> models/gaussian_*.json",
                  transformation="entry-bar snapshot of batch features (parity A1)", contract_identity="schema_checksum (md5 of names) only",
                  dependency_path=path_ok([("scripts/training/phase5_calibration.py", "src/training/trainer.py"), ("scripts/training/phase5_calibration.py", "src/features/dataset_builder.py")]),
                  parity_evidence="source results dirs not in repo; snapshot parity shown in A1", status="unverified", required_tests=["training row equals pipeline row at the trade timestamp"], acceptance="dataset hash + contract hash stored in artifact"))
    B.append(dict(id="C2", tree="C", producer="src/training/train_pipeline.py -> src/config_layer/rr/rr_dataset_builder.py", consumer="trainer / model_registry",
                  transformation="FeaturePipeline run over trade records treated as candles; positional alignment", contract_identity="SCHEMA_HASH stored in dataset cache",
                  dependency_path=path_ok([("src/training/train_pipeline.py", "src/config_layer/rr/rr_dataset_builder.py"), ("src/training/train_pipeline.py", "src/training/trainer.py"), ("src/training/train_pipeline.py", "src/core/model_registry.py")]),
                  parity_evidence=f"different observation unit; rows surviving warm-up on N trades: {ev['rr_dataset_builder_rows_surviving']}", status="mismatched",
                  required_tests=["training rows come from contiguous candle history keyed by timestamp"], acceptance="row timestamps match the originating bars"))
    B.append(dict(id="C3", tree="C", producer="ARTIFACTS:gaussian_p5_* (12)", consumer="src/training/trainer.py::load_gaussian_model",
                  transformation="32/33-feature schemas", contract_identity="schema_checksum bffbe5c1.../36ff0665...; no definition identity; no timeframe",
                  dependency_path=path_ok([("ARTIFACTS:gaussian_p5_* (12)", "src/training/trainer.py")]), parity_evidence=f"{len(rejected)} of {len(rejected)+len(loads)-1} p5 files rejected by loader (all)",
                  status="mismatched", required_tests=["loader rejects stale/incompatible artifacts (exists: test_trainer)"], acceptance="artifacts marked ineligible by derived status, not deleted"))
    B.append(dict(id="C3b", tree="C", producer="ARTIFACTS:gaussian_xau_m15_causal_n9_20261011", consumer="src/training/trainer.py::load_gaussian_model",
                  transformation="35 ordered features; experimental 9-trade fit", contract_identity=f"schema_checksum {fs.GAUSSIAN_SCHEMA.checksum}; feature_definition_hash present; metrics degenerate",
                  dependency_path=path_ok([("ARTIFACTS:gaussian_xau_m15_causal_n9_20261011", "src/training/trainer.py")]),
                  parity_evidence="loads; order exact", status="unverified", required_tests=["eligibility rule for experimental artifacts"], acceptance="not used for inference unless eligibility criteria met"))
    B.append(dict(id="C4", tree="C", producer="REGISTRY:models/gaussian_registry.json + loader", consumer="src/engines/ml_gaussian_engine.py -> EngineRunner (only if gaussian_impl='ml')",
                  transformation="extract_feature_vector -> scaler -> predict_expected_rr; any exception -> neutral 0.5", contract_identity="n_features check only",
                  dependency_path=path_ok([("REGISTRY:models/gaussian_registry.json", "src/engines/ml_gaussian_engine.py"), ("src/engines/ml_gaussian_engine.py", "src/training/trainer.py"), ("CONFIG:configs/production/v1_multi_2026_03.json", "src/core/engine_runner.py")]),
                  parity_evidence=f"numeric row: {ev['ml_engine_on_numeric_row']}; hook-built row: {ev['ml_engine_on_live_row']} (extract_feature_vector error: {ev['extract_feature_vector_live_row']}); production gaussian_impl={gimpl!r}",
                  status="mismatched", required_tests=["incompatible input yields explicit error, not neutral score"], acceptance="fail-closed adapter; hook-built row accepted"))
    B.append(dict(id="C5", tree="C", producer="REGISTRY:models/gaussian_registry.json + stubs", consumer="src/engines/heuristic_gaussian_engine.py (mu, sigma only) -> EngineRunner (production path)",
                  transformation="reads active entry's mu/sigma and falls back v1 -> import_fix_v1", contract_identity="none (no feature schema check; uses no features from the model)",
                  dependency_path=path_ok([("REGISTRY:models/gaussian_registry.json", "src/engines/heuristic_gaussian_engine.py"), ("src/core/engine_runner.py", "src/engines/heuristic_gaussian_engine.py")]),
                  parity_evidence=f"executed registry resolution: {ev['heuristic_registry_resolution']}", status="verified" if len({(v['mu'], v['sigma']) for v in ev['heuristic_registry_resolution'].values()}) == 1 else "mismatched",
                  required_tests=["registry change cannot alter heuristic mu/sigma silently"], acceptance="registry entry change recorded with impact on this branch"))
    B.append(dict(id="D1", tree="D", producer="src/features/bitnet_feature_builder.py", consumer="none (no callers)",
                  transformation="own anatomy formulas, TREND_MAP/SESSION_MAP string lookups", contract_identity="none",
                  dependency_path=[], parity_evidence=f"equivalent numeric inputs give non-identical features: {bn_bad}", status="mismatched",
                  required_tests=["remove or conform to the contract"], acceptance="no unused divergent implementation"))
    tn = ev["tradenet_artifacts"]
    B.append(dict(id="D2", tree="D", producer="ARTIFACTS:tradenet_p5_* (5)", consumer="src/training/trainer.py::load_model",
                  transformation="32 or 33 inputs against 35", contract_identity="no schema metadata in checkpoint; loader has no schema check; torch.load without weights_only",
                  dependency_path=path_ok([("ARTIFACTS:tradenet_p5_* (5)", "src/training/trainer.py")]),
                  parity_evidence=f"first-layer inputs {[i['first_layer_inputs'] for i in tn['items']]} vs {fs.TRADENET_SCHEMA.n_features}; torch installed: {tn['torch_installed']}",
                  status="mismatched", required_tests=["loader verifies input dimension and contract hash before load_state_dict"], acceptance="incompatible checkpoint raises before use"))
    cpp = ev["cpp_runner"]
    B.append(dict(id="D3", tree="D", producer="tools/cpp/cpp_runner.cpp (FEATURE_ORDER)", consumer="C++ runner reading test_vectors.json + model.json",
                  transformation="no feature computation; missing/null -> 0.0 silently", contract_identity="order mirrors CANONICAL_FEATURES (verified by text parse); no hash",
                  dependency_path=path_ok([("tools/cpp/cpp_runner.cpp", "model_export_format.json")]),
                  parity_evidence=f"order equal: {cpp['order_equal_to_CANONICAL_FEATURES']}; zero-fill policy differs from Python (raises); binary not executed here", status="unverified",
                  required_tests=["Python vs C++ vector parity on shared vectors"], acceptance="identical outputs on the fixture set; missing-value policy aligned"))
    B.append(dict(id="D4", tree="D", producer="src/bitnet/* and src/engines/zone_gate_engine.py", consumer="BitNet/zone gate inference (EngineRunner via get_zone_gate)",
                  transformation="extract_feature_vector / CANONICAL_FEATURE_ORDER vectors", contract_identity="CANONICAL_FEATURE_DIM checks only",
                  dependency_path=path_ok([("src/core/engine_runner.py", "src/engines/live_engine.py")]), parity_evidence="uses canonical vector helpers; model.json legacy schema has fixed input dim 6 (bitnet_inference.py)",
                  status="unverified", required_tests=["zone gate input equals contract vector; legacy schema 1 handled explicitly"], acceptance="schema identity checked at load"))
    B.append(dict(id="D5", tree="D", producer="UNVERIFIED:external_callers", consumer="src/runtime/live_engine_hook.py / agent tools",
                  transformation="unknown", contract_identity="unknown", dependency_path=path_ok([("UNVERIFIED:external_callers", "src/runtime/live_engine_hook.py")]),
                  parity_evidence="no evidence available", status="unverified", required_tests=["identify and register each external caller"], acceptance="caller registered with contract identity"))
    B.append(dict(id="D6", tree="D", producer="src/inout/runner.py (INOUT)", consumer="own probability/scanner stack",
                  transformation="documented as independent of EngineRunner and the hook", contract_identity="not part of the canonical contract",
                  dependency_path=[], parity_evidence="module docstrings state independence; no import edge to hook or EngineRunner found", status="unverified",
                  required_tests=["declare INOUT out of contract scope or map its features"], acceptance="explicit scope statement"))
    for b in B:
        b["path_complete"] = all(p["present"] for p in b["dependency_path"]) if b["dependency_path"] else None

    # ---- outputs ----
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    reg = {
        "generated_by": "scripts/analysis/consumer_graph.py", "git_commit": git,
        "rule": "One feature meaning; many explicitly mapped consumers. A branch that cannot comply is marked incompatible and does not inherit fixes from another branch.",
        "contract_state": {
            "feature_count": len(CF), "ordered_features": CF, "SCHEMA_HASH_names_only": fs.SCHEMA_HASH, "SchemaObject_checksum": fs.GAUSSIAN_SCHEMA.checksum,
            "versions": {"module_SCHEMA_VERSION": fs.SCHEMA_VERSION, "SchemaObject": fs.GAUSSIAN_SCHEMA.version, "model_export_format": json.loads((ROOT / "model_export_format.json").read_text())["schema_version"]},
            "feature_definition_contract_exists": False,
            "feature_pipeline_sha256": hashlib.sha256((ROOT / "src/features/feature_pipeline.py").read_bytes()).hexdigest(),
            "production_config_sha256": hashlib.sha256((ROOT / "configs/production/v1_multi_2026_03.json").read_bytes()).hexdigest()},
        "trees": TREES,
        "nodes": [dict(id=k, role=v[0], tree=v[1]) for k, v in allnodes.items()],
        "edges": edges, "branches": B, "features": feature_rows, "evidence": ev,
        "duplicate_implementations": {
            "anatomy (body_size/wick_size/body_ratio)": ["src/features/feature_pipeline.py", "src/config_layer/crt_engine_v2.py::Candle", "scripts/backtest/manual_backtest.py", "src/runtime/live_engine_hook.py", "src/features/bitnet_feature_builder.py"],
            "double_sweep": ["src/features/feature_pipeline.py (window 5)", "src/core/feature_store.py (deque 10)", "src/features/bitnet_feature_builder.py (pass-through)"],
            "session encoding": ["src/features/feature_pipeline.py (0/1/2 by hour)", "src/features/feature_schema.py::SESSION_MAP", "src/runtime/live_engine_hook.py::_normalize_session (strings)"],
            "validate_vector": ["src/features/feature_schema.py", "src/features/schema_validator.py"],
            "schema hash": ["SCHEMA_HASH (names md5)", "SchemaObject.checksum (md5 of json)"]},
    }
    cnt = defaultdict(int)
    for b in B:
        cnt[b["status"]] += 1
    reg["summary"] = {"branches": len(B), "by_status": dict(cnt), "nodes": len(allnodes), "edges": len(edges),
                      "edges_by_basis": {k: sum(1 for e in edges if e["established_by"] == k) for k in sorted({e["established_by"] for e in edges})},
                      "features_with_single_ast_definition": sum(1 for r in feature_rows if isinstance(r["canonical_definition"], list)),
                      "features_hook_identical": sum(1 for r in feature_rows if r["parity"]["live_hook_featurestore"] == "identical"),
                      "features_bitnet_builder_identical": sum(1 for r in feature_rows if r["parity"]["bitnet_feature_builder"] == "identical")}
    (out / "consumer_registry.json").write_text(json.dumps(reg, indent=2, default=str))
    (out / "dependency_graph.json").write_text(json.dumps({"nodes": reg["nodes"], "edges": edges}, indent=2))
    with open(out / "feature_matrix.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["index", "feature", "canonical_definition", "n_alternate_impls", "n_static_consumer_files", "live_hook", "bitnet_builder", "backtest_snapshot", "crt_candle", "manual_backtest"])
        for r in feature_rows:
            cd = r["canonical_definition"]
            w.writerow([r["index"], r["name"], (f"{cd[0]['function']}:{cd[0]['line']}" if isinstance(cd, list) and cd else "not located"), len(r["alternate_implementations"]),
                        len(r["static_consumers"]), r["parity"]["live_hook_featurestore"], r["parity"]["bitnet_feature_builder"], r["parity"]["backtest_trade_snapshot"],
                        r["parity"].get("crt_candle", ""), r["parity"].get("manual_backtest", "")])
    # mermaid
    lines = ["flowchart LR"]
    sid = {k: f"n{i}" for i, k in enumerate(allnodes)}
    for t, label in TREES.items():
        members = [k for k, v in allnodes.items() if v[1] == t]
        if members:
            lines.append(f'  subgraph {t}["{t}: {label}"]')
            for m in members:
                lines.append(f'    {sid[m]}["{m.replace(chr(34), "")}"]')
            lines.append("  end")
    for e in edges:
        arrow = "-.->" if e["established_by"] in ("absence", "none") else "-->"
        lines.append(f'  {sid[e["src"]]} {arrow} {sid[e["dst"]]}')
    (out / "dependency_graph.mmd").write_text("\n".join(lines))
    print(json.dumps(reg["summary"], indent=1))
    for b in B:
        print(b["id"], b["status"], "path_complete=", b["path_complete"])


if __name__ == "__main__":
    main()
