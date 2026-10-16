"""Hazır kanal şablonları: tek tıkla otomatik kanal ya da video formunu doldurur (Türkçe ve İngilizce)."""
from types import SimpleNamespace

# (anahtar, emoji, kategori, tarz, saatler, {tr: (ad, açıklama, konu, karakterler, [örnek fikirler]), en: (...)})
TEMPLATES = [
    ("komik-meyveler", "🍊", "komedi", "cartoon", "12:00 19:00", {
        "tr": ("Komik Meyveler", "Konuşan meyvelerin market, mutfak ve buzdolabı maceraları.",
               "Konuşan meyveler gündelik hayatta saçma olaylar yaşar. Her video farklı bir mekânda geçsin; sonunda beklenmedik bir espri olsun.",
               "Sinirli, kocaman kaşlı bir portakal ve her şeye gülen saf bir muz.",
               ["Portakal ve muz son indirim için kavga ediyor", "Limon herkesi ekşi suratıyla korkutuyor",
                "Karpuz pikniğe gitmemek için saklanıyor"]),
        "en": ("Funny Fruits", "Talking fruits and their adventures at the market, kitchen and fridge.",
               "Talking fruits get into silly everyday situations. Each video takes place somewhere new and ends with an unexpected joke.",
               "A grumpy orange with huge eyebrows and a naive banana who laughs at everything.",
               ["An orange and a banana fight over the last deal", "A lemon scares everyone with its sour face",
                "A watermelon hides to avoid the picnic"])}),
    ("ofis-kedisi", "🐱", "komedi", "realistic", "09:45 18:30", {
        "tr": ("Ofis Kedisi", "Patronluk taslayan bir kedinin iş hayatı.",
               "Bir kedi ofiste çalışıyormuş gibi davranır: toplantılar, mesai, kahve molası. Her videoda iş hayatından tanıdık bir an.",
               "Gözlüklü, kendini müdür sanan gri bir tekir kedi.",
               ["Kedi pazartesi toplantısını yönetiyor", "Kedi zam istemek için sunum hazırlıyor",
                "Kedi klavyenin üstünde uyuyup raporu siliyor"]),
        "en": ("Office Cat", "A bossy cat's life at the office.",
               "A cat acts like it works at an office: meetings, overtime, coffee breaks. Each video shows a familiar work moment.",
               "A grey tabby cat with glasses who thinks it's the manager.",
               ["The cat runs the Monday meeting", "The cat prepares a slideshow to ask for a raise",
                "The cat falls asleep on the keyboard and deletes the report"])}),
    ("dinozor-sehirde", "🦖", "komedi", "meme3d", "13:00 21:15", {
        "tr": ("Şehirdeki Dinozor", "Modern şehirde yaşamaya çalışan sakar bir dinozor.",
               "Bir dinozor modern şehirde gündelik işleri yapmaya çalışır ve kocaman cüssesi yüzünden her şey karışır.",
               "Kısa kollu, iyi kalpli ama sakar yeşil bir T-Rex.",
               ["Dinozor metrobüse binmeye çalışıyor", "Dinozor berberde saç kestiriyor", "Dinozor asansöre sığmıyor"]),
        "en": ("Dino in the City", "A clumsy dinosaur trying to live in a modern city.",
               "A dinosaur tries to do everyday things in a modern city, and its huge size messes everything up.",
               "A kind-hearted but clumsy green T-Rex with tiny arms.",
               ["The dino tries to ride the bus", "The dino gets a haircut", "The dino doesn't fit in the elevator"])}),
    ("tarih-gercekleri", "🏛️", "egitim", "realistic", "12:00 20:00", {
        "tr": ("Tarihten İlginç Anlar", "Az bilinen tarihi olayları 8 saniyede anlatan kısa sahneler.",
               "Tarihten az bilinen, şaşırtıcı ve doğru bir olayı kısa bir sahneyle canlandır; anlatıcı tek cümleyle açıklasın.",
               "Sakin sesli bir anlatıcı ve döneme uygun kıyafetli kişiler.",
               ["Antik Mısır'da işçilerin grev yapması", "Osmanlı'da ilk kahvehanelerin açılması", "Kâğıt paranın Çin'de icadı"]),
        "en": ("History Bites", "Little-known historical moments in 8-second scenes.",
               "Recreate a little-known, surprising and accurate historical event in a short scene, with a narrator explaining it in one sentence.",
               "A calm-voiced narrator and people in period clothing.",
               ["Workers going on strike in ancient Egypt", "The first coffeehouses opening", "The invention of paper money in China"])}),
    ("bilim-1-dakika", "🔬", "egitim", "cartoon", "10:00 17:00", {
        "tr": ("Bilim Kırıntıları", "Günlük hayattan bilim sorularına eğlenceli cevaplar.",
               "Gündelik bir bilim sorusunu (gökyüzü neden mavi?) sevimli karakterlerle kısa ve doğru şekilde açıkla.",
               "Meraklı bir çocuk ve her şeyi bilen konuşan bir ampul.",
               ["Gökyüzü neden mavi?", "Kediler neden hep dört ayak üstüne düşer?", "Buz neden suyun üstünde yüzer?"]),
        "en": ("Science Snacks", "Fun answers to everyday science questions.",
               "Explain an everyday science question (why is the sky blue?) briefly and accurately with cute characters.",
               "A curious kid and a talking light bulb who knows everything.",
               ["Why is the sky blue?", "Why do cats land on their feet?", "Why does ice float?"])}),
    ("motivasyon", "🌅", "motivasyon", "anime", "07:30 22:00", {
        "tr": ("Günün Motivasyonu", "Kısa, etkileyici motivasyon sahneleri.",
               "Zorlukla karşılaşan bir karakterin pes etmeyip başardığı kısa, duygusal bir sahne; sonunda tek cümlelik motive edici söz.",
               "Hedefi için çalışan genç bir sporcu ya da öğrenci.",
               ["Sabah 5'te koşuya çıkan sporcu", "Sınavdan önce son tekrar", "İlk işinde başarısız olup tekrar deneyen girişimci"]),
        "en": ("Daily Motivation", "Short, powerful motivational scenes.",
               "A short, emotional scene of a character facing a challenge and not giving up, ending with a one-line motivational quote.",
               "A young athlete or student working toward their goal.",
               ["An athlete going for a run at 5 a.m.", "Last review before the exam", "A founder failing and trying again"])}),
    ("mutfak-kazalari", "🍳", "yemek", "claymation", "12:30 19:30", {
        "tr": ("Mutfak Kazaları", "Yemek yaparken işler hep ters gidiyor.",
               "Bir karakter basit bir yemek yapmaya çalışır ama mutfakta komik kazalar olur; sonunda yine de güzel bir tabak çıkar.",
               "Aşırı özgüvenli ama beceriksiz bir aşçı ve onu izleyen yorgun bir tava.",
               ["Menemen yaparken yumurtaların kaçması", "Hamurun mutfağı istila etmesi", "Çay demlerken çaydanlığın konuşması"]),
        "en": ("Kitchen Disasters", "Cooking where everything goes wrong.",
               "A character tries to cook something simple but funny accidents happen; still, a nice plate comes out in the end.",
               "An overconfident but clumsy cook and a tired frying pan watching them.",
               ["Eggs escaping from the pan", "Dough taking over the kitchen", "The teapot talks back"])}),
    ("hayvan-sohbetleri", "🐶", "hayvanlar", "realistic", "11:00 18:00", {
        "tr": ("Hayvanlar Konuşsaydı", "Evcil hayvanların gizli iç sesleri.",
               "Evcil hayvanların sahipleri hakkında düşündüklerini komik iç sesle anlat; gündelik ev anları.",
               "Dramatik bir golden retriever ve onu küçümseyen siyah bir kedi.",
               ["Köpek veteriner yolunu fark ediyor", "Kedi yeni koltuğu onaylamıyor", "Papağan aile sırlarını açıklıyor"]),
        "en": ("If Pets Could Talk", "The secret inner voices of pets.",
               "Show what pets think about their owners with a funny inner voice, in everyday moments at home.",
               "A dramatic golden retriever and a black cat who looks down on it.",
               ["The dog realizes it's going to the vet", "The cat disapproves of the new sofa", "The parrot reveals family secrets"])}),
    ("uzay-maceralari", "🚀", "macera", "anime", "15:45 21:15", {
        "tr": ("Uzay Postacısı", "Galaksiler arası kargo taşıyan bir postacının maceraları.",
               "Uzayda gezegenler arası kargo dağıtan bir postacının her videoda farklı bir gezegendeki komik teslimatı.",
               "Aceleci bir uzay postacısı ve onun sarkastik robot yardımcısı.",
               ["Yerçekimi olmayan gezegene pizza teslimatı", "Uzaylı müşteri imza atmayı bilmiyor", "Kargo kara deliğe düşüyor"]),
        "en": ("Space Courier", "Adventures of a courier delivering parcels between galaxies.",
               "A courier delivering parcels between planets makes a funny delivery on a different planet in each video.",
               "A hasty space courier and their sarcastic robot sidekick.",
               ["Delivering pizza to a zero-gravity planet", "An alien customer doesn't know how to sign", "The parcel falls into a black hole"])}),
    ("cocuk-masallari", "🧸", "cocuk", "cartoon", "19:00", {
        "tr": ("Mini Masallar", "Çocuklar için kısa, öğretici masal sahneleri.",
               "Paylaşmak, dürüstlük, arkadaşlık gibi bir değeri anlatan kısa ve tatlı bir masal sahnesi. Korkutucu öğe olmasın.",
               "Küçük bir ayıcık ve meraklı arkadaşı tavşan.",
               ["Ayıcık balını tavşanla paylaşıyor", "Tavşan kırdığı vazoyu itiraf ediyor", "Yeni gelen sincaba arkadaş olmak"]),
        "en": ("Mini Tales", "Short, wholesome story scenes for kids.",
               "A short, sweet story scene about a value like sharing, honesty or friendship. Nothing scary.",
               "A little teddy bear and its curious bunny friend.",
               ["The bear shares its honey with the bunny", "The bunny admits breaking the vase", "Making friends with the new squirrel"])}),
    ("spor-anlari", "⚽", "spor", "meme3d", "20:00", {
        "tr": ("Mahalle Maçı", "Mahalle maçlarındaki efsane anların abartılı canlandırması.",
               "Mahalle maçında yaşanan tanıdık bir anı (kim kaleye geçecek, top kimin) abartılı ve komik şekilde canlandır.",
               "Her şeyi bilen yorumcu amca ve hep ofsayt diyen bir çocuk.",
               ["Kimse kaleye geçmek istemiyor", "Top komşunun bahçesine kaçıyor", "Son gol oyunu bitiriyor"]),
        "en": ("Street Football", "Over-the-top recreations of legendary moments from neighborhood games.",
               "Recreate a familiar neighborhood football moment (who plays goalie? whose ball is it?) in an exaggerated, funny way.",
               "A know-it-all commentator uncle and a kid who always shouts offside.",
               ["Nobody wants to be goalie", "The ball flies into the neighbor's garden", "Next goal wins"])}),
    ("teknoloji-dertleri", "💻", "teknoloji", "cartoon", "13:00 21:00", {
        "tr": ("Teknoloji Dertleri", "Hepimizin yaşadığı teknoloji sorunları, karakterleştirilmiş halde.",
               "Gündelik bir teknoloji derdini (şarj bitmesi, güncelleme, Wi-Fi kopması) cihazları konuşturarak komik şekilde anlat.",
               "Dramatik bir akıllı telefon ve her şeyi geciktiren yavaş bir modem.",
               ["Telefon %1 şarjda veda konuşması yapıyor", "Bilgisayar en kötü anda güncelleme yapıyor", "Wi-Fi tam maç anında kopuyor"]),
        "en": ("Tech Troubles", "Tech problems we all have, turned into characters.",
               "Tell an everyday tech problem (battery dying, updates, Wi-Fi dropping) in a funny way by making the devices talk.",
               "A dramatic smartphone and a slow modem that delays everything.",
               ["The phone gives a farewell speech at 1%", "The laptop updates at the worst moment", "Wi-Fi drops right at the big moment"])}),
]

