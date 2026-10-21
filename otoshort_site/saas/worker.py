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
from .media import SUB_STYLES
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


def notify(user_id: int, subject: str, title: str, intro: str, button: tuple[str, str] | None = None, /, **kw) -> None:
    """Bildirim e-postası (kullanıcı bildirimleri kapattıysa ya da e-postası doğrulanmamışsa gönderilmez).
    Metinler Türkçe kalıptır; kullanıcının dilinde gönderilir. {ad} yer tutucuları kw ile dolar ({site} hazır)."""
    from . import i18n

    try:
        with db.session() as s:
            u = s.get(User, user_id)
            if not u or not u.notify or not u.email_verified:
                return
            to, lang = u.email, i18n.norm(u.lang)
        kw.setdefault("site", config.SITE_NAME)
        btn = (i18n.t(button[0], lang), button[1]) if button else None
        mailer.send(to, i18n.t(subject, lang, **kw), mailer.render(i18n.t(title, lang, **kw), i18n.th(intro, lang, **kw),
                                                                   btn, lang=lang))
    except Exception:
        log.exception("Bildirim gönderilemedi")


def channel_params(s, ch: Channel) -> dict:
    """Kanalın ayarlarından yeni video işinin parametreleri (kayıtlı karakterlerin güncel hâli dahil)."""
    from . import karakter

    characters, ref_image = karakter.cast(s, ch.user_id, ch.cast_ids, ch.characters, ch.ref_image)
    return dict(idea=ch.topic, characters=characters, style=ch.style, language=ch.language, quality=ch.quality,
                channel_id=ch.id, ref_image=ref_image, subtitles=ch.subtitles, subtitle_style=ch.subtitle_style,
                seconds=ch.seconds, format=ch.format, background=ch.background, hook=ch.hook, progress=ch.progress,
                voice=ch.voice, music=ch.music)


