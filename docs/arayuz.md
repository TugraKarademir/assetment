# Arayüz

## Kendi bilgisayarınızda deneme (Windows / macOS / Linux)

Sahte modellerle denemek için GPU, model indirme ya da sunucu gerekmez. Yaklaşık 1 GB disk ve internet bağlantısı
yeterlidir.

1. `puanlama.zip` dosyasını bir klasöre çıkarın (sağ tık > **Tümünü ayıkla**).
2. Klasörü açın ve işletim sisteminize göre başlatın:
   - **Windows:** `ARAYUZU_AC_Windows.bat` dosyasına çift tıklayın. Windows "korunan bilgisayar" uyarısı verirse
     **Ek bilgi > Yine de çalıştır** deyin.
   - **macOS / Linux:** klasörde bir terminal açıp `bash arayuzu_ac.sh` yazın.
3. İlk açılışta `uv` ve Python ortamı kurulur (birkaç dakika). Ardından tarayıcıda arayüz açılır
   (`http://127.0.0.1:8501`).
4. Kenar çubuğunda **Sahte modeller** seçili kalsın. **Yanıt dene** sekmesinde bir soru seçip **Hazır örnek
   yükle** listesinden bir örnek yükleyin (ya da kendi yanıtınızı yazın), sonra **Puanla** düğmesine basın.
5. **Sentetik deneme** sekmesinde kutuyu işaretleyip düğmeye basarsanız 50 sentetik öğrenciyle tüm akış yaklaşık
   bir dakikada çalışır. Ardından **Sonuçlar** sekmesinde tablolar güncellenir.

Kapatmak için açılan siyah pencereyi kapatın. Komut satırından aynı işler: `uv run scoring demo` (sentetik
deneme) ve `uv run scoring ui --open` (arayüz).

> Sahte modeller gerçek dil modeli değildir; puanlar yalnızca akışı ve ekranları göstermek içindir. Gerçek
> modellerle deneme 64 çekirdekli sunucuda yapılır (aşağıda).

## Sunucuda

Tarayıcıdan kullanılan basit bir arayüz:

```bash
uv sync --extra ui          # bir kez (setup_server.sh bunu zaten yapar)
uv run scoring ui           # http://127.0.0.1:8501
```

Arayüz yalnızca sunucunun kendisinden erişilebilir (`127.0.0.1`). Kendi bilgisayarınızdan açmak için bir SSH
tüneli kurun, sonra tarayıcıda `http://localhost:8501` adresini açın:

```bash
ssh -N -L 8501:127.0.0.1:8501 kullanici@sunucu
```

## Sekmeler

| Sekme | Ne işe yarar |
|---|---|
| **Yanıt dene** | Bir soru seçip yanıt yapıştırırsınız (ya da hazır örnek yüklersiniz). Her modelin Katman 1 ve Katman 2 puanını, ortalama ve ortancayı, birleştiricinin nihai puanını ve tüm gerekçeleri gösterir. Yanıttaki ad, numara ve e-posta gönderilmeden önce maskelenir. |
| **Sonuçlar** | `evaluate` çıktıları: ana tablo, soru bazında QWK, Williamson ve ark. ölçütleri, koşul farkları, ağırlıklar, kararlılık, gerekçe kalitesi, Bland–Altman grafikleri. Tablolar CSV olarak indirilebilir. |
| **Modeller** | Seçili paneldeki modellerin bağlantı, JSON ve bağlam kesilmesi testi. |
| **Sentetik deneme** | Sentetik veriyle tek tuşla uçtan uca çalıştırma (`scoring demo`). Mevcut işlenmiş veriyi değiştirir; gerçek veri varsa kendini kapatır. |

Model paneli kenar çubuğundan seçilir:

- **Sahte modeller:** Kurulum gerektirmez. Yalnızca arayüzü ve akışı denemek içindir; puanlar anlamlı değildir.
- **Gerçek yerel modeller:** Model sunucularının açık olması gerekir. 64 çekirdekli sunucuda tek yanıt denemesi
  için dördünü birlikte başlatın:

```bash
bash scripts/cpu64/start_all_for_ui.sh       # durdurmak: bash scripts/cpu64/stop_servers.sh all
```

CPU'da tek bir yanıtın üç katmandan geçmesi birkaç dakika sürebilir.

## Kayıt ve veri

- Her deneme diğer çalıştırmalar gibi `logs/<çalıştırma>/calls.jsonl` dosyasına kaydedilir ve önbelleğe girer.
- Denemeler araştırma verisine (`data/derived/raw_scores.csv`) ve `results/` klasörüne **yazılmaz**.
- Toplu puanlama için arayüz değil, `scripts/cpu64/run_study.sh` kullanılır.
