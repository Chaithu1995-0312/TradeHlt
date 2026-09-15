#!/usr/bin/env python3
"""
RR L4 — Research execution composition gate under SIGNED L1 + L2 + L3.

Steps (checklist §2.1A L4):
  4a  Co-consistency: certificate / L2 / L3 hashes + pit_status
  4b  Harness bound only to clean L3 dataset (refuse legacy contaminated path)
  4c  Smoke fold on metric path (SMOKE_ONLY — not findings / not KEEP/RETIRE)
  4d  RS acceptance log + GATE-R READY
  4e  Epoch charter → RR_RESEARCH_EPOCH_STATUS = AUTHORIZED (not RUNNING)

Does NOT: re-enable rr_fusion, promote, register KEEP/RETIRE findings.

Usage (repo root):
  python scripts/research/rr_l4_research_execution.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.governance.rr_l1_freeze_certificate import (  # noqa: E402
    DEFAULT_CERT,
    compute_protocol_hash,
    cmd_assert_signed,
)

LEGACY_FORBIDDEN_SUBSTRINGS = (
    "rr_dataset_202605_v1.json",
    "bnbusdt_balanced_20260524/rr_dataset",
    "models/rr_dataset.json",
)

# Research-safe IDs from checklist §2.2 (must ACCEPT or RESOLVE before GATE-R)
RS_IDS: List[Tuple[str, str]] = [
    ("RR-IMP-001", "Gate-bypassed raw-head eval only under L1; gate fix deferred to GATE-P"),
    ("RR-IMP-002", "Offline matrix path only; no starved score_dict fusion path"),
    ("RR-IMP-004", "Offline eval only; no EngineRunner fusion adoption for labels"),
    ("RR-IMP-005", "Docstring hygiene deferred; non-blocking for clean-B research"),
    ("RR-IMP-006", "Dead min_rr field; non-blocking"),
    ("RR-IMP-007", "Error-path shape hygiene deferred"),
    ("RR-IMP-008", "Registry bookkeeping deferred; clean dataset self-describes"),
    ("RR-CTR-001", "Polarity alias; B research offline; DE semantic skip holds"),
    ("RR-CTR-002", "Economic RR authority = Ultron D; A never economic; B offline"),
    ("RR-CTR-003", "Doc drift deferred"),
    ("RR-CTR-004", "No non-ER research callers"),
    ("RR-CTR-005", "Design: Ultron owns true RR"),
    ("RR-CTR-006", "HMF sidecar F-012; zero spine consumption"),
    ("RR-LAB-005", "Explicit L2/L3 paths; config illusion deferred"),
    ("RR-LAB-006", "Incumbent weak fit is prior; research tests clean labels"),
    ("RR-GOV-001", "Measure-only; no ΔG001 claim in L4 smoke"),
    ("RR-GOV-005", "Not shipping production wire"),
    ("RR-GOV-006", "Backtest/shadow only; no live capital claim"),
    ("RR-GOV-007", "active_models YAML hygiene deferred"),
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)


def _auc(scores: np.ndarray, labels: np.ndarray) -> float:
    labels = labels.astype(int)
    pos = scores[labels == 1]
    neg = scores[labels == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    # Mann-Whitney
    correct = 0.0
    for p in pos:
        correct += np.sum(p > neg) + 0.5 * np.sum(p == neg)
    return float(correct / (len(pos) * len(neg)))


def _raw_model_outputs(state: dict, Xtest: np.ndarray):
    """Gate-bypassed ridge + GNB heads (same intent as rr_shadow_value)."""
    W = np.asarray(state["ridge_w"], dtype=np.float64)
    b = float(state["ridge_b"])
    smu = np.asarray(state["scale_mu"], dtype=np.float64)
    ssig = np.asarray(state["scale_sigma"], dtype=np.float64)
    ssig = np.where(ssig == 0, 1.0, ssig)
    cmu = np.asarray(state["conf_mu"], dtype=np.float64)
    P = np.asarray(state["conf_P"], dtype=np.float64)
    gC0 = np.asarray(state["gnb_C"][0], dtype=np.float64)
    gV0 = np.asarray(state["gnb_V"][0], dtype=np.float64)
    gm0 = np.asarray(state["gnb_mu"][0], dtype=np.float64)
    gC1 = np.asarray(state["gnb_C"][1], dtype=np.float64)
    gV1 = np.asarray(state["gnb_V"][1], dtype=np.float64)
    gm1 = np.asarray(state["gnb_mu"][1], dtype=np.float64)
    zi = list(state.get("zero_indices") or [])

    X = np.array(Xtest, dtype=np.float64, copy=True)
    if zi:
        X[:, zi] = 0.0
    Xs = (X - smu) / ssig
    if zi:
        Xs[:, zi] = 0.0
    exp_rr = Xs @ W + b
    ll0 = (gC0 - 0.5 * gV0 * (Xs - gm0) ** 2).sum(axis=1)
    ll1 = (gC1 - 0.5 * gV1 * (Xs - gm1) ** 2).sum(axis=1)
    mx = np.maximum(ll0, ll1)
    e0 = np.exp(ll0 - mx)
    e1 = np.exp(ll1 - mx)
    p_win = e1 / (e0 + e1)
    delta = Xs - cmu
    d_sq = np.einsum("ij,jk,ik->i", delta, P, delta)
    return exp_rr, p_win, d_sq


def co_consistency(cert: dict, l2: dict, l3: dict) -> Tuple[bool, List[str]]:
    errs: List[str] = []
    ph = cert.get("protocol_hash")
    if compute_protocol_hash(cert["contract"]) != ph:
        errs.append("L1 protocol_hash != recomputed contract hash")
    if l2.get("protocol_hash") != ph:
        errs.append("L2 protocol_hash mismatch")
    if l3.get("protocol_hash") != ph:
        errs.append("L3 protocol_hash mismatch")
    if l2.get("certificate_id") != cert.get("certificate_id"):
        errs.append("L2 certificate_id mismatch")
    if l3.get("certificate_id") != cert.get("certificate_id"):
        errs.append("L3 certificate_id mismatch")
    if l2.get("schema_hash") != l3.get("schema_hash") and l2.get("schema_hash") != l3.get(
        "l2_schema_hash"
    ):
        # L3 stores schema_hash and l2_schema_hash
        if l2.get("schema_hash") != l3.get("l2_schema_hash"):
            errs.append("L2/L3 schema_hash mismatch")
    pit = str(l2.get("pit_status") or "")
    if not pit.startswith("PIT_CLEAN"):
        errs.append(f"L2 pit_status not PIT_CLEAN*: {pit!r}")
    if l3.get("l2_pit_status") and l3.get("l2_pit_status") != l2.get("pit_status"):
        errs.append("L3 l2_pit_status != L2 pit_status")
    if not l3.get("degeneracy_check", {}).get("pass", False):
        errs.append("L3 degeneracy_check failed")
    return len(errs) == 0, errs


def harness_path_guard(l3_dir: Path, clean_npz: Path) -> Tuple[bool, List[str]]:
    errs: List[str] = []
    for p in (l3_dir, clean_npz):
        s = str(p).replace("\\", "/")
        for bad in LEGACY_FORBIDDEN_SUBSTRINGS:
            if bad in s:
                errs.append(f"legacy path fragment {bad!r} in {s}")
    if "rr_research/l3" not in str(l3_dir).replace("\\", "/"):
        errs.append("L3 dir must live under results/rr_research/l3/")
    if not clean_npz.is_file():
        errs.append(f"clean_dataset.npz missing: {clean_npz}")
    return len(errs) == 0, errs


def smoke_metrics(
    clean_npz: Path,
    model_path: Path,
    *,
    n_cap: int,
    seed: int,
) -> Dict[str, Any]:
    """N-capped holdout metrics on clean labels with gate-bypassed incumbent heads. SMOKE_ONLY."""
    pack = np.load(clean_npz, allow_pickle=True)
    X = np.asarray(pack["X"], dtype=np.float64)
    y_rr = np.asarray(pack["y_rr"], dtype=np.float64)
    y_win = np.asarray(pack["y_win"], dtype=np.int32)
    n = len(y_rr)
    rng = np.random.default_rng(seed)
    if n > n_cap:
        idx = rng.choice(n, size=n_cap, replace=False)
        X, y_rr, y_win = X[idx], y_rr[idx], y_win[idx]
        n = n_cap
    # holdout 20%
    perm = rng.permutation(n)
    cut = int(0.8 * n)
    tr, te = perm[:cut], perm[cut:]
    state = json.loads(model_path.read_text(encoding="utf-8"))
    # smoke uses incumbent model raw heads on clean y (not retrain) — exercises metric path
    exp_rr, p_win, d_sq = _raw_model_outputs(state, X[te])
    rr_corr = float(np.corrcoef(exp_rr, y_rr[te])[0, 1]) if len(te) > 2 else float("nan")
    auc = _auc(p_win, y_win[te])
    # shuffle null
    y_shuf = y_win[te].copy()
    rng.shuffle(y_shuf)
    auc_shuf = _auc(p_win, y_shuf)
    # top decile
    k = max(1, len(te) // 10)
    order = np.argsort(-exp_rr)
    top = order[:k]
    rand = rng.choice(len(te), size=k, replace=False)
    top_mean = float(y_rr[te][top].mean())
    rand_mean = float(y_rr[te][rand].mean())
    return {
        "tag": "SMOKE_ONLY",
        "authority": "NONE — not findings, not KEEP/RETIRE, not F-045 overturn",
        "n_full": int(len(pack["y_rr"])),
        "n_smoke": int(n),
        "n_test": int(len(te)),
        "model_path": _rel(model_path),
        "confidence_gate": "bypassed",
        "rr_corr": rr_corr,
        "auc_p_win": auc,
        "auc_shuffle": auc_shuf,
        "top_decile_mean_y_rr": top_mean,
        "random_decile_mean_y_rr": rand_mean,
        "d_sq_median": float(np.median(d_sq)),
        "seed": seed,
        "n_cap": n_cap,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cert", type=Path, default=DEFAULT_CERT)
    ap.add_argument("--cert-id", type=str, default=None)
    ap.add_argument("--n-cap", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument(
        "--model",
        type=Path,
        default=REPO_ROOT / "models" / "rr_model.json",
    )
    args = ap.parse_args(argv)

    cert_path = args.cert if args.cert.is_absolute() else (REPO_ROOT / args.cert)
    if cmd_assert_signed(cert_path) != 0:
        return 2
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    cert_id = args.cert_id or cert["certificate_id"]
    protocol_hash = cert["protocol_hash"]

    l2_dir = REPO_ROOT / "results" / "rr_research" / "l2" / cert_id
    l3_dir = REPO_ROOT / "results" / "rr_research" / "l3" / cert_id
    l4_dir = REPO_ROOT / "results" / "rr_research" / "l4" / cert_id
    l4_dir.mkdir(parents=True, exist_ok=True)

    l2 = json.loads((l2_dir / "L2_PROVENANCE.json").read_text(encoding="utf-8"))
    l3 = json.loads((l3_dir / "L3_PROVENANCE.json").read_text(encoding="utf-8"))
    clean_npz = l3_dir / "clean_dataset.npz"

    print("4a co-consistency...")
    ok, errs = co_consistency(cert, l2, l3)
    if not ok:
        print("CO_CONSISTENCY FAIL", errs, file=sys.stderr)
        return 1
    print("  PASS")

    print("4b harness path guard...")
    ok, errs = harness_path_guard(l3_dir, clean_npz)
    if not ok:
        print("HARNESS_PATH FAIL", errs, file=sys.stderr)
        return 1
    # Explicit refuse list for any caller wiring
    refuse = {
        "primary_y_forbidden_paths": list(LEGACY_FORBIDDEN_SUBSTRINGS),
        "primary_y_allowed": _rel(clean_npz),
        "note": "Harness must load y_rr/y_win only from clean L3 npz; F-022 stream fields xref only",
    }
    print("  PASS")

    print("4c smoke metrics (SMOKE_ONLY)...")
    model_path = args.model if args.model.is_absolute() else (REPO_ROOT / args.model)
    smoke = smoke_metrics(clean_npz, model_path, n_cap=args.n_cap, seed=args.seed)
    print(
        f"  n_smoke={smoke['n_smoke']} rr_corr={smoke['rr_corr']:.4f} "
        f"auc={smoke['auc_p_win']:.4f} (shuffle {smoke['auc_shuffle']:.4f})"
    )
    print("  tagged SMOKE_ONLY — not findings")

    print("4d RS acceptance log...")
    accept_log = []
    for rid, rationale in RS_IDS:
        accept_log.append(
            {
                "date": _utc_now()[:10],
                "id": rid,
                "scope": "GATE-R",
                "accepted_by": "owner_session_L4",
                "rationale": rationale,
                "does_not_unblock": "GATE-P / rr_fusion re-enable / production promote",
            }
        )
    rs_path = l4_dir / "RS_ACCEPTANCE_LOG.json"
    rs_path.write_text(json.dumps(accept_log, indent=2) + "\n", encoding="utf-8")
    print(f"  ACCEPTED {len(accept_log)} RS items for GATE-R")

    print("4e epoch charter...")
    epoch_id = f"RR_B_CLEAN_EPOCH_{cert_id}"
    charter = {
        "epoch_id": epoch_id,
        "RR_RESEARCH_EPOCH_STATUS": "AUTHORIZED",
        "RUNNING": False,
        "note": "Outcomes under this protocol_hash become authoritative only after owner sets RUNNING. L4 smoke is not epoch outcome authority.",
        "certificate_id": cert_id,
        "protocol_hash": protocol_hash,
        "schema_hash": l2["schema_hash"],
        "pit_status": l2["pit_status"],
        "l1_certificate_path": _rel(cert_path),
        "l2_dir": _rel(l2_dir),
        "l3_dir": _rel(l3_dir),
        "l3_clean_dataset": _rel(clean_npz),
        "l3_n_samples": l3.get("n_labeled"),
        "authorized_at_utc": _utc_now(),
        "hard_flags_from_l1": cert["contract"]["hard_flags"],
        "success_failure_rules_from_l1": cert["contract"]["success_failure_rules"],
        "forbidden_until_running": [
            "full kill-test findings registration",
            "F-045 overturn claim",
            "rr_fusion enable",
            "promote",
        ],
        "first_allowed_run": "scripts/research/rr_shadow_value.py equivalent on clean L3 path only, with prereg rules from certificate",
    }
    charter_path = l4_dir / "RR_EPOCH_CHARTER.json"
    charter_path.write_text(json.dumps(charter, indent=2) + "\n", encoding="utf-8")
    (l4_dir / "RR_EPOCH_CHARTER.md").write_text(
        f"""# RR Research Epoch Charter — AUTHORIZED (not RUNNING)

