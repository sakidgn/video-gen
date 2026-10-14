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


def signup(c, email, pw="sifre1234", verify=True):
    r = c.post("/kayit", data={"email": email, "password": pw, "name": "Ali", "accept": "1", "consent": "1",
                               "csrf": csrf(c, "/kayit")}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/panel"
    if verify:
        with db.session() as s:
            s.scalar(select(User).where(User.email == email)).email_verified = True


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
        assert u.credits == 5 and u.google_sub is None


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
