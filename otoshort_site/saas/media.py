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
