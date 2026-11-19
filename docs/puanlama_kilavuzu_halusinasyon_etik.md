# Puanlama kılavuzu — Halüsinasyon ve Etik soruları (kısa sürüm, çevrim içi sınav)

Bu kılavuz, iki kısa açık uçlu sorunun **insan değerlendiriciler** tarafından tutarlı biçimde puanlanması için
hazırlanmıştır. Aynı rubrik ve örnek (çapa) yanıtlar modellere de verilir
(`config/items.halusinasyon_etik.yaml`). Böylece insanlar ve modeller aynı ölçütlerle puanlar.

- **Puanlama türü:** analitik. Her soruda 2 ölçüt vardır, her ölçüt 0–4 puandır. Soru başına toplam 0–8 puan.
- **Beklenen yanıt:** 80–150 kelime, soru başına yaklaşık 7–8 dakika.

---

## 1. Öğrenciye gösterilecek metin

**Yönerge**
> Bu bölümde iki kısa açık uçlu soru vardır. Her soruya kendi cümlelerinizle, yaklaşık 80–150 kelimeyle
> yanıt veriniz. Yazım hataları puanı etkilemez. Yanıtlarken yapay zekâ araçlarını kullanmayınız; yanıtınıza
> adınızı ya da numaranızı yazmayınız.

**Soru 1 — Halüsinasyon**
> Büyük dil modellerinde (ör. ChatGPT) "halüsinasyon" nedir ve neden ortaya çıkar? Bir örnekle açıklayınız.

**Soru 2 — Etik**
> Bir şirket, iş başvurularını son on yılda işe aldığı çalışanların verileriyle eğitilmiş bir yapay zekâ ile
> değerlendiriyor ve düşük puan alan adayları hiçbir insan incelemesi olmadan eliyor. Bu uygulamadaki etik
> sorunları açıklayınız ve şirkete gerekçeli bir öneride bulununuz.

**Moodle ayarları**
- Her soru ayrı bir **Kompozisyon (Essay)** sorusu olarak eklenir.
- Sıra: 1. soru Halüsinasyon, 2. soru Etik.
- Yanıt biçimi düz metindir; dosya eklenmez. İsterseniz en fazla 250 kelime sınırı konabilir.
- Araştırma amaçlı veri kullanımı için etik kurul onayı ve öğrenci bilgilendirmesi/onamı sınavdan önce
  tamamlanmalıdır.

---

## 2. Genel puanlama kuralları

1. **Analitik puanlama.** Her ölçütü yalnızca kendi tanımlayıcısına göre, diğer ölçütten bağımsız puanlayın.
2. **Biçim puanlanmaz.** Uzunluk, yazım/dilbilgisi ve üslup, anlam bozulmadıkça puanı etkilemez. Teknik
   terimlerin İngilizcesi (hallucination, bias) kabul edilir.
