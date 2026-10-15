"""Yayına hazırlık kontrolü: canlıya çıkmadan önce eksik ayarları listeler (yönetim paneli → Yayına hazırlık).
Komut satırından: python -m saas.hazirlik"""
import os
import shutil
from dataclasses import dataclass

from . import config

DEFAULT_SECRET = "gelistirme-anahtari-degistir"
DEFAULT_IBAN = "TR00 0000 0000 0000 0000 0000 00"


@dataclass
class Check:
    level: str  # "zorunlu" | "onerilen" | "istege"
    ok: bool
    title: str
    detail: str


def _ffmpeg_ok() -> bool:
    try:
        import imageio_ffmpeg

        return bool(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        return bool(shutil.which("ffmpeg"))


def _price_rows() -> list[tuple[str, float, float]]:
    """(kalite adı, kredi başına en düşük gelir ile video geliri ₺, API maliyeti ₺)"""
    per_credit = min(tl / cr for tl, cr in config.PACKAGES)  # en büyük paketteki hediye krediler dahil
    return [(q["label"], q["credits"] * per_credit, config.VIDEO_COST_USD.get(k, 0) * config.USD_TRY)
            for k, q in config.QUALITIES.items()]


def checks() -> list[Check]:
    out: list[Check] = []

    def add(level, ok, title, detail):
        out.append(Check(level, bool(ok), title, detail))

    add("zorunlu", config.SECRET_KEY != DEFAULT_SECRET and len(config.SECRET_KEY) >= 32, "Gizli anahtar",
        "GIZLI_ANAHTAR uzun ve rastgele olmalı (oturumlar ve bağlı hesap jetonları bununla korunur). Üret: "
        "python -c \"import secrets;print(secrets.token_urlsafe(48))\"")
    add("zorunlu", not config.FAKE_AI, "Gerçek video üretimi",
        "SAHTE_AI=0 olmalı; açıkken kullanıcılara sahte video üretilir.")
    gemini = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    add("zorunlu", gemini, "Google Gemini anahtarı",
        "GEMINI_API_KEY: senaryo, fikir ve altyazı her kalitede Gemini ile yazılır (Veo videoları da bu anahtarla).")
    if any(config.provider(q)[0] == "fal" for q in config.QUALITIES):
        add("zorunlu", config.FAL_KEY, "fal.ai anahtarı", "Bir kalite fal.ai modeli kullanıyor: FAL_KEY gerekli.")
    add("zorunlu", config.SITE_URL.startswith("https://"), "Site adresi (https)",
        "SITE_ADRESI=https://alanadin şeklinde olmalı (e-posta bağlantıları, Google girişi ve Instagram için).")
    from . import mailer

    add("zorunlu", mailer.enabled(), "E-posta gönderimi (SMTP)",
        "SMTP_* ayarları: kayıt doğrulama ve şifre sıfırlama e-postaları bunlarsız gitmez.")
    add("zorunlu", config.IBAN != DEFAULT_IBAN and config.IBAN_NAME not in ("", "Ad Soyad"), "Havale bilgileri",
        "IBAN ve IBAN_ALICI: kredi sayfasında kullanıcıya gösterilen hesap.")
    missing = [k for k, label in (("name", "SIRKET_UNVANI"), ("address", "SIRKET_ADRESI"), ("tax", "VERGI_BILGISI"),
                                   ("email", "ILETISIM_EPOSTA"), ("date", "YASAL_TARIH"), ("host", "SUNUCU_SAGLAYICI"))
               if not config.LEGAL[k]]
    add("zorunlu", not missing, "Yasal sayfalardaki satıcı bilgileri",
        "Eksik: " + ", ".join({"name": "SIRKET_UNVANI", "address": "SIRKET_ADRESI", "tax": "VERGI_BILGISI",
                                "email": "ILETISIM_EPOSTA", "date": "YASAL_TARIH",
                                "host": "SUNUCU_SAGLAYICI"}[k] for k in missing)
        if missing else "Kullanım şartları, KVKK ve mesafeli satış metinleri dolu.")
    add("zorunlu", config.ADMIN_EMAILS, "Yönetici e-postası", "ADMIN_EPOSTALAR: havaleleri onaylayacak hesap.")
    add("zorunlu", _ffmpeg_ok(), "Video araçları (ffmpeg)", "Kapak resmi ve altyazı için gerekli (imageio-ffmpeg paketi).")

    for label, revenue, cost in _price_rows():
        margin = (revenue - cost) / revenue if revenue else -1
        add("zorunlu" if margin < 0 else "onerilen", margin >= 0.3, f"Fiyat/maliyet: {label}",
            f"Video başı gelir ~{revenue:.0f} ₺ (hediye krediler düşülmüş), tahmini API maliyeti ~{cost:.0f} ₺ → "
            f"kâr payı %{margin * 100:.0f}. Gerçek maliyeti öğrenince MALIYET_* ve KREDI_* ayarlarını güncelle.")

    from . import yedek

    add("onerilen", any(yedek.backup_dir().glob("site-*.db")), "Veritabanı yedeği",
        "İşçi günde bir yedek alır (saas_veri/yedekler). Yedekleri ara sıra sunucu dışına da kopyala.")
    try:
        free_gb = shutil.disk_usage(config.DATA_DIR if config.DATA_DIR.exists() else config.ROOT).free / 1e9
    except OSError:
        free_gb = 0
    add("onerilen", free_gb >= 5, "Disk alanı", f"Boş alan ~{free_gb:.1f} GB (video başı ~5–20 MB).")
    add("onerilen", config.SIGNUP_BONUS <= 50, "Kayıt hediyesi",
        f"KAYIT_HEDIYE_KREDI={config.SIGNUP_BONUS}. Yüksek hediye sahte hesapla kötüye kullanılabilir.")

    add("istege", config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET, "Google ile giriş",
        "GOOGLE_CLIENT_ID/SECRET: kayıt olmayı kolaylaştırır (YouTube paylaşımı da bu istemciyi kullanır).")
    from . import social

    for p, meta in social.PLATFORMS.items():
        add("istege", social.configured(p), f"Otomatik paylaşım: {meta['label']}",
            "Anahtarlar ve platform onayı BENIOKU'daki adımlarla.")
    return out


def summary() -> dict:
    cs = checks()
    blockers = [c for c in cs if c.level == "zorunlu" and not c.ok]
    return {"checks": cs, "blockers": len(blockers), "ok": sum(c.ok for c in cs), "total": len(cs)}


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    import importlib

    importlib.reload(config)  # .env'deki ayarlar okunsun
    names = {"zorunlu": "ZORUNLU", "onerilen": "ÖNERİLEN", "istege": "İSTEĞE BAĞLI"}
    for c in checks():
        print(f"[{'✓' if c.ok else '✗'}] {names[c.level]:<12} {c.title}" + ("" if c.ok else f"\n      → {c.detail}"))
