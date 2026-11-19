# Puanlama kılavuzu — Halüsinasyon ve Etik soruları

Bu kılavuz, iki açık uçlu sorunun **insan değerlendiriciler** tarafından tutarlı biçimde puanlanması için
hazırlanmıştır. Aynı rubrik ve çapa yanıtlar modellere de verilir (`config/items.halusinasyon_etik.yaml`).
Böylece insanlar ve modeller aynı ölçütlerle puanlama yapar.

- **Puanlama türü:** analitik. Her soruda 3 ölçüt, her ölçüt 0–4 puan; soru başına toplam 0–12.
- **Birim:** her öğrenci yanıtı, her ölçüt için ayrı ayrı puanlanır.

---

## 1. Öğrenciye gösterilecek metin

**Yönerge (sınavın başında):**
> Bu bölümde iki açık uçlu soru vardır. Her soruya **kendi cümlelerinizle**, yaklaşık **150–300 kelime** ile
> yanıt veriniz (önerilen süre: soru başına 15 dakika). Her sorudaki (a), (b), (c) maddelerinin hepsini
> yanıtlayınız. Yazım hataları puanı etkilemez; düşüncelerinizin doğruluğu ve gerekçeleriniz değerlendirilir.
> Yanıtlarınızı yazarken yapay zekâ araçlarını ya da başka kaynakları kullanmayınız. Yanıtınıza adınızı,
> numaranızı ya da kişisel bilgilerinizi yazmayınız.

**Soru 1 — Halüsinasyon**
> Büyük dil modelleri (ör. ChatGPT, Gemini, Claude) bazen "halüsinasyon" olarak adlandırılan hatalar yapar.
> (a) Büyük dil modellerinde halüsinasyonun ne olduğunu açıklayınız ve somut bir örnek veriniz.
> (b) Bu modellerin neden halüsinasyon ürettiğini açıklayınız.
> (c) Halüsinasyonların zararını azaltmak için hem kullanıcıların hem de modeli geliştirenlerin neler
> yapabileceğini açıklayınız.

**Soru 2 — Etik**
> Bir şirket, iş başvurularındaki özgeçmişleri (CV) ön elemeden geçirmek için bir yapay zekâ sistemi kullanmaya
> karar vermiştir. Sistem, şirketin son on yılda işe aldığı çalışanların verileriyle eğitilmiştir. Başvuruları
> otomatik olarak puanlamakta ve düşük puan alan adayları hiçbir insan incelemesi olmadan elemektedir.
> (a) Bu uygulamanın doğurabileceği etik sorunları belirleyiniz ve her birinin neden sorun olduğunu açıklayınız.
> (b) Bu sorunlardan etkilenebilecek tarafları (paydaşları) ve olası sonuçlarını tartışınız.
> (c) Şirkete, bu uygulamayı sürdürüp sürdürmemesi ve sürdürecekse hangi koşullarla ve önlemlerle sürdürmesi
> gerektiği konusunda gerekçeli bir öneri sununuz.

**Moodle:** Her soru ayrı bir **Kompozisyon (Essay)** sorusu olarak eklenmelidir; sıra 1 = Soru 1, 2 = Soru 2
olmalıdır. Yanıt biçimi düz metin olmalı, dosya eklemeye izin verilmemelidir. Gerekirse kelime sınırı
(ör. en fazla 400) tanımlanabilir. Araştırma amaçlı veri kullanımı için etik kurul onayı ve öğrenci
bilgilendirmesi/onamı sınavdan önce tamamlanmalıdır.

---

## 2. Genel puanlama kuralları (her iki soru için)

1. **Analitik puanlama.** Her ölçütü yalnızca kendi tanımlayıcısına göre, diğer ölçütlerden bağımsız puanlayın.
   Bir ölçütteki zayıflık başka bir ölçütün puanını düşürmez.
2. **Yer önemli değildir.** Bir bilgi hangi bölümde yazılmışsa yazılsın ilgili ölçütte puanlanır. Örneğin
   (a) bölümünde verilen bir neden, C2 "Nedenler" ölçütünde sayılır. Aynı cümle birden çok ölçüte katkı
   verebilir.
3. **Biçim puanlanmaz.** Uzunluk, yazım ve dilbilgisi, üslup, madde işaretiyle yazma, anlam bozulmadıkça puanı
   etkilemez. Teknik terimlerin İngilizcesi (hallucination, bias, RAG) kabul edilir.
