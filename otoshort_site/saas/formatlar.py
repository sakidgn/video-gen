"""Viral formatlar: mesajlaşma hikâyesi, itiraf/hikâye anlatımı, "Hangisini seçerdin?" ve "Bil bakalım" quiz.
Video modeli kullanılmaz: yapay zekâ metni yazar, seslendirme (TTS) okunur, ffmpeg + libass ile arka plan videosunun
üstüne sohbet balonları / gönderi kartı ve kelime kelime altyazı çizilir. Bu yüzden ucuz ve hızlıdır."""
import math
import random
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
    "korku": ("Korku hikâyesi", "Ürpertici anlatım, karanlık kart ve kelime kelime altyazı"),
    "bilgi": ("Bunu biliyor muydun?", "Yalan gibi duran ama gerçek bilgiler, numaralı kartlarla"),
    "liste": ("Top 5 sıralama", "5'ten 1'e geri sayan liste, birinci sona saklanır"),
    "dogru": ("Doğru mu yanlış mı?", "İddia, geri sayım, sonra DOĞRU ya da YANLIŞ damgası"),
    "bayrak": ("Kırmızı bayrak mı?", "Davranış ekrana gelir, izleyici karar verir: kırmızı mı yeşil mi"),
    "bilmece": ("Bunu bilen dahidir", "Bilmece, geri sayım, sonra cevap; izleyici kaçını bildiğini yazar"),
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
for _lang, _w in {  # bilgi, sıralama, doğru/yanlış ve bayrak formatlarının sözleri
    "tr": {"facts": "BUNU BİLİYOR MUYDUN?", "facts_say": "Bunu biliyor muydun?", "fact": "BİLGİ",
           "top": "EN İYİ 5", "top_say": "İşte en iyi beş", "tf": "DOĞRU MU YANLIŞ MI?",
           "tf_say": "Doğru mu, yanlış mı?", "yes": "DOĞRU", "no": "YANLIŞ", "flag": "KIRMIZI BAYRAK MI?",
           "flag_say": "Kırmızı bayrak mı, yeşil bayrak mı?", "red": "KIRMIZI BAYRAK", "green": "YEŞİL BAYRAK",
           "follow": "Devamı için takip et!", "agree": "Katılıyor musun?"},
    "en": {"facts": "DID YOU KNOW?", "facts_say": "Did you know?", "fact": "FACT", "top": "TOP 5",
           "top_say": "Here are the top five", "tf": "TRUE OR FALSE?", "tf_say": "True or false?", "yes": "TRUE",
           "no": "FALSE", "flag": "RED FLAG OR GREEN FLAG?", "flag_say": "Red flag or green flag?",
           "red": "RED FLAG", "green": "GREEN FLAG", "follow": "Follow for more!", "agree": "Do you agree?"},
    "de": {"facts": "WUSSTEST DU SCHON?", "facts_say": "Wusstest du schon?", "fact": "FAKT", "top": "TOP 5",
           "top_say": "Hier sind die Top fünf", "tf": "WAHR ODER FALSCH?", "tf_say": "Wahr oder falsch?",
           "yes": "WAHR", "no": "FALSCH", "flag": "RED FLAG ODER GREEN FLAG?", "flag_say": "Red Flag oder Green Flag?",
           "red": "RED FLAG", "green": "GREEN FLAG", "follow": "Folge für mehr!", "agree": "Stimmst du zu?"},
    "es": {"facts": "¿SABÍAS QUE...?", "facts_say": "¿Sabías que...?", "fact": "DATO", "top": "TOP 5",
           "top_say": "Este es el top cinco", "tf": "¿VERDADERO O FALSO?", "tf_say": "¿Verdadero o falso?",
           "yes": "VERDADERO", "no": "FALSO", "flag": "¿BANDERA ROJA O VERDE?", "flag_say": "¿Bandera roja o verde?",
           "red": "BANDERA ROJA", "green": "BANDERA VERDE", "follow": "¡Síguenos para más!", "agree": "¿Estás de acuerdo?"},
    "ar": {"facts": "هل كنت تعلم؟", "facts_say": "هل كنت تعلم؟", "fact": "معلومة", "top": "أفضل 5",
           "top_say": "إليك أفضل خمسة", "tf": "صح أم خطأ؟", "tf_say": "صح أم خطأ؟", "yes": "صح", "no": "خطأ",
           "flag": "علامة حمراء أم خضراء؟", "flag_say": "علامة حمراء أم خضراء؟", "red": "علامة حمراء",
           "green": "علامة خضراء", "follow": "تابعنا للمزيد!", "agree": "هل توافق؟"},
}.items():
    WORDS[_lang].update(_w)
