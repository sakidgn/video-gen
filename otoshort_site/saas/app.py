import logging
import re
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import selectinload
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware

from . import ai as ai_mod
from . import (abonelik, config, credits, db, formatlar, growth, i18n, karakter, mailer, media, oauth, publisher, rehberler, secretbox,
               social, tokens, worker)
from .icons import LOGO, brand, icon
from .models import Channel, Character, CreditTx, Feedback, Job, SharedScript, PromoCode, Publication, SocialAccount, TopUp, User, now
from .security import RateLimiter, check_password, csrf_ok, csrf_token, hash_password

log = logging.getLogger("saas")
templates = Jinja2Templates(directory=str(config.ROOT / "templates"))
login_limiter = RateLimiter(limit=10, window=600)
SAFE_NEXT = re.compile(r"^/[A-Za-z0-9/_.\-]*(\?[A-Za-z0-9_=&%.\-]*)?(#[A-Za-z0-9_\-]*)?$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")
MAX_TEXT = 600
# Tarayıcı güvenliği: yalnızca kendi dosyalarımız çalışır (satır içi script yok), başka sitede çerçeveye alınamaz
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
       "media-src 'self' blob:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; "
       "form-action 'self'; frame-ancestors 'none'")
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP, "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin", "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
}
FAQS = [
    ("Videoları nereye paylaşabilirim?",
     "TikTok, Instagram Reels, YouTube Shorts ve dikey video kabul eden her yere. Paylaşırken platformun “yapay zekâ ile oluşturuldu” etiketini açmayı unutma."),
    ("Abonelikler nasıl çalışıyor?",
     "Üç abonelik var, her biri farklı bir yapay zekâyı açar: Başlangıç (Ekonomik), Pro (Standart) ve Stüdyo (Premium 1080p). Her 30 günde planın kredisi hesabına yüklenir, kalan kredin devreder. Otomatik çekim yok: süren bitmeden hatırlatırız, yenilemek istersen havaleni bildirirsin."),
    ("Video kaç saniye olabilir?",
     "Süreyi çubukla sen seçersin (4–60 sn). 10 saniyeye kadar sabit fiyat, üstündeki her saniye seçtiğin yapay zekânın saniye fiyatı kadar. Uzun videolar birkaç sahnenin birleştirilmesiyle üretilir."),
    ("Kredi kartı gerekiyor mu?",
     "Hayır. Şimdilik kredi yüklemesi banka havalesi / EFT ile yapılıyor. Kartla ödeme yakında geliyor."),
    ("Ünlü karakterleri ya da kişileri kullanabilir miyim?",
     "Hayır. Telif ve kişilik hakları nedeniyle gerçek kişiler ve başkalarına ait karakterler üretilmez; yazarsan yapay zekâ onu özgün bir karaktere çevirir. Kendi karakterini dilediğin gibi tarif edebilirsin."),
    ("Video beğenmezsem ya da üretilemezse?",
     "Teknik bir hata ya da güvenlik filtresi yüzünden video üretilemezse kredin otomatik iade edilir. Üretilen videolar için iade yapılmaz; önce Ekonomik kaliteyle deneyip beğenince üst kaliteye geçebilirsin."),
    ("Arkadaşımı davet edersem ne kazanırım?",
     "Panelindeki “Davet et” sayfasından bağlantını paylaş. Davet ettiğin kişi ilk kredisini yüklediğinde o yüklemenin %15'i kadar kredi sana, %10 fazlası ona hediye."),
    ("Sık kullananlara hediye var mı?",
     "Evet. Hazır videolarına harcadığın her 400 kredide 1 Ekonomik video bizden. Kendiliğinden yüklenir."),
    ("Yapay zekâ saçma bir şey üretirse hesabımda doğrudan paylaşılır mı?",
     "İstemezsen hayır. Otomatik kanalda “Onaylı paylaşım” modunu seç: video hazır olunca sana bildirim gelir, izleyip tek tıkla onayladığında paylaşılır. Beğenmezsen paylaşma; hiçbir yere gitmez."),
    ("Otomatik kanalda kredim bitince ne olur?",
     "Video üretimi durur ve panelinde bir uyarı görürsün. Borçlanma ya da otomatik çekim yoktur."),    ('Altyazı ve kanca yazısı ekleniyor mu?',
     'Evet, ücretsiz. 6 altyazı stilinden birini seçersin (Viral, Kutu, Neon, Tek kelime, Klasik, Minimal). İstersen ilk 3 saniyede merak uyandıran bir açılış kancası ve en altta ilerleme çubuğu da eklenir. Altyazıyı .srt dosyası olarak da indirebilirsin.'),
    ('Kayıt olmadan deneyebilir miyim?',
     'Evet. Ana sayfadaki senaryo denemesi, Kanal Kurucu, Kanca Üretici ve Başlık ve Hashtag Üretici kayıt istemez. Video üretmek için ücretsiz hesap açman yeterli.'),
    ('Viral formatlarda ses seçebilir miyim?',
     'Evet. Quiz, hikâye, korku, Top 5 gibi formatlarda anlatıcıyı otomatik, kadın ya da erkek seçebilirsin. Mesajlaşma formatında iki farklı ses otomatik atanır.'),
]
PUBLIC_PAGES = ["/", "/fiyatlar", "/kesfet", "/sablonlar", "/araclar", "/araclar/kanal-kurucu", "/araclar/kanca-uretici",
                "/araclar/baslik-uretici", "/rehberler",
                *(f"/rehberler/{g['slug']}" for g in rehberler.GUIDES), "/oneri", "/kayit", "/giris", "/yasal/kullanim",
                "/yasal/kvkk", "/yasal/mesafeli"]


class CachedStatic(StaticFiles):
    """Tarayıcı önbelleği: sürümlü (?v=) dosyalar 1 yıl, yazı tipleri 30 gün, film/görseller 7 gün, gerisi 1 saat."""

    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        if resp.status_code in (200, 206, 304):
            if b"v=" in scope.get("query_string", b""):
                cc = "public, max-age=31536000, immutable"
            elif path.startswith("fonts/"):
                cc = "public, max-age=2592000"
            elif path.startswith(("hero/", "shots/", "icons/")) or path.endswith((".png", ".svg", ".jpg", ".webp")):
                cc = "public, max-age=604800"
            else:
                cc = "public, max-age=3600"
            resp.headers["Cache-Control"] = cc
        return resp


def create_app(*, start_worker: bool | None = None, generator=None, database_url: str | None = None) -> FastAPI:
    if config.SHOWCASE and len(config.SECRET_KEY) < 32:  # herkese açık yayında bilinen anahtar oturum taklidine açar
        raise RuntimeError("Vitrin modu için uzun ve rastgele GIZLI_ANAHTAR gerekli (Canliya_Al.bat kendisi üretir).")
    db.init(database_url)
    app = FastAPI(title=config.SITE_NAME, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY, max_age=60 * 60 * 24 * 30,
                       same_site="lax", https_only=config.SITE_URL.startswith("https://"))

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            resp.headers.setdefault(k, v)
        if config.SHOWCASE:
            resp.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
        if request.url.scheme == "https" or config.SITE_URL.startswith("https://"):
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return resp

    # metin yanıtları (HTML/CSS/JS/JSON) sıkıştırılır; video, resim ve yazı tipleri zaten sıkıştırılmış olduğu için hariç
    app.add_middleware(GZipMiddleware, minimum_size=800, compresslevel=6)
    app.add_middleware(i18n.LangMiddleware)  # en dışta: /en/... önekini diğer katmanlardan önce çözer
    app.mount("/static", CachedStatic(directory=str(config.ROOT / "static")), name="static")
    app.state.generator = generator
    _routes(app)
    if not config.FAKE_AI:  # canlı kurulumda eksik zorunlu ayarları açılışta söyle
        from . import hazirlik

        for c in hazirlik.checks():
            if c.level == "zorunlu" and not c.ok:
                log.warning("Yayına hazırlık eksiği: %s — %s", c.title, c.detail)
    if start_worker if start_worker is not None else config.WORKER_ENABLED:
        app.state.worker = worker.Worker(generator)
        app.state.worker.start()
    return app


# ---------- yardımcılar ----------

def flash(request: Request, msg: str, kind: str = "ok", link: str = "", link_label: str = "", **kw) -> None:
    """Bir sonraki sayfada gösterilecek mesaj; isteğin dilinde saklanır ({ad} yer tutucuları kw ile dolar)."""
    request.session.setdefault("flash", []).append([kind, i18n.t(msg, **kw), link, i18n.t(link_label)])


def site_url(request: Request) -> str:
    return config.SITE_URL or str(request.base_url).rstrip("/")


def mark_verified(s, user: User) -> None:
    """E-postayı doğrulanmış yapar; hoş geldin kredisi yalnızca ilk doğrulamada verilir."""
    if user.email in config.ADMIN_EMAILS:  # yönetici yetkisi ancak e-posta sahipliği kanıtlanınca
        user.is_admin = True
    if user.email_verified:
        return
    user.email_verified = True
    if config.SIGNUP_BONUS:
        credits.add(s, user.id, config.SIGNUP_BONUS, "Hoş geldin hediyesi")
    from . import waitlist



def send_email(request: Request, to: str, subject: str, html: str) -> None:
    name = mailer.send(to, subject, html)
    if name and config.FAKE_AI and not config.SHOWCASE:  # demo: e-posta gerçekten gitmez, açmak için bağlantı göster
        flash(request, "Demo modu: “{subject}” e-postası gerçekten gönderilmedi.", "demo", f"/dev/eposta/{name}",
              "E-postayı aç", subject=subject)


def send_verification(request: Request, uid: int, email: str) -> None:
    url = f"{site_url(request)}/dogrula/{tokens.make_verify(uid, email)}"
    t = i18n.t
    bonus = " " + t("Doğrulayınca hesabına <b>{n} hediye kredi</b> yüklenecek.", n=config.SIGNUP_BONUS) if config.SIGNUP_BONUS else ""
    html = mailer.render(t("E-postanı doğrula"),
                         t("{site}'a hoş geldin! Hesabını kullanmaya başlamak için e-posta adresini doğrula.",
                           site=config.SITE_NAME) + bonus,
                         (t("E-postamı doğrula"), url), t("Bağlantı 3 gün geçerli. Bu kaydı sen yapmadıysan bu e-postayı yok say."))
    send_email(request, email, t("{site}: e-postanı doğrula", site=config.SITE_NAME), html)


def notify_admins_topup(request: Request, email: str, tl: int, sender: str) -> None:
    """Yeni havale bildirimi yöneticilere e-postayla gider (hızlı onay için). Yönetici e-postaları Türkçe."""
    from html import escape

    html = mailer.render("Yeni havale bildirimi",
                         f"<b>{escape(email)}</b> {tl} ₺ havale yaptığını bildirdi (gönderen: {escape(sender)}). "
                         "Banka hesabında parayı gördükten sonra onayla.",
                         ("Yönetim paneli", f"{site_url(request)}/admin"), lang="tr")
    for to in sorted(config.ADMIN_EMAILS):
        try:
            mailer.send(to, f"{config.SITE_NAME}: {tl} ₺ havale bildirimi", html)
        except Exception:
            log.exception("Yönetici bildirimi gönderilemedi")


def remember_ref(request: Request, code: str) -> bool:
    """Davet bağlantısıyla gelen ziyaretçinin kodunu kayıt olana kadar oturumda tutar."""
    code = growth.norm_code(code)
    if not code:
        return False
    with db.session() as s:
        if not growth.referrer_id(s, code):
            return False
    request.session["ref"] = code
    return True


async def read_reference(request: Request, upload, user_id: int, keep: str = "") -> str | None:
    """Formdan gelen referans görseli kaydeder. Görsel yoksa keep (kullanıcının mevcut görseli) döner.
    Hatalı görselde flash mesajı bırakıp None döner."""
    if upload is not None and getattr(upload, "filename", ""):
        data = await upload.read(media.MAX_REF_BYTES + 1)
        try:
            return media.save_reference(data, user_id)
        except media.MediaError as e:
            flash(request, str(e), "err")
            return None
    keep = keep or ""
    return keep if keep.startswith(f"{user_id}/") and media.ref_path(keep) else ""


def require_verified(request: Request, user: User):
    """Doğrulanmamış hesap video/kanal/kredi işlemi yapamaz; yönlendirme döndürür (yoksa None)."""
    if user.email_verified:
        return None
    flash(request, "Önce e-posta adresini doğrula. Gelen kutuna bağlantı gönderdik.", "warn")
    return go("/panel")


def _active(path: str) -> str:
    for prefix in ("/video/yeni", "/kanallar", "/kredi", "/admin", "/hesap", "/davet", "/videolar", "/baglantilar",
                   "/takvim", "/karakterler", "/ayarlar", "/abonelik", "/rehberler", "/oneri"):
        if path.startswith(prefix):
            return prefix
    if path.startswith("/video/"):
        return "/videolar"
    return "/panel"


def render(request: Request, name: str, user: User | None = None, status_code: int = 200, **ctx):
    ctx.setdefault("active", _active(request.url.path))
    lang = i18n.current()
    path = request.url.path
    public = path in PUBLIC_PAGES
    ctx.update(
        lang=lang, langs=i18n.LANGS, path=path, public_page=public,
        canonical=site_url(request) + i18n.localized_path(path, lang, tuple(PUBLIC_PAGES)),
        suggest_en=(public and lang != "en" and not request.state.lang_cookie
                    and i18n.wants_english(request.headers.get("accept-language", ""))),
    )
    ctx.update(
        request=request, user=user, site=config.SITE_NAME, csrf=csrf_token(request.session),
        flashes=request.session.pop("flash", []), qualities=config.QUALITIES, styles=config.STYLE_LABELS,
        languages=config.LANGUAGES, packages=config.PACKAGES, style_emoji=config.STYLE_EMOJI,
        google_button=oauth.enabled() or (config.FAKE_AI and not config.SHOWCASE), demo_mode=config.SHOWCASE,
        prelaunch=config.PRELAUNCH, early_pct=config.EARLY_TOPUP_PCT, ref_pct=config.REFERRAL_PCT, signup_bonus=config.SIGNUP_BONUS, base_url=site_url(request),
        quality_emoji=config.QUALITY_EMOJI, flags=config.LANGUAGE_FLAGS, legal=config.LEGAL,
        ref_qualities=[k for k in config.QUALITIES if config.supports_refs(k)],
        plans=config.PLANS, price=config.price, sec=dict(min=config.MIN_SECONDS, max=config.MAX_SECONDS,
                                                         base=config.BASE_SECONDS, default=config.DEFAULT_SECONDS),
        my_plan=abonelik.active_plan(user) if user else "",
        my_quals=abonelik.allowed(user) if user else config.FREE_QUALITIES,
        plan_for=config.plan_for_quality, formats=formatlar.FORMATS, backgrounds=formatlar.background_choices(), default_bg=formatlar.default_background(), sub_styles=media.SUB_STYLE_LABELS, video_off=config.VIDEO_OFF, voice_presets=ai_mod.VOICE_PRESETS, voice_groups=ai_mod.VOICE_GROUPS,
        format_credits=config.FORMAT_CREDITS, format_min=config.FORMAT_MIN_SECONDS,
        theme=current_theme(request), themes=config.THEMES,
        yearly_save=config.YEARLY_SAVE_PCT,
        yearly_months=config.YEARLY_PAID_MONTHS,
    )
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)


