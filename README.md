# Katmanlı çok modelli puanlama çerçevesi

*Layered multi-LLM scoring framework* — açık uçlu (Moodle "Kompozisyon") sınav yanıtlarını birden çok büyük dil
modeliyle katmanlı bir yapıda puanlayan ve puanları insan uzman puanlarıyla karşılaştıran bir **araştırma aracı**.

Bu araçta tekrar üretilebilirlik, kayıt tutma ve veri gizliliği, hızdan ve görünüşten önce gelir.

> **Durum:** Etik kurul onayı gelene kadar yalnızca **sentetik veri** ile çalışılır. Depodaki sorular, rubrik,
> çapalar ve tüm `results/` çıktıları sentetiktir; mock (sahte) modellerle üretilmiştir ve **bilimsel bir bulgu değildir**.

## Kuramsal dayanak

Mimari, Wang ve ark.'nın (2025) *Mixture-of-Agents* yaklaşımından uyarlanmıştır: birden çok model önce bağımsız
yanıt üretir, sonraki katmanda birbirlerinin çıktılarını görerek yanıtlarını iyileştirir ve bir birleştirici son
çıktıyı oluşturur. Bağımsız ve farklı ailelerden modellerden oluşan bir **puanlama paneli** fikri ise Verga ve
ark.'na (2024, *Replacing Judges with Juries*) dayanır. Değerlendirme ölçütleri Williamson, Xi ve Breyer'in (2012)
otomatik puanlama çerçevesini izler.

