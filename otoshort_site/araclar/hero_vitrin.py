"""Ana sayfa girişindeki telefonun içinde oynayan vitrin videosu: sitenin kendi format motoruyla (parkur arka planı)
mesajlaşma, quiz, "Hangisini seçerdin?" ve bilmece örneklerinden en canlı anları keser, yumuşak geçişle birleştirir.
Ses yok (telefon sessiz oynar). Çıktı: saas/static/hero/vitrin[-en].mp4 + .jpg (720x1280, keskin)

    python araclar/hero_vitrin.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "araclar"))

from format_ornekleri import CHAT, QUIZ, SECIM, SilentAI, silent_clips  # noqa: E402

from saas import formatlar as F  # noqa: E402

OUT = ROOT / "saas" / "static" / "hero"
CUT = 5.2  # her formattan alınan süre (sn)
FADE = 0.45


def clips(lang: str, tmp: Path) -> list[tuple[Path, float]]:
    """(video, başlangıç sn) listesi: her formatın en hareketli anı."""
    out = []
    contact, msgs = CHAT[lang]
    messages = [{"me": me, "text": t} for me, t in msgs]
    times = F.join_audio(silent_clips([m["text"] for m in messages], tmp), 0.3, 0.5, 1.2, tmp / "a.wav")
    total = times[-1][1] + 1.2
    F.render(F.chat_ass(messages, times, contact, total), tmp / "a.wav", total, "parkur", tmp / "chat.mp4")
    out.append((tmp / "chat.mp4", max(0.0, times[4][0] - 0.3)))
    w = F.words(lang)
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
    F.render(F.quiz_ass(topic, questions, times, total, lang), tmp / "d.wav", total, "parkur", tmp / "quiz.mp4")
    out.append((tmp / "quiz.mp4", max(0.0, times[2][0] - CUT + 1.4)))  # soru + geri sayım + doğru cevap
    rounds = [{"a": a, "b": b} for a, b in SECIM[lang]]
    texts = [w["wyr_say"], *(f"{r['a']}, {w['or_word']} {r['b']}?" for r in rounds), w["pick"]]
    gaps = [0.4] + [F.THINK] * len(rounds) + [0.0]
    times = F.join_audio(silent_clips(texts, tmp), gaps, 0.4, 1.2, tmp / "c.wav")
    total = times[-1][1] + 1.2
    F.render(F.wyr_ass(rounds, times, total, lang), tmp / "c.wav", total, "parkur", tmp / "wyr.mp4")
    out.append((tmp / "wyr.mp4", times[1][0]))
    if lang == "tr":
        from saas import worker

        worker.make_format(SilentAI(), "bilmece", "", "tr", 20, "parkur", [], tmp / "bil.mp4")
        out.append((tmp / "bil.mp4", 4.0))
    return out


def build(lang: str) -> None:
    import imageio_ffmpeg

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    suffix = "" if lang == "tr" else "-en"
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        parts = clips(lang, tmp)
        args, chain = [], []
        for i, (p, start) in enumerate(parts):
            args += ["-ss", f"{start:.2f}", "-t", f"{CUT:.2f}", "-i", str(p)]
            chain.append(f"[{i}:v]fps=30,scale=720:1280,setsar=1,format=yuv420p[v{i}]")
        last, off = "v0", CUT - FADE
        for i in range(1, len(parts)):
            chain.append(f"[{last}][v{i}]xfade=transition=fade:duration={FADE}:offset={off:.2f}[x{i}]")
            last, off = f"x{i}", off + CUT - FADE
        OUT.mkdir(parents=True, exist_ok=True)
        dst = OUT / f"vitrin{suffix}.mp4"
        subprocess.run([ff, "-y", "-loglevel", "error", *args, "-filter_complex", ";".join(chain), "-map", f"[{last}]",
                        "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "26", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", str(dst)], check=True)
        subprocess.run([ff, "-y", "-loglevel", "error", "-ss", "3.6", "-i", str(dst), "-frames:v", "1", "-q:v", "4",
                        str(OUT / f"vitrin{suffix}.jpg")], check=True)
        print(dst.name, dst.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    for lang in ("tr", "en"):
        build(lang)