def current_theme(request: Request) -> str:
    name = request.cookies.get(config.THEME_COOKIE, "")
    return name if name in config.THEMES else config.DEFAULT_THEME


def _pw_mark(user: User) -> str:
    """Oturuma yazılan şifre izi (şifre özetinden türetilmiş HMAC; özetin kendisi çereze girmez):
    şifre değişince eski oturumlar (başka cihazlar) geçersiz olur."""
    import hashlib
    import hmac

    return hmac.new(config.SECRET_KEY.encode(), (user.pw_hash or "").encode(), hashlib.sha256).hexdigest()[:16]


def start_session(request: Request, user: User) -> None:
    request.session.clear()
    request.session["uid"] = user.id
    request.session["pv"] = _pw_mark(user)


def current_user(request: Request) -> User | None:
    uid = request.session.get("uid")
    if not uid:
        return None
    with db.session() as s:
        user = s.get(User, uid)
    if not user or user.blocked or request.session.get("pv") != _pw_mark(user):
        request.session.pop("uid", None)  # şifre değişmiş, hesap silinmiş ya da askıya alınmış
        return None
    return user


def require_user(request: Request) -> User:
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/giris"})
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if config.SHOWCASE or not (user.is_admin and user.email_verified):  # vitrinde e-posta sahipliği kanıtlanamaz
        raise HTTPException(status_code=404)
    return user


async def check_csrf(request: Request) -> None:
    form = await request.form()
    if not csrf_ok(request.session, form.get("csrf")):
        raise HTTPException(status_code=400, detail="Oturum süresi doldu, sayfayı yenileyip tekrar dene.")


def go(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def clean(text: str, limit: int = MAX_TEXT) -> str:
    return (text or "").strip()[:limit]


def local_time(dt: datetime | None) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        from datetime import timezone

        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(config.TIMEZONE)).strftime("%Y-%m-%d %H:%M" if i18n.current() == "en" else "%d.%m.%Y %H:%M")


templates.env.filters["tarih"] = local_time
templates.env.filters["slot"] = lambda slot: (f"{slot[5:21]} · {i18n.t('elle')}" if slot.startswith("elle ") else slot) if slot else ""
templates.env.globals["_"] = i18n.t
templates.env.globals["_h"] = i18n.th
templates.env.globals["_db"] = i18n.t_db
STATUS_LABELS = {"sirada": "Sırada", "uretiliyor": "Üretiliyor", "hazir": "Hazır", "hata": "Hata"}
templates.env.globals["status_labels"] = STATUS_LABELS
templates.env.globals["icon"] = icon
templates.env.globals["brand"] = brand


def _asset_version() -> str:
    """Statik dosyalar değişince adres de değişsin (tarayıcı eski CSS/JS'i önbellekten kullanmasın)."""
    import hashlib

    h = hashlib.md5()
    for f in sorted((config.ROOT / "static").glob("*.*")) + sorted((config.ROOT / "static" / "vendor").glob("*.js")):
        h.update(f.read_bytes())
    return h.hexdigest()[:10]


templates.env.globals["v"] = _asset_version()
templates.env.globals["LOGO"] = LOGO
STATUS_BADGE = {"sirada": "b-wait", "uretiliyor": "b-wait", "hazir": "b-ok", "hata": "b-err"}
templates.env.globals["status_badge"] = STATUS_BADGE
templates.env.globals["L"] = lambda path: i18n.localized_path(path, public=tuple(PUBLIC_PAGES))


def static_for_lang(path: str) -> str:
    """/static/hero/hero.mp4 → dil İngilizceyse ve dosyası varsa /static/hero/hero-en.mp4 (yoksa Türkçesi)."""
    if i18n.current() == "en":
        stem, dot, ext = path.rpartition(".")
        alt = f"{stem}-en{dot}{ext}"
        if (config.ROOT / alt.removeprefix("/")).exists():
            return alt
    return path


templates.env.globals["S"] = static_for_lang


def _valid_choice(value: str, options: dict, default: str) -> str:
    return value if value in options else default


# ---------- sayfalar ----------

