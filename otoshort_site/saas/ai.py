"""Yapay zeka katmanı: senaryo/başlık yazımı (Gemini metin) ve video üretimi (Veo)."""
import json
import subprocess
import time
from dataclasses import dataclass, field
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
    shots: list[str] = field(default_factory=list)  # çok sahneli videoda sahne başına Veo komutu


def fit_shots(shots: list[str], fallback: str, n: int) -> list[str]:
    """Tam n sahne komutu: eksikse son sahne devam ettirilir, fazlası atılır."""
    shots = shots[:n] or [fallback]
    while len(shots) < n:
        shots.append(shots[-1] + " Continue the same scene with the same characters.")
    return shots


RULES = (
    "Rules: family-friendly; match the tone the user asks for (funny by default; promotional, educational, "
    "emotional or calm if the idea calls for it); nobody gets seriously hurt; no real people or celebrities; "
    "no copyrighted or trademarked characters, brands or logos of others (if the user names one, replace it with "
    "an original look-alike-free character); the user's own business or product may be named in the dialogue; "
    "no swearing; no on-screen text, subtitles, watermarks, usernames or social media interface in the video."
)


def build_script_request(*, idea: str, characters: str, style: str, language: str, past: list[str],
                         has_ref: bool = False, seconds: int = 8, clips: list[int] | None = None) -> str:
    lang = config.LANGUAGES.get(language, language)
    style_desc = config.STYLES.get(style, style)
    clips = clips or [seconds]
    parts = [
        f"Write one {seconds}-second vertical (9:16) short video for TikTok/Reels/Shorts.",
        f"Visual style: {style_desc}.",
        f"Characters: {characters.strip() or 'invent 1-2 memorable original characters'}.",
        *(["A reference image of the main character is provided to the video model: describe that character "
           "consistently and keep its exact look (do not invent a different design)."] if has_ref else []),
        f"Idea from the user: {idea.strip()}" if idea.strip() else "Invent a fresh, funny, surprising idea.",
        f"Spoken dialogue language: {lang}.",
        RULES,
        *([f"The video model makes at most {max(clips)} seconds at a time, so tell it in {len(clips)} consecutive "
           f"shots of {', '.join(map(str, clips))} seconds that are joined into one video. Return shots: an array of "
           f"exactly {len(clips)} detailed English Veo prompts, one per shot, in order. Each shot prompt must be "
           "self-contained: repeat the full look of every character and the setting word for word so they stay "
           "identical, continue the story from the previous shot, and include only the dialogue lines (in "
           f"{lang}) that fit that shot's length. Hook in shot 1, payoff or call-to-action in the last shot."]
          if len(clips) > 1 else []),
        "Return JSON with: video_prompt (a detailed English prompt for the Veo video model: describe "
        "characters' look, setting, camera, action beat by beat, sound effects and the exact dialogue lines in "
        f"{lang}; strong hook in the first second, punchline at the end"
        + ("; for a multi-shot video a one-paragraph overview of the whole video" if len(clips) > 1 else "") +
        f"), title (max 50 chars, in {lang}, 1-2 emojis), caption (one short line in {lang} with 1-3 emojis, no "
        "hashtags), hashtags (3-6 words without #), summary (one English sentence).",
    ]
    if past:
        parts.append("Do NOT repeat these earlier ideas:\n- " + "\n- ".join(past[-30:]))
    return "\n".join(parts)


def build_preview_request(idea: str, language: str) -> str:
    """Ana sayfadaki kayıtsız deneme: video üretmeden, okunacak kısa senaryo (ucuz metin modeli)."""
    lang = config.LANGUAGES.get(language, language)
    return "\n".join([
        f"Write a funny {config.DURATION_SECONDS}-second vertical short video script (TikTok/Reels/Shorts) in {lang}.",
        f"Idea from the visitor: {idea.strip()}",
        RULES,
        f"Return JSON (all text in {lang}): title (viral, max 50 chars, 1-2 emojis), scene (1-2 sentences: setting, "
        "look of the characters, camera), lines (2-4 dialogue lines, each with who (short character name) and text "
        "(short, punchy); a strong hook first and a punchline last), caption (one short line with 1-2 emojis), "
        "hashtags (3-5 words without #).",
    ])


PREVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"}, "scene": {"type": "string"}, "caption": {"type": "string"},
        "lines": {"type": "array", "items": {"type": "object", "properties": {"who": {"type": "string"},
                                                                             "text": {"type": "string"}},
                                             "required": ["who", "text"]}},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "scene", "lines", "caption", "hashtags"],
}


def clean_preview(data: dict) -> dict:
    lines = [{"who": str(x.get("who", "")).strip()[:30], "text": str(x.get("text", "")).strip()[:160]}
             for x in (data.get("lines") or []) if str(x.get("text", "")).strip()][:4]
    return {"title": str(data.get("title", "")).strip()[:80], "scene": str(data.get("scene", "")).strip()[:400],
            "lines": lines, "caption": str(data.get("caption", "")).strip()[:160],
            "hashtags": [h.strip().lstrip("#")[:30] for h in (data.get("hashtags") or []) if h.strip()][:5]}