def create_job(s, user_id: int, *, idea: str, characters: str, style: str, language: str, quality: str,
               channel_id: int | None = None, slot: str | None = None, ref_image: str = "",
               subtitles: bool = False, subtitle_style: str = "viral", seconds: int = 8, format: str = "",
               background: str = "", hook: bool = False, progress: bool = False, voice: str = "",
               music: str = "") -> Job:
    """İşi oluşturur ve krediyi düşer (yetmezse credits.NotEnoughCredits)."""
    from . import abonelik, formatlar

    format = format if format in formatlar.FORMATS else ""
    if format:  # viral format: video modeli yok, sabit fiyat, abonelik gerekmez
        seconds = max(config.FORMAT_MIN_SECONDS, config.clamp_seconds(seconds))
        background = background if background in formatlar.background_choices() else formatlar.default_background()
        cost = config.FORMAT_CREDITS
    else:
        if config.VIDEO_OFF:
            raise abonelik.VideoOff()
        abonelik.check(s, user_id, quality)  # bu yapay zekâ kullanıcının aboneliğinde yoksa PlanRequired
        seconds = config.clamp_seconds(seconds)
        cost = config.price(quality, seconds)
        background = ""
    job = Job(user_id=user_id, channel_id=channel_id, slot=slot, idea=idea, characters=characters, style=style,
              language=language, quality=quality, cost=cost, ref_image=ref_image or "", subtitles=bool(subtitles),
              subtitle_style=subtitle_style if subtitle_style in SUB_STYLES else "", seconds=seconds,
              format=format, background=background, hook=bool(hook) and not format, progress=bool(progress),
              voice=voice if format and ai_mod.valid_voice(voice) else "",
              music=music if format and music in formatlar.music_choices() else "")
    s.add(job)
    s.flush()
    label = formatlar.FORMATS[format][0] if format else config.QUALITIES[quality]["label"]
    credits.charge(s, user_id, cost, f"Video #{job.id} ({label})", job.id)
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
        quality, seconds = job.quality, config.clamp_seconds(job.seconds)
        fmt, background = job.format, job.background
        want_subs, sub_style = job.subtitles, job.subtitle_style
        want_hook, want_bar, voice, music = job.hook, job.progress, job.voice, job.music
        from . import media

        ref = media.ref_path(job.ref_image) if job.ref_image and config.supports_refs(job.quality) else None
        refs = [ref] if ref else []
        if refs:
            params["has_ref"] = True
    try:
        rel = f"{job_id}.mp4"
        if fmt:  # viral format: yazışma/hikâye metni + seslendirme + çizim
            script = make_format(generator, fmt, params["idea"], params["language"], seconds, background, past,
                                 video_dir() / rel, voice=voice, bar=want_bar, music=music)
            raw = None
        else:
            clips = config.plan_clips(quality, seconds)
            script = generator.write_script(**params, past=past, seconds=seconds, clips=clips)
            shots = ai_mod.fit_shots(script.shots, script.video_prompt, len(clips))
            with db.session() as s:
                s.execute(update(Job).where(Job.id == job_id).values(
                    prompt="\n\n".join(shots) if len(shots) > 1 else script.video_prompt, title=script.title,
                    caption=script.caption, hashtags=" ".join(script.hashtags), summary=script.summary))
            make_scenes(generator, shots, clips, quality, refs, video_dir() / rel, seconds)
            hook = (script.hook or script.title) if want_hook else ""
            raw = add_subtitles(generator, video_dir() / rel, params["language"], sub_style if want_subs else None,
                                hook=hook, bar=want_bar) if want_subs or hook or want_bar else None
        if fmt:
            with db.session() as s:
                s.execute(update(Job).where(Job.id == job_id).values(
                    prompt=script.video_prompt, title=script.title, caption=script.caption,
                    hashtags=" ".join(script.hashtags), summary=script.summary))
        make_poster(video_dir() / rel)
        with db.session() as s:
            s.execute(update(Job).where(Job.id == job_id).values(status="hazir", video_file=rel, finished_at=now(),
                                                                 raw_file=raw.name if raw else ""))
            job = s.get(Job, job_id)
            ch_name = job.channel.name if job.channel else None
            uid = job.user_id
        from . import growth

        with db.session() as s:  # sadakat: her SADAKAT_ESIK kredilik videoda 1 Ekonomik video hediye
            gift = growth.loyalty(s, uid)
        if gift:
            notify(uid, "{site}: 1 video bizden 🎁", "Sadakat hediyen yüklendi!",
                   "Videolarına {every} kredi harcadın; teşekkür olarak hesabına <b>{n} kredi</b> (1 Ekonomik video) yükledik.",
                   ("Video üret", f"{_site()}/video/yeni"), every=config.LOYALTY_EVERY, n=gift)
        log.info("İş %s hazır", job_id)
        from . import publisher, social

        platforms, needs_ok = publisher.queue_for_channel_job(job_id)
        if needs_ok:  # onaylı paylaşım: izleyip tek tıkla onaylasın
            notify(uid, "{channel}: yeni video onayını bekliyor 👀", "Paylaşmadan önce bir bak",
                   "<b>{channel}</b> kanalın için yeni video hazır: “{title}”. İzle; beğenirsen tek tıkla onayla, "
                   "{platforms} hesabına yüklensin. Beğenmezsen paylaşma, hiçbir yere gitmez.",
                   ("İzle ve onayla", f"{_site()}/video/{job_id}"), channel=ch_name, title=script.title,
                   platforms=", ".join(social.PLATFORMS[p]["short"] for p in platforms))
        elif ch_name:  # otomatik kanal videosu: kullanıcı başında değil, haber ver
            notify(uid, "{channel}: yeni videon hazır 🎬", "Yeni videon hazır!",
                   "<b>{channel}</b> kanalın için yeni video üretildi: “{title}”. "
                   "Başlığı, açıklaması ve hashtag'leriyle birlikte paylaşmaya hazır.",
                   ("Videoyu gör", f"{_site()}/video/{job_id}"), channel=ch_name, title=script.title)
    except Exception as e:
        log.exception("İş %s başarısız", job_id)
        if isinstance(e, ai_mod.ContentBlocked):
            msg = "Video güvenlik filtresine takıldı. Fikri biraz değiştirip tekrar dene. Kredin iade edildi."
        elif ai_mod.is_quota_error(e):
            msg = "Yapay zekâ kullanım sınırına takıldı. Birkaç dakika sonra tekrar dene. Kredin iade edildi."
        else:
            msg = "Video üretilemedi, kredin iade edildi. Biraz sonra tekrar dene."
        fail_job(job_id, msg, f"{type(e).__name__}: {e}")


