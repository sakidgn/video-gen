import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


SITE_NAME = _env("SITE_ADI", "Cutless")
SECRET_KEY = _env("GIZLI_ANAHTAR", "gelistirme-anahtari-degistir")
DATA_DIR = Path(_env("VERI_KLASORU", str(ROOT.parent / "saas_veri")))
DATABASE_URL = _env("VERITABANI", f"sqlite:///{DATA_DIR / 'site.db'}")
ADMIN_EMAILS = {e.strip().lower() for e in _env("ADMIN_EPOSTALAR").split(",") if e.strip()}
IBAN = _env("IBAN", "TR00 0000 0000 0000 0000 0000 00")
IBAN_NAME = _env("IBAN_ALICI", "Ad Soyad")
GOOGLE_CLIENT_ID = _env("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = _env("GOOGLE_CLIENT_SECRET")
SITE_URL = _env("SITE_ADRESI").rstrip("/")  # ör. https://cutless.app (boşsa istekten bulunur)
SMTP_HOST = _env("SMTP_SUNUCU")
SMTP_PORT = int(_env("SMTP_PORT", "587") or 587)
SMTP_USER = _env("SMTP_KULLANICI")
SMTP_PASSWORD = _env("SMTP_SIFRE")
SMTP_FROM = _env("SMTP_GONDEREN")  # ör. bildirim@cutless.app
# Yasal sayfalarda (kullanım şartları, KVKK, mesafeli satış) görünen satıcı bilgileri
LEGAL = {
    "name": _env("SIRKET_UNVANI"),  # şirket unvanı ya da şahıs şirketi için ad soyad
    "address": _env("SIRKET_ADRESI"),
    "tax": _env("VERGI_BILGISI"),  # ör. "Kadıköy VD · 1234567890"
    "email": _env("ILETISIM_EPOSTA"),
    "date": _env("YASAL_TARIH"),  # metinlerin son güncellenme tarihi, ör. 01.11.2026
    "host": _env("SUNUCU_SAGLAYICI"),  # ör. "Hetzner Online GmbH, Almanya"
}
SIGNUP_BONUS = int(_env("KAYIT_HEDIYE_KREDI", "0") or 0)
# Açılış öncesi dönem: ana sayfada erken erişim listesi gösterilir (vitrin modunda her zaman açık).
# Listede olan e-postayla kaydolup doğrulayan ERKEN_ERISIM_HEDIYE kadar kredi alır.
EARLY_BONUS = int(_env("ERKEN_ERISIM_HEDIYE", "100") or 0)
# Davet programı: davet edilen kişinin ilk havalesi onaylanınca ikisine de kredi (sahte hesapla kredi toplanamasın diye)
REFERRAL_BONUS = int(_env("DAVET_ODULU", "50") or 0)  # davet edene
REFERRAL_FRIEND_BONUS = int(_env("DAVET_HEDIYE", "25") or 0)  # davetle gelene
# Vitrin modu: herkese açık deneme yayını (Canliya_Al.bat). Her zaman sahte video üretir, ödeme ve yönetim kapalıdır,
# e-posta doğrulaması atlanır; arama motorlarına kapalıdır.
SHOWCASE = _env("VITRIN_MODU") == "1"
FAKE_AI = _env("SAHTE_AI") == "1" or SHOWCASE  # geliştirme/test: API'ye gitmeden sahte video üretir
PRELAUNCH = SHOWCASE or _env("ERKEN_ERISIM") == "1"
TEXT_MODEL = _env("METIN_MODELI", "gemini-flash-latest")
TIMEZONE = _env("SAAT_DILIMI", "Europe/Istanbul")
WORKER_ENABLED = _env("ISCI", "1") != "0"

# Kalite seçenekleri: kullanıcıdan düşen kredi (1 kredi ≈ 1 TL).
# model: "google:<veo modeli>" (ön ek yazılmazsa google) ya da "fal:<fal.ai uç noktası>"; her kademe farklı firma olabilir.
# MODEL_<KADEME>_ARGS: fal.ai'ye gönderilecek ek JSON (ör. {"duration": "5"}); MODEL_<KADEME>_REF: referans görselli
# (image-to-video) fal uç noktası. Google Veo 3.1 referans görseli kendisi destekler.
def _quality(key: str, label: str, model: str, resolution: str, credits: int, desc: str) -> dict:
    env = key.upper()
    return {"label": label, "model": _env(f"MODEL_{env}", model), "args": _env(f"MODEL_{env}_ARGS"),
            "ref_model": _env(f"MODEL_{env}_REF"), "resolution": _env(f"MODEL_{env}_COZUNURLUK", resolution),
            "credits": int(_env(f"KREDI_{env}", str(credits)) or credits), "desc": desc}


QUALITIES = {
    "lite": _quality("lite", "Ekonomik", "veo-3.1-lite-generate-preview", "720p", 35, "Hızlı ve ucuz, denemeler için"),
    "fast": _quality("fast", "Standart", "veo-3.1-fast-generate-preview", "720p", 65, "Çoğu kanal için en iyi denge"),
    "standard": _quality("standard", "Premium", "veo-3.1-generate-preview", "1080p", 250, "En yüksek kalite"),
}
FAL_KEY = _env("FAL_KEY")
# Otomatik paylaşım uygulama anahtarları (YouTube, Google ile girişteki istemciyi kullanır)
TIKTOK_CLIENT_KEY = _env("TIKTOK_CLIENT_KEY")
TIKTOK_CLIENT_SECRET = _env("TIKTOK_CLIENT_SECRET")
INSTAGRAM_APP_ID = _env("INSTAGRAM_APP_ID")
INSTAGRAM_APP_SECRET = _env("INSTAGRAM_APP_SECRET")


def provider(quality: str) -> tuple[str, str]:
    """('google' | 'fal', model adı)"""
    spec = QUALITIES[quality]["model"]
    name, _, rest = spec.partition(":")
    return (name, rest) if rest and name in ("google", "fal") else ("google", spec)


def ai_vendors() -> str:
    """KVKK metni için: verinin aktarıldığı yapay zekâ sağlayıcıları (metin yazımı her zaman Google Gemini)."""
    names = ["Google LLC"]
    if any(provider(q)[0] == "fal" for q in QUALITIES):
        names.append("Features & Labels, Inc. (fal.ai)")
    return ", ".join(names)


def supports_refs(quality: str) -> bool:
    """Bu kalitede referans karakter görseli kullanılabilir mi?"""
    return provider(quality)[0] == "google" or bool(QUALITIES[quality]["ref_model"])


DURATION_SECONDS = 8
# Yönetim panelindeki kâr tahmini için: 8 sn videonun Google fiyatı (USD) ve dolar kuru
VIDEO_COST_USD = {k: float(_env(f"MALIYET_{k.upper()}", v) or v) for k, v in
                  {"lite": "0.40", "fast": "0.80", "standard": "3.20"}.items()}
USD_TRY = float(_env("DOLAR_KURU", "42") or 42)

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
STYLE_EMOJI = {"meme3d": "🎮", "cartoon": "🖍️", "realistic": "🎥", "claymation": "🧱", "anime": "🌸"}
QUALITY_EMOJI = {"lite": "⚡", "fast": "🚀", "standard": "💎"}
LANGUAGE_FLAGS = {"tr": "🇹🇷", "en": "🇬🇧", "de": "🇩🇪", "es": "🇪🇸", "ar": "🇸🇦"}
