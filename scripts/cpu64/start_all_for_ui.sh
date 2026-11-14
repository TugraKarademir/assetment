#!/usr/bin/env bash
# Arayüzde TEK YANIT denemesi için dört modeli birlikte başlatır (her biri tek yuva; çekirdekler eşit paylaşılır).
# Toplu puanlama için DEĞİL: onun için run_study.sh kullanın. Durdurmak: bash scripts/cpu64/stop_servers.sh all
source "$(dirname "$0")/common.sh"
P=$(physical_cores); T=$((P / 4)); [ "$T" -lt 1 ] && T=1
check_ram 40
start_server qwen  Qwen2.5-14B-Instruct-Q4_K_M.gguf        qwen2.5:14b-instruct-q4_K_M  8001 "$T" 1
start_server gemma google_gemma-3-12b-it-Q4_K_M.gguf       gemma3:12b                   8002 "$T" 1
start_server llama Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf  llama3.1:8b-instruct-q4_K_M  8003 "$T" 1
start_server aya   aya-expanse-8b-Q4_K_M.gguf              aya-expanse:8b               8004 "$T" 1
wait_ready 8001; wait_ready 8002; wait_ready 8003; wait_ready 8004
echo "Dört model hazır. Arayüz: uv run scoring ui"
