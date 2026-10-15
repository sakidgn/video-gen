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


def build_script_request(*, idea: str, characters: str, style: str, language: str, past: list[str],
                         has_ref: bool = False) -> str:
    lang = config.LANGUAGES.get(language, language)
    style_desc = config.STYLES.get(style, style)
    parts = [
        f"Write one {config.DURATION_SECONDS}-second vertical (9:16) short video for TikTok/Reels/Shorts.",
        f"Visual style: {style_desc}.",
        f"Characters: {characters.strip() or 'invent 1-2 memorable original characters'}.",
        *(["A reference image of the main character is provided to the video model: describe that character "
           "consistently and keep its exact look (do not invent a different design)."] if has_ref else []),
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

    def write_script(self, *, idea, characters, style, language, past, has_ref=False) -> Script:
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
                                          past=past, has_ref=has_ref),
            config=types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=schema,
                                               temperature=1.1),
        )
        data = json.loads(resp.text)
        return Script(
            video_prompt=data["video_prompt"].strip(), title=data["title"].strip()[:120],
            caption=data["caption"].strip(), summary=data["summary"].strip(),
            hashtags=[h.strip().lstrip("#") for h in data.get("hashtags", []) if h.strip()][:8],
        )

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

    def make_video(self, *, prompt: str, quality: str, out: Path, refs: list[Path] | None = None,
                   poll_s: int = 10, timeout_s: int = 900) -> Path:
        """Kalitenin ayarlı sağlayıcısıyla (Google Veo ya da fal.ai) videoyu üretip out'a kaydeder."""
        name, model = config.provider(quality)
        refs = list(refs or [])[:3]
        if name == "fal":
            return FalVideo().make(quality=quality, model=model, prompt=prompt, out=out, refs=refs,
                                   poll_s=poll_s, timeout_s=timeout_s)
        return self._veo(model=model, prompt=prompt, quality=quality, out=out, refs=refs, poll_s=poll_s,
                         timeout_s=timeout_s)

    def _veo(self, *, model: str, prompt: str, quality: str, out: Path, refs: list[Path], poll_s: int,
             timeout_s: int) -> Path:
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
                aspect_ratio="9:16", resolution=q["resolution"], duration_seconds=config.DURATION_SECONDS,
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

    def payload(self, quality: str, prompt: str, refs: list[Path]) -> dict:
        import base64

        data = {"prompt": prompt, "aspect_ratio": "9:16", "duration": str(config.DURATION_SECONDS),
                "negative_prompt": NEGATIVE, "generate_audio": True}
        if config.QUALITIES[quality]["args"]:
            data.update(json.loads(config.QUALITIES[quality]["args"]))
        if refs:
            data["image_url"] = "data:image/png;base64," + base64.b64encode(refs[0].read_bytes()).decode()
        return data

    def make(self, *, quality: str, model: str, prompt: str, out: Path, refs: list[Path], poll_s: int = 10,
             timeout_s: int = 900) -> Path:
        endpoint = config.QUALITIES[quality]["ref_model"] if refs and config.QUALITIES[quality]["ref_model"] else model
        r = self.http.post(f"{self.BASE}/{endpoint}", headers=self._headers(),
                           json=self.payload(quality, prompt, refs if endpoint != model else []), timeout=60)
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

    def write_script(self, *, idea, characters, style, language, past, has_ref=False) -> Script:
        self.calls += 1
        n = len(past) + 1
        return Script(video_prompt=f"[sahte] {idea or 'rastgele fikir'} #{n}", title=f"Deneme videosu {n} 😂",
                      caption="Bu bir deneme 💀", hashtags=["deneme", "shorts"], summary=f"fake idea {n}")

    def ideas(self, *, topic: str, language: str, past: list[str], n: int = 4) -> list[str]:
        import random

        return random.sample(IDEA_POOL, n)

    def make_video(self, *, prompt: str, quality: str, out: Path, refs=None, **_) -> Path:
        self.last_refs = list(refs or [])
        if self.fail_with:
            raise self.fail_with
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            import imageio_ffmpeg

            src = _demo_clip_args(prompt) if self.pretty else ["-f", "lavfi", "-i", "testsrc=size=360x640:rate=10:duration=2"]
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", *src,
                            "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", str(out)],
                           check=True, timeout=120)
        except Exception:
            out.write_bytes(b"\x00" * 1024)
        return out


DEMO_PALETTES = [  # (arka plan üst, alt, karakter rengi) — sıcak, sinematik tonlar
    ("0xe9c9a0", "0x6b4a2c", (255, 138, 31)), ("0xa9c4c9", "0x2f4248", (240, 196, 92)),
    ("0xd9b8b0", "0x5a3438", (120, 196, 140)), ("0xc9c0a8", "0x3f3a2a", (232, 98, 74)),
]


def _demo_clip_args(seed: str) -> list[str]:
    """Sahte mod için 8 sn'lik demo klip: degrade arka plan, zıplayan gözlü bir karakter.
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
            "duration=8:rate=15", "-vf", f"geq=r='{exprs[0]}':g='{exprs[1]}':b='{exprs[2]}',scale=360:640:flags=bicubic"]


def default_ai():
    return FakeAI(pretty=True) if config.FAKE_AI else RealAI()
