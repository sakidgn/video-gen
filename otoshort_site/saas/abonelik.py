"""Abonelikler: Başlangıç / Pro / Stüdyo. Her plan kendi yapay zekâ kademesini (ve altındakileri) açar ve
her 30 günde plan kredisini yükler. Ödeme havaleyle: kullanıcı bildirir, yönetici onaylayınca plan başlar/uzar.
Otomatik çekim yok; bitişe 3 gün kala hatırlatma e-postası gider, süre dolunca üst kademeler kapanır.
Yıllık plan: 12 ay (10 ay ücreti); ilk ayın kredisi hemen, kalan 11 ayınki her 30 günde bir yüklenir."""
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


class VideoOff(PlanRequired):
    """Yapay zekâ videosu bu sitede kapalı (YZ_VIDEO_KAPALI=1): yalnızca viral formatlar üretilir."""

    def __init__(self):
        super().__init__("lite")


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


def split_plan(value: str) -> tuple[str, bool]:
    """Ödeme kaydındaki plan: "pro" (aylık) ya da "pro:yillik" → (plan, yıllık mı)."""
    plan, _, period = (value or "").partition(":")
    return (plan, period == "yillik") if plan in config.PLANS else ("", False)


def activate(s, user_id: int, plan: str, yearly: bool = False) -> datetime:
    """Planı başlatır ya da uzatır (aynı plan: kalan günlerin üstüne) ve ilk ayın kredisini yükler.
    Yıllıkta 12 × 30 gün eklenir, kalan 11 ayın kredisi refill() ile her ay yüklenir."""
    user = s.get(User, user_id)
    now = datetime.now(timezone.utc)
    current = _aware(user.plan_until)
    same = user.plan == plan and current and current > now
    start = current if same else now
    until = start + timedelta(days=config.PLAN_DAYS * (12 if yearly else 1))
    values = {"plan": plan, "plan_until": until, "plan_reminded": False}
    if yearly:
        values["plan_refills"] = (user.plan_refills if same else 0) + 11
        values["plan_next_refill"] = _aware(user.plan_next_refill) if same and user.plan_refills else \
            now + timedelta(days=config.PLAN_DAYS)
    elif not same:
        values["plan_refills"], values["plan_next_refill"] = 0, None
    s.execute(update(User).where(User.id == user_id).values(**values))
    credits.add(s, user_id, config.PLANS[plan]["credits"],
                f"Abonelik: {config.PLANS[plan]['label']}" + (" (yıllık)" if yearly else ""))
    return until


def refill(s, at: datetime | None = None) -> list[tuple[int, str, int]]:
    """Yıllık planlarda zamanı gelen aylık kredileri yükler; (kullanıcı, plan, kredi) listesi döner."""
    at = at or datetime.now(timezone.utc)
    out = []
    for u in s.scalars(select(User).where(User.plan_refills > 0, User.plan_next_refill.is_not(None))):
        nxt = _aware(u.plan_next_refill)
        if nxt > at or not active_plan(u, at):
            continue
        res = s.execute(update(User).where(User.id == u.id, User.plan_refills == u.plan_refills).values(
            plan_refills=u.plan_refills - 1, plan_next_refill=nxt + timedelta(days=config.PLAN_DAYS)))
        if res.rowcount == 1:
            n = config.PLANS[u.plan]["credits"]
            credits.add(s, u.id, n, f"Abonelik: {config.PLANS[u.plan]['label']} (yıllık, aylık yükleme)")
            out.append((u.id, u.plan, n))
    return out


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
