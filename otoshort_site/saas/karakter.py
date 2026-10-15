"""Karakter / maskot kütüphanesi: kullanıcı karakterinin görünüşünü ve sesini bir kez kaydeder.
Video ya da kanalda seçilince yapay zekâya hep aynı tarif (ve varsa aynı referans görsel) gider; karakter tutarlı kalır.
Kanallar karakteri kimliğiyle tutar: karakter düzenlenirse kanalın sonraki videoları da yeni hâlini kullanır."""
from sqlalchemy import select

from .models import Character

MAX_PER_USER = 20
MAX_PER_VIDEO = 3
MAX_TEXT = 2000


def parse_ids(raw) -> list[int]:
    """Formdan ("3", "7") ya da kanaldan ("3 7") gelen kimlikleri sırasıyla, tekrarsız döndürür."""
    items = raw.split() if isinstance(raw, str) else [str(x) for x in (raw or [])]
    out: list[int] = []
    for x in items:
        if x.strip().isdigit() and int(x) not in out:
            out.append(int(x))
    return out[:MAX_PER_VIDEO]


def owned(s, user_id: int, ids) -> list[Character]:
    """Kullanıcının kendi karakterleri (başkasının kimliği yazılsa da gelmez), seçim sırasıyla."""
    ids = parse_ids(ids)
    if not ids:
        return []
    found = {c.id: c for c in s.scalars(select(Character).where(Character.user_id == user_id, Character.id.in_(ids)))}
    return [found[i] for i in ids if i in found]


def ids_text(chars: list[Character]) -> str:
    return " ".join(str(c.id) for c in chars)


def describe(c: Character) -> str:
    text = f"{c.name} (recurring character: keep exactly the same look and voice in every video)"
    if c.look.strip():
        text += f": {c.look.strip()}"
    if c.voice.strip():
        text += f" Voice: {c.voice.strip()}"
    return text


def cast(s, user_id: int, ids, extra: str = "", ref_image: str = "") -> tuple[str, str]:
    """Seçili karakterlerin tarifi + kullanıcının ek yazdığı karakterler; referans görsel yoksa ilk karakterinki."""
    chars = owned(s, user_id, ids)
    text = "\n".join([*(describe(c) for c in chars), *([extra.strip()] if extra.strip() else [])])
    ref = ref_image or next((c.ref_image for c in chars if c.ref_image), "")
    return text[:MAX_TEXT], ref


def for_user(s, user_id: int) -> list[Character]:
    return list(s.scalars(select(Character).where(Character.user_id == user_id).order_by(Character.id)))
