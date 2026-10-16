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


SUB_STYLES = ("", "viral", "kutu", "neon", "tek", "sade")  # "" klasik (cümle cümle)
WORD_STYLES = ("viral", "kutu", "neon", "tek")  # kelime zamanı gerekenler (karaoke / Shorts tarzı)
SUB_STYLE_LABELS = {  # form değeri: (ad, kısa açıklama, önizleme) — "klasik" "" olarak saklanır
    "viral": ("Viral", "kelime kelime, renkli"), "kutu": ("Kutu", "sarı kutuda, kelime kelime"),
    "neon": ("Neon", "parlayan, kelime kelime"), "tek": ("Tek kelime", "kocaman, tek tek"),
    "klasik": ("Klasik", "sade, cümle cümle"), "sade": ("Minimal", "küçük, yarı saydam kutu"),
}
VIRAL_COLORS = ("&H35E1FF&", "&H5BFF7C&")  # sarı, yeşil (ASS: &HBBGGRR&)
NEON_COLORS = ("&H8B3DFF&", "&HFFD63D&")  # pembe, camgöbeği parıltı
KUTU_HL = "&H5E24E0&"  # kutudaki söylenen kelime: koyu pembe


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


POP = "\\fscx108\\fscy108\\t(0,90,\\fscx122\\fscy122)\\t(90,180,\\fscx112\\fscy112)"


def _viral_events(segments: list[dict], language: str, style: str = "viral") -> list[str]:
    """Kelime kelime altyazı: her kelime söylendiği anda vurgulanır; parça 1–3 kelime, büyük harf.
    viral: renkli + büyür · kutu: sarı kutuda, kelime pembe · neon: parlayan · tek: tek kelime kocaman."""
    events, n = [], 0
    one = style == "tek"
    for seg in segments:
        for chunk in _chunks(word_times(seg), *((1, 99) if one else (3, 16))):
            color = (NEON_COLORS if style == "neon" else VIRAL_COLORS)[n % 2]
            n += 1
            words = [_upper(_ass_text(w), language) for w, _, _ in chunk]
            for i, (_, a, b) in enumerate(chunk):
                b = chunk[i + 1][1] if i + 1 < len(chunk) else b  # bir sonraki kelimeye kadar ekranda kalır
                at = f"{_ass_time(a)},{_ass_time(b)}"
                if one:  # tek kelime: aşağıdan büyüyerek gelir, renkler sırayla
                    c = "&HFFFFFF&" if n % 2 else VIRAL_COLORS[0]
                    events.append(f"Dialogue: 0,{at},Tek,,0,0,0,,{{\\c{c}\\fscx70\\fscy70\\t(0,110,\\fscx112\\fscy112)"
                                  f"\\t(110,190,\\fscx100\\fscy100)}}{words[0]}")
                    continue
                hl = KUTU_HL if style == "kutu" else ("&HFFFFFF&" if style == "neon" else color)
                pop = "" if style == "kutu" else POP  # kutuda büyüme kutuyu bozar
                parts = [f"{{\\c{hl}{pop}}}{w}{{\\r}}" if j == i else w for j, w in enumerate(words)]
                intro = "{\\fad(60,0)}" if i == 0 else ""
                name = {"kutu": "Kutu", "neon": "Neon"}.get(style, "Viral")
                if style == "neon":  # alt katman: aynı yazı, renkli ve bulanık kalın kenar (parıltı)
                    glow = f"{{\\1a&HFF&\\3c{color}\\bord14\\blur10}}" + " ".join(words)
                    events.append(f"Dialogue: 0,{at},Neon,,0,0,0,,{intro}{glow}")
                    parts = [f"{{\\3c{color}}}" + parts[0], *parts[1:]]
                events.append(f"Dialogue: 1,{at},{name},,0,0,0,,{intro}{' '.join(parts)}")
    return events


def hook_events(text: str, width: int, height: int, until: float = 2.8) -> list[str]:
    """Açılış kancası: ilk ~3 saniye ekranın üstünde beyaz kutuda büyük yazı (izleyici kaydırmadan önce merak etsin)."""
    import re

    text = " ".join(re.sub("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]", "", _ass_text(text)).split())
    if not text or until <= 0.3:
        return []
    return [f"Dialogue: 2,{_ass_time(0)},{_ass_time(until)},Kanca,,0,0,0,,"
            f"{{\\fad(0,250)\\fscx80\\fscy80\\t(0,160,\\fscx106\\fscy106)\\t(160,260,\\fscx100\\fscy100)}}{text}"]