def build_channel_request(topic: str, language: str) -> str:
    """Ücretsiz kanal kurucu aracı: konudan kanal adı, açıklama, ilk videolar ve paylaşım planı (yalnızca metin)."""
    lang = config.LANGUAGES.get(language, language)
    return "\n".join([
        f"Plan a new faceless short-video channel (TikTok/Reels/Shorts) about: {topic.strip()}",
        f"Everything in {lang}. Videos are 8-30 second AI-generated vertical clips with original characters.",
        RULES,
        f"Return JSON (all text in {lang}): names (3 catchy, original channel names, max 24 chars each, no "
        "existing brands), bio (one-line channel bio, max 120 chars, 1 emoji), character (one original recurring "
        "character for the channel: look and personality in one sentence), ideas (5 different first video ideas, "
        "one sentence each, max 90 chars, no emojis), times (2-3 best posting times as HH:MM for a Turkish audience), "
        "hashtags (5 words without #).",
    ])


CHANNEL_SCHEMA = {
    "type": "object",
    "properties": {
        "names": {"type": "array", "items": {"type": "string"}}, "bio": {"type": "string"},
        "character": {"type": "string"}, "ideas": {"type": "array", "items": {"type": "string"}},
        "times": {"type": "array", "items": {"type": "string"}},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["names", "bio", "character", "ideas", "times", "hashtags"],
}


def clean_channel(data: dict) -> dict:
    import re

    def strs(key, n, limit):
        return [str(x).strip()[:limit] for x in (data.get(key) or []) if str(x).strip()][:n]

    times = [t for t in strs("times", 3, 5) if re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", t)] or ["12:00", "19:00"]
    return {"names": strs("names", 3, 30), "bio": str(data.get("bio", "")).strip()[:160],
            "character": str(data.get("character", "")).strip()[:300], "ideas": strs("ideas", 5, 120),
            "times": times, "hashtags": [h.lstrip("#") for h in strs("hashtags", 5, 30)]}


# ---------- viral formatlar: mesajlaşma hikâyesi ve itiraf/hikâye ----------
def build_chat_request(idea: str, language: str, seconds: int, past: list[str]) -> str:
    lang = config.LANGUAGES.get(language, language)
    n = max(6, min(18, round(seconds / 2.6)))
    parts = [
        f"Write a short, viral fake text-message conversation for a {seconds}-second vertical video "
        "(TikTok/Reels/Shorts). Two people text each other; it is read aloud with two voices.",
        f"Idea from the user: {idea.strip()}" if idea.strip() else "Invent a fresh, funny everyday situation.",
        f"All text in {lang}. About {n} messages, each max 90 characters, natural texting style. Hook in the "
        "first message, escalate, and end with a surprising or funny twist.",
        RULES.replace("no on-screen text, subtitles, watermarks, usernames or social media interface in the video.", ""),
        f"Return JSON (text in {lang}): contact (how the other person is saved in the phone, max 24 chars, e.g. "
        "a nickname), me_voice and contact_voice (female or male), messages (array of {me: true if sent by the "
        "phone owner, text}), title (max 50 chars, 1-2 emojis), caption (one short line, 1-3 emojis), hashtags "
        "(3-6 words without #), summary (one English sentence).",
    ]
    if past:
        parts.append("Do NOT repeat these earlier ideas:\n- " + "\n- ".join(past[-20:]))
    return "\n".join(parts)


CHAT_SCHEMA = {
    "type": "object",
    "properties": {
        "contact": {"type": "string"}, "me_voice": {"type": "string"}, "contact_voice": {"type": "string"},
        "messages": {"type": "array", "items": {"type": "object", "properties": {
            "me": {"type": "boolean"}, "text": {"type": "string"}}, "required": ["me", "text"]}},
        "title": {"type": "string"}, "caption": {"type": "string"}, "summary": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["contact", "messages", "title", "caption", "hashtags", "summary"],
}


def build_story_request(idea: str, language: str, seconds: int, past: list[str]) -> str:
    lang = config.LANGUAGES.get(language, language)
    words = max(40, min(170, round(seconds * 2.5)))
    parts = [
        f"Write a gripping first-person story for a {seconds}-second vertical narrated video in the style of "
        "anonymous confession / story forums. It is read aloud by one narrator with big word-by-word subtitles.",
        f"Idea from the user: {idea.strip()}" if idea.strip() else "Invent a fresh, surprising everyday story.",
        f"All text in {lang}. About {words} words in total. The first sentence is the post title: a strong hook. "
        "Then short sentences that build suspense, ending with a twist.",
        RULES.replace("no on-screen text, subtitles, watermarks, usernames or social media interface in the video.", ""),
        f"Return JSON (text in {lang}): community (a short forum-like name such as Confessions or Weird stories, "
        "max 22 chars, no real brand names), voice (female or male), sentences (array; sentences[0] is the post "
        "title), title (max 50 chars, 1-2 emojis), caption (one short line, 1-3 emojis), hashtags (3-6 words "
        "without #), summary (one English sentence).",
    ]
    if past:
        parts.append("Do NOT repeat these earlier ideas:\n- " + "\n- ".join(past[-20:]))
    return "\n".join(parts)


STORY_SCHEMA = {
    "type": "object",
    "properties": {
        "community": {"type": "string"}, "voice": {"type": "string"},
        "sentences": {"type": "array", "items": {"type": "string"}},
        "title": {"type": "string"}, "caption": {"type": "string"}, "summary": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["community", "sentences", "title", "caption", "hashtags", "summary"],
}


FORMAT_RETURN_TAIL = ("title (max 50 chars, 1-2 emojis), hashtags (3-6 words without #), "
                      "summary (one English sentence).")


def build_wyr_request(idea: str, language: str, seconds: int, past: list[str]) -> str:
    lang = config.LANGUAGES.get(language, language)
    n = max(3, min(8, round(seconds / 6.5)))
    parts = [
        f"Write a viral 'Would you rather' game for a {seconds}-second vertical video (TikTok/Reels/Shorts). Each "
        "round shows two options on a split screen, a narrator reads them, then viewers get 3 seconds to pick.",
        f"Theme from the user: {idea.strip()}" if idea.strip() else "Pick a fun, relatable theme.",
        f"All text in {lang}. Exactly {n} rounds. Each option max 60 characters, concrete and vivid, written so it "
        "completes 'Would you rather...'. Both options equally tempting (or equally painful) so the choice is hard. "
        "Strong first round, hardest one last. Family-friendly: no violence, sexual content, real people or brands.",
        f"Return JSON (text in {lang}): voice (female or male), rounds (array of {{a, b}}), caption (one short line "
        "asking viewers to comment their picks, 1-3 emojis), " + FORMAT_RETURN_TAIL,
    ]
    if past:
        parts.append("Do NOT repeat these earlier ideas:\n- " + "\n- ".join(past[-20:]))
    return "\n".join(parts)


WYR_SCHEMA = {
    "type": "object",
    "properties": {
        "voice": {"type": "string"},
        "rounds": {"type": "array", "items": {"type": "object", "properties": {
            "a": {"type": "string"}, "b": {"type": "string"}}, "required": ["a", "b"]}},
        "title": {"type": "string"}, "caption": {"type": "string"}, "summary": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["rounds", "title", "caption", "hashtags", "summary"],
}


def build_quiz_request(idea: str, language: str, seconds: int, past: list[str]) -> str:
    lang = config.LANGUAGES.get(language, language)
    n = max(2, min(6, round(seconds / 10)))
    parts = [
        f"Write a viral trivia quiz for a {seconds}-second vertical video (TikTok/Reels/Shorts). Each question shows "
        "three options; a narrator reads it, viewers get 3 seconds to guess, then the right answer is revealed.",
        f"Topic from the user: {idea.strip()}" if idea.strip() else "Pick a fun general-knowledge topic.",
        f"All text in {lang}. Exactly {n} questions, from easy to hard. Question max 90 characters, each option max "
        "32 characters, exactly one correct option. Only well-known facts you are completely sure about; if unsure, "
        "pick another question. Family-friendly.",
        f"Return JSON (text in {lang}): topic (max 24 chars), voice (female or male), questions (array of "
        "{q, options: [3 strings], answer: index 0-2 of the correct option}), caption (one short line asking how "
        "many they got right, 1-3 emojis), " + FORMAT_RETURN_TAIL,
    ]
    if past:
        parts.append("Do NOT repeat these earlier ideas:\n- " + "\n- ".join(past[-20:]))
    return "\n".join(parts)


QUIZ_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"}, "voice": {"type": "string"},
        "questions": {"type": "array", "items": {"type": "object", "properties": {
            "q": {"type": "string"}, "options": {"type": "array", "items": {"type": "string"}},
            "answer": {"type": "integer"}}, "required": ["q", "options", "answer"]}},
        "title": {"type": "string"}, "caption": {"type": "string"}, "summary": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["topic", "questions", "title", "caption", "hashtags", "summary"],
}
FORMAT_REQUESTS = {"sohbet": (build_chat_request, CHAT_SCHEMA), "hikaye": (build_story_request, STORY_SCHEMA),
                   "secim": (build_wyr_request, WYR_SCHEMA), "quiz": (build_quiz_request, QUIZ_SCHEMA)}


def clean_format(kind: str, data: dict) -> dict:
    """Yapay zekânın döndürdüğü yazışma/hikâye/seçim/quiz metnini güvenli sınırlara getirir."""
    common = {"title": str(data.get("title", "")).strip()[:120], "caption": str(data.get("caption", "")).strip()[:300],
              "summary": str(data.get("summary", "")).strip()[:300],
              "hashtags": [str(h).strip().lstrip("#")[:30] for h in data.get("hashtags") or [] if str(h).strip()][:8]}
    voice = lambda v, d: v if v in ("female", "male") else d  # noqa: E731
    if kind == "sohbet":
        msgs = [{"me": bool(m.get("me")), "text": str(m.get("text", "")).strip()[:160]}
                for m in data.get("messages") or [] if isinstance(m, dict) and str(m.get("text", "")).strip()][:24]
        return {**common, "contact": str(data.get("contact", "")).strip()[:30] or "?", "messages": msgs,
                "me_voice": voice(data.get("me_voice"), "female"), "contact_voice": voice(data.get("contact_voice"), "male")}
    if kind == "secim":
        rounds = [{"a": str(r.get("a", "")).strip()[:80], "b": str(r.get("b", "")).strip()[:80]}
                  for r in data.get("rounds") or [] if isinstance(r, dict)]
        return {**common, "rounds": [r for r in rounds if r["a"] and r["b"]][:10],
                "voice": voice(data.get("voice"), "female")}
    if kind == "quiz":
        qs = []
        for q in data.get("questions") or []:
            if not isinstance(q, dict):
                continue
            opts = [str(o).strip()[:48] for o in q.get("options") or [] if str(o).strip()][:3]
            try:
                answer = int(q.get("answer"))
            except (TypeError, ValueError):
                continue
            text = str(q.get("q", "")).strip()[:140]
            if text and len(opts) == 3 and 0 <= answer < 3:
                qs.append({"q": text, "options": opts, "answer": answer})
        return {**common, "topic": str(data.get("topic", "")).strip()[:30], "questions": qs[:8],
                "voice": voice(data.get("voice"), "male")}
    sents = [str(x).strip()[:300] for x in data.get("sentences") or [] if str(x).strip()][:40]
    return {**common, "community": str(data.get("community", "")).strip()[:30] or "?", "sentences": sents,
            "voice": voice(data.get("voice"), "male")}


VOICES = {"female": ("Kore", "Leda"), "male": ("Puck", "Charon")}  # Gemini hazır sesleri


IDEA_POOL = [
    "Kedi, sahibinin online toplantısına gizlice katılıp patronu yönetmeye çalışıyor",
    "Dinozor ilk kez metrobüse biniyor ve kuyruğu kapıya sıkışıyor",
    "Robot, Türk düğününde halaya kalkıp halayın başını kapıyor",
    "Penguen, plajda güneş kremi satmaya çalışıyor ama kimse almıyor",
    "Portakal ve muz markette son indirimli ürün için kavga ediyor",
    "Kaplumbağa, kargo kuryesi olarak ilk gününde rekor kırmaya çalışıyor",
    "Uzaylı, Kapalıçarşı'da halı için pazarlık yapıyor",
    "Pizza dilimi diyete başlamaya karar veriyor, salata ona koçluk yapıyor",
    "Kurbağa, bilgi yarışmasında son soruda jokerini annesine harcıyor",
    "Ayı, kış uykusundan erken uyanıp alarmı kimin kurduğunu arıyor",
    "Simit, çayla ilk buluşmasında heyecandan susamlarını döküyor",
    "Kar tanesi, yaz tatiline çıkmak için çanta hazırlıyor",
    "Baykuş, gece vardiyasından sonra sabah kahvesini bulamıyor",
    "Patates, spor salonunda kızartma olmamak için mekik çekiyor",
    "Çaydanlık, misafir gelmeden önce panikle demleniyor",
    "Martı, vapurda simit çalmak için ustalık sınıfı açıyor",
]


class RealAI:
    def __init__(self, client=None):
        if client is None:
            from google import genai
            from google.genai import types

            client = genai.Client(http_options=types.HttpOptions(timeout=120_000))
        self.client = client

    def write_script(self, *, idea, characters, style, language, past, has_ref=False, seconds=8,
                     clips=None) -> Script:
        from google.genai import types

        clips = clips or [seconds]
        schema = {
            "type": "object",
            "properties": {
                "video_prompt": {"type": "string"}, "title": {"type": "string"},
                "caption": {"type": "string"}, "summary": {"type": "string"},
                "hashtags": {"type": "array", "items": {"type": "string"}},
                **({"shots": {"type": "array", "items": {"type": "string"}}} if len(clips) > 1 else {}),
            },
            "required": ["video_prompt", "title", "caption", "hashtags", "summary",
                         *(["shots"] if len(clips) > 1 else [])],
        }
        resp = self.client.models.generate_content(
            model=config.TEXT_MODEL,
            contents=build_script_request(idea=idea, characters=characters, style=style, language=language,
                                          past=past, has_ref=has_ref, seconds=seconds, clips=clips),
            config=types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=schema,
                                               temperature=1.1),
        )
        data = json.loads(resp.text)
        return Script(
            video_prompt=data["video_prompt"].strip(), title=data["title"].strip()[:120],
            caption=data["caption"].strip(), summary=data["summary"].strip(),
            hashtags=[h.strip().lstrip("#") for h in data.get("hashtags", []) if h.strip()][:8],
            shots=fit_shots([str(x).strip() for x in data.get("shots") or [] if str(x).strip()],
                            data["video_prompt"].strip(), len(clips)),
        )

    def preview(self, *, idea: str, language: str) -> dict:
        """Kayıtsız ziyaretçiye okunacak kısa senaryo (video üretmez)."""
        from google.genai import types

        resp = self.client.models.generate_content(
            model=config.TEXT_MODEL, contents=build_preview_request(idea, language),
            config=types.GenerateContentConfig(response_mime_type="application/json",
                                               response_json_schema=PREVIEW_SCHEMA, temperature=1.0),
        )
        return clean_preview(json.loads(resp.text))

    def write_format(self, *, kind: str, idea: str, language: str, seconds: int, past: list[str]) -> dict:
        """Viral format metni: sohbet (yazışma), hikaye (itiraf), secim (hangisini seçerdin), quiz (bil bakalım)."""
        from google.genai import types

        req, schema = FORMAT_REQUESTS[kind]
        resp = self.client.models.generate_content(
            model=config.TEXT_MODEL, contents=req(idea, language, seconds, past),
            config=types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=schema,
                                               temperature=1.1))
        return clean_format(kind, json.loads(resp.text))

    def speak(self, *, text: str, voice: str, out: Path) -> Path:
        """Gemini seslendirme (TTS): metni seçilen hazır sesle okur, 24 kHz WAV kaydeder."""
        import wave

        from google.genai import types

        resp = self.client.models.generate_content(
            model=config.TTS_MODEL, contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)))))
        pcm = resp.candidates[0].content.parts[0].inline_data.data
        out.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(pcm)
        return out

    def channel_plan(self, *, topic: str, language: str) -> dict:
        """Ücretsiz kanal kurucu: kanal adı, açıklama, karakter, ilk 5 video ve saatler (video üretmez)."""
        from google.genai import types

        resp = self.client.models.generate_content(
            model=config.TEXT_MODEL, contents=build_channel_request(topic, language),
            config=types.GenerateContentConfig(response_mime_type="application/json",
                                               response_json_schema=CHANNEL_SCHEMA, temperature=1.0),
        )
        return clean_channel(json.loads(resp.text))

    def ideas(self, *, topic: str, language: str, past: list[str], n: int = 4) -> list[str]:
        """Kullanıcıya fikir önerir (ucuz metin modeli; video üretmez)."""
        from google.genai import types

        lang = config.LANGUAGES.get(language, language)
        prompt = (f"Suggest {n} short, funny, original ideas for {config.DURATION_SECONDS}-second vertical comedy videos "
                  f"(TikTok/Reels/Shorts). Write each idea as one sentence in {lang}, max 90 characters, no hashtags, "
                  "no emojis. " + (f"Theme from the user: {topic.strip()}. " if topic.strip() else
                                   "Pick varied everyday-life themes. ") + RULES)
        if past:
            prompt += "\nAvoid these earlier ideas:\n- " + "\n- ".join(past[-20:])
        schema = {"type": "object", "properties": {"ideas": {"type": "array", "items": {"type": "string"}}},
                  "required": ["ideas"]}
        resp = self.client.models.generate_content(
            model=config.TEXT_MODEL, contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=schema,
                                               temperature=1.2))
        return [i.strip() for i in json.loads(resp.text).get("ideas", []) if i.strip()][:n]

    def transcribe(self, *, video: Path, language: str, words: bool = False) -> list[dict]:
        """Videodaki konuşmaları zaman damgalı döker: [{"start": sn, "end": sn, "text": "..."}]
        words=True: her segmentte kelime zamanları da istenir ("words": [{"text","start","end"}]; viral altyazı için)."""
        from google.genai import types

        lang = config.LANGUAGES.get(language, language)
        props = {"start": {"type": "number"}, "end": {"type": "number"}, "text": {"type": "string"}}
        if words:
            props["words"] = {"type": "array", "items": {"type": "object", "properties": {
                "text": {"type": "string"}, "start": {"type": "number"}, "end": {"type": "number"}},
                "required": ["text", "start", "end"]}}
        schema = {"type": "object", "properties": {"segments": {"type": "array", "items": {
            "type": "object", "properties": props, "required": ["start", "end", "text"]}}}, "required": ["segments"]}
        resp = self.client.models.generate_content(
            model=config.TEXT_MODEL,
            contents=[types.Part.from_bytes(data=video.read_bytes(), mime_type="video/mp4"),
                      f"Transcribe every spoken line in this video exactly as spoken (language: {lang}). Split into short "
                      "subtitle segments of at most 6 words with precise start/end times in seconds. "
                      + ("For each segment also list every word with its own precise start/end time in seconds. "
                         if words else "") +
                      "Ignore music and sound effects. If nobody speaks, return an empty list."],
            config=types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=schema,
                                               temperature=0))
        return [seg for seg in json.loads(resp.text).get("segments", []) if str(seg.get("text", "")).strip()]

    def make_video(self, *, prompt: str, quality: str, out: Path, refs: list[Path] | None = None,
                   seconds: int = 8, poll_s: int = 10, timeout_s: int = 900) -> Path:
        """Kalitenin ayarlı sağlayıcısıyla (Google Veo ya da fal.ai) bir sahneyi üretip out'a kaydeder."""
        name, model = config.provider(quality)
        refs = list(refs or [])[:3]
        if name == "fal":
            return FalVideo().make(quality=quality, model=model, prompt=prompt, out=out, refs=refs,
                                   seconds=seconds, poll_s=poll_s, timeout_s=timeout_s)
        return self._veo(model=model, prompt=prompt, quality=quality, out=out, refs=refs, seconds=seconds,
                         poll_s=poll_s, timeout_s=timeout_s)

    def _veo(self, *, model: str, prompt: str, quality: str, out: Path, refs: list[Path], seconds: int,
             poll_s: int, timeout_s: int) -> Path:
        from google.genai import types

        q = config.QUALITIES[quality]
        extra = {}
        if refs:  # referans karakter: videoda aynı görünüm korunur
            extra["reference_images"] = [
                types.VideoGenerationReferenceImage(image=types.Image(image_bytes=r.read_bytes(), mime_type="image/png"),
                                                    reference_type=types.VideoGenerationReferenceType.ASSET)
                for r in refs]
        op = self.client.models.generate_videos(
            model=model,
            prompt=prompt,
            config=types.GenerateVideosConfig(
                aspect_ratio="9:16", resolution=q["resolution"], duration_seconds=seconds,
                negative_prompt=NEGATIVE, number_of_videos=1, **extra,
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


NEGATIVE = "watermark, logo, text, subtitles, captions, username, social media interface"


class FalVideo:
    """fal.ai kuyruk API'si: tek anahtarla Kling, Hailuo, Wan, Seedance gibi modeller.
    POST https://queue.fal.run/<uç nokta> → durum adresini yokla → sonuç JSON'undaki video.url'i indir."""
    BASE = "https://queue.fal.run"

    def __init__(self, session=None, key: str | None = None):
        import requests

        self.http = session or requests.Session()
        self.key = key if key is not None else config.FAL_KEY
        if not self.key:
            raise RuntimeError("FAL_KEY ayarlı değil")

    def _headers(self) -> dict:
        return {"Authorization": f"Key {self.key}", "Content-Type": "application/json"}

    def payload(self, quality: str, prompt: str, refs: list[Path], seconds: int = 8) -> dict:
        import base64

        data = {"prompt": prompt, "aspect_ratio": "9:16", "duration": str(seconds),
                "negative_prompt": NEGATIVE, "generate_audio": True}
        if config.QUALITIES[quality]["args"]:
            data.update(json.loads(config.QUALITIES[quality]["args"]))
        if refs:
            data["image_url"] = "data:image/png;base64," + base64.b64encode(refs[0].read_bytes()).decode()
        return data

    def make(self, *, quality: str, model: str, prompt: str, out: Path, refs: list[Path], seconds: int = 8,
             poll_s: int = 10, timeout_s: int = 900) -> Path:
        endpoint = config.QUALITIES[quality]["ref_model"] if refs and config.QUALITIES[quality]["ref_model"] else model
        r = self.http.post(f"{self.BASE}/{endpoint}", headers=self._headers(),
                           json=self.payload(quality, prompt, refs if endpoint != model else [], seconds), timeout=60)
        self._check(r)
        job = r.json()
        start = time.time()
        while True:
            st = self.http.get(job["status_url"], headers=self._headers(), timeout=30)
            self._check(st)
            status = st.json().get("status")
            if status == "COMPLETED":
                break
            if status in ("FAILED", "ERROR", "CANCELLED"):
                raise RuntimeError(f"fal.ai hatası: {st.text[:300]}")
            if time.time() - start > timeout_s:
                raise TimeoutError("Video üretimi zaman aşımına uğradı")
            time.sleep(poll_s)
        res = self.http.get(job["response_url"], headers=self._headers(), timeout=60)
        self._check(res)
        url = ((res.json() or {}).get("video") or {}).get("url")
        if not url:
            raise ContentBlocked("fal.ai video döndürmedi")
        out.parent.mkdir(parents=True, exist_ok=True)
        with self.http.get(url, stream=True, timeout=300) as dl:
            self._check(dl)
            with open(out, "wb") as f:
                for chunk in dl.iter_content(1 << 16):
                    f.write(chunk)
        return out

    @staticmethod
    def _check(r) -> None:
        if r.status_code < 400:
            return
        body = r.text[:300]
        if r.status_code == 422 and any(w in body.lower() for w in ("content", "policy", "safety", "nsfw")):
            raise ContentBlocked(body)
        raise RuntimeError(f"fal.ai {r.status_code}: {body}")


class FakeAI:
    """API'ye gitmeden çalışan sahte üretici (geliştirme ve testler için)."""

    def __init__(self, fail_with: Exception | None = None, pretty: bool = False):
        self.fail_with = fail_with
        self.pretty = pretty  # True: karakterli demo klip (~10 sn sürer); False: hızlı test görüntüsü
        self.calls = 0

    def write_script(self, *, idea, characters, style, language, past, has_ref=False, seconds=8,
                     clips=None) -> Script:
        self.calls += 1
        n = len(past) + 1
        prompt = f"[sahte] {idea or 'rastgele fikir'} #{n}"
        return Script(video_prompt=prompt, title=f"Deneme videosu {n} 😂",
                      caption="Bu bir deneme 💀", hashtags=["deneme", "shorts"], summary=f"fake idea {n}",
                      shots=[f"{prompt} · sahne {i + 1}" for i in range(len(clips or [seconds]))])

    def preview(self, *, idea: str, language: str) -> dict:
        """Sahte mod: fikirden kalıp senaryo (demo; gerçek sürümde yapay zekâ yazar)."""
        import random

        idea = idea.strip().rstrip(".!") or "Kedi markette kasiyerle tartışıyor"
        rnd = random.Random(idea)
        if language == "en":
            lines = [("Hero", "Wait. Nobody told me about this!"), ("Sidekick", "Act natural. Everyone's looking."),
                     ("Hero", "I AM acting natural!"), ("Sidekick", "...that's what worries me.")]
            return {"title": f"{idea[:40]} 😂", "scene": f"Close-up, bright daylight. {idea}. The camera zooms in on "
                    "the main character's shocked face.", "lines": [{"who": w, "text": x} for w, x in lines[:rnd.choice([3, 4])]],
                    "caption": "Wait for the ending 😭", "hashtags": ["funny", "shorts", "ai", "viral"]}
        lines = [("Kahraman", "Bir dakika... Bunu kimse bana söylemedi!"), ("Yan karakter", "Sakin ol, herkes bize bakıyor."),
                 ("Kahraman", "Ben zaten sakinim!"), ("Yan karakter", "...asıl korktuğum da bu.")]
        return {"title": f"{idea[:40]} 😂", "scene": f"Gün ışığı, yakın çekim. {idea}. Kamera ana karakterin "
                "şaşkın yüzüne yaklaşıyor.", "lines": [{"who": w, "text": x} for w, x in lines[:rnd.choice([3, 4])]],
                "caption": "Sonunu bekle 😭", "hashtags": ["komik", "shorts", "yapayzeka", "viral"]}

    def write_format(self, *, kind: str, idea: str, language: str, seconds: int, past: list[str]) -> dict:
        """Sahte mod: kalıp yazışma / hikâye (demo)."""
        self.calls += 1
        n = len(past) + 1
        idea = (idea or "").strip().rstrip(".!")
        common = {"title": f"Deneme {n}: {idea[:30] or 'yazışma'} 😂", "caption": "Sonunu bekle 😭",
                  "hashtags": ["deneme", "shorts"], "summary": f"fake {kind} {n}"}
        if kind == "sohbet":
            msgs = [(False, "Kanka buzdolabındaki son dilim pizzayı kim yedi?"), (True, "Bilmiyorum, belki kedi?"),
                    (False, "Bizim kedimiz yok."), (True, "O zaman sorunu çözdük, bu bir hayalet"),
                    (False, "Hayalet ağzında peynirle mi geziyor?"), (True, "Moda böyle artık"),
                    (False, "Haftaya pizza parası senden.")]
            if idea:
                msgs.insert(0, (False, idea[:80] + "?"))
            return clean_format(kind, {**common, "contact": "Ahmet (ev arkadaşı)", "me_voice": "female",
                                       "contact_voice": "male", "messages": [{"me": m, "text": t} for m, t in msgs]})
        if kind == "secim":
            rounds = [("Her sabah 5'te uyanmak", "Her gece 3'te uyumak"), ("Uçabilmek ama sadece 1 metre",
                      "Görünmez olmak ama sadece sen bakmazken"), ("Bir yıl internetsiz", "Bir yıl tatlısız"),
                      ("Bütün dilleri konuşmak", "Bütün hayvanlarla konuşmak")]
            return clean_format(kind, {**common, "voice": "female", "rounds": [{"a": a, "b": b} for a, b in rounds]})
        if kind == "quiz":
            qs = [("Dünyanın en büyük okyanusu hangisi?", ["Atlas Okyanusu", "Büyük Okyanus", "Hint Okyanusu"], 1),
                  ("Bir yılda kaç hafta vardır?", ["48", "52", "56"], 1),
                  ("Güneş sistemindeki en büyük gezegen hangisi?", ["Jüpiter", "Satürn", "Neptün"], 0)]
            return clean_format(kind, {**common, "topic": idea[:24] or "Genel kültür", "voice": "male",
                                       "questions": [{"q": q, "options": o, "answer": a} for q, o, a in qs]})
        sents = [idea or "Ev arkadaşım üç aydır benim yoğurdumu yiyordu ve bunu nasıl öğrendiğime inanamayacaksınız",
                 "Her sabah buzdolabını açtığımda yoğurdum biraz daha azalıyordu.",
                 "Bir gün kabın altına küçük bir not yazdım: Seni görüyorum.",
                 "Ertesi sabah notun altına cevap yazılmıştı: Ben de seni."]
        return clean_format(kind, {**common, "community": "İtiraf köşesi", "voice": "male", "sentences": sents})

    def speak(self, *, text: str, voice: str, out: Path) -> Path:
        from .formatlar import fake_voice

        return fake_voice(text, out, 0 if voice in VOICES["female"] else 1)

    def channel_plan(self, *, topic: str, language: str) -> dict:
        """Sahte mod: konudan kalıp kanal planı (demo)."""
        t = topic.strip().rstrip(".!") or "Komik hayvanlar"
        short = t.split()[0].capitalize()[:12]
        if language == "en":
            return clean_channel({
                "names": [f"{short} Daily", f"The {short} Show", f"{short} Unfiltered"],
                "bio": f"Short, funny {t.lower()} stories every day 🎬",
                "character": f"A clumsy but lovable host obsessed with {t.lower()}, always one step from disaster.",
                "ideas": [f"{short} tries something new for the first time", f"A day in the life: {t.lower()} edition",
                          f"{short} vs Monday morning", f"The worst {t.lower()} advice ever",
                          f"{short} meets an unexpected rival"],
                "times": ["12:00", "19:00", "21:30"], "hashtags": [short.lower(), "funny", "shorts", "ai", "daily"]})
        return clean_channel({
            "names": [f"Günlük {short}", f"{short} Hikâyeleri", f"{short} Kafası"],
            "bio": f"Her gün kısa ve komik {t.lower()} hikâyeleri 🎬",
            "character": f"{t} konusuna takıntılı, sakar ama sevimli bir anlatıcı; her seferinde felakete bir adım uzakta.",
            "ideas": [f"{short} ilk kez yeni bir şey deniyor", f"{t}: bir günün hikâyesi",
                      f"{short} pazartesi sabahına karşı", f"{t} hakkında verilmiş en kötü tavsiye",
                      f"{short} beklenmedik bir rakiple karşılaşıyor"],
            "times": ["12:00", "19:00", "21:30"], "hashtags": [short.lower(), "komik", "shorts", "yapayzeka", "keşfet"]})

    def ideas(self, *, topic: str, language: str, past: list[str], n: int = 4) -> list[str]:
        import random

        return random.sample(IDEA_POOL, n)

    def transcribe(self, *, video: Path, language: str, words: bool = False) -> list[dict]:
        return [{"start": 0.3, "end": 2.6, "text": "Bu son indirim benim!"},
                {"start": 2.8, "end": 5.4, "text": "Muz bile şahit"}, {"start": 5.6, "end": 7.8, "text": "Kasiyer nerede?!"}]

    def make_video(self, *, prompt: str, quality: str, out: Path, refs=None, seconds: int = 8, **_) -> Path:
        self.last_refs = list(refs or [])
        self.clip_seconds = [*getattr(self, "clip_seconds", []), seconds]
        if self.fail_with:
            raise self.fail_with
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            import imageio_ffmpeg

            src = _demo_clip_args(prompt, seconds) if self.pretty else [
                "-f", "lavfi", "-i", "testsrc=size=360x640:rate=10:duration=2"]
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
                            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", *src, "-shortest",
                            "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", str(out)],
                           check=True, timeout=120)
        except Exception:
            out.write_bytes(b"\x00" * 1024)
        return out


