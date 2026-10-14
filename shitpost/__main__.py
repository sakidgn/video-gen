import argparse
import sys
from pathlib import Path

from .config import list_channels, load_channel


def _client():
    from google import genai
    from google.genai import types

    # Zaman aşımı olmazsa API cevap vermediğinde program sonsuza kadar bekliyor.
    return genai.Client(http_options=types.HttpOptions(timeout=60_000))


def _idle_seconds() -> float:
    from .browser import idle_seconds

    return idle_seconds()


def _sleep_pc() -> None:
    import ctypes

    ctypes.windll.powrprof.SetSuspendState(False, False, False)


def _keep_awake(on: bool) -> None:
    # Zamanlanmış görev bilgisayarı uykudan uyandırınca, iş bitmeden tekrar uykuya geçmesin.
    if sys.platform != "win32":
        return
    import ctypes

    es_continuous, es_system, es_display = 0x80000000, 0x00000001, 0x00000002
    flags = es_continuous | es_system | es_display if on else es_continuous
    ctypes.windll.kernel32.SetThreadExecutionState(flags)


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
    # Zamanlanmış çalışmada kimse bilgisayar başında değilse iş bitince tekrar uyutulur.
    sleep_after = getattr(args, "uyut", False) and _idle_seconds() > 120
    _keep_awake(True)
    from .browser import wake_display

    wake_display()
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
        _keep_awake(False)
        if sleep_after and _idle_seconds() > 60:
            print("İş bitti, kimse bilgisayar başında değil: uyku moduna alınıyor.")
            _sleep_pc()


def _skip_list(args) -> list[str]:
    return [x.strip() for x in (getattr(args, "atla", "") or "").split(",") if x.strip()]


RUN_ATTEMPTS = 3
RUN_RETRY_WAIT = 60
RUN_TIME_BUDGET = 80 * 60  # bundan sonra yeni deneme başlatma (sonraki zamanlanmış çalışmayla çakışmasın)

# Hata metnindeki ipucu -> kullanıcıya Türkçe açıklama
PROBLEM_HINTS = [
    (("oturumu açık değil", "login", "accounts.google.com"),
     "Bir sitede oturum kapanmış. Menüden 1 (ve 2) ile Chrome'u açıp o siteye tekrar giriş yap."),
    (("video limitinin", "noquotaleft", "gemini_profiller"),
     "Gemini'nin iki hesabında da video hakkı dolmuş. Birkaç saat sonra kendiliğinden düzelir."),
    (("yoğun", "geminibusyall", "high traffic"),
     "Gemini çok yoğundu, video üretemedi. Sonraki saatte büyük ihtimalle düzelir."),
    (("chatgpt",), "ChatGPT'den prompt alınamadı. ChatGPT'de oturum açık mı, 'Shitpost gen' projesi duruyor mu bak."),
    (("reddetti", "videofiltered"), "Gemini 3 farklı promptu da reddetti. Sonraki saatte yeni promptla dener."),
    (("chrome bulunamadı",), "Chrome bulunamadı. Chrome'u kur."),
    (("youtube",), "YouTube'a yüklenemedi. Menüden 1 ile YouTube Studio'ya girip bir uyarı var mı bak."),
    (("tiktok",), "TikTok'a yüklenemedi. Menüden 1 ile TikTok'a girip bir uyarı/doğrulama var mı bak."),
    (("instagram",), "Instagram'a yüklenemedi. Menüden 1 ile Instagram'a girip bir uyarı/doğrulama var mı bak."),
    (("timeout", "zaman aşımı", "içinde video vermedi"), "Bir adım çok uzun sürdü (internet yavaş olabilir)."),
]


def explain_problem(text: str) -> str:
    low = text.lower()
    for keys, hint in PROBLEM_HINTS:
        if any(k in low for k in keys):
            return hint
    return "Bilinmeyen bir hata. Menü 8 ile son_calisma.txt'yi açıp Claude'a gönder."


def record_problem(text: str) -> None:
    """Sorunu herkesin anlayacağı şekilde cikti/sorunlar.txt dosyasına ekler."""
    import time as _t

    from .config import OUTPUT_DIR

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    line = f"[{_t.strftime('%d.%m.%Y %H:%M')}] {explain_problem(text)}\n    (teknik: {text[:300]})\n"
    with (OUTPUT_DIR / "sorunlar.txt").open("a", encoding="utf-8") as f:
        f.write(line)
    print("\n" + "=" * 60 + f"\nSORUN: {explain_problem(text)}\n(cikti/sorunlar.txt dosyasına yazıldı)\n" + "=" * 60)


