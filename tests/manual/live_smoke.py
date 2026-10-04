#!/usr/bin/env python
"""
live_smoke — manual reality check against a REAL MetaTrader 5 terminal (Phase 5.5).

The fourth boundary: synthetic fixtures → real broker. NOT a pytest module (no `test_`
prefix ⇒ never collected by CI). Run before a release, with a running, logged-in terminal:

    python tests/manual/live_smoke.py

Writes ONLY to throwaway temp roots (never repo artifacts). No terminal / no MetaTrader5
⇒ clean SKIP + exit 0 (availability is environmental, not a correctness failure). Any
check failing ⇒ FAIL + exit 1.

Seven checks: (1) a real closed position reconstructs, (2) idempotency, (3) live replay
parity rebuild≡daemon via sha256, (4) manifest provenance, (5) no account/identity state
persisted, (6) execution APIs unreachable, (7) the real MT5 candle provider returns bars.
"""
from __future__ import annotations

import copy
import datetime as _dt
import gc
import hashlib
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mt5_analytics.analytics_config import load_config           # noqa: E402
from mt5_analytics.core import daemon, rebuild                   # noqa: E402
from mt5_analytics.core.checkpoint import Checkpoint, save_checkpoint  # noqa: E402
from mt5_analytics.core.mt5_adapter import MT5Adapter, _MT5_AVAILABLE  # noqa: E402
from mt5_analytics.providers.mt5_provider import MT5CandleProvider     # noqa: E402

try:
    from utils.console_safe import safe_print  # type: ignore  # noqa: E402
except Exception:  # pragma: no cover - console_safe always present in-repo
    safe_print = print  # type: ignore
from utils.jsonl_writer import read_jsonl       # type: ignore  # noqa: E402

DAYS = 30
FORBIDDEN_KEYS = ("balance", "equity", "margin", "login", "server")
MUTATION_ATTRS = (
    "order_send", "send_order", "order_close", "order_modify",
    "position_close", "position_modify", "close_position",
)

_results: list[tuple[str, str, str]] = []


def _record(name: str, status: str, detail: str = "") -> None:
    _results.append((name, status, detail))
    safe_print(f"[{status:4}] {name} - {detail}")


def _concat_sha(root: Path, kind: str) -> str:
    h = hashlib.sha256()
    for f in sorted(root.glob(f"{kind}/*/*/*/{kind}.jsonl")):
        h.update(f.read_bytes())
    return h.hexdigest()


# ── Check 6 (structural — no terminal needed) ─────────────────────────────────────
def check_execution_unreachable() -> None:
    exposed = [m for m in MUTATION_ATTRS if hasattr(MT5Adapter, m)]
    if exposed:
        _record("execution_unreachable", "FAIL", f"adapter exposes {exposed}")
    else:
        _record("execution_unreachable", "PASS", "no mutation methods on MT5Adapter")


