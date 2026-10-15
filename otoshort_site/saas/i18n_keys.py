"""Çevrilmesi gereken Türkçe metinleri toplar (testler ve sözlük bakımı için): şablonlardaki _()/_h() çağrıları,
koddaki flash/t/notify metinleri ve kullanıcıya görünen sabitler. Çalıştır: python -m saas.i18n_keys (eksikleri yazar)."""
import ast
import re
from pathlib import Path

from . import config

ROOT = Path(__file__).resolve().parent
# Yönetim paneli yalnızca site sahibine görünür; Türkçe kalır
SKIP_TEMPLATES = {"admin.html"}
_TPL = re.compile(r"""(?<![\w.])_h?\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")""")
_PY_FUNCS = {"flash": 1, "t": 0, "th": 0, "notify": (1, 2, 3, 4), "MediaError": 0, "PromoError": 0, "PublishError": 0,
             "fail_job": 1}
_PY_FILES = ["app.py", "worker.py", "media.py", "growth.py", "social.py", "publisher.py", "mailer.py"]


def template_keys() -> set[str]:
    keys = set()
    for f in sorted((ROOT / "templates").glob("*.html")):
        if f.name in SKIP_TEMPLATES:
            continue
        for a, b in _TPL.findall(f.read_text(encoding="utf-8")):
            keys.add(a or b)
    return keys


def _strings(node) -> list[str]:
    """Düz metin sabitleri (f-string parçaları hariç: onlar çevrilmez)."""
    if isinstance(node, ast.JoinedStr):
        return []
    if isinstance(node, ast.Constant):
        return [node.value] if isinstance(node.value, str) else []
    return [s for child in ast.iter_child_nodes(node) for s in _strings(child)]


def code_keys() -> set[str]:
    keys = set()
    for name in _PY_FILES:
        tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if fn not in _PY_FUNCS:
                continue
            pos = _PY_FUNCS[fn]
            for i in (pos if isinstance(pos, tuple) else (pos,)):
                if i < len(node.args):
                    keys.update(_strings(node.args[i]))
            if fn == "flash":  # bağlantı etiketi (4. argüman) de görünür
                if len(node.args) > 4:
                    keys.update(_strings(node.args[4]))
    return {k for k in keys if k and not k.startswith(("/", "http")) and k not in ("ok", "err", "warn", "demo")}


def constant_keys() -> set[str]:
    from . import social
    from .app import FAQS, STATUS_LABELS

    keys = set(STATUS_LABELS.values()) | set(config.STYLE_LABELS.values())
    for q in config.QUALITIES.values():
        keys |= {q["label"], q["desc"]}
    for p in social.PLATFORMS.values():
        keys |= {p["label"], p["note"]}
    for q, a in FAQS:
        keys |= {q, a}
    return keys


# Değişken üzerinden gösterilen ya da veritabanına yazılan sabit metinler
EXTRA = {
    "Geçerli bir e-posta yaz.", "Şifre en az 8 karakter olmalı.",
    "Kullanım şartlarını, KVKK metnini ve açık rızayı onaylaman gerekiyor.",
    "Oturum süresi doldu, sayfayı yenileyip tekrar dene.",
    "Video güvenlik filtresine takıldı. Fikri biraz değiştirip tekrar dene. Kredin iade edildi.",
    "Video üretilemedi, kredin iade edildi. Biraz sonra tekrar dene.",
    "Hoş geldin hediyesi", "Davet ödülü: arkadaşın ilk yüklemesini yaptı", "Davetle gelen hediye", "Yönetici düzeltmesi",
}
IGNORE = {"label", "onayla"}


def all_keys() -> set[str]:
    return (template_keys() | code_keys() | constant_keys() | EXTRA) - IGNORE


def needs_translation(key: str) -> bool:
    """Etiket ve yer tutucular çıkınca geriye yazı kalıyorsa çevrilmeli (ör. '<span class="mono">{x}</span>' hayır)."""
    return bool(re.search(r"[^\W\d_]", re.sub(r"<[^>]+>|\{\w+\}", "", key)))


def missing() -> list[str]:
    from .i18n_en import EN

    return sorted(k for k in all_keys() if k not in EN and needs_translation(k))


if __name__ == "__main__":
    for k in missing():
        print(repr(k))
