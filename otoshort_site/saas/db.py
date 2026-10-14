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


def _migrate() -> None:
    """Eski veritabanlarına sonradan eklenen sütunları ekler (veri kaybı olmadan)."""
    from sqlalchemy import inspect, text

    cols = {c["name"] for c in inspect(engine).get_columns("users")}
    with engine.begin() as conn:
        if "google_sub" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN google_sub VARCHAR(64)"))
        if "email_verified" not in cols:  # önceden açılmış hesaplar doğrulanmış sayılır
            conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT 1"))
        if "notify" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN notify BOOLEAN NOT NULL DEFAULT 1"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub ON users (google_sub)"))


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
