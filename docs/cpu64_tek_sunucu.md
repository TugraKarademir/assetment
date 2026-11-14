# Tek sanal sunucu (64 çekirdek, yalnızca CPU) — kurulum ve çalıştırma

Bu kılavuz varsayılan düzen içindir (`config/models.yaml`). Tüm modeller ve puanlama aynı sanal sunucuda çalışır.
Model sunucuları yalnızca `127.0.0.1`'e bağlanır: öğrenci yanıtları makineden dışarı çıkmaz.

## 1. Düzen

| Aşama | Ne çalışır | Çekirdek paylaşımı (fiziksel) | Port |
|---|---|---|---|
| A — Katman 1 ve 2 | Qwen2.5-14B, Gemma-3-12B, Llama-3.1-8B **aynı anda** (üç ayrı `llama-server`) | %40 / %35 / %25 | 8001 / 8002 / 8003 |
| B — Katman 3 | Aya-Expanse-8B (birleştirici) **tek başına** | %100 | 8004 |

**Neden bu düzen?** CPU'da metin üretimi bellek bant genişliğiyle sınırlıdır. Üç modeli aynı anda çalıştırmak
toplam verimi bozmaz ve bir katmanın üç modelini birlikte bitirir. Birleştirici yalnızca Katman 2 bittikten sonra
gerekir; o aşamada bütün makine ona verilir. `scripts/cpu64/run_study.sh` iki aşamayı sırayla yürütür ve aşamalar
arasında sunucuları kendisi açıp kapatır.

**Çekirdekler:** 64 vCPU'lu bir sanal makinede bunlar çoğu zaman 32 fiziksel çekirdek × 2 iş parçacığıdır.
Betikler fiziksel çekirdek sayısını `lscpu` ile bulur. Sanal makine bunu yanlış bildirirse elle verin:
`PHYS_CORES=32`. Tek tek değerler de verilebilir: `QWEN_THREADS`, `GEMMA_THREADS`, `LLAMA_THREADS`, `AYA_THREADS`.

**Kısıtlı JSON çıktısı:** Her istemle birlikte rubrikten üretilen bir JSON şeması gönderilir
(`params.json_schema: true`). llama.cpp, çıktıyı bu şemaya uyacak biçimde sınırlar: ölçüt kimlikleri sabittir ve
puanlar o ölçütün aralığında bir tamsayıdır. Küçük modellerde sık görülen bozuk JSON ve yeniden deneme sorunu bu
sayede ortadan kalkar. Bu konteynerde en küçük modelle yapılan denemede geçersiz çıktı oranı 12'de 9'dan 12'de
0'a indi. Şemanın özeti her çağrı kaydına (`json_schema_sha256`) yazılır.

## 2. Gereksinimler

| Kaynak | Öneri |
|---|---|
| RAM | Aşama A için **≥ 48 GB** (üç model ~21 GB + paralel yuvaların bağlam belleği); Aşama B için ≥ 16 GB |
| Disk | Modeller için ~27 GB + gömme modelleri için ~10 GB + günlükler |
| İşletim sistemi | Linux önerilir (betikler bash). Windows için §6 |
| Yazılım | `uv` (Python), llama.cpp `llama-server`, `curl`; isteğe bağlı R (yanlılık modeli), `tmux` |

RAM yetmezse paralel yuvaları azaltın: `QWEN_PAR=2 GEMMA_PAR=2 LLAMA_PAR=1`. Bu durumda `config/models.yaml`
içindeki `max_concurrency` değerlerini de aynı sayılara indirin. Bu da yetmezse §5'e bakın.

## 3. Kurulum (bir kez)

Projeyi sunucuya kopyalayıp açın (zip), sonra tek komut:

```bash
cd puanlama
bash scripts/cpu64/setup_server.sh /veri/modeller     # model klasörü; verilmezse ./modeller
```

Betik sırasıyla şunları yapar ve yeniden çalıştırılabilir (biten adımlar atlanır):

1. Gerekli sistem araçlarını denetler (`curl`, `git`, `cmake`, `g++`). Eksikse kurulum komutunu yazıp durur; kök
   yetkisi yalnızca o komut için gerekir.
2. Donanımı raporlar: vCPU, fiziksel çekirdek, RAM, boş disk, AVX2.
3. `uv` ile Python ortamını kurar.
4. `.env` dosyasını oluşturur: eşleme şifreleme anahtarı, rastgele yerel API anahtarı, model klasörü.
5. llama.cpp'yi kaynaktan, bu işlemciye özel derler (`vendor/llama.cpp`) ve commit'ini kaydeder.
6. Dört modeli indirir (~27 GB) ve SHA-256 ile doğrular.
7. Türkçe yazım sözlüğünü indirir.

