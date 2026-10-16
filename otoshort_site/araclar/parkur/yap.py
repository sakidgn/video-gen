"""Blok parkur arka plan videosunu üretir: parkur.html'in 10 sn'lik döngüsünü kare kare çeker, mp4 yapar.
Çıktı: saas/static/arka_planlar/parkur.mp4 (+ seçici için küçük kapak parkur.jpg)

    python araclar/parkur/yap.py [chromium yolu]
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE.parent.parent / "saas" / "static" / "arka_planlar"
FPS, SECONDS = 24, 10

with tempfile.TemporaryDirectory() as d, sync_playwright() as p:
    exe = sys.argv[1] if len(sys.argv) > 1 else None
    args = ["--no-sandbox", "--allow-file-access-from-files"]
    br = p.chromium.launch(executable_path=exe, args=args) if exe else p.chromium.launch(args=args)
    pg = br.new_page(viewport={"width": 360, "height": 640})
    pg.goto((HERE / "parkur.html").as_uri())
    for i in range(FPS * SECONDS):
        pg.evaluate(f"render({i / FPS})")
        pg.screenshot(path=f"{d}/{i:04d}.png")
    br.close()
    OUT.mkdir(parents=True, exist_ok=True)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ff, "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", f"{d}/%04d.png", "-c:v", "libx264",
                    "-preset", "slow", "-crf", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    str(OUT / "parkur.mp4")], check=True)
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", f"{d}/0030.png", "-vf", "scale=180:-2", "-q:v", "5",
                    str(OUT / "parkur.jpg")], check=True)
print(f"{(OUT / 'parkur.mp4').stat().st_size // 1024} KB")
