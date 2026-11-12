"""Anonimleştirme: ad, numara, e-posta sızmıyor; eşleme şifreli; kimlik sütunları çıktıda yok."""
import pandas as pd
import pytest

from scoring.anonymize import PIIMasker, anonymize_records, load_mapping
from scoring.moodle_io import MoodleRecord, load_column_map, read_moodle_export


def _rec(first, last, email, num, item, text):
    return MoodleRecord({"first_name": first, "last_name": last, "email": email, "id_number": num,
                         "username": email.split("@")[0]}, item, text, False)


@pytest.fixture
def records():
    return [
        _rec("Ayşe", "Kaya", "ayse.kaya@uni.edu.tr", "2023123456", "S1",
             "Ben Ayşe Kaya, numaram 2023123456. Denetimli öğrenmede veri etiketlidir."),
        _rec("Ayşe", "Kaya", "ayse.kaya@uni.edu.tr", "2023123456", "S2",
             "AYŞE KAYA olarak yazıyorum; iletişim: ayse.kaya@uni.edu.tr, tel 0532 111 22 33."),
        _rec("Deniz", "Demir", "deniz.demir@uni.edu.tr", "2023999999", "S1",
             "Model deniz kenarındaki evleri sınıflandırır. Deniz Demir imzası. Arkadaşım Mehmet Öz ile çalıştık."),
        _rec("İsmail", "Işık", "ismail@uni.edu.tr", "2023555555", "S1",
             "ismail ışık burada. Kara kutu modeller açıklanamaz."),
    ]


def test_no_identity_leaks(tmp_path, records, fernet_key):
    out = anonymize_records(records, tmp_path / "map.enc", tmp_path / "resp.csv", tmp_path / "pii.csv",
                            tmp_path / "sum.csv", key=fernet_key)
    blob = "\n".join(out.text).lower()
    for token in ["ayşe", "kaya", "2023123456", "ayse.kaya@uni.edu.tr", "0532 111 22 33", "ismail", "ışık",
                  "deniz demir", "mehmet", "2023999999"]:
        assert token not in blob, token
    # Belirsiz ad ("deniz") küçük harfli sıradan kullanımda maskelenmez ama raporlanır
    assert "deniz kenarındaki" in blob
    pii = pd.read_csv(tmp_path / "pii.csv")
    assert ((pii.value.str.lower() == "deniz") & (~pii.masked)).any()
    # "Kara kutu" (kara = soyad listesinde değil) korunur
    assert "kara kutu" in blob
    # Kimlik sütunları çıktıda yok
    assert set(out.columns) == {"response_id", "student_code", "item_id", "text", "is_empty", "n_masked",
                                "n_flagged_unmasked"}


def test_mapping_is_encrypted_and_stable(tmp_path, records, fernet_key):
    args = (tmp_path / "map.enc", tmp_path / "resp.csv", tmp_path / "pii.csv", tmp_path / "sum.csv")
    out1 = anonymize_records(records, *args, key=fernet_key)
    raw = (tmp_path / "map.enc").read_bytes()
    assert b"ayse" not in raw.lower() and b"2023123456" not in raw
    m = load_mapping(tmp_path / "map.enc", key=fernet_key)
    assert len(m["students"]) == 3
    out2 = anonymize_records(records, *args, key=fernet_key)  # yeniden çalıştırma aynı kodları üretmeli
    assert out1[["response_id", "student_code"]].equals(out2[["response_id", "student_code"]])
    from scoring.anonymize import generate_key
    with pytest.raises(RuntimeError):
        load_mapping(tmp_path / "map.enc", key=generate_key())


def test_masker_patterns():
    m = PIIMasker([], [], [], common_first_names=["Ahmet"], ambiguous_words=[])
    text, f = m.mask("Adım Ahmet Yılmaz, TC 12345678901, mail a.b@c.com, öğrenci no 20231234.")
    assert "Ahmet" not in text and "Yılmaz" not in text and "12345678901" not in text
    assert "a.b@c.com" not in text and "20231234" not in text
    assert {x.pii_type for x in f} >= {"AD", "TCKN", "EPOSTA", "NUMARA"}
    # 4 haneli yıl ve precision@10 maskelenmez
    t2, _ = m.mask("2023 yılında precision@10 ölçütü kullanıldı.")
    assert t2 == "2023 yılında precision@10 ölçütü kullanıldı."


def test_synthetic_export_roundtrip(tmp_path, fernet_key):
    import subprocess, sys
    exp = tmp_path / "exp.csv"
    subprocess.run([sys.executable, "scripts/make_synthetic.py", "--n-students", "12", "--out", str(exp),
                    "--truth", str(tmp_path / "t.csv")], check=True, capture_output=True)
    recs = read_moodle_export(exp, load_column_map())
    assert len(recs) == 12 * 4
    out = anonymize_records(recs, tmp_path / "m.enc", tmp_path / "r.csv", tmp_path / "p.csv", tmp_path / "s.csv",
                            key=fernet_key)
    raw = pd.read_csv(exp, dtype=str).fillna("")
    blob = "\n".join(out.text).lower()
    for _, r in raw.iterrows():
        if r["E-posta adresi"]:
            assert r["E-posta adresi"].lower() not in blob
            assert r["ID numarası"] not in blob
