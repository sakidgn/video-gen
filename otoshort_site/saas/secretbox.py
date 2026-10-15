"""Veritabanındaki erişim anahtarlarını (sosyal hesap jetonları) şifreler.
Yalnızca standart kütüphane: HMAC-SHA256 ile türetilmiş anahtar akışı (sayaç kipi) + şifreli metin üzerinde HMAC etiketi
(şifrele-sonra-doğrula). Anahtar GIZLI_ANAHTAR'dan türetilir; anahtar değişirse eski jetonlar açılamaz (yeniden bağlanılır)."""
import base64
import hashlib
import hmac
import secrets

from . import config


class SecretError(Exception):
    pass


def _keys() -> tuple[bytes, bytes]:
    root = hashlib.sha256(b"cutless-secretbox|" + config.SECRET_KEY.encode()).digest()
    return hmac.new(root, b"enc", hashlib.sha256).digest(), hmac.new(root, b"mac", hashlib.sha256).digest()


def _stream(key: bytes, nonce: bytes, n: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < n:
        out += hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        counter += 1
    return bytes(out[:n])


def seal(text: str) -> str:
    if not text:
        return ""
    enc, mac = _keys()
    nonce = secrets.token_bytes(16)
    data = text.encode()
    ct = bytes(a ^ b for a, b in zip(data, _stream(enc, nonce, len(data))))
    tag = hmac.new(mac, nonce + ct, hashlib.sha256).digest()
    return "v1:" + base64.urlsafe_b64encode(nonce + ct + tag).decode()


def open_(sealed: str) -> str:
    if not sealed:
        return ""
    if not sealed.startswith("v1:"):
        raise SecretError("bilinmeyen biçim")
    try:
        raw = base64.urlsafe_b64decode(sealed[3:].encode())
    except ValueError as e:
        raise SecretError("bozuk jeton") from e
    if len(raw) < 48:
        raise SecretError("bozuk jeton")
    nonce, ct, tag = raw[:16], raw[16:-32], raw[-32:]
    enc, mac = _keys()
    if not hmac.compare_digest(tag, hmac.new(mac, nonce + ct, hashlib.sha256).digest()):
        raise SecretError("jeton bozulmuş ya da anahtar değişmiş")
    return bytes(a ^ b for a, b in zip(ct, _stream(enc, nonce, len(ct)))).decode()
