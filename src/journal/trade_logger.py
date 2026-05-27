# trade_logger.py — persists TradeRecord to JSONL log
#
# Integration rule: all writes MUST also route through core.collector so there
# is a single authoritative audit trail in logs/collector.jsonl.
# TradeLogger retains its own trade_journal.jsonl for outcome-level queries.
import json
import logging
from pathlib import Path
from typing import Optional

from src.journal.schema import TradeRecord

log = logging.getLogger(__name__)

_DEFAULT_LOG = Path("logs/trade_journal.jsonl")

try:
    import core.collector as _collector_mod
    _COLLECTOR_AVAILABLE = True
except Exception:
    _collector_mod = None  # type: ignore[assignment]
    _COLLECTOR_AVAILABLE = False

# Threshold above which trade_journal.jsonl is flagged as systemically corrupted.
MAX_CORRUPTION_RATIO: float = 0.10

try:
    from src.utils.integrity_events import emit_integrity_event  # noqa: F401
except Exception:  # pragma: no cover
    def emit_integrity_event(*_a, **_kw):  # type: ignore[no-redef]
        return None


class TradeLogger:
    """
    Appends TradeRecord entries to logs/trade_journal.jsonl.

    Also routes each record through core.collector so the authoritative audit
    trail in logs/collector.jsonl stays complete (integration rule §6.7).
    """

    def __init__(self, log_path: Optional[str] = None):
        self._path = Path(log_path) if log_path else _DEFAULT_LOG

    def log(self, record: TradeRecord) -> None:
        # Primary write — outcome-level JSONL (trade_journal.jsonl)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(record.to_json() + "\n")
        except Exception as exc:
            log.warning("TradeLogger: write failed: %s", exc)

        # Secondary write — route through Collector for unified audit trail.
        # Maps TradeRecord fields to Collector.log() dict format.
        if _COLLECTOR_AVAILABLE and _collector_mod is not None:
            try:
                _collector_record = {
                    "features": {"id": record.trade_id, "symbol": record.symbol},
                    "engines": {},
                    "decision": record.engine_action or record.override_action or "UNKNOWN",
                    "pnl": record.pnl,
                    "fusion": {},
                    "kind": "trade_outcome",
                    "result": record.result,
                    "regime": record.regime,
                    "rr": record.rr,
                }
                _collector_mod.Collector().log(_collector_record)
            except Exception as exc:
                log.debug("TradeLogger: Collector routing failed (ignored): %s", exc)

    def load_all(self) -> list:
        """Load all TradeRecord dicts from the log file.

        Malformed lines no longer fail silently — they emit a JSONL_CORRUPTION
        integrity event and (if the file is >10% malformed) a
        JSONL_CORRUPTION_THRESHOLD_EXCEEDED event. The return shape is
        unchanged: a list of dicts for the valid lines.
        """
        if not self._path.exists():
            return []
        records: list = []
        malformed = 0
        valid = 0
        with open(self._path, encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                    valid += 1
                except json.JSONDecodeError as exc:
                    malformed += 1
                    emit_integrity_event(
                        "JSONL_CORRUPTION",
                        "WARNING",
                        "src.journal.trade_logger",
                        {
                            "path":        str(self._path),
                            "line_number": lineno,
                            "raw_preview": line[:160],
                            "error":       str(exc),
                        },
                    )
        total = malformed + valid
        if total and (malformed / total) > MAX_CORRUPTION_RATIO:
            emit_integrity_event(
                "JSONL_CORRUPTION_THRESHOLD_EXCEEDED",
                "ERROR",
                "src.journal.trade_logger",
                {
                    "path":             str(self._path),
                    "malformed_lines":  malformed,
                    "valid_lines":      valid,
                    "corruption_ratio": malformed / total,
                },
            )
        return records
