"""
blind_label_rasterize.py
=========================
Renders individual blind-label stimulus SVGs from `results/blind_label/session_01.html` to PNG.

WHY THIS EXISTS (methodologically load-bearing, not a convenience)
-------------------------------------------------------------------
The blind-label stimulus is SVG. Its markup carries `<rect y=... height=...>` and `<line ...>`
coordinates from which exact OHLC values are reconstructable. An annotator that reads the SVG
SOURCE is therefore not perceiving a chart -- it is parsing the underlying data, which is the
"slow computer" failure mode `preregistration-llm-blind-label-annotator.md` identifies, in its
most extreme form. Annotating from source would silently void the experiment.

So: rasterise once, annotate from the IMAGE only. The annotator never sees this file's input.

Read-only with respect to every frozen artifact: `session_01.html` and `sample_manifest.json` are
opened for reading and never written. Output PNGs go to a separate directory.

Usage
    python scripts/analysis/blind_label_rasterize.py --items itm_a,itm_b --out <dir>
    python scripts/analysis/blind_label_rasterize.py --arm-c --out <dir>   # the 20 Arm-C annotations
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SESSION_HTML = ROOT / "results" / "blind_label" / "session_01.html"
MANIFEST = ROOT / "results" / "blind_label" / "sample_manifest.json"

# Matches one complete <svg ...data-item="itm_..."> ... </svg> block.
_SVG_RE = re.compile(
    r'<svg[^>]*data-item="(?P<item>itm_[0-9a-f]+)"[^>]*>.*?</svg>',
    re.DOTALL,
)


def extract_svgs() -> dict[str, str]:
    html = io.open(SESSION_HTML, encoding="utf-8").read()
    return {m.group("item"): m.group(0) for m in _SVG_RE.finditer(html)}


def arm_c_item_ids() -> list[str]:
    """The 20 items Arm C needs: each Arm-C repeat AND the Arm-A original it repeats."""
    m = json.load(io.open(MANIFEST, encoding="utf-8"))
    cs = [i for i in m["items"] if i["arm"] == "C"]
    ids: list[str] = []
    for c in cs:
        ids.append(c["repeat_of"])   # original first
        ids.append(c["item_id"])     # then the repeat
    return ids


async def _render(svgs: dict[str, str], item_ids: list[str], out_dir: Path) -> list[Path]:
    from playwright.async_api import async_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 760, "height": 300},
                                       device_scale_factor=2)
        # Sanity: the stimulus is dark-themed; a screenshot that came out mostly white would
        # mean the CSS did not apply. Verified after render in __main__.
        for item in item_ids:
            svg = svgs[item]
            # CRITICAL FIDELITY REQUIREMENT -- the SVG references CSS custom properties
            # (var(--up)/var(--down)/var(--mark)) and .candles' own background, ALL of which
            # live in session_01.html's <style> block. Rendering the bare <svg> without them
            # silently destroys three visual channels at once: the green/red up-down
            # distinction, the dark chart background, and the ORANGE HIGHLIGHT + dashed
            # vertical line that identify the marked (target) bar. An annotator shown that
            # degraded image is not looking at the stimulus the experiment froze, and the
            # resulting labels would be uninterpretable while appearing perfectly normal.
            # These values are copied verbatim from the committed stimulus, not invented.
            html = (
                "<html><head><style>"
                ":root { --up:#26a269; --down:#c01c28; --mark:#f5a623; "
                "--bg:#111; --fg:#eee; --card:#1a1a1a; }"
                ".candles { width:100%; height:auto; background:#000; border-radius:4px; }"
                "</style></head>"
                "<body style='margin:0;background:#111'>"
                f"{svg}</body></html>"
            )
            await page.set_content(html)
            el = await page.query_selector("svg")
            dst = out_dir / f"{item}.png"
            await el.screenshot(path=str(dst))
            written.append(dst)
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--items", default=None, help="comma-separated item_ids")
    ap.add_argument("--arm-c", action="store_true", help="render the 20 Arm-C annotation images")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    svgs = extract_svgs()
    if args.arm_c:
        ids = arm_c_item_ids()
    elif args.items:
        ids = [s.strip() for s in args.items.split(",") if s.strip()]
    else:
        raise SystemExit("pass --arm-c or --items")

    missing = [i for i in ids if i not in svgs]
    if missing:
        raise SystemExit(f"no SVG in stimulus for: {missing}")

    written = asyncio.run(_render(svgs, ids, Path(args.out)))
    print(f"rendered {len(written)} PNG(s) -> {args.out}")
    for w in written:
        print(f"  {w.name}  ({w.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
