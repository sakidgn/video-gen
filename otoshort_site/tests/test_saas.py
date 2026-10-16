import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from sqlalchemy import select

from saas import ai, config, db, worker
from saas.app import create_app
from saas.models import Channel, Job, User


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "ADMIN_EMAILS", {"admin@x.com"})
    app = create_app(start_worker=False, database_url=f"sqlite:///{tmp_path / 't.db'}")
    return TestClient(app)


def csrf(c, url="/"):
    return re.search(r'name="csrf" value="([^"]+)"', c.get(url).text).group(1)


def signup(c, email, pw="sifre1234", verify=True, plan="studyo"):
    r = c.post("/kayit", data={"email": email, "password": pw, "name": "Ali", "accept": "1", "consent": "1",
                               "csrf": csrf(c, "/kayit")}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/panel"
    if verify:
        with db.session() as s:
            u = s.scalar(select(User).where(User.email == email))
            u.email_verified = True
            u.is_admin = email in config.ADMIN_EMAILS  # gerçekte doğrulama bağlantısında verilir
            if plan:  # testlerde tüm yapay zekâ kademeleri açık olsun (abonelik kilidi ayrı test edilir)
                from datetime import timedelta, timezone

                u.plan, u.plan_until = plan, datetime.now(timezone.utc) + timedelta(days=30)


def last_mail(tmp_path):
    files = sorted((tmp_path / "epostalar").glob("*.html"))
    return files[-1].read_text(encoding="utf-8") if files else ""


def mail_link(tmp_path, path):
    return re.search(rf'href="http://testserver({path}/[^"]+)"', last_mail(tmp_path)).group(1)


def give(email, amount):
    from saas import credits

    with db.session() as s:
        uid = s.scalar(select(User.id).where(User.email == email))
        credits.add(s, uid, amount, "test")


def balance(email):
    with db.session() as s:
        return s.scalar(select(User.credits).where(User.email == email))


def run_queue(gen):
    while (jid := worker.claim_next()) is not None:
        worker.run_job(jid, gen)


def test_pages_render(client):
    for url in ["/", "/kayit", "/giris", "/yasal/kullanim", "/yasal/kvkk", "/yasal/mesafeli"]:
        assert client.get(url).status_code == 200, url
    assert client.get("/yok").status_code == 404
    r = client.get("/panel", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/giris"


def test_post_without_csrf_rejected(client):
    r = client.post("/kayit", data={"email": "a@b.com", "password": "sifre1234", "accept": "1", "consent": "1"})
    assert r.status_code == 400


def test_video_flow_charges_and_delivers(client, tmp_path):
    signup(client, "a@b.com")
    t = csrf(client, "/video/yeni")
    r = client.post("/video/yeni", data={"idea": "muz", "quality": "fast", "csrf": t}, follow_redirects=False)
    assert r.headers["location"] == "/kredi"  # kredi yok

    give("a@b.com", 100)
    r = client.post("/video/yeni", data={"idea": "muz", "quality": "fast", "style": "cartoon", "language": "tr",
                                         "csrf": t}, follow_redirects=False)
    job_url = r.headers["location"]
    assert balance("a@b.com") == 100 - config.QUALITIES["fast"]["credits"]
    assert "üretiliyor" in client.get(job_url).text.lower()

    run_queue(ai.FakeAI())
    page = client.get(job_url).text
    assert "Deneme videosu" in page and "indir=1" in page
    assert client.get(job_url + "/dosya").status_code == 200
    assert client.get(job_url + "/durum").json()["status"] == "hazir"

    # başka kullanıcı göremez
    other = TestClient(client.app)
    signup(other, "c@d.com")
    assert other.get(job_url).status_code == 404
    assert other.get(job_url + "/dosya").status_code == 404


def test_failed_video_refunds_once(client):
    signup(client, "a@b.com")
    give("a@b.com", 100)
    client.post("/video/yeni", data={"quality": "lite", "csrf": csrf(client, "/video/yeni")})
    run_queue(ai.FakeAI(fail_with=ai.ContentBlocked("unsafe")))
    assert balance("a@b.com") == 100
    with db.session() as s:
        job = s.scalar(select(Job))
        assert job.status == "hata" and "filtre" in job.error
    worker.fail_job(job.id, "tekrar")  # ikinci kez iade olmamalı
    assert balance("a@b.com") == 100


def test_topup_and_admin_approval(client):
    signup(client, "a@b.com")
    r = client.post("/kredi/bildirim", data={"package": "1", "sender_name": "Ali Veli", "accept": "1",
                                             "csrf": csrf(client, "/kredi")})
    assert "Bildirimin alındı" in r.text
    admin = TestClient(client.app)
    signup(admin, "admin@x.com")
    page = admin.get("/admin").text
    assert "Ali Veli" in page
    tid = re.search(r"/admin/yukleme/(\d+)/onayla", page).group(1)
    admin.post(f"/admin/yukleme/{tid}/onayla", data={"csrf": csrf(admin, "/admin")})
    assert balance("a@b.com") == config.PACKAGES[1][1]
    admin.post(f"/admin/yukleme/{tid}/onayla", data={"csrf": csrf(admin, "/admin")})  # çift onay yok
    assert balance("a@b.com") == config.PACKAGES[1][1]
    assert client.get("/admin").status_code == 404  # normal kullanıcı yönetime giremez


def test_channel_schedule_creates_jobs_once_and_stops_without_credits(client):
    signup(client, "a@b.com")
    client.post("/kanallar/yeni", data={"name": "Meyveler", "topic": "konuşan meyveler", "quality": "lite",
                                        "times": "09:45 18:30 25:99", "csrf": csrf(client, "/kanallar/yeni")})
    with db.session() as s:
        ch = s.scalar(select(Channel))
        assert ch.times == "09:45 18:30"
    tz = ZoneInfo(config.TIMEZONE)
    at = datetime(2026, 10, 13, 9, 50, tzinfo=tz)

    assert worker.schedule_channels(at) == []  # kredi yok
    with db.session() as s:
        assert "kredi yetersiz" in s.get(Channel, ch.id).notice
    give("a@b.com", 100)
    created = worker.schedule_channels(at)
    assert len(created) == 1
    assert worker.schedule_channels(at) == []  # aynı saat ikinci kez üretilmez
    assert balance("a@b.com") == 100 - config.QUALITIES["lite"]["credits"]
    assert worker.schedule_channels(datetime(2026, 10, 13, 12, 0, tzinfo=tz)) == []  # 2 saatten eski saat telafi edilmez

    run_queue(ai.FakeAI())
    gen = ai.FakeAI()
    worker.schedule_channels(datetime(2026, 10, 13, 18, 31, tzinfo=tz))
    run_queue(gen)
    with db.session() as s:
        jobs = s.scalars(select(Job).order_by(Job.id)).all()
        assert [j.status for j in jobs] == ["hazir", "hazir"]
        assert jobs[1].title.endswith("2 😂")  # önceki fikir geçmiş olarak verildi


def test_channel_belongs_to_owner(client):
    signup(client, "a@b.com")
    client.post("/kanallar/yeni", data={"name": "K", "times": "10:00", "csrf": csrf(client, "/kanallar/yeni")})
    other = TestClient(client.app)
    signup(other, "c@d.com")
    with db.session() as s:
        cid = s.scalar(select(Channel.id))
    assert other.get(f"/kanallar/{cid}").status_code == 404
    other.post(f"/kanallar/{cid}/sil", data={"csrf": csrf(other, "/kanallar")})
    with db.session() as s:
        assert s.get(Channel, cid) is not None


def test_login_rate_limit_and_wrong_password(client):
    signup(client, "a@b.com")
    client.post("/cikis", data={"csrf": csrf(client, "/panel")})
    t = csrf(client, "/giris")
    r = client.post("/giris", data={"email": "a@b.com", "password": "yanlis", "csrf": t})
    assert "yanlış" in r.text
    r = client.post("/giris", data={"email": "a@b.com", "password": "sifre1234", "csrf": t}, follow_redirects=False)
    assert r.headers["location"] == "/panel"


def test_script_request_has_rules_and_past():
    req = ai.build_script_request(idea="", characters="", style="meme3d", language="tr", past=["old idea"])
    assert "Türkçe" in req and "old idea" in req and "copyrighted" in req and "watermark" in req.lower()


def test_site_updater_writes_only_site_files_and_keeps_data(tmp_path):
    import io
    import zipfile

    from saas import guncelle

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("repo-branch/shitpost/x.py", "x")
        z.writestr("repo-branch/otoshort_site/saas/app.py", "yeni")
        z.writestr("repo-branch/otoshort_site/.env", "SIZDIRMA")
        z.writestr("repo-branch/otoshort_site/saas_veri/site.db", "bos")
    (tmp_path / ".env").write_text("benim")
    assert guncelle.extract_site(buf.getvalue(), tmp_path) == 1
    assert (tmp_path / "saas" / "app.py").read_text() == "yeni"
    assert (tmp_path / ".env").read_text() == "benim" and not (tmp_path / "saas_veri").exists()
    assert not (tmp_path / "shitpost").exists()


@pytest.fixture
def google_on(monkeypatch):
    from saas import oauth

    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "sec")
    prof = {"sub": "g-123", "email": "yeni@gmail.com", "email_verified": True, "name": "Yeni Kişi"}
    monkeypatch.setattr(oauth, "exchange_code", lambda code, uri: dict(prof))
    return prof


def google_round(c):
    r = c.get("/auth/google", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("https://accounts.google.com/")
    state = re.search(r"state=([^&]+)", r.headers["location"]).group(1)
    return c.get(f"/auth/google/donus?code=abc&state={state}", follow_redirects=False)


def test_google_new_user_must_accept_terms(client, google_on):
    r = google_round(client)
    assert r.headers["location"] == "/kayit/google"
    page = client.get("/kayit/google").text
    assert "yeni@gmail.com" in page
    t = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
    client.post("/kayit/google", data={"csrf": t, "accept": "1"})  # rıza eksik
    with db.session() as s:
        assert s.scalar(select(User).where(User.email == "yeni@gmail.com")) is None
    r = client.post("/kayit/google", data={"csrf": t, "accept": "1", "consent": "1"}, follow_redirects=False)
    assert r.headers["location"] == "/panel"
    with db.session() as s:
        u = s.scalar(select(User).where(User.email == "yeni@gmail.com"))
        assert u.google_sub == "g-123" and u.pw_hash == ""
    assert client.get("/panel").status_code == 200


def test_google_links_existing_email_account(client, google_on):
    signup(client, "yeni@gmail.com")
    client.post("/cikis", data={"csrf": csrf(client, "/panel")})
    r = google_round(client)
    assert r.headers["location"] == "/panel"
    with db.session() as s:
        assert s.scalar(select(User.google_sub).where(User.email == "yeni@gmail.com")) == "g-123"


def test_google_rejects_bad_state(client, google_on):
    client.get("/auth/google", follow_redirects=False)
    r = client.get("/auth/google/donus?code=abc&state=sahte", follow_redirects=False)
    assert r.headers["location"] == "/giris"


def test_google_button_hidden_when_not_configured(client, monkeypatch):
    monkeypatch.setattr(config, "FAKE_AI", False)
    assert "Google ile devam et" not in client.get("/giris").text
    r = client.get("/auth/google", follow_redirects=False)
    assert r.headers["location"] == "/giris"


def test_migration_adds_google_column_to_old_db(tmp_path, monkeypatch):
    import sqlite3

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    path = tmp_path / "eski.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255) UNIQUE, name VARCHAR(100), "
                "pw_hash VARCHAR(255), credits INTEGER, is_admin BOOLEAN, created_at DATETIME)")
    con.execute("INSERT INTO users (email, name, pw_hash, credits, is_admin) VALUES ('a@b.com','A','x',5,0)")
    con.commit(); con.close()
    db.init(f"sqlite:///{path}")
    with db.session() as s:
        u = s.scalar(select(User))
        assert u.credits == 5 and u.google_sub is None and u.ref_code is None and u.ref_rewarded is False


def test_signup_requires_email_verification_and_gives_bonus_once(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SIGNUP_BONUS", 100)
    signup(client, "a@b.com", verify=False)
    assert "verify-bar" in client.get("/panel").text
    assert balance("a@b.com") == 0
    r = client.post("/video/yeni", data={"quality": "lite", "csrf": csrf(client, "/video/yeni")}, follow_redirects=False)
    assert r.headers["location"] == "/panel"  # doğrulanmadan video yok
    link = mail_link(tmp_path, "/dogrula")
    client.get(link)
    assert balance("a@b.com") == 100
    client.get(link)  # ikinci tıklama hediye vermez
    assert balance("a@b.com") == 100
    assert "verify-bar" not in client.get("/panel").text
    assert client.get("/dogrula/bozuk-jeton", follow_redirects=False).status_code == 303


def test_password_reset_flow(client, tmp_path):
    signup(client, "a@b.com")
    client.post("/cikis", data={"csrf": csrf(client, "/panel")})
    r = client.post("/sifremi-unuttum", data={"email": "a@b.com", "csrf": csrf(client, "/sifremi-unuttum")})
    assert "sıfırlama bağlantısı" in r.text
    link = mail_link(tmp_path, "/sifre-yenile")
    page = client.get(link)
    assert "Yeni şifreni belirle" in page.text
    t = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
    r = client.post(link, data={"csrf": t, "password": "yeniSifre99", "password2": "yeniSifre99"}, follow_redirects=False)
    assert r.headers["location"] == "/panel"
    # aynı bağlantı ikinci kez çalışmaz
    assert client.get(link, follow_redirects=False).headers["location"] == "/sifremi-unuttum"
    client.post("/cikis", data={"csrf": csrf(client, "/panel")})
    r = client.post("/giris", data={"email": "a@b.com", "password": "yeniSifre99", "csrf": csrf(client, "/giris")},
                    follow_redirects=False)
    assert r.headers["location"] == "/panel"


def test_forgot_password_does_not_reveal_accounts(client, tmp_path):
    r = client.post("/sifremi-unuttum", data={"email": "yok@b.com", "csrf": csrf(client, "/sifremi-unuttum")})
    assert "sıfırlama bağlantısı" in r.text and last_mail(tmp_path) == ""


def test_dev_email_viewer_only_in_demo(client, tmp_path, monkeypatch):
    signup(client, "a@b.com", verify=False)
    name = sorted((tmp_path / "epostalar").glob("*.html"))[-1].name
    assert client.get(f"/dev/eposta/{name}").status_code == 404
    monkeypatch.setattr(config, "FAKE_AI", True)
    assert "E-postanı doğrula" in client.get(f"/dev/eposta/{name}").text
    assert client.get("/dev/eposta/..%2Fsite.db").status_code == 404


def test_account_profile_password_and_delete(client, tmp_path):
    signup(client, "a@b.com")
    t = csrf(client, "/hesap")
    client.post("/hesap/profil", data={"csrf": t, "name": "Saki", "notify": ""})
    with db.session() as s:
        u = s.scalar(select(User).where(User.email == "a@b.com"))
        assert u.name == "Saki" and u.notify is False
    r = client.post("/hesap/sifre", data={"csrf": t, "current": "yanlis", "password": "yeni12345", "password2": "yeni12345"})
    assert "Mevcut şifren yanlış" in r.text
    client.post("/hesap/sifre", data={"csrf": t, "current": "sifre1234", "password": "yeni12345", "password2": "yeni12345"})
    give("a@b.com", 100)
    client.post("/video/yeni", data={"quality": "lite", "csrf": csrf(client, "/video/yeni")})
    run_queue(ai.FakeAI())
    assert list((tmp_path / "videolar").glob("*.mp4"))
    client.post("/hesap/sil", data={"csrf": csrf(client, "/hesap"), "confirm": "a@b.com"})
    with db.session() as s:
        assert s.scalar(select(User).where(User.email == "a@b.com")) is None
        assert s.scalar(select(Job)).title == ""
    assert not list((tmp_path / "videolar").glob("*.mp4"))
    assert client.get("/panel", follow_redirects=False).status_code == 303
    signup(client, "a@b.com")  # aynı e-postayla yeniden kayıt olunabilir


def test_channel_video_and_credit_notifications(client, tmp_path):
    signup(client, "a@b.com")
    client.post("/kanallar/yeni", data={"name": "Meyveler", "quality": "lite", "times": "09:45",
                                        "csrf": csrf(client, "/kanallar/yeni")})
    tz = ZoneInfo(config.TIMEZONE)
    at = datetime(2026, 10, 13, 9, 50, tzinfo=tz)
    worker.schedule_channels(at)
    worker.schedule_channels(datetime(2026, 10, 13, 9, 55, tzinfo=tz))  # ikinci kez uyarı e-postası yok
    mails = sorted((tmp_path / "epostalar").glob("*.html"))
    assert sum("kredin bitti" in m.read_text() for m in mails) == 1
    give("a@b.com", 100)
    worker.schedule_channels(datetime(2026, 10, 13, 10, 0, tzinfo=tz))
    run_queue(ai.FakeAI())
    assert "yeni videon hazır" in last_mail(tmp_path)


def test_security_headers_and_no_inline_scripts(client):
    r = client.get("/")
    csp = r.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert r.headers["x-frame-options"] == "DENY" and r.headers["x-content-type-options"] == "nosniff"
    signup(client, "a@b.com")
    for url in ["/", "/panel", "/video/yeni", "/kredi", "/hesap", "/kanallar/yeni"]:
        html = client.get(url).text
        # yalnızca dosyadan yüklenen script ya da veri bloğu (JSON-LD) olabilir; satır içi olay yakalayıcı yok
        tags = re.findall(r"<script[^>]*>", html)
        assert all(" src=" in t or 'type="application/ld+json"' in t for t in tags), url
        assert not re.search(r"\son(submit|error|click|load)=", html), url


def test_health_robots_sitemap_manifest(client):
    assert client.get("/saglik").json() == {"ok": True, "queue": 0}
    robots = client.get("/robots.txt").text
    assert "Disallow: /panel" in robots and "Sitemap: http://testserver/sitemap.xml" in robots
    sm = client.get("/sitemap.xml")
    assert sm.headers["content-type"].startswith("application/xml") and "<loc>http://testserver/kayit</loc>" in sm.text
    m = client.get("/manifest.webmanifest").json()
    assert m["start_url"] == "/panel" and all(client.get(i["src"]).status_code == 200 for i in m["icons"])
    assert client.get("/favicon.ico").status_code == 200


def test_index_has_structured_data(client):
    import json

    html = client.get("/").text
    data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
    faq = next(g for g in data["@graph"] if g["@type"] == "FAQPage")
    assert len(faq["mainEntity"]) >= 5 and faq["mainEntity"][0]["acceptedAnswer"]["text"]


def test_backup_creates_copy_and_rotates(tmp_path, monkeypatch):
    import sqlite3

    from saas import yedek

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    src = tmp_path / "site.db"
    with sqlite3.connect(src) as c:
        c.execute("create table t(x)")
        c.execute("insert into t values (42)")
    url = f"sqlite:///{src}"
    for i in range(4):
        out = yedek.backup(url, keep=3, stamp=f"20260101-00000{i}")
    files = sorted((tmp_path / "yedekler").glob("site-*.db"))
    assert len(files) == 3 and files[-1] == out
    with sqlite3.connect(out) as c:
        assert c.execute("select x from t").fetchone() == (42,)
    assert yedek.backup("postgresql://x/y") is None


def approve_topups(admin_client):
    page = admin_client.get("/admin").text
    for tid in re.findall(r"/admin/yukleme/(\d+)/onayla", page):
        admin_client.post(f"/admin/yukleme/{tid}/onayla", data={"csrf": csrf(admin_client, "/admin")})


def notify_topup(c):
    c.post("/kredi/bildirim", data={"package": "0", "sender_name": "X Y", "accept": "1", "csrf": csrf(c, "/kredi")})


def test_referral_rewards_both_once_after_first_topup(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REFERRAL_PCT", 15)
    monkeypatch.setattr(config, "REFERRAL_FRIEND_PCT", 10)
    signup(client, "a@b.com")
    page = client.get("/davet").text
    code = re.search(r"/d/([A-Z0-9]+)", page).group(1)
    friend = TestClient(client.app)
    r = friend.get(f"/d/{code}", follow_redirects=False)
    assert r.headers["location"] == "/kayit" and "Davetle geldin" in friend.get("/kayit").text
    signup(friend, "f@b.com")
    with db.session() as s:
        a_id = s.scalar(select(User.id).where(User.email == "a@b.com"))
        assert s.scalar(select(User.referred_by).where(User.email == "f@b.com")) == a_id
    assert balance("a@b.com") == 0 and balance("f@b.com") == 0  # kayıtta bedava kredi yok
    admin = TestClient(client.app)
    signup(admin, "admin@x.com")
    notify_topup(friend)
    approve_topups(admin)
    tl, cr = config.PACKAGES[0]
    ref, bonus = cr * 15 // 100, cr * 10 // 100  # ödül yüklemenin yüzdesi
    assert balance("a@b.com") == ref and balance("f@b.com") == cr + bonus
    notify_topup(friend)
    approve_topups(admin)  # ikinci yüklemede ödül tekrar verilmez
    assert balance("a@b.com") == ref and balance("f@b.com") == 2 * cr + bonus
    assert "Davet ödülü" in client.get("/kredi").text
    page = client.get("/davet").text
    assert re.search(r'data-count="1"', page) and re.search(rf'data-count="{ref}"', page)


def test_invalid_or_own_invite_code(client):
    signup(client, "a@b.com")
    code = re.search(r"/d/([A-Z0-9]+)", client.get("/davet").text).group(1)
    other = TestClient(client.app)
    other.get("/d/YANLIS99")
    assert "Davetle geldin" not in other.get("/kayit").text
    with db.session() as s:  # kendini davet etmek bağlantı kurmaz
        from saas import growth

        me = s.scalar(select(User).where(User.email == "a@b.com"))
        growth.attach_referrer(s, me, code)
        assert me.referred_by is None


def test_promo_codes(client):
    from datetime import timedelta

    from saas.models import PromoCode, now

    admin = TestClient(client.app)
    signup(admin, "admin@x.com")
    admin.post("/admin/kod", data={"code": "acilis-100", "amount": "100", "max_uses": "1", "days": "7",
                                   "csrf": csrf(admin, "/admin")})
    assert "ACILIS100" in admin.get("/admin").text
    signup(client, "a@b.com")
    t = csrf(client, "/kredi")
    assert "100 kredi yüklendi" in client.post("/kredi/kod", data={"code": "Acilis100", "csrf": t}).text
    assert balance("a@b.com") == 100
    assert "zaten kullandın" in client.post("/kredi/kod", data={"code": "ACILIS100", "csrf": t}).text
    b = TestClient(client.app)
    signup(b, "b@b.com")
    assert "hakkı dolmuş" in b.post("/kredi/kod", data={"code": "ACILIS100", "csrf": csrf(b, "/kredi")}).text
    with db.session() as s:
        s.add(PromoCode(code="ESKI", credits=10, expires_at=now() - timedelta(days=1)))
        s.add(PromoCode(code="KAPALI", credits=10, active=False))
    tb = csrf(b, "/kredi")
    assert "süresi dolmuş" in b.post("/kredi/kod", data={"code": "ESKI", "csrf": tb}).text
    assert "geçersiz" in b.post("/kredi/kod", data={"code": "KAPALI", "csrf": tb}).text
    assert "geçersiz" in b.post("/kredi/kod", data={"code": "YOKBOYLE", "csrf": tb}).text
    assert balance("b@b.com") == 0
    u = TestClient(client.app)
    signup(u, "u@b.com", verify=False)  # doğrulanmamış hesap kod kullanamaz
    admin.post("/admin/kod", data={"code": "SINIRSIZ", "amount": "5", "max_uses": "0", "days": "0",
                                   "csrf": csrf(admin, "/admin")})
    u.post("/kredi/kod", data={"code": "SINIRSIZ", "csrf": csrf(u, "/kredi")})
    assert balance("u@b.com") == 0


def test_low_credit_bar(client):
    signup(client, "a@b.com")
    assert "Kredin azaldı" in client.get("/panel").text
    assert "Kredin azaldı" not in client.get("/kredi").text
    give("a@b.com", 100)
    assert "Kredin azaldı" not in client.get("/panel").text


def test_videos_page_filters_search_and_pages(client):
    signup(client, "a@b.com")
    give("a@b.com", 2000)
    with db.session() as s:
        uid = s.scalar(select(User.id).where(User.email == "a@b.com"))
        for i in range(30):
            s.add(Job(user_id=uid, idea=f"fikir {i}", title=("Kedi videosu" if i == 3 else f"Video {i}"),
                      status="hazir" if i % 3 else "hata"))
    page = client.get("/videolar").text
    assert "Videolarım" in page and "1 / 2" in page
    assert len(re.findall(r'class="vcard', page)) == 24
    assert len(re.findall(r'class="vcard', client.get("/videolar?sayfa=2").text)) == 6
    hata = client.get("/videolar?durum=hata").text
    assert len(re.findall(r'class="vcard', hata)) == 10
    found = client.get("/videolar?q=kedi").text
    assert "Kedi videosu" in found and len(re.findall(r'class="vcard', found)) == 1
    other = TestClient(client.app)
    signup(other, "o@b.com")
    assert "Kedi videosu" not in other.get("/videolar?q=kedi").text  # başkasının videoları görünmez


def test_regenerate_same_settings_and_prefill(client):
    signup(client, "a@b.com")
    give("a@b.com", 500)
    t = csrf(client, "/video/yeni")
    r = client.post("/video/yeni", data={"idea": "Kedi toplantıda", "characters": "turuncu kedi", "style": "anime",
                                         "language": "en", "quality": "lite", "csrf": t}, follow_redirects=False)
    jid = int(r.headers["location"].rsplit("/", 1)[1])
    r = client.post(f"/video/{jid}/tekrar", data={"csrf": t}, follow_redirects=False)
    new_id = int(r.headers["location"].rsplit("/", 1)[1])
    with db.session() as s:
        new = s.get(Job, new_id)
        assert new_id != jid and (new.idea, new.style, new.language, new.quality) == ("Kedi toplantıda", "anime", "en", "lite")
    assert balance("a@b.com") == 500 - 2 * config.QUALITIES["lite"]["credits"]
    pre = client.get(f"/video/yeni?from={jid}").text
    assert "turuncu kedi" in pre and 'value="anime" data-label="Anime" checked' in pre and "ayarlarıyla dolduruldu" in pre
    other = TestClient(client.app)
    signup(other, "o@b.com")
    give("o@b.com", 500)
    assert other.post(f"/video/{jid}/tekrar", data={"csrf": csrf(other, "/panel")}).status_code == 404
    assert "turuncu kedi" not in other.get(f"/video/yeni?from={jid}").text


def test_channel_make_now(client):
    signup(client, "a@b.com")
    give("a@b.com", 200)
    t = csrf(client, "/kanallar/yeni")
    client.post("/kanallar/yeni", data={"name": "Meyveler", "topic": "konuşan meyveler", "style": "cartoon",
                                        "language": "tr", "quality": "fast", "times": "09:00", "csrf": t})
    with db.session() as s:
        cid = s.scalar(select(Channel.id))
    for _ in range(2):  # art arda iki kez basılsa da çakışmaz
        r = client.post(f"/kanallar/{cid}/simdi", data={"csrf": t}, follow_redirects=False)
        assert r.headers["location"].startswith("/video/")
    with db.session() as s:
        jobs = s.scalars(select(Job).where(Job.channel_id == cid)).all()
        assert len(jobs) == 2 and all(j.slot.startswith("elle ") and j.idea == "konuşan meyveler" for j in jobs)
    assert "· elle" in client.get(f"/kanallar/{cid}").text
    assert balance("a@b.com") == 200 - 2 * config.QUALITIES["fast"]["credits"]


def test_ai_ideas_endpoint(client):
    signup(client, "a@b.com")
    client.app.state.generator = ai.FakeAI()
    t = csrf(client, "/video/yeni")
    d = client.post("/api/fikirler", data={"topic": "", "language": "tr", "csrf": t}).json()
    assert len(d["ideas"]) == 4 and all(isinstance(i, str) and i for i in d["ideas"])
    for _ in range(12):
        r = client.post("/api/fikirler", data={"csrf": t})
    assert r.status_code == 429 and "error" in r.json()

    class Broken(ai.FakeAI):
        def ideas(self, **_):
            raise RuntimeError("api kapalı")

    other = TestClient(client.app)
    signup(other, "o@b.com")
    client.app.state.generator = Broken()
    r = other.post("/api/fikirler", data={"csrf": csrf(other, "/video/yeni")})
    assert r.status_code == 503


def test_real_ai_ideas_parses_json():
    from types import SimpleNamespace

    class Models:
        def generate_content(self, **kw):
            assert "Theme from the user: uzay" in kw["contents"] and "Avoid these earlier ideas" in kw["contents"]
            return SimpleNamespace(text='{"ideas": [" Bir ", "", "İki", "Üç", "Dört", "Beş"]}')

    real = ai.RealAI(client=SimpleNamespace(models=Models()))
    assert real.ideas(topic="uzay", language="tr", past=["eski"]) == ["Bir", "İki", "Üç", "Dört"]


def test_admin_daily_stats_and_profit(client):
    from saas.models import TopUp, now

    admin = TestClient(client.app)
    signup(admin, "admin@x.com")
    signup(client, "a@b.com")
    with db.session() as s:
        uid = s.scalar(select(User.id).where(User.email == "a@b.com"))
        s.add(TopUp(user_id=uid, amount_tl=500, credits=550, sender_name="A", status="onaylandi", decided_at=now()))
        for q in ("fast", "fast", "standard"):
            s.add(Job(user_id=uid, quality=q, status="hazir", finished_at=now()))
        s.add(Job(user_id=uid, quality="fast", status="hata"))
    page = admin.get("/admin").text
    cost = round((0.80 * 2 + 3.20) * config.USD_TRY)
    assert "500 ₺" in page and f"{cost} ₺" in page and f"{500 - cost} ₺" in page
    assert "%25" in page  # 4 videodan 1'i başarısız
    assert page.count('class="bar"') == 3 * 14


def test_index_calculator_and_faq(client):
    html = client.get("/").text
    assert "/fiyatlar" in html and "Arkadaşımı davet edersem" in html and "Diğer sorular" in html
    assert "swipe-m" in html and "plan-cards swipe-m" in html  # telefonda yana kayan kartlar
    page = client.get("/fiyatlar").text  # fiyat ayrıntıları ve hesaplayıcı ayrı sayfada
    assert "data-calc" in page and 'data-packages=\'[[250, 250]' in page and "Her ek saniye" in page
    assert "Abonelikler nasıl çalışıyor" in page
    _assert_english(TestClient(client.app).get("/en/fiyatlar").text, "/en/fiyatlar")


def _make_png() -> bytes:
    import subprocess
    import tempfile

    import imageio_ffmpeg

    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/x.png"
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-f", "lavfi", "-i",
                        "color=c=orange:s=64x64", "-frames:v", "1", out], check=True)
        return open(out, "rb").read()


PNG_1PX = _make_png()


def test_reference_image_flow(client, tmp_path):
    signup(client, "a@b.com")
    give("a@b.com", 500)
    t = csrf(client, "/video/yeni")
    r = client.post("/video/yeni", data={"idea": "maskot", "style": "cartoon", "language": "tr", "quality": "fast",
                                         "csrf": t}, files={"ref": ("maskot.png", PNG_1PX, "image/png")},
                    follow_redirects=False)
    jid = int(r.headers["location"].rsplit("/", 1)[1])
    with db.session() as s:
        ref = s.get(Job, jid).ref_image
    assert ref.endswith(".png") and (tmp_path / "referanslar" / ref).read_bytes().startswith(b"\x89PNG")
    assert client.get(f"/referans/{ref}").status_code == 200
    gen = ai.FakeAI()
    run_queue(gen)
    assert gen.last_refs and gen.last_refs[0].name == ref.split("/")[1]
    # benzerini üret görseli de taşır
    r = client.post(f"/video/{jid}/tekrar", data={"csrf": t}, follow_redirects=False)
    with db.session() as s:
        assert s.get(Job, int(r.headers["location"].rsplit("/", 1)[1])).ref_image == ref
    # başkası göremez
    other = TestClient(client.app)
    signup(other, "o@b.com")
    assert other.get(f"/referans/{ref}").status_code == 404
    # görsel olmayan dosya reddedilir, kredi düşmez
    before = balance("a@b.com")
    r = client.post("/video/yeni", data={"idea": "x", "csrf": t}, files={"ref": ("a.png", b"not an image", "image/png")})
    assert "Sadece PNG, JPG ya da WEBP" in r.text and balance("a@b.com") == before
    # başkasının görseli "koru" alanıyla kullanılamaz
    give("o@b.com", 100)
    r = other.post("/video/yeni", data={"idea": "x", "ref_keep": ref, "csrf": csrf(other, "/video/yeni")},
                   follow_redirects=False)
    with db.session() as s:
        assert s.get(Job, int(r.headers["location"].rsplit("/", 1)[1])).ref_image == ""


def test_channel_reference_copied_to_scheduled_jobs(client):
    signup(client, "a@b.com")
    give("a@b.com", 500)
    t = csrf(client, "/kanallar/yeni")
    client.post("/kanallar/yeni", data={"name": "Maskot", "topic": "x", "times": "09:00", "csrf": t},
                files={"ref": ("m.png", PNG_1PX, "image/png")})
    with db.session() as s:
        ch = s.scalar(select(Channel))
        ref, cid = ch.ref_image, ch.id
    assert ref
    worker.schedule_channels(datetime(2026, 1, 5, 9, 1, tzinfo=ZoneInfo(config.TIMEZONE)))
    with db.session() as s:
        assert s.scalar(select(Job.ref_image).where(Job.channel_id == cid)) == ref
    client.post(f"/kanallar/{cid}", data={"name": "Maskot", "times": "09:00", "ref_remove": "1", "csrf": t})
    with db.session() as s:
        assert s.get(Channel, cid).ref_image == ""


def test_provider_config_and_refs(monkeypatch):
    q = dict(config.QUALITIES["lite"])
    monkeypatch.setitem(config.QUALITIES, "lite", {**q, "model": "fal:fal-ai/wan/v3/text-to-video", "ref_model": ""})
    assert config.provider("lite") == ("fal", "fal-ai/wan/v3/text-to-video") and not config.supports_refs("lite")
    assert config.provider("standard")[0] == "google" and config.supports_refs("standard")


def test_veo_sends_reference_images(tmp_path):
    from types import SimpleNamespace

    seen = {}

    class Models:
        def generate_videos(self, **kw):
            seen.update(kw)
            video = SimpleNamespace(save=lambda p: open(p, "wb").write(b"mp4"))
            return SimpleNamespace(done=True, error=None, response=SimpleNamespace(
                generated_videos=[SimpleNamespace(video=video)]))

    ref = tmp_path / "r.png"
    ref.write_bytes(PNG_1PX)
    real = ai.RealAI(client=SimpleNamespace(models=Models(), files=SimpleNamespace(download=lambda file: None)))
    real.make_video(prompt="p", quality="standard", out=tmp_path / "o.mp4", refs=[ref])
    imgs = seen["config"].reference_images
    assert len(imgs) == 1 and imgs[0].image.image_bytes == PNG_1PX and (tmp_path / "o.mp4").exists()


def test_fal_video_flow_and_content_block(tmp_path, monkeypatch):
    from types import SimpleNamespace

    q = dict(config.QUALITIES["lite"])
    monkeypatch.setitem(config.QUALITIES, "lite", {**q, "model": "fal:fal-ai/kling/v3", "args": '{"duration": "5"}'})
    calls = []

    def resp(code=200, data=None, text="", chunks=()):
        return SimpleNamespace(status_code=code, json=lambda: data, text=text or str(data),
                               iter_content=lambda n: iter(chunks), __enter__=None)

    class Dl:
        status_code, text = 200, ""

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def iter_content(self, n):
            return iter([b"video", b"bytes"])

    class Http:
        polls = 0

        def post(self, url, headers, json, timeout):
            calls.append(("post", url, json))
            assert headers["Authorization"] == "Key k"
            return resp(data={"status_url": "S", "response_url": "R"})

        def get(self, url, headers=None, timeout=None, stream=False):
            calls.append(("get", url))
            if url == "S":
                Http.polls += 1
                return resp(data={"status": "IN_PROGRESS" if Http.polls < 2 else "COMPLETED"})
            if url == "R":
                return resp(data={"video": {"url": "https://cdn/v.mp4"}})
            return Dl()

    out = ai.FalVideo(session=Http(), key="k").make(quality="lite", model="fal-ai/kling/v3", prompt="p",
                                                    out=tmp_path / "v.mp4", refs=[], poll_s=0)
    assert out.read_bytes() == b"videobytes"
    post = calls[0]
    assert post[1] == "https://queue.fal.run/fal-ai/kling/v3" and post[2]["duration"] == "5" and post[2]["aspect_ratio"] == "9:16"

    class Blocked(Http):
        def post(self, url, headers, json, timeout):
            return resp(422, text='{"detail": "content policy violation"}')

    with pytest.raises(ai.ContentBlocked):
        ai.FalVideo(session=Blocked(), key="k").make(quality="lite", model="m", prompt="p", out=tmp_path / "x.mp4",
                                                     refs=[], poll_s=0)


def test_subtitles_burned_and_raw_kept(client, tmp_path):
    signup(client, "a@b.com")
    give("a@b.com", 500)
    t = csrf(client, "/video/yeni")
    r = client.post("/video/yeni", data={"idea": "x", "quality": "lite", "subtitles": "1", "csrf": t},
                    follow_redirects=False)
    jid = int(r.headers["location"].rsplit("/", 1)[1])
    run_queue(ai.FakeAI())
    with db.session() as s:
        job = s.get(Job, jid)
        assert job.status == "hazir" and job.subtitles and job.raw_file == f"{jid}-ham.mp4"
    assert (tmp_path / "videolar" / f"{jid}-ham.mp4").exists()
    page = client.get(f"/video/{jid}").text
    assert "Altyazısız indir" in page and "altyazılı" in page
    r = client.get(f"/video/{jid}/dosya?indir=1&ham=1")
    assert r.status_code == 200 and "altyazisiz" in r.headers["content-disposition"]


def test_subtitle_failure_keeps_video(client):
    class NoSubs(ai.FakeAI):
        def transcribe(self, **_):
            raise RuntimeError("döküm yapılamadı")

    signup(client, "a@b.com")
    give("a@b.com", 500)
    client.post("/video/yeni", data={"idea": "x", "quality": "lite", "subtitles": "1", "csrf": csrf(client, "/video/yeni")})
    run_queue(NoSubs())
    with db.session() as s:
        job = s.scalar(select(Job))
        assert job.status == "hazir" and job.raw_file == "" and balance("a@b.com") == 500 - job.cost


def test_build_ass_escapes_and_skips_empty():
    from saas import media

    ass = media.build_ass([{"start": 0, "end": 1.5, "text": "Merhaba {\\\\an8}dünya"},
                           {"start": 2, "end": 2, "text": "boş süre"}, {"start": 3, "end": 4, "text": "  "}])
    lines = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    assert len(lines) == 1 and "0:00:01.50" in lines[0] and "{" not in lines[0].split(",,", 1)[1]
    assert media.burn_subtitles(None, [{"start": 0, "end": 1, "text": " "}]) is None


def test_real_ai_transcribe_parses_segments(tmp_path):
    from types import SimpleNamespace

    class Models:
        def generate_content(self, **kw):
            assert "Turkish" in kw["contents"][1] or "Türkçe" in kw["contents"][1]
            return SimpleNamespace(text='{"segments": [{"start": 0.1, "end": 1.2, "text": "Selam"}, '
                                        '{"start": 1.3, "end": 2, "text": " "}]}')

    v = tmp_path / "v.mp4"
    v.write_bytes(b"mp4")
    segs = ai.RealAI(client=SimpleNamespace(models=Models())).transcribe(video=v, language="tr")
    assert segs == [{"start": 0.1, "end": 1.2, "text": "Selam"}]


def test_explore_gallery_opt_in_and_moderation(client):
    signup(client, "a@b.com")
    give("a@b.com", 500)
    t = csrf(client, "/video/yeni")
    client.post("/video/yeni", data={"idea": "x", "quality": "lite", "csrf": t})
    run_queue(ai.FakeAI())
    with db.session() as s:
        jid = s.scalar(select(Job.id))
    anon = TestClient(client.app)
    assert anon.get(f"/kesfet/{jid}/video").status_code == 404  # paylaşılmadan herkese açık değil
    assert "Galeri yakında dolacak" in anon.get("/kesfet").text
    other = TestClient(client.app)
    signup(other, "o@b.com")
    assert other.post(f"/video/{jid}/kesfet", data={"csrf": csrf(other, "/panel")}).status_code == 404
    import html

    assert "Keşfet'te yayında" in html.unescape(client.post(f"/video/{jid}/kesfet", data={"csrf": t}).text)
    page = anon.get("/kesfet").text
    assert f'data-play="/kesfet/{jid}/video"' in page and "a@b.com" not in page
    assert anon.get(f"/kesfet/{jid}/video").status_code == 200 and anon.get(f"/kesfet/{jid}/kapak").status_code == 200
    assert f"/kesfet/{jid}/video" in anon.get("/").text  # ana sayfada da görünür
    admin = TestClient(client.app)
    signup(admin, "admin@x.com")
    ta = csrf(admin, "/admin")
    admin.post(f"/admin/kesfet/{jid}/one-cikar", data={"csrf": ta})
    assert "Öne çıkan" in anon.get("/kesfet").text
    admin.post(f"/admin/kesfet/{jid}/kaldir", data={"csrf": ta})
    assert anon.get(f"/kesfet/{jid}/video").status_code == 404 and f"/kesfet/{jid}/video" not in anon.get("/").text
    assert "<loc>http://testserver/kesfet</loc>" in anon.get("/sitemap.xml").text


# --- otomatik paylaşım ---
class FakeResp:
    def __init__(self, data=None, status=200, headers=None):
        self.data, self.status_code, self.headers = data or {}, status, headers or {}
        self.text = str(self.data)

    def json(self):
        return self.data


class FakeHTTP:
    """URL parçasına göre sırayla yanıt veren sahte requests oturumu; çağrıları kaydeder."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def _go(self, method, url, **kw):
        self.calls.append((method, url, kw))
        for (m, part), answers in self.routes.items():
            if m == method and part in url:
                return answers.pop(0) if len(answers) > 1 else answers[0]
        raise AssertionError(f"beklenmeyen istek: {method} {url}")

    def get(self, url, **kw):
        return self._go("GET", url, **kw)

    def post(self, url, **kw):
        return self._go("POST", url, **kw)

    def put(self, url, **kw):
        if hasattr(kw.get("data"), "read"):
            kw["data"] = kw["data"].read()
        return self._go("PUT", url, **kw)


def test_secretbox_roundtrip_and_tamper():
    from saas import secretbox

    sealed = secretbox.seal("ya29.gizli-jeton")
    assert "gizli" not in sealed and secretbox.open_(sealed) == "ya29.gizli-jeton"
    assert secretbox.seal("x") != secretbox.seal("x")  # her seferinde farklı nonce
    import base64

    raw = bytearray(base64.urlsafe_b64decode(sealed[3:]))
    raw[20] ^= 1  # şifreli metinde tek bit değişse bile açılmaz
    for bad in ["v1:" + base64.urlsafe_b64encode(bytes(raw)).decode(), "v1:kısa", "v1:QUJD", "v0:x"]:
        with pytest.raises(secretbox.SecretError):
            secretbox.open_(bad)
    assert secretbox.open_(secretbox.seal("")) == ""


def _demo_connect(c, platform):
    r = c.get(f"/baglan/{platform}", follow_redirects=False)
    assert r.status_code == 303 and f"/baglan/{platform}/donus?code=demo" in r.headers["location"]
    return c.get(r.headers["location"])


def test_demo_connect_and_channel_autopublish(client, monkeypatch):
    from saas import publisher
    from saas.models import Publication, SocialAccount

    monkeypatch.setattr(config, "FAKE_AI", True)
    signup(client, "a@b.com")
    give("a@b.com", 500)
    page = client.get("/baglantilar").text
    assert "YouTube hesabını bağla" in page and "Demo modu" in page
    assert "Demo · YouTube" in _demo_connect(client, "youtube").text
    with db.session() as s:
        acc = s.scalar(select(SocialAccount))
        assert acc.platform == "youtube" and "demo" not in acc.access_enc  # jeton şifreli saklanır
    # kanal formunda bağlı platform seçilebilir, bağlı olmayan "bağla" bağlantısı
    form = client.get("/kanallar/yeni").text
    assert 'name="pub_youtube"' in form and 'name="pub_tiktok"' not in form
    client.post("/kanallar/yeni", data={"name": "K", "quality": "lite", "times": "10:00", "pub_youtube": "1",
                                        "pub_tiktok": "1", "csrf": csrf(client, "/kanallar/yeni")})
    with db.session() as s:
        ch = s.scalar(select(Channel))
        assert ch.publish_to == "youtube tiktok"
    assert 'name="pub_youtube" value="1" checked' in client.get(f"/kanallar/{ch.id}").text
    client.post(f"/kanallar/{ch.id}/simdi", data={"csrf": csrf(client, "/kanallar")})
    run_queue(ai.FakeAI())
    with db.session() as s:
        pubs = s.scalars(select(Publication)).all()
        assert [(p.platform, p.status) for p in pubs] == [("youtube", "bekliyor")]  # TikTok bağlı değil
        jid = pubs[0].job_id
    pid = publisher.claim()
    assert pid and publisher.claim() is None
    publisher.run(pid)
    with db.session() as s:
        assert s.get(Publication, pid).status == "yayinda"
    page = client.get(f"/video/{jid}").text
    assert "Yayında" in page and f"/video/{jid}/yayinla/tiktok" not in page
    assert "Yayında" in client.get("/baglantilar").text
    # bağlantıyı kaldır
    client.post("/baglanti/youtube/kaldir", data={"csrf": csrf(client, "/baglantilar")})
    with db.session() as s:
        assert s.scalar(select(SocialAccount)) is None


def test_connect_rejects_bad_state_and_unconfigured(client, monkeypatch):
    from saas.models import SocialAccount

    signup(client, "a@b.com")
    r = client.get("/baglan/tiktok", follow_redirects=False)  # anahtar yok, demo değil
    assert r.headers["location"] == "/baglantilar"
    assert "Çok yakında" in client.get("/baglantilar").text
    monkeypatch.setattr(config, "FAKE_AI", True)
    client.get("/baglan/youtube", follow_redirects=False)
    assert "tamamlanmadı" in client.get("/baglan/youtube/donus?code=demo&state=sahte").text
    assert "tamamlanmadı" in client.get("/baglan/youtube/donus?error=access_denied").text
    with db.session() as s:
        assert s.scalar(select(SocialAccount)) is None


def test_publish_single_video_retry_and_ownership(client, monkeypatch):
    from saas import publisher
    from saas.models import Publication

    monkeypatch.setattr(config, "FAKE_AI", True)
    signup(client, "a@b.com")
    give("a@b.com", 500)
    t = csrf(client, "/video/yeni")
    client.post("/video/yeni", data={"idea": "x", "quality": "lite", "csrf": t})
    run_queue(ai.FakeAI())
    with db.session() as s:
        jid = s.scalar(select(Job.id))
    assert "/baglantilar" in client.get(f"/video/{jid}").text  # bağlı değil → bağla
    _demo_connect(client, "tiktok")
    assert f"/video/{jid}/yayinla/tiktok" in client.get(f"/video/{jid}").text
    other = TestClient(client.app)
    signup(other, "o@b.com")
    assert other.post(f"/video/{jid}/yayinla/tiktok", data={"csrf": csrf(other, "/panel")}).status_code == 404
    assert "sıraya alındı" in client.post(f"/video/{jid}/yayinla/tiktok", data={"csrf": t}).text
    assert "zaten" in client.post(f"/video/{jid}/yayinla/tiktok", data={"csrf": t}).text
    # platform hatası: tekrar denenir, sonra hata olur ve kullanıcı yeniden sıraya alabilir
    monkeypatch.setattr(social_mod().DemoClient, "publish", lambda *a, **k: (_ for _ in ()).throw(ConnectionError("x")))
    pid = publisher.claim()
    publisher.run(pid)
    with db.session() as s:
        p = s.get(Publication, pid)
        assert (p.status, p.attempts) == ("bekliyor", 1)
    assert publisher.claim() is None  # hemen değil, biraz sonra tekrar denenir
    for _ in range(publisher.MAX_ATTEMPTS - 1):
        with db.session() as s:
            s.get(Publication, pid).status = "yukleniyor"
        publisher.run(pid)
    with db.session() as s:
        p = s.get(Publication, pid)
        assert p.status == "hata" and p.error
    assert other.post(f"/yayin/{pid}/tekrar", data={"csrf": csrf(other, "/panel")}).status_code == 404
    client.post(f"/yayin/{pid}/tekrar", data={"csrf": t})
    with db.session() as s:
        p = s.get(Publication, pid)
        assert (p.status, p.attempts, p.error) == ("bekliyor", 0, "")


def social_mod():
    from saas import social

    return social


def test_media_link_is_signed(client):
    from saas import tokens

    signup(client, "a@b.com")
    give("a@b.com", 100)
    client.post("/video/yeni", data={"idea": "x", "quality": "lite", "csrf": csrf(client, "/video/yeni")})
    run_queue(ai.FakeAI())
    with db.session() as s:
        jid = s.scalar(select(Job.id))
    anon = TestClient(client.app)
    assert anon.get(f"/yayin/dosya/{tokens.make_media(jid)}").status_code == 200
    assert anon.get(f"/yayin/dosya/{tokens.make_media(jid)}x").status_code == 404
    assert anon.get(f"/yayin/dosya/{jid}").status_code == 404


def _post():
    return social_mod().Post(title="Kedi <şef> pizza yapıyor", caption="Çok komik\n\n#kedi #ai", tags=["kedi", "ai"])


def test_youtube_client_connect_publish_and_refresh(tmp_path, monkeypatch):
    from saas import social

    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "sec")
    http = FakeHTTP({
        ("POST", "oauth2.googleapis.com/token"): [FakeResp({"access_token": "A1", "refresh_token": "R1", "expires_in": 3599}),
                                                  FakeResp({"access_token": "A2", "expires_in": 3599})],
        ("GET", "youtube/v3/channels"): [FakeResp({"items": [{"id": "UC1", "snippet": {"title": "Kanalım"}}]})],
        ("POST", "upload/youtube/v3/videos"): [FakeResp(headers={"Location": "https://up.example/1"})],
        ("PUT", "up.example/1"): [FakeResp({"id": "vid123"})],
    })
    yt = social.client("youtube", http)
    url = yt.auth_url("https://x/baglan/youtube/donus", "st")
    assert "access_type=offline" in url and "youtube.upload" in url and "state=st" in url
    acc = yt.exchange("code", "https://x/baglan/youtube/donus")
    assert (acc.name, acc.remote_id, acc.access, acc.refresh) == ("Kanalım", "UC1", "A1", "R1")
    v = tmp_path / "v.mp4"
    v.write_bytes(b"video")
    rid, link = yt.publish("A1", "UC1", v, _post())
    assert (rid, link) == ("vid123", "https://youtube.com/shorts/vid123")
    meta = [c for c in http.calls if c[0] == "POST" and "upload" in c[1]][0][2]["json"]
    assert meta["snippet"]["title"] == "Kedi şef pizza yapıyor #Shorts" and meta["status"]["containsSyntheticMedia"]
    assert [c for c in http.calls if c[0] == "PUT"][0][2]["data"] == b"video"
    assert yt.refresh("R1") == ("A2", 3599, "R1")
    http2 = FakeHTTP({("GET", "youtube/v3/channels"): [FakeResp({"items": []})],
                      ("POST", "token"): [FakeResp({"access_token": "A"})]})
    with pytest.raises(social.PublishError, match="kanal"):
        social.client("youtube", http2).exchange("c", "r")


def test_publisher_refreshes_expiring_token(client, monkeypatch):
    from datetime import timedelta

    from saas import publisher, secretbox
    from saas.models import Publication, SocialAccount, now

    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "sec")
    signup(client, "a@b.com")
    give("a@b.com", 100)
    client.post("/video/yeni", data={"idea": "x", "quality": "lite", "csrf": csrf(client, "/video/yeni")})
    run_queue(ai.FakeAI())
    with db.session() as s:
        job = s.scalar(select(Job))
        s.add(SocialAccount(user_id=job.user_id, platform="youtube", name="K", remote_id="UC1",
                            access_enc=secretbox.seal("ESKI"), refresh_enc=secretbox.seal("R1"),
                            expires_at=now() + timedelta(minutes=2)))
        s.flush()
        assert publisher.queue(s, job, ["youtube", "tiktok", "yok"]) == ["youtube"]
    http = FakeHTTP({
        ("POST", "oauth2.googleapis.com/token"): [FakeResp({"access_token": "YENI", "expires_in": 3600})],
        ("POST", "upload/youtube/v3/videos"): [FakeResp(headers={"Location": "https://up.example/2"})],
        ("PUT", "up.example/2"): [FakeResp({"id": "v9"})],
    })
    pid = publisher.claim()
    publisher.run(pid, http)
    with db.session() as s:
        p, acc = s.get(Publication, pid), s.scalar(select(SocialAccount))
        assert (p.status, p.url) == ("yayinda", "https://youtube.com/shorts/v9")
        assert secretbox.open_(acc.access_enc) == "YENI" and secretbox.open_(acc.refresh_enc) == "R1"
    upload = [c for c in http.calls if "upload" in c[1]][0]
    assert upload[2]["headers"]["Authorization"] == "Bearer YENI"


def test_tiktok_client_publish_and_failure(tmp_path, monkeypatch):
    from saas import social

    monkeypatch.setattr(config, "TIKTOK_CLIENT_KEY", "k")
    monkeypatch.setattr(config, "TIKTOK_CLIENT_SECRET", "s")
    monkeypatch.setattr(social.TikTok, "poll_s", 0)
    v = tmp_path / "v.mp4"
    v.write_bytes(b"12345")
    routes = lambda final: {  # noqa: E731
        ("POST", "oauth/token"): [FakeResp({"access_token": "T", "open_id": "o1", "refresh_token": "TR", "expires_in": 86400})],
        ("GET", "user/info"): [FakeResp({"data": {"user": {"display_name": "Kedici"}}})],
        ("POST", "creator_info/query"): [FakeResp({"data": {"privacy_level_options": ["SELF_ONLY", "PUBLIC_TO_EVERYONE"]}})],
        ("POST", "video/init"): [FakeResp({"data": {"publish_id": "p1", "upload_url": "https://tt.up/1"}})],
        ("PUT", "tt.up/1"): [FakeResp()],
        ("POST", "status/fetch"): [FakeResp({"data": {"status": "PROCESSING_UPLOAD"}}), FakeResp({"data": final})],
    }
    http = FakeHTTP(routes({"status": "PUBLISH_COMPLETE"}))
    tt = social.client("tiktok", http)
    assert "video.publish" in tt.auth_url("r", "s")
    acc = tt.exchange("c", "r")
    assert (acc.name, acc.remote_id, acc.refresh) == ("Kedici", "o1", "TR")
    assert tt.publish("T", "o1", v, _post()) == ("p1", "")
    init = [c for c in http.calls if "video/init" in c[1]][0][2]["json"]
    assert init["post_info"]["is_aigc"] and init["post_info"]["privacy_level"] == "PUBLIC_TO_EVERYONE"
    assert init["source_info"]["video_size"] == 5
    put = [c for c in http.calls if c[0] == "PUT"][0][2]
    assert put["headers"]["Content-Range"] == "bytes 0-4/5"
    bad = social.client("tiktok", FakeHTTP(routes({"status": "FAILED", "fail_reason": "spam_risk"})))
    with pytest.raises(social.PublishError, match="spam_risk"):
        bad.publish("T", "o1", v, _post())


def test_instagram_client_needs_https_and_publishes(tmp_path, monkeypatch):
    from saas import social

    monkeypatch.setattr(config, "INSTAGRAM_APP_ID", "i")
    monkeypatch.setattr(config, "INSTAGRAM_APP_SECRET", "s")
    monkeypatch.setattr(social.Instagram, "poll_s", 0)
    v = tmp_path / "v.mp4"
    v.write_bytes(b"x")
    http = FakeHTTP({
        ("POST", "api.instagram.com/oauth/access_token"): [FakeResp({"access_token": "S", "user_id": 5})],
        ("GET", "graph.instagram.com/access_token"): [FakeResp({"access_token": "L", "expires_in": 5184000})],
        ("GET", "/me"): [FakeResp({"user_id": "17841", "username": "kedici"})],
        ("POST", "/17841/media_publish"): [FakeResp({"id": "m1"})],
        ("POST", "/17841/media"): [FakeResp({"id": "c1"})],
        ("GET", "/c1"): [FakeResp({"status_code": "IN_PROGRESS"}), FakeResp({"status_code": "FINISHED"})],
        ("GET", "/m1"): [FakeResp({"permalink": "https://instagram.com/reel/abc"})],
    })
    ig = social.client("instagram", http)
    acc = ig.exchange("c", "r")
    assert (acc.name, acc.remote_id, acc.access) == ("@kedici", "17841", "L")
    with pytest.raises(social.PublishError, match="https"):
        ig.publish("L", "17841", v, _post(), "http://localhost/yayin/dosya/x")
    assert ig.publish("L", "17841", v, _post(), "https://cutless.app/yayin/dosya/t") == ("m1", "https://instagram.com/reel/abc")
    create = [c for c in http.calls if c[1].endswith("/17841/media")][0][2]["data"]
    assert create["media_type"] == "REELS" and create["video_url"] == "https://cutless.app/yayin/dosya/t"


def test_account_delete_removes_social_links(client, monkeypatch):
    from saas import publisher
    from saas.models import Publication, SocialAccount

    monkeypatch.setattr(config, "FAKE_AI", True)
    signup(client, "a@b.com")
    give("a@b.com", 100)
    _demo_connect(client, "instagram")
    t = csrf(client, "/video/yeni")
    client.post("/video/yeni", data={"idea": "x", "quality": "lite", "csrf": t})
    run_queue(ai.FakeAI())
    with db.session() as s:
        jid = s.scalar(select(Job.id))
    client.post(f"/video/{jid}/yayinla/instagram", data={"csrf": t})
    client.post("/hesap/sil", data={"csrf": csrf(client, "/hesap"), "confirm": "a@b.com"})
    with db.session() as s:
        assert s.scalar(select(SocialAccount)) is None and s.scalar(select(Publication)) is None
        assert s.get(Job, jid).video_file == ""
    assert publisher.claim() is None


# --- İngilizce site ---
TR_CHARS = re.compile(r"[ğĞşŞıİçÇöÖüÜ]")
ALLOWED_TR = ["Türkçe", "Türkçe devam et"]  # dil seçicide dilin kendi adı


def _assert_english(html_text, url, extra=()):
    text = html_text
    for w in [*ALLOWED_TR, *extra]:
        text = text.replace(w, "")
    bad = TR_CHARS.search(text)
    assert not bad, f"{url}: Türkçe metin kaldı → …{text[max(0, bad.start() - 80):bad.end() + 40]}…"
    assert '<html lang="en">' in html_text, url


def test_every_translatable_string_has_english():
    from saas import i18n_keys

    assert i18n_keys.missing() == []
    from saas.i18n_en import EN

    for k, v in EN.items():  # yer tutucular ve etiketler korunmalı
        assert sorted(re.findall(r"\{\w+\}", k)) == sorted(re.findall(r"\{\w+\}", v)), k
        assert len(re.findall(r"<[a-z]", k)) == len(re.findall(r"<[a-z]", v)), k


def test_english_site_has_no_turkish_left(client, monkeypatch):
    from saas import publisher

    monkeypatch.setattr(config, "FAKE_AI", True)
    anon = TestClient(client.app)
    for url in ["/en/", "/en/kesfet", "/en/giris", "/en/kayit", "/en/sifremi-unuttum", "/en/yok"]:
        r = anon.get(url)
        assert r.status_code in (200, 404), url
        _assert_english(r.text, url)
    # İngilizce kayıt olan kullanıcı uygulamanın tamamını İngilizce görür
    c = TestClient(client.app)
    c.get("/en/")
    r = c.post("/kayit", data={"email": "en@b.com", "password": "sifre1234", "name": "Ann", "accept": "1", "consent": "1",
                               "csrf": csrf(c, "/kayit")})
    _assert_english(r.text, "/panel (yeni hesap)")
    with db.session() as s:
        u = s.scalar(select(User).where(User.email == "en@b.com"))
        assert u.lang == "en" and not u.email_verified
        u.email_verified = True
    give("en@b.com", 1000)
    t = csrf(c, "/video/yeni")
    _assert_english(c.get("/karakterler").text, "/karakterler (boş)")
    _assert_english(c.post("/karakterler", data={"name": "Mo", "look": "A grumpy orange", "voice": "deep",
                                                 "csrf": t}).text, "karakter kaydet")
    c.post("/video/yeni", data={"idea": "x", "quality": "lite", "language": "en", "csrf": t})
    c.post("/kanallar/yeni", data={"name": "K", "quality": "lite", "times": "10:00", "csrf": t})
    c.get(c.get("/baglan/youtube", follow_redirects=False).headers["location"])
    run_queue(ai.FakeAI())
    with db.session() as s:
        jid, cid = s.scalar(select(Job.id)), s.scalar(select(Channel.id))
        s.get(Channel, cid).notice = "2026-10-13 09:45 videosu kredi yetersiz olduğu için üretilmedi."
        publisher.queue(s, s.get(Job, jid), ["youtube"])
    publisher.run(publisher.claim())
    for url in ["/panel", "/video/yeni", f"/video/yeni?from={jid}", "/videolar", "/videolar?durum=hata&q=zzz",
                f"/video/{jid}", "/kanallar", "/kanallar/yeni", f"/kanallar/{cid}", "/kredi", "/hesap", "/davet",
                "/baglantilar", "/karakterler", "/karakterler?duzenle=1", "/takvim", "/video/99999"]:
        r = c.get(url)
        assert r.status_code in (200, 404), url
        _assert_english(r.text, url)
    from saas.models import Publication

    with db.session() as s:  # onay bekleyen paylaşım ekranları da İngilizce
        s.scalar(select(Publication)).status = "onay"
    for url in ["/panel", f"/video/{jid}", "/baglantilar"]:
        _assert_english(c.get(url).text, url + " (onay)")
    import html

    assert "wasn't made because you ran out of credits" in html.unescape(c.get("/kanallar").text)
    assert "Video #1 (Economy)" in c.get("/kredi").text
    # düzenle-kaydet akışındaki mesajlar da İngilizce
    _assert_english(c.post(f"/kanallar/{cid}", data={"name": "K2", "times": "11:00", "csrf": t}).text, "kanal kaydet")
    _assert_english(c.post("/kredi/kod", data={"code": "YOK", "csrf": t}).text, "promosyon hatası")


def test_language_switch_cookie_and_seo(client):
    r = client.get("/dil/en?next=/kesfet", follow_redirects=False)
    assert r.headers["location"] == "/en/kesfet" and "dil=en" in r.headers["set-cookie"]
    assert client.get("/dil/en?next=//kotu.site", follow_redirects=False).headers["location"] == "/en/"
    assert client.get("/dil/tr?next=/en/kesfet", follow_redirects=False).headers["location"] == "/kesfet"
    assert client.get("/dil/en?next=/panel", follow_redirects=False).headers["location"] == "/panel"
    home = TestClient(client.app).get("/en/").text
    assert '<link rel="canonical" href="http://testserver/en/">' in home
    assert 'hreflang="tr" href="http://testserver/"' in home and 'hreflang="en" href="http://testserver/en/"' in home
    assert '"inLanguage": "en"' in home and "Do I need a credit card?" in home
    assert "/static/shots/studio-en.jpg" in home  # İngilizce görsel varsa o, yoksa Türkçesi
    assert "/static/shots/studio.jpg" in TestClient(client.app).get("/").text
    tr = TestClient(client.app).get("/", headers={"accept-language": "tr-TR,tr;q=0.9"}).text
    assert '<html lang="tr">' in tr and "View in English" not in tr
    assert "View in English" in TestClient(client.app).get("/", headers={"accept-language": "en-US,en;q=0.9"}).text
    assert "<loc>http://testserver/en/kesfet</loc>" in client.get("/sitemap.xml").text
    assert "Disallow: /en/panel" in client.get("/robots.txt").text


def test_emails_follow_account_language(client, tmp_path):
    c = TestClient(client.app)
    c.get("/en/")
    c.post("/kayit", data={"email": "en@b.com", "password": "sifre1234", "accept": "1", "consent": "1",
                           "csrf": csrf(c, "/kayit")})
    assert "Verify your email" in last_mail(tmp_path) and '<html lang="en">' in last_mail(tmp_path)
    with db.session() as s:
        uid = s.scalar(select(User.id).where(User.email == "en@b.com"))
        s.get(User, uid).email_verified = True
    worker.notify(uid, "{channel}: yeni videon hazır 🎬", "Yeni videon hazır!",
                  "<b>{channel}</b> kanalın için yeni video üretildi: “{title}”. "
                  "Başlığı, açıklaması ve hashtag'leriyle birlikte paylaşmaya hazır.",
                  ("Videoyu gör", "http://x/video/1"), channel="<Kedi>", title="Selam")
    mail = last_mail(tmp_path)
    assert "Your new video is ready!" in mail and "&lt;Kedi&gt;" in mail and "View video" in mail
    # Türkçe sayfadan giriş yapınca seçilmiş dil hesaba yazılır; seçim yoksa hesabın dili gelir
    c2 = TestClient(client.app)
    r = c2.post("/giris", data={"email": "en@b.com", "password": "sifre1234", "csrf": csrf(c2, "/giris")},
                follow_redirects=False)
    assert "dil=en" in r.headers.get("set-cookie", "")


def test_readiness_page_and_legal_info(client, monkeypatch):
    signup(client, "admin@x.com")
    page = client.get("/admin").text
    assert "zorunlu eksik" in page
    r = client.get("/admin/hazirlik").text
    assert "Gizli anahtar" in r and "Yasal sayfalardaki satıcı bilgileri" in r and "SIRKET_UNVANI" in r
    other = TestClient(client.app)
    signup(other, "o@b.com")
    assert other.get("/admin/hazirlik").status_code == 404
    assert "[ŞİRKET UNVANI / AD SOYAD]" in client.get("/yasal/mesafeli").text  # boşken yer tutucu görünür
    monkeypatch.setitem(config.LEGAL, "name", "Deneme Yazılım Ltd. Şti.")
    monkeypatch.setitem(config.LEGAL, "email", "destek@cutless.app")
    monkeypatch.setitem(config.LEGAL, "host", "Hetzner Online GmbH, Almanya")
    satis = client.get("/yasal/mesafeli").text
    assert "Deneme Yazılım Ltd. Şti." in satis and "destek@cutless.app" in satis
    assert "Hetzner Online GmbH, Almanya" in client.get("/yasal/kvkk").text
    assert 'href="mailto:destek@cutless.app"' in client.get("/").text
    from saas import hazirlik

    monkeypatch.setattr(config, "SECRET_KEY", "x" * 40)
    assert next(c for c in hazirlik.checks() if c.title == "Gizli anahtar").ok


def test_api_trial_tool_with_fake_generator(tmp_path, monkeypatch, capsys):
    import json

    from saas import api_dene

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    assert api_dene.main(["--kalite", "hepsi", "--evet"], generator=ai.FakeAI()) == 0
    out = capsys.readouterr().out
    assert "Senaryo" in out and "Özet" in out and out.count("✓") >= 4
    report = json.loads(next((tmp_path / "api_deneme").glob("*-sonuc.json")).read_text(encoding="utf-8"))
    assert [r["kalite"] for r in report["sonuclar"]] == list(config.QUALITIES) and all(r["ok"] for r in report["sonuclar"])
    assert api_dene.main(["--sadece-metin"], generator=ai.FakeAI()) == 0
    assert not list((tmp_path / "api_deneme").glob("*-lite.mp4"))[1:]  # sadece metinde yeni video yok
    assert api_dene.main(["--kalite", "yok"], generator=ai.FakeAI()) == 2
    failing = ai.FakeAI(fail_with=RuntimeError("400 FAILED_PRECONDITION: billing is not enabled"))
    assert api_dene.main(["--evet"], generator=failing) == 1
    assert "faturalandırma" in capsys.readouterr().out
    assert "geçersiz" in api_dene.explain(RuntimeError("API key not valid. Please pass a valid API key."))
    assert "Model adı" in api_dene.explain(RuntimeError("404 NOT_FOUND models/veo-x"))


# --- güvenlik ---
def test_admin_email_needs_verification_before_admin_rights(client, tmp_path):
    c = TestClient(client.app)
    signup(c, "admin@x.com", verify=False)  # saldırgan yönetici e-postasıyla kaydolur ama doğrulayamaz
    assert c.get("/admin").status_code == 404
    with db.session() as s:
        assert not s.scalar(select(User).where(User.email == "admin@x.com")).is_admin
    link = mail_link(tmp_path, "/dogrula")
    c.get(link)  # e-postanın gerçek sahibi doğrularsa yetki gelir
    assert c.get("/admin").status_code == 200


def test_verification_link_does_not_log_in_other_browser(client, tmp_path):
    signup(client, "a@b.com", verify=False)
    link = mail_link(tmp_path, "/dogrula")
    other = TestClient(client.app)
    r = other.get(link, follow_redirects=False)
    assert r.headers["location"] == "/giris"
    assert other.get("/panel", follow_redirects=False).status_code == 303  # sızan bağlantı oturum açmaz
    with db.session() as s:
        assert s.scalar(select(User)).email_verified


def test_password_change_logs_out_other_sessions(client):
    signup(client, "a@b.com")
    phone = TestClient(client.app)
    phone.post("/giris", data={"email": "a@b.com", "password": "sifre1234", "csrf": csrf(phone, "/giris")})
    assert phone.get("/panel", follow_redirects=False).status_code == 200
    client.post("/hesap/sifre", data={"current": "sifre1234", "password": "yenisifre99", "password2": "yenisifre99",
                                      "csrf": csrf(client, "/hesap")})
    assert client.get("/panel", follow_redirects=False).status_code == 200  # değiştiren oturum açık kalır
    assert phone.get("/panel", follow_redirects=False).status_code == 303


def test_google_login_drops_password_planted_on_unverified_account(client, monkeypatch):
    from saas import oauth

    signup(client, "kurban@b.com", verify=False)  # saldırgan kurbanın e-postasıyla şifreli hesap açar
    monkeypatch.setattr(oauth, "enabled", lambda: True)
    monkeypatch.setattr(oauth, "exchange_code", lambda code, redirect: {
        "sub": "g-1", "email": "kurban@b.com", "email_verified": True, "name": "Kurban"})
    import urllib.parse

    victim = TestClient(client.app)
    loc = victim.get("/auth/google", follow_redirects=False).headers["location"]
    st = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)["state"][0]
    victim.get(f"/auth/google/donus?code=x&state={st}")
    with db.session() as s:
        u = s.scalar(select(User).where(User.email == "kurban@b.com"))
        assert u.google_sub == "g-1" and u.pw_hash == "" and u.email_verified
    attacker = TestClient(client.app)
    attacker.post("/giris", data={"email": "kurban@b.com", "password": "sifre1234", "csrf": csrf(attacker, "/giris")})
    assert attacker.get("/panel", follow_redirects=False).status_code == 303


def test_topup_approved_once_and_signup_rate_limited(client):
    from saas.models import TopUp

    signup(client, "a@b.com")
    client.post("/kredi/bildirim", data={"package": 0, "sender_name": "Ali", "accept": "1", "csrf": csrf(client, "/kredi")})
    admin = TestClient(client.app)
    signup(admin, "admin@x.com")
    with db.session() as s:
        tid = s.scalar(select(TopUp.id))
    t = csrf(admin, "/admin")
    admin.post(f"/admin/yukleme/{tid}/onayla", data={"csrf": t})
    admin.post(f"/admin/yukleme/{tid}/onayla", data={"csrf": t})
    assert balance("a@b.com") == config.PACKAGES[0][1]
    mails = [f.read_text(encoding="utf-8") for f in (config.DATA_DIR / "epostalar").glob("*.html")]
    assert any("Yeni havale bildirimi" in m and "a@b.com" in m for m in mails)  # yöneticiye haber gitti
    spam = TestClient(client.app)
    codes = [spam.post("/kayit", data={"email": f"s{i}@b.com", "password": "sifre1234", "accept": "1", "consent": "1",
                                       "csrf": csrf(spam, "/kayit")}, follow_redirects=False).headers["location"]
             for i in range(12)]
    assert codes.count("/kayit") >= 4  # 8'den sonrası reddedilir (2 hesap yukarıda açıldı)


def test_language_switch_rejects_unsafe_next(client):
    for bad in ["//kotu.site", "/\\kotu.site", "https://kotu.site", "/%0d%0aSet-Cookie:x=1", "javascript:alert(1)"]:
        loc = client.get("/dil/en", params={"next": bad}, follow_redirects=False).headers["location"]
        assert loc == "/en/", bad


def test_admin_user_search_detail_block_and_failed_jobs(client):
    signup(client, "ali@b.com")
    give("ali@b.com", 100)

    class Broken(ai.FakeAI):
        def make_video(self, **kw):
            raise RuntimeError("404 NOT_FOUND models/veo-yok")

    client.post("/video/yeni", data={"idea": "x", "quality": "lite", "csrf": csrf(client, "/video/yeni")})
    run_queue(Broken())
    admin = TestClient(client.app)
    signup(admin, "admin@x.com")
    page = admin.get("/admin").text
    assert "Başarısız işler" in page and "404 NOT_FOUND models/veo-yok" in page  # teknik hata yöneticide
    assert "veo-yok" not in client.get("/videolar").text  # kullanıcı teknik hatayı görmez
    with db.session() as s:
        uid = s.scalar(select(User.id).where(User.email == "ali@b.com"))
    lst = admin.get("/admin/kullanicilar?q=ali@").text  # (test kullanıcılarının hepsinin adı "Ali")
    assert f"/admin/kullanici/{uid}" in lst and lst.count('href="/admin/kullanici/') == 1  # yalnızca eşleşen
    detail = admin.get(f"/admin/kullanici/{uid}").text
    assert "ali@b.com" in detail and "İade: video #1" in detail
    t = csrf(admin, "/admin")
    r = admin.post("/admin/kredi", data={"email": "ali@b.com", "amount": 7, "reason": "x", "back": f"/admin/kullanici/{uid}",
                                         "csrf": t}, follow_redirects=False)
    assert r.headers["location"] == f"/admin/kullanici/{uid}" and balance("ali@b.com") == 107
    assert admin.post("/admin/kredi", data={"email": "ali@b.com", "amount": 1, "back": "https://kotu.site", "csrf": t},
                      follow_redirects=False).headers["location"] == "/admin"
    admin.post(f"/admin/kullanici/{uid}/askiya-al", data={"csrf": t})
    assert client.get("/panel", follow_redirects=False).status_code == 303  # askıya alınan oturumdan düşer
    again = TestClient(client.app)
    assert "askıya alındı" in again.post("/giris", data={"email": "ali@b.com", "password": "sifre1234",
                                                          "csrf": csrf(again, "/giris")}).text
    admin.post(f"/admin/kullanici/{uid}/askiya-al", data={"csrf": t})
    again.post("/giris", data={"email": "ali@b.com", "password": "sifre1234", "csrf": csrf(again, "/giris")})
    assert again.get("/panel", follow_redirects=False).status_code == 200
    other = TestClient(client.app)
    signup(other, "o@b.com")
    assert other.get(f"/admin/kullanici/{uid}").status_code == 404


def test_showcase_mode_is_safe_for_public_demo(client, monkeypatch):
    monkeypatch.setattr(config, "SHOWCASE", True)
    monkeypatch.setattr(config, "FAKE_AI", True)
    monkeypatch.setattr(config, "SIGNUP_BONUS", 300)
    r = client.get("/")
    assert "demo-bar" in r.text and r.headers["x-robots-tag"].startswith("noindex")
    assert client.get("/robots.txt").text == "User-agent: *\nDisallow: /\n"
    c = TestClient(client.app)
    r = c.post("/kayit", data={"email": "admin@x.com", "password": "sifre1234", "accept": "1", "consent": "1",
                               "csrf": csrf(c, "/kayit")})
    assert "verify-bar" not in r.text and balance("admin@x.com") == 300  # doğrulama atlanır, hediye gelir
    assert c.get("/admin").status_code == 404  # yönetici e-postasıyla bile yönetim kapalı
    assert "ödeme alınmıyor" in c.get("/kredi").text and 'action="/kredi/bildirim"' not in c.get("/kredi").text
    c.post("/kredi/bildirim", data={"package": 0, "sender_name": "x", "accept": "1", "csrf": csrf(c, "/kredi")})
    from saas.models import TopUp

    with db.session() as s:
        assert s.scalar(select(TopUp)) is None
    anon = TestClient(client.app)
    r = anon.post("/sifremi-unuttum", data={"email": "admin@x.com", "csrf": csrf(anon, "/sifremi-unuttum")})
    assert "şifre sıfırlama kapalı" in r.text and "/dev/eposta/" not in r.text


def test_showcase_launcher_finds_tunnel_url_and_refuses_known_secret(tmp_path, monkeypatch):
    from saas import canli

    fake = tmp_path / "cf.sh"
    fake.write_text("#!/bin/sh\necho 'INF Requesting new quick Tunnel on trycloudflare.com... https://api.trycloudflare.com'\n"
                    "echo 'INF |  https://blue-river-demo.trycloudflare.com  |'\n"
                    "echo 'INF Registered tunnel connection connIndex=0'\nsleep 30\n")
    fake.chmod(0o755)
    monkeypatch.setenv("CLOUDFLARED", str(fake))
    proc, url, registered = canli.start_tunnel(8999, timeout=10)
    assert registered.wait(5)
    proc.terminate()
    assert url == "https://blue-river-demo.trycloudflare.com"  # api. adresi değil, rastgele tünel adresi
    key = canli.secret_for(tmp_path / "v")
    assert len(key) >= 32 and canli.secret_for(tmp_path / "v") == key  # kalıcı
    monkeypatch.setattr(config, "SHOWCASE", True)
    with pytest.raises(RuntimeError, match="GIZLI_ANAHTAR"):
        create_app(start_worker=False, database_url=f"sqlite:///{tmp_path / 'x.db'}")


# --- ziyaretçiyi bağlayanlar: erken erişim, fikir makinesi ---
def test_waitlist_join_reward_and_export(client, tmp_path, monkeypatch):
    from saas.models import Waitlist

    monkeypatch.setattr(config, "PRELAUNCH", True)
    monkeypatch.setattr(config, "EARLY_TOPUP_PCT", 20)
    anon = TestClient(client.app)
    home = anon.get("/").text
    assert 'id="erken"' in home and "data-mcta" in home
    t = csrf(anon, "/")
    assert "e-posta iznini" in anon.post("/erken-erisim", data={"email": "a@b.com", "csrf": t}).text  # izin şart
    assert "Geçerli bir e-posta" in anon.post("/erken-erisim", data={"email": "x", "consent": "1", "csrf": t}).text
    r = anon.post("/erken-erisim", data={"email": " A@b.com ", "consent": "1", "kaynak": "ana-sayfa", "next": "/#erken",
                                         "csrf": t}, follow_redirects=False)
    assert r.headers["location"].startswith("/liste/")
    status = anon.get(r.headers["location"]).text
    assert "Listedesin" in status and "a@b.com" not in status and "a•••@b.com" in status  # e-posta gizli
    anon.post("/erken-erisim", data={"email": "a@b.com", "consent": "1", "next": "https://kotu.site", "csrf": t})
    with db.session() as s:
        assert [w.email for w in s.scalars(select(Waitlist))] == ["a@b.com"]  # tekrar eklenmez
    signup(client, "a@b.com", verify=False)
    client.get(mail_link(tmp_path, "/dogrula"))
    assert balance("a@b.com") == 0  # doğrulamada bedava kredi yok
    admin = TestClient(client.app)
    signup(admin, "admin@x.com")
    for _ in range(2):
        notify_topup(client)
        approve_topups(admin)
    cr = config.PACKAGES[0][1]
    assert balance("a@b.com") == 2 * cr + cr * 20 // 100  # ilk yüklemede %20 fazla, bir kez
    assert "Erken erişim listesi: 1 kişi" in admin.get("/admin").text
    csv_text = admin.get("/admin/erken-erisim.csv").text
    assert "a@b.com" in csv_text and "evet" in csv_text
    assert TestClient(client.app).get("/admin/erken-erisim.csv", follow_redirects=False).status_code == 303
    monkeypatch.setattr(config, "PRELAUNCH", False)
    assert 'id="erken"' not in anon.get("/").text


def test_waitlist_cli_roundtrip(tmp_path, monkeypatch):
    from saas import erken_erisim
    from saas.models import Waitlist

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite:///{tmp_path / 'c.db'}")
    db.init(f"sqlite:///{tmp_path / 'c.db'}")
    with db.session() as s:
        s.add(Waitlist(email="x@y.com", source="ana-sayfa"))
    out = tmp_path / "l.csv"
    assert erken_erisim.main(["disari", str(out)]) == 0
    assert "x@y.com" in out.read_text(encoding="utf-8")
    out.write_text(out.read_text(encoding="utf-8") + "yeni@y.com,en,video,2026-10-15\n", encoding="utf-8")
    assert erken_erisim.main(["iceri", str(out)]) == 0
    with db.session() as s:
        assert sorted(s.scalars(select(Waitlist.email))) == ["x@y.com", "yeni@y.com"]


def test_idea_machine_carries_idea_through_signup(client, monkeypatch):
    import html
    import json

    page = client.get("/").text
    m = re.search(r"data-ideas='([^']+)'", page)
    ideas = json.loads(html.unescape(m.group(1)))
    assert len(ideas) >= 20 and all(i["t"] and i["e"] and i["l"] for i in ideas)
    en = json.loads(html.unescape(re.search(r"data-ideas='([^']+)'", TestClient(client.app).get("/en/").text).group(1)))
    assert en[0]["t"] != ideas[0]["t"] and en[0]["l"] == "Cartoon"
    idea = ideas[0]["t"]
    c = TestClient(client.app)
    c.get("/kayit", params={"fikir": idea})
    r = c.post("/kayit", data={"email": "f@b.com", "password": "sifre1234", "accept": "1", "consent": "1",
                               "csrf": csrf(c, "/kayit")}, follow_redirects=False)
    assert r.headers["location"].startswith("/video/yeni?idea=")
    assert html.escape(idea, quote=False) in html.unescape(c.get(r.headers["location"]).text) or idea in html.unescape(
        c.get(r.headers["location"]).text)


def test_showcase_demo_video_offers_waitlist(client, monkeypatch):
    monkeypatch.setattr(config, "SHOWCASE", True)
    monkeypatch.setattr(config, "FAKE_AI", True)
    monkeypatch.setattr(config, "PRELAUNCH", True)
    c = TestClient(client.app)
    c.post("/kayit", data={"email": "d@b.com", "password": "sifre1234", "accept": "1", "consent": "1",
                           "csrf": csrf(c, "/kayit")})
    give("d@b.com", 100)
    c.post("/video/yeni", data={"idea": "x", "quality": "lite", "csrf": csrf(c, "/video/yeni")})
    run_queue(ai.FakeAI())
    with db.session() as s:
        jid = s.scalar(select(Job.id))
    page = c.get(f"/video/{jid}").text
    assert "Bu bir demo animasyonu" in page
    c.post("/erken-erisim", data={"email": "d@b.com", "consent": "1", "kaynak": "demo-video", "next": f"/video/{jid}",
                                  "csrf": csrf(c, "/panel")})
    from saas.models import Waitlist

    with db.session() as s:
        assert s.scalar(select(Waitlist.source)) == "demo-video"


def test_waitlist_invites_reward_inviter_on_first_topup(client, tmp_path, monkeypatch):
    from saas.models import Waitlist

    monkeypatch.setattr(config, "EARLY_TOPUP_PCT", 20)
    monkeypatch.setattr(config, "REFERRAL_PCT", 15)
    monkeypatch.setattr(config, "REFERRAL_FRIEND_PCT", 10)

    def join(c, email):
        return c.post("/erken-erisim", data={"email": email, "consent": "1", "csrf": csrf(c, "/kayit")},
                      follow_redirects=False).headers["location"]

    host = TestClient(client.app)
    code = join(host, "ev@b.com").rsplit("/", 1)[1]
    for email in ["k1@b.com", "k2@b.com", "ev@b.com"]:
        friend = TestClient(client.app)
        assert friend.get(f"/e/{code}", follow_redirects=False).headers["location"] == "/#erken"
        join(friend, email)
    with db.session() as s:
        refs = {w.email: w.ref for w in s.scalars(select(Waitlist))}
    assert refs["k1@b.com"] == refs["k2@b.com"] == code and refs["ev@b.com"] == ""  # kendini davet sayılmaz
    signup(host, "ev@b.com")
    admin = TestClient(client.app)
    signup(admin, "admin@x.com")
    cr = config.PACKAGES[0][1]
    friends = []
    for email in ["k1@b.com", "k2@b.com"]:
        c = TestClient(client.app)
        signup(c, email)
        friends.append(c)
    assert balance("ev@b.com") == 0 and balance("k1@b.com") == 0  # doğrulamada kimseye bedava kredi yok
    assert "Kaydolan" in host.get(f"/liste/{code}").text
    notify_topup(friends[0])
    approve_topups(admin)
    # davetli: erken erişim %20 (davet %10'dan büyük olan, toplanmaz); davet eden: yüklemenin %15'i
    assert balance("k1@b.com") == cr + cr * 20 // 100 and balance("ev@b.com") == cr * 15 // 100
    assert TestClient(client.app).get("/liste/YOKBOYLE").status_code == 404


def test_loyalty_gives_one_video_per_threshold(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOYALTY_EVERY", 100)
    signup(client, "a@b.com")
    give("a@b.com", 500)
    t = csrf(client, "/video/yeni")
    lite = config.QUALITIES["lite"]["credits"]
    for i in range(3):  # 3 × 49 = 147 kredi → 1 hediye (eşik 100)
        client.post("/video/yeni", data={"idea": f"x{i}", "quality": "lite", "csrf": t})
    run_queue(ai.FakeAI())
    assert balance("a@b.com") == 500 - 3 * lite + lite
    assert "1 video bizden" in last_mail(tmp_path) or "Sadakat" in client.get("/kredi").text
    page = client.get("/kredi").text
    assert f"{(3 * lite) % 100} / 100" in page and "Sadakat hediyesi" in page
    from saas import growth

    with db.session() as s:
        uid = s.scalar(select(User.id).where(User.email == "a@b.com"))
        assert growth.loyalty(s, uid) == 0  # aynı eşik ikinci kez verilmez


def test_templates_page_and_prefill_forms(client):
    import html

    page = TestClient(client.app).get("/sablonlar").text
    assert "Komik Meyveler" in page and "/kayit?sablon=komik-meyveler" in page
    assert "Office Cat" in TestClient(client.app).get("/en/sablonlar").text
    assert "Ofis Kedisi" not in TestClient(client.app).get("/sablonlar?kategori=egitim").text
    assert "<loc>http://testserver/sablonlar</loc>" in client.get("/sitemap.xml").text
    c = TestClient(client.app)
    c.get("/kayit?sablon=ofis-kedisi")
    r = c.post("/kayit", data={"email": "s@b.com", "password": "sifre1234", "accept": "1", "consent": "1",
                               "csrf": csrf(c, "/kayit")}, follow_redirects=False)
    assert r.headers["location"] == "/kanallar/yeni?sablon=ofis-kedisi"
    form = html.unescape(c.get(r.headers["location"]).text)
    assert 'value="Ofis Kedisi"' in form and "Gözlüklü, kendini müdür sanan" in form and 'value="09:45 18:30"' in form
    assert 'action="/kanallar/yeni"' in form  # yeni kanal (düzenleme değil)
    video = html.unescape(c.get("/video/yeni?sablon=dinozor-sehirde").text)
    assert "şablonuyla dolduruldu" in video and "Dinozor metrobüse binmeye çalışıyor" in video
    assert 'value="meme3d" data-label' in video and 'value="meme3d" data-label="Ucuz 3D oyun (meme)" checked' in video


def test_content_calendar_shows_past_and_planned(client):
    signup(client, "a@b.com")
    give("a@b.com", 70)
    assert "Henüz otomatik kanalın yok" in client.get("/takvim").text
    client.post("/kanallar/yeni", data={"name": "Meyve", "quality": "fast", "times": "00:01 23:59",
                                        "csrf": csrf(client, "/kanallar/yeni")})
    client.post("/video/yeni", data={"idea": "x", "quality": "lite", "csrf": csrf(client, "/video/yeni")})
    run_queue(ai.FakeAI())
    page = client.get("/takvim").text
    assert "Bugün" in page and "Yarın" in page and "Planlı" in page and "Deneme videosu" in page
    assert "itibarıyla yetmez" in page  # 35 kredi kaldı, kanal 65 kredilik


def test_edit_share_text(client):
    signup(client, "a@b.com")
    give("a@b.com", 100)
    t = csrf(client, "/video/yeni")
    client.post("/video/yeni", data={"idea": "x", "quality": "lite", "csrf": t})
    run_queue(ai.FakeAI())
    with db.session() as s:
        jid = s.scalar(select(Job.id))
    client.post(f"/video/{jid}/metin", data={"title": "Yeni başlık", "caption": "Açıklama",
                                             "hashtags": "#komik, #komik shorts <x> #yapay-zeka", "csrf": t})
    with db.session() as s:
        j = s.get(Job, jid)
        assert (j.title, j.caption, j.hashtags) == ("Yeni başlık", "Açıklama", "komik shorts x yapayzeka")
    other = TestClient(client.app)
    signup(other, "o@b.com")
    assert other.post(f"/video/{jid}/metin", data={"title": "x", "csrf": csrf(other, "/panel")}).status_code == 404


def test_signup_free_script_trial(client, monkeypatch):
    monkeypatch.setattr(config, "FAKE_AI", True)
    client.app.state.generator = ai.FakeAI()
    t = csrf(client, "/")
    r = client.post("/api/deneme-senaryo", data={"idea": "Kedi markette kasiyerle tartışıyor", "csrf": t})
    assert r.status_code == 200
    data = r.json()
    p = data["preview"]
    assert p["title"] and p["scene"] and len(p["lines"]) >= 2 and all(x["who"] and x["text"] for x in p["lines"])
    assert data["demo"] is True and data["start"].startswith("/kayit?fikir=")
    assert client.post("/api/deneme-senaryo", data={"idea": "x", "csrf": t}).status_code == 400
    assert client.post("/api/deneme-senaryo", data={"idea": "kedi"}).status_code == 400  # CSRF yok
    en = TestClient(client.app)
    r = en.post("/api/deneme-senaryo", data={"idea": "A cat argues with a cashier", "language": "en",
                                             "csrf": csrf(en, "/en/")})
    assert r.status_code == 200 and r.json()["start"].startswith("/en/kayit?fikir=")
    assert r.json()["preview"]["lines"][0]["text"] != p["lines"][0]["text"]
    for _ in range(4):
        assert client.post("/api/deneme-senaryo", data={"idea": "kedi uçuyor", "csrf": t}).status_code == 200
    r = client.post("/api/deneme-senaryo", data={"idea": "kedi uçuyor", "csrf": t})
    assert r.status_code == 429 and "kaydolup" in r.json()["error"]


def test_script_trial_logged_in_goes_to_studio(client):
    client.app.state.generator = ai.FakeAI()
    signup(client, "a@b.com")
    r = client.post("/api/deneme-senaryo", data={"idea": "Portakal ve muz kavga ediyor", "csrf": csrf(client, "/")})
    assert r.status_code == 200 and r.json()["start"].startswith("/video/yeni?idea=")
    page = client.get(r.json()["start"]).text
    assert "Portakal ve muz kavga ediyor" in page


def test_character_library_used_in_videos_and_channels(client):
    from saas.models import Character

    signup(client, "a@b.com")
    give("a@b.com", 500)
    t = csrf(client, "/karakterler")
    r = client.post("/karakterler", data={"name": "", "look": "x", "csrf": t})
    assert "Karaktere bir ad ver" in r.text
    client.post("/karakterler", data={"name": "Portakal Paşa", "look": "Kocaman kaşlı sinirli portakal",
                                      "voice": "Boğuk, Karadeniz şiveli", "csrf": t},
                files={"ref": ("p.png", PNG_1PX, "image/png")})
    client.post("/karakterler", data={"name": "Muz", "look": "Saf, hep gülen muz", "csrf": t})
    with db.session() as s:
        orange, banana = s.scalars(select(Character).order_by(Character.id)).all()
    assert orange.ref_image and not banana.ref_image
    page = client.get("/karakterler").text
    assert "Portakal Paşa" in page and "Bu karakterle video üret" in page

    # stüdyo: ?karakter= ile seçili gelir; seçilen karakterlerin tarifi ve görseli videoya gider
    studio = client.get(f"/video/yeni?karakter={orange.id}").text
    assert re.search(rf'name="cast" value="{orange.id}" checked', studio)
    client.post("/video/yeni", data={"idea": "markette kavga", "quality": "lite", "characters": "bir kasiyer",
                                     "cast": [str(orange.id), str(banana.id)], "csrf": t})
    with db.session() as s:
        job = s.scalar(select(Job).order_by(Job.id.desc()))
    assert "Portakal Paşa" in job.characters and "Karadeniz" in job.characters and "Muz" in job.characters
    assert job.characters.endswith("bir kasiyer") and job.ref_image == orange.ref_image

    # kanal karakteri kimliğiyle tutar: karakter düzenlenince sonraki videolar yeni hâlini kullanır
    client.post("/kanallar/yeni", data={"name": "Meyveler", "topic": "x", "times": "09:00", "cast": [str(banana.id)],
                                        "csrf": t})
    with db.session() as s:
        ch = s.scalar(select(Channel))
    assert ch.cast_ids == str(banana.id)
    assert re.search(rf'name="cast" value="{banana.id}" checked', client.get(f"/kanallar/{ch.id}").text)
    client.post("/karakterler", data={"id": str(banana.id), "name": "Muz Bey", "look": "Gözlüklü muz", "csrf": t})
    worker.schedule_channels(datetime(2026, 1, 5, 9, 1, tzinfo=ZoneInfo(config.TIMEZONE)))
    with db.session() as s:
        cj = s.scalar(select(Job).where(Job.channel_id == ch.id))
    assert "Muz Bey" in cj.characters and "Gözlüklü" in cj.characters

    # başkası bu karakterleri ne görebilir ne kullanabilir
    other = TestClient(client.app)
    signup(other, "o@b.com")
    give("o@b.com", 100)
    ot = csrf(other, "/karakterler")
    assert other.get(f"/karakterler?duzenle={orange.id}").status_code == 404
    assert other.post(f"/karakterler/{orange.id}/sil", data={"csrf": ot}).status_code == 404
    assert other.post("/karakterler", data={"id": str(orange.id), "name": "x", "look": "y", "csrf": ot}).status_code == 404
    other.post("/video/yeni", data={"idea": "x", "quality": "lite", "cast": [str(orange.id)], "csrf": ot})
    with db.session() as s:
        oj = s.scalar(select(Job).join(User).where(User.email == "o@b.com"))
    assert "Portakal" not in oj.characters and oj.ref_image == ""

    # silinen karakter kanaldan da çıkar
    client.post(f"/karakterler/{banana.id}/sil", data={"csrf": t})
    with db.session() as s:
        assert s.get(Channel, ch.id).cast_ids == "" and s.get(Character, banana.id) is None


def test_viral_subtitles_word_by_word():
    from saas import media

    ass = media.build_ass([{"start": 0.3, "end": 2.6, "text": "Bu son {\\\\an8}indirim benim!"},
                           {"start": 3.0, "end": 4.0, "text": "ışık", "words": [{"text": "ışık", "start": 3.2, "end": 3.9}]}],
                          style="viral", language="tr")
    lines = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    assert len(lines) == 5  # her kelime için bir olay
    texts = [l.split(",", 9)[9] for l in lines]
    assert all(t.count("\\c&H") == 1 for t in texts)  # her olayda tek renkli (söylenen) kelime
    assert texts[0].endswith("BU{\\r} SON") and "(AN8)İNDİRİM" in texts[2] and "an8}" not in ass
    assert "IŞIK" in texts[-1] and "0:00:03.20" in lines[-1] and "0:00:03.90" in lines[-1]  # verilen kelime zamanı
    # parça içinde kelimeler kesintisiz: bir olayın bitişi sonrakinin başlangıcı
    ends = [l.split(",")[2] for l in lines[:3]]
    starts = [l.split(",")[1] for l in lines[1:4]]
    assert ends[:2] == starts[:2]
    classic = media.build_ass([{"start": 0, "end": 1, "text": "Bu son indirim"}])
    assert "Bu son indirim" in classic and "\\c&H" not in classic and media.FONT_NAME in classic


def test_viral_subtitle_style_flows_to_jobs_and_channels(client):
    class Spy(ai.FakeAI):
        words = []

        def transcribe(self, *, video, language, words=False):
            Spy.words.append(words)
            return super().transcribe(video=video, language=language)

    signup(client, "a@b.com")
    give("a@b.com", 500)
    t = csrf(client, "/video/yeni")
    page = client.get("/video/yeni").text
    assert re.search(r'name="subtitles" value="1"\s+checked', page) and re.search(r'value="viral"\s+checked', page)
    client.post("/video/yeni", data={"idea": "x", "quality": "lite", "subtitles": "1", "subtitle_style": "viral", "csrf": t})
    client.post("/video/yeni", data={"idea": "y", "quality": "lite", "subtitles": "1", "subtitle_style": "klasik", "csrf": t})
    client.post("/video/yeni", data={"idea": "z", "quality": "lite", "subtitle_style": "<script>", "csrf": t})
    run_queue(Spy())
    with db.session() as s:
        jobs = s.scalars(select(Job).order_by(Job.id)).all()
    assert [j.subtitle_style for j in jobs] == ["viral", "", ""] and Spy.words == [True, False]
    assert "viral altyazılı" in client.get(f"/video/{jobs[0].id}").text
    client.post("/kanallar/yeni", data={"name": "K", "topic": "x", "times": "09:00", "subtitles": "1",
                                        "subtitle_style": "viral", "csrf": t})
    worker.schedule_channels(datetime(2026, 1, 5, 9, 1, tzinfo=ZoneInfo(config.TIMEZONE)))
    with db.session() as s:
        ch = s.scalar(select(Channel))
        cj = s.scalar(select(Job).where(Job.channel_id == ch.id))
    assert ch.subtitle_style == "viral" and cj.subtitles and cj.subtitle_style == "viral"


def test_approval_mode_waits_for_owner_before_posting(client, tmp_path, monkeypatch):
    from saas import publisher
    from saas.models import Publication

    monkeypatch.setattr(config, "FAKE_AI", True)
    signup(client, "a@b.com")
    give("a@b.com", 500)
    _demo_connect(client, "youtube")
    t = csrf(client, "/kanallar/yeni")
    form = client.get("/kanallar/yeni").text
    assert re.search(r'name="approval" value="0"\s+checked', form)  # varsayılan: tam otomatik
    client.post("/kanallar/yeni", data={"name": "Meyveler", "quality": "lite", "times": "10:00", "pub_youtube": "1",
                                        "approval": "1", "csrf": t})
    with db.session() as s:
        ch = s.scalar(select(Channel))
    assert ch.approval and re.search(r'name="approval" value="1"\s+checked', client.get(f"/kanallar/{ch.id}").text)
    assert "onaylı" in client.get("/kanallar").text

    client.post(f"/kanallar/{ch.id}/simdi", data={"csrf": t})
    run_queue(ai.FakeAI())
    with db.session() as s:
        pub = s.scalar(select(Publication))
        jid = pub.job_id
    assert pub.status == "onay" and publisher.claim() is None  # onaysız yüklenmez
    mail = last_mail(tmp_path)
    assert "onayını bekliyor" in mail and f"/video/{jid}" in mail and "YouTube" in mail
    assert "1 video onayını bekliyor" in client.get("/panel").text
    page = client.get(f"/video/{jid}").text
    assert "Onayla ve paylaş" in page and "Onay bekliyor" in page

    # başkası (yönetici bile) onaylayamaz
    other = TestClient(client.app)
    signup(other, "admin@x.com")
    assert other.post(f"/video/{jid}/onayla", data={"csrf": csrf(other, "/panel")}).status_code == 404
    assert publisher.claim() is None

    client.post(f"/video/{jid}/onayla", data={"csrf": t})
    pid = publisher.claim()
    assert pid and publisher.claim() is None
    publisher.run(pid)
    with db.session() as s:
        assert s.get(Publication, pid).status == "yayinda"
    assert "onayını bekliyor" not in client.get("/panel").text

    # "Paylaşma": kayıt silinir, hiçbir yere yüklenmez
    client.post(f"/kanallar/{ch.id}/simdi", data={"csrf": t})
    run_queue(ai.FakeAI())
    with db.session() as s:
        jid2 = s.scalar(select(Job.id).order_by(Job.id.desc()))
    r = client.post(f"/video/{jid2}/paylasma", data={"csrf": t})
    assert "hiçbir yere yüklenmeyecek" in r.text
    with db.session() as s:
        assert s.scalar(select(Publication).where(Publication.job_id == jid2)) is None
    assert publisher.claim() is None

    # tam otomatik moda geçince sıradaki video doğrudan sıraya girer
    client.post(f"/kanallar/{ch.id}", data={"name": "Meyveler", "quality": "lite", "times": "10:00",
                                            "pub_youtube": "1", "approval": "0", "csrf": t})
    client.post(f"/kanallar/{ch.id}/simdi", data={"csrf": t})
    run_queue(ai.FakeAI())
    with db.session() as s:
        last = s.scalar(select(Publication).order_by(Publication.id.desc()))
    assert last.status == "bekliyor" and "yeni videon hazır" in last_mail(tmp_path)


def test_duration_slider_prices_and_multi_scene_video(client):
    assert config.price("lite", 4) == config.price("lite", 10) == config.QUALITIES["lite"]["credits"]
    assert config.price("lite", 11) == config.QUALITIES["lite"]["credits"] + config.QUALITIES["lite"]["per_sec"]
    assert config.plan_clips("fast", 8) == [8] and sum(config.plan_clips("fast", 17)) == 18
    assert config.clamp_seconds(999) == config.MAX_SECONDS and config.clamp_seconds("x") == config.DEFAULT_SECONDS
    signup(client, "a@b.com")
    give("a@b.com", 2000)
    t = csrf(client, "/video/yeni")
    page = client.get("/video/yeni").text
    assert 'name="seconds"' in page and 'data-per-sec=' in page
    client.post("/video/yeni", data={"idea": "uzun", "quality": "fast", "seconds": "20", "csrf": t})
    gen = ai.FakeAI()
    run_queue(gen)
    with db.session() as s:
        job = s.scalar(select(Job))
    assert job.status == "hazir" and job.seconds == 20 and job.cost == config.price("fast", 20)
    assert gen.clip_seconds == config.plan_clips("fast", 20) and len(gen.clip_seconds) == 3  # 8+8+4
    assert job.prompt.count("sahne") == 3 and balance("a@b.com") == 2000 - job.cost
    vids = list((config.DATA_DIR / "videolar").glob(f"{job.id}*.mp4"))
    assert [v.name for v in vids] == [f"{job.id}.mp4"]  # sahne dosyaları silindi
    assert "20 sn" in client.get(f"/video/{job.id}").text


def test_subscriptions_unlock_ai_tiers_and_renewal(client, tmp_path, monkeypatch):
    from datetime import timedelta, timezone

    from saas import abonelik

    signup(client, "a@b.com", plan="")
    give("a@b.com", 500)
    t = csrf(client, "/video/yeni")
    page = client.get("/video/yeni").text
    assert re.search(r'value="fast"[^>]*disabled', page) and "Pro aboneliğiyle" in page
    r = client.post("/video/yeni", data={"idea": "x", "quality": "fast", "csrf": t}, follow_redirects=False)
    assert r.headers["location"] == "/kredi#abonelik" and balance("a@b.com") == 500  # kredi düşmedi
    client.post("/video/yeni", data={"idea": "x", "quality": "lite", "csrf": t})  # Ekonomik aboneliksiz açık
    assert balance("a@b.com") == 500 - config.price("lite", 8)
    # abonelik havalesi → yönetici onayı → plan açılır, planın kredisi yüklenir
    assert "Abonelikler" in client.get("/kredi").text
    client.post("/kredi/bildirim", data={"package": "plan:pro", "sender_name": "A B", "accept": "1", "csrf": t})
    admin = TestClient(client.app)
    signup(admin, "admin@x.com")
    assert "Pro aboneliği" in admin.get("/admin").text
    before = balance("a@b.com")
    approve_topups(admin)
    assert balance("a@b.com") >= before + config.PLANS["pro"]["credits"]
    assert "aboneliğin başladı" in last_mail(tmp_path)
    with db.session() as s:
        u = s.scalar(select(User).where(User.email == "a@b.com"))
        assert abonelik.active_plan(u) == "pro" and abonelik.allowed(u) == ("lite", "fast")
    r = client.post("/video/yeni", data={"idea": "y", "quality": "fast", "csrf": t}, follow_redirects=False)
    assert r.headers["location"].startswith("/video/")
    r = client.post("/video/yeni", data={"idea": "z", "quality": "standard", "csrf": t}, follow_redirects=False)
    assert r.headers["location"] == "/kredi#abonelik"  # Premium Stüdyo'da
    # bitişe 3 günden az kala bir kez hatırlatma
    with db.session() as s:
        u = s.scalar(select(User).where(User.email == "a@b.com"))
        u.plan_until = datetime.now(timezone.utc) + timedelta(days=2)
    worker.remind_plans()
    assert "bitiyor" in last_mail(tmp_path)
    n = len(list((tmp_path / "epostalar").glob("*.html")))
    worker.remind_plans()
    assert len(list((tmp_path / "epostalar").glob("*.html"))) == n
    # süre dolunca kanal üst kademede üretmez, kredi düşmez
    client.post("/kanallar/yeni", data={"name": "K", "quality": "fast", "times": "09:00", "csrf": t})
    with db.session() as s:
        cid = s.scalar(select(Channel.id))
        s.scalar(select(User).where(User.email == "a@b.com")).plan_until = datetime.now(timezone.utc) - timedelta(days=1)
    bal = balance("a@b.com")
    assert worker.schedule_channels(datetime(2026, 1, 5, 9, 1, tzinfo=ZoneInfo(config.TIMEZONE))) == []
    with db.session() as s:
        assert "aboneliğin" in s.get(Channel, cid).notice and balance("a@b.com") == bal


def test_feedback_form_reaches_admin(client, tmp_path):
    from saas.models import Feedback

    anon = TestClient(client.app)
    page = anon.get("/oneri").text
    assert "bizimle paylaş" in page and 'name="email"' in page
    t = csrf(anon, "/oneri")
    assert "Birkaç kelimeyle" in anon.post("/oneri", data={"message": "a", "csrf": t}).text
    anon.post("/oneri", data={"message": "spam", "website": "x", "csrf": t})  # bot tuzağı
    r = anon.post("/oneri", data={"kind": "istek", "message": "Arka plan müziği seçebilelim", "email": "z@b.com",
                                  "csrf": t})
    assert "Teşekkürler" in r.text and "Arka plan müziği" in last_mail(tmp_path)
    with db.session() as s:
        rows = s.scalars(select(Feedback)).all()
    assert [(f.kind, f.email) for f in rows] == [("istek", "z@b.com")]
    assert anon.get("/admin/oneriler", follow_redirects=False).status_code == 303
    admin = TestClient(client.app)
    signup(admin, "admin@x.com")
    assert "1 yeni" in admin.get("/admin").text
    page = admin.get("/admin/oneriler").text
    assert "Arka plan müziği" in page and "z@b.com" in page
    admin.post(f"/admin/oneri/{rows[0].id}/okundu", data={"csrf": csrf(admin, "/admin")})
    with db.session() as s:
        assert s.get(Feedback, rows[0].id).status == "okundu"
    home = anon.get("/").text
    assert "Bize yaz" in home and "/oneri" in home and "Neler üretebilirsin" in home
    _assert_english(TestClient(client.app).get("/en/oneri").text, "/en/oneri")


def test_trial_script_share_page(client, monkeypatch):
    import html

    monkeypatch.setattr(config, "FAKE_AI", True)
    client.app.state.generator = ai.FakeAI()
    r = client.post("/api/deneme-senaryo", data={"idea": "Kedi <b>kasada</b> tartışıyor", "csrf": csrf(client, "/")})
    share = r.json()["share"]
    assert re.fullmatch(r"http://testserver/s/[A-Za-z0-9_-]{8}", share)
    friend = TestClient(client.app)
    page = friend.get(share.replace("http://testserver", "")).text
    assert "data-tphone" in page and "data-preview=" in page and "Sen de fikrini yaz" in page
    assert "<b>kasada</b>" not in page and html.escape("<b>kasada</b>") in page  # kaçışlı
    assert 'name="robots" content="noindex"' in page and 'property="og:title"' in page
    assert page.count('property="og:title"') == 1
    assert "/kayit?fikir=" in page
    assert friend.get("/s/YOKBOYLE1").status_code == 404 and friend.get("/s/../x").status_code == 404
    _assert_english(TestClient(client.app).get("/en/").text, "/en/ (oynatıcı)")


def test_free_channel_builder_carries_plan_into_signup(client, monkeypatch):
    import html
    from urllib.parse import parse_qs, urlparse

    monkeypatch.setattr(config, "FAKE_AI", True)
    client.app.state.generator = ai.FakeAI()
    anon = TestClient(client.app)
    page = anon.get("/araclar/kanal-kurucu").text
    assert "Kanalını" in page and "data-ktool" in page
    t = csrf(anon, "/araclar/kanal-kurucu")
    assert anon.post("/api/kanal-plani", data={"topic": "", "csrf": t}).status_code == 400
    d = anon.post("/api/kanal-plani", data={"topic": "Uzay gerçekleri", "csrf": t}).json()
    plan = d["plan"]
    assert len(plan["names"]) == 3 and len(plan["ideas"]) == 5 and plan["times"] and plan["character"]
    assert d["start"].startswith("/kayit?")
    anon.get(d["start"])  # kayıt sayfası planı oturumda tutar
    r = anon.post("/kayit", data={"email": "k@b.com", "password": "sifre1234", "accept": "1", "consent": "1",
                                  "csrf": csrf(anon, "/kayit")}, follow_redirects=False)
    loc = r.headers["location"]
    assert loc.startswith("/kanallar/yeni?")
    q = parse_qs(urlparse(loc).query)
    assert q["ad"] == [plan["names"][0]] and "Uzay gerçekleri" in q["konu"][0] and q["saatler"] == [" ".join(plan["times"])]
    form = html.unescape(anon.get(loc).text)
    assert f'value="{plan["names"][0]}"' in form and "Uzay gerçekleri" in form and plan["times"][0] in form
    _assert_english(TestClient(client.app).get("/en/araclar/kanal-kurucu").text, "/en/araclar/kanal-kurucu")
    assert "/araclar/kanal-kurucu" in client.get("/sitemap.xml").text
