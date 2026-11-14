#!/usr/bin/env bash
# CPU paneli için GGUF modellerini indirir ve SHA-256 ile doğrular (Linux).
# Kullanım:  bash scripts/download_cpu_models.sh /veri/modeller qwen aya
set -euo pipefail
DEST=${1:-./modeller}; shift || true
KEYS=${*:-"qwen gemma llama aya"}
mkdir -p "$DEST"
tail -n +2 "$(dirname "$0")/cpu_models.tsv" | while IFS=$'\t' read -r key repo file sha tag; do
  [[ " $KEYS " == *" $key "* ]] || continue
  [ -f "$DEST/$file" ] || curl -L --fail -o "$DEST/$file" "https://huggingface.co/$repo/resolve/main/$file"
  if ! echo "$sha  $DEST/$file" | sha256sum -c -; then
    echo "HATA: $file bozuk ya da eksik inmiş. Dosyayı silip betiği yeniden çalıştırın: $DEST/$file"; exit 1
  fi
done
