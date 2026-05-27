"""
registry_refresh.py
===================
Lightweight file-mtime tracker for in-session hot-reload of model and
zone registries after promotion, without process restart.

Cheap path: one ``os.stat`` per check (typically per compute cycle). On
mtime advance, the caller's reload path fires once and the new mtime is
latched. No filesystem watchers, no threads — just ``stat()``.

Contract
--------
- ``needs_reload()`` returns False on the first call (caller is presumed
  to handle the initial load through its existing path; first call simply
  latches the current mtime).
- Subsequent advancements of the file's mtime return True exactly once,
  then re-latch.
- Missing file returns False (fail-open: don't trigger reload churn on a
  transient registry-not-yet-promoted state).

Used by the three runtime engines that hold long-lived registry state:
- HeuristicGaussianEngine  (gaussian_registry.json)
- ReplayMemoryEngine       (zone_registry.json — replay's zone context)
- BitNetZoneGate           (zone_registry.json — live zone gate)

This avoids the previous behaviour where ``promote_gaussian()`` updated
the registry but running engines kept their stale model until the next
full process restart — a real risk during 24/5 live sessions.
"""
from __future__ import annotations

from pathlib import Path
from typing import Union


class RegistryWatcher:
    """Tracks a single registry file's mtime; signals reload on advance."""

    __slots__ = ("_path", "_last_mtime", "_first_check")

    def __init__(self, path: Union[str, Path]):
        self._path = Path(path)
        self._last_mtime: float = 0.0
        self._first_check: bool = True

    def needs_reload(self) -> bool:
        """Return True iff the watched file's mtime advanced since last check.

        First call after construction returns False and latches the current
        mtime. Missing file returns False.
        """
        try:
            mtime = self._path.stat().st_mtime
        except OSError:
            return False
        if self._first_check:
            self._first_check = False
            self._last_mtime = mtime
            return False
        if mtime > self._last_mtime:
            self._last_mtime = mtime
            return True
        return False

    def mark_loaded(self) -> None:
        """Latch the current mtime without signalling a reload.

        Useful when the caller's __init__ does an initial load and wants to
        skip the first ``needs_reload()`` lazy-latch.
        """
        try:
            self._last_mtime = self._path.stat().st_mtime
            self._first_check = False
        except OSError:
            pass

    @property
    def path(self) -> Path:
        return self._path


__all__ = ["RegistryWatcher"]
