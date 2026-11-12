#!/usr/bin/env bash
# RAM < 48 GB: puanlayıcılar TEK TEK, her biri tüm çekirdeklerle. Katman 1 hepsi için, sonra Katman 2 hepsi için,
# sonra birleştirici. Diğer modellerin puanları önbellekten okunur (--only-models).
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/cpu64/common.sh
source scripts/cpu64/env.sh
CONDITION=${CONDITION:-ablation}
LIM=${LIMIT:+--limit $LIMIT}
P=$(physical_cores)
trap 'bash scripts/cpu64/stop_servers.sh all' EXIT
MODELS=(
  "qwen  Qwen2.5-14B-Instruct-Q4_K_M.gguf       qwen2.5:14b-instruct-q4_K_M 8001 3"
  "gemma google_gemma-3-12b-it-Q4_K_M.gguf      gemma3:12b                  8002 3"
  "llama Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf llama3.1:8b-instruct-q4_K_M 8003 2"
)
for layer in 1 2; do
  for spec in "${MODELS[@]}"; do
    read -r name gguf alias port par <<<"$spec"
    start_server "$name" "$gguf" "$alias" "$port" "$P" "$par"; wait_ready "$port"
    uv run scoring check-models --keys "$name"
    uv run scoring score --condition "$CONDITION" --subset gold --only-models "$name" --max-layer "$layer" -y $LIM
    uv run scoring score --condition full --subset all --only-models "$name" --max-layer "$layer" -y $LIM
    stop_server "$name"
  done
done
bash scripts/cpu64/start_aggregator.sh
uv run scoring score --condition "$CONDITION" --subset gold --only-models aya -y $LIM
uv run scoring score --condition full --subset all --only-models aya -y $LIM
stop_server aya
uv run scoring embed-baseline && uv run scoring build-conditions && uv run scoring evaluate
uv run scoring export-bias-data && uv run scoring final-scores
