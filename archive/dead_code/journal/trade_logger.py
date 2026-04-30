# ARCHIVED 2026-04-28 — Dead Code Pass
# Reason: zero importers in active src/; superseded by src/utils/trade_logger.py (active).
# Original: src/journal/trade_logger.py
# Action required on original: remove src/journal/trade_logger.py
# trade_logger.py — persists TradeRecord to JSONL log
import json
import logging
from pathlib import Path
from typing import Optional

from src.journal.schema import TradeRecord

log = logging.getLogger(__name__)

_DEFAULT_LOG = Path("logs/trade_journal.jsonl")


class TradeLogger:
    """Appends TradeRecord entries to logs/trade_journal.jsonl."""

    def __init__(self, log_path: Optional[str] = None):
        self._path = Path(log_path) if log_path else _DEFAULT_LOG

    def log(self, record: TradeRecord) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(record.to_json() + "\n")
        except Exception as exc:
            log.warning("TradeLogger: write failed: %s", exc)

    def load_all(self) -> list:
        if not self._path.exists():
            return []
        records = []
        with open(self._path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return records
