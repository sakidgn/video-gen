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


def _open_real_chrome(p, profile_dir: str) -> ProfileSession:
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
        "about:blank",
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
    browser = p.chromium.connect_over_cdp(endpoint)
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    return ProfileSession(p, endpoint, browser, context, process)


def os_press_enter(pid: int) -> bool:
    """Chrome penceresini öne getirip Windows üzerinden gerçek bir Enter basar."""
    if os.name != "nt":
        return False
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    hwnds = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _collect(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
            hwnds.append(hwnd)
        return True

    user32.EnumWindows(_collect, 0)
    if not hwnds:
        return False
    alt, enter, keyup = 0x12, 0x0D, 0x0002
    user32.keybd_event(alt, 0, 0, 0)  # Windows'un pencereyi öne almasına izin vermesi için
    user32.keybd_event(alt, 0, keyup, 0)
    user32.ShowWindow(hwnds[0], 9)
    user32.SetForegroundWindow(hwnds[0])
    time.sleep(1.0)
    if user32.GetForegroundWindow() != hwnds[0]:
        return False
    user32.keybd_event(enter, 0, 0, 0)
    user32.keybd_event(enter, 0, keyup, 0)
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
