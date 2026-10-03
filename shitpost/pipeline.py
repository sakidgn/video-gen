import json
import time
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import accounts, history, images, postprocess, script, video_web
from .config import OUTPUT_DIR, Channel
from .publish import Post, publish_all
from .video import CopyrightFiltered, VideoFiltered, generate_video


class NoQuotaLeft(RuntimeError):
    pass


@dataclass
class Result:
    folder: Path
    video: Path
    scenario: script.Scenario
    theme: str
    links: dict = field(default_factory=dict)
    errors: dict = field(default_factory=dict)


def _video_via_api(client, channel, scenario, folder, log, **video_kwargs) -> Path:
    scene = script.apply_aliases(channel, scenario.ilk_kare or scenario.video_prompt)
    frame, mime = images.make_first_frame(client, channel, scene)
    (folder / f"ilk_kare{'.jpg' if mime == 'image/jpeg' else '.png'}").write_bytes(frame)
    log("Veo videoyu üretiyor (1-6 dk sürebilir)...")
    prompt = script.apply_aliases(channel, scenario.video_prompt)
    return generate_video(client, channel, prompt, frame, mime, folder / "video.mp4", **video_kwargs)


class GeminiBusyAll(RuntimeError):
    pass


BUSY_WAIT_SECONDS = 300
BUSY_ROUNDS = 3
PUBLISH_RETRIES = 2
PUBLISH_RETRY_WAIT = 30
_sleep = time.sleep


def _video_via_gemini_web(channel, scenario, folder, log) -> Path:
    # ChatGPT promptu önce olduğu gibi denenir; sadece telif reddinde isimler değiştirilir.
    variants = [script.web_video_prompt(channel, scenario)]
    if not scenario.ilk_kare:
        variants.insert(0, script.web_video_prompt(channel, scenario, aliases=False))
    variants = list(dict.fromkeys(variants))
    idx = 0
    profiles = accounts.gemini_profiles()
    for round_no in range(1, BUSY_ROUNDS + 1):
        busy = 0
        for profile in profiles:
            log(f"Gemini hesabı: {profile}")
            while True:
                prompt = variants[idx]
                (folder / f"gemini_prompt_{idx + 1}.txt").write_text(prompt, encoding="utf-8")
                try:
                    return video_web.generate_video_web(profile, prompt, folder / "video.mp4", log=log)
                except video_web.QuotaExceeded:
                    log(f">>> {profile}: Gemini video limitinin dolduğunu söyledi. Sıradaki hesaba geçiliyor.")
                    break
                except video_web.GeminiBusy as e:
                    generic_error = any(w in str(e).lower() for w in ("went wrong", "error", "hata", "sorun"))
                    if generic_error and idx + 1 < len(variants):
                        # "Something went wrong" bazen marka/karakter adından geliyor: önce adları değiştirip dene.
                        idx += 1
                        log(">>> Gemini 'bir hata oldu' dedi; marka/karakter adları değiştirilerek tekrar deneniyor.")
                        continue
                    busy += 1
                    log(f">>> {profile}: Gemini şu an yoğun olduğunu söyledi. Sıradaki hesap deneniyor.")
                    break
                except VideoFiltered:
                    # Telif ya da genel ret: önce aynı promptu karakter adları değiştirilmiş haliyle dene,
                    # o da reddedilirse run() ChatGPT'den yeni prompt ister.
                    if idx + 1 >= len(variants):
                        raise
                    idx += 1
                    log(">>> Gemini reddetti: aynı prompt, karakter isimleri değiştirilerek yeni sohbette tekrar deneniyor.")
        if not busy:
            break
        if round_no < BUSY_ROUNDS:
            log(f">>> Gemini yoğun. {BUSY_WAIT_SECONDS // 60} dakika bekleyip tekrar denenecek ({round_no}/{BUSY_ROUNDS - 1})...")
            _sleep(BUSY_WAIT_SECONDS)
        else:
            raise GeminiBusyAll("Gemini'nin video sunucuları şu an çok yoğun. Biraz sonra tekrar dene.")
    raise NoQuotaLeft("Gemini tüm hesaplarda video limitinin dolduğunu söyledi (ya da .env'de GEMINI_PROFILLER boş)")


