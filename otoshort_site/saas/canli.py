"""Siteyi bu bilgisayardan herkese açık vitrin (demo) olarak yayınlar: python -m saas.canli  (Canliya_Al.bat)

Cloudflare'in ücretsiz "hızlı tüneli" ile https://....trycloudflare.com adresi alınır; hesap, alan adı, sunucu gerekmez.
Site vitrin modunda açılır: sahte videolar, ödeme ve yönetim kapalı, e-posta doğrulaması yok, arama motorlarına kapalı.
Pencere kapanınca yayın da kapanır; her açılışta adres değişir. Veriler saas_veri_vitrin/ klasöründe kalır."""
import os
import platform
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
URL_RE = re.compile(r"https://[a-z0-9]+(?:-[a-z0-9]+)+\.trycloudflare\.com")  # rastgele kelimeler (api. değil)
RELEASES = "https://github.com/cloudflare/cloudflared/releases/latest/download/"


def cloudflared_path() -> Path:
    if os.environ.get("CLOUDFLARED"):
        return Path(os.environ["CLOUDFLARED"])
    exe = "cloudflared.exe" if os.name == "nt" else "cloudflared"
    return ROOT / "araclar" / exe


def ensure_cloudflared() -> Path:
    path = cloudflared_path()
    if path.exists():
        return path
    machine = platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "amd64"
    asset = f"cloudflared-windows-{arch}.exe" if os.name == "nt" else f"cloudflared-linux-{arch}"
    print(f"Cloudflare tüneli indiriliyor ({asset}, ~20 MB, bir kereliğine)…")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".indiriliyor")
    urllib.request.urlretrieve(RELEASES + asset, tmp)
    tmp.replace(path)
    if os.name != "nt":
        path.chmod(0o755)
    return path


def secret_for(data_dir: Path) -> str:
    """Vitrinin kalıcı gizli anahtarı (oturumlar bununla imzalanır; varsayılan anahtar herkese açık olurdu)."""
    f = data_dir / "gizli_anahtar.txt"
    if f.exists() and len(f.read_text().strip()) >= 32:
        return f.read_text().strip()
    data_dir.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(48)
    f.write_text(key)
    return key


def start_tunnel(port: int, timeout: float = 60) -> tuple[subprocess.Popen, str]:
    """Tüneli başlatır ve herkese açık adresi döndürür."""
    exe = ensure_cloudflared()
    proc = subprocess.Popen([str(exe), "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    found: list[str] = []
    log: list[str] = []

    def read():  # çıktıyı sürekli oku (boru dolup tünel takılmasın), adresi yakala
        for line in proc.stdout:
            log.append(line.rstrip())
            if not found and (m := URL_RE.search(line)):
                found.append(m.group(0))

    threading.Thread(target=read, daemon=True).start()
    end = time.time() + timeout
    while time.time() < end and not found and proc.poll() is None:
        time.sleep(0.2)
    if not found:
        proc.terminate()
        tail = "\n".join(log[-8:])
        raise RuntimeError(f"Tünel adresi alınamadı. İnternet bağlantını kontrol et.\n{tail}")
    return proc, found[0]


def main() -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")  # varsa SMTP vb. (aşağıdaki vitrin ayarları her zaman önce gelir)
    except ImportError:
        pass
    import logging

    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    port = int(os.environ.get("VITRIN_PORT", "8010"))  # Siteyi_Ac (8000) ile çakışmasın
    data_dir = ROOT / "saas_veri_vitrin"
    os.environ.update({"VITRIN_MODU": "1", "SAHTE_AI": "1", "VERI_KLASORU": str(data_dir), "PORT": str(port),
                       "GIZLI_ANAHTAR": secret_for(data_dir)})
    os.environ.setdefault("KAYIT_HEDIYE_KREDI", "500")
    try:
        tunnel, url = start_tunnel(port)
    except Exception as e:
        print(f"\n✗ {e}")
        return 1
    os.environ["SITE_ADRESI"] = url
    line = "=" * 64
    print(f"\n{line}\n  SİTE YAYINDA:  {url}\n{line}")
    print("  Bu adresi arkadaşlarına gönderebilirsin (telefondan da açılır).")
    print("  Demo: videolar örnek animasyondur, ödeme ve yönetim paneli kapalıdır.")
    print("  Pencereyi kapatınca yayın biter; her açılışta adres değişir.\n")
    try:
        import webbrowser

        webbrowser.open(url)
    except Exception:
        pass
    try:
        import uvicorn

        from .app import create_app  # ortam değişkenleri ayarlandıktan sonra (config bunları okur)

        uvicorn.run(create_app(), host="127.0.0.1", port=port, proxy_headers=True, forwarded_allow_ips="127.0.0.1",
                    log_level="warning")
    finally:
        tunnel.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
