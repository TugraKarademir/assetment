# data/ — sürüm kontrolü DIŞINDA

Bu klasörün içeriği `.gitignore` ile dışlanır (bu dosya hariç).

| Yol | İçerik | Gizlilik |
|---|---|---|
| `raw/` | Moodle dışa aktarımı (kimlikli) | **Kişisel veri** — yalnızca şifreli diskte |
| `private/mapping.enc` | Kod ↔ kimlik eşlemesi (Fernet ile şifreli) | Anahtar `.env` > `MAPPING_KEY` |
| `private/pii_report.csv` | Maskelenen değerlerin kendisi | **Kişisel veri** |
| `processed/responses.csv` | Anonim, maskelenmiş yanıtlar | API'ye giden tek metin kaynağı |
| `human_scores.csv` | İnsan puanları (resmî + altın set) | Anonim kodlarla |
| `derived/` | Altın set, katlar, ham model puanları, koşul puanları | Gerekçeler öğrenci metninden alıntı içerebilir |
| `synthetic/` | Sentetik gizli "gerçek" puanlar | Yalnızca geliştirme |
| `resources/` | Türkçe Hunspell sözlüğü | MIT lisansı |
