"""Console-safe output helpers for mixed terminal encodings."""

from __future__ import annotations

import logging
import sys
from locale import getpreferredencoding
from typing import TextIO


def sanitize_for_console(text: str, encoding: str | None = None, errors: str = "replace") -> str:
    """
    Return a console-safe representation of text for the target encoding.

    Keeps text unchanged for compatible output streams and replaces only
    unsupported characters when needed.
    """
    target_encoding = encoding or getattr(sys.stdout, "encoding", None) or getpreferredencoding(False) or "utf-8"
    return text.encode(target_encoding, errors=errors).decode(target_encoding, errors=errors)


def safe_print(*args: object, sep: str = " ", end: str = "\n", file: TextIO | None = None, flush: bool = False) -> None:
    """
    Print with graceful Unicode fallback for non-UTF console encodings.
    """
    stream = file if file is not None else sys.stdout
    text = sep.join(str(arg) for arg in args) + end
    try:
        stream.write(text)
    except UnicodeEncodeError:
        stream.write(sanitize_for_console(text, encoding=getattr(stream, "encoding", None)))
    if flush:
        stream.flush()


class SafeStreamHandler(logging.StreamHandler):
    """
    StreamHandler variant that retries with sanitized text on encode failures.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # NOTE: We cannot rely on catching UnicodeEncodeError from super().emit()
        # because StreamHandler.emit() already swallows all exceptions via
        # handleError().  We own the write path directly so we can intercept at
        # stream.write() before the base-class exception handler hides the error.
        try:
            msg = self.format(record)
            stream = self.stream
            try:
                stream.write(msg + self.terminator)
            except UnicodeEncodeError:
                safe_msg = sanitize_for_console(msg, encoding=getattr(stream, "encoding", None))
                stream.write(safe_msg + self.terminator)
            self.flush()
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)
