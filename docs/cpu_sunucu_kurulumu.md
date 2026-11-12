# CPU sunucularında tamamen yerel panel (GPU'suz)

Bu kılavuz, puanlamanın **GPU olmadan**, kurumdaki üç CPU sunucusunda, açık ağırlıklı modellerle yapılması
içindir. Öğrenci yanıtları kurumdan dışarı çıkmaz; API ve GPU gerekmez.

## 1. Sunucu ve model dağılımı

| Sunucu | Model (rol) | GGUF dosyası (Hugging Face) | Boyut | RAM ihtiyacı* |
|---|---|---|---|---|
| 40 çekirdekli | **Qwen2.5-14B-Instruct** (puanlayıcı) | `bartowski/Qwen2.5-14B-Instruct-GGUF` → `Qwen2.5-14B-Instruct-Q4_K_M.gguf` | 9,0 GB | ~16 GB |
| 40 çekirdekli | **Aya-Expanse-8B** (birleştirici, yalnızca K3) | `bartowski/aya-expanse-8b-GGUF` → `aya-expanse-8b-Q4_K_M.gguf` | 5,1 GB | ~10 GB |
| 28 çekirdekli | **Gemma-3-12B-it** (puanlayıcı) | `bartowski/google_gemma-3-12b-it-GGUF` → `google_gemma-3-12b-it-Q4_K_M.gguf` | 7,3 GB | ~14 GB |
| 20 çekirdekli (RH2288H V3, 64 GB) | **Llama-3.1-8B-Instruct** (puanlayıcı) | `bartowski/Meta-Llama-3.1-8B-Instruct-GGUF` → `Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf` | 4,9 GB | ~10 GB |

\* Model ağırlığı + 4 paralel yuva × 8.192 token bağlam için yaklaşık değer.

- Dört model dört farklı aileden gelir (Alibaba, Meta, Google, Cohere). Panel mantığı (Verga ve ark., 2024) korunur.
- En büyük model en hızlı sunucuya verilir; birleştirici aynı sunucuda yalnızca puanlayıcılar bittikten sonra çalışır.
- Dosyaların SHA-256 özetleri `config/models.yaml` (`model_revision`) ve `scripts/cpu_models.tsv` içinde
  sabitlenmiştir; indirme betikleri her dosyayı doğrular.
- **Çekirdek sayısı:** Windows "40 CPUs" diye gösterdiğinde bu çoğunlukla 20 fiziksel çekirdek × 2 iş
  parçacığıdır (hyper-threading). llama.cpp'ye **fiziksel çekirdek sayısını** verin (`-t 20`); iş parçacığı sayısı
  hızı artırmaz, çoğu zaman düşürür.
- Sunucularda yeterli RAM varsa (≥ 32 GB) 40 çekirdekli sunucuda 14B yerine daha büyük bir model denenebilir, ama
  CPU'da süre model boyutuyla doğru orantılı artar (§4).

## 2. Kurulum: llama.cpp `llama-server` (önerilen)

llama.cpp, CPU'da iş parçacığı, NUMA ve önek önbelleği üzerinde en fazla denetimi verir ve OpenAI uyumlu bir uç
nokta sunar.

**İndirme:** https://github.com/ggml-org/llama.cpp/releases adresinden işletim sisteminize uygun CPU sürümünü
indirin (Windows: `llama-...-bin-win-cpu-x64.zip`; bu işlemciler AVX2 destekler, AVX-512 desteklemez).

**Modeller:**

```powershell
# Windows: her sunucuda yalnızca o sunucunun modelini/modellerini indirin
powershell -ExecutionPolicy Bypass -File scripts\download_cpu_models.ps1 -Keys qwen,aya -Dest D:\modeller    # 40 çekirdek
powershell -ExecutionPolicy Bypass -File scripts\download_cpu_models.ps1 -Keys gemma -Dest D:\modeller       # 28 çekirdek
powershell -ExecutionPolicy Bypass -File scripts\download_cpu_models.ps1 -Keys llama -Dest D:\modeller       # 20 çekirdek
```

```bash
# Linux
bash scripts/download_cpu_models.sh /veri/modeller qwen aya
```

**Sunucuyu başlatma** (örnek: 40 çekirdekli sunucu; `-t` fiziksel çekirdek sayısı olmalıdır):

```powershell
llama-server.exe -m D:\modeller\Qwen2.5-14B-Instruct-Q4_K_M.gguf --alias qwen2.5:14b-instruct-q4_K_M `
  --host 0.0.0.0 --port 8001 -t 40 --parallel 4 -c 32768 --cont-batching --cache-reuse 256 --numa distribute `
  --api-key GİZLİ_ANAHTAR
llama-server.exe -m D:\modeller\aya-expanse-8b-Q4_K_M.gguf --alias aya-expanse:8b `
  --host 0.0.0.0 --port 8004 -t 40 --parallel 4 -c 32768 --cont-batching --api-key GİZLİ_ANAHTAR