def _uret(args, pipeline) -> int:
    import time as _t
    import traceback

    channel = load_channel(args.kanal)
    client = _client()
    failed = 0
    started = _t.time()
    for i in range(args.adet):
        if args.adet > 1:
            print(f"\n=== Video {i + 1}/{args.adet} ===")
        last = ""
        result = None
        for attempt in range(1, RUN_ATTEMPTS + 1):
            if attempt > 1:
                if _t.time() - started > RUN_TIME_BUDGET:
                    print("Süre doldu, bu sefer tekrar denenmiyor.")
                    break
                print(f"\n>>> Baştan tekrar deneniyor ({attempt}/{RUN_ATTEMPTS}), {RUN_RETRY_WAIT} sn sonra...")
                _t.sleep(RUN_RETRY_WAIT)
            try:
                result = pipeline.run(client, channel, publish=not args.kuru, skip_platforms=_skip_list(args))
                break
            except pipeline.NoQuotaLeft as e:
                last = f"NoQuotaLeft: {e}"
                print(f"Durduruldu: {e}")
                break  # hak yoksa tekrar denemenin anlamı yok
            except Exception as e:
                last = f"{type(e).__name__}: {e}"
                print(f"HATA: {last}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
        if result is None:
            failed += 1
            record_problem(last or "bilinmeyen hata")
            continue
        if result.errors:
            failed += 1
            for name, err in result.errors.items():
                record_problem(f"{name}: {err}")
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
        urls += [
            "https://chatgpt.com/",
            "https://studio.youtube.com/",
            "https://www.tiktok.com/login",
            "https://www.instagram.com/accounts/login/",
        ]

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
            if not rel or info.is_dir() or rel.endswith("gecmis.json") or rel.startswith(SITE_PREFIX):
                continue  # site (otoshort_site/) ayrı klasörde, buraya inmez
            target = ROOT / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(info))
            updated += 1
    print(f"Güncellendi ({updated} dosya).")
    return 0


SITE_PREFIX = "otoshort_site/"
OLD_SITE_LEFTOVERS = ["saas", "site_dene.bat"]


def _desktop() -> Path:
    """Windows'ta gerçek Masaüstü klasörü (OneDrive'a taşınmış olsa bile)."""
    import os

    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]

            fid = GUID(0xB4BFCC3A, 0xDB2C, 0x424C, (ctypes.c_ubyte * 8)(0xB0, 0x29, 0x7F, 0xE9, 0x9A, 0x87, 0xC6, 0x41))
            out = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(fid), 0, None, ctypes.byref(out)) == 0:
                path = Path(out.value)
                ctypes.windll.ole32.CoTaskMemFree(out)
                return path
        except Exception:
            pass
    home = Path.home()
    return home / "Desktop" if (home / "Desktop").exists() else home


def cmd_site_kur(args) -> int:
    """Siteyi (SaaS) shitpost klasöründen ayrı, Masaüstünde kendi klasörüne indirir ve eski kalıntıları temizler."""
    import io
    import os
    import shutil
    import zipfile

    import requests

    from .config import ROOT

    dest = Path(args.hedef) if args.hedef else _desktop() / "Otoshort Site"
    print(f"Site şu klasöre kuruluyor: {dest}")
    r = requests.get(os.environ.get("GUNCELLEME_URL", UPDATE_URL), timeout=120)
    r.raise_for_status()
    n = 0
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        for info in z.infolist():
            rel = info.filename.split("/", 1)[1] if "/" in info.filename else ""
            if info.is_dir() or not rel.startswith(SITE_PREFIX):
                continue
            sub = rel[len(SITE_PREFIX):]
            if not sub or sub.startswith((".env", "saas_veri")):
                continue
            target = dest / sub
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(info))
            n += 1
    if not n:
        print("Site dosyaları bulunamadı, daha sonra tekrar dene.")
        return 1
    old_data = ROOT / "saas_veri_deneme"
    if old_data.exists() and not (dest / "saas_veri_deneme").exists():
        shutil.move(str(old_data), str(dest / "saas_veri_deneme"))
        print("Deneme verilerin de taşındı.")
    for name in OLD_SITE_LEFTOVERS:
        p = ROOT / name
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()
    print(f"Tamam ({n} dosya). Shitpost klasörü artık sadece shitpost için.")
    print(f"Siteyi açmak için: {dest} klasöründeki Siteyi_Ac.bat")
    if os.name == "nt" and not args.acma:
        os.startfile(str(dest))  # klasörü aç
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
    problems = OUTPUT_DIR / "sorunlar.txt"
    for target in [problems if problems.exists() else None, log if log.exists() else None,
                   runs[-1] if runs else None]:
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
    u.add_argument("--uyut", action="store_true", help="Bitince, kimse başında değilse bilgisayarı uyut")
    u.add_argument("--atla", default="", help="Bu sefer paylaşılmayacak platformlar, virgülle (örn. instagram_web)")
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

    sk = sub.add_parser("site-kur", help="Siteyi Masaüstünde ayrı klasöre kur")
    sk.add_argument("--hedef", default="")
    sk.add_argument("--acma", action="store_true", help="Bitince klasörü açma")
    sk.set_defaults(func=cmd_site_kur)
    sub.add_parser("guncelle", help="En son sürümü GitHub'dan indir").set_defaults(func=cmd_guncelle)
    sub.add_parser("rapor", help="Son çalışmanın kaydını ve klasörünü aç").set_defaults(func=cmd_rapor)

    sub.add_parser("kanallar", help="Kanalları listele").set_defaults(func=cmd_kanallar)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
