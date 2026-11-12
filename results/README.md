# results/ — ÖRNEK ÇIKTI (sentetik veri + mock modeller)

Bu klasördeki tüm tablo ve grafikler `scripts/run_synthetic_demo.sh` ile **sentetik** yanıtlar ve **mock (sahte)**
puanlayıcılarla üretilmiştir. Yalnızca çıktı biçimini göstermek içindir; hiçbir sayı bilimsel bulgu değildir.

- `embedding`: belgedeki 5 çok dilli gömme modeliyle (Hugging Face; commit karmaları `embedding_model_revisions.csv`).
  Sentetik metinler sınırlı bir cümle bankasından kurulduğundan bu koşul yapay olarak yüksek uyum gösterir (gerçek veride beklenmez).
- `stability.md`: iki replikasyon aynı gün üretildi (`farklı_günler = False`); gerçek çalışmada farklı günlerde yapılmalıdır.
- `bias/`: yanlılık veri dosyaları `.gitignore` ile dışlanır (gerçek veriyle çalışırken öğrenci düzeyi puanlar itilmesin).

Ana tablo: `summary_total_pooled.md` · Williamson ve ark. (2012): `wxb_pass_fail_total.md` ·
Koşul farkları: `paired_differences.md` · Grafikler: `figures/`
