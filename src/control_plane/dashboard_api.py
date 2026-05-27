"""
dashboard_api.py
================
Read-only data API for the CRT Trading Dashboard.

All methods read directly from disk files — no imports from src.* to avoid
import-time side-effects (logging setup, config loading, etc.).
Thread-safe: stateless, no shared mutable state.
"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ── Path constants ────────────────────────────────────────────────────────────
REPO_ROOT           = Path(__file__).resolve().parents[2]
GAUSSIAN_REGISTRY   = REPO_ROOT / "models" / "gaussian_registry.json"
ACTIVE_VERSION_FILE = REPO_ROOT / "configs" / "production" / "ACTIVE_VERSION"
KILL_SWITCH_FILE    = REPO_ROOT / "logs" / "kill_switch_state.json"
RESULTS_DIR         = REPO_ROOT / "results"
LOGS_DIR            = REPO_ROOT / "logs"
MODELS_DIR          = REPO_ROOT / "models"
PROD_CONFIG_DIR     = REPO_ROOT / "configs" / "production"

# Instruments available for opportunity logs
KNOWN_INSTRUMENTS = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "EURCAD", "XAUUSD", "BTCUSDT", "ETHUSDT"]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_json(path: Path) -> dict | list | None:
    """Read and parse a JSON file. Returns None on any error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _iso_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _find_latest_trades_csv(instrument: str) -> Path | None:
    """
    Find the most recent INSTRUMENT_trades.csv under results/run_*/.
    Directory names embed timestamps (run_YYYYMMDD_HHMMSS_INSTRUMENT),
    so lexicographic sort gives chronological order.
    """
    pattern = RESULTS_DIR / f"run_*" / f"{instrument}_trades.csv"
    matches = sorted(REPO_ROOT.glob(f"results/run_*/{instrument}_trades.csv"))
    return matches[-1] if matches else None


def _estimate_line_count(path: Path, sample_lines: int = 20) -> int:
    """O(sample_lines) line-count estimate from file size + average line length."""
    try:
        file_size = path.stat().st_size
        if file_size == 0:
            return 0
        sample_bytes = 0
        n = 0
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                sample_bytes += len(line.encode("utf-8", errors="replace"))
                n += 1
                if n >= sample_lines:
                    break
        if n == 0:
            return 0
        avg = sample_bytes / n
        return int(file_size / avg) if avg > 0 else 0
    except Exception:
        return 0


# ── Main API class ─────────────────────────────────────────────────────────────

