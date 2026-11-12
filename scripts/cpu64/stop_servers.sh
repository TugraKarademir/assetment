#!/usr/bin/env bash
# Kullanım: stop_servers.sh [scorers|aggregator|all]
source "$(dirname "$0")/common.sh"
case "${1:-all}" in
  scorers)    stop_server qwen; stop_server gemma; stop_server llama ;;
  aggregator) stop_server aya ;;
  *)          stop_server qwen; stop_server gemma; stop_server llama; stop_server aya ;;
esac
