"""Gerçek veri akışı: onam filtresi, soru eşlemesi, uzunluğa göre altın set, kalibrasyon, Excel içe aktarma, uyum, hakem."""
import numpy as np
import pandas as pd
import pytest
from openpyxl import load_workbook

from scoring.config import load_items
from scoring.consent import filter_records, load_consent
from scoring.moodle_io import MoodleRecord, load_column_map, parse_item_map
from scoring.ratings import (disagreements, merge_into_human_scores, rater_agreement, read_rating_workbook,
                             sample_calibration, write_adjudication_sheet)
from scoring.sampling import sample_gold, write_rating_sheet

REAL = "config/items.halusinasyon_etik.yaml"


def _rec(mail, item="S1", text="yanıt"):
    return MoodleRecord({"email": mail, "first_name": "A", "last_name": "B"}, item, text, False)


def test_consent_file_variants(tmp_path):
    cm = load_column_map()
    p = tmp_path / "onam.csv"
    pd.DataFrame({"E-posta adresi": ["a@x", "b@x", "c@x"], "Onam": ["Evet", "Hayır", "Kabul ediyorum"]}).to_csv(p, index=False)
    assert load_consent(p, cm) == {"a@x", "c@x"}
    p2 = tmp_path / "liste.csv"
    pd.DataFrame({"kimlik": ["A@X", "d@x"]}).to_csv(p2, index=False)       # tek sütunlu liste, büyük harf
    assert load_consent(p2, cm) == {"a@x", "d@x"}
    kept, st = filter_records([_rec("a@x"), _rec("b@x"), _rec("a@x", "S2")], {"a@x"})
    assert len(kept) == 2 and st["students_excluded_no_consent"] == 1


def test_item_map_parsing():
    assert parse_item_map("5=S1, 6=S2", {}) == {5: "S1", 6: "S2"}
    assert parse_item_map(None, {"item_map": {1: "S1"}}) == {1: "S1"}


def _responses(n=40):
    rng = np.random.default_rng(0)
    rows = []
    for item in ("S1", "S2"):
        for i in range(n):
            rows.append({"response_id": f"{item}-{i:03d}", "student_code": f"P{i}", "item_id": item,
                         "text": " ".join(["kelime"] * int(rng.integers(5, 120))), "is_empty": False})
    return pd.DataFrame(rows)


def test_gold_without_official_uses_length_and_calibration_disjoint():
    bank = load_items(REAL)
    resp = _responses()
    gold = sample_gold(resp, None, bank, 20, 5, seed=1)
    assert (gold.groupby("item_id").size() == 20).all() and gold.strata_basis.iloc[0].startswith("yanıt uzunluğu")
    cal = sample_calibration(resp, set(gold.response_id), 5, seed=2)
    assert not set(cal.response_id) & set(gold.response_id) and len(cal) == 10


def test_rating_roundtrip_agreement_and_adjudication(tmp_path):
    bank = load_items(REAL)
    resp = _responses(12)
    gold = sample_gold(resp, None, bank, 6, 3, seed=1)
    sheet = tmp_path / "g.xlsx"
    write_rating_sheet(gold, resp, bank, sheet, seed=3)
    files = {}
    for rater, off in (("rater1", 0), ("rater2", 1)):
        wb = load_workbook(sheet)
        for it in ("S1", "S2"):
            ws = wb[it]
            for k, row in enumerate(ws.iter_rows(min_row=4)):
                row[3].value, row[4].value = 2, (2 + off) if k % 2 else 2
        wb.save(tmp_path / f"{rater}.xlsx")
        files[rater] = tmp_path / f"{rater}.xlsx"
    hs = tmp_path / "human.csv"
    item_of = dict(zip(resp.response_id, resp.item_id))
    for rater, f in files.items():
        scores, warn = read_rating_workbook(f, bank)
        assert not warn and len(scores) == 24
        merge_into_human_scores(hs, scores, rater.upper(), rater, "gold")
    human = pd.read_csv(hs, dtype={"response_id": str})
    agr = rater_agreement(human, "gold", bank, item_of)
    assert set(agr["ölçüt"]) == {"C1", "C2"}
    assert agr.set_index(["soru", "ölçüt"]).loc[("S1", "C1"), "tam_uyum"] == 1.0
    dis = disagreements(human, "gold")
    assert len(dis) == 6 and set(dis.criterion_id) == {"C2"}
    adj = tmp_path / "adj.xlsx"
    assert write_adjudication_sheet(dis, resp, bank, adj, seed=1) == 6
    ws = load_workbook(adj)["S1"]
    assert all(r[3].value == "—" and r[4].value is None for r in ws.iter_rows(min_row=4))   # yalnızca ayrışan ölçüt boş
    # yeniden içe aktarma aynı puanlayıcının eski satırlarını değiştirir
    merge_into_human_scores(hs, read_rating_workbook(files["rater1"], bank)[0], "RATER1", "rater1", "gold")
    assert len(pd.read_csv(hs)) == 48


def test_invalid_scores_reported(tmp_path):
    bank = load_items(REAL)
    resp = _responses(6)
    gold = sample_gold(resp, None, bank, 3, 2, seed=1)
    f = tmp_path / "x.xlsx"
    write_rating_sheet(gold, resp, bank, f, seed=1)
    wb = load_workbook(f)
    ws = wb["S1"]
    ws["D4"], ws["E4"], ws["D5"] = 9, "iyi", 2.5
    wb.save(f)
    scores, warn = read_rating_workbook(f, bank)
    assert len(warn) == 3 and scores.empty
