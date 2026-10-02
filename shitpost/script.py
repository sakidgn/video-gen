import random
import re
import time

from google.genai import errors, types
from pydantic import BaseModel, Field

from . import history
from .config import Channel


class Meta(BaseModel):
    baslik: str = Field(description="Short, clickbait-y video title, max 70 chars, no hashtags.")
    aciklama: str = Field(description="1-2 sentence funny caption for the post, no hashtags.")
    ozet: str = Field(description="One sentence plot summary, used to avoid repeating ideas.")
    hashtagler: list[str] = Field(description="3-6 extra topical hashtags without the # sign.")


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


LANGUAGE_NAMES = {"tr": "Turkish", "en": "English", "de": "German", "es": "Spanish", "fr": "French", "ar": "Arabic"}


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code.lower(), code)


def build_prompt(channel: Channel, theme: str, past: list[str]) -> str:
    chars = "\n".join(
        f"- {c.name} (in ilk_kare and video_prompt ALWAYS call them \"{c.alias}\"): {c.description}"
        for c in channel.characters
    )
    rules = "\n".join(f"- {r}" for r in channel.extra_rules)
    past_block = "\n".join(f"- {s}" for s in past) or "- (none yet)"
    return f"""You write scripts for "{channel.name}", a short-form absurd shitpost channel (YouTube Shorts, TikTok, Reels).

CHARACTERS (describe them exactly like this; the video model blocks anything resembling copyrighted
characters, so never mention real franchises, brands or superheroes, and use only the given alias in
ilk_kare and video_prompt; the real names may appear only in baslik and aciklama):
{chars}

VISUAL STYLE:
{channel.style}

TODAY'S SETTING: {theme}

RULES:
- One single 8-second scene. Hook in the first second, absurd twist, punchline at the end.
- Max 2-3 very short dialogue lines total, spoken in {language_name(channel.language)}. Write the video
  prompt itself in English, but put the dialogue lines in quotes in {language_name(channel.language)} and say
  explicitly that the characters speak {language_name(channel.language)}.
- Write "baslik" and "aciklama" in {language_name(channel.language)}, in natural slangy social-media style.
- Describe sound effects and ambience explicitly; no background music with lyrics.
- No on-screen text or subtitles in the video.
- The video model refuses anything that looks risky, so the humor must be 100% harmless: awkward, absurd,
  cringe, dumb misunderstandings. NO injuries, falls, crashes, explosions, fire, electricity, weapons,
  fights, violence, blood, dangerous stunts, heavy objects falling on anyone, choking, drugs or alcohol.
{rules}

ALREADY MADE - do NOT repeat these ideas, jokes or structures:
{past_block}
"""


def apply_aliases(channel: Channel, text: str) -> str:
    pairs = [
        (name, c.alias)
        for c in channel.characters
        if c.alias != c.name
        for name in [c.name, *c.other_names]
    ]
    if not pairs:
        return text
    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    lookup = {name.lower(): alias for name, alias in pairs}
    pattern = re.compile(r"(?<![\w-])(" + "|".join(re.escape(n) for n, _ in pairs) + r")(?![\w-])", re.IGNORECASE)
    return pattern.sub(lambda m: lookup[m.group(1).lower()], text)


def build_chatgpt_request(channel: Channel) -> str:
    return channel.scenario["chatgpt_mesaj"]