for _lang, _w in {  # bilmece formatı
    "tr": {"riddle": "BUNU BİLEN DAHİDİR", "riddle_say": "Bunu bilen dahidir!", "riddle_n": "BİLMECE"},
    "en": {"riddle": "ONLY GENIUSES GET THIS", "riddle_say": "Only geniuses get this!", "riddle_n": "RIDDLE"},
    "de": {"riddle": "NUR GENIES WISSEN DAS", "riddle_say": "Das wissen nur Genies!", "riddle_n": "RÄTSEL"},
    "es": {"riddle": "SOLO LOS GENIOS LO SABEN", "riddle_say": "¡Solo los genios lo saben!", "riddle_n": "ACERTIJO"},
    "ar": {"riddle": "لا يعرفه إلا العباقرة", "riddle_say": "لا يعرفه إلا العباقرة!", "riddle_n": "لغز"},
}.items():
    WORDS[_lang].update(_w)


def words(language: str) -> dict:
    return WORDS.get(language, WORDS["en"])


BACKGROUNDS = {  # anahtar: (etiket, ffmpeg lavfi kaynağı ya da None = kütüphanedeki video)
    "parkur": "Blok parkur",
    "girdap": "Sonsuz girdap",
    "piksel": "Piksel evren",
    "pastel": "Yumuşak renkler",
    "karanlik": "Karanlık sis",
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
              language: str, dark: bool = False) -> str:
    """İlk cümle (başlık) okunurken gönderi kartı; sonra her cümle kelime kelime viral altyazı.
    dark: korku hikâyesi için koyu kart ve kan kırmızısı vurgu."""
    card, ink, sub, accent = (("#141418", "#F2F2F2", "#8A8A92", "#C1121F") if dark
                              else ("#FFFFFF", INK, "#7C7C80", "#FF5A1F"))
    out = _header(f"Style: Viral,{FONT_NAME},{round(H * 0.07)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,"
                  f"100,100,1,0,1,{round(H * 0.07 * 0.14)},3,5,{round(W * .07)},{round(W * .07)},0,1")
    t_end = times[0][1] + 0.4 if times else 3.0
    lines = wrap(title, 27)
    card_h = 170 + len(lines) * 56 + 70
    x, y, cw = 48, int(H * 0.27), W - 96
    f = "\\fad(0,200)"
    out.append(_ev(0, 0, t_end, f"{{\\an7\\pos({x},{y}){f}\\p1\\c{_bgr(card)}}}{rrect(cw, card_h, 30)}"))
    out.append(_ev(1, 0, t_end, f"{{\\an7\\pos({x + 30},{y + 30}){f}\\p1\\c{_bgr(accent)}}}{rrect(68, 68, 34)}"))
    out.append(_ev(2, 0, t_end, f"{{\\an5\\pos({x + 64},{y + 64}){f}\\fs36\\b1\\c&HFFFFFF&}}"
                                f"{_upper(plain(community)[:1], language)}"))
    out.append(_ev(2, 0, t_end, f"{{\\an7\\pos({x + 116},{y + 32}){f}\\fs32\\b1\\c{_bgr(ink)}}}"
                                f"{plain(community)[:26]}"))
    out.append(_ev(2, 0, t_end, f"{{\\an7\\pos({x + 116},{y + 70}){f}\\fs24\\c{_bgr(sub)}}}"
                                f"{plain(config.SITE_NAME)}"))
    out.append(_ev(2, 0, t_end, f"{{\\an7\\pos({x + 30},{y + 130}){f}\\fs46\\b1\\c{_bgr(ink)}}}"
                                + "\\N".join(lines)))
    fy = y + card_h - 62
    out.append(_ev(2, 0, t_end, f"{{\\an7\\pos({x + 32},{fy + 6}){f}\\p1\\c{_bgr(accent)}}}m 13 0 l 26 20 l 0 20"))
    comments = "yorum" if language == "tr" else "comments"
    out.append(_ev(2, 0, t_end, f"{{\\an7\\pos({x + 68},{fy}){f}\\fs28\\b1\\c{_bgr(sub if dark else '#3C3C43')}}}"
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


# ---------- "Bunu biliyor muydun?", "Top 5" ve "Doğru mu yanlış mı?" / "Kırmızı bayrak mı?" ----------
def _viral_style() -> str:
    size = round(H * 0.07)
    return (f"Style: Viral,{FONT_NAME},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,1,0,1,"
            f"{round(size * 0.14)},3,5,{round(W * .07)},{round(W * .07)},0,1")


def _pill(a: float, b: float, text: str, y: int, color: str = YELLOW) -> list[str]:
    """Üstte ortalanmış etiket (ör. BİLGİ 2/5)."""
    w = max(160, len(text) * 19 + 64)
    return [_ev(4, a, b, f"{{\\an7\\pos({(W - w) // 2},{y})\\p1\\c{_bgr(color)}\\fad(100,0)}}{rrect(w, 64, 32)}"),
            _ev(5, a, b, f"{{\\an5\\pos({W // 2},{y + 32})\\fs40\\b1\\c&H111111&\\fad(100,0)}}{text}")]


def facts_ass(facts: list[str], times: list[tuple[float, float]], total: float, language: str) -> str:
    """times: açılış, her bilgi, kapanış. Her bilgi üstte numaralı etiketle, kelime kelime altyazıyla okunur."""
    w = words(language)
    out = _header(_viral_style())
    out += _title_card(0, times[1][0] if len(times) > 1 else total, w["facts"], "")
    segs = []
    for i, fact in enumerate(facts):
        start, spoken = times[i + 1]
        end = times[i + 2][0] if i + 2 < len(times) else total
        out += _pill(start, end, f"{w['fact']} {i + 1}/{len(facts)}", 230)
        segs.append({"start": start, "end": spoken, "text": fact})
    out += _viral_events(segs, language)
    if len(times) > len(facts) + 1:
        out += _title_card(times[-1][0], total, w["follow"], w["comment"])
    return "\n".join(out) + "\n"


def top_ass(topic: str, items: list[dict], times: list[tuple[float, float]], total: float, language: str) -> str:
    """items: [{"name", "why"}] 5'ten 1'e sırayla (sonuncusu birinci). Liste yukarıdan 1..n satır; her sıra
    okunduğunda kendi satırı sarı yanar, adı yazılır ve açıklaması altta görünür."""
    w = words(language)
    n = len(items)
    out = _header()
    first = times[1][0] if len(times) > 1 else total
    out += _title_card(0, first, w["top"], topic)
    out.append(_ev(3, first, total, f"{{\\an8\\pos({W // 2},56)\\fs62\\b1\\c{_bgr(YELLOW)}{OUTLINE}}}{w['top']}"))
    out.append(_ev(3, first, total, f"{{\\an8\\pos({W // 2},138)\\fs44\\b1\\c&HFFFFFF&{OUTLINE}}}{plain(topic)[:30]}"))
    row_y = lambda rank: 240 + (rank - 1) * 118  # noqa: E731
    for rank in range(1, n + 1):
        y = row_y(rank)
        out.append(_ev(0, first, total, f"{{\\an7\\pos(132,{y})\\p1\\c&HFFFFFF&\\1a&H50&}}{rrect(W - 168, 96, 24)}"))
        out.append(_ev(1, first, total, f"{{\\an7\\pos(36,{y + 8})\\p1\\c{_bgr(VIOLET)}}}{rrect(80, 80, 40)}"))
        out.append(_ev(2, first, total, f"{{\\an5\\pos(76,{y + 48})\\fs52\\b1\\c&HFFFFFF&}}{rank}"))
    for i, item in enumerate(items):
        rank = n - i
        y = row_y(rank)
        start, _ = times[i + 1]
        end = times[i + 2][0] if i + 2 < len(times) else total
        out.append(_ev(1, start, end, f"{{\\an7\\pos(132,{y})\\p1\\c{_bgr(YELLOW)}{_pop(160)}}}{rrect(W - 168, 96, 24)}"))
        out.append(_ev(2, start, total, f"{{\\an4\\pos(158,{y + 48})\\fs46\\b1\\c&H111111&\\fad(150,0)}}"
                                        f"{plain(item['name'])[:24]}"))
        why = wrap(item.get("why", ""), 26)
        if why and why != [""]:
            wy = row_y(n) + 150
            out.append(_ev(3, start, end, f"{{\\an8\\pos({W // 2},{wy})\\fs54\\b1\\c&HFFFFFF&{OUTLINE}\\fad(150,0)}}"
                                          + "\\N".join(why[:3])))
    if len(times) > n + 1:
        out += _title_card(times[-1][0], total, w["agree"], w["comment"])
    return "\n".join(out) + "\n"


def verdict_ass(kind: str, items: list[dict], times: list[tuple[float, float]], total: float, language: str) -> str:
    """kind: "dogru" (DOĞRU/YANLIŞ) ya da "bayrak" (YEŞİL/KIRMIZI BAYRAK). items: [{"text", "ok", "why"}];
    times: açılış, her madde için (iddia, karar), kapanış. İddia kartı + geri sayım, sonra eğik damga ve gerekçe."""
    w = words(language)
    title, yes, no = (w["tf"], w["yes"], w["no"]) if kind == "dogru" else (w["flag"], w["green"], w["red"])
    out = _header()
    out += _title_card(0, times[1][0] if len(times) > 1 else total, title, "")
    n = len(items)
    for i, item in enumerate(items):
        start, spoken = times[1 + 2 * i]
        reveal = times[2 + 2 * i][0] if 2 + 2 * i < len(times) else total
        end = times[3 + 2 * i][0] if 3 + 2 * i < len(times) else total
        out.append(_ev(3, start, end, f"{{\\an8\\pos({W // 2},62)\\fs48\\b1\\c{_bgr(YELLOW)}{OUTLINE}}}"
                                      f"{title} {i + 1}/{n}"))
        lines = wrap(item["text"], 20)
        card_h = 80 + len(lines) * 70
        top = 250
        out.append(_ev(0, start, end, f"{{\\an7\\pos(40,{top})\\p1\\c&HFFFFFF&\\fad(120,0)}}{rrect(W - 80, card_h, 34)}"))
        out.append(_ev(1, start, end, f"{{\\an5\\pos({W // 2},{top + card_h / 2:.0f})\\fs60\\b1\\c&H111111&\\fad(120,0)}}"
                                      + "\\N".join(lines)))
        mid = top + card_h + 150
        think = min(reveal, spoken + 0.15)
        if reveal - think > 0.6:
            out += _countdown(think, reveal, W // 2, mid, 96, 150)
            out += _bar(think, reveal)
        label, color = (yes, GREEN) if item["ok"] else (no, RED)
        sw = max(360, len(label) * 34 + 90)
        rot = f"\\org({W // 2},{mid})\\frz6"
        out.append(_ev(4, reveal, end, f"{{\\an7\\pos({(W - sw) // 2},{mid - 62}){rot}\\p1\\c{_bgr(color)}{_pop(160)}}}"
                                       f"{rrect(sw, 124, 30)}"))
        out.append(_ev(5, reveal, end, f"{{\\an5\\pos({W // 2},{mid}){rot}\\fs64\\b1\\c&HFFFFFF&{_pop(160)}}}{label}"))
        why = wrap(item.get("why", ""), 26)
        if why and why != [""]:
            out.append(_ev(5, reveal, end, f"{{\\an8\\pos({W // 2},{mid + 110})\\fs52\\b1\\c&HFFFFFF&{OUTLINE}\\fad(150,0)}}"
                                           + "\\N".join(why[:3])))
    if len(times) > 2 * n + 1:
        out += _title_card(times[-1][0], total, w["agree"], w["comment"])
    return "\n".join(out) + "\n"


def riddle_ass(items: list[dict], times: list[tuple[float, float]], total: float, language: str) -> str:
    """Bilmece: items [{"q", "answer"}]; times: açılış, her bilmece için (soru, cevap), kapanış.
    Soru kartı + geri sayım ve dolan çubuk, sonra cevap yeşil kutuda büyüyerek açılır."""
    w = words(language)
    out = _header()
    out += _title_card(0, times[1][0] if len(times) > 1 else total, w["riddle"], "")
    n = len(items)
    for i, item in enumerate(items):
        start, spoken = times[1 + 2 * i]
        reveal = times[2 + 2 * i][0] if 2 + 2 * i < len(times) else total
        end = times[3 + 2 * i][0] if 3 + 2 * i < len(times) else total
        out += _pill(start, end, f"{w['riddle_n']} {i + 1}/{n}", 40)
        lines = wrap(item["q"], 20)
        card_h = 80 + len(lines) * 70
        top = 230
        out.append(_ev(0, start, end, f"{{\\an7\\pos(40,{top})\\p1\\c&HFFFFFF&\\fad(120,0)}}{rrect(W - 80, card_h, 34)}"))
        out.append(_ev(1, start, end, f"{{\\an5\\pos({W // 2},{top + card_h / 2:.0f})\\fs58\\b1\\c&H111111&\\fad(120,0)}}"
                                      + "\\N".join(lines)))
        mid = top + card_h + 170
        think = min(reveal, spoken + 0.15)
        if reveal - think > 0.6:
            out += _countdown(think, reveal, W // 2, mid, 96, 150)
            out += _bar(think, reveal)
        ans = wrap(item["answer"], 16)[:2]
        bw = max(320, max(len(x) for x in ans) * 38 + 100)
        bh = 40 + len(ans) * 78
        out.append(_ev(4, reveal, end, f"{{\\an7\\pos({(W - bw) // 2},{mid - bh // 2})\\p1\\c{_bgr(GREEN)}{_pop(160)}}}"
                                       f"{rrect(bw, bh, 30)}"))
        out.append(_ev(5, reveal, end, f"{{\\an5\\pos({W // 2},{mid})\\fs66\\b1\\c&HFFFFFF&{_pop(160)}}}"
                                       + "\\N".join(ans)))
    if len(times) > 2 * n + 1:
        out += _title_card(times[-1][0], total, w["score"], w["comment"])
    return "\n".join(out) + "\n"


# ---------- arka plan ----------
def _bg_source(kind: str, seconds: float) -> list[str]:
    d = f"{seconds:.2f}"
    if kind == "piksel":
        return ["-f", "lavfi", "-i", f"life=s=72x128:mold=6:r=8:ratio=0.10:death_color=#120c22:life_color=#ffb15c:"
                f"mold_color=#5a2d82", "-t", d]
    if kind == "karanlik":  # korku hikâyeleri için koyu, yavaş dalgalanan sis
        return ["-f", "lavfi", "-i", f"gradients=s=240x428:c0=0x040406:c1=0x2a0610:c2=0x0a1018:c3=0x000000:n=4:"
                f"speed=0.012:rate=24:duration={d}"]
    if kind == "pastel":
        return ["-f", "lavfi", "-i", f"gradients=s=240x428:c0=0xffb38a:c1=0x8a6dff:c2=0x4fd1c5:n=3:speed=0.02:"
                f"rate=24:duration={d}"]
    return ["-f", "lavfi", "-i", f"mandelbrot=s=240x428:rate=24:maxiter=160:start_scale=2.4:end_scale=0.0008:"
            f"end_pts={seconds * 24:.0f}:outer=normalized_iteration_count", "-t", d]


def library_backgrounds() -> dict[str, Path]:
    """Yöneticinin koyduğu arka plan videoları: <veri>/arka_planlar/*.mp4|mkv|webm|mov (ad = dosya adı)."""
    folder = config.DATA_DIR / "arka_planlar"
    if not folder.exists():
        return {}
    exts = {".mp4", ".mkv", ".webm", ".mov", ".m4v"}
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in exts)
    return {f"lib:{p.name[:-len(p.suffix)].split('.')[0]}": p for p in files}


def background_choices() -> dict[str, str]:
    """Seçilebilen arka planlar. Klasöre sitedekiyle aynı adda video konursa (ör. parkur.mp4) sitenin kendi
    videosunun yerine geçer: anahtar aynı kalır (eski kanallar etkilenmez), adı "Parkur" olur."""
    lib = library_backgrounds()
    base = {k: ("Parkur" if f"lib:{k}" in lib else v) for k, v in BACKGROUNDS.items()}
    return {**base, **{k: k[4:].replace("_", " ").capitalize() for k in lib if k[4:] not in BACKGROUNDS}}


def background_video(key: str) -> Path | None:
    """Arka planın video dosyası: klasördeki video (aynı adlıysa sitenin videosunun yerine), yoksa sitenin videosu."""
    lib = library_backgrounds()
    return lib.get(key) or lib.get(f"lib:{key}") or BUILTIN_VIDEOS.get(key)


# Siteyle gelen video arka planlar (kendi ürettiğimiz; araclar/parkur/yap.py)
BUILTIN_VIDEOS = {"parkur": config.ROOT / "static" / "arka_planlar" / "parkur.mp4"}
DEFAULT_BACKGROUND = "parkur"


def default_background() -> str:
    """Varsayılan arka plan: .env'de VARSAYILAN_ARKA_PLAN (ör. minecraft_parkur) varsa o, yoksa kütüphaneye konan
    ilk video, o da yoksa sitenin kendi parkuru."""
    lib = {k: v for k, v in library_backgrounds().items() if k[4:] not in BACKGROUNDS}
    want = config._env("VARSAYILAN_ARKA_PLAN")
    for key in (want, f"lib:{want}"):
        if key and key in background_choices():
            return key
    return next(iter(lib), DEFAULT_BACKGROUND)


def random_start(video: Path, seconds: float) -> float:
    """Arka plan videosu istenen süreden epey uzunsa daha önce kullanılmamış rastgele bir başlangıç anı (sn);
    kısaysa 0 (döngüyle oynar). Kullanılan aralıklar <veri>/arka_plan_kullanim.json'da tutulur, böylece uzun bir
    kayıttan (ör. 2,5 saatlik parkur) aynı kısım tekrar gelmez; video bitince en baştan yeniden dağıtılır."""
    import json
    import random
    import threading

    from .media import _probe

    total = _probe(video)[1]
    if total <= seconds + 10:
        return 0.0
    store = config.DATA_DIR / "arka_plan_kullanim.json"
    lock = random_start.__dict__.setdefault("lock", threading.Lock())
    with lock:
        try:
            used = json.loads(store.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            used = {}
        key = f"{video.name}:{int(total)}"
        spans = [tuple(x) for x in used.get(key, [])]
        lo, hi = 1.0, total - seconds - 2
        free = []  # kullanılmamış boşluklar (başlangıç, bitiş)
        cur = lo
        for a, b in sorted(spans):
            if a - cur >= seconds:
                free.append((cur, a - seconds))
            cur = max(cur, b)
        if hi - cur >= 0:
            free.append((cur, hi))
        if not free:  # hepsi kullanıldı: baştan başla
            spans, free = [], [(lo, hi)]
        a, b = random.choices(free, weights=[y - x + 1 for x, y in free])[0]
        start = random.uniform(a, max(a, b))
        spans.append((round(start, 2), round(start + seconds + 1, 2)))
        used[key] = spans
        try:
            store.parent.mkdir(parents=True, exist_ok=True)
            store.write_text(json.dumps(used), encoding="utf-8")
        except OSError:
            pass
    return start


MUSIC_EXTS = {".mp3", ".m4a", ".wav", ".ogg", ".aac", ".flac"}


def music_tracks() -> dict[str, Path]:
    """Fon müzikleri: <veri>/muzikler/ klasörüne konan telifsiz parçalar (ad = dosya adı)."""
    folder = config.DATA_DIR / "muzikler"
    if not folder.exists():
        return {}
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in MUSIC_EXTS)
    return {p.name[:-len(p.suffix)].split(".")[0][:50]: p for p in files}


def music_choices() -> dict[str, str]:
    """Formdaki seçenekler: "rastgele" + her parça (ad → görünen ad)."""
    tracks = music_tracks()
    return {"rastgele": "Rastgele", **{k: k.replace("_", " ").replace("-", " ").capitalize() for k in tracks}} \
        if tracks else {}


def pick_music(choice: str) -> Path | None:
    """Seçime göre parça: "" yok, "rastgele" klasörden rastgele, ya da adıyla. Parça silinmişse rastgele."""
    import random

    tracks = music_tracks()
    if not choice or not tracks:
        return None
    return tracks.get(choice) or random.choice(list(tracks.values()))


def render(ass_text: str, audio: Path, seconds: float, background: str, out: Path, music: Path | None = None) -> Path:
    """Arka plan + çizimler (ASS) + ses (+ fon müziği) → 720x1280 mp4.
    Müzik konuşma sırasında kısılır (sidechain), sonda yavaşça biter; uzun parçada rastgele bir yerden başlar."""
    import imageio_ffmpeg

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / "f.ass").write_text(ass_text, encoding="utf-8")
        shutil.copy(FONT, tmp / FONT.name)
        shutil.copy(audio, tmp / "ses.wav")
        if background_video(background):
            bg = background_video(background)
            start = random_start(bg, seconds)  # uzun videodan (ör. 2 saatlik oyun kaydı) her seferinde başka bir an
            if start:  # dosyayı kopyalamadan doğrudan oradan okunur
                src = ["-ss", f"{start:.2f}", "-i", str(bg), "-t", f"{seconds:.2f}"]
            else:
                shutil.copy(bg, tmp / "bg.mp4")
                src = ["-stream_loop", "-1", "-i", "bg.mp4", "-t", f"{seconds:.2f}"]
        else:
            src = _bg_source(background if background in BACKGROUNDS else "girdap", seconds)
        vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase:flags=neighbor,crop={W}:{H},"
              f"setsar=1,fps=30,eq=brightness=-0.06:saturation=1.1,subtitles=f.ass:fontsdir=.,format=yuv420p[v]")
        amap, msrc = "1:a", []
        if music:
            from .media import _probe

            mdur = _probe(music)[1]
            mstart = random.uniform(0, mdur - seconds - 1) if mdur > seconds + 20 else 0.0
            msrc = ["-stream_loop", "-1", "-ss", f"{mstart:.2f}", "-i", str(music)]
            fade = max(0.0, seconds - 1.5)
            vf += (f";[2:a]aresample=44100,aformat=channel_layouts=stereo,volume=0.32,afade=t=in:d=0.8,"
                   f"afade=t=out:st={fade:.2f}:d=1.5[m];[1:a]aresample=44100,aformat=channel_layouts=stereo,asplit=2[v1][v2];"
                   f"[m][v1]sidechaincompress=threshold=0.02:ratio=6:attack=15:release=350[md];"
                   f"[v2][md]amix=inputs=2:duration=first:normalize=0[a]")
            amap = "[a]"
        subprocess.run([ff, "-y", "-loglevel", "error", *src, "-i", "ses.wav", *msrc, "-filter_complex", vf,
                        "-map", "[v]", "-map", amap, "-t", f"{seconds:.2f}", "-c:v", "libx264", "-preset", "veryfast",
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

    freq = 220 if voice else 320
    paras = [p for p in text.split("\n\n") if p.strip()] or [text]
    srcs, chain = [], []
    for i, p in enumerate(paras):  # her paragraf bir ton, aralarında 0.6 sn sessizlik
        dur = max(0.9, min(8.0, 0.32 * len(p.split()) + 0.3))
        srcs += ["-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=24000:duration={dur:.2f}"]
        chain.append(f"[{2 * i}:a]")
        if i < len(paras) - 1:
            srcs += ["-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono:d=0.6"]
            chain.append(f"[{2 * i + 1}:a]")
    filt = "".join(chain) + f"concat=n={len(chain)}:v=0:a=1,volume=0.3,aresample=24000[a]"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", *srcs, "-filter_complex", filt,
                    "-map", "[a]", "-ac", "1", str(out)], check=True, timeout=60)
    return out


def silences(audio: Path, noise_db: int = -38, min_len: float = 0.18) -> tuple[list[tuple[float, float]], float]:
    """Sesteki sessiz aralıklar [(başlangıç, bitiş)] ve toplam süre (ffmpeg silencedetect)."""
    import re

    import imageio_ffmpeg

    from .media import _probe

    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(audio), "-af",
                        f"silencedetect=noise={noise_db}dB:d={min_len}", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=120)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    total = _probe(audio)[1]
    return [(a, b) for a, b in zip(starts, ends + [total] * (len(starts) - len(ends)))], total