def run(
    client,
    channel: Channel,
    *,
    publish: bool = True,
    skip_platforms: list[str] | None = None,
    attempts: int = 3,
    out_root: Path = OUTPUT_DIR,
    rng: random.Random | None = None,
    log=print,
    **video_kwargs,
) -> Result:
    engine = channel.video["motor"]
    if engine not in ("api", "gemini_web"):
        raise ValueError(f"Bilinmeyen video motoru: {engine} (api ya da gemini_web olmalı)")
    if engine == "gemini_web" and not accounts.gemini_profiles():
        raise NoQuotaLeft(".env içinde GEMINI_PROFILLER boş")
    if engine == "api" and (created := images.ensure_references(client, channel)):
        log(f"Karakter referansları üretildi: {', '.join(c.name for c in created)}")

    folder = out_root / channel.slug / datetime.now().strftime("%Y%m%d-%H%M%S")
    last_error = None
    for attempt in range(1, attempts + 1):
        if channel.scenario["motor"] == "chatgpt_web":
            theme = "chatgpt"
            log(f"[{attempt}/{attempts}] Konuyu ChatGPT projesi seçiyor")
        else:
            theme = script.pick_theme(channel, rng)
            log(f"[{attempt}/{attempts}] Tema: {theme}")
        folder.mkdir(parents=True, exist_ok=True)
        scenario = script.write_scenario(client, channel, theme, log=log, debug_dir=folder)
        log(f"Senaryo: {scenario.baslik}")

        (folder / "senaryo.json").write_text(
            json.dumps({"tema": theme, **scenario.model_dump()}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        try:
            if engine == "api":
                video = _video_via_api(client, channel, scenario, folder, log, **video_kwargs)
            else:
                video = _video_via_gemini_web(channel, scenario, folder, log)
            break
        except VideoFiltered as e:
            last_error = e
            log(f">>> {e}. Yeni bir senaryo yazılıp yeni sohbette tekrar denenecek.")
    else:
        raise RuntimeError(f"{attempts} denemede video üretilemedi: {last_error}")

    if channel.video.get("en_boy") == "9:16":
        try:
            video = postprocess.ensure_vertical(video, log)
        except Exception as e:
            log(f"UYARI: Dikey çevirme başarısız ({type(e).__name__}: {str(e)[:100]}), orijinal video kullanılıyor.")
    result = Result(folder=folder, video=video, scenario=scenario, theme=theme)
    log(f"Video hazır: {video}")
    if not publish:
        return result

    post = Post(title=scenario.baslik, caption=scenario.aciklama, hashtags=channel.hashtags + scenario.hashtagler)
    if skip_platforms:
        log(f"Bu sefer paylaşılmayacak: {', '.join(skip_platforms)}")
    result.links, result.errors = publish_all(channel, video, post, skip=skip_platforms)
    # Paylaşılamayan platformları (sadece onları) 2 kere daha dene; paylaşılanlar tekrar paylaşılmaz.
    for retry in range(1, PUBLISH_RETRIES + 1):
        if not result.errors:
            break
        names = ", ".join(result.errors)
        log(f">>> Paylaşılamadı: {names}. {PUBLISH_RETRY_WAIT} sn sonra tekrar deneniyor ({retry}/{PUBLISH_RETRIES})...")
        _sleep(PUBLISH_RETRY_WAIT)
        done = list(skip_platforms or []) + [n for n in channel.platforms if n not in result.errors]
        links, errors = publish_all(channel, video, post, skip=done)
        result.links.update(links)
        result.errors = errors
    for name, link in result.links.items():
        log(f"Paylaşıldı: {name} -> {link}")
    for name, err in result.errors.items():
        log(f"Paylaşım hatası: {name}: {err}")
    if result.links:
        history.add(channel.history_path, title=scenario.baslik, summary=scenario.ozet, theme=theme, links=result.links)
    return result
