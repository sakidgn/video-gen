"""Kredi işlemleri. Bakiye atomik güncellenir: aynı anda iki iş aynı krediyi harcayamaz."""
from sqlalchemy import update

from .models import CreditTx, User


class NotEnoughCredits(Exception):
    pass


def charge(s, user_id: int, amount: int, reason: str, job_id: int | None = None) -> None:
    res = s.execute(
        update(User).where(User.id == user_id, User.credits >= amount).values(credits=User.credits - amount)
    )
    if res.rowcount != 1:
        raise NotEnoughCredits()
    s.add(CreditTx(user_id=user_id, amount=-amount, reason=reason, job_id=job_id))


def add(s, user_id: int, amount: int, reason: str, job_id: int | None = None) -> None:
    s.execute(update(User).where(User.id == user_id).values(credits=User.credits + amount))
    s.add(CreditTx(user_id=user_id, amount=amount, reason=reason, job_id=job_id))