4. **Adlandırma ve açıklama.**
   - *Adlandırma:* kavramın adını ya da özünü doğru söylemek (ör. "sistem yanlı olabilir").
   - *Açıklama:* bu bağlamda **neden ya da nasıl** ilişkisini en az bir cümleyle kurmak (ör. "geçmişte daha çok
     erkek işe alındığı için sistem bu örüntüyü öğrenir ve kadın adayları düşük puanlar").
5. **Sınırda kalma kuralı.** Yanıt iki düzey arasında kalıyorsa, üst düzeyin **tüm** koşulları karşılanmıyorsa alt
   düzeyi verin.
6. **Kavram yanlışı.** Doğru içeriğin yanında, o ölçütle ilgili **açık bir kavram yanlışı** varsa, ulaşılan
   düzeyden **1 puan düşün** (en düşük 1). Örnekler:
   - halüsinasyonu "modelin bilerek yalan söylemesi" diye tanımlamak;
   - "RAG, modeli baştan eğitmektir" demek;
   - "yapay zekâ yanlı olamaz, çünkü duyguları yoktur" demek.

   Küçük kesinlik hataları (ör. yanlış bir yıl) bu kurala girmez.
7. **Soruyu tekrarlamak** ya da soru metnindeki ifadeleri aktarmak puan getirmez.
8. **Boş, "bilmiyorum" ya da tamamen ilgisiz** yanıtlar tüm ölçütlerde 0 alır.
9. **Kopya ya da yapay zekâyla yazılmış olma şüphesi** puanı etkilemez. Şüphe varsa "Not" sütununa yazın;
   araştırma ekibi ayrıca karar verir.
10. **[AD], [NUMARA] gibi maskeler** anonimleştirmeden gelir; yok sayın.
11. **Kararın yönü puanlanmaz** (Soru 2, C3). "Sistem kullanılmamalı" kararı da "koşullu kullanılmalı" kararı da,
    gerekçe kalitesine göre tam puan alabilir.

---

## 3. Soru 1 — Halüsinasyon

### Örnek tam puanlık yanıt (12/12)
> Halüsinasyon, bir dil modelinin gerçeğe aykırı, doğrulanamayan ya da tamamen uydurma bir bilgiyi akıcı ve
> kendinden emin bir dille, sanki doğruymuş gibi üretmesidir. Model bunu bilerek yapmaz; bir niyeti yoktur. Ancak
> cevap ikna edici göründüğü için kullanıcı hatayı fark etmekte zorlanır. Örneğin bir öğrenci ödevi için kaynak
> istediğinde model, yazar adı, yıl ve dergi adıyla birlikte gerçekte var olmayan bir makale uydurabilir.
>
> Bunun temel nedeni, büyük dil modellerinin bilgiyi bir veri tabanından aramaması; eğitim verisindeki
> örüntülere dayanarak bir sonraki kelimeyi olasılıksal olarak tahmin etmesidir. Bu süreç dilsel olarak
> tutarlı bir metin üretir, ama metnin doğruluğunu denetleyen bir mekanizma içermez. Ayrıca eğitim
> verisindeki eksik, hatalı ya da güncel olmayan bilgiler, eğitimin akıcı ve yardımcı görünen cevapları
> ödüllendirmesi (model "bilmiyorum" demek yerine tahmin yürütür) ve belirsiz ya da yanlış öncüllü sorular da
> halüsinasyona yol açar.
>
> Kullanıcılar önemli bilgileri güvenilir kaynaklardan doğrulamalı, modelden kaynak istemeli ve bu kaynakların
> gerçekten var olduğunu kontrol etmeli, sağlık ya da hukuk gibi kritik konularda yalnızca modele
> güvenmemelidir. Geliştiriciler ise modeli güvenilir belgelere dayandıran erişimle zenginleştirilmiş üretim
> (RAG) kullanabilir. Böylece cevap, modelin belleği yerine bulunup getirilen belgelerden üretilir ve kaynak
> gösterilebilir. Ayrıca modeli emin olmadığında bunu belirtecek biçimde eğitebilir, uyarılar ekleyebilir ve
> modeli sistematik testlerle değerlendirebilirler.

### C1 — Tanım ve örnek (0–4)

| Puan | Tanımlayıcı |
|---|---|
| 0 | Tanım yok, tamamen yanlış (çökme, virüs, yavaşlama, görüntü bozulması) ya da ilgisiz. |
| 1 | Çok genel ya da eksik tanım ("yanlış cevap vermesi", "hata yapması"); uydurma bilgi fikri yok. Örnek yok ya da örnek halüsinasyon değil. |
| 2 | Temel tanım doğru (gerçeğe aykırı ya da uydurma bilgi üretme), ama örnek yok ya da çok genel. **Ya da** uygun somut örnek var, ama tanım belirsiz. |
| 3 | Doğru tanım **ve** somut, uygun bir örnek. |
| 4 | Doğru tanım ve somut örnek; **ek olarak** bilginin akıcı ve kendinden emin biçimde, doğruymuş gibi sunulduğu **ya da** bunun kasıtlı bir yalan olmadığı açıkça belirtilmiş. |

**Kabul edilen somut örnekler:**
- var olmayan kaynak, makale, kitap ya da DOI;
- uydurma mahkeme kararı ya da yasa maddesi;
- yanlış tarih, istatistik ya da kişi bilgisi;
- olmayan bir fonksiyonu öneren kod;
- yaşamayan bir olayı "olmuş" gibi anlatma.

**Örnek sayılmaz:**
- "yanlış bilgi verebilir" (genel ifade);
- yazım hatası, sistem çökmesi, yavaş yanıt;
- görüntü üretimindeki bozulmalar. Görüntü modelleri sorulmadığı için bu, tek başına C1 örneği olarak kabul
  edilmez.

### C2 — Nedenler (0–4)

| Puan | Tanımlayıcı |
|---|---|
| 0 | Neden yok ya da tamamen yanlış (internet kesintisi, virüs, "bilerek yalan söylemek için tasarlanmıştır", "bilgisayar yorulur"). |
| 1 | Belirsiz ya da yüzeysel ("yapay zekâ mükemmel değildir", "hata yapabilir"); kabul edilen nedenlerden hiçbiri yok. |
| 2 | Kabul edilen nedenlerden **yalnızca biri** adlandırılmış, açıklanmamış. |
| 3 | En az **iki** neden adlandırılmış **ya da** biri mekanizmasıyla açıklanmış. |
| 4 | En az iki neden **ve** en az biri mekanizmasıyla doğru açıklanmış; olasılıksal üretimin doğruluk garantisi vermediği anlaşılmış. |

**Kabul edilen nedenler:**
- **(a)** Olasılıksal ya da istatistiksel sonraki kelime tahmini; modelin bilgiyi "bilmemesi", doğruluk
  denetiminin olmaması.
- **(b)** Eğitim verisindeki eksik, hatalı, yanlı ya da **güncel olmayan** bilgi; bilgi kesim tarihi.
- **(c)** Eğitimin akıcı ve yardımsever cevabı ödüllendirmesi; modelin "bilmiyorum" demede zayıf olması,
  belirsizliği ifade etmemesi.
- **(d)** Belirsiz, yönlendirici ya da yanlış öncüllü istemler (ör. var olmayan bir şeyi sormak).
- **(e)** Veride az temsil edilen, nadir ya da uzmanlık gerektiren konular.

**Mekanizma örneği (3–4 için):** "Model en olası kelimeyi seçer; bu, dilsel olarak tutarlı ama gerçekte yanlış
bir cümle üretebilir. Çünkü model, cümlenin doğru olup olmadığını kontrol etmez."

### C3 — Azaltma yolları (0–4)

| Puan | Tanımlayıcı |
|---|---|
| 0 | Öneri yok ya da ilgisiz ("antivirüs kurulmalı", "internet hızlandırılmalı"). |
| 1 | Tek ve belirsiz öneri ("dikkatli olunmalı", "hiç kullanılmamalı"). |
| 2 | Yalnızca **bir** doğru ve somut yöntem. |
| 3 | En az **iki** doğru ve somut yöntem (yalnızca kullanıcı ya da yalnızca geliştirici tarafı olabilir). |
| 4 | **Hem kullanıcı hem geliştirici** için en az birer doğru yöntem (toplam en az üç) **ve** en az birinin nasıl işe yaradığı açıklanmış. |

**Kullanıcı tarafı:**
- güvenilir kaynaklardan doğrulama;
- kaynak isteme ve bu kaynakların var olduğunu kontrol etme;
- birden çok kaynağı karşılaştırma;
- kritik kararlarda (sağlık, hukuk, finans) tek başına güvenmeme;
- açık ve bağlamlı istem yazma;
- modelden emin olmadığında belirtmesini isteme.

**Geliştirici tarafı:**
- RAG ya da güvenilir belgelere veya veri tabanına dayandırma;
- kaynak ya da atıf gösterme;
- "bilmiyorum" demeyi ödüllendiren eğitim (insan geri bildirimi);
- güven göstergesi ve uyarılar;
- olgu denetimi (fact-checking);
- daha kaliteli ve güncel veri;
- sistematik test ve değerlendirme.

**Sayılmaz:** "dikkatli olunmalı" (belirsiz); "yapay zekâ yasaklanmalı" (yöntem değil, yargı).

---

## 4. Soru 2 — Etik

### Örnek tam puanlık yanıt (12/12)
> En önemli sorun yanlılık ve ayrımcılıktır. Sistem son on yılın işe alım verisiyle eğitildiği için o dönemde
> belirli bir cinsiyetten, okuldan, yaş grubundan ya da bölgeden daha çok kişi işe alındıysa bu örüntüyü
> "başarı" olarak öğrenir ve benzer olmayan adayları düşük puanlar. Cinsiyet doğrudan kullanılmasa bile okul
> adı, adres ya da üye olunan kulüp gibi vekil değişkenler üzerinden dolaylı ayrımcılık sürebilir; geçmişteki
> eşitsizlik böylece otomatikleşir. İkinci sorun şeffaflık ve açıklanabilirliktir: aday neden elendiğini
> bilemez. Üçüncüsü insan denetiminin olmaması ve hesap verebilirliktir: hatalı bir elemede sorumlunun kim
> olduğu belirsizdir; KVKK, yalnızca otomatik işlemeyle aleyhe sonuç doğuran kararlara itiraz hakkı tanır.
> Ayrıca aday ve çalışan verilerinin rıza ve amaçla sınırlılık ilkelerine uygun işlenmesi bir gizlilik
> sorunudur.
>
> Bu durumdan en çok, sistemin öğrendiği profile benzemeyen adaylar etkilenir; nitelikli oldukları hâlde haksız
> yere elenir, iş fırsatı kaybederler. Şirket de yetenekli adayları kaçırır, çalışan çeşitliliği azalır, dava ve
> itibar riskiyle karşılaşır. Sistem binlerce başvuruya aynı kuralı uyguladığı için bireysel haksızlıklar
> toplumsal ölçekte eşitsizliği derinleştirebilir; verimlilik ile adalet arasında bir gerilim vardır.
>
> Önerim, sistemin tek başına karar veren değil, insan değerlendiriciyi destekleyen bir araç olarak
> kullanılmasıdır. Hiçbir aday insan incelemesi olmadan elenmemelidir. Kullanıma devam etmeden önce bağımsız bir
> yanlılık denetimi yapılmalı; cinsiyet, yaş ve benzeri gruplar arasındaki seçilme oranları düzenli olarak
> karşılaştırılıp raporlanmalı; vekil değişkenler çıkarılmalı ve eğitim verisi dengelenmelidir. Adaylara yapay
> zekâ kullanıldığı bildirilmeli, karar gerekçesi ve itiraz yolu sunulmalı, veriler KVKK'ya uygun işlenmelidir.
> Denetimde gruplar arasında anlamlı fark bulunursa sistem durdurulmalıdır.

### C1 — Etik sorunların belirlenmesi ve açıklanması (0–4)

| Puan | Tanımlayıcı |
|---|---|
| 0 | Etik sorun yok ya da yalnızca teknik veya maliyet konuları ("pahalıdır", "yavaş çalışır"). |
| 1 | Belirsiz tek endişe ("haksızlık olabilir", "yapay zekâ hata yapar"); etik kavram adlandırılmamış. |
| 2 | **Bir** sorun adlandırılıp açıklanmış **ya da** birden çok sorun yalnızca liste hâlinde adlandırılmış. |
| 3 | En az **iki** farklı sorun adlandırılmış **ve** her biri için neden sorun olduğu açıklanmış. |
| 4 | En az **üç** farklı sorun açıklanmış **ve** yanlılığın bu senaryodaki mekanizması (geçmiş veriden öğrenip eşitsizliği yeniden üretme ya da vekil değişkenler) doğru açıklanmış. |

**Kabul edilen etik sorunlar (farklı sayılanlar):**
1. **Yanlılık ve ayrımcılık:** geçmiş işe alım örüntüsünü öğrenme; cinsiyet, yaş, okul, bölge, engellilik;
   vekil değişkenler.
2. **Şeffaflık ve açıklanabilirlik:** aday neden elendiğini bilemez; kara kutu.
3. **Hesap verebilirlik ve itiraz hakkı:** hatada sorumlu belirsiz; itiraz yolu yok.
4. **İnsan denetiminin olmaması:** tam otomatik karar; insanın karar sürecinden çıkarılması.
5. **Gizlilik ve kişisel veriler:** rıza ya da aydınlatma, amaçla sınırlılık, saklama; çalışan verilerinin
   eğitimde kullanılması.
6. **Doğruluk ya da geçerlik:** "geçmişte işe alınan = iyi aday" varsayımı; hatalı elemenin bedeli.

"Hesap verebilirlik" ve "insan denetimi" aynı paragrafta birlikte işlenmişse, ikisi de açıklanmışsa iki ayrı
sorun sayılır.

### C2 — Paydaşlar ve sonuçlar (0–4)

| Puan | Tanımlayıcı |
|---|---|
| 0 | Paydaş ya da sonuç belirtilmemiş. |
| 1 | Genel ifade ("insanlar zarar görür", "herkes etkilenir"). |
| 2 | **Bir** paydaş ve onun için bir somut sonuç. |
| 3 | En az **iki** farklı paydaş, her biri için somut sonuç. |
| 4 | En az iki paydaş ve somut sonuçlar; **ek olarak** ölçek etkisi, bireysel zararın toplumsal eşitsizliğe dönüşmesi **ya da** çatışan çıkarlar (verimlilik ve adalet) tartışılmış. |

**Paydaşlar ve örnek sonuçlar:**

| Paydaş | Örnek sonuçlar |
|---|---|
| Adaylar (özellikle dezavantajlı gruplar) | haksız eleme, fırsat kaybı, güven kaybı |
| Şirket | yetenek kaybı, çeşitlilik azalması, dava ya da ceza riski, itibar kaybı |
| Mevcut çalışanlar | verileri izinsiz kullanılır; homojen bir çalışma ortamı oluşur |
| İK uzmanları | rol ve sorumluluk belirsizliği |
| Toplum ve işgücü piyasası | eşitsizliğin derinleşmesi |
| Yazılım sağlayıcı ve düzenleyiciler | sorumluluk ve denetim yükü |

"Adaylar" ile "kadın adaylar" aynı paydaştır; "adaylar" ve "şirket" farklıdır.

### C3 — Gerekçeli öneri (0–4)

| Puan | Tanımlayıcı |
|---|---|
| 0 | Öneri yok. |
| 1 | Gerekçesiz kesin yargı ("kesinlikle kullanılmalı", "yasaklanmalı"). |
| 2 | Öneri var, ancak gerekçesi zayıf ya da önlemler belirsiz ("dikkatli kullanılmalı", "kontrol edilmeli"). |
| 3 | Gerekçeli ve tutarlı öneri, en az **iki** somut önlemle. |
| 4 | Sorunlarla doğrudan eşleşen en az **üç** somut önlem; **koşullu karar** (hangi koşulda sürdürülmeli ya da durdurulmalı) **ve** önlemlerin nasıl izleneceği belirtilmiş. |

**Kabul edilen somut önlemler:**
- insan denetimi: sistem yalnızca destek aracı olur, düşük puanlılar bir insan tarafından incelenir;
- bağımsız ya da düzenli yanlılık denetimi: gruplara göre seçilme oranlarının karşılaştırılması;
- vekil ya da hassas değişkenlerin çıkarılması, dengeli ve temsili veri;
- şeffaflık: adaylara YZ kullanımının bildirilmesi, karar gerekçesi, itiraz hakkı;
- KVKK uyumu: aydınlatma, açık rıza, veri minimizasyonu;
- pilot uygulama ve performans izleme;
- açıklanabilir model kullanımı.

"Sistem durdurulmalı" kararı, sorunlara dayanan bir gerekçe ve somut alternatif önlemlerle (ör. "insan
değerlendirici ve yapılandırılmış mülakat kullanılsın; yeniden ancak bağımsız denetimden geçerse kullanılsın")
3–4 alabilir.

---

## 5. Çapa (örnek) yanıtlar

Değerlendirici eğitiminde kullanılacak çapalar `config/items.halusinasyon_etik.yaml` dosyasındadır:

- **S1-A0 … S1-A4, S2-A0 … S2-A4:** her ölçütte aynı düzeyde olan örnekler (0'dan 4'e).
- **S1-K1, S1-K2, S2-K1, S2-K2:** **karma profilli** örnekler. Ölçütlerin birbirinden bağımsız puanlandığını
  göstermek için seçilmiştir. Örneğin S1-K1'de tanım mükemmel (C1 = 4), nedenler yok denecek kadar zayıftır
  (C2 = 1).

Arayüzde (`uv run scoring ui`), **Yanıt dene** sekmesindeki **Hazır örnek yükle** listesiyle bu çapalar
görülebilir.

> Bu çapalar araştırmacı tarafından yazılmış örneklerdir. Pilot uygulamadan sonra, altın sete **girmeyecek**
> gerçek pilot yanıtlardan seçilen çapalarla desteklenmeleri önerilir. Çapa olarak kullanılan bir yanıt altın
> sete alınamaz; sistem bunu otomatik denetler (`scoring check-leakage`).

---

## 6. Değerlendirici eğitimi ve puanlama süreci

1. **Eğitim (yaklaşık 1 saat):** Değerlendiriciler soruları, bu kılavuzu ve çapaları birlikte okur. Karma
   profilli çapalar üzerinde analitik puanlama tartışılır.
2. **Kalibrasyon turu 1:** Altın sete girmeyecek 20 pilot yanıt (her sorudan 10) bağımsız olarak puanlanır.
   Farklılıklar tartışılır ve gerekiyorsa bu kılavuza açıklayıcı not eklenir. Not eklendiyse tarih ve değişiklik
   kaydedilir.
3. **Kalibrasyon turu 2:** Yeni 20 pilot yanıt puanlanır. Hedef, ölçüt düzeyinde **tam uyum ≥ %70** ve
   **QWK ≥ .80**. Hedefe ulaşılamazsa bir tur daha yapılır.
4. **Asıl puanlama (altın set):**
   - İki değerlendirici, birbirinden habersiz (kör) puanlar.
   - Yanıtlar karışık sıradadır (`sample-gold` ile üretilen Excel dosyası).
   - Değerlendiriciler resmî notu, model puanlarını ve birbirlerinin puanlarını **görmez**.
   - Bir oturumda en fazla 60–80 yanıt puanlanır; yorgunluk etkisini azaltmak için ara verilir.
5. **Hakem:** İki değerlendiricinin bir ölçütte farklı puan verdiği yanıtlar üçüncü bir değerlendiriciye (hakem)
   gider. Hakem iki puanı görmeden, yalnızca o ölçüt için puan verir. Bu, sistemdeki
   `consensus: adjudicator_or_mean` kuralına karşılık gelir.
6. **Kayıt:** Puanlar `data/human_scores.csv` dosyasına aktarılır. Sütunlar: `response_id, rater_id, role, set,
   criterion_id, score`. Rol değerleri `rater1`, `rater2`, `adjudicator` ve `official`; set değerleri `gold` ve
   `official`.

## 7. Kodlama formu

Değerlendirici başına bir çalışma sayfası:

| Yanıt kodu | Soru | C1 | C2 | C3 | Not (isteğe bağlı) |
|---|---|---|---|---|---|
| R00017 | S1 | 3 | 2 | 4 | |
| R00042 | S2 | 2 | 3 | 3 | Yanıt yarım kalmış |

`sample-gold` komutunun ürettiği `data/derived/gold_rating_sheet.xlsx` dosyası bu biçimdedir: her soru ayrı
sayfada, rubrik ayrı sayfada, puanlar açılır listeden seçilir.

## 8. Örnekleme notu

Altın set varsayılan olarak soru başına 300 yanıttır (`experiment.yaml > gold.per_item`). Sınava katılan öğrenci
sayısı bundan azsa o sorunun tüm yanıtları alınır. Öğrenilmiş ağırlıkların ve gömme koşulunun güvenilir
olması için soru başına **en az 150–200** altın set yanıtı önerilir.
