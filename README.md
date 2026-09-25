# Oto Shitpost Üretici

Gemini + Veo ile otomatik, sesli, dikey (9:16) shitpost videoları üretir ve YouTube Shorts, TikTok ve Instagram Reels'te paylaşır. Birden fazla kanalı destekler.

```
senaryo (Gemini, JSON)  →  ilk kare görseli (karakter referanslarıyla)  →  Veo 3.1 (sesli 8 sn video)  →  paylaşım
```

- **Tekrar etmez:** Her kanalın `gecmis.json` dosyası tutulur, son 40 senaryo özeti "bunları tekrarlama" diye prompta eklenir. Son 5 tema da tekrar seçilmez.
- **Karakterler tutarlı kalır:** Her karakterin bir referans görseli var (`kanallar/<kanal>/karakterler/`). İlk kare bu görsellerle üretilir, Veo videoyu bu kareden başlatır.
- **Güvenlik filtresi:** Veo videoyu reddederse yeni bir senaryoyla bir kez daha dener.
- **AI etiketi:** YouTube'da `containsSyntheticMedia`, TikTok'ta `isAIGenerated` otomatik işaretlenir.

## Kurulum

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # anahtarları doldur
```

| Ne | Nereden |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio → API key. Veo ücretli olduğu için faturalandırmanın açık olması gerekir. |
| YouTube | Google Cloud Console'da bir proje aç, **YouTube Data API v3**'ü etkinleştir, OAuth istemcisi oluştur (tür: *Desktop app*), `client_secret.json` dosyasını indir. |
| `AYRSHARE_API_KEY` | ayrshare.com → TikTok ve Instagram hesaplarını bağla. Instagram'ın Business/Creator hesabı olması gerekir. |

## Kullanım

```bash
python -m shitpost karakter spoderman            # karakter referanslarını üret (bir kere), beğenmezsen --yenile
python -m shitpost youtube-yetki spoderman       # tarayıcıda YouTube kanalını seç (bir kere)
python -m shitpost uret spoderman --kuru         # üret ama paylaşma, cikti/ klasörüne bak
python -m shitpost uret spoderman                # üret ve paylaş
python -m shitpost uret spoderman --adet 3
```

Karakter görsellerini kendin de koyabilirsin: `kanallar/spoderman/karakterler/spoderman.png` gibi.

## Yeni kanal açmak

1. `kanallar/spoderman/` klasörünü `kanallar/yeni_kanal/` olarak kopyala. `gecmis.json` ve png dosyalarını sil.
2. `kanal.yaml` içinde karakterleri, stili, temaları, hashtag'leri ve `token_env` / `profil_env` isimlerini değiştir.
3. `python -m shitpost karakter yeni_kanal` ve `python -m shitpost youtube-yetki yeni_kanal` komutlarını çalıştır.
4. Otomatik çalışması için `.github/workflows/uret.yml` içinde `matrix.kanal` listesine ekle ve yeni secret'ları `env:` kısmına yaz.

Farklı TikTok ve IG hesapları için Ayrshare'de her kanala ayrı bir profil aç (Business plan) ve profil anahtarını `AYRSHARE_PROFILE_<KANAL>` olarak ekle.

## Otomatik çalıştırma (GitHub Actions)

Repo → Settings → Secrets → Actions kısmına şunları ekle: `GEMINI_API_KEY`, `AYRSHARE_API_KEY`, `AYRSHARE_PROFILE_SPODERMAN`, `YOUTUBE_TOKEN_SPODERMAN` (`youtube_token.json` dosyasının içeriği).

Workflow günde 3 kez çalışır (TR 09:07, 15:07, 20:07). `gecmis.json` dosyasını ve karakter görsellerini repoya geri commit'ler. Üretilen videolar 7 gün boyunca Actions sayfasında artifact olarak durur. Elle çalıştırmak için Actions → "Shitpost üret" → Run workflow (`kuru` seçeneği ile paylaşmadan test edebilirsin).

## Bilinmesi gerekenler

- **Maliyet:** Veo saniye başına ücretlendirilir. Günde 3 video × 8 sn'nin aylık maliyetini Google'ın fiyat sayfasından hesapla. Daha ucuz seçenek: `kanal.yaml` içinde `video: veo-3.1-lite-generate-preview`.
- **YouTube:** Google Cloud'daki OAuth uygulaması "Testing" modundaysa token 7 günde bir düşer. Uygulamayı "In production" yap. Doğrulanmamış uygulamalarla yüklenen videolar private kalabilir; Google'ın API denetimine başvurman gerekebilir. Günlük yükleme kotası sınırlı (varsayılan 10.000 birim ≈ 6 video).
- **Ayrshare modülü** dokümana erişilemeyen bir ortamda yazıldı. İlk gerçek paylaşımı `--kuru` sonrası, dikkatle izleyerek yap.
- **Telif:** Karakterler videolarda markalı isimleriyle değil, "bootleg / parodi" tarifleriyle çiziliyor. Hem Veo filtresine takılmamak hem de telif riskini azaltmak için böyle.
