# Oto Shitpost Üretici

Otomatik, sesli, dikey (9:16) shitpost videoları üretir ve YouTube Shorts, TikTok ve Instagram Reels'te paylaşır. Birden fazla kanalı destekler.

```
senaryo (Gemini API, ücretsiz)  →  video (Gemini uygulaması / Veo, AI Pro hesapların)  →  YouTube API + TikTok/IG tarayıcı
```

- **Tekrar etmez:** Her kanalın `gecmis.json` dosyası tutulur. Son 40 senaryo "bunları tekrarlama" diye prompta eklenir, son 5 tema tekrar seçilmez.
- **Birden fazla Gemini hesabı:** Bir hesabın günlük video hakkı bitince otomatik olarak sıradakine geçer. Hepsi bitince o gün durur.
- **Hata olunca ekran görüntüsü:** Bir adım patlarsa `cikti/<kanal>/<tarih>/hata_*.png` dosyasına ekran görüntüsü kaydedilir.
- **Video motorları:** `gemini_web` (Gemini uygulaması, kart gerekmez) ya da `api` (Veo API, kart gerekir, daha sağlam, GitHub Actions'ta da çalışır). Motor `kanal.yaml` içinden seçilir.

## Kurulum (Windows, bir kere)

1. [Python 3.11+](https://www.python.org/downloads/) kur. Kurarken "Add to PATH" kutusunu işaretle.
2. Projeyi indir (GitHub → Code → Download ZIP ya da `git clone`) ve klasörde bir terminal aç:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   copy .env.example .env
   ```
3. **Gemini API anahtarı (ücretsiz, kart istemez):** https://aistudio.google.com → Get API key → `.env` içindeki `GEMINI_API_KEY=` satırına yapıştır.
4. **Tarayıcı profillerine giriş yap.** Chrome'un kurulu olması lazım. Her Pro hesabı için ayrı bir profil klasörü açılıyor:
   ```
   python -m shitpost giris C:\BotProfil1
   python -m shitpost giris C:\BotProfil2 --sadece-gemini
   ```
   Açılan pencerede 1. profilde Gemini (1. Pro hesap), TikTok ve Instagram'a, 2. profilde sadece Gemini'ye (2. Pro hesap) giriş yap. Sonra terminale dönüp ENTER'a bas. Bu klasörler `.env` içindeki `GEMINI_PROFILLER` ve `PAYLASIM_PROFILI` değerleriyle aynı olmalı.
5. **YouTube:**
   1. https://console.cloud.google.com adresinde bir proje aç. Kart istemez.
   2. "YouTube Data API v3"ü etkinleştir.
   3. OAuth consent screen'i "External" seç, kendi mailini test user olarak ekle, sonra "Publish app" yap. Bunu yapmazsan token 7 günde bir düşer.
   4. Credentials → OAuth client ID → Desktop app. Oluşan dosyayı indirip proje klasörüne `client_secret.json` adıyla koy.
   5. `python -m shitpost youtube-yetki spoderman` komutunu çalıştır ve açılan pencerede kanalını seç.

## Kullanım

```
python -m shitpost uret spoderman --kuru     # üret ama paylaşma, cikti\ klasörüne bak
python -m shitpost uret spoderman            # üret ve 3 platformda paylaş
python -m shitpost uret spoderman --adet 3
```

Çalışırken Chrome penceresi açılıp kapanacak, bu normal. Videonun üretilmesi birkaç dakika sürüyor.

## Otomatik çalıştırma (Windows Görev Zamanlayıcı)

`calistir.bat` üretir ve paylaşır, çıktıyı `kayit.txt` dosyasına yazar.

1. Başlat → "Görev Zamanlayıcı" → Temel Görev Oluştur.
2. Tetikleyici: Günlük, örneğin 10:00. Aynı görevi farklı saatler için (15:00, 20:00) tekrar ekle.
3. Eylem: Program başlat → `calistir.bat` dosyasını seç. "Başlangıç yeri" alanına proje klasörünü yaz.
4. Bilgisayar o saatte açık ve senin kullanıcın oturum açmış olmalı, çünkü tarayıcı görünür modda çalışıyor.

Günde kaç video çıkacağını hesap sayısı × `GEMINI_GUNLUK_LIMIT` belirler. Kota dolmuşsa görev hiçbir şey yapmadan çıkar.

## Yeni kanal açmak

1. `kanallar/spoderman/` klasörünü `kanallar/yeni_kanal/` olarak kopyala ve içindeki `gecmis.json` dosyasını sil.
2. `kanal.yaml` içinde karakterleri, stili, temaları, hashtag'leri ve `token_env` değerini değiştir.
3. `python -m shitpost youtube-yetki yeni_kanal` komutunu çalıştır.
4. TikTok ve IG hesabı farklıysa yeni bir paylaşım profili aç (`giris C:\BotProfil3`). Şimdilik `PAYLASIM_PROFILI` tek bir değer; ikinci kanal geldiğinde kanal başına profil desteği ekleriz.
5. `calistir.bat` dosyasına bir satır ekle: `python -m shitpost uret yeni_kanal >> kayit.txt 2>&1`.

## Bilinmesi gerekenler

- **Kırılganlık:** Gemini, TikTok ve Instagram adımları web arayüzünü tıklayarak çalışıyor. Site tasarımı değişirse bozulabilir. Bozulursa `hata_*.png` ekran görüntüsünü bana at, düzeltirim.
- **Hesap riski:** Google, TikTok ve Meta otomatik kullanımı kurallarında yasaklıyor. Günde birkaç video gibi düşük tempoda risk düşük ama sıfır değil. Ana hesaplarınla değil, bu iş için açtığın hesaplarla kullanman daha güvenli.
- **Kart bulunca:** `kanal.yaml` içinde `motor: api` yap. Karakter referans görselleri kullanılır (`python -m shitpost karakter spoderman`), sonuç daha tutarlı olur ve GitHub Actions'ta bilgisayarın kapalıyken çalışabilir.
- **Telif:** Karakterler markalı isimleriyle değil, "bootleg / parodi" tarifleriyle çiziliyor.
