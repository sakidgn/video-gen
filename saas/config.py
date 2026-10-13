import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


SITE_NAME = _env("SITE_ADI", "Otoshort")
SECRET_KEY = _env("GIZLI_ANAHTAR", "gelistirme-anahtari-degistir")
DATA_DIR = Path(_env("VERI_KLASORU", str(ROOT.parent / "saas_veri")))
DATABASE_URL = _env("VERITABANI", f"sqlite:///{DATA_DIR / 'site.db'}")
ADMIN_EMAILS = {e.strip().lower() for e in _env("ADMIN_EPOSTALAR").split(",") if e.strip()}
IBAN = _env("IBAN", "TR00 0000 0000 0000 0000 0000 00")
IBAN_NAME = _env("IBAN_ALICI", "Ad Soyad")
SIGNUP_BONUS = int(_env("KAYIT_HEDIYE_KREDI", "0") or 0)
FAKE_AI = _env("SAHTE_AI") == "1"  # geliştirme/test: API'ye gitmeden sahte video üretir
TEXT_MODEL = _env("METIN_MODELI", "gemini-flash-latest")
TIMEZONE = _env("SAAT_DILIMI", "Europe/Istanbul")
WORKER_ENABLED = _env("ISCI", "1") != "0"

# Kalite seçenekleri: kullanıcıdan düşen kredi (1 kredi ≈ 1 TL). Maliyet: 8 sn Veo 3.1 (Google fiyat listesi).
QUALITIES = {
    "lite": {"label": "Ekonomik", "model": _env("MODEL_LITE", "veo-3.1-lite-generate-preview"),
             "resolution": "720p", "credits": 35, "desc": "Hızlı ve ucuz, denemeler için"},
    "fast": {"label": "Standart", "model": _env("MODEL_FAST", "veo-3.1-fast-generate-preview"),
             "resolution": "720p", "credits": 65, "desc": "Çoğu kanal için en iyi denge"},
    "standard": {"label": "Premium", "model": _env("MODEL_STANDARD", "veo-3.1-generate-preview"),
                 "resolution": "1080p", "credits": 250, "desc": "En yüksek kalite, 1080p"},
}
DURATION_SECONDS = 8

# Kredi paketleri: (TL, verilen kredi)
PACKAGES = [(250, 250), (500, 550), (1000, 1200)]

LANGUAGES = {"tr": "Türkçe", "en": "English", "de": "Deutsch", "es": "Español", "ar": "العربية"}

STYLES = {
    "meme3d": "cheap janky 3D video game look, low-poly models, stiff animations, silly physics",
    "cartoon": "colorful 2D cartoon animation, bold outlines, exaggerated expressions",
    "realistic": "cinematic realistic footage, natural lighting, handheld camera",
    "claymation": "stop-motion claymation, handmade clay characters, slightly jerky motion",
    "anime": "anime style, vibrant colors, dynamic camera, expressive faces",
}
STYLE_LABELS = {"meme3d": "Ucuz 3D oyun (meme)", "cartoon": "Çizgi film", "realistic": "Gerçekçi",
                "claymation": "Kil animasyon", "anime": "Anime"}
