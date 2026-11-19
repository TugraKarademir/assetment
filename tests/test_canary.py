"""Gizli işaret (kanarya) denetimi: Türkçe karakter/harf/tire farkına duyarsız eşleşme; soruya özgü; yanlış alarm yok."""
import pandas as pd

from scoring.canary import find_markers, flag_responses, load_canaries, summary


def test_matching_is_robust():
    terms = ["Doruk-Mertens", "Mertens etkisi"]
    assert find_markers("Bu durum DORUK MERTENS etkisi olarak bilinir.", terms) == ["Doruk-Mertens", "Mertens etkisi"]
    assert find_markers("doruk-mertens'e göre", terms) == ["Doruk-Mertens"]
    assert find_markers("Halüsinasyon modelin uydurma bilgi üretmesidir.", terms) == []
    assert find_markers("Yalin kapi yöntemi önerilir", ["Yalın Kapı"]) == ["Yalın Kapı"]
    assert find_markers("Mertensia bitkisi", ["Mertens"]) == []          # kelime sınırı


def test_flags_are_item_specific_and_summary_has_no_ids():
    resp = pd.DataFrame({"response_id": ["R1", "R2", "R3"], "item_id": ["S1", "S1", "S2"],
                         "text": ["Doruk-Mertens etkisi de vardır.", "Normal yanıt.", "Doruk-Mertens etkisi"]})
    flags = flag_responses(resp, {"S1": ["Doruk-Mertens"], "S2": ["Yalın Kapı"]})
    assert flags.canary_hit.tolist() == [True, False, False]   # S2'de S1'in işareti aranmaz
    s = summary(flags)
    assert "response_id" not in s.columns and s.set_index("item_id").loc["S1", "n_flagged"] == 1


def test_example_config_loads():
    c = load_canaries("config/canary.example.yaml")
    assert set(c) == {"S1", "S2"} and all(c.values())


def test_canary_terms_not_in_rubric_or_anchors():
    from scoring.config import load_items
    bank = load_items("config/items.halusinasyon_etik.yaml")
    c = load_canaries("config/canary.example.yaml")
    for it in bank.items:
        blob = " ".join([it.question, it.reference_answer or ""] + [a.text for a in it.anchors] +
                        [d for cr in it.criteria for d in cr.levels.values()])
        assert not find_markers(blob, c[it.item_id])           # işaret rubrikte geçerse yanlış alarm olur
