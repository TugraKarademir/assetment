"""Sentetik yanıt üretimi için Türkçe cümle bankası.

Her soru × ölçüt × puan düzeyi (0–4) için birden çok cümle varyantı vardır. Bir sentetik yanıt,
her ölçüt için öğrencinin gizli (latent) düzeyine karşılık gelen cümlelerden kurulur. Böylece
metin kalitesi ile "gerçek" puan arasında bilinen bir ilişki olur.

Bu cümleler items.yaml içindeki çapa yanıtlardan bilinçli olarak farklıdır.
"""

BANK: dict[str, dict[str, dict[int, list[str]]]] = {
    "S1": {
        "C1": {
            0: [],
            1: ["Denetimli öğrenmede bilgisayar bir insan tarafından izlenir, denetimsizde ise serbest bırakılır.",
                "Denetimli öğrenme kurallı öğrenmedir, denetimsiz öğrenme ise kuralsızdır."],
            2: ["Denetimli öğrenmede modele cevaplar verilir, denetimsizde model cevapları kendisi bulur.",
                "Birinde veriler hazırdır ve doğru sonuçlar bellidir, diğerinde model kendi başına çalışır."],
            3: ["Denetimli öğrenmede veriler etiketlidir ve model girdiye karşılık gelen çıktıyı öğrenir; denetimsiz öğrenmede ise etiket yoktur, model verideki yapıyı kendisi keşfeder.",
                "Temel fark etiketli veridir: denetimli öğrenme etiketli örneklerden tahmin yapmayı öğrenir, denetimsiz öğrenme etiketsiz veride örüntü arar."],
            4: ["Denetimli öğrenmede her eğitim örneği hedef değişkenle eşleştirilmiştir ve model bu eşleşmeden genelleme yapar; sınıflandırma ve regresyon bu türdendir. Denetimsiz öğrenmede hedef değişken yoktur, model kümeleme ya da boyut indirgeme ile verinin gizli yapısını ortaya çıkarır.",
                "Ayırt edici nokta hedef değişkenin varlığıdır: denetimli yöntemler etiketli veriyle girdi-çıktı ilişkisini öğrenip sınıflandırma veya regresyon yapar, denetimsiz yöntemler ise etiket olmadan benzer örnekleri kümeler ya da boyut indirger."],
        },
        "C2": {
            0: [],
            1: ["Örneğin akıllı telefonlar denetimsiz öğrenme kullanır.",
                "Mesela robot süpürgeler denetimli öğrenmeye örnektir çünkü biz onları denetleriz."],
            2: ["Örnek olarak yüz tanıma sistemleri denetimli öğrenme kullanır.",
                "Hava durumunu tahmin etmek denetimli öğrenmeye örnektir, diğer türe örnek bulamadım."],
            3: ["Örneğin kredi başvurularının onaylanıp onaylanmayacağını tahmin etmek denetimli, alışveriş sepetlerinden müşteri grupları çıkarmak denetimsiz öğrenmedir.",
                "El yazısı rakamları tanımak denetimli öğrenmeye, haber metinlerini konularına göre gruplamak denetimsiz öğrenmeye örnektir."],
            4: ["Örneğin bir bankanın geçmiş kayıtlarda dolandırıcılık olarak işaretlenmiş işlemlerden yeni işlemleri sınıflandırması denetimlidir çünkü etiketler bellidir; aynı bankanın müşterilerini harcama profillerine göre segmentlere ayırması ise önceden tanımlı grup olmadığı için denetimsizdir.",
                "Tıbbi görüntülerde doktorların işaretlediği tümör örnekleriyle model eğitmek denetimlidir, çünkü doğru teşhis etiketi vardır; bir müzik uygulamasının şarkıları dinlenme örüntülerine göre kendiliğinden gruplaması ise etiket kullanılmadığı için denetimsizdir."],
        },
        "C3": {
            0: ["bilmiyorum hocam"],
            1: ["Yani kısacası öğrenme türleri farklıdır işte bu yüzden ikisi de kullanılır.",
                "Bu konu derste anlatılmıştı, yapay zekada çok kullanılır."],
            2: ["Sonuç olarak iki yöntem de makine öğrenmesinde kullanılır.",
                "Özetle bu iki öğrenme farklı amaçlara hizmet eder."],
            3: ["Sonuç olarak iki yaklaşım, verinin etiketli olup olmamasına göre farklı problemlere uygulanır.",
                "Özetlemek gerekirse, hangi yöntemin seçileceği elimizdeki verinin türüne bağlıdır."],
            4: ["Kısacası seçim, eldeki verinin etiketli olup olmamasına ve amacın tahmin mi yoksa keşif mi olduğuna göre yapılır; iki yaklaşım birbirinin alternatifi değil, farklı soruların cevabıdır.",
                "Bu karşılaştırma, problemin tanımının yöntem seçimini belirlediğini gösterir: hedef biliniyorsa denetimli, yapı aranıyorsa denetimsiz öğrenme uygundur."],
        },
    },
    "S2": {
        "C1": {
            0: ["Aşırı öğrenme modelin hiç öğrenememesidir."],
            1: ["Aşırı öğrenme modelin gereğinden fazla çalışmasıdır.",
                "Overfitting yapay zekanın çok zeki olmasıdır."],
            2: ["Aşırı öğrenmede model eğitim verilerini ezberler.",
                "Model eğitim örneklerini ezberlediği için aşırı öğrenme olur."],
            3: ["Aşırı öğrenme, modelin eğitim verisinde yüksek başarı göstermesine rağmen yeni verilerde başarısız olmasıdır.",
                "Modelin eğitim setine çok iyi uyup test setinde kötü sonuç vermesine aşırı öğrenme denir."],
            4: ["Aşırı öğrenme, modelin eğitim verisindeki rastlantısal gürültüyü de örüntü sanarak öğrenmesi ve bu nedenle görülmemiş verilere genelleme yapamamasıdır.",
                "Model, verideki gerçek ilişkiyle birlikte gürültüyü de ezberlediğinde eğitim performansı yükselir ama genelleme yeteneği kaybolur; buna aşırı öğrenme denir."],
        },
        "C2": {
            0: [],
            1: ["Bunu modelin çok uzun sürede eğitilmesinden anlarız.",
                "Bilgisayar ısınırsa aşırı öğrenme olmuş olabilir."],
            2: ["Bunu anlamak için modeli test verisiyle denemek gerekir.",
                "Test sonuçlarına bakarak fark edilebilir."],
            3: ["Eğitim hatası düşük, doğrulama hatası yüksek olduğunda aşırı öğrenme olduğu anlaşılır.",
                "Eğitim ve doğrulama başarıları arasında büyük bir fark varsa aşırı öğrenme vardır."],
            4: ["Öğrenme eğrileri çizildiğinde eğitim hatası düşmeye devam ederken doğrulama hatasının yükselmeye başlaması aşırı öğrenmeyi gösterir; çapraz doğrulamada katlar arasındaki tutarsızlık da bir işarettir.",
                "Eğitim ve doğrulama kayıplarını epoklara göre izlemek gerekir: aradaki açı açılıyorsa model ezberliyordur; k-katlı çapraz doğrulama da bu farkı güvenilir biçimde ortaya koyar."],
        },
        "C3": {
            0: [],
            1: ["Önlemek için modeli daha uzun süre eğitmek gerekir.",
                "Daha karmaşık bir model kullanılırsa sorun çözülür."],
            2: ["Önlemek için daha fazla veri kullanılabilir.",
                "Düzenlileştirme yapılarak önlenebilir."],
            3: ["Önlemek için daha fazla veri toplanabilir ve düzenlileştirme uygulanabilir.",
                "Erken durdurma ve modelin sadeleştirilmesi aşırı öğrenmeyi azaltır."],
            4: ["Önleme yolları arasında erken durdurma (doğrulama hatası artınca eğitimi kesmek), L1/L2 düzenlileştirme (büyük ağırlıkları cezalandırmak), dropout ve veri artırma sayılabilir; her biri modelin gürültüye uyum sağlamasını farklı bir yoldan sınırlar.",
                "Veri artırma ile eğitim örnekleri çeşitlendirilebilir, dropout ile nöronların birbirine bağımlılığı azaltılabilir, L2 düzenlileştirme ile ağırlıklar küçük tutulabilir ve erken durdurma ile model ezberlemeye başlamadan eğitim sonlandırılabilir."],
        },
    },
    "S3": {
        "C1": {
            0: [],
            1: ["Yapay zeka hastanelerde işleri kolaylaştırır.",
                "Teknoloji her zaman faydalıdır."],
            2: ["Sistem hastaları daha hızlı sıralayabilir.",
                "Doktorların iş yükü azalır ve zaman kazanılır."],
            3: ["Sistem çok sayıda hastayı aynı anda değerlendirerek bekleme süresini kısaltabilir ve yorgunluktan kaynaklanan hataları azaltabilir.",
                "Yapay zeka kritik hastaları erken tespit edebilir ve her hastayı aynı ölçütlerle değerlendirerek tutarlılık sağlar."],
            4: ["Sistem, yaşamsal bulguları ve şikâyetleri saniyeler içinde aynı ölçütlerle değerlendirdiği için yoğun saatlerde bile tutarlı karar verir; gece vardiyasındaki yorgunluk etkisini azaltır ve sepsis gibi sinsi tabloları erken uyarıyla yakalayarak ölüm riskini düşürebilir.",
                "En önemli yarar, insan değerlendirmesinin saate ve yorgunluğa bağlı değişkenliğini ortadan kaldırmasıdır; ayrıca geçmiş binlerce vakadan öğrendiği örüntülerle, belirtileri belirsiz kritik hastaları triyaj hemşiresinden önce işaretleyebilir."],
        },
        "C2": {
            0: [],
            1: ["Ama makineler de bozulabilir.",
                "Robotlar insanların yerini alabilir, bu kötü bir şey."],
            2: ["Ancak sistem bazı hastalara karşı yanlı olabilir.",
                "Hasta verilerinin gizliliği bir sorun olabilir."],
            3: ["Öte yandan eğitim verisindeki yanlılıklar bazı hasta gruplarının dezavantajlı olmasına yol açabilir; ayrıca sistemin nasıl karar verdiği açıklanamayabilir.",
                "Riskler arasında veri yanlılığı ve hatalı kararlarda sorumluluğun belirsiz olması sayılabilir."],
            4: ["Ancak geçmiş kayıtlarla eğitilen model, örneğin kadın hastaların kalp krizi belirtilerinin tarihsel olarak az teşhis edilmesi gibi yanlılıkları yeniden üretebilir; kara kutu yapısı bir kararın gerekçesini açıklamayı imkânsızlaştırır ve hata olduğunda sorumluluğun hekimde mi, hastanede mi, üreticide mi olduğu belirsizleşir. Ayrıca hassas sağlık verilerinin işlenmesi gizlilik riski taşır.",
                "Etik açıdan üç temel risk vardır: azınlık ya da yaşlı gruplara karşı sistematik yanlılık, kararların şeffaf olmaması nedeniyle hastanın itiraz hakkının zayıflaması ve yanlış önceliklendirmede hesap verebilirliğin kimde olduğunun belirsizliği; bunlara kişisel sağlık verilerinin korunması sorunu da eklenmelidir."],
        },
        "C3": {
            0: [],
            1: ["Bence kesinlikle kullanılmalı.",
                "Bence hiç kullanılmamalı, insanlar daha iyidir."],
            2: ["Bu yüzden sistem dikkatli kullanılmalıdır.",
                "Sonuç olarak yararları da zararları da vardır."],
            3: ["Bu nedenle sistem son kararı doktora bırakan bir destek aracı olarak kullanılmalıdır.",
                "Önerim, sistemin insan denetimi altında ve düzenli kontrollerle kullanılmasıdır."],
            4: ["Önerim, sistemin yalnızca karar destek aracı olarak ve hekim onayıyla devreye alınması; önce sınırlı bir pilot uygulamada farklı demografik gruplardaki hata oranlarının izlenmesi, düzenli bağımsız yanlılık denetimleri yapılması ve açıklanabilir modellerin tercih edilmesidir.",
                "Yararların risklerden ağır basması için sistem aşamalı olarak, önce pilot bir serviste, insan denetiminde kullanılmalı; kararlar açıklanabilir olmalı, sonuçlar gruplara göre raporlanmalı ve hatalı kararlarda sorumluluk zinciri baştan tanımlanmalıdır."],
        },
    },
    "S4": {
        "C1": {
            0: [],
            1: ["Veri olarak internetteki bilgileri kullanırım.",
                "Sosyal medyadan öğrencilerin tüm paylaşımlarını toplarım."],
            2: ["Öğrencilerin daha önce aldığı kitapları kullanırım.",
                "Kitapların türlerini veri olarak kullanabilirim."],
            3: ["Öğrencilerin ödünç alma geçmişi ve bölüm bilgileri kullanılabilir, çünkü bunlar ilgi alanlarını gösterir; kitapların konu bilgileri de eklenir.",
                "Veri olarak ödünç alma kayıtları, öğrencilerin aldığı dersler ve kitapların anahtar kelimeleri kullanılır, çünkü bunlar öğrencinin ihtiyacıyla doğrudan ilişkilidir."],
            4: ["Ödünç alma geçmişi, bölüm ve ders kayıtları ile kitapların özet ve konu başlıkları kullanılır; öğrenci kimlikleri anonimleştirilir ve verilerin öneri amacıyla işlenmesi için açık rıza alınır.",
                "Sistemin temel verileri ödünç alma kayıtları, ders izlenceleri ve kitap katalog bilgileri olur; bunlar ilgi alanını yansıtır. Kişisel veriler KVKK kapsamında takma adlarla saklanır ve öğrenci istediğinde sistemden çıkabilir."],
        },
        "C2": {
            0: [],
            1: ["Yöntem olarak yapay zekaya sorarım, o önerir.",
                "Kitapları alfabetik sıraya göre öneririm."],
            2: ["Yöntem olarak işbirlikçi filtreleme kullanırım.",
                "Bir öneri algoritması kullanılabilir."],
            3: ["İşbirlikçi filtreleme ile benzer kitapları okuyan öğrencilerin tercihleri kullanılarak öneri yapılır; bu yöntem kitap içeriğini bilmeye gerek duymaz.",
                "İçerik tabanlı filtreleme ile öğrencinin okuduğu kitaplara konu bakımından benzeyen kitaplar önerilir, çünkü akademik ilgi alanları tutarlıdır."],
            4: ["İşbirlikçi ve içerik tabanlı filtrelemeyi birleştiren hibrit bir model kurarım: işbirlikçi kısım benzer öğrencilerin tercihlerinden öğrenir, içerik tabanlı kısım ise yeni öğrenci ve hiç ödünç alınmamış yeni kitaplarda ortaya çıkan soğuk başlangıç sorununu çözer.",
                "Hibrit bir yaklaşım seçerim; çünkü yalnız işbirlikçi filtreleme yeni kitapları hiç önermez, yalnız içerik tabanlı yöntem ise öğrenciyi dar bir alana hapseder. İkisini ağırlıklı birleştirmek hem soğuk başlangıcı hem de çeşitlilik sorununu hafifletir."],
        },
        "C3": {
            0: [],
            1: ["Öğrenciler mutlu olursa sistem başarılıdır.",
                "Sistemin hızlı çalışması başarı demektir."],
            2: ["Başarıyı önerilen kitapların alınıp alınmadığına bakarak ölçerim.",
                "Kullanıcılara anket yaparak başarı ölçülebilir."],
            3: ["Başarı, geçmiş verilerde precision@k ve recall@k gibi ölçütlerle değerlendirilir.",
                "Sistem iki öğrenci grubuyla A/B testi yapılarak önerilerin ödünç alınma oranına göre değerlendirilir."],
            4: ["Önce geçmiş veride precision@k ve recall@k ile çevrimdışı değerlendirme yapılır; sonra A/B testiyle önerilerin gerçek ödünç alınma oranı ve öğrenci memnuniyeti ölçülür; ayrıca öneri çeşitliliği izlenerek popüler kitapların baskınlığı kontrol edilir.",
                "Çevrimdışı olarak gizlenmiş son ödünç alma kayıtları üzerinde recall@10 hesaplanır, çevrimiçi olarak ise A/B testinde tıklama ve ödünç alma oranları karşılaştırılır; kapsama ve çeşitlilik ölçütleri de raporlanır."],
        },
    },
}