def progress_events(duration: float, width: int, height: int, color: str = "&H3FD2FF&", style: str = "Alt") -> list[str]:
    """İlerleme çubuğu: en altta, video boyunca soldan sağa dolan ince şerit (izleyici sonun yakın olduğunu görür)."""
    if duration <= 0.5:
        return []
    h, ms, y = max(6, round(height * .009)), int(duration * 1000), height - max(6, round(height * .009))
    rect = f"m 0 0 l {width} 0 {width} {h} 0 {h}"
    end = _ass_time(duration)
    return [f"Dialogue: 8,{_ass_time(0)},{end},{style},,0,0,0,,{{\\an7\\pos(0,{y})\\bord0\\shad0\\c&H000000&\\1a&H90&\\p1}}{rect}",
            f"Dialogue: 9,{_ass_time(0)},{end},{style},,0,0,0,,{{\\an7\\pos(0,{y})\\bord0\\shad0\\c{color}\\clip(0,{y - 2},0,{height})"
            f"\\t(0,{ms},\\clip(0,{y - 2},{width},{height}))\\p1}}{rect}"]


def build_ass(segments: list[dict], width: int = 720, height: int = 1280, style: str = "",
              language: str = "tr", hook: str = "", duration: float = 0.0, bar: bool = False) -> str:
    """TikTok tarzı altyazı: kalın, beyaz, siyah kenarlı; platform butonlarının üstünde kalacak yükseklikte.
    style: "" klasik, "viral"/"kutu"/"neon"/"tek" kelime kelime, "sade" küçük yarı saydam kutu.
    hook: ilk saniyelerde üstte görünen kanca yazısı · bar: en altta ilerleme çubuğu (duration gerekir)."""
    size = round(height * 0.052)
    big = round(height * 0.076)
    mx, mv = round(width * .07), round(height * .28)
    fmt = ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
           "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
           "MarginL, MarginR, MarginV, Encoding")

    def st(name, fs, primary, outline, back, border, bord, shad, align, ml, mv_, spacing=0):
        return (f"Style: {name},{FONT_NAME},{fs},{primary},&H00FFFFFF,{outline},{back},1,0,0,0,100,100,{spacing},0,"
                f"{border},{bord},{shad},{align},{ml},{ml},{mv_},1")

    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}", "WrapStyle: 0", "",
        "[V4+ Styles]", fmt,
        st("Alt", size, "&H00FFFFFF", "&H00000000", "&H64000000", 1, max(2, round(size * 0.12)), 1, 2,
           round(width * .08), round(height * .24)),
        st("Viral", big, "&H00FFFFFF", "&H00000000", "&H96000000", 1, max(3, round(big * 0.14)), 3, 2, mx, mv, 1),
        # kutu: sarı opak kutu, koyu yazı (BorderStyle 3: kenar rengi kutunun rengi olur)
        st("Kutu", round(big * .86), "&H00141414", "&H003FD2FF", "&H64000000", 3, round(big * .16), 0, 2, mx, mv),
        st("Neon", big, "&H00FFFFFF", "&H008B3DFF", "&H00000000", 1, 3, 0, 2, mx, mv, 1),
        st("Tek", round(height * .11), "&H00FFFFFF", "&H00000000", "&H96000000", 1, round(height * .011), 4, 2,
           mx, round(height * .30)),
        st("Sade", round(height * .04), "&H00FFFFFF", "&H8C000000", "&H00000000", 3, round(height * .012), 0, 2,
           round(width * .1), round(height * .2)),
        st("Kanca", round(height * .058), "&H00141414", "&H00FFFFFF", "&H50000000", 3, round(height * .016), 0, 8,
           round(width * .1), round(height * .13)),
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    if style in WORD_STYLES:
        lines += _viral_events(segments, language, style)
    else:
        name = "Sade" if style == "sade" else "Alt"
        for seg in segments:
            text = _ass_text(str(seg.get("text", "")))
            start, end = float(seg.get("start", 0)), float(seg.get("end", 0))
            if text and end > start:
                lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},{name},,0,0,0,,{text}")
    if hook:
        lines += hook_events(hook, width, height, min(2.8, duration - .2) if duration else 2.8)
    if bar:
        lines += progress_events(duration, width, height)
    return "\n".join(lines) + "\n"


def srt(segments: list[dict]) -> str:
    """Altyazı dosyası (SRT): YouTube/TikTok'a ayrıca yüklenebilir ya da başka düzenleyicide kullanılır."""
    def tm(t: float) -> str:
        ms = int(round(max(0.0, t) * 1000))
        h, ms = divmod(ms, 3600_000)
        m, ms = divmod(ms, 60_000)
        sec, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

    out, n = [], 0
    for seg in segments:
        text = _ass_text(str(seg.get("text", "")))
        a, b = float(seg.get("start", 0)), float(seg.get("end", 0))
        if text and b > a:
            n += 1
            out.append(f"{n}\n{tm(a)} --> {tm(b)}\n{text}\n")
    return "\n".join(out)


