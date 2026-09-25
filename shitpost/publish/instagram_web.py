from pathlib import Path

from .. import accounts
from ..browser import click_first, first_page, open_profile, screenshot, wait_for_text
from ..config import Channel


def _dialog_button(texts: list[str]) -> list[str]:
    return [f'div[role="dialog"] div[role="button"]:text-is("{t}")' for t in texts] + [
        f'div[role="dialog"] button:text-is("{t}")' for t in texts
    ]


def publish(channel: Channel, video_path: Path, post) -> dict:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = open_profile(p, accounts.publish_profile())
        page = first_page(ctx)
        try:
            page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=90_000)
            page.wait_for_timeout(4000)
            if "accounts/login" in page.url:
                raise RuntimeError("Instagram oturumu açık değil. `python -m shitpost giris` ile giriş yap.")

            if not click_first(page, [
                'svg[aria-label="Yeni gönderi"]', 'svg[aria-label="New post"]',
                'a:has(span:text-is("Oluştur"))', 'a:has(span:text-is("Create"))',
            ], timeout_ms=20_000):
                raise RuntimeError("Instagram 'Oluştur' butonu bulunamadı")
            page.wait_for_timeout(1500)
            click_first(page, ['a:has(span:text-is("Gönderi"))', 'a:has(span:text-is("Post"))'])

            file_input = page.locator('input[type="file"]').first
            file_input.wait_for(state="attached", timeout=30_000)
            file_input.set_input_files(str(video_path))
            page.wait_for_timeout(5000)

            click_first(page, _dialog_button(["Tamam", "OK"]), timeout_ms=3000)

            if click_first(page, ['svg[aria-label="Kırpmayı seç"]', 'svg[aria-label="Select crop"]'], timeout_ms=5000):
                page.wait_for_timeout(800)
                click_first(page, ['span:text-is("Orijinal")', 'span:text-is("Original")'])
                page.wait_for_timeout(800)

            for _ in range(2):
                if not click_first(page, _dialog_button(["İleri", "Next"]), timeout_ms=15_000):
                    raise RuntimeError("Instagram 'İleri' butonu bulunamadı")
                page.wait_for_timeout(2500)

            caption = page.locator(
                'div[aria-label*="açıklama" i][contenteditable="true"], div[aria-label*="caption" i][contenteditable="true"]'
            ).first
            caption.wait_for(state="visible", timeout=20_000)
            caption.click()
            page.keyboard.insert_text(post.caption_with_tags())
            page.wait_for_timeout(1000)

            if not click_first(page, _dialog_button(["Paylaş", "Share"]), timeout_ms=10_000):
                raise RuntimeError("Instagram 'Paylaş' butonu bulunamadı")

            if not wait_for_text(page, ["paylaşıldı", "has been shared", "reel shared", "post shared"], 240):
                raise RuntimeError("Instagram paylaşımı onaylanmadı")
            return {"instagram": "yayınlandı"}
        except Exception:
            screenshot(page, video_path.parent / "hata_instagram.png")
            raise
        finally:
            ctx.close()
