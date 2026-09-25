import time
from pathlib import Path

from google.genai import types

from .config import Channel


class VideoFiltered(RuntimeError):
    pass


def generate_video(
    client,
    channel: Channel,
    prompt: str,
    first_frame: bytes,
    first_frame_mime: str,
    out_path: Path,
    poll_seconds: int = 10,
    timeout_seconds: int = 900,
    sleep=time.sleep,
) -> Path:
    v = channel.video
    op = client.models.generate_videos(
        model=channel.models["video"],
        prompt=prompt,
        image=types.Image(image_bytes=first_frame, mime_type=first_frame_mime),
        config=types.GenerateVideosConfig(
            aspect_ratio=v["en_boy"],
            resolution=v["cozunurluk"],
            duration_seconds=v["sure"],
            negative_prompt=v["negatif_prompt"],
            number_of_videos=1,
        ),
    )
    waited = 0
    while not op.done:
        if waited >= timeout_seconds:
            raise TimeoutError(f"Veo {timeout_seconds} sn içinde bitirmedi ({op.name})")
        sleep(poll_seconds)
        waited += poll_seconds
        op = client.operations.get(op)

    if op.error:
        raise RuntimeError(f"Veo hatası: {op.error}")
    resp = op.response
    if not resp or not resp.generated_videos:
        reasons = (resp.rai_media_filtered_reasons if resp else None) or ["bilinmiyor"]
        raise VideoFiltered(f"Video güvenlik filtresine takıldı: {'; '.join(reasons)}")

    video = resp.generated_videos[0].video
    client.files.download(file=video)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    video.save(str(out_path))
    return out_path
