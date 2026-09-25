import json
import os
from datetime import date
from pathlib import Path

from .config import ROOT

STATE_PATH = ROOT / "yerel" / "kota.json"


def gemini_profiles() -> list[str]:
    return [p.strip() for p in os.environ.get("GEMINI_PROFILLER", "").split(";") if p.strip()]


def publish_profile() -> str:
    profile = os.environ.get("PAYLASIM_PROFILI") or next(iter(gemini_profiles()), "")
    if not profile:
        raise RuntimeError(".env içinde PAYLASIM_PROFILI (ya da GEMINI_PROFILLER) tanımlı değil")
    return profile


def daily_limit() -> int:
    return int(os.environ.get("GEMINI_GUNLUK_LIMIT", "3"))


def _today_state(path: Path) -> tuple[dict, str]:
    today = date.today().isoformat()
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {k: v for k, v in data.items() if v.get("tarih") == today}, today


def available(path: Path | None = None) -> list[str]:
    state, _ = _today_state(path or STATE_PATH)
    limit = daily_limit()
    return [
        p for p in gemini_profiles()
        if not state.get(p, {}).get("bitti") and state.get(p, {}).get("adet", 0) < limit
    ]


def record(profile: str, *, exhausted: bool = False, path: Path | None = None) -> None:
    path = path or STATE_PATH
    state, today = _today_state(path)
    entry = state.setdefault(profile, {"tarih": today, "adet": 0})
    if exhausted:
        entry["bitti"] = True
    else:
        entry["adet"] += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