def _routes(app: FastAPI) -> None:  # noqa: C901
    @app.get("/", response_class=HTMLResponse)
    def index(request: Request, ref: str = ""):
        remember_ref(request, ref)
        faqs_ld = [{"@type": "Question", "name": i18n.t(q), "acceptedAnswer": {"@type": "Answer", "text": i18n.t(a)}}
                   for q, a in FAQS]
        with db.session() as s:
            showcase = s.scalars(_public_q().order_by(Job.featured.desc(), Job.public_at.desc()).limit(8)).all()
        from . import fikirler, sablonlar

        return render(request, "index.html", current_user(request), faqs=FAQS, faqs_ld=faqs_ld, showcase=showcase,
                      tpls=sablonlar.all_for(i18n.current())[:6], tpl_cats=sablonlar.CATEGORIES,
                      use_cases=fikirler.use_cases(i18n.current()),
                      sample=fikirler.sample_script(i18n.current()),
                      ideas=[{**i, "l": i18n.t(config.STYLE_LABELS[i["s"]])} for i in fikirler.for_lang(i18n.current())])

    def _public_q():
        return select(Job).where(Job.public.is_(True), Job.status == "hazir", Job.video_file != "")

    @app.get("/kesfet", response_class=HTMLResponse)
    def explore(request: Request, sira: str = "one-cikan", sayfa: int = 1):
        per = 24
        sira = sira if sira in ("one-cikan", "yeni") else "one-cikan"
        with db.session() as s:
            q = _public_q()
            total = s.scalar(select(func.count()).select_from(q.subquery()))
            order = (Job.featured.desc(), Job.public_at.desc()) if sira == "one-cikan" else (Job.public_at.desc(),)
            pages = max(1, -(-total // per))
            sayfa = min(max(1, sayfa), pages)
            jobs = s.scalars(q.order_by(*order).offset((sayfa - 1) * per).limit(per)).all()
        return render(request, "kesfet.html", current_user(request), jobs=jobs, sira=sira, sayfa=sayfa, pages=pages,
                      total=total)

    def _public_job(s, job_id: int) -> Job:
        job = s.get(Job, job_id)
        if not job or not job.public or job.status != "hazir" or not job.video_file:
            raise HTTPException(404)
        return job

    @app.get("/kesfet/{job_id}/video")
    def explore_video(job_id: int):
        with db.session() as s:
            job = _public_job(s, job_id)
        path = worker.video_dir() / job.video_file
        if not path.exists():
            raise HTTPException(404)
        return FileResponse(path, media_type="video/mp4", headers={"Cache-Control": "public, max-age=3600"})

    @app.get("/kesfet/{job_id}/kapak")
    def explore_poster(job_id: int):
        with db.session() as s:
            job = _public_job(s, job_id)
        poster = (worker.video_dir() / job.video_file).with_suffix(".jpg")
        if not poster.exists():
            raise HTTPException(404)
        return FileResponse(poster, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})

    @app.get("/saglik")
    def health():
        """Sunucu izleme için: veritabanına erişiliyor mu, sırada kaç iş var."""
        try:
            with db.session() as s:
                queue = s.scalar(select(func.count(Job.id)).where(Job.status.in_(["sirada", "uretiliyor"])))
            return {"ok": True, "queue": queue}
        except Exception:
            log.exception("Sağlık kontrolü: veritabanına ulaşılamadı")
            return JSONResponse({"ok": False}, status_code=503)

    @app.get("/robots.txt", response_class=PlainTextResponse)
    def robots(request: Request):
        if config.SHOWCASE:  # geçici demo adresi aranmasın
            return "User-agent: *\nDisallow: /\n"
        private = ["/panel", "/video", "/videolar", "/kanallar", "/kredi", "/hesap", "/admin", "/dev", "/auth",
                   "/dogrula", "/sifre-yenile", "/api", "/baglantilar", "/baglan", "/yayin", "/davet", "/d/",
                   "/liste", "/e/", "/takvim", "/ayarlar", "/abonelik"]
        lines = ["User-agent: *", *(f"Disallow: {pre}{p}" for pre in ("", "/en") for p in private),
                 f"Sitemap: {site_url(request)}/sitemap.xml"]
        return "\n".join(lines) + "\n"

    @app.get("/sitemap.xml")
    def sitemap(request: Request):
        base = site_url(request)
        def alts(p):
            return "".join(f'<xhtml:link rel="alternate" hreflang="{lg}" href="{base}{i18n.localized_path(p, lg, (p,))}"/>'
                           for lg in i18n.LANGS)

        urls = "".join(f"<url><loc>{base}{i18n.localized_path(p, lg, (p,))}</loc>{alts(p)}</url>"
                       for p in PUBLIC_PAGES for lg in i18n.LANGS)
        xml = ('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
               f'xmlns:xhtml="http://www.w3.org/1999/xhtml">{urls}</urlset>')
        return Response(xml, media_type="application/xml")

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return FileResponse(config.ROOT / "static" / "icons" / "icon-192.png", media_type="image/png",
                            headers={"Cache-Control": "public, max-age=604800"})

    @app.get("/manifest.webmanifest")
    def manifest():
        return JSONResponse({
            "name": config.SITE_NAME, "short_name": config.SITE_NAME, "lang": i18n.current(), "start_url": "/panel",
            "display": "standalone", "background_color": config.THEMES[config.DEFAULT_THEME][1],
            "theme_color": config.THEMES[config.DEFAULT_THEME][1],
            "description": i18n.t("Yapay zekâ ile sesli, dikey kısa videolar üret."),
            "icons": [{"src": f"/static/icons/icon-{n}.png", "sizes": f"{n}x{n}", "type": "image/png", "purpose": "any"}
                      for n in (192, 512)] +
                     [{"src": "/static/icons/maskable-512.png", "sizes": "512x512", "type": "image/png",
                       "purpose": "maskable"}],
        }, media_type="application/manifest+json")

    @app.get("/dil/{code}")
    def set_language(request: Request, code: str, next: str = "/"):
        """Dil seçici: çerezi yazar, girişliyse hesaba kaydeder (e-postalar da o dilde gider), aynı sayfaya döner."""
        code = i18n.norm(code)
        path = next if SAFE_NEXT.match(next) and not next.startswith("//") else "/"  # başka siteye yönlenmesin
        path = i18n.localized_path(i18n.strip_prefix(path), code, tuple(PUBLIC_PAGES))
        resp = go(path)
        resp.set_cookie(i18n.COOKIE, code, max_age=i18n.COOKIE_AGE, samesite="lax",
                        secure=config.SITE_URL.startswith("https://"))
        if uid := request.session.get("uid"):
            with db.session() as s:
                if u := s.get(User, uid):
                    u.lang = code
        return resp

    @app.get("/tema/{name}")
    def set_theme(name: str, next: str = "/"):
        """Arka plan teması seçici (JS yoksa): çerezi yazar, aynı sayfaya döner."""
        resp = go(next if SAFE_NEXT.match(next) and not next.startswith("//") else "/")
        if name in config.THEMES:
            resp.set_cookie(config.THEME_COOKIE, name, max_age=365 * 86400, samesite="lax",
                            secure=config.SITE_URL.startswith("https://"))
        return resp

    @app.get("/yasal/{page}", response_class=HTMLResponse)
    def legal(request: Request, page: str):
        if page not in ("kullanim", "kvkk", "mesafeli"):
            raise HTTPException(404)
        return render(request, f"yasal_{page}.html", current_user(request), ai_vendors=config.ai_vendors())

    # --- hesap ---
    @app.get("/d/{code}")
    def invite_link(request: Request, code: str):
        if not remember_ref(request, code):
            flash(request, "Davet bağlantısı geçersiz, yine de kayıt olabilirsin.", "warn")
        return go("/kayit")

    def _after_signup(idea: str, tpl: str = "", kanal: dict | None = None, fmt: str = "") -> str:
        from urllib.parse import quote, urlencode

        if kanal:
            return "/kanallar/yeni?" + urlencode({"ad": kanal.get("ad", ""), "konu": kanal.get("konu", ""),
                                                  "saatler": kanal.get("saatler", "")})
        if tpl:
            return f"/kanallar/yeni?sablon={tpl}"
        if fmt:
            return f"/video/yeni?format={fmt}" + (f"&idea={quote(idea)}" if idea else "")
        return f"/video/yeni?idea={quote(idea)}" if idea else "/panel"

    # --- erken erişim listesi ---
    waitlist_limiter = RateLimiter(limit=10, window=3600)

    @app.post("/erken-erisim", dependencies=[Depends(check_csrf)])
    def waitlist_join(request: Request, email: str = Form(""), consent: str = Form(""), kaynak: str = Form(""),
                      next: str = Form("/")):
        back = next if SAFE_NEXT.match(next) and not next.startswith("//") else "/"
        email = email.strip().lower()
        ip = request.client.host if request.client else "?"
        if not waitlist_limiter.allow(f"w:{ip}"):
            flash(request, "Çok fazla deneme yaptın. Biraz sonra tekrar dene.", "err")
        elif not EMAIL_RE.match(email) or len(email) > 255:
            flash(request, "Geçerli bir e-posta yaz.", "err")
        elif not consent:
            flash(request, "Açılış duyurusu için e-posta iznini işaretlemelisin.", "err")
        else:
            from . import waitlist

            with db.session() as s:
                code = waitlist.join(s, email, i18n.current(), clean(kaynak, 30), request.session.get("wref", "")).code
            request.session["wcode"] = code
            flash(request, "Listedesin! 🎉 Açılışta haber vereceğiz.")
            return go(i18n.localized_path(f"/liste/{code}", public=()))
        return go(back)

    @app.get("/e/{code}")
    def waitlist_invite(request: Request, code: str):
        """Erken erişim davet bağlantısı: kodu hatırla, ana sayfadaki listeye götür."""
        from .models import Waitlist

        code = growth.norm_code(code)
        with db.session() as s:
            if code and s.scalar(select(Waitlist.id).where(Waitlist.code == code)):
                request.session["wref"] = code
        return go(i18n.localized_path("/", public=tuple(PUBLIC_PAGES)) + "#erken")

    @app.get("/liste/{code}", response_class=HTMLResponse)
    def waitlist_status(request: Request, code: str):
        """Listedeki kişinin sayfası: davet bağlantısı ve kazandıkları (bağlantıyı bilen görür; e-posta gizli)."""
        from . import waitlist
        from .models import Waitlist

        with db.session() as s:
            w = s.scalar(select(Waitlist).where(Waitlist.code == growth.norm_code(code)))
            if not w:
                raise HTTPException(404)
            st = waitlist.stats(s, w)
            user_part, _, domain = w.email.partition("@")
            masked = f"{user_part[:2]}•••@{domain}"
        return render(request, "liste.html", current_user(request), w=w, st=st, masked=masked,
                      link=f"{site_url(request)}/e/{w.code}")

    @app.get("/kayit", response_class=HTMLResponse)
    def register_page(request: Request, ref: str = "", fikir: str = "", sablon: str = "", kanal_ad: str = "",
                      kanal_konu: str = "", kanal_saat: str = "", format: str = ""):
        remember_ref(request, ref)
        if format in formatlar.FORMATS:  # format kartından geldi: kayıttan sonra stüdyo o formatla açılsın
            request.session["format"] = format
        if kanal_konu:  # kanal kurucudan geldi: kayıttan sonra kanal formu bu ad ve konuyla açılsın
            request.session["kanal"] = {"ad": clean(kanal_ad, 100), "konu": clean(kanal_konu, 600),
                                        "saatler": clean(kanal_saat, 60)}
        if fikir:  # fikir makinesinden geldi: kayıttan sonra stüdyoda hazır olsun
            request.session["fikir"] = clean(fikir, 300)
        if sablon and re.fullmatch(r"[a-z0-9-]{1,40}", sablon):  # şablondan geldi: kayıttan sonra kanal formu dolu açılsın
            request.session["sablon"] = sablon
        return render(request, "kayit.html", current_user(request), invited=bool(request.session.get("ref")))

    signup_limiter = RateLimiter(limit=8, window=3600)  # aynı IP'den saatte en fazla 8 hesap

    @app.post("/kayit", dependencies=[Depends(check_csrf)])
    def register(request: Request, email: str = Form(...), name: str = Form(""), password: str = Form(...),
                 accept: str = Form(""), consent: str = Form("")):
        email = email.strip().lower()
        err = None
        ip = request.client.host if request.client else "?"
        if not signup_limiter.allow(f"s:{ip}"):
            flash(request, "Çok fazla deneme yaptın. Biraz sonra tekrar dene.", "err")
            return go("/kayit")
        if not EMAIL_RE.match(email):
            err = "Geçerli bir e-posta yaz."
        elif len(password) < 8:
            err = "Şifre en az 8 karakter olmalı."
        elif not accept or not consent:
            err = "Kullanım şartlarını, KVKK metnini ve açık rızayı onaylaman gerekiyor."
        if err:
            flash(request, err, "err")
            return go("/kayit")
        with db.session() as s:
            if s.scalar(select(User.id).where(User.email == email)):
                flash(request, "Bu e-posta ile zaten bir hesap var. Giriş yap.", "err")
                return go("/giris")
            user = User(email=email, name=clean(name, 100), pw_hash=hash_password(password),
                        is_admin=False, email_verified=False, lang=i18n.current())
            s.add(user)
            s.flush()
            growth.attach_referrer(s, user, request.session.get("ref"))
            uid = user.id
        idea = request.session.get("fikir", "")
        tpl = request.session.get("sablon", "")
        kanal = request.session.get("kanal")
        fmt = request.session.get("format", "")
        start_session(request, user)
        if config.SHOWCASE:  # herkese açık demo: gerçek e-posta yok, hesap hemen açılır
            with db.session() as s:
                u = s.get(User, uid)
                u.email_verified = True
                if config.SIGNUP_BONUS:
                    credits.add(s, uid, config.SIGNUP_BONUS, "Hoş geldin hediyesi")
            flash(request, "Hesabın oluşturuldu, hoş geldin! 🎉")
            return go(_after_signup(idea, tpl, kanal, fmt))
        flash(request, "Hesabın oluşturuldu! E-postana bir doğrulama bağlantısı gönderdik. 🎉")
        send_verification(request, uid, email)
        return go(_after_signup(idea, tpl, kanal, fmt))

    @app.get("/giris", response_class=HTMLResponse)
    def login_page(request: Request):
        return render(request, "giris.html", current_user(request))

    @app.post("/giris", dependencies=[Depends(check_csrf)])
    def login(request: Request, email: str = Form(...), password: str = Form(...)):
        email = email.strip().lower()
        ip = request.client.host if request.client else "?"
        if not login_limiter.allow(f"{ip}:{email}"):
            flash(request, "Çok fazla deneme yaptın. 10 dakika sonra tekrar dene.", "err")
            return go("/giris")
        with db.session() as s:
            user = s.scalar(select(User).where(User.email == email))
        if user and not user.pw_hash and user.google_sub:
            flash(request, "Bu hesap Google ile açılmış. “Google ile devam et” butonunu kullan.", "warn")
            return go("/giris")
        if not user or not check_password(password, user.pw_hash):
            flash(request, "E-posta ya da şifre yanlış.", "err")
            return go("/giris")
        if user.blocked:
            flash(request, "Hesabın askıya alındı. Bir yanlışlık olduğunu düşünüyorsan bize yaz.", "err")
            return go("/giris")
        with db.session() as s:  # ADMIN_EPOSTALAR'a sonradan eklenen doğrulanmış hesap
            u = s.get(User, user.id)
            if u.email_verified and u.email in config.ADMIN_EMAILS:
                u.is_admin = True
        return _login_as(request, user.id)

    # --- Google ile giriş ---
    def _google_redirect_uri(request: Request) -> str:
        if config.SITE_URL:
            return f"{config.SITE_URL}/auth/google/donus"
        return str(request.url_for("google_callback"))

    def _login_as(request: Request, uid: int):
        """Oturumu açar. Dil: tarayıcıda seçilmişse hesaba yazılır, seçilmemişse hesabın dili kullanılır."""
        resp = go("/panel")
        chosen = request.state.lang_cookie
        with db.session() as s:
            u = s.get(User, uid)
            start_session(request, u)
            if chosen in i18n.LANGS:
                u.lang = chosen
            elif u.lang != i18n.current():
                resp.set_cookie(i18n.COOKIE, i18n.norm(u.lang), max_age=i18n.COOKIE_AGE, samesite="lax",
                                secure=config.SITE_URL.startswith("https://"))
        return resp

    @app.get("/auth/google")
    def google_start(request: Request):
        if not oauth.enabled():
            flash(request, "Google ile giriş henüz ayarlanmadı. Şimdilik e-posta ile devam et.", "warn")
            return go("/giris")
        state = secrets.token_urlsafe(24)
        request.session["g_state"] = state
        return RedirectResponse(oauth.auth_url(_google_redirect_uri(request), state), status_code=303)

    @app.get("/auth/google/donus", name="google_callback")
    def google_callback(request: Request, code: str = "", state: str = "", error: str = ""):
        expected = request.session.pop("g_state", None)
        if error or not code or not expected or not secrets.compare_digest(state, expected):
            flash(request, "Google ile giriş tamamlanmadı, tekrar dene.", "err")
            return go("/giris")
        try:
            prof = oauth.exchange_code(code, _google_redirect_uri(request))
        except oauth.OAuthError:
            log.exception("Google girişi başarısız")
            flash(request, "Google ile giriş şu an yapılamadı, biraz sonra tekrar dene.", "err")
            return go("/giris")
        if not prof["email_verified"]:
            flash(request, "Google hesabının e-postası doğrulanmamış.", "err")
            return go("/giris")
        with db.session() as s:
            user = s.scalar(select(User).where(User.google_sub == prof["sub"]))
            if not user:
                user = s.scalar(select(User).where(User.email == prof["email"]))
                if user and not user.google_sub:
                    user.google_sub = prof["sub"]  # aynı e-postalı hesaba Google bağlandı
                    if not user.email_verified:
                        # e-postası doğrulanmamış hesabın şifresini başkası koymuş olabilir: gerçek sahibi Google ile geldi
                        user.pw_hash = ""
            if user:
                if user.email == prof["email"]:
                    mark_verified(s, user)
                uid = user.id
            else:
                uid = None
        if uid:
            with db.session() as s:
                if s.get(User, uid).blocked:
                    flash(request, "Hesabın askıya alındı. Bir yanlışlık olduğunu düşünüyorsan bize yaz.", "err")
                    return go("/giris")
            return _login_as(request, uid)
        request.session["g_pending"] = prof  # yeni kullanıcı: önce sözleşme onayı
        return go("/kayit/google")

    @app.get("/kayit/google", response_class=HTMLResponse)
    def google_signup_page(request: Request):
        prof = request.session.get("g_pending")
        if not prof:
            return go("/kayit")
        return render(request, "kayit_google.html", None, prof=prof, invited=bool(request.session.get("ref")))

    @app.post("/kayit/google", dependencies=[Depends(check_csrf)])
    def google_signup(request: Request, accept: str = Form(""), consent: str = Form("")):
        prof = request.session.get("g_pending")
        if not prof:
            return go("/kayit")
        if not accept or not consent:
            flash(request, "Devam etmek için iki onayı da işaretle.", "err")
            return go("/kayit/google")
        with db.session() as s:
            if s.scalar(select(User.id).where((User.email == prof["email"]) | (User.google_sub == prof["sub"]))):
                flash(request, "Bu hesap zaten var, giriş yap.", "err")
                return go("/giris")
            user = User(email=prof["email"], name=prof["name"], pw_hash="", google_sub=prof["sub"],
                        is_admin=prof["email"] in config.ADMIN_EMAILS, email_verified=True, lang=i18n.current())
            s.add(user)
            s.flush()
            growth.attach_referrer(s, user, request.session.get("ref"))
            if config.SIGNUP_BONUS:
                credits.add(s, user.id, config.SIGNUP_BONUS, "Hoş geldin hediyesi")
            uid = user.id
        resp = _login_as(request, uid)
        flash(request, "Hesabın oluşturuldu, hoş geldin! 🎉")
        return resp

    # --- e-posta doğrulama ---
    verify_limiter = RateLimiter(limit=3, window=600)
    reset_limiter = RateLimiter(limit=5, window=900)

    @app.get("/dogrula/{token}")
    def verify_email(request: Request, token: str):
        data = tokens.read_verify(token)
        if not data:
            flash(request, "Doğrulama bağlantısı geçersiz ya da süresi dolmuş. Panelden yenisini iste.", "err")
            return go("/panel" if current_user(request) else "/giris")
        with db.session() as s:
            user = s.get(User, data["u"])
            if not user or user.email != data["e"]:
                flash(request, "Doğrulama bağlantısı geçersiz.", "err")
                return go("/giris")
            already = user.email_verified
            mark_verified(s, user)
            uid = user.id
        if request.session.get("uid") != uid:
            flash(request, "E-posta adresin doğrulandı. Giriş yapabilirsin. 🎉" if not already else
                  "E-posta adresin zaten doğrulanmış.")
            return go(i18n.localized_path("/giris", public=tuple(PUBLIC_PAGES)))
        if already:
            flash(request, "E-posta adresin zaten doğrulanmış.")
        elif config.SIGNUP_BONUS:
            flash(request, "E-posta adresin doğrulandı! 🎉 {n} hediye kredin yüklendi.", n=config.SIGNUP_BONUS)
        else:
            flash(request, "E-posta adresin doğrulandı! 🎉")
        return go("/panel")

    @app.post("/dogrula/tekrar", dependencies=[Depends(check_csrf)])
    def verify_resend(request: Request, user: User = Depends(require_user)):
        if user.email_verified:
            return go("/panel")
        if not verify_limiter.allow(f"v:{user.id}"):
            flash(request, "Çok fazla istek. Birkaç dakika sonra tekrar dene.", "err")
            return go("/panel")
        send_verification(request, user.id, user.email)
        flash(request, "Doğrulama bağlantısını tekrar gönderdik: {email}", email=user.email)
        return go("/panel")

    # --- şifremi unuttum ---
    @app.get("/sifremi-unuttum", response_class=HTMLResponse)
    def forgot_page(request: Request):
        return render(request, "sifremi_unuttum.html", current_user(request))

    @app.post("/sifremi-unuttum", dependencies=[Depends(check_csrf)])
    def forgot(request: Request, email: str = Form(...)):
        email = email.strip().lower()
        if config.SHOWCASE:  # demo e-postası isteyene gösterildiği için vitrinde sıfırlama başkasının hesabını açardı
            flash(request, "Demo sürümde şifre sıfırlama kapalı.", "warn")
            return go("/giris")
        ip = request.client.host if request.client else "?"
        if not reset_limiter.allow(f"{ip}:{email}"):
            flash(request, "Çok fazla deneme yaptın. Biraz sonra tekrar dene.", "err")
            return go("/sifremi-unuttum")
        with db.session() as s:
            user = s.scalar(select(User).where(User.email == email))
        if user:
            url = f"{site_url(request)}/sifre-yenile/{tokens.make_reset(user.id, user.pw_hash)}"
            t = i18n.t
            html = mailer.render(t("Şifreni yenile"), t("Hesabın için şifre sıfırlama isteği aldık. Yeni şifreni belirlemek "
                                                       "için aşağıdaki butona tıkla."), (t("Yeni şifre belirle"), url),
                                 t("Bağlantı 1 saat geçerli ve tek kullanımlık. Bu isteği sen yapmadıysan bu e-postayı "
                                   "yok say; şifren değişmez."))
            send_email(request, user.email, t("{site}: şifre sıfırlama", site=config.SITE_NAME), html)
        # hesap olsa da olmasa da aynı mesaj (e-posta tahmini yapılamasın)
        flash(request, "Bu e-postayla bir hesap varsa şifre sıfırlama bağlantısı gönderdik. Gelen kutunu kontrol et.")
        return go("/giris")

    def _reset_user(token: str):
        uid = tokens.reset_uid(token)
        if not uid:
            return None
        with db.session() as s:
            user = s.get(User, uid)
        if not user or tokens.read_reset(token, user.pw_hash) != user.id:
            return None
        return user

    @app.get("/sifre-yenile/{token}", response_class=HTMLResponse)
    def reset_page(request: Request, token: str):
        if not _reset_user(token):
            flash(request, "Şifre sıfırlama bağlantısı geçersiz ya da süresi dolmuş. Yenisini iste.", "err")
            return go("/sifremi-unuttum")
        return render(request, "sifre_yenile.html", None, token=token)

    @app.post("/sifre-yenile/{token}", dependencies=[Depends(check_csrf)])
    def reset(request: Request, token: str, password: str = Form(...), password2: str = Form(...)):
        user = _reset_user(token)
        if not user:
            flash(request, "Şifre sıfırlama bağlantısı geçersiz ya da süresi dolmuş. Yenisini iste.", "err")
            return go("/sifremi-unuttum")
        if len(password) < 8 or password != password2:
            flash(request, "Şifreler aynı olmalı ve en az 8 karakter olmalı.", "err")
            return go(f"/sifre-yenile/{token}")
        with db.session() as s:
            u = s.get(User, user.id)
            u.pw_hash = hash_password(password)
            mark_verified(s, u)  # e-postasına erişebildiğini kanıtladı
            start_session(request, u)  # diğer cihazlardaki oturumlar düşer
        flash(request, "Şifren güncellendi, giriş yaptın. 🔐")
        return go("/panel")

    # --- demo: kaydedilen e-postayı görüntüle (sadece SAHTE_AI ve SMTP yokken) ---
    @app.get("/dev/eposta/{name}", response_class=HTMLResponse)
    def dev_email(name: str):
        if not config.FAKE_AI or config.SHOWCASE or mailer.enabled() or not re.fullmatch(r"[\w.-]+\.html", name):
            raise HTTPException(404)
        path = mailer.outbox() / name
        if not path.exists():
            raise HTTPException(404)
        return HTMLResponse(path.read_text(encoding="utf-8"))

    @app.post("/cikis", dependencies=[Depends(check_csrf)])
    def logout(request: Request):
        request.session.clear()
        return go("/")

    # --- panel ---
    @app.get("/panel", response_class=HTMLResponse)
    def dashboard(request: Request, user: User = Depends(require_user)):
        with db.session() as s:
            jobs = s.scalars(select(Job).where(Job.user_id == user.id).order_by(Job.id.desc()).limit(24)).all()
            n_channels = s.scalar(select(func.count(Channel.id)).where(Channel.user_id == user.id,
                                                                       Channel.active.is_(True)))
            notices = s.scalars(select(Channel).where(Channel.user_id == user.id, Channel.notice != "")).all()
            n_videos = s.scalar(select(func.count(Job.id)).where(Job.user_id == user.id, Job.status == "hazir"))
            has_credit_tx = bool(s.scalar(select(func.count(CreditTx.id)).where(CreditTx.user_id == user.id,
                                                                               CreditTx.amount > 0)))
            awaiting = list(dict.fromkeys(s.scalars(  # onaylı kanallardan onay bekleyen videolar
                select(Publication.job_id).where(Publication.user_id == user.id, Publication.status == "onay")
                .order_by(Publication.job_id))))
            from datetime import timedelta, timezone

            month_ago = datetime.now(timezone.utc) - timedelta(days=30)
            spent = -(s.scalar(select(func.coalesce(func.sum(CreditTx.amount), 0)).where(
                CreditTx.user_id == user.id, CreditTx.amount < 0, CreditTx.created_at >= month_ago)) or 0)
            month_videos = s.scalar(select(func.count(Job.id)).where(Job.user_id == user.id, Job.status == "hazir",
                                                                     Job.created_at >= month_ago))
        plan = abonelik.active_plan(user)
        usage = {"spent": spent, "videos": month_videos, "limit": config.PLANS[plan]["credits"] if plan else 0}
        return render(request, "panel.html", user, jobs=jobs, n_channels=n_channels, notices=notices, n_videos=n_videos,
                      has_credit_tx=has_credit_tx, awaiting=awaiting, usage=usage, plan_until=user.plan_until)

    # --- tek video ---
    @app.get("/video/yeni", response_class=HTMLResponse)
    def new_video_page(request: Request, idea: str = "", src: int = Query(0, alias="from"), sablon: str = "",
                       karakter_id: int = Query(0, alias="karakter"), format: str = "",
                       user: User = Depends(require_user)):
        from . import sablonlar

        pre, tpl_name = None, ""
        if src:  # "Düzenleyip üret": eski videonun ayarlarıyla doldur
            with db.session() as s:
                job = s.get(Job, src)
                pre = job if job and job.user_id == user.id else None
        elif sablon and (t := sablonlar.get(sablon, i18n.current())):  # hazır şablonun karakter ve tarzıyla
            pre, tpl_name = sablonlar.as_channel(t, i18n.current()), t.name
        from . import fikirler

        return render(request, "video_yeni.html", user, idea=clean(idea) or (pre.idea if pre else ""), pre=pre,
                      use_cases=fikirler.use_cases(i18n.current()),
                      start_format=format if format in formatlar.FORMATS else "",
                      tpl_name=tpl_name, **_cast_ctx(user.id, [karakter_id]))

    @app.get("/takvim", response_class=HTMLResponse)
    def content_calendar(request: Request, user: User = Depends(require_user)):
        """İçerik takvimi: son 3 günün videoları ve önümüzdeki günlerde otomatik kanalların üreteceği videolar."""
        from datetime import time as dtime
        from datetime import timedelta, timezone

        tz = ZoneInfo(config.TIMEZONE)
        now_l = datetime.now(tz)
        today = now_l.date()
        days = [today + timedelta(days=i) for i in range(-3, 11)]
        since = datetime.combine(days[0], dtime.min, tz).astimezone(timezone.utc)
        with db.session() as s:
            chans = s.scalars(select(Channel).where(Channel.user_id == user.id).order_by(Channel.id)).all()
            jobs = s.scalars(select(Job).where(Job.user_id == user.id, Job.created_at >= since).order_by(Job.id)).all()
        names = {c.id: c.name for c in chans}

        def loc(dt):
            return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(tz)

        per_day = {d: [] for d in days}
        done = set()
        for j in jobs:
            if j.slot and j.channel_id:
                done.add((j.channel_id, j.slot))
            at = loc(j.created_at)
            if at.date() in per_day:
                per_day[at.date()].append({"kind": "job", "at": at.strftime("%H:%M"), "job": j,
                                           "channel": names.get(j.channel_id, "")})
        planned = []
        for ch in chans:
            if not ch.active:
                continue
            cost = config.price(ch.quality, ch.seconds, ch.format)
            for d in days:
                if d < today:
                    continue
                for t in ch.time_list():
                    try:
                        hh, mm = (int(x) for x in t.split(":"))
                    except ValueError:
                        continue
                    when = datetime.combine(d, dtime(hh, mm), tz)
                    if (ch.id, when.strftime("%Y-%m-%d %H:%M")) in done or when < now_l - worker.SLOT_GRACE:
                        continue
                    item = {"kind": "plan", "at": t, "when": when, "channel": ch.name, "cid": ch.id, "cost": cost,
                            "style": ch.style}
                    per_day[d].append(item)
                    planned.append(item)
        for items in per_day.values():
            items.sort(key=lambda i: i["at"])
        planned.sort(key=lambda i: i["when"])
        week_end = today + timedelta(days=7)
        week = [i for i in planned if i["when"].date() < week_end]
        runs_out, left = None, user.credits
        for i in planned:  # kredi hangi videoda biter?
            left -= i["cost"]
            if left < 0:
                runs_out = i["when"]
                break
        wd = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        labels = {d: (i18n.t("Bugün") if d == today else i18n.t("Yarın") if d == today + timedelta(days=1)
                      else i18n.t("Dün") if d == today - timedelta(days=1) else i18n.t(wd[d.weekday()])) for d in days}
        # boş geçmiş günler gizlenir; kanal yoksa yalnızca video olan günler
        days = [d for d in days if per_day[d] or (d >= today and chans)]
        return render(request, "takvim.html", user, days=days, per_day=per_day, labels=labels, today=today,
                      week_count=len(week), week_cost=sum(i["cost"] for i in week), runs_out=runs_out,
                      has_channels=bool(chans))

    # --- fikir ve öneriler ---
    feedback_limiter = RateLimiter(limit=5, window=3600)
    FEEDBACK_KINDS = {"oneri": "Fikir / öneri", "istek": "Özellik isteği", "sorun": "Sorun bildir", "diger": "Diğer"}

    @app.get("/oneri", response_class=HTMLResponse)
    def feedback_page(request: Request, tur: str = ""):
        return render(request, "oneri.html", current_user(request), kinds=FEEDBACK_KINDS,
                      kind=tur if tur in FEEDBACK_KINDS else "oneri")

    @app.post("/oneri", dependencies=[Depends(check_csrf)])
    def feedback_send(request: Request, kind: str = Form("oneri"), message: str = Form(""), email: str = Form(""),
                      website: str = Form("")):
        user = current_user(request)
        back = i18n.localized_path("/oneri", public=tuple(PUBLIC_PAGES))
        message, email = clean(message, 2000), clean(email, 255).lower()
        if website:  # bot tuzağı (görünmez alan)
            return go(back)
        ip = request.client.host if request.client else "?"
        if len(message) < 5:
            flash(request, "Birkaç kelimeyle de olsa yaz lütfen.", "err")
            return go(back)
        if email and not EMAIL_RE.match(email):
            flash(request, "Geçerli bir e-posta yaz ya da boş bırak.", "err")
            return go(back)
        if not feedback_limiter.allow(f"f:{user.id if user else ip}"):
            flash(request, "Çok fazla mesaj gönderdin. Biraz sonra tekrar dene.", "err")
            return go(back)
        kind = kind if kind in FEEDBACK_KINDS else "diger"
        with db.session() as s:
            s.add(Feedback(user_id=user.id if user else None, email=user.email if user else email, kind=kind,
                           message=message, lang=i18n.current()))
        from html import escape

        html = mailer.render(f"Yeni {FEEDBACK_KINDS[kind].lower()}",
                             f"<b>{escape(user.email if user else email or 'Ziyaretçi')}</b> yazdı:<br><br>"
                             f"{escape(message)}", ("Önerileri gör", f"{site_url(request)}/admin/oneriler"), lang="tr")
        for to in sorted(config.ADMIN_EMAILS):
            try:
                mailer.send(to, f"{config.SITE_NAME}: yeni {FEEDBACK_KINDS[kind].lower()}", html)
            except Exception:
                log.exception("Öneri bildirimi gönderilemedi")
        flash(request, "Teşekkürler! Mesajın bize ulaştı; hepsini tek tek okuyoruz. 💛")
        return go(back)

    @app.get("/sablonlar", response_class=HTMLResponse)
    def templates_page(request: Request, kategori: str = ""):
        from . import sablonlar

        items = sablonlar.all_for(i18n.current())
        cats = {k: v for k, v in sablonlar.CATEGORIES.items() if any(t.category == k for t in items)}
        kategori = kategori if kategori in cats else ""
        return render(request, "sablonlar.html", current_user(request), items=items, cats=cats, kategori=kategori)

    @app.post("/video/yeni", dependencies=[Depends(check_csrf)])
    async def new_video(request: Request, user: User = Depends(require_user), idea: str = Form(""),
                        characters: str = Form(""), style: str = Form("cartoon"), language: str = Form("tr"),
                        quality: str = Form("fast"), ref: UploadFile | None = File(None), ref_keep: str = Form(""),
                        ref_remove: str = Form(""), subtitles: str = Form(""), cast: list[str] = Form([]),
                        subtitle_style: str = Form("viral"), seconds: int = Form(config.DEFAULT_SECONDS),
                        format: str = Form(""), background: str = Form(""), hook: str = Form(""),
                        progress: str = Form(""), voice: str = Form("")):
        if (blocked := require_verified(request, user)) is not None:
            return blocked
        quality = _valid_choice(quality, config.QUALITIES, "fast")
        ref_image = "" if ref_remove else await read_reference(request, ref, user.id, ref_keep)
        if ref_image is None:
            return go("/video/yeni")
        try:
            with db.session() as s:
                characters, ref_image = karakter.cast(s, user.id, cast, clean(characters), ref_image)
                job = worker.create_job(
                    s, user.id, idea=clean(idea), characters=characters,
                    style=_valid_choice(style, config.STYLES, "cartoon"),
                    language=_valid_choice(language, config.LANGUAGES, "tr"), quality=quality, ref_image=ref_image,
                    subtitles=bool(subtitles), subtitle_style=subtitle_style, seconds=seconds, format=format,
                    background=background, hook=bool(hook), progress=bool(progress), voice=voice)
                job_id = job.id
        except credits.NotEnoughCredits:
            flash(request, "Yeterli kredin yok. Bu video {n} kredi.", "err", n=config.price(quality, seconds))
            return go("/kredi")
        except abonelik.PlanRequired as e:
            return _plan_needed(request, e)
        return go(f"/video/{job_id}")

    @app.get("/videolar", response_class=HTMLResponse)
    def videos(request: Request, user: User = Depends(require_user), durum: str = "", q: str = "", sayfa: int = 1):
        per = 24
        groups = {"hazir": ["hazir"], "uretiliyor": ["sirada", "uretiliyor"], "hata": ["hata"]}
        durum = durum if durum in groups else ""
        q = clean(q, 80)
        with db.session() as s:
            base = select(Job).where(Job.user_id == user.id)
            counts = {k: s.scalar(select(func.count(Job.id)).where(Job.user_id == user.id, Job.status.in_(v)))
                      for k, v in groups.items()}
            counts[""] = sum(counts.values())
            if durum:
                base = base.where(Job.status.in_(groups[durum]))
            if q:
                base = base.where(or_(Job.title.ilike(f"%{q}%"), Job.idea.ilike(f"%{q}%")))
            total = s.scalar(select(func.count()).select_from(base.subquery()))
            pages = max(1, -(-total // per))
            sayfa = min(max(1, sayfa), pages)
            jobs = s.scalars(base.order_by(Job.id.desc()).offset((sayfa - 1) * per).limit(per)).all()
        return render(request, "videolar.html", user, jobs=jobs, durum=durum, q=q, sayfa=sayfa, pages=pages,
                      total=total, counts=counts)

    def _own_job(s, user: User, job_id: int) -> Job:
        job = s.get(Job, job_id)
        if not job or (job.user_id != user.id and not (user.is_admin and user.email_verified)):
            raise HTTPException(404)
        return job

    @app.get("/video/{job_id}", response_class=HTMLResponse)
    def job_page(request: Request, job_id: int, user: User = Depends(require_user)):
        with db.session() as s:
            job = _own_job(s, user, job_id)
            _ = job.channel  # şablonda kanal adı gösterilecek
            pubs = {p.platform: p for p in s.scalars(select(Publication).where(Publication.job_id == job.id))}
        return render(request, "video.html", user, job=job, pubs=pubs, linked=_linked(job.user_id),
                      platforms=social.PLATFORMS, has_srt=(worker.video_dir() / f"{job.id}.srt").exists())

    @app.post("/video/{job_id}/metin", dependencies=[Depends(check_csrf)])
    def job_text_edit(request: Request, job_id: int, user: User = Depends(require_user), title: str = Form(""),
                      caption: str = Form(""), hashtags: str = Form("")):
        """Paylaşım metnini elle düzenle (otomatik paylaşım da bu metni kullanır)."""
        tags = []
        for h in re.split(r"[\s,]+", hashtags):
            h = re.sub(r"[^\w]", "", h.lstrip("#"))[:40]
            if h and h.lower() not in (x.lower() for x in tags):
                tags.append(h)
        with db.session() as s:
            job = _own_job(s, user, job_id)
            if job.user_id != user.id or job.status != "hazir":
                raise HTTPException(404)
            job.title = clean(title, 100) or job.title
            job.caption = (caption or "").strip()[:2000]
            job.hashtags = " ".join(tags[:30])
        flash(request, "Paylaşım metni kaydedildi.")
        return go(f"/video/{job_id}")

    @app.post("/video/{job_id}/kesfet", dependencies=[Depends(check_csrf)])
    def job_public_toggle(request: Request, job_id: int, user: User = Depends(require_user)):
        with db.session() as s:
            job = _own_job(s, user, job_id)
            if job.user_id != user.id or job.status != "hazir":
                raise HTTPException(404)
            job.public = not job.public
            job.public_at = now() if job.public else None
            if not job.public:
                job.featured = False
            public = job.public
        flash(request, "Videon Keşfet'te yayında. 🌟" if public else "Video Keşfet'ten kaldırıldı.")
        return go(f"/video/{job_id}")

    @app.post("/video/{job_id}/tekrar", dependencies=[Depends(check_csrf)])
    def job_again(request: Request, job_id: int, user: User = Depends(require_user)):
        """Aynı ayarlarla yeni bir video (yapay zekâ önceki fikirleri tekrar etmez)."""
        if (blocked := require_verified(request, user)) is not None:
            return blocked
        with db.session() as s:
            old = _own_job(s, user, job_id)
            if old.user_id != user.id:
                raise HTTPException(404)
            params = dict(idea=old.idea, characters=old.characters, style=old.style, language=old.language,
                          quality=old.quality, ref_image=old.ref_image, subtitles=old.subtitles,
                          subtitle_style=old.subtitle_style, seconds=old.seconds, format=old.format,
                          background=old.background, hook=old.hook, progress=old.progress, voice=old.voice)
        try:
            with db.session() as s:
                new_id = worker.create_job(s, user.id, **params).id
        except credits.NotEnoughCredits:
            flash(request, "Yeterli kredin yok. Bu video {n} kredi.", "err",
                  n=config.price(params["quality"], params["seconds"]))
            return go("/kredi")
        except abonelik.PlanRequired as e:
            return _plan_needed(request, e)
        return go(f"/video/{new_id}")

    def _plan_needed(request: Request, e: "abonelik.PlanRequired"):
        if isinstance(e, abonelik.VideoOff):
            flash(request, "Yapay zekâ videosu şu an kapalı. Viral formatlardan birini seç.", "warn")
            return go("/video/yeni?format=quiz")
        flash(request, "{quality} yapay zekâsı {plan} aboneliğinde. Aboneliğini seçip havaleni bildirince açılır.",
              "warn", quality=i18n.t(config.QUALITIES[e.quality]["label"]), plan=i18n.t(config.PLANS[e.plan]["label"]))
        return go("/abonelik")

    def _generator(request: Request):
        gen = request.app.state.generator
        if gen is None:
            gen = request.app.state.generator = (getattr(request.app.state, "worker", None) and
                                                 request.app.state.worker.generator) or ai_mod.default_ai()
        return gen

    trial_limiter = RateLimiter(limit=6, window=3600)  # ziyaretçi başına saatte 6 deneme
    trial_daily: dict = {}  # gün → sayı (toplam günlük sınır: maliyet tavanı)

    @app.post("/api/deneme-senaryo", dependencies=[Depends(check_csrf)])
    def trial_script(request: Request, idea: str = Form(""), language: str = Form("")):
        """Kayıt olmadan deneme: fikirden okunacak kısa senaryo (yalnızca ucuz metin modeli, video yok)."""
        from datetime import date

        idea = clean(idea, 200)
        lang = _valid_choice(language or i18n.current(), config.LANGUAGES, "tr")
        if len(idea) < 3:
            return JSONResponse({"error": i18n.t("Önce bir fikir yaz.")}, status_code=400)
        ip = request.client.host if request.client else "?"
        today = date.today().isoformat()
        if not trial_limiter.allow(f"t:{ip}") or trial_daily.get(today, 0) >= config.TRIAL_DAILY_LIMIT:
            return JSONResponse({"error": i18n.t("Deneme sınırına ulaştın. Ücretsiz kaydolup devam edebilirsin.")},
                                status_code=429)
        if today not in trial_daily:  # yeni gün: sayaç sıfırlanır
            trial_daily.clear()
        trial_daily[today] = trial_daily.get(today, 0) + 1
        try:
            prev = _generator(request).preview(idea=idea, language=lang)
        except Exception:
            log.exception("Deneme senaryosu yazılamadı")
            return JSONResponse({"error": i18n.t("Şu an senaryo yazılamadı, biraz sonra tekrar dene.")}, status_code=503)
        from urllib.parse import quote

        user = current_user(request)
        start = f"/video/yeni?idea={quote(idea)}" if user else \
            i18n.localized_path("/kayit", public=tuple(PUBLIC_PAGES)) + f"?fikir={quote(idea)}"
        import json
        import secrets

        code = secrets.token_urlsafe(6)  # paylaşım bağlantısı (tahmin edilemez)
        with db.session() as s:
            s.add(SharedScript(code=code, idea=idea, lang=lang, data=json.dumps(prev, ensure_ascii=False)))
        return {"preview": prev, "start": start, "demo": config.FAKE_AI, "share": f"{site_url(request)}/s/{code}"}

    @app.get("/s/{code}", response_class=HTMLResponse)
    def shared_script(request: Request, code: str):
        """Paylaşılan deneme senaryosu: telefonda oynayan senaryo + "Sen de dene"."""
        import json
        from urllib.parse import quote

        if not re.fullmatch(r"[A-Za-z0-9_-]{4,12}", code):
            raise HTTPException(404)
        with db.session() as s:
            row = s.scalar(select(SharedScript).where(SharedScript.code == code))
            if not row:
                raise HTTPException(404)
            row.views += 1
            prev, idea = json.loads(row.data), row.idea
        user = current_user(request)
        start = f"/video/yeni?idea={quote(idea)}" if user else \
            i18n.localized_path("/kayit", public=tuple(PUBLIC_PAGES)) + f"?fikir={quote(idea)}"
        return render(request, "senaryo.html", user, p=prev, idea=idea, start=start,
                      share=f"{site_url(request)}/s/{code}")

    @app.get("/fiyatlar", response_class=HTMLResponse)
    def pricing_page(request: Request):
        faqs = [f for f in FAQS if any(w in f[0] for w in ("Abonelik", "saniye", "Kredi", "kredim", "beğenmezsem"))]
        return render(request, "fiyatlar.html", current_user(request), faqs=faqs)

    # --- ücretsiz araçlar (kayıt gerekmez; deneme sınırı ve günlük maliyet tavanı ortak) ---
    def _tool_allowed(request: Request, prefix: str) -> bool:
        from datetime import date

        ip = request.client.host if request.client else "?"
        today = date.today().isoformat()
        if not trial_limiter.allow(f"{prefix}:{ip}") or trial_daily.get(today, 0) >= config.TRIAL_DAILY_LIMIT:
            return False
        if today not in trial_daily:  # yeni gün: sayaç sıfırlanır
            trial_daily.clear()
        trial_daily[today] = trial_daily.get(today, 0) + 1
        return True

    def _start_link(request: Request, idea: str) -> str:
        """Araçtan videoya: girişliyse video formu fikirle açılır, değilse kayıt (fikir kayıttan sonra gelir)."""
        from urllib.parse import quote

        return f"/video/yeni?idea={quote(idea)}" if current_user(request) else \
            i18n.localized_path("/kayit", public=tuple(PUBLIC_PAGES)) + f"?fikir={quote(idea)}"

    @app.get("/araclar", response_class=HTMLResponse)
    def tools_page(request: Request):
        return render(request, "araclar.html", current_user(request))

    @app.get("/araclar/kanal-kurucu", response_class=HTMLResponse)
    def channel_tool(request: Request):
        return render(request, "kanal_kurucu.html", current_user(request))

    @app.get("/araclar/kanca-uretici", response_class=HTMLResponse)
    def hook_tool(request: Request):
        return render(request, "arac.html", current_user(request), tool="kanca")

    @app.get("/araclar/baslik-uretici", response_class=HTMLResponse)
    def title_tool(request: Request):
        return render(request, "arac.html", current_user(request), tool="baslik")

    @app.post("/api/kancalar", dependencies=[Depends(check_csrf)])
    def hooks_api(request: Request, topic: str = Form(""), language: str = Form("")):
        topic = clean(topic, 160)
        lang = _valid_choice(language or i18n.current(), config.LANGUAGES, "tr")
        if len(topic) < 2:
            return JSONResponse({"error": i18n.t("Önce videonun konusunu yaz.")}, status_code=400)
        if not _tool_allowed(request, "h"):
            return JSONResponse({"error": i18n.t("Deneme sınırına ulaştın. Ücretsiz kaydolup devam edebilirsin.")},
                                status_code=429)
        try:
            hooks = _generator(request).hooks(topic=topic, language=lang)
        except Exception:
            log.exception("Kanca yazılamadı")
            return JSONResponse({"error": i18n.t("Şu an yazılamadı, biraz sonra tekrar dene.")}, status_code=503)
        labels = {k: i18n.t(v) for k, v in ai_mod.HOOK_TYPES.items()}
        return {"hooks": [{"type": labels[h["type"]], "text": h["text"],
                           "start": _start_link(request, f"{h['text']} ({topic})")} for h in hooks]}

    @app.post("/api/basliklar", dependencies=[Depends(check_csrf)])
    def titles_api(request: Request, topic: str = Form(""), language: str = Form("")):
        topic = clean(topic, 160)
        lang = _valid_choice(language or i18n.current(), config.LANGUAGES, "tr")
        if len(topic) < 2:
            return JSONResponse({"error": i18n.t("Önce videonun konusunu yaz.")}, status_code=400)
        if not _tool_allowed(request, "b"):
            return JSONResponse({"error": i18n.t("Deneme sınırına ulaştın. Ücretsiz kaydolup devam edebilirsin.")},
                                status_code=429)
        try:
            out = _generator(request).titles(topic=topic, language=lang)
        except Exception:
            log.exception("Başlık yazılamadı")
            return JSONResponse({"error": i18n.t("Şu an yazılamadı, biraz sonra tekrar dene.")}, status_code=503)
        return {**out, "start": _start_link(request, topic)}

    @app.post("/api/kanal-plani", dependencies=[Depends(check_csrf)])
    def channel_plan_api(request: Request, topic: str = Form(""), language: str = Form("")):
        from datetime import date
        from urllib.parse import urlencode

        topic = clean(topic, 120)
        lang = _valid_choice(language or i18n.current(), config.LANGUAGES, "tr")
        if len(topic) < 2:
            return JSONResponse({"error": i18n.t("Önce kanalın konusunu yaz.")}, status_code=400)
        ip = request.client.host if request.client else "?"
        today = date.today().isoformat()
        if not trial_limiter.allow(f"k:{ip}") or trial_daily.get(today, 0) >= config.TRIAL_DAILY_LIMIT:
            return JSONResponse({"error": i18n.t("Deneme sınırına ulaştın. Ücretsiz kaydolup devam edebilirsin.")},
                                status_code=429)
        if today not in trial_daily:
            trial_daily.clear()
        trial_daily[today] = trial_daily.get(today, 0) + 1
        try:
            plan = _generator(request).channel_plan(topic=topic, language=lang)
        except Exception:
            log.exception("Kanal planı yazılamadı")
            return JSONResponse({"error": i18n.t("Şu an plan yazılamadı, biraz sonra tekrar dene.")}, status_code=503)
        name = plan["names"][0] if plan["names"] else topic
        konu = topic + (f". {plan['character']}" if plan["character"] else "")
        q = {"ad": name, "konu": konu, "saatler": " ".join(plan["times"])}
        start = "/kanallar/yeni?" + urlencode(q) if current_user(request) else \
            i18n.localized_path("/kayit", public=tuple(PUBLIC_PAGES)) + "?" + urlencode(
                {"kanal_ad": name, "kanal_konu": konu, "kanal_saat": " ".join(plan["times"])})
        return {"plan": plan, "start": start, "demo": config.FAKE_AI}

    idea_limiter = RateLimiter(limit=12, window=600)

    @app.post("/api/fikirler", dependencies=[Depends(check_csrf)])
    def ideas_api(request: Request, user: User = Depends(require_user), topic: str = Form(""),
                  language: str = Form("tr")):
        if not idea_limiter.allow(f"i:{user.id}"):
            return JSONResponse({"error": i18n.t("Çok fazla fikir istedin, birkaç dakika sonra tekrar dene.")},
                                status_code=429)
        with db.session() as s:
            past = [t for t in s.scalars(select(Job.title).where(Job.user_id == user.id, Job.title != "")
                                         .order_by(Job.id.desc()).limit(20)) if t]
        gen = _generator(request)
        try:
            ideas = gen.ideas(topic=clean(topic, 300), language=_valid_choice(language, config.LANGUAGES, "tr"),
                              past=past)
        except Exception:
            log.exception("Fikir üretilemedi")
            return JSONResponse({"error": i18n.t("Şu an fikir üretilemedi, biraz sonra tekrar dene.")}, status_code=503)
        return {"ideas": [clean(i, 200) for i in ideas][:4]}

    @app.get("/referans/{uid}/{name}")
    def reference_image(uid: int, name: str, user: User = Depends(require_user)):
        path = media.ref_path(f"{uid}/{name}")
        if (uid != user.id and not (user.is_admin and user.email_verified)) or not path:
            raise HTTPException(404)
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=86400"})

    @app.get("/video/{job_id}/durum")
    def job_status(job_id: int, user: User = Depends(require_user)):
        with db.session() as s:
            job = _own_job(s, user, job_id)
        stage = f"{job.status}:{bool(job.prompt)}"
        return JSONResponse({"status": job.status, "label": i18n.t(STATUS_LABELS.get(job.status, job.status)),
                             "stage": stage})

    @app.get("/video/{job_id}/dosya")
    def job_file(job_id: int, indir: int = 0, ham: int = 0, user: User = Depends(require_user)):
        with db.session() as s:
            job = _own_job(s, user, job_id)
        name_ = job.raw_file if ham and job.raw_file else job.video_file
        path = worker.video_dir() / name_ if name_ else None
        if job.status != "hazir" or not path or not path.exists():
            raise HTTPException(404)
        name = (f"video-{job.id}-altyazisiz.mp4" if ham and job.raw_file else f"video-{job.id}.mp4") if indir else None
        return FileResponse(path, media_type="video/mp4", filename=name)

    @app.get("/video/{job_id}/altyazi.srt")
    def job_srt(job_id: int, user: User = Depends(require_user)):
        """Altyazı dosyası: platformlara ayrıca yüklenebilir ya da başka düzenleyicide kullanılır."""
        with db.session() as s:
            job = _own_job(s, user, job_id)
        path = worker.video_dir() / f"{job.id}.srt"
        if job.status != "hazir" or not path.exists():
            raise HTTPException(404)
        return FileResponse(path, media_type="application/x-subrip", filename=f"video-{job.id}.srt")

    voice_sample_limiter = RateLimiter(limit=20, window=600)

    @app.get("/ses-ornek/{name}")
    def voice_sample(request: Request, name: str, user: User = Depends(require_user)):
        """Seçilebilen sesin kısa örneği. Bir kez üretilip saklanır (seslendirme hakkı boşa gitmesin)."""
        if name not in ai_mod.VOICE_PRESETS:
            raise HTTPException(404)
        _g, _label, voice, _gender, style = ai_mod.VOICE_PRESETS[name]
        lang = "en" if i18n.current() == "en" else "tr"
        folder = config.DATA_DIR / "ses_ornekleri"
        path = folder / f"{name}-{lang}-2.wav"  # -2: doğal okuma notlu sürüm
        if not path.exists():
            if not voice_sample_limiter.allow(f"v:{user.id}"):
                return JSONResponse({"error": i18n.t("Çok fazla deneme, birkaç dakika sonra tekrar dene.")}, status_code=429)
            folder.mkdir(parents=True, exist_ok=True)
            text = ("Hi! I can narrate your next video. Ready when you are." if lang == "en" else
                    "Selam! Bir sonraki videonu ben seslendirebilirim. Hazırsan başlayalım.")
            try:
                _generator(request).speak(text=text, voice=voice, out=path, style=style)
            except Exception:
                log.exception("Ses örneği üretilemedi")
                path.unlink(missing_ok=True)
                return JSONResponse({"error": i18n.t("Ses örneği şu an hazırlanamadı, biraz sonra tekrar dene.")},
                                    status_code=503)
        return FileResponse(path, media_type="audio/wav", headers={"Cache-Control": "private, max-age=86400"})

    @app.get("/video/{job_id}/kapak")
    def job_poster(job_id: int, user: User = Depends(require_user)):
        with db.session() as s:
            job = _own_job(s, user, job_id)
        if job.status != "hazir" or not job.video_file:
            raise HTTPException(404)
        video = worker.video_dir() / job.video_file
        poster = video.with_suffix(".jpg")
        if not poster.exists() and video.exists():
            worker.make_poster(video)
        if not poster.exists():
            raise HTTPException(404)
        return FileResponse(poster, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})

    # --- hesap ---
    @app.get("/hesap", response_class=HTMLResponse)
    def account_page(request: Request, user: User = Depends(require_user)):
        return render(request, "hesap.html", user)

    @app.post("/hesap/profil", dependencies=[Depends(check_csrf)])
    def account_profile(request: Request, user: User = Depends(require_user), name: str = Form(""),
                        notify: str = Form("")):
        with db.session() as s:
            u = s.get(User, user.id)
            u.name = clean(name, 100)
            u.notify = bool(notify)
        flash(request, "Bilgilerin kaydedildi.")
        return go("/hesap")

    @app.post("/hesap/sifre", dependencies=[Depends(check_csrf)])
    def account_password(request: Request, user: User = Depends(require_user), current: str = Form(""),
                         password: str = Form(...), password2: str = Form(...)):
        if user.pw_hash and not check_password(current, user.pw_hash):
            flash(request, "Mevcut şifren yanlış.", "err")
            return go("/hesap")
        if len(password) < 8 or password != password2:
            flash(request, "Yeni şifreler aynı olmalı ve en az 8 karakter olmalı.", "err")
            return go("/hesap")
        with db.session() as s:
            u = s.get(User, user.id)
            u.pw_hash = hash_password(password)
            request.session["pv"] = _pw_mark(u)  # bu oturum açık kalır, diğer cihazlar çıkış yapar
        flash(request, "Şifren güncellendi. 🔐")
        return go("/hesap")

    @app.post("/hesap/sil", dependencies=[Depends(check_csrf)])
    def account_delete(request: Request, user: User = Depends(require_user), confirm: str = Form("")):
        if confirm.strip().lower() != user.email:
            flash(request, "Silmek için e-posta adresini aynen yazmalısın.", "err")
            return go("/hesap")
        with db.session() as s:
            u = s.get(User, user.id)
            for row in [*s.scalars(select(Channel).where(Channel.user_id == u.id)), *karakter.for_user(s, u.id)]:
                s.delete(row)
            for job in s.scalars(select(Job).where(Job.user_id == u.id)):
                for ext in (".mp4", ".jpg", "-ham.mp4", ".srt"):
                    f = worker.video_dir() / f"{job.id}{ext}"
                    if f.exists():
                        f.unlink()
                job.channel_id = None
                job.idea = job.characters = job.prompt = job.title = job.caption = job.hashtags = job.summary = ""
                job.ref_image = job.raw_file = ""
                job.public = job.featured = False
                job.video_file = ""
            # bağlı hesap jetonları ve paylaşım kayıtları (sıradakiler de yüklenmesin)
            for row in [*s.scalars(select(SocialAccount).where(SocialAccount.user_id == u.id)),
                        *s.scalars(select(Publication).where(Publication.user_id == u.id))]:
                s.delete(row)
            # muhasebe kayıtları (ödeme/kredi hareketleri) yasal süre boyunca kalır; kişisel bilgiler silinir
            u.email = f"silindi-{u.id}@silindi.invalid"
            u.name, u.pw_hash, u.google_sub, u.notify, u.email_verified, u.is_admin = "", "", None, False, False, False
        media.delete_user_media(user.id)
        request.session.clear()
        flash(request, "Hesabın ve videoların silindi. Görüşmek üzere. 👋")
        return go("/")

    # --- karakter kütüphanesi ---
    def _cast_ctx(user_id: int, selected) -> dict:
        with db.session() as s:
            mine = karakter.for_user(s, user_id)
        return {"my_chars": mine, "sel_chars": set(karakter.parse_ids(selected)), "cast_max": karakter.MAX_PER_VIDEO}

    def _own_character(s, user: User, cid: int) -> Character:
        c = s.get(Character, cid)
        if not c or c.user_id != user.id:
            raise HTTPException(404)
        return c

    def _character_from_form(form) -> dict:
        return dict(name=clean(form.get("name", ""), 60), look=clean(form.get("look", ""), 600),
                    voice=clean(form.get("voice", ""), 300))

    @app.get("/karakterler", response_class=HTMLResponse)
    def characters_page(request: Request, user: User = Depends(require_user), duzenle: int = 0):
        with db.session() as s:
            chars = karakter.for_user(s, user.id)
            edit = _own_character(s, user, duzenle) if duzenle else None
        counts: dict[int, int] = {}
        with db.session() as s:
            for ch in s.scalars(select(Channel).where(Channel.user_id == user.id)):
                for cid in karakter.parse_ids(ch.cast_ids):
                    counts[cid] = counts.get(cid, 0) + 1
        return render(request, "karakterler.html", user, chars=chars, edit=edit, used=counts,
                      limit=karakter.MAX_PER_USER)

    @app.post("/karakterler", dependencies=[Depends(check_csrf)])
    async def character_save(request: Request, user: User = Depends(require_user)):
        """Yeni karakter kaydeder ya da (id varsa) mevcut karakteri günceller."""
        form = await request.form()
        data = _character_from_form(form)
        cid = int(form.get("id") or 0) if str(form.get("id") or "0").isdigit() else 0
        back = f"/karakterler?duzenle={cid}" if cid else "/karakterler"
        if not data["name"]:
            flash(request, "Karaktere bir ad ver.", "err")
            return go(back)
        if not data["look"] and not data["voice"]:
            flash(request, "Karakterin görünüşünü ya da sesini anlat.", "err")
            return go(back)
        with db.session() as s:
            current = _own_character(s, user, cid).ref_image if cid else ""
            if not cid and s.scalar(select(func.count(Character.id)).where(Character.user_id == user.id)) \
                    >= karakter.MAX_PER_USER:
                flash(request, "En fazla {n} karakter kaydedebilirsin.", "err", n=karakter.MAX_PER_USER)
                return go("/karakterler")
        ref_image = "" if form.get("ref_remove") else await read_reference(request, form.get("ref"), user.id, current)
        if ref_image is None:
            return go(back)
        with db.session() as s:
            if cid:
                c = _own_character(s, user, cid)
                for k, v in data.items():
                    setattr(c, k, v)
                c.ref_image = ref_image
            else:
                s.add(Character(user_id=user.id, ref_image=ref_image, **data))
        flash(request, "Karakter kaydedildi. Artık videolarında ve kanallarında seçebilirsin." if not cid else
              "Karakter güncellendi. Kanallarının sonraki videoları yeni hâlini kullanır.")
        return go("/karakterler")

    @app.post("/karakterler/{cid}/sil", dependencies=[Depends(check_csrf)])
    def character_delete(request: Request, cid: int, user: User = Depends(require_user)):
        with db.session() as s:
            s.delete(_own_character(s, user, cid))
            for ch in s.scalars(select(Channel).where(Channel.user_id == user.id, Channel.cast_ids != "")):
                ch.cast_ids = " ".join(str(i) for i in karakter.parse_ids(ch.cast_ids) if i != cid)
        flash(request, "Karakter silindi.")
        return go("/karakterler")

    # --- kanallar ---
    def _channel_from_form(form) -> dict:
        times = [t for t in str(form.get("times", "")).replace(",", " ").split() if TIME_RE.match(t)]
        return dict(
            name=clean(form.get("name", ""), 100) or i18n.t("Kanalım"),
            characters=clean(form.get("characters", "")), topic=clean(form.get("topic", "")),
            style=_valid_choice(form.get("style", ""), config.STYLES, "cartoon"),
            language=_valid_choice(form.get("language", ""), config.LANGUAGES, "tr"),
            quality=_valid_choice(form.get("quality", ""), config.QUALITIES, "fast"),
            times=" ".join(sorted(set(times), key=lambda t: (int(t.split(":")[0]), t)))[:200] or "12:00",
            subtitles=bool(form.get("subtitles")),
            seconds=config.clamp_seconds(form.get("seconds", config.DEFAULT_SECONDS)),
            format=str(form.get("format", "")) if form.get("format") in formatlar.FORMATS else "",
            background=str(form.get("background", ""))[:40] if form.get("background") in formatlar.background_choices() else "",
            subtitle_style=_valid_choice(str(form.get("subtitle_style", "")), media.SUB_STYLES, ""),
            publish_to=" ".join(p for p in social.PLATFORMS if form.get(f"pub_{p}")),
            approval=form.get("approval") == "1",
            hook=bool(form.get("hook")) and not form.get("format"), progress=bool(form.get("progress")),
            voice=str(form.get("voice", "")) if form.get("format") and ai_mod.valid_voice(str(form.get("voice", ""))) else "",
        )

    @app.get("/kanallar", response_class=HTMLResponse)
    def channels(request: Request, user: User = Depends(require_user)):
        with db.session() as s:
            chans = s.scalars(select(Channel).where(Channel.user_id == user.id).order_by(Channel.id)).all()
        return render(request, "kanallar.html", user, channels=chans, linked=_linked(user.id))

    def _linked(user_id: int) -> dict:
        with db.session() as s:
            return {p: a.name for p, a in publisher.accounts(s, user_id).items()}

    @app.get("/kanallar/yeni", response_class=HTMLResponse)
    def channel_new_page(request: Request, sablon: str = "", ad: str = "", konu: str = "", saatler: str = "",
                         user: User = Depends(require_user)):
        from types import SimpleNamespace

        from . import sablonlar

        t = sablonlar.get(sablon, i18n.current()) if sablon else None
        tpl = sablonlar.as_channel(t, i18n.current()) if t else None
        if not tpl and konu:  # kanal kurucudan: ad, konu ve önerilen saatler dolu gelsin
            times = " ".join(x for x in saatler.split() if TIME_RE.match(x)) or "12:00 19:00"
            tpl = SimpleNamespace(id=None, name=clean(ad, 100), topic=clean(konu, 600), characters="", style="cartoon",
                                  language=i18n.current(), quality="fast", times=times, subtitles=True,
                                  subtitle_style="viral", publish_to="", ref_image="", active=True, idea="", title="",
                                  seconds=config.DEFAULT_SECONDS, approval=False, hook=True, progress=False, voice="")
        request.session.pop("kanal", None)
        return render(request, "kanal_form.html", user, ch=None, linked=_linked(user.id), platforms=social.PLATFORMS,
                      tpl=tpl, tpl_name=t.name if t else "", **_cast_ctx(user.id, []))

    @app.post("/kanallar/yeni", dependencies=[Depends(check_csrf)])
    async def channel_new(request: Request, user: User = Depends(require_user)):
        if (blocked := require_verified(request, user)) is not None:
            return blocked
        form = await request.form()
        data = _channel_from_form(form)
        if not data["format"] and config.VIDEO_OFF:
            return _plan_needed(request, abonelik.VideoOff())
        if not data["format"] and data["quality"] not in abonelik.allowed(user):
            return _plan_needed(request, abonelik.PlanRequired(data["quality"]))
        ref_image = await read_reference(request, form.get("ref"), user.id)
        if ref_image is None:
            return go("/kanallar/yeni")
        data["ref_image"] = ref_image
        with db.session() as s:
            data["cast_ids"] = karakter.ids_text(karakter.owned(s, user.id, form.getlist("cast")))
            if s.scalar(select(func.count(Channel.id)).where(Channel.user_id == user.id)) >= 10:
                flash(request, "En fazla 10 kanal açabilirsin.", "err")
                return go("/kanallar")
            s.add(Channel(user_id=user.id, **data))
        flash(request, "Kanal oluşturuldu. Saati gelince videolar kendiliğinden üretilecek. 🚀")
        return go("/kanallar")

    def _own_channel(s, user: User, cid: int) -> Channel:
        ch = s.get(Channel, cid)
        if not ch or ch.user_id != user.id:
            raise HTTPException(404)
        return ch

    @app.get("/kanallar/{cid}", response_class=HTMLResponse)
    def channel_edit_page(request: Request, cid: int, user: User = Depends(require_user)):
        with db.session() as s:
            ch = _own_channel(s, user, cid)
            jobs = s.scalars(select(Job).where(Job.channel_id == cid).order_by(Job.id.desc()).limit(30)).all()
        return render(request, "kanal_form.html", user, ch=ch, jobs=jobs, linked=_linked(user.id),
                      platforms=social.PLATFORMS, **_cast_ctx(user.id, ch.cast_ids))

    @app.post("/kanallar/{cid}", dependencies=[Depends(check_csrf)])
    async def channel_edit(request: Request, cid: int, user: User = Depends(require_user)):
        form = await request.form()
        data = _channel_from_form(form)
        if not data["format"] and config.VIDEO_OFF:
            return _plan_needed(request, abonelik.VideoOff())
        if not data["format"] and data["quality"] not in abonelik.allowed(user):
            return _plan_needed(request, abonelik.PlanRequired(data["quality"]))
        with db.session() as s:
            current = _own_channel(s, user, cid).ref_image
        ref_image = "" if form.get("ref_remove") else await read_reference(request, form.get("ref"), user.id, current)
        if ref_image is None:
            return go(f"/kanallar/{cid}")
        data["ref_image"] = ref_image
        with db.session() as s:
            ch = _own_channel(s, user, cid)
            data["cast_ids"] = karakter.ids_text(karakter.owned(s, user.id, form.getlist("cast")))
            for k, v in data.items():
                setattr(ch, k, v)
        flash(request, "Kanal kaydedildi.")
        return go(f"/kanallar/{cid}")

    @app.post("/kanallar/{cid}/durum", dependencies=[Depends(check_csrf)])
    def channel_toggle(request: Request, cid: int, user: User = Depends(require_user)):
        with db.session() as s:
            ch = _own_channel(s, user, cid)
            ch.active = not ch.active
            ch.notice = ""
            active = ch.active
        flash(request, "Kanal açıldı." if active else "Kanal durduruldu.")
        return go("/kanallar")

    # --- otomatik paylaşım: hesap bağlantıları ---
    def _connect_redirect(request: Request, platform: str) -> str:
        return f"{site_url(request)}/baglan/{platform}/donus"

    @app.get("/baglantilar", response_class=HTMLResponse)
    def connections(request: Request, user: User = Depends(require_user)):
        with db.session() as s:
            accs = publisher.accounts(s, user.id)
            recent = s.scalars(select(Publication).where(Publication.user_id == user.id)
                               .options(selectinload(Publication.job))
                               .order_by(Publication.id.desc()).limit(20)).all()
        info = {p: {**meta, "available": social.available(p), "demo": social.demo(p), "account": accs.get(p)}
                for p, meta in social.PLATFORMS.items()}
        return render(request, "baglantilar.html", user, info=info, recent=recent)

    @app.get("/baglan/{platform}")
    def connect_start(request: Request, platform: str, user: User = Depends(require_user)):
        if platform not in social.PLATFORMS or not social.available(platform):
            flash(request, "Bu platform henüz ayarlanmadı.", "warn")
            return go("/baglantilar")
        state = secrets.token_urlsafe(24)
        request.session["s_state"] = f"{platform}:{state}"
        return RedirectResponse(social.client(platform).auth_url(_connect_redirect(request, platform), state),
                                status_code=303)

    @app.get("/baglan/{platform}/donus")
    def connect_callback(request: Request, platform: str, code: str = "", state: str = "", error: str = "",
                         user: User = Depends(require_user)):
        expected = request.session.pop("s_state", "")
        if (platform not in social.PLATFORMS or error or not code
                or not secrets.compare_digest(f"{platform}:{state}", expected)):
            flash(request, "Bağlantı tamamlanmadı, tekrar dene.", "err")
            return go("/baglantilar")
        try:
            acc = social.client(platform).exchange(code, _connect_redirect(request, platform))
        except Exception as e:
            log.exception("%s bağlantısı başarısız", platform)
            flash(request, str(e) if isinstance(e, social.PublishError) else "Platform şu an yanıt vermedi.", "err")
            return go("/baglantilar")
        from datetime import timedelta

        with db.session() as s:
            row = s.scalar(select(SocialAccount).where(SocialAccount.user_id == user.id, SocialAccount.platform == platform))
            if not row:
                row = SocialAccount(user_id=user.id, platform=platform)
                s.add(row)
            row.name, row.remote_id = acc.name[:120], acc.remote_id[:120]
            row.access_enc, row.refresh_enc = secretbox.seal(acc.access), secretbox.seal(acc.refresh)
            row.expires_at = now() + timedelta(seconds=acc.expires_in) if acc.expires_in else None
        flash(request, "{platform} bağlandı: {name} ✅", platform=i18n.t(social.PLATFORMS[platform]["label"]), name=acc.name)
        return go("/baglantilar")

    @app.post("/baglanti/{platform}/kaldir", dependencies=[Depends(check_csrf)])
    def connect_remove(request: Request, platform: str, user: User = Depends(require_user)):
        with db.session() as s:
            row = s.scalar(select(SocialAccount).where(SocialAccount.user_id == user.id, SocialAccount.platform == platform))
            if row:
                s.delete(row)
        flash(request, "Bağlantı kaldırıldı.")
        return go("/baglantilar")

    @app.post("/video/{job_id}/yayinla/{platform}", dependencies=[Depends(check_csrf)])
    def publish_now(request: Request, job_id: int, platform: str, user: User = Depends(require_user)):
        with db.session() as s:
            job = _own_job(s, user, job_id)
            if job.user_id != user.id or job.status != "hazir":
                raise HTTPException(404)
            added = publisher.queue(s, job, [platform])
        flash(request, "Paylaşım sıraya alındı; birkaç dakika içinde yüklenecek." if added else
              "Bu platform bağlı değil ya da video zaten gönderildi.", "ok" if added else "warn")
        return go(f"/video/{job_id}")

    @app.post("/video/{job_id}/onayla", dependencies=[Depends(check_csrf)])
    def publish_approve(request: Request, job_id: int, user: User = Depends(require_user)):
        """Onaylı kanal videosu: kullanıcı izleyip onaylayınca bağlı hesaplara yüklenir."""
        with db.session() as s:
            job = _own_job(s, user, job_id)
            if job.user_id != user.id:  # yönetici başkası adına onaylayamaz
                raise HTTPException(404)
            n = publisher.approve(s, job.id) if job.status == "hazir" else 0
        flash(request, "Onaylandı; video birkaç dakika içinde yüklenecek. 🚀" if n else
              "Onay bekleyen paylaşım yok.", "ok" if n else "warn")
        return go(f"/video/{job_id}")

    @app.post("/video/{job_id}/paylasma", dependencies=[Depends(check_csrf)])
    def publish_reject(request: Request, job_id: int, user: User = Depends(require_user)):
        with db.session() as s:
            job = _own_job(s, user, job_id)
            if job.user_id != user.id:
                raise HTTPException(404)
            n = publisher.reject(s, job.id)
        flash(request, "Tamam, bu video hiçbir yere yüklenmeyecek." if n else "Onay bekleyen paylaşım yok.",
              "ok" if n else "warn")
        return go(f"/video/{job_id}")

    @app.post("/yayin/{pid}/tekrar", dependencies=[Depends(check_csrf)])
    def publish_retry(request: Request, pid: int, user: User = Depends(require_user)):
        with db.session() as s:
            pub = s.get(Publication, pid)
            if not pub or pub.user_id != user.id:
                raise HTTPException(404)
            if pub.status == "hata":
                pub.status, pub.error, pub.attempts = "bekliyor", "", 0
            job_id = pub.job_id
        flash(request, "Paylaşım tekrar sıraya alındı.")
        return go(f"/video/{job_id}")

    @app.get("/yayin/dosya/{token}")
    def publish_media(token: str):
        """Instagram'ın videoyu indirdiği süreli imzalı adres (giriş gerektirmez)."""
        job_id = tokens.read_media(token)
        with db.session() as s:
            job = s.get(Job, job_id) if job_id else None
        if not job or job.status != "hazir" or not job.video_file:
            raise HTTPException(404)
        return FileResponse(worker.video_dir() / job.video_file, media_type="video/mp4")

    @app.post("/kanallar/{cid}/simdi", dependencies=[Depends(check_csrf)])
    def channel_now(request: Request, cid: int, user: User = Depends(require_user)):
        """Saatini beklemeden kanal ayarlarıyla hemen bir video üretir."""
        if (blocked := require_verified(request, user)) is not None:
            return blocked
        with db.session() as s:
            params = worker.channel_params(s, _own_channel(s, user, cid))
        slot = "elle " + datetime.now(ZoneInfo(config.TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S.%f")
        try:
            with db.session() as s:
                new_id = worker.create_job(s, user.id, slot=slot, **params).id
        except credits.NotEnoughCredits:
            flash(request, "Yeterli kredin yok.", "err")
            return go("/kredi")
        except abonelik.PlanRequired as e:
            return _plan_needed(request, e)
        return go(f"/video/{new_id}")

    @app.post("/kanallar/{cid}/sil", dependencies=[Depends(check_csrf)])
    def channel_delete(request: Request, cid: int, user: User = Depends(require_user)):
        with db.session() as s:
            ch = _own_channel(s, user, cid)
            for job in s.scalars(select(Job).where(Job.channel_id == cid)):
                job.channel_id = None
            s.delete(ch)
        flash(request, "Kanal silindi. Üretilmiş videoların panelde duruyor.")
        return go("/kanallar")

    # --- kredi ---
    @app.get("/kredi", response_class=HTMLResponse)
    def credit_page(request: Request, user: User = Depends(require_user), plan: str = ""):
        if plan in config.PLANS:  # eski bağlantılar: abonelik ödemesi artık Abonelikler sayfasında
            return go(f"/abonelik?plan={plan}#odeme")
        with db.session() as s:
            txs = s.scalars(select(CreditTx).where(CreditTx.user_id == user.id).order_by(CreditTx.id.desc())
                            .limit(50)).all()
            topups = s.scalars(select(TopUp).where(TopUp.user_id == user.id).order_by(TopUp.id.desc())
                               .limit(10)).all()
            loyal = growth.loyalty_progress(s, user.id)
        return render(request, "kredi.html", user, txs=txs, topups=topups, iban=config.IBAN,
                      iban_name=config.IBAN_NAME, loyal=loyal, ref_pct=config.REFERRAL_PCT)

    promo_limiter = RateLimiter(limit=8, window=600)

    @app.post("/kredi/kod", dependencies=[Depends(check_csrf)])
    def credit_code(request: Request, user: User = Depends(require_user), code: str = Form("")):
        if (blocked := require_verified(request, user)) is not None:
            return blocked
        if not promo_limiter.allow(f"p:{user.id}"):
            flash(request, "Çok fazla deneme yaptın. Biraz sonra tekrar dene.", "err")
            return go("/kredi")
        try:
            with db.session() as s:
                amount = growth.redeem(s, user.id, code)
        except growth.PromoError as e:
            flash(request, str(e), "err")
            return go("/kredi")
        flash(request, "Kod kabul edildi, hesabına {n} kredi yüklendi. 🎉", n=amount)
        return go("/kredi")

    @app.get("/abonelik", response_class=HTMLResponse)
    def plans_page(request: Request, user: User = Depends(require_user), plan: str = "", donem: str = ""):
        """Abonelik karşılaştırması (aylık/yıllık) + abonelik havale formu. Kredi paketleri ayrı: /kredi."""
        cols = [{"key": "", "label": "Aboneliksiz", "desc": "Kredi paketiyle kullan", "price": 0, "credits": 0,
                 "quals": config.FREE_QUALITIES, "per_credit": config.PACKAGES[0][0] / config.PACKAGES[0][1]}]
        cols += [{"key": k, "label": p["label"], "desc": p["desc"], "price": p["price"], "credits": p["credits"],
                  "quals": config.plan_qualities(k), "per_credit": p["price"] / p["credits"], "quality": p["quality"]}
                 for k, p in config.PLANS.items()]
        for c in cols[1:]:
            c["yearly"] = config.plan_price(c["key"], True)
            c["yearly_month"] = round(c["yearly"] / 12)
        return render(request, "abonelik.html", user, cols=cols, plan_until=user.plan_until, iban=config.IBAN,
                      iban_name=config.IBAN_NAME, want_plan=plan if plan in config.PLANS else "pro",
                      yearly=donem == "yillik", save_pct=config.YEARLY_SAVE_PCT, refills=user.plan_refills,
                      next_refill=user.plan_next_refill)

    @app.get("/ayarlar", response_class=HTMLResponse)
    def settings_page(request: Request, user: User = Depends(require_user)):
        return render(request, "ayarlar.html", user)

    @app.get("/rehberler", response_class=HTMLResponse)
    def guides_page(request: Request):
        return render(request, "rehberler.html", current_user(request), guides=rehberler.GUIDES)

    @app.get("/rehberler/{slug}", response_class=HTMLResponse)
    def guide_page(request: Request, slug: str):
        guide = rehberler.BY_SLUG.get(slug)
        if not guide:
            raise HTTPException(404)
        return render(request, "rehber.html", current_user(request), guide=guide,
                      others=[g for g in rehberler.GUIDES if g is not guide])

    # --- davet ---
    @app.get("/davet", response_class=HTMLResponse)
    def invite_page(request: Request, user: User = Depends(require_user)):
        with db.session() as s:
            code = growth.ref_code_for(s, user.id)
            stats = growth.referral_stats(s, user.id)
        return render(request, "davet.html", user, link=f"{site_url(request)}/d/{code}", code=code, stats=stats,
                      friend_pct=config.REFERRAL_FRIEND_PCT)

    @app.post("/kredi/bildirim", dependencies=[Depends(check_csrf)])
    def credit_notify(request: Request, user: User = Depends(require_user), package: str = Form(""),
                      donem: str = Form("aylik"), sender_name: str = Form(...), note: str = Form(""),
                      accept: str = Form("")):
        """Havale bildirimi: "package" kredi paketinin sırası ya da "plan:<anahtar>" (abonelik; donem=yillik ise
        12 aylık). Abonelik bildirimleri Abonelikler sayfasından, kredi paketleri Kredi sayfasından gelir."""
        plan = package.removeprefix("plan:") if package.startswith("plan:") else ""
        back = "/abonelik#odeme" if plan else "/kredi"
        if (blocked := require_verified(request, user)) is not None:
            return blocked
        if config.SHOWCASE:
            flash(request, "Bu sürümde ödeme alınmıyor.", "warn")
            return go(back)
        yearly = bool(plan) and donem == "yillik"
        valid = plan in config.PLANS if plan else package.isdigit() and int(package) < len(config.PACKAGES)
        if not valid or not sender_name.strip() or not accept:
            flash(request, "Paketi seç, gönderen adını yaz ve sözleşmeyi onayla.", "err")
            return go(back)
        tl, cr = ((config.plan_price(plan, yearly), config.PLANS[plan]["credits"]) if plan
                  else config.PACKAGES[int(package)])
        with db.session() as s:
            pending = s.scalar(select(func.count(TopUp.id)).where(TopUp.user_id == user.id,
                                                                  TopUp.status == "bekliyor"))
            if pending >= 3:
                flash(request, "Onay bekleyen 3 bildirimin var, onaylanmalarını bekle.", "err")
                return go(back)
            s.add(TopUp(user_id=user.id, amount_tl=tl, credits=cr, sender_name=clean(sender_name, 120),
                        note=clean(note, 300), plan=f"{plan}:yillik" if yearly else plan))
        notify_admins_topup(request, user.email, tl, clean(sender_name, 120))
        flash(request, "Bildirimin alındı. Havale kontrol edilince kredin yüklenecek (genelde birkaç saat).")
        return go(back)

    # --- admin ---
    def _daily_stats(s, days: int = 14) -> dict:
        """Son N günün günlük kayıt, video ve gelir sayıları (yerel saate göre) ve özet rakamlar."""
        from datetime import timedelta, timezone

        tz = ZoneInfo(config.TIMEZONE)
        today = datetime.now(tz).date()
        keys = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
        since = datetime.combine(keys[0], datetime.min.time(), tz).astimezone(timezone.utc)

        def day(dt):
            return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(tz).date()

        series = {k: {"users": 0, "videos": 0, "tl": 0} for k in keys}
        for (dt,) in s.execute(select(User.created_at).where(User.created_at >= since)):
            if day(dt) in series:
                series[day(dt)]["users"] += 1
        cost_usd = 0.0
        for dt, q, sec in s.execute(select(Job.finished_at, Job.quality, Job.seconds)
                                    .where(Job.status == "hazir", Job.finished_at >= since)):
            if day(dt) in series:
                series[day(dt)]["videos"] += 1
                cost_usd += config.cost_usd(q, sec or 8)
        for dt, tl in s.execute(select(TopUp.decided_at, TopUp.amount_tl).where(TopUp.status == "onaylandi",
                                                                               TopUp.decided_at >= since)):
            if day(dt) in series:
                series[day(dt)]["tl"] += tl
        failed = s.scalar(select(func.count(Job.id)).where(Job.status == "hata", Job.created_at >= since)) or 0
        done = sum(v["videos"] for v in series.values())
        revenue = sum(v["tl"] for v in series.values())
        cost_tl = round(cost_usd * config.USD_TRY)
        rows = [{"label": k.strftime("%d.%m"), **v} for k, v in series.items()]
        peak = {m: max(1, *(r[m] for r in rows)) for m in ("users", "videos", "tl")}
        return {
            "rows": rows, "peak": peak, "revenue": revenue, "cost_tl": cost_tl, "profit": revenue - cost_tl,
            "fail_rate": round(100 * failed / (failed + done)) if failed + done else 0,
            "liability": s.scalar(select(func.coalesce(func.sum(User.credits), 0))),
            "channels": s.scalar(select(func.count(Channel.id)).where(Channel.active.is_(True))),
            "days": days,
        }

    @app.get("/admin", response_class=HTMLResponse)
    def admin(request: Request, user: User = Depends(require_admin)):
        with db.session() as s:
            topups = s.scalars(select(TopUp).where(TopUp.status == "bekliyor").order_by(TopUp.id)).all()
            for t in topups:
                _ = t.user.email
            users = s.scalars(select(User).order_by(User.id.desc()).limit(100)).all()
            jobs = s.scalars(select(Job).order_by(Job.id.desc()).limit(50)).all()
            from datetime import timedelta

            failed = s.scalars(select(Job).where(Job.status == "hata", Job.created_at >= now() - timedelta(days=7))
                               .order_by(Job.id.desc()).limit(30)).all()
            promos = s.scalars(select(PromoCode).order_by(PromoCode.id.desc()).limit(30)).all()
            public_jobs = s.scalars(select(Job).where(Job.public.is_(True)).order_by(Job.public_at.desc()).limit(30)).all()
            from .models import Waitlist

            stats = {
                "waitlist": s.scalar(select(func.count(Waitlist.id))),
                "feedback_new": s.scalar(select(func.count(Feedback.id)).where(Feedback.status == "yeni")),
                "users": s.scalar(select(func.count(User.id))),
                "videos": s.scalar(select(func.count(Job.id)).where(Job.status == "hazir")),
                "queue": s.scalar(select(func.count(Job.id)).where(Job.status.in_(["sirada", "uretiliyor"]))),
                "tl": s.scalar(select(func.coalesce(func.sum(TopUp.amount_tl), 0))
                               .where(TopUp.status == "onaylandi")),
            }
            daily = _daily_stats(s)
        from . import hazirlik

        return render(request, "admin.html", user, topups=topups, users=users, jobs=jobs, stats=stats, promos=promos,
                      daily=daily, usd_try=config.USD_TRY, public_jobs=public_jobs, ready=hazirlik.summary(),
                      failed=failed)

    @app.get("/admin/oneriler", response_class=HTMLResponse)
    def admin_feedback(request: Request, user: User = Depends(require_admin), tur: str = ""):
        with db.session() as s:
            q = select(Feedback).order_by(Feedback.id.desc()).limit(200)
            items = s.scalars(q.where(Feedback.kind == tur) if tur else q).all()
        return render(request, "admin_oneriler.html", user, items=items, kinds=FEEDBACK_KINDS, tur=tur)

    @app.post("/admin/oneri/{fid}/okundu", dependencies=[Depends(check_csrf)])
    def admin_feedback_read(fid: int, user: User = Depends(require_admin)):
        with db.session() as s:
            s.execute(update(Feedback).where(Feedback.id == fid).values(status="okundu"))
        return go("/admin/oneriler")

    @app.get("/admin/kullanicilar", response_class=HTMLResponse)
    def admin_users(request: Request, user: User = Depends(require_admin), q: str = "", sayfa: int = 1):
        per = 50
        q = clean(q, 100)
        with db.session() as s:
            base = select(User).where(~User.email.like("silindi-%@silindi.invalid"))
            if q:
                base = base.where(or_(User.email.ilike(f"%{q}%"), User.name.ilike(f"%{q}%"),
                                      User.id == (int(q) if q.isdigit() else -1)))
            total = s.scalar(select(func.count()).select_from(base.subquery()))
            pages = max(1, -(-total // per))
            sayfa = min(max(1, sayfa), pages)
            users = s.scalars(base.order_by(User.id.desc()).offset((sayfa - 1) * per).limit(per)).all()
            ids = [u.id for u in users]
            videos = dict(s.execute(select(Job.user_id, func.count(Job.id)).where(Job.user_id.in_(ids), Job.status == "hazir")
                                    .group_by(Job.user_id)).all()) if ids else {}
            paid = dict(s.execute(select(TopUp.user_id, func.coalesce(func.sum(TopUp.amount_tl), 0))
                                  .where(TopUp.user_id.in_(ids), TopUp.status == "onaylandi").group_by(TopUp.user_id)).all()) if ids else {}
        return render(request, "admin_kullanicilar.html", user, users=users, q=q, total=total, sayfa=sayfa, pages=pages,
                      videos=videos, paid=paid)

    @app.get("/admin/kullanici/{uid}", response_class=HTMLResponse)
    def admin_user(request: Request, uid: int, user: User = Depends(require_admin)):
        with db.session() as s:
            target = s.get(User, uid)
            if not target:
                raise HTTPException(404)
            txs = s.scalars(select(CreditTx).where(CreditTx.user_id == uid).order_by(CreditTx.id.desc()).limit(40)).all()
            topups = s.scalars(select(TopUp).where(TopUp.user_id == uid).order_by(TopUp.id.desc()).limit(20)).all()
            jobs = s.scalars(select(Job).where(Job.user_id == uid).order_by(Job.id.desc()).limit(30)).all()
            chans = s.scalars(select(Channel).where(Channel.user_id == uid)).all()
            accs = s.scalars(select(SocialAccount).where(SocialAccount.user_id == uid)).all()
            referrer = s.get(User, target.referred_by) if target.referred_by else None
            invited = s.scalar(select(func.count(User.id)).where(User.referred_by == uid))
        return render(request, "admin_kullanici.html", user, target=target, txs=txs, topups=topups, jobs=jobs,
                      chans=chans, accs=accs, referrer=referrer, invited=invited)

    @app.post("/admin/kullanici/{uid}/{action}", dependencies=[Depends(check_csrf)])
    def admin_user_action(request: Request, uid: int, action: str, user: User = Depends(require_admin)):
        if action not in ("askiya-al", "dogrula"):
            raise HTTPException(404)
        with db.session() as s:
            target = s.get(User, uid)
            if not target or target.id == user.id:
                raise HTTPException(404)
            if action == "dogrula":
                mark_verified(s, target)
                msg = "E-posta doğrulandı olarak işaretlendi."
            else:
                target.blocked = not target.blocked
                if target.blocked:  # askıdaki hesabın kanalları da durur
                    for ch in s.scalars(select(Channel).where(Channel.user_id == uid)):
                        ch.active = False
                msg = "Hesap askıya alındı." if target.blocked else "Hesap yeniden açıldı."
        flash(request, msg)
        return go(f"/admin/kullanici/{uid}")

    @app.get("/admin/erken-erisim.csv")
    def admin_waitlist_csv(user: User = Depends(require_admin)):
        import csv
        import io

        from .models import Waitlist

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["email", "dil", "kaynak", "tarih", "kaydoldu_hediye"])
        with db.session() as s:
            for r in s.scalars(select(Waitlist).order_by(Waitlist.id)):
                w.writerow([r.email, r.lang, r.source, r.created_at.isoformat(), "evet" if r.rewarded else ""])
        return Response("\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="erken-erisim.csv"'})

    @app.get("/admin/hazirlik", response_class=HTMLResponse)
    def admin_readiness(request: Request, user: User = Depends(require_admin)):
        from . import hazirlik

        return render(request, "admin_hazirlik.html", user, **hazirlik.summary())

    @app.post("/admin/kesfet/{job_id}/{action}", dependencies=[Depends(check_csrf)])
    def admin_explore(request: Request, job_id: int, action: str, user: User = Depends(require_admin)):
        if action not in ("one-cikar", "kaldir"):
            raise HTTPException(404)
        with db.session() as s:
            job = s.get(Job, job_id)
            if not job:
                raise HTTPException(404)
            if action == "kaldir":  # moderasyon: herkese açık listeden çıkar
                job.public = job.featured = False
            else:
                job.featured = not job.featured
        flash(request, "Keşfet güncellendi.")
        return go("/admin")

    @app.post("/admin/kod", dependencies=[Depends(check_csrf)])
    def admin_promo_create(request: Request, user: User = Depends(require_admin), code: str = Form(""),
                           amount: int = Form(...), max_uses: int = Form(0), days: int = Form(0), note: str = Form("")):
        from datetime import timedelta

        code = growth.norm_code(code) or growth.random_code(8)
        if not 0 < amount <= 10000 or max_uses < 0 or days < 0:
            flash(request, "Kredi 1–10000 arası, kullanım ve gün 0 ya da pozitif olmalı.", "err")
            return go("/admin")
        with db.session() as s:
            if s.scalar(select(PromoCode.id).where(PromoCode.code == code)):
                flash(request, f"{code} kodu zaten var.", "err")
                return go("/admin")
            s.add(PromoCode(code=code, credits=amount, max_uses=max_uses, note=clean(note, 200),
                            expires_at=now() + timedelta(days=days) if days else None))
        flash(request, f"{code} kodu oluşturuldu: {amount} kredi" + (f", {max_uses} kişilik" if max_uses else ""))
        return go("/admin")

    @app.post("/admin/kod/{pid}/durum", dependencies=[Depends(check_csrf)])
    def admin_promo_toggle(request: Request, pid: int, user: User = Depends(require_admin)):
        with db.session() as s:
            promo = s.get(PromoCode, pid)
            if not promo:
                raise HTTPException(404)
            promo.active = not promo.active
            msg = f"{promo.code} kodu {'açıldı' if promo.active else 'kapatıldı'}."
        flash(request, msg)
        return go("/admin")

    @app.post("/admin/yukleme/{tid}/{action}", dependencies=[Depends(check_csrf)])
    def admin_topup(request: Request, tid: int, action: str, user: User = Depends(require_admin)):
        if action not in ("onayla", "reddet"):
            raise HTTPException(404)
        with db.session() as s:
            # aynı anda iki kez onaylansa da kredi bir kere yüklensin
            res = s.execute(update(TopUp).where(TopUp.id == tid, TopUp.status == "bekliyor").values(
                status="onaylandi" if action == "onayla" else "reddedildi", decided_at=now()))
            if res.rowcount != 1:
                flash(request, "Bu bildirim zaten işlenmiş.", "err")
                return go("/admin")
            t = s.get(TopUp, tid)
            referrer, ref_amount = None, 0
            plan_until = None
            if action == "onayla":
                plan_key, yearly = abonelik.split_plan(t.plan)
                if plan_key:  # abonelik: planı başlat/uzat, ilk ayın kredisini yükle
                    plan_until = abonelik.activate(s, t.user_id, plan_key, yearly)
                else:
                    credits.add(s, t.user_id, t.credits, f"Havale ile yükleme ({t.amount_tl} TL)")
                referrer, ref_amount = growth.first_topup_rewards(s, t.user_id, t.credits)
            uid, amount_tl, cr, plan = t.user_id, t.amount_tl, t.credits, abonelik.split_plan(t.plan)[0]
        if action == "onayla" and plan_until:
            worker.notify(uid, "{site}: {plan} aboneliğin başladı 🚀", "Aboneliğin aktif!",
                          "{tl} ₺ havalen onaylandı. <b>{plan}</b> aboneliğin {date} tarihine kadar açık ve hesabına "
                          "<b>{n} kredi</b> yüklendi.", ("Video üret", f"{site_url(request)}/video/yeni"),
                          tl=amount_tl, n=cr, plan=config.PLANS[plan]["label"],
                          date=plan_until.astimezone(ZoneInfo(config.TIMEZONE)).strftime("%d.%m.%Y"))
        elif action == "onayla":
            worker.notify(uid, "{site}: kredin yüklendi 💎", "Kredin yüklendi!",
                          "{tl} ₺ havalen onaylandı ve hesabına <b>{n} kredi</b> yüklendi. Üretmeye başlayabilirsin.",
                          ("Video üret", f"{site_url(request)}/video/yeni"), tl=amount_tl, n=cr)
        if referrer and ref_amount:
            worker.notify(referrer, "{site}: davet ödülün geldi 🎁", "Davet ödülün yüklendi!",
                          "Davet ettiğin bir arkadaşın ilk kredisini yükledi; hesabına <b>{n} kredi</b> hediye edildi. "
                          "Teşekkürler!", ("Davet sayfam", f"{site_url(request)}/davet"), n=ref_amount)
        flash(request, "Yükleme onaylandı, kredi eklendi." if action == "onayla" else "Bildirim reddedildi.")
        return go("/admin")

    @app.post("/admin/kredi", dependencies=[Depends(check_csrf)])
    def admin_credit(request: Request, user: User = Depends(require_admin), email: str = Form(...),
                     amount: int = Form(...), reason: str = Form("Yönetici düzeltmesi"), back: str = Form("")):
        back = back if re.fullmatch(r"/admin/kullanici/\d+", back) else "/admin"
        with db.session() as s:
            target = s.scalar(select(User).where(User.email == email.strip().lower()))
            if not target:
                flash(request, "Bu e-postayla kullanıcı yok.", "err")
                return go(back)
            if amount < 0 and target.credits + amount < 0:
                flash(request, "Kullanıcının bakiyesi bu kadar düşürülemez.", "err")
                return go(back)
            credits.add(s, target.id, amount, clean(reason, 200) or "Yönetici düzeltmesi")
        flash(request, f"{email} hesabına {amount:+} kredi işlendi.")
        return go(back)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        if exc.status_code in (301, 302, 303) and exc.headers:
            return RedirectResponse(exc.headers["Location"], status_code=303)
        if exc.status_code == 404:
            return render(request, "hata.html", current_user(request), status_code=404,
                          title=i18n.t("Sayfa bulunamadı"), message=i18n.t("Aradığın sayfa yok ya da sana ait değil."))
        return render(request, "hata.html", current_user(request), status_code=exc.status_code,
                      title=i18n.t("Bir sorun oldu"), message=i18n.t(str(exc.detail)))

    @app.exception_handler(404)
    async def not_found(request: Request, exc):
        return render(request, "hata.html", current_user(request), status_code=404,
                      title=i18n.t("Sayfa bulunamadı"), message=i18n.t("Aradığın sayfa yok ya da sana ait değil."))