def make_format(generator, kind: str, idea: str, language: str, seconds: int, background: str, past: list[str],
                out: Path, voice: str = "", bar: bool = False, music: str = "") -> "ai_mod.Script":
    """Viral format videosu: yapay zekâ metni yazar, her satır seslendirilir, balonlar/kart + altyazı çizilir.
    voice: anlatıcı (ai.VOICE_PRESETS'ten bir ses ya da "female"/"male"; boşsa yapay zekâ seçer; mesajlaşmada "ben") · bar: en altta ilerleme çubuğu.
    Okunan metinler zamanlarıyla '<ad>.srt' altyazı dosyasına da yazılır."""
    import tempfile

    from . import formatlar, media

    data = generator.write_format(kind=kind, idea=idea, language=language, seconds=seconds, past=past)
    narrator, nstyle = ai_mod.voice_for(voice, data.get("voice", "female"))  # tek sesli formatların anlatıcısı
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        if kind == "sohbet":
            msgs = data["messages"][:20] or [{"me": False, "text": idea or "..."}]
            # seçilen ses "ben" olur; karşı taraf yapay zekânın seçtiği cinsiyette, benden farklı bir ses
            me_v, me_style = ai_mod.voice_for(voice, data["me_voice"])
            other_v = next(v for v in ai_mod.VOICES[data["contact_voice"]] if v != me_v)
            parts: list = [None] * len(msgs)  # her ses kendi satırlarını tek seferde okur (2 istek)
            for v, who, st in ((me_v, True, me_style), (other_v, False, "")):
                idx = [i for i, m in enumerate(msgs) if bool(m["me"]) == who]
                if idx:
                    for i, part in zip(idx, speak_lines(generator, [msgs[i]["text"] for i in idx], v, tmp,
                                                        "me" if who else "o", st)):
                        parts[i] = part
            times = formatlar.join_audio(parts, 0.3, 0.5, 1.2, tmp / "ses.wav")
            total = times[-1][1] + 1.2
            ass = formatlar.chat_ass(msgs, times, data["contact"], total)
            lines = [("> " if m["me"] else "< ") + m["text"] for m in msgs]
            spoken = [m["text"] for m in msgs]
        elif kind in ("secim", "quiz", "bilgi", "liste", "dogru", "bayrak", "bilmece"):
            # tek sesli, tur tur ilerleyen formatlar: açılış + turlar (+ düşünme süresi) + kapanış çağrısı
            w, voice = formatlar.words(language), narrator
            if kind == "secim":
                rounds = data["rounds"][:10]
                texts = [w["wyr_say"], *(f"{r['a']}, {w['or_word']} {r['b']}?" for r in rounds)]
                gaps = [0.4] + [formatlar.THINK] * len(rounds)
                lines = [f"{r['a']} / {r['b']}" for r in rounds]
                closing = f"{w['pick']} {w['comment']}"
            elif kind == "quiz":
                qs = data["questions"][:8]
                texts, gaps = [f"{w['quiz_say']} {data['topic']}".strip()], [0.4]
                for q in qs:
                    texts += [q["q"] + " " + " ".join(f"{k}: {o}." for k, o in zip("ABC", q["options"])),
                              f"{w['answer']}: {q['options'][q['answer']]}!"]
                    gaps += [formatlar.THINK, 0.9]
                lines = [f"{q['q']} → {q['options'][q['answer']]}" for q in qs]
                closing = f"{w['score']} {w['comment']}"
            elif kind == "bilmece":
                riddles = data["items"][:8]
                texts, gaps = [w["riddle_say"]], [0.4]
                for x in riddles:
                    texts += [x["q"], f"{w['answer']}: {x['answer']}!"]
                    gaps += [formatlar.THINK, 0.9]
                lines = [f"{x['q']} → {x['answer']}" for x in riddles]
                closing = f"{w['score']} {w['comment']}"
            elif kind == "bilgi":
                facts = data["facts"][:10]
                texts, gaps = [w["facts_say"], *facts], [0.4] + [0.6] * len(facts)
                lines, closing = facts, w["follow"]
            elif kind == "liste":
                items = data["items"][:7]
                n = len(items)
                texts = [f"{w['top_say']}: {data['topic']}".strip(" :"),
                         *(f"{n - i}. {x['name']}. {x['why']}" for i, x in enumerate(items))]
                gaps = [0.4] + [0.7] * n
                lines = [f"#{n - i} {x['name']} — {x['why']}" for i, x in enumerate(items)]
                closing = f"{w['agree']} {w['comment']}"
            else:
                items = data["items"][:8]
                yes, no = (w["yes"], w["no"]) if kind == "dogru" else (w["green"], w["red"])
                texts, gaps = [w["tf_say"] if kind == "dogru" else w["flag_say"]], [0.4]
                for x in items:
                    texts += [x["text"], f"{yes if x['ok'] else no}! {x['why']}".strip()]
                    gaps += [formatlar.THINK, 0.9]
                lines = [f"{x['text']} → {yes if x['ok'] else no}" for x in items]
                closing = f"{w['agree']} {w['comment']}"
            if len(texts) < 2:
                raise RuntimeError("Format metni yazılamadı")
            texts.append(closing)
            gaps.append(0.0)
            parts = speak_lines(generator, texts, voice, tmp, "q", nstyle)
            spoken = texts
            times = formatlar.join_audio(parts, gaps, 0.4, 1.2, tmp / "ses.wav")
            total = times[-1][1] + 1.2
            if kind == "secim":
                ass = formatlar.wyr_ass(rounds, times, total, language)
            elif kind == "quiz":
                ass = formatlar.quiz_ass(data["topic"], qs, times, total, language)
            elif kind == "bilmece":
                ass = formatlar.riddle_ass(riddles, times, total, language)
            elif kind == "bilgi":
                ass = formatlar.facts_ass(facts, times, total, language)
            elif kind == "liste":
                ass = formatlar.top_ass(data["topic"], items, times, total, language)
            else:
                ass = formatlar.verdict_ass(kind, items, times, total, language)
        else:  # hikaye ve korku
            sents = data["sentences"][:30] or [idea or "..."]
            parts = speak_lines(generator, sents, narrator, tmp, "s", nstyle)
            times = formatlar.join_audio(parts, 0.2, 0.3, 1.0, tmp / "ses.wav")
            total = times[-1][1] + 1.0
            ass = formatlar.story_ass(sents[0], data["community"], sents, times, total, language, dark=kind == "korku")
            lines = spoken = sents
        if bar:
            ass += "\n".join(media.progress_events(total, formatlar.W, formatlar.H, style="D")) + "\n"
        formatlar.render(ass, tmp / "ses.wav", total, background, out, music=formatlar.pick_music(music))
    out.with_suffix(".srt").write_text(media.srt([{"text": t, "start": a, "end": b}
                                                  for t, (a, b) in zip(spoken, times)]), encoding="utf-8")
    return ai_mod.Script(video_prompt="\n".join(lines), title=data["title"], caption=data["caption"],
                         hashtags=data["hashtags"], summary=data["summary"])


