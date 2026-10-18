"""Siteyi GitHub'daki en son sürüme günceller: python -m saas.guncelle
Sadece site dosyaları (otoshort_site/ klasörü) yazılır; veriler (.env, saas_veri*) korunur."""
import io
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

UPDATE_URL = "https://github.com/sakidgn/video-gen/archive/refs/heads/claude/oto-reels-uretici-gemini-sucu7b.zip"
PREFIX = "otoshort_site/"
KEEP = (".env", "saas_veri", ".venv")


def extract_site(data: bytes, dest: Path) -> int:
    """Depo zip'inden otoshort_site/ altındaki dosyaları dest klasörüne yazar; yazılan dosya sayısını döndürür."""
    n = 0
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist():
            parts = info.filename.split("/", 1)
            rel = parts[1] if len(parts) == 2 else ""
            if info.is_dir() or not rel.startswith(PREFIX):
                continue
            rel = rel[len(PREFIX):]
            if not rel or rel.startswith(KEEP) or "__pycache__" in rel:
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            data_ = z.read(info)
            if rel.endswith(".bat"):  # Windows komut dosyaları CRLF ister (LF'de etiketler/goto bozulur, pencere kapanır)
                data_ = data_.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            target.write_bytes(data_)
            n += 1
    return n


def download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as r:  # noqa: S310 (sabit GitHub adresi)
        return r.read()


def main() -> int:
    dest = Path(__file__).resolve().parent.parent
    print("En son sürüm indiriliyor...")
    try:
        data = download(os.environ.get("GUNCELLEME_URL", UPDATE_URL))
    except Exception as e:
        print(f"İndirilemedi: {e}")
        return 1
    print(f"Güncellendi ({extract_site(data, dest)} dosya).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
