"""Yapay zeka katmanı: senaryo/başlık yazımı (Gemini metin) ve video üretimi (Veo)."""
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from . import config


class ContentBlocked(Exception):
    """Veo güvenlik filtresi videoyu üretmedi (kredi iade edilir)."""


@dataclass
class Script:
    video_prompt: str
    title: str
    caption: str
    hashtags: list[str]
    summary: str


RULES = (
    "Rules: family-friendly comedy, nobody gets seriously hurt; no real people or celebrities; "
    "no copyrighted or trademarked characters, brands or logos (if the user names one, replace it with an "
    "original look-alike-free character); no swearing; no on-screen text, subtitles, watermarks, usernames "
    "or social media interface in the video."
)


def build_script_request(*, idea: str, characters: str, style: str, language: str, past: list[str]) -> str:
    lang = config.LANGUAGES.get(language, language)
    style_desc = config.STYLES.get(style, style)
    parts = [
        f"Write one {config.DURATION_SECONDS}-second vertical (9:16) short video for TikTok/Reels/Shorts.",
        f"Visual style: {style_desc}.",
        f"Characters: {characters.strip() or 'invent 1-2 memorable original characters'}.",
        f"Idea from the user: {idea.strip()}" if idea.strip() else "Invent a fresh, funny, surprising idea.",
        f"Spoken dialogue language: {lang}.",
        RULES,
        "Return JSON with: video_prompt (a detailed English prompt for the Veo video model: describe "
        "characters' look, setting, camera, action beat by beat, sound effects and the exact dialogue lines in "
        f"{lang}; strong hook in the first second, punchline at the end), title (max 50 chars, in {lang}, 1-2 "
        f"emojis), caption (one short line in {lang} with 1-3 emojis, no hashtags), hashtags (3-6 words without "
        "#), summary (one English sentence).",
    ]
    if past:
        parts.append("Do NOT repeat these earlier ideas:\n- " + "\n- ".join(past[-30:]))
    return "\n".join(parts)


class RealAI:
    def __init__(self, client=None):
        if client is None:
            from google import genai
            from google.genai import types

            client = genai.Client(http_options=types.HttpOptions(timeout=120_000))
        self.client = client

    def write_script(self, *, idea, characters, style, language, past) -> Script:
        from google.genai import types

        schema = {
            "type": "object",
            "properties": {
                "video_prompt": {"type": "string"}, "title": {"type": "string"},
                "caption": {"type": "string"}, "summary": {"type": "string"},
                "hashtags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["video_prompt", "title", "caption", "hashtags", "summary"],
        }
        resp = self.client.models.generate_content(
            model=config.TEXT_MODEL,
            contents=build_script_request(idea=idea, characters=characters, style=style, language=language,
                                          past=past),
            config=types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=schema,
                                               temperature=1.1),
        )
        data = json.loads(resp.text)
        return Script(
            video_prompt=data["video_prompt"].strip(), title=data["title"].strip()[:120],
            caption=data["caption"].strip(), summary=data["summary"].strip(),
            hashtags=[h.strip().lstrip("#") for h in data.get("hashtags", []) if h.strip()][:8],
        )

    def make_video(self, *, prompt: str, quality: str, out: Path, poll_s: int = 10, timeout_s: int = 900) -> Path:
        from google.genai import types

        q = config.QUALITIES[quality]
        op = self.client.models.generate_videos(
            model=q["model"],
            prompt=prompt,
            config=types.GenerateVideosConfig(
                aspect_ratio="9:16", resolution=q["resolution"], duration_seconds=config.DURATION_SECONDS,
                negative_prompt="watermark, logo, text, subtitles, captions, username, social media interface",
                number_of_videos=1,
            ),
        )
        start = time.time()
        while not op.done:
            if time.time() - start > timeout_s:
                raise TimeoutError("Video üretimi zaman aşımına uğradı")
            time.sleep(poll_s)
            op = self.client.operations.get(op)
        if op.error:
            raise RuntimeError(f"Veo hatası: {op.error}")
        resp = op.response
        if not resp or not resp.generated_videos:
            reasons = (getattr(resp, "rai_media_filtered_reasons", None) if resp else None) or ["bilinmiyor"]
            raise ContentBlocked("; ".join(reasons))
        video = resp.generated_videos[0].video
        self.client.files.download(file=video)
        out.parent.mkdir(parents=True, exist_ok=True)
        video.save(str(out))
        return out


class FakeAI:
    """API'ye gitmeden çalışan sahte üretici (geliştirme ve testler için)."""

    def __init__(self, fail_with: Exception | None = None):
        self.fail_with = fail_with
        self.calls = 0

    def write_script(self, *, idea, characters, style, language, past) -> Script:
        self.calls += 1
        n = len(past) + 1
        return Script(video_prompt=f"[sahte] {idea or 'rastgele fikir'} #{n}", title=f"Deneme videosu {n} 😂",
                      caption="Bu bir deneme 💀", hashtags=["deneme", "shorts"], summary=f"fake idea {n}")

    def make_video(self, *, prompt: str, quality: str, out: Path, **_) -> Path:
        if self.fail_with:
            raise self.fail_with
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            import imageio_ffmpeg

            subprocess.run(
                [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi",
                 "-i", "testsrc=size=360x640:rate=10:duration=2", "-pix_fmt", "yuv420p", str(out)],
                check=True, timeout=60,
            )
        except Exception:
            out.write_bytes(b"\x00" * 1024)
        return out


def default_ai():
    return FakeAI() if config.FAKE_AI else RealAI()
