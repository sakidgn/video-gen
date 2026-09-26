import base64
import re
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
  const srcOf = v => v.currentSrc || v.src || (v.querySelector('source') || {}).src || null;
  const inResp = Array.from(document.querySelectorAll('model-response video')).map(srcOf).filter(Boolean);
  if (inResp.length) return inResp[inResp.length - 1];
  const any = Array.from(document.querySelectorAll('video')).map(srcOf).filter(Boolean);
  return any.length ? any[any.length - 1] : null;
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

CLOSE_OVERLAY_JS = """(texts) => {
  const root = document.querySelector('.cdk-overlay-container');
  if (!root || !root.innerText.trim()) return 'bos';
  const backdrop = root.querySelector('.cdk-overlay-backdrop');
  if (backdrop) { backdrop.click(); return 'arka plan'; }
  const btn = Array.from(root.querySelectorAll('button, [role="button"], a'))
    .find(b => texts.includes((b.innerText || b.getAttribute('aria-label') || '').trim().toLowerCase()));
  if (btn) { btn.click(); return (btn.innerText || btn.getAttribute('aria-label')).trim(); }
  return null;
}"""

DISMISS_TEXTS = ["kapat", "close", "anladım", "got it", "hayır, teşekkürler", "no thanks", "şimdi değil",
                 "not now", "tamam", "ok", "reddet", "dismiss", "atla", "skip"]

SKIP_BUTTON = (
    "gönder", "send", "mikrofon", "microphone", "konuş", "speak", "durdur", "stop",
    "yeni sohbet", "new chat", "ana menü", "main menu", "hesap", "account", "ayarlar", "settings",
    "paylaş", "share", "sil", "delete", "çıkış", "sign out", "geçmiş", "history",
)
VIDEO_WORDS = ("video", "veo")
SELECTED_WORDS = ("kaldır", "remove", "deselect", "seçimi")
COPYRIGHT_PHRASES = ("third-party", "third party", "üçüncü taraf")

ASPECT_BUTTON_JS = """() => {
  const btns = Array.from(document.querySelectorAll('button')).filter(b => b.offsetParent !== null);
  const b = btns.find(b => /^(yatay|dikey|landscape|portrait|16:9|9:16)\\b/i.test((b.innerText || '').trim()));
  if (!b) return null;
  b.setAttribute('data-sp-aspect', '1');
  return (b.innerText || '').trim();
}"""

CLICK_PORTRAIT_JS = """() => {
  const root = document.querySelector('.cdk-overlay-container');
  if (!root) return null;
  const items = Array.from(root.querySelectorAll('[role="menuitem"], [role="menuitemradio"], [role="option"], button, li'));
  const hit = items.find(el => el.offsetParent !== null && /(dikey|portrait|9:16)/i.test(el.innerText || ''));
  if (!hit) return null;
  hit.click();
  return (hit.innerText || '').trim().slice(0, 40);
}"""


def _select_portrait(page, log, notes: list) -> None:
    current = page.evaluate(ASPECT_BUTTON_JS)
    if not current:
        notes.append("Format butonu bulunamadı")
        return
    if re.match(r"(dikey|portrait|9:16)", current, re.IGNORECASE):
        notes.append(f"Format zaten dikey: {current!r}")
        return
    try:
        page.locator('button[data-sp-aspect="1"]').click(timeout=3000)
    except Exception:
        page.evaluate("() => document.querySelector('button[data-sp-aspect=\"1\"]').click()")
    page.wait_for_timeout(800)
    picked = page.evaluate(CLICK_PORTRAIT_JS)
    notes.append(f"Format: {current!r} -> {picked!r} (menü: {page.evaluate(OVERLAY_TEXT_JS)!r})")
    if picked:
        log(f"Video formatı dikey yapıldı ({picked}).")
    else:
        log("UYARI: Dikey format seçilemedi, video yatay çıkabilir.")
    _clear_overlays(page, log, notes)


def _click_button(page, idx: int, notes: list) -> bool:
    sel = f'button[data-sp-idx="{idx}"]'
    try:
        page.locator(sel).click(timeout=3000)
        return True
    except Exception as e:
        notes.append(f"Tıklama engellendi ({sel}): {str(e).splitlines()[0][:150]}; JS ile deneniyor")
    try:
        return bool(page.evaluate("s => { const b = document.querySelector(s); if (b) b.click(); return !!b; }", sel))
    except Exception:
        return False


def _clear_overlays(page, log, notes: list) -> None:
    for _ in range(4):
        text = page.evaluate(OVERLAY_TEXT_JS)
        if not text:
            return
        notes.append(f"Açık pencere: {text!r}")
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        if not page.evaluate(OVERLAY_TEXT_JS):
            return
        how = page.evaluate(CLOSE_OVERLAY_JS, DISMISS_TEXTS)
        notes.append(f"Kapatma denemesi: {how}")
        page.wait_for_timeout(600)
    if page.evaluate(OVERLAY_TEXT_JS):
        log("UYARI: Gemini'de kapatılamayan bir pencere açık kaldı, yine de devam ediliyor.")


