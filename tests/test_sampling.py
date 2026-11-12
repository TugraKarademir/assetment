import numpy as np
import pandas as pd

from scoring.sampling import assign_folds, sample_gold


def test_stratified_sampling_reproducible(bank):
    rng = np.random.default_rng(0)
    rows, off = [], []
    for item in bank.ids:
        for k in range(100):
            rid = f"{item}-{k}"
            rows.append({"response_id": rid, "student_code": f"P{k}", "item_id": item, "text": "x", "is_empty": False})
            for c in bank[item].criterion_ids:
                off.append({"response_id": rid, "criterion_id": c, "score": int(rng.integers(0, 5))})
    resp, off = pd.DataFrame(rows), pd.DataFrame(off)
    g1 = sample_gold(resp, off, bank, 40, 5, seed=1, exclude_ids={"S1-0"})
    g2 = sample_gold(resp, off, bank, 40, 5, seed=1, exclude_ids={"S1-0"})
    assert g1.equals(g2)
    assert (g1.groupby("item_id").size() == 40).all()
    assert "S1-0" not in set(g1.response_id)
    # Orantılılık: her katmandan yaklaşık 8 yanıt
    assert g1.groupby(["item_id", "stratum"]).size().between(7, 9).all()
    f = assign_folds(g1, 5, seed=3)
    assert (f.groupby("student_code").fold.nunique() == 1).all()
