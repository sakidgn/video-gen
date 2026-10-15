"""Otomatik paylaşım: YouTube Shorts, TikTok ve Instagram Reels (resmi API'ler, OAuth ile hesap bağlama).

Her platform için: auth_url → (kullanıcı onaylar) → exchange(code) → hesap bilgisi; publish(video) → (uzak id, adres).
Anahtarlar .env'de yoksa platform kapalıdır; SAHTE_AI=1 iken "demo" bağlantı ile akış denenebilir.
Not: TikTok ve Instagram uygulamaları platformun incelemesinden geçene kadar paylaşımlar kısıtlıdır
(TikTok'ta yalnızca "sadece ben", YouTube'da doğrulanmamış projede gizli)."""
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from . import config


class PublishError(Exception):
    pass


@dataclass
class Account:
    name: str
    remote_id: str
    access: str
    refresh: str = ""
    expires_in: int = 0


@dataclass
class Post:
    title: str
    caption: str  # açıklama + hashtag'ler
    tags: list[str]


PLATFORMS = {
    "youtube": {"label": "YouTube Shorts", "short": "YouTube", "icon": "youtube",
                "note": "Google hesabındaki YouTube kanalına Shorts olarak yüklenir; “yapay zekâ ile değiştirildi” bildirimi açık."},
    "tiktok": {"label": "TikTok", "short": "TikTok", "icon": "tiktok",
               "note": "TikTok hesabına yüklenir; yapay zekâ içeriği (AIGC) etiketi açık."},
    "instagram": {"label": "Instagram Reels", "short": "Instagram", "icon": "instagram",
                  "note": "İşletme ya da içerik üreticisi (Creator) Instagram hesabı gerekir."},
}


def _keys(platform: str) -> tuple[str, str]:
    return {
        "youtube": (config.GOOGLE_CLIENT_ID, config.GOOGLE_CLIENT_SECRET),
        "tiktok": (config.TIKTOK_CLIENT_KEY, config.TIKTOK_CLIENT_SECRET),
        "instagram": (config.INSTAGRAM_APP_ID, config.INSTAGRAM_APP_SECRET),
    }[platform]


def configured(platform: str) -> bool:
    return all(_keys(platform))


def demo(platform: str) -> bool:
    """Anahtar yokken deneme modunda sahte bağlantı (arayüzü görmek için)."""
    return config.FAKE_AI and not configured(platform)


def available(platform: str) -> bool:
    return configured(platform) or demo(platform)


def client(platform: str, http=None):
    if demo(platform):
        return DemoClient(platform)
    return {"youtube": YouTube, "tiktok": TikTok, "instagram": Instagram}[platform](http)


def _session(http):
    if http is not None:
        return http
    import requests

    return requests.Session()


def _ok(r, what: str):
    if r.status_code >= 400:
        raise PublishError(f"{what}: {r.status_code} {r.text[:300]}")
    return r


