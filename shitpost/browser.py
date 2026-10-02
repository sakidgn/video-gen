import os
import time
from pathlib import Path


def find_chrome() -> str | None:
    import shutil

    if os.environ.get("TARAYICI_YOLU"):
        return os.environ["TARAYICI_YOLU"]
    candidates = [
        os.path.join(os.environ.get(var, ""), "Google", "Chrome", "Application", "chrome.exe")
        for var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")
        if os.environ.get(var)
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return shutil.which("chrome") or shutil.which("google-chrome") or shutil.which("chromium")


def _window_args() -> list[str]:
    # Ekran dışı pencerede Gemini video üretimini yarıda kesip "yoğunum" diyordu; varsayılan görünür.
    if os.environ.get("TARAYICIYI_GIZLE", "").strip() in ("1", "evet", "true"):
        return ["--window-position=-32000,-32000"]
    return []


def _free_port() -> int:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class ProfileSession:
    """Normal başlatılmış bir Chrome'a CDP ile bağlı oturum; Playwright'ın kendi başlattığı
    Chrome'dan farkı, otomasyon parametreleri olmaması (Google buna farklı davranıyordu)."""

    def __init__(self, p, endpoint, browser, context, process):
        self._p = p
        self._endpoint = endpoint
        self._browser = browser
        self._context = context
        self._process = process

    def __getattr__(self, name):
        return getattr(self._context, name)

    @property
    def pid(self) -> int:
        return self._process.pid

    def detach(self) -> None:
        # Sadece CDP bağlantısını koparır; Chrome ve sekmeler açık kalır.
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
        self._browser = self._context = None

    def attach(self) -> None:
        if self._browser is None:
            self._browser = self._p.chromium.connect_over_cdp(self._endpoint)
            self._context = self._browser.contexts[0]

    def find_page(self, url_part: str):
        pages = self._context.pages
        matches = [pg for pg in pages if url_part in pg.url]
        return (matches or pages)[-1]

    def close(self):
        try:
            self.attach()
            for pg in list(self._context.pages):
                pg.close()
        except Exception:
            pass
        self.detach()
        try:
            self._process.terminate()
            self._process.wait(timeout=10)
        except Exception:
            self._process.kill()


def _open_real_chrome(p, profile_dir: str, url: str = "about:blank", connect: bool = True) -> ProfileSession:
    import subprocess
    import urllib.request

    chrome = find_chrome()
    if not chrome:
        raise RuntimeError("Chrome bulunamadı. https://www.google.com/chrome adresinden kur.")
    port = _free_port()
    args = [
        chrome,
        f"--user-data-dir={profile_dir}",
        f"--remote-debugging-port={port}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        *_window_args(),
        *os.environ.get("TARAYICI_EK_ARGS", "").split(),
        url,
    ]
    process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    endpoint = f"http://127.0.0.1:{port}"
    deadline = time.time() + 30
    while True:
        try:
            urllib.request.urlopen(endpoint + "/json/version", timeout=2).read()
            break
        except Exception:
            if process.poll() is not None or time.time() > deadline:
                process.kill()
                raise RuntimeError(
                    f"Chrome başlatılamadı. {profile_dir} profiliyle açık kalmış bir Chrome penceresi "
                    f"olabilir; Görev Yöneticisi'nden Chrome'u kapatıp tekrar dene."
                )
            time.sleep(0.5)
    session = ProfileSession(p, endpoint, None, None, process)
    if connect:
        session.attach()
    return session


def launch_unattached(p, profile_dir: str, url: str) -> ProfileSession:
    """Chrome'u verilen adresle açar ama bağlanmaz; sayfa hiçbir otomasyon bağlıyken yüklenir."""
    return _open_real_chrome(p, profile_dir, url=url, connect=False)


def _window_info(hwnd) -> dict:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    owner = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
    cls = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls, 256)
    title = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, title, 512)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    area = max(0, rect.right - rect.left) * max(0, rect.bottom - rect.top)
    return {"hwnd": hwnd, "pid": owner.value, "cls": cls.value, "title": title.value, "area": area}


