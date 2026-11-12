> **Not:** Kurumdaki sunucularda GPU olmadığından varsayılan düzen CPU'dur: [cpu_sunucu_kurulumu.md](cpu_sunucu_kurulumu.md).
> Bu kılavuz ileride GPU erişimi olursa kullanılmak üzere saklanmıştır.

# Tamamen yerel, açık ağırlıklı panel: GPU sunucusu kurulumu

Bu kılavuz, puanlamayı **hiçbir ticari API kullanmadan**, üniversitenin GPU sunucusunda çalışan açık ağırlıklı
modellerle yapmak içindir. Öğrenci yanıtları sunucudan dışarı çıkmaz; bu, KVKK ve etik kurul açısından en
temiz seçenektir.

## 1. Panel

| Rol | Model (Hugging Face) | Aile | Yaklaşık ağırlık belleği |
|---|---|---|---|
| Puanlayıcı | `Qwen/Qwen2.5-32B-Instruct-AWQ` | Alibaba | ~19 GB (AWQ int4) |
| Puanlayıcı | `google/gemma-3-27b-it` | Google | ~28 GB (FP8) / ~54 GB (bf16) |
| Puanlayıcı | `mistralai/Mistral-Small-3.1-24B-Instruct-2503` | Mistral AI | ~25 GB (FP8) / ~48 GB (bf16) |
| Birleştirici (K3a) | `meta-llama/Llama-3.3-70B-Instruct` | Meta | ~70 GB (FP8) / ~40 GB (AWQ) |

- Dört model dört farklı aileden gelir; bu, Verga ve ark. (2024) panel mantığının gereğidir.
- **Daha yeni sürümler:** Bu liste kılavuzun yazıldığı tarihteki bilgiye dayanır. Çalıştırmadan önce aynı
  ailelerin daha yeni "instruct" sürümlerine (ör. Qwen3, Gemma'nın yeni sürümleri) bakın. Qwen3 kullanırsanız
  "düşünme" kipini kapatın: `params: {extra_body: {chat_template_kwargs: {enable_thinking: false}}}`.
- **Erişim izni gereken modeller:** Llama ve Gemma, Hugging Face'te lisans onayı ister. Sunucuda bir kez
  `huggingface-cli login` yapılmalıdır. Bu jeton yalnızca sunucuda tutulur, bu depoya girmez.
- Yapılandırma dosyaları: `config/models.gpu.vllm.yaml` (önerilen) ve `config/models.gpu.ollama.yaml`.

## 2. Donanıma göre plan

| Donanım | Önerilen yol |
|---|---|
| 2× 80 GB (A100/H100) ya da 4× 48 GB | Dört vLLM sunucusu aynı anda (§3a) |
| 1× 80 GB | Modeller **sırayla**: aynı anda tek vLLM sunucusu (§3b) |
| 1× 24–48 GB | Ollama + `--sequential-models` (§3c), ya da daha küçük modeller (14B/12B/8B; daha zayıf, sınırlılık olarak raporlanmalı) |

Kabaca iş yükü (gerçek çalışma: 4 soru × 300 altın set, 3.200 toplam yanıt):

| Çalıştırma | Çağrı sayısı |
|---|---|
| Ablasyon (altın set) | ~15.600 |
| Kararlılık (ikinci puanlama) | ~3.600 |
| Altın set dışı operasyonel puanlama | ~14.000 |

Çağrı başına ~1.500–2.200 girdi ve ~450 çıktı token'ı düşülür.

- **vLLM:** Rubrik ve çapalar her istemde aynı olduğundan önek önbelleği (prefix caching) çok işe yarar. Yüksek
  eşzamanlılıkta model başına birkaç saat sürmesi beklenir.
- **Ollama:** Aynı iş günler sürebilir.

Bu süreler kaba tahmindir; ilk olarak `--limit 5` ile kısa bir deneme yapıp kayıttaki `latency_s` ve token
sayılarından kendi sunucunuz için hesaplayın.

## 3a. vLLM — modeller aynı anda (çok GPU)

```bash
# Sunucuda (Python ortamında): pip install vllm
export HF_HOME=/veri/hf_cache          # modeller buraya iner
REV_QWEN=<commit-karması>             # Hugging Face > Files and versions > commit

CUDA_VISIBLE_DEVICES=0 vllm serve Qwen/Qwen2.5-32B-Instruct-AWQ --revision $REV_QWEN \
  --port 8001 --max-model-len 8192 --gpu-memory-utilization 0.45 --api-key "$LOCAL_API_KEY" &
CUDA_VISIBLE_DEVICES=0 vllm serve google/gemma-3-27b-it --revision <karma> --quantization fp8 \
  --port 8002 --max-model-len 8192 --gpu-memory-utilization 0.45 --api-key "$LOCAL_API_KEY" &
CUDA_VISIBLE_DEVICES=1 vllm serve mistralai/Mistral-Small-3.1-24B-Instruct-2503 --revision <karma> \
  --tokenizer-mode mistral --config-format mistral --load-format mistral --quantization fp8 \
  --port 8003 --max-model-len 8192 --gpu-memory-utilization 0.40 --api-key "$LOCAL_API_KEY" &
CUDA_VISIBLE_DEVICES=1 vllm serve meta-llama/Llama-3.3-70B-Instruct --revision <karma> --quantization fp8 \
  --port 8004 --max-model-len 8192 --gpu-memory-utilization 0.55 --api-key "$LOCAL_API_KEY" &
```

> `--gpu-memory-utilization` oranları örnektir; aynı GPU'yu paylaşan sunucuların toplamı 0,95'i geçmemelidir.
> FP8 en verimli biçimde Hopper/Ada kartlarda (H100, L40S, RTX 4090) çalışır. A100 gibi eski kartlarda AWQ
> sürümlerini tercih edin.

İstemci tarafında (bu depo), `.env`:

```bash
VLLM_QWEN_URL=http://gpu-sunucu:8001/v1
VLLM_GEMMA_URL=http://gpu-sunucu:8002/v1
VLLM_MISTRAL_URL=http://gpu-sunucu:8003/v1
VLLM_LLAMA_URL=http://gpu-sunucu:8004/v1
LOCAL_API_KEY=<sunucuda verdiğiniz anahtar>
```

```bash
uv run scoring check-models --models config/models.gpu.vllm.yaml     # bağlantı + JSON + bağlam testi
uv run scoring run-ablation --models config/models.gpu.vllm.yaml --limit 5 -y --no-evaluate   # kısa deneme
uv run scoring run-ablation --models config/models.gpu.vllm.yaml          # tam çalıştırma
```

## 3b. vLLM — tek GPU'da modeller sırayla

Aynı anda yalnızca bir model sunulur. `--only-models` yalnızca o modeli çağırır; diğer modellerin daha önce
üretilmiş puanları **yalnızca önbellekten** okunur. Önbellekte olmayan bir çağrı yapılmaz ve kaydedilmez.
`--max-layer` katmanları sınırlar. Katman 2 ve 3 yalnızca panelin tüm modellerinin önceki katman puanları hazır
olduğunda yürütülür (`experiment.yaml > aggregation.require_full_panel`).

```bash
M=config/models.gpu.vllm.yaml
# Katman 1: her model sırayla (her satırdan önce sunucuda yalnızca o modeli başlatın)
uv run scoring score --condition ablation --models $M --only-models qwen    --max-layer 1 -y
uv run scoring score --condition ablation --models $M --only-models gemma   --max-layer 1 -y
uv run scoring score --condition ablation --models $M --only-models mistral --max-layer 1 -y
# Katman 2: aynı sıra (Katman 1 önbellekten gelir)
uv run scoring score --condition ablation --models $M --only-models qwen    --max-layer 2 -y
uv run scoring score --condition ablation --models $M --only-models gemma   --max-layer 2 -y
uv run scoring score --condition ablation --models $M --only-models mistral --max-layer 2 -y
# Katman 3: birleştirici
uv run scoring score --condition ablation --models $M --only-models llama -y
# Gömme koşulu, koşul puanları ve değerlendirme
uv run scoring embed-baseline && uv run scoring build-conditions --models $M && uv run scoring evaluate
```

Tek GPU'da her model için sunucuyu şöyle başlatın (§3a'daki komutlar, `--gpu-memory-utilization 0.90` ile ve
tek tek):

