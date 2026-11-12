#!/usr/bin/env bash
# 64 çekirdekli tek sunucuda TÜM ÇALIŞMA (kararlılık hariç; o farklı bir günde: run_stability.sh).
# Her adım kaldığı yerden devam eder: kesilirse betiği yeniden çalıştırın, tamamlanan çağrılar önbellekten okunur.
# Uzun sürer; tmux/screen içinde çalıştırın:  tmux new -s puanlama 'bash scripts/cpu64/run_study.sh'
set -euo pipefail
cd "$(dirname "$0")/../.."
D=scripts/cpu64
source $D/env.sh
CONDITION=${CONDITION:-ablation}          # CPU'da süreyi kısaltmak için: CONDITION=ablation_core
SCORERS=qwen,gemma,llama
LIM=${LIMIT:+--limit $LIMIT}              # pilot: LIMIT=5 -> soru başına 5 yanıt
log() { echo "[$(date '+%F %T')] $*"; }
trap 'bash $D/stop_servers.sh all' EXIT

log "Aşama A: puanlayıcılar başlatılıyor"
bash $D/start_scorers.sh
uv run scoring check-models --keys $SCORERS
log "Altın set: Katman 1–2 ($CONDITION)"
uv run scoring score --condition "$CONDITION" --subset gold --only-models $SCORERS --max-layer 2 -y $LIM
log "Altın set dışı (operasyonel): Katman 1–2"
uv run scoring score --condition full --subset all --only-models $SCORERS --max-layer 2 -y $LIM
bash $D/stop_servers.sh scorers

log "Aşama B: birleştirici (tüm çekirdekler)"
bash $D/start_aggregator.sh
uv run scoring check-models --keys aya
uv run scoring score --condition "$CONDITION" --subset gold --only-models aya -y $LIM
uv run scoring score --condition full --subset all --only-models aya -y $LIM
bash $D/stop_servers.sh aggregator

log "Gömme koşulu, koşul puanları, değerlendirme"
uv run scoring embed-baseline
uv run scoring build-conditions
uv run scoring evaluate
uv run scoring export-bias-data
uv run scoring final-scores
if command -v Rscript >/dev/null; then Rscript scripts/bias_model.R; else log "R yok: yanlılık modeli atlandı"; fi
log "Bitti. Sonuçlar: results/   Kararlılık için başka bir gün: bash $D/run_stability.sh"