def _is_bot_chrome(info: dict, pid: int) -> bool:
    return info["cls"] == "Chrome_WidgetWin_1" and bool(info["title"]) and (
        info["pid"] == pid or "gemini" in info["title"].lower()
    )


def _focus_window(pid: int) -> bool:
    """Botun Chrome penceresini öne getirir. Windows'un öne alma kilidini AttachThreadInput ile aşar."""
    import ctypes
    from ctypes import wintypes

    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _collect(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            info = _window_info(hwnd)
            if _is_bot_chrome(info, pid):
                found.append(info)
        return True

    user32.EnumWindows(_collect, 0)
    if not found:
        return False
    hwnd = max(found, key=lambda w: w["area"])["hwnd"]

    for _ in range(3):
        fg = user32.GetForegroundWindow()
        fg_thread = user32.GetWindowThreadProcessId(fg, None)
        me = kernel32.GetCurrentThreadId()
        attached = bool(fg_thread and fg_thread != me and user32.AttachThreadInput(me, fg_thread, True))
        user32.keybd_event(0x12, 0, 0, 0)  # ALT: öne alma izni için
        user32.keybd_event(0x12, 0, 0x0002, 0)
        user32.ShowWindow(hwnd, 9 if user32.IsIconic(hwnd) else 5)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        if attached:
            user32.AttachThreadInput(me, fg_thread, False)
        time.sleep(1.0)
        if _is_bot_chrome(_window_info(user32.GetForegroundWindow()), pid):
            return True
    try:
        user32.SwitchToThisWindow(hwnd, True)
        time.sleep(1.0)
        if _is_bot_chrome(_window_info(user32.GetForegroundWindow()), pid):
            return True
    except Exception:
        pass
    return _click_title_strip(hwnd, pid)


def _click_title_strip(hwnd, pid: int) -> bool:
    """Son çare: pencerenin üstteki boş sekme şeridine gerçek fare tıklaması (Windows her zaman öne alır)."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    old = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(old))
    x, y = rect.right - 280, rect.top + 14
    user32.SetCursorPos(x, y)
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # sol tuş bas
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # bırak
    time.sleep(0.8)
    user32.SetCursorPos(old.x, old.y)
    return _is_bot_chrome(_window_info(user32.GetForegroundWindow()), pid)


def foreground_title() -> str:
    if os.name != "nt":
        return ""
    import ctypes

    info = _window_info(ctypes.windll.user32.GetForegroundWindow())
    return f"{info['title'][:60]} ({info['cls']})"


def wake_display() -> None:
    """Zamanlayıcıyla uyanan Windows ekranı kapalı tutar; fareyi 1 piksel oynatıp ekranı açar."""
    if os.name != "nt":
        return
    import ctypes

    move = 0x0001
    ctypes.windll.user32.mouse_event(move, 1, 0, 0, 0)
    time.sleep(0.1)
    ctypes.windll.user32.mouse_event(move, -1, 0, 0, 0)
    time.sleep(2)


def _tap(*keys: int) -> None:
    import ctypes

    user32 = ctypes.windll.user32
    for k in keys:
        user32.keybd_event(k, 0, 0, 0)
    for k in reversed(keys):
        user32.keybd_event(k, 0, 0x0002, 0)
    time.sleep(0.2)


def _set_clipboard(text: str) -> None:
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(text)
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"Get-Content -Raw -Encoding UTF8 '{f.name}' | Set-Clipboard"],
        check=True, capture_output=True, timeout=30,
    )
    os.unlink(f.name)


def os_press_enter(pid: int) -> bool:
    """Chrome penceresini öne getirip Windows üzerinden gerçek bir Enter basar."""
    if os.name != "nt" or not _focus_window(pid):
        return False
    _tap(0x0D)
    return True


VK = {"Tab": 0x09, "Enter": 0x0D, "Shift": 0x10, "Control": 0x11, "ArrowDown": 0x28, "V": 0x56}


def key_steps_for(plan: dict | None) -> list[str]:
    """Hazırlıkta öğrenilen plana göre Dikey seçimi ve yazı kutusuna dönüş tuşları."""
    if not plan:
        return []
    return (["Tab"] * plan["tab"] + ["Enter"] + ["ArrowDown"] * plan["down"] + ["Enter"]
            + ["Shift+Tab"] * plan["back"])


def os_paste_and_enter(pid: int, text: str, pre_keys: list[str] | None = None) -> bool:
    """Chrome'u öne getirip gerçek klavyeyle önce pre_keys'i, sonra Ctrl+V ve Enter'ı basar."""
    if os.name != "nt":
        return False
    _set_clipboard(text)
    if not _focus_window(pid):
        return False
    for key in pre_keys or []:
        _tap(*[VK[k] for k in key.split("+")])
        time.sleep(0.9 if key == "Enter" else 0.25)
    _tap(VK["Control"], VK["V"])
    time.sleep(2.5)
    _tap(VK["Enter"])
    return True


def open_profile(p, profile_dir: str, headless: bool = False):
    if os.environ.get("TARAYICI_MODU", "normal") == "playwright":
        return p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            channel=os.environ.get("TARAYICI_KANALI", "chrome") or None,
            executable_path=os.environ.get("TARAYICI_YOLU") or None,
            headless=headless,
            accept_downloads=True,
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled", *_window_args()],
            ignore_default_args=["--enable-automation", "--no-sandbox"],
        )
    return _open_real_chrome(p, profile_dir)


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


