import time
from pathlib import Path

from .. import accounts
from ..browser import answer_dialogs, click_first, first_page, open_profile, screenshot, wait_until_idle
from ..config import Channel

UPLOAD_URL = "https://www.youtube.com/upload"

NOT_FOR_KIDS = [
    'tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]',
    'tp-yt-paper-radio-button[name="NOT_MADE_FOR_KIDS"]',
]
ALTERED_YES = [
    'tp-yt-paper-radio-button[name="VIDEO_HAS_ALTERED_CONTENT_YES"]',
    'tp-yt-paper-radio-button[name="ALTERED_CONTENT_YES"]',
]
PUBLIC = ['tp-yt-paper-radio-button[name="PUBLIC"]']

SHARE_LINK_JS = """() => {
  const a = Array.from(document.querySelectorAll('a[href]'))
    .find(a => /youtu\\.be\\/|youtube\\.com\\/shorts\\//.test(a.href));
  return a ? a.href : null;
}"""


def _fill(page, selector: str, text: str) -> None:
    box = page.locator(selector).first
    box.wait_for(state="visible", timeout=60_000)
    box.focus()
    page.keyboard.press("Control+A")
    page.keyboard.press("Delete")
    page.keyboard.insert_text(text)


def _wait_enabled(page, selector: str, timeout_s: int) -> None:
    btn = page.locator(selector).first
    btn.wait_for(state="visible", timeout=60_000)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if btn.get_attribute("aria-disabled") != "true" and btn.is_enabled():
            return
        page.wait_for_timeout(2000)
    raise TimeoutError(f"YouTube'da '{selector}' butonu aktif olmadı")


def publish(channel: Channel, video_path: Path, post) -> dict:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = open_profile(p, accounts.publish_profile())
        page = first_page(ctx)
        try:
            page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=90_000)
            page.wait_for_timeout(5000)
            if "accounts.google.com" in page.url:
                raise RuntimeError("YouTube oturumu açık değil. Menüden 1 ile YouTube'a giriş yap.")

            file_input = page.locator('input[type="file"]').first
            file_input.wait_for(state="attached", timeout=60_000)
            file_input.set_input_files(str(video_path))

            _fill(page, "#title-textarea #textbox", f"{post.title} #shorts"[:100])
            _fill(page, "#description-textarea #textbox", post.caption_with_tags())

            if not click_first(page, NOT_FOR_KIDS, timeout_ms=15_000):
                raise RuntimeError("'Çocuklara yönelik değil' seçeneği bulunamadı")
            if click_first(page, ["#toggle-button"], timeout_ms=3000):
                page.wait_for_timeout(1000)
                click_first(page, ALTERED_YES, timeout_ms=3000)

            for _ in range(3):
                _wait_enabled(page, "#next-button", 60)
                page.locator("#next-button").first.click()
                page.wait_for_timeout(1500)

            if not click_first(page, PUBLIC, timeout_ms=15_000):
                raise RuntimeError("'Herkese açık' seçeneği bulunamadı")
            answer_dialogs(page)
            screenshot(page, video_path.parent / "youtube_paylasim_oncesi.png")
            _wait_enabled(page, "#done-button", 600)
            page.locator("#done-button").first.click()
            page.wait_for_timeout(3000)
            answer_dialogs(page)
            wait_until_idle(page, ["yükleniyor", "yükleme", "uploading", "upload"], 900, "YouTube yükleme")

            link = None
            deadline = time.time() + 120
            while time.time() < deadline and not link:
                page.wait_for_timeout(2000)
                link = page.evaluate(SHARE_LINK_JS)
            return {"youtube": link or "yayınlandı"}
        except Exception:
            screenshot(page, video_path.parent / "hata_youtube.png")
            raise
        finally:
            ctx.close()
