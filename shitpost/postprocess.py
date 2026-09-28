import re
import subprocess
from pathlib import Path

VERTICAL_FILTER = (
    "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=24:2[bg];"
    "[0:v]scale=1080:-2[fg];"
    "[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]"
)


def _ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def video_size(path: Path) -> tuple[int, int] | None:
    r = subprocess.run([_ffmpeg(), "-hide_banner", "-i", str(path)], capture_output=True, text=True, errors="replace")
    m = re.search(r"Video:.*?[ ,](\d{2,5})x(\d{2,5})[ ,\[]", r.stderr)
    return (int(m[1]), int(m[2])) if m else None


def ensure_vertical(path: Path, log=print) -> Path:
    """Yatay videoyu Shorts/Reels için 1080x1920'ye çevirir: video ortada, arkada bulanık kopyası."""
    size = video_size(path)
    if not size:
        log("UYARI: Videonun boyutu okunamadı, dikey kontrolü atlandı.")
        return path
    w, h = size
    if h >= w:
        return path
    out = path.with_name("video_dikey.mp4")
    subprocess.run(
        [_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(path),
         "-filter_complex", VERTICAL_FILTER, "-map", "[v]", "-map", "0:a?",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
         "-movflags", "+faststart", str(out)],
        check=True, capture_output=True,
    )
    log(f"Video yatay geldi ({w}x{h}); dikey formata çevrildi (bulanık arka plan): {out.name}")
    return out
