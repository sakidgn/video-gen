"""Siteyi GitHub'daki en son sürüme günceller: python -m saas.guncelle
Depo gizli (github.com/sakidgn/zaply-site): indirmek için .env'de GITHUB_TOKEN (yalnızca okuma izinli erişim anahtarı)
gerekir. Sadece site dosyaları yazılır; veriler (.env, saas_veri*) ve kurulum (.venv) korunur."""
import io
import json
import os
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

REPO = "sakidgn/zaply-site"
BRANCH = "main"
KEEP = (".env", "saas_veri", ".venv")
TOKEN_HELP = (
    "GitHub erişim anahtarı gerekiyor (depo gizli). Bir kereliğine:\n"
    "  1) github.com/settings/personal-access-tokens/new adresine git (sakidgn hesabı)\n"
    "  2) Ad: zaply-guncelle · Süre: 1 yıl · Repository access: Only select repositories → zaply-site\n"
    "  3) Permissions → Repository permissions → Contents: Read-only → Generate token\n"
    "  4) Çıkan anahtarı .env dosyasına GITHUB_TOKEN=... satırı olarak yapıştır, sonra tekrar Guncelle.bat")


def _prefix(names: list[str]) -> str:
    """Zip içinde site dosyalarının başladığı yer: eski depoda otoshort_site/, yeni depoda doğrudan kök."""
    return "otoshort_site/" if any(n.split("/", 1)[-1].startswith("otoshort_site/") for n in names) else ""


def extract_site(data: bytes, dest: Path, skip: tuple[str, ...] = ()) -> int:
    """Depo zip'indeki site dosyalarını dest klasörüne yazar; değişen dosya sayısını döndürür.
    Aynı kalan dosyalara dokunulmaz (tarayıcı önbelleği boşa bozulmasın); skip: o an çalışan .bat gibi atlanacaklar."""
    n = 0
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        prefix = _prefix(z.namelist())
        for info in z.infolist():
            parts = info.filename.split("/", 1)
            rel = parts[1] if len(parts) == 2 else ""
            if info.is_dir() or not rel.startswith(prefix):
                continue
            rel = rel[len(prefix):]
            if not rel or rel.startswith(KEEP) or "__pycache__" in rel or rel in skip:
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            data_ = z.read(info)
            if rel.endswith(".bat"):  # Windows komut dosyaları CRLF ister (LF'de etiketler/goto bozulur, pencere kapanır)
                data_ = data_.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            if target.exists() and target.read_bytes() == data_:
                continue
            target.write_bytes(data_)
            n += 1
    return n


def _token(dest: Path) -> str:
    """GITHUB_TOKEN: ortamdan ya da sitenin .env dosyasından."""
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"].strip()
    env = dest / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip().startswith("GITHUB_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def download(token: str) -> bytes:
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/zipball/{BRANCH}", headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "User-Agent": "zaply-guncelle"})
    with urllib.request.urlopen(req, timeout=180) as r:  # noqa: S310 (sabit GitHub API adresi)
        return r.read()


def main() -> int:
    dest = Path(__file__).resolve().parent.parent
    token = _token(dest)
    if not token:
        print(TOKEN_HELP)
        return 1
    print("En son sürüm indiriliyor...")
    try:
        data = download(token)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404):
            print("GitHub anahtarı geçersiz ya da süresi dolmuş (ya da zaply-site deposuna izni yok).\n" + TOKEN_HELP)
        else:
            print(f"İndirilemedi: {e}")
        return 1
    except Exception as e:
        print(f"İndirilemedi: {e}")
        return 1
    skip = tuple(sys.argv[sys.argv.index("--atla") + 1:]) if "--atla" in sys.argv else ()
    n = extract_site(data, dest, skip)
    print(f"Güncellendi ({n} dosya değişti)." if n else "Zaten en son sürüm.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
