"""Arayüz ikonları (24x24, çizgi stili). Şablonlarda: {{ icon('video', 18) }}"""
from markupsafe import Markup

PATHS = {
    "grid": '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/>'
            '<rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
    "video": '<rect x="2.5" y="4.5" width="19" height="15" rx="3"/><path d="m10 9.2 4.8 2.8-4.8 2.8z"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "repeat": '<path d="m17 2 4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14"/><path d="m7 22-4-4 4-4"/>'
              '<path d="M21 13v1a4 4 0 0 1-4 4H3"/>',
    "gem": '<path d="M6 3h12l4 6-10 12L2 9z"/><path d="M11 3 8 9l4 12 4-12-3-6"/><path d="M2 9h20"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    "logout": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
    "sparkles": '<path d="M11 3.5 12.9 8l4.6 1.9-4.6 1.9L11 16.4l-1.9-4.6L4.5 9.9 9.1 8z"/>'
                '<path d="M18.5 14.5l.9 2.1 2.1.9-2.1.9-.9 2.1-.9-2.1-2.1-.9 2.1-.9z"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "copy": '<rect x="9" y="9" width="12" height="12" rx="2.5"/><path d="M5 15H4.5A1.5 1.5 0 0 1 3 13.5v-9A1.5 1.5 0 0 1 4.5 3h9A1.5 1.5 0 0 1 15 4.5V5"/>',
    "download": '<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18"/>',
    "palette": '<path d="M12 21a9 9 0 1 1 9-9c0 2.2-1.8 3.5-4 3.5h-1.6a1.9 1.9 0 0 0-1.4 3.2c.5.6.2 2.3-2 2.3z"/>'
               '<circle cx="7.5" cy="11" r="1"/><circle cx="10" cy="7" r="1"/><circle cx="14.5" cy="7" r="1"/>',
    "settings": '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/>'
                '<circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
    "book": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>'
            '<path d="M9 7h7M9 11h5"/>',
    "message": '<path d="M21 14.5a2 2 0 0 1-2 2H8l-5 4.5V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><path d="M8 8.5h8M8 12h5"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "monitor": '<rect x="2.5" y="4" width="19" height="13" rx="2.5"/><path d="M8 21h8M12 17v4"/>',
    "moon": '<path d="M20.5 14.5A8.5 8.5 0 1 1 9.5 3.5a7 7 0 0 0 11 11z"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.3a2.6 2.6 0 0 1 5 .9c0 1.7-2.5 2.3-2.5 3.8"/><path d="M12 17h.01"/>',
    "list": '<path d="M9 6h11M9 12h11M9 18h11"/><path d="M4 6h.01M4 12h.01M4 18h.01"/>',
    "flag": '<path d="M5 21V4"/><path d="M5 4h11l-2 4 2 4H5"/>',
    "zap": '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    "rocket": '<path d="M4.5 16.5c-1.5 1.3-2 5-2 5s3.7-.5 5-2c.7-.8.7-2.1-.1-2.9a2.1 2.1 0 0 0-2.9-.1z"/>'
              '<path d="m12 15-3-3a22 22 0 0 1 2-4A13 13 0 0 1 22 2c0 2.7-.8 7.5-6 11a22 22 0 0 1-4 2z"/>'
              '<path d="M9 12H4s.6-3 2-4c1.6-1.1 5 0 5 0"/><path d="M12 15v5s3-.6 4-2c1.1-1.6 0-5 0-5"/>',
    "crown": '<path d="M3 18h18"/><path d="m3.5 7 4.5 4 4-6.5 4 6.5 4.5-4-2 10.5h-13z"/>',
    "play": '<path d="M7 4.5v15l12.5-7.5z"/>',
    "arrow-right": '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
    "arrow-left": '<path d="M19 12H5"/><path d="m11 6-6 6 6 6"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "calendar": '<rect x="3" y="4.5" width="18" height="16.5" rx="2.5"/><path d="M16 2.5v4M8 2.5v4M3 10h18"/>',
    "alert": '<path d="M10.3 3.9 2.4 17.5A2 2 0 0 0 4.1 20.5h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9.5v4M12 17h.01"/>',
    "trash": '<path d="M3 6h18"/><path d="M8 6V4.5A1.5 1.5 0 0 1 9.5 3h5A1.5 1.5 0 0 1 16 4.5V6"/><path d="m5.5 6 1 13.5A2 2 0 0 0 8.5 21.5h7a2 2 0 0 0 2-2L18.5 6"/>',
    "pause": '<rect x="6" y="4" width="4" height="16" rx="1.2"/><rect x="14" y="4" width="4" height="16" rx="1.2"/>',
    "edit": '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    "mic": '<rect x="9" y="2.5" width="6" height="12" rx="3"/><path d="M5 10.5a7 7 0 0 0 14 0M12 17.5v4"/>',
    "type": '<path d="M4 7V4.5h16V7M9 20h6M12 4.5V20"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "refund": '<path d="M3 12a9 9 0 0 1 15.4-6.4L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15.4 6.4L3 16"/><path d="M3 21v-5h5"/>',
    "layers": '<path d="m12 2.5 9.5 5L12 12.5 2.5 7.5z"/><path d="m2.5 16.5 9.5 5 9.5-5"/><path d="m2.5 12 9.5 5 9.5-5"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "gift": '<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M12 8v13"/><path d="M19 12v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7"/>'
            '<path d="M7.5 8a2.5 2.5 0 0 1 0-5C11 3 12 8 12 8s1-5 4.5-5a2.5 2.5 0 0 1 0 5"/>',
    "tag": '<path d="M12.6 2.6A2 2 0 0 0 11.2 2H4a2 2 0 0 0-2 2v7.2a2 2 0 0 0 .6 1.4l8.7 8.7a2.4 2.4 0 0 0 3.4 0l6.6-6.6a2.4 2.4 0 0 0 0-3.4z"/>'
           '<circle cx="7.5" cy="7.5" r="1.5"/>',
    "share": '<path d="M4 12v7a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7"/><path d="m16 6-4-4-4 4"/><path d="M12 2v13"/>',
    "film": '<rect x="3" y="3" width="18" height="18" rx="2.5"/><path d="M7 3v18M17 3v18M3 7.5h4M17 7.5h4M3 12h18M3 16.5h4M17 16.5h4"/>',
    "bank": '<path d="M3 21h18M5.5 10v8M9.5 10v8M14.5 10v8M18.5 10v8"/><path d="M2.5 10 12 3.5l9.5 6.5z"/>',
    "phone": '<rect x="6" y="2" width="12" height="20" rx="3"/><path d="M11 18h2"/>',
    "lock": '<rect x="4" y="11" width="16" height="10" rx="2.5"/><path d="M8 11V7.5a4 4 0 0 1 8 0V11"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="m3.5 7 8.5 6 8.5-6"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "hash": '<path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/>',
    "eye": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "wand": '<path d="m15 4 5 5"/><path d="M3 21 16.5 7.5"/><path d="M18 2v2M17 3h2M21 7v2M20 8h2"/>',
    "brain": '<path d="M12 5a3 3 0 0 0-5.8-1A3.5 3.5 0 0 0 3.5 9a3.5 3.5 0 0 0 .8 6.4A3.5 3.5 0 0 0 9 20a3 3 0 0 0 3-1z"/>'
             '<path d="M12 5a3 3 0 0 1 5.8-1A3.5 3.5 0 0 1 20.5 9a3.5 3.5 0 0 1-.8 6.4A3.5 3.5 0 0 1 15 20a3 3 0 0 1-3-1z"/><path d="M12 5v14"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6.5 6.5 0 0 1 3.5 6"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
}