def speak_lines(generator, texts: list[str], voice: str, tmp: Path, prefix: str, style: str = "") -> list[Path]:
    """Satırları tek seferde seslendirir (paragraflar arası duraksamadan bölünür): ücretsiz katmanda dakikada
    birkaç seslendirme isteği hakkı olduğu için video başına bir istek. Bölünemezse satır satır seslendirir."""
    from . import formatlar

    if len(texts) > 1:
        whole = generator.speak(text="\n\n".join(t.strip() for t in texts), voice=voice, out=tmp / f"{prefix}hepsi.wav",
                                style=style)
        parts = formatlar.split_audio(whole, len(texts), tmp, prefix, [len(t) + 8 for t in texts])
        if parts:
            return parts
        log.info("Ses bölünemedi, satır satır seslendiriliyor (%d satır)", len(texts))
    return [generator.speak(text=t, voice=voice, out=tmp / f"{prefix}{i}.wav", style=style)
            for i, t in enumerate(texts)]


def make_scenes(generator, shots: list[str], clips: list[int], quality: str, refs: list, out: Path,
                seconds: int) -> Path:
    """Sahneleri üretir; birden fazlaysa birleştirip tam süreye kırpar. Bir sahne bile üretilemezse iş başarısız."""
    from . import media

    if len(clips) == 1:
        generator.make_video(prompt=shots[0], quality=quality, out=out, refs=refs, seconds=clips[0])
        if clips[0] > seconds:
            try:
                media.trim(out, seconds)
            except Exception:
                log.exception("Video kırpılamadı: %s", out.name)
        return out
    parts = []
    try:
        for i, (prompt, sec) in enumerate(zip(shots, clips)):
            part = out.with_name(f"{out.stem}-sahne{i + 1}.mp4")
            generator.make_video(prompt=prompt, quality=quality, out=part, refs=refs, seconds=sec)
            parts.append(part)
        return media.join_clips(parts, out, seconds)
    finally:
        for part in parts:
            part.unlink(missing_ok=True)


