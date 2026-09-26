import argparse
import sys
from pathlib import Path

from .config import list_channels, load_channel


def _client():
    from google import genai

    return genai.Client()


class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for st in self.streams:
            st.write(data)
            st.flush()

    def flush(self):
        for st in self.streams:
            st.flush()


def cmd_uret(args) -> int:
    from . import pipeline
    from .config import OUTPUT_DIR

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log_file = (OUTPUT_DIR / "son_calisma.txt").open("w", encoding="utf-8")
    sys.stdout = _Tee(sys.__stdout__, log_file)
    sys.stderr = _Tee(sys.__stderr__, log_file)
    try:
        return _uret(args, pipeline)
    except Exception:
        import traceback

        traceback.print_exc()
        return 1
    finally:
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__
        log_file.close()


def _uret(args, pipeline) -> int:
    import traceback

    channel = load_channel(args.kanal)
    client = _client()
    failed = 0
    for i in range(args.adet):
        if args.adet > 1:
            print(f"\n=== Video {i + 1}/{args.adet} ===")
        try:
            result = pipeline.run(client, channel, publish=not args.kuru)
        except pipeline.NoQuotaLeft as e:
            print(f"Durduruldu: {e}")
            break
        except Exception as e:
            print(f"HATA: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            failed += 1
            continue
        if result.errors:
            failed += 1
    return 1 if failed else 0


def cmd_karakter(args) -> int:
    from . import images

    channel = load_channel(args.kanal)
    created = images.ensure_references(_client(), channel, force=args.yenile)
    for c in created:
        print(f"Üretildi: {c.reference}")
    if not created:
        print("Tüm referanslar zaten var (yeniden üretmek için --yenile).")
    return 0


def cmd_youtube_yetki(args) -> int:
    from .publish import youtube

    out = youtube.authorize(load_channel(args.kanal), Path(args.client_secret))
    print(f"Token kaydedildi: {out}\nGitHub Actions için bu dosyanın içeriğini secret olarak ekle.")
    return 0


def cmd_giris(args) -> int:
    import subprocess

    from .browser import find_chrome

    urls = ["https://gemini.google.com/app"]
    if not args.sadece_gemini:
        urls += ["https://www.tiktok.com/login", "https://www.instagram.com/accounts/login/"]

    chrome = find_chrome()
    if not chrome:
        print("Chrome bulunamadı. https://www.google.com/chrome adresinden kur ve tekrar dene.")
        return 1
    # Otomasyonsuz normal Chrome: Instagram/Google robot doğrulaması ancak böyle düzgün açılıyor.
    subprocess.Popen([chrome, f"--user-data-dir={args.profil}", "--no-first-run", *urls])
    input(
        f"Profil: {args.profil}\n"
        "Açılan Chrome'da giriş yap. Bitince Chrome'u TAMAMEN KAPAT (sağ üstteki X),\n"
        "sonra buraya dönüp ENTER'a bas..."
    )
    print("Oturumlar kaydedildi.")
    return 0


UPDATE_URL = "https://github.com/sakidgn/video-gen/archive/refs/heads/claude/oto-reels-uretici-gemini-sucu7b.zip"


def cmd_guncelle(args) -> int:
    import io
    import os
    import zipfile

    import requests

    from .config import ROOT

    url = os.environ.get("GUNCELLEME_URL", UPDATE_URL)
    print("En son sürüm indiriliyor...")
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    updated = 0
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        for info in z.infolist():
            rel = info.filename.split("/", 1)[1] if "/" in info.filename else ""
            if not rel or info.is_dir() or rel.endswith("gecmis.json"):
                continue
            target = ROOT / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(info))
            updated += 1
    print(f"Güncellendi ({updated} dosya).")
    return 0


def cmd_rapor(args) -> int:
    import os

    from .config import OUTPUT_DIR

    log = OUTPUT_DIR / "son_calisma.txt"
    runs = sorted((p for p in OUTPUT_DIR.glob("*/*") if p.is_dir()), key=lambda p: p.stat().st_mtime)
    if not log.exists() and not runs:
        print("Henüz rapor yok. Önce 4 ile bir deneme yap.")
        return 1
    opener = getattr(os, "startfile", None)
    for target in [log if log.exists() else None, runs[-1] if runs else None]:
        if target is None:
            continue
        print(f"Açılıyor: {target}")
        if opener:
            opener(str(target))
    return 0


def cmd_kanallar(args) -> int:
    for slug in list_channels():
        print(slug)
    return 0


def main(argv=None) -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    p = argparse.ArgumentParser(prog="shitpost", description="Oto shitpost video üretici")
    sub = p.add_subparsers(dest="komut", required=True)

    u = sub.add_parser("uret", help="Video üret ve paylaş")
    u.add_argument("kanal")
    u.add_argument("--adet", type=int, default=1)
    u.add_argument("--kuru", action="store_true", help="Üret ama paylaşma")
    u.set_defaults(func=cmd_uret)

    k = sub.add_parser("karakter", help="Karakter referans görsellerini üret")
    k.add_argument("kanal")
    k.add_argument("--yenile", action="store_true")
    k.set_defaults(func=cmd_karakter)

    y = sub.add_parser("youtube-yetki", help="YouTube hesabını bağla (bir kere)")
    y.add_argument("kanal")
    y.add_argument("--client-secret", default="client_secret.json")
    y.set_defaults(func=cmd_youtube_yetki)

    g = sub.add_parser("giris", help="Tarayıcı profilinde Gemini/TikTok/Instagram'a giriş yap (bir kere)")
    g.add_argument("profil", help=r"Profil klasörü, ör. C:\BotProfil1")
    g.add_argument("--sadece-gemini", action="store_true", help="Sadece Gemini sekmesini aç")
    g.set_defaults(func=cmd_giris)

    sub.add_parser("guncelle", help="En son sürümü GitHub'dan indir").set_defaults(func=cmd_guncelle)
    sub.add_parser("rapor", help="Son çalışmanın kaydını ve klasörünü aç").set_defaults(func=cmd_rapor)

    sub.add_parser("kanallar", help="Kanalları listele").set_defaults(func=cmd_kanallar)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
