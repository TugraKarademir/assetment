import numpy as np
import pandas as pd
import pytest

from scoring.embedding_baseline import (OrdinalLogistic, SentenceTransformerEncoder, TfidfDemoEncoder,
                                        cv_embedding_scores, similarity_features)


def test_ordinal_logistic_recovers_order():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(400, 1))
    y = np.clip(np.round(2 + 1.2 * x[:, 0] + rng.normal(0, 0.4, 400)), 0, 4).astype(int)
    m = OrdinalLogistic(0, 4, l2=0.01).fit(x, y)
    assert m.beta_[0] > 0 and np.all(np.diff(m.theta_) > 0)
    assert (m.predict(x) == y).mean() > 0.6
    assert np.allclose(m.predict_proba(x).sum(axis=1), 1)


def test_forbidden_models_rejected():
    for name in ["sentence-transformers/all-mpnet-base-v2", "sentence-transformers/all-MiniLM-L6-v2",
                 "bert-base-multilingual-cased"]:
        with pytest.raises(ValueError):
            SentenceTransformerEncoder(name)


def test_forbidden_in_experiment_config():
    from scoring.config import Experiment, load_experiment
    raw = load_experiment().model_dump()
    raw["embedding"]["models"].append({"name": "sentence-transformers/all-MiniLM-L6-v2"})
    with pytest.raises(ValueError):
        Experiment(**raw)


def test_embedding_pipeline_with_demo_encoder(bank):
    rows = []
    rng = np.random.default_rng(1)
    for i in range(60):
        a = bank["S1"].anchors[i % 5]
        rows.append({"response_id": f"R{i}", "item_id": "S1", "text": a.text + " ek cümle " * int(rng.integers(0, 3))})
    resp = pd.DataFrame(rows)
    enc = TfidfDemoEncoder(corpus=list(resp.text))
    feats = similarity_features(resp, bank, [enc])
    assert len(feats) == 60 * 3
    y = feats[["response_id", "criterion_id"]].copy()
    y["y"] = [int(r[1:]) % 5 for r in y.response_id]
    folds = pd.DataFrame({"response_id": resp.response_id, "fold": (np.arange(60) // 5) % 5})  # katlar sınıfla çakışmasın
    ranges = pd.DataFrame([{"item_id": "S1", "criterion_id": c, "score_min": 0, "score_max": 4} for c in ("C1", "C2", "C3")])
    preds, coefs = cv_embedding_scores(feats, y, folds, ranges, "item", 1.0)
    acc = (preds.merge(y, on=["response_id", "criterion_id"]).pipe(lambda d: (d.pred == d.y).mean()))
    assert acc > 0.8