AI_TOGGLE_JS = r"""(pattern) => {
  const re = new RegExp(pattern, 'i');
  const els = Array.from(document.querySelectorAll('span, div, label, p, h2, h3'))
    .filter(el => el.offsetParent !== null && re.test(el.textContent || '') && (el.textContent || '').length < 160);
  els.sort((a, b) => (a.textContent || '').length - (b.textContent || '').length);
  for (const label of els) {
    let node = label;
    for (let i = 0; i < 6 && node; i++, node = node.parentElement) {
      const sw = node.querySelector('[role="switch"], input[type="checkbox"]');
      if (sw) {
        const on = () => sw.getAttribute('aria-checked') === 'true' || sw.checked === true;
        if (on()) return 'zaten açık';
        (sw.closest('label') || sw).click();
        return on() ? 'açıldı' : 'tıklandı';
      }
    }
  }
  return null;
}"""


def turn_on_ai_label(page, pattern: str) -> str | None:
    """Metni pattern'e uyan etiketin yanındaki anahtarı açar; sonucu döndürür (None: bulunamadı)."""
    return page.evaluate(AI_TOGGLE_JS, pattern)


def click_text(page, pattern: str, timeout_ms: int = 3000) -> bool:
    import re

    loc = page.get_by_text(re.compile(pattern, re.IGNORECASE))
    deadline = time.time() + timeout_ms / 1000
    while True:
        for i in range(min(loc.count(), 5)):
            el = loc.nth(i)
            try:
                if el.is_visible():
                    el.click(timeout=3000)
                    return True
            except Exception:
                pass
        if time.time() >= deadline:
            return False
        page.wait_for_timeout(500)


def upload_busy(page, words: list[str]) -> bool:
    """Sayfada yükleme yüzdesi (<%100) ya da 'yükleniyor' gibi bir ifade varsa True."""
    import re

    text = page.evaluate("document.body.innerText")
    low = text.lower()
    for m in re.finditer(r"(\d{1,3})(?:[.,]\d+)?\s?%", text):
        around = low[max(0, m.start() - 80): m.end() + 80]
        if int(m.group(1)) < 100 and any(w in around for w in words):
            return True
    return False


def wait_until_idle(page, words: list[str], timeout_s: int, what: str) -> bool:
    """Yükleme göstergesi kaybolana kadar bekler (2 ardışık kontrol); süre dolarsa False."""
    deadline = time.time() + timeout_s
    calm = 0
    last_log = 0.0
    while time.time() < deadline:
        if upload_busy(page, words):
            calm = 0
            if time.time() - last_log > 30:
                print(f"  {what}: yükleme sürüyor, bekleniyor...")
                last_log = time.time()
        else:
            calm += 1
            if calm >= 2:
                return True
        page.wait_for_timeout(3000)
    print(f"UYARI: {what}: yükleme {timeout_s} sn içinde bitmedi.")
    return False
