#!/usr/bin/env bash
# Aşama A: üç puanlayıcıyı aynı anda başlatır; fiziksel çekirdekleri model boyutuna göre paylaştırır.
source "$(dirname "$0")/common.sh"
P=$(physical_cores)
QT=${QWEN_THREADS:-$((P * 40 / 100))}; GT=${GEMMA_THREADS:-$((P * 35 / 100))}; LT=${LLAMA_THREADS:-$((P - QT - GT))}
QP=${QWEN_PAR:-3}; GP=${GEMMA_PAR:-3}; LP=${LLAMA_PAR:-2}
echo "Fiziksel çekirdek: $P  ->  Qwen $QT, Gemma $GT, Llama $LT"
check_ram 48
start_server qwen  Qwen2.5-14B-Instruct-Q4_K_M.gguf        qwen2.5:14b-instruct-q4_K_M  8001 "$QT" "$QP"
start_server gemma google_gemma-3-12b-it-Q4_K_M.gguf       gemma3:12b                   8002 "$GT" "$GP"
start_server llama Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf  llama3.1:8b-instruct-q4_K_M  8003 "$LT" "$LP"
wait_ready 8001; wait_ready 8002; wait_ready 8003
