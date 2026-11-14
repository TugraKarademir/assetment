#!/usr/bin/env bash
# Linux sunucuda TEK SEFERLİK KURULUM (64 çekirdekli CPU sunucusu). Yeniden çalıştırmak güvenlidir:
# tamamlanmış adımlar atlanır. Kök (root) yetkisi GEREKMEZ; eksik sistem paketi varsa komutu yazar ve durur.
#
# Kullanım:  bash scripts/cpu64/setup_server.sh [MODEL_KLASÖRÜ]      (varsayılan: ./modeller)
set -euo pipefail
cd "$(dirname "$0")/../.."
ROOT=$PWD
MODELS_DIR=${1:-${MODELS_DIR:-$ROOT/modeller}}
say() { echo; echo "== $* =="; }

say "1/7 Sistem araçları"
missing=()
for t in curl git cmake g++ make; do command -v "$t" >/dev/null || missing+=("$t"); done
if [ ${#missing[@]} -gt 0 ]; then
  echo "Eksik: ${missing[*]}"
  echo "Kurmak için (Ubuntu/Debian):  sudo apt-get update && sudo apt-get install -y curl git cmake build-essential"
  echo "            (RHEL/Rocky/Alma): sudo dnf install -y curl git cmake gcc-c++ make"
  exit 1
fi
echo "Tamam."

say "2/7 Donanım"
CORES=$(lscpu -p=Core,Socket 2>/dev/null | grep -v '^#' | sort -u | wc -l); VCPU=$(nproc)
RAM=$(awk '/MemTotal/ {printf "%d", $2/1024/1024}' /proc/meminfo)
DISK=$(df -BG --output=avail "$ROOT" | tail -1 | tr -dc '0-9')
echo "vCPU: $VCPU   fiziksel çekirdek (bildirilen): $CORES   RAM: ${RAM} GB   boş disk: ${DISK} GB"
grep -q avx2 /proc/cpuinfo && echo "AVX2: var" || echo "UYARI: AVX2 yok; llama.cpp çok yavaş çalışır."
[ "$DISK" -lt 45 ] && echo "UYARI: en az ~45 GB boş disk önerilir (modeller ~27 GB + gömme modelleri ~10 GB)."

say "3/7 uv (Python ortam yöneticisi)"
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
uv --version
uv sync --extra spelling --extra embeddings

say "4/7 .env"
[ -f .env ] || cp .env.example .env
grep -q '^MAPPING_KEY=.\+' .env || uv run scoring gen-key 2>/dev/null >> .env
grep -q '^LOCAL_API_KEY=.\+' .env || { sed -i '/^LOCAL_API_KEY=/d' .env; echo "LOCAL_API_KEY=$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9')" >> .env; }
grep -q '^MODELS_DIR=' .env || echo "MODELS_DIR=$MODELS_DIR" >> .env
chmod 600 .env
echo ".env hazır (anahtarlar yalnızca bu dosyada; sürüm kontrolüne girmez)."

say "5/7 llama.cpp (llama-server)"
LS=$(grep '^LLAMA_SERVER=' .env | cut -d= -f2- || true)
if [ -z "$LS" ] || [ ! -x "$LS" ]; then
  mkdir -p vendor
  [ -d vendor/llama.cpp ] || git clone --depth 1 https://github.com/ggml-org/llama.cpp vendor/llama.cpp
  cmake -S vendor/llama.cpp -B vendor/llama.cpp/build -DGGML_NATIVE=ON -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF \
        -DCMAKE_BUILD_TYPE=Release > vendor/llama_build.log 2>&1
  cmake --build vendor/llama.cpp/build -j "$VCPU" --target llama-server >> vendor/llama_build.log 2>&1 \
    || { echo "Derleme başarısız; günlük: vendor/llama_build.log"; tail -5 vendor/llama_build.log; exit 1; }
  LS=$ROOT/vendor/llama.cpp/build/bin/llama-server
  sed -i '/^LLAMA_SERVER=/d' .env; echo "LLAMA_SERVER=$LS" >> .env
  (cd vendor/llama.cpp && git rev-parse HEAD) > vendor/llama_cpp_commit.txt
fi
"$LS" --version 2>&1 | tail -2
echo "llama.cpp commit: $(cat vendor/llama_cpp_commit.txt 2>/dev/null || echo bilinmiyor)  (makalede raporlayın)"

say "6/7 Modeller (~27 GB; SHA-256 ile doğrulanır)"
bash scripts/download_cpu_models.sh "$MODELS_DIR" qwen gemma llama aya

say "7/7 Türkçe yazım sözlüğü"
[ -f data/resources/hunspell_tr/index.dic ] || bash scripts/fetch_tr_dictionary.sh || echo "Sözlük indirilemedi (yazım sayımı NA olur)."

say "KURULUM TAMAM"
if [ "$RAM" -ge 48 ]; then RUN=run_study.sh; else RUN=run_lowram.sh; fi
echo "RAM ${RAM} GB -> kullanılacak betik: scripts/cpu64/$RUN"
[ "$CORES" -eq "$VCPU" ] && echo "Not: sanal makine hiper-iş parçacığını bildirmiyor olabilir; hız düşükse PHYS_CORES=$((VCPU / 2)) deneyin."
cat <<MSG

Sıradaki adımlar:
  1) Veriyi yerleştirin:  data/raw/moodle_export.csv  (ya da sentetik deneme: bash scripts/run_synthetic_demo.sh)
  2) Hız ölçümü:          bash scripts/cpu64/benchmark.sh
  3) Pilot:               LIMIT=5 bash scripts/cpu64/$RUN
  4) Tam çalışma:         tmux new -s puanlama 'bash scripts/cpu64/$RUN 2>&1 | tee -a logs/run.log'
MSG
