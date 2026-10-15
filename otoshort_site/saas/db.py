from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import config


class Base(DeclarativeBase):
    pass


engine = None
SessionLocal = sessionmaker(expire_on_commit=False)


def init(url: str | None = None) -> None:
    """Veritabanına bağlanır ve tabloları oluşturur."""
    global engine
    url = url or config.DATABASE_URL
    if url.startswith("sqlite:///"):
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    kwargs = {"connect_args": {"check_same_thread": False, "timeout": 30}} if url.startswith("sqlite") else {}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _pragmas(conn, _):
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
    SessionLocal.configure(bind=engine)
    from . import models  # noqa: F401

    Base.metadata.create_all(engine)
    _migrate()


# sonradan eklenen sütunlar: (tablo, sütun, tanım)
NEW_COLUMNS = [
    ("jobs", "ref_image", "VARCHAR(120) NOT NULL DEFAULT ''"),
    ("channels", "ref_image", "VARCHAR(120) NOT NULL DEFAULT ''"),
    ("jobs", "subtitles", "BOOLEAN NOT NULL DEFAULT 0"),
    ("channels", "subtitles", "BOOLEAN NOT NULL DEFAULT 0"),
    ("jobs", "raw_file", "VARCHAR(300) NOT NULL DEFAULT ''"),
]


def _migrate() -> None:
    """Eski veritabanlarına sonradan eklenen sütunları ekler (veri kaybı olmadan)."""
    from sqlalchemy import inspect, text

    tables = set(inspect(engine).get_table_names())
    cols = {c["name"] for c in inspect(engine).get_columns("users")}
    with engine.begin() as conn:
        if "google_sub" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN google_sub VARCHAR(64)"))
        if "email_verified" not in cols:  # önceden açılmış hesaplar doğrulanmış sayılır
            conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT 1"))
        if "notify" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN notify BOOLEAN NOT NULL DEFAULT 1"))
        if "ref_code" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN ref_code VARCHAR(12)"))
        if "referred_by" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN referred_by INTEGER"))
        if "ref_rewarded" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN ref_rewarded BOOLEAN NOT NULL DEFAULT 0"))
        for table, col, ddl in NEW_COLUMNS:
            if table in tables and col not in {c["name"] for c in inspect(engine).get_columns(table)}:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub ON users (google_sub)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_ref_code ON users (ref_code)"))


@contextmanager
def session():
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
