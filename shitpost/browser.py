import os
import time
from pathlib import Path


def open_profile(p, profile_dir: str, headless: bool = False):
    channel = os.environ.get("TARAYICI_KANALI", "chrome") or None
    return p.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        channel=channel,
        headless=headless,
        accept_downloads=True,
        viewport={"width": 1280, "height": 900},
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )


def first_page(ctx):
    return ctx.pages[0] if ctx.pages else ctx.new_page()


def screenshot(page, path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(path), full_page=True)
    except Exception:
        pass


def click_first(page, selectors: list[str], timeout_ms: int = 0) -> bool:
    deadline = time.time() + timeout_ms / 1000
    while True:
        for sel in selectors:
            loc = page.locator(sel)
            if loc.count() and loc.first.is_visible():
                loc.first.click()
                return True
        if time.time() >= deadline:
            return False
        page.wait_for_timeout(500)


def wait_for_text(page, needles: list[str], timeout_s: int) -> str | None:
    needles = [n.lower() for n in needles]
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        body = page.evaluate("document.body.innerText").lower()
        for n in needles:
            if n in body:
                return n
        page.wait_for_timeout(2000)
    return None
