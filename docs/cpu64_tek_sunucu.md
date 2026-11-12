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

```bash
# 1) Projeyi sunucuya kopyalayın (zip ya da kendi depo yönteminiz), sonra:
cd puanlama && uv sync --extra spelling --extra embeddings
cp .env.example .env && uv run scoring gen-key >> .env      # MAPPING_KEY
bash scripts/fetch_tr_dictionary.sh                          # Türkçe yazım sözlüğü

# 2) llama.cpp: hazır Linux sürümü (https://github.com/ggml-org/llama.cpp/releases, "ubuntu-x64")
#    ya da kaynaktan:
git clone https://github.com/ggml-org/llama.cpp && cd llama.cpp
cmake -B build -DGGML_NATIVE=ON -DLLAMA_CURL=OFF && cmake --build build -j --target llama-server
export LLAMA_SERVER=$PWD/build/bin/llama-server && cd ..

# 3) Modeller (indirilir ve SHA-256 ile doğrulanır; ~27 GB)
export MODELS_DIR=/veri/modeller
bash scripts/download_cpu_models.sh $MODELS_DIR qwen gemma llama aya
```

`.env` dosyasına (ya da kabuğa) şunları ekleyin. Adresler varsayılan olarak `scripts/cpu64/env.sh` içinden gelir:

```
MODELS_DIR=/veri/modeller
LLAMA_SERVER=/yol/llama.cpp/build/bin/llama-server
LOCAL_API_KEY=<rastgele bir anahtar>
```

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
