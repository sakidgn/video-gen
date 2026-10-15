"""Site dili (Türkçe / İngilizce).

Metinler şablonlarda ve kodda Türkçe yazılır, _() ile sarılır; İngilizcesi i18n_en.py sözlüğünden gelir
(sözlükte yoksa Türkçesi görünür — testler eksik çeviriyi yakalar). Dil seçimi: /en/... adresleri (arama
motorları için ayrı İngilizce adresler) ya da "dil" çerezi; varsayılan Türkçe. Çerez /dil/<kod> ile değişir.
"""
import contextvars
import re
from http.cookies import SimpleCookie

from markupsafe import Markup, escape

LANGS = {"tr": "Türkçe", "en": "English"}
DEFAULT = "tr"
COOKIE = "dil"
COOKIE_AGE = 60 * 60 * 24 * 365
_lang = contextvars.ContextVar("lang", default=DEFAULT)


def current() -> str:
    return _lang.get()


def use(lang: str) -> contextvars.Token:
    return _lang.set(lang if lang in LANGS else DEFAULT)


def norm(lang: str | None) -> str:
    return lang if lang in LANGS else DEFAULT


def _table(lang: str) -> dict:
    if lang == "en":
        from .i18n_en import EN

        return EN
    return {}


def t(text: str, /, _lang_: str | None = None, **kw) -> str:
    """Türkçe metnin seçili dildeki karşılığı; {ad} yer tutucuları kw ile doldurulur."""
    if not text:
        return text or ""
    out = _table(_lang_ or _lang.get()).get(text, text)
    return out.format(**kw) if kw else out


def th(text: str, /, _lang_: str | None = None, **kw) -> Markup:
    """HTML içeren metin (ör. <b>): metnin kendisi güvenilir, yer tutucu değerleri kaçırılır."""
    return Markup(t(text, _lang_, **{k: escape(v) for k, v in kw.items()}))


def t_db(text: str, /, _lang_: str | None = None) -> str:
    """Veritabanında Türkçe saklanan kalıplı metinler (kredi hareketi açıklaması, kanal uyarısı, hata mesajı)."""
    lang = _lang_ or _lang.get()
    if not text or lang == DEFAULT:
        return text or ""
    table = _table(lang)
    if text in table:
        return table[text]
    from .i18n_en import PATTERNS

    for rx, repl in PATTERNS:
        m = rx.fullmatch(text)
        if m:
            return repl.format(*(table.get(g, g) for g in m.groups()))
    return text


def localized_path(path: str, lang: str | None = None, public: tuple[str, ...] = ()) -> str:
    """Herkese açık sayfaların İngilizce adresi /en ile başlar (diğer sayfalar dil çerezine bakar)."""
    lang = lang or _lang.get()
    bare = re.split(r"[?#]", path, maxsplit=1)[0] or "/"
    if lang == "en" and bare in public:
        return "/en" + (path if path != "/" else "/")
    return path


def strip_prefix(path: str) -> str:
    if path == "/en" or path.startswith("/en/") or path.startswith("/en?") or path.startswith("/en#"):
        return path[3:] if path[3:].startswith("/") else "/" + path[3:]
    return path


def wants_english(accept_language: str) -> bool:
    """Tarayıcı dili Türkçe değilse İngilizce önerilir (otomatik yönlendirme yok: arama motorları için)."""
    langs = [p.split(";")[0].strip().lower() for p in (accept_language or "").split(",") if p.strip()]
    return bool(langs) and not any(x.startswith("tr") for x in langs)


class LangMiddleware:
    """/en/... adreslerini İngilizce olarak karşılar (önekini atıp aynı sayfaya yönlendirir) ve isteğin dilini ayarlar."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        cookie = ""
        for k, v in scope.get("headers", []):
            if k == b"cookie":
                try:
                    c = SimpleCookie(v.decode("latin-1")).get(COOKIE)
                except Exception:
                    c = None
                cookie = c.value if c else ""
        prefixed = path == "/en" or path.startswith("/en/")
        if prefixed:
            bare = path[3:] or "/"
            scope = {**scope, "path": bare, "raw_path": bare.encode()}
            lang = "en"
        else:
            lang = norm(cookie)
        scope = {**scope, "state": {**scope.get("state", {}), "lang": lang, "lang_cookie": cookie}}
        set_cookie = prefixed and cookie != "en"

        async def send_with_cookie(msg):
            if set_cookie and msg["type"] == "http.response.start":
                header = f"{COOKIE}=en; Path=/; Max-Age={COOKIE_AGE}; SameSite=Lax".encode()
                msg = {**msg, "headers": [*msg.get("headers", []), (b"set-cookie", header)]}
            await send(msg)

        token = use(lang)
        try:
            await self.app(scope, receive, send_with_cookie)
        finally:
            _lang.reset(token)
