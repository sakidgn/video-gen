"""Medya yardımcıları: referans karakter görselleri."""
import secrets
import shutil
import subprocess
from pathlib import Path

from . import config

MAX_REF_BYTES = 6 * 1024 * 1024


class MediaError(Exception):
    pass


def ref_dir() -> Path:
    return config.DATA_DIR / "referanslar"


def ref_path(rel: str) -> Path | None:
    """'uid/ad.png' → dosya yolu (klasör dışına çıkılamaz)."""
    if not rel:
        return None
    base = ref_dir().resolve()
    p = (base / rel).resolve()
    return p if base in p.parents and p.exists() else None


def _kind(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def save_reference(data: bytes, user_id: int) -> str:
    """Yüklenen görseli doğrular, en fazla 1024 px PNG'ye çevirip kaydeder (meta veriler atılır). 'uid/ad.png' döner."""
    if not data:
        raise MediaError("Görsel boş.")
    if len(data) > MAX_REF_BYTES:
        raise MediaError("Görsel en fazla 6 MB olabilir.")
    kind = _kind(data)
    if not kind:
        raise MediaError("Sadece PNG, JPG ya da WEBP görsel yükleyebilirsin.")
    folder = ref_dir() / str(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    name = secrets.token_hex(8)
    src, out = folder / f"{name}.src.{kind}", folder / f"{name}.png"
    src.write_bytes(data)
    try:
        import imageio_ffmpeg

        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(src),
                        "-vf", "scale='min(1024,iw)':'min(1024,ih)':force_original_aspect_ratio=decrease",
                        "-frames:v", "1", "-map_metadata", "-1", str(out)], check=True, timeout=60)
    except Exception:
        out.unlink(missing_ok=True)
        raise MediaError("Görsel okunamadı, başka bir dosya dene.") from None
    finally:
        src.unlink(missing_ok=True)
    return f"{user_id}/{out.name}"


def delete_user_media(user_id: int) -> None:
    shutil.rmtree(ref_dir() / str(user_id), ignore_errors=True)


# ---------- altyazı ----------
FONT = config.ROOT / "assets" / "PlusJakartaSans-ExtraBold.ttf"


def _ass_time(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, sec = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{sec:05.2f}"


def _ass_text(text: str) -> str:
    return " ".join(text.replace("\\", "").replace("{", "(").replace("}", ")").split())


def build_ass(segments: list[dict], width: int = 720, height: int = 1280) -> str:
    """TikTok tarzı altyazı: kalın, beyaz, siyah kenarlı; platform butonlarının üstünde kalacak yükseklikte."""
    size = round(height * 0.052)
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        f"Style: Alt,Plus Jakarta Sans,{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,"
        f"{max(2, round(size * 0.12))},1,2,{round(width * .08)},{round(width * .08)},{round(height * .24)},1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for seg in segments:
        text = _ass_text(str(seg.get("text", "")))
        start, end = float(seg.get("start", 0)), float(seg.get("end", 0))
        if text and end > start:
            lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Alt,,0,0,0,,{text}")
    return "\n".join(lines) + "\n"


def video_size(path: Path) -> tuple[int, int]:
    import re

    import imageio_ffmpeg

    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True,
                       text=True, timeout=30)
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", r.stderr)
    return (int(m.group(1)), int(m.group(2))) if m else (720, 1280)


def burn_subtitles(video: Path, segments: list[dict]) -> Path | None:
    """Altyazıyı videoya basar. Orijinal '<ad>-ham.mp4' olarak saklanır. Altyazı yoksa None."""
    import tempfile

    import imageio_ffmpeg

    if not any(str(s.get("text", "")).strip() for s in segments):
        return None
    w, h = video_size(video)
    raw = video.with_name(f"{video.stem}-ham.mp4")
    with tempfile.TemporaryDirectory() as d:
        # Windows yollarındaki ':' filtre sözdizimini bozar: ffmpeg geçici klasörde göreli adlarla çalışır
        tmp = Path(d)
        (tmp / "alt.ass").write_text(build_ass(segments, w, h), encoding="utf-8")
        shutil.copy(FONT, tmp / FONT.name)
        shutil.copy(video, tmp / "in.mp4")
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", "in.mp4",
                        "-vf", "subtitles=alt.ass:fontsdir=.", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-c:a", "copy", "out.mp4"], cwd=d, check=True, timeout=300)
        shutil.move(str(video), raw)
        shutil.move(str(tmp / "out.mp4"), video)
    return raw
