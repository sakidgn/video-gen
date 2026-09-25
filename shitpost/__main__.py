import argparse
import sys
from pathlib import Path

from .config import list_channels, load_channel


def _client():
    from google import genai

    return genai.Client()


def cmd_uret(args) -> int:
    from . import pipeline

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
    from playwright.sync_api import sync_playwright

    from .browser import first_page, open_profile

    with sync_playwright() as p:
        ctx = open_profile(p, args.profil)
        first_page(ctx).goto("https://gemini.google.com/app")
        if not args.sadece_gemini:
            ctx.new_page().goto("https://www.tiktok.com/login")
            ctx.new_page().goto("https://www.instagram.com/accounts/login/")
        input(f"Profil: {args.profil}\nAçılan sekmelerde giriş yap, bitince buraya dönüp ENTER'a bas...")
        ctx.close()
    print("Oturumlar kaydedildi.")
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

    sub.add_parser("kanallar", help="Kanalları listele").set_defaults(func=cmd_kanallar)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
