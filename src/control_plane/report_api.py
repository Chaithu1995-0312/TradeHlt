"""
report_api.py — RunReportAPI: Excel generation + Groq LLM analysis for run history reports.

Stdlib-only imports plus openpyxl for Excel; urllib.request for Groq REST.
No src.* imports — operates on raw dicts passed from server routes.
"""
from __future__ import annotations

import io
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL   = "llama-3.1-8b-instant"   # llama3-8b-8192 decommissioned 2026-05
# Token budget: llama3-8b-8192 has 8 192-token context.
# Summary ~300 tokens, prompt overhead ~200 tokens, output 768 tokens → ~7 000 for logs.
# Stdout carries most signal (training metrics, verdicts) so gets 3× the budget.
_STDOUT_CHARS = 6_000
_STDERR_CHARS = 2_000

# Repo root = two levels above this file (src/control_plane/report_api.py)
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    """
    Parse <repo_root>/.env and populate os.environ for any key not already set.
    Supports KEY=VALUE and KEY="VALUE" lines; ignores comments and blank lines.
    Does NOT override keys already present in the environment.
    """
    env_path = _REPO_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        pass  # fail-open: missing / unreadable .env is not fatal


class RunReportAPI:
    """
    Stateless helper instantiated once in ControlPlaneServer.__init__.

    Public methods:
        excel_bytes(run, logs, artifacts) → bytes   (.xlsx)
        llm_analysis(run, logs, artifacts) → dict   (Groq analysis)
    """

    # ------------------------------------------------------------------
    # Excel report
    # ------------------------------------------------------------------
    def excel_bytes(
        self,
        run: dict[str, Any],
        logs: dict[str, str],
        artifacts: list[dict[str, Any]],
    ) -> bytes:
        """
        Build an xlsx workbook with 4 sheets:
          Sheet 1 — Summary   (run metadata + args)
          Sheet 2 — Stdout    (one line per row)
          Sheet 3 — Stderr    (one line per row)
          Sheet 4 — Artifacts (path / exists / size)

        Returns raw bytes suitable for HTTP response.
        Raises RuntimeError if openpyxl is missing.
        """
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill
        except ImportError:
            raise RuntimeError(
                "openpyxl not installed. Run: pip install openpyxl"
            )

        wb = openpyxl.Workbook()

        # ── Sheet 1: Summary ─────────────────────────────────────────
        ws1 = wb.active
        ws1.title = "Summary"
        hdr_font = Font(bold=True, color="FFFFFF")
        hdr_fill = PatternFill("solid", fgColor="0D3349")

        for col, h in enumerate(["Field", "Value"], 1):
            c = ws1.cell(row=1, column=col, value=h)
            c.font = hdr_font
            c.fill = hdr_fill

        summary_rows: list[tuple[str, Any]] = [
            ("Run ID",     run.get("run_id", "")),
            ("Command",    run.get("command_id", "")),
            ("Status",     run.get("status", "")),
            ("Exit Code",  run.get("exit_code", "")),
            ("Started At", run.get("started_at", "")),
            ("Ended At",   run.get("ended_at", "")),
            ("PID",        run.get("pid", "")),
            ("Error",      run.get("error") or ""),
        ]
        # Flatten args dict into individual rows
        for k, v in (run.get("args") or {}).items():
            summary_rows.append((f"arg:{k}", str(v)))

        for row_idx, (field, val) in enumerate(summary_rows, 2):
            ws1.cell(row=row_idx, column=1, value=field)
            ws1.cell(row=row_idx, column=2, value=str(val) if val is not None else "")

        ws1.column_dimensions["A"].width = 22
        ws1.column_dimensions["B"].width = 60

        # ── Sheet 2: Stdout ──────────────────────────────────────────
        ws2 = wb.create_sheet("Stdout")
        stdout = (logs.get("stdout") or "").strip()
        for i, line in enumerate(stdout.splitlines(), 1):
            ws2.cell(row=i, column=1, value=line)
        ws2.column_dimensions["A"].width = 120

        # ── Sheet 3: Stderr ──────────────────────────────────────────
        ws3 = wb.create_sheet("Stderr")
        stderr = (logs.get("stderr") or "").strip()
        for i, line in enumerate(stderr.splitlines(), 1):
            ws3.cell(row=i, column=1, value=line)
        ws3.column_dimensions["A"].width = 120

        # ── Sheet 4: Artifacts ───────────────────────────────────────
        ws4 = wb.create_sheet("Artifacts")
        for col, h in enumerate(["Path", "Exists", "Size (bytes)"], 1):
            ws4.cell(row=1, column=col, value=h).font = Font(bold=True)
        for row_idx, art in enumerate(artifacts, 2):
            ws4.cell(row=row_idx, column=1, value=art.get("path", ""))
            ws4.cell(row=row_idx, column=2, value=str(art.get("exists", "")))
            ws4.cell(row=row_idx, column=3, value=art.get("size", ""))
        ws4.column_dimensions["A"].width = 60

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Excel-as-context builder (shared between llm_analysis and tests)
    # ------------------------------------------------------------------
    def _build_excel_context(
        self,
        run: dict[str, Any],
        logs: dict[str, str],
        artifacts: list[dict[str, Any]],
    ) -> str:
        """
        Render the same four Excel sheets as plain text sections.
        This is passed verbatim to the LLM — it sees exactly what the Excel contains.

        Budget: ~6 000 chars stdout + ~3 000 chars stderr keeps total prompt
        under ~5 000 tokens (Groq llama3-8b-8192 context = 8 192 tokens).
        """
        lines: list[str] = []

        # ── Sheet 1: Summary ─────────────────────────────────────────
        lines.append("=" * 60)
        lines.append("SHEET 1 — RUN SUMMARY")
        lines.append("=" * 60)
        summary_rows = [
            ("Run ID",     run.get("run_id", "")),
            ("Command",    run.get("command_id", "")),
            ("Status",     run.get("status", "")),
            ("Exit Code",  run.get("exit_code", "")),
            ("Started At", run.get("started_at", "")),
            ("Ended At",   run.get("ended_at", "")),
            ("PID",        run.get("pid", "")),
            ("Error",      run.get("error") or ""),
        ]
        for k, v in (run.get("args") or {}).items():
            summary_rows.append((f"arg:{k}", str(v)))
        col_w = max(len(r[0]) for r in summary_rows) + 2
        for field, val in summary_rows:
            lines.append(f"{field:<{col_w}}{val}")

        # ── Sheet 2: Stdout ──────────────────────────────────────────
        lines.append("")
        lines.append("=" * 60)
        lines.append("SHEET 2 — STDOUT")
        lines.append("=" * 60)
        stdout_full = (logs.get("stdout") or "").strip()
        if stdout_full:
            # Keep last _STDOUT_CHARS chars; mark if truncated
            if len(stdout_full) > _STDOUT_CHARS:
                lines.append(f"[... truncated — showing last {_STDOUT_CHARS} chars ...]")
                lines.append(stdout_full[-_STDOUT_CHARS:])
            else:
                lines.append(stdout_full)
        else:
            lines.append("(empty)")

        # ── Sheet 3: Stderr ──────────────────────────────────────────
        lines.append("")
        lines.append("=" * 60)
        lines.append("SHEET 3 — STDERR")
        lines.append("=" * 60)
        stderr_full = (logs.get("stderr") or "").strip()
        if stderr_full:
            if len(stderr_full) > _STDERR_CHARS:
                lines.append(f"[... truncated — showing last {_STDERR_CHARS} chars ...]")
                lines.append(stderr_full[-_STDERR_CHARS:])
            else:
                lines.append(stderr_full)
        else:
            lines.append("(empty)")

        # ── Sheet 4: Artifacts ───────────────────────────────────────
        lines.append("")
        lines.append("=" * 60)
        lines.append("SHEET 4 — ARTIFACTS")
        lines.append("=" * 60)
        if artifacts:
            lines.append(f"{'Path':<70}  {'Exists':<8}  Size (bytes)")
            lines.append("-" * 90)
            for art in artifacts:
                path   = str(art.get("path", ""))
                exists = str(art.get("exists", ""))
                size   = str(art.get("size") or "")
                lines.append(f"{path:<70}  {exists:<8}  {size}")
        else:
            lines.append("(no artifacts)")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Groq LLM analysis — uses Excel content as context
    # ------------------------------------------------------------------
    def llm_analysis(
        self,
        run: dict[str, Any],
        logs: dict[str, str],
        artifacts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Build the same structured content that goes into the Excel file,
        pass it to Groq, and ask for bullet-point analysis of what happened.

        Returns:
            {"ok": True,  "analysis": "<bullet points>"}   on success
            {"ok": False, "error":    "<reason>"}           on any failure
        """
        _load_dotenv()
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            return {"ok": False, "error": "GROQ_API_KEY not set in environment (add to .env or export)"}

        excel_context = self._build_excel_context(run, logs, artifacts)

        divider = "=" * 60
        task_block = "\n".join([
            divider,
            "TASK: Analyse the run above and produce a clear bullet-point summary.",
            "Format your answer as bullet points ONLY (use the bullet character: •).",
            "Cover ALL of the following — one bullet per topic:",
            "  • What command ran and with which key arguments",
            "  • Whether the run succeeded or failed, and why",
            "  • Key numeric results visible in stdout (corr, calibration_error, fitness,",
            "    trade count, drawdown, win rate, verdict — whatever is present)",
            "  • Any errors, exceptions, or warnings found in stderr or stdout",
            "  • Which output files / artifacts were produced (and whether they exist on disk)",
            "  • Recommended next step for the operator",
            "Be factual and specific — quote actual numbers from the logs where available.",
            "No preamble, no explanation, no extra commentary — just the bullet points.",
        ])
        prompt = (
            "You are a trading-system analyst. "
            "Below is the complete run report (same data as the downloaded Excel file) "
            "for an automated backtest or model-training run.\n\n"
            + excel_context
            + "\n\n"
            + task_block
        )

        body = json.dumps({
            "model":       _GROQ_MODEL,
            "messages":    [{"role": "user", "content": prompt}],
            "max_tokens":  768,
            "temperature": 0.2,
        }).encode("utf-8")

        req = urllib.request.Request(
            _GROQ_URL,
            data=body,
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent":    "CRTControlPlane/1.0 (trading-system-analyst)",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = data["choices"][0]["message"]["content"]
            return {"ok": True, "analysis": text}
        except urllib.error.HTTPError as exc:
            body_err = exc.read().decode("utf-8", errors="replace")
            return {"ok": False, "error": f"HTTP {exc.code}: {body_err[:300]}"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
