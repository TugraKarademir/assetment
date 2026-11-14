"""Arayüzün kullandığı tek yanıt puanlama: maskeleme, tüm katmanlar, araştırma deposuna yazmama."""
from pathlib import Path

from scoring.try_one import score_single


def test_score_single_with_mock_panel():
    raw = Path("data/derived/raw_scores.csv")
    before = raw.stat().st_mtime if raw.exists() else None
    r = score_single("S1", "Benim adım Ayşe Demir, numaram 2023456789. Denetimli öğrenmede veriler etiketlidir.",
                     "config/models.mock.yaml")
    assert "Ayşe" not in r.masked_text and "2023456789" not in r.masked_text and r.n_masked >= 2
    assert set(r.rows.layer.astype(int)) == {1, 2, 3}
    tot = r.summary[r.summary["Ölçüt"] == "TOPLAM"].iloc[0]
    assert 0 <= tot["Birleştirici LLM"] <= 12 and 0 <= tot["Ortalama"] <= 12
    assert (Path("logs") / r.run_id / "calls.jsonl").exists()
    assert not (Path("results/manifests") / f"{r.run_id}.json").exists()   # denemeler sonuç klasörünü kirletmez
    assert (raw.stat().st_mtime if raw.exists() else None) == before      # araştırma verisine yazılmaz
