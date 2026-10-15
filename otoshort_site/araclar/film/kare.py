"""Tanıtım filminin bir kare aralığını JPEG olarak çizer (Playwright + Chromium).
kullanım: python kare.py <0=yatay|1=dikey> <ilk> <son>"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
m, a, b = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
FPS = 30
out = HERE / "kareler" / m
out.mkdir(parents=True, exist_ok=True)
args = ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--allow-file-access-from-files"]
with sync_playwright() as p:
    exe = sys.argv[4] if len(sys.argv) > 4 else None
    br = p.chromium.launch(executable_path=exe, args=args) if exe else p.chromium.launch(args=args)
    vp = {"width": 1280, "height": 720} if m == "0" else {"width": 540, "height": 960}
    pg = br.new_page(viewport=vp, device_scale_factor=1.5 if m == "0" else 2)
    pg.goto((HERE / "film.html").as_uri() + f"?m={m}")
    pg.wait_for_timeout(1500)
    for i in range(a, b):
        pg.evaluate(f"render({i / FPS})")
        pg.screenshot(path=str(out / f"{i:04d}.jpg"), quality=94)
    br.close()
