"""
Analyze EngineRunner fusion shadow telemetry from collector logs.

Reads log lines that contain JSON collector records and compares:
  fusion.final_score (compute path) vs fusion.evaluate_shadow.final_score

Output:
  results/validation/automation/fusion_shadow_<timestamp>.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.console_safe import safe_print

try:
    from src.utils.integrity_events import emit_integrity_event  # noqa: F401
except Exception:  # pragma: no cover
    def emit_integrity_event(*_a, **_kw):  # type: ignore[no-redef]
        return None


def _safe_float(value: Any) -> float | None:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(num):
        return None
    return num


def _extract_json_payload(line: str) -> dict[str, Any] | None:
    line = line.strip()
    if not line:
        return None
    # Collector log lines are prefixed by logger metadata before JSON payload.
    idx = line.find("{")
    if idx < 0:
        return None
    payload = line[idx:]
    try:
        loaded = json.loads(payload)
    except json.JSONDecodeError as exc:
        emit_integrity_event(
            "JSONL_CORRUPTION",
            "WARNING",
            "src.runtime.analyze_fusion_shadow",
            {
                "raw_preview": payload[:160],
                "error":       str(exc),
            },
        )
        return None
    if isinstance(loaded, dict):
        return loaded
    return None


def analyze_log(log_path: Path) -> dict[str, Any]:
    total_records = 0
    fusion_records = 0
    shadow_records = 0
    missing_shadow_records = 0
    deltas: list[float] = []
    sample_ids: list[str] = []

    for raw_line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        payload = _extract_json_payload(raw_line)
        if not isinstance(payload, dict):
            continue
        total_records += 1

        fusion = payload.get("fusion")
        if not isinstance(fusion, dict):
            continue
        fusion_records += 1

        compute_score = _safe_float(fusion.get("final_score"))
        shadow = fusion.get("evaluate_shadow")
        if not isinstance(shadow, dict):
            missing_shadow_records += 1
            continue

        shadow_score = _safe_float(shadow.get("final_score"))
        if compute_score is None or shadow_score is None:
            missing_shadow_records += 1
            continue

        shadow_records += 1
        delta = shadow_score - compute_score
        deltas.append(delta)
        if len(sample_ids) < 10:
            sample_ids.append(str(payload.get("id", "unknown")))

    avg_delta = sum(deltas) / len(deltas) if deltas else 0.0
    abs_avg_delta = sum(abs(d) for d in deltas) / len(deltas) if deltas else 0.0

    return {
        "analyzed_at_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "source_log": str(log_path.resolve()),
        "records_total": total_records,
        "records_with_fusion": fusion_records,
        "records_with_shadow": shadow_records,
        "records_missing_shadow": missing_shadow_records,
        "delta_summary": {
            "count": len(deltas),
            "avg_delta_shadow_minus_compute": avg_delta,
            "avg_abs_delta": abs_avg_delta,
            "max_delta": max(deltas) if deltas else 0.0,
            "min_delta": min(deltas) if deltas else 0.0,
        },
        "sample_trade_ids": sample_ids,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze fusion evaluate_shadow telemetry.")
    parser.add_argument(
        "--log-path",
        default="logs/flow_collector.log",
        help="Collector log file path.",
    )
    parser.add_argument(
        "--output-dir",
        default="results/validation/automation",
        help="Directory for analysis output JSON.",
    )
    args = parser.parse_args()

    log_path = (ROOT_DIR / args.log_path).resolve()
    if not log_path.exists():
        safe_print(f"[analyze_fusion_shadow] log file not found: {log_path}")
        return 1

    summary = analyze_log(log_path)
    out_dir = (ROOT_DIR / args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = summary["analyzed_at_utc"]
    out_path = out_dir / f"fusion_shadow_{stamp}.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
    safe_print(f"[analyze_fusion_shadow] wrote {out_path}")
    safe_print(
        "[analyze_fusion_shadow] "
        f"shadow_records={summary['records_with_shadow']} "
        f"avg_abs_delta={summary['delta_summary']['avg_abs_delta']:.6f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