def clean_chatgpt_output(text: str) -> str:
    lines = text.strip().splitlines()
    while lines and re.match(r"^\s*(thought for .*|.*için düşündü.*|.*saniye düşündü.*|düşünme süresi.*)$",
                             lines[0], re.IGNORECASE):
        lines.pop(0)
    text = "\n".join(lines)
    text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text.strip())
    text = re.sub(r"^(video )?prompt\s*:\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def _sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "!", "?")) else text + "."


def web_video_prompt(channel: Channel, scenario: Scenario, *, aliases: bool = True) -> str:
    if not scenario.ilk_kare:
        text = scenario.video_prompt.strip()
        if not aliases:
            return text
        renamed = [c for c in channel.characters if c.alias != c.name]
        intro = " ".join(f"{c.alias[:1].upper() + c.alias[1:]} is {c.description.rstrip('.')}." for c in renamed)
        return f"{intro} {apply_aliases(channel, text)}".strip()
    chars = " ".join(f"{c.alias} is {c.description}." for c in channel.characters)
    return (
        f"Generate a video. Vertical 9:16, 8 seconds, with sound. "
        f"Characters: {chars} Style: {channel.style.rstrip('.')}. "
        f"Opening shot: {_sentence(apply_aliases(channel, scenario.ilk_kare))} "
        f"Action: {_sentence(apply_aliases(channel, scenario.video_prompt))} "
        f"All spoken dialogue is in {language_name(channel.language)}. "
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


def _generate_with_retry(client, model: str, contents, config, delays=None, quiet=False):
    models = [model] + [m for m in FALLBACK_TEXT_MODELS if m != model]
    last_error = None
    for delay in [0, *(RETRY_DELAYS if delays is None else delays)]:
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
                    if not quiet:
                        print(f"'{m}' yoğun ({e.code}), başka model deneniyor...")
                else:
                    raise
        if not models:
            break
    raise last_error


META_TIMEOUT_SECONDS = 90


def _with_deadline(fn, seconds: float):
    """fn'i en fazla `seconds` saniye bekler; takılırsa TimeoutError (iş arka planda bırakılır)."""
    import threading

    box = {}

    def run():
        try:
            box["value"] = fn()
        except BaseException as e:
            box["error"] = e

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive():
        raise TimeoutError(f"{int(seconds)} sn içinde cevap gelmedi")
    if "error" in box:
        raise box["error"]
    return box["value"]


def write_scenario(client, channel: Channel, theme: str, *, log=print, debug_dir=None) -> Scenario:
    if channel.scenario["motor"] == "chatgpt_web":
        return _write_scenario_chatgpt(client, channel, theme, log=log, debug_dir=debug_dir)
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


def _write_scenario_chatgpt(client, channel: Channel, theme: str, *, log=print, debug_dir=None) -> Scenario:
    import os

    from . import accounts, chatgpt_web

    profile = os.environ.get("CHATGPT_PROFILI") or accounts.publish_profile()
    raw = chatgpt_web.ask(profile, build_chatgpt_request(channel),
                          url=channel.scenario["chatgpt_url"], project=channel.scenario.get("chatgpt_proje", ""),
                          log=log, debug_dir=debug_dir)
    video_prompt = clean_chatgpt_output(raw)
    if len(video_prompt) < 40:
        raise RuntimeError(f"ChatGPT'den anlamlı bir prompt gelmedi: {raw[:200]!r}")
    log(f"ChatGPT promptu ({len(video_prompt)} karakter): {video_prompt[:150]}...")

    lang = language_name(channel.language)
    meta_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=Meta,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    names = ", ".join(f"{c.alias} = {c.name}" for c in channel.characters)
    prompt = (
        f"This is the video prompt of a short shitpost video for the channel \"{channel.name}\". "
        f"Character names in the post may use the real names ({names}). Write baslik and aciklama in "
        f"natural slangy {lang} social-media style, ozet as one English sentence, and 3-6 hashtags.\n\n"
        f"VIDEO PROMPT:\n{video_prompt}"
    )
    log("Başlık/açıklama yazılıyor (en fazla 90 sn)...")
    try:
        resp = _with_deadline(lambda: _generate_with_retry(client, channel.models["metin"], prompt, meta_config,
                                                           delays=[], quiet=True), META_TIMEOUT_SECONDS)
        meta = resp.parsed if isinstance(resp.parsed, Meta) else Meta.model_validate_json(resp.text)
    except Exception as e:
        log(f"(Başlık yazan API şu an yoğun, basit başlık kullanılıyor. Videoyu etkilemez.) [{str(e)[:60]}]")
        meta = Meta(baslik=channel.name, aciklama="", ozet=video_prompt[:200], hashtagler=[])
    return Scenario(baslik=meta.baslik, aciklama=meta.aciklama, ozet=meta.ozet, ilk_kare="",
                    video_prompt=video_prompt, hashtagler=meta.hashtagler)