def split_audio(audio: Path, n: int, out_dir: Path, prefix: str, weights: list[float] | None = None) -> list[Path] | None:
    """Tek seferde seslendirilmiş n satırlık sesi en uzun n-1 sessizlikten bölüp n parçaya ayırır.
    Yeterince belirgin sessizlik yoksa ya da parça süreleri satır uzunluklarına (weights) uymuyorsa None
    (çağıran satır satır seslendirir)."""
    import imageio_ffmpeg

    gaps, total = silences(audio)
    inner = [(a, b) for a, b in gaps if a > 0.05 and b < total - 0.05]
    if len(inner) < n - 1:
        return None
    cuts = sorted(sorted(inner, key=lambda g: g[1] - g[0], reverse=True)[:n - 1])
    lead = gaps[0][1] if gaps and gaps[0][0] <= 0.05 else 0.0
    tail = gaps[-1][0] if gaps and gaps[-1][1] >= total - 0.05 else total
    bounds = [lead, *(x for a, b in cuts for x in (a, b)), tail]
    if weights:  # bir satır cümle içi duraksamadan bölündüyse süreler orantısız çıkar: güvenme
        spoken, wsum = sum(bounds[2 * i + 1] - bounds[2 * i] for i in range(n)), sum(weights)
        for i in range(n):
            share = (bounds[2 * i + 1] - bounds[2 * i]) / spoken
            if not weights[i] / wsum / 3 <= share <= weights[i] / wsum * 3:
                return None
    parts = []
    for i in range(n):
        a, b = bounds[2 * i], bounds[2 * i + 1]
        if b - a < 0.15:
            return None
        out = out_dir / f"{prefix}{i}.wav"
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(audio), "-ss", f"{a:.3f}",
                        "-to", f"{b:.3f}", "-ar", "24000", "-ac", "1", str(out)], check=True, timeout=60)
        parts.append(out)
    return parts


def estimate_seconds(n_words: int) -> int:
    return int(math.ceil(n_words * 0.36 + 2))
