"""Ana sayfadaki "Fikir makinesi" için elle seçilmiş komik kısa video fikirleri (Türkçe, İngilizce).
Yapay zekâ çağrısı yapmaz; ziyaretçi butona bastıkça rastgele biri gösterilir."""

IDEAS = [
    ("🐱", "cartoon", "Kedi, sahibinin online toplantısına gizlice katılıp patronu yönetmeye çalışıyor",
     "A cat sneaks into its owner's video call and tries to boss the boss around"),
    ("🦖", "meme3d", "Dinozor ilk kez metrobüse biniyor ve kuyruğu kapıya sıkışıyor",
     "A dinosaur rides the bus for the first time and its tail gets stuck in the door"),
    ("🤖", "cartoon", "Robot, Türk düğününde halaya kalkıp halayın başını kapıyor",
     "A robot joins the line dance at a Turkish wedding and takes over as leader"),
    ("🐧", "claymation", "Penguen, plajda güneş kremi satmaya çalışıyor ama kimse almıyor",
     "A penguin tries to sell sunscreen at the beach, but nobody's buying"),
    ("🍊", "cartoon", "Portakal ve muz markette son indirimli ürün için kavga ediyor",
     "An orange and a banana fight over the last discounted item at the market"),
    ("🐢", "anime", "Kaplumbağa, kargo kuryesi olarak ilk gününde rekor kırmaya çalışıyor",
     "A turtle tries to break a record on its first day as a delivery courier"),
    ("👽", "realistic", "Uzaylı, Kapalıçarşı'da halı için pazarlık yapıyor",
     "An alien haggles for a carpet at the Grand Bazaar"),
    ("🍕", "cartoon", "Pizza dilimi diyete başlamaya karar veriyor, salata ona koçluk yapıyor",
     "A pizza slice decides to go on a diet, and a salad becomes its coach"),
    ("🐸", "meme3d", "Kurbağa, bilgi yarışmasında son soruda jokerini annesine harcıyor",
     "A frog uses its lifeline to call its mom on the final quiz question"),
    ("🐻", "claymation", "Ayı, kış uykusundan erken uyanıp alarmı kimin kurduğunu arıyor",
     "A bear wakes up early from hibernation and hunts for whoever set the alarm"),
    ("🥯", "cartoon", "Simit, çayla ilk buluşmasında heyecandan susamlarını döküyor",
     "A bagel is so nervous on its first date with tea that it drops its sesame seeds"),
    ("❄️", "anime", "Kar tanesi, yaz tatiline çıkmak için çanta hazırlıyor",
     "A snowflake packs its bags for a summer vacation"),
    ("🥔", "meme3d", "Patates spor salonunda kas yapıp kızartma olmaktan kurtulmaya çalışıyor",
     "A potato hits the gym to avoid becoming fries"),
    ("🦉", "anime", "Baykuş, gece vardiyasında çalışan bir güvenlik görevlisine dönüşüyor",
     "An owl takes a job as a night-shift security guard"),
    ("🐶", "realistic", "Köpek, postacıyla barışmak için ona hediye hazırlıyor",
     "A dog prepares a gift to finally make peace with the mail carrier"),
    ("☕", "cartoon", "Kahve bardağı, pazartesi sabahı ofiste herkesin kahramanı oluyor",
     "A coffee cup becomes everyone's hero on a Monday morning at the office"),
    ("🐌", "claymation", "Salyangoz, maratona katılıp seyircileri sabırsızlıktan çıldırtıyor",
     "A snail enters a marathon and drives the crowd crazy with suspense"),
    ("🎈", "cartoon", "Balon, doğum günü partisinde patlamamak için saklanıyor",
     "A balloon hides at a birthday party so it won't get popped"),
    ("🦆", "meme3d", "Ördek, parktaki ekmek dağıtımını yöneten bir mafya babası",
     "A duck runs the bread-handout mafia at the park"),
    ("🧦", "claymation", "Kayıp çorap, çamaşır makinesinden kaçış planı yapıyor",
     "A lost sock plots its escape from the washing machine"),
    ("🐝", "anime", "Arı, kovanda yapılan sabah toplantısında terfi istiyor",
     "A bee asks for a promotion at the hive's morning meeting"),
    ("🍉", "cartoon", "Karpuz, yaz pikniğinde kimseye kesilmemek için kılık değiştiriyor",
     "A watermelon wears a disguise at a summer picnic to avoid getting sliced"),
    ("🦒", "realistic", "Zürafa, sinemada önündekilerin görmesini engellediği için özür diliyor",
     "A giraffe keeps apologizing for blocking everyone's view at the cinema"),
    ("📱", "cartoon", "Şarjı %1 kalan telefon, sahibine veda konuşması yapıyor",
     "A phone at 1% battery gives a farewell speech to its owner"),
    ("🐙", "anime", "Ahtapot, sekiz koluyla aynı anda dört işte çalışan bir garson",
     "An octopus waiter works four jobs at once with its eight arms"),
    ("🍞", "claymation", "Ekmek, tost makinesine girmeden önce son sözlerini söylüyor",
     "A slice of bread shares its last words before going into the toaster"),
    ("🦁", "realistic", "Aslan, kral olarak ilk gününde ormanın şikâyet hattına bakıyor",
     "A lion spends its first day as king answering the jungle's complaint hotline"),
    ("🐑", "cartoon", "Koyun, uyuyamayan insanları saymaktan yorulup greve gidiyor",
     "A sheep goes on strike after counting sleepless humans every night"),
]