BRANDS = {  # tek renk dolgulu platform simgeleri (uyumluluğu göstermek için)
    "tiktok": '<path d="M16.5 3c.4 2.3 1.9 3.8 4.2 4v3.2c-1.5 0-2.9-.4-4.2-1.2v6.4a6 6 0 1 1-6-6h.6v3.3a2.8 2.8 0 1 0 2.2 2.7V3h3.2z"/>',
    "instagram": '<path fill-rule="evenodd" d="M7.5 3h9A4.5 4.5 0 0 1 21 7.5v9a4.5 4.5 0 0 1-4.5 4.5h-9A4.5 4.5 0 0 1 3 16.5v-9A4.5 4.5 0 0 1 7.5 3zm0 1.8A2.7 2.7 0 0 0 4.8 7.5v9a2.7 2.7 0 0 0 2.7 2.7h9a2.7 2.7 0 0 0 2.7-2.7v-9a2.7 2.7 0 0 0-2.7-2.7zM12 7.6a4.4 4.4 0 1 1 0 8.8 4.4 4.4 0 0 1 0-8.8zm0 1.8a2.6 2.6 0 1 0 0 5.2 2.6 2.6 0 0 0 0-5.2zm4.8-3a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"/>',
    "youtube": '<path d="M21.6 7.2a2.6 2.6 0 0 0-1.8-1.8C18.2 5 12 5 12 5s-6.2 0-7.8.4A2.6 2.6 0 0 0 2.4 7.2C2 8.8 2 12 2 12s0 3.2.4 4.8a2.6 2.6 0 0 0 1.8 1.8C5.8 19 12 19 12 19s6.2 0 7.8-.4a2.6 2.6 0 0 0 1.8-1.8c.4-1.6.4-4.8.4-4.8s0-3.2-.4-4.8zM10 15V9l5.2 3L10 15z"/>',
}


def brand(name: str, size: int = 18) -> Markup:
    return Markup(f'<svg class="ic" width="{size}" height="{size}" viewBox="0 0 24 24" fill="currentColor" '
                  f'aria-hidden="true">{BRANDS[name]}</svg>')


def icon(name: str, size: int = 18, cls: str = "") -> Markup:
    body = PATHS.get(name, PATHS["info"])
    return Markup(
        f'<svg class="ic {cls}" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{body}</svg>'
    )


# Zaply işareti: amber zemin üzerinde şimşek (zemin rengi CSS'te .logo-mark)
BOLT = ("M14.2 1.8 4.6 13.4c-.35.42-.05 1.06.5 1.06h5.5l-1.85 7.3c-.13.52.53.84.87.42l9.7-11.7c.35-.42.05-1.06-.5-1.06"
        "h-5.5l1.75-7.2c.13-.52-.53-.84-.87-.42z")
LOGO = Markup(
    f'<span class="logo-mark" aria-hidden="true"><svg width="21" height="21" viewBox="0 0 24 24">'
    f'<path d="{BOLT}" fill="#1a1206"/></svg></span>'
)
