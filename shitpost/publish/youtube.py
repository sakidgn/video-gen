import json
import os
from pathlib import Path

from ..config import Channel

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
COMEDY_CATEGORY = "23"


def _token_info(channel: Channel) -> dict:
    cfg = channel.platforms["youtube"] or {}
    env_name = cfg.get("token_env")
    if env_name and os.environ.get(env_name):
        return json.loads(os.environ[env_name])
    path = channel.dir / "youtube_token.json"
    if path.exists():
        return json.loads(path.read_text())
    raise RuntimeError(
        f"YouTube token yok. `python -m shitpost youtube-yetki {channel.slug}` çalıştır "
        f"ya da {env_name or 'token_env'} ortam değişkenini ayarla."
    )


def authorize(channel: Channel, client_secret: Path) -> Path:
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    out = channel.dir / "youtube_token.json"
    out.write_text(creds.to_json())
    return out


def publish(channel: Channel, video_path: Path, post) -> dict:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    cfg = channel.platforms["youtube"] or {}
    creds = Credentials.from_authorized_user_info(_token_info(channel), SCOPES)
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    body = {
        "snippet": {
            "title": f"{post.title} #shorts"[:100],
            "description": post.caption_with_tags(),
            "tags": [t.lstrip("#") for t in post.hashtags],
            "categoryId": COMEDY_CATEGORY,
        },
        "status": {
            "privacyStatus": cfg.get("gizlilik", "public"),
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,
        },
    }
    req = yt.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True),
    )
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return {"youtube": f"https://youtube.com/shorts/{resp['id']}"}