```bash
vllm serve <model> --revision <karma> --port 8001 --max-model-len 8192 --gpu-memory-utilization 0.90 ...
```

Bu düzende tüm modeller aynı portu kullanabilir; o zaman `.env` dosyasındaki dört adresi de aynı porta
yönlendirin.

## 3c. Ollama (en kolay kurulum)

```bash
# Sunucuda
curl -fsSL https://ollama.com/install.sh | sh
OLLAMA_CONTEXT_LENGTH=8192 OLLAMA_NUM_PARALLEL=4 OLLAMA_HOST=0.0.0.0:11434 ollama serve &
ollama pull qwen2.5:32b-instruct-q4_K_M; ollama pull gemma3:27b; ollama pull mistral-small3.1:24b; ollama pull llama3.3:70b
```

```bash
# Bu depoda: .env -> LOCAL_BASE_URL=http://gpu-sunucu:11434/v1
uv run scoring check-models --models config/models.gpu.ollama.yaml
uv run scoring run-ablation --models config/models.gpu.ollama.yaml --sequential-models -y
```

`--sequential-models` modelleri aynı anda değil sırayla çağırır; Ollama böylece her katmanda her modeli bir kez
yükler, modeller arasında sürekli gidip gelmez.

> **Bağlam uzunluğu uyarısı:** Ollama'nın varsayılan bağlamı istemlerimiz için kısadır ve aşan kısım hata
> vermeden kesilir (rubrik kaybolur). `OLLAMA_CONTEXT_LENGTH=8192` zorunludur. `check-models`, istemin başına
> konan bir kodu geri isteyerek bunu sınar.

## 4. Güvenlik ve gizlilik