def _select_video_tool(page, log, diag_path: Path) -> bool:
    notes: list[str] = []
    try:
        ok = _select_video_tool_inner(page, log, notes)
        if ok:
            page.wait_for_timeout(1000)
            _select_portrait(page, log, notes)
        return ok
    finally:
        _clear_overlays(page, log, notes)
        diag_path.parent.mkdir(parents=True, exist_ok=True)
        diag_path.write_text("\n".join(notes), encoding="utf-8")


def _select_video_tool_inner(page, log, notes: list) -> bool:
    page.on("filechooser", lambda fc: None)  # yanlış butona basılırsa dosya penceresi açılmasın
    _clear_overlays(page, log, notes)
    buttons = page.evaluate(INPUT_BUTTONS_JS)
    notes.append("Yazı kutusu butonları:\n" + "\n".join(f"  {b['label']} (pressed={b['pressed']})" for b in buttons))

    for b in buttons:
        low = b["label"].lower()
        if any(w in low for w in VIDEO_WORDS):
            if b["pressed"] == "true" or any(w in low for w in SELECTED_WORDS):
                notes.append(f"SONUÇ: zaten seçili ({b['label']})")
                log("Video aracı zaten seçili.")
                return True
            _click_button(page, b["idx"], notes)
            notes.append(f"SONUÇ: doğrudan buton ({b['label']})")
            log(f"Video aracı seçildi: {b['label']}")
            return True

    for b in buttons:
        low = b["label"].lower()
        if any(w in low for w in SKIP_BUTTON):
            continue
        if not _click_button(page, b["idx"], notes):
            continue
        page.wait_for_timeout(1000)
        menu_text = page.evaluate(OVERLAY_TEXT_JS)
        picked = page.evaluate(CLICK_VIDEO_MENU_ITEM_JS)
        notes.append(f"[{b['label']}] menüsü: {menu_text!r}")
        if picked:
            page.wait_for_timeout(1000)
            notes.append(f"SONUÇ: '{b['label']}' -> '{picked}'")
            log(f"Video aracı seçildi: '{b['label']}' -> '{picked}'")
            return True
        _clear_overlays(page, log, notes)

    notes.append("SONUÇ: bulunamadı")
    log("UYARI: Video aracı bulunamadı. Detaylar: gemini_arayuz.txt")
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
        new_pages = []
        ctx.on("page", lambda pg: new_pages.append(pg))
        try:
            return _generate(page, prompt, out_path, timeout_s, log, new_pages)
        except Exception as e:
            stamp = time.strftime("%H%M%S")
            screenshot(new_pages[-1] if new_pages else page, out_path.parent / f"hata_gemini_{stamp}.png")
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


def _generate(page, prompt: str, out_path: Path, timeout_s: int, log, new_pages: list | None = None) -> Path:
    new_pages = new_pages if new_pages is not None else []
    folder = out_path.parent
    page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=90_000)
    page.wait_for_timeout(3000)
    if "accounts.google.com" in page.url:
        raise RuntimeError("Bu profilde Google oturumu açık değil. `python -m shitpost giris <profil>` ile giriş yap.")

    box = page.locator('div[role="textbox"]').first
    box.wait_for(state="visible", timeout=60_000)
    page.wait_for_timeout(1500)
    _select_video_tool(page, log, out_path.parent / "gemini_arayuz.txt")
    screenshot(page, folder / "adim_0_arac_secimi.png")
    box.focus()
    page.keyboard.insert_text(prompt)
    _wait_until_box_has(page, box, prompt)
    page.keyboard.press("Enter")
    page.wait_for_timeout(3000)
    if box.inner_text().strip():
        log("UYARI: Gönderdikten sonra yazı kutusunda metin kaldı, prompt yarım gitmiş olabilir.")
        box.focus()
        page.keyboard.press("Control+A")
        page.keyboard.press("Delete")
    log(f"Prompt gönderildi, Gemini videoyu üretiyor... (adres: {page.url})")
    screenshot(page, folder / "adim_1_gonderildi.png")

    start = time.time()
    responses = page.locator("model-response")
    src = None
    prev_text = None
    last_url = page.url
    seen_pages = 0
    next_report = 30
    while time.time() - start < timeout_s:
        page.wait_for_timeout(5000)
        elapsed = int(time.time() - start)
        if len(new_pages) > seen_pages:
            seen_pages = len(new_pages)
            page = new_pages[-1]
            responses = page.locator("model-response")
            log(f"Gemini yeni bir sekme açtı, oraya geçildi: {page.url}")
        if page.url != last_url:
            log(f"Gemini sayfası değişti: {last_url} -> {page.url}")
            last_url = page.url
        if elapsed >= next_report:
            snippet = (responses.last.inner_text() if responses.count() else "").strip().replace("\n", " ")
            log(f"  ...{elapsed} sn geçti. Gemini ekranda: {snippet[-150:]!r}")
            if next_report % 60 == 0:
                screenshot(page, folder / f"adim_bekleme_{elapsed:03d}sn.png")
            next_report += 30
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
            if any(ph in text for ph in COPYRIGHT_PHRASES):
                raise _with_reply(VideoFiltered(
                    "Gemini TELİF filtresine takıldı (karakter bilinen bir markaya benzetildi)"), raw)
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