# ---------------- YouTube ----------------
class YouTube:
    AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN = "https://oauth2.googleapis.com/token"
    SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"

    def __init__(self, http=None):
        self.http = _session(http)
        self.cid, self.secret = _keys("youtube")

    def auth_url(self, redirect: str, state: str) -> str:
        q = {"client_id": self.cid, "redirect_uri": redirect, "response_type": "code", "scope": self.SCOPES,
             "state": state, "access_type": "offline", "prompt": "consent", "include_granted_scopes": "true"}
        return f"{self.AUTH}?{urllib.parse.urlencode(q)}"

    def exchange(self, code: str, redirect: str) -> Account:
        tok = _ok(self.http.post(self.TOKEN, data={"code": code, "client_id": self.cid, "client_secret": self.secret,
                                                   "redirect_uri": redirect, "grant_type": "authorization_code"},
                                 timeout=30), "YouTube jetonu").json()
        ch = _ok(self.http.get("https://www.googleapis.com/youtube/v3/channels", params={"part": "snippet", "mine": "true"},
                               headers={"Authorization": f"Bearer {tok['access_token']}"}, timeout=30),
                 "YouTube kanalı").json()
        items = ch.get("items") or []
        if not items:
            raise PublishError("Bu Google hesabında YouTube kanalı yok. Önce YouTube'da bir kanal oluştur.")
        return Account(name=items[0]["snippet"]["title"], remote_id=items[0]["id"], access=tok["access_token"],
                       refresh=tok.get("refresh_token", ""), expires_in=int(tok.get("expires_in", 3600)))

    def refresh(self, refresh_token: str, access: str = "") -> tuple[str, int, str]:
        tok = _ok(self.http.post(self.TOKEN, data={"client_id": self.cid, "client_secret": self.secret,
                                                   "refresh_token": refresh_token, "grant_type": "refresh_token"},
                                 timeout=30), "YouTube yenileme").json()
        return tok["access_token"], int(tok.get("expires_in", 3600)), refresh_token

    def publish(self, acc_access: str, remote_id: str, video: Path, post: Post, public_url: str = "") -> tuple[str, str]:
        title = (post.title.replace("<", "").replace(">", "")[:90] + " #Shorts").strip()  # YouTube <> kabul etmez
        meta = {"snippet": {"title": title, "description": post.caption[:4900], "tags": post.tags[:15], "categoryId": "23"},
                "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}}
        size = video.stat().st_size
        init = _ok(self.http.post(
            "https://www.googleapis.com/upload/youtube/v3/videos",
            params={"uploadType": "resumable", "part": "snippet,status"}, json=meta, timeout=60,
            headers={"Authorization": f"Bearer {acc_access}", "X-Upload-Content-Type": "video/mp4",
                     "X-Upload-Content-Length": str(size)}), "YouTube yükleme başlatma")
        upload_url = init.headers.get("Location")
        if not upload_url:
            raise PublishError("YouTube yükleme adresi vermedi")
        with open(video, "rb") as f:
            res = _ok(self.http.put(upload_url, data=f, timeout=600,
                                    headers={"Content-Type": "video/mp4", "Content-Length": str(size)}),
                      "YouTube yükleme").json()
        vid = res["id"]
        return vid, f"https://youtube.com/shorts/{vid}"


# ---------------- TikTok ----------------
class TikTok:
    AUTH = "https://www.tiktok.com/v2/auth/authorize/"
    API = "https://open.tiktokapis.com/v2"

    def __init__(self, http=None):
        self.http = _session(http)
        self.key, self.secret = _keys("tiktok")

    def auth_url(self, redirect: str, state: str) -> str:
        q = {"client_key": self.key, "scope": "user.info.basic,video.publish", "response_type": "code",
             "redirect_uri": redirect, "state": state}
        return f"{self.AUTH}?{urllib.parse.urlencode(q)}"

    def _token(self, data: dict) -> dict:
        tok = _ok(self.http.post(f"{self.API}/oauth/token/", data={"client_key": self.key, "client_secret": self.secret,
                                                                    **data}, timeout=30), "TikTok jetonu").json()
        if "access_token" not in tok:
            raise PublishError(f"TikTok jetonu alınamadı: {str(tok)[:200]}")
        return tok

    def exchange(self, code: str, redirect: str) -> Account:
        tok = self._token({"code": code, "grant_type": "authorization_code", "redirect_uri": redirect})
        info = _ok(self.http.get(f"{self.API}/user/info/", params={"fields": "open_id,display_name"}, timeout=30,
                                 headers={"Authorization": f"Bearer {tok['access_token']}"}), "TikTok kullanıcı").json()
        user = (info.get("data") or {}).get("user") or {}
        return Account(name=user.get("display_name") or "TikTok hesabı", remote_id=tok.get("open_id", ""),
                       access=tok["access_token"], refresh=tok.get("refresh_token", ""),
                       expires_in=int(tok.get("expires_in", 86400)))

    def refresh(self, refresh_token: str, access: str = "") -> tuple[str, int, str]:
        tok = self._token({"grant_type": "refresh_token", "refresh_token": refresh_token})
        return tok["access_token"], int(tok.get("expires_in", 86400)), tok.get("refresh_token", refresh_token)

    def publish(self, acc_access: str, remote_id: str, video: Path, post: Post, public_url: str = "") -> tuple[str, str]:
        h = {"Authorization": f"Bearer {acc_access}", "Content-Type": "application/json; charset=UTF-8"}
        info = _ok(self.http.post(f"{self.API}/post/publish/creator_info/query/", headers=h, json={}, timeout=30),
                   "TikTok hesap bilgisi").json().get("data") or {}
        options = info.get("privacy_level_options") or ["SELF_ONLY"]
        privacy = "PUBLIC_TO_EVERYONE" if "PUBLIC_TO_EVERYONE" in options else options[0]
        size = video.stat().st_size
        title = f"{post.caption}"[:2200]
        init = _ok(self.http.post(f"{self.API}/post/publish/video/init/", headers=h, timeout=60, json={
            "post_info": {"title": title, "privacy_level": privacy, "disable_duet": False, "disable_comment": False,
                          "disable_stitch": False, "is_aigc": True},
            "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1},
        }), "TikTok yükleme başlatma").json().get("data") or {}
        publish_id, upload_url = init.get("publish_id"), init.get("upload_url")
        if not publish_id or not upload_url:
            raise PublishError("TikTok yükleme adresi vermedi")
        with open(video, "rb") as f:
            _ok(self.http.put(upload_url, data=f, timeout=600, headers={
                "Content-Type": "video/mp4", "Content-Length": str(size), "Content-Range": f"bytes 0-{size - 1}/{size}"}),
                "TikTok yükleme")
        for _ in range(60):
            st = _ok(self.http.post(f"{self.API}/post/publish/status/fetch/", headers=h, json={"publish_id": publish_id},
                                    timeout=30), "TikTok durum").json().get("data") or {}
            status = st.get("status")
            if status == "PUBLISH_COMPLETE":
                break
            if status == "FAILED":
                raise PublishError(f"TikTok paylaşımı başarısız: {st.get('fail_reason', '')}")
            time.sleep(self.poll_s)
        return publish_id, ""

    poll_s = 5


# ---------------- Instagram ----------------
class Instagram:
    AUTH = "https://www.instagram.com/oauth/authorize"
    GRAPH = "https://graph.instagram.com/v21.0"

    def __init__(self, http=None):
        self.http = _session(http)
        self.app_id, self.secret = _keys("instagram")

    def auth_url(self, redirect: str, state: str) -> str:
        q = {"client_id": self.app_id, "redirect_uri": redirect, "response_type": "code", "state": state,
             "scope": "instagram_business_basic,instagram_business_content_publish"}
        return f"{self.AUTH}?{urllib.parse.urlencode(q)}"

    def exchange(self, code: str, redirect: str) -> Account:
        short = _ok(self.http.post("https://api.instagram.com/oauth/access_token", timeout=30, data={
            "client_id": self.app_id, "client_secret": self.secret, "grant_type": "authorization_code",
            "redirect_uri": redirect, "code": code}), "Instagram jetonu").json()
        long = _ok(self.http.get("https://graph.instagram.com/access_token", timeout=30, params={
            "grant_type": "ig_exchange_token", "client_secret": self.secret, "access_token": short["access_token"]}),
            "Instagram uzun süreli jeton").json()
        me = _ok(self.http.get(f"{self.GRAPH}/me", params={"fields": "user_id,username", "access_token": long["access_token"]},
                               timeout=30), "Instagram hesap").json()
        return Account(name="@" + me.get("username", "instagram"), remote_id=str(me.get("user_id") or short.get("user_id")),
                       access=long["access_token"], expires_in=int(long.get("expires_in", 5_184_000)))

    def refresh(self, refresh_token: str, access: str = "") -> tuple[str, int, str]:
        tok = _ok(self.http.get("https://graph.instagram.com/refresh_access_token", timeout=30,
                                params={"grant_type": "ig_refresh_token", "access_token": access}),
                  "Instagram yenileme").json()
        return tok["access_token"], int(tok.get("expires_in", 5_184_000)), ""

    def publish(self, acc_access: str, remote_id: str, video: Path, post: Post, public_url: str = "") -> tuple[str, str]:
        if not public_url.startswith("https://"):
            raise PublishError("Instagram videoyu internetten indirir: SITE_ADRESI https ile başlamalı.")
        c = _ok(self.http.post(f"{self.GRAPH}/{remote_id}/media", timeout=60, data={
            "media_type": "REELS", "video_url": public_url, "caption": post.caption[:2200], "share_to_feed": "true",
            "access_token": acc_access}), "Instagram video yükleme").json()
        container = c["id"]
        for _ in range(60):
            st = _ok(self.http.get(f"{self.GRAPH}/{container}", timeout=30,
                                   params={"fields": "status_code", "access_token": acc_access}), "Instagram durum").json()
            if st.get("status_code") == "FINISHED":
                break
            if st.get("status_code") in ("ERROR", "EXPIRED"):
                raise PublishError("Instagram videoyu işleyemedi")
            time.sleep(self.poll_s)
        pub = _ok(self.http.post(f"{self.GRAPH}/{remote_id}/media_publish", timeout=60,
                                 data={"creation_id": container, "access_token": acc_access}), "Instagram yayınlama").json()
        media_id = pub["id"]
        link = self.http.get(f"{self.GRAPH}/{media_id}", timeout=30,
                             params={"fields": "permalink", "access_token": acc_access})
        url = link.json().get("permalink", "") if link.status_code < 400 else ""
        return media_id, url

    poll_s = 5


# ---------------- Demo ----------------
class DemoClient:
    """Anahtar yokken (SAHTE_AI=1) akışı denemek için: bağlanır ve 'paylaşır' ama hiçbir yere bir şey gitmez."""

    def __init__(self, platform: str):
        self.platform = platform

    def auth_url(self, redirect: str, state: str) -> str:
        return f"{redirect}?{urllib.parse.urlencode({'code': 'demo', 'state': state})}"

    def exchange(self, code: str, redirect: str) -> Account:
        return Account(name=f"Demo · {PLATFORMS[self.platform]['short']}", remote_id="demo", access="demo",
                       refresh="demo", expires_in=10 ** 7)

    def refresh(self, refresh_token: str, access: str = "") -> tuple[str, int, str]:
        return "demo", 10 ** 7, refresh_token

    def publish(self, acc_access: str, remote_id: str, video: Path, post: Post, public_url: str = "") -> tuple[str, str]:
        if not video.exists():
            raise PublishError("video dosyası yok")
        return f"demo-{int(time.time())}", ""


def post_from_job(job) -> Post:
    tags = [h.strip("#") for h in (job.hashtags or "").split() if h.strip("#")]
    caption = (job.caption or job.title or "").strip()
    if tags:
        caption += "\n\n" + " ".join(f"#{t}" for t in tags)
    return Post(title=job.title or "Yeni video", caption=caption, tags=tags)
