"""Abonelikler: Başlangıç / Pro / Stüdyo. Her plan kendi yapay zekâ kademesini (ve altındakileri) açar ve
her 30 günde plan kredisini yükler. Ödeme havaleyle: kullanıcı bildirir, yönetici onaylayınca plan başlar/uzar.
Otomatik çekim yok; bitişe 3 gün kala hatırlatma e-postası gider, süre dolunca üst kademeler kapanır."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from . import config, credits
from .models import User

REMIND_BEFORE = timedelta(days=3)


class PlanRequired(Exception):
    """Bu kalite kullanıcının aboneliğinde yok."""

    def __init__(self, quality: str):
        self.quality = quality
        self.plan = config.plan_for_quality(quality)
        super().__init__(quality)


def _aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=timezone.utc) if dt and dt.tzinfo is None else dt


def active_plan(user: User, at: datetime | None = None) -> str:
    """Süresi dolmamış planın anahtarı (yoksa "")."""
    at = at or datetime.now(timezone.utc)
    until = _aware(user.plan_until)
    return user.plan if user.plan in config.PLANS and until and until > at else ""


def allowed(user: User) -> tuple:
    return config.plan_qualities(active_plan(user))


def check(s, user_id: int, quality: str) -> None:
    user = s.get(User, user_id)
    if quality not in allowed(user):
        raise PlanRequired(quality)


def activate(s, user_id: int, plan: str) -> datetime:
    """Planı başlatır ya da uzatır (aynı plan: kalan günlerin üstüne 30 gün) ve planın kredisini yükler."""
    user = s.get(User, user_id)
    now = datetime.now(timezone.utc)
    current = _aware(user.plan_until)
    start = current if user.plan == plan and current and current > now else now
    until = start + timedelta(days=config.PLAN_DAYS)
    s.execute(update(User).where(User.id == user_id).values(plan=plan, plan_until=until, plan_reminded=False))
    credits.add(s, user_id, config.PLANS[plan]["credits"], f"Abonelik: {config.PLANS[plan]['label']}")
    return until


def due_reminders(s, at: datetime | None = None) -> list[tuple[int, str, datetime]]:
    """Bitişine 3 günden az kalan ve hatırlatılmamış planlar; hatırlatıldı olarak işaretlenir."""
    at = at or datetime.now(timezone.utc)
    out = []
    for u in s.scalars(select(User).where(User.plan != "", User.plan_reminded.is_(False),
                                          User.plan_until.is_not(None))):
        until = _aware(u.plan_until)
        if at < until <= at + REMIND_BEFORE:
            if s.execute(update(User).where(User.id == u.id, User.plan_reminded.is_(False))
                         .values(plan_reminded=True)).rowcount == 1:
                out.append((u.id, u.plan, until))
    return out
