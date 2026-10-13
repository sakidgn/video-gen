# Otoshort (site) — kurulum

Yapay zekâ ile kısa video üreten, kredili site. Kullanıcı havale ile kredi yükler, tek video ya da
"otomatik kanal" (her gün belirli saatlerde kendiliğinden video) üretir. Videolar Google'ın Veo modeliyle,
başlık/açıklama Gemini ile yazılır.

## Bilgisayarda deneme (API'siz, sahte videolarla)
```
pip install -r saas/requirements.txt
SAHTE_AI=1 ADMIN_EPOSTALAR=sen@mail.com python -m saas
```
Tarayıcıda http://localhost:8000 → kayıt ol (admin e-postasıyla) → Yönetim'den kendine kredi ver → video üret.

## Gerçek kurulum (sunucu)
1. **Google API anahtarı:** https://aistudio.google.com → API key oluştur → projede **faturalandırmayı aç** (kart).
   Google Cloud'da **bütçe uyarısı** kur (ör. aylık 50$). Veo'nun ücretsiz kotası yok, her video ücretli.
2. **Sunucu:** Docker çalıştıran küçük bir VPS (ör. 2 GB RAM). Bir alan adı al ve sunucuya yönlendir.
3. `saas/.env.ornek` dosyasını `saas/.env` olarak kopyala, doldur (`GIZLI_ANAHTAR` uzun ve rastgele olmalı).
4. Çalıştır:
   ```
   docker build -f saas/Dockerfile -t otoshort .
   docker run -d --restart always --env-file saas/.env -v /srv/otoshort:/veri -p 8000:8000 otoshort
   ```
5. Önüne HTTPS için Caddy koy (en kolayı): `caddy reverse-proxy --from alanadin.com --to localhost:8000`
6. Yasal sayfalardaki `[ŞİRKET UNVANI]`, `[ADRES]`, `[E-POSTA]`, `[TARİH]` yerlerini doldur
   (`saas/templates/yasal_*.html`). Satışa başlamadan önce bir muhasebeciye/avukata göster.

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
