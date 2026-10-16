"""Büyüme: davet programı ve promosyon kodları."""
import secrets
from datetime import datetime, timezone

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from . import config, credits
from .models import PromoCode, PromoUse, User

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # karışan harfler (0/O, 1/I) yok


def random_code(n: int = 7) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(n))


def norm_code(code: str) -> str:
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())[:32]


# ---------- davet ----------

def ref_code_for(s, user_id: int) -> str:
    """Kullanıcının davet kodu; yoksa üretip kaydeder."""
    user = s.get(User, user_id)
    while not user.ref_code:
        code = random_code()
        if not s.scalar(select(User.id).where(User.ref_code == code)):
            user.ref_code = code
            s.flush()
    return user.ref_code


def referrer_id(s, code: str) -> int | None:
    code = norm_code(code)
    return s.scalar(select(User.id).where(User.ref_code == code)) if code else None


def attach_referrer(s, user: User, code: str | None) -> None:
    """Yeni kullanıcıyı davet edene bağlar (kendini davet edemez)."""
    rid = referrer_id(s, code or "")
    if rid and rid != user.id and not user.referred_by:
        user.referred_by = rid


def pct(amount: int, percent: int) -> int:
    return amount * percent // 100


def first_topup_rewards(s, user_id: int, topup_credits: int) -> tuple[int | None, int]:
    """İlk onaylı yüklemede (bir kez): davetle gelene / erken erişim listesindekine yüzde fazla kredi (büyüğü),
    davet edene de o yüklemenin yüzdesi kadar kredi. Hepsi ödenen paradan pay; bedava kredi yok.
    (davet edenin id'si, ona verilen kredi) döner."""
    from .models import Waitlist

    res = s.execute(update(User).where(User.id == user_id, User.ref_rewarded.is_(False)).values(ref_rewarded=True))
    if res.rowcount != 1:
        return None, 0
    user = s.get(User, user_id)
    w = s.scalar(select(Waitlist).where(Waitlist.email == user.email))
    if not user.referred_by and w and w.ref:  # erken erişim listesinde davetle gelmiş: davet edenin hesabına bağla
        inviter = s.scalar(select(Waitlist).where(Waitlist.code == w.ref))
        rid = inviter and s.scalar(select(User.id).where(User.email == inviter.email, User.email_verified.is_(True)))
        if rid and rid != user.id:
            user.referred_by = rid
    bonus, reason = 0, ""
    if user.referred_by and config.REFERRAL_FRIEND_PCT:
        bonus, reason = pct(topup_credits, config.REFERRAL_FRIEND_PCT), "Davetle gelen hediye"
    if w and config.EARLY_TOPUP_PCT and pct(topup_credits, config.EARLY_TOPUP_PCT) > bonus:
        bonus, reason = pct(topup_credits, config.EARLY_TOPUP_PCT), "Erken erişim hediyesi"
    if bonus:
        credits.add(s, user.id, bonus, reason)
    if w:
        w.rewarded = True
    ref_amount = pct(topup_credits, config.REFERRAL_PCT) if user.referred_by else 0
    if ref_amount:
        credits.add(s, user.referred_by, ref_amount, "Davet ödülü: arkadaşın ilk yüklemesini yaptı")
    return (user.referred_by, ref_amount) if ref_amount else (None, 0)


def loyalty(s, user_id: int) -> int:
    """Hazır videolara harcanan her LOYALTY_EVERY kredide 1 Ekonomik video hediye. Verilen kredi döner."""
    from .models import Job

    if not config.LOYALTY_EVERY:
        return 0
    spent = s.scalar(select(func.coalesce(func.sum(Job.cost), 0)).where(Job.user_id == user_id,
                                                                     Job.status == "hazir")) or 0
    user = s.get(User, user_id)
    due, given = spent // config.LOYALTY_EVERY, user.loyalty_given
    if due <= given:
        return 0
    # aynı anda biten iki video aynı hediyeyi iki kez vermesin
    if s.execute(update(User).where(User.id == user_id, User.loyalty_given == given)
                 .values(loyalty_given=due)).rowcount != 1:
        return 0
    amount = (due - given) * config.QUALITIES["lite"]["credits"]
    credits.add(s, user_id, amount, "Sadakat hediyesi: 1 Ekonomik video")
    return amount


def loyalty_progress(s, user_id: int) -> dict:
    from .models import Job

    every = config.LOYALTY_EVERY
    spent = s.scalar(select(func.coalesce(func.sum(Job.cost), 0)).where(Job.user_id == user_id,
                                                                     Job.status == "hazir")) or 0
    return {"every": every, "done": spent % every if every else 0, "gift": config.QUALITIES["lite"]["credits"]}


def referral_stats(s, user_id: int) -> dict:
    from .models import CreditTx

    invited = s.scalar(select(func.count(User.id)).where(User.referred_by == user_id)) or 0
    rewarded = s.scalar(select(func.count(User.id)).where(User.referred_by == user_id, User.ref_rewarded.is_(True))) or 0
    earned = s.scalar(select(func.coalesce(func.sum(CreditTx.amount), 0)).where(
        CreditTx.user_id == user_id, CreditTx.reason == "Davet ödülü: arkadaşın ilk yüklemesini yaptı")) or 0
    return {"invited": invited, "rewarded": rewarded, "earned": earned}


# ---------- promosyon kodu ----------

class PromoError(Exception):
    pass


def redeem(s, user_id: int, code: str) -> int:
    """Kodu kullanır, yüklenen krediyi döndürür. Hatada PromoError (kullanıcıya gösterilecek mesajla)."""
    code = norm_code(code)
    promo = s.scalar(select(PromoCode).where(PromoCode.code == code)) if code else None
    now = datetime.now(timezone.utc)
    if not promo or not promo.active:
        raise PromoError("Bu kod geçersiz.")
    expires = promo.expires_at
    if expires and (expires if expires.tzinfo else expires.replace(tzinfo=timezone.utc)) < now:
        raise PromoError("Bu kodun süresi dolmuş.")
    if s.scalar(select(PromoUse.id).where(PromoUse.code_id == promo.id, PromoUse.user_id == user_id)):
        raise PromoError("Bu kodu zaten kullandın.")
    # kullanım hakkı atomik düşülür: son hakkı iki kişi aynı anda alamaz
    res = s.execute(update(PromoCode).where(PromoCode.id == promo.id, or_(PromoCode.max_uses == 0,
                                                                          PromoCode.uses < PromoCode.max_uses))
                    .values(uses=PromoCode.uses + 1))
    if res.rowcount != 1:
        raise PromoError("Bu kodun kullanım hakkı dolmuş.")
    try:
        with s.begin_nested():
            s.add(PromoUse(code_id=promo.id, user_id=user_id))
    except IntegrityError:
        raise PromoError("Bu kodu zaten kullandın.") from None
    credits.add(s, user_id, promo.credits, f"Promosyon kodu: {promo.code}")
    return promo.credits
