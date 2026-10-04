"""One-off probe: dump TradingView controls so the capture script can target them."""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "probe"
OUT.mkdir(parents=True, exist_ok=True)

URLS = [
    ("shared", "https://in.tradingview.com/chart/Io3C5clp/"),
    ("public", "https://www.tradingview.com/chart/?symbol=OANDA:XAUUSD&interval=15"),
]


def dismiss_overlays(page) -> None:
    candidates = [
        "#onetrust-accept-btn-handler",
        'button:has-text("Accept all")',
        'button:has-text("Accept All")',
        'button:has-text("I agree")',
        'button:has-text("Got it")',
        'button:has-text("Maybe later")',
        'button:has-text("Not now")',
        '[data-name="close"]',
        'button[aria-label="Close"]',
        '[data-overflow-tooltip-text="Close"]',
    ]
    for sel in candidates:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=800):
                loc.click(timeout=800)
        except Exception:
            pass


def dump_page(page, tag: str) -> None:
    page.screenshot(path=str(OUT / f"{tag}.png"), full_page=True)
    (OUT / f"{tag}.html").write_text(page.content(), encoding="utf-8")
    info = page.evaluate(
        """() => {
        const buttons = [...document.querySelectorAll('button, [role="button"], a')]
          .slice(0, 250)
          .map(el => ({
            tag: el.tagName,
            id: el.id || '',
            name: el.getAttribute('data-name') || '',
            aria: el.getAttribute('aria-label') || '',
            title: el.getAttribute('title') || '',
            text: (el.innerText || '').trim().slice(0, 80),
            cls: (el.className || '').toString().slice(0, 80),
          }));
        const inputs = [...document.querySelectorAll('input')]
          .slice(0, 80)
          .map(el => ({
            id: el.id || '',
            name: el.name || '',
            type: el.type || '',
            placeholder: el.placeholder || '',
            aria: el.getAttribute('aria-label') || '',
          }));
        return {
          title: document.title,
          url: location.href,
          buttons,
          inputs,
        };
        }"""
    )
    import json

    (OUT / f"{tag}.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"=== {tag} ===")
    print("title:", info["title"])
    print("url:", info["url"])
    print("buttons:", len(info["buttons"]))
    interesting = [
        b
        for b in info["buttons"]
        if any(
            k in (b["text"] + b["aria"] + b["name"] + b["id"] + b["title"]).lower()
            for k in (
                "xau",
                "gold",
                "15",
                "4h",
                "240",
                "interval",
                "go to",
                "goto",
                "date",
                "indicator",
                "volume",
                "symbol",
                "accept",
                "login",
                "chart",
            )
        )
    ]
    for b in interesting[:60]:
        print(
            f"  [{b['id']}|{b['name']}|{b['aria']}|{b['title']}] {b['text']!r}"
        )


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="UTC",
        )
        page = context.new_page()
        page.set_default_timeout(20000)
        for tag, url in URLS:
            print(f"\nOpening {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(6000)
                dismiss_overlays(page)
                page.wait_for_timeout(2500)
                dump_page(page, tag)
            except Exception as exc:
                print(f"FAILED {tag}: {exc}")
                try:
                    page.screenshot(path=str(OUT / f"{tag}_fail.png"))
                except Exception:
                    pass
        browser.close()


if __name__ == "__main__":
    main()
