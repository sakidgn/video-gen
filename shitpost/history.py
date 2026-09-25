import json
from datetime import datetime, timezone
from pathlib import Path


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def recent_summaries(path: Path, n: int = 40) -> list[str]:
    return [e["ozet"] for e in load(path)[-n:]]


def recent_themes(path: Path, n: int = 5) -> list[str]:
    return [e["tema"] for e in load(path)[-n:]]


def add(path: Path, *, title: str, summary: str, theme: str, links: dict) -> None:
    entries = load(path)
    entries.append({
        "tarih": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "baslik": title,
        "ozet": summary,
        "tema": theme,
        "linkler": links,
    })
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
