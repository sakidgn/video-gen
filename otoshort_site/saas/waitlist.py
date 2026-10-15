"""Erken erişim listesi: katılım, kişiye özel davet kodu ve kayıtta verilen hediyeler."""
from sqlalchemy import func, select, update

from . import config, credits, growth
from .models import User, Waitlist


def join(s, email: str, lang: str, source: str, ref: str = "") -> Waitlist:
    """Listeye ekler (zaten varsa mevcut kaydı döndürür). Kendini davet etmek sayılmaz."""
    w = s.scalar(select(Waitlist).where(Waitlist.email == email))
    if w:
        if not w.code:
            w.code = _new_code(s)
        return w
    inviter = s.scalar(select(Waitlist).where(Waitlist.code == ref)) if ref else None
    w = Waitlist(email=email, lang=lang, source=source[:30], code=_new_code(s),
                 ref=inviter.code if inviter and inviter.email != email else "")
    s.add(w)
    s.flush()
    return w


def _new_code(s) -> str:
    while True:
        code = growth.random_code(8)
        if not s.scalar(select(Waitlist.id).where(Waitlist.code == code)):
            return code


def stats(s, w: Waitlist) -> dict:
    invited = s.scalars(select(Waitlist).where(Waitlist.ref == w.code)).all() if w.code else []
    return {"invited": len(invited), "joined": sum(1 for i in invited if i.rewarded), "earned": w.earned,
            "pending": w.pending, "position": s.scalar(select(func.count(Waitlist.id)).where(Waitlist.id <= w.id))}


def reward_on_verify(s, user: User) -> None:
    """Hesap doğrulanınca: listedeyse erken erişim hediyesi + biriken davet kredisi; davet edene ödül."""
    w = s.scalar(select(Waitlist).where(Waitlist.email == user.email))
    if not w:
        return
    pending, ref = w.pending, w.ref  # güncellemeden önce oku (oturumdaki nesne de sıfırlanır)
    # aynı anda iki doğrulamada da tek sefer
    if s.execute(update(Waitlist).where(Waitlist.id == w.id, Waitlist.rewarded.is_(False))
                 .values(rewarded=True, pending=0)).rowcount != 1:
        return
    if config.EARLY_BONUS:
        credits.add(s, user.id, config.EARLY_BONUS, "Erken erişim hediyesi")
    if pending:
        credits.add(s, user.id, pending, "Erken erişim davet ödülü")
    inviter = s.scalar(select(Waitlist).where(Waitlist.code == ref)) if ref else None
    if not inviter or not config.EARLY_INVITE_BONUS:
        return
    amount = min(config.EARLY_INVITE_BONUS, max(0, config.EARLY_INVITE_CAP - inviter.earned))
    if amount <= 0:
        return
    inviter.earned += amount
    owner = s.scalar(select(User).where(User.email == inviter.email, User.email_verified.is_(True)))
    if owner and inviter.rewarded:  # davet edenin hesabı açık: hemen yükle
        credits.add(s, owner.id, amount, "Erken erişim davet ödülü")
    else:  # hesabını açınca yüklenecek
        inviter.pending += amount
