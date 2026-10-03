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
   "Daha önce yapmadığın komik bir prompt yaz." yazılır (`chatgpt_mesaj`). Kullanıcı başka hiçbir şey eklenmesin istedi.
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
4. **Zamanlama:** menü 9 → `zamanla.bat`/`zamanla.ps1`: günde 3 görev (WakeToRun, uykudan uyandırır), 9→3 tek seferlik
   paylaşmayan uyandırma testi. `--uyut`: kimse başında değilse iş bitince bilgisayarı uyutur. Başta fare 1 px oynatılıp
   ekran açılır. Kullanıcı "uyanınca şifre sorma"yı kapattı (kilit ekranına program yazamaz).

## Durum (son konuşma)
- Paylaşım çalışıyor (kullanıcı "gayet iyi" dedi). IG AI etiketi açılmamıştı: anahtar artık etiketle aynı satırdaki
  en yakın anahtar seçilip gerçek fare tıklamasıyla açılıyor (`browser.turn_on_ai_label`). Paylaşım öncesi
  `*_paylasim_oncesi.png` ekran görüntüsü kaydediliyor. Çıkan soru pencerelerine `browser.answer_dialogs` zararsız
  cevap veriyor (Tamam/Şimdi değil/Yine de paylaş...; "At/Sil/Kapat" asla).
- Video üretimi çalışıyor, video kalitesi iyi.
- Son düzeltmeler henüz gerçek Windows'ta doğrulanmadı: Chrome'u öne getirme (`browser._focus_window`, önceden hep
  "Chrome öne gelmedi" veriyordu → hep CDP yedeğiyle gönderiliyordu), uyanınca ekranı açma, kilitli kutu algılama.
- **Sıradaki adımlar:** 1) Menü 5 ile ilk gerçek paylaşım (YouTube/TikTok/IG hiç gerçekte denenmedi).
  2) 9→3 uyandırma testi. 3) 9→1 ile günde 3 otomatik çalıştırma.

## Geliştirme notları
- Testler: `python -m pytest -q` (sahte Gemini client). Tarayıcı akışları için scratchpad'de sahte Gemini/ChatGPT/Studio
  sayfalarıyla `xvfb-run` + `TARAYICI_YOLU=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`, `TARAYICI_EK_ARGS=--no-sandbox`,
  `AYRIK_MOD_TEST=1` kullanılarak uçtan uca denendi.
- Python string içinde JS yazarken `\n`/`\s` için raw string kullan (iki kere satır sonu hatası çıktı).
- `.bat` dosyaları CRLF olmalı; `if (...)` blokları içinde parantezli metin kullanma.
