import pandas as pd
import pytest

from scoring.config import Anchor
from scoring.leakage import LeakageError, check_leakage


def _responses(bank):
    a = bank["S1"].anchors[3]
    return pd.DataFrame({"response_id": ["R1", "R2", "R3"], "item_id": ["S1", "S1", "S1"],
                         "student_code": ["P1", "P2", "P3"],
                         "text": [a.text.upper() + " !!", "Tamamen farklı bir yanıt.", "Başka bir yanıt."]})


def test_identical_text_in_gold_raises(bank):
    with pytest.raises(LeakageError):
        check_leakage(bank, _responses(bank), gold_ids={"R1"})


def test_text_not_in_gold_passes(bank):
    assert check_leakage(bank, _responses(bank), gold_ids={"R2", "R3"})


def test_source_id_in_gold_raises(bank):
    bank["S1"].anchors.append(Anchor(anchor_id="X", text="benzersiz metin", scores={"C1": 1, "C2": 1, "C3": 1},
                                     source_response_id="R3"))
    with pytest.raises(LeakageError):
        check_leakage(bank, _responses(bank), gold_ids={"R3"})
