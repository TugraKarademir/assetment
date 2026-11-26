# Gerçek veriyle adım adım

Bu kılavuz, öğrenci yanıtları elinize geçtikten sonra yapılacak işleri sırasıyla anlatır. Komutlar proje
klasöründe (`puanlama/`) çalıştırılır.

## Arayüzle (komut satırı olmadan)

Aşağıdaki adımların hepsi arayüzün **Gerçek veri** sekmesinden de yapılabilir:

```bash
uv run scoring ui --open          # Windows: ARAYUZU_AC_Windows.bat
```

Sekmedeki bölümler sırasıyla:
1. Dosya yükleme.
2. İnceleme, soru eşleme ve onamlı anonimleştirme.
3. Gizli işaret taraması.
4. Altın set, puanlayıcı ve kalibrasyon Excel'lerini indirme.
5. Doldurulmuş Excel'leri yükleme, puanlayıcı uyumu ve hakem dosyası.
6. Modellerle puanlama ve değerlendirme. İş arka planda çalışır; tarayıcı kapansa da sürer.

Üstteki durum çubuğu hangi adımların bittiğini gösterir. Sonuçlar **Sonuçlar** sekmesinde görünür. İlk gerçek
çalıştırmada depoyla gelen örnek (sentetik) sonuçlar `results/` klasöründen silinir.

## 0. Başlamadan önce

| Koşul | Neden |
|---|---|
| **Etik kurul onayı alındı.** | Yanıtları araştırma amacıyla işlemek (anonimleştirme, puanlama, analiz) ancak onaydan sonra yapılabilir. |
| **Onam verenlerin listesi elinizde.** | Yalnızca onam verenlerin yanıtları işlenir. Program onam listesi olmadan gerçek veriyi işlemez. |
| **İşlemleri kurum bilgisayarında ya da sunucusunda yapıyorsunuz.** | Etik başvurusunda "veri kurum dışına çıkmaz" diye taahhüt edildi. Ham dosyayı, yanıtları ya da kişisel veri içeren çıktıları e-postayla, bulut depolamayla ya da yapay zekâ sohbetleriyle (ChatGPT, Claude vb.) **paylaşmayın.** |

Yardım isterken yalnızca kişisel veri içermeyen çıktıları paylaşın. Bunlar:
- `results/` altındaki özet tablolar;
- komutların ekrana yazdığı sayımlar;
- hata mesajları.

## 1. Dosyaları yerleştirin

```
data/raw/moodle_export.xlsx      ← Moodle > Sınav > Sonuçlar > Yanıtlar raporu (Excel ya da CSV)
data/private/onam.csv            ← onam verenler (aşağıya bakın)
```

- **Onam dosyası** CSV ya da Excel olabilir. İçinde öğrencinin e-postası, numarası ya da kullanıcı adı sütunu
  bulunmalı; tek sütunlu bir liste de olur.
- Dosyada "Onam" adlı bir sütun varsa yalnızca "Evet", "Kabul ediyorum" ya da "Onaylıyorum" yazan satırlar onay
  sayılır.
- Onamları Moodle'da bir **Anket/Seçim** etkinliğiyle topladıysanız, o etkinliğin dışa aktarımını doğrudan
  kullanabilirsiniz.
- `data/` klasörü GitHub'a gitmez.

## 2. Dosyanın yapısını inceleyin

```bash
uv run scoring inspect-export data/raw/moodle_export.xlsx
```

Komut sütunları, her yanıt sütunundaki dolu yanıt sayısını ve soru metinlerinin başını gösterir. Öğrenci yanıtlarını
ve kimlik bilgilerini **ekrana yazdırmaz**. Açık uçlu soruların Moodle'daki sıra numaralarını buradan bulun.
Örneğin sınavda önce 4 çoktan seçmeli soru varsa açık uçlular 5 ve 6 olur.

## 3. Anonimleştirin (yalnızca onam verenler)

```bash
uv run scoring anonymize --export data/raw/moodle_export.xlsx --consent data/private/onam.csv --item-map "5=S1,6=S2"
```

Komut şunları yapar:
- Onam vermeyenleri hiç okumaz ve kaç kişinin alınmadığını raporlar.
- Ad, numara ve e-posta gibi bilgileri siler, her öğrenciye rastgele bir kod verir.
- Yanıt metinlerinde geçen kişisel bilgileri maskeler.
- Kod–kimlik eşlemesini şifreli olarak `data/private/mapping.enc` dosyasına yazar.

Ardından:
- **Maskeleme raporunu elle kontrol edin:** `data/private/pii_report.csv`. Gözden kaçan bir ad görürseniz
  `config/pii_denylist.txt` dosyasına ekleyip komutu yeniden çalıştırın.
- **Yedek alın.** `data/private/mapping.enc` dosyasını ve `.env` içindeki `MAPPING_KEY` anahtarını, kurum içinde
  şifreli bir ortama yedekleyin. Anahtar kaybolursa eşleme açılamaz. Anonimleştirmeyi baştan yaparsanız yanıt
  kodları değişir.

## 4. Gizli işaret taraması (kullandıysanız)

