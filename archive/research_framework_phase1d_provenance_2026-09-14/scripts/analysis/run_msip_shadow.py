#!/usr/bin/env python3
"""Batch MSIP shadow runner (OBSERVATION_ONLY).

Reads frozen OHLCV → FeaturePipeline → MarketStateVector JSONL.
Optional CRT co-run is observation-only (separate object graph; never feeds CRT).

Does NOT write production configs or mutate CRT authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features.feature_schema import FEATURE_ORDER_HASH, SCHEMA_HASH  # noqa: E402
from msip.disagreement import classify_disagreements, emit_disagreement_jsonl  # noqa: E402
from msip.interpretation_config import (  # noqa: E402
    default_experimental_section,
    load_msip_shadow_config,
)
from msip.shadow_emitter import (  # noqa: E402
    ProvenanceContext,
    build_market_state,
    emit_jsonl,
    observe_crt_state,
    stable_json_bytes,
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_commit(root: Path) -> str | None:
    head = root / ".git" / "HEAD"
    if not head.is_file():
        return None
    try:
        ref = head.read_text(encoding="utf-8").strip()
        if ref.startswith("ref:"):
            ref_path = root / ".git" / ref.split(" ", 1)[1].strip()
            if ref_path.is_file():
                return ref_path.read_text(encoding="utf-8").strip()[:40]
        return ref[:40]
    except Exception:
        return None


def _load_ohlcv(path: Path, limit: int | None) -> pd.DataFrame:
    df = pd.read_csv(path)
    # normalize columns
    cols = {c.lower(): c for c in df.columns}
    rename = {}
    for want in ("timestamp", "open", "high", "low", "close", "volume"):
        for k, orig in cols.items():
            if k == want or k.replace(" ", "_") == want:
                rename[orig] = want
                break
    df = df.rename(columns=rename)
    if "timestamp" not in df.columns:
        # try first column
        df = df.rename(columns={df.columns[0]: "timestamp"})
    if limit is not None:
        df = df.iloc[: int(limit)].copy()
    return df


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="MSIP shadow batch runner (OBSERVATION_ONLY)")
    p.add_argument(
        "--csv",
        type=Path,
        default=_ROOT / "data" / "mt5" / "XAUUSD_M15.csv",
        help="OHLCV CSV (default Phase-1 XAUUSD path)",
    )
    p.add_argument("--symbol", default="XAUUSD")
    p.add_argument("--timeframe", default="M15")
    p.add_argument("--limit", type=int, default=500, help="Bar cap (default 500)")
    p.add_argument("--run-id", default=None)
    p.add_argument(
        "--config-json",
        type=Path,
        default=None,
        help="JSON file with msip_shadow section or full prod-like dict",
    )
    p.add_argument("--with-how-labels", action="store_true")
    p.add_argument(
        "--out-root",
        type=Path,
        default=_ROOT / "results" / "msip_shadow",
    )
    p.add_argument(
        "--expected-corpus-sha256",
        default="4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56",
        help="Phase-1 pin; set empty to skip check",
    )
    args = p.parse_args(argv)

    csv_path = args.csv.resolve()
    if not csv_path.is_file():
        print(f"ERROR: corpus not found: {csv_path}", file=sys.stderr)
        return 2

    corpus_sha = _sha256_file(csv_path)
    if args.expected_corpus_sha256 and corpus_sha != args.expected_corpus_sha256:
        print(
            f"ERROR: corpus sha mismatch\n  got  {corpus_sha}\n"
            f"  want {args.expected_corpus_sha256}",
            file=sys.stderr,
        )
        return 3

    if args.config_json:
        raw = json.loads(args.config_json.read_text(encoding="utf-8"))
        if "msip_shadow" in raw:
            prod_like = raw
        else:
            prod_like = {"msip_shadow": raw}
    else:
        prod_like = {
            "msip_shadow": default_experimental_section(
                with_how_labels=args.with_how_labels
            )
        }

    cfg = load_msip_shadow_config(prod_like)
    if not getattr(cfg, "enabled", False):
        print("shadow disabled by config", file=sys.stderr)
        return 4

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.out_root / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    market_path = out_dir / "market_state.jsonl"
    disagree_path = out_dir / "disagreement.jsonl"
    if market_path.exists():
        market_path.unlink()
    if disagree_path.exists():
        disagree_path.unlink()

    df = _load_ohlcv(csv_path, args.limit)
    pipeline = FeaturePipeline(df)
    enriched, _vectors = pipeline.run()

    prov = ProvenanceContext(
        config_id=cfg.config_id,
        config_sha256=cfg.config_sha256,
        repository_commit=_git_commit(_ROOT),
        corpus_path=str(csv_path.relative_to(_ROOT)) if csv_path.is_relative_to(_ROOT) else str(csv_path),
        corpus_sha256=corpus_sha,
        feature_schema_hash=SCHEMA_HASH,
        feature_order_hash=FEATURE_ORDER_HASH,
        parity_audit_refs=[],
    )

    n_complete = 0
    n_partial = 0
    n_total = 0
    det_hashes: list[str] = []

    for i, (idx, row) in enumerate(enriched.iterrows()):
        bar_features = row.to_dict()
        ts = bar_features.get("timestamp", idx)
        # No CRT co-run in default path — observation optional null
        crt_obs = observe_crt_state({"observed": False})
        vec = build_market_state(
            bar_features,
            cfg,
            prov,
            crt_obs=crt_obs if cfg.crt_phase_observation_enabled else None,
            symbol=args.symbol,
            timeframe=args.timeframe,
            bar_timestamp=str(ts),
            bar_index=int(i),
        )
        if vec is None:
            continue
        emit_jsonl(market_path, vec)
        n_total += 1
        if vec.status == "COMPLETE":
            n_complete += 1
        else:
            n_partial += 1
        det_hashes.append(hashlib.sha256(stable_json_bytes(vec)).hexdigest())
        if cfg.emit_disagreement_events:
            recs = classify_disagreements(vec, crt_state=None)
            if recs:
                emit_disagreement_jsonl(disagree_path, recs)

    coverage = (n_complete / n_total) if n_total else 0.0
    manifest = {
        "schema_id": "MSIP_SHADOW_RUN_MANIFEST_V1",
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "task_class": "OBSERVATION_ONLY",
        "implementation_authorized": "NARROW_SHADOW_ONLY",
        "affects_crt": False,
        "affects_execution": False,
        "symbol": args.symbol,
        "timeframe": args.timeframe,
        "corpus_path": prov.corpus_path,
        "corpus_sha256": corpus_sha,
        "config_id": cfg.config_id,
        "config_sha256": cfg.config_sha256,
        "feature_schema_hash": SCHEMA_HASH,
        "feature_order_hash": FEATURE_ORDER_HASH,
        "repository_commit": prov.repository_commit,
        "bars_input_limit": args.limit,
        "bars_enriched": int(len(enriched)),
        "bars_emitted": n_total,
        "bars_complete": n_complete,
        "bars_partial": n_partial,
        "coverage_complete": coverage,
        "metrics": {
            "COV-01": coverage,
            "DET-01": "run_twice_externally",
            "PROV-01": "per_bar_status",
        },
        "output": {
            "market_state_jsonl": str(market_path.relative_to(_ROOT))
            if market_path.is_relative_to(_ROOT)
            else str(market_path),
            "disagreement_jsonl": str(disagree_path.relative_to(_ROOT))
            if disagree_path.is_relative_to(_ROOT)
            else str(disagree_path),
        },
        "payload_sha256_chain": hashlib.sha256(
            "".join(det_hashes).encode("utf-8")
        ).hexdigest()
        if det_hashes
        else None,
        "G-SHADOW-01": "NOT_EVALUATED_IN_RUNNER",
        "G-MIG-01": "CLOSED",
    }
    man_path = out_dir / "run_manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": run_id, "coverage_complete": coverage, "bars_emitted": n_total}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
