import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


# Eski .env dosyalarında kalan önceki marka adı (Cutless) yeni adla değişir
SITE_NAME = "Zaply" if _env("SITE_ADI") in ("", "Cutless") else _env("SITE_ADI")
SECRET_KEY = _env("GIZLI_ANAHTAR", "gelistirme-anahtari-degistir")
DATA_DIR = Path(_env("VERI_KLASORU", str(ROOT.parent / "saas_veri")))
DATABASE_URL = _env("VERITABANI", f"sqlite:///{DATA_DIR / 'site.db'}")
ADMIN_EMAILS = {e.strip().lower() for e in _env("ADMIN_EPOSTALAR").split(",") if e.strip()}
IBAN = _env("IBAN", "TR00 0000 0000 0000 0000 0000 00")
IBAN_NAME = _env("IBAN_ALICI", "Ad Soyad")
GOOGLE_CLIENT_ID = _env("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = _env("GOOGLE_CLIENT_SECRET")
SITE_URL = _env("SITE_ADRESI").rstrip("/")  # ör. https://zaply.app (boşsa istekten bulunur)
SMTP_HOST = _env("SMTP_SUNUCU")
SMTP_PORT = int(_env("SMTP_PORT", "587") or 587)
SMTP_USER = _env("SMTP_KULLANICI")
SMTP_PASSWORD = _env("SMTP_SIFRE")
SMTP_FROM = _env("SMTP_GONDEREN")  # ör. bildirim@zaply.app
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
# Hediyeler hep ödemeye bağlı: bedava kredi yok, bizden para çıkmaz (yalnızca kârdan pay).
# Listedeki e-postayla açılan hesap ilk yüklemesinde % ERKEN_ERISIM_YUZDE fazla kredi alır.
EARLY_TOPUP_PCT = int(_env("ERKEN_ERISIM_YUZDE", "20") or 0)
# Ana sayfadaki kayıtsız senaryo denemesi: günlük toplam sınır (yalnızca metin modeli; maliyet tavanı)
TRIAL_DAILY_LIMIT = int(_env("DENEME_GUNLUK_SINIR", "300") or 0)
# Davet programı: davet edilen kişinin ilk havalesi onaylanınca, o yüklemenin kredisinin yüzdesi kadar
# (sahte hesapla kredi toplanamaz; kendini davet etse bile kâr eksiye düşmez)
REFERRAL_PCT = int(_env("DAVET_ODULU_YUZDE", "15") or 0)  # davet edene
REFERRAL_FRIEND_PCT = int(_env("DAVET_HEDIYE_YUZDE", "10") or 0)  # davetle gelene (erken erişimle toplanmaz, büyüğü)
# Sadakat: hazır videolara harcanan her SADAKAT_ESIK kredide 1 Ekonomik video (kalite fiyatı kadar kredi) hediye
LOYALTY_EVERY = int(_env("SADAKAT_ESIK", "400") or 0)
# Vitrin modu: herkese açık deneme yayını (Canliya_Al.bat). Her zaman sahte video üretir, ödeme ve yönetim kapalıdır,
# e-posta doğrulaması atlanır; arama motorlarına kapalıdır.
SHOWCASE = _env("VITRIN_MODU") == "1"
FAKE_AI = _env("SAHTE_AI") == "1" or SHOWCASE  # geliştirme/test: API'ye gitmeden sahte video üretir
VIDEO_OFF = _env("YZ_VIDEO_KAPALI") == "1"  # ücretli video modeli yokken: yalnızca viral formatlar açık
PRELAUNCH = SHOWCASE or _env("ERKEN_ERISIM") == "1"
TEXT_MODEL = _env("METIN_MODELI", "gemini-flash-lite-latest")  # hızlı ve ücretsiz katmanda
TTS_MODEL = _env("SES_MODELI", "gemini-2.5-flash-preview-tts")  # viral formatların seslendirmesi
# Viral formatlar (mesajlaşma, itiraf/hikâye): video modeli kullanmaz, sadece metin + seslendirme → ucuz, sabit fiyat.
FORMAT_CREDITS = int(_env("KREDI_FORMAT", "19") or 19)
FORMAT_MIN_SECONDS = 15
TIMEZONE = _env("SAAT_DILIMI", "Europe/Istanbul")
WORKER_ENABLED = _env("ISCI", "1") != "0"

# Kalite seçenekleri: kullanıcıdan düşen kredi (1 kredi ≈ 1 TL).
# model: "google:<veo modeli>" (ön ek yazılmazsa google) ya da "fal:<fal.ai uç noktası>"; her kademe farklı firma olabilir.
# MODEL_<KADEME>_ARGS: fal.ai'ye gönderilecek ek JSON (ör. {"duration": "5"}); MODEL_<KADEME>_REF: referans görselli
# (image-to-video) fal uç noktası. Google Veo 3.1 referans görseli kendisi destekler.
def _quality(key: str, label: str, model: str, resolution: str, credits: int, per_sec: int, ai: str,
             desc: str) -> dict:
    env = key.upper()
    clips = [int(x) for x in _env(f"MODEL_{env}_SURELER", "4 6 8").split() if x.isdigit()] or [8]
    return {"label": label, "model": _env(f"MODEL_{env}", model), "args": _env(f"MODEL_{env}_ARGS"),
            "ref_model": _env(f"MODEL_{env}_REF"), "resolution": _env(f"MODEL_{env}_COZUNURLUK", resolution),
            "credits": int(_env(f"KREDI_{env}", str(credits)) or credits),  # BASE_SECONDS'a kadar sabit fiyat
            "per_sec": int(_env(f"KREDI_{env}_SANIYE", str(per_sec)) or per_sec),  # üstündeki her saniye
            "ai": _env(f"MODEL_{env}_AD", ai), "clips": sorted(set(clips)), "desc": desc}


QUALITIES = {
    "lite": _quality("lite", "Ekonomik", "veo-3.1-lite-generate-preview", "720p", 49, 5, "Google Veo 3.1 Lite",
                     "Hızlı ve ucuz, denemeler için"),
    "fast": _quality("fast", "Standart", "veo-3.1-fast-generate-preview", "720p", 99, 10, "Google Veo 3.1 Fast",
                     "Çoğu kanal için en iyi denge"),
    "standard": _quality("standard", "Premium", "veo-3.1-generate-preview", "1080p", 390, 39, "Google Veo 3.1",
                         "En yüksek kalite, 1080p"),
}
# Video süresi: kullanıcı çubukla seçer. BASE_SECONDS'a kadar kalitenin sabit fiyatı, üstü saniye başı.
# Uzun video birden çok sahnenin (Veo: 4/6/8 sn) üretilip birleştirilmesiyle yapılır.
MIN_SECONDS = int(_env("SURE_EN_AZ", "4") or 4)
MAX_SECONDS = int(_env("SURE_EN_COK", "60") or 60)
BASE_SECONDS = int(_env("SURE_SABIT_FIYAT", "10") or 10)
DEFAULT_SECONDS = 8


def clamp_seconds(value) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        v = DEFAULT_SECONDS
    return max(MIN_SECONDS, min(MAX_SECONDS, v))


def price(quality: str, seconds: int, fmt: str = "") -> int:
    """Videonun kredi fiyatı: BASE_SECONDS'a kadar sabit, üstündeki her saniye kalitenin saniye fiyatı.
    Viral formatlar (mesajlaşma, hikâye) video modeli kullanmadığı için sabit fiyatlıdır."""
    if fmt:
        return FORMAT_CREDITS
    q = QUALITIES[quality]
    return q["credits"] + q["per_sec"] * max(0, clamp_seconds(seconds) - BASE_SECONDS)


def plan_clips(quality: str, seconds: int) -> list[int]:
    """İstenen süreyi en az sahne ve en az fazlalıkla karşılayan sahne süreleri (sonra tam süreye kırpılır)."""
    from itertools import combinations_with_replacement

    seconds, opts = clamp_seconds(seconds), QUALITIES[quality]["clips"]
    n = -(-seconds // max(opts))
    while True:
        combos = [c for c in combinations_with_replacement(sorted(opts, reverse=True), n) if sum(c) >= seconds]
        if combos:
            return list(min(combos, key=lambda c: (sum(c), -c[0])))
        n += 1


# Abonelikler: her plan kendi yapay zekâsını (ve altındakileri) açar, her ay kredisini yükler (30 gün, havale ile).
# Aboneliği olmayan Ekonomik'i kredi paketiyle kullanabilir.
def _plan(key: str, label: str, price_tl: int, credits: int, quality: str, desc: str) -> dict:
    env = key.upper()
    return {"label": label, "price": int(_env(f"PLAN_{env}_FIYAT", str(price_tl)) or price_tl),
            "credits": int(_env(f"PLAN_{env}_KREDI", str(credits)) or credits), "quality": quality, "desc": desc}


PLANS = {
    "baslangic": _plan("baslangic", "Başlangıç", 299, 330, "lite", "Yeni başlayan kanallar için"),
    "pro": _plan("pro", "Pro", 749, 850, "fast", "Her gün video paylaşanlar için"),
    "studyo": _plan("studyo", "Stüdyo", 1999, 2300, "standard", "Markalar ve ajanslar için"),
}
PLAN_DAYS = 30
# Yıllık abonelik: 12 ay için bu kadar aylık ücret ödenir (10 → 2 ay bedava); kredi her ay yüklenir
YEARLY_PAID_MONTHS = int(_env("YILLIK_ODENEN_AY", "10") or 10)
YEARLY_SAVE_PCT = round((12 - YEARLY_PAID_MONTHS) * 100 / 12)


def plan_price(plan: str, yearly: bool = False) -> int:
    """Planın ödenecek tutarı (TL): aylık ya da 12 aylık toplam."""
    return PLANS[plan]["price"] * (YEARLY_PAID_MONTHS if yearly else 1)
FREE_QUALITIES = ("lite",)  # aboneliksiz (kredi paketiyle) kullanılabilen kalite


def plan_qualities(plan: str) -> tuple:
    """Planın açtığı kaliteler: kendi kademesi ve altındakiler."""
    order = list(QUALITIES)
    if plan not in PLANS:
        return FREE_QUALITIES
    return tuple(dict.fromkeys([*FREE_QUALITIES, *order[:order.index(PLANS[plan]["quality"]) + 1]]))


def plan_for_quality(quality: str) -> str:
    """Bu kaliteyi açan en ucuz plan."""
    return next((k for k in PLANS if quality in plan_qualities(k)), "")
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
# Yönetim panelindeki kâr tahmini için: 8 sn videonun sağlayıcı fiyatı (USD) ve dolar kuru
VIDEO_COST_USD = {k: float(_env(f"MALIYET_{k.upper()}", v) or v) for k, v in
                  {"lite": "0.40", "fast": "0.80", "standard": "3.20"}.items()}


def cost_usd(quality: str, seconds: int) -> float:
    """Videonun tahmini sağlayıcı maliyeti: üretilen sahnelerin toplam süresi × saniye fiyatı."""
    return VIDEO_COST_USD.get(quality, 0) / 8 * sum(plan_clips(quality, seconds))
USD_TRY = float(_env("DOLAR_KURU", "42") or 42)

# Kredi paketleri: (TL, verilen kredi)
PACKAGES = [(250, 250), (500, 525), (1000, 1100)]

# Arka plan temaları: anahtar -> (ad, zemin rengi). Seçim "tema" çerezinde; varsayılan grafit gri
THEMES = {  # anahtar: (ad, zemin rengi, koyu/açık); "sistem" cihazın açık/koyu ayarını izler
    "grafit": ("Grafit", "#1b1b1f", "dark"), "gece": ("Gece", "#0c0b0a", "dark"), "lacivert": ("Lacivert", "#0f1526", "dark"),
    "mor": ("Mor", "#1a1424", "dark"), "orman": ("Orman", "#101a16", "dark"), "bordo": ("Bordo", "#1c1013", "dark"),
    "petrol": ("Petrol", "#0d1b1e", "dark"), "kahve": ("Kahve", "#1b1612", "dark"),
    "kar": ("Kar", "#f3f3f1", "light"), "krem": ("Krem", "#f8ebd2", "light"), "seftali": ("Şeftali", "#fde0cf", "light"),
    "pudra": ("Pudra", "#fadbe5", "light"), "lavanta": ("Lavanta", "#e8e0fa", "light"), "buz": ("Buz", "#dde9fa", "light"), "nane": ("Nane", "#d9f0e2", "light"),
    "sistem": ("Sistem", "#1b1b1f", "auto"),
}
DEFAULT_THEME = "grafit"
THEME_COOKIE = "tema"

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
