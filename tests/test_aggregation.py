"""Öğrenilmiş ağırlıklar: negatif değil, toplamı 1; CV yalnızca eğitim katlarında öğrenir."""
import numpy as np
import pandas as pd
import pytest

from scoring.aggregation import cv_learned_weights, fit_cls_weights, simple_aggregate, weighted_predict
from scoring.utils import round_score


@pytest.mark.parametrize("seed", range(5))
def test_weights_nonnegative_sum_to_one(seed):
    rng = np.random.default_rng(seed)
    y = rng.integers(0, 5, 300).astype(float)
    X = np.column_stack([y + rng.normal(0, s, 300) for s in (0.3, 1.0, 3.0)])
    X[:, 2] -= 2  # yanlı ve gürültülü model
    w = fit_cls_weights(X, y)
    assert np.all(w >= 0) and w.sum() == pytest.approx(1.0)
    assert w[0] > w[1] > w[2] - 1e-9


def test_weighted_predict_renormalizes_missing():
    X = np.array([[2.0, np.nan, 4.0]])
    assert weighted_predict(X, np.array([0.5, 0.25, 0.25]))[0] == pytest.approx((2 * 0.5 + 4 * 0.25) / 0.75)


def test_rounding_rules():
    assert round_score(2.5, "half_up") == 3 and round_score(2.5, "half_even") == 2
    assert round_score(3.5, "half_even") == 4 and round_score(-0.5, "half_up") == -1


def _wide(n=100, seed=0):
    rng = np.random.default_rng(seed)
    y = rng.integers(0, 5, n)
    df = pd.DataFrame({"response_id": [f"R{i}" for i in range(n)], "item_id": "S1", "criterion_id": "C1",
                       "score_min": 0, "score_max": 4, "y": y,
                       "a": np.clip(y + rng.integers(-1, 2, n), 0, 4), "b": rng.integers(0, 5, n)})
    folds = pd.DataFrame({"response_id": df.response_id, "fold": np.arange(n) % 5})
    return df, folds


def test_cv_weights_per_fold_and_out_of_fold():
    df, folds = _wide()
    pred, w = cv_learned_weights(df, ["a", "b"], folds, "item", "half_up")
    assert pred.notna().all() and pred.between(0, 4).all()
    assert set(w.fold) == set(range(5))
    sums = w.groupby(["fold", "group"]).weight.sum()
    assert np.allclose(sums, 1.0)
    assert (w[w.model_key == "a"].weight > 0.8).all()
    # Kat dışı: bir kattaki y'yi bozmak o katın ağırlıklarını değiştirmez
    df2 = df.copy()
    df2.loc[folds.fold == 0, "y"] = 4 - df2.loc[folds.fold == 0, "y"]
    _, w2 = cv_learned_weights(df2, ["a", "b"], folds, "item", "half_up")
    assert np.allclose(w[w.fold == 0].weight.values, w2[w2.fold == 0].weight.values)


def test_simple_aggregate():
    df = pd.DataFrame({"a": [1, 2, 4], "b": [2, 2, 3], "c": [2, np.nan, 3], "score_min": 0, "score_max": 4})
    assert list(simple_aggregate(df, ["a", "b", "c"], "mean", "half_up")) == [2, 2, 3]
    assert list(simple_aggregate(df, ["a", "b", "c"], "median", "half_up")) == [2, 2, 3]
