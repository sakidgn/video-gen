import os


def gemini_profiles() -> list[str]:
    return [p.strip() for p in os.environ.get("GEMINI_PROFILLER", "").split(";") if p.strip()]


def publish_profile() -> str:
    profile = os.environ.get("PAYLASIM_PROFILI") or next(iter(gemini_profiles()), "")
    if not profile:
        raise RuntimeError(".env içinde PAYLASIM_PROFILI (ya da GEMINI_PROFILLER) tanımlı değil")
    return profile
