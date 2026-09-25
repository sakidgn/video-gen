import os
from pathlib import Path

import requests

from ..config import Channel

API = "https://api.ayrshare.com/api"


def _headers(channel: Channel) -> dict:
    key = os.environ.get("AYRSHARE_API_KEY")
    if not key:
        raise RuntimeError("AYRSHARE_API_KEY ortam değişkeni yok")
    headers = {"Authorization": f"Bearer {key}"}
    profile_env = (channel.platforms["ayrshare"] or {}).get("profil_env")
    if profile_env and os.environ.get(profile_env):
        headers["Profile-Key"] = os.environ[profile_env]
    return headers


def _upload(video_path: Path, headers: dict) -> str:
    r = requests.get(
        f"{API}/media/uploadUrl",
        params={"fileName": video_path.name, "contentType": "mp4"},
        headers=headers,
        timeout=30,
    )
    r.raise_for_status()
    info = r.json()
    with video_path.open("rb") as f:
        put = requests.put(info["uploadUrl"], data=f, headers={"Content-Type": info["contentType"]}, timeout=300)
    put.raise_for_status()
    return info["accessUrl"]


def publish(channel: Channel, video_path: Path, post) -> dict:
    cfg = channel.platforms["ayrshare"] or {}
    platforms = cfg.get("platformlar", ["tiktok", "instagram"])
    headers = _headers(channel)
    media_url = _upload(video_path, headers)
    r = requests.post(
        f"{API}/post",
        headers=headers,
        json={
            "post": post.caption_with_tags(),
            "platforms": platforms,
            "mediaUrls": [media_url],
            "isVideo": True,
            "instagramOptions": {"shareReelsFeed": True},
            "tikTokOptions": {"isAIGenerated": True},
        },
        timeout=120,
    )
    data = r.json() if r.content else {}
    if r.status_code >= 400 or data.get("status") == "error":
        raise RuntimeError(f"Ayrshare {r.status_code}: {data or r.text}")
    links = {}
    for item in data.get("postIds", []):
        links[item.get("platform", "?")] = item.get("postUrl") or item.get("id") or item.get("status")
    return links or {p: "gönderildi" for p in platforms}