def add_subtitles(generator, video: Path, language: str, style: str | None = "", hook: str = "",
                  bar: bool = False) -> Path | None:
    """Konuşmaları döküp videoya basar (+ istenirse açılış kancası ve ilerleme çubuğu). Başarısız olursa video
    yazısız kalır (iş yine de hazır sayılır). style: media.SUB_STYLES'tan biri; None = altyazı yok.
    Kelime kelime stillerde (viral, kutu, neon, tek) kelime zamanları da istenir."""
    from . import media

    try:
        segments = [] if style is None else generator.transcribe(video=video, language=language,
                                                                 words=style in media.WORD_STYLES)
        return media.burn_subtitles(video, segments, style or "", language, hook=hook, bar=bar)
    except Exception:
        log.exception("Altyazı eklenemedi: %s", video.name)
        return None


def fail_job(job_id: int, user_msg: str, detail: str = "") -> None:
    with db.session() as s:
        # Sadece henüz başarısız sayılmamış işi işaretle: iade bir kere yapılır
        res = s.execute(update(Job).where(Job.id == job_id, Job.status != "hata").values(
            status="hata", error=user_msg, error_detail=(detail or "")[:500], finished_at=now()))
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
    from . import abonelik

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
                    job = create_job(s, ch.user_id, slot=slot, **channel_params(s, ch))
                    s.execute(update(Channel).where(Channel.id == ch.id).values(notice=""))
                    created.append(job.id)
            except credits.NotEnoughCredits:
                with db.session() as s:
                    first = not s.get(Channel, ch.id).notice
                    s.execute(update(Channel).where(Channel.id == ch.id).values(
                        notice=f"{slot} videosu kredi yetersiz olduğu için üretilmedi."))
                if first:  # aynı uyarı için tekrar tekrar e-posta atma
                    notify(ch.user_id, "{channel}: kredin bitti", "Otomatik kanalın durdu",
                           "<b>{channel}</b> kanalının {slot} videosu kredi yetersiz olduğu için üretilmedi. "
                           "Kredi yüklediğinde kanal kaldığı yerden devam eder.", ("Kredi yükle", f"{_site()}/kredi"),
                           channel=ch.name, slot=slot)
            except abonelik.PlanRequired:  # abonelik bitti: bu kalitede üretilmez, kredi düşmez
                with db.session() as s:
                    first = not s.get(Channel, ch.id).notice
                    s.execute(update(Channel).where(Channel.id == ch.id).values(
                        notice=f"{slot} videosu aboneliğin bu kaliteyi kapsamadığı için üretilmedi."))
                if first:
                    notify(ch.user_id, "{channel}: aboneliğini yenile", "Otomatik kanalın durdu",
                           "<b>{channel}</b> kanalının seçtiği kalite aboneliğinde yok (ya da aboneliğin bitti). "
                           "Aboneliğini yenilediğinde ya da kanalın kalitesini değiştirdiğinde devam eder.",
                           ("Abonelikler", f"{_site()}/abonelik"), channel=ch.name)
            except IntegrityError:
                pass  # aynı saat için iş zaten oluşturulmuş
    return created


