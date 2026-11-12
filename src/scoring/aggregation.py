"""Katman 3(b) basit ortalama/ortanca ve 3(c) öğrenilmiş ağırlıklar (kısıtlı en küçük kareler, çapraz doğrulama).

Öğrenilmiş ağırlıklar:
  min_w  || X w - y ||²   s.t.  w_j ≥ 0,  Σ_j w_j = 1
X: modellerin (revize) ölçüt puanları, y: altın set insan uzlaşı puanı. Ağırlıklar her katmanda yalnızca
EĞİTİM katlarında öğrenilir ve yalnızca dışarıda tutulan katta değerlendirilir (5 katlı CV, öğrenci düzeyinde
katlar). Bir yanıtta bir modelin puanı eksikse ağırlıklar mevcut modeller üzerinde yeniden normalleştirilir.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .utils import round_score


def fit_cls_weights(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Negatif olmayan, toplamı 1 olan ağırlıklar (SLSQP)."""
    X, y = np.asarray(X, float), np.asarray(y, float)
    m = X.shape[1]
    ok = ~np.isnan(X).any(axis=1)
    X, y = X[ok], y[ok]
    if len(y) == 0:
        return np.full(m, 1 / m)
    obj = lambda w: float(np.sum((X @ w - y) ** 2))
    grad = lambda w: 2 * X.T @ (X @ w - y)
    res = minimize(obj, np.full(m, 1 / m), jac=grad, method="SLSQP", bounds=[(0, 1)] * m,
                   constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1, "jac": lambda w: np.ones(m)}],
                   options={"ftol": 1e-12, "maxiter": 500})
    w = np.clip(res.x, 0, None)
    return w / w.sum()


def weighted_predict(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    X = np.asarray(X, float)
    mask = ~np.isnan(X)
    W = np.where(mask, w, 0.0)
    denom = W.sum(axis=1)
    pred = np.where(denom > 0, np.nansum(np.where(mask, X, 0) * W, axis=1) / np.where(denom > 0, denom, 1), np.nan)
    return pred


def round_clip_series(values: pd.Series, lo: pd.Series, hi: pd.Series, rule: str) -> pd.Series:
    out = []
    for v, a, b in zip(values, lo, hi):
        out.append(np.nan if pd.isna(v) else float(min(b, max(a, round_score(v, rule)))))
    return pd.Series(out, index=values.index)


def simple_aggregate(wide: pd.DataFrame, model_cols: list[str], how: str, rule: str) -> pd.Series:
    """Basit ortalama ya da ortanca (eksik modeller atlanır), sonra yapılandırılan kurala göre yuvarlama."""
    X = wide[model_cols]
    v = X.mean(axis=1) if how == "mean" else X.median(axis=1)
    v[X.notna().sum(axis=1) == 0] = np.nan
    return round_clip_series(v, wide.score_min, wide.score_max, rule)


def _groups(df: pd.DataFrame, level: str) -> pd.Series:
    if level == "item":
        return df.item_id
    if level == "item_criterion":
        return df.item_id + "/" + df.criterion_id
    if level == "global":
        return pd.Series("all", index=df.index)
    raise ValueError(level)


def cv_learned_weights(wide: pd.DataFrame, model_cols: list[str], folds: pd.DataFrame, level: str,
                       rule: str) -> tuple[pd.Series, pd.DataFrame]:
    """Dışarıda tutulan kat tahminleri ve kat × grup × model ağırlık tablosu.

    wide: response_id, item_id, criterion_id, score_min, score_max, y, <model_cols>
    folds: response_id, fold
    """
    df = wide.merge(folds[["response_id", "fold"]], on="response_id", how="left")
    if df.fold.isna().any():
        raise ValueError("Bazı altın set yanıtlarının katı yok (gold_folds.csv)")
    df["group"] = _groups(df, level).values
    pred = pd.Series(np.nan, index=df.index)
    wrows = []
    for k in sorted(df.fold.unique()):
        tr, te = df.fold != k, df.fold == k
        for g in df.group.unique():
            trg, teg = tr & (df.group == g), te & (df.group == g)
            if teg.sum() == 0:
                continue
            w = fit_cls_weights(df.loc[trg, model_cols].to_numpy(), df.loc[trg, "y"].to_numpy())
            pred[teg] = weighted_predict(df.loc[teg, model_cols].to_numpy(), w)
            wrows += [{"fold": int(k), "group": g, "model_key": m, "weight": float(wi), "n_train": int(trg.sum())}
                      for m, wi in zip(model_cols, w)]
    rounded = round_clip_series(pred, df.score_min, df.score_max, rule)
    rounded.index = wide.index
    return rounded, pd.DataFrame(wrows)


def full_data_weights(wide: pd.DataFrame, model_cols: list[str], level: str) -> pd.DataFrame:
    """Tüm altın set üzerinde öğrenilen ağırlıklar — yalnızca altın set DIŞI yanıtların operasyonel puanlaması için."""
    df = wide.copy()
    df["group"] = _groups(df, level).values
    rows = []
    for g, d in df.groupby("group"):
        w = fit_cls_weights(d[model_cols].to_numpy(), d["y"].to_numpy())
        rows += [{"group": g, "model_key": m, "weight": float(wi), "n_train": len(d)} for m, wi in zip(model_cols, w)]
    return pd.DataFrame(rows)


def weight_variability(weights: pd.DataFrame) -> pd.DataFrame:
    """Ağırlıkların katlar arası değişimi (ortalama, SS, min, maks)."""
    return (weights.groupby(["group", "model_key"]).weight
            .agg(mean="mean", sd="std", min="min", max="max").reset_index())
