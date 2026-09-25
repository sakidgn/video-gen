from dataclasses import dataclass
from pathlib import Path

from ..config import Channel


@dataclass
class Post:
    title: str
    caption: str
    hashtags: list[str]

    def caption_with_tags(self) -> str:
        tags = " ".join(f"#{t.lstrip('#')}" for t in self.hashtags)
        return f"{self.caption}\n\n{tags}".strip()


def publish_all(channel: Channel, video_path: Path, post: Post) -> tuple[dict, dict]:
    from . import ayrshare, youtube

    publishers = {"youtube": youtube.publish, "ayrshare": ayrshare.publish}
    links, errors = {}, {}
    for name in channel.platforms:
        if name not in publishers:
            errors[name] = "bilinmeyen platform"
            continue
        try:
            links.update(publishers[name](channel, video_path, post))
        except Exception as e:
            errors[name] = f"{type(e).__name__}: {e}"
    return links, errors
