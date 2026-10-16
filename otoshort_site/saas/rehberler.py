"""Kısa kullanım rehberleri (/rehberler). Metinler Türkçe; İngilizceleri i18n_en sözlüğünde.
Her rehber: adres, ikon, okuma süresi (dk), başlık, özet, adımlar [(başlık, metin)] ve sonunda bir buton (adres, yazı)."""

GUIDES = [
    {"slug": "ilk-video", "icon": "sparkles", "min": 2, "title": "İlk videonu 2 dakikada üret",
     "desc": "Fikirden sesli, dikey videoya: stil, süre ve yapay zekâ seçimi.",
     "steps": [
         ("Fikrini tek cümleyle yaz",
          "Kim, nerede, ne yapıyor? Örn: “Kedi, sahibinin toplantısına gizlice katılıyor.” Fikir bulamazsan zar "
          "butonuna bas ya da hazır şablonlardan birini seç."),
         ("Stil ve süreyi seç",
          "Çizgi film, gerçekçi ya da ucuz 3D gibi bir stil seç. Süreyi çubukla 4–60 saniye arası ayarla; "
          "10 saniyeye kadar fiyat sabit, üstü saniye başı."),
         ("Yapay zekâ seviyesini seç",
          "Ekonomik her hesapta açık; Standart ve Premium abonelikle açılır. Fiyat, seçim yaparken altta canlı görünür."),
         ("Üret ve paylaş",
          "Video birkaç dakikada hazır olur, hazır olunca e-posta da gelir. İndirip paylaşabilir ya da bağlı "
          "hesaplarına doğrudan gönderebilirsin."),
     ], "cta": ("/video/yeni", "Video üret")},
    {"slug": "otomatik-kanal", "icon": "repeat", "min": 3, "title": "Otomatik kanal kur, her gün video gelsin",
     "desc": "Konuyu ve saatleri bir kez seç; yapay zekâ her gün yeni fikir bulup videoyu üretsin.",
     "steps": [
         ("Kanalın konusunu belirle",
          "Dar ve net bir konu seç: “Ofis hayatını anlatan konuşan meyveler” gibi. Emin değilsen ücretsiz Kanal "
          "Kurucu sana kanal adı, açıklama ve ilk 5 video fikrini çıkarır."),
         ("Saatleri seç",
          "Videoların hangi saatlerde üretileceğini seç. Her video bakiyenden düşer; bakiye bitince kanal durur ve "
          "sana haber verilir."),
         ("Onay modunu aç",
          "Onay modunda videolar paylaşılmadan önce sana gelir: beğenirsen onaylarsın, beğenmezsen paylaşılmaz."),
         ("Hesaplarını bağla",
          "YouTube, TikTok ya da Instagram bağlarsan videolar otomatik paylaşılır. Bağlamazsan Videolarım'da birikir."),
     ], "cta": ("/kanallar/yeni", "Kanal kur")},
    {"slug": "hesap-baglama", "icon": "share", "min": 2, "title": "YouTube, TikTok ve Instagram'ı bağla",
     "desc": "Videolar telefona indirmeye gerek kalmadan doğrudan hesabına gitsin.",
     "steps": [
         ("Bağlantılar sayfasını aç",
          "Ayarlar → Bağlantılar'dan platformu seç. Platformun kendi giriş ve izin ekranı açılır; şifren bize gelmez."),
         ("İzni onayla",
          "Yalnızca video paylaşma izni istenir. Bağlantıyı istediğin zaman kaldırabilirsin."),
         ("Videoyu ya da kanalı yönlendir",
          "Tek bir videoyu kendi sayfasından paylaşabilir, otomatik kanallarda videoların hangi hesaplara gideceğini "
          "seçebilirsin."),
         ("AI etiketini unutma",
          "Platform kuralları gereği yapay zekâyla üretilen videolar “AI” etiketiyle paylaşılmalıdır."),
     ], "cta": ("/baglantilar", "Hesap bağla")},
    {"slug": "viral-formatlar", "icon": "message", "min": 2, "title": "Viral formatlar: mesajlaşma, itiraf, seçim, quiz",
     "desc": "Video modeli kullanmayan, ucuz ve çok izlenen dört format.",
     "steps": [
         ("Formatı seç",
          "Video üret sayfasının üstünden Mesajlaşma hikâyesi, İtiraf / hikâye, Hangisini seçerdin? ya da Bil bakalım "
          "formatını seç."),
         ("Konuyu yaz",
          "Örn: “Annem gece 3'te neden çevrimiçi olduğumu soruyor” ya da quiz için “Uzay”. Yapay zekâ mesajları, "
          "hikâyeyi, seçenekleri ya da soruları yazar ve sesli okur."),
         ("Arka planı seç",
          "Hareketli desenlerden birini seç ya da kütüphanendeki bir videoyu arka plan yap."),
         ("Neden işe yarıyor?",
          "İzleyici sonraki mesajı ya da doğru cevabı merak ettiği için videoyu sonuna kadar izler; seçim ve quiz "
          "videoları yorum da getirir. Platform böyle videoları daha çok kişiye gösterir."),
     ], "cta": ("/video/yeni?format=sohbet", "Formatı dene")},
    {"slug": "karakterler", "icon": "users", "min": 2, "title": "Karakter kütüphanesiyle tutarlı maskot",
     "desc": "Aynı karakteri her videoda aynı görünüşle kullan.",
     "steps": [
         ("Karakter ekle",
          "Karakterler sayfasından bir görsel yükle ve adını yaz. Tek kişilik, net ve sade arka planlı görseller en "
          "iyi sonucu verir."),
         ("Videoda seç",
          "Video üretirken karakterini seç. Referans görseli destekleyen yapay zekâlarda karakterin görünüşü korunur."),
         ("Kanala ekle",
          "Otomatik kanala karakter eklersen her gün aynı maskotla video gelir; izleyici kanalını karakterinden tanır."),
     ], "cta": ("/karakterler", "Karakter ekle")},
    {"slug": "kredi-abonelik", "icon": "gem", "min": 2, "title": "Kredi ve abonelik nasıl çalışır?",
     "desc": "Ne zaman kredi paketi, ne zaman abonelik mantıklı?",
     "steps": [
         ("1 kredi ≈ 1 ₺",
          "Her video seçtiğin yapay zekâ ve süreye göre kredi düşer. Üretim başarısız olursa kredi otomatik iade edilir."),
         ("Kredi paketi",
          "Aboneliksiz de Ekonomik yapay zekâyı kullanabilirsin; paket büyüdükçe hediye kredi artar. Krediler silinmez."),
         ("Abonelik",
          "Başlangıç, Pro ve Stüdyo her ay kredi yükler ve daha güçlü yapay zekâları açar. Otomatik çekim yok; süre "
          "bitince istersen uzatırsın."),
         ("Ücretsiz kredi",
          "Arkadaşını davet et: arkadaşın ilk kredi yüklemesini yapınca ikinize de hediye kredi gelir."),
     ], "cta": ("/abonelik", "Abonelikleri gör")},
    {"slug": "izlenme-ipuclari", "icon": "rocket", "min": 3, "title": "Daha çok izlenmek için 6 ipucu",
     "desc": "Kısa videoda ilk 2 saniye her şeydir.",
     "steps": [
         ("İlk 2 saniyede merak uyandır",
          "Videoya olayın ortasından başla: “Kedim toplantıda konuştu.” Açıklamayı sonra yap."),
         ("Kısa tut",
          "8–20 saniyelik videolar en çok sonuna kadar izlenenlerdir; sonuna kadar izlenme platformların en sevdiği "
          "sinyaldir."),
         ("Altyazıyı açık bırak",
          "İnsanların çoğu sessizde izler. Viral altyazı konuşulan kelimeyi vurgular ve gözü ekranda tutar."),
         ("Her gün aynı saatte paylaş",
          "Düzenli paylaşım kanalı büyütür. Otomatik kanal bunu senin yerine yapar."),
         ("Bir karakter, bir dünya",
          "Aynı maskotla seri video yapan kanallar daha hızlı takipçi kazanır."),
         ("Yorumlardan fikir topla",
          "İzleyiciler ne görmek istediğini yorumlara yazar; en iyi yeni fikirler oradan çıkar."),
     ], "cta": ("/video/yeni", "Video üret")},
]
BY_SLUG = {g["slug"]: g for g in GUIDES}


def texts() -> set[str]:
    """Çevrilecek metinler (i18n_keys)."""
    out = set()
    for g in GUIDES:
        out |= {g["title"], g["desc"], g["cta"][1]}
        for title, body in g["steps"]:
            out |= {title, body}
    return out
