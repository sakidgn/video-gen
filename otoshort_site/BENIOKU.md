# Otoshort (site) — kurulum

Yapay zekâ ile kısa video üreten, kredili site. Kullanıcı havale ile kredi yükler, tek video ya da
"otomatik kanal" (her gün belirli saatlerde kendiliğinden video) üretir. Videolar Google'ın Veo modeliyle,
başlık/açıklama Gemini ile yazılır.

Bu klasör kendi başına bir projedir (shitpost otomatiğinden ayrı).

## Bilgisayarda deneme (API'siz, sahte videolarla)
- Windows: **`Siteyi_Ac.bat`**'a çift tıkla (ilk seferde kendi kurulumunu yapar). Güncellemek için **`Guncelle.bat`**.
- Elle: `pip install -r saas/requirements.txt` sonra `SAHTE_AI=1 ADMIN_EPOSTALAR=sen@mail.com python -m saas`
Tarayıcıda http://localhost:8000 → kayıt ol (admin e-postasıyla) → Yönetim'den kendine kredi ver → video üret.

## Gerçek kurulum (sunucu)
1. **Google API anahtarı:** https://aistudio.google.com → API key oluştur → projede **faturalandırmayı aç** (kart).
   Google Cloud'da **bütçe uyarısı** kur (ör. aylık 50$). Veo'nun ücretsiz kotası yok, her video ücretli.
2. **Sunucu:** Docker çalıştıran küçük bir VPS (ör. 2 GB RAM). Bir alan adı al ve sunucuya yönlendir.
3. `.env.ornek` dosyasını `.env` olarak kopyala, doldur (`GIZLI_ANAHTAR` uzun ve rastgele olmalı).
4. Çalıştır:
   ```
   docker build -t otoshort .          # bu klasörün içinden
   docker run -d --restart always --env-file .env -v /srv/otoshort:/veri -p 8000:8000 otoshort
   ```
5. Önüne HTTPS için Caddy koy (en kolayı): `caddy reverse-proxy --from alanadin.com --to localhost:8000`
6. Yasal sayfalardaki `[ŞİRKET UNVANI]`, `[ADRES]`, `[E-POSTA]`, `[TARİH]` yerlerini doldur
   (`saas/templates/yasal_*.html`). Satışa başlamadan önce bir muhasebeciye/avukata göster.

## Google ile giriş (ücretsiz, kart gerekmez)
1. https://console.cloud.google.com → üstten **yeni proje** oluştur (ör. "Otoshort").
2. Menüden **Google Auth Platform** (APIs & Services → OAuth consent screen) → **Get started**:
   uygulama adı "Otoshort", destek e-postası, **Audience: External**, iletişim e-postası → Create.
3. **Clients → Create client** → Application type: **Web application** → *Authorized redirect URIs*:
   - deneme için `http://localhost:8000/auth/google/donus`
   - canlı site için `https://ALANADIN/auth/google/donus`
4. Çıkan **Client ID** ve **Client secret**'ı `.env`'de `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`'a yaz,
   canlıda `SITE_ADRESI=https://ALANADIN` da yaz.
5. **Audience → Publish app** (yayına al). Sadece ad/e-posta istediğimiz için Google incelemesi gerekmez.

Yeni kullanıcı Google ile ilk girişte kullanım şartları ve KVKK onayını verir; aynı e-postayla açılmış hesap
varsa Google o hesaba bağlanır.

## Günlük kullanım (yönetici)
- **Yönetim** sayfası: bekleyen havaleler → banka hesabında parayı gördükten sonra **Onayla**.
- Elle kredi: arkadaşlarına deneme kredisi vermek ya da düzeltme için.
- Video üretilemezse kredi otomatik iade edilir.

## Fiyat / maliyet (8 sn video)
| Kalite | Google maliyeti | Kullanıcıdan düşen |
|---|---|---|
| Ekonomik (Lite 720p) | ~0,40 $ | 35 kredi |
| Standart (Fast 720p) | ~0,80 $ | 65 kredi |
| Premium (1080p) | ~3,20 $ | 250 kredi |

Fiyatlar `saas/config.py` → `QUALITIES` ve `PACKAGES`. Model adları Google değiştirirse `.env`'de
`MODEL_LITE`, `MODEL_FAST`, `MODEL_STANDARD` ile güncellenir.

## Sonraki adımlar
- Kartla ödeme (iyzico / PayTR) — şirket kurulunca.
- YouTube / TikTok / Instagram'a otomatik paylaşım (resmi API onayları gerekiyor).
- E-posta bildirimleri, şifre sıfırlama, Google ile giriş.
