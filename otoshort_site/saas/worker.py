"""Arka plan işçisi: sıradaki videoları üretir, otomatik kanalların saatlerinde iş oluşturur."""
import logging
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from . import ai as ai_mod
from . import config, credits, db, mailer
from .models import Channel, Job, User, now

log = logging.getLogger("saas.worker")
SLOT_GRACE = timedelta(hours=2)  # sunucu kapalıyken kaçan saatler en fazla bu kadar geriden telafi edilir
MAX_PARALLEL = 3


def video_dir():
    return config.DATA_DIR / "videolar"


def make_poster(video: Path) -> Path | None:
    """Videonun 1. saniyesinden kapak resmi (jpg) çıkarır; panelde küçük resim olarak kullanılır."""
    out = video.with_suffix(".jpg")
    try:
        import imageio_ffmpeg

        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-ss", "1", "-i", str(video),
                        "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "4", str(out)], check=True, timeout=60)
        return out if out.exists() else None
    except Exception:
        log.warning("Kapak resmi çıkarılamadı: %s", video.name)
        return None


def _site() -> str:
    return config.SITE_URL or "http://localhost:8000"


def notify(user_id: int, subject: str, title: str, intro: str, button: tuple[str, str] | None = None) -> None:
    """Bildirim e-postası (kullanıcı bildirimleri kapattıysa ya da e-postası doğrulanmamışsa gönderilmez)."""
    try:
        with db.session() as s:
            u = s.get(User, user_id)
            if not u or not u.notify or not u.email_verified:
                return
            to = u.email
        mailer.send(to, subject, mailer.render(title, intro, button))
    except Exception:
        log.exception("Bildirim gönderilemedi")


def create_job(s, user_id: int, *, idea: str, characters: str, style: str, language: str, quality: str,
               channel_id: int | None = None, slot: str | None = None) -> Job:
    """İşi oluşturur ve krediyi düşer (yetmezse credits.NotEnoughCredits)."""
    cost = config.QUALITIES[quality]["credits"]
    job = Job(user_id=user_id, channel_id=channel_id, slot=slot, idea=idea, characters=characters, style=style,
              language=language, quality=quality, cost=cost)
    s.add(job)
    s.flush()
    credits.charge(s, user_id, cost, f"Video #{job.id} ({config.QUALITIES[quality]['label']})", job.id)
    return job


def _past_summaries(s, job: Job) -> list[str]:
    q = select(Job.summary).where(Job.user_id == job.user_id, Job.id != job.id, Job.summary != "")
    q = q.where(Job.channel_id == job.channel_id) if job.channel_id else q
    return list(reversed(s.scalars(q.order_by(Job.id.desc()).limit(30)).all()))


def run_job(job_id: int, generator) -> None:
    with db.session() as s:
        job = s.get(Job, job_id)
        past = _past_summaries(s, job)
        params = dict(idea=job.idea, characters=job.characters, style=job.style, language=job.language)
        quality = job.quality
    try:
        script = generator.write_script(**params, past=past)
        with db.session() as s:
            s.execute(update(Job).where(Job.id == job_id).values(
                prompt=script.video_prompt, title=script.title, caption=script.caption,
                hashtags=" ".join(script.hashtags), summary=script.summary))
        rel = f"{job_id}.mp4"
        generator.make_video(prompt=script.video_prompt, quality=quality, out=video_dir() / rel)
        make_poster(video_dir() / rel)
        with db.session() as s:
            s.execute(update(Job).where(Job.id == job_id).values(status="hazir", video_file=rel, finished_at=now()))
            job = s.get(Job, job_id)
            ch_name = job.channel.name if job.channel else None
            uid = job.user_id
        log.info("İş %s hazır", job_id)
        if ch_name:  # otomatik kanal videosu: kullanıcı başında değil, haber ver
            from html import escape

            notify(uid, f"{ch_name}: yeni videon hazır 🎬", "Yeni videon hazır!",
                   f"<b>{escape(ch_name)}</b> kanalın için yeni video üretildi: “{escape(script.title)}”. "
                   "Başlığı, açıklaması ve hashtag'leriyle birlikte paylaşmaya hazır.",
                   ("Videoyu gör", f"{_site()}/video/{job_id}"))
    except Exception as e:
        log.exception("İş %s başarısız", job_id)
        if isinstance(e, ai_mod.ContentBlocked):
            msg = "Video güvenlik filtresine takıldı. Fikri biraz değiştirip tekrar dene. Kredin iade edildi."
        else:
            msg = "Video üretilemedi, kredin iade edildi. Biraz sonra tekrar dene."
        fail_job(job_id, msg, f"{type(e).__name__}: {e}")