`config/canary.local.yaml` dosyasına Moodle'da kullandığınız uydurma kavram adlarını yazın, sonra:

```bash
uv run scoring check-canary
```

- Soru başına sayımlar `results/canary_summary.csv` dosyasına yazılır.
- İşaretli yanıt kodları `data/derived/canary_flags.csv` dosyasına yazılır; bu dosya gizlidir.
- Etik başvurusundaki taahhüde göre bu bilgi **yalnızca araştırma analizinde** kullanılır.

## 5. Altın seti seçin

```bash
uv run scoring sample-gold
```

- Soru başına 300 yanıt seçilir; daha az yanıt varsa hepsi alınır. Sayıyı değiştirmek için `--per-item 200`.
- Resmî not yoksa katmanlar yanıt uzunluğuna göre oluşturulur.
- Puanlayıcı dosyası: `data/derived/gold_rating_sheet.xlsx`. Dosyada soru başına ayrı bir sayfa ve rubrik
  sayfası vardır; puanlar açılır listeden seçilir.

## 6. Puanlayıcı kalibrasyonu

```bash
uv run scoring calibration-sheet --round 1          # altın sete girmeyen 2 × 10 yanıt
```

1. Dosyanın birer kopyasını iki puanlayıcıya verin. Doldurulunca dosyaları içe aktarın ve uyuma bakın:

   ```bash
   uv run scoring import-ratings --file data/private/kal1_H1.xlsx --rater-id H1 --role rater1 --set calibration1
   uv run scoring import-ratings --file data/private/kal1_H2.xlsx --rater-id H2 --role rater2 --set calibration1
   uv run scoring rater-agreement --set calibration1
   ```

2. Hedef, her ölçütte **tam uyum ≥ %70** ve **QWK ≥ .80**. Ulaşılamazsa farklılıkları tartışın, gerekirse
   kılavuza açıklayıcı not ekleyin ve 2. turu yapın: `--round 2`.

Puanlayıcı kodu olarak ad yazmayın; H1, H2, H3 gibi kodlar kullanın.

## 7. Altın setin kör puanlanması ve hakem

1. İki puanlayıcı aynı dosyayı birbirinden bağımsız doldurur. Ardından dosyaları içe aktarıp uyuma bakın:

   ```bash
   uv run scoring import-ratings --file data/private/gold_H1.xlsx --rater-id H1 --role rater1
   uv run scoring import-ratings --file data/private/gold_H2.xlsx --rater-id H2 --role rater2
   uv run scoring rater-agreement
   ```

2. Hakem dosyasını oluşturun. Dosya yalnızca ayrışan ölçütleri içerir ve puanlayıcıların puanlarını göstermez:

   ```bash
   uv run scoring adjudication-sheet
   ```

3. Hakem doldurunca içe aktarın:

   ```bash
   uv run scoring import-ratings --file data/private/hakem_H3.xlsx --rater-id H3 --role adjudicator
   ```

Programın raporladığı geçersiz puanları (ör. 7 ya da "iyi") ve eksik puanları düzeltip dosyayı yeniden içe
aktarın. Yeniden içe aktarma, aynı puanlayıcının eski puanlarının yerine geçer.

## 8. Modellerle puanlama (64 çekirdekli sunucu)

```bash
bash scripts/cpu64/benchmark.sh              # önce süre tahmini
LIMIT=5 bash scripts/cpu64/run_study.sh      # kısa pilot
bash scripts/cpu64/run_study.sh              # tam çalışma (kesilirse aynı komut kaldığı yerden devam eder)
```

`run_study.sh` şunları sırayla yapar:
1. Altın sette tüm ablasyon koşulları.
2. Diğer yanıtlarda tam çerçeve.
3. Gömme koşulu.
4. Değerlendirme.
5. Yanlılık verisi.
6. Nihai puanlar.

Kararlılık ölçümü **farklı bir günde** yapılır: `bash scripts/cpu64/run_stability.sh`.

## 9. Sonuçlar

| Dosya | İçerik |
|---|---|
| `results/summary_total_pooled.md` | Ana tablo: her koşulun insan puanlarıyla uyumu ve %95 GA |
| `results/wxb_pass_fail_total.md` | Williamson ve ark. (2012) ölçütlerine göre geçti/kaldı |
| `results/paired_differences.md` | Koşullar arası farklar |
| `results/stability.md`, `results/rationale_quality.md` | Kararlılık ve gerekçe kalitesi |
| `results/bias/` | R yanlılık analizi verisi; `Rscript scripts/bias_model.R` |

`results/` dosyaları kişisel veri içermez. Yine de gerçek veriyle çalışırken `results/bias/` klasörünü
herkese açık bir depoya göndermeyin.

## 10. Bitirirken

- Analizler tamamlanınca, onam formunda belirtilen tarihte, kod–kimlik eşleme anahtarını (`MAPPING_KEY`) ve
  `data/private/mapping.enc` dosyasını **yok edin**. Bundan sonra veriler kişilerle ilişkilendirilemez.
- Araştırma sonrası bilgilendirme metnini öğrencilere gönderin.
- Onam formunda belirtilen saklama süresi (önerilen 5 yıl) dolunca anonim verileri imha edin.
