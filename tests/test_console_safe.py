import io
import logging

from utils.console_safe import SafeStreamHandler, safe_print, sanitize_for_console


class StrictEncodedStream(io.StringIO):
    def __init__(self, encoding: str):
        super().__init__()
        self._encoding = encoding

    @property
    def encoding(self) -> str:
        return self._encoding

    def write(self, s: str) -> int:
        s.encode(self.encoding, errors="strict")
        return super().write(s)


def test_sanitize_for_console_preserves_utf8_text():
    text = "unicode ok \u2705"
    assert sanitize_for_console(text, encoding="utf-8") == text


def test_safe_print_falls_back_on_unicode_encode_error():
    stream = StrictEncodedStream("cp1252")
    safe_print("emoji \U0001F4CA", file=stream)
    assert "emoji" in stream.getvalue()
    assert "?" in stream.getvalue()


def test_safe_print_supports_mixed_args():
    stream = io.StringIO()
    safe_print("count", 3, {"k": "v"}, file=stream, sep=" | ", end="")
    assert stream.getvalue() == "count | 3 | {'k': 'v'}"


def test_safe_stream_handler_retries_with_sanitized_output():
    stream = StrictEncodedStream("cp1252")
    handler = SafeStreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger("tests.console_safe.handler")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    logger.info("ready \U0001F50D")
    out = stream.getvalue()
    assert "ready" in out
    assert "?" in out
