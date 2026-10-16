"""Viral formatlar: mesajlaşma hikâyesi, itiraf/hikâye anlatımı, "Hangisini seçerdin?" ve "Bil bakalım" quiz.
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
    "secim": ("Hangisini seçerdin?", "İki seçenek ve geri sayım; izleyici cevabını yoruma yazar"),
    "quiz": ("Bil bakalım", "Soru, üç şık, geri sayım ve doğru cevap"),
}
THINK = 3.0  # seçim/quiz turlarında izleyiciye düşünme süresi (sn)
# Videoda çizilen ve seslendirilen kalıp sözler (videonun dilinde; listede olmayan dil İngilizce)
WORDS = {
    "tr": {"wyr": "HANGİSİNİ SEÇERDİN?", "wyr_say": "Hangisini seçerdin?", "or": "VEYA", "or_word": "yoksa",
           "pick": "Sen hangisini seçerdin?", "comment": "Yorumlara yaz!", "quiz": "BİL BAKALIM",
           "quiz_say": "Bil bakalım!", "q": "SORU", "answer": "Doğru cevap", "score": "Kaç tanesini bildin?"},
    "en": {"wyr": "WOULD YOU RATHER?", "wyr_say": "Would you rather...", "or": "OR", "or_word": "or",
           "pick": "Which one would you pick?", "comment": "Tell us in the comments!", "quiz": "QUIZ TIME",
           "quiz_say": "Quiz time!", "q": "QUESTION", "answer": "The answer is", "score": "How many did you get right?"},
    "de": {"wyr": "WAS WÜRDEST DU WÄHLEN?", "wyr_say": "Was würdest du wählen?", "or": "ODER", "or_word": "oder",
           "pick": "Was würdest du wählen?", "comment": "Schreib es in die Kommentare!", "quiz": "QUIZ-ZEIT",
           "quiz_say": "Quiz-Zeit!", "q": "FRAGE", "answer": "Die Antwort ist", "score": "Wie viele hattest du richtig?"},
    "es": {"wyr": "¿QUÉ PREFIERES?", "wyr_say": "¿Qué prefieres?", "or": "O", "or_word": "o",
           "pick": "¿Tú cuál elegirías?", "comment": "¡Cuéntanos en los comentarios!", "quiz": "¡HORA DEL QUIZ!",
           "quiz_say": "¡Hora del quiz!", "q": "PREGUNTA", "answer": "La respuesta es", "score": "¿Cuántas acertaste?"},
    "ar": {"wyr": "ماذا تختار؟", "wyr_say": "ماذا تختار؟", "or": "أو", "or_word": "أو", "pick": "أيهما تختار؟",
           "comment": "اكتب في التعليقات!", "quiz": "اختبر معلوماتك", "quiz_say": "اختبر معلوماتك!", "q": "سؤال",
           "answer": "الإجابة الصحيحة", "score": "كم إجابة صحيحة عرفت؟"},
}


def words(language: str) -> dict:
    return WORDS.get(language, WORDS["en"])
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


# ---------- "Hangisini seçerdin?" ve "Bil bakalım" ----------
YELLOW, RED, BLUE2, GREEN, VIOLET = "#FFD23F", "#FF3B5C", "#2D7BFF", "#22C55E", "#6C5CE7"
OUTLINE = "\\bord4\\3c&H000000&\\shad0"


def _pop(ms: int = 180) -> str:
    return f"\\fscx82\\fscy82\\t(0,{ms},\\fscx100\\fscy100)"


def _bar(a: float, b: float) -> list[str]:
    """Düşünme süresi çubuğu: a→b arasında soldan sağa dolar."""
    x0, x1, y, ms = 80, 640, 1196, int((b - a) * 1000)
    track = rrect(x1 - x0, 16, 8)
    return [_ev(5, a, b, f"{{\\an7\\pos({x0},{y})\\p1\\c&HFFFFFF&\\1a&HA0&}}{track}"),
            _ev(6, a, b, f"{{\\an7\\pos({x0},{y})\\p1\\c{_bgr(YELLOW)}\\clip({x0},{y - 4},{x0},{y + 20})"
                         f"\\t(0,{ms},\\clip({x0},{y - 4},{x1},{y + 20}))}}{track}")]


def _countdown(a: float, b: float, x: int, y: int, fs: int = 76, disc: int = 0) -> list[str]:
    """3, 2, 1… sayıları (her biri kendi saniyesinde büyüyerek belirir). disc: arkasına koyu daire (çap)."""
    n = max(1, round(b - a))
    step = (b - a) / n
    back = [_ev(6, a, b, f"{{\\an7\\pos({x - disc // 2},{y - disc // 2})\\p1\\c&H111111&\\1a&H08&}}"
                         f"{rrect(disc, disc, disc / 2)}")] if disc else []
    return back + [_ev(7, a + k * step, a + (k + 1) * step, f"{{\\an5\\pos({x},{y})\\fs{fs}\\b1\\c{_bgr(YELLOW)}{OUTLINE}"
                                                      f"\\fscx135\\fscy135\\t(0,220,\\fscx100\\fscy100)}}{n - k}")
            for k in range(n)]


def _title_card(a: float, b: float, big: str, small: str) -> list[str]:
    """Açılış / kapanış kartı: ortada koyu kart, büyük sarı başlık ve altında beyaz yazı."""
    big_lines, small_lines = wrap(big, 14), wrap(small, 22)
    h = 100 + len(big_lines) * 104 + len(small_lines) * 70
    y = (H - h) / 2
    out = [_ev(0, a, b, f"{{\\an7\\pos(60,{y:.0f})\\p1\\c&H111111&\\1a&H18&\\fad(120,120)}}{rrect(W - 120, h, 40)}"),
           _ev(1, a, b, f"{{\\an8\\pos({W // 2},{y + 40:.0f})\\fs98\\b1\\c{_bgr(YELLOW)}\\fad(120,120){_pop()}}}"
                        + "\\N".join(big_lines))]
    if small_lines:
        out.append(_ev(1, a, b, f"{{\\an8\\pos({W // 2},{y + 62 + len(big_lines) * 104:.0f})\\fs62\\b1\\c&HFFFFFF&"
                                f"\\fad(120,120)}}" + "\\N".join(small_lines)))
    return out


def wyr_ass(rounds: list[dict], times: list[tuple[float, float]], total: float, language: str) -> str:
    """rounds: [{"a", "b"}]; times: açılış, her tur, kapanış seslerinin (başlangıç, bitiş) saniyeleri.
    Ekran ikiye bölünür (üst kırmızı, alt mavi), ortada VEYA; seçenekler okunduktan sonra 3-2-1 geri sayım."""
    w = words(language)
    out = _header()
    out += _title_card(0, times[1][0] if len(times) > 1 else total, w["wyr"], "")
    for i, r in enumerate(rounds):
        start, spoken = times[i + 1]
        end = times[i + 2][0] if i + 2 < len(times) else total
        out.append(_ev(0, start, end, f"{{\\an7\\pos(36,150)\\p1\\c{_bgr(RED)}\\1a&H10&}}{rrect(W - 72, 500, 40)}"))
        out.append(_ev(0, start, end, f"{{\\an7\\pos(36,690)\\p1\\c{_bgr(BLUE2)}\\1a&H10&}}{rrect(W - 72, 500, 40)}"))
        out.append(_ev(2, start, end, f"{{\\an8\\pos({W // 2},48)\\fs60\\b1\\c&HFFFFFF&{OUTLINE}}}{w['wyr']}"))
        out.append(_ev(2, start, end, f"{{\\an5\\pos({W // 2},400)\\fs82\\b1\\c&HFFFFFF&{OUTLINE}\\fad(150,0){_pop()}}}"
                                      + "\\N".join(wrap(r["a"], 17))))
        out.append(_ev(2, start, end, f"{{\\an5\\pos({W // 2},940)\\fs82\\b1\\c&HFFFFFF&{OUTLINE}\\fad(150,0){_pop()}}}"
                                      + "\\N".join(wrap(r["b"], 17))))
        out.append(_ev(3, start, end, f"{{\\an7\\pos({W // 2 - 66},604)\\p1\\c&HFFFFFF&}}{rrect(132, 132, 66)}"))
        think = min(end, spoken + 0.15)
        out.append(_ev(4, start, think, f"{{\\an5\\pos({W // 2},670)\\fs46\\b1\\c&H111111&}}{w['or']}"))
        if end - think > 0.6:
            out += _countdown(think, end, W // 2, 670, 96)
            out += _bar(think, end)
    if len(times) > len(rounds) + 1:
        out += _title_card(times[-1][0], total, w["pick"], w["comment"])
    return "\n".join(out) + "\n"


def quiz_ass(topic: str, questions: list[dict], times: list[tuple[float, float]], total: float, language: str) -> str:
    """questions: [{"q", "options": [3], "answer": 0-2}]; times: açılış, her soru için (soru, cevap), kapanış.
    Soru kartı ve şıklar görünür, okunduktan sonra geri sayım, sonra doğru şık yeşile döner."""
    w = words(language)
    out = _header()
    out += _title_card(0, times[1][0] if len(times) > 1 else total, w["quiz"], topic)
    n = len(questions)
    for i, q in enumerate(questions):
        start, spoken = times[1 + 2 * i]
        reveal = times[2 + 2 * i][0] if 2 + 2 * i < len(times) else total
        end = times[3 + 2 * i][0] if 3 + 2 * i < len(times) else total
        out.append(_ev(2, start, end, f"{{\\an8\\pos({W // 2},62)\\fs50\\b1\\c{_bgr(YELLOW)}{OUTLINE}}}"
                                      f"{w['quiz']} · {w['q']} {i + 1}/{n}"))
        q_lines = wrap(q["q"], 24)
        card_h = 70 + len(q_lines) * 70
        opt_lines = [wrap(opt, 26) for opt in q["options"]]
        heights = [108 if len(x) == 1 else 160 for x in opt_lines]
        # soru kartı + şıklar + geri sayım ekranın ortasında dursun
        top = max(130, (H - (card_h + 34 + sum(h + 20 for h in heights) + 190)) / 2)
        out.append(_ev(0, start, end, f"{{\\an7\\pos(40,{top:.0f})\\p1\\c&HFFFFFF&\\fad(120,0)}}{rrect(W - 80, card_h, 32)}"))
        out.append(_ev(1, start, end, f"{{\\an7\\pos(70,{top + 32:.0f})\\fs62\\b1\\c&H111111&\\fad(120,0)}}"
                                      + "\\N".join(q_lines)))
        y = top + card_h + 34
        for j, (o_lines, bh) in enumerate(zip(opt_lines, heights)):
            good = j == q["answer"]
            delay = "\\fad(150,0)"
            out.append(_ev(0, start, reveal, f"{{\\an7\\pos(40,{y:.0f})\\p1\\c&HFFFFFF&\\1a&H18&{delay}}}{rrect(W - 80, bh, 26)}"))
            out.append(_ev(0, reveal, end, f"{{\\an7\\pos(40,{y:.0f})\\p1\\c{_bgr(GREEN if good else '#2A2A30')}"
                                           f"\\1a&H{'00' if good else '18'}&{_pop(160) if good else ''}}}{rrect(W - 80, bh, 26)}"))
            out.append(_ev(1, start, end, f"{{\\an7\\pos(64,{y + bh / 2 - 28:.0f})\\p1\\c{_bgr(VIOLET)}{delay}}}{rrect(56, 56, 28)}"))
            out.append(_ev(2, start, end, f"{{\\an5\\pos(92,{y + bh / 2:.0f})\\fs42\\b1\\c&HFFFFFF&{delay}}}{'ABC'[j]}"))
            out.append(_ev(2, start, reveal, f"{{\\an4\\pos(140,{y + bh / 2:.0f})\\fs50\\b1\\c&H111111&{delay}}}"
                                             + "\\N".join(o_lines)))
            out.append(_ev(2, reveal, end, f"{{\\an4\\pos(140,{y + bh / 2:.0f})\\fs50\\b1"
                                           f"\\c{'&HFFFFFF&' if good else '&H9A9A9A&'}}}" + "\\N".join(o_lines)))
            y += bh + 20
        think = min(reveal, spoken + 0.15)
        if reveal - think > 0.6:
            out += _countdown(think, reveal, W // 2, round(y + 100), 96, 150)
            out += _bar(think, reveal)
    if len(times) > 2 * n + 1:
        out += _title_card(times[-1][0], total, w["score"], w["comment"])
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


def join_audio(clips: list[Path], gap: float | list[float], lead: float, tail: float,
               out: Path) -> list[tuple[float, float]]:
    """Ses parçalarını aralarına sessizlik koyarak birleştirir; her parçanın (başlangıç, bitiş) zamanını döndürür.
    gap: her parçadan sonraki sessizlik (tek sayı ya da parça başına liste; ör. quizde düşünme süresi)."""
    gaps = list(gap) if isinstance(gap, (list, tuple)) else [gap] * len(clips)
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
            t += dur + gaps[i]
            parts.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo,"
                         f"adelay={int(times[-1][0] * 1000)}|{int(times[-1][0] * 1000)}[a{i}]")
        total = t - gaps[-1] + tail
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
