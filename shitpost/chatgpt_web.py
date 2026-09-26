import time

from .browser import first_page, open_profile, screenshot

DEFAULT_URL = "https://chatgpt.com/"

LAST_ASSISTANT_JS = """() => {
  const msgs = document.querySelectorAll('div[data-message-author-role="assistant"]');
  return msgs.length ? msgs[msgs.length - 1].innerText.trim() : '';
}"""

ASSISTANT_COUNT_JS = """() => document.querySelectorAll('div[data-message-author-role="assistant"]').length"""

GENERATING_JS = """() => !!document.querySelector(
  'button[data-testid="stop-button"], button[aria-label*="Stop" i], button[aria-label*="Durdur" i]')"""


def ask(profile_dir: str, message: str, *, url: str = DEFAULT_URL, timeout_s: int = 240, log=print,
        debug_dir=None) -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = open_profile(p, profile_dir)
        page = first_page(ctx)
        try:
            return _ask(page, message, url, timeout_s, log)
        except Exception:
            if debug_dir:
                screenshot(page, debug_dir / f"hata_chatgpt_{time.strftime('%H%M%S')}.png")
            raise
        finally:
            ctx.close()


def _ask(page, message: str, url: str, timeout_s: int, log) -> str:
    page.goto(url, wait_until="domcontentloaded", timeout=90_000)
    page.wait_for_timeout(4000)
    if "/auth/" in page.url or "login" in page.url:
        raise RuntimeError("ChatGPT oturumu açık değil. `python -m shitpost giris` ile ChatGPT'ye giriş yap.")

    box = page.locator("#prompt-textarea").first
    box.wait_for(state="visible", timeout=60_000)
    before = page.evaluate(ASSISTANT_COUNT_JS)
    box.focus()
    page.keyboard.insert_text(message)
    page.wait_for_timeout(1500)
    page.keyboard.press("Enter")
    log("ChatGPT senaryoyu yazıyor...")

    start = time.time()
    prev, stable = "", 0
    while time.time() - start < timeout_s:
        page.wait_for_timeout(2000)
        if page.evaluate(ASSISTANT_COUNT_JS) <= before:
            continue
        text = page.evaluate(LAST_ASSISTANT_JS)
        generating = page.evaluate(GENERATING_JS)
        stable = stable + 1 if (text and text == prev and not generating) else 0
        prev = text
        if stable >= 2:
            return text
    raise TimeoutError(f"ChatGPT {timeout_s} sn içinde cevabı bitirmedi")
