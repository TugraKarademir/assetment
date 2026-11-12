#!/usr/bin/env bash
# Kararlılık: altın setin AYNI ayarlarla, FARKLI BİR GÜNDE ikinci kez puanlanması (Katman 1, puanlayıcılar).
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/cpu64/env.sh
trap 'bash scripts/cpu64/stop_servers.sh scorers' EXIT
bash scripts/cpu64/start_scorers.sh
uv run scoring score --condition stability --replicate 2 --subset gold --only-models qwen,gemma,llama -y ${LIMIT:+--limit $LIMIT}
bash scripts/cpu64/stop_servers.sh scorers
uv run scoring evaluate
