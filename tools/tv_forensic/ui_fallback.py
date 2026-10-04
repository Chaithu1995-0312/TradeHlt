"""The original DOM-driven framing path, kept as a fallback behind --via-ui.

capture_tv.py now frames through the widget API (tv_bridge), which is exact and
readable-back. This module preserves the Go-to-date dialog route that produced the
first working shots, in case a future TradingView build stops exposing
window.TradingViewApi. It is not on the default path.
"""
from __future__ import annotations

import re
from datetime import datetime

from playwright.sync_api import Page

INTERVAL_MENU_LABEL = {
    "1": "1 minute",
    "5": "5 minutes",
    "15": "15 minutes",
    "30": "30 minutes",
    "60": "1 hour",
    "120": "2 hours",
    "180": "3 hours",
    "240": "4 hours",
    "D": "1 day",
    "W": "1 week",
}

HEADER_INTERVAL_ALIASES = {
    "1": ("1 minute", "1m"),
    "5": ("5 minutes", "5m"),
    "15": ("15 minutes", "15m"),
    "30": ("30 minutes", "30m"),
    "60": ("1 hour", "1h"),
    "120": ("2 hours", "2h"),
    "180": ("3 hours", "3h"),
    "240": ("4 hours", "4h"),
    "D": ("1 day", "1D"),
    "W": ("1 week", "1W"),
}


def parse_dt(text: str) -> tuple[str, str]:
    text = text.strip().replace("T", " ")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text, "00:00"
    dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")


def dismiss_overlays(page: Page) -> None:
    selectors = [
        "#onetrust-accept-btn-handler",
        'button:has-text("Accept all")',
        'button:has-text("Accept All")',
        'button:has-text("I agree")',
        'button:has-text("Got it")',
        'button:has-text("Maybe later")',
        'button:has-text("Not now")',
        'button:has-text("No thanks")',
        '[data-name="close"]',
        'button[aria-label="Close"]',
        'button[aria-label="Close all"]',
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=400):
                loc.click(timeout=800)
                page.wait_for_timeout(200)
        except Exception:
            pass


def hide_watchlist(page: Page) -> None:
    wrap = page.locator('[data-name="widgetbar-wrap"]')
    try:
        if wrap.count() and wrap.first.is_visible(timeout=1500):
            page.locator('[data-name="base"]').first.click(timeout=2000)
            page.wait_for_timeout(500)
    except Exception:
        pass


def wait_for_chart(page: Page, timeout_ms: int = 30000) -> None:
    page.wait_for_selector('canvas[aria-label*="Chart for"]', timeout=timeout_ms)
    page.wait_for_timeout(1500)


def dismiss_time_listbox(page: Page) -> None:
    try:
        option = page.locator('[role="option"][aria-selected="true"]').first
        if option.count() and option.is_visible(timeout=200):
            option.click(timeout=500)
            return
    except Exception:
        pass
    try:
        page.locator('[data-name="go-to-date-dialog"]').locator("text=Go to").first.click(
            timeout=500
        )
    except Exception:
        pass


def fill_react_input(locator, value: str) -> None:
    page = locator.page
    locator.click(timeout=4000, force=True)
    locator.fill("")
    locator.fill(value)
    try:
        current = locator.input_value(timeout=1000)
        if current != value:
            raise ValueError(current)
    except Exception:
        locator.click(force=True)
        locator.press("Control+A")
        locator.press("Backspace")
        locator.type(value, delay=30)
    option = page.locator(f"#desktop_time_input_item_{value}")
    try:
        if option.count() and option.first.is_visible(timeout=400):
            option.first.click(timeout=800)
            page.wait_for_timeout(150)
            return
    except Exception:
        pass
    dismiss_time_listbox(page)


def set_symbol(page: Page, symbol: str) -> None:
    btn = page.locator("#header-toolbar-symbol-search")
    current = (btn.inner_text(timeout=4000) or "").strip().upper()
    wanted = symbol.split(":")[-1].upper()
    if current == wanted:
        return
    btn.click()
    page.wait_for_timeout(400)
    search = page.locator('input[placeholder*="Search"], input[data-role="search"]')
    if search.count():
        fill_react_input(search.first, symbol)
    else:
        page.keyboard.type(symbol, delay=40)
    page.wait_for_timeout(600)
    page.keyboard.press("Enter")
    page.wait_for_timeout(1500)
    wait_for_chart(page)


def current_interval_label(page: Page) -> str:
    for code, (aria, _text) in HEADER_INTERVAL_ALIASES.items():
        loc = page.locator(f'button[aria-label="{aria}"]')
        try:
            if loc.count() and loc.last.is_visible(timeout=300):
                return code
        except Exception:
            continue
    change = page.locator('button[aria-label="Change interval"]')
    try:
        if change.count():
            raw = (change.first.inner_text(timeout=800) or "").strip()
            mapping = {
                "15": "15", "5": "5", "1": "1", "30": "30",
                "1h": "60", "2h": "120", "4h": "240", "D": "D", "W": "W",
            }
            return mapping.get(raw, raw)
    except Exception:
        pass
    return ""


def set_interval(page: Page, interval: str) -> None:
    interval = str(interval)
    if current_interval_label(page) == interval:
        return
    opened = False
    for _code, (aria, _text) in HEADER_INTERVAL_ALIASES.items():
        loc = page.locator(f'button[aria-label="{aria}"]')
        try:
            if loc.count() and loc.last.is_visible(timeout=400):
                loc.last.click(timeout=3000)
                opened = True
                break
        except Exception:
            continue
    if not opened:
        page.locator('button[aria-label="Change interval"]').first.click(timeout=4000)
    page.wait_for_timeout(400)
    page.get_by_text(INTERVAL_MENU_LABEL[interval], exact=True).first.click(timeout=4000)
    page.wait_for_timeout(1500)
    wait_for_chart(page)


def set_custom_range(page: Page, start: str, end: str) -> None:
    """Frame a window through Go to -> Custom range. Times must already be UTC."""
    start_date, start_time = parse_dt(start)
    end_date, end_time = parse_dt(end)
    page.locator('[data-name="go-to-date"]').first.click(timeout=5000)
    page.wait_for_selector('[data-name="go-to-date-dialog"]', timeout=8000)
    dialog = page.locator('[data-name="go-to-date-dialog"]')
    dialog.locator("#CustomRange").click(timeout=4000)
    page.wait_for_timeout(300)

    fill_react_input(dialog.locator('input[name="start-date-range"]'), start_date)
    fill_react_input(dialog.locator('input[name="end-date-range"]'), end_date)

    all_inputs = dialog.locator("input")
    times = []
    for i in range(all_inputs.count()):
        el = all_inputs.nth(i)
        if (el.get_attribute("name") or "") in {"start-date-range", "end-date-range"}:
            continue
        times.append(el)
    if len(times) < 2:
        raise RuntimeError("Could not find Custom range time inputs")
    fill_react_input(times[0], start_time)
    fill_react_input(times[1], end_time)

    dialog.locator('[data-name="submit-button"]').click(timeout=4000)
    page.wait_for_timeout(3500)
    wait_for_chart(page)
    try:
        page.locator('[data-name="go-to-date-dialog"]').wait_for(state="hidden", timeout=4000)
    except Exception:
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
    page.wait_for_timeout(1500)
