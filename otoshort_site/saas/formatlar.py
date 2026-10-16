"""Viral formatlar: mesajlaşma hikâyesi ve itiraf/hikâye anlatımı.
Video modeli kullanılmaz: yapay zekâ metni yazar, seslendirme (TTS) okunur, ffmpeg + libass ile arka plan videosunun
üstüne sohbet balonları / gönderi kartı ve kelime kelime altyazı çizilir. Bu yüzden ucuz ve hızlıdır."""
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import config
from .media import FONT, FONT_NAME, _ass_text, _ass_time, _upper, _viral_events

W, H = 720, 1280
FORMATS = {  # anahtar: (etiket, açıklama)
    "sohbet": ("Mesajlaşma hikâyesi", "İki kişinin komik/dramatik yazışması, sesli okunur"),
    "hikaye": ("İtiraf / hikâye", "Gönderi kartı + seslendirme + kelime kelime altyazı"),
}
BACKGROUNDS = {  # anahtar: (etiket, ffmpeg lavfi kaynağı ya da None = kütüphanedeki video)
    "girdap": "Sonsuz girdap",
    "piksel": "Piksel evren",
    "pastel": "Yumuşak renkler",
}


def _bgr(hex_rgb: str) -> str:
    h = hex_rgb.lstrip("#")
    return f"&H{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


def rrect(w: float, h: float, r: float) -> str:
    """ASS çizim komutu: köşeleri yuvarlatılmış dikdörtgen (sol üst 0,0)."""
    r = max(0.0, min(r, w / 2, h / 2))
    c = r * 0.5523
    f = lambda v: f"{v:.1f}".rstrip("0").rstrip(".")  # noqa: E731
    return (f"m {f(r)} 0 l {f(w - r)} 0 b {f(w - r + c)} 0 {f(w)} {f(r - c)} {f(w)} {f(r)} "
            f"l {f(w)} {f(h - r)} b {f(w)} {f(h - r + c)} {f(w - r + c)} {f(h)} {f(w - r)} {f(h)} "
            f"l {f(r)} {f(h)} b {f(r - c)} {f(h)} 0 {f(h - r + c)} 0 {f(h - r)} "
            f"l 0 {f(r)} b 0 {f(r - c)} {f(r - c)} 0 {f(r)} 0")


EMOJI = __import__("re").compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]")


def plain(text: str) -> str:
    """Çizilecek metin: emoji yok (sunucuda emoji fontu olmayabilir), ASS özel karakterleri temiz."""
    return _ass_text(EMOJI.sub("", text))


def wrap(text: str, max_chars: int) -> list[str]:
    words, lines, cur = plain(text).split(), [], ""
    for w in words:
        while len(w) > max_chars:  # çok uzun kelime bölünür
            if cur:
                lines.append(cur)
                cur = ""
            lines.append(w[:max_chars])
            w = w[max_chars:]
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines or [""]


def _header(styles: str = "") -> list[str]:
    return [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2",
        "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        f"Style: D,{FONT_NAME},30,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        styles,
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]


def _ev(layer: int, a: float, b: float, text: str, style: str = "D") -> str:
    return f"Dialogue: {layer},{_ass_time(a)},{_ass_time(b)},{style},,0,0,0,,{text}"


# ---------- mesajlaşma hikâyesi ----------
FS, LINE_H, PAD_X, PAD_Y, CHAR_W = 40, 47, 24, 15, 13.6  # yazı boyutu, satır yüksekliği, iç boşluk, ort. harf genişliği
PANEL_X, PANEL_W, PANEL_TOP, PANEL_MAX_H = 52, 616, 130, 1000
HEAD_H, GAP = 118, 12
BLUE, GRAY, PANEL, INK = "#0A84FF", "#E9E9EB", "#FFFFFF", "#111111"


def _bubble_size(text: str) -> tuple[list[str], float, float]:
    lines = wrap(text, 25)
    w = min(PANEL_W * 0.76, max(len(x) for x in lines) * CHAR_W + 2 * PAD_X)
    return lines, max(70.0, w), len(lines) * LINE_H + 2 * PAD_Y - 4


