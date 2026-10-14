import hashlib
import hmac
import secrets
import time

ITERATIONS = {"n": 2**14, "r": 8, "p": 1}


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, dklen=32, **ITERATIONS)
    return f"scrypt${salt.hex()}${dk.hex()}"


def check_password(pw: str, stored: str) -> bool:
    try:
        _, salt, dk = stored.split("$")
    except ValueError:
        return False
    test = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), dklen=32, **ITERATIONS)
    return hmac.compare_digest(test.hex(), dk)


def csrf_token(session: dict) -> str:
    tok = session.get("csrf")
    if not tok:
        tok = session["csrf"] = secrets.token_urlsafe(24)
    return tok


def csrf_ok(session: dict, sent: str | None) -> bool:
    tok = session.get("csrf")
    return bool(tok and sent and hmac.compare_digest(tok, sent))


class RateLimiter:
    """Basit bellek içi sınırlayıcı: aynı anahtar için `window` saniyede en fazla `limit` deneme."""

    def __init__(self, limit: int, window: int):
        self.limit, self.window, self.hits = limit, window, {}

    def allow(self, key: str) -> bool:
        t = time.time()
        hits = [h for h in self.hits.get(key, []) if t - h < self.window]
        if len(hits) >= self.limit:
            self.hits[key] = hits
            return False
        hits.append(t)
        self.hits[key] = hits
        return True
