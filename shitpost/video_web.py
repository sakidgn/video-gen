import base64
import time
from pathlib import Path

from .browser import first_page, open_profile, screenshot
from .video import VideoFiltered

GEMINI_URL = "https://gemini.google.com/app"

QUOTA_PHRASES = [
    "daily limit", "reached your limit", "limit reached", "try again tomorrow", "come back tomorrow",
    "günlük limit", "günlük sınır", "limitine ulaştın", "sınırına ulaştın", "yarın tekrar",
]
REFUSAL_PHRASES = [
    "i can't", "i cannot", "i'm unable", "i am unable", "can't create", "can't generate", "can't help",
    "yapamıyorum", "oluşturamıyorum", "üretemiyorum", "yardımcı olamam",
]

FETCH_BLOB_JS = """async (src) => {
  const blob = await (await fetch(src)).blob();
  return await new Promise((resolve) => {
    const fr = new FileReader();
    fr.onload = () => resolve(fr.result.split(',')[1]);
    fr.readAsDataURL(blob);
  });
}"""

VIDEO_SRC_JS = """() => {
  const vids = document.querySelectorAll('model-response video');
  if (!vids.length) return null;
  const v = vids[vids.length - 1];
  return v.currentSrc || v.src || (v.querySelector('source') || {}).src || null;
}"""


class QuotaExceeded(RuntimeError):
    pass


def _with_reply(exc: Exception, reply: str) -> Exception:
    exc.reply = reply
    return exc


def generate_video_web(profile_dir: str, prompt: str, out_path: Path, *, timeout_s: int = 600, log=print) -> Path:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = open_profile(p, profile_dir)
        page = first_page(ctx)
        try:
            return _generate(page, prompt, out_path, timeout_s, log)
        except Exception as e:
            stamp = time.strftime("%H%M%S")
            screenshot(page, out_path.parent / f"hata_gemini_{stamp}.png")
            reply = getattr(e, "reply", None)
            if reply:
                (out_path.parent / f"gemini_cevabi_{stamp}.txt").write_text(reply, encoding="utf-8")
            raise
        finally:
            ctx.close()


def _generate(page, prompt: str, out_path: Path, timeout_s: int, log) -> Path:
    page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=90_000)
    page.wait_for_timeout(3000)
    if "accounts.google.com" in page.url:
        raise RuntimeError("Bu profilde Google oturumu açık değil. `python -m shitpost giris <profil>` ile giriş yap.")

    box = page.locator('div[role="textbox"]').first
    box.wait_for(state="visible", timeout=60_000)
    box.click()
    page.keyboard.insert_text(prompt)
    page.wait_for_timeout(1000)
    page.keyboard.press("Enter")
    log("Prompt gönderildi, Gemini videoyu üretiyor...")

    start = time.time()
    responses = page.locator("model-response")
    src = None
    prev_text = None
    while time.time() - start < timeout_s:
        page.wait_for_timeout(5000)
        src = page.evaluate(VIDEO_SRC_JS)
        if src:
            break
        raw = responses.last.inner_text() if responses.count() else ""
        text = raw.lower()
        settled = text == prev_text
        prev_text = text
        if not settled or time.time() - start < 20:
            continue
        if any(ph in text for ph in QUOTA_PHRASES):
            log(f"Gemini'nin cevabı:\n{raw.strip()}")
            raise _with_reply(QuotaExceeded(raw.strip()[:300]), raw)
        if any(ph in text for ph in REFUSAL_PHRASES):
            log(f"Gemini'nin cevabı:\n{raw.strip()}")
            raise _with_reply(VideoFiltered("Gemini bu senaryoyu reddetti"), raw)
    else:
        raise TimeoutError(f"Gemini {timeout_s} sn içinde video vermedi")

    page.wait_for_timeout(3000)
    if src.startswith("blob:"):
        data = base64.b64decode(page.evaluate(FETCH_BLOB_JS, src))
    else:
        resp = page.request.get(src, timeout=120_000)
        if not resp.ok:
            raise RuntimeError(f"Video indirilemedi: HTTP {resp.status}")
        data = resp.body()
    if len(data) < 50_000:
        raise RuntimeError(f"İndirilen dosya video gibi durmuyor ({len(data)} bayt)")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return out_path
