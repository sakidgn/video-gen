"""Erken erişim listesi: katılım ve kişiye özel davet kodu. Hediyeler bedava değil, ilk yüklemeye bağlı
(growth.first_topup_rewards): listedekine yüzde fazla kredi, listeye davet edene arkadaşının yüklemesinden pay."""
from sqlalchemy import func, select, update

from . import growth
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
    joined = s.scalar(select(func.count(User.id)).where(User.email.in_([i.email for i in invited]),
                                                       User.email_verified.is_(True))) if invited else 0
    return {"invited": len(invited), "joined": joined or 0,
            "position": s.scalar(select(func.count(Waitlist.id)).where(Waitlist.id <= w.id))}