```
            ┌──────────── Katman 1: bağımsız puanlama (3 model, farklı aileler, çapalı/çapasız) ──────────┐
 yanıt ───► │  Model 1 (GPT)        Model 2 (Claude)        Model 3 (Qwen, yerel, açık ağırlıklı)        │
            └──────┬───────────────────────┬─────────────────────────┬────────────────────────────────────┘
                   ▼                       ▼                         ▼
            ┌──────────── Katman 2: revizyon (her model diğerlerini anonim "Model A/B/C" olarak, rastgele sırada görür) ┐
            └──────┬───────────────────────┬─────────────────────────┬────────────────────────────────────┘
                   ▼                       ▼                         ▼
            ┌──────────── Katman 3: birleştirme (aynı çalıştırmada üçü birden) ───────────────────────────┐
            │ (a) birleştirici LLM   (b) ortalama / ortanca   (c) öğrenilmiş ağırlıklar (5 katlı CV, Σw=1) │
            └─────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Kurulum

```bash
# Python ≥ 3.11 ve uv gerekir (https://docs.astral.sh/uv/)
uv sync --extra spelling                 # temel + Türkçe yazım denetimi (spylls)
uv sync --extra spelling --extra embeddings   # + gömme koşulu (sentence-transformers, torch)
cp .env.example .env                     # API anahtarlarını doldurun
uv run scoring gen-key >> .env           # eşleme tablosu şifreleme anahtarı (MAPPING_KEY)
bash scripts/fetch_tr_dictionary.sh      # Türkçe Hunspell sözlüğü (yazım hatası sayımı için)
uv run pytest                            # birim testleri
```

**Hiçbir API anahtarı koda yazılmaz**; tümü `.env` dosyasından okunur. `.env` dosyası `.gitignore` kapsamındadır.

## Hızlı deneme (sentetik veri + mock modeller, anahtar gerekmez)

```bash
bash scripts/run_synthetic_demo.sh
```

Bu betik şu adımları sırayla çalıştırır: sentetik Moodle dışa aktarımı → anonimleştirme → (sentetik) resmî not →
altın set → (sentetik) iki kör puanlayıcı + hakem → sızıntı denetimi → 8 ablasyon koşulu → kararlılık →
değerlendirme → yanlılık verisi → R modeli.

## Yapılandırma (`config/`)

| Dosya | İçerik |
|---|---|
| `items.yaml` | Sorular, Bloom basamağı (alt/üst), analitik ölçütler, puan aralığı (varsayılan 0–4), her düzeyin tanımlayıcısı, çapa yanıtlar (her ölçütün her düzeyi için en az bir tane; kod denetler), referans yanıt |
| `models.yaml` | Model rolleri (`scorers`, `aggregator`), sağlayıcı, **tam sürüm kimliği**, parametreler, batch, eşzamanlılık, fiyat. En az bir model `open_weights: true` olmalıdır (kod denetler) |
| `models.mock.yaml` | Anahtarsız uçtan uca deneme için sahte panel |
| `moodle_columns.yaml` | Türkçe/İngilizce Moodle başlıkları için esnek sütun eşlemesi, soru sırası → `item_id` |
| `experiment.yaml` | Tohumlar, yollar, altın set boyutu, kat sayısı, yuvarlama kuralı, ağırlık düzeyi, gömme modelleri, bootstrap, eşikler |
| `pii_denylist.txt`, `tr_first_names.txt`, `pii_ambiguous_words.txt` | Metin içi maskeleme listeleri |
| `spelling_whitelist.txt` | Yazım denetiminde hata sayılmayacak alan terimleri |

İstem şablonları `prompts/` klasöründe ayrı Jinja2 dosyaları olarak tutulur ve sürüm kontrolündedir:
`layer1_score.j2`, `layer1_score_zeroshot.j2`, `layer2_revise.j2`, `layer3_aggregate.j2` ve ortak makrolar
`_common.j2`. Her şablonun SHA-256 özeti, `_common.j2` dahil edilerek hesaplanır ve her çağrıyla birlikte kaydedilir.

## Komutlar

```bash
uv run scoring --help
```

| Komut | Görev |
|---|---|
| `gen-key` | Eşleme tablosu için Fernet anahtarı üretir |
| `anonymize [--export dosya.xlsx]` | Moodle CSV/XLSX okur, kimlikleri koda çevirir, metin içi kişisel veriyi maskeler |
| `sample-gold [--per-item 300] [--synthetic]` | Katmanlı seçkisiz altın set, öğrenci düzeyinde 5 kat, puanlayıcı Excel'i, Label Studio JSON'u |
| `check-leakage` | Çapaların altın setten gelmediğini denetler (ihlalde çıkış kodu 1) |
| `estimate-cost --condition ablation` | İstemleri gerçekten oluşturup token ve maliyet tahmini yapar |
| `score --condition full --subset gold\|all [--replicate 2] [-y]` | LLM katmanlarını çalıştırır; önce maliyet tahmini gösterir ve onay ister |
| `run-ablation [-y] [--offline-embedding-demo]` | **Tek komutla** tüm ablasyon koşulları + gömme koşulu + değerlendirme |
| `embed-baseline` | Gömme tabanlı koşul |
| `build-conditions` | Ham puanlardan koşul puanlarını üretir (aynı katlar) |
| `evaluate [--bootstrap-reps N]` | Tüm metrikler, tablolar ve grafikler → `results/` |
| `export-bias-data` | R'daki karma model için düz veri dosyası |
| `final-scores` | Tam çerçeveyle operasyonel puanlar (altın set için kat dışı tahmin) |

Kararlılık ölçümü için altın set, aynı ayarlarla **farklı bir günde** ikinci kez puanlanır:
`uv run scoring score --condition stability --replicate 2`. Replikasyon numarası önbellek anahtarına dahildir;
bu sayede ikinci puanlama önbellekten gelmez, model gerçekten yeniden çağrılır.

## Veri gizliliği adımları

1. **Gerçek öğrenci verisi yok:** Etik kurul onayına kadar `scripts/make_synthetic.py` ile üretilen Türkçe sentetik
   yanıtlar kullanılır (4 soru × 50 yanıt; farklı kalite düzeyleri, yazım hataları, kasıtlı kişisel veri örnekleri).
2. **Allowlist okuyucu:** `moodle_io` yalnızca yanıt sütunlarını taşır. Kimlik sütunları (ad, soyad, e-posta,
   numara, kullanıcı adı) yalnızca kod üretmek ve maskeleme listesi kurmak için okunur. IP, kurum, süre gibi diğer
   sütunlar hiç taşınmaz.
3. **Rastgele kodlar:** Öğrenci kodları (`P` + 6 onaltılık karakter) ve yanıt kodları (`R00001`…) kriptografik
   rastgelelikle atanır. Yeniden çalıştırmada mevcut eşleme korunur. Kodlar tohumdan türetilmediği için (yeniden
   tanımlamayı önlemek amacıyla) eşleme dosyası silinip sıfırdan anonimleştirilirse yeni kodlar ve dolayısıyla
   farklı bir altın set oluşur. Bu nedenle anonimleştirme **bir kez** yapılmalı ve `mapping.enc` ile
   `gold_sample.csv` yedeklenmelidir.
4. **Şifreli eşleme:** Kod ↔ kimlik tablosu `data/private/mapping.enc` dosyasında Fernet (AES-128-CBC + HMAC-SHA256)
   ile şifrelidir; anahtar `.env` dosyasındaki `MAPPING_KEY`'dir. Hem dosya hem anahtar `.gitignore` içindedir.
5. **Metin içi maskeleme (regex + kontrol listesi):**
   - e-posta, telefon, 11 haneli TCKN, 6–12 haneli numaralar;
   - dışa aktarımdaki tüm öğrenci ad/soyadları (büyük/küçük harf duyarsız, Türkçe İ/ı uyumlu);
   - yaygın Türkçe adlar listesi (yalnızca büyük harfle başlıyorsa) ve ardından gelen büyük harfli soyad;
   - "Adım …", "Ben …" gibi tanıtım kalıpları;
   - yasaklı terimler listesi.
   Sıradan sözcük de olan adlar (Deniz, Umut, Kaya, Kara …) yalnızca büyük harfle başladığında maskelenir. Küçük
   harfli kullanımlar maskelenmez ama raporda "masked=False" olarak işaretlenir.
6. **Raporlama:** Maskelenen her değer konum ve kuralıyla birlikte gizli rapora (`data/private/pii_report.csv`)
   yazılır. Paylaşılabilir özet yalnızca sayımları içerir (`results/pii_summary.csv`).
7. **Son denetim:** Maskeleme sonrası bilinen e-posta, numara ya da tam adlardan biri metinde kalırsa çıktı **yazılmaz**.
8. **API'ye giden tek metin** `data/processed/responses.csv` içindeki anonim, maskelenmiş yanıttır. İstemlerde ve
   kayıtlarda yalnızca yanıt kodu bulunur.
9. `logs/` (tam istem metinleri) ve `data/derived/` (model gerekçeleri öğrenci metninden alıntı içerir) sürüm kontrolü
   dışındadır. `results/bias/` da gerçek veriyle çalışırken itilmemesi için dışlanmıştır.

> Öneri: Gerçek veriyle ilk çalıştırmadan sonra `data/private/pii_report.csv` dosyasını elle gözden geçirin ve
> bulunan ek adları `config/pii_denylist.txt` dosyasına ekleyin. Kural tabanlı maskeleme her adı yakalayamaz.

## Altın set ve sızıntı denetimi

- `sample-gold`, her sorudan 300 yanıtı (yapılandırılabilir) resmî toplam puana göre eşit frekanslı katmanlara
  **orantılı** (büyük kalan yöntemiyle) seçkisiz seçer. Tohum `experiment.yaml` dosyasında sabittir ve
  `gold_sample.csv` dosyasına yazılır.
- Puanlayıcı Excel'i anonimdir ve her soru sayfasında rastgele sıralıdır. Açılır listelerle puan girilir, rubrik
  ayrı sayfadadır; **resmî not dosyada yoktur**. İsteğe bağlı olarak Label Studio içe aktarma JSON'u ve etiketleme
  arayüzü XML'i de yazılır.
- **Sızıntı denetimi:** Çapalar altın setten asla gelemez. `check-leakage` üç düzeyde denetler: kaynak yanıt
  kimliği, normalleştirilmiş metin özeti (SHA-256; büyük/küçük harf, Türkçe karakter ve noktalama farklarına
  duyarsız) ve yakın kopya (Jaccard ≥ .90). Denetim `score`, `run-ablation` ve `embed-baseline` öncesinde otomatik
  çalışır; ihlalde `LeakageError` ile durur. Çapa kaynağı yanıtlar altın set havuzundan baştan dışlanır.
- **Uzlaşı puanı:** İki puanlayıcı aynı puanı verdiyse o puan alınır; farklıysa hakemin puanı; hakem puanı yoksa
  ortalama, yapılandırılan kurala göre yuvarlanır.

## Koşullar ve ablasyon

Tüm koşullar **aynı altın sette ve aynı katlarla** (`data/derived/gold_folds.csv`, öğrenci düzeyinde) üretilir.
LLM çağrıları koşullar arasında paylaşılır; koşullar yalnızca birleştirme biçiminde ayrışır.

| # | Koşul | Tanım |
|---|---|---|
| 1 | `single_zeroshot:<model>` | Tek model, çapasız |
| 2 | `single_anchored:<model>` | Tek model, çapalı |
| 3 | `panel_vote` | Katman 1 + ortalama, revizyon yok (Verga ve ark. tarzı) |
| 4 | `full_zeroshot` | Tam çerçeve, çapasız (K1+K2 çapasız + öğrenilmiş ağırlık) |
| 5 | `full_no_revision` | Tam çerçeve, revizyon katmanı yok (K1 + öğrenilmiş ağırlık) |
| 6 | `full_equal_weight` | Tam çerçeve, eşit ağırlık (K2 ortalaması) |
| 7 | `full` | Tam çerçeve (tüm katmanlar, öğrenilmiş ağırlık) |
| 3b | `full_median` | K2 ortancası |
| 3a | `full_llm_aggregator` | Birleştirici LLM |
| 8 | `embedding` | Gömme tabanlı puanlama (üretken model yok) |

**Öğrenilmiş ağırlıklar:** Ağırlıklar şu problemin çözümüdür: min ‖Xw − y‖², kısıtlar w ≥ 0 ve Σw = 1 (SLSQP).
Varsayılan olarak her soru için ayrı ağırlık öğrenilir (`weights_level: item | item_criterion | global`).
Ağırlıklar yalnızca eğitim katlarında öğrenilir ve yalnızca dışarıda tutulan katta değerlendirilir. Katlara göre
değişimleri `results/weights_variability.md` ve `weights_by_fold.csv` dosyalarında raporlanır.

**Gömme koşulu:** `intfloat/multilingual-e5-large` ve `-base` (`query: `/`passage: ` önekleriyle),
`paraphrase-multilingual-mpnet-base-v2`, `distiluse-base-multilingual-cased-v1` ve `BAAI/bge-m3` kullanılır.
Her model ve ölçüt için iki öznitelik çıkarılır: referans yanıta kosinüs benzerliği ve benzerlik-softmax ağırlıklı
çapa puanı. Öznitelikler model içinde z'ye dönüştürülür (ortalama ve SS eğitim katından alınır). Ardından L2
düzenlileştirmeli sıralı lojistik regresyonla (kümülatif logit) rubrik puanına çevrilir. Yalnızca İngilizce
modeller ve ince ayarsız ham BERT yapılandırmada yasaktır; kod bu yasağı denetler.

## Kayıt ve tekrar üretilebilirlik

- **Çağrı kaydı** (`logs/<run_id>/calls.jsonl`, her çağrı için bir satır): zaman damgası, koşul, katman, varyant,
  istenen model ve **sağlayıcının döndürdüğü sürüm adı**, sağlayıcı, etkin parametreler (gönderilmeyenler
  "unsupported" olarak işaretlenir), şablon adı ve SHA-256 özeti, istem özeti ve **tam metni**, ham yanıt,
  ayrıştırılmış çıktı, doğrulama hatası, deneme numarası, token sayıları, gecikme, tahmini maliyet, hata, önbellek
  bilgisi ve Katman 2/3'te anonim etiketlerin hangi modele karşılık geldiği.
- **Kaydı olmayan sonuç raporlanmaz:** Her koşul puanı, dayandığı çağrı kimliklerini taşır. `evaluate`, kimliği
  hiçbir kayıtta bulunmayan puanları çıkarır ve `results/excluded_unlogged.csv` dosyasına yazar.
- **Önbellek** (`logs/cache.sqlite`): Anahtar; sağlayıcı, model, istemler, etkin parametreler ve replikasyondan
  oluşur. Aynı anahtar için model yeniden çağrılmaz. Yarıda kesilen bir çalıştırma yeniden başlatıldığında kaldığı
  yerden devam eder.
- **Doğrulama:** Çıktı pydantic şemasıyla doğrulanır. Kimlik, ölçüt kümesi, tamsayı puan ve aralık denetlenir;
  aralık dışı puan reddedilir. Geçersiz çıktıda hata mesajıyla en fazla 2 yeniden deneme yapılır, sonra hata
  kaydedilir. LLM'in bildirdiği toplam ile ölçüt toplamı uyuşmazsa bu not edilir; toplam her zaman ölçüt
  puanlarının toplamıdır.
- **Batch ve hız sınırı:** OpenAI Batch API ve Anthropic Message Batches API desteklenir (`batch: true`).
  Diğerlerinde model başına eşzamanlılık sınırı ve üstel geri çekilme (tenacity, jitter) kullanılır.
- **`run_manifest.json`:** Her çalıştırmanın başında `logs/<run_id>/` ve `results/manifests/` altına yazılır. İçinde
  git commit'i ve kirli dosyalar, tüm yapılandırma ve istem dosyalarının SHA-256 özetleri, tohumlar, paket
  sürümleri, Python/platform bilgisi, komut satırı ve model yapılandırması bulunur.
- **Maliyet:** `score` çalıştırmadan önce istemleri gerçekten oluşturarak maliyet tahmini yazdırır ve onay ister
  (`-y` ile atlanır). Katman 1 için önbellekteki çağrılar tahminden düşülür.

## Değerlendirme (`evaluate` → `results/`)

Her koşul için hem toplam puan hem her ölçüt ayrı ayrı, hem her soru ayrı hem tümü birlikte raporlanır:

- İkinci dereceden ağırlıklı kappa (QWK), ICC(2,1), ICC(3,1), tam uyum %, ±1 bitişik uyum %, MAE ve standartlaştırılmış
  ortalama farkı (SMD = (ort_m − ort_h) / √((s²_m + s²_h)/2)). Hepsi için **öğrenci düzeyinde kümelenmiş** 2.000
  tekrarlı bootstrap ile %95 GA verilir. Bootstrap vektörleştirilmiştir: her tekrar bir satır-ağırlık vektörüdür
  ve satır çoğaltmayla birebir aynı sonucu verir (test edilmiştir).
- İnsan–insan uyumu (altın setteki iki puanlayıcı) aynı ölçütlerle hesaplanır; her koşulun insan–insan QWK'sinden
  düşüşü raporlanır.
- **Williamson, Xi ve Breyer (2012) geçti/kaldı tablosu:** QWK ≥ .70, insan–insan QWK'sinden düşüş ≤ .10 ve
  |SMD| ≤ .15 (`wxb_pass_fail*.md`).
- **Eşleştirilmiş bootstrap:** Koşullar arası QWK farkı için %95 GA ve iki yönlü bootstrap p değeri hesaplanır;
  karşılaştırmalar `experiment.yaml > paired_comparisons` altında tanımlanır.
- Bland–Altman grafikleri (`results/figures/*.png|svg`), kapsam (coverage) tablosu ve kararlılık tablosu
  (replikasyonlar arası QWK, tam uyum, ICC(3,1) ve çalıştırma tarihleri; "farklı günler" denetimi).

| Dosya | İçerik |
|---|---|
| `summary_total_pooled.md` | Ana tablo: toplam puan, tüm sorular |
| `qwk_total_by_item.md`, `qwk_by_criterion.md` | Soru ve ölçüt bazında QWK |
| `agreement_long.csv` | Tüm koşul × kapsam × metrik × GA (uzun biçim) |
| `human_human_long.md` | İnsan–insan uyumu |
| `wxb_pass_fail.md`, `wxb_pass_fail_total.md` | Williamson ve ark. (2012) ölçütleri |
| `paired_differences.md` | Eşleştirilmiş koşul farkları |
| `weights_variability.md`, `weights_by_fold.csv` | Öğrenilmiş ağırlıklar ve katlara göre değişim |
| `stability.md` | Model içi tutarlılık |
| `coverage.md`, `excluded_unlogged.csv` | Kapsam ve kayıt denetimi |

## Yanlılık analizi

`export-bias-data` iki düz dosya yazar: `results/bias/bias_data_total.csv` (yanıt başına bir satır) ve
`bias_data_criterion.csv`. Sütunlar: yanıt kodu, öğrenci kodu, soru, Bloom basamağı, iki puanlayıcı, insan uzlaşı
puanı, her koşulun puanı, kelime sayısı, yazım hatası sayısı ve oranı, MTLD, MATTR, TTR.

**Yazım hatası sayımı yöntemi:** Türkçe Hunspell sözlüğü (wooorm/dictionaries `tr`, MIT; Harun Reşit Zafer'in
hunspell-tr çalışmasına dayanır) saf-Python `spylls` ile kullanılır. Türkçenin eklemeli yapısı nedeniyle düz
sözcük listesi yerine Hunspell'in ek kuralları uygulanır. Yalnızca harflerden oluşan ve en az 3 karakterli
sözcükler denetlenir. Anonimleştirme maskeleri, sayılar ve `config/spelling_whitelist.txt` içindeki alan terimleri
(overfitting, dropout, precision@k …) hariç tutulur. Bir sözcük özgün, Türkçe küçük harfli ya da şapkasız
biçimlerinden hiçbiriyle sözlükte bulunmazsa hata sayılır. Sözlük yoksa değer NA olur ve yöntem "unavailable"
olarak kaydedilir.

**Sözcük çeşitliliği:** MTLD (McCarthy ve Jarvis, 2010; eşik .72, iki yönlü) yaklaşık 100 sözcüğün altında
kararsızdır. Kısa yanıtlar için MATTR (Covington ve McFall, 2010; pencere 25) önerilir.

`scripts/bias_model.R` örnek modelleri kurar (`lme4`/`lmerTest`, `ordinal`):
1. Fark puanı (makine − insan) için doğrusal karma model: uzunluk, yazım ve çeşitlilik (z) + soru (sabit) + öğrenci
   (rastgele). Bloom etkisi, soru ile eşdoğrusal olduğundan ayrı bir modelde özelliklerle etkileşim olarak sınanır.
2. Makine ölçüt puanı için sıralı karma model (`clmm`): insan puanı + özellikler + soru (sabit) + öğrenci (rastgele).

## Testler

```bash
uv run pytest
```

Kapsanan konular: anonimleştirme (ad, numara, e-posta ve telefon sızmıyor; eşleme şifreli ve kararlı; belirsiz
adlar), Moodle okuyucu (İngilizce başlıklar, durum filtresi, HTML), JSON doğrulama (aralık dışı, ondalıklı ve eksik
ölçüt reddi), sızıntı denetimi, çağrı motoru (önbellek, doğrulama yeniden denemesi, geri çekilme, kayıt alanları),
Anthropic'e sıcaklık gönderilmemesi, QWK'nin `sklearn` ile tutarlılığı, ICC'nin Shrout ve Fleiss (1979) değerleri,
bootstrap eşdeğerliği, ağırlıkların negatif olmaması ve toplamının 1 olması, kat dışı öğrenme, sıralı lojistik ve
yasaklı gömme modelleri.

## Klasör yapısı

```
config/      yapılandırma (rubrik, modeller, Moodle sütunları, deney)
prompts/     Jinja2 istem şablonları (sürüm kontrolünde)
src/scoring/ moodle_io, anonymize, sampling, leakage, providers/, engine, layers, pipeline,
             aggregation, embedding_baseline, ablation, metrics, evaluate, text_features, manifest, cli
scripts/     sentetik veri, insan puanı simülasyonu, demo betiği, sözlük indirme, bias_model.R
tests/       pytest
data/        (gitignore) ham/anonim veri, eşleme, türetilmiş dosyalar
logs/        (gitignore) çağrı kayıtları, önbellek, manifestler
results/     tablolar (CSV + Markdown), grafikler, manifest kopyaları
```

## Sınırlılıklar

- **Determinizm:** Anthropic'in güncel API sürümü `temperature` parametresini kabul etmez. Bu sağlayıcıda sıcaklık
  gönderilmez, düşük `effort` kullanılır ve kayıtta "unsupported" olarak işaretlenir. OpenAI ve Gemini'de sıcaklık
  0 ve `seed` kullanılır, ancak bu sağlayıcılar da tam determinizm garanti etmez. Bu nedenle kararlılık ayrıca
  ölçülür ve önbellek, aynı çağrının yeniden üretilmesine değil yeniden *kullanılmasına* dayanır.
- **Model sürümleri:** `models.yaml` içindeki kimlikler örnektir. Gerçek çalışmadan önce tarihli sürüm kimlikleriyle
  güncellenmelidir. Sağlayıcının döndürdüğü sürüm adı her çağrıda ayrıca kaydedilir.
- **Doğrulanmamış canlı yollar:** Geliştirme ortamında API anahtarı olmadığından OpenAI, Anthropic ve Gemini
  istemcileri ile batch yolları canlı olarak çalıştırılmadı. İstek gövdeleri birim testleriyle, boru hattı ise mock
  sağlayıcıyla sınandı. Gemini için batch modu uygulanmadı; eşzamanlı çağrı kullanılır. İlk gerçek çalıştırmadan
  önce `--limit 2` ile küçük bir deneme yapılmalıdır.
- **Gömme modelleri:** Geliştirme ortamında HuggingFace erişimi olmadığından gerçek gömme modelleri uçtan uca
  çalıştırılamadı. Örnek sonuçlardaki `embedding_tfidf_demo`, yalnızca boru hattını sınayan bir karakter n-gram
  TF-IDF kodlayıcısıdır. Sentetik metinler sınırlı bir cümle bankasından kurulduğu için bu demo yapay olarak
  yüksek uyum gösterir ve yorumlanmamalıdır.
- **Mock modeller** gerçek dil modeli değildir. `results/` altındaki sayılar yalnızca çıktı biçimini gösterir.
- **Kural tabanlı maskeleme** listede olmayan, küçük harfle yazılmış ya da yazım hatalı adları kaçırabilir. Gizli
  raporun elle gözden geçirilmesi önerilir.
- **Katman 2 uyum (conformity) riski:** Modeller, kimlikler gizlense de çoğunluğa yaklaşabilir. İstem bunu açıkça
  yasaklar; revizyonun etkisi `full` − `full_no_revision` karşılaştırmasıyla ölçülür.
- **Öğrenilmiş ağırlıklar** yalnızca kısıtlı en küçük kareler ile uygulanmıştır (sıralı regresyon seçeneği yoktur).
  Soru başına 300 yanıtla bile katlara göre ağırlık değişkenliği raporlanmalıdır.
- **Yanlılık analizi:** Altın sette sorular bağımsız örneklendiğinden çoğu öğrencinin tek yanıtı olabilir; öğrenci
  rastgele etkisi bu durumda zayıf tahmin edilir.
- **Toplam puan QWK'si (tüm sorular):** Soruların toplam aralıkları aynıysa (burada 0–12) anlamlıdır. Farklı
  aralıklarda soru bazındaki sonuçlar esas alınmalıdır.
- **Yazım denetimi**, sözlükte olmayan özel adları ve yeni terimleri hata sayabilir. Beyaz liste veriyle birlikte
  güncellenmelidir.

## Kaynaklar

- Covington, M. A., & McFall, J. D. (2010). Cutting the Gordian knot: The moving-average type–token ratio (MATTR).
  *Journal of Quantitative Linguistics, 17*(2), 94–100.
- McCarthy, P. M., & Jarvis, S. (2010). MTLD, vocd-D, and HD-D: A validation study of sophisticated approaches to
  lexical diversity assessment. *Behavior Research Methods, 42*(2), 381–392.
- Shrout, P. E., & Fleiss, J. L. (1979). Intraclass correlations: Uses in assessing rater reliability.
  *Psychological Bulletin, 86*(2), 420–428.
- Verga, P., Hofstätter, S., Althammer, S., Su, Y., Piktus, A., Arkhangorodsky, A., Xu, M., White, N., & Lewis, P.
  (2024). *Replacing judges with juries: Evaluating LLM generations with a panel of diverse models*. arXiv:2404.18796.
- Wang, J., Wang, J., Athiwaratkun, B., Zhang, C., & Zou, J. (2025). Mixture-of-Agents enhances large language model
  capabilities. *International Conference on Learning Representations (ICLR 2025)*. arXiv:2406.04692.
- Williamson, D. M., Xi, X., & Breyer, F. J. (2012). A framework for evaluation and use of automated scoring.
  *Educational Measurement: Issues and Practice, 31*(1), 2–13.
