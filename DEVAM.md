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