# ── live checks ───────────────────────────────────────────────────────────────────
def _run_live(adapter) -> None:
    # The adapter now normalizes MT5 server-time -> true UTC (incl. query bounds), so a
    # plain UTC window works (small forward pad covers clock skew / in-flight bars).
    now = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(minutes=5)
    frm = now - _dt.timedelta(days=DAYS)
    root_r = Path(tempfile.mkdtemp(prefix="mt5smoke_rebuild_"))
    root_d = Path(tempfile.mkdtemp(prefix="mt5smoke_daemon_"))
    cfg = load_config()
    cfg_r = copy.deepcopy(cfg)
    cfg_r["artifact_root"] = str(root_r); cfg_r["audit_root"] = str(root_r / "audit")
    cfg_d = copy.deepcopy(cfg)
    cfg_d["artifact_root"] = str(root_d); cfg_d["audit_root"] = str(root_d / "audit")

    summary_r = rebuild.run(frm, now, cfg=cfg_r)

    # 7 — real candle provider
    sym = summary_r.episodes[0]["symbol"] if summary_r.episodes else None
    if sym:
        bars = MT5CandleProvider(adapter).get_window(
            sym, int(frm.timestamp()), int(now.timestamp())
        )
        _record("real_candle_provider", "PASS" if bars else "FAIL",
                f"{len(bars)} bars for {sym}")
    else:
        _record("real_candle_provider", "SKIP", "no episode symbol to test")

    # 1 — a real closed position reconstructs
    if summary_r.episodes_written == 0:
        _record("single_position", "SKIP", f"no closed positions in last {DAYS}d")
    else:
        feat_n = sum(len(read_jsonl(f))
                     for f in root_r.glob("features/*/*/*/features.jsonl"))
        expected = summary_r.episodes_written - summary_r.episodes_skipped
        ok = feat_n == expected
        _record("single_position", "PASS" if ok else "FAIL",
                f"{summary_r.episodes_written} episodes, {feat_n} features")

    # daemon path: seed checkpoint to the same window, 3 ticks into root_d
    cp_path = str(root_d / "checkpoint.json")
    daemon._CHECKPOINT_PATH = cp_path  # isolate from the repo checkpoint
    save_checkpoint(Checkpoint(last_processed_time=int(frm.timestamp())), cp_path)
    daemon.tick(adapter, cfg=cfg_d, now=now)
    s2 = daemon.tick(adapter, cfg=cfg_d, now=now)
    s3 = daemon.tick(adapter, cfg=cfg_d, now=now)

    # 2 — idempotency
    ids = [r["episode_id"]
           for f in root_d.glob("episodes/*/*/*/episodes.jsonl") for r in read_jsonl(f)]
    if not ids:
        _record("idempotency", "SKIP", "no episodes to dedup")
    elif s2.episodes_written == 0 and s3.episodes_written == 0 and len(ids) == len(set(ids)):
        _record("idempotency", "PASS", f"tick2/3 wrote 0; {len(ids)} unique ids")
    else:
        _record("idempotency", "FAIL",
                f"rewrites={s2.episodes_written}/{s3.episodes_written}, "
                f"dups={len(ids) - len(set(ids))}")

    # 3 — live replay parity (sha256)
    same = (_concat_sha(root_r, "episodes") == _concat_sha(root_d, "episodes")
            and _concat_sha(root_r, "features") == _concat_sha(root_d, "features"))
    _record("replay_parity", "PASS" if same else "FAIL",
            f"rebuild==daemon over {DAYS}d window" if same else "sha mismatch")

    # 4 — manifest provenance
    manifests = list(root_r.glob("episodes/*/*/*/manifest.json"))
    if not manifests:
        _record("manifest", "SKIP", "no partitions written")
    else:
        import json
        m = json.loads(manifests[0].read_text())
        need = ("records", "sha256", "source_history_window",
                "engine_registry_hash", "python_version")
        missing = [k for k in need if k not in m]
        _record("manifest", "PASS" if not missing else "FAIL",
                "all provenance keys present" if not missing else f"missing {missing}")

    # deal coverage (broker-semantics report — informational, never a FAIL)
    from mt5_analytics.engines.deal_characterizer import (  # local import keeps top clean
        characterize_deal_stream, coverage_score,
    )
    all_deals = adapter.history_deals_get(frm, now)
    counts = characterize_deal_stream(all_deals)
    sc = coverage_score(counts)
    _record("deal_coverage", "INFO",
            f"{sc['coverage_score']}/100 {sc['tier']} | validated={sc['validated_patterns']}"
            f"/{sc['validated_patterns'] + sc['missing_patterns']} | "
            f"trades={counts['trade_positions']} acct_ops={counts['account_ops_skipped']}")

    # 5 — no account/identity state persisted
    adapter.account_info()  # liveness only — must not leak into artifacts
    gc.collect()
    leaked = []
    for root in (root_r, root_d):
        for kind in ("episodes", "features"):
            for f in root.glob(f"{kind}/*/*/*/{kind}.jsonl"):
                blob = f.read_text(encoding="utf-8").lower()
                leaked += [k for k in FORBIDDEN_KEYS if k in blob]
    _record("no_account_state", "FAIL" if leaked else "PASS",
            f"leaked {sorted(set(leaked))}" if leaked else "no balance/equity/login/server")


def main() -> int:
    safe_print("=== mt5_analytics live smoke ===")
    check_execution_unreachable()                    # structural, always runs

    if not _MT5_AVAILABLE:
        _record("live_suite", "SKIP", "MetaTrader5 not installed")
        return _finish()
    try:
        with MT5Adapter() as adapter:
            _run_live(adapter)
    except RuntimeError as exc:
        _record("live_suite", "SKIP", f"terminal unreachable: {exc}")
    return _finish()


def _finish() -> int:
    n_fail = sum(1 for _, s, _ in _results if s == "FAIL")
    n_pass = sum(1 for _, s, _ in _results if s == "PASS")
    n_skip = sum(1 for _, s, _ in _results if s == "SKIP")
    safe_print(f"\n=== {n_pass} PASS / {n_fail} FAIL / {n_skip} SKIP ===")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
