import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CHANNELS_DIR = ROOT / "kanallar"
OUTPUT_DIR = ROOT / "cikti"

DEFAULT_MODELS = {
    "metin": "gemini-3.8-flash",
    "gorsel": "gemini-3.1-flash-image",
    "video": "veo-3.1-generate-preview",
}

DEFAULT_VIDEO = {
    "motor": "api",
    "en_boy": "9:16",
    "cozunurluk": "720p",
    "sure": 8,
    "negatif_prompt": "subtitles, captions, on-screen text, watermark, logo",
}


@dataclass
class Character:
    name: str
    description: str
    reference: Path


@dataclass
class Channel:
    slug: str
    dir: Path
    name: str
    language: str
    style: str
    characters: list[Character]
    themes: list[str]
    hashtags: list[str]
    extra_rules: list[str] = field(default_factory=list)
    models: dict = field(default_factory=dict)
    video: dict = field(default_factory=dict)
    platforms: dict = field(default_factory=dict)

    @property
    def history_path(self) -> Path:
        return self.dir / "gecmis.json"


def list_channels(channels_dir: Path = CHANNELS_DIR) -> list[str]:
    return sorted(p.parent.name for p in channels_dir.glob("*/kanal.yaml"))


def load_channel(slug: str, channels_dir: Path = CHANNELS_DIR) -> Channel:
    path = channels_dir / slug / "kanal.yaml"
    if not path.exists():
        mevcut = ", ".join(list_channels(channels_dir)) or "yok"
        raise FileNotFoundError(f"Kanal bulunamadı: {slug} (mevcut kanallar: {mevcut})")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    chan_dir = path.parent

    characters = [
        Character(
            name=c["ad"],
            description=c["tarif"].strip(),
            reference=chan_dir / c.get("referans", f"karakterler/{c['ad'].lower().replace(' ', '_')}.png"),
        )
        for c in raw["karakterler"]
    ]
    if not raw.get("temalar"):
        raise ValueError(f"{slug}: en az bir tema gerekli")

    models = {**DEFAULT_MODELS, **(raw.get("modeller") or {})}
    for key in models:
        env = os.environ.get(f"MODEL_{key.upper()}")
        if env:
            models[key] = env

    return Channel(
        slug=slug,
        dir=chan_dir,
        name=raw["ad"],
        language=raw.get("dil", "en"),
        style=raw.get("stil", "").strip(),
        characters=characters,
        themes=list(raw["temalar"]),
        hashtags=list(raw.get("hashtagler") or []),
        extra_rules=list(raw.get("kurallar") or []),
        models=models,
        video={**DEFAULT_VIDEO, **(raw.get("video") or {})},
        platforms=raw.get("platformlar") or {},
    )
