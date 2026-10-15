"""Gerçek API denemesi: anahtarları kontrol eder, senaryo yazdırır ve seçilen kalitede gerçek video üretir.
Süreyi, dosya boyutunu ve tahmini maliyeti yazar; sonuçlar saas_veri/api_deneme/ klasörüne kaydedilir.

    python -m saas.api_dene                  # Ekonomik kalitede 1 video (önce onay sorar)
    python -m saas.api_dene --kalite hepsi   # her kaliteden 1 video
    python -m saas.api_dene --sadece-metin   # video üretmeden yalnızca anahtar + senaryo denemesi (ucuz)

Video üretimi ücretlidir: her video Google/fal.ai hesabından düşer."""
import argparse
import importlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

IDEA = "Portakal ve muz markette son indirimli ürün için kavga ediyor, kasiyer de aslında bir karpuz."


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    from . import config

    importlib.reload(config)


def explain(err: Exception) -> str:
    """Sık görülen API hatalarını anlaşılır Türkçe öneriye çevirir."""
    text = f"{type(err).__name__}: {err}"
    low = text.lower()
    if "api key not valid" in low or "api_key_invalid" in low or "401" in low or "unauthenticated" in low:
        return "Anahtar geçersiz görünüyor. .env'deki anahtarı boşluk/tırnak olmadan yeniden yapıştır."
    if "billing" in low or "failed_precondition" in low:
        return "Google hesabında faturalandırma kapalı. AI Studio → Billing'den kart ekle (Veo ücretli)."
    if "permission" in low or "403" in low:
        return "Bu anahtarın bu modele izni yok. Faturalandırmayı ve projede API'nin açık olduğunu kontrol et."
    if "not found" in low or "404" in low:
        return "Model adı bulunamadı. .env'de MODEL_LITE / MODEL_FAST / MODEL_STANDARD ile güncel model adını yaz."
    if "429" in low or "quota" in low or "resource_exhausted" in low:
        return "Kota/limit doldu. Biraz bekleyip tekrar dene ya da hesabın kotasını yükselt."
    if "timeout" in low or "zaman aşımı" in low:
        return "Yanıt çok uzun sürdü. Tekrar dene; sürerse daha hızlı bir model seç."
    if "contentblocked" in low:
        return "Güvenlik filtresine takıldı. Fikri değiştirip tekrar dene (kredi sitede otomatik iade edilir)."
    return "Beklenmeyen hata. Bu mesajı olduğu gibi gönder, birlikte bakalım."


def _video_info(path: Path) -> str:
    """"8.0 sn · 720x1280 · 3.1 MB" gibi kısa bilgi (ffmpeg yoksa sadece boyut)."""
    import re
    import subprocess

    parts = []
    try:
        import imageio_ffmpeg

        err = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True,
                             timeout=30).stderr
        if m := re.search(r"Duration: (\d+):(\d+):([\d.]+)", err):
            parts.append(f"{int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]):.1f} sn")
        if m := re.search(r"Video:.*?(\d{3,4})x(\d{3,4})", err):
            parts.append(f"{m[1]}x{m[2]}")
    except Exception:
        pass
    parts.append(f"{path.stat().st_size / 1e6:.1f} MB")
    return " · ".join(parts)


