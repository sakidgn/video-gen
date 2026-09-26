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


INPUT_BUTTONS_JS = """() => {
  let node = document.querySelector('div[role="textbox"]');
  for (let i = 0; i < 10 && node && node.querySelectorAll('button').length < 3; i++) node = node.parentElement;
  if (!node) return [];
  return Array.from(node.querySelectorAll('button')).filter(b => b.offsetParent !== null).map((b, i) => {
    b.setAttribute('data-sp-idx', String(i));
    return {idx: i, label: ((b.getAttribute('aria-label') || '') + ' | ' + (b.innerText || '')).trim(),
            pressed: b.getAttribute('aria-pressed') || ''};
  });
}"""

CLICK_VIDEO_MENU_ITEM_JS = """() => {
  const re = /(video|veo)/i;
  const root = document.querySelector('.cdk-overlay-container');
  if (!root) return null;
  const items = Array.from(root.querySelectorAll(
    '[role="menuitem"], [role="menuitemcheckbox"], [role="menuitemradio"], [role="option"], button, li'));
  const hit = items.find(el => el.offsetParent !== null &&
    re.test((el.innerText || '') + ' ' + (el.getAttribute('aria-label') || '')));
  if (!hit) return null;
  hit.click();
  return ((hit.innerText || hit.getAttribute('aria-label') || '').trim()).slice(0, 60);
}"""

OVERLAY_TEXT_JS = """() => {
  const root = document.querySelector('.cdk-overlay-container');
  return root ? root.innerText.trim().slice(0, 500) : '';
}"""

SKIP_BUTTON = ("gönder", "send", "mikrofon", "microphone", "konuş", "speak", "durdur", "stop")
VIDEO_WORDS = ("video", "veo")
SELECTED_WORDS = ("kaldır", "remove", "deselect", "seçimi")


def _select_video_tool(page, log, diag_path: Path) -> bool:
    page.on("filechooser", lambda fc: None)  # yanlış butona basılırsa dosya penceresi açılmasın
    buttons = page.evaluate(INPUT_BUTTONS_JS)

    for b in buttons:
        low = b["label"].lower()
        if any(w in low for w in VIDEO_WORDS):
            if b["pressed"] == "true" or any(w in low for w in SELECTED_WORDS):
                log("Video aracı zaten seçili.")
                return True
            page.locator(f'button[data-sp-idx="{b["idx"]}"]').click()
            log(f"Video aracı seçildi: {b['label']}")
            return True

    overlays = []
    for b in buttons:
        low = b["label"].lower()
        if any(w in low for w in SKIP_BUTTON):
            continue
        try:
            page.locator(f'button[data-sp-idx="{b["idx"]}"]').click(timeout=3000)
        except Exception:
            continue
        page.wait_for_timeout(1000)
        picked = page.evaluate(CLICK_VIDEO_MENU_ITEM_JS)
        if picked:
            page.wait_for_timeout(1000)
            log(f"Video aracı seçildi: '{b['label']}' -> '{picked}'")
            return True
        overlays.append(f"[{b['label']}] -> {page.evaluate(OVERLAY_TEXT_JS)!r}")
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)

    diag_path.parent.mkdir(parents=True, exist_ok=True)
    diag_path.write_text(
        "Yazı kutusu butonları:\n" + "\n".join(b["label"] for b in buttons)
        + "\n\nAçılan menüler:\n" + "\n".join(overlays),
        encoding="utf-8",
    )
    log(f"UYARI: Video aracı bulunamadı. Detaylar: {diag_path.name}")
    return False


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


def _norm_len(text: str) -> int:
    return len("".join(text.split()))


def _wait_until_box_has(page, box, prompt: str, timeout_s: int = 20) -> None:
    # Gemini'nin editörü uzun metni parça parça işliyor; tamamı yerleşmeden Enter'a basılırsa yarım gidiyor.
    expected = _norm_len(prompt)
    deadline = time.time() + timeout_s
    prev = -1
    while time.time() < deadline:
        page.wait_for_timeout(700)
        cur = _norm_len(box.inner_text())
        if cur >= expected * 0.98 and cur == prev:
            return
        prev = cur
    raise RuntimeError(f"Prompt yazı kutusuna tam yerleşmedi ({prev}/{expected} karakter)")


def _generate(page, prompt: str, out_path: Path, timeout_s: int, log) -> Path:
    page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=90_000)
    page.wait_for_timeout(3000)
    if "accounts.google.com" in page.url:
        raise RuntimeError("Bu profilde Google oturumu açık değil. `python -m shitpost giris <profil>` ile giriş yap.")

    box = page.locator('div[role="textbox"]').first
    box.wait_for(state="visible", timeout=60_000)
    page.wait_for_timeout(1500)
    _select_video_tool(page, log, out_path.parent / "gemini_arayuz.txt")
    box.click()
    page.keyboard.insert_text(prompt)
    _wait_until_box_has(page, box, prompt)
    page.keyboard.press("Enter")
    page.wait_for_timeout(3000)
    if box.inner_text().strip():
        log("UYARI: Gönderdikten sonra yazı kutusunda metin kaldı, prompt yarım gitmiş olabilir.")
        box.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Delete")
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