def for_lang(lang: str) -> list[dict]:
    return [{"e": e, "s": s, "t": en if lang == "en" else tr} for e, s, tr, en in IDEAS]


# "Neler üretebilirsin?" örnekleri: (ikon, başlık TR, örnek TR, başlık EN, örnek EN). Konuyu kullanıcı kendi seçer;
# bunlar yalnızca ilham verir ve tıklayınca stüdyodaki fikir kutusunu doldurur.
USE_CASES = [
    ("sparkles", "Komik skeç", "Kedi, sahibinin online toplantısına gizlice katılıp patronu yönetmeye çalışıyor",
     "Comedy sketch", "A cat sneaks into its owner's video call and tries to boss the boss around"),
    ("tag", "Marka tanıtımı", "Kahve dükkânım için sıcak ve samimi bir tanıtım: sabah ilk kahvesiyle gülümseyen insanlar",
     "Brand intro", "A warm, friendly intro for my coffee shop: people smiling over their first coffee of the day"),
    ("gem", "Ürün reklamı", "El yapımı doğal sabunlarımızın ferah, sakin bir reklamı; köpükler ve yeşil yapraklar",
     "Product ad", "A fresh, calm ad for our handmade natural soaps; soft foam and green leaves"),
    ("brain", "Eğitici video", "Gökkuşağı nasıl oluşur? Meraklı bir bilim insanı çocuklara kısaca anlatıyor",
     "Explainer", "How does a rainbow form? A curious scientist explains it to kids in a few seconds"),
    ("film", "Hikâye / masal", "Yalnız bir deniz feneri bekçisi ile bir martının duygusal arkadaşlığı",
     "Story", "A lonely lighthouse keeper and a seagull become unlikely friends"),
    ("rocket", "Motivasyon", "Sabah beşte yağmurda koşuya çıkan bir sporcu; güne başlama motivasyonu",
     "Motivation", "An athlete heads out for a run at 5 a.m. in the rain; a morning motivation clip"),
    ("calendar", "Etkinlik duyurusu", "Cumartesi akşamki canlı müzik gecemizin enerjik duyurusu",
     "Event promo", "An energetic promo for our live music night this Saturday"),
    ("globe", "Mekân tanıtımı", "Deniz manzaralı kafemizin gün batımında huzurlu bir tanıtımı",
     "Place tour", "A peaceful sunset tour of our seaside café"),
]


def use_cases(lang: str) -> list[dict]:
    en = lang == "en"
    return [{"icon": ic, "title": te if en else tt, "example": ee if en else et} for ic, tt, et, te, ee in USE_CASES]


# Ana sayfadaki "Viral formatlar" bölümünde yapay zekâ videosu kartında oynayan örnek senaryo
SAMPLE_SCRIPT = {
    "tr": {"title": "Portakal markette olay çıkardı 😭", "lines": [
        {"who": "Portakal", "text": "Bu son indirim benim!"}, {"who": "Muz", "text": "Ben ondan önce sıradaydım"},
        {"who": "Portakal", "text": "Sen sıraya hiç girmedin ki"}, {"who": "Muz", "text": "Kasiyer de bir karpuz zaten"}]},
    "en": {"title": "The orange lost it at the store 😭", "lines": [
        {"who": "Orange", "text": "That last deal is mine!"}, {"who": "Banana", "text": "I was in line before you"},
        {"who": "Orange", "text": "You never even got in line"}, {"who": "Banana", "text": "The cashier is a watermelon anyway"}]},
}


def sample_script(lang: str) -> dict:
    return SAMPLE_SCRIPT["en" if lang == "en" else "tr"]
