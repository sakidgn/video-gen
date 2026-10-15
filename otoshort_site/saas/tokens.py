"""Süreli, imzalı bağlantı jetonları (e-posta doğrulama, şifre sıfırlama)."""
import hashlib

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from . import config

VERIFY_MAX_AGE = 3 * 24 * 3600
RESET_MAX_AGE = 3600


def _s(salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.SECRET_KEY, salt=salt)


def _pw_fingerprint(pw_hash: str) -> str:
    return hashlib.sha256((pw_hash or "-").encode()).hexdigest()[:16]


def make_verify(uid: int, email: str) -> str:
    return _s("eposta-dogrula").dumps({"u": uid, "e": email})


def read_verify(token: str) -> dict | None:
    try:
        return _s("eposta-dogrula").loads(token, max_age=VERIFY_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def make_reset(uid: int, pw_hash: str) -> str:
    """Şifre değişince (ya da bir kez kullanılınca) geçersiz olan sıfırlama jetonu."""
    return _s("sifre-yenile").dumps({"u": uid, "h": _pw_fingerprint(pw_hash)})


def read_reset(token: str, pw_hash_now) -> int | None:
    try:
        data = _s("sifre-yenile").loads(token, max_age=RESET_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    if pw_hash_now is None or data.get("h") != _pw_fingerprint(pw_hash_now):
        return None
    return data.get("u")


def reset_uid(token: str) -> int | None:
    """Jetondaki kullanıcı (imza/süre kontrolüyle, parmak izi kontrolü ayrıca yapılır)."""
    try:
        return _s("sifre-yenile").loads(token, max_age=RESET_MAX_AGE).get("u")
    except (BadSignature, SignatureExpired):
        return None


MEDIA_MAX_AGE = 3 * 3600


def make_media(job_id: int) -> str:
    """Paylaşım platformunun videoyu indirebilmesi için süreli imzalı jeton."""
    return _s("medya").dumps({"j": job_id})


def read_media(token: str) -> int | None:
    try:
        return int(_s("medya").loads(token, max_age=MEDIA_MAX_AGE)["j"])
    except (BadSignature, SignatureExpired, KeyError, TypeError, ValueError):
        return None
