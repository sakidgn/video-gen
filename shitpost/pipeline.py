import json
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import history, images, script
from .config import OUTPUT_DIR, Channel
from .publish import Post, publish_all
from .video import VideoFiltered, generate_video


@dataclass
class Result:
    folder: Path
    video: Path
    scenario: script.Scenario
    theme: str
    links: dict = field(default_factory=dict)
    errors: dict = field(default_factory=dict)


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
    if created := images.ensure_references(client, channel):
        log(f"Karakter referansları üretildi: {', '.join(c.name for c in created)}")

    folder = out_root / channel.slug / datetime.now().strftime("%Y%m%d-%H%M%S")
    last_error = None
    for attempt in range(1, attempts + 1):
        theme = script.pick_theme(channel, rng)
        log(f"[{attempt}/{attempts}] Tema: {theme}")
        scenario = script.write_scenario(client, channel, theme)
        log(f"Senaryo: {scenario.baslik}")

        frame, mime = images.make_first_frame(client, channel, scenario.ilk_kare)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"ilk_kare{'.jpg' if mime == 'image/jpeg' else '.png'}").write_bytes(frame)
        (folder / "senaryo.json").write_text(
            json.dumps({"tema": theme, **scenario.model_dump()}, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        log("Veo videoyu üretiyor (1-6 dk sürebilir)...")
        try:
            video = generate_video(client, channel, scenario.video_prompt, frame, mime, folder / "video.mp4", **video_kwargs)
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