INTROS = [
    "",
    "Bu soruyu cevaplamak için önce kavramları açıklamak istiyorum.",
    "Derste işlediğimiz konulara göre cevabım şöyledir.",
    "",
    "Bu konu yapay zekanın temel konularından biridir.",
]

OFF_TOPIC = [
    "Yapay zeka hayatımızın her alanına girmiştir.",
    "Bence bu çok güzel bir soru.",
    "Teknoloji hızla gelişmektedir ve bunu takip etmek gerekir.",
    "Sınav süresi biraz kısaydı.",
]

FIRST_NAMES = ["Ahmet", "Ayşe", "Mehmet", "Zeynep", "Mustafa", "Elif", "Emre", "Merve", "Burak", "Esra",
               "Can", "Deniz", "Selin", "Oğuz", "Gizem", "Kaan", "Büşra", "Hakan", "İrem", "Serkan",
               "Ceren", "Tolga", "Şeyma", "Umut", "Gökhan"]
LAST_NAMES = ["Yılmaz", "Kaya", "Demir", "Şahin", "Çelik", "Yıldız", "Yıldırım", "Öztürk", "Aydın",
              "Özdemir", "Arslan", "Doğan", "Kılıç", "Aslan", "Çetin", "Kara", "Koç", "Kurt", "Özkan", "Şimşek"]
