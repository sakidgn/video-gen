"""Erken erişim listesini dışa/içe aktarır (vitrinde toplananları gerçek siteye taşımak için).

    python -m saas.erken_erisim disari liste.csv --vitrin   # Canliya_Al ile toplananları dosyaya yaz
    python -m saas.erken_erisim iceri liste.csv             # gerçek sitenin veritabanına ekle (tekrarlar atlanır)"""
import argparse
import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("islem", choices=["disari", "iceri"])
    ap.add_argument("dosya")
    ap.add_argument("--vitrin", action="store_true", help="Canliya_Al'ın veritabanı (saas_veri_vitrin)")
    args = ap.parse_args(argv)
    if args.vitrin:
        os.environ["VERI_KLASORU"] = str(ROOT / "saas_veri_vitrin")
        os.environ.pop("VERITABANI", None)
    else:
        try:
            from dotenv import load_dotenv

            load_dotenv(ROOT / ".env")
        except ImportError:
            pass
    from sqlalchemy import select

    from . import db
    from .models import Waitlist

    db.init()
    path = Path(args.dosya)
    if args.islem == "disari":
        with db.session() as s, path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["email", "dil", "kaynak", "tarih"])
            rows = s.scalars(select(Waitlist).order_by(Waitlist.id)).all()
            for r in rows:
                w.writerow([r.email, r.lang, r.source, r.created_at.isoformat()])
        print(f"{len(rows)} kişi yazıldı: {path}")
    else:
        added = 0
        with db.session() as s, path.open(encoding="utf-8") as f:
            have = set(s.scalars(select(Waitlist.email)))
            for row in csv.DictReader(f):
                email = (row.get("email") or "").strip().lower()
                if email and "@" in email and email not in have:
                    s.add(Waitlist(email=email, lang=row.get("dil") or "tr", source=row.get("kaynak") or "aktarim"))
                    have.add(email)
                    added += 1
        print(f"{added} yeni kişi eklendi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
