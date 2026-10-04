"""
verification_report_v1_0 — the result of reconciling MT5 truth ↔ persisted artifacts.

Produced by `core/verify.reconcile`. A zero-trade account reconciles to all-zeros ⇒ PASS
(zero is a valid ledger). `to_audit_dict()` feeds the Phase-6.5 audit chain; `to_markdown()`
renders `reports/verification/daily_verification.md`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

VERIFICATION_SCHEMA_VERSION = "1.0"


@dataclass
class VerificationReport:
    status: str = "PASS"                       # PASS | FAIL
    mt5_positions: int = 0                     # distinct closed position_ids (MT5 truth)
    artifact_episodes: int = 0                 # episode records on disk
    missing: list = field(default_factory=list)     # expected episode_id absent on disk
    orphan: list = field(default_factory=list)      # on disk but not expected
    duplicate: list = field(default_factory=list)   # episode_id appearing > 1 on disk
    net_pnl_diff: float = 0.0                  # Σ|MT5 raw cashflow − artifact net_pnl| per pid
    volume_diff: float = 0.0                   # Σ|expected − artifact volume| per pid
    manifests_ok: bool = True
    corrupt_lines: int = 0
    discrepancies: list = field(default_factory=list)
    window: dict = field(default_factory=lambda: {"from": None, "to": None})
    schema_version: str = VERIFICATION_SCHEMA_VERSION

    def to_audit_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "mt5_positions": self.mt5_positions,
            "artifact_episodes": self.artifact_episodes,
            "missing": list(self.missing),
            "orphan": list(self.orphan),
            "duplicate": list(self.duplicate),
            "net_pnl_diff": round(self.net_pnl_diff, 10),
            "volume_diff": round(self.volume_diff, 10),
            "manifests_ok": self.manifests_ok,
            "corrupt_lines": self.corrupt_lines,
            "discrepancies": list(self.discrepancies),
            "window": dict(self.window),
        }

    def to_markdown(self) -> str:
        rows = [
            ("MT5 positions (closed)", self.mt5_positions),
            ("Artifact episodes", self.artifact_episodes),
            ("Missing", len(self.missing)),
            ("Orphan", len(self.orphan)),
            ("Duplicate", len(self.duplicate)),
            ("Net P/L diff", round(self.net_pnl_diff, 6)),
            ("Volume diff", round(self.volume_diff, 6)),
            ("Manifests OK", str(self.manifests_ok).lower()),
            ("Corrupt lines", self.corrupt_lines),
        ]
        lines = [
            "# MT5 Analytics Verification",
            "",
            f"**Status:** {self.status}",
            "",
            f"Window: `{self.window.get('from')}` -> `{self.window.get('to')}`",
            "",
            "| Metric | Value |",
            "| --- | --- |",
        ]
        lines += [f"| {k} | {v} |" for k, v in rows]
        if self.discrepancies:
            lines += ["", "## Discrepancies"]
            lines += [f"- {d}" for d in self.discrepancies]
        return "\n".join(lines) + "\n"