def chat_ass(messages: list[dict], times: list[tuple[float, float]], contact: str, total: float) -> str:
    """messages: [{"me": bool, "text": str}], times: her mesajın (başlangıç, bitiş) saniyesi.
    Her mesaj konuşulmaya başladığı anda balon olarak belirir; panel en son mesajlara göre kayar."""
    out = _header()
    sizes = [_bubble_size(m["text"]) for m in messages]
    body_max = PANEL_MAX_H - HEAD_H - 24
    initial = (_upper(contact[:1], "tr") or "?")
    for i, (start, _) in enumerate(times):
        end = times[i + 1][0] if i + 1 < len(times) else total
        # ekrana sığan son mesajlar (yeniden eskiye)
        visible, used = [], 0.0
        for j in range(i, -1, -1):
            hgt = sizes[j][2] + GAP
            if used + hgt > body_max and visible:
                break
            visible.insert(0, j)
            used += hgt
        panel_h = HEAD_H + 24 + used
        out.append(_ev(0, start, end, f"{{\\an7\\pos({PANEL_X},{PANEL_TOP})\\p1\\c{_bgr(PANEL)}\\1a&H08&}}"
                                      f"{rrect(PANEL_W, panel_h, 34)}"))
        # başlık: avatar + ad
        cx = PANEL_X + PANEL_W / 2
        out.append(_ev(1, start, end, f"{{\\an7\\pos({cx - 30:.0f},{PANEL_TOP + 14})\\p1\\c{_bgr('#9AA3B2')}}}"
                                      f"{rrect(60, 60, 30)}"))
        out.append(_ev(2, start, end, f"{{\\an5\\pos({cx:.0f},{PANEL_TOP + 44})\\fs30\\b1\\c&HFFFFFF&}}{initial}"))
        out.append(_ev(2, start, end, f"{{\\an8\\pos({cx:.0f},{PANEL_TOP + 80})\\fs28\\c{_bgr(INK)}}}"
                                      f"{plain(contact)[:28]}"))
        out.append(_ev(1, start, end, f"{{\\an7\\pos({PANEL_X},{PANEL_TOP + HEAD_H})\\p1\\c{_bgr('#E5E5EA')}}}"
                                      f"{rrect(PANEL_W, 2, 0)}"))
        y = PANEL_TOP + HEAD_H + 14
        for j in visible:
            lines, bw, bh = sizes[j]
            me = messages[j]["me"]
            x = PANEL_X + PANEL_W - 20 - bw if me else PANEL_X + 20
            fade = "\\fad(120,0)" if j == i else ""
            out.append(_ev(3, start, end, f"{{\\an7\\pos({x:.0f},{y:.0f}){fade}\\p1\\c{_bgr(BLUE if me else GRAY)}}}"
                                          f"{rrect(bw, bh, 22)}"))
            text = "\\N".join(lines)
            out.append(_ev(4, start, end, f"{{\\an7\\pos({x + PAD_X:.0f},{y + PAD_Y - 4:.0f}){fade}\\fs{FS}"
                                          f"\\c{_bgr('#FFFFFF' if me else INK)}}}{text}"))
            y += bh + GAP
    return "\n".join(out) + "\n"


# ---------- itiraf / hikâye anlatımı ----------
def story_ass(title: str, community: str, sentences: list[str], times: list[tuple[float, float]], total: float,
              language: str) -> str:
    """İlk cümle (başlık) okunurken gönderi kartı; sonra her cümle kelime kelime viral altyazı."""
    out = _header(f"Style: Viral,{FONT_NAME},{round(H * 0.07)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,"
                  f"100,100,1,0,1,{round(H * 0.07 * 0.14)},3,5,{round(W * .07)},{round(W * .07)},0,1")
    t_end = times[0][1] + 0.4 if times else 3.0
    lines = wrap(title, 27)
    card_h = 170 + len(lines) * 56 + 70
    x, y, cw = 48, int(H * 0.27), W - 96
    f = "\\fad(0,200)"
    out.append(_ev(0, 0, t_end, f"{{\\an7\\pos({x},{y}){f}\\p1\\c&HFFFFFF&}}{rrect(cw, card_h, 30)}"))
    out.append(_ev(1, 0, t_end, f"{{\\an7\\pos({x + 30},{y + 30}){f}\\p1\\c{_bgr('#FF5A1F')}}}{rrect(68, 68, 34)}"))
    out.append(_ev(2, 0, t_end, f"{{\\an5\\pos({x + 64},{y + 64}){f}\\fs36\\b1\\c&HFFFFFF&}}"
                                f"{_upper(plain(community)[:1], language)}"))
    out.append(_ev(2, 0, t_end, f"{{\\an7\\pos({x + 116},{y + 32}){f}\\fs32\\b1\\c{_bgr(INK)}}}"
                                f"{plain(community)[:26]}"))
    out.append(_ev(2, 0, t_end, f"{{\\an7\\pos({x + 116},{y + 70}){f}\\fs24\\c{_bgr('#7C7C80')}}}"
                                f"{plain(config.SITE_NAME)}"))
    out.append(_ev(2, 0, t_end, f"{{\\an7\\pos({x + 30},{y + 130}){f}\\fs46\\b1\\c{_bgr(INK)}}}"
                                + "\\N".join(lines)))
    fy = y + card_h - 62
    out.append(_ev(2, 0, t_end, f"{{\\an7\\pos({x + 32},{fy + 6}){f}\\p1\\c{_bgr('#FF5A1F')}}}m 13 0 l 26 20 l 0 20"))
    comments = "yorum" if language == "tr" else "comments"
    out.append(_ev(2, 0, t_end, f"{{\\an7\\pos({x + 68},{fy}){f}\\fs28\\b1\\c{_bgr('#3C3C43')}}}"
                                f"12,4B      1,2B {comments}"))
    segs = [{"start": a, "end": b, "text": s} for s, (a, b) in zip(sentences[1:], times[1:])]
    out += [e.replace(",Viral,,", ",Viral,,", 1) for e in _viral_events(segs, language)]
    return "\n".join(out) + "\n"


