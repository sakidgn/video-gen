"""Google ile giriş (OAuth 2.0 / OpenID Connect, yetkilendirme kodu akışı)."""
import json
import urllib.parse
import urllib.request

from . import config

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class OAuthError(Exception):
    pass


def enabled() -> bool:
    return bool(config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET)


def auth_url(redirect_uri: str, state: str) -> str:
    q = {"client_id": config.GOOGLE_CLIENT_ID, "redirect_uri": redirect_uri, "response_type": "code",
         "scope": "openid email profile", "state": state, "prompt": "select_account", "access_type": "online"}
    return f"{AUTH_URL}?{urllib.parse.urlencode(q)}"


def _post(url: str, data: dict) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 (sabit Google adresi)
        return json.loads(r.read())


def _get(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310
        return json.loads(r.read())


def exchange_code(code: str, redirect_uri: str) -> dict:
    """Kodu Google'dan alınan kullanıcı bilgisine çevirir: {sub, email, email_verified, name}."""
    try:
        tok = _post(TOKEN_URL, {"code": code, "client_id": config.GOOGLE_CLIENT_ID,
                                "client_secret": config.GOOGLE_CLIENT_SECRET, "redirect_uri": redirect_uri,
                                "grant_type": "authorization_code"})
        info = _get(USERINFO_URL, tok["access_token"])
    except Exception as e:
        raise OAuthError(f"Google yanıtı alınamadı: {e}") from e
    if not info.get("sub") or not info.get("email"):
        raise OAuthError("Google e-posta bilgisini vermedi")
    return {"sub": str(info["sub"]), "email": info["email"].strip().lower(),
            "email_verified": bool(info.get("email_verified")), "name": (info.get("name") or "")[:100]}
