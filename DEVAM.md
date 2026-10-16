# Devam notu (yeni sohbet için)

Yeni bir Claude sohbetinde bu dosyayı okut: "DEVAM.md'yi oku, kaldığımız yerden devam edelim."

## Kullanıcı
- Türkçe, kısa ve samimi konuşuyor ("bro", "kanka"). Uzun açıklama sevmiyor; adım adım, net talimat ister.
- Windows'ta çalışıyor, kod bilgisi az. Komut yazdırma; her şey `menu.bat` ve çift tıklamayla olmalı.
- Güncellemeleri `menu.bat` → 7 (GitHub'dan zip indirir) ile alıyor. Değişiklik → commit → `claude/oto-reels-uretici-gemini-sucu7b` dalına push.
- Hata olunca menü 8 ile `cikti/son_calisma.txt` ve son klasörü açıp ekran görüntüsü/dosya atıyor. Tahmin yerine bu kayıtlara bak.

## Sistem ne yapıyor
Spoderman & Orange shitpost kanalı (YouTube Shorts, TikTok, Instagram). `python -m shitpost uret spoderman`:
1. **Senaryo:** Tarayıcıdaki ChatGPT projesi "Shitpost gen" (`senaryo.chatgpt_proje`) açılır, sadece
   "Daha önce yapmadığın komik bir prompt yaz. Videoda küfür, filigran ve ekranda kullanıcı adı olmasın." yazılır (`chatgpt_mesaj`). Kullanıcı bundan başka hiçbir şey eklenmesin istedi.
   Başlık/açıklama/hashtag Gemini ücretsiz API'sinden; API yoğunsa basit başlıkla devam (videoyu durdurmaz).
2. **Video (Gemini web, iki AI Pro hesabı C:\BotProfil1 ve C:\BotProfil2):**
   - Google, CDP/Playwright bağlıyken yüklenen sayfadan gelen video isteğini "high traffic / full capacity /
     encountering an error" diye reddediyor (elle aynı prompt çalışıyor). Bu yüzden `video_web._generate_hands_off`:
     a) Hazırlık (bağlı): soldaki "Videolar" bölümü, Dikey seçimi, Dikey için klavye yolu öğrenilir (Tab/ok/Shift+Tab).
     b) Chrome kapatılır, Videolar URL'siyle **bağlantısız** yeniden açılır; Windows `user32` ile gerçek klavye:
        Dikey tuşları + panodan Ctrl+V + Enter.
     c) Sonra 20 sn'de bir kısa bağlanıp video beklenir ve indirilir.
   - Chrome, Playwright ile değil normal başlatılıp CDP ile bağlanılıyor (`browser._open_real_chrome`). Pencere görünür
     olmalı (ekran dışı pencerede Gemini videoyu yarıda kesiyordu).
   - Telif: promptta "Spoderman" varsa önce olduğu gibi gönderilir; telif reddinde ad "the costume guy" yapılıp görünüş
     tarifi başa eklenir (eski "Blocky Guy" Minecraft karakteri çıkarıyordu).
   - Kilitli/soluk yazı kutusu = o hesabın günlük video hakkı doldu → sıradaki hesap. "Yoğunum" → diğer hesap, 5 dk bekle, 3 tur.
   - Yatay gelen video ffmpeg (imageio-ffmpeg) ile 1080x1920 bulanık arka planlı dikeye çevrilir (`postprocess.py`).
