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
    if os.environ.get("TARAYICIYI_GOSTER", "").strip() in ("1", "evet", "true"):
        return []
    return ["--window-position=-32000,-32000"]


def _free_port() -> int:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class ProfileSession:
    """Normal başlatılmış bir Chrome'a CDP ile bağlı oturum; Playwright'ın kendi başlattığı
    Chrome'dan farkı, otomasyon parametreleri olmaması (Google buna farklı davranıyordu)."""

    def __init__(self, browser, context, process):
        self._browser = browser
        self._context = context
        self._process = process

    def __getattr__(self, name):
        return getattr(self._context, name)

    def close(self):
        try:
            for pg in list(self._context.pages):
                pg.close()
        except Exception:
            pass
        try:
            self._browser.close()
        except Exception:
            pass
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
    return ProfileSession(browser, context, process)


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
