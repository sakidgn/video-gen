import time

from .browser import first_page, open_profile, screenshot

DEFAULT_URL = "https://chatgpt.com/"

LAST_ASSISTANT_JS = """() => {
  const msgs = document.querySelectorAll('div[data-message-author-role="assistant"]');
  return msgs.length ? msgs[msgs.length - 1].innerText.trim() : '';
}"""

ASSISTANT_COUNT_JS = """() => document.querySelectorAll('div[data-message-author-role="assistant"]').length"""

FIND_PROJECT_JS = r"""(name) => {
  const norm = t => (t || '').toLowerCase().replace(/[-_]+/g, ' ').replace(/\s+/g, ' ').trim();
  const want = norm(name);
  const slug = want.replace(/ /g, '-');
  const all = Array.from(document.querySelectorAll('a[href]'));
  const hrefOf = a => (a.getAttribute('href') || '').toLowerCase();
  const proj = all.filter(a => /\/g\/g-p-/.test(hrefOf(a)));
  const hit = proj.find(a => norm(a.innerText) === want)
    || proj.find(a => norm(a.innerText).includes(want))
    || proj.find(a => hrefOf(a).includes('-' + slug + '/'))
    || proj.find(a => hrefOf(a).includes(slug));
  const pp = all.find(a => /\/projects\/?(\?|$)/.test(hrefOf(a)))
    || all.find(a => /^(projeler|projects)$/i.test((a.innerText || '').trim()));
  return {
    href: hit ? hit.href : null,
    projectsPage: pp ? pp.href : null,
    names: proj.map(a => (a.innerText || '').trim().split('\n')[0] || hrefOf(a)).slice(0, 30),
  };
}"""

EXPAND_TEXTS = ["Daha fazla", "Daha fazlasını gör", "See more", "Show more", "Tümünü göster", "See all", "View all"]

GENERATING_JS = """() => !!document.querySelector(
  'button[data-testid="stop-button"], button[aria-label*="Stop" i], button[aria-label*="Durdur" i]')"""


def ask(profile_dir: str, message: str, *, url: str = DEFAULT_URL, project: str = "", timeout_s: int = 240,
        log=print, debug_dir=None) -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = open_profile(p, profile_dir)
        page = first_page(ctx)
        try:
            return _ask(page, message, url, timeout_s, log, project)
        except Exception:
            if debug_dir:
                screenshot(page, debug_dir / f"hata_chatgpt_{time.strftime('%H%M%S')}.png")
            raise
        finally:
            ctx.close()


def _find_project(page, name: str, wait_s: int) -> dict:
    deadline = time.time() + wait_s
    while True:
        found = page.evaluate(FIND_PROJECT_JS, name)
        if found["href"] or time.time() >= deadline:
            return found
        page.wait_for_timeout(1000)


def _open_project(page, name: str, log, fallback_url: str = "") -> None:
    found = _find_project(page, name, 6)
    for text in EXPAND_TEXTS:
        if found["href"]:
            break
        loc = page.get_by_text(text, exact=True)
        if loc.count():
            try:
                loc.first.click(timeout=3000)
            except Exception:
                continue
            found = _find_project(page, name, 2)
    if not found["href"] and found["projectsPage"]:
        log("ChatGPT Projeler sayfası açılıyor...")
        page.goto(found["projectsPage"], wait_until="domcontentloaded", timeout=90_000)
        found = {**_find_project(page, name, 12), "projectsPage": None}
    if found["href"]:
        log(f"ChatGPT projesi açılıyor: {name}")
        page.goto(found["href"], wait_until="domcontentloaded", timeout=90_000)
    elif "/g/g-p-" in fallback_url:
        log(f"'{name}' listede bulunamadı, kayıtlı proje linkine gidiliyor.")
        page.goto(fallback_url, wait_until="domcontentloaded", timeout=90_000)
    else:
        names = ", ".join(found["names"]) or "hiç proje görünmedi"
        raise RuntimeError(f"ChatGPT'de '{name}' adında proje bulunamadı. Görünen projeler: {names}")
    page.wait_for_timeout(3000)


def _ask(page, message: str, url: str, timeout_s: int, log, project: str = "") -> str:
    page.goto(DEFAULT_URL if project else url, wait_until="domcontentloaded", timeout=90_000)
    page.wait_for_timeout(4000)
    if "/auth/" in page.url or "login" in page.url:
        raise RuntimeError("ChatGPT oturumu açık değil. `python -m shitpost giris` ile ChatGPT'ye giriş yap.")
    if project:
        _open_project(page, project, log, fallback_url=url)

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
