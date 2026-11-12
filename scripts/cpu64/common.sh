#!/usr/bin/env bash
# Ortak ayarlar — 64 çekirdekli tek sanal sunucu (Linux). Gerekirse ortam değişkenleriyle geçersiz kılın.
set -euo pipefail
MODELS_DIR=${MODELS_DIR:-/veri/modeller}                 # GGUF dosyaları (scripts/download_cpu_models.sh)
LLAMA_SERVER=${LLAMA_SERVER:-llama-server}               # llama.cpp ikilisi (PATH'te ya da tam yol)
RUN_DIR=${RUN_DIR:-$HOME/.llama_runs}                    # PID ve günlük dosyaları
CTX_PER_SLOT=${CTX_PER_SLOT:-8192}
API_KEY=${LOCAL_API_KEY:-local}
mkdir -p "$RUN_DIR"

# Fiziksel çekirdek sayısı (sanal makinede vCPU'lar hiper-iş parçacığı olabilir; llama.cpp için fiziksel önemli).
# Sanal makine topolojiyi yanlış bildirirse PHYS_CORES=32 gibi elle verin.
physical_cores() {
  if [ -n "${PHYS_CORES:-}" ]; then echo "$PHYS_CORES"; return; fi
  local n
  n=$(lscpu -p=Core,Socket 2>/dev/null | grep -v '^#' | sort -u | wc -l)
  if [ "$n" -gt 0 ]; then echo "$n"; else nproc; fi
}

# llama.cpp seçenek adları sürümler arasında değişir: isteğe bağlı seçenekler yalnızca destekleniyorsa eklenir.
_HELP=""
supports() {
  [ -z "$_HELP" ] && _HELP=$("$LLAMA_SERVER" --help 2>&1 || true)
  grep -qE -- "(^|[ ,])$1([ ,]|$)" <<<"$_HELP"
}

optional_flags() {
  local f=()
  supports --cont-batching && f+=(--cont-batching)
  supports --cache-reuse && f+=(--cache-reuse 256)
  if [ "${MLOCK:-0}" = "1" ]; then           # bellek kilitleme: memlock yetkisi gerekir (ulimit -l unlimited)
    if supports --mlock; then f+=(--mlock); elif supports --load-mode; then f+=(--load-mode mmap+mlock); fi
  fi
  local nf; nf=$(numa_flag); [ -n "$nf" ] && supports --numa && f+=($nf)
  echo "${f[@]}"
}

numa_flag() {
  local nodes
  nodes=$(lscpu 2>/dev/null | awk -F: '/NUMA node\(s\)/ {gsub(/ /,"",$2); print $2}')
  if [ "${nodes:-1}" -gt 1 ]; then echo "--numa distribute"; fi
}

# start_server <ad> <gguf> <alias> <port> <iş_parçacığı> <paralel_yuva>
start_server() {
  local name=$1 gguf=$2 alias=$3 port=$4 threads=$5 parallel=$6
  local ctx=$((CTX_PER_SLOT * parallel))
  if [ ! -f "$MODELS_DIR/$gguf" ]; then
    echo "Model yok: $MODELS_DIR/$gguf (önce: bash scripts/download_cpu_models.sh $MODELS_DIR)"; exit 1
  fi
  echo "Başlatılıyor: $name  port=$port  iş parçacığı=$threads  paralel=$parallel  bağlam=$ctx"
  command -v "$LLAMA_SERVER" >/dev/null || { echo "llama-server bulunamadı: $LLAMA_SERVER (LLAMA_SERVER=...)"; exit 1; }
  # shellcheck disable=SC2046
  nohup "$LLAMA_SERVER" -m "$MODELS_DIR/$gguf" --alias "$alias" --host 127.0.0.1 --port "$port" \
    -t "$threads" -tb "$threads" --parallel "$parallel" -c "$ctx" $(optional_flags) \
    --api-key "$API_KEY" > "$RUN_DIR/$name.log" 2>&1 &
  echo $! > "$RUN_DIR/$name.pid"
}

wait_ready() {  # wait_ready <port> [zaman_aşımı_sn]
  local port=$1 limit=${2:-900} t=0
  until curl -sf -H "Authorization: Bearer $API_KEY" "http://127.0.0.1:$port/v1/models" >/dev/null; do
    # Süreç çöktüyse beklemeden günlüğü göster
    for pf in "$RUN_DIR"/*.pid; do
      [ -f "$pf" ] || continue
      if ! kill -0 "$(cat "$pf")" 2>/dev/null; then
        echo "Sunucu süreci kapandı: $(basename "$pf" .pid). Günlük:"; tail -5 "${pf%.pid}.log"; exit 1
      fi
    done
    sleep 5; t=$((t + 5))
    if [ "$t" -ge "$limit" ]; then echo "Sunucu $port hazır olmadı; günlük: $RUN_DIR/"; exit 1; fi
  done
  echo "Hazır: port $port"
}

stop_server() {
  local name=$1
  local pidfile="${RUN_DIR:?}/${name:?}.pid"
  if [ -f "$pidfile" ]; then
    kill "$(cat "$pidfile")" 2>/dev/null || true
    rm -f -- "$pidfile"
    echo "Durduruldu: $name"
  fi
}

check_ram() {  # check_ram <gereken_GB>
  local need=$1 avail
  avail=$(awk '/MemAvailable/ {printf "%d", $2/1024/1024}' /proc/meminfo)
  if [ "$avail" -lt "$need" ]; then
    echo "UYARI: kullanılabilir RAM ${avail} GB; bu aşama için ~${need} GB önerilir."
    echo "       Paralel yuvaları azaltın (QWEN_PAR/GEMMA_PAR/LLAMA_PAR=1) ya da docs/cpu64_tek_sunucu.md §5'e bakın."
  fi
}