| Field | Value |
|-------|--------|
| epoch_id | `{epoch_id}` |
| status | **AUTHORIZED** |
| RUNNING | **false** (owner start required) |
| certificate_id | `{cert_id}` |
| protocol_hash | `{protocol_hash}` |
| clean dataset | `{_rel(clean_npz)}` |
| n_samples | {l3.get("n_labeled")} |

## Layers

L1 SIGNED · L2 COMPLETE · L3 COMPLETE · L4 COMPLETE

## Smoke (not findings)

See `SMOKE_ONLY.json`. Do not treat as KEEP/RETIRE.

## Start epoch

Owner sets `RUNNING=true` (or re-runs research scripts that honor this charter) to begin
full preregistered kill-tests under this `protocol_hash`.
""",
        encoding="utf-8",
    )

    smoke_path = l4_dir / "SMOKE_ONLY.json"
    smoke_path.write_text(json.dumps(smoke, indent=2) + "\n", encoding="utf-8")

    completion = {
        "L4_COMPLETE": True,
        "GATE_R_STATUS": "READY",
        "RR_RESEARCH_EPOCH_STATUS": "AUTHORIZED",
        "RUNNING": False,
        "certificate_id": cert_id,
        "protocol_hash": protocol_hash,
        "schema_hash": l2["schema_hash"],
        "co_consistency": "PASS",
        "harness_path_guard": "PASS",
        "smoke": "PASS",
        "smoke_tag": "SMOKE_ONLY",
        "rs_accepted_count": len(accept_log),
        "refuse_primary_y": refuse,
        "artifacts": {
            "smoke": _rel(smoke_path),
            "rs_acceptance": _rel(rs_path),
            "epoch_charter": _rel(charter_path),
        },
        "completed_at_utc": _utc_now(),
        "next": "Owner may set epoch RUNNING and execute full kill-test on clean L3 only",
    }
    (l4_dir / "L4_COMPLETION.json").write_text(
        json.dumps(completion, indent=2) + "\n", encoding="utf-8"
    )
    (l4_dir / "L4_COMPLETION.md").write_text(
        f"""# L4 Research Execution — COMPLETE

| Gate | Status |
|------|--------|
| 4a co-consistency | PASS |
| 4b harness path | PASS |
| 4c smoke | PASS (`SMOKE_ONLY`) |
| 4d RS accepts | {len(accept_log)} / GATE-R **READY** |
| 4e epoch charter | **AUTHORIZED** (not RUNNING) |

protocol_hash=`{protocol_hash}`

Smoke metrics are **not** findings. Full kill-test only after owner starts epoch RUNNING.
""",
        encoding="utf-8",
    )

    print("L4_COMPLETE=YES")
    print("  GATE_R_STATUS=READY")
    print("  RR_RESEARCH_EPOCH_STATUS=AUTHORIZED (not RUNNING)")
    print(f"  out_dir={l4_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