```

28 çekirdekli sunucuda `-t 28 --parallel 3 -c 24576`, 20 çekirdekli sunucuda `-t 20 --parallel 2 -c 16384`
kullanın.

- `-c` **tüm yuvaların toplam bağlamıdır**: yuva başına en az 8.192 token için `-c = 8192 × --parallel` olmalıdır.
- `--parallel` değeri `config/models.yaml` içindeki `max_concurrency` ile aynı olmalıdır.
- Aya, Qwen ile aynı sunucuda Katman 3'te çalışır. İkisini aynı anda açık tutmak RAM ister; RAM kısıtlıysa Aya'yı
  yalnızca Katman 3 öncesinde başlatın (§5).

**Bu depoda** `.env`:

```
QWEN_URL=http://sunucu40:8001/v1
GEMMA_URL=http://sunucu28:8002/v1
LLAMA_URL=http://sunucu20:8003/v1
AYA_URL=http://sunucu40:8004/v1
LOCAL_API_KEY=GİZLİ_ANAHTAR
```

### Alternatif: Ollama (daha kolay, daha az denetim)

```powershell
setx OLLAMA_CONTEXT_LENGTH 8192 ; setx OLLAMA_NUM_PARALLEL 4 ; setx OLLAMA_HOST 0.0.0.0:11434
# Ollama'yı yeniden başlatın, sonra (40 çekirdekli sunucu örneği):
ollama pull qwen2.5:14b-instruct-q4_K_M ; ollama pull aya-expanse:8b
```

`.env` içindeki adresler `http://sunucuXX:11434/v1` olur. Ollama kullanıldığında `model_revision` alanına
`ollama show <model> --modelfile` çıktısındaki özeti yazın. **`OLLAMA_CONTEXT_LENGTH=8192` zorunludur**; aksi halde
uzun istemlerin başı (rubrik) hata vermeden kesilir.

## 3. Doğrulama ve hız ölçümü

```bash
uv run scoring check-models      # her sunucu: bağlantı, geçerli JSON, bağlam kesilmesi testi
uv run scoring benchmark --n 2   # her modele gerçek istemler; ölçülen hız + tüm çalışmanın süre tahmini
```

`benchmark`, katmanları sıralı ve aynı katmandaki puanlayıcıları paralel (ayrı sunucular) kabul ederek süre
hesaplar. Sonuçlar `results/benchmark/` altına yazılır. Gerçek çalışmanın boyutu varsayılan olarak 4 × 300 altın
set ve 3.200 toplam yanıttır (`--n-gold`, `--n-all` ile değiştirilebilir).

## 4. Süre beklentisi ve azaltma yolları

CPU'da süreyi çıktı token'ları belirler. Bu yüzden `experiment.yaml > prompt.rationale_style: short` (tek
cümlelik gerekçe) varsayılan yapılmıştır; standart kipe göre çıktı yaklaşık yarıya iner.

Bu konteynerde (4 sanal çekirdek, Qwen2.5-1.5B) ölçülen değerler:
- çağrı başına ~2.000 girdi ve ~300 çıktı token'ı;
- tek yuvada çağrı başına ~40 sn.

Sunucularınızdaki gerçek değeri `benchmark` verir. Süreyi kısaltmak için:

| Yol | Kazanç | Bedeli |
|---|---|---|
| `--condition ablation_core` | ~%23 daha az ablasyon çağrısı | Koşul 4 (`full_zeroshot`) üretilmez |
| Operasyonel puanlamada yalnızca `--condition full` | Altın set dışında K1z/K2z çağrısı yok (zaten varsayılan) | — |
| Daha küçük modeller (ör. 40 çekirdekte 14B → 7B) | ~2× hız | Puan kalitesi düşebilir |
| Kararlılık ölçümünü altın setin bir alt kümesinde yapmak (`--limit`) | ~3.600 → birkaç yüz çağrı | Kararlılık tahmini daha geniş GA'lı olur |

Çalıştırma yarıda kesilirse (elektrik, yeniden başlatma) aynı komutu yeniden verin: tamamlanan çağrılar
önbellekten okunur, kaldığı yerden devam eder. Uzun koşular için komutu `tmux`/`screen` (Linux) ya da Görev
Zamanlayıcı (Windows) altında çalıştırın.

## 5. RAM kısıtlıysa: modelleri sırayla açmak

Bir sunucuda iki modeli birden açacak RAM yoksa `--only-models` ve `--max-layer` ile katmanlar sırayla yürütülür:

```bash
uv run scoring score --condition ablation --only-models qwen,gemma,llama --max-layer 2 -y   # K1 + K2 (üç sunucu paralel)
# Aya'yı başlatın (Qwen'i kapatabilirsiniz), sonra:
uv run scoring score --condition ablation --only-models aya -y                              # K3 (K1/K2 önbellekten)
uv run scoring embed-baseline && uv run scoring build-conditions && uv run scoring evaluate
```

## 6. Güvenlik ve gizlilik

- `llama-server`/Ollama portlarını internete açmayın; yalnızca kurum ağına ya da SSH tüneline açın.
- `--api-key` kullanın; istemci aynı anahtarı `.env > LOCAL_API_KEY` ile gönderir.
- `logs/` (tam istemler) ve `data/` puanlamayı başlatan makinede kalır ve `.gitignore` kapsamındadır.

## 7. Raporlama için kaydedilenler

Her çağrının kaydında model adı, GGUF SHA-256 özeti, niceleme türü ve sunucu (`model_meta`) bulunur. Makaleye
ayrıca şunları yazın: llama.cpp/Ollama sürümü, işlemci modeli, çekirdek ve iş parçacığı ayarları. CPU'da sıcaklık
0 ile açgözlü çözümleme yapılır. Paralel yuvalar sayısal sonuçları çok az değiştirebileceğinden kararlılık ayrıca
ölçülür.
