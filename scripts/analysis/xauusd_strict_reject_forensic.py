#!/usr/bin/env python3
"""Replay strict-fetch REJECT for the 50,169-row XAUUSD artifact (read-only).

Does NOT write fingerprint reports. Prints gate decisions and exact missing
tradable timestamps when Jul-4 known_gap is ablated.

  python scripts/analysis/xauusd_strict_reject_forensic.py
"""
from __future__ import annotations

import copy
import json
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from config_layer.production_config import get_prod_section  # noqa: E402
from data_ingestion.dataset_integrity import (  # noqa: E402
    _parse_known_gaps,
    _stream_candles,
    validate_dataset,
)
from data_ingestion.session_autoderive import (  # noqa: E402
    derive_weekly_mask,
    is_tradable_by_mask,
)

PATH = ROOT / "data" / "mt5" / "_rejected" / "XAUUSD_M15.csv"
OUT = ROOT / "reports" / "xauusd_m15_strict_reject_forensic.json"


def main() -> int:
    if not PATH.is_file():
        print(f"missing {PATH}")
        return 1
    cfg = get_prod_section("dataset_integrity")
    strict = {k: v for k, v in cfg["strict_fetch"].items() if k != "_doc"}

    results = {}
    for label, override in [
        ("strict_current", strict),
        ("default", {}),
        (
            "strict_without_jul4_known_gap",
            {
                **strict,
                "session_calendar": {
                    **copy.deepcopy(cfg["session_calendar"]),
                    "known_gaps": [
                        g
                        for g in cfg["session_calendar"].get("known_gaps", [])
                        if not (
                            g.get("symbol") == "XAUUSD"
                            and str(g.get("from", "")).startswith("2026-07-03")
                        )
                    ],
                },
            },
        ),
        (
            "strict_without_any_xau_known_gaps",
            {
                **strict,
                "session_calendar": {
                    **copy.deepcopy(cfg["session_calendar"]),
                    "known_gaps": [
                        g
                        for g in cfg["session_calendar"].get("known_gaps", [])
                        if g.get("symbol") != "XAUUSD"
                    ],
                },
            },
        ),
    ]:
        rep = validate_dataset(
            str(PATH),
            instrument="XAUUSD",
            raise_on_fail=False,
            write_report=False,
            cfg_override=override or None,
        )
        results[label] = {
            "decision": rep.get("decision"),
            "hard_failures": rep.get("hard_failures"),
            "missing_pct": rep.get("missing_pct"),
            "largest_gap_candles": rep.get("largest_gap_candles"),
            "largest_gap_span_minutes": rep.get("largest_gap_span_minutes"),
            "rows": rep.get("rows"),
            "file_hash": rep.get("file_hash"),
        }
        print(label, rep.get("decision"), rep.get("hard_failures"))

    # exact missing tradable under no Jul-4
    ts_all = [t for _l, t, *_ in _stream_candles(PATH)]
    mask = derive_weekly_mask(ts_all, presence_min=0.5)
    holidays = set(cfg["session_calendar"].get("holidays", []))
    kg = [
        g
        for g in cfg["session_calendar"].get("known_gaps", [])
        if not (
            g.get("symbol") == "XAUUSD"
            and str(g.get("from", "")).startswith("2026-07-03")
        )
    ]
    known = _parse_known_gaps(kg, "XAUUSD")
    step = timedelta(minutes=15)

    def tradable(t):
        if any(lo <= t < hi for lo, hi in known):
            return False
        return is_tradable_by_mask(t, mask, holidays)

    missing = []
    prev = None
    for ts in ts_all:
        if prev is not None and (ts - prev) > step:
            t = prev + step
            while t < ts:
                if tradable(t):
                    missing.append(t.isoformat())
                t += step
        prev = ts

    payload = {
        "_doc": "Strict-REJECT forensic replay for XAUUSD 50169-row artifact. Read-only.",
        "path": str(PATH.relative_to(ROOT)).replace("\\", "/"),
        "gate_replays": results,
        "missing_tradable_without_jul4_known_gap": missing,
        "n_missing_tradable_without_jul4": len(missing),
        "reject_class": "CALENDAR_CONTRACT",
        "authority_status": "UNRESOLVED",
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"missing tradable without Jul-4: {len(missing)}")
    for m in missing:
        print(" ", m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