# ---------- arka plan ----------
def _bg_source(kind: str, seconds: float) -> list[str]:
    d = f"{seconds:.2f}"
    if kind == "piksel":
        return ["-f", "lavfi", "-i", f"life=s=72x128:mold=6:r=8:ratio=0.10:death_color=#120c22:life_color=#ffb15c:"
                f"mold_color=#5a2d82", "-t", d]
    if kind == "pastel":
        return ["-f", "lavfi", "-i", f"gradients=s=240x428:c0=0xffb38a:c1=0x8a6dff:c2=0x4fd1c5:n=3:speed=0.02:"
                f"rate=24:duration={d}"]
    return ["-f", "lavfi", "-i", f"mandelbrot=s=240x428:rate=24:maxiter=160:start_scale=2.4:end_scale=0.0008:"
            f"end_pts={seconds * 24:.0f}:outer=normalized_iteration_count", "-t", d]


def library_backgrounds() -> dict[str, Path]:
    """Yöneticinin koyduğu arka plan videoları: <veri>/arka_planlar/*.mp4 (ad = dosya adı)."""
    folder = config.DATA_DIR / "arka_planlar"
    return {f"lib:{p.stem}": p for p in sorted(folder.glob("*.mp4"))} if folder.exists() else {}


def background_choices() -> dict[str, str]:
    return {**BACKGROUNDS, **{k: k[4:].replace("_", " ").capitalize() for k in library_backgrounds()}}


def render(ass_text: str, audio: Path, seconds: float, background: str, out: Path) -> Path:
    """Arka plan + çizimler (ASS) + ses → 720x1280 mp4."""
    import imageio_ffmpeg

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    lib = library_backgrounds()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / "f.ass").write_text(ass_text, encoding="utf-8")
        shutil.copy(FONT, tmp / FONT.name)
        shutil.copy(audio, tmp / "ses.wav")
        if background in lib:
            shutil.copy(lib[background], tmp / "bg.mp4")
            src = ["-stream_loop", "-1", "-i", "bg.mp4", "-t", f"{seconds:.2f}"]
        else:
            src = _bg_source(background if background in BACKGROUNDS else "girdap", seconds)
        vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase:flags=neighbor,crop={W}:{H},"
              f"setsar=1,fps=30,eq=brightness=-0.06:saturation=1.1,subtitles=f.ass:fontsdir=.,format=yuv420p[v]")
        subprocess.run([ff, "-y", "-loglevel", "error", *src, "-i", "ses.wav", "-filter_complex", vf,
                        "-map", "[v]", "-map", "1:a", "-t", f"{seconds:.2f}", "-c:v", "libx264", "-preset", "veryfast",
                        "-crf", "22", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "out.mp4"],
                       cwd=d, check=True, timeout=900)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp / "out.mp4"), out)
    return out


def join_audio(clips: list[Path], gap: float, lead: float, tail: float, out: Path) -> list[tuple[float, float]]:
    """Ses parçalarını aralarına sessizlik koyarak birleştirir; her parçanın (başlangıç, bitiş) zamanını döndürür."""
    import imageio_ffmpeg

    from .media import _probe

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    times, t = [], lead
    with tempfile.TemporaryDirectory() as d:
        args, parts = [], []
        for i, c in enumerate(clips):
            shutil.copy(c, Path(d) / f"a{i}.wav")
            args += ["-i", f"a{i}.wav"]
            dur = _probe(c)[1]
            times.append((t, t + dur))
            t += dur + gap
            parts.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo,"
                         f"adelay={int(times[-1][0] * 1000)}|{int(times[-1][0] * 1000)}[a{i}]")
        total = t - gap + tail
        mix = "".join(f"[a{i}]" for i in range(len(clips)))
        filt = ";".join(parts) + f";{mix}amix=inputs={len(clips)}:normalize=0,apad,atrim=0:{total:.3f}[o]"
        subprocess.run([ff, "-y", "-loglevel", "error", *args, "-filter_complex", filt, "-map", "[o]", "out.wav"],
                       cwd=d, check=True, timeout=300)
        shutil.move(str(Path(d) / "out.wav"), out)
    return times


def fake_voice(text: str, out: Path, voice: int = 0) -> Path:
    """Sahte mod: metin uzunluğuna göre süreli hafif bir ton (gerçek sürümde Gemini seslendirir)."""
    import imageio_ffmpeg

    dur = max(0.9, min(8.0, 0.32 * len(text.split()) + 0.3))
    freq = 220 if voice else 320
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"sine=frequency={freq}:duration={dur:.2f}", "-af", "volume=0.04", "-ar", "24000", str(out)],
                   check=True, timeout=60)
    return out


def estimate_seconds(n_words: int) -> int:
    return int(math.ceil(n_words * 0.36 + 2))