def remind_plans() -> None:
    """Aboneliği 3 gün içinde bitecek olanlara bir kez hatırlatma (otomatik çekim yok)."""
    from . import abonelik

    with db.session() as s:
        due = abonelik.due_reminders(s)
    for uid, plan, until in due:
        notify(uid, "{site}: aboneliğin {date} tarihinde bitiyor", "Aboneliğin bitmek üzere",
               "<b>{plan}</b> aboneliğin {date} tarihinde bitiyor. Kesintisiz devam etmek için yenileme havaleni "
               "bildir; yeni 30 gün kalan günlerinin üstüne eklenir.", ("Aboneliği yenile", f"{_site()}/abonelik#odeme"),
               plan=config.PLANS[plan]["label"], date=until.astimezone(ZoneInfo(config.TIMEZONE)).strftime("%d.%m.%Y"))


def refill_plans() -> None:
    """Yıllık aboneliklerde zamanı gelen aylık kredileri yükler ve haber verir."""
    from . import abonelik

    with db.session() as s:
        done = abonelik.refill(s)
    for uid, plan, n in done:
        notify(uid, "{site}: bu ayın {n} kredisi yüklendi 💎", "Aylık kredin yüklendi",
               "Yıllık <b>{plan}</b> aboneliğinin bu ayki <b>{n} kredisi</b> hesabına yüklendi.",
               ("Video üret", f"{_site()}/video/yeni"), plan=config.PLANS[plan]["label"], n=n)


def recover() -> None:
    """Sunucu yeniden başlarken yarıda kalan işleri sıraya geri koyar."""
    with db.session() as s:
        s.execute(update(Job).where(Job.status == "uretiliyor").values(status="sirada"))
        from .models import Publication

        s.execute(update(Publication).where(Publication.status == "yukleniyor").values(status="bekliyor"))


class Worker:
    def __init__(self, generator=None):
        self.generator = generator or ai_mod.default_ai()
        self.pool = ThreadPoolExecutor(max_workers=MAX_PARALLEL + 2)  # +2: paylaşım yüklemeleri
        self.running = 0
        self.lock = threading.Lock()
        self.stop = threading.Event()

    def _done(self, _):
        with self.lock:
            self.running -= 1

    def tick(self) -> None:
        schedule_channels()
        remind_plans()
        refill_plans()
        self.daily_backup()
        self.publish_tick()
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

    def publish_tick(self) -> None:
        """Sıradaki paylaşımları yükler (video üretiminden ayrı, en fazla 2 aynı anda)."""
        from . import publisher

        while True:
            with self.lock:
                if getattr(self, "publishing", 0) >= 2:
                    return
            pid = publisher.claim()
            if pid is None:
                return
            with self.lock:
                self.publishing = getattr(self, "publishing", 0) + 1

            def done(_):
                with self.lock:
                    self.publishing -= 1
            self.pool.submit(publisher.run, pid).add_done_callback(done)

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

