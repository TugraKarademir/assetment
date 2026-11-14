#!/usr/bin/env bash
# Sentetik veri + MOCK modellerle uçtan uca deneme çalıştırması (API anahtarı gerektirmez).
# Gerçek modellerle çalıştırmak için --models config/models.yaml kullanın ve .env'i doldurun.
set -euo pipefail
MODELS=${MODELS:-config/models.mock.yaml}
EMB_FLAG=${EMB_FLAG---offline-embedding-demo}   # HuggingFace erişimi varsa: EMB_FLAG="" ile gerçek gömme modelleri

if ! grep -q '^MAPPING_KEY=.\+' .env 2>/dev/null; then
  echo "MAPPING_KEY üretiliyor (.env)"; uv run scoring gen-key 2>/dev/null >> .env
fi
[ -f data/resources/hunspell_tr/index.dic ] || bash scripts/fetch_tr_dictionary.sh || echo "Sözlük indirilemedi; yazım sayımı NA olacak"

uv run python scripts/make_synthetic.py --n-students 50 --seed 20261112          # 1) sentetik Moodle dışa aktarımı
uv run scoring anonymize                                                         # 2) anonimleştirme + maskeleme
uv run python scripts/simulate_human_scores.py --stage official                  # 3) (sentetik) resmî not
uv run scoring sample-gold --synthetic                                           # 4) altın set + katlar + puanlayıcı dosyası
uv run python scripts/simulate_human_scores.py --stage gold                      # 5) (sentetik) iki kör puanlayıcı + hakem
uv run scoring check-leakage                                                     # 6) çapa ↔ altın set sızıntı denetimi
uv run scoring run-ablation --models "$MODELS" -y $EMB_FLAG --no-evaluate         # 7) 8 ablasyon koşulu
uv run scoring score --condition stability --replicate 2 --models "$MODELS" -y   # 8) kararlılık (2. puanlama)
uv run scoring evaluate                                                          # 9) değerlendirme -> results/
uv run scoring export-bias-data                                                  # 10) yanlılık veri dosyası
if command -v Rscript >/dev/null; then Rscript scripts/bias_model.R; else echo "R yok: scripts/bias_model.R atlandı"; fi
