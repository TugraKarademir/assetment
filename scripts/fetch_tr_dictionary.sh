#!/usr/bin/env bash
# Türkçe Hunspell sözlüğünü indirir (wooorm/dictionaries, MIT lisansı; kaynak: Harun Reşit Zafer, hunspell-tr).
set -euo pipefail
DEST=data/resources/hunspell_tr
mkdir -p "$DEST"
BASE=https://raw.githubusercontent.com/wooorm/dictionaries/main/dictionaries/tr
for f in index.aff index.dic license; do curl -fsSL -o "$DEST/$f" "$BASE/$f"; done
echo "Sözlük indirildi: $DEST"
