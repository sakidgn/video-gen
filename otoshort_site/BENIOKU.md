# Zaply (site) — kurulum

Yapay zekâ ile kısa video üreten, kredili site. Kullanıcı havale ile kredi yükler, tek video ya da
"otomatik kanal" (her gün belirli saatlerde kendiliğinden video) üretir. Videolar Google'ın Veo modeliyle,
başlık/açıklama Gemini ile yazılır.

Bu klasör kendi başına bir projedir (shitpost otomatiğinden ayrı).

## Bilgisayarda deneme (API'siz, sahte videolarla)
- Windows: **`Siteyi_Ac.bat`**'a çift tıkla (ilk seferde kendi kurulumunu yapar). Güncellemek için **`Guncelle.bat`**.
- Elle: `pip install -r saas/requirements.txt` sonra `SAHTE_AI=1 ADMIN_EPOSTALAR=sen@mail.com python -m saas`
Tarayıcıda http://localhost:8000 → kayıt ol (admin e-postasıyla) → Yönetim'den kendine kredi ver → video üret.

## Öylesine canlıya al (ücretsiz demo yayını)
`Canliya_Al.bat`'ı çalıştır: site bu bilgisayardan Cloudflare'in ücretsiz tüneliyle `https://….trycloudflare.com`
adresinde herkese açılır (hesap, alan adı, sunucu, kart gerekmez). **Vitrin modu**nda çalışır: videolar sahte (para
harcanmaz), ödeme ve yönetim paneli kapalı, e-posta doğrulaması yok, şifre sıfırlama kapalı, arama motorlarına kapalı;
her sayfada "Demo sürüm" şeridi görünür. Pencere kapanınca yayın biter, her açılışta adres değişir. Veriler
`saas_veri_vitrin/` klasöründe kalır. Kayıt olanların e-postaları da orada durur; demo bitince klasörü silebilirsin.