class TradingDashboardAPI:
    """
    Stateless read-only API for the trading dashboard.
    No caching — each call reads from disk.  Thread-safe by design.
    """

    # ── Status ────────────────────────────────────────────────────────────────

    def status_payload(self, instrument: str = "EURUSD") -> dict[str, Any]:
        """
        Returns per-instrument runtime status.
        Args:
            instrument: trading pair (e.g. "EURUSD", "BTCUSDT")
        Returns:
            instrument, active_config, active_model_version, active_model_corr,
            latest_run, kill_switch, trades_last_24h
        """
        # Active config version
        try:
            active_config = ACTIVE_VERSION_FILE.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            active_config = "unknown"

        # Per-instrument active model: scan models/{instrument}/ for latest run dir
        active_model_version = None
        active_model_corr    = None
        latest_run           = None
        inst_models_dir = MODELS_DIR / instrument
        try:
            if inst_models_dir.is_dir():
                runs = sorted(
                    d.name for d in inst_models_dir.iterdir() if d.is_dir()
                )
                if runs:
                    latest_run  = runs[-1]
                    run_dir     = inst_models_dir / latest_run
                    g_files     = sorted(run_dir.glob("gaussian_*.json"))
                    if g_files:
                        stem = g_files[-1].stem          # e.g. "gaussian_v6_2026_05_eur"
                        active_model_version = stem.replace("gaussian_", "", 1)
                        model_data = _read_json(g_files[-1])
                        if isinstance(model_data, dict):
                            m = model_data.get("metrics") or {}
                            active_model_corr = m.get("corr_expected_rr")
        except Exception:
            pass

        # Kill switch state (global — not per-instrument)
        ks: dict[str, Any] = {
            "tripped": False,
            "trip_reason": None,
            "trip_ts": None,
            "daily_loss_inr": None,
            "weekly_loss_inr": None,
        }
        raw_ks = _read_json(KILL_SWITCH_FILE)
        if isinstance(raw_ks, dict):
            ks["tripped"]         = bool(raw_ks.get("tripped", False))
            ks["trip_reason"]     = raw_ks.get("trip_reason") or None
            ks["trip_ts"]         = raw_ks.get("trip_ts") or None
            ks["daily_loss_inr"]  = raw_ks.get("daily_loss_inr")
            ks["weekly_loss_inr"] = raw_ks.get("weekly_loss_inr")

        # Trades in last 24h for the requested instrument
        trades_last_24h = 0
        csv_path = _find_latest_trades_csv(instrument)
        if csv_path:
            try:
                cutoff = _iso_now() - timedelta(hours=24)
                with open(csv_path, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        ts_raw = row.get("opened_at", "")
                        try:
                            ts = datetime.fromisoformat(ts_raw.replace(" ", "T"))
                            if ts.tzinfo is None:
                                ts = ts.replace(tzinfo=timezone.utc)
                            if ts >= cutoff:
                                trades_last_24h += 1
                        except (ValueError, AttributeError):
                            pass
            except Exception:
                pass

        return {
            "instrument":           instrument,
            "active_config":        active_config,
            "active_model_version": active_model_version,
            "active_model_corr":    active_model_corr,
            "latest_run":           latest_run,
            "kill_switch":          ks,
            "trades_last_24h":      trades_last_24h,
        }

    # ── Models ────────────────────────────────────────────────────────────────

    def models_payload(self) -> dict[str, Any]:
        """
        Returns all Gaussian model versions from the registry, sorted by
        trained_at descending (entries with no trained_at sort last).
        """
        try:
            reg = json.loads(GAUSSIAN_REGISTRY.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"models": [], "error": "registry not found"}
        except Exception as exc:
            return {"models": [], "error": str(exc)}

        models = []
        for key, entry in reg.items():
            if key.startswith("_") or not isinstance(entry, dict):
                continue
            m = entry.get("metrics") or {}
            models.append({
                "version":            entry.get("version", key),
                "active":             bool(entry.get("active", False)),
                "corr_expected_rr":   m.get("corr_expected_rr"),
                "calibration_error":  m.get("calibration_error"),
                "n_train":            m.get("n_train"),
                "trained_at":         entry.get("trained_at"),
                "run_id":             entry.get("run_id"),
                "instrument":         entry.get("instrument"),
            })

        # Sort by trained_at descending; None sorts last
        def _sort_key(e: dict) -> str:
            return e["trained_at"] or "0000"

        models.sort(key=_sort_key, reverse=True)
        return {"models": models}

    # ── All-4-Model versions ─────────────────────────────────────────────────

    def model_versions_payload(self) -> dict[str, Any]:
        """
        Returns current-in-use version info for all 4 training models:
          gaussian, zone_gate, rr_model, tradenet.

        Config-driven paths for zone_gate and rr_model are read from the
        active production config so the display always matches backtest reality.
        """
        # Defaults (override from active production config below)
        zone_path = MODELS_DIR / "zone_registry.json"
        rr_path   = MODELS_DIR / "rr_model.json"
        try:
            active = ACTIVE_VERSION_FILE.read_text(encoding="utf-8").strip().split()[0]
            cfg = _read_json(PROD_CONFIG_DIR / f"{active}.json")
            if cfg:
                er  = cfg.get("engine_runner", {})
                zrp = er.get("zone_registry_path")
                if zrp:
                    zone_path = REPO_ROOT / zrp
                rrf = cfg.get("rr_fusion", {}) or {}
                rrp = rrf.get("model_path") or (cfg.get("rr_model") or {}).get("model_path")
                if rrp:
                    rr_path = REPO_ROOT / rrp
        except Exception:
            pass

        return {
            "gaussian":  self._gaussian_model_version(),
            "zone_gate": self._zone_gate_version(zone_path),
            "rr_model":  self._rr_model_version(rr_path),
            "tradenet":  self._tradenet_version(),
        }

    def _gaussian_model_version(self) -> dict[str, Any]:
        try:
            reg = json.loads(GAUSSIAN_REGISTRY.read_text(encoding="utf-8"))
            for key, entry in reg.items():
                if key.startswith("_") or not isinstance(entry, dict):
                    continue
                if entry.get("active"):
                    m = entry.get("metrics") or {}
                    ver = entry.get("version", key)
                    model_file = MODELS_DIR / f"gaussian_{ver}.json"
                    return {
                        "version":           ver,
                        "corr":              m.get("corr_expected_rr"),
                        "calibration_error": m.get("calibration_error"),
                        "n_train":           m.get("n_train"),
                        "trained_at":        entry.get("trained_at"),
                        "file_exists":       model_file.exists(),
                        "status":            "active",
                    }
            return {"version": None, "status": "no-active", "file_exists": False}
        except Exception as exc:
            return {"version": None, "status": "error", "error": str(exc), "file_exists": False}

    def _zone_gate_version(self, zone_path: Path) -> dict[str, Any]:
        # ── Try new versioned registry first ─────────────────────────────────
        reg = _read_json(MODELS_DIR / "zone_gate_registry.json")
        if reg and isinstance(reg, dict):
            active_entry = next(
                (v for v in reg.values() if isinstance(v, dict) and v.get("active")),
                None,
            )
            if active_entry:
                mf_path = REPO_ROOT / active_entry.get("model_file", "")
                return {
                    "version":        active_entry["version"],
                    "zone_count":     active_entry.get("n_zones", 0),
                    "model_file":     active_entry.get("model_file", ""),
                    "trained_at":     (active_entry.get("trained_at") or "")[:10],
                    "total_versions": len(reg),
                    "status":         "ok" if mf_path.exists() else "file-missing",
                }
            return {"status": "no-active", "total_versions": len(reg), "zone_count": 0}

        # ── Fallback: read canonical zone_registry.json (pre-versioning) ─────
        if not zone_path.exists():
            return {"file": zone_path.name, "status": "missing", "zone_count": 0}
        try:
            data = _read_json(zone_path)
            if data is None:
                return {"file": zone_path.name, "status": "parse-error", "zone_count": 0}
            zones          = data.get("zones", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            schema_version = data.get("schema_version") if isinstance(data, dict) else None
            mtime = datetime.fromtimestamp(
                zone_path.stat().st_mtime, tz=timezone.utc
            ).strftime("%Y-%m-%d")
            return {
                "file":           zone_path.name,
                "zone_count":     len(zones),
                "schema_version": schema_version,
                "updated_at":     mtime,
                "total_versions": 1,
                "status":         "ok" if zones else "empty",
            }
        except Exception as exc:
            return {"file": zone_path.name, "status": "error", "error": str(exc), "zone_count": 0}

    def _rr_model_version(self, rr_path: Path) -> dict[str, Any]:
        # ── Try new versioned registry first ─────────────────────────────────
        reg = _read_json(MODELS_DIR / "rr_registry.json")
        if reg and isinstance(reg, dict):
            active_entry = next(
                (v for v in reg.values() if isinstance(v, dict) and v.get("active")),
                None,
            )
            if active_entry:
                mf_path = REPO_ROOT / active_entry.get("model_file", "") if active_entry.get("model_file") else None
                model_exists = mf_path.exists() if mf_path else False
                return {
                    "version":        active_entry["version"],
                    "n_samples":      active_entry.get("n_samples"),
                    "model_file":     active_entry.get("model_file"),
                    "dataset_file":   active_entry.get("dataset_file"),
                    "model_exists":   model_exists,
                    "trained_at":     (active_entry.get("trained_at") or "")[:10],
                    "total_versions": len(reg),
                    "status":         "ok" if model_exists else "no-model",
                }
            return {"status": "no-active", "total_versions": len(reg), "model_exists": False}

        # ── Fallback: check canonical files (pre-versioning) ─────────────────
        rr_dataset = MODELS_DIR / "rr_dataset.json"
        result: dict[str, Any] = {
            "model_file":     rr_path.name,
            "model_exists":   rr_path.exists(),
            "dataset_file":   rr_dataset.name if rr_dataset.exists() else None,
            "n_samples":      None,
            "schema_version": None,
            "total_versions": 1,
            "status":         "ok" if rr_path.exists() else "no-model",
        }
        if rr_path.exists():
            d = _read_json(rr_path)
            if isinstance(d, dict):
                result["n_samples"]      = d.get("n_samples")
                result["schema_version"] = d.get("schema_version")
        if result["n_samples"] is None and rr_dataset.exists():
            d = _read_json(rr_dataset)
            if isinstance(d, dict):
                result["n_samples"]      = d.get("n_samples")
                result["schema_version"] = d.get("schema_version")
        return result

    def _tradenet_version(self) -> dict[str, Any]:
        # ── Try new versioned registry first ─────────────────────────────────
        reg = _read_json(MODELS_DIR / "tradenet_registry.json")
        if reg and isinstance(reg, dict):
            active_entry = next(
                (v for v in reg.values() if isinstance(v, dict) and v.get("active")),
                None,
            )
            if active_entry:
                mf_path = REPO_ROOT / active_entry.get("model_file", "")
                return {
                    "version":        active_entry["version"],
                    "model_file":     active_entry.get("model_file", ""),
                    "trained_at":     (active_entry.get("trained_at") or "")[:10],
                    "metrics":        active_entry.get("metrics", {}),
                    "total_versions": len(reg),
                    "status":         "ok" if mf_path.exists() else "file-missing",
                }
            return {"status": "no-active", "total_versions": len(reg)}

        # ── Fallback: glob .pth files (pre-registry) ─────────────────────────
        pth_files = sorted(MODELS_DIR.glob("tradenet_p5_*.pth"))
        if not pth_files:
            return {"file": None, "version": None, "trained_at": None,
                    "count": 0, "total_versions": 0, "status": "no-files"}
        latest = pth_files[-1]
        mtime  = datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d")
        return {
            "file":           latest.name,
            "version":        latest.stem.replace("tradenet_p5_", ""),
            "trained_at":     mtime,
            "count":          len(pth_files),
            "total_versions": len(pth_files),
            "status":         "ok",
        }

    # ── Promote model ─────────────────────────────────────────────────────────

    def promote_model_payload(self, version: str, force: bool = False) -> dict[str, Any]:
        """
        Set `version` as active in gaussian_registry.json.
        Atomic write: write to .tmp then os.replace().

        NOTE: No cross-process file lock is held here.  model_registry.py uses
        its own _file_lock advisory lock.  Last-writer-wins via os.replace()
        is sufficient for operator use from the dashboard.
        """
        try:
            reg = json.loads(GAUSSIAN_REGISTRY.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"ok": False, "reason": f"cannot read registry: {exc}", "active_version": None}

        # Validate version exists and is not a meta key
        if version.startswith("_") or version not in reg or not isinstance(reg[version], dict):
            return {"ok": False, "reason": f"version '{version}' not found in registry", "active_version": None}

        if not force and reg[version].get("active"):
            return {"ok": False, "reason": f"version '{version}' is already active", "active_version": version}

        try:
            # Deactivate all, activate target
            for key, entry in reg.items():
                if key.startswith("_") or not isinstance(entry, dict):
                    continue
                entry["active"] = False
            reg[version]["active"] = True

            # Atomic write
            tmp = GAUSSIAN_REGISTRY.with_suffix(".tmp")
            tmp.write_text(json.dumps(reg, indent=2), encoding="utf-8")
            os.replace(tmp, GAUSSIAN_REGISTRY)

            return {"ok": True, "reason": f"promoted {version}", "active_version": version}

        except Exception as exc:
            return {"ok": False, "reason": str(exc), "active_version": None}

    # ── Non-Gaussian model registry lists ─────────────────────────────────────

    def _promote_registry(self, reg_path: Path, version: str, label: str) -> dict[str, Any]:
        """Generic atomic promote for any model registry JSON."""
        try:
            reg = json.loads(reg_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"ok": False, "reason": f"cannot read {label} registry: {exc}"}
        if version not in reg or not isinstance(reg[version], dict):
            return {"ok": False, "reason": f"{label} version '{version}' not found"}
        for k, e in reg.items():
            if isinstance(e, dict):
                e["active"] = False
        reg[version]["active"] = True
        tmp = reg_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(reg, indent=2), encoding="utf-8")
        os.replace(tmp, reg_path)
        return {"ok": True, "reason": f"{label} promoted: {version}", "active_version": version}

    def zone_gate_models_payload(self) -> dict[str, Any]:
        reg = _read_json(MODELS_DIR / "zone_gate_registry.json")
        if not reg:
            return {"models": [], "error": "zone_gate_registry.json not found"}
        models = []
        for key, entry in reg.items():
            if not isinstance(entry, dict):
                continue
            mf = entry.get("model_file", "")
            models.append({
                "version":              entry.get("version", key),
                "active":               bool(entry.get("active", False)),
                "n_zones":              entry.get("n_zones", 0),
                "n_clusters_requested": entry.get("n_clusters_requested", 0),
                "trained_at":           (entry.get("trained_at") or "")[:10],
                "model_file":           mf,
                "file_exists":          (REPO_ROOT / mf).exists() if mf else False,
                "run_id":               entry.get("run_id"),
                "instrument":           entry.get("instrument"),
            })
        models.sort(key=lambda x: x.get("trained_at") or "0000", reverse=True)
        return {"models": models}

    def rr_models_payload(self) -> dict[str, Any]:
        reg = _read_json(MODELS_DIR / "rr_registry.json")
        if not reg:
            return {"models": [], "error": "rr_registry.json not found"}
        models = []
        for key, entry in reg.items():
            if not isinstance(entry, dict):
                continue
            m = entry.get("metrics") or {}
            models.append({
                "version":      entry.get("version", key),
                "active":       bool(entry.get("active", False)),
                "n_samples":    entry.get("n_samples"),
                "n_features":   entry.get("n_features", 35),
                "ridge_alpha":  m.get("ridge_alpha"),
                "model_file":   entry.get("model_file"),
                "model_exists": bool(entry.get("model_exists", False)),
                "dataset_file": entry.get("dataset_file"),
                "trained_at":   (entry.get("trained_at") or "")[:10],
                "run_id":       entry.get("run_id"),
                "instrument":   entry.get("instrument"),
            })
        models.sort(key=lambda x: x.get("trained_at") or "0000", reverse=True)
        return {"models": models}

    def tradenet_models_payload(self) -> dict[str, Any]:
        reg = _read_json(MODELS_DIR / "tradenet_registry.json")
        if not reg:
            return {"models": [], "error": "tradenet_registry.json not found"}
        models = []
        for key, entry in reg.items():
            if not isinstance(entry, dict):
                continue
            mf = entry.get("model_file", "")
            mf_path = REPO_ROOT / mf if mf else None
            models.append({
                "version":    entry.get("version", key),
                "active":     bool(entry.get("active", False)),
                "model_file": mf,
                "trained_at": (entry.get("trained_at") or "")[:10],
                "metrics":    entry.get("metrics", {}),
                "file_exists": mf_path.exists() if mf_path else False,
                "run_id":     entry.get("run_id"),
                "instrument": entry.get("instrument"),
            })
        models.sort(key=lambda x: x.get("trained_at") or "0000", reverse=True)
        return {"models": models}

    def promote_zone_gate_payload(self, version: str) -> dict[str, Any]:
        return self._promote_registry(MODELS_DIR / "zone_gate_registry.json", version, "zone_gate")

    def promote_rr_payload(self, version: str) -> dict[str, Any]:
        return self._promote_registry(MODELS_DIR / "rr_registry.json", version, "rr")

    def promote_tradenet_payload(self, version: str) -> dict[str, Any]:
        return self._promote_registry(MODELS_DIR / "tradenet_registry.json", version, "tradenet")

    # ── Opportunities ─────────────────────────────────────────────────────────

    def opportunities_payload(
        self,
        instrument: str = "EURUSD",
        page: int = 1,
        per_page: int = 20,
        direction: str = "",
        outcome: str = "",
    ) -> dict[str, Any]:
        """
        Stream-paginated read of opportunities_{instrument}.jsonl.
        Never loads the full file (289 MB for EURUSD).
        Features dict is excluded from response records.
        """
        path = self._find_opportunity_file(instrument)
        empty = {
            "records": [], "page": page, "per_page": per_page,
            "total_count_estimate": 0, "has_more": False, "count_is_estimate": True,
        }
        if path is None:
            return empty

        filtered = bool(direction or outcome)
        total_estimate = _estimate_line_count(path)
        skip = (page - 1) * per_page

        records: list[dict] = []
        matched = 0
        extra = False  # did we see a record beyond per_page (for has_more)?

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for raw_line in f:
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    try:
                        rec = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue

                    # Apply filters
                    if direction and rec.get("direction") != direction:
                        continue
                    if outcome and rec.get("outcome") != outcome:
                        continue

                    matched += 1
                    if matched <= skip:
                        continue
                    if len(records) >= per_page:
                        extra = True
                        break

                    # Omit features to keep response lean
                    records.append({
                        "timestamp":        rec.get("timestamp"),
                        "instrument":       rec.get("instrument"),
                        "direction":        rec.get("direction"),
                        "outcome":          rec.get("outcome"),
                        "rr_achieved":      rec.get("rr_achieved"),
                        "duration_candles": rec.get("duration_candles"),
                        "mfe":              rec.get("mfe"),
                        "mae":              rec.get("mae"),
                    })
        except Exception as exc:
            return {**empty, "error": str(exc)}

        return {
            "records":              records,
            "page":                 page,
            "per_page":             per_page,
            "total_count_estimate": total_estimate,
            "has_more":             extra,
            "count_is_estimate":    True,
        }

    # ── Opportunity helpers ───────────────────────────────────────────────────

    def _find_opportunity_file(self, instrument: str) -> "Path | None":
        """Resolve the latest opportunities JSONL for an instrument.

        Priority:
          1. logs/{instrument}/{latest_run_dir}/opportunities.jsonl  (scanner output)
          2. logs/opportunities_{instrument}.jsonl                   (legacy flat file)
        Returns None if neither exists.
        """
        run_dir = LOGS_DIR / instrument
        if run_dir.is_dir():
            runs = sorted(
                (d for d in run_dir.iterdir() if d.is_dir()),
                key=lambda d: d.name,
                reverse=True,
            )
            for run in runs:
                candidate = run / "opportunities.jsonl"
                if candidate.exists():
                    return candidate
        flat = LOGS_DIR / f"opportunities_{instrument}.jsonl"
        return flat if flat.exists() else None

    # ── Opportunity stats ─────────────────────────────────────────────────────

    def opportunity_stats_payload(self, instrument: str = "EURUSD") -> dict[str, Any]:
        """
        Aggregate win rates from the first 10,000 records of the opportunity log.
        Win = rr_achieved > 0.
        Session comes from record['features']['session'] (float like 1.0, 2.0, 3.0).
        Also returns avg_rr across the sampled window.
        """
        path = self._find_opportunity_file(instrument)
        empty = {
            "win_rate_by_direction": {},
            "win_rate_by_session":   {},
            "outcome_distribution":  {},
            "total_sampled":         0,
            "avg_rr":                None,
        }
        if path is None:
            return empty

        dir_wins: dict[str, int] = {}
        dir_total: dict[str, int] = {}
        sess_wins: dict[str, int] = {}
        sess_total: dict[str, int] = {}
        outcome_counts: dict[str, int] = {}
        rr_sum:   float = 0.0
        rr_count: int   = 0
        n = 0

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for raw_line in f:
                    if n >= 10_000:
                        break
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    try:
                        rec = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("type") == "run_header":
                        continue

                    n += 1
                    d   = rec.get("direction", "unknown")
                    rr  = float(rec.get("rr_achieved", 0.0) or 0.0)
                    win = rr > 0
                    oc  = rec.get("outcome", "UNKNOWN")

                    # avg_rr accumulator
                    rr_sum   += rr
                    rr_count += 1

                    # Direction win rate
                    dir_total[d] = dir_total.get(d, 0) + 1
                    if win:
                        dir_wins[d] = dir_wins.get(d, 0) + 1

                    # Session win rate (from nested features)
                    feats = rec.get("features") or {}
                    sess_raw = feats.get("session")
                    if sess_raw is not None:
                        sess_key = str(float(sess_raw))
                        sess_total[sess_key] = sess_total.get(sess_key, 0) + 1
                        if win:
                            sess_wins[sess_key] = sess_wins.get(sess_key, 0) + 1

                    # Outcome distribution
                    outcome_counts[oc] = outcome_counts.get(oc, 0) + 1

        except Exception:
            pass

        wr_dir  = {d: round(dir_wins.get(d, 0) / dir_total[d], 4)
                   for d in dir_total if dir_total[d] > 0}
        wr_sess = {s: round(sess_wins.get(s, 0) / sess_total[s], 4)
                   for s in sess_total if sess_total[s] > 0}

        return {
            "win_rate_by_direction": wr_dir,
            "win_rate_by_session":   wr_sess,
            "outcome_distribution":  outcome_counts,
            "total_sampled":         n,
            "avg_rr":                round(rr_sum / rr_count, 4) if rr_count else None,
        }

    def scan_jobs_payload(self, instrument: str = "EURUSD") -> dict[str, Any]:
        """List completed opportunity scanner runs for an instrument (latest 20)."""
        run_dir = LOGS_DIR / instrument
        if not run_dir.is_dir():
            return {"jobs": []}
        jobs: list[dict] = []
        for d in sorted(run_dir.iterdir(), key=lambda d: d.name, reverse=True):
            if not d.is_dir():
                continue
            opp_file = d / "opportunities.jsonl"
            if not opp_file.exists():
                continue
            run_id   = d.name          # "YYYYMMDD_HHMMSS"
            job_time = run_id
            rec_est  = _estimate_line_count(opp_file)
            # Try to read run_header for richer metadata
            try:
                with open(opp_file, "r", encoding="utf-8", errors="replace") as f:
                    first_line = f.readline().strip()
                hdr = json.loads(first_line) if first_line else {}
                if hdr.get("type") == "run_header":
                    job_time = hdr.get("started_at", run_id)[:16].replace("T", " ")
            except Exception:
                pass
            jobs.append({
                "id":     f"SCAN-{run_id}",
                "inst":   instrument,
                "time":   job_time,
                "rec":    f"{max(0, rec_est - 1):,}",   # subtract header line
                "status": "Completed",
            })
        return {"jobs": jobs[:20]}

    def opportunity_analytics_payload(self, instrument: str = "EURUSD") -> dict[str, Any]:
        """Stride-sampled analytics for scatter + time-series charts.

        Reads up to ~2,000 records uniformly across the file (stride-based).
        Returns:
          scatter_points     — list of {x, y, color} (max 300)
          outcomes_over_time — list of {period, tp, sl, to} bucketed by quarter
        """
        path = self._find_opportunity_file(instrument)
        empty: dict[str, Any] = {"scatter_points": [], "outcomes_over_time": []}
        if path is None:
            return empty

        total_lines = _estimate_line_count(path)
        stride      = max(1, total_lines // 2_000)
        OUTCOME_COLOR = {
            "TP_HIT":  "#22c55e",
            "SL_HIT":  "#ef4444",
            "TIMEOUT": "#facc15",
        }
        scatter: list[dict] = []
        buckets: dict[str, dict] = {}

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for i, raw_line in enumerate(f):
                    if i % stride != 0:
                        continue
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    try:
                        rec = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("type") == "run_header":
                        continue

                    outcome = rec.get("outcome", "UNKNOWN")
                    feats   = rec.get("features") or {}
                    rr      = float(rec.get("rr_achieved", 0) or 0)

                    # Scatter: rsi_14 as x-axis, rr_achieved mapped to 0–100 as y-axis
                    rsi = float(feats.get("rsi_14", 50) or 50)
                    y   = min(100.0, max(0.0, (rr + 1) * 50.0))
                    scatter.append({
                        "x":     round(rsi, 1),
                        "y":     round(y, 1),
                        "color": OUTCOME_COLOR.get(outcome, "#7f8da6"),
                    })

                    # Time-series: bucket by quarter
                    ts = rec.get("timestamp", "")
                    if ts and len(ts) >= 7:
                        try:
                            yr  = int(ts[:4])
                            mo  = int(ts[5:7])
                            qtr = (mo - 1) // 3 + 1
                            key = f"{yr}-Q{qtr}"
                            if key not in buckets:
                                buckets[key] = {"tp": 0, "sl": 0, "to": 0}
                            if outcome == "TP_HIT":
                                buckets[key]["tp"] += 1
                            elif outcome == "SL_HIT":
                                buckets[key]["sl"] += 1
                            elif outcome == "TIMEOUT":
                                buckets[key]["to"] += 1
                        except ValueError:
                            pass
        except Exception:
            return empty

        outcomes_over_time = [
            {"period": k, **v}
            for k, v in sorted(buckets.items())
        ]
        return {
            "scatter_points":     scatter[:300],
            "outcomes_over_time": outcomes_over_time,
        }

    # ── Trades ────────────────────────────────────────────────────────────────

    def trades_payload(
        self,
        instrument: str = "EURUSD",
        page: int = 1,
        per_page: int = 50,
    ) -> dict[str, Any]:
        """
        Paginated trade journal from the most recent INSTRUMENT_trades.csv.
        Returns a subset of columns suitable for the dashboard table.
        """
        empty = {"records": [], "page": page, "per_page": per_page, "total_count": 0}
        csv_path = _find_latest_trades_csv(instrument)
        if csv_path is None:
            return empty

        rows: list[dict] = []
        try:
            with open(csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        rows.append({
                            "trade_id":     row.get("trade_id", ""),
                            "opened_at":    row.get("opened_at", ""),
                            "direction":    row.get("direction", ""),
                            "pnl_rr_net":   _safe_float(row.get("pnl_rr_net")),
                            "exit_reason":  row.get("exit_reason", ""),
                            "session":      row.get("session", ""),
                            "capital_after": _safe_float(row.get("capital_after")),
                        })
                    except Exception:
                        continue
        except Exception as exc:
            return {**empty, "error": str(exc)}

        total = len(rows)
        start = (page - 1) * per_page
        page_rows = rows[start: start + per_page]

        return {
            "records":     page_rows,
            "page":        page,
            "per_page":    per_page,
            "total_count": total,
        }

    # ── Equity curve ──────────────────────────────────────────────────────────

    def equity_curve_payload(self, instrument: str = "EURUSD") -> dict[str, Any]:
        """
        Cumulative PnL curve from the most recent INSTRUMENT_trades.csv.
        Downsampled to last-value-per-date (caps at ~500 chart points).
        """
        csv_path = _find_latest_trades_csv(instrument)
        if csv_path is None:
            return {"curve": []}

        rows = []
        try:
            with open(csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        rows.append({
                            "opened_at":    row.get("opened_at", ""),
                            "pnl_rr_net":   _safe_float(row.get("pnl_rr_net"), 0.0),
                            "capital_after": _safe_float(row.get("capital_after", 0.0)),
                        })
                    except Exception:
                        continue
        except Exception:
            return {"curve": []}

        # Sort by opened_at (ISO strings sort lexicographically)
        rows.sort(key=lambda r: r["opened_at"])

        # Accumulate cumulative PnL, then downsample to last-per-date
        cumulative = 0.0
        # date → (cumulative_pnl_rr, capital_after)
        by_date: dict[str, tuple[float, float]] = {}
        for r in rows:
            cumulative += r["pnl_rr_net"]
            date = r["opened_at"][:10]  # YYYY-MM-DD
            by_date[date] = (round(cumulative, 4), r["capital_after"])

        curve = [
            {"date": d, "cumulative_pnl_rr": v[0], "capital": v[1]}
            for d, v in sorted(by_date.items())
        ]
        return {"curve": curve}

    # ── Backtest history ──────────────────────────────────────────────────────

    def backtest_history_payload(self) -> dict[str, Any]:
        """
        List all p5_calibration_*.json files in results/, sorted by mtime desc.
        """
        files = sorted(
            REPO_ROOT.glob("results/p5_calibration_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        backtests = []
        for p in files:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                ev   = data.get("eval") or {}
                tm   = data.get("train_metrics") or {}
                mtime_iso = datetime.fromtimestamp(
                    p.stat().st_mtime, tz=timezone.utc
                ).strftime("%Y-%m-%dT%H:%M:%SZ")
                backtests.append({
                    "filename":            p.name,
                    "version":             data.get("version", p.stem),
                    "n_samples":           data.get("n_samples"),
                    "corr_expected_rr":    ev.get("corr_expected_rr"),
                    "calibration_error":   ev.get("calibration_error"),
                    "verdict":             data.get("verdict"),
                    "integration_approved": data.get("integration_approved"),
                    "trained_at":          tm.get("trained_at") or data.get("trained_at"),
                    "mtime":               mtime_iso,
                })
            except json.JSONDecodeError:
                backtests.append({"filename": p.name, "error": "parse error"})
            except Exception as exc:
                backtests.append({"filename": p.name, "error": str(exc)})

        return {"backtests": backtests}

    # ── Available instruments ─────────────────────────────────────────────────

    def instruments_payload(self) -> dict[str, Any]:
        """
        Return instruments sourced from the active production config.
        Combines data_ingestion.pairs (forex) + inout.scanner.allowed_symbols (crypto).
        Falls back to KNOWN_INSTRUMENTS if the config cannot be read.
        """
        try:
            active_ver  = ACTIVE_VERSION_FILE.read_text(encoding="utf-8").strip()
            cfg_path    = PROD_CONFIG_DIR / f"{active_ver}.json"
            cfg         = _read_json(cfg_path) or {}
            pairs       = cfg.get("data_ingestion", {}).get("pairs", [])
            syms        = cfg.get("inout", {}).get("scanner", {}).get("allowed_symbols", [])
            merged      = sorted(set(pairs) | set(syms))
            if merged:
                return {"instruments": merged}
        except Exception:
            pass
        # Fallback: return first two known instruments
        return {"instruments": KNOWN_INSTRUMENTS[:2]}


    # ── Groq model explainer ──────────────────────────────────────────────────

    def explain_model_payload(self, model_type: str, version: str) -> dict[str, Any]:
        """Call GroqClient to generate a plain-English explanation of model training results.

        model_type: one of "gaussian", "zone_gate", "rr", "tradenet"
        version:    registry key (e.g. "v5_auto_2026_06_eth")
        Returns:    {"ok": True, "explanation": str} or {"ok": False, "error": str}
        """
        REGISTRIES: dict[str, Path] = {
            "gaussian":  MODELS_DIR / "gaussian_registry.json",
            "zone_gate": MODELS_DIR / "zone_gate_registry.json",
            "rr":        MODELS_DIR / "rr_registry.json",
            "tradenet":  MODELS_DIR / "tradenet_registry.json",
        }
        reg_path = REGISTRIES.get(model_type)
        if not reg_path or not reg_path.exists():
            return {"ok": False, "error": f"Unknown model type or missing registry: {model_type}"}

        try:
            registry = json.loads(reg_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"ok": False, "error": f"Registry parse error: {exc}"}

        entry = registry.get(version)
        if not entry or not isinstance(entry, dict):
            return {"ok": False, "error": f"Version not found: {version}"}

        metrics = entry.get("metrics") or {}
        ctx_lines = [
            f"Model type: {model_type}",
            f"Version: {version}",
            f"Trained at: {(entry.get('trained_at') or '—')[:10]}",
            f"Active: {entry.get('active', False)}",
            f"Instrument: {entry.get('instrument', 'multi')}",
            f"Run ID: {entry.get('run_id', 'n/a')}",
        ]
        # Append all metric fields
        for k, v in metrics.items():
            ctx_lines.append(f"{k}: {v}")
        # Model-type-specific extras
        for field in ("n_zones", "n_samples", "n_features", "n_clusters_requested",
                      "ridge_alpha", "calibration_error", "corr_expected_rr"):
            val = entry.get(field)
            if val is not None:
                ctx_lines.append(f"{field}: {val}")
        if entry.get("n_train"):
            ctx_lines.append(f"n_train: {entry['n_train']}")

        context = "\n".join(ctx_lines)
        prompt = (
            f"You are an expert quant analyst reviewing a machine-learning trading model.\n\n"
            f"Model stats:\n{context}\n\n"
            f"In 3–5 bullet points, explain in plain English:\n"
            f"1. How good is this model (correlation, calibration, accuracy)?\n"
            f"2. Is the training dataset large enough to trust?\n"
            f"3. Any red flags or concerns?\n"
            f"4. Is it ready for live trading?\n"
            f"Be concise, specific, and use non-technical language where possible."
        )

        try:
            from src.agent.groq_client import GroqClient
            client = GroqClient()
            explanation = client.chat(prompt, max_tokens=512)
            if not explanation:
                return {"ok": False, "error": "Groq returned empty response (check GROQ_API_KEY or circuit breaker)"}
            return {"ok": True, "explanation": explanation, "version": version, "model_type": model_type}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


# ── Private helpers ───────────────────────────────────────────────────────────

def _safe_float(value: Any, default: float | None = None) -> float | None:
    """Cast value to float, return default on failure."""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