DEMO_PALETTES = [  # (arka plan üst, alt, karakter rengi) — sıcak, sinematik tonlar
    ("0xe9c9a0", "0x6b4a2c", (255, 138, 31)), ("0xa9c4c9", "0x2f4248", (240, 196, 92)),
    ("0xd9b8b0", "0x5a3438", (120, 196, 140)), ("0xc9c0a8", "0x3f3a2a", (232, 98, 74)),
]


def _demo_clip_args(seed: str, seconds: int = 8) -> list[str]:
    """Sahte mod için demo klip: degrade arka plan, zıplayan gözlü bir karakter.
    Hız için 270x480 / 15 fps çizilip 360x640'a büyütülür."""
    top, bottom, (cr, cg, cb) = DEMO_PALETTES[sum(map(ord, seed)) % len(DEMO_PALETTES)]
    k = 0.75
    n = lambda v: f"{v * k:g}"  # noqa: E731
    cy = f"({n(372)}-{n(70)}*abs(sin(T*2.6)))"
    shapes = [  # arkadan öne: (x, y, yarıçap_x, yarıçap_y, (r, g, b)); (0,0,0) = gölge
        (n(180), n(548), n(70), n(12), (0, 0, 0)),
        (n(180), cy, n(86), n(86), (cr, cg, cb)),
        (n(150), f"({cy}-{n(16)})", n(19), n(21), (255, 255, 255)),
        (n(210), f"({cy}-{n(16)})", n(19), n(21), (255, 255, 255)),
        (f"({n(153)}+{n(7)}*sin(T*1.3))", f"({cy}-{n(12)})", n(9), n(10), (25, 25, 35)),
        (f"({n(213)}+{n(7)}*sin(T*1.3))", f"({cy}-{n(12)})", n(9), n(10), (25, 25, 35)),
        (n(180), f"({cy}+{n(30)})", n(22), f"({n(4)}+{n(11)}*abs(sin(T*8)))", (80, 20, 35)),
    ]
    exprs = []
    for ch, base in ((0, "r(X,Y)"), (1, "g(X,Y)"), (2, "b(X,Y)")):
        e = base
        for x, y, rx, ry, col in shapes:
            val = f"{base}*0.7" if col == (0, 0, 0) else str(col[ch])
            e = f"if(lt(hypot((X-{x})/{rx},(Y-{y})/{ry}),1),{val},{e})"
        exprs.append(e)
    return ["-f", "lavfi", "-i", f"gradients=s=270x480:c0={top}:c1={bottom}:x0=0:y0=0:x1=270:y1=480:speed=0.015:"
            f"duration={seconds}:rate=15", "-vf", f"geq=r='{exprs[0]}':g='{exprs[1]}':b='{exprs[2]}',scale=360:640:flags=bicubic"]


def default_ai():
    return FakeAI(pretty=True) if config.FAKE_AI else RealAI()
