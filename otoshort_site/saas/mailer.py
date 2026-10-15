"""E-posta gönderimi. SMTP ayarlıysa gerçekten gönderir; değilse (demo) e-postayı saas_veri/epostalar'a kaydeder."""
import logging
import re
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from pathlib import Path

from . import config

log = logging.getLogger("saas.mailer")


def enabled() -> bool:
    return bool(config.SMTP_HOST and config.SMTP_FROM)


def outbox() -> Path:
    return config.DATA_DIR / "epostalar"


def render(title: str, intro: str, button: tuple[str, str] | None = None, outro: str = "") -> str:
    """Marka renklerinde, e-posta programlarıyla uyumlu (tablolu, satır içi stilli) HTML."""
    btn = ""
    if button:
        label, url = button
        btn = (f'<tr><td style="padding:8px 0 28px"><a href="{escape(url)}" style="display:inline-block;padding:15px 28px;'
               'border-radius:999px;background:#f4efe6;color:#0c0b0a;'
               f'font-weight:700;font-size:15px;text-decoration:none">{escape(label)}</a></td></tr>'
               f'<tr><td style="font-size:12px;color:#857e73;padding-bottom:20px;word-break:break-all">Buton çalışmazsa bu bağlantıyı '
               f'tarayıcına yapıştır:<br><a href="{escape(url)}" style="color:#c9ff6b">{escape(url)}</a></td></tr>')
    outro_html = f'<tr><td style="font-size:15px;line-height:1.6;color:#bdb5a8;padding-bottom:8px">{outro}</td></tr>' if outro else ""
    return f'''<!doctype html><html lang="tr"><body style="margin:0;background:#0c0b0a;padding:32px 12px;font-family:'Plus Jakarta Sans',Segoe UI,Arial,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#151311;border:1px solid #2e2a25;border-radius:22px">
<tr><td style="height:6px;border-radius:22px 22px 0 0;background:#d8b98a;background-image:linear-gradient(90deg,#f4efe6,#d8b98a)"></td></tr>
<tr><td style="padding:30px 32px 8px">
<table role="presentation" cellpadding="0" cellspacing="0" width="100%">
<tr><td style="padding-bottom:24px"><span style="display:inline-block;width:30px;height:30px;line-height:30px;text-align:center;border-radius:10px;background:#f4efe6;color:#0c0b0a;font-size:13px">▶</span>
<span style="color:#f4efe6;font-family:Georgia,'Times New Roman',serif;font-weight:400;font-size:22px;vertical-align:middle;margin-left:8px">{escape(config.SITE_NAME)}</span></td></tr>
<tr><td style="color:#f4efe6;font-family:Georgia,'Times New Roman',serif;font-size:28px;font-weight:400;line-height:1.2;padding-bottom:14px">{escape(title)}</td></tr>
<tr><td style="font-size:15px;line-height:1.6;color:#bdb5a8;padding-bottom:22px">{intro}</td></tr>
{btn}{outro_html}
</table></td></tr>
<tr><td style="padding:18px 32px 26px;border-top:1px solid #2a2622;font-size:12px;color:#857e73">Bu e-postayı {escape(config.SITE_NAME)} hesabınla ilgili bir işlem yapıldığı için aldın.</td></tr>
</table></td></tr></table></body></html>'''


def _text(html: str) -> str:
    t = re.sub(r"<br\s*/?>", "\n", html)
    t = re.sub(r"</(td|tr|p)>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def _smtp_send(msg: EmailMessage) -> None:
    ctx = ssl.create_default_context()
    if config.SMTP_PORT == 465:
        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=ctx, timeout=30) as s:
            if config.SMTP_USER:
                s.login(config.SMTP_USER, config.SMTP_PASSWORD)
            s.send_message(msg)
    else:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as s:
            s.starttls(context=ctx)
            if config.SMTP_USER:
                s.login(config.SMTP_USER, config.SMTP_PASSWORD)
            s.send_message(msg)


def send(to: str, subject: str, html: str, *, background: bool = True) -> str | None:
    """E-postayı gönderir. Demo modda kaydedilen dosyanın adını döndürür (gerçek gönderimde None)."""
    if not enabled():
        outbox().mkdir(parents=True, exist_ok=True)
        name = f"{time.strftime('%Y%m%d-%H%M%S')}-{int(time.time() * 1000) % 1000:03d}.html"
        (outbox() / name).write_text(f"<!-- Kime: {escape(to)} | Konu: {escape(subject)} -->\n{html}", encoding="utf-8")
        log.info("Demo e-posta kaydedildi: %s -> %s (%s)", subject, to, name)
        return name
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((config.SITE_NAME, config.SMTP_FROM))
    msg["To"] = to
    msg.set_content(_text(html))
    msg.add_alternative(html, subtype="html")

    def run():
        try:
            _smtp_send(msg)
        except Exception:
            log.exception("E-posta gönderilemedi: %s", subject)

    if background:
        threading.Thread(target=run, daemon=True).start()
    else:
        run()
    return None
