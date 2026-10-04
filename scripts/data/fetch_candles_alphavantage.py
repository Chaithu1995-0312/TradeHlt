#!/usr/bin/env python
"""
CLI: Fetch historical FX OHLCV candles from Alpha Vantage -> Tradelatest CSV.

Reads defaults from the 'alphavantage_data' section of the production config;
CLI flags override any config value.

Usage examples
--------------
# Fetch AUDUSD 15min candles for 2024 (requires free API key):
    python scripts/data/fetch_candles_alphavantage.py \\
        --pair AUDUSD --start 2024-01-01 --end 2025-01-01 \\
        --api-key YOUR_FREE_KEY

# Override interval and output directory:
    python scripts/data/fetch_candles_alphavantage.py \\
        --pair EURUSD --interval 60min \\
        --start 2025-01-01 --end 2025-06-01 \\
        --api-key YOUR_FREE_KEY --out data/alphavantage

Free API key: https://www.alphavantage.co/support/#api-key
Rate limit: 25 requests/day (free tier). Each monthly batch = 1 request.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# ── Path bootstrap ─────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve()
_ROOT = _HERE.parent.parent.parent
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

# ── Internal imports (business logic lives in src/, never here) ─────────────
from inout.alphavantage_candle_fetcher import (  # type: ignore
    AlphaVantageCandleFetcher,
    AlphaVantageFetcherConfig,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# Env var holding the Alpha Vantage key (read from repo-root .env or the process env).
_ENV_KEY = "fetch_candles_alphavantage_apikey"


# ── .env loader (stdlib only — mirrors llm_inference_client._load_dotenv) ────
def _load_dotenv(start: Path = _HERE) -> None:
    """Walk up from *start* until a .env file is found; inject KEY=VALUE pairs
    into os.environ without overwriting vars already set in the process env.
    The file is never echoed — only individual values are read at use sites."""
    for parent in [start, *start.parents]:
        dotenv = parent / ".env"
        if dotenv.is_file():
            try:
                for raw in dotenv.read_text(encoding="utf-8").splitlines():
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    line = line.removeprefix("export").strip()
                    if "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.split("#")[0].strip().strip("\"'")
                    if key and key not in os.environ:
                        os.environ[key] = val
            except Exception as exc:  # pragma: no cover - best-effort bootstrap
                logger.debug("Could not load .env at %s: %s", dotenv, exc)
            return


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch historical FX OHLCV candles from Alpha Vantage -> Tradelatest CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--pair", default=None, metavar="PAIR",
        help="6-char forex pair, e.g. AUDUSD, EURUSD (split at pos 3 into from/to symbols)",
    )
    parser.add_argument(
        "--interval", default=None,
        help="Candle interval: 1min 5min 15min 30min 60min (default: 15min)",
    )
    parser.add_argument("--start", required=True, metavar="YYYY-MM-DD", help="Start date (UTC, inclusive)")
    parser.add_argument("--end",   required=True, metavar="YYYY-MM-DD", help="End date (UTC, exclusive)")
    parser.add_argument(
        "--api-key", default=None, dest="api_key",
        help=("Alpha Vantage API key (optional; overrides config/env). Default source is the "
              "fetch_candles_alphavantage_apikey var in repo-root .env."),
    )
    parser.add_argument("--out", default=None, metavar="DIR", help="Output directory (default: data/alphavantage)")
    parser.add_argument(
        "--config",
        default="configs/production/v1_multi_2026_03.json",
        metavar="PATH",
        help="Path to production config JSON",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    _load_dotenv()  # make .env keys (e.g. fetch_candles_alphavantage_apikey) visible

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: config not found: {config_path}", file=sys.stderr)
        return 1

    with open(config_path, encoding="utf-8") as fh:
        prod_cfg = json.load(fh)

    # Build alphavantage_data section from config, then apply CLI overrides
    av_section: dict = dict(prod_cfg.get("alphavantage_data", {}))

    # Resolve API key: CLI > .env/env var (preferred) > legacy env var > config.
    api_key = (
        args.api_key
        or os.environ.get(_ENV_KEY)
        or os.environ.get("AV_API_KEY")
        or av_section.get("api_key", "")
    )
    if not api_key:
        print(
            "ERROR: Alpha Vantage API key not provided. "
            f"Set {_ENV_KEY} in the repo-root .env (preferred), use --api-key YOUR_KEY, "
            "or add api_key to the alphavantage_data config section.",
            file=sys.stderr,
        )
        return 1
    av_section["api_key"] = api_key

    if args.out:
        av_section["output_dir"] = args.out
    if not av_section.get("output_dir"):
        av_section["output_dir"] = "data/alphavantage"

    if args.interval:
        av_section["interval"] = args.interval
    if not av_section.get("interval"):
        av_section["interval"] = "15min"

    # Parse --pair AUDUSD -> from_symbol=AUD, to_symbol=USD
    if args.pair:
        pair = args.pair.upper().replace("/", "")
        if len(pair) != 6:
            print(
                f"ERROR: --pair must be a 6-character forex pair (e.g. AUDUSD), got '{args.pair}'",
                file=sys.stderr,
            )
            return 1
        av_section["from_symbol"] = pair[:3]
        av_section["to_symbol"]   = pair[3:]

    # start/end are always required CLI args
    av_section["start_date"] = args.start
    av_section["end_date"]   = args.end

    try:
        cfg = AlphaVantageFetcherConfig.from_section(av_section)
        fetcher = AlphaVantageCandleFetcher(cfg)
    except (KeyError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        path = fetcher.fetch()
        print(f"  wrote -> {path}")
        return 0
    except Exception as exc:
        print(f"ERROR: fetch failed — {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