def main(argv: list[str] | None = None, generator=None) -> int:
    ap = argparse.ArgumentParser(description="Cutless gerçek API denemesi")
    ap.add_argument("--kalite", default="lite", help="lite | fast | standard | hepsi")
    ap.add_argument("--fikir", default=IDEA)
    ap.add_argument("--dil", default="tr")
    ap.add_argument("--altyazi", action="store_true", help="altyazı da ekle (ek Gemini çağrısı)")
    ap.add_argument("--sadece-metin", action="store_true", help="video üretme, sadece senaryo")
    ap.add_argument("--evet", action="store_true", help="onay sormadan üret")
    args = ap.parse_args(argv)
    if generator is None:
        _load_env()
    from . import config

    qualities = list(config.QUALITIES) if args.kalite == "hepsi" else [args.kalite]
    if any(q not in config.QUALITIES for q in qualities):
        print(f"Bilinmeyen kalite. Seçenekler: {', '.join(config.QUALITIES)}, hepsi")
        return 2

    print("== Ayarlar ==")
    gemini = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    print(f"  Gemini anahtarı : {'var' if gemini else 'YOK'}")
    print(f"  fal.ai anahtarı : {'var' if config.FAL_KEY else 'yok'}")
    for q in qualities:
        prov, model = config.provider(q)
        print(f"  {config.QUALITIES[q]['label']:<9}: {prov} · {model} · {config.QUALITIES[q]['credits']} kredi · "
              f"tahmini maliyet ~{config.VIDEO_COST_USD.get(q, 0):.2f} $")
    if generator is None and not gemini:
        print("\n.env dosyasına GEMINI_API_KEY=... satırını ekle (aistudio.google.com → Get API key).")
        return 1
    need_fal = [q for q in qualities if config.provider(q)[0] == "fal"]
    if need_fal and not config.FAL_KEY and generator is None:
        print("\nSeçili kalite fal.ai kullanıyor ama FAL_KEY yok.")
        return 1

    if generator is None:
        from .ai import RealAI

        generator = RealAI()
    out_dir = config.DATA_DIR / "api_deneme"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    results = []

    print("\n== 1) Senaryo (Gemini metin) ==")
    t0 = time.time()
    try:
        script = generator.write_script(idea=args.fikir, characters="", style="cartoon", language=args.dil, past=[])
    except Exception as e:
        print(f"  ✗ {type(e).__name__}: {str(e)[:300]}\n  → {explain(e)}")
        return 1
    print(f"  ✓ {time.time() - t0:.1f} sn")
    print(f"  Başlık   : {script.title}\n  Açıklama : {script.caption}\n  Hashtag  : {' '.join(script.hashtags)}")
    print(f"  Video komutu: {script.video_prompt[:240]}…")
    if args.sadece_metin:
        print("\nAnahtar çalışıyor. Video denemek için --sadece-metin olmadan çalıştır.")
        return 0

    total = sum(config.VIDEO_COST_USD.get(q, 0) for q in qualities)
    if not args.evet:
        ans = input(f"\n{len(qualities)} gerçek video üretilecek, tahmini maliyet ~{total:.2f} $. Devam? (e/h) ")
        if ans.strip().lower() not in ("e", "evet", "y", "yes"):
            print("Vazgeçildi.")
            return 0

    for i, q in enumerate(qualities, 2):
        label = config.QUALITIES[q]["label"]
        print(f"\n== {i}) Video: {label} ({config.provider(q)[1]}) ==  (genelde 1–5 dakika)")
        out = out_dir / f"{stamp}-{q}.mp4"
        t0 = time.time()
        try:
            generator.make_video(prompt=script.video_prompt, quality=q, out=out, refs=[])
            secs = time.time() - t0
            size = _video_info(out)
            row = {"kalite": q, "ok": True, "sure_sn": round(secs), "dosya": str(out), "boyut": size}
            if args.altyazi:
                from . import worker

                raw = worker.add_subtitles(generator, out, args.dil)
                row["altyazi"] = bool(raw)
            print(f"  ✓ {secs:.0f} sn · {size} · {out}")
        except Exception as e:
            secs = time.time() - t0
            row = {"kalite": q, "ok": False, "sure_sn": round(secs), "hata": f"{type(e).__name__}: {str(e)[:300]}",
                   "oneri": explain(e)}
            print(f"  ✗ {row['hata']}\n  → {row['oneri']}")
        row["tahmini_maliyet_usd"] = config.VIDEO_COST_USD.get(q, 0)
        row["kredi"] = config.QUALITIES[q]["credits"]
        results.append(row)

    report = out_dir / f"{stamp}-sonuc.json"
    report.write_text(json.dumps({"fikir": args.fikir, "baslik": script.title, "sonuclar": results},
                                 ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n== Özet ==")
    for r in results:
        print(f"  {config.QUALITIES[r['kalite']]['label']:<9} {'✓' if r['ok'] else '✗'}  {r['sure_sn']} sn  "
              f"~{r['tahmini_maliyet_usd']:.2f} $  → {r['kredi']} kredi")
    print(f"\nVideolar ve rapor: {out_dir}")
    print("Gerçek maliyeti Google AI Studio / fal.ai faturasından kontrol edip .env'deki MALIYET_* değerlerini güncelle.")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
