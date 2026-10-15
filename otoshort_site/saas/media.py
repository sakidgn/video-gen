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

        # biçim zorla seçilir: dosya ne iddia ederse etsin ffmpeg onu sadece o görsel türü olarak okur
        demux = {"png": "png_pipe", "jpg": "jpeg_pipe", "webp": "webp_pipe"}[kind]
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-protocol_whitelist", "file",
                        "-f", demux, "-i", str(src),
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
FONT_NAME = "Plus Jakarta Sans ExtraBold"  # dosyadaki aile adı (libass bununla eşleştirir)


def _ass_time(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, sec = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{sec:05.2f}"


def _ass_text(text: str) -> str:
    return " ".join(text.replace("\\", "").replace("{", "(").replace("}", ")").split())


SUB_STYLES = ("", "viral")  # "" klasik, "viral" kelime kelime renkli (karaoke / Shorts tarzı)
VIRAL_COLORS = ("&H35E1FF&", "&H5BFF7C&")  # sarı, yeşil (ASS: &HBBGGRR&)


def _upper(text: str, language: str) -> str:
    if language in ("tr", "az"):  # Türkçe: i → İ, ı → I
        text = text.replace("i", "İ").replace("ı", "I")
    return text.upper()


def word_times(seg: dict) -> list[tuple[str, float, float]]:
    """Segmentin kelimeleri ve zamanları. Yapay zekâ kelime zamanı verdiyse o, yoksa süre kelime uzunluğuna göre bölünür."""
    start, end = float(seg.get("start", 0)), float(seg.get("end", 0))
    given = [(str(w.get("text", "")).strip(), float(w.get("start", 0)), float(w.get("end", 0)))
             for w in seg.get("words") or [] if isinstance(w, dict)]
    given = [(t, a, b) for t, a, b in given if t and start - .05 <= a < b <= end + .05]
    if given and len(given) == len(given[:40]):
        return given
    words = _ass_text(str(seg.get("text", ""))).split()
    if not words or end <= start:
        return []
    weights = [len(w) + 2 for w in words]
    total, t, out = sum(weights), start, []
    for w, k in zip(words, weights):
        d = (end - start) * k / total
        out.append((w, t, t + d))
        t += d
    return out


def _chunks(words: list[tuple[str, float, float]], max_words: int = 3, max_chars: int = 16):
    """Kelimeleri ekranda birlikte görünecek 1–3 kelimelik parçalara böler."""
    chunk: list = []
    for w in words:
        if chunk and (len(chunk) >= max_words or sum(len(x[0]) for x in chunk) + len(w[0]) > max_chars):
            yield chunk
            chunk = []
        chunk.append(w)
    if chunk:
        yield chunk


def _viral_events(segments: list[dict], language: str) -> list[str]:
    """Her kelime söylendiği anda renklenip büyür; parça 1–3 kelime, büyük harf (Shorts / karaoke tarzı)."""
    events, n = [], 0
    for seg in segments:
        for chunk in _chunks(word_times(seg)):
            color = VIRAL_COLORS[n % len(VIRAL_COLORS)]
            n += 1
            words = [_upper(_ass_text(w), language) for w, _, _ in chunk]
            for i, (_, a, b) in enumerate(chunk):
                b = chunk[i + 1][1] if i + 1 < len(chunk) else b  # bir sonraki kelimeye kadar ekranda kalır
                parts = []
                for j, w in enumerate(words):
                    if j == i:  # söylenen kelime: renkli, hafif büyük, "pop" ile girer
                        parts.append(f"{{\\c{color}\\fscx108\\fscy108\\t(0,90,\\fscx122\\fscy122)"
                                     f"\\t(90,180,\\fscx112\\fscy112)}}{w}{{\\r}}")
                    else:
                        parts.append(w)
                intro = "{\\fad(60,0)}" if i == 0 else ""
                events.append(f"Dialogue: 0,{_ass_time(a)},{_ass_time(b)},Viral,,0,0,0,,{intro}{' '.join(parts)}")
    return events


def build_ass(segments: list[dict], width: int = 720, height: int = 1280, style: str = "",
              language: str = "tr") -> str:
    """TikTok tarzı altyazı: kalın, beyaz, siyah kenarlı; platform butonlarının üstünde kalacak yükseklikte.
    style="viral": kelime kelime renklenen büyük harfli altyazı."""
    size = round(height * 0.052)
    big = round(height * 0.076)
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        f"Style: Alt,{FONT_NAME},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,"
        f"{max(2, round(size * 0.12))},1,2,{round(width * .08)},{round(width * .08)},{round(height * .24)},1",
        f"Style: Viral,{FONT_NAME},{big},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,1,0,1,"
        f"{max(3, round(big * 0.14))},3,2,{round(width * .07)},{round(width * .07)},{round(height * .28)},1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    if style == "viral":
        lines += _viral_events(segments, language)
    else:
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


def burn_subtitles(video: Path, segments: list[dict], style: str = "", language: str = "tr") -> Path | None:
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
        (tmp / "alt.ass").write_text(build_ass(segments, w, h, style, language), encoding="utf-8")
        shutil.copy(FONT, tmp / FONT.name)
        shutil.copy(video, tmp / "in.mp4")
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", "in.mp4",
                        "-vf", "subtitles=alt.ass:fontsdir=.", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-c:a", "copy", "out.mp4"], cwd=d, check=True, timeout=300)
        shutil.move(str(video), raw)
        shutil.move(str(tmp / "out.mp4"), video)
    return raw
