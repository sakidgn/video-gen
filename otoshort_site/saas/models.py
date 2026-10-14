from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), default="")
    pw_hash: Mapped[str] = mapped_column(String(255))  # Google ile kayıtta boş (şifreyle giriş yok)
    google_sub: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    notify: Mapped[bool] = mapped_column(Boolean, default=True)  # bildirim e-postaları
    credits: Mapped[int] = mapped_column(Integer, default=0)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CreditTx(Base):
    """Kredi hareketleri: + yükleme/iade, - harcama. Bakiye users.credits'te, burası döküm."""
    __tablename__ = "credit_tx"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(200))
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TopUp(Base):
    """Havale bildirimi: admin onaylayınca kredi yüklenir."""
    __tablename__ = "topups"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount_tl: Mapped[int] = mapped_column(Integer)
    credits: Mapped[int] = mapped_column(Integer)
    sender_name: Mapped[str] = mapped_column(String(120))
    note: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(20), default="bekliyor")  # bekliyor / onaylandi / reddedildi
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user: Mapped[User] = relationship()


class Channel(Base):
    """Otomatik kanal: kullanıcının ayarladığı saatlerde kendiliğinden video üretilir."""
    __tablename__ = "channels"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    characters: Mapped[str] = mapped_column(Text, default="")
    topic: Mapped[str] = mapped_column(Text, default="")
    style: Mapped[str] = mapped_column(String(30), default="cartoon")
    language: Mapped[str] = mapped_column(String(5), default="tr")
    quality: Mapped[str] = mapped_column(String(20), default="fast")
    times: Mapped[str] = mapped_column(String(200), default="12:00")  # "09:45 18:30"
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notice: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    def time_list(self) -> list[str]:
        return [t for t in self.times.replace(",", " ").split() if t]


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("channel_id", "slot", name="uq_channel_slot"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    channel_id: Mapped[int | None] = mapped_column(ForeignKey("channels.id"), nullable=True, index=True)
    slot: Mapped[str | None] = mapped_column(String(40), nullable=True)  # kanal işi için "2026-10-13 09:45"
    idea: Mapped[str] = mapped_column(Text, default="")
    characters: Mapped[str] = mapped_column(Text, default="")
    style: Mapped[str] = mapped_column(String(30), default="cartoon")
    language: Mapped[str] = mapped_column(String(5), default="tr")
    quality: Mapped[str] = mapped_column(String(20), default="fast")
    cost: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="sirada", index=True)  # sirada/uretiliyor/hazir/hata
    prompt: Mapped[str] = mapped_column(Text, default="")
    title: Mapped[str] = mapped_column(String(200), default="")
    caption: Mapped[str] = mapped_column(Text, default="")
    hashtags: Mapped[str] = mapped_column(String(400), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    video_file: Mapped[str] = mapped_column(String(300), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    channel: Mapped[Channel | None] = relationship()