CATEGORIES = {"komedi": "Komedi", "egitim": "Eğitim", "motivasyon": "Motivasyon", "yemek": "Yemek",
              "hayvanlar": "Hayvanlar", "macera": "Macera", "cocuk": "Çocuk", "spor": "Spor", "teknoloji": "Teknoloji"}


def all_for(lang: str) -> list[SimpleNamespace]:
    out = []
    for key, emoji, cat, style, times, text in TEMPLATES:
        name, desc, topic, chars, ideas = text["en" if lang == "en" else "tr"]
        out.append(SimpleNamespace(key=key, emoji=emoji, category=cat, style=style, times=times, name=name, desc=desc,
                                   topic=topic, characters=chars, ideas=ideas))
    return out


def get(key: str, lang: str) -> SimpleNamespace | None:
    return next((t for t in all_for(lang) if t.key == key), None)


def as_channel(t: SimpleNamespace, lang: str) -> SimpleNamespace:
    """Kanal formunu doldurmak için kanal benzeri nesne (kaydedilmemiş)."""
    return SimpleNamespace(id=None, name=t.name, topic=t.topic, characters=t.characters, style=t.style,
                           language=lang if lang in ("tr", "en") else "tr", quality="fast", times=t.times,
                           subtitles=True, subtitle_style="viral", publish_to="", ref_image="", active=True, idea=t.ideas[0], title="",
                           hook=True, progress=False, voice="")
