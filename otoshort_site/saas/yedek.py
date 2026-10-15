"""Veritabanı yedeği: SQLite dosyasının tutarlı bir kopyasını saas_veri/yedekler'e alır, en yeni N tanesini tutar.
Elle: python -m saas.yedek   (işçi açıkken günde bir kez kendiliğinden de alınır)"""
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from . import config

log = logging.getLogger("saas.yedek")
KEEP = 14


def backup_dir() -> Path:
    return config.DATA_DIR / "yedekler"


def _db_path(url: str | None = None) -> Path | None:
    url = url or config.DATABASE_URL
    return Path(url.removeprefix("sqlite:///")) if url.startswith("sqlite:///") else None


def backup(url: str | None = None, keep: int = KEEP, stamp: str | None = None) -> Path | None:
    """Yedeği alır ve dosya yolunu döndürür (SQLite değilse ya da veritabanı yoksa None)."""
    src = _db_path(url)
    if not src or not src.exists():
        return None
    out_dir = backup_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"site-{stamp or datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    with sqlite3.connect(src) as a, sqlite3.connect(out) as b:
        a.backup(b)  # çalışan veritabanından güvenli kopya (WAL dahil)
    for old in sorted(out_dir.glob("site-*.db"))[:-keep]:
        old.unlink()
    log.info("Veritabanı yedeklendi: %s", out.name)
    return out


def backed_up_today() -> bool:
    return any(backup_dir().glob(f"site-{datetime.now().strftime('%Y%m%d')}-*.db"))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(backup() or "Yedeklenecek SQLite veritabanı bulunamadı.")
