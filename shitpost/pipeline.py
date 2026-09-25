import json
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import accounts, history, images, script, video_web
from .config import OUTPUT_DIR, Channel
from .publish import Post, publish_all
from .video import VideoFiltered, generate_video


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
    frame, mime = images.make_first_frame(client, channel, scenario.ilk_kare)
    (folder / f"ilk_kare{'.jpg' if mime == 'image/jpeg' else '.png'}").write_bytes(frame)
    log("Veo videoyu üretiyor (1-6 dk sürebilir)...")
    return generate_video(client, channel, scenario.video_prompt, frame, mime, folder / "video.mp4", **video_kwargs)


def _video_via_gemini_web(channel, scenario, folder, log) -> Path:
    prompt = script.web_video_prompt(channel, scenario)
    for profile in accounts.available():
        log(f"Gemini hesabı: {profile}")
        try:
            path = video_web.generate_video_web(profile, prompt, folder / "video.mp4", log=log)
        except video_web.QuotaExceeded:
            log(f"{profile}: günlük video hakkı bitmiş, sıradaki hesaba geçiliyor")
            accounts.record(profile, exhausted=True)
            continue
        accounts.record(profile)
        return path
    raise NoQuotaLeft("Bugün tüm Gemini hesaplarının video hakkı bitti (ya da .env'de GEMINI_PROFILLER boş)")


def run(
    client,
    channel: Channel,
    *,
    publish: bool = True,
    attempts: int = 2,
    out_root: Path = OUTPUT_DIR,
    rng: random.Random | None = None,
    log=print,
    **video_kwargs,
) -> Result:
    engine = channel.video["motor"]
    if engine not in ("api", "gemini_web"):
        raise ValueError(f"Bilinmeyen video motoru: {engine} (api ya da gemini_web olmalı)")
    if engine == "gemini_web" and not accounts.available():
        raise NoQuotaLeft("Bugün kullanılabilir Gemini hesabı kalmadı")
    if engine == "api" and (created := images.ensure_references(client, channel)):
        log(f"Karakter referansları üretildi: {', '.join(c.name for c in created)}")

    folder = out_root / channel.slug / datetime.now().strftime("%Y%m%d-%H%M%S")
    last_error = None
    for attempt in range(1, attempts + 1):
        theme = script.pick_theme(channel, rng)
        log(f"[{attempt}/{attempts}] Tema: {theme}")
        scenario = script.write_scenario(client, channel, theme)
        log(f"Senaryo: {scenario.baslik}")

        folder.mkdir(parents=True, exist_ok=True)
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
            log(f"{e} - yeni senaryoyla tekrar deneniyor")
    else:
        raise RuntimeError(f"{attempts} denemede video üretilemedi: {last_error}")

    result = Result(folder=folder, video=video, scenario=scenario, theme=theme)
    log(f"Video hazır: {video}")
    if not publish:
        return result

    post = Post(title=scenario.baslik, caption=scenario.aciklama, hashtags=channel.hashtags + scenario.hashtagler)
    result.links, result.errors = publish_all(channel, video, post)
    for name, link in result.links.items():
        log(f"Paylaşıldı: {name} -> {link}")
    for name, err in result.errors.items():
        log(f"Paylaşım hatası: {name}: {err}")
    if result.links:
        history.add(channel.history_path, title=scenario.baslik, summary=scenario.ozet, theme=theme, links=result.links)
    return result