- Sunucu portlarını internete açmayın. vLLM/Ollama'yı yalnızca kurum ağına ya da `127.0.0.1`'e bağlayıp
  istemciden SSH tüneliyle erişin: `ssh -N -L 8001:localhost:8001 kullanici@gpu-sunucu`.
- vLLM'i `--api-key` ile başlatın. İstemci aynı anahtarı `.env > LOCAL_API_KEY` üzerinden gönderir.
- `logs/` (tam istemler) ve `data/` istemci makinede kalır ve `.gitignore` kapsamındadır.

## 5. Tekrar üretilebilirlik

- Her modelin Hugging Face **commit karmasını** `model_revision` alanına yazın ve sunucuyu aynı `--revision`
  ile başlatın. Ollama için `ollama show <model> --modelfile` çıktısındaki özeti (digest) yazın. Bu alanlar
  her çağrı kaydına `model_meta` olarak girer.
- Kullanılan vLLM/Ollama sürümünü ve GPU modelini de not edin (`vllm --version`, `nvidia-smi`). Bunlar sayısal
  sonuçları çok az etkileyebilir.
- Sıcaklık 0 açgözlü (greedy) çözümlemedir. Yine de toplu işleme ve kayan nokta farkları nedeniyle çıktılar
  çalıştırmadan çalıştırmaya birebir aynı olmayabilir. Bu nedenle kararlılık ayrıca ölçülür
  (`score --condition stability --replicate 2`, farklı bir günde).

## 6. GPU'suz sunucu (yalnızca CPU)

Örnek: Huawei RH2288H V3, 2× Xeon E5-2640 v4 (20 çekirdek / 40 iş parçacığı), 64 GB RAM, Windows.

CPU'da metin üretim hızı, modelin bellekten okunma hızıyla sınırlıdır. Kaba beklentiler şöyledir; kesin değer
için `--limit 2` ile ölçün ve kayıttaki `latency_s` değerine bakın.

| Model boyutu (4-bit) | Üretim hızı | Çağrı başına (~2.000 girdi + ~400 çıktı token) | Ablasyon (~15.600 çağrı) |
|---|---|---|---|
| 7–8B | ~6–10 token/sn | ~0,5–1 dk | ~5–11 gün |
| 12B | ~4–6 token/sn | ~1–2 dk | ~2–3 hafta |
| 24–32B | ~1,5–3 token/sn | ~3–5 dk | aylar (uygun değil) |

Öneriler:
- Bu sunucuda **gömme koşulu** rahatça çalışır (CPU yeterli).
- LLM katmanları için `config/models.cpu.single.yaml` (7–12B modeller, Ollama) ile boru hattını gerçek
  modellerle sınayın ve küçük bir pilot yapın: `--limit 10 --sequential-models`.
- Asıl çalışma için GPU erişimi önerilir:
  - **TÜBİTAK ULAKBİM TRUBA**: akademisyenlere ücretsiz GPU (A100 vb.) hesaplama sağlar. Verinin üçüncü taraf bir
    sunucuda işlenmesi etik kurul başvurusunda belirtilmelidir; veri yine Türkiye'de ve kurumsal altyapıda kalır.
  - Üniversitenin HPC merkezi ya da başka bir fakültenin GPU'lu sunucusu.
  - Bu sunucuya düşük profilli bir GPU takmak (ör. NVIDIA L4 24 GB ya da T4 16 GB; 2U kasaya uyumu ve güç
    kablosu üreticiden doğrulanmalıdır).
- 7–12B modeller Türkçe puanlamada 24–32B modellerden belirgin biçimde zayıf olabilir. Küçük modellerle yapılan
  bir çalışma, bu durumu sınırlılık olarak raporlamalıdır.

### Tek 24–40 GB GPU için doğrulanmış 4-bit sürümler (Hugging Face, 2026-11-12)

| Rol | Depo | Commit | Ağırlık |
|---|---|---|---|
| Puanlayıcı | `Qwen/Qwen3-32B-AWQ` (resmî; düşünme kipi kapatılmalı) | `0499c3ac83fdef8810b907a23894ba91e95eddd8` | 19,3 GB |
| Puanlayıcı | `gaunernst/gemma-3-27b-it-int4-awq` (topluluk) | `7cf8bdc81343c635390dd1e1bf590ab22dd6f366` | 18,5 GB |
| Puanlayıcı | `jeffcookio/Mistral-Small-3.2-24B-Instruct-2506-awq-sym` (topluluk) | `49ec31ec0975e46a1aeef24186a45f11be3042b8` | 15,0 GB |
| Birleştirici | `kevinbazira/aya-expanse-32b-gptq-4bit` (topluluk; CC-BY-NC) | `8bce2e1ca4d9edcdc37eda38aa88823d75580196` | 19,9 GB |

40 GB'lık bir kartta bunlar **tek tek** sunulur (§3b, `--only-models`). Topluluk nicelemeleri resmî değildir;
commit karmasıyla sabitleyin ve ilk çalıştırmada `check-models` ile doğrulayın.