3. **Adlandırma ve açıklama arasındaki fark.**
   - *Adlandırma:* kavramın adını ya da özünü doğru söylemek (ör. "sistem yanlı olabilir").
   - *Açıklama:* bu bağlamda neden ya da nasıl ilişkisini en az bir cümleyle kurmak (ör. "geçmişte daha çok
     erkek işe alındığı için sistem bu örüntüyü öğrenir ve kadın adayları düşük puanlar").
4. **Sınırda kalma kuralı.** Yanıt iki düzey arasında kalıyorsa ve üst düzeyin **tüm** koşulları
   karşılanmıyorsa alt düzeyi verin.
5. **Kavram yanlışı.** Doğru içeriğin yanında o ölçütle ilgili **açık bir kavram yanlışı** varsa, ulaşılan
   düzeyden **1 puan düşün** (en düşük 1).
   - Örnekler: halüsinasyonu "modelin bilerek yalan söylemesi" diye tanımlamak; "yapay zekâ yanlı olamaz,
     çünkü duyguları yoktur" demek.
   - Küçük kesinlik hataları (ör. yanlış bir yıl) bu kurala girmez.
6. **Soruyu tekrarlamak** puan getirmez.
7. **Boş, "bilmiyorum" ya da tamamen ilgisiz** yanıtlar tüm ölçütlerde 0 alır.
8. **Kopya ya da yapay zekâyla yazılmış olma şüphesi** puanı etkilemez; şüpheyi "Not" sütununa yazın.
9. **[AD], [NUMARA] gibi maskeler** anonimleştirmeden gelir; yok sayın.
10. **Soru 2'de kararın yönü puanlanmaz.** "Kullanılmamalı" kararı da "koşullu kullanılmalı" kararı da gerekçe
    kalitesine göre tam puan alabilir. Öneri ölçütü (C2), sorun ölçütünden (C1) bağımsızdır. Öğrenci sorunları
    zayıf açıklasa bile, önerdiği önlemler hangi sorunu çözdüğünü kendi içinde belirtiyorsa C2'de yüksek puan
    alabilir.

---

## 3. Soru 1 — Halüsinasyon

### Örnek tam puanlık yanıt (8/8)
> Halüsinasyon, bir dil modelinin gerçeğe aykırı ya da tamamen uydurma bir bilgiyi akıcı ve kendinden emin bir
> dille, sanki doğruymuş gibi üretmesidir. Model bunu bilerek yapmaz; ancak cevap ikna edici olduğu için hata
> kolay fark edilmez. Örneğin ödev için kaynak istendiğinde, yazar adı ve yılıyla birlikte gerçekte var olmayan
> bir makale uydurabilir. Bunun temel nedeni, modelin bilgiyi bir veri tabanından aramaması; eğitim verisindeki
> örüntülere dayanarak bir sonraki kelimeyi olasılıksal olarak tahmin etmesidir. Bu süreç dilsel olarak tutarlı
> bir metin üretir, ama doğruluğunu denetlemez. Eğitim verisindeki eksik, hatalı ya da eski bilgiler ve modelin
> "bilmiyorum" demek yerine tahmin yürütmeye eğilimli olması da halüsinasyona yol açar.

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
- olmayan bir fonksiyon öneren kod;
- yaşanmamış bir olayı olmuş gibi anlatma.

**Örnek sayılmaz:**
- "yanlış bilgi verebilir" gibi genel ifadeler;
- yazım hatası, çökme, yavaş yanıt;
- görüntü üretimindeki bozulmalar.

### C2 — Nedenler (0–4)

| Puan | Tanımlayıcı |
|---|---|
| 0 | Neden yok ya da tamamen yanlış (internet kesintisi, virüs, "bilerek yalan söylemek için tasarlanmıştır", "bilgisayar yorulur"). |
| 1 | Belirsiz ya da yüzeysel ("yapay zekâ mükemmel değildir", "hata yapabilir"); kabul edilen nedenlerden hiçbiri yok. |
| 2 | Kabul edilen nedenlerden **yalnızca biri** adlandırılmış, açıklanmamış. |
| 3 | En az **iki** neden adlandırılmış **ya da** biri mekanizmasıyla açıklanmış. |
| 4 | En az iki neden **ve** en az biri mekanizmasıyla doğru açıklanmış; olasılıksal üretimin doğruluk garantisi vermediği anlaşılmış. |

**Kabul edilen nedenler:**
- **(a)** Olasılıksal "sonraki kelime" tahmini; modelin bilgiyi "bilmemesi", doğruluk denetiminin olmaması.
- **(b)** Eğitim verisindeki eksik, hatalı, yanlı ya da güncel olmayan bilgi.
- **(c)** Eğitimin akıcı cevabı ödüllendirmesi; modelin "bilmiyorum" demede zayıf olması.
- **(d)** Belirsiz ya da yanlış öncüllü sorular (ör. var olmayan bir şeyi sormak).
- **(e)** Veride az temsil edilen ya da uzmanlık gerektiren konular.

**Mekanizma örneği (3–4 puan için):**
> "Model en olası kelimeyi seçer; bu dilsel olarak tutarlı ama gerçekte yanlış bir cümle üretebilir, çünkü
> model cümlenin doğru olup olmadığını kontrol etmez."

---

## 4. Soru 2 — Etik

### Örnek tam puanlık yanıt (8/8)
> En önemli sorun yanlılıktır. Sistem son on yılın işe alım verisiyle eğitildiği için geçmişte hangi gruplar
> daha çok işe alındıysa onları "iyi aday" olarak öğrenir ve benzemeyenleri düşük puanlar. Cinsiyet doğrudan
> kullanılmasa bile okul ya da adres gibi vekil bilgiler üzerinden ayrımcılık sürebilir; eski eşitsizlik
> otomatikleşir. İkinci sorun, kararların insan denetimi olmadan verilmesi ve açıklanamamasıdır: aday neden
> elendiğini bilemez, itiraz edemez ve hata olduğunda sorumlu belirsizdir. Önerim, sistemin yalnızca İK uzmanını
> destekleyen bir araç olarak kullanılması ve hiçbir adayın insan incelemesi olmadan elenmemesidir. Ayrıca
> cinsiyet ve yaş gibi gruplara göre seçilme oranları düzenli olarak denetlenmeli, adaylara yapay zekâ
> kullanıldığı bildirilip itiraz yolu açılmalıdır. Denetimde gruplar arasında anlamlı fark çıkarsa sistem
> durdurulmalıdır.

### C1 — Etik sorunlar ve açıklaması (0–4)

| Puan | Tanımlayıcı |
|---|---|
| 0 | Etik sorun yok ya da yalnızca teknik veya maliyet konuları ("pahalıdır", "hızlı çalışır"). |
| 1 | Belirsiz tek endişe ("haksızlık olabilir", "yapay zekâ hata yapar"); etik kavram adlandırılmamış. |
| 2 | Bir sorun adlandırılmış ama açıklanmamış **ya da** birden çok sorun yalnızca liste hâlinde sayılmış. |
| 3 | En az **bir** etik sorun bu senaryoya bağlanarak açıklanmış. |
| 4 | En az **iki** farklı sorun açıklanmış **ve** yanlılığın bu senaryodaki mekanizması (geçmiş veriden öğrenip eşitsizliği yeniden üretme ya da vekil değişkenler) doğru açıklanmış. |

**Kabul edilen etik sorunlar:**
1. **Yanlılık ve ayrımcılık:** geçmiş işe alım örüntüsünü öğrenme; cinsiyet, yaş, okul, bölge, engellilik;
   vekil değişkenler.
2. **Şeffaflık ve açıklanabilirlik:** aday neden elendiğini bilemez.
3. **Hesap verebilirlik ve itiraz hakkı:** hatada sorumlu belirsizdir, itiraz yolu yoktur.
4. **İnsan denetiminin olmaması:** karar tamamen otomatiktir.
5. **Gizlilik ve kişisel veriler:** rıza, aydınlatma, amaçla sınırlılık.
6. **Doğruluk ve geçerlik:** "geçmişte işe alınan = iyi aday" varsayımı.

### C2 — Gerekçeli öneri (0–4)

| Puan | Tanımlayıcı |
|---|---|
| 0 | Öneri yok. |
| 1 | Gerekçesiz kesin yargı ("kesinlikle kullanılmalı", "yasaklanmalı"). |
| 2 | Öneri var ama belirsiz ya da gerekçesi zayıf ("dikkatli kullanılmalı", "kontrol edilmeli"). |
| 3 | En az **bir** somut önlem, gerekçesiyle (hangi sorunu çözdüğü belli). |
| 4 | En az **iki** somut önlem, sorunlarla açıkça eşleşmiş ve gerekçelendirilmiş; **ek olarak** koşullu karar (hangi durumda sürdürülmeli ya da durdurulmalı) **ya da** önlemin nasıl izleneceği belirtilmiş. |

**Kabul edilen somut önlemler:**
- **İnsan denetimi:** sistem yalnızca destek aracı olur; düşük puanlı başvuruları bir insan inceler.
- **Yanlılık denetimi:** gruplara göre seçilme oranları karşılaştırılır.
- **Veri düzeltme:** vekil ya da hassas değişkenler çıkarılır, eğitim verisi dengelenir.
- **Şeffaflık:** adaylara yapay zekâ kullanıldığı bildirilir, karar gerekçesi verilir, itiraz hakkı tanınır.
- **KVKK uyumu.**
- **Pilot uygulama ve izleme.**

"Sistem durdurulmalı" önerisi, sorunlara dayanan bir gerekçe ve somut bir alternatifle (ör. "insan
değerlendirici kullanılsın; sistem ancak bağımsız denetimden geçerse yeniden kullanılsın") 3–4 alabilir.

---

## 5. Çapa (örnek) yanıtlar

Değerlendirici eğitiminde kullanılacak çapalar `config/items.halusinasyon_etik.yaml` dosyasındadır.

- **S1-A0 … S1-A4, S2-A0 … S2-A4:** her iki ölçütte aynı düzeyde olan örnekler (0'dan 4'e).
- **S1-K1, S1-K2, S2-K1, S2-K2:** **karma profilli** örnekler. Ölçütlerin birbirinden bağımsız puanlandığını
  gösterir. Örneğin S1-K1'de tanım mükemmeldir (C1 = 4), neden ise yok denecek kadar zayıftır (C2 = 1).

Arayüzde (`uv run scoring ui`), **Yanıt dene** sekmesindeki **Hazır örnek yükle** listesiyle bu çapalar
görülebilir.

> Bu çapalar araştırmacı tarafından yazılmış örneklerdir. Pilot uygulamadan sonra, altın sete **girmeyecek**
> gerçek yanıtlardan seçilen çapalarla desteklenmeleri önerilir. Çapa olarak kullanılan bir yanıt altın sete
> alınamaz; sistem bunu otomatik denetler (`scoring check-leakage`).

---

## 6. Değerlendirici eğitimi ve puanlama süreci

1. **Eğitim (yaklaşık 45 dakika):** Değerlendiriciler sorular, bu kılavuz ve çapalar üzerinde birlikte çalışır.
   Karma profilli çapalar tartışılır.
2. **Kalibrasyon turu 1:** Altın sete girmeyecek 20 pilot yanıt (her sorudan 10) bağımsız olarak puanlanır.
   Farklılıklar tartışılır. Gerekirse bu kılavuza tarihli bir açıklayıcı not eklenir.
3. **Kalibrasyon turu 2:** Yeni 20 pilot yanıt puanlanır. Hedef: ölçüt düzeyinde **tam uyum ≥ %70** ve
   **QWK ≥ .80**. Hedefe ulaşılamazsa bir tur daha yapılır.
4. **Asıl puanlama (altın set):**
   - İki değerlendirici birbirinden habersiz (kör) puanlar.
   - Yanıtlar karışık sıradadır (`sample-gold` ile üretilen Excel dosyası).
   - Değerlendiriciler resmî notu, model puanlarını ve birbirlerinin puanlarını görmez.
   - Bir oturumda en fazla 80–100 yanıt puanlanır.
5. **Hakem:** İki değerlendiricinin bir ölçütte farklı puan verdiği yanıtlar, iki puanı görmeyen üçüncü bir
   değerlendiriciye gider. Bu, sistemdeki `consensus: adjudicator_or_mean` kuralına karşılık gelir.
6. **Kayıt:** Puanlar `data/human_scores.csv` dosyasına şu sütunlarla aktarılır:
   `response_id, rater_id, role, set, criterion_id, score`.
   - Rol değerleri: `rater1`, `rater2`, `adjudicator`, `official`.
   - Küme değerleri: `gold`, `official`.

## 7. Kodlama formu

| Yanıt kodu | Soru | C1 | C2 | Not (isteğe bağlı) |
|---|---|---|---|---|
| R00017 | S1 | 3 | 2 | |
| R00042 | S2 | 4 | 3 | |

`sample-gold` komutunun ürettiği `data/derived/gold_rating_sheet.xlsx` dosyası bu biçimdedir. Her soru ayrı bir
sayfadadır, rubrik de ayrı bir sayfadadır; puanlar açılır listeden seçilir.

## 8. Örnekleme notu

Altın set varsayılan olarak soru başına 300 yanıttır (`experiment.yaml > gold.per_item`). Katılımcı sayısı
bundan azsa o sorunun tüm yanıtları alınır. Öğrenilmiş ağırlıkların ve gömme koşulunun güvenilir olması için
soru başına **en az 150–200** altın set yanıtı önerilir.
