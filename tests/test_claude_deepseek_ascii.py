"""ASCII-safety + entity-leak guard for Claude-deepseek.md.

The file is deliberately authored pure-ASCII so NO reader (cp1252-default tools included) can
mis-decode it. This test fails the moment a non-ASCII byte, an HTML entity, or a <br> tag
creeps back in.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "Claude-deepseek.md"


def _text() -> str:
    return F.read_text(encoding="utf-8")


def test_pure_ascii():
    text = _text()
    offenders = [(c, o) for o, c in enumerate(text) if ord(c) > 127]
    assert not offenders, (
        f"{len(offenders)} non-ASCII char(s) — this file must stay ASCII-only "
        f"(first: {offenders[:5]})"
    )


def test_no_html_entity_leak():
    text = _text()
    for token in ["&nbsp;", "&amp;", "&lt;", "<br>", "</br>"]:
        assert token not in text, f"HTML entity/break leaked into bootloader: {token!r}"