"""Tek kare önizleme: python on.py <m> <t> <çıktı.jpg> [chromium]"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
HERE = Path(__file__).resolve().parent
m, t, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
args = ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--allow-file-access-from-files"]
with sync_playwright() as p:
    exe = sys.argv[4] if len(sys.argv) > 4 else None
    br = p.chromium.launch(executable_path=exe, args=args) if exe else p.chromium.launch(args=args)
    vp = {"width": 1280, "height": 720} if m == "0" else {"width": 540, "height": 960}
    pg = br.new_page(viewport=vp, device_scale_factor=1.5 if m == "0" else 2)
    pg.goto((HERE / "film.html").as_uri() + f"?m={m}"); pg.wait_for_timeout(1500)
    pg.evaluate(f"render({t})"); pg.screenshot(path=out, quality=90, timeout=180_000); br.close()
