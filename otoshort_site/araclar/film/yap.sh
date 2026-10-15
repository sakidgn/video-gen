#!/bin/bash
# Tanıtım filmini baştan üretir: 16 sn, 30 fps; yatay (1920x1080) + dikey (720x1280), posterler ve paylaşım görseli (og.png).
# Gerekenler: python + playwright, ffmpeg. İsteğe bağlı 1. argüman: chromium yolu.
set -e
cd "$(dirname "$0")"; EXE=$1; ST=../../saas/static
rm -rf kareler
for m in 0 1; do
  for k in 0 1 2 3; do python3 kare.py $m $((k*120)) $(((k+1)*120)) $EXE & done; wait
done
mkdir -p $ST/hero
ffmpeg -y -loglevel error -framerate 30 -i kareler/0/%04d.jpg -vf format=yuv420p -c:v libx264 -preset slow -crf 24 -movflags +faststart -an $ST/hero/hero.mp4
ffmpeg -y -loglevel error -framerate 30 -i kareler/1/%04d.jpg -vf format=yuv420p,scale=720:1280:flags=lanczos -c:v libx264 -preset slow -crf 24 -movflags +faststart -an $ST/hero/hero-m.mp4
ffmpeg -y -loglevel error -i kareler/0/0045.jpg -vf scale=-2:720 -q:v 4 $ST/hero/hero.jpg
ffmpeg -y -loglevel error -i kareler/1/0045.jpg -vf scale=720:-2 -q:v 4 $ST/hero/hero-m.jpg
python3 - "$EXE" <<'PY'
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
exe = sys.argv[1] or None; here = Path.cwd()
with sync_playwright() as p:
    br = p.chromium.launch(executable_path=exe, args=["--no-sandbox", "--allow-file-access-from-files"]) if exe else p.chromium.launch(args=["--allow-file-access-from-files"])
    pg = br.new_page(viewport={"width": 1200, "height": 630}); pg.goto((here / "og.html").as_uri()); pg.wait_for_timeout(800)
    pg.screenshot(path=str(here / "../../saas/static/og.png")); br.close()
PY
ls -la $ST/hero $ST/og.png
echo BITTI
