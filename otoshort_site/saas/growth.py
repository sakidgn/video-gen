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


def reward_referral(s, user_id: int) -> int | None:
    """Davetle gelen kullanıcının ilk onaylı havalesinde ödülleri bir kez verir; ödül alan davet edenin id'si."""
    res = s.execute(update(User).where(User.id == user_id, User.referred_by.is_not(None),
                                       User.ref_rewarded.is_(False)).values(ref_rewarded=True))
    if res.rowcount != 1:
        return None
    user = s.get(User, user_id)
    if config.REFERRAL_BONUS:
        credits.add(s, user.referred_by, config.REFERRAL_BONUS, "Davet ödülü: arkadaşın ilk yüklemesini yaptı")
    if config.REFERRAL_FRIEND_BONUS:
        credits.add(s, user.id, config.REFERRAL_FRIEND_BONUS, "Davetle gelen hediye")
    return user.referred_by


def referral_stats(s, user_id: int) -> dict:
    invited = s.scalar(select(func.count(User.id)).where(User.referred_by == user_id)) or 0
    rewarded = s.scalar(select(func.count(User.id)).where(User.referred_by == user_id, User.ref_rewarded.is_(True))) or 0
    return {"invited": invited, "rewarded": rewarded, "earned": rewarded * config.REFERRAL_BONUS}


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
