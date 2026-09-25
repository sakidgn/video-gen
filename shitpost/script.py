import random

from google.genai import types
from pydantic import BaseModel, Field

from . import history
from .config import Channel


class Scenario(BaseModel):
    baslik: str = Field(description="Short, clickbait-y video title, max 70 chars, no hashtags.")
    aciklama: str = Field(description="1-2 sentence funny caption for the post, no hashtags.")
    ozet: str = Field(description="One sentence plot summary, used to avoid repeating ideas.")
    ilk_kare: str = Field(
        description="English description of the very first frame: setting, character poses, camera framing. Vertical 9:16."
    )
    video_prompt: str = Field(
        description="English video prompt for Veo: action beat by beat, camera moves, dialogue lines in quotes "
        "with the speaking character named, sound effects and ambience. Fits in 8 seconds."
    )
    hashtagler: list[str] = Field(description="3-6 extra topical hashtags without the # sign.")


def pick_theme(channel: Channel, rng: random.Random | None = None) -> str:
    rng = rng or random.Random()
    used = set(history.recent_themes(channel.history_path, n=min(5, len(channel.themes) - 1)))
    candidates = [t for t in channel.themes if t not in used] or channel.themes
    return rng.choice(candidates)


def build_prompt(channel: Channel, theme: str, past: list[str]) -> str:
    chars = "\n".join(f"- {c.name}: {c.description}" for c in channel.characters)
    rules = "\n".join(f"- {r}" for r in channel.extra_rules)
    past_block = "\n".join(f"- {s}" for s in past) or "- (none yet)"
    return f"""You write scripts for "{channel.name}", a short-form absurd shitpost channel (YouTube Shorts, TikTok, Reels).

CHARACTERS (always describe them exactly like this, never by trademarked names in visual descriptions):
{chars}

VISUAL STYLE:
{channel.style}

TODAY'S SETTING: {theme}

RULES:
- One single 8-second scene. Hook in the first second, absurd twist, punchline at the end.
- Max 2-3 very short dialogue lines total, spoken in language "{channel.language}".
- Describe sound effects and ambience explicitly; no background music with lyrics.
- No on-screen text or subtitles in the video.
{rules}

ALREADY MADE - do NOT repeat these ideas, jokes or structures:
{past_block}
"""


def web_video_prompt(channel: Channel, scenario: Scenario) -> str:
    chars = " ".join(f"{c.name} is {c.description}." for c in channel.characters)
    return (
        f"Generate a video. Vertical 9:16, 8 seconds, with sound. "
        f"Characters: {chars} Style: {channel.style} "
        f"Opening shot: {scenario.ilk_kare} Action: {scenario.video_prompt} "
        f"No subtitles, captions or on-screen text."
    )


def write_scenario(client, channel: Channel, theme: str) -> Scenario:
    past = history.recent_summaries(channel.history_path)
    resp = client.models.generate_content(
        model=channel.models["metin"],
        contents=build_prompt(channel, theme, past),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Scenario,
            temperature=1.2,
        ),
    )
    if isinstance(resp.parsed, Scenario):
        return resp.parsed
    return Scenario.model_validate_json(resp.text)
