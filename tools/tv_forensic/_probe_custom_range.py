"""Probe Custom range inputs and interval menu."""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "probe"


def dump_dialog(page, tag: str) -> None:
    page.screenshot(path=str(OUT / f"{tag}.png"))
    info = page.evaluate(
        """() => {
        const root = document.querySelector('[data-name="go-to-date-dialog"]') || document.body;
        const els = [...root.querySelectorAll('button, input, [role="tab"], [data-name], label, span')]
          .slice(0, 250)
          .map(el => ({
            tag: el.tagName,
            id: el.id || '',
            name: el.getAttribute('data-name') || '',
            aria: el.getAttribute('aria-label') || '',
            ph: el.getAttribute('placeholder') || '',
            type: el.getAttribute('type') || '',
            value: el.value || '',
            text: (el.innerText || '').trim().slice(0, 80),
          }));
        const html = root.innerHTML.slice(0, 15000);
        return { els, html };
        }"""
    )
    (OUT / f"{tag}.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"\n=== {tag} ===")
    for e in info["els"]:
        if e["tag"] in {"INPUT", "BUTTON"} or e["name"] or e["ph"] or e["aria"]:
            print(
                f"  {e['tag']} id={e['id']!r} name={e['name']!r} aria={e['aria']!r} "
                f"ph={e['ph']!r} val={e['value']!r} text={e['text']!r}"
            )


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="UTC",
        ).new_page()
        page.goto(
            "https://www.tradingview.com/chart/?symbol=OANDA:XAUUSD&interval=15",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        page.wait_for_timeout(7000)

        # Hide watchlist
        try:
            page.locator('[data-name="base"]').first.click(timeout=3000)
            page.wait_for_timeout(800)
            page.screenshot(path=str(OUT / "watchlist_toggled.png"))
            print("toggled watchlist")
        except Exception as exc:
            print("watchlist toggle failed", exc)

        # Interval via header 15m button that has visible text
        try:
            page.locator('#header-toolbar-intervals, button[aria-label="15 minutes"]').last.click(
                timeout=4000
            )
            page.wait_for_timeout(800)
            page.screenshot(path=str(OUT / "interval_open.png"))
            items = page.evaluate(
                """() => [...document.querySelectorAll('[role="menuitem"], [role="option"], button')]
                .map(el => ({
                  aria: el.getAttribute('aria-label') || '',
                  name: el.getAttribute('data-name') || '',
                  text: (el.innerText || '').trim().slice(0, 60),
                }))
                .filter(x => /hour|minute|4H|240|15|interval|day/i.test(x.aria + x.text + x.name))
                """
            )
            (OUT / "interval_items.json").write_text(json.dumps(items, indent=2), encoding="utf-8")
            print("interval items", items[:40])
            page.keyboard.press("Escape")
        except Exception as exc:
            print("interval failed", exc)

        # Custom range
        page.locator('[data-name="go-to-date"]').first.click(timeout=5000)
        page.wait_for_timeout(800)
        dump_dialog(page, "goto_date_tab")
        page.locator("#CustomRange").click(timeout=4000)
        page.wait_for_timeout(800)
        dump_dialog(page, "goto_custom_tab")

        browser.close()


if __name__ == "__main__":
    main()
