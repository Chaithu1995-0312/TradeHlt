"""Orchestrate IC-003B arms S / T / C and write artifacts.

Supports safe pause/resume via on-disk per-arm checkpoints under out_dir:
  arm_{S|T}_N{N}/shapes.json (+ assignment.jsonl)
  arm_C_N{N}.json
  checkpoint.json  - machine-readable resume state
  RUN_STATUS.md    - human pause/complete note

Incomplete in-memory work is discarded on kill; only written artifacts survive.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from research.ic002_entry_evolution.io_util import load_batch, repo_root, sha256_file
from research.ic002_entry_evolution.schema import TRAJECTORY_FEATURE_IDS
from research.ic003b_sequence_geometry.cluster_dtw import run_arm_t
from research.ic003b_sequence_geometry.cluster_euclid import run_arm_s
from research.ic003b_sequence_geometry.continuum import run_arm_c
from research.ic003b_sequence_geometry.schema import (
    DIAGNOSTIC_N,
    DTW_CHANNELS,
    PRIMARY_N,
)
from research.ic003b_sequence_geometry.summarize import mflat, path_summary_matrix

logger = logging.getLogger("ic003b.build")

DEFAULT_IC002 = repo_root() / "results" / "research" / "ic_002"
DEFAULT_OUT = repo_root() / "results" / "research" / "ic_003b"

CHECKPOINT_NAME = "checkpoint.json"
RUN_STATUS_NAME = "RUN_STATUS.md"


def _channel_indices(feature_ids: tuple[str, ...] | list[str]) -> list[int]:
    fids = list(feature_ids)
    idx = []
    for ch in DTW_CHANNELS:
        if ch not in fids:
            raise RuntimeError(f"DTW channel {ch} missing from feature_ids")
        idx.append(fids.index(ch))
    return idx


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _arm_dir(out_dir: Path, arm: str, N: int) -> Path:
    return out_dir / f"arm_{arm}_N{N}"


def _arm_complete(out_dir: Path, arm: str, N: int) -> bool:
    """True when shapes.json exists and has arm+N+verdict (assignment optional if INSUFFICIENT)."""
    p = _arm_dir(out_dir, arm, N) / "shapes.json"
    if not p.is_file() or p.stat().st_size < 20:
        return False
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        str(d.get("N")) == str(N)
        and str(d.get("arm", "")).upper() == arm.upper()
        and "verdict" in d
    )


def _load_arm(out_dir: Path, arm: str, N: int) -> dict[str, Any] | None:
    if not _arm_complete(out_dir, arm, N):
        return None
    p = _arm_dir(out_dir, arm, N) / "shapes.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    # labels not required for final report; keep None on resume
    d.setdefault("labels", None)
    return d


def _c_path(out_dir: Path, N: int) -> Path:
    return out_dir / f"arm_C_N{N}.json"


def _c_complete(out_dir: Path, N: int) -> bool:
    p = _c_path(out_dir, N)
    if not p.is_file() or p.stat().st_size < 10:
        return False
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(d, dict) and ("flags" in d or "reprs" in d)


def _load_c(out_dir: Path, N: int) -> dict[str, Any] | None:
    if not _c_complete(out_dir, N):
        return None
    return json.loads(_c_path(out_dir, N).read_text(encoding="utf-8"))


def _write_arm_artifacts(
    out_dir: Path,
    arm_name: str,
    N: int,
    res: dict[str, Any],
    trade_ids: list[str],
    outcomes: list[str],
) -> None:
    sub = _arm_dir(out_dir, arm_name, N)
    sub.mkdir(parents=True, exist_ok=True)
    slim = {k: v for k, v in res.items() if k != "labels"}
    (sub / "shapes.json").write_text(
        json.dumps(slim, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    if res.get("labels") is not None:
        with open(sub / "assignment.jsonl", "w", encoding="utf-8") as f:
            for i, lab in enumerate(res["labels"]):
                f.write(
                    json.dumps(
                        {
                            "trade_id": trade_ids[i],
                            "label": int(lab),
                            "outcome": outcomes[i],
                        }
                    )
                    + "\n"
                )


def _write_checkpoint(
    out_dir: Path,
    *,
    status: str,
    completed: list[str],
    pending: list[str],
    note: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "program": "H-IC003B-001",
        "status": status,
        "updated_utc": _utc_now(),
        "completed_units": completed,
        "pending_units": pending,
        "resume_command": (
            "python scripts/research/ic003b_build.py --resume "
            f"--out {out_dir.as_posix()}"
        ),
        "fresh_command": (
            "python scripts/research/ic003b_build.py --fresh "
            f"--out {out_dir.as_posix()}"
        ),
        "note": note,
        "authority": "research_only",
        "production_config_changed": False,
    }
    if extra:
        payload.update(extra)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / CHECKPOINT_NAME).write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _write_run_status_md(
    out_dir: Path,
    *,
    status: str,
    completed: list[str],
    pending: list[str],
    note: str = "",
) -> None:
    lines = [
        "# IC-003B RUN STATUS",
        "",
        f"**Status:** `{status}`",
        f"**Updated (UTC):** {_utc_now()}",
        "",
        "> RESEARCH_ONLY | resume-safe | incomplete DTW work is **not** on disk",
        "",
        "## Completed (on disk - survives reboot)",
        "",
    ]
    if completed:
        for u in completed:
            lines.append(f"- `{u}`")
    else:
        lines.append("- _(none)_")
    lines += [
        "",
        "## Pending (re-run on resume)",
        "",
    ]
    if pending:
        for u in pending:
            lines.append(f"- `{u}`")
    else:
        lines.append("- _(none - full run complete)_")
    lines += [
        "",
        "## Resume after system restart",
        "",
        "```bash",
        "cd D:/Tradelatest",
        "$env:PYTHONPATH='src'   # PowerShell",
        "python scripts/research/ic003b_build.py --resume",
        "```",
        "",
        "Skips any unit with a valid `shapes.json` / `arm_C_N*.json` under `results/research/ic_003b/`.",
        "",
        "Force full recompute (destroys resume benefit):",
        "",
        "```bash",
        "python scripts/research/ic003b_build.py --fresh",
        "```",
        "",
    ]
    if note:
        lines += ["## Note", "", note, ""]
    (out_dir / RUN_STATUS_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _planned_units(primary_N: tuple[int, ...], diagnostic_N: tuple[int, ...]) -> list[str]:
    units: list[str] = []
    for N in list(primary_N) + list(diagnostic_N):
        units.append(f"S_N{N}")
        units.append(f"T_N{N}")
        units.append(f"C_N{N}")
    return units


def inventory_units(
    out_dir: Path,
    primary_N: tuple[int, ...] = PRIMARY_N,
    diagnostic_N: tuple[int, ...] = DIAGNOSTIC_N,
) -> tuple[list[str], list[str]]:
    """Return (completed, pending) unit ids."""
    completed: list[str] = []
    pending: list[str] = []
    for N in list(primary_N) + list(diagnostic_N):
        for arm in ("S", "T"):
            u = f"{arm}_N{N}"
            if _arm_complete(out_dir, arm, N):
                completed.append(u)
            else:
                pending.append(u)
        u = f"C_N{N}"
        if _c_complete(out_dir, N):
            completed.append(u)
        else:
            pending.append(u)
    return completed, pending


def write_paused_checkpoint(
    out_dir: Path | None = None,
    *,
    note: str = "",
    primary_N: tuple[int, ...] = PRIMARY_N,
    diagnostic_N: tuple[int, ...] = DIAGNOSTIC_N,
) -> dict[str, Any]:
    """Snapshot disk inventory after a manual pause (no process required)."""
    out_dir = out_dir or DEFAULT_OUT
    completed, pending = inventory_units(out_dir, primary_N, diagnostic_N)
    _write_checkpoint(
        out_dir,
        status="PAUSED",
        completed=completed,
        pending=pending,
        note=note
        or (
            "User-requested safe pause. N=16 DTW (~2.5-3.5h) not finished - "
            "no partial DTW matrix on disk. Resume skips completed units only."
        ),
        extra={
            "next_session_priority": True,
            "eta_remaining_hours": "3-4 (dominated by Arm T N=16 DTW)",
            "survives_reboot": True,
            "pids_do_not_matter": True,
        },
    )
    _write_run_status_md(
        out_dir,
        status="PAUSED",
        completed=completed,
        pending=pending,
        note=note
        or (
            "Paused safely before system restart. Re-run with `--resume`. "
            "Priority for next session."
        ),
    )
    return {
        "status": "PAUSED",
        "completed": completed,
        "pending": pending,
        "checkpoint": str(out_dir / CHECKPOINT_NAME),
    }


def build_all(
    *,
    ic002_dir: Path | None = None,
    out_dir: Path | None = None,
    primary_N: tuple[int, ...] = PRIMARY_N,
    diagnostic_N: tuple[int, ...] = DIAGNOSTIC_N,
    resume: bool = True,
) -> dict[str, Any]:
    ic002_dir = ic002_dir or DEFAULT_IC002
    out_dir = out_dir or DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)

    arm_s: dict[str, Any] = {}
    arm_t: dict[str, Any] = {}
    continuum_by_n: dict[str, Any] = {}

    planned = _planned_units(primary_N, diagnostic_N)
    completed_units: list[str] = []
    pending_units = list(planned)

    def _mark_done(unit: str) -> None:
        if unit not in completed_units:
            completed_units.append(unit)
        if unit in pending_units:
            pending_units.remove(unit)
        _write_checkpoint(
            out_dir,
            status="RUNNING",
            completed=list(completed_units),
            pending=list(pending_units),
            note=f"Last finished unit: {unit}",
        )
        _write_run_status_md(
            out_dir,
            status="RUNNING",
            completed=list(completed_units),
            pending=list(pending_units),
            note=f"Last finished unit: {unit}",
        )

    # Seed resume inventory
    if resume:
        for unit in planned:
            if unit.startswith("C_"):
                N = int(unit.split("_N")[1])
                if _c_complete(out_dir, N):
                    completed_units.append(unit)
                    pending_units.remove(unit)
            else:
                arm, npart = unit.split("_N")
                N = int(npart)
                if _arm_complete(out_dir, arm, N):
                    completed_units.append(unit)
                    pending_units.remove(unit)
        logger.info(
            "resume=%s completed=%s pending=%s",
            resume,
            completed_units,
            pending_units,
        )
        _write_checkpoint(
            out_dir,
            status="RUNNING",
            completed=list(completed_units),
            pending=list(pending_units),
            note="Resume build started",
        )

    for role, n_list in (("primary", primary_N), ("diagnostic", diagnostic_N)):
        for N in n_list:
            need_s = not (resume and _arm_complete(out_dir, "S", N))
            need_t = not (resume and _arm_complete(out_dir, "T", N))
            need_c = not (resume and _c_complete(out_dir, N))

            if not need_s:
                logger.info("SKIP Arm S N=%s (checkpoint)", N)
                arm_s[str(N)] = _load_arm(out_dir, "S", N) or {}
            if not need_t:
                logger.info("SKIP Arm T N=%s (checkpoint)", N)
                arm_t[str(N)] = _load_arm(out_dir, "T", N) or {}
            if not need_c:
                logger.info("SKIP Arm C N=%s (checkpoint)", N)
                continuum_by_n[str(N)] = _load_c(out_dir, N) or {}

            if not (need_s or need_t or need_c):
                continue

            logger.info("load N=%s role=%s", N, role)
            batch = load_batch(ic002_dir, N)
            Z = np.asarray(batch.Z, dtype=np.float64)
            fids = batch.feature_ids or TRAJECTORY_FEATURE_IDS

            Xs = path_summary_matrix(Z)
            Xf = mflat(Z)

            if need_s:
                logger.info("Arm S N=%s", N)
                s_res = run_arm_s(
                    Xs,
                    batch.timestamps,
                    batch.entry_indices,
                    batch.trade_ids,
                    batch.outcomes,
                    N,
                    role=role,
                )
                arm_s[str(N)] = s_res
                _write_arm_artifacts(
                    out_dir, "S", N, s_res, batch.trade_ids, batch.outcomes
                )
                _mark_done(f"S_N{N}")
            else:
                arm_s[str(N)] = _load_arm(out_dir, "S", N) or arm_s.get(str(N)) or {}

            if need_t:
                logger.info("Arm T N=%s (DTW)", N)
                ch = _channel_indices(fids)
                seqs = Z[:, :, ch]
                t_res = run_arm_t(
                    seqs,
                    batch.timestamps,
                    batch.entry_indices,
                    batch.trade_ids,
                    batch.outcomes,
                    N,
                    role=role,
                )
                arm_t[str(N)] = t_res
                _write_arm_artifacts(
                    out_dir, "T", N, t_res, batch.trade_ids, batch.outcomes
                )
                _mark_done(f"T_N{N}")
            else:
                arm_t[str(N)] = _load_arm(out_dir, "T", N) or arm_t.get(str(N)) or {}

            if need_c:
                logger.info("Arm C N=%s", N)
                order = sorted(
                    range(len(batch.entry_indices)),
                    key=lambda i: (batch.timestamps[i] or "", batch.entry_indices[i]),
                )
                cut = int(round(len(order) * 0.7))
                is_idx = order[:cut]
                c_res = run_arm_c(Xf[is_idx], Xs[is_idx])
                continuum_by_n[str(N)] = c_res
                _c_path(out_dir, N).write_text(
                    json.dumps(c_res, indent=2, sort_keys=True, default=str),
                    encoding="utf-8",
                )
                _mark_done(f"C_N{N}")
            else:
                continuum_by_n[str(N)] = (
                    _load_c(out_dir, N) or continuum_by_n.get(str(N)) or {}
                )

    # Ensure all results loaded for rollup even if fully skipped path
    for N in list(primary_N) + list(diagnostic_N):
        if str(N) not in arm_s:
            arm_s[str(N)] = _load_arm(out_dir, "S", N) or {}
        if str(N) not in arm_t:
            arm_t[str(N)] = _load_arm(out_dir, "T", N) or {}
        if str(N) not in continuum_by_n:
            continuum_by_n[str(N)] = _load_c(out_dir, N) or {}

    # program verdict
    def _ok(arm: dict, N: int) -> bool:
        v = (arm.get(str(N)) or {}).get("verdict", "")
        return v == "LIBRARY_OK" or v == "LIBRARY_OK_DIAGNOSTIC"

    s_both = all(_ok(arm_s, N) for N in primary_N)
    s_one = any(_ok(arm_s, N) for N in primary_N) and not s_both
    t_both = all(_ok(arm_t, N) for N in primary_N)

    if s_both:
        prog = "IC003B_LIBRARY_OK"
        rec = "Arm S multi-N library OK under G1=0.85; research only; no production filters."
    elif s_one or t_both:
        prog = "IC003B_PARTIAL"
        rec = (
            "Partial library success (Arm S one N and/or Arm T multi-N). "
            "Descriptive prototypes only; no production."
        )
    else:
        prog = "IC003B_FAIL"
        rec = (
            "Neither Arm S multi-N nor Arm T multi-N passed library gates. "
            "Accept representation-level boundary; do not loosen G1."
        )

    cont_flags = set()
    for N in primary_N:
        c = continuum_by_n.get(str(N)) or {}
        for fl in c.get("flags") or []:
            cont_flags.add(fl)

    program_verdict = {
        "label": prog,
        "recommendation": rec,
        "arm_S_primary": {str(N): arm_s.get(str(N), {}).get("verdict") for N in primary_N},
        "arm_T_primary": {str(N): arm_t.get(str(N), {}).get("verdict") for N in primary_N},
        "continuum_flags": sorted(cont_flags),
    }

    report = {
        "program": "H-IC003B-001",
        "status": "RUN_COMPLETE",
        "authority": "research_only",
        "hard_flags": {
            "IC003_GATE_AMENDMENT": False,
            "ENTRY_TIME_SHAPE_FILTERS": False,
            "NEW_ENGINES": False,
        },
        "arm_S": {k: {kk: vv for kk, vv in v.items() if kk != "labels"} for k, v in arm_s.items()},
        "arm_T": {k: {kk: vv for kk, vv in v.items() if kk != "labels"} for k, v in arm_t.items()},
        "arm_C": continuum_by_n,
        "program_verdict": program_verdict,
        "production_config_changed": False,
    }

    (out_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )
    (out_dir / "arm_C_continuum.json").write_text(
        json.dumps(continuum_by_n, indent=2, sort_keys=True), encoding="utf-8"
    )

    lib_lines = [
        "# IC-003B Shape Library",
        "",
        "> RESEARCH_ONLY | sequence geometry | **not** IC-003 gate amendment",
        f"> Program: **{prog}**",
        "",
        rec,
        "",
    ]
    for arm_name, arm in (("S", arm_s), ("T", arm_t)):
        lib_lines.append(f"## Arm {arm_name}")
        lib_lines.append("")
        for N in list(primary_N) + list(diagnostic_N):
            r = arm.get(str(N))
            if not r:
                continue
            lib_lines.append(
                f"### N={N} ({r.get('role')}) - **{r.get('verdict')}** k*={r.get('k_star')}"
            )
            lib_lines.append("")
            g = r.get("gates") or {}
            lib_lines.append(f"gates: `{json.dumps(g)}`")
            lib_lines.append("")
            if "LIBRARY_OK" not in str(r.get("verdict")):
                lib_lines.append("_No shapes promoted to library (failed gates)._")
                lib_lines.append("")
                continue
            lib_lines.append("| shape_id | n_is | n_oos | tp_oos | medoid |")
            lib_lines.append("|----------|-----:|------:|-------:|--------|")
            for s in r.get("shapes") or []:
                lib_lines.append(
                    f"| `{s['shape_id']}` | {s.get('n_is')} | {s.get('n_oos')} | "
                    f"{s.get('tp_rate_oos')} | `{s.get('medoid_trade_id')}` |"
                )
            lib_lines.append("")
    (out_dir / "SHAPE_LIBRARY.md").write_text("\n".join(lib_lines) + "\n", encoding="utf-8")

    lines = [
        "# H-IC003B-001 - Sequence Geometry Report",
        "",
        "> RESEARCH_ONLY | **not** an IC-003 G1 amendment | G1 stays **0.85** for Arm S",
        "",
        f"**Program verdict:** **{prog}**",
        "",
        rec,
        "",
        "## Arm S (path summary, primary)",
        "",
        "| N | role | k* | verdict | G1 sse | G2 sil | G3 | G4 |",
        "|---:|------|---:|---------|-------:|-------:|----|----|",
    ]
    for N in list(primary_N) + list(diagnostic_N):
        r = arm_s.get(str(N)) or {}
        g = r.get("gates") or {}
        lines.append(
            f"| {N} | {r.get('role')} | {r.get('k_star')} | **{r.get('verdict')}** | "
            f"{g.get('G1', {}).get('sse_ratio')} | {g.get('G2', {}).get('silhouette')} | "
            f"{g.get('G3', {}).get('ok')} | {g.get('G4', {}).get('ok')} |"
        )
    lines += [
        "",
        "## Arm T (DTW medoids, secondary)",
        "",
        "| N | role | k* | verdict | G1_T ratio | G2_T sil | G3 | G4 |",
        "|---:|------|---:|---------|-----------:|---------:|----|----|",
    ]
    for N in list(primary_N) + list(diagnostic_N):
        r = arm_t.get(str(N)) or {}
        g = r.get("gates") or {}
        lines.append(
            f"| {N} | {r.get('role')} | {r.get('k_star')} | **{r.get('verdict')}** | "
            f"{g.get('G1_T', {}).get('ratio')} | {g.get('G2_T', {}).get('silhouette')} | "
            f"{g.get('G3_T', {}).get('ok')} | {g.get('G4', {}).get('ok')} |"
        )
    lines += [
        "",
        "## Arm C (continuum diagnostic)",
        "",
        f"Flags (union over primary N): **{program_verdict['continuum_flags']}**",
        "",
    ]
    for N in primary_N:
        c = continuum_by_n.get(str(N)) or {}
        lines.append(f"### N={N}")
        lines.append(f"- flags: {c.get('flags')}")
        for name, rr in (c.get("reprs") or {}).items():
            lines.append(
                f"- {name}: cumvar_4={rr.get('cumvar_4')} max_sil={rr.get('max_kmeans_silhouette_on_pcs')}"
            )
        lines.append("")
    lines += [
        "## Epistemic note",
        "",
        "- IC-003 archive (M-FLAT) remains LIBRARY_FAIL under G1=0.85.",
        "- IC-003B tests **representation change**, not gate looseness.",
        "- LIBRARY_OK still ≠ entry-time filters or expectancy authority.",
        "- IC-002 path information is independent of prototype compressibility.",
        "",
        "## Explicit non-actions",
        "- No production config / shape_id filters / engines",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    pins = {}
    for N in list(primary_N) + list(diagnostic_N):
        npz = ic002_dir / f"trajectories_N{N}.npz"
        if npz.exists():
            pins[f"N{N}"] = sha256_file(npz)
    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                "program": "H-IC003B-001",
                "ic002_pins": pins,
                "program_verdict": program_verdict,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    _write_checkpoint(
        out_dir,
        status="RUN_COMPLETE",
        completed=list(planned),
        pending=[],
        note=f"Program verdict: {prog}",
        extra={"program_verdict": program_verdict},
    )
    _write_run_status_md(
        out_dir,
        status="RUN_COMPLETE",
        completed=list(planned),
        pending=[],
        note=f"Program verdict: {prog}",
    )
    return report
