"""Probe Go-to-date, interval menu, and panel-close controls."""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "probe"
OUT.mkdir(parents=True, exist_ok=True)


def dump(page, tag: str) -> None:
    page.screenshot(path=str(OUT / f"{tag}.png"))
    info = page.evaluate(
        """() => {
        const els = [...document.querySelectorAll(
          'button, [role="button"], input, [role="dialog"], [data-name], [aria-label]'
        )].slice(0, 400).map(el => ({
          tag: el.tagName,
          id: el.id || '',
          name: el.getAttribute('data-name') || '',
          role: el.getAttribute('role') || '',
          aria: el.getAttribute('aria-label') || '',
          placeholder: el.getAttribute('placeholder') || '',
          type: el.getAttribute('type') || '',
          text: (el.innerText || '').trim().slice(0, 120),
        }));
        return { title: document.title, url: location.href, els };
        }"""
    )
    (OUT / f"{tag}.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"\n=== {tag} ===")
    for e in info["els"]:
        blob = " ".join(
            [e["id"], e["name"], e["aria"], e["placeholder"], e["text"], e["role"]]
        ).lower()
        if any(
            k in blob
            for k in (
                "go to",
                "goto",
                "date",
                "time",
                "range",
                "4h",
                "4 hour",
                "240",
                "15",
                "interval",
                "watchlist",
                "close",
                "custom",
                "from",
                "to",
                "july",
                "calendar",
            )
        ):
            print(
                f"  [{e['tag']} id={e['id']!r} name={e['name']!r} aria={e['aria']!r} "
                f"ph={e['placeholder']!r}] {e['text']!r}"
            )


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="UTC",
        ).new_page()
        page.set_default_timeout(25000)
        page.goto(
            "https://www.tradingview.com/chart/?symbol=OANDA:XAUUSD&interval=15",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        page.wait_for_timeout(7000)
        try:
            page.locator("#onetrust-accept-btn-handler").click(timeout=1500)
        except Exception:
            pass

        # Close cookie/login toasts if any
        for sel in [
            'button:has-text("Accept all")',
            'button[aria-label="Close"]',
            '[data-name="close"]',
        ]:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=600):
                    loc.click(timeout=600)
            except Exception:
                pass

        dump(page, "base")

        # Interval menu
        try:
            page.locator('button[aria-label="15 minutes"]').first.click(timeout=4000)
            page.wait_for_timeout(800)
            dump(page, "interval_menu")
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
        except Exception as exc:
            print("interval menu failed", exc)

        # Go to date via data-name
        try:
            page.locator('[data-name="go-to-date"]').first.click(timeout=4000)
            page.wait_for_timeout(1000)
            dump(page, "goto_click")
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
        except Exception as exc:
            print("goto click failed", exc)

        # Go to date via Alt+G
        try:
            page.keyboard.press("Alt+KeyG")
            page.wait_for_timeout(1000)
            dump(page, "goto_altg")
        except Exception as exc:
            print("altg failed", exc)

        # Date ranges menu
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            page.locator('[data-name="date-ranges-menu"]').first.click(timeout=4000)
            page.wait_for_timeout(800)
            dump(page, "date_ranges")
        except Exception as exc:
            print("date ranges failed", exc)

        browser.close()


if __name__ == "__main__":
    main()
