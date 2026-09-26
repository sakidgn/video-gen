import random
import time

from google.genai import errors, types
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
- The video model refuses anything that looks risky, so the humor must be 100% harmless: awkward, absurd,
  cringe, dumb misunderstandings. NO injuries, falls, crashes, explosions, fire, electricity, weapons,
  fights, violence, blood, dangerous stunts, heavy objects falling on anyone, choking, drugs or alcohol.
{rules}

ALREADY MADE - do NOT repeat these ideas, jokes or structures:
{past_block}
"""


def web_video_prompt(channel: Channel, scenario: Scenario) -> str:
    chars = " ".join(f"{c.name} is {c.description}." for c in channel.characters)
    return (
        f"Generate a video. Vertical 9:16, 8 seconds, with sound. "
        f"Characters: {chars} Style: {channel.style.rstrip('.')}. "
        f"Opening shot: {scenario.ilk_kare} Action: {scenario.video_prompt} "
        f"Lighthearted, family-friendly comedy: everyone is safe and nobody gets hurt. "
        f"No subtitles, captions or on-screen text."
    )


FALLBACK_TEXT_MODELS = [
    "gemini-flash-latest",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
]
RETRY_DELAYS = [10, 30, 60]
_sleep = time.sleep


def _is_temporary(e: errors.APIError) -> bool:
    return isinstance(e, errors.ServerError) or e.code == 429


def _generate_with_retry(client, model: str, contents, config):
    models = [model] + [m for m in FALLBACK_TEXT_MODELS if m != model]
    last_error = None
    for delay in [0, *RETRY_DELAYS]:
        if delay:
            print(f"Tüm modeller yoğun, {delay} sn bekleniyor...")
            _sleep(delay)
        for m in list(models):
            try:
                return client.models.generate_content(model=m, contents=contents, config=config)
            except errors.APIError as e:
                last_error = e
                if e.code == 404:
                    models.remove(m)
                elif _is_temporary(e):
                    print(f"'{m}' yoğun ({e.code}), başka model deneniyor...")
                else:
                    raise
        if not models:
            break
    raise last_error


def write_scenario(client, channel: Channel, theme: str) -> Scenario:
    past = history.recent_summaries(channel.history_path)
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=Scenario,
        temperature=1.2,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    contents = build_prompt(channel, theme, past)
    resp = _generate_with_retry(client, channel.models["metin"], contents, config)
    if isinstance(resp.parsed, Scenario):
        return resp.parsed
    return Scenario.model_validate_json(resp.text)
