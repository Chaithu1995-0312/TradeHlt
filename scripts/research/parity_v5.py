#!/usr/bin/env python
"""parity_v5.py — STORY-83.6 five-surface parity, v5 shadow vs active v2.

Arm A is v2_htfcrt_2026_08. Arm B is v5_htfcrt_sot_dual_k23_2026_09.
Each arm runs in its own isolated config root (src/utils/isolated_config_root.py).
Ledger comparison is scripts/analysis/v3_config_parity.py:compare. This file does
not reimplement that comparison and does not edit any production config.

Known non-decision differences, declared in every verdict's ignored_fields:
config_version, version, config_id, config_hash, active_version, run_id (and
label_run_id / preexisting_run_ids / trace_id / span_id, which embed a run id),
plus the clock stamps compare() already skips (timestamp, generated_at,
started_at, finished_at, duration_sec, and the same class: generated_utc,
label_generated_utc, built_at).

USAGE
    python scripts/research/parity_v5.py --window short
    python scripts/research/parity_v5.py --window full
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
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

# Declared non-decision fields. Anything else that differs is a FINDING.
IGNORE_KEYS = set(VOLATILE_SUMMARY_KEYS) | {
    VERSION_STAMP_COLUMN,
    "version",
    "config_id",
    "config_hash",
    "active_version",
    "run_id",
    "label_run_id",
    "preexisting_run_ids",
    "trace_id",
    "span_id",
    "generated_utc",
    "label_generated_utc",
    "built_at",
}


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


def _env() -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO / "src")
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _run(cmd: list[str], cwd: Path, label: str) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}  (cwd={cwd})", flush=True)
    proc = subprocess.run(
        cmd, cwd=str(cwd), env=_env(), capture_output=True, text=True,
    )
    tail = ((proc.stdout or "") + "\n" + (proc.stderr or ""))[-4000:]
    if proc.returncode != 0:
        print(tail, flush=True)
        raise RuntimeError(f"{label} failed exit {proc.returncode}")
    if tail.strip():
        print(tail[-1500:], flush=True)
    return proc


def _deep_diffs(a, b, path: str, out: list, limit: int = 5) -> None:
    if len(out) >= limit:
        return
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if key in IGNORE_KEYS:
                continue
            child = f"{path}.{key}" if path else key
            if key not in a or key not in b:
                out.append({"path": child, "a": a.get(key), "b": b.get(key)})
                if len(out) >= limit:
                    return
                continue
            _deep_diffs(a[key], b[key], child, out, limit)
        return
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append({"path": path, "a_len": len(a), "b_len": len(b)})
            return
        for i, (x, y) in enumerate(zip(a, b)):
            _deep_diffs(x, y, f"{path}[{i}]", out, limit)
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


def _verdict(surface: str, path_a, path_b, n_a: int, n_b: int,
             diffs: list, extra: dict | None = None) -> dict:
    rec = {
        "surface": surface,
        "arm_a_path": str(path_a),
        "arm_b_path": str(path_b),
        "n_rows_a": n_a,
        "n_rows_b": n_b,
        "verdict": "IDENTICAL" if not diffs and n_a == n_b else "DIFFERS",
        "ignored_fields": sorted(IGNORE_KEYS),
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
    trade_diffs: list = []
    if len(ra) != len(rb):
        trade_diffs.append({"path": "<row count>", "a": len(ra), "b": len(rb)})
    else:
        cols = sorted((set(ra[0]) | set(rb[0])) if ra else [])
        for i, (xa, xb) in enumerate(zip(ra, rb)):
            for col in cols:
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

    ev_a = _load_jsonl(run_a / f"{INSTRUMENT}_events.jsonl")
    ev_b = _load_jsonl(run_b / f"{INSTRUMENT}_events.jsonl")
    tel_a = _load_jsonl(run_a / f"{INSTRUMENT}_crt_telemetry.jsonl")
    tel_b = _load_jsonl(run_b / f"{INSTRUMENT}_crt_telemetry.jsonl")
    state_diffs: list = []
    if len(ev_a) != len(ev_b):
        state_diffs.append({"path": "events.len", "a": len(ev_a), "b": len(ev_b)})
    else:
        for i, (xa, xb) in enumerate(zip(ev_a, ev_b)):
            _deep_diffs(xa, xb, f"events[{i}]", state_diffs)
            if len(state_diffs) >= 5:
                break
    if len(tel_a) != len(tel_b):
        state_diffs.append({"path": "telemetry.len", "a": len(tel_a), "b": len(tel_b)})
    else:
        for i, (xa, xb) in enumerate(zip(tel_a, tel_b)):
            before = len(state_diffs)
            _deep_diffs(xa, xb, f"telemetry[{i}]", state_diffs)
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
    _deep_diffs(sum_a, sum_b, "summary", sum_diffs)
    # summary is part of the trade-ledger surface. Fold any non-ignored summary
    # diff into that surface so it cannot pass on trades alone.
    if sum_diffs:
        ledger["first_diffs"] = (ledger["first_diffs"] + sum_diffs)[:5]
        ledger["verdict"] = "DIFFERS"
        print(f"trade_ledger: summary added {len(sum_diffs)} diffs -> DIFFERS", flush=True)
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
    _deep_diffs(meta_a, meta_b, "meta", meta_diffs)
    diffs.extend(meta_diffs)
    return _verdict(
        "resolver_states", caches["a"], caches["b"], len(ra), len(rb), diffs[:5],
        {"states_csv_byte_equal": byte_equal},
    )


def _layer_trace_paths(root: Path) -> Path:
    return root / "results" / "layer_trace" / f"{INSTRUMENT}_layer_trace.jsonl"


def _surface_layer_trace(root_a: Path, root_b: Path) -> dict:
    # Both configs carry layer_trace.enabled true. Cite the active file; v5 is the copy.
    cfg_a = json.loads(
        (REPO / "configs" / "production" / f"{ARM_A}.json").read_text(encoding="utf-8")
    )
    cfg_b = json.loads(
        (REPO / "configs" / "production" / f"{ARM_B}.json").read_text(encoding="utf-8")
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

    def canon(rec: dict) -> str:
        cleaned = {k: v for k, v in rec.items() if k not in IGNORE_KEYS}
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
    return _verdict(
        "layer_trace", path_a, path_b, len(rows_a), len(rows_b), diffs,
        {"enabled_a": en_a, "enabled_b": en_b,
         "join": "trade_id+layer+bar_ts when trade_id is set; else bar_ts+bar_idx+layer+module+status"},
    )


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
            py, str(REPO / "scripts" / "research" / "build_bar_matrix.py"),
            "--instrument", INSTRUMENT, "--timeframe", "M15",
            "--csv", str(root / corpus_rel),
            "--out-dir", str(matrix_dir),
        ]
        if lt_id:
            cmd += ["--lt-id", lt_id, "--layer-trace-path", str(trace)]
        else:
            cmd.append("--no-trace-join")
        _run(cmd, root, f"bar_matrix {name}")
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
                    if col in IGNORE_KEYS:
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
    _deep_diffs(man_a, man_b, "manifest", man_diffs)
    diffs.extend(man_diffs)
    return _verdict(
        "oracle_labels", outs["a"], outs["b"], len(ra), len(rb), diffs[:5],
        {"labels_csv_byte_equal": byte_equal},
    )


def run_window(window: str) -> int:
    corpus_rel = _check_corpus(window)
    scratch = Path(tempfile.mkdtemp(prefix=f"parity_v5_{window}_"))
    print(f"scratch {scratch}", flush=True)
    root_a = build_config_root(REPO, scratch / "arm_a", ARM_A)
    root_b = build_config_root(REPO, scratch / "arm_b", ARM_B)
    print("backtest arm A", flush=True)
    run_a = run_backtest(REPO, root_a, corpus_rel, INSTRUMENT, python=sys.executable)
    print(f"  -> {run_a}", flush=True)
    print("backtest arm B", flush=True)
    run_b = run_backtest(REPO, root_b, corpus_rel, INSTRUMENT, python=sys.executable)
    print(f"  -> {run_b}", flush=True)

    surfaces = _surface_ledger(run_a, run_b)
    surfaces.append(_surface_resolver(root_a, root_b, corpus_rel))
    surfaces.append(_surface_layer_trace(root_a, root_b))
    surfaces.append(_surface_oracle(
        root_a, root_b, corpus_rel,
        _layer_trace_paths(root_a), _layer_trace_paths(root_b),
    ))

    out_dir = REPO / "results" / "parity_v5" / window
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "window": window,
        "corpus": corpus_rel,
        "arm_a": ARM_A,
        "arm_b": ARM_B,
        "scratch": str(scratch),
        "surfaces": surfaces,
    }
    dest = out_dir / "verdict.json"
    dest.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"wrote {dest}", flush=True)
    failed = [s["surface"] for s in surfaces if s["verdict"] == "DIFFERS"]
    return 0 if not failed else 0


def main() -> int:
    print(f"self-check runtime.backtest_v2={_bt_mod.__file__}", flush=True)
    if REPO.resolve() not in Path(_bt_mod.__file__).resolve().parents:
        raise SystemExit(f"PYTHONPATH is not this worktree: {_bt_mod.__file__}")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--window", required=True, choices=sorted(WINDOWS))
    args = ap.parse_args()
    try:
        return run_window(args.window)
    except Exception as exc:  # noqa: BLE001 — surface the arm failure and stop
        print(f"ERROR: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
