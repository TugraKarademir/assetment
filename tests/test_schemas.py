"""JSON doğrulama: şema, kimlikler, ölçüt kümesi, aralık dışı puanların reddi."""
import json

from scoring.schemas import RevisionOutput, make_validator


def _out(**over):
    d = {"item_id": "S1", "response_id": "R1",
         "criteria": [{"criterion_id": c, "score": 2, "rationale": "r", "rubric_evidence": "e"} for c in ("C1", "C2", "C3")],
         "total": 6, "confidence": 0.7}
    d.update(over)
    return json.dumps(d, ensure_ascii=False)


def test_valid_and_fenced(bank):
    v = make_validator(bank["S1"], "R1")
    parsed, err = v("```json\n" + _out() + "\n```")
    assert err is None and parsed["total"] == 6 and not parsed["total_mismatch"]
    parsed, err = v("İşte sonuç: " + _out(total=9) + " teşekkürler")
    assert err is None and parsed["total"] == 6 and parsed["total_mismatch"]


def test_rejections(bank):
    v = make_validator(bank["S1"], "R1")
    bad_range = json.loads(_out()); bad_range["criteria"][0]["score"] = 5
    assert v(json.dumps(bad_range))[1] and "aralık dışında" in v(json.dumps(bad_range))[1]
    neg = json.loads(_out()); neg["criteria"][1]["score"] = -1
    assert v(json.dumps(neg))[1]
    frac = json.loads(_out()); frac["criteria"][0]["score"] = 2.5
    assert v(json.dumps(frac))[1]
    missing = json.loads(_out()); missing["criteria"] = missing["criteria"][:2]
    assert "ölçüt kümesi" in v(json.dumps(missing))[1]
    dup = json.loads(_out()); dup["criteria"][2]["criterion_id"] = "C1"
    assert v(json.dumps(dup))[1]
    assert "kimlik" in v(_out(response_id="R2"))[1]
    assert v(_out(confidence=1.4))[1]
    assert v("bu bir JSON değil")[1]


def test_revision_schema_requires_fields(bank):
    v = make_validator(bank["S1"], "R1", RevisionOutput)
    assert v(_out())[1]
    assert v(_out(changed=False, revision_reason="koruyorum"))[1] is None


def test_evidence_verbatim_flag(bank):
    v = make_validator(bank["S1"], "R1", response_text="Denetimli öğrenmede VERİLER etiketlidir; model tahmin yapar.")
    d = json.loads(_out())
    d["criteria"][0]["rubric_evidence"] = "verilerin etiketlidir"   # yanıtta yok
    d["criteria"][1]["rubric_evidence"] = "veriler etiketlidir"     # var (harf/noktalama farkı yok sayılır)
    d["criteria"][2]["rubric_evidence"] = ""
    parsed, err = v(json.dumps(d, ensure_ascii=False))
    assert err is None
    assert [c["evidence_verbatim"] for c in parsed["criteria"]] == [False, True, None]
