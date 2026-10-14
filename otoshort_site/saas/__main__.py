"""Siteyi başlatır: python -m saas  (adres: http://localhost:8000)"""
import logging
import os

import uvicorn

try:
    from dotenv import load_dotenv

    load_dotenv()  # .env dosyasındaki ayarlar (config import edilmeden önce)
except ImportError:
    pass

from .app import create_app  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "8000")),
                proxy_headers=True, forwarded_allow_ips="*")