Sonunda RAM'e göre hangi betiğin kullanılacağını yazar: 48 GB ve üzeri için `run_study.sh`, daha azı için
`run_lowram.sh`. Sunucunun internet erişimi gerekir: github.com, huggingface.co, pypi.org, astral.sh. Erişim
kısıtlıysa modelleri başka bir makinede indirip klasöre kopyalayın; betik var olan dosyaları yalnızca doğrular.

cpu64 betikleri ayarları (`MODELS_DIR`, `LLAMA_SERVER`, `LOCAL_API_KEY`) proje kökündeki `.env` dosyasından okur;
kabukta tanımlı değerler önceliklidir.

## 4. Çalıştırma

```bash
# a) Hız ölçümü ve süre tahmini (≈ 30–60 dk): results/benchmark/
bash scripts/cpu64/benchmark.sh

# b) Pilot: soru başına 5 yanıtla tüm akış
LIMIT=5 bash scripts/cpu64/run_study.sh

# c) Tam çalışma (günler sürebilir; kesilirse aynı komutu yeniden verin, kaldığı yerden devam eder)
tmux new -s puanlama 'bash scripts/cpu64/run_study.sh 2>&1 | tee -a logs/run_study.log'
#    Süreyi ~%23 kısaltmak için (koşul 4 "full_zeroshot" üretilmez):
#    CONDITION=ablation_core bash scripts/cpu64/run_study.sh

# d) Kararlılık: FARKLI BİR GÜNDE
bash scripts/cpu64/run_stability.sh
```

`run_study.sh` sırasıyla şunları yapar:
1. Puanlayıcıları başlatır ve `check-models` ile doğrular (bağlantı, JSON, bağlam kesilmesi).
2. Altın sette Katman 1 ve 2'yi çalıştırır, ardından altın set dışındaki yanıtlarda Katman 1 ve 2'yi.
3. Puanlayıcıları kapatıp birleştiriciyi açar ve Katman 3'ü çalıştırır.
4. Gömme koşulunu, koşul puanlarını, değerlendirmeyi, yanlılık verisini ve nihai puanları üretir.

Betik nasıl biterse bitsin (hata ya da Ctrl+C dahil) model sunucularını kapatır.

**Kesinti güvenliği:** Her model çağrısı biter bitmez önbelleğe ve `logs/<run_id>/calls.jsonl` kaydına yazılır.
Elektrik kesintisi, yeniden başlatma ya da Ctrl+C sonrasında aynı komut, tamamlanan çağrıları yeniden yapmadan
devam eder.

## 5. RAM 48 GB'tan azsa

Puanlayıcıları **tek tek**, her birine tüm çekirdekleri vererek çalıştırın:

```bash
bash scripts/cpu64/run_lowram.sh            # pilot: LIMIT=5 bash scripts/cpu64/run_lowram.sh
```

Betik önce üç modelin Katman 1'ini, sonra Katman 2'sini, en son birleştiriciyi çalıştırır. Diğer modellerin daha
önce üretilmiş puanları önbellekten okunur. Aynı anda yalnızca bir model bellektedir (~10–16 GB). Modeller
ardışık çalıştığından bu yol daha yavaştır; `benchmark` sonucuna göre karar verin.

## 6. Windows sanal sunucu

Aynı düzen Windows'ta da kurulabilir:

- llama.cpp'nin Windows CPU sürümünü (`bin-win-cpu-x64.zip`) kullanın.
- Modelleri `scripts\download_cpu_models.ps1` ile indirin.
- Üç `llama-server.exe` sürecini `docs/cpu_sunucu_kurulumu.md` §2'deki komutlarla elle başlatın: aynı portlar,
  `--host 127.0.0.1`, iş parçacıkları %40/%35/%25.
- Ardından `uv run scoring ...` komutlarını `run_study.sh` içindeki sırayla çalıştırın.

## 7. Raporlama için

- Her çağrının kaydında model adı, GGUF SHA-256 özeti, niceleme ve sunucu bilgisi (`model_meta`) bulunur.
- Makaleye şunları ekleyin: işlemci modeli (`lscpu`), vCPU ve fiziksel çekirdek sayısı, RAM, llama.cpp sürümü
  (`llama-server --version`), iş parçacığı ve paralel yuva ayarları.
- Paralel yuvalar sayısal sonuçları çok az değiştirebilir. Bu yüzden kararlılık ayrı bir günde ölçülür.
