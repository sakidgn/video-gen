"""Ana sayfadaki "Viral formatlar" kartlarının örnek videolarını üretir (sitenin kendi format motoruyla):
mesajlaşma, itiraf, "Hangisini seçerdin?" ve "Bil bakalım".
Ses yok (kartlar sessiz oynar); süreler kelime sayısına göre. Çıktı: saas/static/formatlar/{ad}[-en].mp4 + .jpg

    python araclar/format_ornekleri.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from saas import formatlar as F  # noqa: E402

OUT = ROOT / "saas" / "static" / "formatlar"

CHAT = {
    "tr": ("Annem", [
        (False, "Oğlum dün gece 3'te neden çevrimiçiydin?"), (True, "Ders çalışıyordum anne"),
        (False, "Hangi ders? Saat 3'te?"), (True, "Gece kimyası. Moleküller gece daha aktif oluyor"),
        (False, "Baban kimya öğretmeni, ona soralım mı?"), (True, "Anne dur"),
        (False, "Sordum. Moleküller de uyuyormuş."), (True, "Kimya değişmiş demek ki")]),
    "en": ("Mom", [
        (False, "Why were you online at 3 am?"), (True, "I was studying mom"),
        (False, "Studying what? At 3?"), (True, "Night chemistry. Molecules are more active at night"),
        (False, "Your dad teaches chemistry, should I ask him?"), (True, "Mom wait"),
        (False, "Asked him. Molecules sleep too."), (True, "Chemistry must have changed")]),
}
STORY = {
    "tr": ("İtiraf köşesi", [
        "Ev arkadaşım üç aydır yoğurdumu yiyordu ve bunu nasıl öğrendiğime inanamayacaksınız",
        "Her sabah buzdolabını açtığımda yoğurdum biraz daha azalıyordu.",
        "Bir gün kabın altına küçük bir not yazdım: Seni görüyorum.",
        "Ertesi sabah notun altına cevap yazılmıştı: Ben de seni.",
        "Sorun şu ki ben yalnız yaşıyorum."]),
    "en": ("Confessions", [
        "My roommate had been eating my yogurt for three months and you won't believe how I found out",
        "Every morning there was a little less yogurt in the fridge.",
        "One day I left a tiny note under the lid: I see you.",
        "The next morning someone had written back: I see you too.",
        "The problem is, I live alone."]),
}


SECIM = {
    "tr": [("Her sabah 5'te uyanmak", "Her gece 3'te uyumak"), ("Bir yıl internetsiz", "Bir yıl tatlısız"),
           ("Bütün dilleri konuşmak", "Bütün hayvanlarla konuşmak")],
    "en": [("Wake up at 5 am every day", "Go to bed at 3 am every night"), ("A year without internet",
           "A year without dessert"), ("Speak every language", "Talk to every animal")],
}
QUIZ = {
    "tr": ("Genel kültür", [("Dünyanın en büyük okyanusu hangisi?", ["Atlas Okyanusu", "Büyük Okyanus", "Hint Okyanusu"], 1),
                            ("Güneş sistemindeki en büyük gezegen hangisi?", ["Jüpiter", "Satürn", "Neptün"], 0)]),
    "en": ("General knowledge", [("What is the largest ocean on Earth?", ["Atlantic Ocean", "Pacific Ocean", "Indian Ocean"], 1),
                                 ("Which is the largest planet in the solar system?", ["Jupiter", "Saturn", "Neptune"], 0)]),
}


def silent_clips(texts: list[str], tmp: Path) -> list[Path]:
    import imageio_ffmpeg

    out = []
    for i, t in enumerate(texts):
        dur = max(1.1, min(6.0, 0.34 * len(t.split()) + 0.4))
        p = tmp / f"c{i}.wav"
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        f"anullsrc=r=24000:cl=mono", "-t", f"{dur:.2f}", str(p)], check=True)
        out.append(p)
    return out


def web(src: Path, name: str, fps: int = 24, crf: int = 30, poster_at: float = 3.2) -> None:
    """Kart için küçük, sessiz, hızlı açılan sürüm + kapak görseli."""
    import imageio_ffmpeg

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(src), "-vf", f"scale=360:640:flags=lanczos,fps={fps}",
                    "-an", "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", str(OUT / f"{name}.mp4")], check=True)
    subprocess.run([ff, "-y", "-loglevel", "error", "-ss", f"{poster_at:.1f}", "-i", str(OUT / f"{name}.mp4"), "-frames:v", "1",
                    "-q:v", "5", str(OUT / f"{name}.jpg")], check=True)


def main() -> None:
    for lang in ("tr", "en"):
        suffix = "" if lang == "tr" else "-en"
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            contact, msgs = CHAT[lang]
            messages = [{"me": me, "text": t} for me, t in msgs]
            times = F.join_audio(silent_clips([m["text"] for m in messages], tmp), 0.3, 0.5, 1.2, tmp / "a.wav")
            total = times[-1][1] + 1.2
            F.render(F.chat_ass(messages, times, contact, total), tmp / "a.wav", total, "pastel", tmp / "chat.mp4")
            web(tmp / "chat.mp4", f"sohbet{suffix}", poster_at=total - 1.5)  # kapakta dolu sohbet
            community, sents = STORY[lang]
            times = F.join_audio(silent_clips(sents, tmp), 0.2, 0.3, 1.0, tmp / "b.wav")
            total = times[-1][1] + 1.0
            F.render(F.story_ass(sents[0], community, sents, times, total, lang), tmp / "b.wav", total, "piksel",
                     tmp / "story.mp4")
            web(tmp / "story.mp4", f"hikaye{suffix}", fps=16, crf=32)  # piksel desen saniyede 8 kare değişir
            w = F.words(lang)
            rounds = [{"a": a, "b": b} for a, b in SECIM[lang]]
            texts = [w["wyr_say"], *(f"{r['a']}, {w['or_word']} {r['b']}?" for r in rounds), w["pick"]]
            gaps = [0.4] + [F.THINK] * len(rounds) + [0.0]
            times = F.join_audio(silent_clips(texts, tmp), gaps, 0.4, 1.2, tmp / "c.wav")
            total = times[-1][1] + 1.2
            F.render(F.wyr_ass(rounds, times, total, lang), tmp / "c.wav", total, "pastel", tmp / "wyr.mp4")
            web(tmp / "wyr.mp4", f"secim{suffix}", poster_at=times[1][1] + 1.6)  # kapakta geri sayım
            topic, qs = QUIZ[lang]
            questions = [{"q": q, "options": o, "answer": a} for q, o, a in qs]
            texts, gaps = [f"{w['quiz_say']} {topic}"], [0.4]
            for q in questions:
                texts += [q["q"] + " " + " ".join(q["options"]), f"{w['answer']}: {q['options'][q['answer']]}"]
                gaps += [F.THINK, 0.9]
            texts.append(w["score"])
            gaps.append(0.0)
            times = F.join_audio(silent_clips(texts, tmp), gaps, 0.4, 1.2, tmp / "d.wav")
            total = times[-1][1] + 1.2
            F.render(F.quiz_ass(topic, questions, times, total, lang), tmp / "d.wav", total, "piksel", tmp / "quiz.mp4")
            web(tmp / "quiz.mp4", f"quiz{suffix}", fps=16, crf=32, poster_at=times[2][0] + 0.8)  # kapakta doğru cevap
    for p in sorted(OUT.iterdir()):
        print(f"{p.name:20s} {p.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
