"""
verify — reconcile MT5 truth ↔ persisted artifacts (Phase 6).

Pure `reconcile()` core (CI-testable with fixtures, no terminal) + a thin live `run()`
wrapper. Three checks:

  1. Round-trip integrity — expected `episode_id`s (re-reconstructed from deals) vs the
     ids on disk: missing / orphan / duplicate.
  2. Independent P/L oracle — Σ raw-deal cashflow (profit+swap+commission) per position_id,
     computed directly from deals (NOT via reconstruction), vs Σ artifact `net_pnl` per
     position_id. This catches a reconstruction *or* an artifact P/L error.
  3. Manifest integrity — recompute `records_sha256` over each partition's records and
     compare to its `manifest.json.sha256`; assert provenance keys present.

A zero-trade input reconciles to all-zeros ⇒ PASS.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
from collections import Counter, defaultdict
from pathlib import Path

from ..analytics_config import _require, load_config
from ..engines.position_reconstructor import (
    is_position_deal,
    reconstruct_position_episodes,
)
from ..schemas.verification_report_v1_0 import VerificationReport
from ..storage.manifest_builder import records_sha256
from utils.jsonl_writer import append_jsonl  # type: ignore

_MANIFEST_PROVENANCE = ("records", "sha256", "source_history_window",
                        "engine_registry_hash", "python_version")


def _read_partition(path: Path, errors_path: Path) -> list[dict]:
    """Read a partition's JSONL; corrupt lines are logged + skipped (counted by caller)."""
    out: list[dict] = []
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            append_jsonl(errors_path, {"file": str(path), "line": raw[:200],
                                       "error": "json_decode"}, fail_silent=True)
            out.append({"__corrupt__": True})
    return out


