#!/usr/bin/env bash
# macOS / Linux: kurulum + arayüz. Kullanım: bash arayuzu_ac.sh
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v uv >/dev/null; then
  echo "[1/3] uv kuruluyor..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
echo "[2/3] Python ortamı hazırlanıyor..."
uv sync --extra ui --extra spelling
echo "[3/3] Arayüz açılıyor: http://127.0.0.1:8501  (kapatmak için Ctrl+C)"
uv run scoring ui --open
