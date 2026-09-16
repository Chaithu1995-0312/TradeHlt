"""REM-TG-01 (+ TG-02 format, TG-04 fingerprint): live_alert_v1 -> TelegramBridge.

RESEARCH_ONLY. Default is forced dry_run - no HTTP, no hook_submit_orders flip.
Credentials: TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID (env or ROOT/.env).
Does not reuse send_signal_alert BUY/SELL ontology for CRT costume alerts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from live.telegram_bridge import TelegramBridge  # noqa: E402

ACTIONABLE = frozenset({"A_SETUP_CANDIDATE", "EXECUTION_RARE"})
DEFAULT_SEVERITIES = frozenset({"action"})  # EXECUTION often severity=watch - include via --include-execution


def format_live_alert_v1(alert: dict[str, Any]) -> str:
    """REM-TG-02 format contract - not a SIGNAL BUY/SELL blurb."""
    kind = alert.get("kind", "UNKNOWN")
    instrument = alert.get("instrument", "?")
    ev = alert.get("evidence") or {}
    lines = [
        f"LIVE_ALERT_V1 | {kind} | {instrument}",
        f"severity:    {alert.get('severity')}",
        f"constructor: {alert.get('constructor_id', 'engine')}",
        f"bar_ts:      {alert.get('bar_ts')}",
        f"api_run_id:  {alert.get('api_run_id')}",
        f"message:     {alert.get('message')}",
    ]
    if ev.get("expansion_bars") is not None:
        lines.append(f"expansion_bars: {ev.get('expansion_bars')}")
    if alert.get("direction"):
        lines.append(f"direction:  {alert.get('direction')}")
    if alert.get("remediation_id"):
        lines.append(f"remediation: {alert.get('remediation_id')}")
    lines.append("authority: RESEARCH_ONLY - not an order / not economic claim")
    return "\n".join(lines)


def fingerprint(alert: dict[str, Any]) -> str:
    raw = "|".join(
        [
            str(alert.get("kind")),
            str(alert.get("bar_ts")),
            str(alert.get("api_run_id")),
            str(alert.get("candle_index")),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def iter_alerts(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def select_alerts(
    alerts: Iterable[dict[str, Any]],
    *,
    severities: set[str],
    include_execution: bool,
    seen: set[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for a in alerts:
        kind = a.get("kind")
        sev = a.get("severity")
        ok = sev in severities
        if include_execution and kind == "EXECUTION_RARE":
            ok = True
        if kind == "A_SETUP_CANDIDATE" and sev == "action":
            ok = True
        if not ok:
            continue
        if kind == "A_SETUP_CANDIDATE" and (a.get("evidence") or {}).get("near_miss"):
            continue
        fp = fingerprint(a)
        if fp in seen:
            continue
        seen.add(fp)
        a = dict(a)
        a["_fingerprint"] = fp
        out.append(a)
    return out


def _load_dotenv_telegram(root: Path) -> None:
    """Best-effort load of TELEGRAM_* from ROOT/.env without printing values."""
    env_path = root / ".env"
    if not env_path.is_file():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            if k not in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
                continue
            if os.environ.get(k):
                continue
            v = v.strip().strip('"').strip("'")
            if v:
                os.environ[k] = v
    except OSError:
        return


def _env_creds() -> tuple[str, str]:
    return (
        str(os.environ.get("TELEGRAM_BOT_TOKEN", "") or ""),
        str(os.environ.get("TELEGRAM_CHAT_ID", "") or ""),
    )


def build_bridge(*, force_dry_run: bool, from_prod: bool) -> tuple[TelegramBridge, str]:
    """Prefer TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID. Never log secret values.

    Returns (bridge, credential_source) where credential_source is
    env | prod | placeholder.
    """
    _load_dotenv_telegram(ROOT)
    token, chat = _env_creds()

    if not force_dry_run:
        if not token or not chat:
            raise SystemExit(
                "REM-TG-01: --allow-live-send requires TELEGRAM_BOT_TOKEN and "
                "TELEGRAM_CHAT_ID in the environment (or ROOT/.env)."
            )
        return (
            TelegramBridge(
                bot_token=token,
                chat_id=chat,
                enabled=True,
                dry_run=False,
            ),
            "env",
        )

    # dry-run path
    if token and chat:
        tg = TelegramBridge(
            bot_token=token,
            chat_id=chat,
            enabled=True,
            dry_run=True,
        )
        source = "env"
    elif from_prod:
        tg = TelegramBridge.from_prod_config()
        tg._dry_run = True  # noqa: SLF001
        source = "prod"
        if not tg._token or not tg._chat_id:  # noqa: SLF001
            tg._token = "DRY_RUN_PLACEHOLDER"  # noqa: SLF001
            tg._chat_id = "DRY_RUN_PLACEHOLDER"  # noqa: SLF001
            tg._enabled = True  # noqa: SLF001
            source = "placeholder"
    else:
        tg = TelegramBridge(
            bot_token="DRY_RUN_PLACEHOLDER",
            chat_id="DRY_RUN_PLACEHOLDER",
            enabled=True,
            dry_run=True,
        )
        source = "placeholder"

    tg._dry_run = True  # noqa: SLF001 - REM-TG-01 safety latch
    return tg, source


def main() -> None:
    ap = argparse.ArgumentParser(description="REM-TG-01 live_alert_v1 -> Telegram bridge")
    ap.add_argument("--alerts-jsonl", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--force-dry-run", action="store_true", default=True)
    ap.add_argument(
        "--allow-live-send",
        action="store_true",
        help="DANGEROUS: real HTTP via TELEGRAM_* env (not research default)",
    )
    ap.add_argument("--from-prod-config", action="store_true")
    ap.add_argument("--include-execution", action="store_true", default=True)
    ap.add_argument("--limit", type=int, default=5, help="Max messages this run")
    ap.add_argument("--seen-path", type=Path, default=None, help="Fingerprint store for REM-TG-04")
    args = ap.parse_args()

    force_dry = not args.allow_live_send
    args.out_dir.mkdir(parents=True, exist_ok=True)
    seen_path = args.seen_path or (args.out_dir / "telegram_seen_fingerprints.json")
    seen: set[str] = set()
    if seen_path.exists():
        seen = set(json.loads(seen_path.read_text(encoding="utf-8")).get("fingerprints", []))

    selected = select_alerts(
        iter_alerts(args.alerts_jsonl),
        severities=set(DEFAULT_SEVERITIES),
        include_execution=args.include_execution,
        seen=seen,
    )
    selected = selected[: max(0, args.limit)]

    tg, cred_source = build_bridge(force_dry_run=force_dry, from_prod=args.from_prod_config)
    results = []
    dry_log_path = args.out_dir / "telegram_dry_run.log"
    with dry_log_path.open("a", encoding="utf-8") as logf:
        for a in selected:
            text = format_live_alert_v1(a)
            ok = tg.send_research_alert(text)
            rec = {
                "ts_utc": datetime.now(timezone.utc).isoformat(),
                "ok": bool(ok),
                "dry_run": force_dry,
                "fingerprint": a["_fingerprint"],
                "kind": a.get("kind"),
                "severity": a.get("severity"),
                "bar_ts": a.get("bar_ts"),
                "api_run_id": a.get("api_run_id"),
                "text": text,
            }
            results.append(rec)
            logf.write(json.dumps(rec, ensure_ascii=False) + "\n")

    seen_path.write_text(
        json.dumps(
            {
                "fingerprints": sorted(seen),
                "updated_utc": datetime.now(timezone.utc).isoformat(),
                "remediation": "REM-TG-04",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = {
        "remediation": "REM-TG-01",
        "format": "REM-TG-02",
        "dedupe": "REM-TG-04",
        "authority": "RESEARCH_ONLY",
        "force_dry_run": force_dry,
        "credential_source": cred_source,
        "env_token_set": bool(os.environ.get("TELEGRAM_BOT_TOKEN")),
        "env_chat_set": bool(os.environ.get("TELEGRAM_CHAT_ID")),
        "n_selected": len(selected),
        "n_sent_ok": sum(1 for r in results if r["ok"]),
        "alerts_jsonl": str(args.alerts_jsonl),
        "dry_log": str(dry_log_path),
        "results": results,
        "note": (
            "No BUY/SELL signal ontology; CRT live_alert_v1 text only. "
            "Creds from TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID. "
            "HTTP suppressed when force_dry_run."
        ),
    }
    (args.out_dir / "REM_TG_01_VERIFY.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "n_selected",
                    "n_sent_ok",
                    "force_dry_run",
                    "credential_source",
                    "env_token_set",
                    "env_chat_set",
                    "dry_log",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