def fail_job(job_id: int, user_msg: str, detail: str = "") -> None:
    with db.session() as s:
        # Sadece henüz başarısız sayılmamış işi işaretle: iade bir kere yapılır
        res = s.execute(update(Job).where(Job.id == job_id, Job.status != "hata").values(
            status="hata", error=user_msg, finished_at=now()))
        if res.rowcount == 1:
            job = s.get(Job, job_id)
            if job.cost:
                credits.add(s, job.user_id, job.cost, f"İade: video #{job_id}", job_id)
            if detail:
                log.warning("İş %s: %s", job_id, detail[:500])


def claim_next() -> int | None:
    with db.session() as s:
        for job_id in s.scalars(select(Job.id).where(Job.status == "sirada").order_by(Job.id).limit(5)):
            res = s.execute(update(Job).where(Job.id == job_id, Job.status == "sirada").values(status="uretiliyor"))
            if res.rowcount == 1:
                return job_id
    return None


def schedule_channels(at: datetime | None = None) -> list[int]:
    """Saati gelen kanal videolarını oluşturur. Oluşan iş id'lerini döndürür."""
    tz = ZoneInfo(config.TIMEZONE)
    at = (at or datetime.now(tz)).astimezone(tz)
    created = []
    with db.session() as s:
        channels = s.scalars(select(Channel).where(Channel.active.is_(True))).all()
    for ch in channels:
        for t in ch.time_list():
            try:
                hh, mm = (int(x) for x in t.split(":"))
            except ValueError:
                continue
            when = at.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if not (when <= at < when + SLOT_GRACE):
                continue
            slot = when.strftime("%Y-%m-%d %H:%M")
            with db.session() as s:
                if s.scalar(select(Job.id).where(Job.channel_id == ch.id, Job.slot == slot)):
                    continue
            try:
                with db.session() as s:
                    job = create_job(s, ch.user_id, idea=ch.topic, characters=ch.characters, style=ch.style,
                                     language=ch.language, quality=ch.quality, channel_id=ch.id, slot=slot)
                    s.execute(update(Channel).where(Channel.id == ch.id).values(notice=""))
                    created.append(job.id)
            except credits.NotEnoughCredits:
                with db.session() as s:
                    first = not s.get(Channel, ch.id).notice
                    s.execute(update(Channel).where(Channel.id == ch.id).values(
                        notice=f"{slot} videosu kredi yetersiz olduğu için üretilmedi. Kredi yükle."))
                if first:  # aynı uyarı için tekrar tekrar e-posta atma
                    from html import escape

                    notify(ch.user_id, f"{ch.name}: kredin bitti", "Otomatik kanalın durdu",
                           f"<b>{escape(ch.name)}</b> kanalının {slot} videosu kredi yetersiz olduğu için üretilmedi. "
                           "Kredi yüklediğinde kanal kaldığı yerden devam eder.", ("Kredi yükle", f"{_site()}/kredi"))
            except IntegrityError:
                pass  # aynı saat için iş zaten oluşturulmuş
    return created


def recover() -> None:
    """Sunucu yeniden başlarken yarıda kalan işleri sıraya geri koyar."""
    with db.session() as s:
        s.execute(update(Job).where(Job.status == "uretiliyor").values(status="sirada"))


class Worker:
    def __init__(self, generator=None):
        self.generator = generator or ai_mod.default_ai()
        self.pool = ThreadPoolExecutor(max_workers=MAX_PARALLEL)
        self.running = 0
        self.lock = threading.Lock()
        self.stop = threading.Event()

    def _done(self, _):
        with self.lock:
            self.running -= 1

    def tick(self) -> None:
        schedule_channels()
        self.daily_backup()
        while True:
            with self.lock:
                if self.running >= MAX_PARALLEL:
                    return
            job_id = claim_next()
            if job_id is None:
                return
            with self.lock:
                self.running += 1
            self.pool.submit(run_job, job_id, self.generator).add_done_callback(self._done)

    def daily_backup(self) -> None:
        from . import yedek

        today = datetime.now().date()
        if getattr(self, "_backup_day", None) == today:
            return
        self._backup_day = today
        try:
            if not yedek.backed_up_today():
                yedek.backup()
        except Exception:
            log.exception("Günlük yedek alınamadı")

    def loop(self, every: float = 5.0) -> None:
        recover()
        while not self.stop.is_set():
            try:
                self.tick()
            except Exception:
                log.exception("İşçi turu hata verdi")
            self.stop.wait(every)

    def start(self) -> threading.Thread:
        t = threading.Thread(target=self.loop, name="saas-worker", daemon=True)
        t.start()
        return t

