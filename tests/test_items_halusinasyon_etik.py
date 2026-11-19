"""Gerçek çalışma soruları: rubrik geçerliliği, çapa kapsamı, soru–ölçüt eşlemesi, istem ve tek yanıt akışı."""
import pytest

from scoring.config import items_path, load_items
from scoring.layers import PromptRenderer
from scoring.schemas import json_schema_for

PATH = "config/items.halusinasyon_etik.yaml"


@pytest.fixture
def real_bank():
    return load_items(PATH)


def test_structure(real_bank):
    assert real_bank.ids == ["S1", "S2"]
    for it in real_bank.items:
        assert [c.criterion_id for c in it.criteria] == ["C1", "C2", "C3"]
        assert it.total_min == 0 and it.total_max == 12
        assert all(f"({x})" in it.question for x in "abc")       # her alt madde bir ölçüte karşılık gelir
        assert it.reference_answer and len(it.reference_answer.split()) > 150
    assert real_bank["S1"].bloom == "alt" and real_bank["S2"].bloom == "üst"


def test_anchor_coverage_and_mixed_profiles(real_bank):
    for it in real_bank.items:
        for c in it.criteria:
            assert {a.scores[c.criterion_id] for a in it.anchors} == {0, 1, 2, 3, 4}
        mixed = [a for a in it.anchors if len(set(a.scores.values())) > 1]
        assert len(mixed) >= 2                                     # analitik puanlamayı gösteren karma çapalar
        assert len({a.anchor_id for a in it.anchors}) == len(it.anchors)


def test_prompt_and_schema_render(real_bank):
    r = PromptRenderer(rationale_style="short")
    for it in real_bank.items:
        system, user = r.render("layer1_score.j2", item=it, anchors=it.anchors, response_id="R1", response_text="x")
        assert it.question[:40] in user and "Çapa 7" in user
        sch = json_schema_for(it, "R1")
        assert sch["properties"]["total"]["maximum"] == 12


def test_experiment_points_to_real_items(monkeypatch):
    monkeypatch.delenv("SCORING_ITEMS", raising=False)
    assert str(items_path()) == PATH


def test_single_response_with_real_items(monkeypatch):
    monkeypatch.setenv("SCORING_ITEMS", PATH)
    from scoring.try_one import score_single
    res = score_single("S2", "Sistem geçmiş veriden öğrendiği için kadın adaylara karşı yanlı olabilir.",
                       "config/models.mock.yaml")
    assert set(res.rows.layer.astype(int)) == {1, 2, 3}
    assert res.summary.iloc[-1]["Aralık"] == "0–12"
