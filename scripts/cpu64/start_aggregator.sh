#!/usr/bin/env bash
# Aşama B: birleştirici (Aya) tüm fiziksel çekirdeklerle. Puanlayıcılar kapalı olmalıdır (stop_servers.sh scorers).
source "$(dirname "$0")/common.sh"
P=$(physical_cores)
check_ram 16
start_server aya aya-expanse-8b-Q4_K_M.gguf aya-expanse:8b 8004 "${AYA_THREADS:-$P}" "${AYA_PAR:-4}"
wait_ready 8004
