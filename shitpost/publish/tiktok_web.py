import time
from pathlib import Path

from .. import accounts
from ..browser import (
    answer_dialogs, click_first, click_text, first_page, open_profile, screenshot, turn_on_ai_label, wait_for_text,
    wait_until_idle,
)
from ..config import Channel

UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload"

AI_PATTERN = r"AI[- ]generated|AI ile oluşturul|yapay zek[aâ]"
BUSY_WORDS = ["yükleniyor", "uploading", "gönderiliyor", "posting", "işleniyor", "processing", "yükleme", "upload"]
DONE_TEXTS = ["yayınlandı", "gönderildi", "been posted", "published", "paylaşıldı"]


def _wait_post_enabled(page, timeout_s: int = 240):
    btn = page.locator('button[data-e2e="post_video_button"], button:has-text("Yayınla"), button:has-text("Post")').first
    btn.wait_for(state="visible", timeout=60_000)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if btn.is_enabled() and btn.get_attribute("aria-disabled") != "true" and btn.get_attribute("data-disabled") != "true":
            return btn
        page.wait_for_timeout(2000)
    raise TimeoutError("TikTok yükleme bitmedi (Yayınla butonu aktif olmadı)")


def publish(channel: Channel, video_path: Path, post) -> dict:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = open_profile(p, accounts.publish_profile())
        page = first_page(ctx)
        try:
            page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=90_000)
            if "login" in page.url:
                raise RuntimeError("TikTok oturumu açık değil. `python -m shitpost giris` ile giriş yap.")
            file_input = page.locator('input[type="file"]').first
            file_input.wait_for(state="attached", timeout=60_000)
            file_input.set_input_files(str(video_path))
            page.wait_for_timeout(5000)
            wait_until_idle(page, BUSY_WORDS, 600, "TikTok video yükleme")

            caption = page.locator('div[contenteditable="true"]').first
            caption.wait_for(state="visible", timeout=90_000)
            caption.click()
            page.keyboard.press("Control+A")
            page.keyboard.press("Delete")
            page.keyboard.insert_text(post.caption_with_tags())
            page.wait_for_timeout(1500)
            page.mouse.click(5, 5)

            click_text(page, r"^(daha fazla göster|daha fazla|show more|more options)$")
            page.wait_for_timeout(1000)
            ai = turn_on_ai_label(page, AI_PATTERN)
            if ai and ai != "zaten açık":
                click_first(page, ['button:text-is("Aç")', 'button:text-is("Turn on")', 'button:text-is("Açık")'],
                            timeout_ms=4000)
            print(f"TikTok AI etiketi: {ai or 'BULUNAMADI'}")
            answer_dialogs(page)
            screenshot(page, video_path.parent / "tiktok_paylasim_oncesi.png")

            _wait_post_enabled(page).click()
            click_first(page, ['button:has-text("Şimdi yayınla")', 'button:has-text("Post now")'], timeout_ms=5000)

            ok = wait_for_text(page, DONE_TEXTS, 300)
            if not ok and "/tiktokstudio/content" not in page.url:
                raise RuntimeError("TikTok paylaşımı onaylanmadı")
            wait_until_idle(page, BUSY_WORDS, 600, "TikTok paylaşım")
            page.wait_for_timeout(10_000)
            return {"tiktok": "yayınlandı"}
        except Exception:
            screenshot(page, video_path.parent / "hata_tiktok.png")
            raise
        finally:
            ctx.close()
