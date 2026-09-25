from google.genai import types

from .config import Channel, Character


def sniff_mime(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _extract_image(resp) -> tuple[bytes, str]:
    for cand in resp.candidates or []:
        for part in (cand.content.parts if cand.content else None) or []:
            if part.inline_data and part.inline_data.data:
                return part.inline_data.data, part.inline_data.mime_type or "image/png"
    raise RuntimeError(f"Görsel üretilemedi (model metin döndü ya da güvenlik filtresine takıldı): {resp.text!r}")


def _generate(client, model: str, contents: list, aspect_ratio: str) -> tuple[bytes, str]:
    resp = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
        ),
    )
    return _extract_image(resp)


def create_reference(client, channel: Channel, character: Character) -> None:
    prompt = (
        f"Character reference sheet, single full-body character centered on a plain white background, "
        f"front view, neutral pose. Character: {character.description}\nStyle: {channel.style}"
    )
    data, _ = _generate(client, channel.models["gorsel"], [prompt], "1:1")
    character.reference.parent.mkdir(parents=True, exist_ok=True)
    character.reference.write_bytes(data)


def ensure_references(client, channel: Channel, force: bool = False) -> list[Character]:
    created = []
    for c in channel.characters:
        if force or not c.reference.exists():
            create_reference(client, channel, c)
            created.append(c)
    return created


def make_first_frame(client, channel: Channel, scene: str) -> tuple[bytes, str]:
    contents: list = []
    for c in channel.characters:
        contents.append(f"Reference image for {c.name}:")
        data = c.reference.read_bytes()
        contents.append(types.Part.from_bytes(data=data, mime_type=sniff_mime(data)))
    contents.append(
        "Create the first frame of a vertical 9:16 video. Keep every character looking EXACTLY like their "
        f"reference image.\nScene: {scene}\nStyle: {channel.style}\nNo text, captions or watermarks."
    )
    return _generate(client, channel.models["gorsel"], contents, channel.video["en_boy"])