## Erken erişim listesi ve fikir makinesi
Açılış öncesi dönemde (vitrin modunda ya da `.env`'de `ERKEN_ERISIM=1`) ana sayfada **Erken erişim** bölümü ve
telefonda altta sabit bir çağrı çubuğu görünür. E-postasını bırakan, gerçek sitede aynı e-postayla kaydolup
doğrulayınca `ERKEN_ERISIM_HEDIYE` (varsayılan 100) kredi alır. Vitrinde toplanan listeyi gerçek siteye taşımak:
`python -m saas.erken_erisim disari liste.csv --vitrin`, sunucuda `python -m saas.erken_erisim iceri liste.csv`.
Yönetim panelinden de CSV indirilebilir. Listeye katılan herkes kendi sayfasında (`/liste/KOD`) kişiye özel davet
bağlantısı alır; o bağlantıyla gelen biri açılışta kaydolup doğrulayınca davet edene `ERKEN_DAVET_ODULU` (20) kredi,
en fazla `ERKEN_DAVET_SINIRI` (200). Davet eden henüz kaydolmadıysa kredi birikir, kaydolunca yüklenir. Ana sayfadaki **Fikir makinesi** (`saas/fikirler.py`) ziyaretçiye
rastgele fikir verir; "Bu fikirle başla" kayıttan sonra stüdyoyu o fikirle açar.

## Ziyaretçiyi kazanan özellikler
- **Kayıt olmadan senaryo denemesi:** ana sayfada fikir yazılır, yapay zekâ (yalnızca ucuz metin modeli) 8 saniyelik
  senaryoyu yazar; altında "videoya dönüştür" butonu kayda götürür. Kişi başı saatte 6 deneme, günlük toplam
  `DENEME_GUNLUK_SINIR` (varsayılan 300; maliyet tavanı).
- **Karakter kütüphanesi** (/karakterler): görünüş + ses + isteğe bağlı görsel bir kez kaydedilir, stüdyoda ve kanallarda
  tek tıkla seçilir (en fazla 3).
- **Viral altyazı:** altyazı açıkken "Viral" stil kelime kelime renklenen, büyük harfli Shorts altyazısı basar; "Klasik"
  sade cümle altyazısıdır.
- **Onaylı paylaşım:** otomatik kanalda "Onaylı paylaşım" seçilirse video hazır olunca e-posta gelir, video sayfasında
  "Onayla ve paylaş" denince yüklenir; "Paylaşma" denirse hiçbir yere gitmez.

## Abonelikler, süre ve fiyatlar
- **3 abonelik, 3 yapay zekâ** (30 gün, havaleyle; otomatik çekim yok, bitişe 3 gün kala e-posta):
  Başlangıç 299 ₺ → 330 kredi/ay, Veo 3.1 Lite · Pro 749 ₺ → 850 kredi, + Veo 3.1 Fast ·
  Stüdyo 1999 ₺ → 2300 kredi, + Veo 3.1 (1080p). Aboneliği olmayan Ekonomik'i kredi paketiyle kullanır.
  Kullanıcı /kredi'de planı seçip havaleyi bildirir; yönetim panelinde "… aboneliği" rozetiyle görünür, onaylanınca
  plan açılır ve kredisi yüklenir. Kalan kredi devreder.
- **Süre çubuğu** (4–60 sn): 10 sn'ye kadar sabit (Ekonomik 49, Standart 99, Premium 390 kredi), üstü saniye başı
  (+5 / +10 / +39). Uzun video, Veo'nun 4/6/8 sn'lik sahnelerinin üretilip birleştirilmesiyle yapılır.
- **Hediyeler bedava değil, ödemeye bağlı:** davet = arkadaşın ilk yüklemesinin %15'i (gelene %10 fazla),
  erken erişim = ilk yüklemede %20, sadakat = her 400 kredilik videoda 1 Ekonomik video.
- Hepsi `.env` ile değişir (bkz. `.env.ornek`). Maliyete göre kâr ~%40.

## Viral formatlar (video modeli yok, ucuz)
Stüdyoda ve otomatik kanallarda **Format** seçilir: yapay zekâ videosu (Veo), **Mesajlaşma hikâyesi** (iki kişinin
yazışması, iki farklı sesle okunur, balonlar arka plan videosu üstünde belirir) ya da **İtiraf / hikâye** (gönderi
kartı + seslendirme + kelime kelime altyazı). Metni Gemini yazar, seslendirmeyi Gemini TTS (`SES_MODELI`) yapar,
video ffmpeg + libass ile çizilir (`saas/formatlar.py`). Sabit fiyat `KREDI_FORMAT` (19), abonelik gerekmez.
Arka planlar: ffmpeg desenleri (girdap, piksel, pastel) ya da `saas_veri/arka_planlar/*.mp4` içine koyduğun
kendi videoların. Ana sayfadaki örnek videolar: `python araclar/format_ornekleri.py`.

## Ziyaretçiyi yakalayan araçlar
- **Senaryo oynatıcı:** ana sayfadaki kayıtsız denemede senaryo telefon ekranında kelime kelime altyazıyla oynar.
- **Paylaşılabilir senaryo:** her denemenin /s/KOD bağlantısı var (WhatsApp/X butonları). Arkadaşı açınca senaryoyu
  oynar halde görür, "Sen de fikrini yaz" ile siteye gelir. Sayfa arama motorlarına kapalı (noindex).
- **Ücretsiz Kanal Kurucu** (/araclar/kanal-kurucu): konu yazılır; kanal adı, açıklama, karakter, ilk 5 video,
  saatler ve hashtag'ler gelir. "Bu kanalı otomatik kur" kayıttan sonra kanal formunu dolu açar. Kayıtsız deneme
  sınırlarını paylaşır (kişi başı saatte 6, günlük toplam DENEME_GUNLUK_SINIR).

## Fikir ve öneriler
Sitede /oneri sayfası (alt menü, panel menüsü ve ana sayfa): kullanıcılar ve ziyaretçiler fikir, istek ya da sorun
yazar. Gelenler yönetim panelinde **Fikir ve öneriler** (/admin/oneriler) altında, yöneticilere e-posta da gider.

## Gerçek API denemesi (satıştan önce)
1. `.env.ornek` dosyasını `.env` adıyla kopyala, `GEMINI_API_KEY=` satırına Google AI Studio anahtarını yaz
   (fal.ai modeli seçtiysen `FAL_KEY` de). Anahtarı kimseyle paylaşma.
2. `API_Dene.bat`'ı çalıştır. Önce **5** ile sadece anahtarı ve senaryo yazımını dene (neredeyse ücretsiz),
   sonra **1** ile tek bir Ekonomik video üret.
3. Videolar ve rapor `saas_veri_deneme/api_deneme/` klasörüne düşer: süre, çözünürlük, dosya boyutu.
4. Gerçek maliyeti Google/fal.ai faturasından kontrol et; `.env`'deki `MALIYET_*` ve gerekirse `KREDI_*`
   değerlerini güncelle. Yönetim → **Yayına hazırlık** sayfası kâr payını gösterir.

## Gerçek kurulum (sunucu)
Hazır paket: `docker-compose.yml` (site + Caddy), `Caddyfile` (otomatik https sertifikası), `sunucu_kur.sh`
(soru sorarak `.env` oluşturur ve başlatır). Bu kurulum Docker içinde baştan sona denendi.

1. **Google API anahtarı:** https://aistudio.google.com → API key → projede **faturalandırmayı aç** (kart).
   Google Cloud'da **bütçe uyarısı** kur (ör. aylık 50$). Veo'nun ücretsiz kotası yok, her video ücretli.
2. **Sunucu:** Ubuntu 24.04, en az 2 GB RAM'li bir VPS (ör. Hetzner CX22 ~5 €/ay, DigitalOcean, Turhost).
   KVKK metninde yazacağın sunucu firması ve ülkesi budur (`SUNUCU_SAGLAYICI`).
3. **Alan adı:** DNS ayarlarında `A` kaydı → sunucunun IP adresi (www için de aynı). Yayılması birkaç dakika–saat.
4. Sunucuya bağlan (`ssh root@IP`) ve kodu indir:
   ```
   git clone https://github.com/KULLANICI/DEPO.git zaply   # gizli depoysa GitHub token ile
   cd zaply/otoshort_site
   bash sunucu_kur.sh
   ```
   Betik Docker'ı kurar, alan adını/yönetici e-postasını sorar, `GIZLI_ANAHTAR`'ı kendisi üretir ve siteyi başlatır.
5. Kalan ayarları doldur: `nano .env` → SMTP, IBAN, `SIRKET_*` (yasal bilgiler), sonra `docker compose up -d`.
6. Siteye yönetici e-postanla kaydol → **Yönetim → Yayına hazırlık**: kırmızı kalan bir şey olmamalı.
7. **Güncelleme:** `git pull && docker compose up -d --build` (veriler `saas_veri/` klasöründe kalır).
8. **Yedek:** site her gün `saas_veri/yedekler/`e veritabanı yedeği alır; ara sıra bilgisayarına indir:
   `scp -r root@IP:zaply/otoshort_site/saas_veri/yedekler .`
9. Satışa başlamadan önce yasal metinleri bir muhasebeciye/avukata göster.

Faydalı komutlar: `docker compose ps` (durum), `docker compose logs -f site` (günlük),
`docker compose exec site python -m saas.hazirlik` (eksik ayarlar), `docker compose restart site`.

## Google ile giriş (ücretsiz, kart gerekmez)
1. https://console.cloud.google.com → üstten **yeni proje** oluştur (ör. "Zaply").
2. Menüden **Google Auth Platform** (APIs & Services → OAuth consent screen) → **Get started**:
   uygulama adı "Zaply", destek e-postası, **Audience: External**, iletişim e-postası → Create.
3. **Clients → Create client** → Application type: **Web application** → *Authorized redirect URIs*:
   - deneme için `http://localhost:8000/auth/google/donus`
   - canlı site için `https://ALANADIN/auth/google/donus`
4. Çıkan **Client ID** ve **Client secret**'ı `.env`'de `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`'a yaz,
   canlıda `SITE_ADRESI=https://ALANADIN` da yaz.
5. **Audience → Publish app** (yayına al). Sadece ad/e-posta istediğimiz için Google incelemesi gerekmez.

Yeni kullanıcı Google ile ilk girişte kullanım şartları ve KVKK onayını verir; aynı e-postayla açılmış hesap
varsa Google o hesaba bağlanır.

## Otomatik paylaşım (YouTube / TikTok / Instagram)
Kullanıcı **Bağlantılar** sayfasından hesabını bağlar, otomatik kanalında platformları seçer; video hazır olunca
başlığı, açıklaması ve hashtag'leriyle yüklenir (tek videolar video sayfasından da gönderilebilir). Jetonlar
veritabanında şifreli durur (`GIZLI_ANAHTAR`'ı değiştirirsen herkes yeniden bağlanır). `SAHTE_AI=1` iken anahtarsız
"demo" bağlantıyla akış denenebilir. Hepsi `https://` adresli canlı site ister.

- **YouTube Shorts:** Google girişindeki projede **YouTube Data API v3**'ü etkinleştir, istemciye
  `https://ALANADIN/baglan/youtube/donus` yönlendirmesini ekle, izinlere `youtube.upload` ve `youtube.readonly` ekle.
  Bu izinler hassas olduğu için Google **uygulama doğrulaması** ister (birkaç hafta); doğrulanana kadar yüklenen
  videolar gizli kalır ve en fazla 100 test kullanıcısı bağlanabilir. API kotası günde ~100 yüklemeye yeter;
  fazlası için Google'dan kota artışı istenir.
- **TikTok:** https://developers.tiktok.com → uygulama oluştur → **Login Kit** + **Content Posting API**
  (Direct Post) ekle, yönlendirme `https://ALANADIN/baglan/tiktok/donus`. Anahtarları `.env`'de `TIKTOK_CLIENT_KEY` /
  `TIKTOK_CLIENT_SECRET`'a yaz. TikTok incelemesi (audit) bitene kadar videolar yalnızca **"sadece ben"** görünür.
- **Instagram Reels:** https://developers.facebook.com → uygulama → **Instagram API with Instagram Login** →
  izinler `instagram_business_basic`, `instagram_business_content_publish`, yönlendirme
  `https://ALANADIN/baglan/instagram/donus`. `INSTAGRAM_APP_ID` / `INSTAGRAM_APP_SECRET`'ı yaz. Kullanıcının
  hesabı **İşletme ya da İçerik üreticisi** olmalı. Meta **App Review**'dan geçene kadar sadece uygulamaya eklenen
  test hesapları bağlanabilir. Instagram videoyu siteden kendisi indirir (`/yayin/dosya/…`, 3 saat geçerli imzalı adres).

## İngilizce site
Site Türkçe ve İngilizce. İngilizce sayfalar `/en/...` adresinde (arama motorları için ayrı adres, hreflang ve
sitemap hazır); menüdeki **EN/TR** düğmesi ve alt bilgideki dil seçici çerezle dili hatırlar. Tarayıcısı Türkçe
olmayan ziyaretçiye üstte "View in English" önerisi çıkar (otomatik yönlendirme yapılmaz). Hesabın dili e-postalara
da uygulanır (Hesabım → Dil). Yasal metinler bağlayıcı dil olarak Türkçe kalır; İngilizce sayfada bunu söyleyen bir
not görünür. Yönetim paneli Türkçe.

Yeni metin eklerken şablonda `{{ _('Türkçe metin') }}` (HTML içeriyorsa `_h`), kodda `i18n.t("…")` kullan ve
İngilizcesini `saas/i18n_en.py`'ye yaz. Eksik çeviri: `python -m saas.i18n_keys` (testler de yakalar).
Tanıtım filminin İngilizce sürümü: `araclar/film/yap.sh <chromium> "" "" en` → `hero-en.mp4`, `hero-m-en.mp4`, `og-en.png`.

## E-posta (doğrulama, şifre sıfırlama, bildirimler)
Kayıt olan herkes e-postasını doğrular (hediye kredi doğrulamada yüklenir); şifremi unuttum ve bildirim e-postaları
da buradan gider. Ücretsiz bir SMTP servisi yeterli (ör. Brevo günde 300 e-posta ücretsiz): hesap aç, alan adını
doğrula, SMTP bilgilerini `.env`'deki `SMTP_*` satırlarına yaz. Boş bırakırsan e-postalar gönderilmez,
`saas_veri/epostalar` klasörüne kaydedilir (deneme modunda sitede "E-postayı aç" bağlantısı çıkar).

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
- Otomatik paylaşım için platform onayları (Google doğrulaması, TikTok audit, Meta App Review).
