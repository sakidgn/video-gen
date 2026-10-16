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
    ref_code: Mapped[str | None] = mapped_column(String(12), nullable=True)  # davet kodu (ilk gerektiğinde üretilir)
    referred_by: Mapped[int | None] = mapped_column(Integer, nullable=True)  # davet eden kullanıcının id'si
    ref_rewarded: Mapped[bool] = mapped_column(Boolean, default=False)  # davet ödülü verildi mi
    loyalty_given: Mapped[int] = mapped_column(Integer, default=0)  # verilen sadakat hediyesi sayısı
    plan: Mapped[str] = mapped_column(String(20), default="")  # abonelik: baslangic / pro / studyo
    plan_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    plan_reminded: Mapped[bool] = mapped_column(Boolean, default=False)  # bitişe az kala hatırlatıldı
    lang: Mapped[str] = mapped_column(String(5), default="tr")  # site ve e-posta dili
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)  # yönetici askıya aldı: giriş yapamaz
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PromoCode(Base):
    """Promosyon kodu: yönetici oluşturur, her kullanıcı bir kez kullanır."""
    __tablename__ = "promo_codes"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    credits: Mapped[int] = mapped_column(Integer)
    max_uses: Mapped[int] = mapped_column(Integer, default=0)  # 0 = sınırsız
    uses: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PromoUse(Base):
    __tablename__ = "promo_uses"
    __table_args__ = (UniqueConstraint("code_id", "user_id", name="uq_promo_user"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    code_id: Mapped[int] = mapped_column(ForeignKey("promo_codes.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
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
    plan: Mapped[str] = mapped_column(String(20), default="")  # abonelik ödemesiyse planın anahtarı
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
    ref_image: Mapped[str] = mapped_column(String(120), default="")  # referans karakter görseli ("uid/ad.png")
    subtitles: Mapped[bool] = mapped_column(Boolean, default=False)  # videolara altyazı basılsın mı
    subtitle_style: Mapped[str] = mapped_column(String(10), default="viral")  # "viral" kelime kelime, "" klasik
    seconds: Mapped[int] = mapped_column(Integer, default=8)  # her videonun süresi
    format: Mapped[str] = mapped_column(String(10), default="")  # "" yapay zekâ videosu, "sohbet", "hikaye"
    background: Mapped[str] = mapped_column(String(40), default="")  # viral formatların arka planı
    publish_to: Mapped[str] = mapped_column(String(60), default="")  # otomatik paylaşım: "youtube tiktok instagram"
    cast_ids: Mapped[str] = mapped_column(String(60), default="")  # kayıtlı karakterler: "3 7"
    approval: Mapped[bool] = mapped_column(Boolean, default=False)  # onaylı paylaşım: kullanıcı onaylayınca yüklenir
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    def time_list(self) -> list[str]:
        return [t for t in self.times.replace(",", " ").split() if t]


class Character(Base):
    """Kayıtlı karakter / maskot: görünüş ve ses bir kez yazılır, seçilen her videoda aynı karakter oynar."""
    __tablename__ = "characters"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    look: Mapped[str] = mapped_column(Text, default="")  # görünüş ve kişilik
    voice: Mapped[str] = mapped_column(String(300), default="")  # ses, şive, konuşma tarzı
    ref_image: Mapped[str] = mapped_column(String(120), default="")  # "uid/ad.png"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


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
    ref_image: Mapped[str] = mapped_column(String(120), default="")
    subtitles: Mapped[bool] = mapped_column(Boolean, default=False)
    subtitle_style: Mapped[str] = mapped_column(String(10), default="viral")
    seconds: Mapped[int] = mapped_column(Integer, default=8)
    format: Mapped[str] = mapped_column(String(10), default="")
    background: Mapped[str] = mapped_column(String(40), default="")
    raw_file: Mapped[str] = mapped_column(String(300), default="")  # altyazısız orijinal
    public: Mapped[bool] = mapped_column(Boolean, default=False)  # sahibi Keşfet'te paylaşmayı seçti
    featured: Mapped[bool] = mapped_column(Boolean, default=False)  # yönetici öne çıkardı
    public_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    error_detail: Mapped[str] = mapped_column(Text, default="")  # teknik hata (yalnızca yönetici görür)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    channel: Mapped[Channel | None] = relationship()


class SocialAccount(Base):
    """Bağlı sosyal medya hesabı (kullanıcı başına platformda bir tane). Jetonlar şifreli saklanır."""
    __tablename__ = "social_accounts"
    __table_args__ = (UniqueConstraint("user_id", "platform", name="uq_user_platform"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    platform: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120), default="")
    remote_id: Mapped[str] = mapped_column(String(120), default="")
    access_enc: Mapped[str] = mapped_column(Text, default="")
    refresh_enc: Mapped[str] = mapped_column(Text, default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Publication(Base):
    """Bir videonun bir platforma paylaşımı: bekliyor → yukleniyor → yayinda / hata."""
    __tablename__ = "publications"
    __table_args__ = (UniqueConstraint("job_id", "platform", name="uq_job_platform"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    platform: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="bekliyor", index=True)
    remote_id: Mapped[str] = mapped_column(String(120), default="")
    url: Mapped[str] = mapped_column(String(300), default="")
    error: Mapped[str] = mapped_column(String(400), default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped["Job"] = relationship()


class Waitlist(Base):
    """Erken erişim listesi: açılış öncesi e-postasını bırakanlar (kaydolunca hediye kredi alır)."""
    __tablename__ = "waitlist"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    lang: Mapped[str] = mapped_column(String(5), default="tr")
    source: Mapped[str] = mapped_column(String(30), default="")  # hangi butondan geldi (ana sayfa, video...)
    rewarded: Mapped[bool] = mapped_column(Boolean, default=False)
    code: Mapped[str | None] = mapped_column(String(12), nullable=True, unique=True)  # kişiye özel davet kodu
    ref: Mapped[str] = mapped_column(String(12), default="")  # davet edenin kodu
    pending: Mapped[int] = mapped_column(Integer, default=0)  # hesabı açılınca yüklenecek davet kredisi
    earned: Mapped[int] = mapped_column(Integer, default=0)  # davetlerden kazanılan toplam (sınır için)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)



class Feedback(Base):
    """Kullanıcı ve ziyaretçilerin fikir, istek ve sorun bildirimleri (yönetim panelinde okunur)."""
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(255), default="")  # cevap için (isteğe bağlı)
    kind: Mapped[str] = mapped_column(String(20), default="oneri")  # oneri / istek / sorun / diger
    message: Mapped[str] = mapped_column(Text)
    lang: Mapped[str] = mapped_column(String(5), default="tr")
    status: Mapped[str] = mapped_column(String(20), default="yeni", index=True)  # yeni / okundu
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SharedScript(Base):
    """Ana sayfadaki kayıtsız denemede yazılan senaryo: /s/KOD bağlantısıyla paylaşılabilir (kod tahmin edilemez)."""
    __tablename__ = "shared_scripts"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    idea: Mapped[str] = mapped_column(String(300), default="")
    lang: Mapped[str] = mapped_column(String(5), default="tr")
    data: Mapped[str] = mapped_column(Text, default="{}")  # yapay zekânın yazdığı senaryo (JSON)
    views: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
