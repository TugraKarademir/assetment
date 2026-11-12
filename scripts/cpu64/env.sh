#!/usr/bin/env bash
# Model sunucusu adresleri (aynı makine). .env içinde tanımlıysa o değerler önceliklidir.
export QWEN_URL=${QWEN_URL:-http://127.0.0.1:8001/v1}
export GEMMA_URL=${GEMMA_URL:-http://127.0.0.1:8002/v1}
export LLAMA_URL=${LLAMA_URL:-http://127.0.0.1:8003/v1}
export AYA_URL=${AYA_URL:-http://127.0.0.1:8004/v1}
