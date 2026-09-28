#!/usr/bin/env python
"""parity_v5.py — STORY-83.6 five-surface parity, v5 shadow vs active v2.

Arm A is v2_htfcrt_2026_08. Arm B is v5_htfcrt_sot_dual_k23_2026_09.
Each arm runs in its own isolated config root (src/utils/isolated_config_root.py).
Ledger comparison is scripts/analysis/v3_config_parity.py:compare. This file does
not reimplement that comparison and does not edit any production config.

Known non-decision differences, listed in verdict.json:
  ignored: config_version, version, config_id, active_version, run_id (and
  label_run_id / preexisting_run_ids / trace_id / span_id), clock stamps
  (timestamp, generated_at, started_at, finished_at, duration_sec,
  generated_utc, label_generated_utc, built_at, summary artifact_timestamp),
  and resolver meta.json corpus_path. states.csv is the resolver surface.
  config_hash is a DECLARED difference (A 7de09f62... vs B e496a94c...),
  reported under declared_differences, never as DIFFERS.

USAGE
    python scripts/research/parity_v5.py --window short
    python scripts/research/parity_v5.py --window full
    # any two configs (EPIC-84 F1):
    python scripts/research/parity_v5.py --window short --arm-b v2_dispkill_shadow_2026_08 --label dispkill
    # same config, two code trees (EPIC-84 lane review): arm B runs from another worktree
    python scripts/research/parity_v5.py --window short --arm-b v2_htfcrt_2026_08 --code-b D:/Tradelatest-wt-<lane> --label <lane>
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "analysis"))

from utils.isolated_config_root import build_config_root, run_backtest  # noqa: E402
from v3_config_parity import (  # noqa: E402
    VERSION_STAMP_COLUMN,
    VOLATILE_SUMMARY_KEYS,
    compare,
)

import runtime.backtest_v2 as _bt_mod  # noqa: E402

ARM_A = "v2_htfcrt_2026_08"
ARM_B = "v5_htfcrt_sot_dual_k23_2026_09"
INSTRUMENT = "XAUUSD"

#: Code tree each arm runs from, keyed by the arm's isolated root (set in run_window).
#: Arm A always runs from REPO; arm B from REPO or from --code-b.
_ARM_REPO: dict = {}

WINDOWS = {
    "short": {
        "csv": "data/mt5/XAUUSD_W2026-07-06-to-2026-08-07.csv",
        "sha_prefix": "dcaf88a76b927d53",
        "rows": 2300,
    },
    "full": {
        "csv": "data/mt5/XAUUSD_M15.csv",
        "sha_prefix": "4d73f5cebe33ec91",
        "rows": 47275,
    },
}

# Non-decision fields. config_hash is NOT in this set: it is reported separately.
IGNORE_KEYS = set(VOLATILE_SUMMARY_KEYS) | {
    VERSION_STAMP_COLUMN,
    "version",
    "config_id",
    "active_version",
    "run_id",
    "label_run_id",
    "preexisting_run_ids",
    "trace_id",
    "span_id",
    # layer-trace run id copied onto every label row (lt_<utc>_<instrument>)
    "lt_id",
    "generated_utc",
    "label_generated_utc",
    "built_at",
    "artifact_timestamp",
}
# resolver meta.json only. states.csv is the resolver surface.
RESOLVER_META_IGNORE = IGNORE_KEYS | {"corpus_path"}
# Arm scratch paths and elapsed-time stamps inside the oracle manifest.
ORACLE_IGNORE = IGNORE_KEYS | {
    "artifact_path", "trace_source_path", "build_seconds", "elapsed_seconds",
}
#: Provenance fields that differ only because the arms run from different code trees.
CODE_TREE_PROVENANCE = {"corpus_path", "git_sha", "code_sha"}

DECLARED_HASH_WHY = (
    "DECLARED difference: params hash. A is 7de09f62... (5 params); "
    "B is e496a94c... (47 params). Not a behavior diff."
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _row_count(path: Path) -> int:
    with path.open("rb") as fh:
        return max(sum(1 for _ in fh) - 1, 0)


def _check_corpus(window: str) -> str:
    spec = WINDOWS[window]
    path = REPO / spec["csv"]
    if not path.is_file():
        raise SystemExit(f"BLOCKED: corpus missing: {path}")
    digest = _sha256(path)
    rows = _row_count(path)
    print(f"corpus {path.name} sha256={digest} rows={rows}", flush=True)
    if not digest.startswith(spec["sha_prefix"]) or rows != spec["rows"]:
        raise SystemExit(
            f"corpus {path.name} does not match the pinned identity "
            f"(got {digest[:16]} rows={rows}, expected {spec['sha_prefix']} "
            f"rows={spec['rows']})"
        )
    return spec["csv"]


def _env(repo: Path) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo / "src")
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _run(cmd: list[str], cwd: Path, label: str) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}  (cwd={cwd})", flush=True)
    proc = subprocess.run(
        cmd, cwd=str(cwd), env=_env(_ARM_REPO[Path(cwd)]), capture_output=True, text=True,
    )
    tail = ((proc.stdout or "") + "\n" + (proc.stderr or ""))[-4000:]
    if proc.returncode != 0:
        print(tail, flush=True)
        raise RuntimeError(f"{label} failed exit {proc.returncode}")
    if tail.strip():
        print(tail[-1500:], flush=True)
    return proc


def _declare_hash(declared: list, path: str, a, b) -> None:
    if a == b:
        return
    sig = (str(a), str(b))
    for item in declared:
        if item.get("_sig") == sig:
            item["occurrences"] = item.get("occurrences", 1) + 1
            return
    declared.append({
        "field": "config_hash",
        "path": path,
        "a": a,
        "b": b,
        "occurrences": 1,
        "why": DECLARED_HASH_WHY,
        "_sig": sig,
    })


def _deep_diffs(a, b, path: str, out: list, limit: int = 5,
                ignore: set | None = None, declared: list | None = None) -> None:
    if len(out) >= limit:
        return
    skip = IGNORE_KEYS if ignore is None else ignore
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            child = f"{path}.{key}" if path else key
            if key == "config_hash":
                if declared is not None:
                    _declare_hash(declared, child, a.get(key), b.get(key))
                continue
            if key in skip:
                continue
            if key not in a or key not in b:
                out.append({"path": child, "a": a.get(key), "b": b.get(key)})
                if len(out) >= limit:
                    return
                continue
            _deep_diffs(a[key], b[key], child, out, limit, skip, declared)
        return
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append({"path": path, "a_len": len(a), "b_len": len(b)})
            return
        for i, (x, y) in enumerate(zip(a, b)):
            _deep_diffs(x, y, f"{path}[{i}]", out, limit, skip, declared)
            if len(out) >= limit:
                return
        return
    if a != b:
        out.append({"path": path, "a": a, "b": b})


def _load_jsonl(path: Path) -> list:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _public_declared(declared: list) -> list:
    out = []
    for item in declared:
        cleaned = {k: v for k, v in item.items() if k != "_sig"}
        out.append(cleaned)
    return out


def _verdict(surface: str, path_a, path_b, n_a: int, n_b: int,
             diffs: list, extra: dict | None = None,
             ignored: set | None = None) -> dict:
    rec = {
        "surface": surface,
        "arm_a_path": str(path_a),
        "arm_b_path": str(path_b),
        "n_rows_a": n_a,
        "n_rows_b": n_b,
        "verdict": "IDENTICAL" if not diffs and n_a == n_b else "DIFFERS",
        "ignored_fields": sorted(IGNORE_KEYS if ignored is None else ignored),
        "first_diffs": diffs[:5],
    }
    if extra:
        rec.update(extra)
    print(
        f"{surface}: {rec['verdict']} rows {n_a}/{n_b} diffs {len(diffs)}",
        flush=True,
    )
    return rec


def _csv_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _surface_ledger(run_a: Path, run_b: Path) -> list[dict]:
    """Surfaces 1 and 2. compare() is the reused gate; the dict is the report."""
    print("\n== compare() events/telemetry/trades/summary ==", flush=True)
    compare_ok = compare(
        run_a, run_b, INSTRUMENT, f"{ARM_A} vs {ARM_B}",
        expect_version_stamp_differs=True,
    )
    print(f"compare() returned {compare_ok}", flush=True)

    trades_a = run_a / f"{INSTRUMENT}_trades.csv"
    trades_b = run_b / f"{INSTRUMENT}_trades.csv"
    ra = _csv_rows(trades_a) if trades_a.exists() else []
    rb = _csv_rows(trades_b) if trades_b.exists() else []
    declared: list = []
    trade_diffs: list = []
    if len(ra) != len(rb):
        trade_diffs.append({"path": "<row count>", "a": len(ra), "b": len(rb)})
    else:
        cols = sorted((set(ra[0]) | set(rb[0])) if ra else [])
        for i, (xa, xb) in enumerate(zip(ra, rb)):
            for col in cols:
                if col == "config_hash":
                    _declare_hash(declared, f"trades[{i}].config_hash", xa.get(col), xb.get(col))
                    continue
                if col in IGNORE_KEYS:
                    continue
                if xa.get(col) != xb.get(col):
                    trade_diffs.append({
                        "path": f"row[{i}].{col}", "a": xa.get(col), "b": xb.get(col),
                    })
                    if len(trade_diffs) >= 5:
                        break
            if len(trade_diffs) >= 5:
                break
    ledger = _verdict(
        "trade_ledger", run_a, run_b, len(ra), len(rb), trade_diffs,
        {"compare_returned": compare_ok},
    )
    if len(ra) == 0 and len(rb) == 0:
        ledger["note"] = (
            "0 trades on this window. The trade-ledger check proves nothing here."
        )

    ev_a = _load_jsonl(run_a / f"{INSTRUMENT}_events.jsonl")
    ev_b = _load_jsonl(run_b / f"{INSTRUMENT}_events.jsonl")
    tel_a = _load_jsonl(run_a / f"{INSTRUMENT}_crt_telemetry.jsonl")
    tel_b = _load_jsonl(run_b / f"{INSTRUMENT}_crt_telemetry.jsonl")
    state_diffs: list = []
    if len(ev_a) != len(ev_b):
        state_diffs.append({"path": "events.len", "a": len(ev_a), "b": len(ev_b)})
    else:
        for i, (xa, xb) in enumerate(zip(ev_a, ev_b)):
            _deep_diffs(xa, xb, f"events[{i}]", state_diffs, declared=declared)
            if len(state_diffs) >= 5:
                break
    if len(tel_a) != len(tel_b):
        state_diffs.append({"path": "telemetry.len", "a": len(tel_a), "b": len(tel_b)})
    else:
        for i, (xa, xb) in enumerate(zip(tel_a, tel_b)):
            before = len(state_diffs)
            _deep_diffs(xa, xb, f"telemetry[{i}]", state_diffs, declared=declared)
            if len(state_diffs) > before and len(state_diffs) >= 5:
                break
    state = _verdict(
        "engine_state", run_a, run_b, len(ev_a), len(ev_b), state_diffs[:5],
        {"telemetry_rows_a": len(tel_a), "telemetry_rows_b": len(tel_b),
         "compare_returned": compare_ok},
    )

    sum_a = json.loads((run_a / f"{INSTRUMENT}_summary.json").read_text(encoding="utf-8"))
    sum_b = json.loads((run_b / f"{INSTRUMENT}_summary.json").read_text(encoding="utf-8"))
    sum_diffs: list = []
    _deep_diffs(sum_a, sum_b, "summary", sum_diffs, declared=declared)
    # summary is part of the trade-ledger surface. Fold any non-ignored summary
    # diff into that surface so it cannot pass on trades alone.
    # artifact_timestamp is in IGNORE_KEYS. config_hash is declared, not a diff.
    if sum_diffs:
        ledger["first_diffs"] = (ledger["first_diffs"] + sum_diffs)[:5]
        ledger["verdict"] = "DIFFERS"
        print(f"trade_ledger: summary added {len(sum_diffs)} diffs -> DIFFERS", flush=True)
    if declared:
        ledger["declared_differences"] = _public_declared(declared)
        state["declared_differences"] = _public_declared(declared)
    return [ledger, state]


def _surface_resolver(root_a: Path, root_b: Path, corpus_rel: str) -> dict:
    py = sys.executable
    caches = {}
    for name, root in (("a", root_a), ("b", root_b)):
        csv_path = str(root / corpus_rel)
        code = (
            "from charts.resolver_overlay import build_and_cache\n"
            f"print(build_and_cache({INSTRUMENT!r}, {csv_path!r}))\n"
        )
        _run([py, "-c", code], root, f"resolver {name}")
        cache_root = root / "results" / "charts" / "_resolver_cache"
        dirs = sorted(p for p in cache_root.iterdir() if p.is_dir())
        if len(dirs) != 1:
            raise RuntimeError(f"resolver cache dirs in {cache_root}: {dirs}")
        caches[name] = dirs[0]
    states_a = caches["a"] / "states.csv"
    states_b = caches["b"] / "states.csv"
    byte_equal = states_a.read_bytes() == states_b.read_bytes()
    ra = _csv_rows(states_a)
    rb = _csv_rows(states_b)
    diffs: list = []
    if not byte_equal:
        if len(ra) != len(rb):
            diffs.append({"path": "states.len", "a": len(ra), "b": len(rb)})
        else:
            for i, (xa, xb) in enumerate(zip(ra, rb)):
                if xa != xb:
                    diffs.append({"path": f"states[{i}]", "a": xa, "b": xb})
                    if len(diffs) >= 5:
                        break
    meta_a = json.loads((caches["a"] / "meta.json").read_text(encoding="utf-8"))
    meta_b = json.loads((caches["b"] / "meta.json").read_text(encoding="utf-8"))
    meta_diffs: list = []
    _deep_diffs(meta_a, meta_b, "meta", meta_diffs, ignore=RESOLVER_META_IGNORE)
    diffs.extend(meta_diffs)
    ignored_obs = []
    for key in ("built_at", "corpus_path"):
        if meta_a.get(key) != meta_b.get(key):
            ignored_obs.append({
                "field": f"meta.{key}", "a": meta_a.get(key), "b": meta_b.get(key),
            })
    return _verdict(
        "resolver_states", caches["a"], caches["b"], len(ra), len(rb), diffs[:5],
        {"states_csv_byte_equal": byte_equal,
         "surface_file": "states.csv",
         "ignored_observations": ignored_obs},
        ignored=RESOLVER_META_IGNORE,
    )


def _layer_trace_paths(root: Path) -> Path:
    return root / "results" / "layer_trace" / f"{INSTRUMENT}_layer_trace.jsonl"


def _surface_layer_trace(root_a: Path, root_b: Path) -> dict:
    # Both configs carry layer_trace.enabled true. Cite the active file; v5 is the copy.
    cfg_a = json.loads(
        (_ARM_REPO[root_a] / "configs" / "production" / f"{ARM_A}.json").read_text(encoding="utf-8")
    )
    cfg_b = json.loads(
        (_ARM_REPO[root_b] / "configs" / "production" / f"{ARM_B}.json").read_text(encoding="utf-8")
    )
    en_a = bool(cfg_a.get("layer_trace", {}).get("enabled", True))
    en_b = bool(cfg_b.get("layer_trace", {}).get("enabled", True))
    path_a = _layer_trace_paths(root_a)
    path_b = _layer_trace_paths(root_b)
    if not en_a and not en_b:
        print(
            "layer_trace: NOT EMITTED "
            f"(v2 layer_trace.enabled false at configs/production/{ARM_A}.json; "
            f"v5 same key)",
            flush=True,
        )
        return {
            "surface": "layer_trace",
            "arm_a_path": str(path_a),
            "arm_b_path": str(path_b),
            "n_rows_a": 0,
            "n_rows_b": 0,
            "verdict": "NOT_EMITTED",
            "ignored_fields": sorted(IGNORE_KEYS),
            "first_diffs": [],
            "config_key": (
                f"configs/production/{ARM_A}.json layer_trace.enabled=false; "
                f"configs/production/{ARM_B}.json layer_trace.enabled=false"
            ),
        }
    rows_a = _load_jsonl(path_a) if path_a.exists() else []
    rows_b = _load_jsonl(path_b) if path_b.exists() else []

    def key_of(rec: dict):
        if rec.get("trade_id"):
            return ("trade_id", rec.get("trade_id"), rec.get("layer"), rec.get("bar_ts"))
        return (
            "bar", rec.get("bar_ts"), rec.get("bar_idx"), rec.get("layer"),
            rec.get("module"), rec.get("status"),
        )

    declared: list = []
    if rows_a and rows_b:
        _declare_hash(
            declared, "config_hash",
            rows_a[0].get("config_hash"), rows_b[0].get("config_hash"),
        )

    def canon(rec: dict) -> str:
        cleaned = {
            k: v for k, v in rec.items()
            if k not in IGNORE_KEYS and k != "config_hash"
        }
        return json.dumps(cleaned, sort_keys=True, default=str)

    from collections import defaultdict
    ga, gb = defaultdict(list), defaultdict(list)
    for rec in rows_a:
        ga[key_of(rec)].append(canon(rec))
    for rec in rows_b:
        gb[key_of(rec)].append(canon(rec))
    diffs = []
    for key in sorted(set(ga) | set(gb), key=str):
        if sorted(ga.get(key, [])) != sorted(gb.get(key, [])):
            diffs.append({
                "path": str(key),
                "a": ga.get(key, [])[:1],
                "b": gb.get(key, [])[:1],
            })
            if len(diffs) >= 5:
                break
    extra = {
        "enabled_a": en_a, "enabled_b": en_b,
        "join": "trade_id+layer+bar_ts when trade_id is set; else bar_ts+bar_idx+layer+module+status",
    }
    if declared:
        extra["declared_differences"] = _public_declared(declared)
    return _verdict(
        "layer_trace", path_a, path_b, len(rows_a), len(rows_b), diffs, extra,
    )


def _install_cost_calibration(root: Path) -> None:
    """Copy the SEM-015 calibration tree into this arm.

    labeler.py:413-418 globs ``<root>/results/research/xauusd_mt5_cost_calibration/*manifest_LATEST.json``.
    ``_ROOT`` there is the module repo (labeler.py:66). The arm's ``src`` junction
    resolves back to the worktree, so the worktree copy is what the glob hits.
    Each arm still receives its own copy, as specified.
    """
    src = REPO / "results" / "research" / "xauusd_mt5_cost_calibration"
    dst = root / "results" / "research" / "xauusd_mt5_cost_calibration"
    if not src.is_dir():
        raise RuntimeError(f"cost calibration dir missing: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=True)
    print(f"cost calibration -> {dst}", flush=True)


def _surface_oracle(root_a: Path, root_b: Path, corpus_rel: str,
                    trace_a: Path, trace_b: Path) -> dict:
    py = sys.executable
    outs = {}
    for name, root, trace in (
        ("a", root_a, trace_a), ("b", root_b, trace_b),
    ):
        matrix_dir = root / "results" / "bar_matrix"
        label_dir = root / "results" / "oracle_labels"
        matrix_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        lt_id = None
        if trace.exists():
            first = _load_jsonl(trace)
            if first:
                lt_id = first[0].get("run_id")
        cmd = [
            py, str(_ARM_REPO[root] / "scripts" / "research" / "build_bar_matrix.py"),
            "--instrument", INSTRUMENT, "--timeframe", "M15",
            "--csv", str(root / corpus_rel),
            "--out-dir", str(matrix_dir),
        ]
        if lt_id:
            cmd += ["--lt-id", lt_id, "--layer-trace-path", str(trace)]
        else:
            cmd.append("--no-trace-join")
        _run(cmd, root, f"bar_matrix {name}")
        _install_cost_calibration(root)
        _run([
            py, "-m", "research.oracle.labeler",
            "--instrument", INSTRUMENT, "--timeframe", "M15",
            "--matrix-dir", str(matrix_dir),
            "--out-dir", str(label_dir),
        ], root, f"labeler {name}")
        outs[name] = label_dir
    labels_a = outs["a"] / "labels.csv"
    labels_b = outs["b"] / "labels.csv"
    byte_equal = labels_a.read_bytes() == labels_b.read_bytes()
    ra = _csv_rows(labels_a)
    rb = _csv_rows(labels_b)
    diffs: list = []
    if not byte_equal:
        if len(ra) != len(rb):
            diffs.append({"path": "labels.len", "a": len(ra), "b": len(rb)})
        else:
            cols = sorted(set(ra[0]) | set(rb[0])) if ra else []
            for i, (xa, xb) in enumerate(zip(ra, rb)):
                for col in cols:
                    if col in ORACLE_IGNORE:
                        continue
                    if xa.get(col) != xb.get(col):
                        diffs.append({
                            "path": f"labels[{i}].{col}",
                            "a": xa.get(col), "b": xb.get(col),
                        })
                        if len(diffs) >= 5:
                            break
                if len(diffs) >= 5:
                    break
    man_a = json.loads((outs["a"] / "manifest.json").read_text(encoding="utf-8"))
    man_b = json.loads((outs["b"] / "manifest.json").read_text(encoding="utf-8"))
    man_diffs: list = []
    declared: list = []
    _deep_diffs(man_a, man_b, "manifest", man_diffs, ignore=ORACLE_IGNORE, declared=declared)
    diffs.extend(man_diffs)
    ignored_obs = []

    def _find(obj, key, acc):
        if isinstance(obj, dict):
            if key in obj:
                acc.append(obj[key])
            for v in obj.values():
                _find(v, key, acc)
        elif isinstance(obj, list):
            for v in obj:
                _find(v, key, acc)
    for key in ("artifact_path", "trace_source_path", "build_seconds", "elapsed_seconds", "lt_id"):
        fa, fb = [], []
        _find(man_a, key, fa)
        _find(man_b, key, fb)
        if fa != fb:
            ignored_obs.append({"field": f"manifest.{key}", "a": fa[:2], "b": fb[:2]})
    extra = {"labels_csv_byte_equal": byte_equal, "ignored_observations": ignored_obs}
    if declared:
        extra["declared_differences"] = _public_declared(declared)
    return _verdict(
        "oracle_labels", outs["a"], outs["b"], len(ra), len(rb), diffs[:5], extra,
        ignored=ORACLE_IGNORE,
    )


def run_window(window: str, code_b: Path, label: str) -> int:
    corpus_rel = _check_corpus(window)
    scratch = Path(tempfile.mkdtemp(prefix=f"parity_v5_{window}_"))
    print(f"scratch {scratch}", flush=True)
    print(f"arm A {ARM_A} code {REPO}; arm B {ARM_B} code {code_b}", flush=True)
    root_a = build_config_root(REPO, scratch / "arm_a", ARM_A)
    root_b = build_config_root(code_b, scratch / "arm_b", ARM_B)
    _ARM_REPO[root_a] = REPO
    _ARM_REPO[root_b] = code_b
    print("backtest arm A", flush=True)
    run_a = run_backtest(REPO, root_a, corpus_rel, INSTRUMENT, python=sys.executable)
    print(f"  -> {run_a}", flush=True)
    print("backtest arm B", flush=True)
    run_b = run_backtest(code_b, root_b, corpus_rel, INSTRUMENT, python=sys.executable)
    print(f"  -> {run_b}", flush=True)

    surfaces = _surface_ledger(run_a, run_b)
    surfaces.append(_surface_resolver(root_a, root_b, corpus_rel))
    surfaces.append(_surface_layer_trace(root_a, root_b))
    surfaces.append(_surface_oracle(
        root_a, root_b, corpus_rel,
        _layer_trace_paths(root_a), _layer_trace_paths(root_b),
    ))

    out_dir = REPO / "results" / "parity_v5" / (window if label == "v5" else f"{label}_{window}")
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "window": window,
        "corpus": corpus_rel,
        "arm_a": ARM_A,
        "arm_b": ARM_B,
        "code_a": str(REPO),
        "code_b": str(code_b),
        "scratch": str(scratch),
        "surfaces": surfaces,
    }
    dest = out_dir / "verdict.json"
    dest.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"wrote {dest}", flush=True)
    failed = [s["surface"] for s in surfaces if s["verdict"] == "DIFFERS"]
    print(f"verdict: {'PASS' if not failed else 'DIFFERS ' + ','.join(failed)}", flush=True)
    return 0 if not failed else 2


def main() -> int:
    global ARM_A, ARM_B
    print(f"self-check runtime.backtest_v2={_bt_mod.__file__}", flush=True)
    if REPO.resolve() not in Path(_bt_mod.__file__).resolve().parents:
        raise SystemExit(f"PYTHONPATH is not this worktree: {_bt_mod.__file__}")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--window", required=True, choices=sorted(WINDOWS))
    ap.add_argument("--arm-a", default=ARM_A, help="config version for arm A")
    ap.add_argument("--arm-b", default=ARM_B, help="config version for arm B")
    ap.add_argument("--code-b", default=None,
                    help="code tree (worktree root) arm B runs from; default this repo")
    ap.add_argument("--label", default="v5", help="results/parity_v5/<label>_<window>")
    args = ap.parse_args()

    ARM_A, ARM_B = args.arm_a, args.arm_b
    code_b = Path(args.code_b).resolve() if args.code_b else REPO
    if not (code_b / "src" / "runtime" / "backtest_v2.py").exists():
        raise SystemExit(f"--code-b is not a code tree: {code_b}")
    if code_b != REPO.resolve():
        # Two code trees: each arm stamps its own tree path and git sha into provenance
        # fields. Those are environment identity, not behaviour; ignore them (listed in
        # verdict.json as ignored_fields). Decision rows are still compared in full.
        IGNORE_KEYS.update(CODE_TREE_PROVENANCE)
        ORACLE_IGNORE.update(CODE_TREE_PROVENANCE | {"source"})
    try:
        return run_window(args.window, code_b, args.label)
    except Exception as exc:  # noqa: BLE001 — surface the arm failure and stop
        print(f"ERROR: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