3. **Paylaşım (tarayıcı, PAYLASIM_PROFILI):** `youtube_web` (Studio: #shorts, çocuklara değil, AI etiketi, herkese açık),
   `tiktok_web`, `instagram_web`. Google Cloud kurulumunu kullanıcı yapamadı, API yolu kullanılmıyor.
4. **Zamanlama:** menü 9 → `zamanla.bat`/`zamanla.ps1`: günde 5 görev (09:45 12:45 15:45 18:45 21:15; Instagram sadece 12:45 18:45 21:15, diğerleri `--atla instagram_web`) (WakeToRun, uykudan uyandırır), 9→3 tek seferlik
   paylaşmayan uyandırma testi. `--uyut`: kimse başında değilse iş bitince bilgisayarı uyutur. Başta fare 1 px oynatılıp
   ekran açılır. Kullanıcı "uyanınca şifre sorma"yı kapattı (kilit ekranına program yazamaz).

## Durum (son konuşma)
- Paylaşım çalışıyor (kullanıcı "gayet iyi" dedi). IG AI etiketi açılmamıştı: anahtar artık etiketle aynı satırdaki
  en yakın anahtar seçilip gerçek fare tıklamasıyla açılıyor (`browser.turn_on_ai_label`). Paylaşım öncesi
  `*_paylasim_oncesi.png` ekran görüntüsü kaydediliyor. Çıkan soru pencerelerine `browser.answer_dialogs` zararsız
  cevap veriyor (Tamam/Şimdi değil/Yine de paylaş...; "At/Sil/Kapat" asla).
- Her şey çalışıyor ve OTOMATİKTE: uyandırıp üretip 3 platforma paylaşma gerçek PC'de doğrulandı.
  Menü başında `zamanla.ps1 -Durum` satırı "OTOMATIK: AKTIF (5 video/gun ...) Siradaki: ..." gösteriyor.
- Hata dayanıklılığı: tüm çalışma 3 kere baştan denenir (`__main__._uret`, 80 dk bütçe), paylaşılamayan platform
  2 kere daha denenir (`pipeline.PUBLISH_RETRIES`). 3'ünde de olmazsa Türkçe açıklama `cikti/sorunlar.txt`'ye yazılır
  (menü 8 bunu da açar). Gemini "hard time fulfilling" = ret → isimler değiştirilmiş prompt → yeni ChatGPT promptu.
- Başlık/açıklama kısa ve emojili (kalın Unicode yazı bilerek yok: Türkçe harf yok, aramada görünmüyor).
- Veo videoya uydurma @kullanıcı adı çiziyordu: Gemini promptunun sonuna `script.CLEAN_FRAME` ekleniyor.
  Köşedeki Google "Veo" logosu kaldırılmıyor (AI işareti).
- **Sıradaki:** İlk günlerin paylaşımlarını izle; `sorunlar.txt`'ye bak. Kullanıcı sonra başka kanallar/işler isteyebilir.

## Geliştirme notları
- Testler: `python -m pytest -q` (sahte Gemini client). Tarayıcı akışları için scratchpad'de sahte Gemini/ChatGPT/Studio
  sayfalarıyla `xvfb-run` + `TARAYICI_YOLU=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`, `TARAYICI_EK_ARGS=--no-sandbox`,
  `AYRIK_MOD_TEST=1` kullanılarak uçtan uca denendi.
- Python string içinde JS yazarken `\n`/`\s` için raw string kullan (iki kere satır sonu hatası çıktı).
- `.bat` dosyaları CRLF olmalı; `if (...)` blokları içinde parantezli metin kullanma.

## SaaS sitesi — marka adı **Cutless** (cutless.app); kod klasörü hâlâ `otoshort_site/` (güncelleyici bu yola bağlı, değiştirme)
- FastAPI + SQLite + Jinja; kredili video üretimi (Veo API), otomatik kanallar, havale ile kredi, yönetim paneli.
- Tasarım: neon tema bırakıldı → zarif koyu tema (sıcak siyah #0c0b0a, fildişi #f4efe6, şampanya #d8b98a). Başlık fontu
  **Cormorant Garamond** (Instrument Serif "basık" bulundu), metin **Plus Jakarta Sans**, düz rakamlar (lining-nums).
- Ana sayfa: tam ekran tanıtım filmi (`static/hero/hero.mp4` + telefon için `hero-m.mp4`; scratchpad'deki film.html'den kare kare
  render edilip ffmpeg ile kodlanır), ürün vitrini (`static/shots/studio.jpg`), kayan fikir şeritleri, bento özellikler.
  Kaydırınca geride kalan bloklar hafifçe bulanıklaşır (kullanıcı "fazla" dedi → üst üçte birde, en fazla 6px), Lenis ile
  yumuşak kaydırma (`static/vendor/lenis.min.js`), başlıklar kelime kelime belirir, footer'da büyük silik marka yazısı.
- Özellikler (Ekim 2026): davet programı (/davet, /d/KOD; ödül ilk onaylı havalede, DAVET_ODULU/DAVET_HEDIYE),
  promosyon kodları (yönetimden), düşük bakiye uyarısı, /videolar (filtre+arama+sayfa), benzerini/düzenleyip üret,
  kanalda "şimdi üret", stüdyoda yapay zekâ fikir önerisi (/api/fikirler), telefonda dosyalı paylaşım (Web Share),
  yönetimde 14 günlük grafikler + kâr tahmini (VIDEO_COST_USD × DOLAR_KURU), ana sayfada maliyet hesaplayıcı.
  Güvenlik: sıkı CSP (satır içi script YOK — yeni JS fx.js'e), /saglik, robots/sitemap, PWA manifest, günlük DB yedeği.
- Video modelleri: her kalite kademesi ayrı firma olabilir (`MODEL_LITE/FAST/STANDARD` = `google:<veo>` ya da `fal:<uç nokta>`,
  `saas/ai.py` FalVideo). Referans karakter görseli (Veo kendisi; fal için `MODEL_X_REF`), altyazı (Gemini döküm → ASS →
  ffmpeg/libass, ham dosya `<id>-ham.mp4` kalır), Keşfet galerisi (/kesfet, kullanıcı izniyle, yönetim öne çıkarır/kaldırır).
- Otomatik paylaşım: /baglantilar (OAuth; `saas/social.py` YouTube/TikTok/Instagram + SAHTE_AI'de DemoClient), jetonlar
  `saas/secretbox.py` ile şifreli (cryptography paketi bu ortamda bozuk → stdlib). Kanal `publish_to`, `Publication` kuyruğu
  işçide (`saas/publisher.py`, 3 deneme, 3 dk arayla). Instagram videoyu `/yayin/dosya/<imzalı jeton>`'dan indirir.
  Gerçek kullanım için platform onayları gerekiyor (BENIOKU'da adımlar).
- İngilizce site: `saas/i18n.py` (LangMiddleware: /en önekini atar, "dil" çerezi; contextvar ile `i18n.t`), şablonlarda
  `_()`/`_h()`/`_db()` (veritabanındaki Türkçe kalıplar), çeviriler `saas/i18n_en.py`, eksik kontrolü `saas/i18n_keys.py`.
  User.lang e-posta dili. Herkese açık sayfalar `L('/yol')` ile /en adresi alır. Film/og/stüdyo görselinin -en sürümleri var.
- Yayına hazırlık (Ekim 2026): yönetimde /admin/hazirlik kontrol listesi (`saas/hazirlik.py`, CLI de var), yasal satıcı
  bilgileri SIRKET_* env'den, `API_Dene.bat`/`saas/api_dene.py` gerçek API denemesi, sunucu paketi (docker-compose +
  Caddy https + `sunucu_kur.sh`, Docker içinde denendi), güvenlik düzeltmeleri (yönetici yetkisi sadece doğrulanmış
  e-postaya, Google ile ele geçirme önlemi, şifre değişince diğer oturumlar düşer, atomik havale onayı, kayıt hız sınırı),
  yönetimde kullanıcı arama/detay/askıya alma, başarısız işlerin teknik hatası (Job.error_detail), havale bildiriminde
  yöneticiye e-posta.
- Ziyaretçi/kullanıcı bağlama (Ekim 2026): vitrin modu + Canliya_Al.bat (Cloudflare hızlı tüneli), erken erişim listesi
  (`saas/waitlist.py`, davet kodlu, /liste/KOD), fikir makinesi (`saas/fikirler.py`), hazır şablonlar (`saas/sablonlar.py`,
  /sablonlar herkese açık), içerik takvimi (/takvim), paylaşım metni düzenleme, hız optimizasyonu (gzip, önbellek, WebP).
  Kullanıcı kredi/bütçe ayarlarını şimdilik sormamamı istedi.
- Dönüşüm özellikleri (Ekim 2026): ana sayfada kayıt olmadan senaryo denemesi (`/api/deneme-senaryo`, sadece metin,
  IP başına saatte 6 + `DENEME_GUNLUK_SINIR`), karakter/maskot kütüphanesi (`saas/karakter.py`, /karakterler; kanal
  `cast_ids` ile tutar, düzenleme sonraki videolara yansır), viral karaoke altyazı (`media.build_ass(style="viral")`,
  kelime kelime renkli; Job/Channel.subtitle_style), onaylı paylaşım (Channel.approval → Publication "onay" durumu,
  e-posta + /video/ID'de "Onayla ve paylaş"). Altyazı fontu aile adı "Plus Jakarta Sans ExtraBold" olmalı (libass).
- Fiyat/hediye (Ekim 2026, kullanıcı "bizden para gitmesin" dedi): Veo 3.1 Lite/Fast/standart → 39/75/290 kredi,
  paketler 250/525/1100. Bedava kredi yok: davet = ilk yüklemenin %15'i (davet edene) / %10'u (gelene), erken erişim =
  ilk yüklemede %20, sadakat = her 400 kredilik videoda 1 Ekonomik (`growth.first_topup_rewards`, `growth.loyalty`).
  Emojiler arayüzden kalktı (şablon kartında tarz illüstrasyonu, kayan şeritte serif yazı, CSS `.mascot` portakal).
- Abonelik + süre (Ekim 2026): 3 plan (`config.PLANS`, `saas/abonelik.py`; her biri bir Veo kademesi açar, havaleyle
  30 gün, `TopUp.plan`), aboneliksiz sadece Ekonomik. Süre çubuğu 4–60 sn (`config.price`, `plan_clips`): 10 sn'ye kadar
  sabit, üstü saniye başı; çok sahne `worker.make_scenes` + `media.join_clips`. "Neler üretebilirsin" örnekleri
  (`fikirler.USE_CASES`), fikir/öneri formu (/oneri, `Feedback`, /admin/oneriler).
- Dikkat çekici araçlar: senaryo oynatıcı (`_phone_player.html`, fx.js `playScript`), paylaşılabilir senaryo
  (/s/KOD, `SharedScript`), ücretsiz Kanal Kurucu (/araclar/kanal-kurucu, `ai.channel_plan`, kayıtta `session['kanal']`).
- Viral formatlar: `Job/Channel.format` ("", "sohbet", "hikaye") + `background`; `worker.make_format`,
  `ai.write_format` + `ai.speak` (Gemini TTS), çizim `formatlar.chat_ass/story_ass/render`. Ana sayfada #formatlar dikey
  kart vitrini (örnek videolar static/formatlar, `araclar/format_ornekleri.py`). Telefonda ana sayfa ~10 ekran.
- Kullanıcı tasarımda "yapmacık" olmamasını, en iyisini istedi; ekran görüntüsüyle "tamam" diyene kadar iterasyon.
- Kullanıcının PC'sinde ayrı klasör: Masaüstü\\Otoshort Site (yeni kurulumda "Cutless Site") (shitpost klasöründeki `site_kur.bat` → `python -m shitpost site-kur`
  indirir, eski `saas/` ve `site_dene.bat` kalıntılarını siler). Shitpost `guncelle` `otoshort_site/`'ı atlar.
- Site klasöründe: `Siteyi_Ac.bat` (kendi .venv'ini kurar; SAHTE_AI=1, admin@deneme.com, 1000 deneme kredisi),
  `Guncelle.bat` (`python -m saas.guncelle`, .env ve saas_veri* korunur).
- Hesap: e-posta doğrulama (hediye kredi doğrulamada), şifremi unuttum, Google ile giriş, /hesap (ad, şifre, bildirim, hesabı sil),
  bildirim e-postaları (`saas/mailer.py`; SMTP yoksa saas_veri/epostalar'a kaydeder, demo modda "E-postayı aç" bağlantısı).
- Testler: `otoshort_site/tests/test_saas.py` (kökten `python -m pytest` hepsini çalıştırır). Ekran görüntüsü için Playwright + swiftshader (scratchpad betikleri).
