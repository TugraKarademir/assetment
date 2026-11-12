#!/usr/bin/env bash
# Hız ölçümü ve süre tahmini: önce puanlayıcılar (aynı anda, gerçek koşullarda), sonra birleştirici tek başına.
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/cpu64/env.sh
trap 'bash scripts/cpu64/stop_servers.sh all' EXIT
bash scripts/cpu64/start_scorers.sh
uv run scoring check-models --keys qwen,gemma,llama
uv run scoring benchmark --keys qwen,gemma,llama --n "${N:-2}" --condition "${CONDITION:-ablation}"
bash scripts/cpu64/stop_servers.sh scorers
bash scripts/cpu64/start_aggregator.sh
uv run scoring check-models --keys aya
uv run scoring benchmark --keys aya --n "${N:-2}" --condition "${CONDITION:-ablation}"
