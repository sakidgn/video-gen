"""Paylaşım kuyruğu: hazır videoları bağlı hesaplara yükler (işçi turunda çalışır)."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError

from . import config, db, secretbox, social, tokens
from .models import Channel, Job, Publication, SocialAccount, now

log = logging.getLogger("saas.publisher")
MAX_ATTEMPTS = 3
RETRY_AFTER = timedelta(minutes=3)


def accounts(s, user_id: int) -> dict[str, SocialAccount]:
    return {a.platform: a for a in s.scalars(select(SocialAccount).where(SocialAccount.user_id == user_id))}


def queue(s, job: Job, platforms: list[str], status: str = "bekliyor") -> list[str]:
    """Video için paylaşım kayıtları açar (bağlı olmayan ve zaten sırada olan platformlar atlanır).
    status="onay": kullanıcı onaylayana kadar yüklenmez (onaylı paylaşım modu)."""
    linked = accounts(s, job.user_id)
    added = []
    for p in platforms:
        if p not in social.PLATFORMS or p not in linked:
            continue
        if s.scalar(select(Publication.id).where(Publication.job_id == job.id, Publication.platform == p)):
            continue
        try:
            with s.begin_nested():
                s.add(Publication(job_id=job.id, user_id=job.user_id, platform=p, status=status))
            added.append(p)
        except IntegrityError:
            pass
    return added


def queue_for_channel_job(job_id: int) -> tuple[list[str], bool]:
    """Otomatik kanal videosu hazır olunca kanalın seçtiği platformlara sıraya koyar.
    Kanal onaylı moddaysa kayıtlar "onay" durumunda açılır. (platformlar, onay bekliyor mu) döner."""
    with db.session() as s:
        job = s.get(Job, job_id)
        ch = s.get(Channel, job.channel_id) if job and job.channel_id else None
        if ch and ch.publish_to:
            added = queue(s, job, ch.publish_to.split(), "onay" if ch.approval else "bekliyor")
            return added, bool(added and ch.approval)
    return [], False


def approve(s, job_id: int) -> int:
    """Onay bekleyen paylaşımları yükleme sırasına alır; kaç kayıt onaylandığını döner."""
    return s.execute(update(Publication).where(Publication.job_id == job_id, Publication.status == "onay")
                     .values(status="bekliyor", attempts=0, error="", updated_at=None)).rowcount


def reject(s, job_id: int) -> int:
    """Onay bekleyen paylaşımları iptal eder (video hiçbir yere yüklenmez)."""
    rows = s.scalars(select(Publication).where(Publication.job_id == job_id, Publication.status == "onay")).all()
    for r in rows:
        s.delete(r)
    return len(rows)


def claim() -> int | None:
    with db.session() as s:
        # tekrar denemeler hemen değil, deneme sayısıyla artan aralıklarla alınır
        due = or_(Publication.attempts == 0, Publication.updated_at.is_(None),
                  Publication.updated_at < now() - RETRY_AFTER)
        for pid in s.scalars(select(Publication.id).where(Publication.status == "bekliyor", due)
                             .order_by(Publication.id).limit(5)):
            res = s.execute(update(Publication).where(Publication.id == pid, Publication.status == "bekliyor")
                            .values(status="yukleniyor", updated_at=now()))
            if res.rowcount == 1:
                return pid
    return None


def _fresh_access(acc: SocialAccount, cli) -> str:
    """Süresi dolmak üzereyse jetonu yeniler ve kaydeder."""
    expired = social.PublishError("Hesap bağlantısının süresi dolmuş. Bağlantılar sayfasından yeniden bağla.")
    try:
        access = secretbox.open_(acc.access_enc)
    except secretbox.SecretError:
        raise expired from None
    exp = acc.expires_at
    if exp and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp and exp - datetime.now(timezone.utc) < timedelta(minutes=10):
        try:
            new_access, expires_in, new_refresh = cli.refresh(secretbox.open_(acc.refresh_enc), access)
        except (secretbox.SecretError, social.PublishError) as e:  # izin geri alınmış ya da yenileme jetonu geçersiz
            log.warning("Jeton yenilenemedi (%s): %s", acc.platform, e)
            raise expired from None
        with db.session() as s:
            a = s.get(SocialAccount, acc.id)
            a.access_enc = secretbox.seal(new_access)
            if new_refresh:
                a.refresh_enc = secretbox.seal(new_refresh)
            a.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        access = new_access
    return access


def public_video_url(job_id: int) -> str:
    """Instagram gibi videoyu adresten indiren platformlar için süreli, imzalı bağlantı."""
    return f"{config.SITE_URL}/yayin/dosya/{tokens.make_media(job_id)}" if config.SITE_URL else ""


def run(pid: int, http=None) -> None:
    from . import worker

    with db.session() as s:
        pub = s.get(Publication, pid)
        job = s.get(Job, pub.job_id)
        acc = s.scalar(select(SocialAccount).where(SocialAccount.user_id == pub.user_id,
                                                   SocialAccount.platform == pub.platform))
        platform, attempts = pub.platform, pub.attempts
    try:
        if not acc:
            raise social.PublishError("Hesap bağlantısı kaldırılmış. Bağlantılar sayfasından yeniden bağla.")
        if job.status != "hazir" or not job.video_file:
            raise social.PublishError("Video hazır değil")
        cli = social.client(platform, http)
        access = _fresh_access(acc, cli)
        remote_id, url = cli.publish(access, acc.remote_id, worker.video_dir() / job.video_file,
                                     social.post_from_job(job), public_video_url(job.id))
        with db.session() as s:
            s.execute(update(Publication).where(Publication.id == pid).values(
                status="yayinda", remote_id=remote_id, url=url, error="", attempts=attempts + 1, updated_at=now()))
        log.info("Paylaşım %s (%s) yayında", pid, platform)
    except Exception as e:
        log.exception("Paylaşım %s başarısız", pid)
        msg = str(e)[:380] if isinstance(e, social.PublishError) else "Platform şu an yanıt vermedi."
        retry = attempts + 1 < MAX_ATTEMPTS and not isinstance(e, social.PublishError)
        with db.session() as s:
            s.execute(update(Publication).where(Publication.id == pid).values(
                status="bekliyor" if retry else "hata", error=msg, attempts=attempts + 1, updated_at=now()))
