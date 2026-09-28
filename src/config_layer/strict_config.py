"""Strict config reads: no defaults, no fallbacks; a missing key fails closed (EPIC-84).

User rule 2026-09-28: every value that affects behaviour comes from a declared, loaded
config. A missing key is an error, never a code literal. This module is the one shared
primitive; the per-module ``_require`` copies fold into it.

Two failure surfaces, one error type:

* **Load / construction time** -- ``require`` / ``require_all`` / ``require_section``
  raise ``ConfigKeyMissingError``. ``require_all`` collects every missing key first, so
  one failure lists them all. There is no environment switch and no warn-only mode.
* **Trade time** (a per-trade payload value such as ``risk_percent``) -- ``missing_keys``
  + ``missing_reason`` let the caller REJECT that one trade with a named reason
  (``config_key_missing:<section>.<key>``) instead of substituting a literal.

A key that is present with value ``None`` is PRESENT: ``None`` is a declared value
(e.g. "no time-stop"). Only absence fails.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

__all__ = [
    "ConfigKeyMissingError",
    "REASON_PREFIX",
    "missing_keys",
    "missing_reason",
    "require",
    "require_all",
    "require_section",
]

#: Prefix of the reject reason emitted when a trade-time value is absent.
REASON_PREFIX = "config_key_missing"


class ConfigKeyMissingError(KeyError):
    """One or more required config keys are absent.

    Carries every missing key plus where it was looked for, so the message alone is
    enough to fix the config: key(s), section, consumer, config version, source path.
    """

    def __init__(
        self,
        missing: Iterable[str],
        *,
        section: str,
        consumer: str,
        version: str | None = None,
        source: str | None = None,
    ) -> None:
        self.missing = tuple(missing)
        self.section = section
        self.consumer = consumer
        self.version = version
        self.source = source
        super().__init__(self.missing)

    def __str__(self) -> str:
        keys = ", ".join(f"{self.section}.{k}" for k in self.missing)
        where = []
        if self.version:
            where.append(f"version={self.version}")
        if self.source:
            where.append(f"source={self.source}")
        suffix = f" ({'; '.join(where)})" if where else ""
        return (
            f"missing required config key(s) [{keys}] for {self.consumer}{suffix}. "
            f"No default applies: declare the key in the config."
        )


def _check_mapping(section: Any, section_name: str, consumer: str,
                   version: str | None, source: str | None) -> Mapping:
    if isinstance(section, Mapping):
        return section
    if section is None:
        raise ConfigKeyMissingError(
            ["<section>"], section=section_name, consumer=consumer,
            version=version, source=source,
        )
    raise TypeError(
        f"config section '{section_name}' for {consumer} must be a mapping, "
        f"got {type(section).__name__}"
    )


def require(
    section: Mapping,
    key: str,
    *,
    section_name: str,
    consumer: str,
    version: str | None = None,
    source: str | None = None,
) -> Any:
    """Return ``section[key]``; raise ``ConfigKeyMissingError`` if the key is absent."""
    sec = _check_mapping(section, section_name, consumer, version, source)
    if key not in sec:
        raise ConfigKeyMissingError(
            [key], section=section_name, consumer=consumer,
            version=version, source=source,
        )
    return sec[key]


def require_all(
    section: Mapping,
    keys: Iterable[str],
    *,
    section_name: str,
    consumer: str,
    version: str | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """Return ``{key: section[key]}`` for every key; raise once listing ALL absent keys."""
    sec = _check_mapping(section, section_name, consumer, version, source)
    wanted = list(keys)
    absent = [k for k in wanted if k not in sec]
    if absent:
        raise ConfigKeyMissingError(
            absent, section=section_name, consumer=consumer,
            version=version, source=source,
        )
    return {k: sec[k] for k in wanted}


def require_section(
    cfg: Mapping,
    name: str,
    *,
    consumer: str,
    version: str | None = None,
    source: str | None = None,
) -> Mapping:
    """Return the nested section ``cfg[name]``; absent or non-mapping fails closed."""
    top = _check_mapping(cfg, "<root>", consumer, version, source)
    if name not in top:
        raise ConfigKeyMissingError(
            [name], section="<root>", consumer=consumer,
            version=version, source=source,
        )
    return _check_mapping(top[name], name, consumer, version, source)


def missing_keys(payload: Mapping, keys: Iterable[str]) -> list[str]:
    """Trade-time check: the keys absent from ``payload`` (empty list = complete)."""
    if not isinstance(payload, Mapping):
        return list(keys)
    return [k for k in keys if k not in payload]


def missing_reason(section_name: str, missing: Iterable[str]) -> str:
    """Reject reason for a trade whose payload lacks required values."""
    return f"{REASON_PREFIX}:" + ",".join(f"{section_name}.{k}" for k in missing)