def video_size(path: Path) -> tuple[int, int]:
    import re

    import imageio_ffmpeg

    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True,
                       text=True, timeout=30)
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", r.stderr)
    return (int(m.group(1)), int(m.group(2))) if m else (720, 1280)


def _probe(path: Path) -> tuple[bool, float]:
    """(sesi var mı, süre sn)"""
    import re

    import imageio_ffmpeg

    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True,
                       text=True, timeout=30)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return "Audio:" in r.stderr, (int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])) if m else 8.0


def join_clips(clips: list[Path], out: Path, seconds: int) -> Path:
    """Sahneleri sırayla tek videoya birleştirir ve istenen süreye kırpar (sesi olmayan sahneye sessizlik eklenir)."""
    import tempfile

    import imageio_ffmpeg

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    w, h = video_size(clips[0])
    with tempfile.TemporaryDirectory() as d:
        args, parts = [], []
        for i, c in enumerate(clips):
            name = f"s{i}.mp4"
            shutil.copy(c, Path(d) / name)  # Windows yollarındaki ':' filtreyi bozmasın
            args += ["-i", name]
        n = len(clips)
        for i, c in enumerate(clips):
            parts.append(f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,"
                         f"setsar=1,fps=30,format=yuv420p[v{i}]")
            has_audio, dur = _probe(c)
            if has_audio:  # ses görüntüden kısa/uzunsa sahne sınırında kayma olmasın: görüntü süresine eşitlenir
                parts.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo,apad,atrim=duration={dur:.3f}[a{i}]")
            else:
                parts.append(f"anullsrc=r=44100:cl=stereo,atrim=duration={dur:.3f}[a{i}]")
        chain = "".join(f"[v{i}][a{i}]" for i in range(n))
        filt = ";".join(parts) + f";{chain}concat=n={n}:v=1:a=1[v][a]"
        subprocess.run([ff, "-y", "-loglevel", "error", *args, "-filter_complex", filt, "-map", "[v]", "-map", "[a]",
                        "-t", str(seconds), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac",
                        "-movflags", "+faststart", "out.mp4"], cwd=d, check=True, timeout=600)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(Path(d) / "out.mp4"), out)
    return out


def trim(video: Path, seconds: int) -> None:
    """Tek sahne istenenden uzunsa (ör. 5 sn için 6 sn üretildi) yerinde kırpar."""
    import tempfile

    import imageio_ffmpeg

    with tempfile.TemporaryDirectory() as d:
        shutil.copy(video, Path(d) / "in.mp4")
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", "in.mp4", "-t", str(seconds),
                        "-c", "copy", "out.mp4"], cwd=d, check=True, timeout=120)
        shutil.move(str(Path(d) / "out.mp4"), video)


def burn_subtitles(video: Path, segments: list[dict], style: str = "", language: str = "tr", hook: str = "",
                   bar: bool = False) -> Path | None:
    """Altyazıyı (ve istenirse açılış kancasını, ilerleme çubuğunu) videoya basar. Orijinal '<ad>-ham.mp4' olarak
    saklanır. Basılacak bir şey yoksa None."""
    import tempfile

    import imageio_ffmpeg

    has_text = any(str(s.get("text", "")).strip() for s in segments)
    if not has_text and not hook.strip() and not bar:
        return None
    w, h = video_size(video)
    duration = _probe(video)[1]
    raw = video.with_name(f"{video.stem}-ham.mp4")
    with tempfile.TemporaryDirectory() as d:
        # Windows yollarındaki ':' filtre sözdizimini bozar: ffmpeg geçici klasörde göreli adlarla çalışır
        tmp = Path(d)
        (tmp / "alt.ass").write_text(build_ass(segments, w, h, style, language, hook, duration, bar),
                                     encoding="utf-8")
        shutil.copy(FONT, tmp / FONT.name)
        shutil.copy(video, tmp / "in.mp4")
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", "in.mp4",
                        "-vf", "subtitles=alt.ass:fontsdir=.", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-c:a", "copy", "out.mp4"], cwd=d, check=True, timeout=300)
        shutil.move(str(video), raw)
        shutil.move(str(tmp / "out.mp4"), video)
    if has_text:  # altyazı dosyası da indirilebilsin
        video.with_suffix(".srt").write_text(srt(segments), encoding="utf-8")
    return raw