def reconcile(deals, artifact_root, *, tol: float = 1e-6, cfg: "dict | None" = None,
              window: "dict | None" = None) -> VerificationReport:
    """Reconcile reconstructed truth + raw-deal P/L against on-disk artifacts."""
    cfg = cfg or load_config()
    root = Path(artifact_root)
    errors_path = root / "analytics" / "errors.jsonl"
    report = VerificationReport(window=window or {"from": None, "to": None})

    expected = reconstruct_position_episodes(deals)
    expected_ids = {e.episode_id for e in expected}
    report.mt5_positions = len({e.position_id for e in expected})

    # read all episode records on disk
    on_disk: list[dict] = []
    for f in sorted(root.glob("episodes/*/*/*/episodes.jsonl")):
        on_disk.extend(_read_partition(f, errors_path))
    report.corrupt_lines = sum(1 for r in on_disk if r.get("__corrupt__"))
    on_disk = [r for r in on_disk if not r.get("__corrupt__")]
    report.artifact_episodes = len(on_disk)

    # 1 — round-trip integrity
    disk_ids = [r.get("episode_id") for r in on_disk]
    counts = Counter(disk_ids)
    report.duplicate = sorted(i for i, c in counts.items() if c > 1 and i is not None)
    disk_id_set = set(disk_ids)
    report.missing = sorted(expected_ids - disk_id_set)
    report.orphan = sorted(disk_id_set - expected_ids)

    # 2 — independent P/L oracle (raw-deal cashflow per position_id)
    mt5_pnl: dict[int, float] = defaultdict(float)
    for d in deals:
        if not is_position_deal(d):
            continue   # exclude account ops (deposits/credits) from the P/L oracle
        pid = int(d["position_id"])
        mt5_pnl[pid] += (float(d.get("profit", 0.0) or 0.0)
                         + float(d.get("swap", 0.0) or 0.0)
                         + float(d.get("commission", 0.0) or 0.0))
    art_pnl: dict[int, float] = defaultdict(float)
    art_vol: dict[int, float] = defaultdict(float)
    for r in on_disk:
        pid = int(r["position_id"])
        art_pnl[pid] += float(r.get("net_pnl", 0.0) or 0.0)
        art_vol[pid] += float(r.get("volume", 0.0) or 0.0)
    report.net_pnl_diff = sum(
        abs(mt5_pnl.get(p, 0.0) - art_pnl.get(p, 0.0))
        for p in set(mt5_pnl) | set(art_pnl)
    )

    # volume round-trip (expected reconstruction vs artifact)
    exp_vol: dict[int, float] = defaultdict(float)
    for e in expected:
        exp_vol[e.position_id] += e.volume
    report.volume_diff = sum(
        abs(exp_vol.get(p, 0.0) - art_vol.get(p, 0.0))
        for p in set(exp_vol) | set(art_vol)
    )

    # 3 — manifest integrity
    for data_file in sorted(root.glob("episodes/*/*/*/episodes.jsonl")):
        manifest_file = data_file.parent / "manifest.json"
        recs = [r for r in _read_partition(data_file, errors_path)
                if not r.get("__corrupt__")]
        if not manifest_file.exists():
            report.manifests_ok = False
            report.discrepancies.append(f"missing manifest: {manifest_file}")
            continue
        m = json.loads(manifest_file.read_text(encoding="utf-8"))
        if records_sha256(recs) != m.get("sha256"):
            report.manifests_ok = False
            report.discrepancies.append(f"sha256 mismatch: {data_file}")
        missing_keys = [k for k in _MANIFEST_PROVENANCE if k not in m]
        if missing_keys:
            report.manifests_ok = False
            report.discrepancies.append(f"manifest missing {missing_keys}: {manifest_file}")

    # verdict
    if report.missing:
        report.discrepancies.append(f"{len(report.missing)} missing episode_id(s)")
    if report.orphan:
        report.discrepancies.append(f"{len(report.orphan)} orphan episode_id(s)")
    if report.duplicate:
        report.discrepancies.append(f"{len(report.duplicate)} duplicate episode_id(s)")
    if report.net_pnl_diff > tol:
        report.discrepancies.append(f"net_pnl diff {report.net_pnl_diff:.6f}")
    if report.volume_diff > tol:
        report.discrepancies.append(f"volume diff {report.volume_diff:.6f}")

    ok = (not report.missing and not report.orphan and not report.duplicate
          and report.net_pnl_diff <= tol and report.volume_diff <= tol
          and report.manifests_ok)
    report.status = "PASS" if ok else "FAIL"
    return report


def run(date_from: _dt.datetime, date_to: _dt.datetime, *, cfg: "dict | None" = None):
    """Live wrapper: read MT5 deals for the window, reconcile, write report + audit."""
    from .audit import append_audit
    from .mt5_adapter import MT5Adapter

    cfg = cfg or load_config()
    artifact_root = str(_require(cfg, "artifact_root"))
    report_root = Path(str(_require(cfg, "report_root")))
    window = {"from": date_from.strftime("%Y-%m-%d"), "to": date_to.strftime("%Y-%m-%d")}

    with MT5Adapter(server_utc_offset_hours=cfg.get("server_utc_offset_hours")) as adapter:
        deals = adapter.history_deals_get(date_from, date_to)
    report = reconcile(deals, artifact_root, cfg=cfg, window=window)

    out = report_root / "verification" / "daily_verification.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.to_markdown(), encoding="utf-8")
    append_audit("verification_run", report.to_audit_dict(), cfg=cfg)
    return report


def _parse_date(s: str) -> _dt.datetime:
    return _dt.datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=_dt.timezone.utc)


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description="MT5 analytics verification")
    ap.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD (UTC)")
    ap.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD (UTC)")
    args = ap.parse_args(argv)
    report = run(_parse_date(args.date_from), _parse_date(args.date_to))
    try:
        from utils.console_safe import safe_print  # type: ignore
        safe_print(report.to_markdown())
    except Exception:
        print(report.to_markdown().encode("ascii", "replace").decode("ascii"))
    return 0 if report.status == "PASS" else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
