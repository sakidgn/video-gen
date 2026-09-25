import time
from pathlib import Path

from .. import accounts
from ..browser import click_first, first_page, open_profile, screenshot, wait_for_text
from ..config import Channel

UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload"

AI_LABEL_JS = """() => {
  const re = /AI-generated|yapay zeka/i;
  const labels = Array.from(document.querySelectorAll('span, div, label, p'))
    .filter(el => re.test(el.textContent || '') && (el.textContent || '').length < 80);
  for (const label of labels) {
    let node = label;
    for (let i = 0; i < 5 && node; i++, node = node.parentElement) {
      const sw = node.querySelector('[role="switch"], input[type="checkbox"]');
      if (sw) {
        const on = sw.getAttribute('aria-checked') === 'true' || sw.checked === true;
        if (!on) sw.click();
        return true;
      }
    }
  }
  return false;
}"""


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

            caption = page.locator('div[contenteditable="true"]').first
            caption.wait_for(state="visible", timeout=90_000)
            caption.click()
            page.keyboard.press("Control+A")
            page.keyboard.press("Delete")
            page.keyboard.insert_text(post.caption_with_tags())
            page.wait_for_timeout(1500)
            page.mouse.click(5, 5)

            click_first(page, ['div:has-text("Daha fazla göster") >> nth=-1', 'div:has-text("Show more") >> nth=-1'])
            page.wait_for_timeout(1000)
            if page.evaluate(AI_LABEL_JS):
                click_first(page, ['button:text-is("Aç")', 'button:text-is("Turn on")'], timeout_ms=3000)

            _wait_post_enabled(page).click()
            click_first(page, ['button:has-text("Şimdi yayınla")', 'button:has-text("Post now")'], timeout_ms=5000)

            ok = wait_for_text(page, ["yayınlandı", "yüklendi", "been posted", "been uploaded", "published"], 90)
            if not ok and "/tiktokstudio/content" not in page.url:
                raise RuntimeError("TikTok paylaşımı onaylanmadı")
            return {"tiktok": "yayınlandı"}
        except Exception:
            screenshot(page, video_path.parent / "hata_tiktok.png")
            raise
        finally:
            ctx.close()
